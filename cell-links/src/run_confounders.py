"""Step 7: confounders. Rain attenuation compared with fire signatures, the effect of ATPC, and
what one simulated crossing looks like under three logging schemes with real OpenMRG noise.

Usage: .venv/bin/python -I src/run_confounders.py
Outputs: results/confounders/*.csv, figures/conf_*.png/svg, NUMBERS.json entries conf.*
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from pycomlink.processing.k_R_relation import a_b  # noqa: E402

from common import OI, RESULTS, load_config, record, savefig, style  # noqa: E402
from detect import minmax_15, quantize  # noqa: E402
from run_detection import DT, apply_atpc, dry_chunks, load_openmrg, wet_mask_from_gauges  # noqa: E402

OUT = RESULTS / "confounders"


def main():
    cfg = load_config("detection.json")
    gsum = pd.read_csv(RESULTS / "geometry" / "summary.csv", index_col=0)
    OUT.mkdir(parents=True, exist_ok=True)
    style()
    nums = {}

    # ---- Rain: path attenuation for light rain over the median hop of each band ----
    rows = []
    for band, r in gsum.drop(index="All").iterrows():
        f = float(band.split()[0])
        a, b = a_b(f, "V", approx_type="ITU_2005")
        for R in [0.5, 1.0, 2.0, 5.0]:
            rows.append({"band": band, "f_ghz": f, "median_L_km": r.median_L_km, "rain_mm_h": R,
                         "gamma_db_km": float(a[0] * R ** b[0]), "path_db": float(a[0] * R ** b[0] * r.median_L_km)})
    rain = pd.DataFrame(rows)
    rain.to_csv(OUT / "rain_attenuation.csv", index=False)
    print(rain.pivot(index="band", columns="rain_mm_h", values="path_db").round(2))
    for _, r in rain.iterrows():
        nums[f"conf.rain.{r.band.replace(' ', '')}.{r.rain_mm_h:g}mmh.path_db"] = (r.path_db, "dB",
            f"ITU-R P.838-3 path attenuation, vertical pol., uniform {r.rain_mm_h:g} mm/h over the median {r.band} hop")

    # Fire signature magnitudes for comparison (extreme scenario)
    md = pd.read_csv(RESULTS / "crossings" / "links_extreme.csv")
    order = ["7 GHz", "13 GHz", "18 GHz", "23 GHz", "38 GHz", "80 GHz"]
    fig, ax = plt.subplots(figsize=(8.5, 4))
    for i, band in enumerate(order):
        g = md[md.band == band]
        y = np.sort(g.maxA_lab_peak.to_numpy())
        yy = y[y > 0.05]
        ax.scatter(np.full(len(yy), i) - 0.12 + 0.08 * np.random.default_rng(i).uniform(-1, 1, len(yy)), yy,
                   s=9, color=OI["vermillion"], alpha=0.7, lw=0, label="Fire: peak mean loss (crossings above 0.05 dB)" if i == 0 else None)
        ys = g.maxS.to_numpy()
        ax.scatter(np.full(len(ys), i) + 0.12 + 0.08 * np.random.default_rng(i + 9).uniform(-1, 1, len(ys)), ys,
                   s=9, color=OI["blue"], alpha=0.5, lw=0, label="Fire: peak scintillation std (all crossings)" if i == 0 else None)
        for R, mk in [(1.0, "_"), (5.0, "_")]:
            v = rain[(rain.band == band) & (rain.rain_mm_h == R)].path_db.iloc[0]
            ax.scatter(i, v, marker=mk, s=500, color=OI["green"] if R == 1 else OI["black"], lw=2,
                       label=(f"Rain {R:g} mm/h over median hop" if i == 0 else None), zorder=5)
    ax.set_yscale("log")
    ax.set_ylim(5e-3, 40)
    ax.set_xticks(range(len(order)), order)
    ax.set_ylabel("dB")
    ax.set_title("Simulated fire signatures ('extreme' spread) versus light-rain attenuation", fontsize=10.5)
    ax.legend(fontsize=7.5, loc="upper left", ncol=2)
    fig.tight_layout()
    savefig(fig, "conf_rain_vs_fire")

    # ---- One crossing under several logging schemes with real noise ----
    rng = np.random.default_rng(cfg["seed"] + 1)
    x, _ = load_openmrg(cfg, 40, rng)
    wet = wet_mask_from_gauges(x.index, cfg)
    chunks = dry_chunks(x, wet, 12 * 3600)
    sig = np.load(RESULTS / "crossings" / "signatures_extreme.npz")
    best = md.sort_values("maxA_lab_peak").iloc[-int(len(md) * 0.03)]  # a strong but not the most extreme case
    key = f"link{int(best.link)}"
    t, A, S = sig[key + "_t"], sig[key + "_A_lab_peak"], sig[key + "_S"]
    i0 = int(np.argmax(A > 0.05)) - 180
    seg = slice(max(i0, 0), max(i0, 0) + 360 * 2)
    A, S, t = A[seg], S[seg], t[seg]
    noise = sorted(chunks, key=lambda c: np.std(c[2]))[len(chunks) // 2][2][: len(A) + 360]
    lead = 360
    fade = np.zeros(len(noise))
    fade[lead:lead + len(A)] = A + S * rng.standard_normal(len(A))
    y = noise - fade
    tm = (np.arange(len(y)) - lead) * DT / 60 + (t[0] - best.t_first_s) / 60
    fig, axes = plt.subplots(3, 1, figsize=(8.5, 7.2), sharex=True)
    axes[0].plot(tm, quantize(y, 0.3), color=OI["blue"], lw=0.8, label="10 s instantaneous, 0.3 dB (as OpenMRG)")
    axes[0].plot(tm[::6], quantize(y[::6], 0.3), color=OI["vermillion"], lw=1.2, marker="o", ms=2.5,
                 label="1 min instantaneous, 0.3 dB (as Germany)")
    lo, hi = minmax_15(y, DT, 1.0)
    tb = tm[::90][: len(lo)] + 7.5
    axes[0].step(tb, lo, where="mid", color=OI["green"], lw=1.4, label="15 min min/max, 1 dB (as Netherlands)")
    axes[0].step(tb, hi, where="mid", color=OI["green"], lw=1.4)
    axes[0].set_ylabel("RSL - TSL change (dB)")
    axes[0].legend(fontsize=7.5, loc="lower left")
    axes[0].set_title(f"One simulated {best.band} crossing ({best.L_m/1e3:.1f} km) in real dry OpenMRG noise", fontsize=10.5)
    for w, col in [(2.0, OI["purple"]), (5.0, OI["orange"])]:
        axes[1].plot(tm, quantize(noise - apply_atpc(fade, w), 0.3), color=col, lw=0.8, label=f"RSL only, ATPC window {w:g} dB")
    axes[1].plot(tm, quantize(y, 0.3), color=OI["blue"], lw=0.6, alpha=0.6, label="RSL - TSL (ATPC visible through TSL)")
    axes[1].set_ylabel("Logged level (dB)")
    axes[1].legend(fontsize=7.5, loc="lower left")
    axes[2].plot(tm, -np.r_[np.zeros(lead), A, np.zeros(len(y) - lead - len(A))][: len(tm)], color=OI["vermillion"],
                 label="Mean fire loss (model)")
    axes[2].fill_between(tm, -2 * np.r_[np.zeros(lead), S, np.zeros(len(y) - lead - len(S))][: len(tm)],
                         2 * np.r_[np.zeros(lead), S, np.zeros(len(y) - lead - len(S))][: len(tm)],
                         color=OI["skyblue"], alpha=0.6, lw=0, label="+- 2 x scintillation std (model)")
    axes[2].set_ylabel("Model signal (dB)")
    axes[2].set_xlabel("Minutes after the fire first reaches the link ground track")
    axes[2].legend(fontsize=7.5, loc="lower left")
    fig.tight_layout()
    savefig(fig, "conf_logging_example")
    nums["conf.example.maxA_db"] = (float(best.maxA_lab_peak), "dB", "Peak mean loss of the logging example crossing")
    nums["conf.example.mm15_min_drop_db"] = (float(np.nanmedian(lo[:4]) - np.nanmin(lo)), "dB",
                                             "Drop of the 15-min minimum in the logging example")
    record(nums, "src/run_confounders.py", "configs/detection.json")


if __name__ == "__main__":
    main()
