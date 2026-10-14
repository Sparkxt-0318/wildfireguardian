"""Matched model plots against independent observation-derived perimeters.

This module adds explicit observation and model labels to the cumulative
runner's existing scientific plots. It does not reconstruct arrivals, alter
evaluation cohorts, fit a calibration function, or recalculate saved scores.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from .cumulative_report_plots import _number, generate_report_plots


def _spatial_inputs(spatial, model_ids):
    """Validate a complete, common two-dimensional observation grid."""
    initial = np.asarray(spatial["initial_burned"])
    observed = np.asarray(spatial["observed_burned"])
    if initial.ndim != 2 or observed.shape != initial.shape:
        raise ValueError("initial_burned and observed_burned must have matching [H,W] shapes")
    for name, value in (("initial_burned", initial), ("observed_burned", observed)):
        if not np.isin(value, (0, 1)).all():
            raise ValueError(f"{name} must contain binary values; unknowns belong in observed_valid")
    masks = {}
    for name in ("observed_valid", "shared_valid"):
        value = np.asarray(spatial.get(name, spatial["observed_valid"]))
        if value.dtype != np.dtype(bool) or value.shape != initial.shape:
            raise ValueError(f"{name} must be a boolean array with the complete [H,W] shape")
        masks[name] = value
    if np.any(masks["shared_valid"] & ~masks["observed_valid"]):
        raise ValueError("shared_valid must be contained in observed_valid")
    predictions = {}
    for model_id in model_ids:
        record = spatial["predictions"][model_id]
        predictions[model_id] = {}
        for quantity in ("new_burn", "burned"):
            probability = np.asarray(record[quantity], dtype=float)
            if probability.shape != initial.shape:
                raise ValueError(f"{model_id} {quantity} must have the common [H,W] shape")
            selected = probability[masks["shared_valid"]]
            if not np.isfinite(selected).all() or np.any((selected < 0) | (selected > 1)):
                raise ValueError(f"{model_id} {quantity} has unavailable or invalid probability on shared_valid")
            predictions[model_id][quantity] = probability
    extent = spatial.get("extent")
    if extent is not None:
        extent = np.asarray(extent, dtype=float)
        if extent.shape != (4,) or not np.isfinite(extent).all() or extent[1] <= extent[0] or extent[3] <= extent[2]:
            raise ValueError("extent must be finite [left,right,bottom,top] with increasing limits")
        extent = extent.tolist()
    return initial.astype(bool), observed.astype(bool), masks, predictions, extent


def generate_observed_report_plots(report, output_dir, *, stores, spatial=None):
    """Generate previous-style plots for exactly two matched model records.

    ``report`` uses the cumulative report schema: ``models``, ``summary``,
    ``per_event``, and ``protocol``. Each model may have a ``display_label``.
    ``stores`` maps ``(model_index, 'shared_models', quantity)`` to objects with
    ``entries()`` returning complete one-dimensional binary ``y`` and numeric
    ``p`` arrays; they must represent the same ordered cohort for both models.

    Optional ``spatial`` keys are binary ``initial_burned`` and
    ``observed_burned`` [H,W] arrays, boolean ``observed_valid`` and optional
    ``shared_valid`` arrays, and ``predictions[model_id][quantity]`` [H,W]
    probability maps for both ``new_burn`` and ``burned``. The reference map
    uses the endpoint survey perimeter; new burns exclude the initial survey
    perimeter. Optional ``extent=[left,right,bottom,top]``, ``coordinate_label``
    and ``description`` supply spatial presentation metadata. Masks never
    convert missing reference cells into negative observations.

    Returned records include PNG/SVG hashes and are also written to the common
    plots/manifest.json. Supplied reports, probabilities, and stores are not
    mutated. All base metric, distance, reliability, ROC/PR, coverage,
    architecture and event plots are reused without changing score semantics.
    """
    models = report.get("models", [])
    if len(models) != 2 or len({str(model["model_id"]) for model in models}) != 2:
        raise ValueError("Observed comparison plots require exactly two distinct model records")
    model_ids = [str(model["model_id"]) for model in models]
    labels = {str(model["model_id"]): str(model.get("display_label", model["model_id"])) for model in models}
    context = dict(
        model_noun="models", model_labels=labels,
        model_index_label="Model (named in model_index.csv)",
        process_label="matched observed-perimeter evaluation",
        reference_label="Observed perimeter outcome fraction",
        reference_description="binary survey-perimeter outcome",
        sampling_label="M548 uses recursive Monte Carlo probabilities; FARSITE is one fixed 0/1 scenario.",
        prediction_kind="mixed_recursive_monte_carlo_and_deterministic_farsite",
    )
    context.update(report.get("plot_context", {}))
    prepared = deepcopy(report)
    prepared["plot_context"] = context
    rows = {}
    for quantity in ("new_burn", "burned"):
        selected = {str(row["model_id"]): row for row in prepared.get("summary", [])
                    if row.get("cohort") == "shared_models" and row.get("quantity") == quantity}
        if not selected:
            continue
        if set(selected) != set(model_ids):
            raise ValueError(f"Both models must have shared-model summary rows for {quantity}")
        targets = []
        for index, model_id in enumerate(model_ids):
            key = (index, "shared_models", quantity)
            if key not in stores:
                raise ValueError(f"Complete pooled entries are required for {model_id} {quantity}")
            entries = stores[key].entries()
            targets.append(np.asarray(entries["y"]).copy())
            if len(targets[-1]) != selected[model_id].get("metrics", {}).get("sample_count"):
                raise ValueError(f"Pooled entries disagree with summary sample count for {model_id} {quantity}")
        if not np.array_equal(targets[0], targets[1]):
            raise ValueError(f"The models must use the same ordered observed cohort for {quantity}")
        rows[quantity] = selected
    if not rows:
        raise ValueError("Observed comparison plots require shared-model evaluation rows")
    spatial_inputs = _spatial_inputs(spatial, model_ids) if spatial is not None else None
    manifest = generate_report_plots(prepared, output_dir, stores=stores)
    manifest["reference_kind"] = "observation_derived_survey_perimeter"
    manifest["reference_interpretation"] = (
        "Mapped survey footprint rasterized onto the evaluation grid; not direct hourly cell arrival or active flame. "
        "The two models use identical ordered shared-model entries. No metric confidence intervals are inferred."
    )

    import matplotlib as mpl
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    directory = Path(output_dir) / "plots"
    protocol = prepared.get("protocol", {})
    hours = protocol.get("hours", "?")
    interval_label = str(context.get("interval_label", f"{hours}-hour"))
    threshold = protocol.get("threshold", .5)
    colors = ["#dba234", "#4072a6"]

    def save(fig, stem, description, **details):
        outputs = {}
        for extension in ("png", "svg"):
            path = directory / f"{stem}.{extension}"
            fig.savefig(path, dpi=150, facecolor="white", bbox_inches="tight", pad_inches=.12,
                        metadata={"Creator": "wildfire observed evaluation"} if extension == "svg"
                        else {"Software": "wildfire observed evaluation"})
            outputs[extension] = dict(path=f"plots/{path.name}", size_bytes=path.stat().st_size,
                                      sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        manifest["figures"][stem] = dict(description=description, outputs=outputs,
                                         plotted_ids=model_ids, **details)
        fig.clear()

    def figure(rows_count, columns_count, size):
        fig = Figure(figsize=size, layout="constrained")
        FigureCanvasAgg(fig)
        return fig, fig.subplots(rows_count, columns_count, squeeze=False)

    style = {"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
             "axes.spines.right": False, "svg.fonttype": "none", "axes.grid": True, "grid.alpha": .18}
    with mpl.rc_context(style):
        for quantity, selected in rows.items():
            quantity_name = "Future new burns" if quantity == "new_burn" else "Total burned occupancy"
            classification = (
                ("accuracy", "Accuracy"), ("balanced_accuracy", "Balanced accuracy"),
                ("precision", "Precision"), ("recall", "Recall / sensitivity"),
                ("specificity", "Specificity"), ("f1", "F1"),
                ("mcc", "Matthews correlation coefficient"), ("intersection_over_union", "Intersection over union"),
            )
            fig, axes = figure(2, 4, (17, 8))
            for ax, (key, title) in zip(axes.flat, classification):
                values = [_number(selected[model_id].get("classification", {}).get(key)) for model_id in model_ids]
                for index, value in enumerate(values):
                    if math.isfinite(value):
                        ax.bar(index, value, color=colors[index], width=.6)
                        ax.text(index, value + .035 if value >= 0 else value - .065, f"{value:.4g}", ha="center", fontsize=9)
                    else:
                        ax.text(index, .5, "undefined", ha="center", rotation=90, fontsize=9)
                ax.set(title=title, xticks=[0, 1], xticklabels=[labels[model_id] for model_id in model_ids],
                       ylim=(-1.08, 1.15) if key == "mcc" else (-.04, 1.15))
            fig.suptitle(f"{quantity_name} · {interval_label} matched observed-perimeter evaluation\nClassification diagnostics at fixed threshold {threshold}", fontsize=16)
            fig.supxlabel("Identical observed cohort for both models. Thresholds are supplied before evaluation; no threshold optimization on these outcomes.", fontsize=9)
            save(fig, f"{quantity}_classification", "All eight saved fixed-threshold classification diagnostics; undefined values remain labeled.",
                 quantity=quantity, metric_keys=[key for key, _ in classification], threshold=threshold)

            fig, axes = figure(1, 2, (11, 5.5))
            for ax, model_id in zip(axes.flat, model_ids):
                values = selected[model_id].get("classification", {})
                counts = np.array([[_number(values.get("tn")), _number(values.get("fp"))],
                                   [_number(values.get("fn")), _number(values.get("tp"))]])
                image = ax.imshow(np.ma.masked_invalid(counts), cmap="Blues", vmin=0)
                for y, x in np.ndindex(counts.shape):
                    value = counts[y, x]
                    finite_counts = counts[np.isfinite(counts)]
                    maximum = float(finite_counts.max()) if len(finite_counts) else 0.0
                    ax.text(x, y, f"{value:g}" if math.isfinite(value) else "undefined", ha="center", va="center", fontsize=14,
                            color="white" if math.isfinite(value) and maximum > 0 and value > maximum * .5 else "black")
                ax.set(title=labels[model_id], xticks=[0, 1], xticklabels=["Unburned", "Burned"],
                       yticks=[0, 1], yticklabels=["Unburned", "Burned"], xlabel="Thresholded prediction", ylabel="Survey-perimeter outcome")
                ax.grid(False)
                fig.colorbar(image, ax=ax, label="Equal-weight cell count", shrink=.8)
            fig.suptitle(f"{quantity_name} · matched observed-perimeter confusion matrices\nFixed threshold {threshold}", fontsize=15)
            fig.supxlabel("Rows are observation-derived outcomes; columns are thresholded predictions. These cells are the same shared evaluation cohort.", fontsize=9)
            save(fig, f"{quantity}_confusion", "Saved TP/FP/TN/FN counts for identical observed cohorts; no probabilities are thresholded again.", quantity=quantity, threshold=threshold)

        if spatial_inputs is not None:
            initial, observed, masks, predictions, extent = spatial_inputs
            cmap = mpl.colormaps["inferno"].copy()
            cmap.set_bad("#d7d7d7")
            coordinate_label = str(spatial.get("coordinate_label", "Grid-cell position"))
            contour_options = {} if extent is None else dict(extent=extent, origin="upper")
            for quantity in rows:
                reference = observed & ~initial if quantity == "new_burn" else observed
                eligible = masks["shared_valid"] & ~initial if quantity == "new_burn" else masks["shared_valid"]
                fig, axes = figure(1, 3, (17, 6))
                maps = [reference] + [predictions[model_id][quantity] for model_id in model_ids]
                panel_labels = ["Observed endpoint perimeter" if quantity == "burned" else "Observed perimeter expansion"] + [labels[model_id] for model_id in model_ids]
                for ax, values, label in zip(axes.flat, maps, panel_labels):
                    image = ax.imshow(np.ma.array(values, mask=~eligible), cmap=cmap, vmin=0, vmax=1,
                                      interpolation="nearest", extent=extent, origin="upper")
                    if initial.any() and (~initial).any():
                        ax.contour(initial.astype(float), levels=[.5], colors=["#3ac6bb"], linewidths=1.0, **contour_options)
                    ax.set(title=label, xlabel=coordinate_label)
                    ax.grid(False)
                axes[0, 0].set_ylabel(coordinate_label)
                fig.colorbar(image, ax=list(axes.flat), label="Burned outcome (reference) / predicted probability", shrink=.85)
                name = "Future new burns" if quantity == "new_burn" else "Total burned occupancy"
                fig.suptitle(f"{name} · same-area {interval_label} observed comparison\n{spatial.get('description', protocol.get('event', ''))}", fontsize=16)
                fig.legend(handles=[Line2D([], [], color="#3ac6bb", label="Initial observed perimeter"),
                                    Patch(facecolor="#d7d7d7", label="Outside the shared evaluation cohort")],
                           loc="outside lower center", ncol=2, fontsize=9)
                save(fig, f"{quantity}_spatial_comparison", "Identical observation grid and mask for reference, M548 and FARSITE probability maps; initial survey perimeter outlined.",
                     quantity=quantity, shape=list(initial.shape), shared_cell_count=int(eligible.sum()), extent=extent)
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    return manifest
