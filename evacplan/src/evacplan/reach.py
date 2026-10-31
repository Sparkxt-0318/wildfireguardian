"""RELAXED time-dependent reachability on the 1 s lattice: departure masks, the backward
latest-safe-departure sweep, forward routing and the certain-contact relaxation.

Nothing in this module is a final state (program rule 3): it prunes and guides searches and
produces candidates (witness trips, relaxation claims) that :mod:`evacplan.oracle` turns into
``checked`` / ``model_no_route`` / ``unresolved``.

Lattice
-------
Every decision time is a whole second on the instance clock, from 0 to ``Hi`` = floor(horizon -
``t0_offset_s``): the oracle never checks an occupancy that ends after the hazard horizon, so a
plan that can be delivered lives in [0, Hi]. Travel times, per-resident boarding and unloading
times and vehicle start times must be whole seconds (:class:`LatticeError` otherwise; the
generators and the router graphs are). Shelter windows, release times and shift limits are rounded
inwards (later opening, earlier closing).

Two relaxations of the oracle's leg rule (same occupancies as the oracle: uniform motion along each
edge, closed cells, :func:`evacplan.oracle.contact_records`)
-----------------------------------------------------------------------------------------------
* POSITIVE ("checkable"): a departure is usable iff no touched cell burns at any instant of its
  occupancy in ANY member (touch intervals widened by ``margin_s``), every touched cell is supported
  in every member, the edge stays inside the grid and the leg ends by the horizon. A stay at a node
  (wait, boarding, unloading) likewise. Contact-only (no flux, no dose): the oracle may still reject
  a usable leg on peak or dose, never on contact or support.
* NEGATIVE ("not certainly blocked"): a departure is blocked only if the oracle would certainly
  find flame contact up to the horizon in some member (touch intervals narrowed by ``margin_s``).
  Unknown cells are passable, turn rules are ignored, and waiting is allowed anywhere without a
  contact check. If even this relaxation has no route, no plan can deliver the residents (the basis
  of the scoped ``model_no_route`` claims in :mod:`evacplan.deadlines`). The integer lattice is
  complete for it when every cell that starts burning by the horizon keeps burning through it and
  all instance data are whole seconds (:attr:`Reach.lattice_complete`).

Latest-safe-departure sweep (:meth:`Reach.sweep`)
------------------------------------------------
A backward dynamic programme over (state, second), states = "just traversed edge e" (the heading,
for turn rules) and "at node v with a fresh heading" (after boarding or unloading):
``R[t, s] = target(s, t) or wait(s, t) and R[t+1, s] or any(usable(e', t) and R[t + T_e', e'])``
over the successors e' allowed by the turn rules. Waiting keeps the heading and needs a waitable
node and a usable 1 s stay; the target is unloading one resident of the class at a shelter that
accepts it, inside an opening window, with a usable stay, by the horizon. Exact on the lattice for
any hazard (no monotonicity assumed), with all K members at once.
"""
from __future__ import annotations

import heapq
import math
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

import hazard_contract as hc
from hazard_contract.geometry import polyline_cells

from .oracle import contact_records
from .schema import CLASSES, Drive, Instance, InstanceIndex, Wait

MARGIN_S = 1e-6
WINDOW_TOL_S = 1e-6        # the validator's TIME_TOL_S
NEG_INF = -(1 << 60)
POS_INF = 1 << 60


class LatticeError(ValueError):
    """The instance is not on the whole-second lattice this module works on."""


def _is_int(x: float) -> bool:
    return math.isfinite(float(x)) and float(x).is_integer()


@dataclass(frozen=True)
class Route:
    """A timed path: ``steps`` = ((edge index, departure), ...); waits are the gaps between the
    arrival at a node and the next departure from it (or before the first departure)."""

    start: int
    arrival: int
    steps: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class ClassTarget:
    """Unloading ONE resident of a class at a shelter (the sweep's target)."""

    shelter: str
    node: int
    unload_s: int
    windows: tuple[tuple[int, int], ...]     # rounded inwards: [ceil(open), floor(close)]


class Reach:
    """Relaxed reachability for one instance and scenario set (build once; reuse)."""

    def __init__(self, instance: Instance, scenario_set: hc.ScenarioSet, *, index: InstanceIndex | None = None,
                 margin_s: float = MARGIN_S):
        if instance.graph.crs_epsg != scenario_set.meta.crs_epsg:
            raise ValueError(f"graph CRS EPSG:{instance.graph.crs_epsg} != hazard CRS EPSG:{scenario_set.meta.crs_epsg}")
        self.instance = instance
        self.ss = scenario_set
        self.index = index or InstanceIndex(instance)
        self.margin = float(margin_s)
        self.off = float(instance.hazard.t0_offset_s)
        self.horizon = float(scenario_set.meta.horizon_s)
        self.H = self.horizon - self.off
        if not self.H >= 0:
            raise LatticeError("the hazard horizon ends before instance time 0")
        self.Hi = int(math.floor(self.H + 1e-9))
        self._check_lattice()

        g = instance.graph
        self.node_ids = [n.id for n in g.nodes]
        self.nidx = {n: i for i, n in enumerate(self.node_ids)}
        self.N = len(self.node_ids)
        self.waitable = np.array([n.waitable for n in g.nodes], dtype=bool)
        order = sorted(range(len(g.edges)), key=lambda i: (self.nidx[g.edges[i].u], i))
        self.edge_ids = [g.edges[i].id for i in order]
        self.eidx = {e: i for i, e in enumerate(self.edge_ids)}
        self.E = len(self.edge_ids)
        self.tail = np.array([self.nidx[g.edges[i].u] for i in order], dtype=np.int64)
        self.head = np.array([self.nidx[g.edges[i].v] for i in order], dtype=np.int64)
        self.T = np.array([int(g.edges[i].travel_time_s) for i in order], dtype=np.int64)
        self.Tl = self.T.tolist()
        self.headl = self.head.tolist()
        self.taill = self.tail.tolist()
        nodes = np.arange(self.N)
        self.out_start = np.searchsorted(self.tail, nodes, side="left")
        self.out_end = np.searchsorted(self.tail, nodes, side="right")
        self.out = [list(range(int(a), int(b))) for a, b in zip(self.out_start, self.out_end)]
        self.inc: list[list[int]] = [[] for _ in range(self.N)]
        for e in range(self.E):
            self.inc[self.headl[e]].append(e)
        forb: dict[int, list[int]] = defaultdict(list)
        for a, b in g.forbidden_turns:
            forb[self.eidx[a]].append(self.eidx[b])
        self.forbidden = {k: frozenset(v) for k, v in forb.items()}
        width = max((len(v) for v in self.forbidden.values()), default=1)
        self.forb_pad = np.full((self.E, width), self.E, dtype=np.int64)     # self.E = the zero sentinel column
        for e, ban in self.forbidden.items():
            self.forb_pad[e, :len(ban)] = sorted(ban)

        self._edge_masks()
        self._node_masks()
        self.lattice_complete, self.lattice_note = self._completeness()
        self._static: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        self._lower: dict[int, np.ndarray] = {}

    # ------------------------------------------------------------------------ lattice data
    def _check_lattice(self) -> None:
        inst = self.instance
        bad = [e.id for e in inst.graph.edges if not _is_int(e.travel_time_s)]
        if bad:
            raise LatticeError(f"travel times must be whole seconds (e.g. edge {bad[0]!r})")
        for f in inst.facilities:
            if not all(_is_int(x) for x in f.boarding_s.vector()):
                raise LatticeError(f"facility {f.id!r}: boarding times must be whole seconds")
            if f.release_s < 0:
                raise LatticeError(f"facility {f.id!r}: negative release time")
        for s in inst.shelters:
            if not all(_is_int(x) for x in s.unloading_s.vector()):
                raise LatticeError(f"shelter {s.id!r}: unloading times must be whole seconds")
        for v in inst.vehicles:
            if not _is_int(v.start_s) or v.start_s < 0:
                raise LatticeError(f"vehicle {v.id!r}: start time must be a whole, non-negative second")

    def _integer_data(self) -> bool:
        inst = self.instance
        vals = [self.off] + [f.release_s for f in inst.facilities]
        vals += [x for s in inst.shelters for w in s.open_windows for x in w]
        vals += [v.shift_limit_s for v in inst.vehicles if v.shift_limit_s is not None]
        return all(_is_int(x) for x in vals)

    def _completeness(self) -> tuple[bool, str]:
        ss = self.ss
        burns = ss.supported & (ss.extinguish_s > ss.ignite_s) & (ss.ignite_s <= self.horizon)
        stops = bool(np.any(burns & (ss.extinguish_s <= self.horizon)))
        if stops:
            return False, "a cell stops burning within the horizon (non-monotone hazard)"
        if not self._integer_data():
            return False, "instance times are not all whole seconds"
        return True, "monotone hazard within the horizon and whole-second data"

    # -------------------------------------------------------------------------- masks
    def _edge_records(self):
        """Contact records of every edge for a departure at 0 (reverse edges reuse their twin's,
        mirrored in time): ``(edge, row, col, s0, s1)`` arrays and the per-edge outside flags."""
        grid, E = self.ss.grid, self.E
        g = self.instance.graph
        geo = {e.id: e.geometry for e in g.edges}
        seen: dict[tuple, int] = {}
        recs: list = [None] * E
        outside = np.zeros(E, dtype=bool)
        for e in range(E):
            eid = self.edge_ids[e]
            u, v, T = self.taill[e], self.headl[e], self.Tl[e]
            gm = geo[eid]
            key = (u, v, T, None if gm is None else tuple(map(tuple, gm)))
            twin_key = (v, u, T, None if gm is None else tuple(map(tuple, gm[::-1])))
            j = seen.get(twin_key)
            if j is not None:
                rows, cols, t0, t1 = recs[j]
                recs[e] = (rows, cols, T - t1, T - t0)
                outside[e] = outside[j]
            else:
                rows, cols, t0, t1, out = contact_records(grid, self.index.edge_geometry(eid), 0.0, float(T))
                recs[e] = (rows, cols, t0, t1)
                outside[e] = bool(out)
            seen.setdefault(key, e)
        cat = [np.concatenate([np.full(r[0].size, e, dtype=np.int64) for e, r in enumerate(recs)])]
        for i in range(4):
            cat.append(np.concatenate([r[i] for r in recs]))
        return cat, outside

    def _edge_masks(self) -> None:
        ss, m, off, Hi, E = self.ss, self.margin, self.off, self.Hi, self.E
        (re_, rr_, rc_, s0, s1), outside = self._edge_records()
        sup_all = np.all(ss.supported[:, rr_, rc_], axis=0)
        bad = np.zeros(E, dtype=bool)
        np.logical_or.at(bad, re_[~sup_all], True)
        self.edge_unsupported = bad | outside
        pos: list[list[tuple[int, int]]] = [[] for _ in range(E)]
        neg: list[list[tuple[int, int]]] = [[] for _ in range(E)]
        with np.errstate(invalid="ignore"):
            for k in range(ss.K):
                ig = ss.ignite_s[k, rr_, rc_]
                ex = ss.extinguish_s[k, rr_, rc_]
                j = np.flatnonzero(ss.supported[k, rr_, rc_] & (ex > ig) & (ig < np.inf))
                if not j.size:
                    continue
                # POSITIVE: contact iff ignite <= d + off + s1 and extinguish > d + off + s0 (widened by m)
                lo = _ceil_clip(ig[j] - off - s1[j] - m, 0, Hi + 1)
                hi = _ceil_clip(ex[j] - off - s0[j] + m, 0, Hi + 2) - 1
                for e, a, b in zip(re_[j].tolist(), lo.tolist(), hi.tolist()):
                    if a <= min(b, Hi):
                        pos[e].append((a, min(b, Hi)))
                # NEGATIVE: certain contact with its first instant by the horizon (narrowed by m)
                sel = j[ig[j] <= self.horizon - m]
                if sel.size:
                    lo2 = _ceil_clip(ig[sel] - off - s1[sel] + m, -POS_INF, POS_INF)
                    hi2 = np.minimum(_ceil_clip(ex[sel] - off - s0[sel] - m, -POS_INF, POS_INF) - 1,
                                     _floor_clip(self.horizon - off - s0[sel] - m, -POS_INF, POS_INF))
                    for e, a, b in zip(re_[sel].tolist(), lo2.tolist(), hi2.tolist()):
                        if a <= b:
                            neg[e].append((a, b))
        ok = np.zeros((Hi + 1, E), dtype=bool)                      # okT[t, e]: departure at t usable
        self.free_lo: list[list[int]] = []
        self.free_hi: list[list[int]] = []
        self.neg_lo: list[list[int]] = []
        self.neg_hi: list[list[int]] = []
        for e in range(E):
            last = Hi - self.Tl[e]                                     # the leg must end by the horizon
            blo, bhi = _merge_int(pos[e])
            flo, fhi = [], []
            if not self.edge_unsupported[e] and last >= 0:
                a = 0
                for x, y in zip(blo, bhi):
                    if x > last:
                        break
                    if a <= x - 1:
                        flo.append(a)
                        fhi.append(x - 1)
                    a = max(a, y + 1)
                if a <= last:
                    flo.append(a)
                    fhi.append(last)
            for a, b in zip(flo, fhi):
                ok[a:b + 1, e] = True
            self.free_lo.append(flo)
            self.free_hi.append(fhi)
            nlo, nhi = _merge_int(neg[e])
            self.neg_lo.append(nlo)
            self.neg_hi.append(nhi)
        self.okT = ok

    def _node_masks(self) -> None:
        ss, grid, m, off, Hi = self.ss, self.ss.grid, self.margin, self.off, self.Hi
        self.node_unsupported = np.zeros(self.N, dtype=bool)
        self.node_iv: list[tuple[list[float], list[float]]] = []
        W = np.zeros((Hi + 1, self.N), dtype=bool)                   # 1 s wait [t, t+1] usable
        for v, nid in enumerate(self.node_ids):
            rows, cols, outside = polyline_cells(grid, self.index.node_xy(nid))
            uns = bool(outside or (rows.size and not np.all(ss.supported[:, rows, cols])))
            self.node_unsupported[v] = uns
            ivs = []
            if rows.size:
                ig = ss.ignite_s[:, rows, cols].ravel()
                ex = ss.extinguish_s[:, rows, cols].ravel()
                sup = ss.supported[:, rows, cols].ravel()
                with np.errstate(invalid="ignore"):
                    b = sup & (ex > ig) & (ig < np.inf)
                ivs = sorted(zip((ig[b] - off - m).tolist(), (ex[b] - off + m).tolist()))
            lo, hi = _merge_float(ivs)
            self.node_iv.append((lo, hi))
            if self.waitable[v] and not uns and Hi >= 1:
                W[: Hi, v] = True
                for a, b in zip(lo, hi):                      # stay [t, t+1] meets [a, b) iff t >= a-1 and t < b
                    t0 = int(_ceil_clip(np.array([a - 1]), 0, Hi + 1)[0])
                    t1 = int(_ceil_clip(np.array([b]), 0, Hi + 1)[0]) - 1
                    if t0 <= t1:
                        W[t0:t1 + 1, v] = False
        self.WT = W

    # ------------------------------------------------------------------- primitives
    def node(self, node_id: str) -> int:
        return self.nidx[node_id]

    def stay_ok(self, v: int, a: float, b: float) -> bool:
        """POSITIVE: a stationary occupancy of node ``v`` over [a, b] is usable (no contact in any
        member, supported, ends by the horizon)."""
        if self.node_unsupported[v] or b > self.H + 1e-9 or a > b:
            return False
        lo, hi = self.node_iv[v]
        i = bisect_right(hi, a)                                # first interval with hi > a
        return not (i < len(lo) and lo[i] <= b)

    def depart_ok(self, e: int, t: int) -> bool:
        return 0 <= t <= self.Hi and bool(self.okT[t, e])

    def next_departure(self, e: int, t: int) -> int | None:
        """Earliest usable departure of edge ``e`` at or after ``t`` (POSITIVE)."""
        lo, hi = self.free_lo[e], self.free_hi[e]
        i = bisect_right(lo, t) - 1
        if i >= 0 and t <= hi[i]:
            return t
        return lo[i + 1] if i + 1 < len(lo) else None

    def neg_prev_ok(self, e: int, x: int) -> int:
        """Latest departure <= x of edge ``e`` not certainly blocked (NEGATIVE)."""
        lo, hi = self.neg_lo[e], self.neg_hi[e]
        i = bisect_right(lo, x) - 1
        if i >= 0 and x <= hi[i]:
            return lo[i] - 1
        return x

    def neg_next_ok(self, e: int, t: int) -> int:
        lo, hi = self.neg_lo[e], self.neg_hi[e]
        i = bisect_right(lo, t) - 1
        if i >= 0 and t <= hi[i]:
            return hi[i] + 1
        return t

    # --------------------------------------------------------------------- targets
    def class_targets(self, c: int, *, count: int = 1) -> list[ClassTarget]:
        """Shelters that accept class ``c``: unloading ``count`` residents of it."""
        out = []
        for s in self.instance.shelters:
            if s.capacity.vector()[c] <= 0:
                continue
            u = int(s.unloading_s.vector()[c]) * int(count)
            wins = tuple((int(math.ceil(a - WINDOW_TOL_S)), int(math.floor(b + WINDOW_TOL_S))) for a, b in s.open_windows)
            out.append(ClassTarget(shelter=s.id, node=self.nidx[s.node], unload_s=u, windows=wins))
        return out

    def unload_ok(self, tg: ClassTarget, t: int, unload_s: int | None = None) -> bool:
        u = tg.unload_s if unload_s is None else int(unload_s)
        return (any(a <= t and t + u <= b for a, b in tg.windows) and t + u <= self.Hi
                and self.stay_ok(tg.node, t, t + u))

    def _target_mask(self, tg: ClassTarget) -> np.ndarray:
        """[Hi+1] bool: unloading can start at t (window, usable stay, by the horizon)."""
        Hi, u = self.Hi, tg.unload_s
        mask = np.zeros(Hi + 1, dtype=bool)
        if self.node_unsupported[tg.node]:
            return mask
        for a, b in tg.windows:
            lo, hi = max(a, 0), min(b - u, Hi - u)
            if lo <= hi:
                mask[lo:hi + 1] = True
        for a, b in zip(*self.node_iv[tg.node]):             # stay [t, t+u] meets [a, b) iff t >= a-u and t < b
            t0 = int(_ceil_clip(np.array([a - u]), 0, Hi + 1)[0])
            t1 = int(_ceil_clip(np.array([b]), 0, Hi + 1)[0]) - 1
            if t0 <= t1:
                mask[t0:t1 + 1] = False
        return mask

    # ---------------------------------------------------------------------- sweep
    def sweep(self, targets: list[list[ClassTarget]], fresh_nodes: list[int]) -> "Sweep":
        """The backward latest-safe-departure sweep for several target sets (one per class) at once.
        ``fresh_nodes``: nodes where a fresh-heading state is kept (facilities)."""
        C, E, Hi = len(targets), self.E, self.Hi
        fresh = list(dict.fromkeys(int(v) for v in fresh_nodes))
        F = len(fresh)
        S = E + F
        state_node = np.concatenate([self.head, np.asarray(fresh, dtype=np.int64)])
        tnodes = sorted({tg.node for tgs in targets for tg in tgs})
        trow = np.full(self.N, len(tnodes), dtype=np.int64)
        for i, v in enumerate(tnodes):
            trow[v] = i
        tgt = np.zeros((Hi + 1, C, len(tnodes) + 1), dtype=bool)
        for c, tgs in enumerate(targets):
            for tg in tgs:
                tgt[:, c, trow[tg.node]] |= self._target_mask(tg)
        srow = trow[state_node]
        Tmax = int(self.T.max()) if E else 0
        R = np.zeros((Hi + 2 + Tmax, C, S), dtype=bool)
        ar = np.arange(E)
        cidx = np.arange(C)[:, None]
        out_s, out_e = self.out_start, self.out_end
        fresh_a = np.asarray(fresh, dtype=np.int64)
        cs = np.zeros((C, E + 1), dtype=np.int32)
        Xp = np.zeros((C, E + 1), dtype=bool)
        for t in range(Hi, -1, -1):
            X = R[t + self.T, cidx, ar]                       # [C, E]: arriving via e' at t + T_e' is feasible
            X &= self.okT[t]
            Xp[:, :E] = X
            np.cumsum(X, axis=1, out=cs[:, 1:])
            cnt = cs[:, out_e] - cs[:, out_s]                 # [C, N]: usable successors per node
            mv_e = (cnt[:, self.head] - Xp[:, self.forb_pad].sum(axis=2)) > 0
            row = R[t]
            row[:, :E] = mv_e
            row[:, E:] = cnt[:, fresh_a] > 0
            row |= tgt[t][:, srow]
            row |= R[t + 1] & self.WT[t][state_node]
        return Sweep(self, targets, fresh, R)

    def departure_field(self, classes=(0, 1, 2)) -> np.ndarray:
        """The latest-safe-departure field: ``[len(classes), N]`` int, per node the latest second at which
        a vehicle there with a fresh heading can still leave (or unload) and deliver one resident of the
        class to an open shelter that accepts it (POSITIVE, all K members); -1 where none."""
        classes = list(classes)
        sw = self.sweep([self.class_targets(c) for c in classes], list(range(self.N)))
        col = sw.R[: self.Hi + 1, :, self.E:]                      # [t, class, node]
        any_t = col.any(axis=0)
        last = self.Hi - np.argmax(col[::-1], axis=0)
        return np.where(any_t, last, -1).astype(np.int64)

    # ---------------------------------------------------------- negative relaxation
    def latest_arrival_neg(self, targets: list[ClassTarget]) -> np.ndarray:
        """NEGATIVE relaxation: per node, the latest time a vehicle there can still reach one of
        ``targets`` and unload by the horizon (waiting anywhere, no turn rules, unknown cells
        passable, only certain contact blocks). ``NEG_INF``: never."""
        LD = [NEG_INF] * self.N
        for tg in targets:
            for a, b in tg.windows:
                close = min(b, self.Hi) - tg.unload_s           # unloading must end inside the window, by the horizon
                if close >= a:                                  # arriving earlier: wait (allowed anywhere here)
                    LD[tg.node] = max(LD[tg.node], close)
        heap = [(-x, v) for v, x in enumerate(LD) if x > NEG_INF]
        heapq.heapify(heap)
        done = [False] * self.N
        while heap:
            x, v = heapq.heappop(heap)
            x = -x
            if done[v] or x < LD[v]:
                continue
            done[v] = True
            for e in self.inc[v]:
                u = self.taill[e]
                if done[u]:
                    continue
                cand = self.neg_prev_ok(e, x - self.Tl[e])
                if cand > LD[u]:
                    LD[u] = cand
                    heapq.heappush(heap, (-cand, u))
        return np.array(LD, dtype=np.int64)

    def earliest_arrival_neg(self, src: int, t0: int) -> np.ndarray:
        """NEGATIVE relaxation: earliest arrival at every node from ``src`` at ``t0`` with every leg
        ending by the horizon. ``POS_INF``: never."""
        EA = [POS_INF] * self.N
        EA[src] = int(t0)
        heap = [(int(t0), src)]
        while heap:
            t, v = heapq.heappop(heap)
            if t > EA[v]:
                continue
            for e in self.out[v]:
                d = self.neg_next_ok(e, t)
                a = d + self.Tl[e]
                if a <= self.Hi and a < EA[self.headl[e]]:
                    EA[self.headl[e]] = a
                    heapq.heappush(heap, (a, self.headl[e]))
        return np.array(EA, dtype=np.int64)

    # ------------------------------------------------------------- static routing
    def static_from(self, src: int) -> tuple[np.ndarray, np.ndarray]:
        """Turn-aware free-flow shortest paths from ``src`` (fresh heading) over edge states:
        ``(dist[e], parent[e])``."""
        got = self._static.get(src)
        if got is not None:
            return got
        dist = [POS_INF] * self.E
        parent = [-1] * self.E
        heap = []
        for e in self.out[src]:
            dist[e] = self.Tl[e]
            heap.append((dist[e], e))
        heapq.heapify(heap)
        while heap:
            d, e = heapq.heappop(heap)
            if d > dist[e]:
                continue
            ban = self.forbidden.get(e, ())
            for e2 in self.out[self.headl[e]]:
                if e2 in ban:
                    continue
                nd = d + self.Tl[e2]
                if nd < dist[e2]:
                    dist[e2] = nd
                    parent[e2] = e
                    heapq.heappush(heap, (nd, e2))
        got = (np.array(dist, dtype=np.int64), np.array(parent, dtype=np.int64))
        self._static[src] = got
        return got

    def static_path(self, src: int, dst: int) -> tuple[list[int], int] | None:
        if src == dst:
            return [], 0
        dist, parent = self.static_from(src)
        inc = self.inc[dst]
        if not inc:
            return None
        best = min(inc, key=lambda e: (dist[e], e))
        if dist[best] >= POS_INF:
            return None
        path = [int(best)]
        while parent[path[-1]] >= 0:
            path.append(int(parent[path[-1]]))
        path.reverse()
        return path, int(dist[best])

    def lower_bound_to(self, dst: int) -> np.ndarray:
        """Free-flow travel time from every node to ``dst`` ignoring turn rules (an A* bound)."""
        got = self._lower.get(dst)
        if got is not None:
            return got
        dist = [POS_INF] * self.N
        dist[dst] = 0
        heap = [(0, dst)]
        while heap:
            d, v = heapq.heappop(heap)
            if d > dist[v]:
                continue
            for e in self.inc[v]:
                u = self.taill[e]
                nd = d + self.Tl[e]
                if nd < dist[u]:
                    dist[u] = nd
                    heapq.heappush(heap, (nd, u))
        got = np.array(dist, dtype=np.int64)
        self._lower[dst] = got
        return got

    def static_time(self, src: int, dst: int) -> int:
        sp = self.static_path(src, dst)
        return POS_INF if sp is None else sp[1]

    # ------------------------------------------------------------ forward routing
    def route(self, src: int, t0: int, dst: int) -> Route | None:
        """POSITIVE earliest-arrival route from ``src`` (fresh heading) leaving no earlier than
        ``t0`` to ``dst``: the free-flow shortest path if it is usable at once, else a
        time-dependent A* over edge states with waits at waitable nodes (exact when arriving
        earlier is never worse, e.g. a monotone hazard)."""
        t0 = int(t0)
        if src == dst:
            return Route(t0, t0, ())
        if t0 > self.Hi:
            return None
        sp = self.static_path(src, dst)
        if sp is None:
            return None
        path, tt = sp
        t, steps = t0, []
        for e in path:
            if t > self.Hi or not self.okT[t, e]:
                break
            steps.append((e, t))
            t += self.Tl[e]
        else:
            return Route(t0, t, tuple(steps))
        return self._td_astar(src, t0, dst)

    def _depart(self, v: int, e: int, a: int) -> int | None:
        """Earliest usable departure of ``e`` from node ``v`` for a vehicle there from ``a``."""
        if a <= self.Hi and self.okT[a, e]:
            return a
        if not self.waitable[v]:
            return None
        d = self.next_departure(e, a)
        if d is None or not self.stay_ok(v, a, d):
            return None
        return d

    def _td_astar(self, src: int, t0: int, dst: int) -> Route | None:
        h = self.lower_bound_to(dst)
        if h[src] >= POS_INF:
            return None
        best: dict[int, int] = {}
        parent: dict[int, tuple[int, int]] = {}
        heap: list[tuple[int, int, int]] = []
        for e in self.out[src]:
            d = self._depart(src, e, t0)
            if d is None:
                continue
            a = d + self.Tl[e]
            if a < best.get(e, POS_INF):
                best[e] = a
                parent[e] = (-1, d)
                heapq.heappush(heap, (a + int(h[self.headl[e]]), a, e))
        while heap:
            _, a, e = heapq.heappop(heap)
            if a > best.get(e, POS_INF):
                continue
            v = self.headl[e]
            if v == dst:
                steps = []
                cur = e
                while cur >= 0:
                    prev, d = parent[cur]
                    steps.append((cur, d))
                    cur = prev
                steps.reverse()
                return Route(t0, a, tuple(steps))
            ban = self.forbidden.get(e, ())
            for e2 in self.out[v]:
                if e2 in ban:
                    continue
                d = self._depart(v, e2, a)
                if d is None:
                    continue
                a2 = d + self.Tl[e2]
                if a2 < best.get(e2, POS_INF):
                    best[e2] = a2
                    parent[e2] = (e, d)
                    heapq.heappush(heap, (a2 + int(h[self.headl[e2]]), a2, e2))
        return None

    def route_ok(self, route: Route, src: int) -> bool:
        """Re-check a route against the POSITIVE masks (drives, waits, turns)."""
        v, t, last = src, route.start, None
        for e, d in route.steps:
            if self.taill[e] != v or d < t or (last is not None and e in self.forbidden.get(last, ())):
                return False
            if d > t and not (self.waitable[v] and self.stay_ok(v, t, d)):
                return False
            if not self.depart_ok(e, d):
                return False
            t, v, last = d + self.Tl[e], self.headl[e], e
        return t == route.arrival

    def actions(self, route: Route, src: int) -> list:
        """Schema actions (``Drive`` and ``Wait``) for a route that starts at node ``src``."""
        out: list = []
        v, t = src, route.start
        run: list[str] = []
        run_dep = None
        for e, d in route.steps:
            if d > t:
                if run:
                    out.append(Drive(edges=run, depart_s=float(run_dep)))
                    run, run_dep = [], None
                out.append(Wait(node=self.node_ids[v], duration_s=float(d - t)))
            if not run:
                run_dep = d
            run.append(self.edge_ids[e])
            t, v = d + self.Tl[e], self.headl[e]
        if run:
            out.append(Drive(edges=run, depart_s=float(run_dep)))
        return out


class Sweep:
    """Result of :meth:`Reach.sweep`: ``R[t, c, state]`` (states: edges, then fresh nodes)."""

    def __init__(self, reach: Reach, targets: list[list[ClassTarget]], fresh: list[int], R: np.ndarray):
        self.reach = reach
        self.targets = targets
        self.fresh = {v: reach.E + i for i, v in enumerate(fresh)}
        self.R = R

    def feasible(self, c: int, node: int, t: int) -> bool:
        return 0 <= t <= self.reach.Hi and bool(self.R[t, c, self.fresh[node]])

    def latest_departure(self, c: int, node: int, *, not_before: int = 0, board_s: int = 0,
                         before: int | None = None) -> int | None:
        """Latest t in [``not_before``, ``before``] such that a fresh vehicle at ``node`` at t can still
        deliver (class ``c``) and a ``board_s`` stay [t - board_s, t] at the node is usable."""
        rh = self.reach
        top = rh.Hi if before is None else min(rh.Hi, int(before))
        if top < 0:
            return None
        col = self.R[: top + 1, c, self.fresh[node]]
        for t in np.flatnonzero(col)[::-1].tolist():
            if t < not_before:
                return None
            if t - board_s >= 0 and rh.stay_ok(node, t - board_s, t):
                return int(t)
        return None

    def witness(self, c: int, node: int, t: int) -> tuple[Route, ClassTarget, int]:
        """A POSITIVE trip from a fresh vehicle at ``node`` departing at ``t``: the route to a
        target shelter and the unloading start. Preference: unload, then move (successor nearest
        to a target in free-flow time), then wait 1 s."""
        rh, R = self.reach, self.R
        if not self.feasible(c, node, t):
            raise ValueError("no feasible continuation at this state and time")
        tgs = self.targets[c]
        by_node: dict[int, list[ClassTarget]] = defaultdict(list)
        for tg in tgs:
            by_node[tg.node].append(tg)
        near = np.full(rh.N, POS_INF, dtype=np.int64)
        for v in by_node:
            near = np.minimum(near, rh.lower_bound_to(v))
        v, state, heading, steps, start = node, self.fresh[node], None, [], t
        for _ in range(4 * (rh.Hi + 2)):
            for tg in by_node.get(v, ()):
                if rh.unload_ok(tg, t):
                    arrival = steps[-1][1] + rh.Tl[steps[-1][0]] if steps else start
                    return Route(start, arrival, tuple(steps)), tg, t
            ban = rh.forbidden.get(heading, ()) if heading is not None else ()
            cands = [e for e in rh.out[v] if e not in ban and t + rh.Tl[e] <= rh.Hi and rh.okT[t, e]
                     and R[t + rh.Tl[e], c, e]]
            can_wait = bool(rh.WT[t, v] and R[t + 1, c, state])
            if cands:
                e = min(cands, key=lambda x: (int(near[rh.headl[x]]) + rh.Tl[x], x))
                if not can_wait or near[rh.headl[e]] < near[v]:      # move if it makes progress or must
                    steps.append((e, t))
                    t, v, state, heading = t + rh.Tl[e], rh.headl[e], e, e
                    continue
            if can_wait:
                t += 1
                continue
            raise AssertionError("sweep table inconsistent with its own successors")  # pragma: no cover
        raise AssertionError("witness reconstruction did not terminate")  # pragma: no cover


def _ceil_clip(x, lo: int, hi: int) -> np.ndarray:
    """ceil, clipped to [lo, hi] (infinities included), as int64."""
    return np.clip(np.ceil(np.asarray(x, dtype=float)), lo, hi).astype(np.int64)


def _floor_clip(x, lo: int, hi: int) -> np.ndarray:
    return np.clip(np.floor(np.asarray(x, dtype=float)), lo, hi).astype(np.int64)


def _merge_int(ivs: list[tuple[int, int]]) -> tuple[list[int], list[int]]:
    """Merge closed integer intervals (touching ones too: [a, b] + [b+1, c] = [a, c])."""
    lo, hi = [], []
    for a, b in sorted(ivs):
        if lo and a <= hi[-1] + 1:
            hi[-1] = max(hi[-1], b)
        else:
            lo.append(a)
            hi.append(b)
    return lo, hi


def _merge_float(ivs: list[tuple[float, float]]) -> tuple[list[float], list[float]]:
    """Merge half-open [a, b) intervals."""
    lo, hi = [], []
    for a, b in sorted(ivs):
        if lo and a <= hi[-1]:
            hi[-1] = max(hi[-1], b)
        else:
            lo.append(a)
            hi.append(b)
    return lo, hi


def one_resident(c: int) -> tuple[int, int, int]:
    v = [0, 0, 0]
    v[c] = 1
    return tuple(v)


__all__ = ["CLASSES", "ClassTarget", "LatticeError", "MARGIN_S", "NEG_INF", "POS_INF", "Reach", "Route", "Sweep",
           "one_resident"]
