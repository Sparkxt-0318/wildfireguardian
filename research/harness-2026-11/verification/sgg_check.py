#!/usr/bin/env python3
"""Independent check of the 시군구 labels (Hannah, verifier). Written independently of label_sigungu.py.

Run UNMODIFIED in the container that holds the owner's archive:
    python3 -I sgg_check.py --archive /path/to/BND_SIGUNGU_PG.zip --places places_input.json > sgg_check_out.json

Reads the zip members in memory (no extraction, runs nothing from the archive). Needs pyshp, shapely>=2, pyproj.
Output (JSON, stdout): archive and member sha256, CRS (.prj text sha256 and pyproj EPSG guess), field names,
feature count, BASE_DATE values, the sanity facts, and for every place: the polygons containing the point
and the entry node, and the distance from the point to the containing polygon's boundary (m).
It prints no geometry and no link.
"""
import argparse, hashlib, io, json, sys, zipfile

import shapefile                      # pyshp
from shapely.geometry import shape, Point
from shapely.strtree import STRtree
from pyproj import CRS, Transformer


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--archive', required=True)
    ap.add_argument('--places', required=True)
    a = ap.parse_args()
    raw = open(a.archive, 'rb').read()
    out = {'script': 'sgg_check.py (Hannah)', 'archive_bytes': len(raw), 'archive_sha256': sha(raw)}
    z = zipfile.ZipFile(io.BytesIO(raw))
    mem = {}
    for n in z.namelist():
        base = n.rsplit('/', 1)[-1]
        if base.startswith('BND_SIGUNGU_PG.'):
            mem[base.split('.', 1)[1].lower()] = z.read(n)
    out['members'] = {k: {'bytes': len(v), 'sha256': sha(v)} for k, v in sorted(mem.items())}
    enc = mem.get('cpg', b'cp949').decode('ascii', 'replace').strip() or 'cp949'
    prj = mem['prj'].decode('ascii', 'replace')
    crs = CRS.from_wkt(prj)
    out['crs'] = {'prj_sha256': sha(mem['prj']), 'name': crs.name, 'epsg_guess': crs.to_epsg(min_confidence=20), 'cpg': enc}
    r = shapefile.Reader(shp=io.BytesIO(mem['shp']), shx=io.BytesIO(mem['shx']), dbf=io.BytesIO(mem['dbf']), encoding=enc)
    fields = [f[0] for f in r.fields[1:]]
    out['fields'] = fields
    cd = next(f for f in fields if f.upper().endswith('_CD'))
    nm = next(f for f in fields if f.upper().endswith('_NM'))
    bd = next((f for f in fields if 'DATE' in f.upper()), None)
    geoms, attrs = [], []
    for sr in r.iterShapeRecords():
        g = shape(sr.shape.__geo_interface__)
        if not g.is_valid:
            g = g.buffer(0)
        geoms.append(g)
        attrs.append({'cd': str(sr.record[cd]), 'nm': str(sr.record[nm]), 'base_date': str(sr.record[bd]) if bd else None})
    out['feature_count'] = len(geoms)
    out['base_dates'] = sorted({x['base_date'] for x in attrs if x['base_date']})
    wanted = ['의성군', '안동시', '영덕군', '청송군', '영양군', '군위군']
    out['sanity'] = {w: sorted({x['cd'] for x in attrs if x['nm'] == w}) for w in wanted}
    out['sanity_note'] = 'SGIS province prefix of each code: 37 = 경상북도, 22 = 대구광역시 (expected: 5 counties 37xxx; 군위군 22xxx)'
    tree = STRtree(geoms)
    tr = Transformer.from_crs('EPSG:4326', crs, always_xy=True)

    def containing(lon, lat):
        x, y = tr.transform(lon, lat)
        p = Point(x, y)
        idx = [int(i) for i in tree.query(p, predicate='intersects')]
        return p, idx

    places = json.load(open(a.places, encoding='utf-8'))
    out['places_input_sha256'] = sha(open(a.places, 'rb').read())
    res = {}
    for pl in places['places']:
        p, idx = containing(pl['point']['lon'], pl['point']['lat'])
        e = pl.get('entry') or {}
        _, eidx = containing(e['lon'], e['lat']) if 'lon' in e else (None, [])
        res[pl['id']] = {
            'region': pl.get('region'),
            'point_in': [attrs[i]['nm'] + '|' + attrs[i]['cd'] for i in idx],
            'entry_in': [attrs[i]['nm'] + '|' + attrs[i]['cd'] for i in eidx],
            'boundary_m': round(min(geoms[i].boundary.distance(p) for i in idx), 1) if idx else None,
        }
    out['places'] = res
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1, sort_keys=True)
    print()


if __name__ == '__main__':
    main()
