"""E2 pricing: the clock DP, a dense dynamic programme on E4's contact-free time-expanded network.

For one vehicle (or a batch of vehicles of one type, priced together) and prices on the master's rows, find the
itinerary of largest value: +1 minus the shelter's capacity price per resident unloaded, minus the facility's resident
price and the vehicle's trip-cut prices per resident boarded (:mod:`evacplan.methods.e2_colgen`).

Network: E4's :class:`~evacplan.methods.flow_bound.FlowNetwork` (reused, not copied): its locations (facility and
shelter nodes), its kept moves ``(i, k) -> (j, EA)`` (cell ``k`` = [k delta, (k + 1) delta), ``EA`` the NEGATIVE earliest
arrival leaving at ``k delta``), its vehicle entries and its sites' action sets per class (``Site.usable``).

States: (time unit ``u``, vehicle of the batch, location, load per class); the clock runs in units of ``g`` seconds, ``g``
dividing ``delta``. Transitions: wait one unit (anywhere); board or unload ONE resident of one class at one site of the
location (taking that resident's seconds); take one of E4's moves; enter at the vehicle's entries; end with nobody on
board. The table is filled in blocks shorter than the shortest action, so inside a block only waits chain (a running
maximum along ``u``) and every action lands in a later block; moves are applied at the end of their departure cell.

Two modes (same table, same code):

* ``RELAXED`` (the bound, and columns for the LP): times rounded down (``floor``); an action of ``s`` seconds at unit ``u``
  is allowed iff ``u >= floor(lo / g)`` and ``u + floor(s / g) <= floor(hi / g)`` for an interval ``[lo, hi]`` of the
  site's action set for the class; a vehicle in ANY unit of cell ``k`` may take a move from ``(i, k)`` (E4's semantics:
  departures rounded down to the cell start), arriving at ``floor(EA / g)``. Every checked itinerary maps to a path
  with the same counts (``experiments/E2-column-generation/README.md``, "Why the bound is valid"), so the optimum is an
  upper bound on the value of every checked itinerary at these prices.
* ``RESTRICTED`` (columns for the integer plan): times rounded up (``ceil``); a move from ``(i, k)`` only at the cell
  start ``k delta``, arriving at ``ceil(EA / g)``. Its paths are then realized on the POSITIVE masks
  (:mod:`evacplan.methods.realize`).

Zero-unit actions (a zero-second boarding or unloading, or ``g`` above an action's seconds) are closed per unit; a
value that still grows after ``2 * space + 4`` rounds means a positive cycle (``unbounded``: no bound may be claimed).
Nothing here declares a state (rule 3).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .flow_bound import FlowNetwork

RELAXED = "relaxed"
RESTRICTED = "restricted"
MODES = (RELAXED, RESTRICTED)
NEG = -np.inf


@dataclass(frozen=True)
class ActionSpec:
    """Boarding (``sign`` +1, at a facility site) or unloading (-1, at a shelter site) of ONE resident of class ``cls``."""

    index: int
    loc: int
    site: int                                   # index into FlowNetwork.sites
    cls: int
    sign: int
    secs: float                                 # seconds per resident
    d: int                                      # duration in units
    ranges: tuple[tuple[int, int], ...]         # allowed START units [a, b], inclusive (absolute units)


@dataclass(frozen=True)
class Event:
    kind: str                                   # "entry" | "act" | "move"
    loc: int
    unit: int
    action: int = -1                            # ActionSpec.index for "act"
    src_loc: int = -1                           # for "move"


@dataclass
class PricedPath:
    """A path read off the table: the vehicle's events in order and its DP value at the prices used."""

    vehicle: str
    value: float
    end_loc: int
    end_unit: int
    events: list[Event]


@dataclass
class DPResult:
    values: dict[str, float]                    # vehicle -> max(0, best value): the DP optimum per vehicle
    unbounded: bool
    paths: list[PricedPath] = field(default_factory=list)
    seconds: float = 0.0


def clock_units(net: FlowNetwork, vehicles, *, max_cells: float) -> tuple[int, int]:
    """(g, batch size) for one vehicle type (README, clock unit rule): the smallest divisor ``g`` of ``delta`` that is
    at most the shortest positive per-resident action time of a class the type carries, with as many vehicles of the
    type in one batch as fit in ``max_cells`` table cells (at the largest admissible ``g`` if needed)."""
    cap = vehicles[0].capacity()
    cls = [c for c in net.classes if cap[c] > 0]
    secs = [s.secs[c] for s in net.sites for c in cls if s.usable[c] and s.limit[c] > 0 and s.secs[c] > 0]
    shortest = min(secs) if secs else net.delta
    divisors = [d for d in range(1, net.delta + 1) if net.delta % d == 0 and d <= max(1.0, shortest)] or [1]
    nl = int(np.prod([cap[c] + 1 for c in cls])) if cls else 1
    H = net.H
    span = max(min(H, v.start_s + (v.shift_limit_s if v.shift_limit_s is not None else H)) for v in vehicles) - \
        min(v.start_s for v in vehicles)
    for nb in range(len(vehicles), 0, -1):
        for g in divisors:
            if nb * (span / g + 2) * net.L * nl <= max_cells:
                return g, nb
    return divisors[-1], 1


class BatchDP:
    """The clock DP of a batch of vehicles of one type (same space per class), for one mode."""

    def __init__(self, net: FlowNetwork, vehicles, *, g: int, mode: str):
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        if net.delta % g:
            raise ValueError("the clock unit must divide the network's step")
        caps = {v.capacity() for v in vehicles}
        if len(caps) != 1:
            raise ValueError("a batch holds vehicles of one type (same space per class)")
        self.net, self.g, self.mode = net, int(g), mode
        self.vehicles = list(vehicles)
        self.vid = [v.id for v in vehicles]
        self.nv = len(vehicles)
        cap = vehicles[0].capacity()
        self.cap = cap
        self.cls = [c for c in net.classes if cap[c] > 0]
        self.shape = tuple(cap[c] + 1 if c in self.cls else 1 for c in range(3))
        self.NL = int(np.prod(self.shape))
        self.stride = (self.shape[1] * self.shape[2], self.shape[2], 1)
        self.L = net.L
        self.m = net.delta // self.g                                   # units per cell
        relaxed = mode == RELAXED
        fl = (lambda t: int(math.floor(t / self.g + 1e-9))) if relaxed else (lambda t: int(math.ceil(t / self.g - 1e-9)))
        self._time_unit = fl
        H = net.H
        self.us, self.ue = [], []
        for v in vehicles:
            end = H if v.shift_limit_s is None else min(H, float(v.start_s) + float(v.shift_limit_s))
            self.us.append(fl(float(v.start_s)))
            self.ue.append(int(math.floor(end / self.g + 1e-9)))
        self.U0 = min(self.us)
        self.U1 = max(self.ue)
        self.T = max(0, self.U1 - self.U0 + 1)
        # entries
        self.entries: list[tuple[int, int, int]] = []                  # (vehicle in batch, loc, unit)
        for b, v in enumerate(vehicles):
            for (j, _kk, a) in net.src.get(v.id, []):
                ua = fl(float(a))
                if self.us[b] <= ua <= self.ue[b]:
                    self.entries.append((b, int(j), ua))
        self.entry_set = {(b, j, u) for b, j, u in self.entries}
        # actions
        self.actions: list[ActionSpec] = []
        for si, site in enumerate(net.sites):
            for c in self.cls:
                if site.limit[c] <= 0 or not site.usable[c]:
                    continue
                secs = float(site.secs[c])
                sign = 1 if site.kind == "facility" else -1
                d = int(math.floor(secs / self.g + 1e-9)) if relaxed else int(math.ceil(secs / self.g - 1e-9))
                rngs = []
                for lo, hi in site.usable[c]:
                    if relaxed:
                        a, top = int(math.floor(lo / self.g + 1e-9)), int(math.floor(hi / self.g + 1e-9))
                    else:
                        a, top = int(math.ceil(lo / self.g - 1e-9)), int(math.floor((hi - 2e-6) / self.g))
                    b_ = top - d
                    a, b_ = max(a, self.U0), min(b_, self.U1 - d)
                    if a <= b_:
                        rngs.append((a, b_))
                if rngs:
                    self.actions.append(ActionSpec(len(self.actions), site.loc, si, c, sign, secs, d, tuple(rngs)))
        self.zero = [a for a in self.actions if a.d == 0]
        pos = [a.d for a in self.actions if a.d > 0]
        self.D = 1 if self.zero else max(1, min(pos + [self.m]))
        self.at_loc: dict[int, list[ActionSpec]] = {}
        for a in self.actions:
            self.at_loc.setdefault(a.loc, []).append(a)
        self._slices = {a.index: self._load_slices(a) for a in self.actions}
        # moves, grouped by departure cell. RELAXED: from the cell's last unit (the max over the cell, by the waits),
        # arriving at floor(EA / g). RESTRICTED: from every unit u of the cell, arriving at u + ceil((EA - k delta) / g)
        # (the cell's travel time; a heuristic for columns, judged by the realizer)
        mv = net.mv
        tk, ti, hj, ea = mv["tk"], mv["ti"], mv["hi"], mv["entry"]
        self.moves_by_cell: dict[int, tuple] = {}
        self.arrivals: dict[tuple[int, int], list[tuple[int, int]]] = {}     # RELAXED: (head, unit) -> [(src unit, tail)]
        self.into: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}  # RESTRICTED: head -> (tail, cell, shift)
        if self.T:
            if relaxed:
                src_u = np.minimum((tk + 1) * self.m - 1, self.U1)
                arr_u = np.floor(ea / self.g + 1e-9).astype(np.int64)
                ok = (src_u >= self.U0) & (arr_u <= self.U1) & (arr_u > src_u)
            else:
                shift = np.ceil((ea - tk * net.delta) / self.g - 1e-9).astype(np.int64)
                first = np.maximum(tk * self.m, self.U0)
                ok = (first <= np.minimum((tk + 1) * self.m - 1, self.U1)) & (first + shift <= self.U1) & (shift >= 1)
            sel = np.flatnonzero(ok)
            if sel.size:
                cells = tk[sel]
                order = np.argsort(cells, kind="stable")
                sel, cells = sel[order], cells[order]
                for grp in np.split(sel, np.flatnonzero(np.diff(cells)) + 1):
                    k = int(tk[grp[0]])
                    if relaxed:
                        self.moves_by_cell[k] = ((src_u[grp] - self.U0).astype(np.intp), ti[grp].astype(np.intp),
                                                 (arr_u[grp] - self.U0).astype(np.intp), hj[grp].astype(np.intp))
                    else:
                        self.moves_by_cell[k] = [(int(ti[i]), int(hj[i]), int(shift[i])) for i in grp]
                if relaxed:
                    for i in sel.tolist():
                        self.arrivals.setdefault((int(hj[i]), int(arr_u[i])), []).append((int(src_u[i]), int(ti[i])))
                else:
                    for j in np.unique(hj[sel]).tolist():
                        q = sel[hj[sel] == j]
                        self.into[int(j)] = (ti[q].astype(np.int64), tk[q].astype(np.int64), shift[q].astype(np.int64))
        self.V: np.ndarray | None = None
        self.unbounded = False

    # ------------------------------------------------------------------------------------------ helpers
    @property
    def cells(self) -> int:
        return self.T * self.nv * self.L * self.NL

    def _load_slices(self, a: ActionSpec):
        n = self.shape[a.cls]
        src = [slice(None)] * 3
        dst = [slice(None)] * 3
        if a.sign > 0:
            src[a.cls], dst[a.cls] = slice(0, n - 1), slice(1, n)
        else:
            src[a.cls], dst[a.cls] = slice(1, n), slice(0, n - 1)
        return tuple(src), tuple(dst)

    def load_vector(self, l: int) -> tuple[int, int, int]:
        return (l // self.stride[0], (l // self.stride[1]) % self.shape[1], l % self.shape[2])

    # ----------------------------------------------------------------------------------------------- run
    def run(self, profits: np.ndarray, buffer: np.ndarray | None = None) -> np.ndarray:
        """Fill the table for ``profits[action index, vehicle in batch]``; returns the DP optimum per vehicle (>= 0:
        the empty itinerary). ``buffer``: optional float64 memory of at least :attr:`cells` entries (reused)."""
        nv, L, NL, T = self.nv, self.L, self.NL, self.T
        self.unbounded = False
        if T <= 0:
            self.V = None
            return np.zeros(nv)
        n = T * nv * L * NL
        if buffer is not None and buffer.size >= n:
            V = buffer[:n].reshape(T, nv, L, NL)
        else:
            V = np.empty((T, nv, L, NL))
        V.fill(NEG)
        self.V = V
        Vr = V.reshape((T, nv, L) + self.shape)
        for b, j, u in self.entries:
            x = u - self.U0
            if V[x, b, j, 0] < 0.0:
                V[x, b, j, 0] = 0.0
        prof = np.asarray(profits, dtype=float).reshape(len(self.actions), nv) if self.actions else np.zeros((0, nv))
        pb = [prof[a.index].reshape(1, nv, 1, 1, 1) for a in self.actions]
        late = [(b, self.ue[b]) for b in range(nv) if self.ue[b] < self.U1]
        max_rounds = 2 * sum(self.cap) + 4
        U0, U1, m, D = self.U0, self.U1, self.m, self.D
        for k in range(U0 // m, U1 // m + 1):
            c0, c1 = max(k * m, U0), min((k + 1) * m - 1, U1)
            b0 = c0
            while b0 <= c1:
                b1 = min(b0 + D, c1 + 1)
                x0, x1 = b0 - U0, b1 - U0
                if x0 > 0:
                    np.maximum(V[x0], V[x0 - 1], out=V[x0])
                if x1 - x0 > 1:
                    np.maximum.accumulate(V[x0:x1], axis=0, out=V[x0:x1])
                for b, ue in late:                                   # nothing after a vehicle's end
                    if ue < b1 - 1:
                        V[max(x0, ue + 1 - U0):x1, b] = NEG
                if self.zero:
                    self._close_zero(Vr, pb, b0, max_rounds)
                for a in self.actions:
                    if a.d == 0:
                        continue
                    ssl, dsl = self._slices[a.index]
                    for ra, rb in a.ranges:
                        s0, s1 = max(b0, ra), min(b1 - 1, rb)
                        if s0 > s1:
                            continue
                        y0, y1 = s0 - U0, s1 - U0 + 1
                        src = Vr[(slice(y0, y1), slice(None), a.loc) + ssl]
                        dst = Vr[(slice(y0 + a.d, y1 + a.d), slice(None), a.loc) + dsl]
                        np.maximum(dst, src + pb[a.index], out=dst)
                b0 = b1
            grp = self.moves_by_cell.get(k)
            if grp is not None:
                if self.mode == RELAXED:
                    sx, ti, ax, hj = grp
                    np.maximum.at(V, (ax, slice(None), hj, slice(None)), V[sx, :, ti, :])
                else:
                    x0 = c0 - U0
                    for i, j, sh in grp:
                        n = min(c1 - c0 + 1, U1 - (c0 + sh) + 1)
                        dst = V[x0 + sh:x0 + sh + n, :, j, :]
                        np.maximum(dst, V[x0:x0 + n, :, i, :], out=dst)
        out = np.zeros(nv)
        for b in range(nv):
            x = self.ue[b] - U0
            if x >= 0:
                out[b] = max(0.0, float(np.max(V[x, b, :, 0])))
        return out

    def _close_zero(self, Vr, pb, u: int, max_rounds: int) -> None:
        y = u - self.U0
        for _ in range(max_rounds):
            changed = False
            for a in self.zero:
                if not any(ra <= u <= rb for ra, rb in a.ranges):
                    continue
                ssl, dsl = self._slices[a.index]
                src = Vr[(slice(y, y + 1), slice(None), a.loc) + ssl]
                dst = Vr[(slice(y, y + 1), slice(None), a.loc) + dsl]
                new = np.maximum(dst, src + pb[a.index])
                if np.any(new > dst):
                    dst[...] = new
                    changed = True
            if not changed:
                return
        self.unbounded = True

    # --------------------------------------------------------------------------------------- extraction
    def paths(self, profits: np.ndarray, *, per_vehicle: int, min_value: float,
              only: set[str] | None = None) -> list[PricedPath]:
        """Up to ``per_vehicle`` paths per vehicle (``only``: these vehicles): the best empty end state at each of the
        best locations (value above ``min_value``), read off the last filled table by backtracking."""
        out: list[PricedPath] = []
        if self.V is None:
            return out
        prof = np.asarray(profits, dtype=float).reshape(len(self.actions), self.nv) if self.actions else None
        for b in range(self.nv):
            if only is not None and self.vid[b] not in only:
                continue
            x = self.ue[b] - self.U0
            if x < 0:
                continue
            term = self.V[x, b, :, 0]
            order = sorted(range(self.L), key=lambda i: (-term[i], i))
            got = 0
            for i in order:
                if got >= per_vehicle or not term[i] > min_value:
                    break
                path = self._backtrack(b, self.ue[b], i, float(term[i]), prof)
                if path is not None:
                    out.append(path)
                    got += 1
        return out

    def _backtrack(self, b: int, u: int, i: int, val: float, prof) -> PricedPath | None:
        V, U0 = self.V, self.U0
        end_loc, end_unit, end_val = i, u, val
        l = 0
        events: list[Event] = []
        seen: set[tuple[int, int, int]] = set()
        us = self.us[b]
        for _ in range(4 * (self.T + 10) * max(1, self.NL)):
            tol = 1e-9 * max(1.0, abs(val))
            col = V[us - U0:u - U0 + 1, b, i, l]
            below = np.flatnonzero(col < val - tol)
            u0 = us + (int(below[-1]) + 1 if below.size else 0)
            if l == 0 and abs(val) <= tol and (b, i, u0) in self.entry_set:
                events.append(Event("entry", i, u0))
                events.reverse()
                return PricedPath(self.vid[b], end_val, end_loc, end_unit, events)
            best = None
            for a in self.at_loc.get(i, ()):
                lv = list(self.load_vector(l))
                lv[a.cls] -= a.sign
                if not 0 <= lv[a.cls] < self.shape[a.cls]:
                    continue
                ls = lv[0] * self.stride[0] + lv[1] * self.stride[1] + lv[2]
                su = u0 - a.d
                if su < us or not any(ra <= su <= rb for ra, rb in a.ranges) or (su, i, ls) in seen:
                    continue
                cand = V[su - U0, b, i, ls] + prof[a.index, b]
                err = abs(cand - val)
                if err <= tol and (best is None or err < best[0]):
                    best = (err, Event("act", i, u0, action=a.index), su, i, ls)
            if self.mode == RELAXED:
                srcs = self.arrivals.get((i, u0), ())
            else:
                srcs = []
                got = self.into.get(i)
                if got is not None:
                    tl, kc, sh = got
                    su_all = u0 - sh
                    hit = np.flatnonzero((su_all // self.m == kc) & (su_all >= us))
                    srcs = [(int(su_all[h]), int(tl[h])) for h in hit]
            for su, j in srcs:
                if su < us or (su, j, l) in seen:
                    continue
                cand = V[su - U0, b, j, l]
                err = abs(cand - val)
                if err <= tol and (best is None or err < best[0]):
                    best = (err, Event("move", i, u0, src_loc=j), su, j, l)
            if best is None:
                return None                                          # pragma: no cover - table inconsistent
            _, ev, u, i, l = best
            seen.add((u, i, l))
            events.append(ev)
            val = float(V[u - U0, b, i, l])
        return None                                                  # pragma: no cover


__all__ = ["ActionSpec", "BatchDP", "DPResult", "Event", "MODES", "PricedPath", "RELAXED", "RESTRICTED",
           "clock_units"]
