"""Importable data, fitted-model, training, and radiant-heat interface.

Prediction consumes current burned state, environmental inputs and their masks.
It does not consume outcome labels or fit preprocessing. Output tensors retain
all input batch/time dimensions and the singleton channel axis [..., 1, H, W].
"""

from __future__ import annotations

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

from .probability_model.model import BurnProbability
from .probability_model.direct_convolution.model import DirectBurnPrediction
from .probability_model.runtime import choose_device
from .pytorch_loader import WildfireSequenceDataset
from .pytorch_loader.dataset import DEFAULT_ROOT


__all__ = ["TrainingConfig", "WildfireModel", "load_data", "load_model"]

ModelFamily = Literal["exponential", "direct"]
Prediction = BurnProbability | DirectBurnPrediction
_FAMILIES = {
    "EnvironmentConditionedConvolution": "exponential",
    "DirectEnvironmentConditionedConvolution": "direct",
}


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
    """Options for either existing trainer; cache metadata fixes the channels/kernel.

    Positive integer fields exclude booleans. Rates must be finite; learning_rate
    is positive and weight_decay is nonnegative. Device 'auto' selects CUDA,
    then MPS, then CPU. The default uses CPU for reproducible examples.
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


def load_data(data_root: str | Path = DEFAULT_ROOT, **options) -> WildfireSequenceDataset:
    """Open an aligned dataset with the existing dataset's keyword options.

    Use as a context manager to close cached raster readers. This unbound loader
    does not select a model's channels; use model.load_data() for a saved schema.
    """
    return WildfireSequenceDataset(data_root, **options)


def load_model(path: str | Path, *, device: str | torch.device = "cpu") -> WildfireModel:
    """Load either checkpoint family, keeping its saved channel/preprocessing contract."""
    return WildfireModel.from_checkpoint(path, device=device)


class WildfireModel:
    """One fitted probability model with its saved preprocessing and channel order.

    Construct with from_checkpoint()/load_model(), or train() on an existing
    prepared cache. 'direct' predicts clipped signed scores over exactly one hour;
    'exponential' converts an hourly rate with the existing exponential link.
    """

    def __init__(self, predictor, checkpoint: Mapping[str, Any], path: Path, digest: str):
        self.predictor = predictor
        self.checkpoint_path = path
        self.checkpoint_sha256 = digest
        self._checkpoint = checkpoint
        self.training_metrics: dict[str, Any] | None = None

    @classmethod
    def from_checkpoint(cls, path: str | Path, *, device: str | torch.device = "cpu") -> WildfireModel:
        path = Path(path).expanduser().resolve()
        selected_device = _device(device)
        saved = torch.load(path, map_location="cpu", weights_only=True)
        if not isinstance(saved, dict) or not isinstance(saved.get("contract"), dict):
            raise ValueError("Checkpoint must contain a model contract")
        architecture = saved["contract"].get("architecture")
        if architecture not in _FAMILIES:
            raise ValueError(f"Unsupported checkpoint architecture: {architecture!r}")
        module = (".probability_model.direct_convolution.inference"
                  if _FAMILIES[architecture] == "direct" else ".probability_model.inference")
        loader = importlib.import_module(module, package=__package__).load_trained_model
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

    def predict(
        self, burned_area: Any, environmental_data: Any, *, channel_names: Sequence[str],
        burned_area_valid=None, feature_valid=None, dt_hours=1.0, boundary="unknown",
    ) -> Prediction:
        """Infer from raw ordered inputs; return tensors on this model's device.

        Inputs retain shape [..., C, H, W]; burned_area has C=1. Masks must be
        boolean with the matching full shape. Unknown outputs remain NaN/false.
        The exponential result also has rate/rate_valid; the direct result has
        raw_score. Changing dt_hours rescales only the exponential family, whose
        trained endpoint is one hour; the direct family requires exactly 1.0.
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

    def predict_sample(self, sample: Mapping[str, Any], *, dt_hours=1.0, boundary="unknown") -> Prediction:
        """Predict from one dataset sample or collated batch, without reading labels."""
        return self.predict(
            sample["burned_area"], sample["features"], channel_names=sample["channel_names"],
            burned_area_valid=sample.get("burned_area_valid"), feature_valid=sample.get("feature_valid"),
            dt_hours=dt_hours, boundary=boundary,
        )

    def predict_proba(self, burned_area: Any, environmental_data: Any, **options) -> torch.Tensor:
        """Return only probability [..., 1, H, W]; predict() also returns validity."""
        return self.predict(burned_area, environmental_data, **options).probability

    @classmethod
    def train(
        cls, prepared_data: str | Path, output_dir: str | Path, *,
        family: ModelFamily = "direct", config: TrainingConfig | None = None,
    ) -> WildfireModel:
        """Fit either trainer and load its validation-selected checkpoint.

        prepared_data contains metadata.json and train/validation/test.npz. The
        existing trainers fit normalization on training rows and keep the saved
        event partitions. output_dir must be new or empty. training_metrics holds
        the returned evaluation report. This operation uses the configured random
        seed through the original trainer and restores the prior CPU thread count.
        """
        if family not in ("exponential", "direct"):
            raise ValueError("family must be exponential or direct")
        config = TrainingConfig() if config is None else config
        if not isinstance(config, TrainingConfig):
            raise TypeError("config must be TrainingConfig")
        device = _device(config.device)
        options = asdict(config)
        # Convert accepted scalar types to plain types for JSON/checkpoint metadata.
        for name in ("epochs", "patience", "batch_size", "hidden_channels", "seed", "threads"):
            options[name] = int(options[name])
        for name in ("learning_rate", "weight_decay"):
            options[name] = float(options[name])
        options.update(data_dir=Path(prepared_data).expanduser().resolve(),
                       output_dir=Path(output_dir).expanduser().resolve(), device=str(device))
        module = (".probability_model.direct_convolution.train"
                  if family == "direct" else ".probability_model.train")
        trainer = importlib.import_module(module, package=__package__)
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
        Its predict_sample() accepts one spatial snapshot and returns interval-mean
        radiant heat in W/m² and incident energy in J/m², with coverage bounds.
        """
        from expected_heat_flux import WildfireHeatModel

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
