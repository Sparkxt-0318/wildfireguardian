"""F06 safety distance: how far each calibration fire spread in 5 hours, the safety distance, and 25 March 2025.

Slide 6, full width. Left: one strip per California fire (28 GOFER fires, every issue hour), the frozen safety
distance R(5 h) as a blue line, labelled with the held-out miss rate and its 95% interval, and the largest calibration
value. Right, same y axis: the 25 March 2025 Gyeongbuk fire by issue hour (KST), each hour marked by what the
calibration gate did (answer withheld: filled triangle; answer given: open circle), with its largest value labelled.
Sources: research/kcf-margin/{numbers.json, derived/gofer_reach.csv.gz, derived/gyeongbuk_reach.csv};
research/kcf-abstain/numbers.json.
"""
import gzip
import io

import matplotlib.patheffects as pe
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

import style as S
from figkit import add_caption, boxed_legend, grid, save
from prov import Ledger, git_show

M = "research/kcf-margin"
AB = "research/kcf-abstain/numbers.json"
YMAX = 50


def read(L):
    nb = L.json(f"{M}/numbers.json")
    row = [r for r in nb["table"] if r["fire_set"] == "all28" and r["h"] == 5 and r["cls"] == "all"
           and r["alpha"] == 0.1][0]
    R = L.add("Safety distance R(5 h), 10% target", row["R_km"], unit="km", shown=f"{row['R_km']:.2f} km",
              file=f"{M}/numbers.json", field="table[fire_set=all28, h=5, cls=all, alpha=0.1].R_km",
              n=f"{row['n_fires']} fires, {row['hours']} issue hours", expected="3.8 km",
              note="TALK_NUMBERS rounds 3.75 to 3.8; the figure prints the file value")
    miss = L.add("Held-out (leave-one-fire-out) share of hours beyond R", row["lofo_miss"],
                 shown=f"{row['lofo_miss'] * 100:.1f}%", file=f"{M}/numbers.json",
                 field="table[...].lofo_miss", n=f"{row['n_fires']} fires, {row['hours']} hours", expected="6.2%")
    ci = L.add("95% interval of the held-out share", row["lofo_ci95"],
               shown=f"{row['lofo_ci95'][0] * 100:.1f}–{row['lofo_ci95'][1] * 100:.0f}%", file=f"{M}/numbers.json",
               field="table[...].lofo_ci95")
    raw = git_show(f"{M}/derived/gofer_reach.csv.gz")
    df = pd.read_csv(io.BytesIO(gzip.decompress(raw)))
    df = df[df["h"] == 5]
    nf = L.add("California fires plotted", df["fire"].nunique(), file=f"{M}/derived/gofer_reach.csv.gz",
               field="distinct fire, rows with h == 5", expected="28")
    L.add("California issue hours plotted (5 h reach, km)", len(df), shown=f"{len(df):,}",
          file=f"{M}/derived/gofer_reach.csv.gz", field="rows with h == 5, column reach_km", n=f"{nf} fires",
          expected="20,161 hours")
    cal_max = L.add("Largest 5 h reach in the calibration set", df["reach_km"].max(), unit="km",
                    shown=f"{df['reach_km'].max():.1f} km", file=f"{M}/derived/gofer_reach.csv.gz",
                    field="max reach_km at h == 5", expected="17.3 km")
    gk = pd.read_csv(io.BytesIO(git_show(f"{M}/derived/gyeongbuk_reach.csv")))
    gk = gk[(gk["h"] == 5) & (gk["complete"])].copy()
    L.add("Gyeongbuk complete issue hours plotted", len(gk), file=f"{M}/derived/gyeongbuk_reach.csv",
          field="rows with h == 5 and complete == True, column reach_km", expected="23 hours")
    imax = gk["reach_km"].idxmax()
    kmax = L.add("Largest Gyeongbuk 5 h reach", gk.loc[imax, "reach_km"], unit="km",
                 shown=f"{gk.loc[imax, 'reach_km']:.1f} km", file=f"{M}/derived/gyeongbuk_reach.csv",
                 field="max reach_km (h == 5)", expected="up to 40.1 km",
                 note=f"issued {int(gk.loc[imax, 'kst_hour']):02d}:00 KST")
    ab = L.json(AB)["march25"]
    gate = {int(h["kst_hour"]): bool(h["abstain"]) for h in ab["hours"]}
    reach5 = {int(h["kst_hour"]): h["reach5_km"] for h in ab["hours"]}
    assert all(abs(reach5[int(k_)] - r_) < 1e-6 for k_, r_ in zip(gk["kst_hour"], gk["reach_km"]))
    gk["withheld"] = gk["kst_hour"].astype(int).map(gate)
    n_w = int(gk["withheld"].sum())
    L.add("Gyeongbuk plotted hours: answer withheld / given", [n_w, len(gk) - n_w],
          shown=f"withheld ({n_w}), given ({len(gk) - n_w})", file=AB,
          field="march25.hours[kst_hour].abstain, joined on kst_hour with the plotted hours",
          note="reach5_km in this file equals reach_km in gyeongbuk_reach.csv for every plotted hour (checked)")
    run = ab["hours_10_20_kst"]
    n_run = sum(bool(h["abstain"]) for h in run)
    L.add("Run hours (10–20 KST) with the answer withheld", n_run, shown=f"{n_run} of {len(run)}",
          file=AB, field="march25.hours_10_20_kst[*].abstain", expected="11 of 11",
          note="'outside all calibration data' = beyond all 20,065 calibration hours of the abstain scoring set "
               "(kcf-abstain RESULTS.md); over all 24 hours of the day 22 were withheld (march25.hours[*].abstain)")
    return df, gk, R, miss, ci, cal_max, kmax, n_w, n_run, len(run), nf


def main():
    L = Ledger("F06", "Safety distance and 25 March 2025")
    df, gk, R, miss, ci, cal_max, kmax, n_w, n_run, n_runh, nf = read(L)
    fig = S.new_figure()
    W, H = S.W_IN, S.H_IN
    top, h = 0.95, 4.15
    xa, wa = 1.35, 7.25
    xb, wb = 9.25, 3.6

    def axes(x, w):
        return fig.add_axes([x / W, 1 - (top + h) / H, w / W, h / H])

    def box_label(ax, text, xy, xytext, ha="center"):
        """Direct label on its own white box (a patch, so the text-free picture keeps it) with a leader line from
        the box edge to the point."""
        t = ax.text(*xytext, text, ha=ha, va="center", fontsize=S.PT_TEXT, zorder=8)
        fig.canvas.draw()
        bb = t.get_window_extent(fig.canvas.get_renderer())
        px, py = 10 * S.DPI / 72, 6 * S.DPI / 72
        bx0, by0, bx1, by1 = bb.x0 - px, bb.y0 - py, bb.x1 + px, bb.y1 + py
        inv = ax.transData.inverted()
        (x0, y0), (x1, y1) = inv.transform([(bx0, by0), (bx1, by1)])
        box = Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=S.WHITE, edgecolor=S.INK, linewidth=0.6, zorder=7)
        box.set_gid("box:label")
        ax.add_patch(box)
        # leave the box where the straight line from its centre to the point crosses its edge (display pixels)
        cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
        tx, ty = ax.transData.transform(xy)
        dx, dy = tx - cx, ty - cy
        s = min((bx1 - cx) / abs(dx) if dx else np.inf, (by1 - cy) / abs(dy) if dy else np.inf)
        ex, ey = inv.transform((cx + s * dx, cy + s * dy))
        ln, = ax.plot([ex, xy[0]], [ey, xy[1]], color=S.INK, lw=1.2, zorder=6, solid_capstyle="butt",
                      path_effects=[pe.Stroke(linewidth=3.4, foreground=S.WHITE), pe.Normal()])
        ln.set_gid("leader")
        return t

    # ---------------------------------------------------------------- left: California
    ax = axes(xa, wa)
    grid(ax, axis="y")
    order = df.groupby("fire")["reach_km"].max().sort_values().index.tolist()
    rng = np.random.RandomState(3)
    for i, f in enumerate(order):
        v = df.loc[df["fire"] == f, "reach_km"].to_numpy()
        x = i + rng.uniform(-0.28, 0.28, len(v))
        ax.scatter(x, v, s=6, color=S.MID, alpha=0.5, linewidths=0, rasterized=True)
    ax.set_xlim(-1.0, nf)
    ax.set_ylim(-1.5, YMAX)
    ax.plot([-1.0, nf], [R, R], color=S.OURS, lw=2, zorder=6)
    ax.set_xticks([])
    ax.set_xlabel("One column per fire, by largest spread", labelpad=S.LABEL_PAD)
    ax.set_yticks([0, 10, 20, 30, 40])
    ax.set_ylabel("Fire spread within 5 hours (km)")
    fig.text(xa / W, 1 - (top - 0.32) / H, f"{nf} California fires, {len(df):,} hours", va="center")
    box_label(ax, f"safety distance {R:.2f} km", (2.0, R), (5.2, 11.0))
    ax.text(-0.3, 21.5, f"passed in {miss * 100:.1f}% of held-out hours", va="center", fontsize=S.PT_TEXT)
    ax.text(-0.3, 16.3, f"(95% interval {ci[0] * 100:.1f}–{ci[1] * 100:.0f}%)", va="center", fontsize=S.PT_TEXT)
    imx = order.index(df.loc[df["reach_km"].idxmax(), "fire"])
    box_label(ax, f"largest: {cal_max:.1f} km", (imx, cal_max), (imx - 4.5, 27.5))

    # ---------------------------------------------------------------- right: Gyeongbuk, by issue hour
    bx = axes(xb, wb)
    grid(bx, axis="y")
    hrs = gk["kst_hour"].astype(int).to_numpy()
    v = gk["reach_km"].to_numpy()
    w = gk["withheld"].to_numpy()
    bx.plot(hrs, v, color=S.FIRE, lw=0.8, alpha=0.6, zorder=3)
    bx.scatter(hrs[w], v[w], s=58, marker="^", color=S.FIRE, linewidths=0, zorder=5)
    bx.scatter(hrs[~w], v[~w], s=48, marker="o", facecolors=S.WHITE, edgecolors=S.FIRE, linewidths=1.4, zorder=5)
    bx.plot([-1.5, 23.5], [R, R], color=S.OURS, lw=2, zorder=4)
    bx.set_xlim(-1.5, 23.5)
    bx.set_ylim(-1.5, YMAX)
    bx.set_yticks([0, 10, 20, 30, 40])
    bx.tick_params(axis="y", labelleft=False, length=0)
    bx.set_xticks([0, 6, 12, 18])
    bx.set_xticklabels(["00:00", "06:00", "12:00", "18:00"])
    bx.set_xlabel("Hour forecast issued (KST)", labelpad=S.LABEL_PAD)
    fig.text(xb / W, 1 - (top - 0.32) / H, "Gyeongbuk fire, 25 March 2025", va="center")
    hk = int(gk.loc[gk["reach_km"].idxmax(), "kst_hour"])
    box_label(bx, f"largest: {kmax:.1f} km", (hk, kmax), (7.5, 46.0))
    hs = [Line2D([], [], marker="^", ls="none", color=S.FIRE, ms=9),
          Line2D([], [], marker="o", ls="none", mfc=S.WHITE, mec=S.FIRE, mew=1.4, ms=8)]
    boxed_legend(bx, hs, [f"withheld ({n_w})", f"given ({len(gk) - n_w})"],
                 title="Answer", alignment="left", title_fontsize=S.PT_TEXT, loc="upper left", bbox_to_anchor=(0.0, 0.84), fontsize=S.PT_TEXT, handletextpad=0.4,
                 borderaxespad=0.3, labelspacing=0.8)

    cap = add_caption(fig, (
        f"Figure 6. How far each fire spread in the 5 hours after each forecast hour. Left: {len(df):,} hours of {nf} "
        f"California calibration fires; the frozen safety distance of {R:.2f} km (blue) was passed in "
        f"{miss * 100:.1f}% of held-out hours (leave one fire out). Right: on 25 March 2025 the Gyeongbuk fire reached "
        f"{kmax:.1f} km, beyond every calibration value, and the answer was withheld in {n_w} of {len(gk)} hours, "
        f"including {n_run} of {n_runh} run hours 10–20 KST. Source: research/kcf-margin, research/kcf-abstain."),
        x_in=0.45, width_in=12.45, top_in=6.12)
    L.save()
    save(fig, "F06_safety_distance", caption=cap)


if __name__ == "__main__":
    main()
