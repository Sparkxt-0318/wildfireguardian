#!/usr/bin/env python3
"""Close-up map detail for each region: OpenStreetMap building footprints and roads at full detail (zoom 15).

usage: python3 tools/osm_detail.py [region ...]      (default: every region in site/regions/index.js)

Reads the same Protomaps daily build the planner's offline basemap was cut from (planner/public/basemap/SOURCES.json),
with HTTP Range requests, and writes site/regions/<id>.detail.js:
  WFG_DETAIL[id] = { o: [W, S], b: [[h, x0, y0, x1, y1, ...], ...], r: [[class, x0, y0, ...], ...] }
x/y are 1e-5 degree steps from the region's south-west corner; h is the building height in metres from OSM (0 when
OSM has none). Road classes: 0 motorway/trunk, 1 primary, 2 secondary, 3 tertiary, 4 minor, 5 track/service, 6 path.
OSM data © OpenStreetMap contributors (ODbL). Needs: pip install pmtiles mapbox-vector-tile requests
"""
import gzip, json, math, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import mapbox_vector_tile
import requests
from pmtiles.reader import Reader

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / 'site'
Z = 15
ROAD = {'highway': 0, 'motorway': 0, 'trunk': 0, 'primary': 1, 'secondary': 2, 'tertiary': 3,
        'residential': 4, 'unclassified': 4, 'living_street': 4, 'service': 5, 'track': 5, 'path': 6, 'footway': 6, 'cycleway': 6, 'steps': 6}


def road_class(p):
    k, d = p.get('kind', ''), p.get('kind_detail', '')
    if k == 'highway': return 0
    if d in ROAD: return ROAD[d]
    return {'major_road': 2, 'minor_road': 4, 'path': 6}.get(k)


def main():
    src = json.loads((ROOT.parent / 'public/basemap/SOURCES.json').read_text())['tiles']['source_url']
    reader = Reader(lambda off, ln: requests.get(src, headers={'Range': f'bytes={off}-{off + ln - 1}'}, timeout=60).content)
    index = (SITE / 'regions/index.js').read_text()
    regions = json.loads(index[index.index('=') + 1:].strip().rstrip(';'))
    want = sys.argv[1:]
    for reg in regions:
        if want and reg['id'] not in want: continue
        W, S, E, N = reg['bbox']; n = 2 ** Z
        tx = lambda lon: int((lon + 180) / 360 * n)
        ty = lambda lat: int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
        q = lambda lon, lat: (round((lon - W) * 1e5), round((lat - S) * 1e5))
        inside = lambda lon, lat: W - .002 <= lon <= E + .002 and S - .002 <= lat <= N + .002
        bld, rds, seen = [], [], set()
        xy = [(x, y) for x in range(tx(W), tx(E) + 1) for y in range(ty(N), ty(S) + 1)]
        with ThreadPoolExecutor(16) as ex:     # tiles fetched 16 at a time, decoded in order
            tiles = list(ex.map(lambda p: reader.get(Z, *p), xy))
        for (x, y), t in zip(xy, tiles):
                if not t: continue
                d = mapbox_vector_tile.decode(gzip.decompress(t), default_options={'y_coord_down': True})
                def ll(px, py, ext):     # tile pixel -> lon/lat
                    lon = (x + px / ext) / n * 360 - 180
                    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + py / ext) / n))))
                    return lon, lat
                for f in d.get('buildings', {}).get('features', []):
                    ext = d['buildings']['extent']; g = f['geometry']
                    polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates'] if g['type'] == 'MultiPolygon' else []
                    for poly in polys:
                        ring = [ll(px, py, ext) for px, py in poly[0]]
                        if len(ring) < 4 or not inside(*ring[0]): continue
                        flat = [v for p in ring[:-1] for v in q(*p)]
                        key = tuple(flat[:4])
                        if key in seen: continue
                        seen.add(key); bld.append([round(float(f['properties'].get('height') or 0), 1)] + flat)
                for f in d.get('roads', {}).get('features', []):
                    c = road_class(f['properties'])
                    if c is None: continue
                    ext = d['roads']['extent']; g = f['geometry']
                    lines = [g['coordinates']] if g['type'] == 'LineString' else g['coordinates'] if g['type'] == 'MultiLineString' else []
                    for line in lines:
                        pts = [ll(px, py, ext) for px, py in line]
                        if len(pts) < 2 or not any(inside(*p) for p in pts): continue
                        rds.append([c] + [v for p in pts for v in q(*p)])
        out = SITE / 'regions' / f"{reg['id']}.detail.js"
        out.write_text(f"(window.WFG_DETAIL=window.WFG_DETAIL||{{}})[{json.dumps(reg['id'])}]=" + json.dumps({'o': [W, S], 'b': bld, 'r': rds}, separators=(',', ':')) + ';\n')
        print(f"{reg['id']}: {len(bld)} buildings, {len(rds)} road pieces, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == '__main__':
    main()
