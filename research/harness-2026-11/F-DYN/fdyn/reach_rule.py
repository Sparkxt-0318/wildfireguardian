"""Reach table for the F-DYN start rule (STARTS_RULE.md, rule commits 6042132 + 89d0222) and the 6 recorded starts,
on the full KFS_01 grid with the recorded roads (interim graph): every start, quiet ones included.

Burned state at the start comes from the kriged TOA (= the recorded export at recorded starts, tested). Columns:
road_cells_igniting (cells crossed by >= 1 routed edge that ignite within the horizon), places_entry_cell,
places_within_1km (entry node within 1 km of an igniting cell centre).

    python3 research/harness-2026-11/F-DYN/fdyn/reach_rule.py --instance INSTANCE.json --arrival TOA.tif \
        --arrival-variant kriged_mean --kriged-toa TOA.tif --out REACH.json
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
from fdyn import build, ignitions, synthetic_export  # noqa: E402

RECORDED = {'uiseong_andong_2025': ['20250323T010000Z', '20250324T090000Z', '20250325T170000Z'],
            'yeongdeok_2025': ['20250325T190000Z', '20250325T230000Z', '20250326T080000Z']}


def rule_starts():
    out = []
    for k in range(29):
        t = build.T0_UTC + dt.timedelta(hours=24 + 3 * k)
        out.append(t.replace(minute=0, second=0).strftime('%Y%m%dT%H%M%SZ'))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--instance', type=Path, required=True)
    ap.add_argument('--arrival', type=Path, required=True)
    ap.add_argument('--arrival-variant', required=True)
    ap.add_argument('--kriged-toa', type=Path, required=True)
    ap.add_argument('--arrival-hi', type=Path, default=None, help='envelope: bracket-end raster')
    ap.add_argument('--member-set', default='central')
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    arrival = build.read_raster(a.arrival)
    arrival_hi = build.read_raster(a.arrival_hi) if a.arrival_hi else None
    toa = build.read_raster(a.kriged_toa).astype(np.float64)
    origins = {}
    for i in json.loads(a.instance.read_text())['instances']:
        origins.setdefault(i['region'], {o['origin_id']: o for o in i['origins']})
    T = 3970.4642815249267            # recorded KFS_01 contract cell duration (all exports)
    full = {'x0': 1085250.0, 'y0': 1815750.0, 'res': 375.0, 'W': 237, 'H': 79}
    rows = []
    for region in ('uiseong_andong_2025', 'yeongdeok_2025'):
        g = json.loads((build.GRAPHS / region / 'graph.json').read_text())
        gw = g['grid']
        dc = int((gw['x0'] - full['x0']) / 375)
        dr = int((gw['y0'] - full['y0']) / 375)
        cells = set()
        for e in g['edges']:
            for s in e['segments']:
                r, c = divmod(s['cell'], gw['width'])
                cells.add((r + dr) * full['W'] + (c + dc))           # full grid, row 0 = south
        xy = {n['id']: (n['x'], n['y']) for n in g['nodes']}
        starts = [(t, 'rule') for t in rule_starts()] + [(t, 'recorded') for t in RECORDED[region]]
        for tag, kind in starts:
            start = dt.datetime.strptime(tag, '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
            h = (start - build.T0_UTC).total_seconds() / 3600
            pf = synthetic_export.present_fire_arrays(toa, h, T)
            burned = pf['source_burned_area_valid'] & (pf['source_burned_area'] == 1)
            present = pf['heat__initial_active_burning_probability'] > 0
            for H in (5, 8):
                if arrival_hi is None:
                    t = ignitions.schedule(arrival, h, H * 3600.0, 300.0, ignitions.MEMBER_SETS[a.member_set],
                                           burned, T)
                else:
                    t, _ = ignitions.envelope_schedule(arrival, arrival_hi, h, H * 3600.0, 300.0, burned, T)
                ign = np.isfinite(t).any(axis=0)[::-1, :]               # north-up -> row 0 = south
                flat = set(np.flatnonzero(ign.ravel()).tolist())
                rr, cc = np.nonzero(ign)
                fx, fy = full['x0'] + (cc + 0.5) * 375, full['y0'] + (rr + 0.5) * 375
                in_cell = within = 0
                for o in origins[region].values():
                    x, y = xy[o['entry_node']]
                    idx = int((y - full['y0']) // 375) * full['W'] + int((x - full['x0']) // 375)
                    in_cell += idx in flat
                    within += bool(fx.size) and float(np.min(np.hypot(fx - x, fy - y))) <= 1000.0
                rows.append({'region': region, 'start': tag, 'kind': kind, 'start_kst': (start + dt.timedelta(hours=9)).strftime('%m-%d %H:%M'),
                             'horizon_h': H, 'present_fire_cells_full_grid': int(present.sum()),
                             'ignitions_full_grid': int(len(flat)), 'road_cells': len(cells),
                             'road_cells_igniting': len(flat & cells), 'places': len(origins[region]),
                             'places_entry_cell': in_cell, 'places_within_1km': within})
    a.out.write_text(json.dumps({'arrival_variant': a.arrival_variant, 'member_set': a.member_set, 'rows': rows},
                                indent=1))
    for r in rows:
        print('{region:20s} {start} {kind:8s} KST {start_kst} {horizon_h}h present {present_fire_cells_full_grid:5d} '
              'ign {ignitions_full_grid:5d} road {road_cells_igniting:4d}/{road_cells} entry {places_entry_cell:2d} '
              '1km {places_within_1km:2d}/{places}'.format(**r))


if __name__ == '__main__':
    main()
