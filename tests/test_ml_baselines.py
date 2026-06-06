"""Unit tests for the ML-baseline LOFO comparator (logistic regression / random
forest vs the canonical gradient-boosted model).

Validates the controlled-comparison wiring on a synthetic multi-fire frame: every
model runs over the SAME leave-one-fire-out folds with the 16 feature columns,
returns per-fire + mean-of-folds + pooled AUCs, and learns the planted signal
(AUC > 0.5). No real FIRMS data needed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from wildfireguardian.spread_v2.features import FEATURE_COLUMNS
from wildfireguardian.validation.ml_baselines import default_models, lofo_compare


def _synthetic_ds(n_fires=4, n_per=400, seed=0) -> pd.DataFrame:
    """Multi-fire frame with a planted signal in two features (so AUC > 0.5)."""
    rng = np.random.default_rng(seed)
    rows = []
    for f in range(n_fires):
        y = (rng.random(n_per) < 0.25).astype(int)
        data = {c: rng.normal(0, 1, n_per) for c in FEATURE_COLUMNS}
        # plant signal: dist_to_fire_m lower + days_since_rain higher for positives
        data["dist_to_fire_m"] = rng.normal(0, 1, n_per) - 1.2 * y
        data["days_since_rain"] = rng.normal(0, 1, n_per) + 1.2 * y
        df = pd.DataFrame(data)
        df["label"] = y
        df["fire_id"] = f"fire_{f}"
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


def test_lofo_compare_runs_all_models_same_folds():
    ds = _synthetic_ds()
    res = lofo_compare(ds, seed=20250603)
    assert set(res) == {"logistic", "random_forest", "hist_gbm"}
    fires = sorted(ds["fire_id"].unique())
    for name, r in res.items():
        # every model evaluated on the SAME held-out fire set
        assert set(r.per_fire_auc) == set(fires)
        # learns the planted signal
        assert r.mean_of_folds > 0.55, f"{name} failed to learn signal"
        assert r.pooled_auc is not None and r.pooled_auc > 0.55
        assert np.isfinite(r.sd)


def test_lofo_compare_is_deterministic():
    ds = _synthetic_ds(seed=1)
    a = lofo_compare(ds, seed=20250603)["random_forest"].mean_of_folds
    b = lofo_compare(ds, seed=20250603)["random_forest"].mean_of_folds
    assert a == b


def test_default_models_documented_set():
    models = default_models(seed=20250603)
    assert set(models) == {"logistic", "random_forest", "hist_gbm"}
    # logistic standardizes (controlled comparison); RF/GBM do not need it
    assert "scale" in dict(models["logistic"].named_steps)
