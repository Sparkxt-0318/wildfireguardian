"""Per start/horizon/variant: how much of the routed network and how many places the moving fire reaches (Iris's
workload acceptance; the share of fire-set deadlines needs a deadline solver and comes from Richard's field).

  road_cells_igniting   375 m cells crossed by >= 1 routed edge (edge segments) that ignite within the horizon
  places_entry_cell     places whose road-entry node lies in a cell that ignites within the horizon
  places_within_1km     places whose entry node is within 1 km of a cell centre igniting within the horizon

    python3 research/harness-2026-11/F-DYN/fdyn/reach.py --instance INSTANCE.json --arrival TOA.tif \
        --arrival-variant kriged_mean [--member-set central]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from fdyn import build, ignitions  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--instance', type=Path, required=True)
    ap.add_argument('--arrival', type=Path, required=True)
    ap.add_argument('--arrival-variant', required=True)
    ap.add_argument('--member-set', default='central')
    ap.add_argument('--quantum-s', type=float, default=ignitions.DEFAULT_QUANTUM_S)
    a = ap.parse_args()
    arrival = build.read_raster(a.arrival)
    inst = json.loads(a.instance.read_text())['instances']
    graphs = {}
    rows = []
    for i in inst:
        region, tag, H = i['region'], i['start_tag'], i['horizon_s']
        if region not in graphs:
            g = json.loads((build.GRAPHS / region / 'graph.json').read_text())
            gr = g['grid']
            cells = {s['cell'] for e in g['edges'] for s in e['segments']}     # flat index, row 0 = south
            xy = {n['id']: (n['x'], n['y']) for n in g['nodes']}
            graphs[region] = (gr, cells, xy)
        gr, cells, xy = graphs[region]
        win = build.recorded_window(region, tag)
        with np.load(build.INPUTS / 'exports' / build.EVENT / f'FORECAST_{tag}.npz') as z:
            burned = z['source_burned_area_valid'] & (z['source_burned_area'] == 1)
            T = float(z['contract__cell_duration_s'])
        start = dt.datetime.strptime(tag, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
        h = (start - build.T0_UTC).total_seconds() / 3600
        t = ignitions.schedule(arrival, h, H, a.quantum_s, ignitions.MEMBER_SETS[a.member_set], burned, T)
        ign = np.isfinite(t).any(axis=0)[win['r0']:win['r1'] + 1, win['c0']:win['c1'] + 1]   # north-up window rows
        ign_s = ign[::-1, :]                                                                   # row 0 = south
        flat = set(np.flatnonzero(ign_s.ravel()).tolist())
        road_ign = len(flat & cells)
        rr, cc = np.nonzero(ign_s)
        fx = gr['x0'] + (cc + 0.5) * gr['resolution']
        fy = gr['y0'] + (rr + 0.5) * gr['resolution']
        in_cell = within = 0
        for o in i['origins']:
            x, y = xy[o['entry_node']]
            c = int((x - gr['x0']) // gr['resolution'])
            r = int((y - gr['y0']) // gr['resolution'])
            in_cell += (r * gr['width'] + c) in flat
            within += bool(fx.size) and float(np.min(np.hypot(fx - x, fy - y))) <= 1000.0
        rows.append({'region': region, 'start': tag, 'horizon_h': H / 3600, 'road_cells': len(cells),
                     'road_cells_igniting': road_ign, 'places': len(i['origins']), 'places_entry_cell': in_cell,
                     'places_within_1km': within})
        print(json.dumps(rows[-1]))


if __name__ == '__main__':
    main()
