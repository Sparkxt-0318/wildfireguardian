"""Property tests of the oracle on random SYNTHETIC cases (hypothesis drives the case seed).

1. Adding a constraint never turns a non-checked result into checked (in fact no state ever
   improves): tighter peak or dose budgets, shorter shelter windows, less vehicle space, less shelter
   capacity, fewer residents, extra burning cells, later release, shorter shifts, extra forbidden
   turns, fewer waitable nodes.
2. Unresolved never counts as delivered; every delivered resident is independently re-verified
   against hazard_contract and the validator.
3. Unsupported hazard data leads to unresolved; unknown data never makes anything checked.
Plus: the RELAXED check agrees exactly with hazard_contract's contact and support, and the safety
slack is exact (delaying by just less keeps the leg contact-free, by just more does not).
"""
import math

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from evacplan import (
    Budgets, ClassCounts, InstanceIndex, Oracle, RelaxedContactCheck, State, check_plan, contact_records,
    state_rank, validate_solution,
)
from evacplan_testkit import NAN, random_case

SEEDS = st.integers(0, 2**32 - 1)
SET = settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
CHECKED, MNR, UNR = State.CHECKED, State.MODEL_NO_ROUTE, State.UNRESOLVED
TIGHTENINGS = ("peak", "dose", "window", "vehicle_space", "shelter_capacity", "residents", "burning", "release",
               "shift", "turn", "waitable")


# ------------------------------------------------------------------------------ tightenings
def _replace(items, i, **upd):
    out = list(items)
    out[i] = out[i].model_copy(update=upd)
    return out


def _budgets(inst, K, *, peak=None, dose=None):
    p, d = inst.hazard.budgets.per_member(K)
    b = Budgets(peak_kw_m2=(p if peak is None else peak).tolist(), dose_kj_m2=(d if dose is None else dose).tolist())
    return inst.model_copy(update={"hazard": inst.hazard.model_copy(update={"budgets": b})})


def more_burning(ss, rng):
    """Earlier ignitions, later extinctions and new burning cells; unknown stays unknown."""
    ig, ex = ss.ignite_s.copy(), ss.extinguish_s.copy()
    known = ss.supported
    pick = known & (rng.random(ig.shape) < 0.3)
    never = pick & (ig == np.inf)
    ig[never] = rng.choice([-50.0, 0.0, 60.0, 200.0], size=int(never.sum()))
    ex[never] = ig[never] + rng.choice([20.0, 300.0], size=int(never.sum()))
    burn = pick & np.isfinite(ig) & ~never
    ig[burn] -= rng.choice([0.0, 10.0, 100.0], size=int(burn.sum()))
    ex[burn] += rng.choice([0.0, 10.0, 100.0], size=int(burn.sum()))
    return type(ss)(ig, ex, ss.supported, ss.meta)


def tighten(inst, ss, kind, rng):
    """One added constraint. Returns (instance, scenario_set) or None if not applicable."""
    K = ss.K
    if kind == "peak":
        p, _ = inst.hazard.budgets.per_member(K)
        return _budgets(inst, K, peak=p * rng.uniform(0.0, 1.0, size=K)), ss
    if kind == "dose":
        _, d = inst.hazard.budgets.per_member(K)
        d = d.copy()
        d[int(rng.integers(K))] *= rng.uniform(0.0, 1.0)
        return _budgets(inst, K, dose=d), ss
    if kind == "window":
        i = int(rng.integers(len(inst.shelters)))
        w = [(a + 0.5 * rng.random() * (b - a), b - 0.5 * rng.random() * (b - a)) for a, b in inst.shelters[i].open_windows]
        return inst.model_copy(update={"shelters": _replace(inst.shelters, i, open_windows=w)}), ss
    if kind == "vehicle_space":
        i = int(rng.integers(len(inst.vehicles)))
        v = inst.vehicles[i]
        field = ["seats", "wheelchair_slots", "stretcher_slots"][int(rng.integers(3))]
        if getattr(v, field) == 0:
            return None
        return inst.model_copy(update={"vehicles": _replace(inst.vehicles, i, **{field: getattr(v, field) - 1})}), ss
    if kind == "shelter_capacity":
        i = int(rng.integers(len(inst.shelters)))
        cap = list(inst.shelters[i].capacity.vector())
        c = int(rng.integers(3))
        if cap[c] == 0:
            return None
        cap[c] -= 1
        return inst.model_copy(update={"shelters": _replace(inst.shelters, i, capacity=ClassCounts.of(cap))}), ss
    if kind == "residents":
        i = int(rng.integers(len(inst.facilities)))
        res = list(inst.facilities[i].residents.vector())
        c = int(rng.integers(3))
        if res[c] == 0:
            return None
        res[c] -= 1
        return inst.model_copy(update={"facilities": _replace(inst.facilities, i, residents=ClassCounts.of(res))}), ss
    if kind == "burning":
        return inst, more_burning(ss, rng)
    if kind == "release":
        i = int(rng.integers(len(inst.facilities)))
        later = inst.facilities[i].release_s + float(rng.choice([1.0, 30.0, 200.0]))
        return inst.model_copy(update={"facilities": _replace(inst.facilities, i, release_s=later)}), ss
    if kind == "shift":
        i = int(rng.integers(len(inst.vehicles)))
        cur = inst.vehicles[i].shift_limit_s or 2000.0
        return inst.model_copy(update={"vehicles": _replace(inst.vehicles, i, shift_limit_s=cur * rng.uniform(0.1, 1.0))}), ss
    if kind == "turn":
        idx = InstanceIndex(inst)
        edges = inst.graph.edges
        a = edges[int(rng.integers(len(edges)))]
        outs = idx.out_edges(a.v)
        b = outs[int(rng.integers(len(outs)))]
        turns = list(inst.graph.forbidden_turns)
        if (a.id, b) in turns:
            return None
        g = inst.graph.model_copy(update={"forbidden_turns": turns + [(a.id, b)]})
        return inst.model_copy(update={"graph": g}), ss
    if kind == "waitable":
        nodes = list(inst.graph.nodes)
        cand = [i for i, n in enumerate(nodes) if n.waitable]
        if not cand:
            return None
        i = cand[int(rng.integers(len(cand)))]
        nodes[i] = nodes[i].model_copy(update={"waitable": False})
        return inst.model_copy(update={"graph": inst.graph.model_copy(update={"nodes": nodes})}), ss
    raise ValueError(kind)


def assert_never_better(a, b):
    """Every leg, action, trip and vehicle of plan b is no better than in plan a; delivered no larger."""
    assert len(a.vehicles) == len(b.vehicles)
    for va, vb in zip(a.vehicles, b.vehicles):
        assert [(lg.action, lg.kind, lg.t_start, lg.t_end) for lg in va.legs] == \
               [(lg.action, lg.kind, lg.t_start, lg.t_end) for lg in vb.legs]
        for la, lb in zip(va.legs, vb.legs):
            assert state_rank(lb.state) <= state_rank(la.state), (la, lb)
        for xa, xb in zip(va.actions, vb.actions):
            assert state_rank(xb.state) <= state_rank(xa.state)
        assert [t.action for t in va.trips] == [t.action for t in vb.trips]
        for ta, tb in zip(va.trips, vb.trips):
            assert state_rank(tb.state) <= state_rank(ta.state)
            if ta.state is not CHECKED:
                assert tb.state is not CHECKED
        assert state_rank(vb.state) <= state_rank(va.state)
    assert b.delivered_total <= a.delivered_total
    for fid, cc in b.delivered_by_facility.items():
        assert all(x <= y for x, y in zip(cc.vector(), a.delivered_by_facility[fid].vector()))


# ----------------------------------------------------------------------- 1. monotonicity
@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(SEEDS, st.sampled_from(TIGHTENINGS), SEEDS)
def test_adding_a_constraint_never_turns_anything_into_checked(seed, kind, seed2):
    inst, ss, sol = random_case(seed)
    t = tighten(inst, ss, kind, np.random.default_rng(seed2))
    if t is None:
        return
    inst2, ss2 = t
    a = check_plan(inst, ss, sol)
    b = check_plan(inst2, ss2, sol)
    assert_never_better(a, b)
    if kind == "burning":                       # more burning never lengthens a slack
        for va, vb in zip(a.vehicles, b.vehicles):
            for la, lb in zip(va.legs, vb.legs):
                if la.slack_s is not None and lb.slack_s is not None:
                    assert lb.slack_s <= la.slack_s + 1e-9


@pytest.mark.parametrize("kind", TIGHTENINGS)
def test_each_tightening_is_exercised(kind):
    """Guard against vacuous property runs: each tightening applies and changes some state."""
    changed = 0
    for seed in range(400):
        inst, ss, sol = random_case(seed)
        t = tighten(inst, ss, kind, np.random.default_rng(seed + 1))
        if t is None:
            continue
        a, b = check_plan(inst, ss, sol), check_plan(*t, sol)
        assert_never_better(a, b)
        changed += any(la.state != lb.state for va, vb in zip(a.vehicles, b.vehicles) for la, lb in zip(va.legs, vb.legs))
        if changed:
            return
    pytest.fail(f"tightening {kind!r} never changed a state in 400 random cases")


# -------------------------------------------------------- 2. unresolved is never delivered
def _independent_hazard(inst, ss, seg):
    nodes = {n.id: n for n in inst.graph.nodes}
    off = inst.hazard.t0_offset_s
    if seg.edge is not None:
        e = next(e for e in inst.graph.edges if e.id == seg.edge)
        geom = np.array([[nodes[e.u].x, nodes[e.u].y], [nodes[e.v].x, nodes[e.v].y]])
        return ss.query_uniform(geom, seg.t0 + off, seg.t1 + off)
    n = nodes[seg.node]
    return ss.query(np.array([[n.x, n.y]]), seg.t0 + off, seg.t1 + off)


@SET
@given(SEEDS)
def test_delivered_residents_are_independently_verified_and_unresolved_never_counts(seed):
    inst, ss, sol = random_case(seed)
    r = check_plan(inst, ss, sol)
    rep = validate_solution(inst, sol)
    peak, dose = inst.hazard.budgets.per_member(ss.K)
    delivered = np.zeros(3, dtype=int)
    unresolved = model_no_route = 0
    for v, sch in zip(r.vehicles, rep.schedules):
        for t in v.trips:
            n = t.counts.total
            if t.state is CHECKED:
                delivered += t.counts.vector()
            elif t.state is UNR:
                unresolved += n
                continue
            else:
                model_no_route += n
                continue
            # independent re-check of everything the vehicle did up to the end of this trip
            assert not [i for i in sch.issues if i.action <= t.action]
            lo, hi = np.zeros(ss.K), np.zeros(ss.K)
            for seg in sch.segments:
                if seg.action > t.action:
                    break
                for k, h in enumerate(_independent_hazard(inst, ss, seg)):
                    assert h.contact is False and h.supported and h.flux_upper <= peak[k]
                    hi[k] += h.dose_upper
            assert np.all(hi <= dose)
        model_no_route += v.onboard_end.total
    assert tuple(delivered) == r.delivered.vector() and int(delivered.sum()) == r.delivered_total
    assert unresolved == r.unresolved_total == sum(r.unresolved_by_reason.values())
    assert model_no_route == r.model_no_route_total == sum(r.model_no_route_by_reason.values())
    codes = {i.code for i in rep.issues}
    if not codes & {"OVERBOARDED", "UNLOAD_EXCEEDS_LOAD", "UNKNOWN_VEHICLE", "DUPLICATE_ITINERARY"}:
        assert r.delivered_total + r.unresolved_total + r.model_no_route_total + r.not_planned_total \
            == r.residents_total


# ------------------------------------------------------ 3. unsupported data -> unresolved
def mark_unknown(ss, cells):
    ig, ex, sup = ss.ignite_s.copy(), ss.extinguish_s.copy(), ss.supported.copy()
    for k, r, c in cells:
        ig[k, r, c] = ex[k, r, c] = NAN
        sup[k, r, c] = False
    return type(ss)(ig, ex, sup, ss.meta)


@SET
@given(SEEDS, SEEDS)
def test_unknown_cell_under_a_checked_leg_makes_it_unresolved(seed, seed2):
    inst, ss, sol = random_case(seed)
    a = check_plan(inst, ss, sol)
    cand = [(vi, lg) for vi, v in enumerate(a.vehicles) for lg in v.legs if lg.hazard_state is CHECKED]
    if not cand:
        return
    rng = np.random.default_rng(seed2)
    vi, leg = cand[int(rng.integers(len(cand)))]
    idx = InstanceIndex(inst)
    geom = idx.edge_geometry(leg.edge) if leg.edge else idx.node_xy(leg.node)
    off = inst.hazard.t0_offset_s
    rows, cols, *_ = contact_records(ss.grid, geom, leg.t_start + off, leg.t_end + off)
    j = int(rng.integers(rows.size))
    k = int(rng.integers(ss.K))
    b = check_plan(inst, mark_unknown(ss, [(k, rows[j], cols[j])]), sol)
    leg_b = b.vehicles[vi].legs[leg.index]
    assert leg_b.hazard_state is UNR and "UNSUPPORTED_HAZARD" in leg_b.reasons
    assert leg_b.members[k].contact is None and not leg_b.members[k].supported
    for t in b.vehicles[vi].trips:
        if t.action >= leg.action:
            assert t.state is not CHECKED
    for va, vb in zip(a.vehicles, b.vehicles):          # unknown data never makes anything checked
        for ta, tb in zip(va.trips, vb.trips):
            assert tb.state is not CHECKED or ta.state is CHECKED
    assert b.delivered_total <= a.delivered_total


@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(SEEDS)
def test_all_unknown_hazard_delivers_nobody(seed):
    inst, ss, sol = random_case(seed)
    K, Hh, Ww = ss.shape
    unknown = mark_unknown(ss, [(k, r, c) for k in range(K) for r in range(Hh) for c in range(Ww)])
    r = check_plan(inst, unknown, sol)
    assert r.delivered_total == 0
    for v in r.vehicles:
        for lg in v.legs:
            assert lg.hazard_state in (None, UNR)
            assert lg.state is not CHECKED
        for t in v.trips:
            assert t.state is not CHECKED


# ----------------------------------------------------- RELAXED check and slack exactness
@settings(max_examples=80, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(SEEDS)
def test_relaxed_check_matches_hazard_contract_contact_and_support(seed):
    inst, ss, sol = random_case(seed)
    relaxed = RelaxedContactCheck(inst, ss)
    oracle = Oracle(inst, ss, evaluate_after_failure=True)
    r = oracle.check_plan(sol)
    rep = validate_solution(inst, sol)
    for v, sch in zip(r.vehicles, rep.schedules):
        assert len(v.legs) == len(sch.segments)
        for lg, seg in zip(v.legs, sch.segments):
            got = relaxed.segment(seg)
            hz = _independent_hazard(inst, ss, seg)
            assert got.blocked == any(h.contact is True for h in hz)
            assert got.uncertain == (not all(h.supported for h in hz))
            if got.blocked:
                assert lg.hazard_state is MNR and "FLAME_CONTACT" in lg.reasons
            assert not hasattr(got, "state")
    for it in sol.itineraries:
        ri = relaxed.itinerary(it, stop_at_block=False)
        assert not hasattr(ri, "state")


@SET
@given(SEEDS)
def test_safety_slack_is_exact(seed):
    inst, ss, sol = random_case(seed, p_burn=0.2)
    oracle = Oracle(inst, ss)
    r = oracle.check_plan(sol)
    idx = InstanceIndex(inst)
    off = inst.hazard.t0_offset_s
    for v in r.vehicles:
        for lg in v.legs:
            if lg.slack_s is None:
                continue
            a, b = lg.t_start + off, lg.t_end + off
            assert lg.slack_s >= 0.0 and b + lg.slack_s <= ss.meta.horizon_s + 1e-9
            if math.isclose(lg.slack_s, ss.meta.horizon_s - b):
                continue                                   # capped at the horizon
            geom = idx.edge_geometry(lg.edge) if lg.edge else idx.node_xy(lg.node)
            q = ss.query_uniform if lg.edge else ss.query

            def contact(d):
                return any(h.contact is True for h in q(geom, a + d, b + d))

            eps = 1e-6 * max(1.0, lg.slack_s)
            assert not contact(max(lg.slack_s - eps, 0.0))
            assert contact(lg.slack_s + eps)
