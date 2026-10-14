"""Figures and summary tables from results/sweeps.csv. SYNTHETIC.

Usage: .venv/bin/python scripts/05_figures_sweeps.py
Writes figures/fig4_sweep_median.*, fig5_sweep_p90.*, fig6_sweep_cls_spots.*, fig7_scenarios.*
and results/sweep_summary.json.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from matplotlib import pyplot as plt  # noqa: E402

from lastgasp import style  # noqa: E402

FIG = ROOT / "figures"
style.apply()
METHODS = ["idw_naive", "idw_topology", "huygens"]
PANELS = [
    ("meter_density", "Meter density (nodes per km²)", "nodes_per_km2", "log"),
    ("delivery", "Last-gasp delivery probability", "value", "linear"),
    ("timing_noise", "Median ignition delay (min)", "value", "log"),
    ("grid_failure", "Span fault probability when fire arrives", "value", "linear"),
    ("tag_density", "Tag density (nodes per km²)", "nodes_per_km2", "log"),
    ("substation_trip", "Whole-substation trip time (min)", "value", "cat"),
]
PANEL_TITLES = ["(a) Meters: density", "(b) Meters: delivery", "(c) Meters: timing noise",
                "(d) Meters: grid fault rate", "(e) Battery tags only: density", "(f) Meters: substation trip"]
SHORT_X = ["Meter density\n(nodes per km²)", "Delivery\nprobability", "Median ignition\ndelay (min)",
           "Span fault\nprobability"]


def log_axis(ax, ticks):
    from matplotlib.ticker import FixedLocator, NullFormatter, NullLocator
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.set_xticklabels([f"{t:g}" for t in ticks])
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_minor_formatter(NullFormatter())


LOG_TICKS = {"meter_density": [5, 10, 20, 50, 100], "timing_noise": [0.5, 1, 2, 5, 10, 20],
             "tag_density": [1, 2, 5, 10, 20, 50]}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def load():
    rows = list(csv.DictReader(open(ROOT / "results/sweeps.csv")))
    meta = json.loads((ROOT / "results/sweeps_meta.json").read_text())
    return rows, meta


def xvalue(sweep, v, cfg_base):
    if sweep == "timing_noise":
        return float(v) * cfg_base["observe"]["ignition_delay_median_min"]
    if sweep == "grid_failure":
        return float(v) * cfg_base["grid"]["p_span_fault_given_fire"]
    return v


def group(rows, sweep):
    out = {}
    for r in rows:
        if r["sweep"] != sweep or r.get("error"):
            continue
        out.setdefault(r["value"], []).append(r)
    return out


def stats(rs, key):
    a = np.array([num(r.get(key)) for r in rs])
    a = a[np.isfinite(a)]
    if a.size == 0:
        return np.nan, np.nan, np.nan
    return float(np.median(a)), float(np.percentile(a, 25)), float(np.percentile(a, 75))


def order_values(sweep, groups):
    if sweep == "substation_trip":
        keys = ["none", "80", "60", "40", "20"]
        return [k for k in keys if k in groups]
    return sorted(groups, key=float)


def summarise(rows, cfg_base):
    summ = {}
    for sweep, _, xkey, _ in PANELS:
        g = group(rows, sweep)
        summ[sweep] = []
        for v in order_values(sweep, g):
            rs = g[v]
            d = {"value": v, "n_runs": len(rs), "x": xvalue(sweep, v, cfg_base) if v != "none" else "none",
                 "nodes_per_km2": stats(rs, "nodes_per_km2")[0]}
            for m in METHODS + ["oracle_idw"]:
                for st in ("bldg_med", "bldg_p90"):
                    med, lo, hi = stats(rs, f"{m}_{st}")
                    d[f"{m}_{st}"] = med
                    d[f"{m}_{st}_q25"] = lo
                    d[f"{m}_{st}_q75"] = hi
            for k in ("cls_balanced_acc", "cls_time_only_balanced_acc", "frac_fire_censored_by_grid",
                      "frac_deaths_fire", "cls_acc"):
                d[k] = stats(rs, k)[0]
            det = sum(num(r["spot_n_detected"]) for r in rs)
            mdet = sum(num(r["spot_n_matched_det"]) for r in rs)
            ntrue = sum(num(r["spot_n_true"]) for r in rs)
            nobs = sum(num(r["spot_n_observable"]) for r in rs)
            mtrue = sum(num(r["spot_n_matched_true"]) for r in rs)
            d.update({"spot_detected": det, "spot_precision_pooled": mdet / det if det else np.nan,
                      "spot_true": ntrue, "spot_observable": nobs, "spot_recall_pooled": mtrue / ntrue if ntrue else np.nan,
                      "spot_dist_err_med_m": stats(rs, "spot_dist_err_med_m")[0],
                      "spot_jump_err_med_m": stats(rs, "spot_jump_err_med_m")[0],
                      "n_fire_deaths_used": stats(rs, "n_fire_deaths_used")[0]})
            summ[sweep].append(d)
    scen = {}
    for r in rows:
        if r["sweep"] == "scenario" and not r.get("error"):
            scen.setdefault(r["value"], []).append(r)
    summ["scenarios"] = []
    for name, rs in scen.items():
        d = {"value": name, "n_runs": len(rs), "nodes_per_km2": stats(rs, "nodes_per_km2")[0]}
        for m in METHODS + ["oracle_idw"]:
            for st in ("bldg_med", "bldg_p90"):
                med, lo, hi = stats(rs, f"{m}_{st}")
                d[f"{m}_{st}"], d[f"{m}_{st}_q25"], d[f"{m}_{st}_q75"] = med, lo, hi
        for k in ("cls_balanced_acc", "frac_fire_censored_by_grid", "frac_deaths_fire"):
            d[k] = stats(rs, k)[0]
        det = sum(num(r["spot_n_detected"]) for r in rs)
        ntrue = sum(num(r["spot_n_true"]) for r in rs)
        d["spot_precision_pooled"] = sum(num(r["spot_n_matched_det"]) for r in rs) / det if det else np.nan
        d["spot_recall_pooled"] = sum(num(r["spot_n_matched_true"]) for r in rs) / ntrue if ntrue else np.nan
        d["spot_true"] = ntrue
        d["spot_observable"] = sum(num(r["spot_n_observable"]) for r in rs)
        d["spot_detected"] = det
        d["spot_dist_err_med_m"] = stats(rs, "spot_dist_err_med_m")[0]
        d["spot_jump_err_med_m"] = stats(rs, "spot_jump_err_med_m")[0]
        d["n_fire_deaths_used"] = stats(rs, "n_fire_deaths_used")[0]
        summ["scenarios"].append(d)
    return summ


def xs_for(sweep, rowsum, xkey):
    if xkey == "nodes_per_km2":
        return np.array([d["nodes_per_km2"] for d in rowsum])
    if sweep == "substation_trip":
        return np.arange(len(rowsum))
    return np.array([float(d["x"]) for d in rowsum])


def fig_arrival(summ, stat, name, ylabel):
    fig, axes = plt.subplots(2, 3, figsize=(7.4, 5.2), constrained_layout=True)
    for ax, ptitle, (sweep, xlabel, xkey, scale) in zip(axes.ravel(), PANEL_TITLES, PANELS):
        rs = summ[sweep]
        x = xs_for(sweep, rs, xkey)
        for m in METHODS:
            y = np.array([d[f"{m}_{stat}"] for d in rs])
            lo = np.array([d[f"{m}_{stat}_q25"] for d in rs])
            hi = np.array([d[f"{m}_{stat}_q75"] for d in rs])
            ax.plot(x, y, marker="o", ms=3, lw=1.3, color=style.METHOD_COLORS[m], label=style.METHOD_LABELS[m])
            ax.fill_between(x, lo, hi, color=style.METHOD_COLORS[m], alpha=0.15, lw=0)
        y = np.array([d[f"oracle_idw_{stat}"] for d in rs])
        ax.plot(x, y, ls="--", lw=1.0, color=style.METHOD_COLORS["oracle_idw"], label=style.METHOD_LABELS["oracle_idw"])
        if scale == "log":
            log_axis(ax, LOG_TICKS[sweep])
        if sweep == "substation_trip":
            ax.set_xticks(x)
            ax.set_xticklabels(["none" if d["value"] == "none" else d["value"] for d in rs])
        ax.set_title(ptitle, fontsize=8.5, loc="left")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color="#e5e5e5", lw=0.6)
    h, lab = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.5, -0.045), fontsize=7.5)
    fig.suptitle(f"Arrival-time error at burned buildings, {('median' if stat == 'bldg_med' else '90th percentile')} "
                 "over buildings. Lines: median over 10 runs; bands: interquartile range.\n"
                 f"Other parameters at defaults (meters on 50% of buildings). {style.SYNTH_NOTE}.", fontsize=8.5)
    return style.save(fig, FIG, name)


def fig_cls_spots(summ):
    sweeps = PANELS[:4]
    fig, axes = plt.subplots(2, 4, figsize=(7.4, 4.8), constrained_layout=True, sharey="row")
    C = style.OKABE_ITO
    for j, (sweep, xlabel, xkey, scale) in enumerate(sweeps):
        rs = summ[sweep]
        x = xs_for(sweep, rs, xkey)
        ax = axes[0, j]
        # Balanced accuracy is undefined when almost every death is fire caused (no grid faults).
        ok = np.array([d["frac_deaths_fire"] < 0.95 for d in rs])
        ax.plot(x[ok], np.array([d["cls_balanced_acc"] for d in rs])[ok], marker="o", ms=3, color=C["blue"],
                label="Topology classifier\n(balanced accuracy)")
        ax.plot(x[ok], np.array([d["cls_time_only_balanced_acc"] for d in rs])[ok], marker="s", ms=3, color=C["grey"],
                label="Time-only classifier\n(balanced accuracy)")
        ax.plot(x, [d["frac_fire_censored_by_grid"] for d in rs], marker="^", ms=3, ls="--", color=C["purple"],
                label="Fraction of fire signals lost\nto an earlier grid outage")
        ax.set_ylim(0, 1.02)
        ax = axes[1, j]
        ax.plot(x, [d["spot_precision_pooled"] for d in rs], marker="o", ms=3, color=C["vermillion"],
                label="Spot precision (pooled)")
        ax.plot(x, [d["spot_recall_pooled"] for d in rs], marker="s", ms=3, color=C["green"],
                label="Spot recall, significant\nspots (pooled)")
        ax.set_ylim(0, 1.02)
        ax.set_xlabel(SHORT_X[j], fontsize=7.5)
        for a in axes[:, j]:
            if scale == "log":
                log_axis(a, LOG_TICKS[sweep][::2] if sweep == "timing_noise" else [10, 30, 100])
            a.grid(axis="y", color="#e5e5e5", lw=0.6)
    axes[0, 0].set_ylabel("Balanced accuracy or fraction")
    axes[1, 0].set_ylabel("Precision or recall")
    for r in range(2):
        h, lab = axes[r, 0].get_legend_handles_labels()
        axes[r, -1].legend(h, lab, loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False, fontsize=7)
    fig.suptitle("Fire versus grid classification (top) and spot fire detection (bottom), smart meters on 50% of buildings.\n"
                 "Medians over 10 runs; spot metrics pooled over runs; classification not shown when grid faults are off.\n"
                 f"{style.SYNTH_NOTE}.", fontsize=8)
    return style.save(fig, FIG, "fig6_sweep_cls_spots")


def fig_scen(summ):
    order = ["meters_50pct", "routers_50pct", "meters_no_grid_faults", "meters_plus_tags_10pct", "tags_50pct"]
    labels = ["Meters\n50%", "Routers\n50%", "Meters\n50%,\nno grid\nfaults", "Meters\n50% +\ntags 10%", "Tags\n50%"]
    sc = {d["value"]: d for d in summ["scenarios"]}
    order = [o for o in order if o in sc]
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.4), constrained_layout=True)
    w = 0.26
    x = np.arange(len(order))
    for ax, stat, title in ((axes[0], "bldg_med", "(a) Median error"), (axes[1], "bldg_p90", "(b) 90th percentile error")):
        for k, m in enumerate(METHODS):
            y = np.array([sc[o][f"{m}_{stat}"] for o in order])
            lo = y - np.array([sc[o][f"{m}_{stat}_q25"] for o in order])
            hi = np.array([sc[o][f"{m}_{stat}_q75"] for o in order]) - y
            ax.bar(x + (k - 1) * w, y, w, color=style.METHOD_COLORS[m], label=style.METHOD_LABELS[m],
                   yerr=[lo, hi], error_kw=dict(lw=0.6, capsize=1.5))
        ax.set_xticks(x)
        ax.set_xticklabels([labels[["meters_50pct", "routers_50pct", "meters_no_grid_faults",
                                    "meters_plus_tags_10pct", "tags_50pct"].index(o)] for o in order], fontsize=7)
        ax.set_ylabel("Error at burned buildings (min)")
        ax.set_title(title)
        ax.grid(axis="y", color="#e5e5e5", lw=0.6)
    axes[0].legend(frameon=False, fontsize=7, loc="upper right")
    fig.suptitle("Device types and grid dependence, nodes on 50% of buildings unless stated.\n"
                 f"Medians over 10 runs; error bars show the interquartile range. {style.SYNTH_NOTE}.", fontsize=8.5)
    return style.save(fig, FIG, "fig7_scenarios")


if __name__ == "__main__":
    rows, meta = load()
    cfg_base = json.loads((ROOT / "configs/default.json").read_text())
    summ = summarise(rows, cfg_base)
    summ["_provenance"] = {k: meta[k] for k in ("commit", "code_dirty", "script", "config", "fire_seeds",
                                                "obs_seeds", "n_runs", "n_errors") if k in meta}
    summ["_provenance"]["summary_script"] = "scripts/05_figures_sweeps.py"
    (ROOT / "results/sweep_summary.json").write_text(json.dumps(summ, indent=1, default=float))
    for p in (fig_arrival(summ, "bldg_med", "fig4_sweep_median", "Median error (min)"),
              fig_arrival(summ, "bldg_p90", "fig5_sweep_p90", "90th percentile error (min)"),
              fig_cls_spots(summ), fig_scen(summ)):
        print(p)
