"""Independent checks of the new-burn/combustion/radiation integration.

No model is fitted in these tests. The deterministic wrapper deliberately has
an inadmissible raw score so confusing that score with probability fails loudly.
"""

from datetime import timedelta
from hashlib import sha256
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from numpy.testing import assert_allclose, assert_array_equal

from wildfire.heat import AffineGrid
from wildfire.heat import CombustionParameters
from wildfire.heat import EcologicalFuelMaps
from wildfire.heat import WildfireHeatModel


class DeterministicPredictor(torch.nn.Module):
    """Return supplied probabilities and retain the exact wrapper input call."""

    def __init__(self, probability, valid=None):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros((), dtype=torch.float64))
        self.probability = np.asarray(probability, dtype=np.float64)
        self.valid = np.isfinite(self.probability) if valid is None else np.asarray(valid, dtype=bool)
        self.best_epoch = 7
        self.channel_names = ("temperature", "fuel_moisture")
        self.source_channels = self.channel_names
        self.categorical_classes = {}
        self.calls = []

    def forward(self, burned, environment, **kwargs):
        self.calls.append((burned.clone(), environment.clone(), kwargs))
        assert not torch.is_grad_enabled()
        return SimpleNamespace(
            probability=torch.as_tensor(self.probability, device=burned.device, dtype=burned.dtype),
            valid=torch.as_tensor(self.valid, device=burned.device),
            rate=torch.full_like(burned, 123.0),
        )


def make_model(predictor=None, *, duration=900.0, fuel=1.0, radiative_fraction=0.3, **kwargs):
    return WildfireHeatModel(
        predictor,
        grid=AffineGrid.from_cell_size(10.0),
        combustion=CombustionParameters(fuel, 18e6, duration, consumed_fraction=0.6),
        radiative_fraction=radiative_fraction,
        emission_height_m=5.0,
        **kwargs,
    )


def test_saved_probability_tuple_retains_nan_heat_and_known_geographic_positions():
    model = make_model(epsg=32652)
    probability = np.array([[0.4, np.nan]])
    flux, coordinates = model.predict_from_new_burn_probability(probability)
    details = model.predict_from_new_burn_probability_details(probability)
    assert flux.shape == probability.shape
    assert coordinates.shape == probability.shape + (2,)
    assert np.isnan(flux).all()
    assert np.isfinite(coordinates).all()
    assert_allclose(flux, details.expected_heat_flux_w_m2, equal_nan=True)
    assert details.metadata["epsg"] == 32652


def test_predict_tuple_matches_saved_probability_heat_and_coordinates():
    predictor = DeterministicPredictor([[0.0, 0.2], [0.3, 0.4]])
    model = make_model(predictor, epsg=32652)
    burned = [[1.0, 0.0], [0.0, 0.0]]
    flux, coordinates = model.predict(burned, np.zeros((2, 2, 2)), channel_names=predictor.channel_names)
    reference_flux, reference_coordinates = model.predict_from_new_burn_probability(
        predictor.probability, already_burned_mask=np.asarray(burned, dtype=bool),
    )
    assert_allclose(flux, reference_flux)
    assert_allclose(coordinates, reference_coordinates)
    assert len(predictor.calls) == 1


def test_sample_tuple_uses_its_epsg_and_masks_only_padding_locations():
    predictor = DeterministicPredictor([[0.0, np.nan], [0.3, 0.4]])
    model = make_model(predictor)
    sample = dict(
        affine_transform=np.array(model.heat_model.grid.transform), epsg=np.array(32652),
        burned_area=np.array([[[1.0, 0.0], [0.0, 0.0]]]),
        features=np.zeros((2, 2, 2)), channel_names=predictor.channel_names,
        pixel_valid=np.array([[[True, True], [True, False]]]), time_valid=np.array([True]),
    )
    flux, coordinates = model.predict_sample(sample)
    assert flux.shape == (2, 2)
    assert coordinates.shape == (2, 2, 2)
    assert np.isnan(flux).all()
    assert np.isfinite(coordinates[0, 1]).all()  # Unknown outcome still has a real position.
    assert np.isnan(coordinates[1, 1]).all()  # Spatial padding has no position.
    assert model.epsg is None  # Sample CRS does not reconfigure a shared model.
    assert model.predict_sample_details(sample).metadata["epsg"] == 32652
    static_coordinates = coordinates.copy()
    sample["time_valid"] = np.array([False])
    _, coordinates = model.predict_sample(sample)
    assert_array_equal(coordinates, static_coordinates)


def test_heat_tuple_requires_epsg_and_rejects_sample_crs_disagreement_before_inference():
    predictor = DeterministicPredictor([[0.4]])
    local = make_model(predictor)
    with pytest.raises(ValueError, match="requires epsg"):
        local.predict([[0.0]], np.zeros((2, 1, 1)), channel_names=predictor.channel_names)
    with pytest.raises(ValueError, match="requires epsg"):
        local.predict_from_new_burn_probability([[0.4]])
    sample = dict(
        affine_transform=np.array(local.heat_model.grid.transform), burned_area=[[0.0]],
        features=np.zeros((2, 1, 1)), channel_names=predictor.channel_names,
    )
    with pytest.raises(ValueError, match="sample requires epsg"):
        local.predict_sample(sample)
    sample["epsg"] = 32652
    with pytest.raises(ValueError, match="epsg differs"):
        make_model(predictor, epsg=32651).predict_sample(sample)
    assert not predictor.calls


@pytest.mark.parametrize("duration", [60.0, 900.0, 3600.0, 7200.0])
def test_single_cell_interval_flux_and_dose_match_analytic_space_time_integral(duration):
    probability = 0.7
    model = make_model(duration=duration)
    result = model.predict_from_new_burn_probability_details([[probability]])
    # A 10 m square centered 5 m above the receiver subtends 2*pi/3 sr.
    # Integrate q*min(t,T)/D, the instantaneous uniform-arrival occupancy,
    # using its piecewise-linear breakpoints rather than the bridge's formula.
    times = np.unique([0.0, min(duration, 3600.0), 3600.0])
    instantaneous_active = probability * np.minimum(times, duration) / 3600.0
    time_integral = np.sum(0.5 * (instantaneous_active[1:] + instantaneous_active[:-1]) * np.diff(times))
    conditional_flux = 0.3 * 1.0 * 18e6 * 0.6 / duration / 6.0
    assert_allclose(result.expected_incident_energy_j_m2, [[conditional_flux * time_integral]], rtol=2e-14)
    assert_allclose(result.expected_heat_flux_w_m2 * 3600.0, result.expected_incident_energy_j_m2, rtol=2e-14)
    assert_allclose(result.endpoint_heat_flux_lower_bound_w_m2, [[conditional_flux * instantaneous_active[-1]]], rtol=2e-14)
    assert result.complete
    assert_array_equal(result.probability_valid, [[True]])


def test_cell_specific_burning_duration_matches_temporal_integral_of_spatial_flux():
    durations = np.array([[600.0, 1800.0], [3600.0, 7200.0]])
    probability = np.array([[0.8, 0.3], [0.6, 0.2]])
    model = make_model(duration=durations, fuel=np.array([[0.5, 1.0], [1.5, 2.0]]))
    result = model.predict_from_new_burn_probability_details(probability)
    times = np.unique(np.r_[0.0, np.minimum(durations.ravel(), 3600.0), 3600.0])
    instantaneous_flux = np.stack([
        model.heat_model.predict_details(probability * np.minimum(time, durations) / 3600.0).incident_heat_flux_w_m2
        for time in times
    ])
    independent_dose = np.sum(
        0.5 * (instantaneous_flux[1:] + instantaneous_flux[:-1]) * np.diff(times)[:, None, None], axis=0,
    )
    assert_allclose(result.expected_incident_energy_j_m2, independent_dose, rtol=3e-14)
    assert_allclose(result.heat_flux_lower_bound_w_m2, result.expected_heat_flux_w_m2)
    assert_allclose(result.heat_flux_upper_bound_w_m2, result.expected_heat_flux_w_m2)
    assert_allclose(result.expected_heat_flux_kw_m2, result.expected_heat_flux_w_m2 / 1000)


def test_unknown_source_affects_full_receiver_field_not_only_unknown_pixel():
    model = make_model()
    q = np.array([[0.5, np.nan], [0.1, 0.2]])
    result = model.predict_from_new_burn_probability_details(q)
    assert not result.complete
    assert np.isnan(result.expected_heat_flux_w_m2).all()
    assert np.isnan(result.expected_incident_energy_j_m2).all()
    assert np.isfinite(result.known_source_heat_flux_w_m2).all()
    assert np.all(result.heat_flux_upper_bound_w_m2 > result.heat_flux_lower_bound_w_m2)
    assert np.isnan(result.mean_active_burning_probability[0, 1])
    assert result.metadata["unresolved_emitting_source_cells"] == 1
    assert result.metadata["unresolved_probability_cells"] == 1
    assert_array_equal(result.original_probability_valid, np.isfinite(q))
    assert_array_equal(result.externally_supplied_probability_mask, np.zeros(q.shape, dtype=bool))


@pytest.mark.parametrize("unknown_values", [[0, 0], [0, 1], [1, 0], [1, 1], [0.25, 0.8]])
def test_unknown_probability_bounds_encompass_fully_specified_maps(unknown_values):
    model = make_model()
    incomplete_q = np.array([[0.5, np.nan], [np.nan, 0.1]])
    incomplete = model.predict_from_new_burn_probability_details(incomplete_q)
    completed_q = incomplete_q.copy()
    completed_q[np.isnan(completed_q)] = unknown_values
    completed = model.predict_from_new_burn_probability_details(completed_q)
    assert np.all(completed.expected_heat_flux_w_m2 >= incomplete.heat_flux_lower_bound_w_m2 - 1e-11)
    assert np.all(completed.expected_heat_flux_w_m2 <= incomplete.heat_flux_upper_bound_w_m2 + 1e-11)
    assert_allclose(incomplete.known_source_heat_flux_w_m2, incomplete.heat_flux_lower_bound_w_m2)
    assert_allclose(incomplete.incident_energy_upper_bound_j_m2, incomplete.heat_flux_upper_bound_w_m2 * 3600)


@pytest.mark.parametrize("cause", ["zero_fuel", "zero_radiation", "zero_transmission"])
def test_unresolved_zero_emission_source_does_not_invalidate_known_full_flux(cause):
    kwargs = {}
    if cause == "zero_fuel":
        kwargs["fuel"] = np.array([[1.0, 0.0]])
    elif cause == "zero_radiation":
        kwargs["radiative_fraction"] = np.array([[0.3, 0.0]])
    else:
        kwargs["atmospheric_transmissivity"] = 0.0
    model = make_model(**kwargs)
    result = model.predict_from_new_burn_probability_details([[0.4, np.nan]])
    assert result.complete
    assert np.isfinite(result.expected_heat_flux_w_m2).all()
    assert_allclose(result.heat_flux_lower_bound_w_m2, result.heat_flux_upper_bound_w_m2)
    assert result.metadata["unresolved_probability_cells"] == 1
    assert result.metadata["unresolved_emitting_source_cells"] == 0


def test_external_unknown_probability_is_marked_and_applied_only_to_missing_sources():
    model = make_model()
    q = np.array([[0.4, np.nan], [0.7, 0.2]])
    valid = np.array([[True, False], [False, True]])
    result = model.predict_from_new_burn_probability_details(
        q, probability_valid=valid, unknown_new_burn_probability=[[0.9, 0.3], [0.1, 0.8]],
    )
    assert_array_equal(result.new_burn_probability, [[0.4, 0.3], [0.1, 0.2]])
    reference = model.predict_from_new_burn_probability_details([[0.4, 0.3], [0.1, 0.2]])
    assert_allclose(result.expected_heat_flux_w_m2, reference.expected_heat_flux_w_m2)
    assert result.complete
    assert result.metadata["externally_supplied_probability_cells"] == 2
    assert result.metadata["original_probability_valid_cells"] == 2
    assert_array_equal(result.original_probability_valid, valid)
    assert_array_equal(result.externally_supplied_probability_mask, ~valid)
    assert_array_equal(result.probability_valid, np.ones(q.shape, dtype=bool))


def test_already_burned_state_without_timing_retains_unknown_current_fire():
    predictor = DeterministicPredictor([[0.9, 0.4], [0.2, 0.1]])
    model = make_model(predictor)
    burned = np.array([[1, 0], [0, 0]])
    result = model.predict_details(burned, np.zeros((2, 2, 2)), channel_names=predictor.channel_names)
    reference = model.predict_from_new_burn_probability_details([[0, 0.4], [0.2, 0.1]])
    assert np.isnan(result.expected_heat_flux_w_m2).all()
    assert_allclose(result.known_source_heat_flux_w_m2, reference.expected_heat_flux_w_m2)
    assert np.isnan(result.mean_active_burning_probability[0, 0])
    assert result.new_burn_probability[0, 0] == 0
    assert "unresolved burn-start timing" in result.metadata["scope"]


def test_supplied_present_fire_adds_only_explicit_remaining_burning_time():
    model = make_model(duration=900.0)
    new_probability = [[np.nan, 0.5]]
    old_mask = np.array([[True, False]])
    result = model.predict_from_new_burn_probability_details(
        new_probability,
        already_burned_mask=old_mask,
        initial_active_burning_probability=[[0.6, 0]],
        initial_remaining_burning_duration_s=[[600.0, 0.0]],
    )
    # Existing fire burns for 600 s if active initially; new arrivals have the
    # independently integrated mean factor 7/32 for T/D=1/4.
    expected_active = np.array([[0.6 * 600 / 3600, 0.5 * 7 / 32]])
    reference = model.heat_model.predict_details(expected_active).incident_heat_flux_w_m2
    assert_allclose(result.expected_heat_flux_w_m2, reference)
    assert_allclose(result.mean_active_burning_probability, expected_active)
    assert result.endpoint_active_burning_probability[0, 0] == 0
    assert_array_equal(result.probability_valid, [[True, True]])
    assert "caller-supplied present" in result.metadata["scope"]


@pytest.mark.parametrize("q", [[[0.1, 0.0]], [[np.nan, 0.0]]])
def test_initial_fire_cannot_overlap_possible_first_new_burning(q):
    with pytest.raises(ValueError, match="disjoint|already.burned"):
        make_model().predict_from_new_burn_probability_details(
            q, already_burned_mask=np.array([[False, False]]),
            initial_active_burning_probability=[[0.5, 0]],
            initial_remaining_burning_duration_s=100.0,
        )


def test_initial_fire_requires_explicit_known_already_burned_support():
    with pytest.raises(ValueError, match="already.burned|mask"):
        make_model().predict_from_new_burn_probability_details(
            [[0.0, 0.0]], initial_active_burning_probability=[[0.5, 0]],
            initial_remaining_burning_duration_s=100.0,
        )


@pytest.mark.parametrize("kwargs", [
    {"initial_active_burning_probability": [[0.1]]},
    {"initial_remaining_burning_duration_s": 10},
])
def test_initial_probability_and_remaining_duration_must_be_supplied_together(kwargs):
    with pytest.raises(ValueError):
        make_model().predict_from_new_burn_probability_details([[0.0]], **kwargs)


def test_prediction_wrapper_uses_probability_and_forwards_raw_current_context():
    q = np.array([[0.0, 0.2], [0.3, np.nan]])
    predictor = DeterministicPredictor(q)
    model = make_model(predictor)
    burned = torch.tensor([[[1.0, 0.0], [0.0, 0.0]]], dtype=torch.float32)
    features = torch.tensor([[[280.0, 285.0], [290.0, 295.0]], [[0.2, 0.3], [0.4, 0.5]]])
    burned_valid = torch.ones_like(burned, dtype=torch.bool)
    feature_valid = torch.ones_like(features, dtype=torch.bool)
    result = model.predict_details(
        burned, features, channel_names=predictor.channel_names,
        burned_area_valid=burned_valid, feature_valid=feature_valid,
    )
    called_burned, called_features, context = predictor.calls[0]
    assert_array_equal(called_burned.numpy(), burned.numpy())
    assert_array_equal(called_features.numpy(), features.numpy())
    assert called_burned.dtype == predictor.anchor.dtype
    assert context["channel_names"] == predictor.channel_names
    assert context["dt_hours"] == 1.0
    assert context["boundary"] == "unknown"
    assert_array_equal(context["burned_area_valid"].numpy(), burned_valid.numpy())
    assert_array_equal(context["feature_valid"].numpy(), feature_valid.numpy())
    assert_allclose(result.new_burn_probability, q, equal_nan=True)
    assert not result.complete


def test_prediction_current_active_requires_known_already_burned_support():
    predictor = DeterministicPredictor([[0, 0]])
    with pytest.raises(ValueError, match="known already-burned"):
        make_model(predictor).predict_details(
            [[1, 0]], np.zeros((2, 1, 2)), channel_names=predictor.channel_names,
            initial_active_burning_probability=[[0, 0.5]],
            initial_remaining_burning_duration_s=100,
        )
    assert not predictor.calls


def test_predict_sample_uses_aligned_current_state_and_ignores_future_labels():
    predictor = DeterministicPredictor([[0, 0.2], [0.3, 0.4]])
    model = make_model(predictor)
    sample = dict(
        affine_transform=torch.tensor(model.heat_model.grid.transform),
        burned_area=torch.tensor([[[1.0, 0], [0, 0]]]),
        features=torch.zeros((2, 2, 2)),
        channel_names=predictor.channel_names,
        future_burned_area=object(), arrival_time=object(),
    )
    result = model.predict_sample_details(sample, include_previous_burning=False)
    assert result.complete
    assert len(predictor.calls) == 1
    assert_allclose(result.new_burn_probability, predictor.probability)
    sample["affine_transform"] = np.array(model.heat_model.grid.transform) + [0, 0, 1, 0, 0, 0]
    with pytest.raises(ValueError, match="affine grid differs"):
        model.predict_sample_details(sample)
    assert len(predictor.calls) == 1


@pytest.mark.parametrize("interval", [60.0, 1800.0, 7200.0, np.nan, np.inf, True, [3600], "3600", timedelta(seconds=3600), np.timedelta64(3600, "s")])
def test_interval_is_exact_numeric_one_hour(interval):
    with pytest.raises((TypeError, ValueError)):
        make_model(interval_s=interval)


@pytest.mark.parametrize("probability", [[], [0.5], np.ones((2, 2, 2)), [[-0.1]], [[1.01]], [[np.inf]], [[0.5 + 0j]], [["0.5"]], np.ma.array([[0.5]], mask=[[True]])])
def test_invalid_new_burn_probability_shape_type_and_range_rejected(probability):
    with pytest.raises((TypeError, ValueError)):
        make_model().predict_from_new_burn_probability_details(probability)


@pytest.mark.parametrize("mask", [[[1, 0]], [[True]], np.ma.array([[True, True]], mask=[[False, True]])])
def test_validity_requires_complete_boolean_mask_with_exact_shape(mask):
    with pytest.raises(ValueError):
        make_model().predict_from_new_burn_probability_details([[0.3, 0.4]], probability_valid=mask)


def test_marking_missing_probability_valid_is_rejected():
    with pytest.raises(ValueError, match="valid new-burn"):
        make_model().predict_from_new_burn_probability_details([[np.nan]], probability_valid=[[True]])


def test_complete_probability_singleton_batch_dimensions_are_supported():
    result = make_model().predict_from_new_burn_probability_details(np.array([[[[0.4, 0.1]]]]))
    assert result.expected_heat_flux_w_m2.shape == (1, 2)


def test_combustion_duration_and_source_arrays_must_match_probability_grid():
    with pytest.raises(ValueError, match="shape"):
        make_model(duration=np.ones((2, 2)) * 10).predict_from_new_burn_probability_details([[0.1]])
    with pytest.raises(ValueError, match="shape"):
        make_model(fuel=np.ones((2, 2))).predict_from_new_burn_probability_details([[0.1]])


def test_predict_requires_trained_predictor_but_saved_probability_bridge_does_not():
    model = make_model()
    with pytest.raises(ValueError, match="predictor is absent"):
        model.predict_details([[0]], np.zeros((2, 1, 1)), channel_names=("x", "y"))
    assert model.predict_from_new_burn_probability_details([[0.5]]).complete


@pytest.mark.parametrize("architecture", ["EnvironmentConditionedConvolution", "LearnedNonnegativeKernel"])
def test_checkpoint_dispatch_preserves_loaded_wrapper_and_records_provenance(tmp_path, monkeypatch, architecture):
    import wildfire.inference as exponential

    path = tmp_path / "checkpoint.pt"
    saved_mean = torch.tensor([281.0, 0.3])
    torch.save({"contract": {"architecture": architecture}, "normalization_mean": saved_mean}, path)
    wrapper = DeterministicPredictor([[0.3]])
    calls = []

    def load(selected_path, *, device):
        calls.append((selected_path, device))
        assert_array_equal(torch.load(selected_path, weights_only=True)["normalization_mean"].numpy(), saved_mean.numpy())
        return wrapper

    monkeypatch.setattr(exponential, "load_trained_model", load)
    model = WildfireHeatModel.from_checkpoint(
        path, grid=AffineGrid.from_cell_size(10),
        combustion=CombustionParameters(1, 18e6, 900),
        radiative_fraction=0.3, emission_height_m=5,
    )
    assert model.predictor is wrapper
    assert calls == [(path.resolve(), "cpu")]
    assert model.predictor_provenance["checkpoint_sha256"] == sha256(path.read_bytes()).hexdigest()
    assert model.predictor_provenance["architecture"] == architecture
    assert model.predictor_provenance["best_epoch"] == 7


def test_unknown_checkpoint_architecture_rejected_before_loading_model(tmp_path):
    path = tmp_path / "unsupported.pt"
    torch.save({"contract": {"architecture": "UnrelatedModel"}}, path)
    with pytest.raises(ValueError, match="Unsupported wildfire checkpoint architecture"):
        WildfireHeatModel.from_checkpoint(path)


def test_signed_checkpoint_is_explicitly_retired_before_heat_loading(tmp_path):
    path = tmp_path / "retired.pt"
    torch.save({"contract": {"architecture": "DirectEnvironmentConditionedConvolution"}}, path)
    with pytest.raises(ValueError, match="signed direct-convolution model has been retired"):
        WildfireHeatModel.from_checkpoint(path)


def test_ecological_mapped_fraction_and_explicit_unknown_fuel_change_source_heat():
    ecology = EcologicalFuelMaps(
        fuel_load_kg_m2=[[1.0, 2.0]], valid=[[True, False]],
        coverage_fraction=[[1.0, 0.5]], provenance={"source": "test reference loading"},
    )
    with pytest.raises(ValueError, match="incomplete fuel coverage"):
        ecology.combustion_parameters(
            heat_of_combustion_j_kg=18e6, burning_duration_s=900, consumed_fraction=0.6,
        )
    parameters = ecology.combustion_parameters(
        heat_of_combustion_j_kg=18e6, burning_duration_s=900, consumed_fraction=0.6,
        fallback_fuel_load_kg_m2=0.4,
    )
    assert_allclose(parameters.fuel_load_kg_m2, [[1.0, 1.2]])
    model = WildfireHeatModel(
        None, grid=AffineGrid.from_cell_size(10), combustion=parameters,
        radiative_fraction=0.3, emission_height_m=5,
    )
    result = model.predict_from_new_burn_probability_details([[0.5, 0.5]])
    reference = make_model(fuel=np.array([[1.0, 1.2]])).predict_from_new_burn_probability_details([[0.5, 0.5]])
    assert_allclose(result.expected_heat_flux_w_m2, reference.expected_heat_flux_w_m2)
