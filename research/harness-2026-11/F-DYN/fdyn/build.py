"""Build one F-DYN hazard packet (v2): arrival raster -> multi-hour packet through the unchanged writer.

    python3 research/harness-2026-11/F-DYN/fdyn/build.py --region yeongdeok_2025 --start 20250325T230000Z \
        --horizon-h 5 --arrival RASTER --arrival-variant kriged_mean [--sd SD.tif] [--member-set central] \
        [--quantum-s 300] [--domain recorded_window | full_grid --graph GRAPH.json] --out OUT_DIR

RASTER is a GeoTIFF (EPSG:5179, the KFS_01 export grid) or an .npz with an ``arrival_h`` array on that grid, in
hours since t0 = 2025-03-22 02:24 UTC (Choi 2026 convention). Its SHA-256 and the variant label are recorded in the
plan and in the packet settings (so they enter the settings digest and the scenario ids).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from fdyn import ignitions  # noqa: E402

REPO = HERE.parents[3]
INPUTS = REPO / 'data' / 'routing' / 'latest_inputs_try02'
GRAPHS = REPO / 'data' / 'routing' / 'graphs'
EVENT = 'KFS_01'
T0_UTC = dt.datetime(2025, 3, 22, 2, 24, tzinfo=dt.timezone.utc)
EXPORT_AFFINE = (375.0, 0.0, 1085250.0, 0.0, -375.0, 1845375.0)
EXPORT_SHAPE = (79, 237)
KRIGED_TOA_SHA256 = 'fe81f945ddb9dd68f9de27b5865ca12d1a345934540934b723bd66b7d01fa953'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read_exact(path: Path | None):
    """v3.1: the variant's timestamp_exact mask (cells whose arrival is a source timestamp), None if not recorded."""
    if path is None or path.suffix != '.npz':
        return None
    with np.load(path, allow_pickle=False) as z:
        return z['timestamp_exact'].astype(bool) if 'timestamp_exact' in z.files else None


def read_raster(path: Path) -> np.ndarray:
    if path.suffix == '.npz':
        with np.load(path, allow_pickle=False) as z:
            a = z['arrival_h'].astype(float)
            aff = tuple(float(v) for v in z['affine_transform'])
            t0 = str(z['t0_utc'])
        if dt.datetime.fromisoformat(t0) != T0_UTC:
            raise SystemExit(f'ARRIVAL_T0 {t0}')
    else:
        import rasterio
        with rasterio.open(path) as s:
            a = s.read(1).astype(float)
            aff = tuple(float(v) for v in list(s.transform)[:6])
            if s.crs.to_epsg() != 5179:
                raise SystemExit('ARRIVAL_CRS')
            t0 = s.tags().get('t0_utc')
            if t0 is not None and dt.datetime.fromisoformat(t0).replace(tzinfo=dt.timezone.utc) != T0_UTC:
                raise SystemExit(f'ARRIVAL_T0 {t0}')
    if aff != EXPORT_AFFINE or a.shape != EXPORT_SHAPE:
        raise SystemExit(f'ARRIVAL_GRID {aff} {a.shape}')
    return a


def add_b0(p, arrival, export_burned, present_fire, start_h):
    """NOREENTRY2_RULE.md 1 and 6.1-6.3: C0 = export known-burned | (variant arrival or lo <= start, integer ms since
    t0, inclusive), computed from whatever --arrival is passed (NOREENTRY2_RULE.md erratum 1: a clamped dilated
    --arrival can add cells to C0 but adds nothing to B0, since those cells are already born at 0). Per member,
    B0 = C0 minus present fire minus cells already born at 0; B0 cells get birth 0 (with T = R = H in the child:
    active on [0, H)), replacing any later birth (6.2)."""
    a_ms, fin = ignitions.to_ms(arrival)
    c0 = np.asarray(export_burned, bool) | (fin & (a_ms <= ignitions.hour_ms(start_h)))
    times = p['times']
    if times.shape[1:] != c0.shape:
        raise SystemExit('NOREENTRY2_GRID: B0 is defined on the full export grid only')
    added = []
    for k in range(times.shape[0]):
        b0 = c0 & ~present_fire & (times[k] != 0.0)
        later = b0 & np.isfinite(times[k])                       # 6.2: a later /1 birth replaced by 0
        times[k][b0] = 0.0
        added.append({'export_burned_not_present': int((b0 & export_burned).sum()),
                      'variant_burned_out': int((b0 & ~export_burned).sum()),
                      'replaced_later_birth': int(later.sum()), 'b0_total': int(b0.sum())})
    m = p['meta']
    base = {'plan_sha256': m['plan_sha256'], 'ignition_times_sha256': m['ignition_times_sha256']}
    m['transform'] = 'no_reentry/2'
    m['ignition_times_sha256'] = ignitions.digest(times)
    m['no_reentry2'] = {'rule': 'NOREENTRY2_RULE.md', 'c0_cells': int(c0.sum()), 'added_at_0': added,
                        'base_plan': base,
                        'c0_definition': 'export known-burned | variant arrival (envelope: lo) <= start, integer ms since '
                                         't0 2025-03-22T02:24Z, inclusive; never from a dilated raster'}
    m.pop('plan_sha256')
    m['plan_sha256'] = hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()
    return added


def recorded_window(region: str, start: str) -> dict:
    md = json.loads((INPUTS / 'packets' / region / start / 'NATIVE_METADATA.json').read_text())
    return md['regional']['window_rows_cols_north_up']


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--region', required=True)
    ap.add_argument('--start', required=True, help='recorded input tag, e.g. 20250325T190000Z')
    ap.add_argument('--horizon-h', type=float, required=True)
    ap.add_argument('--arrival', type=Path, required=True)
    ap.add_argument('--arrival-variant', required=True)
    ap.add_argument('--arrival-source', default='{}', help='JSON provenance of the raster (doi, derivation)')
    ap.add_argument('--arrival-hi', type=Path, default=None, help='envelope: bracket-end raster (arrival = bracket start)')
    ap.add_argument('--sd', type=Path, default=None)
    ap.add_argument('--member-set', default='central', choices=sorted(ignitions.MEMBER_SETS))
    ap.add_argument('--quantum-s', type=float, default=ignitions.DEFAULT_QUANTUM_S)
    ap.add_argument('--domain', default='recorded_window', choices=['recorded_window', 'full_grid'])
    ap.add_argument('--graph', type=Path, default=None, help='required for full_grid (graph on the export grid)')
    ap.add_argument('--synthetic-export-dir', type=Path, default=None,
                    help='use a SYNTHETIC present-fire export (fdyn/synthetic_export.py) for a non-recorded start')
    ap.add_argument('--kriged-toa', type=Path, default=None, help='published TOA for the synthetic present fire')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--python', default=sys.executable)
    ap.add_argument('--no-reentry', action='store_true',
                    help='NOREENTRY_RULE.md: born cells closed to the horizon (scalar law T = R = H), own identity')
    ap.add_argument('--no-reentry2', action='store_true',
                    help='NOREENTRY2_RULE.md: as --no-reentry, plus cells burned out before the start closed on [0, H)')
    ap.add_argument('--pad-cells', type=int, default=0,
                    help='WIDENED_GRAPH_RULE.md §2.1: pad export and rasters by N cells (full_grid; graph on the padded grid)')
    ap.add_argument('--padded-export-dir', type=Path, default=None, help='fresh directory for the padded export (with --pad-cells)')
    ap.add_argument('--support-mask', type=Path, default=None,
                    help='F-9.3 SUPPORT_WIRING_RULE.md: npz with boolean "support" (north-up; export grid or packet grid)')
    ap.add_argument('--support-rule', default=None, help='supplied/1 (the only rule on this path)')
    ap.add_argument('--support-provenance', default=None, help='JSON provenance of the mask (required with a mask)')
    a = ap.parse_args(argv)
    if a.no_reentry and a.no_reentry2:
        raise SystemExit('NOREENTRY_TRANSFORM: --no-reentry and --no-reentry2 are exclusive')
    nr_any = a.no_reentry or a.no_reentry2
    if a.support_mask is not None and a.arrival_variant == 'envelope' and not nr_any:   # correction 1 (per-cell only)
        raise SystemExit('SUPPORT_ENVELOPE_UNSUPPORTED: masks apply to scalar-law packets only')
    arrival = read_raster(a.arrival)
    sd = read_raster(a.sd) if a.sd else None
    arrival_hi = read_raster(a.arrival_hi) if a.arrival_hi else None
    arrival_exact, arrival_hi_exact = read_exact(a.arrival), read_exact(a.arrival_hi)
    if a.pad_cells:                                       # WIDENED_GRAPH_RULE.md §2.1 (NaN = no arrival in padding)
        from fdyn import pad_export
        if a.domain != 'full_grid' or a.padded_export_dir is None or a.synthetic_export_dir is not None:
            raise SystemExit('PAD_ARGS: --pad-cells needs --domain full_grid and --padded-export-dir (recorded exports only)')
        arrival, sd, arrival_hi, arrival_exact, arrival_hi_exact = (
            pad_export.pad_raster(x, a.pad_cells) for x in (arrival, sd, arrival_hi, arrival_exact, arrival_hi_exact))
    elif a.padded_export_dir is not None:
        raise SystemExit('PAD_ARGS: --padded-export-dir needs --pad-cells')
    source = json.loads(a.arrival_source)
    source['file_sha256'] = sha(a.arrival)
    if a.arrival_variant == 'kriged_mean' and source['file_sha256'] != KRIGED_TOA_SHA256:
        raise SystemExit('KRIGED_MEAN_SHA_MISMATCH')
    start = dt.datetime.strptime(a.start, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
    start_h = (start - T0_UTC).total_seconds() / 3600.0
    if a.domain == 'recorded_window':
        win, graph = recorded_window(a.region, a.start), GRAPHS / a.region / 'graph.json'
        if a.graph is not None:
            raise SystemExit('--graph only with --domain full_grid')
    else:
        if a.graph is None:
            raise SystemExit('--domain full_grid needs --graph')
        win, graph = None, a.graph
    export_dir = INPUTS / 'exports' / EVENT
    if a.synthetic_export_dir is not None:
        if a.domain != 'full_grid':
            raise SystemExit('synthetic starts are built on the full grid only')
        if (export_dir / f'FORECAST_{a.start}.npz').exists():
            raise SystemExit('a recorded export exists for this start; use it, not a synthetic one')
        from fdyn import synthetic_export
        if a.kriged_toa is None or sha(a.kriged_toa) != KRIGED_TOA_SHA256:
            raise SystemExit('synthetic present fire needs --kriged-toa (the published TOA, as the recorded exports)')
        synthetic_export.write(a.kriged_toa, a.start, a.synthetic_export_dir)
        export_dir = a.synthetic_export_dir
    if a.pad_cells:
        export_dir = pad_export.write(export_dir, a.start, a.pad_cells, a.padded_export_dir)
    with np.load(export_dir / f'FORECAST_{a.start}.npz') as z:
        burned_at_start = z['source_burned_area_valid'] & (z['source_burned_area'] == 1)
        export_burned = burned_at_start.copy()                       # NOREENTRY2_RULE.md 6.1 (C0, part a)
        _iv = z['heat__initial_burning_valid'].astype(bool)
        present_fire = (_iv & (z['heat__initial_active_burning_probability'] == 1) & export_burned) | (export_burned & ~_iv)
        if a.arrival_variant == 'envelope_burnset':   # PACKET_CONSISTENCY_RULE.md A: only present fire is skipped
            iv = z['heat__initial_burning_valid'].astype(bool)
            cur = (iv & (z['heat__initial_active_burning_probability'] == 1) & burned_at_start) | (burned_at_start & ~iv)
            burned_at_start = cur
        burn_T = float(z['contract__cell_duration_s'])
    p = ignitions.plan(arrival, sd, arrival_variant=a.arrival_variant, arrival_source=source, start_h=start_h,
                       start_utc=start.isoformat(), horizon_s=a.horizon_h * 3600.0, quantum_s=a.quantum_s,
                       member_set=a.member_set, region=a.region, window=win,
                       burned_at_start=burned_at_start, burn_duration_s=burn_T,
                       arrival_hi_h=arrival_hi, arrival_exact=arrival_exact, arrival_hi_exact=arrival_hi_exact)
    if a.arrival_variant.startswith('envelope') != (a.arrival_hi is not None):
        raise SystemExit('--arrival-variant envelope* requires --arrival-hi (and only it)')
    if a.arrival_hi is not None and a.domain != 'full_grid':
        raise SystemExit('the envelope is built on the full grid only')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    plan_path = a.out.with_name(a.out.name + '.plan.npz')
    extra = {} if p['hi_rel'] is None else {'hi_rel': p['hi_rel']}
    if a.arrival_variant == 'envelope_burnset':          # ENVELOPE_BURNSET_RULE.md: static law on the burn set
        extra['burnset_mask'] = np.isfinite(arrival)
    if a.no_reentry:                                       # NOREENTRY_RULE.md (absent: plan bytes as v3.5)
        p['meta']['transform'] = 'no_reentry/1'
    if a.no_reentry2:                                      # NOREENTRY2_RULE.md: /1 plus B0 born at 0
        add_b0(p, arrival, export_burned, present_fire, start_h)
    np.savez_compressed(plan_path, times=p['times'], meta=json.dumps(p['meta']), **extra)
    cmd = [a.python, '-I', '-B', str(HERE / '_packet_child.py'), '--plan', str(plan_path), '--graph', str(graph),
           '--export-dir', str(export_dir), '--cutoff', start.strftime('%Y-%m-%dT%H:%M:%SZ'),
           '--region', a.region, '--event', EVENT, '--window-json', json.dumps(win), '--out', str(a.out)]
    if (a.support_mask is None) != (a.support_rule is None) or (a.support_mask is None) != (a.support_provenance is None):
        raise SystemExit('SUPPORT_ARGS: --support-mask, --support-rule and --support-provenance go together')
    if a.support_mask is not None:                       # F-9.3 SUPPORT_WIRING_RULE.md
        if a.arrival_variant == 'envelope' and not nr_any:   # SUPPORT_WIRING_RULE.md correction 1 (per-cell law)
            raise SystemExit('SUPPORT_ENVELOPE_UNSUPPORTED: masks apply to scalar-law packets only')
        if a.support_rule != 'supplied/1':
            raise SystemExit(f'SUPPORT_RULE_UNKNOWN {a.support_rule!r} (F-DYN path: supplied/1 only)')
        prov = json.loads(a.support_provenance)
        if not prov:
            raise SystemExit('SUPPORT_PROVENANCE_MISSING')
        with np.load(a.support_mask, allow_pickle=False) as z:
            mask = np.asarray(z['support'])
        if mask.dtype != bool:
            raise SystemExit(f'SUPPORT_SHAPE dtype {mask.dtype}')
        if win is not None and mask.shape == arrival.shape:          # full export grid -> window, as the plan
            mask = mask[win['r0']:win['r1'] + 1, win['c0']:win['c1'] + 1]
        if mask.shape != p['times'].shape[1:]:
            raise SystemExit(f'SUPPORT_SHAPE {mask.shape} != packet grid {p["times"].shape[1:]}')
        mask_path = a.out.with_name(a.out.name + '.support.npz')
        np.savez_compressed(mask_path, support=mask)
        cmd += ['--support-mask', str(mask_path), '--support-rule', a.support_rule,
                '--support-provenance', json.dumps(prov, sort_keys=True)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('FDYN_PACKET_BUILD_FAILED\n' + (r.stdout + r.stderr)[-3000:])
    print(r.stdout.strip())
    print(json.dumps({k: p['meta'][k] for k in ('arrival_variant', 'member_set', 'ignitions_in_domain',
                                                 'distinct_ignition_times_in_domain',
                                                 'kriging_sd_h_at_first_member_ignitions')}))


if __name__ == '__main__':
    main()
