"""Legible F09: search per village against one backward pass, six forecast hours and the total (slot 1100 x 560; D48).

Numbers from F09_speed.read_data and update_interval (research/kcf-bench, host B), unchanged. Layout only: the region
moves into each row's label, the per-row check counts and the region place counts are left out, the legend and the
hourly line share one row, ratios stay at the end of each pair.
"""
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import legible as G
import style as S
from F09_speed import TICK_LABELS, TICKS, X0, read_data, update_interval
from prov import Ledger


def main():
    L = Ledger("L09", "Legible speed chart")
    rows, tot, dis, ncases = read_data(L)
    hourly = update_interval(L)
    fig = G.figure("F09_speed")
    ax = G.ax_in(fig, 3.75, 0.7, 5.95, 3.88)
    ax.set_xscale("log")
    ax.set_xlim(8, 2e6)
    for v in TICKS:
        ax.axvline(v, color=S.tint(S.GREY, 0.18), lw=0.8, zorder=0).set_gid("bg:grid")
    ys, labels, y, prev = [], [], 0.0, None
    for r in rows:
        y += 1.0 if prev in (None, r["place"]) else 1.25
        prev = r["place"]
        ys.append(y)
        labels.append(f"{r['place']}, {r['when'].replace(' KST', '')}")
    ys.append(y + 1.25)
    labels.append("all six hours")
    bh = 0.36
    for y0, r in zip(ys, rows + [tot]):
        ax.barh(y0 - bh / 2, r["old"] - X0, left=X0, height=bh, facecolor=S.tint(S.GREY, 0.3), edgecolor=S.INK,
                hatch="///", linewidth=0.8)
        ax.barh(y0 + bh / 2, r["new"] - X0, left=X0, height=bh, facecolor=S.BLUE, edgecolor=S.INK, linewidth=0.8)
        for v, lo, hi, dy in ((r["old"], r["old_lo"], r["old_hi"], -bh / 2), (r["new"], r["new_lo"], r["new_hi"], bh / 2)):
            ax.errorbar(v, y0 + dy, xerr=[[v - lo], [hi - v]], fmt="none", ecolor=S.INK, elinewidth=1.2, capsize=3)
        ax.annotate(f"{r['ratio']:.0f}×", (max(r["old_hi"], r["new_hi"]), y0), xytext=(9, 0), textcoords="offset points",
                    va="center", ha="left")
    ax.axvline(hourly, color=S.INK, lw=1.8, ls=(0, (5, 3)), zorder=4).set_gid("bg:hourly")
    ax.set_ylim(ys[-1] + 0.6, 0.45)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels)
    ax.tick_params(axis="y", length=0)
    ax.set_xticks(TICKS)
    ax.set_xticklabels(TICK_LABELS)
    ax.minorticks_off()
    ax.set_xlabel("Time to check every village's routes", labelpad=9)
    W, H = fig._wh
    hs = [Patch(facecolor=S.tint(S.GREY, 0.3), edgecolor=S.INK, hatch="///"), Patch(facecolor=S.BLUE, edgecolor=S.INK),
          Line2D([0], [0], color=S.INK, lw=1.8, ls=(0, (5, 3)))]
    leg = fig.legend(hs, ["search per village", "one backward pass", "hourly update"], loc="center",
                     bbox_to_anchor=(5.5 / W, 1 - 0.33 / H), ncol=3, frameon=False, columnspacing=1.4,
                     handlelength=1.5, handletextpad=0.5, borderaxespad=0)
    for hnd in leg.legend_handles:
        hnd.set_gid("bg:legend handle")
    L.save()
    G.save(fig, "F09_speed", notes=[f"{dis} disagreements in {ncases:,} checks (not printed)"])


if __name__ == "__main__":
    main()
