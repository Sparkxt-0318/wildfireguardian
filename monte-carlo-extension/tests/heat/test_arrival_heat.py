"""Duration-aware heat from known burned cells and their supplied arrival ages.

The independent time-indicator integrations below test both the temporal
assumption and its radiation/dose consequence. No checkpoint is trained and no
future arrival is used to replace a new-burning forecast probability.
"""

from datetime import timedelta

import numpy as np
import pytest
from numpy.testing import assert_allclose, assert_array_equal

from tests.heat.test_pipeline import DeterministicPredictor, make_model


def _sample(model, predictor, burned, **timing):
    burned = np.asarray(burned, dtype=float)
    return dict(
        affine_transform=np.array(model.heat_model.grid.transform),
        burned_area=burned[None],
        features=np.zeros((2,) + burned.shape),
        channel_names=predictor.channel_names,
        **timing,
    )


@pytest.mark.parametrize(
    "duration, age",
    [(900.0, 60.0), (900.0, 900.0), (3600.0, 0.0),
     (7200.0, 3600.0), (7200.0, 3599.0), (7200.0, 0.0)],
)
def test_arrival_age_heat_and_dose_match_independent_time_indicator(duration, age):
    model = make_model(duration=duration)
    cutoff = 12_000.0
    arrival = cutoff - age
    result = model.predict_from_new_burn_probability_details(
        [[np.nan]], already_burned_mask=np.array([[True]]),
        arrival_time_s=[[arrival]], current_time_s=cutoff,
    )
    # Integrate the original active indicator, with a midpoint grid fine enough
    # to cover the one-second endpoint boundary case without sampling an edge.
    times = (np.arange(72_000) + 0.5) * 3600.0 / 72_000
    active = (cutoff + times >= arrival) & (cutoff + times < arrival + duration)
    mean = active.mean()
    endpoint = float(arrival <= cutoff + 3600.0 < arrival + duration)
    initial = float(arrival <= cutoff < arrival + duration)
    # The square source 5 m above its center subtends 2*pi/3 steradians.
    conditional_flux = 0.3 * 18e6 * 0.6 / duration / 6.0
    assert_allclose(result.mean_active_burning_probability, [[mean]], atol=1e-14)
    assert_allclose(result.endpoint_active_burning_probability, [[endpoint]], atol=0)
    assert_allclose(result.expected_heat_flux_w_m2, [[conditional_flux * mean]], rtol=2e-14, atol=1e-14)
    assert_allclose(result.expected_incident_energy_j_m2, [[conditional_flux * active.sum() * 0.05]], rtol=2e-14, atol=1e-14)
    assert_allclose(result.endpoint_heat_flux_lower_bound_w_m2, [[conditional_flux * endpoint]], rtol=2e-14)
    assert_allclose(result.expected_endpoint_heat_flux_w_m2, [[conditional_flux * endpoint]], rtol=2e-14)
    assert_array_equal(result.initial_active_burning_probability, [[initial]])
    assert_allclose(result.initial_remaining_burning_duration_s, [[max(duration - age, 0.0)]])
    assert_array_equal(result.initial_burning_valid, [[True]])
    assert_array_equal(result.new_burn_probability, [[0.0]])
    assert result.complete
    assert result.endpoint_complete


def test_cell_specific_arrival_ages_combined_with_forecast_new_ignitions():
    duration = np.array([[600.0, 7200.0, 1800.0, 1200.0]])
    cutoff = 4000.0
    model = make_model(duration=duration)
    old = np.array([[True, True, False, True]])
    probability = np.array([[np.nan, 0.9, 0.6, 0.9]])
    arrival = np.array([[3900.0, 0.0, -999_999.0, 2800.0]])
    result = model.predict_from_new_burn_probability_details(
        probability, already_burned_mask=old,
        arrival_time_s=arrival, current_time_s=cutoff,
    )
    # Integrate the current activity indicators and a separate uniform-arrival
    # indicator over the next hour. The third arrival input is deliberately
    # contradictory to the unburned state and must not enter current activity.
    count = 4096
    times = (np.arange(count) + 0.5) * 3600.0 / count
    new_arrivals = times.copy()
    instantaneous = np.zeros((count, 1, 4))
    for column in (0, 1, 3):
        instantaneous[:, 0, column] = (
            (cutoff + times >= arrival[0, column])
            & (cutoff + times < arrival[0, column] + duration[0, column])
        )
    instantaneous[:, 0, 2] = 0.6 * np.mean(
        (times[:, None] >= new_arrivals)
        & (times[:, None] < new_arrivals + 1800.0), axis=1,
    )
    integrated_mean = instantaneous.mean(axis=0)
    assert_allclose(result.mean_active_burning_probability, integrated_mean, atol=1 / count)
    expected_mean_flux = model.heat_model.predict_details(integrated_mean).incident_heat_flux_w_m2
    assert_allclose(result.expected_heat_flux_w_m2, expected_mean_flux, rtol=4e-4)
    assert_array_equal(result.new_burn_probability, [[0.0, 0.0, 0.6, 0.0]])
    assert_array_equal(result.initial_active_burning_probability, [[1.0, 1.0, 0.0, 0.0]])
    assert_array_equal(result.initial_remaining_burning_duration_s, [[500.0, 3200.0, 0.0, 0.0]])
    assert_allclose(result.endpoint_active_burning_probability, [[0.0, 0.0, 0.3, 0.0]])
    assert result.complete
    assert_allclose(probability, [[np.nan, 0.9, 0.6, 0.9]], equal_nan=True)
    assert_array_equal(arrival, [[3900.0, 0.0, -999_999.0, 2800.0]])


def test_missing_burned_cell_age_has_duration_limited_bounds_and_separate_validity():
    model = make_model(duration=np.array([[600.0, 3600.0, 7200.0]]))
    result = model.predict_from_new_burn_probability_details(
        [[np.nan, np.nan, np.nan]], already_burned_mask=np.ones((1, 3), bool),
        arrival_time_s=[[np.nan, np.nan, np.nan]], current_time_s=1000.0,
        arrival_valid=np.zeros((1, 3), bool),
    )
    # Conditional on being already burned, the maximum remaining duration is
    # T, attained by arrival at the cutoff. Arrival can also be sufficiently old
    # that no flaming remains. T==D is extinct at the endpoint by [A,A+T).
    upper_mean = np.array([[1 / 6, 1.0, 1.0]])
    upper_endpoint = np.array([[0.0, 0.0, 1.0]])
    upper_flux = model.heat_model.predict_details(upper_mean).incident_heat_flux_w_m2
    upper_endpoint_flux = model.heat_model.predict_details(upper_endpoint).incident_heat_flux_w_m2
    assert_array_equal(result.new_burn_probability, [[0.0, 0.0, 0.0]])
    assert_array_equal(result.probability_valid, [[True, True, True]])
    assert_array_equal(result.initial_burning_valid, [[False, False, False]])
    assert_array_equal(result.active_burning_valid, [[False, False, False]])
    assert_array_equal(result.endpoint_active_burning_valid, [[True, True, False]])
    assert np.isnan(result.initial_active_burning_probability).all()
    assert np.isnan(result.initial_remaining_burning_duration_s).all()
    assert np.isnan(result.mean_active_burning_probability).all()
    assert_allclose(result.endpoint_active_burning_probability, [[0.0, 0.0, np.nan]], equal_nan=True)
    assert np.isnan(result.expected_heat_flux_w_m2).all()
    assert np.isnan(result.expected_incident_energy_j_m2).all()
    assert_array_equal(result.heat_flux_lower_bound_w_m2, np.zeros((1, 3)))
    assert_allclose(result.heat_flux_upper_bound_w_m2, upper_flux, rtol=2e-14)
    assert_allclose(result.incident_energy_upper_bound_j_m2, upper_flux * 3600, rtol=2e-14)
    assert_allclose(result.endpoint_heat_flux_upper_bound_w_m2, upper_endpoint_flux, rtol=2e-14)
    flame_map = result.endpoint_flame_map()
    assert_array_equal(flame_map.valid, [[True, True, False]])
    assert_allclose(flame_map.probability, [[0.0, 0.0, np.nan]], equal_nan=True)
    assert not result.complete
    assert not result.endpoint_complete
    assert np.isnan(result.expected_endpoint_heat_flux_w_m2).all()


def test_unknown_present_activity_can_still_have_exactly_extinct_endpoint_heat():
    model = make_model(duration=np.array([[600.0, 3600.0]]))
    result = model.predict_from_new_burn_probability_details(
        [[np.nan, np.nan]], already_burned_mask=np.ones((1, 2), bool),
        arrival_time_s=[[np.nan, np.nan]], current_time_s=1000.0,
    )
    # Every admissible past arrival extinguishes by c+D when T<=D, even though
    # its initial activity and the heat accumulated during the hour are unknown.
    assert not result.complete
    assert result.endpoint_complete
    assert np.isnan(result.expected_heat_flux_w_m2).all()
    assert_array_equal(result.expected_endpoint_heat_flux_w_m2, [[0.0, 0.0]])
    assert_array_equal(result.endpoint_heat_flux_lower_bound_w_m2, [[0.0, 0.0]])
    assert_array_equal(result.endpoint_heat_flux_upper_bound_w_m2, [[0.0, 0.0]])
    assert_array_equal(result.endpoint_active_burning_valid, [[True, True]])
    assert_array_equal(result.endpoint_flame_map().probability, [[0.0, 0.0]])


def test_probability_fallback_does_not_resolve_unknown_existing_fire_age():
    model = make_model(duration=7200.0)
    result = model.predict_from_new_burn_probability_details(
        [[np.nan, np.nan]], already_burned_mask=np.array([[True, False]]),
        arrival_time_s=[[np.nan, 500.0]], current_time_s=100.0,
        unknown_new_burn_probability=0.4,
    )
    assert_array_equal(result.new_burn_probability, [[0.0, 0.4]])
    assert_array_equal(result.externally_supplied_probability_mask, [[False, True]])
    assert_array_equal(result.probability_valid, [[True, True]])
    assert_array_equal(result.initial_burning_valid, [[False, True]])
    assert_allclose(result.mean_active_burning_probability, [[np.nan, 0.2]], equal_nan=True)
    assert_allclose(result.endpoint_active_burning_probability, [[np.nan, 0.4]], equal_nan=True)
    assert not result.complete


def test_missing_age_of_zero_emission_source_preserves_complete_heat():
    model = make_model(duration=7200.0, fuel=np.array([[0.0, 1.0]]))
    result = model.predict_from_new_burn_probability_details(
        [[np.nan, 0.4]], already_burned_mask=np.array([[True, False]]),
        arrival_time_s=[[np.nan, np.nan]], current_time_s=0.0,
    )
    reference = model.predict_from_new_burn_probability_details(
        [[0.0, 0.4]], already_burned_mask=np.array([[True, False]]),
    )
    assert result.complete
    assert np.isnan(result.mean_active_burning_probability[0, 0])
    assert_allclose(result.expected_heat_flux_w_m2, reference.expected_heat_flux_w_m2, rtol=2e-14)
    assert_allclose(result.heat_flux_lower_bound_w_m2, result.heat_flux_upper_bound_w_m2, rtol=2e-14)


def test_raw_predictor_entry_points_use_arrival_ages_and_keep_predictor_inputs_current():
    predictor = DeterministicPredictor([[0.9, 0.2]])
    model = make_model(predictor, duration=7200.0, epsg=32652)
    burned = np.array([[1.0, 0.0]])
    environment = np.zeros((2, 1, 2))
    timing = dict(arrival_time_s=[[0.0, 10_000.0]], current_time_s=100.0)
    details = model.predict_details(
        burned, environment, channel_names=predictor.channel_names, **timing,
    )
    flux, coordinates = model.predict(
        burned, environment, channel_names=predictor.channel_names, **timing,
    )
    saved_flux, saved_coordinates = model.predict_from_new_burn_probability(
        [[np.nan, 0.2]], already_burned_mask=np.array([[True, False]]), **timing,
    )
    assert_allclose(details.expected_heat_flux_w_m2, flux)
    assert_allclose(saved_flux, flux)
    assert_allclose(saved_coordinates, coordinates)
    assert_array_equal(details.initial_remaining_burning_duration_s, [[7100.0, 0.0]])
    assert_array_equal(details.endpoint_active_burning_probability, [[1.0, 0.2]])
    assert len(predictor.calls) == 2
    for received_burned, received_environment, options in predictor.calls:
        assert_array_equal(received_burned.numpy(), burned)
        assert_array_equal(received_environment.numpy(), environment)
        assert "arrival_time_s" not in options
        assert "current_time_s" not in options


def test_default_sample_arrival_bridge_converts_hours_and_ignores_future_labels():
    predictor = DeterministicPredictor([[0.9, 0.2, 0.9]])
    model = make_model(predictor, duration=7200.0)

    class NoFutureLabels(dict):
        forbidden = {"newly_burned_area", "future_burned_area", "future_labels", "arrival_std_hours"}

        def __getitem__(self, name):
            assert name not in self.forbidden, f"prediction consumed future label {name}"
            return super().__getitem__(name)

        def get(self, name, default=None):
            assert name not in self.forbidden, f"prediction consumed future label {name}"
            return super().get(name, default)

    sample = NoFutureLabels(_sample(
        model, predictor, [[1.0, 0.0, 1.0]],
        arrival_hours=np.array([[[1.75, 20.0, 0.0]]]),
        elapsed_hours=np.array([2.0]), arrival_valid=np.ones((1, 1, 3), bool),
        time_valid=np.array([True]), epsg=32652,
        future_labels=object(), future_burned_area=object(),
        newly_burned_area=object(), arrival_std_hours=object(),
    ))
    result = model.predict_sample_details(sample)
    assert_array_equal(result.initial_active_burning_probability, [[1.0, 0.0, 0.0]])
    assert_array_equal(result.initial_remaining_burning_duration_s, [[6300.0, 0.0, 0.0]])
    assert_array_equal(result.endpoint_active_burning_probability, [[1.0, 0.2, 0.0]])
    flux, coordinates = model.predict_sample(sample)
    assert_allclose(flux, result.expected_heat_flux_w_m2)
    assert coordinates.shape == (1, 3, 2)
    assert len(predictor.calls) == 2


class NoTimingReads(dict):
    forbidden = {"arrival_hours", "arrival_valid", "elapsed_hours"}

    def __getitem__(self, name):
        assert name not in self.forbidden, f"unexpected retrospective timing read {name}"
        return super().__getitem__(name)

    def get(self, name, default=None):
        assert name not in self.forbidden, f"unexpected retrospective timing read {name}"
        return super().get(name, default)


def test_sample_arrival_option_false_does_not_read_arrival_or_elapsed_fields():
    predictor = DeterministicPredictor([[0.0, 0.2]])
    model = make_model(predictor, duration=7200.0)
    sample = NoTimingReads(_sample(
        model, predictor, [[1.0, 0.0]],
        arrival_hours=object(), arrival_valid=object(), elapsed_hours=object(),
    ))
    result = model.predict_sample_details(sample, initial_burning_from_arrival=False)
    assert_array_equal(result.initial_active_burning_probability, [[0.0, 0.0]])
    assert_array_equal(result.endpoint_active_burning_probability, [[0.0, 0.2]])
    assert result.complete


def test_explicit_sample_present_fire_overrides_automatic_arrival_without_reading_it():
    predictor = DeterministicPredictor([[0.0, 0.2]])
    model = make_model(predictor, duration=7200.0)
    sample = NoTimingReads(_sample(
        model, predictor, [[1.0, 0.0]],
        arrival_hours=object(), arrival_valid=object(), elapsed_hours=object(),
    ))
    result = model.predict_sample_details(
        sample, initial_active_burning_probability=[[0.4, 0.0]],
        initial_remaining_burning_duration_s=[[100.0, 0.0]],
    )
    assert_allclose(result.mean_active_burning_probability, [[0.4 * 100 / 3600, 0.1]])
    assert_array_equal(result.initial_active_burning_probability, [[0.4, 0.0]])
    assert_array_equal(result.initial_remaining_burning_duration_s, [[100.0, 0.0]])


def test_sample_without_arrival_fields_retains_new_ignition_only_behavior():
    predictor = DeterministicPredictor([[0.0, 0.2]])
    model = make_model(predictor, duration=7200.0)
    result = model.predict_sample_details(_sample(model, predictor, [[1.0, 0.0]]))
    assert_array_equal(result.initial_active_burning_probability, [[0.0, 0.0]])
    assert_array_equal(result.initial_burning_valid, [[True, True]])
    assert_allclose(result.mean_active_burning_probability, [[0.0, 0.1]])
    assert result.complete


@pytest.mark.parametrize("timing", [
    {"arrival_hours": np.array([[[0.0]]])},
    {"elapsed_hours": np.array([1.0])},
    {"arrival_valid": np.array([[[True]]])},
])
def test_partial_sample_arrival_fields_are_rejected_before_predicting(timing):
    predictor = DeterministicPredictor([[0.0]])
    model = make_model(predictor)
    with pytest.raises(ValueError):
        model.predict_sample_details(_sample(model, predictor, [[1.0]], **timing))
    assert not predictor.calls


@pytest.mark.parametrize("options", [
    {"arrival_time_s": [[0.0]]},
    {"current_time_s": 100.0},
    {"arrival_valid": np.array([[True]])},
    {"arrival_time_s": [[0.0]], "current_time_s": 100.0,
     "initial_active_burning_probability": [[1.0]],
     "initial_remaining_burning_duration_s": 20.0},
])
def test_partial_or_conflicting_raw_current_burning_inputs_fail(options):
    with pytest.raises(ValueError):
        make_model().predict_from_new_burn_probability_details(
            [[0.0]], already_burned_mask=np.array([[True]]), **options,
        )


def test_raw_arrival_bridge_requires_explicit_already_burned_support():
    with pytest.raises(ValueError, match="already.burned"):
        make_model().predict_from_new_burn_probability_details(
            [[0.0]], arrival_time_s=[[0.0]], current_time_s=100.0,
        )


def test_future_arrival_in_known_burned_cell_is_rejected():
    with pytest.raises(ValueError):
        make_model().predict_from_new_burn_probability_details(
            [[0.0]], already_burned_mask=np.array([[True]]),
            arrival_time_s=[[101.0]], current_time_s=100.0,
        )


@pytest.mark.parametrize("options", [
    {"arrival_time_s": [[0.0, 0.0]], "current_time_s": 100.0},
    {"arrival_time_s": [[0.0]], "current_time_s": [100.0]},
    {"arrival_time_s": [[0.0]], "current_time_s": True},
    {"arrival_time_s": [[0.0]], "current_time_s": timedelta(seconds=100)},
    {"arrival_time_s": [[0.0]], "current_time_s": np.inf},
    {"arrival_time_s": [["0"]], "current_time_s": 100.0},
    {"arrival_time_s": [[True]], "current_time_s": 100.0},
    {"arrival_time_s": [[np.inf]], "current_time_s": 100.0},
    {"arrival_time_s": [[np.nan]], "current_time_s": 100.0, "arrival_valid": np.array([[True]])},
    {"arrival_time_s": [[0.0]], "current_time_s": 100.0, "arrival_valid": np.array([[1]])},
    {"arrival_time_s": [[0.0]], "current_time_s": 100.0, "arrival_valid": np.array([[True, True]])},
])
def test_raw_arrival_contract_rejects_wrong_shape_type_or_false_validity(options):
    with pytest.raises(ValueError):
        make_model().predict_from_new_burn_probability_details(
            [[0.0]], already_burned_mask=np.array([[True]]), **options,
        )


def test_explicit_false_arrival_validity_ignores_placeholder_in_burned_cell():
    result = make_model(duration=7200.0).predict_from_new_burn_probability_details(
        [[0.0]], already_burned_mask=np.array([[True]]),
        arrival_time_s=[[900_000.0]], current_time_s=100.0,
        arrival_valid=np.array([[False]]),
    )
    assert_array_equal(result.probability_valid, [[True]])
    assert_array_equal(result.initial_burning_valid, [[False]])
    assert np.isnan(result.initial_active_burning_probability[0, 0])
    assert not result.complete
