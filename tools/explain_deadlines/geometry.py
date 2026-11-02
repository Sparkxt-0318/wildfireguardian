"""Exact road/grid geometry on the routing graph's 375 m lattice (rational arithmetic only).

Two geometric readings of a straight road chord p0 -> p1 are needed, because a recorded ``checked_route`` had
to pass both of them (see README.md, "Contact rule"):

* closed footprint (runtime whole-road contact check, kit ``routing_candidate/baseline/contact_first.py``):
  the closed segment is clipped against the CLOSED rectangle of every burning cell
  (``clip_closed_rectangle``), giving the line-parameter interval [u0, u1] spent inside or on the boundary
  of that cell;
* cell pieces (router search, kit ``routing-package/routing/core.py::edge_occupancies``): the chord is cut at
  every interior grid line; each open piece belongs to the cell of its midpoint and every cut point
  (including both ends) is a point occupancy of the cell that contains it (floor rule).

Everything is exact (``fractions.Fraction``); binary64 inputs convert exactly.
"""
from __future__ import annotations

import math
from fractions import Fraction as F
from typing import Iterable


def exact(v) -> F:
    """Exact rational of an int, a finite binary64 float, a Fraction or a decimal/rational string."""
    if isinstance(v, bool) or v is None:
        raise ValueError("non-numeric value %r" % (v,))
    if isinstance(v, F):
        return v
    if isinstance(v, int):
        return F(v)
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ValueError("non-finite value %r" % (v,))
        return F(v)
    if isinstance(v, str):
        return F(v)
    # numpy scalars
    try:
        import numpy as np  # noqa: WPS433 (optional)
        if isinstance(v, np.integer):
            return F(int(v))
        if isinstance(v, np.floating):
            return exact(float(v))
    except ImportError:  # pragma: no cover
        pass
    raise ValueError("unsupported numeric type %r" % (type(v),))


def floor_q(x: F) -> int:
    return x.numerator // x.denominator


def ceil_q(x: F) -> int:
    return -((-x.numerator) // x.denominator)


class Grid:
    """Router cell lattice: cell index = row * width + col with row counted from y0 upwards (south-up)."""

    def __init__(self, x0, y0, resolution, width: int, height: int):
        self.x0, self.y0, self.res = exact(x0), exact(y0), exact(resolution)
        self.W, self.H = int(width), int(height)
        if self.res <= 0 or self.W < 1 or self.H < 1:
            raise ValueError("invalid grid")

    @classmethod
    def from_graph(cls, graph_grid: dict) -> "Grid":
        return cls(graph_grid["x0"], graph_grid["y0"], graph_grid["resolution"], graph_grid["width"], graph_grid["height"])

    def cell_of(self, x: F, y: F) -> int:
        """Router ``node_cell`` (floor rule). Raises ValueError outside the grid."""
        c = floor_q((x - self.x0) / self.res)
        r = floor_q((y - self.y0) / self.res)
        if not (0 <= c < self.W and 0 <= r < self.H):
            raise ValueError("coordinate outside grid")
        return r * self.W + c

    def rect(self, cell: int) -> tuple:
        """Closed rectangle (xmin, xmax, ymin, ymax) of a router cell."""
        r, c = divmod(int(cell), self.W)
        return (self.x0 + c * self.res, self.x0 + (c + 1) * self.res,
                self.y0 + r * self.res, self.y0 + (r + 1) * self.res)

    def centre(self, cell: int) -> tuple:
        r, c = divmod(int(cell), self.W)
        return (self.x0 + (c + F(1, 2)) * self.res, self.y0 + (r + F(1, 2)) * self.res)

    def cells_touching_box(self, xmin: F, xmax: F, ymin: F, ymax: F) -> Iterable[int]:
        """Every in-grid cell whose CLOSED rectangle intersects the closed box."""
        c0 = max(0, ceil_q((xmin - self.x0) / self.res) - 1)
        c1 = min(self.W - 1, floor_q((xmax - self.x0) / self.res))
        r0 = max(0, ceil_q((ymin - self.y0) / self.res) - 1)
        r1 = min(self.H - 1, floor_q((ymax - self.y0) / self.res))
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                yield r * self.W + c


def clip_closed(p0: tuple, p1: tuple, rect: tuple):
    """Line-parameter interval [lo, hi] of the closed segment p0->p1 inside the closed axis-aligned rectangle,
    or None. Same algorithm and comparisons as ``contact_first.clip_closed_rectangle`` (Liang-Barsky, exact)."""
    low, high = F(0), F(1)
    for x, y, left, right in ((p0[0], p1[0], rect[0], rect[1]), (p0[1], p1[1], rect[2], rect[3])):
        delta = y - x
        if delta == 0:
            if x < left or x > right:
                return None
        else:
            a, b = (left - x) / delta, (right - x) / delta
            low = max(low, min(a, b))
            high = min(high, max(a, b))
            if low > high:
                return None
    return low, high


def chord_cuts(grid: Grid, p0: tuple, p1: tuple, f: F = F(0), q: F = F(1)) -> list:
    """Sorted cut parameters in [f, q]: f, q and every crossing of an interior grid line (router rule:
    lines 1 .. width-1 and 1 .. height-1 only)."""
    cuts = {f, q}
    for a, b, base, count in ((p0[0], p1[0], grid.x0, grid.W), (p0[1], p1[1], grid.y0, grid.H)):
        if a == b:
            continue
        lo, hi = min(a, b), max(a, b)
        kmin = max(1, floor_q((lo - base) / grid.res))
        kmax = min(count - 1, ceil_q((hi - base) / grid.res))
        for k in range(kmin, kmax + 1):
            z = (base + k * grid.res - a) / (b - a)
            if f < z < q:
                cuts.add(z)
    return sorted(cuts)


def chord_pieces(grid: Grid, p0: tuple, p1: tuple, f: F = F(0), q: F = F(1)):
    """Router occupancy geometry of a chord: (pieces, points) with pieces = [(cell, za, zb)] for every open piece
    (cell of its midpoint) and points = [(cell, z)] for every cut point. Parameters are chord fractions."""
    cuts = chord_cuts(grid, p0, p1, f, q)

    def pt(z):
        return (p0[0] + z * (p1[0] - p0[0]), p0[1] + z * (p1[1] - p0[1]))

    pieces = [(grid.cell_of(*pt((a + b) / 2)), a, b) for a, b in zip(cuts, cuts[1:])]
    points = [(grid.cell_of(*pt(z)), z) for z in cuts]
    return pieces, points
