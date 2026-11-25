"""PROTOCOL_v3 helpers: moving front geometry, crown flame, thermal dose, gas scaling. NumPy only; tested in tests/.

Everything here is a published equation or plain geometry; sources in PROTOCOL_v3.md.
"""
from __future__ import annotations

import numpy as np

# section 4: Thomas (1963) crown flame length, via Rothermel (1991) Table 4: 38,800 kW/m <-> 100 ft
THOMAS_COEF_M = 0.0266                   # L[m] = 0.0266 * I[kW/m]**(2/3)
ROTHERMEL_CROWN_FACTOR = 3.34            # Rothermel (1991); Scott & Reinhardt (2001) eq. 7-8
VAN_WAGNER_MASS_FLOW = 0.05              # R_crit = 0.05 / CBD (kg/m2/s), Scott (2006)
FM10_HEAT_KJ_KG = 18622.32               # Behave/pyrothermel fuel model 10 heat content (Rothermel 1972 standard)
FOLIAR_MOISTURE_PERCENT = 100.0          # pipeline's referenced scenario (NWCG PMS 437)

# section 5: thermal dose (pipeline's PublishedDangerCriteria, CFAST eq. 6.7 / ABCB)
FED_LIMIT = 0.3
FED_WINDOW_MIN = 10                      # our choice (PROTOCOL_v3 5, H2); 30 as sensitivity
RADIANT_THR_KW = {"residents": 2.5, "responders": 7.0}

# section 6: gases. AEGL-2 (final), ppm; Andreae (2019) Table 1 temperate forest, g/kg
AEGL2_PPM = {"co": (420.0, 150.0, 83.0), "acrolein": (0.44, 0.18, 0.10), "hcn": (17.0, 10.0, 7.1)}
CO_AEGL2_MG_M3 = (480.0, 170.0, 95.0)    # NRC (2010) mass values, as the pipeline uses
EF_G_KG = {"co": 113.0, "acrolein": 0.34, "hcn": 0.64}
MOLAR_MASS = {"acrolein": 56.06, "hcn": 27.03}
MOLAR_VOLUME_L = 24.45                   # 25 C, 1 atm
WINDOWS_MIN = (10, 30, 60)


def thomas_flame_length_m(intensity_kw_m):
    return THOMAS_COEF_M * np.power(np.maximum(np.asarray(intensity_kw_m, float), 0.0), 2.0 / 3.0)


def van_wagner_critical_intensity_kw_m(cbh_m, fmc_percent=FOLIAR_MOISTURE_PERCENT):
    return np.power(0.01 * np.asarray(cbh_m, float) * (460.0 + 25.9 * fmc_percent), 1.5)


def gas_limits_mg_m3(gas):
    """AEGL-2 for 10/30/60 min in mg/m3 (CO: the NRC mass values; others ppm * M / 24.45)."""
    if gas == "co":
        return CO_AEGL2_MG_M3
    return tuple(v * MOLAR_MASS[gas] / MOLAR_VOLUME_L for v in AEGL2_PPM[gas])


def gas_from_co(co_mg_m3, gas):
    """The pipeline's plume is linear in the emission factor: gas = CO x EF_gas / EF_CO (same source)."""
    return np.asarray(co_mg_m3) * (EF_G_KG[gas] / EF_G_KG["co"]) if gas != "co" else np.asarray(co_mg_m3)


def fed_rate_per_min(q_kw_m2, gas_temp_c):
    """CFAST eq. 6.7 as the pipeline writes it: 1[q>=2.5] q^1.9/4.2 + max(T,0)^3.61/4.1e8, per minute."""
    q = np.asarray(q_kw_m2, float)
    t = np.maximum(np.asarray(gas_temp_c, float), 0.0)
    return np.where(q >= 2.5, np.power(q, 1.9) / 4.2, 0.0) + np.power(t, 3.61) / 4.1e8


def trailing_sum(x, w, axis=0):
    """Sum over the w bins ending at each bin; NaN where the window would start before the cutoff."""
    x = np.moveaxis(np.asarray(x, float), axis, 0)
    c = np.cumsum(x, axis=0)
    out = np.full(x.shape, np.nan)
    out[w - 1] = c[w - 1]
    out[w:] = c[w:] - c[:-w]
    return np.moveaxis(out, 0, axis)


def first_true(mask, axis=0):
    """Index of the first True along axis as float; +inf where none."""
    m = np.asarray(mask, bool)
    return np.where(m.any(axis=axis), np.argmax(m, axis=axis).astype(float), np.inf)


def cell_square(x0, ytop, res, row, col):
    """Corners of a north-up cell, counter-clockwise from the lower left."""
    xl, xr = x0 + col * res, x0 + (col + 1) * res
    yt, yb = ytop - row * res, ytop - (row + 1) * res
    return np.array([[xl, yb], [xr, yb], [xr, yt], [xl, yt]], float)


def entry_offset_and_depth(corners, d):
    """Projection of the cell on the unit spread direction d: (smallest projection, depth)."""
    pr = corners @ d
    return float(pr.min()), float(pr.max() - pr.min())


def chord(corners, d, s):
    """Segment of the front line {x: d.x = s} inside the convex cell; None if it misses the cell."""
    t = np.array([-d[1], d[0]])
    pts = []
    for i in range(4):
        p, q = corners[i], corners[(i + 1) % 4]
        a, b = p @ d - s, q @ d - s
        if a == 0.0:
            pts.append(p)
        if (a < 0 < b) or (b < 0 < a):
            u = a / (a - b)
            pts.append(p + u * (q - p))
    if len(pts) < 2:
        return None
    pts = np.array(pts)
    proj = pts @ t
    lo, hi = pts[np.argmin(proj)], pts[np.argmax(proj)]
    if np.hypot(*(hi - lo)) <= 1e-6:
        return None
    return lo, hi


def contact_time_s(points, onset_s, d, s_entry, rate_m_s):
    """Time the front reaches each point: onset + (d.p - s_entry) / R."""
    return onset_s + (np.asarray(points, float) @ d - s_entry) / rate_m_s


def seg_distance(px, py, a, b):
    """Horizontal distance from points to the segment a-b."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a
    t = np.clip(((np.asarray(px) - a[0]) * d[0] + (np.asarray(py) - a[1]) * d[1]) / (d @ d), 0., 1.)
    return np.hypot(np.asarray(px) - (a[0] + t * d[0]), np.asarray(py) - (a[1] + t * d[1]))
