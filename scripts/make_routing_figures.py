#!/usr/bin/env python
"""Bilingual (Korean + English) figures for the routing-spine demonstration.

Reads the arrays/metrics produced by ``run_routing_integration.py`` and writes:

  docs/figures/routing_hazard_sequence.png   growing hazard envelope over time
                                             with naive (into hazard) vs
                                             future-aware (detour) routes.
  docs/figures/routing_exposure_comparison.png  exposure / hazard-along-route.
  docs/figures/spread_v2_findings.png        permutation importance (severity
                                             vs wind direction), drift, growth.

Run after the integration script:  python scripts/make_routing_figures.py
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
from matplotlib.lines import Line2D  # noqa: E402
from pyproj import Transformer  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402
from wildfireguardian.spread_v2.features import FEATURE_COLUMNS, SEVERITY_FEATURES  # noqa: E402

PROC = REPO / "data" / "processed"
FIG = REPO / "docs" / "figures"
_TO_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)


def _setup_font() -> bool:
    for p in ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
              "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf"):
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
    xy = np.atleast_2d(xy)
    lon, lat = _TO_4326.transform(xy[:, 0], xy[:, 1])
    return np.column_stack([lon, lat])


def hazard_sequence_figure(npz, fwd):
    g = _grid_from_extent(npz["grid_extent"])
    lon, lat = g.center_lonlat()
    haz_times = npz["haz_times"]
    haz_stack = npz["haz_stack"]
    obs_times = npz["obs_times"]
    obs_stack = npz["obs_stack"]
    ign = _ll(npz["ign_xy"])[0]
    shelters = _ll(npz["shelters_xy"])
    naive = _ll(npz["naive_xy"])
    fa = _ll(npz["fa_xy"])
    origin = _ll(npz["origin_xy"])[0]

    # Pick up to 4 step indices spanning the horizon.
    idxs = np.unique(np.linspace(0, len(haz_times) - 1, 4).round().astype(int))
    fig, axes = plt.subplots(1, len(idxs), figsize=(5.2 * len(idxs), 5.4), constrained_layout=True)
    if len(idxs) == 1:
        axes = [axes]
    mesh = None
    for ax, k in zip(axes, idxs):
        mesh = ax.pcolormesh(lon, lat, haz_stack[k], cmap="YlOrRd", vmin=0.0, vmax=1.0, shading="auto")
        # observed footprint nearest this step (drift overlay)
        j = int(np.argmin(np.abs(obs_times - haz_times[k])))
        ax.contour(lon, lat, obs_stack[j].astype(float), levels=[0.5],
                   colors="black", linewidths=1.1, linestyles="--")
        # White casing under each route so they read on any background.
        for xy, col in ((naive, "#1d4ed8"), (fa, "#06e0ff")):
            ax.plot(xy[:, 0], xy[:, 1], "-", color="white", lw=4.2, zorder=3.8)
            ax.plot(xy[:, 0], xy[:, 1], "-", color=col, lw=2.4, zorder=4)
        ax.scatter(shelters[:, 0], shelters[:, 1], s=8, c="#10b981", marker="s", alpha=0.5, zorder=3)
        ax.scatter([ign[0]], [ign[1]], s=130, marker="*", c="black", zorder=5)
        ax.scatter([origin[0]], [origin[1]], s=70, marker="o", c="white",
                   edgecolors="black", zorder=5)
        hh = haz_times[k] / 60.0
        ax.set_title(f"t + {hh:.0f} h", fontsize=12)
        ax.set_xlabel("경도 / Longitude")
        ax.set_xlim(lon.min(), lon.max())
        ax.set_ylim(lat.min(), lat.max())
        ax.tick_params(labelsize=8)
    axes[0].set_ylabel("위도 / Latitude")

    cbar = fig.colorbar(mesh, ax=axes, fraction=0.025, pad=0.01)
    cbar.set_label("예측 발화 확률 P / Predicted ignition probability")

    legend_handles = [
        Line2D([0], [0], color="#1d4ed8", lw=2.6, label="순진한 경로 (최근접) / Naive (nearest)"),
        Line2D([0], [0], color="#06e0ff", lw=2.6, label="미래-인지 경로 / Future-aware"),
        Line2D([0], [0], ls="--", color="black", lw=1.2, label="실제 관측 화선 / Observed FIRMS footprint"),
        Line2D([0], [0], marker="*", color="black", lw=0, markersize=12, label="발화점 / Ignition"),
        Line2D([0], [0], marker="o", color="white", markeredgecolor="black", lw=0, label="대피 출발지(고령자) / Origin (elderly)"),
        Line2D([0], [0], marker="s", color="#10b981", lw=0, label="안전 목적지·해안 / Safe dest. (coast)"),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=3, fontsize=9,
               bbox_to_anchor=(0.5, -0.10))
    fig.suptitle(
        "영덕 2025 산불: 성장하는 예측 위험 영역 vs 대피 경로  /  "
        "Yeongdeok 2025: growing PREDICTED hazard envelope vs evacuation routes\n"
        "(위험은 풍향이 아닌 화재기상 강도로 결정되는 넓은 도달 영역  /  "
        "hazard is a broad severity-scaled reach, not a wind-direction jet)",
        fontsize=12.5)
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / "routing_hazard_sequence.png", dpi=135, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / "routing_hazard_sequence.png")


def exposure_figure(npz, demo):
    h = demo["headline"]
    nv, fa = h["naive"], h["future_aware"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)

    # Left: exposure + max-hazard bars.
    labels = ["순진한\nNaive", "미래-인지\nFuture-aware"]
    expo = [nv["exposure"], fa["exposure"]]
    bars = ax1.bar(labels, expo, color=["#1d4ed8", "#06b6d4"])
    ax1.set_ylim(0, max(expo) * 1.28)
    ax1.set_ylabel("누적 노출 ∫P·dt (확률·분) / Cumulative exposure (prob·min)")
    ax1.set_title("경로별 예측 위험 노출 / Exposure to predicted hazard")
    for b, v, mh, en in zip(bars, expo, [nv["max_hazard"], fa["max_hazard"]],
                            [nv["enters_hazard"], fa["enters_hazard"]]):
        ax1.text(b.get_x() + b.get_width() / 2, v + max(expo) * 0.015,
                 f"max P={mh:.2f}\n{'위험 진입 enters!' if en else '회피 avoids'}",
                 ha="center", va="bottom", fontsize=9,
                 color=("#b91c1c" if en else "#065f46"))
    if nv["exposure"] > 0:
        red = 100.0 * (nv["exposure"] - fa["exposure"]) / nv["exposure"]
        ax1.annotate(f"노출 {red:.0f}% 감소\n{red:.0f}% lower",
                     xy=(1, fa["exposure"]), xytext=(0.5, max(expo) * 0.6),
                     ha="center", fontsize=11, color="#065f46",
                     arrowprops=dict(arrowstyle="->", color="#065f46"))

    # Right: hazard along each route vs clock time.
    ax2.plot(npz["naive_arrivals"] / 60.0, npz["naive_node_haz"], "-o", ms=3,
             color="#1f4ed8", label="순진한 / Naive")
    ax2.plot(npz["fa_arrivals"] / 60.0, npz["fa_node_haz"], "-o", ms=3,
             color="#06b6d4", label="미래-인지 / Future-aware")
    ax2.axhline(0.5, ls="--", color="red", lw=1, label="통행 불가 기준 p_cut=0.5 / impassable cutoff")
    ax2.set_xlabel("출발 후 경과 시간 (시간) / Hours since departure")
    ax2.set_ylabel("그 지점·시각의 발화 확률 / Ignition prob. at node on arrival")
    ax2.set_title("경로를 따라가며 마주치는 위험 / Hazard encountered along route")
    ax2.legend(fontsize=9)
    ax2.set_ylim(-0.02, 1.02)

    fig.suptitle("순진한 vs 미래-인지 대피 경로 노출 비교 / Naive vs future-aware exposure",
                 fontsize=13)
    fig.savefig(FIG / "routing_exposure_comparison.png", dpi=135, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / "routing_exposure_comparison.png")


def findings_figure(lofo, fwd):
    imp = lofo["permutation_importance"]
    fig, axes = plt.subplots(1, 3, figsize=(17, 5.4), constrained_layout=True)

    # (a) permutation importance, severity vs direction colour-coded.
    names = list(imp.keys())
    vals = [imp[n] for n in names]
    colors = []
    for n in names:
        if n in SEVERITY_FEATURES:
            colors.append("#dc2626")            # severity = red
        elif n == "wind_alignment":
            colors.append("#2563eb")            # wind DIRECTION = blue
        else:
            colors.append("#9ca3af")            # geometry/terrain = grey
    order = np.argsort(vals)
    axes[0].barh([names[i] for i in order], [vals[i] for i in order],
                 color=[colors[i] for i in order])
    axes[0].set_title("순열 중요도 (LOFO) / Permutation importance\n"
                      "빨강=기상 강도, 파랑=풍향 / red=severity, blue=wind direction", fontsize=10.5)
    axes[0].set_xlabel("AUC 하락 / AUC drop when permuted")

    # (b) drift vs observed (IoU + captured) over time.
    steps = [d["minutes"] / 60.0 for d in fwd["drift"]]
    iou = [d["iou"] for d in fwd["drift"]]
    cap = [d["captured_frac"] for d in fwd["drift"]]
    axes[1].plot(steps, iou, "-o", color="#dc2626", label="IoU (vs 관측/observed)")
    axes[1].plot(steps, cap, "-s", color="#16a34a", label="포착률 captured frac")
    axes[1].set_ylim(0, 1.02)
    axes[1].set_xlabel("순방향 모의 시간 (시간) / Forward-sim hours")
    axes[1].set_title("복합 오차: 예측 위험의 관측 대비 표류\n"
                      "Compounding error: drift vs observed", fontsize=10.5)
    axes[1].legend(fontsize=9)

    # (c) envelope area + breadth growth.
    area = fwd["envelope_area_ha"]
    breadth = fwd["envelope_breadth_deg"]
    ax3 = axes[2]
    ax3.plot(steps, area, "-o", color="#b45309", label="위험 면적 ha / hazard area")
    ax3.set_xlabel("순방향 모의 시간 (시간) / Forward-sim hours")
    ax3.set_ylabel("위험 영역 면적 (ha) / envelope area")
    ax3b = ax3.twinx()
    ax3b.plot(steps, breadth, "-^", color="#7c3aed", label="각폭 deg / breadth")
    ax3b.set_ylabel("도달 영역 각폭 (도) / envelope breadth (deg)")
    ax3.set_title("넓고 성장하는 도달 영역 / Broad, growing reach", fontsize=10.5)
    lines = ax3.get_lines() + ax3b.get_lines()
    ax3.legend(lines, [ln.get_label() for ln in lines], fontsize=8, loc="lower right")

    fig.suptitle("spread_v2: 원거리 예측력은 풍향이 아닌 화재기상 강도에서 나온다  /  "
                 "far-field skill comes from fire-weather severity, not wind direction",
                 fontsize=12.5)
    fig.savefig(FIG / "spread_v2_findings.png", dpi=135, bbox_inches="tight")
    plt.close(fig)
    print("wrote", FIG / "spread_v2_findings.png")


def main() -> int:
    npz_path = PROC / "routing_demo.npz"
    if not npz_path.exists():
        print("missing data/processed/routing_demo.npz; run run_routing_integration.py first",
              file=sys.stderr)
        return 2
    ok = _setup_font()
    print("Korean font:", "NanumGothic" if ok else "NOT FOUND (labels may not render Hangul)")
    npz = np.load(npz_path)
    demo = json.loads((PROC / "routing_demo.json").read_text())
    lofo = json.loads((PROC / "spread_v2_lofo.json").read_text())
    fwd = json.loads((PROC / "yeongdeok_forward_sim.json").read_text())
    hazard_sequence_figure(npz, fwd)
    exposure_figure(npz, demo)
    findings_figure(lofo, fwd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
