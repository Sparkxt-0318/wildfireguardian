"""F06 safety distance: how far each calibration fire ran in 5 hours, the safety distance, and 25 March 2025.

Slide 6, right two thirds. One strip per California fire (28 GOFER fires, every issue hour), the frozen safety
distance R(5 h) as a blue line with the held-out miss rate, and the 25 March 2025 Gyeongbuk hours in brick red
inside a hatched band: the answer was withheld because the hour lay outside all calibration data.
Sources: research/kcf-margin/{numbers.json, derived/gofer_reach.csv.gz, derived/gyeongbuk_reach.csv};
research/kcf-abstain/numbers.json.
"""
import gzip
import io

import numpy as np
import pandas as pd

import style as S
from figkit import save
from prov import Ledger, git_show

M = "research/kcf-margin"


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
                 field="table[...].lofo_miss", n=f"{row['n_fires']} fires, {row['hours']} hours",
                 expected="6.2%", note=f"95% interval {row['lofo_ci95'][0] * 100:.1f}–{row['lofo_ci95'][1] * 100:.0f}%")
    raw = git_show(f"{M}/derived/gofer_reach.csv.gz")
    df = pd.read_csv(io.BytesIO(gzip.decompress(raw)))
    df = df[df["h"] == 5]
    L.add("California issue hours plotted (5 h reach, km)", len(df), file=f"{M}/derived/gofer_reach.csv.gz",
          field="rows with h == 5, column reach_km", n=f"{df['fire'].nunique()} fires", expected="20,161 hours")
    cal_max = L.add("Largest 5 h reach in the calibration set", df["reach_km"].max(), unit="km",
                    shown=f"{df['reach_km'].max():.1f} km", file=f"{M}/derived/gofer_reach.csv.gz",
                    field="max reach_km at h == 5", expected="17.3 km")
    gk = pd.read_csv(io.BytesIO(git_show(f"{M}/derived/gyeongbuk_reach.csv")))
    gk = gk[(gk["h"] == 5) & (gk["complete"])]
    L.add("Gyeongbuk complete issue hours plotted", len(gk), file=f"{M}/derived/gyeongbuk_reach.csv",
          field="rows with h == 5 and complete == True, column reach_km", expected="23 hours")
    kmax = L.add("Largest Gyeongbuk 5 h reach", gk["reach_km"].max(), unit="km", shown=f"{gk['reach_km'].max():.1f} km",
                 file=f"{M}/derived/gyeongbuk_reach.csv", field="max reach_km (h == 5)", expected="up to 40.1 km")
    ab = L.json("research/kcf-abstain/numbers.json")
    run = ab["march25"]["hours_10_20_kst"]
    n_with = sum(bool(h["abstain"]) for h in run)
    L.add("Run hours (10–20 KST) with the answer withheld", n_with, shown=f"{n_with} of {len(run)}",
          file="research/kcf-abstain/numbers.json", field="march25.hours_10_20_kst[*].abstain", expected="11 of 11",
          note="'outside all calibration data' = beyond all 20,065 calibration hours of the abstain scoring set "
               "(kcf-abstain RESULTS.md); over all 24 hours of the day 22 were withheld (march25.hours[*].abstain)")
    run_hours = {int(h["kst_hour"]) for h in run}
    return df, gk, R, miss, cal_max, kmax, n_with, len(run), run_hours


def main():
    L = Ledger("F06", "Safety distance and 25 March 2025")
    df, gk, R, miss, cal_max, kmax, n_with, n_run, run_hours = read(L)
    fig = S.new_figure()
    W, H = S.W_IN, S.H_IN
    l, t, w, h = 5.55, 1.15, 7.05, 5.05
    ax = fig.add_axes([l / W, 1 - (t + h) / H, w / W, h / H])
    # California strips, ordered by each fire's largest reach
    order = df.groupby("fire")["reach_km"].max().sort_values().index.tolist()
    rng = np.random.RandomState(3)
    for i, f in enumerate(order):
        v = df.loc[df["fire"] == f, "reach_km"].to_numpy()
        x = i + rng.uniform(-0.28, 0.28, len(v))
        ax.scatter(x, v, s=7, color=S.MID, alpha=0.45, linewidths=0, rasterized=True)
    nf = len(order)
    kx = nf + 2.2                              # Korean column
    ax.set_xlim(-1.0, kx + 1.3)
    ymax = 54.5
    ax.set_ylim(-1.5, ymax)
    # hatched band for the withheld answers
    ax.fill_between([kx - 0.9, kx + 0.9], -1.5, 43.0, facecolor=S.WHITE, edgecolor=S.LIGHT, hatch="///",
               linewidth=0, gid="bg:withheld band")
    run_mask = gk["kst_hour"].astype(int).isin(run_hours)
    jit = np.linspace(-0.35, 0.35, len(gk))
    ax.scatter(kx + jit[~run_mask.to_numpy()], gk.loc[~run_mask, "reach_km"], s=60, facecolors=S.WHITE,
               edgecolors=S.FIRE, linewidths=1.6, zorder=4)
    ax.scatter(kx + jit[run_mask.to_numpy()], gk.loc[run_mask, "reach_km"], s=70, color=S.FIRE, zorder=5,
               linewidths=0)
    # safety distance
    ax.plot([-1.0, nf + 0.4], [R, R], color=S.OURS, lw=3, zorder=6, solid_capstyle="butt")
    ax.text(-0.6, 12.8, f"safety distance {R:.2f} km", color=S.OURS, fontsize=S.PT_BODY, fontweight="bold",
            va="center", ha="left")
    ax.plot([0.4, 0.4], [R + 0.9, 9.6], color=S.OURS, lw=1.2)
    ax.text(0.4, 28.5, f"{miss * 100:.1f}%", color=S.OURS, fontsize=S.PT_KEY, fontweight="bold", va="center")
    ax.text(5.9, 28.5, "of held-out hours ran past it\n(leave one fire out)", color=S.INK,
            fontsize=S.PT_MIN, va="center", linespacing=1.15)
    ax.text(nf - 0.5, 21.0, f"largest in calibration: {cal_max:.1f} km", ha="right", va="center",
            fontsize=S.PT_MIN, color=S.MID)
    ax.annotate(f"{kmax:.1f} km", (kx + jit[int(np.argmax(gk['reach_km'].to_numpy()))], kmax), xytext=(-16, 0),
                textcoords="offset points", ha="right", va="center", fontsize=S.PT_LABEL, color=S.FIRE,
                fontweight="bold")
    ax.text(kx + 0.9, 51.6, "answer withheld: outside all calibration data", ha="right", va="center",
            fontsize=S.PT_MIN, color=S.INK)
    ax.text(kx + 0.9, 47.2, f"{n_with} of {n_run} run hours (10–20 KST, filled)", ha="right", va="center",
            fontsize=S.PT_MIN, color=S.MID)
    ax.set_xticks([(nf - 1) / 2, kx])
    ax.set_xticklabels([f"{nf} California fires, every issue hour\n({len(df):,} hours, one column per fire)",
                        "Gyeongbuk\n25 Mar 2025"], fontsize=S.PT_MIN, linespacing=1.15)
    ax.tick_params(axis="x", length=0)
    ax.spines["bottom"].set_visible(False)
    ax.set_yticks([0, 10, 20, 30, 40])
    ax.set_ylabel("How far the fire ran in 5 hours (km)")
    L.save()
    save(fig, "F06_safety_distance")


if __name__ == "__main__":
    main()
