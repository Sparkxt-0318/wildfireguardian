"""Standard ML baselines for the spread_v2 LOFO task (logistic regression, random
forest) as controlled comparators to the canonical gradient-boosted model.

Answers the 기술적 우수성 critique "you only beat a bad physics model": how does the
canonical model compare to *standard ML baselines* on the **identical 16 features,
identical fold set, identical seed**? This module runs leave-one-fire-out for any
set of estimators over the same holdout loop the canonical model uses, so the
comparison is controlled (no per-model feature/fold/seed differences, no tuning to
manufacture a gap).

The baselines get a median-imputer (the GBM handles NaN natively; LR/RF do not)
and, for LR, standardization — documented, reasonable defaults, **not tuned**.
Model-agnostic in/out (a dataframe with ``fire_id``/``label`` + the feature
columns), so it is unit-tested on a synthetic multi-fire frame without the
(git-ignored) FIRMS bundle.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..spread_v2.features import FEATURE_COLUMNS
from ..spread_v2.model import DEFAULT_SEED


def default_models(seed: int = DEFAULT_SEED) -> dict:
    """The comparator estimators with documented, untuned defaults.

    - ``logistic``       : median-impute → standardize → L2 logistic regression.
    - ``random_forest``  : median-impute → 300-tree RF (min_samples_leaf=20).
    - ``hist_gbm``       : the canonical gradient-boosted model (native NaN) — the
      reference row (model card mean-of-folds 0.89 / pooled 0.905).
    """
    from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    return {
        "logistic": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("clf", LogisticRegression(max_iter=2000, C=1.0, random_state=seed)),
        ]),
        "random_forest": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("clf", RandomForestClassifier(
                n_estimators=300, max_depth=None, min_samples_leaf=20,
                n_jobs=-1, random_state=seed)),
        ]),
        # The canonical model's estimator (HistGradientBoosting, log-loss) — same
        # config as spread_v2.model._make_classifier; the reference, not retuned.
        "hist_gbm": HistGradientBoostingClassifier(
            loss="log_loss", learning_rate=0.08, max_iter=300, max_leaf_nodes=31,
            min_samples_leaf=40, l2_regularization=1.0, early_stopping=True,
            validation_fraction=0.15, random_state=seed),
    }


@dataclass
class BaselineResult:
    model: str
    per_fire_auc: dict[str, float | None]
    mean_of_folds: float
    sd: float
    pooled_auc: float | None

    def as_dict(self) -> dict:
        return {"model": self.model,
                "per_fire_auc": {k: (None if v is None else round(v, 4))
                                 for k, v in self.per_fire_auc.items()},
                "mean_of_folds": round(self.mean_of_folds, 4),
                "sd": round(self.sd, 4),
                "pooled_auc": (None if self.pooled_auc is None else round(self.pooled_auc, 4))}


def _auc(y, p) -> float | None:
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y)
    if y.min() == y.max():
        return None
    return float(roc_auc_score(y, p))


def lofo_compare(
    ds: pd.DataFrame, *, models: dict | None = None, seed: int = DEFAULT_SEED,
    feature_columns: tuple[str, ...] = FEATURE_COLUMNS,
) -> dict[str, BaselineResult]:
    """Leave-one-fire-out AUC for each estimator on the SAME folds/features/seed.

    Mirrors :func:`spread_v2.model.leave_one_fire_out`'s holdout loop (hold out
    whole fires; train on the rest) but parameterized by the estimator, so every
    model sees identical data — the controlled comparison the critique asks for.
    """
    models = models or default_models(seed)
    fires = sorted(ds["fire_id"].unique())
    cols = list(feature_columns)
    out: dict[str, BaselineResult] = {}
    for name, est in models.items():
        per_fire: dict[str, float | None] = {}
        oof_y: list[np.ndarray] = []
        oof_p: list[np.ndarray] = []
        for held in fires:
            train = ds[ds["fire_id"] != held]
            test = ds[ds["fire_id"] == held]
            if train["label"].nunique() < 2 or len(test) == 0:
                per_fire[held] = None
                continue
            from sklearn.base import clone
            clf = clone(est)
            clf.fit(train[cols].to_numpy("float64"), train["label"].to_numpy("int64"))
            p = clf.predict_proba(test[cols].to_numpy("float64"))[:, 1]
            per_fire[held] = _auc(test["label"].to_numpy(), p)
            oof_y.append(test["label"].to_numpy())
            oof_p.append(p)
        vals = [v for v in per_fire.values() if v is not None]
        pooled = (_auc(np.concatenate(oof_y), np.concatenate(oof_p)) if oof_y else None)
        out[name] = BaselineResult(
            model=name, per_fire_auc=per_fire,
            mean_of_folds=float(np.mean(vals)) if vals else float("nan"),
            sd=float(np.std(vals, ddof=1)) if len(vals) > 1 else float("nan"),
            pooled_auc=pooled)
    return out


__all__ = ["default_models", "BaselineResult", "lofo_compare"]
