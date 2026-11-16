"""Three figures from numbers.json (+ route.json): miss vs target, zone size by class, pixel vs route.

    python figures.py --numbers numbers.json --route route.json --out fig/
"""
import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLUE, ORANGE, INK, INK2, GRID, SURF = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF})


def fig_miss(num, out):
    fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharey=True)
    for ax, fset, title in zip(axes, ("all28", "noComplex"), ("All 28 fires", "Without 'Complex' fires (n=17)")):
        ax.plot([0, 0.35], [0, 0.35], color=INK2, lw=1, ls="--", zorder=1)
        ax.text(0.33, 0.30, "miss = target", color=INK2, fontsize=8, ha="right")
        for h, col, dx in ((5, BLUE, -0.004), (8, ORANGE, 0.004)):
            rows = [r for r in num["miss_vs_target"] if r["fire_set"] == fset and r["h"] == h]
            x = [r["alpha"] + dx for r in rows]
            y = [r["lofo_miss"] for r in rows]
            lo = [r["lofo_miss"] - r["ci95"][0] for r in rows]
            hi = [r["ci95"][1] - r["lofo_miss"] for r in rows]
            ax.errorbar(x, y, yerr=[lo, hi], color=col, lw=2, marker="o", ms=6, capsize=0, elinewidth=1,
                        label=f"{h} h", mec=SURF, mew=1.5)
        ax.set_title(title, fontsize=10, color=INK, loc="left")
        ax.set_xlabel("miss target α")
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_xlim(0, 0.35)
    axes[0].set_ylabel("leave-one-fire-out miss rate\n(fire-weighted, 95% Clopper–Pearson)")
    axes[0].legend(frameon=False, loc="upper left")
    fig.suptitle("Fig 1. Miss rate against target, class 'all hours' (GOFER, MEASURED)", x=0.01, ha="left",
                 fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(out / "fig1_miss_vs_target.png", dpi=150)


def fig_zone(num, out):
    classes = ["all", "quiet", "slow", "running", "gust<10", "gust10-20", "gust>=20"]
    rows = {(r["h"], r["cls"]): r for r in num["table"] if r["fire_set"] == "all28" and abs(r["alpha"] - 0.1) < 1e-9}
    fig, ax = plt.subplots(figsize=(8, 4.2))
    w = 0.38
    ymax = 0
    for k, (h, col) in enumerate(((5, BLUE), (8, ORANGE))):
        for i, c in enumerate(classes):
            r = rows[(h, c)]
            v = r["R_km"]
            x = i + (k - 0.5) * w
            if v is None or not math.isfinite(v):
                ax.text(x, 0.3, "n too\nsmall", ha="center", fontsize=7, color=INK2)
                continue
            ax.bar(x, v, w - 0.04, color=col, label=f"{h} h" if i == 0 else None, edgecolor=SURF, linewidth=1)
            ax.text(x, v + 0.3, f"{v:.1f}", ha="center", fontsize=8, color=INK)
            ymax = max(ymax, v)
    labels = [f"{c}\n(n={rows[(5, c)]['n_fires']}/{rows[(8, c)]['n_fires']})" for c in classes]
    ax.set_xticks(range(len(classes)), labels, fontsize=8)
    ax.set_ylabel("R at 90% (km beyond known perimeter)")
    ax.set_ylim(0, ymax * 1.15 + 1)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False)
    ax.set_title("Fig 2. Zone size by class, α = 0.10, all 28 fires (n = fires with hours in class, 5 h / 8 h)",
                 fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(out / "fig2_zone_by_class.png", dpi=150)


def fig_route(route, out):
    s = route["summary"]
    AQUA, YELLOW = "#1baf7a", "#eda100"
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    groups = [("pixel90", "Zone calibrated per pixel (90%)"), ("issue90", "Zone calibrated per issue time (90%)")]
    series = (("pixel_miss_fire_weighted", BLUE, "spread pixels outside the zone"),
              ("route_fail_fire_weighted", ORANGE, "random detours crossing a missed pixel (all spread hours)"),
              ("spread_hours_with_any_missed_pixel_fire_weighted", AQUA, "spread hours with at least one missed pixel"),
              ("route_fail_in_hours_with_a_miss_fire_weighted", YELLOW, "detours crossing a missed pixel, in those hours"))
    w = 0.2
    top = max(s[g][k] for g, _ in groups for k, _, _ in series)
    for k, (key, col, lab) in enumerate(series):
        for i, (g, _) in enumerate(groups):
            v = s[g][key]
            x = i + (k - 1.5) * w
            ax.bar(x, v, w - 0.03, color=col, label=lab if i == 0 else None, edgecolor=SURF)
            ax.text(x, v + top * 0.015, f"{100 * v:.0f}%", ha="center", fontsize=8, color=INK)
    ax.set_xticks(range(2), [f"{t}\n(n={s[g]['n_fires']} fires, {s[g]['routes']} routes)" for g, t in groups], fontsize=8)
    ax.set_ylabel("rate (fire-weighted, leave-one-fire-out)")
    ax.set_ylim(0, top * 1.12)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=8)
    ax.set_title("Fig 3. Pixel miss vs route failure, 5 h, held-out GOFER fires (grid roads ASSUMED)",
                 fontsize=10, color=INK, loc="left")
    fig.tight_layout()
    fig.savefig(out / "fig3_pixel_vs_route.png", dpi=150)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--numbers", required=True)
    ap.add_argument("--route")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(exist_ok=True)
    num = json.loads(Path(a.numbers).read_text())
    fig_miss(num, out)
    fig_zone(num, out)
    if a.route and Path(a.route).exists():
        fig_route(json.loads(Path(a.route).read_text()), out)


if __name__ == "__main__":
    main()
