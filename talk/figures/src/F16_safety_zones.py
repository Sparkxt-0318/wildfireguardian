"""F16 safety zones (slide 7, right half).

(a) Geometry: a flame of height H, a receiver at distance d, the published rule d = 4H (Butler and Cohen 1998) and the
    7 kW/m2 threshold. (b) Distribution of the computed safe separation distance d*(7 kW/m2) over every burned cell of
    the four reconstructed Korean fires (baseline fuel), with a line at one 375 m grid cell.
Sources: research/kcf-radiation/data/fires/cells_KFS_*.csv.gz (column dstar_7), data/fires/fires_summary.json,
data/panels/summary.json (replay front), data/c1_butler_cohen.json.
"""
import gzip
import io

import matplotlib.patches as mp
import numpy as np
import pandas as pd

import style as S
from figkit import add_caption, grid, save
from prov import Ledger, git_show

R = "research/kcf-radiation"
FIRES = ["KFS_01", "KFS_02", "KFS_05", "KFS_11"]


def read(L):
    fs = L.json(f"{R}/data/fires/fires_summary.json")
    vals, n = [], {}
    for k in FIRES:
        f = f"{R}/data/fires/cells_{k}.csv.gz"
        df = pd.read_csv(io.BytesIO(gzip.decompress(git_show(f))))
        vals.append(df["dstar_7"].to_numpy())
        n[k] = len(df)
        L.add(f"{fs[k]['name']}: burned cells, baseline d*(7) per cell", len(df), file=f, field="column dstar_7 (m)")
    d = np.concatenate(vals)
    below = int((d < 375).sum())
    L.add("Burned cells with d*(7) below 375 m (baseline fuel)", below, shown=f"{below:,} of {len(d):,}",
          file=f"{R}/data/fires/cells_KFS_*.csv.gz", field="count of dstar_7 < 375", expected="all 13,125")
    L.add("Largest d*(7), baseline fuel", float(d.max()), unit="m", shown=f"{d.max():.0f} m",
          file=f"{R}/data/fires/cells_KFS_*.csv.gz", field="max dstar_7")
    mx = max((fs[k][lv]["dstar_7_m_p50_90_99_max"][3], fs[k]["name"], lv) for k in FIRES
             for lv in ("baseline", "fuel_low", "fuel_high"))
    shares = [fs[k][lv]["share_dstar_7_below_375m"] for k in FIRES for lv in ("baseline", "fuel_low", "fuel_high")]
    L.add("Largest d*(7) over every fuel level", mx[0], unit="m", shown=f"{mx[0]:.0f} m ({mx[1]}, {mx[2]})",
          file=f"{R}/data/fires/fires_summary.json", field="max over fires and fuel levels of dstar_7_m_p50_90_99_max[3]",
          expected="largest 320 m",
          note="DIFFERENT FROM EXPECTED: RESULTS.md and TALK_NUMBERS say 'max 320 m (Uiseong, high fuel)' (Uiseong "
               f"fuel_high max = {fs['KFS_01']['fuel_high']['dstar_7_m_p50_90_99_max'][3]} m); the summary file holds "
               f"{mx[0]} m for {mx[1]} at {mx[2]}. The file value is printed.")
    L.add("Share below 375 m, every fire and fuel level", min(shares), file=f"{R}/data/fires/fires_summary.json",
          field="min of share_dstar_7_below_375m over fires and fuel levels", shown=f"{min(shares):.0%}")
    a = L.json(f"{R}/data/panels/summary.json")["A"]
    med = a["front_dstar_7_m_p50_90_max"][0]
    L.add("Replay front cells: median d*(7)", med, unit="m", shown=f"{med:.0f} m", file=f"{R}/data/panels/summary.json",
          field="A.front_dstar_7_m_p50_90_max[0]", n=f"{a['front_cells_reached_after_issue']:,} road cell-hours",
          expected="25 m")
    return d, below, mx, med, a["front_cells_reached_after_issue"], n


def main():
    L = Ledger("F16", "Safety zones")
    d, below, mx, med, nfront, n = read(L)
    W, H = S.W_IN, S.H_IN
    fig = S.new_figure()
    # ---------------- (a) geometry
    l, t, w, h = 6.9, 0.55, 6.0, 2.35
    ax = fig.add_axes([l / W, 1 - (t + h) / H, w / W, h / H])
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.75, 3.15)
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.plot([0.2, 9.8], [0, 0], color=S.INK, lw=1.0)
    fx, Hf = 1.2, 1.55
    flame = mp.Polygon([(fx - 0.45, 0), (fx + 0.45, 0), (fx, Hf)], closed=True, facecolor="#F3DAD6",
                       edgecolor=S.FIRE, lw=1.0)
    ax.add_patch(flame)
    rx = fx + 4 * Hf                  # receiver drawn at d = 4H, to scale
    ax.plot([rx, rx], [0, 0.9], color=S.INK, lw=1.5)
    ax.plot([rx], [0.9], marker="o", ms=6, color=S.INK)
    ax.annotate("", xy=(fx - 0.75, Hf), xytext=(fx - 0.75, 0),
                arrowprops=dict(arrowstyle="<|-|>,head_length=0.35,head_width=0.15", color=S.INK, lw=0.8))
    ax.text(fx - 0.95, Hf / 2, "$H$", ha="right", va="center", fontsize=S.PT_TITLE)
    ax.annotate("", xy=(rx, -0.35), xytext=(fx, -0.35),
                arrowprops=dict(arrowstyle="<|-|>,head_length=0.35,head_width=0.15", color=S.INK, lw=0.8))
    ax.text((fx + rx) / 2, -0.38, "$d$", ha="center", va="top", fontsize=S.PT_TITLE)
    ax.text(2.3, 2.75, "$d = 4H$  (Butler and Cohen 1998)", va="center")
    ax.text(2.3, 2.05, "$q^{\\prime\\prime} \\leq 7$ kW m$^{-2}$ at the receiver", va="center")
    S.panel_letter(fig, l - 0.3, t, "a")
    # ---------------- (b) distribution
    lb, tb, wb, hb = 8.0, 3.2, 4.85, 1.5
    axb = fig.add_axes([lb / W, 1 - (tb + hb) / H, wb / W, hb / H])
    grid(axb, axis="y")
    bins = np.arange(0, 410, 10)
    axb.hist(d, bins=bins, facecolor=S.LIGHT, edgecolor=S.INK, linewidth=0.5)
    axb.set_yscale("log")
    axb.axvline(375, color=S.INK, lw=1.2, ls=(0, (4, 2)))
    axb.annotate("one grid cell (375 m)", (375, 2500), xytext=(-8, 0), textcoords="offset points", ha="right",
                 va="center")
    axb.set_xlim(0, 400)
    axb.set_xticks([0, 100, 200, 300, 400])
    axb.set_ylim(0.8, 3e4)
    axb.set_yticks([1, 100, 10000])
    axb.set_yticklabels(["", "100", "10,000"])
    axb.set_xlabel("Safe separation distance $d^*$ at 7 kW m$^{-2}$ (m)")
    axb.set_ylabel("Burned cells")
    S.panel_letter(fig, l - 0.3, tb - 0.3, "b")
    cap = add_caption(fig, (
        "Figure 16. (a) A flame of height H and a receiver (person) at distance d on flat ground; the published rule "
        "d = 4H (Butler and Cohen 1998) keeps the radiant heat flux q″ reaching the receiver at or below 7 kW/m². "
        f"(b) The computed safe separation distance d* at 7 kW/m² in every burned cell of four reconstructed Korean "
        f"fires ({len(d):,} cells, baseline fuel; log count): {below:,} of {len(d):,} lie below one 375 m grid cell; "
        f"the largest over every fuel level is {mx[0]:.0f} m ({mx[1]}, high fuel). On the replay's front road cells "
        f"the median is {med:.0f} m ({nfront:,} cell-hours). Model output; no measured flux. Source: "
        "research/kcf-radiation."), x_in=0.45, width_in=12.45, top_in=5.85)
    L.save()
    save(fig, "F16_safety_zones", caption=cap)


if __name__ == "__main__":
    main()
