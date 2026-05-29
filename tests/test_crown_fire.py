"""Tests for crown-fire transition + active crown spread (Session 6 D2)."""

from __future__ import annotations

import pytest

from wildfireguardian.spread_model.crown_fire import (
    CrownRegime,
    active_crown_check,
    byram_intensity,
    classify_crown_regime,
    critical_surface_intensity,
    crown_spread_rate,
    crown_transition_check,
)


# ---------------------------------------------------------------------------
# Van Wagner 1977 critical intensity — reproduce published magnitudes
# ---------------------------------------------------------------------------


def test_van_wagner_canonical_value():
    """Van Wagner's classic example: CBH 6 m, FMC 100% → I_o ≈ 2500 kW/m."""
    i_o = critical_surface_intensity(6.0, 100.0)
    assert i_o == pytest.approx(2476.0, rel=0.02)


def test_van_wagner_korean_pine_well_watered():
    """Korean pine CBH 4 m, FMC 119% → ~1690 kW/m."""
    i_o = critical_surface_intensity(4.0, 119.0)
    assert i_o == pytest.approx(1686.0, rel=0.03)


def test_higher_foliar_moisture_raises_threshold():
    """Wetter foliage is harder to crown (higher I_o)."""
    dry = critical_surface_intensity(4.0, 40.0)
    wet = critical_surface_intensity(4.0, 119.0)
    assert wet > dry


def test_higher_cbh_raises_threshold():
    assert critical_surface_intensity(6.0, 100.0) > critical_surface_intensity(3.0, 100.0)


# ---------------------------------------------------------------------------
# Byram intensity + transition
# ---------------------------------------------------------------------------


def test_byram_intensity_scales():
    i = byram_intensity(r_surface_m_min=3.0, fine_load_kg_m2=0.85, heat_kj_kg=18600.0)
    # 18600 * 0.85 * 3 / 60 = 790.5 kW/m
    assert i == pytest.approx(790.5, rel=1e-3)


def test_transition_triggers_above_threshold_not_below():
    cbh, fmc = 4.0, 40.0   # drought foliage → low threshold (~463 kW/m)
    i_o = critical_surface_intensity(cbh, fmc)
    assert crown_transition_check(i_o + 1.0, cbh, fmc) is True
    assert crown_transition_check(i_o - 1.0, cbh, fmc) is False


# ---------------------------------------------------------------------------
# Cruz/Alexander active crown ROS magnitudes
# ---------------------------------------------------------------------------


def test_crown_spread_rate_in_expected_range():
    """Korean pine at 10 m/s 10-m wind → ~20–80 m/min."""
    r = crown_spread_rate(10.0, cbd_kg_m3=0.47, fine_fuel_moisture_pct=8.0)
    assert 20.0 <= r <= 80.0, r


def test_crown_spread_increases_with_wind():
    assert crown_spread_rate(20.0, 0.47) > crown_spread_rate(5.0, 0.47)


def test_active_crown_requires_mass_flow():
    # Dense CBD easily meets mass flow; very sparse CBD at low wind may not.
    assert active_crown_check(40.0, 0.47) is True
    assert active_crown_check(2.0, 0.05) is False   # 2*0.05=0.1 < 3.0


# ---------------------------------------------------------------------------
# classify_crown_regime end-to-end
# ---------------------------------------------------------------------------


def test_low_surface_intensity_stays_surface():
    """A weak surface fire (low R) under wet foliage does not crown."""
    regime, r = classify_crown_regime(
        r_surface_m_min=1.0, fine_load_kg_m2=0.85, u_10m_ms=13.9,
        canopy_base_height_m=4.0, canopy_bulk_density_kg_m3=0.47,
        foliar_moisture_pct=119.0,
    )
    assert regime is CrownRegime.SURFACE
    assert r == pytest.approx(1.0)


def test_intense_surface_drought_crowns_active():
    """Intense surface fire + drought foliage + strong wind → active crown,
    ROS jumps to the crown rate."""
    regime, r = classify_crown_regime(
        r_surface_m_min=5.0, fine_load_kg_m2=0.85, u_10m_ms=20.0,
        canopy_base_height_m=4.0, canopy_bulk_density_kg_m3=0.47,
        foliar_moisture_pct=40.0,
    )
    assert regime is CrownRegime.ACTIVE_CROWN
    assert r > 20.0   # crown rate, not the 5 m/min surface rate


def test_active_crown_only_when_both_criteria_met():
    """Transition met but sparse canopy fails mass flow → passive, not active."""
    # Force transition (drought, intense surface) but tiny CBD.
    regime, r = classify_crown_regime(
        r_surface_m_min=5.0, fine_load_kg_m2=0.85, u_10m_ms=3.0,
        canopy_base_height_m=4.0, canopy_bulk_density_kg_m3=0.02,
        foliar_moisture_pct=40.0,
    )
    # R_active * 0.02 likely < 3.0 → passive.
    assert regime in (CrownRegime.PASSIVE_CROWN, CrownRegime.SURFACE)
    assert r == pytest.approx(5.0)
