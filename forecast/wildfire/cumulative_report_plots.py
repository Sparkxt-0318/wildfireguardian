"""Scientific plots for pooled cumulative comparisons, including forests.

All-model panels retain every checkpoint. A deterministic subset is used only
for readable detailed panels; it never changes evaluation cohorts or scores.
Undefined values and infinite exact losses are shown separately from finite
numeric axes. No uncertainty intervals for evaluation metrics are inferred.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import textwrap

import numpy as np

MAX_DETAIL_MODELS = 20
MAX_RELIABILITY_MODELS = 8
MAX_CURVE_MODELS = 8


def _number(value):
    """Retain infinity while representing missing/undefined values as NaN."""
    if value is None or isinstance(value, (bool, np.bool_)):
        return math.nan
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _value(row, section, key):
    return _number(row.get(section, {}).get(key)) if row else math.nan


def _family(model):
    return str(model.get("architecture") or model.get("contract", {}).get("architecture") or "Unspecified")


def _family_label(name):
    aliases = {
        "EnvironmentConditionedConvolution": "Environment-conditioned CNN",
        "BayesianKernelAverage": "Bayesian kernel average",
        "RandomForestClassifier": "Random forest",
        "HuotRandomForest": "Huot-style random forest",
    }
    return aliases.get(name, name)


def _priority(family):
    lower = family.lower()
    return 0 if "forest" in lower or "random_forest" in lower else 1 if "bayes" in lower else 2


def _select(rows, families, maximum):
    """One representative per architecture first, then lowest finite Brier.

    Forest and Bayesian architectures take priority if there are more families
    than display slots. Missing/undefined Brier is ordered after finite scores.
    The model id breaks all ties, making selection independent of input order.
    """
    def key(model_id):
        score = _value(rows.get(model_id), "metrics", "brier")
        return (score if math.isfinite(score) else math.inf, model_id)

    ranked = sorted(rows, key=key)
    architectures = sorted({families[model_id] for model_id in ranked}, key=lambda name: (_priority(name), name))
    selected = []
    for architecture in architectures:
        candidates = [model_id for model_id in ranked if families[model_id] == architecture]
        if candidates and len(selected) < maximum:
            selected.append(candidates[0])
    for model_id in ranked:
        if model_id not in selected and len(selected) < maximum:
            selected.append(model_id)
    return sorted(selected, key=key)


def _threshold_curves(y, probability):
    """Exact equal-weight pooled curves, grouping tied scores simultaneously."""
    y, probability = np.asarray(y), np.asarray(probability, dtype=np.float64)
    if y.ndim != 1 or probability.shape != y.shape:
        raise ValueError("Curve entries must have matching one-dimensional target/probability arrays")
    if not np.isin(y, (0, 1)).all() or not np.isfinite(probability).all() or np.any((probability < 0) | (probability > 1)):
        raise ValueError("Curve entries must contain binary targets and finite probabilities in [0,1]")
    positive, negative = int(np.count_nonzero(y)), int(np.count_nonzero(y == 0))
    if not len(y):
        return dict(roc=None, pr=None, positive_count=0, negative_count=0)
    order = np.argsort(-probability, kind="stable")
    scores = probability[order]
    target = y[order].astype(np.int64)
    last = np.r_[np.flatnonzero(np.diff(scores) != 0), len(scores) - 1]
    tp = np.cumsum(target, dtype=np.int64)[last]
    fp = (last + 1) - tp
    roc = None if not positive or not negative else (np.r_[0., fp / negative], np.r_[0., tp / positive])
    # AP is the integral of the descending-threshold precision step function;
    # the PR line is drawn as steps, never substituted for the stored AP score.
    pr = None if not positive else (np.r_[0., tp / positive], np.r_[1., tp / (tp + fp)])
    return dict(roc=roc, pr=pr, positive_count=positive, negative_count=negative)


def generate_report_plots(report, output_dir, *, stores=None):
    """Write PNG/SVG figures and return a JSON-serializable plot manifest.

    ``report`` is the cumulative runner's report. ``stores`` optionally maps
    ``(model_index, cohort, quantity)`` to stores with ``entries()`` returning
    ``{'y': target, 'p': probability}``. Curves use the complete shared-model
    entries, without resampling or reducing the pooled scoring cohort.

    Figures use pooled equal-cell-cutoff scores. Detailed display selection
    uses Brier ranking with architecture representatives; this is descriptive
    presentation only and must not be interpreted as checkpoint selection or
    calibration using these outcomes. All-model panels and the index retain
    the full inventory. Pointwise Monte Carlo intervals are not metric CIs.
    """
    import matplotlib as mpl
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.lines import Line2D

    output = Path(output_dir)
    directory = output / "plots"
    directory.mkdir(parents=True, exist_ok=True)
    models = report.get("models", [])
    known = {str(model["model_id"]): model for model in models}
    for row in report.get("summary", []):
        known.setdefault(str(row["model_id"]), dict(model_id=str(row["model_id"]), architecture="Unspecified"))
    ids = sorted(known)
    plot_context = report.get("plot_context", {})
    model_labels = plot_context.get("model_labels", {})
    codes = {model_id: str(model_labels.get(model_id, f"M{position + 1:03d}")) for position, model_id in enumerate(ids)}
    families = {model_id: _family(known[model_id]) for model_id in ids}
    architecture_names = sorted(set(families.values()))
    palette = mpl.colormaps["tab20"]
    colors = {name: palette(index % 20) for index, name in enumerate(architecture_names)}
    protocol = report.get("protocol", {})
    hours, samples = protocol.get("hours", "?"), protocol.get("n_samples", "?")
    interval_label = str(plot_context.get("interval_label", f"{hours}-hour"))
    deterministic = protocol.get("method") == "deterministic_farsite"
    model_noun = str(plot_context.get("model_noun", "scenarios" if deterministic else "checkpoints"))
    process_label = str(plot_context.get("process_label", "deterministic FARSITE scenario" if deterministic else "recursive probability"))
    reference_label = str(plot_context.get("reference_label", "Observed outcome fraction"))
    reference_description = str(plot_context.get("reference_description", "binary observed outcome"))
    index_label = str(plot_context.get("model_index_label", ("Scenario index" if deterministic else "Checkpoint index") + " (M### in model_index.csv)"))
    sampling_label = str(plot_context.get("sampling_label", "One deterministic simulator run per cutoff; 0/1 scenario predictions. No Monte Carlo intervals." if deterministic else f"N = {samples} trajectories per cutoff."))
    manifest = dict(
        directory="plots", model_count=len(ids), figures={}, selections={},
        model_index="plots/model_index.csv",
        cohort="shared_models",
        pooling="equal-cell-cutoff entries pooled before scoring; event scores separately pooled within event",
        display_selection=f"At most 20 {model_noun}: lowest Brier within each architecture (forest/Bayesian families first if needed), then lowest remaining Brier; id breaks ties. Display only, no fitting or model selection.",
        numeric_policy="Finite values use numeric axes; triangles outside the finite axis mark infinity; crosses outside the axis mark undefined/missing. Values are never replaced with zero or finite loss caps.",
        uncertainty=("One deterministic FARSITE scenario supplies 0/1 predictions; no Monte Carlo or metric confidence intervals." if deterministic else "Descriptive evaluation scores and reliability bins; no confidence intervals for evaluation metrics. Pointwise simulation intervals describe Monte Carlo error only."),
        distance_space="Per-cell Bernoulli outcome distributions on {0,1} with unit ground distance; not geographic transport or joint-map distance",
        prediction_kind=plot_context.get("prediction_kind", "deterministic_farsite_scenario" if deterministic else "recursive_monte_carlo"),
        plot_context=plot_context,
    )
    with (directory / "model_index.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["plot_id", "model_id", "architecture", "path"])
        writer.writeheader()
        for model_id in ids:
            writer.writerow(dict(plot_id=codes[model_id], model_id=model_id, architecture=families[model_id], path=known[model_id].get("path", "")))

    def figure(rows=1, columns=1, size=(13, 7)):
        fig = Figure(figsize=size, layout="constrained")
        FigureCanvasAgg(fig)
        return fig, fig.subplots(rows, columns, squeeze=False)

    def save(fig, stem, description, plotted_ids, **details):
        outputs = {}
        for extension in ("png", "svg"):
            path = directory / f"{stem}.{extension}"
            fig.savefig(path, dpi=150, facecolor="white", bbox_inches="tight", pad_inches=.12, metadata={"Creator": "wildfire cumulative evaluation"} if extension == "svg" else {"Software": "wildfire cumulative evaluation"})
            outputs[extension] = dict(path=f"plots/{path.name}", size_bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        manifest["figures"][stem] = dict(description=description, outputs=outputs, plotted_ids=list(plotted_ids), **details)
        fig.clear()

    def title(fig, label, quantity, extra=""):
        name = "Future new burns" if quantity == "new_burn" else "Total burned occupancy"
        fig.suptitle(f"{name} · {interval_label} {process_label}\n{label}{extra}", fontsize=16)

    def footer(fig, text):
        fig.supxlabel(text, fontsize=9)

    def families_legend(ax):
        handles = [Line2D([], [], color=colors[name], marker="o", linestyle="none", markersize=5, label=_family_label(name)) for name in architecture_names]
        if handles:
            ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(.5, -.18), ncol=min(4, len(handles)), fontsize=8)

    def annotate_nonfinite(ax, values, *, positions, horizontal=False):
        values = np.asarray(values, dtype=float)
        infinite, missing = np.isinf(values), np.isnan(values)
        if horizontal:
            transform = ax.get_yaxis_transform()
            for mask, marker, color, x in ((infinite, "^", "#c15100", 1.015), (missing, "x", "#666666", 1.055)):
                ax.scatter(np.full(mask.sum(), x), np.asarray(positions)[mask], transform=transform, marker=marker, c=color, s=30, clip_on=False)
        else:
            transform = ax.get_xaxis_transform()
            for mask, marker, color, y in ((infinite, "^", "#c15100", 1.025), (missing, "x", "#666666", -.055)):
                ax.scatter(np.asarray(positions)[mask], np.full(mask.sum(), y), transform=transform, marker=marker, c=color, s=16, clip_on=False)
        ax.text(.99, .98, f"infinite: {infinite.sum()}\nundefined: {missing.sum()}", transform=ax.transAxes, ha="right", va="top", fontsize=8, bbox=dict(facecolor="white", alpha=.85, edgecolor="none"))

    if not report.get("summary"):
        fig, axes = figure(size=(10, 4))
        axes[0, 0].axis("off")
        axes[0, 0].text(.5, .5, "No pooled evaluation results\nNo metric values or model rankings are available.", ha="center", va="center", fontsize=15)
        fig.suptitle(f"Cumulative evaluation · {plot_context.get('interval_label', f'{hours} hours')}", fontsize=16)
        save(fig, "no_results", "Empty evaluation report; no scores are synthesized.", [])

    style = {"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.alpha": .18, "svg.fonttype": "none"}
    with mpl.rc_context(style):
        for quantity in ("new_burn", "burned"):
            rows = {str(row["model_id"]): row for row in report.get("summary", []) if row.get("cohort") == "shared_models" and row.get("quantity") == quantity}
            if not rows:
                continue
            # Include every declared checkpoint in overview panels, even if a
            # metric or a pooled row is missing. Absence stays visible as NaN.
            detail = _select(rows, families, MAX_DETAIL_MODELS)
            reliability_ids = _select(rows, families, MAX_RELIABILITY_MODELS)
            manifest["selections"][quantity] = dict(detail_ids=detail, reliability_ids=reliability_ids, omitted_detail_ids=[model_id for model_id in ids if model_id not in detail], all_model_ids=ids)
            overview = (
                ("metrics", "brier", "Brier score ↓"),
                ("metrics", "average_precision", "Average precision ↑"),
                ("metrics", "roc_auc", "ROC AUC ↑ (requires both classes)"),
                ("metrics", "clipped_log_loss", "Probability-floored NLL ↓ (nats)"),
                ("calibration", "weighted_expected_calibration_error", "Fixed-bin calibration error ↓"),
                ("metrics", "exact_negative_log_likelihood_mean", "Exact NLL ↓ (nats; may be infinite)"),
            )
            fig, axes = figure(2, 3, (16, 9))
            positions = np.arange(1, len(ids) + 1)
            brier_values = np.array([_value(rows.get(model_id), "metrics", "brier") for model_id in ids])
            finite_brier = brier_values[np.isfinite(brier_values)]
            brier_max = max(.005, float(finite_brier.max()) * 1.12) if len(finite_brier) else 1.
            for ax, (section, key, label) in zip(axes.flat, overview):
                values = np.array([_value(rows.get(model_id), section, key) for model_id in ids])
                finite = np.isfinite(values)
                ax.scatter(positions[finite], values[finite], c=[colors[families[model_id]] for model_id, yes in zip(ids, finite) if yes], s=13, alpha=.8, edgecolors="none")
                ax.set(title=label, xlabel=index_label, xlim=(.5, max(1.5, len(ids) + .5)))
                if model_labels:
                    ax.set_xticks(positions, [codes[model_id] for model_id in ids])
                ax.set_title(label, pad=19)
                if key in ("average_precision", "roc_auc"):
                    ax.set_ylim(-.035, 1.055)
                elif key in ("brier", "weighted_expected_calibration_error"):
                    finite_values = values[finite]
                    upper = max(.005, float(finite_values.max()) * 1.12) if len(finite_values) else 1.
                    ax.set_ylim(-.035 * upper, upper)
                else:
                    ax.set_ylim(bottom=0)
                annotate_nonfinite(ax, values, positions=positions)
            families_legend(axes[-1, 1])
            title(fig, f"All {len(ids)} {model_noun} · pooled shared-model cohort", quantity)
            footer(fig, f"{sampling_label} △ infinity and × undefined are outside numeric scales. No metric confidence intervals.\nEach model index is retained; exact losses remain distinct from probability-floored losses.")
            save(fig, f"{quantity}_metrics", f"Six pooled metrics for all {model_noun}, retaining infinite/undefined values distinctly.", ids, quantity=quantity, metric_keys=[key for _, key, _ in overview])

            fig, axes = figure(1, 2, (16, max(5.5, len(architecture_names) * .45 + 2)))
            ax = axes[0, 0]
            for index, family in enumerate(architecture_names):
                members = [model_id for model_id in ids if families[model_id] == family]
                values = np.array([_value(rows.get(model_id), "metrics", "brier") for model_id in members])
                valid = np.isfinite(values)
                if valid.any():
                    # Deterministic offsets expose points; no random state is used.
                    offsets = np.linspace(-.16, .16, valid.sum())
                    ax.scatter(values[valid], index + offsets, s=18, color=colors[family], alpha=.7, zorder=3)
                    ax.boxplot(values[valid], positions=[index], vert=False, widths=.5, showfliers=False, manage_ticks=False, medianprops=dict(color="black"))
            ax.set_yticks(range(len(architecture_names)), [_family_label(name) + f" (n={sum(families[model_id] == name for model_id in ids)})" for name in architecture_names], fontsize=9)
            ax.set(xlabel="Brier score ↓", title="Architecture distributions · each finite score shown", xlim=(-.02 * brier_max, brier_max))
            ax.invert_yaxis()
            ax = axes[0, 1]
            undefined_pairs = 0
            for family in architecture_names:
                pairs = np.array([[_value(rows.get(model_id), "metrics", "brier"), _value(rows.get(model_id), "metrics", "average_precision")] for model_id in ids if families[model_id] == family])
                valid = np.isfinite(pairs).all(axis=1)
                undefined_pairs += int((~valid).sum())
                ax.scatter(pairs[valid, 0], pairs[valid, 1], c=[colors[family]], s=24, alpha=.65, label=_family_label(family))
            ax.set(xlabel="Brier score ↓", ylabel="Average precision ↑", title="All finite Brier/AP pairs", xlim=(-.035 * brier_max, brier_max), ylim=(-.035, 1.035))
            ax.text(.98, .02, f"Undefined pairs: {undefined_pairs}", transform=ax.transAxes, ha="right", fontsize=9)
            ax.legend(fontsize=8, loc="best")
            title(fig, "Architecture comparison · shared-model cohort", quantity)
            footer(fig, f"Box plots describe distributions over {model_noun}, not uncertainty intervals. Undefined scores are excluded from distributions and counted in the all-model overview.")
            save(fig, f"{quantity}_architectures", f"All finite scores by architecture, plus Brier/AP scatter; box plots describe distributions over {model_noun}.", ids, quantity=quantity)

            distances = (
                ("bernoulli_total_variation_distance_mean", "Total variation = Wasserstein-1 ↓"),
                ("bernoulli_hellinger_distance_mean", "Mean Hellinger distance ↓"),
                ("bernoulli_jensen_shannon_divergence_mean", "Mean Jensen–Shannon divergence ↓ (nats)"),
                ("bernoulli_jensen_shannon_distance_mean", "Mean Jensen–Shannon distance ↓ (√nats)"),
                ("bernoulli_wasserstein_2_distance_mean", "Mean Wasserstein-2 distance ↓"),
                ("bernoulli_kl_divergence_mean", "Mean exact KL divergence ↓ (nats)"),
                ("floored_bernoulli_kl_divergence_mean", "Mean probability-floored KL ↓ (nats)"),
                ("bernoulli_bhattacharyya_distance_mean", "Mean Bhattacharyya distance ↓ (nats)"),
            )
            fig, axes = figure(2, 4, (21, max(9, len(detail) * .4 + 3)))
            positions = np.arange(len(detail))
            for ax, (key, label) in zip(axes.flat, distances):
                values = np.array([_value(rows[model_id], "metrics", key) for model_id in detail])
                finite = np.isfinite(values)
                ax.barh(positions[finite], values[finite], color=[colors[families[model_id]] for model_id, yes in zip(detail, finite) if yes], alpha=.85)
                ax.set_yticks(positions, [codes[model_id] for model_id in detail], fontsize=8)
                # Retain rows with infinite/undefined values: bar autoscaling
                # otherwise removes an unavailable final row from the axes.
                ax.set_ylim(len(detail) - .5, -.5)
                ax.set(title=label, xlabel="Pooled mean over cell-cutoff entries")
                ax.set_xlim(left=0)
                annotate_nonfinite(ax, values, positions=positions, horizontal=True)
            title(fig, f"Bernoulli probability distances · {len(detail)} display representatives", quantity)
            footer(fig, f"Per-cell predicted Bernoulli distribution versus its {reference_description}; unit distance on {{0,1}}. These are not geographic distances.\nDisplay subset only; all {model_noun} and exact values remain in summary.csv. △ infinite, × undefined (outside finite scale).")
            save(fig, f"{quantity}_distances", "Eight representative displays for all nine exact/floored KL and Bernoulli probability-distance fields; total variation equals Wasserstein-1 for unit distance on {0,1}. Infinity and undefined values retained separately.", detail, quantity=quantity, metric_keys=[key for key, _ in distances] + ["bernoulli_wasserstein_1_distance_mean"], combined_metric_equivalences={"bernoulli_total_variation_distance_mean": "bernoulli_wasserstein_1_distance_mean"})

            columns = 4 if len(reliability_ids) > 4 else max(1, len(reliability_ids))
            grid_rows = math.ceil(len(reliability_ids) / columns)
            fig, axes = figure(grid_rows, columns, (columns * 4.2, grid_rows * 3.9 + 1.2))
            for ax, model_id in zip(axes.flat, reliability_ids):
                bins = rows[model_id].get("calibration", {}).get("bins", [])
                usable = [entry for entry in bins if math.isfinite(_number(entry.get("mean_probability"))) and math.isfinite(_number(entry.get("weighted_outcome_rate"))) and _number(entry.get("sample_count")) > 0]
                ax.plot([0, 1], [0, 1], color="#777777", linestyle="--", linewidth=1, label="Perfect calibration")
                if usable:
                    p = np.array([_number(entry["mean_probability"]) for entry in usable])
                    y = np.array([_number(entry["weighted_outcome_rate"]) for entry in usable])
                    fraction = np.array([_number(entry.get("population_fraction")) for entry in usable])
                    fraction = np.where(np.isfinite(fraction), fraction, 0)
                    ax.plot(p, y, color=colors[families[model_id]], linewidth=1.5)
                    ax.scatter(p, y, s=20 + 220 * fraction, color=colors[families[model_id]], zorder=3)
                else:
                    ax.text(.5, .5, "No nonempty reliability bins", transform=ax.transAxes, ha="center", fontsize=9)
                label = textwrap.fill(f"{codes[model_id]} · {_family_label(families[model_id])}", width=34)
                ax.set(title=label, xlim=(-.035, 1.035), ylim=(-.035, 1.035), xlabel="Mean predicted probability", ylabel=reference_label)
                ax.title.set_fontsize(10)
                count = rows[model_id].get("metrics", {}).get("sample_count", 0)
                ax.text(.04, .96, f"entries: {count}", transform=ax.transAxes, fontsize=8, va="top")
            for ax in list(axes.flat)[len(reliability_ids):]:
                ax.axis("off")
            title(fig, "Fixed-bin reliability · shared-model cohort", quantity)
            footer(fig, "Marker area increases with bin population fraction. Empty bins are omitted; bins are fixed before evaluation.\nNo fitted calibration and no confidence intervals for these descriptive bin summaries.")
            save(fig, f"{quantity}_reliability", "Fixed-bin reliability small multiples; empty bins omitted and marker size reflects bin population.", reliability_ids, quantity=quantity)

            event_rows = {(str(row["model_id"]), str(row["event"])): row for row in report.get("per_event", []) if row.get("cohort") == "shared_models" and row.get("quantity") == quantity}
            events = sorted({event for _, event in event_rows})
            fig, axes = figure(size=(max(10, len(events) * .75 + 4), max(5.5, len(detail) * .32 + 2.5)))
            ax = axes[0, 0]
            if events:
                values = np.array([[_value(event_rows.get((model_id, event)), "metrics", "brier") for event in events] for model_id in detail])
                cmap = mpl.colormaps["viridis_r"].copy()
                cmap.set_bad("#e0e0e0")
                image = ax.imshow(np.ma.masked_invalid(values), aspect="auto", cmap=cmap, vmin=0, vmax=1)
                fig.colorbar(image, ax=ax, label="Brier score ↓", shrink=.85)
                ax.set_xticks(range(len(events)), events, rotation=45, ha="right")
                ax.set_yticks(range(len(detail)), [codes[model_id] for model_id in detail])
                ax.grid(False)
                if len(events) * len(detail) <= 300:
                    for y, x in np.ndindex(values.shape):
                        value = values[y, x]
                        rgba = cmap(value) if math.isfinite(value) else (.88, .88, .88, 1)
                        brightness = .2126 * rgba[0] + .7152 * rgba[1] + .0722 * rgba[2]
                        ax.text(x, y, f"{value:.3f}" if math.isfinite(value) else "—", ha="center", va="center", fontsize=8, color="black" if brightness > .5 else "white")
                ax.set(xlabel="Event (metrics separately pooled within event)", ylabel="Display representative")
            else:
                ax.axis("off")
                ax.text(.5, .5, "No per-event evaluation rows", transform=ax.transAxes, ha="center", fontsize=14)
            title(fig, "Per-event Brier score · shared-model cohort", quantity)
            footer(fig, "Gray cells / — denote undefined or missing scores. Pooled summary scores are recomputed from entries, not averaged from these event scores.")
            save(fig, f"{quantity}_event_brier", "Per-event pooled Brier heatmap for display representatives; unavailable event scores remain gray.", detail, quantity=quantity, events=events)

            fig, axes = figure(1, 2, (15, 6))
            native = np.array([_number(rows.get(model_id, {}).get("native_coverage_fraction")) for model_id in ids])
            shared = np.array([_number(rows.get(model_id, {}).get("shared_retention_fraction")) for model_id in ids])
            ax = axes[0, 0]
            positions = np.arange(1, len(ids) + 1)
            ax.scatter(positions[np.isfinite(native)], native[np.isfinite(native)], s=18, color="#287a38", alpha=.65, label="Native prediction coverage")
            ax.scatter(positions[np.isfinite(shared)], shared[np.isfinite(shared)], s=10, marker="x", color="#3052a0", alpha=.7, label="Shared-model retention")
            ax.set(title="Coverage of reference-eligible entries", xlabel=index_label, ylabel="Covered / reference-eligible entries", ylim=(-.03, 1.04), xlim=(.5, max(1.5, len(ids) + .5)))
            if model_labels:
                ax.set_xticks(positions, [codes[model_id] for model_id in ids])
            ax.legend(fontsize=9, loc="lower left")
            ax.text(.98, .04, f"Undefined native: {np.isnan(native).sum()}\nUndefined shared: {np.isnan(shared).sum()}", transform=ax.transAxes, ha="right", va="bottom", fontsize=8)
            ax = axes[0, 1]
            for family in architecture_names:
                members = [model_id for model_id in ids if families[model_id] == family]
                x = np.array([_number(rows.get(model_id, {}).get("native_coverage_fraction")) for model_id in members])
                y = np.array([_value(rows.get(model_id), "metrics", "brier") for model_id in members])
                finite = np.isfinite(x) & np.isfinite(y)
                ax.scatter(x[finite], y[finite], color=colors[family], s=24, alpha=.7, label=_family_label(family))
            ax.set(title="Shared-cohort Brier versus native coverage", xlabel="Native coverage fraction", ylabel="Shared-cohort Brier ↓", xlim=(-.03, 1.03), ylim=(-.03 * brier_max, brier_max))
            ax.legend(fontsize=8, loc="best")
            title(fig, f"Coverage diagnostics · all {model_noun}", quantity)
            footer(fig, "Native coverage is model-specific. Comparison scores use identical shared-model cell-cutoff entries. Missing references are never assumed unburned for evaluation.")
            save(fig, f"{quantity}_coverage", f"Native availability and shared-model retention for all {model_noun}; coverage versus shared-cohort Brier.", ids, quantity=quantity)

            if stores is not None:
                curve_ids = _select(rows, families, MAX_CURVE_MODELS)
                by_index = {str(model["model_id"]): index for index, model in enumerate(models)}
                fig, axes = figure(1, 2, (15, 7))
                skipped, available, class_counts = {}, [], {}
                for curve_number, model_id in enumerate(curve_ids):
                    store = stores.get((by_index.get(model_id), "shared_models", quantity))
                    if store is None:
                        skipped[model_id] = "No complete pooled entry store"
                        continue
                    entries = store.entries()
                    expected = rows[model_id].get("metrics", {}).get("sample_count")
                    if expected is not None and len(entries["y"]) != expected:
                        raise ValueError(f"Complete pooled curve entries disagree with summary sample count for {model_id}: {len(entries['y'])} != {expected}")
                    curves = _threshold_curves(entries["y"], entries["p"])
                    class_counts[model_id] = dict(positive_count=curves["positive_count"], negative_count=curves["negative_count"])
                    color = mpl.colormaps["tab10"](curve_number % 10)
                    label = f"{codes[model_id]} · {_family_label(families[model_id])}"
                    used = False
                    for ax, name in zip(axes.flat, ("roc", "pr")):
                        curve = curves[name]
                        if curve is not None:
                            ax.plot(*curve, color=color, linewidth=1.7, label=label, drawstyle="steps-pre" if name == "pr" else "default")
                            used = True
                    if used:
                        available.append(model_id)
                    if curves["roc"] is None or curves["pr"] is None:
                        skipped[model_id] = "ROC undefined without both classes; PR undefined without positives" if curves["roc"] is None else "PR undefined without positives"
                    # Release memmap views before runner removes scratch files.
                    del entries, curves
                axes[0, 0].plot([0, 1], [0, 1], linestyle="--", color="#777777", linewidth=1, label="Chance diagonal")
                axes[0, 0].set(title="Pooled ROC", xlabel="False positive rate", ylabel="True positive rate", xlim=(-.02, 1.02), ylim=(-.02, 1.02))
                axes[0, 1].set(title="Pooled precision–recall", xlabel="Recall", ylabel="Precision", xlim=(-.02, 1.02), ylim=(-.02, 1.02))
                prevalence = next((_value(rows[model_id], "metrics", "weighted_prevalence") for model_id in curve_ids if math.isfinite(_value(rows[model_id], "metrics", "weighted_prevalence"))), math.nan)
                if math.isfinite(prevalence):
                    axes[0, 1].axhline(prevalence, linestyle="--", color="#777777", linewidth=1, label=f"Prevalence = {prevalence:.3g}")
                for ax in axes.flat:
                    handles, labels = ax.get_legend_handles_labels()
                    ax.legend(handles, labels, fontsize=8, loc="best")
                title(fig, "Complete pooled ROC / PR curves · display representatives", quantity)
                footer(fig, f"Exact threshold groups from every stored shared-cohort entry; no curve resampling. ROC requires both outcome classes.\n{len(skipped)} representatives have missing/undefined curve support; details are in the plot manifest. AP in summary.csv uses its own step-integral definition.")
                save(fig, f"{quantity}_curves", "Complete pooled ROC and step precision-recall curves for display representatives; single-class/empty support recorded.", available, quantity=quantity, requested_ids=curve_ids, unavailable_curves=skipped, class_counts=class_counts)
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return manifest
