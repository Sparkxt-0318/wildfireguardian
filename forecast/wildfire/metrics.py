"""Metrics operations for the wildfire workspace."""
from __future__ import annotations



# Metrics
# Population-weighted scoring and calibration for either model family.


from typing import Any

import numpy as np

from wildfire.cache import CachedSplit

LOG_LOSS_EPSILON = 1e-7


def brier(target: np.ndarray, prediction: np.ndarray, weight: np.ndarray) -> float:
    residual = prediction.astype(np.float64) - target.astype(np.float64)
    return float(np.dot(weight, residual * residual) / weight.sum(dtype=np.float64))


def weighted_rank_metrics(target: np.ndarray, prediction: np.ndarray,
                          weight: np.ndarray) -> tuple[float | None, float | None]:
    """Average precision and ROC AUC with tied scores treated as one threshold."""
    positive = float(np.dot(weight, target))
    negative = float(weight.sum(dtype=np.float64) - positive)
    if positive == 0:
        return None, None
    order = np.argsort(-prediction, kind="stable")
    sorted_scores = prediction[order]
    sorted_y = target[order]
    sorted_w = weight[order]
    thresholds = np.r_[np.flatnonzero(np.diff(sorted_scores)), len(order) - 1]
    true_positive = np.cumsum(sorted_w * sorted_y, dtype=np.float64)[thresholds]
    false_positive = np.cumsum(sorted_w * (1 - sorted_y), dtype=np.float64)[thresholds]
    recall = true_positive / positive
    precision = true_positive / (true_positive + false_positive)
    ap = float(np.dot(np.diff(np.r_[0.0, recall]), precision))
    auc = None
    if negative > 0:
        fpr = np.r_[0.0, false_positive / negative]
        tpr = np.r_[0.0, recall]
        auc = float(np.sum(np.diff(fpr) * (tpr[:-1] + tpr[1:]) / 2))
    return ap, auc


def probability_metrics(target: np.ndarray, prediction: np.ndarray,
                        weight: np.ndarray, neighbor_count: np.ndarray) -> dict[str, Any]:
    n = len(target)
    if n == 0:
        return {"sample_count": 0, "represented_population_weight": 0.0,
                "brier": None, "average_precision": None, "roc_auc": None,
                "clipped_log_loss": None, "exact_negative_log_likelihood_mean": None}
    y = target.astype(np.float64)
    p = prediction.astype(np.float64)
    total = float(weight.sum(dtype=np.float64))
    positives = y == 1
    zero_contact = neighbor_count == 0
    unsupported = positives & (p == 0)
    wrong_certain = (~positives) & (p == 1)
    clipped = np.clip(p, LOG_LOSS_EPSILON, 1 - LOG_LOSS_EPSILON)
    clipped_terms = np.where(positives, -np.log(clipped), -np.log1p(-clipped))
    if unsupported.any() or wrong_certain.any():
        exact_nll: float | str = "infinity"
    else:
        exact_terms = np.empty(n, dtype=np.float64)
        exact_terms[positives] = -np.log(p[positives])
        exact_terms[~positives] = -np.log1p(-p[~positives])
        exact_nll = float(np.dot(weight, exact_terms) / total)
    ap, auc = weighted_rank_metrics(y, p, weight)
    positive_weight = float(weight[positives].sum(dtype=np.float64))
    return {
        "sample_count": n,
        "represented_population_weight": total,
        "positive_sample_count": int(positives.sum()),
        "sample_positive_fraction": float(positives.mean()),
        "positive_population_weight": positive_weight,
        "weighted_prevalence": positive_weight / total,
        "mean_probability": float(np.dot(weight, p) / total),
        "brier": brier(y, p, weight),
        "positive_class_brier": brier(y[positives], p[positives], weight[positives]) if positives.any() else None,
        "negative_class_brier": brier(y[~positives], p[~positives], weight[~positives]) if (~positives).any() else None,
        "average_precision": ap,
        "roc_auc": auc,
        "clipped_log_loss": float(np.dot(weight, clipped_terms) / total),
        "log_loss_probability_floor": LOG_LOSS_EPSILON,
        "exact_negative_log_likelihood_mean": exact_nll,
        "unsupported_positive_sample_count": int(unsupported.sum()),
        "unsupported_positive_population_weight": float(weight[unsupported].sum()),
        "zero_contact_positive_sample_count": int((zero_contact & positives).sum()),
        "zero_contact_positive_population_weight": float(weight[zero_contact & positives].sum()),
        "zero_contact_positive_fraction": (float(weight[zero_contact & positives].sum()) / positive_weight
                                            if positive_weight else None),
        "zero_contact_population_weight": float(weight[zero_contact].sum()),
        "wrong_probability_one_negative_sample_count": int(wrong_certain.sum()),
    }


def weighted_calibration(target, prediction, weight):
    """Descriptive pooled reliability bins with inverse sampling weights.

    Bins are fixed before evaluation. These weighted cell-hour summaries do
    not give uncertainty intervals or assume neighboring targets independent.
    """
    edges = np.array([0, .01, .02, .05, .1, .2, .5, 1.0], dtype=np.float64)
    membership = np.minimum(np.searchsorted(edges, prediction, side="right") - 1, len(edges) - 2)
    total = float(weight.sum(dtype=np.float64))
    bins, absolute_error = [], 0.0
    for index in range(len(edges) - 1):
        selected = membership == index
        population = float(weight[selected].sum(dtype=np.float64))
        mean_p = float(np.dot(weight[selected], prediction[selected]) / population) if population else None
        outcome = float(np.dot(weight[selected], target[selected]) / population) if population else None
        if population:
            absolute_error += population / total * abs(mean_p - outcome)
        bins.append(dict(lower=float(edges[index]), upper=float(edges[index + 1]),
                         upper_inclusive=index == len(edges) - 2,
                         sample_count=int(selected.sum()),
                         positive_sample_count=int(target[selected].sum()),
                         represented_population_weight=population,
                         population_fraction=population / total,
                         mean_probability=mean_p, weighted_outcome_rate=outcome))
    return dict(bins=bins, weighted_expected_calibration_error=absolute_error,
                interpretation="Fixed-bin descriptive weighted reliability; no confidence intervals")


def scoped_metrics(data: CachedSplit, predictions: dict[str, np.ndarray],
                   selection: np.ndarray | None = None) -> dict[str, Any]:
    selected = np.ones(len(data), dtype=bool) if selection is None else selection
    counts = data.neighbor_count
    result = {}
    for name, p in predictions.items():
        result[name] = {}
        for scope, mask in (("all_eligible", selected), ("burned_neighbor_contact", selected & (counts > 0))):
            result[name][scope] = probability_metrics(data.target[mask], p[mask], data.weight[mask], counts[mask])
    return result


def country_for_event(metadata: dict[str, Any], event_id: str) -> str:
    per_event = metadata.get("per_event", {})
    if isinstance(per_event, dict):
        entry = per_event.get(event_id, {})
    else:
        entry = next((record for record in per_event
                      if record.get("event_id", record.get("id")) == event_id), {})
    value = entry.get("country", entry.get("country_code", "unknown"))
    return str(value)


def split_metrics(data: CachedSplit, predictions: dict[str, np.ndarray],
                  metadata: dict[str, Any]) -> dict[str, Any]:
    indices = np.unique(data.event_index)
    event_metrics = {}
    for index in indices:
        event_id = metadata["event_ids"][int(index)]
        event_metrics[event_id] = scoped_metrics(data, predictions, data.event_index == index)
    return {"models": scoped_metrics(data, predictions),
            "per_event": event_metrics}



# Categorical balance
# Training-only categorical rarity weights with unchanged population scoring.
# 
# Fit marginal category presence using raw cropped training patches and original
# inverse inclusion weights. The returned optimization weights deliberately
# change the training covariate distribution. Population evaluation continues to
# use the original weights. This method balances neither outcomes nor every
# joint categorical pattern, and does not guarantee improved generalization.


import hashlib
import math
from numbers import Real


from wildfire.schema import one_hot_groups

BALANCE_MODES = ("none", "inverse-sqrt")
ALGORITHM_VERSION = 1


def validate_categorical_balance_settings(mode="inverse-sqrt", min_frequency=.001,
                                           max_factor=10., chunk_size=512):
    """Validate explicit frequency/factor bounds and return JSON scalar settings."""
    if not isinstance(mode, str) or mode not in BALANCE_MODES:
        raise ValueError(f"categorical balance mode must be one of {BALANCE_MODES}")
    for name, value in (("min_frequency", min_frequency), ("max_factor", max_factor)):
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            raise ValueError(f"{name} must be a finite numeric scalar")
        try:
            numeric = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"{name} must be a finite numeric scalar") from None
        if not math.isfinite(numeric):
            raise ValueError(f"{name} must be finite")
    if not 0 < float(min_frequency) <= 1:
        raise ValueError("min_frequency must lie in (0, 1]")
    if float(max_factor) < 1:
        raise ValueError("max_factor must be at least one")
    if (not isinstance(chunk_size, (int, np.integer)) or isinstance(chunk_size, (bool, np.bool_))
            or chunk_size < 1):
        raise ValueError("chunk_size must be a positive integer")
    return dict(mode=mode, min_frequency=float(min_frequency), max_factor=float(max_factor),
                chunk_size=int(chunk_size))


def categorical_balance_settings(args):
    """Read the shared options, including defaults for legacy Namespace callers."""
    return validate_categorical_balance_settings(
        mode=getattr(args, "categorical_balance", "inverse-sqrt"),
        min_frequency=getattr(args, "categorical_balance_min_frequency", .001),
        max_factor=getattr(args, "categorical_balance_max_factor", 10.),
        chunk_size=getattr(args, "categorical_balance_chunk_size", 512))


def add_categorical_balance_arguments(parser):
    """Add the same training-only balancing options to each training command."""
    parser.add_argument("--categorical-balance", choices=BALANCE_MODES, default="inverse-sqrt",
                        help="Training-only category presence weighting; population evaluation weights remain original")
    parser.add_argument("--categorical-balance-min-frequency", type=float, default=.001,
                        help="Floor for original inverse-weighted training patch-presence frequency")
    parser.add_argument("--categorical-balance-max-factor", type=float, default=10.,
                        help="Maximum raw per-category rarity factor before weighted-mean normalization")
    return parser


def _categorical_balance_inputs(data, metadata, chunk_size, *, selected=None, allow_empty=False):
    environment = np.asarray(data.environment)
    weight = np.asarray(data.weight)
    if (environment.ndim != 4 or (environment.shape[0] < 1 and not allow_empty)
            or environment.shape[1] != len(metadata["channels"])
            or environment.shape[-1] != environment.shape[-2]
            or environment.shape[-1] < 3 or environment.shape[-1] % 2 != 1
            or not np.issubdtype(environment.dtype, np.floating)):
        raise ValueError("Environmental inputs must be raw nonempty N,C,K,K floating patches with odd K >= 3")
    n = environment.shape[0]
    if (weight.shape != (n,) or not np.issubdtype(weight.dtype, np.floating)
            or not np.isfinite(weight).all() or not (weight > 0).all()):
        raise ValueError("Population weights must be matching finite positive floating values")
    weights = weight.astype(np.float64, copy=False)
    if selected is not None:
        weights = weights[selected]
        n = len(selected)
    total = float(weights.sum(dtype=np.float64))
    if not math.isfinite(total) or (total <= 0 and not (allow_empty and n == 0)):
        raise ValueError("Population weight sum must be finite and positive")
    groups = one_hot_groups(metadata)
    presences = {}
    for start in range(0, n, chunk_size):
        chunk = environment[start:start + chunk_size] if selected is None else environment[selected[start:start + chunk_size]]
        if not np.isfinite(chunk).all():
            raise ValueError("Raw environmental inputs must be finite")
    for source, indices in groups.items():
        present = np.empty((n, len(indices)), dtype=bool)
        for start in range(0, n, chunk_size):
            end = min(start + chunk_size, n)
            chunk = environment[start:end] if selected is None else environment[selected[start:end]]
            values = chunk[:, indices]
            if not np.isin(values, (0, 1)).all() or not (values.sum(axis=1) == 1).all():
                raise ValueError(f"Raw one-hot group {source} must have exactly one active class at every patch position")
            present[start:end] = (values == 1).any(axis=(2, 3))
        presences[source] = present
    return environment, weights, total, groups, presences


def _digest(values):
    # Canonical little-endian float64 bytes, independent of input strides.
    return hashlib.sha256(np.ascontiguousarray(values, dtype="<f8").tobytes()).hexdigest()


def _effective_sample_size(weights):
    # Rescaling avoids overflow when inverse inclusion weights are large.
    relative = weights / float(weights.max())
    return float(relative.sum(dtype=np.float64) ** 2 / np.dot(relative, relative))


def _class_record(metadata, source, index):
    info = metadata["channel_info"][index]
    return dict(input_channel_index=int(index), input_channel=metadata["channels"][index],
                source_channel=source, class_code=int(info["class_code"]),
                class_name=info.get("class_name"))


def fit_categorical_balance(data, metadata, *, mode="inverse-sqrt", min_frequency=.001,
                            max_factor=10., chunk_size=512):
    """Return optimization weights and a reproducible training-only fit audit.

    For source g and category c, p_gc = sum_i w_i I_gc(i) / sum_i w_i,
    where I_gc(i) is true when c appears anywhere in i's RAW cropped patch.
    Observed categories use r_gc = min(max_factor, max(p_gc,min_frequency)^(-1/2));
    unobserved categories use neutral factor one. Each row averages r_gc across
    its DISTINCT present categories, then averages across categorical sources.
    Divide that row factor by its original-population-weighted mean, and return
    w_i times the normalized factor. No targets, event labels, validation data,
    test data, or fitted model parameters are read by this function.
    """
    settings = validate_categorical_balance_settings(mode, min_frequency, max_factor, chunk_size)
    environment, weight, total, groups, presences = _categorical_balance_inputs(data, metadata, settings["chunk_size"])
    n = environment.shape[0]
    raw_factor = np.zeros(n, dtype=np.float64) if groups else np.ones(n, dtype=np.float64)
    source_data = []
    for source, indices in groups.items():
        present = presences[source]
        mass = np.array([weight[present[:, column]].sum(dtype=np.float64)
                         for column in range(len(indices))], dtype=np.float64)
        frequency = np.clip(mass / total, 0., 1.)
        observed = present.any(axis=0)
        rarity = np.ones(len(indices), dtype=np.float64)
        if settings["mode"] == "inverse-sqrt":
            rarity[observed] = np.minimum(settings["max_factor"],
                                         np.maximum(frequency[observed], settings["min_frequency"]) ** -.5)
        distinct = present.sum(axis=1)
        if not (distinct >= 1).all():
            raise ValueError("Every raw categorical source must have at least one present class per row")
        raw_factor += present @ rarity / distinct
        classes = []
        for column, index in enumerate(indices):
            classes.append(dict(**_class_record(metadata, source, index),
                                present_rows=int(present[:, column].sum()),
                                population_presence_weight=float(mass[column]),
                                population_presence_frequency=float(frequency[column]),
                                observed_in_training=bool(observed[column]), rarity_factor=float(rarity[column])))
        source_data.append(dict(source_channel=source, classes=classes))
    if groups:
        raw_factor /= len(groups)
    normalizer = 1. if mode == "none" or not groups else float(np.dot(weight / total, raw_factor))
    if not math.isfinite(normalizer) or normalizer <= 0:
        raise ValueError("Categorical factor normalizer must be finite and positive")
    factor = raw_factor / normalizer
    # Disabled/no-category behavior reproduces the original population weights.
    optimization_weight = weight.copy() if mode == "none" or not groups else weight * factor
    optimization_total = float(optimization_weight.sum(dtype=np.float64))
    if (not math.isfinite(optimization_total) or optimization_total <= 0
            or not np.isfinite(optimization_weight).all() or not (optimization_weight > 0).all()):
        raise ValueError("Categorical optimization weights must be finite and positive")
    for entry in source_data:
        present = presences[entry["source_channel"]]
        for column, record in enumerate(entry["classes"]):
            effective = float(optimization_weight[present[:, column]].sum(dtype=np.float64))
            record["effective_presence_weight"] = effective
            record["effective_presence_frequency"] = effective / optimization_total
    audit = dict(algorithm_version=ALGORITHM_VERSION, method="raw_patch_presence_inverse_square_root" if mode == "inverse-sqrt" else "none",
                 settings=settings, kernel_size=int(environment.shape[-1]), row_count=n,
                 fit_scope="training_only", uses_targets=False, uses_validation=False, uses_test=False,
                 presence_scope="Anywhere in each learner's actual raw cropped environmental patch",
                 sources=source_data, categorical_source_count=len(groups),
                 source_combination="Arithmetic mean of source factors; each source factor averages distinct present classes",
                 normalizer=normalizer, factor_min=float(factor.min()), factor_max=float(factor.max()),
                 factor_lower_bound=1. / settings["max_factor"], factor_upper_bound=settings["max_factor"],
                 population_weight_sum=total, optimization_weight_sum=optimization_total,
                 relative_population_mass_change=(optimization_total - total) / total,
                 population_weights_sha256=_digest(weight), optimization_weights_sha256=_digest(optimization_weight),
                 effective_sample_size_population=_effective_sample_size(weight),
                 effective_sample_size_optimization=_effective_sample_size(optimization_weight),
                 population_evaluation_weights_changed=False,
                 limitations=["Changes the training covariate distribution, rather than balancing outcomes",
                              "Presence groups overlap; this does not make every category equally frequent",
                              "Does not guarantee equal feature gradients, calibration, or improved held-out performance"])
    return optimization_weight.astype(np.float64, copy=False), audit


def categorical_group_metrics(data, probability, metadata, *, chunk_size=512, indices=None):
    """Population metrics for overlapping raw-input categories in an optional cohort.

    Predictions contain one value per data row. Unique integer ``indices`` select
    a cohort; only its raw patches are read, in bounded chunks. No environmental
    array for the complete selected cohort is materialized.
    """
    settings = validate_categorical_balance_settings(chunk_size=chunk_size)
    source_environment = np.asarray(data.environment)
    if source_environment.ndim != 4:
        raise ValueError("Evaluation environmental inputs must have N,C,K,K shape")
    source_count = source_environment.shape[0]
    selected = None
    if indices is not None:
        selected = np.asarray(indices)
        if (selected.ndim != 1 or not np.issubdtype(selected.dtype, np.integer)
                or (selected < 0).any() or (selected >= source_count).any()
                or len(np.unique(selected)) != len(selected)):
            raise ValueError("Metric cohort indices must be unique in-range integers")
        selected = selected.astype(np.int64, copy=False)
    environment, weight, total, groups, presences = _categorical_balance_inputs(data, metadata, settings["chunk_size"],
                                                          selected=selected, allow_empty=True)
    n = len(weight)
    target, prediction = np.asarray(data.target), np.asarray(probability)
    if target.shape != (source_count,) or prediction.shape != (source_count,):
        raise ValueError("Evaluation targets and predictions must contain one value per source row")
    if selected is not None:
        target, prediction = target[selected], prediction[selected]
    if target.shape != (n,) or not np.isin(target, (0, 1)).all():
        raise ValueError("Evaluation targets must be a matching binary [N] array")
    if (prediction.shape != (n,) or not np.isfinite(prediction).all()
            or not ((prediction >= 0) & (prediction <= 1)).all()):
        raise ValueError("Evaluation predictions must be matching finite probabilities")
    residual_square = (prediction.astype(np.float64) - target.astype(np.float64)) ** 2
    sources = []
    for source, indices in groups.items():
        classes = []
        for column, index in enumerate(indices):
            present = presences[source][:, column]
            mass = float(weight[present].sum(dtype=np.float64))
            positive = float(np.dot(weight[present], target[present]))
            classes.append(dict(**_class_record(metadata, source, index),
                                sample_count=int(present.sum()), positive_sample_count=int(target[present].sum()),
                                represented_population_weight=mass, positive_population_weight=positive,
                                population_presence_frequency=mass / total if total else None,
                                weighted_prevalence=positive / mass if mass else None,
                                brier=float(np.dot(weight[present], residual_square[present]) / mass) if mass else None))
        sources.append(dict(source_channel=source, classes=classes))
    return dict(presence_scope="Anywhere in the actual raw cropped environmental patch",
                algorithm_version=ALGORITHM_VERSION, kernel_size=int(environment.shape[-1]),
                row_count=n, source_row_count=source_count, sources=sources,
                groups_overlap=True, group_counts_are_additive=False,
                weights="Original inverse inclusion population weights; no categorical balancing applied to evaluation",
                population_weights_sha256=_digest(weight), represented_population_weight=total)


# Classification
# Weighted PR-curve area, binary classification, and validation thresholds.





def _classification_vector(value: Any, name: str) -> np.ndarray:
    try:
        array = np.asarray(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a one-dimensional numeric vector") from error
    if array.ndim != 1 or array.dtype.kind not in "biuf":
        raise ValueError(f"{name} must be a one-dimensional real numeric vector")
    with np.errstate(over="ignore", invalid="ignore"):
        array = array.astype(np.float64, copy=False)
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain finite values")
    return array


def _classification_inputs(target: Any, prediction: Any, weight: Any):
    labels = _classification_vector(target, "target")
    probabilities = _classification_vector(prediction, "prediction")
    weights = _classification_vector(weight, "weight")
    if len(labels) == 0 or not labels.shape == probabilities.shape == weights.shape:
        raise ValueError("target, prediction, and weight must have equal nonempty lengths")
    if ((labels != 0) & (labels != 1)).any():
        raise ValueError("target must contain binary labels, exactly 0 or 1")
    if ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("prediction must lie in [0, 1]")
    if (weights <= 0).any():
        raise ValueError("weight must be strictly positive")
    with np.errstate(over="ignore"):
        total = float(weights.sum(dtype=np.float64))
    if not np.isfinite(total) or total <= 0:
        raise ValueError("weight total must be finite and positive")
    return labels.astype(bool), probabilities, weights, total


def _divide(numerator, denominator):
    numerator, denominator = np.broadcast_arrays(numerator, denominator)
    return np.divide(numerator, denominator, out=np.zeros(numerator.shape, dtype=np.float64),
                     where=denominator != 0)


def _scores(tp, fp, tn, fn, total):
    """Vectorized safe scores; zero-denominator scores use the value zero."""
    tp, fp, tn, fn = (np.asarray(value, dtype=np.float64) for value in (tp, fp, tn, fn))
    precision = _divide(tp, tp + fp)
    recall = _divide(tp, tp + fn)
    # Divide weights by their total before count arithmetic. This prevents
    # overflowing 2*TP and the fourth-order unscaled MCC denominator.
    a, b, c, d = (value / total for value in (tp, fp, tn, fn))
    f1 = _divide(2 * a, 2 * a + b + d)
    # The product of separately square-rooted marginal ratios avoids an
    # underflow-prone four-factor denominator. Raw ratios also preserve a
    # rare class if total-weight normalization rounded its mass to zero.
    positive_product = (
        np.sqrt(_divide(tp, tp + fp)) * np.sqrt(_divide(tp, tp + fn))
        * np.sqrt(_divide(tn, tn + fp)) * np.sqrt(_divide(tn, tn + fn))
    )
    negative_product = (
        np.sqrt(_divide(fp, tp + fp)) * np.sqrt(_divide(fp, tn + fp))
        * np.sqrt(_divide(fn, tp + fn)) * np.sqrt(_divide(fn, tn + fn))
    )
    mcc = positive_product - negative_product
    defined = ((tp + fp) > 0) & ((tp + fn) > 0) & ((tn + fp) > 0) & ((tn + fn) > 0)
    mcc = np.where(defined, np.clip(mcc, -1, 1), 0)
    # Extreme valid weight ratios can make normalized TP underflow. The
    # equivalent harmonic-mean form preserves that case without 1/precision.
    smaller = np.minimum(precision, recall)
    larger = np.maximum(precision, recall)
    stable_harmonic = _divide(2 * smaller, 1 + _divide(smaller, larger))
    f1 = np.where((a == 0) & (tp > 0), stable_harmonic, f1)
    return {"precision": precision, "recall": recall, "f1": f1, "mcc": mcc}


def _curve_counts(labels, probabilities, weights):
    order = np.argsort(-probabilities, kind="stable")
    scores = probabilities[order]
    y = labels[order]
    w = weights[order]
    group_ends = np.r_[np.flatnonzero(np.diff(scores)), len(scores) - 1]
    tp = np.cumsum(np.where(y, w, 0), dtype=np.float64)[group_ends]
    fp = np.cumsum(np.where(y, 0, w), dtype=np.float64)[group_ends]
    return scores[group_ends], tp, fp


def weighted_pr_auc(target: Any, prediction: Any, weight: Any) -> float | None:
    """Trapezoidal area under the weighted precision-recall curve.

    A threshold predicts positive exactly when ``prediction >= threshold``.
    Equal prediction scores enter as one group. The curve starts at recall
    zero and precision one, then traverses the observed score groups in
    descending order. If no positive outcome is observed, the function
    returns ``None`` because positive recall is undefined.

    This is trapezoidal PR AUC, not average precision (AP). For a constant
    predictor with weighted prevalence q > 0, PR AUC is (1+q)/2 while AP is q.
    """
    labels, probabilities, weights, _ = _classification_inputs(target, prediction, weight)
    if not labels.any():
        return None
    _, tp, fp = _curve_counts(labels, probabilities, weights)
    recall = np.r_[0.0, tp / tp[-1]]
    precision = np.r_[1.0, tp / (tp + fp)]
    return float(np.sum(np.diff(recall) * (precision[:-1] + precision[1:]) / 2))


def weighted_classification_metrics(target: Any, prediction: Any, weight: Any, *,
                                    threshold: float) -> dict[str, float]:
    """Weighted confusion counts, precision, recall, F1, and MCC at a threshold.

    All rows contribute their supplied inverse-probability/population weight.
    Decisions are ``prediction >= threshold``. Any finite real threshold is
    allowed, including a threshold just above one for an all-negative rule.
    A score with a zero denominator is assigned zero, including degenerate
    MCC, following sklearn's zero-division convention. Returned confusion
    counts retain their original weight scale; scores use safe normalized
    arithmetic and do not depend on a common positive rescaling of weights.
    """
    labels, probabilities, weights, total = _classification_inputs(target, prediction, weight)
    if (not isinstance(threshold, Real) or isinstance(threshold, (bool, np.bool_))
            or not np.isfinite(threshold)):
        raise ValueError("threshold must be a finite real numeric scalar")
    positive = probabilities >= threshold
    tp = float(weights[labels & positive].sum(dtype=np.float64))
    fp = float(weights[~labels & positive].sum(dtype=np.float64))
    tn = float(weights[~labels & ~positive].sum(dtype=np.float64))
    fn = float(weights[labels & ~positive].sum(dtype=np.float64))
    result = {name: float(value) for name, value in _scores(tp, fp, tn, fn, total).items()}
    result.update(tp=tp, fp=fp, tn=tn, fn=fn, threshold=float(threshold))
    return result


def select_classification_threshold(target: Any, prediction: Any, weight: Any, *,
                                    criterion: str = "f1") -> dict[str, Any]:
    """Choose a threshold from validation data only in O(N log N) time.

    The finite candidate set is each unique observed validation probability,
    plus ``nextafter(max_probability, +infinity)`` for the all-negative rule.
    Every candidate uses ``prediction >= threshold``. Equal scores are grouped
    before computing the confusion counts. The largest metric wins; exact
    metric ties prefer the higher threshold among this candidate set.

    Callers must supply validation data, persist this result, and apply its
    fixed threshold to test data. This helper neither identifies a split nor
    uses test data. ``unidentifiable`` is true when the supplied validation
    outcomes contain fewer than two classes; in particular MCC is then zero
    for every threshold. The flag describes the observed validation labels,
    not whether a threshold can produce positive or negative decisions.
    """
    if criterion not in ("f1", "mcc"):
        raise ValueError("criterion must be 'f1' or 'mcc'")
    labels, probabilities, weights, total = _classification_inputs(target, prediction, weight)
    scores, tp, fp = _curve_counts(labels, probabilities, weights)
    candidates = np.r_[np.nextafter(scores[0], np.inf), scores]
    positive_total, negative_total = tp[-1], fp[-1]
    tp, fp = np.r_[0.0, tp], np.r_[0.0, fp]
    fn = np.maximum(positive_total - tp, 0)
    tn = np.maximum(negative_total - fp, 0)
    values = _scores(tp, fp, tn, fn, total)[criterion]
    # Candidates are strictly descending. np.argmax chooses their first
    # occurrence, hence the highest threshold on an exact metric tie.
    index = int(np.argmax(values))
    chosen_threshold = float(candidates[index])
    validation_metrics = weighted_classification_metrics(
        labels, probabilities, weights, threshold=chosen_threshold,
    )
    value = validation_metrics[criterion]
    return {
        "threshold": chosen_threshold,
        "criterion": criterion,
        "validation_metric": value,
        "validation_metric_value": value,
        "validation_metrics": validation_metrics,
        "decision_rule": "prediction_probability >= threshold",
        "candidate_count": len(candidates),
        "candidate_set": "unique_validation_scores_plus_nextafter_max_score_toward_positive_infinity",
        "tie_break": "higher_threshold",
        "selected_on": "validation",
        "unidentifiable": bool(not labels.any() or labels.all()),
        "validation_sample_count": len(labels),
    }


# Kl
# Population-weighted Bernoulli KL divergence in natural-log units (nats).



from scipy.special import rel_entr


def _kl_vector(value: Any, name: str) -> np.ndarray:
    try:
        array = np.asarray(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a real numeric vector") from error
    if array.ndim != 1 or array.dtype.kind not in "biuf":
        raise ValueError(f"{name} must be a one-dimensional real numeric vector")
    with np.errstate(over="ignore", invalid="ignore"):
        array = array.astype(np.float64, copy=False)
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain finite values")
    return array


def weighted_bernoulli_kl(reference_probability: Any, prediction_probability: Any,
                          weight: Any, *,
                          probability_floor: float | None = None) -> float | str:
    r"""Return the positive-weight mean of ``KL(Bern(r) || Bern(p))``.

    For each row, the directed divergence is

    ``r * log(r / p) + (1-r) * log((1-r) / (1-p))``.

    Natural logarithms give nats. A zero reference mass contributes zero,
    including when its prediction mass is also zero. A positive reference
    mass assigned zero probability contributes positive infinity, returned
    as the JSON-compatible string ``"infinity"``. Every weight must be finite
    and strictly positive, and the sum of weights must be finite.

    ``probability_floor`` must lie strictly between 0 and 0.5. If supplied,
    only ``p`` is clipped to ``[floor, 1-floor]``: the returned value therefore
    compares the reference distribution with a changed prediction
    distribution Q. The reference ``r`` is unchanged. With hard references
    ``r in {0,1}``, this KL equals the corresponding negative log likelihood,
    because the reference Bernoulli distribution has zero entropy.
    """
    reference = _kl_vector(reference_probability, "reference_probability")
    prediction = _kl_vector(prediction_probability, "prediction_probability")
    weights = _kl_vector(weight, "weight")
    if len(reference) == 0 or reference.shape != prediction.shape or reference.shape != weights.shape:
        raise ValueError("reference_probability, prediction_probability, and weight must have equal nonempty lengths")
    if ((reference < 0) | (reference > 1)).any():
        raise ValueError("reference_probability must lie in [0, 1]")
    if ((prediction < 0) | (prediction > 1)).any():
        raise ValueError("prediction_probability must lie in [0, 1]")
    if (weights <= 0).any():
        raise ValueError("weight must be strictly positive")
    with np.errstate(over="ignore"):
        total = float(weights.sum(dtype=np.float64))
    if not np.isfinite(total) or total <= 0:
        raise ValueError("weight total must be finite and positive")
    if probability_floor is not None:
        if (not isinstance(probability_floor, Real)
                or isinstance(probability_floor, (bool, np.bool_))
                or not np.isfinite(probability_floor)
                or not 0 < probability_floor < 0.5):
            raise ValueError("probability_floor must be finite, numeric, and strictly between 0 and 0.5")
        prediction = np.clip(prediction, probability_floor, 1 - probability_floor)
    terms = rel_entr(reference, prediction) + rel_entr(1 - reference, 1 - prediction)
    # The endpoint expressions avoid cancellation of tiny p in 1-p and
    # agree with the existing exact and floored negative-log-loss formulas.
    with np.errstate(divide="ignore"):
        zero_reference = reference == 0
        one_reference = reference == 1
        terms[zero_reference] = -np.log1p(-prediction[zero_reference])
        terms[one_reference] = -np.log(prediction[one_reference])
    if np.isposinf(terms).any():
        return "infinity"
    # KL is nonnegative; tiny negative sums can occur from floating-point
    # cancellation when the reference and prediction are nearly equal.
    terms = np.maximum(terms, 0)
    return float(np.dot(weights / total, terms))


def probability_metrics_with_kl(target: Any, prediction: Any,
                                weight: Any, neighbor_count: Any) -> dict[str, Any]:
    """Preserve existing binary-outcome metrics and add exact and floored KL.

    ``target`` is the observed hard label in ``{0,1}``, interpreted as the
    probability of the degenerate empirical Bernoulli reference. The added
    exact KL equals exact NLL, and the added floored KL equals the existing
    clipped log loss with ``LOG_LOSS_EPSILON``. This is not a KL comparison
    between two models' predictive distributions. Empty scopes preserve the
    existing metrics behavior and contain ``None`` for both KL means.
    """
    labels = _kl_vector(target, "target")
    probabilities = _kl_vector(prediction, "prediction")
    weights = _kl_vector(weight, "weight")
    counts = _kl_vector(neighbor_count, "neighbor_count")
    if not (labels.shape == probabilities.shape == weights.shape == counts.shape):
        raise ValueError("target, prediction, weight, and neighbor_count must have equal lengths")
    if ((labels != 0) & (labels != 1)).any():
        raise ValueError("target must contain binary observed labels, exactly 0 or 1")
    if ((counts < 0) | (counts != np.floor(counts))).any():
        raise ValueError("neighbor_count must contain nonnegative integer counts")
    if len(labels) == 0:
        result = probability_metrics(labels, probabilities, weights, counts)
        result["bernoulli_kl_divergence_mean"] = None
        result["floored_bernoulli_kl_divergence_mean"] = None
        return result
    exact = weighted_bernoulli_kl(labels, probabilities, weights)
    floored = weighted_bernoulli_kl(labels, probabilities, weights,
                                   probability_floor=LOG_LOSS_EPSILON)
    result = probability_metrics(labels, probabilities, weights, counts)
    result["bernoulli_kl_divergence_mean"] = exact
    result["floored_bernoulli_kl_divergence_mean"] = floored
    return result


# Distances
# Exact weighted per-cell distances between two Bernoulli distributions.





DISTANCE_FIELDS = (
    "bernoulli_total_variation_distance_mean",
    "bernoulli_hellinger_distance_mean",
    "bernoulli_jensen_shannon_divergence_mean",
    "bernoulli_jensen_shannon_distance_mean",
    "bernoulli_bhattacharyya_distance_mean",
    "bernoulli_wasserstein_1_distance_mean",
    "bernoulli_wasserstein_2_distance_mean",
)

STATISTICAL_DISTANCE_FIELDS = DISTANCE_FIELDS

__all__ = ["DISTANCE_FIELDS", "STATISTICAL_DISTANCE_FIELDS",
           "weighted_bernoulli_distances", "probability_metrics_with_statistical_distances"]


def _distances_vector(value: Any, name: str) -> np.ndarray:
    try:
        result = np.asarray(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a one-dimensional real numeric vector") from error
    if result.ndim != 1 or result.dtype.kind not in "biuf":
        raise ValueError(f"{name} must be a one-dimensional real numeric vector")
    with np.errstate(over="ignore", invalid="ignore"):
        result = result.astype(np.float64, copy=False)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must contain finite values")
    return result


def _distances_inputs(reference: Any, prediction: Any, weight: Any):
    r = _distances_vector(reference, "reference_probability")
    p = _distances_vector(prediction, "prediction_probability")
    w = _distances_vector(weight, "weight")
    if len(r) == 0 or not r.shape == p.shape == w.shape:
        raise ValueError("reference_probability, prediction_probability, and weight must have equal nonempty lengths")
    if ((r < 0) | (r > 1)).any() or ((p < 0) | (p > 1)).any():
        raise ValueError("reference and prediction probabilities must lie in [0, 1]")
    if (w <= 0).any():
        raise ValueError("weight must be strictly positive")
    with np.errstate(over="ignore"):
        total = float(w.sum(dtype=np.float64))
    if not np.isfinite(total) or total <= 0:
        raise ValueError("weight total must be finite and positive")
    return r, p, w / total


def _js_mass_pair(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Half the two mass contributions to Jensen-Shannon divergence.

    Writing s=a+b and x=(a-b)/s gives
    s/4 * (log1p(-x*x) + 2*x*atanh(x)). This even expression preserves tiny
    positive divergence for nearly equal masses, without subtracting two
    first-order entropy terms. At |x|=1 the parenthesis is exactly 2*log(2).
    The expression also avoids an underflowing explicit mixture s/2.
    """
    total = a + b
    result = np.zeros_like(total)
    nonzero = total > 0
    x = np.zeros_like(total)
    x[nonzero] = (a[nonzero] - b[nonzero]) / total[nonzero]
    endpoint = nonzero & (np.abs(x) >= 1)
    result[endpoint] = total[endpoint] * (np.log(2) / 2)
    interior = nonzero & ~endpoint
    z = x[interior]
    even_entropy = np.log1p(-z * z) + 2 * z * np.arctanh(z)
    result[interior] = total[interior] * (0.25 * even_entropy)
    return np.maximum(result, 0)


def weighted_bernoulli_distances(reference_probability: Any,
                                 prediction_probability: Any,
                                 weight: Any) -> dict[str, float | str]:
    r"""Weighted means of seven exact per-cell Bernoulli quantities.

    A row has distributions P=(1-r,r), Q=(1-p,p) on the ordered support
    {0,1}, and positive supplied population/inverse-probability weight w.
    Every returned value is sum(w_i*d_i)/sum(w_i), where d_i is the per-cell
    quantity below. No probability clipping or flooring is performed.

    * Total variation: 0.5*sum(abs(P-Q)) = abs(r-p), in [0,1].
    * Hellinger: sqrt(0.5*sum((sqrt(P)-sqrt(Q))**2)), in [0,1].
    * Jensen-Shannon divergence: 0.5*KL(P||M)+0.5*KL(Q||M),
      M=(P+Q)/2, using natural logarithms, in [0,log(2)] nats.
    * Jensen-Shannon distance: sqrt(the per-cell JS divergence).
    * Bhattacharyya distance: -log(sum(sqrt(P*Q))), using natural logs.
      Disjoint supports give infinity, returned as the string "infinity".
    * Wasserstein-1: abs(r-p), using unit distance between support points.
    * Wasserstein-2: sqrt(abs(r-p)), using that same binary ground space.

    In particular, mean JS distance is the mean of the per-cell square
    roots, not the square root of mean JS divergence. The analogous ordering
    applies to mean Wasserstein-2 and mean Hellinger distances. Total
    variation and Wasserstein-1 coincide on this binary unit ground space.

    These quantities are symmetric in r and p. Soft r is allowed here.
    For an observed hard outcome r=y in {0,1}, P is a degenerate empirical
    reference, not a known calibrated distribution of future outcomes. The
    distances then measure per-row predictive disagreement with the label,
    rather than a distance between models or between their spatial maps.
    """
    r, p, normalized_weight = _distances_inputs(reference_probability, prediction_probability, weight)
    variation = np.abs(r - p)
    r0, p0 = 1 - r, 1 - p
    sqrt_r, sqrt_p = np.sqrt(r), np.sqrt(p)
    sqrt_r0, sqrt_p0 = np.sqrt(r0), np.sqrt(p0)
    hellinger_squared = 0.5 * ((sqrt_r - sqrt_p)**2 + (sqrt_r0 - sqrt_p0)**2)
    hellinger_squared = np.clip(hellinger_squared, 0, 1)
    hellinger = np.sqrt(hellinger_squared)
    js = _js_mass_pair(r, p) + _js_mass_pair(r0, p0)
    # Enforce the exact mathematical bounds if cancellation rounds a value
    # slightly below zero or above log(2).
    js = np.clip(js, 0, np.log(2))
    coefficient = np.clip(sqrt_r * sqrt_p + sqrt_r0 * sqrt_p0, 0, 1)
    bhattacharyya = np.empty_like(coefficient)
    near_one = coefficient > 0.5
    with np.errstate(divide="ignore"):
        # BC=1-H^2: log1p preserves tiny distances near identical P and Q.
        bhattacharyya[near_one] = -np.log1p(-hellinger_squared[near_one])
        # Direct BC preserves tiny positive support near disjoint P and Q.
        bhattacharyya[~near_one] = -np.log(coefficient[~near_one])
    quantities = (
        variation, hellinger, js, np.sqrt(js), bhattacharyya,
        variation, np.sqrt(variation),
    )
    return {
        name: ("infinity" if np.isposinf(values).any()
               else float(np.dot(normalized_weight, values)))
        for name, values in zip(STATISTICAL_DISTANCE_FIELDS, quantities)
    }


def probability_metrics_with_statistical_distances(target: Any, prediction: Any,
                                                   weight: Any, neighbor_count: Any) -> dict[str, Any]:
    """Preserve existing hard-label metrics and add exact Bernoulli distances.

    Each binary observed outcome defines P=(1-y,y). This wrapper measures
    per-cell disagreement with those outcomes; it does not compare two
    fitted model distributions or the distributions of spatial event maps.
    Empty scopes retain the original metrics and append None distance means.
    """
    labels = _distances_vector(target, "target")
    p = _distances_vector(prediction, "prediction")
    w = _distances_vector(weight, "weight")
    counts = _distances_vector(neighbor_count, "neighbor_count")
    if not labels.shape == p.shape == w.shape == counts.shape:
        raise ValueError("target, prediction, weight, and neighbor_count must have equal lengths")
    if ((labels != 0) & (labels != 1)).any():
        raise ValueError("target must contain binary observed labels, exactly 0 or 1")
    if ((counts < 0) | (counts != np.floor(counts))).any():
        raise ValueError("neighbor_count must contain nonnegative integer counts")
    additions = (weighted_bernoulli_distances(labels, p, w) if len(labels)
                 else dict.fromkeys(STATISTICAL_DISTANCE_FIELDS, None))
    result = probability_metrics(labels, p, w, counts)
    result.update(additions)
    return result


# Metric set
# Probability and threshold-dependent metrics under one explicit protocol.



def probability_metrics_with_all(target, prediction, weight, neighbor_count, *, thresholds=None):
    """Add exact statistical distances, PR AUC, and fixed/validation F1/MCC.

    PR AUC is the trapezoidal area of the weighted precision-recall curve,
    distinct from the existing non-interpolated average precision. The two
    validation threshold records, when supplied, optimize F1 and MCC separately.
    Their values are passed in from the shared validation partition, never
    fitted here from the outcomes being scored.
    Statistical distances compare each predicted Bernoulli distribution with
    its observed binary outcome using the same original weights. They do not
    tune a threshold or alter any probabilities.
    """
    result = probability_metrics_with_kl(target, prediction, weight, neighbor_count)
    names = ["precision_recall_auc", "precision_at_0_5", "recall_at_0_5", "f1_at_0_5", "mcc_at_0_5",
             "validation_f1_threshold", "precision_at_validation_f1_threshold", "recall_at_validation_f1_threshold",
             "f1_at_validation_f1_threshold", "mcc_at_validation_f1_threshold", "validation_mcc_threshold",
             "mcc_at_validation_mcc_threshold", "f1_at_validation_mcc_threshold"]
    if len(target) == 0:
        result.update({name: None for name in names})
        result.update({name: None for name in DISTANCE_FIELDS})
        return result
    result.update(weighted_bernoulli_distances(target, prediction, weight))
    result["precision_recall_auc"] = weighted_pr_auc(target, prediction, weight)
    fixed = weighted_classification_metrics(target, prediction, weight, threshold=.5)
    for name in ("precision", "recall", "f1", "mcc"):
        result[f"{name}_at_0_5"] = fixed[name]
    result["classification_at_0_5"] = fixed
    result.update({name: None for name in names[5:]})
    if thresholds is not None:
        f1_threshold, mcc_threshold = thresholds["f1"]["threshold"], thresholds["mcc"]["threshold"]
        f1 = weighted_classification_metrics(target, prediction, weight, threshold=f1_threshold)
        mcc = weighted_classification_metrics(target, prediction, weight, threshold=mcc_threshold)
        result["validation_f1_threshold"], result["validation_mcc_threshold"] = f1_threshold, mcc_threshold
        for name in ("precision", "recall", "f1", "mcc"):
            result[f"{name}_at_validation_f1_threshold"] = f1[name]
        result["mcc_at_validation_mcc_threshold"] = mcc["mcc"]
        result["f1_at_validation_mcc_threshold"] = mcc["f1"]
        result["classification_at_validation_f1_threshold"] = f1
        result["classification_at_validation_mcc_threshold"] = mcc
    return result
