"""Independent flaming-position checks: phase boundaries, support and geometry.

The deterministic-arrival tests evaluate the defining activity indicator. The
forecast tests integrate that indicator over separate arrival and time grids;
they do not reuse the forecast conversion's closed-form expression.
"""

from datetime import timedelta

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal

from wildfire.heat import AffineGrid
from wildfire.heat import ActiveFlameMap
from wildfire.heat import active_flames_from_arrival
from wildfire.heat import forecast_active_flames
from wildfire.heat import FlameResidenceTime


def residence(duration):
    return FlameResidenceTime(duration, {"source": "explicit test scenario"})


@pytest.fixture
def grid():
    return AffineGrid.from_cell_size(10.0)


def test_arrival_and_extinction_use_half_open_phase_and_negative_origins(grid):
    arrival = np.array([[-20.0, -10.0, -5.0, 0.0, 1.0]])
    # At t=0 the first two cells have extinguished, including extinction exactly
    # at t=0. A cell arriving exactly now is active for the full residence time.
    result = active_flames_from_arrival(arrival, residence(10.0), 0.0, grid=grid)
    assert_array_equal(result.valid, np.ones(arrival.shape, dtype=bool))
    assert_array_equal(result.probability, [[0.0, 0.0, 1.0, 1.0, 0.0]])
    assert_array_equal(result.remaining_duration_s, [[0.0, 0.0, 5.0, 10.0, 0.0]])
    assert result.time_s == 0.0


def test_each_cell_has_its_own_residence_and_flames_do_not_persist_forever(grid):
    arrival = np.array([[0.0, 0.0], [5.0, 20.0]])
    duration = np.array([[5.0, 20.0], [4.0, 1.0]])
    result = active_flames_from_arrival(arrival, residence(duration), 10.0, grid=grid)
    assert_array_equal(result.probability, [[0.0, 1.0], [0.0, 0.0]])
    assert_array_equal(result.remaining_duration_s, [[0.0, 10.0], [0.0, 0.0]])
    late = active_flames_from_arrival(arrival, residence(duration), 100.0, grid=grid)
    assert_array_equal(late.probability, np.zeros(arrival.shape))


def test_unknown_arrival_is_not_reported_as_extinguished_or_unburned(grid):
    arrival = np.array([[np.nan, -1.0], [0.0, 999.0]])
    supplied_valid = np.array([[False, True], [True, False]])
    result = active_flames_from_arrival(
        arrival, residence(2.0), 0.0, grid=grid, arrival_valid=supplied_valid,
    )
    assert_array_equal(result.valid, supplied_valid)
    assert np.isnan(result.probability[~supplied_valid]).all()
    assert np.isnan(result.remaining_duration_s[~supplied_valid]).all()
    assert_array_equal(result.probability[supplied_valid], [1.0, 1.0])
    positions = result.positions(min_probability=1.0)
    assert_array_equal(positions.cells_rc, [[0, 1], [1, 0]])


def test_nan_arrival_support_is_inferred_only_when_mask_is_absent(grid):
    result = active_flames_from_arrival([[np.nan, 0.0]], residence(2.0), 1.0, grid=grid)
    assert_array_equal(result.valid, [[False, True]])
    assert np.isnan(result.probability[0, 0])
    with pytest.raises(ValueError):
        active_flames_from_arrival(
            [[np.nan]], residence(2.0), 1.0, grid=grid,
            arrival_valid=np.array([[True]]),
        )


def test_positions_use_full_affine_cell_centers_and_explicit_threshold():
    # This transform has rotation/shear; separate x/y spacings cannot represent it.
    grid = AffineGrid((3.0, 1.0, 100.0, 2.0, -4.0, 200.0))
    probability = np.array([[0.0, 0.5, np.nan], [0.75, 0.25, 1.0]])
    valid = np.isfinite(probability)
    result = ActiveFlameMap(probability, valid, grid, 12.0, {"source": "scenario"})
    positions = result.positions(min_probability=0.5)
    assert_array_equal(positions.cells_rc, [[0, 1], [1, 0], [1, 2]])
    assert positions.cells_rc.dtype.kind in "iu"
    assert_allclose(positions.coordinates_xy_m, [[105.0, 201.0], [103.0, 195.0], [109.0, 199.0]], rtol=0, atol=0)
    assert_array_equal(positions.probabilities, [0.5, 0.75, 1.0])
    with pytest.raises(TypeError):
        result.positions()


def test_empty_positions_have_stable_two_column_coordinate_shapes(grid):
    result = ActiveFlameMap([[0.0, np.nan]], [[True, False]], grid, 0.0, {})
    positions = result.positions(min_probability=0.01)
    assert positions.cells_rc.shape == (0, 2)
    assert positions.coordinates_xy_m.shape == (0, 2)
    assert positions.probabilities.shape == (0,)


def test_position_arrays_are_readonly_independently_of_the_map(grid):
    result = ActiveFlameMap([[0.4]], [[True]], grid, 0.0, {})
    positions = result.positions(min_probability=0.1)
    for array in (positions.cells_rc, positions.coordinates_xy_m, positions.probabilities):
        assert not array.flags.writeable
        with pytest.raises(ValueError):
            array.flat[0] = 0


@pytest.mark.parametrize("threshold", [0.0, -1.0, 1.00001, np.nan, np.inf, True, "0.5", [0.5]])
def test_position_threshold_requires_explicit_positive_probability(threshold, grid):
    result = ActiveFlameMap([[1.0]], [[True]], grid, 0.0, {})
    with pytest.raises(ValueError):
        result.positions(min_probability=threshold)


def test_flame_map_owns_readonly_arrays_and_normalizes_invalid_support(grid):
    probability = np.array([[1.0, 0.9]])
    valid = np.array([[True, False]])
    remaining = np.array([[2.0, 100.0]])
    result = ActiveFlameMap(
        probability, valid, grid, 0.0, {}, remaining_duration_s=remaining,
    )
    probability[:] = 0
    valid[:] = True
    remaining[:] = 0
    assert_array_equal(result.probability[:, :1], [[1.0]])
    assert np.isnan(result.probability[0, 1])
    assert_array_equal(result.valid, [[True, False]])
    assert_array_equal(result.remaining_duration_s[:, :1], [[2.0]])
    assert np.isnan(result.remaining_duration_s[0, 1])
    for array in (result.probability, result.valid, result.remaining_duration_s):
        assert not array.flags.writeable
        with pytest.raises(ValueError):
            array.flat[0] = 0


@pytest.mark.parametrize("duration", [1.0, 20.0, 80.0, 100.0, 101.0, 300.0])
def test_new_ignition_forecast_matches_independent_activity_indicator_quadrature(duration, grid):
    probability, interval, samples = 0.63, 100.0, 1024
    result = forecast_active_flames([[probability]], residence(duration), interval, grid=grid)
    # Independent midpoint integration on the conditional arrival-time domain.
    arrival = interval * (np.arange(samples) + 0.5) / samples
    time = interval * (np.arange(samples) + 0.5) / samples
    activity = (time[:, None] >= arrival) & (time[:, None] < arrival + duration)
    independent_mean = probability * activity.mean()
    independent_endpoint = probability * np.mean((interval >= arrival) & (interval < arrival + duration))
    assert_allclose(result.mean_active_probability, [[independent_mean]], atol=probability / samples, rtol=0)
    assert_allclose(result.endpoint.probability, [[independent_endpoint]], atol=probability / samples, rtol=0)
    assert result.endpoint.time_s == interval
    assert result.interval_s == interval


def test_forecast_zero_probability_stays_zero_even_for_long_residence(grid):
    result = forecast_active_flames([[0.0]], residence(1e5), 3600.0, grid=grid)
    assert_array_equal(result.mean_active_probability, [[0.0]])
    assert_array_equal(result.endpoint.probability, [[0.0]])
    assert result.endpoint.positions(min_probability=1e-12).cells_rc.shape == (0, 2)


def test_forecast_cell_specific_durations_and_unresolved_probabilities(grid):
    q = np.array([[0.6, 0.8], [np.nan, 0.7]])
    duration = np.array([[20.0, 100.0], [80.0, 300.0]])
    valid = np.array([[True, True], [False, False]])
    result = forecast_active_flames(q, residence(duration), 100.0, grid=grid, probability_valid=valid)
    assert_array_equal(result.valid, valid)
    assert_array_equal(result.endpoint.valid, valid)
    assert np.isnan(result.new_burn_probability[~valid]).all()
    assert np.isnan(result.mean_active_probability[~valid]).all()
    assert np.isnan(result.endpoint.probability[~valid]).all()
    assert_allclose(result.endpoint.probability[valid], [0.12, 0.8], rtol=1e-14)
    assert_allclose(result.mean_active_probability[valid], [0.108, 0.4], rtol=1e-14)
    assert_array_equal(result.endpoint.positions(min_probability=0.2).cells_rc, [[0, 1]])
    assert not result.new_burn_probability.flags.writeable
    assert not result.mean_active_probability.flags.writeable
    assert not result.valid.flags.writeable


def test_forecast_probability_inputs_are_copied_and_nan_mask_is_inferred(grid):
    probability = np.array([[0.6, np.nan]])
    result = forecast_active_flames(probability, residence(20.0), 100.0, grid=grid)
    probability[0, 0] = 0.0
    assert_array_equal(result.valid, [[True, False]])
    assert result.new_burn_probability[0, 0] == 0.6
    assert result.endpoint.probability[0, 0] == pytest.approx(0.12)


@pytest.mark.parametrize("function", [active_flames_from_arrival, forecast_active_flames])
@pytest.mark.parametrize("invalid_matrix", [[], [0.0], np.zeros((1, 1, 1)), [["0.1"]], [[1 + 0j]], np.ma.array([[0.1]], mask=[[True]])])
def test_maps_require_explicit_real_unmasked_spatial_matrices(function, invalid_matrix, grid):
    with pytest.raises(ValueError):
        function(invalid_matrix, residence(20.0), 100.0, grid=grid)


@pytest.mark.parametrize("function, mask_name", [
    (active_flames_from_arrival, "arrival_valid"),
    (forecast_active_flames, "probability_valid"),
])
@pytest.mark.parametrize("mask", [[[1]], np.array([True]), np.ones((1, 2), dtype=bool)])
def test_validity_masks_require_boolean_values_and_exact_matrix_shape(function, mask_name, mask, grid):
    with pytest.raises(ValueError):
        function([[0.1]], residence(20.0), 100.0, grid=grid, **{mask_name: mask})


@pytest.mark.parametrize("function", [active_flames_from_arrival, forecast_active_flames])
def test_cell_specific_duration_shape_cannot_broadcast_over_the_map(function, grid):
    with pytest.raises(ValueError):
        function(np.zeros((2, 3)), residence(np.ones((1, 3))), 100.0, grid=grid)


@pytest.mark.parametrize("arrival", [np.inf, -np.inf])
def test_infinite_arrival_is_rejected_even_outside_declared_support(arrival, grid):
    with pytest.raises(ValueError):
        active_flames_from_arrival(
            [[arrival]], residence(20.0), 0.0, grid=grid,
            arrival_valid=np.array([[False]]),
        )


@pytest.mark.parametrize("probability", [-0.01, 1.01, np.inf, -np.inf, np.nan])
def test_valid_forecast_probabilities_must_be_finite_and_in_unit_interval(probability, grid):
    with pytest.raises(ValueError):
        forecast_active_flames(
            [[probability]], residence(20.0), 100.0, grid=grid,
            probability_valid=np.array([[True]]),
        )


@pytest.mark.parametrize("time", [np.nan, np.inf, -np.inf, True, "100", [100.0], timedelta(seconds=100), np.timedelta64(100, "s")])
def test_arrival_evaluation_time_requires_finite_real_scalar_seconds(time, grid):
    with pytest.raises(ValueError):
        active_flames_from_arrival([[0.0]], residence(20.0), time, grid=grid)


@pytest.mark.parametrize("interval", [0.0, -1.0, np.nan, np.inf, True, "100", [100.0], timedelta(seconds=100), np.timedelta64(100, "s")])
def test_forecast_interval_requires_positive_numeric_scalar_seconds(interval, grid):
    with pytest.raises(ValueError):
        forecast_active_flames([[0.5]], residence(20.0), interval, grid=grid)


def test_arrival_and_evaluation_can_share_any_negative_numeric_origin(grid):
    first = active_flames_from_arrival([[-100.0, -90.0]], residence(20.0), -95.0, grid=grid)
    translated = active_flames_from_arrival([[0.0, 10.0]], residence(20.0), 5.0, grid=grid)
    assert_array_equal(first.probability, translated.probability)
    assert_array_equal(first.remaining_duration_s, translated.remaining_duration_s)


def test_extreme_finite_arrivals_remain_valid_and_do_not_overflow_the_activity_comparison(grid):
    # A+t is not the right numerical operation for deciding activity. Both
    # inputs can be finite while their difference exceeds float64 range.
    with np.errstate(over="raise", invalid="raise"):
        result = active_flames_from_arrival(
            [[-1e308, 1e308]], residence(20.0), 1e308, grid=grid,
        )
    assert_array_equal(result.valid, [[True, True]])
    assert_array_equal(result.probability, [[0.0, 1.0]])
    assert_array_equal(result.remaining_duration_s, [[0.0, 20.0]])


@pytest.mark.parametrize("probability", [-0.1, 1.1, np.nan, np.inf])
def test_active_map_rejects_invalid_probabilities_on_supported_cells(probability, grid):
    with pytest.raises(ValueError):
        ActiveFlameMap([[probability]], [[True]], grid, 0.0, {})


@pytest.mark.parametrize("remaining", [[[-1.0]], [[np.nan]], [[np.inf]], [[1.0, 2.0]]])
def test_active_map_remaining_duration_requires_finite_nonnegative_matching_matrix(remaining, grid):
    with pytest.raises(ValueError):
        ActiveFlameMap([[1.0]], [[True]], grid, 0.0, {}, remaining_duration_s=remaining)


@pytest.mark.parametrize("indices", [[[0.5, 1.0]], [[True, False]]])
def test_position_indices_cannot_silently_round_or_convert_booleans(indices):
    from wildfire.heat import FlamePositions

    with pytest.raises(ValueError, match="integers"):
        FlamePositions(indices, [[10.0, 20.0]], [0.5])
