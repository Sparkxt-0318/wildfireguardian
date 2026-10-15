"""Detectors and evaluation helpers for fire signatures in link received-level series.

All series are received level relative to transmit level (RSL - TSL, dB) on a regular grid.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def quantize(x, step):
    return np.round(x / step) * step if step else x


def rolling_baseline(x, dt_s, window_s, gap_s):
    """Median of the past `window_s` seconds, ending `gap_s` before each sample (causal)."""
    n_w = max(int(window_s / dt_s), 1)
    n_g = int(gap_s / dt_s)
    s = pd.Series(x)
    b = s.rolling(n_w, min_periods=max(n_w // 3, 1)).median().shift(n_g)
    return b.to_numpy()


def drop_stat(x, dt_s, base_window_s=3600, gap_s=120, persist=2):
    """Drop below a causal baseline that must persist for `persist` consecutive samples."""
    b = rolling_baseline(x, dt_s, base_window_s, gap_s)
    worst_recent = pd.Series(x).rolling(persist, min_periods=persist).max().to_numpy()
    return b - worst_recent


def var_stat(x, dt_s, win_s=180, base_window_s=6 * 3600, gap_s=600, floor=0.087):
    """Ratio of the short-window std to a causal baseline std (median of past short-window stds)."""
    n = max(int(win_s / dt_s), 3)
    sd = pd.Series(x).rolling(n, min_periods=n).std().to_numpy()
    base = rolling_baseline(sd, dt_s, base_window_s, gap_s)
    return sd / np.maximum(base, floor)


def minmax_15(x, dt_s, q=1.0):
    """15-min minimum and maximum of a fine series, quantized (Netherlands-style logging)."""
    n = int(900 / dt_s)
    m = len(x) // n
    blk = x[: m * n].reshape(m, n)
    with np.errstate(all="ignore"):
        lo, hi = np.nanmin(blk, axis=1), np.nanmax(blk, axis=1)
    return quantize(lo, q), quantize(hi, q)


def minmax_stats(lo, hi, base_n=24):
    """Drop of the 15-min minimum below the median of past minima, and growth of the range."""
    blo = pd.Series(lo).rolling(base_n, min_periods=base_n // 3).median().shift(1).to_numpy()
    rng = hi - lo
    brng = pd.Series(rng).rolling(base_n, min_periods=base_n // 3).median().shift(1).to_numpy()
    return blo - lo, rng - brng


def alarm_onsets(stat, thr, refractory_n):
    """Indices where stat rises above thr, merging onsets closer than refractory_n samples."""
    above = np.nan_to_num(stat, nan=-np.inf) >= thr
    edges = np.nonzero(above & ~np.concatenate([[False], above[:-1]]))[0]
    if len(edges) == 0:
        return edges
    keep = [edges[0]]
    for i in edges[1:]:
        if i - keep[-1] > refractory_n:
            keep.append(i)
    return np.array(keep)


def first_alarm(stat, thr, valid):
    """First index in `valid` mask where stat >= thr, or -1."""
    hit = (np.nan_to_num(stat, nan=-np.inf) >= thr) & valid
    i = np.argmax(hit)
    return int(i) if hit[i] else -1
