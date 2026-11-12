"""Build F-DYN hazard packets: arrival-time field -> multi-hour 4-member packet for a recorded 2025 start.

    python3 research/harness-2026-11/F-DYN/fdyn/build.py --region yeongdeok_2025 --start 20250325T190000Z \
        --horizon-h 5 --toa PATH/KFS_01_pswt_ok_toa.tif --sd PATH/KFS_01_pswt_ok_std.tif --out OUT_DIR

Writes OUT_DIR/{HAZARD.json, NATIVE_METADATA.json, REPORT.json, constructed_arrays.npz, BUILD_SUMMARY.json} and
OUT_DIR.plan.npz. Large outputs: keep outside git.
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
TOA_SHA256 = 'fe81f945ddb9dd68f9de27b5865ca12d1a345934540934b723bd66b7d01fa953'
SD_SHA256 = '40305f9fecf5fffb77797ec0c8d1e22ad514ddf214dc654ba1188f23d3d77ecf'
EXPORT_AFFINE = (375.0, 0.0, 1085250.0, 0.0, -375.0, 1845375.0)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read_field(toa_path: Path, sd_path: Path):
    import rasterio
    if sha(toa_path) != TOA_SHA256 or sha(sd_path) != SD_SHA256:
        raise SystemExit('ARRIVAL_FIELD_SHA_MISMATCH')
    with rasterio.open(toa_path) as s:
        toa = s.read(1).astype(float)
        tags = s.tags()
        aff = tuple(float(v) for v in list(s.transform)[:6])
        if s.crs.to_epsg() != 5179:
            raise SystemExit('ARRIVAL_FIELD_CRS')
    with rasterio.open(sd_path) as s:
        sd = s.read(1).astype(float)
    # rasterio Affine order (a, b, c, d, e, f) = (375, 0, x0, 0, -375, y_top)
    if aff != EXPORT_AFFINE:
        raise SystemExit(f'ARRIVAL_FIELD_GRID {aff}')
    t0 = dt.datetime.fromisoformat(tags['t0_utc']).replace(tzinfo=dt.timezone.utc)
    return toa, sd, t0, tags


def window_of(region: str, start: str) -> dict:
    md = json.loads((INPUTS / 'packets' / region / start / 'NATIVE_METADATA.json').read_text())
    return md['regional']['window_rows_cols_north_up']


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--region', required=True)
    ap.add_argument('--start', required=True, help='recorded input tag, e.g. 20250325T190000Z')
    ap.add_argument('--horizon-h', type=float, required=True)
    ap.add_argument('--quantum-s', type=float, default=ignitions.DEFAULT_QUANTUM_S)
    ap.add_argument('--toa', type=Path, required=True)
    ap.add_argument('--sd', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--python', default=sys.executable)
    a = ap.parse_args(argv)
    toa, sd, t0, tags = read_field(a.toa, a.sd)
    start = dt.datetime.strptime(a.start, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
    start_h = (start - t0).total_seconds() / 3600.0
    win = window_of(a.region, a.start)
    source = {'doi': '10.5281/zenodo.21788344', 'citation': 'Choi, Seo & Cha 2026 (CC-BY-4.0)',
              'configuration': tags.get('configuration'), 't0_utc': t0.isoformat(),
              'toa_sha256': TOA_SHA256, 'sd_sha256': SD_SHA256}
    p = ignitions.plan(toa, sd, start_h=start_h, start_utc=start.isoformat(), horizon_s=a.horizon_h * 3600.0,
                       quantum_s=a.quantum_s, source=source, region=a.region, window=win)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    plan_path = a.out.with_name(a.out.name + '.plan.npz')
    np.savez_compressed(plan_path, times=p['times'], meta=json.dumps(p['meta']))
    cmd = [a.python, '-I', '-B', str(HERE / '_packet_child.py'), '--plan', str(plan_path),
           '--graph', str(GRAPHS / a.region / 'graph.json'), '--export-dir', str(INPUTS / 'exports' / EVENT),
           '--cutoff', start.strftime('%Y-%m-%dT%H:%M:%SZ'), '--region', a.region, '--event', EVENT,
           '--window-json', json.dumps(win), '--out', str(a.out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit('FDYN_PACKET_BUILD_FAILED\n' + (r.stdout + r.stderr)[-3000:])
    print(r.stdout.strip())
    print(json.dumps({k: p['meta'][k] for k in ('ignitions_in_window', 'distinct_ignition_times_in_window',
                                                 'kriging_sd_h_at_central_ignitions_in_window')}))


if __name__ == '__main__':
    main()
