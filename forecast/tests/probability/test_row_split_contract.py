"""Explicit row-split authority, identity separation, and trained-run checks."""

import json

import numpy as np
import pytest

from wildfire.cache import CachedSplit
from wildfire.cache import cell_hour_identities
from wildfire.cache import load_split
from wildfire.cache import validate_partition_disjointness
from wildfire.cache import validate_split_metadata
from wildfire.train import parser
from wildfire.train import train
from wildfire.train import verify_run


def _metadata():
    return {
        "channels": ["weather.temperature_2m"], "kernel_size": 3,
        "dt_hours": 1.0, "eligibility": "at_least_one_burned_neighbor",
        "event_ids": ["development_fire", "empty_fire", "test_fire"],
        "split_unit": "cell_hour",
        "splits": {"development_fire": ["train", "validation"],
                   "empty_fire": [], "test_fire": ["test"]},
        "original_splits": {"development_fire": "train", "empty_fire": "validation",
                            "test_fire": "test"},
        "source_files": [],
    }


def _data(event_index, times):
    times = np.asarray(times, dtype=np.int64)
    n = len(times)
    burned = np.zeros((n, 1, 3, 3), dtype=np.float32)
    burned[:, 0, 0, 0] = 1
    return CachedSplit(
        environment=np.arange(n * 9, dtype=np.float32).reshape(n, 1, 3, 3),
        burned=burned, target=np.resize(np.array([1, 0], dtype=np.float32), n),
        weight=np.resize(np.array([1, 3], dtype=np.float64), n),
        event_index=np.full(n, event_index, dtype=np.int64), time_utc=times,
        row=np.ones(n, dtype=np.int32), col=np.ones(n, dtype=np.int32),
    )


def _save(directory, name, data):
    np.savez_compressed(directory / f"{name}.npz", **vars(data))


def test_row_metadata_declares_actual_memberships_and_keeps_empty_events():
    result = validate_split_metadata(_metadata(), require_all_partitions=True)
    assert result["development_fire"] == frozenset(("train", "validation"))
    assert result["empty_fire"] == frozenset()
    assert result["test_fire"] == frozenset(("test",))


@pytest.mark.parametrize("split_unit", [None, "whole_fire", "fire"])
def test_legacy_fire_metadata_keeps_single_assignment_authority(split_unit):
    metadata = _metadata()
    metadata["splits"] = metadata.pop("original_splits")
    if split_unit is None:
        metadata.pop("split_unit")
    else:
        metadata["split_unit"] = split_unit
    memberships = validate_split_metadata(metadata, require_all_partitions=True)
    assert memberships["development_fire"] == frozenset(("train",))
    metadata["splits"]["development_fire"] = ["train", "validation"]
    with pytest.raises(ValueError, match="Whole-fire"):
        validate_split_metadata(metadata)


@pytest.mark.parametrize("change", [
    lambda m: m.update(split_unit="unknown"),
    lambda m: m.pop("original_splits"),
    lambda m: m["event_ids"].append("development_fire"),
    lambda m: m["splits"].pop("empty_fire"),
    lambda m: m["original_splits"].pop("empty_fire"),
    lambda m: m["original_splits"].update(empty_fire=["validation"]),
    lambda m: m["splits"].update(development_fire="train"),
    lambda m: m["splits"].update(development_fire=["train", "train"]),
    lambda m: m["splits"].update(development_fire=["unknown"]),
    lambda m: m["splits"].update(test_fire=["test", "validation"]),
    lambda m: m["splits"].update(test_fire=["validation"]),
    lambda m: m["splits"].update(test_fire=[]),
    lambda m: m["splits"].update(development_fire=["test"]),
])
def test_invalid_row_metadata_is_rejected(change):
    metadata = _metadata()
    change(metadata)
    with pytest.raises(ValueError):
        validate_split_metadata(metadata)


def test_loading_allows_declared_shared_fire_but_rejects_wrong_partition(tmp_path):
    metadata = _metadata()
    _save(tmp_path, "validation", _data(0, [7200, 10800]))
    validation = load_split(tmp_path, "validation", metadata)
    assert set(validation.event_index) == {0}
    _save(tmp_path, "train", _data(2, [0, 3600]))
    with pytest.raises(ValueError, match="wrong cache split"):
        load_split(tmp_path, "train", metadata)


def test_loading_rejects_duplicate_cell_hour_identity(tmp_path):
    _save(tmp_path, "train", _data(0, [0, 0]))
    with pytest.raises(ValueError, match="Duplicate cell-hour identities"):
        load_split(tmp_path, "train", _metadata())


def test_partition_check_uses_all_four_identity_coordinates():
    training = _data(0, [0, 3600])
    validation = _data(0, [7200, 10800])
    testing = _data(2, [0, 3600])
    report = validate_partition_disjointness(
        {"train": training, "validation": validation, "test": testing}, _metadata())
    assert report["disjoint_cell_hour_identities"]
    assert report["test_fires_disjoint_from_training_validation"]
    assert not report["disjoint_contributing_fire_sets"]
    # An equal event/time/row with a different column is a different cell-hour.
    moved = _data(0, [0, 3600])
    moved.col[:] = 2
    validate_partition_disjointness({"train": training, "validation": moved}, _metadata())
    # A single identical event/time/row/column is sufficient to reject the split.
    moved.col[0] = 1
    with pytest.raises(ValueError, match="Shared cell-hour identities"):
        validate_partition_disjointness({"train": training, "validation": moved}, _metadata())


def test_identity_only_verification_rejects_duplicates_and_wrong_test_fire():
    training = cell_hour_identities(_data(0, [0, 3600]))
    validation = cell_hour_identities(_data(0, [7200, 10800]))
    validate_partition_disjointness({"train": training, "validation": validation}, _metadata())
    duplicate = np.concatenate((training, training[:1]))
    with pytest.raises(ValueError, match="Duplicate cell-hour identities"):
        validate_partition_disjointness({"train": duplicate}, _metadata())
    with pytest.raises(ValueError, match="wrong cache split"):
        validate_partition_disjointness({"train": training, "test": validation}, _metadata())


def test_train_rejects_cross_partition_identity_before_fitting(tmp_path):
    directory = tmp_path / "prepared"
    directory.mkdir()
    (directory / "metadata.json").write_text(json.dumps(_metadata()))
    _save(directory, "train", _data(0, [0, 3600]))
    _save(directory, "validation", _data(0, [3600, 7200]))
    output = tmp_path / "fitted"
    arguments = parser().parse_args(["--data-dir", str(directory), "--output-dir", str(output)])
    with pytest.raises(ValueError, match="Shared cell-hour identities"):
        train(arguments)
    assert not output.exists()


def test_fresh_row_split_training_and_independent_verification(tmp_path):
    run = tmp_path / "row_run"
    directory = run / "prepared"
    directory.mkdir(parents=True)
    metadata = _metadata()
    metadata["data_root"] = str(tmp_path)
    (directory / "metadata.json").write_text(json.dumps(metadata))
    for name, data in (("train", _data(0, [0, 3600])),
                       ("validation", _data(0, [7200, 10800])),
                       ("test", _data(2, [0, 3600]))):
        _save(directory, name, data)
    arguments = parser().parse_args([
        "--data-dir", str(directory), "--output-dir", str(run / "fitted"),
        "--epochs", "1", "--batch-size", "2", "--hidden-channels", "2", "--threads", "1",
    ])
    metrics = train(arguments)
    assert metrics["contract"]["split_unit"] == "cell_hour"
    assert metrics["contract"]["original_splits"] == metadata["original_splits"]
    assert metrics["selection"]["test_used_for_selection"] is False
    report = verify_run(run)
    assert report["split_unit"] == "cell_hour"
    assert report["disjoint_cell_hour_identities"]
    assert report["test_fires_disjoint_from_training_validation"]
    assert not report["disjoint_contributing_fire_sets"]
    assert report["training_only_normalization_reproduced_exactly"]
