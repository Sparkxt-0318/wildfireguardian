"""Create a contact-conditioned training report from saved results, without fitting.

Usage: python -m wildfire_burned_area_hourly.probability_model.report_training
--run-dir wildfire_burned_area_hourly/probability_model/training_runs/RUN
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np

# Keep Matplotlib's disposable cache outside the repository.
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/wildfire_probability_matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


SPLITS = ("train", "validation", "test")
MODELS = ("zero", "train_marginal", "global_neighbor_rate", "learned_environment_kernel")
MODEL_LABELS = {
    "zero": "Always zero",
    "train_marginal": "Training marginal probability",
    "global_neighbor_rate": "One fitted rate per burned neighbor",
    "learned_environment_kernel": "Learned environmental kernel",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def score(metrics: dict, split: str, model: str = "learned_environment_kernel") -> dict:
    return metrics["splits"][split]["models"][model]["all_eligible"]


def number(value, digits=6):
    if value is None:
        return "unavailable"
    if isinstance(value, str):
        return "∞" if value == "infinity" else value
    return f"{value:.{digits}f}"


def percent(value):
    return f"{100 * value:.3f}%"


def whole(value):
    return f"{round(value):,}"


def link(label: str, path: Path) -> str:
    return f"[{label}](<{path.resolve()}>)"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    return "\n".join(["| " + " | ".join(headers) + " |",
                       "| " + " | ".join(["---"] * len(headers)) + " |"]
                      + ["| " + " | ".join(row) + " |" for row in rows])


def channel_representation(metadata: dict) -> list[str]:
    """Describe the saved input schema; legacy caches need only channel names."""
    channels = metadata["channels"]
    info = metadata.get("channel_info")
    if info is None:
        return []
    if len(info) != len(channels):
        raise ValueError("Channel representation metadata does not match the input channel count")
    for name, entry in zip(channels, info):
        if entry.get("name", name) != name:
            raise ValueError("Channel representation metadata does not match the input channel order")
    source_channels = metadata.get("source_channels", list(dict.fromkeys(entry["source_channel"] for entry in info)))
    one_hot = [entry for entry in info if entry.get("encoding") == "one_hot"]
    continuous = [entry for entry in info if entry.get("encoding") == "continuous"]
    lines = ["", f"The {len(source_channels)} source fields produce {len(channels)} ordered model inputs: "
             f"{len(continuous)} continuous channels and {len(one_hot)} one-hot indicator channels.", ""]
    groups = metadata.get("channel_groups", {})
    rows = []
    for source in source_channels:
        indices = groups.get(source, [index for index, entry in enumerate(info) if entry["source_channel"] == source])
        entries = [info[index] for index in indices]
        encodings = sorted({entry["encoding"] for entry in entries})
        rows.append([f"`{source}`", ", ".join(str(index + 1) for index in indices), ", ".join(encodings)])
    lines += [markdown_table(["Source field", "Model input positions (one-based)", "Representation"], rows), ""]
    if one_hot:
        lines += ["The categorical vocabulary and output order are fixed in the saved schema. "
                  "Each observed categorical source value is represented by exactly one indicator equal to one and all other indicators equal to zero; "
                  "unavailable source values remain invalid. The model therefore reads binary indicators rather than the numeric class codes.", "",
                  markdown_table(["Indicator input", "Source class code", "Class name"],
                                 [[f"`{entry['name']}`", str(entry["class_code"]), str(entry.get("class_name", entry["class_code"]))]
                                  for entry in one_hot]), "",
                  "These binary indicators are standardized with training-only weighted means and scales before entering the network, "
                  "using the same normalization method as the continuous channels. Channels constant in training use a scale of one."]
    return lines


def kernel_geometry(metadata: dict, metrics: dict) -> tuple[int, int, str]:
    """Read the fitted support, refusing a cache/checkpoint mismatch."""
    kernel_size = metrics["contract"]["kernel_size"]
    if (not isinstance(kernel_size, int) or isinstance(kernel_size, bool)
            or kernel_size < 3 or kernel_size % 2 != 1
            or metadata.get("kernel_size") != kernel_size):
        raise ValueError("Prepared and fitted kernel sizes must agree and be odd integers >= 3")
    radius = kernel_size // 2
    spacing = metadata.get("grid_resolution_m")
    geometry = (f"The square support contains {kernel_size * kernel_size} environmental positions and "
                f"{kernel_size * kernel_size - 1} possible burned-source offsets, extending {radius} grid {'cell' if radius == 1 else 'cells'} "
                "from the target center along each grid axis.")
    if spacing is not None:
        if (not isinstance(spacing, (int, float)) or isinstance(spacing, bool)
                or not np.isfinite(spacing) or spacing <= 0):
            raise ValueError("grid_resolution_m must be a finite positive scalar")
        geometry += (f" At the saved {spacing:g} m grid spacing, the square footprint is "
                     f"{kernel_size * spacing:g} m on each side. The largest axial source-center offset is "
                     f"{radius * spacing:g} m, and the largest diagonal source-center distance is "
                     f"{np.sqrt(2) * radius * spacing:.1f} m. These distances describe the model grid; "
                     "resampling does not give the source environmental products this spatial resolution.")
    return kernel_size, radius, geometry


def precision_recall(target: np.ndarray, prediction: np.ndarray, weight: np.ndarray):
    """Exact weighted threshold curve; tied probabilities share a threshold."""
    order = np.argsort(-prediction, kind="stable")
    p, y, w = prediction[order], target[order], weight[order]
    last = np.r_[np.flatnonzero(np.diff(p)), len(order) - 1]
    tp = np.cumsum(w * y, dtype=np.float64)[last]
    fp = np.cumsum(w * (1 - y), dtype=np.float64)[last]
    positive_weight = float(np.dot(weight, target))
    if positive_weight <= 0:
        raise ValueError("A precision-recall curve requires a positive target")
    recall = tp / positive_weight
    precision = tp / (tp + fp)
    ap = float(np.dot(np.diff(np.r_[0.0, recall]), precision))
    return np.r_[0.0, recall], np.r_[precision[0], precision], ap


def validate_saved_results(run: Path, metadata: dict, metrics: dict, history: list):
    kernel_geometry(metadata, metrics)
    if metadata.get("eligibility") != "at_least_one_burned_neighbor":
        raise ValueError("This report requires the user-requested contact-only cache")
    if metrics["contract"].get("eligibility") != metadata["eligibility"]:
        raise ValueError("Fitted checkpoint contract and prepared eligibility disagree")
    actual_hash = hashlib.sha256((run / "prepared" / "metadata.json").read_bytes()).hexdigest()
    if actual_hash != metrics["contract"]["cache_metadata_sha256"]:
        raise ValueError("The prepared metadata differs from the metadata used for fitting")
    if not history or metrics["selection"]["test_used_for_selection"]:
        raise ValueError("The training history or held-out test contract is invalid")
    best = min(history, key=lambda item: item["validation_brier"])
    if best["epoch"] != metrics["selection"]["best_epoch"]:
        raise ValueError("The selected checkpoint is not the validation Brier minimum")
    predictions = {}
    for split in SPLITS:
        path = run / "fitted" / f"{split}_predictions.npz"
        with np.load(path, allow_pickle=False) as archive:
            values = {key: archive[key] for key in archive.files}
        if not (values["neighbor_count"] > 0).all():
            raise ValueError(f"No-contact targets remain in the {split} predictions")
        recorded = score(metrics, split)
        if len(values["y"]) != recorded["sample_count"]:
            raise ValueError(f"Sample count mismatch in {split}")
        if int(values["y"].sum()) != recorded["positive_sample_count"]:
            raise ValueError(f"Positive target count mismatch in {split}")
        if not np.isclose(values["w"].sum(), recorded["represented_population_weight"], rtol=0, atol=1e-6):
            raise ValueError(f"Represented population weight mismatch in {split}")
        residual = values["p"].astype(np.float64) - values["y"]
        actual_brier = float(np.dot(values["w"], residual * residual) / values["w"].sum())
        if not np.isclose(actual_brier, recorded["brier"], rtol=0, atol=1e-12):
            raise ValueError(f"Saved prediction Brier mismatch in {split}")
        calibration = metrics["splits"][split].get("calibration")
        if calibration is not None:
            probability = values["p"].astype(np.float64)
            covered = np.zeros(len(values["y"]), dtype=bool)
            total_weight = float(values["w"].sum(dtype=np.float64))
            absolute_error = 0.0
            for entry in calibration["bins"]:
                selected = probability >= entry["lower"]
                selected &= (probability <= entry["upper"] if entry["upper_inclusive"]
                             else probability < entry["upper"])
                if np.any(covered & selected):
                    raise ValueError(f"Overlapping calibration bins in {split}")
                covered |= selected
                population = float(values["w"][selected].sum(dtype=np.float64))
                if (int(selected.sum()) != entry["sample_count"]
                        or int(values["y"][selected].sum()) != entry["positive_sample_count"]
                        or not np.isclose(population, entry["represented_population_weight"], rtol=0, atol=1e-6)):
                    raise ValueError(f"Calibration bin population mismatch in {split}")
                if population:
                    mean_p = float(np.dot(values["w"][selected], values["p"][selected]) / population)
                    outcome = float(np.dot(values["w"][selected], values["y"][selected]) / population)
                    if (not np.isclose(mean_p, entry["mean_probability"], rtol=0, atol=1e-12)
                            or not np.isclose(outcome, entry["weighted_outcome_rate"], rtol=0, atol=1e-12)):
                        raise ValueError(f"Calibration bin means mismatch in {split}")
                    absolute_error += population / total_weight * abs(mean_p - outcome)
                elif entry["mean_probability"] is not None or entry["weighted_outcome_rate"] is not None:
                    raise ValueError(f"An empty calibration bin has means in {split}")
                if not np.isclose(population / total_weight, entry["population_fraction"], rtol=0, atol=1e-12):
                    raise ValueError(f"Calibration bin fraction mismatch in {split}")
            if not covered.all() or not np.isclose(absolute_error, calibration["weighted_expected_calibration_error"],
                                                  rtol=0, atol=1e-12):
                raise ValueError(f"Calibration coverage or expected error mismatch in {split}")
        predictions[split] = values
    return predictions


def create_figure(path: Path, metrics: dict, history: list, test_predictions: dict):
    colors = {"learned": "#1769aa", "uniform": "#cf741d", "observed": "#37474f"}
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 12, "axes.labelsize": 10,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, axes = plt.subplots(1, 3, figsize=(15.6, 5.2), layout="constrained")
    epoch = np.array([entry["epoch"] for entry in history])
    axes[0].plot(epoch, [entry["train_brier"] for entry in history], marker="o", markersize=3,
                 color=colors["learned"], label="Training")
    axes[0].plot(epoch, [entry["validation_brier"] for entry in history], marker="o", markersize=3,
                 color=colors["uniform"], label="Validation")
    best = metrics["selection"]["best_epoch"]
    axes[0].axvline(best, color="#777777", linestyle="--", linewidth=1, label=f"Selected epoch {best}")
    axes[0].set(title="Weighted Brier during training", xlabel="Epoch", ylabel="Brier score (lower is better)")
    tick_step = max(1, int(np.ceil(len(epoch) / 12)))
    axes[0].set_xticks(np.unique(np.r_[epoch[::tick_step], epoch[-1]]))
    axes[0].legend(frameon=False, fontsize=9)
    axes[0].grid(axis="y", alpha=.22)

    y, weight = test_predictions["y"], test_predictions["w"]
    for model, key, color, label in (
        ("learned_environment_kernel", "p", colors["learned"], "Learned kernel"),
        ("global_neighbor_rate", "baseline_global_neighbor_rate", colors["uniform"], "One neighbor rate"),
    ):
        recall, precision, ap = precision_recall(y, test_predictions[key], weight)
        if not np.isclose(ap, score(metrics, "test", model)["average_precision"], atol=1e-12, rtol=0):
            raise ValueError("The plotted AP differs from saved test metrics")
        axes[1].step(recall, precision, where="pre", color=color, linewidth=1.3,
                     label=f"{label}: AP {ap:.3f}")
    prevalence = score(metrics, "test")["weighted_prevalence"]
    axes[1].axhline(prevalence, color="#777777", linestyle="--", linewidth=1,
                   label=f"Constant score: AP {prevalence:.3f}")
    axes[1].set(title="Weighted test precision–recall", xlabel="Recall", ylabel="Precision",
                xlim=(0, 1), ylim=(0, 1.01))
    axes[1].legend(frameon=False, fontsize=9, loc="upper right")
    axes[1].grid(alpha=.22)

    calibration = metrics["splits"]["test"].get("calibration")
    if calibration is not None:
        bins = [entry for entry in calibration["bins"] if entry["sample_count"] > 0]
        predicted = np.array([entry["mean_probability"] * 100 for entry in bins])
        observed = np.array([entry["weighted_outcome_rate"] * 100 for entry in bins])
        fraction = np.array([entry["population_fraction"] for entry in bins])
        axis_limit = min(100, max(10, 1.15 * max(predicted.max(), observed.max())))
        axes[2].plot([0, axis_limit], [0, axis_limit], linestyle="--", color="#777777", linewidth=1,
                     label="Equal probability and outcome rate")
        axes[2].scatter(predicted, observed, s=30 + 300 * fraction, color=colors["learned"],
                        edgecolors="white", linewidths=.8, label="Nonempty fixed probability bins", zorder=3)
        axes[2].set(title="Pooled test reliability", xlabel="Mean predicted probability (%)",
                    ylabel="Weighted outcome rate (%)", xlim=(0, axis_limit), ylim=(0, axis_limit))
        axes[2].text(.02, .98,
                     f"Weighted calibration error: {100 * calibration['weighted_expected_calibration_error']:.2f} percentage points\n"
                     "Larger markers indicate more cell-hours",
                     transform=axes[2].transAxes, va="top", fontsize=9)
        axes[2].legend(frameon=False, fontsize=8, loc="lower right")
        axes[2].grid(alpha=.22)
    else:
        names = [split.capitalize() for split in SPLITS]
        values = [score(metrics, split) for split in SPLITS]
        position = np.arange(len(names))
        observed = np.array([value["weighted_prevalence"] * 100 for value in values])
        predicted = np.array([value["mean_probability"] * 100 for value in values])
        bars1 = axes[2].bar(position - .18, observed, .36, color=colors["observed"], label="Observed outcome rate")
        bars2 = axes[2].bar(position + .18, predicted, .36, color=colors["learned"], label="Mean predicted probability")
        axes[2].bar_label(bars1, labels=[f"{value:.2f}" for value in observed], padding=3, fontsize=9)
        axes[2].bar_label(bars2, labels=[f"{value:.2f}" for value in predicted], padding=3, fontsize=9)
        axes[2].set(title="Pooled probability and outcome averages", ylabel="Percent of contact population")
        axes[2].set_xticks(position, names)
        axes[2].set_ylim(0, max(observed.max(), predicted.max()) * 1.28)
        axes[2].legend(frameon=False, fontsize=9, loc="upper right")
        axes[2].grid(axis="y", alpha=.22)
    axes[2].set_axisbelow(True)
    kernel_size = metrics["contract"]["kernel_size"]
    fig.suptitle(f"Next-hour burn probability: {kernel_size}×{kernel_size} contact-conditioned evaluation", fontsize=16)
    fig.supxlabel("Inverse sampling weights represent eligible cell-hours; targets without a burned neighbor were excluded.", fontsize=10)
    fig.savefig(path, dpi=200, facecolor="white")
    plt.close(fig)


def create_report(run: Path, metadata: dict, metrics: dict, configuration: dict) -> str:
    kernel_size, radius, support_geometry = kernel_geometry(metadata, metrics)
    selected = metrics["selection"]
    learned = score(metrics, "test")
    uniform = score(metrics, "test", "global_neighbor_rate")
    brier_change = uniform["brier"] - learned["brier"]
    brier_relative = 100 * brier_change / uniform["brier"] if uniform["brier"] else None
    logloss_change = learned["clipped_log_loss"] - uniform["clipped_log_loss"]
    arguments = configuration["arguments"]
    numerical_checks = metrics["verification"]
    center_tolerance = numerical_checks.get("public_forward_center_absolute_tolerance", 1e-7)
    center_check_text = (
        f"The float32 patch-center computation and public model agreed before and after training within absolute tolerance "
        f"{center_tolerance:.1g}. The final maximum absolute difference was "
        f"{numerical_checks['public_forward_center_max_error_final']:.9g}. "
    )
    if numerical_checks.get("cpu_float64_reference_center_checked"):
        center_check_text += (
            "A separate CPU float64 comparison of the two computations passed absolute tolerance "
            f"{numerical_checks['cpu_float64_reference_center_absolute_tolerance']:.1g}. "
        )
    center_check_text += (
        "Independent checkpoint loading on the same backend reproduced all stored partition probabilities within absolute tolerance 1e-7. "
        "The checkpoint loaded with PyTorch's weights-only mechanism."
    )
    if brier_change == 0:
        brier_comparison = "(equal)"
    elif brier_relative is None:
        brier_comparison = "(the baseline Brier is zero, so relative change is undefined)"
    else:
        brier_comparison = f"({abs(brier_relative):.4f}% {'lower' if brier_change > 0 else 'higher'})"
    logloss_comparison = "higher" if logloss_change > 0 else "lower" if logloss_change < 0 else "equal to"
    stopping_description = (
        f"Early stopping after {arguments['patience']} epochs without validation improvement ended the run after "
        f"{selected['epochs_completed']} epochs. "
        if selected.get("early_stopped") else f"The run completed {selected['epochs_completed']} epochs. "
    )
    completed = datetime.fromisoformat(metrics["finished_utc"]).astimezone(ZoneInfo("Asia/Seoul"))
    lines = [
        "# Next-hour burn probability training result",
        "",
        f"The contact-only model was trained and selected at epoch **{selected['best_epoch']}**. "
        f"On held-out fires, its weighted Brier score is **{learned['brier']:.6f}**, "
        f"versus **{uniform['brier']:.6f}** for a single fitted rate per burned neighbor "
        f"{brier_comparison}. "
        f"Its average precision is **{number(learned['average_precision'])}** and ROC AUC is **{number(learned['roc_auc'])}**. "
        f"Its log loss is **{learned['clipped_log_loss']:.6f}**, "
        f"{logloss_comparison} {'than ' if logloss_change else ''}the single-rate baseline's **{uniform['clipped_log_loss']:.6f}**.",
        "",
        "One shared model was fitted to the pooled training partition, and validation and test results pool all included fires. "
        "The previous split, one-hour target, neighborhood-conditioned kernel, contact exclusion, and sampling-weight method were retained. "
        "This run establishes fitted behavior on the reconstructed dataset; it does not establish operational forecast accuracy or scientific superiority.",
        "",
        f"Completed {completed.strftime('%Y-%m-%d %H:%M:%S')} Asia/Seoul. "
        f"Training and final evaluation took {metrics['elapsed_seconds']:.2f} seconds on `{metrics['versions']['device']}`.",
        "",
        "## Target, eligibility, and model",
        "",
        "For each cell i and current time t, the target is whether a cell known to be unburned at t "
        "has become burned at exactly t + 3,600 seconds. Environmental inputs come from the current time t. "
        f"Training, validation, and test all exclude cells with no previously burned neighbor in the surrounding {kernel_size}×{kernel_size} patch, "
        "as requested. They also require known labels and complete current burned and environmental context.",
        "",
        f"The network reads the full environmental {kernel_size}×{kernel_size} neighborhood and produces a separate nonnegative weight "
        "for each neighboring displacement. Its parameters are shared across cells; its generated kernels vary with environmental context. "
        "The central contribution is zero. With B_t indicating the current cumulative burned map, the hourly transition rate "
        "and one-hour probability are",
        "",
        r"\[",
        rf"\lambda_t(i)=\sum_{{\delta\in\{{-{radius},\ldots,{radius}\}}^2\setminus\{{(0,0)\}}}}w_\theta(E_t|_{{\mathcal N(i)}},\delta)B_t(i+\delta),",
        r"\qquad p_t(i)=1-\exp[-\lambda_t(i)\cdot 1\,\mathrm{hour}].",
        r"\]",
        "",
        support_geometry,
        "",
        f"The network uses {metrics['contract']['hidden_channels']} hidden channels, SiLU, and softplus rate outputs. "
        "Current cumulative burned cells act as sources; this does not identify an active flame front.",
        "",
        "Environmental channel order:",
        "",
    ]
    lines.extend(f"{index}. `{channel}`" for index, channel in enumerate(metadata["channels"], 1))
    lines.extend(channel_representation(metadata))
    lines += ["", "Normalization was fitted again using only the contact-only training partition. "
              f"It uses inverse-sampling-weighted moments across all {kernel_size * kernel_size} positions in each environmental patch. "
              "The saved checkpoint includes those means and scales.", "", "## Partition and sampling", ""]
    partition_rows = []
    for split in SPLITS:
        summary = metadata["split_summary"][split]
        current = score(metrics, split)
        partition_rows.append([split.capitalize(), whole(summary["events"]), whole(summary["contributing_events"]),
                               whole(current["sample_count"]), whole(current["positive_sample_count"]),
                               percent(current["positive_sample_count"] / current["sample_count"]),
                               whole(current["represented_population_weight"]), percent(current["weighted_prevalence"])])
    lines += [markdown_table(["Partition", "Assigned fires", "Contributing fires", "Actual samples", "Positive samples",
                              "Sample positive fraction", "Represented eligible cell-hours", "Weighted outcome rate"], partition_rows), "",
              f"All {len(metadata['event_ids'])} available fires were assigned before fitting. "
              "The former fixed allocation of whole season groups defines the partitions, so cells and hours from one fire remain together. "
              "Some assigned fires have no eligible contact-conditioned targets after exclusions.", "",
              "Every positive candidate was retained before validity and contact exclusions. Negative candidates were sampled "
              "uniformly without replacement within each fire and burned-neighbor-contact stratum. "
              f"The contact-negative cap was {metadata['sampling']['contact_limit']:,} samples per fire. "
              "The original inverse inclusion-probability weights were retained after filtering; there was no class or prevalence reweighting. "
              "No refill followed environmental validity filtering.", "",
              "A weight is the negative candidate population divided by the sampled negative count in its stratum; positive weights are one. "
              "The represented population is the sum of weights. Population scores are inverse-inclusion-weighted estimates, "
              "rather than exact full-grid scores. A cell-hour is one eligible cell at one prediction time.", "",
              "The sample positive fraction counts retained positives divided by retained samples; it is affected by negative subsampling. "
              "The weighted outcome rate divides the weighted positive count by the sum of weights and estimates the eligible population's burn frequency. "
              "Training and evaluation use the inverse-inclusion weights, so the sampled positive fraction does not become the fitted probability target. "
              "No class balancing, oversampling of positives, or inverse-class-frequency loss was added. "
              "The division of the loss by training prevalence is one constant applied to every sample, not a class-dependent weight.", "",
              "The user-requested contact filter removed the following previously prepared samples:", "",
              markdown_table(["Partition", "Excluded no-contact samples", "Excluded no-contact positive samples"],
                             [[split.capitalize(), whole(metadata["split_summary"][split]["excluded_no_contact_samples"]),
                               whole(metadata["split_summary"][split]["excluded_no_contact_positives"])] for split in SPLITS]), "",
              "## Fitting and checkpoint selection", "",
              f"Adam used learning rate {arguments['learning_rate']:g}, weight decay {arguments['weight_decay']:g}, "
              f"batch size {arguments['batch_size']:,}, seed {arguments['seed']}, and up to {arguments['epochs']} epochs. "
              f"{stopping_description}Epoch {selected['best_epoch']} minimized weighted validation Brier. "
              "Test data did not select the checkpoint.", "",
              "The minibatch objective was the mean of (weight / mean training weight) × (prediction − target)², "
              "divided by the weighted training prevalence. These constant rescalings preserve the weighted Brier objective. "
              "The final layer started at the training-fitted single per-neighbor rate.", "",
              markdown_table(["Partition", "Brier ↓", "Average precision ↑", "ROC AUC ↑", "Log loss ↓",
                              "Mean probability", "Outcome rate"],
                             [[split.capitalize(), number(score(metrics, split)["brier"]),
                               number(score(metrics, split)["average_precision"]), number(score(metrics, split)["roc_auc"]),
                               number(score(metrics, split)["clipped_log_loss"]), percent(score(metrics, split)["mean_probability"]),
                               percent(score(metrics, split)["weighted_prevalence"])] for split in SPLITS]), "",
              "## Held-out test comparison", "",
              markdown_table(["Model", "Brier ↓", "Average precision ↑", "ROC AUC ↑", "Clipped log loss ↓", "Exact log loss ↓"],
                             [[MODEL_LABELS[model], number(score(metrics, "test", model)["brier"]),
                               number(score(metrics, "test", model)["average_precision"]),
                               number(score(metrics, "test", model)["roc_auc"]),
                               number(score(metrics, "test", model)["clipped_log_loss"]),
                               number(score(metrics, "test", model)["exact_negative_log_likelihood_mean"])] for model in MODELS]), "",
              f"The marginal baseline uses the training weighted probability {metrics['baselines']['train_marginal_probability']:.9f}. "
              f"The single-rate baseline fits one hourly rate {metrics['baselines']['global_neighbor_rate']['per_neighbor_rate_per_hour']:.9f} "
              "per burned neighbor on training data, then predicts 1 − exp(−rate × burned-neighbor count). "
              "All baseline parameters use training data only.", "",
              "Brier is the weighted mean squared probability error, a proper probability score; smaller values are better. "
              "Log loss is a separate probability score and can rank models differently. The clipped calculation limits probabilities "
              "to [10⁻⁷, 1 − 10⁻⁷]; the report also gives exact log loss. The always-zero model has infinite exact log loss because positive outcomes exist. "
              f"The learned model's exact log loss on the contact-only test set is "
              f"{number(learned['exact_negative_log_likelihood_mean'])}.", "",
              "Average precision summarizes the weighted precision–recall curve over probability thresholds. "
              "It is not classification accuracy or precision at a chosen decision threshold. ROC AUC summarizes ranking discrimination. "
              "Higher values are better for both ranking measures. No threshold accuracy claim is made.", "",
              f"Against the single-rate model, the learned model changes test Brier by {-brier_change:+.9f} and "
              f"log loss by {logloss_change:+.9f}. No uncertainty interval or statistical significance test was computed.", "",
              f"The pooled test mean predicted probability is {percent(learned['mean_probability'])}, "
              f"compared with a weighted next-hour outcome rate of {percent(learned['weighted_prevalence'])}. "
              "These means cannot assess calibration across probability levels.", ""]
    if "positive_class_brier" in learned:
        lines += ["Conditional squared probability error for each test label class is reported below to make the imbalance explicit. "
                  "For positive targets it is the weighted mean of (1 − probability)²; for negative targets it is the weighted mean of probability². "
                  "The overall Brier score equals outcome rate × positive-target error + (1 − outcome rate) × negative-target error. "
                  "These diagnostics do not replace the population Brier objective.", "",
                  markdown_table(["Model", "Positive-target squared error ↓", "Negative-target squared error ↓"],
                                 [[MODEL_LABELS[model], number(score(metrics, "test", model)["positive_class_brier"]),
                                   number(score(metrics, "test", model)["negative_class_brier"])] for model in MODELS]), ""]
    calibration = metrics["splits"]["test"].get("calibration")
    if calibration is not None:
        lines += ["## Pooled test calibration", "",
                  "Fixed probability bins were specified for descriptive evaluation. Every cell-hour in a bin retains its sampling weight. "
                  "The mean probability and outcome rate below are weighted within that bin; the population fraction is the bin weight divided by total test weight. "
                  "Empty bins have no empirical mean or outcome rate.", "",
                  markdown_table(["Probability interval", "Samples", "Population fraction", "Mean probability", "Outcome rate"],
                                 [[f"[{entry['lower']:g}, {entry['upper']:g}{']' if entry['upper_inclusive'] else ')'}",
                                   whole(entry["sample_count"]), percent(entry["population_fraction"]),
                                   percent(entry["mean_probability"]) if entry["mean_probability"] is not None else "unavailable",
                                   percent(entry["weighted_outcome_rate"]) if entry["weighted_outcome_rate"] is not None else "unavailable"]
                                  for entry in calibration["bins"]]), "",
                  f"Weighted expected calibration error is **{number(calibration['weighted_expected_calibration_error'])}** "
                  f"({100 * calibration['weighted_expected_calibration_error']:.3f} percentage points). "
                  "It is the sum over nonempty bins of population fraction × absolute difference between bin mean probability and bin outcome rate. "
                  "This value depends on the chosen bins. No uncertainty interval was computed, and fitting a calibration correction was not part of this run.", ""]
        figure_description = "Training history, pooled weighted test precision–recall, and pooled test reliability"
    else:
        lines += ["The figure compares pooled probability and outcome averages separately for training, validation, and test.", ""]
        figure_description = "Training history, pooled weighted test precision–recall, and pooled partition probability/outcome averages"
    lines += [f"![{figure_description}]({run / 'training_results.png'})", "",
              "## Evidence limits and inference", "",
              metadata["label_interpretation"] + ". "
              "The labels come from reconstructed arrival times inside final fire perimeters. "
              "They are not independently observed hourly burn labels. Current environmental context prevents using next-hour environmental inputs, "
              "but this retrospective experiment does not demonstrate availability or reliability of real-time environmental forecasts.", "",
              "The evaluation condition is proximity to an already burned source. It provides no trained claim for isolated new ignitions "
              "or cells without such contact. The saved-model inference wrapper returns NaN and a false validity mask for currently unburned "
              "cells without a known burned neighbor. Its input channel names and order must match the checkpoint. "
              "It accepts source-unit continuous values and encoded categorical indicators in the saved channel order, "
              "and applies saved training normalization without fitting again.", "",
              center_check_text, "",
              f"Training used `{metrics['versions']['device']}` with float32 model arithmetic and float64 normalization moment accumulation. "
              "For MPS execution, the public-forward equivalence checks use an operation that falls back to CPU in this PyTorch version; "
              "the optimized training center path avoids that operation.", "",
              "## Reproduce and use the saved model", "",
              "Run the commands from the WildfireGuardian workspace root. Use a new output directory to preserve this result:", "",
              "```bash",
              "PYTORCH_ENABLE_MPS_FALLBACK=1 .venv/bin/python \\",
              "  -m wildfire_burned_area_hourly.probability_model.train \\",
              f"  --data-dir {arguments['data_dir']} \\",
              f"  --output-dir {Path(arguments['output_dir']).parent / 'reproduction_fitted'} \\",
              f"  --device {arguments['device']} --batch-size {arguments['batch_size']} \\",
              f"  --epochs {arguments['epochs']} --patience {arguments['patience']} \\",
              f"  --hidden-channels {arguments['hidden_channels']} --learning-rate {arguments['learning_rate']:g} \\",
              f"  --weight-decay {arguments['weight_decay']:g} --seed {arguments['seed']} --threads {arguments['threads']}",
              "```", "",
              "This runnable example uses raw current-context patches from the saved test cache:", "",
              "```python", "import json", "from pathlib import Path", "import numpy as np", "import torch",
              "from wildfire_burned_area_hourly.probability_model.inference import load_trained_model", "",
              f"run = Path({str(run.relative_to(Path.cwd()))!r})" if run.is_relative_to(Path.cwd()) else f"run = Path({str(run)!r})",
              'metadata = json.loads((run / "prepared/metadata.json").read_text())',
              'model = load_trained_model(run / "fitted/checkpoint.pt", device="cpu")',
              'with np.load(run / "prepared/test.npz", allow_pickle=False) as saved:',
              '    environment = torch.from_numpy(saved["environment"][:32])',
              '    burned = torch.from_numpy(saved["burned"][:32])',
              "with torch.no_grad():", "    result = model(burned, environment, channel_names=metadata[\"channels\"])",
              f"probability = result.probability[:, 0, {radius}, {radius}]",
              f"valid = result.valid[:, 0, {radius}, {radius}]", "print(probability[valid])",
              "```", "", "## Saved artifacts", ""]
    verification_path = run / "verification.json"
    if verification_path.exists():
        verification = read_json(verification_path)
        if verification.get("passed") is False:
            raise ValueError("The independent saved verification did not pass")
        verification_statements = []
        if "tests_passed" in verification:
            test_scope = f" covering {verification['test_scope'].lower()}" if "test_scope" in verification else ""
            verification_statements.append(
                f"The independent verification record reports **{verification['tests_passed']} passing tests**{test_scope}."
            )
        cpu_partition_checks = verification.get("cpu_wrapper_predictions_reproduced")
        cpu_tolerance = verification.get("cpu_wrapper_absolute_tolerance")
        if cpu_partition_checks is None:
            cpu_partition_checks = verification.get("cpu_wrapper_predictions_reproduced_atol_1e_6")
            cpu_tolerance = 1e-6
        if cpu_partition_checks:
            if (not isinstance(cpu_tolerance, (int, float)) or isinstance(cpu_tolerance, bool)
                    or not np.isfinite(cpu_tolerance) or cpu_tolerance <= 0):
                raise ValueError("CPU inference verification requires its finite positive absolute tolerance")
            counts = ", ".join(f"{split}: {cpu_partition_checks[split]['samples']:,}" for split in SPLITS
                               if split in cpu_partition_checks)
            max_error = max(entry["cpu_wrapper_max_absolute_error"] for entry in cpu_partition_checks.values())
            if max_error > cpu_tolerance:
                raise ValueError("CPU inference verification exceeds the recorded absolute tolerance")
            verification_statements.append(
                f"Independent CPU public inference reproduced the saved {metrics['versions']['device']} probabilities "
                f"across the checked partitions ({counts}), with maximum absolute difference {max_error:.9g}, "
                f"within absolute tolerance {cpu_tolerance:g}."
            )
        elif "public_cpu_inference_test_samples" in verification:
            verification_statements.append(
                f"CPU public inference on all {verification['public_cpu_inference_test_samples']:,} held-out samples "
                f"reproduced the saved MPS probabilities with maximum absolute difference "
                f"{verification['mps_saved_vs_cpu_public_max_absolute_error']:.9g}, within absolute tolerance "
                f"{verification['tolerance']:.1g}."
            )
        if "source_hashes_verified" in verification:
            verification_statements.append(f"All {verification['source_hashes_verified']:,} recorded source-file checksums matched.")
        if verification.get("training_only_normalization_reproduced_exactly"):
            verification_statements.append("Independent training-only normalization reproduced the saved moments exactly.")
        if verification.get("disjoint_contributing_fire_sets"):
            verification_statements.append("The contributing fire sets were disjoint across partitions.")
        if verification.get("channel_order_rejection_checked"):
            verification_statements.append("Reordered channels were rejected.")
        if verification.get("no_contact_inference_unavailable") or verification.get("no_contact_unburned_inference_excluded"):
            verification_statements.append("No-contact unburned inputs were confirmed unavailable.")
        if verification_statements:
            insertion = lines.index("## Reproduce and use the saved model")
            lines[insertion:insertion] = [" ".join(verification_statements), ""]
    for label, relative in (
        ("Fitted checkpoint and normalization", "fitted/checkpoint.pt"),
        ("Training configuration and versions", "fitted/configuration.json"),
        ("Epoch history", "fitted/history.json"),
        ("Complete pooled scores and per-fire results", "fitted/metrics.json"),
        ("Prepared-data provenance, split, exclusions, and source hashes", "prepared/metadata.json"),
        ("Training probabilities, targets, weights, and baselines", "fitted/train_predictions.npz"),
        ("Validation probabilities, targets, weights, and baselines", "fitted/validation_predictions.npz"),
        ("Test probabilities, targets, weights, and baselines", "fitted/test_predictions.npz"),
        ("Scientific result figure", "training_results.png"),
    ):
        lines.append(f"- {link(label, run / relative)}")
    if verification_path.exists():
        lines.append(f"- {link('Independent inference and test verification', verification_path)}")
    lines += ["", "The prepared metadata preserves individual source checksums and any parent-cache provenance chain. "
              "Historical training artifacts are retained separately and do not contribute to this run's fitting or scores.", ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run = args.run_dir.resolve()
    metadata = read_json(run / "prepared" / "metadata.json")
    metrics = read_json(run / "fitted" / "metrics.json")
    history = read_json(run / "fitted" / "history.json")
    configuration = read_json(run / "fitted" / "configuration.json")
    predictions = validate_saved_results(run, metadata, metrics, history)
    figure = run / "training_results.png"
    create_figure(figure, metrics, history, predictions["test"])
    report = run / "report.md"
    report.write_text(create_report(run, metadata, metrics, configuration), encoding="utf-8")
    print(json.dumps({"report": str(report), "figure": str(figure), "refit": False}, indent=2), flush=True)


if __name__ == "__main__":
    main()
