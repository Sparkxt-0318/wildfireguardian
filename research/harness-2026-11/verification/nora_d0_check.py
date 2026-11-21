"""Independent verifier: AIR-EXTRACT D0 rows. Daylight with an independent solar routine (astral 3.2 elevation, refraction
off -> geometric centre vs -0.833), row times for the three tables from EARLY_ACTION_LIST, wind-gate consistency from
the shown values, summary counts. argv: D0_AIR_ROW.json, EARLY_ACTION_LIST.json"""
import json, sys, collections, datetime as dt
from astral import Observer
from astral.sun import elevation
D, L = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
KT = 0.514444
src = {'main_list': L['main_list'], 'some_variants_only': L['some_variants_only'], 'mixed_not_evaluated': L['mixed_not_evaluated']}
key = lambda u: (u['region'], u['start'], u['horizon_h'], u['origin'])
out = collections.Counter(); bad = []
for tab, rows in D['tables'].items():
    S = {key(u): u for u in src[tab]}
    out[tab + ':rows'] = len(rows); out[tab + ':src'] = len(S)
    for r in rows:
        u = S[key(r)]
        # row time per amendment 2 B3
        if tab == 'main_list': want = u['first_grid_departure_in_set']
        else:
            ev = [v for v in u['pairs'] if u['pairs'][v] != 'not evaluated']
            lbs = {v: u['leave_by_s'][v] for v in ev}
            v0 = min(ev, key=lambda v: -1 if lbs[v] is None else lbs[v])
            H = u['horizon_h'] * 3600
            want = 0 if lbs[v0] is None else (lbs[v0] // 1800 + 1) * 1800
            if want >= H: want = None
        if r['row_offset_s'] != want: bad.append(('row time', tab, key(r), r['row_offset_s'], want))
        t = dt.datetime.strptime(r['start'], '%Y%m%dT%H%M%SZ').replace(tzinfo=dt.timezone.utc) + dt.timedelta(seconds=r['row_offset_s'])
        lon, lat = r['place_lonlat']
        e = elevation(Observer(latitude=lat, longitude=lon), t, with_refraction=False)
        night = e < -0.833
        if night != r['daylight']['night']: bad.append(('night', tab, key(r), round(e, 3), r['daylight']['sun_elevation_deg']))
        out[tab + ':max_elev_diff_x1000'] = max(out[tab + ':max_elev_diff_x1000'], int(abs(e - r['daylight']['sun_elevation_deg']) * 1000))
        w = r['wind']; over = w['mean_ms'] > 40 * KT or (w['have_gusts'] and w['gust_ms'] - w['mean_ms'] > 15 * KT)
        if over != w['over_type12']: bad.append(('wind flag', tab, key(r)))
        exc = night or w['over_type12']
        out[tab + ':night'] += night; out[tab + ':wind'] += w['over_type12']; out[tab + ':any'] += exc
        if exc != r['status'].startswith('excluded'): bad.append(('status', tab, key(r), r['status'][:40]))
        out[tab + ':spread_margin_min_ms_x10'] = min(out.get(tab + ':spread_margin_min_ms_x10', 999), int(abs((w['gust_ms'] - w['mean_ms']) - 15 * KT) * 10))
print(dict(out)); print('summary in file', D['summary_counts']); print('problems', len(bad)); [print(' ', b) for b in bad[:10]]
