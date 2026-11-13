"""D0_RULE amendment 1 (P-b cross-check): place → 시군구 from OSM 2025-01-01 polygons vs the merged jurisdiction
labels (W-KIT JURISDICTION/labels.json, V-World BND_SIGUNGU_PG 2025-06-30), for every place on the early-action main
list. Disagreements are reported, never resolved.

    python -I check_place_sigungu.py --list EARLY_ACTION_LIST.json --osm sigungu_osm_20250101.geojson \
        --labels labels.json --places-dir planner/public/data/regions --out PLACE_SIGUNGU_CHECK.json
"""
import argparse
import hashlib
import json
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.strtree import STRtree


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def norm(n):
    return (n or '').strip()


def main():
    ap = argparse.ArgumentParser()
    for k in ('--list', '--osm', '--labels', '--places-dir', '--out'):
        ap.add_argument(k, type=Path, required=True)
    a = ap.parse_args()
    ea = json.loads(a.list.read_text())
    osm = json.loads(a.osm.read_text())
    lab = json.loads(a.labels.read_text())['labels']
    polys = [shape(f['geometry']) for f in osm['features']]
    names = [f['properties']['name'] for f in osm['features']]
    tree = STRtree(polys)
    pts = {}
    for reg in {u['region'] for u in ea['main_list']}:
        for f in json.loads((a.places_dir / reg / 'places.geojson').read_text())['features']:
            pts[(reg, f['properties']['id'])] = f['geometry']['coordinates']
    rows, seen = [], set()
    for u in ea['main_list']:
        key = (u['region'], u['origin'])
        if key in seen:
            continue
        seen.add(key)
        xy = pts.get(key)
        if xy is None:
            rows.append({'region': key[0], 'origin': key[1], 'osm': None, 'labels': None, 'status': 'place point not found'})
            continue
        p = Point(xy)
        hits = [names[i] for i in tree.query(p) if polys[i].covers(p)]
        lb = lab.get(key[1])
        lk = lb.get('ko') if lb else None
        osm_name = hits[0] if len(hits) == 1 else (hits or None)
        status = ('agree' if isinstance(osm_name, str) and lk and norm(osm_name) == norm(lk) else
                  'no label in labels.json' if lk is None else
                  'OSM polygon count != 1' if not isinstance(osm_name, str) else 'DISAGREE')
        rows.append({'region': key[0], 'origin': key[1], 'name': u['name'], 'lonlat': xy, 'osm': osm_name,
                     'labels': lk, 'labels_status': lb.get('status') if lb else None, 'status': status})
    from collections import Counter
    out = {'rule': 'D0_RULE.md amendment 1, P-b cross-check',
           'osm_label': osm.get('label'), 'osm_sha256': sha(a.osm), 'labels_sha256': sha(a.labels),
           'list_sha256': sha(a.list), 'places': len(rows), 'status_counts': dict(Counter(r['status'] for r in rows)),
           'rows': rows}
    a.out.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(json.dumps({k: out[k] for k in ('places', 'status_counts')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
