"""Independent integration, high-precision and contract checks for hazard timing."""

from decimal import Decimal, localcontext

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal
from scipy.integrate import quad

from wildfire.heat import BurningOccupancy, initial_active_occupancy
from wildfire.heat_timing import (
    constant_hazard_occupancy,
    constant_hazard_unknown_occupancy_upper,
    infer_ignition_rate,
)


@pytest.mark.parametrize("hazard_exposure", [0.01, 0.5, 5.0, 100.0])
@pytest.mark.parametrize("duration_ratio", [0.003, 0.25, 0.8, 1.0, 2.0])
def test_occupancy_matches_independent_arrival_density_quadrature(hazard_exposure, duration_ratio):
    interval = 3600.0
    duration = interval * duration_ratio
    rate = hazard_exposure / interval
    result = constant_hazard_occupancy([[rate]], duration, interval)
    # Integrate individual arrivals' overlap with the forecast interval against
    # the unconditional first-arrival density, including the no-arrival mass.
    mean = quad(
        lambda arrival: rate * np.exp(-rate * arrival) * min(duration, interval - arrival) / interval,
        0.0, interval, points=[max(interval - duration, 0.0)], epsabs=1e-13, epsrel=1e-12,
    )[0]
    endpoint = quad(
        lambda arrival: rate * np.exp(-rate * arrival), max(interval - duration, 0.0), interval,
        epsabs=1e-13, epsrel=1e-12,
    )[0]
    assert_allclose(result.mean_active_probability, [[mean]], rtol=2e-12, atol=1e-14)
    assert_allclose(result.endpoint_active_probability, [[endpoint]], rtol=2e-12, atol=1e-14)


def test_stable_occupancies_match_high_precision_independent_integrals():
    for exposure in ("1e-15", "1e-8", "1e-4", "0.1", "1", "10", "100", "1e4"):
        for fraction in ("1e-12", "0.003", "0.1", "0.9", "1"):
            with localcontext() as context:
                context.prec = 100
                x, r = Decimal(exposure), Decimal(fraction)
                endpoint = (-x * (1 - r)).exp() - (-x).exp()
                mean = r - endpoint / x
            result = constant_hazard_occupancy(float(x), float(r), 1.0)
            assert_allclose(result.mean_active_probability, float(mean), rtol=5e-14, atol=0)
            assert_allclose(result.endpoint_active_probability, float(endpoint), rtol=5e-14, atol=0)


def test_zero_rate_and_scalar_or_exact_cell_specific_duration():
    rates = np.array([[0.0, 0.005], [0.02, 0.01]])
    durations = np.array([[600.0, 300.0], [3600.0, 7200.0]])
    result = constant_hazard_occupancy(rates, durations, 3600.0)
    assert isinstance(result, BurningOccupancy)
    assert result.mean_active_probability.shape == rates.shape
    assert result.endpoint_active_probability.shape == rates.shape
    assert result.mean_active_probability[0, 0] == 0
    assert result.endpoint_active_probability[0, 0] == 0
    assert not result.mean_active_probability.flags.writeable
    assert not result.endpoint_active_probability.flags.writeable
    for index in np.ndindex(rates.shape):
        scalar = constant_hazard_occupancy(rates[index], durations[index], 3600.0)
        assert_allclose(result.mean_active_probability[index], scalar.mean_active_probability)
        assert_allclose(result.endpoint_active_probability[index], scalar.endpoint_active_probability)


def test_finite_rate_preserves_information_when_probability_saturates():
    rate = 50.0
    assert -np.expm1(-rate) == 1.0
    result = constant_hazard_occupancy(rate, 0.5, 1.0)
    assert result.endpoint_active_probability > 0
    assert_allclose(result.endpoint_active_probability, np.exp(-25.0) - np.exp(-50.0))
    with pytest.raises(ValueError, match="q=1"):
        infer_ignition_rate(1.0, 1.0)


def test_finite_hazard_at_exact_duration_endpoint_differs_from_initial_fire_extinction():
    rate, interval = 0.003, 3600.0
    new_fire = constant_hazard_occupancy(rate, interval, interval)
    old_fire = initial_active_occupancy(1.0, interval, interval)
    assert_allclose(new_fire.endpoint_active_probability, -np.expm1(-rate * interval))
    assert old_fire.endpoint_active_probability == 0
    assert constant_hazard_occupancy(rate, np.nextafter(interval, 0), interval).endpoint_active_probability < new_fire.endpoint_active_probability


def test_finite_inputs_with_overflowing_exposure_products_remain_supported():
    result = constant_hazard_occupancy([[1e308, 1e308, 0.0]], [[1e307, 1e308, 1e308]], 1e308)
    assert_allclose(result.mean_active_probability, [[0.1, 1.0, 0.0]])
    assert_array_equal(result.endpoint_active_probability, [[0.0, 1.0, 0.0]])


@pytest.mark.parametrize("fraction", [1e-12, 0.003, 0.1, 0.9, np.nextafter(1.0, 0.0)])
def test_endpoint_upper_matches_optimizer_and_encloses_nonmonotone_hazards(fraction):
    upper = constant_hazard_unknown_occupancy_upper(fraction, 1.0)
    optimum = -np.log1p(-fraction) / fraction
    at_optimum = constant_hazard_occupancy(optimum, fraction, 1.0)
    assert_allclose(upper.endpoint_active_probability, at_optimum.endpoint_active_probability, rtol=2e-14)
    assert_allclose(upper.mean_active_probability, fraction)
    for exposure in np.r_[0.0, np.logspace(-14, 6, 100), optimum]:
        result = constant_hazard_occupancy(exposure, fraction, 1.0)
        assert result.mean_active_probability <= upper.mean_active_probability + 1e-15
        assert result.endpoint_active_probability <= upper.endpoint_active_probability * (1 + 2e-14)
    assert constant_hazard_occupancy(1000.0, fraction, 1.0).endpoint_active_probability < at_optimum.endpoint_active_probability


def test_upper_handles_exact_endpoint_long_durations_and_tiny_ratios():
    result = constant_hazard_unknown_occupancy_upper([[3600.0, 7200.0, 600.0]], 3600.0)
    assert_allclose(result.mean_active_probability, [[1.0, 1.0, 1 / 6]])
    assert_allclose(result.endpoint_active_probability, [[1.0, 1.0, (1 / 6) * (5 / 6) ** 5]])
    tiny = constant_hazard_unknown_occupancy_upper(np.nextafter(0.0, 1.0), 1e308)
    assert tiny.mean_active_probability == 0
    assert tiny.endpoint_active_probability == 0


def test_inferred_rate_roundtrip_including_tiny_probability_and_shape():
    probability = np.array([[0.0, 1e-300, 1e-15], [0.3, 0.9, np.nextafter(1.0, 0.0)]])
    rate = infer_ignition_rate(probability, 3600.0)
    assert rate.shape == probability.shape
    assert_allclose(-np.expm1(-rate * 3600.0), probability, rtol=5e-15, atol=0)
    assert infer_ignition_rate(0.0, 1.0) == 0
    with pytest.raises(ValueError, match="numeric range"):
        infer_ignition_rate(0.5, np.nextafter(0.0, 1.0))


@pytest.mark.parametrize("bad_rate", [-1, np.nan, np.inf, True, "1", 1j, [], np.ma.array([1.0], mask=[True])])
def test_invalid_rate_inputs_are_rejected(bad_rate):
    with pytest.raises(ValueError):
        constant_hazard_occupancy(bad_rate, 1.0, 1.0)


@pytest.mark.parametrize("bad_duration", [0, -1, np.nan, np.inf, True, "1", 1j, [], [[1.0]]])
def test_invalid_or_broadcast_duration_inputs_are_rejected(bad_duration):
    with pytest.raises(ValueError):
        constant_hazard_occupancy([[1.0, 2.0]], bad_duration, 1.0)


@pytest.mark.parametrize("bad_interval", [0, -1, np.nan, np.inf, True, "1", 1j, [1.0]])
def test_invalid_interval_inputs_are_rejected(bad_interval):
    for function, first in (
        (lambda rate, duration: constant_hazard_occupancy(rate, duration, bad_interval), 0.1),
        (lambda probability, _: infer_ignition_rate(probability, bad_interval), 0.1),
        (lambda duration, _: constant_hazard_unknown_occupancy_upper(duration, bad_interval), 1.0),
    ):
        with pytest.raises(ValueError):
            function(first, 1.0)


@pytest.mark.parametrize("bad_probability", [-0.1, 1.0, 1.1, np.nan, np.inf, True, "0.1", [], 1j])
def test_probability_inversion_rejects_missing_invalid_or_infinite_hazard_inputs(bad_probability):
    with pytest.raises(ValueError):
        infer_ignition_rate(bad_probability, 3600.0)
