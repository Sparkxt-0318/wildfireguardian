#!/usr/bin/env python3
"""The two figures: leave-one-fire-out risk-coverage curve, and the 25 March 2025 timeline.

    python3 figures.py --numbers numbers.json --fig fig
"""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

SURF, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#e1e0d9", "#c3c2b7"
S1, S2, S3, S4, S5 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK, "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "lines.linewidth": 2.0, "font.family": "DejaVu Sans"})


def risk_coverage(nb, out):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.0), sharey=True)
    lo = nb["calibration_lofo"]["primary"]
    for ax, h in zip(axes, (5, 8)):
        rc = lo[f"h{h}"]["risk_coverage"]
        cov = np.array(rc["coverage"])
        risk = np.array([np.nan if v is None else v for v in rc["risk"]])
        o = np.argsort(cov)
        ax.plot(cov[o], risk[o], color=S1, lw=2, label="out-of-range score (frozen)")
        ax.axhline(rc["random_risk"], color=MUTED, lw=1.4, ls=(0, (5, 3)),
                   label=f"no abstention = random abstention ({rc['random_risk']:.1%})")
        ax.plot(rc["oracle_coverage"], rc["oracle_risk"], color=INK2, lw=1.2, ls=(0, (1, 2)),
                label="oracle (withholds missed hours first)")
        op = lo[f"h{h}"]["at_beta_0_05"]
        ax.plot([1 - op["abstention_rate"]], [op["miss_rate_retained"]], "o", ms=8, mfc=S1, mec=SURF, mew=2, zorder=5)
        ax.annotate(f"frozen rule (β = 0.05)\ncoverage {1 - op['abstention_rate']:.1%}, miss {op['miss_rate_retained']:.1%}",
                    (1 - op["abstention_rate"], op["miss_rate_retained"]), xytext=(-18, -34), textcoords="offset points",
                    ha="right", va="top", fontsize=8, color=INK, arrowprops=dict(arrowstyle="-", color=AXIS, lw=0.8),
                    bbox=dict(fc=SURF, ec="none", pad=1.5))
        ax.legend(loc="upper left", fontsize=7.5, frameon=False)
        sep = lo[f"h{h}"]["separation"]
        ax.set_title(f"{h} h margin (R = {nb['meta']['R_frozen_km'][str(h)]:.2f} km, LOFO per fire)\n"
                     f"AUROC {sep['auroc']:.2f} [{sep['auroc_ci95'][0]:.2f}, {sep['auroc_ci95'][1]:.2f}]: "
                     f"{sep['verdict']}", fontsize=9, loc="left", color=INK)
        ax.set_xlabel("coverage: share of issue hours with a number (fire-weighted)")
        ax.set_xlim(0, 1.0)
        ax.set_ylim(0, 1.45 * max(lo["h5"]["risk_coverage"]["random_risk"], lo["h8"]["risk_coverage"]["random_risk"]))
    axes[0].set_ylabel("miss rate among hours not abstained\n(fire-weighted, leave-one-fire-out)")
    fig.suptitle("Risk-coverage on the 28 GOFER calibration fires: does withholding the number on out-of-range hours "
                 "remove misses?", fontsize=10, x=0.01, ha="left", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(out, dpi=200)
    plt.close(fig)


def timeline(nb, out):
    rows = nb["march25"]["hours"]
    kst = np.array([r["kst_hour"] for r in rows])
    r5 = np.array([np.nan if r["reach5_km"] is None else r["reach5_km"] for r in rows])
    r8 = np.array([np.nan if r["reach8_km"] is None else r["reach8_km"] for r in rows])
    s = np.array([np.nan if r["score"] is None else r["score"] for r in rows])
    ab = np.array([bool(r["abstain"]) if r["abstain"] is not None else False for r in rows])
    tau = nb["thresholds_for_test_fires"]["primary"]
    R = nb["meta"]["R_frozen_km"]
    fig, axes = plt.subplots(3, 1, figsize=(9.2, 8.4), sharex=True, gridspec_kw=dict(height_ratios=[1.2, 0.9, 1.1]))
    for ax in axes:
        ax.axvspan(9.5, 20.5, color=GRID, alpha=0.55, lw=0, zorder=0)
    ax = axes[0]
    for y, col, h in ((r5, S1, 5), (r8, S2, 8)):
        Rh = R[str(h)]
        ax.axhline(Rh, color=col, lw=1.2, ls=(0, (5, 3)))
        ax.plot(kst, y, color=col, lw=2)
        miss = y > Rh
        ax.plot(kst[miss], y[miss], "o", ms=7, mfc=col, mec=SURF, mew=1.5)
        ax.plot(kst[~miss & np.isfinite(y)], y[~miss & np.isfinite(y)], "o", ms=7, mfc=SURF, mec=col, mew=1.5)
        pk = int(np.nanargmax(y))
        ax.annotate(f"{h} h reach", (kst[pk], y[pk]), xytext=(10, 4), textcoords="offset points", color=INK, fontsize=8)
    ax.text(0.01, 0.97, f"dashed: frozen margin R = {R['5']:.2f} km (5 h, blue), {R['8']:.2f} km (8 h, orange)",
            transform=ax.transAxes, color=INK2, fontsize=8, va="top", ha="left")
    ax.set_ylabel("reach beyond known fire (km)")
    ax.set_title("25 March 2025, Gyeongbuk (KFS_01): reach from detections vs the frozen margin; filled = margin missed",
                 fontsize=9, loc="left")
    ax = axes[1]
    ax.semilogy(kst, np.clip(s, 1e-4, 1), color=S1, lw=2)
    ax.plot(kst[ab], np.clip(s[ab], 1e-4, 1), "o", ms=8, mfc=S1, mec=SURF, mew=1.5)
    ax.plot(kst[~ab & np.isfinite(s)], np.clip(s[~ab & np.isfinite(s)], 1e-4, 1), "o", ms=7, mfc=SURF, mec=S1, mew=1.5)
    ax.axhline(max(tau, 1e-4), color=INK, lw=1.2, ls=(0, (5, 3)))
    ax.text(23.4, max(tau, 1e-4), f"abstain at or below τ = {tau:.4f}", fontsize=8, va="bottom", ha="right", color=INK)
    ax.set_ylabel("out-of-range score s\n(min tail probability; low = unusual)")
    ax.text(-0.3, 1.25e-4, "s = 0 (beyond every calibration hour) is drawn at 1e-4", fontsize=7.5, color=INK2, va="bottom")
    ax.set_title("Out-of-range score at each issue hour (GFS as issued, 5 h delay); filled = system abstains",
                 fontsize=9, loc="left")
    ax = axes[2]
    names = [("p_gust_ms", "gust", S1), ("p_w850_ms", "850 hPa wind", S2), ("p_rhmin_pct", "min RH", S3),
             ("p_hdw", "HDW", S4), ("p_prior3_km", "prior-3 h spread", S5)]
    ends = []
    for key, lab, col in names:
        v = np.array([np.nan if r[key] is None else r[key] for r in rows])
        ax.semilogy(kst, np.clip(v, 1e-4, 1), color=col, lw=1.8)
        last = np.flatnonzero(np.isfinite(v))[-1]
        ends.append([np.log10(np.clip(v[last], 1e-4, 1)), lab, kst[last]])
    ends.sort()
    for k in range(1, len(ends)):                       # keep end labels at least 0.24 decades apart
        ends[k][0] = max(ends[k][0], ends[k - 1][0] + 0.24)
    for y, lab, x in ends:
        ax.text(x + 0.3, 10 ** y, lab, fontsize=8, va="center", color=INK)
    ax.axhline(max(tau, 1e-4), color=INK, lw=1.2, ls=(0, (5, 3)))
    ax.set_ylabel("tail probability vs\n28 calibration fires")
    ax.set_title("Each predictor's share of calibration hours at least as dangerous (fire-weighted)", fontsize=9, loc="left")
    ax.set_xlabel("issue hour, KST on 25 March 2025 (grey band: 10:00-20:00, when the margin failed)")
    ax.set_xticks(range(0, 24, 2))
    ax.set_xlim(-0.5, 25.5)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--numbers", required=True)
    ap.add_argument("--fig", required=True)
    a = ap.parse_args()
    nb = json.load(open(a.numbers))
    Path(a.fig).mkdir(parents=True, exist_ok=True)
    risk_coverage(nb, Path(a.fig) / "risk_coverage.png")
    timeline(nb, Path(a.fig) / "march25_timeline.png")


if __name__ == "__main__":
    main()
