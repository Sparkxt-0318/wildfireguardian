"""Direct-score semantics, exact center gradients, and saved inference contract."""

from copy import deepcopy

import pytest
import torch

from wildfire_burned_area_hourly.probability_model.direct_convolution.model import DirectEnvironmentConditionedConvolution, apply_direct_convolution, center_raw_score
from wildfire_burned_area_hourly.probability_model.direct_convolution.inference import load_trained_model


@pytest.mark.parametrize("k", [3, 5, 7, 9])
@pytest.mark.parametrize("constraint", ["signed", "nonnegative"])
def test_raw_center_matches_public_value_and_all_gradients(k, constraint):
    """Double precision comparison checks independent full/center calculations."""
    torch.manual_seed(10 + k)
    model = DirectEnvironmentConditionedConvolution(2, k, 3, constraint).double()
    reference = deepcopy(model)
    e = torch.randn(3, 2, k, k, dtype=torch.float64, requires_grad=True)
    e_full = e.detach().clone().requires_grad_(True)
    b = torch.randint(0, 2, (3, 1, k, k)).double()
    b[:, :, k // 2, k // 2] = 0
    optimized = center_raw_score(model, b, e)
    public = reference(b, e_full).raw_score[:, 0, k // 2, k // 2]
    torch.testing.assert_close(optimized, public, atol=1e-12, rtol=0)
    coefficients = torch.tensor([0.25, -0.75, 1.0], dtype=torch.float64)
    (optimized * coefficients).sum().backward()
    (public * coefficients).sum().backward()
    torch.testing.assert_close(e.grad, e_full.grad, atol=1e-12, rtol=0)
    for parameter, expected in zip(model.parameters(), reference.parameters()):
        torch.testing.assert_close(parameter.grad, expected.grad, atol=1e-12, rtol=0)
    assert model.kernel_coefficients(e.detach())[:, k * k // 2, k // 2, k // 2].eq(0).all()


@pytest.mark.parametrize("coefficient,target,expected_gradient", [(2.0, 0.0, 4.0), (-2.0, 1.0, -6.0)])
def test_unclipped_training_score_has_gradient_beyond_probability_bounds(coefficient, target, expected_gradient):
    model = DirectEnvironmentConditionedConvolution(1, 3, 1)
    with torch.no_grad():
        for parameter in model.parameters():
            parameter.zero_()
        model.kernel_network[2].bias[0] = coefficient
    b = torch.zeros(1, 1, 3, 3)
    b[0, 0, 0, 0] = 1
    e = torch.zeros(1, 1, 3, 3)
    model.train()
    raw = center_raw_score(model, b, e)
    public = model(b, e)
    assert raw.item() == coefficient
    assert public.raw_score[0, 0, 1, 1].item() == coefficient
    assert public.probability[0, 0, 1, 1].item() == min(1, max(0, coefficient))
    ((raw - target) ** 2).mean().backward()
    assert model.kernel_network[2].bias.grad[0].item() == expected_gradient
    assert model.kernel_network[2].bias.grad[4].item() == 0
    model.eval()
    assert center_raw_score(model, b, e).item() == coefficient


def test_signed_coefficient_orientation_and_zero_center():
    b = torch.zeros(1, 1, 5, 5)
    b[0, 0, 1, 3] = 1  # Offset (-1,+1) relative to center (2,2).
    kernels = torch.zeros(1, 9, 5, 5)
    kernels[:, 2] = -0.4
    kernels[:, 6] = 0.9  # Opposite offset must not contribute.
    output = apply_direct_convolution(b, kernels)
    assert output.raw_score[0, 0, 2, 2].item() == pytest.approx(-0.4)
    assert output.probability[0, 0, 2, 2].item() == 0
    assert output.valid[0, 0, 2, 2]


def test_missing_sources_and_environment_stay_unknown_even_when_coefficients_are_zero():
    model = DirectEnvironmentConditionedConvolution(1, 3, 1)
    for parameter in model.parameters():
        parameter.data.zero_()
    b = torch.zeros(1, 1, 7, 7)
    e = torch.zeros_like(b)
    source_valid = torch.ones_like(b, dtype=torch.bool)
    source_valid[0, 0, 2, 2] = False
    feature_valid = torch.ones_like(e, dtype=torch.bool)
    feature_valid[0, 0, 4, 4] = False
    output = model(b, e, burned_area_valid=source_valid, feature_valid=feature_valid)
    assert not output.valid[0, 0, 3, 3]
    assert torch.isnan(output.raw_score[0, 0, 3, 3])
    assert torch.isnan(output.probability[0, 0, 3, 3])
    assert not output.valid[0, 0, 0, 3]
    assert output.valid[0, 0, 1, 5]
    assert model(b, e, boundary="zero").valid.all()


def test_already_burned_zero_does_not_claim_a_new_burn_when_context_missing():
    model = DirectEnvironmentConditionedConvolution(1)
    b = torch.ones(1, 1, 3, 3)
    e = torch.full_like(b, torch.nan)
    result = model(b, e)
    assert result.valid.all()
    assert result.raw_score.eq(0).all() and result.probability.eq(0).all()


@pytest.mark.parametrize("horizon", [0.0, 2.0, -1.0, float("nan"), float("inf")])
def test_direct_coefficients_cannot_be_rescaled_to_another_horizon(horizon):
    model = DirectEnvironmentConditionedConvolution(1)
    with pytest.raises(ValueError, match="dt_hours=1.0"):
        model(torch.zeros(1, 1, 3, 3), torch.zeros(1, 1, 3, 3), dt_hours=horizon)


def test_leading_snapshot_dimensions_are_independent():
    model = DirectEnvironmentConditionedConvolution(1)
    b = torch.zeros(2, 3, 1, 5, 5)
    b[..., 1, 1] = 1
    e = torch.randn_like(b)
    result = model(b, e, dt_hours=torch.ones(2, 3))
    flat = model(b.flatten(0, 1), e.flatten(0, 1))
    torch.testing.assert_close(result.raw_score.flatten(0, 1), flat.raw_score, equal_nan=True)
    with pytest.raises(ValueError, match="leading dimensions"):
        model(b, e, dt_hours=torch.ones(2))


def _checkpoint(k=3, encoded=False):
    channels = ["temperature", "wind_u", "wind_v", "slope", "tree"]
    if encoded:
        channels += [f"biome={code}" for code in range(1, 15)]
    model = DirectEnvironmentConditionedConvolution(len(channels), k, 3)
    contract = {
        "format_version": 1, "architecture": "DirectEnvironmentConditionedConvolution",
        "dt_hours": 1.0, "center_coefficient": 0.0, "output_link": "identity",
        "training_clipping": False, "evaluation_clipping": [0.0, 1.0],
        "kernel_constraint": "signed", "kernel_size": k, "hidden_channels": 3,
        "in_channels": len(channels), "channels": channels,
        "eligibility": "at_least_one_burned_neighbor",
    }
    if encoded:
        sources = channels[:5] + ["biome"]
        info = [{"name": name, "source_channel": name, "encoding": "continuous"}
                for name in channels[:5]]
        info += [{"name": f"biome={code}", "source_channel": "biome",
                  "encoding": "one_hot", "class_code": code} for code in range(1, 15)]
        contract.update(source_channels=sources, channel_info=info,
                        categorical_encoding="one_hot", categorical_classes={"biome": list(range(1, 15))},
                        channel_groups={**{name: [i] for i, name in enumerate(sources[:5])},
                                        "biome": list(range(5, 19))})
    return {
        "model_state_dict": model.state_dict(), "contract": contract,
        "normalization_mean": torch.arange(len(channels), dtype=torch.float32),
        "normalization_std": torch.arange(1, len(channels) + 1, dtype=torch.float32),
        "best_epoch": 2,
    }


@pytest.mark.parametrize("k", [3, 5, 7, 9])
def test_checkpoint_preserves_training_normalization_kernel_size_and_structural_zeros(tmp_path, k):
    torch.manual_seed(6)
    saved = _checkpoint(k)
    path = tmp_path / "checkpoint.pt"
    torch.save(saved, path)
    fitted = load_trained_model(path)
    size = 3 * k
    b = torch.zeros(1, 1, size, size)
    b[0, 0, size // 2, size // 2] = 1
    normalized = torch.randn(1, 5, size, size)
    raw_environment = normalized * fitted.std + fitted.mean
    result = fitted(b, raw_environment, channel_names=fitted.channel_names)
    direct = fitted.model(b, normalized)
    mask = result.valid
    torch.testing.assert_close(result.raw_score[mask], direct.raw_score[mask], atol=3e-6, rtol=1e-5)
    assert fitted.model.kernel_size == k and not fitted.training
    assert result.valid[0, 0, k // 2, k // 2]  # Complete, all-unburned source neighborhood.
    assert result.raw_score[0, 0, k // 2, k // 2].item() == 0
    assert result.probability[0, 0, k // 2, k // 2].item() == 0
    assert result.valid[0, 0, size // 2, size // 2]
    assert result.raw_score[0, 0, size // 2, size // 2].item() == 0
    assert torch.isnan(result.probability[0, 0, 0, 0])
    with pytest.raises(ValueError, match="channel names/order"):
        fitted(b, raw_environment, channel_names=fitted.channel_names[::-1])


def test_raw_one_hot_groups_are_checked_before_saved_normalization(tmp_path):
    saved = _checkpoint(encoded=True)
    path = tmp_path / "checkpoint.pt"
    torch.save(saved, path)
    fitted = load_trained_model(path)
    b = torch.zeros(1, 1, 5, 5)
    b[0, 0, 1, 1] = 1
    e = torch.zeros(1, 19, 5, 5)
    e[:, 5] = 1
    assert fitted(b, e, channel_names=fitted.channel_names).valid[0, 0, 2, 2]
    e[:, 6] = 1
    with pytest.raises(ValueError, match="one-hot input"):
        fitted(b, e, channel_names=fitted.channel_names)
    e[:, 6] = 0
    valid = torch.ones_like(e, dtype=torch.bool)
    valid[:, 5, 2, 2] = False
    output = fitted(b, e, channel_names=fitted.channel_names, feature_valid=valid)
    assert not output.valid[0, 0, 2, 2]


@pytest.mark.parametrize("key,value", [
    ("architecture", "EnvironmentConditionedConvolution"), ("output_link", "exponential"),
    ("training_clipping", True), ("evaluation_clipping", [-1.0, 1.0]),
    ("center_coefficient", 0.1), ("kernel_constraint", "invalid"), ("dt_hours", 2.0),
])
def test_legacy_or_incompatible_checkpoint_cannot_be_silently_reinterpreted(tmp_path, key, value):
    saved = _checkpoint()
    saved["contract"][key] = value
    path = tmp_path / "checkpoint.pt"
    torch.save(saved, path)
    with pytest.raises(ValueError, match="checkpoint contract"):
        load_trained_model(path)


def test_tampered_center_mask_checkpoint_is_rejected(tmp_path):
    saved = _checkpoint()
    saved["model_state_dict"]["off_center"][:, 4] = 1
    path = tmp_path / "checkpoint.pt"
    torch.save(saved, path)
    with pytest.raises(ValueError, match="center coefficient"):
        load_trained_model(path)
