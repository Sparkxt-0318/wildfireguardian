"""Tests for the rule-based regime-switching classifier (Session 6 D4)."""

from __future__ import annotations

import pytest

from wildfireguardian.spread_model.crown_fire import CrownRegime
from wildfireguardian.spread_model.regime import (
    RegimeThresholds,
    classify_regime,
)


def test_non_canopy_fuel_is_always_surface():
    d = classify_regime(
        r_surface_m_min=10.0, fine_load_kg_m2=0.85, u_10m_ms=25.0,
        canopy_base_height_m=None, canopy_bulk_density_kg_m3=None,
        foliar_moisture_pct=40.0,
    )
    assert d.regime is CrownRegime.SURFACE
    assert d.effective_ros_m_min == pytest.approx(10.0)
    assert d.spotting_enabled is False


def test_weak_surface_fire_stays_surface():
    d = classify_regime(
        r_surface_m_min=0.5, fine_load_kg_m2=0.85, u_10m_ms=13.9,
        canopy_base_height_m=4.0, canopy_bulk_density_kg_m3=0.47,
        foliar_moisture_pct=119.0,
    )
    assert d.regime is CrownRegime.SURFACE
    assert d.surface_intensity_kw_m < d.critical_intensity_kw_m
    assert d.spotting_enabled is False


def test_intense_drought_fire_goes_active_crown_with_spotting():
    d = classify_regime(
        r_surface_m_min=5.0, fine_load_kg_m2=0.85, u_10m_ms=25.0,
        canopy_base_height_m=4.0, canopy_bulk_density_kg_m3=0.47,
        foliar_moisture_pct=40.0,
    )
    assert d.regime is CrownRegime.ACTIVE_CROWN
    assert d.effective_ros_m_min > 5.0
    assert d.spotting_enabled is True
    assert d.is_crown is True


def test_passive_crown_when_mass_flow_fails():
    """Transition met but sparse canopy → passive crown, no spotting, R≈surface."""
    d = classify_regime(
        r_surface_m_min=5.0, fine_load_kg_m2=0.85, u_10m_ms=3.0,
        canopy_base_height_m=4.0, canopy_bulk_density_kg_m3=0.02,
        foliar_moisture_pct=40.0,
    )
    assert d.regime in (CrownRegime.PASSIVE_CROWN, CrownRegime.SURFACE)
    if d.regime is CrownRegime.PASSIVE_CROWN:
        assert d.effective_ros_m_min == pytest.approx(5.0)
        assert d.spotting_enabled is False


def test_higher_foliar_moisture_makes_crowning_harder():
    """Same fire, wetter foliage → higher critical intensity → less likely crown."""
    kw = dict(r_surface_m_min=3.0, fine_load_kg_m2=0.85, u_10m_ms=20.0,
              canopy_base_height_m=4.0, canopy_bulk_density_kg_m3=0.47)
    dry = classify_regime(foliar_moisture_pct=40.0, **kw)
    wet = classify_regime(foliar_moisture_pct=119.0, **kw)
    assert wet.critical_intensity_kw_m > dry.critical_intensity_kw_m


def test_spotting_gate_thresholds_respected():
    """With spotting_requires_active_crown=False, passive crown enables spotting."""
    th = RegimeThresholds(spotting_requires_active_crown=False)
    d = classify_regime(
        r_surface_m_min=5.0, fine_load_kg_m2=0.85, u_10m_ms=3.0,
        canopy_base_height_m=4.0, canopy_bulk_density_kg_m3=0.02,
        foliar_moisture_pct=40.0, thresholds=th,
    )
    if d.regime is CrownRegime.PASSIVE_CROWN:
        assert d.spotting_enabled is True


def test_decision_matches_underlying_crown_fire_module():
    """The classifier's regime must agree with crown_fire.classify_crown_regime."""
    from wildfireguardian.spread_model.crown_fire import classify_crown_regime
    args = dict(r_surface_m_min=4.0, fine_load_kg_m2=0.85, u_10m_ms=22.0,
                canopy_base_height_m=4.0, canopy_bulk_density_kg_m3=0.47,
                foliar_moisture_pct=40.0)
    reg_direct, ros_direct = classify_crown_regime(**args)
    d = classify_regime(**args)
    assert d.regime is reg_direct
    assert d.effective_ros_m_min == pytest.approx(ros_direct)
