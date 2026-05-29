"""Rule-based fire-regime classifier (Session 6, Deliverable 4).

Selects which physics applies to a cell from its conditions — surface
spread, passive crown (torching), active crown, and whether spotting is
plausible. This is **rule/threshold-based**, exactly how operational tools
(FARSITE, FlamMap, NEXUS) switch regimes — NOT machine learning. An
ML type-conditional predictor is explicitly Round-2 work, deferred until
real Korean fire data exist.

The classifier is a thin, testable wrapper over the already-validated
physics in :mod:`crown_fire` and :mod:`spotting`: it does not introduce new
spread numbers, it just *labels* the regime and reports the effective rate
of spread the cellular automaton should use. Keeping it separate means the
CA's regime logic is independently inspectable and unit-tested against the
underlying Van Wagner / Cruz-Alexander criteria.

Decision logic (per cell, per timestep):

1. Compute Byram surface intensity ``I_B`` from the surface ROS + fine load.
2. **Van Wagner transition**: ``I_B ≥ I_o(CBH, FMC)``?  If not → SURFACE.
3. If transition met, compute Cruz/Alexander active crown ROS and apply the
   **mass-flow criterion** ``R_active·CBD ≥ 3.0``:
   - pass → ACTIVE_CROWN (R = max(R_surface, R_active)); spotting enabled.
   - fail → PASSIVE_CROWN (torching; R ≈ R_surface); spotting unlikely.
4. Non-canopy fuels (no CBH/CBD) can never crown → SURFACE.

References: Van Wagner (1977) CJFR 7; Cruz, Alexander & Wakimoto (2005)
CJFR 35; Scott & Reinhardt (2001) RMRS-RP-29 (regime classification).
"""

from __future__ import annotations

from dataclasses import dataclass

from .crown_fire import (
    CrownRegime,
    active_crown_check,
    byram_intensity,
    critical_surface_intensity,
    crown_spread_rate,
)


@dataclass(frozen=True)
class RegimeDecision:
    """Outcome of classifying one cell's fire regime."""

    regime: CrownRegime
    effective_ros_m_min: float
    surface_intensity_kw_m: float
    critical_intensity_kw_m: float
    crown_ros_m_min: float
    spotting_enabled: bool

    @property
    def is_crown(self) -> bool:
        return self.regime in (CrownRegime.PASSIVE_CROWN, CrownRegime.ACTIVE_CROWN)


@dataclass(frozen=True)
class RegimeThresholds:
    """Tunable thresholds (defaults = the published criteria)."""

    van_wagner_c: float = 0.01
    fine_fuel_moisture_pct: float = 8.0
    #: Spotting only from active crown fires whose flame intensity is high
    #: enough to loft brands; uses the active-crown label as the gate.
    spotting_requires_active_crown: bool = True


def classify_regime(
    *,
    r_surface_m_min: float,
    fine_load_kg_m2: float,
    u_10m_ms: float,
    canopy_base_height_m: float | None,
    canopy_bulk_density_kg_m3: float | None,
    foliar_moisture_pct: float,
    heat_kj_kg: float = 18600.0,
    thresholds: RegimeThresholds | None = None,
) -> RegimeDecision:
    """Classify a cell's regime and return the effective ROS + diagnostics."""
    th = thresholds or RegimeThresholds()
    i_b = byram_intensity(r_surface_m_min, fine_load_kg_m2, heat_kj_kg)

    # Non-canopy fuel → can never crown.
    if canopy_base_height_m is None or canopy_bulk_density_kg_m3 is None:
        return RegimeDecision(
            regime=CrownRegime.SURFACE, effective_ros_m_min=r_surface_m_min,
            surface_intensity_kw_m=i_b, critical_intensity_kw_m=float("inf"),
            crown_ros_m_min=0.0, spotting_enabled=False,
        )

    i_o = critical_surface_intensity(canopy_base_height_m, foliar_moisture_pct,
                                     th.van_wagner_c)
    if i_b < i_o:
        return RegimeDecision(
            regime=CrownRegime.SURFACE, effective_ros_m_min=r_surface_m_min,
            surface_intensity_kw_m=i_b, critical_intensity_kw_m=i_o,
            crown_ros_m_min=0.0, spotting_enabled=False,
        )

    r_active = crown_spread_rate(u_10m_ms, canopy_bulk_density_kg_m3,
                                 th.fine_fuel_moisture_pct)
    if active_crown_check(r_active, canopy_bulk_density_kg_m3):
        return RegimeDecision(
            regime=CrownRegime.ACTIVE_CROWN,
            effective_ros_m_min=max(r_surface_m_min, r_active),
            surface_intensity_kw_m=i_b, critical_intensity_kw_m=i_o,
            crown_ros_m_min=r_active,
            spotting_enabled=True,
        )
    return RegimeDecision(
        regime=CrownRegime.PASSIVE_CROWN, effective_ros_m_min=r_surface_m_min,
        surface_intensity_kw_m=i_b, critical_intensity_kw_m=i_o,
        crown_ros_m_min=r_active,
        spotting_enabled=not th.spotting_requires_active_crown,
    )


__all__ = ["RegimeDecision", "RegimeThresholds", "classify_regime"]
