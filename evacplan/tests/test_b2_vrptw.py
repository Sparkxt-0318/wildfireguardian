"""B2 (OR-Tools VRPTW with pickup and delivery, per-class capacities, static windows from the per-facility
latest departures): valid plans within the budget, every planned trip oracle-checked, departures by the
deadlines, the hand-worked coordination example, chunking. SYNTHETIC instances only (seeds 9601+)."""
import time

import pytest

from evacplan import Oracle, State, validate_solution
from evacplan.deadlines import class_deadlines
from evacplan.generators import SyntheticConfig, generate
from evacplan.methods import canonical, get_method
from evacplan.methods.b2_vrptw import chunk_sizes
from evacplan.methods.dispatch import latest_departures
from evacplan.reach import Reach
from test_baselines import _departures, gap_instance

CONFIGS = [SyntheticConfig(size="S", tightness=0.5, graph="grid", seed=9601),
           SyntheticConfig(size="M", tightness=0.6, graph="geo", seed=9602)]


@pytest.fixture(scope="module")
def generated():
    return [generate(c) for c in CONFIGS]


def solve(inst, ss, budget, **cfg):
    m = get_method("B2", **cfg)
    t0 = time.monotonic()
    res = m.solve(inst, ss, budget_s=budget, seed=0, deadline=t0 + budget)
    return res, time.monotonic() - t0


@pytest.mark.parametrize("k", range(len(CONFIGS)))
def test_b2_plans_are_valid_checked_and_within_budget(generated, k):
    g = generated[k]
    inst, ss = g.instance, g.hazard
    budget = 8.0
    res, runtime = solve(inst, ss, budget)
    assert runtime <= budget + 0.5
    sol = res.solution
    assert sol.method == "b2_vrptw" and sol.instance == inst.name
    assert validate_solution(inst, sol).ok                   # capacities, release, windows, shifts, waits, turns
    plan = Oracle(inst, ss).check_plan(sol)
    boarded = sum(a.counts.total for it in sol.itineraries for a in it.actions if a.kind == "board")
    assert plan.delivered_total == boarded > 0               # every planned trip is checked in all K members
    assert plan.unresolved_total == plan.model_no_route_total == 0
    assert plan.delivered_total + plan.not_planned_total == inst.residents_total
    assert all(t.state is State.CHECKED for v in plan.vehicles for t in v.trips)
    info = res.info
    assert info["realization"]["residents_realized"] == plan.delivered_total <= info["residents_served_static"]
    assert info["residents_served_static"] <= info["residents_in_requests"] <= inst.residents_total
    # how deep the seedless, time-limited search got (recorded in the harness row's config)
    diag = res.diagnostics
    assert diag["solutions"] >= 1 and diag["objective"] == info["objective"]
    assert 0 < diag["search_s"] <= diag["time_limit_s"] + 0.5


def test_b2_static_windows_come_from_the_latest_departures(generated):
    g = generated[1]
    inst, ss = g.instance, g.hazard
    D = latest_departures(inst, Reach(inst, ss))
    m = get_method("B2")
    fac = {f.id: f for f in inst.facilities}
    reqs = m.requests(inst, D)
    for (fid, c), n in {(f.id, c): f.residents.vector()[c] for f in inst.facilities for c in range(3)}.items():
        got = sum(k for f2, c2, k in reqs if (f2, c2) == (fid, c))
        assert got == (n if (fid, c) in D and any(v.capacity()[c] for v in inst.vehicles) else 0)
    for fid, c, n in reqs:                                    # each chunk can board between release and deadline
        f = fac[fid]
        assert f.release_s + n * f.boarding_s.vector()[c] <= D[(fid, c)]
        assert n <= max(v.capacity()[c] for v in inst.vehicles)
    res, _ = solve(inst, ss, 6.0)
    leave = {(d.facility, ["ambulatory", "wheelchair", "bedbound"].index(d.mobility_class)): d.leave_by_s
             for d in class_deadlines(inst, ss)}
    deps = _departures(res.solution)
    assert deps and all(d <= leave[(f, c)] for f, c, d in deps)


def test_b2_coordinates_the_hand_worked_gap_instance():
    inst, ss = gap_instance()                                 # B1 delivers all 4, B0 only 2 (test_baselines)
    res, _ = solve(inst, ss, 3.0)
    plan = Oracle(inst, ss).check_plan(res.solution)
    assert plan.delivered_total == 4 and plan.not_planned_total == 0


def test_b2_with_a_spent_budget_still_returns_a_valid_plan():
    inst, ss = gap_instance()
    m = get_method("b2_vrptw")
    t0 = time.monotonic()
    res = m.solve(inst, ss, budget_s=1.0, seed=0, deadline=t0 - 10.0)
    assert time.monotonic() - t0 < 3.0
    assert validate_solution(inst, res.solution).ok


def test_chunks_and_config():
    assert chunk_sizes(15, 8) == [8, 4, 2, 1]
    assert chunk_sizes(16, 8) == [8, 8]
    assert chunk_sizes(3, 2) == [2, 1]
    assert chunk_sizes(5, 1) == [1] * 5
    assert chunk_sizes(0, 8) == []
    assert canonical("B2") == canonical("b2") == "b2_vrptw" and canonical("B3") == "b3_mip"
    cfg = get_method("B2").config()
    assert cfg["first_solution"] == "PARALLEL_CHEAPEST_INSERTION" and cfg["metaheuristic"] == "GUIDED_LOCAL_SEARCH"
    with pytest.raises(ValueError):
        get_method("B2", metaheuristic="ANNEALING_PLEASE")
    with pytest.raises(ValueError):
        get_method("B2", max_chunk=0)
