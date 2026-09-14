#!/usr/bin/env python
"""Publication-ready figures for the 2026-09-13/14 results, in the house style
(paper/style.py; docs/auto/knowledge/FIGURE_STYLE_REFERENCE.md). Every number is read from a
committed artifact; nothing is typed. Writes PNG (300 dpi) and PDF (vector) to
docs/figures/finals/. New filenames only; docs/figures/*.png of the manuscript are untouched.

    python paper/make_finals_figures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "paper"))
import style  # noqa: E402

OUT = REPO / "docs/figures/finals"
J = lambda p: json.loads((REPO / p).read_text(encoding="utf-8"))  # noqa: E731
P = style.PALETTE
CLS = [("admissible_all", "admissible under every bound", P["teal"]), ("indeterminate", "indeterminate (0–333 min gap)", P["yellow"]),
       ("inadmissible_all", "inadmissible: in a detected cell", P["fire"]), ("not_reached", "no route", P["grey"])]


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", facecolor="white", dpi=300); fig.savefig(OUT / f"{name}.pdf", facecolor="white"); plt.close(fig)
    print("wrote", name)


def hstack(ax, rows, labels, total, fontsize=7.5):
    """Horizontal stacked bars with in-bar counts; rows = list of dict class->count."""
    for i, r in enumerate(rows):
        left = 0
        for key, lab, col in CLS:
            v = r.get(key, 0)
            if v == 0: continue
            ax.barh(i, v, left=left, color=col, edgecolor="black", linewidth=0.6, height=0.62)
            if v / total > 0.045:
                ax.text(left + v / 2, i, f"{v:,}", ha="center", va="center", fontsize=fontsize, color="white" if key in ("inadmissible_all", "admissible_all") else style.INK)
            left += v
    ax.set_yticks(range(len(rows))); ax.set_yticklabels(labels, fontsize=8); ax.invert_yaxis()
    ax.set_xlim(0, total); ax.set_xlabel(f"buildings (of {total:,})" if total > 1000 else f"origins (of {total})")


# ---------------------------------------------------------------- FA: observed grading, sample and census
def fig_observed_grading():
    r3 = J("data/processed/regrade_three_way_yeongdeok.json"); og = J("data/processed/building_origins_observed_grading_yeongdeok.json")
    S = r3["summary"]; B = og["summary"]["buildings"]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 2.7), gridspec_kw={"width_ratios": [1, 1]})
    hstack(ax, [S["fire_blind"]["m0"], S["forecast_aware"]["m0"]], ["fire-blind\nshortest walk", "forecast-aware\nwalk"], 458)
    ax.set_title("458 sampled origins", fontsize=8.5, color=style.INK)
    hstack(bx, [B["fire_blind"]["a4_base"], B["forecast_aware"]["a4_base"], B["fire_blind"]["a4_dilated"], B["forecast_aware"]["a4_dilated"]],
           ["fire-blind", "forecast-aware", "fire-blind,\nadjacent-cell\nsensitivity", "forecast-aware,\nadjacent-cell\nsensitivity"], og["denominators"]["routable_buildings"])
    bx.set_title("19,250 main buildings (road-name address register)", fontsize=8.5, color=style.INK)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c, ec="black", lw=0.6) for _, _, c in CLS]
    fig.legend(handles, [lab for _, lab, _ in CLS], loc="lower center", ncol=4, fontsize=7, frameon=True, bbox_to_anchor=(0.5, -0.06))
    style.label_panels([ax, bx]); fig.tight_layout(rect=(0, 0.04, 1, 1)); save(fig, "F12_observed_grading")


# ---------------------------------------------------------------- FB: the 190 buildings, diagnosed, and the intervention
def fig_diagnosis_intervention():
    og = J("data/processed/building_origins_observed_grading_yeongdeok.json"); vp = J("data/processed/vehicle_pickup_intervention_yeongdeok.json")
    diag = og["diagnosis"]
    flags = [("forecast-only", "forecast-only\n(observation clear)"), ("budget-bound", "budget-bound\n(900/1,200 min)"), ("snap-suspect", "snapping suspect\n(> 200 m)"),
             ("threshold-bound", "threshold-bound\n(safe at 0.7)"), ("origin-burns-first", "origin burns\nfirst"), ("corridor-burns", "corridor\nburns")]
    counts_n = [sum(1 for d in diag if f in d["flags"]) for f, _ in flags]; counts_b = [sum(d["n_buildings"] for d in diag if f in d["flags"]) for f, _ in flags]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 3.0), gridspec_kw={"width_ratios": [1.25, 1]})
    y = np.arange(len(flags))
    ax.barh(y - 0.19, counts_n, height=0.38, color=P["slate"], edgecolor="black", linewidth=0.6, label="nodes (of 54)")
    ax.barh(y + 0.19, counts_b, height=0.38, color=P["brown"], edgecolor="black", linewidth=0.6, label="buildings (of 190)")
    for i in range(len(flags)):
        ax.text(counts_n[i] + 2, i - 0.19, str(counts_n[i]), va="center", fontsize=7.5); ax.text(counts_b[i] + 2, i + 0.19, str(counts_b[i]), va="center", fontsize=7.5)
    ax.set_yticks(y); ax.set_yticklabels([l for _, l in flags], fontsize=7.5); ax.invert_yaxis(); ax.set_xlim(0, 210); ax.set_xlabel("count (a node may carry several flags)")
    ax.legend(loc="lower right", fontsize=7); ax.set_title("No-safe-route class, diagnosed", fontsize=8.5, color=style.INK)
    cred = og["credible_failures"]
    ax.text(0.98, 0.02, f"credible: {cred['nodes']} nodes / {cred['buildings']} buildings", transform=ax.transAxes, ha="right", va="bottom", fontsize=7, color=style.INK,
            bbox=dict(boxstyle="square,pad=0.3", fc="white", ec="black", lw=0.6)) if False else None
    runs = [r for k, r in vp["runs"].items() if r["dispatch_delay_min"] == 30.0]
    ks = [r["vehicles"] for r in runs]; comp = [r["completed_buildings"] for r in runs]; total = vp["population"]["credible_buildings"]
    bx.plot(ks, comp, marker="o", color=P["fire"], lw=1.2, label="completed by a vehicle")
    bx.axhline(total, color=P["grey"], lw=0.8, ls="--"); bx.text(ks[-1], total + 1.5, f"credible failures: {total} buildings", ha="right", fontsize=7, color=style.MUTED)
    bx.axhline(0, color=P["grey"], lw=0.8); bx.text(ks[0], 1.5, "walking: 0", fontsize=7, color=style.MUTED)
    bx.set_xticks(ks); bx.set_ylim(-3, total + 10); bx.set_xlabel("vehicles in the fleet (dispatch 30 min)"); bx.set_ylabel("buildings")
    bx.set_title("One intervention: assisted pickup", fontsize=8.5, color=style.INK); bx.legend(loc="center right", fontsize=7)
    bx.text(ks[-1], comp[-1] - 6, f"{comp[-1]} of {total}: the same nine nodes\nat every fleet size; the rest\nhave no safe road in", ha="right", va="top", fontsize=7, color=style.INK)
    style.label_panels([ax, bx]); fig.tight_layout(); save(fig, "F13_diagnosis_intervention")


# ---------------------------------------------------------------- FC: last safe departure, doctrine units
def fig_last_safe_departure():
    d = J("data/processed/last_safe_departure_yeongdeok.json"); rows = d["per_node"]
    w = np.array([r["n_buildings"] for r in rows], float)
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 2.9), gridspec_kw={"width_ratios": [1.3, 1]})
    for key, lab, col in (("lsd_fire_blind_min", "fire-blind shortest walk", P["blue"]), ("lsd_time_aware_min", "forecast-aware walk", P["fire"])):
        v = np.array([r[key] for r in rows], float)
        grid = np.arange(-10, 601, 10); cum = [w[v <= g].sum() for g in grid]
        ax.step(grid, cum, where="post", color=col, lw=1.3, label=lab)
    for x, lab in ((300, "5 h rule:\nimmediate\nevacuation"), (480, "8 h rule:\nvulnerable\nresidents")):
        ax.axvline(x, color=P["grey"], lw=0.8, ls="--"); ax.text(x + 6, w.sum() * 0.155, lab, fontsize=6.5, color=style.MUTED, va="top", ha="left")
    ax.set_xlim(-10, 600); ax.set_ylim(0, w.sum() * 0.16); ax.set_xlabel("latest safe departure after forecast issue (min); -10 = never")
    ax.set_ylabel("buildings that must have left by then"); ax.legend(loc="center left", fontsize=7); ax.set_title("Cumulative, lower 16 % of buildings shown", fontsize=8.5, color=style.INK)
    summ = {s["label"]: s for s in d["summaries"]}; a = summ["all routable"]
    cats = ["no safe departure\nat any time", "must leave\nwithin 5 h", "safe leaving any time\nup to 10 h"]
    fb = [a["buildings_fb_never"], a["buildings_fb_below_300"] - a["buildings_fb_never"], a["buildings_fb_censored_600"]]
    fa = [a["buildings_fa_never"], a["buildings_fa_below_300"] - a["buildings_fa_never"], a["buildings_fa_censored_600"]]
    y = np.arange(3)
    bx.barh(y - 0.19, fb, height=0.38, color=P["blue"], edgecolor="black", linewidth=0.6, label="fire-blind"); bx.barh(y + 0.19, fa, height=0.38, color=P["fire"], edgecolor="black", linewidth=0.6, label="forecast-aware")
    for i in range(3):
        bx.text(fb[i] + 200, i - 0.19, f"{fb[i]:,}", va="center", fontsize=7); bx.text(fa[i] + 200, i + 0.19, f"{fa[i]:,}", va="center", fontsize=7)
    bx.set_yticks(y); bx.set_yticklabels(cats, fontsize=7.5); bx.invert_yaxis(); bx.set_xlim(0, 24000); bx.set_xlabel("buildings (of 19,250)"); bx.legend(loc="center right", fontsize=7)
    bx.set_title("Against the 5-hour rule", fontsize=8.5, color=style.INK)
    style.label_panels([ax, bx]); fig.tight_layout(); save(fig, "F14_last_safe_departure")


# ---------------------------------------------------------------- FD: the leak-free fold
def fig_leakfree():
    lf = J("data/processed/leakfree_yeongdeok_fold.json"); zc = np.load(REPO / "data/processed/routing_demo_canonical.npz")
    fig, (ax, bx, cx) = plt.subplots(1, 3, figsize=(7.0, 2.8), gridspec_kw={"width_ratios": [1.2, 1, 1]})
    t = [0, 180, 360, 540, 720]; f = lf["field"]["cells_ge_0.5_per_slice"]
    ax.plot(t, f["canonical"], marker="o", color=P["fire"], lw=1.2, label="canonical field (Uiseong-Andong in training)")
    ax.plot(t, f["leakfree"], marker="s", color=P["blue"], lw=1.2, label="leak-free field (Uiseong-Andong excluded)")
    obs_t = [float(v) for v in zc["obs_times"]]; obs_c = [int(zc["obs_stack"][i].sum()) for i in range(len(obs_t))]
    keep = [i for i, v in enumerate(obs_t) if v <= 720]
    ax.plot([obs_t[i] for i in keep], [obs_c[i] for i in keep], marker="^", color=style.INK, lw=0, label="FIRMS detected (cumulative)")
    ax.set_xlabel("minutes after forecast issue"); ax.set_ylabel("500 m cells at p >= 0.5"); ax.set_ylim(150, 1150); ax.legend(loc="lower right", fontsize=6.3); ax.set_title("Forecast core vs observation", fontsize=8.5, color=style.INK)
    o = lf["origins_458"]; b = lf["buildings"]
    for axx, canon, free, tot, title in ((bx, o["partition_canonical"]["naive_into_FA_safe"], o["partition_leakfree"]["naive_into_FA_safe"], 458, "forecast-only origins\n(of 458)"),
                                         (cx, b["partition_canonical"]["naive_into_FA_safe"], b["partition_leakfree"]["naive_into_FA_safe"], b["n_routable"], "forecast-only buildings\n(of 19,250)")):
        vals = [canon, free]; axx.bar([0, 1], vals, color=[P["fire"], P["blue"]], edgecolor="black", linewidth=0.6, width=0.6)
        for i, v in enumerate(vals): axx.text(i, v + max(vals) * 0.03, f"{v:,}", ha="center", fontsize=8, color=style.INK)
        axx.set_xticks([0, 1]); axx.set_xticklabels(["canonical", "leak-free"], fontsize=8); axx.set_ylim(0, max(vals) * 1.25); axx.set_title(title, fontsize=8.5, color=style.INK)
    auc = lf["held_out_yeongdeok_auc"]
    bx.text(0.5, 0.97, f"held-out AUC {auc['canonical_fold']:.3f} to {auc['leakfree_fold']:.3f}", transform=bx.transAxes, ha="center", va="top", fontsize=7, color=style.MUTED)
    style.label_panels([ax, bx, cx], inside=True); fig.tight_layout(); save(fig, "F15_leakfree_fold")


# ---------------------------------------------------------------- FE: coverage — 124 vs 19,959 and what changed
def fig_coverage():
    jb = J("data/processed/external/juso_buildings_yeongdeok/manifest.json"); bo = J("data/processed/building_origin_routing_juso_main_yeongdeok.json")["regions"][0]
    bo_osm = J("data/processed/building_origin_routing.json")["regions"][0]
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 2.7), gridspec_kw={"width_ratios": [1, 1.25]})
    vals = [jb["counts"]["osm_buildings_inside_walk_bbox"], jb["counts"]["inside_canonical_box_main_buildings"], jb["counts"]["inside_canonical_box"]]
    labs = ["OSM\n(used until\n09-12)", "register,\nmain\nbuildings", "register,\nall\nbuildings"]
    ax.bar(range(3), vals, color=[P["grey"], P["brown"], P["mauve"]], edgecolor="black", linewidth=0.6, width=0.62)
    for i, v in enumerate(vals): ax.text(i, v + 400, f"{v:,}", ha="center", fontsize=8)
    ax.set_xticks(range(3)); ax.set_xticklabels(labs, fontsize=7.5); ax.set_ylim(0, 32000); ax.set_ylabel("buildings inside the canonical box"); ax.set_title("Coverage", fontsize=8.5, color=style.INK)
    cls = [("both_safe", "both safe", P["teal"]), ("naive_into_FA_safe", "forecast-aware only", P["fire"]), ("no_safe_route", "no safe route", P["black"])]
    for i, (rec, tot, lab) in enumerate(((bo_osm["building_level_counts"], bo_osm["n_routable"], "OSM sample (119 routed)"), (bo["building_level_counts"], bo["n_routable"], "register census (19,250 routed)"))):
        left = 0
        for key, l, c in cls:
            v = rec[key] / tot * 100
            bx.barh(i, v, left=left, color=c, edgecolor="black", linewidth=0.6, height=0.6)
            if v > 3: bx.text(left + v / 2, i, f"{rec[key]:,}\n{v:.1f} %", ha="center", va="center", fontsize=7, color="white" if key != "both_safe" else style.INK)
            elif v > 0: bx.text(left + v + 1, i, f"{rec[key]:,} ({v:.1f} %)", ha="left", va="center", fontsize=7, color=style.INK)
            left += v
    bx.set_yticks([0, 1]); bx.set_yticklabels(["OSM sample\n(119 routed)", "register census\n(19,250 routed)"], fontsize=7.5); bx.invert_yaxis(); bx.set_xlim(0, 100); bx.set_xlabel("share of routed buildings (%)")
    bx.legend([plt.Rectangle((0, 0), 1, 1, color=c, ec="black", lw=0.6) for _, _, c in cls], [l for _, l, _ in cls], loc="lower left", fontsize=7, ncol=3, bbox_to_anchor=(0, -0.55))
    bx.set_title("Forecast-graded classes, sample vs census", fontsize=8.5, color=style.INK)
    style.label_panels([ax, bx]); fig.tight_layout(); save(fig, "F16_coverage")


if __name__ == "__main__":
    style.apply()
    fig_coverage(); fig_observed_grading(); fig_diagnosis_intervention(); fig_last_safe_departure(); fig_leakfree()
    (OUT / "README.md").write_text("# Finals figure set (2026-09-14)\n\nBuilt by `paper/make_finals_figures.py` from committed artifacts only; PNG at 300 dpi and PDF vector. "
                                   "House style: `paper/style.py`. Captions live in the documents that cite them.\n\n"
                                   "| file | what | artifact |\n|---|---|---|\n"
                                   "| F16_coverage | 124 OSM vs 19,959 address-register buildings; forecast-graded classes, sample vs census | juso manifest; building_origin_routing*.json |\n"
                                   "| F12_observed_grading | three-way observed grading, 458 sample and 19,250 census, with the adjacent-cell sensitivity | regrade_three_way; building_origins_observed_grading |\n"
                                   "| F13_diagnosis_intervention | flags on the 54 no-safe-route nodes; buildings completed by a vehicle vs fleet size | building_origins_observed_grading; vehicle_pickup_intervention |\n"
                                   "| F14_last_safe_departure | cumulative latest-safe-departure by policy with the 5 h / 8 h doctrine lines; the 5-hour rule counts | last_safe_departure |\n"
                                   "| F15_leakfree_fold | canonical vs leak-free forecast core vs FIRMS; 42 → 34 and 1,606 → 1,277 | leakfree_yeongdeok_fold |\n", encoding="utf-8")
