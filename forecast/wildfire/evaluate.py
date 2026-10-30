"""Evaluate operations for the wildfire workspace."""
from __future__ import annotations

from .paths import resolve_recorded_path



# Evaluate kernels
# Compare saved kernels on a single sampled, equally weighted population.
# 
# The largest prepared context supplies anchors and inverse inclusion weights.
# Retain only anchors with a burned source in the smallest centered support.
# This is a fixed subset of one sampling design, never an intersection of
# independently subsampled negatives. Model weights and preprocessing are frozen.

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from wildfire.inference import load_single_trained_model
from wildfire.models import center_probability
from wildfire.cache import load_split
from wildfire.metrics import probability_metrics
from wildfire.metrics import weighted_calibration
from wildfire.utils import write_json
from wildfire.utils import choose_device


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
        model = load_single_trained_model(directory / "fitted" / "checkpoint.pt", device=selected_device)
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


def kernels_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    # Additive track 1B option; without it the released kernel comparison runs unchanged.
    parser.add_argument("--perimeter-scores", action="store_true",
                        help="Score saved perimeter-interval entry files (RUN_DIR/heldout/*.npz) with "
                             "wildfire.baselines.score_entries instead of comparing cached kernels")
    parser.add_argument("--bootstrap-draws", type=int, default=10000)
    args = parser.parse_args()
    if args.perimeter_scores:
        return perimeter_scores_main(args)
    evaluate_runs(args.run_dir, args.output_dir, args.device)


def perimeter_scores_main(args):
    """Write pooled, per-fire and fire-paired perimeter scores to OUTPUT_DIR/perimeter_scores.json."""
    from wildfire.baselines import load_scored_entries, score_entries
    if len(args.run_dir) != 1:
        raise SystemExit("--perimeter-scores takes exactly one --run-dir")
    entries = load_scored_entries(Path(args.run_dir[0]) / "heldout")
    result = score_entries(entries, draws=args.bootstrap_draws)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "perimeter_scores.json", result)
    return result




# Compare
# Fit Huot-style neighborhood forests against the frozen exponential 5x5 fit.
# 
# Run from the installed workspace with ``python -m
# wildfire compare --output-dir PATH``.
# Existing experimental outputs are never overwritten. Depth selection is saved
# before test arrays are loaded. Every baseline uses the native 5x5 training rows
# and their inverse inclusion weights. Metrics require contact inside each
# model's footprint; patch prediction still accepts complete no-contact inputs.


import gc
import platform
import shutil
import time
from datetime import datetime, timezone



from wildfire.metrics import country_for_event
from wildfire.metrics import select_classification_threshold
from wildfire.metrics import probability_metrics_with_all
from wildfire.models import PatchRandomForest


IDENTITY_KEYS = ("event_index", "time_utc", "row", "col")
from .paths import RUNS
ORIGINAL = "20261007_1h_kernel_sweep"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def assert_identities(data, indices, payload):
    """Bind current inputs to saved labels, weights, and unique cell-hour keys."""
    for key, actual in (("y", data.target[indices]), ("w", data.weight[indices])):
        np.testing.assert_array_equal(actual, payload[key], err_msg=key)
    for key in IDENTITY_KEYS:
        np.testing.assert_array_equal(getattr(data, key)[indices], payload[key], err_msg=key)
    keys = np.column_stack([payload[key] for key in IDENTITY_KEYS])
    if len(np.unique(keys, axis=0)) != len(keys):
        raise ValueError("Duplicate event/time/row/column identities in comparison cohort")


def subset_payload(data, indices):
    return {"y": data.target[indices], "w": data.weight[indices],
            **{key: getattr(data, key)[indices] for key in IDENTITY_KEYS}}


def cluster_bootstrap_brier(payload, candidate, reference="ours_original_5", *, draws=5000, seed=19):
    """Paired event bootstrap, resampling whole fires rather than cell-hours.

    Within each draw the score is the ratio of summed weighted losses to summed
    weights. The interval is descriptive and conditions on reconstructed labels,
    fixed fitted models, and the existing sampled cell-hours and their weights.
    """
    if draws < 1:
        raise ValueError("Bootstrap draws must be positive")
    events = np.unique(payload["event_index"])
    weights = payload["w"].astype(np.float64)
    residual_difference = ((payload[candidate].astype(np.float64) - payload["y"]) ** 2
                           - (payload[reference].astype(np.float64) - payload["y"]) ** 2)
    totals = np.array([weights[payload["event_index"] == event].sum() for event in events])
    differences = np.array([np.dot(weights[payload["event_index"] == event],
                                   residual_difference[payload["event_index"] == event])
                            for event in events])
    sampled = np.random.default_rng(seed).integers(0, len(events), size=(draws, len(events)))
    values = differences[sampled].sum(axis=1) / totals[sampled].sum(axis=1)
    lower, upper = np.quantile(values, [0.025, 0.975])
    return {"candidate": candidate, "reference": reference,
            "definition": "candidate weighted Brier minus reference weighted Brier; positive favors reference",
            "point_difference": float(differences.sum() / totals.sum()),
            "percentile_95_interval": [float(lower), float(upper)],
            "contributing_fires": len(events), "draws": draws, "seed": seed,
            "sampling_unit": "whole fire, with replacement; paired predictions in every draw",
            "limitations": f"Only {len(events)} contributing test fires; conditional on fixed models and reconstructed labels. Does not include label reconstruction or initial negative-sampling uncertainty."}


def score_payload(payload, counts, metadata, classification_thresholds=None):
    """Score only current-contact rows within each model's own footprint.

    A shared cohort should have contact for every model. On a broader native
    cache the per-model sample counts can differ, so those native scores are
    descriptive coverage results rather than a matched population comparison.
    This filtering does not alter saved full-row probability predictions.
    """
    def model_counts(name):
        return counts[name] if isinstance(counts, dict) else counts

    def model_thresholds(name):
        return None if classification_thresholds is None else classification_thresholds[name]

    names = [key for key in payload if key.startswith(("rf_", "ours_", "control_"))]
    result = {"sample_count": len(payload["y"]),
              "positive_sample_count": int(payload["y"].sum()),
              "represented_population_weight": float(payload["w"].sum()),
              "contributing_fires": len(np.unique(payload["event_index"])),
              "models": {}, "calibration": {}, "per_event": {}, "by_country": {}}
    for name in names:
        selected = model_counts(name) > 0
        result["models"][name] = probability_metrics_with_all(payload["y"][selected], payload[name][selected], payload["w"][selected], model_counts(name)[selected], thresholds=model_thresholds(name))
        result["calibration"][name] = (weighted_calibration(payload["y"][selected], payload[name][selected], payload["w"][selected])
                                       if selected.any() else {"bins": [], "weighted_expected_calibration_error": None})
    for event in np.unique(payload["event_index"]):
        selected = payload["event_index"] == event
        event_id = metadata["event_ids"][int(event)]
        result["per_event"][event_id] = {
            "country": country_for_event(metadata, event_id),
            "sample_count": int(selected.sum()),
            "models": {name: probability_metrics_with_all(payload["y"][selected & (model_counts(name) > 0)], payload[name][selected & (model_counts(name) > 0)],
                                                payload["w"][selected & (model_counts(name) > 0)], model_counts(name)[selected & (model_counts(name) > 0)], thresholds=model_thresholds(name)) for name in names}}
    country = np.array([country_for_event(metadata, metadata["event_ids"][int(event)])
                        for event in payload["event_index"]])
    for value in np.unique(country):
        selected = country == value
        result["by_country"][str(value)] = {
            "contributing_fires": len(np.unique(payload["event_index"][selected])),
            "models": {name: probability_metrics_with_all(payload["y"][selected & (model_counts(name) > 0)], payload[name][selected & (model_counts(name) > 0)],
                                                payload["w"][selected & (model_counts(name) > 0)], model_counts(name)[selected & (model_counts(name) > 0)], thresholds=model_thresholds(name)) for name in names}}
    return result


def research_record():
    return {
        "publication": "Huot et al. (2022), Next Day Wildfire Spread: A Machine Learning Dataset to Predict Wildfire Spreading From Remote-Sensing Data",
        "doi": "10.1109/TGRS.2022.3192974",
        "urls": ["https://research.google/pubs/next-day-wildfire-spread-a-machine-learning-dataset-to-predict-wildfire-spreading-from-remote-sensing-data/",
                 "https://arxiv.org/pdf/2112.02447",
                 "https://scikit-learn.org/1.5/modules/generated/sklearn.ensemble.RandomForestClassifier.html"],
        "method_locations": "Author manuscript Section IV-A and Appendix A-B",
        "published_method": {"algorithm": "pixelwise random forest with environmental and previous-fire-mask neighborhood features",
                             "context": "target pixel plus eight neighbors (3x3)",
                             "endpoint": "next-day active fire at 1 km support",
                             "depth_search": "1 through 20, selected by validation AUC-PR; selected depth 15",
                             "balancing": "balanced training sample and tuned no-fire class weighting"},
        "adaptations": ["Use our one-hour cumulative burned-state transition at the existing 375 m grid; no published numerical score is imported.",
                        "Reuse exactly the frozen native 5x5 whole-fire training rows and inverse inclusion weights; class_weight=None, no additional class rebalance.",
                        "Fit a published-footprint 3x3 forest and a 5x5 forest with the same spatial input support as ours.",
                        "Restricted depth grid 1,2,3,4,5,10,15,20, each forest uses 100 trees and seed 7; minimum leaf size 1, bootstrap enabled, Gini criterion, sqrt feature subsampling.",
                        "Select depth separately within each footprint using shared weighted validation Brier to match our probability criterion.",
                        "Use raw physical features without normalization (decision-tree split ordering is unaffected by positive affine feature scaling)."],
        "scope": "Adapted published baseline family, not an exact reproduction of the paper's data, sampling, objective, or reported scores."}


def statistical_distance_protocol():
    return {
        "distributions": "Per-cell Bernoulli(observed reconstructed binary target) and Bernoulli(predicted probability)",
        "aggregation": "Original inverse-inclusion-weighted mean of each per-cell distance or divergence, before pooling; square roots are applied per cell before averaging.",
        "metrics": ["total variation", "Hellinger", "Jensen-Shannon divergence", "Jensen-Shannon distance", "Bhattacharyya", "Wasserstein-1", "Wasserstein-2"],
        "logarithm": "natural; JS divergence and Bhattacharyya distance in nats, JS distance in square-root nats",
        "hellinger_convention": "sqrt(0.5 * sum((sqrt(P)-sqrt(Q))**2)), bounded by1",
        "wasserstein_ground_space": "Binary outcome states {0,1}, ground distance |a-b| in outcome-state units; no geographic displacement is measured.",
        "binary_identities": "TV = W1 = abs(y-p); W2 = sqrt(abs(y-p)); Bhattacharyya = exact KL/2 for binary observed y.",
        "endpoints": "Exact probabilities retained; disjoint-support Bhattacharyya distance is infinity. No prediction flooring.",
        "interpretation": "Distances to realized hard outcomes are not distances to an observed true conditional-probability field. These diagnostics are not all strictly proper probability scoring rules.",
        "selection": "Additional metrics do not change forests, selected depth, classification thresholds, or predicted probabilities."}


def statistical_distance_sources():
    return {
        "definitions": [
            {"publication": "Sason (2015), Tight Bounds for Symmetric Divergence Measures and a New Inequality Relating f-Divergences",
             "url": "https://arxiv.org/pdf/1502.06428", "used_for": "Total variation and Bhattacharyya coefficient; explicitly normalize the squared Hellinger convention by one half."},
            {"publication": "Sason and Verdu (2016), f-Divergence Inequalities",
             "url": "https://arxiv.org/pdf/1508.00335", "used_for": "Definition5: Bhattacharyya divergence and its failure of the triangle inequality."},
            {"publication": "Endres and Schindelin (2003), A New Metric for Probability Distributions",
             "url": "https://pdodds.w3.uvm.edu/research/papers/others/2003/endres2003a.pdf", "used_for": "Square-root Jensen-Shannon is a metric; their squared quantity is twice our natural-log JS divergence."},
            {"publication": "Peyre and Cuturi, Computational Optimal Transport",
             "url": "https://optimaltransport.github.io/pdf/ComputationalOT.pdf", "used_for": "Proposition2.3: Wasserstein definition; binary-unit-ground-distance coupling gives W1=TV and W2=sqrt(TV)."},
            {"publication": "Gneiting and Raftery (2007), Strictly Proper Scoring Rules, Prediction, and Estimation",
             "url": "https://sites.stat.washington.edu/people/raftery/Research/PDF/Gneiting2007jasa.pdf", "used_for": "Propriety definition and Brier/logarithmic probability scores; distinguish distribution metrics from proper hard-outcome scoring rules."}],
        "scope": "Per-cell forecast Bernoulli distribution versus observed hard outcome, not an observed true probability field or geographic mass distribution."}


def run_comparison(output_dir, *, runs=RUNS, n_estimators=100, n_jobs=4, seed=7):
    import sklearn
    output, runs = Path(output_dir).resolve(), Path(runs).resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise FileExistsError("Output must be a new or empty directory")
    if n_estimators < 1 or n_jobs < 1:
        raise ValueError("Tree and job counts must be positive")
    started = time.perf_counter()
    original_dir = runs / ORIGINAL
    train_dir, common_dir = original_dir / "5x5/prepared", original_dir / "9x9/prepared"
    train_meta, common_meta = read_json(train_dir / "metadata.json"), read_json(common_dir / "metadata.json")
    for field in ("channels", "source_channels", "categorical_classes", "event_ids", "splits", "dt_hours"):
        if train_meta[field] != common_meta[field]:
            raise ValueError(f"Native and shared input contracts differ: {field}")
    if train_meta["dt_hours"] != 1.0 or train_meta["kernel_size"] != 5:
        raise ValueError("Expected the existing one-hour native 5x5 training data")
    selected_original = read_json(original_dir / "common_selection.json")
    if selected_original["kernel_size"] != 5 or selected_original["test_used_for_selection"]:
        raise ValueError("Comparison requires the already validation-selected exponential 5x5 model")
    original = load_single_trained_model(original_dir / "5x5/fitted/checkpoint.pt", device="cpu")
    if original.contract["cache_metadata_sha256"] != sha256(train_dir / "metadata.json"):
        raise ValueError("Our exponential model was trained on a different cache")
    prior_common = read_json(original_dir / "common_metrics.json")
    if prior_common["common_metadata_sha256"] != sha256(common_dir / "metadata.json"):
        raise ValueError("Shared cache metadata differs from the frozen exponential comparison")
    torch.set_num_threads(n_jobs)
    output.mkdir(parents=True, exist_ok=True)
    protocol = {"created_utc": datetime.now(timezone.utc).isoformat(),
                "primary_comparison": "rf_5 versus frozen ours_original_5; matched 5x5 input support and training rows",
                "additional_comparison": "rf_3 follows published spatial footprint; two simple controls",
                "target": "Y_i(t)=1 iff currently unburned cell i is burned in the exact t+3600-second reconstructed snapshot",
                "horizon_hours": 1.0, "grid_spacing_m": 375,
                "training_cache": str(train_dir), "shared_cache": str(common_dir),
                "training_population": "Native 5x5 complete-context contact rows; identical to frozen exponential 5x5 fit",
                "shared_population": "Frozen 9x9 sampled cell-hours with a burned source in centered 3x3; retain original9 inverse inclusion weights",
                "native_population": "Original native5 sampled rows and weights; metrics additionally require source contact inside each model's own support",
                "kernel_sizes": [3, 5], "depth_grid": [1, 2, 3, 4, 5, 10, 15, 20],
                "depth_grid_rationale": "A preliminary validation-only grid5,10,15,20 selected its lower boundary for both footprints. Depths1-4 were added using those validation results, before inspecting baseline test performance. This remains a restricted grid relative to the paper's depths1-20.",
                "n_estimators": n_estimators, "seed": seed, "n_jobs": n_jobs,
                "selection": "Minimum shared weighted validation Brier separately per footprint; shallower depth breaks exact ties; no test use",
                "class_reweighting": None, "calibration": None,
                "classification_metrics": {"decision_rule": "positive iff predicted probability >= threshold",
                                           "fixed_threshold": .5,
                                           "threshold_selection": "Separate model-specific thresholds maximize weighted F1 and weighted MCC on shared validation only; exact ties prefer higher thresholds.",
                                           "finite_threshold_candidates": "Every unique shared validation prediction plus nextafter(max_prediction,+infinity) for the all-negative decision.",
                                           "precision_recall_auc": "Trapezoidal area of weighted precision-recall curve, including recall0 precision1 endpoint; distinct from non-interpolated average precision.",
                                           "zero_denominator_convention": "Precision, recall, F1 and MCC return zero when their denominators vanish."},
                "kl_divergence": {"direction": "Bernoulli(observed binary target) || Bernoulli(predicted probability)",
                                  "aggregation": "inverse-inclusion-weighted mean over cell-hours",
                                  "units": "nats; natural logarithms",
                                  "binary_identity": "For target y in {0,1}, per-cell KL equals Bernoulli negative log likelihood because the reference entropy is zero.",
                                  "prediction_floor_diagnostic": 1e-7,
                                  "floor_changes": "Only the prediction is clipped to [epsilon,1-epsilon]; exact KL retains boundary probabilities.",
                                  "unknown_true_probabilities": "Underlying conditional burn probabilities are not observed; the reference is the empirical hard outcome, not a known true probability field."},
                "baseline_training_preprocessing": "No scaling, imputation or category fitting; use frozen ordered 19 channels and centered current-state patches",
                "weights": "Original inverse inclusion probabilities; fit weights divided by train mean, preserving all relative weights",
                "versions": {"python": platform.python_version(), "numpy": np.__version__,
                             "sklearn": sklearn.__version__, "torch": str(torch.__version__)},
                "scientific_limits": ["Retrospective labels inside known final perimeter, not independent hourly observations.",
                                      "Teacher-forced one-hour prediction from current reconstructed state; no autoregressive rollout is evaluated.",
                                      "Shared validation has three contributing US fires and shared test has eight contributing fires.",
                                      "Existing test fires were evaluated in earlier model development; this is a frozen historical comparison, not a new blind external validation.",
                                      "RF3 receives less spatial information than ours5; RF5 matches spatial support.",
                                      "Single seed and restricted depth search; conditional bootstrap does not establish operational skill."]}
    protocol["statistical_distances"] = statistical_distance_protocol()
    write_json(output / "protocol.json", protocol)
    write_json(output / "research_sources.json", research_record())
    write_json(output / "statistical_distance_sources.json", statistical_distance_sources())
    sources = [train_dir / "metadata.json", common_dir / "metadata.json", original_dir / "protocol.json",
               original_dir / "common_selection.json", original_dir / "common_metrics.json",
               original_dir / "5x5/fitted/checkpoint.pt"]
    for split in ("train", "validation", "test"):
        sources.extend([train_dir / f"{split}.npz", common_dir / f"{split}.npz",
                        original_dir / "common_predictions" / f"{split}.npz",
                        original_dir / "5x5/fitted" / f"{split}_predictions.npz"])
    initial_hashes = {str(path): sha256(path) for path in sources}
    write_json(output / "input_sha256.json", initial_hashes)
    training = load_split(train_dir, "train", train_meta)
    common_validation = load_split(common_dir, "validation", common_meta)
    validation_indices = np.flatnonzero(common_selection(common_validation.burned, 3))
    validation = subset_payload(common_validation, validation_indices)
    with np.load(original_dir / "common_predictions/validation.npz", allow_pickle=False) as prior:
        assert_identities(common_validation, validation_indices, prior)
    prevalence = float(np.dot(training.weight, training.target) / training.weight.sum())
    selection = {"criterion": protocol["selection"], "test_used_for_selection": False,
                 "training_sample_count": len(training), "training_weighted_prevalence": prevalence,
                 "training_event_count": len(np.unique(training.event_index)),
                 "candidates": [], "selected": {}}
    selected_models = {}
    channels = tuple(train_meta["channels"])
    for k in protocol["kernel_sizes"]:
        best_value, best_model, best_depth = float("inf"), None, None
        for depth in protocol["depth_grid"]:
            fit_start = time.perf_counter()
            candidate = PatchRandomForest(kernel_size=k, max_depth=depth, n_estimators=n_estimators,
                                          random_state=seed, n_jobs=n_jobs)
            candidate.fit(training.environment, training.burned, training.target, training.weight,
                          channel_names=channels)
            probability = candidate.predict_probability(common_validation.environment[validation_indices],
                                                        common_validation.burned[validation_indices], channel_names=channels)
            candidate_name = f"rf_{k}_depth_{depth}"
            validation[candidate_name] = probability
            record = {"name": candidate_name, "kernel_size": k, "max_depth": depth,
                      "fit_and_validation_seconds": time.perf_counter() - fit_start,
                      "metrics": probability_metrics_with_all(validation["y"], probability, validation["w"],
                                                     common_validation.neighbor_count[validation_indices])}
            selection["candidates"].append(record)
            value = record["metrics"]["brier"]
            if value < best_value:
                best_value, best_model, best_depth = value, candidate, depth
            print(json.dumps({"candidate": candidate_name, "validation_brier": value,
                              "seconds": record["fit_and_validation_seconds"]}), flush=True)
            del candidate
            gc.collect()
        selected_models[k] = best_model
        selection["selected"][f"rf_{k}"] = {"max_depth": best_depth, "validation_brier": best_value,
                                                   "n_features": (len(channels) + 1) * k * k}
        best_model.save(output / f"rf_{k}.joblib", metadata={"protocol": protocol,
                                                           "selection": selection["selected"][f"rf_{k}"]})
    # This durable selection record precedes loading any test arrays.
    selection["saved_utc_before_test_read"] = datetime.now(timezone.utc).isoformat()
    write_json(output / "selection.json", selection)
    np.savez_compressed(output / "validation_candidates.npz", **validation)
    roundtrip = {}
    for k, model in selected_models.items():
        reloaded = PatchRandomForest.load(output / f"rf_{k}.joblib")
        reference = model.predict_probability(training.environment[:32], training.burned[:32], channel_names=channels)
        reproduced = reloaded.predict_probability(training.environment[:32], training.burned[:32], channel_names=channels)
        # Parallel tree-probability summation can change the last float64 bits.
        # Check exact stored trees separately from the floating reduction.
        for before, after in zip(model.estimator.estimators_, reloaded.estimator.estimators_, strict=True):
            a, b = before.tree_.__getstate__(), after.tree_.__getstate__()
            for field in ("nodes", "values"):
                np.testing.assert_array_equal(a[field], b[field])
        np.testing.assert_allclose(reference, reproduced, rtol=0, atol=1e-12)
        roundtrip[str(k)] = {"max_absolute_error": float(np.max(np.abs(reference - reproduced))),
                             "absolute_tolerance": 1e-12, "tree_parameters_exactly_equal": True,
                             "checked_training_rows": len(reference),
                             "numerical_note": "Parallel float64 sums may differ in their final bits; stored tree nodes and values are exactly equal."}
        del reloaded
    del common_validation, training, validation
    gc.collect()
    result = {"protocol": protocol, "selection": selection, "shared": {}, "native": {}, "verification": {}}
    classification_thresholds = None
    (output / "predictions").mkdir()
    for scope, directory, metadata in (("shared", common_dir, common_meta), ("native", train_dir, train_meta)):
        for split in ("validation", "test", "train"):
            data = load_split(directory, split, metadata)
            indices = (np.flatnonzero(common_selection(data.burned, 3)) if scope == "shared"
                       else np.arange(len(data)))
            payload = subset_payload(data, indices)
            footprint_counts = {}
            for k in (3, 5):
                crop = centered_slice(data.burned.shape[-1], k)
                footprint_counts[k] = data.burned[indices, :, crop, crop].sum(axis=(1, 2, 3), dtype=np.float32)
            counts = {name: footprint_counts[3 if name == "rf_3" else 5]
                      for name in ("rf_3", "rf_5", "ours_original_5",
                                   "control_no_spread", "control_train_prevalence")}
            errors = {}
            for family, folder, key in (("original", original_dir, "p_5"),):
                path = (folder / "common_predictions" / f"{split}.npz" if scope == "shared"
                        else folder / "5x5/fitted" / f"{split}_predictions.npz")
                with np.load(path, allow_pickle=False) as prior:
                    assert_identities(data, indices, prior)
                    payload[f"ours_{family}_5"] = prior[key if scope == "shared" else "p"].copy()
                # Recompute shared predictions using live checkpoints on CPU.
                if scope == "shared":
                    live, _, public_error = frozen_predictions(original, data, indices)
                    error = float(np.max(np.abs(live - payload[f"ours_{family}_5"])))
                    np.testing.assert_allclose(live, payload[f"ours_{family}_5"], rtol=0, atol=1e-6)
                    errors[family] = {"live_cpu_vs_frozen_probability_max_absolute_error": error,
                                      "absolute_tolerance": 1e-6, "public_center_max_absolute_error": public_error}
            for k, model in selected_models.items():
                predict_start = time.perf_counter()
                payload[f"rf_{k}"] = model.predict_probability(data.environment[indices], data.burned[indices],
                                                               channel_names=channels)
                errors[f"rf_{k}"] = {"prediction_seconds": time.perf_counter() - predict_start}
            payload["control_no_spread"] = np.zeros(len(indices), dtype=np.float64)
            payload["control_train_prevalence"] = np.full(len(indices), prevalence, dtype=np.float64)
            if scope == "shared" and split == "validation":
                classification_thresholds = {
                    name: {criterion: select_classification_threshold(payload["y"], payload[name], payload["w"], criterion=criterion)
                           for criterion in ("f1", "mcc")}
                    for name in payload if name.startswith(("rf_", "ours_", "control_"))}
                threshold_record = {"scope": "shared_validation", "test_used_for_threshold_selection": False,
                                    "saved_utc_before_classification_test_read": datetime.now(timezone.utc).isoformat(),
                                    "models": classification_thresholds}
                write_json(output / "classification_thresholds.json", threshold_record)
                result["classification_thresholds"] = threshold_record
            record = score_payload(payload, counts, metadata, classification_thresholds)
            if split == "test":
                record["paired_event_bootstrap_brier"] = {
                    name: cluster_bootstrap_brier(
                        {key: value[(counts[name] > 0) & (counts["ours_original_5"] > 0)] for key, value in payload.items()}, name)
                    for name in ("rf_3", "rf_5")}
            result[scope][split] = record
            result["verification"][f"{scope}_{split}"] = {"identical_unique_cell_hour_keys_labels_weights": True,
                                                          "prediction_checks": errors}
            np.savez_compressed(output / "predictions" / f"{scope}_{split}.npz",
                                neighbor_count_3=footprint_counts[3], neighbor_count_5=footprint_counts[5], **payload)
            write_json(output / "metrics.json", result)
            print(json.dumps({"scope": scope, "split": split, "samples": len(indices),
                              "brier": {name: metric["brier"] for name, metric in record["models"].items()}}), flush=True)
            del data, payload
            gc.collect()
    final_hashes = {str(path): sha256(path) for path in sources}
    if initial_hashes != final_hashes:
        raise AssertionError("An existing source artifact changed during the comparison")
    source_snapshot = output / "source_snapshot"
    source_snapshot.mkdir()
    code = sorted(Path(__file__).parent.glob("*.py"))
    for path in code:
        shutil.copy2(path, source_snapshot / path.name)
    result["verification"]["source_artifacts_unchanged"] = True
    result["verification"]["checkpoint_roundtrip"] = roundtrip
    result["verification"]["source_code_sha256"] = {str(path): sha256(path) for path in code}
    result["elapsed_seconds"] = time.perf_counter() - started
    result["completed_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(output / "metrics.json", result)
    from wildfire.report import generate_report
    generate_report(output)
    artifacts = {str(path.relative_to(output)): sha256(path) for path in output.rglob("*") if path.is_file()}
    write_json(output / "output_sha256.json", artifacts)
    return result


def baseline_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runs", type=Path, default=RUNS)
    parser.add_argument("--n-estimators", type=int, default=100)
    parser.add_argument("--n-jobs", type=int, default=4)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    run_comparison(args.output_dir, runs=args.runs, n_estimators=args.n_estimators,
                   n_jobs=args.n_jobs, seed=args.seed)




# Add kl
# Add explicit Bernoulli KL to a completed comparison without refitting.
# 
# Prediction arrays, fitted forests, and selected settings remain unchanged.
# Pre-KL metric/source/manifest records must be preserved before running this
# command. ``python -m ...baselines.add_kl RUN_DIRECTORY`` rescales no input and
# recomputes the score tables from the existing saved probabilities and weights.





from wildfire.metrics import probability_metrics_with_kl
from wildfire.report import generate_report


def add_kl_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def add_kl(run_directory):
    run = Path(run_directory).resolve()
    before_manifest = json.loads((run / "output_sha256_before_kl.json").read_text())
    result = json.loads((run / "metrics.json").read_text())
    previous = json.loads((run / "metrics_before_kl.json").read_text())
    immutable = ["rf_3.joblib", "rf_5.joblib", "validation_candidates.npz"] + [
        f"predictions/{scope}_{split}.npz" for scope in ("shared", "native")
        for split in ("train", "validation", "test")]
    for name in immutable:
        if add_kl_digest(run / name) != before_manifest[name]:
            raise ValueError(f"A fitted model or prediction archive changed: {name}")
    protocol = json.loads((run / "protocol.json").read_text())
    protocol["kl_divergence"] = {
        "direction": "Bernoulli(observed binary target) || Bernoulli(predicted probability)",
        "aggregation": "inverse-inclusion-weighted mean over cell-hours",
        "units": "nats; natural logarithms",
        "binary_identity": "For target y in {0,1}, per-cell KL equals Bernoulli negative log likelihood because reference entropy is zero.",
        "prediction_floor_diagnostic": 1e-7,
        "floor_changes": "Only prediction is clipped to [epsilon,1-epsilon]; exact KL retains boundary probabilities.",
        "unknown_true_probabilities": "Reference is the empirical hard outcome; underlying conditional burn probabilities are unobserved."}
    result["protocol"] = protocol
    selection = json.loads((run / "selection.json").read_text())
    with np.load(run / "validation_candidates.npz", allow_pickle=False) as candidates:
        with np.load(run / "predictions/shared_validation.npz", allow_pickle=False) as validation:
            for record in selection["candidates"]:
                count = validation[f"neighbor_count_{record['kernel_size']}"]
                updated = probability_metrics_with_kl(candidates["y"], candidates[record["name"]], candidates["w"], count)
                for field, value in record["metrics"].items():
                    if updated[field] != value:
                        raise AssertionError(f"Existing validation metric changed: {record['name']} {field}")
                record["metrics"] = updated
    if selection["selected"] != previous["selection"]["selected"]:
        raise AssertionError("The selected settings changed while adding KL")
    result["selection"] = selection
    metadata_by_scope = {
        "shared": json.loads((resolve_recorded_path(protocol["shared_cache"]) / "metadata.json").read_text()),
        "native": json.loads((resolve_recorded_path(protocol["training_cache"]) / "metadata.json").read_text())}
    for scope in ("shared", "native"):
        for split in ("train", "validation", "test"):
            with np.load(run / "predictions" / f"{scope}_{split}.npz", allow_pickle=False) as archive:
                payload = {key: archive[key] for key in archive.files if not key.startswith("neighbor_count_")}
                counts = {name: archive["neighbor_count_3" if name == "rf_3" else "neighbor_count_5"]
                          for name in payload if name.startswith(("rf_", "ours_", "control_"))}
                updated = score_payload(payload, counts, metadata_by_scope[scope])
            old = previous[scope][split]
            for name, values in old["models"].items():
                for field, value in values.items():
                    if updated["models"][name][field] != value:
                        raise AssertionError(f"Existing pooled metric changed: {scope} {split} {name} {field}")
            if "paired_event_bootstrap_brier" in old:
                updated["paired_event_bootstrap_brier"] = old["paired_event_bootstrap_brier"]
            result[scope][split] = updated
    for name in immutable:
        if add_kl_digest(run / name) != before_manifest[name]:
            raise AssertionError("A prediction or model changed during score extension")
    result["verification"]["kl_metric_extension"] = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "prediction_and_forest_artifact_sha256_unchanged": True,
        "selected_settings_unchanged": True, "original_metric_values_unchanged": True,
        "fitted_models_retrained": False,
        "pre_kl_manifest_sha256": add_kl_digest(run / "output_sha256_before_kl.json")}
    for name in ("evaluate.py", "report.py", "metrics.py"):
        path = Path(__file__).with_name(name)
        shutil.copy2(path, run / "source_snapshot" / name)
        result["verification"]["source_code_sha256"][str(path)] = add_kl_digest(path)
    for name, value in (("protocol.json", protocol), ("selection.json", selection), ("metrics.json", result)):
        (run / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    generate_report(run)
    artifacts = {str(path.relative_to(run)): add_kl_digest(path) for path in run.rglob("*")
                 if path.is_file() and path.name not in ("output_sha256.json", "independent_audit.json")}
    (run / "output_sha256.json").write_text(json.dumps(artifacts, indent=2) + "\n")
    return result




# Add distances
# Add exact Bernoulli statistical distances to a frozen comparison.
# 
# All forecasts, fitted models, selected depths, and classification thresholds
# remain unchanged. Preserve metrics/protocol/selection/output_sha256 records as
# *_before_distances.json before running this extension. It is an additional
# analysis of the previously inspected historical cohorts, with no new tuning.







def add_distances_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def assert_preserved(previous, current, path=""):
    """Require exact preservation of all old nested metric fields."""
    if isinstance(previous, dict):
        for key, value in previous.items():
            if key not in current:
                raise AssertionError(f"Existing field missing: {path}/{key}")
            assert_preserved(value, current[key], f"{path}/{key}")
    elif isinstance(previous, list):
        if not isinstance(current, list) or len(previous) != len(current):
            raise AssertionError(f"Existing list changed: {path}")
        for index, value in enumerate(previous):
            assert_preserved(value, current[index], f"{path}/{index}")
    elif previous != current:
        raise AssertionError(f"Existing value changed: {path}")


def add_distances(run_directory):
    run = Path(run_directory).resolve()
    before_manifest = json.loads((run / "output_sha256_before_distances.json").read_text())
    previous = json.loads((run / "metrics_before_distances.json").read_text())
    result = json.loads((run / "metrics.json").read_text())
    immutable = ["rf_3.joblib", "rf_5.joblib", "validation_candidates.npz",
                 "classification_thresholds.json"] + [
        f"predictions/{scope}_{split}.npz" for scope in ("shared", "native")
        for split in ("train", "validation", "test")]
    for name in immutable:
        if add_distances_digest(run / name) != before_manifest[name]:
            raise ValueError(f"Frozen forecast or selection artifact changed: {name}")
    protocol = json.loads((run / "protocol.json").read_text())
    protocol["statistical_distances"] = statistical_distance_protocol()
    result["protocol"] = protocol
    (run / "statistical_distance_sources.json").write_text(json.dumps(statistical_distance_sources(), indent=2) + "\n")
    thresholds = result["classification_thresholds"]["models"]
    selection = json.loads((run / "selection.json").read_text())
    with np.load(run / "validation_candidates.npz", allow_pickle=False) as candidates:
        with np.load(run / "predictions/shared_validation.npz", allow_pickle=False) as validation:
            for record in selection["candidates"]:
                count = validation[f"neighbor_count_{record['kernel_size']}"]
                updated = probability_metrics_with_all(candidates["y"], candidates[record["name"]], candidates["w"], count)
                assert_preserved(record["metrics"], updated, record["name"])
                record["metrics"] = updated
    assert_preserved(previous["selection"], selection, "selection")
    result["selection"] = selection
    metadata_by_scope = {
        "shared": json.loads((resolve_recorded_path(protocol["shared_cache"]) / "metadata.json").read_text()),
        "native": json.loads((resolve_recorded_path(protocol["training_cache"]) / "metadata.json").read_text())}
    for scope in ("shared", "native"):
        for split in ("train", "validation", "test"):
            with np.load(run / "predictions" / f"{scope}_{split}.npz", allow_pickle=False) as archive:
                payload = {key: archive[key] for key in archive.files if not key.startswith("neighbor_count_")}
                counts = {name: archive["neighbor_count_3" if name == "rf_3" else "neighbor_count_5"]
                          for name in thresholds}
                updated = score_payload(payload, counts, metadata_by_scope[scope], thresholds)
            old = previous[scope][split]
            if "paired_event_bootstrap_brier" in old:
                updated["paired_event_bootstrap_brier"] = old["paired_event_bootstrap_brier"]
            assert_preserved(old, updated, f"{scope}/{split}")
            result[scope][split] = updated
    for name in immutable:
        if add_distances_digest(run / name) != before_manifest[name]:
            raise AssertionError(f"Frozen artifact changed during extension: {name}")
    result["verification"]["statistical_distance_extension"] = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "forecast_model_and_threshold_artifact_sha256_unchanged": True,
        "selected_forest_settings_unchanged": True,
        "all_previous_nested_metric_fields_exactly_preserved": True,
        "fitted_models_retrained": False, "new_metric_tuning": False,
        "pre_distances_manifest_sha256": add_distances_digest(run / "output_sha256_before_distances.json"),
        "chronology": "Additional metrics requested after previous test-score inspection; no new blinded evaluation."}
    for name in ("evaluate.py", "report.py", "metrics.py"):
        path = Path(__file__).with_name(name)
        shutil.copy2(path, run / "source_snapshot" / name)
        result["verification"]["source_code_sha256"][str(path)] = add_distances_digest(path)
    for name, value in (("protocol.json", protocol), ("selection.json", selection), ("metrics.json", result)):
        (run / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    generate_report(run)
    artifacts = {str(path.relative_to(run)): add_distances_digest(path) for path in run.rglob("*")
                 if path.is_file() and path.name not in ("output_sha256.json", "independent_audit.json")}
    (run / "output_sha256.json").write_text(json.dumps(artifacts, indent=2) + "\n")
    return result




# Add classification
# Extend a frozen comparison with PR AUC, F1, and MCC without refitting.
# 
# Thresholds are selected solely from saved shared-validation probabilities and
# written before this extension reads classification test outcomes. This is an
# additional analysis of a previously inspected historical test cohort, rather
# than a newly blinded experiment. Existing probability metrics remain unchanged.







def add_classification_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def add_classification(run_directory):
    run = Path(run_directory).resolve()
    before_manifest = json.loads((run / "output_sha256_before_classification.json").read_text())
    previous = json.loads((run / "metrics_before_classification.json").read_text())
    result = json.loads((run / "metrics.json").read_text())
    immutable = ["rf_3.joblib", "rf_5.joblib", "validation_candidates.npz"] + [
        f"predictions/{scope}_{split}.npz" for scope in ("shared", "native")
        for split in ("train", "validation", "test")]
    for name in immutable:
        if add_classification_digest(run / name) != before_manifest[name]:
            raise ValueError(f"Frozen probability artifact changed: {name}")
    protocol = json.loads((run / "protocol.json").read_text())
    protocol["classification_metrics"] = {
        "decision_rule": "positive iff predicted probability >= threshold",
        "weights": "Original inverse inclusion weights for every confusion count and metric",
        "fixed_threshold": .5,
        "threshold_selection": "Separate model-specific thresholds maximize weighted F1 and weighted MCC on shared validation only; exact ties prefer higher thresholds.",
        "finite_threshold_candidates": "Every unique shared validation prediction plus nextafter(max_prediction,+infinity) for the all-negative decision.",
        "precision_recall_auc": "Trapezoidal area of weighted precision-recall curve with recall0/precision1 endpoint; distinct from average precision.",
        "zero_denominator_convention": "Precision, recall, F1 and MCC return zero when their denominators vanish."}
    with np.load(run / "predictions/shared_validation.npz", allow_pickle=False) as validation:
        names = [name for name in validation.files if name.startswith(("rf_", "ours_", "control_"))]
        thresholds = {name: {criterion: select_classification_threshold(validation["y"], validation[name], validation["w"], criterion=criterion)
                             for criterion in ("f1", "mcc")} for name in names}
    threshold_record = {
        "scope": "shared_validation", "test_used_for_threshold_selection": False,
        "saved_utc_before_classification_test_read": datetime.now(timezone.utc).isoformat(),
        "requested_after_probability_test_evaluation": True,
        "chronology": "The user requested these additional metrics after the probability comparison. All threshold choices use only shared validation; this remains a historical analysis of previously inspected test fires.",
        "models": thresholds}
    (run / "classification_thresholds.json").write_text(json.dumps(threshold_record, indent=2, allow_nan=False) + "\n")
    result["protocol"], result["classification_thresholds"] = protocol, threshold_record
    selection = json.loads((run / "selection.json").read_text())
    with np.load(run / "validation_candidates.npz", allow_pickle=False) as candidates:
        with np.load(run / "predictions/shared_validation.npz", allow_pickle=False) as validation:
            for record in selection["candidates"]:
                count = validation[f"neighbor_count_{record['kernel_size']}"]
                updated = probability_metrics_with_all(candidates["y"], candidates[record["name"]], candidates["w"], count)
                for field, value in record["metrics"].items():
                    if updated[field] != value:
                        raise AssertionError(f"Existing candidate metric changed: {record['name']} {field}")
                record["metrics"] = updated
    if selection["selected"] != previous["selection"]["selected"]:
        raise AssertionError("Adding classification metrics changed selected forest settings")
    result["selection"] = selection
    metadata_by_scope = {
        "shared": json.loads((resolve_recorded_path(protocol["shared_cache"]) / "metadata.json").read_text()),
        "native": json.loads((resolve_recorded_path(protocol["training_cache"]) / "metadata.json").read_text())}
    for scope in ("shared", "native"):
        for split in ("validation", "test", "train"):
            with np.load(run / "predictions" / f"{scope}_{split}.npz", allow_pickle=False) as archive:
                payload = {key: archive[key] for key in archive.files if not key.startswith("neighbor_count_")}
                counts = {name: archive["neighbor_count_3" if name == "rf_3" else "neighbor_count_5"]
                          for name in names}
                updated = score_payload(payload, counts, metadata_by_scope[scope], thresholds)
            old = previous[scope][split]
            for name, values in old["models"].items():
                for field, value in values.items():
                    if updated["models"][name][field] != value:
                        raise AssertionError(f"Existing pooled metric changed: {scope} {split} {name} {field}")
            if "paired_event_bootstrap_brier" in old:
                updated["paired_event_bootstrap_brier"] = old["paired_event_bootstrap_brier"]
            result[scope][split] = updated
    for name in immutable:
        if add_classification_digest(run / name) != before_manifest[name]:
            raise AssertionError("A prediction or forest changed during classification extension")
    result["verification"]["classification_metric_extension"] = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "prediction_and_forest_artifact_sha256_unchanged": True,
        "selected_forest_settings_unchanged": True, "previous_probability_and_kl_metric_values_unchanged": True,
        "fitted_models_retrained": False, "test_used_for_threshold_selection": False,
        "pre_classification_manifest_sha256": add_classification_digest(run / "output_sha256_before_classification.json")}
    for name in ("evaluate.py", "report.py", "metrics.py"):
        path = Path(__file__).with_name(name)
        shutil.copy2(path, run / "source_snapshot" / name)
        result["verification"]["source_code_sha256"][str(path)] = add_classification_digest(path)
    for name, value in (("protocol.json", protocol), ("selection.json", selection), ("metrics.json", result)):
        (run / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    generate_report(run)
    artifacts = {str(path.relative_to(run)): add_classification_digest(path) for path in run.rglob("*")
                 if path.is_file() and path.name not in ("output_sha256.json", "independent_audit.json")}
    (run / "output_sha256.json").write_text(json.dumps(artifacts, indent=2) + "\n")
    return result


