"""Public rectangular inference with zero initial state and exterior context."""

from copy import deepcopy
import json

import numpy as np
import pytest
import torch

from tests.test_environment_rectangle import _fitted_model


@pytest.fixture
def model():
    return _fitted_model()


def _sample(model, leading=(1,)):
    shape = (*leading, 1, 5, 7)
    return dict(
        burned_area=torch.zeros(shape),
        burned_area_valid=torch.ones(shape, dtype=torch.bool),
        features=torch.zeros((*leading, 2, 5, 7)),
        feature_valid=torch.ones((*leading, 2, 5, 7), dtype=torch.bool),
        channel_names=model.channel_names,
        affine_transform=(375, 0, 500000, 0, -375, 4100000), epsg=32611,
    )


def _assert_details_equal(left, right):
    for field in ("probability", "valid", "rate", "rate_valid"):
        torch.testing.assert_close(getattr(left, field), getattr(right, field),
                                   rtol=0, atol=0, equal_nan=True)


def test_default_prediction_retains_every_edge_of_arrival_masked_rectangle(model):
    sample = _sample(model)
    sample["burned_area"].fill_(255)
    sample["burned_area_valid"].zero_()
    sample["burned_area"][0, 0, 0, 0] = 1
    sample["burned_area_valid"][0, 0, 0, 0] = True
    before = deepcopy(sample)

    result = model.predict(sample)
    expected = torch.zeros_like(sample["burned_area"])
    expected[0, 0, 0, 1] = 0.5
    expected[0, 0, 1, :2] = 0.5
    assert result.probability.shape == (1, 1, 5, 7)
    assert result.valid.all()
    expected_rate_valid = torch.ones_like(result.valid)
    expected_rate_valid[0, 0, 0, 0] = False  # Isolated prior burns have no fitted contact rate.
    torch.testing.assert_close(result.rate_valid, expected_rate_valid)
    torch.testing.assert_close(result.probability, expected)
    assert result.coordinates.shape == (5, 7, 2)
    assert torch.isfinite(result.coordinates).all()
    assert result.metadata["boundary"] == "zero"
    assert result.metadata["missing_burned_area"] == "unburned"
    assert result.metadata["assumed_unburned_cells"] == 34
    for field in ("burned_area", "burned_area_valid", "features", "feature_valid"):
        torch.testing.assert_close(sample[field], before[field], rtol=0, atol=0)
    metadata = json.loads(result.numpy()["metadata_json"].item())
    assert metadata["assumed_unburned_cells"] == 34


@pytest.mark.parametrize("missing", ["masked_one", "masked_sentinel", "nan", "inf", "negative_inf"])
def test_missing_initial_state_is_zero_and_can_become_a_new_burn(model, missing):
    sample = _sample(model)
    sample["burned_area"][0, 0, 2, 2] = 1
    target = (0, 0, 2, 3)
    if missing.startswith("masked"):
        sample["burned_area"][target] = 1 if missing == "masked_one" else 255
        sample["burned_area_valid"][target] = False
    else:
        sample["burned_area"][target] = {"nan": torch.nan, "inf": torch.inf,
                                        "negative_inf": -torch.inf}[missing]
    before = sample["burned_area"].clone()

    result = model.predict(sample)
    assert result.valid.all()
    # The unavailable stored state starts unburned, so its observed neighbor
    # gives it a first-new-burn probability of 1-exp(-log(2))=1/2.
    assert result.probability[target] == pytest.approx(0.5)
    assert result.probability[0, 0, 2, 4] == 0  # It is not an initial source.
    assert result.probability[0, 0, 2, 2] == 0  # The observed burn is absorbing.
    assert result.metadata["assumed_unburned_cells"] == 1
    torch.testing.assert_close(sample["burned_area"], before,
                               rtol=0, atol=0, equal_nan=True)

    unknown = model.predict(sample, missing_burned_area="unknown")
    assert not unknown.valid[target]
    assert torch.isnan(unknown.probability[target])
    assert not unknown.valid[0, 0, 2, 4]
    assert unknown.metadata["assumed_unburned_cells"] == 0


@pytest.mark.parametrize("leading", [(), (2,), (2, 3)])
def test_zero_initial_and_exterior_states_cannot_start_a_fire_without_a_known_source(model, leading):
    sample = _sample(model, leading)
    sample["burned_area"].fill_(1)
    sample["burned_area_valid"].zero_()
    sample["burned_area"][..., 0, 0] = torch.nan
    result = model.predict(sample)
    assert result.valid.all() and result.rate_valid.all()
    assert result.probability.eq(0).all() and result.rate.eq(0).all()
    assert result.metadata["assumed_unburned_cells"] == sample["burned_area"].numel()
    assert result.probability.shape == sample["burned_area"].shape


def test_explicit_unknown_boundary_retains_conservative_exterior_context(model):
    sample = _sample(model)
    result = model.predict(sample, boundary="unknown")
    expected = torch.zeros_like(result.valid)
    expected[..., 1:-1, 1:-1] = True
    torch.testing.assert_close(result.valid, expected)
    assert result.probability[expected].eq(0).all()
    assert torch.isnan(result.probability[~expected]).all()
    assert result.metadata["boundary"] == "unknown"


def test_initial_zero_assumption_preserves_environmental_gaps_and_reference_masks(model):
    sample = _sample(model)
    sample["burned_area_valid"][..., 2, 3] = False
    sample["feature_valid"][..., 0, 2, 3] = False
    before = deepcopy(sample)
    result = model.predict(sample)
    assert not result.valid[..., 2, 3].any()
    assert torch.isnan(result.probability[..., 2, 3]).all()
    assert result.valid[..., 0, 0].all() and result.valid[..., -1, -1].all()
    assert result.metadata["assumed_unburned_cells"] == 1
    for field in ("burned_area", "burned_area_valid", "features", "feature_valid"):
        torch.testing.assert_close(sample[field], before[field], rtol=0, atol=0)


def test_spatial_and_temporal_padding_remain_excluded_from_initial_zero_assumption(model):
    sample = _sample(model, leading=(2,))
    sample["pixel_valid"] = torch.ones((5, 7), dtype=torch.bool)
    sample["pixel_valid"][-1, -1] = False
    sample["time_valid"] = torch.tensor([True, False])
    sample["burned_area_valid"].zero_()
    result = model.predict(sample)
    assert result.metadata["assumed_unburned_cells"] == 34
    assert not result.valid[1].any()
    assert not result.valid[..., -1, -1].any()
    assert torch.isnan(result.probability[1]).all()
    assert torch.isnan(result.coordinates[-1, -1]).all()
    assert result.valid[0, 0, 0, 0]
    assert not sample["burned_area_valid"].any()


def test_sample_raw_and_legacy_prediction_adapters_share_zero_padded_defaults(model):
    sample = _sample(model)
    sample["burned_area"][0, 0, 2, 2] = 1
    sample["burned_area"][0, 0, 2, 3] = torch.nan
    options = dict(channel_names=model.channel_names,
                   burned_area_valid=sample["burned_area_valid"],
                   feature_valid=sample["feature_valid"])
    result = model.predict(sample)
    raw = model.predict(sample["burned_area"], sample["features"], **options)
    details = model.predict_details(sample["burned_area"], sample["features"], **options)
    for other in (raw, details, model.predict_sample_details(sample)):
        _assert_details_equal(result, other)
    torch.testing.assert_close(model.predict_proba(sample["burned_area"], sample["features"], **options),
                               result.probability, rtol=0, atol=0)
    for probability, coordinates in (
        model.predict_sample(sample),
        model.predict_coordinates(sample["burned_area"], sample["features"], **options,
                                  affine_transform=sample["affine_transform"], epsg=sample["epsg"]),
    ):
        torch.testing.assert_close(probability, result.probability, rtol=0, atol=0)
        torch.testing.assert_close(coordinates, result.coordinates, rtol=0, atol=0)


def test_fixed_horizons_use_filled_initial_state_without_resurrecting_masked_existing_burn(model):
    sample = _sample(model)
    sample["burned_area"][0, 0, 2, 2] = 1
    sample["burned_area"][0, 0, 2, 3] = 1
    sample["burned_area_valid"][0, 0, 2, 3] = False
    result = model.predict_cumulative(sample, method="fixed", hours=[0.5, 1, 2])
    assert result.valid.all()
    assert result.probability.shape == (3, 1, 1, 5, 7)
    for hour in result.hours:
        prediction = result.at(hours=hour)
        _assert_details_equal(prediction, model.predict(sample, dt_hours=hour))
        assert prediction.probability[0, 0, 2, 3] == pytest.approx(1 - 2 ** (-hour))
        assert prediction.burned_probability[0, 0, 2, 3] == prediction.probability[0, 0, 2, 3]
        assert prediction.burned_probability[0, 0, 2, 2] == 1
        assert prediction.metadata["assumed_unburned_cells"] == 1
    assert sample["burned_area"][0, 0, 2, 3] == 1
    assert not sample["burned_area_valid"][0, 0, 2, 3]


@pytest.mark.parametrize("policy", [None, True, "zero", "invalid"])
def test_public_prediction_rejects_unsupported_missing_state_policy(model, policy):
    sample = _sample(model)
    with pytest.raises(ValueError, match="missing_burned_area"):
        model.predict(sample, missing_burned_area=policy)
    with pytest.raises(ValueError, match="missing_burned_area"):
        model.predict_details(sample["burned_area"], sample["features"],
                              channel_names=model.channel_names, missing_burned_area=policy)
