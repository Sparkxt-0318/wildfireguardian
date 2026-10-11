"""Cohort operations for the wildfire workspace."""
from __future__ import annotations



# Kernel cohort
# Current-state contact cohorts for kernel learning and comparison.
# 
# The frozen largest cache provides identities, outcomes, and inverse inclusion
# weights. Native K evaluation retains known, currently unburned centers with at
# least one known burned off-center source inside the centered K by K crop. A
# matched comparison additionally requires contact inside the smallest support
# and complete largest context. Membership never uses next-hour target labels.
# 
# These helpers select evaluation rows; they do not restrict model prediction.
# Complete no-contact patches must remain acceptable prediction inputs. Masks
# mark unknown cells explicitly: unknown is never treated as unburned.


from typing import Any, Mapping, Sequence

import numpy as np

from wildfire.cache import CachedSplit
from wildfire.metrics import probability_metrics

IDENTITY_KEYS = ("event_index", "time_utc", "row", "col")


def centered_slice(outer: int, inner: int) -> slice:
    """Return the centered crop of odd support ``inner`` in odd ``outer``."""
    if (type(outer) is not int or type(inner) is not int or outer < 3
            or inner < 3 or outer % 2 != 1 or inner % 2 != 1 or inner > outer):
        raise ValueError("Centered contexts require odd integers with 3 <= inner <= outer")
    start = (outer - inner) // 2
    return slice(start, start + inner)


def _burned_context(burned: np.ndarray, kernel_size: int,
                    burned_valid: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(burned)
    if values.ndim != 4 or values.shape[1] != 1 or values.shape[2] != values.shape[3]:
        raise ValueError("burned must have shape [N, 1, K, K] with square odd support")
    crop = centered_slice(int(values.shape[-1]), kernel_size)
    known = np.isfinite(values)
    if burned_valid is not None:
        validity = np.asarray(burned_valid)
        if validity.dtype != np.bool_ or validity.shape != values.shape:
            raise ValueError("burned_valid must be a bool array matching burned shape")
        known &= validity
    if not np.isin(values[known], (0, 1)).all():
        raise ValueError("Known burned states must be exactly zero or one")
    return values[:, :, crop, crop], known[:, :, crop, crop]


def kernel_neighbor_count(burned: np.ndarray, kernel_size: int,
                          burned_valid: np.ndarray | None = None) -> np.ndarray:
    """Count known off-center burned sources; this alone is not eligibility.

    An incomplete patch can have positive known contact and still be excluded
    by :func:`kernel_contact_mask`. The count excludes the center even if it is
    already burned, so it cannot make itself eligible.
    """
    values, known = _burned_context(burned, kernel_size, burned_valid)
    positive = known & (values == 1)
    center = kernel_size // 2
    return (positive.sum(axis=(1, 2, 3), dtype=np.int64)
            - positive[:, 0, center, center].astype(np.int64))


def kernel_contact_mask(burned: np.ndarray, kernel_size: int,
                        burned_valid: np.ndarray | None = None) -> np.ndarray:
    """Return label-free current-state eligibility for one kernel footprint.

    Every source cell in the K by K patch must be known, the center must be
    known and unburned, and an off-center cell must already be burned. Missing
    values outside the chosen centered crop do not affect native K membership.
    """
    values, known = _burned_context(burned, kernel_size, burned_valid)
    center = kernel_size // 2
    unburned_center = known[:, 0, center, center] & (values[:, 0, center, center] == 0)
    positive = known & (values == 1)
    count = (positive.sum(axis=(1, 2, 3), dtype=np.int64)
             - positive[:, 0, center, center].astype(np.int64))
    return known.all(axis=(1, 2, 3)) & unburned_center & (count > 0)


def _environment_complete(data: CachedSplit, kernel_size: int) -> np.ndarray:
    if (data.environment.ndim != 4 or data.environment.shape[0] != len(data)
            or data.environment.shape[-2:] != data.burned.shape[-2:]):
        raise ValueError("Environmental and burned patch shapes must align")
    crop = centered_slice(int(data.environment.shape[-1]), kernel_size)
    complete = np.empty(len(data), dtype=bool)
    # Bound the temporary mask even for wide one-hot input contracts.
    for start in range(0, len(data), 512):
        end = min(start + 512, len(data))
        complete[start:end] = np.isfinite(data.environment[start:end, :, crop, crop]).all(axis=(1, 2, 3))
    return complete


def native_indices(data: CachedSplit, kernel_size: int) -> np.ndarray:
    """Indices of complete current-contact targets within model support K."""
    return np.flatnonzero(kernel_contact_mask(data.burned, kernel_size)
                         & _environment_complete(data, kernel_size))


def common_indices(data: CachedSplit, kernel_sizes: Sequence[int] = (3, 5, 7, 9)) -> np.ndarray:
    """Matched identities from one base cache, using smallest-support contact.

    All compared models receive the same next-hour outcomes and original base
    weights. This is a subset of one sampling design, never an intersection of
    independently sampled kernel caches.
    """
    sizes = tuple(kernel_sizes)
    if not sizes or len(set(sizes)) != len(sizes):
        raise ValueError("kernel_sizes must contain distinct odd supports")
    outer = int(data.burned.shape[-1])
    for size in sizes:
        centered_slice(outer, size)
    complete_base = _environment_complete(data, outer)
    # Requiring largest known current-state context preserves unknown masks
    # when a caller constructs CachedSplit directly rather than load_split().
    _, known = _burned_context(data.burned, outer)
    complete_base &= known.all(axis=(1, 2, 3))
    return np.flatnonzero(complete_base & kernel_contact_mask(data.burned, min(sizes)))


def _indices(data: CachedSplit, indices: np.ndarray | None) -> np.ndarray:
    selected = np.arange(len(data), dtype=np.int64) if indices is None else np.asarray(indices)
    if (selected.ndim != 1 or not np.issubdtype(selected.dtype, np.integer)
            or (selected < 0).any() or (selected >= len(data)).any()):
        raise ValueError("indices must be one-dimensional in-range integers")
    if len(np.unique(selected)) != len(selected):
        raise ValueError("Duplicate base-cache row indices would duplicate population weights")
    return selected


def crop_split(data: CachedSplit, kernel_size: int,
               indices: np.ndarray | None = None) -> CachedSplit:
    """Crop spatial inputs while preserving labels, weights, and identities.

    No contact filtering occurs unless the caller passes selected indices.
    In particular, inference can use this helper for all no-contact rows.
    """
    crop = centered_slice(int(data.burned.shape[-1]), kernel_size)
    if indices is None:
        fields = {key: getattr(data, key) for key in CachedSplit.__dataclass_fields__}
        fields["environment"] = data.environment[:, :, crop, crop]
        fields["burned"] = data.burned[:, :, crop, crop]
    else:
        selected = _indices(data, indices)
        fields = {key: getattr(data, key)[selected] for key in CachedSplit.__dataclass_fields__
                  if key not in ("environment", "burned")}
        fields["environment"] = data.environment[:, :, crop, crop][selected]
        fields["burned"] = data.burned[:, :, crop, crop][selected]
    return CachedSplit(**fields)


def cohort_payload(data: CachedSplit, indices: np.ndarray) -> dict[str, np.ndarray]:
    """Return base row index and unchanged labels, weights, cell-hour identity."""
    selected = _indices(data, indices)
    identities = np.column_stack([getattr(data, key)[selected] for key in IDENTITY_KEYS])
    if len(np.unique(identities, axis=0)) != len(selected):
        raise ValueError("Duplicate event/time/row/column identities in the selected base-cache rows")
    return {"source_index": selected.copy(), "y": data.target[selected], "w": data.weight[selected],
            **{key: getattr(data, key)[selected] for key in IDENTITY_KEYS}}


def cohort_summary(data: CachedSplit, indices: np.ndarray, kernel_size: int) -> dict[str, Any]:
    selected = _indices(data, indices)
    membership = np.zeros(len(data), dtype=bool)
    membership[selected] = True
    weight = data.weight[selected]
    total = float(weight.sum(dtype=np.float64))
    return {"base_sample_count": len(data), "sample_count": len(selected),
            "positive_sample_count": int(data.target[selected].sum()),
            "represented_population_weight": total,
            "weighted_prevalence": float(np.dot(weight, data.target[selected]) / total) if total else None,
            "contributing_events": len(np.unique(data.event_index[selected])),
            "excluded_sample_count": int((~membership).sum()),
            "excluded_positive_sample_count": int(data.target[~membership].sum()),
            "contact_kernel_size": kernel_size,
            "selection_uses_next_hour_target": False,
            "inverse_inclusion_weights_preserved": True}


def evaluate_contact_predictions(data: CachedSplit, predictions: Mapping[str, np.ndarray],
                                 metadata: dict[str, Any] | None = None,
                                 kernel_sizes: Mapping[str, int] | None = None) -> dict[str, Any]:
    """Score full-coverage predictions on native and matched contact cohorts.

    ``predictions[name]`` must have one probability per original base-cache row;
    ``kernel_sizes[name]`` explicitly identifies that model's spatial support.
    Metadata is accepted for callers carrying the cache contract; membership
    depends exclusively on current spatial inputs. No probabilities are clipped.
    """
    if not predictions or kernel_sizes is None or set(kernel_sizes) != set(predictions):
        raise ValueError("Every prediction must have one explicit kernel_sizes entry")
    sizes = sorted(set(kernel_sizes.values()))
    common = common_indices(data, sizes)
    result: dict[str, Any] = {"native": {}, "common": {},
                               "common_cohort": cohort_summary(data, common, sizes[0]),
                               "prediction_sample_count": len(data)}
    for name, probabilities in predictions.items():
        p = np.asarray(probabilities)
        if p.shape != (len(data),) or not np.isfinite(p).all() or not ((p >= 0) & (p <= 1)).all():
            raise ValueError(f"{name} predictions must be finite probabilities for every base-cache row")
        size = kernel_sizes[name]
        native = native_indices(data, size)
        counts = kernel_neighbor_count(data.burned, size)
        result["native"][name] = {
            "cohort": cohort_summary(data, native, size),
            "metrics": probability_metrics(data.target[native], p[native], data.weight[native], counts[native])}
        result["common"][name] = probability_metrics(data.target[common], p[common], data.weight[common], counts[common])
    return result
