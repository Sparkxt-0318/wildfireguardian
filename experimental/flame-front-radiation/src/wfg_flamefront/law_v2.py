"""Radiation law ``wfg.radiation.law/2-flamefront``: point flux, rigorous enclosure, dose (Contract C).

Point flux q(x, t) in kW/m2 at a receiver x (ground position, height ``fuel.receiver_height_m``):

* engulfment: if x lies in the flaming band of an active host cell, tau(x) <= t < tau(x) + residence(host), with tau
  the centre-split piecewise-linear interpolant of the member's arrival field (``isochrone``), then q = E(host): the
  receiver is inside the flame (AS 3959 flame zone);
* otherwise q = tau_a sum_k E_k F_k(x) over the leading-isochrone flame pieces k (``isochrone.front_pieces``) whose
  ground distance to x is at most ``fuel.cutoff_radius_m``; F_k is the worst-case (or vertical-facing) view factor of
  the panel standing on piece k (``solidflame``), height from the Byram flame length of the local rate of spread.

Enclosure (``flux_enclosure``). For an axis-aligned receiver box X and a closed time interval [a, b]. Every dual
square is split into four triangles at its centre and each triangle into two halves at the square midline; a half is a
triangle with one host cell and a linear arrival field, hence one rate of spread, one flame height and one E. Every
flame piece of the point model is the level line tau = L of one half, for some level L in [a, b].

* upper = max(engulfment term, radiation term). Radiation term: the sum, over every half (no cutoff) whose host cell is
  active somewhere in [a, b] and whose arrival range straddles a level in [a, b], of tau_a E min(1, Omega / pi). Here
  Omega is the exact solid angle of a box in the frame aligned with the level lines: along the level lines it spans the
  half cut by Lmin <= tau <= Lmax (vertices: half vertices inside, edge crossings of the two levels), across them the
  exact level band (tau is linear), vertically [0, flame height], horizontally widened by the maximum lean, and finally
  Minkowski-differenced with the receiver box, so it contains (panel - x) for every receiver x in X. For any receiver
  orientation the configuration factor of a panel is at most its solid angle over pi, and at most 1. Engulfment term:
  E(host) for any half whose host is active in [a, b] and whose part inside X has tau <= b and tau + residence > a
  (exact extremes of a linear field on a convex polygon, attained at its vertices).
* lower: E(host) when X lies inside the dual region and inside one host cell that is active throughout [a, b], and
  every x in X is in the flaming band throughout [a, b] (max tau over X <= a and min tau + residence > b); otherwise 0.
  A tighter lower bound for radiation outside the flame would need enclosures of panel orientation; it is not provided.
* both are monotone: enlarging X or [a, b] adds halves, widens level bands and Minkowski boxes (solid angle of a
  superset) and makes the lower-bound conditions harder.
* the upper bound is never below the point evaluation at any (x, t) in X x [a, b]: each point term is dominated by its
  half's term, the point sum is truncated at the cutoff while the bound is not, and engulfment is dominated by the
  engulfment term. A relative margin of 1e-9 and an absolute margin of 1e-12 kW/m2 cover floating-point rounding.

Dose (``dose``): trapezoid integral of samples; ``linear`` gives kJ/m2 (q in kW/m2, t in s), ``tdu`` gives the thermal
dose unit integral of q^(4/3) dt in (kW/m2)^(4/3) s (Eisenberg et al. 1975; TNO Green Book; UK HSE).

Context recorded for users of the numbers: the 2006 CSIRO passenger-vehicle burnover tests saw 10 to 40 kW/m2 peak
radiant intensities outside the vehicle and an average time to toxic-air untenability inside of about 10 minutes,
driven by smoke and particles more than by heat. A route therefore needs both a peak threshold and a duration or dose
cap. Convective heating (comparable to radiation at the front in surface fires, extending two or more flame lengths ahead
on slopes and in wind), smoke, embers and vehicle shielding are not modelled.
"""
from __future__ import annotations

import math

import numpy as np

from . import provenance as PV
from .field import FrontField, Grid, prepare
from .intensity import FuelParameters, flame_geometry, max_flame_extent
from .isochrone import _TRI, corner_values, front_pieces, pl_value, triangle_plane
from .solidflame import box_solid_angle, panel_vertices, point_to_segment_distance

LAW_VERSION = PV.LAW_VERSION
REL_MARGIN = 1e-9
ABS_MARGIN_KW_M2 = 1e-12


def _field(member, grid, present_fire="enclosure"):
    if isinstance(member, FrontField):
        return member
    return prepare(member, grid, present_fire=present_fire)


def _residence_map(fuel, shape):
    return np.broadcast_to(np.asarray(fuel.residence_s, float), shape)


def _emissive_map(fuel, shape):
    """Flame-surface emissive power of the panels (radiation at a distance)."""
    return np.broadcast_to(np.asarray(fuel.emissive_power_kw_m2, float), shape)


def _inflame_map(fuel, shape):
    """In-flame flux for an engulfed receiver; defaults to the panel emissive power."""
    v = fuel.inflame_emissive_power_kw_m2
    return _emissive_map(fuel, shape) if v is None else np.broadcast_to(np.asarray(v, float), shape)


class _PointGeometry:
    """Static per-point data for engulfment tests: dual square, local coordinates, interpolated arrival, host cell."""

    def __init__(self, ff, pts):
        g = ff.grid
        H, W = ff.shape
        u, v = g.to_index(pts[:, 0], pts[:, 1])
        self.sr = np.floor(v).astype(np.int64)
        self.sc = np.floor(u).astype(np.int64)
        inside = (self.sr >= 0) & (self.sr < H - 1) & (self.sc >= 0) & (self.sc < W - 1)
        sr = np.clip(self.sr, 0, H - 2); sc = np.clip(self.sc, 0, W - 2)
        self.lu, self.lv = u - sc, v - sr
        c00, c01, c10, c11, ok = ff.squares()
        self.inside = inside & ok[sr, sc]
        with np.errstate(invalid="ignore"):
            self.tau = pl_value(c00[sr, sc], c01[sr, sc], c10[sr, sc], c11[sr, sc], self.lu, self.lv)
        self.hr = np.clip(np.floor(v + 0.5).astype(np.int64), 0, H - 1)
        self.hc = np.clip(np.floor(u + 0.5).astype(np.int64), 0, W - 1)


def flux_at_points(points_xy, times_s, member, grid, fuel, receiver="worst_case", *, present_fire="enclosure",
                   chunk_pairs=2_000_000, details=False):
    """Incident radiant flux q[P, T] (kW/m2) at receiver points [P, 2] (m) and times [T] (s since cutoff).

    ``member`` is a v1/v2 member mapping (see ``field.prepare``) or a prepared ``FrontField``; ``grid`` the affine grid
    (``Grid``, an affine 6-tuple with the member shape, or a routing graph grid mapping); ``fuel`` a ``FuelParameters``,
    mapping or None (defaults). ``receiver``: ``"worst_case"`` or ``("vertical_facing", theta_rad)``.
    With ``details=True`` also returns a dict with the engulfment mask and the number of flame pieces per time.
    """
    ff = _field(member, grid, present_fire)
    fuel = FuelParameters.coerce(fuel)
    pts = np.asarray(points_xy, float).reshape(-1, 2)
    times = np.asarray(times_s, float).reshape(-1)
    P, T = pts.shape[0], times.size
    q = np.zeros((P, T))
    eng = np.zeros((P, T), bool)
    npieces = np.zeros(T, np.int64)
    if P == 0 or T == 0:
        return (q, {"engulfed": eng, "pieces": npieces}) if details else q
    pg = _PointGeometry(ff, pts)
    res = _residence_map(fuel, ff.shape)[pg.hr, pg.hc]
    Eh = _inflame_map(fuel, ff.shape)[pg.hr, pg.hc]
    zr = float(fuel.receiver_height_m)
    P3 = np.column_stack([pts, np.full(P, zr)])
    cutoff = float(fuel.cutoff_radius_m)
    for j, t in enumerate(times):
        act = ff.active_at(t)
        with np.errstate(invalid="ignore"):
            band = pg.inside & act[pg.hr, pg.hc] & (pg.tau <= t) & (t < pg.tau + res)
        pieces = front_pieces(ff, t, r_max=fuel.r_max_m_s, active=act)
        S = pieces["x0"].size
        npieces[j] = S
        if S:
            geo = flame_geometry(pieces, fuel)
            V = panel_vertices(pieces["x0"], pieces["y0"], pieces["x1"], pieces["y1"], geo["height"],
                               geo["reach"] * geo["lean_x"], geo["reach"] * geo["lean_y"], 0.0)
            # ground-distance prefilter on bounding boxes, then exact segment distance
            bx0 = np.minimum(pieces["x0"], pieces["x1"]) - cutoff; bx1 = np.maximum(pieces["x0"], pieces["x1"]) + cutoff
            by0 = np.minimum(pieces["y0"], pieces["y1"]) - cutoff; by1 = np.maximum(pieces["y0"], pieces["y1"]) + cutoff
            near_pts = np.nonzero((pts[:, 0] >= bx0.min()) & (pts[:, 0] <= bx1.max())
                                  & (pts[:, 1] >= by0.min()) & (pts[:, 1] <= by1.max()) & ~band)[0]
            step = max(1, int(chunk_pairs // max(S, 1)))
            for s0 in range(0, near_pts.size, step):
                idx = near_pts[s0:s0 + step]
                d = point_to_segment_distance(pts[idx, 0], pts[idx, 1], pieces["x0"], pieces["y0"],
                                              pieces["x1"], pieces["y1"])
                m = d <= cutoff
                if not m.any():
                    continue
                pi_, si_ = np.nonzero(m)
                F = view_factors_pairs(P3[idx][pi_], V[si_], receiver)
                contrib = fuel.transmissivity * geo["E"][si_] * F
                q[idx, j] += np.bincount(pi_, weights=contrib, minlength=idx.size)
        if band.any():
            q[band, j] = Eh[band]
            eng[band, j] = True
    if details:
        return q, {"engulfed": eng, "pieces": npieces}
    return q


def view_factors_pairs(P3, V, receiver):
    """View factors for paired receivers [N, 3] and panels [N, 4, 3]."""
    from .solidflame import lambert_vector
    R = V - P3[:, None, :]
    v = lambert_vector(R)
    if receiver == "worst_case":
        F = np.linalg.norm(v, axis=-1)
    else:
        kind, theta = receiver
        if kind != "vertical_facing":
            raise ValueError("receiver must be 'worst_case' or ('vertical_facing', theta)")
        centre = V.mean(axis=-2) - P3
        sgn = np.sign(np.einsum("nk,nk->n", v, centre))
        n = np.array([math.cos(theta), math.sin(theta), 0.0])
        F = np.maximum(0.0, sgn * (v @ n))
    return np.minimum(F, 1.0)


# ---- enclosure ---------------------------------------------------------------------------------------------------

def _boxes(box_xy):
    b = np.asarray(box_xy, float)
    if b.shape == (2, 2):
        b = np.array([[b[0, 0], b[1, 0], b[0, 1], b[1, 1]]])
    b = b.reshape(-1, 4)
    if np.any(b[:, 1] < b[:, 0]) or np.any(b[:, 3] < b[:, 2]):
        raise ValueError("box must be (xmin, xmax, ymin, ymax) with min <= max")
    return b


def _half_triangles(ff, fuel):
    """Static data of the eight half-triangles of every dual square (cached per field and fuel object).

    Each triangle of the centre split is cut by its midline into two halves, each a triangle with one host cell, a
    linear arrival field and therefore one rate of spread, one flame height and one emissive power.
    Returns dict of flat arrays over all valid (square, half) pairs.
    """
    cache = getattr(ff, "_halves", None)
    if cache is not None and cache[0] is fuel:
        return cache[1]
    g = ff.grid
    cs, ok = corner_values(ff)
    h, w = ok.shape
    rr, cc = np.nonzero(ok)
    c = [x[rr, cc] for x in cs]
    cm = 0.25 * (c[0] + c[1] + c[2] + c[3])
    out = {k: [] for k in ("sr", "sc", "hr", "hc", "U", "V", "T", "gx", "gy", "R", "E", "Hf", "reach")}
    for k, ((ua, va), (ub, vb), (ia, ib), axis, qlo, qhi) in enumerate(_TRI):
        t0, gu, gv = triangle_plane(c, k)
        A, B = c[ia], c[ib]
        # midpoint of the outer edge AB, split point on the midline
        um, vm = 0.5 * (ua + ub), 0.5 * (va + vb)
        Mv = 0.5 * (A + B)
        for (pu, pv, pval), quad in (((ua, va, A), qlo if (ua if axis == "u" else va) < 0.5 else qhi),
                                     ((ub, vb, B), qlo if (ub if axis == "u" else vb) < 0.5 else qhi)):
            out["sr"].append(rr); out["sc"].append(cc)
            out["hr"].append(rr + quad[0]); out["hc"].append(cc + quad[1])
            n = rr.size
            out["U"].append(np.tile([pu, um, 0.5], (n, 1))); out["V"].append(np.tile([pv, vm, 0.5], (n, 1)))
            out["T"].append(np.stack([pval, Mv, cm], -1))
            gx, gy = gu / g.a, gv / g.e
            out["gx"].append(gx); out["gy"].append(gy)
    D = {k: np.concatenate(v) for k, v in out.items() if v}
    mag = np.hypot(D["gx"], D["gy"])
    D["mag"] = mag
    with np.errstate(divide="ignore", invalid="ignore"):
        D["R"] = np.where(mag * fuel.r_max_m_s <= 1.0, fuel.r_max_m_s, 1.0 / mag)
    L, reach = max_flame_extent(D["R"], D["hr"], D["hc"], fuel)
    D["Hf"] = L * (1.0 + 1e-12); D["reach"] = reach
    D["E"] = _emissive_map(fuel, ff.shape)[D["hr"], D["hc"]]
    PX, PY = g.to_xy(D["sc"][:, None] + D["U"], D["sr"][:, None] + D["V"])
    D["PX"], D["PY"] = PX, PY
    D["tmin"], D["tmax"] = D["T"].min(-1), D["T"].max(-1)
    ff._halves = (fuel, D)
    return D


def _radiation_upper(ff, fuel, boxes, intervals):
    """Upper bound of the radiation term for boxes [N, 4] and intervals [N, 2] (see module docstring)."""
    D = _half_triangles(ff, fuel)
    N = boxes.shape[0]
    up = np.zeros(N)
    if D["tmin"].size == 0:
        return up
    a_all, b_all = float(intervals[:, 0].min()), float(intervals[:, 1].max())
    sel = (D["tmin"] <= b_all) & (D["tmax"] > a_all) & (D["mag"] > 0)
    if not sel.any():
        return up
    q = np.nonzero(sel)[0]
    hr, hc = D["hr"][q], D["hc"][q]
    act = np.zeros((N, q.size), bool)
    cache = {}
    for n_ in range(N):
        key = (intervals[n_, 0], intervals[n_, 1])
        A = cache.get(key)
        if A is None:
            A = cache[key] = ff.active_anywhere(key[0], key[1])[hr, hc]
        act[n_] = A
    a = intervals[:, 0][:, None]; b = intervals[:, 1][:, None]
    tmin, tmax = D["tmin"][q][None], D["tmax"][q][None]
    Lmin = np.maximum(a, tmin); Lmax = np.minimum(b, tmax)
    m = act & (Lmin <= Lmax) & (Lmin < tmax)
    if not m.any():
        return up
    ni, qi = np.nonzero(m)
    qq = q[qi]
    Lo, Hi = Lmin[ni, qi], Lmax[ni, qi]
    PX, PY, T = D["PX"][qq], D["PY"][qq], D["T"][qq]                     # [M, 3]
    gx, gy, mag = D["gx"][qq], D["gy"][qq], D["mag"][qq]
    nx, ny = gx / mag, gy / mag                                          # along grad tau
    ex, ey = -ny, nx                                                     # along the level lines
    # vertices of P = half-triangle cut by Lo <= tau <= Hi: vertices inside, edge crossings of tau = Lo and tau = Hi
    cand_s, cand_ok = [], []
    for i in range(3):
        j = (i + 1) % 3
        inside = (T[:, i] >= Lo) & (T[:, i] <= Hi)
        cand_s.append(PX[:, i] * ex + PY[:, i] * ey); cand_ok.append(inside)
        for Lv in (Lo, Hi):
            with np.errstate(divide="ignore", invalid="ignore"):
                s = (Lv - T[:, i]) / (T[:, j] - T[:, i])
            okc = (s >= 0) & (s <= 1) & (T[:, j] != T[:, i])
            s = np.where(okc, s, 0.0)
            xx = PX[:, i] + s * (PX[:, j] - PX[:, i]); yy = PY[:, i] + s * (PY[:, j] - PY[:, i])
            cand_s.append(xx * ex + yy * ey); cand_ok.append(okc)
    S = np.stack(cand_s, -1); OK = np.stack(cand_ok, -1)
    s0 = np.where(OK, S, np.inf).min(-1); s1 = np.where(OK, S, -np.inf).max(-1)
    good = np.isfinite(s0) & np.isfinite(s1)
    # n-range from the levels: tau = T0 + mag * (n - n0) at vertex 0
    n_ref = PX[:, 0] * nx + PY[:, 0] * ny
    t0 = n_ref + (Lo - T[:, 0]) / mag; t1 = n_ref + (Hi - T[:, 0]) / mag
    reach = D["reach"][qq]
    pad = 1e-9 * (1.0 + np.abs(s0) + np.abs(t0))
    es0, es1 = s0 - reach - pad, s1 + reach + pad
    en0, en1 = t0 - reach - pad, t1 + reach + pad
    bx = boxes[ni][:, [0, 1, 1, 0]]; by = boxes[ni][:, [2, 2, 3, 3]]
    RS = bx * ex[:, None] + by * ey[:, None]; RT = bx * nx[:, None] + by * ny[:, None]
    zr = float(fuel.receiver_height_m)
    lo3 = np.column_stack([es0 - RS.max(-1), en0 - RT.max(-1), np.full(ni.size, -zr)])
    hi3 = np.column_stack([es1 - RS.min(-1), en1 - RT.min(-1), D["Hf"][qq] - zr])
    om = box_solid_angle(lo3, hi3)
    F = np.where(good, np.minimum(1.0, om / math.pi), 1.0)
    contrib = fuel.transmissivity * D["E"][qq] * F
    return np.bincount(ni, weights=contrib, minlength=N)


def _tri_box_range(PX, PY, T, box):
    """Exact (min, max) of the linear field on triangle (PX, PY, T [3]) intersected with box; None if disjoint."""
    x0, x1, y0, y1 = box
    tol = 1e-9 * (1.0 + abs(x0) + abs(y0))
    # triangle edge functions for the inside test
    area = (PX[1] - PX[0]) * (PY[2] - PY[0]) - (PX[2] - PX[0]) * (PY[1] - PY[0])
    if area == 0:
        return None
    # barycentric coordinates give the linear value at any point
    def bary(x, y):
        l1 = ((PX[1] - x) * (PY[2] - y) - (PX[2] - x) * (PY[1] - y)) / area
        l2 = ((PX[2] - x) * (PY[0] - y) - (PX[0] - x) * (PY[2] - y)) / area
        return l1, l2, 1.0 - l1 - l2
    pts = [(PX[i], PY[i]) for i in range(3)] + [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    E = [(PX[i], PY[i], PX[(i + 1) % 3], PY[(i + 1) % 3]) for i in range(3)]
    for (ax, ay, bx_, by_) in E:
        for xv in (x0, x1):
            if bx_ != ax:
                s = (xv - ax) / (bx_ - ax)
                if 0 <= s <= 1:
                    pts.append((xv, ay + s * (by_ - ay)))
        for yv in (y0, y1):
            if by_ != ay:
                s = (yv - ay) / (by_ - ay)
                if 0 <= s <= 1:
                    pts.append((ax + s * (bx_ - ax), yv))
    vals = []
    for (x, y) in pts:
        if x < x0 - tol or x > x1 + tol or y < y0 - tol or y > y1 + tol:
            continue
        l = bary(x, y)
        if min(l) < -1e-9:
            continue
        vals.append(l[0] * T[0] + l[1] * T[1] + l[2] * T[2])
    if not vals:
        return None
    return min(vals), max(vals)


def _engulf_terms(ff, fuel, box, a, b):
    """(upper, lower) engulfment terms for one box and interval."""
    D = _half_triangles(ff, fuel)
    g = ff.grid
    H, W = ff.shape
    ux0, vy0 = g.to_index(box[0], box[2]); ux1, vy1 = g.to_index(box[1], box[3])
    umin, umax = min(ux0, ux1), max(ux0, ux1); vmin, vmax = min(vy0, vy1), max(vy0, vy1)
    res = _residence_map(fuel, ff.shape); Em = _inflame_map(fuel, ff.shape)
    c00, c01, c10, c11, ok = ff.squares()
    act_any = ff.active_anywhere(a, b)
    act_all = ff.active_throughout(a, b)
    r0, r1 = int(math.floor(vmin)), int(math.floor(vmax))
    c0, c1 = int(math.floor(umin)), int(math.floor(umax))
    covered = r0 >= 0 and c0 >= 0 and r1 <= H - 2 and c1 <= W - 2
    if not hasattr(ff, "_half_index"):
        idx = {}
        for i, (r, c) in enumerate(zip(D["sr"], D["sc"])):
            idx.setdefault((int(r), int(c)), []).append(i)
        ff._half_index = idx
    up, lower_ok, hosts = 0.0, covered, set()
    tau_max, tau_min_res = -np.inf, np.inf
    for r in range(max(r0, 0), min(r1, H - 2) + 1):
        for c in range(max(c0, 0), min(c1, W - 2) + 1):
            if not ok[r, c]:
                lower_ok = False
                continue
            for i in ff._half_index.get((r, c), ()):
                rng = _tri_box_range(D["PX"][i], D["PY"][i], D["T"][i], box)
                if rng is None:
                    continue
                hr, hc = int(D["hr"][i]), int(D["hc"][i])
                hosts.add((hr, hc))
                rh = float(res[hr, hc])
                if act_any[hr, hc] and rng[0] <= b and rng[1] + rh > a:
                    up = max(up, float(Em[hr, hc]))
                tau_max = max(tau_max, rng[1]); tau_min_res = min(tau_min_res, rng[0] + rh)
                if not act_all[hr, hc]:
                    lower_ok = False
    lower = 0.0
    if lower_ok and len(hosts) == 1 and tau_max <= a and tau_min_res > b:
        (hr, hc), = hosts
        lower = float(Em[hr, hc])
    return up, lower


def flux_enclosure(box_xy, interval_s, member, grid, fuel, *, present_fire="enclosure"):
    """Rigorous (lower, upper) bounds (kW/m2) of the point flux over a receiver box and a closed time interval.

    ``box_xy``: (xmin, xmax, ymin, ymax) in metres (the kit's order) or [[xmin, ymin], [xmax, ymax]].
    ``interval_s``: (a, b) with a <= b. Valid for every receiver orientation (see module docstring).
    """
    ff = _field(member, grid, present_fire)
    fuel = FuelParameters.coerce(fuel)
    box = _boxes(box_xy)
    a, b = (float(v) for v in interval_s)
    if b < a:
        raise ValueError("interval must satisfy a <= b")
    rad = float(_radiation_upper(ff, fuel, box, np.array([[a, b]]))[0])
    eu, el = _engulf_terms(ff, fuel, box[0], a, b)
    upper = max(rad, eu)
    upper = upper * (1.0 + REL_MARGIN) + ABS_MARGIN_KW_M2
    return float(el), float(upper)


def flux_enclosure_many(boxes, intervals, member, grid, fuel, *, present_fire="enclosure", engulfment=True):
    """Vectorised upper bounds for many (box, interval) pairs; returns (lower[N], upper[N])."""
    ff = _field(member, grid, present_fire)
    fuel = FuelParameters.coerce(fuel)
    B = _boxes(boxes)
    I = np.asarray(intervals, float).reshape(-1, 2)
    up = np.zeros(B.shape[0])
    for s0 in range(0, B.shape[0], 256):
        up[s0:s0 + 256] = _radiation_upper(ff, fuel, B[s0:s0 + 256], I[s0:s0 + 256])
    lo = np.zeros(B.shape[0])
    if engulfment:
        for n in range(B.shape[0]):
            eu, el = _engulf_terms(ff, fuel, B[n], I[n, 0], I[n, 1])
            up[n] = max(up[n], eu); lo[n] = el
    return lo, up * (1.0 + REL_MARGIN) + ABS_MARGIN_KW_M2


# ---- dose, bands, probit ------------------------------------------------------------------------------------------

def dose(q, times_s, form="linear"):
    """Trapezoid dose of samples q[T] (kW/m2) at strictly increasing times_s[T] (s).

    ``linear``: kJ/m2. ``tdu``: thermal dose units, integral of q^(4/3) dt in (kW/m2)^(4/3) s.
    """
    q = np.asarray(q, float)
    t = np.asarray(times_s, float)
    if t.ndim != 1 or t.size < 2 or q.shape[0] != t.size:
        raise ValueError("q and times_s must have the same leading length >= 2")
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise ValueError("times_s must be strictly increasing")
    if np.any(q < 0) or not np.all(np.isfinite(q)):
        raise ValueError("q must be finite and nonnegative")
    if form == "linear":
        f = q
    elif form == "tdu":
        f = q ** PV.TDU_EXPONENT
    else:
        raise ValueError("form must be 'linear' or 'tdu'")
    shape = (dt.size,) + (1,) * (q.ndim - 1)
    return np.sum(0.5 * (f[:-1] + f[1:]) * dt.reshape(shape), axis=0)


def as3959_band(q_kw_m2):
    """AS 3959-2018 bushfire attack level band for a peak radiant flux (kW/m2)."""
    q = float(q_kw_m2)
    for name, limit in PV.AS3959_BANDS_KW_M2:
        if q <= limit:
            return name
    return "BAL-FZ"


def probit_lethality(tdu):
    """Eisenberg lethality probit Pr = -14.9 + 2.56 ln(TDU) (q in kW/m2) and the implied probability."""
    tdu = float(tdu)
    if tdu <= 0:
        return {"probit": -math.inf, "probability": 0.0}
    pr = PV.EISENBERG_PROBIT["a_kw"] + PV.EISENBERG_PROBIT["b"] * math.log(tdu)
    return {"probit": pr, "probability": 0.5 * (1.0 + math.erf((pr - 5.0) / math.sqrt(2.0)))}
