"""Fit the environmental convolution to cached next-hour cell transitions.

Run from the repository root with ``python -m
wildfire_burned_area_hourly.probability_model.train --data-dir CACHE
--output-dir NEW_RUN``. The cache contains complete, known square source
patches around currently unburned targets. Positive targets are retained;
sampled negative targets have inverse inclusion-probability weights. Reported
population metrics are consequently weighted estimates, not full-grid scores.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from scipy.optimize import minimize_scalar
import torch
from torch import Tensor

from .model import EnvironmentConditionedConvolution, center_probability
from .input_schema import SCHEMA_KEYS, one_hot_groups, validate_one_hot_array

# Compatibility exports: existing imports from train continue to work.
from .cache import (
    SPLIT_NAMES, cache_kernel_size, CachedSplit, load_split, fit_normalization,
)
from .metrics import (
    LOG_LOSS_EPSILON, brier, weighted_rank_metrics, probability_metrics,
    weighted_calibration, scoped_metrics, country_for_event, split_metrics,
)
from .runtime import (
    write_json, choose_device,
)


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
    if not isinstance(metadata.get("event_ids"), list) or len(set(metadata["event_ids"])) != len(metadata["event_ids"]):
        raise ValueError("Cache metadata must contain a unique ordered event_ids list")
    if set(metadata.get("splits", {})) != set(metadata["event_ids"]):
        raise ValueError("Each metadata event must have exactly one split assignment")
    if set(metadata["splits"].values()) != set(SPLIT_NAMES):
        raise ValueError("Cache metadata must assign events to train, validation, and test")
    training = load_split(directory, "train", metadata)
    validation = load_split(directory, "validation", metadata)
    device = choose_device(args.device)
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)
    mean_array, std_array = fit_normalization(training)
    mean = torch.from_numpy(mean_array).to(device).reshape(1, -1, 1, 1)
    std = torch.from_numpy(std_array).to(device).reshape(1, -1, 1, 1)
    total_weight = float(training.weight.sum(dtype=np.float64))
    mean_weight = total_weight / len(training)
    prevalence = float(np.dot(training.weight, training.target) / total_weight)
    if prevalence <= 0 or prevalence >= 1:
        raise ValueError("Training requires positive and negative next-hour targets")
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
        "normalization": f"training-only inverse-sampling-weighted moments across target patches and {kernel_size * kernel_size} positions",
        "boundary": "unknown; complete interior patches only",
        "cache_metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        "event_ids": metadata["event_ids"], "splits": metadata["splits"],
        "eligibility": metadata.get("eligibility", "all_known_currently_unburned_targets"),
        "population_condition": metadata.get("population_condition", "Known currently unburned target with complete context"),
        "evaluation_grouping": "pooled_countries",
    }
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
            weight = torch.from_numpy((training.weight[indices] / mean_weight).astype(np.float32)).to(device)
            optimizer.zero_grad(set_to_none=True)
            probability = center_probability(model, environment, burned)
            loss = (weight * (probability - target).square()).mean() / prevalence
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
        validation_brier = brier(validation.target, validation_predictions, validation.weight)
        improved = validation_brier < best_brier
        if improved:
            best_brier, best_epoch, stale = validation_brier, epoch, 0
            checkpoint = {"contract": contract, "model_state_dict": model.state_dict(),
                          "normalization_mean": torch.from_numpy(mean_array.copy()),
                          "normalization_std": torch.from_numpy(std_array.copy()),
                          "mean_train_sampling_weight": mean_weight,
                          "train_weighted_prevalence": prevalence,
                          "global_rate_baseline": global_baseline,
                          "best_epoch": best_epoch, "validation_brier": best_brier,
                          "configuration": config, "versions": versions}
            torch.save(checkpoint, output / "checkpoint.pt")
        else:
            stale += 1
        record = {"epoch": epoch, "train_brier": training_brier,
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
    metrics: dict[str, Any] = {
        "contract": contract, "versions": versions, "configuration": config,
        "selection": {"criterion": "minimum all-eligible weighted validation Brier",
                      "best_epoch": best_epoch, "epochs_completed": len(history),
                      "early_stopped": len(history) < args.epochs, "validation_brier": best_brier,
                      "test_used_for_selection": False},
        "metric_interpretation": {
            "population": "inverse-inclusion-weighted estimates of eligible currently unburned targets; not exact full-grid metrics",
            "brier_objective": "All targets satisfying the checkpoint's explicit population condition",
            "minibatch_loss": "mean((weight / mean_train_weight) * (p-y)^2) / train_weighted_prevalence",
            "log_loss": "clipped probabilities use floor 1e-7; exact negative log likelihood is infinity for a positive target with p=0",
            "rank_metrics": "weighted threshold grouping for tied scores; null when the necessary label class is absent",
            "normalization_scope": "training partition only",
        },
        "baselines": {"zero": 0.0, "train_marginal_probability": prevalence,
                      "global_neighbor_rate": global_baseline},
        "verification": {"public_forward_center_max_error_initial": center_error_initial,
                         "public_forward_center_max_error_final": center_error_final},
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
    return result


def main() -> None:
    argument_parser = parser()
    args = argument_parser.parse_args()
    for name in ("epochs", "patience", "batch_size", "hidden_channels", "threads"):
        if getattr(args, name) < 1:
            argument_parser.error(f"--{name.replace('_', '-')} must be a positive integer")
    if not math.isfinite(args.learning_rate) or args.learning_rate <= 0:
        argument_parser.error("--learning-rate must be finite and positive")
    if not math.isfinite(args.weight_decay) or args.weight_decay < 0:
        argument_parser.error("--weight-decay must be finite and nonnegative")
    try:
        train(args)
    except (ValueError, TypeError, FileExistsError) as error:
        print(f"Training contract error: {error}", file=sys.stderr, flush=True)
        raise


if __name__ == "__main__":
    main()
