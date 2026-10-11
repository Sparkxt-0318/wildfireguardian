"""Exact acquisition-source provenance after workspace consolidation."""
from hashlib import sha256

import pytest


@pytest.mark.parametrize("location", ["current", "legacy", "hashed_archive"])
def test_biome_source_record_requires_exact_matching_bytes(tmp_path, monkeypatch, location):
    import wildfire.environment as environment

    root = tmp_path / "data" / "environment"
    root.mkdir(parents=True)
    monkeypatch.setattr(environment, "ROOT", root)
    current = tmp_path / "environment.py"
    current.write_bytes(b"different current implementation\n")
    monkeypatch.setattr(environment, "__file__", str(current))
    archive = root.parent / "records" / "environment_code"
    archive.mkdir(parents=True)
    original = b"exact historical acquisition implementation\n"
    digest = sha256(original).hexdigest()
    if location == "current":
        target = current
    elif location == "legacy":
        target = archive / "acquire_biome.py"
    else:
        (archive / "acquire_biome.py").write_bytes(b"later compatibility wrapper\n")
        target = archive / f"acquire_biome_{digest}.py"
    target.write_bytes(original)
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert environment._biome_acquisition_source(digest) == target
    assert {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


def test_biome_source_record_rejects_tampered_hash_named_archive(tmp_path, monkeypatch):
    import wildfire.environment as environment

    root = tmp_path / "data" / "environment"
    root.mkdir(parents=True)
    monkeypatch.setattr(environment, "ROOT", root)
    digest = sha256(b"missing original source").hexdigest()
    archive = root.parent / "records" / "environment_code"
    archive.mkdir(parents=True)
    target = archive / f"acquire_biome_{digest}.py"
    target.write_bytes(b"tampered source under the correct filename")
    with pytest.raises(ValueError, match="No exact acquisition source"):
        environment._biome_acquisition_source(digest)


@pytest.mark.parametrize("digest", [None, "", "../acquire_biome.py", "A" * 64, "g" * 64])
def test_biome_source_record_rejects_invalid_digests(digest):
    import wildfire.environment as environment

    with pytest.raises(ValueError, match="lowercase SHA-256"):
        environment._biome_acquisition_source(digest)
