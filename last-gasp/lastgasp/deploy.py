"""Phase 2 tag deployment layouts (synthetic).

- roads: tags every `spacing` metres of drivable road (OSM roads).
- edge: tags every `spacing` metres along a forest-edge proxy, the line at
  `edge_buffer_m` from the nearest building (the boundary between settled
  land and the surrounding vegetation). No land-cover data are used; this is
  a geometric stand-in for "forest edge" around villages.
- roads+edge: both.
"""
from __future__ import annotations

import numpy as np
from scipy.ndimage import distance_transform_edt


def _place_along(polylines, spacing, width, height, step=5.0):
    """Greedy thinning of dense samples (every `step` m) so accepted tags are >= spacing apart.

    Walking each line in order and accepting a sample when no accepted tag lies
    within `spacing` gives about one tag per `spacing` metres of line, including
    across short connected OSM ways.
    """
    dense = []
    for xy in polylines:
        xy = np.asarray(xy, dtype=float)
        if len(xy) < 2:
            continue
        seg = np.hypot(*np.diff(xy, axis=0).T)
        cum = np.r_[0.0, np.cumsum(seg)]
        if cum[-1] <= 0:
            continue
        s = np.arange(0.0, cum[-1] + 1e-9, step)
        dense.append(np.c_[np.interp(s, cum, xy[:, 0]), np.interp(s, cum, xy[:, 1])])
    if not dense:
        return np.zeros((0, 2))
    P = np.vstack(dense)
    P = P[(P[:, 0] >= 0) & (P[:, 0] <= width) & (P[:, 1] >= 0) & (P[:, 1] <= height)]
    cellsz = spacing
    grid = {}
    kept = []
    r2 = (0.999 * spacing) ** 2
    for p in P:
        cx, cy = int(p[0] // cellsz), int(p[1] // cellsz)
        ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for q in grid.get((cx + dx, cy + dy), ()):
                    if (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 < r2:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            kept.append(p)
            grid.setdefault((cx, cy), []).append(p)
    return np.asarray(kept)


def road_length_m(world):
    W, H = world["width_m"], world["height_m"]
    tot = 0.0
    for r in world["roads"]:
        xy = np.asarray(r["xy"])
        inside = (xy[:, 0] >= 0) & (xy[:, 0] <= W) & (xy[:, 1] >= 0) & (xy[:, 1] <= H)
        seg = np.hypot(*np.diff(xy, axis=0).T)
        tot += float(np.sum(seg[inside[:-1] & inside[1:]]))
    return tot


def edge_polylines(world, bxy, buffer_m=100.0, cell=10.0):
    """Contour at distance buffer_m from the nearest building, clipped to the domain."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    W, H = world["width_m"], world["height_m"]
    nx, ny = int(np.ceil(W / cell)), int(np.ceil(H / cell))
    occ = np.ones((ny, nx), bool)
    ix = np.clip((bxy[:, 0] / cell).astype(int), 0, nx - 1)
    iy = np.clip((bxy[:, 1] / cell).astype(int), 0, ny - 1)
    occ[iy, ix] = False
    dist = distance_transform_edt(occ) * cell
    xs = (np.arange(nx) + 0.5) * cell
    ys = (np.arange(ny) + 0.5) * cell
    fig = plt.figure()
    cs = plt.contour(xs, ys, dist, levels=[buffer_m])
    lines = [seg for seg in cs.allsegs[0] if len(seg) > 2]
    plt.close(fig)
    return lines


def edge_length_m(lines):
    return float(sum(np.sum(np.hypot(*np.diff(np.asarray(l), axis=0).T)) for l in lines))


def layout(world, bxy, kind, spacing, buffer_m=100.0):
    """Tag positions (N, 2) for a layout kind and spacing (m)."""
    W, H = world["width_m"], world["height_m"]
    parts = []
    if kind in ("roads", "roads+edge"):
        parts.append(_place_along([r["xy"] for r in world["roads"]], spacing, W, H))
    if kind in ("edge", "roads+edge"):
        parts.append(_place_along(edge_polylines(world, bxy, buffer_m), spacing, W, H))
    P = np.vstack([p for p in parts if len(p)]) if parts else np.zeros((0, 2))
    return P
