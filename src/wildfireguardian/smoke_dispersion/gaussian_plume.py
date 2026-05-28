"""Gaussian plume smoke dispersion — architecture demonstration (Session 3 Tier 2).

Implements the classic Gaussian plume equation (Pasquill-Gifford
dispersion) for a continuous point source, producing a downwind ground-
level PM2.5 concentration field from a fire's emission rate, the wind,
and an atmospheric stability class.

This is an **architecture demonstration**, not validated science. The
emission rate is derived from a simple area × emission-factor model, and
the dispersion coefficients are the standard Pasquill-Gifford curves
(rural). A production smoke model would couple to HYSPLIT or a CMAQ-style
Eulerian solver. We label the output accordingly.

Equations
---------

Ground-level (z=0) concentration from a continuous point source at
effective height H, for a receptor at downwind distance x, crosswind
distance y (Pasquill 1961; Turner 1970):

.. math::

   C(x, y, 0) = \\frac{Q}{2\\pi u\\,\\sigma_y \\sigma_z}
                \\exp\\!\\left(-\\frac{y^2}{2\\sigma_y^2}\\right)
                \\exp\\!\\left(-\\frac{H^2}{2\\sigma_z^2}\\right)

where:

- Q   — emission rate (µg/s)
- u   — wind speed at stack height (m/s)
- σ_y, σ_z — Pasquill-Gifford horizontal/vertical dispersion coefficients
             (m), functions of downwind distance x and stability class.
- H   — effective emission height (m).

References
----------
- Pasquill, F. (1961). *The estimation of the dispersion of windborne
  material.* Meteorol. Mag. 90: 33-49.
- Turner, D.B. (1970). *Workbook of Atmospheric Dispersion Estimates.*
  US EPA AP-26.
- Briggs, G.A. (1973). *Diffusion estimation for small emissions.* ATDL-106.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import numpy as np


class StabilityClass(str, Enum):
    """Pasquill-Gifford atmospheric stability classes A (very unstable) – F (stable)."""

    A = "A"   # very unstable
    B = "B"   # unstable
    C = "C"   # slightly unstable
    D = "D"   # neutral
    E = "E"   # slightly stable
    F = "F"   # stable


# Briggs (1973) rural dispersion-coefficient parameters.
# σ_y = a·x / (1 + b·x)^c ;  σ_z = d·x / (1 + e·x)^f   (x in metres).
# Coefficients from Briggs 1973, as tabulated in Turner 1970 / EPA.
_BRIGGS_RURAL: dict[StabilityClass, dict[str, float]] = {
    # sigma_y: a / (1 + b x)^0.5 form simplified to the Briggs interpolation
    StabilityClass.A: {"ay": 0.22, "by": 0.0001, "az": 0.20, "bz": 0.0},
    StabilityClass.B: {"ay": 0.16, "by": 0.0001, "az": 0.12, "bz": 0.0},
    StabilityClass.C: {"ay": 0.11, "by": 0.0001, "az": 0.08, "bz": 0.0002},
    StabilityClass.D: {"ay": 0.08, "by": 0.0001, "az": 0.06, "bz": 0.0015},
    StabilityClass.E: {"ay": 0.06, "by": 0.0001, "az": 0.03, "bz": 0.0003},
    StabilityClass.F: {"ay": 0.04, "by": 0.0001, "az": 0.016, "bz": 0.0003},
}


def sigma_y_briggs(x_m: np.ndarray, stability: StabilityClass) -> np.ndarray:
    """Horizontal dispersion coefficient σ_y (m) — Briggs 1973 rural."""
    p = _BRIGGS_RURAL[stability]
    x = np.maximum(x_m, 1.0)
    return p["ay"] * x / np.sqrt(1.0 + p["by"] * x)


def sigma_z_briggs(x_m: np.ndarray, stability: StabilityClass) -> np.ndarray:
    """Vertical dispersion coefficient σ_z (m) — Briggs 1973 rural."""
    p = _BRIGGS_RURAL[stability]
    x = np.maximum(x_m, 1.0)
    if p["bz"] > 0.0:
        return p["az"] * x / np.sqrt(1.0 + p["bz"] * x)
    return p["az"] * x


@dataclass
class PlumeConfig:
    """Configuration for one Gaussian-plume snapshot.

    Attributes
    ----------
    emission_rate_ug_s : float
        Source strength Q in micrograms per second of PM2.5.
    wind_speed_ms : float
        Wind speed at emission height (m/s). Must be > 0.
    wind_to_bearing_deg : float
        Direction the wind is blowing TOWARD, compass degrees (0=N, 90=E).
    effective_height_m : float
        Effective emission height H (plume rise + stack), metres.
    stability : StabilityClass
        Pasquill-Gifford stability class.
    """

    emission_rate_ug_s: float
    wind_speed_ms: float
    wind_to_bearing_deg: float
    effective_height_m: float = 50.0
    stability: StabilityClass = StabilityClass.D


def estimate_pm25_emission_rate_ug_s(
    active_fire_area_ha: float,
    emission_factor_g_per_m2_s: float = 3e-5,
) -> float:
    """Estimate a PM2.5 emission rate from active fire area.

    Q = area × emission_factor. The default emission factor (~3e-5
    g/m²/s) is a coarse order-of-magnitude value for smouldering+flaming
    forest fire PM2.5 (Urbanski 2014); a production model would use
    fuel-consumption × EF_PM2.5 per Andreae 2019.

    Returns Q in µg/s.
    """
    area_m2 = active_fire_area_ha * 10_000.0
    q_g_s = area_m2 * emission_factor_g_per_m2_s
    return q_g_s * 1e6   # g → µg


def gaussian_plume_concentration(
    x_downwind_m: np.ndarray,
    y_crosswind_m: np.ndarray,
    cfg: PlumeConfig,
) -> np.ndarray:
    """Ground-level PM2.5 concentration field (µg/m³).

    Parameters
    ----------
    x_downwind_m : np.ndarray
        Downwind distance(s) from source, metres. Concentration is 0 for
        x ≤ 0 (upwind).
    y_crosswind_m : np.ndarray
        Crosswind distance(s), metres. Same shape as ``x_downwind_m``.
    cfg : PlumeConfig

    Returns
    -------
    np.ndarray
        PM2.5 concentration in µg/m³, same shape as inputs.
    """
    if cfg.wind_speed_ms <= 0.0:
        raise ValueError("wind_speed_ms must be > 0 for the Gaussian plume model")
    x = np.asarray(x_downwind_m, dtype=np.float64)
    y = np.asarray(y_crosswind_m, dtype=np.float64)
    conc = np.zeros_like(x)

    downwind = x > 0.0
    if not np.any(downwind):
        return conc

    sy = sigma_y_briggs(x, cfg.stability)
    sz = sigma_z_briggs(x, cfg.stability)

    H = cfg.effective_height_m
    pref = cfg.emission_rate_ug_s / (2.0 * math.pi * cfg.wind_speed_ms * sy * sz)
    exp_y = np.exp(-(y ** 2) / (2.0 * sy ** 2))
    exp_z = np.exp(-(H ** 2) / (2.0 * sz ** 2))
    conc_full = pref * exp_y * exp_z
    conc = np.where(downwind, conc_full, 0.0)
    return conc


def plume_grid(
    source_xy_m: tuple[float, float],
    cfg: PlumeConfig,
    extent_m: float = 30_000.0,
    resolution_m: float = 200.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute a 2-D PM2.5 concentration grid around a source.

    Returns ``(X, Y, C)`` where X, Y are EPSG-frame meshgrids (metres,
    relative to source) and C is the concentration field (µg/m³).

    The grid is rotated so the plume aligns with ``cfg.wind_to_bearing_deg``:
    we compute concentration in a wind-aligned (downwind, crosswind) frame,
    then express on the map grid.
    """
    sx, sy = source_xy_m
    n = int(2 * extent_m / resolution_m) + 1
    coords = np.linspace(-extent_m, extent_m, n)
    XX, YY = np.meshgrid(coords, coords)   # map-frame offsets from source

    # Rotate map offsets into the wind-aligned frame.
    # downwind axis points along wind_to_bearing; compass bearing → math angle.
    theta = math.radians(90.0 - cfg.wind_to_bearing_deg)   # math angle of downwind axis
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    # Downwind = projection onto wind direction; crosswind = perpendicular.
    downwind = XX * cos_t + YY * sin_t
    crosswind = -XX * sin_t + YY * cos_t

    C = gaussian_plume_concentration(downwind, crosswind, cfg)
    # Express grid in absolute EPSG metres.
    return XX + sx, YY + sy, C


__all__ = [
    "StabilityClass",
    "PlumeConfig",
    "sigma_y_briggs",
    "sigma_z_briggs",
    "estimate_pm25_emission_rate_ug_s",
    "gaussian_plume_concentration",
    "plume_grid",
]
