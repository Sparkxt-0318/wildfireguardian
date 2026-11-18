"""Thermal dose (TDU) of every move in a deadline-field instance, under the closed-form law (DERIVATION.md, C.3).

A move is an edge traversal started at second t, a one-second wait at a node started at t, or a destination dwell
starting at arrival t. Its dose is

    sum over its seconds [tau, tau + 1) of  phi(u(tau)),   phi(q) = q^(4/3) if q > q0 else 0      ((kW/m2)^(4/3) s)

where u(tau) is an UPPER BOUND on the flux during that second (so the dose is an upper bound on the integral of
q^(4/3) above q0, because phi is increasing):

* the receiver occupies a known piece of the road during the second (an edge is traversed at constant speed, as in
  F-3.1's movement model: second k of an edge with D ticks covers the chord from k/D to (k+1)/D);
* for every cell c and member phase [b, x) that the flux model reads (the nearest-front reading of RouteExposure):
  - flaming during the second ([tau, tau + 1) meets [b, x)):  chi*E_A*R / (2*pi*(dist + R*t_r/2)), dist = the
    minimum distance from the road piece to the cell rectangle (0 when it crosses the cell);
  - the road piece crosses the cell and tau < b (front approaching inside the cell): chi*E_A / (2*pi*((b - s) +
    t_r/2)) at the latest moment s = min(tau + 1, b) of the second;
* u = the maximum over cells and over members (a journey must satisfy every member, so summing the per-second
  maximum over members is an upper bound for each member's dose; exact for single-member packets).

Every per-second term is rounded UP to an integer number of quanta (default 1e-4 TDU), so all sums are exact integer
arithmetic and each move's dose is an upper bound on the real-valued dose of the stated model.
Vehicle shielding is not modelled (unshielded person), as in C.3.
"""
from __future__ import annotations

import bisect
import math
from fractions import Fraction as F

import numpy as np

from .closure import HeatRule

Q0_KW_M2 = 1.42           # 24 CFR 51.203(a)(2), 450 Btu/ft2-h (ROUTING_EFFECT.md C.3)
QUANTUM_TDU = 1e-4


def _floor(q: F) -> int:
    return math.floor(q)


def _ceil(q: F) -> int:
    return math.ceil(q)


def seg_rect_dist(px, py, qx, qy, rect):
    """Minimum Euclidean distance between segments P->Q (arrays) and an axis-aligned rectangle (x0, x1, y0, y1);
    0 where the segment meets the closed rectangle."""
    x0, x1, y0, y1 = rect
    px, py, qx, qy = (np.asarray(a, dtype=float) for a in (px, py, qx, qy))
    dx, dy = qx - px, qy - py
    t0 = np.zeros_like(px); t1 = np.ones_like(px); ok = np.ones(px.shape, dtype=bool)
    for p, q in ((-dx, px - x0), (dx, x1 - px), (-dy, py - y0), (dy, y1 - py)):
        par = p == 0
        ok &= ~(par & (q < 0))
        with np.errstate(divide="ignore", invalid="ignore"):
            r = np.where(par, 0.0, q / np.where(par, 1.0, p))
        t0 = np.where(~par & (p < 0), np.maximum(t0, r), t0)
        t1 = np.where(~par & (p > 0), np.minimum(t1, r), t1)
    inter = ok & (t0 <= t1)

    def pr(ax, ay):
        return np.hypot(np.maximum.reduce([x0 - ax, np.zeros_like(ax), ax - x1]),
                        np.maximum.reduce([y0 - ay, np.zeros_like(ay), ay - y1]))

    d = np.minimum(pr(px, py), pr(qx, qy))
    L2 = dx * dx + dy * dy
    for cx, cy in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
        with np.errstate(divide="ignore", invalid="ignore"):
            s = np.where(L2 > 0, ((cx - px) * dx + (cy - py) * dy) / np.where(L2 > 0, L2, 1.0), 0.0)
        s = np.clip(s, 0.0, 1.0)
        d = np.minimum(d, np.hypot(px + s * dx - cx, py + s * dy - cy))
    return np.where(inter, 0.0, d)


def max_rle(terms):
    """terms: [(lo, hi, v)] integer-closed intervals with v > 0 -> RLE of the pointwise max: sorted disjoint
    [(lo, hi, v)], v > 0, adjacent runs with equal v merged."""
    if not terms:
        return []
    cuts = sorted({lo for lo, _, _ in terms} | {hi + 1 for _, hi, _ in terms})
    out = []
    for a, b in zip(cuts, cuts[1:]):
        v = max((t[2] for t in terms if t[0] <= a <= t[1]), default=0)
        if v <= 0:
            continue
        if out and out[-1][1] == a - 1 and out[-1][2] == v:
            out[-1] = (out[-1][0], b - 1, v)
        else:
            out.append((a, b - 1, v))
    return out


def rle_from_dense(arr, offset=0):
    """Dense integer array -> RLE [(lo, hi, v)] of its positive values (index + offset)."""
    a = np.asarray(arr)
    if a.size == 0 or not a.any():
        return []
    chg = np.flatnonzero(np.diff(a)) + 1
    starts = np.concatenate(([0], chg)); ends = np.concatenate((chg - 1, [a.size - 1]))
    return [(int(s) + offset, int(e) + offset, int(a[s])) for s, e in zip(starts, ends) if a[s] > 0]


class RLE:
    """Sorted disjoint positive runs [(lo, hi, cost)]; cost 0 elsewhere."""
    __slots__ = ("runs", "starts")

    def __init__(self, runs):
        self.runs = runs
        self.starts = [r[0] for r in runs]

    def __bool__(self):
        return bool(self.runs)

    def at(self, t: int) -> int:
        i = bisect.bisect_right(self.starts, t) - 1
        if i >= 0 and self.runs[i][1] >= t:
            return self.runs[i][2]
        return 0

    def split(self, lo: int, hi: int):
        """Pieces (a, b, cost) covering [lo, hi] in increasing order, constant cost on each."""
        out = []
        i = max(bisect.bisect_right(self.starts, lo) - 1, 0)
        cur = lo
        runs = self.runs
        while cur <= hi:
            while i < len(runs) and runs[i][1] < cur:
                i += 1
            if i >= len(runs) or runs[i][0] > hi:
                out.append((cur, hi, 0))
                break
            a, b, c = runs[i]
            if a > cur:
                out.append((cur, a - 1, 0))
                cur = a
            e = min(b, hi)
            out.append((cur, e, c))
            cur = e + 1
            i += 1
        return out


EMPTY = RLE([])


class DoseModel:
    """Per (packet model, rule, q0): dose RLEs of every edge start, wait start and dwell, in integer quanta."""

    def __init__(self, pm, rule: HeatRule = HeatRule(), *, q0: float = Q0_KW_M2, quantum: float = QUANTUM_TDU):
        self.pm, self.rule, self.q0, self.quantum = pm, rule, float(q0), float(quantum)
        self.H = pm.H
        self.k_flame = rule.chi * rule.energy_kj_m2 * rule.spread_m_s / (2 * math.pi)   # kW/m
        self.off = rule.spread_m_s * rule.residence_s / 2.0                                  # m
        self.k_time = rule.chi * rule.energy_kj_m2 / (2 * math.pi)                           # kJ/m2 * ... -> kW/m2 * s
        self.tr2 = rule.residence_s / 2.0
        self.reach_m = max(self.k_flame / self.q0 - self.off, 0.0)       # flaming flux > q0 only within this distance
        self.ramp_s = max(self.k_time / self.q0 - self.tr2, 0.0)         # pre-arrival flux > q0 only this long before b
        # phases per cell (all members, Fractions); x beyond H is clipped by the horizon
        big = F(self.H + 1)
        self.ph = {c: [(b, big if x is None else x) for b, x, _s in lst] for c, lst in pm.closed_ph.items()
                   if c in pm.burning}
        self._edge, self._wait, self._dwell = {}, {}, {}
        self.stats = {"edges_near": 0, "edges_positive": 0}

    # ------------------------------------------------------------------ per-second flux upper bound -> quanta
    def _q(self, v: float) -> int:
        """phi(q) in quanta, rounded up (0 if q <= q0)."""
        if v <= self.q0:
            return 0
        return int(math.ceil(v ** (4.0 / 3.0) / self.quantum * (1 + 1e-12)))

    def _cells_near(self, xmin, xmax, ymin, ymax):
        r = F(math.ceil(self.reach_m * 100) + 100, 100)
        grid = self.pm.g.grid
        return [c for c in grid.cells_touching_box(xmin - r, xmax + r, ymin - r, ymax + r) if c in self.ph]

    def _second_terms(self, dists, cells):
        """For pieces (rows of `dists`, one column per cell): per piece, (constant flame terms [(lo, hi, quanta)],
        ramp arrays (tau, quanta)) over absolute seconds tau in [0, H - 1]."""
        H = self.H
        out = []
        for row in dists:
            terms, ramps = [], []
            for ci, c in enumerate(cells):
                d = float(row[ci])
                qf = self._q(self.k_flame / (d + self.off)) if d < self.reach_m + 1e-9 else 0
                for b, x in self.ph[c]:
                    if qf:
                        lo, hi = max(_floor(b), 0), min(_ceil(x) - 1, H - 1)
                        if lo <= hi:
                            terms.append((lo, hi, qf))
                    if d == 0.0:
                        bf = float(b)
                        lo = max(int(math.floor(bf - self.ramp_s)) - 1, 0)
                        hi = min(_ceil(b) - 1, H - 1)
                        if lo <= hi:
                            tau = np.arange(lo, hi + 1)
                            s = np.minimum(tau + 1.0, bf)
                            qv = self.k_time / ((bf - s) + self.tr2)
                            keep = qv > self.q0
                            if keep.any():
                                vals = np.ceil(qv[keep] ** (4.0 / 3.0) / self.quantum * (1 + 1e-12)).astype(np.int64)
                                ramps.append((tau[keep], vals))
            pc = max_rle(terms)
            if ramps:
                tau = np.concatenate([r[0] for r in ramps]); val = np.concatenate([r[1] for r in ramps])
                order = np.argsort(tau, kind="stable"); tau, val = tau[order], val[order]
                u, idx = np.unique(tau, return_index=True)
                val = np.maximum.reduceat(val, idx)
                tau = u
                # pointwise max with the constant flame terms: keep only the excess over pc
                starts = np.array([r[0] for r in pc]) if pc else np.zeros(0, dtype=np.int64)
                pcv = np.zeros(len(tau), dtype=np.int64)
                if pc:
                    i = np.searchsorted(starts, tau, side="right") - 1
                    ends = np.array([r[1] for r in pc]); vals_pc = np.array([r[2] for r in pc])
                    inside = (i >= 0) & (tau <= ends[np.clip(i, 0, None)])
                    pcv = np.where(inside, vals_pc[np.clip(i, 0, None)], 0)
                ex = np.maximum(val - pcv, 0)
                m = ex > 0
                ramp = (tau[m], ex[m])
            else:
                ramp = None
            out.append((pc, ramp))
        return out

    # ------------------------------------------------------------------ edges
    def edge(self, j: int) -> RLE:
        """Dose of traversing edge j starting at t (t in [0, H - D])."""
        if j in self._edge:
            return self._edge[j]
        g, H = self.pm.g, self.H
        p0, p1 = g.xy(g.u[j]), g.xy(g.v[j])
        cells = self._cells_near(min(p0[0], p1[0]), max(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[1], p1[1]))
        D = int(g.ticks[j])
        if not cells or H - D < 0:
            self._edge[j] = EMPTY
            return EMPTY
        self.stats["edges_near"] += 1
        z = np.arange(D + 1) / D
        x0, y0, x1, y1 = float(p0[0]), float(p0[1]), float(p1[0]), float(p1[1])
        X = x0 + z * (x1 - x0); Y = y0 + z * (y1 - y0)
        dist = np.stack([seg_rect_dist(X[:-1], Y[:-1], X[1:], Y[1:], tuple(float(v) for v in g.grid.rect(c)))
                         for c in cells], axis=1)
        T = H - D                                  # valid starts [0, T]
        diff = np.zeros(T + 2, dtype=np.int64)
        for k, (pc, ramp) in enumerate(self._second_terms(dist, cells)):
            for lo, hi, v in pc:
                a, b = max(lo - k, 0), min(hi - k, T)
                if a <= b:
                    diff[a] += v; diff[b + 1] -= v
            if ramp is not None:
                t = ramp[0] - k
                m = (t >= 0) & (t <= T)
                if m.any():
                    np.add.at(diff, t[m], ramp[1][m]); np.add.at(diff, t[m] + 1, -ramp[1][m])
        cost = np.cumsum(diff[:T + 1])
        r = RLE(rle_from_dense(cost))
        if r:
            self.stats["edges_positive"] += 1
        self._edge[j] = r
        return r

    # ------------------------------------------------------------------ points: waits and dwells
    def _point_seconds(self, node):
        """Per-second dose quanta at a node point over [0, H - 1], dense int64 (or None if zero everywhere)."""
        g, H = self.pm.g, self.H
        p = g.xy(node)
        cells = self._cells_near(p[0], p[0], p[1], p[1])
        if not cells:
            return None
        px, py = np.array([float(p[0])]), np.array([float(p[1])])
        dist = np.stack([seg_rect_dist(px, py, px, py, tuple(float(v) for v in g.grid.rect(c))) for c in cells], axis=1)
        (pc, ramp), = self._second_terms(dist, cells)
        if not pc and ramp is None:
            return None
        a = np.zeros(H, dtype=np.int64)
        for lo, hi, v in pc:
            a[lo:hi + 1] = np.maximum(a[lo:hi + 1], v)
        if ramp is not None:
            np.add.at(a, ramp[0], ramp[1])
        return a if a.any() else None

    def wait(self, n: int) -> RLE:
        """Dose of the one-second wait [t, t + 1] at node index n, t in [0, H - 1]."""
        if n not in self._wait:
            a = self._point_seconds(self.pm.node_ids[n])
            self._wait[n] = EMPTY if a is None else RLE(rle_from_dense(a))
        return self._wait[n]

    def dwell(self, n: int, L: int) -> RLE:
        """Dose of the dwell [t, t + L] at node index n for arrival t in [0, H - L]."""
        key = (n, L)
        if key not in self._dwell:
            a = self._point_seconds(self.pm.node_ids[n])
            if a is None or L <= 0:
                self._dwell[key] = EMPTY
            else:
                c = np.concatenate(([0], np.cumsum(a)))
                T = self.H - L
                s = c[L:L + T + 1] - c[0:T + 1] if T >= 0 else np.zeros(0, dtype=np.int64)
                self._dwell[key] = RLE(rle_from_dense(s))
        return self._dwell[key]

    def tdu(self, quanta: int) -> float:
        return quanta * self.quantum

    def quanta(self, tdu: float) -> int:
        """Budget in quanta: the largest integer number of quanta not above `tdu`."""
        return int(math.floor(tdu / self.quantum + 1e-9))
