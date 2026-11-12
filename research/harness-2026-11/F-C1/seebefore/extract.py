"""Per-case extract for the see-before-leave analysis (stream F-C1).

Re-uses research/solve2027-impact (planner rules on the recorded 2025 cache; window classification on the
SHA-verified road graph and HAZARD packets). Adds each place's OSM point and road-entry-node coordinates (EPSG:5179)
and nothing else. Produces one row per (place, recorded input time) for villages and care facilities.

No new route checks; no change to routing, forecast or planner code.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
IMPACT = REPO / 'research' / 'solve2027-impact'
if str(IMPACT) not in sys.path:
    sys.path.insert(0, str(IMPACT))

from wfg_impact import analysis, sources  # noqa: E402

KEEP = ('scope', 'region', 'input_time', 'origin_id', 'name', 'name_en', 'category', 'origin_type', 'best_verdict',
        'latest_s', 'deadline_set_by', 'trip_min_s', 'entry_node', 'entry_distance_m')


def _lonlat_to_5179():
    from pyproj import Transformer
    return Transformer.from_crs(4326, 5179, always_xy=True)


def node_xy(region: str) -> dict:
    """Road-graph node coordinates (EPSG:5179) by node id."""
    g = json.loads(sources.graph_path(region).read_text())
    crs = str(g.get('crs', ''))
    nodes = g['nodes']
    out = {}
    for n in nodes if isinstance(nodes, list) else [dict(id=k, **v) for k, v in nodes.items()]:
        out[n['id']] = (float(n['x']), float(n['y']))
    if '5179' not in crs:
        raise ValueError(f'{region}: graph CRS {crs!r} is not EPSG:5179')
    return out


def build() -> list[dict]:
    out = analysis.run(with_graphs=True)
    tr = _lonlat_to_5179()
    places = {}
    for region in sources.REGIONS:
        for p in sources.load_places(region):
            places[(region, p['id'])] = p
    nodes = {region: node_xy(region) for region in sources.REGIONS}
    rows = []
    for r in out['records']:
        if r['origin_type'] not in ('village', 'care_facility'):
            continue
        p = places[(r['region'], r['origin_id'])]
        row = {k: r.get(k) for k in KEEP}
        row['place_x'], row['place_y'] = tr.transform(p['lon'], p['lat'])
        row['lon'], row['lat'] = p['lon'], p['lat']
        ex = nodes[r['region']].get(r['entry_node'])
        row['entry_x'], row['entry_y'] = ex if ex else (None, None)
        rows.append(row)
    return rows


if __name__ == '__main__':
    dest = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('cases.json')
    rows = build()
    dest.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(f'{len(rows)} cases, {len({(r["region"], r["origin_id"]) for r in rows})} places -> {dest}')
