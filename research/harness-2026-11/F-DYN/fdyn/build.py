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
    a = ap.parse_args(argv)
    arrival = read_raster(a.arrival)
    sd = read_raster(a.sd) if a.sd else None
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
    with np.load(export_dir / f'FORECAST_{a.start}.npz') as z:
        burned_at_start = z['source_burned_area_valid'] & (z['source_burned_area'] == 1)
        burn_T = float(z['contract__cell_duration_s'])
    p = ignitions.plan(arrival, sd, arrival_variant=a.arrival_variant, arrival_source=source, start_h=start_h,
                       start_utc=start.isoformat(), horizon_s=a.horizon_h * 3600.0, quantum_s=a.quantum_s,
                       member_set=a.member_set, region=a.region, window=win,
                       burned_at_start=burned_at_start, burn_duration_s=burn_T,
                       arrival_hi_h=read_raster(a.arrival_hi) if a.arrival_hi else None)
    if (a.arrival_variant == 'envelope') != (a.arrival_hi is not None):
        raise SystemExit('--arrival-variant envelope requires --arrival-hi (and only it)')
    if a.arrival_hi is not None and a.domain != 'full_grid':
        raise SystemExit('the envelope is built on the full grid only')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    plan_path = a.out.with_name(a.out.name + '.plan.npz')
    extra = {} if p['hi_rel'] is None else {'hi_rel': p['hi_rel']}
    np.savez_compressed(plan_path, times=p['times'], meta=json.dumps(p['meta']), **extra)
    cmd = [a.python, '-I', '-B', str(HERE / '_packet_child.py'), '--plan', str(plan_path), '--graph', str(graph),
           '--export-dir', str(export_dir), '--cutoff', start.strftime('%Y-%m-%dT%H:%M:%SZ'),
           '--region', a.region, '--event', EVENT, '--window-json', json.dumps(win), '--out', str(a.out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('FDYN_PACKET_BUILD_FAILED\n' + (r.stdout + r.stderr)[-3000:])
    print(r.stdout.strip())
    print(json.dumps({k: p['meta'][k] for k in ('arrival_variant', 'member_set', 'ignitions_in_domain',
                                                 'distinct_ignition_times_in_domain',
                                                 'kriging_sd_h_at_first_member_ignitions')}))


if __name__ == '__main__':
    main()
