"""Core reach scoring and conformal calibration for kcf-margin (see PROTOCOL.md).

Pure numpy/scipy; geometry I/O lives in the run scripts.
"""
import math

import numpy as np
from scipy import ndimage
from scipy.stats import beta

CELL_KM = 0.375
SEP_KM = 5.0          # PROTOCOL: a new-burn component farther than this from K_t is a separate fire
NEVER = np.iinfo(np.int32).max
EIGHT = np.ones((3, 3), bool)


def arrival_from_stack(rasters):
    """rasters: list of bool arrays (one per hour index 0..T-1). Returns int32 arrival hour index, NEVER if unburned."""
    A = np.full(rasters[0].shape, NEVER, np.int32)
    for k, r in enumerate(rasters):
        A[(A == NEVER) & r] = k
    return A


def dist_km(known):
    """Euclidean distance (km) from every cell centre to the nearest cell centre of `known`."""
    return ndimage.distance_transform_edt(~known) * CELL_KM


def component_reach(known, new, seps_km=(SEP_KM,), dist=None):
    """Reach (km) of `new` cells from `known` under each separation threshold.

    Components of `new` (8-connected) whose nearest cell is > sep km from `known` are separate fires and ignored.
    Returns dict sep -> reach km (0.0 if nothing counts), plus the distance array (km) for `new` cells and the
    boolean mask of new cells that count as spread under the first threshold.
    """
    out = {s: 0.0 for s in seps_km}
    if not new.any() or not known.any():
        return out, np.zeros(0), np.zeros_like(new)
    if dist is None:
        dist = dist_km(known)
    lab, n = ndimage.label(new, structure=EIGHT)
    idx = np.arange(1, n + 1)
    cmin = np.asarray(ndimage.minimum(dist, lab, idx))
    cmax = np.asarray(ndimage.maximum(dist, lab, idx))
    for s in seps_km:
        keep = cmin <= s
        out[s] = float(cmax[keep].max()) if keep.any() else 0.0
    keep0 = np.concatenate([[False], cmin <= seps_km[0]])
    spread_mask = keep0[lab]
    return out, dist[spread_mask], spread_mask


def conformal_R(scores_by_fire, alpha, draws=2000, seed=20261116):
    """Split conformal with one random issue hour per calibration fire, repeated draws.

    scores_by_fire: list of 1-D arrays (one per fire, the fire's eligible hourly scores; empty arrays are skipped).
    Returns (median R over draws, array of R per draw, n fires). R is inf if n is too small for the level.
    """
    arrs = [np.asarray(a, float) for a in scores_by_fire if len(a)]
    n = len(arrs)
    k = math.ceil((n + 1) * (1 - alpha))
    if n == 0 or k > n:
        return math.inf, np.full(draws, math.inf), n
    rng = np.random.default_rng(seed)
    picks = np.stack([a[rng.integers(0, len(a), draws)] for a in arrs], axis=1)  # draws x n
    picks.sort(axis=1)
    Rs = picks[:, k - 1]
    return float(np.median(Rs)), Rs, n


def weighted_quantile_by_fire(values_by_fire, q):
    """Fire-weighted quantile: each fire's values share total weight 1."""
    vals, w = [], []
    for v in values_by_fire:
        v = np.asarray(v, float)
        if v.size:
            vals.append(v)
            w.append(np.full(v.size, 1.0 / v.size))
    if not vals:
        return math.nan
    v = np.concatenate(vals)
    w = np.concatenate(w)
    o = np.argsort(v)
    cw = np.cumsum(w[o]) / w.sum()
    return float(v[o][np.searchsorted(cw, q, side="left")])


def clopper_pearson(k, n, conf=0.95):
    """Exact (Clopper-Pearson) interval; k may be fractional (sum of per-fire miss fractions)."""
    a = (1 - conf) / 2
    lo = 0.0 if k <= 0 else float(beta.ppf(a, k, n - k + 1))
    hi = 1.0 if k >= n else float(beta.ppf(1 - a, k + 1, n - k))
    return lo, hi
