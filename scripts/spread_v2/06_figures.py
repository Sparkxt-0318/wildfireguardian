#!/usr/bin/env python3
# =============================================================================
# LEGACY / SUPERSEDED — research history, NOT part of the live pipeline.
#
# This "Deliverable 0-6" script belongs to the abandoned `spread_v2_xgb`
# forbidden-ok: XGBoost
# (XGBoost) re-train track and imports `wildfireguardian.spread_v2_xgb`. The
# CANONICAL data-driven spread model is the `spread_v2` package
# (src/wildfireguardian/spread_v2/), exercised end-to-end by
# scripts/run_routing_integration.py and scripts/calibration_metrics.py. Kept
# for provenance only — do NOT run it as part of reproduction. See the README
# research log: "spread_v2_xgb — superseded XGBoost re-train (legacy)".
# =============================================================================
"""Deliverable 6 — bilingual (한국어/English) figures for the v2 re-train.

Generates into docs/figures/:
  spread_v2_audit.png         — data-fix audit (uljin positives, orientation
                                diagnostic, gangneung_donghae burnable coverage)
  spread_v2_lofo_auc.png      — per-fire ROC-AUC + conditional AUC by band
  spread_v2_comparison.png    — model comparison + weather severity/direction
  spread_v2_importance.png    — LOFO permutation importance by feature group
  spread_v2_footprint.png     — predicted vs observed footprint (uljin)

Run:  .venv/bin/python scripts/spread_v2/06_figures.py
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from wildfireguardian.spread_v2_xgb import SEED  # noqa: E402
from wildfireguardian.spread_v2_xgb.dataset import get_fire  # noqa: E402
from wildfireguardian.spread_v2_xgb.detections import (  # noqa: E402
    build_observed_sequence, load_detections,
)
from wildfireguardian.spread_v2_xgb.features import ALL_FEATURES  # noqa: E402
from wildfireguardian.spread_v2_xgb.grid import Grid, build_region  # noqa: E402
from wildfireguardian.spread_v2_xgb.model import BANDS, feature_group, lofo_predict  # noqa: E402

plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 130

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed" / "spread_v2"
FIGS = ROOT / "docs" / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

GROUP_COLOR = {
    "weather": "#1f77b4", "intensity/proximity": "#d62728",
    "fuel": "#2ca02c", "terrain": "#9467bd", "v1_proxy": "#ff7f0e",
}


def _load(name):
    return json.loads((PROC / name).read_text())


def fig_audit():
    audit = _load("audit.json")["fires"]
    by = {r["fire_id"]: r for r in audit if "error" not in r}
    usable = _load("class_balance.json")["per_fire"]

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))
    # Panel A — positives per usable fire
    fids = [b["fire_id"] for b in usable]
    pos = [b["positives"] for b in usable]
    colors = ["#d62728" if f == "uljin_samcheok_2022" else "#4c72b0" for f in fids]
    ax[0].barh(range(len(fids)), pos, color=colors)
    ax[0].set_yticks(range(len(fids)))
    ax[0].set_yticklabels([f.replace("_", "\n") for f in fids], fontsize=8)
    for i, p in enumerate(pos):
        ax[0].text(p + 10, i, str(p), va="center", fontsize=8)
    ax[0].set_xlabel("양성 셀 수 / positive cells")
    ax[0].set_title("화재별 양성(점화) 셀\nPositive (ignition) cells per fire")
    ax[0].invert_yaxis()

    # Panel B — uljin orientation diagnostic
    labels = ["이전 버그\nprior (bug)", "게이트 뒤집기\nflipped gate", "수정됨\ncorrected"]
    vals = [120, 615, 915]
    bcol = ["#999999", "#dd8452", "#d62728"]
    ax[1].bar(labels, vals, color=bcol)
    for i, v in enumerate(vals):
        ax[1].text(i, v + 12, str(v), ha="center", fontsize=10, fontweight="bold")
    ax[1].set_ylabel("울진 양성 셀 / uljin positives")
    ax[1].set_title("방향 버그 진단 (울진)\nOrientation-bug diagnostic (uljin)")
    ax[1].axhline(880, ls="--", c="k", lw=0.8)
    ax[1].text(0.02, 890, "목표 target ≈ 880", fontsize=8)

    # Panel C — gangneung_donghae burnable coverage
    g = by["gangneung_donghae_2022"]
    ax[2].bar(["이전\nprior", "수정됨\ncorrected"], [0.05, g["mean_burnable_frac"]],
              color=["#999999", "#2ca02c"])
    ax[2].text(0, 0.07, "~0.05", ha="center", fontsize=10)
    ax[2].text(1, g["mean_burnable_frac"] + 0.02, f"{g['mean_burnable_frac']:.2f}",
               ha="center", fontsize=10, fontweight="bold")
    ax[2].set_ylim(0, 0.85)
    ax[2].set_ylabel("연소가능 비율 / burnable fraction")
    ax[2].set_title("강릉·동해 연료 피복 복구\nGangneung-Donghae fuel coverage fix")

    fig.suptitle("Deliverable 0 — 데이터 수정 감사 / Data-correction audit",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIGS / "spread_v2_audit.png", bbox_inches="tight")
    plt.close(fig)


def fig_lofo(oof):
    lofo = _load("lofo_metrics.json")
    comp = _load("comparison_metrics.json")["results"]["A_full_usable"]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))

    pf = sorted(lofo["summary"]["per_fire"], key=lambda r: r["roc_auc"])
    fids = [r["fire_id"] for r in pf]
    aucs = [r["roc_auc"] for r in pf]
    ax[0].barh(range(len(fids)), aucs, color="#4c72b0")
    ax[0].set_yticks(range(len(fids)))
    ax[0].set_yticklabels([f.replace("_", "\n") for f in fids], fontsize=8)
    for i, a in enumerate(aucs):
        ax[0].text(a - 0.02, i, f"{a:.3f}", va="center", ha="right",
                   color="white", fontsize=8, fontweight="bold")
    # Pooled + fold-mean reference lines shown via a legend rather than inline
    # ax.text() labels: the inline labels otherwise collide with each other, the
    # x-axis "0.9" tick and the title. Legend sits inside the axes (lower-right,
    # an empty region given the ascending sort) so nothing is drawn over the title.
    fold_mean = float(np.mean(aucs))
    pooled = lofo["summary"]["overall_pooled_roc_auc"]
    l1 = ax[0].axvline(fold_mean, ls="--", c="k", lw=1.3,
                       label=f"폴드 평균  {fold_mean:.3f}")
    l2 = ax[0].axvline(pooled, ls=":", c="0.45", lw=1.3,
                       label=f"pooled  {pooled:.3f}")
    ax[0].legend(handles=[l1, l2], loc="lower right", fontsize=8,
                 frameon=True, framealpha=0.92, borderpad=0.5)
    ax[0].set_xlim(0.5, 1.0)
    ax[0].set_xlabel("ROC-AUC (LOFO)")
    ax[0].set_title("화재별 LOFO ROC-AUC\nPer-fire leave-one-fire-out AUC")

    x = np.arange(len(BANDS))
    w = 0.27
    for i, (mname, lab, col) in enumerate([
        ("distance_only", "거리만 / distance-only", "#bbbbbb"),
        ("no_weather", "기상 제외 / no-weather", "#dd8452"),
        ("with_weather", "기상 포함 / with-weather", "#4c72b0"),
    ]):
        ba = [comp[mname]["band_auc"][b] for b in BANDS]
        ax[1].bar(x + (i - 1) * w, ba, w, label=lab, color=col)
    ax[1].axhline(0.5, ls=":", c="k", lw=0.8)
    ax[1].set_xticks(x)
    ax[1].set_xticklabels(["0–375", "375–750", "750–1500", ">1500"])
    ax[1].set_xlabel("점화원까지 거리(m) / distance to fire (m)")
    ax[1].set_ylabel("조건부 ROC-AUC / conditional AUC")
    ax[1].set_ylim(0.4, 0.9)
    ax[1].legend(fontsize=8, loc="lower left")
    ax[1].set_title("거리대별 조건부 AUC\nConditional AUC by distance band")

    fig.suptitle("Deliverable 3 — LOFO 교차검증 / cross-validation",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(FIGS / "spread_v2_lofo_auc.png", bbox_inches="tight")
    plt.close(fig)


def fig_comparison():
    comp = _load("comparison_metrics.json")["results"]
    dec = _load("weather_decomposition.json")
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))

    sets = ["distance_only", "no_weather", "with_weather"]
    labs = ["거리만\ndistance", "기상제외\nno-weather", "기상포함\nwith-weather"]
    overall = [comp["A_full_usable"][s]["overall_pooled_roc_auc"] for s in sets]
    far = [comp["A_full_usable"][s]["band_auc"][">1500"] for s in sets]
    x = np.arange(len(sets))
    ax[0].bar(x - 0.2, overall, 0.4, label="전체 / overall", color="#4c72b0")
    ax[0].bar(x + 0.2, far, 0.4, label="원거리대 >1500m / far-band", color="#c44e52")
    ax[0].axhline(0.781, ls="--", c="#4c72b0", lw=0.8)
    ax[0].axhline(0.66, ls="--", c="#c44e52", lw=0.8)
    ax[0].text(-0.45, 0.787, "이전 prior 0.781", fontsize=7, color="#4c72b0", ha="left")
    ax[0].text(-0.45, 0.668, "이전 far 0.63–0.66", fontsize=7, color="#c44e52", ha="left")
    ax[0].set_xticks(x); ax[0].set_xticklabels(labs)
    ax[0].set_ylim(0.4, 0.9); ax[0].legend(fontsize=8, loc="upper left")
    ax[0].set_ylabel("ROC-AUC")
    ax[0].set_title("모델 비교 (전체 6 화재)\nModel comparison (full set)")

    r = dec["results"]
    dsets = ["no_weather", "no_wx_plus_severity", "no_wx_plus_direction", "with_weather_all"]
    dlabs = ["기상제외\nno-wx", "+심각도\n+severity", "+풍향\n+direction", "+전체\n+all"]
    dfar = [r[s]["band_auc"][">1500"] for s in dsets]
    cols = ["#dd8452", "#55a868", "#8172b3", "#4c72b0"]
    ax[1].bar(range(4), dfar, color=cols)
    for i, v in enumerate(dfar):
        ax[1].text(i, v + 0.01, f"{v:.3f}", ha="center", fontsize=9, fontweight="bold")
    ax[1].set_xticks(range(4)); ax[1].set_xticklabels(dlabs)
    ax[1].set_ylim(0.4, 0.9)
    ax[1].set_ylabel("원거리대 AUC / far-band AUC (>1500m)")
    ax[1].set_title("원거리 기상효과 분해: 심각도 vs 풍향\nFar-band weather: severity vs direction")

    fig.suptitle("Deliverable 4 — 실제 바람이 도움이 되는가? / Does real wind help?",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(FIGS / "spread_v2_comparison.png", bbox_inches="tight")
    plt.close(fig)


def fig_importance():
    imp = _load("importance_metrics.json")
    perm = pd.DataFrame(imp["permutation_importance"]).sort_values("auc_drop_mean")
    fig, ax = plt.subplots(figsize=(9, 7))
    colors = [GROUP_COLOR[feature_group(f)] for f in perm["feature"]]
    ax.barh(range(len(perm)), perm["auc_drop_mean"], xerr=perm["auc_drop_std"],
            color=colors, error_kw=dict(lw=0.7))
    ax.set_yticks(range(len(perm)))
    ax.set_yticklabels(perm["feature"], fontsize=9)
    ax.set_xlabel("풀링 AUC 감소 (셔플 시) / pooled-AUC drop when shuffled")
    ax.axvline(0, c="k", lw=0.6)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in GROUP_COLOR.values()]
    ax.legend(handles, list(GROUP_COLOR), fontsize=8, loc="lower right",
              title="feature group")
    ax.set_title("Deliverable 5 — LOFO 순열 중요도 / permutation importance\n"
                 "days_since_rain 지배적; wind_alignment ≈ v1_alignment ≈ 0",
                 fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGS / "spread_v2_importance.png", bbox_inches="tight")
    plt.close(fig)


def fig_footprint(oof, fire_id="uljin_samcheok_2022"):
    fire = get_fire(fire_id)
    grid = Grid(build_region(fire))
    seq = build_observed_sequence(fire_id, load_detections(fire.detections_csv), grid)
    observed = seq.final_mask()
    seed_mask = seq.cumulative[0]

    g = oof[oof["fire_id"] == fire_id]
    n_pos = int(g["label"].sum())
    gg = g.groupby(["row", "col"])["oof_pred"].max().reset_index().sort_values(
        "oof_pred", ascending=False).head(n_pos)
    pred = seed_mask.copy()
    pred[gg["row"].to_numpy(), gg["col"].to_numpy()] = True

    tp = pred & observed
    fn = observed & ~pred
    fp = pred & ~observed
    iou = tp.sum() / np.logical_or(pred, observed).sum()

    img = np.zeros((*grid.shape, 3))
    img[...] = 1.0
    img[fn] = [0.84, 0.19, 0.19]   # missed (observed, not predicted) — red
    img[fp] = [0.27, 0.51, 0.71]   # false alarm (predicted, not observed) — blue
    img[tp] = [0.18, 0.55, 0.34]   # hit — green

    fig, ax = plt.subplots(figsize=(7, 7.2))
    ax.imshow(img, interpolation="nearest")
    # Crop to the main fire body (+ margin), using 1–99th percentiles of cell
    # positions so isolated far detections don't force a whitespace-heavy view.
    ys, xs = np.where(observed | pred)
    m = 6
    r0, r1 = np.percentile(ys, [1, 99]); c0, c1 = np.percentile(xs, [1, 99])
    ax.set_xlim(max(0, c0 - m), min(grid.ncols, c1 + m))
    ax.set_ylim(min(grid.nrows, r1 + m), max(0, r0 - m))
    ax.set_xticks([]); ax.set_yticks([])
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=[0.18, 0.55, 0.34], label="적중 / hit (TP)"),
        Patch(color=[0.84, 0.19, 0.19], label="미탐 / missed (FN)"),
        Patch(color=[0.27, 0.51, 0.71], label="오탐 / false (FP)"),
    ], loc="upper right", fontsize=9)
    ax.set_title(f"Deliverable 3 — 예측 vs 관측 화재 영역 / predicted vs observed footprint\n"
                 f"{fire.name_kr}  IoU={iou:.2f}  (기계론적 mechanistic ≈ 0.09)",
                 fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGS / "spread_v2_footprint.png", bbox_inches="tight")
    plt.close(fig)


def main():
    np.random.seed(SEED)
    p = PROC / "features.parquet"
    df = pd.read_parquet(p) if p.exists() else pd.read_csv(PROC / "features.csv.gz")
    print("[fig] running LOFO for footprint preds …", flush=True)
    oof, _ = lofo_predict(df, ALL_FEATURES, seed=SEED)

    print("[fig] audit …"); fig_audit()
    print("[fig] lofo …"); fig_lofo(oof)
    print("[fig] comparison …"); fig_comparison()
    print("[fig] importance …"); fig_importance()
    print("[fig] footprint …"); fig_footprint(oof)
    print(f"Wrote 5 figures to {FIGS}")


if __name__ == "__main__":
    main()
