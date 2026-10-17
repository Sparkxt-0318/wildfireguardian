#!/usr/bin/env python3
"""Precompute evacuation dispatch results for every origin of a region through the Route-Check API.

The planner never imports routing or forecasting code. This script only talks to the
Route-Check API (official contract: planner/contract/wfg_api_v1.yaml):

* OSM origins are grouped by their K nearest shelters and sent as POST /dispatch-plans
  (≤ 200 origins, ≤ 20 destinations, ≤ 24 departure offsets per plan, policy "full").
* Recorded research-panel origins are sent as individual POST /route-checks with their
  recorded destination, dwell, arrival window and incurred dose (dispatch plans have no
  incurred-dose field), at every grid offset plus their recorded departure offset.
* For every origin with a checked route, one more check with policy "travel_only" at the
  same start, shelter and offset gives the dashed travel-time-only comparison.

Results are written per recorded scenario set to planner/cache/<region>/<input_compact>.json
with provenance, plus planner/cache/INDEX.json. The app loads these files so the booth demo
is instant and works offline. Standard library only.

    python3 planner/scripts/precompute.py --api http://127.0.0.1:8765/v1 \
        --regions uiseong_andong_2025,yeongdeok_2025
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PLANNER = Path(__file__).resolve().parents[1]
SCHEMA = 'wfg.planner.cache/1'
DEFAULT_DWELL_S = 120          # required stay of every recorded study mission
SNAP_LIMIT_M = 300             # the API refuses snaps farther than this
MAX_ORIGINS, MAX_DESTINATIONS, MAX_OFFSETS = 200, 20, 24
LFS_LIMIT_BYTES = 50 * 1024 * 1024
DONE = ('done', 'failed')


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class ApiError(Exception):
    def __init__(self, status: int, body: dict | str):
        super().__init__(f'HTTP {status}: {str(body)[:300]}')
        self.status, self.body = status, body


class Api:
    def __init__(self, base: str, timeout: float = 60.0):
        self.base = base.rstrip('/')
        self.timeout = timeout

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode('utf-8')
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        last: Exception | None = None
        for attempt in range(6):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                detail = e.read().decode('utf-8', 'replace')
                if e.code < 500:
                    try:
                        raise ApiError(e.code, json.loads(detail))
                    except json.JSONDecodeError:
                        raise ApiError(e.code, detail[:800])
                last = e
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = e
            time.sleep(min(30, 2 ** attempt))
        raise SystemExit(f'{method} {path} failed after retries: {last}')

    def get(self, path: str) -> dict:
        return self.call('GET', path)

    def post(self, path: str, body: dict) -> dict:
        return self.call('POST', path, body)


def haversine_m(a, b) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def compact(iso: str) -> str:
    t = dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(dt.timezone.utc)
    return t.strftime('%Y%m%dT%H%M%SZ')


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git_commit() -> str | None:
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=PLANNER, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def is_mock(health: dict) -> bool:
    return health.get('mode') == 'mock' or health.get('mock') is True


def load_places(region_id: str) -> list[dict]:
    p = PLANNER / 'public' / 'data' / 'regions' / region_id / 'places.geojson'
    if not p.is_file():
        raise SystemExit(f'Missing {p}; run planner/tools/extract_places.py first')
    return json.loads(p.read_text(encoding='utf-8'))['features']


def lonlat(f: dict) -> dict:
    lon, lat = f['geometry']['coordinates'][:2]
    return {'lon': lon, 'lat': lat}


def grid_offsets(horizon_s: float, step_s: int) -> list[int]:
    offs = list(range(0, int(horizon_s), step_s))
    if len(offs) > MAX_OFFSETS:
        raise SystemExit(f'{len(offs)} offsets exceed the contract limit {MAX_OFFSETS}; use a larger --step-min')
    return offs


def dispatch_requests(region_id: str, sset: dict, places: list[dict], offsets: list[int], k: int) -> list[dict]:
    """OSM origins grouped by identical K-nearest shelter sets (straight-line distance)."""
    shelters = [f for f in places if f['properties']['role'] == 'destination' and f['properties'].get('checkable', True)]
    origins = [f for f in places if f['properties']['role'] == 'origin' and f['properties'].get('checkable', True)]
    if not shelters or not origins:
        return []
    k = max(1, min(k, MAX_DESTINATIONS))
    by_id = {s['properties']['id']: s for s in shelters}
    groups: dict[tuple[str, ...], list[dict]] = {}
    for o in origins:
        oc = o['geometry']['coordinates']
        near = sorted(shelters, key=lambda s: (haversine_m(oc, s['geometry']['coordinates']), s['properties']['id']))[:k]
        groups.setdefault(tuple(sorted(s['properties']['id'] for s in near)), []).append(o)
    horizon = float(sset['horizon_s'])
    out = []
    for dest_ids, members in sorted(groups.items()):
        for i in range(0, len(members), MAX_ORIGINS):
            chunk = members[i:i + MAX_ORIGINS]
            out.append({
                'region': region_id,
                'input_time': sset['input_time'],
                'fire_input': {'type': 'recorded', 'scenario_set_id': sset['scenario_set_id']},
                'origins': [{'id': o['properties']['id'], 'location': lonlat(o)} for o in chunk],
                'destinations': [{'id': d, 'location': lonlat(by_id[d]), 'dwell_s': DEFAULT_DWELL_S,
                                  'window': [0, horizon]} for d in dest_ids],
                'depart_offsets_s': offsets,
                'dwell_s': DEFAULT_DWELL_S,
                'policy': 'full',
                'client_ref': f'planner-precompute:{region_id}:{compact(sset["input_time"])}',
            })
    return out


def research_requests(region_id: str, sset: dict, places: list[dict], offsets: list[int]) -> list[tuple[dict, dict]]:
    """Individual route checks for recorded research origins (recorded destination/dwell/window/incurred)."""
    out = []
    for o in places:
        p = o['properties']
        if p['role'] != 'research_origin' or p.get('scenario_set_id') != sset['scenario_set_id']:
            continue
        rec = p['recorded']
        offs = sorted(set(offsets) | {int(rec['depart_offset_s'])})
        open_s, close_s = rec['destination_window']
        horizon = float(rec.get('horizon_s') or sset['horizon_s'])
        for off in offs:
            if max(off, open_s) + rec['dwell_s'] > min(close_s, horizon):
                # Same rule the API applies (422 WINDOW_UNSATISFIABLE): no arrival can meet the recorded window.
                out.append(({'origin_id': p['id'], 'destination_id': rec['destination_id'], 'depart_offset_s': off,
                             'job_id': None, 'skipped': 'WINDOW_UNSATISFIABLE'}, None))
                continue
            body = {
                'region': region_id,
                'input_time': sset['input_time'],
                'start': {'node_id': p['snap']['node']},
                'destination': {'node_id': rec['destination_node']},
                'depart_offset_s': off,
                'dwell_s': rec['dwell_s'],
                'destination_window': rec['destination_window'],
                'policy': 'full',
                'fire_input': {'type': 'recorded', 'scenario_set_id': sset['scenario_set_id']},
                'client_ref': f'planner-precompute:{p["id"]}',
            }
            if rec.get('incurred_dose_kj_m2') is not None:
                body['incurred_dose_kj_m2'] = rec['incurred_dose_kj_m2']
            if rec.get('limits'):   # FN/FX missions carry mission-specific recorded dose limits
                body['limits'] = rec['limits']
            out.append(({'origin_id': p['id'], 'destination_id': rec['destination_id'], 'depart_offset_s': off}, body))
    return out


def wait_jobs(api: Api, kind: str, job_ids: list[str], poll_s: float, timeout_s: float) -> dict[str, dict]:
    path = '/dispatch-plans/' if kind == 'dispatch_plan' else '/route-checks/'
    pending, done = list(job_ids), {}
    started, last = time.monotonic(), None
    while pending:
        still = []
        for jid in pending:
            job = api.get(path + jid)
            if job['status'] in DONE:
                done[jid] = job
            else:
                still.append(jid)
        pending = still
        state = (kind, len(done), len(job_ids))
        if state != last:
            log(f'    {kind}: {len(done)}/{len(job_ids)} finished')
            last = state
        if pending:
            if time.monotonic() - started > timeout_s:
                raise SystemExit(f'{len(pending)} {kind} jobs unfinished after {timeout_s} s')
            time.sleep(poll_s)
    return done


def best_checked(plan_jobs: list[dict], research: list[tuple[dict, dict]], checks: dict[str, dict]) -> dict[str, dict]:
    """Per origin: the attempt the app shows by default (latest checked offset, earliest arrival)."""
    best = {}
    for job in plan_jobs:
        for plan in (job.get('result') or {}).get('plans', []):
            b = plan.get('best')
            if plan.get('best_verdict') == 'checked_route' and b and b.get('route_check_job_id'):
                best[plan['origin_id']] = b['route_check_job_id']
    by_origin: dict[str, list] = {}
    for meta, _ in research:
        if not meta.get('job_id'):
            continue
        res = (checks.get(meta['job_id']) or {}).get('result') or {}
        if res.get('verdict') == 'checked_route':
            by_origin.setdefault(meta['origin_id'], []).append((meta['depart_offset_s'], -(res.get('arrival_s') or 0), meta['job_id']))
    for oid, rows in by_origin.items():
        best[oid] = max(rows)[2]
    return {oid: checks[jid] for oid, jid in best.items() if jid in checks}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--api', default='http://127.0.0.1:8765/v1')
    ap.add_argument('--regions', default='uiseong_andong_2025,yeongdeok_2025')
    ap.add_argument('--step-min', type=int, default=10, help='departure offset step in minutes')
    ap.add_argument('--k', type=int, default=3, help='candidate shelters per origin (nearest by straight line)')
    ap.add_argument('--out', type=Path, default=PLANNER / 'cache')
    ap.add_argument('--poll', type=float, default=2.0)
    ap.add_argument('--timeout-h', type=float, default=24.0)
    ap.add_argument('--no-travel-only', action='store_true', help='skip the travel-time-only comparison checks')
    ap.add_argument('--allow-mock', action='store_true', help='write a cache from the MOCK API (labelled MOCK)')
    a = ap.parse_args()

    api = Api(a.api)
    try:
        health = api.get('/health')
    except ApiError as e:
        raise SystemExit(f'GET /health failed: {e}')
    mode = 'mock' if is_mock(health) else 'live'
    if mode == 'mock' and not a.allow_mock:
        raise SystemExit('The API is the MOCK server. Pass --allow-mock to write a MOCK-labelled cache.')
    regions = {r['id']: r for r in api.get('/regions')['regions']}
    wanted = [r.strip() for r in a.regions.split(',') if r.strip()]
    a.out.mkdir(parents=True, exist_ok=True)
    index_path = a.out / 'INDEX.json'
    index = json.loads(index_path.read_text(encoding='utf-8')) if index_path.is_file() else []
    commit = git_commit()
    timeout_s = a.timeout_h * 3600

    for region_id in wanted:
        if region_id not in regions:
            raise SystemExit(f'Region {region_id} not served by the API; available: {sorted(regions)}')
        places = load_places(region_id)
        for sset in regions[region_id]['scenario_sets']:
            t0 = time.monotonic()
            log(f'{region_id} · {sset["input_time"]} · {sset["scenario_set_id"]}')
            offsets = grid_offsets(sset['horizon_s'], a.step_min * 60)
            plans_req = dispatch_requests(region_id, sset, places, offsets, a.k)
            research = research_requests(region_id, sset, places, offsets)
            n_attempts = sum(len(r['origins']) * len(r['destinations']) * len(r['depart_offsets_s']) for r in plans_req)
            log(f'  {len(plans_req)} dispatch plans ({n_attempts} checks) + {len(research)} research checks')

            plan_ids, rejected = [], []
            for body in plans_req:
                try:
                    plan_ids.append(api.post('/dispatch-plans', body)['job_id'])
                except ApiError as e:
                    rejected.append({'kind': 'dispatch_plan', 'origins': [o['id'] for o in body['origins']],
                                     'status': e.status, 'error': e.body})
                    log(f'  dispatch plan rejected: {e}')
            for meta, body in research:
                if body is None:
                    continue
                try:
                    meta['job_id'] = api.post('/route-checks', body)['job_id']
                except ApiError as e:
                    meta['job_id'], meta['skipped'] = None, (e.body.get('error', {}).get('code') if isinstance(e.body, dict) else 'REJECTED')
                    rejected.append({'kind': 'route_check', 'origin_id': meta['origin_id'],
                                     'depart_offset_s': meta['depart_offset_s'], 'status': e.status, 'error': e.body})
                    log(f'  route check rejected: {e}')
            plan_jobs = wait_jobs(api, 'dispatch_plan', plan_ids, a.poll, timeout_s)
            check_ids = [m['job_id'] for m, _ in research if m.get('job_id')]
            for job in plan_jobs.values():
                for plan in (job.get('result') or {}).get('plans', []):
                    check_ids += [x['route_check_job_id'] for x in plan.get('attempts', []) if x.get('route_check_job_id')]
            checks = wait_jobs(api, 'route_check', sorted(set(check_ids)), a.poll, timeout_s)

            travel_only = {}
            if not a.no_travel_only:
                best = best_checked([plan_jobs[i] for i in plan_ids], research, checks)
                to_ids = {}
                for oid, job in best.items():
                    req = dict(job['request'])
                    for key in ('policy', 'limits', 'run_independent_check', 'client_ref'):
                        req.pop(key, None)
                    req.update({'policy': 'travel_only', 'client_ref': f'planner-precompute:travel_only:{oid}'})
                    try:
                        to_ids[api.post('/route-checks', req)['job_id']] = oid
                    except ApiError as e:
                        rejected.append({'kind': 'travel_only', 'origin_id': oid, 'status': e.status, 'error': e.body})
                        log(f'  travel_only check rejected: {e}')
                for jid, job in wait_jobs(api, 'route_check', list(to_ids), a.poll, timeout_s).items():
                    travel_only[to_ids[jid]] = job

            doc = {
                'schema': SCHEMA,
                'region_id': region_id,
                'scenario_set_id': sset['scenario_set_id'],
                'input_time': sset['input_time'],
                'fire_input': {'type': 'recorded', 'scenario_set_id': sset['scenario_set_id']},
                'created_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                'api': {'base': a.api, 'mode': mode, 'health': health},
                'planner_commit': commit,
                'generator': {'script': 'planner/scripts/precompute.py', 'python': platform.python_version(),
                              'client_host': f'{platform.system()} {platform.machine()}',
                              'step_min': a.step_min, 'shelters_per_origin': a.k,
                              'default_dwell_s': DEFAULT_DWELL_S, 'wall_s': round(time.monotonic() - t0, 1)},
                'requests': plans_req,
                'plans': [plan_jobs[i] for i in plan_ids],
                'research_checks': [m for m, _ in research],
                'rejected_requests': rejected,
                'route_checks': checks,
                'travel_only': travel_only,
            }
            raw = json.dumps(doc, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            rel = Path(region_id) / f'{compact(sset["input_time"])}.json'
            out = a.out / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(raw)
            if len(raw) > LFS_LIMIT_BYTES:
                log(f'  WARNING {out} is {len(raw) / 1e6:.1f} MB: store it with Git LFS or as a Release asset, not a normal commit')
            n_origins = sum(len(r['origins']) for r in plans_req) + len({m['origin_id'] for m, _ in research})
            index = [e for e in index if not (e['region_id'] == region_id and e['scenario_set_id'] == sset['scenario_set_id'])]
            index.append({'region_id': region_id, 'scenario_set_id': sset['scenario_set_id'],
                          'input_time': sset['input_time'], 'path': rel.as_posix(), 'api_mode': mode,
                          'created_at': doc['created_at'], 'origins': n_origins,
                          'bytes': len(raw), 'sha256': sha256_bytes(raw)})
            log(f'  wrote {out} ({len(raw) / 1e6:.2f} MB, {n_origins} origins, {doc["generator"]["wall_s"]} s)')
    index.sort(key=lambda e: (e['region_id'], e['input_time']))
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    log(f'Updated {index_path}')


if __name__ == '__main__':
    main()
