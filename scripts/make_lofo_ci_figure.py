#!/usr/bin/env python
"""Two-panel headline figure for the spread_v2 LOFO validation.

LEFT  — per-fire leave-one-fire-out ROC-AUC as horizontal bars with DeLong
        95 % CI whiskers, plus two reference lines: the mean-of-folds (black
        dashed, 0.889) and the overall pooled AUC (grey dotted, 0.905).
RIGHT — burned-area IoU: data-driven (forward-sim) 0.40 vs mechanistic
        (Rothermel CA) 0.09.

All values are the published submission numbers (transcribed straight from the
figure / README table); this script just re-renders the chart so the PNG can be
regenerated cleanly. Run:  python scripts/make_lofo_ci_figure.py
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FIG = REPO / "docs" / "figures"
OUT = FIG / "spread_v2_lofo_ci.png"

# ── colours ──────────────────────────────────────────────────────────────
BLUE = "#4c72b0"     # standard per-fire bar
NAVY = "#2c3e6b"     # yeongdeok 2025 (demo) — highlighted
RED = "#c0392b"      # gangneung 2023 — tiny/noisy fold
GREY = "#b0b3b8"     # mechanistic bar
NAVY_TXT = "#21314f"  # value labels on the right panel
POOLED_C = "#7f7f7f"  # grey dotted pooled line + its label

# ── per-fire data (top → bottom, exactly as on the figure) ───────────────
# (label, auc, ci_low, ci_high, colour)
FIRES = [
    ("miryang\n2022",            0.974, 0.941, 0.989, BLUE),
    ("hongseong\n2023",          0.945, 0.916, 0.964, BLUE),
    ("yeongdeok\n2025\n(데모)",   0.941, 0.936, 0.946, NAVY),
    ("uljin_samcheok\n2022",     0.918, 0.911, 0.924, BLUE),
    ("uiseong_andong\n2025",     0.878, 0.871, 0.884, BLUE),
    ("gangneung_2023\n(8건·noisy)", 0.682, 0.577, 0.771, RED),
]
MEAN_OF_FOLDS = 0.889
POOLED = 0.905


def _setup_font() -> bool:
    plt.rcParams["axes.unicode_minus"] = False
    for p in ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
              "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf"):
        if os.path.exists(p):
            fm.fontManager.addfont(p)
            plt.rcParams["font.family"] = fm.FontProperties(fname=p).get_name()
            return True
    available = {f.name for f in fm.fontManager.ttflist}
    for name in ("Noto Sans CJK KR", "NanumGothic", "Malgun Gothic",
                 "AppleGothic", "WenQuanYi Zen Hei", "WenQuanYi Zen Hei Sharp"):
        if name in available:
            plt.rcParams["font.family"] = name
            return True
    return False


def left_panel(ax):
    n = len(FIRES)
    y = np.arange(n)[::-1]                       # first row at top
    aucs = np.array([f[1] for f in FIRES])
    lo = np.array([f[2] for f in FIRES])
    hi = np.array([f[3] for f in FIRES])
    colors = [f[4] for f in FIRES]
    xerr = np.vstack([aucs - lo, hi - aucs])     # asymmetric DeLong CI

    ax.barh(y, aucs, color=colors, height=0.62, zorder=2)
    ax.errorbar(aucs, y, xerr=xerr, fmt="none", ecolor="#222222",
                elinewidth=1.1, capsize=3.5, capthick=1.1, zorder=4)

    # FIX 1 — one identical label style for ALL six bars: white, bold,
    # right-aligned just INSIDE each bar tip, drawn on top so the value reads
    # cleanly and no label is jammed against a CI cap/whisker.
    for yi, a in zip(y, aucs):
        ax.text(a - 0.006, yi, f"{a:.3f}", ha="right", va="center",
                color="white", fontsize=9, fontweight="bold", zorder=6)

    ax.set_yticks(y)
    ax.set_yticklabels([f[0] for f in FIRES], fontsize=8.5)
    ax.set_xlim(0.5, 1.0)
    ax.set_ylim(-0.8, n - 0.4)
    ax.set_xlabel("ROC-AUC (LOFO) · 막대=95% DeLong 신뢰구간", fontsize=9.5)

    # reference lines (unchanged) …
    ax.axvline(MEAN_OF_FOLDS, ls="--", color="black", lw=1.2, zorder=3)
    ax.axvline(POOLED, ls=":", color=POOLED_C, lw=1.4, zorder=3)

    # FIX 2 — both reference-line labels anchored LOW (clear of the title),
    # stacked at two heights so they never overlap each other or a whisker.
    tr = ax.get_xaxis_transform()               # x=data, y=axes-fraction
    ax.text(0.903, 0.135, f"풀링 {POOLED:.3f}", transform=tr, ha="right",
            va="bottom", color=POOLED_C, fontsize=8.5, zorder=6)
    ax.text(0.887, 0.02, f"폴드평균 {MEAN_OF_FOLDS:.3f}", transform=tr,
            ha="right", va="bottom", color="black", fontsize=8.5, zorder=6)

    ax.set_title("화재별 LOFO ROC-AUC + 95% 신뢰구간\n"
                 "Per-fire AUC with DeLong 95% CIs "
                 "(all p≪0.001, gangneung p=2.7e-4)",
                 fontsize=11, pad=12)


def right_panel(ax):
    vals = [0.40, 0.09]
    ax.bar([0, 1], vals, width=0.6, color=[BLUE, GREY], zorder=2)
    ax.set_ylim(0.0, 0.5)
    ax.set_yticks(np.arange(0, 0.51, 0.1))
    ax.set_ylabel("연소 면적 IoU", fontsize=10)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["데이터 기반\nData-driven\n(전방 모의)",
                        "물리 기반\nMechanistic\n(Rothermel)"], fontsize=9)
    for x, v in zip([0, 1], vals):
        ax.text(x, v + 0.012, f"{v:.2f}", ha="center", va="bottom",
                color=NAVY_TXT, fontsize=12, fontweight="bold", zorder=4)

    # ≈4× drop arrow (data-driven → mechanistic); lands on the top-left of the
    # mechanistic bar so its head never collides with the "0.09" value label.
    ax.annotate("", xy=(0.80, 0.105), xytext=(0.08, 0.40),
                arrowprops=dict(arrowstyle="-|>", color=RED, lw=2.0,
                                shrinkA=2, shrinkB=2))
    ax.text(0.60, 0.27, "≈ 4배", color=RED, fontsize=13, fontweight="bold",
            ha="left", va="center", zorder=5)

    ax.set_title("연소 면적 IoU\n원거리대(>3km) 폴드평균 AUC 0.925",
                 fontsize=11, pad=12)


def main() -> int:
    ok = _setup_font()
    print("Korean font:", plt.rcParams["font.family"] if ok
          else "NOT FOUND (Hangul may not render)")
    fig, (axL, axR) = plt.subplots(
        1, 2, figsize=(13.2, 5.0), gridspec_kw={"width_ratios": [1.95, 1]},
        constrained_layout=True)
    left_panel(axL)
    right_panel(axR)
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=135, bbox_inches="tight")
    plt.close(fig)
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
