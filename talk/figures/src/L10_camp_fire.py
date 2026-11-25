"""Legible F10: Camp Fire, blocked roads flagged before the crew report, how much earlier, hits and false alarms
(slot 1212 x 560; D48). Numbers from F10_camp_fire.read and paradise_point (research/kcf-camp), unchanged. The
false-alarm bar is grey #6B6B6B (was ochre); legend and labels shortened.
"""
import math

import numpy as np

import F10_camp_fire as F
import legible as G
import style as S
from prov import Ledger


def main():
    L = Ledger("L10", "Legible Camp Fire figure")
    closed, caught, early, med, hits, fc, npass = F.read(L)
    t = F.T
    plat, plon = F.paradise_point(L)
    fig = G.figure("F10_camp_fire")
    lat0, lon0 = closed["lat"].mean(), closed["lon"].mean()
    x, y = F.project(closed["lat"].to_numpy(), closed["lon"].to_numpy(), lat0, lon0)
    hit = (closed["state_MR_strict"] == "HIT").to_numpy()
    # (a) map
    mx0, mx1 = x.min() - 0.8, x.max() + 0.8
    my0, my1 = y.min() - 0.8, y.max() + 1.0
    mh = 3.05
    mw = mh * (mx1 - mx0) / (my1 - my0)
    axm = G.ax_in(fig, 0.3, 0.72, mw, mh)
    axm.set_xlim(mx0, mx1)
    axm.set_ylim(my0, my1)
    axm.set_aspect("equal", adjustable="box")
    G.strip(axm)
    h1 = axm.scatter(x[hit], y[hit], s=60, marker="o", color=S.BLUE, linewidths=0, zorder=4)
    h2 = axm.scatter(x[~hit], y[~hit], s=75, marker="s", facecolors=S.PAPER, edgecolors=S.INK, linewidths=1.6, zorder=3)
    h1.set_gid("bg:hits")
    h2.set_gid("bg:misses")
    px, py = F.project(plat, plon, lat0, lon0)
    axm.scatter([px], [py], s=200, marker="*", color=S.INK, linewidths=0, zorder=5).set_gid("bg:town")
    axm.annotate("Paradise", (px, py), xytext=(-10, 12), textcoords="offset points", ha="right", va="bottom", zorder=6)
    fx_, fy_ = (mx1 - mx0) / 100, (my1 - my0) / 100
    sb = 5.0
    bx, by = mx1 - sb - 5 * fx_, my0 + 9 * fy_
    axm.plot([bx, bx + sb], [by, by], color=S.INK, lw=3, solid_capstyle="butt")[0].set_gid("bg:scale")
    axm.text(bx - 2 * fx_, by, "5 km", ha="right", va="center")
    axm.annotate("", xy=(mx1 - 5 * fx_, my1 - 4 * fy_), xytext=(mx1 - 5 * fx_, my1 - 16 * fy_),
                 arrowprops=dict(arrowstyle="-|>,head_length=0.6,head_width=0.3", color=S.INK, lw=1.6))
    axm.text(mx1 - 8 * fx_, my1 - 10 * fy_, "N", ha="right", va="center")
    W, H = fig._wh
    leg = fig.legend([h1, h2], [f"flagged in time ({hits})", f"not in time ({len(closed) - hits})"], loc="upper left",
                     bbox_to_anchor=(0.3 / W, 1 - (0.72 + mh + 0.22) / H), frameon=False, handletextpad=0.4,
                     labelspacing=0.55, borderaxespad=0, borderpad=0, markerscale=1.2)
    for hnd in leg.legend_handles:
        hnd.set_gid("bg:legend handle")
    G.text_in(fig, 0.3, 0.3, "Blocked-road reports")
    # (b) hours earlier
    xb0 = 5.3
    ax = G.ax_in(fig, xb0, 0.72, 2.15, 3.95)
    hrs = early.to_numpy() / 60.0
    rng = np.random.RandomState(5)
    ax.scatter(rng.uniform(-0.3, 0.3, len(hrs)), hrs, s=30, marker="o", facecolors=S.PAPER, edgecolors=S.BLUE,
               linewidths=1.1).set_gid("bg:reports")
    medh = med / 60.0
    floor_h = math.floor(medh * 10) / 10
    ax.plot([-0.45, 0.45], [medh, medh], color=S.INK, lw=2.5)[0].set_gid("bg:median")
    ax.annotate(f"half\n≥ {floor_h:.1f} h", (0.45, medh), xytext=(8, 6), textcoords="offset points", va="bottom",
                ha="left", linespacing=1.1)
    ax.axhline(0, color=S.INK, lw=1.0, ls=(0, (3, 2))).set_gid("bg:zero")
    ax.text(2.25 - 0.2, -0.9, "crew report", ha="right", va="top")
    ax.set_xlim(-0.55, 2.25)
    topv = float(np.ceil(hrs.max() / 4) * 4)
    ax.set_ylim(-5.0, topv + 0.6)
    ax.set_yticks(np.arange(0, topv + 0.1, 4))
    ax.set_yticklabels([f"{v:g}" for v in np.arange(0, topv + 0.1, 4)])
    ax.set_xticks([])
    ax.set_ylabel("Hours earlier")
    G.text_in(fig, xb0 - 0.6, 0.3, "How much earlier")
    # (c) hits and false alarms: horizontal bars, counts inside
    xc0 = 9.55
    axc = G.ax_in(fig, xc0, 0.95, 2.35, 2.75)
    vals = [hits / len(closed) * 100, fc / npass * 100]
    cis = [t["hit_ci95"], t["false_closure_ci95"]]
    for i_, (v, ci, col, cnt) in enumerate(zip(vals, cis, [S.BLUE, S.GREY],
                                                [f"{hits} of {len(closed)}", f"{fc} of {npass}"])):
        b = axc.barh(i_, v, height=0.62, color=col, edgecolor=S.INK, linewidth=0.8)
        b.patches[0].set_gid("box:bar")
        axc.errorbar(v, i_, xerr=[[v - ci[0] * 100], [ci[1] * 100 - v]], fmt="none", ecolor=S.INK, elinewidth=1.2,
                     capsize=5)
        axc.text(4, i_, cnt, ha="left", va="center", color=S.PAPER)
    axc.set_ylim(1.6, -0.6)
    axc.set_xlim(0, 108)
    axc.set_xticks([0, 50, 100])
    axc.set_xticklabels(["0", "50", "100"])
    axc.set_yticks([0, 1])
    axc.set_yticklabels(["blocked", "passable"])
    axc.tick_params(axis="y", length=0)
    axc.set_ylabel("What crews saw")
    axc.set_xlabel("% flagged")
    G.text_in(fig, 8.3, 0.3, "Hits and false alarms")
    L.save()
    G.save(fig, "F10_camp_fire")


if __name__ == "__main__":
    main()
