"""E1 (ALNS with the oracle in the loop): oracle-valid plans, never fewer residents than its warm start, the
budget, determinism with an iteration cap, the decode reproducing B1, and oracle certification of dose.
SYNTHETIC instances only: hand-built (evacplan_testkit) and generated with seeds 9701+, outside the frozen split."""
import time

import numpy as np
import pytest

from evacplan import Oracle, State, validate_solution
from evacplan.generators import SyntheticConfig, generate
from evacplan.methods import get_method
from evacplan.methods.dispatch import latest_departures
from evacplan.methods.e1_alns import DEFAULTS, VDec, _Net, _Run
from evacplan.reach import Reach
from evacplan.schema import Itinerary
from evacplan_testkit import INF, facility, grid_graph, instance, make_set, nid, shelter, vehicle

CONFIGS = [SyntheticConfig(size="S", tightness=0.5, graph="grid", seed=9701),
           SyntheticConfig(size="S", tightness=0.8, graph="geo", seed=9702),
           SyntheticConfig(size="M", tightness=0.6, graph="grid", seed=9703)]


@pytest.fixture(scope="module")
def generated():
    return [generate(c) for c in CONFIGS]


def solve(name, inst, ss, budget=10.0, seed=0, **cfg):
    m = get_method(name, **cfg)
    t0 = time.monotonic()
    res = m.solve(inst, ss, budget_s=budget, seed=seed, deadline=t0 + budget)
    return res, time.monotonic() - t0


def tiny_case(dose=100.0):
    """3 x 7 lattice (100 m cells, 50 s per edge). The fire burns from the west: column 0 from 600 s, column 1
    from 1500 s, column 2 from 2600 s, and keeps burning. Facility A (n1_1) is threatened first, B (n1_3) later;
    the shelter and the van's depot are in the east."""
    ig = np.full((1, 3, 7), INF)
    ig[0, :, 0], ig[0, :, 1], ig[0, :, 2] = 600.0, 1500.0, 2600.0
    ss = make_set(ig, horizon=6000.0, burn=1e9)
    inst = instance(grid_graph(3, 7), facilities=[facility("A", nid(1, 1), amb=6, wc=1, release=0.0),
                                                  facility("B", nid(1, 3), amb=5, bed=1, release=60.0)],
                    vehicles=[vehicle("V", nid(2, 6), seats=4, wc=1, stretchers=1)],
                    shelters=[shelter("S", nid(1, 6))], dose=dose)
    return inst, ss


def boarded(sol):
    return sum(a.counts.total for it in sol.itineraries for a in it.actions if a.kind == "board")


def test_returns_an_oracle_valid_plan_on_a_tiny_case():
    inst, ss = tiny_case()
    res, runtime = solve("e1_alns", inst, ss, budget=8.0)
    sol = res.solution
    assert runtime <= 8.0 and sol.method == "e1_alns" and sol.instance == inst.name
    assert validate_solution(inst, sol).ok
    plan = Oracle(inst, ss).check_plan(sol)
    assert plan.label == "SYNTHETIC"
    assert plan.delivered_total == boarded(sol) > 0
    assert plan.unresolved_total == plan.model_no_route_total == 0
    assert all(t.state is State.CHECKED for v in plan.vehicles for t in v.trips)
    d = res.diagnostics
    assert d["certified"] and d["delivered_certified"] == plan.delivered_total
    assert d["iterations"] > 0 and d["oracle_calls"] >= 1
    b1, _ = solve("b1_greedy", inst, ss)
    assert plan.delivered_total >= Oracle(inst, ss).check_plan(b1.solution).delivered_total


@pytest.mark.parametrize("k", range(len(CONFIGS)))
def test_never_fewer_residents_than_its_warm_start(generated, k):
    g = generated[k]
    inst, ss = g.instance, g.hazard
    oracle = Oracle(inst, ss)
    res, runtime = solve("e1_alns", inst, ss, budget=8.0)
    assert runtime <= 8.0
    assert validate_solution(inst, res.solution).ok
    plan = oracle.check_plan(res.solution)
    b1, _ = solve("b1_greedy", inst, ss)
    p1 = oracle.check_plan(b1.solution)
    assert plan.delivered_total >= p1.delivered_total
    assert plan.delivered_total + plan.unresolved_total + plan.model_no_route_total + plan.not_planned_total \
        == inst.residents_total
    if res.diagnostics["certified"]:                       # a certified incumbent: every trip is checked
        assert res.diagnostics["delivered_certified"] == plan.delivered_total == boarded(res.solution)
        assert plan.unresolved_total == plan.model_no_route_total == 0


def test_respects_the_budget(generated):
    for g, budget in ((generated[0], 1.5), (generated[2], 4.0)):
        res, runtime = solve("e1_alns", g.instance, g.hazard, budget=budget)
        assert runtime <= budget
        assert validate_solution(g.instance, res.solution).ok
    g = generated[2]
    m = get_method("e1_alns")                              # a budget already spent still returns a valid plan
    res = m.solve(g.instance, g.hazard, budget_s=1.0, seed=0, deadline=time.monotonic() - 10.0)
    assert validate_solution(g.instance, res.solution).ok and res.diagnostics["iterations"] == 0


def test_deterministic_given_seed_and_iteration_cap(generated):
    g = generated[0]
    a, _ = solve("e1_alns", g.instance, g.hazard, budget=60.0, seed=3, max_iterations=40)
    b, _ = solve("e1_alns", g.instance, g.hazard, budget=60.0, seed=3, max_iterations=40)
    assert a.diagnostics["iterations"] == b.diagnostics["iterations"] == 40
    assert a.diagnostics["stop"] == "max_iterations"
    assert a.solution == b.solution
    keys = ("accepted", "improvements", "new_best", "weights", "used", "relaxed_best", "delivered_certified")
    assert {k: a.diagnostics[k] for k in keys} == {k: b.diagnostics[k] for k in keys}


def test_the_decode_reproduces_b1(generated):
    """E1's warm start: B1's trips decoded by E1's machinery give B1's own plan, action for action."""
    for g in generated:
        inst, ss = g.instance, g.hazard
        b1, _ = solve("b1_greedy", inst, ss)
        run = _Run({**DEFAULTS}, "e1_alns", inst, ss, 60.0, 0, time.monotonic() + 60.0)
        rh = Reach(inst, ss)
        D = latest_departures(inst, rh)
        net = run.net = _Net(inst, rh, D)
        dsp = run._warm_start(rh, D, time.monotonic() + 60.0)
        its = []
        for v, vid in enumerate(net.vid):
            keys = [(((net.fidx[tr.facility], tuple(tr.counts)),), net.sidx[tr.delivery.shelter])
                    for tr in dsp.vs[vid].trips]
            vd = VDec(net, v, net.decode(v, net.vnode[v], net.vstart[v], keys))
            assert len(vd.outs) == len(keys)
            if vd.outs:
                its.append(Itinerary(vehicle=vid, actions=net.emit(v, vd)))
        assert its == b1.solution.itineraries


def test_dose_is_left_to_the_oracle_and_certified():
    """With a dose budget so small that trips near the fire cannot be certified, B1's plan has unresolved
    residents; E1 returns only oracle-certified trips (every trip checked) and still delivers at least as many."""
    inst, ss = tiny_case(dose=0.02)
    oracle = Oracle(inst, ss)
    b1, _ = solve("b1_greedy", inst, ss)
    p1 = oracle.check_plan(b1.solution)
    assert p1.unresolved_total + p1.model_no_route_total > 0          # the case does exercise dose
    res, runtime = solve("e1_alns", inst, ss, budget=8.0)
    plan = oracle.check_plan(res.solution)
    assert runtime <= 8.0 and res.diagnostics["certified"]
    assert plan.unresolved_total == plan.model_no_route_total == 0
    assert plan.delivered_total == boarded(res.solution) >= p1.delivered_total
    assert res.diagnostics["oracle_cut_residents"] > 0
    assert any(c.startswith("DOSE") for c in res.diagnostics["oracle_cut_by_cause"])


def test_configuration_is_recorded_and_checked():
    cfg = get_method("e1_alns").config()
    assert cfg["segment"] == 100 and cfg["reaction"] == 0.1 and cfg["scores"] == [33.0, 9.0, 13.0]
    assert cfg["remove_min"] == 0.1 and cfg["remove_max"] == 0.4 and cfg["p_shaw"] == 6 and cfg["p_worst"] == 3
    assert cfg["noise"] == 0.025 and cfg["start_worse"] == 0.05 and cfg["cooling"] == 0.99975
    with pytest.raises(ValueError):
        get_method("e1_alns", dose_weight=1.0)
    with pytest.raises(ValueError):
        get_method("e1_alns", remove_min=0.5, remove_max=0.2)
