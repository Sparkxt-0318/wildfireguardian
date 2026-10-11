"""Selective cache recovery must preserve cohorts and refuse inconsistent state.

Every test uses a private temporary cache/archive. No production cache or
training job is created, restored, read, or started by these regressions.
"""

from hashlib import sha256
import json
from pathlib import Path
import zipfile
import warnings
import struct

import numpy as np
import pytest


CACHE_FILES = ("metadata.json", "train.npz", "validation.npz", "test.npz")
ARCHIVE_PREFIX = (
    'WildfireGuardian/runs/20261007_1h_kernel_sweep/9x9/prepared_all/'
)


def _hashes(directory):
    return {name: sha256((directory / name).read_bytes()).hexdigest() for name in CACHE_FILES}


def _write_cache(directory, data_root):
    directory.mkdir()
    data_root.mkdir(exist_ok=True)
    source = data_root / "source.bin"
    source.write_bytes(b"Unmodified input provenance for the private test cache.\n")
    metadata = {
        "dt_hours": 1.0, "kernel_size": 9, "channels": ["fixture.a", "fixture.b"],
        "event_ids": ["train_event", "validation_event", "test_event"],
        "splits": {"train_event": "train", "validation_event": "validation", "test_event": "test"},
        "split_summary": {name: {"samples": 3} for name in ("train", "validation", "test")},
        "data_root": str(data_root.resolve()),
        "source_files": [{"path": "source.bin", "sha256": sha256(source.read_bytes()).hexdigest()}],
    }
    (directory / "metadata.json").write_text(json.dumps(metadata))
    for event_index, split in enumerate(("train", "validation", "test")):
        burned = np.zeros((3, 1, 9, 9), dtype=np.float32)
        burned[:2, 0, 3, 4] = 1.0
        np.savez(
            directory / f"{split}.npz",
            environment=np.full((3, 2, 9, 9), event_index + 0.5, dtype=np.float32),
            burned=burned, target=np.array([1.0, 0.0, 0.0], dtype=np.float32),
            weight=np.array([1.0, 4.0, 1.0], dtype=np.float64),
            event_index=np.full(3, event_index, dtype=np.int64),
            time_utc=np.full(3, 3600, dtype=np.int64),
            row=np.arange(3, dtype=np.int64), col=np.full(3, 7, dtype=np.int64),
        )
    return metadata


def _archive_cache(cache, archive, *, prefix=ARCHIVE_PREFIX, extras=None):
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name in CACHE_FILES:
            # writestr preserves the requested member path, including the
            # deliberately unsafe leading slash in the path regression.
            zipped.writestr(prefix + name, (cache / name).read_bytes())
        for name, payload in (extras or {}).items():
            zipped.writestr(name, payload)
    return archive


@pytest.fixture
def recovery_fixture(tmp_path):
    cache = tmp_path / "archived_cache"
    data_root = tmp_path / "inputs"
    metadata = _write_cache(cache, data_root)
    archive = _archive_cache(cache, tmp_path / "snapshot.zip")
    return cache, metadata, archive, tmp_path / "cache", tmp_path / "run"


def _recovery():
    import wildfire.cache as recover_search_cache

    return recover_search_cache


def _write_protocol(output, cache, hashes, *, source_hash=None):
    utility = _recovery()
    source = Path(utility.__file__).parent / "cache.py"
    output.mkdir(exist_ok=True)
    protocol = {
        "cache": str(cache.resolve()), "cache_sha256": dict(hashes),
        "training_source_sha256": {"cache.py": source_hash or sha256(source.read_bytes()).hexdigest()},
    }
    (output / "protocol.json").write_text(json.dumps(protocol))
    return protocol


def test_selective_recovery_preserves_exact_payload_and_ignores_unrelated_archive_files(recovery_fixture, tmp_path):
    source, metadata, archive, cache, output = recovery_fixture
    _archive_cache(source, archive, extras={"WildfireGuardian/unrelated_secret.txt": b"Not a cache member."})
    expected = _hashes(source)
    before = set(tmp_path.iterdir())
    record = _recovery().recover_cache(archive, cache, expected_hashes=expected, run_output=output)
    assert isinstance(record, dict)
    assert _hashes(cache) == expected
    assert json.loads((cache / "metadata.json").read_text()) == metadata
    assert not (tmp_path / "WildfireGuardian").exists()
    assert not (cache / "unrelated_secret.txt").exists()
    assert not output.exists()
    assert set(tmp_path.iterdir()) == before | {cache}
    assert json.loads((cache / "recovery.json").read_text()) == record
    assert record["training_started"] is False
    assert record["optimizer_state_recovered"] is False
    assert record["source_files_verified"] == 1
    assert record["split_rows"] == {"train": 3, "validation": 3, "test": 3}


def test_recovery_validates_headers_for_all_splits_without_materializing_array_values(recovery_fixture, monkeypatch):
    source, _, archive, cache, output = recovery_fixture
    utility = _recovery()
    calls = []
    original = utility._npz_headers

    def inspect_headers(path, channels):
        calls.append(path.name)
        return original(path, channels)

    def no_outcome_values(*args, **kwargs):
        raise AssertionError("Recovery must not load held-out array values")

    monkeypatch.setattr(utility, "_npz_headers", inspect_headers)
    monkeypatch.setattr(np, "load", no_outcome_values)
    utility.recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert calls == ["train.npz", "validation.npz", "test.npz"]


def test_complete_cache_reuses_payload_even_when_archive_is_unavailable(recovery_fixture, tmp_path):
    source, _, _, _, output = recovery_fixture
    expected = _hashes(source)
    before = {name: (source / name).read_bytes() for name in CACHE_FILES}
    result = _recovery().recover_cache(tmp_path / "not-present.zip", source,
                                       expected_hashes=expected, run_output=output)
    assert isinstance(result, dict)
    assert {name: (source / name).read_bytes() for name in CACHE_FILES} == before


def test_partial_existing_cache_is_preserved_and_not_filled(recovery_fixture):
    source, _, archive, cache, output = recovery_fixture
    cache.mkdir()
    (cache / "metadata.json").write_bytes((source / "metadata.json").read_bytes())
    before = {path.name: path.read_bytes() for path in cache.iterdir()}
    with pytest.raises((ValueError, FileExistsError, RuntimeError), match="[Pp]artial|[Ii]ncomplete|nonempty"):
        _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert {path.name: path.read_bytes() for path in cache.iterdir()} == before


def test_empty_existing_cache_directory_can_receive_atomic_recovery(recovery_fixture):
    source, _, archive, cache, output = recovery_fixture
    cache.mkdir()
    _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert _hashes(cache) == _hashes(source)


def test_recovery_rejects_changed_original_sources_without_promoting_cache(recovery_fixture, tmp_path):
    source, metadata, archive, cache, output = recovery_fixture
    (Path(metadata["data_root"]) / "source.bin").write_bytes(b"Changed original inputs")
    before = set(tmp_path.iterdir())
    with pytest.raises((ValueError, RuntimeError), match="[Ss]ource.*[Ii]ntegrity|[Ss]ource.*[Hh]ash|mismatch"):
        _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert not cache.exists()
    assert set(tmp_path.iterdir()) == before


def test_existing_complete_cache_is_rejected_if_its_payload_hash_differs(recovery_fixture):
    source, _, archive, _, output = recovery_fixture
    expected = _hashes(source)
    (source / "metadata.json").write_text((source / "metadata.json").read_text() + "\n")
    changed_bytes = (source / "metadata.json").read_bytes()
    with pytest.raises((ValueError, RuntimeError), match="[Ii]ntegrity|[Hh]ash|mismatch"):
        _recovery().recover_cache(archive, source, expected_hashes=expected, run_output=output)
    assert (source / "metadata.json").read_bytes() == changed_bytes


def test_protocol_bound_missing_cache_is_restored_only_with_exact_original_hashes(recovery_fixture):
    source, _, archive, cache, output = recovery_fixture
    expected = _hashes(source)
    protocol = _write_protocol(output, cache, expected)
    candidate = output / "candidates" / "one"
    candidate.mkdir(parents=True)
    (candidate / "last.pt").write_bytes(b"Existing candidate state is never read or modified by recovery")
    checkpoint = (candidate / "last.pt").read_bytes()
    _recovery().recover_cache(archive, cache, expected_hashes=expected, run_output=output)
    assert _hashes(cache) == expected
    assert json.loads((output / "protocol.json").read_text()) == protocol
    assert (candidate / "last.pt").read_bytes() == checkpoint


@pytest.mark.parametrize("mismatch", ["cache_path", "cache_hash", "training_source_hash"])
def test_resume_protocol_mismatch_refuses_recovery(recovery_fixture, mismatch, tmp_path):
    source, _, archive, cache, output = recovery_fixture
    expected = _hashes(source)
    protocol = _write_protocol(output, cache, expected)
    if mismatch == "cache_path":
        protocol["cache"] = str(tmp_path / "different_cache")
    elif mismatch == "cache_hash":
        protocol["cache_sha256"]["train.npz"] = "0" * 64
    else:
        protocol["training_source_sha256"]["cache.py"] = "0" * 64
    (output / "protocol.json").write_text(json.dumps(protocol))
    before = set(tmp_path.iterdir())
    with pytest.raises((ValueError, RuntimeError), match="[Pp]rotocol|[Ii]ntegrity|[Hh]ash|[Pp]ath|mismatch"):
        _recovery().recover_cache(archive, cache, expected_hashes=expected, run_output=output)
    assert not cache.exists()
    assert set(tmp_path.iterdir()) == before
    assert json.loads((output / "protocol.json").read_text()) == protocol


def test_orphan_saved_candidate_without_protocol_refuses_fresh_recovery(recovery_fixture):
    source, _, archive, cache, output = recovery_fixture
    candidate = output / "candidates" / "one"
    candidate.mkdir(parents=True)
    (candidate / "last.pt").write_bytes(b"Existing last checkpoint")
    with pytest.raises((ValueError, RuntimeError), match="[Pp]rotocol|checkpoint|[Oo]rphan"):
        _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert not cache.exists()
    assert (candidate / "last.pt").read_bytes() == b"Existing last checkpoint"


@pytest.mark.parametrize("prefix", ["../" + ARCHIVE_PREFIX, "/" + ARCHIVE_PREFIX])
def test_unsafe_selected_zip_paths_are_rejected(recovery_fixture, prefix, tmp_path):
    source, _, archive, cache, output = recovery_fixture
    _archive_cache(source, archive, prefix=prefix)
    before = set(tmp_path.iterdir())
    with pytest.raises((ValueError, RuntimeError), match="[Uu]nsafe|[Aa]bsolute|traversal|path"):
        _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert not cache.exists()
    assert set(tmp_path.iterdir()) == before


def test_multiple_complete_archive_cache_copies_are_rejected_as_ambiguous(recovery_fixture):
    source, _, archive, cache, output = recovery_fixture
    with zipfile.ZipFile(archive, "a") as zipped:
        for name in CACHE_FILES:
            zipped.write(source / name, "AnotherCopy/" + ARCHIVE_PREFIX + name)
    with pytest.raises((ValueError, RuntimeError), match="[Aa]mbigu|multiple|unique|exactly one"):
        _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert not cache.exists()


def test_duplicate_selected_archive_member_is_rejected(recovery_fixture):
    source, _, archive, cache, output = recovery_fixture
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(archive, "a") as zipped:
            zipped.writestr(ARCHIVE_PREFIX + "train.npz", (source / "train.npz").read_bytes())
    with pytest.raises((ValueError, RuntimeError), match="[Dd]uplicate|unique|ambig|exactly one"):
        _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert not cache.exists()


def test_symlink_selected_archive_member_is_rejected(recovery_fixture):
    source, _, archive, cache, output = recovery_fixture
    with zipfile.ZipFile(archive, "w") as zipped:
        for name in CACHE_FILES:
            if name == "train.npz":
                member = zipfile.ZipInfo(ARCHIVE_PREFIX + name)
                member.create_system = 3
                member.external_attr = 0o120777 << 16
                zipped.writestr(member, b"../external-target")
            else:
                zipped.write(source / name, ARCHIVE_PREFIX + name)
    with pytest.raises((ValueError, RuntimeError), match="[Ss]ymlink|regular|type|[Uu]nsafe"):
        _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert not cache.exists()


def test_missing_archive_member_is_reported_without_partial_cache(recovery_fixture):
    source, _, archive, cache, output = recovery_fixture
    with zipfile.ZipFile(archive, "w") as zipped:
        for name in CACHE_FILES[:-1]:
            zipped.write(source / name, ARCHIVE_PREFIX + name)
    with pytest.raises((ValueError, RuntimeError), match="[Cc]omplete|[Mm]issing|four|cache"):
        _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert not cache.exists()


@pytest.mark.parametrize("corruption", ["not_zip", "archive_payload_hash"])
def test_bad_archive_does_not_leave_staged_cache(recovery_fixture, corruption, tmp_path):
    source, _, archive, cache, output = recovery_fixture
    if corruption == "not_zip":
        archive.write_bytes(b"Not a ZIP archive")
    else:
        with zipfile.ZipFile(archive, "w") as zipped:
            for name in CACHE_FILES:
                payload = (source / name).read_bytes()
                zipped.writestr(ARCHIVE_PREFIX + name, payload + (b"changed" if name == "train.npz" else b""))
    before = set(tmp_path.iterdir())
    with pytest.raises((ValueError, RuntimeError, zipfile.BadZipFile)):
        _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert not cache.exists()
    assert set(tmp_path.iterdir()) == before


def test_bad_member_crc_is_rejected_and_staging_is_removed(recovery_fixture, tmp_path):
    source, _, archive, cache, output = recovery_fixture
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as zipped:
        for name in CACHE_FILES:
            zipped.writestr(ARCHIVE_PREFIX + name, (source / name).read_bytes())
        info = zipped.getinfo(ARCHIVE_PREFIX + "train.npz")
    payload = bytearray(archive.read_bytes())
    filename_size, extra_size = struct.unpack_from("<HH", payload, info.header_offset + 26)
    payload_offset = info.header_offset + 30 + filename_size + extra_size
    payload[payload_offset + 4] ^= 1
    archive.write_bytes(payload)
    before = set(tmp_path.iterdir())
    with pytest.raises((ValueError, RuntimeError, zipfile.BadZipFile), match="CRC|[Cc]orrupt|[Ii]ntegrity"):
        _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert not cache.exists()
    assert set(tmp_path.iterdir()) == before


@pytest.mark.parametrize("invalid", ["missing_array", "bad_shape", "bad_dtype", "wrong_kernel", "wrong_horizon",
                                     "smoke_subset", "contact_subset"])
def test_invalid_cache_contract_or_npz_headers_refuse_promotion(recovery_fixture, invalid, tmp_path):
    source, metadata, archive, cache, output = recovery_fixture
    if invalid in ("wrong_kernel", "wrong_horizon", "smoke_subset", "contact_subset"):
        if invalid == "smoke_subset":
            metadata["smoke_verification_only"] = True
        elif invalid == "contact_subset":
            metadata["eligibility"] = "at_least_one_burned_neighbor"
        else:
            metadata["kernel_size" if invalid == "wrong_kernel" else "dt_hours"] = 7 if invalid == "wrong_kernel" else 2.0
        (source / "metadata.json").write_text(json.dumps(metadata))
    else:
        with np.load(source / "test.npz", allow_pickle=False) as zipped:
            arrays = {name: zipped[name] for name in zipped.files}
        if invalid == "missing_array":
            del arrays["target"]
        elif invalid == "bad_shape":
            arrays["environment"] = np.zeros((3, 2, 7, 7), dtype=np.float32)
        else:
            arrays["weight"] = arrays["weight"].astype(np.float32)
        np.savez(source / "test.npz", **arrays)
    _archive_cache(source, archive)
    before = set(tmp_path.iterdir())
    with pytest.raises((ValueError, TypeError, RuntimeError), match="[Cc]ache|[Ss]hape|dtype|[Mm]issing|[Hh]our|9x9|[Kk]ernel|weight|target|environment"):
        _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert not cache.exists()
    assert set(tmp_path.iterdir()) == before


@pytest.mark.parametrize("failure", ["record_write", "directory_promotion"])
def test_atomic_write_failure_removes_staged_payload_and_leaves_no_final_cache(recovery_fixture, tmp_path, monkeypatch, failure):
    source, _, archive, cache, output = recovery_fixture
    utility = _recovery()
    if failure == "record_write":
        original = Path.write_text

        def fail_record(path, *args, **kwargs):
            if path.name == "recovery.json":
                raise OSError("Simulated recovery record write failure")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_record)
    else:
        def fail_promotion(*args, **kwargs):
            raise OSError("Simulated directory promotion failure")

        monkeypatch.setattr(utility.os, "replace", fail_promotion)
    before = set(tmp_path.iterdir())
    with pytest.raises(OSError, match="Simulated"):
        utility.recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert not cache.exists()
    assert set(tmp_path.iterdir()) == before


def test_unsafe_source_manifest_is_rejected_without_source_access_or_cache_promotion(recovery_fixture, tmp_path):
    source, metadata, archive, cache, output = recovery_fixture
    metadata["source_files"][0]["path"] = "../outside/source.bin"
    (source / "metadata.json").write_text(json.dumps(metadata))
    _archive_cache(source, archive)
    before = set(tmp_path.iterdir())
    with pytest.raises(ValueError, match="Unsafe source-file path"):
        _recovery().recover_cache(archive, cache, expected_hashes=_hashes(source), run_output=output)
    assert not cache.exists()
    assert set(tmp_path.iterdir()) == before
