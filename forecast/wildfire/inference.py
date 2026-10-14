"""Load fitted models with their saved preprocessing and channel contracts."""

from pathlib import Path
from .paths import resolve_recorded_path

import torch

from .models import (
    EnvironmentConditionedConvolution, NormalizedBurnModel, TrainedBurnModel,
    build_kernel_model,
    build_mixed_kernel_model, build_neural_mixed_kernel_model,
    BayesianBurnModel,
)
from .schema import one_hot_groups

__all__ = [
    "NormalizedBurnModel", "TrainedBurnModel", "checkpoint_normalization",
    "load_single_trained_model", "load_mixed_trained_model",
    "load_neural_mixed_trained_model", "load_trained_model",
    "load_bayesian_trained_model",
]


# Saved checkpoint normalization
# ------------------------------


def checkpoint_normalization(saved, channels, *, shape_error, require_floating=False):
    """Validate saved scales without fitting or inspecting any data labels."""
    mean, std = saved["normalization_mean"], saved["normalization_std"]
    if mean.shape != (len(channels),) or std.shape != mean.shape:
        raise ValueError(shape_error)
    if ((require_floating and (not mean.is_floating_point() or not std.is_floating_point()))
            or not torch.isfinite(mean).all() or not torch.isfinite(std).all()
            or not (std > 0).all()):
        raise ValueError("Checkpoint normalization must be finite with positive scales")
    return mean, std


# Single-kernel checkpoint inference
# ----------------------------------


def load_single_trained_model(path: str | Path, device="cpu") -> TrainedBurnModel:
    """Load parameters, normalization and channel contract, using weights_only.

    Default inference is CPU. Call with device='mps'/'cuda', or move the result
    with .to(device), and move data and masks to the same device. This function
    does not refit preprocessing, inspect labels, or read the training cache.
    A contact-only checkpoint also returns structural zeros for known unburned
    cells whose complete source neighborhood is unburned. Unknown source or
    environmental context remains unavailable (NaN/false mask).
    """
    saved = torch.load(resolve_recorded_path(path), map_location="cpu", weights_only=True)
    return single_model_from_checkpoint(saved, device=device)


def single_model_from_checkpoint(saved, device="cpu") -> TrainedBurnModel:
    """Reconstruct a single fitted kernel from an embedded checkpoint payload."""
    if not isinstance(saved, dict) or not isinstance(saved.get("contract"), dict):
        raise ValueError("A component checkpoint must contain its saved contract")
    contract = saved["contract"]
    if (contract["format_version"] != 1
            or contract["architecture"] not in ("EnvironmentConditionedConvolution", "LearnedNonnegativeKernel")
            or contract["dt_hours"] != 1.0 or contract["center_rate"] != 0.0):
        raise ValueError("Unsupported trained probability checkpoint contract")
    channels = contract["channels"]
    one_hot_groups(contract)
    if len(channels) != contract["in_channels"] or len(set(channels)) != len(channels):
        raise ValueError("Invalid checkpoint channel schema")
    mean, std = checkpoint_normalization(
        saved, channels, shape_error="Checkpoint normalization shape differs from its channel schema",
        require_floating=False,
    )
    if contract["architecture"] == "EnvironmentConditionedConvolution":
        model = EnvironmentConditionedConvolution(
            contract["in_channels"], contract["kernel_size"], contract["hidden_channels"],
        )
    else:
        configuration = contract.get("kernel_model")
        if not isinstance(configuration, dict):
            raise ValueError("A learned kernel checkpoint must declare its kernel_model configuration")
        required = {"architecture", "hidden_channels", "depth", "dropout"}
        if set(configuration) != required:
            raise ValueError("Invalid learned kernel checkpoint configuration fields")
        model = build_kernel_model(contract["in_channels"], contract["kernel_size"], **configuration)
    model = model.to(dtype=mean.dtype)
    model.load_state_dict(saved["model_state_dict"], strict=True)
    result = TrainedBurnModel(model, mean, std, contract, saved["best_epoch"])
    return result.to(device=device, dtype=mean.dtype).eval()


def bayesian_checkpoint_payload(predictor, original=None):
    """Export resident component parameters and preprocessing, without source files."""
    from copy import deepcopy

    saved = deepcopy(original) if original is not None else {}
    components = []
    originals = saved.get("components", [{} for _ in predictor.components])
    for component, payload in zip(predictor.components, originals, strict=True):
        payload.update(
            contract=deepcopy(component.contract), best_epoch=component.best_epoch,
            model_state_dict={name: value.detach().cpu().clone()
                              for name, value in component.model.state_dict().items()},
            normalization_mean=component.mean[:, 0, 0].detach().cpu().clone(),
            normalization_std=component.std[:, 0, 0].detach().cpu().clone(),
        )
        components.append(payload)
    saved.update(contract=deepcopy(predictor.contract), components=components,
                 log_posterior_weights=predictor.log_posterior_weights.detach().cpu().clone(),
                 best_epoch=0)
    return saved


def load_bayesian_trained_model(path: str | Path, device="cpu") -> BayesianBurnModel:
    """Load a self-contained average of independently fitted single kernels."""
    saved = torch.load(resolve_recorded_path(path), map_location="cpu", weights_only=True)
    contract = saved.get("contract") if isinstance(saved, dict) else None
    if (not isinstance(contract, dict) or contract.get("format_version") != 1
            or contract.get("architecture") != "BayesianModelAverage"
            or contract.get("dt_hours") != 1.0 or contract.get("center_rate") != 0.0):
        raise ValueError("Unsupported Bayesian model-average checkpoint contract")
    payloads = saved.get("components")
    if not isinstance(payloads, list) or len(payloads) < 2:
        raise ValueError("A Bayesian checkpoint must embed at least two component checkpoints")
    if not isinstance(saved.get("log_posterior_weights"), torch.Tensor):
        raise ValueError("A Bayesian checkpoint must contain log posterior weights")
    components = [single_model_from_checkpoint(payload) for payload in payloads]
    result = BayesianBurnModel(components, saved["log_posterior_weights"], contract)
    return result.to(device).eval()


# Multiscale mixture checkpoint inference
# ---------------------------------------
def load_mixed_trained_model(path: str | Path, device="cpu") -> TrainedBurnModel:
    """Load a mixed checkpoint without fitting, labels, or a training cache.

    The returned public grid model accepts raw environmental channels in the
    saved order. Its masks, contact eligibility, structural no-contact zeros,
    horizon handling, and boundary options match the existing fitted kernels.
    """
    saved = torch.load(resolve_recorded_path(path), map_location="cpu", weights_only=True)
    if not isinstance(saved, dict) or not isinstance(saved.get("contract"), dict):
        raise ValueError("A mixed checkpoint must contain its saved contract")
    contract = saved["contract"]
    if (contract.get("format_version") != 1
            or contract.get("architecture") != "MixedNonnegativeKernel"
            or contract.get("dt_hours") != 1.0 or contract.get("center_rate") != 0.0):
        raise ValueError("Unsupported trained mixed probability checkpoint contract")
    channels = contract.get("channels")
    if (not isinstance(channels, (list, tuple)) or not channels
            or any(not isinstance(channel, str) or not channel for channel in channels)
            or len(set(channels)) != len(channels)
            or not isinstance(contract.get("in_channels"), int)
            or isinstance(contract.get("in_channels"), bool)
            or len(channels) != contract["in_channels"]):
        raise ValueError("Invalid mixed checkpoint channel schema")
    one_hot_groups(contract)
    configuration = contract.get("kernel_model")
    required = {"kernel_sizes", "branch_architecture", "hidden_channels", "depth", "dropout", "mixing_constraint"}
    if not isinstance(configuration, dict) or set(configuration) != required:
        raise ValueError("Invalid mixed kernel checkpoint configuration fields")
    model = build_mixed_kernel_model(contract["in_channels"], **configuration)
    if (not isinstance(contract.get("kernel_size"), int)
            or isinstance(contract.get("kernel_size"), bool)
            or contract["kernel_size"] != model.kernel_size):
        raise ValueError("Mixed checkpoint kernel_size must equal its largest branch size")
    if "normalization_mean" not in saved or "normalization_std" not in saved:
        raise ValueError("A mixed checkpoint must contain frozen normalization")
    if not isinstance(saved["normalization_mean"], torch.Tensor) or not isinstance(saved["normalization_std"], torch.Tensor):
        raise ValueError("Mixed checkpoint normalization must be tensors")
    mean, std = checkpoint_normalization(
        saved, channels, shape_error="Checkpoint normalization shape differs from its channel schema",
        require_floating=True,
    )
    if mean.dtype != std.dtype:
        raise ValueError("Mixed checkpoint normalization tensors must use the same dtype")
    if "model_state_dict" not in saved:
        raise ValueError("A mixed checkpoint must contain its fitted model parameters")
    if not isinstance(saved.get("best_epoch"), int) or isinstance(saved["best_epoch"], bool) or saved["best_epoch"] < 0:
        raise ValueError("Mixed checkpoint best_epoch must be a nonnegative integer")
    model = model.to(dtype=mean.dtype)
    model.load_state_dict(saved["model_state_dict"], strict=True)
    return TrainedBurnModel(model, mean, std, contract, saved["best_epoch"]).to(
        device=device, dtype=mean.dtype,
    ).eval()


# Neural multiscale checkpoint inference
# --------------------------------------
def load_neural_mixed_trained_model(path: str | Path, device="cpu") -> TrainedBurnModel:
    """Load independent branches and scalar neural readout without any fitting."""
    saved = torch.load(resolve_recorded_path(path), map_location="cpu", weights_only=True)
    if not isinstance(saved, dict) or not isinstance(saved.get("contract"), dict):
        raise ValueError("A neural mixed checkpoint must contain its saved contract")
    contract = saved["contract"]
    if (contract.get("format_version") != 1
            or contract.get("architecture") != "NeuralMixedNonnegativeKernel"
            or contract.get("dt_hours") != 1.0 or contract.get("center_rate") != 0.0):
        raise ValueError("Unsupported trained neural mixed probability checkpoint contract")
    channels = contract.get("channels")
    if (not isinstance(channels, (list, tuple)) or not channels
            or any(not isinstance(channel, str) or not channel for channel in channels)
            or len(set(channels)) != len(channels)
            or not isinstance(contract.get("in_channels"), int)
            or isinstance(contract.get("in_channels"), bool)
            or len(channels) != contract["in_channels"]):
        raise ValueError("Invalid neural mixed checkpoint channel schema")
    one_hot_groups(contract)
    configuration = contract.get("kernel_model")
    required = {
        "kernel_sizes", "branch_architecture", "hidden_channels", "depth", "dropout",
        "combiner_hidden_channels", "combiner_dropout", "combiner_input_transform",
    }
    if not isinstance(configuration, dict) or set(configuration) != required:
        raise ValueError("Invalid neural mixed kernel checkpoint configuration fields")
    model = build_neural_mixed_kernel_model(contract["in_channels"], **configuration)
    if (not isinstance(contract.get("kernel_size"), int)
            or isinstance(contract.get("kernel_size"), bool)
            or contract["kernel_size"] != model.kernel_size):
        raise ValueError("Neural mixed checkpoint kernel_size must equal its largest branch size")
    if (not isinstance(saved.get("normalization_mean"), torch.Tensor)
            or not isinstance(saved.get("normalization_std"), torch.Tensor)):
        raise ValueError("A neural mixed checkpoint must contain frozen normalization tensors")
    mean, std = checkpoint_normalization(
        saved, channels, shape_error="Checkpoint normalization shape differs from its channel schema",
        require_floating=True,
    )
    if mean.dtype != std.dtype:
        raise ValueError("Neural mixed checkpoint normalization tensors must use the same dtype")
    if "model_state_dict" not in saved:
        raise ValueError("A neural mixed checkpoint must contain its fitted model parameters")
    if not isinstance(saved.get("best_epoch"), int) or isinstance(saved["best_epoch"], bool) or saved["best_epoch"] < 0:
        raise ValueError("Neural mixed checkpoint best_epoch must be a nonnegative integer")
    model = model.to(dtype=mean.dtype)
    model.load_state_dict(saved["model_state_dict"], strict=True)
    return TrainedBurnModel(model, mean, std, contract, saved["best_epoch"]).to(
        device=device, dtype=mean.dtype,
    ).eval()


def load_trained_model(path: str | Path, device="cpu") -> TrainedBurnModel:
    """Load any maintained tensor checkpoint using its saved architecture.

    Mixed checkpoints use their saved branch sizes and normalization. Existing
    checkpoint architectures retain their original inference implementation.
    This dispatch does not fit preprocessing or read training data.
    """
    saved = torch.load(resolve_recorded_path(path), map_location="cpu", weights_only=True)
    architecture = saved.get("contract", {}).get("architecture") if isinstance(saved, dict) else None
    del saved
    if architecture == "MixedNonnegativeKernel":
        return load_mixed_trained_model(path, device=device)
    if architecture == "NeuralMixedNonnegativeKernel":
        return load_neural_mixed_trained_model(path, device=device)
    if architecture == "BayesianModelAverage":
        return load_bayesian_trained_model(path, device=device)
    return load_single_trained_model(path, device=device)
