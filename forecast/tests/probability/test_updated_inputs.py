"""Semantic checks for the five continuous predictors plus 14 biome planes."""

from copy import deepcopy
import json

from affine import Affine
import numpy as np
import pytest
import torch

from wildfire.data import WildfireSequenceDataset
from wildfire.examples import CHANNELS
from wildfire.inference import load_single_trained_model
from wildfire.models import EnvironmentConditionedConvolution
from wildfire.prepare import prepare_event
from wildfire.prepare import resolve_channel_schema
from tests.probability.test_training import (
    _expected_hourly_targets, _write_raster, hourly_training_bundle,
)
from wildfire.train import fit_normalization
from wildfire.train import load_split
from wildfire.train import probability_metrics
from wildfire.train import weighted_calibration


BIOME_SOURCE = "biome.biome_class"
SOURCE_CHANNELS = tuple(CHANNELS) + (BIOME_SOURCE,)
BIOME_CLASSES = {BIOME_SOURCE: list(range(1, 15))}
ENCODED_CHANNELS = tuple(CHANNELS) + tuple(f"{BIOME_SOURCE}={code}" for code in range(1, 15))


@pytest.fixture
def biome_training_bundle(hourly_training_bundle):
    """Only three of the fourteen published classes occur in this fixture."""
    root, event = hourly_training_bundle
    transform = Affine(*event["transform"])
    codes = np.array([4, 5, 14], dtype=np.float32)[np.indices((5, 5)).sum(axis=0) % 3]
    path = root / "regions" / event["id"] / "biome" / "biome_class_375m.tif"
    _write_raster(path, codes, transform)
    legend = {"classes": [{"code": code, "name": f"Fixture biome {code}"} for code in range(1, 15)]}
    (root / "biome_classes.json").write_text(json.dumps(legend))
    return root, event, codes, path


def _prepare_biome(root, event):
    return prepare_event(
        root, event, 0, np.random.default_rng(7), 1000, 1000,
        chunk_hours=2, source_channels=SOURCE_CHANNELS,
        categorical_classes=BIOME_CLASSES, channel_names=ENCODED_CHANNELS,
    )


def test_schema_expands_selected_source_into_all_fourteen_biome_indicators(biome_training_bundle):
    root, _, _, _ = biome_training_bundle
    schema = resolve_channel_schema(root, source_channels=SOURCE_CHANNELS)
    assert tuple(schema["source_channels"]) == SOURCE_CHANNELS
    assert tuple(schema["channels"]) == ENCODED_CHANNELS
    assert schema["categorical_encoding"] == "one_hot"
    assert schema["categorical_classes"] == BIOME_CLASSES
    assert list(schema["channel_groups"][BIOME_SOURCE]) == list(range(5, 19))
    for index, info in enumerate(schema["channel_info"]):
        assert info["name"] == ENCODED_CHANNELS[index]
        if index < 5:
            assert info["source_channel"] == CHANNELS[index]
            assert info["encoding"] == "continuous"
        else:
            assert info["source_channel"] == BIOME_SOURCE
            assert info["encoding"] == "one_hot"
            assert info["class_code"] == index - 4
    # The complete published vocabulary does not shrink to locally seen codes.
    assert {info["class_code"] for info in schema["channel_info"][5:]} == set(range(1, 15))


def test_preparation_keeps_inactive_biome_zeros_known_and_preserves_hourly_targets(biome_training_bundle):
    root, event, codes, path = biome_training_bundle
    dataset = WildfireSequenceDataset(
        root, events=[event["id"]], channels=SOURCE_CHANNELS,
        categorical_classes=BIOME_CLASSES, sequence_length=5,
    )
    try:
        reference = dataset[0]
        assert tuple(dataset.channel_names) == ENCODED_CHANNELS
    finally:
        dataset.close()
    assert reference["feature_valid"][:, 5:].all()
    assert not reference["features"][:, 5].any()  # Class 1 is absent and known.
    assert (reference["features"][:, 5:].sum(dim=1) == 1).all()
    expected = _expected_hourly_targets(reference)
    arrays, audit, files = _prepare_biome(root, event)
    obtained = {(int(t), int(r), int(c)): index for index, (t, r, c) in
                enumerate(zip(arrays["time_utc"], arrays["row"], arrays["col"]))}
    assert arrays["environment"].shape == (len(expected), 19, 3, 3)
    assert len(obtained) == len(arrays["target"]) and obtained.keys() == expected.keys()
    assert audit["environmental_context_rejections"] == 0
    assert path in files
    for key, (target, environment, burned) in expected.items():
        index = obtained[key]
        assert arrays["target"][index] == target
        assert arrays["weight"][index] == 1
        np.testing.assert_array_equal(arrays["environment"][index], environment)
        np.testing.assert_array_equal(arrays["burned"][index], burned)
        biome = arrays["environment"][index, 5:]
        np.testing.assert_array_equal(biome.sum(axis=0), np.ones((3, 3)))
        _, row, col = key
        np.testing.assert_array_equal(
            biome.argmax(axis=0) + 1, codes[row - 1:row + 2, col - 1:col + 2],
        )


@pytest.mark.parametrize("invalid_code", [-9999, 15, 1.5])
def test_unavailable_or_unknown_biome_context_excludes_targets_without_imputing_a_class(
    biome_training_bundle, invalid_code,
):
    root, event, codes, path = biome_training_bundle
    codes[0, 2] = invalid_code
    _write_raster(path, codes, Affine(*event["transform"]))
    dataset = WildfireSequenceDataset(
        root, events=[event["id"]], channels=SOURCE_CHANNELS,
        categorical_classes=BIOME_CLASSES, sequence_length=5,
    )
    try:
        reference = dataset[0]
    finally:
        dataset.close()
    assert not reference["feature_valid"][:, 5:, 0, 2].any()
    assert not reference["features"][:, 5:, 0, 2].any()
    expected = _expected_hourly_targets(reference)
    arrays, audit, _ = _prepare_biome(root, event)
    obtained = {(int(t), int(r), int(c)) for t, r, c in
                zip(arrays["time_utc"], arrays["row"], arrays["col"])}
    assert obtained == expected.keys()
    assert audit["environmental_context_rejections"] > 0
    assert all(not (row == 1 and abs(col - 2) <= 1) for _, row, col in obtained)
    assert np.isfinite(arrays["environment"]).all()
    np.testing.assert_array_equal(arrays["environment"][:, 5:].sum(axis=1),
                                  np.ones((len(arrays["target"]), 3, 3)))


@pytest.fixture
def one_hot_training_cache(biome_training_bundle, tmp_path):
    root, event, _, _ = biome_training_bundle
    schema = resolve_channel_schema(root, source_channels=SOURCE_CHANNELS)
    arrays, _, _ = _prepare_biome(root, event)
    keep = arrays["burned"].sum(axis=(1, 2, 3)) > 0
    arrays = {key: values[keep] for key, values in arrays.items()}
    directory = tmp_path / "one_hot_cache"
    directory.mkdir()
    np.savez_compressed(directory / "train.npz", **arrays)
    metadata = {**schema, "kernel_size": 3, "dt_hours": 1,
                "event_ids": [event["id"]], "splits": {event["id"]: "train"},
                "eligibility": "at_least_one_burned_neighbor"}
    return directory, metadata, arrays


def test_cache_accepts_complete_biome_groups_and_training_moments_keep_absent_classes_finite(
    one_hot_training_cache,
):
    directory, metadata, arrays = one_hot_training_cache
    cached = load_split(directory, "train", metadata)
    assert cached.environment.shape[1] == 19
    assert (cached.neighbor_count > 0).all()
    np.testing.assert_array_equal(cached.environment, arrays["environment"])
    mean, scale = fit_normalization(cached, chunk_size=2)
    assert mean.shape == scale.shape == (19,)
    assert np.isfinite(mean).all() and np.isfinite(scale).all() and (scale > 0).all()
    absent = [5 + code - 1 for code in range(1, 15) if code not in (4, 5, 14)]
    np.testing.assert_array_equal(mean[absent], np.zeros(len(absent)))
    np.testing.assert_array_equal(scale[absent], np.ones(len(absent)))


@pytest.mark.parametrize("corruption", ["all_zero", "multiple_active", "fractional"])
def test_cache_rejects_invalid_one_hot_groups(one_hot_training_cache, corruption):
    directory, metadata, original = one_hot_training_cache
    arrays = {key: value.copy() for key, value in original.items()}
    biome = arrays["environment"][0, 5:, 1, 1]
    biome[:] = 0
    if corruption == "multiple_active":
        biome[:2] = 1
    elif corruption == "fractional":
        biome[:2] = 0.5
    np.savez_compressed(directory / "train.npz", **arrays)
    with pytest.raises(ValueError):
        load_split(directory, "train", metadata)


@pytest.mark.parametrize("corruption", ["reordered_class_codes", "reordered_group", "omitted_class"])
def test_cache_rejects_inconsistent_encoded_schema(one_hot_training_cache, corruption):
    directory, original, _ = one_hot_training_cache
    metadata = deepcopy(original)
    if corruption == "reordered_class_codes":
        metadata["channel_info"][5]["class_code"] = 2
    elif corruption == "reordered_group":
        metadata["channel_groups"][BIOME_SOURCE] = list(reversed(metadata["channel_groups"][BIOME_SOURCE]))
    else:
        metadata["categorical_classes"][BIOME_SOURCE] = list(range(1, 14))
    with pytest.raises(ValueError):
        load_split(directory, "train", metadata)


@pytest.fixture
def one_hot_checkpoint(one_hot_training_cache, tmp_path):
    directory, schema, _ = one_hot_training_cache
    data = load_split(directory, "train", schema)
    mean, scale = map(torch.from_numpy, fit_normalization(data))
    torch.manual_seed(71)
    model = EnvironmentConditionedConvolution(19, hidden_channels=4).eval()
    contract = {**schema, "format_version": 1, "architecture": "EnvironmentConditionedConvolution",
                "center_rate": 0.0, "in_channels": 19, "hidden_channels": 4}
    saved = {"contract": contract, "model_state_dict": model.state_dict(),
             "normalization_mean": mean, "normalization_std": scale, "best_epoch": 2}
    path = tmp_path / "one_hot.pt"
    torch.save(saved, path)
    return path, saved, model, data


def test_checkpoint_preserves_encoded_contract_and_reproduces_raw_one_hot_prediction(one_hot_checkpoint):
    path, saved, model, data = one_hot_checkpoint
    trained = load_single_trained_model(path)
    assert trained.channel_names == ENCODED_CHANNELS
    for key in ("source_channels", "categorical_encoding", "categorical_classes", "channel_info", "channel_groups"):
        assert trained.contract[key] == saved["contract"][key]
    raw = torch.from_numpy(data.environment[:3])
    burned = torch.from_numpy(data.burned[:3])
    # Zero inactive indicators remain valid environmental observations.
    validity = torch.ones_like(raw, dtype=torch.bool)
    result = trained(burned, raw, channel_names=ENCODED_CHANNELS, feature_valid=validity)
    normalized = (raw - trained.mean) / trained.std
    expected = model(burned, normalized, feature_valid=validity)
    assert result.valid[:, 0, 1, 1].all()
    torch.testing.assert_close(result.probability[:, 0, 1, 1], expected.probability[:, 0, 1, 1], rtol=0, atol=1e-7)
    with pytest.raises(ValueError, match="channel names/order differ"):
        trained(burned, raw, channel_names=SOURCE_CHANNELS)
    with pytest.raises(ValueError, match="channel names/order differ"):
        trained(burned, raw, channel_names=ENCODED_CHANNELS[:5] + ENCODED_CHANNELS[5:][::-1])


@pytest.mark.parametrize("corruption", ["all_zero", "fractional"])
def test_inference_rejects_invalid_known_biome_but_respects_missing_context_mask(one_hot_checkpoint, corruption):
    path, _, _, data = one_hot_checkpoint
    trained = load_single_trained_model(path)
    raw = torch.from_numpy(data.environment[:1].copy())
    burned = torch.from_numpy(data.burned[:1])
    raw[:, 5:, 1, 1] = 0
    if corruption == "fractional":
        raw[:, 5:7, 1, 1] = 0.5
    with pytest.raises(ValueError):
        trained(burned, raw, channel_names=ENCODED_CHANNELS)
    validity = torch.ones_like(raw, dtype=torch.bool)
    validity[:, 5:, 1, 1] = False
    result = trained(burned, raw, channel_names=ENCODED_CHANNELS, feature_valid=validity)
    assert not result.valid[0, 0, 1, 1] and torch.isnan(result.probability[0, 0, 1, 1])


@pytest.mark.parametrize("corruption", ["reordered_class_codes", "reordered_group", "omitted_class"])
def test_checkpoint_rejects_inconsistent_encoded_schema(one_hot_checkpoint, corruption):
    path, original, _, _ = one_hot_checkpoint
    saved = deepcopy(original)
    if corruption == "reordered_class_codes":
        saved["contract"]["channel_info"][5]["class_code"] = 2
    elif corruption == "reordered_group":
        saved["contract"]["channel_groups"][BIOME_SOURCE] = list(range(18, 4, -1))
    else:
        saved["contract"]["categorical_classes"][BIOME_SOURCE] = list(range(1, 14))
    torch.save(saved, path)
    with pytest.raises(ValueError):
        load_single_trained_model(path)


def test_inverse_weights_recover_population_prevalence_and_class_brier_from_balanced_sample():
    # All two positives were retained; two of eighteen negatives were sampled.
    target = np.array([1, 1, 0, 0], dtype=np.float32)
    probability = np.array([0.6, 0.2, 0.4, 0.1], dtype=np.float64)
    weight = np.array([1, 1, 9, 9], dtype=np.float64)
    metrics = probability_metrics(target, probability, weight, np.ones(4))
    assert metrics["sample_positive_fraction"] == 0.5
    assert metrics["weighted_prevalence"] == 0.1
    assert metrics["represented_population_weight"] == 20
    assert metrics["positive_population_weight"] == 2
    assert metrics["mean_probability"] == pytest.approx(0.265)
    assert metrics["positive_class_brier"] == pytest.approx(0.4)
    assert metrics["negative_class_brier"] == pytest.approx(0.085)
    assert metrics["brier"] == pytest.approx(0.1165)
    prevalence = metrics["weighted_prevalence"]
    assert metrics["brier"] == pytest.approx(
        prevalence * metrics["positive_class_brier"] + (1 - prevalence) * metrics["negative_class_brier"],
    )


def test_reliability_bins_use_population_weights_for_outcomes_and_calibration_error():
    target = np.array([1, 0, 1, 0], dtype=np.float32)
    probability = np.array([0.015, 0.015, 0.1, 0.8], dtype=np.float64)
    weight = np.array([1, 9, 1, 9], dtype=np.float64)
    result = weighted_calibration(target, probability, weight)
    populated = [entry for entry in result["bins"] if entry["sample_count"]]
    assert [entry["represented_population_weight"] for entry in populated] == [10, 1, 9]
    assert [entry["population_fraction"] for entry in populated] == [0.5, 0.05, 0.45]
    assert [entry["weighted_outcome_rate"] for entry in populated] == [0.1, 1, 0]
    assert [entry["mean_probability"] for entry in populated] == pytest.approx([0.015, 0.1, 0.8])
    assert result["weighted_expected_calibration_error"] == pytest.approx(0.4475)
    for entry in result["bins"]:
        if entry["sample_count"] == 0:
            assert entry["mean_probability"] is entry["weighted_outcome_rate"] is None


def test_reliability_bins_include_zero_and_one_and_assign_inner_edges_once():
    probability = np.array([0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1], dtype=np.float64)
    target = np.array([0, 1, 0, 1, 0, 1, 0, 1], dtype=np.float32)
    weight = np.arange(1, 9, dtype=np.float64)
    result = weighted_calibration(target, probability, weight)
    bins = result["bins"]
    assert [entry["sample_count"] for entry in bins] == [1, 1, 1, 1, 1, 1, 2]
    assert [entry["represented_population_weight"] for entry in bins] == [1, 2, 3, 4, 5, 6, 15]
    assert sum(entry["population_fraction"] for entry in bins) == pytest.approx(1)
    assert [entry["upper_inclusive"] for entry in bins] == [False] * 6 + [True]
    assert bins[0]["mean_probability"] == 0
    assert bins[-1]["mean_probability"] == pytest.approx((7 * 0.5 + 8 * 1) / 15)
    assert bins[-1]["weighted_outcome_rate"] == pytest.approx(8 / 15)
