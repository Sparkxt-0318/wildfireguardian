#!/usr/bin/env python3
"""Rules, forecast windows and metrics of kcf-aloft (PROTOCOL.md sections 2-4). Pure functions; no outcome is read here.

Every rule is "a level is at or above a threshold". For a series x(v) over the valid hours of the window and a
persistence k, level_k = max over runs of k consecutive valid hours of (min of x over the run). The rule
"x >= thr at k consecutive valid hours" is then exactly level_k >= thr, so one stored number per hour serves every
threshold.
"""
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DELAY_H = 5
WINDOW_H = 8
STEP = 0.25
GUST, U850, V850, HGT850 = range(4)   # field order in fetch_gfs.py
A_CAL = 15.20023                      # m/s; A-cal fires when the window maximum is ABOVE this (PROTOCOL section 3)
RUN_KM = 3.75                         # frozen kcf-margin R(5 h)

# name -> (level column, threshold, strict)
RULES = {
    "G": ("g_k2", 20.0, False),
    "A-cal": ("w_k1", A_CAL, True),
    "A25": ("w_k1", 25.0, False),
    "A30": ("w_k1", 30.0, False),
}
COMBOS = {"A+G": ("A-cal", "G"), "A25+G": ("A25", "G"), "A30+G": ("A30", "G")}
SENS = {
    "G k=1": ("g_k1", 20.0, False), "G k=2 (primary)": ("g_k2", 20.0, False), "G k=3": ("g_k3", 20.0, False),
    "G k=4": ("g_k4", 20.0, False), "G k=6": ("g_k6", 20.0, False),
    "G k=2 same point": ("g_k2sp", 20.0, False), "G k=2, 5 h window": ("g_k2w5", 20.0, False),
    "A-cal k=1 (primary)": ("w_k1", A_CAL, True), "A-cal k=2": ("w_k2", A_CAL, True), "A-cal k=3": ("w_k3", A_CAL, True),
    "A25 k=1 (primary)": ("w_k1", 25.0, False), "A25 k=2": ("w_k2", 25.0, False), "A25 k=3": ("w_k3", 25.0, False),
    "A30 k=1 (primary)": ("w_k1", 30.0, False), "A30 k=2": ("w_k2", 30.0, False), "A30 k=3": ("w_k3", 30.0, False),
}
LEVEL_COLS = ["g_k1", "g_k2", "g_k3", "g_k4", "g_k6", "g_k2sp", "g_k2w5", "w_k1", "w_k2", "w_k3"]


def cycle_of(t):
    """Latest 00/06/12/18 UTC cycle with cycle + 5 h <= t."""
    return (pd.Timestamp(t) - pd.Timedelta(hours=DELAY_H)).floor("6h")


def level(x, k):
    """max over runs of k consecutive entries of the run's minimum; x is 1-D (valid hours). NaN if any NaN."""
    x = np.asarray(x, float)
    if np.isnan(x).any() or x.size < k:
        return math.nan
    return float(max(x[i:i + k].min() for i in range(x.size - k + 1)))


def levels(gust, w850):
    """gust, w850: arrays [8 valid hours, 4 points]. Returns the level columns (LEVEL_COLS)."""
    g = np.asarray(gust, float)
    w = np.asarray(w850, float)
    out = {c: math.nan for c in LEVEL_COLS}
    if not np.isnan(g).any():
        gw = g.max(axis=1)                      # fire-wide: largest of the four points at each valid hour
        for k in (1, 2, 3, 4, 6):
            out[f"g_k{k}"] = level(gw, k)
        out["g_k2sp"] = max(level(g[:, j], 2) for j in range(g.shape[1]))
        out["g_k2w5"] = level(gw[:5], 2)
    if not np.isnan(w).any():
        ww = w.max(axis=1)
        for k in (1, 2, 3):
            out[f"w_k{k}"] = level(ww, k)
    return out


def fires(lv, thr, strict=False):
    """Rule state from a level (array or scalar): True/False, NaN where the level is missing."""
    lv = np.asarray(lv, float)
    s = (lv > thr) if strict else (lv >= thr)
    return np.where(np.isnan(lv), np.nan, s.astype(float))


def either(a, b):
    """State of 'a or b': fires if either fires; unknown only if neither is known to fire and one is missing."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    on = (a == 1) | (b == 1)
    return np.where(on, 1.0, np.where(np.isnan(a) | np.isnan(b), np.nan, 0.0))


class Store:
    """Cycle files written by fetch_gfs.py: arr[lead, field, lat, lon]."""

    def __init__(self, d):
        self.d = Path(d)

    @lru_cache(maxsize=256)
    def load(self, key):
        p = self.d / (key + ".npz")
        if not p.exists():
            return None
        z = np.load(p)
        return z["arr"], z["leads"], z["lat"], z["lon"]

    def window(self, t, lat, lon, step=STEP):
        """Fields at the four lattice points around (lat, lon) for valid hours t+1..t+8 from cycle c(t).
        Returns (array [8, nfield, 4], cycle) or (None, cycle)."""
        t = pd.Timestamp(t)
        c = cycle_of(t)
        z = self.load(c.strftime("%Y%m%d%H"))
        if z is None:
            return None, c
        arr, leads, la, lo = z
        i = int(math.floor((lat - la[0]) / step + 1e-9))
        j = int(math.floor((lon % 360.0 - lo[0]) / step + 1e-9))
        if not (0 <= i < la.size - 1 and 0 <= j < lo.size - 1):
            return None, c
        first = int((t - c) / pd.Timedelta(hours=1)) + 1
        li = [int(np.flatnonzero(leads == L)[0]) if (leads == L).any() else -1 for L in range(first, first + WINDOW_H)]
        if min(li) < 0:
            return None, c
        b = arr[li][:, :, i:i + 2, j:j + 2].astype(np.float64)
        return b.reshape(b.shape[0], b.shape[1], 4), c


def window_levels(store, t, lat, lon):
    """Level columns, plus the 8 h window maxima and the 850 hPa height, for one issue hour at one place."""
    b, c = store.window(t, lat, lon)
    out = {c_: math.nan for c_ in LEVEL_COLS}
    out.update(cycle_utc=str(c), hgt850_m=math.nan)
    if b is None:
        out["fc_note"] = "no_cycle_or_lead"
        return out
    gust = b[:, GUST]
    w = np.hypot(b[:, U850], b[:, V850])
    out.update(levels(gust, w))
    h = b[:, HGT850]
    out["hgt850_m"] = float(np.nanmean(h)) if np.isfinite(h).any() else math.nan
    miss = [n for n, v in (("gust", gust), ("w850", w)) if np.isnan(v).any()]
    out["fc_note"] = ("missing:" + ",".join(miss)) if miss else ""
    return out


# ------------------------------------------------------------------ metrics on one fire's hourly timeline
def lead_hours(state, i1, cap=24, floor_i=0):
    """Hours immediately before index i1 through which state == 1 without a break (state[i1] must be 1).
    Stops at a 0 or a NaN, at `cap`, and never goes below index floor_i."""
    if not state[i1] == 1:
        return None
    L = 0
    i = i1 - 1
    while i >= floor_i and L < cap and state[i] == 1:
        L += 1
        i -= 1
    return L


def fire_metrics(tl, state, lapsed_h=12):
    """tl: one fire's timeline, hourly and gap-free, sorted, columns t_utc, kst_day, issue (bool: has a 5 h reach),
    run (bool), pre (bool: before the first issue hour). state: rule state per row (1, 0, NaN).
    Returns per-fire-day rows."""
    state = np.asarray(state, float)
    first_issue = int(np.flatnonzero(tl.issue.values)[0])
    rows = []
    for day, g in tl[tl.issue].groupby("kst_day", sort=True):
        idx = g.index.values                      # positions in tl (tl has a RangeIndex)
        runs = idx[g.run.values]
        r = dict(kst_day=day, issue_hours=len(idx), run_hours=len(runs))
        if len(runs):
            i1 = int(runs[0])
            r.update(first_run_utc=str(tl.t_utc.iloc[i1]), first_run_kst_hour=int(tl.kst_hour.iloc[i1]),
                     warned=bool(state[i1] == 1), state_known=bool(not np.isnan(state[i1])),
                     lead_h=lead_hours(state, i1), lead_h_since_ignition=lead_hours(state, i1, floor_i=first_issue),
                     warned_lapsed=bool(np.nansum(state[max(0, i1 - lapsed_h):i1 + 1]) > 0),
                     run_hours_missed=int(np.sum(state[runs] != 1)),
                     run_hours_unknown=int(np.sum(np.isnan(state[runs]))))
        else:
            r.update(alarm_no_run=bool(np.nansum(state[idx]) > 0), alarm_hours=int(np.nansum(state[idx])))
        rows.append(r)
    return rows


# ------------------------------------------------------------------ exact intervals
def clopper_pearson(k, n, conf=0.95):
    if n == 0:
        return (math.nan, math.nan)
    a = 1 - conf
    lo = 0.0 if k == 0 else float(stats.beta.ppf(a / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1 - a / 2, k + 1, n - k))
    return (lo, hi)


def garwood(k, conf=0.95):
    """Exact Poisson interval for a count k."""
    a = 1 - conf
    lo = 0.0 if k == 0 else float(stats.chi2.ppf(a / 2, 2 * k) / 2)
    hi = float(stats.chi2.ppf(1 - a / 2, 2 * k + 2) / 2)
    return (lo, hi)


def sign_test(b, c):
    """Exact two-sided sign test for discordant counts b and c."""
    n = b + c
    if n == 0:
        return 1.0
    return float(min(1.0, 2 * stats.binom.cdf(min(b, c), n, 0.5)))
