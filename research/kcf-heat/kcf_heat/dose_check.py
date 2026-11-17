"""Independent bounds on a route's dose, for checking the field's witnesses and the dose model.

Re-derives the per-second flux bound of kcf_heat/dose.py from its text with plain floats and dense sampling, and
shares none of its interval, RLE or difference-array code. For each second of the journey the receiver's road piece
is sampled at n + 1 points:

* lower: distance = the smallest sampled distance to each cell (>= the true minimum), so the flux is <= the model's;
* upper: that distance minus half the sample spacing, floored at 0 (<= the true minimum), so the flux is >= the
  model's; a cell counts as crossed (pre-arrival term) if any sample is inside it (lower) or if the slack reaches it
  (upper).

So  lower <= model dose <= upper  for every route; the field's integer dose may exceed the model's real dose by its
round-up (at most one quantum per second).
"""
from __future__ import annotations

import math

import numpy as np


class DoseBounds:
    def __init__(self, dm, n_samples: int = 16):
        self.dm, self.n = dm, n_samples
        pm = dm.pm
        grid = pm.g.grid
        cells = sorted(dm.ph)
        self.rects = np.array([[float(v) for v in grid.rect(c)] for c in cells]) if cells else np.zeros((0, 4))
        self.phases = [[(float(b), float(x)) for b, x in dm.ph[c]] for c in cells]
        self._sub = None

    def _restrict(self, xs, ys):
        """Keep only cells within reach of the bounding box of the points (xs, ys): a superset of every cell that
        can contribute at those points (pure speed; the per-second evaluation is unchanged)."""
        m = self.dm.reach_m + 2.0
        x0, x1, y0, y1 = min(xs) - m, max(xs) + m, min(ys) - m, max(ys) + m
        R = self.rects
        keep = np.flatnonzero((R[:, 1] >= x0) & (R[:, 0] <= x1) & (R[:, 3] >= y0) & (R[:, 2] <= y1)) if len(R) else []
        self._sub = (R[keep], [self.phases[i] for i in keep])

    def _second(self, X, Y, tau):
        """(lower, upper) per-second phi for a road piece sampled at points (X, Y) during [tau, tau + 1)."""
        dm = self.dm
        R, phases = self._sub if self._sub is not None else (self.rects, self.phases)
        if len(R) == 0:
            return 0.0, 0.0
        dx = np.maximum.reduce([R[:, 0:1] - X, np.zeros((len(R), len(X))), X - R[:, 1:2]])
        dy = np.maximum.reduce([R[:, 2:3] - Y, np.zeros((len(R), len(X))), Y - R[:, 3:4]])
        d = np.hypot(dx, dy).min(axis=1)
        step = math.hypot(X[-1] - X[0], Y[-1] - Y[0]) / max(len(X) - 1, 1)
        d_lb = np.maximum(d - step / 2.0, 0.0)
        lo = hi = 0.0
        for ci in np.flatnonzero(d_lb < dm.reach_m + 1.0):
            for b, x in phases[ci]:
                if tau + 1 > b and tau < x:
                    lo = max(lo, dm.k_flame / (d[ci] + dm.off))
                    hi = max(hi, dm.k_flame / (d_lb[ci] + dm.off))
                if tau < b:
                    q = dm.k_time / ((b - min(tau + 1.0, b)) + dm.tr2)
                    if d[ci] == 0.0:
                        lo = max(lo, q)
                    if d_lb[ci] == 0.0:
                        hi = max(hi, q)
        phi = lambda q: q ** (4.0 / 3.0) if q > dm.q0 else 0.0  # noqa: E731
        return phi(lo), phi(hi)

    def edge(self, j: int, t: int):
        pm = self.dm.pm
        g = pm.g
        p0, p1 = g.xy(g.u[j]), g.xy(g.v[j])
        D = int(g.ticks[j])
        self._restrict([float(p0[0]), float(p1[0])], [float(p0[1]), float(p1[1])])
        lo = hi = 0.0
        for k in range(D):
            z = (k + np.linspace(0.0, 1.0, self.n + 1)) / D
            X = float(p0[0]) + z * (float(p1[0]) - float(p0[0]))
            Y = float(p0[1]) + z * (float(p1[1]) - float(p0[1]))
            a, b = self._second(X, Y, t + k)
            lo += a; hi += b
        self._sub = None
        return lo, hi

    def point(self, node, t: int, L: int):
        p = self.dm.pm.g.xy(node)
        X, Y = np.array([float(p[0])]), np.array([float(p[1])])
        self._restrict([X[0]], [Y[0]])
        lo = hi = 0.0
        for k in range(L):
            a, b = self._second(X, Y, t + k)
            lo += a; hi += b
        self._sub = None
        return lo, hi

    def route(self, legs, dest_node=None, arrival=None, dwell=0):
        """legs: ('EDGE', j, a, b) / ('WAIT', node_index, a, b) -> (lower, upper, seconds) of the whole journey."""
        pm = self.dm.pm
        lo = hi = 0.0
        secs = 0
        for kind, x, a, b in legs:
            if kind == "EDGE":
                l, h = self.edge(x, a)
            else:
                l, h = self.point(pm.node_ids[x], a, b - a)
            lo += l; hi += h; secs += b - a
        if dest_node is not None and dwell:
            l, h = self.point(dest_node, arrival, int(dwell))
            lo += l; hi += h; secs += int(dwell)
        return lo, hi, secs
