"""E2, column generation with a proven bound: plans the oracle accepts, a bound that covers the brute-force optimum of
tiny instances and every plan the oracle checks on random small instances (for the method's prices and for arbitrary
nonnegative prices), the clock DP's relaxed optimum covering its restricted one and the values of the paths it reads
off, the budget, determinism, and no ``highspy`` in the main process. Added after the dev results (batch-2 review):
the in-budget oracle repair path on a dose-limited case (E2-D3), and no worker call outlasting the deadline, with a
HiGHS child that stops answering (E2-D4). SYNTHETIC instances only (generated ones use seeds 9801+, outside the
split)."""
from __future__ import annotations

import math
import os
import signal
import sys
import time

import numpy as np
import pytest

from evacplan import Oracle, State, validate_solution
from evacplan.generators import SyntheticConfig, generate
from evacplan.methods import get_method
from evacplan.methods.e2_colgen import CALL_MARGIN_S, Column, E2ColGen, _Run, cap_sequence, path_to_sequence
from evacplan.methods.e2_pricing import RELAXED, RESTRICTED, BatchDP, clock_units
from evacplan.methods.e2_worker import HighsWorker, WorkerError
from evacplan.methods.flow_bound import FlowNetwork
from evacplan.methods.realize import Sequence, Stop, Unit
from evacplan.methods.timexp import trivial_bound
from evacplan.reach import Reach
from evacplan_testkit import make_set, quiet, random_case
from test_b3_mip import brute_force, tiny
from test_e1b_alns import tiny_case
from test_flow_bound import persistent


def solve(name, inst, ss, budget, seed=0, **cfg):
    m = get_method(name, **cfg)
    t0 = time.monotonic()
    res = m.solve(inst, ss, budget_s=budget, seed=seed, deadline=t0 + budget)
    return res, time.monotonic() - t0


def checked(inst, ss, res):
    p = Oracle(inst, ss).check_plan(res.solution)
    return p


class WorkerLog:
    """Every ``HighsWorker.call`` of a test, as (command, model, start, timeout, end, error); the child processes seen;
    and ``freeze``: the (command, model) at whose first call the child is stopped (SIGSTOP), so that it stops answering
    as a HiGHS run that overruns its time limit would. The real call then times out and kills the child."""

    def __init__(self):
        self.calls: list[tuple] = []
        self.procs: list = []
        self.freeze: tuple | None = None
        self.frozen = False


@pytest.fixture
def worker_log(monkeypatch):
    log = WorkerLog()
    orig = HighsWorker.call

    def recording(self, cmd, *, timeout, **payload):
        if self.proc is not None and all(p is not self.proc for p in log.procs):
            log.procs.append(self.proc)
        if self.proc is not None and not log.frozen and log.freeze == (cmd, payload.get("model")):
            log.frozen = True
            os.kill(self.proc.pid, signal.SIGSTOP)
        t, err = time.monotonic(), None
        try:
            return orig(self, cmd, timeout=timeout, **payload)
        except WorkerError as exc:
            err = exc
            raise
        finally:
            log.calls.append((cmd, payload.get("model"), t, float(timeout), time.monotonic(), err))

    monkeypatch.setattr(HighsWorker, "call", recording)
    yield log
    for p in log.procs:                                  # never leave a child behind, even when a test fails
        if p.poll() is None:
            p.kill()
            p.wait()


def assert_no_call_past(log: WorkerLog, deadline: float) -> None:
    """No worker call could make the parent wait past ``deadline``: each call's timeout (at least the worker's 0.05 s
    floor) ends by then, and each call did end by then."""
    assert log.calls
    for cmd, model, t, timeout, end, _ in log.calls:
        assert t + max(0.05, timeout) <= deadline, (cmd, model, round(deadline - t, 3), timeout)
        assert end <= deadline, (cmd, model, round(end - deadline, 3))


# ------------------------------------------------------------------------------------------- tiny: exact optimum
def test_tiny_instance_optimal_plan_and_tight_bound():
    inst, ss = tiny()
    opt, _ = brute_force(inst, ss)
    assert opt == 5
    res, runtime = solve("e2_colgen", inst, ss, 30.0)
    assert runtime < 30.0
    p = checked(inst, ss, res)
    assert validate_solution(inst, res.solution).ok
    assert p.delivered_total <= opt <= res.best_bound <= trivial_bound(inst)
    assert res.best_bound == 5 and p.delivered_total == 5          # the plan reaches the bound: proven optimal
    assert all(t.state is State.CHECKED for v in p.vehicles for t in v.trips)
    assert res.info["certified"] and not res.info["unbounded"]
    assert "highspy" not in sys.modules                              # HiGHS only in the child process


@pytest.mark.parametrize("seed", range(10))
def test_bound_covers_brute_force_on_random_tiny_instances(seed):
    """Off-grid data (travel, boarding, unloading, release, opening, start, fire timing), as B3's and E4's tests."""
    rng = np.random.default_rng(seed)
    step = float(rng.choice([40.0, 50.0, 70.0]))
    kw = dict(step=step, board=float(rng.choice([30.0, 45.0, 90.0])), unload=float(rng.choice([20.0, 35.0, 60.0])),
              wc_unload=90.0, release=tuple(float(x) for x in rng.choice([0.0, 100.0, 250.0], size=2)),
              ignite=float(rng.choice([700.0, 1000.0, 1300.0])), fire_col=int(rng.choice([1, 3])),
              start=float(rng.choice([0.0, 30.0, 90.0])), opens=float(rng.choice([0.0, 300.0])))
    inst, ss = tiny(**kw)
    opt, _ = brute_force(inst, ss)
    res, _ = solve("e2_colgen", inst, ss, 8.0, seed=seed)
    p = checked(inst, ss, res)
    assert res.info["certified"], res.info
    assert p.delivered_total <= opt <= res.best_bound, (kw, opt, res.best_bound, res.info.get("lagrangian_bound"))
    assert p.unresolved_total == 0 and validate_solution(inst, res.solution).ok


def test_bound_holds_for_any_nonnegative_prices():
    """The Lagrangian bound needs no optimal prices: for random y >= 0 it still covers the optimum (README, steps
    1-4), here recomputed outside the method from its own rows and DP."""
    from evacplan.methods.e2_colgen import _Run
    inst, ss = tiny()
    opt, _ = brute_force(inst, ss)
    rh = Reach(inst, ss)
    net = FlowNetwork(inst, rh, delta_s=60, grouping="vehicle")
    m = E2ColGen()
    run = _Run(m, inst, ss, rh, net, seed=0, budget_s=30.0, deadline=time.monotonic() + 30.0,
               t_start=time.monotonic(), info={"resource_bound": trivial_bound(inst)})
    run._rows()
    run._batches()
    rng = np.random.default_rng(0)
    for scale in (0.0, 0.1, 0.5, 1.0, 3.0):
        for _ in range(4):
            y = np.where(run.is_conv, 0.0, rng.uniform(0.0, scale, size=len(run.rows)))
            vals, _ = run._price(RELAXED, y, extract=False)
            assert run._bound(y, vals) + 1e-9 >= opt, (scale, y, vals)


# ----------------------------------------------------------------------------------------- random small cases
@pytest.mark.parametrize("seed", range(12))
def test_bound_covers_every_checked_plan_on_random_small_instances(seed):
    """Random small instances (co-located sites, zero boarding times, windows, shifts, unknown cells), the fire made
    persistent so the network is certified: the bound covers the random plan of the case, B0, B1, (every third
    seed) B3 and E2's own plan, all checked by the oracle; E2's plan is valid."""
    inst, ss0, sol = random_case(seed)
    ss = persistent(ss0)
    res, runtime = solve("e2_colgen", inst, ss, 8.0, seed=seed)
    assert runtime <= 8.0 + 0.5
    oracle = Oracle(inst, ss)
    assert validate_solution(inst, res.solution).ok
    got = {"random": oracle.check_plan(sol).delivered_total, "e2": oracle.check_plan(res.solution).delivered_total}
    for name in ("b0_independent", "b1_greedy"):
        got[name] = oracle.check_plan(solve(name, inst, ss, 20.0)[0].solution).delivered_total
    if seed % 3 == 0:
        got["b3_mip"] = oracle.check_plan(solve("b3_mip", inst, ss, 6.0, delta_s=60)[0].solution).delivered_total
    b = res.best_bound
    assert b is not None and max(got.values()) <= b <= trivial_bound(inst), (got, b, res.info)


def test_only_the_resource_bound_when_the_lattice_is_incomplete():
    inst, _ = tiny()
    ig = quiet(1, 5)
    ig[0, 0, 1] = 1000.0
    ss = make_set(ig, horizon=3600.0, burn=100.0)                    # the cell stops burning within the horizon
    res, _ = solve("e2_colgen", inst, ss, 8.0)
    assert not res.info["certified"] and res.best_bound == trivial_bound(inst)
    assert validate_solution(inst, res.solution).ok
    assert checked(inst, ss, res).delivered_total <= res.best_bound


# ---------------------------------------------------------------------------------------------- the clock DP
def _dp_setup(inst, ss, mode, g=None):
    rh = Reach(inst, ss)
    net = FlowNetwork(inst, rh, delta_s=60, grouping="vehicle")
    vs = [v for v in inst.vehicles if any(v.id in grp.vehicles for grp in net.groups)]
    if g is None:
        g, _ = clock_units(net, vs, max_cells=24e6)
    return net, vs, BatchDP(net, vs[:1], g=g, mode=mode)


@pytest.mark.parametrize("seed", (1, 4, 7, 11))
def test_restricted_optimum_never_exceeds_the_relaxed_one_and_paths_carry_their_value(seed):
    """RESTRICTED is a restriction of RELAXED (later departures, ceil instead of floor); every path read off the table
    has the value the table gives (recomputed from its actions' profits)."""
    inst, ss0, _ = random_case(seed)
    ss = persistent(ss0)
    rng = np.random.default_rng(seed)
    net, vs, rel = _dp_setup(inst, ss, RELAXED)
    if not vs:
        pytest.skip("no vehicle can carry a class here")
    g = rel.g
    res_dp = BatchDP(net, vs[:1], g=g, mode=RESTRICTED)
    for dp in (rel, res_dp):
        assert len(dp.actions) == len({a.index for a in dp.actions})
    prof_rel = np.zeros((len(rel.actions), 1))
    prof_res = np.zeros((len(res_dp.actions), 1))
    by_key = {(a.site, a.cls): rng.uniform(-0.5, 0.2) if a.sign > 0 else rng.uniform(0.3, 1.0) for a in rel.actions}
    for a in rel.actions:
        prof_rel[a.index, 0] = by_key[(a.site, a.cls)]
    for a in res_dp.actions:
        prof_res[a.index, 0] = by_key.get((a.site, a.cls), -1.0)
    v_rel = rel.run(prof_rel)[0]
    paths_rel = rel.paths(prof_rel, per_vehicle=3, min_value=1e-9)
    v_res = res_dp.run(prof_res)[0]
    if rel.unbounded or res_dp.unbounded:
        pytest.skip("a zero-second board/unload cycle at a co-located facility and shelter: no finite optimum")
    assert v_res <= v_rel + 1e-9
    for p in paths_rel:
        val = sum(prof_rel[ev.action, 0] for ev in p.events if ev.kind == "act")
        assert val == pytest.approx(p.value, abs=1e-9)
        assert p.value <= v_rel + 1e-9
        seq, board, unload = path_to_sequence(p, rel, net)
        assert sum(board.values()) == sum(unload.values())          # every boarded resident is unloaded
        assert sum(u.n for u in seq.units) == sum(board.values())


def test_tiny_dp_at_zero_prices_is_at_least_the_single_vehicle_optimum():
    inst, ss = tiny()
    opt, _ = brute_force(inst, ss)
    net, vs, dp = _dp_setup(inst, ss, RELAXED, g=1)
    prof = np.array([[1.0 if a.sign < 0 else 0.0] for a in dp.actions])
    assert dp.run(prof)[0] >= opt


def test_cap_sequence_caps_boardings_first_come_first_served():
    seq = Sequence(vehicle="V", stops=[Stop("a", (("board", "A"),)), Stop("s", (("unload", "S"),)),
                                       Stop("a", (("board", "A"),)), Stop("s", (("unload", "S"),))],
                   units=[Unit("A", 0, 2, 0, ((1, "S", 2),)), Unit("A", 0, 2, 2, ((3, "S", 2),))])
    out = cap_sequence(seq, {("A", 0): 3})
    assert [u.n for u in out.units] == [2, 1] and out.units[1].drops == ((3, "S", 1),)
    assert cap_sequence(seq, {("A", 0): 0}) is None


# --------------------------------------------------------------------------------------- budget, determinism
@pytest.fixture(scope="module")
def m_instance():
    return generate(SyntheticConfig(size="M", tightness=0.75, graph="grid", seed=9811))


def test_respects_the_budget_and_plans_are_checked_on_a_generated_m_instance(m_instance, worker_log):
    """Also (review E2-D4): no worker call of the run (start, columns, the LP solves of the column generation, the MIP)
    could make the parent wait past the deadline."""
    inst, ss = m_instance.instance, m_instance.hazard
    budget = 20.0
    t0 = time.monotonic()
    res, runtime = solve("e2_colgen", inst, ss, budget)
    assert runtime <= budget + 0.5, runtime
    assert_no_call_past(worker_log, t0 + budget)
    kinds = {(c[0], c[1]) for c in worker_log.calls}
    assert ("solve", "lp") in kinds or res.info["rounds"] == 0, kinds
    assert ("solve", "mip") in kinds or res.info.get("mip") is None, kinds
    assert res.diagnostics["worker_error"] is None and all(p.poll() is not None for p in worker_log.procs)
    assert validate_solution(inst, res.solution).ok
    p = checked(inst, ss, res)
    assert p.delivered_total + p.not_planned_total + p.unresolved_total + p.model_no_route_total == inst.residents_total
    assert p.delivered_total <= res.best_bound <= trivial_bound(inst)
    b1, _ = solve("b1_greedy", inst, ss, 60.0)
    got_b1 = checked(inst, ss, b1).delivered_total
    assert got_b1 <= res.best_bound
    assert p.delivered_total >= got_b1                     # B1 is E2's warm start (README, amendment 3)
    assert res.info["warm_start"]["planned"] >= got_b1


def test_same_seed_same_plan_when_the_time_limit_does_not_bind():
    """On the tiny instance the plan reaches the proven bound, so no phase runs into the time limit: two runs with
    the same seed give the same plan and bound."""
    inst, ss = tiny()
    a, ta = solve("e2_colgen", inst, ss, 30.0, seed=3)
    b, tb = solve("e2_colgen", inst, ss, 30.0, seed=3)
    assert ta < 20.0 and tb < 20.0
    assert checked(inst, ss, a).delivered_total == a.best_bound            # proven optimal: nothing ran to the limit
    assert a.solution.model_dump() == b.solution.model_dump()
    assert a.best_bound == b.best_bound and a.info["rounds"] == b.info["rounds"]


def test_worker_round_trip_dual_signs_and_errors():
    """The persistent HiGHS worker: warm LP re-solve after adding a column, nonnegative duals of binding <= rows in a
    maximization (the bound's prices), an error reply for an unknown command, and WorkerError once it is gone."""
    from evacplan.methods.e2_worker import HighsWorker, WorkerError
    w = HighsWorker()
    w.call("init", timeout=5, row_lower=np.array([-np.inf, -np.inf]), row_upper=np.array([1.0, 0.5]))
    w.call("add_cols", timeout=5, model="lp", cost=[1.0, 3.0], lower=[0.0, 0.0], upper=[1.0, 1.0], start=[0, 1],
           index=[0, 0, 1], value=[1.0, 1.0, 1.0])
    r = w.call("solve", timeout=5, model="lp", time_limit=2.0)
    assert r["status"] == "Optimal" and r["objective"] == pytest.approx(2.0)
    assert r["row_dual"] == pytest.approx([1.0, 2.0])
    w.call("add_cols", timeout=5, model="lp", cost=[2.0], lower=[0.0], upper=[1.0], start=[0], index=[0], value=[1.0])
    r = w.call("solve", timeout=5, model="lp", time_limit=2.0)
    assert r["objective"] == pytest.approx(2.5) and r["num_col"] == 3          # x1 = 0.5 (row 2), x2 = 0.5
    with pytest.raises(WorkerError):
        w.call("nonsense", timeout=5)
    assert w.alive
    w.proc.kill()
    w.proc.wait()
    with pytest.raises(WorkerError):
        w.call("ping", timeout=1)
    w.close()
    assert "highspy" not in sys.modules


def test_method_is_registered_with_its_defaults():
    m = get_method("e2_colgen")
    assert isinstance(m, E2ColGen) and not m.bound_only
    assert m.config()["smoothing_alpha"] == 0.5 and m.config()["trip_cuts"] is True
    with pytest.raises(ValueError):
        get_method("e2_colgen", nonsense=1)
    with pytest.raises(ValueError):
        get_method("e2_colgen", smoothing_alpha=1.0)


# ------------------------------------------------------------------- in-budget oracle repairs (review E2-D3)
def test_in_budget_oracle_repairs_cut_the_trips_the_oracle_does_not_check():
    """The repair path of the in-budget oracle check (``_Run._oracle_repairs``), which ran in no dev row. The dose
    budget of ``test_e1b_alns.tiny_case(dose=0.02)`` is so small that trips near the fire fail the oracle; neither the
    masks nor the bound model dose, so E2's first plan (B1's, all 13 residents in one van) fails the check. E2 cuts the
    failing column before its first trip the oracle does not check, forbids it, re-solves the MIP and checks again:
    at least one repair, residents cut, the last plan checked in the budget, and every trip of the returned plan
    checked by a fresh oracle, within the budget."""
    inst, ss = tiny_case(dose=0.02)
    budget = 8.0
    res, runtime = solve("e2_colgen", inst, ss, budget)
    assert runtime <= budget
    d = res.diagnostics
    o = d["oracle"]
    assert o["repairs"] >= 1 and o["cut_residents"] >= 1, o
    assert o["skipped_vehicles"] == 0 and o["checked_vehicles"] == o["repairs"] + 1, o   # one van, checked after each
    assert d["worker_error"] is None and d["mip_error"] is None
    assert validate_solution(inst, res.solution).ok
    p = checked(inst, ss, res)
    assert all(t.state is State.CHECKED for v in p.vehicles for t in v.trips)
    assert p.unresolved_total == p.model_no_route_total == 0
    assert 0 < p.delivered_total == d["planned"] < d["warm_start"]["planned"] <= res.best_bound


# --------------------------------------------------------------- worker calls and the deadline (review E2-D4)
def test_a_mip_solve_whose_grace_ends_after_the_deadline_is_cut_before_it(worker_log):
    """The review's case: a MIP solve whose own grace (HiGHS's time limit + 2 s) would end after the deadline, sent to
    a HiGHS child that stops answering (SIGSTOP). The call's timeout is capped at the time left minus
    ``CALL_MARGIN_S``: it returns before the deadline, the child is killed, the worker is retired and the incumbent
    is kept."""
    inst, ss = tiny()
    rh = Reach(inst, ss)
    net = FlowNetwork(inst, rh, delta_s=60, grouping="vehicle")
    run = _Run(E2ColGen(), inst, ss, rh, net, seed=0, budget_s=60.0, deadline=time.monotonic() + 60.0,
               t_start=time.monotonic(), info={"resource_bound": trivial_bound(inst)})
    run._rows()
    run.eps = 1e-3
    run.worker = HighsWorker()
    run._call("init", timeout=10.0, row_lower=np.full(len(run.rows), -np.inf), row_upper=run.b, threads=1, seed=0)
    f, s = inst.facilities[0], inst.shelters[0]
    c = next(c for c in range(3) if f.residents.vector()[c] > 0)
    col = Column(run.vids[0], {(f.id, c): 1}, {(s.id, c): 1}, "test", vtime=60.0)
    run._add_mip([col])
    run.incumbent = (1, 60.0, [col])
    worker_log.freeze = ("solve", "mip")
    run.deadline = time.monotonic() + 2.0
    run._solve_mip(1.5)                                       # its own grace: 3.5 s, past the deadline
    end = time.monotonic()
    cmd, model, t, timeout, call_end, err = worker_log.calls[-1]
    assert worker_log.frozen and (cmd, model) == ("solve", "mip") and t + 1.5 + 2.0 > run.deadline
    assert isinstance(err, WorkerError) and "Timeout" in str(err)
    assert t + timeout <= run.deadline - CALL_MARGIN_S + 0.05 and call_end <= end <= run.deadline
    assert run.worker is None and all(p.poll() is not None for p in worker_log.procs)    # no child left
    assert "mip" not in run.info and "Timeout" in run.info["mip_error"]
    assert run.incumbent == (1, 60.0, [col])


@pytest.mark.parametrize("freeze", [("set_bounds", "mip"), ("solve", "mip")])
def test_a_frozen_highs_child_cannot_hold_e2_past_its_deadline(worker_log, freeze):
    """Through ``solve``, on the repair path of the dose case (budget 4 s): the HiGHS child stops answering (SIGSTOP)
    at the repair's first call, which removes the failing column from the MIP (``set_bounds``, its own grace 5 s:
    past the deadline), or at the repair's MIP solve. The call ends by the deadline, the child is killed and the
    worker retired; E2 keeps its incumbent (the column cut before its failing trip) and returns normally within the
    budget, with a plan whose every trip a fresh oracle checks. No other worker call of the run could have waited
    past the deadline either."""
    inst, ss = tiny_case(dose=0.02)
    budget = 4.0
    worker_log.freeze = freeze
    t0 = time.monotonic()
    res, runtime = solve("e2_colgen", inst, ss, budget)
    assert worker_log.frozen and runtime <= budget, runtime
    assert_no_call_past(worker_log, t0 + budget)
    hit = next(c for c in worker_log.calls if c[:2] == freeze)
    assert isinstance(hit[5], WorkerError) and "Timeout" in str(hit[5])
    assert all(p.poll() is not None for p in worker_log.procs)                       # no child left
    d = res.diagnostics
    assert d["oracle"]["repairs"] >= 1 and "Timeout" in d["worker_error"]
    assert (d["mip_error"] is not None) == (freeze[0] == "solve")
    assert validate_solution(inst, res.solution).ok
    p = checked(inst, ss, res)
    assert all(t.state is State.CHECKED for v in p.vehicles for t in v.trips)
    assert 0 < p.delivered_total == d["planned"]
