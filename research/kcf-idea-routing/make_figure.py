"""figures/margin_field.png: (a) the two-route example of METHOD.md Proposition 3, computed by the code; (b) leave-by
time against the margin for recorded origins (results/real/*.json, cert rule, keep variant); (c) measured time for K
margins, existing pass against the margin pass (results/bench.json round 1, results/bench2.json round 2).

    MPLCONFIGDIR=$TMPDIR python3 research/kcf-idea-routing/make_figure.py
"""
from __future__ import annotations

import glob
import json
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "kcf-theorem"))
import randgraphs  # noqa: E402
from margin_field import field as mf, pl  # noqa: E402

BLUE, ORANGE, AQUA, INK, MUTED, SURFACE = "#2a78d6", "#eb6834", "#1baf7a", "#0b0b0b", "#52514e", "#fcfcfb"


def style(ax, title):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=10.5, color=INK)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c9c8c2")
    ax.tick_params(colors=MUTED, labelsize=8.5)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.7)
    ax.set_axisbelow(True)


def main():
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), facecolor=SURFACE)

    # (a) two-route example
    ax = axes[0]
    chk = {"H": 12, "n_nodes": 2, "edges": [[0, 1, 1], [0, 1, 1]], "waitable": [], "forbidden": [],
           "B": {0: [[6, 40]], 1: [[0, 5]]}, "W": {}, "A": {0: [[0, 12]], 1: [[0, 12]]}, "IB": {}, "AN": {}}
    fld = mf.margin_field(randgraphs.to_instance(chk), 8, erode_accept=True)
    d = pl.to_dense(mf.issue_margin(fld, 0), 0, 11)
    edge = [min(8, 12 - t - 1) for t in range(12)]      # Proposition 3: distance to the end of the window - 1
    assert all(x <= e for x, e in zip(d, edge)), (d, edge)
    ax.step(range(12), edge, where="mid", color=MUTED, linewidth=1.5, linestyle=(0, (4, 3)),
            label="read off the window: seconds to its end, minus 1")
    ax.step(range(12), d, where="mid", color=BLUE, linewidth=2.2, label="margin field (exact)")
    ax.plot(range(12), d, "o", color=BLUE, markersize=5)
    ax.annotate("road 1 closes at 6,\nroad 2 opens at 6:\nmargin 0", xy=(5.5, 0), xytext=(4.0, 3.6), fontsize=8.5,
                color=INK, ha="center", arrowprops={"arrowstyle": "-", "color": MUTED, "linewidth": 0.8})
    ax.set_xlabel("departure second (all of 0–11 are feasible)", fontsize=9, color=MUTED)
    ax.set_ylabel("largest margin that keeps it feasible (s)", fontsize=9, color=MUTED)
    ax.legend(frameon=False, fontsize=8.5, loc="upper center")
    ax.set_ylim(-0.3, 10.5)
    style(ax, "(a) A wide window is not a safe one")

    # (b) leave-by against margin, recorded origins
    ax = axes[1]
    curves = []
    for f in sorted(glob.glob(str(HERE / "results/real/*.json"))):
        for row in json.loads(Path(f).read_text()):
            for o, per in row.get("leave_by_curves_cert_keep", {}).items():
                for dn, cur in per.items():
                    if cur and cur[0][1] is not None:
                        curves.append((row["cache"], o, dn, cur))
    def expand(cur):
        xs, ys = [], []
        for i, (m, L) in enumerate(cur):
            end = cur[i + 1][0] - 1 if i + 1 < len(cur) else 600
            if L is None:
                break
            xs += [m, end]
            ys += [L, L if i + 1 == len(cur) else None]
        return xs, ys

    def dense(cur):
        out, j = [], 0
        for m in range(601):
            while j + 1 < len(cur) and cur[j + 1][0] <= m:
                j += 1
            out.append(cur[j][1])
        return out

    ds = [dense(c[3]) for c in curves]
    drop = [(d0[0] - d0[600]) if d0[600] is not None else None for d0 in ds]
    lost = sum(x is None for x in drop)
    flat = sum(x == 0 for x in drop)
    full = sum(x == 600 for x in drop)
    for d0 in ds[:: max(1, len(ds) // 400)]:
        ax.plot(range(601), [x / 60 if x is not None else None for x in d0], color=BLUE, linewidth=0.6, alpha=0.18)
    part = [d0 for d0, x in zip(ds, drop) if x not in (None, 0, 600)]
    if part:
        ex = max(part, key=lambda d0: len(set(d0)))
        ax.plot(range(601), [x / 60 for x in ex], color=ORANGE, linewidth=2.2,
                label="one place whose route changes with the margin")
        ax.legend(frameon=False, fontsize=8.5, loc="lower left")
    ax.set_xlabel("time margin on every closure (s)", fontsize=9, color=MUTED)
    ax.set_ylabel("leave-by time (minutes after issue)", fontsize=9, color=MUTED)
    style(ax, "(b) Leave-by time against the margin, %s place–shelter pairs" % format(len(ds), ","))
    ax.set_ylim(0, 74)
    ax.text(0.99, 0.99, "%s unchanged at 600 s  ·  %s lose the full 600 s\n%s lose part  ·  %s lose the window" % (
        format(flat, ","), format(full, ","), format(len(ds) - flat - full - lost, ","), format(lost, ",")),
        transform=ax.transAxes, ha="right", va="top", fontsize=8.5, color=MUTED)

    # (c) speed ratio per cache, one field and K margins
    ax = axes[2]
    b1 = json.loads((HERE / "results/bench.json").read_text())
    b2 = json.loads((HERE / "results/bench2.json").read_text())
    Ks = ["1", "2", "4", "8", "16"]
    xs = list(range(6))
    ax.axhline(1, color=INK, linewidth=1)
    seen = set()
    for name, c in sorted(b1["caches"].items()):   # round 1: before the fast path
        col = BLUE if "uiseong" in name else ORANGE
        ys = [statistics.median(s["T1"]["ratio"] for s in c["specs"])] + [
            statistics.median(s["T2"][K]["ratio"] for s in c["specs"]) for K in Ks]
        ax.plot(xs, ys, "--", color=col, linewidth=1, alpha=0.55,
                label=None if "r1" in seen else "round 1 (before the fast path)")
        seen.add("r1")
    for name, c in sorted(b2["caches"].items()):   # round 2
        reg = "Uiseong–Andong" if "uiseong" in name else "Yeongdeok"
        col = BLUE if "uiseong" in name else ORANGE
        ys = [statistics.median(s["T1"]["ratio_existing_over_new"] for s in c["specs"])] + [
            statistics.median(s["T2"][K]["ratio_existing_over_new"] for s in c["specs"]) for K in Ks]
        ax.plot(xs, ys, "-o", color=col, linewidth=2, markersize=5,
                label=None if reg in seen else reg + (" (3 caches, 43,826 edges)" if reg[0] == "U"
                                                      else " (3 caches, 111,924 edges)"))
        seen.add(reg)
    ax.set_yscale("log")
    ax.set_yticks([0.5, 1, 2, 4, 8, 16])
    ax.set_yticklabels(["0.5×", "1×", "2×", "4×", "8×", "16×"])
    ax.minorticks_off()
    ax.set_xticks(xs)
    ax.set_xticklabels(["one field\n(margin 0)", "1", "2", "4", "8", "16"])
    ax.set_xlabel("number of margins wanted", fontsize=9, color=MUTED)
    ax.set_ylabel("existing time / new time (median of 6 shelters)", fontsize=9, color=MUTED)
    ax.text(5.1, 1.04, "faster above", fontsize=8.5, color=MUTED, ha="right", va="bottom")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    style(ax, "(c) Speed against the existing pass")

    fig.tight_layout()
    (HERE / "figures").mkdir(exist_ok=True)
    fig.savefig(HERE / "figures" / "margin_field.png", dpi=170, facecolor=SURFACE)
    print("wrote figures/margin_field.png;", len(ds), "curves; flat", flat, "full", full, "lost", lost)


if __name__ == "__main__":
    main()
