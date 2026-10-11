"""Copy the original search cache with a verified source-data root for this host.

Only metadata.data_root changes. Prepared arrays, labels, weights, source hashes,
and split definitions are preserved. The existing cache and training runner are
not modified. Use the relocated cache with a fresh experiment output directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile

RUNS = Path(__file__).resolve().parent / "training_runs"
DEFAULT_SOURCE_CACHE = RUNS / "20261007_1h_kernel_sweep/9x9/prepared_all"
DEFAULT_OUTPUT_CACHE = RUNS / "20261007_1h_kernel_sweep/9x9/prepared_relocated"
FILES = ("metadata.json", "train.npz", "validation.npz", "test.npz")
# Original prepared_all bindings corroborated by the archived parent-cache
# manifest. Explicit alternate hashes are available only through the Python API
# for callers managing their own independently bound full caches.
ORIGINAL_CACHE_SHA256 = {
    "metadata.json": "5a83a0d0e3ec4dcff75cf9cb23efd560724169186175a6328496e878086a95c2",
    "train.npz": "b173420d618679ad0f70920cde12fce4ae595b245478e90ad3339cec23261a32",
    "validation.npz": "0c6520af473cfb672bb9d121a2adaffda8448b8bd733cecfe15c1ed73f9e2174",
    "test.npz": "e36391d77a6e5909ad4dfae8de4d14c50d6da28a4caf18409f1f0b19cbef8e0e",
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_sources(metadata, data_root):
    if not data_root.is_dir():
        raise FileNotFoundError(f"Environmental data directory is missing: {data_root}")
    manifest = metadata.get("source_files")
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("A nonempty original source-file manifest is required")
    seen = set()
    for source in manifest:
        if not isinstance(source, dict):
            raise ValueError("Invalid source-file manifest entry")
        name, expected = source.get("path"), source.get("sha256")
        if not isinstance(name, str) or not name or "\\" in name:
            raise ValueError("Unsafe source-file path in metadata")
        relative = PurePosixPath(name)
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise ValueError(f"Unsafe source-file path: {name}")
        canonical = relative.as_posix()
        if canonical in seen:
            raise ValueError(f"Duplicate source-file path: {name}")
        seen.add(canonical)
        if not isinstance(expected, str) or len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
            raise ValueError(f"Invalid source-file SHA-256: {name}")
        actual = (data_root / relative).resolve()
        if not actual.is_relative_to(data_root):
            raise ValueError(f"Source-file path escapes the environmental data root: {name}")
        if not actual.is_file():
            raise FileNotFoundError(f"Original environmental source file is missing: {actual}")
        if sha256(actual) != expected:
            raise ValueError(f"Source integrity mismatch at relocated root: {actual}")
    return len(seen)


def _verify_destination(destination, relocated_metadata, expected_arrays):
    if not all((destination / name).is_file() for name in FILES):
        raise ValueError("Destination cache is partial; existing files are preserved")
    if json.loads((destination / "metadata.json").read_text()) != relocated_metadata:
        raise ValueError("Destination metadata differs from the requested relocation; existing files are preserved")
    hashes = {name: sha256(destination / name) for name in FILES}
    if any(hashes[name] != digest for name, digest in expected_arrays.items()):
        raise ValueError("Destination prepared-array integrity mismatch; existing files are preserved")
    return hashes


def relocate_cache(source_cache, destination_cache, data_root, *, expected_hashes=None):
    """Verify original inputs and atomically create a cache with one new root."""
    source = Path(source_cache).resolve()
    destination = Path(destination_cache).resolve()
    root = Path(data_root).resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source and destination caches must be separate, nonoverlapping directories")
    if destination == root or destination in root.parents or root in destination.parents:
        raise ValueError("Destination cache and environmental data must be separate, nonoverlapping directories")
    expected = dict(ORIGINAL_CACHE_SHA256 if expected_hashes is None else expected_hashes)
    if set(expected) != set(FILES):
        raise ValueError("Expected hashes must bind all four original cache files")
    original_hashes = {name: sha256(source / name) for name in FILES}
    if original_hashes != expected:
        raise ValueError("Original cache SHA-256 mismatch; use the unchanged prepared_all cache")
    metadata = json.loads((source / "metadata.json").read_text())
    if metadata.get("dt_hours") != 1.0 or metadata.get("kernel_size") != 9 or metadata.get("smoke_verification_only"):
        raise ValueError("Relocation requires the full one-hour 9x9 search cache")
    if metadata.get("eligibility") == "at_least_one_burned_neighbor":
        raise ValueError("Relocation requires prepared_all, not a contact-filtered cache")
    if not isinstance(metadata.get("data_root"), str) or not metadata["data_root"]:
        raise ValueError("Original metadata must declare its data_root")
    verified_sources = _verify_sources(metadata, root)
    relocated_metadata = {**metadata, "data_root": str(root)}
    expected_arrays = {name: expected[name] for name in FILES if name != "metadata.json"}
    details = dict(source_cache=str(source), destination_cache=str(destination),
                   original_data_root=metadata["data_root"], data_root=str(root),
                   original_cache_sha256=original_hashes, verified_source_files=verified_sources,
                   training_started=False, metadata_changes=["data_root"],
                   requires_fresh_experiment_output=True)
    if destination.exists() and any(destination.iterdir()):
        hashes = _verify_destination(destination, relocated_metadata, expected_arrays)
        return dict(status="already_present", relocated_cache_sha256=hashes, **details)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".cache-relocation-", dir=destination.parent))
    try:
        for name in expected_arrays:
            shutil.copyfile(source / name, staging / name)
        (staging / "metadata.json").write_text(json.dumps(relocated_metadata, indent=2) + "\n")
        hashes = _verify_destination(staging, relocated_metadata, expected_arrays)
        # Reject a source changed during the copy rather than record a stale
        # provenance binding. Source files are never opened for writing.
        if any(sha256(source / name) != original_hashes[name] for name in FILES):
            raise ValueError("Original cache changed during relocation")
        record = dict(status="relocated", relocated_at_utc=datetime.now(timezone.utc).isoformat(),
                      relocated_cache_sha256=hashes, **details)
        (staging / "relocation.json").write_text(json.dumps(record, indent=2) + "\n")
        # Windows cannot replace an existing directory with os.replace. A
        # pre-existing empty destination has no payload to preserve; rmdir
        # also refuses a concurrently populated destination rather than
        # overwrite it. The staged directory is then promoted in one rename.
        if destination.exists():
            destination.rmdir()
        os.replace(staging, destination)
        return record
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-cache", type=Path, default=DEFAULT_SOURCE_CACHE)
    parser.add_argument("--output-cache", type=Path, default=DEFAULT_OUTPUT_CACHE)
    parser.add_argument("--data-root", type=Path, required=True,
                        help="This host's complete original environmental_data directory")
    args = parser.parse_args()
    print(json.dumps(relocate_cache(args.source_cache, args.output_cache, args.data_root), indent=2))


if __name__ == "__main__":
    main()
