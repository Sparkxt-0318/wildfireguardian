"""B3 exact: MIPs on a time-expanded site network, solved with HiGHS; S instances only.

Two MIPs on the grid ``tau_k = k * delta`` (:mod:`evacplan.methods.timexp`; HiGHS in a child process,
:mod:`evacplan.methods.highs_worker`):

1. RELAXED model first (the bound): every plan the oracle accepts maps into it, so its MIP dual bound
   (and the bound of its LP relaxation, solved first by interior point) bounds the residents ANY plan can
   deliver. ``best_bound`` = the smallest of these and the resource bound (residents of classes some
   vehicle and some shelter can take, up to the shelters' room), rounded down; only the resource bound
   when the relaxation is not certified (the 1 s lattice is not complete for it, or a move between active
   locations is shorter than ``delta``).
2. RESTRICTED model (the primal) on grids ``levels`` x ``delta`` (default 4, 2, 1: coarse to fine), each capped
   by that bound so the solver stops when it reaches it (and the finer grids are then skipped): moves are
   POSITIVE earliest-arrival routes rounded up to the grid, so every solution is realizable. Each grid's
   incumbent is lifted onto the next grid as a MIP start (:func:`evacplan.methods.timexp.lift`; the grids
   nest). Coarse grids lose more time to rounding but solve far faster, so within a budget they often give
   the better plan.
3. Every incumbent becomes stop sequences and is realized as soon as possible on the POSITIVE masks
   (:mod:`evacplan.methods.realize`); the plan with the most residents realized is returned (ties: the
   finest restricted grid). The relaxed incumbent may lose residents in realization; restricted ones do not
   when cells never stop burning within the horizon (earlier is then never worse).

The harness checks the plan with the oracle and computes ``gap = (best_bound - delivered) / best_bound``.
Budget: the relaxed MIP gets ``relaxed_share`` of the time left, the restricted grids the rest in
proportion to ``level_share``, minus a reserve for realization. HiGHS runs single-threaded (equal resources for every method).
Results depend on how far the solver gets within the budget (machine load), not on the seed.
"""
from __future__ import annotations

import math
import time

from ..reach import Reach
from ..schema import Solution
from .base import Method, MethodResult
from .dispatch import Dispatcher
from .highs_worker import solve_mip
from .realize import Realizer
from .timexp import RELAXED, RESTRICTED, Network, NotCertified, build_mip, extract, lift, trivial_bound

S_LIMITS = {"max_facilities": 3, "max_vehicles": 2, "max_residents": 60}


class B3MIP(Method):
    name = "b3_mip"

    def __init__(self, delta_s: int = 180, levels: tuple[int, ...] | list[int] = (4, 2, 1),
                 level_share: tuple[float, ...] | list[float] = (0.2, 0.3, 0.5), relaxed_share: float = 0.3,
                 threads: int = 1, heuristic_effort: float = 0.3, max_facilities: int = S_LIMITS["max_facilities"],
                 max_vehicles: int = S_LIMITS["max_vehicles"], max_residents: int = S_LIMITS["max_residents"],
                 repair: bool = False, **config):
        if int(delta_s) != delta_s or delta_s < 1:
            raise ValueError("delta_s must be a whole number of seconds >= 1")
        if not 0.0 < relaxed_share < 1.0:
            raise ValueError("relaxed_share must be in (0, 1)")
        levels = [int(f) for f in levels]
        if not levels or levels[-1] != 1 or any(a % b or a <= b for a, b in zip(levels, levels[1:])):
            raise ValueError("levels: grid multiples of delta_s, decreasing, each a multiple of the next, ending at 1")
        if len(level_share) != len(levels) or any(x <= 0 for x in level_share):
            raise ValueError("level_share: one positive share per level")
        super().__init__(delta_s=int(delta_s), levels=levels, level_share=[float(x) for x in level_share],
                         relaxed_share=float(relaxed_share), threads=int(threads),
                         heuristic_effort=float(heuristic_effort), max_facilities=int(max_facilities),
                         max_vehicles=int(max_vehicles), max_residents=int(max_residents), repair=bool(repair),
                         **config)
        self.levels = levels
        self.level_share = [float(x) for x in level_share]
        self.delta = int(delta_s)
        self.share = float(relaxed_share)
        self.threads = int(threads)
        self.effort = float(heuristic_effort)
        self.limits = (int(max_facilities), int(max_vehicles), int(max_residents))
        self.do_repair = bool(repair)

    def applicable(self, instance) -> bool:
        """S instances only (problem v0 size S: ~2 facilities, 1-2 vehicles, 20-40 residents)."""
        f, v, r = self.limits
        return len(instance.facilities) <= f and len(instance.vehicles) <= v and instance.residents_total <= r

    def solve(self, instance, scenario_set, *, budget_s, seed, deadline) -> MethodResult:
        t_start = time.monotonic()
        info: dict = {"delta_s": self.delta}
        empty = Solution(instance=instance.name, method=self.name, itineraries=[],
                         provenance={"seed": int(seed), "note": "B3 MIP (SYNTHETIC instances)"})
        if not self.applicable(instance):
            info["skipped"] = "B3 runs on S instances only"
            return MethodResult(empty, info=info)
        reserve = 1.5 + 0.03 * budget_s
        rh = Reach(instance, scenario_set)
        dsp = Dispatcher(instance, rh)
        bound = trivial_bound(instance)
        info["resource_bound"] = bound
        candidates = []
        # 1. the relaxed model: the bound
        certified = False
        try:
            net_x = Network(instance, rh, delta_s=self.delta, mode=RELAXED, dispatcher=dsp)
            certified = net_x.certified
            info["relaxed_note"] = net_x.note
            mip_x = build_mip(net_x)
            left = deadline - time.monotonic() - reserve
            res_x = solve_mip(mip_x, time_limit=max(0.5, self.share * left), threads=self.threads, seed=seed,
                              heuristic_effort=self.effort, lp_bound_first=True)
            info["relaxed"] = _summary(res_x, mip_x)
            if certified:
                for b in (res_x.dual_bound, res_x.info.get("lp_bound")):
                    if b is not None and math.isfinite(b):
                        bound = min(bound, int(math.floor(b + 1e-6)))
            if res_x.has_solution:
                candidates.append(("relaxed", net_x, extract(net_x, mip_x, res_x.x)))
        except NotCertified as exc:
            info["relaxed_note"] = f"not certified: {exc}"
        info["certified"] = certified
        # 2. the restricted model on coarse-to-fine grids: the primal, capped by the bound; each incumbent is
        #    lifted onto the next grid as a MIP start
        levels = [self.delta * f for f in self.levels]
        prev = None
        info["restricted"] = {}
        for n, dl in enumerate(levels):
            left = deadline - time.monotonic() - reserve
            if left <= 0.5 and n > 0:
                break
            net_r = Network(instance, rh, delta_s=dl, mode=RESTRICTED, dispatcher=dsp)
            mip_r = build_mip(net_r, max_delivered=bound)
            start = lift(prev[0], prev[1], prev[2], net_r, mip_r) if prev is not None else None
            share = self.level_share[n] / sum(self.level_share[n:])
            res_r = solve_mip(mip_r, time_limit=max(0.5, share * left), threads=self.threads, seed=seed,
                              heuristic_effort=self.effort, start=start)
            summ = _summary(res_r, mip_r)
            summ["warm_start"] = None if prev is None else start is not None
            info["restricted"][str(dl)] = summ
            if res_r.has_solution:
                candidates.insert(0, (f"restricted@{dl}s", net_r, extract(net_r, mip_r, res_r.x)))
                prev = (net_r, mip_r, res_r.x)
                if res_r.objective is not None and res_r.objective >= bound - 1e-6:
                    break                                  # proven optimal: the bound is reached
        # 3. realize every incumbent; keep the best
        rz = Realizer(instance, rh, dispatcher=dsp)
        best = None
        info["candidates"] = {}
        for name, _net, (seqs, predicted) in candidates:
            real = rz.realize(seqs)
            summ = real.summary(seqs)
            info["candidates"][name] = {"mip_unloaded": predicted, "realized": summ["residents_realized"],
                                        "dropped": summ["residents_dropped"]}
            if best is None or summ["residents_realized"] > best[2]:
                best = (name, seqs, summ["residents_realized"], real)
        sol = empty
        if best is not None:
            name, seqs, _, real = best
            info["plan_from"] = name
            if self.do_repair and time.monotonic() < deadline - 0.5:
                from ..oracle import Oracle
                real, info["repair"] = rz.repair(seqs, real, Oracle(instance, scenario_set), self.name,
                                                 deadline=deadline - 0.5)
            sol = real.solution(instance, self.name, {"seed": int(seed),
                                                      "note": f"B3 MIP, {name} model (SYNTHETIC instances)"})
        info["solve_s"] = round(time.monotonic() - t_start, 3)
        return MethodResult(sol, best_bound=float(bound), info=info)


def _summary(res, mip) -> dict:
    rows, cols, nnz = mip.shape
    return {"status": res.status, "objective": res.objective, "dual_bound": res.dual_bound,
            "lp_bound": res.info.get("lp_bound"), "gap": res.gap, "nodes": res.nodes,
            "solve_s": None if res.solve_s != res.solve_s else round(res.solve_s, 3), "wall_s": round(res.wall_s, 3),
            "rows": rows, "cols": cols, "nnz": nnz}


__all__ = ["B3MIP", "S_LIMITS"]
