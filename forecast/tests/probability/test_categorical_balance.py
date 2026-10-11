"""Independent numerical checks for training-only covariate rarity weighting."""
import argparse
from copy import deepcopy
import json
from types import SimpleNamespace

import numpy as np
import pytest

from wildfire.metrics import add_categorical_balance_arguments
from wildfire.metrics import categorical_balance_settings
from wildfire.metrics import categorical_group_metrics
from wildfire.metrics import fit_categorical_balance
from wildfire.metrics import validate_categorical_balance_settings


def _fixture():
    sources = ["biome", "cover"]
    classes = {"biome": [4, 8, 13], "cover": [1, 2]}
    channels = [f"{source}={code}" for source in sources for code in classes[source]]
    info = [dict(name=f"{source}={code}", source_channel=source, encoding="one_hot", categorical=True,
                 class_code=code, class_name=f"Class {code}")
            for source in sources for code in classes[source]]
    metadata = dict(channels=channels, source_channels=sources, channel_info=info,
                    categorical_encoding="one_hot", categorical_classes=classes,
                    channel_groups={"biome": [0, 1, 2], "cover": [3, 4]}, kernel_size=9)
    environment = np.zeros((4, 5, 3, 3), dtype=np.float32)
    environment[:, 0] = 1
    environment[0, 0, 0, 0] = 0
    environment[0, 1, 0, 0] = 1  # Rare class 8 appears only in the corner.
    environment[:3, 3] = 1
    environment[3, 4] = 1
    data = SimpleNamespace(environment=environment, weight=np.array([1., 1., 2., 4.]),
                           target=np.array([1., 0., 1., 0.], dtype=np.float32))
    return data, metadata


def test_weights_match_hand_calculation_for_presence_and_source_means():
    data, metadata = _fixture()
    before_environment, before_weight = data.environment.copy(), data.weight.copy()
    effective, audit = fit_categorical_balance(data, metadata, chunk_size=1)
    # Biome4: all rows, frequency1, factor1. Biome8: first row, mass1/8,
    # factor sqrt8. Cover1/2 each have mass4/8, hence factor sqrt2.
    # Distinct class means come first, followed by the source mean.
    raw = np.array([((1 + np.sqrt(8)) / 2 + np.sqrt(2)) / 2] + [(1 + np.sqrt(2)) / 2] * 3)
    normalizer = (raw[0] + raw[1] + 2 * raw[2] + 4 * raw[3]) / 8
    expected = np.array([1., 1., 2., 4.]) * raw / normalizer
    np.testing.assert_allclose(effective, expected, rtol=1e-14, atol=0)
    assert audit["normalizer"] == pytest.approx(normalizer)
    assert audit["kernel_size"] == 3  # Actual crop, not metadata's outer 9x9.
    assert effective.dtype == np.float64 and effective.sum() == pytest.approx(8.)
    assert effective[0] > data.weight[0]
    classes = audit["sources"][0]["classes"]
    assert classes[0]["population_presence_frequency"] == 1
    assert classes[1]["population_presence_frequency"] == .125
    assert classes[1]["rarity_factor"] == pytest.approx(np.sqrt(8))
    assert classes[1]["effective_presence_weight"] == pytest.approx(expected[0])
    assert classes[2]["observed_in_training"] is False and classes[2]["rarity_factor"] == 1
    assert audit["effective_sample_size_population"] == pytest.approx(64 / 22)
    assert audit["effective_sample_size_optimization"] == pytest.approx(expected.sum() ** 2 / np.dot(expected, expected))
    np.testing.assert_array_equal(data.environment, before_environment)
    np.testing.assert_array_equal(data.weight, before_weight)
    json.dumps(audit, allow_nan=False)


def test_fit_is_label_blind_and_does_not_read_data_length():
    data, metadata = _fixture()
    class TrainingInputsOnly:
        environment = data.environment
        weight = data.weight
        @property
        def target(self):
            raise AssertionError("Training frequencies cannot read labels")
        def __len__(self):
            raise AssertionError("Calling data length could inspect CachedSplit targets")
    weights, audit = fit_categorical_balance(TrainingInputsOnly(), metadata)
    changed = deepcopy(data)
    changed.target = 1 - changed.target
    other, other_audit = fit_categorical_balance(changed, metadata)
    np.testing.assert_array_equal(weights, other)
    assert audit == other_audit and audit["uses_targets"] is False
    assert not audit["uses_validation"] and not audit["uses_test"]


def test_presence_repeats_once_and_is_not_patch_area_weighting():
    data, metadata = _fixture()
    original, original_audit = fit_categorical_balance(data, metadata)
    changed = deepcopy(data)
    # Repeat the same rare class across eight positions. Presence is unchanged.
    changed.environment[0, 0] = 0
    changed.environment[0, 1] = 1
    changed.environment[0, 0, 1, 1] = 1
    changed.environment[0, 1, 1, 1] = 0
    repeated, repeated_audit = fit_categorical_balance(changed, metadata)
    np.testing.assert_array_equal(original, repeated)
    assert original_audit == repeated_audit


def test_floor_cap_normalization_and_disabled_weights():
    data, metadata = _fixture()
    effective, audit = fit_categorical_balance(data, metadata, min_frequency=.25, max_factor=1.5)
    assert audit["sources"][0]["classes"][1]["rarity_factor"] == 1.5
    factors = effective / data.weight
    assert factors.min() >= 1 / 1.5 - 1e-15 and factors.max() <= 1.5 + 1e-15
    assert np.dot(data.weight, factors) / data.weight.sum() == pytest.approx(1.)
    disabled, disabled_audit = fit_categorical_balance(data, metadata, mode="none")
    np.testing.assert_array_equal(disabled, data.weight)
    assert disabled is not data.weight
    assert disabled_audit["normalizer"] == disabled_audit["factor_min"] == disabled_audit["factor_max"] == 1
    assert disabled_audit["population_weights_sha256"] == disabled_audit["optimization_weights_sha256"]
    uncapped_floor, floor_audit = fit_categorical_balance(data, metadata, min_frequency=.5, max_factor=10)
    assert floor_audit["sources"][0]["classes"][1]["rarity_factor"] == pytest.approx(np.sqrt(2))
    assert uncapped_floor.sum() == pytest.approx(data.weight.sum())


def test_no_categorical_source_returns_original_weights():
    data = SimpleNamespace(environment=np.ones((3, 1, 3, 3), dtype=np.float32),
                           weight=np.array([1., 2., 100.]))
    output, audit = fit_categorical_balance(data, {"channels": ["continuous"]})
    np.testing.assert_array_equal(output, data.weight)
    assert audit["sources"] == [] and audit["categorical_source_count"] == 0
    assert audit["normalizer"] == audit["factor_min"] == audit["factor_max"] == 1


def test_group_metrics_use_original_weights_and_hand_computed_brier():
    data, metadata = _fixture()
    predictions = np.array([.2, .8, .3, .4])
    report = categorical_group_metrics(data, predictions, metadata, chunk_size=1)
    biome, cover = report["sources"]
    assert biome["classes"][0]["brier"] == pytest.approx(2.9 / 8)
    assert biome["classes"][1]["brier"] == pytest.approx(.64)
    assert biome["classes"][2]["sample_count"] == 0 and biome["classes"][2]["brier"] is None
    assert cover["classes"][0]["brier"] == pytest.approx(2.26 / 4)
    assert cover["classes"][0]["weighted_prevalence"] == pytest.approx(3 / 4)
    assert cover["classes"][1]["brier"] == pytest.approx(.16)
    assert report["groups_overlap"] and not report["group_counts_are_additive"]
    assert sum(entry["sample_count"] for entry in biome["classes"]) == 5 > report["row_count"]
    before = deepcopy(report)
    fit_categorical_balance(data, metadata)
    assert categorical_group_metrics(data, predictions, metadata, chunk_size=1) == before
    json.dumps(report, allow_nan=False)


def test_group_metrics_selected_chunks_and_empty_cohort():
    data, metadata = _fixture()
    # This excluded row is intentionally invalid, demonstrating that selected
    # metrics inspect only the requested raw patches, not a complete copy.
    data.environment[1] = np.nan
    predictions = np.array([.2, .8, .3, .4])
    selected = categorical_group_metrics(data, predictions, metadata, indices=np.array([2, 0]), chunk_size=1)
    assert selected["row_count"] == 2 and selected["source_row_count"] == 4
    assert selected["sources"][0]["classes"][0]["brier"] == pytest.approx(1.62 / 3)
    empty = categorical_group_metrics(data, predictions, metadata, indices=np.array([], dtype=np.int64))
    assert empty["row_count"] == empty["represented_population_weight"] == 0
    for source in empty["sources"]:
        assert all(entry["sample_count"] == 0 and entry["brier"] is None for entry in source["classes"])
    json.dumps(empty, allow_nan=False)


@pytest.mark.parametrize("indices", [[0, 0], [-1], [4], [0.5], [[0]], [True]])
def test_group_metrics_reject_invalid_cohort_indices(indices):
    data, metadata = _fixture()
    with pytest.raises(ValueError, match="indices"):
        categorical_group_metrics(data, np.full(4, .5), metadata, indices=np.asarray(indices))


@pytest.mark.parametrize("option", [
    {"mode": "unsupported"}, {"mode": None}, {"min_frequency": 0}, {"min_frequency": 1.1},
    {"min_frequency": True}, {"min_frequency": "0.1"}, {"min_frequency": float("nan")},
    {"max_factor": .5}, {"max_factor": float("inf")}, {"max_factor": "10"},
    {"chunk_size": 0}, {"chunk_size": True}, {"chunk_size": 1.5},
])
def test_invalid_settings_are_rejected(option):
    with pytest.raises(ValueError):
        validate_categorical_balance_settings(**option)


@pytest.mark.parametrize("failure", ["normalized_one_hot", "missing_class", "two_active", "invalid_weight"])
def test_fit_refuses_invalid_raw_inputs(failure):
    data, metadata = _fixture()
    if failure == "normalized_one_hot":
        data.environment[0, 0, 0, 0] = -.5
    elif failure == "missing_class":
        data.environment[0, :3, 0, 0] = 0
    elif failure == "two_active":
        data.environment[0, 0, 0, 0] = 1
    else:
        data.weight[0] = np.nan
    with pytest.raises(ValueError):
        fit_categorical_balance(data, metadata)


def test_shared_cli_options_and_settings_defaults():
    parser = add_categorical_balance_arguments(argparse.ArgumentParser())
    assert categorical_balance_settings(parser.parse_args([])) == validate_categorical_balance_settings()
    assert categorical_balance_settings(SimpleNamespace()) == validate_categorical_balance_settings()
    settings = categorical_balance_settings(parser.parse_args([
        "--categorical-balance", "none", "--categorical-balance-min-frequency", ".02",
        "--categorical-balance-max-factor", "3",
    ]))
    assert settings == dict(mode="none", min_frequency=.02, max_factor=3., chunk_size=512)
