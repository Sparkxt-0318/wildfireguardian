"""Baselines B0 (every facility alone, today's planner logic) and B1 (EDF insertion): valid plans,
oracle-checked counts, consistency with the deadlines, and a hand-worked coordination gap.
SYNTHETIC instances only (generator seeds 9401+, outside the frozen split)."""
import time

import pytest

from evacplan import Oracle, State, validate_solution
from evacplan.deadlines import class_deadlines
from evacplan.generators import SyntheticConfig, generate
from evacplan.methods import get_method
from evacplan.methods.b0_independent import PLANNER_STEP_S, PlannerLogic
from evacplan.methods.dispatch import Dispatcher
from evacplan.reach import Reach
from evacplan_testkit import facility, grid_graph, instance, make_set, nid, quiet, shelter, vehicle

METHODS = ("b0_independent", "b1_greedy")
CONFIGS = [SyntheticConfig(size="S", tightness=0.5, graph="grid", seed=9401),
           SyntheticConfig(size="S", tightness=0.8, graph="geo", seed=9402),
           SyntheticConfig(size="M", tightness=0.6, graph="grid", seed=9403)]


@pytest.fixture(scope="module")
def generated():
    return [generate(c) for c in CONFIGS]


def solve(name, inst, ss, budget=60.0, **cfg):
    m = get_method(name, **cfg)
    t0 = time.monotonic()
    res = m.solve(inst, ss, budget_s=budget, seed=0, deadline=t0 + budget)
    return res, time.monotonic() - t0


@pytest.mark.parametrize("name", METHODS)
@pytest.mark.parametrize("k", range(len(CONFIGS)))
def test_plans_are_valid_and_every_trip_is_checked(generated, name, k):
    g = generated[k]
    inst, ss = g.instance, g.hazard
    res, runtime = solve(name, inst, ss)
    sol = res.solution
    assert runtime < 60 and sol.instance == inst.name and sol.method == name
    assert validate_solution(inst, sol).ok                   # capacities, release, windows, shifts, waits, turns
    plan = Oracle(inst, ss).check_plan(sol)
    assert plan.label == "SYNTHETIC"
    boarded = sum(a.counts.total for it in sol.itineraries for a in it.actions if a.kind == "board")
    assert plan.delivered_total == boarded > 0               # every planned trip is checked in all K members
    assert plan.unresolved_total == plan.model_no_route_total == 0
    assert plan.delivered_total + plan.not_planned_total == inst.residents_total
    assert all(t.state is State.CHECKED for v in plan.vehicles for t in v.trips)
    again, _ = solve(name, inst, ss)
    assert again.solution == sol                              # deterministic


def _departures(sol):
    """(facility, class, departure after boarding) for every boarding."""
    out = []
    for it in sol.itineraries:
        acts = it.actions
        for j, a in enumerate(acts):
            if a.kind == "board":
                d = next(b.depart_s for b in acts[j + 1:] if b.kind == "drive")
                out += [(a.facility, c, d) for c in range(3) if a.counts.vector()[c]]
    return out


def test_b1_leaves_by_the_facility_deadlines(generated):
    g = generated[2]
    inst, ss = g.instance, g.hazard
    res, _ = solve("b1_greedy", inst, ss)
    leave = {(d.facility, ["ambulatory", "wheelchair", "bedbound"].index(d.mobility_class)): d.leave_by_s
             for d in class_deadlines(inst, ss)}
    deps = _departures(res.solution)
    assert deps and all(d <= leave[(f, c)] for f, c, d in deps)
    assert res.info["deadlines"] == {f"{f}/{c}": int(v) for (f, c), v in sorted(leave.items()) if v is not None}


def test_b0_departs_on_the_planner_grid_by_the_contiguous_deadline(generated):
    g = generated[0]
    inst, ss = g.instance, g.hazard
    res, _ = solve("b0_independent", inst, ss)
    pl = PlannerLogic(Dispatcher(inst, Reach(inst, ss)))
    deps = _departures(res.solution)
    assert deps
    for f, c, d in deps:
        assert d % PLANNER_STEP_S == 0
        assert d <= pl.deadline(f, frozenset([c]))
    assert len(pl.candidates(inst.facilities[0].id, frozenset([0]))) == min(3, len(inst.shelters))


def gap_instance():
    """Hand-worked coordination gap (1 x 5 road, 100 m cells, 50 s per edge, one van at the shelter):
    A (n0_0, release 200) lies west of cell (0,1), which burns from 1000, so A's last departure is 924
    (the second edge east touches (0,1) until 75 s after leaving A); B (n0_2, release 0) is never
    threatened. B1 (EDF): A first (van arrives 200, leaves 220), then B: 4 delivered. B0: the planner's
    contiguous deadline for A is the 600 s offset; B books the van for 100 and A for 200, so the van
    serves B first (leaves B at the 600 s offset) and reaches A at 910, too late: 2 delivered."""
    ig = quiet(1, 5)
    ig[0, 0, 1] = 1000.0
    ss = make_set(ig, horizon=5000.0, burn=1e9)
    inst = instance(grid_graph(1, 5), facilities=[facility("A", nid(0, 0), amb=2, release=200.0),
                                                  facility("B", nid(0, 2), amb=2, release=0.0)],
                    vehicles=[vehicle("V", nid(0, 4))], shelters=[shelter("S", nid(0, 4))])
    return inst, ss


def test_hand_worked_coordination_gap():
    inst, ss = gap_instance()
    oracle = Oracle(inst, ss)
    leave = {d.facility: d.leave_by_s for d in class_deadlines(inst, ss)}
    assert leave["A"] == 924.0
    b1, _ = solve("b1_greedy", inst, ss)
    p1 = oracle.check_plan(b1.solution)
    assert p1.delivered_total == 4 and [a.facility for a in b1.solution.itineraries[0].actions if a.kind == "board"] \
        == ["A", "B"]
    assert _departures(b1.solution)[0] == ("A", 0, 220.0)
    b0, _ = solve("b0_independent", inst, ss)
    p0 = oracle.check_plan(b0.solution)
    assert p0.delivered_total == 2 and p0.not_planned == {"A": p0.not_planned["A"]} and p0.not_planned_total == 2
    assert b0.info["planner_deadlines"]["A/0"] == 600 and b0.info["dropped_bookings"] == 1
    assert _departures(b0.solution) == [("B", 0, 600.0)]


def test_nothing_to_do_and_tiny_budgets():
    ig = quiet(1, 5)
    ig[0, 0, 0] = -100.0                                    # the only facility burns from before issue
    ss = make_set(ig, horizon=5000.0, burn=1e9)
    inst = instance(grid_graph(1, 5), facilities=[facility("A", nid(0, 0), amb=2)],
                    vehicles=[vehicle("V", nid(0, 4))], shelters=[shelter("S", nid(0, 4))])
    for name in METHODS:
        res, _ = solve(name, inst, ss)
        assert res.solution.itineraries == []
        assert Oracle(inst, ss).check_plan(res.solution).not_planned_total == 2
    inst, ss = gap_instance()
    for name in METHODS:                                    # a budget already spent still returns a valid plan
        m = get_method(name)
        res = m.solve(inst, ss, budget_s=1.0, seed=0, deadline=time.monotonic() - 10.0)
        assert validate_solution(inst, res.solution).ok


def test_method_configs_are_recorded_and_checked():
    assert get_method("b1_greedy").config() == {"vehicle_rule": "per_resident", "repair": False}
    assert get_method("b0_independent").config()["step_s"] == 600
    with pytest.raises(ValueError):
        get_method("b1_greedy", vehicle_rule="nearest")
    with pytest.raises(ValueError):
        get_method("b0_independent", deadline="sometimes")
    inst, ss = gap_instance()
    res, _ = solve("b1_greedy", inst, ss, repair=True)        # the oracle repair finds nothing to cut here
    assert res.info["repair"]["trips_cut"] == 0 and res.info["repair"]["vehicles_checked"] == 1
