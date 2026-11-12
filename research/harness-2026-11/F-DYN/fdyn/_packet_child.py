"""Child process: write one F-DYN packet with the UNCHANGED packet writer (wfg_latest.packets.write_regional_packet).

Two injections at the writer's own extension points, as api/adapters/_zone_packet_child.py does:
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
    S = times.shape[0]
    horizon = float(meta['horizon_s'])
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
        s['burning_duration_s'] = T0 + Q
        s['consumed_fraction'] = cf0 * (T0 + Q) / T0
        s['fdyn'] = {k: meta[k] for k in ('fdyn_version', 'label', 'plan_sha256', 'ignition_times_sha256',
                                          'quantum_s', 'member_set', 'members', 'arrival_variant',
                                          'arrival_source', 'arrival_raster_sha256')}
        s['fdyn']['present_fire_source'] = present_fire_source
        if hi_rel is not None:
            s['source_law_version'] = 'wfg.fdyn.envelope-per-cell/1'
            s['fdyn']['envelope'] = ('per-cell law: burning [floor_Q(lo), floor_Q(hi) + T + Q); NOT the scalar law, so '
                                     'the kit independent checker scalar recomputation does not apply')
            if meta.get('arrival_variant') == 'envelope':
                s['fdyn']['soundness'] = ('lo = FIRMS bracket-start, NOT A LOWER BOUND: not guaranteed conservative where '
                                          'fire arrived before that overpass (use envelope_sound)')
        s['fdyn']['duration_widening'] = {'export_cell_duration_s': T0, 'packet_burning_duration_s': T0 + Q,
                                          'export_consumed_fraction': cf0,
                                          'packet_consumed_fraction': cf0 * (T0 + Q) / T0}
        return s

    B.draw_ignitions = fdyn_draws
    B.settings_for = fdyn_settings
    envelope_checks = []
    if hi_rel is not None:
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
    if hi_rel is not None and len(envelope_checks) != 1:
        raise SystemExit('ENVELOPE_NOT_APPLIED_EXACTLY_ONCE')
    sub = times if win is None else times[:, win['r0']:win['r1'] + 1, win['c0']:win['c1'] + 1]
    with np.load(Path(out) / 'constructed_arrays.npz', allow_pickle=False) as z:
        if not np.array_equal(z['ignition_time_s'], sub):
            raise SystemExit('WRITTEN_IGNITIONS_DIFFER_FROM_PLAN')
    if float(hz['valid_until']) != horizon:
        raise SystemExit('HORIZON_NOT_WRITTEN')
    summ.update(region=a.region, event_id=a.event, cutoff=iso, graph_sha256=sha(a.graph), forecast_npz_sha256=sha(npz),
                forecast_record_sha256=sha(recp), fdyn=meta, window=win, status='BUILT')
    with (Path(out) / 'BUILD_SUMMARY.json').open('x') as f:
        json.dump(summ, f, indent=1, default=str)
        f.write('\n')
    print(json.dumps({k: summ.get(k) for k in ('region', 'cutoff', 'shape', 'ignitions_per_member',
                                                'present_fire_cells', 'max_flux_kW_m2')}, default=str))


if __name__ == '__main__':
    main()
