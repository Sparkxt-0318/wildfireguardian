"""Tests for the heuristic topographic wind field (Session 6 D1)."""

from __future__ import annotations

import numpy as np
import pytest

from wildfireguardian.spread_model.topo_wind import (
    TopoWindConfig,
    topographic_wind_field,
)


def _ramp_dem(nrows=40, ncols=40, slope_m_per_m=0.3, axis="east"):
    """A planar ramp rising toward east (or north)."""
    ii, jj = np.meshgrid(np.arange(nrows), np.arange(ncols), indexing="ij")
    cell = 50.0
    if axis == "east":
        z = jj * cell * slope_m_per_m       # rises toward +east (+j)
    else:
        z = (nrows - 1 - ii) * cell * slope_m_per_m  # rises toward +north (-i)
    return z.astype(float), cell


# ---------------------------------------------------------------------------
# Identity on flat terrain
# ---------------------------------------------------------------------------


def test_flat_terrain_is_identity():
    dem = np.full((30, 30), 250.0)
    U, th = topographic_wind_field(8.0, 135.0, dem, 50.0)
    assert np.allclose(U, 8.0)
    assert np.allclose(th, 135.0)


# ---------------------------------------------------------------------------
# Slope acceleration (directional)
# ---------------------------------------------------------------------------


def test_upslope_aligned_wind_speeds_up():
    """Wind blowing upslope (toward east, up an east-rising ramp) → speed-up."""
    dem, cell = _ramp_dem(slope_m_per_m=0.3, axis="east")
    # ramp rises toward +east; blowing toward east (90°) is upslope.
    U, th = topographic_wind_field(10.0, 90.0, dem, cell)
    interior = U[5:-5, 5:-5]
    assert interior.mean() > 10.5, interior.mean()


def test_cross_slope_wind_speeds_up_less_than_aligned():
    """Cross-slope wind gets a much smaller speed-up than aligned wind."""
    dem, cell = _ramp_dem(slope_m_per_m=0.3, axis="east")
    U_aligned, _ = topographic_wind_field(10.0, 90.0, dem, cell)   # upslope (east)
    U_cross, _ = topographic_wind_field(10.0, 0.0, dem, cell)      # cross (north)
    sl = (slice(5, -5), slice(5, -5))
    assert U_aligned[sl].mean() > U_cross[sl].mean()
    # cross-slope speed-up should be tiny (≈ ambient).
    assert U_cross[sl].mean() == pytest.approx(10.0, abs=0.2)


def test_downslope_wind_is_lee_decelerated():
    """Wind blowing downslope (toward west, down an east-rising ramp) → lee
    deceleration below ambient."""
    dem, cell = _ramp_dem(slope_m_per_m=0.3, axis="east")
    U, th = topographic_wind_field(10.0, 270.0, dem, cell)   # toward west = downhill
    interior = U[5:-5, 5:-5]
    assert interior.mean() < 10.0, interior.mean()


# ---------------------------------------------------------------------------
# Physical bounds
# ---------------------------------------------------------------------------


def test_multipliers_stay_in_physical_bounds():
    rng = np.random.default_rng(0)
    dem = np.cumsum(rng.normal(0, 5, (60, 60)), axis=1)  # rough terrain
    dem += np.cumsum(rng.normal(0, 5, (60, 60)), axis=0)
    U, th = topographic_wind_field(12.0, 110.0, dem, 30.0)
    assert U.min() >= 12.0 * 0.4 - 1e-6
    assert U.max() <= 12.0 * 3.0 + 1e-6
    assert (th >= 0).all() and (th < 360).all()


def test_channel_funnelling_accelerates_valley():
    """A V-shaped valley aligned with the wind funnels (accelerates) the flow."""
    n = 60
    ii, jj = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    cell = 50.0
    centre = n / 2.0
    # Valley running east-west (along j): walls rise with |i - centre|.
    dem = (np.abs(ii - centre) * 8.0).astype(float)
    U, th = topographic_wind_field(10.0, 90.0, dem, cell)  # blow east, along valley
    valley_floor = U[int(centre), 5:-5]
    assert valley_floor.mean() > 10.5, valley_floor.mean()


# ---------------------------------------------------------------------------
# Config plumbing
# ---------------------------------------------------------------------------


def test_zero_coefficients_recover_ambient():
    dem, cell = _ramp_dem(slope_m_per_m=0.3)
    cfg = TopoWindConfig(k_slope=0.0, channel_max_gain=1.0, lee_factor=1.0,
                         channel_align=0.0)
    U, th = topographic_wind_field(10.0, 90.0, dem, cell, cfg)
    assert np.allclose(U, 10.0, atol=1e-5)
    assert np.allclose(th, 90.0, atol=1e-5)
