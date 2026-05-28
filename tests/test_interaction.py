"""Tests for the honest moisture-wind cross-partial (Session 5).

Replaces tests/test_lfmc_wind_decomposition.py, which asserted the
tautological four-corner ratio.
"""

from __future__ import annotations

import pytest

from wildfireguardian.spread_model import interaction as I


def test_marginal_wind_effect_positive():
    """∂R/∂U > 0: more wind always speeds spread."""
    for dead in (I.DRY_DEAD, I.MOIST_DEAD):
        for u in (0.5, 1.5, 3.0):
            assert I.dR_dU(dead, u) > 0.0


def test_cross_partial_negative():
    """∂²R/∂M∂U < 0: drier fuel ⇒ larger marginal wind effect."""
    cross = I.d2R_dM_dU(0.12, 1.5)
    assert cross < 0.0


def test_drier_fuel_has_larger_wind_slope():
    """The dimensional statement: wind adds more m/min per m/s when drier."""
    dry = I.dR_dU(I.DRY_DEAD, 1.5)
    moist = I.dR_dU(I.MOIST_DEAD, 1.5)
    assert dry > moist


def test_separability_ratio_constant_across_U():
    """The slope ratio ∂R/∂U(dry)/∂R/∂U(moist) is constant in U.

    This is the proof that Rothermel is separable, hence the old
    four-corner ratio carried no information. We assert the ratio varies by
    < 1 % across a wide range of midflame winds.
    """
    pairs = I.separability_slope_ratio_across_U((1.0, 1.5, 2.0, 3.0, 4.0))
    ratios = [r for _, r in pairs]
    assert max(ratios) - min(ratios) < 0.01 * max(ratios), (
        f"ratio not constant across U: {ratios}"
    )


def test_report_structure():
    rep = I.marginal_wind_effect_report(1.5)
    assert rep["dR_dU_dry_m_min_per_ms"] > rep["dR_dU_moist_m_min_per_ms"]
    assert rep["extra_wind_effect_when_dry"] > 0.0
    assert rep["d2R_dM_dU"] < 0.0
    # Dimensional sanity: marginal effects are O(0.1-3) m/min per m/s.
    assert 0.05 < rep["dR_dU_dry_m_min_per_ms"] < 5.0
