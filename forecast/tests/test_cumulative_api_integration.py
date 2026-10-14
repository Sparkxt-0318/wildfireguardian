"""Public cumulative prediction/evaluation exports and checkpoint workflow."""

import json

import numpy as np
import pytest
import torch

from tests.test_prediction import categorical_model


def _categorical_forecast_sample(model, *, padding=None):
    burned = torch.zeros((2, 1, 5, 6))
    burned[:, 0, 2, 1] = 1
    features = torch.zeros((2, 4, 5, 6))
    features[:, 0] = -.2
    features[:, 1] = 1
    pixels = torch.ones((5, 6), dtype=torch.bool)
    times = torch.ones(2, dtype=torch.bool)
    if padding == "pixel":
        pixels[-1, -1] = False
    elif padding == "time":
        times[-1] = False
    sample = dict(burned_area=burned, features=features,
                  channel_names=model.channel_names, pixel_valid=pixels, time_valid=times)
    forecast = torch.stack((features, features))
    return sample, forecast


def _named_categorical_forecast(model, features, schema):
    if schema == "reordered":
        order = [2, 0, 3, 1]
        return dict(features=features[..., order, :, :],
                    channel_names=tuple(model.channel_names[index] for index in order))
    extra = torch.zeros_like(features[..., :1, :, :])
    # Include an additional categorical class as well as changing channel order.
    return dict(features=torch.cat((extra, features[..., [2, 0, 1, 3], :, :]), dim=-3),
                channel_names=("biome.biome_class=13", "biome.biome_class=5",
                               "weather.temperature_2m", "biome.biome_class=4",
                               "biome.biome_class=8"))


def test_evaluator_exports_share_the_same_public_function():
    import wildfire
    import wildfire.api as api
    from wildfire.cumulative_evaluation import evaluate_cumulative

    assert api.evaluate_cumulative is wildfire.evaluate_cumulative is evaluate_cumulative
    assert "evaluate_cumulative" in api.__all__
    assert "evaluate_cumulative" in wildfire.__all__


def test_loaded_public_model_forecasts_then_evaluates_with_original_reference_masks(tmp_path):
    from wildfire.api import CumulativePrediction, evaluate_cumulative, load_model
    from wildfire.models import EnvironmentConditionedConvolution, initialize_kernel_rate

    channels = ("fixture.temperature", "fixture.wind")
    with torch.random.fork_rng():
        torch.manual_seed(19)
        kernel = EnvironmentConditionedConvolution(2, 3, 2).double()
    initialize_kernel_rate(kernel, 0.7)
    contract = dict(
        format_version=1, architecture="EnvironmentConditionedConvolution",
        in_channels=2, channels=list(channels), kernel_size=3, hidden_channels=2,
        dt_hours=1.0, center_rate=0.0, eligibility="at_least_one_burned_neighbor",
    )
    checkpoint = tmp_path / "probability.pt"
    torch.save(dict(
        contract=contract, model_state_dict=kernel.state_dict(),
        normalization_mean=torch.zeros(2, dtype=torch.float64),
        normalization_std=torch.ones(2, dtype=torch.float64), best_epoch=1,
    ), checkpoint)
    model = load_model(checkpoint)
    burned = np.zeros((1, 1, 7, 9), dtype=np.float64)
    burned[0, 0, 3, 2] = 1
    burned_valid = np.ones(burned.shape, dtype=bool)
    burned_valid[0, 0, 3, 3] = False
    environment = np.ones((1, 2, 7, 9), dtype=np.float64)
    feature_valid = np.ones(environment.shape, dtype=bool)
    feature_valid[..., 0, 8] = False
    sample = dict(
        burned_area=burned, burned_area_valid=burned_valid,
        features=environment, feature_valid=feature_valid, channel_names=channels,
        time_utc=np.asarray([10_000]), event_id="public-workflow",
    )
    forecast = dict(
        features=np.stack((environment[:, ::-1], environment[:, ::-1])),
        feature_valid=np.stack((feature_valid[:, ::-1], feature_valid[:, ::-1])),
        channel_names=channels[::-1],
    )
    result = model.predict_cumulative(
        sample, hours=[2, 1], n_samples=128, seed=7, trajectory_batch_size=32,
        environmental_forecast=forecast, boundary="zero",
    )
    assert isinstance(result, CumulativePrediction)
    assert result.probability.shape == (2, 1, 1, 7, 9)
    assert result.metadata["method"] == "recursive"
    assert result.metadata["environment_policy"] == "hourly_forecast"
    assert result.metadata["missing_burned_area"] == "unburned"
    assert result.metadata["assumed_unburned_cells"] == 1
    assert result.at(hours=1).probability[0, 0, 3, 4] == 0
    assert result.at(hours=2).probability[0, 0, 3, 4] > 0
    for hour in result.hours:
        endpoint = result.at(hours=hour)
        assert endpoint.burned_probability[0, 0, 3, 2] == 1
        assert endpoint.probability[0, 0, 3, 2] == 0
        assert not endpoint.rate_valid.any()
        assert not endpoint.valid[0, 0, 0, 8]
        assert torch.isnan(endpoint.probability[0, 0, 0, 8])
        assert endpoint.mc_standard_error is not None
        assert endpoint.confidence_lower is not None
        assert endpoint.confidence_upper is not None

    states = np.stack((burned[0], burned[0].copy(), burned[0].copy()))
    states[1:, 0, 3, 3] = 1
    states[2, 0, 3, 4] = 1
    observed_valid = np.ones(states.shape, dtype=bool)
    observed_valid[0, 0, 3, 3] = False
    reference = dict(
        burned_area=states, burned_area_valid=observed_valid,
        time_utc=np.asarray([10_000, 13_600, 17_200]), event_id="public-workflow",
    )
    cohort = np.zeros((7, 9), dtype=bool)
    cohort[3, 2:5] = True
    report = result.evaluate(reference, hours=[1, 2], cohort_mask=cohort)
    assert report == evaluate_cumulative(result, reference, hours=[1, 2], cohort_mask=cohort)
    assert [row["hours"] for row in report["per_horizon"]] == [1, 2]
    for row in report["per_horizon"]:
        assert row["coverage"]["initially_burned_excluded_cells"] == 1
        assert row["coverage"]["evaluated_cells"] == 1
    assert report["per_horizon"][0]["metrics"]["brier"] == 0
    q2 = result.at(hours=2).probability[0, 0, 3, 4].item()
    assert report["per_horizon"][1]["metrics"]["brier"] == pytest.approx((1 - q2)**2)
    total = result.evaluate(reference, hours=2, quantity="burned", cohort_mask=cohort)
    assert total["per_horizon"][0]["coverage"]["evaluated_cells"] == 3
    assert total["per_horizon"][0]["metrics"]["positive_sample_count"] == 3
    assert not reference["burned_area_valid"][0, 0, 3, 3]
    json.dumps(report, allow_nan=False)
    json.dumps(total, allow_nan=False)


@pytest.mark.parametrize("schema", ["reordered", "superset"])
@pytest.mark.parametrize("padding", ["pixel", "time"])
@pytest.mark.parametrize("stored_value", [0, .5, 2])
def test_categorical_forecast_projection_ignores_pixel_and_time_padding_without_a_feature_mask(
    categorical_model, schema, padding, stored_value,
):
    sample, features = _categorical_forecast_sample(categorical_model, padding=padding)
    if padding == "pixel":
        features[..., 1:, -1, -1] = stored_value
    else:
        features[:, -1, 1:] = stored_value
    ordered = dict(features=features, channel_names=categorical_model.channel_names)
    projected = _named_categorical_forecast(categorical_model, features, schema)
    assert "feature_valid" not in ordered and "feature_valid" not in projected
    controls = dict(hours=[1, 2], n_samples=9, seed=11, trajectory_batch_size=8, boundary="zero")
    expected = categorical_model.predict_cumulative(sample, environmental_forecast=ordered, **controls)
    actual = categorical_model.predict_cumulative(sample, environmental_forecast=projected, **controls)
    for name in ("probability", "valid", "rate", "rate_valid", "burned_probability",
                 "mc_standard_error", "confidence_lower", "confidence_upper"):
        torch.testing.assert_close(getattr(actual, name), getattr(expected, name),
                                   rtol=0, atol=0, equal_nan=True)
    assert actual.metadata == expected.metadata
    if padding == "pixel":
        assert not actual.valid[..., -1, -1].any()
        assert torch.isnan(actual.probability[..., -1, -1]).all()
    else:
        assert not actual.valid[:, -1].any()
        assert torch.isnan(actual.probability[:, -1]).all()


@pytest.mark.parametrize("schema", ["reordered", "superset"])
@pytest.mark.parametrize("stored_value", [0, .5])
def test_categorical_forecast_still_rejects_invalid_one_hot_groups_on_known_interior_support(
    categorical_model, schema, stored_value,
):
    sample, features = _categorical_forecast_sample(categorical_model, padding="pixel")
    features[..., 1:, 2, 3] = stored_value
    forecast = _named_categorical_forecast(categorical_model, features, schema)
    with pytest.raises(ValueError, match="one-hot"):
        categorical_model.predict_cumulative(sample, hours=1, n_samples=1,
                                             environmental_forecast=forecast, boundary="zero")


def test_forecast_full_feature_mask_shape_is_validated_before_padding_support_is_applied(categorical_model):
    sample, features = _categorical_forecast_sample(categorical_model, padding="time")
    forecast = _named_categorical_forecast(categorical_model, features, "superset")
    # Omitting the cutoff-time dimension must fail even though one cutoff is padded.
    forecast["feature_valid"] = torch.ones((2, 5, 5, 6), dtype=torch.bool)
    with pytest.raises(ValueError, match="feature_valid.*complete"):
        categorical_model.predict_cumulative(sample, hours=1, n_samples=1,
                                             environmental_forecast=forecast, boundary="zero")


def _recursive_rectangle(*, leading=()):
    from tests.test_rollout import CHANNELS, _inputs, _model

    burned, features = _inputs(rate=1000, leading=leading)
    return _model(), dict(burned_area=burned, features=features, channel_names=CHANNELS)


def _assert_prediction_fields_equal(actual, expected):
    for name in ("probability", "valid", "rate", "rate_valid", "burned_probability",
                 "mc_standard_error", "confidence_lower", "confidence_upper"):
        left, right = getattr(actual, name), getattr(expected, name)
        if left is None or right is None:
            assert left is right
        else:
            torch.testing.assert_close(left, right, rtol=0, atol=0, equal_nan=True)


def test_recursive_default_preserves_full_rectangle_at_every_horizon_and_records_boundary():
    model, sample = _recursive_rectangle()
    # These are missing observations inside the original rectangle. Filling
    # them does not turn a stored masked one into an already-burned cell.
    valid = torch.ones_like(sample["burned_area"], dtype=torch.bool)
    sample["burned_area"][0, 2, 2] = 1
    valid[0, 2, 2] = False
    sample["burned_area"][0, 0, 0] = torch.nan
    sample["burned_area_valid"] = valid
    sample["affine_transform"] = (375, 0, 500000, 0, -375, 4100000)
    sample["epsg"] = 32611
    original_burned = sample["burned_area"].clone()
    original_valid = valid.clone()
    controls = dict(hours=[1, 2, 4], n_samples=17, seed=13, trajectory_batch_size=8)
    default = model.predict_cumulative(sample, **controls)
    explicit_zero = model.predict_cumulative(sample, boundary="zero", **controls)
    unknown = model.predict_cumulative(sample, boundary="unknown", **controls)

    assert default.probability.shape == unknown.probability.shape == (3, 1, 5, 6)
    assert default.burned_probability.shape == default.valid.shape == (3, 1, 5, 6)
    assert default.valid.all()
    assert torch.isfinite(default.probability).all()
    assert torch.isfinite(default.burned_probability).all()
    assert default.metadata["boundary"] == explicit_zero.metadata["boundary"] == "zero"
    assert unknown.metadata["boundary"] == "unknown"
    assert default.metadata["missing_burned_area"] == "unburned"
    assert default.metadata["assumed_unburned_cells"] == 2
    _assert_prediction_fields_equal(default, explicit_zero)
    assert default.metadata == explicit_zero.metadata

    # The first missing cell becomes a source only after the first interval.
    assert default.at(hours=1).probability[0, 2, 2] == 1
    assert default.at(hours=1).probability[0, 2, 3] == 0
    assert default.at(hours=2).probability[0, 2, 3] == 1
    coverage = [int(unknown.at(hours=hour).valid.sum()) for hour in controls["hours"]]
    assert coverage[0] < 5 * 6
    assert coverage[0] > coverage[1] > coverage[2]
    assert not unknown.at(hours=1).valid[0, 0, 0]
    assert torch.isnan(unknown.at(hours=1).probability[0, 0, 0])
    assert default.coordinates.shape == unknown.coordinates.shape == (5, 6, 2)
    np.testing.assert_array_equal(default.coordinates, unknown.coordinates)
    for hour in controls["hours"]:
        np.testing.assert_array_equal(default.at(hours=hour).coordinates, default.coordinates)
        np.testing.assert_array_equal(unknown.at(hours=hour).coordinates, default.coordinates)
    torch.testing.assert_close(sample["burned_area"], original_burned,
                               rtol=0, atol=0, equal_nan=True)
    torch.testing.assert_close(sample["burned_area_valid"], original_valid)


def test_recursive_default_zero_exterior_cannot_start_a_fire_without_an_observed_source():
    model, sample = _recursive_rectangle()
    sample["burned_area"].zero_()
    valid = torch.ones_like(sample["burned_area"], dtype=torch.bool)
    sample["burned_area"][0, 2, 1] = 1
    valid[0, 2, 1] = False
    sample["burned_area"][0, 0, 0] = torch.nan
    sample["burned_area_valid"] = valid
    result = model.predict_cumulative(sample, hours=[1, 2, 6], n_samples=3,
                                      seed=5, trajectory_batch_size=2)
    assert result.valid.shape == (3, 1, 5, 6)
    assert result.valid.all()
    assert result.probability.eq(0).all()
    assert result.burned_probability.eq(0).all()
    assert result.mc_standard_error.eq(0).all()
    assert result.metadata["boundary"] == "zero"
    assert result.metadata["assumed_unburned_cells"] == 2


def test_recursive_default_does_not_fill_a_missing_environmental_value_inside_the_rectangle():
    model, sample = _recursive_rectangle()
    sample["burned_area"][0, 2, 2] = torch.nan
    feature_valid = torch.ones_like(sample["features"], dtype=torch.bool)
    feature_valid[0, 2, 2] = False
    sample["feature_valid"] = feature_valid
    result = model.predict_cumulative(sample, hours=[1, 2, 4], n_samples=3,
                                      seed=5, trajectory_batch_size=2)
    assert result.probability.shape == (3, 1, 5, 6)
    assert result.metadata["boundary"] == "zero"
    assert result.metadata["assumed_unburned_cells"] == 1
    assert not result.valid[:, 0, 2, 2].any()
    assert torch.isnan(result.probability[:, 0, 2, 2]).all()
    assert torch.isnan(result.burned_probability[:, 0, 2, 2]).all()
    # The observed seed stays known even when nearby context is incomplete.
    assert result.valid[:, 0, 2, 1].all()
    assert result.burned_probability[:, 0, 2, 1].eq(1).all()
    assert result.at(hours=1).valid[0, 0, 0]
    assert not sample["feature_valid"][0, 2, 2]


def test_recursive_default_does_not_turn_physical_or_time_padding_into_known_cells():
    model, sample = _recursive_rectangle(leading=(2,))
    pixels = torch.ones((5, 6), dtype=torch.bool)
    pixels[-1, -1] = False
    sample["pixel_valid"] = pixels
    sample["time_valid"] = torch.tensor([True, False])
    # Missing observations in padding must never count as assumed unburned.
    sample["burned_area"][:, 0, -1, -1] = torch.nan
    sample["burned_area"][1] = torch.nan
    result = model.predict_cumulative(sample, hours=[1, 2, 4], n_samples=3,
                                      seed=5, trajectory_batch_size=2)
    assert result.probability.shape == (3, 2, 1, 5, 6)
    assert result.metadata["boundary"] == "zero"
    assert result.metadata["assumed_unburned_cells"] == 0
    assert not result.valid[..., -1, -1].any()
    assert not result.valid[:, 1].any()
    for name in ("probability", "burned_probability", "mc_standard_error",
                 "confidence_lower", "confidence_upper"):
        value = getattr(result, name)
        assert torch.isnan(value[..., -1, -1]).all()
        assert torch.isnan(value[:, 1]).all()
    assert result.valid[:, 0, 0, 2, 1].all()
    assert sample["pixel_valid"].shape == (5, 6)
    assert sample["time_valid"].tolist() == [True, False]


def test_recursive_ordinary_and_fixed_share_zero_exterior_defaults():
    model, sample = _recursive_rectangle()
    ordinary = model.predict(sample)
    ordinary_unknown = model.predict(sample, boundary="unknown")
    ordinary_zero = model.predict(sample, boundary="zero")
    _assert_prediction_fields_equal(ordinary, ordinary_zero)
    assert ordinary.valid.all()
    assert not ordinary_unknown.valid[0, 0, 0]
    assert ordinary_zero.valid.all()

    fixed = model.predict_cumulative(sample, method="fixed", hours=[.5, 2])
    fixed_unknown = model.predict_cumulative(sample, method="fixed", hours=[.5, 2],
                                             boundary="unknown")
    fixed_zero = model.predict_cumulative(sample, method="fixed", hours=[.5, 2],
                                          boundary="zero")
    _assert_prediction_fields_equal(fixed, fixed_zero)
    assert fixed.probability.shape == (2, 1, 5, 6)
    assert fixed.valid.all()
    assert not fixed_unknown.valid[:, 0, 0, 0].any()
    assert fixed_zero.valid.all()
    assert fixed.rate_valid.any()
    assert fixed.mc_standard_error is None
