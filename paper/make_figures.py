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
def F1_system(out: Path) -> bool:
    """System overview: data → forecast → time-expanded routing → decisions → delivery.
    Drawn on a fixed grid so boxes align and arrows meet box edges exactly."""
    fig, ax = plt.subplots(figsize=(7.0, 2.9))
    ax.set_axis_off(); ax.grid(False)
    ax.set_xlim(0, 100); ax.set_ylim(0, 40)
    boxes = [  # (x, y, w, h, title, sub)
        (1, 22, 18, 13, "Public inputs", "FIRMS · ERA5 · SRTM\nWorldCover · OSM"),
        (21.5, 22, 18, 13, "Spread model", "P(ignite) per cell\nleave-one-fire-out"),
        (42, 22, 18, 13, "Hazard field", "time-sliced probability\n0 to 720 min"),
        (62.5, 22, 18, 13, "Routing", "time-expanded walk-out\nroutes avoid future fire"),
        (83, 22, 16, 13, "Decisions", "A4 sheet · broadcast\nscript · SMS draft"),
        (21.5, 3, 18, 11, "Rescue ingress", "which homes a crew can\nstill reach, until when"),
        (42, 3, 38.5, 11, "Evidence registry", "every reported number re-derived from its artifact\n(make verify); withdrawn claims kept in the tree"),
    ]
    for x, y, w, h, t, s in boxes:
        ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2",
                                             facecolor="white", edgecolor=style.INK, linewidth=0.9))
        ax.text(x + w / 2, y + h - 3.2, t, ha="center", va="center", fontsize=8, weight="bold", color=style.INK)
        ax.text(x + w / 2, y + h / 2 - 2.4, s, ha="center", va="center", fontsize=6.5, color=style.MUTED, linespacing=1.25)

    def arrow(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=style.INK, lw=0.9, shrinkA=0, shrinkB=0, mutation_scale=9))
    for xa, xb in ((19, 21.5), (39.5, 42), (60, 62.5), (80.5, 83)):
        arrow(xa, 28.5, xb, 28.5)
    arrow(51, 22, 39.5, 14)      # hazard field feeds rescue ingress
    arrow(39.5, 8.5, 42, 8.5)    # rescue ingress → registry
    arrow(71.5, 22, 61.25, 14)   # routing → registry
    ax.text(50, 0.4, "Solid arrows: data flow for one fire. The registry sits under every reported number.",
            ha="center", va="bottom", fontsize=7, color=style.MUTED)
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


FIGURES = [F1_system, F2_lofo_auc, F3_regions]


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
