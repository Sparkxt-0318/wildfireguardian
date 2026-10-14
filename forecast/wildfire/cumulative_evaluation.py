"""Evaluate explicit cumulative horizons against exact endpoint references.

Evaluation consumes reference outcomes after prediction. It never initializes
missing reference states, filters to cutoff-neighbor contact, tunes thresholds,
or combines overlapping horizons into a single score.
"""
from __future__ import annotations

from collections.abc import Mapping
import json
import math
from numbers import Real
from typing import Any

import numpy as np

from .cumulative import CumulativePrediction, _hours, _interval_targets
from .prediction import _array, _metadata_json, _support

__all__ = ["evaluate_cumulative"]


def _grid_argument(value, shape, name, *, boolean=False):
    """Permit only the documented scalar/spatial/full-shape organizations."""
    array = _array(value)
    if np.ma.isMaskedArray(array):
        raise ValueError(f"{name} must not be a masked array")
    if boolean:
        if array.dtype.kind != "b":
            raise TypeError(f"{name} must contain booleans")
        shapes = (shape[-2:], shape)
    else:
        if array.dtype.kind not in "iuf":
            raise TypeError(f"{name} must contain real numeric values excluding booleans")
        shapes = ((), shape[-2:], shape)
        with np.errstate(over="ignore", invalid="ignore"):
            array = array.astype(np.float64, copy=False)
        if not np.isfinite(array).all() or (array < 0).any():
            raise ValueError(f"{name} must contain finite nonnegative values")
    if array.shape not in shapes:
        qualifier = "[H,W] or the original prediction shape" if boolean else "a scalar, [H,W], or the original prediction shape"
        raise ValueError(f"{name} must have {qualifier} {shape}; no horizon axis is accepted")
    return np.broadcast_to(array, shape)


def _sum_weight(weight, mask):
    with np.errstate(over="ignore", invalid="ignore"):
        total = float(weight[mask].sum(dtype=np.float64))
    if not math.isfinite(total):
        raise ValueError("Selected weight total must be finite")
    return total


def _score(target, probability, weight, threshold):
    from .metrics import (
        LOG_LOSS_EPSILON, probability_metrics_with_all,
        weighted_calibration, weighted_classification_metrics,
    )

    # Neighbor counts in this wrapper affect only one-hour contact diagnostics.
    # Cumulative evaluation has no contact restriction or inferred contact
    # counts, so those diagnostics are removed from the public result below.
    with np.errstate(over="ignore", invalid="ignore"):
        metrics = probability_metrics_with_all(target, probability, weight, np.zeros(len(target)))
    metrics = {name: value for name, value in metrics.items() if not name.startswith("zero_contact_")}
    if len(target):
        # These Bernoulli helpers use normalized weights internally. Reuse their
        # equivalent hard-label scores to avoid an overflowing weighted log sum.
        metrics["exact_negative_log_likelihood_mean"] = metrics["bernoulli_kl_divergence_mean"]
        metrics["clipped_log_loss"] = metrics["floored_bernoulli_kl_divergence_mean"]
        classification = weighted_classification_metrics(target, probability, weight, threshold=threshold)
        tp, fp, tn, fn = (classification[name] for name in ("tp", "fp", "tn", "fn"))
        total = float(weight.sum(dtype=np.float64))
        specificity = tn / (tn + fp) if tn + fp else 0.0
        # Sum normalized correct-class masses without overflowing raw counts.
        accuracy = tp / total + tn / total
        union = tp + fp + fn
        classification.update(
            accuracy=accuracy, specificity=specificity,
            balanced_accuracy=(classification["recall"] + specificity) / 2,
            intersection_over_union=tp / union if union else 0.0,
        )
        calibration = weighted_calibration(target, probability, weight)
    else:
        metrics.update(
            positive_sample_count=0, positive_population_weight=0.0,
            sample_positive_fraction=None, weighted_prevalence=None, mean_probability=None,
            positive_class_brier=None, negative_class_brier=None,
            unsupported_positive_sample_count=0, unsupported_positive_population_weight=0.0,
            wrong_probability_one_negative_sample_count=0,
            classification_at_0_5=None,
        )
        classification = dict.fromkeys(
            ("precision", "recall", "f1", "mcc", "accuracy", "specificity",
             "balanced_accuracy", "intersection_over_union"), None,
        )
        classification.update(tp=0.0, fp=0.0, tn=0.0, fn=0.0, threshold=threshold)
        calibration = dict(bins=[], weighted_expected_calibration_error=None,
                           interpretation="Empty evaluation cohort; calibration is undefined")
    metrics.setdefault("log_loss_probability_floor", LOG_LOSS_EPSILON)
    return metrics, classification, calibration


def evaluate_cumulative(
    prediction: CumulativePrediction,
    observed: Mapping[str, Any],
    *,
    hours,
    quantity: str = "new_burn",
    coverage: str = "per_horizon",
    weight=None,
    threshold: float = 0.5,
    cohort_mask=None,
) -> dict[str, Any]:
    """Return JSON-compatible scores at explicitly entered forecast durations.

    ``hours`` is required: supply a positive duration or distinct durations
    already computed in ``prediction``. Their supplied order is retained.
    ``observed`` is a reference sample/batch of the same event and grid with
    binary cumulative ``burned_area``, its original ``burned_area_valid`` mask,
    and integer ``time_utc``. Only exact cutoff/endpoint timestamps are used.

    ``quantity='new_burn'`` evaluates ``probability`` on cells known unburned
    at the cutoff and known at the endpoint. ``quantity='burned'`` evaluates
    ``burned_probability`` against the known endpoint state, including initial
    burns; it does not require a known cutoff reference. Known 1-to-0 reference
    transitions are rejected. Missing reference states are never assumed zero.

    ``coverage='per_horizon'`` uses each horizon's available cohort.
    ``'shared'`` uses the intersection across the explicitly selected horizons.
    Each row retains its own reference/prediction coverage diagnostics. Scores
    pool cell-cutoff entries within a horizon, never across horizons.

    ``weight`` is None (unit weights), a finite nonnegative scalar, a spatial
    [H,W] map, or an array exactly matching one Prediction's probability shape.
    It has no horizon axis; zero weights exclude entries. ``cohort_mask`` is an
    optional boolean spatial/full-shape selection. Padding remains excluded.
    Classification uses ``probability >= threshold`` at the supplied finite
    threshold without fitting it to these outcomes.

    Distances compare per-cell Bernoulli predictions with binary outcomes on
    {0,1}; they do not measure geographic displacement or joint map distance.
    Exact zero/one Monte Carlo estimates are retained, including infinite exact
    log losses. Floored scores are reported separately. Monte Carlo confidence
    bounds are not confidence intervals for these evaluation metrics.

    References should describe the same cutoff and forecasting scenario as
    the prediction. The simulation's missing-initial-state assumption is kept
    in the report metadata and is not applied to observed reference states.
    """
    if not isinstance(prediction, CumulativePrediction):
        raise TypeError("prediction must be a CumulativePrediction")
    if not isinstance(observed, Mapping):
        raise TypeError("observed must be a reference sample or batch mapping")
    selected_hours = _hours(hours)
    for hour in selected_hours:
        prediction.at(hours=hour)
    if quantity not in ("new_burn", "burned"):
        raise ValueError("quantity must be 'new_burn' or 'burned'")
    if coverage not in ("per_horizon", "shared"):
        raise ValueError("coverage must be 'per_horizon' or 'shared'")
    if (not isinstance(threshold, Real) or isinstance(threshold, (bool, np.bool_))
            or not math.isfinite(float(threshold))):
        raise ValueError("threshold must be a finite real number excluding booleans")
    threshold = float(threshold)
    first = prediction.at(hours=selected_hours[0])
    shape = tuple(first.probability.shape)
    support, _, _ = _support(shape, first._pixel_valid, first._time_valid)
    weights = np.ones(shape, dtype=np.float64) if weight is None else _grid_argument(weight, shape, "weight")
    selection = np.ones(shape, dtype=bool) if cohort_mask is None else _grid_argument(cohort_mask, shape, "cohort_mask", boolean=True)
    candidates = support & selection & (weights > 0)
    _sum_weight(weights, candidates)
    field = "probability" if quantity == "new_burn" else "burned_probability"
    rows = []
    for hour in selected_hours:
        forecast = prediction.at(hours=hour)
        value = getattr(forecast, field)
        if value is None:
            raise ValueError(f"quantity='burned' requires {field} in every evaluated horizon")
        probabilities = _array(value)
        valid = _array(forecast.valid)
        if (np.ma.isMaskedArray(probabilities) or probabilities.dtype.kind not in "iuf"
                or tuple(probabilities.shape) != shape):
            raise ValueError(f"{field} must be a real array of the original prediction shape")
        if np.ma.isMaskedArray(valid) or valid.dtype.kind != "b" or tuple(valid.shape) != shape:
            raise ValueError("Prediction valid must be a boolean array of the complete prediction shape")
        if np.any(valid & (~np.isfinite(probabilities) | (probabilities < 0) | (probabilities > 1))):
            raise ValueError(f"{field} is nonfinite or outside [0,1] on declared prediction coverage at hours={hour:g}")
        start, start_valid, end, end_valid = prediction._aligned_burned_states(observed, hours=hour)
        interval, interval_valid = _interval_targets(start, start_valid, end, end_valid)
        if quantity == "new_burn":
            target = interval
            reference_valid = interval_valid & (start == 0)
            initially_burned_excluded = candidates & start_valid & (start == 1)
        else:
            target, reference_valid = end, end_valid
            initially_burned_excluded = np.zeros(shape, dtype=bool)
        eligible = candidates & reference_valid
        covered = eligible & valid
        rows.append(dict(hours=hour, target=target, probability=np.asarray(probabilities, dtype=np.float64),
                         eligible=eligible, covered=covered, initially_burned_excluded=initially_burned_excluded))
    shared = np.logical_and.reduce([row["covered"] for row in rows]) if coverage == "shared" else None
    results = []
    for row in rows:
        evaluated = row["covered"] if shared is None else shared
        eligible_weight = _sum_weight(weights, row["eligible"])
        covered_weight = _sum_weight(weights, row["covered"])
        evaluated_weight = _sum_weight(weights, evaluated)
        metrics, classification, calibration = _score(
            row["target"][evaluated].astype(np.float64), row["probability"][evaluated],
            weights[evaluated], threshold,
        )
        counts = dict(
            physical_support_cells=int(support.sum()), candidate_cells=int(candidates.sum()),
            reference_eligible_cells=int(row["eligible"].sum()), reference_eligible_weight=eligible_weight,
            prediction_covered_cells=int(row["covered"].sum()), prediction_covered_weight=covered_weight,
            evaluated_cells=int(evaluated.sum()), evaluated_weight=evaluated_weight,
            coverage_fraction=evaluated_weight / eligible_weight if eligible_weight else None,
            prediction_coverage_fraction=covered_weight / eligible_weight if eligible_weight else None,
            reference_unavailable_or_ineligible_cells=int((candidates & ~row["eligible"]).sum()),
            prediction_unavailable_cells=int((row["eligible"] & ~row["covered"]).sum()),
            excluded_by_shared_coverage_cells=int((row["covered"] & ~evaluated).sum()),
            initially_burned_excluded_cells=int(row["initially_burned_excluded"].sum()),
            zero_weight_excluded_cells=int((support & selection & (weights == 0)).sum()),
        )
        results.append(dict(hours=row["hours"], coverage=counts, metrics=metrics,
                            classification=classification, calibration=calibration))
    metadata = None if prediction.metadata is None else json.loads(_metadata_json(prediction.metadata))
    protocol = dict(
        quantity=quantity, probability_field=field, coverage=coverage,
        cohort="known_unburned_at_cutoff_and_known_endpoint" if quantity == "new_burn" else "known_endpoint",
        hours=list(selected_hours), threshold=threshold,
        prediction_shape=list(shape),
        event_id=None if prediction.event_id is None else _array(prediction.event_id).tolist(),
        cutoff_time_utc=None if prediction.time_utc is None else _array(prediction.time_utc).tolist(),
        weighting="equal_cell_cutoff" if weight is None else "caller_supplied",
        aggregation="pooled_cell_cutoff_entries_within_each_horizon",
        cutoff_neighbor_contact_required=False, reference_initialization="original_validity_masks",
        endpoint_alignment="exact_t_plus_hours", threshold_selection="caller_supplied_not_fitted_here",
        probability_distance_reference="per_cell_binary_observed_outcome",
        distance_ground_space="binary_outcome_0_1_with_unit_distance",
        logarithm_base="natural", classification_zero_division=0,
        monte_carlo_intervals_are_metric_intervals=False, prediction_metadata=metadata,
    )
    return dict(protocol=protocol, per_horizon=results)
