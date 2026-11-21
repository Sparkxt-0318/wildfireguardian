"""Run a few real kit route checks (wfg_latest.api.route_and_check, arm RDA_CAND, kit v3, unchanged) on an F-DYN packet:
proves the packet is consumable by the evaluated routing path over a multi-hour horizon. Not a benchmark.

    python3 research/harness-2026-11/F-DYN/fdyn/smoke_check.py --instance INSTANCE.json --packet DIR \
        --region yeongdeok_2025 --start 20250325T230000Z --horizon-h 5 --n-origins 3 --offsets 0 3600 7200 --out DIR
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / 'integration' / 'src'))
sys.path.insert(0, str(REPO))

from api.requests_build import build_request  # noqa: E402
from wfg_latest.api import route_and_check  # noqa: E402

GRAPHS = REPO / 'data' / 'routing' / 'graphs'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--instance', type=Path, required=True)
    ap.add_argument('--packet', type=Path, required=True)
    ap.add_argument('--region', required=True)
    ap.add_argument('--start', required=True)
    ap.add_argument('--horizon-h', type=float, required=True)
    ap.add_argument('--n-origins', type=int, default=3)
    ap.add_argument('--offsets', type=int, nargs='+', default=[0, 3600])
    ap.add_argument('--budget-s', type=float, default=30.0)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    inst = next(i for i in json.loads(a.instance.read_text())['instances']
                if i['region'] == a.region and i['start_tag'] == a.start and i['horizon_s'] == int(a.horizon_h * 3600))
    hz = json.loads((a.packet / 'HAZARD.json').read_text())
    graph_path = GRAPHS / a.region / 'graph.json'
    g = json.loads(graph_path.read_text())
    xy = {n['id']: (n['x'], n['y']) for n in g['nodes']}
    # origins nearest to any member-0 ignition inside the window (most likely to meet the moving fire)
    arr = np.load(a.packet / 'constructed_arrays.npz')['ignition_time_s'][0]
    gr = hz['grid']
    rr, cc = np.nonzero(np.isfinite(arr))
    # constructed arrays are native north-up rows: row 0 = north edge
    fx = gr['x0'] + (cc + 0.5) * gr['resolution']
    fy = gr['y0'] + (gr['height'] - rr - 0.5) * gr['resolution']

    def dist(o):
        x, y = xy[o['entry_node']]
        return float(np.min(np.hypot(fx - x, fy - y))) if fx.size else float('inf')
    origins = sorted(inst['origins'], key=dist)[: a.n_origins]
    ids = [m['id'] for m in hz['members']]
    rows = []
    a.out.mkdir(parents=True, exist_ok=True)
    for o in origins:
        d = o['destinations'][0]
        for off in a.offsets:
            req = build_request(start_node=o['entry_node'], dest_node=d['node'], depart_offset_s=off, dwell_s=d['dwell_s'],
                                window=inst['destination_window_s'], limits={'peak_kw_m2': 10, 'dose_kj_m2': 100,
                                                                             'incurred_dose_kj_m2': 0},
                                scenario_ids=ids, horizon_s=hz['valid_until'], valid_from=hz['valid_from'],
                                hazard_version=hz['version'], as_of_iso=hz['issued_at'])
            tag = f"{o['origin_id'].replace('/', '_').replace(':', '_')}_{off}"
            rp = a.out / f'REQ_{tag}.json'
            rp.write_text(json.dumps(req))
            r = route_and_check(kit_root=REPO / 'integration' / 'kit', packet_dir=a.packet, graph=graph_path,
                                request=rp, out_dir=a.out / f'RUN_{tag}', budget_s=a.budget_s)
            row = {'origin_id': o['origin_id'], 'dist_to_fire_m': round(dist(o)), 'depart_s': off,
                   'dest': d['destination_id'], **{k: r[k] for k in ('authoritative_status', 'successful_journey',
                                                                     'unresolved_reason', 'arrival_s', 'wall_s',
                                                                     'on_time', 'independent')}}
            rows.append(row)
            print(json.dumps(row, default=str), flush=True)
    (a.out / 'SMOKE.json').write_text(json.dumps(rows, indent=1, default=str))


if __name__ == '__main__':
    main()
