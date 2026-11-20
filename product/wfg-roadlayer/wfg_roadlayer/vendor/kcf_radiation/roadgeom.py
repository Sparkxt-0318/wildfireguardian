"""Road pieces and their distance to 375 m cells (METHOD.md section 7).

A graph edge is the straight chord between its two nodes, split into pieces by its ``segments`` list
(cell, end fraction), exactly as research/kcf-replay/replay.py and product/wfg-roadlayer read it. Piece k of edge j
runs from fraction end_{k-1} (0 for the first) to end_k along the chord and lies in cell ``cell_k``.

``piece_cell_distance`` gives the Euclidean distance (m) from a piece (a line segment) to the closed rectangle of a
cell; 0 when they touch. Everything here is plain geometry; no fire physics.
"""
from __future__ import annotations

import numpy as np


def pieces(road):
    """Arrays over all pieces: edge index, piece index within the edge, cell, fraction start/end, and the piece's
    end points (x0, y0, x1, y1) in the graph CRS (EPSG:5179, metres)."""
    E, K, C, F0, F1, X0, Y0, X1, Y1 = ([] for _ in range(9))
    for j, segs in enumerate(road.seg):
        xa, ya = road.node_xy[road.tail[j]]
        xb, yb = road.node_xy[road.head[j]]
        prev = 0.0
        for k, (c, zb) in enumerate(segs):
            z = float(zb)
            E.append(j); K.append(k); C.append(int(c)); F0.append(prev); F1.append(z)
            X0.append(xa + (xb - xa) * prev); Y0.append(ya + (yb - ya) * prev)
            X1.append(xa + (xb - xa) * z); Y1.append(ya + (yb - ya) * z)
            prev = z
    a = lambda v, t=float: np.asarray(v, dtype=t)  # noqa: E731
    return {"edge": a(E, np.int64), "k": a(K, np.int64), "cell": a(C, np.int64), "f0": a(F0), "f1": a(F1),
            "x0": a(X0), "y0": a(Y0), "x1": a(X1), "y1": a(Y1)}


def _point_rect(px, py, xmin, xmax, ymin, ymax):
    dx = np.maximum(np.maximum(xmin - px, 0.0), px - xmax)
    dy = np.maximum(np.maximum(ymin - py, 0.0), py - ymax)
    return np.hypot(dx, dy)


def _point_segment(px, py, x0, y0, x1, y1):
    vx, vy = x1 - x0, y1 - y0
    L2 = vx * vx + vy * vy
    with np.errstate(invalid="ignore", divide="ignore"):
        t = np.where(L2 > 0, ((px - x0) * vx + (py - y0) * vy) / np.where(L2 > 0, L2, 1.0), 0.0)
    t = np.clip(t, 0.0, 1.0)
    return np.hypot(px - (x0 + t * vx), py - (y0 + t * vy))


def _segments_intersect(ax, ay, bx, by, cx, cy, dx, dy):
    def orient(px, py, qx, qy, rx, ry):
        return (qx - px) * (ry - py) - (qy - py) * (rx - px)
    o1 = orient(ax, ay, bx, by, cx, cy)
    o2 = orient(ax, ay, bx, by, dx, dy)
    o3 = orient(cx, cy, dx, dy, ax, ay)
    o4 = orient(cx, cy, dx, dy, bx, by)
    return (o1 * o2 <= 0) & (o3 * o4 <= 0)


def segment_rect_distance(x0, y0, x1, y1, xmin, xmax, ymin, ymax):
    """Distance from segment(s) to axis-aligned rectangle(s), vectorised; 0 if they intersect."""
    d = np.minimum(_point_rect(x0, y0, xmin, xmax, ymin, ymax), _point_rect(x1, y1, xmin, xmax, ymin, ymax))
    corners = ((xmin, ymin), (xmin, ymax), (xmax, ymin), (xmax, ymax))
    for cx, cy in corners:
        d = np.minimum(d, _point_segment(cx, cy, x0, y0, x1, y1))
    edges = ((xmin, ymin, xmax, ymin), (xmax, ymin, xmax, ymax), (xmax, ymax, xmin, ymax), (xmin, ymax, xmin, ymin))
    hit = np.zeros(np.broadcast(x0, xmin).shape, dtype=bool)
    for ex0, ey0, ex1, ey1 in edges:
        hit |= _segments_intersect(x0, y0, x1, y1, ex0, ey0, ex1, ey1)
    return np.where(hit, 0.0, d)


def cell_rect_arrays(road, cells):
    cells = np.asarray(cells, dtype=np.int64)
    r, c = np.divmod(cells, road.W)
    x0, y0, res = float(road.x0), float(road.y0), float(road.res)
    return x0 + c * res, x0 + (c + 1) * res, y0 + r * res, y0 + (r + 1) * res


def neighbour_cells(road, cells, ring: int):
    """For each cell, the cells within ``ring`` rows/columns (including itself), clipped to the grid.
    Returns a (n, (2*ring+1)^2) int array with -1 where outside the grid."""
    cells = np.asarray(cells, dtype=np.int64)
    r, c = np.divmod(cells, road.W)
    out = []
    for dr in range(-ring, ring + 1):
        for dc in range(-ring, ring + 1):
            rr, cc = r + dr, c + dc
            ok = (rr >= 0) & (rr < road.H) & (cc >= 0) & (cc < road.W)
            out.append(np.where(ok, rr * road.W + cc, -1))
    return np.stack(out, axis=1)
