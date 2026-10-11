"""Pre-exponential multiscale mixture mathematics and saved-grid contracts."""

import copy
import math

import pytest
import torch

from wildfire.models import KERNEL_ARCHITECTURES
from wildfire.models import initialize_kernel_rate
from wildfire.inference import load_mixed_trained_model
from wildfire.models import build_mixed_kernel_model
from wildfire.models import initialize_mixed_kernel_rate
from wildfire.models import mixed_model_configuration
from wildfire.models import center_probability


@pytest.fixture(autouse=True)
def _few_threads():
    original = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(original)


@pytest.mark.parametrize("constraint", ["nonnegative", "simplex"])
def test_mixture_combines_convolution_rates_before_exponential(constraint):
    model = build_mixed_kernel_model(1, (3, 5), "constant", mixing_constraint=constraint).double()
    initialize_kernel_rate(model.branches["3"], 0.2)
    initialize_kernel_rate(model.branches["5"], 0.7)
    with torch.no_grad():
        if constraint == "nonnegative":
            model.mixing_logits.copy_(torch.tensor([math.log(math.expm1(2)), math.log(math.expm1(3))]))
        else:
            model.mixing_logits.copy_(torch.log(torch.tensor([0.25, 0.75])))
    environment = torch.zeros(1, 1, 5, 5, dtype=torch.float64)
    burned = torch.zeros(1, 1, 5, 5, dtype=torch.float64)
    burned[0, 0, 1, 2] = 1  # One source in both branch supports.
    burned[0, 0, 0, 2] = 1  # One source only in the larger branch.
    rates = model.branch_center_convolution_rates(environment, burned)
    torch.testing.assert_close(rates, torch.tensor([[0.2, 1.4]], dtype=torch.float64), rtol=0, atol=1e-14)
    weights = model.mixing_weights()
    expected = -torch.expm1(-(rates * weights).sum(dim=1))
    actual = model.center_probability(environment, burned)
    torch.testing.assert_close(actual, expected, rtol=0, atol=1e-14)
    weighted_probabilities = ((-torch.expm1(-rates)) * weights).sum(dim=1)
    assert not torch.allclose(actual, weighted_probabilities, rtol=0, atol=1e-6)
    assert (weights >= 0).all()
    if constraint == "simplex":
        torch.testing.assert_close(weights.sum(), torch.tensor(1.0, dtype=torch.float64))
    else:
        assert weights.sum() > 1


def test_native_branch_offsets_embed_centrally_and_keep_center_zero():
    model = build_mixed_kernel_model(1, (3, 5), "constant").double()
    initialize_kernel_rate(model.branches["3"], 0.2)
    initialize_kernel_rate(model.branches["5"], 0.7)
    environment = torch.zeros(1, 1, 5, 5, dtype=torch.float64)
    combined = model.kernel_rates(environment, boundary="zero")[0, :, 2, 2].reshape(5, 5)
    weights = model.mixing_weights()
    expected = torch.ones((5, 5), dtype=torch.float64) * (0.7 * weights[1])
    expected[1:4, 1:4] += 0.2 * weights[0]
    expected[2, 2] = 0
    torch.testing.assert_close(combined, expected, rtol=0, atol=1e-14)
    native = model.branch_kernel_rates(environment)
    assert native[3].shape == (1, 9, 5, 5)
    assert native[5].shape == (1, 25, 5, 5)
    assert native[3][:, 4, 2, 2].eq(0).all()
    assert native[5][:, 12, 2, 2].eq(0).all()
    # Every branch observes the combined model's largest-context mask.
    assert torch.isnan(native[3][:, :, 0, 0]).all()
    assert torch.isnan(native[5][:, :, 0, 0]).all()


@pytest.mark.parametrize("architecture", KERNEL_ARCHITECTURES)
@pytest.mark.parametrize("constraint", ["nonnegative", "simplex"])
def test_cached_and_optimized_center_match_public_grid_for_every_branch_family(architecture, constraint):
    torch.manual_seed(23)
    model = build_mixed_kernel_model(3, (3, 5, 7, 9), architecture, hidden_channels=4,
                                     depth=3, mixing_constraint=constraint).double().eval()
    environment = torch.randn(4, 3, 9, 9, dtype=torch.float64)
    burned = torch.randint(0, 2, (4, 1, 9, 9)).double()
    burned[:, 0, 4, 4] = 0
    burned[0] = 0
    burned[1, 0, 4, 4] = 1
    expected = model(burned, environment).probability[:, 0, 4, 4]
    optimized = center_probability(model, environment, burned)
    cached_features = model.center_features(environment)
    assert cached_features is environment
    cached = model.center_from_features(cached_features, burned)
    torch.testing.assert_close(optimized, expected, rtol=0, atol=1e-12)
    torch.testing.assert_close(cached, expected, rtol=0, atol=1e-12)
    assert optimized[0] == 0
    assert optimized[1] == 0
    grid_rates = model.kernel_rates(environment, boundary="zero")
    assert grid_rates[:, 40].eq(0).all()
    assert (grid_rates >= 0).all()
    # Leading snapshot and batch dimensions retain the inherited interface.
    result = model(burned.reshape(2, 2, 1, 9, 9), environment.reshape(2, 2, 3, 9, 9))
    torch.testing.assert_close(result.probability.reshape(4, 1, 9, 9),
                               model(burned, environment).probability, equal_nan=True)


@pytest.mark.parametrize("architecture", KERNEL_ARCHITECTURES)
@pytest.mark.parametrize("constraint", ["nonnegative", "simplex"])
def test_initialization_equalizes_effective_offset_rate_across_overlapping_branches(architecture, constraint):
    torch.manual_seed(42)
    model = build_mixed_kernel_model(2, (3, 5, 7, 9), architecture, hidden_channels=4,
                                     depth=3, mixing_constraint=constraint).double().eval()
    # Initialization must account for existing coefficients, including unequal ones.
    with torch.no_grad():
        model.mixing_logits.copy_(torch.tensor([-1.0, 0.3, 1.1, 2.3], dtype=torch.float64))
    initial_weights = model.mixing_weights().clone()
    initialize_mixed_kernel_rate(model, 0.03)
    torch.testing.assert_close(model.mixing_weights(), initial_weights, rtol=0, atol=0)
    environment = torch.randn(3, 2, 9, 9, dtype=torch.float64)
    rates = model.kernel_rates(environment, boundary="zero")
    expected = torch.full_like(rates, 0.03)
    expected[:, 40] = 0
    torch.testing.assert_close(rates, expected, rtol=0, atol=1e-14)
    burned = torch.zeros(3, 1, 9, 9, dtype=torch.float64)
    burned[0, 0, 0, 0] = 1
    burned[1, 0, 3, 2:5] = 1
    expected_probability = torch.tensor([-math.expm1(-0.03), -math.expm1(-0.09), 0], dtype=torch.float64)
    torch.testing.assert_close(model.center_probability(environment, burned), expected_probability,
                               rtol=0, atol=1e-14)


@pytest.mark.parametrize("architecture", KERNEL_ARCHITECTURES)
def test_loss_backpropagates_to_mixing_coefficients_and_every_branch(architecture):
    torch.manual_seed(71)
    model = build_mixed_kernel_model(2, (3, 5), architecture, hidden_channels=4, depth=3).double()
    environment = torch.randn(6, 2, 5, 5, dtype=torch.float64)
    burned = torch.zeros(6, 1, 5, 5, dtype=torch.float64)
    burned[:, 0, 1, 2] = 1
    burned[:, 0, 0, 2] = 1
    prediction = model.center_probability(environment, burned)
    prediction.square().mean().backward()
    assert model.mixing_logits.grad is not None
    assert torch.isfinite(model.mixing_logits.grad).all()
    assert (model.mixing_logits.grad != 0).all()
    for branch in model.branches.values():
        gradients = [p.grad for p in branch.parameters() if p.grad is not None]
        assert gradients and all(torch.isfinite(gradient).all() for gradient in gradients)
        assert any((gradient != 0).any() for gradient in gradients)


def test_masks_boundaries_burned_targets_zero_horizons_and_no_contact_remain_explicit():
    model = build_mixed_kernel_model(1, (3, 5), "constant").double().eval()
    initialize_mixed_kernel_rate(model, 0.05)
    environment = torch.zeros(1, 1, 9, 9, dtype=torch.float64)
    burned = torch.zeros(1, 1, 9, 9, dtype=torch.float64)
    prediction = model(burned, environment)
    assert prediction.valid[0, 0, 4, 4]
    assert prediction.rate_valid[0, 0, 4, 4]
    assert prediction.probability[0, 0, 4, 4] == 0
    assert prediction.rate[0, 0, 4, 4] == 0
    assert not prediction.valid[0, 0, 0, 0]
    assert model(burned, environment, boundary="zero").valid.all()
    feature_valid = torch.ones_like(environment, dtype=torch.bool)
    feature_valid[0, 0, 2, 4] = False  # Outside size3 context, within size5.
    missing = model(burned, environment, feature_valid=feature_valid)
    assert not missing.valid[0, 0, 4, 4]
    burned_valid = torch.ones_like(burned, dtype=torch.bool)
    burned_valid[0, 0, 2, 4] = False
    missing = model(burned, environment, burned_area_valid=burned_valid)
    assert not missing.valid[0, 0, 4, 4]
    zero_horizon = model(burned, environment, feature_valid=feature_valid, dt_hours=0)
    assert zero_horizon.valid[0, 0, 4, 4]
    assert zero_horizon.probability[0, 0, 4, 4] == 0
    burned[0, 0, 4, 4] = 1
    already = model(burned, environment, feature_valid=feature_valid)
    assert already.valid[0, 0, 4, 4]
    assert already.probability[0, 0, 4, 4] == 0


def _checkpoint(model):
    return dict(
        contract=dict(
            format_version=1, architecture="MixedNonnegativeKernel", in_channels=2,
            channels=["weather.temperature_2m", "terrain.slope_degrees"], kernel_size=model.kernel_size,
            kernel_model=mixed_model_configuration(model), dt_hours=1.0, center_rate=0.0,
            eligibility="at_least_one_burned_neighbor",
        ),
        model_state_dict=model.state_dict(), normalization_mean=torch.tensor([15.0, -2.0], dtype=torch.float64),
        normalization_std=torch.tensor([3.0, 5.0], dtype=torch.float64), best_epoch=19,
    )


@pytest.mark.parametrize("architecture", KERNEL_ARCHITECTURES)
@pytest.mark.parametrize("constraint", ["nonnegative", "simplex"])
def test_saved_mixed_model_preserves_parameters_normalization_and_no_contact_support(tmp_path, architecture, constraint):
    torch.manual_seed(22)
    model = build_mixed_kernel_model(2, (3, 5), architecture, hidden_channels=4, depth=3,
                                     mixing_constraint=constraint).double().eval()
    saved = _checkpoint(model)
    path = tmp_path / "mixed.pt"
    torch.save(saved, path)
    loaded = load_mixed_trained_model(path)
    normalized = torch.randn(2, 2, 11, 13, dtype=torch.float64)
    raw = normalized * saved["normalization_std"][:, None, None] + saved["normalization_mean"][:, None, None]
    burned = torch.zeros(2, 1, 11, 13, dtype=torch.float64)
    burned[:, 0, 5, 9] = 1
    expected = model(burned, normalized)
    actual = loaded(burned, raw, channel_names=saved["contract"]["channels"])
    torch.testing.assert_close(actual.probability, expected.probability, equal_nan=True)
    torch.testing.assert_close(actual.rate[burned == 0], expected.rate[burned == 0], equal_nan=True)
    torch.testing.assert_close(loaded.model.mixing_weights(), model.mixing_weights(), rtol=0, atol=0)
    assert loaded.best_epoch == 19
    assert actual.valid[:, 0, 5, 3].all()
    assert actual.rate_valid[:, 0, 5, 3].all()
    assert actual.probability[:, 0, 5, 3].eq(0).all()
    assert actual.rate[:, 0, 5, 3].eq(0).all()
    with pytest.raises(ValueError, match="channel names/order"):
        loaded(burned, raw, channel_names=list(reversed(saved["contract"]["channels"])))
    with pytest.raises(ValueError, match="Unsupported"):
        saved["contract"]["architecture"] = "LearnedNonnegativeKernel"
        torch.save(saved, path)
        load_mixed_trained_model(path)


@pytest.mark.parametrize("change,message", [
    (lambda saved: saved["contract"]["kernel_model"].pop("mixing_constraint"), "configuration"),
    (lambda saved: saved["contract"]["kernel_model"].update(extra=True), "configuration"),
    (lambda saved: saved["contract"].update(kernel_size=3), "largest branch"),
    (lambda saved: saved["contract"].update(channels=["a", "a"]), "channel schema"),
    (lambda saved: saved["contract"].update(in_channels=True), "channel schema"),
    (lambda saved: saved.update(normalization_mean=torch.zeros(1)), "shape"),
    (lambda saved: saved.update(normalization_std=torch.tensor([0.0, 1.0])), "positive"),
    (lambda saved: saved.update(normalization_mean=torch.tensor([0, 1])), "finite"),
    (lambda saved: saved.update(normalization_std=torch.tensor([1.0, 1.0])), "same dtype"),
    (lambda saved: saved.update(best_epoch=-1), "best_epoch"),
])
def test_invalid_saved_mixed_contracts_fail_before_prediction(tmp_path, change, message):
    model = build_mixed_kernel_model(2, (3, 5), "constant").double()
    saved = copy.deepcopy(_checkpoint(model))
    change(saved)
    path = tmp_path / "bad.pt"
    torch.save(saved, path)
    with pytest.raises(ValueError, match=message):
        load_mixed_trained_model(path)


@pytest.mark.parametrize("option,value", [
    ("kernel_sizes", []), ("kernel_sizes", [3, 3]), ("kernel_sizes", [5, 3]),
    ("kernel_sizes", [3, 4]), ("kernel_sizes", [True, 3]), ("kernel_sizes", [1, 3]),
    ("branch_architecture", "signed"), ("mixing_constraint", "signed"),
    ("depth", 0), ("dropout", float("nan")), ("hidden_channels", True),
])
def test_invalid_model_configurations_fail_explicitly(option, value):
    with pytest.raises(ValueError):
        build_mixed_kernel_model(2, **{option: value})


def test_invalid_center_data_and_initial_rates_fail_explicitly():
    model = build_mixed_kernel_model(2, (3, 5), "constant")
    environment = torch.zeros(2, 2, 5, 5)
    burned = torch.zeros(2, 1, 5, 5)
    with pytest.raises(ValueError, match="complete"):
        model.center_features(environment[..., :3, :3])
    with pytest.raises(ValueError, match="dtype"):
        model.center_features(environment.double())
    environment[0, 0, 0, 0] = torch.nan
    with pytest.raises(ValueError, match="finite"):
        model.center_features(environment)
    environment.zero_()
    burned[0, 0, 0, 0] = 0.5
    with pytest.raises(ValueError, match="binary"):
        model.center_probability(environment, burned)
    for rate in (0, -1, float("nan"), float("inf"), True):
        with pytest.raises(ValueError, match="strictly positive"):
            initialize_mixed_kernel_rate(model, rate)
    with torch.no_grad():
        model.mixing_logits[0] = torch.nan
    with pytest.raises(RuntimeError, match="nonfinite"):
        model.mixing_weights()
