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
from figkit import add_caption, boxed_legend, grid, save
from prov import Ledger, git_show

M = "research/kcf-margin"
CI = None


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
    global CI
    CI = row['lofo_ci95']
    return df, gk, R, miss, cal_max, kmax, n_with, len(run), run_hours


def main():
    L = Ledger("F06", "Safety distance and 25 March 2025")
    df, gk, R, miss, cal_max, kmax, n_with, n_run, run_hours = read(L)
    fig = S.new_figure()
    W, H = S.W_IN, S.H_IN
    l, t, w, h = 6.0, 0.5, 6.9, 4.2
    ax = fig.add_axes([l / W, 1 - (t + h) / H, w / W, h / H])
    grid(ax, axis="y")
    order = df.groupby("fire")["reach_km"].max().sort_values().index.tolist()
    rng = np.random.RandomState(3)
    for i, f in enumerate(order):
        v = df.loc[df["fire"] == f, "reach_km"].to_numpy()
        x = i + rng.uniform(-0.28, 0.28, len(v))
        sc = ax.scatter(x, v, s=6, color=S.MID, alpha=0.5, linewidths=0, rasterized=True,
                        label="California hour (28 fires)" if i == 0 else None)
    nf = len(order)
    kx = nf + 2.2
    ax.set_xlim(-1.0, kx + 1.3)
    ax.set_ylim(-1.5, 45)
    band = ax.fill_between([kx - 0.9, kx + 0.9], -1.5, 45, facecolor=S.WHITE, edgecolor=S.MID, hatch="///",
                           linewidth=0, label="answer withheld")
    band.set_gid("bg:withheld band")
    run_mask = gk["kst_hour"].astype(int).isin(run_hours).to_numpy()
    jit = np.linspace(-0.35, 0.35, len(gk))
    ax.scatter(kx + jit[~run_mask], gk.loc[~run_mask, "reach_km"], s=40, marker="o", facecolors=S.WHITE,
               edgecolors=S.FIRE, linewidths=1.2, zorder=4, label="Gyeongbuk, other hours")
    ax.scatter(kx + jit[run_mask], gk.loc[run_mask, "reach_km"], s=48, marker="^", color=S.FIRE, zorder=5,
               linewidths=0, label="Gyeongbuk, run hours 10–20 KST")
    ax.plot([-1.0, kx + 1.3], [R, R], color=S.OURS, lw=2, zorder=6, label=f"safety distance {R:.2f} km")
    ax.set_xticks([(nf - 1) / 2, kx])
    ax.set_xticklabels(["28 California fires\n(one column per fire)", "Gyeongbuk\n25 Mar 2025"], linespacing=1.15)
    ax.tick_params(axis="x", length=0)
    ax.set_yticks([0, 10, 20, 30, 40])
    ax.set_ylabel("Distance run in 5 hours (km)")
    boxed_legend(ax, loc="upper left", fontsize=S.PT_TEXT, labelspacing=0.6, markerscale=1.6)
    cap = add_caption(fig, (
        f"Figure 6. How far each fire ran in the 5 hours after every issue hour: {len(df):,} hours of {nf} California "
        f"calibration fires (grey) and the 25 March 2025 Gyeongbuk fire (red; complete hours). The frozen safety "
        f"distance of {R:.2f} km (blue) was passed in {miss * 100:.1f}% of held-out hours (leave one fire out; 95% "
        f"interval {CI[0] * 100:.1f}–{CI[1] * 100:.0f}%). The largest calibration value is {cal_max:.1f} km; Gyeongbuk reached {kmax:.1f} km, "
        f"and the answer was withheld in {n_with} of {n_run} run hours as outside all calibration data (hatched). "
        "Source: research/kcf-margin, research/kcf-abstain."), x_in=0.45, width_in=12.45, top_in=5.8)
    L.save()
    save(fig, "F06_safety_distance", caption=cap)


if __name__ == "__main__":
    main()
