"""Architecture-independent mathematical and saved-inference kernel contracts."""

import math

import pytest
import torch

from wildfire.inference import load_single_trained_model
from wildfire.models import KERNEL_ARCHITECTURES
from wildfire.models import build_kernel_model
from wildfire.models import initialize_kernel_rate
from wildfire.models import kernel_model_configuration
from wildfire.models import center_probability


@pytest.fixture(autouse=True)
def _few_threads():
    original = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(original)


@pytest.mark.parametrize("architecture", KERNEL_ARCHITECTURES)
@pytest.mark.parametrize("size", [3, 5, 9])
def test_optimized_and_cached_centers_match_public_grid_probability(architecture, size):
    torch.manual_seed(43)
    model = build_kernel_model(3, size, architecture, hidden_channels=5, depth=3).double().eval()
    environment = torch.randn(4, 3, size, size, dtype=torch.float64)
    burned = torch.randint(0, 2, (4, 1, size, size)).double()
    # Include a completely unburned patch and an already burned target.
    burned[0] = 0
    burned[1, 0, size // 2, size // 2] = 1
    expected = model(burned, environment).probability[:, 0, size // 2, size // 2]
    optimized = center_probability(model, environment, burned)
    cached = model.center_from_features(model.center_features(environment), burned)
    torch.testing.assert_close(optimized, expected, rtol=0, atol=1e-12)
    torch.testing.assert_close(cached, expected, rtol=0, atol=1e-12)
    assert optimized[0] == 0
    assert optimized[1] == 0
    rates = model.kernel_rates(environment, boundary="zero")
    assert (rates >= 0).all()
    assert rates[:, size * size // 2].eq(0).all()


@pytest.mark.parametrize("architecture", KERNEL_ARCHITECTURES)
def test_initialized_offset_rates_have_analytic_probability_and_finite_gradients(architecture):
    torch.manual_seed(54)
    model = build_kernel_model(2, 5, architecture, hidden_channels=4, depth=3).double()
    initialize_kernel_rate(model, 0.02)
    environment = torch.randn(3, 2, 5, 5, dtype=torch.float64)
    burned = torch.zeros(3, 1, 5, 5, dtype=torch.float64)
    burned[0, 0, 0, 0] = 1
    burned[1, 0, 0, :3] = 1
    prediction = model.center_probability(environment, burned)
    torch.testing.assert_close(
        prediction, torch.tensor([-math.expm1(-0.02), -math.expm1(-0.06), 0], dtype=torch.float64),
        rtol=0, atol=1e-14,
    )
    loss = (prediction - torch.tensor([1, 0, 0], dtype=torch.float64)).square().mean()
    loss.backward()
    gradients = [p.grad for p in model.parameters() if p.grad is not None]
    assert gradients and all(torch.isfinite(gradient).all() for gradient in gradients)
    assert any((gradient != 0).any() for gradient in gradients)


@pytest.mark.parametrize("architecture", KERNEL_ARCHITECTURES)
def test_saved_model_preserves_normalization_and_zero_contact_support(tmp_path, architecture):
    torch.manual_seed(17)
    model = build_kernel_model(2, 3, architecture, hidden_channels=4, depth=3).eval()
    contract = dict(
        format_version=1, architecture="LearnedNonnegativeKernel", in_channels=2,
        channels=["weather.temperature_2m", "terrain.slope_degrees"], kernel_size=3,
        kernel_model=kernel_model_configuration(model), dt_hours=1.0, center_rate=0.0,
        eligibility="at_least_one_burned_neighbor",
    )
    mean, std = torch.tensor([15.0, -2.0]), torch.tensor([3.0, 5.0])
    checkpoint = tmp_path / f"{architecture}.pt"
    torch.save(dict(
        contract=contract, model_state_dict=model.state_dict(),
        normalization_mean=mean, normalization_std=std, best_epoch=19,
    ), checkpoint)
    saved = load_single_trained_model(checkpoint)
    normalized = torch.randn(2, 3, 2, 7, 9)
    raw = normalized * std[:, None, None] + mean[:, None, None]
    burned = torch.zeros(2, 3, 1, 7, 9)
    burned[..., 0, 4, 6] = 1
    prediction = saved(burned, raw, channel_names=contract["channels"])
    expected = model(burned, normalized)
    torch.testing.assert_close(prediction.probability, expected.probability, equal_nan=True)
    torch.testing.assert_close(prediction.rate[burned == 0], expected.rate[burned == 0], equal_nan=True)
    assert saved.best_epoch == 19
    # This interior target has no burning cell within its kernel support.
    assert prediction.valid[..., 0, 2, 2].all()
    assert prediction.rate_valid[..., 0, 2, 2].all()
    assert prediction.probability[..., 0, 2, 2].eq(0).all()
    assert prediction.rate[..., 0, 2, 2].eq(0).all()
    feature_valid = torch.ones_like(raw, dtype=torch.bool)
    feature_valid[..., 0, 1, 1] = False
    missing = saved(burned, raw, channel_names=contract["channels"], feature_valid=feature_valid)
    assert not missing.valid[..., 0, 2, 2].any()
    with pytest.raises(ValueError, match="channel names/order"):
        saved(burned, raw, channel_names=list(reversed(contract["channels"])))


@pytest.mark.parametrize("architecture", ["cnn", "mlp", "residual_mlp"])
def test_dropout_regularizes_training_and_saved_inference_is_deterministic(architecture):
    torch.manual_seed(711)
    model = build_kernel_model(2, 3, architecture, hidden_channels=12, depth=3, dropout=0.5)
    environment = torch.randn(32, 2, 3, 3)
    burned = torch.zeros(32, 1, 3, 3)
    burned[:, 0, 0, 1] = 1
    model.train()
    first = model.center_probability(environment, burned)
    second = model.center_probability(environment, burned)
    assert not torch.equal(first, second)
    model.eval()
    first = model.center_probability(environment, burned)
    second = model.center_probability(environment, burned)
    torch.testing.assert_close(first, second, rtol=0, atol=0)


def test_pooled_environment_contract_and_spatial_cnn_are_distinct():
    torch.manual_seed(909)
    patches = torch.zeros(2, 1, 3, 3, dtype=torch.float64)
    patches[0, 0, 0, 0] = 1
    patches[1, 0, 2, 2] = 1
    burned = torch.zeros(2, 1, 3, 3, dtype=torch.float64)
    burned[:, 0, 0, 1] = 1
    for architecture in ("constant", "linear", "mlp", "residual_mlp"):
        model = build_kernel_model(1, 3, architecture, hidden_channels=4).double().eval()
        prediction = model.center_probability(patches, burned)
        torch.testing.assert_close(prediction[0], prediction[1], rtol=0, atol=0)
    cnn = build_kernel_model(1, 3, "cnn", hidden_channels=4).double().eval()
    assert not torch.isclose(*cnn.center_probability(patches, burned), rtol=0, atol=1e-12)


@pytest.mark.parametrize("option,value", [("dropout", -0.1), ("dropout", 1.0),
                                         ("dropout", float("nan")), ("depth", 0),
                                         ("depth", True), ("architecture", "signed")])
def test_invalid_kernel_configurations_fail_explicitly(option, value):
    with pytest.raises(ValueError):
        build_kernel_model(2, **{option: value})


def test_invalid_cached_patch_data_and_initial_rates_fail_explicitly():
    model = build_kernel_model(2, 3, "mlp")
    environment = torch.zeros(2, 2, 3, 3)
    burned = torch.zeros(2, 1, 3, 3)
    environment[0, 0, 0, 0] = torch.nan
    with pytest.raises(ValueError, match="finite"):
        model.center_features(environment)
    environment.zero_()
    burned[0, 0, 0, 0] = 0.5
    with pytest.raises(ValueError, match="binary"):
        model.center_probability(environment, burned)
    for invalid in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="strictly positive"):
            initialize_kernel_rate(model, invalid)
