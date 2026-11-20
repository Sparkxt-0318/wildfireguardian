"""Flame tilt in wind and flame height from flame length (METHOD.md section 4).

Baseline: Albini (1981), "A model for the wind-blown flame from a line fire", Combustion and Flame 43:155-174:
    tan(theta) = 1.22 U / sqrt(g H),    H = L cos(theta)
with theta measured from the vertical, U the wind speed acting on the flame (m/s), H the flame height (m),
g = 9.81 m/s2. The two equations are solved together for theta (fixed point; the map is monotone and converges).

Wind acting on the flame: the forecast gives the 10 m open wind U10. The 6.1 m (20 ft) open wind is U10 / 1.15
(Turner and Lawson 1978, as used by BehavePlus), and the midflame wind is WAF x U_6.1 with the wind adjustment factor
of Albini and Baughman (1979) / Andrews (2012, RMRS-GTR-266): WAF = 0.4 for unsheltered surface fuels (grass,
shrub), 0.2 under a forest canopy for a surface fire (partially sheltered, Andrews 2012 table 2 range 0.1-0.2,
upper end used), and 1.0 (the 6.1 m open wind itself) for a crown fire whose flame stands above the canopy.

Field evidence on wind-tilt correlations is weak: Nelson and Adkins (1986) caution against using their laboratory
tilt correlations in the field, and Weise and Biging (1996) found Froude-number equations underestimate measured flame
angles. The conservative envelope therefore takes the tilt that maximises the view factor (AS 3959-2018 Method 2;
used for wildfire safety distances by Zarate et al. 2008), viewfactor.tilted_max.
"""
from __future__ import annotations

import numpy as np

G = 9.81
U10_TO_U6 = 1.0 / 1.15
WAF_OPEN, WAF_CANOPY, WAF_CROWN = 0.4, 0.2, 1.0


def midflame_wind(u10, sheltered, crown):
    """Midflame wind (m/s) from the 10 m open wind."""
    u6 = np.asarray(u10, dtype=float) * U10_TO_U6
    waf = np.where(np.asarray(crown, dtype=bool), WAF_CROWN, np.where(np.asarray(sheltered, dtype=bool), WAF_CANOPY, WAF_OPEN))
    return waf * u6


def albini_tilt(U, L, iters=60):
    """theta (rad) solving tan(theta) = 1.22 U / sqrt(g L cos(theta)). U, L arrays (m/s, m)."""
    U = np.maximum(np.asarray(U, dtype=float), 0.0)
    L = np.asarray(L, dtype=float)
    th = np.zeros(np.broadcast(U, L).shape)
    ok = L > 0
    for _ in range(iters):
        H = np.where(ok, L * np.cos(th), 1.0)
        th = np.where(ok, np.arctan(1.22 * U / np.sqrt(G * np.maximum(H, 1e-6))), 0.0)
    return th


def flame_tilt(u10, L, I_total=None, *, sheltered=None, crown=None, law="baseline"):
    """Tilt from the 10 m wind. ``sheltered`` / ``crown``: per-cell booleans (default: open, surface)."""
    L = np.asarray(L, dtype=float)
    if law == "vertical":
        return np.zeros(L.shape)
    sh = np.zeros(L.shape, dtype=bool) if sheltered is None else np.asarray(sheltered, dtype=bool)
    cr = np.zeros(L.shape, dtype=bool) if crown is None else np.asarray(crown, dtype=bool)
    return albini_tilt(midflame_wind(u10, sh, cr), L)
