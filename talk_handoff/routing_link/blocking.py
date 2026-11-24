"""Exposure fields -> first blocked time per cell (PROTOCOL.md section 3). No model code: thresholds only.

Input contract, one record per forecast hour h = 0 .. H-1 (an ``HourFields``), all arrays on the exposure grid
(rows north-down, the pipeline's own orientation), NaN = not computed:

* ``bin_edges_s``      [K+1] seconds from the start of the hour, 0 .. 3600 (the pipeline's time bins);
* ``q_rad_kw_m2``      [K, ny, nx] binwise weighted incident radiant flux, kW/m2 (eq. 2 of the session summary);
                        may be None, then ``thermal_j_m2`` [ny, nx] (accumulated energy) gives the hourly mean flux
                        E / 3600 s, a LOWER bound on the binwise peak (``radiant_is_lower_bound`` is then True);
* ``thermal_resolved`` [ny, nx] bool, False where some source's heat is unknown (known part is a lower bound);
* ``co_mg_m3``         [K, ny, nx] binwise CO, mg/m3; may be None, then ``co_mean_mg_m3`` [ny, nx] gives the
                        60 min check only (10 and 30 min "not computable");
* ``p_vis``            [ny, nx] sampled probability that visibility <= 10 m during the hour (eq. 4);
* ``pm25_ug_m3``       [ny, nx] hourly mean PM2.5 (reported only).

Output: minutes from the issue time to the start of the first hour in which the criterion holds; +inf = never
inside the horizon; NaN = a cell where no hour was computed.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# PROTOCOL.md section 3 (sources: SOURCES.md). Do not edit after a result.
RADIANT_KW_M2 = {"residents": 2.5, "responders": 7.0}
CO_AEGL2_PPM = {600: 420.0, 1800: 150.0, 3600: 83.0}  # window seconds -> ppm (NRC 2010 vol. 8, final)
MG_M3_PER_PPM = 1.145                                   # the AEGL document's own conversion
VIS_LEVEL_MAIN = 0.5                                    # OUR CHOICE (assumption), with 0.1 and 0.9 as sensitivity
VIS_LEVELS = (0.1, 0.5, 0.9)
AUDIENCES = ("residents", "responders")


@dataclass
class HourFields:
    bin_edges_s: np.ndarray
    p_vis: np.ndarray
    pm25_ug_m3: np.ndarray | None = None
    q_rad_kw_m2: np.ndarray | None = None
    thermal_j_m2: np.ndarray | None = None
    thermal_resolved: np.ndarray | None = None
    co_mg_m3: np.ndarray | None = None
    co_mean_mg_m3: np.ndarray | None = None


def radiant_hourly_max(hf: HourFields):
    """(hourly peak flux kW/m2, is_lower_bound). The known contribution is used where inputs are unresolved."""
    if hf.q_rad_kw_m2 is not None:
        q = np.asarray(hf.q_rad_kw_m2, float)
        return np.where(np.all(np.isnan(q), axis=0), np.nan, np.nanmax(np.where(np.isnan(q), -np.inf, q), axis=0)), False
    if hf.thermal_j_m2 is not None:
        return np.asarray(hf.thermal_j_m2, float) / 3600.0 / 1000.0, True
    raise ValueError("hour has neither binwise radiant flux nor accumulated thermal energy")


def co_series(hours):
    """Concatenate binwise CO (ppm) over hours: (edges_s [N+1] from issue time, values [N, ny, nx]) or None."""
    if any(h.co_mg_m3 is None for h in hours):
        return None
    edges, vals = [0.0], []
    for k, h in enumerate(hours):
        e = np.asarray(h.bin_edges_s, float)
        if abs(e[0]) > 1e-9 or abs(e[-1] - 3600.0) > 1e-6 or np.any(np.diff(e) <= 0):
            raise ValueError("hour %d: bin edges must run from 0 to 3600 s, increasing" % k)
        edges.extend((3600.0 * k + e[1:]).tolist())
        vals.append(np.asarray(h.co_mg_m3, float) / MG_M3_PER_PPM)
    return np.array(edges), np.concatenate(vals, axis=0)


def max_window_mean_by_hour(edges, vals, w, n_hours):
    """Largest mean over any window [t - w, t] inside [0, end], grouped by the hour in which the window ends.

    The series is piecewise constant, so the largest window mean is attained with t or t - w on a bin edge; both
    families of candidate end points are evaluated exactly. Returns [n_hours, ny, nx]; -inf where no window fits."""
    bad = np.isnan(vals)
    v0 = np.where(bad, 0.0, vals)
    dt = np.diff(edges)[:, None, None]
    z = np.zeros((1,) + vals.shape[1:])
    cum = np.concatenate([z, np.cumsum(v0 * dt, axis=0)])
    nbad = np.concatenate([z, np.cumsum(bad * dt, axis=0)])

    def at(c, src, t):  # integral of src from 0 to t, src piecewise constant on the bins
        i = int(np.clip(np.searchsorted(edges, t, side="right") - 1, 0, len(edges) - 2))
        return c[i] + src[i] * (t - edges[i])

    T = edges[-1]
    cand = sorted({float(t) for t in edges if t >= w - 1e-9} | {float(t + w) for t in edges if t + w <= T + 1e-9})
    out = np.full((n_hours,) + vals.shape[1:], -np.inf)
    for t in cand:
        t = min(t, T)
        if t < w - 1e-9:
            continue
        m = (at(cum, v0, t) - at(cum, v0, t - w)) / w
        miss = (at(nbad, bad, t) - at(nbad, bad, t - w)) > 1e-9
        m = np.where(miss, np.nan, m)  # a window touching an uncomputed bin is not computable
        h = int(np.ceil(t / 3600.0 - 1e-9)) - 1  # a window ending at t counts for the hour it ends in
        hs = {min(max(h, 0), n_hours - 1)}
        if abs(t / 3600.0 - round(t / 3600.0)) < 1e-12 and 0 < round(t / 3600.0) < n_hours:
            hs.add(int(round(t / 3600.0)))  # the supremum over windows ending just after an hour boundary
        for hh in hs:
            out[hh] = np.fmax(out[hh], m)
    return out


def criteria_by_hour(hours):
    """Per criterion, a boolean [H, ny, nx] 'holds in hour h', plus notes. NaN cells give False with computed=False."""
    H = len(hours)
    ny, nx = np.shape(hours[0].p_vis)
    computed = np.stack([np.isfinite(np.asarray(h.p_vis, float)) for h in hours])
    crit, notes = {}, []
    rad = []
    lower = False
    for h in hours:
        q, lb = radiant_hourly_max(h)
        rad.append(q)
        lower |= lb
    rad = np.stack(rad)
    if lower:
        notes.append("radiant: hourly mean flux from accumulated energy (lower bound on the binwise peak)")
    for aud, thr in RADIANT_KW_M2.items():
        crit["radiant_%s" % aud] = np.nan_to_num(rad, nan=-np.inf) >= thr
    unresolved = np.stack([(np.zeros((ny, nx), bool) if h.thermal_resolved is None else ~np.asarray(h.thermal_resolved, bool))
                           for h in hours])
    ser = co_series(hours)
    if ser is not None:
        edges, vals = ser
        for w, lim in CO_AEGL2_PPM.items():
            crit["co_%dmin" % (w // 60)] = np.nan_to_num(max_window_mean_by_hour(edges, vals, w, H), nan=-np.inf) >= lim
    else:
        means = np.stack([np.asarray(h.co_mean_mg_m3, float) / MG_M3_PER_PPM for h in hours])
        crit["co_60min"] = np.nan_to_num(means, nan=-np.inf) >= CO_AEGL2_PPM[3600]
        notes.append("CO: only hourly means saved; 10 and 30 min checks not computable (60 min check only)")
    pv = np.stack([np.asarray(h.p_vis, float) for h in hours])
    for lv in VIS_LEVELS:
        crit["vis_p%02d" % round(lv * 100)] = np.nan_to_num(pv, nan=-np.inf) >= lv
    return crit, computed, unresolved & ~crit["radiant_residents"], notes


def audience_rule(crit, audience, vis_level=VIS_LEVEL_MAIN):
    """Boolean [H, ny, nx]: any of (a) radiant at the audience threshold, (b) any CO window, (c) visibility."""
    m = crit["radiant_%s" % audience] | crit["vis_p%02d" % round(vis_level * 100)]
    for k in crit:
        if k.startswith("co_"):
            m = m | crit[k]
    return m


def first_blocked_minutes(holds, computed):
    """Minutes from issue to the start of the first hour in which ``holds``; +inf if never; NaN if never computed."""
    H = holds.shape[0]
    any_h = holds.any(axis=0)
    first = np.argmax(holds, axis=0).astype(float) * 60.0
    out = np.where(any_h, first, np.inf)
    return np.where(computed.any(axis=0), out, np.nan)


def earlier_of(exposure_min, fire_min):
    """Cellwise earlier of the exposure block and fire arrival; NaN only where both are NaN."""
    a = np.where(np.isnan(exposure_min), np.inf, exposure_min)
    b = np.where(np.isnan(fire_min), np.inf, fire_min)
    out = np.minimum(a, b)
    return np.where(np.isnan(exposure_min) & np.isnan(fire_min), np.nan, out)


def blocked_cell_hours(block_min, n_hours):
    """[H, ny, nx] bool: cell blocked at some point in hour h (block time < end of hour), no reopening."""
    ends = (np.arange(n_hours, dtype=float) + 1.0) * 60.0
    b = np.where(np.isnan(block_min), np.inf, block_min)
    return b[None] < ends[:, None, None]
