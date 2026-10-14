"""Load, predict, evaluate, train and save wildfire models.

``model.predict(sample)`` returns the fitted model's one-hour Prediction.
``model.predict_cumulative(sample, hours=[1, 3, 6])`` defaults to recursive
binary trajectory simulation: newly burned cells can spread fire next hour.
It returns CumulativePrediction with new-burn and total burned probabilities,
Monte Carlo uncertainty, validity masks and simulation metadata. Both methods
also accept raw arrays with an explicit channel schema. Full input rectangles
are retained. Predictions default to unburned missing initial states and
known-unburned outside-grid padding; spatial and temporal padding inside the
input remain excluded. These assumptions never change reference masks.

Evaluate only after prediction, supplying reference cumulative states at exact
endpoints and explicit durations: ``result.evaluate(reference, hours=[3, 6])``.
The same evaluator is exported as ``evaluate_cumulative`` from this module and
the package root. Original reference masks remain authoritative for scoring.
Legacy tensor/tuple methods remain explicit adapters for existing integrations.
"""
from __future__ import annotations

from .paths import DEFAULT_CHECKPOINT, resolve_recorded_path



# Api
# Importable data, fitted-model, training, and radiant-heat interface.
# 
# Prediction consumes current burned state, environmental inputs and their masks.
# It does not consume outcome labels or fit preprocessing. Result coordinates
# are static WGS84 (latitude, longitude) pixel centers in degrees.


import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import hashlib
import importlib
import math
from numbers import Integral, Real
import os
from pathlib import Path
import tempfile
from typing import Any, Literal, Mapping, Sequence

import numpy as np
import torch

from wildfire.models import BurnProbability
from wildfire.utils import choose_device
from wildfire.prediction import Prediction
from wildfire.cumulative import CumulativePrediction
from wildfire.cumulative_evaluation import evaluate_cumulative
from wildfire.catalog import available_events, available_cutoffs


__all__ = ["TrainingConfig", "WildfireModel", "Prediction", "CumulativePrediction", "evaluate_cumulative", "load_model", "train_model",
           "available_events", "available_cutoffs"]

ModelFamily = Literal["exponential", "mixture_exponential", "random_forest"]
_FAMILIES = {
    "EnvironmentConditionedConvolution": "exponential",
    "LearnedNonnegativeKernel": "exponential",
    "MixedNonnegativeKernel": "exponential",
    "NeuralMixedNonnegativeKernel": "exponential",
    "BayesianModelAverage": "mixture_exponential",
    "PatchRandomForest": "random_forest",
}
_SIGNED_RETIREMENT = (
    "The signed direct-convolution model has been retired. Its checkpoint is "
    "historical evidence and cannot be loaded by the active prediction API. "
    "Use a supported nonnegative-kernel checkpoint."
)


def _device(requested: str | torch.device) -> torch.device:
    if str(requested) == "auto":
        requested = ("cuda" if torch.cuda.is_available()
                     else "mps" if torch.backends.mps.is_available() else "cpu")
    return choose_device(str(requested))


def _tensor(value: Any, reference: torch.Tensor, *, boolean: bool = False) -> torch.Tensor:
    if isinstance(value, torch.Tensor):
        if boolean and value.dtype != torch.bool:
            raise TypeError("Validity masks must contain booleans")
        if value.is_complex() or value.is_quantized:
            raise TypeError("Inputs must contain real, unquantized numeric values")
    else:
        if np.ma.isMaskedArray(value) and np.any(np.ma.getmaskarray(value)):
            raise ValueError("Masked inputs require a separate boolean validity mask")
        value = np.asarray(value)
        if boolean and value.dtype.kind != "b":
            raise TypeError("Validity masks must contain booleans")
        if not boolean and value.dtype.kind not in "biuf":
            raise TypeError("Inputs must contain real numeric values")
    return torch.as_tensor(
        value, device=reference.device, dtype=torch.bool if boolean else reference.dtype,
    )


@dataclass(frozen=True)
class TrainingConfig:
    """Options for the exponential trainer; cache metadata fixes channels/kernel.

    Positive integer fields exclude booleans. Rates must be finite; learning_rate
    is positive and weight_decay is nonnegative. Device 'auto' selects CUDA,
    then MPS, then CPU. The default uses CPU for reproducible examples.
    Categorical balancing fits capped inverse-square-root patch-presence
    weights on training inputs only; 'none' disables this loss adjustment.
    Continuous normalization retains population weights; one-hot inputs stay
    raw 0/1. Validation and test scores always use original population weights.
    """

    epochs: int = 30
    patience: int = 6
    batch_size: int = 1024
    hidden_channels: int = 16
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    seed: int = 7
    threads: int = 4
    device: str = "cpu"
    categorical_balance: str = "inverse-sqrt"
    categorical_balance_min_frequency: float = 1e-3
    categorical_balance_max_factor: float = 10.0

    def __post_init__(self):
        for name in ("epochs", "patience", "batch_size", "hidden_channels", "threads"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if (isinstance(self.seed, bool) or not isinstance(self.seed, Integral)
                or not 0 <= self.seed < 2**64):
            raise ValueError("seed must be an integer in [0, 2**64)")
        for name in ("learning_rate", "weight_decay"):
            value = getattr(self, name)
            if (isinstance(value, bool) or not isinstance(value, Real)
                    or not math.isfinite(value)
                    or (value <= 0 if name == "learning_rate" else value < 0)):
                raise ValueError(f"{name} must be finite and "
                                 + ("positive" if name == "learning_rate" else "nonnegative"))
        if self.device not in ("cpu", "cuda", "mps", "auto"):
            raise ValueError("device must be cpu, cuda, mps, or auto")
        from wildfire.metrics import validate_categorical_balance_settings
        validate_categorical_balance_settings(
            mode=self.categorical_balance, min_frequency=self.categorical_balance_min_frequency,
            max_factor=self.categorical_balance_max_factor,
        )


def load_model(path: str | Path = DEFAULT_CHECKPOINT, *, device: str | torch.device = "cpu") -> WildfireModel:
    """Load a supported checkpoint with its saved channel/preprocessing contract.

    Tensor checkpoints retain the chosen device. Trusted local PatchRandomForest
    joblib checkpoints use CPU inference, including when device='auto'. Their
    saved normalization is applied without fitting new preprocessing.
    """
    return WildfireModel.from_checkpoint(path, device=device)


def train_model(
    prepared_data: str | Path, output_dir: str | Path, *,
    family: ModelFamily = "exponential", config: TrainingConfig | None = None,
) -> WildfireModel:
    """Fit a new model from a prepared cache and return its selected checkpoint.

    Data preparation is independent: prepare_training_data() reads event
    timelines and writes the cache. Loading an existing model uses load_model().
    """
    return WildfireModel.train(prepared_data, output_dir, family=family, config=config)


class WildfireModel:
    """One fitted probability model with its saved preprocessing and channel order.

    Construct with from_checkpoint()/load_model(), or train() on a prepared
    cache. predict() evaluates the fitted next-hour model. predict_cumulative()
    defaults to recursive hourly binary spread and exposes explicit fixed-state
    compatibility through method='fixed'. Every forecast uses current state,
    named environmental inputs and masks; reference outcomes are read only by
    result comparison/evaluation methods after prediction. Evaluation requires
    explicit hours already present in the cumulative result.

    Prediction assumes unavailable initial burned states inside real input
    support are unburned by default, and uses boundary='zero' for outside-grid
    unburned sources and zero environmental context. Explicit boundary='unknown'
    retains conservative outside-grid uncertainty. Feature missingness remains
    masked, and input padding remains excluded. New-burn probability, total burned
    probability and Monte Carlo uncertainty are distinct output quantities;
    cumulative burned state does not describe active flames. 'exponential'
    converts a nonnegative hourly rate with the existing exponential link.
    'random_forest' applies saved patch forests on CPU, using mean tree
    probabilities at each recursive one-hour transition without tree sampling.
    Forests support ordinary one-hour prediction and recursive whole-hour
    horizons; fixed-mode extrapolation beyond the fitted hour is unavailable.
    Signed direct-convolution checkpoints are retired.
    """

    def __init__(self, predictor, checkpoint: Mapping[str, Any], path: Path, digest: str):
        self.predictor = predictor
        self.checkpoint_path = path
        self.checkpoint_sha256 = digest
        self._checkpoint = checkpoint
        self.training_metrics: dict[str, Any] | None = None

    @classmethod
    def from_checkpoint(cls, path: str | Path, *, device: str | torch.device = "cpu") -> WildfireModel:
        path = resolve_recorded_path(path).resolve()
        if path.suffix.lower() in (".joblib", ".pkl", ".pickle"):
            if str(device) not in ("cpu", "auto"):
                raise ValueError("PatchRandomForest inference requires device='cpu'")
            from .forest_inference import ForestGridPredictor
            from .models import PatchRandomForest
            predictor = ForestGridPredictor(PatchRandomForest.load(path)).eval()
            saved = dict(contract=deepcopy(predictor.contract), metadata=predictor.forest.metadata)
            return cls(predictor, saved, path, hashlib.sha256(path.read_bytes()).hexdigest())
        selected_device = _device(device)
        saved = torch.load(path, map_location="cpu", weights_only=True)
        if not isinstance(saved, dict) or not isinstance(saved.get("contract"), dict):
            raise ValueError("Checkpoint must contain a model contract")
        architecture = saved["contract"].get("architecture")
        if architecture == "DirectEnvironmentConditionedConvolution":
            raise ValueError(_SIGNED_RETIREMENT)
        if architecture not in _FAMILIES:
            raise ValueError(f"Unsupported checkpoint architecture: {architecture!r}")
        if architecture == "MixedNonnegativeKernel":
            loader = importlib.import_module(
                ".inference", package=__package__,
            ).load_mixed_trained_model
        elif architecture == "NeuralMixedNonnegativeKernel":
            loader = importlib.import_module(
                ".inference", package=__package__,
            ).load_neural_mixed_trained_model
        else:
            loader = importlib.import_module(".inference", package=__package__).load_trained_model
        predictor = loader(path, device=selected_device)
        return cls(predictor, saved, path, hashlib.sha256(path.read_bytes()).hexdigest())

    @property
    def family(self) -> ModelFamily:
        return _FAMILIES[self.predictor.contract["architecture"]]

    @property
    def channel_names(self) -> tuple[str, ...]:
        return self.predictor.channel_names

    @property
    def contract(self) -> dict[str, Any]:
        """A copy of the checkpoint contract; changing it does not alter the model."""
        return deepcopy(self.predictor.contract)

    @property
    def device(self) -> torch.device:
        return next(self.predictor.parameters()).device

    def to(self, device: str | torch.device) -> WildfireModel:
        """Move resident weights and saved normalization together; return this model."""
        if self.family == "random_forest":
            if str(device) not in ("cpu", "auto"):
                raise ValueError("PatchRandomForest inference requires device='cpu'")
            return self
        self.predictor.to(_device(device))
        return self

    def _sample_environment(self, sample: Mapping[str, Any]):
        """Arrange independently loaded named inputs at the prediction boundary."""
        names = tuple(sample["channel_names"])
        if any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
            raise ValueError("Sample channel_names must be distinct nonempty strings")
        missing = [name for name in self.channel_names if name not in names]
        if missing:
            raise ValueError(f"Sample is missing required channels: {missing}")
        features, valid = sample["features"], sample.get("feature_valid")
        if names == self.channel_names:
            return features, valid
        reference = next(self.predictor.parameters())
        features = _tensor(features, reference)
        if features.ndim < 3 or features.shape[-3] != len(names):
            raise ValueError("Sample feature channel count must match channel_names")
        if valid is not None:
            valid = _tensor(valid, reference, boolean=True)
            if valid.shape != features.shape:
                raise ValueError("Validity masks must match the complete input shape")
        known = torch.isfinite(features) if valid is None else valid & torch.isfinite(features)
        if sample.get("pixel_valid") is not None or sample.get("time_valid") is not None:
            from .prediction import _support
            shape = (*features.shape[:-3], 1, *features.shape[-2:])
            support, _, _ = _support(shape, sample.get("pixel_valid"), sample.get("time_valid"))
            known = known & torch.as_tensor(support, device=reference.device)
        order = [names.index(name) for name in self.channel_names]
        selected = features[..., order, :, :]
        selected_valid = known[..., order, :, :].clone()
        # An independently chosen vocabulary can include classes absent from
        # training. Validate its complete group, then mark those classes unknown
        # to this model rather than interpreting all-zero required indicators.
        for source in self.predictor.categorical_classes:
            group = [i for i, name in enumerate(names) if name.startswith(source + "=")]
            values = features[..., group, :, :]
            group_known = known[..., group, :, :].all(dim=-3)
            binary = ((values == 0) | (values == 1)).all(dim=-3)
            if not bool((~group_known | (binary & (values.sum(dim=-3) == 1))).all()):
                raise ValueError(f"Invalid known one-hot input group: {source}")
            required = [i for i, name in enumerate(self.channel_names) if name.startswith(source + "=")]
            recognized = selected[..., required, :, :].sum(dim=-3) == 1
            selected_valid[..., required, :, :] &= (group_known & recognized).unsqueeze(-3)
        return selected, selected_valid

    def predict_details(
        self, burned_area: Any, environmental_data: Any, *, channel_names: Sequence[str],
        burned_area_valid=None, feature_valid=None, dt_hours=1.0, boundary="zero",
        missing_burned_area="unburned",
    ) -> BurnProbability:
        """Infer from raw ordered inputs; return tensors on this model's device.

        Inputs retain shape [..., C, H, W]; burned_area has C=1. Masks must be
        boolean with the matching full shape. Unavailable burned states default
        to zero; missing_burned_area='unknown' retains their missingness.
        boundary='zero' pads exterior context with zeros without resizing the
        output rectangle. Missing environmental inputs remain NaN/false.
        The result also has rate/rate_valid. Single-kernel families hold their
        hourly rate fixed over dt_hours. Bayesian averages combine the component
        probabilities at each horizon and report its equivalent interval rate;
        that rate generally changes with the horizon. The trained endpoint is
        one hour for every family.
        Forests accept only dt_hours=1 and report the equivalent value -log(1-q),
        which may be infinite when q=1; it is not a fitted continuous-time rate.
        """
        reference = next(self.predictor.parameters())
        duration = (torch.as_tensor(dt_hours, device=reference.device)
                    if isinstance(dt_hours, (torch.Tensor, np.ndarray))
                    else dt_hours)
        inputs = dict(
            burned_area=_tensor(burned_area, reference),
            burned_area_valid=(None if burned_area_valid is None
                               else _tensor(burned_area_valid, reference, boolean=True)),
        )
        inputs, _ = self._initialize_burned_area(inputs, {}, missing_burned_area)
        with torch.inference_mode():
            self.predictor.eval()
            return self.predictor(
                inputs["burned_area"], _tensor(environmental_data, reference),
                channel_names=channel_names,
                burned_area_valid=inputs["burned_area_valid"],
                feature_valid=(None if feature_valid is None
                               else _tensor(feature_valid, reference, boolean=True)),
                dt_hours=duration, boundary=boundary,
            )

    def predict_sample_details(
        self, sample: Mapping[str, Any], *, dt_hours=1.0, boundary="zero",
        missing_burned_area="unburned",
    ) -> BurnProbability:
        """Return probability, validity and diagnostics without reading outcome labels."""
        result = self.predict(sample, dt_hours=dt_hours, boundary=boundary,
                              missing_burned_area=missing_burned_area)
        return BurnProbability(result.probability, result.valid, result.rate, result.rate_valid)

    def predict(
        self, burned_area: Any, environmental_data: Any = None, *,
        channel_names: Sequence[str] | None = None,
        burned_area_valid=None, feature_valid=None, dt_hours=1.0, boundary="zero",
        missing_burned_area="unburned",
        affine_transform=None, epsg=None, pixel_valid=None, time_valid=None,
    ) -> Prediction:
        """Predict from a dataset sample/batch or raw ordered arrays.

        Return one result exposing probability, valid, rate, rate_valid,
        optional static WGS84 coordinates, and plot()/compare() helpers.
        Raw arrays require explicit channel_names in checkpoint order. A sample
        may supply reordered or additional named channels; prediction selects
        this checkpoint's required channels without changing the loaded sample.
        A sample supplies its schema,
        masks and geometry; overriding those fields is rejected. Neither route
        reads outcome labels. dt_hours is a scalar or matches all input leading
        dimensions; the one-hour trained endpoint is the default.
        Unavailable or nonfinite burned states inside real pixel/time support
        default to unburned zero. boundary='zero' supplies zero exterior source
        and environmental context, retaining edge coverage on a complete grid.
        Explicit missing_burned_area='unknown' and boundary='unknown' preserve
        conservative missingness. Environmental gaps and pixel/time padding
        remain excluded; original samples and reference masks are never changed.
        """
        inputs, geometry = self._prepare_prediction_inputs(
            burned_area, environmental_data, channel_names=channel_names,
            burned_area_valid=burned_area_valid, feature_valid=feature_valid,
            affine_transform=affine_transform, epsg=epsg,
            pixel_valid=pixel_valid, time_valid=time_valid,
        )
        inputs, initialization = self._initialize_burned_area(inputs, geometry, missing_burned_area)
        details = self.predict_details(**inputs, dt_hours=dt_hours, boundary=boundary,
                                       missing_burned_area="unknown")
        return Prediction.from_details(details, dt_hours=dt_hours, **geometry,
                                       metadata={**getattr(self.predictor, "prediction_metadata", {}),
                                                 **initialization, "boundary": boundary})

    @staticmethod
    def _initialize_burned_area(inputs, geometry, missing_burned_area):
        """Apply a forecast assumption to a copy, retaining observation masks."""
        if missing_burned_area not in ("unburned", "unknown"):
            raise ValueError("missing_burned_area must be 'unburned' or 'unknown'")
        burned = inputs["burned_area"]
        if burned.ndim < 3 or burned.shape[-3] != 1:
            raise ValueError("burned_area must have shape [...,1,H,W]")
        known = torch.isfinite(burned)
        mask = inputs.get("burned_area_valid")
        if mask is not None:
            if mask.shape != burned.shape:
                raise ValueError("Validity masks must match the complete input shape")
            known = known & mask
        from .prediction import _support
        support, _, _ = _support(tuple(burned.shape), geometry.get("pixel_valid"), geometry.get("time_valid"))
        support = torch.as_tensor(support, device=burned.device)
        assumed = support & ~known if missing_burned_area == "unburned" else torch.zeros_like(support)
        result = dict(inputs)
        if missing_burned_area == "unburned":
            result["burned_area"] = torch.where(assumed, 0, burned)
            result["burned_area_valid"] = (known | assumed) & support
        return result, {"missing_burned_area": missing_burned_area,
                        "assumed_unburned_cells": int(assumed.sum().item())}

    def _prepare_prediction_inputs(
        self, burned_area, environmental_data=None, *, channel_names=None,
        burned_area_valid=None, feature_valid=None, affine_transform=None,
        epsg=None, pixel_valid=None, time_valid=None,
    ):
        """Prepare only cutoff inputs, preserving schema, masks and geometry."""
        metadata = {}
        if isinstance(burned_area, Mapping):
            if environmental_data is not None or any(value is not None for value in (
                channel_names, burned_area_valid, feature_valid, affine_transform,
                epsg, pixel_valid, time_valid,
            )):
                raise ValueError("A sample supplies input schema, masks and geometry; do not override those fields")
            sample = burned_area
            burned_area = sample["burned_area"]
            environmental_data, feature_valid = self._sample_environment(sample)
            channel_names = self.channel_names
            burned_area_valid = sample.get("burned_area_valid")
            affine_transform = sample.get("affine_transform")
            epsg = sample.get("epsg")
            pixel_valid = sample.get("pixel_valid")
            time_valid = sample.get("time_valid")
            # Current metadata only: target/arrival labels are never accessed.
            metadata = {name: sample[name] for name in ("time_utc", "event_id") if name in sample}
        if environmental_data is None:
            raise TypeError("environmental_data is required for raw burned_area arrays")
        if channel_names is None:
            raise ValueError("Raw arrays require channel_names in checkpoint order")
        if (affine_transform is None) != (epsg is None):
            raise ValueError("Supply both affine_transform and epsg, or neither")
        from .prediction import _support
        reference = next(self.predictor.parameters())
        burned_area = _tensor(burned_area, reference)
        environmental_data = _tensor(environmental_data, reference)
        if burned_area.ndim < 3 or burned_area.shape[-3] != 1:
            raise ValueError("burned_area must have shape [...,1,H,W]")
        if (environmental_data.ndim < 3
                or environmental_data.shape[:-3] != burned_area.shape[:-3]
                or environmental_data.shape[-2:] != burned_area.shape[-2:]):
            raise ValueError("burned_area and environmental_data must match leading and spatial dimensions")
        support, _, _ = _support(tuple(burned_area.shape), pixel_valid, time_valid)
        support = torch.as_tensor(support, device=reference.device)

        def input_validity(value, mask):
            if mask is None:
                return torch.broadcast_to(support, value.shape)
            mask = _tensor(mask, reference, boolean=True)
            if mask.shape != value.shape:
                raise ValueError("Validity masks must match the complete input shape")
            return mask & support

        inputs = dict(
            burned_area=burned_area, environmental_data=environmental_data,
            channel_names=channel_names,
            burned_area_valid=input_validity(burned_area, burned_area_valid),
            feature_valid=input_validity(environmental_data, feature_valid),
        )
        geometry = dict(affine_transform=affine_transform, epsg=epsg,
                        pixel_valid=pixel_valid, time_valid=time_valid, **metadata)
        return inputs, geometry

    def predict_cumulative(
        self, *args, hours, method="recursive", n_samples=1024, seed=0,
        trajectory_batch_size=32, environmental_forecast=None,
        missing_burned_area="unburned", **options,
    ) -> CumulativePrediction:
        """Estimate first-new-burn probability within explicit future durations.

        Accept a current sample or the raw-array inputs/masks accepted by
        predict(). ``hours`` is a positive whole-hour value or a nonempty
        sequence of distinct whole-hour values in recursive mode; the supplied
        order is retained. Leading dimensions are independent forecast cutoffs,
        rather than consecutive states of one trajectory.

        ``method='recursive'`` is the default. It averages ``n_samples=1024``
        absorbing binary trajectories with synchronous one-hour updates: cells
        ignited during one step become sources in the next step. Bayesian
        trajectories retain one sampled component throughout. Cell ignitions
        are independent conditional on the current state and component.
        ``n_samples`` and ``trajectory_batch_size=32`` must be positive integers;
        ``seed=0`` must be a nonnegative integer. Local random streams leave the
        global RNG unchanged. Repeated calls with the same inputs, seed, sample
        count and batch size are reproducible; changing requested horizon order
        or adding later horizons preserves estimates at existing horizons.

        Optional ``environmental_forecast`` is a mapping containing ``features``
        of shape ``[S,*L,C,H,W]``, ``channel_names``, and optionally boolean
        ``feature_valid`` of that complete shape. L denotes the current inputs'
        leading dimensions and C the supplied named channels; channel selection
        uses the saved model schema. Slice zero supplies conditions for the first
        hourly transition, and S must cover max(hours). The interval axis is
        separate from L. Extra intervals are unused. Without a forecast, current
        conditions repeat at every step. No future outcome labels are read.

        ``missing_burned_area='unburned'`` initializes unavailable or nonfinite
        initial burned states to zero only inside real input support. Explicit
        ``'unknown'`` retains their unavailable status. This assumption does not
        fill missing environmental inputs: predictions requiring those inputs
        remain unavailable. The full rectangular grid and static coordinates are
        retained; pixel/time padding inside the input stay excluded. Recursive
        ``boundary='zero'`` is the default: outside-grid burned sources are known
        unburned and environmental context is padded with zeros. This prevents
        missing outside-grid context from shrinking valid edge coverage as the
        horizon increases. Explicit ``boundary='unknown'`` retains uncertainty
        outside the rectangle and can restrict edge coverage. Interior missing
        features remain masked, and conservative coverage can still restrict
        predictions depending on unavailable interior context. Boundary policy
        does not resize any output arrays.
        Metadata records initialization/environment policies, sampling controls
        and the assumed initial count.

        The result's ``probability`` is cumulative first-new-burn probability;
        initialized prior burns have zero new-burn probability.
        ``burned_probability`` includes those prior burns. ``mc_standard_error``
        and nominal 95% pointwise Wilson ``confidence_lower/upper`` describe
        Monte Carlo uncertainty in new-burn estimates, rather than forecast
        calibration or evaluation-metric confidence intervals. Recursive rates
        are unavailable (NaN/false ``rate_valid``). Select an output with
        ``result.at(hours=h)``. Arrays have an added requested-horizon axis;
        coordinates and cutoff timestamps retain their original organization.

        ``method='fixed'`` retains the frozen-state calculation and positive
        fractional horizons, with the same missing_burned_area and zero-boundary
        defaults as ordinary and recursive prediction. Sampling controls are
        ignored there, and environmental forecasts are rejected. Both modes
        supply total burned probability.
        PatchRandomForest has a fixed fitted one-hour endpoint, so its fixed
        mode accepts only hours=1; use recursion for multi-hour forest results.

        After forecasting, ``result.evaluate(reference, hours=[1, 3])`` scores
        explicitly selected existing horizons using exact cutoff/endpoint
        states. ``quantity='new_burn'`` uses known initially unburned reference
        cells; ``quantity='burned'`` scores total endpoint occupancy. Original
        reference masks are never filled by the simulation's initial assumption.
        ``evaluate_cumulative(result, reference, hours=...)`` is the equivalent
        public function. Neither interface fits classification thresholds.
        """
        from .cumulative import _hours
        from .rollout import simulate, validate_controls

        if "dt_hours" in options:
            raise ValueError("predict_cumulative uses hours; do not also pass dt_hours")
        if method not in ("recursive", "fixed"):
            raise ValueError("method must be 'recursive' or 'fixed'")
        requested = _hours(hours)
        if self.family == "random_forest" and method == "fixed" and any(hour != 1 for hour in requested):
            raise ValueError("PatchRandomForest fixed mode supports only hours=1; use method='recursive' for multi-hour probabilities")
        if method == "recursive":
            validate_controls(requested, n_samples, seed, trajectory_batch_size)
        elif environmental_forecast is not None:
            raise ValueError("environmental_forecast is available only with method='recursive'")
        options.setdefault("boundary", "zero")
        inputs, geometry = self._prepare_prediction_inputs(
            *args, **{name: value for name, value in options.items() if name != "boundary"},
        )
        inputs, initialization = self._initialize_burned_area(inputs, geometry, missing_burned_area)
        if method == "fixed":
            predictions = []
            for hour in requested:
                prediction = self.predict(*args, dt_hours=hour,
                                          missing_burned_area=missing_burned_area, **options)
                total = torch.where(inputs["burned_area"] == 1, 1, prediction.probability)
                predictions.append(replace(
                    prediction, burned_probability=total.masked_fill(~prediction.valid, torch.nan),
                    metadata={**prediction.metadata, "method": "fixed", "environment_policy": "fixed"},
                ))
        else:
            from .prediction import _support
            support, _, _ = _support(
                tuple(inputs["burned_area"].shape), geometry["pixel_valid"], geometry["time_valid"],
            )
            support = torch.as_tensor(support, device=inputs["burned_area"].device)
            forecast = None
            forecast_valid = None
            if environmental_forecast is not None:
                if not isinstance(environmental_forecast, Mapping):
                    raise TypeError("environmental_forecast must be a mapping")
                # Forecasts add an interval axis, not a dataset time axis. Apply
                # base support separately rather than interpreting its geometry.
                reference = next(self.predictor.parameters())
                base_shape = tuple(inputs["environmental_data"].shape)
                forecast = _tensor(environmental_forecast["features"], reference)
                if (forecast.ndim != len(base_shape) + 1
                        or tuple(forecast.shape[1:-3]) != base_shape[:-3]
                        or tuple(forecast.shape[-2:]) != base_shape[-2:]):
                    raise ValueError("environmental_forecast features must have shape [S,*current_environment_shape] after channel selection")
                if forecast.shape[0] < max(requested):
                    raise ValueError("environmental_forecast must cover max(hours) hourly intervals")
                forecast_valid = environmental_forecast.get("feature_valid")
                if forecast_valid is not None:
                    forecast_valid = _tensor(forecast_valid, reference, boolean=True)
                    if forecast_valid.shape != forecast.shape:
                        raise ValueError("environmental_forecast feature_valid must match the complete feature shape")
                # Channel projection validates complete one-hot groups. Apply
                # base support first so padding cannot become a known all-zero
                # group merely because the forecast names require reordering.
                raw_forecast_support = support.unsqueeze(0)
                forecast_valid = (raw_forecast_support.expand_as(forecast)
                                  if forecast_valid is None
                                  else forecast_valid & raw_forecast_support)
                # Extra intervals have no effect, including their categorical
                # values. Still validate the original mask's full shape/type.
                steps = int(max(requested))
                forecast, forecast_valid = self._sample_environment(dict(
                    features=forecast[:steps], channel_names=environmental_forecast["channel_names"],
                    feature_valid=None if forecast_valid is None else forecast_valid[:steps],
                ))
                if tuple(forecast.shape[1:]) != base_shape:
                    raise ValueError("environmental_forecast channel count must match its selected checkpoint schema")
                forecast_support = support.unsqueeze(0)
                forecast_valid = (forecast_support.expand_as(forecast) if forecast_valid is None
                                  else forecast_valid & forecast_support)
            outputs = simulate(
                self.predictor, **inputs, hours=requested, n_samples=int(n_samples),
                seed=int(seed), trajectory_batch_size=int(trajectory_batch_size),
                boundary=options.get("boundary", "zero"),
                environmental_forecast=forecast, forecast_valid=forecast_valid,
                missing_burned_area=missing_burned_area,
                assumed_unburned_cells=initialization["assumed_unburned_cells"],
            )
            for output in outputs:
                output["metadata"] = {**output["metadata"],
                                      **getattr(self.predictor, "prediction_metadata", {})}
            predictions = tuple(Prediction.from_details(
                output.pop("details"), dt_hours=hour, **geometry, **output,
            ) for hour, output in zip(requested, outputs))
        return CumulativePrediction(hours=requested, _predictions=predictions)

    def predict_coordinates(
        self, burned_area: Any, environmental_data: Any, *, channel_names: Sequence[str],
        affine_transform: Any, epsg: Any, pixel_valid=None, time_valid=None,
        burned_area_valid=None, feature_valid=None, dt_hours=1.0, boundary="zero",
        missing_burned_area="unburned",
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return (probability matrix, WGS84 coordinate matrix) for raw inputs.

        Probability has shape [T,1,H,W] or [B,T,1,H,W] on the model device.
        Coordinates have shape [H,W,2] or [B,H,W,2], with no time or channel
        dimension. A single snapshot [1,H,W] also returns coordinates [H,W,2].
        The final axis is (latitude,longitude) in degrees, as CPU float64 tensors.
        This preserves geographic precision on devices that do not support
        float64. affine_transform contains the six
        pixel-corner coefficients (a,b,c,d,e,f); epsg identifies its source CRS.
        A shared grid or one grid/EPSG per batch item is supported. Missing
        georeferencing is an error. Unknown probabilities keep their locations;
        spatial padding supplied by pixel_valid has NaN coordinates. time_valid
        masks prediction inputs/outputs without changing these static locations.
        Use predict() for the structured result, validity masks and rates.
        """
        result = self.predict(
            burned_area, environmental_data, channel_names=channel_names,
            burned_area_valid=burned_area_valid, feature_valid=feature_valid,
            dt_hours=dt_hours, boundary=boundary, missing_burned_area=missing_burned_area,
            affine_transform=affine_transform,
            epsg=epsg, pixel_valid=pixel_valid, time_valid=time_valid,
        )
        return result.probability, result.coordinates

    def predict_sample(
        self, sample: Mapping[str, Any], *, dt_hours=1.0, boundary="zero",
        missing_burned_area="unburned",
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return aligned probability and Earth coordinates from a sample or batch.

        Coordinates are static [H,W,2], or [B,H,W,2] for collated batches,
        independently of sequence length or temporal padding. Current inputs,
        affine_transform, epsg and optional spatial padding masks are consumed.
        Future outcomes and arrival labels are unused.
        """
        result = self.predict(sample, dt_hours=dt_hours, boundary=boundary,
                              missing_burned_area=missing_burned_area)
        if result.coordinates is None:
            raise ValueError("predict_sample requires affine_transform and epsg for coordinates")
        return result.probability, result.coordinates

    def predict_proba(self, burned_area: Any, environmental_data: Any, **options) -> torch.Tensor:
        """Return only probability [..., 1, H, W], without requiring georeferencing.

        Options are those of predict_details(). Use predict() for a structured
        result or predict_coordinates()/predict_sample() for the legacy tuple.
        """
        return self.predict_details(burned_area, environmental_data, **options).probability

    def predict_active_flames(
        self, burned_area: Any, environmental_data: Any, *, channel_names,
        residence_time, grid, burned_area_valid=None, feature_valid=None,
    ):
        """Estimate next-hour surface-flame occupancy for one spatial snapshot.

        Requires a literature-derived or explicitly supplied FlameResidenceTime
        and an AffineGrid in metres. Conditional first-new-burning arrival is
        uniform in the hour. The returned endpoint map provides position
        extraction with an explicit probability threshold. Existing flames need
        separate arrival ages; cumulative burned cells are not assumed active.
        The original checkpoint and its prediction/validity contract are reused.
        """
        from wildfire.heat import forecast_active_flames
        from wildfire.heat import _single_matrix
        from wildfire.heat import _mask

        burned = _single_matrix(burned_area, "burned_area")
        known = np.isfinite(burned)
        if burned_area_valid is not None:
            known &= _mask(burned_area_valid, burned.shape, "burned_area_valid")
        if np.any(known & (burned != 0) & (burned != 1)):
            raise ValueError("known burned_area must contain binary cumulative states")
        prediction = self.predict_details(
            burned_area, environmental_data, channel_names=channel_names,
            burned_area_valid=burned_area_valid, feature_valid=feature_valid,
            dt_hours=1.0, boundary="unknown", missing_burned_area="unknown",
        )
        probability = _single_matrix(prediction.probability, "prediction probability").copy()
        valid = _single_matrix(prediction.valid, "prediction validity").copy()
        already_burned = known & (burned == 1)
        probability[already_burned] = 0.0
        valid[already_burned] = True
        result = forecast_active_flames(
            probability, residence_time, 3600.0, grid=grid, probability_valid=valid,
        )
        result.metadata["predictor"] = {
            "checkpoint_path": str(self.checkpoint_path),
            "checkpoint_sha256": self.checkpoint_sha256,
            "architecture": self.predictor.contract["architecture"],
            "probability_semantics": "first new cumulative burning during next exact hour",
        }
        result.endpoint.metadata["predictor"] = deepcopy(result.metadata["predictor"])
        return result

    def predict_active_flames_sample(self, sample: Mapping[str, Any], *, residence_time):
        """Use current features/state and sample grid; arrival/future labels unused.

        Select one snapshot before calling. Use active_flames_from_arrival
        explicitly for a separate retrospective arrival scenario.
        """
        from wildfire.heat import AffineGrid

        transform = sample["affine_transform"]
        if hasattr(transform, "detach"):
            transform = transform.detach().cpu().numpy()
        grid = AffineGrid(tuple(np.asarray(transform)))
        epsg = None
        if "epsg" in sample:
            from pyproj import CRS

            raw_epsg = sample["epsg"]
            if hasattr(raw_epsg, "detach"):
                raw_epsg = raw_epsg.detach().cpu().numpy()
            raw_epsg = np.asarray(raw_epsg)
            if raw_epsg.ndim != 0 or raw_epsg.dtype.kind not in "iu":
                raise ValueError("sample EPSG must be an integer scalar")
            epsg = int(raw_epsg)
            crs = CRS.from_epsg(epsg)
            if not crs.is_projected or any(axis.unit_conversion_factor != 1.0 for axis in crs.axis_info):
                raise ValueError("active-flame positions require a projected CRS in metres")
        if "time_valid" in sample:
            time_valid = sample["time_valid"]
            if hasattr(time_valid, "detach"):
                time_valid = time_valid.detach().cpu().numpy()
            time_valid = np.asarray(time_valid)
            if time_valid.dtype != np.bool_ or time_valid.size != 1 or not time_valid.all():
                raise ValueError("active-flame forecasting requires one valid, unpadded time snapshot")
        features, feature_valid = self._sample_environment(sample)
        result = self.predict_active_flames(
            sample["burned_area"], features,
            channel_names=self.channel_names, residence_time=residence_time, grid=grid,
            burned_area_valid=sample.get("burned_area_valid"), feature_valid=feature_valid,
        )
        if epsg is not None:
            result.metadata["epsg"] = epsg
            result.endpoint.metadata["epsg"] = epsg
        if "time_utc" in sample:
            time = sample["time_utc"]
            if hasattr(time, "detach"):
                time = time.detach().cpu().numpy()
            times = np.asarray(time)
            if times.size != 1 or times.dtype.kind not in "iu":
                raise ValueError("active-flame forecasting requires one integer Unix-seconds time snapshot")
            result.metadata["cutoff_unix_s"] = int(times.reshape(-1)[0])
            result.endpoint.metadata["endpoint_unix_s"] = int(times.reshape(-1)[0]) + 3600
        return result

    @classmethod
    def train(
        cls, prepared_data: str | Path, output_dir: str | Path, *,
        family: ModelFamily = "exponential", config: TrainingConfig | None = None,
    ) -> WildfireModel:
        """Fit the exponential trainer and load its validation-selected checkpoint.

        prepared_data contains metadata.json and train/validation/test.npz. The
        existing trainers fit normalization on training rows and keep the saved
        event partitions. output_dir must be new or empty. training_metrics holds
        the returned evaluation report. This operation uses the configured random
        seed through the original trainer and restores the prior CPU thread count.
        """
        if family == "direct":
            raise ValueError(_SIGNED_RETIREMENT)
        if family != "exponential":
            raise ValueError("family must be exponential")
        config = TrainingConfig() if config is None else config
        if not isinstance(config, TrainingConfig):
            raise TypeError("config must be TrainingConfig")
        device = _device(config.device)
        options = asdict(config)
        # Convert accepted scalar types to plain types for JSON/checkpoint metadata.
        for name in ("epochs", "patience", "batch_size", "hidden_channels", "seed", "threads"):
            options[name] = int(options[name])
        for name in ("learning_rate", "weight_decay", "categorical_balance_min_frequency", "categorical_balance_max_factor"):
            options[name] = float(options[name])
        options.update(data_dir=Path(prepared_data).expanduser().resolve(),
                       output_dir=Path(output_dir).expanduser().resolve(), device=str(device))
        trainer = importlib.import_module(".train", package=__package__)
        previous_threads = torch.get_num_threads()
        try:
            metrics = trainer.train(argparse.Namespace(**options))
        finally:
            torch.set_num_threads(previous_threads)
        result = cls.from_checkpoint(options["output_dir"] / "checkpoint.pt", device=device)
        result.training_metrics = metrics
        return result

    def save(self, path: str | Path, *, overwrite: bool = False) -> Path:
        """Atomically save resident parameters with the original checkpoint metadata.

        Saved normalization and contract are retained, without fitting. Existing
        destinations raise FileExistsError unless overwrite=True is explicit.
        Forests retain their portable joblib format and require a .joblib,
        .pkl, or .pickle destination; tensor models retain the torch format.
        """
        destination = Path(path).expanduser().absolute()
        if self.family == "random_forest" and destination.suffix.lower() not in (".joblib", ".pkl", ".pickle"):
            raise ValueError("Save PatchRandomForest checkpoints with a .joblib extension")
        destination.parent.mkdir(parents=True, exist_ok=True)
        saved = dict(self._checkpoint)
        if self.family == "random_forest":
            saved = self.predictor.checkpoint_payload()
        elif self.family == "mixture_exponential":
            from .inference import bayesian_checkpoint_payload
            saved = bayesian_checkpoint_payload(self.predictor, saved)
        else:
            saved.update(
                contract=self.contract, best_epoch=self.predictor.best_epoch,
                model_state_dict={name: tensor.detach().cpu().clone()
                                  for name, tensor in self.predictor.model.state_dict().items()},
                normalization_mean=self.predictor.mean[:, 0, 0].detach().cpu().clone(),
                normalization_std=self.predictor.std[:, 0, 0].detach().cpu().clone(),
            )
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".checkpoint-", delete=False) as stream:
                temporary = Path(stream.name)
                if self.family == "random_forest":
                    import joblib
                    joblib.dump(saved, stream, compress=3)
                else:
                    torch.save(saved, stream)
                stream.flush()
                os.fsync(stream.fileno())
            if overwrite:
                os.replace(temporary, destination)
            else:
                os.link(temporary, destination)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return destination

    def heat_model(
        self, *, grid, combustion, radiative_fraction, emission_height_m,
        receiver_height_m=0.0, atmospheric_transmissivity=1.0,
        atmosphere=None, transfer_atol=1e-7, transfer_rtol=1e-2,
        ignition_time_model="uniform",
        interval_s=3600.0, residence_time=None, cell_burning_duration=None, epsg=None,
        spread_rate_m_s=None, spread_direction_deg=0.0, use_cell_burning_duration=True,
    ):
        """Compose these resident weights with the existing WildfireHeatModel.

        Required parameters: grid, combustion, radiative_fraction, emission_height_m.
        Its predict_sample() accepts one spatial snapshot and returns a tuple of
        interval-mean radiant heat in W/m² and WGS84 coordinates. Use
        predict_sample_details() for incident energy and coverage bounds.
        Sample arrival/elapsed fields determine existing burning from age and
        the supplied combustion duration by default. Reconstructed arrival data
        remain retrospective scenarios. Set initial_burning_from_arrival=False
        on the heat prediction call to omit sample timing.

        Known previous burns without timing retain unresolved current activity
        and conditional flux bounds. All heat routes share
        burning_state_from_arrival; explicit include_previous_burning=False
        requests new-burning-only heat. An optional CellBurningDuration retimes
        source emission while preserving the supplied consumed-fuel energy.
        With residence_time, automatic cell duration is enabled by default;
        spread_rate_m_s=None uses the reported PT-FireSprd median 341 m/h.
        Supply a positive scalar or spatial speed map to change that scenario,
        and set spread_direction_deg counterclockwise from projected +x.
        use_cell_burning_duration=False explicitly retains point duration.

        ``atmosphere=HomogeneousAtmosphere(...)`` selects path-dependent grey
        Beer--Lambert absorption instead of a supplied scalar transmissivity.
        ``ignition_time_model='constant_hazard'`` is an explicit exponential
        first-ignition scenario; finite neural rates are retained. Bayesian
        probability mixtures require componentwise timing and reject their
        equivalent rate as a constant hazard. Uniform timing remains available.
        """
        from wildfire.heat import WildfireHeatModel

        provenance = {
            "checkpoint_path": str(self.checkpoint_path),
            "checkpoint_sha256": self.checkpoint_sha256,
            "architecture": self.predictor.contract["architecture"],
            "best_epoch": int(self.predictor.best_epoch), "device": str(self.device),
            "channel_names": list(self.channel_names),
            "source_channels": list(self.predictor.source_channels),
            "categorical_classes": deepcopy(self.predictor.categorical_classes),
            "normalization": "checkpoint's saved training-only statistics",
            "probability_semantics": "new cumulative burning during the next exact hour",
        }
        return WildfireHeatModel(
            self.predictor, predictor_provenance=provenance, grid=grid,
            combustion=combustion, radiative_fraction=radiative_fraction,
            emission_height_m=emission_height_m, receiver_height_m=receiver_height_m,
            atmospheric_transmissivity=atmospheric_transmissivity, interval_s=interval_s,
            atmosphere=atmosphere, transfer_atol=transfer_atol, transfer_rtol=transfer_rtol,
            ignition_time_model=ignition_time_model,
            residence_time=residence_time, cell_burning_duration=cell_burning_duration, epsg=epsg,
            spread_rate_m_s=spread_rate_m_s, spread_direction_deg=spread_direction_deg,
            use_cell_burning_duration=use_cell_burning_duration,
        )
