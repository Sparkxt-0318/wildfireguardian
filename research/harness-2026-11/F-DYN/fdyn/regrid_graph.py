"""INTERIM F-DYN graph: re-index a recorded (window-clipped) road graph onto the full KFS_01 export grid.

Roads stay exactly as recorded: same nodes, edges, travel ticks, forbidden turns, waitable flags. Only the grid
metadata and each edge segment's cell index change (window cell -> full-grid cell, both row-major with row 0 at the
south edge, as the router indexes cells). With the hazard on the full grid (writer window=None) no burning cell is
omitted; roads beyond the recorded window are still absent (road-limited workload until the un-clipped graph exists).

    python3 research/harness-2026-11/F-DYN/fdyn/regrid_graph.py --region yeongdeok_2025 --out G.json
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from fdyn import build  # noqa: E402

FULL = {'x0': 1085250.0, 'y0': 1845375.0 - 79 * 375.0, 'resolution': 375.0, 'width': 237, 'height': 79}


def regrid(g: dict) -> dict:
    gw = g['grid']
    if gw['resolution'] != FULL['resolution']:
        raise ValueError('resolution')
    dc = (gw['x0'] - FULL['x0']) / FULL['resolution']
    dr = (gw['y0'] - FULL['y0']) / FULL['resolution']
    if dc != int(dc) or dr != int(dr) or dc < 0 or dr < 0 or dc + gw['width'] > FULL['width'] or \
            dr + gw['height'] > FULL['height']:
        raise ValueError(f'window not aligned inside the full grid: {dc} {dr}')
    dc, dr = int(dc), int(dr)
    out = copy.deepcopy(g)
    out['grid'] = dict(FULL)
    for e in out['edges']:
        for s in e['segments']:
            r, c = divmod(s['cell'], gw['width'])
            s['cell'] = (r + dr) * FULL['width'] + (c + dc)
    out['revision'] = g['revision'] + '+fdyn-fullgrid-interim'
    out['provenance'] = dict(g['provenance'])
    out['provenance']['fdyn_interim'] = (
        'INTERIM: recorded window-clipped roads re-indexed onto the full KFS_01 export grid (79x237); roads beyond the '
        'recorded window are absent; source graph revision %s' % g['revision'])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--region', required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    src = build.GRAPHS / a.region / 'graph.json'
    g = json.loads(src.read_text())
    out = regrid(g)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, separators=(',', ':')))
    print(json.dumps({'region': a.region, 'source_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
                      'out_sha256': hashlib.sha256(a.out.read_bytes()).hexdigest(), 'revision': out['revision'],
                      'nodes': len(out['nodes']), 'edges': len(out['edges'])}))


if __name__ == '__main__':
    main()
