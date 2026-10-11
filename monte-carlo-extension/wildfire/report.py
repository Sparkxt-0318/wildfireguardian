"""Report operations for the wildfire workspace."""
from __future__ import annotations



# Report training
# Create a contact-conditioned training report from saved results, without fitting.
# 
# Usage: python -m wildfire report
# --run-dir runs/RUN


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


training_SPLITS = ("train", "validation", "test")
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


def channel_representation(metadata: dict, *, raw_one_hot: bool = False) -> list[str]:
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
                  ("These binary indicators retain their raw 0/1 values: categorical means are zero and scales are one. "
                   "Only continuous channels use training-only inverse-sampling-weighted standardization. "
                   "This avoids amplifying rare category indicators by a very small standard deviation."
                   if raw_one_hot else
                   "These binary indicators are standardized with training-only weighted means and scales before entering the network, "
                   "using the same normalization method as the continuous channels. Channels constant in training use a scale of one.")]
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
    for split in training_SPLITS:
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
        names = [split.capitalize() for split in training_SPLITS]
        values = [score(metrics, split) for split in training_SPLITS]
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
    categorical_balance = metrics["contract"].get("categorical_balance")
    if categorical_balance is None:
        reproduction_balance_options = ""
        objective_description = (
            "The minibatch objective was the mean of (weight / mean training weight) × (prediction − target)², "
            "divided by the weighted training prevalence. These constant rescalings preserve the weighted Brier objective. "
        )
    else:
        settings = categorical_balance["settings"]
        reproduction_balance_options = (
            f" --categorical-balance {settings['mode']}"
            f" --categorical-balance-min-frequency {settings['min_frequency']:g}"
            f" --categorical-balance-max-factor {settings['max_factor']:g}"
        )
        objective_description = (
            f"Categorical weighting mode was `{settings['mode']}`, with presence-frequency floor "
            f"{settings['min_frequency']:g} and raw category-factor cap {settings['max_factor']:g}. "
            "Category frequencies were fitted using only raw training patches and original inverse inclusion weights. "
            "For enabled balancing, each row averages capped inverse-square-root factors over its distinct present categories, "
            "then over categorical source fields, and divides by the original-weighted mean factor. "
            "The optimization weight is the original weight multiplied by this normalized factor. "
            "The minibatch objective uses optimization weights divided by their training mean, then divides by the "
            "optimization-weighted training prevalence. Validation selection and all population scores retain original weights. "
            "No outcome-class weighting was introduced. Category-presence groups overlap, and equal category mass is not guaranteed. "
        )
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
    lines.extend(channel_representation(metadata, raw_one_hot=categorical_balance is not None))
    lines += ["", "Normalization was fitted again using only the contact-only training partition. "
              f"It uses inverse-sampling-weighted moments across all {kernel_size * kernel_size} positions in each environmental patch" +
              (" for continuous channels; categorical indicators remain raw 0/1. " if categorical_balance is not None else ". ") +
              "The saved checkpoint includes those means and scales.", "", "## Partition and sampling", ""]
    partition_rows = []
    for split in training_SPLITS:
        summary = metadata["split_summary"][split]
        current = score(metrics, split)
        partition_rows.append([split.capitalize(), whole(summary["events"]), whole(summary["contributing_events"]),
                               whole(current["sample_count"]), whole(current["positive_sample_count"]),
                               percent(current["positive_sample_count"] / current["sample_count"]),
                               whole(current["represented_population_weight"]), percent(current["weighted_prevalence"])])
    lines += [markdown_table(["Partition", "Assigned fires", "Contributing fires", "Actual samples", "Positive samples",
                              "Sample positive fraction", "Represented eligible cell-hours", "Weighted outcome rate"], partition_rows), "",
              f"All {len(metadata['event_ids'])} available fires have explicit partition declarations before fitting. "
              f"Split policy: {metadata.get('split_policy', 'Whole-fire assignments')}. " +
              ("Training and validation share fires with disjoint cell-hour identities; original test fires remain separate. "
               if metadata.get("split_unit") == "cell_hour" else
               "Cells and hours from one fire remain together in one partition. ") +
              "Some assigned fires have no eligible contact-conditioned targets after exclusions.", "",
              "Every positive candidate was retained before validity and contact exclusions. Negative candidates were sampled "
              "uniformly without replacement within each fire and burned-neighbor-contact stratum. "
              f"The contact-negative cap was {metadata['sampling']['contact_limit']:,} samples per fire. "
              "The cached inverse inclusion-probability weights were retained after filtering; there was no outcome-class or prevalence reweighting of the cache. "
              "No refill followed environmental validity filtering.", "",
              "A weight is the negative candidate population divided by the sampled negative count in its stratum; positive weights are one. "
              "The represented population is the sum of weights. Population scores are inverse-inclusion-weighted estimates, "
              "rather than exact full-grid scores. A cell-hour is one eligible cell at one prediction time.", "",
              "The sample positive fraction counts retained positives divided by retained samples; it is affected by negative subsampling. "
              "The weighted outcome rate divides the weighted positive count by the sum of weights and estimates the eligible population's burn frequency. "
              "Population evaluation uses inverse-inclusion weights, so the sampled positive fraction is not the population burn frequency. "
              "No outcome-class balancing or oversampling of positives was added. "
              "The division of the loss by its stated training prevalence is one constant applied to every sample. "
              + ("Categorical input reweighting for optimization is described below. " if categorical_balance is not None else
                 "Training also uses the original inverse-inclusion weights. "), "",
              "The user-requested contact filter removed the following previously prepared samples:", "",
              markdown_table(["Partition", "Excluded no-contact samples", "Excluded no-contact positive samples"],
                             [[split.capitalize(), whole(metadata["split_summary"][split]["excluded_no_contact_samples"]),
                               whole(metadata["split_summary"][split]["excluded_no_contact_positives"])] for split in training_SPLITS]), "",
              "## Fitting and checkpoint selection", "",
              f"Adam used learning rate {arguments['learning_rate']:g}, weight decay {arguments['weight_decay']:g}, "
              f"batch size {arguments['batch_size']:,}, seed {arguments['seed']}, and up to {arguments['epochs']} epochs. "
              f"{stopping_description}Epoch {selected['best_epoch']} minimized weighted validation Brier. "
              "Test data did not select the checkpoint.", "",
              objective_description +
              "The final layer started at the training-fitted single per-neighbor rate.", "",
              markdown_table(["Partition", "Brier ↓", "Average precision ↑", "ROC AUC ↑", "Log loss ↓",
                              "Mean probability", "Outcome rate"],
                             [[split.capitalize(), number(score(metrics, split)["brier"]),
                               number(score(metrics, split)["average_precision"]), number(score(metrics, split)["roc_auc"]),
                               number(score(metrics, split)["clipped_log_loss"]), percent(score(metrics, split)["mean_probability"]),
                               percent(score(metrics, split)["weighted_prevalence"])] for split in training_SPLITS]), "",
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
              "or cells without such contact. Current saved-model inference retains valid structural zeros for known unburned "
              "cells with complete all-unburned source neighborhoods and available required input context. "
              "Unknown neighboring source states remain unavailable (NaN and a false validity mask). "
              "These structural zeros follow from the model equation and do not extend the empirical evaluation cohort. "
              "They are excluded as training targets; the training loss still uses only contact-eligible target patches. "
              "Its input channel names and order must match the checkpoint. "
              "It accepts source-unit continuous values and encoded categorical indicators in the saved channel order, "
              "and applies saved training normalization without fitting again.", "",
              center_check_text, "",
              f"Training used `{metrics['versions']['device']}` with float32 model arithmetic and float64 normalization moment accumulation. "
              "For MPS execution, the public-forward equivalence checks use an operation that falls back to CPU in this PyTorch version; "
              "the optimized training center path avoids that operation.", "",
              "## Reproduce and use the saved model", "",
              "Run the commands from the WildfireGuardian workspace root using the source version bound to the original fit. "
              "Saved checkpoints preserve their historical preprocessing; newer training methods require a fresh fit. "
              "Use a new output directory to preserve this result:", "",
              "```bash",
              "PYTORCH_ENABLE_MPS_FALLBACK=1 .venv/bin/python \\",
              "  -m wildfire train \\",
              f"  --data-dir {arguments['data_dir']} \\",
              f"  --output-dir {Path(arguments['output_dir']).parent / 'reproduction_fitted'} \\",
              f"  --device {arguments['device']} --batch-size {arguments['batch_size']} \\",
              f"  --epochs {arguments['epochs']} --patience {arguments['patience']} \\",
              f"  --hidden-channels {arguments['hidden_channels']} --learning-rate {arguments['learning_rate']:g} \\",
              f"  --weight-decay {arguments['weight_decay']:g} --seed {arguments['seed']} --threads {arguments['threads']}" + reproduction_balance_options,
              "```", "",
              "This runnable example uses raw current-context patches from the saved test cache:", "",
              "```python", "import json", "from pathlib import Path", "import numpy as np", "import torch",
              "from wildfire.inference import load_single_trained_model as load_trained_model", "",
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
            counts = ", ".join(f"{split}: {cpu_partition_checks[split]['samples']:,}" for split in training_SPLITS
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
            verification_statements.append(
                "The saved verification record used the earlier inference policy that excluded no-contact unburned inputs."
            )
        if verification.get("no_contact_structural_zero_valid"):
            verification_statements.append(
                "Complete all-unburned source neighborhoods were confirmed to give valid structural-zero predictions."
            )
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


def training_main():
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




# Broader comparison
# Report a broader-kernel comparison from saved predictions without fitting.
# 
# Native runs have different eligible populations. The separate common cohort
# must contain the same labels and weights for every model within each split.





from wildfire.metrics import probability_metrics
from wildfire.metrics import weighted_calibration

# report_training configures a disposable Matplotlib cache and the Agg backend.


KERNELS = (3, 5, 7, 9)
comparison_COLORS = {3: "#1769aa", 5: "#dd871f", 7: "#37925e", 9: "#a25ca0"}


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
    for split in training_SPLITS:
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
    for split in training_SPLITS:
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
        axes[1].step(recall, precision, where="pre", linewidth=1.3, color=comparison_COLORS[kernel],
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
                     linewidth=1, color=comparison_COLORS[kernel], label=f"{kernel}×{kernel}")
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
        for split in training_SPLITS)
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
                              percent(_common(common, split, 3)["weighted_prevalence"])] for split in training_SPLITS]), "",
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
    for split in training_SPLITS:
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


def comparison_main():
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




# Evaluation report
# Report every saved search evaluation without fitting or changing predictions.
# 
# Run ``python -m wildfire report-metrics
# RUN_DIRECTORY`` to extend a completed kernel-search report. This module is
# deliberately separate from the source files sealed by training protocols.


import csv
import math
import re
import textwrap
from typing import Any


START = "<!-- BEGIN COMPLETE PROBABILITY EVALUATION -->"
END = "<!-- END COMPLETE PROBABILITY EVALUATION -->"
OVERVIEW_START = "<!-- BEGIN EVALUATION BAR OVERVIEW -->"
OVERVIEW_END = "<!-- END EVALUATION BAR OVERVIEW -->"
evaluation_SPLITS = ("train", "validation", "test")
evaluation_COLORS = ("#0072B2", "#D55E00", "#009E73")
GROUPS = (
    "Probability scores", "Probability distances", "Ranking scores",
    "Classification scores and confusion counts", "Calibration",
    "Cohort and support diagnostics", "Thresholds and scoring configuration",
    "Full prediction coverage", "Other saved metrics",
)
NAMES = {
    "brier": "Weighted Brier score",
    "positive_class_brier": "Positive-class Brier score",
    "negative_class_brier": "Negative-class Brier score",
    "exact_negative_log_likelihood_mean": "Exact negative log likelihood (nats)",
    "clipped_log_loss": "Floored log loss (nats)",
    "bernoulli_kl_divergence_mean": "Exact Bernoulli KL divergence (nats)",
    "floored_bernoulli_kl_divergence_mean": "Floored Bernoulli KL divergence (nats)",
    "bernoulli_total_variation_distance_mean": "Bernoulli total variation distance",
    "bernoulli_hellinger_distance_mean": "Bernoulli Hellinger distance",
    "bernoulli_jensen_shannon_divergence_mean": "Bernoulli Jensen-Shannon divergence (nats)",
    "bernoulli_jensen_shannon_distance_mean": "Bernoulli Jensen-Shannon distance",
    "bernoulli_bhattacharyya_distance_mean": "Bernoulli Bhattacharyya distance",
    "bernoulli_wasserstein_1_distance_mean": "Bernoulli Wasserstein-1 distance",
    "bernoulli_wasserstein_2_distance_mean": "Bernoulli Wasserstein-2 distance",
    "average_precision": "Average precision (non-interpolated)",
    "precision_recall_auc": "Precision-recall AUC (trapezoidal)",
    "roc_auc": "ROC AUC",
    "calibration.weighted_expected_calibration_error": "Weighted expected calibration error",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _scalar(value: Any) -> bool:
    return (value is None or
            isinstance(value, (float, int)) and not isinstance(value, bool) or
            isinstance(value, str) and value in ("infinity", "-infinity"))


def flatten_metrics(values: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Discover all scalar metrics, including nested classification and ECE.

    Reliability-bin arrays are exported separately. Text describes the scoring
    protocol; it is not a numerical metric. New numeric fields are discovered
    automatically rather than omitted by a fixed metric allowlist.
    """
    result = {}
    for key, value in values.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten_metrics(value, name))
        elif _scalar(value):
            result[name] = value
    return result


def _status(value: Any, *, present: bool = True) -> tuple[str, float | None]:
    if not present:
        return "missing", None
    if value is None:
        return "undefined", None
    if value == "infinity":
        return "positive_infinity", None
    if value == "-infinity":
        return "negative_infinity", None
    number = float(value)
    if math.isnan(number):
        raise ValueError("NaN is not a supported saved metric; use JSON null for an undefined metric")
    if math.isinf(number):
        return ("positive_infinity" if number > 0 else "negative_infinity"), None
    return "finite", number


def _category(key: str) -> str:
    if key.startswith("coverage."):
        return "Full prediction coverage"
    if key in ("validation_f1_threshold", "validation_mcc_threshold", "log_loss_probability_floor") or key.rsplit(".", 1)[-1] == "threshold":
        return "Thresholds and scoring configuration"
    if "bernoulli_" in key:
        return "Probability distances"
    if key.startswith("calibration."):
        return "Calibration"
    if key in ("average_precision", "roc_auc", "precision_recall_auc"):
        return "Ranking scores"
    if key.startswith(("classification_", "precision_at_", "recall_at_", "f1_at_", "mcc_at_")):
        return "Classification scores and confusion counts"
    if "brier" in key or "log_loss" in key or "likelihood" in key:
        return "Probability scores"
    if any(word in key for word in ("count", "weight", "fraction", "prevalence", "mean_probability")):
        return "Cohort and support diagnostics"
    return "Other saved metrics"


def _direction(key: str) -> str:
    group = _category(key)
    if group in ("Probability scores", "Probability distances", "Calibration"):
        return "Lower is better"
    if group == "Ranking scores" or (group == "Classification scores and confusion counts" and
                                     key.rsplit(".", 1)[-1] not in ("tp", "fp", "tn", "fn")):
        return "Higher is better"
    return "Descriptive; no universal better direction"


def _title(key: str) -> str:
    return NAMES.get(key, key.replace("_", " ").replace(".", " / "))


def _labels(selection: dict[str, Any], model_ids: list[str]) -> dict[str, str]:
    labels = {}
    for record in selection.get("selected", []):
        candidate = record.get("candidate", record)
        model = candidate.get("id")
        if model is None:
            continue
        family = candidate.get("family", "random_forest")
        support = "+".join(map(str, candidate.get("kernel_sizes", [candidate["kernel_size"]])))
        labels[model] = f"{family} K={support}"
    # Saved identifiers remain available in every table/CSV, even when labels
    # are abbreviated in figures. Disambiguate unexpected repeated settings.
    counts = {label: list(labels.values()).count(label) for label in labels.values()}
    return {model: labels.get(model, model) + (f" [{model}]" if counts.get(labels.get(model)) > 1 else "")
            for model in model_ids}


def collect_metrics(metrics: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Return every model/split/scope/metric cell, with explicit missing status."""
    if "test" not in metrics:
        raise ValueError("A completed comparison must contain test evaluations")
    model_ids = list(metrics["test"].get("models", {}))
    if not model_ids:
        raise ValueError("No evaluated models in metrics.json")
    available = {}
    kernels = {}
    for split in evaluation_SPLITS:
        if split not in metrics or set(metrics[split].get("models", {})) != set(model_ids):
            raise ValueError(f"Model/split mismatch in metrics.json: {split}")
        for model in model_ids:
            row = metrics[split]["models"][model]
            kernel = row["kernel_size"]
            if not isinstance(kernel, int) or isinstance(kernel, bool) or kernel < 1:
                raise ValueError(f"Invalid kernel_size for {model}")
            if model in kernels and kernels[model] != kernel:
                raise ValueError(f"Kernel support changed across splits: {model}")
            kernels[model] = kernel
            for scope in ("common", "native"):
                if not isinstance(row.get(scope), dict):
                    raise ValueError(f"Missing {scope} evaluation: {split}/{model}")
                available[split, model, scope] = flatten_metrics(row[scope])
            available[split, model, "full_prediction"] = flatten_metrics(row.get("coverage", {}), "coverage")
    metric_names = sorted({key for values in available.values() for key in values},
                          key=lambda key: (GROUPS.index(_category(key)), key))
    rows = []
    for key in metric_names:
        for split in evaluation_SPLITS:
            for model in model_ids:
                for scope in (("full_prediction",) if key.startswith("coverage.") else ("common", "native")):
                    values = available[split, model, scope]
                    value = values.get(key)
                    status, finite = _status(value, present=key in values)
                    rows.append(dict(metric=key, split=split, model=model, kernel_size=kernels[model],
                                     scope=scope, value=value, status=status, finite_value=finite))
    return rows, metric_names, model_ids


def _panels(plt, model_count: int, native_sizes: list[int]):
    """One shared-cohort axis and one independent axis per native support."""
    if not native_sizes:
        fig, ax = plt.subplots(figsize=(12, max(4, .32 * model_count + 2)))
        return fig, [ax]
    native_rows = math.ceil(len(native_sizes) / 2)
    height = max(6, .32 * model_count + 2, native_rows * 3.2)
    fig = plt.figure(figsize=(18, height))
    grid = fig.add_gridspec(native_rows, 3, width_ratios=(1.6, 1, 1))
    axes = [fig.add_subplot(grid[:, 0])]
    axes.extend(fig.add_subplot(grid[index // 2, index % 2 + 1]) for index in range(len(native_sizes)))
    return fig, axes


def _draw_metric(plt, path: Path, key: str, rows: list[dict[str, Any]],
                 model_ids: list[str], labels: dict[str, str]) -> None:
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    full = key.startswith("coverage.")
    sizes = sorted({row["kernel_size"] for row in rows if row["scope"] == "native"})
    fig, axes = _panels(plt, len(model_ids), sizes)
    scopes = [("full_prediction" if full else "common", None)] + [("native", size) for size in sizes]
    lookup = {(row["scope"], row["split"], row["model"]): row for row in rows}
    status_labels = {"undefined": "N/A", "missing": "missing", "positive_infinity": "+∞", "negative_infinity": "−∞"}
    for ax, (scope, size) in zip(axes, scopes):
        ids = [model for model in model_ids if (scope, "test", model) in lookup and
               (size is None or lookup[scope, "test", model]["kernel_size"] == size)]
        finite_values = []
        for split_index, (split, color) in enumerate(zip(evaluation_SPLITS, evaluation_COLORS)):
            xs, ys = [], []
            for index, model in enumerate(ids):
                row = lookup[scope, split, model]
                y = index + (split_index - 1) * .22
                if row["status"] == "finite":
                    xs.append(row["finite_value"])
                    ys.append(y)
                    finite_values.append(row["finite_value"])
                else:
                    ax.text(1.01, y, status_labels[row["status"]], color=color, fontsize=7,
                            va="center", transform=ax.get_yaxis_transform(), clip_on=False)
            ax.barh(ys, xs, height=.20, color=color, label=split, zorder=3,
                    edgecolor="white", linewidth=.3)
        ax.set_yticks(range(len(ids)), [labels[model] for model in ids], fontsize=8)
        ax.set_ylim(len(ids) - .4, -.7)
        ax.set_title("All base prediction rows" if full else "Matched 3×3-contact cohort" if size is None else f"Native {size}×{size}-contact cohort", fontsize=11)
        ax.set_xlabel("Saved metric value", fontsize=9)
        ax.grid(axis="x", alpha=.25)
        ax.tick_params(axis="x", labelsize=8)
        ax.margins(x=.12)
        if finite_values:
            # Every bar starts at zero, including negative MCC values. A
            # truncated bar baseline would exaggerate small differences.
            low, high = min(0., min(finite_values)), max(0., max(finite_values))
            span = high - low or 1.
            ax.set_xlim(low - .04 * span if low < 0 else 0,
                        high + .08 * span if high > 0 else .04 * span)
            ax.axvline(0, color="gray", linewidth=.7)
            ax.xaxis.set_major_locator(MaxNLocator(4))
            ax.xaxis.set_major_formatter(FuncFormatter(lambda value, position: f"{value:.5g}"))
        else:
            ax.set_xticks([])
            ax.text(.5, .5, "No finite values", ha="center", va="center", transform=ax.transAxes,
                    color="gray", fontsize=10)
        ax.legend(fontsize=7, loc="best")
    fig.suptitle(f"{_title(key)}\n{_direction(key)}", fontsize=13)
    fig.text(.5, .01, "Axes scale independently by cohort. +∞ / −∞ = exact infinity; N/A = undefined; missing = absent field. No confidence intervals.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .035, .96, .94), w_pad=4)
    fig.savefig(path, dpi=110, facecolor="white")
    plt.close(fig)


def _overview_model(selection: dict[str, Any], models: list[str]) -> str:
    """Default to the saved validation-selected model, without reselecting it."""
    best = selection.get("best", {})
    model = best.get("candidate", best).get("id")
    return model if model in models else models[0]


def _overview_title(key: str) -> str:
    """Compact decision-rule labels keep every metric identifiable in the grid."""
    policies = (("0_5", "0.5"), ("validation_f1_threshold", "val-F1 threshold"),
                ("validation_mcc_threshold", "val-MCC threshold"))
    score_names = {"precision": "Precision", "recall": "Recall", "f1": "F1", "mcc": "MCC",
                   "tp": "Weighted TP", "fp": "Weighted FP", "tn": "Weighted TN", "fn": "Weighted FN",
                   "threshold": "Decision threshold"}
    for suffix, label in policies:
        prefix = f"classification_at_{suffix}."
        if key.startswith(prefix):
            score = key[len(prefix):]
            return f"{score_names.get(score, score)} ({label}; detail)"
        for score in ("precision", "recall", "f1", "mcc"):
            if key == f"{score}_at_{suffix}":
                return f"{score_names[score]} at {label}"
    return _title(key)


def _write_overview_dashboard(destination: Path, rows: list[dict[str, Any]], names: list[str],
                              models: list[str], labels: dict[str, str], default_model: str) -> None:
    """One local page displays all fields at once for any selected model/scope."""
    cells = {model: {} for model in models}
    for row in rows:
        cells[row["model"]].setdefault(row["scope"], {}).setdefault(row["metric"], {})[row["split"]] = {
            "value": row["finite_value"], "status": row["status"], "text": _format(row)}
    payload = dict(metrics=[dict(key=key, title=_overview_title(key), category=_category(key), direction=_direction(key)) for key in names],
                   models=[dict(id=model, label=labels[model]) for model in models],
                   cells=cells, default_model=default_model, colors=evaluation_COLORS, splits=evaluation_SPLITS)
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>All evaluation metrics — bar overview</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f6fa;color:#172338;font:13px system-ui,sans-serif}
header{padding:10px 16px;background:white;border-bottom:1px solid #d6deea}h1{font-size:18px;margin:0 0 8px}
.controls{display:flex;gap:14px;align-items:center;flex-wrap:wrap}label{display:flex;gap:5px;align-items:center}
select,button{font:inherit;border:1px solid #c0ccdd;border-radius:4px;padding:4px;background:white;max-width:360px}
.note{font-size:11px;margin:7px 0 0;color:#43516a}.legend span{margin-right:10px;font-weight:600}
#metrics{--columns:8;display:grid;grid-template-columns:repeat(var(--columns),minmax(0,1fr));gap:5px;
height:calc(100vh - 154px);min-height:480px;padding:8px}
.card{background:white;border:1px solid #d6deea;border-radius:4px;min-width:0;min-height:0;padding:4px 6px;
display:grid;grid-template-rows:25px minmax(0,1fr) 13px;overflow:hidden}
.card h2{margin:0;font-size:10px;font-weight:600;line-height:12px;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.card svg{width:100%;height:100%;min-height:12px}.values{display:flex;gap:4px;justify-content:space-between;font-size:9px;white-space:nowrap}
.values span{overflow:hidden;text-overflow:ellipsis}.expanded #metrics{height:auto;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));grid-auto-rows:145px}
.expanded .card{grid-template-rows:32px minmax(0,1fr) 18px}.expanded .card h2{font-size:12px;line-height:15px}.expanded .values{font-size:11px}
footer{padding:2px 16px 8px;font-size:11px;color:#43516a}footer a{color:#0072B2}
</style></head><body>
<header><h1>All evaluation metrics at a glance</h1><div class="controls">
<label>Model <select id="model" aria-label="Model"></select></label>
<label>Cohort <select id="scope"><option value="common">Matched 3×3-contact</option><option value="native">Native contact for this model</option></select></label>
<label>Columns <select id="columns"><option>6</option><option selected>8</option><option>10</option></select></label>
<button id="size" type="button">Larger charts</button><span id="count"></span>
<span class="legend"><span style="color:#0072B2">Tr: training</span><span style="color:#D55E00">Va: validation</span><span style="color:#009E73">Te: test</span></span>
</div><p class="note">Each card uses its own raw-value scale and a zero baseline. ↓ lower is better; ↑ higher is better; = descriptive. Default model comes from saved validation selection. Full prediction coverage always uses all base rows.</p></header>
<main id="metrics" aria-label="Every saved scalar evaluation metric"></main>
<footer>Hover a card for its full field name, values, and interpretation. Infinities and N/A are labeled, never replaced by zero. Native populations differ across kernel sizes. <a href="report.md">Detailed bar graphs and tables</a> · <a href="metrics.csv">All exact values (CSV)</a></footer>
<script id="evaluation-data" type="application/json">__EVALUATION_DATA__</script>
<script>
const data=JSON.parse(document.getElementById('evaluation-data').textContent), grid=document.getElementById('metrics'), model=document.getElementById('model'), scope=document.getElementById('scope');
for(const item of data.models){const option=document.createElement('option');option.value=item.id;option.textContent=item.label;model.append(option)}model.value=data.default_model;
const svgNode=(tag,attrs)=>{const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,value] of Object.entries(attrs))node.setAttribute(key,value);return node};
function render(){grid.replaceChildren();document.getElementById('count').textContent=`${data.metrics.length} fields`;
for(const metric of data.metrics){const cohort=metric.key.startsWith('coverage.')?'full_prediction':scope.value, entries=data.cells[model.value][cohort][metric.key];
const card=document.createElement('article');card.className='card';card.dataset.metric=metric.key;
card.title=`${metric.title}\n${metric.key}\n${metric.category}; ${metric.direction}\nScope: ${cohort}\n`+data.splits.map(split=>`${split}: ${entries[split].text}`).join('\n');
const heading=document.createElement('h2'),arrow=metric.direction.startsWith('Lower')?'↓':metric.direction.startsWith('Higher')?'↑':'=';heading.textContent=arrow+' '+metric.title;card.append(heading);
const chart=svgNode('svg',{viewBox:'0 0 180 55',role:'img','aria-label':card.title,preserveAspectRatio:'none'}), finite=data.splits.map(split=>entries[split].value).filter(value=>value!==null);
let low=Math.min(0,...finite), high=Math.max(0,...finite);const span=high-low||1;low=low<0?low-.06*span:0;high=high+.08*span;const y=value=>51-(value-low)/(high-low)*47;
chart.append(svgNode('line',{x1:4,x2:176,y1:y(0),y2:y(0),stroke:'#9aa8bb','stroke-width':.6}));
data.splits.forEach((split,index)=>{const entry=entries[split],x=18+index*56;if(entry.value!==null){const yy=y(entry.value);chart.append(svgNode('rect',{x,y:Math.min(yy,y(0)),width:30,height:Math.abs(yy-y(0)),fill:data.colors[index]}))}
else{const text=svgNode('text',{x:x+15,y:28,'text-anchor':'middle',fill:data.colors[index],'font-size':10});text.textContent=entry.text;chart.append(text)}});card.append(chart);
const values=document.createElement('div');values.className='values';data.splits.forEach((split,index)=>{const value=document.createElement('span'),entry=entries[split];value.style.color=data.colors[index];value.textContent=['Tr','Va','Te'][index]+' '+(entry.value===null?entry.text:entry.value===0?'0':Number(entry.value).toPrecision(4));values.append(value)});card.append(values);grid.append(card)}}
model.addEventListener('change',render);scope.addEventListener('change',render);document.getElementById('columns').addEventListener('change',event=>grid.style.setProperty('--columns',event.target.value));
document.getElementById('size').addEventListener('click',event=>{const expanded=document.body.classList.toggle('expanded');event.target.textContent=expanded?'Fit all metrics':'Larger charts'});render();
</script></body></html>'''
    (destination / "overview.html").write_text(template.replace("__EVALUATION_DATA__", data), encoding="utf-8")


def _overview_assets(plt, destination: Path, rows: list[dict[str, Any]], names: list[str],
                     models: list[str], labels: dict[str, str], default_model: str) -> tuple[dict[str, str], dict[str, str]]:
    """Export all metric bar panels together, with independent metric scales."""
    from matplotlib.patches import Patch
    from matplotlib.ticker import FuncFormatter, MaxNLocator

    lookup = {(row["metric"], row["scope"], row["split"]): row for row in rows if row["model"] == default_model}
    images, vectors = {}, {}
    columns = 8
    panel_rows = math.ceil(len(names) / columns)
    for scope in ("common", "native"):
        fig, axes = plt.subplots(panel_rows, columns, figsize=(25.6, panel_rows * 1.8 + 1.3), squeeze=False)
        for ax, key in zip(axes.flat, names):
            actual_scope = "full_prediction" if key.startswith("coverage.") else scope
            finite = []
            for index, (split, color) in enumerate(zip(evaluation_SPLITS, evaluation_COLORS)):
                row = lookup[key, actual_scope, split]
                if row["status"] == "finite":
                    value = row["finite_value"]
                    finite.append(value)
                    ax.bar(index, value, color=color, width=.65)
                else:
                    ax.text((index + .5) / 3, .4, _format(row), color=color,
                            transform=ax.transAxes, ha="center", fontsize=7)
            if finite:
                low, high = min(0., min(finite)), max(0., max(finite))
                span = high - low or 1.
                ax.set_ylim(low - .08 * span if low < 0 else 0, high + .15 * span)
            else:
                ax.set_yticks([])
            arrow = "↓" if _direction(key).startswith("Lower") else "↑" if _direction(key).startswith("Higher") else "="
            ax.set_title(textwrap.fill(f"{arrow} {_overview_title(key)}", width=45), fontsize=7.5, loc="left", pad=3)
            ax.set_xticks((0, 1, 2), ("Tr", "Va", "Te"), fontsize=7)
            ax.set_xlim(-.6, 2.6)
            ax.yaxis.set_major_locator(MaxNLocator(3))
            ax.yaxis.set_major_formatter(FuncFormatter(lambda value, position: f"{value:.3g}"))
            if not finite:
                ax.set_yticks([])
            ax.tick_params(axis="y", labelsize=6)
            ax.grid(axis="y", alpha=.18)
            ax.axhline(0, color="gray", linewidth=.5)
        for ax in list(axes.flat)[len(names):]:
            ax.set_visible(False)
        cohort = "Matched 3×3-contact" if scope == "common" else "Native contact for this model"
        fig.suptitle(f"All {len(names)} saved numeric fields — {labels[default_model]}\n{cohort}; model selected on validation", fontsize=15)
        fig.legend(handles=[Patch(facecolor=color, label=split) for split, color in zip(evaluation_SPLITS, evaluation_COLORS)], loc="upper center", bbox_to_anchor=(.5, .96), ncol=3, fontsize=10)
        fig.text(.5, .01, "Raw values; independent scale per metric; bars start at zero. ↓ lower; ↑ higher; = descriptive. Coverage uses all base rows. Infinities and undefined values stay labeled.", ha="center", fontsize=9)
        fig.tight_layout(rect=(0, .03, 1, .93), h_pad=1.5, w_pad=1.5)
        images[scope], vectors[scope] = f"figures/overview_{scope}.png", f"figures/overview_{scope}.svg"
        fig.savefig(destination / images[scope], dpi=130, facecolor="white")
        fig.savefig(destination / vectors[scope], facecolor="white")
        plt.close(fig)
    _write_overview_dashboard(destination, rows, names, models, labels, default_model)
    return images, vectors


def _calibration_assets(plt, destination: Path, metrics: dict[str, Any], model_ids: list[str],
                        labels: dict[str, str]) -> tuple[list[dict[str, Any]], list[str]]:
    bins = []
    images = []
    sizes = sorted({metrics["test"]["models"][model]["kernel_size"] for model in model_ids})
    for split in evaluation_SPLITS:
        fig, axes = _panels(plt, max(len(model_ids), 20), sizes)
        scopes = [("common", None)] + [("native", size) for size in sizes]
        for ax, (scope, size) in zip(axes, scopes):
            ids = [model for model in model_ids if size is None or metrics[split]["models"][model]["kernel_size"] == size]
            for index, model in enumerate(ids):
                record = metrics[split]["models"][model]
                entries = record[scope].get("calibration", {}).get("bins", [])
                for bin_index, entry in enumerate(entries):
                    bins.append(dict(split=split, model=model, kernel_size=record["kernel_size"],
                                     scope=scope, bin_index=bin_index, **entry))
                defined = [entry for entry in entries if entry.get("mean_probability") is not None and entry.get("weighted_outcome_rate") is not None]
                # Connect adjacent populated bins only. Empty bins remain absent
                # and are retained explicitly in calibration_bins.csv.
                x = [entry.get("mean_probability") if entry in defined else math.nan for entry in entries]
                y = [entry.get("weighted_outcome_rate") if entry in defined else math.nan for entry in entries]
                ax.plot(x, y, marker="o", markersize=3, linewidth=.8,
                        color=plt.get_cmap("tab20")(index % 20),
                        linestyle=("-", "--", ":")[index // 20 % 3], label=labels[model])
            ax.plot([0, 1], [0, 1], color="black", linewidth=1, linestyle=":")
            ax.set(xlim=(0, 1), ylim=(0, 1), xlabel="Bin mean predicted probability", ylabel="Weighted observed outcome rate",
                   title="Matched cohort" if size is None else f"Native {size}×{size} cohort")
            ax.grid(alpha=.2)
            ax.legend(fontsize=6, ncol=2 if size is None else 1, loc="best")
        fig.suptitle(f"{split.capitalize()}: descriptive weighted reliability (no confidence intervals)", fontsize=13)
        fig.tight_layout(rect=(0, 0, 1, .96), w_pad=3)
        relative = f"figures/reliability_{split}.png"
        fig.savefig(destination / relative, dpi=110, facecolor="white")
        plt.close(fig)
        images.append(relative)
    return bins, images


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _format(row: dict[str, Any]) -> str:
    if row["status"] == "finite":
        return f"{row['finite_value']:.8g}"
    return {"undefined": "N/A", "missing": "missing", "positive_infinity": "+∞", "negative_infinity": "−∞"}[row["status"]]


def _markdown(rows: list[dict[str, Any]], names: list[str], models: list[str],
              labels: dict[str, str], figures: dict[str, str], reliability: list[str], *,
              asset_prefix: str, default_model: str) -> str:
    lines = ["## Complete evaluation metrics and graphs", "",
             "All scalar fields in saved `metrics.json` are reported below, including nested classification metrics, weighted ECE, thresholds, and support diagnostics. Every metric has a grouped bar graph and numerical values for training, validation, and test. Newly added scalar evaluation fields are discovered automatically.", "",
             "### All metrics at a glance", "",
             f"[Open the all-metric bar dashboard]({asset_prefix}overview.html). Select any model and either the matched or native cohort; all {len(names)} fields appear together. Use Larger charts for an expanded view. Each card retains raw values and its own scale. The initial model, **{labels[default_model]}**, comes from the saved validation selection.", "",
             f"![All numeric fields as bar charts for the saved validation-selected model]({asset_prefix}figures/overview_common.png)", "",
             f"[Scalable matched overview (SVG)]({asset_prefix}figures/overview_common.svg) · [Native overview (PNG)]({asset_prefix}figures/overview_native.png) · [Scalable native overview (SVG)]({asset_prefix}figures/overview_native.svg)", "",
             "**Comparison populations.** Matched results compare all models on identical current 3×3-contact rows with their original inverse inclusion weights. Native results use each model's own K-contact population; compare families within the same K. Full prediction coverage describes all base rows and is separate from both scoring populations. Training, validation, and test are reported separately; their split construction is defined by the saved training protocol. Each graph keeps these populations separate, with independent horizontal axis scales and a zero bar baseline.", "",
             "**Probability reference.** For row i, yᵢ ∈ {0,1} is the reconstructed next-hour outcome, pᵢ ∈ [0,1] is the saved prediction, and wᵢ > 0 is its original sampling weight. The Bernoulli reference is Pᵢ=(1−yᵢ,yᵢ), the prediction is Qᵢ=(1−pᵢ,pᵢ), and every distance mean is Σᵢwᵢd(Pᵢ,Qᵢ)/Σᵢwᵢ. These compare predictions with binary empirical outcomes, not a known true conditional-probability field or two models. They do not measure spatial fire-front displacement. The endpoint is first-new-burning in the next hour, not currently active flame.", "",
             "| Quantity per row | Definition |", "|---|---|",
             "| Exact KL | ΣₓPᵢ(x) ln(Pᵢ(x)/Qᵢ(x)); equals exact NLL for binary yᵢ |",
             "| Floored KL | Same directed KL after clipping pᵢ to [ε,1−ε]; equals floored log loss for binary yᵢ; ε is reported below |",
             "| Total variation | ½Σₓ&#124;Pᵢ(x)−Qᵢ(x)&#124; = &#124;yᵢ−pᵢ&#124; |",
             "| Hellinger | √(½Σₓ(√Pᵢ(x)−√Qᵢ(x))²) |",
             "| Jensen-Shannon divergence | ½KL(Pᵢ ∥ Mᵢ)+½KL(Qᵢ ∥ Mᵢ), Mᵢ=(Pᵢ+Qᵢ)/2 |",
             "| Jensen-Shannon distance | Square root of each row's JS divergence, then weighted averaging |",
             "| Bhattacharyya | −ln(Σₓ√(Pᵢ(x)Qᵢ(x))) |",
             "| Wasserstein-1 / Wasserstein-2 | &#124;yᵢ−pᵢ&#124; / √&#124;yᵢ−pᵢ&#124; for support {0,1} with unit ground distance |", "",
             "Natural logarithms give divergences and log loss in nats. Exact zero-probability failures remain +∞ in tables and graph status columns. N/A means the evaluator returned an undefined result; missing means that field was not saved for that model/split. Neither is changed to zero. Bounded distances may reward low probabilities in an imbalanced population; retain Brier, log loss, positive-class scores, ranking, and classification results when interpreting them. No test data are used to reselect models or thresholds.", "",
             "**Classification.** Decisions use pᵢ ≥ threshold. Threshold 0.5 and the separately validation-selected F1 and MCC thresholds are reported explicitly and applied unchanged to all splits. TP, FP, TN, and FN are weighted population counts; precision=TP/(TP+FP), recall=TP/(TP+FN), F1=2TP/(2TP+FP+FN), and MCC=(TP·TN−FP·FN)/√((TP+FP)(TP+FN)(TN+FP)(TN+FN)). The evaluator assigns zero when a classification denominator is zero. Average precision is non-interpolated; PR AUC uses trapezoidal integration. They are different metrics.", "",
             f"[All metric cells as CSV]({asset_prefix}metrics.csv) · [All reliability-bin values as CSV]({asset_prefix}calibration_bins.csv) · [Cohort summaries as CSV]({asset_prefix}cohorts.csv) · [Coverage and file hashes]({asset_prefix}manifest.json)", ""]
    for group in GROUPS:
        group_names = [key for key in names if _category(key) == group]
        if not group_names:
            continue
        lines += [f"### {group}", ""]
        for key in group_names:
            cells = [row for row in rows if row["metric"] == key]
            lookup = {(row["model"], row["scope"], row["split"]): row for row in cells}
            full = key.startswith("coverage.")
            lines += [f"#### {_title(key)}", "", f"Saved field: `{key}`. {_direction(key)}.", "",
                      f"![{_title(key)} across models and splits]({asset_prefix}{figures[key]})", ""]
            if full:
                lines += ["| Model | Train: full rows | Validation: full rows | Test: full rows |", "|---|---:|---:|---:|"]
            else:
                lines += ["| Model | Native K | Matched train | Matched validation | Matched test | Native train | Native validation | Native test |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
            for model in models:
                first = lookup[model, "full_prediction" if full else "common", "test"]
                scopes = ("full_prediction",) if full else ("common", "native")
                values = [_format(lookup[model, scope, split]) for scope in scopes for split in evaluation_SPLITS]
                text = f"{labels[model]} (`{model}`)".replace("|", "\\|")
                lines.append(f"| {text} | " + ("" if full else f"{first['kernel_size']} | ") + " | ".join(values) + " |")
            lines.append("")
    lines += ["### Reliability curves and calibration bins", "",
              "Each point is a populated, prespecified probability bin. Its horizontal coordinate is the weighted mean prediction and its vertical coordinate is the weighted observed outcome rate. Empty bins are retained in the bin CSV and create gaps in curves. The diagonal represents equal predicted and observed bin means. These are descriptive pooled summaries without confidence intervals or independent-cell assumptions. ECE is Σ_b(W_b/W)\u007cp̄_b−ȳ_b\u007c and appears above as a scalar metric.", ""]
    for relative in reliability:
        lines += [f"![Weighted reliability by evaluation population]({asset_prefix}{relative})", ""]
    return "\n".join(lines)


def _append_report(path: Path, section: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else "# Probability-model comparison\n"
    if (START in existing) != (END in existing):
        raise ValueError("Incomplete generated evaluation markers in report.md")
    block = f"{START}\n{section}\n{END}"
    if START in existing:
        before, tail = existing.split(START, 1)
        _, after = tail.split(END, 1)
        updated = before + block + after
    else:
        updated = existing.rstrip() + "\n\n" + block + "\n"
    if existing != updated:
        path.write_text(updated, encoding="utf-8")


def _linked_supplement(section: str) -> str:
    for prefix in ("figures/", "overview.html)", "metrics.csv)", "calibration_bins.csv)", "cohorts.csv)", "manifest.json)"):
        section = section.replace(f"]({prefix}", f"](evaluation/{prefix}")
    return section


def _insert_overview(path: Path, model_label: str, field_count: int) -> None:
    """Put the overview before the existing analysis, without duplicating it."""
    existing = path.read_text(encoding="utf-8")
    notice = "\n\n**Generated-control verification only.** Its split values repeat because the fixtures reuse identical features, outcomes, and weights." if "generated-control" in existing.splitlines()[0].lower() else ""
    section = (f"{OVERVIEW_START}\n## Evaluation metrics at a glance{notice}\n\n"
               f"[Open all {field_count} metrics in the bar dashboard](evaluation/overview.html). "
               f"Select a model and cohort to see training, validation, and test together. "
               f"The static overview below uses the saved validation-selected model, **{model_label}**.\n\n"
               "![All evaluation metrics as bar charts](evaluation/figures/overview_common.png)\n\n"
               "[Scalable overview (SVG)](evaluation/figures/overview_common.svg) · "
               "[Native-cohort overview](evaluation/figures/overview_native.png)\n"
               f"{OVERVIEW_END}")
    if (OVERVIEW_START in existing) != (OVERVIEW_END in existing):
        raise ValueError("Incomplete overview markers in report.md")
    if OVERVIEW_START in existing:
        before, tail = existing.split(OVERVIEW_START, 1)
        _, after = tail.split(OVERVIEW_END, 1)
        updated = before + section + after
    else:
        first_line, _, rest = existing.partition("\n")
        updated = first_line + "\n\n" + section + "\n\n" + rest.lstrip("\n")
    if existing != updated:
        path.write_text(updated, encoding="utf-8")


def generate_evaluation_report(run_directory: Path | str) -> dict[str, Any]:
    """Add complete tables/figures to a completed run; keep scoring inputs intact.

    Existing assets are reused only if the saved inputs, this reporter's source,
    and every generated asset match their recorded SHA-256 values. This avoids
    rebuilding dozens of figures on a normal completed-run resume.
    """
    root = Path(run_directory).resolve()
    complete = json.loads((root / "complete.json").read_text(encoding="utf-8"))
    if complete.get("completed") is not True:
        raise ValueError("Report generation requires a completed comparison")
    sources = {name: _sha256(root / name) for name in ("metrics.json", "selection.json", "protocol.json", "complete.json")}
    reporter_sha = _sha256(Path(__file__))
    metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
    selection = json.loads((root / "selection.json").read_text(encoding="utf-8"))
    if selection.get("test_used_for_selection") is not False:
        raise ValueError("A comparison must explicitly record validation-before-test selection")
    rows, names, models = collect_metrics(metrics)
    labels = _labels(selection, models)
    default_model = _overview_model(selection, models)
    # A resumed finalist restores the same tensor values through torch.save,
    # which can change serialized checkpoint/selection hashes. Plot inputs
    # remain identical in that case; refresh provenance and reuse the assets.
    render_sha = hashlib.sha256(json.dumps(dict(metrics=sources["metrics.json"],
        protocol=sources["protocol.json"], labels=labels), sort_keys=True).encode("utf-8")).hexdigest()
    destination = root / "evaluation"
    manifest_path = destination / "manifest.json"
    if manifest_path.exists():
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (saved.get("render_sha256") == render_sha and saved.get("reporter_sha256") == reporter_sha and
                saved.get("asset_sha256") and all((destination / name).is_file() and
                _sha256(destination / name) == digest for name, digest in saved["asset_sha256"].items())):
            if saved["source_sha256"] != sources:
                saved["source_sha256"] = sources
                manifest_path.write_text(json.dumps(saved, indent=2, allow_nan=False) + "\n", encoding="utf-8")
            _append_report(root / "report.md", _linked_supplement((destination / "report.md").read_text(encoding="utf-8")))
            _insert_overview(root / "report.md", labels[default_model], len(names))
            return saved
    (destination / "figures").mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figures = {}
    for index, key in enumerate(names):
        relative = f"figures/{index + 1:03d}_{re.sub(r'[^a-zA-Z0-9_]+', '_', key)}.png"
        _draw_metric(plt, destination / relative, key, [row for row in rows if row["metric"] == key], models, labels)
        figures[key] = relative
    bins, reliability = _calibration_assets(plt, destination, metrics, models, labels)
    overview_figures, overview_vectors = _overview_assets(plt, destination, rows, names, models, labels, default_model)
    _write_csv(destination / "metrics.csv", rows)
    _write_csv(destination / "calibration_bins.csv", bins)
    cohorts = []
    for split in evaluation_SPLITS:
        for scope, summary in [("common", metrics[split].get("common_cohort", {}))] + [
                (f"native_k{size}", summary) for size, summary in metrics[split].get("native_cohorts", {}).items()]:
            cohorts.append(dict(split=split, scope=scope, **flatten_metrics(summary)))
    _write_csv(destination / "cohorts.csv", cohorts)
    section = _markdown(rows, names, models, labels, figures, reliability, asset_prefix="", default_model=default_model)
    (destination / "report.md").write_text(section, encoding="utf-8")
    _append_report(root / "report.md", _linked_supplement(section))
    _insert_overview(root / "report.md", labels[default_model], len(names))
    if any(_sha256(root / name) != digest for name, digest in sources.items()):
        raise ValueError("Saved evaluation inputs changed during report generation")
    assets = ["report.md", "metrics.csv", "calibration_bins.csv", "cohorts.csv", "overview.html",
              *figures.values(), *reliability, *overview_figures.values(), *overview_vectors.values()]
    manifest = dict(schema_version=2, chart_style="grouped_bars", source_sha256=sources, reporter_sha256=reporter_sha, render_sha256=render_sha,
                    asset_sha256={name: _sha256(destination / name) for name in assets},
                    metric_count=len(names), metric_cell_count=len(rows), evaluated_models=len(models),
                    scalar_metrics=names, figures=figures, reliability_figures=reliability,
                    overview_dashboard="overview.html", overview_model=default_model,
                    overview_figures=overview_figures, overview_vectors=overview_vectors,
                    splits=list(evaluation_SPLITS), scopes=["common", "native", "full_prediction"],
                    graph_covers_every_scalar_metric=set(names) == set(figures),
                    predictions_refitted=False, thresholds_reselected=False,
                    metric_status_counts={status: sum(row["status"] == status for row in rows) for status in (
                        "finite", "undefined", "missing", "positive_infinity", "negative_infinity")})
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return manifest


def evaluation_main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path, help="Completed kernel-search output containing metrics.json")
    args = parser.parse_args()
    manifest = generate_evaluation_report(args.run_directory)
    print(json.dumps(dict(report=str(args.run_directory.resolve() / "report.md"),
                          evaluated_models=manifest["evaluated_models"], scalar_metrics=manifest["metric_count"],
                          metric_figures=len(manifest["figures"]), reliability_figures=len(manifest["reliability_figures"]),
                          overview=str(args.run_directory.resolve() / "evaluation" / manifest["overview_dashboard"])), indent=2))




# Report
# Inspect active nonnegative exponential kernels and random forest baselines.

matplotlib.use('Agg')

LABELS = {'ours_original_5': 'Nonnegative exponential kernel 5×5',
          'rf_3': 'Published-family RF 3×3', 'rf_5': 'Matched-input RF 5×5',
          'control_train_prevalence': 'Train prevalence', 'control_no_spread': 'No spread (p=0)'}
ORDER = list(LABELS)
report_COLORS = ['#2563eb', '#f59e0b', '#b45309', '#6b7280', '#b5b9c2']


def display(value):
    if value == 'infinity':
        return '∞'
    if isinstance(value, (int, np.integer)):
        return f'{value:,}'
    return '—' if value is None else f'{value:.6f}'


def _table(models, headings, fields):
    lines = ['| Model | ' + ' | '.join(headings) + ' |', '| --- | ' + ' | '.join('---:' for _ in fields) + ' |']
    for name in ORDER:
        if name in models:
            lines.append('| ' + LABELS[name] + ' | ' + ' | '.join(display(models[name].get(field)) for field in fields) + ' |')
    return '\n'.join(lines)


def table(models):
    return _table(models, ['Samples', 'Weighted Brier ↓', 'AP ↑', 'ROC AUC ↑', 'Exact log loss / KL ↓', 'Floored log loss / KL ↓', 'Positive targets at p=0'],
                  ['sample_count', 'brier', 'average_precision', 'roc_auc', 'exact_negative_log_likelihood_mean', 'clipped_log_loss', 'unsupported_positive_sample_count'])


def classification_table(models):
    return _table(models, ['PR AUC ↑', 'AP ↑', 'F1 at 0.5 ↑', 'MCC at 0.5 ↑', 'Validation-threshold F1 ↑', 'Validation-threshold MCC ↑'],
                  ['precision_recall_auc', 'average_precision', 'f1_at_0_5', 'mcc_at_0_5', 'f1_at_validation_f1_threshold', 'mcc_at_validation_mcc_threshold'])


def distance_table(models):
    return _table(models, ['TV = W1 ↓', 'Hellinger ↓', 'JS divergence ↓', 'JS distance ↓', 'Bhattacharyya ↓', 'W2 ↓'],
                  ['bernoulli_total_variation_distance_mean', 'bernoulli_hellinger_distance_mean', 'bernoulli_jensen_shannon_divergence_mean',
                   'bernoulli_jensen_shannon_distance_mean', 'bernoulli_bhattacharyya_distance_mean', 'bernoulli_wasserstein_2_distance_mean'])


def _plots(directory, shared):
    names = [name for name in ORDER if name in shared['models'] and name != 'control_no_spread']
    learned = [name for name in names if not name.startswith('control_')]
    colors = dict(zip(ORDER, report_COLORS))
    specifications = [('comparison.png', [('brier', 'Weighted Brier · lower is better'), ('average_precision', 'Weighted AP · higher is better')], names),
                      ('classification_comparison.png', [('precision_recall_auc', 'Weighted PR AUC'), ('f1_at_validation_f1_threshold', 'F1 · validation threshold'), ('mcc_at_validation_mcc_threshold', 'MCC · validation threshold')], learned),
                      ('distance_comparison.png', [('bernoulli_total_variation_distance_mean', 'Mean TV = binary W1'), ('bernoulli_hellinger_distance_mean', 'Mean Hellinger'), ('bernoulli_jensen_shannon_divergence_mean', 'Mean JS divergence · nats')], learned)]
    for filename, metrics, selected in specifications:
        fig, axes = plt.subplots(1, 3, figsize=(16, 5), constrained_layout=True)
        for ax, (metric, title) in zip(axes, metrics):
            values = [shared['models'][name].get(metric) for name in selected]
            bars = ax.bar(np.arange(len(selected)), [np.nan if value is None else value for value in values], color=[colors[name] for name in selected])
            ax.bar_label(bars, fmt='%.4f', padding=4, fontsize=9)
            ax.set_xticks(np.arange(len(selected)), [LABELS[name].replace(' ', '\n', 1) for name in selected], fontsize=8)
            ax.set_title(title, fontsize=10)
            ax.grid(axis='y', alpha=.2)
            ax.set_axisbelow(True)
        if filename == 'comparison.png':
            for name in learned:
                bins = [entry for entry in shared['calibration'][name]['bins'] if entry['sample_count']]
                axes[2].plot([entry['mean_probability'] for entry in bins], [entry['weighted_outcome_rate'] for entry in bins], marker='o', color=colors[name], label=LABELS[name], markersize=4)
            axes[2].plot([0, 1], [0, 1], '--', color='#9ca3af')
            axes[2].set(xlim=(0, 1), ylim=(0, 1), xlabel='Mean predicted probability', ylabel='Weighted observed transition rate', title='Shared-test reliability')
            axes[2].legend(fontsize=7)
        fig.suptitle(f"One-hour reconstructed transitions · {shared['sample_count']:,} matched contact cell-hours")
        fig.savefig(directory / filename, dpi=170)
        plt.close(fig)


def _export_csv(directory, data):
    scalar_fields = sorted({field for scope in ('shared', 'native') for entry in data[scope].values()
                            for name, metrics in entry['models'].items() if name in ORDER
                            for field, value in metrics.items() if not isinstance(value, (dict, list))})
    for filename, per_event in (('metrics.csv', False), ('per_event_metrics.csv', True)):
        prefix = ['scope', 'split', 'model'] + (['event', 'country'] if per_event else [])
        with (directory / filename).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=prefix + scalar_fields)
            writer.writeheader()
            for scope in ('shared', 'native'):
                for split, entry in data[scope].items():
                    records = entry['per_event'].items() if per_event else [(None, entry)]
                    for event, record in records:
                        for name in ORDER:
                            if name not in record['models']:
                                continue
                            metric = record['models'][name]
                            row = {'scope': scope, 'split': split, 'model': name, **{field: metric.get(field) for field in scalar_fields}}
                            if per_event:
                                row.update(event=event, country=record['country'])
                            writer.writerow(row)


def generate_report(directory):
    directory = Path(directory).resolve()
    data = json.loads((directory / 'metrics.json').read_text())
    selection, protocol = data['selection'], data['protocol']
    shared, native = data['shared']['test'], data['native']['test']
    ours, rf = shared['models']['ours_original_5'], shared['models']['rf_5']
    lines = ['# Nonnegative exponential kernel and random forest comparison', '',
             f"On the matched shared test cohort, the exponential 5×5 kernel has weighted Brier **{display(ours['brier'])}** and matched-input RF5 has **{display(rf['brier'])}**. These are fixed fitted models evaluated against reconstructed one-hour transitions.", '',
             '![Probability, ranking and reliability comparison](comparison.png)', '',
             '## Target, sampling and contact scope', '',
             'The target is a known currently unburned cell that becomes reconstructed burned exactly one hour later. Current burned inputs are cumulative burned area. Every metric requires at least one previously burned off-center source inside that model’s kernel range. Complete no-contact patches remain supported prediction inputs; metric filtering does not make their predictions unavailable.', '',
             f"The matched cohort contains **{shared['sample_count']:,} cell-hours**, **{shared['positive_sample_count']:,} positives**, and **{shared['contributing_fires']} fires**. It comes from one frozen 9×9 cache, requires complete known 9×9 context and contact inside the central 3×3, and retains original identities and inverse inclusion weights. All models use identical labels and weights here.", '',
             '## Baseline and validation selection', '',
             'The forest family adapts [Huot et al., Next Day Wildfire Spread](https://research.google/pubs/next-day-wildfire-spread-a-machine-learning-dataset-to-predict-wildfire-spreading-from-remote-sensing-data/). The published endpoint is next-day active fire at 1 km; this experiment uses one-hour cumulative burned transitions at 375 m. RF3 follows the published footprint and RF5 matches the exponential kernel’s support. Ordered environmental features and the current burned mask are predictors. Future state, outcome, event identity, row and column are excluded from predictors.', '',
             f"Forests fit {selection['training_sample_count']:,} native 5×5 training rows from {selection['training_event_count']} fires. Weighted training prevalence is {selection['training_weighted_prevalence']:.6%}. RF3 crops the same rows and may see no-contact patches in training. Original inverse inclusion weights divided by their mean retain relative population weighting. Trees use raw environmental features and the fixed category vocabulary.", '',
             f"Each forest uses {protocol['n_estimators']} trees and seed {protocol['seed']}. Depth grid: {protocol['depth_grid']}. Selection minimizes shared weighted validation Brier separately per support; shallower depths break exact ties. The saved selection precedes test loading. The exponential checkpoint is frozen from its earlier validation selection.", '',
             '| Forest | Selected depth | Features | Shared validation Brier |', '| --- | ---: | ---: | ---: |']
    for name in ('rf_3', 'rf_5'):
        entry = selection['selected'][name]
        lines.append(f"| {LABELS[name]} | {entry['max_depth']} | {entry['n_features']} | {entry['validation_brier']:.6f} |")
    lines.extend(['', '## Matched contact test metrics', '', table(shared['models']), '',
                  'Brier and Bernoulli log loss are probability scores. AP is non-interpolated weighted average precision; PR AUC below uses trapezoidal interpolation. Exact log loss retains endpoint probabilities: y=1 with p=0, or y=0 with p=1, makes it infinite. Floored log loss uses clip(p,10⁻⁷,1−10⁻⁷) only for that diagnostic. KL(observed Bernoulli || predicted Bernoulli) equals exact log loss for binary outcomes. The true conditional probability field is not observed.', '',
                  classification_table(shared['models']), '',
                  'Classification decisions are positive iff p ≥ threshold. The fixed threshold is 0.5. Model-specific F1 and MCC thresholds are selected separately on shared validation and applied unchanged to test and fire/country groups. Confusion counts retain inverse inclusion weights. Zero denominators return zero; ties select the higher validation threshold.', '',
                  '![Classification metrics](classification_comparison.png)', '', distance_table(shared['models']), '',
                  'TV and binary W1 equal |y−p|. W2 equals √|y−p| on outcome states {0,1} with unit ground distance. Hellinger uses √(½Σ(√P−√Q)²). JS divergence is the half-sum of KL to (P+Q)/2; JS distance applies its square root per cell before averaging. Bhattacharyya is −lnΣ√(PQ), equal to half of exact log loss for binary observed targets. Each metric is an inverse-inclusion-weighted mean of per-cell distances. These diagnostics do not all define proper probability scores and do not measure geographic displacement.', '',
                  '![Statistical distances](distance_comparison.png)', ''])
    for name, entry in shared.get('paired_event_bootstrap_brier', {}).items():
        if name in ORDER and entry['reference'] == 'ours_original_5':
            lo, hi = entry['percentile_95_interval']
            lines.extend([f"{LABELS[name]} minus exponential-kernel Brier: {entry['point_difference']:.6f}; paired whole-fire bootstrap 95% percentile interval [{lo:.6f}, {hi:.6f}], using {entry['draws']:,} draws. Positive differences favor the exponential kernel. This conditions on fixed predictions and reconstructed labels; initial sampling and reconstruction uncertainty are excluded.", ''])
    lines.extend(['## Native footprint contact test metrics', '',
                  f"The native5 test archive contains {native['sample_count']:,} cell-hours. Each model’s metrics retain only current-contact rows within its own footprint, so per-model sample counts can differ. This table describes coverage; the shared table is the matched comparison. Predictions remain stored for all supplied native rows.", '',
                  table(native['models']), '', classification_table(native['models']), '', distance_table(native['models']), '',
                  '## Scientific limits and verification', '',
                  'Labels are retrospective hourly reconstructions inside known final perimeters, rather than independent hourly observations. Current reconstructed burned state is supplied anew for every prediction; recursive rollout is not evaluated. Unknown context and boundary targets are excluded. Historic test fires have already been inspected during earlier development; this is not a new blind external validation. Metrics include per-fire and per-country results.', '',
                  'Cell-hour identity, labels and original weights are bound to source archives. Exponential shared probabilities are recomputed with the frozen checkpoint. Forest round-trip verification compares tree parameters exactly and probabilities within absolute tolerance 10⁻¹². Source hashes and executed code snapshots are saved with each new run.', '',
                  '## Prediction use', '', '```python', 'from wildfire.models import PatchRandomForest',
                  f"forest = PatchRandomForest.load({str(directory / 'rf_5.joblib')!r})", "probability = forest.predict_probability(environment, burned, channel_names=forest.contract['channels'], dt_hours=1.0)", '```', '',
                  'Patch prediction returns one probability per complete known currently unburned input patch, including no-contact patches. It uses saved channel ordering and does not refit preprocessing. Only load trusted local joblib artifacts.'])
    (directory / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    _export_csv(directory, data)
    _plots(directory, shared)


