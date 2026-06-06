"""Unit tests for the ROC-AUC inference tools (DeLong CI, significance, bootstrap,
permutation, mean-of-folds interval).

These validate the *statistics* independently of the (git-ignored) FIRMS bundle:
the DeLong AUC matches scikit-learn exactly, its analytic variance tracks the
bootstrap variance, significance/permutation tests behave on separable vs random
data, and the mean-of-folds t-interval reproduces the canonical per-fire spread
(0.890 ± 0.107, n=6) with the small-sample flag set.
"""

from __future__ import annotations

import numpy as np
import pytest

from wildfireguardian.validation.auc_stats import (
    bootstrap_auc_ci,
    delong_auc_variance,
    delong_ci,
    delong_significance,
    mean_of_folds_interval,
    permutation_test_auc,
)

# Canonical Build-B per-fire LOFO AUCs (from spread_v2_lofo.json) — used to check
# the mean-of-folds interval reproduces the model card's 0.890 ± 0.107.
CANONICAL_PER_FIRE = [0.682, 0.945, 0.974, 0.878, 0.918, 0.941]


def _separable(n=2000, sep=1.0, seed=0):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.2).astype(int)        # ~20% positives (rare-ish)
    score = rng.normal(0, 1, n) + sep * y         # positives shifted up
    return y, score


# ---------------------------------------------------------------------------
# DeLong AUC + variance
# ---------------------------------------------------------------------------


def test_delong_auc_matches_sklearn():
    from sklearn.metrics import roc_auc_score
    for seed in range(5):
        y, s = _separable(seed=seed, sep=0.8)
        auc, _ = delong_auc_variance(y, s)
        assert auc == pytest.approx(roc_auc_score(y, s), abs=1e-9)


def test_delong_auc_handles_ties():
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(1)
    y = (rng.random(500) < 0.3).astype(int)
    s = rng.integers(0, 5, 500).astype(float)     # heavy ties
    auc, var = delong_auc_variance(y, s)
    assert auc == pytest.approx(roc_auc_score(y, s), abs=1e-9)
    assert var > 0


def test_delong_variance_tracks_bootstrap():
    from sklearn.metrics import roc_auc_score
    y, s = _separable(n=1500, sep=0.7, seed=3)
    _auc, var = delong_auc_variance(y, s)
    rng = np.random.default_rng(7)
    pos, neg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
    boots = []
    for _ in range(400):
        bi = np.concatenate([rng.choice(pos, len(pos)), rng.choice(neg, len(neg))])
        boots.append(roc_auc_score(y[bi], s[bi]))
    boot_var = np.var(boots, ddof=1)
    # analytic DeLong variance should be the same order as the bootstrap variance
    assert 0.3 < (var / boot_var) < 3.0


def test_delong_variance_raises_one_class():
    with pytest.raises(ValueError):
        delong_auc_variance(np.ones(10), np.arange(10.0))


# ---------------------------------------------------------------------------
# CI + significance
# ---------------------------------------------------------------------------


def test_delong_ci_brackets_auc_and_in_unit_interval():
    y, s = _separable(seed=2, sep=0.9)
    ci = delong_ci(y, s)
    assert 0.0 <= ci.ci_low <= ci.auc <= ci.ci_high <= 1.0
    assert ci.n_pos == int(np.asarray(y).sum())


def test_significance_separated_is_significant_random_is_not():
    y, s = _separable(n=3000, sep=1.0, seed=4)
    sig = delong_significance(y, s, ref=0.5)
    assert sig["auc"] > 0.6 and sig["p_value"] < 1e-3      # clearly > 0.5

    rng = np.random.default_rng(5)
    y2 = (rng.random(3000) < 0.2).astype(int)
    s2 = rng.normal(0, 1, 3000)                            # no signal
    sig2 = delong_significance(y2, s2, ref=0.5)
    assert sig2["p_value"] > 0.05                          # cannot reject AUC=0.5


def test_bootstrap_ci_brackets_point_auc():
    y, s = _separable(n=1500, sep=0.8, seed=6)
    out = bootstrap_auc_ci(y, s, n_boot=300, seed=11)
    lo, hi = out["ci95"]
    assert 0.0 <= lo <= out["auc"] <= hi <= 1.0
    assert out["n_boot_effective"] > 250


def test_permutation_test_separates_signal_from_noise():
    y, s = _separable(n=1200, sep=1.0, seed=8)
    assert permutation_test_auc(y, s, n_perm=200, seed=1)["p_value"] < 0.02
    rng = np.random.default_rng(9)
    y2 = (rng.random(1200) < 0.2).astype(int)
    s2 = rng.normal(size=1200)
    assert permutation_test_auc(y2, s2, n_perm=200, seed=2)["p_value"] > 0.05


# ---------------------------------------------------------------------------
# Mean-of-folds interval (the n=6 small-sample caveat)
# ---------------------------------------------------------------------------


def test_mean_of_folds_reproduces_canonical_spread():
    out = mean_of_folds_interval(CANONICAL_PER_FIRE)
    assert out["mean"] == pytest.approx(0.890, abs=0.002)   # model card headline
    assert out["sd"] == pytest.approx(0.107, abs=0.003)
    assert out["n"] == 6
    assert out["small_sample"] is True
    lo, hi = out["ci95"]
    assert lo < out["mean"] < hi
    # n=6 t-interval is WIDE — must span well over ±0.05 (the honest caveat)
    assert (hi - lo) > 0.15


def test_mean_of_folds_ignores_none_folds():
    out = mean_of_folds_interval([0.9, None, 0.8, 0.85])
    assert out["n"] == 3
