#!/usr/bin/env python3
"""OPTIONAL: add 임시주거시설 (temporary housing facilities) from 행정안전부_이재민 임시주거시설 정보 조회 서비스
(data.go.kr dataset 15139148) as extra candidate destinations.

OSM shelters stay the primary destinations. This importer is used only when the service response includes
coordinates for each facility; records without coordinates are never geocoded or guessed. Imported points
are labelled 임시주거시설 (category "temporary_housing"), never 대피소, and keep the record's own identifiers
as their source tag.

Input, one of:
  --file PATH        a response you downloaded from the service (JSON or XML; CSV also accepted)
  --url URL          the request URL from your data.go.kr 활용신청 page WITHOUT the key; the key is read from
                     DATA_GO_KR_SERVICE_KEY in planner/.env (never committed) and appended as serviceKey

Coordinates: WGS84 longitude/latitude fields are detected by name (lon/lng/longitude/lot/LO/경도/X... and
lat/latitude/la/LA/위도/Y...). If the values are not WGS84 degrees, pass --crs EPSG:xxxx (e.g. 5186) and they
are transformed with pyproj. Without usable coordinates the tool stops and writes nothing.

Output: planner/public/data/regions/<region>/temporary_housing.geojson for every region whose graph bbox
contains facilities, with the same entry-point (진입 지점) snapping as the OSM places, and a report.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import planner_common as pc  # noqa: E402
from extract_places import API_SNAP_LIMIT_M, ENTRY_MAX_M, PUBLIC_REGIONS, snap_points  # noqa: E402

DATASET = '행정안전부_이재민 임시주거시설 정보 조회 서비스 (data.go.kr 15139148)'
LON_KEYS = ['lon', 'lng', 'longitude', 'lot', 'lo', 'x', 'xcord', 'xcrd', 'x_crdnt', '경도', 'gpslon', 'gps_lon']
LAT_KEYS = ['lat', 'latitude', 'la', 'y', 'ycord', 'ycrd', 'y_crdnt', '위도', 'gpslat', 'gps_lat']
NAME_KEYS = ['fcltynm', 'fclty_nm', 'facility_name', 'name', 'nm', '시설명', 'acmdfcltynm', 'vt_acmdfclty_nm']
ID_KEYS = ['fcltyid', 'fclty_id', 'mngsn', 'mng_sn', 'id', 'sn', '관리번호', 'acmdfcltysn', 'vt_acmdfclty_sn']
ADDR_KEYS = ['rnadres', 'rn_adres', 'dtladres', 'address', 'addr', '주소', '도로명주소']


def norm(k: str) -> str:
    return re.sub(r'[^0-9a-z가-힣_]', '', k.lower())


def pick(rec: dict, keys: list[str]):
    m = {norm(k): v for k, v in rec.items()}
    for k in keys:
        v = m.get(norm(k))
        if v not in (None, ''):
            return v
    return None


def records_from_bytes(raw: bytes) -> list[dict]:
    text = raw.decode('utf-8-sig', 'replace').strip()
    if text.startswith('{') or text.startswith('['):
        doc = json.loads(text)
        found: list[dict] = []

        def walk(o):
            if isinstance(o, list):
                if o and all(isinstance(x, dict) for x in o) and any(len(x) > 3 for x in o):
                    found.extend(o)
                    return
                for x in o:
                    walk(x)
            elif isinstance(o, dict):
                for v in o.values():
                    walk(v)
        walk(doc)
        return found
    if text.startswith('<'):
        root = ET.fromstring(text)
        rows = []
        for item in root.iter():
            kids = list(item)
            if kids and all(len(list(k)) == 0 for k in kids) and len(kids) > 3:
                rows.append({k.tag: (k.text or '').strip() for k in kids})
        return rows
    return list(csv.DictReader(io.StringIO(text)))


def fetch(url: str) -> bytes:
    key = os.environ.get('DATA_GO_KR_SERVICE_KEY')
    env = Path(__file__).resolve().parents[1] / '.env'
    if not key and env.is_file():
        for line in env.read_text(encoding='utf-8').splitlines():
            if line.startswith('DATA_GO_KR_SERVICE_KEY='):
                key = line.split('=', 1)[1].strip()
    if not key:
        raise SystemExit('Set DATA_GO_KR_SERVICE_KEY in planner/.env (never committed) or the environment.')
    sep = '&' if '?' in url else '?'
    full = url + sep + 'serviceKey=' + urllib.parse.quote(key, safe='')
    with urllib.request.urlopen(full, timeout=60) as r:
        return r.read()


def to_float(v):
    try:
        f = float(str(v).replace(',', ''))
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--file', type=Path)
    src.add_argument('--url')
    ap.add_argument('--crs', default=None, help='source CRS when coordinates are not WGS84 degrees, e.g. EPSG:5186')
    ap.add_argument('--regions', nargs='*', default=pc.REGION_IDS)
    a = ap.parse_args(argv)

    raw = a.file.read_bytes() if a.file else fetch(a.url)
    recs = records_from_bytes(raw)
    if not recs:
        raise SystemExit('No records found in the response; nothing imported.')
    pts, missing = [], 0
    transformer = None
    if a.crs:
        from pyproj import Transformer
        transformer = Transformer.from_crs(a.crs, 'EPSG:4326', always_xy=True)
    for r in recs:
        x, y = to_float(pick(r, LON_KEYS)), to_float(pick(r, LAT_KEYS))
        if x is None or y is None:
            missing += 1
            continue
        if transformer is not None:
            x, y = transformer.transform(x, y)
        elif not (120 < x < 135 and 30 < y < 40):
            raise SystemExit('Coordinates are not WGS84 degrees (e.g. %r, %r). Re-run with --crs EPSG:xxxx.' % (x, y))
        pts.append((x, y, r))
    if not pts:
        raise SystemExit('The response has no coordinates (%d records): 임시주거시설 are NOT imported, as agreed.' % len(recs))

    report = {'dataset': DATASET, 'records': len(recs), 'with_coordinates': len(pts),
              'without_coordinates_skipped': missing, 'regions': {}}
    for region in a.regions:
        g = pc.load_graph(region)
        x0, y0, x1, y1 = g.grid_rect()
        inside = []
        for lon, lat, r in pts:
            X, Y = pc.to_5179(lon, lat)
            if x0 <= X <= x1 and y0 <= Y <= y1:
                inside.append((lon, lat, X, Y, r))
        out = PUBLIC_REGIONS / region / 'temporary_housing.geojson'
        if not inside:
            if out.exists():
                out.unlink()
            report['regions'][region] = 0
            continue
        snaps = snap_points(g, [p[2] for p in inside], [p[3] for p in inside])
        feats = []
        for (lon, lat, _, _, r), (node, dist) in zip(inside, snaps):
            i = g.index[node]
            elon, elat = pc.to_wgs84(g.x[i], g.y[i])
            rid = pick(r, ID_KEYS)
            name = pick(r, NAME_KEYS)
            feats.append({'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [round(lon, 7), round(lat, 7)]},
                          'properties': {
                              'id': f'mois-tmp-housing:{rid}' if rid else f'mois-tmp-housing:{round(lon, 6)},{round(lat, 6)}',
                              'role': 'destination', 'category': 'temporary_housing', 'label_ko': '임시주거시설',
                              'name': name, 'name_en': None, 'source': DATASET,
                              'source_tag': f'15139148 {rid or "(no id)"}', 'address': pick(r, ADDR_KEYS),
                              'osm': None, 'record': r,
                              'snap': {'node': node, 'distance_m': round(dist, 1)},
                              'entry': {'node': node, 'lon': round(float(elon), 7), 'lat': round(float(elat), 7),
                                        'distance_m': round(dist, 1), 'within_api_lonlat_snap': dist <= API_SNAP_LIMIT_M},
                              'checkable': dist <= ENTRY_MAX_M, 'vulnerable': False,
                              'scenario_set_id': None, 'input_time': None, 'case_id': None, 'recorded': None}})
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({'type': 'FeatureCollection', 'region_id': region, 'source': DATASET,
                                   'notes': ['Optional extra destinations, labelled 임시주거시설 (not 대피소).'],
                                   'features': feats}, ensure_ascii=False), encoding='utf-8')
        report['regions'][region] = len(feats)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
