#!/usr/bin/env python3
"""Precompute evacuation dispatch results for every origin of a region through the Route-Check API.

The planner never imports routing or forecasting code. This script only talks to the Route-Check
API (official contract: planner/contract/wfg_api_v1.yaml):

* OSM origins (villages, care facilities) start at their 진입 지점 (entry point: the nearest road node
  the API accepts, see planner/public/data/regions/<region>/places.geojson -> properties.entry) and
  are grouped by their K nearest shelters — K distinct entry nodes, the same rule as the app's
  kNearestDestinations — into POST /dispatch-plans (policy "full"; ≤ 200 origins, ≤ 20 destinations,
  ≤ 24 departure offsets, ≤ 4 800 attempts per plan).
* Recorded research-panel origins are sent as individual POST /route-checks with their recorded
  destination, dwell, arrival window, incurred dose and limits (dispatch plans have no incurred dose),
  at every grid offset plus their recorded departure offset. Offsets whose recorded arrival window
  cannot be met are not sent (the API's WINDOW_UNSATISFIABLE rule) and are recorded as skipped.
* For every origin with a checked route, one extra route check with policy "travel_only" at the same
  start, shelter and offset gives the dashed travel-time-only comparison.

Resumable: every finished dispatch plan / route check is saved at once under <out>/.state/. Re-running
the same command continues where it stopped: finished work is reused, in-flight jobs are polled again
(or resubmitted when the API was restarted and no longer knows them). A scenario set whose cache file
already matches the planned requests is skipped. Use --fresh to ignore saved state.

Each scenario set is written to <out>/<region>/<input_compact>.json with provenance (API version, git
commit, host that computed the results, generator.purpose "booth" | "test"), plus <out>/INDEX.json.
Standard library only.

Booth cache vs test data (ARCHITECTURE.md §6): only the real API on the evaluated host (native macOS on
Apple silicon) writes planner/cache/ (purpose "booth"). Any other host, or the MOCK, writes test data to
planner/.test-cache/ by default (never committed or shipped); --out planner/cache is refused for them.

    # booth (on the M5 Pro, real API running):
    python3 planner/scripts/precompute.py --api http://127.0.0.1:8765/v1 \
        --regions uiseong_andong_2025,yeongdeok_2025
    # anywhere else (test data; view with WFG_CACHE_DIR=.test-cache npm run dev):
    python3 planner/scripts/precompute.py --api http://127.0.0.1:8765/v1 --out planner/.test-cache
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PLANNER = Path(__file__).resolve().parents[1]
SCHEMA = 'wfg.planner.cache/1'
DEFAULT_DWELL_S = 120          # required stay of every recorded study mission
MAX_ORIGINS, MAX_DESTINATIONS, MAX_OFFSETS, MAX_ATTEMPTS = 200, 20, 24, 4800
LFS_LIMIT_BYTES = 50 * 1024 * 1024
DONE = ('done', 'failed')


def log(msg: str) -> None:
    print(f'[{dt.datetime.now().strftime("%H:%M:%S")}] {msg}', file=sys.stderr, flush=True)


# ------------------------------------------------------------------------------------------------
# HTTP
# ------------------------------------------------------------------------------------------------

class ApiError(Exception):
    def __init__(self, status: int, body):
        super().__init__(f'HTTP {status}: {str(body)[:300]}')
        self.status, self.body = status, body

    @property
    def code(self) -> str:
        if isinstance(self.body, dict):
            return (self.body.get('error') or {}).get('code') or f'HTTP_{self.status}'
        return f'HTTP_{self.status}'


class Api:
    def __init__(self, base: str, timeout: float = 120.0):
        self.base = base.rstrip('/')
        self.timeout = timeout

    def call(self, method: str, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(body).encode('utf-8')
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        last: Exception | None = None
        for attempt in range(8):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    return json.loads(r.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                raw = e.read().decode('utf-8', 'replace')
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = raw[:800]
                err = ApiError(e.code, payload)
                # 503 BUSY / DATA_UNAVAILABLE and other 5xx: back off and retry; 4xx: caller decides.
                if e.code < 500:
                    raise err
                last = err
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last = e
            time.sleep(min(60, 2 ** attempt))
        raise SystemExit(f'{method} {path} failed after retries: {last}')

    def get(self, path: str) -> dict:
        return self.call('GET', path)

    def post(self, path: str, body: dict) -> dict:
        return self.call('POST', path, body)


# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------

def haversine_m(a, b) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def compact(iso: str) -> str:
    t = dt.datetime.fromisoformat(iso.replace('Z', '+00:00')).astimezone(dt.timezone.utc)
    return t.strftime('%Y%m%dT%H%M%SZ')


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def digest(obj) -> str:
    return sha256_bytes(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode('utf-8'))


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def git_commit() -> str | None:
    try:
        return subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=PLANNER, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def is_mock(health: dict) -> bool:
    return health.get('mode') == 'mock' or health.get('mock') is True


def write_json_atomic(path: Path, obj, compact_json: bool = False) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(obj, ensure_ascii=False, separators=(',', ':')) if compact_json
           else json.dumps(obj, ensure_ascii=False, indent=1) + '\n').encode('utf-8')
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_bytes(raw)
    os.replace(tmp, path)
    return raw


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return default


def load_places(region_id: str) -> list[dict]:
    p = PLANNER / 'public' / 'data' / 'regions' / region_id / 'places.geojson'
    if not p.is_file():
        raise SystemExit(f'Missing {p}; run planner/tools/extract_places.py first')
    features = json.loads(p.read_text(encoding='utf-8'))['features']
    # Optional 임시주거시설 (data.go.kr 15139148, only when it had coordinates): extra candidate destinations.
    extra = p.with_name('temporary_housing.geojson')
    if extra.is_file():
        features += json.loads(extra.read_text(encoding='utf-8'))['features']
    return features


def entry_location(f: dict) -> dict:
    """OSM places start/end at their 진입 지점 node (accepted by the API as node_id)."""
    return {'node_id': f['properties']['entry']['node']}


def grid_offsets(horizon_s: float, step_s: int) -> list[int]:
    offs = list(range(0, int(horizon_s), step_s))
    if len(offs) > MAX_OFFSETS:
        raise SystemExit(f'{len(offs)} offsets exceed the contract limit {MAX_OFFSETS}; use a larger --step-min')
    return offs


# ------------------------------------------------------------------------------------------------
# planning
# ------------------------------------------------------------------------------------------------

def dispatch_requests(region_id: str, sset: dict, places: list[dict], offsets: list[int], k: int) -> list[dict]:
    """OSM origins grouped by identical K-nearest shelter sets (straight-line distance between OSM points)."""
    shelters = [f for f in places if f['properties']['role'] == 'destination' and f['properties']['checkable']]
    origins = [f for f in places if f['properties']['role'] == 'origin' and f['properties']['checkable']]
    if not shelters or not origins:
        return []
    k = max(1, min(k, MAX_DESTINATIONS))
    by_id = {s['properties']['id']: s for s in shelters}
    groups: dict[tuple[str, ...], list[dict]] = {}
    for o in origins:
        oc = o['geometry']['coordinates']
        # Never pair an origin with a shelter that shares its entry node (START_EQUALS_DESTINATION).
        cand = [s for s in shelters if s['properties']['entry']['node'] != o['properties']['entry']['node']]
        # K nearest with K DISTINCT entry nodes: several OSM shelters often share one 진입 지점, and
        # checking the same node twice repeats the same check (same rule as the app).
        near, seen = [], set()
        for s in sorted(cand, key=lambda s: (haversine_m(oc, s['geometry']['coordinates']), s['properties']['id'])):
            node = s['properties']['entry']['node']
            if node in seen:
                continue
            seen.add(node)
            near.append(s)
            if len(near) >= k:
                break
        groups.setdefault(tuple(sorted(s['properties']['id'] for s in near)), []).append(o)
    horizon = float(sset['horizon_s'])
    per_plan = max(1, min(MAX_ORIGINS, MAX_ATTEMPTS // max(1, k * len(offsets))))
    out = []
    for dest_ids, members in sorted(groups.items()):
        members.sort(key=lambda f: f['properties']['id'])
        for i in range(0, len(members), per_plan):
            chunk = members[i:i + per_plan]
            out.append({
                'region': region_id,
                'input_time': sset['input_time'],
                'fire_input': {'type': 'recorded', 'scenario_set_id': sset['scenario_set_id']},
                'origins': [{'id': o['properties']['id'], 'location': entry_location(o)} for o in chunk],
                'destinations': [{'id': d, 'location': entry_location(by_id[d]), 'dwell_s': DEFAULT_DWELL_S,
                                  'window': [0, horizon]} for d in dest_ids],
                'depart_offsets_s': offsets,
                'dwell_s': DEFAULT_DWELL_S,
                'policy': 'full',
                'client_ref': f'planner-precompute:{region_id}:{compact(sset["input_time"])}',
            })
    return out


def research_requests(region_id: str, sset: dict, places: list[dict], offsets: list[int]) -> list[dict]:
    """Individual route checks for recorded research origins; unsatisfiable windows are recorded, not sent."""
    out = []
    for o in places:
        p = o['properties']
        if p['role'] != 'research_origin' or p.get('scenario_set_id') != sset['scenario_set_id']:
            continue
        rec = p['recorded']
        open_s, close_s = rec['destination_window']
        horizon = float(rec.get('horizon_s') or sset['horizon_s'])
        for off in sorted(set(offsets) | {int(rec['depart_offset_s'])}):
            meta = {'origin_id': p['id'], 'destination_id': rec['destination_id'], 'depart_offset_s': off}
            if max(off, open_s) + rec['dwell_s'] > min(close_s, horizon):
                out.append({'meta': {**meta, 'skipped': 'WINDOW_UNSATISFIABLE'}, 'body': None})
                continue
            body = {
                'region': region_id,
                'input_time': sset['input_time'],
                'start': {'node_id': p['entry']['node']},
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
            out.append({'meta': meta, 'body': body})
    return out


# ------------------------------------------------------------------------------------------------
# resumable execution
# ------------------------------------------------------------------------------------------------

class State:
    """Per scenario set: <out>/.state/<region>/<input_compact>/{inflight.json, done/<key>.json}."""

    def __init__(self, root: Path):
        self.root = root
        self.done_dir = root / 'done'
        self.done_dir.mkdir(parents=True, exist_ok=True)
        self.inflight_path = root / 'inflight.json'
        self.inflight: dict = read_json(self.inflight_path, {}) or {}

    def done(self, key: str):
        return read_json(self.done_dir / f'{key}.json')

    def save_done(self, key: str, obj) -> None:
        write_json_atomic(self.done_dir / f'{key}.json', obj, compact_json=True)
        if key in self.inflight:
            del self.inflight[key]
            self.save_inflight()

    def set_inflight(self, key: str, job_id: str, kind: str) -> None:
        self.inflight[key] = {'job_id': job_id, 'kind': kind, 'submitted_at': utc_now()}
        self.save_inflight()

    def save_inflight(self) -> None:
        write_json_atomic(self.inflight_path, self.inflight)


def get_job(api: Api, kind: str, job_id: str) -> dict | None:
    path = ('/dispatch-plans/' if kind == 'dispatch_plan' else '/route-checks/') + job_id
    try:
        return api.get(path)
    except ApiError as e:
        if e.status == 404:
            return None          # the API restarted and forgot the job: resubmit
        raise


def submit(api: Api, kind: str, body: dict) -> str:
    path = '/dispatch-plans' if kind == 'dispatch_plan' else '/route-checks'
    return api.post(path, body)['job_id']


def run_units(api: Api, state: State, units: list[dict], poll_s: float, timeout_s: float, label: str) -> None:
    """units: [{key, kind, body}]. Submits what is not done or in flight, polls until all are done.
    A finished dispatch plan is saved together with every route-check job its attempts reference."""
    pending = []
    for u in units:
        if state.done(u['key']) is not None:
            continue
        inf = state.inflight.get(u['key'])
        if inf and get_job(api, u['kind'], inf['job_id']) is not None:
            pending.append({**u, 'job_id': inf['job_id']})
            continue
        try:
            jid = submit(api, u['kind'], u['body'])
        except ApiError as e:
            state.save_done(u['key'], {'rejected': {'status': e.status, 'code': e.code, 'error': e.body},
                                       'request': u['body'], 'kind': u['kind']})
            log(f'  {label}: request rejected ({e.code})')
            continue
        state.set_inflight(u['key'], jid, u['kind'])
        pending.append({**u, 'job_id': jid})
    total = len(units)
    started, last = time.monotonic(), None
    while pending:
        still = []
        for u in pending:
            job = get_job(api, u['kind'], u['job_id'])
            if job is None:      # forgotten by a restarted API: resubmit once more
                try:
                    u['job_id'] = submit(api, u['kind'], u['body'])
                    state.set_inflight(u['key'], u['job_id'], u['kind'])
                    still.append(u)
                except ApiError as e:
                    state.save_done(u['key'], {'rejected': {'status': e.status, 'code': e.code, 'error': e.body},
                                               'request': u['body'], 'kind': u['kind']})
                continue
            if job['status'] not in DONE:
                still.append(u)
                continue
            record = {'kind': u['kind'], 'job': job}
            if u['kind'] == 'dispatch_plan':
                checks = {}
                for plan in (job.get('result') or {}).get('plans', []):
                    for att in plan.get('attempts', []):
                        cid = att.get('route_check_job_id')
                        if cid and cid not in checks:
                            cj = get_job(api, 'route_check', cid)
                            if cj is not None:
                                checks[cid] = cj
                record['route_checks'] = checks
            state.save_done(u['key'], record)
        pending = still
        n_done = total - len(pending)
        if (n_done, total) != last:
            log(f'  {label}: {n_done}/{total} finished')
            last = (n_done, total)
        if pending:
            if time.monotonic() - started > timeout_s:
                raise SystemExit(f'{len(pending)} {label} jobs unfinished after {timeout_s:.0f} s; re-run to resume')
            time.sleep(poll_s)


def recheck_timeouts(api: Api, state: State, poll_s: float, timeout_s: float) -> int:
    """Re-run attempts that ended unresolved/TIMEOUT one at a time (lower host load), same request."""
    n = 0
    for f in sorted(state.done_dir.glob('*.json')):
        rec = read_json(f)
        if not rec or rec.get('kind') != 'dispatch_plan':
            continue
        for cid, cj in list((rec.get('route_checks') or {}).items()):
            res = cj.get('result') or {}
            if res.get('verdict') != 'unresolved' or res.get('reason_code') != 'TIMEOUT':
                continue
            if cid in (rec.get('rechecks') or {}):
                continue
            req = dict(cj['request'])
            req['client_ref'] = f'planner-precompute:recheck:{cid}'
            try:
                jid = submit(api, 'route_check', req)
            except ApiError as e:
                log(f'  recheck rejected ({e.code})')
                continue
            t0 = time.monotonic()
            while True:
                j = get_job(api, 'route_check', jid)
                if j and j['status'] in DONE:
                    break
                if time.monotonic() - t0 > timeout_s:
                    raise SystemExit('recheck did not finish; re-run to resume')
                time.sleep(poll_s)
            j['recheck_of'] = cid
            rec.setdefault('rechecks', {})[cid] = j
            write_json_atomic(f, rec, compact_json=True)
            n += 1
            log(f'  rechecked {cid}: {(j.get("result") or {}).get("verdict")}')
    return n


def best_checked(plan_records: list[dict], research: list[dict], checks: dict[str, dict],
                 rechecks: dict[str, dict] | None = None) -> dict[str, dict]:
    """Per origin: the attempt shown by default (latest checked offset, earliest arrival, then destination
    id) — the app's rule, with re-checks replacing the attempt they re-ran."""
    rechecks = rechecks or {}
    best = {}
    for rec in plan_records:
        for plan in ((rec.get('job') or {}).get('result') or {}).get('plans', []):
            rows = []
            for att in plan.get('attempts', []):
                cid = att.get('route_check_job_id')
                rj = rechecks.get(cid) if cid else None
                if rj is not None:
                    res = rj.get('result') or {}
                    verdict, arrival, jid = res.get('verdict'), res.get('arrival_s'), rj.get('job_id')
                else:
                    verdict, arrival, jid = att.get('verdict'), att.get('arrival_s'), cid
                if verdict == 'checked_route' and jid in checks:
                    rows.append((-int(att['depart_offset_s']), arrival if arrival is not None else math.inf,
                                 str(att.get('destination_id')), jid))
            if rows:
                best[plan['origin_id']] = checks[min(rows)[3]]
    rows: dict[str, list] = {}
    for r in research:
        jid = r['meta'].get('job_id')
        res = ((checks.get(jid) or {}).get('result') or {}) if jid else {}
        if res.get('verdict') == 'checked_route':
            rows.setdefault(r['meta']['origin_id'], []).append((r['meta']['depart_offset_s'], -(res.get('arrival_s') or 0), jid))
    for oid, rr in rows.items():
        best[oid] = checks[max(rr)[2]]
    return best


# ------------------------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--api', default='http://127.0.0.1:8765/v1')
    ap.add_argument('--regions', default='uiseong_andong_2025,yeongdeok_2025')
    ap.add_argument('--scenario-sets', default='', help='comma-separated input times (compact, e.g. 20250324T090000Z); default all')
    ap.add_argument('--step-min', type=int, default=10, help='departure offset step in minutes')
    ap.add_argument('--k', type=int, default=3, help='candidate shelters per origin (nearest by straight line)')
    ap.add_argument('--out', type=Path, default=None,
                    help='output folder; default planner/cache on the evaluated host (real API, macOS arm64), '
                         'else planner/.test-cache (test data)')
    ap.add_argument('--poll', type=float, default=3.0)
    ap.add_argument('--timeout-h', type=float, default=24.0)
    ap.add_argument('--no-travel-only', action='store_true', help='skip the travel-time-only comparison checks')
    ap.add_argument('--recheck-timeouts', action='store_true',
                    help='after the run, re-check unresolved/TIMEOUT attempts one at a time (same request)')
    ap.add_argument('--fresh', action='store_true', help='ignore saved state and finished cache files')
    ap.add_argument('--allow-mock', action='store_true', help='write a cache from the MOCK API (labelled MOCK)')
    ap.add_argument('--plan-only', action='store_true', help='print the planned check counts and exit')
    a = ap.parse_args()

    api = Api(a.api)
    try:
        health = api.get('/health')
    except ApiError as e:
        raise SystemExit(f'GET /health failed: {e}')
    mode = 'mock' if is_mock(health) else 'live'
    if mode == 'mock' and not a.allow_mock and not a.plan_only:
        raise SystemExit('The API is the MOCK server. Pass --allow-mock to write a MOCK-labelled cache.')
    if health.get('status') != 'ok':
        raise SystemExit(f'API health is {health.get("status")!r}: {health.get("issues")}')
    host = (health.get('provenance') or {}).get('host')
    # Booth cache only from the real API on the evaluated host (native macOS, Apple silicon); the chip
    # (M5 Pro) is not reported by the API, so the test is macOS + arm64.
    plat, mach = str((host or {}).get('platform') or ''), str((host or {}).get('machine') or '')
    booth_host = (plat.startswith('macOS') or 'Darwin' in plat) and mach == 'arm64'
    purpose = 'booth' if (booth_host and mode == 'live') else 'test'
    booth_dir = (PLANNER / 'cache').resolve()
    if a.out is None:
        a.out = PLANNER / 'cache' if purpose == 'booth' else PLANNER / '.test-cache'
        log(f'output {a.out} ({"booth cache" if purpose == "booth" else "TEST DATA — not the booth cache, never commit"})')
    if a.out.resolve() == booth_dir and purpose != 'booth' and not a.plan_only:
        raise SystemExit('Not the evaluation host (real API on native macOS arm64) or the MOCK: the booth cache '
                         'planner/cache must not receive these results. Write them to planner/.test-cache with '
                         '--out planner/.test-cache')
    regions = {r['id']: r for r in api.get('/regions')['regions']}
    wanted = [r.strip() for r in a.regions.split(',') if r.strip()]
    only = {s.strip() for s in a.scenario_sets.split(',') if s.strip()}
    index_path = a.out / 'INDEX.json'
    index = read_json(index_path, []) or []
    commit = git_commit()
    timeout_s = a.timeout_h * 3600
    log(f'API {a.api} · {mode} · api_version {health.get("api_version")} · git {health.get("git_commit")} · '
        f'workers {health.get("workers")} · host {json.dumps(host)}')
    grand = 0

    for region_id in wanted:
        if region_id not in regions:
            raise SystemExit(f'Region {region_id} not served by the API; available: {sorted(regions)}')
        places = load_places(region_id)
        for sset in regions[region_id]['scenario_sets']:
            ic = compact(sset['input_time'])
            if only and ic not in only:
                continue
            t0 = time.monotonic()
            offsets = grid_offsets(sset['horizon_s'], a.step_min * 60)
            plans_req = dispatch_requests(region_id, sset, places, offsets, a.k)
            research = research_requests(region_id, sset, places, offsets)
            n_att = sum(len(r['origins']) * len(r['destinations']) * len(r['depart_offsets_s']) for r in plans_req)
            n_res = sum(1 for r in research if r['body'] is not None)
            n_orig = sum(len(r['origins']) for r in plans_req) + len({r['meta']['origin_id'] for r in research})
            grand += n_att + n_res + (0 if a.no_travel_only else n_orig)
            log(f'{region_id} · {ic} · {sset["scenario_set_id"]}: {len(plans_req)} dispatch plans '
                f'({n_att} checks) + {n_res} research checks + up to {n_orig} travel-only checks')
            if a.plan_only:
                continue
            plan_digest = digest({'plans': plans_req, 'research': [r['body'] for r in research],
                                  'travel_only': not a.no_travel_only, 'api_git': health.get('git_commit')})
            rel = Path(region_id) / f'{ic}.json'
            out = a.out / rel
            existing = read_json(out)
            if existing and existing.get('plan_digest') == plan_digest and not a.fresh and not a.recheck_timeouts:
                log('  cache up to date, skipped')
                continue
            state_root = a.out / '.state' / region_id / ic
            if a.fresh and state_root.exists():
                shutil.rmtree(state_root)
            state = State(state_root)

            units = [{'key': 'plan_' + digest(b)[:24], 'kind': 'dispatch_plan', 'body': b} for b in plans_req]
            units += [{'key': 'rc_' + digest(r['body'])[:24], 'kind': 'route_check', 'body': r['body']}
                      for r in research if r['body'] is not None]
            run_units(api, state, units, a.poll, timeout_s, 'checks')

            if a.recheck_timeouts:
                n = recheck_timeouts(api, state, a.poll, timeout_s)
                log(f'  rechecked {n} TIMEOUT attempts')

            plan_records, checks, rechecks = [], {}, {}
            for u in units:
                rec = state.done(u['key']) or {}
                if u['kind'] == 'dispatch_plan':
                    plan_records.append(rec)
                    checks.update(rec.get('route_checks') or {})
                    # a re-check is stored under its OWN job id with recheck_of = the check it re-ran; the
                    # original stays under its id (the app shows the re-check in that cell)
                    for cid, rj in (rec.get('rechecks') or {}).items():
                        rid = rj.get('job_id') or f'{cid}:recheck'
                        checks[rid] = {**rj, 'recheck_of': cid}
                        rechecks[cid] = checks[rid]
                elif rec.get('job'):
                    checks[rec['job']['job_id']] = rec['job']
            for r in research:
                if r['body'] is not None:
                    rec = state.done('rc_' + digest(r['body'])[:24]) or {}
                    r['meta']['job_id'] = (rec.get('job') or {}).get('job_id')
                    if rec.get('rejected'):
                        r['meta']['skipped'] = rec['rejected']['code']

            travel_only = {}
            if not a.no_travel_only:
                best = best_checked([r for r in plan_records if r.get('job')], research, checks, rechecks)
                to_units = []
                for oid, job in sorted(best.items()):
                    req = {k2: v for k2, v in job['request'].items()
                           if k2 not in ('policy', 'run_independent_check', 'client_ref')}
                    req.update({'policy': 'travel_only', 'client_ref': f'planner-precompute:travel_only:{oid}'})
                    to_units.append({'key': 'to_' + digest(req)[:24], 'kind': 'route_check', 'body': req, 'origin': oid})
                run_units(api, state, to_units, a.poll, timeout_s, 'travel-only checks')
                for u in to_units:
                    rec = state.done(u['key']) or {}
                    if rec.get('job'):
                        travel_only[u['origin']] = rec['job']

            rejected = []
            for u in units:
                rec = state.done(u['key']) or {}
                if rec.get('rejected'):
                    rejected.append({'kind': u['kind'], 'request': u['body'], **rec['rejected']})
            doc = {
                'schema': SCHEMA,
                'region_id': region_id,
                'scenario_set_id': sset['scenario_set_id'],
                'input_time': sset['input_time'],
                'fire_input': {'type': 'recorded', 'scenario_set_id': sset['scenario_set_id']},
                'created_at': utc_now(),
                'api': {'base': a.api, 'mode': mode, 'health': health, 'host': host},
                'planner_commit': commit,
                'plan_digest': plan_digest,
                'generator': {'script': 'planner/scripts/precompute.py', 'python': platform.python_version(),
                              'client_host': f'{platform.system()} {platform.machine()}',
                              'step_min': a.step_min, 'shelters_per_origin': a.k,
                              'default_dwell_s': DEFAULT_DWELL_S, 'origin_location': 'entry node (진입 지점) as node_id',
                              'destinations': 'K nearest shelters with distinct entry nodes',
                              'purpose': purpose,
                              'wall_s_this_invocation': round(time.monotonic() - t0, 1)},
                'requests': plans_req,
                # refused dispatch plans have no job; they are listed in rejected_requests
                'plans': [r['job'] for r in plan_records if r.get('job')],
                'research_checks': [r['meta'] for r in research],
                'rejected_requests': rejected,
                'route_checks': checks,
                'travel_only': travel_only,
            }
            raw = write_json_atomic(out, doc, compact_json=True)
            if len(raw) > LFS_LIMIT_BYTES:
                log(f'  WARNING {out} is {len(raw) / 1e6:.1f} MB: store it with Git LFS or as a Release asset')
            verdicts: dict[str, int] = {}
            for cid, cj in checks.items():
                if cid in rechecks:      # superseded by its re-check (counted there)
                    continue
                res = cj.get('result') or {}
                key = res.get('verdict', 'none') + ('/' + res['reason_code'] if res.get('reason_code') else '')
                verdicts[key] = verdicts.get(key, 0) + 1
            index = [e for e in index if not (e['region_id'] == region_id and e['scenario_set_id'] == sset['scenario_set_id'])]
            index.append({'region_id': region_id, 'scenario_set_id': sset['scenario_set_id'],
                          'input_time': sset['input_time'], 'path': rel.as_posix(), 'api_mode': mode,
                          'purpose': purpose,
                          'api_version': health.get('api_version'), 'host': host,
                          'created_at': doc['created_at'], 'origins': n_orig, 'checks': len(checks),
                          'verdicts': verdicts, 'bytes': len(raw), 'sha256': sha256_bytes(raw)})
            index.sort(key=lambda e: (e['region_id'], e['input_time']))
            write_json_atomic(index_path, index)
            log(f'  wrote {out} ({len(raw) / 1e6:.2f} MB, {n_orig} origins, {len(checks)} checks, {verdicts})')
    if a.plan_only:
        log(f'planned total: {grand} checks')
    else:
        log(f'Updated {index_path}')


if __name__ == '__main__':
    main()
