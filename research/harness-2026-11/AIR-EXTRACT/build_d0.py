"""D0_RULE.md (+ amendments 1-2): the D0 air row (staff/agency only) for the three early-action tables.

Daylight gate always; wind gate only with --wind (Open-Meteo archive JSON written by fetch_wind_openmeteo.py).
Reads the register CSV from outside the repository (sha-gated), the OSM 2025-01-01 sigungu polygons, the early-action
list and planner place points. Recomputes no routing.

    python -I build_d0.py --csv CSV --osm SIGUNGU.geojson --list EARLY_ACTION_LIST.json --places-dir DIR \
        [--wind WIND.json] --out-dir results
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
from collections import Counter
from pathlib import Path

from pyproj import Geod
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

CSV_SHA = '55f666251b5e803ad2fd92eaaf1a8518200045038dc03838b0d76f73b6137931'
KST = dt.timezone(dt.timedelta(hours=9))
STEP = 1800
VARIANTS = ('kriged_mean', 'firms_early', 'envelope')
RADIUS_KM = 100.0
G = Geod(ellps='WGS84')
ABSENCE = "one fire, March 2025, that day's wind. A place not on this list has not been shown to have a road escape."
STAFF = 'Staff and agency use only. Not resident-facing.'
FIXED = ['flight feasibility is the pilot\'s and agency\'s decision', 'forest-aviation operating site, not a pickup point',
         'this row does not resolve the place']
DATUM = 'not stated anywhere in the source; read as WGS84/GRS80 geographic; possible position error of a few hundred metres'
BASE_DATE = ('The register\'s base date (2025-10-22) is after the March 2025 fires. These rows describe sites registered '
             'as of that date, not sites known to exist at the replay time.')
PORTAL = 'Portal limits (quoted from the source): military landing sites are excluded; use requires prior coordination with the managing agency.'
IDENT = ('data.go.kr 15069465, 산림청 산림항공본부, licence unrestricted, base date 2025-10-22 (this release pinned; '
         'annual updates, next 2027-07-31); custody ledger row 88')
WIND_LABEL = 'reanalysis-based, not observed; grid scale kilometres; not a flight-safety assessment'
GUST_OBS = ('documented observation, not a gate: gusts of about 27 m/s reported on 25 Mar 2025 (source researcher); the '
            'reanalysis used here peaks at about 14 m/s, so its wind gate errs toward "not excluded"')
KT = 0.514444
LIM12, LIM3, SPREAD = 40 * KT, 30 * KT, 15 * KT
FORBIDDEN = [r'\bflyable\b', r'\bpossible\b(?! position error)', r'\bsafe\b', r'\brescue\b', r'evacuate by air',
             r'landing zone', r'\bextraction\b']


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---------------------------------------------------------------- NOAA solar position (General Solar Position, NOAA)
def solar_elevation(lat, lon, t_utc: dt.datetime) -> float:
    jd = t_utc.timestamp() / 86400.0 + 2440587.5
    jc = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360
    m = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    e = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    c = (math.sin(math.radians(m)) * (1.914602 - jc * (0.004817 + 0.000014 * jc)) +
         math.sin(math.radians(2 * m)) * (0.019993 - 0.000101 * jc) + math.sin(math.radians(3 * m)) * 0.000289)
    true_long = l0 + c
    omega = 125.04 - 1934.136 * jc
    app_long = true_long - 0.00569 - 0.00478 * math.sin(math.radians(omega))
    eps0 = 23 + (26 + ((21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813)))) / 60) / 60
    eps = eps0 + 0.00256 * math.cos(math.radians(omega))
    decl = math.degrees(math.asin(math.sin(math.radians(eps)) * math.sin(math.radians(app_long))))
    y = math.tan(math.radians(eps / 2)) ** 2
    eqt = 4 * math.degrees(y * math.sin(2 * math.radians(l0)) - 2 * e * math.sin(math.radians(m)) +
                           4 * e * y * math.sin(math.radians(m)) * math.cos(2 * math.radians(l0)) -
                           0.5 * y * y * math.sin(4 * math.radians(l0)) - 1.25 * e * e * math.sin(2 * math.radians(m)))
    minutes = t_utc.hour * 60 + t_utc.minute + t_utc.second / 60
    tst = (minutes + eqt + 4 * lon) % 1440
    ha = tst / 4 - 180 if tst / 4 >= 0 else tst / 4 + 180
    zen = math.degrees(math.acos(math.sin(math.radians(lat)) * math.sin(math.radians(decl)) +
                                 math.cos(math.radians(lat)) * math.cos(math.radians(decl)) * math.cos(math.radians(ha))))
    return 90 - zen


def daylight_minutes_left(lat, lon, t_utc):
    """Minutes until the sun's centre reaches -0.833° (0 at night). 1-minute steps, up to 24 h."""
    if solar_elevation(lat, lon, t_utc) < -0.833:
        return 0
    for k in range(1, 24 * 60 + 1):
        if solar_elevation(lat, lon, t_utc + dt.timedelta(minutes=k)) < -0.833:
            return k
    return 24 * 60


def sun_event(lat, lon, day: dt.date, rising: bool):
    """Sunrise/sunset (UTC) by 1-minute scan of the elevation crossing -0.833°, for the D6 test."""
    t = dt.datetime(day.year, day.month, day.day, tzinfo=KST).astimezone(dt.timezone.utc)
    prev = solar_elevation(lat, lon, t)
    for k in range(1, 24 * 60 + 1):
        tk = t + dt.timedelta(minutes=k)
        e = solar_elevation(lat, lon, tk)
        if rising and prev < -0.833 <= e or (not rising) and prev >= -0.833 > e:
            return tk
        prev = e
    return None


def d6_test():
    from astral import LocationInfo
    from astral.sun import sun
    out = []
    for name, lat, lon, day in (('Yeongdeok', 36.415, 129.365, dt.date(2025, 3, 25)),
                                ('Seoul', 37.5665, 126.978, dt.date(2025, 6, 21))):
        ref = sun(LocationInfo(name, 'KR', 'Asia/Seoul', lat, lon).observer, date=day, tzinfo=KST)
        for ev, rising in (('sunrise', True), ('sunset', False)):
            mine = sun_event(lat, lon, day, rising)
            diff = abs((mine - ref[ev].astimezone(dt.timezone.utc)).total_seconds()) / 60
            out.append({'place': name, 'date': str(day), 'event': ev, 'noaa_kst': mine.astimezone(KST).strftime('%H:%M'),
                        'astral_kst': ref[ev].strftime('%H:%M'), 'diff_min': round(diff, 2), 'ok': diff <= 2})
    return out


# ---------------------------------------------------------------- register
def parse_register(path):
    rows = list(csv.DictReader(io.StringIO(Path(path).read_bytes().decode('cp949'))))
    sites, counts, bad_by_sgg = [], Counter(), Counter()
    for r in rows:
        f = [r[k].strip() for k in ('북쪽위도', '북위분', '북위초', '동경도', '동경분', '동경초')]
        parts = r['이착륙장주소'].split()
        sgg = parts[1] if len(parts) > 1 else None
        if not all(f):
            counts['blank'] += 1
            bad_by_sgg[sgg] += 1
            continue
        try:
            d = [float(x) for x in f]
        except ValueError:
            counts['invalid'] += 1
            bad_by_sgg[sgg] += 1
            continue
        lat, lon = d[0] + d[1] / 60 + d[2] / 3600, d[3] + d[4] / 60 + d[5] / 3600
        wellformed = d[1] < 60 and d[2] < 60 and d[4] < 60 and d[5] < 60
        inside = 33 <= lat <= 39 and 124 <= lon <= 132
        if wellformed and inside:
            counts['usable'] += 1
            sites.append({'name': r['이착륙장명'], 'agency': r['관할기관명'], 'address': r['이착륙장주소'],
                          'sgg_address': sgg, 'lat': lat, 'lon': lon})
        else:
            counts['invalid'] += 1
            counts['invalid_wellformed_outside_korea'] += wellformed and not inside
            bad_by_sgg[sgg] += 1
    pts = {}
    for s in sites:
        pts.setdefault((round(s['lat'], 7), round(s['lon'], 7)), []).append(s)
    return rows, sites, pts, counts, bad_by_sgg


def norm_sgg(name):
    return (name or '').replace(' ', '')


def main():
    ap = argparse.ArgumentParser()
    for k in ('--csv', '--osm', '--list', '--places-dir', '--out-dir'):
        ap.add_argument(k, type=Path, required=True)
    ap.add_argument('--wind', type=Path, default=None)
    a = ap.parse_args()
    if sha(a.csv) != CSV_SHA:
        raise SystemExit('REGISTER_SHA_MISMATCH: D0 stops (D0_RULE amendment 1)')
    rows, sites, pts, counts, bad_by_sgg = parse_register(a.csv)
    ea = json.loads(a.list.read_text())
    osm = json.loads(a.osm.read_text())
    polys = [shape(f['geometry']) for f in osm['features']]
    pnames = [f['properties']['name'] for f in osm['features']]
    tree = STRtree(polys)

    def sgg_of(lon, lat):
        hits = [pnames[i] for i in tree.query(Point(lon, lat)) if polys[i].covers(Point(lon, lat))]
        return hits[0] if len(hits) == 1 else None

    place_xy = {}
    for reg in {u['region'] for t in ('main_list', 'some_variants_only', 'mixed_not_evaluated') for u in ea[t]}:
        for f in json.loads((a.places_dir / reg / 'places.geojson').read_text())['features']:
            place_xy[(reg, f['properties']['id'])] = f['geometry']['coordinates']
    wind = json.loads(a.wind.read_text()) if a.wind else None
    dpts = [(k[0], k[1], v) for k, v in pts.items()]           # distinct usable points
    # point-in-polygon of distinct site points that lie within RADIUS of any listed place
    used_places = {(u['region'], u['origin']) for t in ('main_list', 'some_variants_only', 'mixed_not_evaluated') for u in ea[t]}
    near = set()
    for (lat, lon, ss) in dpts:
        for key in used_places:
            x, y = place_xy[key]
            if G.inv(x, y, lon, lat)[2] / 1000 <= RADIUS_KM:
                near.add((lat, lon))
                break
    pip = {}
    for (lat, lon, ss) in dpts:
        if (lat, lon) in near:
            poly_sgg = sgg_of(lon, lat)
            pip[(lat, lon)] = {'osm_sgg': poly_sgg,
                               'inside_stated': all(poly_sgg and norm_sgg(s['sgg_address']) in norm_sgg(poly_sgg) or
                                                    (poly_sgg and norm_sgg(poly_sgg).startswith(norm_sgg(s['sgg_address'])))
                                                    for s in ss)}

    def row_time(u, table):
        lb = u['leave_by_s']
        if table == 'main_list':
            return u['first_grid_departure_in_set']
        ev = [v for v in VARIANTS if u['pairs'][v] != 'not evaluated']
        v0 = min(ev, key=lambda v: -1 if lb[v] is None else lb[v])
        return 0 if lb[v0] is None else (lb[v0] // STEP + 1) * STEP

    out_rows = {}
    d3_bad = []
    for table in ('main_list', 'some_variants_only', 'mixed_not_evaluated'):
        out_rows[table] = []
        for u in ea[table]:
            x, y = place_xy[(u['region'], u['origin'])]
            off = row_time(u, table)
            H = u['horizon_h'] * 3600
            if off >= H:                     # ledger row 85 note 1: no computed departure without a route
                out_rows[table].append({'region': u['region'], 'start': u['start'], 'horizon_h': u['horizon_h'],
                                        'origin': u['origin'], 'name': u['name'], 'name_en': u['name_en'],
                                        'row_time': None, 'status': 'no computed departure without a route',
                                        'gates': 'none evaluated (no row time)', 'fixed': FIXED})
                continue
            t0 = dt.datetime.strptime(u['start'], '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc)
            t = t0 + dt.timedelta(seconds=off)
            dists = sorted(((G.inv(x, y, lon, lat)[2] / 1000, lat, lon, ss) for lat, lon, ss in dpts), key=lambda r: r[0])
            dkm, slat, slon, ss = dists[0]
            # D3: independent haversine
            hv = sorted(((2 * 6371.0088 * math.asin(math.sqrt(math.sin(math.radians(lat - y) / 2) ** 2 + math.cos(math.radians(y)) *
                          math.cos(math.radians(lat)) * math.sin(math.radians(lon - x) / 2) ** 2)), lat, lon) for lat, lon, _ in dpts))
            if (hv[0][1], hv[0][2]) != (slat, slon) and abs(hv[0][0] - dkm) > 0.005 * dkm:
                d3_bad.append(u['origin'])
            within = sum(1 for r in dists if r[0] <= RADIUS_KM)
            psgg = sgg_of(x, y)
            excl = sum(n for k, n in bad_by_sgg.items() if k and psgg and norm_sgg(psgg).startswith(norm_sgg(k)))
            elev = solar_elevation(y, x, t)
            night = elev < -0.833
            left = daylight_minutes_left(y, x, t)
            texts = [f'{excl} registered site(s) in {psgg} excluded: coordinates blank or invalid in the source; '
                     'an excluded site could be nearer']
            if psgg and psgg.startswith('의성'):
                texts.append('의성 has 0 registered sites in the source')
            if psgg and psgg.startswith('울진'):
                texts.append('1 registered site in 울진 excluded: coordinates invalid in the source')
            w = None
            gates_not = ['wind', 'smoke', 'visibility']
            reason = ['night'] if night else []
            if wind is not None:
                w = wind_at(wind, (y, x), (slat, slon), t)
                if w and w['have_gusts']:
                    gates_not = ['smoke', 'visibility']
                    if w['over_type12']:
                        reason.append('wind')
            status = (f'excluded ({" and ".join(reason)})' if reason else
                      f'not excluded by the gates evaluated ({", ".join(gates_not[:-1]) + " and " + gates_not[-1] if len(gates_not) > 1 else gates_not[0]} not evaluated)')
            out_rows[table].append({
                'region': u['region'], 'start': u['start'], 'horizon_h': u['horizon_h'], 'origin': u['origin'],
                'name': u['name'], 'name_en': u['name_en'], 'place_sigungu_osm': psgg,
                'row_time': t.astimezone(KST).strftime('%Y-%m-%d %H:%M KST (replay)'), 'row_offset_s': off,
                'place_lonlat': [x, y],
                'nearest_site': {'name': ss[0]['name'], 'agency': ss[0]['agency'], 'address': ss[0]['address'],
                                 'lat': slat, 'lon': slon,
                                 'sites_at_this_point': len(ss), 'osm_sgg': pip.get((slat, slon), {}).get('osm_sgg'),
                                 'outside_stated_sigungu': not pip.get((slat, slon), {}).get('inside_stated', True)},
                'straight_line_distance_km': round(dkm, 1),
                'distinct_site_points_within_100km': within,
                'exclusion_texts': texts,
                'daylight': {'sun_elevation_deg': round(elev, 2), 'night': night, 'minutes_of_daylight_remaining': left},
                'wind': w, 'wind_observation_note': GUST_OBS if wind is not None else None,
                'status': status, 'fixed': FIXED})
    # ---- tests
    tests = {}
    tests['D1_rows'] = all(len(out_rows[t]) == len(ea[t]) for t in out_rows)
    tests['D2_register'] = (counts['usable'], counts['blank'], counts['invalid']) == (538, 24, 65) and \
        len(pts) == 500 and counts['invalid_wellformed_outside_korea'] == 10
    tests['D3_nearest'] = not d3_bad
    timed = [r for t in out_rows.values() for r in t if r.get('row_time')]
    tests['D4_exclusion_text'] = all(r['exclusion_texts'] for r in timed)
    tests['D5_pip'] = all((lat, lon) in pip for lat, lon, _ in dpts if (lat, lon) in near)
    d6 = d6_test()
    tests['D6_daylight'] = all(x['ok'] for x in d6) and all(r['daylight'] is not None for r in timed)
    tests['D7_statuses'] = all(r['status'].startswith(('excluded (', 'not excluded by the gates evaluated (')) or
                               r['status'] == 'no computed departure without a route' for t in out_rows.values() for r in t)
    tests['D8_labels'] = all(r['fixed'] == FIXED for t in out_rows.values() for r in t)
    partial = wind is None or not all(r['wind'] and r['wind']['have_gusts'] for r in timed)
    summ = {t: {'rows': len(v), 'no_row_time': sum(not r.get('row_time') for r in v),
                'excluded_night': sum(r['daylight']['night'] for r in v if r.get('row_time')),
                'excluded_wind': sum('wind' in r['status'] and r['status'].startswith('excluded') for r in v),
                'excluded_any': sum(r['status'].startswith('excluded') for r in v),
                'not_excluded': sum(r['status'].startswith('not excluded') for r in v),
                'wind_within_0p1_ms_of_a_limit': sum(bool(r.get('wind') and r['wind']['near_limit']) for r in v)}
            for t, v in out_rows.items()}
    out = {'schema': 'wfg.air-extract.d0/1', 'rule': 'D0_RULE.md (+ amendments 1-2)', 'staff_label': STAFF,
           'absence_line': ABSENCE, 'partial': 'partial: daylight gate only' if partial else None,
           'register': {'identity': IDENT, 'base_date_note': BASE_DATE, 'datum': DATUM, 'portal_limits': PORTAL,
                        'counts': dict(counts), 'distinct_usable_points': len(pts)},
           'boundaries': osm.get('label'), 'wind_source': None if wind is None else wind.get('label'),
           'gates_evaluated': ['daylight'] + (['wind'] if not partial else []),
           'summary_counts': summ,
           'summary_note': ('not a finding until the wind gate is in (assessor); hypothesis: most rows excluded'
                            if partial else 'hypothesis (assessor): most rows excluded; these counts are the finding'),
           'sites_outside_stated_sigungu': sum(1 for v in pip.values() if not v['inside_stated']),
           'd6_solar_test': d6, 'inputs_sha256': {'csv': sha(a.csv), 'osm': sha(a.osm), 'list': sha(a.list),
                                                  **({'wind': sha(a.wind)} if a.wind else {})},
           'tables': out_rows}
    md = render(out)
    bad = [p for p in FORBIDDEN if re.search(p, md.replace('# D0: AIR-EXTRACT', ''), re.I)]
    tests['D7_forbidden'] = not bad
    tests['D8_header'] = ABSENCE in md and BASE_DATE in md and DATUM in md
    out['pass_criteria'] = tests
    out['all_pass'] = all(tests.values())
    out['forbidden_hits'] = bad
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / 'D0_AIR_ROW.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    (a.out_dir / 'D0_AIR_ROW.md').write_text(md)
    print(json.dumps({'pass_criteria': tests, 'summary': summ, 'partial': out['partial'], 'hits': bad,
                      'outside_stated': out['sites_outside_stated_sigungu']}, ensure_ascii=False, indent=1))


def wind_at(wind, place, site, t):
    """Each location (place point, nearest site) is tested on its own at the row's hour (UTC); either one over the
    limit excludes (D0_RULE amendment 1; ledger row 85 fix). Values shown per point at 0.01 m/s."""
    hour = t.replace(minute=0, second=0).strftime('%Y-%m-%dT%H:00')
    pts = []
    for role, (lat, lon) in (('place', place), ('site', site)):
        rec = wind['points'].get(f'{lat:.4f},{lon:.4f}')
        if rec is None or hour not in rec['time']:
            return None
        i = rec['time'].index(hour)
        ws = rec['wind_speed_10m'][i]
        wg = (rec.get('wind_gusts_10m') or [None] * len(rec['time']))[i]
        have = wg is not None
        spread = (wg - ws) if have else None
        o12 = ws > LIM12 or (have and spread > SPREAD)
        o3 = ws > LIM3 or (have and spread > SPREAD)
        margin = min(abs(ws - LIM12), abs(ws - LIM3), abs(spread - SPREAD) if have else 1e9)
        pts.append({'point': role, 'mean_ms': round(ws, 2), 'gust_ms': None if wg is None else round(wg, 2),
                    'gust_spread_ms': None if spread is None else round(spread, 2), 'over_type12': o12, 'over_type3': o3,
                    'within_0p1_ms_of_a_limit': margin < 0.1})
    return {'label': WIND_LABEL, 'hour_utc': hour, 'points': pts, 'have_gusts': all(p['gust_ms'] is not None for p in pts),
            'over_type12': any(p['over_type12'] for p in pts), 'over_type3': any(p['over_type3'] for p in pts),
            'near_limit': any(p['within_0p1_ms_of_a_limit'] for p in pts),
            'limits': 'US interagency reference (NWCG PMS 510): 40 kt (20.58 m/s) Type 1-2, 30 kt (15.43 m/s) Type 3, '
                      '15 kt (7.72 m/s) gust spread; tested per point'}


def render(o):
    L = ['# D0: AIR-EXTRACT registered-site row (staff and agency use only)', '']
    if o['partial']:
        L += [f'> **{o["partial"]}.** The summary counts are not a finding until the wind gate is in.', '']
    L += [f'> {o["staff_label"]}', '', f'> **{o["absence_line"]}**', '',
          f'- **Register:** {o["register"]["identity"]}.', f'- **{o["register"]["base_date_note"]}**',
          f'- **Datum:** {o["register"]["datum"]}.', f'- **{o["register"]["portal_limits"]}**',
          f'- **Register counts:** {o["register"]["counts"]}; distinct usable points {o["register"]["distinct_usable_points"]}.',
          f'- **Boundaries:** {o["boundaries"]}.', f'- **Gates evaluated:** {", ".join(o["gates_evaluated"])}. Smoke and '
          'visibility are not evaluated.' + (f' Wind: {o["wind_source"]}.' if o['wind_source'] else ''),
          f'- **Sites within 100 km found outside the 시군구 named in their address (flagged, not moved):** '
          f'{o["sites_outside_stated_sigungu"]}.',
          f'- **Summary counts** ({o["summary_note"]}): {o["summary_counts"]}', '']
    heads = {'main_list': 'Main list', 'some_variants_only': 'No checked route under some variants only',
             'mixed_not_evaluated': 'Timing variants disagree on whether the modelled fire has already reached the start point'}
    for t, rows in o['tables'].items():
        L += [f'## {heads[t]} ({len(rows)} rows)', '',
              '| Place | Row time | Nearest registered site | Straight-line distance (km) | Site points within 100 km | '
              'Minutes of daylight remaining | Status | Notes |', '|---|---|---|---|---|---|---|---|']
        for r in rows:
            if not r.get('row_time'):
                L.append(f'| {r["name"]} ({r["name_en"]}), {r["region"]} {r["start"]} h{r["horizon_h"]} | — | — | — | — | — | '
                         f'{r["status"]} | {r["gates"]}; {"; ".join(r["fixed"])} |')
                continue
            ns = r['nearest_site']
            notes = r['exclusion_texts'] + (['nearest site lies outside the 시군구 named in its address'] if ns['outside_stated_sigungu'] else [])
            if r['wind']:
                notes.append(f'wind ({r["wind"]["label"]}; {r["wind"]["hour_utc"]} UTC): ' + '; '.join(
                    f'{p["point"]} mean {p["mean_ms"]} / gust {p["gust_ms"]} / spread {p["gust_spread_ms"]} m/s'
                    + (' (within 0.1 m/s of a limit)' if p['within_0p1_ms_of_a_limit'] else '') for p in r['wind']['points']))
            if r['wind_observation_note']:
                notes.append(r['wind_observation_note'])
            notes += r['fixed']
            L.append(f'| {r["name"]} ({r["name_en"]}), {r["region"]} {r["start"]} h{r["horizon_h"]} | {r["row_time"]} | '
                     f'{ns["name"]} ({ns["agency"]}) | {r["straight_line_distance_km"]} | {r["distinct_site_points_within_100km"]} | '
                     f'{r["daylight"]["minutes_of_daylight_remaining"]} | {r["status"]} | {"; ".join(notes)} |')
        L.append('')
    L += [f'> **{o["absence_line"]}**', '']
    return '\n'.join(L)


if __name__ == '__main__':
    main()
