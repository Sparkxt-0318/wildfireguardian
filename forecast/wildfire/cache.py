"""Cache operations for the wildfire workspace."""
from __future__ import annotations

from .paths import resolve_recorded_path, resolve_source_root



# Cache
# Prepared partitions and training-only weighted feature normalization.


from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np

from wildfire.schema import one_hot_groups
from wildfire.schema import validate_one_hot_array

SPLIT_NAMES = ("train", "validation", "test")
IDENTITY_FIELDS = ("event_index", "time_utc", "row", "col")
IDENTITY_DTYPE = np.dtype([(name, np.int64) for name in IDENTITY_FIELDS])


def validate_split_metadata(metadata: dict[str, Any], *,
                            require_all_partitions: bool = False) -> dict[str, frozenset[str]]:
    """Validate event declarations for either whole-fire or explicit row splits.

    Missing ``split_unit`` retains the legacy whole-fire contract. Only an
    explicit ``cell_hour`` declaration allows an event in both training and
    validation. Original test events must remain exclusively in test. Events
    with no prepared rows may have an empty row-split membership list.
    """
    event_ids = metadata.get("event_ids")
    if (not isinstance(event_ids, list) or not event_ids
            or not all(isinstance(event_id, str) and event_id for event_id in event_ids)
            or len(set(event_ids)) != len(event_ids)):
        raise ValueError("Cache metadata must contain a nonempty unique ordered event_ids list")
    declarations = metadata.get("splits")
    if not isinstance(declarations, dict) or set(declarations) != set(event_ids):
        raise ValueError("Each metadata event must have exactly one split declaration")
    split_unit = metadata.get("split_unit", "whole_fire")
    if split_unit not in ("whole_fire", "fire", "cell_hour"):
        raise ValueError("Cache split_unit must be whole_fire or cell_hour")
    memberships = {}
    if split_unit == "cell_hour":
        original = metadata.get("original_splits")
        if (not isinstance(original, dict) or set(original) != set(event_ids)
                or any(not isinstance(value, str) or value not in SPLIT_NAMES
                       for value in original.values())):
            raise ValueError("Cell-hour splits require the complete original whole-fire split map")
        for event_id, values in declarations.items():
            if (not isinstance(values, list)
                    or any(not isinstance(value, str) or value not in SPLIT_NAMES for value in values)
                    or len(set(values)) != len(values)):
                raise ValueError(f"Invalid cell-hour split membership list for event {event_id}")
            assigned = frozenset(values)
            if "test" in assigned and assigned != frozenset(("test",)):
                raise ValueError(f"Test event {event_id} cannot also contribute to training or validation")
            if (original[event_id] == "test") != (assigned == frozenset(("test",))):
                raise ValueError(f"Cell-hour splitting must preserve the original test assignment for {event_id}")
            memberships[event_id] = assigned
    else:
        for event_id, value in declarations.items():
            if not isinstance(value, str) or value not in SPLIT_NAMES:
                raise ValueError(f"Whole-fire event {event_id} must have exactly one named split assignment")
            memberships[event_id] = frozenset((value,))
    if require_all_partitions and set().union(*memberships.values()) != set(SPLIT_NAMES):
        raise ValueError("Cache metadata must declare train, validation, and test partitions")
    return memberships


def cache_kernel_size(metadata: dict[str, Any]) -> int:
    """Read the explicit odd spatial kernel side length from cache metadata."""
    size = metadata.get("kernel_size")
    if not isinstance(size, int) or isinstance(size, bool) or size < 3 or size % 2 != 1:
        raise ValueError("Cache kernel_size must be an odd integer >= 3")
    return size


@dataclass(frozen=True)
class CachedSplit:
    environment: np.ndarray
    burned: np.ndarray
    target: np.ndarray
    weight: np.ndarray
    event_index: np.ndarray
    time_utc: np.ndarray
    row: np.ndarray
    col: np.ndarray

    def __len__(self) -> int:
        return len(self.target)

    @property
    def neighbor_count(self) -> np.ndarray:
        # The central cell is required to be unburned by load_split().
        return self.burned.sum(axis=(1, 2, 3), dtype=np.float32)


def cell_hour_identities(data: CachedSplit) -> np.ndarray:
    """Return exact event/time/row/column keys without retaining patch arrays."""
    keys = np.empty(len(data), dtype=IDENTITY_DTYPE)
    for name in IDENTITY_FIELDS:
        values = getattr(data, name)
        if values.shape != (len(data),) or not np.issubdtype(values.dtype, np.integer):
            raise ValueError(f"Cell-hour identity {name} must be a one-dimensional integer array")
        if np.issubdtype(values.dtype, np.unsignedinteger) and (values > np.iinfo(np.int64).max).any():
            raise ValueError(f"Cell-hour identity {name} exceeds the supported int64 range")
        keys[name] = values
    return keys


def validate_partition_disjointness(partitions: dict[str, CachedSplit | np.ndarray],
                                   metadata: dict[str, Any]) -> dict[str, Any]:
    """Reject duplicated rows, shared identities, and undeclared event overlap.

    Identity-only arrays from ``cell_hour_identities`` are accepted so that
    independent verification need not retain all environmental patch arrays.
    Whole-fire caches retain pairwise event separation. Row-split caches allow
    training/validation event overlap but keep test fires separate from both.
    """
    memberships = validate_split_metadata(metadata)
    row_split = metadata.get("split_unit") == "cell_hour"
    keys, event_sets = {}, {}
    for name, data in partitions.items():
        if name not in SPLIT_NAMES:
            raise ValueError(f"Unknown cache partition {name}")
        identity = cell_hour_identities(data) if isinstance(data, CachedSplit) else np.asarray(data)
        if identity.ndim != 1 or identity.dtype != IDENTITY_DTYPE:
            raise ValueError("Partition identities must use the exact event/time/row/column key schema")
        if len(np.unique(identity)) != len(identity):
            raise ValueError(f"Duplicate cell-hour identities in {name}")
        keys[name] = identity
        event_sets[name] = set(int(index) for index in np.unique(identity["event_index"]))
        for index in event_sets[name]:
            if index < 0 or index >= len(metadata["event_ids"]):
                raise ValueError(f"Out-of-range event indices in {name}")
            event_id = metadata["event_ids"][index]
            if name not in memberships[event_id]:
                raise ValueError(f"Event {event_id} is in the wrong cache split")
    names = list(keys)
    for position, first in enumerate(names):
        for second in names[position + 1:]:
            if np.intersect1d(keys[first], keys[second], assume_unique=True).size:
                raise ValueError(f"Shared cell-hour identities between {first} and {second}")
            if event_sets[first] & event_sets[second] and (not row_split or "test" in (first, second)):
                raise ValueError(f"A fire contributes to both {first} and {second} despite its split contract")
    return {
        "split_unit": "cell_hour" if row_split else "whole_fire",
        "disjoint_cell_hour_identities": True,
        "disjoint_contributing_fire_sets": all(
            not event_sets[first] & event_sets[second]
            for position, first in enumerate(names) for second in names[position + 1:]),
        "test_fires_disjoint_from_training_validation": all(
            not event_sets.get("test", set()) & event_sets.get(name, set())
            for name in ("train", "validation")),
    }


def load_split(directory: Path, name: str, metadata: dict[str, Any]) -> CachedSplit:
    """Load one cache partition and reject an inconsistent training contract."""
    if name not in SPLIT_NAMES:
        raise ValueError(f"Unknown cache partition {name}")
    memberships = validate_split_metadata(metadata)
    with np.load(directory / f"{name}.npz", allow_pickle=False) as archive:
        names = tuple(CachedSplit.__dataclass_fields__)
        missing = set(names) - set(archive.files)
        if missing:
            raise ValueError(f"{name}.npz is missing {sorted(missing)}")
        data = CachedSplit(**{key: archive[key] for key in names})
    n, channels = len(data), len(metadata["channels"])
    kernel_size = cache_kernel_size(metadata)
    center = kernel_size // 2
    if n == 0:
        raise ValueError(f"The {name} cache is empty")
    if data.environment.shape != (n, channels, kernel_size, kernel_size):
        raise ValueError(f"Invalid environmental patch shape in {name}")
    if data.burned.shape != (n, 1, kernel_size, kernel_size):
        raise ValueError(f"Invalid burned patch shape in {name}")
    for key in ("target", "weight", "event_index", "time_utc", "row", "col"):
        if getattr(data, key).shape != (n,):
            raise ValueError(f"Invalid {key} shape in {name}")
    if data.environment.dtype != np.float32 or data.burned.dtype != np.float32:
        raise TypeError("Environmental and burned patches must be float32")
    if data.weight.dtype != np.float64:
        raise TypeError("Inverse inclusion-probability weights must be float64")
    if not np.isfinite(data.environment).all():
        raise ValueError(f"Nonfinite environmental features in {name}")
    validate_one_hot_array(data.environment, metadata)
    if not np.isin(data.burned, (0, 1)).all():
        raise ValueError(f"Nonbinary burned patch values in {name}")
    if not (data.burned[:, 0, center, center] == 0).all():
        raise ValueError(f"The {name} cache contains already-burned targets")
    if metadata.get("eligibility") == "at_least_one_burned_neighbor" and not (data.neighbor_count > 0).all():
        raise ValueError(f"The {name} cache contains a no-contact target despite its contact-only contract")
    if not np.isin(data.target, (0, 1)).all():
        raise ValueError(f"Targets in {name} must be exactly zero or one")
    if not np.isfinite(data.weight).all() or not (data.weight >= 1).all():
        raise ValueError(f"Invalid inverse sampling weights in {name}")
    for key in ("event_index", "time_utc", "row", "col"):
        if not np.issubdtype(getattr(data, key).dtype, np.integer):
            raise TypeError(f"{key} must have an integer dtype")
    if (data.event_index < 0).any() or (data.event_index >= len(metadata["event_ids"])).any():
        raise ValueError(f"Out-of-range event indices in {name}")
    for index in np.unique(data.event_index):
        event_id = metadata["event_ids"][int(index)]
        if name not in memberships[event_id]:
            raise ValueError(f"Event {event_id} is in the wrong cache split")
    if metadata.get("split_unit") == "cell_hour":
        # Row-level assignment requires unique identities even within a file.
        # Legacy whole-fire archives keep their historical load behavior.
        if len(np.unique(cell_hour_identities(data))) != n:
            raise ValueError(f"Duplicate cell-hour identities in {name}")
    return data


def fit_normalization(data: CachedSplit, chunk_size: int = 8192, *,
                      metadata: dict[str, Any] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Weighted feature moments using training targets and every patch cell.

    Each target's inverse sampling weight applies equally to its feature
    positions. A second centered pass avoids cancellation for large raw values.
    Constant continuous channels use a scale of one. With an explicit input
    schema, categorical indicators retain mean zero and scale one: raw 0/1
    inputs do not acquire very large values when their categories are rare.
    Omitting metadata retains the historical all-channel normalization for
    independently reproducing older fitted checkpoints.
    """
    channels = data.environment.shape[1]
    # Wider environmental patches should not require an unbounded float64
    # temporary. Existing 3x3 runs retain their 8192-row summation order.
    bytes_per_row = channels * math.prod(data.environment.shape[2:]) * np.dtype(np.float64).itemsize
    chunk_size = min(chunk_size, max(1, (64 * 1024 * 1024) // bytes_per_row))
    total_weight = float(data.weight.sum(dtype=np.float64))
    mean = np.zeros(channels, dtype=np.float64)
    for start in range(0, len(data), chunk_size):
        end = min(start + chunk_size, len(data))
        values = data.environment[start:end].astype(np.float64)
        pixel_mean = values.mean(axis=(2, 3))
        mean += (pixel_mean * data.weight[start:end, None]).sum(axis=0)
    mean /= total_weight
    variance = np.zeros(channels, dtype=np.float64)
    for start in range(0, len(data), chunk_size):
        end = min(start + chunk_size, len(data))
        centered = data.environment[start:end].astype(np.float64) - mean[None, :, None, None]
        pixel_variance = np.square(centered).mean(axis=(2, 3))
        variance += (pixel_variance * data.weight[start:end, None]).sum(axis=0)
    std = np.sqrt(variance / total_weight)
    std = np.where(std < 1e-6, 1.0, std)
    if metadata is not None:
        categorical_indices = [index for group in one_hot_groups(metadata).values() for index in group]
        mean[categorical_indices] = 0.0
        std[categorical_indices] = 1.0
    if not np.isfinite(mean).all() or not np.isfinite(std).all():
        raise RuntimeError("Training normalization produced nonfinite moments")
    return mean.astype(np.float32), std.astype(np.float32)


# Recover search cache
# Restore the original full search cache from a verified local ZIP archive.
# 
# This restores exact input bytes; it never rebuilds data, changes a run protocol,
# starts training, or recovers an optimizer state. ZIP members unrelated to the
# four cache files are not extracted. Existing nonempty partial caches are kept.


import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
from zipfile import ZipFile


PACKAGE = Path(__file__).resolve().parent
from .paths import RUNS as recover_RUNS
CACHE_SUFFIX = '20261007_1h_kernel_sweep/9x9/prepared_all/'
DEFAULT_CACHE = recover_RUNS / CACHE_SUFFIX
DEFAULT_ARCHIVE = PACKAGE.parent.parent / 'WildfireGuardian.zip'
DEFAULT_RUN_OUTPUT = recover_RUNS / '20261009_multiscale_kernel_search'
recover_FILES = ('metadata.json', 'train.npz', 'validation.npz', 'test.npz')
# Independently corroborated by the archived contact-filtered cache's parent
# bindings; the source manifest also matches all 486 current original inputs.
recover_ORIGINAL_CACHE_SHA256 = {
    'metadata.json': '5a83a0d0e3ec4dcff75cf9cb23efd560724169186175a6328496e878086a95c2',
    'train.npz': 'b173420d618679ad0f70920cde12fce4ae595b245478e90ad3339cec23261a32',
    'validation.npz': '0c6520af473cfb672bb9d121a2adaffda8448b8bd733cecfe15c1ed73f9e2174',
    'test.npz': 'e36391d77a6e5909ad4dfae8de4d14c50d6da28a4caf18409f1f0b19cbef8e0e',
}


def recover_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _check_run(output, cache, expected):
    if output is None or not output.exists():
        return
    path = output / 'protocol.json'
    if not path.exists():
        if any(output.rglob('*.pt')) or (output / 'candidate_selection.json').exists():
            raise ValueError('Saved training states have no protocol; restore their original protocol before recovery')
        return
    protocol = json.loads(path.read_text())
    if protocol.get('cache') != str(cache.resolve()) or protocol.get('cache_sha256') != expected:
        raise ValueError('Recovery cache path/hashes differ from the frozen run protocol; its binding will not be changed')
    for name, digest in protocol.get('training_source_sha256', {}).items():
        if recover_sha256(PACKAGE / name) != digest:
            raise ValueError(f'Frozen training source integrity mismatch: {name}')


def _npz_headers(path, channels):
    """Verify every declared array without loading held-out outcomes."""
    fields = ('environment', 'burned', 'target', 'weight', 'event_index', 'time_utc', 'row', 'col')
    headers = {}
    with ZipFile(path) as archive:
        for field in fields:
            entries = [info for info in archive.infolist() if info.filename == field + '.npy']
            if len(entries) != 1:
                raise ValueError(f'{path.name} requires exactly one {field}.npy')
            with archive.open(entries[0]) as stream:
                version = np.lib.format.read_magic(stream)
                if version == (1, 0):
                    shape, order, dtype = np.lib.format.read_array_header_1_0(stream)
                elif version == (2, 0):
                    shape, order, dtype = np.lib.format.read_array_header_2_0(stream)
                else:
                    raise ValueError(f'Unsupported array header version in {path.name}')
            headers[field] = (shape, np.dtype(dtype))
    shape, _ = headers['target']
    if len(shape) != 1 or shape[0] <= 0:
        raise ValueError(f'{path.name} has no valid target rows')
    n = shape[0]
    for field, (shape, dtype) in headers.items():
        expected_shape = (n, channels, 9, 9) if field == 'environment' else (n, 1, 9, 9) if field == 'burned' else (n,)
        if shape != expected_shape:
            raise ValueError(f'Invalid {field} array shape in {path.name}')
        if field in ('environment', 'burned', 'target') and dtype != np.dtype('float32'):
            raise ValueError(f'Invalid {field} array dtype in {path.name}')
        if field == 'weight' and dtype != np.dtype('float64'):
            raise ValueError(f'Invalid weight dtype in {path.name}')
        if field in ('event_index', 'time_utc', 'row', 'col') and not np.issubdtype(dtype, np.integer):
            raise ValueError(f'Invalid {field} array dtype in {path.name}')
    return n


def _validate_cache(cache, expected):
    actual = {name: recover_sha256(cache / name) for name in recover_FILES}
    if actual != expected:
        mismatches = [name for name in recover_FILES if actual[name] != expected[name]]
        raise ValueError(f'Original cache SHA-256 mismatch: {mismatches}')
    metadata = json.loads((cache / 'metadata.json').read_text())
    if metadata.get('kernel_size') != 9 or metadata.get('dt_hours') != 1.0 or metadata.get('smoke_verification_only'):
        raise ValueError('Recovery requires the full one-hour 9x9 cache, not a smoke subset')
    if metadata.get('eligibility') == 'at_least_one_burned_neighbor':
        raise ValueError('Recovery requires prepared_all, not a contact-filtered cache')
    channels = metadata.get('channels')
    if not isinstance(channels, list) or not channels or len(set(channels)) != len(channels):
        raise ValueError('Invalid cache channel schema')
    data_root = resolve_source_root(metadata)
    sources = metadata.get('source_files')
    if not isinstance(sources, list) or not sources:
        raise ValueError('Recovery requires the original source-file manifest')
    for source in sources:
        relative = PurePosixPath(source['path'])
        if relative.is_absolute() or '..' in relative.parts or '\\' in source['path']:
            raise ValueError('Unsafe source-file path in cache metadata')
        path = data_root / relative
        if not path.is_file() or recover_sha256(path) != source['sha256']:
            raise ValueError(f'Source integrity mismatch: {path}')
    rows = {name: _npz_headers(cache / f'{name}.npz', len(channels)) for name in ('train', 'validation', 'test')}
    for name, n in rows.items():
        if metadata.get('split_summary', {}).get(name, {}).get('samples') != n:
            raise ValueError(f'{name} row count differs from the saved metadata')
    return dict(cache_sha256=actual, source_files_verified=len(sources), split_rows=rows, channels=len(channels))


def _select_members(archive):
    suffix = CACHE_SUFFIX + 'metadata.json'
    candidates = [info.filename[:-len('metadata.json')] for info in archive.infolist() if info.filename.endswith(suffix)]
    if len(candidates) != 1:
        raise ValueError('Archive must contain exactly one original 9x9 cache prefix')
    prefix = candidates[0]
    selected = {}
    for name in recover_FILES:
        entries = [info for info in archive.infolist() if info.filename == prefix + name]
        if len(entries) != 1:
            raise ValueError(f'Archive requires exactly one cache member: {name}')
        info = entries[0]
        path = PurePosixPath(info.filename)
        if path.is_absolute() or '..' in path.parts or '\\' in info.filename or info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
            raise ValueError(f'Unsafe selected archive member: {info.filename}')
        selected[name] = info
    return selected


def recover_cache(archive, cache, *, expected_hashes=None, run_output=None):
    """Restore exact original bytes atomically, or verify an existing cache."""
    archive, cache = Path(archive), Path(cache)
    output = None if run_output is None else Path(run_output)
    expected = dict(recover_ORIGINAL_CACHE_SHA256 if expected_hashes is None else expected_hashes)
    if set(expected) != set(recover_FILES):
        raise ValueError('Expected hashes must bind all four original cache files')
    _check_run(output, cache, expected)
    if cache.exists() and any(cache.iterdir()):
        if not all((cache / name).is_file() for name in recover_FILES):
            raise ValueError('Existing cache is partial; recovery preserves it and requires a separate empty destination')
        result = _validate_cache(cache, expected)
        return dict(status='already_present', cache=str(cache.resolve()), **result)
    if not archive.is_file():
        raise FileNotFoundError(f'Original cache and recovery archive are missing: {archive}')
    cache.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.cache-recovery-', dir=cache.parent))
    try:
        with ZipFile(archive) as source:
            selected = _select_members(source)
            for name, info in selected.items():
                with source.open(info) as reader, (staging / name).open('wb') as writer:
                    shutil.copyfileobj(reader, writer, length=1024 * 1024)
        result = _validate_cache(staging, expected)
        record = dict(status='restored', restored_at_utc=datetime.now(timezone.utc).isoformat(),
                      archive=str(archive.resolve()), archive_members={name:info.filename for name,info in selected.items()},
                      cache=str(cache.resolve()), training_started=False, optimizer_state_recovered=False, **result)
        (staging / 'recovery.json').write_text(json.dumps(record, indent=2) + '\n')
        os.replace(staging, cache)
        return record
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def recover_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument('--cache', type=Path, default=DEFAULT_CACHE)
    parser.add_argument('--run-output', type=Path, default=DEFAULT_RUN_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(recover_cache(args.archive, args.cache, run_output=args.run_output), indent=2))




# Relocate search cache
# Copy the original search cache with a verified source-data root for this host.
# 
# Only metadata.data_root changes. Prepared arrays, labels, weights, source hashes,
# and split definitions are preserved. The existing cache and training runner are
# not modified. Use the relocated cache with a fresh experiment output directory.



from .paths import RUNS as relocate_RUNS
DEFAULT_SOURCE_CACHE = relocate_RUNS / "20261007_1h_kernel_sweep/9x9/prepared_all"
DEFAULT_OUTPUT_CACHE = relocate_RUNS / "20261007_1h_kernel_sweep/9x9/prepared_relocated"
relocate_FILES = ("metadata.json", "train.npz", "validation.npz", "test.npz")
# Original prepared_all bindings corroborated by the archived parent-cache
# manifest. Explicit alternate hashes are available only through the Python API
# for callers managing their own independently bound full caches.
relocate_ORIGINAL_CACHE_SHA256 = {
    "metadata.json": "5a83a0d0e3ec4dcff75cf9cb23efd560724169186175a6328496e878086a95c2",
    "train.npz": "b173420d618679ad0f70920cde12fce4ae595b245478e90ad3339cec23261a32",
    "validation.npz": "0c6520af473cfb672bb9d121a2adaffda8448b8bd733cecfe15c1ed73f9e2174",
    "test.npz": "e36391d77a6e5909ad4dfae8de4d14c50d6da28a4caf18409f1f0b19cbef8e0e",
}


def relocate_sha256(path):
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
        if relocate_sha256(actual) != expected:
            raise ValueError(f"Source integrity mismatch at relocated root: {actual}")
    return len(seen)


def _verify_destination(destination, relocated_metadata, expected_arrays):
    if not all((destination / name).is_file() for name in relocate_FILES):
        raise ValueError("Destination cache is partial; existing files are preserved")
    if json.loads((destination / "metadata.json").read_text()) != relocated_metadata:
        raise ValueError("Destination metadata differs from the requested relocation; existing files are preserved")
    hashes = {name: relocate_sha256(destination / name) for name in relocate_FILES}
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
    expected = dict(relocate_ORIGINAL_CACHE_SHA256 if expected_hashes is None else expected_hashes)
    if set(expected) != set(relocate_FILES):
        raise ValueError("Expected hashes must bind all four original cache files")
    original_hashes = {name: relocate_sha256(source / name) for name in relocate_FILES}
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
    expected_arrays = {name: expected[name] for name in relocate_FILES if name != "metadata.json"}
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
        if any(relocate_sha256(source / name) != original_hashes[name] for name in relocate_FILES):
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


def relocate_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-cache", type=Path, default=DEFAULT_SOURCE_CACHE)
    parser.add_argument("--output-cache", type=Path, default=DEFAULT_OUTPUT_CACHE)
    parser.add_argument("--data-root", type=Path, required=True,
                        help="This host's complete original environmental_data directory")
    args = parser.parse_args()
    print(json.dumps(relocate_cache(args.source_cache, args.output_cache, args.data_root), indent=2))


