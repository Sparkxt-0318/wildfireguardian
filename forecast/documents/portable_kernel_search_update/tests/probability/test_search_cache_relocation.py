"""Relocation preserves frozen samples while rebinding verified source paths.

All caches, source inputs, output protocols, and failure cases are private test
fixtures. These tests never launch training or alter a production run/cache.
"""

from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pytest


FILES = ("metadata.json", "train.npz", "validation.npz", "test.npz")
SPLITS = ("train", "validation", "test")


def _hashes(directory):
    return {name: sha256((directory / name).read_bytes()).hexdigest() for name in FILES}


def _payload(directory):
    return {name: (directory / name).read_bytes() for name in FILES}


def _utility():
    from wildfire_burned_area_hourly.probability_model import relocate_search_cache

    return relocate_search_cache


@pytest.fixture
def relocation_fixture(tmp_path):
    source = tmp_path / "original_cache"
    source.mkdir()
    new_root = tmp_path / "linux_inputs"
    (new_root / "weather").mkdir(parents=True)
    (new_root / "biome_classes.json").write_bytes(b'{"biomes": ["forest", "grass"]}\n')
    (new_root / "weather" / "source.bin").write_bytes(b"Identical copied source data.\n")
    metadata = {
        "dt_hours": 1.0,
        "kernel_size": 9,
        "channels": ["weather.temperature_2m", "terrain.slope_degrees"],
        "event_ids": ["train_event", "validation_event", "test_event"],
        "splits": {
            "train_event": "train", "validation_event": "validation", "test_event": "test",
        },
        "split_summary": {split: {"samples": 3} for split in SPLITS},
        # The machine that prepared the cache is intentionally inaccessible.
        "data_root": "/Users/original-machine/WildfireGuardian/environmental_data",
        "source_files": [
            {"path": name, "sha256": sha256((new_root / name).read_bytes()).hexdigest()}
            for name in ("biome_classes.json", "weather/source.bin")
        ],
        "seed": 7,
        "created_at_utc": "2026-10-07T09:32:54.772080+00:00",
        "sampling": {"contact_negatives_per_event": 5000, "no_contact_negatives_per_event": 2000},
    }
    (source / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    for event_index, split in enumerate(SPLITS):
        burned = np.zeros((3, 1, 9, 9), dtype=np.float32)
        burned[:2, 0, 3, 4] = 1
        np.savez(
            source / f"{split}.npz",
            environment=np.full((3, 2, 9, 9), event_index + 0.5, dtype=np.float32),
            burned=burned,
            target=np.array([1, 0, 0], dtype=np.float32),
            weight=np.array([1, 4, 1], dtype=np.float64),
            event_index=np.full(3, event_index, dtype=np.int64),
            time_utc=np.full(3, 3600, dtype=np.int64),
            row=np.arange(3, dtype=np.int64),
            col=np.full(3, 7, dtype=np.int64),
        )
    return source, tmp_path / "relocated_cache", new_root, metadata


def _relocate(fixture, *, expected_hashes=None):
    source, destination, data_root, _ = fixture
    return _utility().relocate_cache(
        source, destination, data_root,
        expected_hashes=_hashes(source) if expected_hashes is None else expected_hashes,
    )


def test_relocation_changes_only_data_root_and_preserves_every_sample_byte(relocation_fixture):
    source, destination, new_root, original_metadata = relocation_fixture
    before = _payload(source)
    result = _relocate(relocation_fixture)
    expected_metadata = {**original_metadata, "data_root": str(new_root.resolve())}
    assert json.loads((destination / "metadata.json").read_text()) == expected_metadata
    assert _payload(source) == before
    for split in SPLITS:
        assert (destination / f"{split}.npz").read_bytes() == before[f"{split}.npz"]
    assert result["status"] == "relocated"
    assert result["training_started"] is False
    assert result["verified_source_files"] == 2
    assert result["source_cache"] == str(source.resolve())
    assert result["destination_cache"] == str(destination.resolve())
    assert result["original_data_root"] == original_metadata["data_root"]
    assert result["data_root"] == str(new_root.resolve())
    assert result["original_cache_sha256"] == _hashes(source)
    assert result["relocated_cache_sha256"] == _hashes(destination)
    assert result["original_cache_sha256"]["metadata.json"] != result["relocated_cache_sha256"]["metadata.json"]
    assert json.loads((destination / "relocation.json").read_text()) == result


def test_original_data_root_is_not_required_to_exist(relocation_fixture):
    _, destination, _, metadata = relocation_fixture
    assert not Path(metadata["data_root"]).exists()
    _relocate(relocation_fixture)
    assert all((destination / name).is_file() for name in FILES)


def test_relocation_reuses_only_identical_existing_destination(relocation_fixture):
    source, destination, _, _ = relocation_fixture
    first = _relocate(relocation_fixture)
    before = {path.name: path.read_bytes() for path in destination.iterdir()}
    second = _relocate(relocation_fixture)
    assert second["status"] == "already_present"
    assert second["training_started"] is False
    assert second["original_cache_sha256"] == _hashes(source)
    assert second["relocated_cache_sha256"] == _hashes(destination)
    assert second["verified_source_files"] == first["verified_source_files"]
    assert {path.name: path.read_bytes() for path in destination.iterdir()} == before


def test_empty_destination_accepts_atomic_relocation(relocation_fixture):
    _, destination, _, _ = relocation_fixture
    destination.mkdir()
    assert _relocate(relocation_fixture)["status"] == "relocated"


@pytest.mark.parametrize("change", ["metadata", "train", "validation", "test"])
def test_changed_destination_is_preserved_and_refused(relocation_fixture, change):
    _, destination, _, _ = relocation_fixture
    _relocate(relocation_fixture)
    if change == "metadata":
        metadata = json.loads((destination / "metadata.json").read_text())
        metadata["seed"] = 100
        (destination / "metadata.json").write_text(json.dumps(metadata))
    else:
        path = destination / f"{change}.npz"
        path.write_bytes(path.read_bytes() + b"altered destination")
    before = {path.name: path.read_bytes() for path in destination.iterdir()}
    with pytest.raises((ValueError, FileExistsError, RuntimeError)):
        _relocate(relocation_fixture)
    assert {path.name: path.read_bytes() for path in destination.iterdir()} == before


def test_nonempty_partial_destination_is_preserved(relocation_fixture):
    source, destination, _, _ = relocation_fixture
    destination.mkdir()
    (destination / "metadata.json").write_bytes((source / "metadata.json").read_bytes())
    (destination / "note.txt").write_text("Keep this incomplete destination intact.")
    before = {path.name: path.read_bytes() for path in destination.iterdir()}
    with pytest.raises((ValueError, FileExistsError, RuntimeError)):
        _relocate(relocation_fixture)
    assert {path.name: path.read_bytes() for path in destination.iterdir()} == before


@pytest.mark.parametrize("overlap", ["same", "child", "parent"])
def test_overlapping_cache_paths_are_refused_without_changes(relocation_fixture, overlap):
    source, _, new_root, _ = relocation_fixture
    destination = {"same": source, "child": source / "clone", "parent": source.parent}[overlap]
    before = _payload(source)
    with pytest.raises((ValueError, FileExistsError, RuntimeError)):
        _utility().relocate_cache(source, destination, new_root, expected_hashes=_hashes(source))
    assert _payload(source) == before
    assert not (source / "clone").exists()


def test_symlink_alias_cannot_bypass_overlap_check(relocation_fixture, tmp_path):
    source, _, data_root, _ = relocation_fixture
    alias = tmp_path / "same-cache-symlink"
    alias.symlink_to(source, target_is_directory=True)
    before = _payload(source)
    with pytest.raises((ValueError, FileExistsError, RuntimeError)):
        _utility().relocate_cache(source, alias, data_root, expected_hashes=_hashes(source))
    assert _payload(source) == before


@pytest.mark.parametrize("name", FILES)
def test_modified_original_cache_fails_hash_binding(relocation_fixture, name):
    source, destination, _, _ = relocation_fixture
    expected = _hashes(source)
    path = source / name
    path.write_bytes(path.read_bytes() + b"changed original payload")
    changed = path.read_bytes()
    with pytest.raises((ValueError, RuntimeError)):
        _relocate(relocation_fixture, expected_hashes=expected)
    assert path.read_bytes() == changed
    assert not destination.exists()


@pytest.mark.parametrize("name", FILES)
def test_missing_original_cache_file_is_reported_without_destination(relocation_fixture, name):
    source, destination, _, _ = relocation_fixture
    expected = _hashes(source)
    (source / name).unlink()
    with pytest.raises((ValueError, FileNotFoundError, RuntimeError)):
        _relocate(relocation_fixture, expected_hashes=expected)
    assert not destination.exists()


def test_default_hash_binding_does_not_accept_arbitrary_fixture(relocation_fixture):
    source, destination, new_root, _ = relocation_fixture
    with pytest.raises((ValueError, RuntimeError)):
        _utility().relocate_cache(source, destination, new_root)
    assert not destination.exists()


@pytest.mark.parametrize("failure", ["missing", "changed", "root_missing"])
def test_source_inputs_must_match_original_manifest_before_relocation(relocation_fixture, failure):
    source, destination, new_root, _ = relocation_fixture
    before = _payload(source)
    if failure == "missing":
        (new_root / "biome_classes.json").unlink()
    elif failure == "changed":
        (new_root / "weather" / "source.bin").write_bytes(b"Different environmental observations")
    else:
        new_root = new_root / "nonexistent"
    with pytest.raises((ValueError, FileNotFoundError, RuntimeError)):
        _utility().relocate_cache(source, destination, new_root, expected_hashes=_hashes(source))
    assert _payload(source) == before
    assert not destination.exists()


@pytest.mark.parametrize("invalid", [
    "empty_manifest", "duplicate", "absolute", "traversal", "backslash",
    "bad_digest", "missing_digest", "empty_path", "wrong_horizon", "wrong_kernel",
])
def test_invalid_source_metadata_is_rejected_before_writing(relocation_fixture, invalid):
    source, destination, _, metadata = relocation_fixture
    if invalid == "empty_manifest":
        metadata["source_files"] = []
    elif invalid == "duplicate":
        metadata["source_files"].append(dict(metadata["source_files"][0]))
    elif invalid in ("absolute", "traversal", "backslash", "empty_path"):
        metadata["source_files"][0]["path"] = {
            "absolute": "/biome_classes.json", "traversal": "../biome_classes.json",
            "backslash": "weather\\source.bin", "empty_path": "",
        }[invalid]
    elif invalid == "bad_digest":
        metadata["source_files"][0]["sha256"] = "not-a-sha256"
    elif invalid == "missing_digest":
        del metadata["source_files"][0]["sha256"]
    elif invalid == "wrong_horizon":
        metadata["dt_hours"] = 2.0
    else:
        metadata["kernel_size"] = 7
    (source / "metadata.json").write_text(json.dumps(metadata))
    before = _payload(source)
    with pytest.raises((ValueError, FileNotFoundError, RuntimeError)):
        _relocate(relocation_fixture)
    assert _payload(source) == before
    assert not destination.exists()


def test_symlink_source_escape_is_rejected_even_if_its_digest_matches(relocation_fixture, tmp_path):
    source, destination, new_root, metadata = relocation_fixture
    original_bytes = _payload(source)
    path = new_root / "biome_classes.json"
    outside = tmp_path / "outside.json"
    outside.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(outside)
    assert sha256(path.read_bytes()).hexdigest() == metadata["source_files"][0]["sha256"]
    with pytest.raises((ValueError, RuntimeError)):
        _relocate(relocation_fixture)
    assert not destination.exists()
    assert _payload(source) == original_bytes


@pytest.mark.parametrize("failure", ["record_write", "promotion"])
def test_atomic_failure_removes_staging_and_preserves_original(relocation_fixture, monkeypatch, failure):
    source, destination, _, _ = relocation_fixture
    utility = _utility()
    before_files = _payload(source)
    before_children = set(destination.parent.iterdir())
    if failure == "record_write":
        original = Path.write_text

        def fail_record(path, *args, **kwargs):
            if path.name == "relocation.json":
                raise OSError("Simulated record write failure")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_record)
    else:
        def fail_promotion(*args, **kwargs):
            raise OSError("Simulated atomic promotion failure")

        monkeypatch.setattr(utility.os, "replace", fail_promotion)
    with pytest.raises(OSError, match="Simulated"):
        _relocate(relocation_fixture)
    assert _payload(source) == before_files
    assert not destination.exists()
    assert set(destination.parent.iterdir()) == before_children


def test_runner_accepts_relocated_cache_and_freezes_new_root_and_hashes(relocation_fixture, tmp_path):
    from wildfire_burned_area_hourly.probability_model import kernel_search_multiscale as search

    _, destination, _, _ = relocation_fixture
    record = _relocate(relocation_fixture)
    output = tmp_path / "new_cuda_run"
    protocol = search.setup(output, destination, 512, 4096, 7)
    assert protocol["cache"] == str(destination.resolve())
    assert protocol["cache_sha256"] == record["relocated_cache_sha256"]
    assert protocol["verified_source_files"] == 2
    assert len(protocol["candidates"]) == 368
    assert json.loads((output / "protocol.json").read_text()) == protocol
    assert search.setup(output, destination, 512, 4096, 7) == protocol
    assert not list(output.rglob("*.pt"))


def test_runner_source_mismatch_does_not_write_protocol(relocation_fixture, tmp_path):
    from wildfire_burned_area_hourly.probability_model import kernel_search_multiscale as search

    _, destination, new_root, _ = relocation_fixture
    _relocate(relocation_fixture)
    (new_root / "biome_classes.json").write_bytes(b"Changed after relocation")
    output = tmp_path / "failed_run"
    with pytest.raises(ValueError, match="Source integrity mismatch"):
        search.setup(output, destination, 512, 4096, 7)
    assert not (output / "protocol.json").exists()
    assert not (output / "source_snapshot").exists()
    assert not list(output.rglob("*.pt"))
