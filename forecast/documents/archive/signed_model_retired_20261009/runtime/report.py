"""Report the signed direct-convolution experiment from saved predictions.

This module does not fit or select models using test data. It independently
recomputes recorded probability scores and audits the exact paired population.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from ..report_training import (SPLITS, link, markdown_table, number, percent,
                               precision_recall, read_json, whole)
from ..metrics import brier, probability_metrics, weighted_calibration

# report_training configures a disposable Matplotlib cache and the Agg backend.
import matplotlib.pyplot as plt


KERNELS = (3, 5, 7, 9)
COLORS = {3: "#1769aa", 5: "#d48218", 7: "#278154", 9: "#9c5796"}
IDENTITY_KEYS = ("y", "w", "event_index", "time_utc", "row", "col")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clipping_percent(value: float) -> str:
    """Keep small nonzero clipping fractions visible rather than rounding to zero."""
    return f"{100 * value:.6f}".rstrip("0").rstrip(".") + "%"


def load_predictions(path: Path) -> dict:
    with np.load(path, allow_pickle=False) as archive:
        values = {key: archive[key] for key in archive.files}
    y, weight = values["y"], values["w"]
    if (y.ndim != 1 or not len(y) or weight.shape != y.shape
            or not np.isin(y, [0, 1]).all() or not np.isfinite(weight).all()
            or not (weight > 0).all()):
        raise ValueError(f"Invalid labels or sampling weights: {path}")
    if any(values[key].shape != y.shape for key in IDENTITY_KEYS):
        raise ValueError(f"Invalid cell-hour identity shape: {path}")
    identity = np.rec.fromarrays([values[key] for key in IDENTITY_KEYS[2:]])
    if len(np.unique(identity)) != len(y):
        raise ValueError(f"Duplicate cell-hour identity: {path}")
    return values


def compare_metrics(actual: dict, recorded: dict, label: str) -> None:
    """Check values including exact zero/one log-loss singularities."""
    for key, value in actual.items():
        if key not in recorded:
            raise ValueError(f"Missing recorded {key}: {label}")
        saved = recorded[key]
        if isinstance(value, (dict, list)):
            if isinstance(value, dict):
                compare_metrics(value, saved, f"{label}/{key}")
            else:
                if len(value) != len(saved):
                    raise ValueError(f"Mismatched recorded array length: {label}/{key}")
                for index, (a, s) in enumerate(zip(value, saved, strict=True)):
                    if isinstance(a, dict):
                        compare_metrics(a, s, f"{label}/{key}/{index}")
                    elif a != s:
                        raise ValueError(f"Mismatched recorded array: {label}/{key}")
        elif value is None or isinstance(value, (str, bool)):
            if saved != value:
                raise ValueError(f"Mismatched recorded {key}: {label}")
        elif not np.isclose(value, saved, rtol=0, atol=1e-10):
            raise ValueError(f"Mismatched recorded {key}: {label}")


def raw_diagnostics(y: np.ndarray, raw: np.ndarray, weight: np.ndarray) -> dict:
    """Raw values are unconstrained scores, rather than probabilities."""
    if raw.shape != y.shape or not np.isfinite(raw).all():
        raise ValueError("Raw convolution outputs must be finite and match targets")
    total = float(weight.sum(dtype=np.float64))
    below, above = raw < 0, raw > 1
    clipped = np.clip(raw, 0, 1)
    return dict(raw_minimum=float(raw.min()), raw_maximum=float(raw.max()),
                raw_brier=brier(y, raw, weight),
                clipped_brier=brier(y, clipped, weight),
                below_zero_sample_count=int(below.sum()),
                above_one_sample_count=int(above.sum()),
                below_zero_sample_fraction=float(below.mean()),
                above_one_sample_fraction=float(above.mean()),
                below_zero_population_weight=float(weight[below].sum(dtype=np.float64)),
                above_one_population_weight=float(weight[above].sum(dtype=np.float64)),
                below_zero_weighted_fraction=float(weight[below].sum(dtype=np.float64) / total),
                above_one_weighted_fraction=float(weight[above].sum(dtype=np.float64) / total),
                positive_at_zero_sample_count=int(((y == 1) & (clipped == 0)).sum()),
                negative_at_one_sample_count=int(((y == 0) & (clipped == 1)).sum()))


def ensure_probabilities(y: np.ndarray, probability: np.ndarray, label: str) -> None:
    if (probability.shape != y.shape or not np.isfinite(probability).all()
            or not ((probability >= 0) & (probability <= 1)).all()):
        raise ValueError(f"Invalid probabilities: {label}")


def native_original_runs(sweep: Path, original3: Path) -> dict[int, Path]:
    return {3: original3, **{kernel: sweep / f"{kernel}x{kernel}" for kernel in (5, 7, 9)}}


def native_raw(values: dict) -> np.ndarray:
    for key in ("p_raw", "raw", "q_raw", "raw_probability", "raw_prediction", "raw_output"):
        if key in values:
            return values[key]
    raise ValueError("A direct native prediction file does not contain raw convolution outputs")


def load_native(root: Path, originals: dict[int, Path]) -> dict:
    native = {}
    for kernel in KERNELS:
        fitted = root / f"{kernel}x{kernel}" / "fitted"
        original = originals[kernel]
        metadata = read_json(original / "prepared/metadata.json")
        metrics = read_json(fitted / "metrics.json")
        history = read_json(fitted / "history.json")
        configuration = read_json(fitted / "configuration.json")
        old_metrics = read_json(original / "fitted/metrics.json")
        old_configuration = read_json(original / "fitted/configuration.json")
        if (metrics["contract"]["kernel_size"] != kernel
                or metrics["contract"]["in_channels"] != 19
                or metrics["contract"]["hidden_channels"] != 16):
            raise ValueError("The report's kernel, input, and hidden-width capacity contract changed")
        if metrics["selection"].get("test_used_for_selection", True):
            raise ValueError("Direct native checkpoint selection must exclude test data")
        val_key = "validation_clipped_brier" if "validation_clipped_brier" in history[0] else "validation_brier"
        if min(history, key=lambda row: row[val_key])["epoch"] != metrics["selection"]["best_epoch"]:
            raise ValueError("The direct checkpoint is not the minimum clipped validation-Brier epoch")
        if metrics["contract"]["cache_metadata_sha256"] != digest(original / "prepared/metadata.json"):
            raise ValueError("Direct native cache binding differs from the original cache")
        for key in ("channels", "in_channels", "hidden_channels", "kernel_size", "splits", "dt_hours"):
            if metrics["contract"][key] != old_metrics["contract"][key]:
                raise ValueError(f"A paired model contract differs in {key}")
        for key in ("seed", "epochs", "patience", "batch_size", "hidden_channels", "learning_rate", "weight_decay"):
            if configuration["arguments"][key] != old_configuration["arguments"][key]:
                raise ValueError(f"A paired training configuration differs in {key}")
        entry = dict(metrics=metrics, history=history, configuration=configuration,
                     metadata=metadata, original_metrics=old_metrics, fitted=fitted,
                     original=original, splits={})
        for split in SPLITS:
            direct = load_predictions(fitted / f"{split}_predictions.npz")
            old = load_predictions(original / "fitted" / f"{split}_predictions.npz")
            for key in (*IDENTITY_KEYS, "neighbor_count"):
                if not np.array_equal(direct[key], old[key]):
                    raise ValueError(f"Native paired labels/weights/identities differ: {kernel}/{split}/{key}")
            raw, probability = native_raw(direct), direct["p"]
            ensure_probabilities(direct["y"], probability, f"native/{kernel}/{split}")
            if not np.array_equal(probability, np.clip(raw, 0, 1)):
                raise ValueError("Native evaluated direct probabilities must equal exact [0,1] clipping")
            clipping = raw_diagnostics(direct["y"], raw, direct["w"])
            computed = probability_metrics(direct["y"], probability, direct["w"], direct["neighbor_count"])
            original_score = probability_metrics(old["y"], old["p"], old["w"], old["neighbor_count"])
            compare_metrics(computed, metrics["splits"][split]["models"]["learned_environment_kernel"]["all_eligible"],
                            f"native/{kernel}/{split}/direct")
            compare_metrics(original_score, old_metrics["splits"][split]["models"]["learned_environment_kernel"]["all_eligible"],
                            f"native/{kernel}/{split}/original")
            compare_metrics(weighted_calibration(direct["y"], probability, direct["w"]),
                            metrics["splits"][split]["calibration"], f"native/{kernel}/{split}/calibration")
            raw_record = metrics["splits"][split]["raw_score_diagnostics"]
            compare_metrics({"minimum": clipping["raw_minimum"], "maximum": clipping["raw_maximum"],
                             "raw_brier": clipping["raw_brier"], "clipped_brier": clipping["clipped_brier"],
                             "below_zero_sample_count": clipping["below_zero_sample_count"],
                             "above_one_sample_count": clipping["above_one_sample_count"],
                             "below_zero_population_fraction": clipping["below_zero_weighted_fraction"],
                             "above_one_population_fraction": clipping["above_one_weighted_fraction"]},
                            raw_record, f"native/{kernel}/{split}/raw")
            entry["splits"][split] = dict(direct=computed, original=original_score,
                                           raw=clipping, contributing_events=len(np.unique(direct["event_index"])))
        native[kernel] = entry
    return native


def load_common(root: Path, original_sweep: Path) -> tuple[dict, dict, dict, int]:
    common = read_json(root / "common_metrics.json")
    values, audit = {}, {}
    for split in SPLITS:
        saved = load_predictions(root / "common_predictions" / f"{split}.npz")
        original = load_predictions(original_sweep / "common_predictions" / f"{split}.npz")
        for key in IDENTITY_KEYS:
            if not np.array_equal(saved[key], original[key]):
                raise ValueError(f"The exact original common population changed: {split}/{key}")
        audit[split] = dict(sample_count=len(saved["y"]), paired_identity_labels_weights_equal=True,
                            metrics={}, calibration={}, raw_diagnostics={})
        previous = None
        for kernel in KERNELS:
            neighbors = saved[f"neighbor_count_{kernel}"]
            if not np.array_equal(neighbors, original[f"neighbor_count_{kernel}"]):
                raise ValueError("Common burned-neighbor counts changed")
            if not (neighbors > 0).all() or (previous is not None and (neighbors < previous).any()):
                raise ValueError("Common target must have nested positive source-contact counts")
            previous = neighbors
            if not np.array_equal(saved[f"p_original_{kernel}"], original[f"p_{kernel}"]):
                raise ValueError("The frozen original common predictions changed")
            raw = saved[f"raw_direct_{kernel}"]
            if not np.array_equal(saved[f"p_direct_{kernel}"], np.clip(raw, 0, 1)):
                raise ValueError("Common direct probabilities differ from exact [0,1] clipping")
            raw_stats = raw_diagnostics(saved["y"], raw, saved["w"])
            compare_metrics({"raw_min": raw_stats["raw_minimum"], "raw_max": raw_stats["raw_maximum"],
                             "raw_brier": raw_stats["raw_brier"],
                             "below_zero_count": raw_stats["below_zero_sample_count"],
                             "above_one_count": raw_stats["above_one_sample_count"],
                             "below_zero_sample_fraction": raw_stats["below_zero_sample_fraction"],
                             "above_one_sample_fraction": raw_stats["above_one_sample_fraction"],
                             "below_zero_weighted_fraction": raw_stats["below_zero_weighted_fraction"],
                             "above_one_weighted_fraction": raw_stats["above_one_weighted_fraction"]},
                            common["splits"][split]["clipping"][f"direct_{kernel}"],
                            f"common/{split}/{kernel}/raw")
            audit[split]["raw_diagnostics"][str(kernel)] = raw_stats
            for kind in ("original", "direct"):
                key = f"{kind}_{kernel}"
                probability = saved[f"p_{key}"]
                ensure_probabilities(saved["y"], probability, f"common/{split}/{key}")
                computed = probability_metrics(saved["y"], probability, saved["w"], neighbors)
                calibration = weighted_calibration(saved["y"], probability, saved["w"])
                compare_metrics(computed, common["splits"][split]["models"][key], f"{split}/{key}")
                compare_metrics(calibration, common["splits"][split]["calibration"][key], f"{split}/{key}/calibration")
                audit[split]["metrics"][key], audit[split]["calibration"][key] = computed, calibration
        values[split] = saved
    selected = min(KERNELS, key=lambda kernel: common["splits"]["validation"]["models"][f"direct_{kernel}"]["brier"])
    if (common["selection"]["kernel_size"] != selected
            or common["selection"].get("test_used_for_selection", True)):
        raise ValueError("The direct kernel choice must be the common-validation Brier minimizer")
    if read_json(root / "common_selection.json") != common["selection"]:
        raise ValueError("The pre-test selection artifact differs from the final selection")
    return common, values, audit, selected


def make_figure(path: Path, common: dict, values: dict, selected: int) -> None:
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 12, "axes.labelsize": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(2, 2, figsize=(13.8, 10.0), layout="constrained")
    x = np.arange(4)
    for ax, split in zip(axes[0], ("validation", "test"), strict=True):
        for shift, kind, color in ((-.18, "original", "#7d91a5"), (.18, "direct", "#cf8032")):
            scores = [common["splits"][split]["models"][f"{kind}_{kernel}"]["brier"] for kernel in KERNELS]
            bars = ax.bar(x + shift, scores, width=.36, color=color,
                          label="Original exponential link" if kind == "original" else "Signed direct convolution (clipped)")
            ax.bar_label(bars, labels=[f"{score:.4f}" for score in scores], padding=3, fontsize=8, rotation=40)
        max_score = max(common["splits"][split]["models"][f"{kind}_{kernel}"]["brier"]
                        for kernel in KERNELS for kind in ("original", "direct"))
        ax.set(title=f"Shared {split}: paired probability error", ylabel="Weighted Brier (lower is better)",
               xticks=x, xticklabels=[f"{kernel}×{kernel}" for kernel in KERNELS], ylim=(0, max_score * 1.25))
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
    test = values["test"]
    for kernel in KERNELS:
        for kind, style in (("original", "--"), ("direct", "-")):
            recall, precision, ap = precision_recall(test["y"], test[f"p_{kind}_{kernel}"], test["w"])
            axes[1, 0].step(recall, precision, where="pre", linewidth=1.2, color=COLORS[kernel], linestyle=style,
                            label=f"{kernel}×{kernel} {'original' if kind == 'original' else 'direct'}: AP {ap:.3f}")
    prevalence = common["splits"]["test"]["models"]["direct_3"]["weighted_prevalence"]
    axes[1, 0].axhline(prevalence, color="#777777", linewidth=1, linestyle=":", label=f"Outcome rate {prevalence:.3f}")
    axes[1, 0].set(title="Shared test precision–recall", xlabel="Recall", ylabel="Precision", xlim=(0, 1), ylim=(0, 1.01))
    axes[1, 0].legend(frameon=False, fontsize=8, loc="upper right")
    axes[1, 0].grid(alpha=.2)
    nonempty = {f"{kind}_{kernel}": [row for row in common["splits"]["test"]["calibration"][f"{kind}_{kernel}"]["bins"]
                                   if row["sample_count"]]
                for kernel in KERNELS for kind in ("original", "direct")}
    limit = min(100, max(10, 1.12 * max(max(row["mean_probability"], row["weighted_outcome_rate"]) * 100
                                     for bins in nonempty.values() for row in bins)))
    axes[1, 1].plot([0, limit], [0, limit], color="#777777", linestyle=":", linewidth=1)
    for kernel in KERNELS:
        for kind, style, marker in (("original", "--", "o"), ("direct", "-", "s")):
            bins = nonempty[f"{kind}_{kernel}"]
            axes[1, 1].plot([row["mean_probability"] * 100 for row in bins],
                            [row["weighted_outcome_rate"] * 100 for row in bins], color=COLORS[kernel],
                            linestyle=style, marker=marker, markersize=3.5, linewidth=1,
                            label=f"{kernel}×{kernel} {kind}")
    axes[1, 1].set(title="Shared test reliability", xlabel="Bin mean predicted probability (%)",
                   ylabel="Bin weighted outcome rate (%)", xlim=(0, limit), ylim=(0, limit))
    axes[1, 1].legend(frameon=False, fontsize=8, loc="lower right")
    axes[1, 1].grid(alpha=.2)
    fig.suptitle(f"Next-hour burning: signed direct convolution versus exponential link\n"
                 f"Direct kernel selected on shared validation: {selected}×{selected}", fontsize=15)
    fig.supxlabel("Every paired score uses identical target labels, cell-hour identities, and inverse sampling weights.", fontsize=10)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def coverage(values: dict, metadata: dict) -> dict:
    countries = {event["id"]: event["country"] for event in metadata["per_event"]}
    result = {}
    for split in SPLITS:
        ids = [metadata["event_ids"][index] for index in np.unique(values[split]["event_index"])]
        if any(metadata["splits"][event] != split for event in ids):
            raise ValueError("A common fire belongs to a different fixed partition")
        result[split] = dict(event_ids=ids, countries={country: sum(countries[event] == country for event in ids)
                                                     for country in sorted({countries[event] for event in ids})})
    return result


def numerical_verification(root: Path) -> dict | None:
    """Read a completed audit; retain the initial failed raw-only precision check."""
    final_path = root / "verification_separate_tolerances.json"
    if not final_path.exists():
        return None
    final = read_json(final_path)
    if final["result"] != "passed" or final["numerical_failures"]:
        raise ValueError("The final numerical verification did not pass")
    for relative, expected in final["artifact_sha256"].items():
        if digest(root / relative) != expected:
            raise ValueError(f"Numerical verification input changed: {relative}")
    raw_atol = final["cpu_raw_absolute_tolerance"]
    probability_atol = final["cpu_probability_absolute_tolerance"]
    if raw_atol != 1e-5 or probability_atol != 1e-6:
        raise ValueError("The recorded raw/probability precision domains changed")
    records = [split for entry in final["native"].values() for split in entry["splits"].values()]
    records += [model for split in final["common"].values() for model in split["models"].values()]
    for record in records:
        for key, tolerance in (("cpu_raw_reproduction", raw_atol),
                               ("cpu_clipped_probability_reproduction", probability_atol)):
            check = record[key]
            if (not check["passed"] or check["count_above_tolerance"]
                    or check["absolute_tolerance"] != tolerance
                    or check["max_absolute_error"] > tolerance):
                raise ValueError("A numerical reproduction check failed its stated domain tolerance")
    initial_binding = final["preserved_initial_cpu_tolerance_failure"]
    precision_binding = final["precision_investigation"]
    initial_path = root / initial_binding["path"]
    precision_path = root / precision_binding["path"]
    if digest(initial_path) != initial_binding["sha256"] or digest(precision_path) != precision_binding["sha256"]:
        raise ValueError("The preserved numerical investigation artifacts changed")
    initial, precision = read_json(initial_path), read_json(precision_path)
    if (initial["result"] != "failed" or precision["outlier_count"] != 23
            or not precision["all_outliers_raw_above_one"]
            or not precision["all_outlier_clipped_probabilities_identically_one"]):
        raise ValueError("The preserved raw-only precision investigation differs from its explanation")
    return dict(result="passed", cpu_raw_absolute_tolerance=raw_atol,
                cpu_probability_absolute_tolerance=probability_atol,
                global_cpu_raw_max_absolute_error=max(row["cpu_raw_reproduction"]["max_absolute_error"] for row in records),
                global_cpu_probability_max_absolute_error=max(row["cpu_clipped_probability_reproduction"]["max_absolute_error"] for row in records),
                initial_outlier_count=precision["outlier_count"],
                all_outlier_clipped_probabilities_identically_one=True,
                exact_original_batch_mps_vs_saved_max=precision["exact_original_batch_mps_vs_saved_max"],
                outlier_cpu_float64_public_vs_center_max=precision["cpu_float64_public_vs_center_max"],
                outlier_cpu_float64_vs_saved_mps_raw_max=precision["cpu_float64_vs_saved_mps_raw_max"],
                source_hashes_verified=final["source_hashes_verified"],
                input_files=[str(final_path), str(initial_path), str(precision_path)])


def make_report(root: Path, native: dict, common: dict, values: dict, audit: dict, selected: int,
                numerical: dict | None = None, tests_passed: int | None = None) -> str:
    test_models = common["splits"]["test"]["models"]
    selected_score = test_models[f"direct_{selected}"]
    paired = test_models[f"original_{selected}"]
    change = (selected_score["brier"] / paired["brier"] - 1) * 100
    direction = "higher" if change > 0 else "lower" if change < 0 else "equal"
    common_coverage = coverage(values, native[9]["metadata"])
    lines = ["# Signed direct-convolution next-hour burn probability", "",
             f"All four signed direct models were fitted. The direct **{selected}×{selected} kernel** minimizes shared validation Brier. "
             f"On shared test targets, its Brier is **{number(selected_score['brier'])}**, "
             f"**{abs(change):.2f}% {direction}** than the frozen original {selected}×{selected} model's **{number(paired['brier'])}**. "
             "Kernel selection uses validation only; test scores are reported after that choice.", "",
             f"Its **exact test log loss is {number(selected_score['exact_negative_log_likelihood_mean'])}**. "
             f"Clipping assigns probability zero to **{whole(selected_score['unsupported_positive_sample_count'])} positive test labels** "
             f"and probability one to **{whole(selected_score['wrong_probability_one_negative_sample_count'])} negative test labels**. "
             "The Brier improvement therefore does not establish improvement across probability scoring rules.", "",
             "![Paired shared-population probability and ranking comparison](comparison_results.png)", "",
             "## Model and training objective", "",
             r"For a currently unburned target cell \(i\), let \(B_{i+\delta}(t)\in\{0,1\}\) identify "
             "current cumulative burned source cells. The environmental neural network generates signed kernel coefficients "
             r"\(a_{i,\delta}\in\mathbb R\); the center coefficient is masked to zero. The raw model output is", "",
             r"$$q_i^{\mathrm{raw}}=\sum_{\delta\ne0}a_{i,\delta}B_{i+\delta}(t).$$", "",
             "The direct coefficients are dimensionless and may be negative. This raw output is an unconstrained score. "
             "There is no hazard rate, softplus coefficient constraint, exponential link, sigmoid, or learned additive output bias "
             "after the convolution. Validation, testing, and default probability inference use", "",
             r"$$q_i=\operatorname{clip}(q_i^{\mathrm{raw}},0,1).$$", "",
             "Training compares the **unclipped** raw output directly with the one-hour binary target using inverse "
             r"sampling-probability weighted squared error. For sampling weights \(s_i\), weighted training prevalence "
             r"\(\pi_{\mathrm{train}}\), and mean training weight \(\bar s\), each uniformly sampled minibatch uses", "",
             r"$$\mathcal L_{\mathrm{batch}}=\frac{1}{\pi_{\mathrm{train}}}\,"
             r"\operatorname{mean}_{i\in\mathrm{batch}}\left[\frac{s_i}{\bar s}"
             r"(q_i^{\mathrm{raw}}-y_i)^2\right].$$", "",
             "The two denominators are fixed using training data. They scale gradients without changing positive/negative "
             "relative sampling weights. No clipping enters the training gradient. The reported full-partition raw Brier "
             "omits the fixed prevalence scale; clipped training Brier is an additional descriptive check. "
             "The checkpoint minimizes **clipped native validation Brier**, with the first minimum retained. "
             "Adam, seed 7, maximum 30 epochs, patience 6, hidden width 16, batch size 2048, learning rate 0.001, "
             "and weight decay 0.0001 match the saved original runs.", "",
             "The direct model starts with zero output-layer weights and a uniform coefficient fitted on training data "
             "by unclipped weighted least squares. The original exponential-link model used its own train-fitted "
             "uniform-rate initialization. Thus initialization respects each model's own output definition rather "
             "than asserting numerically identical initial coefficients.", "",
             "## Preserved data and paired comparison", "",
             "The five continuous predictors plus fourteen fixed biome indicators give nineteen inputs. "
             "The original prepared arrays, normalization fitted on training rows, inverse inclusion weights, exact one-hour "
             "targets, and whole-fire partitions are reused. One model per kernel pools countries. "
             "The assigned partitions contain 27 training, 7 validation, and 10 test fires. Complete environmental/burned "
             "context is required, and each target must have at least one current burned neighbor inside its kernel.", "",
             "Within each kernel, direct and original native scores use **identical cache rows and weights**. "
             "Native populations still differ across kernel sizes. The shared evaluation uses the **exact saved earlier "
             "comparison cohort**, with complete 9×9 context and burned source contact in its central 3×3 support. "
             "Original probabilities are copied from the saved earlier comparison; none of the original models is refitted. "
             "The report checks every shared label, weight, event, timestamp, row, column, neighbor count, and original "
             "prediction against those earlier files.", "",
             markdown_table(["Shared partition", "Samples", "Positive sample fraction", "Represented population weight", "Weighted outcome rate", "Contributing fires"],
                            [[split, whole(len(values[split]["y"])), percent(float(values[split]["y"].mean())),
                              number(float(values[split]["w"].sum()), 2),
                              percent(common["splits"][split]["models"]["direct_3"]["weighted_prevalence"]),
                              str(len(common_coverage[split]["event_ids"]))] for split in SPLITS]), "",
             "Shared validation retains three US fires and no Korean fires under the complete-9×9-context rule. "
             "Shared test retains eight fires. These are coverage counts; scores remain pooled. "
             "The shared training-season evaluation uses the earlier common sampling design and is not the optimizer's "
             "native training loss.", "",
             "## Shared validation and test results", "",
             "Brier and exact log loss evaluate probabilities; lower is better. Average precision and ROC AUC evaluate "
             "ranking; higher is better. Every model within a partition uses one identical label and sampling-weight array.", ""]
    for split in ("validation", "test"):
        rows = []
        for kernel in KERNELS:
            for kind in ("original", "direct"):
                score = common["splits"][split]["models"][f"{kind}_{kernel}"]
                rows.append([f"{kernel}×{kernel}", "Original exponential" if kind == "original" else "Signed direct, clipped",
                             number(score["brier"]), number(score["average_precision"]), number(score["roc_auc"]),
                             number(score["exact_negative_log_likelihood_mean"]), number(score["clipped_log_loss"]),
                             percent(score["mean_probability"])])
        lines += [f"### Shared {split}", "",
                  markdown_table(["Kernel", "Model", "Brier ↓", "Average precision ↑", "ROC AUC ↑", "Exact log loss ↓", "Floor-limited log loss ↓", "Mean probability"], rows), ""]
    lines += ["The floor-limited diagnostic uses probability floor 10⁻⁷; it is different from exact log loss. "
              "Exact log loss is **∞** if any positive-weight positive target has probability zero, or any "
              "positive-weight negative target has probability one. These outcomes are counted explicitly below.", "",
              "## Raw outputs and clipping on the shared cohort", "",
              markdown_table(["Partition", "Kernel", "Raw minimum", "Raw maximum", "Raw < 0: weighted fraction", "Raw > 1: weighted fraction", "Positive targets at p = 0", "Negative targets at p = 1"],
                             [[split, f"{kernel}×{kernel}", number(audit[split]["raw_diagnostics"][str(kernel)]["raw_minimum"]),
                               number(audit[split]["raw_diagnostics"][str(kernel)]["raw_maximum"]),
                               clipping_percent(audit[split]["raw_diagnostics"][str(kernel)]["below_zero_weighted_fraction"]),
                               clipping_percent(audit[split]["raw_diagnostics"][str(kernel)]["above_one_weighted_fraction"]),
                               whole(audit[split]["raw_diagnostics"][str(kernel)]["positive_at_zero_sample_count"]),
                               whole(audit[split]["raw_diagnostics"][str(kernel)]["negative_at_one_sample_count"])]
                              for split in ("validation", "test") for kernel in KERNELS]), "",
              "Clipping fractions above use represented population weights. Counts are actual saved sample counts. "
              "For a binary target, clipping a finite raw value into [0,1] cannot increase its squared error; this "
              "fact does not ensure calibrated probabilities or finite exact log loss.", "",
              "## Native training, validation, and test results", "",
              "Each row is paired with its original kernel on the same native samples. Training optimizes the raw "
              "column; validation checkpoint selection and test probability scores use the clipped column. "
              "Rows across different kernel sizes have different eligible populations and are not direct kernel-size comparisons.", "",
              markdown_table(["Kernel", "Partition", "Samples", "Weighted outcome rate", "Original Brier ↓", "Direct raw Brier ↓", "Direct clipped Brier ↓", "Direct AP ↑", "Direct AUC ↑", "Direct exact log loss ↓"],
                             [[f"{kernel}×{kernel}", split, whole(native[kernel]["splits"][split]["direct"]["sample_count"]),
                               percent(native[kernel]["splits"][split]["direct"]["weighted_prevalence"]),
                               number(native[kernel]["splits"][split]["original"]["brier"]),
                               number(native[kernel]["splits"][split]["raw"]["raw_brier"]),
                               number(native[kernel]["splits"][split]["direct"]["brier"]),
                               number(native[kernel]["splits"][split]["direct"]["average_precision"]),
                               number(native[kernel]["splits"][split]["direct"]["roc_auc"]),
                               number(native[kernel]["splits"][split]["direct"]["exact_negative_log_likelihood_mean"])]
                              for kernel in KERNELS for split in SPLITS]), "",
              markdown_table(["Kernel", "Partition", "Raw minimum", "Raw maximum", "Raw < 0: weighted fraction", "Raw > 1: weighted fraction"],
                             [[f"{kernel}×{kernel}", split,
                               number(native[kernel]["splits"][split]["raw"]["raw_minimum"]),
                               number(native[kernel]["splits"][split]["raw"]["raw_maximum"]),
                               clipping_percent(native[kernel]["splits"][split]["raw"]["below_zero_weighted_fraction"]),
                               clipping_percent(native[kernel]["splits"][split]["raw"]["above_one_weighted_fraction"])]
                              for kernel in KERNELS for split in SPLITS]), "",
              "## Selected checkpoints and model capacity", "",
              markdown_table(["Kernel", "Parameters per model", "Direct selected epoch", "Direct completed epochs", "Training device", "Direct fitting/evaluation seconds", "Direct checkpoint"],
                             [[f"{kernel}×{kernel}", whole(321 * kernel * kernel + 16),
                               str(native[kernel]["metrics"]["selection"]["best_epoch"]),
                               str(native[kernel]["metrics"]["selection"]["epochs_completed"]),
                               str(native[kernel]["configuration"]["arguments"]["device"]),
                               number(native[kernel]["metrics"]["elapsed_seconds"], 2),
                               link("checkpoint", native[kernel]["fitted"] / "checkpoint.pt")] for kernel in KERNELS]), "",
              "Each same-size original/direct pair has the same neural-network parameter count. The different kernel sizes "
              "have different capacity and native training populations. At the verified 375 m cell size, footprint widths are "
              "1.125, 1.875, 2.625, and 3.375 km; maximum axial source-center distances are 0.375, 0.750, 1.125, and 1.500 km.", "",
              "## Interpretation and limits", "",
              "This is a controlled same-cache comparison within each kernel, with one fixed seed and no uncertainty "
              "intervals. The raw-output training loss and clipped validation criterion are deliberately different. "
              "A signed coefficient is a learned predictive contribution and has no direct physical hazard interpretation. "
              "The labels are retrospective reconstructed arrival/burned-area labels, rather than independently observed "
              "hourly ground truth. Shared kernel selection has only three retained validation fires, all US fires. "
              "Spatially and temporally dependent targets do not constitute independent repetitions.", "",
              "## Reproducible records", "",
              "This report reads saved predictions and independently recomputes weighted Brier, ranking scores, exact "
              "and floor-limited log loss, calibration, raw output ranges, and clipping fractions. It confirms paired native "
              "and shared identities/labels/weights and checks the validation-only selection. "
              "The generated report audit binds these input artifacts by SHA-256.", "",
              "- " + link("Frozen experiment protocol", root / "protocol.json"),
              "- " + link("Shared metrics", root / "common_metrics.json"),
              "- " + link("Validation-only kernel selection", root / "common_selection.json"),
              "- " + link("Report recomputation audit", root / "report_audit.json"), ""]
    if numerical is not None:
        test_text = f"The complete test suite passed **{tests_passed} tests**. " if tests_passed is not None else ""
        lines += ["## Numerical validation", "",
                  test_text + "Independent CPU verification passed for every native and shared partition. "
                  f"The largest CPU/MPS difference in **clipped probabilities** is **{numerical['global_cpu_probability_max_absolute_error']:.10g}**, "
                  f"within an absolute tolerance of **{numerical['cpu_probability_absolute_tolerance']:.0e}**. "
                  f"The largest difference in **unclipped raw scores** is **{numerical['global_cpu_raw_max_absolute_error']:.10g}**, "
                  f"within a separate absolute tolerance of **{numerical['cpu_raw_absolute_tolerance']:.0e}**. "
                  "These tolerances apply to different output domains; the probability check retains the stricter bound.", "",
                  "The preserved initial CPU audit failed its 2×10⁻⁶ raw-score tolerance on exactly **23 native 3×3 validation targets**. "
                  "Every one of these raw values is greater than one, and clipping gives **exactly one on both CPU and MPS**. "
                  f"Replaying the original MPS batches reproduces the saved raw outputs with maximum difference **{numerical['exact_original_batch_mps_vs_saved_max']:.0f}**. "
                  f"For those 23 targets, CPU float64 public and independent center calculations agree within **{numerical['outlier_cpu_float64_public_vs_center_max']:.10g}**, "
                  f"and their raw difference from saved MPS is at most **{numerical['outlier_cpu_float64_vs_saved_mps_raw_max']:.10g}**. "
                  "No parameters, saved predictions, or probability scores were changed to obtain the final verification. "
                  f"All **{numerical['source_hashes_verified']} source-file hashes**, the training-code bindings, and original checkpoints remain verified.", "",
                  "- " + link("Final verification with separate raw and probability tolerances", root / "verification_separate_tolerances.json"),
                  "- " + link("Preserved initial raw-tolerance failure", root / "verification.json"),
                  "- " + link("Independent precision investigation", root / "cpu_precision_audit.json"), ""]
    return "\n".join(lines)


def generate(root: Path, original_sweep: Path, original3: Path, tests_passed: int | None = None) -> dict:
    root, original_sweep, original3 = root.resolve(), original_sweep.resolve(), original3.resolve()
    originals = native_original_runs(original_sweep, original3)
    native = load_native(root, originals)
    common, values, common_audit, selected = load_common(root, original_sweep)
    numerical = numerical_verification(root)
    # Finish all checks before writing the report or figure.
    make_figure(root / "comparison_results.png", common, values, selected)
    report = make_report(root, native, common, values, common_audit, selected, numerical, tests_passed)
    inputs = [root / "protocol.json", root / "common_metrics.json", root / "common_selection.json", Path(__file__).resolve()]
    if numerical is not None:
        inputs += [Path(path) for path in numerical["input_files"]]
    for split in SPLITS:
        inputs += [root / "common_predictions" / f"{split}.npz", original_sweep / "common_predictions" / f"{split}.npz"]
    for kernel in KERNELS:
        fitted = root / f"{kernel}x{kernel}" / "fitted"
        inputs += [fitted / name for name in ("checkpoint.pt", "configuration.json", "history.json", "metrics.json")]
        inputs += [fitted / f"{split}_predictions.npz" for split in SPLITS]
        inputs += [originals[kernel] / "prepared/metadata.json"]
        inputs += [originals[kernel] / "fitted" / name for name in ("metrics.json", "configuration.json")]
        inputs += [originals[kernel] / "fitted" / f"{split}_predictions.npz" for split in SPLITS]
    audit = dict(result="passed", fitting_performed=False, selected_direct_kernel_size=selected,
                 selection_uses_only_validation=True, native_paired_population_verified=True,
                 exact_saved_original_common_population_verified=True,
                 original_common_predictions_preserved_exactly=True,
                 numerical_verification=numerical,
                 test_suite_passed_count=tests_passed,
                 shared_recomputed=common_audit,
                 native_recomputed={str(kernel): entry["splits"] for kernel, entry in native.items()},
                 input_sha256={str(path): digest(path) for path in inputs})
    (root / "report_audit.json").write_text(json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (root / "comparison_report.md").write_text(report, encoding="utf-8")
    return dict(result="passed", report=str(root / "comparison_report.md"),
                figure=str(root / "comparison_results.png"), selected_direct_kernel_size=selected)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--original-sweep", type=Path, required=True)
    parser.add_argument("--original-3-run", type=Path, required=True)
    parser.add_argument("--tests-passed", type=int,
                        help="Completed test-suite count supplied from the separate executed suite")
    args = parser.parse_args()
    print(json.dumps(generate(args.run_root, args.original_sweep, args.original_3_run, args.tests_passed), indent=2), flush=True)


if __name__ == "__main__":
    main()
