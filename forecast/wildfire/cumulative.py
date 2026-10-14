"""First-new-burn probabilities for explicitly requested forecast horizons.

Results may describe recursive binary trajectory simulations or explicitly
fixed-state horizons. Method and simulation assumptions are recorded in result
metadata. Reference outcomes are accessed only by comparison/alignment methods.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
import math
from numbers import Real
from typing import Any

import numpy as np

from .prediction import Prediction, _array, _metadata_json, _OPTIONAL_OUTPUT_FIELDS

__all__ = ["CumulativePrediction"]


def _hour(value) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise TypeError("hours must contain real numbers, excluding booleans and strings")
    try:
        value = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError("hours must contain finite positive values representable as floats") from error
    if not math.isfinite(value) or value <= 0:
        raise ValueError("hours must contain finite positive values")
    return value


def _hours(values) -> tuple[float, ...]:
    """Normalize one horizon or a nonempty iterable, retaining supplied order."""
    if isinstance(values, Real) and not isinstance(values, (bool, np.bool_)):
        values = (values,)
    elif isinstance(values, (str, bytes, bool, np.bool_)):
        raise TypeError("hours must be a real number or an iterable of real numbers")
    else:
        try:
            values = iter(values)
        except TypeError as error:
            raise TypeError("hours must be a real number or an iterable of real numbers") from error
    result = tuple(_hour(value) for value in values)
    if not result:
        raise ValueError("hours must contain at least one forecast horizon")
    if len(set(result)) != len(result):
        raise ValueError("hours must contain unique forecast horizons")
    return result


def _same_metadata(first, second):
    if first is None or second is None:
        return first is None and second is None
    left, right = _array(first), _array(second)
    if left.dtype.kind in "fc" and right.dtype.kind in "fc":
        return np.array_equal(left, right, equal_nan=True)
    return np.array_equal(left, right)


def _interval_targets(start, start_valid, end, end_valid):
    valid = start_valid & end_valid
    if np.any(valid & (end < start)):
        raise ValueError("Known cumulative burned_area must be nondecreasing between cutoff and endpoint")
    return np.where(valid, (start == 0) & (end == 1), np.nan), valid


@dataclass(frozen=True)
class CumulativePrediction:
    """A frozen container of cumulative first-new-burn probabilities.

    ``hours`` is a tuple of distinct positive horizons in the supplied order.
    Probability, validity, rate and rate validity have shape
    ``[N, *prediction.shape]``, with the new first dimension indexing horizons.
    Optional total burned probability and Monte Carlo uncertainty use the same
    shape and probability validity mask. Confidence bounds describe new burns.
    Fixed-state rates have inverse-hour units; Bayesian rates are equivalent
    interval rates. Recursive aggregate rates are unavailable. Method and
    simulation assumptions are in ``metadata``. Coordinates and cutoff
    timestamps retain their original static organization and have no added
    horizon dimension.

    Select by horizon value with ``at(hours=3)`` or plot directly with
    ``plot(hours=3, index=...)``. Plot indices address the original prediction's
    time/batch dimensions; they do not address the horizon dimension.
    """

    hours: tuple[float, ...]
    _predictions: tuple[Prediction, ...] = field(repr=False)
    probability: Any = field(init=False, repr=False)
    valid: Any = field(init=False, repr=False)
    rate: Any = field(init=False, repr=False)
    rate_valid: Any = field(init=False, repr=False)
    burned_probability: Any = field(init=False, default=None, repr=False)
    mc_standard_error: Any = field(init=False, default=None, repr=False)
    confidence_lower: Any = field(init=False, default=None, repr=False)
    confidence_upper: Any = field(init=False, default=None, repr=False)

    def __post_init__(self):
        import torch

        hours = _hours(self.hours)
        predictions = tuple(self._predictions)
        if len(predictions) != len(hours):
            raise ValueError("Each requested horizon requires exactly one Prediction")
        if any(not isinstance(prediction, Prediction) for prediction in predictions):
            raise TypeError("_predictions must contain Prediction objects")
        first = predictions[0]
        shape = tuple(first.probability.shape)
        for hour, prediction in zip(hours, predictions):
            if not np.all(_array(prediction.dt_hours) == hour):
                raise ValueError("Prediction.dt_hours must equal its corresponding requested horizon")
            for name in ("probability", "valid", "rate", "rate_valid"):
                if tuple(getattr(prediction, name).shape) != shape:
                    raise ValueError("All cumulative prediction fields must share the original prediction shape")
            for name in _OPTIONAL_OUTPUT_FIELDS:
                value, initial = getattr(prediction, name), getattr(first, name)
                if (value is None) != (initial is None):
                    raise ValueError(f"Cumulative prediction horizons must consistently supply {name}")
                if value is not None and tuple(value.shape) != shape:
                    raise ValueError(f"{name} must share the original prediction shape")
            for name in ("coordinates", "time_utc", "event_id", "_affine_transform", "_epsg",
                         "_time_valid", "_pixel_valid"):
                if not _same_metadata(getattr(first, name), getattr(prediction, name)):
                    raise ValueError(f"Cumulative prediction horizons must share {name} metadata")
            if (first.metadata is None) != (prediction.metadata is None) or (
                first.metadata is not None
                and _metadata_json(first.metadata) != _metadata_json(prediction.metadata)
            ):
                raise ValueError("Cumulative prediction horizons must share result metadata")
        object.__setattr__(self, "hours", hours)
        object.__setattr__(self, "_predictions", predictions)
        for name in ("probability", "valid", "rate", "rate_valid"):
            values = tuple(getattr(prediction, name) for prediction in predictions)
            object.__setattr__(self, name, torch.stack(values, dim=0))
        for name in _OPTIONAL_OUTPUT_FIELDS:
            if getattr(first, name) is not None:
                values = tuple(getattr(prediction, name) for prediction in predictions)
                object.__setattr__(self, name, torch.stack(values, dim=0))

    @property
    def coordinates(self):
        """Static WGS84 coordinates, without a forecast-horizon dimension."""
        return self._predictions[0].coordinates

    @property
    def time_utc(self):
        """Original prediction cutoffs, without a forecast-horizon dimension."""
        return self._predictions[0].time_utc

    @property
    def event_id(self):
        return self._predictions[0].event_id

    @property
    def metadata(self):
        """An independent copy of the shared method and simulation metadata."""
        return deepcopy(self._predictions[0].metadata)

    def at(self, *, hours) -> Prediction:
        """Return the Prediction for an exactly requested horizon value."""
        selected = _hour(hours)
        try:
            index = self.hours.index(selected)
        except ValueError as error:
            raise ValueError(
                f"hours={selected:g} was not requested; available horizons are {self.hours}"
            ) from error
        return self._predictions[index]

    def numpy(self) -> dict[str, np.ndarray]:
        """Copy outputs and horizons; export shared metadata as scalar JSON."""
        result = {
            name: np.array(_array(getattr(self, name)), copy=True)
            for name in ("probability", "valid", "rate", "rate_valid")
        }
        result["hours"] = np.array(self.hours, dtype=float, copy=True)
        for name in _OPTIONAL_OUTPUT_FIELDS:
            if getattr(self, name) is not None:
                result[name] = np.array(_array(getattr(self, name)), copy=True)
        for name in ("coordinates", "time_utc"):
            if getattr(self, name) is not None:
                result[name] = np.array(_array(getattr(self, name)), copy=True)
        if self.metadata is not None:
            result["metadata_json"] = np.array(_metadata_json(self.metadata), copy=True)
        return result

    def plot(self, *, hours, index=None, **options):
        """Plot first-new-burn probability q within one requested horizon.

        The method and environmental assumptions are recorded in ``metadata``.
        ``index`` selects the original prediction's time/batch dimensions,
        with Prediction.plot() semantics.
        """
        prediction = self.at(hours=hours)
        hour = _hour(hours)
        options.setdefault("title", f"Probability q: first new burn within {hour:g} h")
        options.setdefault("colorbar_label", f"First-new-burn probability q within {hour:g} h")
        return prediction.plot(index=index, **options)

    def _aligned_burned_states(self, observed, *, hours):
        prediction = self.at(hours=hours)
        promoted = (
            len(prediction.probability.shape) == 3 and isinstance(observed, Mapping)
            and _array(observed["burned_area"]).ndim == 4
        )
        if promoted:
            # A snapshot needs both cutoff and endpoint rows from a reference
            # timeline. Add a temporary singleton time axis for the shared
            # exact-time alignment, while retaining the public snapshot shape.
            fields = {name: getattr(prediction, name).unsqueeze(0)
                      for name in ("probability", "valid", "rate", "rate_valid")}
            fields.update({name: getattr(prediction, name).unsqueeze(0)
                           for name in _OPTIONAL_OUTPUT_FIELDS
                           if getattr(prediction, name) is not None})
            prediction = replace(
                prediction, **fields,
                time_utc=(None if prediction.time_utc is None
                          else np.asarray(prediction.time_utc).reshape(1)),
                _time_valid=(np.ones(1, dtype=bool) if prediction._time_valid is None
                             else np.asarray(prediction._time_valid).reshape(1)),
            )
        start, start_valid = prediction.aligned_burned_area(observed)
        seconds = _hour(hours) * 3600
        if not seconds.is_integer():
            # Check before adding the offset to a large Unix timestamp: a tiny
            # fractional offset could otherwise round back to an integer.
            end = np.full_like(start, np.nan)
            end_valid = np.zeros_like(start_valid)
        else:
            end, end_valid = prediction._aligned_sample_field(
                observed, "burned_area", "burned_area_valid", offset_seconds=int(seconds),
            )
        states = (start, start_valid, end, end_valid)
        return tuple(state[0] for state in states) if promoted else states

    def aligned_observations(self, observed: Mapping[str, Any], *, hours) -> tuple[np.ndarray, np.ndarray]:
        """Align cumulative reference new burns in (t, t+hours].

        The reference event is a cell unburned at the exact cutoff t and burned
        at the exact endpoint t+hours*3600 seconds. Both burned-area states must
        be known. Missing endpoints remain NaN/invalid. Fixed-state predictions
        can use fractional horizons; no timestamp is rounded or truncated, so a noninteger-second
        endpoint cannot match integer Unix-second source timestamps. Known
        cumulative states may not change from burned to unburned.

        A snapshot prediction with shape [1,H,W] can align a reference timeline
        with shape [T,1,H,W]; its aligned targets retain shape [1,H,W].

        These reference states may be retrospective reconstructions. They are
        used only for evaluation/display, never for cumulative prediction.
        """
        return _interval_targets(*self._aligned_burned_states(observed, hours=hours))

    def evaluate(
        self, observed: Mapping[str, Any], *, hours, quantity="new_burn",
        coverage="per_horizon", weight=None, threshold=0.5, cohort_mask=None,
    ) -> dict[str, Any]:
        """Score explicitly entered durations against exact reference endpoints.

        New-burn scoring excludes cells already burned at the cutoff and
        unavailable reference states. Total burned scoring uses known endpoint
        occupancy. Returns per-horizon metrics, Bernoulli distances,
        classification, calibration and coverage; no threshold is fitted here.
        See evaluate_cumulative() for the complete evaluation protocol.
        """
        from .cumulative_evaluation import evaluate_cumulative
        return evaluate_cumulative(
            self, observed, hours=hours, quantity=quantity, coverage=coverage,
            weight=weight, threshold=threshold, cohort_mask=cohort_mask,
        )

    def compare(
        self, observed, *, hours, observed_valid=None, burned_area=None,
        burned_area_valid=None, index=None, mode="overlay", **options,
    ):
        """Compare cumulative new burns and probability q within a horizon.

        A sample mapping supplies cumulative burned_area states at the exact
        cutoff and endpoint; its hourly newly_burned_area labels are not used.
        Explicit arrays must already describe the whole requested interval.
        Prior burns, hollow event markers, probability masks and the complete
        loaded-region outline retain Prediction.compare() plotting options.
        """
        prediction = self.at(hours=hours)
        hour = _hour(hours)
        is_sample = isinstance(observed, Mapping)
        if is_sample:
            if observed_valid is not None:
                raise ValueError("Observed samples supply their own validity masks")
            sample = observed
            states = self._aligned_burned_states(sample, hours=hour)
            observed, observed_valid = _interval_targets(*states)
            if burned_area is None:
                if burned_area_valid is not None:
                    raise ValueError("burned_area_valid requires burned_area")
                burned_area, burned_area_valid = states[:2]
        options.setdefault("event_label", f"Newly burned within {hour:g} h")
        reference_name = "Reconstructed" if is_sample else "Reference"
        options.setdefault("titles", (
            f"{reference_name} new burns within {hour:g} h",
            f"Predicted probability q within {hour:g} h",
            f"Previous burns and new burns within {hour:g} h\nOver predicted probability q",
        ))
        return prediction.compare(
            observed, observed_valid=observed_valid, burned_area=burned_area,
            burned_area_valid=burned_area_valid, index=index, mode=mode, **options,
        )
