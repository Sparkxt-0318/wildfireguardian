#!/usr/bin/env python
"""Bilingual (Korean + English) figures for the rescue-aware routing demonstration.

Reads the arrays/metrics produced by ``run_rescue_routing.py`` and writes:

  docs/figures/rescue_map.png            hazard envelope + drive network coloured by
                                         ingress-survival time + refuges (rescue-
                                         reachable vs not) + one responder route +
                                         one resident route + UNREACHABLE homes.
  docs/figures/rescue_four_way.png       the four-way origin split (sums to N) +
                                         resident a/b/c and responder survival-aware
                                         vs shortest-path exposure contrasts.
  docs/figures/rescue_sensitivity.png    how the reachable/unreachable split moves
                                         under the vehicle cutoff, responder ETA
                                         (speed), dispatch delay and time budget.

Run after the integration script:  python scripts/make_rescue_figures.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402
from pyproj import Transformer  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402

PROC = REPO / "data" / "processed"
FIG = REPO / "docs" / "figures"
_TO_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)


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


def _grid_from_extent(ext) -> CoarseGrid:
    minx, miny, maxx, maxy, cell = ext
    ncols = int(round((maxx - minx) / cell))
    nrows = int(round((maxy - miny) / cell))
    return CoarseGrid(minx, miny, maxx, maxy, cell, nrows, ncols)


def _ll(xy):
    xy = np.atleast_2d(np.asarray(xy, float))
    if xy.size == 0:
        return xy.reshape(-1, 2)
    lon, lat = _TO_4326.transform(xy[:, 0], xy[:, 1])
    return np.column_stack([lon, lat])


# ---------------------------------------------------------------------------
# Figure 1 — the rescue map
# ---------------------------------------------------------------------------


def rescue_map(npz, summary):
    g = _grid_from_extent(npz["grid_extent"])
    lon, lat = g.center_lonlat()
    haz = npz["haz_stack"]
    times = npz["haz_times"]
    # A late-but-not-final hazard surface so routes/destinations stay legible.
    k = int(np.clip(int(round(0.6 * (len(times) - 1))), 0, len(times) - 1))

    drive = _ll(npz["drive_xy"])
    surv = npz["drive_survival"]                # -1 == never cut within horizon
    dest = _ll(npz["dest_xy"])
    rr = npz["dest_rescue_reachable"]
    depot = _ll(npz["depot_xy"])
    unreach = _ll(npz["unreachable_xy"])
    ign = _ll(npz["ignition_xy"])[0]

    fig, ax = plt.subplots(figsize=(11, 9), constrained_layout=True)
    ax.pcolormesh(lon, lat, haz[k], cmap="Oranges", vmin=0.0, vmax=1.0,
                  shading="auto", alpha=0.55, zorder=1)

    # Drive network coloured by ingress-survival time (grey = never cut).
    finite = surv >= 0
    sc = ax.scatter(drive[finite, 0], drive[finite, 1], c=surv[finite] / 60.0,
                    cmap="viridis", s=6, zorder=2, vmin=0.0, vmax=float(times[-1]) / 60.0)
    ax.scatter(drive[~finite, 0], drive[~finite, 1], c="0.78", s=4, zorder=1.5)
    cbar = fig.colorbar(sc, ax=ax, fraction=0.035, pad=0.01)
    cbar.set_label("도로 통행 가능 잔여시간 / Ingress-survival time (h)")

    # Destinations: rescue-reachable (green) vs not (red X).
    ax.scatter(dest[rr, 0], dest[rr, 1], s=130, marker="*", c="#10b981",
               edgecolors="black", zorder=5, label="구조 가능 대피소 / rescue-reachable")
    ax.scatter(dest[~rr, 0], dest[~rr, 1], s=120, marker="X", c="#b91c1c",
               edgecolors="black", zorder=5, label="접근로 차단 대피소 / NOT rescue-reachable")
    # Depots, ignition.
    ax.scatter(depot[:, 0], depot[:, 1], s=200, marker="P", c="#2563eb",
               edgecolors="white", zorder=6, label="소방서·119안전센터(합성) / depot")
    ax.scatter([ign[0]], [ign[1]], s=240, marker="*", c="black", zorder=6,
               label="발화점 / ignition")

    # Example responder route (cyan) and resident routes (naive blue / rescue magenta).
    rr_route = _ll(npz["responder_route_xy"])
    if len(rr_route):
        ax.plot(rr_route[:, 0], rr_route[:, 1], "-", color="white", lw=5, zorder=6.8)
        ax.plot(rr_route[:, 0], rr_route[:, 1], "-", color="#06b6d4", lw=2.6, zorder=7,
                label="구조대 차량 경로(생존-인지) / responder route")
    res_n = _ll(npz["resident_naive_xy"])
    res_r = _ll(npz["resident_rescue_xy"])
    if len(res_n):
        ax.plot(res_n[:, 0], res_n[:, 1], "--", color="#1d4ed8", lw=2.0, zorder=7,
                label="주민 순진한 도보 / resident naive walk")
    if len(res_r):
        ax.plot(res_r[:, 0], res_r[:, 1], "-", color="#c026d3", lw=2.4, zorder=7,
                label="주민 미래-인지 도보(구조가능 대피소) / resident → rescue-reachable")

    # Unreachable homes — highlighted (the honesty core).
    if len(unreach):
        ax.scatter(unreach[:, 0], unreach[:, 1], s=160, marker="o",
                   facecolors="none", edgecolors="#dc2626", linewidths=2.2, zorder=8,
                   label="구조 불가 가옥 / UNREACHABLE homes")

    ax.set_xlabel("경도 / Longitude")
    ax.set_ylabel("위도 / Latitude")
    ax.set_xlim(lon.min(), lon.max())
    ax.set_ylim(lat.min(), lat.max())
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    c = summary["four_way_counts"]
    ax.set_title(
        f"영덕 구조-인지 대피 라우팅 (합성 PoC, t+{times[k]/60:.0f}h)  /  Yeongdeok rescue-aware "
        f"evacuation routing (synthetic PoC)\n"
        f"구조가능 대피소 {summary['n_refuges_rescue_reachable']}/{summary['n_refuges']}, "
        f"구조 불가 가옥 {c['no_surviving_vehicle_ingress']}호 / unreachable homes "
        f"(reported, not imputed)",
        fontsize=11)
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / "rescue_map.png", dpi=135, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / "rescue_map.png")


# ---------------------------------------------------------------------------
# Figure 2 — four-way split + exposure contrasts
# ---------------------------------------------------------------------------


def four_way_figure(summary):
    c = summary["four_way_counts"]
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.2), constrained_layout=True)

    # (a) four-way split (must sum to N).
    labels = ["구조가능\n대피소로 구조\nsaved (→RR refuge)",
              "원래 안전\nalready safe",
              "도보 불가·\n구조대 가능\nno walk, rescuer can",
              "차량 접근 불가\nUNREACHABLE"]
    keys = ["saved_by_rescue_reachable_refuge", "already_safe",
            "no_safe_pedestrian_route", "no_surviving_vehicle_ingress"]
    vals = [c[k] for k in keys]
    colors = ["#10b981", "#9ca3af", "#f59e0b", "#dc2626"]
    bars = axes[0].bar(labels, vals, color=colors)
    axes[0].set_ylabel("출발지 수 / number of origins")
    axes[0].set_title(f"4-구분 결과 (합 = N = {sum(vals)}) / four-way split (sums to N)",
                      fontsize=11)
    for b, v in zip(bars, vals):
        axes[0].text(b.get_x() + b.get_width() / 2, v + max(vals) * 0.01, str(v),
                     ha="center", va="bottom", fontsize=10)
    axes[0].tick_params(axis="x", labelsize=8)

    # (b) resident exposure a/b/c.
    rex = summary["resident_exposure"]
    rlabels = ["순진한\nnaive (a)", "미래-인지\n→any safe (b)", "미래-인지\n→RR refuge (c)"]
    rvals = [_mean(rex["naive"]), _mean(rex["future_aware_any"]),
             _mean(rex["future_aware_rescue"])]
    rb = axes[1].bar(rlabels, rvals, color=["#1d4ed8", "#06b6d4", "#c026d3"])
    axes[1].set_ylabel("평균 노출 ∫P·dt (확률·분) / mean exposure (prob·min)")
    axes[1].set_title("주민 경로별 예측 위험 노출 / resident exposure by policy", fontsize=11)
    for b, v in zip(rb, rvals):
        if v is not None:
            axes[1].text(b.get_x() + b.get_width() / 2, v, f"{v:.1f}",
                         ha="center", va="bottom", fontsize=10)
    axes[1].text(0.5, 0.92,
                 f"정책 c가 대피소를 바꾼 출발지: {rex['policy_c_changed_refuge_count']}곳\n"
                 f"policy (c) re-routed {rex['policy_c_changed_refuge_count']} origins off a "
                 f"cut-off refuge",
                 transform=axes[1].transAxes, ha="center", va="top", fontsize=8,
                 color="#6b21a8")

    # (c) responder exposure survival-aware vs shortest-path.
    pe = summary["responder_exposure"]
    pvals = [_mean(pe["survival_aware"]), _mean(pe["shortest_path"])]
    pb = axes[2].bar(["생존-인지\nsurvival-aware", "최단경로\nshortest-path"], pvals,
                     color=["#06b6d4", "#1d4ed8"])
    axes[2].set_ylabel("평균 노출 ∫P·dt / mean exposure (prob·min)")
    axes[2].set_title(f"구조대 차량 경로 노출 / responder ingress exposure\n"
                      f"(출동 {pe['n_dispatch']}건, 구조불가 {pe['n_unreachable']}건 / "
                      f"dispatch {pe['n_dispatch']}, unreachable {pe['n_unreachable']})",
                      fontsize=11)
    for b, v in zip(pb, pvals):
        if v is not None:
            axes[2].text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}",
                         ha="center", va="bottom", fontsize=10)

    fig.suptitle("구조-인지 대피 라우팅: 4-구분 결과와 노출 대조  /  Rescue-aware routing: "
                 "four-way outcome split and exposure contrasts (synthetic 영덕 PoC)",
                 fontsize=12.5)
    fig.savefig(FIG / "rescue_four_way.png", dpi=135, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / "rescue_four_way.png")


# ---------------------------------------------------------------------------
# Figure 3 — sensitivity sweep
# ---------------------------------------------------------------------------


def sensitivity_figure(summary):
    sw = summary["sensitivity_sweep"]
    groups = [("vehicle_cutoff", "차량 통행불가 기준 / vehicle cutoff"),
              ("vehicle_speed_kmh", "차량 속도 km/h / vehicle speed (ETA proxy)"),
              ("responder_dispatch_delay_min", "출동 지연 min / dispatch delay"),
              ("responder_time_budget_min", "시간 예산 min / time budget")]
    fig, axes = plt.subplots(1, 4, figsize=(19, 4.6), constrained_layout=True)
    for ax, (key, title) in zip(axes, groups):
        pts = sw.get(key, {})
        xs = [float(k) for k in pts]
        order = np.argsort(xs)
        xs = [xs[i] for i in order]
        labels = list(pts.keys())
        labels = [labels[i] for i in order]
        saved = [pts[labels[i]]["counts"]["saved_by_rescue_reachable_refuge"] for i in range(len(xs))]
        nowalk = [pts[labels[i]]["counts"]["no_safe_pedestrian_route"] for i in range(len(xs))]
        noing = [pts[labels[i]]["counts"]["no_surviving_vehicle_ingress"] for i in range(len(xs))]
        ax.plot(xs, noing, "-o", color="#dc2626", label="구조불가 / unreachable")
        ax.plot(xs, nowalk, "-s", color="#f59e0b", label="구조대 필요 / needs rescuer")
        ax.plot(xs, saved, "-^", color="#10b981", label="대피소로 구조 / saved")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("출발지 수 / number of origins")
    axes[0].legend(fontsize=8, loc="upper right")
    n_sweep = sw["baseline"]["n_origins"]
    fig.suptitle("민감도 분석: 매개변수에 따른 구조가능/불가 구분의 이동 (이것이 강건한 결과)  /  "
                 f"Sensitivity: how the reachable/unreachable split moves (N={n_sweep} sampled). "
                 "This robustness is the result.",
                 fontsize=12)
    fig.savefig(FIG / "rescue_sensitivity.png", dpi=135, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / "rescue_sensitivity.png")


def _mean(d):
    return d.get("mean") if isinstance(d, dict) else None


def main() -> int:
    npz_path = PROC / "rescue_routing.npz"
    if not npz_path.exists():
        print("missing data/processed/rescue_routing.npz; run run_rescue_routing.py first",
              file=sys.stderr)
        return 2
    ok = _setup_font()
    print("Korean font:", "OK" if ok else "NOT FOUND (Hangul may not render)")
    npz = np.load(npz_path)
    summary = json.loads((PROC / "rescue_routing.json").read_text())
    rescue_map(npz, summary)
    four_way_figure(summary)
    sensitivity_figure(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
