"""Independent verifier script for AIR-EXTRACT D0 (ledger row 85a), run by the D0 author against his copies of the inputs
(the register CSV and the OSM 시군구 extract stay out of git). Own code only: CSV parse, Vincenty geodesic on WGS84
(not pyproj.Geod), ray-casting point-in-polygon (not shapely). Standard library only.

    python3 -I nora_d0_sites_check.py CSV SIGUNGU.geojson D0_AIR_ROW.json > OUT.json

Checks: register counts (usable / blank / invalid, distinct usable points, invalid well-formed outside Korea); per row
with a row time: nearest usable site (identity by coordinates) and its distance to 0.1 km, the count of distinct usable
points within 100 km, the place's 시군구; for every usable site within 100 km of a listed place: inside/outside the
시군구 named in its address, the outside total, and the nearest-site outside flags on the rows."""
import csv, hashlib, io, json, math, sys

CSV, GEO, D0 = sys.argv[1:4]
raw = open(CSV, 'rb').read()
res = {'csv_sha256': hashlib.sha256(raw).hexdigest(), 'geo_sha256': hashlib.sha256(open(GEO, 'rb').read()).hexdigest()}
rows = list(csv.DictReader(io.StringIO(raw.decode('cp949'))))
cnt = {'rows': len(rows), 'usable': 0, 'blank': 0, 'invalid': 0, 'invalid_wellformed_outside_korea': 0}
sites = []


def num(s):
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return 'bad'


for r in rows:
    v = [num(r[k]) for k in ('북쪽위도', '북위분', '북위초', '동경도', '동경분', '동경초')]
    if any(x is None for x in v):
        cnt['blank'] += 1; continue
    if any(x == 'bad' for x in v):
        cnt['invalid'] += 1; continue
    lat = v[0] + v[1] / 60.0 + v[2] / 3600.0; lon = v[3] + v[4] / 60.0 + v[5] / 3600.0
    wf = v[1] < 60 and v[2] < 60 and v[4] < 60 and v[5] < 60
    ins = 33 <= lat <= 39 and 124 <= lon <= 132
    if wf and ins:
        cnt['usable'] += 1
        a = r['이착륙장주소'].split()
        sites.append({'name': r['이착륙장명'], 'lat': lat, 'lon': lon, 'sgg': a[1] if len(a) > 1 else None})
    else:
        cnt['invalid'] += 1; cnt['invalid_wellformed_outside_korea'] += int(wf and not ins)
pts = {}
for s in sites:
    pts.setdefault((round(s['lat'], 7), round(s['lon'], 7)), []).append(s)
cnt['distinct_usable_points'] = len(pts)
res['register'] = cnt


def vincenty(lat1, lon1, lat2, lon2):
    a, f = 6378137.0, 1 / 298.257223563; b = a * (1 - f)
    L = math.radians(lon2 - lon1); U1 = math.atan((1 - f) * math.tan(math.radians(lat1))); U2 = math.atan((1 - f) * math.tan(math.radians(lat2)))
    sU1, cU1, sU2, cU2 = math.sin(U1), math.cos(U1), math.sin(U2), math.cos(U2); lam = L
    for _ in range(200):
        sl, cl = math.sin(lam), math.cos(lam)
        ss = math.hypot(cU2 * sl, cU1 * sU2 - sU1 * cU2 * cl)
        if ss == 0: return 0.0
        cs = sU1 * sU2 + cU1 * cU2 * cl; sig = math.atan2(ss, cs); sa = cU1 * cU2 * sl / ss; c2a = 1 - sa * sa
        c2m = cs - 2 * sU1 * sU2 / c2a if c2a else 0.0
        C = f / 16 * c2a * (4 + f * (4 - 3 * c2a)); lp = lam
        lam = L + (1 - C) * f * sa * (sig + C * ss * (c2m + C * cs * (-1 + 2 * c2m * c2m)))
        if abs(lam - lp) < 1e-12: break
    u2 = c2a * (a * a - b * b) / (b * b); A = 1 + u2 / 16384 * (4096 + u2 * (-768 + u2 * (320 - 175 * u2))); B = u2 / 1024 * (256 + u2 * (-128 + u2 * (74 - 47 * u2)))
    ds = B * ss * (c2m + B / 4 * (cs * (-1 + 2 * c2m * c2m) - B / 6 * c2m * (-3 + 4 * ss * ss) * (-3 + 4 * c2m * c2m)))
    return b * A * (sig - ds)


def rings(geom):
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    return polys


def in_ring(x, y, ring):
    c = False; n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]; x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: c = not c
    return c


def in_geom(x, y, geom):
    for poly in rings(geom):
        if in_ring(x, y, poly[0]) and not any(in_ring(x, y, h) for h in poly[1:]): return True
    return False


feats = [f for f in json.load(open(GEO))['features'] if f.get('geometry')]
norm = lambda s: (s or '').replace(' ', '')
def sgg_of(lon, lat):
    hits = [f['properties'].get('name') for f in feats if in_geom(lon, lat, f['geometry'])]
    return hits


d0 = json.load(open(D0)); mism = []; near_ids = set(); n_rows = 0
for tab, trows in d0['tables'].items():
    for r in trows:
        if not r.get('row_time'): continue
        n_rows += 1
        lon, lat = r['place_lonlat']
        dist = sorted((vincenty(lat, lon, p[0], p[1]) / 1000.0, p) for p in pts)
        best = dist[0]; within = sum(1 for d, _ in dist if d <= 100.0)
        ns = r['nearest_site']; got = (round(ns['lat'], 7), round(ns['lon'], 7))
        if got != best[1] and abs(vincenty(lat, lon, *got) / 1000.0 - best[0]) > 0.005 * best[0]:
            mism.append(('nearest', tab, r['origin'], r['start'], got, best[1], round(best[0], 3)))
        if abs(round(best[0], 1) - r['straight_line_distance_km']) > 0.1:
            mism.append(('distance', tab, r['origin'], r['start'], r['straight_line_distance_km'], round(best[0], 2)))
        if within != r['distinct_site_points_within_100km']:
            mism.append(('within100', tab, r['origin'], r['start'], r['distinct_site_points_within_100km'], within))
        h = sgg_of(lon, lat)
        if [norm(x) for x in h] != [norm(r['place_sigungu_osm'])]:
            mism.append(('place sgg', tab, r['origin'], h, r['place_sigungu_osm']))
        for d, p in dist:
            if d <= 100.0: near_ids.add(p)
out_n, out_pts = 0, set()
for p in near_ids:
    for s in pts[p]:
        h = [norm(x) for x in sgg_of(s['lon'], s['lat'])]
        if norm(s['sgg']) not in h:
            out_n += 1; out_pts.add(p)
for tab, trows in d0['tables'].items():
    for r in trows:
        if not r.get('row_time'): continue
        ns = r['nearest_site']; p = (round(ns['lat'], 7), round(ns['lon'], 7))
        if (p in out_pts) != bool(ns['outside_stated_sigungu']):
            mism.append(('outside flag', tab, r['origin'], r['start'], ns['name'], ns['outside_stated_sigungu'], p in out_pts))
res.update({'rows_checked': n_rows, 'usable_sites_within_100km_of_a_row': sum(len(pts[p]) for p in near_ids),
            'sites_outside_stated_sigungu': out_n, 'd0_reports_outside': d0.get('sites_outside_stated_sigungu'),
            'mismatches': len(mism), 'mismatch_detail': mism[:50]})
print(json.dumps(res, ensure_ascii=False, indent=1))
