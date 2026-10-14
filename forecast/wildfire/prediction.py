"""Public prediction results and exact next-hour outcome alignment.

Plotting is imported only when requested. Reference fields are aligned only
for comparison; future outcome labels are never read by model inference.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Mapping
import json
from typing import Any

import numpy as np


_OPTIONAL_OUTPUT_FIELDS = (
    "burned_probability", "mc_standard_error", "confidence_lower", "confidence_upper",
)


def _metadata_json(value):
    """Serialize result metadata as JSON that needs no NumPy pickle support."""
    if not isinstance(value, Mapping):
        raise TypeError("Prediction metadata must be a mapping")
    return json.dumps(dict(value), ensure_ascii=False, sort_keys=True, allow_nan=False)


def _array(value):
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asanyarray(value)


def _metadata_array(value, name):
    array = _array(value)
    if np.any(np.ma.getmaskarray(array)):
        raise ValueError(f"{name} must not contain masked values")
    return np.array(array, copy=True)


def _times(value, leading, name):
    value = _array(value)
    if value.dtype.kind not in "iu" or np.ma.isMaskedArray(value):
        raise ValueError(f"{name} must contain integer Unix seconds")
    if not leading and value.size == 1:
        value = value.reshape(())
    if value.shape != leading:
        raise ValueError(f"{name} must match the time/batch dimensions {leading}")
    return np.asarray(value).copy()


def _time_mask(value, leading):
    mask = np.ones(leading, dtype=bool) if value is None else _array(value)
    if not leading and mask.size == 1:
        mask = mask.reshape(())
    if mask.dtype.kind != "b" or mask.shape != leading or np.ma.isMaskedArray(mask):
        raise ValueError(f"time_valid must be boolean with shape {leading}")
    return np.asarray(mask).copy()


def _pixel_mask(value, shape):
    # Static grids omit the final leading (time) and singleton channel axes.
    grid_shape = shape[:-4] + shape[-2:]
    if value is None:
        mask = np.ones(grid_shape, dtype=bool)
    else:
        mask = _array(value)
        if mask.dtype.kind != "b" or np.ma.isMaskedArray(mask):
            raise TypeError("pixel_valid must contain booleans")
        if mask.ndim == len(grid_shape) + 1 and mask.shape[-3] == 1:
            mask = np.squeeze(mask, axis=-3)
        try:
            mask = np.broadcast_to(mask, grid_shape)
        except ValueError as error:
            raise ValueError(f"pixel_valid must describe static grids with shape {grid_shape}") from error
    return np.asarray(mask).copy()


def _support(shape, pixel_valid=None, time_valid=None):
    leading = shape[:-3]
    temporal = _time_mask(time_valid, leading)
    spatial = _pixel_mask(pixel_valid, shape)
    spatial_shape = shape[:-4] + ((1, 1) if len(shape) >= 4 else (1,)) + shape[-2:]
    support = np.broadcast_to(spatial.reshape(spatial_shape), shape).copy()
    support &= temporal.reshape(leading + (1, 1, 1))
    return support, temporal, spatial


@dataclass(frozen=True)
class Prediction:
    """First new-burn probabilities with coverage, locations and diagnostics.

    Tensors have shape ``[...,1,H,W]`` and stay on the model's device. Rates
    use inverse hours; Bayesian rates are equivalent interval rates. Coordinates
    are optional CPU float64 tensors in WGS84 (latitude,longitude) degrees,
    shaped ``[H,W,2]`` for a sequence or ``[B,H,W,2]`` for a batch.
    Time/spatial padding has false validity and NaN numerical outputs.

    Optional ``burned_probability`` includes burns already present at the
    cutoff. Monte Carlo standard errors and confidence bounds describe
    ``probability``, the cumulative new-burn event, and share its validity.
    ``metadata`` records the method and available simulation assumptions.
    """

    probability: Any
    valid: Any
    rate: Any
    rate_valid: Any
    coordinates: Any = None
    time_utc: np.ndarray | None = None
    dt_hours: Any = 1.0
    event_id: Any = None
    _affine_transform: Any = field(default=None, repr=False)
    _epsg: Any = field(default=None, repr=False)
    _time_valid: Any = field(default=None, repr=False)
    _pixel_valid: Any = field(default=None, repr=False)
    burned_probability: Any = field(default=None, repr=False)
    mc_standard_error: Any = field(default=None, repr=False)
    confidence_lower: Any = field(default=None, repr=False)
    confidence_upper: Any = field(default=None, repr=False)
    metadata: Mapping[str, Any] | None = None

    @classmethod
    def from_details(
        cls, details, *, dt_hours=1.0, affine_transform=None, epsg=None,
        pixel_valid=None, time_valid=None, time_utc=None, event_id=None,
        burned_probability=None, mc_standard_error=None, confidence_lower=None,
        confidence_upper=None, metadata=None,
    ):
        import torch
        from copy import deepcopy

        shape = tuple(details.probability.shape)
        leading = shape[:-3]
        support, temporal, spatial = _support(shape, pixel_valid, time_valid)
        support_tensor = torch.as_tensor(support, device=details.probability.device)
        valid = details.valid & support_tensor
        rate_valid = details.rate_valid & support_tensor
        probability = torch.where(valid, details.probability, float("nan"))
        rate = torch.where(rate_valid, details.rate, float("nan"))
        optional = {}
        for name, value in zip(_OPTIONAL_OUTPUT_FIELDS, (
            burned_probability, mc_standard_error, confidence_lower, confidence_upper,
        )):
            if value is None:
                optional[name] = None
                continue
            if isinstance(value, torch.Tensor):
                if value.is_complex() or value.is_quantized:
                    raise TypeError(f"{name} must contain real numeric values")
            else:
                array = np.asanyarray(value)
                if np.any(np.ma.getmaskarray(array)):
                    raise ValueError(f"{name} must use the prediction validity mask")
                if array.dtype.kind not in "biuf":
                    raise TypeError(f"{name} must contain real numeric values")
            value = torch.as_tensor(
                value, device=probability.device, dtype=probability.dtype,
            )
            if tuple(value.shape) != shape:
                raise ValueError(f"{name} must match the complete prediction shape {shape}")
            optional[name] = torch.where(valid, value, float("nan"))
        if metadata is not None:
            _metadata_json(metadata)
            metadata = deepcopy(dict(metadata))
        coordinates = None
        transform = None if affine_transform is None else _metadata_array(affine_transform, "affine_transform")
        crs = None if epsg is None else _metadata_array(epsg, "epsg")
        if (transform is None) != (crs is None):
            raise ValueError("Supply both affine_transform and epsg, or neither")
        if transform is not None:
            from .coordinates import geographic_coordinates
            coordinates = torch.from_numpy(geographic_coordinates(
                shape[:-4] + shape[-2:], affine_transform=transform,
                epsg=crs, pixel_valid=spatial,
            ))
        times = None if time_utc is None else _times(time_utc, leading, "time_utc")
        if times is not None and np.any(temporal & (times < 0)):
            raise ValueError("Valid time_utc entries must be nonnegative Unix seconds")
        return cls(
            probability, valid, rate, rate_valid, coordinates, times,
            np.array(_array(dt_hours), copy=True), deepcopy(event_id),
            transform, crs, temporal, spatial,
            **optional, metadata=metadata,
        )

    def numpy(self) -> dict[str, np.ndarray]:
        """Copy numeric outputs to CPU NumPy arrays for analysis or export.

        Includes available total burned probability, Monte Carlo uncertainty,
        validity, horizon, coordinates and cutoff times. ``metadata_json`` is
        a scalar Unicode array, safe to save/load without pickle support.
        No unavailable value is filled with zero.
        """
        names = ("probability", "valid", "rate", "rate_valid", "coordinates", "time_utc", "dt_hours")
        names += _OPTIONAL_OUTPUT_FIELDS
        result = {name: np.array(_array(getattr(self, name)), copy=True)
                  for name in names if getattr(self, name) is not None}
        if self.metadata is not None:
            result["metadata_json"] = np.array(_metadata_json(self.metadata), copy=True)
        return result

    def plot(self, *, index=None, **options):
        """Plot one probability matrix; select time/batch with index.

        index addresses already computed predictions, not positions in the
        source dataset. A one-time prediction accepts index=0 or no index.
        To predict another loaded time, select_time(data, index=i) first.
        Returns ``(figure, axis)``; use figure.savefig(...) or plt.show().
        Options are those of wildfire.plot_matrix. Color limits default to 0,1.
        """
        from .plotting import plot_matrix
        options.setdefault("title", "Predicted new-burn probability q")
        options.setdefault("colorbar_label", "New-burn probability q")
        options.setdefault("vmin", 0.0)
        options.setdefault("vmax", 1.0)
        self._check_plot_index(index)
        return plot_matrix(self.probability, valid=self.valid, index=index, **options)

    def _check_plot_index(self, index):
        from .plotting import _select
        shape = tuple(self.probability.shape)
        # Validate the actual selection without copying the prediction tensor
        # or allocating an array proportional to the event's timeline.
        shape_only = np.broadcast_to(np.zeros((), dtype=np.uint8), shape)
        try:
            _select(shape_only, index)
        except IndexError as error:
            raise IndexError(
                f"{error}. Plot index selects this Prediction's shape {shape}, "
                "not the loaded event timeline. To predict another loaded time, use "
                "selected_sample = select_time(event_data, index=i), then "
                "model.predict(selected_sample).plot()."
            ) from error

    def aligned_observations(self, observed: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        """Align a dataset's hourly new-burn labels to forecast endpoints.

        A label stamped at s describes (s-3600,s]. A prediction stamped at t
        with dt_hours=1 describes (t,t+3600]. Consequently only a label stamped
        at exactly t+3600 is eligible. Missing endpoints are NaN/invalid.
        The input may be the original sequence or separately loaded endpoint
        snapshots of the same event and grid. Reconstructed labels remain
        retrospective reference outcomes. Non-hourly horizons require explicit
        binary targets instead of this hourly-label alignment.
        """
        if self.time_utc is None:
            raise ValueError("Sample comparison requires prediction time_utc; use model.predict(sample)")
        if not np.all(_array(self.dt_hours) == 1.0):
            raise ValueError("Hourly observed samples require dt_hours=1; supply explicit interval targets otherwise")
        return self._aligned_sample_field(
            observed, "newly_burned_area", "newly_burned_area_valid", offset_seconds=3600,
            fallback_validity="burned_area_valid",
        )

    def aligned_burned_area(self, observed: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        """Align cumulative burned area at each prediction's exact cutoff t.

        This reference state contains arrivals at or before t, whereas the
        next-hour outcomes describe arrivals in (t,t+3600]. Each field has its
        own validity mask. Missing cutoff timestamps remain NaN/invalid; a
        future or nearest state is never substituted. Event, grid and padding
        checks are the same as for aligned_observations(). The forecast horizon
        does not change the cutoff used for this historical state.
        """
        if self.time_utc is None:
            raise ValueError("Sample comparison requires prediction time_utc; use model.predict(sample)")
        return self._aligned_sample_field(
            observed, "burned_area", "burned_area_valid", offset_seconds=0,
        )

    def _aligned_sample_field(
        self, observed, field_name, validity_name, *, offset_seconds, fallback_validity=None,
    ):
        if not isinstance(observed, Mapping):
            raise TypeError("observed must be a dataset sample or batch")
        supplied_target = _array(observed[field_name])
        target_mask = np.ma.getmaskarray(supplied_target)
        target = np.asarray(np.ma.getdata(supplied_target))
        shape = tuple(self.probability.shape)
        if len(shape) not in (3, 4, 5) or target.ndim != len(shape) or target.shape[-3:] != shape[-3:]:
            raise ValueError("Observed samples must match prediction spatial/channel dimensions and organization")
        if target.dtype.kind not in "biuf":
            raise TypeError("Observed targets must contain real binary values")
        if len(shape) == 5 and target.shape[0] != shape[0]:
            raise ValueError("Observed batch size must match predictions")
        for name, expected in (("affine_transform", self._affine_transform), ("epsg", self._epsg)):
            if expected is not None:
                actual = _metadata_array(observed[name], name)
                if actual.shape != expected.shape or not np.array_equal(actual, expected):
                    raise ValueError(f"Observed {name} differs from the prediction grid")
        if self.event_id is not None:
            if "event_id" not in observed or not np.array_equal(_array(observed["event_id"]), _array(self.event_id)):
                raise ValueError("Observed event_id differs from the prediction event")
        leading = target.shape[:-3]
        timestamps = _times(observed["time_utc"], leading, "observed time_utc")
        temporal = _time_mask(observed.get("time_valid"), leading)
        if np.any(temporal & (timestamps < 0)):
            raise ValueError("Valid observed timestamps must be nonnegative Unix seconds")
        validity = observed.get(validity_name)
        if validity is None and fallback_validity is not None:
            validity = observed.get(fallback_validity)
        if validity is None:
            required = validity_name if fallback_validity is None else f"{validity_name} or {fallback_validity}"
            raise ValueError(f"Observed samples require {required}")
        known = _array(validity)
        if known.dtype.kind != "b" or known.shape != target.shape or np.ma.isMaskedArray(known):
            raise ValueError("Observed validity must be a boolean mask of the complete target shape")
        known = np.asarray(known).copy() & np.isfinite(target) & ~target_mask
        known &= temporal.reshape(leading + (1, 1, 1))
        spatial = _pixel_mask(observed.get("pixel_valid"), target.shape)
        spatial_shape = target.shape[:-4] + ((1, 1) if target.ndim >= 4 else (1,)) + target.shape[-2:]
        known &= spatial.reshape(spatial_shape)
        if np.any(known & (target != 0) & (target != 1)):
            raise ValueError("Known observed targets must be exactly 0 or 1")
        aligned = np.full(shape, np.nan, dtype=float)
        aligned_valid = np.zeros(shape, dtype=bool)
        # Normalize snapshot/sequence/batch to B,T,1,H,W for exact lookup.
        batches = shape[0] if len(shape) == 5 else 1
        pred_count = shape[-4] if len(shape) >= 4 else 1
        obs_count = target.shape[-4] if target.ndim >= 4 else 1
        pred_times = self.time_utc.reshape(batches, pred_count)
        pred_valid = self._time_valid.reshape(batches, pred_count)
        obs_times = timestamps.reshape(batches, obs_count)
        obs_valid = temporal.reshape(batches, obs_count)
        raw = np.asarray(np.ma.getdata(target)).reshape(batches, obs_count, *shape[-3:])
        masks = known.reshape(batches, obs_count, *shape[-3:])
        prediction_pixels = _pixel_mask(self._pixel_valid, shape).reshape(batches, 1, *shape[-2:])
        out = aligned.reshape(batches, pred_count, *shape[-3:])
        out_valid = aligned_valid.reshape(batches, pred_count, *shape[-3:])
        # Source timestamps are integer seconds. Reject fractional endpoints
        # before adding them to epoch seconds: floating-point addition could
        # otherwise round a tiny positive interval back onto the cutoff.
        exact_seconds = np.isfinite(offset_seconds) and float(offset_seconds).is_integer()
        integer_offset = int(offset_seconds) if exact_seconds else None
        for batch in range(batches):
            times = obs_times[batch, obs_valid[batch]]
            if np.unique(times).size != times.size:
                raise ValueError("Observed valid timestamps must be unique within each event")
            lookup = {int(obs_times[batch, i]): i for i in range(obs_count) if obs_valid[batch, i]}
            for step in range(pred_count):
                if integer_offset is None:
                    continue
                endpoint = int(pred_times[batch, step]) + integer_offset
                if pred_valid[batch, step] and endpoint in lookup:
                    j = lookup[endpoint]
                    display_valid = masks[batch, j] & prediction_pixels[batch]
                    out_valid[batch, step] = display_valid
                    out[batch, step] = np.where(display_valid, raw[batch, j], np.nan)
        return aligned, aligned_valid

    def compare(
        self, observed, *, observed_valid=None, burned_area=None,
        burned_area_valid=None, index=None, mode="overlay", **options,
    ):
        """Show previous burns and next-hour new burns over probabilities.

        ``observed`` is an hourly sample/batch (automatically time aligned), or
        an explicitly aligned binary target array. Full arrays must match the
        prediction shape; a 2D target may describe the matrix selected by index.
        For a sample mapping, cumulative burned_area is automatically aligned
        at the prediction cutoff t when present, while new-burn labels align at
        t+3600. Explicit burned_area and its mask can supply an already aligned
        historical state instead. These arrays must match the full prediction
        shape, or be selected 2D matrices when observed is also a 2D matrix.
        Known prior burns and positive outcomes retain their own masks and stay
        visible where probabilities are unavailable. The default is one overlay
        panel: probability background, translucent brown prior burns, and cyan
        hollow cyan next-hour markers, with the loaded region outlined and the
        full spatial grid in view. Other layouts and styles use plot_comparison options.
        Returns (figure, axes), with a one-dimensional array of panel axes.
        """
        self._check_plot_index(index)
        from .plotting import _matrix, plot_comparison
        if "region_valid" not in options:
            shape = tuple(self.probability.shape)
            pixels = _pixel_mask(self._pixel_valid, shape)
            pixel_shape = shape[:-4] + ((1, 1) if len(shape) >= 4 else (1,)) + shape[-2:]
            options["region_valid"] = np.broadcast_to(pixels.reshape(pixel_shape), shape)
        if burned_area is None and burned_area_valid is not None:
            raise ValueError("burned_area_valid requires burned_area")
        if isinstance(observed, Mapping):
            if observed_valid is not None:
                raise ValueError("Observed samples supply their own validity masks")
            options.setdefault("event_label", "Newly burned in next hour")
            if burned_area is None and "burned_area" in observed:
                burned_area, burned_area_valid = self.aligned_burned_area(observed)
            observed, observed_valid = self.aligned_observations(observed)
            overlay_title = (
                "Previous burned area and next-hour new burns\nReconstructed reference over predicted probability q"
                if burned_area is not None else "Reconstructed next-hour new burns over probability q"
            )
            options.setdefault("titles", ("Reconstructed next-hour new burns", "Predicted probability q", overlay_title))
        if _array(observed).ndim == 2 and len(self.probability.shape) > 2:
            probability = _matrix(self.probability, valid=self.valid, index=index)
            region = options.get("region_valid")
            if region is not None and _array(region).shape == tuple(self.probability.shape):
                options["region_valid"] = _matrix(region, index=index)
            if burned_area is not None and _array(burned_area).ndim > 2:
                if tuple(_array(burned_area).shape) != tuple(self.probability.shape):
                    raise ValueError("burned_area must match the full prediction shape or selected 2D matrix")
                burned_area = _matrix(burned_area, valid=burned_area_valid, index=index)
                burned_area_valid = None
            return plot_comparison(
                probability, observed, observed_valid=observed_valid,
                burned_area=burned_area, burned_area_valid=burned_area_valid,
                mode=mode, **options,
            )
        return plot_comparison(
            self.probability, observed, valid=self.valid, observed_valid=observed_valid,
            burned_area=burned_area, burned_area_valid=burned_area_valid,
            index=index, mode=mode, **options,
        )
