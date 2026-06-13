#!/usr/bin/env python
"""Operator-facing output mockup — illustrative operator / welfare-worker view.

Renders the concrete artifact an operator (복지사·지자체) would see during a
wildfire evacuation: a clean, prioritized **dispatch & delivery table**, one
auto-generated resident **SMS**, and a colour **legend** for the 4-way triage
classes (적시 구조 / 자력 대피 / 용량 지연 / 도달 불가, mirroring the capacity layer).

This is an **illustrative mockup** in the style of the rescue-PoC output —
representative rows on synthetic-and-tagged geometry, NOT a deployed product/UI
and NOT real residents (names are placeholders, ○○○, filled from the operator's
resident registry in a deployment).

Outputs: docs/figures/operator_output.png  +  docs/operator_output_sample.txt

Run:  python scripts/operator_output_demo.py
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FIG = REPO / "docs" / "figures"
TXT = REPO / "docs" / "operator_output_sample.txt"

# ---- palette (the 4-class colours double as the legend) ----
NAVY, INK, MUTED, TINT, RED_NOTE = "#26395a", "#2b2b2b", "#5b6675", "#eef2f7", "#c0392b"
CLASS_COLOR = {
    "self_evac": "#2f5ea4",          # blue  — 자력 대피 가능
    "rescue_in_time": "#2f8b57",     # green — 구조 필요·적시 구조
    "capacity_deferred": "#d4a32e",  # gold  — 구조 필요·용량 지연
    "unreachable": "#b23f39",        # red   — 도달 불가
}

# ---- illustrative dispatch rows (representative; ○○○ = registry placeholder) ----
# (rank, household, class label, assembly/action, surviving road, ETA, class key)
ROWS = [
    (1, "H-118", "구조 필요·적시 구조", "구조대 출동 → 남정 집결지", "군도 12 (생존)", "18분", "rescue_in_time"),
    (2, "H-204", "자력 대피 가능", "도보 안내 SMS 발송", "해안로 (생존)", "—", "self_evac"),
    (3, "H-077", "구조 필요·용량 지연", "대기열(부대 부족)", "임도 3 (생존)", "지연", "capacity_deferred"),
    (4, "H-251", "도달 불가(도로 소실)", "대체 경로 없음 → 별도 대응", "(전 구간 소실)", "—", "unreachable"),
]
HEADERS = ["우선순위", "가구", "분류", "집결지/조치", "생존 도로", "ETA"]
COLX = [40, 170, 330, 620, 1010, 1290, 1460]   # column left edges + right edge (x: 0..1500)

LEGEND = [
    ("self_evac", "자력 대피 가능"),
    ("rescue_in_time", "구조 필요·적시 구조"),
    ("capacity_deferred", "구조 필요·용량 지연"),
    ("unreachable", "도달 불가"),
]

SMS_TITLE = "자동 생성 SMS (H-204 · 자력 대피)"
SMS_BODY = ("[산불 대피 안내] ○○○님, 지금 바로 집을 나와 해안로를 따라 '남정 대피소'로 "
            "이동하세요. 산 쪽·내륙 도로는 위험합니다. 도움이 필요하면 119.")
DISCLAIMER = ("※ 예시(illustrative) 출력 — 합성·태깅된 PoC 데이터 기반이며 "
              "실제 배포 제품/대시보드가 아닙니다.")


def _setup_font():
    from matplotlib import font_manager as fm
    plt.rcParams["axes.unicode_minus"] = False
    for p in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"):
        if os.path.exists(p):
            fm.fontManager.addfont(p)
            plt.rcParams["font.family"] = fm.FontProperties(fname=p).get_name()
            return
    # Fallback to any installed Hangul-capable family (e.g. WenQuanYi).
    available = {f.name for f in fm.fontManager.ttflist}
    for name in ("Noto Sans CJK KR", "NanumGothic", "Malgun Gothic",
                 "AppleGothic", "WenQuanYi Zen Hei", "WenQuanYi Zen Hei Sharp"):
        if name in available:
            plt.rcParams["font.family"] = name
            return


def _wrap(s: str, width: int) -> str:
    out, line = [], ""
    for tok in s.split(" "):
        if line and len(line) + len(tok) + 1 > width:
            out.append(line)
            line = tok
        else:
            line = (line + " " + tok).strip()
    if line:
        out.append(line)
    return "\n".join(out)


def render():
    _setup_font()
    # data coords 1500x750 over a 15x7.5in canvas → 1:1 scale, so squares are square.
    fig = plt.figure(figsize=(15, 7.5), dpi=130)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, 1500)
    ax.set_ylim(750, 0)             # invert y so layout reads top-to-bottom
    ax.axis("off")

    # ---- title ----
    ax.text(40, 34, "운영자(복지사·지자체) 화면 예시 — 우선 출동·전달 목록",
            fontsize=19, fontweight="bold", color=NAVY, va="center")
    ax.text(40, 74, "Operator (welfare worker / local gov) view — "
            "prioritized dispatch & delivery list",
            fontsize=12.5, color=MUTED, va="center")

    # ---- header bar ----
    hy0, hy1 = 120, 168
    ax.add_patch(Rectangle((COLX[0], hy0), COLX[-1] - COLX[0], hy1 - hy0,
                           facecolor=NAVY, edgecolor="none"))
    for j, h in enumerate(HEADERS):
        ax.text(COLX[j] + 18, (hy0 + hy1) / 2, h, fontsize=13, color="white",
                fontweight="bold", va="center", ha="left")

    # ---- data rows ----
    row_h = 90
    for i, (rank, hh, cls, act, road, eta, key) in enumerate(ROWS):
        y0 = hy1 + i * row_h
        yc = y0 + row_h / 2
        if i % 2 == 0:
            ax.add_patch(Rectangle((COLX[0], y0), COLX[-1] - COLX[0], row_h,
                                   facecolor=TINT, edgecolor="none"))
        # priority square with the rank centred inside it (ha/va='center')
        s = 46
        cx = (COLX[0] + COLX[1]) / 2
        ax.add_patch(Rectangle((cx - s / 2, yc - s / 2), s, s,
                               facecolor=CLASS_COLOR[key], edgecolor="none"))
        ax.text(cx, yc, str(rank), fontsize=17, fontweight="bold",
                color="white", ha="center", va="center")
        # remaining cells: left-aligned, vertically centred
        for j, val in ((1, hh), (2, cls), (3, act), (4, road), (5, eta)):
            ax.text(COLX[j] + 18, yc, val, fontsize=12.5, color=INK,
                    ha="left", va="center")
    ty1 = hy1 + len(ROWS) * row_h
    ax.plot([COLX[0], COLX[-1]], [ty1, ty1], color="#d6dbe3", lw=1.0)

    # ---- bottom-left: auto-generated SMS card (green) ----
    bx, by, bw, bh = 40, 560, 660, 150
    ax.add_patch(FancyBboxPatch((bx, by), bw, bh,
                 boxstyle="round,pad=0,rounding_size=14",
                 facecolor="#f5faf6", edgecolor=CLASS_COLOR["rescue_in_time"], lw=2.0))
    ax.text(bx + 24, by + 30, SMS_TITLE, fontsize=13, fontweight="bold",
            color=CLASS_COLOR["rescue_in_time"], va="center")
    ax.text(bx + 24, by + 58, _wrap(SMS_BODY, 30), fontsize=11.5, color=INK,
            va="top", linespacing=1.5)

    # ---- bottom-right: colour legend (orange) ----
    lx, ly, lw_, lh = 760, 560, 700, 150
    ax.add_patch(FancyBboxPatch((lx, ly), lw_, lh,
                 boxstyle="round,pad=0,rounding_size=14",
                 facecolor="#fffaf2", edgecolor="#e08a2e", lw=2.0))
    ax.text(lx + 24, ly + 28, "색상 = 4분류 결과", fontsize=13, fontweight="bold",
            color=NAVY, va="center")
    for k, (key, label) in enumerate(LEGEND):
        sy = ly + 58 + k * 23
        ax.add_patch(Rectangle((lx + 26, sy - 9), 18, 18,
                               facecolor=CLASS_COLOR[key], edgecolor="none"))
        ax.text(lx + 54, sy, label, fontsize=12, color=INK, va="center")

    # ---- disclaimer ----
    ax.text(750, 735, DISCLAIMER, fontsize=11, color=RED_NOTE, ha="center", va="center")

    FIG.mkdir(parents=True, exist_ok=True)
    out = FIG / "operator_output.png"
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print("wrote", out)


def write_text():
    lines = [
        "운영자(복지사·지자체) 화면 예시 — 우선 출동·전달 목록",
        "Operator (welfare worker / local gov) view — prioritized dispatch & delivery list",
        "*** 예시(illustrative) 출력 — 합성·태깅된 PoC 데이터 기반, 실제 주민/배포 제품 아님. ***",
        "",
        f"{'우선':<4} | {'가구':<6} | {'분류':<20} | {'집결지/조치':<26} | {'생존 도로':<14} | ETA",
        "-" * 96,
    ]
    for rank, hh, cls, act, road, eta, _key in ROWS:
        lines.append(f"{rank:<4} | {hh:<6} | {cls:<20} | {act:<26} | {road:<14} | {eta}")
    lines += [
        "",
        f"[자동 생성 SMS · {ROWS[1][1]} · 자력 대피]",
        SMS_BODY,
        "",
        "색상 = 4분류 결과: 자력 대피(파랑) · 적시 구조(초록) · 용량 지연(노랑) · 도달 불가(빨강)",
    ]
    TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", TXT)


def main() -> int:
    render()
    write_text()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
