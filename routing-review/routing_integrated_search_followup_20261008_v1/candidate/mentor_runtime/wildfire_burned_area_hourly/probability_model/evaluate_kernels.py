"""Compare saved kernels on a single sampled, equally weighted population.

The largest prepared context supplies anchors and inverse inclusion weights.
Retain only anchors with a burned source in the smallest centered support.
This is a fixed subset of one sampling design, never an intersection of
independently subsampled negatives. Model weights and preprocessing are frozen.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from .inference import load_trained_model
from .model import center_probability
from .cache import load_split
from .metrics import probability_metrics, weighted_calibration
from .runtime import write_json, choose_device


def centered_slice(outer, inner):
    if type(outer) is not int or type(inner) is not int or inner < 3 or inner % 2 != 1 or outer % 2 != 1 or inner > outer:
        raise ValueError("Centered contexts require odd sizes with 3 <= inner <= outer")
    start = (outer - inner) // 2
    return slice(start, start + inner)


def common_selection(burned, smallest_kernel):
    """Membership uses known current sources, never next-hour target outcomes."""
    crop = centered_slice(burned.shape[-1], smallest_kernel)
    return burned[:, :, crop, crop].sum(axis=(1, 2, 3)) > 0


@torch.no_grad()
def frozen_predictions(model, data, indices, batch_size=2048):
    """Use efficient exact centers; verify sampled public wrapper agreement."""
    size = model.model.kernel_size
    crop = centered_slice(data.burned.shape[-1], size)
    device = model.mean.device
    probability = np.empty(len(indices), dtype=np.float32)
    counts = np.empty(len(indices), dtype=np.float32)
    public_max_error = 0.0
    for start in range(0, len(indices), batch_size):
        stop = min(start + batch_size, len(indices))
        selected = indices[start:stop]
        environment = torch.from_numpy(data.environment[selected, :, crop, crop].copy()).to(device)
        burned = torch.from_numpy(data.burned[selected, :, crop, crop].copy()).to(device)
        optimized = center_probability(model.model, (environment - model.mean) / model.std, burned)
        probability[start:stop] = optimized.cpu().numpy()
        counts[start:stop] = burned.sum(dim=(1, 2, 3)).cpu().numpy()
        if start == 0:
            n = min(32, len(selected))
            public = model(burned[:n], environment[:n], channel_names=model.channel_names)
            radius = size // 2
            if not public.valid[:, 0, radius, radius].all():
                raise AssertionError("A selected common target is unavailable in public inference")
            reference = public.probability[:, 0, radius, radius]
            public_max_error = float((reference - optimized[:n]).abs().max())
            if not torch.allclose(reference, optimized[:n], rtol=0, atol=1e-6):
                raise AssertionError("Common inference center differs from the public wrapper")
    if not np.isfinite(probability).all() or not (counts > 0).all():
        raise AssertionError("Common predictions require finite probabilities and source contact")
    return probability, counts, public_max_error


def evaluate_runs(run_dirs, output_dir, device="cpu"):
    output = Path(output_dir).resolve()
    if (output / "common_metrics.json").exists() or (output / "common_predictions").exists():
        raise FileExistsError("Common evaluation outputs already exist; preserve the previous comparison")
    if not (output / "protocol.json").exists():
        raise FileNotFoundError("Save the sweep protocol before evaluating the comparison")
    protocol = json.loads((output / "protocol.json").read_text())
    torch.set_num_threads(4)
    selected_device = choose_device(device)
    runs, models, fitted = {}, {}, {}
    for directory in run_dirs:
        directory = Path(directory).resolve()
        model = load_trained_model(directory / "fitted" / "checkpoint.pt", device=selected_device)
        k = model.model.kernel_size
        if k in models:
            raise ValueError("Each kernel size must occur exactly once")
        runs[k], models[k] = directory, model
        fitted[k] = json.loads((directory / "fitted" / "metrics.json").read_text())
        if fitted[k]["contract"] != model.contract:
            raise AssertionError("Fitted metrics do not match their checkpoint")
    sizes = sorted(models)
    if sizes != protocol["kernel_sizes"]:
        raise ValueError("The compared kernels differ from the saved sweep protocol")
    largest, smallest = sizes[-1], sizes[0]
    metadata_path = runs[largest] / "prepared" / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    reference = models[largest].contract
    for model in models.values():
        for field in ("channels", "categorical_classes", "source_channels", "splits", "dt_hours"):
            if model.contract[field] != reference[field]:
                raise ValueError(f"Kernel input or split contracts differ: {field}")
        if model.contract["eligibility"] != "at_least_one_burned_neighbor":
            raise ValueError("All kernels must preserve the contact eligibility rule")
    if hashlib.sha256(metadata_path.read_bytes()).hexdigest() != reference["cache_metadata_sha256"]:
        raise AssertionError("The largest cache differs from its fitted contract")
    metrics = dict(protocol=protocol, largest_kernel=largest, smallest_kernel=smallest,
                   based_on_run9=str(runs[largest]),
                   common_metadata_sha256=reference["cache_metadata_sha256"],
                   evaluation_device=str(selected_device),
                   model_runs={str(k): str(path) for k, path in runs.items()},
                   splits={}, selection=None)
    (output / "common_predictions").mkdir(parents=True)
    # Validation fixes the kernel choice before the common test cache is read.
    for split in ("validation", "test", "train"):
        data = load_split(runs[largest] / "prepared", split, metadata)
        indices = np.flatnonzero(common_selection(data.burned, smallest))
        if not len(indices):
            raise ValueError(f"No common eligible targets in {split}")
        target, weight = data.target[indices], data.weight[indices]
        saved = dict(y=target, w=weight, event_index=data.event_index[indices],
                     time_utc=data.time_utc[indices], row=data.row[indices], col=data.col[indices])
        record = dict(sample_count=len(indices), positive_sample_count=int(target.sum()),
                      contributing_events=len(np.unique(saved["event_index"])),
                      represented_population_weight=float(weight.sum()),
                      excluded_largest_only_contact_samples=len(data) - len(indices),
                      models={}, calibration={}, baselines={}, verification={})
        for size in sizes:
            model = models[size]
            probability, counts, error = frozen_predictions(model, data, indices)
            record["models"][str(size)] = probability_metrics(target, probability, weight, counts)
            record["calibration"][str(size)] = weighted_calibration(target, probability, weight)
            record["verification"][str(size)] = dict(public_wrapper_center_max_absolute_error=error,
                                                       public_wrapper_absolute_tolerance=1e-6,
                                                       checkpoint_mean_std_used_without_fitting=True)
            saved[f"p_{size}"], saved[f"neighbor_count_{size}"] = probability, counts
            rate = fitted[size]["baselines"]["global_neighbor_rate"]["per_neighbor_rate_per_hour"]
            baseline = -np.expm1(-rate * counts.astype(np.float64))
            record["baselines"][f"uniform_{size}"] = probability_metrics(target, baseline, weight, counts)
            saved[f"uniform_{size}"] = baseline
        record["baselines"]["zero"] = probability_metrics(target, np.zeros(len(target)), weight,
                                                           saved[f"neighbor_count_{smallest}"])
        metrics["splits"][split] = record
        np.savez_compressed(output / "common_predictions" / f"{split}.npz", **saved)
        if split == "validation":
            selected = min(sizes, key=lambda size: record["models"][str(size)]["brier"])
            metrics["selection"] = dict(kernel_size=selected,
                                         criterion="Minimum common-population weighted validation Brier; smaller kernel breaks exact ties",
                                         test_used_for_selection=False,
                                         validation_brier=record["models"][str(selected)]["brier"])
            write_json(output / "common_selection.json", metrics["selection"])
        print(json.dumps({"split": split, "samples": len(indices),
                          "weighted_prevalence": record["models"][str(smallest)]["weighted_prevalence"],
                          "brier": {k: value["brier"] for k, value in record["models"].items()}}, indent=2), flush=True)
        del data
    write_json(output / "common_metrics.json", metrics)
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    evaluate_runs(args.run_dir, args.output_dir, args.device)


if __name__ == "__main__":
    main()
