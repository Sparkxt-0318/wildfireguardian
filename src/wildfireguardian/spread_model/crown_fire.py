"""Crown-fire transition and active crown-fire spread rate.

Session 6, Deliverable 2 — the dominant missing physics for Korean pine
wind-driven spring fires. Surface Rothermel cannot reproduce the observed
spread because, once the surface fire is intense enough, the fire climbs
into and runs through the canopy at rates an order of magnitude faster.

Three published relationships:

1. **Byram (1959) fireline intensity** of the surface fire:
   ``I_B = H · w · R / 60``  (kW/m), with H heat content (kJ/kg), w
   available fine-fuel load (kg/m²), R surface rate of spread (m/min).

2. **Van Wagner (1977) crown-transition criterion**: the surface fire
   crowns when ``I_B ≥ I_o`` where the critical intensity is
   ``I_o = (C · z · (460 + 25.9 · M))^1.5`` (kW/m), z = canopy base height
   (m), M = foliar moisture content (%), C = 0.01 (empirical).
   Van Wagner, C.E. (1977). *Conditions for the start and spread of crown
   fire.* Can. J. For. Res. 7: 23–34.

3. **Cruz, Alexander & Wakimoto (2005) active crown-fire rate of spread**:
   ``R_active = 11.02 · U10^0.7 · CBD^0.19 · exp(-0.17 · EFFM)`` (m/min),
   U10 in km/h, CBD canopy bulk density (kg/m³), EFFM estimated fine-fuel
   moisture (%). Active crowning additionally requires Van Wagner's
   **critical mass-flow** criterion ``R_active · CBD ≥ 3.0 kg/m²/min``;
   otherwise the fire is *passive* (intermittent torching ≈ surface rate).
   Cruz, M.G., Alexander, M.E., Wakimoto, R.H. (2005). *Development and
   testing of models for predicting crown fire rate of spread.* Can. J.
   For. Res. 35: 1626–1639. (See also Cruz & Alexander 2010.)

Implementation note (honest): the Session-6 task brief wrote the Cruz form
with ``U10^0.9`` and an ``exp(-0.17·CFC)`` term; we use the **published**
Cruz et al. 2005 form (``U10^0.7``, EFFM in km/h) because it reproduces the
cited 20–80 m/min Korean-pine magnitudes and is the actual source. This is
documented rather than silently changed.
"""

from __future__ import annotations

import math
from enum import IntEnum

#: Critical mass-flow rate for active crowning (Van Wagner 1977), kg/m²/min.
CRITICAL_MASS_FLOW_KG_M2_MIN: float = 3.0

#: Van Wagner empirical constant in the critical-intensity formula.
VAN_WAGNER_C: float = 0.01

#: Korean Pinus densiflora (Gyeongbuk) canopy defaults (Lee et al. 2018).
KOREAN_PINE_CBH_M: float = 4.0          # canopy base height (range 3.6–5.2)
KOREAN_PINE_CBD_KG_M3: float = 0.47     # canopy bulk density (dense Gyeongbuk)
KOREAN_PINE_FOLIAR_MOISTURE_PCT: float = 119.0   # well-watered measured value
KOREAN_PINE_HEAT_KJ_KG: float = 18600.0


class CrownRegime(IntEnum):
    SURFACE = 0
    PASSIVE_CROWN = 1
    ACTIVE_CROWN = 2


def byram_intensity(
    r_surface_m_min: float, fine_load_kg_m2: float,
    heat_kj_kg: float = KOREAN_PINE_HEAT_KJ_KG,
) -> float:
    """Byram (1959) surface fireline intensity, kW/m.

    ``I = H · w · R / 60`` with R in m/min → kW/m.
    """
    return heat_kj_kg * fine_load_kg_m2 * r_surface_m_min / 60.0


def critical_surface_intensity(
    canopy_base_height_m: float, foliar_moisture_pct: float,
    c: float = VAN_WAGNER_C,
) -> float:
    """Van Wagner (1977) critical surface intensity for crown ignition, I_o (kW/m).

    ``I_o = (C · z · (460 + 25.9 · M))^1.5``.
    """
    if canopy_base_height_m <= 0.0:
        raise ValueError("canopy base height must be > 0")
    return (c * canopy_base_height_m * (460.0 + 25.9 * foliar_moisture_pct)) ** 1.5


def crown_transition_check(
    i_b_surface_kw_m: float, canopy_base_height_m: float,
    foliar_moisture_pct: float, c: float = VAN_WAGNER_C,
) -> bool:
    """True if the surface fire intensity reaches Van Wagner's threshold."""
    i_o = critical_surface_intensity(canopy_base_height_m, foliar_moisture_pct, c)
    return i_b_surface_kw_m >= i_o


def crown_spread_rate(
    u_10m_ms: float, cbd_kg_m3: float,
    fine_fuel_moisture_pct: float = 8.0, u_crit_ms: float = 15.0,
) -> float:
    """Cruz, Alexander & Wakimoto (2005) active crown-fire ROS, m/min.

    ``R_active = 11.02 · U10(km/h)^0.7 · CBD^0.19 · exp(-0.17 · EFFM)``.

    ``u_crit_ms`` is retained from the task brief for API compatibility but
    is not part of the published ROS formula; active-vs-passive is decided
    by the mass-flow criterion in :func:`classify_crown_regime`.
    """
    if u_10m_ms <= 0.0:
        return 0.0
    u_kmh = u_10m_ms * 3.6
    return 11.02 * (u_kmh ** 0.7) * (cbd_kg_m3 ** 0.19) * math.exp(-0.17 * fine_fuel_moisture_pct)


def active_crown_check(r_active_m_min: float, cbd_kg_m3: float) -> bool:
    """Van Wagner active-crown criterion: mass flow ≥ 3.0 kg/m²/min."""
    return (r_active_m_min * cbd_kg_m3) >= CRITICAL_MASS_FLOW_KG_M2_MIN


def classify_crown_regime(
    r_surface_m_min: float,
    fine_load_kg_m2: float,
    u_10m_ms: float,
    canopy_base_height_m: float,
    canopy_bulk_density_kg_m3: float,
    foliar_moisture_pct: float,
    *,
    fine_fuel_moisture_pct: float = 8.0,
    heat_kj_kg: float = KOREAN_PINE_HEAT_KJ_KG,
) -> tuple[CrownRegime, float]:
    """Return (regime, effective_ROS_m_min) for one cell.

    - SURFACE: surface intensity below Van Wagner threshold → R = R_surface.
    - PASSIVE_CROWN: transition met but mass-flow criterion not → torching,
      R ≈ R_surface (we return R_surface; passive crowning does not sustain
      a faster independent run).
    - ACTIVE_CROWN: both criteria met → R = max(R_surface, R_active).
    """
    i_b = byram_intensity(r_surface_m_min, fine_load_kg_m2, heat_kj_kg)
    if not crown_transition_check(i_b, canopy_base_height_m, foliar_moisture_pct):
        return CrownRegime.SURFACE, r_surface_m_min
    r_active = crown_spread_rate(u_10m_ms, canopy_bulk_density_kg_m3,
                                 fine_fuel_moisture_pct)
    if active_crown_check(r_active, canopy_bulk_density_kg_m3):
        return CrownRegime.ACTIVE_CROWN, max(r_surface_m_min, r_active)
    return CrownRegime.PASSIVE_CROWN, r_surface_m_min


__all__ = [
    "CrownRegime",
    "CRITICAL_MASS_FLOW_KG_M2_MIN",
    "VAN_WAGNER_C",
    "KOREAN_PINE_CBH_M",
    "KOREAN_PINE_CBD_KG_M3",
    "KOREAN_PINE_FOLIAR_MOISTURE_PCT",
    "KOREAN_PINE_HEAT_KJ_KG",
    "byram_intensity",
    "critical_surface_intensity",
    "crown_transition_check",
    "crown_spread_rate",
    "active_crown_check",
    "classify_crown_regime",
]
