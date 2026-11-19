#!/usr/bin/env python3
"""The one figure: lead time per run fire-day, gust rule G and wind-aloft rule A-cal (PROTOCOL.md section 7).

    python3 figure.py --numbers numbers.json --out fig/lead_time.png
"""
import argparse
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e0"
COL = {"G": "#2a78d6", "A-cal": "#eb6834"}          # categorical slots 1 and 2 (validated pair)
LABEL = {"G": "G: forecast gust ≥ 20 m/s, persisting", "A-cal": "A-cal: forecast 850 hPa wind > 15.2 m/s"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--numbers", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    n = json.load(open(a.numbers))
    days = {r: {(d["fire"], d["kst_day"]): d for d in n["fire_set"][r]["fire_days"] if d["run_hours"] > 0} for r in COL}
    keys = sorted(days["G"])
    fig, ax = plt.subplots(figsize=(9.6, 0.6 * len(keys) + 2.3), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    h = 0.24
    for i, k in enumerate(keys):
        y = len(keys) - 1 - i
        for j, r in enumerate(("G", "A-cal")):
            d = days[r][k]
            yy = y + (0.17 if j == 0 else -0.17)
            if d["warned"]:
                L = d["lead_h"]
                w = max(L, 0.35)                     # a lead of 0 h still shows as a mark at the run hour
                ax.add_patch(FancyBboxPatch((-w, yy - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.09",
                                            mutation_aspect=1.0, fc=COL[r], ec="none"))
                ax.text(-w - 0.35, yy, f"{L} h" + (" (cap)" if L == 24 else ""), ha="right", va="center", fontsize=8, color=INK)
            else:
                ax.plot([0], [yy], marker="x", ms=6, mew=1.6, color=COL[r])
                ax.text(-0.7, yy, "not firing at the run hour", ha="right", va="center", fontsize=8, color=INK2)
        d = days["G"][k]
        name = d["name"] + ("" if k != ("KFS_01", "2025-03-25") else "")
        ax.text(-39.6, y, f"{name}  {k[1]}\nfirst run hour {d['first_run_kst_hour']:02d} KST", ha="left", va="center",
                fontsize=8.5, color=INK, linespacing=1.35)
    ax.axvline(0, color=INK2, lw=1)
    for x in (-24, -18, -12, -6):
        ax.axvline(x, color=GRID, lw=1, zorder=0)
    ax.set_xlim(-40, 1.2)
    ax.set_ylim(-0.7, len(keys) - 0.3)
    ax.set_xticks([-24, -18, -12, -6, 0])
    ax.set_xticklabels(["24", "18", "12", "6", "0"], fontsize=8.5, color=INK2)
    ax.set_xlabel("hours the rule had been firing without a break before the first run hour of the day (capped at 24 h)",
                  fontsize=8.5, color=INK2, x=0.62)
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    handles = [plt.Rectangle((0, 0), 1, 1, fc=COL[r], ec="none") for r in COL]
    ax.legend(handles, [LABEL[r] for r in COL], loc="lower left", bbox_to_anchor=(0.0, 1.005), ncol=2, frameon=False,
              fontsize=8.5, handlelength=1.2, borderaxespad=0)
    g, ac = n["fire_set"]["G"]["full"], n["fire_set"]["A-cal"]["full"]
    fig.suptitle("Lead time before the first run hour, per run fire-day (%d fire-days, %d fires)"
                 % (g["run_fire_days"], g["fires_with_run"]), x=0.012, y=0.985, ha="left", fontsize=11, color=INK, weight="bold")
    b = n["burden"]
    fig.text(0.012, 0.012,
             "Run hour: an issue hour whose 5 h reach is above 3.75 km. Forecasts: GFS as issued, assumed available 5 h after the cycle.\n"
             "Lead counts hours before ignition, at the fire's first position. x: the rule was not firing at the first run hour.\n"
             "Cost in the burden set (seasons %s, ten points): G fires on %.1f days per point and season, A-cal on %.1f.\n"
             "Counts only. 25 March 2025 was known to be flagged by the 850 hPa wind before the protocol was written."
             % ("-".join(str(x) for x in (b["G"]["full_seasons"][0], b["G"]["full_seasons"][-1])),
                b["G"]["alarm_days_per_point_season"]["mean"], b["A-cal"]["alarm_days_per_point_season"]["mean"]),
             fontsize=7.5, color=INK2, ha="left", va="bottom", linespacing=1.45)
    fig.subplots_adjust(left=0.012, right=0.988, top=0.9, bottom=0.215)
    fig.savefig(a.out, facecolor=SURFACE)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
