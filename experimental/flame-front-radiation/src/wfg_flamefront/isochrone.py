"""Isochrones of the arrival-time field (centre-split marching squares), rate and direction of spread.

Interpolant. On the dual grid (nodes at cell centres) every square is split into four triangles that share the square
centre, where the value is the bilinear centre value (mean of the four corners). On each triangle the field is linear.
The resulting continuous piecewise-linear interpolant tau(x) equals the bilinear interpolant at the corners, along every
square edge (both are linear there, so edge crossings are the classical marching-squares points) and at the centre.
This is marching squares with centre-value saddle disambiguation; inside a square the isochrone is a polyline of up to
four straight pieces, each an exact level line of tau. The flaming band, the emitters and the enclosure all use this
one field, so they are consistent by construction.

For a level t a vertex is "burned" when its value is <= t; a triangle whose vertices differ carries one segment between
the crossing points of its two straddling edges. The segment is split at the square midline that passes through the
triangle; each piece lies in one host cell (the grid cell containing it) and is kept only if that cell is active at t
(``FrontField.frames``), so v2 flames lie inside the cells that v1 marks as flaming. Squares with an unknown corner
carry nothing.

Rate of spread. grad tau (s/m) is constant on a triangle; R = 1 / |grad tau| (m/s) clipped to ``r_max`` (default 3 m/s);
the spread direction is the unit vector of +grad tau, the direction in which arrival time increases, which is the
direction the front moves. A zero gradient cannot carry a segment (no straddling edge). The clip is flagged.

Degenerate cases (tested): an isolated burning cell gives a closed loop of pieces around its centre, inside that cell
while the loop is within half a cell; simultaneous neighbours give no crossing between them and the clipped maximum rate
only where the gradient is tiny; present-fire cells share the enclosure arrival R_max - T, so the interior of a present
fire has no isochrone at t >= 0 and only its perimeter carries a front.
"""
from __future__ import annotations

import numpy as np

from . import provenance as PV
from .field import prepare

# triangles of a dual square in local (u, v): vertex A, vertex B, then the centre; the split midline and host quadrant
# (qv, qu) on each side of it
_TRI = [
    # A,       B,       corner keys, midline axis ('u' or 'v'), quadrant below the midline value, above it
    ((0., 0.), (1., 0.), (0, 1), "u", (0, 0), (0, 1)),   # bottom: c00, c01
    ((1., 0.), (1., 1.), (1, 3), "v", (0, 1), (1, 1)),   # right:  c01, c11
    ((1., 1.), (0., 1.), (3, 2), "u", (1, 0), (1, 1)),   # top:    c11, c10
    ((0., 1.), (0., 0.), (2, 0), "v", (0, 0), (1, 0)),   # left:   c10, c00
]


def corner_values(field, level_offset=None):
    c00, c01, c10, c11, ok = field.squares()
    if level_offset is not None:
        o = np.broadcast_to(np.asarray(level_offset, float), field.shape)
        c00, c01, c10, c11 = c00 + o[:-1, :-1], c01 + o[:-1, 1:], c10 + o[1:, :-1], c11 + o[1:, 1:]
    return (c00, c01, c10, c11), ok


def triangle_of(lu, lv):
    """Index (0 bottom, 1 right, 2 top, 3 left) of the triangle containing local point (lu, lv)."""
    du, dv = lu - 0.5, lv - 0.5
    return np.where(dv <= -np.abs(du), 0, np.where(du >= np.abs(dv), 1, np.where(dv >= np.abs(du), 2, 3)))


def triangle_plane(cs, k):
    """Linear function of triangle k: returns (t0, gu, gv) with tau = t0 + gu*u + gv*v in local coordinates."""
    c = cs
    cm = 0.25 * (c[0] + c[1] + c[2] + c[3])
    (ua, va), (ub, vb), (ia, ib), *_ = _TRI[k]
    A, B = c[ia], c[ib]
    # solve tau(A)=A, tau(B)=B, tau(0.5,0.5)=cm
    M = np.array([[1., ua, va], [1., ub, vb], [1., .5, .5]])
    Minv = np.linalg.inv(M)
    t0 = Minv[0, 0] * A + Minv[0, 1] * B + Minv[0, 2] * cm
    gu = Minv[1, 0] * A + Minv[1, 1] * B + Minv[1, 2] * cm
    gv = Minv[2, 0] * A + Minv[2, 1] * B + Minv[2, 2] * cm
    return t0, gu, gv


def pl_value(c00, c01, c10, c11, lu, lv):
    """Piecewise-linear (centre-split) interpolant at local coordinates."""
    cs = (c00, c01, c10, c11)
    k = triangle_of(lu, lv)
    out = np.full(np.shape(lu), np.nan)
    for kk in range(4):
        t0, gu, gv = triangle_plane(cs, kk)
        out = np.where(k == kk, t0 + gu * lu + gv * lv, out)
    return out


def _cross(p, q, L):
    bp, bq = p <= L, q <= L
    x = bp != bq
    with np.errstate(divide="ignore", invalid="ignore"):
        s = np.clip((L - p) / (q - p), 0.0, 1.0)
    return np.where(x, s, np.nan), x


def front_pieces(field, t, *, level_offset=None, r_max=PV.MAX_SPREAD_RATE_M_S, active=None):
    """Flame pieces of the isochrone tau(x) = t (or tau(x) + level_offset(x) = t) clipped to active host cells.

    Returns a dict of 1-D arrays: x0, y0, x1, y1 (m), host_r, host_c, sq_r, sq_c, tri, R (m/s), dir_x, dir_y,
    clipped (rate clipped at r_max).
    """
    f = field
    cs, ok = corner_values(f, level_offset)
    lo = np.fmin(np.fmin(cs[0], cs[1]), np.fmin(cs[2], cs[3]))
    hi = np.fmax(np.fmax(cs[0], cs[1]), np.fmax(cs[2], cs[3]))
    cand = ok & (lo <= t) & (hi > t)
    keys_f = ("x0", "y0", "x1", "y1", "R", "dir_x", "dir_y")
    keys_i = ("host_r", "host_c", "sq_r", "sq_c", "tri")
    empty = {k: np.zeros(0) for k in keys_f}
    empty.update({k: np.zeros(0, np.int64) for k in keys_i})
    empty["clipped"] = np.zeros(0, bool)
    if not cand.any():
        return empty
    rr, cc = np.nonzero(cand)
    c = [x[rr, cc] for x in cs]
    cm = 0.25 * (c[0] + c[1] + c[2] + c[3])
    act = f.active_at(t) if active is None else active
    g = f.grid
    parts = []
    for k, ((ua, va), (ub, vb), (ia, ib), axis, qlo, qhi) in enumerate(_TRI):
        A, B = c[ia], c[ib]
        verts = [(ua, va, A), (ub, vb, B), (0.5, 0.5, cm)]
        pts = []
        for (pu, pv, pval), (qu, qv, qval) in ((verts[0], verts[1]), (verts[1], verts[2]), (verts[2], verts[0])):
            s, x = _cross(pval, qval, t)
            pts.append((pu + s * (qu - pu), pv + s * (qv - pv), x))
        x01, x12, x20 = pts[0][2], pts[1][2], pts[2][2]
        n = x01.astype(int) + x12 + x20
        m = n == 2
        if not m.any():
            continue
        # the two crossed edges
        U = np.stack([pts[0][0], pts[1][0], pts[2][0]], -1); V = np.stack([pts[0][1], pts[1][1], pts[2][1]], -1)
        X = np.stack([x01, x12, x20], -1)
        idx = np.nonzero(m)[0]
        first = np.argmax(X[idx], axis=-1)
        Xr = X[idx].copy(); Xr[np.arange(idx.size), first] = False
        second = np.argmax(Xr, axis=-1)
        u0 = U[idx, first]; v0 = V[idx, first]; u1 = U[idx, second]; v1 = V[idx, second]
        t0, gu, gv = triangle_plane([ci[idx] for ci in c], k)
        # split at the triangle's midline
        a0 = u0 if axis == "u" else v0
        a1 = u1 if axis == "u" else v1
        with np.errstate(divide="ignore", invalid="ignore"):
            tm = (0.5 - a0) / (a1 - a0)
        split = (tm > 0) & (tm < 1)
        tm = np.where(split, tm, 1.0)
        um, vm = u0 + tm * (u1 - u0), v0 + tm * (v1 - v0)
        for (pa_u, pa_v, pb_u, pb_v, sel) in ((u0, v0, um, vm, np.ones(idx.size, bool)), (um, vm, u1, v1, split)):
            if not sel.any():
                continue
            j = np.nonzero(sel)[0]
            mid = 0.5 * ((pa_u[j] + pb_u[j]) if axis == "u" else (pa_v[j] + pb_v[j]))
            qv_, qu_ = np.where(mid > 0.5, qhi[0], qlo[0]), np.where(mid > 0.5, qhi[1], qlo[1])
            parts.append((rr[idx[j]], cc[idx[j]], np.full(j.size, k), pa_u[j], pa_v[j], pb_u[j], pb_v[j],
                          rr[idx[j]] + qv_, cc[idx[j]] + qu_, gu[j], gv[j]))
    if not parts:
        return empty
    sr, sc, tri, pu0, pv0, pu1, pv1, hr, hc, gu, gv = (np.concatenate([p[i] for p in parts]) for i in range(11))
    keep = act[hr, hc] & ((pu0 != pu1) | (pv0 != pv1))
    if not keep.any():
        return empty
    sr, sc, tri, pu0, pv0, pu1, pv1, hr, hc, gu, gv = (z[keep] for z in (sr, sc, tri, pu0, pv0, pu1, pv1, hr, hc, gu, gv))
    x0, y0 = g.to_xy(sc + pu0, sr + pv0)
    x1, y1 = g.to_xy(sc + pu1, sr + pv1)
    gx, gy = gu / g.a, gv / g.e
    mag = np.hypot(gx, gy)
    clipped = mag * r_max <= 1.0
    with np.errstate(divide="ignore", invalid="ignore"):
        R = np.where(clipped, r_max, 1.0 / mag)
        dxu = np.where(mag > 0, gx / mag, 0.0)
        dyu = np.where(mag > 0, gy / mag, 0.0)
    return {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "host_r": hr, "host_c": hc, "sq_r": sr, "sq_c": sc, "tri": tri,
            "R": R, "dir_x": dxu, "dir_y": dyu, "clipped": clipped}


def front_segments(ignition_time_s, t, grid, residence_s, *, fuel=None, never_arrival_s=None, horizon_s=None,
                   duration_s=None, r_max=PV.MAX_SPREAD_RATE_M_S, include_trailing=True):
    """Contract C: flame segments of the isochrone of the ignition-time field at time t.

    ``ignition_time_s`` is either an [H, W] array (seconds since cutoff; inf = never, mapped to ``never_arrival_s``,
    default horizon + T; nan = unknown; every cell treated as active, no v1 activity clipping) or a member mapping /
    ``FrontField`` (v1 conventions and activity clipping, see ``field.prepare``). ``residence_s`` is a scalar or [H, W]
    flame residence time; the trailing edge of the flaming band is the isochrone tau(x) + residence = t.

    Returns a list of dicts, one per piece: ``edge`` ("leading" or "trailing"), ``p0``, ``p1`` (m), ``length_m``,
    ``host_cell`` (row, col), ``rate_of_spread_m_s``, ``spread_direction``, ``intensity_kw_m``, ``flame_length_m``,
    ``flame_height_m``, ``tilt_rad``, ``tilt_direction``, ``emissive_power_kw_m2``, ``rate_clipped``.
    """
    from .intensity import flame_geometry, FuelParameters
    if isinstance(ignition_time_s, (np.ndarray, list, tuple)):
        ign = np.array(ignition_time_s, dtype=float)
        ff = prepare({"ignition_time_s": ign}, grid, horizon_s=horizon_s, duration_s=duration_s,
                     never_arrival_s=never_arrival_s)
        ff.frames = np.ones((1,) + ign.shape, bool)
        ff.breakpoints = np.array([-np.inf, np.inf])
    else:
        ff = prepare(ignition_time_s, grid, horizon_s=horizon_s, duration_s=duration_s, never_arrival_s=never_arrival_s)
    fuel = FuelParameters.coerce(fuel)
    res = np.broadcast_to(np.asarray(residence_s, dtype=float), ff.shape)
    out = []
    edges = [("leading", None)] + ([("trailing", res)] if include_trailing else [])
    for name, off in edges:
        p = front_pieces(ff, t, level_offset=off, r_max=r_max)
        geo = flame_geometry(p, fuel)
        for i in range(p["x0"].size):
            out.append({
                "edge": name,
                "p0": (float(p["x0"][i]), float(p["y0"][i])),
                "p1": (float(p["x1"][i]), float(p["y1"][i])),
                "length_m": float(np.hypot(p["x1"][i] - p["x0"][i], p["y1"][i] - p["y0"][i])),
                "host_cell": (int(p["host_r"][i]), int(p["host_c"][i])),
                "rate_of_spread_m_s": float(p["R"][i]),
                "spread_direction": (float(p["dir_x"][i]), float(p["dir_y"][i])),
                "intensity_kw_m": float(geo["intensity"][i]),
                "flame_length_m": float(geo["length"][i]),
                "flame_height_m": float(geo["height"][i]),
                "tilt_rad": float(geo["tilt"][i]),
                "tilt_direction": (float(geo["lean_x"][i]), float(geo["lean_y"][i])),
                "emissive_power_kw_m2": float(geo["E"][i]),
                "rate_clipped": bool(p["clipped"][i]),
            })
    return out
