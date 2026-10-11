"""Api operations for the wildfire workspace."""
from __future__ import annotations

from .paths import resolve_recorded_path



# Api
# Importable data, fitted-model, training, and radiant-heat interface.
# 
# Prediction consumes current burned state, environmental inputs and their masks.
# It does not consume outcome labels or fit preprocessing. Public predictions
# return (probability, coordinates): [T, 1, H, W] and [H, W, 2], or
# [B, T, 1, H, W] and [B, H, W, 2] for batches. Coordinates are static WGS84
# (latitude, longitude) pixel centers in degrees. Detailed results retain
# the original masks, rates, and scores through the explicit *_details methods.


import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass
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
from wildfire.data import WildfireSequenceDataset
from wildfire.data import DEFAULT_ROOT


__all__ = ["TrainingConfig", "WildfireModel", "load_data", "load_model"]

ModelFamily = Literal["exponential"]
Prediction = BurnProbability
_FAMILIES = {
    "EnvironmentConditionedConvolution": "exponential",
    "LearnedNonnegativeKernel": "exponential",
    "MixedNonnegativeKernel": "exponential",
    "NeuralMixedNonnegativeKernel": "exponential",
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


def load_data(data_root: str | Path = DEFAULT_ROOT, **options) -> WildfireSequenceDataset:
    """Open an aligned dataset with the existing dataset's keyword options.

    Use as a context manager to close cached raster readers. This unbound loader
    does not select a model's channels; use model.load_data() for a saved schema.
    """
    return WildfireSequenceDataset(data_root, **options)


def load_model(path: str | Path, *, device: str | torch.device = "cpu") -> WildfireModel:
    """Load a supported checkpoint with its saved channel/preprocessing contract."""
    return WildfireModel.from_checkpoint(path, device=device)


class WildfireModel:
    """One fitted probability model with its saved preprocessing and channel order.

    Construct with from_checkpoint()/load_model(), or train() on an existing
    prepared cache. 'exponential' converts a nonnegative hourly rate with the
    existing exponential link. Signed direct-convolution checkpoints are retired.
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
        self.predictor.to(_device(device))
        return self

    def load_data(self, data_root: str | Path = DEFAULT_ROOT, **options) -> WildfireSequenceDataset:
        """Open data using exactly this checkpoint's channel order and vocabulary.

        Supply event, time, sequence, or patch filters as dataset options. Channel
        and categorical options are fixed here; load_data() permits custom schemas.
        """
        fixed = {"channels", "categorical_encoding", "categorical_classes"} & options.keys()
        if fixed:
            raise ValueError(f"Model-bound data loading fixes these options: {sorted(fixed)}")
        dataset = load_data(
            data_root, channels=self.channel_names, categorical_encoding="one_hot",
            categorical_classes=self.predictor.categorical_classes or None, **options,
        )
        if tuple(dataset.channel_names) != self.channel_names:
            dataset.close()
            raise ValueError("Dataset channel order differs from the checkpoint")
        return dataset

    def predict_details(
        self, burned_area: Any, environmental_data: Any, *, channel_names: Sequence[str],
        burned_area_valid=None, feature_valid=None, dt_hours=1.0, boundary="unknown",
    ) -> Prediction:
        """Infer from raw ordered inputs; return tensors on this model's device.

        Inputs retain shape [..., C, H, W]; burned_area has C=1. Masks must be
        boolean with the matching full shape. Unknown outputs remain NaN/false.
        The result also has rate/rate_valid. Changing dt_hours rescales the
        frozen hourly rate mathematically; the trained endpoint is one hour.
        """
        reference = next(self.predictor.parameters())
        duration = (torch.as_tensor(dt_hours, device=reference.device)
                    if isinstance(dt_hours, (torch.Tensor, np.ndarray))
                    else dt_hours)
        with torch.inference_mode():
            self.predictor.eval()
            return self.predictor(
                _tensor(burned_area, reference), _tensor(environmental_data, reference),
                channel_names=channel_names,
                burned_area_valid=(None if burned_area_valid is None
                                   else _tensor(burned_area_valid, reference, boolean=True)),
                feature_valid=(None if feature_valid is None
                               else _tensor(feature_valid, reference, boolean=True)),
                dt_hours=duration, boundary=boundary,
            )

    def predict_sample_details(self, sample: Mapping[str, Any], *, dt_hours=1.0, boundary="unknown") -> Prediction:
        """Return probability, validity and diagnostics without reading outcome labels."""
        return self.predict_details(
            sample["burned_area"], sample["features"], channel_names=sample["channel_names"],
            burned_area_valid=sample.get("burned_area_valid"), feature_valid=sample.get("feature_valid"),
            dt_hours=dt_hours, boundary=boundary,
        )

    def predict(
        self, burned_area: Any, environmental_data: Any, *, channel_names: Sequence[str],
        affine_transform: Any, epsg: Any, pixel_valid=None, time_valid=None,
        burned_area_valid=None, feature_valid=None, dt_hours=1.0, boundary="unknown",
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
        is accepted for compatibility and does not mask these static locations.
        Use predict_details() for validity masks, raw scores or hourly rates.
        """
        from wildfire.coordinates import geographic_coordinates

        prediction = self.predict_details(
            burned_area, environmental_data, channel_names=channel_names,
            burned_area_valid=burned_area_valid, feature_valid=feature_valid,
            dt_hours=dt_hours, boundary=boundary,
        )
        # The last leading dimension is time; any earlier leading dimensions
        # identify batches of fixed grids. A snapshot has no leading dimensions.
        shape = tuple(prediction.probability.shape)
        coordinate_shape = shape[:-4] + shape[-2:]
        coordinates = geographic_coordinates(
            coordinate_shape, affine_transform=affine_transform,
            epsg=epsg, pixel_valid=pixel_valid,
        )
        return prediction.probability, torch.from_numpy(coordinates)

    def predict_sample(
        self, sample: Mapping[str, Any], *, dt_hours=1.0, boundary="unknown",
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """Return aligned probability and Earth coordinates from a sample or batch.

        Coordinates are static [H,W,2], or [B,H,W,2] for collated batches,
        independently of sequence length or temporal padding. Current inputs,
        affine_transform, epsg and optional spatial padding masks are consumed.
        Future outcomes and arrival labels are unused.
        """
        return self.predict(
            sample["burned_area"], sample["features"], channel_names=sample["channel_names"],
            affine_transform=sample["affine_transform"], epsg=sample["epsg"],
            pixel_valid=sample.get("pixel_valid"), time_valid=sample.get("time_valid"),
            burned_area_valid=sample.get("burned_area_valid"), feature_valid=sample.get("feature_valid"),
            dt_hours=dt_hours, boundary=boundary,
        )

    def predict_proba(self, burned_area: Any, environmental_data: Any, **options) -> torch.Tensor:
        """Return only probability [..., 1, H, W], without requiring georeferencing.

        Options are those of predict_details(). Use predict()/predict_sample()
        for the probability/coordinate tuple.
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
            dt_hours=1.0, boundary="unknown",
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
        result = self.predict_active_flames(
            sample["burned_area"], sample["features"],
            channel_names=sample["channel_names"], residence_time=residence_time, grid=grid,
            burned_area_valid=sample.get("burned_area_valid"), feature_valid=sample.get("feature_valid"),
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
        """
        destination = Path(path).expanduser().absolute()
        destination.parent.mkdir(parents=True, exist_ok=True)
        saved = dict(self._checkpoint)
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

    def heat_model(self, **physical_parameters):
        """Compose these resident weights with the existing WildfireHeatModel.

        Required parameters: grid, combustion, radiative_fraction, emission_height_m.
        Its predict_sample() accepts one spatial snapshot and returns a tuple of
        interval-mean radiant heat in W/m² and WGS84 coordinates. Use
        predict_sample_details() for incident energy and coverage bounds.
        Sample arrival/elapsed fields determine existing burning from age and
        the supplied combustion duration by default. Reconstructed arrival data
        remain retrospective scenarios. Set initial_burning_from_arrival=False
        on the heat prediction call to omit sample timing.
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
        return WildfireHeatModel(self.predictor, predictor_provenance=provenance, **physical_parameters)
