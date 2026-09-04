#!/usr/bin/env python
"""Regenerate every manuscript figure from committed artifacts. Deterministic.

    python paper/make_figures.py            # writes paper/figures/F*.png
    python paper/make_figures.py --out DIR  # elsewhere (tests)

Each figure function returns True if drawn, False if its artifact is absent, in
which case the manuscript must carry a [GAP] for it. Add a figure by adding a
function and registering it in FIGURES; keep the F-number stable once cited.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "paper"))
import style  # noqa: E402

style.apply()
FIRE_LABEL = {"gangneung_2023": "Gangneung 2023", "hongseong_2023": "Hongseong 2023", "miryang_2022": "Miryang 2022",
              "uiseong_andong_2025": "Uiseong-Andong 2025", "uljin_samcheok_2022": "Uljin-Samcheok 2022", "yeongdeok_2025": "Yeongdeok 2025"}


def load(rel: str):
    p = REPO / rel
    return json.loads(p.read_text()) if p.exists() else None


# ---------------------------------------------------------------------------
def _fit_text(fig, ax, cx, cy, box_w, text, max_fs, color, weight="normal"):
    """Place centred text and shrink it until its widest line fits `box_w` data units.

    Matplotlib neither wraps nor shrinks text to a patch, so a label that fits in
    one font renders straight through the box edge in another — the exact failure
    paper/README.md records for this sandbox's DejaVu fallback. Measuring the drawn
    extent and stepping the size down is deterministic for a given font and keeps
    the diagram legible under either family.
    """
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    x0 = ax.transData.transform((0, 0))[0]
    limit = ax.transData.transform((box_w, 0))[0] - x0
    fs = max_fs
    while True:
        t = ax.text(cx, cy, text, ha="center", va="center", fontsize=fs,
                    weight=weight, color=color, linespacing=1.25)
        if t.get_window_extent(renderer=renderer).width <= limit or fs <= 3.5:
            return t
        t.remove()
        fs -= 0.25


def F1_system(out: Path) -> bool:
    """System overview: data → forecast → time-expanded routing → decisions → delivery.
    Drawn on a fixed grid so boxes align and arrows meet box edges exactly; every
    label is measured against its own box so nothing overflows."""
    fig, ax = plt.subplots(figsize=(7.0, 2.9))
    ax.set_axis_off(); ax.grid(False)
    ax.set_xlim(0, 100); ax.set_ylim(0, 40)
    boxes = [  # (x, y, w, h, title, sub)
        (1, 22, 18, 13, "Public inputs", "FIRMS · ERA5 · SRTM\nWorldCover · OSM"),
        (21.5, 22, 18, 13, "Spread model", "P(ignite) per cell\nleave-one-fire-out"),
        (42, 22, 18, 13, "Hazard field", "time slices of P(ignite)\n0 to 720 min"),
        (62.5, 22, 18, 13, "Routing", "walk-out routes that\navoid the future fire"),
        (83, 22, 16, 13, "Decisions", "A4 sheet · broadcast\nscript · SMS draft"),
        (15, 3, 24.5, 11, "Rescue ingress", "which homes a crew can\nstill reach, and until when"),
        (42, 3, 38.5, 11, "Evidence registry", "every reported number re-derived from its artifact\n(make verify); withdrawn claims kept in the tree"),
    ]
    for x, y, w, h, t, s in boxes:
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2",
                                             facecolor="white", edgecolor=style.INK, linewidth=0.9))
        _fit_text(fig, ax, x + w / 2, y + h - 3.2, w - 2.0, t, 8.0, style.INK, weight="bold")
        _fit_text(fig, ax, x + w / 2, y + h / 2 - 2.4, w - 2.0, s, 6.5, style.MUTED)

    def arrow(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=style.INK, lw=0.9, shrinkA=0, shrinkB=0, mutation_scale=9))
    for xa, xb in ((19, 21.5), (39.5, 42), (60, 62.5), (80.5, 83)):
        arrow(xa, 28.5, xb, 28.5)
    arrow(51, 22, 39.5, 14)      # hazard field feeds rescue ingress
    arrow(39.5, 8.5, 42, 8.5)    # rescue ingress → registry
    arrow(71.5, 22, 61.25, 14)   # routing → registry
    _fit_text(fig, ax, 50, 1.2, 98,
              "Solid arrows: data flow for one fire. The registry sits under every reported number.",
              7.0, style.MUTED)
    style.finish(fig, out / "F1_system.png")
    return True


def F2_lofo_auc(out: Path) -> bool:
    d = load("data/processed/spread_v2_lofo.json")
    if not d or "per_fire_auc" not in d:
        return False
    items = sorted(d["per_fire_auc"].items(), key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=style.FULL)
    y = range(len(items))
    ax.barh(y, [v for _, v in items], color=style.OKABE["blue"], height=0.6)
    ax.set_yticks(list(y)); ax.set_yticklabels([FIRE_LABEL.get(k, k) for k, _ in items])
    ax.set_xlim(0.5, 1.0); ax.set_xlabel("Held-out ROC-AUC (leave-one-fire-out)")
    mean = sum(v for _, v in items) / len(items)
    ax.axvline(mean, color=style.OKABE["vermilion"], lw=1, ls="--")
    ax.text(mean, len(items) - 0.4, f"mean of folds {mean:.2f}", color=style.OKABE["vermilion"], fontsize=8, ha="right", va="bottom")
    if "pooled_auc" in d:
        ax.axvline(d["pooled_auc"], color=style.MUTED, lw=1, ls=":")
        ax.text(d["pooled_auc"], -0.6, f"pooled {d['pooled_auc']:.3f}", color=style.MUTED, fontsize=8, ha="left", va="top")
    for i, (_, v) in enumerate(items):
        ax.text(v + 0.005, i, f"{v:.3f}", va="center", fontsize=8, color=style.INK)
    ax.grid(axis="y", visible=False)
    style.finish(fig, out / "F2_lofo_auc.png")
    return True


def F3_regions(out: Path) -> bool:
    """Three-region routing partition (share of scanned origins) with each region's
    walk-network coverage beside its name, from multi_region_comparison.json."""
    d = load("data/processed/multi_region_comparison.json")
    if not d or not isinstance(d.get("regions"), list):
        return False
    keys = [("both_safe", "safe on both routes"), ("future_aware_only_safe", "safe only on the forecast-aware route"),
            ("no_safe_route", "no safe walking route"), ("fa_exceeds_budget", "forecast-aware route exceeds budget")]
    colors = [style.OKABE["green"], style.OKABE["orange"], style.OKABE["vermilion"], style.OKABE["grey"]]
    rows = [r for r in d["regions"] if all(k in r for k, _ in keys[:3]) and "n_origins_scanned" in r]
    if not rows:
        return False
    fig, ax = plt.subplots(figsize=style.FULL)
    left = [0.0] * len(rows)
    for (k, lab), c in zip(keys, colors):
        share = [100.0 * float(r.get(k, 0)) / float(r["n_origins_scanned"]) for r in rows]
        ax.barh(range(len(rows)), share, left=left, color=c, label=lab, height=0.55)
        for i_, (s_, l_) in enumerate(zip(share, left)):
            if s_ >= 4:
                ax.text(l_ + s_ / 2, i_, f"{s_:.1f} %", ha="center", va="center", fontsize=7.5, color="white" if k != "fa_exceeds_budget" else style.INK)
        left = [l + s_ for l, s_ in zip(left, share)]
    names = []
    for r in rows:
        cov = r.get("envelope_coverage_final_slice")
        lab = r["region"].replace("_", " ").title().replace("Uiseong Andong", "Uiseong-Andong").replace("Uljin Samcheok", "Uljin-Samcheok")
        names.append(f"{lab}\nn = {r['n_origins_scanned']} origins; walk coverage {100 * cov:.1f} %" if cov is not None else lab)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(names, fontsize=8)
    ax.invert_yaxis(); ax.set_xlim(0, 100); ax.set_xlabel("Share of scanned origins (%)")
    ax.legend(ncol=2, loc="lower center", bbox_to_anchor=(0.5, 1.01), fontsize=7.5)
    ax.grid(axis="y", visible=False)
    style.finish(fig, out / "F3_regions.png")
    return True


def F4_operating_point(out: Path) -> bool:
    """Operating point: per-fire recall at the 0.3 advance threshold (left) and the
    pooled out-of-fold precision-recall curve against prevalence (right)."""
    pf = load("data/processed/operating_point/per_fire_recall.json")
    oof = load("data/processed/oof_classification_metrics.json")
    if not pf or not oof or "per_fire" not in pf:
        return False
    items = sorted(pf["per_fire"].items(), key=lambda kv: kv[1]["recall"])
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 3.2), gridspec_kw={"width_ratios": [1.15, 1.0]})
    y = list(range(len(items)))
    ax.barh(y, [v["recall"] for _, v in items], color=style.OKABE["blue"], height=0.58)
    ax.set_yticks(y)
    ax.set_yticklabels([f"{FIRE_LABEL.get(k, k)}\n{v['n_positive']} igniting cells" for k, v in items], fontsize=7.5)
    ax.set_xlim(0, 0.62); ax.set_xlabel("Held-out cell recall at threshold 0.3")
    for i, (_, v) in enumerate(items):
        lab = f"{v['recall']:.3f}" + ("" if v["threshold_is_reachable"] else "  (threshold unreachable)")
        ax.text(v["recall"] + 0.012, i, lab, va="center", fontsize=7.5, color=style.INK)
    ax.axvline(pf["pooled_recall"], color=style.OKABE["vermilion"], lw=1, ls="--")
    ax.text(pf["pooled_recall"] + 0.012, len(items) - 0.42, f"pooled {pf['pooled_recall']:.3f}",
            color=style.OKABE["vermilion"], fontsize=7.5, ha="left", va="bottom")
    ax.grid(axis="y", visible=False)

    pts = oof["pr_curve"]["points"]
    rec = [p["recall"] for p in pts]; pre = [p["precision"] for p in pts]
    order = sorted(range(len(rec)), key=lambda i: rec[i])
    bx.plot([rec[i] for i in order], [pre[i] for i in order], color=style.OKABE["blue"], lw=1.4)
    prev = oof["pr_curve"]["prevalence"]
    bx.axhline(prev, color=style.MUTED, lw=1, ls=":")
    bx.text(0.02, prev + 0.018, f"prevalence {prev:.4f} — the no-skill line", fontsize=7.5,
            color=style.MUTED, ha="left", va="bottom")
    op = [p for p in pts if abs(p["threshold"] - 0.3) < 1e-9]
    if op:
        bx.plot([op[0]["recall"]], [op[0]["precision"]], marker="o", ms=5, color=style.OKABE["vermilion"], zorder=5)
        bx.annotate(f"threshold 0.3\nrecall {op[0]['recall']:.3f}\nprecision {op[0]['precision']:.3f}",
                    xy=(op[0]["recall"] + 0.03, op[0]["precision"] + 0.02), fontsize=7.5,
                    color=style.OKABE["vermilion"], ha="left", va="bottom", linespacing=1.25)
    bx.set_xlim(0, 1.0); bx.set_ylim(0, 0.85)
    bx.set_xlabel("Recall"); bx.set_ylabel("Precision")
    bx.text(0.98, 0.82, f"average precision {oof['pr_curve']['average_precision']:.3f}",
            fontsize=7.5, ha="right", va="top", color=style.INK)
    fig.tight_layout(w_pad=1.6)
    style.finish(fig, out / "F4_operating_point.png")
    return True


def F5_decision_shift(out: Path) -> bool:
    """Canonical Yeongdeok: where the 458 scanned origins land under the fire-blind
    route and then under the forecast-aware route, beside the hazard core's growth."""
    d = load("data/processed/real_roads_real_hazard_canonical.json")
    if not d or "arms" not in d or "slope_digraph_canonical" not in d["arms"]:
        return False
    c = d["arms"]["slope_digraph_canonical"]["counts"]
    n = d["arms"]["slope_digraph_canonical"]["n_origins_scanned"]
    both, fa_only, none_ = c["both_safe"], c["naive_into_FA_safe"], c["no_safe_route"]
    slices = d.get("hazard_source", {}).get("cells_ge_0.5_per_slice")

    unsafe = fa_only + none_
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 3.0), gridspec_kw={"width_ratios": [1.5, 1.0]})
    segs = [("safe", "reaches a refuge without entering the predicted hazard", style.OKABE["green"], "white"),
            ("enters", "route enters the predicted hazard", style.OKABE["orange"], "white"),
            ("none", "no safe walking route exists", style.OKABE["vermilion"], style.INK)]
    data = {"safe": [both, both + fa_only], "enters": [unsafe, 0], "none": [0, none_]}
    left = [0.0, 0.0]
    for key, lab, col, txt in segs:
        vals = data[key]
        ax.barh([0, 1], vals, left=left, color=col, label=lab, height=0.5)
        for i, (v, l) in enumerate(zip(vals, left)):
            if v >= 0.06 * n:
                ax.text(l + v / 2, i, str(v), ha="center", va="center", fontsize=9, weight="bold", color=txt)
            elif v > 0:
                ax.text(l + v + 0.012 * n, i, str(v), ha="left", va="center", fontsize=9, weight="bold", color=style.INK)
        left = [l + v for l, v in zip(left, vals)]
    ax.set_yticks([0, 1])
    ax.set_yticklabels(["Fire-blind route\n(shortest distance)", "Forecast-aware route\n(same origins)"], fontsize=8)
    ax.invert_yaxis(); ax.set_xlim(0, n * 1.04); ax.set_xlabel(f"Scanned walk-network origins (n = {n})")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.30), fontsize=7, ncol=1)
    ax.grid(axis="y", visible=False)

    if slices:
        t = [0, 180, 360, 540, 720][: len(slices)]
        bx.plot(t, slices, marker="o", ms=4, color=style.OKABE["vermilion"], lw=1.4)
        bx.set_xlabel("Forecast horizon (minutes)")
        bx.set_ylabel("Cells at P(ignite) ≥ 0.5")
        bx.set_xticks(t)
        bx.set_ylim(0, max(slices) * 1.22)
        for tt, vv in zip(t, slices):
            bx.text(tt, vv + max(slices) * 0.045, str(vv), ha="center", fontsize=7.5, color=style.INK)
        bx.set_title("Canonical hazard core", fontsize=8.5, color=style.INK)
    else:
        bx.set_axis_off()
    fig.tight_layout(w_pad=1.8)
    style.finish(fig, out / "F5_decision_shift.png")
    return True


def F6_sensitivity(out: Path) -> bool:
    """Three sweeps on the canonical field: evacuation-time budget, slope sampling,
    and a morphological dilation of the forecast."""
    bud = load("data/processed/objective_budget_canonical.json")
    slp = load("data/processed/slope_sweep_canonical.json")
    dil = load("data/processed/dilation_perturbation.json")
    if not bud or not dil or "budget_sweep" not in bud:
        return False
    fig, (ax, bx, cx) = plt.subplots(1, 3, figsize=(7.0, 2.9))

    rows = sorted(bud["budget_sweep"]["rows"], key=lambda r: r["budget_min"])
    xs = [r["budget_min"] for r in rows]
    pos = list(range(len(xs)))
    ax.plot(pos, [100 * r["distance_objective"]["w"] for r in rows], marker="o", ms=4,
            color=style.OKABE["blue"], lw=1.4, label="slope timing")
    ax.plot(pos, [100 * r["flat_distance_objective_control"]["w"] for r in rows], marker="s", ms=3.5,
            color=style.MUTED, lw=1.0, ls="--", label="flat-timing control")
    ax.set_xticks(pos); ax.set_xticklabels([f"{int(v)}" for v in xs], fontsize=8)
    ax.set_xlabel("Evacuation-time budget (min)"); ax.set_ylabel("Failure share of origins (%)")
    ax.set_ylim(0, 65); ax.legend(loc="upper right", fontsize=7)
    ax.set_title("Budget", fontsize=8.5, color=style.INK)

    if slp and "arms" in slp:
        arms = slp["arms"]
        labels, vals = [], []
        for key, lab in (("flat_digraph", "flat"), ("slope_30", "30 m"), ("slope_60", "60 m"), ("slope_90", "90 m")):
            a = arms.get(key)
            if a and "counts" in a:
                labels.append(lab); vals.append(a["counts"]["naive_into_FA_safe"])
        if labels:
            bx.bar(range(len(vals)), vals, color=[style.MUTED] + [style.OKABE["orange"]] * (len(vals) - 1), width=0.6)
            bx.set_xticks(range(len(vals))); bx.set_xticklabels(labels, fontsize=7.5)
            bx.set_ylim(0, max(vals) * 1.3)
            for i, v in enumerate(vals):
                bx.text(i, v + max(vals) * 0.04, str(v), ha="center", fontsize=8, color=style.INK)
            bx.set_xlabel("Slope sampling interval")
            bx.set_ylabel("Origins safe only on the\nforecast-aware route")
            bx.set_title("Terrain sampling", fontsize=8.5, color=style.INK)
    else:
        bx.set_axis_off()

    sw = sorted(dil["sweep"], key=lambda r: r["d_m"])
    dm = [r["d_m"] for r in sw]
    cx.plot(dm, [r["fa_max_hazard"] for r in sw], marker="o", ms=3, color=style.OKABE["blue"], lw=1.4,
            label="forecast-aware route")
    cx.plot(dm, [r["naive_max_hazard"] for r in sw], marker="s", ms=3, color=style.OKABE["vermilion"], lw=1.0,
            ls="--", label="fire-blind route")
    cx.axhline(dil["p_cut"], color=style.MUTED, lw=1, ls=":")
    brk = dil["breaking_distance"]["fa_first_grid_point_reaching_pcut_m"]
    cx.axvline(brk, color=style.OKABE["green"], lw=1)
    cx.text(brk + 25, 0.30, f"forecast-aware route\nbreaks at {brk} m", fontsize=7.2,
            color=style.OKABE["green"], va="center", ha="left", linespacing=1.25)
    cx.text(1000, dil["p_cut"] + 0.02, "cutoff 0.5", fontsize=7.2, color=style.MUTED, ha="right", va="bottom")
    cx.set_xlabel("Forecast dilation radius (m)"); cx.set_ylabel("Peak P(ignite) on the route")
    cx.set_ylim(0, 1.08); cx.legend(loc="lower right", fontsize=7, framealpha=0.0)
    cx.set_title("Forecast error", fontsize=8.5, color=style.INK)
    fig.tight_layout(w_pad=1.4)
    style.finish(fig, out / "F6_sensitivity.png")
    return True


def F7_dispatch_ordering(out: Path) -> bool:
    """Dispatch ordering: rescues completed at the committed operating cell (left) and
    the win/tie/loss tally of deadline-first against nearest-first by window (right)."""
    d = load("data/processed/dispatch_ordering_comparison.json")
    if not d or "summary" not in d:
        return False
    arm = d["arms"].get("yeongdeok_2025|synthetic")
    cell = arm["grid"].get("depot_return|W75|s25p0|d30") if arm else None
    if not cell:
        return False
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 3.0), gridspec_kw={"width_ratios": [1.15, 1.0]})
    teams = sorted(cell["nearest_eta"], key=lambda k: int(k))
    x = [int(t) for t in teams]
    series = [("nearest_eta", "nearest first", style.OKABE["green"], "-", "o"),
              ("deadline_closing_window", "deadline first (shipped)", style.OKABE["vermilion"], "-", "s"),
              ("earliest_closure", "earliest closure", style.OKABE["blue"], "--", "^"),
              ("list_order", "no sort (scan order)", style.MUTED, ":", "v")]
    for key, lab, col, ls, mk in series:
        ax.plot(x, [cell[key][t] for t in teams], marker=mk, ms=4, lw=1.3, ls=ls, color=col, label=lab)
    rnd = [cell["random"][t] for t in teams]
    ax.errorbar(x, [r["mean"] for r in rnd], yerr=[r["sd"] for r in rnd], fmt="none",
                ecolor=style.OKABE["purple"], elinewidth=1.0, capsize=2.5)
    ax.plot(x, [r["mean"] for r in rnd], marker="d", ms=3.5, lw=1.0, ls="-.", color=style.OKABE["purple"],
            label="random order (200 seeds)")
    ax.set_xticks(x); ax.set_xlabel("Rescue teams available"); ax.set_ylabel("Homes reached within the window")
    ax.legend(fontsize=7, loc="upper left")
    ax.set_title("Committed operating cell\n(window 75 min, service 25 min, delay 30 min)", fontsize=8.5, color=style.INK)

    by = d["summary"]["by_window"]
    wins = sorted(by, key=lambda k: int(k[1:]))
    cats = [("deadline_wins", "deadline first wins", style.OKABE["green"]),
            ("ties", "tie", style.OKABE["grey"]),
            ("deadline_loses", "deadline first loses", style.OKABE["vermilion"])]
    left = [0.0] * len(wins)
    for key, lab, col in cats:
        vals = [by[w][key] for w in wins]
        bx.barh(range(len(wins)), vals, left=left, color=col, label=lab, height=0.5)
        for i, (v, l) in enumerate(zip(vals, left)):
            if v > 0:
                bx.text(l + v / 2, i, str(v), ha="center", va="center", fontsize=8,
                        color=style.INK if key == "ties" else "white")
        left = [l + v for l, v in zip(left, vals)]
    bx.set_yticks(range(len(wins)))
    bx.set_yticklabels([f"window {w[1:]} min" + ("\n(committed)" if w == "W75" else "\n(exploratory)") for w in wins], fontsize=8)
    bx.invert_yaxis(); bx.set_xlabel("Configuration cells (of 180 per window)")
    bx.legend(fontsize=7, ncol=1, loc="upper center", bbox_to_anchor=(0.5, -0.24))
    bx.grid(axis="y", visible=False)
    fig.tight_layout(w_pad=1.6)
    style.finish(fig, out / "F7_dispatch_ordering.png")
    return True


FIGURES = [F1_system, F2_lofo_auc, F3_regions, F4_operating_point, F5_decision_shift,
           F6_sensitivity, F7_dispatch_ordering]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "paper" / "figures"))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    drawn, skipped = [], []
    for f in FIGURES:
        (drawn if f(out) else skipped).append(f.__name__)
    print(f"[figures] drawn {drawn}; skipped (artifact absent) {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
