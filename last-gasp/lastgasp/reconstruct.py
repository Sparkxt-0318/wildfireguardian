"""Arrival-time reconstruction and spot fire detection from node death times.

Baseline: inverse distance weighting (IDW) of delay-corrected death times.

Better: Huygens min-plus reconstruction (an eikonal solution for a
homogeneous anisotropic medium). Every accepted fire death i at corrected
time t_i is treated as a secondary ignition, and
    T_hat(x) = kth-min_i [ t_i + |x - x_i| / R(theta_ix) ] + b,
with R(theta) the elliptical spread rate (head rate, wind direction and
length-to-breadth ratio) fitted to the data by minimising a Huber loss on
causal leave-one-out residuals r_j = t_j - min_{i: t_i < t_j}(t_i + tau_ij).
kth-min is the k-th smallest value (k = huygens_k, default 3), which makes the
field robust to a few early outliers; b is the leave-one-out median residual
(a bias correction).

Spot fire detection: in time order, a death that is earlier than every
earlier death could explain (r_j < -tol) is an unexplained ignition. It is a
spot fire when (1) at least one instrumented node between it and the
would-be explaining node was still alive at that time, and (2) at least
`spot_min_support` later deaths trace back to it and are spatially
progressive (not simultaneous) and are themselves earlier than the rest of
the network can explain (by support_tolerance_min). An unexplained death with no support is an
outlier ('other', e.g. an unrelated outage) and is dropped.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree


def idw(xy_obs, t_obs, xy_q, power=2.0, k=8):
    if len(t_obs) == 0:
        return np.full(len(xy_q), np.nan)
    k = min(k, len(t_obs))
    tree = cKDTree(xy_obs)
    d, j = tree.query(xy_q, k=k)
    if k == 1:
        d, j = d[:, None], j[:, None]
    w = 1.0 / np.maximum(d, 1.0) ** power
    return (w * t_obs[j]).sum(1) / w.sum(1)


def _fac(theta, e):
    return (1.0 - e) / (1.0 - e * np.cos(theta))


def travel_time(xy_src, xy_dst, params):
    """tau[i, j] travel time from src i to dst j under elliptical spread (min)."""
    R, ang, lb = params
    e = math.sqrt(max(0.0, 1.0 - 1.0 / lb ** 2))
    dx = xy_dst[None, :, 0] - xy_src[:, None, 0]
    dy = xy_dst[None, :, 1] - xy_src[:, None, 1]
    d = np.hypot(dx, dy)
    th = np.arctan2(dy, dx) - ang
    return d / (R * _fac(th, e))


def _unpack(z):
    return (math.exp(z[0]), z[1], 1.0 + math.exp(z[2]))


class PairGeometry:
    """Pairwise distances and bearings between observation points (reused across fits)."""

    def __init__(self, xy):
        dx = xy[None, :, 0] - xy[:, None, 0]
        dy = xy[None, :, 1] - xy[:, None, 1]
        self.d = np.hypot(dx, dy)
        self.th = np.arctan2(dy, dx)


def causal_residuals(xy, t, params, active=None, geom=None):
    """r_j = t_j - min_{i active, t_i < t_j} (t_i + tau_ij); also returns the argmin explainer."""
    n = len(t)
    act = np.ones(n, bool) if active is None else active
    geom = geom or PairGeometry(xy)
    R, ang, lb = params
    e = math.sqrt(max(0.0, 1.0 - 1.0 / lb ** 2))
    tau = geom.d * (1.0 - e * np.cos(geom.th - ang)) / (R * (1.0 - e))
    earlier = (t[:, None] < t[None, :]) & act[:, None]
    cand = np.where(earlier, t[:, None] + tau, np.inf)
    j_best = np.argmin(cand, axis=0)
    P = cand[j_best, np.arange(n)]
    return t - P, j_best, P


def fit_spread(xy, t, huber=5.0, starts=4, rng=None, init=None, max_points=700):
    """Fit (R_head m/min, direction rad, LB) by Huber loss on causal residuals."""
    rng = rng or np.random.default_rng(0)
    if len(t) > max_points:
        sel = rng.choice(len(t), size=max_points, replace=False)
        xy, t = xy[sel], t[sel]
    geom = PairGeometry(xy)
    # Initial direction and speed from a least-squares plane fit t ~ a + b x + c y.
    A = np.c_[np.ones(len(t)), xy]
    coef, *_ = np.linalg.lstsq(A, t, rcond=None)
    g = coef[1:]
    gn = np.hypot(*g)
    ang0 = math.atan2(g[1], g[0]) if gn > 0 else 0.0
    R0 = float(np.clip(1.0 / gn if gn > 0 else 30.0, 5.0, 200.0))

    def loss(z):
        if not (-10 < z[2] < 3.0) or not (0.0 < z[0] < math.log(400.0)):
            return 1e12
        r, _, _ = causal_residuals(xy, t, _unpack(z), geom=geom)
        r = r[np.isfinite(r)]
        a = np.abs(r)
        h = np.where(a <= huber, 0.5 * a ** 2, huber * (a - 0.5 * huber))
        return float(h.mean())

    if init is not None:
        inits = [(math.log(init[0]), init[1], math.log(max(init[2] - 1.0, 1e-3)))]
    else:
        inits = [(math.log(R0), ang0, math.log(2.0))]
        for _ in range(starts - 1):
            inits.append((math.log(R0) + rng.normal(0, 0.5), ang0 + rng.normal(0, 0.5), rng.normal(0.5, 0.8)))
    best = None
    for z0 in inits:
        res = minimize(loss, np.array(z0), method="Nelder-Mead",
                       options={"xatol": 1e-3, "fatol": 1e-3, "maxiter": 300})
        if best is None or res.fun < best.fun:
            best = res
    return _unpack(best.x), float(best.fun)


def huygens_field(xy_src, t_src, xy_q, params, k=1, chunk=200):
    """k-th smallest of t_i + tau(x_i -> x) over sources (k=1 is the plain min-plus field)."""
    k = max(1, min(k, len(t_src)))
    best = np.full((k, len(xy_q)), np.inf)
    for s in range(0, len(t_src), chunk):
        cand = t_src[s:s + chunk, None] + travel_time(xy_src[s:s + chunk], xy_q, params)
        both = np.vstack([best, cand])
        best = np.partition(both, k - 1, axis=0)[:k] if both.shape[0] > k else both
    return np.sort(best, axis=0)[k - 1]


def loo_kth(xy, t, params, k):
    """Leave-one-out k-th smallest t_i + tau_ij over i != j, at every observation point."""
    tau = travel_time(xy, xy, params)
    C = t[:, None] + tau
    np.fill_diagonal(C, np.inf)
    return np.partition(C, min(k, len(t) - 1) - 1, axis=0)[min(k, len(t) - 1) - 1]


class HuygensCorrected:
    """Huygens k-th field plus an IDW-interpolated leave-one-out residual correction.

    T_hat(x) = H_k(x) + s(x) * IDW(residuals)(x) + (1 - s(x)) * median(residuals),
    s(x) = exp(-(d_min(x) / L)^2) with d_min the distance to the nearest node.
    Near nodes the field follows the data (like IDW); far from nodes it falls
    back to the physics-based Huygens extrapolation with a global bias shift.
    """

    def __init__(self, xy, t, params, k=3, L=200.0, power=2.0, nn=8):
        self.xy, self.t, self.params, self.k, self.L = xy, t, params, k, L
        self.power, self.nn = power, nn
        self.res = t - loo_kth(xy, t, params, k) if len(t) > k else np.zeros(len(t))
        self.bias = float(np.median(self.res)) if len(t) else 0.0
        self.tree = cKDTree(xy)

    def __call__(self, q):
        H = huygens_field(self.xy, self.t, q, self.params, self.k)
        dmin = self.tree.query(q)[0]
        s = np.exp(-(dmin / self.L) ** 2)
        corr = idw(self.xy, self.res, q, self.power, self.nn)
        return H + s * corr + (1 - s) * self.bias

    def loo_error(self):
        """Leave-one-out absolute errors at nodes (residual correction also leaves the node out)."""
        n = len(self.t)
        k = min(self.nn + 1, n)
        d, j = self.tree.query(self.xy, k=k)
        d, j = d[:, 1:], j[:, 1:]
        w = 1.0 / np.maximum(d, 1.0) ** self.power
        corr = (w * self.res[j]).sum(1) / w.sum(1)
        s = np.exp(-(d[:, 0] / self.L) ** 2)
        pred = (self.t - self.res) + s * corr + (1 - s) * self.bias
        return np.abs(pred - self.t)


def idw_loo_error(xy, t, power=2.0, k=8):
    tree = cKDTree(xy)
    kk = min(k + 1, len(t))
    d, j = tree.query(xy, k=kk)
    d, j = d[:, 1:], j[:, 1:]
    w = 1.0 / np.maximum(d, 1.0) ** power
    return np.abs((w * t[j]).sum(1) / w.sum(1) - t)


def loo_bias(xy, t, params, k):
    """Median of t_j minus the k-th smallest t_i + tau_ij over i != j (bias correction)."""
    if len(t) <= k:
        return 0.0
    tau = travel_time(xy, xy, params)
    C = t[:, None] + tau
    np.fill_diagonal(C, np.inf)
    Pk = np.partition(C, k - 1, axis=0)[k - 1]
    r = t - Pk
    return float(np.median(r[np.isfinite(r)]))


def detect_and_reconstruct(xy, t, all_xy, all_status, cfg, window_min, rng=None, grid_partner=None):
    """Full 'better' pipeline on fire-candidate deaths.

    xy, t: fire-candidate positions and delay-corrected times.
    all_xy: positions of every instrumented device; all_status(t0) -> bool array
      'known alive at t0' for every device (used for the survivor check).
    grid_partner(j) -> True if another meter under the same small protective
      device died within the window (a grid signature); such candidates are
      rejected as outliers.
    Returns dict with params, accepted mask, role per candidate, spots, bias.
    """
    c = cfg
    n = len(t)
    role = np.array(["front"] * n, dtype=object)
    if n < 3:
        return {"params": None, "active": np.ones(n, bool), "role": role, "spots": [], "bias": 0.0}
    active = np.ones(n, bool)
    params, _ = fit_spread(xy, t, c["fit_huber_min"], c["fit_starts"], rng)
    tree_all = cKDTree(all_xy)
    geom = PairGeometry(xy)
    for it in range(3):
        r, jb, P = causal_residuals(xy, t, params, active, geom)
        R_, ang_, lb_ = params
        e_ = math.sqrt(max(0.0, 1.0 - 1.0 / lb_ ** 2))
        tau = geom.d * (1.0 - e_ * np.cos(geom.th - ang_)) / (R_ * (1.0 - e_))
        order = np.argsort(t)
        unexplained = (~np.isfinite(r)) | (r < -c["spot_tolerance_min"])
        # Root of each node: follow the explainer chain until an unexplained node.
        root = np.arange(n)
        for j in order:
            if not active[j]:
                continue
            root[j] = j if unexplained[j] else root[jb[j]]
        roles = np.array(["front"] * n, dtype=object)
        spots = []
        changed = False
        for j in order:
            if not active[j] or not unexplained[j]:
                continue
            members = np.where((root == j) & active & (t > t[j] + window_min))[0]
            # Support: later deaths in this node's group that the main front (all other
            # groups) cannot explain either, i.e. they are also early.
            support = 0
            if members.size:
                others = active & (root != j)
                cand_wo = np.where(others[:, None] & (t[:, None] < t[None, members]),
                                   t[:, None] + tau[:, members], np.inf)
                P_wo = cand_wo.min(0)
                support = int(np.sum(t[members] < P_wo - c["support_tolerance_min"]))
            if not np.isfinite(r[j]):
                roles[j] = "first"
                continue
            i_star = jb[j]
            # Survivors between the would-be explainer and this node at time t_j.
            a, b = xy[i_star], xy[j]
            L = float(np.hypot(*(b - a)))
            mid = 0.5 * (a + b)
            near = tree_all.query_ball_point(mid, L / 2 + c["corridor_width_m"])
            alive = all_status(t[j] + c["survivor_margin_min"])
            n_between = 0
            if near and L > 0:
                q = all_xy[near]
                u = (b - a) / L
                s = (q - a) @ u
                perp = np.abs((q - a) @ np.array([-u[1], u[0]]))
                inside = (s > 0.1 * L) & (s < 0.9 * L) & (perp < c["corridor_width_m"] / 2)
                n_between = int(np.sum(alive[np.asarray(near)][inside]))
            if support < c["spot_min_support"] or (grid_partner is not None and grid_partner(j)):
                roles[j] = "outlier"
                active[j] = False
                changed = True
            elif n_between >= 1:
                roles[j] = "spot"
                # Jump distance: to nearest earlier accepted death outside this node's own group.
                prior = np.where(active & (t < t[j]) & (root != j))[0]
                jump = float(np.min(np.hypot(*(xy[prior] - b).T))) if prior.size else float("nan")
                spots.append({"idx": int(j), "x": float(b[0]), "y": float(b[1]), "t": float(t[j]),
                              "support": support, "n_alive_between": n_between, "jump_m": jump,
                              "lead_min": float(-r[j])})
            else:
                roles[j] = "unconfirmed"
        role = roles
        role[~active & (role == "front")] = "outlier"
        if not changed:
            break
        params, _ = fit_spread(xy[active], t[active], c["fit_huber_min"], 1, rng, init=params)
    bias = loo_bias(xy[active], t[active], params, c["huygens_k"])
    return {"params": params, "active": active, "role": role, "spots": spots, "bias": bias}
