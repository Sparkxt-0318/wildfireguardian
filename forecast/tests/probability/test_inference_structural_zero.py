"""Saved contact-only models expose zeros implied by fully known source states."""

import pytest
import torch

from wildfire.inference import load_single_trained_model
from wildfire.models import EnvironmentConditionedConvolution


def _saved_contact_model(tmp_path, family, kernel_size):
    """Use nonidentity saved preprocessing and an explicit contact-only contract."""
    torch.manual_seed(128 + kernel_size)
    channels = ("weather.temperature_2m", "terrain.slope_degrees")
    contract = dict(
        format_version=1, dt_hours=1.0, channels=list(channels), in_channels=2,
        kernel_size=kernel_size, hidden_channels=3,
        eligibility="at_least_one_burned_neighbor",
    )
    model = EnvironmentConditionedConvolution(2, kernel_size, 3)
    loader = load_single_trained_model
    contract.update(architecture="EnvironmentConditionedConvolution", center_rate=0.0)
    path = tmp_path / f"{family}_{kernel_size}.pt"
    torch.save(dict(
        contract=contract, model_state_dict=model.state_dict(),
        normalization_mean=torch.tensor([10.0, -3.0]),
        normalization_std=torch.tensor([2.0, 5.0]), best_epoch=2,
    ), path)
    return loader(path)


def _assert_known_zero(prediction, mask, family):
    assert prediction.valid[mask].all()
    assert prediction.probability[mask].eq(0).all()
    assert prediction.rate_valid[mask].all()
    assert prediction.rate[mask].eq(0).all()


def _assert_unknown(prediction, index, family):
    assert not prediction.valid[index]
    assert torch.isnan(prediction.probability[index])
    assert not prediction.rate_valid[index]
    assert torch.isnan(prediction.rate[index])


@pytest.mark.parametrize("family", ["exponential"])
@pytest.mark.parametrize("kernel_size", [3, 5, 7, 9])
@pytest.mark.parametrize("boundary", ["unknown", "zero"])
def test_saved_contact_model_returns_structural_zero_on_complete_unburned_neighborhoods(
    tmp_path, family, kernel_size, boundary,
):
    model = _saved_contact_model(tmp_path, family, kernel_size)
    height, width = 2 * kernel_size + 1, kernel_size + 4
    burned = torch.zeros(2, 3, 1, height, width)
    normalized = torch.randn(2, 3, 2, height, width)
    raw = normalized * model.std + model.mean
    result = model(burned, raw, channel_names=model.channel_names, boundary=boundary)
    expected_valid = torch.zeros_like(burned, dtype=torch.bool)
    radius = kernel_size // 2
    if boundary == "unknown":
        expected_valid[..., radius:-radius, radius:-radius] = True
    else:
        expected_valid[:] = True
    # A manual geometric mask checks source completeness independently of the
    # inference helper, including rectangular grids and batch/time dimensions.
    torch.testing.assert_close(result.valid, expected_valid)
    _assert_known_zero(result, expected_valid, family)
    assert torch.isnan(result.probability[~expected_valid]).all()
    if family == "exponential":
        torch.testing.assert_close(result.rate_valid, expected_valid)
    torch.testing.assert_close(model.mean[:, 0, 0], torch.tensor([10.0, -3.0]))
    torch.testing.assert_close(model.std[:, 0, 0], torch.tensor([2.0, 5.0]))


@pytest.mark.parametrize("family", ["exponential"])
@pytest.mark.parametrize("kernel_size", [3, 9])
@pytest.mark.parametrize("missing", ["nonfinite", "masked"])
def test_no_known_burned_neighbor_does_not_resolve_unknown_source_or_target(
    tmp_path, family, kernel_size, missing,
):
    model = _saved_contact_model(tmp_path, family, kernel_size)
    size = 3 * kernel_size
    burned = torch.zeros(1, 1, size, size)
    raw = model.mean.expand(1, 2, size, size).clone()
    burned_valid = torch.ones_like(burned, dtype=torch.bool)
    radius = kernel_size // 2
    target = (0, 0, kernel_size, kernel_size)
    source = (0, 0, kernel_size - radius, kernel_size + radius)
    if missing == "nonfinite":
        burned[source] = torch.nan
    else:
        burned[source] = 255  # A masked stored sentinel is not a burned source.
        burned_valid[source] = False
    for boundary in ("unknown", "zero"):
        result = model(
            burned, raw, channel_names=model.channel_names,
            burned_area_valid=burned_valid, boundary=boundary,
        )
        _assert_unknown(result, target, family)
        _assert_unknown(result, source, family)
        # A complete target outside the missing source's neighborhood is still
        # resolved, so the missing cell must not contaminate the full raster.
        unaffected = torch.zeros_like(burned_valid)
        unaffected[0, 0, 2 * kernel_size, 2 * kernel_size] = True
        _assert_known_zero(result, unaffected, family)


@pytest.mark.parametrize("family", ["exponential"])
def test_structural_zero_retains_environment_validity_and_already_burned_semantics(tmp_path, family):
    model = _saved_contact_model(tmp_path, family, 3)
    burned = torch.zeros(1, 1, 9, 9)
    burned[0, 0, 6, 6] = 1
    raw = model.mean.expand(1, 2, 9, 9).clone()
    feature_valid = torch.ones_like(raw, dtype=torch.bool)
    feature_valid[0, 0, 1, 1] = False
    feature_valid[0, 0, 6, 6] = False
    result = model(
        burned, raw, channel_names=model.channel_names, feature_valid=feature_valid,
    )
    _assert_unknown(result, (0, 0, 2, 2), family)
    known_zero = torch.zeros_like(burned, dtype=torch.bool)
    known_zero[0, 0, 4, 2] = True
    _assert_known_zero(result, known_zero, family)
    # Existing burned targets remain a valid zero new-burn probability even
    # though their environmental context cannot determine an exposure rate.
    burned_target = (0, 0, 6, 6)
    assert result.valid[burned_target] and result.probability[burned_target] == 0
    assert not result.rate_valid[burned_target]
    assert torch.isnan(result.rate[burned_target])
