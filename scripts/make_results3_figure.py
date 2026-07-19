#!/usr/bin/env python
"""결과-3 summary figure for the 작품설명서 (Korea Code Fair project description):
self-evacuable vs needs-rescuer, and the dispatch-delay -> beyond-reach curve.

READ-ONLY on already-committed results: this script does not import or call the
routing/spread pipeline and does not recompute anything. It only reads the two
committed verification JSONs and plots the numbers that are already in them:

  data/processed/rescue_verify_fc.json   baseline four-way split / self_evacuable /
                                          needs_rescuer @ (immobile_fraction=0.30,
                                          walk_cutoff=0.50) -- the headline cell.
  data/processed/rescue_verify.json      dispatch-delay x vehicle-cutoff grid; the
                                          cutoff=0.7 column is the beyond-reach curve.

Output: docs/figures/rescue_results3_summary.png (bilingual Korean/English, styled
to match the other docs/figures/rescue_*.png figures).

Run:  python scripts/make_results3_figure.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
PROC = REPO / "data" / "processed"
FIG = REPO / "docs" / "figures"

BASELINE_CUTOFF = 0.7
DELAYS = [0.0, 15.0, 30.0, 45.0, 60.0]
BASELINE_DELAY = 30.0
BASELINE_F = 0.30
BASELINE_WALKCUT = 0.50


def _setup_font() -> bool:
    """Prefer Noto Sans CJK KR (per brief), then Nanum, for Korean labels."""
    for p in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
              "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
              "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
              "/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf"):
        if os.path.exists(p):
            fm.fontManager.addfont(p)
            plt.rcParams["font.family"] = fm.FontProperties(fname=p).get_name()
            plt.rcParams["axes.unicode_minus"] = False
            return True
    plt.rcParams["axes.unicode_minus"] = False
    return False


def _source_banner(sources: dict) -> str:
    """Bilingual, data-driven banner from the committed provenance `sources` map
    (never hand-typed) -- mirrors make_rescue_figures.py::_real_or_syn."""
    real = {k for k, v in sources.items() if v in ("osm", "real")}
    if real and sources.get("hazard") == "synthetic":
        return ("도로·대피소·소방서: 실제 OSM  |  화재위험·지형: 합성 (FIRMS 번들 대기)  /  "
                "roads·refuges·depots: REAL OSM;  fire hazard + terrain: "
                "SYNTHETIC (pending FIRMS bundle)")
    if not real:
        return "전 입력 합성 (오프라인 폴백)  /  all inputs synthetic (offline fallback)"
    return "입력별 출처는 provenance 참조  /  see provenance for per-input source"


def main() -> int:
    fc_path = PROC / "rescue_verify_fc.json"
    v_path = PROC / "rescue_verify.json"
    if not fc_path.exists() or not v_path.exists():
        print(f"missing {fc_path} or {v_path}; nothing to plot", )
        return 2

    fc = json.loads(fc_path.read_text())
    v = json.loads(v_path.read_text())

    ok = _setup_font()
    print("Korean font:", "OK" if ok else "NOT FOUND (Hangul may not render)")

    # ---- panel A data: baseline four-way -> self-evacuable vs needs-rescuer ----
    N = fc["n_origins"]
    base_key = f"{BASELINE_F:.2f}|{BASELINE_WALKCUT:.2f}"
    base_cell = fc["grid"][base_key]
    self_evac = base_cell["self_evacuable"]
    needs_resc = base_cell["needs_rescuer"]
    assert self_evac + needs_resc == N, "self_evacuable + needs_rescuer must sum to N"
    needs_pct = fc["needs_rescuer"]["baseline_pct"]

    # ---- panel B data: dispatch-delay -> unreachable ("beyond reach"), cutoff 0.7 ----
    grid = v["grid"]
    unreach = [grid[f"{d:.0f}|{BASELINE_CUTOFF:.2f}"]["no_surviving_vehicle_ingress"]
               for d in DELAYS]
    n_dispatch = v["headline_four_way"]["no_safe_pedestrian_route"]

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.4), constrained_layout=True)

    # Panel A -- self-evacuable vs needs-rescuer.
    ax = axes[0]
    labels = [f"자력 대피 가능\nself-evacuable", f"구조 필요\nneeds rescuer\n({needs_pct:.0f}%)"]
    vals = [self_evac, needs_resc]
    bars = ax.bar(labels, vals, color=["#10b981", "#dc2626"], width=0.55)
    for b, val in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, val + N * 0.012, str(val),
                 ha="center", va="bottom", fontsize=13, fontweight="bold")
    ax.set_ylabel("출발지 수 / number of origins")
    ax.set_ylim(0, N * 1.12)
    ax.set_title(f"자력대피 vs 구조필요 (합 = N = {N})\nself-evacuable vs needs-rescuer "
                 f"(sums to N = {N})", fontsize=11)

    # Panel B -- dispatch delay vs beyond-reach (unreachable) curve, cutoff 0.7.
    axb = axes[1]
    axb.plot(DELAYS, unreach, "-o", color="#dc2626", lw=2.4, markersize=7,
              label="구조 사각지대 / beyond reach (unreachable)")
    for d, u in zip(DELAYS, unreach):
        axb.annotate(str(u), (d, u), textcoords="offset points", xytext=(0, 8),
                     ha="center", fontsize=10)
    bi = DELAYS.index(BASELINE_DELAY)
    axb.scatter([BASELINE_DELAY], [unreach[bi]], s=140, facecolors="none",
                edgecolors="#2563eb", linewidths=2.2, zorder=5,
                label=f"기준선 {BASELINE_DELAY:.0f}분 / baseline {BASELINE_DELAY:.0f} min")
    axb.set_xlabel("출동 지연 (분) / dispatch delay (min)")
    axb.set_ylabel("도달 불가 출발지 수 / unreachable origins (beyond reach)")
    axb.set_title(f"출동 지연에 따른 도달 불가 증가 (차량 통행불가 기준 {BASELINE_CUTOFF})\n"
                  f"unreachable vs dispatch delay (vehicle cutoff {BASELINE_CUTOFF}; "
                  f"dispatch pool n={n_dispatch})", fontsize=11)
    axb.set_xticks(DELAYS)
    axb.grid(alpha=0.3)
    axb.legend(fontsize=8, loc="upper left")

    banner = _source_banner(fc.get("sources", {}))
    fig.suptitle(
        "설명서 결과-3: 자력대피/구조필요 구분과 출동지연 민감도 (영덕, 실도로망)  /  "
        "Results-3: self-evac/needs-rescuer split and dispatch-delay sensitivity "
        "(Yeongdeok, real roads)\n" + banner,
        fontsize=11.5)

    FIG.mkdir(parents=True, exist_ok=True)
    outpath = FIG / "rescue_results3_summary.png"
    fig.savefig(outpath, dpi=135, bbox_inches="tight")
    plt.close(fig)
    print("wrote", outpath)
    print(f"  self_evacuable={self_evac} needs_rescuer={needs_resc} ({needs_pct:.1f}%) N={N}")
    print(f"  unreachable @ cutoff {BASELINE_CUTOFF}, delay {DELAYS}: {unreach}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
