"""Spatial block cross-validation of the five configurations.

VIIRS cells are withheld block by block; geostationary points stay in. The variogram is refitted on the training
VIIRS cells of every fold. Per-event statistics pool the validation pairs of all valid folds.
"""
import numpy as np
from sklearn.model_selection import GroupKFold

from toa_kriging import fit_variogram, idw, local_kriging

GEOSTATIONARY_VARIANCE_FACTOR = 27.4     # (2 km / 0.375 km)^2 - 1
CONFIGURATIONS = ("P-IDW", "PS-IDW", "P-OK", "PS-OK", "PSwt-OK")


def geostationary_variance(nugget, n):
    """Error variance assigned to geostationary points in PSwt-OK: 27.4 * max(nugget, 1 h^2)."""
    return np.full(n, GEOSTATIONARY_VARIANCE_FACTOR * max(nugget, 1.0))


def predict_all(xt, yt, zt, xg, yg, zg, xp, yp, params):
    """Predictions of the five configurations at (xp, yp) from training VIIRS cells (t) and geostationary points (g)."""
    out = {"P-IDW": idw(xt, yt, zt, xp, yp), "P-OK": local_kriging(xp, yp, xt, yt, zt, np.zeros(len(xt)), params)[0]}
    if len(xg) == 0:
        out.update({"PS-IDW": out["P-IDW"].copy(), "PS-OK": out["P-OK"].copy(), "PSwt-OK": out["P-OK"].copy()})
        return out
    x, y, z = np.r_[xt, xg], np.r_[yt, yg], np.r_[zt, zg]
    out["PS-IDW"] = idw(x, y, z, xp, yp)
    out["PS-OK"] = local_kriging(xp, yp, x, y, z, np.zeros(len(x)), params)[0]
    out["PSwt-OK"] = local_kriging(xp, yp, x, y, z, np.r_[np.zeros(len(xt)), geostationary_variance(params[2], len(xg))], params)[0]
    return out


def all_finite(predictions):
    """True when every configuration predicted a finite value at every point."""
    return all(np.isfinite(v).all() for v in predictions.values())


def block_size_km(range_km):
    """Half of the whole-data variogram range, limited to 5-30 km."""
    return min(max(range_km / 2.0, 5.0), 30.0)


def statistics(observed, predicted):
    """Pearson r, mean error and mean absolute error (predicted - observed, hours) of the pooled validation pairs."""
    e = predicted - observed
    return {"n": int(len(e)), "r": float(np.corrcoef(observed, predicted)[0, 1]), "ME_h": float(e.mean()), "MAE_h": float(np.abs(e).mean())}


def cross_validate_us(x, y, z, xg, yg, zg):
    """U.S. design: blocks on the integer grid floor(coordinate / block size); every occupied block is one fold.
    A fold is used only if it has at least 5 training cells, its variogram refit converged, and all five configurations
    predicted finite values. Returns the statistics per configuration and the numbers of folds used and skipped."""
    size = block_size_km(fit_variogram(x, y, z)[1])
    block = np.unique(np.c_[np.floor(x / size), np.floor(y / size)], axis=0, return_inverse=True)[1].ravel()
    obs, pred, used, skipped = [], {c: [] for c in CONFIGURATIONS}, 0, 0
    for b in np.unique(block):
        test = block == b; train = ~test
        if train.sum() < 5:
            skipped += 1; continue
        try:
            params = fit_variogram(x[train], y[train], z[train])
        except RuntimeError:
            skipped += 1; continue
        p = predict_all(x[train], y[train], z[train], xg, yg, zg, x[test], y[test], params)
        if not all_finite(p):
            skipped += 1; continue
        obs.append(z[test]); used += 1
        for c in CONFIGURATIONS:
            pred[c].append(p[c])
    obs = np.concatenate(obs)
    return {c: statistics(obs, np.concatenate(pred[c])) for c in CONFIGURATIONS} | {"folds_used": used, "folds_skipped": skipped}


def cross_validate_kr(x, y, z, xg, yg, zg):
    """Korean design (PSwt-OK): blocks int(coordinate / block size); at most 10 folds of whole blocks (GroupKFold);
    a fold needs at least 20 training and 3 validation cells. The statistics are adopted only if the whole-data range
    is at least 0.5 km, at least 3 blocks are occupied and at least 10 validation pairs were pooled."""
    params = fit_variogram(x, y, z)
    size = block_size_km(params[1])
    block = (x / size).astype(int) * 10000 + (y / size).astype(int)
    n_blocks = len(np.unique(block))
    result = {"range_km": params[1], "block_km": size, "blocks": n_blocks, "statistics": None,
              "status": "evaluation withheld: variogram degeneracy" if params[1] < 0.5 else None}
    if n_blocks < 3:
        result["status"] = result["status"] or "evaluation withheld: insufficient spatial blocks"
        return result
    obs, pred = [], []
    for train, test in GroupKFold(n_splits=min(10, n_blocks)).split(np.c_[x, y], groups=block):
        if len(train) < 20 or len(test) < 3:
            continue
        p = fit_variogram(x[train], y[train], z[train])
        xa, ya, za = np.r_[x[train], xg], np.r_[y[train], yg], np.r_[z[train], zg]
        ev = np.r_[np.zeros(len(train)), geostationary_variance(p[2], len(xg))]
        obs.append(z[test]); pred.append(local_kriging(x[test], y[test], xa, ya, za, ev, p)[0])
    if obs and sum(len(o) for o in obs) >= 10:
        o, p = np.concatenate(obs), np.concatenate(pred)
        if o.std() > 0 and p.std() > 0:                 # a zero variance leaves r undefined; the statistics are then not adopted
            result["statistics"] = statistics(o, p)
        else:
            result["status"] = result["status"] or "evaluation withheld: zero variance of the observations or predictions"
    result["status"] = result["status"] or ("evaluated" if result["statistics"] else "evaluation withheld: fewer than 10 validation pairs")
    return result
