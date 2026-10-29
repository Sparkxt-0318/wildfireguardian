"""Input-level arm neutralization (ARM_DEFINITIONS.md). Pure, deterministic, never mutates inputs.

Table implemented exactly:
  flame off          -> planning hazard: every members[*].flame[k][cell] = False (support, flux untouched)
  peak off           -> planning request: budgets.peak = S
  dose off           -> planning request: budgets.dose[m] = S for every member (incurred unchanged)
  peak AND dose off  -> additionally planning hazard: members[*].flux[k][cell] = 0.0   (A0, A1 only)
Nothing else is touched (support, breakpoints, dt, destinations, dwell, openings, horizon, departure,
position, incoming edge, exposure_scope, incurred, limits, solver, metadata).
"""
import copy
import hashlib
import json
import math

ARMS = ('A0', 'A1', 'A2', 'A3', 'A4')
ENABLED = {'A0': frozenset(), 'A1': frozenset({'FLAME'}), 'A2': frozenset({'FLAME', 'PEAK'}),
           'A3': frozenset({'FLAME', 'DOSE'}), 'A4': frozenset({'FLAME', 'PEAK', 'DOSE'})}
DEFAULT_SENTINEL = 1.0e12
SCHEMA = 'wfg.ablation.arm-transform/1'


def canonical_sha256(obj):
    """SHA-256 of compact sorted-key JSON (same canonical form as the reference worker)."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _check_sentinel(sentinel):
    if isinstance(sentinel, bool) or not isinstance(sentinel, (int, float)) or not math.isfinite(sentinel) or sentinel <= 0:
        raise ValueError('sentinel must be a positive finite number')
    return float(sentinel)


def arm_inputs(arm, hazard, request, *, sentinel=DEFAULT_SENTINEL, with_hashes=True):
    """Return (planning_hazard, planning_request, receipt) for `arm`. Inputs are deep-copied, never mutated."""
    if arm not in ENABLED:
        raise ValueError('unknown arm: %r' % (arm,))
    S = _check_sentinel(sentinel)
    enabled = ENABLED[arm]
    ph, pr = copy.deepcopy(hazard), copy.deepcopy(request)
    changed = []
    if 'FLAME' not in enabled:
        cleared = 0
        for m in ph['members']:
            for row in m['flame']:
                cleared += sum(1 for v in row if v is True)
                row[:] = [False] * len(row)
        changed.append({'field': 'hazard.members[*].flame[k][cell]', 'new': False, 'true_entries_cleared': cleared})
    if 'PEAK' not in enabled:
        changed.append({'field': 'request.budgets.peak', 'old': pr['budgets']['peak'], 'new': S})
        pr['budgets']['peak'] = S
    if 'DOSE' not in enabled:
        dose = pr['budgets']['dose']
        changed.append({'field': 'request.budgets.dose[*]', 'old': dict(dose), 'new': S})
        for mid in list(dose):
            dose[mid] = S
    if 'PEAK' not in enabled and 'DOSE' not in enabled:
        nonzero = 0
        for m in ph['members']:
            for row in m['flux']:
                nonzero += sum(1 for v in row if v != 0)
                row[:] = [0.0] * len(row)
        changed.append({'field': 'hazard.members[*].flux[k][cell]', 'new': 0.0, 'nonzero_entries_cleared': nonzero})
    receipt = {'schema': SCHEMA, 'arm': arm, 'enabled': sorted(enabled),
               'disabled': sorted({'FLAME', 'PEAK', 'DOSE'} - enabled), 'sentinel': S,
               'flux_zeroed': 'PEAK' not in enabled and 'DOSE' not in enabled, 'changed_fields': changed}
    if with_hashes:
        receipt['sha256'] = {'original_hazard': canonical_sha256(hazard), 'planning_hazard': canonical_sha256(ph),
                             'original_request': canonical_sha256(request), 'planning_request': canonical_sha256(pr)}
    return ph, pr, receipt


def verify_transform(arm, hazard, request, planning_hazard, planning_request, *, sentinel=DEFAULT_SENTINEL):
    """Independent re-check that only declared fields differ. Returns list of violations (empty = ok)."""
    enabled, S, bad = ENABLED[arm], float(sentinel), []
    h0 = {k: v for k, v in hazard.items() if k != 'members'}
    h1 = {k: v for k, v in planning_hazard.items() if k != 'members'}
    if h0 != h1:
        bad.append('hazard non-member fields changed')
    if len(hazard['members']) != len(planning_hazard['members']):
        bad.append('member count changed')
    for m0, m1 in zip(hazard['members'], planning_hazard['members']):
        if {k: v for k, v in m0.items() if k not in ('flame', 'flux')} != {k: v for k, v in m1.items() if k not in ('flame', 'flux')}:
            bad.append('member %s non-flame/flux fields changed' % m0.get('id'))
        want_flame = m0['flame'] if 'FLAME' in enabled else [[False] * len(r) for r in m0['flame']]
        if m1['flame'] != want_flame:
            bad.append('member %s flame not as declared' % m0.get('id'))
        zero = 'PEAK' not in enabled and 'DOSE' not in enabled
        want_flux = [[0.0] * len(r) for r in m0['flux']] if zero else m0['flux']
        if m1['flux'] != want_flux or (zero and any(type(v) is not float for r in m1['flux'] for v in r)):
            bad.append('member %s flux not as declared' % m0.get('id'))
    r0 = {k: v for k, v in request.items() if k != 'budgets'}
    r1 = {k: v for k, v in planning_request.items() if k != 'budgets'}
    if r0 != r1:
        bad.append('request non-budget fields changed')
    b0, b1 = request['budgets'], planning_request['budgets']
    if set(b0) != set(b1) or {k: v for k, v in b0.items() if k not in ('peak', 'dose')} != {k: v for k, v in b1.items() if k not in ('peak', 'dose')}:
        bad.append('budget keys changed')
    if b1['peak'] != (b0['peak'] if 'PEAK' in enabled else S):
        bad.append('peak budget not as declared')
    if set(b1['dose']) != set(b0['dose']) or any(b1['dose'][m] != (b0['dose'][m] if 'DOSE' in enabled else S) for m in b0['dose']):
        bad.append('dose budgets not as declared')
    return bad


def sentinel_sufficiency(hazard, request, S=DEFAULT_SENTINEL):
    """Gate G2 with the numbers: S > 1000*(max flux*(horizon - departure) + max incurred) and S > 1000*max flux.

    Also required (time consistency): departure >= 0, horizon >= departure, valid_from >= 0 and every member breakpoint
    >= 0. Informational: S not below any original budget.
    """
    S = _check_sentinel(S)
    max_flux = max((float(v) for m in hazard['members'] for row in m['flux'] for v in row), default=0.0)
    departure, horizon = float(request['departure']), float(request['horizon'])
    duration = horizon - departure
    max_incurred = max((float(v) for v in request['incurred'].values()), default=0.0)
    dose_bound = max_flux * duration + max_incurred
    min_breakpoint = min((float(b) for m in hazard['members'] for b in m['breakpoints']), default=0.0)
    times = {'departure_ge_0': departure >= 0, 'horizon_ge_departure': duration >= 0,
             'valid_from_ge_0': float(hazard['valid_from']) >= 0, 'breakpoints_ge_0': min_breakpoint >= 0,
             'flux_and_incurred_ge_0': min((float(v) for m in hazard['members'] for row in m['flux'] for v in row), default=0.0) >= 0
             and min((float(v) for v in request['incurred'].values()), default=0.0) >= 0}
    c1, c2 = S > 1000.0 * dose_bound, S > 1000.0 * max_flux
    b = request['budgets']
    above = S >= float(b['peak']) and all(S >= float(v) for v in b['dose'].values())
    return {'ok': bool(c1 and c2 and all(times.values())), 'S': S, 'max_flux': max_flux, 'departure': departure,
            'horizon': horizon, 'mission_duration': duration, 'max_incurred': max_incurred,
            'valid_from': float(hazard['valid_from']), 'min_breakpoint': min_breakpoint,
            'dose_bound_max_flux_x_duration_plus_max_incurred': dose_bound,
            'S_gt_1000x_dose_bound': c1, 'S_gt_1000x_max_flux': c2, 'times_consistent': times,
            'S_not_below_original_budgets': above}
