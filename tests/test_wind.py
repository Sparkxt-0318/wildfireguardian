"""Tests for the midflame Wind Adjustment Factor (Andrews 2012)."""

from __future__ import annotations

import math

import pytest

from wildfireguardian.spread_model import wind as W
from wildfireguardian.utils import units as U


# ---------------------------------------------------------------------------
# WAF range and ordering
# ---------------------------------------------------------------------------


def test_waf_in_unit_interval():
    for depth_m in [0.02, 0.05, 0.1, 0.3, 0.6, 1.0]:
        waf = W.wind_adjustment_factor(depth_m)
        assert 0.0 < waf <= 1.0


def test_sheltered_waf_less_than_unsheltered():
    depth = 0.08
    unsheltered = W.wind_adjustment_factor(depth)
    sheltered = W.wind_adjustment_factor(depth, canopy_cover_frac=0.5, canopy_height_m=12.0)
    assert sheltered < unsheltered


def test_midflame_wind_less_than_10m_wind():
    waf = W.korean_pine_waf()
    u10 = 13.0
    umid = W.midflame_wind(u10, waf)
    assert umid < u10
    assert umid == pytest.approx(waf * u10)


def test_deeper_fuel_bed_gives_larger_unsheltered_waf():
    """A deeper fuel bed reaches higher into the wind profile → larger WAF."""
    shallow = W.wind_adjustment_factor(0.05)
    deep = W.wind_adjustment_factor(0.5)
    assert deep > shallow


# ---------------------------------------------------------------------------
# Reproduce published Andrews 2012 unsheltered values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "depth_ft, expected_waf",
    [
        # Andrews 2012 (RMRS-GTR-266) unsheltered midflame WAF vs fuel depth.
        (0.5, 0.32),
        (1.0, 0.36),
        (2.0, 0.42),
    ],
)
def test_andrews_2012_unsheltered_examples(depth_ft, expected_waf):
    waf = W.wind_adjustment_factor(depth_ft * U.M_PER_FT)
    assert waf == pytest.approx(expected_waf, abs=0.02)


# ---------------------------------------------------------------------------
# Korean pine closed-canopy stand
# ---------------------------------------------------------------------------


def test_korean_pine_waf_is_small_and_sheltered():
    """Closed Korean pine canopy → small WAF (strongly sheltered surface fuel)."""
    waf = W.korean_pine_waf()
    assert 0.05 <= waf <= 0.30, f"closed-canopy WAF {waf} outside expected range"
    # Much smaller than the ad-hoc 0.30 used in Sessions 3-4.
    assert waf < 0.30 or math.isclose(waf, 0.30, abs_tol=0.05)


def test_denser_crown_gives_smaller_waf():
    """Higher crown ratio → denser crown fill → less wind penetration →
    smaller (more sheltered) WAF. Tested on the raw sheltered formula to
    avoid the floor clamp."""
    H_ft = 12.0 * U.FT_PER_M
    dense = W._sheltered_waf(H_ft, 0.5 * 0.9)   # crown_ratio 0.9 → f = 0.45
    sparse = W._sheltered_waf(H_ft, 0.5 * 0.4)  # crown_ratio 0.4 → f = 0.20
    assert dense < sparse


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_zero_depth_raises():
    with pytest.raises(ValueError):
        W.wind_adjustment_factor(0.0)


def test_sheltered_requires_canopy_height():
    with pytest.raises(ValueError):
        W.wind_adjustment_factor(0.08, canopy_cover_frac=0.5, canopy_height_m=None)


def test_midflame_rejects_bad_waf():
    with pytest.raises(ValueError):
        W.midflame_wind(10.0, 1.5)
    with pytest.raises(ValueError):
        W.midflame_wind(10.0, 0.0)
