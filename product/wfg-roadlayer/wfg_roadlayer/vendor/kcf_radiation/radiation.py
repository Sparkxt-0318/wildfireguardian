"""Solid-flame radiant flux to a receiver ahead of a fire front, and the safe distance at a flux threshold
(METHOD.md section 5). Units: m, K, kW/m2.

q(d) = tau(d) * E * F(d)

* E = eps * sigma * T_f^4, the flame's emissive power (flame as a grey radiating surface at T_f);
* F(d) = configuration factor from the flame surface to the receiver (viewfactor.py);
* tau(d) = atmospheric transmissivity over the path (Pietersen and Huerta 1985, TNO; or 1 = none).

The safe distance d*(q*) is the smallest distance beyond which q(d) < q*; q is decreasing in d for every geometry
used here (tested), so it is found by bisection.
"""
from __future__ import annotations

import math

from . import viewfactor as vf

SIGMA_KW = 5.670374419e-11  # Stefan-Boltzmann constant, kW m^-2 K^-4 (CODATA 2018)
D_MIN = 0.5  # m; flux is not evaluated closer than this to the flame surface (numerical quadrature limit)


def emissive_power(T_flame_K: float, emissivity: float = 1.0) -> float:
    return emissivity * SIGMA_KW * T_flame_K ** 4


def saturation_vapour_pressure_pa(T_air_C: float) -> float:
    """Alduchov and Eskridge (1996) Magnus form over water: 610.94 exp(17.625 T / (T + 243.04)) Pa."""
    return 610.94 * math.exp(17.625 * T_air_C / (T_air_C + 243.04))


def transmissivity_pietersen(path_m: float, rh_pct: float, T_air_C: float) -> float:
    """Pietersen and Huerta (1985), TNO 'Yellow Book': tau = 2.02 (P_w x)^-0.09, P_w = partial pressure of water
    vapour (Pa), x = path length (m). Stated for 1e4 < P_w x < 1e5 Pa m; outside it the value is clipped to <= 1
    (below the range the formula exceeds 1 at short paths)."""
    pw = max(rh_pct, 0.0) / 100.0 * saturation_vapour_pressure_pa(T_air_C)
    px = max(pw * max(path_m, 1e-6), 1e-9)
    return min(1.0, 2.02 * px ** -0.09)


class Flame:
    """A radiating flame sheet: length L, tilt theta (rad from vertical, toward the receiver), front width W."""

    def __init__(self, L: float, theta: float, W: float):
        self.L, self.theta, self.W = L, theta, W

    @property
    def height(self) -> float:
        return self.L * math.cos(self.theta)


def view_factor(kind: str, d: float, fl: Flame, z_r: float) -> float:
    if kind == "planar":          # vertical sheet of the flame HEIGHT (Butler and Cohen 1998 geometry)
        return vf.planar_mcguire(d, fl.height, fl.W, z_r)
    if kind == "planar_length":   # vertical sheet of the flame LENGTH (upper bound on planar)
        return vf.planar_mcguire(d, fl.L, fl.W, z_r)
    if kind == "tilted":          # sheet tilted by the wind angle
        v = vf.tilted_numeric(d, fl.L, fl.W, fl.theta, z_r)
        return float("inf") if math.isnan(v) else v
    if kind == "tilted_max":      # worst flame angle (AS 3959 Method 2 rule)
        return vf.tilted_max(d, fl.L, fl.W, z_r)[0]
    if kind == "cylinder":        # Mudan (1984) vertical cylinder, D = W, distance from its surface = d
        return vf.cylinder_mudan(d + fl.W / 2.0, fl.W, fl.height)
    raise ValueError(kind)


def flux(d: float, fl: Flame, *, T_flame_K: float, emissivity: float = 1.0, vf_kind: str = "planar",
         z_r: float = 1.5, rh_pct: float | None = None, T_air_C: float | None = None) -> float:
    """Radiant flux (kW/m2) at horizontal distance d from the flame base. Transmissivity is applied when
    rh_pct and T_air_C are given (path = distance to the flame's centre of area), else tau = 1."""
    F = view_factor(vf_kind, d, fl, z_r)
    tau = 1.0
    if rh_pct is not None and T_air_C is not None:
        lean = 0.5 * fl.L * math.sin(fl.theta) if vf_kind == "tilted" else 0.0
        path = math.hypot(d - lean, 0.5 * fl.height - z_r)  # receiver to the flame sheet's centre of area
        tau = transmissivity_pietersen(max(path, 0.1), rh_pct, T_air_C)
    return tau * emissive_power(T_flame_K, emissivity) * min(F, 1.0)


def safe_distance(q_star: float, fl: Flame, *, d_max: float = 5000.0, tol: float = 0.01, **kw) -> float:
    """Smallest d with flux(d) <= q_star (bisection). 0 if the flux at the flame base is already below q_star
    (only possible for very small flames or low T_f)."""
    if fl.L <= 0:
        return 0.0
    lo = D_MIN + (fl.L * math.sin(fl.theta) if kw.get("vf_kind", "planar") == "tilted" else 0.0)
    if flux(lo, fl, **kw) <= q_star:
        return 0.0
    hi = max(4.0 * fl.L, 10.0)
    while flux(hi, fl, **kw) > q_star:
        hi *= 2.0
        if hi > d_max:
            return d_max
    while hi - lo > tol:
        m = 0.5 * (lo + hi)
        if flux(m, fl, **kw) > q_star:
            lo = m
        else:
            hi = m
    return hi
