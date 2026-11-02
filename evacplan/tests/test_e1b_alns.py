"""E1b (E1's ALNS with incremental certification): oracle-valid plans; never fewer residents than the warm start;
unchanged warm-start itineraries never reach the oracle in the loop; each distinct changed itinerary is checked once;
in-loop oracle time counts toward the budget; the budget; determinism with an iteration cap; E1's parameters; the
certification counters added after the KILL (a relaxed-only pass is not an oracle certification; review E1b-D1).
SYNTHETIC instances only: hand-built (evacplan_testkit) and generated with seeds 9701+, outside the frozen split."""
import time

import numpy as np
import pytest

from evacplan import Oracle, State, validate_solution
from evacplan.generators import SyntheticConfig, generate
from evacplan.methods import get_method
from evacplan.methods.e1_alns import DEFAULTS, VDec
from evacplan.methods.e1b_alns import _RunB, _WarmCert
from evacplan_testkit import INF, facility, grid_graph, instance, make_set, nid, shelter, vehicle

CONFIGS = [SyntheticConfig(size="S", tightness=0.5, graph="grid", seed=9701),
           SyntheticConfig(size="S", tightness=0.8, graph="geo", seed=9702),
           SyntheticConfig(size="M", tightness=0.6, graph="grid", seed=9703)]


@pytest.fixture(scope="module")
def generated():
    return [generate(c) for c in CONFIGS]


@pytest.fixture
def oracle_calls(monkeypatch):
    """Every itinerary sent to Oracle.check_itinerary during the test, as (vehicle, its canonical JSON)."""
    calls = []
    orig = Oracle.check_itinerary

    def recording(self, itinerary):
        calls.append((itinerary.vehicle, itinerary.model_dump_json()))
        return orig(self, itinerary)

    monkeypatch.setattr(Oracle, "check_itinerary", recording)
    return calls


def solve(name, inst, ss, budget=10.0, seed=0, **cfg):
    m = get_method(name, **cfg)
    t0 = time.monotonic()
    res = m.solve(inst, ss, budget_s=budget, seed=seed, deadline=t0 + budget)
    runtime = time.monotonic() - t0
    assert "error" not in res.diagnostics, res.diagnostics.get("error")
    return res, runtime


def warm_itineraries(inst, ss) -> dict:
    """B1's plan = E1's and E1b's warm start (test_e1_alns.test_the_decode_reproduces_b1): its itineraries' canonical
    JSON per vehicle, and B1's result."""
    b1, _ = solve("b1_greedy", inst, ss)
    return {it.vehicle: it.model_dump_json() for it in b1.solution.itineraries}, b1


def tiny_case(dose=100.0):
    """test_e1_alns.tiny_case: a 3 x 7 lattice, the fire burns from the west, two facilities, one van."""
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


def warm_run(g, **cfg):
    """A finished E1b run with no search iteration: the warm start, nothing checked in the loop."""
    run = _RunB({**DEFAULTS, "max_iterations": 0, **cfg}, "e1b_alns", g.instance, g.hazard, 60.0, 0,
                time.monotonic() + 60.0)
    res = run.run()
    return run, res


# ------------------------------------------------------------------------------------------ plans
def test_returns_an_oracle_valid_plan_on_a_tiny_case():
    inst, ss = tiny_case()
    res, runtime = solve("e1b_alns", inst, ss, budget=8.0)
    sol = res.solution
    assert runtime <= 8.0 and sol.method == "e1b_alns" and sol.instance == inst.name
    assert validate_solution(inst, sol).ok
    plan = Oracle(inst, ss).check_plan(sol)
    assert plan.label == "SYNTHETIC"
    assert plan.delivered_total == boarded(sol) > 0
    assert plan.unresolved_total == plan.model_no_route_total == 0
    assert all(t.state is State.CHECKED for v in plan.vehicles for t in v.trips)
    b1, _ = solve("b1_greedy", inst, ss)
    assert plan.delivered_total >= Oracle(inst, ss).check_plan(b1.solution).delivered_total
    d = res.diagnostics
    assert d["iterations"] > 0
    inc = d["incremental"]
    assert inc["changed_vehicles"] + inc["unchanged_warm_vehicles"] == len(sol.itineraries)
    assert inc["incumbent_value_residents"] == plan.delivered_total        # nothing cut by the harness here


@pytest.mark.parametrize("k", range(len(CONFIGS)))
def test_never_fewer_residents_than_its_warm_start(generated, k):
    g = generated[k]
    inst, ss = g.instance, g.hazard
    oracle = Oracle(inst, ss)
    res, runtime = solve("e1b_alns", inst, ss, budget=8.0)
    assert runtime <= 8.0
    assert validate_solution(inst, res.solution).ok
    plan = oracle.check_plan(res.solution)
    _, b1 = warm_itineraries(inst, ss)
    p1 = oracle.check_plan(b1.solution)
    assert plan.delivered_total >= p1.delivered_total
    assert plan.delivered_total + plan.unresolved_total + plan.model_no_route_total + plan.not_planned_total \
        == inst.residents_total
    # the incumbent's value counts changed itineraries with the oracle's numbers and unchanged warm-start ones with
    # their relaxed numbers; a relaxed count is never below the oracle's, so the harness can only confirm or lower it
    assert plan.delivered_total <= res.diagnostics["incremental"]["incumbent_value_residents"]


# ------------------------------------------------------------------------------ the in-loop oracle
def test_certify_sends_only_changed_itineraries_to_the_oracle(generated, oracle_calls):
    """A candidate with one changed vehicle and the other vehicles' warm-start itineraries: only the changed
    itinerary reaches the oracle, once; the estimate counts it alone, and nothing once it is cached."""
    g = generated[2]
    run, res = warm_run(g)
    assert oracle_calls == [] and run.oracle_checks == 0               # no search: nothing checked in the loop
    assert res.diagnostics["incremental"]["changed_vehicles"] == 0 and not res.diagnostics["certified"]
    # the warm run's one certification pass valued only warm-start itineraries (review E1b-D1)
    assert (run.certifications, run.certifications_oracle, run.certifications_relaxed_only) == (1, 0, 1)
    warm = run.warm
    assert run._estimate(warm) == 0.0
    multi = [v for v, d in enumerate(warm.vd) if len(d.outs) >= 2]
    assert len([v for v, d in enumerate(warm.vd) if d.outs]) >= 2 and multi
    v = multi[0]
    st = warm.copy()
    run._set_vehicle(st, v, VDec(run.net, v, warm.vd[v].outs[:-1]))   # drop vehicle v's last trip
    assert not run.is_warm(v, st.vd[v]) and all(run.is_warm(u, d) for u, d in enumerate(st.vd) if u != v and d.outs)
    assert run._estimate(st) == pytest.approx(st.vd[v].legs * run.s_per_leg * DEFAULTS["oracle_safety"])
    got = run.certify(st, time.monotonic() + 60.0)
    assert got is not None
    assert [c[0] for c in oracle_calls] == [run.net.vid[v]]
    assert (run.certifications, run.certifications_oracle, run.certifications_relaxed_only) == (2, 1, 1)
    assert run.relaxed_itineraries(got[0]) == len([u for u, d in enumerate(st.vd) if d.outs]) - 1   # all but v
    assert run._estimate(st) == 0.0
    assert run.certify(st, time.monotonic() + 60.0) is not None and len(oracle_calls) == 1     # cached
    assert (run.certifications_oracle, run.certifications_relaxed_only) == (2, 1)    # a cached verdict is the oracle's
    for u, d in enumerate(st.vd):
        if d.outs:
            assert isinstance(run.cert[(u, d.trips)], _WarmCert) == (u != v)


def test_a_warm_only_run_counts_no_oracle_certification(generated, oracle_calls):
    """Review E1b-D1: with no search iteration, E1's flow certifies the warm start, which E1b values relaxed. E1's
    count shows that pass as a certification (kept for comparability); the diagnostics added after the KILL show
    that the oracle checked nothing, the plan is not certified, and the incumbent's itineraries were all valued
    relaxed."""
    run, res = warm_run(generated[2])
    d = res.diagnostics
    assert oracle_calls == [] and d["oracle_calls"] == 0 and d["stop"] == "max_iterations"
    kept = d["incremental"]["unchanged_warm_vehicles"]
    assert kept >= 2 and d["incremental"]["changed_vehicles"] == 0
    assert d["certifications"] == d["certifications_relaxed_only"] == 1
    assert d["certifications_oracle"] == 0
    assert d["certified"] is False and d["delivered_certified"] is None
    assert [(e[0], e[2], e[3]) for e in d["incumbents"]] == [(0, d["warm_planned"], "warm")]
    assert d["incumbent_relaxed_itineraries"] == [kept]                 # every itinerary of that incumbent relaxed


def test_unchanged_warm_itineraries_are_never_checked_and_changed_ones_once(generated, oracle_calls):
    """A whole run (iteration cap): no itinerary sent to the oracle is a warm-start itinerary of its vehicle, no
    itinerary is sent twice, and every returned itinerary is either a warm-start one (left to the harness) or one
    the oracle checked in the loop."""
    exercised = 0
    for g in generated[:2]:
        oracle_calls.clear()
        inst, ss = g.instance, g.hazard
        res, _ = solve("e1b_alns", inst, ss, budget=60.0, seed=1, max_iterations=300)
        warm, _ = warm_itineraries(inst, ss)
        exercised += len(oracle_calls)
        assert not any(warm.get(vid) == acts for vid, acts in oracle_calls)
        assert len(set(oracle_calls)) == len(oracle_calls) == res.diagnostics["oracle_calls"]
        prov = res.solution.provenance
        d = res.diagnostics                                # the counters added after the KILL (review E1b-D1)
        assert d["certifications_oracle"] + d["certifications_relaxed_only"] <= d["certifications"]
        assert len(d["incumbent_relaxed_itineraries"]) == len(d["incumbents"])
        if prov["checked_in_loop"]:                        # a changed itinerary was certified in the loop
            assert d["certifications_oracle"] >= 1
            assert d["incumbent_relaxed_itineraries"][-1] == len(prov["unchanged_warm_start"])
        plan = Oracle(inst, ss).check_plan(res.solution)
        for it, v in zip(res.solution.itineraries, plan.vehicles):
            acts = it.model_dump_json()
            if it.vehicle in prov["unchanged_warm_start"]:
                assert warm[it.vehicle] == acts
            else:                                          # checked in the loop: every trip kept is checked
                assert it.vehicle in prov["checked_in_loop"] and (it.vehicle, acts) in oracle_calls
                assert all(t.state is State.CHECKED for t in v.trips)
    assert exercised, "no run sent a changed itinerary to the oracle: the test exercises nothing"


def test_in_loop_oracle_time_counts_toward_the_budget(generated, monkeypatch):
    """A slow oracle (0.25 s more per itinerary): E1b books it as oracle time inside its own runtime, raises its cost
    estimate, and still returns within the budget."""
    orig = Oracle.check_itinerary

    def slow(self, itinerary):
        time.sleep(0.25)
        return orig(self, itinerary)

    monkeypatch.setattr(Oracle, "check_itinerary", slow)
    g = generated[0]
    res, runtime = solve("e1b_alns", g.instance, g.hazard, budget=8.0)
    d = res.diagnostics
    assert runtime <= 8.0, (runtime, d["time_s"])
    assert d["oracle_calls"] >= 1
    assert d["time_s"]["oracle"] >= 0.25 * d["oracle_calls"]
    assert d["time_s"]["oracle"] <= d["time_s"]["total"] <= runtime
    assert d["oracle_s_per_leg"] > DEFAULTS["oracle_s_per_leg0"]          # the measured cost replaced the prior
    assert validate_solution(g.instance, res.solution).ok


def test_respects_the_budget(generated):
    """As E1 (test_e1_alns.test_respects_the_budget): the setup (Reach and the latest-departure sweep, booked in
    time_s.warm_start) cannot be interrupted; everything after it stops at the deadline."""
    for g, budget in ((generated[0], 1.5), (generated[2], 4.0)):
        res, runtime = solve("e1b_alns", g.instance, g.hazard, budget=budget)
        warm = res.diagnostics["time_s"]["warm_start"]
        assert runtime <= max(budget, warm + 0.1), (runtime, warm)
        assert validate_solution(g.instance, res.solution).ok
    for g in generated:
        res, runtime = solve("e1b_alns", g.instance, g.hazard, budget=6.0)
        assert runtime <= 6.0, (runtime, res.diagnostics["time_s"])
        assert validate_solution(g.instance, res.solution).ok
    g = generated[2]
    m = get_method("e1b_alns")                             # a budget already spent still returns a valid plan
    res = m.solve(g.instance, g.hazard, budget_s=1.0, seed=0, deadline=time.monotonic() - 10.0)
    assert validate_solution(g.instance, res.solution).ok and res.diagnostics["iterations"] == 0
    assert "error" not in res.diagnostics


def test_deterministic_given_seed_and_iteration_cap(generated):
    g = generated[0]
    a, _ = solve("e1b_alns", g.instance, g.hazard, budget=60.0, seed=3, max_iterations=40)
    b, _ = solve("e1b_alns", g.instance, g.hazard, budget=60.0, seed=3, max_iterations=40)
    assert a.diagnostics["iterations"] == b.diagnostics["iterations"] == 40
    assert a.diagnostics["stop"] == "max_iterations"
    assert a.solution == b.solution
    keys = ("accepted", "improvements", "new_best", "weights", "used", "relaxed_best", "incremental", "oracle_calls",
            "certifications", "certifications_oracle", "certifications_relaxed_only", "incumbent_relaxed_itineraries")
    assert {k: a.diagnostics[k] for k in keys} == {k: b.diagnostics[k] for k in keys}


def test_dose_is_left_to_the_oracle_for_changed_itineraries():
    """With a dose budget so small that trips near the fire fail the oracle: E1b still delivers at least B1's
    residents; a trip the harness's oracle does not check can only be on an unchanged warm-start itinerary (never
    checked in the loop, as for B2); every itinerary the search changed is oracle-checked and cut before its first
    trip that fails."""
    inst, ss = tiny_case(dose=0.02)
    oracle = Oracle(inst, ss)
    warm, b1 = warm_itineraries(inst, ss)
    p1 = oracle.check_plan(b1.solution)
    assert p1.unresolved_total + p1.model_no_route_total > 0          # the case does exercise dose
    res, runtime = solve("e1b_alns", inst, ss, budget=8.0, max_iterations=400)
    plan = oracle.check_plan(res.solution)
    assert plan.delivered_total >= p1.delivered_total
    for it, v in zip(res.solution.itineraries, plan.vehicles):
        if any(t.state is not State.CHECKED for t in v.trips):
            assert warm[it.vehicle] == it.model_dump_json()
            assert it.vehicle in res.solution.provenance["unchanged_warm_start"]
        else:
            assert v.delivered.total == sum(a.counts.total for a in it.actions if a.kind == "board")


def test_configuration_is_e1s():
    """E1b runs E1's pre-registered parameters, untuned."""
    assert get_method("e1b_alns").config() == get_method("e1_alns").config()
    with pytest.raises(ValueError):
        get_method("e1b_alns", dose_weight=1.0)
    with pytest.raises(ValueError):
        get_method("e1b_alns", remove_min=0.5, remove_max=0.2)
