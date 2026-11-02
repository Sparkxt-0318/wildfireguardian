"""Path A: an exact Python port of the planner's own verdict and deadline rules (standard library only).

Replicated source (repository commit 0cd95db2, files unchanged by this package):

* ``planner/src/domain/plan.ts``
  - ``combineVerdicts`` / ``cellVerdict``  (lines 106-115): a departure offset is ``checked_route`` if ANY candidate
    destination is checked, ``model_no_route`` only if EVERY attempted destination is ``model_no_route``, otherwise
    ``unresolved``; no attempt at all is ``unresolved``.
  - ``bestCheckedAttempt`` (118-126): earliest arrival, ties by destination id.
  - ``buildSweep`` (132-147): one cell per requested / attempted / skipped offset.
  - ``isWindowSkip`` (150-152), ``latestSafeDeparture`` (155-161): 출발 마감 (leave-by deadline) = the latest offset
    whose cell is ``checked_route``; unresolved and skipped cells never count.
  - ``contiguousSafeDeparture`` (169-178): walk the offsets from the earliest, leaving out only "시간창 밖"
    (``window_unsatisfiable``) cells; stop at the first cell that is not ``checked_route``.
  - ``planFromAttempts`` (194-220), ``unresolvedPlan`` (223-242).
* ``planner/src/api/adapter.ts`` - ``num``/``str`` (50-56), ``adaptVerdict`` (59-61: unknown strings are unresolved),
  ``adaptAttempt`` (219-232), ``adaptOriginPlan`` (234-239), ``adaptDispatchJob`` (255-280), ``adaptRouteJob``
  (334-412), ``attemptFromRoute`` (415-427).
* ``planner/src/api/cache.ts`` - ``planJobs`` (23-25) and ``cacheToModel`` (114-291): route-check maps and re-checks
  (120-145: a re-check replaces the attempt it re-ran), dispatch plans (148-178), refused dispatch requests (181-194),
  research origins (196-248: only offsets precompute skipped as WINDOW_UNSATISFIABLE become "시간창 밖" cells; a
  request the API refused is an unresolved attempt), travel-only comparisons (250-258: kept only when their departure
  equals the origin's best checked attempt), ``researchKey``/``refusedResearchKeys`` (301-321).
* ``planner/src/state/controller.ts`` ``completePlans`` (494-501) and the cache branch of ``selectScenario``
  (559-565): every scenario origin without a result is an unresolved plan (``not_checkable`` / ``not_computed``).
* ``planner/src/data/staticData.ts`` ``scenarioOrigins`` (179-183) and the place adapter (120-121:
  ``checkable = p.checkable !== false``, ``vulnerable = p.vulnerable === true``).
* ``planner/src/components/LeftPanel.tsx`` ``glyphKind`` (234-238): origin type = village (not vulnerable) or
  facility (vulnerable: nursing_home / social_facility); research and not-checkable origins are separate.

JavaScript details reproduced: ``num`` accepts only finite numbers (not booleans), ``str`` only non-empty strings;
``job.result`` is read only when ``status == 'done'``; JS truthiness of objects is used where the TypeScript relies on
it (an empty object is truthy). The single behaviour that cannot be reproduced byte-for-byte - the tie-break of
``destinationId.localeCompare`` between two checked attempts with exactly equal arrival - is replaced by code-point
order and every such tie is counted (``tie_breaks``); the analysis requires that count to be zero.
"""
from __future__ import annotations

import math

CHECKED, NO_ROUTE, UNRESOLVED = 'checked_route', 'model_no_route', 'unresolved'
VERDICTS = (CHECKED, NO_ROUTE, UNRESOLVED)
WINDOW_UNSATISFIABLE = 'window_unsatisfiable'


# ------------------------------------------------------------------------------------------------ JS value helpers

def js_num(v):
    """adapter.ts / cache.ts ``num``: finite numbers only (JSON booleans are not numbers in JS)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return v if math.isfinite(v) else None


def js_str(v):
    """adapter.ts / cache.ts ``str``: non-empty strings only."""
    return v if isinstance(v, str) and len(v) > 0 else None


def js_number(v):
    """``Number(x)`` restricted to the numeric values the cache holds; anything else is rejected, never guessed."""
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise TypeError(f'expected a finite number, got {v!r}')
    return int(v) if float(v).is_integer() else v


def js_truthy_obj(v) -> bool:
    """JS truthiness for a JSON value used as an object (``{}`` and ``[]`` are truthy in JS)."""
    return v is not None and v is not False and v != 0 and v != ''


# ------------------------------------------------------------------------------------------------ plan.ts

def adapt_verdict(v) -> str:
    return v if v in VERDICTS else UNRESOLVED


def combine_verdicts(verdicts: list[str]) -> str:
    if len(verdicts) == 0:
        return UNRESOLVED
    if any(v == CHECKED for v in verdicts):
        return CHECKED
    if all(v == NO_ROUTE for v in verdicts):
        return NO_ROUTE
    return UNRESOLVED


def cell_verdict(attempts: list[dict]) -> str:
    return combine_verdicts([a['verdict'] for a in attempts])


class TieCounter:
    """Counts equal-arrival ties among checked attempts (where localeCompare and code-point order could differ)."""
    n = 0


def best_checked_attempt(attempts: list[dict]):
    checked = [a for a in attempts if a['verdict'] == CHECKED]
    key = lambda a: (math.inf if a['arrival_s'] is None else a['arrival_s'])  # noqa: E731
    checked.sort(key=lambda a: (key(a), a['destination_id']))
    if len(checked) >= 2 and key(checked[0]) == key(checked[1]) and checked[0]['destination_id'] != checked[1]['destination_id']:
        TieCounter.n += 1
    return checked[0] if checked else None


def build_sweep(offsets_s, attempts: list[dict], skipped: dict | None = None) -> list[dict]:
    skipped = skipped or {}
    offsets = set(offsets_s)
    offsets.update(a['offset_s'] for a in attempts)
    offsets.update(skipped.keys())
    sweep = []
    for off in sorted(offsets):
        here = [a for a in attempts if a['offset_s'] == off]
        cell = {'offset_s': off, 'verdict': cell_verdict(here), 'attempts': here}
        best = best_checked_attempt(here)
        if best is not None:
            cell['best'] = best
        skip = skipped.get(off)
        if skip and len(here) == 0:
            cell['skipped'] = skip
        sweep.append(cell)
    return sweep


def is_window_skip(cell: dict) -> bool:
    return cell.get('skipped') == WINDOW_UNSATISFIABLE


def latest_safe_departure(sweep: list[dict]):
    latest = None
    for c in sweep:
        if c['verdict'] == CHECKED and (latest is None or c['offset_s'] > latest):
            latest = c['offset_s']
    return latest


def contiguous_safe_departure(sweep: list[dict]):
    cells = sorted((c for c in sweep if not is_window_skip(c)), key=lambda c: c['offset_s'])
    latest = None
    for c in cells:
        if c['verdict'] != CHECKED:
            break
        latest = c['offset_s']
    return latest


def plan_from_attempts(origin_id: str, offsets_s, attempts: list[dict], skipped: dict | None = None) -> dict:
    sweep = build_sweep(offsets_s, attempts, skipped or {})
    latest = latest_safe_departure(sweep)
    plan = {'origin_id': origin_id, 'latest_safe_departure_s': latest,
            'contiguous_safe_departure_s': contiguous_safe_departure(sweep),
            'best_verdict': combine_verdicts([a['verdict'] for a in attempts]), 'sweep': sweep, 'note': None}
    if latest is not None:
        cell = next((c for c in sweep if c['offset_s'] == latest), None)
        if cell is not None and cell.get('best') is not None:
            plan['best'] = cell['best']
    return plan


def unresolved_plan(origin_id: str, offsets_s, note: str) -> dict:
    sweep = [{'offset_s': o, 'verdict': UNRESOLVED, 'attempts': []} for o in sorted(set(offsets_s))]
    return {'origin_id': origin_id, 'latest_safe_departure_s': None, 'contiguous_safe_departure_s': None,
            'best_verdict': UNRESOLVED, 'sweep': sweep, 'note': note}


def grid_offsets(horizon_s: float, step_min: int) -> list[int]:
    """plan.ts gridOffsets (57-62)."""
    step = max(1, round(step_min * 60))
    out, t = [], 0
    while t < horizon_s:
        out.append(t)
        t += step
    return out


def departure_offsets(horizon_s: float, step_min: int, extra_s) -> list[int]:
    """plan.ts departureOffsets (68-74)."""
    s = set(grid_offsets(horizon_s, step_min))
    for x in extra_s:
        if isinstance(x, (int, float)) and math.isfinite(x) and 0 <= x < horizon_s:
            s.add(int(round(x)))
    return sorted(s)


# ------------------------------------------------------------------------------------------------ adapter.ts

def adapt_attempt(a: dict) -> dict:
    verdict = adapt_verdict(a.get('verdict'))
    return {'offset_s': js_number(a['depart_offset_s']), 'destination_id': str(a['destination_id']),
            'verdict': verdict, 'arrival_s': js_num(a.get('arrival_s')), 'compute_s': js_num(a.get('compute_s')),
            'job_id': js_str(a.get('route_check_job_id')),
            'reason_code': js_str(a.get('reason_code')) if verdict == UNRESOLVED else None,
            'raw_status': js_str(a.get('raw_status')), 'recheck_of': None}


def adapt_route_job(job: dict) -> dict:
    status = job.get('status')
    res = job.get('result') if status == 'done' else None
    has_res = js_truthy_obj(res)
    verdict = adapt_verdict(res.get('verdict')) if has_res else UNRESOLVED
    req = job.get('request') if js_truthy_obj(job.get('request')) else {}
    if has_res and verdict == UNRESOLVED:
        reason = js_str(res.get('reason_code'))
    elif status == 'failed':
        reason = js_str((job.get('error') or {}).get('code'))
    else:
        reason = None
    return {'job_id': job.get('job_id'), 'status': status, 'verdict': verdict, 'reason_code': reason,
            'raw_status': js_str(res.get('raw_status')) if has_res else None,
            'arrival_s': js_num(res.get('arrival_s')) if has_res else None,
            'compute_s': js_num(res.get('compute_s')) if has_res else None,
            'depart_offset_s': js_num(req.get('depart_offset_s'))}


def attempt_from_route(d: dict, destination_id: str, offset_s) -> dict:
    return {'offset_s': offset_s, 'destination_id': destination_id,
            'verdict': d['verdict'] if d['status'] == 'done' else UNRESOLVED,
            'arrival_s': d['arrival_s'] if d['verdict'] == CHECKED else None,
            'compute_s': d['compute_s'], 'job_id': d['job_id'],
            'reason_code': d['reason_code'] if (d['verdict'] == UNRESOLVED or d['status'] != 'done') else None,
            'raw_status': d['raw_status'], 'recheck_of': None}


def adapt_origin_plan(p: dict, offsets_s) -> dict:
    attempts = [adapt_attempt(a) for a in (p.get('attempts') or [])]
    return plan_from_attempts(p['origin_id'], offsets_s, attempts)


def adapt_dispatch_job(job: dict) -> dict:
    req = job.get('request') if js_truthy_obj(job.get('request')) else {}
    dos = req.get('depart_offsets_s')
    offsets = sorted({js_number(x) for x in dos}) if isinstance(dos, list) else []
    result = job.get('result') if job.get('status') == 'done' else None
    result = result if js_truthy_obj(result) else {}
    plans = [adapt_origin_plan(p, offsets) for p in (result.get('plans') or [])]
    rejected = [{'origin_id': r['origin_id'], 'code': str((r.get('error') or {}).get('code') or 'REJECTED')}
                for r in (result.get('rejected_origins') or [])]
    err = job.get('error')
    return {'job_id': job.get('job_id'), 'status': job.get('status'), 'plans': plans, 'rejected': rejected,
            'error': {'code': str(err.get('code')), 'message': str(err.get('message'))} if js_truthy_obj(err) else None}


# ------------------------------------------------------------------------------------------------ cache.ts

def research_key(origin_id: str, offset_s) -> str:
    return f'{origin_id}|{offset_s}'


def refused_research_keys(rejected: list) -> set:
    out = set()
    for r in rejected:
        if r.get('kind') != 'route_check':
            continue
        req = r.get('request') or {}
        cref = req.get('client_ref')
        ref = cref[len('planner-precompute:'):] if isinstance(cref, str) and cref.startswith('planner-precompute:') else None
        origin_id = r.get('origin_id') if r.get('origin_id') is not None else ref
        off = r.get('depart_offset_s')
        if off is None:
            off = req.get('depart_offset_s') if isinstance(req.get('depart_offset_s'), (int, float)) else None
        if origin_id and off is not None:
            out.add(research_key(origin_id, js_number(off)))
    return out


def cache_to_model(doc: dict) -> dict:
    """cache.ts cacheToModel: plans by origin id, travel-only comparisons, dispatch offsets, route-check maps."""
    plans: dict[str, dict] = {}
    jobs: dict[str, dict] = {}
    rechecks: dict[str, dict] = {}
    for key, job in (doc.get('route_checks') or {}).items():
        if not job or not isinstance(job, dict):
            continue
        of = job.get('recheck_of') if js_str(job.get('recheck_of')) else None
        if of:
            rechecks[of] = job
            if job.get('job_id'):
                jobs[job['job_id']] = job
            if key != of and key not in jobs:
                jobs[key] = job
        else:
            if key not in jobs:
                jobs[key] = job
            if job.get('job_id') and job['job_id'] not in jobs:
                jobs[job['job_id']] = job

    def recheck_attempt(a: dict) -> dict:
        rj = rechecks.get(a['job_id']) if a['job_id'] else None
        if rj is None:
            return a
        return {**attempt_from_route(adapt_route_job(rj), a['destination_id'], a['offset_s']), 'recheck_of': a['job_id']}

    def with_rechecks(p: dict) -> dict:
        attempts = [a for c in p['sweep'] for a in c['attempts']]
        if not any(a['job_id'] and a['job_id'] in rechecks for a in attempts):
            return p
        return plan_from_attempts(p['origin_id'], [c['offset_s'] for c in p['sweep']], [recheck_attempt(a) for a in attempts])

    plan_jobs = [j for j in (doc.get('plans') or []) if j and isinstance(j, dict)]
    offsets: set = set()
    for req in doc.get('requests') or []:
        for o in req.get('depart_offsets_s') or []:
            offsets.add(js_number(o))
    offsets_s = sorted(offsets)
    for job in plan_jobs:
        a = adapt_dispatch_job(job)
        for p in a['plans']:
            plans[p['origin_id']] = with_rechecks(p)
        req = job.get('request') or {}
        req_offsets = [js_number(x) for x in req['depart_offsets_s']] if isinstance(req.get('depart_offsets_s'), list) else offsets_s
        for r in a['rejected']:
            plan = unresolved_plan(r['origin_id'], req_offsets, 'rejected')
            plan['reject_reason'] = r['code']
            plans[r['origin_id']] = plan
        if job.get('status') == 'failed':
            failed_origins = req.get('origins') if isinstance(req.get('origins'), list) else []
            for o in failed_origins:
                if o['id'] in plans:
                    continue
                plan = unresolved_plan(o['id'], req_offsets, 'rejected')
                plan['reject_reason'] = (a['error'] or {}).get('code', 'JOB_FAILED')
                plans[o['id']] = plan
    for rej in doc.get('rejected_requests') or []:
        if rej.get('kind') != 'dispatch_plan':
            continue
        req_origins = (rej.get('request') or {}).get('origins')
        ids = rej['origins'] if isinstance(rej.get('origins'), list) else (
            [str(o.get('id')) for o in req_origins] if isinstance(req_origins, list) else [])
        ro = (rej.get('request') or {}).get('depart_offsets_s')
        offs = [js_number(x) for x in ro] if isinstance(ro, list) else offsets_s
        for oid in ids:
            if oid in plans:
                continue
            plan = unresolved_plan(oid, offs, 'rejected')
            plan['reject_reason'] = str(rej.get('code') or 'REJECTED')
            plans[oid] = plan

    # research origins: individual route checks per offset (insertion order = JS Map order)
    refused = refused_research_keys(doc.get('rejected_requests') or [])
    slots: dict[str, dict] = {}
    for rc in doc.get('research_checks') or []:
        slot = slots.setdefault(rc['origin_id'], {'attempts': [], 'offsets': [], 'skipped': {}, 'sent': 0,
                                                  'refused': 0, 'first_refused': None})
        off = js_number(rc['depart_offset_s'])
        slot['offsets'].append(off)
        jid = rc.get('job_id') if js_str(rc.get('job_id')) else None
        job = None
        if jid:
            job = jobs.get(jid)
            if job is None:
                job = rechecks.get(jid)
        if job is not None:
            slot['sent'] += 1
            rj = rechecks.get(jid) if jid else None
            d = adapt_route_job(rj if rj is not None else job)
            att = attempt_from_route(d, rc['destination_id'], off)
            slot['attempts'].append({**att, 'recheck_of': jid} if rj is not None else att)
        elif rc.get('skipped') in ('WINDOW_UNSATISFIABLE', WINDOW_UNSATISFIABLE) and research_key(rc['origin_id'], off) not in refused:
            slot['skipped'][off] = WINDOW_UNSATISFIABLE
        elif rc.get('skipped'):
            slot['sent'] += 1
            slot['refused'] += 1
            slot['first_refused'] = slot['first_refused'] or rc['skipped']
            slot['attempts'].append({'offset_s': off, 'destination_id': rc['destination_id'], 'verdict': UNRESOLVED,
                                     'arrival_s': None, 'compute_s': None, 'job_id': None,
                                     'reason_code': rc['skipped'], 'raw_status': None, 'recheck_of': None})
        else:
            slot['sent'] += 1
            slot['attempts'].append({'offset_s': off, 'destination_id': rc['destination_id'], 'verdict': UNRESOLVED,
                                     'arrival_s': None, 'compute_s': None, 'job_id': None, 'reason_code': None,
                                     'raw_status': None, 'recheck_of': None})
    for origin_id, slot in slots.items():
        plan = plan_from_attempts(origin_id, slot['offsets'], slot['attempts'], slot['skipped'])
        if slot['sent'] > 0 and slot['refused'] == slot['sent']:
            plan['note'] = 'rejected'
            plan['reject_reason'] = str(slot['first_refused'] or 'REJECTED')
        plans[origin_id] = plan

    travel_only = {}
    for origin_id, job in (doc.get('travel_only') or {}).items():
        if not job or not isinstance(job, dict):
            continue
        d = adapt_route_job(job)
        best = (plans.get(origin_id) or {}).get('best')
        if best is not None and d['depart_offset_s'] is not None and d['depart_offset_s'] != best['offset_s']:
            continue
        travel_only[origin_id] = {'detail': d, 'job': job}
    return {'plans': plans, 'travel_only': travel_only, 'offsets_s': offsets_s, 'jobs': jobs, 'rechecks': rechecks}


# ------------------------------------------------------------------------------------------------ controller / places

def place_from_properties(p: dict) -> dict:
    """staticData.ts place adapter (the fields the analysis reads)."""
    return {'id': p['id'], 'role': p['role'], 'category': p.get('category'), 'name': p.get('name'),
            'name_en': p.get('name_en'),
            'checkable': p.get('checkable') is not False, 'vulnerable': p.get('vulnerable') is True,
            'scenario_set_id': p.get('scenario_set_id'), 'recorded': p.get('recorded'),
            'entry_node': (p.get('entry') or {}).get('node')}


def scenario_origins(places: list[dict], scenario_set_id: str) -> list[dict]:
    return [p for p in places if p['role'] == 'origin' or
            (p['role'] == 'research_origin' and p['scenario_set_id'] == scenario_set_id)]


def origin_type(place: dict) -> str:
    """LeftPanel.tsx glyphKind: not_checkable first, then research, then facility (vulnerable) / village."""
    if not place['checkable']:
        return 'not_checkable'
    if place['role'] == 'research_origin':
        return 'research'
    return 'care_facility' if place['vulnerable'] else 'village'


def complete_plans(model: dict, origins: list[dict], horizon_s: float, step_min: int) -> dict:
    """controller.ts completePlans with the cache branch's offsetsFor (559-565)."""
    out = dict(model['plans'])
    for o in origins:
        if o['id'] in out:
            continue
        if o['role'] == 'research_origin':
            rec = o.get('recorded') or {}
            offs = departure_offsets(horizon_s, step_min, [rec['depart_offset_s']] if rec else [])
        else:
            offs = model['offsets_s'] if model['offsets_s'] else grid_offsets(horizon_s, step_min)
        out[o['id']] = unresolved_plan(o['id'], offs, 'not_computed' if o['checkable'] else 'not_checkable')
    return out
