"""Arm-relative in-deadline route check: the only place that calls bundle checker components.

Bundle mode (study jobs), reproducing HybridChecker.check's own preparation path:
  A0     -> MISSION_ONLY: source clock contract + mission_contract.prepare_mission (graph revision/digest authority).
            CERTIFIED_FOR_ARM iff mission VALID.
  A1     -> CONTACT_ONLY: the same mission validation + contact_first.check_contact on the source packet.
            CERTIFIED_FOR_ARM iff CLEAR; DEFINITE_REJECT on a flame witness; else UNRESOLVED.
  A2..A4 -> CONTACT_AND_RADIATION: the full checker class (HybridChecker or the job's checker_module) called with the
            ARM request (sentinel budgets where disabled). CERTIFIED_FOR_ARM iff CERTIFIED_ADMISSIBLE.
Fixture mode (CENTRE_ONLY_FIXTURE_MODE): engine internal centre check (routing.independent.check_route) on the
planning hazard/request. Only for LABELLED_FIXTURE hazards; refused otherwise. Never emitted by make_schedule.
Statuses: CERTIFIED_FOR_ARM | DEFINITE_REJECT | UNRESOLVED (| NOT_RUN set by the worker when no route exists).
"""
import copy
import time
from pathlib import Path

SCOPE = {'A0': 'MISSION_ONLY', 'A1': 'CONTACT_ONLY', 'A2': 'CONTACT_AND_RADIATION',
         'A3': 'CONTACT_AND_RADIATION', 'A4': 'CONTACT_AND_RADIATION'}
FIXTURE_MODE = 'CENTRE_ONLY_FIXTURE_MODE'
BUNDLE_MODE = 'BUNDLE'


def started_label(arm, mode=BUNDLE_MODE):
    """Honest label written before the check starts (survives a deadline stop)."""
    return {'status': 'UNRESOLVED', 'reason': 'CHECK_STARTED_NOT_COMPLETED', 'arm': arm,
            'scope': FIXTURE_MODE if mode == FIXTURE_MODE else SCOPE[arm], 'mode': mode}


def _arm_request_violations(arm, original, arm_request, sentinel):
    """The arm request may differ from the original only in budgets; each budget equals the original for an enabled
    component and equals the sentinel for a disabled one. Returns a list of violations (empty = consistent)."""
    from arm_transform import ENABLED
    en, bad = ENABLED[arm], []
    if {k: v for k, v in original.items() if k != 'budgets'} != {k: v for k, v in arm_request.items() if k != 'budgets'}:
        bad.append('NON_BUDGET_FIELDS_DIFFER')
    b0, b1 = original.get('budgets', {}), arm_request.get('budgets', {})
    if set(b0) != set(b1) or {k: v for k, v in b0.items() if k not in ('peak', 'dose')} != {k: v for k, v in b1.items() if k not in ('peak', 'dose')}:
        bad.append('BUDGET_KEYS_DIFFER')
    if b1.get('peak') != (b0.get('peak') if 'PEAK' in en else sentinel):
        bad.append('PEAK_BUDGET_NOT_ORIGINAL_OR_SENTINEL_AS_ARM_REQUIRES')
    d0, d1 = b0.get('dose', {}), b1.get('dose', {})
    if set(d0) != set(d1) or any(d1[m] != (d0[m] if 'DOSE' in en else sentinel) for m in d0):
        bad.append('DOSE_BUDGETS_NOT_ORIGINAL_OR_SENTINEL_AS_ARM_REQUIRES')
    return bad


def _finish(out, started, deadline, hc=None):
    """Deadline (and RSS, when the checker module is present) gate before any certificate, as HybridChecker._finish."""
    now = time.perf_counter()
    rss_over = hc is not None and hc.rss_mb() > hc.RSS_LIMIT_MB
    if (now >= deadline or rss_over) and out['status'] != 'UNRESOLVED':
        out = dict(out, status='UNRESOLVED', reason='RSS_LIMIT' if rss_over else 'WALL_CAP_AFTER_CHECK',
                   checked_result_status=out['status'], checked_result_reason=out['reason'],
                   checked_result_is_secondary=True)
    out['elapsed_s'] = time.perf_counter() - started
    return out


def _mission_and_contact(arm, mods, packet_dir, graph, arm_request, legs, destination, deadline):
    """A0/A1: HybridChecker.check steps up to (A1: including) the contact check, without radiation."""
    mc, cf, hc = mods['mission_contract'], mods['contact_first'], mods['hybrid_checker']
    started = time.perf_counter()
    out = {'status': 'UNRESOLVED', 'reason': 'INCOMPLETE', 'arm': arm, 'scope': SCOPE[arm], 'mode': BUNDLE_MODE, 'timing_s': {}}
    times = out['timing_s']
    try:
        if time.perf_counter() >= deadline:
            raise mc.MissionInvalid('WALL_CAP_BEFORE_PREPARATION')
        directory = Path(packet_dir).resolve()
        ts = time.perf_counter()
        identity = hc.file_sha(directory / 'constructed_arrays.npz') + ':' + hc.file_sha(directory / 'REPORT.json')
        source = cf.ContactSources.from_case(directory, deadline=deadline)
        times['source_preparation_and_binding'] = time.perf_counter() - ts
        ts = time.perf_counter()
        g, r, walk = copy.deepcopy(graph), copy.deepcopy(arm_request), copy.deepcopy(legs)
        source.clock_contract.validate_request(r)
        mc.unmasked((graph, arm_request, legs))
        digest = mc.graph_digest(g)
        mission = mc.prepare_mission(g, r, walk, destination, scenario_ids=source.ids, source_horizon=source.horizon,
                                     deadline=deadline, expected_graph_revision=graph['revision'],
                                     expected_graph_sha256=mc.graph_digest(graph))
        times['mission_validation'] = time.perf_counter() - ts
        out['mission'] = {k: v for k, v in mission.items() if k != 'trajectory'}
        out['trajectory'] = mission['trajectory']; out['graph_identity'] = digest
        if mission['status'] != 'VALID':
            out.update(status='UNRESOLVED', reason='MISSION_VALIDATION')
        elif arm == 'A0':
            out.update(status='CERTIFIED_FOR_ARM', reason='MISSION_VALID')
        else:
            ts = time.perf_counter()
            contact = cf.check_contact(source, mission['trajectory'], deadline=deadline)
            times['contact_check'] = time.perf_counter() - ts
            out['contact'] = contact
            if contact['status'] == 'CLEAR':
                out.update(status='CERTIFIED_FOR_ARM', reason='CONTACT_CLEAR')
            elif contact['status'] == 'DEFINITE_REJECT':
                out.update(status='DEFINITE_REJECT', reason='FLAME_CONTACT_WITNESS')
            else:
                out.update(status='UNRESOLVED', reason='CONTACT_NOT_COMPLETE')
        # Authority re-check after computation, before any certificate (as HybridChecker).
        if identity != hc.file_sha(directory / 'constructed_arrays.npz') + ':' + hc.file_sha(directory / 'REPORT.json'):
            raise mc.MissionInvalid('SOURCE_CHANGED_DURING_CHECK')
        if digest != mc.graph_digest(graph) or r != arm_request or walk != legs:
            raise mc.MissionInvalid('MISSION_AUTHORITY_CHANGED_DURING_CHECK')
        out['source_identity'] = identity
    except (mc.MissionInvalid, ValueError, TypeError, KeyError, ArithmeticError, OSError) as exc:
        out.update(status='UNRESOLVED', reason=str(exc) or type(exc).__name__)
    return _finish(out, started, deadline, hc)


def _full_checker(arm, checker_class, mods, packet_dir, graph, arm_request, legs, destination, deadline):
    """A2..A4: the bundle's full checker under the arm request."""
    mc = mods['mission_contract']
    started = time.perf_counter()
    raw = checker_class(packet_dir).check(graph, arm_request, legs, destination, deadline=deadline,
                                          wall_s=max(0.0, deadline - time.perf_counter()),
                                          expected_graph_revision=graph['revision'],
                                          expected_graph_sha256=mc.graph_digest(graph))
    status = {'CERTIFIED_ADMISSIBLE': 'CERTIFIED_FOR_ARM', 'DEFINITE_REJECT': 'DEFINITE_REJECT'}.get(raw.get('status'), 'UNRESOLVED')
    raw = dict(raw)  # retain trajectory for final-kit route identity binding
    out = {'status': status, 'reason': raw.get('reason'), 'arm': arm, 'scope': SCOPE[arm], 'mode': BUNDLE_MODE,
           'checker_status': raw.get('status'), 'checker_schema': raw.get('schema'), 'checker_result': raw}
    return _finish(out, started, deadline, mods.get('hybrid_checker'))


def _fixture_centre(arm, mods, fixture_inputs, legs, destination, deadline):
    graph, planning_hazard, planning_request = fixture_inputs
    if planning_hazard.get('evidence_class') != 'LABELLED_FIXTURE':
        raise ValueError('FIXTURE_MODE_REFUSED_FOR_NON_FIXTURE_INPUT')
    started = time.perf_counter()
    raw = mods['independent'].check_route(graph, planning_hazard, planning_request, legs, destination)
    status = 'CERTIFIED_FOR_ARM' if raw.get('status') == 'CHECKED_ROUTE' and raw.get('ok') else (
        'DEFINITE_REJECT' if raw.get('status') in ('REJECTED_ROUTE', 'AT_ISSUE_FAILURE') else 'UNRESOLVED')
    out = {'status': status, 'reason': raw.get('status'), 'arm': arm, 'scope': FIXTURE_MODE, 'mode': FIXTURE_MODE,
           'checker_result': raw, 'fixture_only': True}
    return _finish(out, started, deadline)


def check_for_arm(arm, engine_modules, packet_dir, graph, original_request, arm_request, legs, destination, deadline,
                  *, checker_class=None, mode=BUNDLE_MODE, fixture_inputs=None, sentinel=1.0e12):
    """Return {status, reason, scope, ...} for the arm's in-deadline check. `deadline` is a perf_counter value."""
    if arm not in SCOPE:
        raise ValueError('unknown arm')
    bad = _arm_request_violations(arm, original_request, arm_request, float(sentinel))
    if bad:
        raise ValueError('ARM_REQUEST_INCONSISTENT:' + ';'.join(bad))
    if mode == FIXTURE_MODE:
        return _fixture_centre(arm, engine_modules, fixture_inputs, legs, destination, deadline)
    if mode != BUNDLE_MODE:
        raise ValueError('unknown arm check mode')
    if arm in ('A0', 'A1'):
        return _mission_and_contact(arm, engine_modules, packet_dir, graph, arm_request, legs, destination, deadline)
    if checker_class is None:
        raise ValueError('checker class required for ' + arm)
    return _full_checker(arm, checker_class, engine_modules, packet_dir, graph, arm_request, legs, destination, deadline)
