"""Prepare operations for the wildfire workspace."""
from __future__ import annotations

from .paths import resolve_recorded_path, resolve_source_root



# Weighted split
# Seeded row splits that retain inverse weights and categorical coverage.
# 
# Only pooled training and validation rows belong in this function. The caller
# keeps the test partition fixed. Allocation strata are the binary next-hour
# target, the smallest current-contact footprint, and the categorical values
# present anywhere in the full environmental patch. Allocation never changes a
# row's original inverse inclusion weight.


from typing import Any

import numpy as np


def _nearest_weighted_subset(weights: np.ndarray, fraction: float,
                             rng: np.random.Generator) -> np.ndarray:
    """Find a seeded, locally refined subset while leaving both sides nonempty.

    Rows are considered in seeded random order. Refinement considers one-row
    moves and one-for-one swaps. This is
    a bounded heuristic for the weighted subset problem, not an exact solver.
    """
    count = len(weights)
    selected = np.zeros(count, dtype=bool)
    if count == 1:
        return selected
    permutation = rng.permutation(count)
    desired = fraction * float(weights.sum(dtype=np.float64))
    current = 0.0
    selected_count = 0
    for index in permutation:
        candidate = current + float(weights[index])
        if selected_count < count - 1 and abs(candidate - desired) < abs(current - desired):
            selected[index] = True
            selected_count += 1
            current = candidate
    if selected_count == 0:
        # A stratum can have no weight small enough to improve on the empty
        # subset. The two-sided count guard then selects its lightest row.
        index = permutation[int(np.argmin(weights[permutation]))]
        selected[index] = True
        current = float(weights[index])

    # Representative rows preserve the seeded order among equal weights. A
    # weight can therefore be optimized once without sorting every tied row.
    for _ in range(64):
        inside = permutation[selected[permutation]]
        outside = permutation[~selected[permutation]]
        in_weights, in_first = np.unique(weights[inside], return_index=True)
        out_weights, out_first = np.unique(weights[outside], return_index=True)
        in_rows, out_rows = inside[in_first], outside[out_first]
        error = abs(current - desired)
        tolerance = 8 * np.finfo(np.float64).eps * max(1.0, desired, current)
        best_error = error
        action: tuple[str, int, int | None] | None = None
        if len(outside) > 1:
            errors = np.abs(current + out_weights - desired)
            position = int(np.argmin(errors))
            if float(errors[position]) < best_error - tolerance:
                best_error = float(errors[position])
                action = ("add", int(out_rows[position]), None)
        if len(inside) > 1:
            errors = np.abs(current - in_weights - desired)
            position = int(np.argmin(errors))
            if float(errors[position]) < best_error - tolerance:
                best_error = float(errors[position])
                action = ("remove", int(in_rows[position]), None)
        # For each selected weight a, the best outside replacement is the
        # available weight nearest desired-current+a. Binary search examines
        # the two adjacent candidates rather than all pairs of rows.
        positions = np.searchsorted(out_weights, desired - current + in_weights)
        for adjustment in (0, -1):
            candidate_positions = np.clip(positions + adjustment, 0, len(out_weights) - 1)
            errors = np.abs(current - in_weights + out_weights[candidate_positions] - desired)
            position = int(np.argmin(errors))
            if float(errors[position]) < best_error - tolerance:
                best_error = float(errors[position])
                action = ("swap", int(in_rows[position]),
                          int(out_rows[candidate_positions[position]]))
        if action is None:
            break
        kind, first, second = action
        if kind == "add":
            selected[first] = True
            current += float(weights[first])
        elif kind == "remove":
            selected[first] = False
            current -= float(weights[first])
        else:
            assert second is not None
            selected[first], selected[second] = False, True
            current += float(weights[second] - weights[first])
    return selected


def _population_summary(target: np.ndarray, weight: np.ndarray,
                        membership: np.ndarray) -> dict[str, Any]:
    values, weights = target[membership], weight[membership]
    positive = float(weights[values == 1].sum(dtype=np.float64))
    negative = float(weights[values == 0].sum(dtype=np.float64))
    total = positive + negative
    return {"rows": int(membership.sum()),
            "positive_rows": int((values == 1).sum()),
            "positive_weight": positive, "negative_weight": negative,
            "population_weight": total,
            "weighted_frequency": positive / total if total else None}


def weighted_row_assignment(target: np.ndarray, weight: np.ndarray,
                            burned: np.ndarray,
                            categorical_presence: np.ndarray | None = None, *,
                            validation_fraction: float = .2,
                            seed: int = 7) -> tuple[np.ndarray, dict[str, Any]]:
    """Assign pooled non-test rows to validation with explicit weighted strata.

    ``target`` and ``weight`` have shape ``[N]``. Targets must be zero or one;
    weights must be finite and at least one. ``burned`` has shape ``[N,1,K,K]``
    for odd ``K>=3``; every state must be known and binary, with center zero.
    ``categorical_presence``, when supplied, is a bool array ``[N,C]``. Column
    c states whether categorical value c occurs anywhere in that row's full
    environmental patch; the caller supplies the column-to-value vocabulary.

    The returned bool mask has shape ``[N]`` and is true for validation rows.
    All input rows and weights are retained. Strata with at least two rows
    keep at least one row on each side; singleton strata remain in training.
    Consequently every validation categorical signature also occurs in
    training. The requested fraction is a weighted population-mass target,
    not a required sampled-row fraction. The audit reports attainable errors.

    The caller must pool only training and validation rows and preserve test
    rows separately. No test labels, event identities, or test features enter
    this calculation. Row splitting may place neighboring cells or hours
    from the same fire on both sides; it is not a whole-fire holdout.
    """
    if (isinstance(validation_fraction, (bool, np.bool_))
            or not np.isscalar(validation_fraction)):
        raise ValueError("validation_fraction must be a finite number strictly between zero and one")
    fraction = float(validation_fraction)
    if not np.isfinite(fraction) or not 0 < fraction < 1:
        raise ValueError("validation_fraction must be a finite number strictly between zero and one")
    if (not isinstance(seed, (int, np.integer)) or isinstance(seed, (bool, np.bool_))
            or seed < 0):
        raise ValueError("seed must be a nonnegative integer")
    targets = np.asarray(target)
    weights = np.asarray(weight, dtype=np.float64)
    states = np.asarray(burned)
    if targets.ndim != 1 or weights.shape != targets.shape or len(targets) < 2:
        raise ValueError("target and weight must have matching nonempty [N] shapes with N >= 2")
    if not np.isin(targets, (0, 1)).all():
        raise ValueError("Targets must be exactly zero or one")
    if not np.isfinite(weights).all() or (weights < 1).any():
        raise ValueError("Inverse inclusion weights must be finite and at least one")
    with np.errstate(over="ignore"):
        total_weight = float(weights.sum(dtype=np.float64))
    if not np.isfinite(total_weight):
        raise ValueError("The pooled inverse inclusion weight must have a finite float64 sum")
    count = len(targets)
    if (states.ndim != 4 or states.shape[:2] != (count, 1)
            or states.shape[2] != states.shape[3]
            or states.shape[2] < 3 or states.shape[2] % 2 != 1):
        raise ValueError("burned must have shape [N, 1, K, K] for odd K >= 3")
    if not np.isin(states, (0, 1)).all():
        raise ValueError("Every burned patch state must be known and exactly zero or one")
    outer = states.shape[2]
    if (states[:, 0, outer // 2, outer // 2] != 0).any():
        raise ValueError("Every target center must currently be unburned")
    if categorical_presence is None:
        presence = np.empty((count, 0), dtype=bool)
    else:
        presence = np.asarray(categorical_presence)
        if presence.dtype != np.bool_ or presence.ndim != 2 or presence.shape[0] != count:
            raise ValueError("categorical_presence must be a bool array with shape [N, C]")

    supports = tuple(range(3, outer + 1, 2))
    contact_band = np.zeros(count, dtype=np.int64)
    for support in supports:
        start = (outer - support) // 2
        contact = states[:, :, start:start + support, start:start + support].sum(axis=(1, 2, 3)) > 0
        contact_band[(contact_band == 0) & contact] = support
    keys = np.column_stack((targets.astype(np.int64), contact_band,
                            presence.astype(np.int64)))
    signatures, stratum_index = np.unique(keys, axis=0, return_inverse=True)
    grouped_rows = np.argsort(stratum_index, kind="stable")
    boundaries = np.concatenate(([0], np.cumsum(np.bincount(stratum_index))))
    rng = np.random.default_rng(int(seed))
    validation = np.zeros(count, dtype=bool)
    strata = []
    for index, signature in enumerate(signatures):
        rows = grouped_rows[boundaries[index]:boundaries[index + 1]]
        selected = _nearest_weighted_subset(weights[rows], fraction, rng)
        validation[rows] = selected
        total = float(weights[rows].sum(dtype=np.float64))
        selected_weight = float(weights[rows[selected]].sum(dtype=np.float64))
        strata.append({"target": int(signature[0]),
                       "smallest_contact_support": int(signature[1]),
                       "categorical_presence_columns": np.flatnonzero(signature[2:]).tolist(),
                       "rows": len(rows), "training_rows": int((~selected).sum()),
                       "validation_rows": int(selected.sum()),
                       "population_weight": total,
                       "validation_population_weight": selected_weight,
                       "target_validation_population_weight": fraction * total,
                       "validation_mass_share": selected_weight / total,
                       "mass_share_deviation": selected_weight / total - fraction,
                       "singleton_retained_in_training": len(rows) == 1})
    if not validation.any():
        raise ValueError("No stratum contains two rows; categorical coverage permits no validation rows")
    train_presence = presence[~validation].any(axis=0)
    validation_presence = presence[validation].any(axis=0)
    if (validation_presence & ~train_presence).any():
        raise RuntimeError("Validation categorical coverage is not contained in training")

    cohorts = {}
    for name, membership in [("base", np.ones(count, dtype=bool))] + [
            (f"native_{support}", (contact_band > 0) & (contact_band <= support))
            for support in supports]:
        pooled = _population_summary(targets, weights, membership)
        train = _population_summary(targets, weights, membership & ~validation)
        val = _population_summary(targets, weights, membership & validation)
        shares = {field: val[field] / pooled[field] if pooled[field] else None
                  for field in ("positive_weight", "negative_weight", "population_weight")}
        cohorts[name] = {"pooled": pooled, "train": train, "validation": val,
                         "validation_positive_mass_share": shares["positive_weight"],
                         "validation_negative_mass_share": shares["negative_weight"],
                         "validation_population_mass_share": shares["population_weight"],
                         "frequency_difference_validation_minus_training": (
                             val["weighted_frequency"] - train["weighted_frequency"]
                             if val["weighted_frequency"] is not None
                             and train["weighted_frequency"] is not None else None)}
    audit = {"method": "seeded_weighted_row_stratification",
             "exact_weighted_subset_optimization": False,
             "within_stratum_optimizer": "seeded random-row-order greedy; up to 64 improving one-row moves or one-for-one swaps",
             "validation_fraction": fraction, "seed": int(seed),
             "stratification": ["binary target", "smallest current-contact support", "full-patch categorical presence signature"],
             "objective": "Minimize absolute validation-weight deviation from validation_fraction times pooled weight within each stratum, subject to two-sided count guards; heuristic local refinement",
             "inverse_inclusion_weights_unchanged": True,
             "all_pooled_rows_retained": True,
             "test_labels_used": False,
             "test_partition_received": False,
             "rows": count, "training_rows": int((~validation).sum()),
             "validation_rows": int(validation.sum()),
             "stratum_count": len(strata),
             "singleton_stratum_count": sum(row["singleton_retained_in_training"] for row in strata),
             "categorical_presence_column_count": presence.shape[1],
             "training_categorical_presence_columns": np.flatnonzero(train_presence).tolist(),
             "validation_categorical_presence_columns": np.flatnonzero(validation_presence).tolist(),
             "validation_categories_subset_of_training": True,
             "cohorts": cohorts, "strata": strata,
             "limitations": ["Assignment does not keep whole fires in a single partition.",
                             "Nearby cell-hours can occur on opposite sides.",
                             "Unequal indivisible weights and singleton strata can prevent an exact validation fraction.",
                             "Categorical coverage applies to the full-patch presence columns supplied by the caller."]}
    return validation, audit


# Resplit training
# Derive weighted cell-hour training/validation partitions, preserving test bytes.
# 
# Only the old training and validation rows enter the allocation. Full-patch
# categorical indicators are checked on test inputs after allocation; test labels
# never enter split selection. This design allows the same fire in training and
# validation and therefore measures within-fire interpolation, not unseen-fire
# or later-season generalization. Original caches and fitted artifacts are intact.


import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile


FIELDS = ("environment", "burned", "target", "weight", "event_index", "time_utc", "row", "col")
FILES = ("metadata.json", "train.npz", "validation.npz", "test.npz")
IDENTITY_FIELDS = ("event_index", "time_utc", "row", "col")
PARTITIONS = ("train", "validation", "test")


def _resplit_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def categorical_columns(metadata):
    """Return explicit one-hot source/class/input-position records in input order."""
    channels = metadata["channels"]
    info = metadata.get("channel_info", [])
    columns = []
    for index, name in enumerate(channels):
        entry = info[index] if index < len(info) else {}
        if entry.get("categorical") or entry.get("encoding") == "one_hot":
            if entry.get("encoding") != "one_hot":
                raise ValueError("Categorical split support requires one-hot input channels")
            columns.append(dict(index=index, name=name, source_channel=entry.get("source_channel", name),
                                class_code=entry.get("class_code"), class_name=entry.get("class_name")))
    # Older caches may carry the group/vocabulary contract without channel_info.
    if not columns and metadata.get("categorical_classes"):
        for source, classes in metadata["categorical_classes"].items():
            indices = metadata.get("channel_groups", {}).get(source)
            if not isinstance(indices, list) or len(indices) != len(classes):
                raise ValueError(f"Categorical vocabulary/group mismatch for {source}")
            for index, code in zip(indices, classes):
                if type(index) is not int or not 0 <= index < len(channels):
                    raise ValueError("Categorical input index is out of range")
                columns.append(dict(index=index, name=channels[index], source_channel=source,
                                    class_code=code, class_name=None))
        columns.sort(key=lambda entry: entry["index"])
    if len({entry["index"] for entry in columns}) != len(columns):
        raise ValueError("Categorical input positions must be unique")
    return columns


def categorical_presence(environment, metadata, chunk_size=512):
    """Boolean N-by-category presence anywhere in each complete context patch."""
    columns = categorical_columns(metadata)
    result = np.zeros((len(environment), len(columns)), dtype=bool)
    indices = [entry["index"] for entry in columns]
    for start in range(0, len(environment), chunk_size):
        end = min(start + chunk_size, len(environment))
        values = environment[start:end]
        if not np.isfinite(values).all():
            raise ValueError("Prepared environmental patches must be finite")
        if indices:
            categorical = values[:, indices]
            if not np.isin(categorical, (0, 1)).all():
                raise ValueError("Categorical split indicators must be exactly zero or one")
            result[start:end] = (categorical == 1).any(axis=(2, 3))
    if columns:
        groups = {}
        for entry in columns:
            groups.setdefault(entry["source_channel"], []).append(entry["index"])
        for indices in groups.values():
            for start in range(0, len(environment), chunk_size):
                if not (environment[start:start + chunk_size, indices].sum(axis=1) == 1).all():
                    raise ValueError("Each categorical source must have one active class at every patch position")
    return result


def _contact_masks(burned):
    size = burned.shape[-1]
    masks = {"base": np.ones(len(burned), dtype=bool)}
    for support in (3, 5, 7, 9):
        if support <= size:
            start = (size - support) // 2
            context = burned[:, :, start:start + support, start:start + support]
            masks[f"native_{support}x{support}"] = context.sum(axis=(1, 2, 3)) > 0
    if "native_3x3" in masks:
        masks["common_3x3"] = masks["native_3x3"]
    return masks


def partition_summary(target, weight, burned, event_index, mask=None):
    """Exact sample counts and inverse-weighted frequencies for each support."""
    selected = np.ones(len(target), dtype=bool) if mask is None else np.asarray(mask, dtype=bool)
    summaries = {}
    for name, contact in _contact_masks(burned).items():
        keep = selected & contact
        total = float(weight[keep].sum(dtype=np.float64))
        positive = float(np.dot(weight[keep], target[keep]))
        summaries[name] = dict(samples=int(keep.sum()), positives=int(target[keep].sum()),
                               contributing_events=len(np.unique(event_index[keep])),
                               estimated_eligible_cell_hours=total, represented_population_weight=total,
                               positive_population_weight=positive,
                               weighted_prevalence=positive / total if total else None)
    return {**summaries["base"], "frequencies_by_support": summaries}


class _MemoryMaps:
    """Track mappings explicitly so Windows can remove temporary files."""
    def __init__(self):
        self.arrays = []

    def track(self, array):
        self.arrays.append(array)
        return array

    def read(self, path):
        return self.track(np.load(path, mmap_mode="r", allow_pickle=False))

    @staticmethod
    def close(array):
        mapping = getattr(array, "_mmap", None)
        if mapping is not None and not mapping.closed:
            if array.flags.writeable:
                array.flush()
            mapping.close()

    def close_all(self):
        for array in self.arrays:
            self.close(array)
        self.arrays.clear()


def _extract_field(archive, field, work, partition, mapped=None):
    """Stream a compressed .npy member to disk and expose its memory map."""
    path = work / f"{partition}_{field}.npy"
    with zipfile.ZipFile(archive) as bundle:
        expected = [f"{key}.npy" for key in FIELDS]
        if sorted(bundle.namelist()) != sorted(expected):
            raise ValueError(f"{archive.name} must contain exactly the prepared cache fields")
        with bundle.open(f"{field}.npy") as source, path.open("wb") as destination:
            shutil.copyfileobj(source, destination, length=8 * 1024 * 1024)
    result = (np.load(path, mmap_mode="r", allow_pickle=False) if mapped is None else mapped.read(path))
    if result.dtype.hasobject:
        raise ValueError("Prepared cache fields cannot contain Python objects")
    return result


def _load_small(source, work, partition, mapped=None):
    result = {key: _extract_field(source / f"{partition}.npz", key, work, partition, mapped)
              for key in FIELDS if key != "environment"}
    n = len(result["target"])
    if not n:
        raise ValueError(f"Source {partition} partition is empty")
    for key in FIELDS[2:]:
        if result[key].shape != (n,):
            raise ValueError(f"Invalid source {partition} {key} shape")
    if result["weight"].dtype != np.float64 or not np.isfinite(result["weight"]).all() or not (result["weight"] >= 1).all():
        raise ValueError("Source inverse inclusion weights must be finite float64 values at least one")
    if not np.isin(result["target"], (0, 1)).all():
        raise ValueError("Source outcomes must be binary")
    burned = result["burned"]
    if (burned.dtype != np.float32 or burned.ndim != 4 or burned.shape[0] != n
            or burned.shape[1] != 1 or burned.shape[-1] != burned.shape[-2]
            or burned.shape[-1] < 3 or burned.shape[-1] % 2 != 1
            or not np.isin(burned, (0, 1)).all()
            or not (burned[:, 0, burned.shape[-1] // 2, burned.shape[-1] // 2] == 0).all()):
        raise ValueError("Source burned contexts must be complete binary float32 patches with unburned centers")
    for key in IDENTITY_FIELDS:
        if not np.issubdtype(result[key].dtype, np.integer):
            raise ValueError("Source row identity fields must be integers")
    return result


def _identities(data):
    return np.column_stack([data[key] for key in IDENTITY_FIELDS]).astype(np.int64, copy=False)


def _validate_identities(parts, metadata):
    from wildfire.cache import validate_split_metadata
    event_ids = metadata["event_ids"]
    declarations = validate_split_metadata(metadata, require_all_partitions=True)
    identities = []
    for name, data in parts.items():
        indices = data["event_index"]
        if (indices < 0).any() or (indices >= len(event_ids)).any():
            raise ValueError("Source event index is out of range")
        for index in np.unique(indices):
            if name not in declarations[event_ids[int(index)]]:
                raise ValueError("Source event is in an undeclared partition")
        identities.append(_identities(data))
    all_ids = np.concatenate(identities)
    if len(np.unique(all_ids, axis=0)) != len(all_ids):
        raise ValueError("Duplicate cell-hour identities within or across source partitions")
    non_test = np.unique(np.concatenate([parts[name]["event_index"] for name in ("train", "validation")]))
    if np.intersect1d(non_test, np.unique(parts["test"]["event_index"])).size:
        raise ValueError("A test fire also contributes to source training or validation")


def _verify_sources(metadata, root):
    verified = 0
    for item in metadata.get("source_files", []):
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe source manifest path")
        path = (root / relative).resolve()
        if root != path and root not in path.parents:
            raise ValueError("Source manifest escapes data_root")
        if not path.is_file() or _resplit_hash(path) != item["sha256"]:
            raise ValueError(f"Source integrity mismatch: {path}")
        if "bytes" in item and path.stat().st_size != item["bytes"]:
            raise ValueError(f"Source size mismatch: {path}")
        verified += 1
    return verified


def _write_partition_field(bundle, field, sources, masks, dtype, shape):
    with bundle.open(f"{field}.npy", "w", force_zip64=True) as destination:
        np.lib.format.write_array_header_2_0(destination, dict(descr=np.lib.format.dtype_to_descr(dtype),
                                                            fortran_order=False, shape=shape))
        bytes_per_row = max(1, dtype.itemsize * int(np.prod(shape[1:], dtype=np.int64)))
        chunk_rows = max(1, (8 * 1024 * 1024) // bytes_per_row)
        for values, mask in zip(sources, masks):
            for start in range(0, len(values), chunk_rows):
                selected = np.ascontiguousarray(values[start:start + chunk_rows][mask[start:start + chunk_rows]])
                destination.write(selected.tobytes(order="C"))


def resplit_existing_cache(source, output, validation_fraction=.2, seed=7, data_root=None):
    """Atomically create a new weighted row split; never reuse fitted state."""
    
    from wildfire.cache import validate_split_metadata

    if (isinstance(validation_fraction, (bool, np.bool_)) or not np.isscalar(validation_fraction)
            or not np.isfinite(float(validation_fraction)) or not 0 < float(validation_fraction) < 1):
        raise ValueError("validation_fraction must be a finite number strictly between zero and one")
    if not isinstance(seed, (int, np.integer)) or isinstance(seed, (bool, np.bool_)) or seed < 0:
        raise ValueError("seed must be a nonnegative integer")
    validation_fraction, seed = float(validation_fraction), int(seed)
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError("Source and output caches must be separate nonoverlapping directories")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Resplit output must be new or empty; existing files are preserved")
    metadata = json.loads((source / "metadata.json").read_text())
    validate_split_metadata(metadata, require_all_partitions=True)
    if metadata.get("smoke_verification_only"):
        raise ValueError("A smoke verification cache cannot define a new scientific split")
    root = resolve_source_root(metadata, data_root=data_root).resolve()
    source_hashes = {name: _resplit_hash(source / name) for name in FILES}
    verified_sources = _verify_sources(metadata, root)
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".weighted-resplit-", dir=output.parent))
    work = staging / "_work"
    work.mkdir()
    mapped = _MemoryMaps()
    try:
        parts = {name: _load_small(source, work, name, mapped) for name in PARTITIONS}
        _validate_identities(parts, metadata)
        train_count = len(parts["train"]["target"])
        pool = {}
        for field in FIELDS[1:]:
            left, right = parts["train"][field], parts["validation"][field]
            if left.dtype != right.dtype or left.shape[1:] != right.shape[1:]:
                raise ValueError(f"Source training/validation {field} contracts differ")
            destination = np.lib.format.open_memmap(work / f"pooled_{field}.npy", mode="w+", dtype=left.dtype,
                                                   shape=(len(left) + len(right), *left.shape[1:]))
            destination[:len(left)] = left
            destination[len(left):] = right
            pool[field] = mapped.track(destination)
        presence_parts = {}
        support_presence_parts = {}
        for name in PARTITIONS:
            environment = _extract_field(source / f"{name}.npz", "environment", work, name, mapped)
            expected = (len(parts[name]["target"]), len(metadata["channels"]), metadata["kernel_size"], metadata["kernel_size"])
            if environment.dtype != np.float32 or environment.shape != expected:
                raise ValueError(f"Source {name} environment differs from the declared schema")
            presence_parts[name] = categorical_presence(environment, metadata)
            support_presence_parts[name] = {}
            for support in (3, 5, 7, 9):
                if support <= metadata["kernel_size"]:
                    start = (metadata["kernel_size"] - support) // 2
                    support_presence_parts[name][support] = categorical_presence(
                        environment[:, :, start:start + support, start:start + support], metadata)
            mapped.close(environment)
            del environment
        presence = np.concatenate([presence_parts[name] for name in ("train", "validation")])
        support_presence = {support: np.concatenate([support_presence_parts[name][support]
                             for name in ("train", "validation")])
                            for support in support_presence_parts["train"]}
        # Including every cropped support in the categorical signature preserves
        # actual validation category support for each native kernel learner.
        assignment_presence = np.concatenate([support_presence[k] for k in sorted(support_presence)], axis=1)
        validation_mask, audit = weighted_row_assignment(pool["target"], pool["weight"], pool["burned"], assignment_presence,
                                                         validation_fraction=validation_fraction, seed=seed)
        validation_mask = np.asarray(validation_mask)
        if validation_mask.dtype != np.bool_ or validation_mask.shape != (len(pool["target"]),):
            raise ValueError("Weighted assignment must return one boolean per pooled row")
        train_mask = ~validation_mask
        if not validation_mask.any() or not train_mask.any():
            raise ValueError("Weighted allocation must retain nonempty training and validation partitions")
        covered = presence[train_mask].any(axis=0)
        val_present = presence[validation_mask].any(axis=0)
        test_present = presence_parts["test"].any(axis=0)
        columns = categorical_columns(metadata)
        pooled_present = presence.any(axis=0)
        uncovered = np.flatnonzero((pooled_present | test_present) & ~covered)
        if len(uncovered):
            names = [columns[index]["name"] for index in uncovered]
            raise ValueError(f"Validation/test categorical values absent from new training: {names}; test partition is preserved")
        old_train_seen = presence_parts["train"].any(axis=0)
        old_val_seen = presence_parts["validation"].any(axis=0)
        coverage = dict(full_patch=True, columns=columns,
                        original_training_present=[columns[i]["name"] for i in np.flatnonzero(old_train_seen)],
                        original_validation_present=[columns[i]["name"] for i in np.flatnonzero(old_val_seen)],
                        original_validation_unseen_in_training=[columns[i]["name"] for i in np.flatnonzero(old_val_seen & ~old_train_seen)],
                        original_test_unseen_in_training=[columns[i]["name"] for i in np.flatnonzero(test_present & ~old_train_seen)],
                        training_present=[columns[i]["name"] for i in np.flatnonzero(covered)],
                        validation_present=[columns[i]["name"] for i in np.flatnonzero(val_present)],
                        pooled_present=[columns[i]["name"] for i in np.flatnonzero(pooled_present)],
                        test_present=[columns[i]["name"] for i in np.flatnonzero(test_present)],
                        pooled_covered_by_training=True, validation_covered_by_training=True, test_covered_by_training=True,
                        test_labels_used_for_assignment=False, test_features_used_for_assignment=False)
        coverage["assignment_signature_supports"] = sorted(support_presence)
        coverage["assignment_signature_columns"] = [dict(kernel_size=support, **column)
                                                    for support in sorted(support_presence) for column in columns]
        coverage["native_supports"] = {}
        pool_contacts, test_contacts = _contact_masks(pool["burned"]), _contact_masks(parts["test"]["burned"])
        for support, support_values in support_presence.items():
            contact_name = f"native_{support}x{support}"
            native_contact = pool_contacts[contact_name]
            train_seen = support_values[train_mask & native_contact].any(axis=0)
            val_seen = support_values[validation_mask & native_contact].any(axis=0)
            pool_seen = support_values[native_contact].any(axis=0)
            test_seen = support_presence_parts["test"][support][test_contacts[contact_name]].any(axis=0)
            absent = np.flatnonzero((pool_seen | val_seen | test_seen) & ~train_seen)
            old_train_native = support_presence_parts["train"][support][_contact_masks(parts["train"]["burned"])[contact_name]].any(axis=0)
            old_val_native = support_presence_parts["validation"][support][_contact_masks(parts["validation"]["burned"])[contact_name]].any(axis=0)
            entry = dict(original_training_present=[columns[i]["name"] for i in np.flatnonzero(old_train_native)],
                         original_validation_unseen_in_training=[columns[i]["name"] for i in np.flatnonzero(old_val_native & ~old_train_native)],
                         original_test_unseen_in_training=[columns[i]["name"] for i in np.flatnonzero(test_seen & ~old_train_native)],
                         training_present=[columns[i]["name"] for i in np.flatnonzero(train_seen)],
                         pooled_present=[columns[i]["name"] for i in np.flatnonzero(pool_seen)],
                         validation_present=[columns[i]["name"] for i in np.flatnonzero(val_seen)],
                         test_present=[columns[i]["name"] for i in np.flatnonzero(test_seen)],
                         pooled_covered_by_training=not bool(np.any(pool_seen & ~train_seen)),
                         validation_covered_by_training=not bool(np.any(val_seen & ~train_seen)),
                         test_covered_by_training=not bool(np.any(test_seen & ~train_seen)))
            coverage["native_supports"][str(support)] = entry
            if len(absent):
                names = [columns[index]["name"] for index in absent]
                raise ValueError(f"Native {support}x{support} validation/test categorical values absent from training: {names}; fixed test cannot repair this")
        masks = {"train": (train_mask[:train_count], train_mask[train_count:]),
                 "validation": (validation_mask[:train_count], validation_mask[train_count:])}
        with zipfile.ZipFile(staging / "train.npz", "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as train_zip, \
             zipfile.ZipFile(staging / "validation.npz", "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as val_zip:
            for field in FIELDS:
                if field == "environment":
                    fields = [mapped.read(work / f"{name}_{field}.npy")
                              for name in ("train", "validation")]
                else:
                    fields = [parts[name][field] for name in ("train", "validation")]
                if fields[0].dtype != fields[1].dtype or fields[0].shape[1:] != fields[1].shape[1:]:
                    raise ValueError(f"Source {field} contracts differ")
                for name, bundle in (("train", train_zip), ("validation", val_zip)):
                    count = sum(int(mask.sum()) for mask in masks[name])
                    _write_partition_field(bundle, field, fields, masks[name], fields[0].dtype,
                                           (count, *fields[0].shape[1:]))
                if field == "environment":
                    for array in fields:
                        mapped.close(array)
                del fields
        shutil.copyfile(source / "test.npz", staging / "test.npz")
        if _resplit_hash(staging / "test.npz") != source_hashes["test.npz"]:
            raise AssertionError("Copied test archive differs from its frozen source")
        new_metadata = deepcopy(metadata)
        original_splits = deepcopy(metadata.get("original_splits", metadata["splits"]))
        memberships = {}
        for index, event_id in enumerate(metadata["event_ids"]):
            names = [name for name, mask in (("train", train_mask), ("validation", validation_mask))
                     if (pool["event_index"][mask] == index).any()]
            if (parts["test"]["event_index"] == index).any() or "test" in ([metadata["splits"][event_id]]
                    if isinstance(metadata["splits"][event_id], str) else metadata["splits"][event_id]):
                names.append("test")
            memberships[event_id] = names
        summaries = {name: partition_summary(pool["target"], pool["weight"], pool["burned"], pool["event_index"], mask)
                     for name, mask in (("train", train_mask), ("validation", validation_mask))}
        summaries["test"] = partition_summary(parts["test"]["target"], parts["test"]["weight"],
                                                parts["test"]["burned"], parts["test"]["event_index"])
        for name in PARTITIONS:
            summaries[name]["events"] = sum(name in value for value in memberships.values())
        per_event = []
        originals = {entry["id"]: entry for entry in metadata.get("per_event", [])}
        for index, event_id in enumerate(metadata["event_ids"]):
            record = deepcopy(originals.get(event_id, {"id": event_id}))
            record["original_split"] = deepcopy(record.get("split", original_splits[event_id]))
            record["split"] = memberships[event_id]
            record["partition_counts"] = {}
            for name in PARTITIONS:
                values = parts["test"] if name == "test" else pool
                mask = values["event_index"] == index
                if name != "test":
                    mask &= train_mask if name == "train" else validation_mask
                record["partition_counts"][name] = partition_summary(values["target"], values["weight"],
                                                                       values["burned"], values["event_index"], mask)
            per_event.append(record)
        created = datetime.now(timezone.utc).isoformat()
        record = dict(created_at_utc=created, source_directory=str(source), source_cache_sha256=source_hashes,
                      validation_fraction=validation_fraction, split_seed=seed,
                      split_unit="cell_hour", algorithm=audit, categorical_coverage=coverage,
                      original_splits=original_splits, new_splits=memberships, split_summary=summaries,
                      test_archive_sha256=source_hashes["test.npz"], test_archive_preserved_byte_for_byte=True,
                      source_files_verified=verified_sources, rows_and_weights_preserved_exactly=True,
                      row_identity_checked_unique=True, test_labels_used_for_assignment=False,
                      fitted_state_reused=False, training_started=False,
                      generalization_scope="Within-fire cell-hour interpolation; overlapping spatial contexts and fire histories across train/validation")
        new_metadata.update(created_at_utc=created, data_root=str(root), split_unit="cell_hour",
                            splits=memberships, original_splits=original_splits, split_summary=summaries,
                            per_event=per_event, split_policy="Inverse-weighted outcome/contact/full-patch categorical strata; training/validation cell-hours pooled; test fixed",
                            split_seed=seed, validation_fraction=validation_fraction, stratification=audit,
                            categorical_coverage=coverage, parent_prepared_directory=str(source),
                            parent_metadata_sha256=source_hashes["metadata.json"],
                            parent_cache_files=[dict(path=str(source / name), sha256=source_hashes[name]) for name in FILES],
                            generalization_scope=record["generalization_scope"])
        (staging / "metadata.json").write_text(json.dumps(new_metadata, indent=2, allow_nan=False) + "\n")
        # Verify output archive identities and every field in bounded chunks.
        for name in ("train", "validation"):
            for field in FIELDS:
                result = _extract_field(staging / f"{name}.npz", field, work, f"check_{name}", mapped)
                offset = 0
                for old_name, mask in zip(("train", "validation"), masks[name]):
                    values = mapped.read(work / f"{old_name}_{field}.npy")
                    bytes_per_row = max(1, values.dtype.itemsize * int(np.prod(values.shape[1:], dtype=np.int64)))
                    step = max(1, 8 * 1024 * 1024 // bytes_per_row)
                    for start in range(0, len(values), step):
                        expected = values[start:start + step][mask[start:start + step]]
                        if not np.array_equal(result[offset:offset + len(expected)], expected):
                            raise AssertionError(f"Output {name} {field} values changed")
                        offset += len(expected)
                    mapped.close(values)
                    del values
                if offset != len(result):
                    raise AssertionError("Output archive contains extra rows")
                mapped.close(result)
                del result
                (work / f"check_{name}_{field}.npy").unlink()
        if {name: _resplit_hash(source / name) for name in FILES} != source_hashes:
            raise ValueError("Source cache changed while resplitting; staged output rejected")
        record["output_cache_sha256"] = {name: _resplit_hash(staging / name) for name in FILES}
        (staging / "resplit.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
        mapped.close_all()
        pool.clear()
        parts.clear()
        shutil.rmtree(work)
        if output.exists():
            if any(output.iterdir()):
                raise FileExistsError("Output became nonempty while resplitting; existing files are preserved")
            output.rmdir()
        staging.rename(output)
        return record
    except BaseException:
        mapped.close_all()
        shutil.rmtree(staging, ignore_errors=True)
        raise


def resplit_main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--validation-fraction", type=float, default=.2)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--data-root", type=Path, help="Current environmental root; every source manifest hash is verified")
    args = parser.parse_args(argv)
    result = resplit_existing_cache(args.source_dir, args.output_dir, args.validation_fraction, args.seed, args.data_root)
    print(json.dumps({key: result[key] for key in ("split_unit", "split_summary", "categorical_coverage", "test_archive_preserved_byte_for_byte", "training_started")}, indent=2))
    return result




# Prepare training
# Prepare strictly paired one-hour targets with weighted negative sampling.
# 
# All positive targets are retained before environmental validity filtering.
# Negative targets are sampled without replacement within fire/contact strata;
# their inverse inclusion probabilities preserve the cell-hour population loss.
# The raw source rasters are never modified.

from collections import defaultdict
import operator

import pandas as pd
import rasterio
from scipy.ndimage import minimum_filter

from wildfire.data import WildfireSequenceDataset
from wildfire.data import DEFAULT_ROOT
from wildfire.data import load_data
from wildfire.schema import CHANNELS
from wildfire.schema import TRAINING_SOURCE_CHANNELS


def resolve_channel_schema(root, source_channels=TRAINING_SOURCE_CHANNELS):
    """Freeze the loader's expanded inputs and published categorical legend."""
    dataset = WildfireSequenceDataset(root, sequence_length=1, channels=source_channels,
                                      categorical_encoding="one_hot")
    try:
        return dict(
            source_channels=list(dataset.source_channel_names),
            channels=list(dataset.channel_names),
            channel_info=list(dataset.channel_info),
            categorical_encoding="one_hot",
            categorical_classes={name: list(dataset.categorical_classes[name])
                                 for name in dataset.source_channel_names
                                 if name in dataset.categorical_classes},
            channel_groups={name: list(indices) for name, indices in dataset.channel_groups.items()},
        )
    finally:
        dataset.close()


def season_split(event):
    season = (event["country"], event["year"])
    if season in (("KR", 2022), ("US", 2020), ("US", 2021)):
        return "train"
    if season in (("KR", 2023), ("US", 2022)):
        return "validation"
    if season in (("KR", 2025), ("US", 2024)):
        return "test"
    raise ValueError(f"No predetermined split for {season}")


def sample_segments(lengths, starts, limit, rng):
    """Uniform distinct indices from disjoint integer time segments per cell."""
    lengths = np.asarray(lengths, dtype=np.int64)
    cumulative = np.cumsum(lengths)
    total = int(cumulative[-1]) if len(cumulative) else 0
    count = min(limit, total)
    if not count:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64), np.empty(0), total
    draws = np.sort(rng.choice(total, size=count, replace=False))
    cells = np.searchsorted(cumulative, draws, side="right")
    prior = np.concatenate(([0], cumulative[:-1]))
    times = starts[cells] + draws - prior[cells]
    weights = np.full(count, total / count, dtype=np.float64)
    return cells, times, weights, total


def _prepare_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _patches(array, rows, cols, radius=1):
    windows = np.lib.stride_tricks.sliding_window_view(array, (2 * radius + 1,) * 2, axis=(-2, -1))
    return windows[:, rows - radius, cols - radius].transpose(1, 0, 2, 3).copy()


def _chunk_hours(value):
    if value is None:
        return None
    if isinstance(value, (bool, np.bool_)):
        raise ValueError("chunk_hours must be a positive integer or None")
    try:
        result = operator.index(value)
    except TypeError as error:
        raise ValueError("chunk_hours must be a positive integer or None") from error
    if result < 1:
        raise ValueError("chunk_hours must be a positive integer or None")
    return result


def prepare_event(root, event, event_index, rng, contact_limit, no_contact_limit, chunk_hours=None,
                  *, source_channels=None, categorical_classes=None, channel_names=None, kernel_size=3):
    """Extract weighted next-hour rows from an event's complete selected timeline.

    chunk_hours=None loads that entire timeline once. A positive integer reads
    bounded windows while retaining identical sampled rows, targets, and weights.
    """
    chunk_hours = _chunk_hours(chunk_hours)
    if type(kernel_size) is not int or kernel_size < 3 or kernel_size % 2 != 1:
        raise ValueError("kernel_size must be an odd integer at least three")
    radius = kernel_size // 2
    with rasterio.open(root / event["arrival_path"]) as source:
        arrival = source.read(1, masked=True).filled(np.nan).astype(np.float32)
        metric_grid = source.crs.is_projected and source.crs.linear_units in ("metre", "meter")
        spacing = [abs(source.transform.a), abs(source.transform.e)] if metric_grid and source.transform.b == source.transform.d == 0 else None
    finite = np.isfinite(arrival)
    neighborhood_known = minimum_filter(finite.astype("uint8"), size=kernel_size, mode="constant", cval=0) > 0
    offsets = np.ones((kernel_size, kernel_size), dtype=bool)
    offsets[radius, radius] = False
    neighbor_arrival = minimum_filter(
        np.where(finite, arrival, np.inf), footprint=offsets, mode="constant", cval=np.inf,
    )
    start = pd.Timestamp(event["start_utc"])
    end = pd.Timestamp(event["end_utc"])
    origin = pd.Timestamp(event["t0_utc"])
    hours = int((end - start).total_seconds() // 3600)
    elapsed = (start - origin).total_seconds() / 3600 + np.arange(hours + 1, dtype=np.float64)
    # First burned snapshot index. Match the loader's float64 elapsed values
    # rather than rounding fractional event origins to the arrival dtype.
    first_burn = np.searchsorted(elapsed, arrival, side="left")
    risk_lengths = np.minimum(first_burn, hours)
    raw_risk = int(risk_lengths[finite].sum())
    cells_flat = np.flatnonzero(neighborhood_known)
    a = arrival.ravel()[cells_flat]
    first = first_burn.ravel()[cells_flat]
    risk = risk_lengths.ravel()[cells_flat]
    positive = (first >= 1) & (first <= hours)
    negative_lengths = risk - positive.astype(np.int64)
    contact_start = np.searchsorted(elapsed[:-1], neighbor_arrival.ravel()[cells_flat], side="left")
    no_contact_lengths = np.minimum(contact_start, negative_lengths)
    contact_lengths = negative_lengths - no_contact_lengths
    pos_cells = np.flatnonzero(positive)
    cell_lists = [pos_cells]
    time_lists = [first[pos_cells] - 1]
    weight_lists = [np.ones(len(pos_cells), dtype=np.float64)]
    contact_cells, contact_times, contact_weights, contact_population = sample_segments(
        contact_lengths, no_contact_lengths, contact_limit, rng,
    )
    cold_cells, cold_times, cold_weights, cold_population = sample_segments(
        no_contact_lengths, np.zeros_like(no_contact_lengths), no_contact_limit, rng,
    )
    cell_lists.extend((contact_cells, cold_cells))
    time_lists.extend((contact_times, cold_times))
    weight_lists.extend((contact_weights, cold_weights))
    chosen = np.concatenate(cell_lists)
    indices = np.concatenate(time_lists).astype(np.int64)
    weights = np.concatenate(weight_lists)
    expected_target = np.concatenate((np.ones(len(pos_cells)), np.zeros(len(contact_cells) + len(cold_cells))))
    absolute = cells_flat[chosen]
    rows, cols = np.unravel_index(absolute, arrival.shape)
    order = np.argsort(indices, kind="stable")
    indices, rows, cols = indices[order], rows[order], cols[order]
    weights, expected_target = weights[order], expected_target[order]
    storage = defaultdict(list)
    unknown_environment = 0
    files = [root / event["arrival_path"]]
    dataset = load_data(
        root, events=[event["id"]], sequence_length=chunk_hours, temporal_stride=chunk_hours,
        patch_size=None, channels=CHANNELS if source_channels is None else source_channels,
        categorical_encoding="one_hot", categorical_classes=categorical_classes,
    )
    try:
        state = dataset._events[0]
        if channel_names is not None and tuple(channel_names) != dataset.channel_names:
            raise ValueError("Expanded event channels differ from the frozen training schema")
        files.extend(state["layers"][name].path for name in dataset.source_channel_names)
        for model in state["hourly_times"]:
            files.append(root / "regions" / event["id"] / "weather" / f"{model}_bands.csv")
            files.append(root / "regions" / event["id"] / "weather" / f"{model}_complete.json")
        block_hours = hours + 1 if chunk_hours is None else chunk_hours
        blocks = np.unique(indices // block_hours)
        for block in blocks:
            sample = dataset[int(block)]
            features = sample["features"].numpy()
            feature_valid = sample["feature_valid"].numpy()
            burned = sample["burned_area"].numpy()
            label_valid = sample["burned_area_valid"].numpy()
            selected = np.flatnonzero(indices // block_hours == block)
            for hour in np.unique(indices[selected]):
                positions = selected[indices[selected] == hour]
                local = int(hour % block_hours)
                rr, cc = rows[positions], cols[positions]
                assert bool(sample["time_valid"][local])
                current_utc = int(sample["time_utc"][local])
                expected_utc = int(start.timestamp()) + int(hour) * 3600
                assert current_utc == expected_utc and current_utc + 3600 <= int(end.timestamp())
                dynamic_ends = sample["source_interval_end_utc"][local]
                assert bool(((dynamic_ends <= current_utc) | (dynamic_ends == -1)).all())
                valid_context = _patches(feature_valid[local], rr, cc, radius).all(axis=(1, 2, 3))
                valid_burned = _patches(label_valid[local], rr, cc, radius).all(axis=(1, 2, 3))
                current_patch = _patches(burned[local], rr, cc, radius)
                next_state = (arrival[rr, cc].astype(np.float64) <= elapsed[int(hour) + 1]).astype(np.float32)
                assert (current_patch[:, 0, radius, radius] == 0).all()
                assert valid_burned.all()
                assert np.array_equal(next_state, expected_target[positions])
                unknown_environment += int((~valid_context).sum())
                keep = positions[valid_context]
                if not len(keep):
                    continue
                storage["environment"].append(_patches(features[local], rr, cc, radius)[valid_context])
                storage["burned"].append(current_patch[valid_context])
                storage["target"].append(next_state[valid_context])
                storage["weight"].append(weights[keep])
                storage["event_index"].append(np.full(len(keep), event_index, dtype=np.int64))
                storage["time_utc"].append(np.full(len(keep), current_utc, dtype=np.int64))
                storage["row"].append(rows[keep].astype(np.int32))
                storage["col"].append(cols[keep].astype(np.int32))
    finally:
        dataset.close()
    arrays = {name: np.concatenate(values) for name, values in storage.items()}
    count = len(arrays.get("target", []))
    audit = dict(
        id=event["id"], name=event["name"], country=event["country"], year=event["year"],
        grid_pixel_size_m=spacing,
        split=season_split(event), hourly_intervals=hours,
        label_known_unburned_cell_hours=raw_risk,
        burned_context_known_unburned_cell_hours=int(risk.sum()),
        positive_targets_before_environment_filter=int(positive.sum()),
        no_contact_positive_targets_before_environment_filter=int((positive & (contact_start > first - 1)).sum()),
        contact_negative_population=contact_population, no_contact_negative_population=cold_population,
        candidate_samples=len(chosen), environmental_context_rejections=unknown_environment,
        accepted_samples=count,
        accepted_positives=int(arrays["target"].sum()) if count else 0,
        accepted_no_contact_positives=int(((arrays["target"] == 1) & (arrays["burned"].sum(axis=(1, 2, 3)) == 0)).sum()) if count else 0,
        estimated_environment_valid_cell_hours=float(arrays["weight"].sum()) if count else 0,
        exclusion=f"No eligible full {kernel_size}x{kernel_size} context / next-hour at-risk target" if not count else None,
    )
    return arrays, audit, files


def prepare_season_cache(args):
    """Extract the original weighted rows with the historical season mapping.

    The weighted split is applied afterwards, so a different split seed never
    changes the selected negative examples, labels, or inclusion weights.
    """
    chunk_hours = _chunk_hours(getattr(args, "chunk_hours", None))
    if args.kernel_size < 3 or args.kernel_size % 2 != 1:
        raise ValueError("kernel_size must be an odd integer at least three")
    if args.contact_negatives_per_event <= 0 or args.no_contact_negatives_per_event <= 0:
        raise ValueError("Negative sampling limits must be positive")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise FileExistsError("Prepared output directory is not empty; choose a new directory")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    root = args.data_root.resolve()
    catalog = json.loads((root / "events.json").read_text())
    schema = resolve_channel_schema(root, args.channels)
    rng = np.random.default_rng(args.seed)
    splits = defaultdict(lambda: defaultdict(list))
    per_event, source_files = [], {root / "events.json"}
    if "biome.biome_class" in schema["source_channels"]:
        source_files.add(root / "biome_classes.json")
    for index, event in enumerate(catalog):
        arrays, audit, files = prepare_event(
            root, event, index, rng, args.contact_negatives_per_event, args.no_contact_negatives_per_event,
            source_channels=schema["source_channels"], categorical_classes=schema["categorical_classes"],
            channel_names=schema["channels"],
            kernel_size=args.kernel_size, chunk_hours=chunk_hours,
        )
        per_event.append(audit)
        source_files.update(files)
        for name, value in arrays.items():
            splits[audit["split"]][name].append(value)
        print(json.dumps(audit), flush=True)
    split_summary = {}
    for partition in ("train", "validation", "test"):
        arrays = {name: np.concatenate(values) for name, values in splits[partition].items()}
        np.savez_compressed(args.output_dir / f"{partition}.npz", **arrays)
        split_summary[partition] = dict(
            events=sum(season_split(event) == partition for event in catalog),
            samples=len(arrays["target"]), positives=int(arrays["target"].sum()),
            estimated_eligible_cell_hours=float(arrays["weight"].sum()),
        )
    manifest = []
    for path in sorted(source_files):
        manifest.append(dict(path=str(path.relative_to(root)), bytes=path.stat().st_size, sha256=_prepare_hash(path)))
    metadata = dict(
        created_at_utc=datetime.now(timezone.utc).isoformat(), data_root=str(root),
        **schema, kernel_size=args.kernel_size, dt_hours=1.0, seed=args.seed,
        data_loading=dict(mode="full_event_timeline" if chunk_hours is None else "time_windows",
                          chunk_hours=chunk_hours),
        evaluation_grouping="pooled_countries",
        event_ids=[event["id"] for event in catalog],
        splits={event["id"]: season_split(event) for event in catalog},
        split_unit="whole_fire",
        split_policy="Whole country-year seasons, fixed before fitting or test evaluation",
        split_summary=split_summary, per_event=per_event, source_files=manifest,
        sampling=dict(
            all_positives=True, negatives="Uniform without replacement within event and contact stratum",
            contact_limit=args.contact_negatives_per_event, no_contact_limit=args.no_contact_negatives_per_event,
            weights="Inverse candidate inclusion probability N_stratum/n_sampled; no refill after validity filtering",
            metric_scope="All eligible reconstructed targets; negative-population metrics estimated by sampling weights",
        ),
        label_interpretation="Retrospective reconstructed hourly burned states inside final perimeter; not observed hourly ground truth",
        target="Currently unburned at t becomes burned at t+3600 seconds, using current t environmental context",
    )
    spacings = [event["grid_pixel_size_m"] for event in per_event]
    if all(spacing == spacings[0] for spacing in spacings) and spacings[0] is not None and spacings[0][0] == spacings[0][1]:
        metadata["grid_resolution_m"] = spacings[0][0]
    (args.output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(split_summary, indent=2), flush=True)


def _preparation_integer(value, name, minimum):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be an integer at least {minimum}")
    try:
        result = operator.index(value)
    except TypeError as error:
        raise ValueError(f"{name} must be an integer at least {minimum}") from error
    if result < minimum:
        raise ValueError(f"{name} must be an integer at least {minimum}")
    return result


def _prepare_training_data(args):
    """Shared preparation implementation for Python and the command line."""
    if args.split_policy not in ("weighted-cell-hour", "season"):
        raise ValueError("split_policy must be weighted-cell-hour or season")
    try:
        valid_fraction = np.isfinite(args.validation_fraction) and 0 < args.validation_fraction < 1
    except (TypeError, ValueError) as error:
        raise ValueError("validation_fraction must be finite and strictly between zero and one") from error
    if not valid_fraction:
        raise ValueError("validation_fraction must be finite and strictly between zero and one")
    for name, minimum in (("seed", 0), ("split_seed", 0), ("kernel_size", 3),
                          ("contact_negatives_per_event", 1), ("no_contact_negatives_per_event", 1)):
        setattr(args, name, _preparation_integer(getattr(args, name), name, minimum))
    if args.kernel_size % 2 != 1:
        raise ValueError("kernel_size must be an odd integer at least three")
    args.chunk_hours = _chunk_hours(getattr(args, "chunk_hours", None))
    if args.split_policy == "season":
        prepare_season_cache(args)
        return args.output_dir.resolve()
    destination = args.output_dir.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("Prepared output directory is not empty; choose a new directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    

    with tempfile.TemporaryDirectory(prefix=".prepare-season-", dir=destination.parent) as temporary:
        extraction = argparse.Namespace(**vars(args))
        extraction.output_dir = Path(temporary)
        prepare_season_cache(extraction)
        parent_metadata = (extraction.output_dir / "metadata.json").read_text()
        record = resplit_existing_cache(
            extraction.output_dir, destination, validation_fraction=args.validation_fraction,
            seed=args.split_seed, data_root=args.data_root,
        )
        # Retain the complete extraction metadata even though its temporary
        # array files are removed: the final train/validation union contains
        # exactly those original rows, and the original test bytes are copied.
        parent_name = "preparation_season_parent_metadata.json"
        (destination / parent_name).write_text(parent_metadata)
        metadata_path = destination / "metadata.json"
        metadata = json.loads(metadata_path.read_text())
        metadata["fresh_preparation"] = dict(
            negative_sampling_seed=args.seed, split_seed=args.split_seed,
            parent_metadata_file=parent_name,
            parent_metadata_sha256=_prepare_hash(destination / parent_name),
            temporary_parent_array_files_retained=False,
        )
        metadata["parent_prepared_cache_retained"] = False
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
        record["fresh_preparation"] = metadata["fresh_preparation"]
        record["source_directory_retained"] = False
        record["output_cache_sha256"]["metadata.json"] = _prepare_hash(metadata_path)
        (destination / "resplit.json").write_text(json.dumps(record, indent=2, allow_nan=False) + "\n")
        print(json.dumps(record, indent=2), flush=True)
    return destination


def prepare_training_data(
    output_dir: str | Path, *, data_root: str | Path = DEFAULT_ROOT,
    channels=TRAINING_SOURCE_CHANNELS, kernel_size: int = 3,
    contact_negatives_per_event: int = 5000, no_contact_negatives_per_event: int = 2000,
    seed: int = 7, split_policy: str = "weighted-cell-hour",
    validation_fraction: float = .2, split_seed: int = 7,
    chunk_hours: int | None = None,
) -> Path:
    """Prepare a training cache from independent event data without a model.

    Return the resolved output directory containing train.npz, validation.npz,
    test.npz, and metadata.json. By default event data is loaded as complete
    timelines; chunk_hours selects bounded reads without changing sampled
    targets or inclusion weights. The weighted-cell-hour policy repartitions
    the original training/validation pool while preserving test archive bytes.
    The season policy retains the historical whole-season partitions. Negative
    sampling uses seed; the independent training/validation split uses
    split_seed. An existing nonempty output directory is rejected.
    """
    if isinstance(channels, (str, bytes)):
        raise ValueError("channels must be an ordered sequence of source field names")
    try:
        source_channels = tuple(channels)
    except TypeError as error:
        raise ValueError("channels must be an ordered sequence of source field names") from error
    if (not source_channels or any(not isinstance(name, str) or not name for name in source_channels)
            or len(set(source_channels)) != len(source_channels)):
        raise ValueError("channels must contain distinct nonempty source field names")
    args = argparse.Namespace(
        output_dir=Path(output_dir).expanduser(), data_root=Path(data_root).expanduser(),
        channels=source_channels, kernel_size=kernel_size,
        contact_negatives_per_event=contact_negatives_per_event,
        no_contact_negatives_per_event=no_contact_negatives_per_event,
        seed=seed, split_policy=split_policy, validation_fraction=validation_fraction,
        split_seed=split_seed, chunk_hours=chunk_hours,
    )
    return _prepare_training_data(args)


def prepare_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--contact-negatives-per-event", type=int, default=5000)
    parser.add_argument("--no-contact-negatives-per-event", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=7, help="Negative-sampling seed")
    parser.add_argument("--kernel-size", type=int, default=3)
    parser.add_argument("--channels", nargs="+", default=TRAINING_SOURCE_CHANNELS,
                        help="Ordered source fields; categorical fields expand into complete one-hot groups")
    parser.add_argument("--chunk-hours", type=int, default=None,
                        help="Positive time-window length for bounded reads; omitted loads each complete event timeline")
    parser.add_argument("--split-policy", choices=("weighted-cell-hour", "season"),
                        default="weighted-cell-hour",
                        help="Weighted stratified train/validation rows (default), or historical whole-season split")
    parser.add_argument("--validation-fraction", type=float, default=0.2,
                        help="Target validation share of weighted positive and negative population (default: 0.2)")
    parser.add_argument("--split-seed", type=int, default=7,
                        help="Split seed, independent of negative sampling (default: 7)")
    args = parser.parse_args()
    if not np.isfinite(args.validation_fraction) or not 0 < args.validation_fraction < 1:
        parser.error("--validation-fraction must be strictly between zero and one")
    if args.split_seed < 0:
        parser.error("--split-seed must be nonnegative")
    if args.chunk_hours is not None and args.chunk_hours < 1:
        parser.error("--chunk-hours must be a positive integer")
    return _prepare_training_data(args)




# Filter contact
# Exclude no-burned-neighbor targets from every prepared partition.



from wildfire.cache import validate_split_metadata


def filter_contact(source: Path, output: Path):
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Contact-only output is not empty; choose a new directory")
    source_metadata = source / "metadata.json"
    metadata = json.loads(source_metadata.read_text())
    memberships = validate_split_metadata(metadata)
    kernel_size = metadata["kernel_size"]
    if type(kernel_size) is not int or kernel_size < 3 or kernel_size % 2 != 1:
        raise ValueError("kernel_size must be an odd integer at least three")
    radius = kernel_size // 2
    output.mkdir(parents=True, exist_ok=True)
    summaries, event_counts, parent_files = {}, {}, []
    for split in ("train", "validation", "test"):
        path = source / f"{split}.npz"
        with np.load(path, allow_pickle=False) as archive:
            arrays = {key: archive[key] for key in archive.files}
        if arrays["burned"].shape[1:] != (1, kernel_size, kernel_size):
            raise ValueError("Burned patch shape differs from the kernel metadata")
        if not (arrays["burned"][:, 0, radius, radius] == 0).all():
            raise ValueError("Expected currently unburned target centers")
        counts = arrays["burned"].sum(axis=(1, 2, 3))
        keep = counts > 0
        excluded_positives = int(arrays["target"][~keep].sum())
        filtered = {key: value[keep] for key, value in arrays.items()}
        assert (filtered["burned"].sum(axis=(1, 2, 3)) > 0).all()
        np.savez_compressed(output / f"{split}.npz", **filtered)
        summaries[split] = dict(
            events=sum(split in value for value in memberships.values()),
            contributing_events=len(np.unique(filtered["event_index"])),
            samples=int(keep.sum()), positives=int(filtered["target"].sum()),
            estimated_eligible_cell_hours=float(filtered["weight"].sum()),
            excluded_no_contact_samples=int((~keep).sum()),
            excluded_no_contact_positives=excluded_positives,
        )
        for index in np.unique(arrays["event_index"]):
            before = arrays["event_index"] == index
            after = filtered["event_index"] == index
            counts_for_split = dict(
                unfiltered_accepted_samples=int(before.sum()),
                excluded_no_contact_samples=int((before & ~keep).sum()),
                excluded_no_contact_positives=int(arrays["target"][before & ~keep].sum()),
                accepted_samples=int(after.sum()), accepted_positives=int(filtered["target"][after].sum()),
                accepted_no_contact_positives=0,
                estimated_environment_valid_cell_hours=float(filtered["weight"][after].sum()),
            )
            event_id = metadata["event_ids"][int(index)]
            total = event_counts.setdefault(event_id, {key: 0 for key in counts_for_split})
            for key, value in counts_for_split.items():
                total[key] += value
        parent_files.append(dict(path=str(path.resolve()), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    for event in metadata["per_event"]:
        event.update(event_counts.get(event["id"], {}))
        if event["accepted_samples"] == 0 and event.get("exclusion") is None:
            event["exclusion"] = f"No targets with a previously burned neighbor within the {kernel_size}x{kernel_size} kernel"
    metadata.update(
        created_at_utc=datetime.now(timezone.utc).isoformat(), split_summary=summaries,
        eligibility="at_least_one_burned_neighbor",
        population_condition=f"Known currently unburned target with complete context and at least one burned neighbor inside the {kernel_size}x{kernel_size} kernel",
        parent_prepared_directory=str(source.resolve()),
        parent_metadata_sha256=hashlib.sha256(source_metadata.read_bytes()).hexdigest(),
        parent_cache_files=parent_files,
    )
    metadata["sampling"]["metric_scope"] = "Contact-conditioned eligible targets; inverse-inclusion weighted estimates"
    metadata["sampling"]["contact_filter_weights"] = "Original inverse inclusion weights retained exactly, with no class or prevalence reweighting"
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(summaries, indent=2), flush=True)
    return metadata


def contact_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    filter_contact(args.source_dir, args.output_dir)




# Subset country
# Partition a prepared contact-only cache by country without resampling.
# 
# Original partition memberships, raw features, labels, and inverse
# inclusion weights are retained. Event indices are remapped to the country's
# ordered event list. Parent checksums retain the complete provenance chain.




from wildfire.cache import SPLIT_NAMES
from wildfire.cache import load_split


def subset_country(source: Path, output: Path, country: str) -> dict:
    """Write country-only partitions; fail for invalid or empty partitions."""
    source, output = Path(source).resolve(), Path(output).resolve()
    if country not in ("KR", "US"):
        raise ValueError("country must be KR or US")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Country output is not empty; choose a new directory")
    metadata_path = source / "metadata.json"
    original = json.loads(metadata_path.read_text(encoding="utf-8"))
    memberships = validate_split_metadata(original)
    if original.get("eligibility") != "at_least_one_burned_neighbor":
        raise ValueError("Country experiments require the contact-only source cache")
    events = original["per_event"]
    records = {event["id"]: event for event in events}
    original_ids = original["event_ids"]
    if len(records) != len(events) or set(records) != set(original_ids):
        raise ValueError("The source must identify every event and country exactly once")
    selected_ids = [event_id for event_id in original_ids if records[event_id]["country"] == country]
    if not selected_ids:
        raise ValueError(f"No {country} events in the source cache")
    mapping = np.full(len(original_ids), -1, dtype=np.int64)
    for new_index, event_id in enumerate(selected_ids):
        mapping[original_ids.index(event_id)] = new_index
    # Validate all partitions before writing any artifacts.
    partitions, summaries, parent_files = {}, {}, []
    for split in SPLIT_NAMES:
        data = load_split(source, split, original)
        keep = mapping[data.event_index] >= 0
        if not keep.any():
            raise ValueError(f"No eligible {country} targets in {split}")
        arrays = {key: getattr(data, key)[keep].copy() for key in data.__dataclass_fields__}
        arrays["event_index"] = mapping[data.event_index[keep]].astype(data.event_index.dtype)
        partitions[split] = arrays
        split_events = [records[event_id] for event_id in selected_ids if split in memberships[event_id]]
        if any(split not in ([event["split"]] if isinstance(event["split"], str) else event["split"])
               for event in split_events):
            raise ValueError("Source per-event split assignments are inconsistent")
        summaries[split] = dict(
            events=len(split_events), contributing_events=len(np.unique(arrays["event_index"])),
            samples=len(arrays["target"]), positives=int(arrays["target"].sum()),
            estimated_eligible_cell_hours=float(arrays["weight"].sum(dtype=np.float64)),
            excluded_no_contact_samples=sum(event.get("excluded_no_contact_samples", 0) for event in split_events),
            excluded_no_contact_positives=sum(event.get("excluded_no_contact_positives", 0) for event in split_events),
            excluded_other_country_samples=int((~keep).sum()),
        )
        cache_path = source / f"{split}.npz"
        parent_files.append(dict(path=str(cache_path), sha256=hashlib.sha256(cache_path.read_bytes()).hexdigest()))
    metadata = deepcopy(original)
    metadata.update(
        created_at_utc=datetime.now(timezone.utc).isoformat(), country=country,
        event_ids=selected_ids, splits={event_id: original["splits"][event_id] for event_id in selected_ids},
        per_event=[deepcopy(records[event_id]) for event_id in selected_ids], split_summary=summaries,
        split_policy=original.get("split_policy", "Original assignments retained") + "; restricted to " + country,
        parent_prepared_directory=str(source),
        parent_metadata_sha256=hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        parent_cache_files=parent_files,
        country_selection=dict(
            rule="Select events by per_event.country in every partition without resampling or reweighting",
            country=country, original_event_ids=original_ids,
            event_index_mapping={str(original_ids.index(event_id)): index for index, event_id in enumerate(selected_ids)},
            source_manifest_scope="Selected event files plus shared events.json; full parent manifest remains in parent metadata",
        ),
    )
    if "original_splits" in metadata:
        metadata["original_splits"] = {event_id: original["original_splits"][event_id] for event_id in selected_ids}
    # A selected cache uses only its country-specific rasters and shared catalog.
    metadata["source_files"] = [item for item in original.get("source_files", [])
                                if item["path"] == "events.json" or any(
                                    item["path"].startswith(f"regions/{event_id}/") for event_id in selected_ids)]
    output.mkdir(parents=True, exist_ok=True)
    for split, arrays in partitions.items():
        np.savez_compressed(output / f"{split}.npz", **arrays)
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"country": country, "split_summary": summaries}, indent=2), flush=True)
    return metadata


def country_main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--country", choices=("KR", "US"), required=True)
    args = parser.parse_args()
    subset_country(args.source_dir, args.output_dir, args.country)


