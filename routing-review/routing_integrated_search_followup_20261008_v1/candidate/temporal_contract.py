"""Versioned event-time arithmetic at fixed cell-centre receivers.

Fractions verify time and summation relative to the represented source
coefficients. Original finite-cell geometry remains numerical. This module
does not certify exposure over continuous roads or change the delivered router.
"""
from bisect import bisect_right
from collections import defaultdict
from fractions import Fraction
import heapq
import math
from pathlib import Path
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'routing-package'))
from routing.core import edge_occupancies, node_cell


class Unsupported(ValueError):
    pass


class WorkCap(RuntimeError):
    pass


def q(value):
    """Exact rational value of a represented input; bool is never a number."""
    if isinstance(value, np.generic): value = value.item()
    if isinstance(value, bool): raise ValueError('Boolean numerical input')
    if isinstance(value, float) and not math.isfinite(value): raise ValueError('Nonfinite numerical input')
    return Fraction(value)


def approximate(value):
    try: return float(value)
    except OverflowError: return None


def check_deadline(deadline):
    if deadline is not None and (isinstance(deadline, bool) or not math.isfinite(deadline)):
        raise ValueError('Finite numerical deadline required')
    if deadline is not None and time.perf_counter() >= deadline: raise WorkCap('WALL_CLOCK')


def wall_deadline(wall_s):
    value = q(wall_s)
    if value < 0 or approximate(value) is None or not math.isfinite(float(value)): raise ValueError('Finite nonnegative wall cap required')
    return time.perf_counter() + float(value)


class TemporalContract:
    schema = 'wfg.hazard.temporal-coefficient-contract/1'
    representations = ('exact', 'union300')

    def __init__(self, reference, *, source_histories_complete=False, receiver_support=None,
                 represented_coefficients_w_m2=None, dt=1):
        if type(source_histories_complete) is not bool: raise ValueError('Explicit Boolean source completeness required')
        self.reference = reference
        if np.ma.isMaskedArray(reference.events) or np.ma.isMaskedArray(reference.current):
            raise ValueError('Masked source histories are unsupported; do not strip their mask')
        events, current = np.asarray(reference.events), np.asarray(reference.current)
        if events.ndim != 3 or min(events.shape) < 1 or not np.issubdtype(events.dtype, np.number) or current.shape != events.shape[1:] or current.dtype != np.bool_:
            raise ValueError('Numeric scenario,row,column events and Boolean current grid required')
        if np.iscomplexobj(events) or np.any(np.isnan(events)) or np.any(events < 0):
            raise ValueError('Source births must be nonnegative or positive infinity')
        if np.any(np.isfinite(events[:, current])): raise ValueError('Current and future-event sources must be disjoint')
        if not isinstance(reference.ids, (list, tuple)): raise ValueError('Explicit scenario ID sequence required')
        self.ids = list(reference.ids)
        if any(type(mid) is not str or not mid for mid in self.ids) or len(self.ids) != events.shape[0] or len(set(self.ids)) != len(self.ids):
            raise ValueError('Unique nonempty member IDs matching scenarios required')
        self.shape = tuple(reference.shape)
        if any(type(v) is not int or v <= 0 for v in self.shape) or self.shape != current.shape: raise ValueError('Declared source shape differs from array shape')
        self.source_count = math.prod(self.shape)
        self.horizon, self.duration, self.remaining = map(q, (reference.horizon, reference.duration, reference.remaining))
        if self.horizon <= 0 or self.duration <= 0 or not 0 <= self.remaining <= self.duration:
            raise ValueError('Positive horizon/duration and same-phase remaining required')
        if any(q(v) >= self.horizon for v in events.ravel() if np.isfinite(v)):
            raise ValueError('Finite births must precede the declared horizon')
        self.dt = q(dt)
        if self.dt <= 0: raise ValueError('Positive lattice spacing required')
        self.interval = Fraction(300)
        self.complete = source_histories_complete
        if np.ma.isMaskedArray(receiver_support): raise ValueError('Masked receiver support is unsupported')
        support = np.ones(self.source_count, dtype=bool) if receiver_support is None else np.asarray(receiver_support)
        if support.shape != (self.source_count,) or support.dtype != np.bool_: raise ValueError('Boolean receiver support vector required')
        self.support = support.copy(); self.support.flags.writeable = False
        if np.ma.isMaskedArray(reference.grid.transform): raise ValueError('Masked geometry is unsupported')
        self.transform = tuple(q(x) for x in reference.grid.transform)
        if len(self.transform) != 6 or self.transform[0]*self.transform[4] - self.transform[1]*self.transform[3] == 0:
            raise ValueError('Nonsingular six-coefficient affine required')
        self.histories = []
        for s in range(len(self.ids)):
            histories = []
            for i, event in enumerate(events[s].ravel()):
                if current.ravel()[i]: histories.append((Fraction(0), self.remaining) if self.remaining > 0 else None)
                elif np.isfinite(event):
                    birth = q(event); histories.append((birth, birth + self.duration))
                else: histories.append(None)
            self.histories.append(tuple(histories))
        self.histories = tuple(self.histories)
        self.coefficient_kind = 'original finite-cell float64 coefficients at fixed centres'
        self.explicit_coefficients = None
        if represented_coefficients_w_m2 is not None:
            if np.ma.isMaskedArray(represented_coefficients_w_m2) or any(np.ma.isMaskedArray(row) for row in represented_coefficients_w_m2):
                raise ValueError('Masked source coefficients are unsupported')
            if len(represented_coefficients_w_m2) != self.source_count or any(len(row) != self.source_count for row in represented_coefficients_w_m2):
                raise ValueError('Explicit receiver/source coefficient matrix shape mismatch')
            self.explicit_coefficients = tuple(tuple(q(v) for v in row) for row in represented_coefficients_w_m2)
            if any(v < 0 for row in self.explicit_coefficients for v in row): raise ValueError('Nonnegative coefficients required')
            self.coefficient_kind = 'explicit abstract nonnegative represented coefficients, mathematical control'
        self._coefficients, self._timelines, self._registered = {}, {}, set()

    @classmethod
    def from_reference(cls, reference, *, source_histories_complete=False, receiver_support=None, dt=1):
        return cls(reference, source_histories_complete=source_histories_complete, receiver_support=receiver_support, dt=dt)

    @classmethod
    def from_control(cls, control):
        from event_reference import EventReference
        events = np.array([[[math.inf if v is None else v for v in row] for row in member] for member in control['events_s']], dtype=float)
        current = np.array(control['current_active'])
        reference = EventReference(events, current, control['config'], control['affine_transform'], control['scenario_ids'])
        return cls(reference, source_histories_complete=control['source_histories_complete'], receiver_support=control['receiver_support'],
                   represented_coefficients_w_m2=control['represented_coefficients_w_m2'])

    def proof_scope(self):
        return {'schema': self.schema, 'arithmetic': 'exact rational arithmetic over represented coefficients and event times',
                'coefficient_scope': self.coefficient_kind, 'source_histories_complete_asserted': self.complete,
                'entry_requires_validated_unmasked_reference': True,
                'prior_mask_stripping_cannot_be_recovered': True,
                'original_forecast_support_is_not_repaired': True,
                'temporal_endpoint_semantics': 'half-open source phases; right-continuous field; closed receiver occupancy',
                'geometric_rounding_bound_available': False, 'continuous_road_acceptance_certified': False,
                'physical_safety_claim': False, 'delivered_default_changed': False}

    def cache_info(self):
        return {'coefficient_vectors': len(self._coefficients), 'timeline_count': len(self._timelines),
                'coefficient_total_bytes': 8 * self.source_count * len(self._coefficients),
                'byte_scope': 'float64 vector payload equivalent only; excludes Python Fraction/cache overhead and source histories'}

    def _grid(self, grid):
        key = tuple(grid.get(k) for k in ('x0', 'y0', 'resolution', 'width', 'height'))
        if key in self._registered: return
        if (grid['height'], grid['width']) != self.shape: raise Unsupported('GRID_SHAPE')
        res = q(grid['resolution'])
        expected = (res, Fraction(0), q(grid['x0']), Fraction(0), -res, q(grid['y0']) + self.shape[0] * res)
        if self.transform != expected: raise Unsupported('GRID_REGISTRATION')
        self._registered.add(key)

    def native_cell(self, router_cell, grid):
        self._grid(grid)
        if type(router_cell) is not int or not 0 <= router_cell < self.source_count: raise Unsupported('RECEIVER_CELL')
        bottom, col = divmod(router_cell, self.shape[1])
        return (self.shape[0] - 1 - bottom) * self.shape[1] + col

    def _supported(self, cell):
        if not self.complete: raise Unsupported('SOURCE_HISTORIES_INCOMPLETE')
        if type(cell) is not int or not 0 <= cell < self.source_count or not self.support[cell]: raise Unsupported('RECEIVER_SUPPORT')

    def _weights(self, cell, deadline):
        self._supported(cell); check_deadline(deadline)
        if cell not in self._coefficients:
            if self.explicit_coefficients is not None: values = self.explicit_coefficients[cell]
            else:
                row, col = divmod(cell, self.shape[1])
                supplied = self.reference.weights_at_cell(row, col)
                if np.ma.isMaskedArray(supplied): raise Unsupported('MASKED_COEFFICIENTS')
                raw = np.asarray(supplied, dtype=float).copy()
                if raw.shape != (self.source_count,) or np.any(~np.isfinite(raw)) or np.any(raw < 0): raise Unsupported('COEFFICIENTS')
                values = tuple(q(float(v)) for v in raw)
            self._coefficients[cell] = values
        check_deadline(deadline); return self._coefficients[cell]

    def _timeline(self, cell, scenario, representation, deadline):
        key = (cell, scenario, representation)
        if key in self._timelines: return self._timelines[key]
        weights = self._weights(cell, deadline); jumps = defaultdict(Fraction); initial = Fraction(0)
        for i, history in enumerate(self.histories[scenario]):
            if i % 64 == 0: check_deadline(deadline)
            if history is None: continue
            birth, burnout = history; value = weights[i]
            if representation == 'union300':
                first = birth // self.interval
                last = -(-(burnout / self.interval).numerator // (burnout / self.interval).denominator) - 1
                final = -(-(self.horizon / self.interval).numerator // (self.horizon / self.interval).denominator) - 1
                first, last = max(0, first), min(last, final)
                if first > last: continue
                birth, burnout = first * self.interval, (last + 1) * self.interval
            if birth == 0: initial += value
            elif birth <= self.horizon: jumps[birth] += value
            # Union uses the delivered last-bin clamp at the terminal point.
            if 0 < burnout < self.horizon or (burnout == self.horizon and representation == 'exact'):
                jumps[burnout] -= value
        knots = sorted({Fraction(0), self.horizon, *jumps.keys()})
        levels, cumulative = [], [Fraction(0)]
        value = initial
        for i, knot in enumerate(knots):
            if i: cumulative.append(cumulative[-1] + (knot - knots[i-1]) * levels[-1])
            value += jumps[knot]
            if value < 0: raise AssertionError('Negative exact source sum')
            levels.append(value)
        result = (tuple(knots), tuple(levels), tuple(cumulative))
        self._timelines[key] = result; check_deadline(deadline); return result

    @staticmethod
    def _primitive(timeline, t):
        knots, levels, cumulative = timeline; i = bisect_right(knots, t) - 1
        return cumulative[i] + (t - knots[i]) * levels[i]

    def _contact(self, scenario, cell, start, end, representation):
        history = self.histories[scenario][cell]
        if history is None: return False
        birth, burnout = history
        if representation == 'union300':
            first = birth // self.interval
            last = -(-(burnout / self.interval).numerator // (burnout / self.interval).denominator) - 1
            birth, burnout = first * self.interval, (last + 1) * self.interval
            if end == self.horizon and burnout >= self.horizon and birth <= self.horizon: return True
        return birth <= end and burnout > start

    def integrate_native_cell(self, cell, start, end, *, representation='exact', deadline=None):
        if representation not in self.representations: raise ValueError('Unknown temporal representation')
        start, end = q(start), q(end)
        if start < 0 or end < start or end > self.horizon: raise Unsupported('TIME_COVERAGE')
        self._supported(cell)
        result = []
        for s, mid in enumerate(self.ids):
            timeline = self._timeline(cell, s, representation, deadline)
            knots, levels, _ = timeline
            first, last = bisect_right(knots, start) - 1, bisect_right(knots, end) - 1
            dose = (self._primitive(timeline, end) - self._primitive(timeline, start)) / 1000
            peak = max(levels[first:last+1]) / 1000
            result.append({'id': mid, 'dose': dose, 'peak': peak, 'flame_contact': self._contact(s, cell, start, end, representation)})
        return result

    def evaluate_occupancies(self, occupancies, grid, *, representation='exact', deadline=None):
        per = {mid: {'dose': Fraction(0), 'peak': Fraction(0), 'flame_contact': False} for mid in self.ids}
        try:
            for occ in occupancies:
                check_deadline(deadline); cell = self.native_cell(occ['cell'], grid)
                for value in self.integrate_native_cell(cell, occ['start'], occ['end'], representation=representation, deadline=deadline):
                    out = per[value['id']]; out['dose'] += value['dose']; out['peak'] = max(out['peak'], value['peak'])
                    out['flame_contact'] |= value['flame_contact']
        except Unsupported as exc: return self._unavailable('UNSUPPORTED', str(exc), representation)
        except WorkCap as exc: return self._unavailable('UNRESOLVED', str(exc), representation)
        codes = ['FLAME_CONTACT'] if any(row['flame_contact'] for row in per.values()) else []
        return self._encode(per, codes, representation)

    def _encode(self, per, codes, representation):
        return {'status': 'REFUSED' if codes else 'ADMISSIBLE_COEFFICIENT_MODEL', 'ok': not codes, 'codes': sorted(set(codes)),
                'per_member': {mid: {'dose': approximate(v['dose']), 'dose_kj_m2': approximate(v['dose']), 'dose_exact': str(v['dose']),
                                     'peak': approximate(v['peak']), 'peak_kw_m2': approximate(v['peak']), 'peak_exact': str(v['peak']),
                                     'flame_contact': v['flame_contact']} for mid, v in per.items()},
                'representation': representation, 'proof_scope': self.proof_scope()}

    def _unavailable(self, status, code, representation):
        return {'status': status, 'ok': False, 'codes': [code],
                'per_member': {mid: {'dose': None, 'dose_exact': None, 'peak': None, 'peak_exact': None, 'flame_contact': None} for mid in self.ids},
                'representation': representation, 'proof_scope': self.proof_scope()}

    def admission(self, graph, request, *, representation='exact', wall_s=30):
        return admission(graph, request, self, representation=representation, deadline=wall_deadline(wall_s))

    def check_mission(self, graph, request, legs, destination, *, representation='exact', wall_s=30):
        return check_mission(graph, request, legs, destination, self, representation=representation, wall_s=wall_s)


def with_budgets(result, request, contract, *, incurred=None):
    if result['status'] in ('UNSUPPORTED', 'UNRESOLVED'): return result
    totals = {}; codes = set(result['codes'])
    incurred = request['incurred'] if incurred is None else incurred
    if set(incurred) != set(contract.ids) or set(request['budgets']['dose']) != set(contract.ids): raise ValueError('Member histories/budgets differ from source IDs')
    peak_budget = q(request['budgets']['peak'])
    if peak_budget < 0: raise ValueError('Negative budget')
    for mid, row in result['per_member'].items():
        prior, budget = q(incurred[mid]), q(request['budgets']['dose'][mid])
        if prior < 0 or budget < 0: raise ValueError('Negative history/budget')
        dose, peak = q(row['dose_exact']) + prior, q(row['peak_exact'])
        if dose > budget: codes.add('DOSE_BUDGET')
        if peak > peak_budget: codes.add('PEAK_BUDGET')
        totals[mid] = {'dose': dose, 'peak': peak, 'flame_contact': row['flame_contact']}
    output = contract._encode(totals, codes, result['representation'])
    for mid in totals: output['per_member'][mid]['incurred_exact'] = str(q(incurred[mid]))
    return output


def _query(graph, request, contract):
    if request.get('objective', 'earliest_arrival') != 'earliest_arrival' or request.get('exposure_scope') != 'including_dwell':
        raise Unsupported('MISSION_SCOPE')
    nodes = {n['id']: n for n in graph['nodes']}; edges = {e['id']: e for e in graph['edges']}
    if len(nodes) != len(graph['nodes']) or len(edges) != len(graph['edges']): raise ValueError('Duplicate graph ID')
    if set(request['position']) != {'node'} or request['position']['node'] not in nodes: raise Unsupported('POSITION')
    departure, horizon = q(request['departure']), q(request['horizon'])
    if departure < 0 or horizon < departure or horizon > contract.horizon: raise Unsupported('TIME_COVERAGE')
    if departure / contract.dt != int(departure / contract.dt) or horizon / contract.dt != int(horizon / contract.dt): raise Unsupported('TIME_LATTICE')
    contract._grid(graph['grid'])
    incoming = request.get('incoming_edge')
    if incoming is not None and (incoming not in edges or edges[incoming]['v'] != request['position']['node']): raise Unsupported('INCOMING_CONTEXT')
    return nodes, edges, departure, horizon


def admission(graph, request, contract, *, representation='exact', deadline=None):
    try:
        nodes, _, departure, _ = _query(graph, request, contract)
        occ = [{'cell': node_cell(graph, nodes[request['position']['node']]), 'start': departure, 'end': departure}]
        return with_budgets(contract.evaluate_occupancies(occ, graph['grid'], representation=representation, deadline=deadline), request, contract)
    except Unsupported as exc: return contract._unavailable('UNSUPPORTED', str(exc), representation)
    except WorkCap as exc: return contract._unavailable('UNRESOLVED', str(exc), representation)


def check_probe(contract, probe, request, *, representation='exact'):
    try:
        values = contract.integrate_native_cell(probe['native_cell'], probe['start'], probe['end'], representation=representation)
        per = {v['id']: v for v in values}; codes = ['FLAME_CONTACT'] if any(v['flame_contact'] for v in values) else []
        return with_budgets(contract._encode(per, codes, representation), request, contract)
    except Unsupported as exc: return contract._unavailable('UNSUPPORTED', str(exc), representation)


def check_mission(graph, request, legs, destination, contract, *, representation='exact', wall_s=30):
    deadline = wall_deadline(wall_s)
    depart = admission(graph, request, contract, representation=representation, deadline=deadline)
    try:
        nodes, edges, t, horizon = _query(graph, request, contract)
        node, incoming, arrived = request['position']['node'], request.get('incoming_edge'), True
        occupancies = [{'cell': node_cell(graph, nodes[node]), 'start': t, 'end': t}]
        forbidden = {tuple(pair) for pair in graph.get('forbidden_turns', [])}
        for leg in legs:
            check_deadline(deadline)
            start, end = q(leg['start']), q(leg['end'])
            if start != t or end <= start or end > horizon: raise Unsupported('LEG_TIME_OR_CONTINUITY')
            if leg['kind'] == 'EDGE':
                e = edges[leg['edge']]
                if e['u'] != node or (incoming, e['id']) in forbidden or q(leg.get('from_fraction', 0)) != 0 or q(leg.get('to_fraction', 1)) != 1:
                    raise Unsupported('EDGE_OR_TURN_CONTEXT')
                if type(e['travel_ticks']) is not int or e['travel_ticks'] <= 0 or end - start != e['travel_ticks'] * contract.dt: raise Unsupported('EDGE_TRAVEL_TIME')
                occupancies.extend(edge_occupancies(e, start, end, graph=graph, node_lookup=nodes))
                node, incoming, arrived = e['v'], e['id'], True
            elif leg['kind'] == 'WAIT':
                ticks = (end - start) / contract.dt
                if leg.get('node') != node or nodes[node].get('waitable') is not True or ticks != int(ticks): raise Unsupported('WAIT_CONTEXT')
                occupancies.append({'cell': node_cell(graph, nodes[node]), 'start': start, 'end': end}); arrived = False
            else: raise Unsupported('LEG_KIND')
            t = end
        if node != destination or not arrived: raise Unsupported('DESTINATION_ARRIVAL_CONTEXT')
        eligible = []
        for d in request['destinations']:
            if d['node'] != destination: continue
            dwell = q(d['dwell'])
            if dwell < 0 or dwell / contract.dt != int(dwell / contract.dt): raise Unsupported('DWELL_LATTICE')
            end = t + dwell
            if end <= horizon and any(q(a) <= t and end <= q(b) for a, b in d['open_intervals']): eligible.append((d, end))
        if not eligible: raise Unsupported('DESTINATION_OPENING_OR_HORIZON')
        mission = None
        for _, end in eligible:
            whole = occupancies + [{'cell': node_cell(graph, nodes[node]), 'start': t, 'end': end}]
            value = with_budgets(contract.evaluate_occupancies(whole, graph['grid'], representation=representation, deadline=deadline), request, contract)
            if mission is None or value['ok']: mission = value
            if value['ok']: break
        mission['arrival'] = approximate(t); mission['destination'] = destination
    except Unsupported as exc: mission = contract._unavailable('UNSUPPORTED', str(exc), representation)
    except WorkCap as exc: mission = contract._unavailable('UNRESOLVED', str(exc), representation)
    mission['admission'] = depart
    mission['mission_ok'] = bool(depart['ok'] and mission['ok'])
    if not depart['ok']:
        mission['ok'] = False; mission['codes'] = sorted(set(mission['codes']) | {'DEPARTURE_REFUSAL'} | set(depart['codes']))
        if depart['status'] in ('UNSUPPORTED', 'UNRESOLVED'): mission['status'] = depart['status']
        elif mission['status'] == 'ADMISSIBLE_COEFFICIENT_MODEL': mission['status'] = 'REFUSED'
    return mission


def exhaustive_walk(graph, request, contract, *, representation='exact', state_cap=200000, wall_s=10):
    """Enumerate all admissible timed prefixes in earliest-time order, no dominance."""
    if type(state_cap) is not int or state_cap < 0: raise ValueError('Invalid exhaustive cap')
    deadline = wall_deadline(wall_s); started = time.perf_counter(); expanded = generated = 0
    initial = admission(graph, request, contract, representation=representation, deadline=deadline)
    def finish(status, reason, **extra):
        return {'status': status, 'reason': reason, 'representation': representation, 'expanded_prefixes': expanded,
                'generated_prefixes': generated, 'wall_s': time.perf_counter() - started, 'state_cap': state_cap,
                'proof_scope': contract.proof_scope(), 'no_dominance_or_deduplication': True, **extra}
    if not initial['ok']:
        return finish(initial['status'] if initial['status'] in ('UNSUPPORTED', 'UNRESOLVED') else 'REFUSED_AT_DEPARTURE', 'INITIAL_ADMISSION', admission=initial)
    try: nodes, edges, departure, horizon = _query(graph, request, contract)
    except Unsupported as exc: return finish('UNSUPPORTED', str(exc))
    outgoing = defaultdict(list)
    for edge in edges.values():
        if type(edge['travel_ticks']) is not int or edge['travel_ticks'] <= 0: return finish('UNSUPPORTED', 'NONPOSITIVE_EDGE')
        outgoing[edge['u']].append(edge)
    for values in outgoing.values(): values.sort(key=lambda edge: edge['id'])
    forbidden = {tuple(pair) for pair in graph.get('forbidden_turns', [])}
    dose = tuple(q(request['incurred'][mid]) for mid in contract.ids)
    peak = tuple(q(initial['per_member'][mid]['peak_exact']) for mid in contract.ids)
    heap = [(departure, 0, request['position']['node'], request.get('incoming_edge'), True, dose, peak, ())]
    generated = 1; unsupported_seen = False
    complete = contract.complete and bool(np.all(contract.support))
    while heap:
        try: check_deadline(deadline)
        except WorkCap: return finish('UNRESOLVED', 'WALL_CLOCK')
        t, _, node, incoming, arrival_context, dose, peak, legs = heapq.heappop(heap)
        if arrival_context:
            for d in request['destinations']:
                if d['node'] != node: continue
                end = t + q(d['dwell'])
                if end > horizon or not any(q(a) <= t and end <= q(b) for a, b in d['open_intervals']): continue
                occupancy = [{'cell': node_cell(graph, nodes[node]), 'start': t, 'end': end}]
                prior = dict(zip(contract.ids, dose))
                value = with_budgets(contract.evaluate_occupancies(occupancy, graph['grid'], representation=representation, deadline=deadline), request, contract, incurred=prior)
                if value['status'] in ('UNSUPPORTED', 'UNRESOLVED'):
                    if value['status'] == 'UNRESOLVED': return finish('UNRESOLVED', 'WALL_CLOCK')
                    unsupported_seen = True; continue
                if value['ok']:
                    checked = check_mission(graph, request, list(legs), node, contract, representation=representation, wall_s=max(0., deadline-time.perf_counter()))
                    if not checked['mission_ok']:
                        return finish('UNRESOLVED' if checked['status'] == 'UNRESOLVED' else 'UNSUPPORTED', 'WITNESS_RECHECK', checker=checked)
                    witness = {'legs': list(legs), 'arrival': approximate(t), 'destination': node, 'checker': checked}
                    if time.perf_counter() >= deadline: return finish('UNRESOLVED', 'WALL_CLOCK_AFTER_CHECK', checked_incumbent=witness)
                    return finish('PROVEN_OPTIMUM_COEFFICIENT_LATTICE' if complete and not unsupported_seen else 'CHECKED_ROUTE_OPTIMUM_UNRESOLVED',
                                  'EARLIEST_COMPLETE_TIMED_WALK', **witness)
        if expanded >= state_cap: return finish('UNRESOLVED', 'STATE_CAP')
        expanded += 1
        candidates = []
        for edge in outgoing[node]:
            if (incoming, edge['id']) in forbidden: continue
            end = t + edge['travel_ticks'] * contract.dt
            if end > horizon: continue
            occupancy = edge_occupancies(edge, t, end, graph=graph, node_lookup=nodes)
            leg = {'kind': 'EDGE', 'edge': edge['id'], 'start': approximate(t), 'end': approximate(end), 'from_fraction': 0, 'to_fraction': 1}
            candidates.append((edge['v'], edge['id'], end, True, occupancy, leg))
        if nodes[node].get('waitable') is True and t + contract.dt <= horizon:
            end = t + contract.dt
            candidates.append((node, incoming, end, False, [{'cell': node_cell(graph, nodes[node]), 'start': t, 'end': end}],
                               {'kind': 'WAIT', 'node': node, 'start': approximate(t), 'end': approximate(end)}))
        for destination, next_incoming, end, context, occupancy, leg in candidates:
            prior = dict(zip(contract.ids, dose))
            cost = with_budgets(contract.evaluate_occupancies(occupancy, graph['grid'], representation=representation, deadline=deadline), request, contract, incurred=prior)
            if cost['status'] == 'UNRESOLVED': return finish('UNRESOLVED', 'WALL_CLOCK')
            if cost['status'] == 'UNSUPPORTED': unsupported_seen = True; continue
            if not cost['ok']: continue
            ndose = tuple(q(cost['per_member'][mid]['dose_exact']) for mid in contract.ids)
            npeak = tuple(max(old, q(cost['per_member'][mid]['peak_exact'])) for old, mid in zip(peak, contract.ids))
            generated += 1
            heapq.heappush(heap, (end, generated, destination, next_incoming, context, ndose, npeak, legs + (leg,)))
    return finish('PROVEN_INFEASIBLE_COEFFICIENT_LATTICE' if complete and not unsupported_seen else 'UNSUPPORTED',
                  'ALL_FINITE_TIMED_WALKS_EXHAUSTED')
