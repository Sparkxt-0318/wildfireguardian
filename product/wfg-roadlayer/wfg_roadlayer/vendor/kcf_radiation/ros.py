"""Rate of spread from a fire-arrival-time raster (METHOD.md section 1).

The arrival time t(x) of a front moving at normal speed R satisfies the eikonal equation |grad t| = 1/R
(Osher and Sethian 1988; Sethian 1999, ch. 1; the same relation underlies minimum-travel-time fire growth,
Finney 2002). So R = 1 / |grad t|.

Discretisation: second-order central differences where both neighbours along an axis are finite, one-sided first
differences where only one is, and no estimate along an axis where neither is. Cells whose gradient is zero or
undefined get no estimate (NaN). R is then limited to [r_min, r_max] (PROTOCOL.md section 3); the caller is told how
many cells were limited.
"""
from __future__ import annotations

import numpy as np


def gradient_magnitude(t_s: np.ndarray, cell_m: float) -> np.ndarray:
    """|grad t| (s/m) on a regular grid. Non-finite t is treated as missing."""
    t = np.asarray(t_s, dtype=float)
    fin = np.isfinite(t)
    comps = []
    for axis in (0, 1):
        g = np.full(t.shape, np.nan)
        fwd = np.full(t.shape, np.nan)
        bwd = np.full(t.shape, np.nan)
        sl_c = [slice(None)] * 2
        sl_n = [slice(None)] * 2
        # forward difference t[i+1] - t[i]
        sl_c[axis] = slice(0, -1)
        sl_n[axis] = slice(1, None)
        ok = fin[tuple(sl_c)] & fin[tuple(sl_n)]
        d = np.where(ok, t[tuple(sl_n)] - t[tuple(sl_c)], np.nan)
        fwd[tuple(sl_c)] = d
        bwd[tuple(sl_n)] = d
        both = np.isfinite(fwd) & np.isfinite(bwd)
        g[both] = 0.5 * (fwd[both] + bwd[both])
        only_f = np.isfinite(fwd) & ~np.isfinite(bwd)
        only_b = np.isfinite(bwd) & ~np.isfinite(fwd)
        g[only_f] = fwd[only_f]
        g[only_b] = bwd[only_b]
        comps.append(g / cell_m)
    gy, gx = comps
    have = np.isfinite(gx) | np.isfinite(gy)
    mag = np.sqrt(np.nan_to_num(gx) ** 2 + np.nan_to_num(gy) ** 2)
    mag[~have | ~fin] = np.nan
    return mag


# provenance codes of rate_of_spread_with_source
SRC_GRADIENT, SRC_DONOR, SRC_DEFAULT_CAP, SRC_NONE = 0, 1, 2, 3
DONORS_K = 3


def _donor_rate(R, donor_ok, targets, k):
    """Median R of the k nearest donor cells (centre distance) for each target (row, col); NaN if no donor."""
    dr, dc = np.nonzero(donor_ok)
    out = np.full(len(targets), np.nan)
    if dr.size == 0 or not len(targets):
        return out
    dv = R[dr, dc]
    for i, (r, c) in enumerate(targets):
        d2 = (dr - r) ** 2 + (dc - c) ** 2
        order = np.lexsort((np.arange(d2.size), d2))[:k]   # ties broken by raster order: deterministic
        out[i] = float(np.median(dv[order]))
    return out


def rate_of_spread_with_source(t_s, cell_m, r_min, r_max, known_fire=None, donors_k=DONORS_K):
    """As rate_of_spread, with the PROTOCOL A7 rule and a per-cell provenance array.

    known_fire: boolean grid of cells already burning at issue (arrival exactly 0). Such a cell with a zero or
    undefined gradient does NOT get r_max: it gets the median R of the donors_k nearest cells with a real gradient
    (finite, positive |grad t|), or no rate (NaN, source SRC_NONE) if the input has no such cell. Every other flat or
    undefined cell keeps r_max (SRC_DEFAULT_CAP). known_fire=None gives the old behaviour exactly.
    Returns (R, info, source); source is an int8 grid (SRC_*), -1 where t is not finite."""
    g = gradient_magnitude(t_s, cell_m)
    t = np.asarray(t_s, dtype=float)
    fin = np.isfinite(t)
    with np.errstate(divide="ignore", invalid="ignore"):
        R = 1.0 / g
    real = fin & np.isfinite(R) & (g > 0)
    undefined = fin & ~real
    R = np.where(undefined, r_max, R)
    lo = fin & (R < r_min)
    hi = fin & (R > r_max)
    R = np.clip(R, r_min, r_max)
    R[~fin] = np.nan
    src = np.full(t.shape, -1, dtype=np.int8)
    src[real] = SRC_GRADIENT
    src[undefined] = SRC_DEFAULT_CAP
    info = {"cells": int(fin.sum()), "undefined_set_to_r_max": int(undefined.sum()),
            "raised_to_r_min": int(lo.sum()), "lowered_to_r_max": int((hi & ~undefined).sum())}
    if known_fire is not None:
        kf = np.asarray(known_fire, dtype=bool) & fin
        flat_kf = kf & undefined
        targets = list(zip(*[a.tolist() for a in np.nonzero(flat_kf)]))
        vals = _donor_rate(R, real, targets, donors_k)
        n_none = 0
        for (r, c), v in zip(targets, vals):
            if np.isfinite(v):
                R[r, c] = v
                src[r, c] = SRC_DONOR
            else:
                R[r, c] = np.nan
                src[r, c] = SRC_NONE
                n_none += 1
        info.update({"known_fire_cells": int(kf.sum()), "known_fire_flat": int(flat_kf.sum()),
                     "known_fire_flat_from_donors": int(flat_kf.sum()) - n_none, "known_fire_flat_no_donor": n_none,
                     "undefined_set_to_r_max": int((fin & (src == SRC_DEFAULT_CAP)).sum())})
    return R, info, src


def rate_of_spread(t_s: np.ndarray, cell_m: float, r_min: float, r_max: float):
    """R (m/s) = 1/|grad t|, limited to [r_min, r_max].

    Returns (R, info). R is NaN where t is not finite. Where the gradient is zero or undefined (an isolated burned
    cell, or a flat patch of equal arrival times) R is set to r_max, the conservative choice for intensity
    (PROTOCOL.md section 3); info counts those cells and the limited ones."""
    g = gradient_magnitude(t_s, cell_m)
    fin = np.isfinite(np.asarray(t_s, dtype=float))
    with np.errstate(divide="ignore", invalid="ignore"):
        R = 1.0 / g
    undefined = fin & ~(np.isfinite(R) & (g > 0))
    R = np.where(undefined, r_max, R)
    lo = fin & (R < r_min)
    hi = fin & (R > r_max)
    R = np.clip(R, r_min, r_max)
    R[~fin] = np.nan
    info = {"cells": int(fin.sum()), "undefined_set_to_r_max": int(undefined.sum()),
            "raised_to_r_min": int(lo.sum()), "lowered_to_r_max": int((hi & ~undefined).sum())}
    return R, info
