"""The spread_v2 per-cell ignition-probability model + honest validation.

A gradient-boosted classifier predicts, for each candidate cell at overpass
``k``, the probability it is detected as burning by overpass ``k+1``. The
model is deliberately simple and reproducible (fixed seed); the point of this
project is the *coupling* of a probabilistic hazard into routing, not a
state-of-the-art fire model.

Validation is **leave-one-fire-out (LOFO)**: train on all-but-one fire,
predict the held-out fire, so reported skill is genuinely out-of-sample on an
unseen event. We report:

- **AUC** (pooled out-of-fold and per held-out fire),
- **far-band AUC** (rows >3 km from the active front — the "can it predict
  *reach*?" question, which is where the severity signal must live),
- **footprint IoU** of the thresholded next-overpass prediction vs the
  observed next-overpass detection footprint, against a "spread-to-adjacent"
  persistence baseline (so any "Nx baseline" claim is grounded in *this* data,
  not an external number),
- **permutation importance**, aggregated across folds as a ROW-WEIGHTED
  average (each fold's AUC drop weighted by its held-out row count — the
  largest fire carries ~54 % of rows, so this is not a plain fold mean).
  ⚠ The "severity, not wind direction" conclusion this once evidenced is
  WITHDRAWN as not established (docs/MODEL_CARD.md).

We use scikit-learn's :class:`HistGradientBoostingClassifier` (handles NaN,
no extra dependency); xgboost is intentionally not required.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS

DEFAULT_SEED = 20250603


def _make_classifier(seed: int):
    from sklearn.ensemble import HistGradientBoostingClassifier

    # NB: we deliberately do NOT use class_weight="balanced". The router
    # integrates these outputs as genuine ignition *probabilities*, so honest
    # calibration matters more than a balanced operating point. On this data
    # the unweighted log-loss model is both better calibrated (held-out
    # Brier ~0.03 vs ~0.09 balanced) and at least as discriminating
    # (incl. a markedly higher far-band AUC), and its forward-simulated
    # envelope grows sensibly instead of exploding. AUC is rank-based and so
    # is unaffected by the rare-positive base rate.
    return HistGradientBoostingClassifier(
        loss="log_loss",
        learning_rate=0.08,
        max_iter=300,
        max_leaf_nodes=31,
        min_samples_leaf=40,
        l2_regularization=1.0,
        early_stopping=True,
        validation_fraction=0.15,
        random_state=seed,
    )


@dataclass
class IgnitionModelV2:
    """Fitted spread_v2 model: feature columns + a calibrated GBM."""

    seed: int = DEFAULT_SEED
    feature_columns: tuple[str, ...] = FEATURE_COLUMNS
    clf: object | None = None

    def fit(self, df: pd.DataFrame) -> "IgnitionModelV2":
        X = df[list(self.feature_columns)].to_numpy(dtype="float64")
        y = df["label"].to_numpy(dtype="int64")
        self.clf = _make_classifier(self.seed).fit(X, y)
        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        if self.clf is None:
            raise RuntimeError("model not fitted")
        X = df[list(self.feature_columns)].to_numpy(dtype="float64")
        return self.clf.predict_proba(X)[:, 1]

    def predict_proba_matrix(self, X: np.ndarray) -> np.ndarray:
        if self.clf is None:
            raise RuntimeError("model not fitted")
        return self.clf.predict_proba(X)[:, 1]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _safe_auc(y: np.ndarray, p: np.ndarray) -> float | None:
    from sklearn.metrics import roc_auc_score

    y = np.asarray(y)
    if y.min() == y.max():  # only one class present
        return None
    return float(roc_auc_score(y, p))


def cell_iou(pred_mask: np.ndarray, obs_mask: np.ndarray) -> float:
    """Intersection-over-union of two boolean cell masks."""
    inter = np.logical_and(pred_mask, obs_mask).sum()
    union = np.logical_or(pred_mask, obs_mask).sum()
    if union == 0:
        return 1.0
    return float(inter / union)


@dataclass
class LofoResult:
    """Outputs of a leave-one-fire-out run."""

    pooled_auc: float | None
    far_band_auc: float | None
    mid_band_auc: float | None
    per_fire_auc: dict[str, float | None]
    oof: pd.DataFrame                              # fire_id, label, prob, dist_band, ...
    permutation_importance: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "pooled_auc": self.pooled_auc,
            "far_band_auc": self.far_band_auc,
            "mid_band_auc": self.mid_band_auc,
            "per_fire_auc": self.per_fire_auc,
            "permutation_importance": self.permutation_importance,
            "n_oof_rows": int(len(self.oof)),
            "notes": self.notes,
        }


def _permutation_importance_fold(model: IgnitionModelV2, df_test: pd.DataFrame,
                                 base_auc: float, rng: np.random.Generator) -> dict[str, float]:
    """AUC drop when each feature column is permuted (one held-out fire)."""
    X = df_test[list(model.feature_columns)].to_numpy(dtype="float64")
    y = df_test["label"].to_numpy(dtype="int64")
    drops: dict[str, float] = {}
    for j, name in enumerate(model.feature_columns):
        Xp = X.copy()
        Xp[:, j] = rng.permutation(Xp[:, j])
        auc_p = _safe_auc(y, model.predict_proba_matrix(Xp))
        drops[name] = (base_auc - auc_p) if (auc_p is not None) else 0.0
    return drops


def leave_one_fire_out(
    ds: pd.DataFrame,
    *,
    seed: int = DEFAULT_SEED,
    compute_importance: bool = True,
) -> LofoResult:
    """Run leave-one-fire-out CV and gather honest out-of-sample metrics."""
    fires = sorted(ds["fire_id"].unique())
    notes: list[str] = []
    oof_parts: list[pd.DataFrame] = []
    per_fire_auc: dict[str, float | None] = {}
    imp_accum: dict[str, list[tuple[float, int]]] = {c: [] for c in FEATURE_COLUMNS}
    rng = np.random.default_rng(seed)

    for held in fires:
        train = ds[ds["fire_id"] != held]
        test = ds[ds["fire_id"] == held]
        if train["label"].nunique() < 2 or len(test) == 0:
            per_fire_auc[held] = None
            continue
        model = IgnitionModelV2(seed=seed).fit(train)
        p = model.predict_proba(test)
        part = test[["fire_id", "label", "dist_band", "dist_to_fire_m"]].copy()
        part["prob"] = p
        oof_parts.append(part)
        auc = _safe_auc(test["label"].to_numpy(), p)
        per_fire_auc[held] = auc
        if compute_importance and auc is not None:
            for name, drop in _permutation_importance_fold(model, test, auc, rng).items():
                imp_accum[name].append((drop, len(test)))

    if not oof_parts:
        return LofoResult(None, None, None, per_fire_auc, pd.DataFrame(),
                          notes=["no fold had both classes in training"])
    oof = pd.concat(oof_parts, ignore_index=True)

    pooled = _safe_auc(oof["label"].to_numpy(), oof["prob"].to_numpy())
    far = oof[oof["dist_band"] == "far"]
    mid = oof[oof["dist_band"] == "mid"]
    far_auc = _safe_auc(far["label"].to_numpy(), far["prob"].to_numpy()) if len(far) else None
    mid_auc = _safe_auc(mid["label"].to_numpy(), mid["prob"].to_numpy()) if len(mid) else None

    importance: dict[str, float] = {}
    if compute_importance:
        for name, vals in imp_accum.items():
            if vals:
                w = np.array([n for _, n in vals], dtype=float)
                d = np.array([dr for dr, _ in vals], dtype=float)
                importance[name] = float(np.average(d, weights=w))
        importance = dict(sorted(importance.items(), key=lambda kv: -kv[1]))

    return LofoResult(
        pooled_auc=pooled, far_band_auc=far_auc, mid_band_auc=mid_auc,
        per_fire_auc=per_fire_auc, oof=oof,
        permutation_importance=importance, notes=notes,
    )


# ---------------------------------------------------------------------------
# Footprint IoU (model vs persistence baseline), leave-one-fire-out
# ---------------------------------------------------------------------------


def _persistence_prediction(active: np.ndarray) -> np.ndarray:
    """Baseline: predict the fire spreads to its immediately-adjacent cells."""
    from scipy.ndimage import binary_dilation

    return binary_dilation(active, iterations=1) & ~active


@dataclass
class FootprintIoU:
    model_iou: float
    persistence_iou: float
    ratio: float
    n_transitions: int


def footprint_iou_lofo(
    fire_ids: list[str],
    ds: pd.DataFrame,
    *,
    threshold: float = 0.5,
    seed: int = DEFAULT_SEED,
    cell_size_m: float = 500.0,
    gap_minutes: float = 90.0,
    buffer_m: float = 6000.0,
    data_dir=None,
) -> FootprintIoU:
    """Footprint IoU of next-overpass prediction vs observed, LOFO.

    For each fire, a model trained on the *other* fires predicts each
    transition; we threshold to a predicted new-burn mask, union with the
    active footprint, and IoU against the observed next-overpass footprint.
    Compared to the spread-to-adjacent persistence baseline.
    """
    from . import data as datamod
    from . import grid as gridmod
    from .features import StaticLayers, build_transition_frame
    from .weather import weather_series_from_event

    model_ious: list[float] = []
    pers_ious: list[float] = []

    for held in fire_ids:
        train = ds[ds["fire_id"] != held]
        if train["label"].nunique() < 2:
            continue
        model = IgnitionModelV2(seed=seed).fit(train)

        ev = datamod.load_event(held, data_dir=data_dir)
        ws = weather_series_from_event(ev)
        if ws is None:
            continue
        g = gridmod.build_grid(ev.meta.bbox_wgs84, cell_size_m=cell_size_m)
        snaps = gridmod.overpass_snapshots(ev, g, gap_minutes=gap_minutes)
        if len(snaps) < 2:
            continue
        static = StaticLayers.from_event(ev, g)
        for k in range(len(snaps) - 1):
            active = snaps[k].cumulative_mask
            obs_next = snaps[k + 1].cumulative_mask
            if not active.any() or active.all():
                continue
            # Skip trivial no-growth transitions (obs_next == active): they
            # are predicted by definition and would inflate the mean IoU.
            if not (obs_next & ~active).any():
                continue
            frame = build_transition_frame(ev, g, static, snaps[k:k + 2], ws, buffer_m=buffer_m)
            if frame.empty:
                continue
            probs = model.predict_proba(frame)
            pred_new = np.zeros_like(active)
            sel = probs >= threshold
            pred_new[frame["row"].to_numpy()[sel], frame["col"].to_numpy()[sel]] = True
            pred_cum = active | pred_new
            model_ious.append(cell_iou(pred_cum, obs_next))
            pers_cum = active | _persistence_prediction(active)
            pers_ious.append(cell_iou(pers_cum, obs_next))

    m = float(np.mean(model_ious)) if model_ious else float("nan")
    p = float(np.mean(pers_ious)) if pers_ious else float("nan")
    ratio = (m / p) if (p and np.isfinite(p) and p > 0) else float("nan")
    return FootprintIoU(model_iou=m, persistence_iou=p, ratio=ratio,
                        n_transitions=len(model_ious))


__all__ = [
    "IgnitionModelV2",
    "LofoResult",
    "FootprintIoU",
    "leave_one_fire_out",
    "footprint_iou_lofo",
    "cell_iou",
    "DEFAULT_SEED",
]
