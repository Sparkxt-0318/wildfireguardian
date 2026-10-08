"""Report a broader-kernel comparison from saved predictions without fitting.

Native runs have different eligible populations. The separate common cohort
must contain the same labels and weights for every model within each split.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from .report_training import (SPLITS, kernel_geometry, link,
                              markdown_table, number, percent, precision_recall,
                              read_json, score, whole)
from .metrics import probability_metrics, weighted_calibration

# report_training configures a disposable Matplotlib cache and the Agg backend.
import matplotlib.pyplot as plt


KERNELS = (3, 5, 7, 9)
COLORS = {3: "#1769aa", 5: "#dd871f", 7: "#37925e", 9: "#a25ca0"}


def load_native_runs(run_dirs: list[Path]) -> dict[int, dict]:
    runs = {}
    for directory in run_dirs:
        run = directory.resolve()
        metadata = read_json(run / "prepared/metadata.json")
        metrics = read_json(run / "fitted/metrics.json")
        history = read_json(run / "fitted/history.json")
        configuration = read_json(run / "fitted/configuration.json")
        kernel, _, _ = kernel_geometry(metadata, metrics)
        if kernel in runs:
            raise ValueError(f"Duplicate {kernel}×{kernel} native run")
        if metrics["selection"]["test_used_for_selection"]:
            raise ValueError("A native checkpoint used test data for selection")
        if min(history, key=lambda entry: entry["validation_brier"])["epoch"] != metrics["selection"]["best_epoch"]:
            raise ValueError("A native checkpoint is not the minimum validation Brier epoch")
        digest = hashlib.sha256((run / "prepared/metadata.json").read_bytes()).hexdigest()
        if digest != metrics["contract"]["cache_metadata_sha256"]:
            raise ValueError("A native prepared-data manifest differs from the fitting contract")
        runs[kernel] = dict(run=run, metadata=metadata, metrics=metrics,
                            history=history, configuration=configuration)
    if set(runs) != set(KERNELS):
        raise ValueError("The comparison requires exactly one native run for each of 3, 5, 7, and 9")
    reference = runs[9]["metrics"]["contract"]
    for entry in runs.values():
        contract = entry["metrics"]["contract"]
        for key in ("channels", "in_channels", "hidden_channels", "dt_hours", "center_rate", "splits", "eligibility"):
            if contract[key] != reference[key]:
                raise ValueError(f"Native runs disagree on the preserved {key} contract")
        for key in ("source_channels", "categorical_encoding", "categorical_classes", "channel_groups"):
            if contract.get(key) != reference.get(key):
                raise ValueError(f"Native runs disagree on the preserved {key} representation")
        if contract.get("evaluation_grouping") != "pooled_countries":
            raise ValueError("The comparison requires pooled-country evaluation")
    return runs


def _compare_metrics(actual: dict, recorded: dict, label: str):
    for key, value in actual.items():
        if key not in recorded:
            raise ValueError(f"Missing {key} metric in {label}")
        saved = recorded[key]
        if value is None or isinstance(value, str):
            if saved != value:
                raise ValueError(f"Stored {key} differs from predictions in {label}")
        elif not np.isclose(value, saved, rtol=0, atol=1e-10):
            raise ValueError(f"Stored {key} differs from predictions in {label}")


def validate_common_results(common: dict, predictions_dir: Path) -> tuple[dict, int]:
    """Recompute every common-cohort score from one shared label/weight array."""
    predictions = {}
    for split in SPLITS:
        with np.load(predictions_dir / f"{split}.npz", allow_pickle=False) as archive:
            values = {name: archive[name] for name in archive.files}
        y, weight = values["y"], values["w"]
        if (y.ndim != 1 or weight.shape != y.shape or len(y) == 0
                or not np.isin(y, [0, 1]).all() or not np.isfinite(weight).all()
                or not (weight > 0).all()):
            raise ValueError(f"Invalid common labels or sampling weights in {split}")
        for key in ("event_index", "time_utc", "row", "col"):
            if values[key].shape != y.shape:
                raise ValueError(f"Common cell-hour identity array {key} has the wrong shape")
        identities = np.rec.fromarrays([values[key] for key in ("event_index", "time_utc", "row", "col")])
        if len(np.unique(identities)) != len(y):
            raise ValueError(f"Repeated common cell-hour identity in {split}")
        if not (values["neighbor_count_3"] > 0).all():
            raise ValueError(f"The common {split} contains a target without a 3×3 burned neighbor")
        previous_neighbors = None
        for kernel in KERNELS:
            key = str(kernel)
            probability = values[f"p_{kernel}"]
            neighbors = values[f"neighbor_count_{kernel}"]
            if (probability.shape != y.shape or not np.isfinite(probability).all()
                    or not ((probability >= 0) & (probability <= 1)).all()
                    or neighbors.shape != y.shape or not (neighbors > 0).all()):
                raise ValueError(f"Invalid common predictions for {kernel}×{kernel} in {split}")
            if previous_neighbors is not None and (neighbors < previous_neighbors).any():
                raise ValueError("Larger centered kernels cannot lose known burned neighbors")
            previous_neighbors = neighbors
            _compare_metrics(probability_metrics(y, probability, weight, neighbors),
                             common["splits"][split]["models"][key], f"{split}/{kernel}")
            calibration = weighted_calibration(y, probability, weight)
            recorded_calibration = common["splits"][split]["calibration"][key]
            for actual_bin, recorded_bin in zip(calibration["bins"], recorded_calibration["bins"], strict=True):
                _compare_metrics(actual_bin, recorded_bin, f"{split}/{kernel} calibration")
            if not np.isclose(calibration["weighted_expected_calibration_error"],
                              recorded_calibration["weighted_expected_calibration_error"], rtol=0, atol=1e-12):
                raise ValueError("Stored common calibration error differs from predictions")
        baselines = common["splits"][split].get("baselines", {})
        for label, recorded in baselines.items():
            if label == "zero":
                probability = np.zeros_like(y)
                neighbors = values["neighbor_count_9"]
            elif label.startswith("uniform_") and int(label.removeprefix("uniform_")) in KERNELS:
                probability = values[label]
                neighbors = values[f"neighbor_count_{label.removeprefix('uniform_')}"]
            else:
                raise ValueError(f"Unknown common baseline {label}")
            if (probability.shape != y.shape or not np.isfinite(probability).all()
                    or not ((probability >= 0) & (probability <= 1)).all()):
                raise ValueError(f"Invalid common baseline predictions in {split}/{label}")
            _compare_metrics(probability_metrics(y, probability, weight, neighbors), recorded, f"{split}/{label}")
        predictions[split] = values
    selected = min(KERNELS, key=lambda kernel: common["splits"]["validation"]["models"][str(kernel)]["brier"])
    selection = common.get("selection", {})
    for key in ("selected_kernel_size", "kernel_size", "best_kernel_size"):
        if key in selection and selection[key] != selected:
            raise ValueError("Saved kernel selection disagrees with common validation Brier")
    if selection.get("test_used_for_selection", False):
        raise ValueError("Kernel size selection used test data")
    return predictions, selected


def _common(common: dict, split: str, kernel: int) -> dict:
    return common["splits"][split]["models"][str(kernel)]


def common_fire_coverage(native: dict, common: dict, predictions_dir: Path) -> dict:
    """Count retained fire identities using the saved event/country manifest."""
    metadata = native[9]["metadata"]
    events = metadata["event_ids"]
    event_info = {entry["id"]: entry for entry in metadata["per_event"]}
    coverage = {}
    for split in SPLITS:
        with np.load(predictions_dir / f"{split}.npz", allow_pickle=False) as archive:
            indices = np.unique(archive["event_index"])
        if not np.issubdtype(indices.dtype, np.integer) or (indices < 0).any() or (indices >= len(events)).any():
            raise ValueError("Common-cohort event indices do not match the event manifest")
        retained = [events[index] for index in indices]
        if any(metadata["splits"][event] != split for event in retained):
            raise ValueError("A common-cohort fire belongs to another partition")
        if common["splits"][split].get("contributing_events", len(retained)) != len(retained):
            raise ValueError("Recorded common-cohort contributing fire count disagrees with saved identities")
        countries = {}
        for event in retained:
            country = event_info[event]["country"]
            countries[country] = countries.get(country, 0) + 1
        coverage[split] = dict(events=len(retained), countries=countries)
    return coverage


def create_comparison_figure(path: Path, common: dict, predictions: dict, selected: int):
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 12, "axes.labelsize": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.4), layout="constrained")
    position = np.arange(len(KERNELS))
    for shift, split, color in ((-.18, "validation", "#5b8fb9"), (.18, "test", "#d49043")):
        scores = [_common(common, split, kernel)["brier"] for kernel in KERNELS]
        bars = axes[0].bar(position + shift, scores, .36, label=split.capitalize(), color=color)
        axes[0].bar_label(bars, labels=[f"{value:.4f}" for value in scores], padding=3, fontsize=8, rotation=45)
    axes[0].set_xticks(position, [f"{kernel}×{kernel}" for kernel in KERNELS])
    axes[0].set(title="Same cohort within each partition", xlabel="Kernel size", ylabel="Weighted Brier (lower is better)")
    maximum = max(_common(common, split, kernel)["brier"] for split in ("validation", "test") for kernel in KERNELS)
    axes[0].set_ylim(0, maximum * 1.22)
    axes[0].legend(frameon=False, fontsize=9)
    axes[0].grid(axis="y", alpha=.2)
    axes[0].set_axisbelow(True)
    axes[0].text(.02, .98, f"Validation selected {selected}×{selected}", transform=axes[0].transAxes, va="top", fontsize=9)

    test = predictions["test"]
    for kernel in KERNELS:
        recall, precision, ap = precision_recall(test["y"], test[f"p_{kernel}"], test["w"])
        axes[1].step(recall, precision, where="pre", linewidth=1.3, color=COLORS[kernel],
                     label=f"{kernel}×{kernel}: AP {ap:.3f}")
    prevalence = _common(common, "test", 3)["weighted_prevalence"]
    axes[1].axhline(prevalence, color="#777777", linestyle="--", linewidth=1,
                   label=f"Outcome rate {prevalence:.3f}")
    axes[1].set(title="Common pooled test precision–recall", xlabel="Recall", ylabel="Precision",
                xlim=(0, 1), ylim=(0, 1.01))
    axes[1].legend(frameon=False, fontsize=8, loc="upper right")
    axes[1].grid(alpha=.2)

    nonempty = {}
    for kernel in KERNELS:
        bins = common["splits"]["test"]["calibration"][str(kernel)]["bins"]
        nonempty[kernel] = [entry for entry in bins if entry["sample_count"]]
    limit = min(100, max(10, 1.12 * max(max(entry["mean_probability"], entry["weighted_outcome_rate"]) * 100
                                     for bins in nonempty.values() for entry in bins)))
    axes[2].plot([0, limit], [0, limit], linestyle="--", color="#777777", linewidth=1)
    for kernel in KERNELS:
        bins = nonempty[kernel]
        axes[2].plot([entry["mean_probability"] * 100 for entry in bins],
                     [entry["weighted_outcome_rate"] * 100 for entry in bins], marker="o", markersize=4,
                     linewidth=1, color=COLORS[kernel], label=f"{kernel}×{kernel}")
    axes[2].set(title="Common pooled test reliability", xlabel="Bin mean predicted probability (%)",
                ylabel="Bin weighted outcome rate (%)", xlim=(0, limit), ylim=(0, limit))
    axes[2].legend(frameon=False, fontsize=9, loc="lower right")
    axes[2].grid(alpha=.2)
    fig.suptitle("Next-hour burn probability: broader kernels on a common cohort", fontsize=16)
    fig.supxlabel("One label and sampling-weight array per partition; native training populations differ across kernel sizes.", fontsize=10)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def create_comparison_report(output: Path, native: dict, common: dict, selected: int, common_path: Path,
                             predictions_dir: Path) -> str:
    chosen = _common(common, "test", selected)
    original = _common(common, "test", 3)
    relative = 100 * (original["brier"] - chosen["brier"]) / original["brier"]
    reference = native[9]["metrics"]["contract"]
    channels, hidden = reference["in_channels"], reference["hidden_channels"]
    coverage = common_fire_coverage(native, common, predictions_dir)
    split_labels = {"train": "Training-season evaluation", "validation": "Validation", "test": "Test"}
    country_names = {"KR": "Korean", "US": "US"}
    coverage_description = "; ".join(
        f"{split_labels[split].lower()}: {coverage[split]['events']} fires "
        "(" + ", ".join(f"{coverage[split]['countries'].get(country, 0)} {country_names[country]}" for country in ("KR", "US")) + ")"
        for split in SPLITS)
    lines = ["# Broader-kernel next-hour burn probability comparison", "",
             f"**{selected}×{selected} was selected using the lowest common-cohort validation Brier score.** "
             f"Its common held-out test Brier is **{chosen['brier']:.6f}**, versus **{original['brier']:.6f}** "
             f"for the previously fitted 3×3 model ({abs(relative):.3f}% {'lower' if relative >= 0 else 'higher'}). "
             "Kernel size and training epoch were selected without test outcomes. All test results below are descriptive held-out comparisons.", "",
             "The 5×5, 7×7, and 9×9 models were newly fitted. The saved 3×3 model was loaded as the reference. "
             "One shared model per kernel pools the countries. Each uses the former five continuous predictors and 14 one-hot biome indicators, "
             f"{hidden} hidden channels, a complete current environmental neighborhood, nonnegative position-dependent rates, zero central rate, "
             "and the exact one-hour-later reconstructed burn target. Whole-fire partition assignments and the sampling-weighted Brier objective were retained.", "",
             "## Comparison populations and selection", "",
             "The common cohort starts from the 9×9 native prepared sample in each partition and retains targets with at least one already burned "
             "neighbor inside the central 3×3 neighborhood. Complete known 9×9 context makes every smaller centered patch known as well. "
             "All four models receive the same cell-hour identities, labels, and original 9×9 inverse inclusion-probability weights. "
             "The smaller patches are centered crops. Selection uses current context validity and current burned-neighbor contact; it does not use next-hour outcomes. "
             "Independently sampled native caches are not intersected.", "",
             "The common-cohort weights estimate the subset of the 9×9 eligible population that also has a 3×3 burned neighbor. "
             "Negative weights remain the 9×9 negative stratum's candidate count divided by its sampled count; positive weights remain one. "
             "These scores are sampling estimates, not an exhaustive full-grid census. Native training, normalization, baseline fitting, "
             "and checkpoint epoch selection still use each kernel's own eligible population. The common validation cohort selects only the kernel size. "
             "Thus this comparison measures the resulting trained systems on fixed evaluation targets; it does not isolate kernel geometry from changes in training population or model capacity.", "",
             markdown_table(["Common partition", "Contributing fires", "Samples", "Positive samples", "Sample positive fraction", "Represented cell-hours", "Weighted outcome rate"],
                            [[split_labels[split], whole(coverage[split]["events"]), whole(_common(common, split, 3)["sample_count"]),
                              whole(_common(common, split, 3)["positive_sample_count"]),
                              percent(_common(common, split, 3)["sample_positive_fraction"]),
                              whole(_common(common, split, 3)["represented_population_weight"]),
                              percent(_common(common, split, 3)["weighted_prevalence"])] for split in SPLITS]), "",
             f"All {len(native[9]['metadata']['event_ids'])} fires remain in the original partition allocation, with one pooled model per kernel. "
             f"The common-cohort context and contact requirements leave {coverage_description}. "
             "These counts describe coverage; the model fits and score tables remain pooled across countries. "
             "The training-season row is a post-fit evaluation of the common subset; optimization used each model's native training cache.", "",
             "The sampled positive fraction is changed by negative subsampling. The weighted outcome rate describes the represented population. "
             "Training and every evaluation retain the inverse inclusion weights; no class-dependent balancing was added. "
             "Dividing the training objective by weighted training prevalence is one common factor for both label classes.", "",
             "## Kernel support and parameter counts", ""]
    if coverage["validation"]["countries"].get("KR", 0) == 0:
        insertion = lines.index("## Kernel support and parameter counts")
        lines[insertion:insertion] = [
            "No Korean fire contributes to common validation after the complete 9×9 context and central 3×3 contact requirements. "
            "Kernel-size selection therefore has direct validation evidence only from the retained US fires. "
            "This coverage restriction limits the interpretation of the pooled kernel choice, including its transfer to Korean fires.", ""]
    spacing = native[9]["metadata"].get("grid_resolution_m")
    headers = ["Kernel", "Environmental positions", "Burned-source offsets", "Axial radius (cells)", "Trainable parameters"]
    if spacing is not None:
        headers += ["Square side (m)", "Axial source-center radius (m)", "Diagonal source-center radius (m)"]
    rows = []
    for kernel in KERNELS:
        radius = kernel // 2
        parameters = hidden * channels * kernel * kernel + hidden + hidden * kernel * kernel + kernel * kernel
        row = [f"{kernel}×{kernel}", str(kernel * kernel), str(kernel * kernel - 1), str(radius), whole(parameters)]
        if spacing is not None:
            row += [number(kernel * spacing, 0), number(radius * spacing, 0), number(np.sqrt(2) * radius * spacing, 1)]
        rows.append(row)
    lines += [markdown_table(headers, rows), "",
              "The output has one rate per offset, including the fixed-zero center. Parameter counts include both convolution layers and their biases; "
              "the zero-center mask is a buffer. Enlarging the first convolution and output layer increases capacity despite keeping the hidden width fixed. "
              "The model grid's physical support does not establish the environmental sources' native spatial resolution.", "",
              "## Common validation scores used to choose kernel size", "",
              markdown_table(["Kernel", "Selected epoch in native training", "Common validation Brier ↓", "Average precision ↑", "ROC AUC ↑", "Exact log loss ↓"],
                             [[f"{kernel}×{kernel}" + (" **selected**" if kernel == selected else ""),
                               str(native[kernel]["metrics"]["selection"]["best_epoch"]),
                               number(_common(common, "validation", kernel)["brier"]),
                               number(_common(common, "validation", kernel)["average_precision"]),
                               number(_common(common, "validation", kernel)["roc_auc"]),
                               number(_common(common, "validation", kernel)["exact_negative_log_likelihood_mean"])] for kernel in KERNELS]), "",
              "## Common held-out test scores", "",
              markdown_table(["Kernel", "Brier ↓", "Average precision ↑", "ROC AUC ↑", "Exact log loss ↓", "Mean probability", "Weighted outcome rate", "Weighted calibration error"],
                             [[f"{kernel}×{kernel}", number(_common(common, "test", kernel)["brier"]),
                               number(_common(common, "test", kernel)["average_precision"]),
                               number(_common(common, "test", kernel)["roc_auc"]),
                               number(_common(common, "test", kernel)["exact_negative_log_likelihood_mean"]),
                               percent(_common(common, "test", kernel)["mean_probability"]),
                               percent(_common(common, "test", kernel)["weighted_prevalence"]),
                               number(common["splits"]["test"]["calibration"][str(kernel)]["weighted_expected_calibration_error"])] for kernel in KERNELS]), "",
              "Brier is a proper probability score, the weighted mean of squared probability errors. Exact log loss is another proper score; "
              "it is infinite when a positive outcome is assigned probability zero or a negative outcome probability one. "
              "Average precision summarizes the weighted precision–recall curve and is not classification accuracy. ROC AUC summarizes ranking. "
              "Calibration error is the fixed-bin weighted average absolute difference between mean probability and outcome rate; "
              "it depends on the specified bins and is not an uncertainty interval.", "",
              markdown_table(["Kernel", "Positive-target squared error ↓", "Negative-target squared error ↓"],
                             [[f"{kernel}×{kernel}", number(_common(common, "test", kernel)["positive_class_brier"]),
                               number(_common(common, "test", kernel)["negative_class_brier"])] for kernel in KERNELS]), "",
              "Overall Brier equals weighted outcome rate × positive-target error plus (1 − weighted outcome rate) × negative-target error. "
              "These separate errors expose the label imbalance without replacing the population objective.", "",
              f"![Common validation and test Brier, common pooled test precision–recall, and common pooled test reliability]({output / 'kernel_comparison.png'})", ""]
    baselines = common["splits"]["test"].get("baselines", {})
    if baselines:
        baseline_order = [f"uniform_{kernel}" for kernel in KERNELS if f"uniform_{kernel}" in baselines]
        if "zero" in baselines:
            baseline_order.append("zero")
        lines += ["## Common held-out test baselines", "",
                  markdown_table(["Baseline", "Brier ↓", "Average precision ↑", "ROC AUC ↑", "Exact log loss ↓", "Mean probability"],
                                 [[("Always zero" if name == "zero" else f"One fitted {name.removeprefix('uniform_')}×{name.removeprefix('uniform_')} neighbor rate"),
                                   number(baselines[name]["brier"]), number(baselines[name]["average_precision"]),
                                   number(baselines[name]["roc_auc"]), number(baselines[name]["exact_negative_log_likelihood_mean"]),
                                   percent(baselines[name]["mean_probability"])] for name in baseline_order]), "",
                  "Each uniform baseline uses the per-neighbor rate fitted only on its own native training population, "
                  "then applies that rate to the common-cohort burned-neighbor count within its kernel. No baseline parameters were fitted on common validation or test. "
                  "The zero model has infinite exact log loss whenever positive outcomes exist.", ""]
    lines += ["## Each kernel's own native population", "",
              "The following scores describe different eligibility conditions. A native K×K population requires an already burned neighbor inside K×K "
              "and complete K×K current context. Broader kernels can admit more distant cells while rejecting more edge or missing-context cells. "
              "Their outcome rates and sampling weights therefore differ. Raw native-score differences do not measure a paired improvement.", ""]
    for split in SPLITS:
        lines += [f"### {split.capitalize()}", "",
                  markdown_table(["Kernel", "Assigned / contributing fires", "Samples", "Positive samples", "Represented cell-hours", "Weighted outcome rate", "Brier ↓", "Average precision ↑", "ROC AUC ↑", "Exact log loss ↓"],
                                 [[f"{kernel}×{kernel}",
                                   f"{native[kernel]['metadata']['split_summary'][split]['events']} / {native[kernel]['metadata']['split_summary'][split]['contributing_events']}",
                                   whole(score(native[kernel]["metrics"], split)["sample_count"]),
                                   whole(score(native[kernel]["metrics"], split)["positive_sample_count"]),
                                   whole(score(native[kernel]["metrics"], split)["represented_population_weight"]),
                                   percent(score(native[kernel]["metrics"], split)["weighted_prevalence"]),
                                   number(score(native[kernel]["metrics"], split)["brier"]),
                                   number(score(native[kernel]["metrics"], split)["average_precision"]),
                                   number(score(native[kernel]["metrics"], split)["roc_auc"]),
                                   number(score(native[kernel]["metrics"], split)["exact_negative_log_likelihood_mean"])] for kernel in KERNELS]), ""]
    lines += ["## Limits and saved evidence", "",
              "These are retrospective reconstructed arrival-time labels inside final fire perimeters, not independently observed hourly burned-cell labels. "
              "The current burned map is cumulative and does not identify an active flame front. The contact condition excludes isolated ignitions. "
              "One fixed seed was used for each model, and no confidence intervals or formal significance tests were computed. "
              "The held-out scores do not establish prospective operational forecast accuracy.", "",
              "The report and figure were generated from saved probabilities without fitting. The report generator independently recomputes common-cohort "
              "Brier, ranking, exact and clipped log loss, class-conditional errors, and calibration bins. It checks probability bounds, positive sampling weights, "
              "unique cell-hour identities, nested neighbor counts, unchanged input/split contracts, and validation-only kernel selection.", "",
              f"- {link('Common-cohort metrics and selection', common_path)}",
              f"- {link('Common-cohort saved predictions', predictions_dir)}",
              f"- {link('Comparison figure', output / 'kernel_comparison.png')}"]
    for kernel in KERNELS:
        run = native[kernel]["run"]
        lines += [f"- {link(f'{kernel}×{kernel} native report', run / 'report.md')}",
                  f"- {link(f'{kernel}×{kernel} fitted checkpoint', run / 'fitted/checkpoint.pt')}"]
    if (output / "comparison_audit.json").exists():
        lines.append(f"- {link('Independent source, label, sampling-weight, and comparison audit', output / 'comparison_audit.json')}")
    lines += ["", "Historical run artifacts are preserved. This report creates no new model weights.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, action="append", required=True)
    parser.add_argument("--common-metrics", type=Path, required=True)
    parser.add_argument("--common-predictions-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    common_path = args.common_metrics.resolve()
    predictions_dir = (args.common_predictions_dir or common_path.parent / "common_predictions").resolve()
    native = load_native_runs(args.run_dir)
    common = read_json(common_path)
    predictions, selected = validate_common_results(common, predictions_dir)
    create_comparison_figure(output / "kernel_comparison.png", common, predictions, selected)
    report = output / "comparison_report.md"
    report.write_text(create_comparison_report(output, native, common, selected, common_path, predictions_dir), encoding="utf-8")
    print(json.dumps(dict(report=str(report), figure=str(output / "kernel_comparison.png"),
                          selected_kernel_size=selected, refit=False), indent=2), flush=True)


if __name__ == "__main__":
    main()
