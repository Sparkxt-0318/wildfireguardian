"""Synthetic, hand-computed cases for the port of the planner rules, plus a seeded property test against the API's
own aggregation code (api/dispatch.py, loaded read-only)."""
import random

import pytest

from wfg_impact import api_rules, planner_rules as pr

CH, NR, UN = pr.CHECKED, pr.NO_ROUTE, pr.UNRESOLVED


def att(off, dest, verdict, arrival=None, job=None):
    return {'offset_s': off, 'destination_id': dest, 'verdict': verdict, 'arrival_s': arrival, 'compute_s': None,
            'job_id': job, 'reason_code': None, 'raw_status': None, 'recheck_of': None}


# ------------------------------------------------------------------------------------------------ verdict rules

@pytest.mark.parametrize('verdicts, expected', [
    ([], UN), ([CH], CH), ([NR, CH, UN], CH), ([NR, NR, NR], NR), ([NR, UN], UN), ([UN, UN], UN)])
def test_combine_verdicts(verdicts, expected):
    assert pr.combine_verdicts(verdicts) == expected


def test_unknown_verdict_strings_are_unresolved():
    assert pr.adapt_verdict('safe') == UN
    assert pr.adapt_verdict(None) == UN
    assert pr.adapt_verdict('checked_route') == CH


def test_js_helpers_match_typescript_num_and_str():
    assert pr.js_num(True) is None and pr.js_num(float('inf')) is None and pr.js_num(3) == 3
    assert pr.js_str('') is None and pr.js_str('x') == 'x' and pr.js_str(5) is None
    assert pr.js_number(3000.0) == 3000 and isinstance(pr.js_number(3000.0), int)
    with pytest.raises(TypeError):
        pr.js_number(None)            # Number(null) would be 0 in JS: never guessed


# ------------------------------------------------------------------------------------------------ deadlines

def test_gap_latest_vs_contiguous():
    # +0 checked, +10 refused everywhere, +20 checked at one of two shelters
    a = [att(0, 'A', CH, 300), att(0, 'B', NR), att(600, 'A', NR), att(600, 'B', NR),
         att(1200, 'A', UN), att(1200, 'B', CH, 1500)]
    p = pr.plan_from_attempts('o', [0, 600, 1200], a)
    assert [c['verdict'] for c in p['sweep']] == [CH, NR, CH]
    assert p['latest_safe_departure_s'] == 1200          # 출발 마감 = latest checked offset
    assert p['contiguous_safe_departure_s'] == 0         # stops at the first unchecked offset
    assert p['best_verdict'] == CH
    assert p['best']['destination_id'] == 'B' and p['best']['offset_s'] == 1200


def test_unresolved_never_counts_and_empty_cell_breaks_contiguity():
    a = [att(0, 'A', CH, 100), att(1200, 'A', CH, 1300)]          # offset 600 requested but never attempted
    p = pr.plan_from_attempts('o', [0, 600, 1200], a)
    assert p['sweep'][1]['verdict'] == UN and p['sweep'][1]['attempts'] == []
    assert p['latest_safe_departure_s'] == 1200 and p['contiguous_safe_departure_s'] == 0
    q = pr.plan_from_attempts('o', [0, 600], [att(0, 'A', UN), att(600, 'A', UN)])
    assert q['latest_safe_departure_s'] is None and q['best_verdict'] == UN


def test_window_unsatisfiable_is_its_own_category_and_left_out_of_contiguity():
    a = [att(0, 'R', CH, 900), att(600, 'R', CH, 1500), att(1800, 'R', CH, 2500)]
    p = pr.plan_from_attempts('r', [0, 600, 1200, 1800], a, {1200: pr.WINDOW_UNSATISFIABLE})
    cells = {c['offset_s']: c for c in p['sweep']}
    assert pr.is_window_skip(cells[1200]) and cells[1200]['verdict'] == UN and cells[1200]['attempts'] == []
    # "시간창 밖" is left out of the contiguous walk, so the run continues to +30 min
    assert p['latest_safe_departure_s'] == 1800 and p['contiguous_safe_departure_s'] == 1800
    # a request the API refused is an unresolved attempt, not a window skip: it breaks the run
    refused = dict(att(1200, 'R', UN), reason_code='WINDOW_UNSATISFIABLE')
    q = pr.plan_from_attempts('r', [0, 600, 1200, 1800], a + [refused], {})
    assert q['latest_safe_departure_s'] == 1800 and q['contiguous_safe_departure_s'] == 600
    # a skip entry at an offset that does have attempts is not a skip cell (plan.ts 143-144)
    s = pr.plan_from_attempts('r', [0], [att(0, 'R', NR)], {0: pr.WINDOW_UNSATISFIABLE})
    assert not pr.is_window_skip(s['sweep'][0])


def test_window_rule_matches_planner_formula():
    # plan.ts windowUnsatisfiable: max(offset, open) + dwell > min(close, horizon)
    def unsat(off, w, dwell, horizon):
        return max(off, w[0]) + dwell > min(w[1], horizon)
    assert unsat(3000, (0, 2619), 120, 3600) and not unsat(2400, (0, 2619), 120, 3600)


def test_best_checked_attempt_earliest_arrival_then_destination_id():
    pr.TieCounter.n = 0
    best = pr.best_checked_attempt([att(0, 'b', CH, 500), att(0, 'a', CH, 700), att(0, 'c', NR)])
    assert best['destination_id'] == 'b' and pr.TieCounter.n == 0
    best = pr.best_checked_attempt([att(0, 'b', CH, 500), att(0, 'a', CH, 500)])
    assert best['destination_id'] == 'a' and pr.TieCounter.n == 1     # ties are counted (localeCompare caveat)


# ------------------------------------------------------------------------------------------------ cache_to_model

def _job(jid, verdict, arrival=None, offset=0, status='done', recheck_of=None, reason=None):
    j = {'job_id': jid, 'status': status, 'request': {'depart_offset_s': offset},
         'result': {'verdict': verdict, 'arrival_s': arrival, 'reason_code': reason}}
    if recheck_of:
        j['recheck_of'] = recheck_of
    return j


def synthetic_doc():
    attempts = lambda oid, rows: [{'destination_id': d, 'depart_offset_s': o, 'verdict': v, 'arrival_s': a,  # noqa: E731
                                   'reason_code': r, 'route_check_job_id': f'rc_{oid}_{d}_{o}'} for d, o, v, a, r in rows]
    plans = [{'job_id': 'dp1', 'status': 'done', 'request': {'depart_offsets_s': [0, 600, 1200], 'origins': [{'id': 'o1'}, {'id': 'o2'}]},
              'result': {'plans': [
                  {'origin_id': 'o1', 'attempts': attempts('o1', [('A', 0, CH, 400, None), ('B', 0, CH, 300, None),
                                                                  ('A', 600, UN, None, 'TIMEOUT'), ('B', 600, NR, None, None),
                                                                  ('A', 1200, NR, None, None), ('B', 1200, NR, None, None)])},
                  {'origin_id': 'o2', 'attempts': attempts('o2', [('A', 0, NR, None, None), ('B', 0, NR, None, None),
                                                                  ('A', 600, NR, None, None), ('B', 600, NR, None, None),
                                                                  ('A', 1200, NR, None, None), ('B', 1200, NR, None, None)])}],
                  'rejected_origins': []}}]
    route_checks = {
        'rc_o1_A_600': _job('rc_o1_A_600', UN, offset=600, reason='TIMEOUT'),
        'rc_re1': _job('rc_re1', CH, 1000, offset=600, recheck_of='rc_o1_A_600'),     # re-check -> checked
        'rc_r0': _job('rc_r0', CH, 800, 0), 'rc_r600': _job('rc_r600', NR, None, 600),
        'rc_o1_B_0': _job('rc_o1_B_0', CH, 300, 0),
    }
    research = [{'origin_id': 'r1', 'destination_id': 'rd', 'depart_offset_s': 0, 'job_id': 'rc_r0'},
                {'origin_id': 'r1', 'destination_id': 'rd', 'depart_offset_s': 600, 'job_id': 'rc_r600'},
                {'origin_id': 'r1', 'destination_id': 'rd', 'depart_offset_s': 1200, 'skipped': 'WINDOW_UNSATISFIABLE'}]
    travel = {'o1': {'job_id': 't1', 'status': 'done', 'request': {'depart_offset_s': 600}, 'result': {'verdict': CH}},
              'r1': {'job_id': 't2', 'status': 'done', 'request': {'depart_offset_s': 600}, 'result': {'verdict': CH}}}
    return {'requests': [{'depart_offsets_s': [0, 600, 1200]}], 'plans': plans, 'route_checks': route_checks,
            'research_checks': research, 'rejected_requests': [], 'travel_only': travel}


def test_cache_to_model_rechecks_research_and_travel_only():
    m = pr.cache_to_model(synthetic_doc())
    o1, o2, r1 = m['plans']['o1'], m['plans']['o2'], m['plans']['r1']
    # o1: the TIMEOUT attempt at +10 min was re-checked as checked -> deadline moves from 0 to 600
    assert o1['latest_safe_departure_s'] == 600 and o1['contiguous_safe_departure_s'] == 600
    assert o1['best']['job_id'] == 'rc_re1' and o1['best']['recheck_of'] == 'rc_o1_A_600'
    assert o2['best_verdict'] == NR and o2['latest_safe_departure_s'] is None
    # research origin: window-unsatisfiable +20 min is its own cell, not counted
    cells = {c['offset_s']: c for c in r1['sweep']}
    assert pr.is_window_skip(cells[1200])
    assert r1['latest_safe_departure_s'] == 0 and r1['contiguous_safe_departure_s'] == 0
    # travel-only kept only when its departure equals the best checked attempt's (cache.ts 255-256)
    assert 'o1' in m['travel_only'] and 'r1' not in m['travel_only']


def test_original_attempts_reproduce_api_fields_without_rechecks():
    doc = synthetic_doc()
    wire = doc['plans'][0]['result']['plans'][0]
    original = pr.adapt_origin_plan(wire, [0, 600, 1200])
    api = api_rules.api_rule_fields(wire, ['A', 'B'])
    assert original['latest_safe_departure_s'] == api['latest_s'] == 0
    assert original['contiguous_safe_departure_s'] == api['contiguous_s'] == 0
    assert original['best_verdict'] == api['best_verdict'] == CH


def test_complete_plans_marks_uncheckable_and_research_offsets():
    model = {'plans': {}, 'offsets_s': [0, 600]}
    origins = [{'id': 'x', 'role': 'origin', 'checkable': False}, {'id': 'y', 'role': 'origin', 'checkable': True},
               {'id': 'r', 'role': 'research_origin', 'checkable': True, 'recorded': {'depart_offset_s': 300}}]
    plans = pr.complete_plans(model, origins, 3600, 10)
    assert plans['x']['note'] == 'not_checkable' and plans['y']['note'] == 'not_computed'
    assert [c['offset_s'] for c in plans['r']['sweep']] == [0, 300, 600, 1200, 1800, 2400, 3000]
    assert all(p['best_verdict'] == UN and p['latest_safe_departure_s'] is None for p in plans.values())


def test_origin_type_follows_glyph_kind():
    mk = lambda **k: {'checkable': True, 'role': 'origin', 'vulnerable': False, **k}  # noqa: E731
    assert pr.origin_type(mk(checkable=False, vulnerable=True)) == 'not_checkable'
    assert pr.origin_type(mk(role='research_origin')) == 'research'
    assert pr.origin_type(mk(vulnerable=True)) == 'care_facility'
    assert pr.origin_type(mk()) == 'village'


# ------------------------------------------------------------------------------------------------ property test

def test_planner_rules_equal_api_dispatch_rules_on_random_attempt_sets():
    """Without re-checks and with every requested offset attempted, the planner's deadline rules and the API's
    api/dispatch.py rules must give the same three fields for any verdict pattern."""
    rng = random.Random(20261102)
    for _ in range(3000):
        offsets = sorted(rng.sample([0, 600, 1200, 1800, 2400, 3000], rng.randint(1, 6)))
        dests = ['d%d' % i for i in range(rng.randint(1, 3))]
        rows = []
        for o in offsets:
            for d in dests:
                v = rng.choice([CH, NR, UN, CH, NR])
                rows.append({'destination_id': d, 'depart_offset_s': o, 'verdict': v,
                             'arrival_s': o + rng.randint(1, 900) if v == CH else None, 'reason_code': None,
                             'route_check_job_id': None})
        wire = {'origin_id': 'o', 'attempts': rows}
        p = pr.adapt_origin_plan(wire, offsets)
        api = api_rules.api_rule_fields(wire, dests)
        assert (p['best_verdict'], p['latest_safe_departure_s'], p['contiguous_safe_departure_s']) == \
            (api['best_verdict'], api['latest_s'], api['contiguous_s'])
        # the share checked at t equals the share with deadline >= t exactly when there is no gap
        if p['latest_safe_departure_s'] == p['contiguous_safe_departure_s'] and p['latest_safe_departure_s'] is not None:
            for c in p['sweep']:
                assert (c['verdict'] == CH) == (c['offset_s'] <= p['latest_safe_departure_s'])
