"""Compare frozen signed-direct and exponential models on identical targets.

The prior 9x9 sampling design supplies every identity and inverse inclusion
weight. Kernel selection uses clipped common validation predictions, and its
result is saved before the common test cache or predictions are loaded.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from ..evaluate_kernels import centered_slice, common_selection
from ..runtime import choose_device, write_json
from ..cache import load_split
from ..metrics import probability_metrics, weighted_calibration
from .inference import load_trained_model
from .model import center_raw_score


def raw_diagnostics(target, raw, weight):
    raw = raw.astype(np.float64)
    target = target.astype(np.float64)
    total = weight.sum(dtype=np.float64)
    below, above = raw < 0, raw > 1
    return {
        "raw_min": float(raw.min()), "raw_max": float(raw.max()),
        "raw_mean": float(raw.mean()), "raw_weighted_mean": float(np.dot(weight, raw) / total),
        "raw_brier": float(np.dot(weight, (raw - target) ** 2) / total),
        "below_zero_count": int(below.sum()), "above_one_count": int(above.sum()),
        "below_zero_sample_fraction": float(below.mean()),
        "above_one_sample_fraction": float(above.mean()),
        "below_zero_weighted_fraction": float(weight[below].sum() / total),
        "above_one_weighted_fraction": float(weight[above].sum() / total),
    }


@torch.inference_mode()
def frozen_raw_predictions(model, data, indices, batch_size=2048):
    k = model.model.kernel_size
    crop = centered_slice(data.burned.shape[-1], k)
    device = model.mean.device
    raw = np.empty(len(indices), dtype=np.float32)
    counts = np.empty(len(indices), dtype=np.float32)
    public_error = 0.0
    for start in range(0, len(indices), batch_size):
        stop = min(start + batch_size, len(indices))
        selected = indices[start:stop]
        environment = torch.from_numpy(data.environment[selected, :, crop, crop].copy()).to(device)
        burned = torch.from_numpy(data.burned[selected, :, crop, crop].copy()).to(device)
        score = center_raw_score(model.model, burned, (environment - model.mean) / model.std)
        raw[start:stop] = score.cpu().numpy()
        counts[start:stop] = burned.sum(dim=(1, 2, 3)).cpu().numpy()
        if start == 0:
            n = min(32, len(selected))
            public = model(burned[:n], environment[:n], channel_names=model.channel_names)
            radius = k // 2
            assert bool(public.valid[:, 0, radius, radius].all())
            reference = public.raw_score[:, 0, radius, radius]
            public_error = float((reference - score[:n]).abs().max().cpu())
            if not torch.allclose(reference, score[:n], rtol=0, atol=2e-6):
                raise AssertionError(f"Public/raw center mismatch: {public_error}")
            torch.testing.assert_close(public.probability[:, 0, radius, radius],
                                       score[:n].clamp(0, 1), rtol=0, atol=2e-6)
    if not np.isfinite(raw).all() or not (counts > 0).all():
        raise AssertionError("Common anchors require finite raw output and current contact")
    return raw, counts, public_error


def evaluate_runs(run_dir, device="auto"):
    run = Path(run_dir).resolve()
    if (run / "common_metrics.json").exists() or (run / "common_predictions").exists():
        raise FileExistsError("Common evaluation already exists; preserve its records")
    protocol = json.loads((run / "protocol.json").read_text())
    sizes = protocol["kernel_sizes"]
    if sizes != [3, 5, 7, 9]:
        raise ValueError("This comparison requires the four prespecified kernels")
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    device = choose_device(device)
    torch.set_num_threads(protocol["training"]["threads"])
    reference = Path(protocol["common_reference"])
    largest_cache = Path(protocol["native_data"]["9"])
    metadata = json.loads((largest_cache / "metadata.json").read_text())
    if hashlib.sha256((largest_cache / "metadata.json").read_bytes()).hexdigest() != protocol["native_metadata_sha256"]["9"]:
        raise AssertionError("The frozen common source cache metadata changed")
    models = {}
    for k in sizes:
        path = run / f"{k}x{k}" / "fitted" / "checkpoint.pt"
        model = load_trained_model(path, device=device)
        contract = model.contract
        assert model.model.kernel_size == k
        assert contract["kernel_constraint"] == "signed"
        assert contract["training_clipping"] is False
        assert contract["evaluation_clipping"] == [0, 1]
        assert contract["cache_metadata_sha256"] == protocol["native_metadata_sha256"][str(k)]
        for field in ("channels", "source_channels", "categorical_classes", "event_ids", "splits"):
            assert contract[field] == metadata[field], field
        assert contract["eligibility"] == "at_least_one_burned_neighbor"
        models[k] = model
    metrics = {
        "protocol": protocol, "evaluation_device": str(device),
        "largest_kernel": 9, "smallest_kernel": 3,
        "common_reference": str(reference), "splits": {}, "selection": None,
    }
    (run / "common_predictions").mkdir()
    for split in ("validation", "test", "train"):
        data = load_split(largest_cache, split, metadata)
        indices = np.flatnonzero(common_selection(data.burned, 3))
        if not len(indices):
            raise ValueError(f"No common eligible targets in {split}")
        target, weight = data.target[indices], data.weight[indices]
        payload = {
            "y": target, "w": weight, "event_index": data.event_index[indices],
            "time_utc": data.time_utc[indices], "row": data.row[indices], "col": data.col[indices],
        }
        record = {
            "sample_count": len(indices), "positive_sample_count": int(target.sum()),
            "represented_population_weight": float(weight.sum(dtype=np.float64)),
            "contributing_events": len(np.unique(payload["event_index"])),
            "models": {}, "calibration": {}, "clipping": {}, "verification": {},
        }
        with np.load(reference / "common_predictions" / f"{split}.npz", allow_pickle=False) as prior:
            for key, value in payload.items():
                np.testing.assert_array_equal(value, prior[key], err_msg=f"Shared {split} {key} changed")
            for k in sizes:
                raw, counts, error = frozen_raw_predictions(models[k], data, indices)
                clipped = np.clip(raw, 0, 1)
                original = prior[f"p_{k}"].copy()
                np.testing.assert_array_equal(counts, prior[f"neighbor_count_{k}"])
                for name, probability in ((f"direct_{k}", clipped), (f"original_{k}", original)):
                    record["models"][name] = probability_metrics(target, probability, weight, counts)
                    record["calibration"][name] = weighted_calibration(target, probability, weight)
                record["clipping"][f"direct_{k}"] = raw_diagnostics(target, raw, weight)
                record["verification"][str(k)] = {
                    "public_raw_center_max_absolute_error": error,
                    "public_raw_center_absolute_tolerance": 2e-6,
                    "same_original_identities_labels_weights": True,
                    "saved_training_normalization_used_without_fitting": True,
                }
                payload[f"raw_direct_{k}"] = raw
                payload[f"p_direct_{k}"] = clipped
                payload[f"p_original_{k}"] = original
                payload[f"neighbor_count_{k}"] = counts
        metrics["splits"][split] = record
        np.savez_compressed(run / "common_predictions" / f"{split}.npz", **payload)
        if split == "validation":
            selected = min(sizes, key=lambda k: record["models"][f"direct_{k}"]["brier"])
            metrics["selection"] = {
                "kernel_size": selected,
                "criterion": "Minimum common clipped-probability weighted validation Brier; smaller kernel breaks exact ties",
                "validation_brier": record["models"][f"direct_{selected}"]["brier"],
                "test_used_for_selection": False,
            }
            write_json(run / "common_selection.json", metrics["selection"])
        print(json.dumps({
            "split": split, "samples": len(indices),
            "brier": {name: value["brier"] for name, value in record["models"].items()},
        }, indent=2), flush=True)
        del data
    write_json(run / "common_metrics.json", metrics)
    return metrics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    evaluate_runs(args.run_dir, args.device)


if __name__ == "__main__":
    main()
