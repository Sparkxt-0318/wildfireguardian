"""Import and score an explicitly timed, deterministic FARSITE scenario.

This module consumes simulator output; it never constructs a simulator run or
uses reconstructed reference arrival labels as simulated predictions. A single
run supplies binary occupancy, represented as a degenerate Bernoulli forecast.
Its uncertainty is not estimated by Monte Carlo sampling.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import math
from numbers import Integral, Real
from types import SimpleNamespace

import numpy as np

from .cumulative import CumulativePrediction, _hours
from .cumulative_evaluation import evaluate_cumulative
from .prediction import Prediction, _array, _metadata_json, _support, _times

__all__ = ["farsite_cumulative_prediction", "evaluate_farsite", "summarize_farsite"]


def _origin_seconds(value):
    if isinstance(value, (bool, np.bool_)):
        raise TypeError("arrival_origin_time_utc must be integer Unix seconds or an ISO timestamp with UTC offset")
    if isinstance(value, Integral):
        seconds = int(value)
    elif isinstance(value, str):
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("arrival_origin_time_utc must be an ISO timestamp with UTC offset") from error
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("arrival_origin_time_utc must contain a UTC offset")
        timestamp = timestamp.astimezone(timezone.utc)
        if timestamp.microsecond:
            raise ValueError("arrival_origin_time_utc must use whole Unix seconds")
        seconds = int(timestamp.timestamp())
    else:
        raise TypeError("arrival_origin_time_utc must be integer Unix seconds or an ISO timestamp with UTC offset")
    if seconds < 0:
        raise ValueError("arrival_origin_time_utc must be nonnegative Unix seconds")
    return seconds


def _original_grid(value, shape, name, *, boolean=False):
    array = _array(value)
    if np.ma.isMaskedArray(array):
        raise ValueError(f"{name} must not be a masked array")
    if boolean:
        if array.dtype.kind != "b":
            raise TypeError(f"{name} must contain booleans")
    elif array.dtype.kind not in "iuf":
        raise TypeError(f"{name} must contain real numeric values excluding booleans")
    if tuple(array.shape) not in (shape[-2:], shape):
        raise ValueError(f"{name} must have the original [H,W] shape {shape[-2:]} or complete prediction shape {shape}")
    return np.array(np.broadcast_to(array, shape), copy=True)


def farsite_cumulative_prediction(
    arrival_time_minutes,
    cutoff_sample: Mapping,
    *,
    hours,
    arrival_origin_time_utc,
    no_burn_value,
    coverage,
    metadata: Mapping | None = None,
    _exact_duration_minutes: int | None = None,
) -> CumulativePrediction:
    """Return absorbing, deterministic predictions on the original rectangle.

    ``arrival_time_minutes`` is simulator elapsed time relative to the explicit
    ``arrival_origin_time_utc``. It and boolean ``coverage`` have [H,W] or the
    cutoff burned-state's full [...,1,H,W] shape. They must already be aligned
    to the cutoff grid: this function does not crop, resample, or reproject.
    The caller is responsible for confirming the simulator's CRS and transform.

    A finite negative ``no_burn_value`` is the documented simulator no-arrival
    sentinel. It means unburned only where the separate coverage mask declares
    a successfully simulated domain. Every other arrival on that domain must
    be finite and nonnegative. Unknown domain cells remain unavailable even
    when initially burned. Time/spatial padding stays unavailable.

    Initial missing burned observations are initialized as zero within physical
    support. Known states must be binary. Total occupancy is the union of that
    initial state and simulated arrivals at or before the exact horizon endpoint;
    new-burn probability is zero on initial burns. Consequently arrival zero is
    included in every positive horizon. If simulated ignition extends beyond
    the observed cutoff raster, those cells are included explicitly rather than
    silently erased. Reference masks are never modified by this initialization.

    One run has no sampling distribution: rate, Monte Carlo standard errors,
    and confidence bounds are unavailable. Numerical arrays use CPU float64;
    all inputs and exported arrays are independent copies.
    """
    import torch

    if not isinstance(cutoff_sample, Mapping):
        raise TypeError("cutoff_sample must be a prediction-cutoff sample mapping")
    if "burned_area" not in cutoff_sample or "time_utc" not in cutoff_sample:
        raise ValueError("cutoff_sample requires burned_area and exact time_utc")
    burned = _array(cutoff_sample["burned_area"])
    if np.ma.isMaskedArray(burned) or burned.dtype.kind not in "biuf":
        raise TypeError("burned_area must be an unmasked real binary-state array")
    shape = tuple(burned.shape)
    if len(shape) < 3 or shape[-3] != 1 or min(shape[-2:]) < 1:
        raise ValueError("burned_area must have shape [...,1,H,W] with a nonempty original rectangle")
    support, temporal, spatial = _support(shape, cutoff_sample.get("pixel_valid"), cutoff_sample.get("time_valid"))
    cutoff_times = _times(cutoff_sample["time_utc"], shape[:-3], "time_utc")
    if np.any(temporal & (cutoff_times < 0)):
        raise ValueError("Valid cutoff time_utc entries must be nonnegative Unix seconds")
    origin = _origin_seconds(arrival_origin_time_utc)
    if np.any(temporal & (cutoff_times < origin)):
        raise ValueError("arrival_origin_time_utc must not be after a valid prediction cutoff")
    horizons = _hours(hours)
    if _exact_duration_minutes is not None:
        if (isinstance(_exact_duration_minutes, (bool, np.bool_))
                or not isinstance(_exact_duration_minutes, Integral)
                or _exact_duration_minutes <= 0 or len(horizons) != 1
                or not math.isclose(horizons[0] * 60, _exact_duration_minutes,
                                    rel_tol=0, abs_tol=1e-8)):
            raise ValueError("Exact observed duration must be a positive integer number of minutes matching one horizon")
        _exact_duration_minutes = int(_exact_duration_minutes)
    if (not isinstance(no_burn_value, Real) or isinstance(no_burn_value, (bool, np.bool_))
            or not math.isfinite(float(no_burn_value)) or no_burn_value >= 0):
        raise ValueError("no_burn_value must be the documented finite negative simulator no-arrival sentinel")
    no_burn_value = float(no_burn_value)
    arrival = _original_grid(arrival_time_minutes, shape, "arrival_time_minutes")
    domain = _original_grid(coverage, shape, "coverage", boolean=True) & support
    no_arrival = arrival == no_burn_value
    if np.any(domain & ~no_arrival & (~np.isfinite(arrival) | (arrival < 0))):
        raise ValueError("arrival_time_minutes must be finite and nonnegative on declared coverage, except the explicit no_burn_value")
    known = np.isfinite(burned)
    if "burned_area_valid" in cutoff_sample:
        mask = _array(cutoff_sample["burned_area_valid"])
        if np.ma.isMaskedArray(mask) or mask.dtype.kind != "b" or tuple(mask.shape) != shape:
            raise ValueError(f"burned_area_valid must be boolean with exact complete shape {shape}")
        if np.any(support & mask & ~np.isfinite(burned)):
            raise ValueError("Known burned_area entries must be finite binary states")
        known &= mask
    if np.any(support & known & (burned != 0) & (burned != 1)):
        raise ValueError("Known burned_area entries must be binary zero or one")
    initial = support & known & (burned == 1)
    details_metadata = dict(
        method="farsite_deterministic", model_family="FARSITE", scenario_count=1,
        output_interpretation="degenerate Bernoulli occupancy from one deterministic simulator scenario",
        uncertainty_interpretation="No Monte Carlo sampling or probability calibration; simulation intervals unavailable",
        arrival_units="minutes", arrival_origin_time_utc=origin, no_burn_value=no_burn_value,
        arrival_endpoint="inclusive_at_exact_cutoff_plus_hours",
        initial_ignition_policy="observed_initial_burn_union_simulated_arrivals_including_zero",
        missing_burned_area="unburned", unavailable_domain="excluded_by_explicit_coverage",
        full_rectangle=True, grid_alignment="caller_verified_no_resampling_in_importer",
    )
    if metadata is not None:
        if not isinstance(metadata, Mapping):
            raise TypeError("metadata must be a mapping")
        for name, value in metadata.items():
            if name in details_metadata and value != details_metadata[name]:
                raise ValueError(f"metadata must not override deterministic import field {name!r}")
        details_metadata.update(deepcopy(dict(metadata)))
    if _exact_duration_minutes is not None:
        details_metadata["exact_duration_minutes"] = _exact_duration_minutes
    _metadata_json(details_metadata)
    offset_minutes = ((cutoff_times - origin) / 60).reshape(shape[:-3] + (1, 1, 1))
    predictions = []
    for hour in horizons:
        duration_minutes = hour * 60 if _exact_duration_minutes is None else _exact_duration_minutes
        endpoint_minutes = offset_minutes + duration_minutes
        if not np.isfinite(endpoint_minutes).all():
            raise ValueError("hours must give finite arrival-time endpoints")
        total = initial | (domain & ~no_arrival & (arrival <= endpoint_minutes))
        new_burn = ~initial & total
        probability = torch.from_numpy(new_burn.astype(np.float64))
        valid = torch.from_numpy(domain.copy())
        details = SimpleNamespace(probability=probability, valid=valid,
                                  rate=torch.full_like(probability, torch.nan),
                                  rate_valid=torch.zeros_like(valid))
        predictions.append(Prediction.from_details(
            details, dt_hours=hour, burned_probability=torch.from_numpy(total.astype(np.float64)),
            affine_transform=cutoff_sample.get("affine_transform"), epsg=cutoff_sample.get("epsg"),
            pixel_valid=spatial, time_valid=temporal, time_utc=cutoff_times,
            event_id=cutoff_sample.get("event_id"), metadata=details_metadata,
        ))
    return CumulativePrediction(horizons, tuple(predictions))


def evaluate_farsite(arrival_time_minutes, cutoff_sample, observed, *, hours,
                     arrival_origin_time_utc, no_burn_value, coverage,
                     metadata=None, threshold=.5, cohort_mask=None):
    """Import simulator output, then score both quantities on original truth.

    Returns ``(prediction, {'new_burn': report, 'burned': report})``. The observed
    timeline is consulted only after import and never initializes a simulation.
    ``hours`` is required and retains the requested horizon order.
    """
    prediction = farsite_cumulative_prediction(
        arrival_time_minutes, cutoff_sample, hours=hours,
        arrival_origin_time_utc=arrival_origin_time_utc,
        no_burn_value=no_burn_value, coverage=coverage, metadata=metadata,
    )
    reports = {quantity: evaluate_cumulative(
        prediction, observed, hours=prediction.hours, quantity=quantity,
        threshold=threshold, cohort_mask=cohort_mask,
    ) for quantity in ("new_burn", "burned")}
    return prediction, reports


def summarize_farsite(prediction, observed, *, hours, model_id="FARSITE", threshold=.5,
                      cohort_mask=None):
    """Return current report rows and pooled entries for one explicit horizon.

    Returns ``(rows, entries)`` where rows have the cumulative report's summary
    schema and entries are keyed by ``(cohort, quantity)``. Native and shared
    cohorts are both included. Without an additional mask their entries match;
    a multi-model comparison must supply the actual intersection mask and
    rescore every participating model on it.
    """
    from .cumulative_report import _pool, _score_case

    selected = _hours(hours)
    if len(selected) != 1:
        raise ValueError("summarize_farsite requires exactly one explicit horizon")
    hour = selected[0]
    rows, entries = [], {}
    for quantity in ("new_burn", "burned"):
        native, native_entries = _score_case(prediction, observed, hour, quantity=quantity, threshold=threshold)
        shared, shared_entries = _score_case(prediction, observed, hour, quantity=quantity,
                                            threshold=threshold, cohort_mask=cohort_mask)
        counts = dict(reference_eligible_cells=native["per_horizon"][0]["coverage"]["reference_eligible_cells"],
                      native_prediction_covered_cells=native["per_horizon"][0]["coverage"]["evaluated_cells"],
                      shared_evaluated_cells=shared["per_horizon"][0]["coverage"]["evaluated_cells"])
        denominator = counts["reference_eligible_cells"]
        for cohort, values in (("native", native_entries), ("shared_models", shared_entries)):
            entries[(cohort, quantity)] = {name: value.copy() for name, value in values.items()}
            rows.append(dict(model_id=str(model_id), event="ALL", hours=hour, cohort=cohort, quantity=quantity,
                             **counts, native_coverage_fraction=counts["native_prediction_covered_cells"] / denominator if denominator else None,
                             shared_retention_fraction=counts["shared_evaluated_cells"] / denominator if denominator else None,
                             **_pool([values], threshold)))
    return rows, entries
