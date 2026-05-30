"""Deliverable 6 -- visualisations (Korean + English labels).

Three figures:
* per-held-out-fire prediction maps (predicted ignition probability vs the
  cells that actually newly burned, for one representative transition),
* overlaid ROC curves (one per held-out fire),
* gain-based feature-importance bar chart.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from sklearn.metrics import roc_curve

_WQY = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"


def setup_korean_font() -> bool:
    """Register a Hangul-capable font; return True on success."""
    try:
        if Path(_WQY).exists():
            font_manager.fontManager.addfont(_WQY)
            plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
            plt.rcParams["axes.unicode_minus"] = False
            return True
    except Exception:
        pass
    return False


def plot_roc_curves(oof: pd.DataFrame, per_fire: dict, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 6))
    for fid in sorted(oof["fire_id"].unique()):
        sub = oof[oof["fire_id"] == fid]
        if sub["label"].nunique() < 2:
            continue
        fpr, tpr, _ = roc_curve(sub["label"], sub["pred"])
        auc = per_fire.get(fid, {}).get("roc_auc")
        blind = per_fire.get(fid, {}).get("fuel_blind")
        tag = " (fuel-blind)" if blind else ""
        ax.plot(fpr, tpr, lw=1.8, label=f"{fid}{tag}: AUC={auc:.3f}" if auc else fid)
    ax.plot([0, 1], [0, 1], "k--", lw=1, alpha=0.5, label="random (무작위)")
    ax.set_xlabel("False positive rate (오경보율)")
    ax.set_ylabel("True positive rate (탐지율)")
    ax.set_title("Leave-one-fire-out ROC / 화재 단위 교차검증 ROC")
    ax.legend(fontsize=8, loc="lower right")
    ax.set_aspect("equal")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_feature_importance(importance: dict, out_path: Path) -> None:
    gain = importance["gain_normalised"]
    items = sorted(gain.items(), key=lambda kv: kv[1])
    names = [k for k, _ in items]
    vals = [v for _, v in items]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(names, vals, color="#c0392b")
    ax.set_xlabel("Normalised gain importance (정규화 이득 중요도)")
    ax.set_title("Feature importance / 변수 중요도 (XGBoost gain)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def plot_prediction_map(seq, oof: pd.DataFrame, fire_id: str, out_path: Path):
    """Map predicted ignition probability vs actual new burns for the
    transition (of this fire) that had the most new ignitions."""
    sub = oof[oof["fire_id"] == fire_id]
    if sub.empty:
        return None
    # representative transition = most positives
    t = int(sub.groupby("transition")["label"].sum().idxmax())
    tr = sub[sub["transition"] == t]
    H, W = seq.shape
    burned_t = seq.burned_mask(t)

    fig, ax = plt.subplots(figsize=(7.5, 7))
    # background: already-burned at t (grey), land/sea via elevation
    ax.imshow(np.isfinite(seq.elevation), cmap="Greys", alpha=0.12, origin="upper")
    by, bx = np.nonzero(burned_t)
    ax.scatter(bx, by, s=6, c="0.45", marker="s", label="Burned by t (기연소)")
    sc = ax.scatter(
        tr["col"], tr["row"], c=tr["pred"], cmap="YlOrRd", s=10,
        vmin=0, vmax=max(0.05, float(tr["pred"].max())), label="P(ignite) 예측확률",
    )
    pos = tr[tr["label"] == 1]
    ax.scatter(
        pos["col"], pos["row"], facecolors="none", edgecolors="#1f4ed8",
        s=42, linewidths=1.3, label="Actually ignited (실제 신규연소)",
    )
    cbar = fig.colorbar(sc, ax=ax, shrink=0.8)
    cbar.set_label("Predicted ignition probability / 예측 발화확률")
    blind = " [fuel-blind 연료자료 없음]" if seq.fuel_covered.mean() < 0.3 else ""
    ax.set_title(
        f"{fire_id} — transition t={t} (전이 t={t}){blind}\n"
        f"predicted prob vs actual new ignitions / 예측확률 대 실제 신규발화"
    )
    ax.set_xlabel("grid col (375 m)")
    ax.set_ylabel("grid row (375 m)")
    ax.legend(fontsize=8, loc="upper right")
    ax.set_xlim(max(0, bx.min() - 10), min(W, bx.max() + 10))
    ax.set_ylim(min(H, by.max() + 10), max(0, by.min() - 10))
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return t


def plot_conditional_auc(per_fire: dict, band_labels, out_path: Path) -> None:
    """Grouped bars: AUC within each distance band, per held-out fire."""
    fires = [f for f in per_fire if isinstance(per_fire[f], dict) and "conditional_auc" in per_fire[f]]
    x = np.arange(len(band_labels))
    width = 0.8 / max(1, len(fires))
    fig, ax = plt.subplots(figsize=(9, 5.5))
    for i, f in enumerate(fires):
        cond = per_fire[f]["conditional_auc"]
        vals = [cond.get(b, {}).get("auc") for b in band_labels]
        vals = [np.nan if v is None else v for v in vals]
        ax.bar(x + i * width, vals, width, label=f)
    ax.axhline(0.5, color="k", ls="--", lw=1, alpha=0.6)
    ax.set_xticks(x + width * (len(fires) - 1) / 2)
    ax.set_xticklabels(band_labels)
    ax.set_ylim(0.3, 1.0)
    ax.set_xlabel("Distance-to-nearest-fire band (최근접 화재까지 거리 구간)")
    ax.set_ylabel("AUC within band (구간 내 AUC)")
    ax.set_title("Conditional AUC by distance band / 거리구간별 조건부 AUC\n(0.5 = no skill 무변별력)")
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
