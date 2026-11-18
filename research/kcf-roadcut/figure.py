"""The one figure: gap = T_village - T_road per place, primary configuration (R, MEASURED, 8 h), every issue hour.

Model output on reconstructed inputs. Not what happened to people.

Usage: python3 figure.py R_ROWS.json OUT.png [ARM] [HORIZON]
"""
from __future__ import annotations

import json, statistics, sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D

# reference palette, light mode (dataviz skill references/palette.md; first three slots validate all-pairs)
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
COL = {"ROAD_CELL": "#2a78d6", "ORIGIN_CELL": "#eb6834", "SHELTER_CELL": "#1baf7a", "UNCLEAR": INK2, "NO_WINDOW": INK2}
LAB = {"ROAD_CELL": "last window ends on a road cell (road cut before the village is reached)",
       "ORIGIN_CELL": "last window ends on the village's own cell",
       "SHELTER_CELL": "last window ends at the shelter (dwell)",
       "NO_WINDOW": "no window at the issue hour (lower bound: T_village - issue)",
       "UNCLEAR": "binding unclear (slack > 60 s)"}


def korean_font():
    for f in font_manager.findSystemFonts():
        if any(k in f for k in ("NanumGothic", "NotoSansCJK", "NotoSansKR", "UnDotum", "Noto Sans CJK")):
            font_manager.fontManager.addfont(f)
            return font_manager.FontProperties(fname=f).get_name()
    return None


def main(rows_path, out, arm="MEASURED", hz="8h"):
    fam = korean_font()
    if fam:
        plt.rcParams["font.family"] = [fam, "DejaVu Sans"]
    rows = [x for x in json.loads(Path(rows_path).read_text())["rows"] if x["arm"] == arm and x["horizon"] == hz]
    by = defaultdict(list)
    for x in rows:
        by[x["place_id"]].append(x)
    pts = {}
    for p, xs in by.items():
        v = []
        for x in xs:
            if x["state"] == "CUT" and x["gap_s"] is not None:
                v.append((x["gap_s"] / 60, x["binding"], False))
            elif x["state"] == "CUT" and x["gap_lower_bound_s"] is not None:
                v.append((x["gap_lower_bound_s"] / 60, x["binding"], True))
            elif x["state"] == "NO_WINDOW":
                v.append((max(x["gap_lower_bound_s"], 1) / 60, "NO_WINDOW", True))
        if v:
            pts[p] = (xs[0]["name"] or xs[0]["category"], xs[0]["sigungu"], v)
    order = sorted(pts, key=lambda p: statistics.median(g for g, _, _ in pts[p][2]))
    n_other = len(by) - len(order)
    h = max(4.0, 0.14 * len(order) + 2.2)
    fig, ax = plt.subplots(figsize=(9.5, h), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    seen = set()
    for i, p in enumerate(order):
        for g, b, bound in pts[p][2]:
            g = max(g, 0.05)
            ax.scatter([g], [i], s=26 if not bound else 30, marker="o" if not bound else ">",
                       facecolors=COL[b] if not bound else "none", edgecolors=COL[b], linewidths=1.2 if bound else 0.8,
                       zorder=3)
            seen.add(b)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([f"{pts[p][0]} ({pts[p][1]})" for p in order], fontsize=6.5, color=INK2)
    ax.set_xscale("log")
    ax.set_xlim(0.05, 600)
    ax.set_xticks([0.1, 1, 5, 15, 60, 120, 300, 480])
    ax.set_xticklabels(["0.1", "1", "5", "15", "60", "120", "300", "480"], color=INK2, fontsize=8)
    ax.axvline(5, color=INK2, lw=0.8, ls=(0, (3, 3)), zorder=1)
    ax.text(5.3, len(order) - 0.3, "5 min", color=INK2, fontsize=7, va="top")
    ax.grid(axis="x", color=GRID, lw=0.6, zorder=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", length=0)
    ax.set_ylim(-0.8, len(order) - 0.2)
    ax.set_xlabel("gap = T_village − T_road (minutes, log scale)", color=INK, fontsize=9)
    hd = [Line2D([], [], marker="o", ls="", color=COL[k], markersize=6, label=LAB[k]) for k in
          ("ROAD_CELL", "ORIGIN_CELL", "SHELTER_CELL", "UNCLEAR") if k in seen]
    hd += [Line2D([], [], marker=">", ls="", markerfacecolor="none", markeredgecolor=INK2, markersize=6,
                  label="open ▷ = lower bound (village not reached within the horizon, or no window)")]
    if "NO_WINDOW" in seen:
        hd += [Line2D([], [], marker=">", ls="", markerfacecolor="none", markeredgecolor=COL["NO_WINDOW"], markersize=6,
                      label=LAB["NO_WINDOW"])]
    ax.legend(handles=hd, loc="upper left", bbox_to_anchor=(0, -0.9 / h * 2.2 - 0.02), frameon=False, fontsize=7.5,
              labelcolor=INK)
    title = f"How much earlier the last road is cut than the village is reached — {arm}, {hz} horizon"
    sub = (f"kcf-replay, 25 Mar 2025 12:00–24:00 KST issues; one dot per place and issue hour; {len(order)} places "
           f"shown (sorted by median), {n_other} with no cut window in any hour not shown.\n"
           "Model output on reconstructed inputs. Not what happened to people.")
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, color=INK, y=1 - 0.25 / h)
    fig.text(0.01, 1 - 0.62 / h, sub, ha="left", va="top", fontsize=7.5, color=INK2)
    fig.subplots_adjust(left=0.24, right=0.98, top=1 - 1.15 / h, bottom=1.55 / h)
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    print(out, len(order), n_other, fam)


if __name__ == "__main__":
    main(*sys.argv[1:])
