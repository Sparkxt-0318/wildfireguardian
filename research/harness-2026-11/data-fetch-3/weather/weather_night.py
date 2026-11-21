#!/usr/bin/env python3
"""Resumable, throttled slim-weather run (13 Nov 2026 plan), using research/forecast-v2/scripts/rebuild_environment.py.

- Calls rebuild_environment.slim_weather(e) per event. Each Open-Meteo response is cached by request signature, and each
  event writes ecmwf_ifs_complete.json; so a relaunch re-sends NOTHING that already succeeded (no double-spend).
- Throttle on WEIGHTED calls (Open-Meteo: locations x max(1, days/14) x max(1, variables/10)), counted before each
  real request, against rolling windows: <= PER_MIN per 60 s, <= PER_HOUR per 3600 s, <= PER_DAY since 00:00 UTC.
  It waits rather than exceeding them; it never retries around a limit reply (the module's polite wait applies).
- Appends one CSV row per real request to LOG (utc, workspace, event, locations, days, weighted, day_total) and one
  line per start/stop to RUNLOG, so restarts are visible with time and stage.
Usage: python weather_night.py PLAN.json   (PLAN: [{"workspace": DIR, "events": [ids] | "all"}], run in order)
"""
import csv, json, os, sys, time
from collections import deque
from pathlib import Path

PER_MIN, PER_HOUR, PER_DAY = 500, 4500, 9500
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / 'research/forecast-v2/scripts'))
import rebuild_environment as rb  # noqa: E402
env = rb.env
import pandas as pd  # noqa: E402

LOG = Path(os.environ.get('WN_LOG', 'weather_requests.csv'))
RUNLOG = Path(os.environ.get('WN_RUNLOG', 'weather_runlog.txt'))
window = deque()  # (t, weighted)
state = {'ws': '', 'ev': ''}


def day_total():
    if not LOG.exists():
        return 0.0
    today = time.strftime('%Y-%m-%d', time.gmtime())
    with LOG.open() as f:
        return sum(float(r['weighted']) for r in csv.DictReader(f) if r['utc'].startswith(today))


def weighted(params):
    n = len(str(params['latitude']).split(','))
    days = (pd.Timestamp(params['end_date']) - pd.Timestamp(params['start_date'])).days + 1
    nvars = len(str(params['hourly']).split(','))
    return n * max(1.0, days / 14) * max(1.0, nvars / 10), n, days


def throttle(cost):
    while True:
        now = time.time()
        while window and now - window[0][0] > 3600:
            window.popleft()
        last_min = sum(c for t, c in window if now - t <= 60)
        last_hour = sum(c for _, c in window)
        if day_total() + cost > PER_DAY:
            raise RuntimeError('Daily public API limit reached (own budget %d); cached downloads preserved' % PER_DAY)
        if last_min + cost <= PER_MIN and last_hour + cost <= PER_HOUR:
            return
        time.sleep(5)


_get = env.SESSION.get


def get(url, params=None, **kw):
    if 'open-meteo' in url:
        cost, n, days = weighted(params)
        throttle(cost)
        r = _get(url, params=params, **kw)
        window.append((time.time(), cost))
        new = not LOG.exists()
        with LOG.open('a', newline='') as f:
            w = csv.writer(f)
            if new:
                w.writerow(['utc', 'workspace', 'event', 'locations', 'days', 'weighted', 'http', 'day_total'])
            w.writerow([time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), state['ws'], state['ev'], n, days,
                        round(cost, 2), r.status_code, round(day_total() + cost, 1)])
        return r
    return _get(url, params=params, **kw)


env.SESSION.get = get


def note(msg):
    with RUNLOG.open('a') as f:
        f.write(time.strftime('%Y-%m-%dT%H:%M:%SZ ', time.gmtime()) + msg + '\n')
    print(msg, flush=True)


def estimate(e):
    p, _, _ = env.grid(e)
    n = len(env.o1280_locations(e, p))
    s, t = pd.Timestamp(e['start_utc']), pd.Timestamp(e['end_utc'])
    days = (t.floor('D') - s.floor('D')).days + 1
    batches = [min(12, n - k) for k in range(0, n, 12)]
    return sum(b * max(1.0, days / 14) for b in batches), n, days


def main():
    plan = json.loads(Path(sys.argv[1]).read_text())
    if '--estimate' in sys.argv:
        tot = 0.0
        for step in plan:
            ws = Path(step['workspace']).resolve(); root = ws / 'data/environment'
            rb.configure(root, ws / 'zenodo/extracted')
            events = json.loads((root / 'events.json').read_text())
            if step['events'] != 'all':
                events = [e for e in events if e['id'] in set(step['events'])]
            sub = sum(estimate(e)[0] for e in events
                      if not (root / 'regions' / e['id'] / 'weather/ecmwf_ifs_complete.json').exists())
            print(f'{ws.name}: {len(events)} events, weighted still to fetch {sub:.0f}'); tot += sub
        print(f'TOTAL {tot:.0f}')
        return 0
    note(f'START pid={os.getpid()} plan={sys.argv[1]} day_total_so_far={day_total():.1f}')
    for step in plan:
        ws = Path(step['workspace']).resolve()
        root = ws / 'data/environment'
        rb.configure(root, ws / 'zenodo/extracted')  # zenodo path unused by the weather stage
        events = json.loads((root / 'events.json').read_text())
        if step['events'] != 'all':
            want = set(step['events'])
            events = [e for e in events if e['id'] in want]
            assert len(events) == len(want), (ws, want - {e['id'] for e in events})
        events.sort(key=lambda e: e['width'] * e['height'] * (pd.Timestamp(e['end_utc']) - pd.Timestamp(e['start_utc'])).days)
        done = sum((root / 'regions' / e['id'] / 'weather/ecmwf_ifs_complete.json').exists() for e in events)
        note(f'STEP {ws.name}: {len(events)} events, {done} already complete')
        for e in events:
            state['ws'], state['ev'] = ws.name, e['id']
            try:
                rb.slim_weather(e)
            except RuntimeError as err:
                if 'limit' in str(err).lower():
                    note(f'STOPPED (limit) at {ws.name}/{e["id"]}: {err}')
                    return 3
                raise
        note(f'STEP DONE {ws.name}')
    note('ALL DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
