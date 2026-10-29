"""A trained one-hour new-burn predictor connected to incident radiant heat.

New burning during an interval is converted to active occupancy under an
explicit uniform conditional arrival-time model. Unknown ignition probabilities
produce bounds, not invented zero observations. Present burning is a separate
optional input; cumulative burned area does not identify ongoing combustion.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import ArrayLike

from .model import (
    AffineGrid, CombustionParameters, ExpectedHeatFluxModel, FloatArray,
    _finite_array, _physical_array, _scalar,
)
from .temporal import ignition_to_active_probability, initial_active_occupancy


def _numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    if np.ma.isMaskedArray(value) and np.any(np.ma.getmaskarray(value)):
        raise ValueError("masked inputs require explicit numeric arrays and separate validity masks")
    return np.asarray(value)


def _single_matrix(value: Any, name: str) -> np.ndarray:
    array = _numpy(value)
    if array.ndim < 2 or any(size != 1 for size in array.shape[:-2]):
        raise ValueError(f"{name} must be [H,W] or have only singleton leading dimensions")
    if min(array.shape[-2:]) < 1:
        raise ValueError(f"{name} must have a nonempty spatial matrix")
    return array.reshape(array.shape[-2:])


def _mask(value: Any, shape: tuple[int, int], name: str) -> np.ndarray:
    array = _single_matrix(value, name)
    if array.dtype != np.bool_ or array.shape != shape:
        raise ValueError(f"{name} must be boolean and match shape {shape}")
    return np.array(array, copy=True)


def _map(value: ArrayLike, shape: tuple[int, int], name: str, *, upper=None) -> FloatArray:
    array = _physical_array(value, name, upper=upper)
    if array.ndim == 0:
        return np.full(shape, float(array))
    if array.shape != shape:
        raise ValueError(f"{name} must be scalar or exactly match shape {shape}")
    return array


@dataclass(frozen=True)
class IntegratedHeatPrediction:
    """One forecast interval, with [H,W] matrices and explicit source coverage.

    ``expected_heat_flux_w_m2`` is the interval-mean full supplied-domain radiant
    flux. It is NaN if any unresolved positive emitting source can contribute.
    ``known_source_heat_flux_w_m2`` is the finite expected contribution of known
    new-burn sources and any supplied present-active sources. Under the stated
    fixed combustion/arrival assumptions it equals the lower bound. Upper bounds
    let each unknown new-event probability vary up to one. They do not bound
    unmodeled convection, emission parameters, or outside-domain fires.
    """

    new_burn_probability: FloatArray
    probability_valid: np.ndarray
    original_probability_valid: np.ndarray
    externally_supplied_probability_mask: np.ndarray
    mean_active_burning_probability: FloatArray
    endpoint_active_burning_probability: FloatArray
    expected_heat_flux_w_m2: FloatArray
    known_source_heat_flux_w_m2: FloatArray
    heat_flux_lower_bound_w_m2: FloatArray
    heat_flux_upper_bound_w_m2: FloatArray
    expected_incident_energy_j_m2: FloatArray
    incident_energy_lower_bound_j_m2: FloatArray
    incident_energy_upper_bound_j_m2: FloatArray
    endpoint_heat_flux_lower_bound_w_m2: FloatArray
    endpoint_heat_flux_upper_bound_w_m2: FloatArray
    complete: bool
    metadata: dict

    @property
    def expected_heat_flux_kw_m2(self) -> FloatArray:
        return self.expected_heat_flux_w_m2 / 1000.0

    @property
    def known_source_heat_flux_kw_m2(self) -> FloatArray:
        return self.known_source_heat_flux_w_m2 / 1000.0


class WildfireHeatModel:
    """Compose a trained one-hour wildfire predictor and finite-cell radiation.

    ``combustion.burning_duration_s`` is also the duration of active emission
    after a future ignition. First-event arrival is uniform in the next hour,
    conditional on that event. New-burning heat is modeled by default; present
    burning is included only when its active probability and remaining duration
    are explicitly supplied. One invocation processes one spatial snapshot.
    """

    def __init__(
        self,
        predictor: Any,
        *,
        grid: AffineGrid,
        combustion: CombustionParameters,
        radiative_fraction: ArrayLike,
        emission_height_m: float,
        receiver_height_m: float = 0.0,
        atmospheric_transmissivity: float = 1.0,
        interval_s: float = 3600.0,
        predictor_provenance: dict | None = None,
    ):
        if not isinstance(combustion, CombustionParameters):
            raise TypeError("combustion must be CombustionParameters")
        if np.asarray(interval_s).dtype.kind not in "iuf":
            raise ValueError("interval_s must be numeric seconds, not strings or booleans")
        self.interval_s = _scalar(interval_s, "interval_s")
        # Both maintained model families were fitted on exact one-hour pairs.
        if self.interval_s != 3600.0:
            raise ValueError("the maintained wildfire checkpoint endpoint is exactly 3600 seconds")
        self.predictor = predictor
        self.combustion = combustion
        self.predictor_provenance = dict(predictor_provenance or {})
        self.heat_model = ExpectedHeatFluxModel(
            grid=grid,
            heat_release_rate_density_w_m2=combustion.heat_release_rate_density_w_m2,
            radiative_fraction=radiative_fraction,
            emission_height_m=emission_height_m,
            receiver_height_m=receiver_height_m,
            atmospheric_transmissivity=atmospheric_transmissivity,
        )

    @classmethod
    def from_checkpoint(cls, path: str | Path, *, device="cpu", **physical_parameters):
        """Load saved normalization/channel schema and the proper model family.

        Torch and the maintained ``wildfire_burned_area_hourly`` package are
        optional integration dependencies. The radiation-only API remains NumPy.
        No training or preprocessing fit is performed. CPU is the default.
        """
        import torch

        path = Path(path).expanduser().resolve()
        saved = torch.load(path, map_location="cpu", weights_only=True)
        architecture = saved.get("contract", {}).get("architecture")
        del saved
        if architecture == "DirectEnvironmentConditionedConvolution":
            from wildfire_burned_area_hourly.probability_model.direct_convolution import load_trained_model
        elif architecture == "EnvironmentConditionedConvolution":
            from wildfire_burned_area_hourly.probability_model import load_trained_model
        else:
            raise ValueError(f"Unsupported wildfire checkpoint architecture: {architecture!r}")
        predictor = load_trained_model(path, device=device)
        provenance = {
            "checkpoint_path": str(path),
            "checkpoint_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "architecture": architecture,
            "best_epoch": int(predictor.best_epoch),
            "device": str(device),
            "channel_names": list(predictor.channel_names),
            "source_channels": list(predictor.source_channels),
            "categorical_classes": predictor.categorical_classes,
            "normalization": "checkpoint's saved training-only statistics",
            "probability_semantics": "new cumulative burning during the next exact hour",
        }
        return cls(predictor, predictor_provenance=provenance, **physical_parameters)

    def predict_sample(self, sample: dict, **current_burning) -> IntegratedHeatPrediction:
        """Use current burned/environmental tensors; arrival/future labels are unused.

        The source dataset itself may be retrospective. Not consuming its future
        labels does not make its reconstructed current state operational evidence.
        """
        transform = _finite_array(_numpy(sample["affine_transform"]), "sample affine_transform")
        if transform.shape != (6,) or not np.allclose(
            transform, self.heat_model.grid.transform, rtol=0, atol=1e-9
        ):
            raise ValueError("sample affine grid differs from the configured radiation grid")
        return self.predict(
            sample["burned_area"], sample["features"],
            channel_names=sample["channel_names"],
            burned_area_valid=sample.get("burned_area_valid"),
            feature_valid=sample.get("feature_valid"),
            **current_burning,
        )

    def predict(
        self,
        burned_area: Any,
        environmental_data: Any,
        *,
        channel_names,
        burned_area_valid=None,
        feature_valid=None,
        initial_active_burning_probability=None,
        initial_remaining_burning_duration_s=None,
        unknown_new_burn_probability=None,
    ) -> IntegratedHeatPrediction:
        """Run the trained predictor and return interval mean heat and radiant dose.

        An optional ``unknown_new_burn_probability`` is a separately justified
        scalar/map used only for unsupported predictions. Such entries are marked
        as supplied estimates in metadata, never claimed as original predictions.
        Without it, the full expectation remains unknown and bounds are returned.
        """
        if self.predictor is None:
            raise ValueError("predictor is absent; use predict_from_new_burn_probability")
        import torch

        burned = _single_matrix(burned_area, "burned_area")
        known = np.isfinite(burned)
        if burned_area_valid is not None:
            known &= _mask(burned_area_valid, burned.shape, "burned_area_valid")
        if np.any(known & (burned != 0) & (burned != 1)):
            raise ValueError("known burned_area must contain binary cumulative states")
        already_burned = known & (burned == 1)
        if initial_active_burning_probability is not None:
            initial = _map(initial_active_burning_probability, burned.shape,
                           "initial_active_burning_probability", upper=1.0)
            if np.any((initial > 0) & ~already_burned):
                raise ValueError("present active fire must be in known already-burned cells")
        # Preserve wrapper channel checks and raw-input normalization. Match its
        # own device/dtype rather than refitting or converting physical features.
        parameter = next(self.predictor.parameters())
        def tensor(value, *, boolean=False):
            array = _numpy(value)
            if boolean and array.dtype.kind != "b":
                raise ValueError("validity masks must contain booleans")
            if not boolean and array.dtype.kind not in "biuf":
                raise ValueError("burned/environment inputs must contain real numeric values")
            return torch.as_tensor(value, device=parameter.device,
                                   dtype=torch.bool if boolean else parameter.dtype)
        with torch.inference_mode():
            prediction = self.predictor(
                tensor(burned_area), tensor(environmental_data),
                channel_names=channel_names,
                burned_area_valid=None if burned_area_valid is None else tensor(burned_area_valid, boolean=True),
                feature_valid=None if feature_valid is None else tensor(feature_valid, boolean=True),
                dt_hours=1.0, boundary="unknown",
            )
        return self.predict_from_new_burn_probability(
            _single_matrix(prediction.probability, "prediction probability"),
            probability_valid=_single_matrix(prediction.valid, "prediction validity"),
            already_burned_mask=already_burned,
            initial_active_burning_probability=initial_active_burning_probability,
            initial_remaining_burning_duration_s=initial_remaining_burning_duration_s,
            unknown_new_burn_probability=unknown_new_burn_probability,
        )

    def predict_from_new_burn_probability(
        self,
        new_burn_probability: ArrayLike,
        *,
        probability_valid=None,
        already_burned_mask=None,
        initial_active_burning_probability=None,
        initial_remaining_burning_duration_s=None,
        unknown_new_burn_probability=None,
    ) -> IntegratedHeatPrediction:
        """Apply the timing/radiation bridge to a saved one-hour probability map.

        These probabilities must be the evaluation probability, not an unbounded
        direct-convolution raw score. A known already-burned mask resolves its
        first-new-burn probability to zero even where model context is unavailable.
        """
        if np.ma.isMaskedArray(new_burn_probability) or np.iscomplexobj(new_burn_probability):
            raise ValueError("use an explicit validity mask with a real new-burn probability map")
        raw_q = _single_matrix(new_burn_probability, "new_burn_probability")
        if raw_q.dtype.kind not in "biuf":
            raise ValueError("new_burn_probability must contain real numeric probabilities")
        q = np.array(raw_q, dtype=float, copy=True)
        shape = q.shape
        if np.any(np.isinf(q)):
            raise ValueError("new_burn_probability cannot contain infinity")
        valid = np.isfinite(q) if probability_valid is None else _mask(probability_valid, shape, "probability_valid")
        if np.any(valid & (~np.isfinite(q) | (q < 0) | (q > 1))):
            raise ValueError("valid new-burn probabilities must be finite and in [0,1]")
        if already_burned_mask is not None:
            old_burned = _mask(already_burned_mask, shape, "already_burned_mask")
            q[old_burned] = 0.0
            valid[old_burned] = True
        original_valid = valid.copy()
        supplied = np.zeros(shape, dtype=bool)
        if unknown_new_burn_probability is not None:
            fallback = _map(unknown_new_burn_probability, shape, "unknown_new_burn_probability", upper=1.0)
            supplied = ~valid
            q[supplied] = fallback[supplied]
            valid[supplied] = True
        q[~valid] = np.nan
        # Zero and one below are uncertainty endpoints, not missing-data fills.
        lower_q = np.where(valid, q, 0.0)
        upper_q = np.where(valid, q, 1.0)
        lower = ignition_to_active_probability(lower_q, self.combustion.burning_duration_s, self.interval_s)
        upper = ignition_to_active_probability(upper_q, self.combustion.burning_duration_s, self.interval_s)
        if initial_active_burning_probability is None:
            if initial_remaining_burning_duration_s is not None:
                raise ValueError("remaining burning duration requires an initial active probability")
            initial_mean = np.zeros(shape)
            initial_endpoint = np.zeros(shape)
            scope = "radiation from newly igniting cells only; present-fire contribution is excluded"
        else:
            if initial_remaining_burning_duration_s is None:
                raise ValueError("initial active fire requires remaining_burning_duration_s")
            active = _map(initial_active_burning_probability, shape,
                          "initial_active_burning_probability", upper=1.0)
            if np.any(active > 0) and already_burned_mask is None:
                raise ValueError("present active fire requires an explicit known already_burned_mask")
            if already_burned_mask is not None and np.any((active > 0) & ~old_burned):
                raise ValueError("present active fire must be in known already-burned cells")
            if np.any((active > 0) & ((upper_q > 0) | ~valid)):
                raise ValueError("initial active and possible first-new-burning sources must be disjoint")
            current = initial_active_occupancy(active, initial_remaining_burning_duration_s, self.interval_s)
            initial_mean, initial_endpoint = current.mean_active_probability, current.endpoint_active_probability
            scope = "newly igniting cells plus caller-supplied present active-fire contribution"
        lower_mean = lower.mean_active_probability + initial_mean
        upper_mean = upper.mean_active_probability + initial_mean
        lower_end = lower.endpoint_active_probability + initial_endpoint
        upper_end = upper.endpoint_active_probability + initial_endpoint
        mean_lower_flux = self.heat_model.predict(lower_mean).incident_heat_flux_w_m2
        mean_upper_flux = self.heat_model.predict(upper_mean).incident_heat_flux_w_m2
        end_lower_flux = self.heat_model.predict(lower_end).incident_heat_flux_w_m2
        end_upper_flux = self.heat_model.predict(upper_end).incident_heat_flux_w_m2
        emitting = self.heat_model._weighted_sources(np.ones(shape)) > 0
        unresolved_emission = (~valid) & emitting & (self.heat_model.atmospheric_transmissivity > 0)
        complete = not bool(np.any(unresolved_emission))
        exact_flux = mean_lower_flux.copy() if complete else np.full(shape, np.nan)
        mean_active = lower_mean.copy()
        endpoint_active = lower_end.copy()
        mean_active[~valid] = np.nan
        endpoint_active[~valid] = np.nan
        metadata = {
            "forecast_interval_s": self.interval_s,
            "heat_flux_semantics": "interval-mean incident radiant flux in W/m2",
            "dose_semantics": "integral of interval-mean radiant flux over forecast interval in J/m2",
            "scope": scope,
            "arrival_time_assumption": "conditional on a first-new-burning event, arrival is uniform within the hour",
            "burning_profile_assumption": "constant conditional HRR for the supplied residence duration after arrival",
            "present_burning_assumption": "only caller-supplied active probabilities and remaining durations are included",
            "unknown_probability_policy": "full expectation is NaN; nonnegative-source probability endpoints 0 and 1 yield bounds",
            "source_cells": int(q.size),
            "original_probability_valid_cells": int(original_valid.sum()),
            "externally_supplied_probability_cells": int(supplied.sum()),
            "unresolved_probability_cells": int((~valid).sum()),
            "unresolved_emitting_source_cells": int(unresolved_emission.sum()),
            "complete_full_domain_expectation": complete,
            "bounds_scope": "fixed supplied combustion, duration, geometry, and finite source domain; excludes omitted transport and parameter uncertainty",
            "predictor": self.predictor_provenance,
        }
        return IntegratedHeatPrediction(
            q, valid, original_valid, supplied, mean_active, endpoint_active, exact_flux, mean_lower_flux,
            mean_lower_flux, mean_upper_flux, exact_flux * self.interval_s,
            mean_lower_flux * self.interval_s, mean_upper_flux * self.interval_s,
            end_lower_flux, end_upper_flux, complete, metadata,
        )
