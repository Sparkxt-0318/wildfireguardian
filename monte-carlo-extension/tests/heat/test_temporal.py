"""Independent occupancy integration and input-contract checks."""

from datetime import timedelta

import numpy as np
import pytest
from numpy.testing import assert_allclose

from wildfire.heat import BurningOccupancy
from wildfire.heat import ignition_to_active_probability
from wildfire.heat import initial_active_occupancy


def sampled_new_burn_occupancy(probability, duration, interval, *, samples=2048):
    """Integrate the active indicator on independent time and arrival grids.

    Midpoints avoid giving continuous-arrival boundaries artificial mass. No
    implementation formula or analytic overlap-length expression is used.
    """
    arrival = interval * (np.arange(samples) + 0.5) / samples
    time = interval * (np.arange(samples) + 0.5) / samples
    active = (time[:, None] >= arrival) & (time[:, None] < arrival + duration)
    mean = probability * np.mean(active)
    endpoint = probability * np.mean((interval >= arrival) & (interval < arrival + duration))
    return mean, endpoint


@pytest.mark.parametrize("duration_ratio", [0.001, 0.1, 0.4, 0.99, 1.0, 1.01, 4.0])
def test_new_burning_matches_independent_time_and_arrival_quadrature(duration_ratio):
    probability = 0.63
    interval = 3600.0
    duration = duration_ratio * interval
    result = ignition_to_active_probability([[probability]], duration, interval)
    mean, endpoint = sampled_new_burn_occupancy(probability, duration, interval)
    assert_allclose(result.mean_active_probability, [[mean]], atol=probability / 2048, rtol=0)
    assert_allclose(result.endpoint_active_probability, [[endpoint]], atol=probability / 2048, rtol=0)


def test_each_duration_regime_and_cell_specific_arrays():
    probability = np.array([[0.0, 0.2, 0.7], [1.0, 0.4, 0.8]])
    duration = np.array([[1.0, 25.0, 50.0], [100.0, 150.0, 500.0]])
    result = ignition_to_active_probability(probability, duration, 100.0)
    assert_allclose(result.mean_active_probability, probability * [[0.00995, 0.21875, 0.375], [0.5, 0.5, 0.5]])
    assert_allclose(result.endpoint_active_probability, probability * [[0.01, 0.25, 0.5], [1.0, 1.0, 1.0]])
    assert result.mean_active_probability.shape == probability.shape
    assert result.endpoint_active_probability.shape == probability.shape


def test_subinterval_mean_has_smaller_dose_than_the_complete_burning_phase():
    probability, duration, interval, heat_release_rate = 0.72, 40.0, 100.0, 5000.0
    occupancy = ignition_to_active_probability(probability, duration, interval)
    interval_dose = float(occupancy.mean_active_probability) * interval * heat_release_rate
    # The complete phase continues past the forecast interval for late arrivals.
    # Integrating the original activity indicator until D + T recovers q*T.
    count = 2048
    arrival = interval * (np.arange(count) + 0.5) / count
    dt = (interval + duration) / (4 * count)
    time = dt * (np.arange(4 * count) + 0.5)
    complete_active = (time[:, None] >= arrival) & (time[:, None] < arrival + duration)
    complete_dose = probability * complete_active.mean(axis=1).sum() * dt * heat_release_rate
    assert complete_dose == pytest.approx(probability * duration * heat_release_rate, rel=1e-4)
    assert interval_dose < complete_dose
    # Independent arrival-by-arrival integration of the interval truncation.
    expected_interval_dose = probability * np.minimum(duration, interval - arrival).mean() * heat_release_rate
    assert interval_dose == pytest.approx(expected_interval_dose, rel=1e-6)


def test_same_ignition_probability_can_have_different_early_and_late_heating():
    probability, duration, interval = 0.8, 20.0, 100.0
    uniform = ignition_to_active_probability(probability, duration, interval)
    # Point-mass arrival laws at 0 and 95 s are not the assumed uniform law.
    early_mean = probability * duration / interval
    late_mean = probability * 5.0 / interval
    early_endpoint, late_endpoint = 0.0, probability
    assert late_mean < uniform.mean_active_probability < early_mean
    assert early_endpoint < uniform.endpoint_active_probability < late_endpoint


def test_initial_occupancy_matches_direct_time_indicator_integration():
    probability = np.array([[0.9, 0.6, 0.4, 0.2, 0.8]])
    remaining = np.array([[0.0, 25.0, 100.0, 101.0, 1000.0]])
    result = initial_active_occupancy(probability, remaining, 100.0)
    time = (np.arange(4000) + 0.5) * 100.0 / 4000
    expected_mean = probability * np.mean(time[:, None, None] < remaining, axis=0)
    expected_endpoint = probability * np.array([[False, False, False, True, True]])
    assert_allclose(result.mean_active_probability, expected_mean, atol=1e-15)
    assert_allclose(result.endpoint_active_probability, expected_endpoint, atol=0)


def test_initial_activity_and_disjoint_first_ignition_do_not_double_count():
    # The probability space has initial burning with p=0.3, new ignition with
    # q=0.5, and no burning with probability 0.2, as mutually exclusive states.
    initial = initial_active_occupancy([[0.3]], 100.0, 100.0)
    new = ignition_to_active_probability([[0.5]], 200.0, 100.0)
    assert_allclose(initial.mean_active_probability + new.mean_active_probability, [[0.55]])
    assert_allclose(initial.endpoint_active_probability + new.endpoint_active_probability, [[0.5]])


@pytest.mark.parametrize("function", [ignition_to_active_probability, initial_active_occupancy])
@pytest.mark.parametrize(
    "probability",
    [
        [[-1e-12]], [[1.000000001]], [[np.nan]], [[np.inf]],
        np.ma.array([[0.5]], mask=[[True]]), [[1 + 0j]], [["0.5"]], [],
    ],
)
def test_invalid_probability_is_rejected(function, probability):
    with pytest.raises(ValueError):
        function(probability, 20.0, 100.0)


@pytest.mark.parametrize("function", [ignition_to_active_probability, initial_active_occupancy])
@pytest.mark.parametrize(
    "interval",
    [0.0, -1.0, np.nan, np.inf, [100.0], True, np.array(True), "100", np.timedelta64(100, "s"), timedelta(seconds=100)],
)
def test_interval_requires_finite_positive_numeric_scalar_seconds(function, interval):
    with pytest.raises(ValueError):
        function([[0.5]], 20.0, interval)


@pytest.mark.parametrize("function", [ignition_to_active_probability, initial_active_occupancy])
@pytest.mark.parametrize(
    "duration",
    [
        -1.0, np.nan, np.inf, [20.0], [[20.0, 20.0]], True, np.array(True), "20",
        np.timedelta64(20, "s"), timedelta(seconds=20),
        np.ma.array([[20.0]], mask=[[True]]),
    ],
)
def test_duration_requires_valid_scalar_or_exact_shape_numeric_seconds(function, duration):
    with pytest.raises(ValueError):
        function([[0.5]], duration, 100.0)


def test_zero_duration_requires_initial_occupancy():
    with pytest.raises(ValueError, match="positive"):
        ignition_to_active_probability([[0.5]], 0.0, 100.0)
    initial = initial_active_occupancy([[0.5]], 0.0, 100.0)
    assert_allclose(initial.mean_active_probability, [[0.0]])
    assert_allclose(initial.endpoint_active_probability, [[0.0]])


@pytest.mark.parametrize("function", [ignition_to_active_probability, initial_active_occupancy])
def test_large_duration_small_interval_remains_finite(function):
    with np.errstate(over="raise"):
        result = function([[0.7]], np.finfo(float).max, np.finfo(float).tiny)
    expected_mean = [[0.35]] if function is ignition_to_active_probability else [[0.7]]
    assert_allclose(result.mean_active_probability, expected_mean)
    assert_allclose(result.endpoint_active_probability, [[0.7]])


def test_result_owns_immutable_validated_probability_arrays():
    mean = np.array([[0.1]])
    endpoint = np.array([[0.2]])
    result = BurningOccupancy(mean, endpoint)
    mean[:] = 0.9
    endpoint[:] = 0.8
    assert_allclose(result.mean_active_probability, [[0.1]])
    assert_allclose(result.endpoint_active_probability, [[0.2]])
    with pytest.raises(ValueError):
        result.mean_active_probability[0, 0] = 0.4
    with pytest.raises(ValueError):
        BurningOccupancy([[0.1]], [0.2])
    with pytest.raises(ValueError):
        BurningOccupancy([[np.nan]], [[0.2]])


def test_scalar_and_singleton_durations_preserve_probability_shape():
    scalar = ignition_to_active_probability(0.6, 50.0, 100.0)
    assert scalar.mean_active_probability.shape == ()
    assert scalar.endpoint_active_probability.shape == ()
    assert_allclose(scalar.mean_active_probability, 0.225)
    assert_allclose(scalar.endpoint_active_probability, 0.3)
    matrix = ignition_to_active_probability([[0.6]], [[50.0]], 100.0)
    assert matrix.mean_active_probability.shape == (1, 1)
    assert_allclose(matrix.mean_active_probability, [[0.225]])
