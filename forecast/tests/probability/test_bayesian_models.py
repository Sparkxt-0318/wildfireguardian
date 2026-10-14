"""Bayesian evidence, predictive mixture, and missing-data contracts."""

import json
import math

import numpy as np
import pytest
import torch

from wildfire.models import (
    BayesianBurnModel,
    TrainedBurnModel,
    bayesian_model_weights,
    build_kernel_model,
    initialize_kernel_rate,
    kernel_model_configuration,
)


@pytest.fixture(autouse=True)
def _few_threads():
    original = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(original)


def _component(size, rate, *, architecture="constant", dropout=0.0):
    model = build_kernel_model(
        1, size, architecture, hidden_channels=6, depth=2, dropout=dropout,
    ).double()
    initialize_kernel_rate(model, rate)
    contract = {
        "format_version": 1,
        "architecture": "LearnedNonnegativeKernel",
        "in_channels": 1,
        "channels": ["weather.temperature_2m"],
        "kernel_size": size,
        "kernel_model": kernel_model_configuration(model),
        "dt_hours": 1.0,
        "center_rate": 0.0,
        "eligibility": "at_least_one_burned_neighbor",
    }
    return TrainedBurnModel(
        model, torch.tensor([10.0], dtype=torch.float64),
        torch.tensor([2.0], dtype=torch.float64), contract, best_epoch=3,
    ).double()


def _ensemble(components=None, log_weights=None):
    if components is None:
        components = [_component(3, 0.15), _component(5, 0.8)]
    if log_weights is None:
        log_weights = [math.log(0.3), math.log(0.7)]
    contract = {
        "format_version": 1,
        "architecture": "BayesianModelAverage",
        "in_channels": 1,
        "channels": ["weather.temperature_2m"],
        "kernel_size": max(component.model.kernel_size for component in components),
        "dt_hours": 1.0,
        "center_rate": 0.0,
        "eligibility": "at_least_one_burned_neighbor",
    }
    return BayesianBurnModel(components, log_weights, contract)


def _prediction_inputs(batch=1):
    burned = torch.zeros(batch, 1, 9, 9, dtype=torch.float64)
    burned[:, 0, 3, 4] = 1
    raw_environment = torch.full((batch, 1, 9, 9), 12.0, dtype=torch.float64)
    return burned, raw_environment


def test_posterior_is_bayes_rule_from_shared_binary_observations():
    probabilities = np.array([[0.8, 0.2], [0.75, 0.6], [0.1, 0.4]])
    target = np.array([1, 0, 0])
    # Three independent Bernoulli observations give likelihoods 0.18 and 0.048.
    result = bayesian_model_weights(probabilities, target)
    np.testing.assert_allclose(result["prior_weights"], [0.5, 0.5], rtol=0, atol=1e-15)
    np.testing.assert_allclose(
        result["log_likelihood"], np.log([0.18, 0.048]), rtol=0, atol=1e-14,
    )
    expected = np.array([0.18, 0.048]) / 0.228
    np.testing.assert_allclose(result["posterior_weights"], expected, rtol=0, atol=1e-14)
    np.testing.assert_allclose(result["log_posterior_weights"], np.log(expected), atol=1e-14)
    assert result["sample_count"] == 3
    assert result["effective_sample_count"] == 3
    assert result["likelihood_power"] == 1
    assert result["evidence_mode"] == "ordinary_conditional_plug_in_bayes"
    # All evidence fields must be portable JSON, including exact impossible support.
    json.dumps(result, allow_nan=False)


def test_nonuniform_prior_is_normalized_and_multiplied_by_likelihood():
    probabilities = [[0.8, 0.2], [0.75, 0.6], [0.1, 0.4]]
    result = bayesian_model_weights(probabilities, [1, 0, 0], prior_weights=[1, 3])
    np.testing.assert_allclose(result["prior_weights"], [0.25, 0.75], rtol=0, atol=1e-15)
    # Unnormalized joint masses are 0.25*0.18=0.045 and 0.75*0.048=0.036.
    np.testing.assert_allclose(result["posterior_weights"], [5 / 9, 4 / 9], atol=1e-14)


def test_exact_zero_likelihood_is_zero_posterior_without_probability_clipping():
    result = bayesian_model_weights([[1.0, 0.0], [0.0, 1.0]], [1, 0])
    assert result["log_likelihood"] == [0.0, None]
    assert result["log_posterior_weights"] == [0.0, None]
    assert result["posterior_weights"] == [1.0, 0.0]
    json.dumps(result, allow_nan=False)


def test_zero_prior_excludes_a_model_even_when_its_likelihood_is_positive():
    result = bayesian_model_weights([[0.2, 0.8]], [1], prior_weights=[1.0, 0.0])
    assert result["posterior_weights"] == [1.0, 0.0]
    assert result["log_posterior_weights"] == [0.0, None]
    assert result["log_likelihood"][1] == pytest.approx(math.log(0.8))


@pytest.mark.parametrize(
    "probabilities,target,prior",
    [([[0.0, 0.0]], [1], None), ([[0.0, 1.0]], [1], [1.0, 0.0])],
)
def test_all_models_impossible_under_the_prior_raise(probabilities, target, prior):
    with pytest.raises(ValueError):
        bayesian_model_weights(probabilities, target, prior_weights=prior)


def test_log_space_evidence_preserves_support_after_numeric_posterior_underflow():
    count = 10000
    result = bayesian_model_weights(
        np.tile([0.2, 0.8], (count, 1)), np.ones(count),
    )
    expected_log_odds = count * math.log(0.2 / 0.8)
    np.testing.assert_allclose(
        result["log_likelihood"], count * np.log([0.2, 0.8]), rtol=1e-13,
    )
    assert result["posterior_weights"] == [0.0, 1.0]
    assert result["log_posterior_weights"][0] == pytest.approx(expected_log_odds)
    assert result["log_posterior_weights"][0] is not None
    assert result["log_posterior_weights"][1] == pytest.approx(0.0)


def test_likelihood_power_tempers_evidence_without_tempering_the_prior():
    result = bayesian_model_weights(
        [[0.81, 0.25]], [1], prior_weights=[1, 3], likelihood_power=0.5,
    )
    # The generalized joint masses are 0.25*sqrt(0.81) and 0.75*sqrt(0.25).
    expected = np.array([0.25 * 0.9, 0.75 * 0.5])
    expected /= expected.sum()
    np.testing.assert_allclose(result["posterior_weights"], expected, atol=1e-14)
    assert result["likelihood_power"] == 0.5
    ordinary = bayesian_model_weights([[0.81, 0.25]], [1])
    assert result["evidence_mode"] != ordinary["evidence_mode"]


def test_weighted_evidence_is_scale_invariant_and_identified_as_generalized():
    probabilities = np.array([[0.8, 0.2], [0.3, 0.7]])
    target = np.array([1, 0])
    weighted = bayesian_model_weights(probabilities, target, sample_weight=[1.0, 3.0])
    rescaled = bayesian_model_weights(probabilities, target, sample_weight=[1e200, 3e200])
    # Normalize weights to mean one, giving likelihood powers 0.5 and 1.5.
    log_likelihood = np.log([0.8, 0.2]) * 0.5 + np.log([0.7, 0.3]) * 1.5
    expected = np.exp(log_likelihood - np.max(log_likelihood))
    expected /= expected.sum()
    np.testing.assert_allclose(weighted["log_likelihood"], log_likelihood, atol=1e-14)
    np.testing.assert_allclose(weighted["posterior_weights"], expected, atol=1e-14)
    np.testing.assert_allclose(rescaled["posterior_weights"], expected, atol=1e-14)
    ordinary = bayesian_model_weights(probabilities, target)
    assert weighted["evidence_mode"] != ordinary["evidence_mode"]
    assert rescaled["effective_sample_count"] == weighted["effective_sample_count"]
    assert weighted["effective_sample_count"] == pytest.approx(1.6)
    assert weighted["evidence_mode"] == "generalized_conditional_plug_in_bayes"


@pytest.mark.parametrize(
    "probabilities,target,options",
    [
        ([], [], {}),
        ([0.2, 0.8], [1], {}),
        ([[0.2, 0.8]], [1, 0], {}),
        ([[0.2, 0.8]], [0.5], {}),
        ([[float("nan"), 0.8]], [1], {}),
        ([[1.2, 0.8]], [1], {}),
        ([[0.2, -0.1]], [1], {}),
        ([[0.2, 0.8]], [1], {"prior_weights": [1]}),
        ([[0.2, 0.8]], [1], {"prior_weights": [-1, 2]}),
        ([[0.2, 0.8]], [1], {"prior_weights": [0, 0]}),
        ([[0.2, 0.8]], [1], {"sample_weight": [0]}),
        ([[0.2, 0.8]], [1], {"likelihood_power": 0}),
        ([[0.2, 0.8]], [1], {"likelihood_power": float("inf")}),
    ],
)
def test_invalid_evidence_inputs_are_rejected(probabilities, target, options):
    with pytest.raises((TypeError, ValueError)):
        bayesian_model_weights(probabilities, target, **options)


@pytest.mark.parametrize(
    "probabilities,target", [([[0.2, 0.8], [0.2, 0.8]], [1, 1]), ([[0.001, 0.9]], [1])],
)
def test_unrepresentable_finite_likelihood_power_raises_instead_of_losing_support(probabilities, target):
    # The first case overflows the exponent metadata; the second overflows a
    # posterior log difference. Both model likelihoods are strictly positive.
    with pytest.raises(ValueError):
        bayesian_model_weights(probabilities, target, likelihood_power=1e308)


@pytest.mark.parametrize("horizon", [0.25, 1.0, 4.0])
def test_probability_mixture_differs_from_applying_link_to_average_rate(horizon):
    ensemble = _ensemble()
    burned, environment = _prediction_inputs()
    result = ensemble(
        burned, environment, channel_names=["weather.temperature_2m"],
        dt_hours=horizon,
    )
    center = (0, 0, 4, 4)
    expected_probability = 0.3 * -math.expm1(-0.15 * horizon) + 0.7 * -math.expm1(-0.8 * horizon)
    expected_rate = -math.log(0.3 * math.exp(-0.15 * horizon) + 0.7 * math.exp(-0.8 * horizon)) / horizon
    assert result.valid[center]
    assert result.rate_valid[center]
    assert result.probability[center] == pytest.approx(expected_probability, abs=1e-14)
    assert result.rate[center] == pytest.approx(expected_rate, abs=1e-14)
    assert not math.isclose(expected_probability, -math.expm1(-(0.3 * 0.15 + 0.7 * 0.8) * horizon))
    torch.testing.assert_close(
        result.probability[center], -torch.expm1(-result.rate[center] * horizon),
        rtol=0, atol=1e-14,
    )


def test_effective_rate_has_weighted_rate_limit_at_zero_horizon_and_tensor_horizons():
    ensemble = _ensemble()
    burned, environment = _prediction_inputs(batch=3)
    horizons = torch.tensor([0.0, 1.0, 3.0], dtype=torch.float64)
    result = ensemble(
        burned, environment, channel_names=["weather.temperature_2m"],
        dt_hours=horizons,
    )
    assert result.probability[0, 0, 4, 4] == 0
    assert result.rate_valid[0, 0, 4, 4]
    assert result.rate[0, 0, 4, 4] == pytest.approx(0.3 * 0.15 + 0.7 * 0.8, abs=1e-14)
    expected = [0.0] + [
        0.3 * -math.expm1(-0.15 * horizon) + 0.7 * -math.expm1(-0.8 * horizon)
        for horizon in (1.0, 3.0)
    ]
    torch.testing.assert_close(
        result.probability[:, 0, 4, 4], torch.tensor(expected, dtype=torch.float64),
        rtol=0, atol=1e-14,
    )


def test_long_horizon_effective_rate_is_finite_when_probabilities_saturate():
    ensemble = _ensemble()
    burned, environment = _prediction_inputs()
    horizon = 10000.0
    result = ensemble(
        burned, environment, channel_names=["weather.temperature_2m"],
        dt_hours=horizon,
    )
    center = (0, 0, 4, 4)
    assert result.probability[center] == 1.0
    assert result.rate_valid[center]
    # The slower component dominates survival; the other correction is < exp(-6500).
    assert result.rate[center] == pytest.approx(0.15 - math.log(0.3) / horizon, abs=1e-14)


def test_small_positive_horizon_preserves_probability_and_effective_rate_precision():
    ensemble = _ensemble()
    burned, environment = _prediction_inputs()
    horizon = 1e-12
    result = ensemble(
        burned, environment, channel_names=["weather.temperature_2m"],
        dt_hours=horizon,
    )
    center = (0, 0, 4, 4)
    expected_probability = 0.3 * -math.expm1(-0.15 * horizon) + 0.7 * -math.expm1(-0.8 * horizon)
    assert result.probability[center] == pytest.approx(expected_probability, rel=1e-13, abs=0)
    assert result.rate[center] == pytest.approx(0.3 * 0.15 + 0.7 * 0.8, abs=1e-12)


def test_overflowing_rate_times_horizon_does_not_hide_a_finite_effective_rate():
    ensemble = _ensemble(components=[_component(3, 1e200), _component(5, 2e200)])
    burned, environment = _prediction_inputs()
    result = ensemble(
        burned, environment, channel_names=["weather.temperature_2m"],
        dt_hours=1e200,
    )
    center = (0, 0, 4, 4)
    assert result.valid[center]
    assert result.probability[center] == 1.0
    assert result.rate_valid[center]
    assert torch.isfinite(result.rate[center])
    # The slower model dominates survival; -log(0.3)/t is below float64 precision.
    assert result.rate[center] == pytest.approx(1e200, rel=1e-14)


@pytest.mark.parametrize("second_log_weight", [math.log(0.7), -1000.0])
def test_missing_supported_component_invalidates_mixture_without_local_reweighting(second_log_weight):
    log_total = float(np.logaddexp(math.log(0.3), second_log_weight))
    ensemble = _ensemble(log_weights=[math.log(0.3) - log_total, second_log_weight - log_total])
    burned, environment = _prediction_inputs()
    feature_valid = torch.ones_like(environment, dtype=torch.bool)
    feature_valid[0, 0, 2, 4] = False  # In the 5x5 support, outside the 3x3 support.
    result = ensemble(
        burned, environment, channel_names=["weather.temperature_2m"],
        feature_valid=feature_valid,
    )
    center = (0, 0, 4, 4)
    assert not result.valid[center]
    assert torch.isnan(result.probability[center])
    assert not result.rate_valid[center]
    assert torch.isnan(result.rate[center])


def test_exact_zero_posterior_component_does_not_require_its_missing_context():
    ensemble = _ensemble(log_weights=[0.0, -math.inf])
    burned, environment = _prediction_inputs()
    feature_valid = torch.ones_like(environment, dtype=torch.bool)
    feature_valid[0, 0, 2, 4] = False
    result = ensemble(
        burned, environment, channel_names=["weather.temperature_2m"],
        feature_valid=feature_valid,
    )
    center = (0, 0, 4, 4)
    assert result.valid[center]
    assert result.rate_valid[center]
    assert result.probability[center] == pytest.approx(-math.expm1(-0.15), abs=1e-14)
    assert result.rate[center] == pytest.approx(0.15, abs=1e-14)


@pytest.mark.parametrize("known_zero", ["zero_horizon", "already_burned"])
def test_known_zero_probability_survives_unavailable_rate_context(known_zero):
    ensemble = _ensemble()
    burned, environment = _prediction_inputs()
    feature_valid = torch.ones_like(environment, dtype=torch.bool)
    feature_valid[0, 0, 2, 4] = False
    horizon = 0.0 if known_zero == "zero_horizon" else 1.0
    center = (0, 0, 4, 4)
    if known_zero == "already_burned":
        burned[center] = 1.0
    result = ensemble(
        burned, environment, channel_names=["weather.temperature_2m"],
        dt_hours=horizon, feature_valid=feature_valid,
    )
    assert result.valid[center]
    assert result.probability[center] == 0.0
    assert not result.rate_valid[center]
    assert torch.isnan(result.rate[center])


def test_frozen_dropout_components_stay_in_eval_mode_and_predict_deterministically():
    torch.manual_seed(912)
    components = [
        _component(3, 0.15, architecture="mlp", dropout=0.6),
        _component(5, 0.8, architecture="mlp", dropout=0.6),
    ]
    # Restore nonconstant output parameters so dropout affects predictions in training mode.
    with torch.no_grad():
        for component in components:
            component.model.kernel_network.output.weight.normal_(mean=0.0, std=0.1)
    ensemble = _ensemble(components=components)
    ensemble.train()
    assert all(not component.training for component in components)
    assert all(not module.training for component in components for module in component.modules())
    assert all(not parameter.requires_grad for parameter in ensemble.parameters())
    burned, environment = _prediction_inputs(batch=8)
    first = ensemble(burned, environment, channel_names=["weather.temperature_2m"])
    second = ensemble(burned, environment, channel_names=["weather.temperature_2m"])
    torch.testing.assert_close(first.probability, second.probability, rtol=0, atol=0, equal_nan=True)


def test_prediction_rejects_channel_order_instead_of_reinterpreting_inputs():
    ensemble = _ensemble()
    burned, environment = _prediction_inputs()
    with pytest.raises(ValueError, match="channel"):
        ensemble(burned, environment, channel_names=["terrain.slope_degrees"])


def test_incompatible_component_endpoint_contracts_are_rejected():
    components = [_component(3, 0.15), _component(5, 0.8)]
    components[1].contract["dt_hours"] = 2.0
    with pytest.raises(ValueError):
        _ensemble(components=components)


@pytest.mark.parametrize("log_weights", [[math.nan, 0.0], [math.inf, 0.0], [-math.inf, -math.inf], [0.0]])
def test_invalid_posterior_support_is_rejected(log_weights):
    with pytest.raises((TypeError, ValueError)):
        _ensemble(log_weights=log_weights)


def test_converting_posterior_logs_to_component_dtype_cannot_discard_finite_support():
    components = [_component(3, 0.15).float(), _component(5, 0.8).float()]
    # This log has finite float64 support but cannot be represented in float32.
    with pytest.raises(ValueError):
        _ensemble(components=components, log_weights=[0.0, -1e300])
