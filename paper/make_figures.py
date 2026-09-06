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
    arrow(46, 22, 27.25, 14)     # hazard field feeds rescue ingress, meeting its top edge
                                 # at the centre (39.5, 14 is the box's corner, and an
                                 # arrowhead on a corner reads as pointing between boxes)
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
    # The two reference lines are named in a boxed legend, not in floating text.
    # Inline labels put "mean of folds" across a bar's value and "pooled" on top of
    # the x-axis tick labels (critic #7, F36); a legend in the empty lower-right
    # corner — empty because the bars there are the shortest — can collide with
    # neither. Values are written inside the bars for the same reason.
    mean = sum(v for _, v in items) / len(items)
    ax.axvline(mean, color=style.OKABE["vermilion"], lw=1, ls="--",
               label=f"mean of folds {mean:.3f}")
    if "pooled_auc" in d:
        ax.axvline(d["pooled_auc"], color=style.MUTED, lw=1, ls=":",
                   label=f"pooled out-of-fold {d['pooled_auc']:.3f}")
    for i, (_, v) in enumerate(items):
        ax.text(v - 0.008, i, f"{v:.3f}", va="center", ha="right", fontsize=8, color="white")
    style.boxed_legend(ax, loc="lower right")
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
    style.label_panels([ax, bx])
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
    style.label_panels([ax, bx])
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
        # Margin on both axes so the last point's value label, centred over a point that
        # sits on the right-hand tick, does not run into the panel frame.
        bx.set_xlim(-0.06 * t[-1], t[-1] * 1.06)
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
    style.label_panels([ax, bx, cx])

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
    style.label_panels([ax, bx])
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
    # Both legends sit below their panel. Inside the panel there is no corner free of
    # data: every series rises left to right, so an upper-left box crosses the
    # nearest-first line at the middle team counts and a lower-right box crosses the
    # scan-order line. The operating cell takes the top-left instead, which is empty
    # because every series starts near zero there.
    ax.legend(fontsize=7, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.24))
    ax.set_title("Committed operating cell", fontsize=8.5, color=style.INK)
    ax.text(0.03, 0.97, "window 75 min · service 25 min · delay 30 min", transform=ax.transAxes,
            ha="left", va="top", fontsize=7, color=style.MUTED)

    by = d["summary"]["by_window"]
    wins = sorted(by, key=lambda k: int(k[1:]))
    # Colour means the same thing in both panels: vermilion is deadline-first, teal is
    # nearest-first. The first version of this panel coloured "deadline first wins" with
    # panel a's nearest-first teal, so one colour carried two opposite meanings side by
    # side (critic #7, F36). Ties take the style's neutral rule colour, which is not a
    # series colour in panel a.
    cats = [("deadline_wins", "deadline first ahead", style.OKABE["vermilion"]),
            ("ties", "tie", style.LINE),
            ("deadline_loses", "nearest first ahead", style.OKABE["green"])]
    left = [0.0] * len(wins)
    for key, lab, col in cats:
        vals = [by[w][key] for w in wins]
        bx.barh(range(len(wins)), vals, left=left, color=col, label=lab, height=0.5)
        for i, (v, l) in enumerate(zip(vals, left)):
            if v > 0:
                bx.text(l + v / 2, i, str(v), ha="center", va="center", fontsize=8,
                        color=style.INK if key == "ties" else "white")
        left = [l + v for l, v in zip(left, vals)]
    bx.set_xlim(0, max(sum(by[w][k] for k, _, _ in cats) for w in wins) * 1.02)
    bx.set_yticks(range(len(wins)))
    bx.set_yticklabels([f"window {w[1:]} min" + ("\n(committed)" if w == "W75" else "\n(exploratory)") for w in wins], fontsize=8)
    bx.invert_yaxis(); bx.set_xlabel("Configuration cells (of 180 per window)")
    bx.legend(fontsize=7, ncol=1, loc="upper center", bbox_to_anchor=(0.5, -0.24))
    bx.grid(axis="y", visible=False)
    fig.tight_layout(w_pad=1.6)
    style.finish(fig, out / "F7_dispatch_ordering.png")
    return True


# ---------------------------------------------------------------------------
# F8: the routing map. Everything below reads committed snapshots and artifacts
# only (data/snapshots/*, data/processed/*) and recomputes the two example routes
# with the repository's own router; nothing is fetched at figure time.
# ---------------------------------------------------------------------------
_F8_NPZ = "data/processed/routing_demo_canonical.npz"
_F8_JSON = "data/processed/real_roads_real_hazard_canonical.json"
_F8_MANIFEST = "data/snapshots/MANIFEST.json"


def _snapshot(source: str, region: str) -> Path | None:
    """Resolve one stored snapshot from data/snapshots/MANIFEST.json, or None."""
    man = load(_F8_MANIFEST)
    if not man:
        return None
    hits = [s for s in man.get("snapshots", []) if s.get("source") == source
            and s.get("region") == region and s.get("stored_file")]
    if len(hits) != 1:
        return None
    p = REPO / "data" / "snapshots" / hits[0]["stored_file"]
    return p if p.exists() else None


def _graticule(ax, to_ll, to_xy, step_deg: float, fmt_lon="{:.1f}°E", fmt_lat="{:.1f}°N"):
    """Lat/lon graticule on a projected (EPSG:5179) panel: thin grey lines inside the
    frame, tick labels where each meridian meets the bottom edge and each parallel
    meets the left edge, so the labels sit on the outer edges as in Moreno et al."""
    import numpy as np
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    cx = np.array([x0, x1, x1, x0]); cy = np.array([y0, y0, y1, y1])
    lon_c, lat_c = to_ll.transform(cx, cy)
    lons = np.arange(np.floor(lon_c.min() / step_deg) * step_deg, lon_c.max() + step_deg, step_deg)
    lats = np.arange(np.floor(lat_c.min() / step_deg) * step_deg, lat_c.max() + step_deg, step_deg)
    xt, xl, yt, yl = [], [], [], []
    for lon in lons:
        la = np.linspace(lat_c.min() - 0.1, lat_c.max() + 0.1, 200)
        gx, gy = to_xy.transform(np.full_like(la, lon), la)
        ax.plot(gx, gy, color="white", lw=0.5, alpha=0.75, zorder=6)
        ax.plot(gx, gy, color=style.INK, lw=0.3, alpha=0.55, zorder=6)
        # where the meridian crosses the bottom edge
        k = np.argsort(gy); xb = np.interp(y0, gy[k], gx[k])
        if x0 < xb < x1:
            xt.append(xb); xl.append(fmt_lon.format(lon))
    for lat in lats:
        lo = np.linspace(lon_c.min() - 0.1, lon_c.max() + 0.1, 200)
        gx, gy = to_xy.transform(lo, np.full_like(lo, lat))
        ax.plot(gx, gy, color="white", lw=0.5, alpha=0.75, zorder=6)
        ax.plot(gx, gy, color=style.INK, lw=0.3, alpha=0.55, zorder=6)
        k = np.argsort(gx); yb = np.interp(x0, gx[k], gy[k])
        if y0 < yb < y1:
            yt.append(yb); yl.append(fmt_lat.format(lat))
    ax.set_xticks(xt); ax.set_xticklabels(xl, fontsize=7)
    ax.set_yticks(yt); ax.set_yticklabels(yl, fontsize=7, rotation=90, va="center")
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)


def _scale_bar(ax, km: float, loc=(0.04, 0.035)):
    """A two-segment black/white scale bar in a small white box, bottom-left."""
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    w, h = x1 - x0, y1 - y0
    bx, by = x0 + loc[0] * w, y0 + loc[1] * h
    L = km * 1000.0; t = 0.012 * h
    ax.add_patch(mpatches.Rectangle((bx - 0.012 * w, by - 0.02 * h), L + 0.024 * w, t + 0.055 * h,
                                    facecolor="white", edgecolor=style.INK, linewidth=0.5, zorder=20))
    ax.add_patch(mpatches.Rectangle((bx, by), L / 2, t, facecolor=style.INK, edgecolor=style.INK, linewidth=0.5, zorder=21))
    ax.add_patch(mpatches.Rectangle((bx + L / 2, by), L / 2, t, facecolor="white", edgecolor=style.INK, linewidth=0.5, zorder=21))
    for v, xx in ((0, bx), (km / 2, bx + L / 2), (km, bx + L)):
        ax.text(xx, by + t + 0.006 * h, f"{v:g}" + (" km" if v == km else ""), ha="center", va="bottom",
                fontsize=6.5, color=style.INK, zorder=22)


def _hillshade(dem_path: Path, extent, res_m: float):
    """Reproject the committed SRTM GeoTIFF onto an EPSG:5179 grid covering `extent`
    and return (hillshade array, imshow extent). Offline; rasterio only."""
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.warp import reproject
    from matplotlib.colors import LightSource
    x0, y0, x1, y1 = extent
    ncol, nrow = int(round((x1 - x0) / res_m)), int(round((y1 - y0) / res_m))
    dst = np.full((nrow, ncol), np.nan, dtype="float32")
    with rasterio.open(dem_path) as src:
        reproject(rasterio.band(src, 1), dst, dst_transform=from_origin(x0, y1, res_m, res_m),
                  dst_crs="EPSG:5179", dst_nodata=np.nan, resampling=Resampling.bilinear)
    dem = np.where(np.isfinite(dst), dst, np.nan)
    filled = np.where(np.isfinite(dem), dem, np.nanmin(dem))
    hs = LightSource(azdeg=315, altdeg=45).hillshade(filled, vert_exag=1.5, dx=res_m, dy=res_m)
    hs = np.where(np.isfinite(dem), hs, np.nan)
    return hs, (x0, x1, y0, y1)


def _route_xy(Gp, route, net):
    """Stitch a node route into a polyline using the OSM edge geometries (EPSG:5179);
    straight segments where an edge carries none."""
    import numpy as np
    from shapely.geometry import LineString
    pts = []
    for u, v in zip(route[:-1], route[1:]):
        geom = None
        for a, b, rev in ((u, v, False), (v, u, True)):
            if Gp.has_edge(a, b):
                data = min(Gp[a][b].values(), key=lambda d: d.get("length", 0.0))
                g = data.get("geometry")
                if g is None:
                    g = LineString([(Gp.nodes[a]["x"], Gp.nodes[a]["y"]), (Gp.nodes[b]["x"], Gp.nodes[b]["y"])])
                geom = list(g.coords)[::-1] if rev else list(g.coords)
                break
        if geom is None:
            geom = [net.node_xy(u), net.node_xy(v)]
        pts.extend(geom if not pts else geom[1:])
    return np.asarray(pts)


def F8_routing_map(out: Path) -> bool:
    """Canonical Yeongdeok 2025 on a hillshaded ground: (a) the forecast hazard field
    at the 720-minute horizon over the simulation canvas, with the walk-network box;
    (b) the walk network, refuges, the 458 scanned origins classed by outcome, and
    example origins whose fire-blind route enters the forecast while a forecast-aware
    route stays clear. Routes are recomputed with the repository router from the
    committed snapshots, so the figure carries no stored geometry of its own."""
    import numpy as np
    canon = load(_F8_JSON)
    npz_p = REPO / _F8_NPZ
    dem_p = _snapshot("srtm-dem", "yeongdeok-2025")
    walk_p = _snapshot("osm-walk", "yeongdeok-2025")
    shel_p = _snapshot("osm-shelters", "yeongdeok-2025")
    if not canon or not npz_p.exists() or not (dem_p and walk_p and shel_p):
        return False
    try:
        import osmnx as ox
        from pyproj import Transformer
        sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(REPO / "scripts"))
        from wildfireguardian.routing.evacuation import future_aware_route, naive_route
        from wildfireguardian.routing.hazard import HazardSequence
        from wildfireguardian.routing.slope import build_walk_network, load_snapshot_graph
        from wildfireguardian.spread_v2.grid import CoarseGrid
        from run_real_roads_real_hazard_slope import candidate_origins
        from run_multi_region_routing import read_poi_snapshot
    except Exception as e:  # noqa: BLE001
        print(f"[figures] F8 skipped: {e}", file=sys.stderr)
        return False
    to_ll = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    to_xy = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

    # --- hazard field (committed npz) and the scan's parameters (committed json)
    z = np.load(npz_p)
    haz = z["haz_stack"].astype(np.float32); times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax, cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    hazard = HazardSequence(grid=grid, times_min=times, surfaces=[haz[i] for i in range(haz.shape[0])])
    prm = canon["parameters"]; arm = canon["arms"]["slope_digraph_canonical"]
    p_cut = float(prm["p_cut"]); horizon = int(times[-1])
    rb = canon["preflight"]["routing_bbox_5179"]

    # --- walk network (snapshot), slope timing from the snapshot DEM, refuges (snapshot)
    G = load_snapshot_graph(walk_p)
    net, _ = build_walk_network(G, dem_p, sampling_m=float(prm["slope_sampling_m"]),
                                max_abs_slope=float(prm["max_abs_slope"]), directed=True, apply_slope=True)
    dests, n_pois = read_poi_snapshot(shel_p, kind="shelter")
    net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
    Gp = ox.project_graph(G, to_crs="EPSG:5179")
    edges = ox.graph_to_gdfs(Gp, nodes=False, edges=True)

    # --- the scan itself, in the committed order, with the committed classification
    cand, _ = candidate_origins(net, hazard, haz, (xmin, ymin, xmax, ymax, cell), p_cut)
    classes = {"both_safe": [], "naive_into_FA_safe": [], "no_safe_route": [], "other": []}
    routes = {}
    for n in cand:
        nv = naive_route(net, n, hazard, departure_min=0.0, p_cut=p_cut, objective="length_m")
        fa = future_aware_route(net, n, hazard, departure_min=0.0, time_budget_min=float(prm["time_budget_min"]),
                                p_cut=p_cut, time_step_min=float(prm["time_step_min"]))
        if nv.reached and nv.enters_hazard and fa.reached and not fa.enters_hazard:
            classes["naive_into_FA_safe"].append(n); routes[n] = (nv, fa)
        elif nv.reached and nv.enters_hazard and not fa.reached:
            classes["no_safe_route"].append(n)
        elif nv.reached and not nv.enters_hazard and fa.reached and not fa.enters_hazard:
            classes["both_safe"].append(n)
        else:
            classes["other"].append(n)
    counts_ok = all(len(classes[k]) == arm["counts"][k] for k in ("both_safe", "naive_into_FA_safe", "no_safe_route")) \
        and len(cand) == arm["n_origins_scanned"]
    if not counts_ok:
        print("[figures] F8: recomputed partition differs from the committed artifact; counts left off the legend", file=sys.stderr)
    # Example origins: walk the fire-blind-fails origins in scan order and keep one
    # whenever it lies at least 4 km from every origin already kept (so the examples
    # do not overprint), up to three.
    examples = []
    for n in classes["naive_into_FA_safe"]:
        x, y = net.node_xy(n)
        if all(np.hypot(x - ex[1], y - ex[2]) >= 4000 for ex in examples):
            examples.append((n, x, y))
        if len(examples) == 3:
            break

    # --- figure: (a) canvas context, (b) the walk box
    a_ext = (1130400.0, 1802400.0, 1187400.0, 1862300.0)   # inner rectangle of the snapshot DEM in EPSG:5179
    m = 1200.0
    b_ext = (rb[0] - m, rb[1] - m, rb[2] + m, rb[3] + m)
    fig = plt.figure(figsize=(7.0, 4.75))
    gs = fig.add_gridspec(1, 2, width_ratios=[(a_ext[2] - a_ext[0]) / (a_ext[3] - a_ext[1]),
                                              (b_ext[2] - b_ext[0]) / (b_ext[3] - b_ext[1])], wspace=0.16)
    ax, bx = fig.add_subplot(gs[0]), fig.add_subplot(gs[1])
    seq = plt.get_cmap(style.SEQ_CMAP)
    hz_ext = (xmin, xmax, ymin, ymax)
    for a, ext, res in ((ax, a_ext, 90.0), (bx, b_ext, 45.0)):
        hs, hs_ext = _hillshade(dem_p, ext, res)
        a.imshow(hs, extent=hs_ext, cmap="gray", vmin=-0.1, vmax=1.15, origin="upper", zorder=1, interpolation="bilinear")
        a.set_xlim(ext[0], ext[2]); a.set_ylim(ext[1], ext[3]); a.set_aspect("equal")
    # (a): the P(ignite) field at the horizon, masked below 0.05, and the 0.5 isolines
    field = np.ma.masked_less(haz[-1], 0.05)
    im = ax.imshow(field, extent=hz_ext, cmap=seq, vmin=0, vmax=1, alpha=0.8, origin="upper", zorder=3, interpolation="nearest")
    # The horizon's 0.5 isoline is drawn on a one-cell Gaussian smoothing of the slice,
    # for display only: the field itself is cell-wise and drawn as such above, and a
    # contour traced through it cell by cell dissolves into hundreds of one-cell rings.
    # The 0-minute slice is binary and its cells are scattered, so no isoline can trace
    from scipy.ndimage import gaussian_filter
    from matplotlib.colors import ListedColormap
    xs = xmin + (np.arange(haz.shape[2]) + 0.5) * cell; ys = ymax - (np.arange(haz.shape[1]) + 0.5) * cell
    # it; those cells are drawn filled, in (a) only so that (b) stays legible.
    t0 = np.ma.masked_less(haz[0], p_cut)
    ax.imshow(t0, extent=hz_ext, cmap=ListedColormap([style.PALETTE["teal"]]), alpha=0.9, origin="upper", zorder=5,
              interpolation="nearest")
    for a in (ax, bx):
        a.contour(xs, ys, gaussian_filter(haz[-1], 1.0), levels=[p_cut], colors=[style.PALETTE["blue"]], linewidths=1.1,
                  linestyles="dashed", zorder=7)
    ax.plot(*z["ign_xy"], marker="*", ms=9, color=style.PALETTE["yellow"], mec=style.INK, mew=0.5, ls="none", zorder=9)
    ax.add_patch(mpatches.Rectangle((rb[0], rb[1]), rb[2] - rb[0], rb[3] - rb[1], facecolor="none",
                                    edgecolor=style.INK, linewidth=1.0, zorder=8))
    ax.text(rb[0] + 0.5 * (rb[2] - rb[0]), rb[3] + 900, "walk network (panel b)", ha="center", va="bottom", fontsize=6.5,
            color=style.INK, zorder=9, bbox=dict(facecolor="white", edgecolor="none", pad=0.6, alpha=0.85))
    # (b): walk network, refuges, classed origins, example routes
    edges.plot(ax=bx, color="#6E6E6E", linewidth=0.22, alpha=0.9, zorder=4)
    bx.imshow(field, extent=hz_ext, cmap=seq, vmin=0, vmax=1, alpha=0.35, origin="upper", zorder=3, interpolation="nearest")
    for key, col, mk, ms_, zo in (("both_safe", "#F2F2F2", "o", 2.6, 8), ("naive_into_FA_safe", style.PALETTE["brown"], "o", 4.0, 9),
                                  ("no_safe_route", style.INK, "x", 5.0, 10)):
        pts = np.array([net.node_xy(n) for n in classes[key]]) if classes[key] else np.empty((0, 2))
        if len(pts):
            bx.plot(pts[:, 0], pts[:, 1], ls="none", marker=mk, ms=ms_, mfc=col, mec=style.INK if mk == "o" else col,
                    mew=0.35 if mk == "o" else 1.0, zorder=zo)
    sx = np.array([net.node_xy(n) for n in sorted(net.shelters)])
    bx.plot(sx[:, 0], sx[:, 1], ls="none", marker="^", ms=5.0, mfc=style.PALETTE["blue"], mec=style.INK, mew=0.4, zorder=11)
    for i, (n, x, y) in enumerate(examples, start=1):
        nv, fa = routes[n]
        # Each route is cased in white so it reads over the hillshade and the field.
        p = _route_xy(Gp, nv.route, net)
        bx.plot(p[:, 0], p[:, 1], color="white", lw=3.2, zorder=12)
        bx.plot(p[:, 0], p[:, 1], color=style.PALETTE["grey"], lw=1.8, ls=(0, (3, 1.5)), zorder=12.5)
        p = _route_xy(Gp, fa.route, net)
        bx.plot(p[:, 0], p[:, 1], color="white", lw=3.2, zorder=13)
        bx.plot(p[:, 0], p[:, 1], color=style.PALETTE["fire"], lw=1.8, zorder=13.5)
        bx.plot(x, y, marker="o", ms=6.5, mfc="white", mec=style.INK, mew=0.8, ls="none", zorder=14)
        bx.text(x, y, str(i), ha="center", va="center", fontsize=5.5, color=style.INK, zorder=15)
    # graticule, scale bars, panel letters
    _graticule(ax, to_ll, to_xy, 0.2); _graticule(bx, to_ll, to_xy, 0.1)
    _scale_bar(ax, 10); _scale_bar(bx, 5)
    for a, letter in ((ax, "a"), (bx, "b")):
        a.text(0.02, 0.975, f"{letter})", transform=a.transAxes, ha="left", va="top", fontsize=9, color=style.INK, zorder=30,
               bbox=dict(facecolor="white", edgecolor="none", pad=1.2, alpha=0.9))
    # colour bar for (a), boxed inside the panel
    cax = ax.inset_axes([0.585, 0.905, 0.36, 0.028])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal", ticks=[0, 0.5, 1])
    cb.ax.tick_params(labelsize=6.5, length=2, width=0.5, pad=1.5); cb.outline.set_linewidth(0.5)
    cax.set_title(f"P(ignite) at {horizon} min", fontsize=6.5, pad=2)
    ax.add_patch(mpatches.Rectangle((0.545, 0.865), 0.435, 0.12, transform=ax.transAxes, facecolor="white",
                                    edgecolor=style.INK, linewidth=0.5, zorder=cax.get_zorder() - 1, alpha=0.95))
    # legend, boxed, below both panels
    from matplotlib.lines import Line2D
    n_or = arm["n_origins_scanned"]; c = arm["counts"]
    lab = (lambda k, s: f"{s} ({c[k]})" if counts_ok else s)
    handles = [
        mpatches.Patch(facecolor=style.PALETTE["teal"], edgecolor=style.INK, linewidth=0.4, label=f"P(ignite) ≥ {p_cut:g} at 0 min"),
        Line2D([], [], color=style.PALETTE["blue"], lw=1.1, ls="--", label=f"P(ignite) ≥ {p_cut:g} at {horizon} min"),
        Line2D([], [], marker="*", ms=8, mfc=style.PALETTE["yellow"], mec=style.INK, mew=0.5, ls="none", label="reported ignition"),
        Line2D([], [], marker="^", ms=5, mfc=style.PALETTE["blue"], mec=style.INK, mew=0.4, ls="none", label=f"refuge ({n_pois} OSM POIs)"),
        Line2D([], [], marker="o", ms=3, mfc="#F2F2F2", mec=style.INK, mew=0.35, ls="none", label=lab("both_safe", "origin: safe on both routes")),
        Line2D([], [], marker="o", ms=4, mfc=style.PALETTE["brown"], mec=style.INK, mew=0.35, ls="none",
               label=lab("naive_into_FA_safe", "origin: safe only forecast-aware")),
        Line2D([], [], marker="x", ms=5, color=style.INK, mew=1.0, ls="none", label=lab("no_safe_route", "origin: no safe walking route")),
        Line2D([], [], color=style.PALETTE["grey"], lw=1.6, ls=(0, (3, 1.5)), label="fire-blind route (shortest)"),
        Line2D([], [], color=style.PALETTE["fire"], lw=1.6, label="forecast-aware route"),
    ]
    if counts_ok:
        bx.text(0.975, 0.03, f"n = {n_or} scanned origins", transform=bx.transAxes, ha="right", va="bottom", fontsize=6.5,
                color=style.INK, zorder=30, bbox=dict(facecolor="white", edgecolor=style.INK, linewidth=0.5, pad=2.0))
    fig.subplots_adjust(left=0.06, right=0.985, top=0.985, bottom=0.215)
    # Equal-aspect panels end up shorter than their slot, so the legend is anchored
    # to the drawn frame's bottom edge (measured after layout) instead of the figure's.
    fig.canvas.draw()
    lo = min(ax.get_position().y0, bx.get_position().y0)
    lg = fig.legend(handles=handles, loc="upper center", ncol=3, fontsize=6.8, frameon=True, bbox_to_anchor=(0.52, lo - 0.055),
                    handlelength=1.6, columnspacing=1.2, handletextpad=0.6, borderaxespad=0.2)
    lg.get_frame().set_linewidth(0.5); lg.get_frame().set_edgecolor(style.INK)
    style.finish(fig, out / "F8_routing_map.png")
    return True


def F9_present_perimeter(out: Path) -> bool:
    """How the present-perimeter opponent fails, across the five buffer widths that
    were run (Uiseong-Andong 2025, committed canonical arm).

    ⚠ NOT REFERENCED BY THE MANUSCRIPT (lap 10, 2026-09-06; paper/GAPS.md gap G8).
    It is built and committed so it stays reproducible and can drop straight into
    §4.5 once NH-032 is answered, and it is kept rather than deleted per CHARTER
    §3.7. check_paper.py checks that every referenced figure exists, not that every
    drawn figure is referenced, so an unreferenced figure is not a gate failure.

    Only the three FAILURE classes are drawn, and deliberately not the safe total:
    the safe total against the forecast-aware arm's own total is the contested
    margin the project has not settled, and a figure is not the place to settle it.
    What the failure classes show is the part both builds of the opponent agree on
    — that the two ways of failing trade off against each other as the buffer
    widens.

    ⚠ The first version of this function contradicted the paragraph above and the
    lap reviewer caught it: it printed each bar's TOTAL above the stack and put the
    origin count in the y-axis label, so subtracting one from the other recovered
    the whole safe series the docstring says it does not draw — and, with the
    forecast-aware total that Table 2 of the manuscript already determines, the
    margin itself. Neither the totals nor the denominator is drawn now. The y axis
    is a bare count, and a reader who wants the safe totals has to go to the
    committed artifact, where they carry their caveats.

    The x axis is CATEGORICAL on purpose. The five widths are 250 / 500 / 1000 /
    2000 / 3000 m, so the nearest measured neighbours of the middle width are a
    factor of two away on either side; drawing them on a metric axis with a line
    through them would assert a curve shape between the samples that the run
    cannot resolve (WFG-127). Five bars, no interpolation.
    """
    d = load("data/processed/present_perimeter_arm_uiseong_andong_2025.json")
    if not d or not isinstance(d.get("buffer_sensitivity"), list):
        return False
    rows = sorted(d["buffer_sensitivity"], key=lambda r: float(r["buffer_m"]))
    if not rows:
        return False
    classes = [("failed_enters_hazard", "route crosses ground that is alight when the walker crosses it", style.PALETTE["fire"]),
               ("failed_unreachable", "no route to any refuge outside the buffer", style.PALETTE["slate"]),
               ("failed_over_budget", "reaches a refuge, but after the 600-minute budget", style.PALETTE["brown"])]
    fig, ax = plt.subplots(figsize=style.FULL)
    x = list(range(len(rows)))
    bottom = [0.0] * len(rows)
    for key, label, colour in classes:
        vals = [float(r.get(key, 0)) for r in rows]
        ax.bar(x, vals, bottom=bottom, color=colour, label=label, width=0.58)
        for xi, (v, b) in enumerate(zip(vals, bottom)):
            if v >= 6:
                ax.text(xi, b + v / 2, f"{int(v)}", ha="center", va="center", fontsize=7.5, color="white")
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_xticks(x)
    ax.set_xticklabels([f"{int(r['buffer_m'])} m" if float(r["buffer_m"]) < 1000
                        else f"{float(r['buffer_m']) / 1000:g} km" for r in rows])
    ax.set_xlabel("Buffer width refused beyond the slice-0 perimeter (five measured widths, categorical spacing)")
    ax.set_ylabel("Origins failing")
    ax.set_ylim(0, max(bottom) * 1.12)
    # Legend below the axes: the tall bars sit at both ends of the x range, so no
    # corner inside the panel is provably empty (paper/README.md, figure rule 2).
    lg = ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=1, fontsize=7.5)
    lg.get_frame().set_linewidth(0.5)
    ax.grid(axis="y", visible=True)
    style.finish(fig, out / "F9_present_perimeter.png")
    return True


FIGURES = [F1_system, F2_lofo_auc, F3_regions, F4_operating_point, F5_decision_shift,
           F6_sensitivity, F7_dispatch_ordering, F8_routing_map, F9_present_perimeter]


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
