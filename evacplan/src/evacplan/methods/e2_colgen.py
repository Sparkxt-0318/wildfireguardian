"""E2: column generation over single-vehicle itineraries, with a proven upper bound (``e2_colgen``).

Dantzig-Wolfe decomposition by vehicle (``evacplan/experiments/E2-column-generation/README.md``):

* **Master** (restricted, in a persistent HiGHS child process, :mod:`evacplan.methods.e2_worker`): columns are
  single-vehicle itineraries with residents boarded per (facility, class) and unloaded per (shelter, class); rows: at
  most one itinerary per vehicle, residents per facility and class, shelter capacity per class (where it can bind),
  and E4's trip cuts per vehicle and facility (:meth:`evacplan.methods.flow_bound.FlowNetwork.trip_limits`). Objective:
  residents delivered.
* **Pricing**: the clock DP on E4's network (:mod:`evacplan.methods.e2_pricing`), RELAXED for the bound and LP columns,
  RESTRICTED for columns that are realized (:mod:`evacplan.methods.realize`, as B2 and B3) for the integer plan.
* **Bound** (valid for any nonnegative prices ``y``, every round): ``floor(fsum(y b) + sum_v max(0, DP_v(y)) + 1e-6)``,
  the smallest over rounds, at most the resource bound; only the resource bound when E4's network is not certified
  (incomplete 1 s lattice) or a zero-time positive cycle makes the DP unbounded. The README gives the argument.
* **Integer plan**: a set-packing MIP over the realized columns (HiGHS), realized again as a whole; optionally checked
  by the oracle inside the budget, cutting columns before trips it does not check. The harness certifies the plan.

Stabilisation: Wentges smoothing of the prices with the mispricing rule. Single-threaded: the parent waits while HiGHS
runs, but never past the deadline: every worker call's timeout is capped at the time left minus ``CALL_MARGIN_S``, and a
call that fails or times out retires the worker (its child killed) while E2 keeps its incumbent (review E2-D4).
Declares no state (rule 3).
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from ..reach import Reach
from ..schema import Board, Drive, Solution, Unload, Wait
from .base import Method, MethodResult
from .dispatch import Dispatcher, latest_departures
from .e2_pricing import RELAXED, RESTRICTED, BatchDP, PricedPath, clock_units
from .e2_worker import HighsWorker, WorkerError
from .flow_bound import FlowNetwork, NotCertified
from .realize import BOARD, UNLOAD, Realizer, Sequence, Stop, Unit
from .timexp import trivial_bound

DEFAULTS = dict(delta_s=60, large_delta_s=120, large_facilities=10, trip_cuts=True, max_cells=24_000_000,
                columns_per_vehicle=3, smoothing_alpha=0.5, rc_tol=1e-7, mip_share=0.10, reserve_s=2.0,
                cg_reserve_share=0.40, oracle_reserve_share=0.15, oracle_check_min_left=0.12, oracle_repairs=2,
                max_rounds=100_000, threads=1, cg_round_max_share=0.10, reopt_clock_s=3, reopt_passes=3,
                lns_max_remove=3, warm_start_share=0.25)
BOUND_MARGIN = 1e-6
ORACLE_S_PER_LEG = 0.03       # a priori oracle cost per leg (E1 measured 18-25.5 ms on M and L)
CALL_MARGIN_S = 0.5           # every worker call's timeout ends at least this long before the deadline (review E2-D4)
MIN_CALL_S = 0.05             # HighsWorker.call waits at least this long: with less time left no call is sent


# ------------------------------------------------------------------------------------------------ columns
@dataclass
class Column:
    vehicle: str
    board: dict[tuple[str, int], int]
    unload: dict[tuple[str, int], int]
    origin: str                                  # "relaxed" | "restricted" | "realized" | "cut"
    seq: Sequence | None = None                  # realized columns: the stop sequence and the units kept
    kept: frozenset = frozenset()
    vtime: float = math.inf                      # realized columns: vehicle time of the realized itinerary
    lp: int | None = None
    mip: int | None = None

    @property
    def delivered(self) -> int:
        return int(sum(self.unload.values()))

    @property
    def key(self) -> tuple:
        return (self.vehicle, tuple(sorted(self.board.items())), tuple(sorted(self.unload.items())))


def path_to_sequence(path: PricedPath, dp: BatchDP, net: FlowNetwork) -> tuple[Sequence, dict, dict]:
    """The stop sequence (stops in path order, units first in first out per class, as ``timexp.extract``) and the
    counts of one DP path. Within a stop unloadings come before boardings (a new stop at the same node otherwise)."""
    stops: list[list] = []                      # [node id, [(kind, site id, class)]]
    cur, keys, last = None, set(), None
    for ev in path.events:
        if ev.kind in ("entry", "move"):
            cur = None
            loc = ev.loc
            continue
        a = dp.actions[ev.action]
        site = net.sites[a.site]
        kind = BOARD if a.sign > 0 else UNLOAD
        key = (kind, site.id)
        has_board = cur is not None and any(k == BOARD for k, _, _ in stops[cur][1])
        if cur is None or (key in keys and last != key) or (kind == UNLOAD and has_board):
            stops.append([net.loc_nodes[loc], []])
            cur, keys = len(stops) - 1, set()
        stops[cur][1].append((kind, site.id, a.cls))
        keys.add(key)
        last = key
    seq_stops: list[Stop] = []
    agg: list[tuple[int, str, str, int, int]] = []          # (stop, kind, site, class, count)
    board: dict[tuple[str, int], int] = defaultdict(int)
    unload: dict[tuple[str, int], int] = defaultdict(int)
    for si, (node, acts) in enumerate(stops):
        order: list[tuple[str, str]] = []
        for kind, site, c in acts:
            if not order or order[-1] != (kind, site):
                order.append((kind, site))
            if agg and agg[-1][:4] == (si, kind, site, c):
                agg[-1] = (si, kind, site, c, agg[-1][4] + 1)
            else:
                agg.append((si, kind, site, c, 1))
            (board if kind == BOARD else unload)[(site, c)] += 1
        seq_stops.append(Stop(node=node, order=tuple(order)))
    units: list[list] = []
    fifo: list[list[list]] = [[], [], []]
    for si, kind, site, c, n in agg:
        if kind == BOARD:
            u = [site, c, n, si, []]
            units.append(u)
            fifo[c].append([u, n])
        else:
            need = n
            while need:
                if not fifo[c]:                                       # pragma: no cover - the DP never unloads more
                    raise AssertionError("a path unloads residents it never boarded")
                head = fifo[c][0]
                take = min(need, head[1])
                head[0][4].append((si, site, take))
                head[1] -= take
                need -= take
                if head[1] == 0:
                    fifo[c].pop(0)
    out_units = []
    for f, c, n, si, drops in units:
        merged: dict[tuple[int, str], int] = defaultdict(int)
        for s, sid, k in drops:
            merged[(s, sid)] += k
        out_units.append(Unit(facility=f, cls=c, n=n, board_stop=si,
                              drops=tuple((s, sid, k) for (s, sid), k in sorted(merged.items()))))
    return Sequence(vehicle=path.vehicle, stops=seq_stops, units=out_units), dict(board), dict(unload)


def cap_sequence(seq: Sequence, avail: dict[tuple[str, int], int]) -> Sequence | None:
    """Cap the residents a sequence boards per (facility, class) at ``avail``, first boardings first (a DP path may
    board one facility on several visits beyond its residents; the realizer would drop such boardings whole). A capped
    unit unloads fewer residents at its last drops. ``None`` when nothing is left."""
    rem = dict(avail)
    units = []
    for u in seq.units:
        k = min(u.n, max(0, int(rem.get((u.facility, u.cls), 0))))
        if k <= 0:
            continue
        rem[(u.facility, u.cls)] = rem.get((u.facility, u.cls), 0) - k
        drops = list(u.drops)
        cut = u.n - k
        while cut > 0:
            s_, sid, m = drops[-1]
            take = min(cut, m)
            if m > take:
                drops[-1] = (s_, sid, m - take)
            else:
                drops.pop()
            cut -= take
        units.append(Unit(facility=u.facility, cls=u.cls, n=k, board_stop=u.board_stop, drops=tuple(drops)))
    return Sequence(vehicle=seq.vehicle, stops=seq.stops, units=units) if units else None


def itinerary_end(instance, actions, start: float) -> float:
    """End of the last action of an itinerary (whole seconds on these instances)."""
    travel = {e.id: float(e.travel_time_s) for e in instance.graph.edges}
    fac = {f.id: f for f in instance.facilities}
    shel = {s.id: s for s in instance.shelters}
    t = float(start)
    for a in actions:
        if isinstance(a, Drive):
            t = float(a.depart_s) + sum(travel[e] for e in a.edges)
        elif isinstance(a, Wait):
            t += float(a.duration_s)
        elif isinstance(a, Board):
            t += fac[a.facility].boarding_s.duration(a.counts)
        elif isinstance(a, Unload):
            t += shel[a.shelter].unloading_s.duration(a.counts)
    return t


# ------------------------------------------------------------------------------------------------- method
class E2ColGen(Method):
    """Column generation with a proven bound (see the module docstring and the experiment README)."""

    name = "e2_colgen"

    def __init__(self, **config):
        unknown = set(config) - set(DEFAULTS)
        if unknown:
            raise ValueError(f"unknown e2_colgen options: {sorted(unknown)}")
        cfg = {**DEFAULTS, **config}
        for k in ("delta_s", "large_delta_s"):
            if int(cfg[k]) != cfg[k] or cfg[k] < 1:
                raise ValueError("time steps must be whole numbers of seconds >= 1")
        if not 0.0 <= float(cfg["smoothing_alpha"]) < 1.0:
            raise ValueError("smoothing_alpha must be in [0, 1)")
        super().__init__(**cfg)
        self.cfg = cfg

    def setting(self, instance) -> int:
        return int(self.cfg["large_delta_s"] if len(instance.facilities) > self.cfg["large_facilities"]
                   else self.cfg["delta_s"])

    def solve(self, instance, scenario_set, *, budget_s, seed, deadline) -> MethodResult:
        t0 = time.monotonic()
        rb = trivial_bound(instance)
        rh = Reach(instance, scenario_set)
        info: dict = {"resource_bound": rb, "reach_s": round(time.monotonic() - t0, 3)}
        try:
            net = FlowNetwork(instance, rh, delta_s=self.setting(instance), grouping="vehicle",
                              trip_cuts=bool(self.cfg["trip_cuts"]))
        except NotCertified as exc:
            return self._fallback(instance, scenario_set, rh, rb, seed, budget_s, deadline, info, str(exc))
        run = _Run(self, instance, scenario_set, rh, net, seed=int(seed), budget_s=float(budget_s), deadline=deadline,
                   t_start=t0, info=info)
        return run.run()

    def _fallback(self, instance, ss, rh, rb, seed, budget_s, deadline, info, why) -> MethodResult:
        """E4's network is not certified here (incomplete 1 s lattice): no network to price on. Plan with B1 inside the
        budget and claim only the resource bound."""
        from .b1_greedy import B1Greedy
        info.update(certified=False, note=f"not certified: {why}; B1 plan, resource bound only")
        res = B1Greedy().solve(instance, ss, budget_s=budget_s, seed=seed, deadline=deadline)
        sol = res.solution.model_copy(update={"method": self.name, "provenance": {
            **res.solution.provenance, "note": "E2 fallback: B1 plan (network not certified) (SYNTHETIC instances)"}})
        diag = {"certified": False, "bound": rb, "fallback": "b1_greedy"}
        return MethodResult(sol, best_bound=float(rb), info=info, diagnostics=diag)


class _Run:
    """One solve of E2 on one instance (see :class:`E2ColGen`)."""

    def __init__(self, method: E2ColGen, instance, ss, rh: Reach, net: FlowNetwork, *, seed: int, budget_s: float,
                 deadline: float, t_start: float, info: dict):
        self.m, self.cfg = method, method.cfg
        self.inst, self.ss, self.rh, self.net = instance, ss, rh, net
        self.seed, self.budget, self.deadline, self.t_start = seed, budget_s, deadline, t_start
        self.info = info
        self.rb = info["resource_bound"]
        self.reserve = float(self.cfg["reserve_s"]) + float(self.cfg["cg_reserve_share"]) * budget_s
        self.improve_end = deadline - 1.0 - float(self.cfg["oracle_reserve_share"]) * budget_s
        self.dsp = Dispatcher(instance, rh)
        self.rz = Realizer(instance, rh, dispatcher=self.dsp)
        self.fac = {f.id: f for f in instance.facilities}
        self.shel = {s.id: s for s in instance.shelters}
        self.veh = {v.id: v for v in instance.vehicles}
        self.vids = [vid for g in net.groups for vid in g.vehicles]
        self.unbounded = False
        self.best_bound_value = math.inf          # the smallest Lagrangian value (float)
        self.bound_round = None
        self.columns: list[Column] = []           # LP columns, in LP order
        self.by_key: dict[tuple, Column] = {}
        self.realized: dict[tuple, Column] = {}   # realized columns by counts key (the MIP's columns)
        self.mip_cols: list[Column] = []
        self.forbidden: set[tuple] = set()
        self.worker: HighsWorker | None = None
        self.incumbent: tuple[int, float, list[Column]] = (0, 0.0, [])
        self.stats = defaultdict(float)

    # --------------------------------------------------------------------------------------------- rows
    def _rows(self) -> None:
        inst, net = self.inst, self.net
        N = [sum(f.residents.vector()[c] for f in inst.facilities) for c in range(3)]
        rows: list[tuple[str, tuple, float]] = []
        self.conv = {}
        for vid in self.vids:
            self.conv[vid] = len(rows)
            rows.append(("conv", (vid,), 1.0))
        self.res, self.cap, self.trip, self.tsec = {}, {}, {}, {}
        self.N_fc = {(f.id, c): int(f.residents.vector()[c]) for f in inst.facilities for c in range(3)}
        self.C_sc = {(s.id, c): int(s.capacity.vector()[c]) for s in inst.shelters for c in range(3)}
        for f in inst.facilities:
            for c in net.classes:
                if f.residents.vector()[c] > 0:
                    self.res[(f.id, c)] = len(rows)
                    rows.append(("res", (f.id, c), float(f.residents.vector()[c])))
        for s in inst.shelters:
            for c in net.classes:
                if 0 < s.capacity.vector()[c] < N[c]:
                    self.cap[(s.id, c)] = len(rows)
                    rows.append(("cap", (s.id, c), float(s.capacity.vector()[c])))
        if self.cfg["trip_cuts"]:
            for vid in self.vids:
                cap = self.veh[vid].capacity()
                for si, site in enumerate(net.sites):
                    if site.kind != "facility":
                        continue
                    lim = net.trip_limits(vid, si)
                    f = self.fac[site.id]
                    total = 0.0
                    for c in net.classes:
                        n = f.residents.vector()[c]
                        if n <= 0 or cap[c] <= 0:
                            continue
                        total += site.secs[c] * min(n, cap[c] * 10**6)
                        nm = lim["n"][c]
                        if math.isfinite(nm) and nm < n:
                            self.trip[(vid, f.id, c)] = len(rows)
                            rows.append(("trip", (vid, f.id, c), float(nm)))
                    sm = lim["secs"]
                    if math.isfinite(sm) and sm < total - 1e-9:
                        self.tsec[(vid, f.id)] = len(rows)
                        rows.append(("tsec", (vid, f.id), float(sm)))
        self.rows = rows
        self.b = np.array([r[2] for r in rows], dtype=float)
        self.is_conv = np.array([r[0] == "conv" for r in rows], dtype=bool)

    def _coeffs(self, col: Column, *, mip: bool = False) -> tuple[list[int], list[float]]:
        idx: dict[int, float] = defaultdict(float)
        idx[self.conv[col.vehicle]] += 1.0
        for (fid, c), n in col.board.items():
            r = self.res.get((fid, c))
            if r is not None:
                idx[r] += n
            if not mip:
                r = self.trip.get((col.vehicle, fid, c))
                if r is not None:
                    idx[r] += n
                r = self.tsec.get((col.vehicle, fid))
                if r is not None:
                    idx[r] += n * float(self.fac[fid].boarding_s.vector()[c])
        for (sid, c), n in col.unload.items():
            r = self.cap.get((sid, c))
            if r is not None:
                idx[r] += n
        keys = sorted(k for k, v in idx.items() if v != 0.0)
        return keys, [idx[k] for k in keys]

    # ------------------------------------------------------------------------------------------- pricing
    def _batches(self) -> None:
        net = self.net
        types: dict[tuple, list] = defaultdict(list)
        for vid in self.vids:
            types[self.veh[vid].capacity()].append(self.veh[vid])
        self.batches: list[dict] = []
        self.batch_of: dict[str, dict] = {}
        self.single: dict[str, BatchDP] = {}
        cells = 0
        for _, vs in sorted(types.items()):
            g, nb = clock_units(net, vs, max_cells=float(self.cfg["max_cells"]))
            for i in range(0, len(vs), nb):
                part = vs[i:i + nb]
                dps = {mode: BatchDP(net, part, g=g, mode=mode) for mode in (RELAXED, RESTRICTED)}
                cells = max(cells, *(d.cells for d in dps.values()))
                self.batches.append({"vehicles": [v.id for v in part], "g": g, "dp": dps})
                for v in part:
                    self.batch_of[v.id] = self.batches[-1]
        self.buffer = np.empty(max(1, cells))
        self.info["batches"] = [{"vehicles": b["vehicles"], "g": b["g"], "cells": b["dp"][RELAXED].cells}
                                for b in self.batches]

    def _profits(self, dp: BatchDP, y: np.ndarray) -> np.ndarray:
        net = self.net
        out = np.zeros((len(dp.actions), dp.nv))
        for a in dp.actions:
            site = net.sites[a.site]
            if a.sign < 0:
                r = self.cap.get((site.id, a.cls))
                out[a.index, :] = 1.0 - (y[r] if r is not None else 0.0)
                continue
            r = self.res.get((site.id, a.cls))
            base = -(y[r] if r is not None else 0.0)
            for b, vid in enumerate(dp.vid):
                p = base
                r = self.trip.get((vid, site.id, a.cls))
                if r is not None:
                    p -= y[r]
                r = self.tsec.get((vid, site.id))
                if r is not None:
                    p -= a.secs * y[r]
                out[a.index, b] = p
        return out

    def _price(self, mode: str, y: np.ndarray, *, extract: bool) -> tuple[dict[str, float], list[tuple]]:
        """Run every batch's DP of ``mode`` at prices ``y``: the DP optimum per vehicle and (``extract``) the paths."""
        values: dict[str, float] = {}
        found: list[tuple] = []
        t0 = time.monotonic()
        for bt in self.batches:
            dp = bt["dp"][mode]
            prof = self._profits(dp, y)
            vals = dp.run(prof, self.buffer)
            if dp.unbounded and mode == RELAXED:
                self.unbounded = True
            for b, vid in enumerate(dp.vid):
                values[vid] = float(vals[b])
            if extract:
                for p in dp.paths(prof, per_vehicle=int(self.cfg["columns_per_vehicle"]), min_value=1e-9):
                    found.append((p, dp))
        self.stats[f"{mode}_dp_s"] += time.monotonic() - t0
        self.stats[f"{mode}_dp_calls"] += 1
        return values, found

    def _bound(self, y: np.ndarray, values: dict[str, float]) -> float:
        yb = math.fsum((y[~self.is_conv] * self.b[~self.is_conv]).tolist())
        return yb + math.fsum(max(0.0, values.get(vid, 0.0)) for vid in self.vids)

    def _note_bound(self, y: np.ndarray, values: dict[str, float], rnd: int) -> float:
        val = self._bound(y, values)
        if not self.unbounded and val < self.best_bound_value:
            self.best_bound_value, self.bound_round = val, rnd
        return val

    @property
    def bound(self) -> int:
        if self.unbounded or not math.isfinite(self.best_bound_value):
            return self.rb
        return min(self.rb, int(math.floor(self.best_bound_value + BOUND_MARGIN)))

    # -------------------------------------------------------------------------------------------- worker
    def _left(self) -> float:
        """Seconds a worker call may still wait: the time left to the deadline minus ``CALL_MARGIN_S``."""
        return self.deadline - time.monotonic() - CALL_MARGIN_S

    def _call(self, cmd: str, *, timeout: float, **payload):
        """``HighsWorker.call`` with its timeout capped at :meth:`_left`, so that no worker call (LP, MIP or other) can
        make the parent wait past the deadline (review E2-D4); with less than ``MIN_CALL_S`` left the call is not sent.
        Any failure (timeout, no time left, an error reply, a child gone) retires the worker: :meth:`_retire` kills
        the child, ``self.worker`` becomes ``None`` and ``info["worker_error"]`` keeps the first error. Raises
        :class:`WorkerError`; the callers keep their incumbent."""
        w = self.worker
        if w is None:
            raise WorkerError(f"worker call {cmd!r}: no worker")
        left = self._left()
        try:
            if left < MIN_CALL_S:
                raise WorkerError(f"worker call {cmd!r}: no time left before the deadline")
            return w.call(cmd, timeout=min(float(timeout), left), **payload)
        except WorkerError as exc:
            self.info.setdefault("worker_error", str(exc))
            self._retire()
            raise

    def _retire(self) -> None:
        """Close the worker without waiting past the deadline: a quit message only while there is time for it, then
        the child is killed (``HighsWorker.close``). ``self.worker`` becomes ``None``."""
        w, self.worker = self.worker, None
        if w is not None:
            left = self._left()
            w.close(timeout=min(2.0, left) if left >= MIN_CALL_S else 0.0)

    # ------------------------------------------------------------------------------------------- columns
    def _add_lp(self, cols: list[Column]) -> int:
        new = [c for c in cols if c.key not in self.by_key]
        if not new or self.worker is None:
            return 0
        start, index, value = [], [], []
        for c in new:
            r, v = self._coeffs(c)
            start.append(len(index))
            index += r
            value += v
        out = self._call("add_cols", timeout=max(1.0, self.deadline - time.monotonic()), model="lp",
                         cost=[float(c.delivered) for c in new], lower=[0.0] * len(new),
                         upper=[1.0] * len(new), start=start, index=index, value=value)
        for i, c in enumerate(new):
            c.lp = out["first"] + i
            self.by_key[c.key] = c
            self.columns.append(c)
        return len(new)

    def _add_mip(self, cols: list[Column]) -> None:
        if not cols or self.worker is None:
            return
        start, index, value = [], [], []
        for c in cols:
            r, v = self._coeffs(c, mip=True)
            start.append(len(index))
            index += r
            value += v
        try:
            out = self._call("add_cols", timeout=max(1.0, self.deadline - time.monotonic()), model="mip",
                             cost=[self._mip_cost(c) for c in cols], lower=[0.0] * len(cols),
                             upper=[1.0] * len(cols), start=start, index=index, value=value, integer=True)
        except WorkerError:
            return                      # the worker is retired (_call): no more MIP; the columns stay in the pool
        for i, c in enumerate(cols):
            c.mip = out["first"] + i
            self.mip_cols.append(c)

    def _mip_cost(self, c: Column) -> float:
        return float(c.delivered) - self.eps * (c.vtime if math.isfinite(c.vtime) else 0.0)

    def _realize(self, col: Column) -> Column | None:
        """Realize one column alone (every resident and all shelter room available); the realized version keeps the
        units the realizer kept. ``None`` when nothing is delivered."""
        if col.seq is None:
            return None
        t0 = time.monotonic()
        real = self.rz.realize([col.seq], {col.vehicle: set(col.kept) if col.kept else set(range(len(col.seq.units)))})
        self.stats["realize_s"] += time.monotonic() - t0
        self.stats["realize_calls"] += 1
        vp = real.vehicles[col.vehicle]
        return self._realized_column(col.seq, frozenset(vp.kept), vp.actions, origin="realized")

    def _realized_column(self, seq: Sequence, kept: frozenset, actions, *, origin: str) -> Column | None:
        board: dict[tuple[str, int], int] = defaultdict(int)
        unload: dict[tuple[str, int], int] = defaultdict(int)
        for uid in kept:
            u = seq.units[uid]
            board[(u.facility, u.cls)] += u.n
            for _, sid, k in u.drops:
                unload[(sid, u.cls)] += k
        if not unload:
            return None
        v = self.veh[seq.vehicle]
        vtime = itinerary_end(self.inst, actions, v.start_s) - float(v.start_s)
        return Column(seq.vehicle, dict(board), dict(unload), origin, seq=seq, kept=kept, vtime=vtime)

    def _keep_realized(self, cols: list[Column]) -> list[Column]:
        """New realized columns (or faster versions of known ones) for the MIP."""
        out = []
        for c in cols:
            if c is None or c.key in self.forbidden:
                continue
            old = self.realized.get(c.key)
            if old is not None:
                if c.vtime < old.vtime - 1e-9:                         # same counts: one MIP column, the faster plan
                    old.vtime, old.seq, old.kept = c.vtime, c.seq, c.kept
                continue
            self.realized[c.key] = c
            out.append(c)
        return out

    def _columns_from(self, found: list[tuple], origin: str, cap: dict | None = None) -> list[Column]:
        """Columns of DP paths; ``cap``: residents available per (facility, class), applied to the sequence that will be
        realized (the column's own counts stay the path's: they are valid LP columns either way)."""
        out = []
        for path, dp in found:
            seq, board, unload = path_to_sequence(path, dp, self.net)
            if not unload:
                continue
            if cap is not None:
                seq = cap_sequence(seq, cap)
                if seq is None:
                    continue
            out.append(Column(path.vehicle, board, unload, origin, seq=seq))
        return out

    def _rc(self, col: Column, y: np.ndarray, sigma: dict[str, float]) -> float:
        r, v = self._coeffs(col)                          # y is 0 on the convexity rows
        return col.delivered - float(np.dot(y[r], v)) - sigma.get(col.vehicle, 0.0)

    # ------------------------------------------------------------------------------------------ integer
    def _greedy(self) -> tuple[int, float, list[Column]]:
        left = {k: self.b[r] for k, r in self.res.items()}
        room = {k: self.b[r] for k, r in self.cap.items()}
        used, chosen = set(), []
        for c in sorted(self.realized.values(), key=lambda c: (-c.delivered, c.vtime, c.vehicle)):
            if c.vehicle in used or c.key in self.forbidden:
                continue
            if any(n > left.get(k, math.inf) + 1e-9 for k, n in c.board.items()):
                continue
            if any(n > room.get(k, math.inf) + 1e-9 for k, n in c.unload.items()):
                continue
            for k, n in c.board.items():
                if k in left:
                    left[k] -= n
            for k, n in c.unload.items():
                if k in room:
                    room[k] -= n
            used.add(c.vehicle)
            chosen.append(c)
        return sum(c.delivered for c in chosen), sum(c.vtime for c in chosen), chosen

    def _update_incumbent(self, cand: tuple[int, float, list[Column]]) -> None:
        if cand[2] and (not self.incumbent[2] or (cand[0], -cand[1]) > (self.incumbent[0], -self.incumbent[1])):
            self.incumbent = cand

    def _solve_mip(self, time_limit: float) -> None:
        if self.worker is None or not self.mip_cols or time_limit < 0.2:
            return
        start = np.zeros(len(self.mip_cols))
        for c in self.incumbent[2]:
            if c.mip is not None:
                start[c.mip] = 1.0
        try:
            out = self._call("solve", timeout=time_limit + 2.0, model="mip", time_limit=time_limit, start=start,
                             options={"mip_rel_gap": 0.0, "mip_abs_gap": min(1e-6, self.eps / 4)})
        except WorkerError as exc:                       # timed out or failed: the incumbent stays (review E2-D4)
            self.info["mip_error"] = str(exc)
            self.worker = None
            return
        self.info["mip"] = {"status": out["status"], "objective": out["objective"], "solve_s": round(out["solve_s"], 3),
                            "nodes": out.get("nodes"), "columns": len(self.mip_cols)}
        x = out.get("x")
        if x is None:
            return
        chosen = [c for c in self.mip_cols if x[c.mip] > 0.5 and c.key not in self.forbidden]
        self._update_incumbent((sum(c.delivered for c in chosen), sum(c.vtime for c in chosen), chosen))

    def _forbid(self, col: Column) -> None:
        self.forbidden.add(col.key)
        if col.mip is not None and self.worker is not None:
            try:
                self._call("set_bounds", timeout=5.0, model="mip", index=[col.mip], lower=[0.0], upper=[0.0])
            except WorkerError:
                pass                    # the worker is retired (_call); the column stays forbidden

    def _plan(self, chosen: list[Column]):
        seqs = [c.seq for c in sorted(chosen, key=lambda c: self.vids.index(c.vehicle))]
        active = {c.vehicle: set(c.kept) for c in chosen}
        return self.rz.realize(seqs, active)

    # ------------------------------------------------------------------------- residual re-optimization
    def _realize_residual(self, seq: Sequence, left: dict, room: dict):
        """Realize one sequence alone against residual residents and shelter room (the others' columns fixed)."""
        saved = (self.dsp.left, self.dsp.room)
        self.dsp.left = {f.id: [max(0, int(left.get((f.id, c), 0))) for c in range(3)] for f in self.inst.facilities}
        self.dsp.room = {sh.id: [max(0, int(room.get((sh.id, c), 0))) for c in range(3)] for sh in self.inst.shelters}
        t0 = time.monotonic()
        try:
            return self.rz.realize([seq])
        finally:
            self.dsp.left, self.dsp.room = saved
            self.stats["realize_s"] += time.monotonic() - t0
            self.stats["realize_calls"] += 1

    def _reopt(self, vid: str, inc: dict[str, Column]) -> Column | None:
        """The best RESTRICTED itinerary of ``vid`` given the other vehicles' columns: profit 1 per resident unloaded
        where shelter room is left, boarding only where residents are left; the paths are capped by the residual
        residents and realized against the residual resources. Up to ``reopt_passes`` passes: facility classes a path
        over-boarded get a boarding price, halfway towards 1 each pass. Returns the best realized column (or ``None``)."""
        left = dict(self.N_fc)
        room = dict(self.C_sc)
        for v, c in inc.items():
            if v == vid or c is None:
                continue
            for k, n in c.board.items():
                left[k] = left.get(k, 0) - n
            for k, n in c.unload.items():
                room[k] = room.get(k, 0) - n
        dp = self.single.get(vid)
        if dp is None:                                  # one vehicle at a time: its own table, a clock of <= 3 s
            gt = self.batch_of[vid]["g"]
            cap_g = max(int(self.cfg["reopt_clock_s"]), gt)
            g = max(d for d in range(1, self.net.delta + 1) if self.net.delta % d == 0 and d <= cap_g)
            dp = self.single[vid] = BatchDP(self.net, [self.veh[vid]], g=g, mode=RESTRICTED)
        mu: dict[tuple[str, int], float] = {}           # price of boarding an over-boarded facility class, in [0, 1)
        best = None
        for _pass in range(int(self.cfg["reopt_passes"])):
            prof = np.zeros((len(dp.actions), dp.nv))
            for a in dp.actions:
                site = self.net.sites[a.site]
                key = (site.id, a.cls)
                if a.sign > 0:
                    prof[a.index, :] = -mu.get(key, 0.0) if left.get(key, 0) > 0 else -np.inf
                else:
                    prof[a.index, :] = 1.0 if room.get(key, 0) > 0 else -np.inf
            t0 = time.monotonic()
            dp.run(prof, self.buffer)
            paths = dp.paths(prof, per_vehicle=int(self.cfg["columns_per_vehicle"]), min_value=1e-9, only={vid})
            self.stats["reopt_dp_s"] += time.monotonic() - t0
            self.stats["reopt_dp_calls"] += 1
            over: set[tuple[str, int]] = set()
            for p in paths:
                seq, board, _ = path_to_sequence(p, dp, self.net)
                over |= {k for k, n in board.items() if n > left.get(k, 0)}
                seq = cap_sequence(seq, left)
                if seq is None:
                    continue
                real = self._realize_residual(seq, left, room)
                vp = real.vehicles[vid]
                col = self._realized_column(seq, frozenset(vp.kept), vp.actions, origin="reopt")
                if col is None:
                    continue
                if best is None or (col.delivered, -col.vtime) > (best.delivered, -best.vtime):
                    best = col
            if not over:
                break
            # Lagrangian heuristic for the per-itinerary resident limits the DP does not see (Beasley and Christofides
            # 1989): price the over-boarded classes, halfway towards 1 each pass (at 1 they would be worthless)
            for k in over:
                mu[k] = 0.5 * (mu.get(k, 0.0) + 1.0)
        return best

    def _register(self, col: Column) -> Column:
        """The pooled realized column with ``col``'s counts (added to the pool and the MIP if new; the faster
        itinerary kept if known)."""
        known = self.realized.get(col.key)
        if known is None:
            self.realized[col.key] = col
            self._add_mip([col])
            return col
        if col.vtime < known.vtime - 1e-9:
            known.vtime, known.seq, known.kept = col.vtime, col.seq, col.kept
        return known

    def _lns(self, until: float) -> int:
        """Large-neighbourhood search on the incumbent: remove 1 to ``lns_max_remove`` random vehicles' itineraries and
        re-insert them in random order with :meth:`_reopt` (the exact single-vehicle DP as the repair); accept if not
        worse (delivered, then vehicle time). Seeded: deterministic for a seed when the time does not bind."""
        rng = np.random.default_rng(self.seed)
        cur = {c.vehicle: c for c in self.incumbent[2]}

        def score(d):
            cols = [c for c in d.values() if c is not None]
            return sum(c.delivered for c in cols), -sum(c.vtime for c in cols)

        best = score(cur)
        its = 0
        nv = len(self.vids)
        while nv and time.monotonic() < until:
            its += 1
            k = int(rng.integers(1, min(int(self.cfg["lns_max_remove"]), nv) + 1))
            out = [self.vids[i] for i in rng.choice(nv, size=k, replace=False)]
            trial = {v: c for v, c in cur.items() if v not in out}
            for i in rng.permutation(k):
                if time.monotonic() >= until:
                    break
                col = self._reopt(out[i], trial)
                if col is not None:
                    trial[out[i]] = self._register(col)
            sc = score(trial)
            if sc >= best:
                cur, best = trial, sc
                cols = [c for c in cur.values() if c is not None]
                self._update_incumbent((sc[0], -sc[1], cols))
        return its

    def _warm_start(self, stop_at: float) -> list[Column]:
        """B1 (greedy earliest-deadline-first insertion with :class:`B1Greedy`'s own trip rule) on this run's Reach, as E1
        does; each vehicle's trips become a stop sequence realized alone (a realized column). Together they are B1's plan,
        which satisfies every master row."""
        from .b1_greedy import B1Greedy
        b1 = B1Greedy()
        D = latest_departures(self.inst, self.rh)
        dsp = Dispatcher(self.inst, self.rh)
        dead: set = set()
        while time.monotonic() < stop_at:
            jobs = [(dl, fid, c) for (fid, c), dl in D.items() if (fid, c) not in dead and dsp.left[fid][c] > 0]
            if not jobs:
                break
            _, fid, c = min(jobs)
            best, best_key = None, None
            for vs in dsp.vs.values():
                tr = b1._trip(dsp, vs, fid, c, D)
                if tr is not None and (best is None or b1._key(dsp, tr) < best_key):
                    best, best_key = tr, b1._key(dsp, tr)
            if best is None:
                dead.add((fid, c))
                continue
            dsp.commit(best)
        cols = []
        for vid, vs in dsp.vs.items():
            if not vs.trips or vid not in self.batch_of:
                continue
            stops, units = [], []
            for tr in vs.trips:
                b_at = len(stops)
                stops.append(Stop(self.fac[tr.facility].node, ((BOARD, tr.facility),)))
                u_at = len(stops)
                stops.append(Stop(self.shel[tr.delivery.shelter].node, ((UNLOAD, tr.delivery.shelter),)))
                for c in range(3):
                    if tr.counts[c] > 0:
                        units.append(Unit(tr.facility, c, int(tr.counts[c]), b_at,
                                          ((u_at, tr.delivery.shelter, int(tr.counts[c])),)))
            seq = Sequence(vehicle=vid, stops=stops, units=units)
            real = self.rz.realize([seq])
            vp = real.vehicles[vid]
            col = self._realized_column(seq, frozenset(vp.kept), vp.actions, origin="b1")
            if col is not None:
                cols.append(col)
        return cols

    def _improve(self, until: float, max_passes: int = 1_000_000) -> int:
        """Block-coordinate ascent on the incumbent: each vehicle in turn gets its best residual itinerary
        (:meth:`_reopt`) if that delivers more (or as many in less vehicle time); until a full pass changes nothing.
        Returns the passes made."""
        inc = {c.vehicle: c for c in self.incumbent[2]}
        order = sorted(self.vids, key=lambda v: (-sum(self.veh[v].capacity()), self.veh[v].start_s, v))
        passes, stale = 0, 0
        while time.monotonic() < until and stale < len(order) and passes < max_passes:
            passes += 1
            for vid in order:
                if time.monotonic() >= until:
                    break
                col = self._reopt(vid, inc)
                cur = inc.get(vid)
                if col is not None and (cur is None or (col.delivered, -col.vtime) > (cur.delivered, -cur.vtime + 1e-6)):
                    inc[vid] = self._register(col)
                    stale = 0
                else:
                    stale += 1
                if stale >= len(order):
                    break
            cols = [c for c in inc.values() if c is not None]
            self._update_incumbent((sum(c.delivered for c in cols), sum(c.vtime for c in cols), cols))
        return passes

    # ------------------------------------------------------------------------------------------------ run
    def run(self) -> MethodResult:
        inst, cfg = self.inst, self.cfg
        info = self.info
        info.update(certified=True, delta_s=self.net.delta, note=self.net.note)
        self._rows()
        self.eps = 1.0 / (1.0 + sum(max(0.0, (min(self.net.H, v.start_s + (v.shift_limit_s or self.net.H)) - v.start_s))
                                    for v in inst.vehicles))
        self._batches()
        info["setup_s"] = round(time.monotonic() - self.t_start, 3)
        n_rows = len(self.rows)
        y = np.zeros(n_rows)
        rounds, converged, why = 0, False, "time"
        try:
            left = self._left()                                  # the start (its ping) is capped as every call
            if left < MIN_CALL_S:
                raise WorkerError("no time left before the deadline to start the worker")
            self.worker = HighsWorker(start_timeout=min(20.0, left))
            self._call("init", timeout=10.0, row_lower=np.full(n_rows, -np.inf), row_upper=self.b,
                       threads=int(cfg["threads"]), seed=self.seed)
        except WorkerError as exc:
            info["worker_error"] = str(exc)
            self.worker = None
        cg_end = self.deadline - self.reserve
        lp_value = None
        phases: dict[str, float] = {}
        try:
            # A. warm start (B1 on this Reach), then one residual re-optimization pass from it (from an empty plan if
            #    B1 planned nothing): each vehicle in turn takes its best RESTRICTED itinerary given the others
            t_a = time.monotonic()
            warm = [self._register(c) for c in self._warm_start(t_a + float(cfg["warm_start_share"]) * self.budget)]
            b1 = (sum(c.delivered for c in warm), sum(c.vtime for c in warm), warm)
            info["warm_start"] = {"planned": b1[0], "s": round(time.monotonic() - t_a, 3)}
            #    and the residual construction from an empty plan (one pass); the better of the two is the incumbent
            t_c = time.monotonic()
            self._improve(until=cg_end, max_passes=1)
            info["construct"] = {"planned": self.incumbent[0], "s": round(time.monotonic() - t_c, 3)}
            self._update_incumbent(b1)
            phases["construct_s"] = time.monotonic() - t_a
            # B. column generation: round 0 at prices 0, then smoothed rounds (README, The method)
            t_b = time.monotonic()
            vals, found = self._price(RELAXED, y, extract=True)
            self._note_bound(y, vals, 0)
            center, center_val = y.copy(), self._bound(y, vals)
            self._add_lp(self._columns_from(found, "relaxed"))
            self._add_lp(list(self.realized.values()))
            if time.monotonic() < cg_end:
                self._restricted_round(y)
            self._update_incumbent(self._greedy())
            slow = time.monotonic() - t_b > float(cfg["cg_round_max_share"]) * self.budget
            if slow:
                why = "round too slow for the budget"                # keep round 0's bound, give the time to the plan
            while not slow and rounds < int(cfg["max_rounds"]):
                if self.worker is None:
                    why = "worker error"                             # failed or timed out (review E2-D4): no LP
                    break
                if self.bound <= self.incumbent[0]:
                    converged, why = True, "plan reaches the bound"
                    break
                if time.monotonic() >= cg_end:
                    why = "time"
                    break
                rounds += 1
                t_round = time.monotonic()
                lp = self._call("solve", timeout=max(0.5, cg_end - time.monotonic()) + 2.0, model="lp",
                                time_limit=max(0.2, cg_end - time.monotonic()))
                self.stats["lp_s"] += lp["solve_s"]
                if lp["row_dual"] is None or lp["objective"] is None:
                    why = f"LP status {lp['status']}"
                    break
                lp_value = float(lp["objective"])
                dual = np.maximum(np.asarray(lp["row_dual"], dtype=float), 0.0)
                y_lp = np.where(self.is_conv, 0.0, dual)
                sigma = {vid: float(dual[r]) for vid, r in self.conv.items()}
                if self.best_bound_value - lp_value < 1e-6:
                    converged, why = True, "LP converged (bound = LP value)"
                    break
                # Wentges smoothing; on a mispricing (no column improves the LP at its own prices) price again at the
                # LP's prices in the same round: if exact pricing there finds none either, the LP is optimal
                alpha = float(cfg["smoothing_alpha"])
                y_sep = alpha * center + (1.0 - alpha) * y_lp
                vals, found = self._price(RELAXED, y_sep, extract=True)
                val = self._note_bound(y_sep, vals, rounds)
                if val < center_val:
                    center, center_val = y_sep.copy(), val
                cols = [c for c in self._columns_from(found, "relaxed")
                        if self._rc(c, y_lp, sigma) > float(cfg["rc_tol"])]
                if not cols and alpha > 0.0:
                    self.stats["mispricings"] += 1
                    vals, found = self._price(RELAXED, y_lp, extract=True)
                    val = self._note_bound(y_lp, vals, rounds)
                    if val < center_val:
                        center, center_val = y_lp.copy(), val
                    cols = [c for c in self._columns_from(found, "relaxed")
                            if self._rc(c, y_lp, sigma) > float(cfg["rc_tol"])]
                if not self._add_lp(cols):
                    converged, why = True, "no improving column at the LP prices (exact pricing)"
                    break
                if time.monotonic() < cg_end:
                    self._restricted_round(y_lp)
                self._update_incumbent(self._greedy())
                if time.monotonic() - t_round > float(cfg["cg_round_max_share"]) * self.budget:
                    why = "round too slow for the budget"            # fewer rounds than ~5 cannot converge
                    break
            phases["cg_s"] = time.monotonic() - t_b
        except WorkerError as exc:
            info["worker_error"] = str(exc)
            self.worker = None
            why = "worker error"
        info.update(rounds=rounds, converged=converged, stop=why, lp_value=lp_value,
                    lagrangian_bound=None if not math.isfinite(self.best_bound_value) else self.best_bound_value,
                    bound_round=self.bound_round, unbounded=self.unbounded)
        # C. integer plan: the MIP over the realized columns, then residual re-optimization, then a last MIP
        t_c = time.monotonic()
        if self.bound > self.incumbent[0]:
            left = min(self.improve_end, self.deadline - 1.0 - 0.02 * self.budget) - time.monotonic()
            self._solve_mip(min(float(cfg["mip_share"]) * self.budget, left))
        n_before = len(self.realized)
        passes, lns = 0, 0
        if self.bound > self.incumbent[0]:
            passes = self._improve(until=self.improve_end)
        if self.bound > self.incumbent[0]:
            lns = self._lns(until=self.improve_end)
        if len(self.realized) > n_before and self.bound > self.incumbent[0]:
            left = min(self.improve_end, self.deadline - 1.0 - 0.02 * self.budget) - time.monotonic()
            self._solve_mip(min(0.05 * self.budget, left))
        phases["integer_s"] = time.monotonic() - t_c
        info["improve_passes"] = passes
        info["lns_iterations"] = lns
        # D. in-budget oracle check of the plan, with repairs
        t_d = time.monotonic()
        plan_cols = list(self.incumbent[2])
        real = self._plan(plan_cols)
        info["oracle"] = self._oracle_repairs(plan_cols, real)
        plan_cols, real = info["oracle"].pop("_plan")
        phases["oracle_s"] = time.monotonic() - t_d
        sol = real.solution(inst, self.m.name, {"seed": self.seed, "note": "E2 column generation (SYNTHETIC instances)"})
        self._retire()
        info.update(planned=sum(c.delivered for c in plan_cols), columns=len(self.columns),
                    realized_columns=len(self.realized), total_s=round(time.monotonic() - self.t_start, 3),
                    timing={k: round(v, 3) for k, v in {**self.stats, **phases}.items()}, bound=self.bound)
        diag = {k: info.get(k) for k in ("warm_start", "construct", "rounds", "converged", "stop", "lp_value", "lagrangian_bound", "bound",
                                         "resource_bound", "planned", "columns", "realized_columns", "setup_s",
                                         "total_s", "unbounded", "improve_passes", "lns_iterations",
                                         "worker_error", "mip_error")}          # None unless a worker call failed
        diag["batches"] = [(b["g"], len(b["vehicles"])) for b in self.batches]
        diag["mip"] = info.get("mip")
        diag["oracle"] = info["oracle"]
        diag["timing"] = info["timing"]
        return MethodResult(sol, best_bound=float(self.bound), info=info, diagnostics=diag)

    def _restricted_round(self, y: np.ndarray) -> None:
        _, found = self._price(RESTRICTED, y, extract=True)
        cols = self._columns_from(found, "restricted", cap=self.N_fc)
        real = []
        for c in cols:
            if time.monotonic() >= self.deadline - self.reserve:
                break
            rc = self._realize(c)
            if rc is not None:
                real.append(rc)
        new = self._keep_realized(real)
        self._add_lp(new)
        self._add_mip(new)

    def _oracle_repairs(self, plan_cols: list[Column], real) -> dict:
        """Check the plan's itineraries with the oracle, one vehicle at a time, while the time left covers 1.5 x the
        estimated cost (legs x the slowest observed seconds per leg, a priori ``ORACLE_S_PER_LEG``); cut a column before
        its first trip the oracle does not check, forbid the old column, re-solve the MIP and re-realize (at most
        ``oracle_repairs`` times). Only decides which columns to keep: the harness certifies the returned plan."""
        out: dict = {"checked_vehicles": 0, "skipped_vehicles": 0, "repairs": 0, "cut_residents": 0}
        from ..oracle import Oracle, State
        if not plan_cols or self.deadline - time.monotonic() < float(self.cfg["oracle_check_min_left"]) * self.budget:
            out["_plan"] = (plan_cols, real)
            return out
        oracle = Oracle(self.inst, self.ss)
        rate = ORACLE_S_PER_LEG
        ok: set[tuple] = set()                       # (vehicle, column key) whose itinerary the oracle checked
        for _ in range(int(self.cfg["oracle_repairs"]) + 1):
            sol = real.solution(self.inst, self.m.name)
            by_vid = {c.vehicle: c for c in plan_cols}
            bad_cols = []
            for it in sol.itineraries:
                col = by_vid[it.vehicle]
                if (it.vehicle, col.key) in ok:
                    continue
                legs = sum(len(a.edges) if isinstance(a, Drive) else 1 for a in it.actions)
                if self.deadline - time.monotonic() - 0.5 < 1.5 * rate * legs:
                    out["skipped_vehicles"] += 1
                    continue
                t0 = time.monotonic()
                vres = oracle.check_itinerary(it)
                dt = time.monotonic() - t0
                self.stats["oracle_s"] += dt
                rate = max(rate, dt / max(1, legs))
                out["checked_vehicles"] += 1
                bad = next((t for t in vres.trips if t.state is not State.CHECKED), None)
                if bad is None:
                    ok.add((it.vehicle, col.key))
                else:
                    bad_cols.append((col, real.vehicles[it.vehicle].stop_of[bad.action]))
            if not bad_cols:
                break
            out["repairs"] += 1
            new = []
            for col, stop in bad_cols:
                self._forbid(col)
                keep = frozenset(u for u in col.kept if all(s < stop for s, _, _ in col.seq.units[u].drops))
                out["cut_residents"] += col.delivered
                if keep:
                    rr = self.rz.realize([col.seq], {col.vehicle: set(keep)})
                    vp = rr.vehicles[col.vehicle]
                    c2 = self._realized_column(col.seq, frozenset(vp.kept), vp.actions, origin="cut")
                    if c2 is not None and c2.key not in self.forbidden:
                        out["cut_residents"] -= c2.delivered
                        if c2.key not in self.realized:
                            self.realized[c2.key] = c2
                            new.append(c2)
            self._add_mip(new)
            self.incumbent = (0, 0.0, [])
            self._update_incumbent(self._greedy())
            self._solve_mip(min(0.05 * self.budget, self.deadline - time.monotonic() - 1.0))
            plan_cols = list(self.incumbent[2])
            real = self._plan(plan_cols)
        out["s_per_leg"] = round(rate, 5)
        out["_plan"] = (plan_cols, real)
        return out


__all__ = ["Column", "DEFAULTS", "E2ColGen", "itinerary_end", "path_to_sequence"]
