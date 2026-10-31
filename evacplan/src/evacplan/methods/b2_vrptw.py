"""B2: OR-Tools VRPTW with pickup and delivery, per-class capacities and STATIC time windows from the
per-facility latest departures; realized on the time-dependent network and checked by the oracle.

The static model sees the hazard only through the windows (the classical approach this baseline stands
for): travel times are free-flow.

* Deadlines: the latest departure from each facility per class, from one backward sweep (all K members,
  RELAXED contact; :func:`evacplan.methods.dispatch.latest_departures`, as B1).
* Requests: the residents of each (facility, class) with a deadline, in chunks: as many chunks of ``q`` as
  fit, the rest in powers of two (so small vehicles can take small chunks), ``q`` = the smallest space for
  the class among vehicles with room for at least two (else 1), capped by ``max_chunk`` and by what can
  board between the release and the deadline.
* Nodes: a start per vehicle (its depot), a free end per vehicle (vehicles need not return), a pickup per
  chunk (service: boarding it) and, per chunk, one delivery alternative per shelter that accepts its class
  (service: unloading it). ``AddPickupAndDeliverySets``: if a pickup is performed, exactly one of its
  deliveries is performed later on the same route; a chunk not served costs ``BIG`` per resident.
* Dimensions: time (turn-aware free-flow shortest-path time between sites plus the service at the
  from-node; waiting allowed). Windows: vehicle start >= its start time, route end <= min(horizon, start +
  shift); pickup start in [release, deadline - boarding the chunk] (leave by the deadline); delivery start
  inside an opening window, unloading done by the horizon. Three capacity dimensions (seats, wheelchair
  slots, stretchers). Shelter capacity per class: a constraint on the active delivery alternatives.
* Objective: ``BIG`` x residents not served + total free-flow travel time. Search: parallel cheapest
  insertion, then guided local search until the time limit = the budget minus a reserve for the rest.
* Realization (:mod:`evacplan.methods.realize`): each route's stops are replayed as soon as possible on the
  POSITIVE masks of :mod:`evacplan.reach` (time-dependent routes, contact-free in all K members); a chunk
  whose boarding or unloading cannot be done there is dropped (its residents are not planned). Optional
  ``repair``: cut what the oracle does not check (peak, dose). The harness checks the plan with the oracle.

Time-limited local search: results can vary with machine load; the seed is recorded but OR-Tools'
routing search does not use one.
"""
from __future__ import annotations

import math
import time

from ..reach import POS_INF, Reach
from .base import Method, MethodResult
from .dispatch import Dispatcher, latest_departures
from .realize import BOARD, UNLOAD, Realizer, Sequence, Stop, Unit


def chunk_sizes(n: int, q: int) -> list[int]:
    """``n`` residents in chunks of ``q``, the remainder in powers of two (largest first)."""
    if n <= 0:
        return []
    q = max(1, int(q))
    out = [q] * (n // q)
    r = n % q
    while r:
        p = 1 << (r.bit_length() - 1)
        out.append(p)
        r -= p
    return out


class B2VRPTW(Method):
    name = "b2_vrptw"

    def __init__(self, max_chunk: int | None = None, first_solution: str = "PARALLEL_CHEAPEST_INSERTION",
                 metaheuristic: str = "GUIDED_LOCAL_SEARCH", reserve_s: float | None = None, repair: bool = False,
                 **config):
        from ortools.constraint_solver import routing_enums_pb2 as enums
        if first_solution not in enums.FirstSolutionStrategy.Value.keys():
            raise ValueError(f"unknown first_solution {first_solution!r}")
        if metaheuristic not in enums.LocalSearchMetaheuristic.Value.keys():
            raise ValueError(f"unknown metaheuristic {metaheuristic!r}")
        if max_chunk is not None and int(max_chunk) < 1:
            raise ValueError("max_chunk must be >= 1")
        super().__init__(max_chunk=None if max_chunk is None else int(max_chunk), first_solution=first_solution,
                         metaheuristic=metaheuristic, reserve_s=reserve_s, repair=bool(repair), **config)
        self.max_chunk = None if max_chunk is None else int(max_chunk)
        self.first = first_solution
        self.meta = metaheuristic
        self.reserve = reserve_s
        self.do_repair = bool(repair)

    # ------------------------------------------------------------------ requests
    def requests(self, instance, D: dict) -> list[tuple[str, int, int]]:
        """Chunks ``(facility, class, residents)`` of every (facility, class) with a deadline."""
        out = []
        for f in instance.facilities:
            rel = int(math.ceil(f.release_s - 1e-6))
            for c in range(3):
                n = f.residents.vector()[c]
                if n == 0 or (f.id, c) not in D:
                    continue
                caps = [v.capacity()[c] for v in instance.vehicles if v.capacity()[c] > 0]
                if not caps:
                    continue
                big = [x for x in caps if x >= 2]
                q = min(big) if big else 1
                if self.max_chunk is not None:
                    q = min(q, self.max_chunk)
                b = int(f.boarding_s.vector()[c])
                if b > 0:
                    q = max(1, min(q, (D[(f.id, c)] - rel) // b))
                out += [(f.id, c, k) for k in chunk_sizes(n, q)]
        return out

    # --------------------------------------------------------------------- solve
    def solve(self, instance, scenario_set, *, budget_s, seed, deadline) -> MethodResult:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2 as enums

        t_start = time.monotonic()
        rh = Reach(instance, scenario_set)
        D = latest_departures(instance, rh)
        dsp = Dispatcher(instance, rh)
        reqs = self.requests(instance, D)
        info: dict = {"requests": len(reqs), "residents_in_requests": sum(n for *_, n in reqs),
                      "deadlines": {f"{fid}/{c}": d for (fid, c), d in sorted(D.items())}}
        V = len(instance.vehicles)
        Hi = rh.Hi
        fac = {f.id: f for f in instance.facilities}
        shel = {s.id: s for s in instance.shelters}
        # ------------------------------------------------------------- nodes
        site: list[str] = [v.depot for v in instance.vehicles] + [None] * V        # graph node (None: free end)
        service: list[int] = [0] * (2 * V)
        pick: list[int] = []
        drops: list[list[tuple[int, str]]] = []
        for fid, c, n in reqs:
            pick.append(len(site))
            site.append(fac[fid].node)
            service.append(n * int(fac[fid].boarding_s.vector()[c]))
            alts = []
            for s in instance.shelters:
                if s.capacity.vector()[c] >= n:
                    alts.append((len(site), s.id))
                    site.append(s.node)
                    service.append(n * int(s.unloading_s.vector()[c]))
            drops.append(alts)
        nodes = sorted({x for x in site if x is not None})
        far = 10 * (Hi + 1)
        tt = {}
        for a in nodes:
            for b in nodes:
                t = 0 if a == b else rh.static_time(rh.node(a), rh.node(b))
                tt[(a, b)] = int(t) if t < POS_INF else far
        n_nodes = len(site)
        travel = [[0 if (site[i] is None or site[j] is None) else tt[(site[i], site[j])] for j in range(n_nodes)]
                  for i in range(n_nodes)]
        transit = [[service[i] + travel[i][j] for j in range(n_nodes)] for i in range(n_nodes)]
        # ------------------------------------------------------------- model
        manager = pywrapcp.RoutingIndexManager(n_nodes, V, list(range(V)), list(range(V, 2 * V)))
        routing = pywrapcp.RoutingModel(manager)
        cost_cb = routing.RegisterTransitMatrix(travel)
        routing.SetArcCostEvaluatorOfAllVehicles(cost_cb)
        time_cb = routing.RegisterTransitMatrix(transit)
        routing.AddDimension(time_cb, Hi, Hi, False, "time")
        tdim = routing.GetDimensionOrDie("time")
        for k, v in enumerate(instance.vehicles):
            end = Hi if v.shift_limit_s is None else min(Hi, int(math.floor(v.start_s + v.shift_limit_s + 1e-6)))
            tdim.CumulVar(routing.Start(k)).SetRange(int(v.start_s), Hi)
            tdim.CumulVar(routing.End(k)).SetRange(int(v.start_s), max(int(v.start_s), end))
        BIG = 10 * V * (Hi + 1)
        demand = [[0] * n_nodes for _ in range(3)]
        for r, (fid, c, n) in enumerate(reqs):
            p = pick[r]
            demand[c][p] = n
            f = fac[fid]
            lo = int(math.ceil(f.release_s - 1e-6))
            hi = D[(fid, c)] - service[p]
            ip = manager.NodeToIndex(p)
            if hi < lo:  # pragma: no cover - chunk sizes keep the boarding between release and deadline
                raise AssertionError(f"chunk {reqs[r]} cannot board between release and deadline")
            tdim.CumulVar(ip).SetRange(lo, hi)
            allowed = [k for k, v in enumerate(instance.vehicles) if v.capacity()[c] >= n]
            routing.SetAllowedVehiclesForIndex(allowed, ip)
            pd = routing.AddDisjunction([ip], n * BIG)
            ids = []
            for dnode, sid in drops[r]:
                demand[c][dnode] = -n
                idx = manager.NodeToIndex(dnode)
                ids.append(idx)
                wins = [(int(math.ceil(a - 1e-6)), min(int(math.floor(b + 1e-6)), Hi) - service[dnode])
                        for a, b in shel[sid].open_windows]
                wins = [(a, b) for a, b in wins if a <= b]
                cv = tdim.CumulVar(idx)
                if not wins:                                  # no window fits this unloading by the horizon
                    routing.solver().Add(routing.ActiveVar(idx) == 0)
                    continue
                cv.SetRange(wins[0][0], wins[-1][1])
                for (_, b0), (a1, _) in zip(wins, wins[1:]):
                    if b0 + 1 <= a1 - 1:
                        cv.RemoveInterval(b0 + 1, a1 - 1)
                routing.SetAllowedVehiclesForIndex(allowed, idx)
            if not ids:
                routing.solver().Add(routing.ActiveVar(ip) == 0)
                continue
            dd = routing.AddDisjunction(ids, 0, 1)
            routing.AddPickupAndDeliverySets(pd, dd)
        for c in range(3):
            if not any(demand[c]):
                continue
            cb = routing.RegisterUnaryTransitVector(demand[c])
            routing.AddDimensionWithVehicleCapacity(cb, 0, [v.capacity()[c] for v in instance.vehicles], True,
                                                    f"load{c}")
        solver = routing.solver()
        n_cap_rows = 0
        for s in instance.shelters:
            for c in range(3):
                terms = [(manager.NodeToIndex(dnode), reqs[r][2]) for r in range(len(reqs)) if reqs[r][1] == c
                         for dnode, sid in drops[r] if sid == s.id]
                if sum(n for _, n in terms) > s.capacity.vector()[c]:
                    solver.Add(solver.Sum([routing.ActiveVar(i) * n for i, n in terms]) <= s.capacity.vector()[c])
                    n_cap_rows += 1
        info["shelter_capacity_constraints"] = n_cap_rows
        # ------------------------------------------------------------- search
        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = enums.FirstSolutionStrategy.Value.Value(self.first)
        params.local_search_metaheuristic = enums.LocalSearchMetaheuristic.Value.Value(self.meta)
        reserve = self.reserve if self.reserve is not None else 0.5 + 0.03 * budget_s + 0.004 * len(reqs)
        limit = max(0.2, deadline - time.monotonic() - reserve)
        params.time_limit.FromMilliseconds(int(1000 * limit))
        t_solve = time.monotonic()
        sol = routing.SolveWithParameters(params) if reqs else None
        info["model_s"] = round(t_solve - t_start, 3)
        info["search_s"] = round(time.monotonic() - t_solve, 3)
        info["time_limit_s"] = round(limit, 3)
        info["status"] = int(routing.status())
        seqs: list[Sequence] = []
        served = 0
        if sol is not None:
            info["objective"] = int(sol.ObjectiveValue())
            where = {p: (r, None) for r, p in enumerate(pick)}
            for r, alts in enumerate(drops):
                for dnode, sid in alts:
                    where[dnode] = (r, sid)
            for k, v in enumerate(instance.vehicles):
                i = routing.Start(k)
                stops: list[Stop] = []
                at: dict[int, tuple[int, int, str]] = {}
                while not routing.IsEnd(i):
                    node = manager.IndexToNode(i)
                    if node in where:
                        r, sid = where[node]
                        fid, c, n = reqs[r]
                        if sid is None:
                            at[r] = (len(stops), -1, "")
                            stops.append(Stop(node=fac[fid].node, order=((BOARD, fid),)))
                        else:
                            at[r] = (at[r][0], len(stops), sid)
                            stops.append(Stop(node=shel[sid].node, order=((UNLOAD, sid),)))
                    i = sol.Value(routing.NextVar(i))
                units = [Unit(facility=reqs[r][0], cls=reqs[r][1], n=reqs[r][2], board_stop=b,
                              drops=((d, sid, reqs[r][2]),)) for r, (b, d, sid) in sorted(at.items())]
                served += sum(u.n for u in units)
                seqs.append(Sequence(vehicle=v.id, stops=stops, units=units))
        info["residents_served_static"] = served
        rz = Realizer(instance, rh, dispatcher=dsp)
        real = rz.realize(seqs)
        info["realization"] = real.summary(seqs)
        if self.do_repair and time.monotonic() < deadline - 0.5:
            from ..oracle import Oracle
            real, info["repair"] = rz.repair(seqs, real, Oracle(instance, scenario_set), self.name,
                                             deadline=deadline - 0.5)
        sol_out = real.solution(instance, self.name, {"seed": int(seed),
                                                      "note": "B2 OR-Tools VRPTW with static windows (SYNTHETIC instances)"})
        info["solve_s"] = round(time.monotonic() - t_start, 3)
        return MethodResult(sol_out, info=info)


__all__ = ["B2VRPTW", "chunk_sizes"]
