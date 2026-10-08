"""Verify a saved pooled run, source hashes, and CPU inference without fitting."""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import torch

from .inference import load_trained_model
from .prepare_training import _hash
from .cache import SPLIT_NAMES, cache_kernel_size, fit_normalization, load_split
from .metrics import probability_metrics


def verify_run(run, cpu_atol=1e-6):
    if not math.isfinite(cpu_atol) or cpu_atol <= 0:
        raise ValueError("CPU reproduction tolerance must be finite and positive")
    run = Path(run).resolve()
    metadata_path = run / "prepared" / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metrics = json.loads((run / "fitted" / "metrics.json").read_text())
    model = load_trained_model(run / "fitted" / "checkpoint.pt", device="cpu")
    kernel_size = cache_kernel_size(metadata)
    center = kernel_size // 2
    if model.model.kernel_size != kernel_size:
        raise AssertionError("Prepared patches and checkpoint use different kernel sizes")
    torch.set_num_threads(4)
    if hashlib.sha256(metadata_path.read_bytes()).hexdigest() != model.contract["cache_metadata_sha256"]:
        raise AssertionError("Prepared metadata no longer matches the selected checkpoint")
    if metrics["contract"] != model.contract or model.contract["evaluation_grouping"] != "pooled_countries":
        raise AssertionError("Saved results do not identify one pooled checkpoint")
    if metrics["selection"]["test_used_for_selection"]:
        raise AssertionError("The test partition was used for checkpoint selection")
    root = Path(metadata["data_root"])
    for source in metadata["source_files"]:
        path = root / source["path"]
        if path.stat().st_size != source["bytes"] or _hash(path) != source["sha256"]:
            raise AssertionError(f"Source changed since preparation: {source['path']}")
    checked, event_sets = {}, {}
    for split in SPLIT_NAMES:
        data = load_split(run / "prepared", split, metadata)
        event_sets[split] = set(data.event_index.tolist())
        if split == "train":
            mean, std = fit_normalization(data)
            np.testing.assert_array_equal(mean, model.mean[:, 0, 0].numpy())
            np.testing.assert_array_equal(std, model.std[:, 0, 0].numpy())
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
        checked[split] = dict(samples=len(data), positive_samples=int(data.target.sum()),
                              cpu_wrapper_max_absolute_error=error)
    for first, second in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if event_sets[first] & event_sets[second]:
            raise AssertionError("A fire contributes to multiple partitions")
    with torch.no_grad():
        empty = torch.zeros(1, 1, kernel_size, kernel_size)
        raw = torch.from_numpy(data.environment[:1])
        output = model(empty, raw, channel_names=model.channel_names)
        if output.valid.any() or not torch.isnan(output.probability).all():
            raise AssertionError("A no-burned-neighbor target was admitted")
    code_files = list(Path(__file__).parent.glob("*.py")) + [Path(__file__).parents[1] / "pytorch_loader" / "dataset.py"]
    result = dict(source_hashes_verified=len(metadata["source_files"]),
                  kernel_size=kernel_size,
                  channels=list(model.channel_names),
                  categorical_classes=model.categorical_classes,
                  training_only_normalization_reproduced_exactly=True,
                  disjoint_contributing_fire_sets=True,
                  no_contact_inference_unavailable=True,
                  cpu_wrapper_predictions_reproduced=checked,
                  cpu_wrapper_absolute_tolerance=cpu_atol,
                  selection=metrics["selection"],
                  code_sha256={str(path): _hash(path) for path in sorted(code_files)})
    if cpu_atol == 1e-6:
        result["cpu_wrapper_predictions_reproduced_atol_1e_6"] = checked
    (run / "verification.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--cpu-atol", type=float, default=1e-6,
                        help="Absolute CPU-versus-training-backend probability tolerance, recorded explicitly")
    args = parser.parse_args()
    print(json.dumps(verify_run(args.run_dir, args.cpu_atol), indent=2), flush=True)


if __name__ == "__main__":
    main()
