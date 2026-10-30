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
        fig.savefig(out / f"{name}.{ext}", dpi=300, bbox_inches="tight")


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ablation(run: Path, draws: int = 10000, seed: int = 20261029) -> dict:
    """Variant minus base on development folds, paired by development fire."""
    rows = []
    for path in sorted((run / "folds").glob("*/result.json")):
        r = json.loads(path.read_text())
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
    """Pre-specified rule: lowest pooled development Brier among the fitted variants."""
    return min(abl, key=lambda v: abl[v]["pooled_brier"]) if abl else None


def figure_reliability(plt, scored, entries, out, label):
    fig, (ax, low) = plt.subplots(1, 2, figsize=(DOUBLE, 3.0))
    names = [n for n in ("c651_mc", "c651_meanfield", "logistic", "dilation_best") if n in scored["models"]]
    names += [n for n in scored["models"] if n.startswith(("base", "d4", "ellipse", "burnout", "mixed"))]
    y_all = entries["y"]
    for colour, name in zip(OKABE_ITO * 3, names):
        table = scored["models"][name]["pooled"]["calibration"]
        x = [r["mean_prediction"] for r in table if r["count"]]
        y = [r["observed_frequency"] for r in table if r["count"]]
        ax.plot(x, y, marker="o", ms=2.5, lw=0.9, color=colour, label=name)
        p = entries["predictions"][name]
        index = np.clip(np.digitize(p, FINE_BINS[1:-1]), 0, len(FINE_BINS) - 2)
        xs, ys = [], []
        for b in range(len(FINE_BINS) - 1):
            use = index == b
            if use.sum() >= 50:
                xs.append(max(p[use].mean(), 1e-5))
                ys.append(max(y_all[use].mean(), 1e-5))
        low.plot(xs, ys, marker="o", ms=2.5, lw=0.9, color=colour)
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
    ax.legend(loc="upper left", frameon=False)
    fig.tight_layout()
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
    for i, f in enumerate(fires):
        vals = [scored["models"][n]["per_fire"][f]["brier"] for n in names]
        ax.plot([i - 0.3, i + 0.3], [min(vals), min(vals)], color="#dddddd", lw=0.5, zorder=1)
    ax.set_xticks(x, [f.split("_")[1] if "_" in f else f for f in fires])
    ax.set_ylabel("Brier score per fire (lower is better)")
    ax.set_title(f"Per-fire Brier on held-out 2024 fires, same cells for every model{label}")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)
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
    ax.set_xlabel("Development Brier minus base (paired by fire, 95% bootstrap)")
    ax.set_title(f"Structural ablations on 2020 to 2022 folds{label}")
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
    ax.set_ylabel("RMSE, mean field vs Monte Carlo\n(cells with p > 0.001)")
    ax.set_title(f"c651 mean field against 1,024 trajectories{label}")
    ax.legend(frameon=False)
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
        fields[name] = field
    r = np.flatnonzero((initial | later).any(1))
    c = np.flatnonzero((initial | later).any(0))
    window = (slice(max(r[0] - 8, 0), r[-1] + 9), slice(max(c[0] - 8, 0), c[-1] + 9))
    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE, 2.0))
    panels = [("Initial mapped extent", initial.astype(float)), (f"c651 Monte Carlo", fields["c651_mc"]),
              (f"{primary} mean field", fields[primary]), ("Later mapped extent", later.astype(float))]
    for ax, (title, image) in zip(axes, panels):
        shown = ax.imshow(image[window], vmin=0, vmax=1, cmap="viridis", interpolation="nearest")
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.colorbar(shown, ax=axes, fraction=0.02, pad=0.01, label="Probability or mapped (1)")
    fig.suptitle(f"{fire}, {t1.isoformat()} plus {float(data['hours'][interval]):.1f} h, {count} newly mapped cells{label}", y=1.05)
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
    results = dict(label=args.label or "REAL INPUTS", run=str(args.run))
    abl = ablation(args.run)
    results["ablation"] = abl
    results["primary_candidate_rule"] = "lowest pooled development Brier over the 2020 to 2022 leave-one-year-out folds (decided before held-out scoring)"
    primary = primary_candidate(abl)
    finals = {}
    for path in sorted((args.run / "final").glob("*/result.json")):
        r = json.loads(path.read_text())
        finals[path.parent.name] = dict(variant=r["variant"], seed=r["seed"], epochs=r["epochs"],
                                        checkpoint_sha256=r["checkpoint_sha256"], parameters=r["parameters"],
                                        fit_seconds=r["fit_seconds"])
    results["final_models"] = finals
    chosen = [k for k, v in finals.items() if v["variant"] == primary]
    results["primary_candidate"] = dict(variant=primary, run=chosen[0] if chosen else None,
                                        checkpoint_sha256=finals[chosen[0]]["checkpoint_sha256"] if chosen else None)
    if abl:
        figure_ablation(plt, abl, figures, label)
        pd.DataFrame(abl).T.to_csv(args.out / "ablation.csv")
    heldout = args.run / "heldout"
    if heldout.exists() and list(heldout.glob("*.npz")):
        entries = B.load_scored_entries(heldout)
        scored = B.score_entries(entries)
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
        figure_per_fire(plt, scored, figures, label, primary_run)
        rows = []
        for model, record in scored["models"].items():
            for fire, s in record["per_fire"].items():
                rows.append(dict(model=model, fire=fire, **{k: s[k] for k in ("entries", "positives", "brier",
                                 "bss_vs_persistence", "average_precision", "roc_auc", "ece_10_bins", "clipped_nll")}))
        pd.DataFrame(rows).to_csv(args.out / "per_fire.csv", index=False)
        if primary_run and (args.run / "report_inputs.json").exists():
            results["example_figure"] = figure_example(plt, args.run, entries, primary_run, figures, label)
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
