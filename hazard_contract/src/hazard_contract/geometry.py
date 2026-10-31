"""Grid geometry for the raster reference implementation (numpy only).

Conventions
-----------
* Grids are north-up: affine ``(a, b, c, d, e, f)`` in rasterio order with ``b == d == 0``,
  so a pixel corner (col, row) maps to ``x = a*col + c``, ``y = e*row + f``.
* Cells are CLOSED squares. A point on a shared edge touches both cells and a corner touches
  four. This is the conservative choice: more cells are checked, never fewer.
* Geometries are polylines ``[n, 2]`` in the grid CRS. ``n == 1`` (or all vertices equal) is a
  stationary position.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

PIXEL_EPS = 1e-9  # points within this many pixels of a grid line touch the cells on both sides


@dataclass(frozen=True)
class Grid:
    transform: tuple[float, float, float, float, float, float]
    height: int
    width: int

    def __post_init__(self) -> None:
        a, b, _c, d, e, _f = (float(v) for v in self.transform)
        if b != 0.0 or d != 0.0:
            raise ValueError("north-up grids only (b == d == 0)")
        if a == 0.0 or e == 0.0:
            raise ValueError("degenerate transform")
        if self.height <= 0 or self.width <= 0:
            raise ValueError("empty grid")

    @property
    def cell_area_m2(self) -> float:
        a, _b, _c, _d, e, _f = self.transform
        return abs(a * e)

    @property
    def cell_size(self) -> tuple[float, float]:
        a, _b, _c, _d, e, _f = self.transform
        return abs(a), abs(e)

    def to_pixel(self, xy: np.ndarray) -> np.ndarray:
        """CRS coordinates ``[..., 2]`` -> fractional pixel coordinates ``[..., 2]`` as (col, row)."""
        a, _b, c, _d, e, f = self.transform
        xy = np.asarray(xy, dtype=float)
        out = np.empty_like(xy)
        out[..., 0] = (xy[..., 0] - c) / a
        out[..., 1] = (xy[..., 1] - f) / e
        return out

    def cell_rects(self, rows: np.ndarray, cols: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Closed cell rectangles (x0, x1, y0, y1) with x0 < x1 and y0 < y1."""
        a, _b, c, _d, e, f = self.transform
        rows = np.asarray(rows, dtype=float)
        cols = np.asarray(cols, dtype=float)
        xa, xb = a * cols + c, a * (cols + 1) + c
        ya, yb = e * rows + f, e * (rows + 1) + f
        return np.minimum(xa, xb), np.maximum(xa, xb), np.minimum(ya, yb), np.maximum(ya, yb)

    def cell_centers(self, rows: np.ndarray, cols: np.ndarray) -> np.ndarray:
        a, _b, c, _d, e, f = self.transform
        rows = np.asarray(rows, dtype=float)
        cols = np.asarray(cols, dtype=float)
        return np.stack([a * (cols + 0.5) + c, e * (rows + 0.5) + f], axis=-1)

    def index_box(self, xmin: float, xmax: float, ymin: float, ymax: float) -> tuple[int, int, int, int]:
        """Row/col half-open ranges ``(r0, r1, c0, c1)`` of every in-grid cell whose closed
        square meets the CRS box. Cells outside the returned ranges lie entirely outside it."""
        corners = self.to_pixel(np.array([[xmin, ymin], [xmax, ymax]], dtype=float))
        cmin, cmax = np.sort(corners[:, 0])
        rmin, rmax = np.sort(corners[:, 1])
        c0 = int(np.floor(cmin - 1 - PIXEL_EPS)) + 1
        c1 = int(np.floor(cmax + PIXEL_EPS)) + 1
        r0 = int(np.floor(rmin - 1 - PIXEL_EPS)) + 1
        r1 = int(np.floor(rmax + PIXEL_EPS)) + 1
        c0, r0 = max(c0, 0), max(r0, 0)
        c1, r1 = min(c1, self.width), min(r1, self.height)
        return r0, max(r1, r0), c0, max(c1, c0)


def as_polyline(geom_xy) -> np.ndarray:
    g = np.asarray(geom_xy, dtype=float)
    if g.ndim == 1:
        g = g.reshape(1, -1)
    if g.ndim != 2 or g.shape[1] != 2 or g.shape[0] < 1:
        raise ValueError("geometry must be an [n, 2] polyline (n >= 1)")
    if not np.all(np.isfinite(g)):
        raise ValueError("geometry coordinates must be finite")
    return g


def is_stationary(g: np.ndarray) -> bool:
    return bool(np.all(g == g[0]))


def _closed_cells_of_points(pts: np.ndarray) -> np.ndarray:
    """All (row, col) cells whose closed square contains each pixel-space point (col, row)."""
    x, y = pts[:, 0], pts[:, 1]
    j_lo = np.ceil(x - 1 - PIXEL_EPS).astype(np.int64)
    j_hi = np.floor(x + PIXEL_EPS).astype(np.int64)
    i_lo = np.ceil(y - 1 - PIXEL_EPS).astype(np.int64)
    i_hi = np.floor(y + PIXEL_EPS).astype(np.int64)
    cells = np.concatenate([
        np.stack([i_lo, j_lo], 1), np.stack([i_lo, j_hi], 1),
        np.stack([i_hi, j_lo], 1), np.stack([i_hi, j_hi], 1),
    ])
    return np.unique(cells, axis=0)


def _segment_probe_points(p0: np.ndarray, p1: np.ndarray) -> np.ndarray:
    """Points along a pixel-space segment: every grid-line crossing plus the midpoint of every
    piece between crossings. Their closed-cell sets cover exactly the cells the segment meets."""
    d = p1 - p0
    ts = [np.array([0.0, 1.0])]
    for axis in (0, 1):
        if d[axis] != 0.0:
            lo, hi = sorted((p0[axis], p1[axis]))
            ks = np.arange(np.ceil(lo), np.floor(hi) + 1.0)
            if ks.size:
                ts.append((ks - p0[axis]) / d[axis])
    t = np.unique(np.clip(np.concatenate(ts), 0.0, 1.0))
    t = np.concatenate([t, 0.5 * (t[:-1] + t[1:])])
    return p0[None, :] + t[:, None] * d[None, :]


def polyline_cells(grid: Grid, geom_xy) -> tuple[np.ndarray, np.ndarray, bool]:
    """Closed-cell supercover of a polyline.

    Returns ``(rows, cols, touches_outside)``: unique in-grid cells the geometry meets, and
    whether any part of it touches a cell outside the grid (including the grid's outer edge).
    """
    g = as_polyline(geom_xy)
    px = grid.to_pixel(g)
    if is_stationary(g):
        probes = px[:1]
    else:
        probes = np.concatenate([_segment_probe_points(px[i], px[i + 1]) for i in range(len(px) - 1)])
    cells = _closed_cells_of_points(probes)
    rows, cols = cells[:, 0], cells[:, 1]
    inside = (rows >= 0) & (rows < grid.height) & (cols >= 0) & (cols < grid.width)
    return rows[inside], cols[inside], bool((~inside).any())


def point_rect_dist(px: np.ndarray, py: np.ndarray, x0, x1, y0, y1) -> np.ndarray:
    """Distance from points to closed rectangles (broadcasting)."""
    dx = np.maximum(np.maximum(x0 - px, 0.0), px - x1)
    dy = np.maximum(np.maximum(y0 - py, 0.0), py - y1)
    return np.hypot(dx, dy)


def _point_segment_dist(qx, qy, ax: float, ay: float, bx: float, by: float) -> np.ndarray:
    vx, vy = bx - ax, by - ay
    L2 = vx * vx + vy * vy
    if L2 == 0.0:
        return np.hypot(qx - ax, qy - ay)
    t = np.clip(((qx - ax) * vx + (qy - ay) * vy) / L2, 0.0, 1.0)
    return np.hypot(qx - (ax + t * vx), qy - (ay + t * vy))


def _segment_hits_rects(ax: float, ay: float, bx: float, by: float, x0, x1, y0, y1) -> np.ndarray:
    """Liang-Barsky: does the closed segment meet each closed rectangle?"""
    dx, dy = bx - ax, by - ay
    t0 = np.zeros(np.shape(x0))
    t1 = np.ones(np.shape(x0))
    ok = np.ones(np.shape(x0), dtype=bool)
    for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if p == 0.0:
            ok &= q >= 0.0
        else:
            r = q / p
            if p < 0.0:
                t0 = np.maximum(t0, r)
            else:
                t1 = np.minimum(t1, r)
    return ok & (t0 <= t1)


def polyline_rect_dmin(g: np.ndarray, x0, x1, y0, y1) -> np.ndarray:
    """Minimum distance from a polyline to each closed rectangle (0 if they meet)."""
    if len(g) == 1:
        return point_rect_dist(g[0, 0], g[0, 1], x0, x1, y0, y1)
    out = np.full(np.shape(x0), np.inf)
    corners = ((x0, y0), (x0, y1), (x1, y0), (x1, y1))
    for i in range(len(g) - 1):
        ax, ay = g[i]
        bx, by = g[i + 1]
        d = np.minimum(point_rect_dist(ax, ay, x0, x1, y0, y1), point_rect_dist(bx, by, x0, x1, y0, y1))
        for cx, cy in corners:
            d = np.minimum(d, _point_segment_dist(cx, cy, ax, ay, bx, by))
        d = np.where(_segment_hits_rects(ax, ay, bx, by, x0, x1, y0, y1), 0.0, d)
        out = np.minimum(out, d)
    return out


def points_rect_dmax(pts: np.ndarray, x0, x1, y0, y1) -> np.ndarray:
    """Farthest distance from each point (rows of ``pts``) to each rectangle: ``[n_pts, n_rects]``."""
    px = pts[:, 0][:, None]
    py = pts[:, 1][:, None]
    dx = np.maximum(np.abs(px - x0[None, :]), np.abs(px - x1[None, :]))
    dy = np.maximum(np.abs(py - y0[None, :]), np.abs(py - y1[None, :]))
    return np.hypot(dx, dy)


def solid_angle_rects(pts: np.ndarray, x0, x1, y0, y1, h: float) -> np.ndarray:
    """Exact solid angle (sr) of horizontal rectangles at height ``h`` above each point:
    ``[n_pts, n_rects]``. Inclusion-exclusion of ``atan(u v / (h sqrt(u^2 + v^2 + h^2)))``."""
    px = pts[:, 0][:, None]
    py = pts[:, 1][:, None]

    def F(u, v):
        return np.arctan(u * v / (h * np.sqrt(u * u + v * v + h * h)))

    u0, u1 = x0[None, :] - px, x1[None, :] - px
    v0, v1 = y0[None, :] - py, y1[None, :] - py
    return np.maximum(F(u1, v1) - F(u0, v1) - F(u1, v0) + F(u0, v0), 0.0)


def solid_angle_cap(sx: float, sy: float, h: float) -> float:
    """Largest solid angle of an ``sx`` by ``sy`` rectangle at height ``h`` (seen from below its centre)."""
    a, b = sx / 2.0, sy / 2.0
    return float(4.0 * np.arctan(a * b / (h * np.sqrt(a * a + b * b + h * h))))


def solid_angle_upper(dmin: np.ndarray, area: float, h: float, cap: float) -> np.ndarray:
    """Upper bound on a cell's solid angle from any receiver at distance >= ``dmin`` from it.

    For ``dmin > 0`` the cell lies in a wedge of angle < pi at radii >= dmin; the bathtub
    principle for the radially decreasing kernel ``h / (r^2 + h^2)^1.5`` gives
    ``pi h (1/sqrt(dmin^2 + h^2) - 1/sqrt(dmin^2 + 2 A / pi + h^2))``. Touching cells get ``cap``.
    """
    d2 = np.asarray(dmin, dtype=float) ** 2
    wedge = np.pi * h * (1.0 / np.sqrt(d2 + h * h) - 1.0 / np.sqrt(d2 + 2.0 * area / np.pi + h * h))
    return np.where(d2 > 0.0, np.minimum(wedge, cap), cap)


def solid_angle_lower(dmax: np.ndarray, area: float, h: float) -> np.ndarray:
    """Lower bound on a cell's solid angle from any receiver within ``dmax`` of all of it: the
    cell (area A) lies in the disk of radius dmax, and the outer annulus of area A minimises the
    integral of the radially decreasing kernel."""
    d2 = np.asarray(dmax, dtype=float) ** 2
    rin2 = np.maximum(d2 - area / np.pi, 0.0)
    return np.maximum(2.0 * np.pi * h * (1.0 / np.sqrt(rin2 + h * h) - 1.0 / np.sqrt(d2 + h * h)), 0.0)


def probe_points_xy(g: np.ndarray) -> np.ndarray:
    """Vertices and segment midpoints: positions the vehicle certainly occupies at some time."""
    if is_stationary(g):
        return g[:1].copy()
    mids = 0.5 * (g[:-1] + g[1:])
    return np.concatenate([g, mids])


def rasterize_polygons(grid: Grid, polygons) -> np.ndarray:
    """All-touched rasterization: cells whose closed square meets any polygon (rings as
    ``[n, 2]`` arrays in CRS units; holes are not subtracted — conservative)."""
    mask = np.zeros((grid.height, grid.width), dtype=bool)
    rings = list(_iter_rings(polygons))
    if not rings:
        return mask
    rows, cols = np.mgrid[0:grid.height, 0:grid.width]
    centers = grid.cell_centers(rows.ravel(), cols.ravel())
    for ring in rings:
        closed = np.vstack([ring, ring[:1]]) if not np.array_equal(ring[0], ring[-1]) else ring
        r, c, _ = polyline_cells(grid, closed)
        mask[r, c] = True
        mask |= _points_in_ring(centers, closed).reshape(grid.height, grid.width)
    return mask


def polygons_dmin(grid: Grid, polygons) -> np.ndarray:
    """Minimum distance (m) from every cell to the union of polygons; 0 where touched."""
    touched = rasterize_polygons(grid, polygons)
    rows, cols = np.mgrid[0:grid.height, 0:grid.width]
    x0, x1, y0, y1 = grid.cell_rects(rows.ravel(), cols.ravel())
    d = np.full(rows.size, np.inf)
    for ring in _iter_rings(polygons):
        closed = np.vstack([ring, ring[:1]]) if not np.array_equal(ring[0], ring[-1]) else ring
        d = np.minimum(d, polyline_rect_dmin(closed, x0, x1, y0, y1))
    d = d.reshape(grid.height, grid.width)
    d[touched] = 0.0
    return d


def _iter_rings(polygons):
    """Accept one ring, a polygon (list of rings) or a list of polygons."""
    if polygons is None:
        return
    arr = None
    try:
        arr = np.asarray(polygons, dtype=float)
    except (ValueError, TypeError):
        arr = None
    if arr is not None and arr.ndim == 2 and arr.shape[1] == 2:
        yield as_polyline(arr)
        return
    for item in polygons:
        yield from _iter_rings(item)


def _points_in_ring(pts: np.ndarray, ring: np.ndarray) -> np.ndarray:
    """Even-odd point-in-polygon test for many points against one closed ring."""
    x, y = pts[:, 0], pts[:, 1]
    inside = np.zeros(len(pts), dtype=bool)
    xs, ys = ring[:, 0], ring[:, 1]
    for i in range(len(ring) - 1):
        xa, ya, xb, yb = xs[i], ys[i], xs[i + 1], ys[i + 1]
        if ya == yb:
            continue
        cond = (ya > y) != (yb > y)
        xint = xa + (y - ya) * (xb - xa) / (yb - ya)
        inside ^= cond & (x < xint)
    return inside
