"""Bounded end-to-end checks of explicit constant-hazard heat scenarios."""

from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pytest
import torch
from numpy.testing import assert_allclose, assert_array_equal
from scipy.integrate import quad

from wildfire.heat import AffineGrid, CombustionParameters, WildfireHeatModel


def make_heat_model(predictor=None, *, duration=900.0, **options):
    return WildfireHeatModel(
        predictor,
        grid=AffineGrid.from_cell_size(10.0),
        combustion=CombustionParameters(1.0, 18e6, duration, consumed_fraction=0.6),
        radiative_fraction=0.3,
        emission_height_m=5.0,
        ignition_time_model="constant_hazard",
        **options,
    )


class FixedRatePredictor(torch.nn.Module):
    """Return consistent probability/rate diagnostics without fitting a model."""

    def __init__(self, rate_per_hour, *, architecture="LearnedNonnegativeKernel"):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros((), dtype=torch.float64))
        self.rate_per_hour = float(rate_per_hour)
        self.contract = {"architecture": architecture}
        self.channel_names = ("example",)
        self.source_channels = self.channel_names
        self.categorical_classes = {}
        self.best_epoch = 0
        self.calls = []

    def forward(self, burned, environment, **options):
        self.calls.append(options)
        rates = torch.full_like(burned, self.rate_per_hour)
        return SimpleNamespace(
            probability=-torch.expm1(-rates), valid=torch.ones_like(burned, dtype=torch.bool),
            rate=rates, rate_valid=torch.ones_like(burned, dtype=torch.bool),
        )


def test_raw_probability_bridge_matches_independently_integrated_expected_flux():
    probability, duration, interval = 0.6, 900.0, 3600.0
    rate = -np.log1p(-probability) / interval
    mean = quad(
        lambda arrival: rate * np.exp(-rate * arrival) * min(duration, interval - arrival) / interval,
        0.0, interval, points=[interval - duration], epsabs=1e-14,
    )[0]
    endpoint = quad(lambda arrival: rate * np.exp(-rate * arrival), interval - duration, interval)[0]
    model = make_heat_model(duration=duration)
    result = model.predict_from_new_burn_probability_details([[probability]])
    expected_mean = model.heat_model.predict_details([[mean]]).incident_heat_flux_w_m2
    expected_endpoint = model.heat_model.predict_details([[endpoint]]).incident_heat_flux_w_m2
    assert result.complete and result.endpoint_complete
    assert_allclose(result.mean_active_burning_probability, [[mean]], rtol=2e-13)
    assert_allclose(result.expected_heat_flux_w_m2, expected_mean, rtol=2e-13)
    assert_allclose(result.expected_endpoint_heat_flux_w_m2, expected_endpoint, rtol=2e-13)
    assert_allclose(result.heat_flux_lower_bound_w_m2, result.heat_flux_upper_bound_w_m2)
    assert_allclose(result.expected_incident_energy_j_m2, expected_mean * interval)


def test_explicit_finite_rate_retains_saturated_probability_endpoint_information():
    model = make_heat_model(duration=1800.0)
    result = model.predict_from_new_burn_probability_details([[1.0]], ignition_rate_s_inv=[[50.0 / 3600.0]])
    endpoint = np.exp(-25.0) - np.exp(-50.0)
    assert result.complete
    assert result.endpoint_active_burning_probability[0, 0] > 0
    assert_allclose(result.endpoint_active_burning_probability, [[endpoint]], rtol=2e-14)
    assert result.expected_endpoint_heat_flux_w_m2[0, 0] > 0


def test_raw_probability_one_requires_explicit_finite_rate():
    with pytest.raises(ValueError, match="q=1"):
        make_heat_model().predict_from_new_burn_probability_details([[1.0]])


def test_unknown_source_endpoint_upper_encloses_interior_hazard_maximum():
    duration, interval = 300.0, 3600.0
    model = make_heat_model(duration=duration)
    incomplete = model.predict_from_new_burn_probability_details([[0.4, np.nan]])
    ratio = duration / interval
    optimum_exposure = -np.log1p(-ratio) / ratio
    optimum_probability = -np.expm1(-optimum_exposure)
    completed = model.predict_from_new_burn_probability_details([[0.4, optimum_probability]])
    assert not incomplete.complete and not incomplete.endpoint_complete
    assert np.isnan(incomplete.expected_heat_flux_w_m2).all()
    assert_allclose(completed.expected_endpoint_heat_flux_w_m2, incomplete.endpoint_heat_flux_upper_bound_w_m2, rtol=2e-13)
    assert np.all(completed.expected_heat_flux_w_m2 <= incomplete.heat_flux_upper_bound_w_m2 + 1e-10)
    high_rate = model.predict_from_new_burn_probability_details(
        [[0.4, 1.0]], ignition_rate_s_inv=[[-np.log1p(-0.4) / interval, 1000.0 / interval]],
    )
    assert np.all(high_rate.expected_endpoint_heat_flux_w_m2 < completed.expected_endpoint_heat_flux_w_m2)


def test_missing_old_age_and_known_new_ignition_have_disjoint_duration_limited_bounds():
    durations = np.array([[600.0, 900.0]])
    model = make_heat_model(duration=durations)
    result = model.predict_from_new_burn_probability_details(
        [[np.nan, 0.4]], already_burned_mask=[[True, False]],
        arrival_time_s=[[np.nan, np.nan]], current_time_s=1000.0,
    )
    assert_array_equal(result.new_burn_probability, [[0.0, 0.4]])
    assert_array_equal(result.probability_valid, [[True, True]])
    assert not result.complete and result.endpoint_complete
    assert np.isnan(result.expected_heat_flux_w_m2).all()
    assert np.isfinite(result.expected_endpoint_heat_flux_w_m2).all()
    assert_allclose(result.endpoint_heat_flux_lower_bound_w_m2, result.endpoint_heat_flux_upper_bound_w_m2)
    known_mean = make_heat_model(duration=durations).predict_from_new_burn_probability_details([[0.0, 0.4]])
    old_upper_flux = model.heat_model.predict_details([[600.0 / 3600.0, 0.0]]).incident_heat_flux_w_m2
    assert_allclose(result.heat_flux_lower_bound_w_m2, known_mean.expected_heat_flux_w_m2)
    assert_allclose(result.heat_flux_upper_bound_w_m2, known_mean.expected_heat_flux_w_m2 + old_upper_flux)


def test_trained_predictor_rate_propagates_in_inverse_seconds():
    predictor = FixedRatePredictor(50.0)
    model = make_heat_model(predictor, duration=1800.0)
    result = model.predict_details([[0.0]], [[[1.0]]], channel_names=("example",))
    assert predictor.calls[0]["dt_hours"] == 1.0
    assert predictor.calls[0]["boundary"] == "unknown"
    assert_allclose(result.endpoint_active_burning_probability, [[np.exp(-25.0) - np.exp(-50.0)]], rtol=2e-14)


def test_bayesian_equivalent_rate_is_not_silently_used_as_constant_hazard():
    predictor = FixedRatePredictor(1.0, architecture="BayesianModelAverage")
    model = make_heat_model(predictor)
    with pytest.raises(ValueError, match="componentwise"):
        model.predict_details([[0.0]], [[[1.0]]], channel_names=("example",))


def test_unresolved_probability_mask_remains_authoritative_over_supplied_rate():
    model = make_heat_model()
    result = model.predict_from_new_burn_probability_details(
        [[0.5]], probability_valid=[[False]], ignition_rate_s_inv=[[0.1]],
    )
    assert not result.complete
    assert_array_equal(result.heat_flux_lower_bound_w_m2, [[0.0]])
    assert np.isnan(result.new_burn_probability).all()


def test_external_probability_fallback_accepts_matching_rate_and_rejects_contradiction():
    model = make_heat_model()
    supplied = model.predict_from_new_burn_probability_details(
        [[0.4, np.nan]], unknown_new_burn_probability=0.3,
        ignition_rate_s_inv=[[-np.log1p(-0.4) / 3600.0, -np.log1p(-0.3) / 3600.0]],
    )
    direct = model.predict_from_new_burn_probability_details([[0.4, 0.3]])
    assert supplied.complete
    assert_array_equal(supplied.externally_supplied_probability_mask, [[False, True]])
    assert_allclose(supplied.expected_heat_flux_w_m2, direct.expected_heat_flux_w_m2)
    assert_allclose(supplied.expected_endpoint_heat_flux_w_m2, direct.expected_endpoint_heat_flux_w_m2)
    with pytest.raises(ValueError, match="inconsistent"):
        model.predict_from_new_burn_probability_details(
            [[0.4, np.nan]], unknown_new_burn_probability=0.3,
            ignition_rate_s_inv=[[-np.log1p(-0.4) / 3600.0, 100.0]],
        )


def test_original_float32_saturation_is_consistent_with_finite_rate():
    model = make_heat_model(duration=1800.0)
    probability = np.array([[1.0]], dtype=np.float32)
    result = model.predict_from_new_burn_probability_details(
        probability, ignition_rate_s_inv=[[20.0 / 3600.0]],
    )
    assert_allclose(result.endpoint_active_burning_probability, [[np.exp(-10.0) - np.exp(-20.0)]], rtol=2e-14)
    with pytest.raises(ValueError, match="inconsistent"):
        model.predict_from_new_burn_probability_details(
            probability.astype(np.float64), ignition_rate_s_inv=[[20.0 / 3600.0]],
        )


def test_resolved_zero_probability_cannot_create_positive_rate_heat():
    with pytest.raises(ValueError, match="zero new-burning probability"):
        make_heat_model().predict_from_new_burn_probability_details(
            [[0.0]], ignition_rate_s_inv=[[1e-7 / 3600.0]],
        )


def test_float64_probability_one_requires_actual_native_dtype_saturation():
    exposure = 35.0
    assert -np.expm1(-exposure) < 1.0
    with pytest.raises(ValueError, match="inconsistent|saturat"):
        make_heat_model().predict_from_new_burn_probability_details(
            np.array([[1.0]], dtype=np.float64),
            ignition_rate_s_inv=[[exposure / 3600.0]],
        )


def test_tiny_positive_float32_probability_cannot_match_zero_rate():
    with pytest.raises(ValueError, match="inconsistent"):
        make_heat_model().predict_from_new_burn_probability_details(
            np.array([[1e-8]], dtype=np.float32), ignition_rate_s_inv=[[0.0]],
        )


def test_api_composition_preserves_reference_parameter_provenance_and_flux_enclosures():
    from wildfire.api import WildfireModel
    from wildfire.heat_transfer import HomogeneousAtmosphere, RadiativeFractionEstimate

    predictor = FixedRatePredictor(1.0)
    api_model = WildfireModel(predictor, {"contract": predictor.contract}, Path("/tmp/heat-test-checkpoint.pt"), "test-digest")
    combustion = CombustionParameters.from_fbfm40(
        [[101]], fuel_load_kg_m2=[[0.4]], consumed_fraction=[[0.2]],
        provenance={"fuel_loading": "explicit bounded synthetic test scenario"},
    )
    atmosphere = HomogeneousAtmosphere(0.005, "explicit synthetic absorption scenario")
    radiation = RadiativeFractionEstimate(0.3, "explicit synthetic flaming radiation fraction")
    model = api_model.heat_model(
        grid=AffineGrid.from_cell_size(10.0), combustion=combustion,
        radiative_fraction=radiation, emission_height_m=5.0,
        atmosphere=atmosphere, transfer_atol=1e-7, transfer_rtol=0.02,
        ignition_time_model="constant_hazard",
    )
    result = model.predict_details([[0.0]], [[[1.0]]], channel_names=("example",))
    assert model.ignition_time_model == "constant_hazard"
    assert model.heat_model.atmosphere is atmosphere
    assert model.heat_model.transfer_rtol == 0.02
    assert result.complete
    assert result.metadata["ignition_time_model"] == "constant_hazard"
    assert "exponential survival" in result.metadata["arrival_time_assumption"]
    assert result.metadata["combustion"] == combustion.provenance_dict()
    assert result.metadata["radiation"]["atmosphere"] == atmosphere.provenance_dict()
    assert np.all(result.heat_flux_lower_bound_w_m2 <= result.expected_heat_flux_w_m2)
    assert np.all(result.expected_heat_flux_w_m2 <= result.heat_flux_upper_bound_w_m2)
    assert np.all(result.heat_flux_lower_bound_w_m2 < result.heat_flux_upper_bound_w_m2)
