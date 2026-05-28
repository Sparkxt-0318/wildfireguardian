"""Unit tests for the Gaussian-plume smoke dispersion model (Session 3 Tier 2)."""

from __future__ import annotations

import numpy as np
import pytest

from wildfireguardian.smoke_dispersion.gaussian_plume import (
    PlumeConfig,
    StabilityClass,
    estimate_pm25_emission_rate_ug_s,
    gaussian_plume_concentration,
    plume_grid,
    sigma_y_briggs,
    sigma_z_briggs,
)


def _ground_source_cfg() -> PlumeConfig:
    """A ground-level source (H=0) gives clean monotonic downwind decay."""
    return PlumeConfig(
        emission_rate_ug_s=1e8,
        wind_speed_ms=10.0,
        wind_to_bearing_deg=90.0,
        effective_height_m=0.0,
        stability=StabilityClass.D,
    )


# ---------------------------------------------------------------------------
# Dispersion coefficients
# ---------------------------------------------------------------------------


def test_sigma_increases_with_distance() -> None:
    x = np.array([100.0, 1000.0, 10000.0])
    sy = sigma_y_briggs(x, StabilityClass.D)
    sz = sigma_z_briggs(x, StabilityClass.D)
    assert (np.diff(sy) > 0).all()
    assert (np.diff(sz) > 0).all()


def test_unstable_disperses_faster_than_stable() -> None:
    """Class A (unstable) should have larger σ_y than class F (stable)."""
    x = np.array([5000.0])
    assert sigma_y_briggs(x, StabilityClass.A)[0] > sigma_y_briggs(x, StabilityClass.F)[0]


# ---------------------------------------------------------------------------
# Concentration field
# ---------------------------------------------------------------------------


def test_upwind_concentration_is_zero() -> None:
    cfg = _ground_source_cfg()
    c = gaussian_plume_concentration(np.array([-1000.0]), np.array([0.0]), cfg)
    assert c[0] == 0.0


def test_ground_source_decreases_monotonically_downwind() -> None:
    """For a ground-level source, centerline concentration decreases
    monotonically with downwind distance."""
    cfg = _ground_source_cfg()
    xs = np.array([200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0])
    ys = np.zeros_like(xs)
    conc = gaussian_plume_concentration(xs, ys, cfg)
    assert (np.diff(conc) < 0).all(), conc


def test_crosswind_concentration_is_gaussian_peaked_on_axis() -> None:
    """At fixed downwind distance, concentration peaks on the centerline."""
    cfg = _ground_source_cfg()
    x = np.full(5, 2000.0)
    y = np.array([-1000.0, -500.0, 0.0, 500.0, 1000.0])
    conc = gaussian_plume_concentration(x, y, cfg)
    assert conc[2] == conc.max()           # centerline is the max
    assert conc[0] < conc[2] and conc[4] < conc[2]


def test_zero_wind_raises() -> None:
    cfg = PlumeConfig(
        emission_rate_ug_s=1e8, wind_speed_ms=0.0,
        wind_to_bearing_deg=90.0,
    )
    with pytest.raises(ValueError, match="wind_speed_ms must be > 0"):
        gaussian_plume_concentration(np.array([1000.0]), np.array([0.0]), cfg)


# ---------------------------------------------------------------------------
# Mass-conservation sanity (approximate)
# ---------------------------------------------------------------------------


def test_gaussian_plume_invariant_is_conserved_downwind() -> None:
    """The Gaussian-plume invariant C(x,0)·σ_y·σ_z = Q/(2π u) holds at all x.

    This is the correct statement of mass conservation for the basic
    (non-reflecting, H=0) Gaussian plume. The ground-level crosswind
    integral itself scales as 1/σ_z (the plume spreads vertically as well),
    so it is NOT invariant — but the centerline concentration times the
    product of dispersion coefficients is.
    """
    cfg = _ground_source_cfg()
    u = cfg.wind_speed_ms
    Q = cfg.emission_rate_ug_s
    expected_invariant = Q / (2.0 * np.pi * u)

    for x_val in (1000.0, 5000.0, 15000.0):
        c0 = gaussian_plume_concentration(
            np.array([x_val]), np.array([0.0]), cfg,
        )[0]
        sy = sigma_y_briggs(np.array([x_val]), cfg.stability)[0]
        sz = sigma_z_briggs(np.array([x_val]), cfg.stability)[0]
        invariant = c0 * sy * sz
        assert invariant == pytest.approx(expected_invariant, rel=1e-6), (
            f"x={x_val}: invariant={invariant:.3e}, expected={expected_invariant:.3e}"
        )


# ---------------------------------------------------------------------------
# Emission-rate estimator
# ---------------------------------------------------------------------------


def test_emission_rate_scales_with_area() -> None:
    q1 = estimate_pm25_emission_rate_ug_s(100.0)
    q2 = estimate_pm25_emission_rate_ug_s(200.0)
    assert q2 == pytest.approx(2.0 * q1)


def test_emission_rate_positive() -> None:
    assert estimate_pm25_emission_rate_ug_s(500.0) > 0.0


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------


def test_plume_grid_shape_and_orientation() -> None:
    cfg = PlumeConfig(
        emission_rate_ug_s=1e8, wind_speed_ms=10.0,
        wind_to_bearing_deg=90.0,    # blowing east
        effective_height_m=0.0, stability=StabilityClass.D,
    )
    X, Y, C = plume_grid((1_170_000.0, 1_830_000.0), cfg,
                         extent_m=10_000.0, resolution_m=500.0)
    assert X.shape == Y.shape == C.shape
    # Plume blows east → max concentration east of source (positive x offset)
    src_x = 1_170_000.0
    # Find argmax cell
    idx = np.unravel_index(np.argmax(C), C.shape)
    assert X[idx] > src_x, "plume max should be east (downwind) of source"
