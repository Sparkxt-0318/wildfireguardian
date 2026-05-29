"""Heuristic topographic wind field for the cellular automaton.

Session 6, Deliverable 1. Replaces the single ambient wind with a
spatially-varying field driven by terrain. This is a deliberately
lightweight heuristic — NOT a mass-consistent CFD solver (WindNinja) — but
it captures the three terrain effects that dominated the March 2025
Yeongdeok 양강지풍 (Föhn) event:

1. **Slope acceleration** — flow speeds up where it blows upslope.
2. **Channel funnelling** — flow accelerates and aligns where terrain
   narrows into a valley along the flow.
3. **Ridge / lee deceleration** — flow slows just downwind of a crest.

All effects are multipliers/rotations on the ambient wind, so on flat
terrain the field is exactly the ambient wind (identity property, tested).

Coefficients (``TopoWindConfig``) cite the empirical literature:

- Slope-acceleration coefficient ``k_slope`` ≈ 0.3–0.5. Korean Föhn
  ("양간지풍 / 양강지풍") downslope-windstorm studies report 10-m wind
  enhancement factors of order 1.3–1.8 over aligned slopes
  (e.g. Lee & Kim 2008, *Atmosphere* (KMS); Jang & Chun 2008). We use 0.4.
- Channel funnelling up to ~2× in deep, narrow, aligned valleys is the
  standard gap-flow / Venturi expectation (Whiteman 2000, *Mountain
  Meteorology*, ch. 11; Wagner et al. 2015).
- Lee-side deceleration to ~0.5–0.7× of ambient in the immediate lee of a
  ridge (Whiteman 2000, ch. 5; separation/eddy zone).

These are order-of-magnitude heuristics; the ablation in
``docs/OVERNIGHT_REPORT_SESSION6.md`` reports what they actually buy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TopoWindConfig:
    """Coefficients for the heuristic topographic wind corrections."""

    k_slope: float = 0.4            # slope-acceleration coefficient (Föhn studies)
    channel_max_gain: float = 2.0   # max funnelling speed multiplier
    lee_factor: float = 0.6         # lee-side speed multiplier (fraction of ambient)
    lee_grad_ref: float = 0.30      # along-wind downhill grad (m/m) for full lee effect
    channel_sigma_k: float = 3.0    # curvature normalised by k·std → [0,1]
    channel_align: float = 0.30     # max direction rotation weight toward valley axis
    min_mult: float = 0.4           # clamp on the total speed multiplier
    max_mult: float = 3.0


def _bearing_to_unit(bearing_deg: np.ndarray | float):
    """Compass 'blowing toward' bearing → (east, north) unit components."""
    r = np.radians(bearing_deg)
    return np.sin(r), np.cos(r)   # east = sin(bearing), north = cos(bearing)


def _circular_blend(a_deg, b_deg, w):
    """Blend two compass bearings by weight ``w`` toward ``b`` (vector mean)."""
    ar, br = np.radians(a_deg), np.radians(b_deg)
    ex = (1 - w) * np.sin(ar) + w * np.sin(br)
    ny = (1 - w) * np.cos(ar) + w * np.cos(br)
    return (np.degrees(np.arctan2(ex, ny)) + 360.0) % 360.0


def topographic_wind_field(
    u_amb_ms: float,
    theta_amb_to_deg: float,
    dem: np.ndarray,
    cell_size_m: float,
    config: TopoWindConfig | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Spatial wind speed + direction field from terrain and an ambient wind.

    Parameters
    ----------
    u_amb_ms : float
        Ambient wind speed (same reference height as you want the field in —
        e.g. 10-m). Multipliers are applied to this.
    theta_amb_to_deg : float
        Ambient wind direction, compass degrees, **blowing toward**.
    dem : np.ndarray
        Elevation (m), shape ``(nrows, ncols)``; ``dem[i, j]`` with ``i``
        increasing southward, ``j`` increasing eastward (FireGrid convention).
    cell_size_m : float
        Grid cell size, metres.
    config : TopoWindConfig | None
        Coefficients; defaults to :class:`TopoWindConfig`.

    Returns
    -------
    (U_field, theta_field) : tuple[np.ndarray, np.ndarray]
        Speed (m/s) and direction (compass, blowing-toward) arrays, same
        shape as ``dem``.
    """
    cfg = config or TopoWindConfig()
    dem = np.asarray(dem, dtype=np.float64)
    nrows, ncols = dem.shape

    # Gradients in geographic (east, north). np.gradient axis 0 = i (south),
    # axis 1 = j (east). i increases southward, so north-gradient = -d/di.
    dz_di, dz_dj = np.gradient(dem, cell_size_m, cell_size_m)
    gx = dz_dj            # ∂z/∂east
    gy = -dz_di           # ∂z/∂north
    grad_mag = np.hypot(gx, gy)
    slope_rad = np.arctan(grad_mag)

    # Wind unit vector (blowing toward).
    wx, wy = _bearing_to_unit(theta_amb_to_deg)

    # ----- (1) slope acceleration -----
    # Upslope component of the wind = wind · (uphill unit). Uphill unit = +grad.
    safe = np.where(grad_mag > 1e-9, grad_mag, 1.0)
    upslope_comp = np.clip((wx * gx + wy * gy) / safe, 0.0, 1.0)
    upslope_comp = np.where(grad_mag > 1e-9, upslope_comp, 0.0)
    mult_slope = 1.0 + cfg.k_slope * np.sin(slope_rad) * upslope_comp

    # ----- (3) ridge / lee deceleration -----
    # Along-wind gradient: positive = climbing (windward), negative = lee.
    g_along = wx * gx + wy * gy
    descent = np.clip(-g_along / cfg.lee_grad_ref, 0.0, 1.0)
    mult_lee = 1.0 - (1.0 - cfg.lee_factor) * descent

    # ----- (2) channel funnelling -----
    # Cross-flow second derivative of elevation; positive ⇒ valley walls rise
    # perpendicular to the flow ⇒ channelling.
    z_xx_di, z_xx_dj = np.gradient(gx, cell_size_m, cell_size_m)  # ∂gx
    z_yy_di, z_yy_dj = np.gradient(gy, cell_size_m, cell_size_m)  # ∂gy
    z_ee = z_xx_dj                  # ∂²z/∂east²
    z_nn = -z_yy_di                 # ∂²z/∂north²  (north = -i)
    z_en = z_xx_di * -1.0           # ∂²z/∂east∂north ≈ -∂gx/∂i
    cx, cy = -wy, wx                # cross-flow unit (perpendicular to wind)
    kappa_c = cx * cx * z_ee + 2.0 * cx * cy * z_en + cy * cy * z_nn
    pos_curv = np.clip(kappa_c, 0.0, None)
    scale = cfg.channel_sigma_k * float(np.std(kappa_c))
    if scale > 1e-12:
        channel_strength = np.clip(pos_curv / scale, 0.0, 1.0)
    else:
        channel_strength = np.zeros_like(kappa_c)   # flat terrain → no channelling
    mult_channel = 1.0 + (cfg.channel_max_gain - 1.0) * channel_strength

    # ----- combine + clamp -----
    mult = mult_slope * mult_lee * mult_channel
    mult = np.clip(mult, cfg.min_mult, cfg.max_mult)
    U_field = (u_amb_ms * mult).astype(np.float32)

    # ----- direction: rotate toward the down-valley axis where channelled -----
    # Down-valley direction ≈ downhill bearing (valid near valley floors).
    downhill_bearing = (np.degrees(np.arctan2(-gx, -gy)) + 360.0) % 360.0
    w_rot = cfg.channel_align * channel_strength
    theta_field = _circular_blend(theta_amb_to_deg, downhill_bearing, w_rot)
    theta_field = theta_field.astype(np.float32)

    return U_field, theta_field


__all__ = ["TopoWindConfig", "topographic_wind_field"]
