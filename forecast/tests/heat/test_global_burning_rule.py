"""Public arrival-age rule and its propagation through every heat entry point.

The activity checks use the defining half-open time indicator. Spatial heat and
dose checks integrate that indicator independently of the forecast bridge. No
weights are trained, and no observed future labels enter new-ignition inference.
"""

from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal

import wildfire
from tests.heat.test_pipeline import DeterministicPredictor, make_model


def test_direct_arrival_based_state_rejects_active_at_exact_extinction():
    from wildfire import BurningState

    with pytest.raises(ValueError, match="positive remaining"):
        BurningState([[1.0]], [[0.0]], [[True]])
from wildfire.heat import AffineGrid, FlameResidenceTime, active_flames_from_arrival


def _sample(model, predictor, burned, **timing):
    burned = np.asarray(burned, dtype=float)
    return dict(
        affine_transform=np.asarray(model.heat_model.grid.transform),
        epsg=32652,
        burned_area=burned[None],
        features=np.zeros((2,) + burned.shape),
        channel_names=predictor.channel_names,
        **timing,
    )


def test_burning_state_is_public_and_uses_the_half_open_arrival_interval():
    from wildfire.heat import BurningState, burning_state_from_arrival

    assert wildfire.BurningState is BurningState
    assert wildfire.burning_state_from_arrival is burning_state_from_arrival
    arrival = np.array([[-20.0, -10.0, -5.0, 0.0, 1.0, np.nan]])
    state = burning_state_from_arrival(arrival, 10.0, 0.0)
    assert isinstance(state, BurningState)
    assert_array_equal(state.valid, [[True, True, True, True, True, False]])
    assert_allclose(
        state.active_burning_probability, [[0.0, 0.0, 1.0, 1.0, 0.0, np.nan]],
        equal_nan=True,
    )
    assert_allclose(
        state.remaining_burning_duration_s, [[0.0, 0.0, 5.0, 10.0, 0.0, np.nan]],
        equal_nan=True,
    )


def test_explicit_old_support_resolves_unburned_cells_and_preserves_unknown_old_age():
    from wildfire import burning_state_from_arrival

    arrival = [[np.nan, np.nan, 20.0, -100.0, 1_000_000.0]]
    old = np.array([[True, False, False, False, True]])
    supplied_valid = np.array([[False, False, True, True, False]])
    state = burning_state_from_arrival(
        arrival, 7200.0, 100.0,
        arrival_valid=supplied_valid, already_burned_mask=old,
    )
    assert_array_equal(state.valid, [[False, True, True, True, False]])
    assert_allclose(
        state.active_burning_probability, [[np.nan, 0.0, 0.0, 0.0, np.nan]],
        equal_nan=True,
    )
    assert_allclose(
        state.remaining_burning_duration_s, [[np.nan, 0.0, 0.0, 0.0, np.nan]],
        equal_nan=True,
    )


def test_global_state_and_active_flame_map_agree_for_cell_specific_durations():
    from wildfire import burning_state_from_arrival

    arrival = np.array([[0.0, 10.0, 11.0], [np.nan, -10.0, 5.0]])
    duration = np.array([[10.0, 20.0, 20.0], [10.0, 20.0, 6.0]])
    current = 10.0
    state = burning_state_from_arrival(arrival, duration, current)
    flames = active_flames_from_arrival(
        arrival, FlameResidenceTime(duration, {"source": "test scenario"}),
        current, grid=AffineGrid.from_cell_size(10.0),
    )
    assert_array_equal(state.valid, flames.valid)
    assert_allclose(state.active_burning_probability, flames.probability, equal_nan=True)
    assert_allclose(state.remaining_burning_duration_s, flames.remaining_duration_s, equal_nan=True)
    age = current - arrival
    independent_active = (age >= 0.0) & (age < duration)
    assert_array_equal(state.active_burning_probability[state.valid], independent_active[state.valid])


@pytest.mark.parametrize("duration, age", [(900.0, 100.0), (900.0, 900.0), (7200.0, 0.0), (7200.0, 3600.0)])
def test_known_previous_burning_flux_and_dose_match_independent_time_indicator(duration, age):
    model = make_model(duration=duration)
    current = 12_000.0
    arrival = current - age
    result = model.predict_from_new_burn_probability_details(
        [[np.nan]], already_burned_mask=np.array([[True]]),
        arrival_time_s=[[arrival]], current_time_s=current,
    )
    # 0.05 s midpoint bins exactly resolve the chosen phase boundaries.
    time = (np.arange(72_000) + 0.5) * 0.05
    activity = (current + time >= arrival) & (current + time < arrival + duration)
    # A 10 m square 5 m above the receiver subtends 2*pi/3 sr. A Lambertian
    # emitter sends one sixth of its radiative HRR per area to that receiver.
    conditional_flux = 0.3 * 18e6 * 0.6 / duration / 6.0
    independent_dose = conditional_flux * np.sum(activity) * 0.05
    assert_allclose(result.expected_incident_energy_j_m2, [[independent_dose]], rtol=2e-14, atol=1e-12)
    assert_allclose(result.expected_heat_flux_w_m2, [[independent_dose / 3600.0]], rtol=2e-14, atol=1e-14)
    assert_array_equal(result.new_burn_probability, [[0.0]])
    assert_array_equal(result.initial_active_burning_probability, [[float(0 <= age < duration)]])
    assert_array_equal(result.initial_remaining_burning_duration_s, [[max(duration - age, 0.0)]])
    assert result.complete


@pytest.mark.parametrize("entry", ["raw", "sample", "probability"])
def test_default_missing_previous_age_returns_unknown_activity_and_duration_limited_bounds(entry):
    predictor = DeterministicPredictor([[np.nan, 0.4]])
    model = make_model(predictor, duration=7200.0, epsg=32652)
    burned = np.array([[1.0, 0.0]])
    if entry == "raw":
        result = model.predict_details(burned, np.zeros((2, 1, 2)), channel_names=predictor.channel_names)
    elif entry == "sample":
        result = model.predict_sample_details(_sample(model, predictor, burned))
    else:
        result = model.predict_from_new_burn_probability_details(
            predictor.probability, already_burned_mask=burned.astype(bool),
        )
    assert_array_equal(result.probability_valid, [[True, True]])
    assert_array_equal(result.new_burn_probability, [[0.0, 0.4]])
    assert_array_equal(result.initial_burning_valid, [[False, True]])
    assert_allclose(result.initial_active_burning_probability, [[np.nan, 0.0]], equal_nan=True)
    assert_allclose(result.initial_remaining_burning_duration_s, [[np.nan, 0.0]], equal_nan=True)
    assert_allclose(result.mean_active_burning_probability, [[np.nan, 0.2]], equal_nan=True)
    assert_allclose(result.endpoint_active_burning_probability, [[np.nan, 0.4]], equal_nan=True)
    lower = model.heat_model.predict_details([[0.0, 0.2]]).incident_heat_flux_w_m2
    upper = model.heat_model.predict_details([[1.0, 0.2]]).incident_heat_flux_w_m2
    assert_allclose(result.heat_flux_lower_bound_w_m2, lower, rtol=2e-14)
    assert_allclose(result.heat_flux_upper_bound_w_m2, upper, rtol=2e-14)
    assert_allclose(result.incident_energy_upper_bound_j_m2, 3600.0 * upper, rtol=2e-14)
    assert not result.complete
    assert not result.endpoint_complete
    assert np.isnan(result.expected_heat_flux_w_m2).all()


@pytest.mark.parametrize("entry", ["raw", "sample", "probability"])
def test_default_tuple_keeps_unknown_previous_heat_and_returns_real_coordinates(entry):
    predictor = DeterministicPredictor([[0.0, 0.4]])
    model = make_model(predictor, duration=7200.0, epsg=32652)
    burned = np.array([[1.0, 0.0]])
    if entry == "raw":
        flux, coordinates = model.predict(burned, np.zeros((2, 1, 2)), channel_names=predictor.channel_names)
    elif entry == "sample":
        flux, coordinates = model.predict_sample(_sample(model, predictor, burned))
    else:
        flux, coordinates = model.predict_from_new_burn_probability(
            predictor.probability, already_burned_mask=burned.astype(bool),
        )
    assert np.isnan(flux).all()
    assert coordinates.shape == (1, 2, 2)
    assert np.isfinite(coordinates).all()


@pytest.mark.parametrize("entry", ["raw", "sample", "probability"])
def test_explicit_opt_out_excludes_old_burning_in_details_and_tuples(entry):
    predictor = DeterministicPredictor([[0.0, 0.4]])
    model = make_model(predictor, duration=7200.0, epsg=32652)
    burned = np.array([[1.0, 0.0]])
    if entry == "raw":
        args = (burned, np.zeros((2, 1, 2)))
        kwargs = dict(channel_names=predictor.channel_names, include_previous_burning=False)
        details, pair = model.predict_details, model.predict
    elif entry == "sample":
        args = (_sample(model, predictor, burned),)
        kwargs = dict(initial_burning_from_arrival=False)
        details, pair = model.predict_sample_details, model.predict_sample
    else:
        args = (predictor.probability,)
        kwargs = dict(already_burned_mask=burned.astype(bool), include_previous_burning=False)
        details, pair = model.predict_from_new_burn_probability_details, model.predict_from_new_burn_probability
    result = details(*args, **kwargs)
    flux, coordinates = pair(*args, **kwargs)
    assert result.complete
    assert_array_equal(result.initial_burning_valid, [[True, True]])
    assert_array_equal(result.initial_active_burning_probability, [[0.0, 0.0]])
    expected = model.heat_model.predict_details([[0.0, 0.2]]).incident_heat_flux_w_m2
    assert_allclose(result.expected_heat_flux_w_m2, expected, rtol=2e-14)
    assert_allclose(flux, expected, rtol=2e-14)
    assert np.isfinite(coordinates).all()


@pytest.mark.parametrize("entry", ["raw", "probability"])
@pytest.mark.parametrize("explicit", [
    dict(arrival_time_s=[[0.0]], current_time_s=100.0),
    dict(initial_active_burning_probability=[[1.0]], initial_remaining_burning_duration_s=[[100.0]]),
])
def test_opt_out_rejects_conflicting_explicit_current_burning_inputs(entry, explicit):
    predictor = DeterministicPredictor([[0.0]])
    model = make_model(predictor)
    options = dict(include_previous_burning=False, **explicit)
    with pytest.raises(ValueError):
        if entry == "raw":
            model.predict_details([[1.0]], np.zeros((2, 1, 1)), channel_names=predictor.channel_names, **options)
        else:
            model.predict_from_new_burn_probability_details([[0.0]], already_burned_mask=np.array([[True]]), **options)


def test_sample_opt_out_preserves_an_explicit_activity_override():
    predictor = DeterministicPredictor([[0.0]])
    model = make_model(predictor, duration=7200.0)
    sample = _sample(model, predictor, [[1.0]], arrival_hours=np.array([[[0.0]]]), elapsed_hours=np.array([0.0]))
    result = model.predict_sample_details(
        sample, initial_burning_from_arrival=False,
        initial_active_burning_probability=[[0.4]], initial_remaining_burning_duration_s=[[100.0]],
    )
    assert result.complete
    assert_array_equal(result.initial_active_burning_probability, [[0.4]])
    assert_allclose(result.mean_active_burning_probability, [[0.4 * 100.0 / 3600.0]], rtol=2e-14)


@pytest.mark.parametrize("invalid_time", [True, "100", [100.0], np.inf, np.nan, timedelta(seconds=100)])
def test_invalid_current_time_has_the_same_contract_for_global_flame_and_heat_routes(invalid_time):
    from wildfire import burning_state_from_arrival

    with pytest.raises(ValueError):
        burning_state_from_arrival([[0.0]], 7200.0, invalid_time)
    with pytest.raises(ValueError):
        active_flames_from_arrival(
            [[0.0]], FlameResidenceTime(7200.0, {"source": "test scenario"}),
            invalid_time, grid=AffineGrid.from_cell_size(10.0),
        )
    with pytest.raises(ValueError):
        make_model(duration=7200.0).predict_from_new_burn_probability_details(
            [[0.0]], already_burned_mask=np.array([[True]]),
            arrival_time_s=[[0.0]], current_time_s=invalid_time,
        )


@pytest.mark.parametrize("invalid_mask", [np.array([[1]]), np.array([True]), np.ones((1, 2), bool)])
def test_global_burning_state_requires_boolean_masks_with_exact_spatial_shape(invalid_mask):
    from wildfire import burning_state_from_arrival

    for name in ("arrival_valid", "already_burned_mask"):
        with pytest.raises(ValueError):
            burning_state_from_arrival([[0.0]], 7200.0, 100.0, **{name: invalid_mask})


def test_global_burning_state_rejects_a_future_arrival_on_known_old_support():
    from wildfire import burning_state_from_arrival

    with pytest.raises(ValueError):
        burning_state_from_arrival([[101.0]], 7200.0, 100.0, already_burned_mask=np.array([[True]]))
    # Without a cumulative-state assertion this is a valid not-yet-active cell.
    result = burning_state_from_arrival([[101.0]], 7200.0, 100.0)
    assert_array_equal(result.active_burning_probability, [[0.0]])
    assert_array_equal(result.remaining_burning_duration_s, [[0.0]])


def test_public_api_heat_model_uses_old_arrival_state_and_keeps_missing_age_unknown():
    from wildfire.api import WildfireModel

    predictor = DeterministicPredictor([[0.9, 0.2]])
    predictor.contract = {"architecture": "EnvironmentConditionedConvolution"}
    api = WildfireModel(predictor, {"contract": predictor.contract}, Path("/tmp/synthetic-global-rule.pt"), "synthetic-digest")
    physical = make_model(duration=7200.0)
    model = api.heat_model(
        grid=physical.heat_model.grid, combustion=physical.combustion,
        radiative_fraction=0.3, emission_height_m=5.0,
    )
    sample = _sample(
        model, predictor, [[1.0, 0.0]],
        arrival_hours=np.array([[[0.0, 100.0]]]),
        elapsed_hours=np.array([0.5]), arrival_valid=np.ones((1, 1, 2), bool),
    )
    result = model.predict_sample_details(sample)
    assert_array_equal(result.initial_active_burning_probability, [[1.0, 0.0]])
    assert_array_equal(result.initial_remaining_burning_duration_s, [[5400.0, 0.0]])
    assert_allclose(result.mean_active_burning_probability, [[1.0, 0.1]], rtol=2e-14)
    expected = model.heat_model.predict_details([[1.0, 0.1]]).incident_heat_flux_w_m2
    assert_allclose(result.expected_heat_flux_w_m2, expected, rtol=2e-14)
    assert result.complete
    missing = model.predict_sample_details(_sample(model, predictor, [[1.0, 0.0]]))
    assert not missing.complete
    assert_array_equal(missing.initial_burning_valid, [[False, True]])
    assert np.isnan(missing.expected_heat_flux_w_m2).all()
    for _, _, options in predictor.calls:
        assert "arrival_time_s" not in options
        assert "current_time_s" not in options
