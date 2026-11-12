"""Child process: write one F-DYN packet with the UNCHANGED packet writer (wfg_latest.packets.write_regional_packet).

Injections at the writer's own extension points, as api/adapters/_zone_packet_child.py does (plus bridge.construct
for the per-cell variants, and bridge.radiation_operator_identity for a repo-relative module path, IDENTITY_PATH_RULE.md):
  * bridge.draw_ignitions returns the F-DYN schedule (full event grid) instead of random draws;
  * bridge.settings_for sets horizon_s to the F-DYN horizon and adds an ``fdyn`` entry, so the settings digest, the
    construction id and the scenario ids identify the F-DYN output.
Run: python -I -B _packet_child.py --plan PLAN.npz --graph graph.json --export-dir DIR --cutoff ISO --region R
     --event KFS_01 --window-json '{...}' --out DIR
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WFG = REPO / 'integration' / 'src' / 'wfg_latest'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def repo_relative_radiation_identity(ident, pinned_sha):
    """IDENTITY_PATH_RULE.md: the frozen bridge's {module: absolute path, sha256} with the module path made
    repo-relative (POSIX); refuses a module outside the repository or with a sha other than the vendored pin."""
    mod = Path(ident['module']).resolve()
    try:
        rel = mod.relative_to(REPO.resolve())
    except ValueError:
        raise SystemExit(f'RADIATION_MODULE_OUTSIDE_REPO {mod}')
    if ident['sha256'] != pinned_sha or sha(mod) != pinned_sha:
        raise SystemExit('RADIATION_MODULE_NOT_PINNED')
    return {'module': rel.as_posix(), 'sha256': ident['sha256'],
            'module_path_form': 'repo-relative (F-DYN IDENTITY_PATH_RULE.md)'}


def rebuild_members(B, np, built, epsg, ext_of):
    """The bridge.construct member loop (verbatim law) with per-cell extinction ends ext_of(member, births)."""
    st = built['settings']
    horizon = float(st['horizon_s'])
    current, remaining = built['current'], float(built['remaining_s'])
    model = B.radiation_model(built['affine_transform'], st, epsg)
    out = []
    for s_idx in range(built['events'].shape[0]):
        births = built['events'][s_idx]
        fin = np.isfinite(births)
        ext = ext_of(s_idx, births)
        knots = {0.0, horizon}
        knots.update(float(v) for v in births[fin] if 0.0 < v < horizon)
        knots.update(float(v) for v in ext[fin] if 0.0 < v < horizon)
        if current.any() and 0.0 < remaining < horizon:
            knots.add(float(remaining))
        bp = sorted(knots)
        flame, flux = [], []
        for left in bp[:-1]:
            active = (fin & (births <= left) & (left < ext))
            if current.any() and left < remaining:
                active = active | current
            f = model.predict_details(active.astype(float)).incident_heat_flux_w_m2.astype(float)
            if active.any():
                f = np.nextafter(f + 1e-8 * max(1.0, float(f.max())), np.inf)
            flame.append(active.copy()); flux.append(f)
        out.append({'breakpoints': bp, 'flame': np.array(flame, dtype=bool), 'flux_w_m2': np.array(flux, dtype=float),
                    'ignition_time_s': births, 'extinction_breakpoint_s': ext})
    return out


def burnset_members(B, np, built, epsg, footprint):
    """ENVELOPE_BURNSET_RULE.md: one interval [0, H) with flame = burn set | present fire; nothing clears."""
    st = built['settings']
    horizon = float(st['horizon_s'])
    model = B.radiation_model(built['affine_transform'], st, epsg)
    active = np.asarray(footprint, bool) | np.asarray(built['current'], bool)
    f = model.predict_details(active.astype(float)).incident_heat_flux_w_m2.astype(float)
    if active.any():
        f = np.nextafter(f + 1e-8 * max(1.0, float(f.max())), np.inf)
    out = []
    for s_idx in range(built['events'].shape[0]):
        births = built['events'][s_idx]
        out.append({'breakpoints': [0.0, horizon], 'flame': active[None].copy(), 'flux_w_m2': f[None].copy(),
                    'ignition_time_s': births, 'extinction_breakpoint_s': np.full(births.shape, np.inf)})
    return out


def scalar_ext(B, np, births, T):
    ext = np.full(births.shape, np.inf)
    for idx in zip(*np.nonzero(np.isfinite(births))):
        ext[idx] = B.round_up_sum(births[idx], T)
    return ext


def same_members(np, a, b):
    return all(x['breakpoints'] == y['breakpoints'] and np.array_equal(x['flame'], y['flame']) and
               np.array_equal(x['flux_w_m2'], y['flux_w_m2']) and np.array_equal(x['extinction_breakpoint_s'],
                                                                                  y['extinction_breakpoint_s'])
               for x, y in zip(a, b)) and len(a) == len(b)


def main():
    ap = argparse.ArgumentParser()
    for k in ('--plan', '--graph', '--export-dir', '--cutoff', '--region', '--event', '--window-json', '--out'):
        ap.add_argument(k, required=True)
    for k in ('--support-mask', '--support-rule', '--support-provenance'):   # F-9.3 SUPPORT_WIRING_RULE.md
        ap.add_argument(k, default=None)
    a = ap.parse_args()
    sys.path.insert(0, str(WFG))
    import build_packet as BP            # noqa: E402
    BP.install_radiation()
    import numpy as np                   # noqa: E402
    import bridge as B                   # noqa: E402
    import contract as CT                # noqa: E402
    import packets as P                  # noqa: E402

    with np.load(a.plan, allow_pickle=False) as z:
        times = z['times'].copy()
        meta = json.loads(str(z['meta']))
        hi_rel = z['hi_rel'].copy() if 'hi_rel' in z.files else None
        footprint = z['burnset_mask'].copy() if 'burnset_mask' in z.files else None
    S = times.shape[0]
    horizon = float(meta['horizon_s'])
    noreentry = meta.get('transform') == 'no_reentry/1'          # NOREENTRY_RULE.md (absent: v3.5 path unchanged)
    calls = []

    def fdyn_draws(q, scenario_count, seed, horizon_s):
        if scenario_count != S or float(horizon_s) != horizon or np.asarray(q).shape != times.shape[1:]:
            raise ValueError('FDYN_DRAW_MISMATCH')
        calls.append(1)
        return times.copy()

    orig = B.settings_for

    Q = float(meta['quantum_s'])

    def fdyn_settings(T):
        s = orig(T)
        T0, cf0 = float(s['burning_duration_s']), float(s['consumed_fraction'])
        s['horizon_s'] = horizon
        s['scenario_count'] = S
        s['timing'] = 'arrival-time raster (F-DYN), not uniform draws'
        # floor(ignition) + widened duration T+Q covers [exact ignition, exact ignition + T); consumed fraction scaled
        # so the emitted heat-release-rate density fuel*H*cf/T is unchanged (conservative for contact and radiation)
        burnset = meta.get('arrival_variant') == 'envelope_burnset'
        # PACKET_CONSISTENCY_RULE.md A (burn set on [0, H)) and NOREENTRY_RULE.md (born cells closed to H): T = H
        Tp = horizon if (burnset or noreentry) else T0 + Q
        s['burning_duration_s'] = Tp
        s['consumed_fraction'] = cf0 * Tp / T0
        s['fdyn'] = {k: meta[k] for k in ('fdyn_version', 'label', 'plan_sha256', 'ignition_times_sha256',
                                          'quantum_s', 'member_set', 'members', 'arrival_variant',
                                          'arrival_source', 'arrival_raster_sha256')}
        s['fdyn']['present_fire_source'] = present_fire_source
        if 'quantization' in meta:                                  # v3.1 convention (QUANT_v3_1_RULE.md)
            s['fdyn']['quantization'] = meta['quantization']
        if hi_rel is not None:
            s['source_law_version'] = 'wfg.fdyn.envelope-per-cell/1'
            s['fdyn']['envelope'] = ('per-cell law: burning [floor_Q(lo), floor_Q(hi) + T + Q); NOT the scalar law, so '
                                     'the kit independent checker scalar recomputation does not apply')
            if meta.get('arrival_variant') == 'envelope_sound':
                s['fdyn']['soundness'] = ('WITHDRAWN AS A BOUND (Nora, ledger row 28): lo = last confirmed-clear view is '
                                          'not a lower bound because detection-to-cell attribution is pixel-level; '
                                          'bracket scenario only, do not score')
            if meta.get('arrival_variant') == 'envelope_burnset':
                s['source_law_version'] = 'wfg.fdyn.burnset-scalar/1'
                s['fdyn']['envelope'] = ('static law as the writer scalar law: birth 0 on burn set minus present fire, '
                                         'T = H, R = H; burn set | present fire on [0, H) in HAZARD and in the arrays '
                                         '(ENVELOPE_BURNSET_RULE.md, PACKET_CONSISTENCY_RULE.md A)')
                s['fdyn']['soundness'] = ('SOUND RELATIVE TO THE FINAL MAPPED BURN SET (fire never mapped is outside it): lo = ignition, no cell cleared within the horizon; single implementation, not independently checked (Nora PASS WITH NOTES, row 32)')
            if meta.get('arrival_variant') == 'envelope':
                s['fdyn']['soundness'] = ('lo = FIRMS bracket-start, NOT A LOWER BOUND: not guaranteed conservative where '
                                          'fire arrived before that overpass. HAZARD-only; not for array-based routing '
                                          'or certification (PACKET_CONSISTENCY_RULE.md B)')
        if noreentry:                             # NOREENTRY_RULE.md: own identity (settings digest, ids), labelled
            s['source_law_version'] = 'wfg.fdyn.no-reentry-scalar/1'
            s['fdyn']['transform'] = 'no_reentry/1'
            s['fdyn']['no_reentry'] = ('no re-entry: a cell born at b is closed on [b, H), present fire on [0, H), '
                                       'burned-out-at-start cells open (Richard PacketModel never); scalar law T = R = H '
                                       '(NOREENTRY_RULE.md); default for person-facing outputs')
            s['fdyn']['no_reentry_flux'] = "burning intensity held to the horizon; raises dose and peak vs reopening; contact set equals Richard's never-clears"
            s['fdyn'].pop('envelope', None)
            if meta.get('arrival_variant') == 'envelope':
                s['fdyn']['soundness'] = ('lo = FIRMS bracket-start, NOT A LOWER BOUND: not guaranteed conservative where '
                                          'fire arrived before that overpass; no re-entry from lo, scalar law, arrays '
                                          'consistent with HAZARD (NOREENTRY_RULE.md)')
        s['fdyn']['duration_widening'] = {'export_cell_duration_s': T0, 'packet_burning_duration_s': Tp,
                                          'export_consumed_fraction': cf0,
                                          'packet_consumed_fraction': cf0 * Tp / T0}
        return s

    B.draw_ignitions = fdyn_draws
    B.settings_for = fdyn_settings
    rad_calls = []
    orig_rad = B.radiation_operator_identity

    def fdyn_radiation_identity():          # IDENTITY_PATH_RULE.md: host-independent module path, same sha
        rad_calls.append(1)
        return repo_relative_radiation_identity(orig_rad(), BP.RADIATION_SHA256['heat.py'])

    B.radiation_operator_identity = fdyn_radiation_identity
    envelope_checks = []
    nr_checks = []
    if noreentry and footprint is None:          # NOREENTRY_RULE.md: births from the plan, T = R = H (burnset keeps its path)
        orig_nr = B.construct

        def noreentry_construct(forecast, *, cutoff_utc, epsg, settings):
            built = orig_nr(forecast, cutoff_utc=cutoff_utc, epsg=epsg, settings=settings)
            T = float(built['settings']['burning_duration_s'])
            if T != horizon:
                raise SystemExit('NOREENTRY_T_NOT_H')
            again = rebuild_members(B, np, built, epsg, lambda k, b: scalar_ext(B, np, b, T))
            if not same_members(np, again, built['members']):
                raise SystemExit('NOREENTRY_LOOP_DOES_NOT_REPRODUCE_WRITER')
            built['remaining_s'], built['remaining_exact'] = horizon, False       # present fire closed to H
            built['members'] = rebuild_members(B, np, built, epsg, lambda k, b: scalar_ext(B, np, b, T))
            nr_checks.append(1)
            return built
        B.construct = noreentry_construct
    if hi_rel is not None and not (noreentry and footprint is None):
        orig_construct = B.construct

        def envelope_construct(forecast, *, cutoff_utc, epsg, settings):
            built = orig_construct(forecast, cutoff_utc=cutoff_utc, epsg=epsg, settings=settings)
            T = float(built['settings']['burning_duration_s'])
            # self-check: the re-implemented loop with scalar ends reproduces the unchanged writer's members exactly
            again = rebuild_members(B, np, built, epsg, lambda k, b: scalar_ext(B, np, b, T))
            if not same_members(np, again, built['members']):
                raise SystemExit('ENVELOPE_LOOP_DOES_NOT_REPRODUCE_WRITER')
            H = built['events'].shape[1:]
            full = H == hi_rel.shape[1:]
            if not full:
                raise SystemExit('ENVELOPE_ONLY_ON_FULL_GRID')
            if footprint is not None:
                if footprint.shape != H:
                    raise SystemExit('FOOTPRINT_MASK_SHAPE')
                if T != horizon:
                    raise SystemExit('BURNSET_T_NOT_H')
                built['remaining_s'], built['remaining_exact'] = horizon, False        # R = H (rule A)
                built['members'] = rebuild_members(B, np, built, epsg, lambda k, b: scalar_ext(B, np, b, T))
                ref = burnset_members(B, np, built, epsg, footprint)                     # the stated law
                for m, r in zip(built['members'], ref):
                    if m['breakpoints'] != r['breakpoints'] or not np.array_equal(m['flame'], r['flame']):
                        raise SystemExit('BURNSET_SCALAR_LAW_DIFFERS_FROM_STATED_LAW')
            else:
                built['members'] = rebuild_members(B, np, built, epsg, lambda k, b: scalar_ext(B, np, np.where(np.isfinite(b), hi_rel[k], np.inf), T))
            envelope_checks.append(1)
            return built
        B.construct = envelope_construct
    iso, _ = CT.normalize_cutoff(a.cutoff)
    exp = Path(a.export_dir)
    tag = CT.tag(iso)
    npz = exp / ('FORECAST_%s.npz' % tag)
    recp = exp / ('FORECAST_RECORD_%s.json' % tag)
    rec = json.loads(recp.read_text())
    synthetic = rec.get('fdyn_synthetic')
    if synthetic is not None:
        # this process only: the binding compares record.checkpoint_sha256 with this constant and the writer stamps it
        # into the packet identity, so both say SYNTHETIC instead of claiming the c651 checkpoint
        if not str(rec['checkpoint_sha256']).startswith('SYNTHETIC-fdyn-present-fire-from-TOA:'):
            raise SystemExit('SYNTHETIC_RECORD_WITHOUT_MARKER')
        CT.CHECKPOINT_SHA256 = rec['checkpoint_sha256']
    elif rec.get('checkpoint_sha256') != CT.CHECKPOINT_SHA256:
        raise SystemExit('RECORDED_EXPORT_NOT_C651')
    present_fire_source = (('SYNTHETIC: ' + synthetic['label']) if synthetic else
                           'recorded c651 export at a recorded input time (equals the kriged TOA thresholded there)')
    graph = json.loads(Path(a.graph).read_text())
    epsg = int(graph['crs'].split(':', 1)[1])
    win = json.loads(a.window_json)  # null = full event grid (un-clipped)
    out, hz, summ = P.write_regional_packet(graph, a.graph, npz, rec, sha(recp), iso, epsg, a.out,
                                            event_id=a.event, region_id=a.region, window=win)
    if len(calls) != 1:
        raise SystemExit('DRAW_INJECTION_NOT_USED_EXACTLY_ONCE')
    if len(rad_calls) != 1:
        raise SystemExit('RADIATION_IDENTITY_INJECTION_NOT_USED')
    if noreentry and footprint is None and len(nr_checks) != 1:
        raise SystemExit('NOREENTRY_NOT_APPLIED_EXACTLY_ONCE')
    if hi_rel is not None and not (noreentry and footprint is None) and len(envelope_checks) != 1:
        raise SystemExit('ENVELOPE_NOT_APPLIED_EXACTLY_ONCE')
    sub = times if win is None else times[:, win['r0']:win['r1'] + 1, win['c0']:win['c1'] + 1]
    with np.load(Path(out) / 'constructed_arrays.npz', allow_pickle=False) as z:
        if not np.array_equal(z['ignition_time_s'], sub):
            raise SystemExit('WRITTEN_IGNITIONS_DIFFER_FROM_PLAN')
    if float(hz['valid_until']) != horizon:
        raise SystemExit('HORIZON_NOT_WRITTEN')
    variant = meta.get('arrival_variant')
    if a.support_mask is not None:                # F-9.3 SUPPORT_WIRING_RULE.md: before the envelope NaN rewrite
        with np.load(a.support_mask, allow_pickle=False) as z:
            smask = np.asarray(z['support'])
        rec = {'rule': a.support_rule, 'provenance': json.loads(a.support_provenance),
               'unsupported_cells': int((~smask).sum()), 'cells': int(smask.size)}
        if smask.all():                           # rule B: an all-true mask is never applied
            rec.update(applied=False, reason='all cells supported')
        else:
            sys.path.insert(0, str(REPO / 'research' / 'harness-2026-11' / 'F-9.3' / 'support_mask'))
            import packets_f93 as PF              # noqa: E402  (the verified wrapper, merged #152)
            try:
                hz, summ = PF.apply_support(Path(out), graph, summ, smask, a.support_rule, rec['provenance'])
            except Exception:
                Path(out, 'SUPPORT_WRITE_FAILED').write_text('the support channel was not applied; do not use this packet\n')
                raise
            rec.update(applied=True, support_writer=summ['support_writer'])
        meta['support'] = rec
    arrays = Path(out) / 'constructed_arrays.npz'
    hazard_only = variant == 'envelope' and not noreentry   # no-re-entry envelope is scalar-law (NOREENTRY_RULE.md)
    if hazard_only:                              # PACKET_CONSISTENCY_RULE.md B: HAZARD-only, array path must refuse
        meta['arrays_sha256_as_written'] = sha(arrays)
        with np.load(arrays, allow_pickle=False) as z:
            arr = {k: z[k] for k in z.files}
        arr['ignition_time_s'] = np.full(arr['ignition_time_s'].shape, np.nan)
        arr['per_cell_law_HAZARD_only'] = np.array(True)
        np.savez_compressed(arrays, **arr)
        summ['files_sha256']['constructed_arrays.npz'] = sha(arrays)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from fdyn import consistency                 # PACKET_CONSISTENCY_RULE.md C: builder self-check, every variant
    chk = consistency.check(out)
    if hazard_only:
        if not str(chk.get('array_path', '')).startswith('REFUSED'):
            raise SystemExit('HAZARD_ONLY_ARRAYS_NOT_REFUSED')
    elif not chk['consistent']:
        if a.support_mask is not None and meta.get('support', {}).get('applied'):   # Hannah row 50 note 4
            Path(out, 'SUPPORT_WRITE_FAILED').write_text('consistency check failed after the support channel was applied; do not use this packet\n')
        raise SystemExit('PACKET_INCONSISTENT ' + json.dumps(chk.get('member_rows')))
    meta['packet_self_check'] = {k: chk.get(k) for k in ('consistent', 'array_path', 'member_rows')}
    # writer identity, copied from the written packet (Richard's condition, NOREENTRY_RULE.md): BUILD_SUMMARY only
    hz_id = json.loads((Path(out) / 'HAZARD.json').read_text())['provenance']['identity']
    nm = json.loads((Path(out) / 'NATIVE_METADATA.json').read_text())
    st = nm['settings']
    here = Path(__file__).resolve().parent
    writer_identity = {'packet_writer_sha256': hz_id['packet_writer_sha256'],
                       'base_packet_writer_sha256': hz_id.get('base_packet_writer_sha256'),
                       'support_writer': hz_id.get('support_writer'),
                       'source_law_version': st.get('source_law_version') or nm['construction']['assumptions'].get('version'),
                       'transform': st.get('fdyn', {}).get('transform', 'reopening'),
                       'no_reentry_flux': st.get('fdyn', {}).get('no_reentry_flux'),
                       'fdyn_builder_sha256': {n: sha(here / n) for n in ('build.py', '_packet_child.py')}}
    summ.update(region=a.region, event_id=a.event, cutoff=iso, graph_sha256=sha(a.graph), forecast_npz_sha256=sha(npz),
                forecast_record_sha256=sha(recp), fdyn=meta, window=win, writer_identity=writer_identity, status='BUILT')
    with (Path(out) / 'BUILD_SUMMARY.json').open('x') as f:
        json.dump(summ, f, indent=1, default=str)
        f.write('\n')
    print(json.dumps({k: summ.get(k) for k in ('region', 'cutoff', 'shape', 'ignitions_per_member',
                                                'present_fire_cells', 'max_flux_kW_m2')}, default=str))


if __name__ == '__main__':
    main()
