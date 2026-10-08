"""Interpolation core: variogram fit, exponential covariance, local ordinary kriging with per-observation
error variance, and inverse distance weighting.

Units: coordinates in km, time of arrival in hours, variances in h^2.
"""
import numpy as np
from scipy.linalg import solve
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.distance import cdist

N_LAGS = 20
N_NEIGHBOURS = 50
NUGGET_FLOOR_RATIO = 0.001      # lower bound of the nugget as a fraction of the partial sill
RIDGE_RATIO = 1e-4              # diagonal regularisation as a fraction of the partial sill
LARGE_N = 15000                 # above this size the empirical variogram is accumulated in chunks
FIT_TOLERANCE = 1e-15           # termination tolerances of the variogram fit; loose tolerances leave slowly converging fits
                                # dependent on rounding in the input coordinates


def empirical_variogram(x, y, z, n_lags=N_LAGS, chunk=2000):
    """Isotropic empirical semivariogram in `n_lags` equal-width distance bins between the smallest and the
    largest pair distance (the binning of PyKrige). Returns (mean lag, mean semivariance) of the non-empty bins."""
    xy = np.column_stack([np.asarray(x, float), np.asarray(y, float)]); z = np.asarray(z, float); n = len(z)
    if n <= LARGE_N:
        from scipy.spatial.distance import pdist
        d = pdist(xy); g = 0.5 * pdist(z[:, None], metric="sqeuclidean")
        dmin, dmax = np.amin(d), np.amax(d)
        edges = [dmin + k * (dmax - dmin) / n_lags for k in range(n_lags)] + [dmax + 0.001]
        lags, semi = [], []
        for k in range(n_lags):
            sel = (d >= edges[k]) & (d < edges[k + 1])
            if sel.any():
                lags.append(np.mean(d[sel])); semi.append(np.mean(g[sel]))
        return np.array(lags), np.array(semi)
    dmin, dmax = np.inf, -np.inf
    for i in range(0, n, chunk):
        for j in range(i, n, chunk):
            d = cdist(xy[i:i + chunk], xy[j:j + chunk])
            v = d[np.triu_indices(d.shape[0], 1, d.shape[1])] if i == j else d.ravel()
            if v.size:
                dmin, dmax = min(dmin, float(v.min())), max(dmax, float(v.max()))
    edges = np.array([dmin + k * (dmax - dmin) / n_lags for k in range(n_lags)] + [dmax + 0.001])
    cnt, dsum, gsum = np.zeros(n_lags), np.zeros(n_lags), np.zeros(n_lags)
    for i in range(0, n, chunk):
        for j in range(i, n, chunk):
            d = cdist(xy[i:i + chunk], xy[j:j + chunk]); g = 0.5 * (z[i:i + chunk, None] - z[None, j:j + chunk]) ** 2
            if i == j:
                iu = np.triu_indices(d.shape[0], 1, d.shape[1]); d, g = d[iu], g[iu]
            else:
                d, g = d.ravel(), g.ravel()
            if d.size:
                k = np.clip(np.searchsorted(edges, d, side="right") - 1, 0, n_lags - 1)
                cnt += np.bincount(k, minlength=n_lags); dsum += np.bincount(k, weights=d, minlength=n_lags); gsum += np.bincount(k, weights=g, minlength=n_lags)
    ok = cnt > 0
    return dsum[ok] / cnt[ok], gsum[ok] / cnt[ok]


def fit_variogram(x, y, z):
    """Exponential variogram gamma(h) = psill * (1 - exp(-3h/range)) + nugget fitted to the empirical variogram by
    bounded least squares with a soft-L1 loss, iterated to convergence at tight tolerances.
    `range` is the effective range (about 95 % of the sill). Returns (psill, range_km, nugget) with the nugget floor applied."""
    lags, semi = empirical_variogram(x, y, z)

    def residuals(p):
        return p[0] * (1.0 - np.exp(-lags / (p[1] / 3.0))) + p[2] - semi
    x0 = [np.amax(semi) - np.amin(semi), 0.25 * np.amax(lags), np.amin(semi)]
    bounds = ([0.0, 0.0, 0.0], [10.0 * np.amax(semi), np.amax(lags), np.amax(semi)])
    res = least_squares(residuals, x0, bounds=bounds, loss="soft_l1", ftol=FIT_TOLERANCE, xtol=FIT_TOLERANCE, gtol=FIT_TOLERANCE,
                        max_nfev=2000000)
    if not res.success:
        raise RuntimeError(f"variogram fit did not converge (status {res.status})")
    psill, rng, nugget = (float(v) for v in res.x)
    return psill, rng, max(nugget, psill * NUGGET_FLOOR_RATIO)


def covariance(h, psill, rng, nugget):
    """Covariance of the fitted model: psill * exp(-3h/range) for h > 0 and psill + nugget at h = 0."""
    h = np.asarray(h, float)
    return np.where(h == 0, nugget + psill, psill * np.exp(-3.0 * h / rng))


def idw(xd, yd, zd, xp, yp, k=20, power=2):
    """Inverse distance weighting over the k nearest observations."""
    dist, idx = cKDTree(np.column_stack([xd, yd])).query(np.column_stack([xp, yp]), k=min(k, len(xd)))
    if dist.ndim == 1:
        return np.asarray(zd)[idx]
    w = 1.0 / np.maximum(dist, 1e-10) ** power
    return np.sum(w / w.sum(axis=1, keepdims=True) * np.asarray(zd)[idx], axis=1)


def local_kriging(xp, yp, xd, yd, zd, error_variance, params, k=N_NEIGHBOURS):
    """Ordinary kriging at each prediction point from its k nearest observations. `error_variance` (one value per
    observation, 0 for VIIRS cells) is added to the diagonal of the covariance matrix together with the ridge term.
    Returns (prediction, kriging variance)."""
    psill, rng, nugget = params
    xd, yd, zd, ev = (np.asarray(a, float) for a in (xd, yd, zd, error_variance))
    tree = cKDTree(np.column_stack([xd, yd])); k = min(k, len(xd)); ridge = psill * RIDGE_RATIO
    z, var = np.full(len(xp), np.nan), np.full(len(xp), np.nan)
    for i in range(len(xp)):
        _, nb = tree.query([xp[i], yp[i]], k=k)
        nb = np.atleast_1d(nb); n = len(nb)
        if n < 3:
            continue
        pts = np.column_stack([xd[nb], yd[nb]])
        a = np.zeros((n + 1, n + 1))
        a[:n, :n] = covariance(cdist(pts, pts), psill, rng, nugget) + np.diag(ev[nb] + ridge)
        a[:n, n] = 1.0; a[n, :n] = 1.0
        c0 = covariance(np.hypot(xd[nb] - xp[i], yd[nb] - yp[i]), psill, rng, nugget)
        w = solve(a, np.append(c0, 1.0), assume_a="sym")
        z[i] = w[:n] @ zd[nb]
        var[i] = max(psill + nugget - w[:n] @ c0 - w[n], 0.0)
    return z, var
