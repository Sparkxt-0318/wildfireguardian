"""Probability-calibration measurement for the spread_v2 ignition model.

The Round-1 문서 adopted the gradient-boosted model partly for **확률 보정**
(probability calibration) — a claim that was never *measured*. This module turns
it into evidence. It scores calibration on the **out-of-fold (LOFO)**
predictions of the canonical GBM and its controlled baselines (random forest,
logistic regression) — each fire scored by a model that never saw it — with:

- **Brier score** — mean squared error of the probability, ``mean((p - y)**2)``;
  0 = perfect, decomposes into calibration + refinement.
- **Expected Calibration Error (ECE)** — the count-weighted mean gap between
  predicted probability and observed frequency, over **15 equal-count
  (equal-mass) bins**. Equal-count (not equal-width) binning is deliberate: the
  ignition base rate is ~2 %, so predicted probabilities pile up near zero and
  equal-width bins would leave the high-probability bins nearly empty and
  dominated by noise. Bins are assigned by a stable rank split so every bin
  holds ``N/15`` rows regardless of ties — see :func:`equal_count_bin_ids`.
- **Reliability curve** — mean predicted probability vs observed frequency per
  bin, the data plotted in ``docs/figures/calibration_reliability.png``.

Everything here is a pure function of ``(y, p)`` or an OOF DataFrame, so it is
unit-testable on synthetic data without the (git-ignored) FIRMS bundle. Nothing
in this module trains or touches the spread model, the forward-sim, or routing.

Why calibration matters for *this* system (not a generic ML nicety): the
evacuation/rescue router integrates the hazard as an **exposure** dose
``∫ P(ignition) dt`` (``routing/evacuation.py``: ``exposure += h * dt``). If
``P`` is miscalibrated, that integral is off by the miscalibration at every step
— a route ranked "low exposure" may not be. Calibrated ``P`` is what makes the
exposure metric physically meaningful.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..spread_v2.features import FEATURE_COLUMNS
from ..spread_v2.model import DEFAULT_SEED

#: Binning used for ECE / reliability throughout this module and the report.
N_BINS: int = 15
BINNING_STRATEGY: str = "equal-count (equal-mass)"


# ---------------------------------------------------------------------------
# Core metrics (pure functions of y, p)
# ---------------------------------------------------------------------------


def brier(y: np.ndarray, p: np.ndarray) -> float:
    """Brier score ``mean((p - y)**2)`` for binary ``y`` and probability ``p``."""
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    if p.size == 0:
        return float("nan")
    return float(np.mean((p - y) ** 2))


def equal_count_bin_ids(p: np.ndarray, n_bins: int = N_BINS) -> np.ndarray:
    """Assign each probability to one of ``n_bins`` **equal-count** bins.

    Rows are ranked (stable order breaks ties deterministically) and split into
    ``n_bins`` contiguous groups of ~equal size, so every bin holds ``N/n_bins``
    rows even when many probabilities are identical (the rare-positive regime).
    Returns an int array in ``[0, n_bins)`` (bin 0 = lowest probabilities).
    """
    p = np.asarray(p, dtype=np.float64)
    n = p.size
    if n == 0:
        return np.empty(0, dtype=np.int64)
    order = np.argsort(p, kind="stable")
    ranks = np.empty(n, dtype=np.int64)
    ranks[order] = np.arange(n, dtype=np.int64)
    return (ranks * n_bins // n).astype(np.int64)


def reliability_table(y: np.ndarray, p: np.ndarray, n_bins: int = N_BINS) -> list[dict]:
    """Per-bin reliability data: mean predicted prob vs observed frequency.

    One dict per non-empty equal-count bin with ``bin`` index, ``n``,
    ``positives``, ``mean_pred`` (x of the reliability curve), ``obs_freq``
    (y of the curve), and the bin's probability span ``[p_lo, p_hi]``.
    """
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    b = equal_count_bin_ids(p, n_bins)
    rows: list[dict] = []
    for k in range(n_bins):
        m = b == k
        if not m.any():
            continue
        rows.append({
            "bin": int(k),
            "n": int(m.sum()),
            "positives": int(y[m].sum()),
            "mean_pred": float(p[m].mean()),
            "obs_freq": float(y[m].mean()),
            "p_lo": float(p[m].min()),
            "p_hi": float(p[m].max()),
        })
    return rows


def expected_calibration_error(y: np.ndarray, p: np.ndarray, n_bins: int = N_BINS) -> float:
    """ECE over ``n_bins`` equal-count bins: ``sum_b (n_b/N) |obs_b - pred_b|``."""
    y = np.asarray(y, dtype=np.float64)
    p = np.asarray(p, dtype=np.float64)
    n = p.size
    if n == 0:
        return float("nan")
    b = equal_count_bin_ids(p, n_bins)
    ece = 0.0
    for k in range(n_bins):
        m = b == k
        if not m.any():
            continue
        ece += (m.sum() / n) * abs(float(y[m].mean()) - float(p[m].mean()))
    return float(ece)


# ---------------------------------------------------------------------------
# Pooled + per-fold aggregation over an OOF frame
# ---------------------------------------------------------------------------


def calibration_by_fold(
    oof: pd.DataFrame, *, n_bins: int = N_BINS, prob_col: str = "prob",
) -> dict:
    """Per-held-out-fire Brier / ECE plus their mean ± SD across folds."""
    folds: dict[str, dict] = {}
    for fid, g in oof.groupby("fire_id"):
        y = g["label"].to_numpy()
        p = g[prob_col].to_numpy()
        folds[str(fid)] = {
            "n": int(len(g)),
            "positives": int(y.sum()),
            "brier": brier(y, p),
            "ece": expected_calibration_error(y, p, n_bins),
        }
    briers = np.array([v["brier"] for v in folds.values()], dtype=float)
    eces = np.array([v["ece"] for v in folds.values()], dtype=float)
    return {
        "folds": folds,
        "brier_mean": float(np.mean(briers)) if briers.size else float("nan"),
        "brier_sd": float(np.std(briers, ddof=1)) if briers.size > 1 else float("nan"),
        "ece_mean": float(np.mean(eces)) if eces.size else float("nan"),
        "ece_sd": float(np.std(eces, ddof=1)) if eces.size > 1 else float("nan"),
    }


def calibration_report(
    oof: pd.DataFrame, *, n_bins: int = N_BINS, prob_col: str = "prob",
) -> dict:
    """Full calibration summary for one model's OOF frame.

    ``pooled`` (Brier / ECE / base rate over all OOF rows), ``per_fold`` (Brier /
    ECE per held-out fire + mean±SD), and ``reliability`` (pooled reliability
    curve). This is the per-model block persisted in ``calibration_metrics.json``.
    """
    y = oof["label"].to_numpy()
    p = oof[prob_col].to_numpy()
    return {
        "pooled": {
            "n": int(len(y)),
            "positives": int(np.asarray(y).sum()),
            "base_rate": float(np.asarray(y, dtype=float).mean()) if len(y) else float("nan"),
            "brier": brier(y, p),
            "ece": expected_calibration_error(y, p, n_bins),
        },
        "per_fold": calibration_by_fold(oof, n_bins=n_bins, prob_col=prob_col),
        "reliability": reliability_table(y, p, n_bins),
    }


# ---------------------------------------------------------------------------
# SUPPLEMENTARY — per-fold isotonic calibration of the GBM (bounded scope)
# ---------------------------------------------------------------------------


def isotonic_oof_gbm(
    ds: pd.DataFrame, *, seed: int = DEFAULT_SEED,
    feature_columns: tuple[str, ...] = FEATURE_COLUMNS, n_splits: int = 5,
) -> pd.DataFrame:
    """Per-fold isotonic recalibration of the canonical GBM, LOFO.

    For each held-out fire the canonical GBM (identical config/seed to
    :func:`spread_v2.model` via ``default_models(seed)['hist_gbm']``) is:

    - fit on the **training fires only** and applied to the held-out fire →
      ``prob_raw`` (row-for-row the canonical OOF), and
    - wrapped in ``CalibratedClassifierCV(method='isotonic')`` whose isotonic map
      is learned by **internal CV on the training fires only** (no leakage from
      the held-out fire), then applied to the held-out fire → ``prob_iso``.

    Returns an OOF frame ``[fire_id, label, prob_raw, prob_iso]`` so raw-vs-post
    Brier/ECE can be compared on identical rows. This is measurement only — the
    calibrated probabilities are **not** wired into the forward-sim or router
    (that would change every routing number; it is noted as future work).
    """
    from sklearn.base import clone
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import StratifiedKFold

    from .ml_baselines import default_models

    base = default_models(seed)["hist_gbm"]
    cols = list(feature_columns)
    fires = sorted(ds["fire_id"].unique())
    parts: list[pd.DataFrame] = []
    for held in fires:
        train = ds[ds["fire_id"] != held]
        test = ds[ds["fire_id"] == held]
        if train["label"].nunique() < 2 or len(test) == 0:
            continue
        x_tr = train[cols].to_numpy("float64")
        y_tr = train["label"].to_numpy("int64")
        x_te = test[cols].to_numpy("float64")

        raw = clone(base).fit(x_tr, y_tr).predict_proba(x_te)[:, 1]

        n_pos = int(y_tr.sum())
        n_neg = int((y_tr == 0).sum())
        k = max(2, min(n_splits, n_pos, n_neg))
        cv = StratifiedKFold(n_splits=k, shuffle=True, random_state=seed)
        cal = CalibratedClassifierCV(estimator=clone(base), method="isotonic", cv=cv)
        cal.fit(x_tr, y_tr)
        iso = cal.predict_proba(x_te)[:, 1]

        parts.append(pd.DataFrame({
            "fire_id": test["fire_id"].to_numpy(),
            "label": test["label"].to_numpy().astype(int),
            "prob_raw": raw,
            "prob_iso": iso,
        }))
    if not parts:
        return pd.DataFrame(columns=["fire_id", "label", "prob_raw", "prob_iso"])
    return pd.concat(parts, ignore_index=True)


def isotonic_summary(
    iso_oof: pd.DataFrame, *, n_bins: int = N_BINS,
) -> dict:
    """Raw-vs-post Brier/ECE (pooled + per-fold means) for the isotonic OOF."""
    raw = iso_oof.rename(columns={"prob_raw": "prob"})[["fire_id", "label", "prob"]]
    post = iso_oof.rename(columns={"prob_iso": "prob"})[["fire_id", "label", "prob"]]
    rr = calibration_report(raw, n_bins=n_bins)
    pp = calibration_report(post, n_bins=n_bins)
    return {
        "method": ("per-fold isotonic — CalibratedClassifierCV(method='isotonic'), "
                   "internal StratifiedKFold CV on train fires only, applied to the "
                   "held-out fire"),
        "raw": {
            "pooled_brier": rr["pooled"]["brier"], "pooled_ece": rr["pooled"]["ece"],
            "per_fold_brier_mean": rr["per_fold"]["brier_mean"],
            "per_fold_ece_mean": rr["per_fold"]["ece_mean"],
        },
        "post": {
            "pooled_brier": pp["pooled"]["brier"], "pooled_ece": pp["pooled"]["ece"],
            "per_fold_brier_mean": pp["per_fold"]["brier_mean"],
            "per_fold_ece_mean": pp["per_fold"]["ece_mean"],
        },
        "delta": {
            "pooled_brier": pp["pooled"]["brier"] - rr["pooled"]["brier"],
            "pooled_ece": pp["pooled"]["ece"] - rr["pooled"]["ece"],
        },
        "reliability_post": pp["reliability"],
        "note": ("SUPPLEMENTARY / measurement only — calibrated probabilities are "
                 "NOT wired into the forward-sim or routing this round (that would "
                 "change every routing number); future work."),
    }


# ---------------------------------------------------------------------------
# Serialization — deterministic, rounded JSON assembly
# ---------------------------------------------------------------------------


def round_floats(obj, ndigits: int = 6):
    """Recursively round floats to ``ndigits`` (numpy scalars → Python types).

    Persisted metrics are rounded so the JSON is **byte-identical** across runs:
    the only run-to-run variation is machine-epsilon (~2e-16) parallel-reduction
    noise in the random-forest baseline, which vanishes far below ``ndigits``.
    """
    if isinstance(obj, dict):
        return {k: round_floats(v, ndigits) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [round_floats(v, ndigits) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        f = float(obj)
        if not np.isfinite(f):
            return None
        return round(f, ndigits)
    return obj


def assemble_metrics(
    models_reports: dict, isotonic: dict, *, meta: dict,
    seed: int = DEFAULT_SEED, n_bins: int = N_BINS, ndigits: int = 6,
) -> dict:
    """Assemble the rounded, JSON-ready ``calibration_metrics.json`` payload.

    Pure function of already-computed per-model :func:`calibration_report`
    blocks + the isotonic summary + script-supplied ``meta`` (dataset counts,
    OOF file paths, reference AUCs). Rounding makes the result deterministic.
    """
    payload = {
        "seed": seed,
        "binning": {
            "strategy": BINNING_STRATEGY,
            "n_bins": n_bins,
            "note": ("each bin holds ~N/n_bins rows via a stable rank split "
                     "(equal-count / equal-mass), robust to ties in the "
                     "rare-positive regime; ECE = count-weighted mean "
                     "|observed - predicted| over the bins"),
        },
        "dataset": meta.get("dataset", {}),
        "oof_files": meta.get("oof_files", {}),
        "models": models_reports,
        "supplementary_isotonic_gbm": isotonic,
        "reference": meta.get("reference", {}),
        "generated_by": "scripts/calibration_metrics.py",
        "measurement_only": ("no model / forward-sim / routing change; OOF "
                             "predictions scored by models that never saw the fire"),
    }
    return round_floats(payload, ndigits)


# ---------------------------------------------------------------------------
# Figure — reliability diagram (bilingual, repo style; lazy matplotlib import)
# ---------------------------------------------------------------------------

#: Display order, colour and bilingual label for each model in the figure.
MODEL_STYLE: dict[str, dict] = {
    "hist_gbm": {"color": "#4c72b0", "label": "GBM (정준 / canonical)", "marker": "o"},
    "random_forest": {"color": "#dd8452", "label": "랜덤 포레스트 / random forest", "marker": "s"},
    "logistic": {"color": "#55a868", "label": "로지스틱 / logistic", "marker": "^"},
}


def make_reliability_figure(models: dict, out_path, *, title_suffix: str = "") -> str:
    """Write the three-model reliability diagram to ``out_path`` (PNG).

    ``models`` maps model name → the per-model block from
    :func:`calibration_report` (needs ``reliability`` + ``pooled`` Brier/ECE).
    Draws each model's reliability curve, the ``y = x`` perfect-calibration
    diagonal, and an annotation box of pooled Brier/ECE per model. Matplotlib is
    imported lazily so this module stays import-light for pure-metric tests.
    """
    from pathlib import Path

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        plt.rcParams["font.family"] = "WenQuanYi Zen Hei"
    except Exception:  # pragma: no cover - font optional in headless envs
        pass
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 130

    fig, ax = plt.subplots(figsize=(7.4, 7.0))
    ax.plot([0, 1], [0, 1], ls="--", c="0.4", lw=1.2,
            label="완전 보정 / perfect calibration (y = x)")

    ann_lines = []
    for name, style in MODEL_STYLE.items():
        blk = models.get(name)
        if blk is None:
            continue
        rel = blk["reliability"]
        xs = [r["mean_pred"] for r in rel]
        ys = [r["obs_freq"] for r in rel]
        ax.plot(xs, ys, marker=style["marker"], ms=5, lw=1.6,
                color=style["color"], label=style["label"])
        b = blk["pooled"]["brier"]
        e = blk["pooled"]["ece"]
        ann_lines.append((style["color"], f"{style['label']}:  Brier {b:.4f}   ECE {e:.4f}"))

    # Square axes zoomed to where equal-count bins live (rare-positive regime
    # keeps most mass at low probability); a shared limit keeps the diagonal 45°.
    hi = 0.0
    for name in MODEL_STYLE:
        blk = models.get(name)
        if blk is None:
            continue
        for r in blk["reliability"]:
            hi = max(hi, r["mean_pred"], r["obs_freq"])
    hi = min(1.0, max(0.2, hi * 1.12))
    ax.set_xlim(0, hi)
    ax.set_ylim(0, hi)
    ax.set_aspect("equal", adjustable="box")

    ax.set_xlabel("예측 확률 (구간 평균) / mean predicted probability")
    ax.set_ylabel("관측 빈도 / observed frequency")
    ttl = "확률 보정 신뢰도 곡선 / probability-calibration reliability curve"
    if title_suffix:
        ttl += f"\n{title_suffix}"
    ax.set_title(ttl + "\nLOFO out-of-fold · 15 equal-count bins", fontsize=11,
                 fontweight="bold")
    ax.legend(loc="upper left", fontsize=8.5, framealpha=0.92)
    ax.grid(True, ls=":", lw=0.5, alpha=0.6)

    # Brier/ECE annotation box (the "inset" the brief asks for).
    y0 = 0.02
    ax.text(0.985 * hi, y0 + 0.008 * hi,
            "풀링 OOF / pooled OOF", ha="right", va="bottom", fontsize=8.5,
            fontweight="bold", transform=ax.transData)
    for i, (col, txt) in enumerate(ann_lines):
        ax.text(0.985 * hi, y0 + 0.008 * hi + (i + 1) * 0.045 * hi, txt,
                ha="right", va="bottom", fontsize=8, color=col,
                transform=ax.transData)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)


__all__ = [
    "N_BINS",
    "BINNING_STRATEGY",
    "brier",
    "equal_count_bin_ids",
    "reliability_table",
    "expected_calibration_error",
    "calibration_by_fold",
    "calibration_report",
    "isotonic_oof_gbm",
    "isotonic_summary",
    "round_floats",
    "assemble_metrics",
    "make_reliability_figure",
    "MODEL_STYLE",
]
