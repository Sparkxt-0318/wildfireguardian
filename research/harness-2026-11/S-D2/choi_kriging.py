"""Re-implementation of the parts of Choi et al. (2026) kriging needed for the block-CV check.

The algorithm and constants follow the published code (Zenodo 10.5281/zenodo.21788344, code/, MIT licence):
``preprocess.cell_summary``, ``toa_kriging.empirical_variogram`` (small-n branch), ``fit_variogram``,
``covariance`` and ``local_kriging``. This module was written for this stream; the downloaded code is not
imported or executed. Units: km, hours, h^2.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.linalg import solve
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist, pdist

CELL_KM = 0.375
N_LAGS = 20
N_NEIGHBOURS = 50
NUGGET_FLOOR_RATIO = 1e-3
RIDGE_RATIO = 1e-4
FIT_TOLERANCE = 1e-15


def cell_summary(x_km, y_km, hours, lon, lat):
    """One observation per 375 m cell: median detection time, location of the earliest detection
    (ties: smaller latitude, then longitude)."""
    d = pd.DataFrame({"x": x_km, "y": y_km, "t": hours, "lon": lon, "lat": lat})
    d["cx"], d["cy"] = np.round(d["x"] / CELL_KM), np.round(d["y"] / CELL_KM)
    d = d.sort_values(["t", "lat", "lon"], kind="stable")
    return d.groupby(["cx", "cy"], as_index=False).agg(x=("x", "first"), y=("y", "first"), t=("t", "median"))[["x", "y", "t"]]


def empirical_variogram(x, y, z, n_lags=N_LAGS):
    """Isotropic semivariogram in equal-width bins between the smallest and largest pair distance."""
    xy = np.column_stack([np.asarray(x, float), np.asarray(y, float)])
    z = np.asarray(z, float)
    d = pdist(xy)
    g = 0.5 * pdist(z[:, None], metric="sqeuclidean")
    dmin, dmax = d.min(), d.max()
    edges = [dmin + k * (dmax - dmin) / n_lags for k in range(n_lags)] + [dmax + 0.001]
    lags, semi = [], []
    for k in range(n_lags):
        sel = (d >= edges[k]) & (d < edges[k + 1])
        if sel.any():
            lags.append(d[sel].mean())
            semi.append(g[sel].mean())
    return np.array(lags), np.array(semi)


def fit_variogram(x, y, z):
    """Exponential model psill*(1-exp(-3h/range)) + nugget, bounded soft-L1 least squares.
    Returns (psill, effective range km, nugget) with the nugget floor applied."""
    lags, semi = empirical_variogram(x, y, z)

    def residuals(p):
        return p[0] * (1.0 - np.exp(-lags / (p[1] / 3.0))) + p[2] - semi

    x0 = [semi.max() - semi.min(), 0.25 * lags.max(), semi.min()]
    bounds = ([0.0, 0.0, 0.0], [10.0 * semi.max(), lags.max(), semi.max()])
    res = least_squares(residuals, x0, bounds=bounds, loss="soft_l1", ftol=FIT_TOLERANCE, xtol=FIT_TOLERANCE,
                        gtol=FIT_TOLERANCE, max_nfev=2_000_000)
    if not res.success:
        raise RuntimeError(f"variogram fit did not converge (status {res.status})")
    psill, rng, nugget = (float(v) for v in res.x)
    return psill, rng, max(nugget, psill * NUGGET_FLOOR_RATIO)


def covariance(h, psill, rng, nugget):
    h = np.asarray(h, float)
    return np.where(h == 0, nugget + psill, psill * np.exp(-3.0 * h / rng))


def local_kriging(xp, yp, xd, yd, zd, error_variance, params, k=N_NEIGHBOURS):
    """Ordinary kriging from the k nearest observations; returns (prediction, kriging variance)."""
    psill, rng, nugget = params
    xd, yd, zd, ev = (np.asarray(v, float) for v in (xd, yd, zd, error_variance))
    tree = cKDTree(np.column_stack([xd, yd]))
    k = min(k, len(xd))
    ridge = psill * RIDGE_RATIO
    z, var = np.full(len(xp), np.nan), np.full(len(xp), np.nan)
    for i in range(len(xp)):
        _, nb = tree.query([xp[i], yp[i]], k=k)
        nb = np.atleast_1d(nb)
        n = len(nb)
        if n < 3:
            continue
        pts = np.column_stack([xd[nb], yd[nb]])
        a = np.zeros((n + 1, n + 1))
        a[:n, :n] = covariance(cdist(pts, pts), psill, rng, nugget) + np.diag(ev[nb] + ridge)
        a[:n, n] = 1.0
        a[n, :n] = 1.0
        c0 = covariance(np.hypot(xd[nb] - xp[i], yd[nb] - yp[i]), psill, rng, nugget)
        w = solve(a, np.append(c0, 1.0), assume_a="sym")
        z[i] = w[:n] @ zd[nb]
        var[i] = max(psill + nugget - w[:n] @ c0 - w[n], 0.0)
    return z, var
