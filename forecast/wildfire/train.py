"""Train operations for the wildfire workspace."""
from __future__ import annotations

from .paths import resolve_recorded_path, resolve_source_root



# Learning rate schedules
# Explicit per-optimizer-step learning rates for resumable full-batch fits.
# 
# Steps are one-based. Every candidate fixes its horizon before training starts;
# the first 512 steps and a continued finalist use the same 4,096-step schedule.
# No scheduler depends on validation or on the requested continuation endpoint.


import math
from numbers import Integral

SCHEDULES = ("constant", "warmup_cosine", "warmup_cosine_restarts")


def validate_scheduler(scheduler):
    """Validate and return a copied, JSON-serializable scheduler configuration."""
    expected = {"name", "horizon", "warmup_epochs", "minimum_lr_factor", "restart_period"}
    if set(scheduler) != expected:
        raise ValueError(f"Scheduler requires exactly {sorted(expected)}")
    result = dict(scheduler)
    if result["name"] not in SCHEDULES:
        raise ValueError(f"Unknown learning-rate schedule: {result['name']}")
    for key in ("horizon", "warmup_epochs", "restart_period"):
        if isinstance(result[key], bool) or not isinstance(result[key], Integral):
            raise ValueError(f"{key} must be an integer")
        result[key] = int(result[key])
    if result["horizon"] < 1:
        raise ValueError("The fixed scheduling horizon must be positive")
    if not 0 <= result["warmup_epochs"] < result["horizon"]:
        raise ValueError("Warmup epochs must satisfy 0 <= warmup < horizon")
    if result["restart_period"] < 2:
        raise ValueError("Restart period must contain at least two optimizer steps")
    factor = float(result["minimum_lr_factor"])
    if not math.isfinite(factor) or not 0. <= factor <= 1.:
        raise ValueError("Minimum learning-rate factor must be finite and in [0, 1]")
    result["minimum_lr_factor"] = factor
    return result


def learning_rate_at_step(peak_learning_rate, optimizer_step, scheduler):
    """Return the rate assigned immediately before a one-based optimizer step.

    Constant schedules always use the peak. Nonconstant schedules linearly
    warm up from peak/W at step 1 to the peak at step W. With W > 0, ordinary
    cosine progress is (step-W)/(H-W), reaching the floor at the fixed horizon
    H. With W = 0, progress is (step-1)/(H-1), so step 1 uses the peak.

    Restart schedules use P-step cosine cycles after warmup. Within each cycle,
    progress is 0/(P-1), ..., (P-1)/(P-1); the next cycle restarts at the peak.
    Rates are never recomputed from the endpoint of a partial training call.
    """
    config = validate_scheduler(scheduler)
    peak = float(peak_learning_rate)
    if not math.isfinite(peak) or peak <= 0.:
        raise ValueError("Peak learning rate must be finite and positive")
    if isinstance(optimizer_step, bool) or not isinstance(optimizer_step, Integral):
        raise ValueError("Optimizer step must be an integer")
    step = int(optimizer_step)
    if not 1 <= step <= config["horizon"]:
        raise ValueError("Optimizer step must lie inside the fixed scheduling horizon")
    if config["name"] == "constant":
        return peak
    warmup = config["warmup_epochs"]
    if warmup and step <= warmup:
        return peak * step / warmup
    floor = peak * config["minimum_lr_factor"]
    if config["name"] == "warmup_cosine_restarts":
        position = (step - warmup - 1) % config["restart_period"]
        progress = position / (config["restart_period"] - 1)
    elif warmup:
        progress = (step - warmup) / (config["horizon"] - warmup)
    else:
        progress = (step - 1) / (config["horizon"] - 1) if config["horizon"] > 1 else 0.
    return floor + (peak - floor) * .5 * (1. + math.cos(math.pi * progress))


# Cuda equivalence
# Strict CUDA verification without changing a resumed training trajectory.
# 
# The frozen search compares a flattened linear path with public convolutions.
# PyTorch 2.5 permits TF32 separately for those operations. Use full float32
# arithmetic for that comparison, then restore the caller's training settings.
# The existing float32 tolerances and CPU float64 reference remain unchanged.


from contextlib import contextmanager
from functools import wraps
import os

import torch


@contextmanager
def full_precision_cuda_verification():
    """Temporarily disable TF32; restore all changed settings on every exit."""
    if os.environ.get("TORCH_ALLOW_TF32_CUBLAS_OVERRIDE") == "1":
        raise RuntimeError(
            "Strict CUDA verification requires TORCH_ALLOW_TF32_CUBLAS_OVERRIDE "
            "to be unset or 0; its value 1 forces reduced-precision matrix multiplication."
        )
    previous = dict(
        cudnn_allow_tf32=torch.backends.cudnn.allow_tf32,
        matmul_allow_tf32=torch.backends.cuda.matmul.allow_tf32,
        float32_matmul_precision=torch.get_float32_matmul_precision(),
    )
    try:
        torch.backends.cudnn.allow_tf32 = False
        torch.set_float32_matmul_precision("highest")
        torch.backends.cuda.matmul.allow_tf32 = False
        yield previous
    finally:
        torch.backends.cuda.matmul.allow_tf32 = previous["matmul_allow_tf32"]
        # In PyTorch 2.5, assigning allow_tf32=True changes "medium" to
        # "high". Restore the named policy last to retain it exactly.
        torch.set_float32_matmul_precision(previous["float32_matmul_precision"])
        torch.backends.cudnn.allow_tf32 = previous["cudnn_allow_tf32"]


@contextmanager
def strict_cuda_equivalence(search):
    """Scope the portable runner's verification override to one dispatch.

    No frozen source, model parameter, optimizer, RNG or tolerance is edited.
    CPU/MPS checks delegate directly to the original implementation.
    """
    original = search.verify_equivalence

    @wraps(original)
    def verify(model, data, mean, std, family, device):
        if torch.device(device).type != "cuda":
            return original(model, data, mean, std, family, device)
        with full_precision_cuda_verification() as previous:
            try:
                result = original(model, data, mean, std, family, device)
            except AssertionError as error:
                raise AssertionError(
                    f"{error} (family={family}, device={device}; CUDA verification "
                    "used highest float32 matmul precision with both TF32 flags disabled)"
                ) from error
        return {
            **result,
            "cuda_verification_precision": {
                "policy": "Full float32 for equivalence only; original tolerances retained",
                "cudnn_allow_tf32": False,
                "matmul_allow_tf32": False,
                "float32_matmul_precision": "highest",
                "training_settings_restored": previous,
            },
        }

    search.verify_equivalence = verify
    try:
        yield
    finally:
        search.verify_equivalence = original


# Train
# Fit the environmental convolution to cached next-hour cell transitions.
# 
# Run from the repository root with ``python -m
# wildfire train --data-dir CACHE
# --output-dir NEW_RUN``. The cache contains complete, known square source
# patches around currently unburned targets. Positive targets are retained;
# sampled negative targets have inverse inclusion-probability weights. Reported
# population metrics are consequently weighted estimates, not full-grid scores.


import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from scipy.optimize import minimize_scalar
from torch import Tensor

from wildfire.models import EnvironmentConditionedConvolution
from wildfire.models import center_probability
from wildfire.schema import SCHEMA_KEYS
from wildfire.schema import one_hot_groups
from wildfire.schema import validate_one_hot_array
from wildfire.metrics import add_categorical_balance_arguments
from wildfire.metrics import categorical_balance_settings
from wildfire.metrics import fit_categorical_balance
from wildfire.metrics import categorical_group_metrics

# Compatibility exports: existing imports from train continue to work.
from wildfire.cache import SPLIT_NAMES
from wildfire.cache import cache_kernel_size
from wildfire.cache import CachedSplit
from wildfire.cache import load_split
from wildfire.cache import fit_normalization
from wildfire.cache import validate_split_metadata
from wildfire.cache import validate_partition_disjointness
from wildfire.metrics import LOG_LOSS_EPSILON
from wildfire.metrics import brier
from wildfire.metrics import weighted_rank_metrics
from wildfire.metrics import probability_metrics
from wildfire.metrics import weighted_calibration
from wildfire.metrics import scoped_metrics
from wildfire.metrics import country_for_event
from wildfire.metrics import split_metrics
from wildfire.utils import write_json
from wildfire.utils import choose_device


FORMAT_VERSION = 1


@torch.no_grad()
def verify_center_equivalence(model: EnvironmentConditionedConvolution, mean: Tensor, std: Tensor,
                              data: CachedSplit, device: torch.device) -> float:
    n = min(32, len(data))
    environment = torch.from_numpy(data.environment[:n]).to(device)
    environment = (environment - mean) / std
    burned = torch.from_numpy(data.burned[:n]).to(device)
    efficient = center_probability(model, environment, burned)
    center = model.kernel_size // 2
    public = model(burned, environment, dt_hours=1.0).probability[:, 0, center, center]
    error = float((efficient - public).abs().max().cpu())
    # Cropped and padded convolutions can accumulate float32 products in
    # different orders on either backend. A float64 reference checks the
    # mathematical computation separately from this rounding tolerance.
    tolerance = 1e-6
    if not torch.allclose(efficient, public, rtol=0, atol=tolerance):
        raise AssertionError(f"Center/public forward mismatch: {error}")
    reference = EnvironmentConditionedConvolution(
        model.in_channels, model.kernel_size, model.kernel_network[0].out_channels,
    ).cpu().double().eval()
    reference.load_state_dict({name: value.detach().cpu() for name, value in model.state_dict().items()})
    cpu_environment, cpu_burned = environment.cpu().double(), burned.cpu().double()
    cpu_efficient = center_probability(reference, cpu_environment, cpu_burned)
    cpu_public = reference(cpu_burned, cpu_environment, dt_hours=1.0).probability[:, 0, center, center]
    if not torch.allclose(cpu_efficient, cpu_public, rtol=0, atol=1e-12):
        raise AssertionError("The float64 reference center/public forward differs")
    return error


def fit_global_rate(data: CachedSplit) -> dict[str, Any]:
    counts = data.neighbor_count.astype(np.int64)
    positions = math.prod(data.burned.shape[2:])
    weighted_counts = np.bincount(counts, weights=data.weight, minlength=positions)
    weighted_positives = np.bincount(counts, weights=data.weight * data.target, minlength=positions)
    total = float(weighted_counts.sum())
    offsets = np.arange(positions, dtype=np.float64)

    def objective(rate: float) -> float:
        p = -np.expm1(-rate * offsets)
        return float((weighted_counts * p * p - 2 * weighted_positives * p + weighted_positives).sum() / total)

    # A broad patch can have only high neighbor counts. Starting the bounded
    # optimizer at rates near 10 then makes every probability exactly one in
    # float64 and hides the small-rate optimum. Scale the numerical bracket
    # by the smallest occupied positive count, and retain the original rate
    # endpoints as candidates. The existing 3x3 fitting path is unchanged.
    search_upper = 20.0
    if positions > 9:
        occupied_positive = np.flatnonzero(weighted_counts[1:] > 0) + 1
        if occupied_positive.size:
            search_upper /= int(occupied_positive[0])
    result = minimize_scalar(objective, bounds=(0.0, search_upper), method="bounded",
                             options={"xatol": 1e-10})
    if not result.success:
        raise RuntimeError(f"Global-rate baseline fitting failed: {result.message}")
    # Include the endpoints because a constrained optimum can be exactly zero.
    rate = min((0.0, float(result.x), search_upper, 20.0), key=objective)
    fitted = {"per_neighbor_rate_per_hour": rate, "train_brier": objective(rate),
              "optimization_lower_bound": 0.0, "optimization_upper_bound": 20.0}
    if positions > 9:
        fitted["optimization_search_upper_bound"] = search_upper
        fitted["optimization_search_bracket_reason"] = (
            "Scale by the smallest occupied positive neighbor count to avoid a numerically saturated initial search; "
            "original admissible rate endpoints 0 and 20 remain candidates"
        )
    return fitted


@torch.no_grad()
def predict(model: EnvironmentConditionedConvolution, data: CachedSplit, mean: Tensor,
            std: Tensor, device: torch.device, batch_size: int) -> np.ndarray:
    model.eval()
    result = np.empty(len(data), dtype=np.float32)
    for start in range(0, len(data), batch_size):
        end = min(start + batch_size, len(data))
        environment = torch.from_numpy(data.environment[start:end]).to(device)
        environment = (environment - mean) / std
        burned = torch.from_numpy(data.burned[start:end]).to(device)
        result[start:end] = center_probability(model, environment, burned).cpu().numpy()
    if not np.isfinite(result).all() or (result < 0).any() or (result > 1).any():
        raise RuntimeError("Predictions must be finite probabilities in [0,1]")
    return result


def train(args: argparse.Namespace) -> dict[str, Any]:
    start_time = time.perf_counter()
    balance_settings = categorical_balance_settings(args)
    directory, output = args.data_dir.resolve(), args.output_dir.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("The output directory must be new or empty; existing results are never overwritten")
    metadata_path = directory / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    channels = metadata.get("channels")
    if not isinstance(channels, list) or not channels or not all(isinstance(c, str) for c in channels):
        raise ValueError("Cache metadata must contain a nonempty ordered list of channel names")
    if len(set(channels)) != len(channels):
        raise ValueError("The cache must use unique channels")
    kernel_size = cache_kernel_size(metadata)
    one_hot_groups(metadata)
    if metadata.get("dt_hours") != 1.0:
        raise ValueError("The cache must explicitly declare dt_hours=1.0")
    validate_split_metadata(metadata, require_all_partitions=True)
    training = load_split(directory, "train", metadata)
    validation = load_split(directory, "validation", metadata)
    validate_partition_disjointness({"train": training, "validation": validation}, metadata)
    device = choose_device(args.device)
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    mean_array, std_array = fit_normalization(training, metadata=metadata)
    optimization_weights, balance_audit = fit_categorical_balance(training, metadata, **balance_settings)
    total_optimization_weight = float(optimization_weights.sum(dtype=np.float64))
    mean_optimization_weight = total_optimization_weight / len(training)
    mean = torch.from_numpy(mean_array).to(device).reshape(1, -1, 1, 1)
    std = torch.from_numpy(std_array).to(device).reshape(1, -1, 1, 1)
    total_weight = float(training.weight.sum(dtype=np.float64))
    mean_weight = total_weight / len(training)
    prevalence = float(np.dot(training.weight, training.target) / total_weight)
    if prevalence <= 0 or prevalence >= 1:
        raise ValueError("Training requires positive and negative next-hour targets")
    optimization_prevalence = float(np.dot(optimization_weights, training.target) / total_optimization_weight)
    if not 0 < optimization_prevalence < 1:
        raise ValueError("Optimization requires positive and negative weighted next-hour targets")
    global_baseline = fit_global_rate(training)
    model = EnvironmentConditionedConvolution(len(channels), kernel_size=kernel_size,
                                              hidden_channels=args.hidden_channels).to(device)
    initial_rate = max(global_baseline["per_neighbor_rate_per_hour"], 1e-8)
    inverse_softplus = math.log(math.expm1(initial_rate))
    with torch.no_grad():
        model.kernel_network[2].weight.zero_()
        model.kernel_network[2].bias.fill_(inverse_softplus)
    center_error_initial = verify_center_equivalence(model, mean, std, training, device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    output.mkdir(parents=True, exist_ok=True)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    contract = {
        "format_version": FORMAT_VERSION,
        "architecture": "EnvironmentConditionedConvolution",
        "in_channels": len(channels), "channels": channels,
        "kernel_size": kernel_size, "hidden_channels": args.hidden_channels,
        "dt_hours": 1.0, "center_rate": 0.0,
        "target": "currently unburned cell is burned at the exact next-hour snapshot",
        "input_context": f"current known {kernel_size}x{kernel_size} reconstructed burned map and environmental neighborhood",
        "normalization": f"continuous channels: training-only inverse-sampling-weighted moments across target patches and {kernel_size * kernel_size} positions; categorical one-hot indicators: raw 0/1 (mean zero, scale one)",
        "categorical_balance": balance_audit,
        "boundary": "unknown; complete interior patches only",
        "cache_metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        "event_ids": metadata["event_ids"], "splits": metadata["splits"],
        "split_unit": "cell_hour" if metadata.get("split_unit") == "cell_hour" else "whole_fire",
        "eligibility": metadata.get("eligibility", "all_known_currently_unburned_targets"),
        "population_condition": metadata.get("population_condition", "Known currently unburned target with complete context"),
        "evaluation_grouping": "pooled_countries",
    }
    if metadata.get("split_unit") == "cell_hour":
        contract["original_splits"] = metadata["original_splits"]
        contract["partition_identity"] = ["event_id", "time_utc", "row", "col"]
    contract.update({key: metadata[key] for key in SCHEMA_KEYS if key in metadata})
    versions = {"python": platform.python_version(), "numpy": str(np.__version__),
                "scipy": str(scipy.__version__), "torch": str(torch.__version__),
                "platform": platform.platform(), "device": str(device),
                "mps_available": bool(torch.backends.mps.is_available()),
                "mps_built": bool(torch.backends.mps.is_built()),
                "cuda_available": bool(torch.cuda.is_available()),
                "model_dtype": "float32", "moment_accumulation_dtype": "float64",
                "training_forward": "center convolution without unfold; public-forward equivalence checked separately"}
    write_json(output / "configuration.json", {"arguments": config, "contract": contract,
                                                "versions": versions, "started_utc": datetime.now(timezone.utc).isoformat()})
    write_json(output / "categorical_balance.json", balance_audit)
    history = []
    best_brier = math.inf
    best_epoch = 0
    stale = 0
    for epoch in range(1, args.epochs + 1):
        epoch_start = time.perf_counter()
        model.train()
        order = rng.permutation(len(training))
        for start in range(0, len(training), args.batch_size):
            indices = order[start:start + args.batch_size]
            environment = torch.from_numpy(training.environment[indices]).to(device)
            environment = (environment - mean) / std
            burned = torch.from_numpy(training.burned[indices]).to(device)
            target = torch.from_numpy(training.target[indices].astype(np.float32, copy=False)).to(device)
            weight = torch.from_numpy((optimization_weights[indices] / mean_optimization_weight).astype(np.float32)).to(device)
            optimizer.zero_grad(set_to_none=True)
            probability = center_probability(model, environment, burned)
            loss = (weight * (probability - target).square()).mean() / optimization_prevalence
            if not bool(torch.isfinite(loss)):
                raise RuntimeError(f"Nonfinite training loss at epoch {epoch}")
            loss.backward()
            if any(parameter.grad is not None and not bool(torch.isfinite(parameter.grad).all())
                   for parameter in model.parameters()):
                raise RuntimeError(f"Nonfinite training gradient at epoch {epoch}")
            optimizer.step()
        training_predictions = predict(model, training, mean, std, device, args.batch_size)
        validation_predictions = predict(model, validation, mean, std, device, args.batch_size)
        training_brier = brier(training.target, training_predictions, training.weight)
        training_optimization_brier = brier(training.target, training_predictions, optimization_weights)
        validation_brier = brier(validation.target, validation_predictions, validation.weight)
        improved = validation_brier < best_brier
        if improved:
            best_brier, best_epoch, stale = validation_brier, epoch, 0
            checkpoint = {"contract": contract, "model_state_dict": model.state_dict(),
                          "normalization_mean": torch.from_numpy(mean_array.copy()),
                          "normalization_std": torch.from_numpy(std_array.copy()),
                          "mean_train_sampling_weight": mean_weight,
                          "train_weighted_prevalence": prevalence,
                          "mean_train_optimization_weight": mean_optimization_weight,
                          "train_optimization_weighted_prevalence": optimization_prevalence,
                          "global_rate_baseline": global_baseline,
                          "best_epoch": best_epoch, "validation_brier": best_brier,
                          "configuration": config, "versions": versions}
            torch.save(checkpoint, output / "checkpoint.pt")
        else:
            stale += 1
        record = {"epoch": epoch, "train_brier": training_brier,
                  "train_categorical_balanced_brier": training_optimization_brier,
                  "validation_brier": validation_brier, "selected": improved,
                  "seconds": time.perf_counter() - epoch_start}
        history.append(record)
        write_json(output / "history.json", history)
        print(f"epoch={epoch:02d} train_brier={training_brier:.9g} validation_brier={validation_brier:.9g} "
              f"best_epoch={best_epoch} seconds={record['seconds']:.2f}", flush=True)
        if stale >= args.patience:
            break

    # Restore the validation-selected checkpoint before reading test samples.
    selected = torch.load(output / "checkpoint.pt", map_location=device, weights_only=True)
    model.load_state_dict(selected["model_state_dict"], strict=True)
    mean = selected["normalization_mean"].to(device).reshape(1, -1, 1, 1)
    std = selected["normalization_std"].to(device).reshape(1, -1, 1, 1)
    center_error_final = verify_center_equivalence(model, mean, std, training, device)
    testing = load_split(directory, "test", metadata)
    partitions = {"train": training, "validation": validation, "test": testing}
    partition_verification = validate_partition_disjointness(partitions, metadata)
    metrics: dict[str, Any] = {
        "contract": contract, "versions": versions, "configuration": config,
        "selection": {"criterion": "minimum all-eligible weighted validation Brier",
                      "best_epoch": best_epoch, "epochs_completed": len(history),
                      "early_stopped": len(history) < args.epochs, "validation_brier": best_brier,
                      "test_used_for_selection": False},
        "metric_interpretation": {
            "population": "inverse-inclusion-weighted estimates of eligible currently unburned targets; not exact full-grid metrics",
            "brier_objective": "All targets satisfying the checkpoint's explicit population condition",
            "minibatch_loss": "mean((optimization_weight / mean_train_optimization_weight) * (p-y)^2) / train_optimization_weighted_prevalence",
            "optimization_weight": "original inverse inclusion weight multiplied by training-only categorical patch-presence factor; weighted mean factor one",
            "evaluation_weight": "original inverse inclusion weight; categorical factors do not alter reported population metrics or checkpoint selection",
            "log_loss": "clipped probabilities use floor 1e-7; exact negative log likelihood is infinity for a positive target with p=0",
            "rank_metrics": "weighted threshold grouping for tied scores; null when the necessary label class is absent",
            "normalization_scope": "training partition only",
        },
        "baselines": {"zero": 0.0, "train_marginal_probability": prevalence,
                      "global_neighbor_rate": global_baseline},
        "verification": {"public_forward_center_max_error_initial": center_error_initial,
                         "public_forward_center_max_error_final": center_error_final,
                         **partition_verification},
        "splits": {},
    }
    metrics["verification"].update(public_forward_center_absolute_tolerance=1e-6,
                                    cpu_float64_reference_center_absolute_tolerance=1e-12,
                                    cpu_float64_reference_center_checked=True)
    reloaded = EnvironmentConditionedConvolution(len(channels), kernel_size=kernel_size,
                                                 hidden_channels=args.hidden_channels).to(device)
    independently_loaded = torch.load(output / "checkpoint.pt", map_location=device, weights_only=True)
    if independently_loaded["contract"] != contract:
        raise AssertionError("The reloaded checkpoint contract changed")
    reloaded.load_state_dict(independently_loaded["model_state_dict"], strict=True)
    reload_mean = independently_loaded["normalization_mean"].to(device).reshape(1, -1, 1, 1)
    reload_std = independently_loaded["normalization_std"].to(device).reshape(1, -1, 1, 1)
    reload_errors = {}
    for name, data in partitions.items():
        probability = predict(model, data, mean, std, device, args.batch_size)
        verification = predict(reloaded, data, reload_mean, reload_std, device, args.batch_size)
        error = float(np.max(np.abs(probability - verification)))
        if not np.allclose(probability, verification, rtol=0, atol=1e-7):
            raise AssertionError(f"Checkpoint probability reload mismatch in {name}: {error}")
        reload_errors[name] = error
        predictions = {"learned_environment_kernel": probability,
                       "zero": np.zeros(len(data), dtype=np.float32),
                       "train_marginal": np.full(len(data), prevalence, dtype=np.float64),
                       "global_neighbor_rate": -np.expm1(-global_baseline["per_neighbor_rate_per_hour"] * data.neighbor_count.astype(np.float64))}
        metrics["splits"][name] = split_metrics(data, predictions, metadata)
        metrics["splits"][name]["calibration"] = weighted_calibration(data.target, probability, data.weight)
        metrics["splits"][name]["categorical_groups"] = categorical_group_metrics(data, probability, metadata)
        np.savez_compressed(output / f"{name}_predictions.npz", y=data.target, p=probability,
                            w=data.weight, event_index=data.event_index, time_utc=data.time_utc,
                            row=data.row, col=data.col, neighbor_count=data.neighbor_count,
                            baseline_zero=predictions["zero"], baseline_train_marginal=predictions["train_marginal"],
                            baseline_global_neighbor_rate=predictions["global_neighbor_rate"])
    metrics["verification"].update({"checkpoint_weights_only_reload_succeeded": True,
                                    "checkpoint_probabilities_reproduced_atol_1e_7": True,
                                    "checkpoint_reload_max_absolute_error_by_split": reload_errors})
    metrics["elapsed_seconds"] = time.perf_counter() - start_time
    metrics["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(output / "metrics.json", metrics)
    summary = {"output_dir": str(output), "best_epoch": best_epoch,
               "epochs_completed": len(history), "elapsed_seconds": metrics["elapsed_seconds"],
               "all_eligible": {name: result["models"]["learned_environment_kernel"]["all_eligible"]
                                for name, result in metrics["splits"].items()},
               "checkpoint_reload_verified": True}
    print(json.dumps(summary, indent=2, allow_nan=False), flush=True)
    return metrics


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--data-dir", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--epochs", type=int, default=30)
    result.add_argument("--patience", type=int, default=6)
    result.add_argument("--batch-size", type=int, default=1024)
    result.add_argument("--hidden-channels", type=int, default=16)
    result.add_argument("--learning-rate", type=float, default=1e-3)
    result.add_argument("--weight-decay", type=float, default=1e-4)
    result.add_argument("--seed", type=int, default=7)
    result.add_argument("--threads", type=int, default=4)
    result.add_argument("--device", default="cpu")
    add_categorical_balance_arguments(result)
    _add_perimeter_arguments(result)
    return result


# Additive track 1B options. With the default --objective next_hour they are
# removed from the namespace before train() runs, so the original code path,
# its saved configuration and its outputs are unchanged.
PERIMETER_OPTIONS = ("objective", "structured_prior", "structured_frame", "d4_augmentation",
                     "residence_hours", "spotting_radius")


def _add_perimeter_arguments(result: argparse.ArgumentParser) -> None:
    group = result.add_argument_group("interval-censored perimeter training (track 1B, opt-in)")
    group.add_argument("--objective", choices=("next_hour", "perimeter_survival"), default="next_hour",
                       help="next_hour (default) runs the released cache trainer; perimeter_survival fits a "
                            "StructuredKernelModel through the mean field on pickled PerimeterSample lists "
                            "DATA_DIR/train_samples.pkl and DATA_DIR/validation_samples.pkl")
    group.add_argument("--structured-prior", choices=("free", "ellipse"), default="free")
    group.add_argument("--structured-frame", choices=("none", "d4", "wind"), default="none")
    group.add_argument("--d4-augmentation", action="store_true")
    group.add_argument("--residence-hours", type=float, default=None)
    group.add_argument("--spotting-radius", type=int, default=0)


def _strip_perimeter_options(args: argparse.Namespace) -> argparse.Namespace:
    values = {key: value for key, value in vars(args).items() if key not in PERIMETER_OPTIONS}
    return argparse.Namespace(**values)


def train_perimeter(args: argparse.Namespace) -> dict[str, Any]:
    """Fit a structured kernel on perimeter intervals through the mean field."""
    import pickle
    from wildfire.models import StructuredKernelModel
    from wildfire.survival import fit_mean_field, fit_normalization
    directory, output = args.data_dir.resolve(), args.output_dir.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("The output directory must be new or empty; existing results are never overwritten")
    training = pickle.loads((directory / "train_samples.pkl").read_bytes())
    validation = pickle.loads((directory / "validation_samples.pkl").read_bytes())
    names = json.loads((directory / "channels.json").read_text())
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    mean, std = fit_normalization(training, names)
    model = StructuredKernelModel(len(names), 9, args.hidden_channels, 0.0, channel_names=names, mean=mean,
                                  std=std, prior=args.structured_prior, frame=args.structured_frame,
                                  residence_hours=args.residence_hours, spotting_radius=args.spotting_radius)
    model.initialize_rate(0.05)
    result = fit_mean_field(model, training, validation, epochs=args.epochs, learning_rate=args.learning_rate,
                            weight_decay=args.weight_decay, seed=args.seed, patience=args.patience,
                            d4=args.d4_augmentation)
    output.mkdir(parents=True, exist_ok=True)
    torch.save({"configuration": model.configuration(), "state_dict": model.state_dict(),
                "arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}},
               output / "checkpoint.pt")
    write_json(output / "history.json", result)
    return result


def train_main() -> None:
    argument_parser = parser()
    args = argument_parser.parse_args()
    for name in ("epochs", "patience", "batch_size", "hidden_channels", "threads"):
        if getattr(args, name) < 1:
            argument_parser.error(f"--{name.replace('_', '-')} must be a positive integer")
    if not math.isfinite(args.learning_rate) or args.learning_rate <= 0:
        argument_parser.error("--learning-rate must be finite and positive")
    if not math.isfinite(args.weight_decay) or args.weight_decay < 0:
        argument_parser.error("--weight-decay must be finite and nonnegative")
    if args.objective == "perimeter_survival":
        train_perimeter(args)
        return
    args = _strip_perimeter_options(args)
    try:
        train(args)
    except (ValueError, TypeError, FileExistsError) as error:
        print(f"Training contract error: {error}", file=sys.stderr, flush=True)
        raise




# Verify training
# Verify a saved pooled run, source hashes, and CPU inference without fitting.



from wildfire.inference import load_single_trained_model
from wildfire.prepare import _prepare_hash
from wildfire.cache import cell_hour_identities


@torch.inference_mode()
def _mask_checks(model, environment):
    """Check structural zeros separately from unavailable source context."""
    raw = torch.from_numpy(environment[:1].copy())
    kernel_size = model.model.kernel_size
    center = kernel_size // 2
    empty = torch.zeros(1, 1, kernel_size, kernel_size)
    output = model(empty, raw, channel_names=model.channel_names)
    expected_valid = torch.zeros_like(output.valid)
    expected_valid[0, 0, center, center] = True
    if (not torch.equal(output.valid, expected_valid)
            or not torch.equal(output.rate_valid, expected_valid)
            or output.probability[0, 0, center, center] != 0
            or output.rate[0, 0, center, center] != 0
            or not torch.isnan(output.probability[~expected_valid]).all()
            or not torch.isnan(output.rate[~expected_valid]).all()):
        raise AssertionError("Complete no-contact context must give a valid zero probability and rate; unknown boundaries remain unavailable")
    output = model(empty, raw, channel_names=model.channel_names, boundary="zero")
    if (not output.valid.all() or not output.rate_valid.all()
            or not output.probability.eq(0).all() or not output.rate.eq(0).all()):
        raise AssertionError("Explicit zero boundaries rejected a complete all-unburned source map")
    missing = empty.clone()
    missing[0, 0, 0, 0] = torch.nan
    output = model(missing, raw, channel_names=model.channel_names)
    if (output.valid[0, 0, center, center] or output.rate_valid[0, 0, center, center]
            or not torch.isnan(output.probability[0, 0, center, center])
            or not torch.isnan(output.rate[0, 0, center, center])):
        raise AssertionError("An unknown source was interpreted as a known unburned neighbor")
    return {"no_contact_structural_zero_valid": True, "zero_rate_valid": True,
            "unknown_boundary_unavailable": True, "explicit_zero_boundary_structural_zero_valid": True,
            "missing_burned_state_unavailable": True}


def verify_run(run, cpu_atol=1e-6):
    if not math.isfinite(cpu_atol) or cpu_atol <= 0:
        raise ValueError("CPU reproduction tolerance must be finite and positive")
    run = Path(run).resolve()
    metadata_path = run / "prepared" / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    validate_split_metadata(metadata, require_all_partitions=True)
    metrics = json.loads((run / "fitted" / "metrics.json").read_text())
    checkpoint = torch.load(run / "fitted" / "checkpoint.pt", map_location="cpu", weights_only=True)
    model = load_single_trained_model(run / "fitted" / "checkpoint.pt", device="cpu")
    kernel_size = cache_kernel_size(metadata)
    center = kernel_size // 2
    if model.model.kernel_size != kernel_size:
        raise AssertionError("Prepared patches and checkpoint use different kernel sizes")
    torch.set_num_threads(4)
    if hashlib.sha256(metadata_path.read_bytes()).hexdigest() != model.contract["cache_metadata_sha256"]:
        raise AssertionError("Prepared metadata no longer matches the selected checkpoint")
    if metrics["contract"] != model.contract or model.contract["evaluation_grouping"] != "pooled_countries":
        raise AssertionError("Saved results do not identify one pooled checkpoint")
    if metadata.get("split_unit") == "cell_hour" and any(
            model.contract.get(key) != metadata[key]
            for key in ("split_unit", "splits", "original_splits")):
        raise AssertionError("The checkpoint does not preserve its cell-hour split contract")
    if metrics["selection"]["test_used_for_selection"]:
        raise AssertionError("The test partition was used for checkpoint selection")
    root = resolve_source_root(metadata)
    for source in metadata["source_files"]:
        path = root / source["path"]
        if path.stat().st_size != source["bytes"] or _prepare_hash(path) != source["sha256"]:
            raise AssertionError(f"Source changed since preparation: {source['path']}")
    checked, identities = {}, {}
    for split in SPLIT_NAMES:
        data = load_split(run / "prepared", split, metadata)
        identities[split] = cell_hour_identities(data)
        if split == "train":
            balance = model.contract.get("categorical_balance")
            mean, std = fit_normalization(data, metadata=metadata if balance is not None else None)
            np.testing.assert_array_equal(mean, model.mean[:, 0, 0].numpy())
            np.testing.assert_array_equal(std, model.std[:, 0, 0].numpy())
            if balance is not None:
                optimization_weights, reproduced_balance = fit_categorical_balance(data, metadata, **balance["settings"])
                if reproduced_balance != balance:
                    raise AssertionError("The checkpoint categorical training weights do not match training inputs")
                stored_balance = json.loads((run / "fitted" / "categorical_balance.json").read_text())
                if stored_balance != balance:
                    raise AssertionError("The saved categorical balance audit differs from the checkpoint")
                expected_statistics = {
                    "mean_train_optimization_weight": float(optimization_weights.sum(dtype=np.float64) / len(data)),
                    "train_optimization_weighted_prevalence": float(np.dot(optimization_weights, data.target) / optimization_weights.sum(dtype=np.float64)),
                }
                for key, expected in expected_statistics.items():
                    actual = checkpoint.get(key)
                    if (isinstance(actual, bool) or not isinstance(actual, (int, float))
                            or not math.isfinite(actual)
                            or not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=0)):
                        raise AssertionError(f"Checkpoint optimization statistic {key} does not match training inputs")
        with np.load(run / "fitted" / f"{split}_predictions.npz", allow_pickle=False) as archive:
            saved = {name: archive[name] for name in archive.files}
        for cache_key, output_key in (("target", "y"), ("weight", "w"), ("event_index", "event_index"),
                                      ("time_utc", "time_utc"), ("row", "row"), ("col", "col")):
            np.testing.assert_array_equal(getattr(data, cache_key), saved[output_key])
        reproduced = np.empty(len(data), dtype=np.float32)
        with torch.no_grad():
            for start in range(0, len(data), 2048):
                end = min(start + 2048, len(data))
                output = model(torch.from_numpy(data.burned[start:end]),
                               torch.from_numpy(data.environment[start:end]),
                               channel_names=model.channel_names)
                if not output.valid[:, 0, center, center].all():
                    raise AssertionError("A complete eligible cache patch is unavailable during inference")
                reproduced[start:end] = output.probability[:, 0, center, center].numpy()
        error = float(np.max(np.abs(reproduced - saved["p"])))
        np.testing.assert_allclose(reproduced, saved["p"], rtol=0, atol=cpu_atol)
        actual = probability_metrics(data.target, saved["p"], data.weight, data.neighbor_count)
        recorded = metrics["splits"][split]["models"]["learned_environment_kernel"]["all_eligible"]
        if actual != recorded:
            raise AssertionError(f"Metrics do not match saved predictions in {split}")
        if "categorical_groups" in metrics["splits"][split]:
            if categorical_group_metrics(data, saved["p"], metadata) != metrics["splits"][split]["categorical_groups"]:
                raise AssertionError(f"Categorical population metrics do not match predictions in {split}")
        checked[split] = dict(samples=len(data), positive_samples=int(data.target.sum()),
                              cpu_wrapper_max_absolute_error=error)
    partition_verification = validate_partition_disjointness(identities, metadata)
    inference_masks = _mask_checks(model, data.environment)
    code_files = list(Path(__file__).parent.glob("*.py"))
    result = dict(source_hashes_verified=len(metadata["source_files"]),
                  kernel_size=kernel_size,
                  channels=list(model.channel_names),
                  categorical_classes=model.categorical_classes,
                  training_only_normalization_reproduced_exactly=True,
                  categorical_balance_reproduced_exactly=model.contract.get("categorical_balance") is not None,
                  optimization_statistics_reproduced=model.contract.get("categorical_balance") is not None,
                  **partition_verification,
                  **inference_masks,
                  cpu_wrapper_predictions_reproduced=checked,
                  cpu_wrapper_absolute_tolerance=cpu_atol,
                  selection=metrics["selection"],
                  code_sha256={str(path): _prepare_hash(path) for path in sorted(code_files)})
    if cpu_atol == 1e-6:
        result["cpu_wrapper_predictions_reproduced_atol_1e_6"] = checked
    (run / "verification.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def verify_training_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--cpu-atol", type=float, default=1e-6,
                        help="Absolute CPU-versus-training-backend probability tolerance, recorded explicitly")
    args = parser.parse_args()
    print(json.dumps(verify_run(args.run_dir, args.cpu_atol), indent=2), flush=True)


def fit_bayesian_model(checkpoints, calibration, metadata, output_directory, *,
                       prior_weights=None, population_weighted=False,
                       likelihood_power=1.0, device="cpu", batch_size=512):
    """Calibrate Bayes weights over frozen independently fitted kernel checkpoints.

    ``calibration`` is one largest-context CachedSplit, declared as validation
    in ``metadata``. All models use identical rows, labels and (optionally)
    population weights. No component is trained or renormalized here. Default
    evidence is an ordinary product of Bernoulli probabilities conditional on
    fitted parameters. Population weighting normalizes inverse inclusion
    weights to mean one and produces a generalized, powered likelihood.

    The caller must keep these rows out of component parameter fitting. Reusing
    validation previously used for epoch/model selection is calibration reuse,
    not independent evidence. This operation never reads a test partition.
    """
    from copy import deepcopy
    from .api import WildfireModel, _device
    from .cache import CachedSplit, cell_hour_identities, validate_partition_disjointness, cache_kernel_size
    from .cohort import common_indices, cohort_payload, centered_slice, kernel_neighbor_count
    from .inference import single_model_from_checkpoint, bayesian_checkpoint_payload
    from .models import BayesianBurnModel, bayesian_model_weights, center_probability
    from .schema import SCHEMA_KEYS, validate_one_hot_array, probability_target_id

    if not isinstance(calibration, CachedSplit):
        raise TypeError("calibration must be a CachedSplit")
    if type(batch_size) is not int or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")
    if type(population_weighted) is not bool:
        raise TypeError("population_weighted must be boolean")
    output = Path(output_directory).expanduser().resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Bayesian output directory must be new or empty")
    paths = [resolve_recorded_path(path).resolve() for path in checkpoints]
    if len(paths) < 2 or len(set(paths)) != len(paths):
        raise ValueError("Supply at least two distinct independently trained checkpoints")
    payloads = [torch.load(path, map_location="cpu", weights_only=True) for path in paths]
    selected_device = _device(device)
    components = [single_model_from_checkpoint(saved, device=selected_device) for saved in payloads]
    contract = deepcopy(components[0].contract)
    sizes = [component.model.kernel_size for component in components]
    contract.update(architecture="BayesianModelAverage", kernel_size=max(sizes), kernel_sizes=sizes,
                    normalization="Each independent component retains its own frozen training normalization",
                    output_link="posterior_weighted_component_probabilities",
                    rate_semantics="Equivalent interval rate; at zero horizon the posterior mean initial rate")
    contract.pop("kernel_model", None)
    contract.pop("categorical_balance", None)
    contract.pop("cache_metadata_sha256", None)
    contract.update(input_context="Current burned state and each independent kernel's environmental neighborhood",
                    population_condition="Complete shared context with smallest-support current burned contact for calibration")
    # Validate components before reading outcome labels or writing artifacts.
    BayesianBurnModel(components, np.full(len(components), -math.log(len(components))), contract)
    if metadata.get("channels") != list(components[0].channel_names):
        raise ValueError("Calibration channel schema differs from component checkpoints")
    for key in SCHEMA_KEYS:
        if metadata.get(key) != components[0].contract.get(key):
            raise ValueError(f"Calibration schema differs from component {key}")
    if metadata.get("dt_hours", 1.0) != 1.0:
        raise ValueError("Bayesian calibration requires the same one-hour endpoint")
    if (metadata.get("target") is not None
            and probability_target_id(metadata) != probability_target_id(contract)):
        raise ValueError("Calibration target endpoint differs from component checkpoints")
    outer = cache_kernel_size(metadata)
    if calibration.burned.shape != (len(calibration), 1, outer, outer):
        raise ValueError("Calibration burned patches differ from their declared kernel_size")
    partition_audit = validate_partition_disjointness({"validation": calibration}, metadata)
    if (calibration.environment.ndim != 4
            or calibration.environment.shape[:2] != (len(calibration), len(contract["channels"]))
            or calibration.environment.shape[-2:] != calibration.burned.shape[-2:]):
        raise ValueError("Calibration environmental and burned patches must align")
    validate_one_hot_array(calibration.environment, metadata)
    indices = common_indices(calibration, sorted(set(sizes)))
    if not len(indices):
        raise ValueError("The shared calibration cohort is empty")
    selected = cohort_payload(calibration, indices)
    target, weight = selected["y"], selected["w"]
    # Training on these outcomes, or using any member's designated test fires,
    # would invalidate the intended calibration/test separation.
    for component in components:
        saved_contract = component.contract
        member_splits = saved_contract.get("splits", {})
        for index in np.unique(calibration.event_index[indices]):
            event = metadata["event_ids"][int(index)]
            memberships = member_splits.get(event, [])
            memberships = [memberships] if isinstance(memberships, str) else memberships
            if "test" in memberships:
                raise ValueError("Calibration cannot use a component's designated test fires")
            if "train" in memberships and "validation" not in memberships:
                raise ValueError("Calibration cannot use a component's training-only fires")
    if (weight.shape != target.shape or not np.isfinite(weight).all() or (weight <= 0).any()):
        raise ValueError("Calibration population weights must be finite and positive")
    probability = np.empty((len(indices), len(components)), dtype=np.float64)
    with torch.inference_mode():
        for column, component in enumerate(components):
            size = sizes[column]
            crop = centered_slice(calibration.burned.shape[-1], size)
            reference = next(component.parameters())
            for start in range(0, len(indices), batch_size):
                stop = min(start + batch_size, len(indices))
                rows = indices[start:stop]
                environment = torch.as_tensor(calibration.environment[rows, :, crop, crop].copy(),
                                              device=reference.device, dtype=reference.dtype)
                burned = torch.as_tensor(calibration.burned[rows, :, crop, crop].copy(),
                                         device=reference.device, dtype=reference.dtype)
                component._validate_one_hot(environment, None)
                values = center_probability(component.model, (environment-component.mean)/component.std, burned)
                probability[start:stop, column] = values.cpu().numpy()
    evidence = bayesian_model_weights(probability, target, prior_weights=prior_weights,
                                      sample_weight=weight if population_weighted else None,
                                      likelihood_power=likelihood_power)
    log_weights = [-math.inf if value is None else value for value in evidence["log_posterior_weights"]]
    predictor = BayesianBurnModel(components, log_weights, contract)
    posterior = np.asarray(evidence["posterior_weights"])
    mixture_probability = probability @ posterior
    source_records = [dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                           kernel_size=size, best_epoch=component.best_epoch,
                           cache_metadata_sha256=component.contract.get("cache_metadata_sha256"))
                      for path, size, component in zip(paths, sizes, components, strict=True)]
    evidence.update(
        components=source_records, calibration_split="validation", test_used_for_weights=False,
        cohort="Complete largest-context rows with burned contact in the smallest support",
        row_identities_sha256=hashlib.sha256(cell_hour_identities(calibration)[indices].tobytes()).hexdigest(),
        population_weights_used_for_evidence=population_weighted,
        component_parameters_integrated_out=False,
        likelihood_assumption="Conditionally independent Bernoulli cell-hours given each frozen fitted predictor",
        calibration_independence="Caller supplied; prior validation selection reuse is not independent evidence",
        calibration_metadata_sha256=hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest(),
        interpretation="Conditional plug-in model averaging; posterior weights are not physical validation",
    )
    contract["bayesian"] = evidence
    predictor.contract = deepcopy(contract)
    report = dict(contract=contract, evidence=evidence,
                  verification=dict(component_parameters_frozen=True,
                                    component_normalizations_preserved=True,
                                    common_cohort_identity_checked=True,
                                    **partition_audit),
                  calibration_metrics=probability_metrics(
                      target, mixture_probability, weight,
                      kernel_neighbor_count(calibration.burned, min(sizes))[indices]))
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = bayesian_checkpoint_payload(predictor, dict(components=payloads, calibration=evidence))
    destination = output / "checkpoint.pt"
    torch.save(checkpoint, destination)
    np.savez_compressed(output / "calibration_predictions.npz", **selected,
                        component_probability=probability, mixture_probability=mixture_probability,
                        kernel_sizes=np.asarray(sizes), posterior_weights=posterior)
    write_json(output / "metrics.json", report)
    fitted = WildfireModel.from_checkpoint(destination, device=selected_device)
    fitted.training_metrics = report
    return fitted


def bayesian_main():
    """Calibrate a frozen kernel average using a prepared validation partition."""
    parser = argparse.ArgumentParser(description="Bayesian averaging of independent fitted kernel checkpoints")
    parser.add_argument("--checkpoints", type=Path, nargs="+", required=True)
    parser.add_argument("--cache", type=Path, required=True,
                        help="Largest-context prepared cache; only validation outcomes are used")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prior-weights", type=float, nargs="+")
    parser.add_argument("--population-weighted", action="store_true",
                        help="Use mean-one inverse inclusion weights (generalized Bayes)")
    parser.add_argument("--likelihood-power", type=float, default=1.0)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda", "auto"), default="cpu")
    parser.add_argument("--batch-size", type=int, default=512)
    args = parser.parse_args()
    directory = resolve_recorded_path(args.cache).resolve()
    metadata_path = directory / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    calibration = load_split(directory, "validation", metadata)
    # Check identity separation without loading training features or outcomes.
    from .cache import CachedSplit, cell_hour_identities, validate_partition_disjointness, IDENTITY_FIELDS
    with np.load(directory / "train.npz", allow_pickle=False) as archive:
        identities = {key: archive[key] for key in IDENTITY_FIELDS}
    identity_data = CachedSplit(environment=None, burned=None, target=np.empty(len(identities["row"])),
                               weight=None, **identities)
    validate_partition_disjointness({"train": cell_hour_identities(identity_data),
                                    "validation": calibration}, metadata)
    digest = hashlib.sha256(metadata_path.read_bytes()).hexdigest()
    fitted = fit_bayesian_model(args.checkpoints, calibration, metadata, args.output,
                               prior_weights=args.prior_weights, population_weighted=args.population_weighted,
                               likelihood_power=args.likelihood_power, device=args.device,
                               batch_size=args.batch_size)
    fitted.training_metrics["verification"].update(
        calibration_cache_train_validation_identities_disjoint=True,
        calibration_cache_metadata_file_sha256=digest,
        metadata_file_matches_component_cache=[
            item["cache_metadata_sha256"] == digest if item["cache_metadata_sha256"] is not None else None
            for item in fitted.contract["bayesian"]["components"]],
    )
    write_json(Path(args.output) / "metrics.json", fitted.training_metrics)
    print(json.dumps(dict(checkpoint=str(fitted.checkpoint_path),
                          kernel_sizes=fitted.contract["kernel_sizes"],
                          posterior_weights=fitted.contract["bayesian"]["posterior_weights"]), indent=2))


