"""B1 greedy: earliest-deadline-first insertion with the latest-safe-departure sweep's deadlines.

1. Deadlines: one backward sweep (:meth:`evacplan.reach.Reach.sweep`, all K members, RELAXED contact)
   gives, per facility and mobility class, the latest departure from the facility that can still
   reach an open shelter accepting the class (after release and one boarding). Classes with no such
   departure are skipped (the harness reports them per facility; see :mod:`evacplan.deadlines`).
2. Jobs = (facility, class) with residents left, taken earliest deadline first. Each job is
   appended (insertion at the end of a vehicle's schedule: earlier deadlines were served first) to
   the vehicle with the cheapest insertion: the least added vehicle time per resident moved
   (``vehicle_rule="per_resident"``, default; ties: earlier departure from the facility, then
   vehicle id), or the vehicle that leaves the facility earliest (``vehicle_rule="earliest"``). The
   load is the job's class up to the vehicle's space, topped up with the facility's other classes in
   deadline order, each only as far as every loaded class still leaves by its deadline; it goes to
   the shelter (accepting every loaded class, with room) where unloading ends first. A job that no
   vehicle can serve any more is dropped (its residents stay unplanned).
3. ``repair`` (default off): cut each itinerary before its first trip that the oracle does not check
   (peak or dose; the relaxed masks already guarantee contact, support and horizon), if time allows.
   A vehicle's state never improves along its itinerary, so this only relabels the residents of the
   cut trips from model_no_route/unresolved to not planned; it cannot raise the delivered count.
   There is no local search.
"""
from __future__ import annotations

import math
import time

from ..oracle import Oracle
from ..reach import Reach
from .base import Method, MethodResult
from .dispatch import Dispatcher, Track


class B1Greedy(Method):
    name = "b1_greedy"

    def __init__(self, vehicle_rule: str = "per_resident", repair: bool = False, **config):
        if vehicle_rule not in ("per_resident", "earliest"):
            raise ValueError("vehicle_rule must be 'per_resident' or 'earliest'")
        super().__init__(vehicle_rule=vehicle_rule, repair=bool(repair), **config)
        self.rule = vehicle_rule
        self.do_repair = bool(repair)

    def _key(self, dsp, tr):
        if self.rule == "earliest":
            return (tr.depart, tr.end, tr.vehicle)
        added = tr.end - dsp.vs[tr.vehicle].t
        return (added / sum(tr.counts), tr.depart, tr.end, tr.vehicle)

    def solve(self, instance, scenario_set, *, budget_s, seed, deadline) -> MethodResult:
        t_start = time.monotonic()
        rh = Reach(instance, scenario_set)
        present = sorted({c for f in instance.facilities for c in range(3) if f.residents.vector()[c] > 0})
        cpos = {c: i for i, c in enumerate(present)}
        sweep = rh.sweep([rh.class_targets(c) for c in present], [rh.node(f.node) for f in instance.facilities])
        t_sweep = time.monotonic() - t_start
        D: dict[tuple[str, int], int] = {}
        for f in instance.facilities:
            rel = int(math.ceil(f.release_s - 1e-6))
            for c in present:
                if f.residents.vector()[c] == 0:
                    continue
                b = int(f.boarding_s.vector()[c])
                ld = sweep.latest_departure(cpos[c], rh.node(f.node), not_before=rel + b, board_s=b)
                if ld is not None:
                    D[(f.id, c)] = ld
        del sweep
        dsp = Dispatcher(instance, rh)
        dead: set[tuple[str, int]] = set()
        n_trips, stopped = 0, False
        while True:
            if time.monotonic() > deadline - 0.05 * budget_s:
                stopped = True
                break
            jobs = [(d, fid, c) for (fid, c), d in D.items() if (fid, c) not in dead and dsp.left[fid][c] > 0]
            if not jobs:
                break
            _, fid, c = min(jobs)
            best, best_key = None, None
            for vs in dsp.vs.values():
                tr = self._trip(dsp, vs, fid, c, D)
                if tr is not None and (best is None or self._key(dsp, tr) < best_key):
                    best, best_key = tr, self._key(dsp, tr)
            if best is None:
                dead.add((fid, c))
                continue
            dsp.commit(best)
            n_trips += 1
        info = {"deadlines": {f"{fid}/{c}": d for (fid, c), d in sorted(D.items())}, "trips": n_trips,
                "dropped_jobs": sorted(f"{fid}/{c}" for fid, c in dead), "sweep_s": round(t_sweep, 3),
                "stopped_at_budget": stopped}
        if self.do_repair and time.monotonic() < deadline - 0.05 * budget_s:
            info["repair"] = dsp.repair(Oracle(instance, scenario_set), deadline=deadline - 0.05 * budget_s)
        sol = dsp.solution(self.name, {"seed": int(seed), "note": "B1 EDF insertion (SYNTHETIC instances)"})
        return MethodResult(sol, info=info)

    @staticmethod
    def _trip(dsp: Dispatcher, vs: Track, fid: str, c: int, D: dict):
        cap = vs.cap
        if cap[c] == 0:
            return None
        f = dsp.fac[fid]
        bt = f.boarding_s.vector()
        left = dsp.left[fid]
        first = dsp.board(vs, fid, tuple(1 if k == c else 0 for k in range(3)))
        if first is None:
            return None
        s = first.start
        order = [c] + sorted((k for k in range(3) if k != c and left[k] > 0 and (fid, k) in D), key=lambda k: D[(fid, k)])
        counts = [0, 0, 0]
        lim = math.inf
        for k in order:
            lim_k = min(lim, D[(fid, k)])
            used = s + sum(counts[j] * int(bt[j]) for j in range(3))
            n = min(cap[k], left[k])
            if int(bt[k]) > 0:
                n = min(n, int((lim_k - used) // int(bt[k])))
            if n <= 0:
                if k == c:
                    return None
                continue
            counts[k] = n
            lim = lim_k
        loads = [tuple(counts)]
        if any(counts[k] for k in range(3) if k != c):
            loads.append(tuple(counts[k] if k == c else 0 for k in range(3)))
        for load in loads:
            shelters = [sid for sid in dsp.shel if all(dsp.room[sid][k] >= load[k] for k in range(3))]
            if not shelters:
                continue
            b = dsp.board(vs, fid, load)
            if b is None:
                continue
            tr = dsp.trip(vs, fid, load, shelters, boarding=b)
            if tr is not None:
                return tr
        return None
