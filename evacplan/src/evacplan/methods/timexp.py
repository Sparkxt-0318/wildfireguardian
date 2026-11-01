"""Time-expanded site network and its MIP (B3, S instances).

Grid and locations
------------------
Time is the grid ``tau_k = k * delta`` (instance clock, whole seconds), ``k = 0 .. KT = floor(Hi / delta)``
with ``Hi`` the last whole second of the hazard horizon (:mod:`evacplan.reach`). Locations are the
distinct graph nodes of the facilities, shelters and vehicle depots; a location is ACTIVE if a facility
or a shelter is there. Network nodes are ``(location, k)``. Arcs: MOVES between locations (only into
active locations; from a depot-only location only to facilities, since the vehicle starts empty),
WAITS ``(i, k) -> (i, k + 1)`` and an END at any node (vehicles need not return to their depots).

Actions and time
----------------
Boardings and unloadings are integer counts per class at a node: they are COMPLETE by ``tau_k``, so the
residents are on board when the vehicle leaves that node. Their duration is paid from a per-vehicle,
per-location BANK of usable stay time: each wait arc adds its usable seconds (after the facility's
release, inside the shelter's opening window), each arrival adds a credit, and every boarding or
unloading at the node draws ``count x seconds per resident``. The bank empties when the vehicle leaves.
Per-class loads ride on the vehicle's arcs (load <= space x arc flow, the strong form); residents left per
facility and shelter capacity per class are shared by all vehicles. Objective: residents unloaded.

Two models on the same grid
---------------------------
* ``restricted`` (the primal): a move from ``i`` at ``tau_k`` follows the POSITIVE earliest-arrival
  route (:meth:`evacplan.reach.Reach.route`; contact-free in all K members, supported, waits only at
  waitable nodes) and arrives at node ``ceil(a / delta)``, the vehicle idling at the destination
  meanwhile (waitable, usable stay); the idle time counts as credit only where it is usable (after the
  release / inside the window). Waits need a waitable node and a usable stay. Every plan of this model is
  realizable: :mod:`evacplan.methods.realize` replays its stops as soon as possible, which under a
  hazard where cells never stop burning within the horizon can only arrive earlier.
* ``relaxed`` (the bound): a move from ``i`` at ``tau_k`` arrives at ``floor(EA / delta)`` with ``EA`` the
  NEGATIVE-relaxation earliest arrival (:meth:`~evacplan.reach.Reach.earliest_arrival_neg`: only certain
  contact blocks, waiting anywhere, no turn rules); waits are free; an arrival at ``a`` credits the rest of
  its grid cell less 1 s, or ``delta - 1`` if the release or the window opening is still ahead (with whole-
  second times, a stay from ``a`` to a departure in the cell of node ``k_d`` lasts at most that plus ``delta``
  per wait arc; :meth:`Network.relaxed_credit`), wait arcs accrue the part after the earliest release /
  inside a window, and actions are allowed at ``k`` when ``[tau_k, tau_k + delta)`` meets the release / window. Any plan the oracle accepts maps into this model (times floored to the grid), so its
  optimum, and any MIP dual bound of it, bounds the residents ANY plan can deliver: certified only when
  the 1 s lattice is complete for the relaxation (cells never stop burning within the horizon, whole-second
  data; :attr:`evacplan.reach.Reach.lattice_complete`) and every move between active locations advances
  at least one grid step (``delta`` <= the shortest free-flow time between them), else not certified. When
  every instance time is a multiple of ``delta`` (``aligned``), times are WLOG on the grid: moves round up
  and no credit is needed (exact on the grid).
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from ..reach import POS_INF, Reach
from ..schema import Instance
from .dispatch import Dispatcher
from .realize import BOARD, UNLOAD, Sequence, Stop, Unit

RESTRICTED = "restricted"
RELAXED = "relaxed"
EPS_T = 1e-6


class NotCertified(ValueError):
    """The relaxed network would not be a valid relaxation at this grid (no bound can be claimed)."""


@dataclass(frozen=True)
class Location:
    index: int
    node: int
    node_id: str
    facilities: tuple[str, ...]
    shelters: tuple[str, ...]
    depots: tuple[str, ...]

    @property
    def active(self) -> bool:
        return bool(self.facilities or self.shelters)


@dataclass(frozen=True)
class Move:
    src: int
    dst: int
    k: int
    k2: int
    credit: float


@dataclass
class VehicleNet:
    vehicle: str
    loc: int
    k0: int
    kE: int
    src_credit: float
    cap: tuple[int, int, int]


def _overlap(a: float, b: float, lo: float, hi: float) -> float:
    return max(0.0, min(b, hi) - max(a, lo))


class Network:
    """The time-expanded site network of one instance for one mode (see the module docstring)."""

    def __init__(self, instance: Instance, reach: Reach, *, delta_s: int, mode: str,
                 dispatcher: Dispatcher | None = None):
        if mode not in (RESTRICTED, RELAXED):
            raise ValueError("mode must be 'restricted' or 'relaxed'")
        d = int(delta_s)
        if d < 1 or d != delta_s:
            raise ValueError("delta_s must be a whole number of seconds >= 1")
        self.inst, self.rh, self.mode, self.delta = instance, reach, mode, d
        self.dsp = dispatcher or Dispatcher(instance, reach)
        self.KT = reach.Hi // d
        self.fac = {f.id: f for f in instance.facilities}
        self.shel = {s.id: s for s in instance.shelters}
        by_node: dict[str, list[list[str]]] = {}
        for f in instance.facilities:
            by_node.setdefault(f.node, [[], [], []])[0].append(f.id)
        for s in instance.shelters:
            by_node.setdefault(s.node, [[], [], []])[1].append(s.id)
        for v in instance.vehicles:
            by_node.setdefault(v.depot, [[], [], []])[2].append(v.id)
        self.locs = [Location(i, reach.node(n), n, tuple(fs), tuple(ss), tuple(ds))
                     for i, (n, (fs, ss, ds)) in enumerate(by_node.items())]
        self.loc_of_site = {x: loc.index for loc in self.locs for x in (*loc.facilities, *loc.shelters)}
        self.L = len(self.locs)
        self.aligned = mode == RELAXED and self._aligned()
        self.certified, self.note = True, "restricted model (primal only)"
        if mode == RELAXED:
            self.certified, self.note = self._certify()
        self.wait_ok = np.zeros((self.L, max(self.KT, 0)), dtype=bool)
        self.acc = np.zeros((self.L, max(self.KT, 0)))
        for loc in self.locs:
            for k in range(self.KT):
                a, b = k * d, (k + 1) * d
                if mode == RELAXED:
                    self.wait_ok[loc.index, k] = True
                else:
                    self.wait_ok[loc.index, k] = bool(reach.waitable[loc.node]) and reach.stay_ok(loc.node, a, b)
                if loc.active and self.wait_ok[loc.index, k]:
                    self.acc[loc.index, k] = self.usable(loc, a, b)
        self.vehicles = [self._vehicle(v) for v in instance.vehicles]
        self.moves: list[Move] = []
        self.out_moves: dict[tuple[int, int], list[int]] = defaultdict(list)
        self.in_moves: dict[tuple[int, int], list[int]] = defaultdict(list)
        self._build_moves()

    # ----------------------------------------------------------------- site rules
    def _aligned(self) -> bool:
        """Every instance time is a multiple of delta (and the lattice is complete): times are WLOG on the grid."""
        d, inst, rh = self.delta, self.inst, self.rh
        if not rh.lattice_complete or rh.Hi % d:
            return False
        vals = [e.travel_time_s for e in inst.graph.edges]
        for f in inst.facilities:
            vals += [f.release_s, *f.boarding_s.vector()]
        for s in inst.shelters:
            vals += [*s.unloading_s.vector(), *(x for w in s.open_windows for x in w if x <= rh.Hi)]
        for v in inst.vehicles:
            vals += [v.start_s] + ([v.shift_limit_s] if v.shift_limit_s is not None else [])
        return all(float(x).is_integer() and int(x) % d == 0 for x in vals)

    def _certify(self) -> tuple[bool, str]:
        rh = self.rh
        if not rh.lattice_complete:
            return False, f"lattice not complete for the relaxation: {rh.lattice_note}"
        act = [loc for loc in self.locs if loc.active]
        for a in act:
            lb = rh.lower_bound_to(a.node)
            for b in act:
                if a.index != b.index and int(lb[b.node]) < self.delta:
                    return False, (f"delta {self.delta} s exceeds the free-flow time {int(lb[b.node])} s between active "
                                   f"locations {b.node_id} and {a.node_id}")
        return True, ("certified relaxation: complete 1 s lattice, every move between active locations advances "
                      + ("(aligned grid: exact)" if self.aligned else "at least one grid step"))

    def release(self, loc: Location) -> float:
        rel = [self.fac[f].release_s for f in loc.facilities]
        if self.mode == RESTRICTED:
            return float(math.ceil(max(rel) - EPS_T))
        return min(rel) - EPS_T

    def windows(self, sid: str) -> list[tuple[float, float]]:
        if self.mode == RESTRICTED:
            return [(float(a), float(b)) for a, b in self.dsp.windows[sid]]
        return [(a - EPS_T, b + EPS_T) for a, b in self.shel[sid].open_windows]

    def usable(self, loc: Location, a: float, b: float) -> float:
        """Seconds of the stay [a, b] at ``loc`` usable for boarding / unloading (mode-dependent)."""
        parts = []
        if loc.facilities:
            parts.append(max(0.0, b - max(a, self.release(loc))))
        if loc.shelters:
            per = [max((_overlap(a, b, lo, hi) for lo, hi in self.windows(s)), default=0.0) for s in loc.shelters]
            parts.append(min(per) if self.mode == RESTRICTED else max(per))
        if not parts:
            return 0.0
        v = float(min(parts) if self.mode == RESTRICTED else max(parts))
        return round(v, 6) if v >= 1e-6 else 0.0           # no float dust in the MIP

    def relaxed_credit(self, loc: Location, a: float, k: int) -> float:
        """RELAXED (not aligned) credit of an arrival at ``a`` (or a start), placed at node ``k`` = floor(a / delta).

        The relaxation is certified only when the 1 s lattice is complete, and then every event time may be taken
        as a whole second (flooring a plan keeps it feasible). The real stay runs from some ``alpha >= a`` to a
        departure in the cell of the node ``kd`` the vehicle leaves from, i.e. at most ``tau_kd + delta - 1``, so its
        actions take at most ``tau_kd + delta - 1 - max(a, start of work)``. The bank at ``kd`` is this credit plus
        the accruals of the wait arcs ``k .. kd - 1``. If work may start on arrival (a facility here is already
        released, or a shelter's window is open at ``a``), the credit is the rest of the arrival cell, plus the part
        of that cell before the release / opening (the first wait arc's accrual misses it), minus 1 s; otherwise
        ``delta - 1``. ``tests/test_b3_mip.py`` checks the bound against brute force."""
        d = float(self.delta)
        t0 = k * d
        starts = []
        if loc.facilities:
            r = min(self.fac[f].release_s for f in loc.facilities)
            if r <= a + EPS_T:
                starts.append(r)
        for sid in loc.shelters:
            for lo, hi in self.windows(sid):
                if lo <= a <= hi:
                    starts.append(lo)
        v = d if not starts else min(d, (t0 + d - a) + max(0.0, max(starts) - t0))
        return round(max(0.0, v - 1.0), 6)

    def can_board(self, fid: str, k: int) -> bool:
        """May a boarding at this facility be complete by ``tau_k`` (release rule of the mode)?"""
        t, rel = k * self.delta, self.fac[fid].release_s
        if self.mode == RESTRICTED:
            return t >= math.ceil(rel - EPS_T)
        if self.aligned:
            return t >= rel - EPS_T
        return t + self.delta > rel - EPS_T

    def can_unload(self, sid: str, k: int) -> bool:
        t = k * self.delta
        if self.mode == RESTRICTED or self.aligned:
            return any(lo <= t <= hi for lo, hi in self.windows(sid))
        return any(t <= hi and t + self.delta > lo for lo, hi in self.windows(sid))

    # -------------------------------------------------------------------- vehicles
    def _vehicle(self, v) -> VehicleNet:
        d, rh = self.delta, self.rh
        loc = self.locs[next(l.index for l in self.locs if v.id in l.depots)]
        start = float(v.start_s)
        if self.mode == RESTRICTED:
            k0 = int(math.ceil(start / d - 1e-12))
            ok = start == k0 * d or (bool(rh.waitable[loc.node]) and rh.stay_ok(loc.node, start, k0 * d))
            credit = self.usable(loc, start, k0 * d) if (loc.active and ok) else 0.0
        else:
            k0 = int(math.floor(start / d + 1e-12))
            credit = 0.0 if (self.aligned or not loc.active) else self.relaxed_credit(loc, start, k0)
        end = float(rh.Hi) if v.shift_limit_s is None else min(float(rh.Hi), start + v.shift_limit_s)
        kE = min(self.KT, int(math.floor(end / d + 1e-12)))
        return VehicleNet(v.id, loc.index, k0, kE, credit, v.capacity())

    # ----------------------------------------------------------------------- moves
    def _build_moves(self) -> None:
        rh, d, KT = self.rh, self.delta, self.KT
        first_k = {}
        for vn in self.vehicles:
            first_k[vn.loc] = min(first_k.get(vn.loc, KT + 1), vn.k0)
        for i, src in enumerate(self.locs):
            k_from = 0 if src.active else first_k.get(i, KT + 1)
            targets = [j for j in self.locs if j.index != i and (j.facilities if not src.active else j.active)]
            if not targets:
                continue
            for k in range(k_from, KT):
                t = k * d
                if self.mode == RELAXED:
                    ea = rh.earliest_arrival_neg(src.node, t)
                for dst in targets:
                    if self.mode == RELAXED:
                        a = int(ea[dst.node])
                        if a >= POS_INF:
                            continue
                        k2 = -(-a // d) if self.aligned else a // d
                        credit = 0.0 if self.aligned else self.relaxed_credit(dst, a, k2)
                        if k2 <= k and src.active:
                            raise NotCertified(f"a move {src.node_id} -> {dst.node_id} does not advance the grid")
                    else:
                        r = self.dsp.route(src.node, t, dst.node)
                        if r is None:
                            continue
                        a = r.arrival
                        k2 = -(-a // d)
                        if k2 <= KT and a < k2 * d and not (rh.waitable[dst.node] and rh.stay_ok(dst.node, a, k2 * d)):
                            continue
                        credit = self.usable(dst, a, k2 * d) if k2 <= KT else 0.0
                    if k2 > KT:
                        continue
                    m = len(self.moves)
                    self.moves.append(Move(i, dst.index, k, int(k2), credit))
                    self.out_moves[(i, k)].append(m)
                    self.in_moves[(dst.index, int(k2))].append(m)

    def reachable(self, vn: VehicleNet) -> np.ndarray:
        """``[L, KT + 1]`` bool: nodes on some path of the vehicle from its start (by its end limit) to a node
        where it can unload; the start node is always kept (the vehicle may stay unused)."""
        L, KT = self.L, self.KT
        F = np.zeros((L, KT + 1), dtype=bool)
        if vn.k0 > vn.kE:
            return F
        F[vn.loc, vn.k0] = True
        order = sorted(range(L), key=lambda i: self.locs[i].active)      # depot-only locations first
        for k in range(vn.k0, vn.kE + 1):
            for i in order:
                if not F[i, k]:
                    continue
                if k < vn.kE and k < KT and self.wait_ok[i, k]:
                    F[i, k + 1] = True
                for m in self.out_moves.get((i, k), ()):
                    mv = self.moves[m]
                    if mv.k2 <= vn.kE:
                        F[mv.dst, mv.k2] = True
        U = np.zeros_like(F)
        for loc in self.locs:
            for sid in loc.shelters:
                for k in range(vn.k0, vn.kE + 1):
                    if F[loc.index, k] and self.can_unload(sid, k):
                        U[loc.index, k] = True
        for k in range(vn.kE, vn.k0 - 1, -1):
            for i in reversed(order):
                if U[i, k] or not F[i, k]:
                    continue
                if k < vn.kE and k < KT and self.wait_ok[i, k] and U[i, k + 1]:
                    U[i, k] = True
                    continue
                for m in self.out_moves.get((i, k), ()):
                    mv = self.moves[m]
                    if mv.k2 <= vn.kE and U[mv.dst, mv.k2]:
                        U[i, k] = True
                        break
        U[vn.loc, vn.k0] = True
        return F & U


# ===================================================================================== the MIP
@dataclass
class MipModel:
    """A MIP in HiGHS's row-wise form (maximize ``cost @ x``)."""

    cost: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    integer: np.ndarray
    row_lower: np.ndarray
    row_upper: np.ndarray
    a_start: np.ndarray
    a_index: np.ndarray
    a_value: np.ndarray
    maps: dict = field(default_factory=dict)

    @property
    def shape(self) -> tuple[int, int, int]:
        return len(self.row_lower), len(self.cost), len(self.a_value)

    def arrays(self) -> dict[str, np.ndarray]:
        return {k: getattr(self, k) for k in ("cost", "lower", "upper", "integer", "row_lower", "row_upper",
                                              "a_start", "a_index", "a_value")}


class _Builder:
    def __init__(self):
        self.cost, self.lo, self.hi, self.intg = [], [], [], []
        self.rlo, self.rhi = [], []
        self.rows: list[tuple[list[int], list[float]]] = []

    def col(self, lo: float, hi: float, cost: float = 0.0, integer: bool = False) -> int:
        self.cost.append(cost)
        self.lo.append(lo)
        self.hi.append(hi)
        self.intg.append(integer)
        return len(self.cost) - 1

    def row(self, terms: dict[int, float] | list[tuple[int, float]], lo: float, hi: float) -> None:
        items = terms.items() if isinstance(terms, dict) else terms
        acc: dict[int, float] = defaultdict(float)
        for c, v in items:
            acc[c] += v
        idx = [c for c, v in acc.items() if v != 0.0]
        if not idx:
            if lo > 1e-9 or hi < -1e-9:
                raise ValueError("an empty row that cannot hold")
            return
        self.rows.append((idx, [acc[c] for c in idx]))
        self.rlo.append(lo)
        self.rhi.append(hi)

    def model(self, maps: dict) -> MipModel:
        start = np.zeros(len(self.rows) + 1, dtype=np.int32)
        start[1:] = np.cumsum([len(r[0]) for r in self.rows])
        index = np.fromiter((c for r in self.rows for c in r[0]), dtype=np.int32, count=int(start[-1]))
        value = np.fromiter((v for r in self.rows for v in r[1]), dtype=np.float64, count=int(start[-1]))
        return MipModel(np.asarray(self.cost, float), np.asarray(self.lo, float), np.asarray(self.hi, float),
                        np.asarray(self.intg, bool), np.asarray(self.rlo, float), np.asarray(self.rhi, float),
                        start, index, value, maps)


def build_mip(net: Network, *, max_delivered: float | None = None) -> MipModel:
    """The MIP of a network (see the module docstring). Per vehicle: binary arcs (moves, waits) and ends (at
    shelter locations or the start node), per-class loads carried ON the arcs (load <= space x arc), integer
    boardings and unloadings at nodes, and the stay-time banks. Actions happen only at the node where the
    vehicle leaves (by a move) or ends: any stay's actions can be deferred to its last node, since the bank
    is cumulative over the stay (this removes symmetric solutions without changing either model's optimum).
    ``max_delivered``: an optional cap on the objective (e.g. a proven bound), which lets the solver stop
    as soon as an incumbent reaches it."""
    inst, d, KT = net.inst, net.delta, net.KT
    INF = math.inf
    N = [sum(f.residents.vector()[c] for f in inst.facilities) for c in range(3)]
    work = {}
    for loc in net.locs:
        w = 0.0
        for fid in loc.facilities:
            f = net.fac[fid]
            w += sum(n * b for n, b in zip(f.residents.vector(), f.boarding_s.vector()))
        for sid in loc.shelters:
            s = net.shel[sid]
            w += sum(min(cp, N[c]) * u for c, (cp, u) in enumerate(zip(s.capacity.vector(), s.unloading_s.vector())))
        work[loc.index] = float(w)
    B = _Builder()
    maps: dict = {"vehicles": []}
    glob_board: dict[tuple[str, int], list[int]] = defaultdict(list)
    glob_unload: dict[tuple[str, int], list[int]] = defaultdict(list)
    for vn in net.vehicles:
        R = net.reachable(vn)
        cap = vn.cap
        cls = [c for c in range(3) if cap[c] > 0 and N[c] > 0]
        vm = {"vehicle": vn.vehicle, "x": {}, "y": {}, "z": {}, "board": {}, "unload": {}, "bank": {},
              "k0": vn.k0, "kE": vn.kE, "loc": vn.loc}
        src = (vn.loc, vn.k0)
        nodes = [(i, k) for k in range(vn.k0, vn.kE + 1) for i in range(net.L) if R[i, k]]
        load: dict[tuple, dict[int, int]] = {}            # arc key -> class -> load column
        for i, k in nodes:
            loc = net.locs[i]
            if loc.shelters or (i, k) == src:
                vm["z"][(i, k)] = B.col(0, 1, 0.0, True)
            if k < vn.kE and k < KT and net.wait_ok[i, k] and R[i, k + 1]:
                vm["y"][(i, k)] = B.col(0, 1, 0.0, True)
                load[("y", i, k)] = {c: B.col(0, cap[c]) for c in cls}
            for m in net.out_moves.get((i, k), ()):
                mv = net.moves[m]
                if mv.k2 <= vn.kE and R[mv.dst, mv.k2]:
                    vm["x"][m] = B.col(0, 1, 0.0, True)
                    load[("x", m)] = {c: B.col(0, cap[c]) for c in cls}
            for fid in loc.facilities:
                if not net.can_board(fid, k):
                    continue
                for c in cls:
                    n = net.fac[fid].residents.vector()[c]
                    if n > 0:
                        col = B.col(0, min(n, cap[c]), 0.0, True)
                        vm["board"][(fid, c, k)] = col
                        glob_board[(fid, c)].append(col)
            for sid in loc.shelters:
                if not net.can_unload(sid, k):
                    continue
                for c in cls:
                    sc = net.shel[sid].capacity.vector()[c]
                    if sc > 0:
                        col = B.col(0, min(sc, cap[c], N[c]), 1.0, True)
                        vm["unload"][(sid, c, k)] = col
                        glob_unload[(sid, c)].append(col)
            if loc.active and work[i] > 0:
                vm["bank"][(i, k)] = B.col(0, work[i], 0.0, False)
        # loads ride on arcs: load <= space x arc
        for key, cols in load.items():
            arc = vm["y"][(key[1], key[2])] if key[0] == "y" else vm["x"][key[1]]
            for c, col in cols.items():
                B.row({col: 1.0, arc: -float(cap[c])}, -INF, 0.0)
        # vehicle flow conservation and the single end
        for i, k in nodes:
            terms: dict[int, float] = defaultdict(float)
            for m in net.in_moves.get((i, k), ()):
                if m in vm["x"]:
                    terms[vm["x"][m]] += 1.0
            if (i, k - 1) in vm["y"]:
                terms[vm["y"][(i, k - 1)]] += 1.0
            for m in net.out_moves.get((i, k), ()):
                if m in vm["x"]:
                    terms[vm["x"][m]] -= 1.0
            if (i, k) in vm["y"]:
                terms[vm["y"][(i, k)]] -= 1.0
            if (i, k) in vm["z"]:
                terms[vm["z"][(i, k)]] -= 1.0
            rhs = -1.0 if (i, k) == src else 0.0
            B.row(terms, rhs, rhs)
        B.row({col: 1.0 for col in vm["z"].values()}, 1.0, 1.0)
        # per-class load conservation at nodes (ends carry nothing: everyone boarded is unloaded)
        acts_at: dict[tuple[int, int], list[tuple[int, float]]] = defaultdict(list)    # (loc, k) -> (col, seconds)
        bd_at: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        ul_at: dict[tuple[int, int, int], list[int]] = defaultdict(list)
        for (fid, c, k), col in vm["board"].items():
            i = net.loc_of_site[fid]
            acts_at[(i, k)].append((col, float(net.fac[fid].boarding_s.vector()[c])))
            bd_at[(i, k, c)].append(col)
        for (sid, c, k), col in vm["unload"].items():
            i = net.loc_of_site[sid]
            acts_at[(i, k)].append((col, float(net.shel[sid].unloading_s.vector()[c])))
            ul_at[(i, k, c)].append(col)
        for i, k in nodes:
            for c in cls:
                arr = [load[("x", m)][c] for m in net.in_moves.get((i, k), ()) if m in vm["x"]]
                if (i, k - 1) in vm["y"]:
                    arr.append(load[("y", i, k - 1)][c])
                dep = [load[("x", m)][c] for m in net.out_moves.get((i, k), ()) if m in vm["x"]]
                if (i, k) in vm["y"]:
                    dep.append(load[("y", i, k)][c])
                terms = defaultdict(float)
                for col in arr:
                    terms[col] += 1.0
                for col in dep:
                    terms[col] -= 1.0
                for col in bd_at.get((i, k, c), ()):
                    terms[col] += 1.0
                for col in ul_at.get((i, k, c), ()):
                    terms[col] -= 1.0
                if terms:
                    B.row(terms, 0.0, 0.0)
                if net.mode == RESTRICTED and ul_at.get((i, k, c)):    # unload only residents that arrived on board
                    t2 = {col: 1.0 for col in ul_at[(i, k, c)]}
                    for col in arr:
                        t2[col] = t2.get(col, 0.0) - 1.0
                    B.row(t2, -INF, 0.0)
        # actions only where the vehicle leaves by a move or ends (deferral to the stay's last node)
        big = 2.0 * sum(cap)
        for (i, k), cols in acts_at.items():
            terms = {col: 1.0 for col, _ in cols}
            outs = [vm["x"][m] for m in net.out_moves.get((i, k), ()) if m in vm["x"]]
            if (i, k) in vm["z"]:
                outs.append(vm["z"][(i, k)])
            for col in outs:
                terms[col] = terms.get(col, 0.0) - big
            B.row(terms, -INF, 0.0)
        # banks: actions draw the usable stay time accrued in the current stay
        for (i, k), bcol in vm["bank"].items():
            used = [(col, sec) for col, sec in acts_at.get((i, k), ()) if sec > 0]
            if used:
                B.row(used + [(bcol, -1.0)], -INF, 0.0)
            arrivals = [(vm["x"][m], -net.moves[m].credit) for m in net.in_moves.get((i, k), ())
                        if m in vm["x"] and net.moves[m].credit > 0]
            src_credit = vn.src_credit if (i, k) == src else 0.0
            prev = (i, k - 1)
            carry = []
            if prev in vm["y"]:
                carry = [(vm["y"][prev], -float(net.acc[i, k - 1]))]
                if prev in vm["bank"]:
                    carry.append((vm["bank"][prev], -1.0))
                    carry += [(col, sec) for col, sec in acts_at.get(prev, ()) if sec > 0]
            B.row([(bcol, 1.0)] + carry + arrivals, -INF, src_credit)
            hold = [(vm["y"][prev], -work[i])] if prev in vm["y"] else []
            B.row([(bcol, 1.0)] + hold + arrivals, -INF, src_credit)
        vm["load"] = load
        maps["vehicles"].append(vm)
    for (fid, c), cols in glob_board.items():
        B.row({col: 1.0 for col in cols}, -INF, float(net.fac[fid].residents.vector()[c]))
    for (sid, c), cols in glob_unload.items():
        if net.shel[sid].capacity.vector()[c] < N[c]:
            B.row({col: 1.0 for col in cols}, -INF, float(net.shel[sid].capacity.vector()[c]))
    if max_delivered is not None:
        B.row({col: 1.0 for cols in glob_unload.values() for col in cols}, -INF, float(max_delivered))
    return B.model(maps)


def trivial_bound(instance: Instance) -> int:
    """Residents of classes that some vehicle and some shelter can take (a bound needing no model)."""
    out = 0
    for c in range(3):
        if any(v.capacity()[c] > 0 for v in instance.vehicles) and any(s.capacity.vector()[c] > 0
                                                                        for s in instance.shelters):
            n = sum(f.residents.vector()[c] for f in instance.facilities)
            out += min(n, sum(s.capacity.vector()[c] for s in instance.shelters))
    return out


# ================================================================================ extraction
def _path(net: Network, vm: dict, val: np.ndarray) -> list[tuple[tuple[int, int], tuple]]:
    """The vehicle's path in a solution: ``[(node, how it is left), ...]`` with ``("y",)`` (wait),
    ``("x", move)`` or ``("z",)`` (end)."""
    moves_from: dict[tuple[int, int], int] = {}
    for m, col in vm["x"].items():
        if val[col] > 0:
            mv = net.moves[m]
            moves_from[(mv.src, mv.k)] = m
    node, out = (vm["loc"], vm["k0"]), []
    for _ in range(len(vm["z"]) + len(vm["y"]) + len(vm["x"]) + 1):
        i, k = node
        if (i, k) in vm["y"] and val[vm["y"][(i, k)]] > 0:
            out.append((node, ("y",)))
            node = (i, k + 1)
        elif (i, k) in moves_from:
            m = moves_from[(i, k)]
            out.append((node, ("x", m)))
            node = (net.moves[m].dst, net.moves[m].k2)
        else:
            out.append((node, ("z",)))
            break
    return out


def extract(net: Network, model: MipModel, x: np.ndarray) -> tuple[list[Sequence], int]:
    """Per-vehicle stop sequences of a MIP solution (stops in path order; within a stay, actions in grid
    order, unloadings before boardings at the same node) and the residents it unloads. Units are matched
    first in, first out per class (the validator's convention)."""
    val = np.rint(np.asarray(x, dtype=float)).astype(np.int64)
    seqs: list[Sequence] = []
    total = 0
    for vm in model.maps["vehicles"]:
        boards: dict[tuple[int, int], list[tuple[str, int, int]]] = defaultdict(list)
        unloads: dict[tuple[int, int], list[tuple[str, int, int]]] = defaultdict(list)
        for (fid, c, k), col in vm["board"].items():
            if val[col] > 0:
                boards[(net.loc_of_site[fid], k)].append((fid, c, int(val[col])))
        for (sid, c, k), col in vm["unload"].items():
            if val[col] > 0:
                unloads[(net.loc_of_site[sid], k)].append((sid, c, int(val[col])))
                total += int(val[col])
        path = [n for n, _ in _path(net, vm, val)]
        stops: list[Stop] = []
        events: list[tuple[int, str, str, int, int]] = []     # (stop, kind, site, class, count)
        cur_loc, cur_keys = None, set()
        onboard = [0, 0, 0]
        for i, k in path:
            first, later = [], []                   # unload what is on board, board, then unload the rest
            for sid, c, n in sorted(unloads.get((i, k), ())):
                m = min(n, onboard[c])
                onboard[c] -= m
                if m:
                    first.append((UNLOAD, sid, c, m))
                if n - m:
                    later.append((UNLOAD, sid, c, n - m))
            brd = [(BOARD, f, c, n) for f, c, n in sorted(boards.get((i, k), ()))]
            for _, _, c, n in brd:
                onboard[c] += n
            for _, _, c, n in later:
                onboard[c] -= n
            acts = first + brd + later
            if not acts:
                if cur_loc is not None and i != cur_loc:
                    cur_loc, cur_keys = None, set()
                continue
            for kind, site, c, n in acts:
                key = (kind, site)
                if cur_loc != i or (key in cur_keys and stops[-1].order[-1] != key):
                    stops.append(Stop(node=net.locs[i].node_id, order=()))
                    cur_loc, cur_keys = i, set()
                if key not in cur_keys:
                    stops[-1] = Stop(node=stops[-1].node, order=stops[-1].order + (key,))
                    cur_keys.add(key)
                events.append((len(stops) - 1, kind, site, c, n))
        units: list[list] = []
        fifo: list[list[list]] = [[], [], []]
        for si, kind, site, c, n in events:
            if kind == BOARD:
                u = [site, c, n, si, []]
                units.append(u)
                fifo[c].append([u, n])
            else:
                need = n
                while need:
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
            for s, sid, m in drops:
                merged[(s, sid)] += m
            out_units.append(Unit(facility=f, cls=c, n=n, board_stop=si,
                                  drops=tuple((s, sid, m) for (s, sid), m in sorted(merged.items()))))
        seqs.append(Sequence(vehicle=vm["vehicle"], stops=stops, units=out_units))
    return seqs, total


def row_activity(model: MipModel, x: np.ndarray) -> np.ndarray:
    prod = model.a_value * np.asarray(x, dtype=float)[model.a_index]
    return np.add.reduceat(prod, model.a_start[:-1]) if prod.size else np.zeros(len(model.row_lower))


def is_feasible(model: MipModel, x: np.ndarray, tol: float = 1e-6) -> bool:
    """Does ``x`` satisfy every bound, row and integrality of the model?"""
    x = np.asarray(x, dtype=float)
    if x.shape != model.cost.shape or np.any(x < model.lower - tol) or np.any(x > model.upper + tol):
        return False
    if np.any(np.abs(x[model.integer] - np.rint(x[model.integer])) > tol):
        return False
    act = row_activity(model, x)
    return bool(np.all(act >= model.row_lower - tol) and np.all(act <= model.row_upper + tol))


def lift(coarse: Network, cmodel: MipModel, x: np.ndarray, fine: Network, fmodel: MipModel) -> np.ndarray | None:
    """Map a RESTRICTED solution on a grid of ``r * delta`` onto the RESTRICTED model on ``delta`` (a MIP start).

    The coarse grid's times are fine grid times, a coarse move leaves at the same instant on the same POSITIVE
    route and arrives no later on the fine grid (the vehicle then idles, which the coarse arc already checked),
    a coarse wait is ``r`` fine waits, actions keep their instant, loads ride on the image arcs and the banks are
    recomputed along the fine path. Returns ``None`` if any piece is missing in the fine model or the result is
    not feasible there (it is then simply not used)."""
    if coarse.mode != RESTRICTED or fine.mode != RESTRICTED or coarse.delta % fine.delta:
        return None
    r = coarse.delta // fine.delta
    val = np.rint(np.asarray(x, dtype=float)).astype(np.int64)
    out = np.zeros(len(fmodel.cost))
    for vmc, vmf, vnf in zip(cmodel.maps["vehicles"], fmodel.maps["vehicles"], fine.vehicles):
        if vmc["vehicle"] != vmf["vehicle"] or vmc["loc"] != vmf["loc"] or vmf["k0"] > vmc["k0"] * r:
            return None
        fpath: list[tuple[tuple[int, int], tuple, list[tuple]]] = []    # fine (node, entry, load keys of the leg)
        entry: tuple = ("src",)
        for kk in range(vmf["k0"], vmc["k0"] * r):          # the fine grid may start earlier: wait at the depot
            if (vmf["loc"], kk) not in vmf["y"]:
                return None
            out[vmf["y"][(vmf["loc"], kk)]] = 1.0
            fpath.append(((vmf["loc"], kk), entry, []))
            entry = ("y",)
        for (i, kc), how in _path(coarse, vmc, val):
            k = kc * r
            if how[0] == "z":
                if (i, k) not in vmf["z"]:
                    return None
                fpath.append(((i, k), entry, []))
                out[vmf["z"][(i, k)]] = 1.0
                break
            if how[0] == "y":
                keys = [("y", i, k + t) for t in range(r)]
                start_entry = entry
                for t in range(r):
                    if (i, k + t) not in vmf["y"]:
                        return None
                    out[vmf["y"][(i, k + t)]] = 1.0
                    fpath.append(((i, k + t), start_entry if t == 0 else ("y",), []))
                legload = (("y", i, kc), keys)
                entry = ("y",)
            else:
                mc = coarse.moves[how[1]]
                mf = next((m for m in fine.out_moves.get((i, k), ()) if fine.moves[m].dst == mc.dst), None)
                if mf is None or mf not in vmf["x"] or fine.moves[mf].k2 > mc.k2 * r:
                    return None
                out[vmf["x"][mf]] = 1.0
                fpath.append(((i, k), entry, []))
                keys = [("x", mf)]
                for kk in range(fine.moves[mf].k2, mc.k2 * r):
                    if (mc.dst, kk) not in vmf["y"]:
                        return None
                    out[vmf["y"][(mc.dst, kk)]] = 1.0
                    fpath.append(((mc.dst, kk), ("x", mf) if kk == fine.moves[mf].k2 else ("y",), []))
                    keys.append(("y", mc.dst, kk))
                legload = (("x", how[1]), keys)
                entry = ("x", mf) if fine.moves[mf].k2 == mc.k2 * r else ("y",)
            # loads of the coarse leg ride on every fine arc of its image
            ckey, fkeys = legload
            for c, ccol in vmc["load"].get(ckey, {}).items():
                for fk in fkeys:
                    fcol = vmf["load"].get(fk, {}).get(c)
                    if fcol is None:
                        return None
                    out[fcol] = float(val[ccol])
        for kind in ("board", "unload"):
            for (site, c, kc), col in vmc[kind].items():
                if val[col] > 0:
                    fcol = vmf[kind].get((site, c, kc * r))
                    if fcol is None:
                        return None
                    out[fcol] = float(val[col])
        # banks along the fine path
        used_at: dict[tuple[int, int], float] = defaultdict(float)
        for kind, table, secs in (("board", vmf["board"], lambda s_, c_: fine.fac[s_].boarding_s.vector()[c_]),
                                  ("unload", vmf["unload"], lambda s_, c_: fine.shel[s_].unloading_s.vector()[c_])):
            for (site, c, k), col in table.items():
                if out[col] > 0:
                    used_at[(fine.loc_of_site[site], k)] += out[col] * float(secs(site, c))
        prev_bank, prev_node = 0.0, None
        for (i, k), how, _ in fpath:
            if (i, k) not in vmf["bank"]:
                prev_node = (i, k)
                continue
            credit = vnf.src_credit if how[0] == "src" else (fine.moves[how[1]].credit if how[0] == "x" else 0.0)
            if how[0] == "y" and prev_node == (i, k - 1):
                wcap = fmodel.upper[vmf["bank"][(i, k)]]
                b = min(wcap, prev_bank - used_at[(i, k - 1)] + float(fine.acc[i, k - 1]))
            else:
                b = credit
            if used_at[(i, k)] > b + 1e-6:
                return None
            out[vmf["bank"][(i, k)]] = b
            prev_bank, prev_node = b, (i, k)
    return out if is_feasible(fmodel, out) else None


__all__ = ["Location", "MipModel", "Move", "Network", "NotCertified", "RELAXED", "RESTRICTED", "build_mip", "extract",
           "is_feasible", "lift", "trivial_bound"]
