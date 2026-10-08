"""Fit signed direct-convolution scores to exact next-hour binary targets.

Training minimizes squared error of the unclipped convolution score. Epoch
selection and all probability metrics use that score clipped to [0, 1]. This
experiment imports the preceding cache validation and weighted preprocessing
utilities without modifying the original hazard-model implementation or runs.
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
import torch
from torch import Tensor

from ..input_schema import SCHEMA_KEYS, one_hot_groups
from ..cache import CachedSplit, SPLIT_NAMES, cache_kernel_size, fit_normalization, load_split
from ..metrics import brier, split_metrics, weighted_calibration
from ..runtime import choose_device, write_json
from .model import DirectEnvironmentConditionedConvolution, center_raw_score


FORMAT_VERSION = 1


def fit_uniform_linear(data: CachedSplit) -> dict[str, Any]:
    """Train-only exact weighted least-squares coefficient for score = r*n.

    No clipping enters this closed-form objective. The allowed coefficient is
    signed even though binary labels and nonnegative counts imply r >= 0 here.
    """
    counts = data.neighbor_count.astype(np.float64)
    y = data.target.astype(np.float64)
    numerator = float(np.dot(data.weight, counts * y))
    denominator = float(np.dot(data.weight, counts * counts))
    if denominator <= 0 or not math.isfinite(denominator):
        raise ValueError("Linear initialization requires finite positive burned-neighbor support")
    coefficient = numerator / denominator
    raw = coefficient * counts
    return {
        "per_burned_neighbor_coefficient": coefficient,
        "weighted_numerator": numerator,
        "weighted_denominator": denominator,
        "train_raw_brier": brier(y, raw, data.weight),
        "train_clipped_brier": brier(y, np.clip(raw, 0, 1), data.weight),
        "fitted_partition": "train",
        "objective": "unclipped inverse-inclusion-weighted squared error of coefficient * neighbor_count",
        "formula": "sum(w * neighbor_count * y) / sum(w * neighbor_count**2)",
    }


def training_loss(raw: Tensor, target: Tensor, weight: Tensor,
                  mean_train_weight: float, prevalence: float) -> Tensor:
    """Original global IPW/prevalence normalization, with NO score clipping."""
    return ((weight / mean_train_weight) * (raw - target).square()).mean() / prevalence


def clipped_probability(raw: np.ndarray) -> np.ndarray:
    if not np.isfinite(raw).all():
        raise ValueError("Cannot evaluate a nonfinite direct-convolution score")
    return np.clip(raw, 0.0, 1.0)


def raw_score_diagnostics(data: CachedSplit, raw: np.ndarray) -> dict[str, Any]:
    """Report what clipping removes, including native population weighting."""
    if raw.shape != data.target.shape or not np.isfinite(raw).all():
        raise ValueError("Raw score diagnostics require one finite score per target")
    total = float(data.weight.sum(dtype=np.float64))
    result: dict[str, Any] = {
        "sample_count": len(data),
        "minimum": float(raw.min()), "maximum": float(raw.max()),
        "sample_mean_raw_score": float(raw.astype(np.float64).mean()),
        "weighted_mean_raw_score": float(np.dot(data.weight, raw.astype(np.float64)) / total),
        "raw_brier": brier(data.target, raw, data.weight),
        "clipped_brier": brier(data.target, clipped_probability(raw), data.weight),
        "raw_scores_are_probabilities": False,
        "clip_definition": "min(1, max(0, raw_score)); boundary values 0 and 1 are unchanged",
    }
    for label, selection in (("below_zero", raw < 0), ("above_one", raw > 1),
                             ("clipped", (raw < 0) | (raw > 1))):
        result[f"{label}_sample_count"] = int(selection.sum())
        result[f"{label}_sample_fraction"] = float(selection.mean())
        result[f"{label}_population_weight"] = float(data.weight[selection].sum(dtype=np.float64))
        result[f"{label}_population_fraction"] = result[f"{label}_population_weight"] / total
    return result


@torch.no_grad()
def predict_raw(model: DirectEnvironmentConditionedConvolution, data: CachedSplit,
                mean: Tensor, std: Tensor, device: torch.device, batch_size: int) -> np.ndarray:
    model.eval()
    raw = np.empty(len(data), dtype=np.float32)
    for start in range(0, len(data), batch_size):
        end = min(start + batch_size, len(data))
        environment = (torch.from_numpy(data.environment[start:end]).to(device) - mean) / std
        burned = torch.from_numpy(data.burned[start:end]).to(device)
        raw[start:end] = center_raw_score(model, burned, environment).cpu().numpy()
    if not np.isfinite(raw).all():
        raise RuntimeError("Direct-convolution predictions must be finite")
    return raw


@torch.no_grad()
def verify_center_equivalence(model: DirectEnvironmentConditionedConvolution,
                              mean: Tensor, std: Tensor, data: CachedSplit,
                              device: torch.device) -> dict[str, float]:
    """Independent full-map vs center forward, including float64 reference."""
    n = min(32, len(data))
    environment = (torch.from_numpy(data.environment[:n]).to(device) - mean) / std
    burned = torch.from_numpy(data.burned[:n]).to(device)
    center = model.kernel_size // 2
    efficient = center_raw_score(model, burned, environment)
    public = model(burned, environment, dt_hours=1.0).raw_score[:, 0, center, center]
    error = float((efficient - public).abs().max().cpu())
    if not torch.allclose(efficient, public, rtol=0, atol=1e-6):
        raise AssertionError(f"Signed center/public float32 forward mismatch: {error}")
    reference = DirectEnvironmentConditionedConvolution(
        model.in_channels, model.kernel_size, model.kernel_network[0].out_channels,
        kernel_constraint="signed",
    ).cpu().double().eval()
    reference.load_state_dict({name: value.detach().cpu() for name, value in model.state_dict().items()})
    cpu_environment, cpu_burned = environment.cpu().double(), burned.cpu().double()
    cpu_efficient = center_raw_score(reference, cpu_burned, cpu_environment)
    cpu_public = reference(cpu_burned, cpu_environment).raw_score[:, 0, center, center]
    reference_error = float((cpu_efficient - cpu_public).abs().max())
    if not torch.allclose(cpu_efficient, cpu_public, rtol=0, atol=1e-12):
        raise AssertionError(f"Signed center/public float64 reference mismatch: {reference_error}")
    return {"float32_max_absolute_error": error, "float32_absolute_tolerance": 1e-6,
            "cpu_float64_max_absolute_error": reference_error,
            "cpu_float64_absolute_tolerance": 1e-12}


def _read_metadata(directory: Path) -> tuple[dict[str, Any], Path]:
    metadata_path = directory / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    channels = metadata.get("channels")
    if (not isinstance(channels, list) or not channels
            or not all(isinstance(c, str) for c in channels)
            or len(set(channels)) != len(channels)):
        raise ValueError("Cache must contain a nonempty unique ordered channel list")
    cache_kernel_size(metadata)
    one_hot_groups(metadata)
    if metadata.get("dt_hours") != 1.0:
        raise ValueError("The direct model requires exact one-hour cache labels")
    events = metadata.get("event_ids")
    if not isinstance(events, list) or len(set(events)) != len(events):
        raise ValueError("Cache event_ids must be a unique ordered list")
    if set(metadata.get("splits", {})) != set(events):
        raise ValueError("Each fire must have exactly one split assignment")
    if set(metadata["splits"].values()) != set(SPLIT_NAMES):
        raise ValueError("Cache must have train, validation, and test fire partitions")
    if metadata.get("eligibility") != "at_least_one_burned_neighbor":
        raise ValueError("This experiment requires the original contact-only prepared cache")
    return metadata, metadata_path


def train(args: argparse.Namespace) -> dict[str, Any]:
    start_time = time.perf_counter()
    directory, output = args.data_dir.resolve(), args.output_dir.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Output must be new or empty; existing experimental results are preserved")
    metadata, metadata_path = _read_metadata(directory)
    channels, kernel_size = metadata["channels"], cache_kernel_size(metadata)
    training = load_split(directory, "train", metadata)
    validation = load_split(directory, "validation", metadata)
    requested_device = args.device
    if requested_device == "auto":
        requested_device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    device = choose_device(requested_device)
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
    if not 0 < prevalence < 1:
        raise ValueError("Training requires positive and negative next-hour targets")
    uniform_baseline = fit_uniform_linear(training)
    model = DirectEnvironmentConditionedConvolution(
        len(channels), kernel_size, args.hidden_channels, kernel_constraint="signed",
    ).to(device)
    with torch.no_grad():
        model.kernel_network[2].weight.zero_()
        model.kernel_network[2].bias.fill_(uniform_baseline["per_burned_neighbor_coefficient"])
    initial_equivalence = verify_center_equivalence(model, mean, std, training, device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    output.mkdir(parents=True, exist_ok=True)
    config = {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()}
    contract = {
        "format_version": FORMAT_VERSION, "architecture": "DirectEnvironmentConditionedConvolution",
        "output_link": "identity", "kernel_constraint": "signed",
        "training_clipping": False, "evaluation_clipping": [0.0, 1.0],
        "in_channels": len(channels), "channels": channels,
        "kernel_size": kernel_size, "hidden_channels": args.hidden_channels,
        "dt_hours": 1.0, "center_coefficient": 0.0,
        "target": "currently unburned cell is burned at the exact next-hour snapshot",
        "input_context": f"current known {kernel_size}x{kernel_size} reconstructed burned map and environmental neighborhood",
        "normalization": f"training-only inverse-sampling-weighted moments across target patches and {kernel_size * kernel_size} positions",
        "boundary": "unknown; complete interior patches only",
        "cache_metadata_sha256": hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
        "event_ids": metadata["event_ids"], "splits": metadata["splits"],
        "eligibility": metadata["eligibility"],
        "population_condition": metadata.get("population_condition", "Known currently unburned target with complete context and burned-neighbor contact"),
        "evaluation_grouping": "pooled_countries",
    }
    contract.update({key: metadata[key] for key in SCHEMA_KEYS if key in metadata})
    versions = {
        "python": platform.python_version(), "numpy": str(np.__version__), "scipy": str(scipy.__version__),
        "torch": str(torch.__version__), "platform": platform.platform(), "device": str(device),
        "mps_available": bool(torch.backends.mps.is_available()), "mps_built": bool(torch.backends.mps.is_built()),
        "cuda_available": bool(torch.cuda.is_available()), "model_dtype": "float32",
        "moment_accumulation_dtype": "float64",
        "training_forward": "unclipped signed center convolution without unfold; full public forward checked independently",
    }
    initialization = {
        "uniform_linear_baseline": uniform_baseline,
        "last_layer_weight": "zero", "last_layer_bias": uniform_baseline["per_burned_neighbor_coefficient"],
        "kernel_constraint": "signed", "fitted_partition": "train",
    }
    write_json(output / "configuration.json", {
        "arguments": config, "contract": contract, "versions": versions,
        "initialization": initialization, "started_utc": datetime.now(timezone.utc).isoformat(),
    })
    history: list[dict[str, Any]] = []
    best_brier, best_epoch, stale = math.inf, 0, 0
    for epoch in range(1, args.epochs + 1):
        epoch_start = time.perf_counter()
        model.train()
        order = rng.permutation(len(training))
        for start in range(0, len(training), args.batch_size):
            indices = order[start:start + args.batch_size]
            environment = (torch.from_numpy(training.environment[indices]).to(device) - mean) / std
            burned = torch.from_numpy(training.burned[indices]).to(device)
            target = torch.from_numpy(training.target[indices].astype(np.float32, copy=False)).to(device)
            # Preserve the preceding trainer's division-before-float32-cast
            # order as well as its global mean-weight normalization.
            weight = torch.from_numpy((training.weight[indices] / mean_weight).astype(np.float32)).to(device)
            optimizer.zero_grad(set_to_none=True)
            raw = center_raw_score(model, burned, environment)
            loss = training_loss(raw, target, weight, 1.0, prevalence)
            if not bool(torch.isfinite(loss)):
                raise RuntimeError(f"Nonfinite unclipped training loss at epoch {epoch}")
            loss.backward()
            if any(parameter.grad is not None and not bool(torch.isfinite(parameter.grad).all())
                   for parameter in model.parameters()):
                raise RuntimeError(f"Nonfinite training gradient at epoch {epoch}")
            optimizer.step()
        training_raw = predict_raw(model, training, mean, std, device, args.batch_size)
        validation_raw = predict_raw(model, validation, mean, std, device, args.batch_size)
        train_raw_brier = brier(training.target, training_raw, training.weight)
        train_clipped_brier = brier(training.target, clipped_probability(training_raw), training.weight)
        validation_brier = brier(validation.target, clipped_probability(validation_raw), validation.weight)
        improved = validation_brier < best_brier
        if improved:
            best_brier, best_epoch, stale = validation_brier, epoch, 0
            torch.save({
                "contract": contract, "model_state_dict": model.state_dict(),
                "normalization_mean": torch.from_numpy(mean_array.copy()),
                "normalization_std": torch.from_numpy(std_array.copy()),
                "mean_train_sampling_weight": mean_weight, "train_weighted_prevalence": prevalence,
                "uniform_linear_baseline": uniform_baseline, "initialization": initialization,
                "best_epoch": best_epoch, "validation_brier": best_brier,
                "configuration": config, "versions": versions,
            }, output / "checkpoint.pt")
        else:
            stale += 1
        record = {
            "epoch": epoch, "train_raw_brier": train_raw_brier,
            "train_clipped_brier": train_clipped_brier, "validation_clipped_brier": validation_brier,
            "validation_raw_brier": brier(validation.target, validation_raw, validation.weight),
            "selected": improved, "seconds": time.perf_counter() - epoch_start,
        }
        history.append(record)
        write_json(output / "history.json", history)
        print(f"epoch={epoch:02d} train_raw_brier={train_raw_brier:.9g} "
              f"validation_clipped_brier={validation_brier:.9g} best_epoch={best_epoch} "
              f"seconds={record['seconds']:.2f}", flush=True)
        if stale >= args.patience:
            break

    # Test data and labels are first read after validation selects the epoch.
    selected = torch.load(output / "checkpoint.pt", map_location=device, weights_only=True)
    model.load_state_dict(selected["model_state_dict"], strict=True)
    mean = selected["normalization_mean"].to(device).reshape(1, -1, 1, 1)
    std = selected["normalization_std"].to(device).reshape(1, -1, 1, 1)
    final_equivalence = verify_center_equivalence(model, mean, std, training, device)
    testing = load_split(directory, "test", metadata)
    partitions = {"train": training, "validation": validation, "test": testing}
    metrics: dict[str, Any] = {
        "contract": contract, "versions": versions, "configuration": config, "initialization": initialization,
        "selection": {
            "criterion": "minimum all-eligible inverse-inclusion-weighted validation Brier after clipping to [0,1]",
            "best_epoch": best_epoch, "epochs_completed": len(history), "early_stopped": len(history) < args.epochs,
            "validation_brier": best_brier, "test_used_for_selection": False,
        },
        "metric_interpretation": {
            "population": "inverse-inclusion-weighted estimates of eligible currently unburned targets; not exact full-grid metrics",
            "training_objective": "unclipped signed direct-convolution squared error against binary next-hour labels",
            "minibatch_loss": "mean((weight / mean_train_weight) * (q_raw-y)^2) / train_weighted_prevalence",
            "probability_metrics": "all reported probability metrics, including training diagnostics, use clip(q_raw,0,1)",
            "raw_score_metrics": "raw Brier is the unscaled training objective; signed raw scores need not lie in [0,1]",
            "log_loss": "diagnostic log loss uses floor 1e-7; exact NLL is infinity for any incorrect probability zero/one",
            "normalization_scope": "training partition only", "evaluation_grouping": "pooled_countries",
        },
        "baselines": {"zero": 0.0, "train_marginal_probability": prevalence,
                      "uniform_linear_neighbor": uniform_baseline},
        "verification": {"public_forward_center_initial": initial_equivalence,
                         "public_forward_center_final": final_equivalence},
        "splits": {},
    }
    independently_loaded = torch.load(output / "checkpoint.pt", map_location=device, weights_only=True)
    reloaded = DirectEnvironmentConditionedConvolution(
        len(channels), kernel_size, args.hidden_channels, kernel_constraint="signed",
    ).to(device)
    reloaded.load_state_dict(independently_loaded["model_state_dict"], strict=True)
    reload_mean = independently_loaded["normalization_mean"].to(device).reshape(1, -1, 1, 1)
    reload_std = independently_loaded["normalization_std"].to(device).reshape(1, -1, 1, 1)
    reload_errors: dict[str, float] = {}
    for name, data in partitions.items():
        raw = predict_raw(model, data, mean, std, device, args.batch_size)
        repeated = predict_raw(reloaded, data, reload_mean, reload_std, device, args.batch_size)
        reload_errors[name] = float(np.max(np.abs(raw - repeated)))
        if not np.allclose(raw, repeated, rtol=0, atol=1e-7):
            raise AssertionError(f"Independent checkpoint reload differs in {name}: {reload_errors[name]}")
        p = clipped_probability(raw)
        uniform_raw = uniform_baseline["per_burned_neighbor_coefficient"] * data.neighbor_count.astype(np.float64)
        predictions = {
            "learned_environment_kernel": p, "zero": np.zeros(len(data), dtype=np.float32),
            "train_marginal": np.full(len(data), prevalence, dtype=np.float64),
            "uniform_linear_neighbor": clipped_probability(uniform_raw),
        }
        metrics["splits"][name] = split_metrics(data, predictions, metadata)
        metrics["splits"][name]["calibration"] = weighted_calibration(data.target, p, data.weight)
        metrics["splits"][name]["raw_score_diagnostics"] = raw_score_diagnostics(data, raw)
        np.savez_compressed(
            output / f"{name}_predictions.npz", y=data.target, p_raw=raw, p=p, w=data.weight,
            event_index=data.event_index, time_utc=data.time_utc, row=data.row, col=data.col,
            neighbor_count=data.neighbor_count, baseline_zero=predictions["zero"],
            baseline_train_marginal=predictions["train_marginal"], baseline_uniform_raw=uniform_raw,
            baseline_uniform_linear_neighbor=predictions["uniform_linear_neighbor"],
        )
    metrics["verification"].update({
        "checkpoint_weights_only_reload_succeeded": True,
        "checkpoint_raw_scores_reproduced_atol_1e_7": True,
        "checkpoint_reload_max_absolute_error_by_split": reload_errors,
    })
    metrics["elapsed_seconds"] = time.perf_counter() - start_time
    metrics["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(output / "metrics.json", metrics)
    print(json.dumps({
        "output_dir": str(output), "best_epoch": best_epoch, "epochs_completed": len(history),
        "elapsed_seconds": metrics["elapsed_seconds"], "checkpoint_reload_verified": True,
        "clipped_probability_metrics": {
            name: record["models"]["learned_environment_kernel"]["all_eligible"]
            for name, record in metrics["splits"].items()
        },
        "raw_score_diagnostics": {name: record["raw_score_diagnostics"] for name, record in metrics["splits"].items()},
    }, indent=2, allow_nan=False), flush=True)
    return metrics


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--data-dir", type=Path, required=True)
    result.add_argument("--output-dir", type=Path, required=True)
    result.add_argument("--epochs", type=int, default=30)
    result.add_argument("--patience", type=int, default=6)
    result.add_argument("--batch-size", type=int, default=2048)
    result.add_argument("--hidden-channels", type=int, default=16)
    result.add_argument("--learning-rate", type=float, default=1e-3)
    result.add_argument("--weight-decay", type=float, default=1e-4)
    result.add_argument("--seed", type=int, default=7)
    result.add_argument("--threads", type=int, default=4)
    result.add_argument("--device", default="auto", choices=("auto", "cpu", "mps", "cuda"))
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
