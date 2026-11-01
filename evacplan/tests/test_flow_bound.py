"""E4, the flow-over-time bound (bound only): it covers the brute-force optimum of tiny instances and every plan
the oracle checks on random small instances (random plans, B0, B1, B3); adding a constraint never raises it;
the weak-duality certificate holds for any duals; dropping dominated moves keeps the LP optimum; the method
plans nothing and claims only the resource bound when the 1 s lattice is not complete. SYNTHETIC instances
only."""
from __future__ import annotations

import math
import time

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from hazard_contract import ScenarioSet
from evacplan import Oracle, State
from evacplan.methods import get_method
from evacplan.methods.flow_bound import E4FlowBound, FlowNetwork, certified_value, dual_bound, flow_bound
from evacplan.methods.lp_worker import solve_lp
from evacplan.methods.timexp import trivial_bound
from evacplan.reach import Reach
from evacplan_testkit import make_set, quiet, random_case
from test_b3_mip import brute_force, tiny


def persistent(ss: ScenarioSet) -> ScenarioSet:
    """The same fire with every ignited cell burning through the horizon (the 1 s lattice is then complete)."""
    ex = np.where(np.isfinite(ss.ignite_s), np.inf, ss.extinguish_s)
    return ScenarioSet(ss.ignite_s.copy(), ex, ss.supported.copy(), ss.meta)


def lp_value(r) -> float:
    """The LP optimum (an empty model, where nothing can be delivered, has value 0)."""
    if r.status == "Empty":
        return 0.0
    assert r.status == "Optimal", r.status
    return float(r.objective)


def solve(name, inst, ss, budget, **cfg):
    res = get_method(name, **cfg).solve(inst, ss, budget_s=budget, seed=0, deadline=time.monotonic() + budget)
    return res


# ------------------------------------------------------------------------------- exact optima
def test_bound_covers_the_brute_force_optimum_of_a_tiny_instance():
    inst, ss = tiny()
    opt, plan = brute_force(inst, ss)
    assert opt == 5 and Oracle(inst, ss).check_plan(plan.solution(inst, "brute")).delivered_total == 5
    b, info = flow_bound(inst, ss, delta_s=60)
    assert info["certified"] and info["lp_status"] == "Optimal"
    assert opt <= b <= inst.residents_total
    assert b == 5                                    # tight here (with the trip cuts; 6 without them)
    loose, _ = flow_bound(inst, ss, delta_s=60, trip_cuts=False, free_space=False)
    assert loose == 6       # fractions of the one van board at A while other fractions drive: parallel work


@pytest.mark.parametrize("seed", range(10))
def test_bound_covers_brute_force_on_random_tiny_instances(seed):
    """Off-grid data (travel, boarding, unloading, release, opening, start, fire timing), as in B3's tests."""
    rng = np.random.default_rng(seed)
    step = float(rng.choice([40.0, 50.0, 70.0]))
    kw = dict(step=step, board=float(rng.choice([30.0, 45.0, 90.0])), unload=float(rng.choice([20.0, 35.0, 60.0])),
              wc_unload=90.0, release=tuple(float(x) for x in rng.choice([0.0, 100.0, 250.0], size=2)),
              ignite=float(rng.choice([700.0, 1000.0, 1300.0])), fire_col=int(rng.choice([1, 3])),
              start=float(rng.choice([0.0, 30.0, 90.0])), opens=float(rng.choice([0.0, 300.0])))
    inst, ss = tiny(**kw)
    opt, _ = brute_force(inst, ss)
    for delta in (60, int(2 * step)):
        b, info = flow_bound(inst, ss, delta_s=delta)
        assert info["certified"], info
        assert opt <= b, (kw, delta, opt, b, info)


# ------------------------------------------------------------------ every checked plan, random instances
@pytest.mark.parametrize("seed", range(12))
def test_bound_covers_every_checked_plan_on_random_small_instances(seed):
    """Random small instances (co-located sites, zero boarding times, windows, shifts, unknown cells), with the
    fire made persistent so the bound is certified: the bound covers the random plan of the case, B0, B1 and
    (every third seed) B3, all checked by the oracle."""
    inst, ss0, sol = random_case(seed)
    ss = persistent(ss0)
    b, info = flow_bound(inst, ss, delta_s=60)
    assert info["certified"], info
    oracle = Oracle(inst, ss)
    got = {"random": oracle.check_plan(sol).delivered_total}
    for name in ("b0_independent", "b1_greedy"):
        got[name] = oracle.check_plan(solve(name, inst, ss, 20.0).solution).delivered_total
    if seed % 3 == 0:
        got["b3_mip"] = oracle.check_plan(solve("b3_mip", inst, ss, 6.0, delta_s=60).solution).delivered_total
    assert max(got.values()) <= b <= trivial_bound(inst), (got, b, info)


# ----------------------------------------------------------------------------- monotonicity
def _restrict(inst, ss, change: str, rng: np.random.Generator):
    if change == "vehicle":
        return inst.model_copy(update={"vehicles": inst.vehicles[:-1]}), ss
    if change == "shift":
        vs = [v.model_copy(update={"shift_limit_s": float(min(v.shift_limit_s or 1e9, rng.choice([120.0, 300.0, 600.0])))})
              for v in inst.vehicles]
        return inst.model_copy(update={"vehicles": vs}), ss
    if change == "horizon":
        h = float(math.floor(ss.meta.horizon_s * float(rng.choice([0.4, 0.7, 0.9]))))
        return inst, ScenarioSet(ss.ignite_s, ss.extinguish_s, ss.supported, ss.meta.model_copy(update={"horizon_s": h}))
    if change == "burn":
        ig = ss.ignite_s.copy()
        ig = np.where(np.isfinite(ig), ig - float(rng.choice([30.0, 120.0, 400.0])), ig)
        new = ss.supported & np.isinf(ig) & (rng.random(ig.shape) < 0.15)
        ig[new] = rng.choice([0.0, 200.0, 600.0], size=int(new.sum()))
        ex = np.where(np.isfinite(ig), np.inf, ss.extinguish_s)
        return inst, ScenarioSet(ig, ex, ss.supported.copy(), ss.meta)
    raise AssertionError(change)


@settings(max_examples=16, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(seed=st.integers(0, 5000), change=st.sampled_from(["vehicle", "shift", "horizon", "burn"]))
def test_adding_a_constraint_never_raises_the_bound(seed, change):
    """Fewer vehicles, shorter shifts, a shorter horizon or more burning (earlier ignitions, new burning cells)
    only shrink the relaxation: the LP value and the bound never grow (same time step: the locations and roads
    are unchanged)."""
    inst, ss0, _ = random_case(seed)
    ss = persistent(ss0)
    rng = np.random.default_rng(seed)
    b1, i1 = flow_bound(inst, ss, delta_s=60, crossover=True)
    inst2, ss2 = _restrict(inst, ss, change, rng)
    b2, i2 = flow_bound(inst2, ss2, delta_s=60, crossover=True)
    assert i1["certified"] and i2["certified"], (i1, i2)
    assert i1["delta_eff_s"] == i2["delta_eff_s"]
    assert b2 <= b1, (change, b1, b2)
    v1, v2 = i1.get("dual_bound"), i2.get("dual_bound")
    if v1 is not None and v2 is not None:
        assert v2 <= v1 + 1e-6, (change, v1, v2)


def test_trip_limits_follow_the_vehicle_timeline():
    """Tiny instance: the van reaches A at 240 s (from S at 0), A's action set ends at 911 s (it must leave by 910 s),
    a round trip A -> S -> A takes 480 s plus one 60 s unloading: one full trip (2 seats) or a second trip that boards
    at most (671 - 540) / 60 = 2.18 residents in all, so 2 residents; boarding seconds at most max(120, 131) = 131."""
    inst, ss = tiny()
    net = FlowNetwork(inst, Reach(inst, ss), delta_s=60)
    a = next(i for i, st in enumerate(net.sites) if st.id == "A")
    lim = net.trip_limits("V", a)
    assert lim["W"] == pytest.approx(671.0, abs=1e-3) and lim["G"] == 540.0
    assert lim["n"][0] == 2 and lim["secs"] == pytest.approx(131.0, abs=1e-3)
    b = next(i for i, st in enumerate(net.sites) if st.id == "B")
    assert net.trip_limits("V", b)["n"][0] >= 3                       # B closes late: no cut there


def test_trip_limits_do_not_separate_trips_at_a_facility_with_a_shelter_on_site():
    """A shelter on the facility's node: trips need not be apart in time, so only the boarding time limits what one
    vehicle boards there (the limit must not stop at one load)."""
    inst, ss = tiny()
    sh = inst.shelters[0].model_copy(update={"id": "S0", "node": inst.facilities[0].node})
    inst = inst.model_copy(update={"shelters": [*inst.shelters, sh]})
    net = FlowNetwork(inst, Reach(inst, ss), delta_s=40)
    a = next(i for i, st in enumerate(net.sites) if st.id == "A")
    lim = net.trip_limits("V", a)
    assert lim["G"] == pytest.approx(60.0)                           # no travel, one unloading
    assert lim["n"][0] >= 3 and lim["n"][0] > inst.vehicles[0].seats


@pytest.mark.parametrize("seed", (2, 9, 17))
def test_free_space_and_trip_cuts_only_lower_the_lp_value(seed):
    inst, ss0, _ = random_case(seed)
    ss = persistent(ss0)
    rh = Reach(inst, ss)
    vals = {}
    for fs, tc in ((False, False), (True, False), (True, True)):
        m = FlowNetwork(inst, rh, delta_s=60, free_space=fs, trip_cuts=tc).build()
        vals[(fs, tc)] = lp_value(solve_lp(m.arrays(), time_limit=60.0, crossover=True))
    assert vals[(True, False)] <= vals[(False, False)] + 1e-6
    assert vals[(True, True)] <= vals[(True, False)] + 1e-6


def test_dropping_dominated_moves_keeps_the_lp_optimum():
    for seed in (3, 8, 21):
        inst, ss0, _ = random_case(seed)
        ss = persistent(ss0)
        rh = Reach(inst, ss)
        vals = []
        for prune in (False, True):
            m = FlowNetwork(inst, rh, delta_s=60, prune_dominated=prune).build()
            vals.append(lp_value(solve_lp(m.arrays(), time_limit=60.0, crossover=True)))
        assert vals[0] == pytest.approx(vals[1], abs=1e-6), (seed, vals)


# ----------------------------------------------------------------------------- certificate
def test_weak_duality_certificate_holds_for_any_duals():
    inst, ss = tiny()
    m = FlowNetwork(inst, Reach(inst, ss), delta_s=60).build()
    r = solve_lp(m.arrays(), time_limit=60.0, crossover=True)
    assert r.status == "Optimal" and r.row_dual is not None
    ub, cert = certified_value(m.arrays(), r.row_dual)
    assert ub == pytest.approx(r.objective, abs=1e-6) and cert["dual_bound_err"] < 1e-3
    rng = np.random.default_rng(0)
    for scale in (1e-3, 0.1, 1.0, 10.0):
        b, _ = dual_bound(m.arrays(), r.row_dual + rng.normal(scale=scale, size=r.row_dual.size))
        assert b >= r.objective - 1e-7
    b0, _ = dual_bound(m.arrays(), np.zeros_like(r.row_dual))    # pi = 0: every unloading at its upper bound
    assert b0 == pytest.approx(float(m.upper[m.cost > 0].sum()))


# ------------------------------------------------------------------------------- the method
def test_method_is_registered_bound_only_and_plans_nothing():
    m = get_method("e4_flow_bound")
    assert isinstance(m, E4FlowBound) and m.bound_only and m.config()["grouping"] == "auto"
    inst, ss = tiny()
    res = m.solve(inst, ss, budget_s=60.0, seed=7, deadline=time.monotonic() + 60.0)
    assert res.solution.itineraries == [] and res.best_bound == 5.0
    p = Oracle(inst, ss).check_plan(res.solution)
    assert p.delivered_total == 0 and p.not_planned_total == inst.residents_total
    assert res.diagnostics["certified"] and res.diagnostics["bound"] == 5
    with pytest.raises(ValueError):
        get_method("e4_flow_bound", grouping="nope")
    with pytest.raises(ValueError):
        get_method("e4_flow_bound", delta_s=0)


def test_size_rule_pools_vehicles_and_coarsens_the_step_on_large_instances():
    m = get_method("e4_flow_bound")
    inst, _ = tiny()
    assert m.setting(inst) == (60, "vehicle")
    many = inst.model_copy(update={"facilities": [f.model_copy(update={"id": f"F{i}"}) for i in range(11)
                                                  for f in inst.facilities[:1]]})
    assert m.setting(many) == (120, "type")


def test_only_the_resource_bound_when_the_lattice_is_incomplete():
    inst, _ = tiny()
    ig = quiet(1, 5)
    ig[0, 0, 1] = 1000.0
    ss = make_set(ig, horizon=3600.0, burn=100.0)          # the cell stops burning within the horizon
    b, info = flow_bound(inst, ss, delta_s=60)
    assert not info["certified"] and "not certified" in info["note"]
    assert b == trivial_bound(inst) == inst.residents_total


def test_pooled_vehicles_bound_is_no_tighter_than_one_commodity_per_vehicle():
    """Pooling identical vehicles relaxes vehicle identity: its value is at least the per-vehicle value."""
    for seed in (5, 13):
        inst, ss0, _ = random_case(seed)
        ss = persistent(ss0)
        twin = inst.vehicles + [inst.vehicles[0].model_copy(update={"id": "TWIN", "start_s": 0.0})]
        inst = inst.model_copy(update={"vehicles": twin})
        bv, iv = flow_bound(inst, ss, delta_s=60, grouping="vehicle", crossover=True)
        bt, it = flow_bound(inst, ss, delta_s=60, grouping="type", crossover=True)
        assert bv <= bt
        if iv.get("dual_bound") is not None and it.get("dual_bound") is not None:
            assert iv["dual_bound"] <= it["dual_bound"] + 1e-6


def test_every_trip_of_a_checked_plan_counts_toward_the_bound():
    """A hand-checked plan on the tiny instance: B3's optimal plan delivers 5, all checked, and the bound is 5."""
    inst, ss = tiny()
    res = solve("b3_mip", inst, ss, 20.0, delta_s=60)
    p = Oracle(inst, ss).check_plan(res.solution)
    assert all(t.state is State.CHECKED for v in p.vehicles for t in v.trips)
    assert p.delivered_total <= flow_bound(inst, ss, delta_s=60)[0]


def test_vehicle_starting_at_a_facility_enters_with_full_free_space():
    """Depot on a facility's node (an entry into a facility-only location): the vehicle starts empty, so it can board
    a full load there at once; the free-space rows must not stop it (bound >= what a direct plan delivers)."""
    inst, ss = tiny()
    v = inst.vehicles[0].model_copy(update={"depot": inst.facilities[1].node})    # start at B
    inst = inst.model_copy(update={"vehicles": [v]})
    b, info = flow_bound(inst, ss, delta_s=60, crossover=True)
    b1 = solve("b1_greedy", inst, ss, 20.0)
    got = Oracle(inst, ss).check_plan(b1.solution).delivered_total
    assert info["certified"] and got >= 2 and got <= b
