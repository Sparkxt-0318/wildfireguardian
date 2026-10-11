"""One-output neural combination of independent multiscale convolution rates."""

import copy
import math

import pytest
import torch
from torch.nn import functional as F

from wildfire.models import KERNEL_ARCHITECTURES
from wildfire.models import initialize_kernel_rate
from wildfire.models import center_probability
from wildfire.inference import load_neural_mixed_trained_model
from wildfire.models import build_neural_mixed_kernel_model
from wildfire.models import initialize_neural_mixed_kernel_rate
from wildfire.models import neural_mixed_model_configuration


@pytest.fixture(autouse=True)
def _few_threads():
    original = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(original)


@pytest.mark.parametrize("transform", ["identity", "log1p"])
def test_one_scalar_neural_readout_combines_rates_before_the_single_exponential(transform):
    model = build_neural_mixed_kernel_model(1, (3, 5), "constant", combiner_hidden_channels=1,
                                            combiner_input_transform=transform).double().eval()
    initialize_kernel_rate(model.branches["3"], 0.2)
    initialize_kernel_rate(model.branches["5"], 0.7)
    with torch.no_grad():
        model.combiner[0].weight.copy_(torch.tensor([[1.0, 2.0]], dtype=torch.float64))
        model.combiner[0].bias.fill_(0.3)
        model.combiner[-1].weight.fill_(1.2)
        model.combiner[-1].bias.fill_(-0.4)
    environment = torch.zeros(1, 1, 5, 5, dtype=torch.float64)
    burned = torch.zeros(1, 1, 5, 5, dtype=torch.float64)
    burned[0, 0, 1, 2] = 1
    burned[0, 0, 0, 2] = 1
    raw = torch.tensor([[0.2, 1.4]], dtype=torch.float64)
    torch.testing.assert_close(model.branch_center_convolution_rates(environment, burned), raw,
                               rtol=0, atol=1e-14)
    transformed = torch.log1p(raw) if transform == "log1p" else raw
    hidden = F.silu(transformed[:, 0] + 2 * transformed[:, 1] + 0.3)
    expected_rate = raw.sum(dim=1) * F.softplus(1.2 * hidden - 0.4)
    actual_rate = model.combined_rate(raw)
    torch.testing.assert_close(actual_rate, expected_rate, rtol=0, atol=1e-14)
    probability = model.center_probability(environment, burned)
    torch.testing.assert_close(probability, -torch.expm1(-expected_rate), rtol=0, atol=1e-14)
    assert actual_rate.shape == (1,)
    assert not torch.allclose(actual_rate, raw.sum(dim=1))
    assert "mixing_logits" not in dict(model.named_parameters())
    with pytest.raises(TypeError, match="no linear mixing"):
        model.mixing_weights()
    with pytest.raises(TypeError, match="depends on burned"):
        model.kernel_rates(environment)


@pytest.mark.parametrize("transform", ["identity", "log1p"])
def test_combined_rate_is_nonnegative_and_preserves_exact_all_zero_input(transform):
    model = build_neural_mixed_kernel_model(2, combiner_input_transform=transform).double()
    with torch.no_grad():
        model.combiner[-1].weight.fill_(0.2)
        model.combiner[-1].bias.fill_(20)
    rates = torch.tensor([[0, 0, 0, 0], [0.1, 0, 0.2, 0], [0, 0, 0, 2]], dtype=torch.float64)
    result = model.combined_rate(rates)
    assert result[0] == 0
    assert (result[1:] > 0).all()
    grid = rates.reshape(1, 3, 4).expand(2, 3, 4)
    torch.testing.assert_close(model.combined_rate(grid), result.expand(2, 3))


@pytest.mark.parametrize("architecture", KERNEL_ARCHITECTURES)
@pytest.mark.parametrize("transform", ["identity", "log1p"])
def test_neural_cached_center_matches_full_grid_with_all_branch_architectures(architecture, transform):
    torch.manual_seed(311)
    model = build_neural_mixed_kernel_model(2, (3, 5, 7, 9), architecture, hidden_channels=4,
                                            depth=3, combiner_input_transform=transform).double().eval()
    with torch.no_grad():
        model.combiner[-1].weight.fill_(0.1)
    environment = torch.randn(4, 2, 9, 9, dtype=torch.float64)
    burned = torch.zeros(4, 1, 9, 9, dtype=torch.float64)
    burned[1, 0, 4, 4] = 1
    burned[2, 0, 3, 4] = 1
    burned[3, 0, 0, 4] = 1
    expected = model(burned, environment).probability[:, 0, 4, 4]
    actual = center_probability(model, environment, burned)
    cached = model.center_from_features(model.center_features(environment), burned)
    torch.testing.assert_close(actual, expected, rtol=0, atol=1e-12)
    torch.testing.assert_close(cached, expected, rtol=0, atol=1e-12)
    assert actual[0] == 0 and actual[1] == 0
    assert (actual[2:] > 0).all()
    raw = model.branch_convolution_rates(burned, environment)[:, :, 4, 4]
    torch.testing.assert_close(raw, model.branch_center_convolution_rates(environment, burned),
                               rtol=0, atol=1e-12)
    result = model(burned.reshape(2, 2, 1, 9, 9), environment.reshape(2, 2, 2, 9, 9))
    torch.testing.assert_close(result.probability.reshape(4, 1, 9, 9),
                               model(burned, environment).probability, equal_nan=True)


@pytest.mark.parametrize("architecture", KERNEL_ARCHITECTURES)
@pytest.mark.parametrize("transform", ["identity", "log1p"])
def test_initial_combined_rate_matches_uniform_baseline_without_overlap_inflation(architecture, transform):
    torch.manual_seed(341)
    model = build_neural_mixed_kernel_model(2, (3, 5, 7, 9), architecture, hidden_channels=4,
                                            depth=3, combiner_input_transform=transform).double().eval()
    initialize_neural_mixed_kernel_rate(model, 0.03)
    rates = torch.rand(5, 4, dtype=torch.float64)
    torch.testing.assert_close(model.combined_rate(rates), rates.sum(dim=1), rtol=0, atol=1e-14)
    environment = torch.randn(3, 2, 9, 9, dtype=torch.float64)
    burned = torch.zeros(3, 1, 9, 9, dtype=torch.float64)
    burned[0, 0, 0, 0] = 1
    burned[1, 0, 3, 2:5] = 1
    raw = model.branch_center_convolution_rates(environment, burned)
    expected_rates = torch.tensor([0.03, 0.09, 0.0], dtype=torch.float64)
    torch.testing.assert_close(model.combined_rate(raw), expected_rates, rtol=0, atol=1e-14)
    expected = -torch.expm1(-expected_rates)
    torch.testing.assert_close(model.center_probability(environment, burned), expected, rtol=0, atol=1e-14)
    prediction = model(burned, environment)
    torch.testing.assert_close(prediction.rate[:, 0, 4, 4], expected_rates, rtol=0, atol=1e-14)


@pytest.mark.parametrize("architecture", KERNEL_ARCHITECTURES)
def test_neural_combiner_and_all_independent_branches_receive_gradients(architecture):
    torch.manual_seed(421)
    model = build_neural_mixed_kernel_model(2, (3, 5), architecture, hidden_channels=4,
                                            depth=3, combiner_hidden_channels=5).double()
    with torch.no_grad():
        model.combiner[-1].weight.fill_(0.05)
    environment = torch.randn(8, 2, 5, 5, dtype=torch.float64)
    burned = torch.zeros(8, 1, 5, 5, dtype=torch.float64)
    burned[:, 0, 1, 2] = 1
    burned[:, 0, 0, 2] = 1
    prediction = model.center_probability(environment, burned)
    prediction.square().mean().backward()
    for layer in (model.combiner[0], model.combiner[-1]):
        assert layer.weight.grad is not None and torch.isfinite(layer.weight.grad).all()
        assert (layer.weight.grad != 0).any()
    for branch in model.branches.values():
        gradients = [parameter.grad for parameter in branch.parameters() if parameter.grad is not None]
        assert gradients and all(torch.isfinite(gradient).all() for gradient in gradients)
        assert any((gradient != 0).any() for gradient in gradients)


def test_full_grid_masks_boundaries_and_duration_semantics_match_original_models():
    model = build_neural_mixed_kernel_model(1, (3, 5), "constant").double().eval()
    initialize_neural_mixed_kernel_rate(model, 0.04)
    environment = torch.zeros(2, 1, 9, 9, dtype=torch.float64)
    burned = torch.zeros(2, 1, 9, 9, dtype=torch.float64)
    burned[:, 0, 3, 4] = 1
    result = model(burned, environment, dt_hours=torch.tensor([1.0, 2.0], dtype=torch.float64))
    expected = -torch.expm1(-torch.tensor([0.04, 0.08], dtype=torch.float64))
    torch.testing.assert_close(result.probability[:, 0, 4, 4], expected, rtol=0, atol=1e-14)
    assert not result.valid[:, 0, 0, 0].any()
    assert model(burned, environment, boundary="zero").valid.all()
    assert result.valid[:, 0, 6, 6].all()
    assert result.probability[:, 0, 6, 6].eq(0).all()
    assert result.rate[:, 0, 6, 6].eq(0).all()
    feature_valid = torch.ones_like(environment, dtype=torch.bool)
    feature_valid[:, 0, 2, 4] = False
    missing = model(burned, environment, feature_valid=feature_valid)
    assert not missing.valid[:, 0, 4, 4].any()
    assert torch.isnan(missing.rate[:, 0, 4, 4]).all()
    zero = model(burned, environment, feature_valid=feature_valid, dt_hours=0)
    assert zero.valid[:, 0, 4, 4].all()
    assert zero.probability[:, 0, 4, 4].eq(0).all()
    burned[:, 0, 4, 4] = 1
    already = model(burned, environment, feature_valid=feature_valid)
    assert already.valid[:, 0, 4, 4].all()
    assert already.probability[:, 0, 4, 4].eq(0).all()
    burned[:, 0, 4, 4] = 0
    burned_valid = torch.ones_like(burned, dtype=torch.bool)
    burned_valid[:, 0, 2, 4] = False
    unavailable = model(burned, environment, burned_area_valid=burned_valid)
    assert not unavailable.rate_valid[:, 0, 4, 4].any()
    raw = model.branch_convolution_rates(burned, environment, burned_area_valid=burned_valid)
    assert torch.isfinite(raw[:, 0, 4, 4]).all()  # Smaller branch does not use that source.
    assert torch.isnan(raw[:, 1, 4, 4]).all()
    for duration in (-1, float("nan"), torch.ones(2, 1)):
        with pytest.raises(ValueError, match="dt_hours"):
            model(burned, environment, dt_hours=duration)


def _checkpoint(model):
    return dict(
        contract=dict(
            format_version=1, architecture="NeuralMixedNonnegativeKernel", in_channels=2,
            channels=["weather.temperature_2m", "terrain.slope_degrees"], kernel_size=model.kernel_size,
            kernel_model=neural_mixed_model_configuration(model), dt_hours=1.0, center_rate=0.0,
            eligibility="at_least_one_burned_neighbor",
        ),
        model_state_dict=model.state_dict(), normalization_mean=torch.tensor([15.0, -2.0], dtype=torch.float64),
        normalization_std=torch.tensor([3.0, 5.0], dtype=torch.float64), best_epoch=23,
    )


@pytest.mark.parametrize("architecture", KERNEL_ARCHITECTURES)
@pytest.mark.parametrize("transform", ["identity", "log1p"])
def test_saved_neural_model_keeps_frozen_preprocessing_parameters_and_zero_contact(tmp_path, architecture, transform):
    torch.manual_seed(32)
    model = build_neural_mixed_kernel_model(2, (3, 5), architecture, hidden_channels=4,
                                            depth=3, combiner_input_transform=transform).double().eval()
    with torch.no_grad():
        model.combiner[-1].weight.fill_(0.01)
    saved = _checkpoint(model)
    path = tmp_path / "neural.pt"
    torch.save(saved, path)
    loaded = load_neural_mixed_trained_model(path)
    normalized = torch.randn(2, 2, 11, 13, dtype=torch.float64)
    raw = normalized * saved["normalization_std"][:, None, None] + saved["normalization_mean"][:, None, None]
    burned = torch.zeros(2, 1, 11, 13, dtype=torch.float64)
    burned[:, 0, 5, 9] = 1
    expected = model(burned, normalized)
    actual = loaded(burned, raw, channel_names=saved["contract"]["channels"])
    torch.testing.assert_close(actual.probability, expected.probability, equal_nan=True)
    torch.testing.assert_close(actual.rate[burned == 0], expected.rate[burned == 0], equal_nan=True)
    assert loaded.best_epoch == 23
    assert actual.valid[:, 0, 5, 3].all()
    assert actual.rate_valid[:, 0, 5, 3].all()
    assert actual.rate[:, 0, 5, 3].eq(0).all()
    assert actual.probability[:, 0, 5, 3].eq(0).all()
    with pytest.raises(ValueError, match="channel names/order"):
        loaded(burned, raw, channel_names=list(reversed(saved["contract"]["channels"])))


@pytest.mark.parametrize("change,message", [
    (lambda saved: saved["contract"].update(architecture="MixedNonnegativeKernel"), "Unsupported"),
    (lambda saved: saved["contract"]["kernel_model"].pop("combiner_input_transform"), "configuration"),
    (lambda saved: saved["contract"]["kernel_model"].update(mixing_constraint="nonnegative"), "configuration"),
    (lambda saved: saved["contract"].update(kernel_size=3), "largest branch"),
    (lambda saved: saved["contract"].update(channels=["a", "a"]), "channel schema"),
    (lambda saved: saved.update(normalization_mean=torch.zeros(1)), "shape"),
    (lambda saved: saved.update(normalization_std=torch.tensor([0.0, 1.0])), "positive"),
    (lambda saved: saved.update(normalization_mean=torch.tensor([0, 1])), "finite"),
    (lambda saved: saved.update(normalization_std=torch.tensor([1.0, 1.0])), "same dtype"),
    (lambda saved: saved.update(best_epoch=True), "best_epoch"),
])
def test_invalid_saved_neural_contracts_fail_explicitly(tmp_path, change, message):
    saved = copy.deepcopy(_checkpoint(build_neural_mixed_kernel_model(2, (3, 5), "constant").double()))
    change(saved)
    path = tmp_path / "bad.pt"
    torch.save(saved, path)
    with pytest.raises(ValueError, match=message):
        load_neural_mixed_trained_model(path)


@pytest.mark.parametrize("option,value", [
    ("combiner_hidden_channels", 0), ("combiner_hidden_channels", True),
    ("combiner_dropout", -0.1), ("combiner_dropout", 1), ("combiner_dropout", float("nan")),
    ("combiner_input_transform", "unknown"), ("kernel_sizes", [3, 3]),
    ("branch_architecture", "signed"),
])
def test_invalid_neural_configurations_fail(option, value):
    with pytest.raises(ValueError):
        build_neural_mixed_kernel_model(2, **{option: value})


def test_invalid_readout_inputs_and_initial_rates_fail_explicitly():
    model = build_neural_mixed_kernel_model(2)
    for raw in (torch.zeros(2, 3), torch.zeros(2, 5)):
        with pytest.raises(ValueError, match="one last-axis"):
            model.combined_rate(raw)
    with pytest.raises(TypeError, match="floating"):
        model.combined_rate(torch.zeros(2, 4, dtype=torch.long))
    with pytest.raises(ValueError, match="dtype"):
        model.combined_rate(torch.zeros(2, 4, dtype=torch.float64))
    for bad in (-0.1, float("nan"), float("inf")):
        raw = torch.zeros(2, 4)
        raw[0, 0] = bad
        with pytest.raises(ValueError, match="finite nonnegative"):
            model.combined_rate(raw)
    for rate in (0, -1, True, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="strictly positive"):
            initialize_neural_mixed_kernel_rate(model, rate)
