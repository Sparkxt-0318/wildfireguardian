"""Tables, RESULTS.json and figures for track 1B from a pipeline run directory.

Usage: python research/forecast-v2/scripts/report.py --run RUN_DIR --out research/forecast-v2 [--label FIXTURE]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import audit_fit_coverage as F
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[3] / "forecast"))
from wildfire import baselines as B  # noqa: E402

# Okabe-Ito without yellow, which is too faint on white.
OKABE_ITO = ["#000000", "#E69F00", "#56B4E9", "#009E73", "#0072B2", "#D55E00", "#CC79A7"]
FINE_BINS = np.array([0, 1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1.0])
SINGLE, DOUBLE = 3.5, 7.2


def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7, "axes.titlesize": 7, "axes.labelsize": 7,
                         "legend.fontsize": 6, "xtick.labelsize": 6, "ytick.labelsize": 6,
                         "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
                         "savefig.facecolor": "white", "axes.facecolor": "white"})
    return plt


def save(fig, out: Path, name: str):
    out.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(out / f"{name}.{ext}", dpi=300)


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_assessment(directory):
    """Load only the exact receipt-bound per-fire files, including honest HOLD."""
    receipt = json.loads((directory / "ASSESSMENT.json").read_text())
    if receipt.get("receipt_version") != "wfg.forecast-assessment/2" or receipt.get("status") not in ("COMPLETE", "HOLD"):
        raise ValueError("Current source-bound assessment receipts are required for reporting")
    frozen = json.loads((directory / "FROZEN_ASSESSMENT.json").read_text())
    F.validate_phase_identity(frozen.get("current_phase"))
    contract = frozen.get("spotting_source_contract", {})
    if contract != F.spotting_source_contract(REPO, contract.get("source_sha256", {})):
        raise ValueError("Assessment requires the corrected immutable spotting source phase")
    if sha256(directory / "FROZEN_ASSESSMENT.json") != receipt["frozen_sha256"]:
        raise ValueError("Assessment source/checkpoint/input identity changed")
    listed = receipt["per_fire_files"]
    if {p.name for p in directory.glob("*.npz")} != listed.keys():
        raise ValueError("Unlisted or missing per-fire score files cannot enter a report")
    for name, expected in listed.items():
        if sha256(directory / name) != expected:
            raise ValueError("Receipt-bound per-fire score bytes changed")
    return B.load_scored_entries(directory), receipt


def ablation(run: Path, draws: int = 10000, seed: int = 20261030) -> dict:
    """Variant minus base on development folds, paired by development fire."""
    rows = []
    paths = [run / phase["result"] for phase in F.current_phase_identity()["phases"]
             if phase["stage"] == "fold" and (run / phase["result"]).is_file()]
    for path in paths:
        phase = next(p for p in F.current_phase_identity()["phases"] if run / p["result"] == path)
        _, r, _, _, _ = F.phase_result(REPO, run, phase["variant"], "fold", phase["fold"])
        for fire, s in r["validation_per_fire"].items():
            rows.append(dict(variant=r["variant"], fold=r["fold"], seed=r["seed"], fire=fire,
                             sq=s["brier"] * s["weight"], w=s["weight"], nll=s["clipped_nll"] * s["weight"],
                             fit_seconds=r["fit_seconds"], parameters=r["parameters"]))
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {}
    by = frame.groupby(["variant", "fire"]).agg(sq=("sq", "mean"), w=("w", "mean"), nll=("nll", "mean")).reset_index()
    summary = {}
    base = by[by.variant == "base"].set_index("fire")
    rng = np.random.default_rng(seed)
    for variant, group in by.groupby("variant"):
        g = group.set_index("fire")
        entry = dict(pooled_brier=float(g.sq.sum() / g.w.sum()), pooled_clipped_nll=float(g.nll.sum() / g.w.sum()),
                     mean_fire_brier=float((g.sq / g.w).mean()),
                     fires=int(len(g)), seeds=sorted(frame[frame.variant == variant].seed.unique().tolist()),
                     folds=sorted(frame[frame.variant == variant].fold.unique().tolist()),
                     mean_fit_seconds=float(frame[frame.variant == variant].fit_seconds.mean()),
                     parameters=int(frame[frame.variant == variant].parameters.iloc[0]))
        common = sorted(set(g.index) & set(base.index))
        if variant != "base" and common:
            d = (g.loc[common].sq - base.loc[common].sq).to_numpy()
            w = base.loc[common].w.to_numpy()
            idx = rng.integers(0, len(common), size=(draws, len(common)))
            values = d[idx].sum(1) / w[idx].sum(1)
            lo, hi = np.quantile(values, [0.025, 0.975])
            entry.update(difference_vs_base=float(d.sum() / w.sum()), interval_95=[float(lo), float(hi)],
                         excludes_zero=bool(hi < 0 or lo > 0), fires_better_than_base=int((d < 0).sum()))
        summary[variant] = entry
    return summary


def primary_candidate(abl: dict) -> str | None:
    """Frozen rule: lowest equal-fire development Brier, then fixed variant order."""
    priority = ["base", "d4", "d4_wind", "ellipse", "burnout", "burnout_spotting", "mixed_base"]
    return min(abl, key=lambda v: (abl[v]["mean_fire_brier"], priority.index(v))) if (set(abl) == set(priority)
            and all(v["folds"] == ["2020", "2021", "2022"] and v["seeds"] == [0] for v in abl.values())) else None


def detailed_scores(entries, draws=10000, seed=20261030):
    """Add honest exact-NLL limits and paired whole-fire skill intervals."""
    scored = B.score_entries(entries, draws=draws, seed=seed)
    fire, y = entries["fire"], entries["y"]
    fires = np.unique(fire)
    sampled = np.random.default_rng(seed).integers(0, len(fires), size=(draws, len(fires)))
    errors = {n: np.array([np.sum((p[fire == f] - y[fire == f]) ** 2) for f in fires])
              for n, p in entries["predictions"].items()}
    for name, record in scored["models"].items():
        p = entries["predictions"][name]
        wrong = int((((p == 0) & (y == 1)) | ((p == 1) & (y == 0))).sum())
        exact = None if wrong else float((-np.log(p[y == 1]).sum() - np.log1p(-p[y == 0]).sum()) / len(y))
        record["pooled"]["exact_nll"] = dict(value=exact, infinite=bool(wrong), certainty_wrong_entries=wrong)
        for reference in ("persistence", "dilation_best"):
            denominator = errors[reference].sum()
            metric = "bss_vs_" + ("best_dilation" if reference == "dilation_best" else "persistence")
            record["pooled"][metric] = float(1 - errors[name].sum() / denominator) if denominator else None
            resampled_denominator = errors[reference][sampled].sum(1)
            supported = resampled_denominator > 0
            values = 1 - errors[name][sampled].sum(1)[supported] / resampled_denominator[supported]
            interval = np.quantile(values, [.025, .975]).tolist() if len(values) else None
            record[metric + "_paired_fire_95_interval"] = dict(interval=interval, draws=draws, seed=seed,
                undefined_zero_reference_draws=int((~supported).sum()), unit="whole fire, pooled error ratio")
            for event, per_fire in record["per_fire"].items():
                db = scored["models"][reference]["per_fire"][event]["brier"]
                per_fire[metric] = 1 - per_fire["brier"] / db if db else None
    return scored


def figure_reliability(plt, scored, entries, out, label):
    fig, (ax, low) = plt.subplots(1, 2, figsize=(DOUBLE, 3.0))
    names = list(scored["models"])
    y_all = entries["y"]
    for index_model, (colour, name) in enumerate(zip(OKABE_ITO * 3, names)):
        line_style = ("-", "--", ":")[index_model // len(OKABE_ITO)]
        table = scored["models"][name]["pooled"]["calibration"]
        x = [r["mean_prediction"] for r in table if r["count"]]
        y = [r["observed_frequency"] for r in table if r["count"]]
        ax.plot(x, y, marker="o", ms=2.5, lw=0.9, ls=line_style, color=colour, label=name)
        p = entries["predictions"][name]
        index = np.clip(np.digitize(p, FINE_BINS[1:-1]), 0, len(FINE_BINS) - 2)
        xs, ys = [], []
        for b in range(len(FINE_BINS) - 1):
            use = index == b
            if use.sum() >= 50:
                xs.append(max(p[use].mean(), 1e-5))
                ys.append(max(y_all[use].mean(), 1e-5))
        low.plot(xs, ys, marker="o", ms=2.5, lw=0.9, ls=line_style, color=colour)
    for axis in (ax, low):
        axis.plot([1e-5, 1], [1e-5, 1], color="#999999", lw=0.6, ls="--")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    low.set_xscale("log")
    low.set_yscale("log")
    low.set_xlim(1e-5, 1)
    low.set_ylim(1e-5, 1)
    ax.set_xlabel("Mean forecast probability in bin\n(ten equal-width bins)")
    ax.set_ylabel("Observed new-mapping frequency")
    low.set_xlabel("Mean forecast probability in bin\n(log bins, >= 50 entries; values floored at 1e-5)")
    ax.set_title(f"Reliability, held-out 2024 intervals{label}")
    low.set_title("Low-probability range")
    fig.legend(*ax.get_legend_handles_labels(), loc="lower center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 0.01))
    fig.subplots_adjust(left=0.09, right=0.985, top=0.89, bottom=0.35, wspace=0.30)
    save(fig, out, "fig01_reliability_all_models")
    plt.close(fig)


def figure_per_fire(plt, scored, out, label, primary):
    fires = scored["fires"]
    names = [n for n in ("persistence", "dilation_best", "logistic", "c651_mc", primary) if n and n in scored["models"]]
    fig, ax = plt.subplots(figsize=(DOUBLE, 2.6))
    x = np.arange(len(fires))
    for k, (colour, name) in enumerate(zip(OKABE_ITO, names)):
        values = [scored["models"][name]["per_fire"][f]["brier"] for f in fires]
        ax.scatter(x + (k - len(names) / 2) * 0.12, values, s=10, color=colour, label=name, zorder=3)
    if primary and "dilation_best" in names:
        left, right = names.index("dilation_best"), names.index(primary)
        for i, fire in enumerate(fires):
            xs = [i + (k - len(names) / 2) * .12 for k in (left, right)]
            ys = [scored["models"][n]["per_fire"][fire]["brier"] for n in ("dilation_best", primary)]
            ax.plot(xs, ys, color="#bbbbbb", lw=.6, zorder=1)
    ax.set_xticks(x, [f.split("_")[1] if "_" in f else f for f in fires])
    ax.set_ylabel("Brier score per fire (lower is better)")
    ax.set_title(f"Held-out 2024 fires, common cells for every model{label}")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)
    fig.subplots_adjust(left=.09, right=.74, bottom=.24, top=.88)
    save(fig, out, "fig02_per_fire_brier_paired")
    plt.close(fig)


def figure_ablation(plt, abl, out, label):
    variants = [v for v in abl if "difference_vs_base" in abl[v]]
    fig, ax = plt.subplots(figsize=(SINGLE, 0.35 * max(len(variants), 1) + 0.9))
    for i, v in enumerate(variants):
        e = abl[v]
        ax.errorbar(e["difference_vs_base"], i, xerr=[[e["difference_vs_base"] - e["interval_95"][0]],
                                                      [e["interval_95"][1] - e["difference_vs_base"]]],
                    fmt="o", ms=3, color=OKABE_ITO[5], ecolor=OKABE_ITO[5], lw=0.8, capsize=2)
    ax.axvline(0, color="#999999", lw=0.6, ls="--")
    ax.set_yticks(range(len(variants)), variants)
    ax.set_xlabel("Cell-pooled development Brier minus base\n(whole-fire bootstrap, 95% interval)")
    ax.set_title(f"Structural ablations, 2020 to 2022 folds{label}")
    fig.subplots_adjust(left=.35, right=.98, bottom=.25, top=.88)
    save(fig, out, "fig03_ablation_forest_plot")
    plt.close(fig)


def figure_meanfield(plt, frame, out, label):
    fig, ax = plt.subplots(figsize=(SINGLE, 2.4))
    fixed = frame[frame.horizon_kind == "fixed"]
    for colour, (country, group) in zip(OKABE_ITO[1:], fixed.groupby("country")):
        stats = group.groupby("hours").rmse_active.agg(["median", "min", "max"])
        ax.plot(stats.index, stats["median"], marker="o", ms=3, color=colour, label=f"{country} median")
        ax.fill_between(stats.index, stats["min"], stats["max"], color=colour, alpha=0.2, lw=0)
    ax.set_xscale("log")
    ax.set_xticks([1, 3, 6, 12, 24], ["1", "3", "6", "12", "24"])
    ax.set_xlabel("Forecast horizon (h)")
    ax.set_ylabel("Mean field vs Monte Carlo RMSE\n(cells where either probability > 0.001)")
    ax.set_title(f"c651, 1,024 trajectories{label}")
    ax.legend(frameon=False)
    fig.subplots_adjust(left=.24, right=.98, bottom=.22, top=.87)
    save(fig, out, "fig04_meanfield_vs_mc_rmse_by_horizon")
    plt.close(fig)


def figure_example(plt, run, scored_entries, primary, out, label):
    import numpy as np
    fire_ids = sorted(set(scored_entries["fire"].tolist()))
    candidates = []
    for fire in fire_ids:
        data = np.load(run / "heldout" / f"{fire}.npz")
        for interval in np.unique(data["interval"]):
            use = data["interval"] == interval
            candidates.append((int(data["y"][use].sum()), fire, int(interval)))
    positive = sorted(c for c in candidates if c[0] > 0)
    if not positive or primary is None:
        return None
    count, fire, interval = positive[len(positive) // 2]
    data = np.load(run / "heldout" / f"{fire}.npz")
    states = np.load(Path(json.loads((run / "report_inputs.json").read_text())["perimeters"]) / fire / "states.npz")
    times = list(pd.to_datetime(states["times"], utc=True))
    t1 = pd.Timestamp(str(data["t1"][interval]))
    i = times.index(t1)
    initial, later = states["states"][i].astype(bool), states["states"][i + 1].astype(bool)
    use = data["interval"] == interval
    rows, cols = data["row"][use], data["col"][use]
    fields = {}
    for name in ("c651_mc", primary):
        field = np.full(initial.shape, np.nan)
        field[rows, cols] = data[f"p_{name}"][use]
        field[initial] = 1.0
        fields[name] = field
    r = np.flatnonzero((initial | later).any(1))
    c = np.flatnonzero((initial | later).any(0))
    window = (slice(max(r[0] - 8, 0), r[-1] + 9), slice(max(c[0] - 8, 0), c[-1] + 9))
    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE, 2.0))
    panels = [("Initial mapped extent", initial.astype(float)), ("c651 Monte Carlo", fields["c651_mc"]),
              (f"{primary}\nmean field", fields[primary]), ("Later mapped extent", later.astype(float))]
    for ax, (title, image) in zip(axes, panels):
        shown = ax.imshow(image[window], vmin=0, vmax=1, cmap="viridis", interpolation="nearest")
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.subplots_adjust(left=.02, right=.89, bottom=.08, top=.70, wspace=.12)
    colour_axis = fig.add_axes([.915, .18, .013, .46])
    fig.colorbar(shown, cax=colour_axis, label="Cumulative probability or mapped (1)")
    fig.suptitle(f"{fire}\n{t1.isoformat()}, +{float(data['hours'][interval]):.1f} h, {count} newly mapped cells{label}", y=.98, fontsize=7)
    save(fig, out, "fig05_example_forecast_vs_perimeter")
    plt.close(fig)
    return dict(fire=fire, interval=interval, t1=t1.isoformat(), positives=count,
                rule="median positive count among held-out intervals with growth")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    label = f" [{args.label}]" if args.label else ""
    plt = style()
    figures = args.out / "figures"
    results = dict(current_phase=F.current_phase_identity(), label=args.label or "REAL INPUTS", run=str(args.run))
    abl = ablation(args.run)
    results["ablation"] = abl
    results["primary_candidate_rule"] = "lowest equal-fire development Brier over the 2020 to 2022 leave-one-year-out folds, with the fixed variant tie order"
    primary = primary_candidate(abl)
    finals = {}
    for variant in F.VARIANTS:
        path = args.run / F.intended_phase(variant, "final")["result"]
        if not path.is_file():
            continue
        _, r, _, _, _ = F.phase_result(REPO, args.run, variant, "final")
        finals[path.parent.name] = dict(variant=r["variant"], seed=r["seed"], epochs=r["epochs"],
                                        checkpoint_sha256=r["checkpoint_sha256"], parameters=r["parameters"],
                                        fit_seconds=r["fit_seconds"])
    results["final_models"] = finals
    chosen = [k for k, v in finals.items() if v["variant"] == primary]
    results["primary_candidate"] = dict(variant=primary, run=chosen[0] if chosen else None,
                                        checkpoint_sha256=finals[chosen[0]]["checkpoint_sha256"] if chosen else None)
    selection_path = args.out / "MODEL_SELECTION.json"
    if selection_path.exists():
        selection = json.loads(selection_path.read_text())
        F.validate_selection_phase(REPO, args.run, selection)
        if selection["selected_variant"] != primary or not chosen:
            raise ValueError("Report selection differs from the frozen development choice")
        if selection["checkpoints"][primary]["sha256"] != finals[chosen[0]]["checkpoint_sha256"]:
            raise ValueError("Report primary checkpoint differs from its frozen identity")
        results["model_selection_sha256"] = sha256(selection_path)
    if abl:
        figure_ablation(plt, abl, figures, label)
        pd.DataFrame(abl).T.to_csv(args.out / "ablation.csv")
    heldout = args.run / "heldout"
    if heldout.exists() and list(heldout.glob("*.npz")):
        entries, assessment = load_assessment(heldout)
        scored = detailed_scores(entries)
        scored["assessment_status"] = assessment["status"]
        scored["unscored_outcomes"] = assessment["failed_or_unavailable"]
        scored["statistic_scope"] = "complete declared cohort" if assessment["status"] == "COMPLETE" else "descriptive supported subset; primary gate remains closed"
        inputs = json.loads((args.run / "report_inputs.json").read_text())
        if "c651_mc" in entries["predictions"]:
            # A finite-trajectory frequency adds its sampling variance to the Brier
            # score; subtract the unbiased estimate p(1-p)/(n-1) per entry.
            n = inputs["n_samples"]
            p = entries["predictions"]["c651_mc"]
            pooled = scored["models"]["c651_mc"]["pooled"]
            pooled["brier_mc_variance_corrected"] = float(pooled["brier"] - np.mean(p * (1 - p)) / (n - 1))
            pooled["mc_trajectories"] = n
        results["heldout_inputs"] = inputs
        results["heldout"] = scored
        figure_reliability(plt, scored, entries, figures, label)
        primary_run = chosen[0] if chosen else None
        if primary_run:
            bins = {n: scored["models"][n]["pooled"]["lowest_bin"]
                    for n in (primary_run, "persistence", "dilation_best")}
            gaps = {n: abs(row["mean_prediction"] - row["observed_frequency"]) if row["count"] else None
                    for n, row in bins.items()}
            comparison = {ref: scored["paired"][primary_run + "__vs__" + ref]["percentile_95_interval"][1] < 0
                          for ref in ("persistence", "dilation_best")}
            calibration = gaps[primary_run] is not None and all(gaps[ref] is not None and gaps[primary_run] <= gaps[ref]
                                                               for ref in ("persistence", "dilation_best"))
            complete = assessment["status"] == "COMPLETE"
            passed = complete and selection_path.exists() and calibration and all(comparison.values())
            results["retrospective_superiority_gate"] = dict(criteria_pass=passed,
                brier_comparisons_pass={ref: complete and value for ref, value in comparison.items()},
                lowest_bin_absolute_gaps=gaps, calibration_pass=complete and calibration,
                complete_cohort_pass=complete,
                descriptive_subset_criteria=dict(brier_comparisons=comparison, calibration=calibration),
                interpretation="Retrospective mapped-extent comparison only; this is not the blind2026 test or physical validation")
        figure_per_fire(plt, scored, figures, label, primary_run)
        rows = []
        for model, record in scored["models"].items():
            for fire, s in record["per_fire"].items():
                rows.append(dict(model=model, fire=fire, **{k: s[k] for k in ("entries", "positives", "brier",
                                 "bss_vs_persistence", "bss_vs_best_dilation", "average_precision", "roc_auc", "ece_10_bins", "clipped_nll")}))
        pd.DataFrame(rows).to_csv(args.out / "per_fire.csv", index=False)
        if primary_run and (args.run / "report_inputs.json").exists():
            results["example_figure"] = figure_example(plt, args.run, entries, primary_run, figures, label)
    korea = args.run / "korean2025"
    if korea.exists() and list(korea.glob("*.npz")):
        entries, assessment = load_assessment(korea)
        results["korean2025_secondary_reconstruction"] = detailed_scores(entries)
        results["korean2025_secondary_reconstruction"]["assessment_status"] = assessment["status"]
        results["korean2025_secondary_reconstruction"]["unscored_outcomes"] = assessment["failed_or_unavailable"]
    mf = args.run / "meanfield_vs_mc" / "meanfield_vs_mc.csv"
    if mf.exists():
        frame = pd.read_csv(mf)
        results["meanfield_vs_mc"] = json.loads((args.run / "meanfield_vs_mc" / "meanfield_vs_mc.json").read_text())
        figure_meanfield(plt, frame, figures, label)
        frame.to_csv(args.out / "meanfield_vs_mc.csv", index=False)
    (args.out / "RESULTS.json").write_text(json.dumps(results, indent=1, default=str) + "\n")
    print(json.dumps(dict(primary=primary, finals=list(finals), heldout="heldout" in results)))


if __name__ == "__main__":
    main()
