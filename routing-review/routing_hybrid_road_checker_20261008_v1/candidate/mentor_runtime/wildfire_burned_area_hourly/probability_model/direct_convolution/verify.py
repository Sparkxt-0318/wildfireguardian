"""Independently replay saved direct scores and audit unchanged experiment inputs.

No fitting or artifact replacement occurs. CPU center scores are recomputed
with explicit Conv/SiLU/Conv/signed-dot operations, rather than the trainer's
center-scoring helper. Any cross-backend tolerance is specified and recorded.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from ..cache import SPLIT_NAMES, fit_normalization, load_split
from ..metrics import brier, probability_metrics, weighted_calibration
from .inference import load_trained_model


IDENTITY_FIELDS = {"y": "target", "w": "weight", "event_index": "event_index",
                   "time_utc": "time_utc", "row": "row", "col": "col"}


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while block := source.read(1 << 20):
            digest.update(block)
    return digest.hexdigest()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _predictions(path):
    with np.load(path, allow_pickle=False) as archive:
        return {key: archive[key] for key in archive.files}


def _equal(actual, saved, label):
    """Check nested recorded statistics without changing their definitions."""
    if isinstance(actual, dict):
        for key, value in actual.items():
            if key not in saved:
                raise AssertionError(f"Missing recorded field: {label}/{key}")
            _equal(value, saved[key], f"{label}/{key}")
    elif isinstance(actual, list):
        if len(actual) != len(saved):
            raise AssertionError(f"Recorded sequence length differs: {label}")
        for index, (first, second) in enumerate(zip(actual, saved, strict=True)):
            _equal(first, second, f"{label}/{index}")
    elif isinstance(actual, (float, np.floating)):
        if not math.isclose(float(actual), float(saved), rel_tol=0, abs_tol=1e-12):
            raise AssertionError(f"Recorded numerical metric differs: {label}")
    elif actual != saved:
        raise AssertionError(f"Recorded metric differs: {label}")


@torch.inference_mode()
def _independent_raw(fitted, environment, burned):
    """Explicit identity-link center calculation, independent of model helper."""
    features = (torch.from_numpy(np.ascontiguousarray(environment)) - fitted.mean) / fitted.std
    current = torch.from_numpy(np.ascontiguousarray(burned)).to(features.dtype)
    first, last = fitted.model.kernel_network[0], fitted.model.kernel_network[2]
    hidden = F.silu(F.conv2d(features, first.weight, first.bias, padding=0))
    coefficients = F.conv2d(hidden, last.weight, last.bias, padding=0)
    coefficients = coefficients * fitted.model.off_center
    raw = (coefficients.flatten(1) * current.flatten(1)).sum(dim=1)
    center = fitted.model.kernel_size // 2
    if not current[:, 0, center, center].eq(0).all():
        raise AssertionError("A currently burned cell entered the at-risk cache")
    if not torch.isfinite(raw).all():
        raise AssertionError("Independent CPU replay produced a nonfinite raw score")
    return raw.numpy()


def _replay(fitted, environment, burned, batch_size):
    raw = np.empty(len(burned), dtype=np.float32)
    for start in range(0, len(raw), batch_size):
        stop = min(start + batch_size, len(raw))
        raw[start:stop] = _independent_raw(fitted, environment[start:stop], burned[start:stop])
    return raw


def _difference(actual, saved, atol):
    if actual.shape != saved.shape or not np.isfinite(saved).all():
        raise AssertionError("Saved raw score shape or finiteness is invalid")
    difference = np.abs(actual.astype(np.float64) - saved.astype(np.float64))
    return {"max_absolute_error": float(difference.max()),
            "absolute_tolerance": atol, "count_above_tolerance": int((difference > atol).sum()),
            "count_above_1e_6": int((difference > 1e-6).sum()),
            "count_above_2e_6": int((difference > 2e-6).sum()),
            "passed": bool((difference <= atol).all())}


@torch.inference_mode()
def _public_sample(fitted, environment, burned, raw_reference, raw_atol, probability_atol):
    count = min(32, len(burned))
    b = torch.from_numpy(np.ascontiguousarray(burned[:count]))
    e = torch.from_numpy(np.ascontiguousarray(environment[:count]))
    output = fitted(b, e, channel_names=fitted.channel_names)
    c = fitted.model.kernel_size // 2
    if not output.valid[:, 0, c, c].all():
        raise AssertionError("A complete contact-eligible patch became unavailable")
    raw = output.raw_score[:, 0, c, c].numpy()
    clipped = output.probability[:, 0, c, c].numpy()
    np.testing.assert_array_equal(clipped, np.clip(raw, 0, 1))
    check = _difference(raw, raw_reference[:count], raw_atol)
    probability_check = _difference(clipped, np.clip(raw_reference[:count], 0, 1), probability_atol)
    # This checks two CPU implementations, separately from CPU/MPS replay.
    if not check["passed"] or not probability_check["passed"]:
        raise AssertionError(f"Independent/public CPU center mismatch: raw={check}, clipped={probability_check}")
    coefficients = fitted.model.kernel_coefficients((e - fitted.mean) / fitted.std)
    center_coefficients = coefficients[:, :, c, c]
    if not center_coefficients[:, c * (2 * c + 1) + c].eq(0).all():
        raise AssertionError("The learned center coefficient is not zero")
    return {"samples": count, "cpu_public_raw_vs_independent_center": check,
            "cpu_public_clipped_vs_independent_center": probability_check,
            "clipped_public_probability_is_exact_clip_of_raw": True,
            "sample_raw_min": float(raw.min()), "sample_raw_max": float(raw.max()),
            "sample_kernel_coefficient_min": float(center_coefficients.min()),
            "sample_kernel_coefficient_max": float(center_coefficients.max())}


@torch.inference_mode()
def _mask_checks(fitted, environment):
    e = torch.from_numpy(environment[:1].copy())
    k = fitted.model.kernel_size
    c = k // 2
    empty = torch.zeros(1, 1, k, k)
    result = fitted(empty, e, channel_names=fitted.channel_names)
    if result.valid.any() or not torch.isnan(result.raw_score).all() or not torch.isnan(result.probability).all():
        raise AssertionError("No-contact inference was interpreted as observed zero risk")
    contact = empty.clone()
    contact[0, 0, 0, 0] = 1
    result = fitted(contact, e, channel_names=fitted.channel_names)
    if not result.valid[0, 0, c, c]:
        raise AssertionError("Complete burned-neighbor context was rejected")
    missing_e = e.clone()
    missing_e[0, 0, 0, 0] = torch.nan
    result = fitted(contact, missing_e, channel_names=fitted.channel_names)
    if result.valid[0, 0, c, c] or not torch.isnan(result.raw_score[0, 0, c, c]):
        raise AssertionError("Missing environmental context became observed zero")
    missing_b = contact.clone()
    missing_b[0, 0, 0, 0] = torch.nan
    result = fitted(missing_b, e, channel_names=fitted.channel_names)
    if result.valid[0, 0, c, c] or not torch.isnan(result.raw_score[0, 0, c, c]):
        raise AssertionError("Missing burned-state context became observed zero")
    burned = torch.ones_like(empty)
    result = fitted(burned, missing_e, channel_names=fitted.channel_names)
    if not result.valid.all() or not result.raw_score.eq(0).all() or not result.probability.eq(0).all():
        raise AssertionError("An already-burned cell received new-burn risk")
    return {"no_contact_unavailable": True, "missing_environment_unavailable": True,
            "missing_burned_state_unavailable": True, "already_burned_new_burn_zero": True}


def _raw_statistics(y, raw, weight):
    total = weight.sum(dtype=np.float64)
    below, above = raw < 0, raw > 1
    return {"minimum": float(raw.min()), "maximum": float(raw.max()),
            "raw_brier": brier(y, raw, weight), "clipped_brier": brier(y, np.clip(raw, 0, 1), weight),
            "below_zero_sample_count": int(below.sum()), "above_one_sample_count": int(above.sum()),
            "below_zero_population_weight": float(weight[below].sum(dtype=np.float64)),
            "above_one_population_weight": float(weight[above].sum(dtype=np.float64)),
            "below_zero_population_fraction": float(weight[below].sum(dtype=np.float64) / total),
            "above_one_population_fraction": float(weight[above].sum(dtype=np.float64) / total)}


def verify(run_root, raw_atol=1e-5, probability_atol=1e-6,
           batch_size=2048, threads=4, output_name="verification.json"):
    """Audit all frozen native/common outputs; write an explicit pass/fail record."""
    if any(not math.isfinite(value) or value <= 0 for value in (raw_atol, probability_atol)):
        raise ValueError("CPU raw and probability tolerances must be finite and positive")
    if batch_size <= 0 or threads <= 0:
        raise ValueError("Batch size and threads must be positive")
    if Path(output_name).name != output_name or not output_name.endswith(".json"):
        raise ValueError("output_name must be a JSON basename within the run root")
    run = Path(run_root).resolve()
    output_path = run / output_name
    if output_path.exists():
        raise FileExistsError("Verification record already exists; preserve it and choose another output name")
    torch.set_num_threads(threads)
    protocol = _read(run / "protocol.json")
    if protocol["kernel_sizes"] != [3, 5, 7, 9] or protocol["family"] != "signed_direct_convolution" or protocol["horizon_hours"] != 1:
        raise AssertionError("Run does not identify the prespecified signed one-hour experiment")
    root = Path(__file__).resolve().parents[3]
    code_hashes = _read(run / "training_source_sha256.json")
    for name, recorded in code_hashes.items():
        if _hash(root / name) != recorded:
            raise AssertionError(f"Training source code changed after fitting began: {name}")
    result = {"result": "pending", "verification_device": "cpu",
              "cpu_raw_absolute_tolerance": raw_atol,
              "cpu_probability_absolute_tolerance": probability_atol,
              "batch_size": batch_size, "threads": threads, "training_code_hashes_unchanged": code_hashes,
              "native": {}, "common": {}, "artifact_sha256": {
                  "protocol.json": _hash(run / "protocol.json"),
                  "training_source_sha256.json": _hash(run / "training_source_sha256.json"),
              }}
    numerical_failures = []
    models = {}
    reference_metadata = None
    source_hashes = {}
    for k in protocol["kernel_sizes"]:
        key = str(k)
        cache = Path(protocol["native_data"][key])
        metadata_path = cache / "metadata.json"
        metadata = _read(metadata_path)
        expected_hash = protocol["native_metadata_sha256"][key]
        if _hash(metadata_path) != expected_hash:
            raise AssertionError(f"Frozen native metadata changed: K={k}")
        checkpoint_path = run / f"{k}x{k}" / "fitted" / "checkpoint.pt"
        metrics_path = checkpoint_path.parent / "metrics.json"
        metrics = _read(metrics_path)
        fitted = load_trained_model(checkpoint_path)
        models[k] = fitted
        if fitted.model.kernel_size != k or fitted.contract["kernel_constraint"] != "signed":
            raise AssertionError("Kernel size or coefficient constraint differs from protocol")
        if fitted.contract["cache_metadata_sha256"] != expected_hash or fitted.contract != metrics["contract"]:
            raise AssertionError("Checkpoint, metadata, and result contracts are not bound")
        for field in ("channels", "source_channels", "categorical_classes", "event_ids", "splits", "eligibility"):
            if fitted.contract[field] != metadata[field]:
                raise AssertionError(f"Checkpoint/cache field differs: {field}, K={k}")
        if reference_metadata is None:
            reference_metadata = metadata
        for field in ("channels", "source_channels", "categorical_classes", "event_ids", "splits"):
            if metadata[field] != reference_metadata[field]:
                raise AssertionError(f"Kernel caches disagree about {field}")
        if len(metadata["event_ids"]) != 44 or metadata["eligibility"] != "at_least_one_burned_neighbor":
            raise AssertionError("Catalog or eligibility differs from the retained former method")
        for record in metadata["source_files"]:
            path = Path(metadata["data_root"]) / record["path"]
            if str(path) not in source_hashes:
                source_hashes[str(path)] = _hash(path)
            if path.stat().st_size != record["bytes"] or source_hashes[str(path)] != record["sha256"]:
                raise AssertionError(f"Live data source changed: {path}")
        original = Path(protocol["original_runs"][key])
        original_checkpoint = original / "fitted" / "checkpoint.pt"
        if _hash(original_checkpoint) != protocol["original_checkpoint_sha256"][key]:
            raise AssertionError(f"Original checkpoint changed: K={k}")
        old = torch.load(original_checkpoint, weights_only=True, map_location="cpu")
        np.testing.assert_array_equal(fitted.mean[:, 0, 0].numpy(), old["normalization_mean"].numpy())
        np.testing.assert_array_equal(fitted.std[:, 0, 0].numpy(), old["normalization_std"].numpy())
        history = _read(checkpoint_path.parent / "history.json")
        selected = min(history, key=lambda row: row["validation_clipped_brier"])
        if (selected["epoch"] != fitted.best_epoch or metrics["selection"]["best_epoch"] != fitted.best_epoch
                or metrics["selection"]["test_used_for_selection"] is not False):
            raise AssertionError("Native checkpoint was not selected by clipped validation Brier")
        native = {"checkpoint_sha256": _hash(checkpoint_path), "original_checkpoint_sha256_unchanged": _hash(original_checkpoint),
                  "cache_metadata_sha256_unchanged": expected_hash, "normalization_equals_original_checkpoint_exactly": True,
                  "best_epoch": fitted.best_epoch, "splits": {}}
        event_sets = {}
        for split in SPLIT_NAMES:
            data = load_split(cache, split, metadata)
            event_sets[split] = set(data.event_index.tolist())
            if any(metadata["splits"][metadata["event_ids"][int(index)]] != split for index in event_sets[split]):
                raise AssertionError("An event contributes to the wrong fixed partition")
            if split == "train":
                mean, std = fit_normalization(data)
                np.testing.assert_array_equal(mean, fitted.mean[:, 0, 0].numpy())
                np.testing.assert_array_equal(std, fitted.std[:, 0, 0].numpy())
                native["training_only_normalization_recomputed_exactly"] = True
                native["inference_masks"] = _mask_checks(fitted, data.environment)
            saved_path = checkpoint_path.parent / f"{split}_predictions.npz"
            saved = _predictions(saved_path)
            prior = _predictions(original / "fitted" / f"{split}_predictions.npz")
            for output_field, cache_field in IDENTITY_FIELDS.items():
                np.testing.assert_array_equal(saved[output_field], getattr(data, cache_field))
                np.testing.assert_array_equal(saved[output_field], prior[output_field])
            np.testing.assert_array_equal(saved["neighbor_count"], data.neighbor_count)
            if not (data.neighbor_count > 0).all():
                raise AssertionError("A no-contact target entered native results")
            np.testing.assert_array_equal(saved["p"], np.clip(saved["p_raw"], 0, 1))
            reproduced = _replay(fitted, data.environment, data.burned, batch_size)
            raw_check = _difference(reproduced, saved["p_raw"], raw_atol)
            clipped_check = _difference(np.clip(reproduced, 0, 1), saved["p"], probability_atol)
            for label, check in (("raw", raw_check), ("clipped", clipped_check)):
                if not check["passed"]:
                    numerical_failures.append(f"native K={k}, {split}, {label}")
            record = metrics["splits"][split]
            actual = probability_metrics(data.target, saved["p"], data.weight, data.neighbor_count)
            _equal(actual, record["models"]["learned_environment_kernel"]["all_eligible"], f"native/{k}/{split}")
            _equal(weighted_calibration(data.target, saved["p"], data.weight), record["calibration"], f"native/{k}/{split}/calibration")
            _equal(_raw_statistics(data.target, saved["p_raw"], data.weight), record["raw_score_diagnostics"], f"native/{k}/{split}/raw")
            native["splits"][split] = {"samples": len(data), "positive_samples": int(data.target.sum()),
                "identities_labels_weights_equal_cache_and_original_exactly": True,
                "probabilities_equal_exact_clip_of_saved_raw": True,
                "recorded_probability_metrics_calibration_and_raw_diagnostics_verified": True,
                "cpu_raw_reproduction": raw_check, "cpu_clipped_probability_reproduction": clipped_check,
                "public_sample": _public_sample(fitted, data.environment, data.burned, reproduced,
                                                 raw_atol, probability_atol)}
            result["artifact_sha256"][str(saved_path.relative_to(run))] = _hash(saved_path)
            del data
        for first, second in (("train", "validation"), ("train", "test"), ("validation", "test")):
            if event_sets[first] & event_sets[second]:
                raise AssertionError("A fire contributes to multiple native partitions")
        native["disjoint_fire_partitions"] = True
        result["native"][key] = native
        result["artifact_sha256"][str(checkpoint_path.relative_to(run))] = native["checkpoint_sha256"]
        result["artifact_sha256"][str(metrics_path.relative_to(run))] = _hash(metrics_path)
        print(json.dumps({"verified_native_kernel": k, "replay": {
            split: native["splits"][split]["cpu_raw_reproduction"] for split in SPLIT_NAMES}}), flush=True)
    largest = Path(protocol["native_data"]["9"])
    largest_metadata = _read(largest / "metadata.json")
    common_metrics = _read(run / "common_metrics.json")
    reference = Path(protocol["common_reference"])
    for split in SPLIT_NAMES:
        data = load_split(largest, split, largest_metadata)
        center = 4
        inner = data.burned[:, 0, center - 1:center + 2, center - 1:center + 2]
        contact = inner.sum(axis=(1, 2)) - data.burned[:, 0, center, center]
        indices = np.flatnonzero(contact > 0)
        saved_path = run / "common_predictions" / f"{split}.npz"
        saved = _predictions(saved_path)
        prior = _predictions(reference / "common_predictions" / f"{split}.npz")
        for output_field, cache_field in IDENTITY_FIELDS.items():
            np.testing.assert_array_equal(saved[output_field], getattr(data, cache_field)[indices])
            np.testing.assert_array_equal(saved[output_field], prior[output_field])
        checked = {"samples": len(indices), "identities_labels_weights_equal_former_common_and_explicit_9x9_cache_subset": True,
                   "models": {}}
        for k in protocol["kernel_sizes"]:
            radius = k // 2
            crop = slice(center - radius, center + radius + 1)
            environment = data.environment[indices, :, crop, crop]
            burned = data.burned[indices, :, crop, crop]
            counts = burned.sum(axis=(1, 2, 3))
            np.testing.assert_array_equal(saved[f"neighbor_count_{k}"], counts)
            np.testing.assert_array_equal(saved[f"neighbor_count_{k}"], prior[f"neighbor_count_{k}"])
            np.testing.assert_array_equal(saved[f"p_original_{k}"], prior[f"p_{k}"])
            raw = saved[f"raw_direct_{k}"]
            clipped = saved[f"p_direct_{k}"]
            np.testing.assert_array_equal(clipped, np.clip(raw, 0, 1))
            reproduced = _replay(models[k], environment, burned, batch_size)
            replay = _difference(reproduced, raw, raw_atol)
            clipped_replay = _difference(np.clip(reproduced, 0, 1), clipped, probability_atol)
            if not replay["passed"]:
                numerical_failures.append(f"common K={k}, {split}, raw")
            if not clipped_replay["passed"]:
                numerical_failures.append(f"common K={k}, {split}, clipped")
            for model_name, probability in ((f"direct_{k}", clipped), (f"original_{k}", prior[f"p_{k}"])):
                record = common_metrics["splits"][split]
                _equal(probability_metrics(saved["y"], probability, saved["w"], counts), record["models"][model_name], f"common/{split}/{model_name}")
                _equal(weighted_calibration(saved["y"], probability, saved["w"]), record["calibration"][model_name], f"common/{split}/{model_name}/calibration")
            checked["models"][str(k)] = {"cpu_raw_reproduction": replay,
                "cpu_clipped_probability_reproduction": clipped_replay,
                "probability_equals_exact_clip_of_raw": True, "original_predictions_unchanged": True,
                "metrics_and_calibration_verified": True,
                "public_sample": _public_sample(models[k], environment, burned, reproduced,
                                                 raw_atol, probability_atol)}
        result["common"][split] = checked
        result["artifact_sha256"][str(saved_path.relative_to(run))] = _hash(saved_path)
        print(json.dumps({"verified_common_split": split, "samples": len(indices)}), flush=True)
        del data
    selected = min(protocol["kernel_sizes"], key=lambda k: common_metrics["splits"]["validation"]["models"][f"direct_{k}"]["brier"])
    selection = _read(run / "common_selection.json")
    if (selection != common_metrics["selection"] or selection["kernel_size"] != selected
            or selection["test_used_for_selection"] is not False):
        raise AssertionError("Common kernel selection is not bound to clipped validation Brier")
    source_bytes = sum(Path(path).stat().st_size for path in source_hashes)
    if (len(source_hashes) != protocol["source_verification"]["files"]
            or source_bytes != protocol["source_verification"]["bytes"]):
        raise AssertionError("Verified source inventory differs from the before-fitting protocol")
    result.update(result="passed" if not numerical_failures else "failed", numerical_failures=numerical_failures,
                  source_hashes_verified=len(source_hashes), source_bytes_verified=source_bytes,
                  source_hashes_match_all_native_manifests=True, original_checkpoints_unchanged=True,
                  common_selection_verified=selection,
                  verification_code_sha256=_hash(Path(__file__)),
                  finished_utc=datetime.now(timezone.utc).isoformat())
    result["artifact_sha256"].update({name: _hash(run / name) for name in ("common_metrics.json", "common_selection.json")})
    preserved_failure = run / "verification.json"
    if preserved_failure != output_path and preserved_failure.exists():
        previous = _read(preserved_failure)
        if previous.get("result") == "failed":
            result["preserved_initial_cpu_tolerance_failure"] = {
                "path": preserved_failure.name, "sha256": _hash(preserved_failure),
                "absolute_tolerance": previous["cpu_absolute_tolerance"],
                "numerical_failures": previous["numerical_failures"],
            }
    precision_path = run / "cpu_precision_audit.json"
    if precision_path.exists():
        precision = _read(precision_path)
        if precision["checkpoint_sha256"] != result["native"]["3"]["checkpoint_sha256"]:
            raise AssertionError("Precision investigation references different model weights")
        result["precision_investigation"] = {
            "path": precision_path.name, "sha256": _hash(precision_path),
            "outlier_count": precision["outlier_count"],
            "all_outlier_clipped_probabilities_identically_one": precision["all_outlier_clipped_probabilities_identically_one"],
            "exact_original_batch_mps_vs_saved_max": precision["exact_original_batch_mps_vs_saved_max"],
            "cpu_float64_public_vs_center_max": precision["cpu_float64_public_vs_center_max"],
            "cpu_float64_vs_saved_mps_raw_max": precision["cpu_float64_vs_saved_mps_raw_max"],
        }
    output_path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if numerical_failures:
        raise AssertionError(f"Explicit CPU tolerance failed; preserved {output_path}: {numerical_failures}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu"], default="cpu")
    parser.add_argument("--raw-atol", type=float, default=1e-5,
                        help="Explicit absolute tolerance for unconstrained raw scores")
    parser.add_argument("--probability-atol", type=float, default=1e-6,
                        help="Explicit absolute tolerance for evaluated clipped probabilities")
    parser.add_argument("--batch-size", type=int, default=2048)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--output-name", default="verification.json",
                        help="New JSON basename; existing records are never replaced")
    args = parser.parse_args()
    result = verify(args.run_root, args.raw_atol, args.probability_atol,
                    args.batch_size, args.threads, args.output_name)
    print(json.dumps({"result": result["result"], "output": str(args.run_root / args.output_name),
                      "cpu_raw_absolute_tolerance": args.raw_atol,
                      "cpu_probability_absolute_tolerance": args.probability_atol,
                      "source_hashes_verified": result["source_hashes_verified"]}), flush=True)


if __name__ == "__main__":
    main()
