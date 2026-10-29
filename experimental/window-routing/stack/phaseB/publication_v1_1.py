"""Publication contract for the RDA candidate worker, version 1.1 (fix F-PC1 of the frozen v1 worker).

Pure function used by rda_worker_v1_1.py and by the offline re-derivation test over frozen Phase C records.

Contract:
 * Only a witness whose MANDATORY whole-road check (the integration checker, never the lower-bound prefilter) returned
   CERTIFIED_ADMISSIBLE before the deadline is placed in `result` as a route.
 * For that route `per_member` is the CENTRE-model exposure from the original unchanged centre evaluation
   (routing.core.check_route on the validated graph / hazard / original request: incurred included, dwell per
   exposure_scope), exactly what the baseline router reports. The search mode's own exposure goes to
   `mode_exposure` = {mode, per_member}; the real checker's per-member dose/peak bounds go to `whole_road_bounds`.
 * Otherwise `result` carries no route: a complete relaxation refusal (PROVEN_INFEASIBLE + refusal certificate), a
   pass-through search outcome (AT_ISSUE_FAILURE, DISCONNECTED, INVALID_INPUT, clock-scope UNKNOWN), or
   {status TIMEOUT (a search or time cap was binding) | UNRESOLVED, reason NO_CERTIFIED_WITNESS, legs [], destination
   null, arrival null}, with whole_road_check {NOT_RUN, NO_CERTIFIED_WITNESS}.
 * Every attempted, unpublished witness is listed in `rejected_witnesses` (diagnostic only) with its check outcome and
   `check_kind` = 'integration_whole_road_check' or 'rda_lower_bound_prefilter' (a prefilter outcome is never labelled a
   checker result).
"""
import copy

KIND_CHECKER = 'integration_whole_road_check'
KIND_PREFILTER = 'rda_lower_bound_prefilter (outward lower road bound; NOT the integration whole-road checker)'
PASS_THROUGH = ('AT_ISSUE_FAILURE', 'DISCONNECTED', 'INVALID_INPUT')
TIME_REASONS = ('WALL_CAP', 'NO_REMAINING_COMPLETE_BUDGET', 'CHECK_STARTED_NOT_COMPLETED', 'CHECK_INITIALIZATION_NOT_COMPLETED', 'RSS_LIMIT')


def whole_road_bounds(check):
    """Per-member dose/peak bounds reported by the REAL checker (adaptive fallback preferred), else None."""
    if not isinstance(check, dict):
        return None
    ad = check.get('adaptive_fallback')
    if isinstance(ad, dict) and isinstance(ad.get('per_member'), dict) and ad['per_member']:
        src, pm = 'adaptive_fallback', ad['per_member']
    else:
        rad = check.get('radiation')
        if not (isinstance(rad, dict) and isinstance(rad.get('per_member'), list) and rad['per_member']):
            return None
        src, pm = 'radiation', {r['id']: r for r in rad['per_member']}
    keys = ('dose_lower_kj_m2', 'dose_upper_kj_m2', 'peak_lower_kw_m2', 'peak_upper_kw_m2')
    return {'source': src, 'status': check.get('status'),
            'per_member': {k: {kk: v.get(kk) for kk in keys} for k, v in pm.items()}}


def route_of(search):
    if not isinstance(search, dict):
        return None, None
    if search.get('destination') is not None:
        return search, 'PRIMARY'
    inc = search.get('checked_incumbent')
    if isinstance(inc, dict) and inc.get('destination') is not None:
        return inc, 'CHECKED_TIMEOUT_INCUMBENT'
    return None, None


def publish(witnesses, *, published_index, refusal, lower_bounds, centre_fn, time_capped):
    """witnesses: stage-ordered list of dicts {stage, mode, search, check, check_kind}; search may be a full search
    result or (offline) a summary; check is None when no check ran. Returns dict(result, whole_road_check,
    optimality_certificate, rejected_witnesses, returned_witness_role)."""
    rejected = []
    for i, w in enumerate(witnesses):
        route, role = route_of(w.get('search'))
        if i == published_index or (route is None and w.get('check') is None):
            continue
        chk = w.get('check') or {}
        rejected.append({'stage': w['stage'], 'mode': w['mode'], 'role': role,
                         'search_status': (w.get('search') or {}).get('status'),
                         'arrival': None if route is None else route.get('arrival'),
                         'destination': None if route is None else route.get('destination'),
                         'legs': None if route is None else route.get('legs'),
                         'mode_exposure': None if route is None else {'mode': w['mode'], 'per_member': route.get('per_member')},
                         'check_kind': w.get('check_kind'), 'check_status': chk.get('status'), 'check_reason': chk.get('reason'),
                         'prefilter': chk.get('prefilter') if w.get('check_kind') == KIND_PREFILTER else None,
                         'whole_road_bounds': whole_road_bounds(chk) if w.get('check_kind') == KIND_CHECKER else None,
                         'published': False, 'note': 'diagnostic only; not a journey'})
    best_lb = max((a for a, _ in lower_bounds), default=None)
    if published_index is not None:
        w = witnesses[published_index]
        assert w.get('check_kind') == KIND_CHECKER and (w.get('check') or {}).get('status') == 'CERTIFIED_ADMISSIBLE'
        result = copy.deepcopy(w['search'])
        route, role = route_of(result)
        opt = None
        if best_lb is not None and role == 'PRIMARY' and route['arrival'] == best_lb:
            kinds = sorted(set(k for a, k in lower_bounds if a == best_lb))
            opt = {'lower_bound_arrival': best_lb, 'relaxation_kind': '+'.join(kinds), 'complete': True,
                   'stage_of_route': w['stage'], 'provenance': 'rda_worker completed relaxation(s)',
                   'mathematics': 'MATH_PROOF.md obligation 7 (sandwich)'}
        centre = centre_fn(route)
        # Status vocabulary (v1.1, D7 tightened): `status` keeps the router's CENTRE-model meaning. A route found by a
        # mode search and certified in the whole-road model is never presented as a centre optimum: it is CHECKED_ROUTE
        # when the unchanged centre evaluation also admits it, else ROAD_CERTIFIED_CENTRE_INFEASIBLE_ROUTE. Full-model
        # optimality is carried ONLY by the optimality certificate (the decision maps it to FULL_OPTIMUM_PROVEN).
        result['mode_raw_status'] = result.get('mode_raw_status') or result.get('status')
        result['mode_raw_solver_status'] = result.get('solver_status')
        result['status'] = 'CHECKED_ROUTE' if centre.get('ok') else 'ROAD_CERTIFIED_CENTRE_INFEASIBLE_ROUTE'
        result['solver_status'] = 'WHOLE_ROAD_CERTIFIED_MODE_%s' % str(w['mode']).upper()
        result['reason'] = ('WHOLE_ROAD_CERTIFIED_FULL_MODEL_OPTIMUM_BY_CERTIFICATE' if opt is not None
                            else 'WHOLE_ROAD_CERTIFIED_NO_OPTIMALITY_CLAIM')
        route['mode_exposure'] = {'mode': w['mode'], 'per_member': route.get('per_member'),
                                  'scope': 'exposure of the search mode that found the route (not the centre model)'}
        route['per_member'] = centre['per_member']
        route['per_member_scope'] = 'centre model: routing.core.check_route (unchanged centre evaluation), incurred included, dwell per exposure_scope'
        route['centre_check'] = {k: centre.get(k) for k in ('ok', 'status', 'codes')}
        route['whole_road_bounds'] = whole_road_bounds(w['check'])
        if route is not result:                     # checked timeout incumbent: top level carries no route metrics
            result['per_member'] = {}
        if 'checker' in result and route is result:
            result['mode_checker'] = result.pop('checker')
        result['published_stage'] = w['stage']
        return {'result': result, 'whole_road_check': w['check'], 'optimality_certificate': opt,
                'rejected_witnesses': rejected, 'returned_witness_role': role}
    if refusal is not None:
        src = next(w for w in witnesses if w['stage'] == refusal['stage'] and (w.get('search') or {}).get('status') == 'PROVEN_INFEASIBLE')
        result = copy.deepcopy(src['search'])
        result['published_stage'] = 'REFUSAL:' + refusal['stage']
        return {'result': result, 'whole_road_check': {'status': 'NOT_RUN', 'reason': 'NO_SOLVER_WITNESS'},
                'optimality_certificate': None, 'rejected_witnesses': rejected, 'returned_witness_role': None}
    passthru = [w for w in witnesses if route_of(w.get('search'))[0] is None and
                ((w.get('search') or {}).get('status') in PASS_THROUGH or (w.get('search') or {}).get('reason') == 'EXACT_CLOCK_SCOPE_UNSUPPORTED')]
    if passthru:
        result = copy.deepcopy(passthru[-1]['search']); result['published_stage'] = None
        return {'result': result, 'whole_road_check': {'status': 'NOT_RUN', 'reason': 'NO_SOLVER_WITNESS'},
                'optimality_certificate': None, 'rejected_witnesses': rejected, 'returned_witness_role': None}
    statuses = [(w.get('search') or {}).get('status') for w in witnesses]
    timed = bool(time_capped) or 'TIMEOUT' in statuses or any(
        w.get('check_kind') == KIND_CHECKER and str((w.get('check') or {}).get('reason') or '').startswith(TIME_REASONS) for w in witnesses)
    result = {'status': 'TIMEOUT' if timed else 'UNRESOLVED', 'reason': 'NO_CERTIFIED_WITNESS',
              'solver_status': 'INCOMPLETE_CAP' if timed else 'NO_CERTIFIED_WITNESS', 'legs': [], 'destination': None,
              'arrival': None, 'per_member': {}, 'metrics': {}, 'published_stage': None,
              'stage_statuses': [{'stage': w['stage'], 'mode': w['mode'], 'status': s} for w, s in zip(witnesses, statuses)],
              'note': 'no witness was certified by the mandatory whole-road check; attempted witnesses are listed in rejected_witnesses'}
    return {'result': result, 'whole_road_check': {'status': 'NOT_RUN', 'reason': 'NO_CERTIFIED_WITNESS'},
            'optimality_certificate': None, 'rejected_witnesses': rejected, 'returned_witness_role': None}
