"""Share-of-paths blocking rule (PROTOCOL.md Amendment 2 items 2-3). Thresholds only; no model code.

Inputs are the counts written by perpath_export.py: for each criterion, cell and minute, the number of the n retained
paths in which the criterion holds; visibility comes from the v1 hourly share (p_vis, the same 1,024 paths).
Output: minutes from the issue time to the first minute in which the share reaches the level; +inf = never inside the
horizon.
"""
from __future__ import annotations

import numpy as np

LEVELS = ("any", "p10", "p50", "p90")               # fixed before any per-path result (Amendment 2 item 3)
LEVEL_VALUE = {"any": None, "p10": 0.1, "p50": 0.5, "p90": 0.9}
MAIN = "p50"
RADIANT_FOR = {"residents": "radiant_2p5", "responders": "radiant_7p0"}
CO_KEYS = ("co_10", "co_30", "co_60")
AUDIENCES = ("residents", "responders")


def need(level, n):
    """Smallest number of paths that meets the level: share > 0 for 'any', share >= value otherwise."""
    v = LEVEL_VALUE[level]
    return 1 if v is None else int(np.ceil(v * n - 1e-9))


def first_minute(counts, n, level):
    """counts [T, ny, nx] paths holding per minute -> first minute with share at the level (float, inf if never)."""
    hit = np.asarray(counts) >= need(level, n)
    out = np.argmax(hit, axis=0).astype(float)
    return np.where(hit.any(axis=0), out, np.inf)


def vis_first_minute(p_vis, level, n):
    """p_vis [H, ny, nx] hourly share -> start of the first hour with share at the level (v1 counts, same paths)."""
    c = np.rint(np.asarray(p_vis, float) * n)          # p_vis is an exact count / n
    hit = c >= need(level, n)
    out = np.argmax(hit, axis=0).astype(float) * 60.0
    return np.where(hit.any(axis=0), out, np.inf)


def minute_to_hours(first_min, n_hours):
    """[ny, nx] first minute -> [H, ny, nx] bool 'blocked at some time in hour h' (no reopening)."""
    ends = (np.arange(n_hours) + 1.0) * 60.0
    return np.asarray(first_min, float)[None] < ends[:, None, None]


def holds_by_hour(counts, n, level, n_hours):
    """[T, ny, nx] counts -> [H, ny, nx] bool 'share at the level in some minute of hour h' (criterion cell-hours)."""
    hit = np.asarray(counts) >= need(level, n)
    T = hit.shape[0]
    return hit.reshape(n_hours, T // n_hours, *hit.shape[1:]).any(axis=1)


def audience_first_minute(firsts, audience):
    """Earliest of radiant at the audience's threshold, any CO window and visibility."""
    keys = (RADIANT_FOR[audience],) + CO_KEYS + ("vis",)
    return np.min(np.stack([firsts[k] for k in keys]), axis=0)


def wilson(k, n, z=1.959964):
    k, n = np.asarray(k, float), float(n)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h
