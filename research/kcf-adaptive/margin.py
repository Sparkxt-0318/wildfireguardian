"""Arm 2 core: wind-aligned shape, scores, zones, static and adaptive sizes (PROTOCOL.md section 3).

Grid convention: rows increase southward, columns eastward; a vector from cell (r0, c0) to (r1, c1) is
east = (c1 - c0) * cell, north = -(r1 - r0) * cell. Grid north is taken as true north (ASSUMED; the
projections used are within about 2 degrees of it at these fires).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "kcf-margin"))
from reach import CELL_KM, EIGHT, NEVER, component_reach, conformal_R, dist_km  # noqa: E402,F401

KS = (0.25, 0.5, 0.75, 1.0)
LB_CAP = 8.0
EPS = 1e-9


# ------------------------------------------------------------------ shape
def length_to_breadth(u_kmh):
    """Alexander (1985), as in the Canadian FBP system; U = 10 m wind in km/h; capped."""
    u = np.maximum(np.asarray(u_kmh, float), 0.0)
    return np.minimum(1.0 + 8.729 * (1.0 - np.exp(-0.030 * u)) ** 2.155, LB_CAP)


def eccentricity(u_kmh):
    lb = length_to_breadth(u_kmh)
    return np.sqrt(1.0 - 1.0 / lb ** 2)


def g(cos_theta, e, k):
    """Reach per unit size at angle theta from downwind. k = 0 circle, k = 1 rear-focus fire ellipse."""
    return (1.0 - k) + k * (1.0 - e) / (1.0 - e * cos_theta)


def downwind_unit(dir_from_deg):
    """(east, north) unit vector the air moves toward, from the meteorological 'from' direction."""
    b = math.radians((float(dir_from_deg) + 180.0) % 360.0)
    return math.sin(b), math.cos(b)


def mean_wind(speed_kmh, dir_from_deg):
    """Vector-mean wind of a series -> (speed km/h, direction-from deg)."""
    a = np.radians(np.asarray(dir_from_deg, float))
    s = np.asarray(speed_kmh, float)
    u, v = -(s * np.sin(a)).mean(), -(s * np.cos(a)).mean()     # toward (east, north)
    return float(math.hypot(u, v)), float((math.degrees(math.atan2(-u, -v))) % 360.0)


# ------------------------------------------------------------------ scores
def _pairs_min(P, C, d, e, ks, chunk=4_000_000):
    """For each point of P [n, 2] (east, north km): min over C [m, 2] of |x - c| / g, one row per k."""
    out = np.full((len(ks), len(P)), np.inf, np.float64)
    if len(C) == 0 or len(P) == 0:
        return out
    step = max(1, chunk // len(C))
    for s in range(0, len(P), step):
        v = P[s:s + step, None, :] - C[None, :, :]
        dist = np.hypot(v[..., 0], v[..., 1])
        with np.errstate(invalid="ignore", divide="ignore"):
            cos = np.where(dist > 0, (v[..., 0] * d[0] + v[..., 1] * d[1]) / dist, 1.0)
        for i, k in enumerate(ks):
            out[i, s:s + step] = (dist / g(cos, e, k)).min(axis=1)
    return out


def cell_scores(known, cells_rc, d, e, ks=KS, cell=CELL_KM):
    """Directional size needed to reach each cell in `cells_rc` from the known set: [len(ks), n].

    The minimum over all known cells is found on the boundary cells first, then checked against every
    interior cell close enough to matter (|x - c| below the boundary value, since g <= 1), so the result
    is the exact minimum over the whole known set and agrees with the raster zone of `zone`.
    """
    cells_rc = np.asarray(cells_rc)
    if len(cells_rc) == 0:
        return np.zeros((len(ks), 0))
    inner = ndimage.binary_erosion(known, structure=EIGHT, border_value=0)
    brc = np.argwhere(known & ~inner)
    to_xy = lambda rc: np.c_[rc[:, 1] * cell, -rc[:, 0] * cell]  # noqa: E731
    P, B = to_xy(cells_rc), to_xy(brc)
    out = _pairs_min(P, B, d, e, ks)
    irc = np.argwhere(inner)
    if len(irc):
        I = to_xy(irc)
        tree = cKDTree(I)
        radius = out.max(axis=0) * (1 - 1e-12)
        need = np.flatnonzero(tree.query_ball_point(P, radius, return_length=True) > 0)
        for j in need:
            idx = tree.query_ball_point(P[j], radius[j])
            out[:, j] = np.minimum(out[:, j], _pairs_min(P[j:j + 1], I[idx], d, e, ks)[:, 0])
    return out


# ------------------------------------------------------------------ zones
def structuring(q_km, d, e, k, cell=CELL_KM):
    """Boolean offsets within the shape of size q (centre = source cell). Includes the origin."""
    r = int(math.floor(q_km / cell + EPS))
    dr, dc = np.mgrid[-r:r + 1, -r:r + 1]
    east, north = dc * cell, -dr * cell
    dist = np.hypot(east, north)
    with np.errstate(invalid="ignore", divide="ignore"):
        cos = np.where(dist > 0, (east * d[0] + north * d[1]) / dist, 1.0)
    return dist <= q_km * g(cos, e, k) + EPS


def zone(known, q_km, d=(0.0, 1.0), e=0.0, k=0.0, cell=CELL_KM, pad=None):
    """Zone of size q: all cells reached from the known set (known cells included), on a padded grid.

    Returns (zone bool array on the padded grid, pad). The flagged area is zone.sum() - known.sum().
    """
    se = structuring(q_km, d, e, k, cell)
    r = se.shape[0] // 2
    pad = r if pad is None else pad
    if pad < r:
        raise ValueError("pad smaller than the shape radius")
    K = np.pad(known, pad).astype(np.float32)
    if r == 0:
        return K > 0.5, pad
    from scipy.signal import fftconvolve
    return fftconvolve(K, se.astype(np.float32), mode="same") > 0.5, pad


def circle_areas(known, qs_km, cell=CELL_KM):
    """Flagged cells of the circular zone for each size (exact Euclidean rule of kcf-margin)."""
    qs = np.asarray(qs_km, float)
    finite = qs[np.isfinite(qs)]
    pad = int(math.ceil((finite.max() if len(finite) else 0.0) / cell)) + 2
    dist = ndimage.distance_transform_edt(~np.pad(known, pad)) * cell
    dd = np.sort(dist[dist > 0])
    return np.where(np.isfinite(qs), np.searchsorted(dd, qs + EPS, side="right"), np.nan)


# ------------------------------------------------------------------ sizes
class WeightedQuantile:
    """Fire-weighted quantile of pooled hourly scores (each fire's hours share weight 1)."""

    def __init__(self, scores_by_fire):
        vals, w = [], []
        for v in scores_by_fire:
            v = np.asarray(v, float)
            if v.size:
                vals.append(v)
                w.append(np.full(v.size, 1.0 / v.size))
        v, w = np.concatenate(vals), np.concatenate(w)
        o = np.argsort(v, kind="stable")
        self.v = v[o]
        self.cw = np.cumsum(w[o]) / w.sum()
        self.max = float(self.v[-1])

    def __call__(self, level):
        """Size for coverage `level` = 1 - a. Returns (q, saturated)."""
        if level <= 0:
            return 0.0, False
        if level >= 1:
            return self.max, True
        i = min(int(np.searchsorted(self.cw, level, side="left")), len(self.v) - 1)
        return float(self.v[i]), False


def aci(t_idx, scores, h, alpha, gamma, Q, a0=None):
    """Adaptive conformal inference with delayed feedback (PROTOCOL 3.4).

    t_idx: increasing integer issue hours; scores[i] is the realised score of issue hour t_idx[i], which
    becomes known only at t_idx[i] + h. NaN scores (incomplete windows) never feed back.
    Returns q, a (as used at each issue hour), saturated flags.
    """
    n = len(t_idx)
    q, a_used, sat = np.zeros(n), np.zeros(n), np.zeros(n, bool)
    a = alpha if a0 is None else a0
    j = 0                                       # next issue hour whose outcome has not been used
    for i in range(n):
        while j < i and t_idx[j] + h <= t_idx[i]:
            if np.isfinite(scores[j]):
                a += gamma * (alpha - float(scores[j] > q[j]))
            j += 1
        a_used[i] = a
        q[i], sat[i] = Q(1.0 - a)
    return q, a_used, sat


def tracker(t_idx, scores, h, alpha, eta, q0):
    """Unbounded log-size tracker with the same delay: ln q <- ln q + eta (err - alpha)."""
    n = len(t_idx)
    q = np.zeros(n)
    lq = math.log(q0)
    j = 0
    for i in range(n):
        while j < i and t_idx[j] + h <= t_idx[i]:
            if np.isfinite(scores[j]):
                lq += eta * (float(scores[j] > q[j]) - alpha)
            j += 1
        q[i] = math.exp(lq)
    return q
