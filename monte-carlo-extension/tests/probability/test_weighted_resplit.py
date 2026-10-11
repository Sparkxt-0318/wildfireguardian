"""Integration checks for exact row preservation and fixed-test weighted splitting."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from wildfire.prepare import categorical_presence
from wildfire.prepare import resplit_existing_cache


def _hashes(path):
    return {name: hashlib.sha256((path / name).read_bytes()).hexdigest()
            for name in ("metadata.json", "train.npz", "validation.npz", "test.npz")}


def _arrays(event_index, count, category, *, start=0):
    # Category 8 appears at a corner only: full-patch coverage must detect it.
    environment = np.zeros((count, 3, 3, 3), dtype=np.float32)
    environment[:, 0] = np.arange(count, dtype=np.float32)[:, None, None] + start
    environment[:, 1] = 1
    if category == 8:
        environment[:, 1, 0, 0] = 0
        environment[:, 2, 0, 0] = 1
    burned = np.zeros((count, 1, 3, 3), dtype=np.float32)
    burned[:, 0, 0, 1] = 1
    return dict(environment=environment, burned=burned,
                target=(np.arange(count) % 2).astype(np.float32),
                weight=np.where(np.arange(count) % 2, 1., np.arange(count) + 2.).astype(np.float64),
                event_index=np.full(count, event_index, dtype=np.int64),
                time_utc=1800000000 + np.arange(count, dtype=np.int64) * 3600,
                row=np.full(count, event_index + 3, dtype=np.int32),
                col=np.arange(count, dtype=np.int32) + start)


@pytest.fixture
def prepared(tmp_path):
    source = tmp_path / "original"
    source.mkdir()
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "evidence.txt").write_text("immutable raw source")
    metadata = dict(data_root=str(raw), kernel_size=3, dt_hours=1., seed=7,
                    channels=["temperature", "biome=4", "biome=8"],
                    source_channels=["temperature", "biome"], categorical_encoding="one_hot",
                    channel_info=[dict(name="temperature", categorical=False, encoding="continuous", source_channel="temperature"),
                                  dict(name="biome=4", categorical=True, encoding="one_hot", source_channel="biome", class_code=4),
                                  dict(name="biome=8", categorical=True, encoding="one_hot", source_channel="biome", class_code=8)],
                    categorical_classes={"biome": [4, 8]}, channel_groups={"temperature": [0], "biome": [1, 2]},
                    event_ids=["trainfire", "valfire", "testfire", "emptyfire"],
                    splits=dict(trainfire="train", valfire="validation", testfire="test", emptyfire="train"),
                    per_event=[dict(id=name, split=split, country="KR", accepted_samples=count)
                               for name, split, count in (("trainfire", "train", 16), ("valfire", "validation", 16),
                                                          ("testfire", "test", 6), ("emptyfire", "train", 0))],
                    sampling=dict(all_positives=True, contact_limit=5000, no_contact_limit=2000),
                    source_files=[dict(path="evidence.txt", bytes=(raw / "evidence.txt").stat().st_size,
                                       sha256=hashlib.sha256((raw / "evidence.txt").read_bytes()).hexdigest())])
    arrays = {"train": _arrays(0, 16, 4), "validation": _arrays(1, 16, 8, start=100),
              "test": _arrays(2, 6, 4, start=200)}
    for name, values in arrays.items():
        np.savez_compressed(source / f"{name}.npz", **values)
    (source / "metadata.json").write_text(json.dumps(metadata))
    return source, arrays, metadata


def _rows(arrays):
    return {tuple(int(arrays[key][index]) for key in ("event_index", "time_utc", "row", "col")):
            {key: arrays[key][index] for key in arrays}
            for index in range(len(arrays["target"]))}


def test_resplit_keeps_every_row_and_weight_and_test_bytes(prepared, tmp_path):
    source, old, original_meta = prepared
    original_hashes = _hashes(source)
    output = tmp_path / "balanced"
    record = resplit_existing_cache(source, output, validation_fraction=.25, seed=11)
    assert _hashes(source) == original_hashes
    assert (output / "test.npz").read_bytes() == (source / "test.npz").read_bytes()
    assert record["test_archive_preserved_byte_for_byte"]
    assert record["training_started"] is False and record["fitted_state_reused"] is False
    assert record["source_files_verified"] == 1
    metadata = json.loads((output / "metadata.json").read_text())
    assert metadata["split_unit"] == "cell_hour"
    assert metadata["original_splits"] == original_meta["splits"]
    assert metadata["splits"]["testfire"] == ["test"]
    assert metadata["splits"]["emptyfire"] == []
    assert metadata["split_summary"]["test"]["frequencies_by_support"]["native_3x3"]["samples"] == 6
    expected = {**_rows(old["train"]), **_rows(old["validation"])}
    obtained = {}
    for name in ("train", "validation"):
        with np.load(output / f"{name}.npz", allow_pickle=False) as archive:
            values = {key: archive[key] for key in archive.files}
        rows = _rows(values)
        assert not set(rows) & set(obtained)
        obtained.update(rows)
        assert metadata["split_summary"][name]["samples"] == len(rows)
        assert metadata["split_summary"][name]["represented_population_weight"] == pytest.approx(values["weight"].sum())
        for index in np.unique(values["event_index"]):
            assert name in metadata["splits"][metadata["event_ids"][int(index)]]
    assert obtained.keys() == expected.keys()
    for identity in expected:
        for field in expected[identity]:
            np.testing.assert_array_equal(obtained[identity][field], expected[identity][field])
    assert record["categorical_coverage"]["training_present"] == ["biome=4", "biome=8"]
    assert record["categorical_coverage"]["validation_covered_by_training"]
    assert record["categorical_coverage"]["test_covered_by_training"]
    assert not list(tmp_path.glob(".weighted-resplit-*"))


def test_full_patch_presence_includes_class_absent_at_center(prepared):
    _, arrays, metadata = prepared
    presence = categorical_presence(arrays["validation"]["environment"], metadata)
    assert presence.all()  # Classes 4 and 8 both occur, although center is class 4.


def test_resplit_assignment_is_deterministic_without_reusing_fit(prepared, tmp_path):
    source, _, _ = prepared
    (source / "checkpoint.pt").write_bytes(b"irrelevant fitted artifact")
    first, second = tmp_path / "first", tmp_path / "second"
    resplit_existing_cache(source, first, seed=41)
    resplit_existing_cache(source, second, seed=41)
    for name in ("train.npz", "validation.npz", "test.npz"):
        with np.load(first / name) as left, np.load(second / name) as right:
            for key in left.files:
                np.testing.assert_array_equal(left[key], right[key])
    assert not (first / "checkpoint.pt").exists()


def test_changed_test_labels_do_not_change_training_assignment(prepared, tmp_path):
    source, arrays, _ = prepared
    first = tmp_path / "first"
    resplit_existing_cache(source, first, seed=7)
    changed = deepcopy(arrays["test"])
    changed["target"] = 1 - changed["target"]
    np.savez_compressed(source / "test.npz", **changed)
    second = tmp_path / "second"
    resplit_existing_cache(source, second, seed=7)
    for name in ("train.npz", "validation.npz"):
        with np.load(first / name) as left, np.load(second / name) as right:
            for key in left.files:
                np.testing.assert_array_equal(left[key], right[key])
    assert (second / "test.npz").read_bytes() == (source / "test.npz").read_bytes()


@pytest.mark.parametrize("failure", ["duplicate", "bad_source_hash", "bad_one_hot", "test_category_missing"])
def test_invalid_source_refuses_atomic_promotion(prepared, tmp_path, failure):
    source, arrays, metadata = prepared
    if failure == "duplicate":
        values = deepcopy(arrays["validation"])
        for key in ("event_index", "time_utc", "row", "col"):
            values[key][0] = arrays["train"][key][0]
        metadata["split_unit"] = "cell_hour"
        metadata["original_splits"] = deepcopy(metadata["splits"])
        metadata["splits"] = {key: [value] for key, value in metadata["splits"].items()}
        metadata["splits"]["trainfire"] = ["train", "validation"]
        np.savez_compressed(source / "validation.npz", **values)
    elif failure == "bad_source_hash":
        metadata["source_files"][0]["sha256"] = "0" * 64
    elif failure == "bad_one_hot":
        values = deepcopy(arrays["validation"])
        values["environment"][0, 2, 0, 0] = .5
        np.savez_compressed(source / "validation.npz", **values)
    else:
        values = deepcopy(arrays["validation"])
        values["environment"][:, 1] = 1
        values["environment"][:, 2] = 0
        np.savez_compressed(source / "validation.npz", **values)
        test_values = deepcopy(arrays["test"])
        test_values["environment"][:, 1] = 0
        test_values["environment"][:, 2] = 1
        np.savez_compressed(source / "test.npz", **test_values)
    (source / "metadata.json").write_text(json.dumps(metadata))
    hashes = _hashes(source)
    output = tmp_path / "rejected"
    with pytest.raises(ValueError):
        resplit_existing_cache(source, output)
    assert not output.exists()
    assert _hashes(source) == hashes
    assert not list(tmp_path.glob(".weighted-resplit-*"))


def test_nonempty_output_and_overlapping_paths_are_refused(prepared, tmp_path):
    source, _, _ = prepared
    output = tmp_path / "occupied"
    output.mkdir()
    (output / "precious").write_text("keep")
    with pytest.raises(FileExistsError):
        resplit_existing_cache(source, output)
    assert (output / "precious").read_text() == "keep"
    for overlapping in (source, source / "nested", source.parent):
        with pytest.raises(ValueError, match="nonoverlapping"):
            resplit_existing_cache(source, overlapping)


def test_loader_accepts_explicit_event_memberships(prepared, tmp_path):
    from wildfire.cache import load_split
    source, _, _ = prepared
    output = tmp_path / "balanced"
    resplit_existing_cache(source, output)
    metadata = json.loads((output / "metadata.json").read_text())
    for name in ("train", "validation", "test"):
        data = load_split(output, name, metadata)
        assert len(data) == metadata["split_summary"][name]["samples"]


def test_archive_fields_are_streamed_instead_of_loading_full_npz(prepared, tmp_path, monkeypatch):
    import wildfire.prepare as utility
    source, _, _ = prepared
    original_load = utility.np.load
    def mapped_npy_only(path, *args, **kwargs):
        assert Path(path).suffix == ".npy", "The resplit must not materialize a complete NPZ split"
        assert kwargs.get("mmap_mode") == "r"
        return original_load(path, *args, **kwargs)
    monkeypatch.setattr(utility.np, "load", mapped_npy_only)
    utility.resplit_existing_cache(source, tmp_path / "streamed")


def test_atomic_write_failure_preserves_source_and_cleans_staging(prepared, tmp_path, monkeypatch):
    import wildfire.prepare as utility
    source, _, _ = prepared
    before = _hashes(source)
    output = tmp_path / "empty"
    output.mkdir()
    def fail(*args, **kwargs):
        raise OSError("Injected archive write failure")
    monkeypatch.setattr(utility, "_write_partition_field", fail)
    with pytest.raises(OSError, match="Injected"):
        utility.resplit_existing_cache(source, output)
    assert output.is_dir() and not any(output.iterdir())
    assert _hashes(source) == before
    assert not list(tmp_path.glob(".weighted-resplit-*"))


def test_native_coverage_uses_cropped_inputs_and_preserves_fixed_test(prepared, tmp_path):
    source, old, metadata = prepared
    metadata["kernel_size"] = 9
    for name in ("train", "validation", "test"):
        values = deepcopy(old[name])
        count = len(values["target"])
        environment = np.zeros((count, 3, 9, 9), dtype=np.float32)
        environment[:, 1] = 1
        if name == "validation":
            environment[:, 1, 0, 0] = 0
            environment[:, 2, 0, 0] = 1
        elif name == "test":
            # Test class 8 is inside the 3x3 crop, while development class 8 is
            # only outside it. Full 9x9 presence would incorrectly pass this.
            environment[:, 1, 4, 4] = 0
            environment[:, 2, 4, 4] = 1
        burned = np.zeros((count, 1, 9, 9), dtype=np.float32)
        burned[:, 0, 3, 4] = 1
        values.update(environment=environment, burned=burned)
        np.savez_compressed(source / f"{name}.npz", **values)
    (source / "metadata.json").write_text(json.dumps(metadata))
    before = _hashes(source)
    output = tmp_path / "native_rejected"
    with pytest.raises(ValueError, match="Native 3x3"):
        resplit_existing_cache(source, output)
    assert not output.exists() and _hashes(source) == before


@pytest.mark.parametrize("failure", [False, True])
def test_all_mappings_close_before_windows_style_file_cleanup(prepared, tmp_path, monkeypatch, failure):
    import wildfire.prepare as utility
    source, _, _ = prepared
    tracked = []
    original_track = utility._MemoryMaps.track
    original_unlink = Path.unlink
    original_rmtree = utility.shutil.rmtree
    def track(self, array):
        tracked.append(array)
        return original_track(self, array)
    def unlink(path, *args, **kwargs):
        matching = [array for array in tracked if Path(array.filename) == path]
        assert all(array._mmap.closed for array in matching), "Windows cannot unlink an open memory map"
        return original_unlink(path, *args, **kwargs)
    def rmtree(path, *args, **kwargs):
        assert all(array._mmap.closed for array in tracked), "Windows cannot remove a directory with mapped files"
        return original_rmtree(path, *args, **kwargs)
    monkeypatch.setattr(utility._MemoryMaps, "track", track)
    monkeypatch.setattr(Path, "unlink", unlink)
    monkeypatch.setattr(utility.shutil, "rmtree", rmtree)
    output = tmp_path / "closed_mappings"
    if failure:
        def fail(*args, **kwargs):
            raise OSError("Injected Windows cleanup check")
        monkeypatch.setattr(utility, "_write_partition_field", fail)
        with pytest.raises(OSError, match="Injected Windows"):
            utility.resplit_existing_cache(source, output)
        assert not output.exists()
    else:
        utility.resplit_existing_cache(source, output)
        assert output.is_dir()
    assert tracked and all(array._mmap.closed for array in tracked)
    assert not list(tmp_path.glob(".weighted-resplit-*"))


@pytest.mark.parametrize("invalid", ["missing_original", "test_remapped", "ambiguous_unit", "membership_not_list"])
def test_malformed_row_source_metadata_refused_before_staging(prepared, tmp_path, invalid):
    source, _, metadata = prepared
    metadata["split_unit"] = "cell_hour"
    metadata["original_splits"] = deepcopy(metadata["splits"])
    metadata["splits"] = {key: [value] for key, value in metadata["splits"].items()}
    if invalid == "missing_original":
        metadata.pop("original_splits")
    elif invalid == "test_remapped":
        metadata["original_splits"]["testfire"] = "train"
    elif invalid == "ambiguous_unit":
        metadata["split_unit"] = "stratified"
    else:
        metadata["splits"]["trainfire"] = "train"
    (source / "metadata.json").write_text(json.dumps(metadata))
    before = _hashes(source)
    output = tmp_path / "malformed_rejected"
    with pytest.raises(ValueError):
        resplit_existing_cache(source, output)
    assert not output.exists() and _hashes(source) == before
    assert not list(tmp_path.glob(".weighted-resplit-*"))
