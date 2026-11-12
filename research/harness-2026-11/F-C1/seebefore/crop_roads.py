"""Burning cells dropped by the routing-packet crop vs the routed road network (F-C1 side finding).

For each recorded 2025 input: present-fire cells of the full KFS_01 export grid that lie outside the HAZARD packet
domain ("cropped"), how many contain a routed road (graph edges densified every 10 m, point inside the 375 m square),
distance bands to the nearest road, graph nodes outside the packet domain, and the omitted-source flux bounds the
packet builder itself recorded (BUILD_SUMMARY.json "omitted").

    python3 research/harness-2026-11/F-C1/seebefore/crop_roads.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seebefore import fire  # noqa: E402

GRAPHS = fire.REPO / 'data' / 'routing' / 'graphs'


def road_points(region):
    g = json.loads((GRAPHS / region / 'graph.json').read_text())
    nx = np.array([[n['x'], n['y']] for n in g['nodes']])
    idx = {n['id']: i for i, n in enumerate(g['nodes'])}
    ku = next(k for k in ('u', 'from', 'source', 'tail') if k in g['edges'][0])
    kv = next(k for k in ('v', 'to', 'target', 'head') if k in g['edges'][0])
    pts = [nx]
    for e in g['edges']:
        a, b = nx[idx[e[ku]]], nx[idx[e[kv]]]
        k = max(int(np.hypot(*(b - a)) // 10), 1)
        f = np.arange(1, k) / k
        if len(f):
            pts.append(a + f[:, None] * (b - a))
    return nx, np.vstack(pts)


def main():
    for region in ('uiseong_andong_2025', 'yeongdeok_2025'):
        nodes, pts = road_points(region)
        tree = cKDTree(pts)
        for t in sorted(p.name for p in (fire.INPUTS / 'packets' / region).iterdir()):
            hz = json.loads((fire.packet_dir(region, t) / 'HAZARD.json').read_text())
            g = hz['grid']
            x0, y0 = g['x0'], g['y0']
            x1, y1 = x0 + g['width'] * g['resolution'], y0 + g['height'] * g['resolution']
            out_nodes = int(((nodes[:, 0] < x0) | (nodes[:, 0] > x1) | (nodes[:, 1] < y0) | (nodes[:, 1] > y1)).sum())
            pres, _, _ = fire.present_fire(t)
            inside = (pres[:, 0] > x0) & (pres[:, 0] < x1) & (pres[:, 1] > y0) & (pres[:, 1] < y1)
            crop = pres[~inside]
            hit = 0
            for c in crop:
                if any(abs(pts[j, 0] - c[0]) <= 187.5 and abs(pts[j, 1] - c[1]) <= 187.5
                       for j in tree.query_ball_point(c, 266.0)):
                    hit += 1
            d = tree.query(crop)[0] if len(crop) else np.array([])
            om = json.loads((fire.packet_dir(region, t) / 'BUILD_SUMMARY.json').read_text()).get('omitted') or {}
            mem = om.get('members') or []
            print(f'{region}/{t}: present {len(pres)}, cropped {len(crop)}, cropped cells containing a routed road '
                  f'{hit}, nearest road <=1 km {int((d <= 1000).sum())}, <=3 km {int((d <= 3000).sum())}; graph nodes '
                  f'outside packet {out_nodes}/{len(nodes)}; packet-recorded omitted flux peak bound '
                  f'{max((m["reported_peak_bound_kW_m2"] for m in mem), default=0):.3f} kW/m2, centre-model max '
                  f'{max((m["centre_model_max_omitted_flux_kW_m2"] for m in mem), default=0):.4f} kW/m2')


if __name__ == '__main__':
    main()
