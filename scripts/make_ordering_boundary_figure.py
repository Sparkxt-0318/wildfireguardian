#!/usr/bin/env python
"""The W axis against the win rate of the deadline-first ordering — four arms.

Round-4 PHASE 24. Reads ``data/processed/ordering_boundary.json`` (produced by
``scripts/run_ordering_boundary.py``) and writes

    docs/figures/ordering_boundary.png

⚠ THE FIGURE MUST NOT READ AS 「우리 정렬이 유효하다」. It is a boundary map of a
NEGATIVE result: the committed operating window is marked on every panel, and at
that window the shipped ordering wins nothing. The rising curve to its right is
the condition under which the rule WOULD help, not a claim that the system runs
there — and W = 75 is itself an ASSUMED parameter with no measured basis in this
repository, which the figure states.

⚠ NEW FILENAME. HANDOFF §5 rule 3 forbids regenerating any committed
``docs/figures/*.png``; this writes one that did not exist before and touches no
other file.

Run:  python scripts/make_ordering_boundary_figure.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

SRC = REPO / "data" / "processed" / "ordering_boundary.json"
FIG = REPO / "docs" / "figures" / "ordering_boundary.png"

COMMITTED_W = 75.0

#: report order, matching docs/ordering_boundary.md.
#: ⚠ NO 「⚠」 IN ANY FIGURE STRING — Nanum Gothic has no U+26A0 and matplotlib
#: renders it as tofu. Use 「※」, which every Korean face here carries.
ARM_LABEL = {
    "yeongdeok_2025|synthetic": "영덕 · 합성 포락면   Yeongdeok · synthetic",
    "uljin_samcheok_2022|real": "울진·삼척 · real   Uljin-Samcheok · real",
    "uljin_samcheok_2022|synthetic": "울진·삼척 · 합성   Uljin-Samcheok · synthetic",
    "yeongdeok_2025|real": "영덕 · real   Yeongdeok · real  ※ 가장 약한 마감 신호",
}
ARM_ORDER = list(ARM_LABEL)


def _wnum(w: str) -> float:
    """'W120' -> 120.0 — the artifact keys windows as strings."""
    return float(w[1:])


def _setup_font() -> bool:
    """Prefer Noto Sans CJK KR (per brief), then Nanum, for Korean labels.

    Same intent as ``make_rescue_figures.py::_setup_font``; that one probes Linux
    paths only, so this adds a lookup by REGISTERED FAMILY NAME for the macOS
    workstation, where the same families exist but not at those paths.
    """
    for p in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
              "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
              "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf"):
        if os.path.exists(p):
            fm.fontManager.addfont(p)
            plt.rcParams["font.family"] = fm.FontProperties(fname=p).get_name()
            plt.rcParams["axes.unicode_minus"] = False
            return True
    have = {f.name for f in fm.fontManager.ttflist}
    for name in ("Noto Sans CJK KR", "NanumGothic", "Nanum Gothic",
                 "Apple SD Gothic Neo", "AppleGothic", "Malgun Gothic"):
        if name in have:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False
            return True
    plt.rcParams["axes.unicode_minus"] = False
    return False


def main() -> int:
    if not SRC.exists():
        print(f"missing {SRC}; run scripts/run_ordering_boundary.py first")
        return 2
    d = json.loads(SRC.read_text())
    b = d["boundary"]
    ws = b["windows_min"]
    per_arm = b["by_arm_by_window"]
    pooled = b["pooled_by_window"]
    dstats = d["deadline_statistics_by_arm_and_window"]
    korean = _setup_font()

    fig, axes = plt.subplots(2, 2, figsize=(13.6, 10.8), sharex=True)
    fig.subplots_adjust(left=0.072, right=0.928, top=0.815, bottom=0.185,
                        hspace=0.40, wspace=0.30)

    for ax, arm in zip(axes.ravel(), ARM_ORDER, strict=True):
        rows = per_arm[arm]
        keys = [f"W{w:g}" for w in ws]
        win = [rows[k]["win_rate_pct"] for k in keys]
        loss = [rows[k]["loss_rate_pct"] for k in keys]

        # the committed window, first so the curves draw over it
        ax.axvspan(ws[0], COMMITTED_W, color="#c62828", alpha=0.055, zorder=0)
        ax.axvline(COMMITTED_W, color="#c62828", lw=1.7, ls="--", zorder=1)

        ax.plot(ws, loss, marker="s", ms=4.6, lw=1.7, color="#8d6e63",
                alpha=0.85, zorder=2,
                label="시한 임박 순이 지는 셀  loses")
        ax.plot(ws, win, marker="o", ms=5.6, lw=2.4, color="#1565c0", zorder=3,
                label="시한 임박 순이 이기는 셀  wins")

        # distinct deadlines at delay 30 — the mechanism, on a twin axis
        ax2 = ax.twinx()
        nd = [dstats[arm][k]["d30"]["n_distinct_deadlines"] for k in keys]
        ax2.plot(ws, nd, marker="^", ms=4.2, lw=1.3, ls=":", color="#2e7d32",
                 alpha=0.9, zorder=2, label="서로 다른 마감 수 (지연 30)")
        ax2.set_ylabel("서로 다른 마감 수\ndistinct deadlines (delay 30)",
                       fontsize=8.5, color="#2e7d32")
        ax2.tick_params(axis="y", labelsize=8, colors="#2e7d32")
        ax2.set_ylim(bottom=0)

        first = b["first_window_with_a_win"]["per_arm_min"].get(arm)
        peak = max(win)
        tag = (f"첫 승리 W = {first:g}분 · 최고 승률 {peak:.1f} %  "
               f"(first win / best win rate)" if first is not None
               else "이 축 전체에서 0승  no win anywhere on this axis")
        ax.set_title(f"{ARM_LABEL[arm]}\n{tag}", fontsize=10.0, linespacing=1.6)
        ax.set_ylabel("셀 비율 (%)  share of cells", fontsize=9)
        ax.set_ylim(-3, 103)
        ax.set_xlim(min(ws) - 12, max(ws) + 12)
        ax.grid(alpha=0.25, lw=0.6)
        ax.tick_params(labelsize=8.5)
        ax.set_zorder(ax2.get_zorder() + 1)
        ax.patch.set_visible(False)

    for ax in axes[1]:
        ax.set_xlabel("운용 창 W (분)   operational window W (min)", fontsize=9.5)

    # pooled curve as an annotation on the first panel
    p_first = b["first_window_with_a_win"]["pooled_min"]
    pooled_txt = "  ".join(
        f"{w:g}:{pooled[f'W{w:g}']['deadline_wins']}" for w in ws)

    handles = [
        Line2D([], [], color="#1565c0", marker="o", lw=2.4, ms=5.6,
               label="시한 임박 순이 이기는 셀 비율   win rate"),
        Line2D([], [], color="#8d6e63", marker="s", lw=1.7, ms=4.6,
               label="지는 셀 비율   loss rate"),
        Line2D([], [], color="#2e7d32", marker="^", lw=1.3, ls=":", ms=4.2,
               label="서로 다른 마감 수 (오른쪽 축)   distinct deadlines (right axis)"),
        Line2D([], [], color="#c62828", lw=1.7, ls="--",
               label=f"커밋된 W = {COMMITTED_W:g}분  ※ 가정이며 실측 근거 없음"),
    ]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.895),
               ncol=2, fontsize=9.2, frameon=False, handlelength=2.6,
               columnspacing=2.4, labelspacing=0.55)

    fig.suptitle(
        "시한 임박 순 배차 정렬은 어디서부터 이기기 시작하는가 — 그리고 그 경계는 "
        "운용 창에서 얼마나 먼가\n"
        "Where deadline-first dispatch ordering starts to win, and how far that is "
        "from the operating window",
        fontsize=12.8, y=0.978, linespacing=1.55)

    # ⚠ the loss rate quoted is the one over the WINNING half of the axis, and
    # it is compared against the committed window — the honest contrast is
    # "past the boundary the rule loses MORE often, not less".
    best = max(t["win_rate_pct"] for t in pooled.values())
    past = [t["loss_rate_pct"] for w, t in pooled.items()
            if p_first is not None and _wnum(w) >= p_first]
    lo, hi = (min(past), max(past)) if past else (0.0, 0.0)
    at_committed = pooled[f"W{COMMITTED_W:g}"]["loss_rate_pct"]
    foot = (
        f"※ 커밋된 W = {COMMITTED_W:g}분에서는 네 팔 전부 0승입니다 (180개 셀 중 0승). "
        f"전체 합산 첫 승리는 W = {p_first:g}분 — 커밋 값의 {p_first / COMMITTED_W:.1f}배.  "
        f"W별 승리 셀 수(전체 180개 중): {pooled_txt}\n"
        if p_first is not None else
        f"※ 커밋된 W = {COMMITTED_W:g}분에서는 네 팔 전부 0승입니다\n")
    foot += (
        f"※ 경계를 넘어도 이 규칙이 좋아지지는 않습니다. 승률은 W = 600분에서도 "
        f"{best:.1f} % 에 그치고, 승리가 나타나는 구간의 패배율은 {lo:.1f}–{hi:.1f} % "
        f"로 커밋된 창({at_committed:.1f} %)보다 오히려 높으며, 평균 차이는 12개 W "
        f"전부에서 음수입니다.\n"
        "이 그림은 「이 정렬이 유효하다」가 아니라 「무효인 이유의 정량적 경계」입니다. "
        "유효한 조건이 존재한다는 것과 현재 조건이 그 조건이라는 것은 다른 진술이고, "
        "커밋된 창은 그 조건이 아닙니다.\n"
        "This maps the boundary of a NEGATIVE result. A window at which the rule would "
        "help is not evidence the system runs at that window; W = 75 is an ASSUMED "
        "parameter (config/default.yaml:365, marked ASSUMED) with no measured basis in "
        "this repository.\n"
        "영덕 수치는 drift arm B (441/174/32/142), 커밋된 439 계열이 아닙니다 · "
        "점유 규칙 (나) depot_return · 서비스·지연·팀수 전 축 집계 (팔당 45셀/W) · "
        "scripts/run_ordering_boundary.py")
    fig.text(0.5, 0.011, foot, ha="center", va="bottom", fontsize=7.9,
             linespacing=1.72, color="#333333")

    FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG, dpi=200, facecolor="white")
    plt.close(fig)
    print(f"wrote {FIG}  (korean font: {'yes' if korean else 'FALLBACK — labels may tofu'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
