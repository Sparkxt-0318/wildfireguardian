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
