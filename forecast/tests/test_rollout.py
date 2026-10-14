"""Binary recursive spread, Monte Carlo error, and forecast-input contracts.

The directed fixtures have exact analytic probabilities. They use the fitted
wrapper's ordinary normalization, masking, eligibility, and binary validation;
only the environmental kernel generator is made explicit for the test oracle.
"""

from copy import deepcopy
import json
import math
from pathlib import Path

import numpy as np
import pytest
import torch

from tests.test_prediction import categorical_model
from wildfire import CumulativePrediction, WildfireModel, load_model
from wildfire.models import (
    BayesianBurnModel,
    BurnProbability,
    EnvironmentConditionedConvolution,
    TrainedBurnModel,
    build_kernel_model,
    build_mixed_kernel_model,
    build_neural_mixed_kernel_model,
    initialize_kernel_rate,
    initialize_mixed_kernel_rate,
    initialize_neural_mixed_kernel_rate,
    kernel_model_configuration,
    mixed_model_configuration,
    neural_mixed_model_configuration,
)


CHANNELS = ("fixture.hourly_rate", "fixture.auxiliary")
SEED_CELL = (0, 2, 1)
SECOND_CELL = (0, 2, 2)
THIRD_CELL = (0, 2, 3)


@pytest.fixture(autouse=True)
def _few_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


class _DirectedKernel(EnvironmentConditionedConvolution):
    """Each target can catch fire only from its immediate western neighbor."""

    def __init__(self, kernel_size=3, fixed_rate=None):
        super().__init__(2, kernel_size, 2)
        self.fixed_rate = fixed_rate
        self.calls = 0

    def _kernels(self, clean):
        shape = (*clean.shape[:-3], self.kernel_size**2, *clean.shape[-2:])
        rates = clean.new_zeros(shape)
        radius = self.kernel_size // 2
        west = radius * self.kernel_size + radius - 1
        value = (clean[..., 0, :, :] if self.fixed_rate is None
                 else clean.new_full(clean.shape[:-3] + clean.shape[-2:], self.fixed_rate))
        rates[..., west, :, :] = value.clamp_min(0)
        return rates

    def forward(self, burned_area, environmental_data, **options):
        known = torch.isfinite(burned_area)
        if options.get("burned_area_valid") is not None:
            known &= options["burned_area_valid"]
        assert torch.all(~known | (burned_area == 0) | (burned_area == 1))
        self.calls += 1
        return super().forward(burned_area, environmental_data, **options)


class _InvalidAfterSpread(_DirectedKernel):
    """A transition failure that the original-state validity envelope misses."""

    def forward(self, burned_area, environmental_data, **options):
        result = super().forward(burned_area, environmental_data, **options)
        failed = burned_area[..., 0, 2, 2] == 1
        if bool(failed.any()):
            probability, valid = result.probability.clone(), result.valid.clone()
            probability[..., 0, 2, 3] = torch.where(
                failed, getattr(self, "failure_value", torch.nan), probability[..., 0, 2, 3],
            )
            if not getattr(self, "failure_valid", False):
                valid[..., 0, 2, 3] &= ~failed
            return BurnProbability(probability, valid, result.rate, result.rate_valid)
        return result


def _contract(kernel_size, architecture="EnvironmentConditionedConvolution"):
    return {
        "format_version": 1, "architecture": architecture,
        "in_channels": 2, "channels": list(CHANNELS),
        "kernel_size": kernel_size, "hidden_channels": 2,
        "dt_hours": 1.0, "center_rate": 0.0,
        "eligibility": "at_least_one_burned_neighbor",
    }


def _component(size=3, fixed_rate=None, kernel_class=_DirectedKernel):
    kernel = kernel_class(size, fixed_rate).double()
    return TrainedBurnModel(
        kernel, torch.zeros(2, dtype=torch.float64), torch.ones(2, dtype=torch.float64),
        _contract(size), best_epoch=1,
    ).double().eval()


def _public(predictor):
    return WildfireModel(
        predictor, {"contract": deepcopy(predictor.contract)},
        Path("/private/tmp/recursive_probability_fixture.pt"), "test-checkpoint",
    )


def _model(fixed_rate=None, kernel_class=_DirectedKernel):
    return _public(_component(fixed_rate=fixed_rate, kernel_class=kernel_class))


def _inputs(rate=math.log(2), leading=()):
    burned = torch.zeros((*leading, 1, 5, 6), dtype=torch.float64)
    burned[..., 0, 2, 1] = 1
    features = torch.zeros((*leading, 2, 5, 6), dtype=torch.float64)
    features[..., 0, :, :] = rate
    features[..., 1, :, :] = 7  # An unused channel makes schema reordering meaningful.
    return burned, features


def _predict(model, burned, features, **options):
    options.setdefault("hours", [1, 2, 3])
    options.setdefault("n_samples", 128)
    options.setdefault("seed", 41)
    options.setdefault("trajectory_batch_size", 32)
    options.setdefault("boundary", "zero")
    return model.predict_cumulative(
        burned, features, channel_names=CHANNELS, **options,
    )


def _equal(left, right):
    assert left.hours == right.hours
    for name in (
        "probability", "valid", "rate", "rate_valid", "burned_probability",
        "mc_standard_error", "confidence_lower", "confidence_upper",
    ):
        torch.testing.assert_close(
            getattr(left, name), getattr(right, name), rtol=0, atol=0, equal_nan=True,
        )


def _assert_sampling_agreement(actual, exact, n_samples):
    # Six theoretical standard deviations plus one count avoids flaky tail
    # failures while rejecting the deterministic mean-source chain recursion.
    tolerance = 6 * math.sqrt(exact * (1 - exact) / n_samples) + 1 / n_samples
    assert float(actual) == pytest.approx(exact, abs=tolerance)


def _bayesian(components, logs):
    contract = _contract(max(member.model.kernel_size for member in components), "BayesianModelAverage")
    contract.pop("hidden_channels")
    return _public(BayesianBurnModel(components, logs, contract))


def test_recursive_chain_matches_joint_state_expectation_and_keeps_binary_inputs():
    model = _model()
    burned, features = _inputs()
    n_samples = 8192
    result = _predict(model, burned, features, hours=[3, 1, 2], n_samples=n_samples,
                      trajectory_batch_size=256)
    assert isinstance(result, CumulativePrediction)
    assert result.hours == (3.0, 1.0, 2.0)
    assert result.probability.shape == (3, 1, 5, 6)
    assert model.predictor.model.calls > 0
    for hours, exact_b, exact_c in ((1, 0.5, 0), (2, 0.75, 0.25), (3, 0.875, 0.5)):
        estimate = result.at(hours=hours)
        _assert_sampling_agreement(estimate.probability[SECOND_CELL], exact_b, n_samples)
        _assert_sampling_agreement(estimate.probability[THIRD_CELL], exact_c, n_samples)
    # With 8192 samples the expected-source-rate value 0.292893 at hour two
    # lies well beyond the justified tolerance around the true value 0.25.
    assert abs(float(result.at(hours=2).probability[THIRD_CELL]) - (1 - 2**-0.5)) > 0.02


def test_one_hour_empirical_probability_agrees_with_ordinary_model_prediction():
    model = _model()
    burned, features = _inputs(rate=-math.log(0.7))
    ordinary = model.predict(burned, features, channel_names=CHANNELS, boundary="zero")
    n_samples = 4096
    recursive = _predict(model, burned, features, hours=1, n_samples=n_samples,
                         trajectory_batch_size=128)
    torch.testing.assert_close(recursive.valid[0], ordinary.valid)
    _assert_sampling_agreement(recursive.probability[(0,) + SECOND_CELL], 0.3, n_samples)
    # Counts, rather than Rao--Blackwell conditional means, define every horizon.
    count = recursive.probability * n_samples
    torch.testing.assert_close(count, count.round(), rtol=0, atol=1e-10)
    assert not torch.equal(recursive.probability[0], ordinary.probability)


def test_absorption_bounds_total_burned_and_uncertainty_have_explicit_semantics():
    model = _model()
    burned, features = _inputs()
    n_samples = 1024
    result = _predict(model, burned, features, n_samples=n_samples)
    known = result.valid
    assert torch.all((result.probability[known] >= 0) & (result.probability[known] <= 1))
    assert torch.all(result.probability[1:] >= result.probability[:-1])
    torch.testing.assert_close(result.burned_probability, result.probability + burned)
    assert result.probability[:, 0, 2, 1].eq(0).all()
    assert result.burned_probability[:, 0, 2, 1].eq(1).all()
    assert result.mc_standard_error[:, 0, 2, 1].eq(0).all()
    assert result.confidence_lower[:, 0, 2, 1].eq(0).all()
    assert result.confidence_upper[:, 0, 2, 1].eq(0).all()
    assert torch.isnan(result.rate).all() and not result.rate_valid.any()
    expected_se = torch.sqrt(result.probability * (1 - result.probability) / n_samples)
    torch.testing.assert_close(result.mc_standard_error, expected_se)
    assert torch.all(result.confidence_lower <= result.probability)
    assert torch.all(result.confidence_upper >= result.probability)
    assert torch.all((result.confidence_lower >= 0) & (result.confidence_upper <= 1))
    # A zero sampled count does not, by itself, prove an exact zero probability.
    assert result.confidence_upper[0, 0, 2, 3] > 0
    assert not result.probability.requires_grad
    assert result.metadata


def test_wilson_interval_matches_score_formula():
    model = _model()
    burned, features = _inputs()
    n_samples = 127
    result = _predict(model, burned, features, hours=1, n_samples=n_samples)
    p = float(result.probability[(0,) + SECOND_CELL])
    z = 1.959963984540054
    denominator = 1 + z*z / n_samples
    center = (p + z*z / (2*n_samples)) / denominator
    half = z / denominator * math.sqrt(p*(1-p)/n_samples + z*z/(4*n_samples*n_samples))
    assert float(result.confidence_lower[(0,) + SECOND_CELL]) == pytest.approx(center-half, abs=1e-12)
    assert float(result.confidence_upper[(0,) + SECOND_CELL]) == pytest.approx(center+half, abs=1e-12)


def test_no_initial_fire_stays_zero_at_every_horizon():
    model = _model()
    burned, features = _inputs()
    burned.zero_()
    result = _predict(model, burned, features, hours=[1, 2, 5])
    assert result.valid.all()
    assert result.probability.eq(0).all()
    assert result.burned_probability.eq(0).all()


def test_default_recursive_controls_are_recorded_as_sampling_configuration():
    model = _model()
    burned, features = _inputs()
    result = model.predict_cumulative(burned, features, hours=1,
                                      channel_names=CHANNELS)
    assert result.metadata["method"] == "recursive"
    assert result.metadata["boundary"] == "zero"
    assert result.metadata["n_samples"] == 1024
    assert result.metadata["seed"] == 0
    assert result.metadata["trajectory_batch_size"] == 32
    assert result.metadata["uncertainty_kind"] == "monte_carlo"


def test_seed_reproducibility_global_rng_isolation_and_horizon_prefix_invariance():
    model = _model()
    burned, features = _inputs(leading=(2,))
    global_state = torch.random.get_rng_state().clone()
    first = _predict(model, burned, features, hours=[1, 2], n_samples=67, seed=18)
    torch.testing.assert_close(torch.random.get_rng_state(), global_state)
    _equal(first, _predict(model, burned, features, hours=[1, 2], n_samples=67, seed=18))
    longer = _predict(model, burned, features, hours=[4, 2, 1], n_samples=67, seed=18)
    for hours in first.hours:
        torch.testing.assert_close(first.at(hours=hours).probability,
                                   longer.at(hours=hours).probability, rtol=0, atol=0)
        torch.testing.assert_close(first.at(hours=hours).valid, longer.at(hours=hours).valid)
    different = _predict(model, burned, features, hours=[1, 2], n_samples=67, seed=19)
    assert not torch.equal(first.probability, different.probability)


@pytest.mark.parametrize("n_samples", [17, 31, 32])
def test_increasing_sample_count_preserves_existing_trajectory_prefix(n_samples):
    model = _model()
    burned, features = _inputs(leading=(2,))
    small = _predict(model, burned, features, n_samples=n_samples, seed=91)
    large = _predict(model, burned, features, n_samples=n_samples+1, seed=91)
    counts_small = (small.probability * n_samples).round()
    counts_large = (large.probability * (n_samples+1)).round()
    extra_trajectory = counts_large - counts_small
    assert torch.all((extra_trajectory == 0) | (extra_trajectory == 1))
    assert torch.all(extra_trajectory[1:] >= extra_trajectory[:-1])


def test_forecast_first_slice_applies_to_first_hour_and_is_reordered_by_name():
    model = _model()
    burned, current = _inputs(rate=1000)
    forecast = current.unsqueeze(0).repeat(3, 1, 1, 1)
    forecast[0, 0] = 0
    forecast[1:, 0] = 1000
    mapping = {"features": forecast[:, [1, 0]], "channel_names": CHANNELS[::-1]}
    result = _predict(model, burned, current, environmental_forecast=mapping)
    assert result.at(hours=1).probability.eq(0).all()
    assert result.at(hours=2).probability[SECOND_CELL] == 1
    assert result.at(hours=2).probability[THIRD_CELL] == 0
    assert result.at(hours=3).probability[THIRD_CELL] == 1
    assert torch.all(forecast[0, 0] == 0)  # Neither forecast nor current data were mutated.
    assert torch.all(current[0] == 1000)


def test_forecast_masks_stay_unresolved_even_if_every_sample_already_burned():
    model = _model()
    burned, features = _inputs(rate=1000)
    forecast = features.unsqueeze(0).repeat(2, 1, 1, 1)
    masks = torch.ones_like(forecast, dtype=torch.bool)
    masks[1, 0, 2, 2] = False
    result = _predict(model, burned, features, hours=[1, 2], n_samples=8,
                      environmental_forecast={"features": forecast, "channel_names": CHANNELS,
                                              "feature_valid": masks})
    assert result.at(hours=1).probability[SECOND_CELL] == 1
    assert not result.at(hours=2).valid[SECOND_CELL]
    assert torch.isnan(result.at(hours=2).probability[SECOND_CELL])
    assert torch.isnan(result.burned_probability[(1,) + SECOND_CELL])
    assert torch.isnan(result.mc_standard_error[(1,) + SECOND_CELL])
    assert torch.isnan(result.confidence_lower[(1,) + SECOND_CELL])
    assert torch.isnan(result.confidence_upper[(1,) + SECOND_CELL])
    # Original known burns stay resolved even when their rate context is missing.
    assert result.at(hours=2).valid[SEED_CELL]
    assert result.at(hours=2).probability[SEED_CELL] == 0
    assert result.burned_probability[(1,) + SEED_CELL] == 1


def test_forecast_interval_axis_remains_separate_from_independent_cutoff_axis():
    model = _model()
    burned, current = _inputs(rate=1000, leading=(2,))
    forecast = current.unsqueeze(0).repeat(3, 1, 1, 1, 1)
    forecast[0, 0, 0] = 0
    forecast[1, 1, 0] = 0
    result = _predict(model, burned, current, environmental_forecast={
        "features": forecast, "channel_names": CHANNELS,
    })
    assert result.probability.shape == (3, 2, 1, 5, 6)
    assert result.at(hours=1).probability[0, 0, 2, 2] == 0
    assert result.at(hours=1).probability[1, 0, 2, 2] == 1
    assert result.at(hours=2).probability[:, 0, 2, 2].eq(1).all()
    assert result.at(hours=2).probability[:, 0, 2, 3].eq(0).all()
    assert result.at(hours=3).probability[:, 0, 2, 3].eq(1).all()


@pytest.mark.parametrize("missing", ["nonfinite", "masked"])
def test_unknown_initial_state_is_never_a_known_zero_or_rescued_burn(missing):
    model = _model()
    burned, features = _inputs(rate=1000)
    valid = torch.ones_like(burned, dtype=torch.bool)
    if missing == "nonfinite":
        burned[SEED_CELL] = torch.nan
    else:
        valid[SEED_CELL] = False  # A stored 1 does not make this an observed burn.
    result = _predict(model, burned, features, burned_area_valid=valid,
                      missing_burned_area="unknown")
    for hours in result.hours:
        prediction = result.at(hours=hours)
        assert not prediction.valid[SEED_CELL]
        assert not prediction.valid[SECOND_CELL]
        assert torch.isnan(prediction.probability[SECOND_CELL])
    assert torch.isnan(result.burned_probability[:, 0, 2, 1]).all()


@pytest.mark.parametrize("missing", ["nan", "positive_infinity", "negative_infinity", "masked_one", "masked_sentinel"])
def test_default_missing_burned_area_is_zero_not_a_rescued_existing_burn(missing):
    model = _model()
    burned, features = _inputs(rate=1000)
    valid = torch.ones_like(burned, dtype=torch.bool)
    if missing == "nan":
        burned[SEED_CELL] = torch.nan
    elif missing == "positive_infinity":
        burned[SEED_CELL] = torch.inf
    elif missing == "negative_infinity":
        burned[SEED_CELL] = -torch.inf
    else:
        valid[SEED_CELL] = False
        if missing == "masked_sentinel":
            burned[SEED_CELL] = 255
    original_burned, original_valid = burned.clone(), valid.clone()
    result = _predict(model, burned, features, burned_area_valid=valid)
    assert result.valid.all()
    assert result.probability.eq(0).all()
    assert result.burned_probability.eq(0).all()
    assert result.metadata["missing_burned_area"] == "unburned"
    assert result.metadata["assumed_unburned_cells"] == 1
    torch.testing.assert_close(burned, original_burned, rtol=0, atol=0, equal_nan=True)
    torch.testing.assert_close(valid, original_valid)


@pytest.mark.parametrize("missing", ["nan", "masked_one"])
def test_assumed_unburned_cell_can_catch_fire_and_become_a_later_source(missing):
    model = _model()
    burned, features = _inputs(rate=1000)
    valid = torch.ones_like(burned, dtype=torch.bool)
    if missing == "nan":
        burned[SECOND_CELL] = torch.nan
    else:
        burned[SECOND_CELL] = 1
        valid[SECOND_CELL] = False
    original_burned, original_valid = burned.clone(), valid.clone()
    result = _predict(model, burned, features, hours=[1, 2], burned_area_valid=valid)
    assert result.valid.all()
    assert result.at(hours=1).probability[SECOND_CELL] == 1
    assert result.at(hours=1).probability[THIRD_CELL] == 0
    assert result.at(hours=2).probability[THIRD_CELL] == 1
    assert result.burned_probability[(0,) + SECOND_CELL] == 1
    assert result.probability[:, 0, 2, 1].eq(0).all()  # Observed seed remains a prior burn.
    assert result.metadata["assumed_unburned_cells"] == 1
    conservative = _predict(model, burned, features, hours=[1, 2], burned_area_valid=valid,
                            missing_burned_area="unknown")
    assert not conservative.valid[:, 0, 2, 2].any()
    assert not conservative.valid[:, 0, 2, 3].any()
    assert conservative.metadata["missing_burned_area"] == "unknown"
    assert conservative.metadata["assumed_unburned_cells"] == 0
    torch.testing.assert_close(burned, original_burned, rtol=0, atol=0, equal_nan=True)
    torch.testing.assert_close(valid, original_valid)


def test_missing_burn_fill_preserves_spatial_temporal_padding_and_environment_unknowns():
    model = _model()
    burned, features = _inputs(rate=1000, leading=(2,))
    burned[0, 0, 2, 2] = torch.nan
    pixels = torch.ones((1, 5, 6), dtype=torch.bool)
    pixels[SEED_CELL] = False
    padded = _predict(model, burned, features, pixel_valid=pixels,
                      time_valid=torch.tensor([True, False]))
    assert padded.metadata["assumed_unburned_cells"] == 1
    assert not padded.valid[:, 0, 0, 2, 1].any()
    assert not padded.valid[:, 1].any()
    assert torch.isnan(padded.burned_probability[:, 1]).all()
    single_burned, single_features = _inputs(rate=1000)
    single_burned[SECOND_CELL] = torch.nan
    feature_valid = torch.ones_like(single_features, dtype=torch.bool)
    feature_valid[0, 2, 2] = False
    environmental = _predict(model, single_burned, single_features, feature_valid=feature_valid)
    assert environmental.metadata["assumed_unburned_cells"] == 1
    assert not environmental.valid[:, 0, 2, 2].any()
    assert torch.isnan(environmental.probability[:, 0, 2, 2]).all()


def test_ordinary_and_fixed_share_initial_zero_default_and_allow_explicit_unknown():
    model = _model()
    burned, features = _inputs(rate=1000)
    burned[SECOND_CELL] = torch.nan
    ordinary = model.predict(burned, features, channel_names=CHANNELS, boundary="zero")
    assert ordinary.valid[SECOND_CELL]
    assert ordinary.metadata["assumed_unburned_cells"] == 1
    fixed = _predict(model, burned, features, method="fixed", hours=[0.5, 2])
    assert fixed.valid[:, 0, 2, 2].all()
    assert torch.isfinite(fixed.burned_probability[:, 0, 2, 2]).all()
    conservative = model.predict(burned, features, channel_names=CHANNELS,
                                 boundary="zero", missing_burned_area="unknown")
    assert not conservative.valid[SECOND_CELL]
    conservative_fixed = _predict(model, burned, features, method="fixed",
                                  hours=[0.5, 2], missing_burned_area="unknown")
    assert not conservative_fixed.valid[:, 0, 2, 2].any()
    assert torch.isnan(conservative_fixed.burned_probability[:, 0, 2, 2]).all()


@pytest.mark.parametrize("policy", ["unsupported", True, ["unknown"], None])
def test_missing_burn_policy_requires_an_explicit_supported_string(policy):
    model = _model()
    burned, features = _inputs()
    with pytest.raises((TypeError, ValueError)):
        _predict(model, burned, features, missing_burned_area=policy)


@pytest.mark.parametrize("policy", ["unknown", "unburned"])
@pytest.mark.parametrize("value", [0.5, 255.0])
def test_missing_policy_does_not_relax_known_binary_state_validation(policy, value):
    model = _model()
    burned, features = _inputs()
    burned[SECOND_CELL] = value
    with pytest.raises(ValueError, match="0 or 1|binary"):
        _predict(model, burned, features, missing_burned_area=policy)


def test_unknown_boundary_propagates_while_zero_boundary_keeps_complete_domain():
    model = _model()
    burned, features = _inputs()
    unknown = _predict(model, burned, features, hours=[1, 2], boundary="unknown")
    zero = _predict(model, burned, features, hours=[1, 2], boundary="zero")
    assert zero.valid.all()
    assert unknown.at(hours=1).valid[0, 1, 1]
    assert not unknown.at(hours=2).valid[0, 1, 1]
    assert not unknown.at(hours=1).valid[0, 0, 3]
    assert unknown.valid[:, 0, 2, 1].all()  # Original burn is rescued.


def test_spatial_and_temporal_padding_mask_sources_before_any_rollout():
    model = _model()
    burned, features = _inputs(leading=(2,))
    pixels = torch.ones((1, 5, 6), dtype=torch.bool)
    pixels[SEED_CELL] = False
    result = _predict(model, burned, features, pixel_valid=pixels,
                      time_valid=torch.tensor([True, False]))
    assert not result.valid[:, 0, 0, 2, 1].any()
    assert not result.valid[:, 0, 0, 2, 2].any()
    assert not result.valid[:, 1].any()
    assert torch.isnan(result.probability[:, 1]).all()
    assert torch.isnan(result.burned_probability[:, 1]).all()


def test_bayesian_model_component_is_drawn_once_and_kept_for_whole_trajectory():
    members = [_component(3, -math.log(0.8)), _component(5, -math.log(0.2))]
    model = _bayesian(members, [math.log(0.5), math.log(0.5)])
    burned, features = _inputs()
    n_samples = 8192
    result = _predict(model, burned, features, hours=[1, 2], n_samples=n_samples,
                      trajectory_batch_size=256)
    _assert_sampling_agreement(result.at(hours=1).probability[SECOND_CELL], 0.5, n_samples)
    _assert_sampling_agreement(result.at(hours=2).probability[SECOND_CELL], 0.66, n_samples)
    assert abs(float(result.at(hours=2).probability[SECOND_CELL]) - 0.75) > 0.06


def test_bayesian_finite_log_mass_still_requires_unsampled_component_context():
    members = [_component(5, 0.2), _component(3, 0.8)]
    supported = _bayesian(members, [-1000.0, 0.0])
    excluded = _bayesian([_component(5, 0.2), _component(3, 0.8)], [-math.inf, 0.0])
    burned, features = _inputs()
    first = _predict(supported, burned, features, hours=1, n_samples=16, boundary="unknown")
    second = _predict(excluded, burned, features, hours=1, n_samples=16, boundary="unknown")
    assert not first.at(hours=1).valid[0, 1, 1]
    assert torch.isnan(first.at(hours=1).probability[0, 1, 1])
    assert second.at(hours=1).valid[0, 1, 1]


@pytest.mark.parametrize("failure_value,failure_valid", [
    (torch.nan, True), (-0.2, True), (1.2, True), (0.5, False),
])
def test_invalid_required_actual_transition_fails_instead_of_becoming_zero(failure_value, failure_valid):
    model = _model(kernel_class=_InvalidAfterSpread)
    model.predictor.model.failure_value = failure_value
    model.predictor.model.failure_valid = failure_valid
    burned, features = _inputs(rate=1000)
    with pytest.raises(RuntimeError):
        _predict(model, burned, features, hours=2, n_samples=8)


def test_sample_metadata_and_inference_never_read_future_labels():
    model = _model()
    burned, features = _inputs()

    class CurrentInputs(dict):
        forbidden = {"newly_burned_area", "newly_burned_area_valid", "arrival_hours",
                     "arrival_valid", "future_labels"}

        def __getitem__(self, key):
            assert key not in self.forbidden
            return super().__getitem__(key)

        def get(self, key, default=None):
            assert key not in self.forbidden
            return super().get(key, default)

        def __contains__(self, key):
            assert key not in self.forbidden
            return super().__contains__(key)

    sample = CurrentInputs(
        burned_area=burned, features=features, channel_names=CHANNELS,
        affine_transform=np.array([0.02, 0, 127, 0, -0.02, 38]), epsg=4326,
        time_utc=np.array(10_000, dtype=np.int64), event_id="directed_fixture",
        newly_burned_area=object(), arrival_hours=object(),
    )
    result = model.predict_cumulative(sample, hours=[1, 2], n_samples=32, seed=3, boundary="zero")
    assert result.coordinates.shape == (5, 6, 2)
    assert result.event_id == "directed_fixture"
    np.testing.assert_array_equal(result.time_utc, np.array(10_000))
    torch.testing.assert_close(result.coordinates, result.at(hours=2).coordinates)


def test_fixed_mode_preserves_real_horizons_rates_and_adds_total_burned():
    model = _model()
    burned, features = _inputs()
    result = _predict(model, burned, features, method="fixed", hours=[0.5, 3])
    for i, hours in enumerate(result.hours):
        expected = model.predict(burned, features, channel_names=CHANNELS,
                                 dt_hours=hours, boundary="zero")
        for field in ("probability", "valid", "rate", "rate_valid"):
            torch.testing.assert_close(getattr(result, field)[i], getattr(expected, field),
                                       rtol=0, atol=0, equal_nan=True)
        torch.testing.assert_close(result.burned_probability[i], burned + expected.probability)
        assert result.probability[(i,) + THIRD_CELL] == 0
    assert result.mc_standard_error is None
    assert result.confidence_lower is None and result.confidence_upper is None


@pytest.mark.parametrize("hours", [0, -1, 0.5, 1.5, True, "1", [], [1, 1], [1, np.nan]])
def test_recursive_horizons_reject_nonpositive_fractional_duplicate_or_nonreal_values(hours):
    model = _model()
    burned, features = _inputs()
    with pytest.raises((TypeError, ValueError)):
        _predict(model, burned, features, hours=hours)


@pytest.mark.parametrize("option,value", [
    ("n_samples", 0), ("n_samples", -1), ("n_samples", True), ("n_samples", 1.5),
    ("trajectory_batch_size", 0), ("trajectory_batch_size", True),
    ("trajectory_batch_size", 1.5), ("seed", True), ("seed", 1.5),
])
def test_invalid_sampling_options_are_rejected(option, value):
    model = _model()
    burned, features = _inputs()
    with pytest.raises((TypeError, ValueError)):
        _predict(model, burned, features, **{option: value})


def test_forecast_validation_rejects_short_wrong_shape_schema_and_nonboolean_masks():
    model = _model()
    burned, features = _inputs()
    valid_forecast = features.unsqueeze(0).repeat(2, 1, 1, 1)
    bad = [
        {"features": valid_forecast[:1], "channel_names": CHANNELS},
        {"features": valid_forecast[..., :-1], "channel_names": CHANNELS},
        {"features": valid_forecast, "channel_names": [CHANNELS[0], CHANNELS[0]]},
        {"features": valid_forecast, "channel_names": [CHANNELS[0], "missing.required"]},
        {"features": valid_forecast, "channel_names": CHANNELS,
         "feature_valid": torch.ones_like(valid_forecast, dtype=torch.int64)},
    ]
    for forecast in bad:
        with pytest.raises((TypeError, ValueError)):
            _predict(model, burned, features, hours=2, environmental_forecast=forecast)
    with pytest.raises(ValueError):
        _predict(model, burned, features, hours=2, method="fixed",
                 environmental_forecast={"features": valid_forecast, "channel_names": CHANNELS})


@pytest.mark.parametrize("architecture", [
    "EnvironmentConditionedConvolution", "LearnedNonnegativeKernel",
    "MixedNonnegativeKernel", "NeuralMixedNonnegativeKernel",
])
def test_every_loadable_single_tensor_family_runs_binary_recursive_inference(tmp_path, architecture):
    contract = _contract(3, architecture)
    if architecture == "EnvironmentConditionedConvolution":
        kernel = EnvironmentConditionedConvolution(2, 3, 2).double()
    elif architecture == "LearnedNonnegativeKernel":
        kernel = build_kernel_model(2, 3, "constant", hidden_channels=2, depth=1).double()
        initialize_kernel_rate(kernel, 0.1)
        contract["kernel_model"] = kernel_model_configuration(kernel)
    elif architecture == "MixedNonnegativeKernel":
        kernel = build_mixed_kernel_model(2, (3, 5), "constant", hidden_channels=2, depth=1).double()
        initialize_mixed_kernel_rate(kernel, 0.1)
        contract["kernel_model"] = mixed_model_configuration(kernel)
    else:
        kernel = build_neural_mixed_kernel_model(
            2, (3, 5), "constant", hidden_channels=2, depth=1, combiner_hidden_channels=2,
        ).double()
        initialize_neural_mixed_kernel_rate(kernel, 0.1)
        contract["kernel_model"] = neural_mixed_model_configuration(kernel)
    contract["kernel_size"] = kernel.kernel_size
    path = tmp_path / f"{architecture}.pt"
    torch.save({"contract": contract, "model_state_dict": kernel.state_dict(),
                "normalization_mean": torch.zeros(2, dtype=torch.float64),
                "normalization_std": torch.ones(2, dtype=torch.float64), "best_epoch": 1}, path)
    model = load_model(path)
    burned, features = _inputs()
    result = _predict(model, burned, features, hours=[1, 2], n_samples=33)
    assert result.valid.all()
    assert torch.all(result.probability[1] >= result.probability[0])
    assert result.burned_probability[:, 0, 2, 1].eq(1).all()
    assert torch.isnan(result.rate).all()


def test_loadable_bayesian_checkpoint_runs_recursive_inference(tmp_path):
    from tests.probability.test_bayesian_models import _ensemble, _prediction_inputs
    from wildfire.inference import bayesian_checkpoint_payload

    path = tmp_path / "bayesian.pt"
    torch.save(bayesian_checkpoint_payload(_ensemble()), path)
    model = load_model(path)
    burned, features = _prediction_inputs()
    result = model.predict_cumulative(
        burned, features, channel_names=model.channel_names, hours=[1, 2],
        n_samples=33, seed=6, boundary="zero",
    )
    assert result.valid.all()
    assert torch.all(result.probability[1] >= result.probability[0])
    assert result.burned_probability[:, 0, 0, 3, 4].eq(1).all()
    assert torch.isnan(result.rate).all() and not result.rate_valid.any()


def _encoded_forecast(model, intervals=2):
    """A reordered superset of the checkpoint's three-class vocabulary."""
    burned, _ = _inputs()
    current = torch.zeros((4, 5, 6), dtype=torch.float32)
    current[0] = -0.2
    current[1] = 1
    names = ("biome.biome_class=13", "biome.biome_class=5", "weather.temperature_2m",
             "biome.biome_class=4", "biome.biome_class=8")
    features = torch.zeros((intervals, 5, 5, 6), dtype=torch.float32)
    features[:, 2] = -0.2
    features[:, 3] = 1
    assert model.channel_names == ("weather.temperature_2m", "biome.biome_class=4",
                                   "biome.biome_class=5", "biome.biome_class=8")
    return burned, current, {"features": features, "channel_names": names}


def _encoded_prediction(model, burned, current, forecast, hours=2):
    return model.predict_cumulative(
        burned, current, channel_names=model.channel_names, hours=hours,
        n_samples=33, seed=15, trajectory_batch_size=32, boundary="zero",
        environmental_forecast=forecast,
    )


def test_unused_malformed_categorical_forecast_intervals_are_ignored_but_full_mask_is_validated(
    categorical_model,
):
    burned, current, extended = _encoded_forecast(categorical_model, intervals=3)
    truncated = {"features": extended["features"][:2].clone(),
                 "channel_names": extended["channel_names"]}
    expected = _encoded_prediction(categorical_model, burned, current, truncated)
    extended["features"][2, [0, 1, 3, 4]] = 0.5  # Known malformed unused one-hot group.
    extended["features"][2, 2] = torch.nan
    extended["feature_valid"] = torch.ones_like(extended["features"], dtype=torch.bool)
    _equal(_encoded_prediction(categorical_model, burned, current, extended), expected)
    with pytest.raises(ValueError, match="one-hot"):
        _encoded_prediction(categorical_model, burned, current, extended, hours=3)
    short_mask = dict(extended, feature_valid=extended["feature_valid"][:2])
    with pytest.raises(ValueError, match="shape"):
        _encoded_prediction(categorical_model, burned, current, short_mask)
    wrong_type = dict(extended, feature_valid=extended["feature_valid"].to(torch.int64))
    with pytest.raises(TypeError):
        _encoded_prediction(categorical_model, burned, current, wrong_type)


def test_categorical_forecast_reordering_and_extra_recognized_channels_preserve_trajectories(
    categorical_model,
):
    burned, current, superset = _encoded_forecast(categorical_model)
    order = [superset["channel_names"].index(name) for name in categorical_model.channel_names]
    ordered = {"features": superset["features"][:, order].clone(),
               "channel_names": categorical_model.channel_names}
    _equal(_encoded_prediction(categorical_model, burned, current, superset),
           _encoded_prediction(categorical_model, burned, current, ordered))


def test_unseen_forecast_category_is_unknown_while_active_malformed_one_hot_is_rejected(
    categorical_model,
):
    burned, current, forecast = _encoded_forecast(categorical_model)
    forecast["features"][1, 3, 2, 2] = 0
    forecast["features"][1, 0, 2, 2] = 1  # Class 13 is valid data, absent from training.
    result = _encoded_prediction(categorical_model, burned, current, forecast, hours=[1, 2])
    assert result.at(hours=1).valid[SECOND_CELL]
    assert not result.at(hours=2).valid[SECOND_CELL]
    assert torch.isnan(result.at(hours=2).probability[SECOND_CELL])
    assert result.at(hours=2).valid[SEED_CELL]
    assert result.burned_probability[(1,) + SEED_CELL] == 1
    malformed = deepcopy(forecast)
    malformed["features"][1, 1, 2, 2] = 1  # Two known classes in the used interval.
    with pytest.raises(ValueError, match="one-hot"):
        _encoded_prediction(categorical_model, burned, current, malformed)


def test_recursive_result_plot_reference_comparison_and_numpy_export_integrate():
    import matplotlib.pyplot as plt

    model = _model()
    burned, features = _inputs(rate=1000)
    transform = np.array([0.02, 0, 127, 0, -0.02, 38])
    sample = {"burned_area": burned, "features": features, "channel_names": CHANNELS,
              "time_utc": np.array(10_000, dtype=np.int64), "event_id": "integration",
              "affine_transform": transform, "epsg": 4326}
    result = model.predict_cumulative(sample, hours=[1, 2], n_samples=16, boundary="zero")
    exported = result.numpy()
    for name in ("burned_probability", "mc_standard_error", "confidence_lower", "confidence_upper"):
        np.testing.assert_array_equal(exported[name], getattr(result, name).numpy())
    assert json.loads(str(exported["metadata_json"].item()))["method"] == "recursive"
    exported["burned_probability"][:] = -1
    assert result.burned_probability.min() >= 0
    endpoint = result.at(hours=2)
    reference = {
        "burned_area": np.stack([burned.numpy(), endpoint.burned_probability.numpy()]),
        "burned_area_valid": np.ones((2, 1, 5, 6), dtype=bool),
        "time_utc": np.array([10_000, 17_200], dtype=np.int64),
        "event_id": "integration", "affine_transform": transform, "epsg": 4326,
    }
    observed, observed_valid = result.aligned_observations(reference, hours=2)
    assert observed_valid.all()
    np.testing.assert_array_equal(observed, endpoint.probability.numpy())
    plotted, axis = result.plot(hours=2, colorbar=False)
    compared = None
    try:
        np.testing.assert_array_equal(axis.images[0].get_array(), endpoint.probability[0].numpy())
        compared, _ = result.compare(reference, hours=2)
        plotted.canvas.draw()
        compared.canvas.draw()
    finally:
        plt.close(plotted)
        if compared is not None:
            plt.close(compared)
