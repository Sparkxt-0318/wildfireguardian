"""E4: a flow-over-time upper bound on the residents ANY plan can deliver (bound only: no plan).

The bound is the optimum of a linear programme on a contact-free time-expanded network (a dynamic flow
relaxation in the sense of Ford and Fulkerson's flows over time). It is computed for any instance size,
including M and L where B3's MIPs cannot run, and it declares nothing about any plan (program rule 3):
``best_bound`` is a number every oracle-checked plan stays at or below.

Network (``delta`` seconds per time step, cell ``k`` = [k delta, (k + 1) delta) on the instance clock)
--------------------------------------------------------------------------------------------------
* Locations: the distinct graph nodes of facilities and shelters. Nodes ``(location, k)`` for
  ``k = 0 .. floor(Hi / delta)``.
* Moves ``(i, k) -> (j, k')``: ``k' = floor(EA / delta)`` with ``EA`` the NEGATIVE-relaxation earliest arrival
  at ``j`` leaving ``i`` at ``k delta`` (:meth:`evacplan.reach.Reach.earliest_arrival_neg`: only certain
  contact blocks; waiting anywhere; no turn rules; every leg by the horizon). Waits ``(i, k) -> (i, k + 1)``
  everywhere. Vehicles enter at their depot and start time (a depot that is not a location sends one move to
  each facility location), and end at a shelter location.
* Commodities: vehicle groups (``grouping="vehicle"``: one per vehicle; ``"type"``: identical vehicles
  pooled, with each vehicle's end of shift kept by cumulative end rows). Per group: vehicle flow on every
  arc, per-class loads on moves and waits (load <= space x flow), boardings and unloadings per site, class and
  cell. Shared: residents per facility and class, shelter capacity per class.
* Free space (``free_space``): on arcs into a facility-only node, load + free space <= space x flow; free space
  arriving at such a node covers what is boarded there plus what leaves towards facility-only nodes (it is
  created only by unloading, at shelters, or at a vehicle's entry), so fractions cannot relay residents through
  a facility and come back with room.
* Trip cuts (``trip_cuts``, :meth:`FlowNetwork.trip_limits`): per vehicle and facility, residents boarded there
  are limited by its timeline: trips of at most one load each, separated by a round trip to a shelter and an
  unloading, all between its earliest arrival (or the release) and the end of the facility's action set.
* Time actually spent: the boarding and unloading seconds a group does at a site in cell ``k`` are at most
  the usable seconds of that cell the group can be there: Delta per arriving wait arc, ``(k + 1) delta - EA``
  per arriving move, both clipped to the site's usable set (facility: from its release until its node
  burns in some member and until one second after the latest NEGATIVE departure that still reaches a shelter
  for the class; shelter: its windows, until its node burns and the horizon) and to the vehicles' shifts.

Why it is a bound: every plan the oracle checks maps to a feasible point with the same residents delivered
(``evacplan/experiments/E4-flow-bound/README.md`` gives the argument step by step). Keep only the delivered
residents and each vehicle's itinerary up to its last delivering unloading; a stay at a location becomes the
nodes of the cells it meets, a move the arc from the departure's cell (NEGATIVE earliest arrival is
non-decreasing in the departure time and a checked trip, floored to whole seconds, is a NEGATIVE trip when
the 1 s lattice is complete), every action's seconds are booked in the cells where they happen. What is
relaxed: vehicle identity within a group and integrality (fractional vehicles), the order of actions inside
a cell, turn rules, waiting rules, dose and peak flux, unknown cells (treated as passable), and rounding of
every departure down to its cell start. Certified only when the lattice is complete
(:attr:`evacplan.reach.Reach.lattice_complete`) and ``delta`` is at most the shortest free-flow time between
two locations (every move then advances at least one step, so the network has no zero-time cycles); else the
step is reduced to that time.

The LP is solved by HiGHS in a child process (:mod:`evacplan.methods.lp_worker`); the bound comes from its
row duals by weak duality (:func:`dual_bound`), so it holds whatever the solver's tolerances or status, and
is rounded down to a whole resident after a floating-point safety margin. ``best_bound`` = min(that, the
resource bound of :func:`evacplan.methods.timexp.trivial_bound`).
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from ..reach import NEG_INF, POS_INF, Reach
from ..schema import Instance, Solution
from .base import Method, MethodResult
from .lp_worker import solve_lp
from .timexp import trivial_bound

GROUPINGS = ("vehicle", "type")
EPS_T = 1e-6
MOVE, WAIT, SOURCE, END = 0, 1, 2, 3


class NotCertified(ValueError):
    """The network would not be a valid relaxation (no bound beyond the resource bound can be claimed)."""


# ------------------------------------------------------------------------------------------ intervals
def _merge(ivs) -> tuple[tuple[float, float], ...]:
    out: list[list[float]] = []
    for a, b in sorted(ivs):
        if b < a:
            continue
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return tuple((a, b) for a, b in out)


def _measure(lo: float, hi: float, ivs) -> float:
    """Length of [lo, hi) inside the union of the disjoint intervals ``ivs``."""
    s = 0.0
    for a, b in ivs:
        x, y = max(lo, a), min(hi, b)
        if y > x:
            s += y - x
    return s


def _meets(lo: float, hi: float, ivs) -> bool:
    """Does the cell [lo, hi) meet one of ``ivs`` (each closed at its right end: an action of zero seconds may
    sit exactly there)?"""
    return any(a < hi and b >= lo for a, b in ivs)


# --------------------------------------------------------------------------------------------- sites
@dataclass(frozen=True)
class Site:
    kind: str                                   # "facility" | "shelter"
    id: str
    loc: int
    secs: tuple[float, float, float]            # boarding / unloading seconds per resident of each class
    limit: tuple[int, int, int]                 # residents (facility) / capacity (shelter) per class
    usable: tuple[tuple[tuple[float, float], ...], ...]    # per class: times an action can take place
    union: tuple[tuple[float, float], ...]


@dataclass
class Group:
    name: str
    vehicles: list[str]
    cap: tuple[int, int, int]
    starts: list[float]
    ends: list[float]                           # min(Hi, start + shift) per vehicle
    k_ends: list[int]

    @property
    def count(self) -> int:
        return len(self.vehicles)


@dataclass
class FlowModel:
    """The LP (maximize ``cost @ x``; rows ``row_lower <= A x <= row_upper``; ``A`` row-wise) and what it means."""

    cost: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    row_lower: np.ndarray
    row_upper: np.ndarray
    a_start: np.ndarray
    a_index: np.ndarray
    a_value: np.ndarray
    delta: int
    grouping: str
    note: str
    stats: dict = field(default_factory=dict)
    unload_cols: dict = field(default_factory=dict)      # (shelter, class) -> columns
    board_cols: dict = field(default_factory=dict)       # (facility, class) -> columns
    names: list | None = None                            # column names (debugging; FlowNetwork.debug_names)

    @property
    def shape(self) -> tuple[int, int, int]:
        return len(self.row_lower), len(self.cost), len(self.a_value)

    def arrays(self) -> dict[str, np.ndarray]:
        return {k: getattr(self, k) for k in ("cost", "lower", "upper", "row_lower", "row_upper", "a_start",
                                              "a_index", "a_value")}


class _Rows:
    """Rows collected as COO triplets, assembled row-wise at the end (fast for ~10^6 entries)."""

    def __init__(self):
        self.r: list[int] = []
        self.c: list[int] = []
        self.v: list[float] = []
        self.lo: list[float] = []
        self.hi: list[float] = []

    def add(self, cols, vals, lo: float, hi: float) -> None:
        if not cols:
            if lo > 1e-9 or hi < -1e-9:
                raise ValueError("an empty row that cannot hold")
            return
        i = len(self.lo)
        self.r.extend([i] * len(cols))
        self.c.extend(cols)
        self.v.extend(vals)
        self.lo.append(lo)
        self.hi.append(hi)

    def assemble(self, ncol: int):
        r = np.asarray(self.r, dtype=np.int64)
        c = np.asarray(self.c, dtype=np.int64)
        v = np.asarray(self.v, dtype=float)
        order = np.lexsort((c, r))
        r, c, v = r[order], c[order], v[order]
        # merge duplicate (row, column) entries
        if r.size:
            new = np.ones(r.size, dtype=bool)
            new[1:] = (r[1:] != r[:-1]) | (c[1:] != c[:-1])
            idx = np.cumsum(new) - 1
            v = np.bincount(idx, weights=v)
            r, c = r[new], c[new]
            keep = v != 0.0
            r, c, v = r[keep], c[keep], v[keep]
        m = len(self.lo)
        start = np.zeros(m + 1, dtype=np.int64)
        np.add.at(start, r + 1, 1)
        start = np.cumsum(start)
        if c.size and (c.max() >= ncol or c.min() < 0):
            raise ValueError("column index out of range")
        return (start.astype(np.int32), c.astype(np.int32), v, np.asarray(self.lo, float), np.asarray(self.hi, float))


# ------------------------------------------------------------------------------------------- network
class FlowNetwork:
    """The contact-free time-expanded network of one instance (see the module docstring)."""

    def __init__(self, instance: Instance, reach: Reach, *, delta_s: int = 60, grouping: str = "vehicle",
                 prune_dominated: bool = True, free_space: bool = True, trip_cuts: bool = True):
        if grouping not in GROUPINGS:
            raise ValueError(f"grouping must be one of {GROUPINGS}")
        if int(delta_s) != delta_s or delta_s < 1:
            raise ValueError("delta_s must be a whole number of seconds >= 1")
        self.inst, self.rh, self.grouping = instance, reach, grouping
        self.prune_dominated = bool(prune_dominated)
        self.free_space = bool(free_space)
        self.trip_cuts = bool(trip_cuts)
        self._trip_cache: dict[tuple[str, int], dict] = {}
        self.debug_names = False                  # set True before build() to name the columns (small models)
        rh = reach
        if not rh.lattice_complete:
            raise NotCertified(f"the 1 s lattice is not complete for the relaxation: {rh.lattice_note}")
        self.H = float(rh.Hi)
        self.timing: dict[str, float] = {}
        t0 = time.monotonic()
        # locations
        by_node: dict[str, list] = {}
        for f in instance.facilities:
            by_node.setdefault(f.node, []).append(("facility", f))
        for s in instance.shelters:
            by_node.setdefault(s.node, []).append(("shelter", s))
        self.loc_nodes = list(by_node)
        self.L = len(self.loc_nodes)
        self.loc_of_node = {n: i for i, n in enumerate(self.loc_nodes)}
        self.vnode = [rh.node(n) for n in self.loc_nodes]
        # step: at most the shortest free-flow time between two locations (no zero-time cycles)
        tmin = POS_INF
        for j in range(self.L):
            lb = rh.lower_bound_to(self.vnode[j])
            for i in range(self.L):
                if i != j:
                    tmin = min(tmin, int(lb[self.vnode[i]]))
        self.tmin = tmin
        d = int(delta_s)
        self.note = "certified: complete 1 s lattice"
        if tmin < POS_INF and d > tmin:
            if tmin < 1:
                raise NotCertified("two locations are joined by a zero-time path")
            self.note += f"; step reduced from {d} s to {tmin} s, the shortest free-flow time between two locations"
            d = int(tmin)
        self.delta = d
        self.KT = int(self.H) // d
        # classes some vehicle and some shelter can take, with residents
        N = [sum(f.residents.vector()[c] for f in instance.facilities) for c in range(3)]
        self.N = N
        self.classes = [c for c in range(3) if N[c] > 0 and any(v.capacity()[c] > 0 for v in instance.vehicles)
                        and any(s.capacity.vector()[c] > 0 for s in instance.shelters)]
        # sites and their usable times
        self.LD = {c: rh.latest_arrival_neg(rh.class_targets(c)) for c in self.classes}
        self.sites: list[Site] = []
        self.loc_sites: list[list[int]] = [[] for _ in range(self.L)]
        for n, items in by_node.items():
            i = self.loc_of_node[n]
            v = rh.node(n)
            ign = self.node_ignition(v)
            for kind, x in items:
                per = []
                for c in range(3):
                    ivs: list[tuple[float, float]] = []
                    if c in self.classes and not rh.node_unsupported[v]:
                        if kind == "facility" and x.residents.vector()[c] > 0:
                            ld = int(self.LD[c][v])
                            if ld > NEG_INF:
                                hi = min(ign + EPS_T, ld + 1.0, self.H)
                                if hi > x.release_s:
                                    ivs.append((float(x.release_s), hi))
                        elif kind == "shelter" and x.capacity.vector()[c] > 0:
                            for a, b in x.open_windows:
                                lo, hi = max(0.0, float(a)), min(float(b), self.H, ign + EPS_T)
                                if hi >= lo:
                                    ivs.append((lo, hi))
                    per.append(_merge(ivs))
                secs = x.boarding_s.vector() if kind == "facility" else x.unloading_s.vector()
                limit = x.residents.vector() if kind == "facility" else x.capacity.vector()
                site = Site(kind, x.id, i, tuple(float(s) for s in secs), tuple(int(q) for q in limit), tuple(per),
                            _merge([iv for p in per for iv in p]))
                self.loc_sites[i].append(len(self.sites))
                self.sites.append(site)
        self.loc_union = [_merge([iv for s in self.loc_sites[i] for iv in self.sites[s].union]) for i in range(self.L)]
        self.has_shelter = [any(self.sites[s].kind == "shelter" for s in self.loc_sites[i]) for i in range(self.L)]
        self.has_facility = [any(self.sites[s].kind == "facility" for s in self.loc_sites[i]) for i in range(self.L)]
        # vehicle groups
        self.groups = self._groups()
        self.timing["sites_s"] = time.monotonic() - t0
        t1 = time.monotonic()
        self._physical_arcs()
        self.timing["arcs_s"] = time.monotonic() - t1

    # ------------------------------------------------------------------------------------- helpers
    def node_ignition(self, v: int) -> float:
        """Instance time from which a stationary occupancy of node ``v`` certainly touches a burning cell in some
        member (persistent burning: from then on); inf if never within the horizon."""
        lo, _ = self.rh.node_iv[v]
        return (lo[0] + self.rh.margin) if lo else math.inf

    def _groups(self) -> list[Group]:
        H = self.H
        out: dict[tuple, Group] = {}
        for v in self.inst.vehicles:
            end = H if v.shift_limit_s is None else min(H, float(v.start_s) + float(v.shift_limit_s))
            key = (v.id,) if self.grouping == "vehicle" else v.capacity()
            g = out.get(key)
            if g is None:
                g = out[key] = Group(name=v.id if self.grouping == "vehicle" else f"type{v.capacity()}", vehicles=[],
                                     cap=v.capacity(), starts=[], ends=[], k_ends=[])
            g.vehicles.append(v.id)
            g.starts.append(float(v.start_s))
            g.ends.append(end)
            g.k_ends.append(int(math.floor(end / self.delta + 1e-12)) if end >= 0 else -1)
        return [g for g in out.values() if any(c in self.classes for c in range(3) if g.cap[c] > 0)]

    def trip_limits(self, vid: str, si: int) -> dict:
        """What one vehicle can board at one facility site at most, from its timeline (valid for every checked plan).

        Split the vehicle's boardings of delivered residents at the facility into trips: maximal runs with no
        unloading of delivered residents in between. Within a trip its load never decreases, so a trip boards at
        most its space of each class. Between two trips it unloads at least one resident at a shelter: it drives
        to a shelter node and back (at least the free-flow times) and unloads for at least the shortest unloading
        time, ``G``. Every boarding lies in [max(earliest NEGATIVE arrival from its start, release), end of the
        facility's action set and the end of its shift], of length ``W``, and boardings take their seconds. So, for
        some number of trips
        m >= 1: n_c <= m · space_c and Σ_c b_c n_c + (m − 1) G <= W. Returns ``n`` (per class, whole residents:
        max over m of min(m · space_c, (W_c − (m − 1) G) / b_c), floored) and ``secs`` (max over m of
        min(m · Σ_c b_c space_c, W − (m − 1) G))."""
        key = (vid, si)
        got = self._trip_cache.get(key)
        if got is not None:
            return got
        rh, site = self.rh, self.sites[si]
        veh = next(v for v in self.inst.vehicles if v.id == vid)
        fnode = self.vnode[site.loc]
        start = float(veh.start_s)
        if not hasattr(self, "_ea_start"):
            self._ea_start: dict[str, np.ndarray] = {}
        if vid not in self._ea_start:
            self._ea_start[vid] = rh.earliest_arrival_neg(rh.node(veh.depot), int(start))
        a = float(self._ea_start[vid][fnode])
        cap = veh.capacity()
        out = {"n": [0.0, 0.0, 0.0], "secs": 0.0}
        if a >= POS_INF:
            self._trip_cache[key] = out
            return out
        shel = [(sv, x) for sv in self.inst.shelters for x in [rh.node(sv.node)]
                if any(sv.capacity.vector()[c] > 0 and cap[c] > 0 for c in self.classes)]
        travel = min((int(rh.lower_bound_to(x)[fnode]) + int(rh.lower_bound_to(fnode)[x]) for _, x in shel),
                     default=POS_INF)
        u_min = min((sv.unloading_s.vector()[c] for sv, _ in shel for c in self.classes
                     if sv.capacity.vector()[c] > 0 and cap[c] > 0), default=0.0)
        G = float(travel) + float(u_min) if travel < POS_INF else math.inf
        t0 = max(a, min((lo for lo, _ in site.union), default=math.inf))

        def best(width: float, per_trip: float, per_unit: float) -> float:
            """max over m >= 1 of min(m · per_trip, (width − (m − 1) G) / per_unit)."""
            if width < 0:
                return 0.0
            if G <= 0:                                   # trips need not be apart in time: time is the only limit
                return width / per_unit if per_unit > 0 else math.inf
            val, m = 0.0, 1
            while m <= 1_000_000:
                left = width - (m - 1) * G
                if left < 0:
                    break
                val = max(val, min(m * per_trip, left / per_unit if per_unit > 0 else math.inf))
                if not math.isfinite(G):                 # no shelter to empty at: one trip only
                    break
                m += 1
            return val
        shift_end = self.H if veh.shift_limit_s is None else min(self.H, start + float(veh.shift_limit_s))
        n = [0.0, 0.0, 0.0]
        for c in range(3):
            ivs = site.usable[c]
            if not ivs or cap[c] <= 0:
                continue
            end = min(max(b for _, b in ivs), shift_end)
            v = best(end - max(a, min(lo for lo, _ in ivs)), float(cap[c]), float(site.secs[c]))
            n[c] = math.floor(v + 1e-9) if math.isfinite(v) else math.inf
        end_all = min(max((b for _, b in site.union), default=-math.inf), shift_end)
        full = sum(site.secs[c] * cap[c] for c in range(3) if site.usable[c])
        secs = best(end_all - t0, float(full), 1.0) if full > 0 else 0.0
        out = {"n": n, "secs": secs, "W": end_all - t0, "G": G}
        self._trip_cache[key] = out
        return out

    def last_departure(self, i: int) -> float:
        """Latest instant a vehicle can still leave location ``i`` with a resident it delivers (facility-only
        locations); shelters: the horizon."""
        if self.has_shelter[i]:
            return self.H
        v = self.vnode[i]
        ign = self.node_ignition(v)
        ld = max((int(self.LD[c][v]) for c in self.classes), default=NEG_INF)
        return min(ign + EPS_T, ld + 1.0, self.H) if ld > NEG_INF else -math.inf

    def _physical_arcs(self) -> None:
        """Moves between locations (from every cell a vehicle can still leave in) and the vehicles' entries.

        A move ``(i, k) -> (j, k')`` is left out when a path of two shorter moves through another location ``m``
        reaches ``j`` in an earlier cell, or in the same cell no later (``prune_dominated``): any flow on it can
        take that path instead (it passes ``m`` without acting, then waits at ``j``), which only adds presence,
        so the LP optimum is unchanged. The two moves are strictly shorter in cells, so by induction on the
        length the replacement path consists of kept moves."""
        rh, d, H, L, KT = self.rh, self.delta, self.H, self.L, self.KT
        hi_loc = np.array([max((b for _, b in u), default=-math.inf) for u in self.loc_union])
        vn = np.asarray(self.vnode, dtype=np.int64)
        # EA[i][k, j]: arrival time of the move (i, k) -> j, or -1 when there is none
        EA = np.full((L, KT + 1, L), -1, dtype=np.int64)
        ea_calls = 0
        for i in range(L):
            last = self.last_departure(i)
            if last == -math.inf:
                continue
            for k in range(KT + 1):
                t = k * d
                if t > last:
                    break
                ea = rh.earliest_arrival_neg(self.vnode[i], t)[vn]
                ea_calls += 1
                ok = (ea < POS_INF) & (ea <= H) & (ea <= hi_loc)
                ok[i] = False
                EA[i, k] = np.where(ok, ea, -1)
        cells = np.where(EA >= 0, EA // d, -1)
        if np.any((EA >= 0) & (cells <= np.arange(KT + 1)[None, :, None])):    # pragma: no cover - step choice
            raise NotCertified("a move between two locations does not advance a cell")
        keep = EA >= 0
        if self.prune_dominated:
            for i in range(L):
                for k in range(KT + 1):
                    row = EA[i, k]
                    if not (row >= 0).any():
                        continue
                    best_c = np.full(L, POS_INF, dtype=np.int64)     # best two-hop arrival cell / time at each j
                    best_t = np.full(L, POS_INF, dtype=np.int64)
                    for m in np.flatnonzero(row >= 0).tolist():
                        k1 = int(cells[i, k, m])
                        if k1 > KT:
                            continue
                        r2 = EA[m, k1]
                        ok = r2 >= 0
                        ok[i] = False
                        c2 = np.where(ok, r2 // d, POS_INF)
                        t2 = np.where(ok, r2, POS_INF)
                        better = (c2 < best_c) | ((c2 == best_c) & (t2 < best_t))
                        best_c = np.where(better, c2, best_c)
                        best_t = np.where(better, t2, best_t)
                    dom = (row >= 0) & ((best_c < cells[i, k]) | ((best_c == cells[i, k]) & (best_t <= row)))
                    keep[i, k] &= ~dom
        ti, tk, hj = np.nonzero(keep)
        self.mv = {"ti": ti.astype(np.int64), "tk": tk.astype(np.int64), "hi": hj.astype(np.int64),
                   "hk": cells[ti, tk, hj].astype(np.int64), "entry": EA[ti, tk, hj].astype(float)}
        self.ea_calls = ea_calls
        self.moves_all = int((EA >= 0).sum())
        # vehicle entries: (vehicle, head location, head cell, entry time)
        self.src: dict[str, list[tuple[int, int, float]]] = {}
        for v in self.inst.vehicles:
            s = float(v.start_s)
            end = H if v.shift_limit_s is None else min(H, s + float(v.shift_limit_s))
            out = []
            if v.depot in self.loc_of_node:
                i = self.loc_of_node[v.depot]
                if s <= end:
                    out.append((i, int(s // d), s))
            else:
                ea = rh.earliest_arrival_neg(rh.node(v.depot), int(s))
                for j in range(self.L):
                    if not self.has_facility[j]:
                        continue                                   # the first stop boards someone
                    a = int(ea[self.vnode[j]])
                    if a >= POS_INF or a > end or a > hi_loc[j]:
                        continue
                    out.append((j, a // d, float(a)))
            self.src[v.id] = out

    # ---------------------------------------------------------------------------------------- LP
    def build(self) -> FlowModel:
        t0 = time.monotonic()
        d, L, KT = self.delta, self.L, self.KT
        mv = self.mv
        cols_cost: list[float] = []
        cols_hi: list[float] = []
        rows = _Rows()

        names: list[str] | None = [] if self.debug_names else None

        def col(hi: float, cost: float = 0.0, name=None) -> int:
            cols_cost.append(cost)
            cols_hi.append(hi)
            if names is not None:
                names.append(name() if callable(name) else str(name))
            return len(cols_cost) - 1

        board_glob: dict[tuple[str, int], list[int]] = defaultdict(list)
        unload_glob: dict[tuple[str, int], list[int]] = defaultdict(list)
        stats = {"groups": len(self.groups), "move_arcs": 0, "wait_arcs": 0, "nodes": 0, "ea_calls": self.ea_calls,
                 "physical_moves": self.moves_all, "physical_moves_kept": int(mv["ti"].size)}
        order_k = np.argsort(mv["tk"], kind="stable")
        for g in self.groups:
            k0 = int(min(s // d for s in g.starts))
            kE = min(KT, max(g.k_ends))
            if kE < k0:
                continue
            s_min, e_max = min(g.starts), max(g.ends)
            cls = [c for c in self.classes if g.cap[c] > 0]
            # ---- arcs of this group: moves inside its window, waits, entries
            sel = (mv["tk"] >= k0) & (mv["hk"] <= kE) & (mv["entry"] <= e_max)
            m_idx = order_k[sel[order_k]]
            srcs = []                                               # (vehicle index in group, loc, k, entry)
            for vi, vid in enumerate(g.vehicles):
                for (j, kk, a) in self.src[vid]:
                    if kk <= g.k_ends[vi] and kk <= kE:
                        srcs.append((vi, j, kk, a))
            # ---- reachability (every arc advances the cell)
            F = np.zeros((L, KT + 2), dtype=bool)
            for _, j, kk, _ in srcs:
                F[j, kk] = True
            tk, ti, hk, hi_ = mv["tk"], mv["ti"], mv["hk"], mv["hi"]
            by_k: dict[int, np.ndarray] = {}
            if m_idx.size:
                ks = tk[m_idx]
                bounds = np.searchsorted(ks, np.arange(k0, kE + 2))
                for n, k in enumerate(range(k0, kE + 1)):
                    by_k[k] = m_idx[bounds[n]:bounds[n + 1]]
            for k in range(k0, kE + 1):
                if k < kE:
                    F[:, k + 1] |= F[:, k]
                a = by_k.get(k)
                if a is not None and a.size:
                    ok = F[ti[a], k]
                    F[hi_[a[ok]], hk[a[ok]]] = True
            B = np.zeros((L, KT + 2), dtype=bool)
            for i in range(L):
                if self.has_shelter[i]:
                    B[i, k0:kE + 1] = True
            for k in range(kE, k0 - 1, -1):
                if k < kE:
                    B[:, k] |= B[:, k + 1]
                a = by_k.get(k)
                if a is not None and a.size:
                    ok = B[hi_[a], hk[a]]
                    B[ti[a[ok]], k] = True
            alive = F & B
            alive[:, kE + 1:] = False
            alive[:, :k0] = False
            keep = alive[ti[m_idx], tk[m_idx]] & alive[hi_[m_idx], hk[m_idx]] if m_idx.size else np.zeros(0, bool)
            m_idx = m_idx[keep]
            stats["move_arcs"] += int(m_idx.size)
            stats["nodes"] += int(alive.sum())
            # ---- columns: vehicle flow
            node_in: dict[tuple[int, int], list[tuple[int, int, float]]] = defaultdict(list)   # -> (x col, kind, entry)
            node_out: dict[tuple[int, int], list[int]] = defaultdict(list)
            # (x col, load cols by class, free-space cols by class (arcs into facility-only nodes), tail, head)
            arc_load_cols: list[tuple[int, dict[int, int], dict[int, int], tuple[int, int] | None, tuple[int, int]]] = []
            n_g = float(g.count)

            def free_space(head: tuple[int, int], what: str) -> dict[int, int]:
                if not self.free_space or self.has_shelter[head[0]]:
                    return {}
                return {c: col(g.cap[c] * n_g, name=lambda: f"{g.name}:free{c}{what}") for c in cls}
            for a in m_idx.tolist():
                tail, head = (int(ti[a]), int(tk[a])), (int(hi_[a]), int(hk[a]))
                x = col(n_g, name=lambda: f"{g.name}:move{tail}->{head}@{mv['entry'][a]:g}")
                node_out[tail].append(x)
                node_in[head].append((x, MOVE, float(mv["entry"][a])))
                arc_load_cols.append((x, {c: col(g.cap[c] * n_g, name=lambda: f"{g.name}:load{c}{tail}->{head}")
                                          for c in cls}, free_space(head, f"{tail}->{head}"), tail, head))
            for i in range(L):
                ks = np.flatnonzero(alive[i, :KT + 1] & alive[i, 1:KT + 2])
                for k in ks.tolist():
                    x = col(n_g, name=lambda: f"{g.name}:wait({i},{k})")
                    stats["wait_arcs"] += 1
                    node_out[(i, k)].append(x)
                    node_in[(i, k + 1)].append((x, WAIT, float((k + 1) * d)))
                    arc_load_cols.append((x, {c: col(g.cap[c] * n_g, name=lambda: f"{g.name}:load{c}wait({i},{k})")
                                              for c in cls}, free_space((i, k + 1), f"wait({i},{k})"), (i, k), (i, k + 1)))
            src_cols: dict[int, list[int]] = defaultdict(list)
            for vi, j, kk, a in srcs:
                if not alive[j, kk]:
                    continue
                x = col(1.0, name=lambda: f"{g.name}:src{vi}->({j},{kk})@{a:g}")
                src_cols[vi].append(x)
                node_in[(j, kk)].append((x, SOURCE, a))
                arc_load_cols.append((x, {}, free_space((j, kk), f"src{vi}"), None, (j, kk)))
            end_cols: dict[int, list[int]] = defaultdict(list)          # k -> end columns
            for i in range(L):
                if not self.has_shelter[i]:
                    continue
                for k in np.flatnonzero(alive[i, :KT + 1]).tolist():
                    x = col(n_g, name=lambda: f"{g.name}:end({i},{k})")
                    node_out[(i, k)].append(x)
                    end_cols[k].append(x)
            # ---- columns: boardings and unloadings (per site, class, cell where the group can be there)
            acts: dict[tuple[int, int], list[tuple[int, int, int, float]]] = defaultdict(list)   # node -> (site, c, col, secs)
            board_grp: dict[tuple[int, int], list[int]] = defaultdict(list)                       # (site, c) -> cols
            for si, site in enumerate(self.sites):
                i = site.loc
                for c in cls:
                    if site.limit[c] <= 0 or not site.usable[c]:
                        continue
                    for k in np.flatnonzero(alive[i, :KT + 1]).tolist():
                        lo, hi = k * d, (k + 1) * d
                        if not _meets(max(lo, s_min), min(hi, e_max + EPS_T), site.usable[c]):
                            continue
                        if site.kind == "facility":
                            x = col(float(site.limit[c]), name=lambda: f"{g.name}:board{site.id}c{c}k{k}")
                            board_glob[(site.id, c)].append(x)
                            board_grp[(si, c)].append(x)
                        else:
                            x = col(float(min(site.limit[c], self.N[c])), cost=1.0,
                                    name=lambda: f"{g.name}:unload{site.id}c{c}k{k}")
                            unload_glob[(site.id, c)].append(x)
                        acts[(i, k)].append((si, c, x, site.secs[c]))
            # ---- rows: vehicle flow conservation, one entry per vehicle at most
            nodes = set(node_in) | set(node_out)
            for nd in nodes:
                cs = [x for x, _, _ in node_in.get(nd, ())] + node_out.get(nd, [])
                vs = [1.0] * len(node_in.get(nd, ())) + [-1.0] * len(node_out.get(nd, []))
                rows.add(cs, vs, 0.0, 0.0)
            for vi, cs in src_cols.items():
                rows.add(cs, [1.0] * len(cs), -math.inf, 1.0)
            # cumulative ends (pooled vehicles): a vehicle whose shift ends in cell kv has ended by kv
            if g.count > 1:
                ends_sorted = sorted(end_cols)
                for kv in sorted(set(g.k_ends)):
                    if kv >= kE:
                        continue
                    done = [x for k in ends_sorted if k <= kv for x in end_cols[k]]
                    must = [x for vi, cs in src_cols.items() if g.k_ends[vi] <= kv for x in cs]
                    if must:
                        rows.add(done + must, [1.0] * len(done) + [-1.0] * len(must), 0.0, math.inf)
            # ---- rows: loads (conservation per class and node, capacity per class and arc)
            lin: dict[tuple[int, int, int], list[int]] = defaultdict(list)
            lout: dict[tuple[int, int, int], list[int]] = defaultdict(list)
            zin: dict[tuple[int, int, int], list[int]] = defaultdict(list)
            zout: dict[tuple[int, int, int], list[int]] = defaultdict(list)
            for x, lc, zc, tail, head in arc_load_cols:
                for c in cls:
                    y, z = lc.get(c), zc.get(c)
                    if y is None and z is None:
                        continue
                    cs = [x] + [q for q in (y, z) if q is not None]
                    rows.add(cs, [-float(g.cap[c])] + [1.0] * (len(cs) - 1), -math.inf, 0.0)   # load + free <= space
                    if y is not None:
                        lout[(tail[0], tail[1], c)].append(y)
                        lin[(head[0], head[1], c)].append(y)
                    if z is not None:
                        zin[(head[0], head[1], c)].append(z)
                        if tail is not None:
                            zout[(tail[0], tail[1], c)].append(z)
            act_terms: dict[tuple[int, int, int], list[tuple[int, float]]] = defaultdict(list)
            for nd, lst in acts.items():
                for si, c, x, _ in lst:
                    act_terms[(nd[0], nd[1], c)].append((x, 1.0 if self.sites[si].kind == "facility" else -1.0))
            for key in set(lin) | set(lout) | set(act_terms):
                cs = lin.get(key, []) + lout.get(key, []) + [x for x, _ in act_terms.get(key, ())]
                vs = [1.0] * len(lin.get(key, [])) + [-1.0] * len(lout.get(key, [])) + [s for _, s in act_terms.get(key, ())]
                rows.add(cs, vs, 0.0, 0.0)
            # free space at a facility-only node: what leaves (to facility-only nodes) plus what is boarded is at most
            # what arrives (free space is created only by unloading, at shelters, or at the vehicle's entry)
            for key in set(zin):
                boards = [x for x, sgn in act_terms.get(key, ()) if sgn > 0]
                cs = zin[key] + zout.get(key, []) + boards
                vs = [1.0] * len(zin[key]) + [-1.0] * (len(zout.get(key, [])) + len(boards))
                rows.add(cs, vs, 0.0, math.inf)
            # ---- rows: seconds of boarding / unloading <= usable seconds the group is there
            for nd, lst in acts.items():
                i, k = nd
                lo, hi = k * d, (k + 1) * d
                by_site: dict[int, list[tuple[int, float]]] = defaultdict(list)
                for si, c, x, secs in lst:
                    if secs > 0:
                        by_site[si].append((x, secs))
                if not by_site:
                    continue
                arrivals = node_in.get(nd, [])
                groups_of_rows = [(si, self.sites[si].union, terms) for si, terms in by_site.items()]
                if len(by_site) > 1:
                    groups_of_rows.append((-1, self.loc_union[i], [t for ts in by_site.values() for t in ts]))
                for _, ivs, terms in groups_of_rows:
                    cs = [x for x, _ in terms]
                    vs = [s for _, s in terms]
                    for x, kind, entry in arrivals:
                        start = lo if kind == WAIT else max(lo, entry)
                        cap = _measure(max(start, s_min), min(hi, e_max), ivs)
                        if cap > 0:
                            cs.append(x)
                            vs.append(-round(cap, 6))
                    rows.add(cs, vs, -math.inf, 0.0)
            # ---- rows: what one vehicle can board at one facility before it closes (trip cuts, see trip_limits)
            if self.trip_cuts:
                for si, site in enumerate(self.sites):
                    if site.kind != "facility":
                        continue
                    lim = [self.trip_limits(v, si) for v in g.vehicles]
                    secs_terms = []
                    for c in cls:
                        cs = board_grp.get((si, c), [])
                        if not cs:
                            continue
                        n_max = sum(lv["n"][c] for lv in lim)
                        if math.isfinite(n_max):
                            rows.add(cs, [1.0] * len(cs), -math.inf, float(n_max))
                        if site.secs[c] > 0:
                            secs_terms += [(x, site.secs[c]) for x in cs]
                    s_max = sum(lv["secs"] for lv in lim)
                    if secs_terms and math.isfinite(s_max):
                        rows.add([x for x, _ in secs_terms], [v for _, v in secs_terms], -math.inf, float(s_max))
                        stats["trip_cut_rows"] = stats.get("trip_cut_rows", 0) + 1
        # ---- shared rows: residents per facility and class, shelter capacity per class
        fac = {f.id: f for f in self.inst.facilities}
        shel = {s.id: s for s in self.inst.shelters}
        for (fid, c), cs in board_glob.items():
            rows.add(cs, [1.0] * len(cs), -math.inf, float(fac[fid].residents.vector()[c]))
        for (sid, c), cs in unload_glob.items():
            rows.add(cs, [1.0] * len(cs), -math.inf, float(shel[sid].capacity.vector()[c]))
        ncol = len(cols_cost)
        start, index, value, rlo, rhi = rows.assemble(ncol)
        stats.update({"rows": int(rlo.size), "cols": ncol, "nnz": int(value.size), "build_s": time.monotonic() - t0,
                      **{k: round(v, 3) for k, v in self.timing.items()}})
        stats["build_s"] = round(stats["build_s"], 3)
        return FlowModel(cost=np.asarray(cols_cost, float), lower=np.zeros(ncol), upper=np.asarray(cols_hi, float),
                         row_lower=rlo, row_upper=rhi, a_start=start, a_index=index, a_value=value, delta=self.delta,
                         grouping=self.grouping, note=self.note, stats=stats, unload_cols=dict(unload_glob),
                         board_cols=dict(board_glob), names=names)


# ----------------------------------------------------------------------------------------- certificate
def dual_bound(arrays: dict[str, np.ndarray], pi: np.ndarray) -> tuple[float, float]:
    """Weak duality for ``max c x, L <= A x <= U, l <= x <= u``: for ANY row multipliers ``pi``,
    ``c x = pi (A x) + (c - A^T pi) x <= sum_i max(pi_i L_i, pi_i U_i) + sum_j max(d_j l_j, d_j u_j)``.
    Multipliers of the wrong sign on a one-sided row are set to 0 (still any ``pi``). Returns the bound and a
    bound on its floating-point error; ``inf`` when a needed bound is infinite."""
    c, l, u = arrays["cost"], arrays["lower"], arrays["upper"]
    L, U = arrays["row_lower"], arrays["row_upper"]
    start, index, value = arrays["a_start"], arrays["a_index"], arrays["a_value"]
    pi = np.asarray(pi, dtype=float).copy()
    pi[~np.isfinite(pi)] = 0.0
    pi[np.isinf(L) & (pi < 0)] = 0.0
    pi[np.isinf(U) & (pi > 0)] = 0.0
    rows = np.repeat(np.arange(L.size), np.diff(start))
    prod = value * pi[rows]
    d = c - np.bincount(index, weights=prod, minlength=c.size)
    mag_d = np.abs(c) + np.bincount(index, weights=np.abs(prod), minlength=c.size)
    with np.errstate(invalid="ignore"):
        rt = np.where(pi > 0, pi * np.where(np.isinf(U), 0.0, U), np.where(pi < 0, pi * np.where(np.isinf(L), 0.0, L), 0.0))
        ct = np.where(d > 0, d * u, np.where(d < 0, d * l, 0.0))
    if np.any(~np.isfinite(ct)) or np.any(~np.isfinite(rt)):
        return math.inf, math.inf
    bound = math.fsum(rt.tolist()) + math.fsum(ct.tolist())
    bnd = np.where(np.isinf(U), 0.0, np.abs(U)) + np.where(np.isinf(L), 0.0, np.abs(L))
    mag = float(np.sum(np.abs(pi) * bnd) + np.sum(mag_d * np.maximum(np.abs(l), np.abs(u))))
    err = 1e-12 * mag + 1e-9            # far above float64 rounding of these sums (~1e-16 per term)
    return bound, err


def certified_value(arrays: dict[str, np.ndarray], pi: np.ndarray | None) -> tuple[float, dict]:
    """The smallest weak-duality bound over ``pi`` and ``-pi`` (both are valid; HiGHS's sign convention for a
    maximization is not relied on), plus its error margin."""
    if pi is None and arrays["row_lower"].size == 0:
        pi = np.zeros(0)                          # no rows: weak duality needs no multipliers
    if pi is None:
        return math.inf, {"dual_bound": None}
    best, best_err = math.inf, math.inf
    for p in (pi, -pi):
        b, e = dual_bound(arrays, p)
        if b + e < best + best_err:
            best, best_err = b, e
    return best, {"dual_bound": None if not math.isfinite(best) else best, "dual_bound_err": best_err}


def flow_bound(instance: Instance, scenario_set=None, *, reach: Reach | None = None, delta_s: int = 60,
               grouping: str = "vehicle", time_limit: float = 600.0, threads: int = 1, solver: str = "ipm",
               crossover: bool = False, ipm_tolerance: float | None = 1e-6, prune_dominated: bool = True,
               free_space: bool = True, trip_cuts: bool = True, fallback: str | None = "pdlp",
               fallback_share: float = 0.7) -> tuple[int, dict]:
    """The E4 bound of one instance (whole residents) and how it was obtained. ``solver`` gets ``fallback_share`` of
    the time left; if it returns no usable duals, ``fallback`` (PDLP) gets the rest (``fallback=None``: one solver,
    all the time)."""
    t0 = time.monotonic()
    rb = trivial_bound(instance)
    info: dict = {"resource_bound": rb, "delta_s": int(delta_s), "grouping": grouping, "free_space": bool(free_space),
                  "trip_cuts": bool(trip_cuts)}
    rh = reach or Reach(instance, scenario_set)
    info["reach_s"] = round(time.monotonic() - t0, 3)
    try:
        net = FlowNetwork(instance, rh, delta_s=delta_s, grouping=grouping, prune_dominated=prune_dominated,
                          free_space=free_space, trip_cuts=trip_cuts)
    except NotCertified as exc:
        info.update(certified=False, note=f"not certified: {exc}; the resource bound only", bound=rb)
        return rb, info
    model = net.build()
    info.update(certified=True, note=model.note, delta_eff_s=model.delta, lp=model.stats)
    if not np.any(model.cost > 0):
        # no unloading can happen anywhere in the network: every delivering plan would map to one, so none exists
        info.update(lp_status="no unloading in the network", dual_bound=0.0, dual_bound_err=0.0, bound=0,
                    total_s=round(time.monotonic() - t0, 3))
        return 0, info
    left = max(1.0, time_limit - (time.monotonic() - t0))
    arrays = model.arrays()
    # the main solver gets most of the time; if it leaves no usable duals (e.g. its time limit), PDLP gets the rest:
    # any duals give a valid bound (certified_value), approximate ones only a looser one
    share = left if fallback is None else max(1.0, fallback_share * left)
    res = solve_lp(arrays, time_limit=share, threads=threads, solver=solver, crossover=crossover,
                   ipm_tolerance=ipm_tolerance)
    info.update(lp_status=res.status, lp_objective=res.objective, lp_solve_s=None if res.solve_s != res.solve_s
                else round(res.solve_s, 3), lp_wall_s=round(res.wall_s, 3), lp_solver=solver)
    ub, cert = certified_value(arrays, res.row_dual)
    rest = time_limit - (time.monotonic() - t0)
    if fallback is not None and (not math.isfinite(ub) or res.status not in ("Optimal", "Empty")) and rest > 5.0:
        res2 = solve_lp(arrays, time_limit=rest - 2.0, threads=threads, solver=fallback, crossover=False)
        ub2, cert2 = certified_value(arrays, res2.row_dual)
        info["fallback"] = {"solver": fallback, "status": res2.status, "objective": res2.objective,
                            "dual_bound": cert2.get("dual_bound"), "wall_s": round(res2.wall_s, 3)}
        if ub2 + cert2.get("dual_bound_err", math.inf) < ub + cert.get("dual_bound_err", math.inf):
            ub, cert, res = ub2, cert2, res2
            info["lp_solver"] = fallback
    info.update(cert)
    bound = rb
    if math.isfinite(ub):
        bound = min(rb, int(math.floor(ub + cert["dual_bound_err"])))
    if res.x is not None:
        info["lp_unloaded_by_class"] = [round(float(sum(res.x[cc].sum() for (s, c), cc in model.unload_cols.items()
                                                        if c == k)), 3) for k in range(3)]
    info["bound"] = bound
    info["total_s"] = round(time.monotonic() - t0, 3)
    return bound, info


# --------------------------------------------------------------------------------------------- method
class E4FlowBound(Method):
    """Bound only: returns the empty plan and ``best_bound`` (see the module docstring)."""

    name = "e4_flow_bound"
    bound_only = True

    def __init__(self, delta_s: int = 60, grouping: str = "auto", large_delta_s: int = 120, large_facilities: int = 10,
                 threads: int = 1, solver: str = "ipm", crossover: bool = False, ipm_tolerance: float = 1e-6,
                 fallback: str | None = "pdlp", **config):
        """``grouping="auto"``: one commodity per vehicle, except on instances with more than ``large_facilities``
        facilities (size L), where identical vehicles are pooled and the step is ``large_delta_s``."""
        if grouping not in (*GROUPINGS, "auto"):
            raise ValueError(f"grouping must be one of {GROUPINGS} or 'auto'")
        for v in (delta_s, large_delta_s):
            if int(v) != v or v < 1:
                raise ValueError("time steps must be whole numbers of seconds >= 1")
        super().__init__(delta_s=int(delta_s), grouping=grouping, large_delta_s=int(large_delta_s),
                         large_facilities=int(large_facilities), threads=int(threads), solver=solver,
                         crossover=bool(crossover), ipm_tolerance=float(ipm_tolerance), fallback=fallback, **config)
        self.delta, self.grouping, self.threads = int(delta_s), grouping, int(threads)
        self.large_delta, self.large_facilities = int(large_delta_s), int(large_facilities)
        self.solver, self.crossover, self.ipm_tolerance = solver, bool(crossover), float(ipm_tolerance)
        self.fallback = fallback

    def setting(self, instance) -> tuple[int, str]:
        """(time step, grouping) for ``instance``."""
        large = len(instance.facilities) > self.large_facilities
        if self.grouping != "auto":
            return (self.large_delta if large else self.delta), self.grouping
        return (self.large_delta, "type") if large else (self.delta, "vehicle")

    def solve(self, instance, scenario_set, *, budget_s, seed, deadline) -> MethodResult:
        empty = Solution(instance=instance.name, method=self.name, itineraries=[],
                         provenance={"seed": int(seed), "note": "E4 flow-over-time bound: no plan (bound only)"})
        left = deadline - time.monotonic() - (0.5 + 0.02 * budget_s)
        delta, grouping = self.setting(instance)
        bound, info = flow_bound(instance, scenario_set, delta_s=delta, grouping=grouping,
                                 time_limit=max(1.0, left), threads=self.threads, solver=self.solver,
                                 crossover=self.crossover, ipm_tolerance=self.ipm_tolerance, fallback=self.fallback)
        diag = {k: info.get(k) for k in ("certified", "delta_s", "delta_eff_s", "grouping", "lp_status", "lp_objective",
                                         "dual_bound", "resource_bound", "bound", "lp_solve_s", "total_s",
                                         "lp_solver", "free_space", "trip_cuts")}
        lp = info.get("lp") or {}
        diag.update({k: lp.get(k) for k in ("rows", "cols", "nnz")})
        return MethodResult(empty, best_bound=float(bound), info=info, diagnostics=diag)


__all__ = ["E4FlowBound", "FlowModel", "FlowNetwork", "NotCertified", "certified_value", "dual_bound", "flow_bound"]
