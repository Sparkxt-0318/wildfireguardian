"""B3 (MIPs on a time-expanded network, HiGHS): optimal on a tiny instance where brute force knows the
optimum, a valid bound off the grid, valid plans within the budget, S instances only, warm starts, and no
``highspy`` in the main process (OR-Tools and highspy ship ABI-incompatible copies of libhighs.so.1).
SYNTHETIC instances only."""
import sys
import time

import pytest

from evacplan import Oracle, State, validate_solution
from evacplan.generators import SyntheticConfig, generate
from evacplan.methods import get_method
from evacplan.methods.dispatch import Dispatcher
from evacplan.methods.highs_worker import solve_mip
from evacplan.methods.realize import BOARD, UNLOAD, Realizer, Sequence, Stop, Unit
from evacplan.methods.timexp import RELAXED, RESTRICTED, Network, build_mip, extract, is_feasible, lift
from evacplan.reach import Reach
from evacplan_testkit import facility, grid_graph, instance, make_set, nid, quiet, shelter, vehicle


def tiny(step: float = 60.0, board: float = 60.0, unload: float = 60.0, wc_unload: float = 120.0, *,
         release=(0.0, 0.0), ignite: float = 1000.0, fire_col: int = 1, start: float = 0.0, opens: float = 0.0):
    """1 x 5 road (100 m cells, ``step`` s per edge); van with 2 seats at the shelter S (n0_4); A (n0_0) and B
    (n0_2) have 3 ambulatory residents each. Cell (0,1) burns from 1000 s, so the van must leave A by about
    910 s (it touches that cell until 1.5 edges after leaving A). Hand-worked with 60 s steps: A's three
    residents need two trips and the second cannot leave A in time, so 5 of 6 is the optimum (trip orders
    such as B, B, A deliver only 3)."""
    ig = quiet(1, 5)
    ig[0, 0, fire_col] = ignite
    ss = make_set(ig, horizon=3600.0, burn=1e9)
    inst = instance(grid_graph(1, 5, travel=step),
                    facilities=[facility("A", nid(0, 0), amb=3, board=(board, 120.0, 300.0), release=release[0]),
                                facility("B", nid(0, 2), amb=3, board=(board, 120.0, 300.0), release=release[1])],
                    vehicles=[vehicle("V", nid(0, 4), seats=2, wc=0, stretchers=0, start=start)],
                    shelters=[shelter("S", nid(0, 4), unload=(unload, wc_unload, 240.0), windows=((opens, 1e6),))])
    return inst, ss


def brute_force(inst, ss) -> tuple[int, object]:
    """Best plan of the single vehicle over every sequence of trips (board 1..space residents at A and/or B,
    in either order, then unload everyone at S), each realized as soon as possible: when cells never stop
    burning, leaving earlier is never worse, so these plans contain an optimal one. Appending a trip never
    changes the earlier ones, so an infeasible prefix is pruned."""
    rh = Reach(inst, ss)
    rz = Realizer(inst, rh, dispatcher=Dispatcher(inst, rh))
    fac = {f.id: f for f in inst.facilities}
    s_node = inst.shelters[0].node
    cap = inst.vehicles[0].seats
    options = []
    for a in range(cap + 1):
        for b in range(cap + 1 - a):
            if a and b:
                options += [(("A", a), ("B", b)), (("B", b), ("A", a))]
            elif a or b:
                options.append((("A", a),) if a else (("B", b),))
    best: list = [0, None]

    def seq_of(trips) -> Sequence:
        stops, units = [], []
        for trip in trips:
            first = len(stops)
            stops += [Stop(fac[fid].node, ((BOARD, fid),)) for fid, _ in trip]
            si = len(stops)
            stops.append(Stop(s_node, ((UNLOAD, "S"),)))
            units += [Unit(fid, 0, n, first + j, ((si, "S", n),)) for j, (fid, n) in enumerate(trip)]
        return Sequence(vehicle="V", stops=stops, units=units)

    def dfs(trips, left):
        for opt in options:
            if any(n > left[fid] for fid, n in opt):
                continue
            new = trips + [opt]
            seq = seq_of(new)
            real = rz.realize([seq])
            got = real.summary([seq])["residents_realized"]
            if got < sum(n for t in new for _, n in t):
                continue
            if got > best[0]:
                best[0], best[1] = got, real
            dfs(new, {k: v - sum(n for fid, n in opt if fid == k) for k, v in left.items()})

    dfs([], {f.id: f.residents.ambulatory for f in inst.facilities})
    return best[0], best[1]


def solve(name, inst, ss, budget, **cfg):
    m = get_method(name, **cfg)
    t0 = time.monotonic()
    res = m.solve(inst, ss, budget_s=budget, seed=0, deadline=t0 + budget)
    return res, time.monotonic() - t0


def test_b3_optimal_on_a_tiny_instance_matches_brute_force():
    inst, ss = tiny()
    opt, plan = brute_force(inst, ss)
    assert opt == 5
    assert Oracle(inst, ss).check_plan(plan.solution(inst, "brute")).delivered_total == 5
    res, runtime = solve("B3", inst, ss, 30.0, delta_s=60)
    assert runtime < 30.0
    p = Oracle(inst, ss).check_plan(res.solution)
    assert validate_solution(inst, res.solution).ok
    assert p.delivered_total == opt == res.best_bound                 # optimal and proven (gap 0)
    assert p.unresolved_total == p.model_no_route_total == 0
    assert res.info["certified"] and "aligned" in res.info["relaxed_note"]
    assert "highspy" not in sys.modules                                # solved in the child process


def test_b3_bound_is_valid_off_the_grid():
    """Travel, boarding and unloading times off the 60 s grid: the relaxed model floors and credits instead of
    being exact. Its bound must still cover the true optimum, and the plan is valid and fully checked."""
    inst, ss = tiny(step=50.0, board=45.0, unload=30.0, wc_unload=90.0)
    opt, _ = brute_force(inst, ss)
    res, _ = solve("B3", inst, ss, 30.0, delta_s=60)
    p = Oracle(inst, ss).check_plan(res.solution)
    assert res.info["certified"] and "aligned" not in res.info["relaxed_note"]
    assert p.delivered_total <= opt <= res.best_bound <= inst.residents_total
    assert all(t.state is State.CHECKED for v in p.vehicles for t in v.trips)


@pytest.fixture(scope="module")
def s_instance():
    return generate(SyntheticConfig(size="S", tightness=0.75, graph="grid", seed=9501))


def test_b3_respects_the_budget_and_bounds_other_methods(s_instance):
    inst, ss = s_instance.instance, s_instance.hazard
    budget = 10.0
    res, runtime = solve("b3_mip", inst, ss, budget)
    assert runtime <= budget + 0.5
    sol = res.solution
    assert sol.method == "b3_mip" and validate_solution(inst, sol).ok
    oracle = Oracle(inst, ss)
    p = oracle.check_plan(sol)
    assert p.delivered_total + p.not_planned_total == inst.residents_total
    assert all(t.state is State.CHECKED for v in p.vehicles for t in v.trips)
    b1, _ = solve("b1_greedy", inst, ss, 60.0)
    others = [p.delivered_total, oracle.check_plan(b1.solution).delivered_total]
    assert res.best_bound is not None and max(others) <= res.best_bound <= inst.residents_total
    assert res.info["plan_from"] in res.info["candidates"]


def test_b3_runs_on_s_instances_only():
    m = get_method("B3")
    big = generate(SyntheticConfig(size="M", tightness=0.5, graph="grid", seed=9502)).instance
    assert not m.applicable(big)
    res = m.solve(big, None, budget_s=1.0, seed=0, deadline=time.monotonic() + 1.0)
    assert res.solution.itineraries == [] and res.best_bound is None and "skipped" in res.info
    with pytest.raises(ValueError):
        get_method("B3", levels=[3, 2, 1])            # each grid must be a multiple of the next
    with pytest.raises(ValueError):
        get_method("B3", delta_s=0)


def test_lift_maps_a_coarse_solution_to_a_feasible_start(s_instance):
    inst, ss = s_instance.instance, s_instance.hazard
    rh = Reach(inst, ss)
    dsp = Dispatcher(inst, rh)
    coarse = Network(inst, rh, delta_s=720, mode=RESTRICTED, dispatcher=dsp)
    cm = build_mip(coarse)
    res = solve_mip(cm, time_limit=5.0)
    assert res.has_solution and is_feasible(cm, res.x)
    fine = Network(inst, rh, delta_s=360, mode=RESTRICTED, dispatcher=dsp)
    fm = build_mip(fine)
    start = lift(coarse, cm, res.x, fine, fm)
    assert start is not None and is_feasible(fm, start)
    assert round(float(start @ fm.cost)) == round(float(res.x @ cm.cost))       # same residents unloaded
    seqs, n = extract(fine, fm, start)
    real = Realizer(inst, rh, dispatcher=dsp).realize(seqs)
    assert real.summary(seqs)["residents_realized"] == n                         # restricted plans realize fully


@pytest.mark.parametrize("seed", range(6))
def test_relaxed_bound_covers_brute_force_on_random_tiny_instances(seed):
    """Off-grid data (travel, boarding, unloading, release, opening, start, fire timing): the relaxed MIP's
    optimum is at least the true optimum (it is a relaxation) and the restricted MIP's at most (its plans
    realize)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    step = float(rng.choice([40.0, 50.0, 70.0]))
    kw = dict(step=step, board=float(rng.choice([30.0, 45.0, 90.0])), unload=float(rng.choice([20.0, 35.0, 60.0])),
              wc_unload=90.0, release=tuple(float(x) for x in rng.choice([0.0, 100.0, 250.0], size=2)),
              ignite=float(rng.choice([700.0, 1000.0, 1300.0])), fire_col=int(rng.choice([1, 3])),
              start=float(rng.choice([0.0, 30.0, 90.0])), opens=float(rng.choice([0.0, 300.0])))
    inst, ss = tiny(**kw)
    opt, _ = brute_force(inst, ss)
    rh = Reach(inst, ss)
    delta = int(rng.choice([60, 2 * int(step)]))
    got = {}
    for mode in (RESTRICTED, RELAXED):
        net = Network(inst, rh, delta_s=delta, mode=mode)
        assert net.certified or mode == RESTRICTED
        res = solve_mip(build_mip(net), time_limit=20.0)
        assert res.status == "Optimal", (kw, delta, mode)
        got[mode] = round(res.objective)
    assert got[RESTRICTED] <= opt <= got[RELAXED], (kw, delta, got, opt)


def test_restricted_never_beats_relaxed_on_the_same_grid():
    inst, ss = tiny(step=50.0, board=45.0, unload=30.0)
    rh = Reach(inst, ss)
    out = {}
    for mode in (RESTRICTED, RELAXED):
        net = Network(inst, rh, delta_s=60, mode=mode)
        res = solve_mip(build_mip(net), time_limit=10.0)
        assert res.status == "Optimal"
        out[mode] = res.objective
    assert out[RESTRICTED] <= out[RELAXED] + 1e-6


def test_b2_and_b3_share_a_process():
    """B2 imports OR-Tools (with its own libhighs); B3 must still work in the same process."""
    from ortools.constraint_solver import pywrapcp  # noqa: F401
    inst, ss = tiny()
    b2, _ = solve("B2", inst, ss, 3.0)
    b3, _ = solve("B3", inst, ss, 15.0, delta_s=60)
    oracle = Oracle(inst, ss)
    assert oracle.check_plan(b3.solution).delivered_total == 5
    assert oracle.check_plan(b2.solution).delivered_total <= 5
    assert "highspy" not in sys.modules
