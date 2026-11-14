"""D0_RULE amendment 2 (B2 fallback): hourly 10 m wind speed and gusts from the Open-Meteo historical archive at every
D0 place point and nearest registered site, 22-27 Mar 2025 (UTC). No key.

Budget (the data-fetch author): today only, hard ceiling 1,500 weighted calls, <= 500/min, stop on any 429.
Weighting assumed per Open-Meteo: one call per location for <= 10 variables and <= 14 days (here 2 variables, 6 days).
Writes the response JSON outside the repository and a ledger of the weighted calls.

    python3 fetch_wind_openmeteo.py --d0 results/D0_AIR_ROW.json --out WIND.json --ledger LEDGER.json
"""
import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

URL = 'https://archive-api.open-meteo.com/v1/archive'
CEILING = 1500
BATCH = 50
LABEL = 'Open-Meteo historical archive (reanalysis-based, not observed; grid scale kilometres; not a flight-safety assessment)'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--d0', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--ledger', type=Path, required=True)
    a = ap.parse_args()
    d0 = json.loads(a.d0.read_text())
    pts = set()
    for rows in d0['tables'].values():
        for r in rows:
            x, y = r['place_lonlat']
            pts.add((round(y, 4), round(x, 4)))
            pts.add((round(r['nearest_site']['lat'], 4), round(r['nearest_site']['lon'], 4)))
    pts = sorted(pts)
    if len(pts) > CEILING:
        raise SystemExit(f'BUDGET: {len(pts)} weighted calls > ceiling {CEILING}')
    out, ledger, spent = {}, [], 0
    for i in range(0, len(pts), BATCH):
        b = pts[i:i + BATCH]
        q = {'latitude': ','.join(f'{p[0]:.4f}' for p in b), 'longitude': ','.join(f'{p[1]:.4f}' for p in b),
             'start_date': '2025-03-22', 'end_date': '2025-03-27', 'hourly': 'wind_speed_10m,wind_gusts_10m',
             'wind_speed_unit': 'ms', 'timezone': 'UTC'}
        req = urllib.request.Request(URL + '?' + urllib.parse.urlencode(q), headers={'User-Agent': 'research-client'})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            ledger.append({'batch': i // BATCH, 'locations': len(b), 'http': e.code, 'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
            a.ledger.write_text(json.dumps({'spent_weighted': spent, 'calls': ledger, 'stopped': f'HTTP {e.code}'}, indent=1))
            raise SystemExit(f'STOP on HTTP {e.code} after {spent} weighted')
        spent += len(b)
        ledger.append({'batch': i // BATCH, 'locations': len(b), 'weighted': len(b),
                       'utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        body = body if isinstance(body, list) else [body]
        for p, rec in zip(b, body):
            h = rec['hourly']
            out[f'{p[0]:.4f},{p[1]:.4f}'] = {'time': h['time'], 'wind_speed_10m': h['wind_speed_10m'],
                                             'wind_gusts_10m': h.get('wind_gusts_10m'),
                                             'grid_lat': rec.get('latitude'), 'grid_lon': rec.get('longitude')}
        time.sleep(2)
    a.out.write_text(json.dumps({'label': LABEL, 'url': URL, 'variables': ['wind_speed_10m', 'wind_gusts_10m'],
                                 'unit': 'm/s', 'dates_utc': ['2025-03-22', '2025-03-27'], 'points': out}))
    a.ledger.write_text(json.dumps({'spent_weighted': spent, 'calls': ledger, 'locations': len(pts)}, indent=1))
    gusts = all(v['wind_gusts_10m'] and any(g is not None for g in v['wind_gusts_10m']) for v in out.values())
    print(json.dumps({'locations': len(pts), 'spent_weighted': spent, 'gusts_present_everywhere': gusts}))


if __name__ == '__main__':
    main()
