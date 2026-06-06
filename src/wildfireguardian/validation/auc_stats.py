"""Confidence intervals + significance tests for ROC-AUC.

These are the inference tools the model card's headline AUC was missing: a
**DeLong** 95 % CI and significance test per fold, a **bootstrap** CI for the
pooled out-of-fold AUC, a small-sample (t) interval on the **mean-of-folds**, and
a label-**permutation** test. They are deliberately model-agnostic — they take
``(y_true, y_score)`` arrays — so the same code serves the spread-model LOFO
re-run (`scripts/auc_intervals.py`) and is independently unit-tested
(`tests/test_auc_stats.py`) without needing the (git-ignored) FIRMS bundle.

DeLong variance uses the fast midrank algorithm (Sun & Xu 2014; DeLong et al.
1988): for a single classifier with ``m`` positives and ``n`` negatives,

    AUC = (Σ midrank(pos in pooled) − m(m+1)/2) / (m·n)
    Var(AUC) = S10/m + S01/n

with ``S10 = var(V10)``, ``S01 = var(V01)`` over the per-case structural
components. This matches scikit-learn's AUC and gives an analytic SE, so the
per-fold CIs (each fold has thousands of cells) are well-powered — the stronger
evidence than the n=6 mean-of-folds interval.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


# ---------------------------------------------------------------------------
# DeLong AUC variance (fast midrank)
# ---------------------------------------------------------------------------


def _midrank(x: np.ndarray) -> np.ndarray:
    """1-based average (mid) ranks of ``x``, ties shared — the DeLong midrank."""
    x = np.asarray(x, dtype=float)
    order = np.argsort(x, kind="mergesort")
    z = x[order]
    n = len(x)
    t = np.zeros(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j < n and z[j] == z[i]:
            j += 1
        t[i:j] = 0.5 * (i + j - 1) + 1.0   # mean of the 1-based ranks i+1..j
        i = j
    out = np.empty(n, dtype=float)
    out[order] = t
    return out


def delong_auc_variance(y_true, y_score) -> tuple[float, float]:
    """Return ``(auc, variance)`` via the fast single-classifier DeLong estimator.

    ``y_true`` is 0/1; ``y_score`` is the predicted score. Raises ``ValueError``
    if either class is absent (AUC undefined).
    """
    y = np.asarray(y_true).astype(int)
    s = np.asarray(y_score, dtype=float)
    if y.min() == y.max():
        raise ValueError("AUC undefined: only one class present")
    pos = s[y == 1]
    neg = s[y == 0]
    m, n = len(pos), len(neg)
    tx = _midrank(pos)
    ty = _midrank(neg)
    tz = _midrank(np.concatenate([pos, neg]))
    auc = tz[:m].sum() / (m * n) - (m + 1.0) / (2.0 * n)
    v10 = (tz[:m] - tx) / n                 # structural component over positives
    v01 = 1.0 - (tz[m:] - ty) / m           # ... over negatives
    s10 = np.var(v10, ddof=1) if m > 1 else 0.0
    s01 = np.var(v01, ddof=1) if n > 1 else 0.0
    var = s10 / m + s01 / n
    return float(auc), float(max(var, 0.0))


# ---------------------------------------------------------------------------
# Per-fold CI + significance vs a reference (e.g. 0.5)
# ---------------------------------------------------------------------------


@dataclass
class AucCI:
    auc: float
    se: float
    ci_low: float
    ci_high: float
    n: int
    n_pos: int

    def as_dict(self) -> dict:
        return {"auc": round(self.auc, 4), "se": round(self.se, 4),
                "ci95": [round(self.ci_low, 4), round(self.ci_high, 4)],
                "n": self.n, "n_pos": self.n_pos}


def _z_for(alpha: float) -> float:
    from scipy.stats import norm
    return float(norm.ppf(1.0 - alpha / 2.0))


def delong_ci(y_true, y_score, *, alpha: float = 0.05, logit: bool = True) -> AucCI:
    """DeLong (1−alpha) CI for one AUC.

    With ``logit=True`` the interval is built on the logit scale and mapped back,
    so it never leaves [0, 1] and is better-behaved for high AUCs — the standard
    choice for ROC-AUC CIs.
    """
    auc, var = delong_auc_variance(y_true, y_score)
    se = math.sqrt(var)
    z = _z_for(alpha)
    if logit and 0.0 < auc < 1.0 and se > 0:
        eta = math.log(auc / (1.0 - auc))
        se_eta = se / (auc * (1.0 - auc))
        lo = 1.0 / (1.0 + math.exp(-(eta - z * se_eta)))
        hi = 1.0 / (1.0 + math.exp(-(eta + z * se_eta)))
    else:
        lo, hi = max(0.0, auc - z * se), min(1.0, auc + z * se)
    y = np.asarray(y_true).astype(int)
    return AucCI(auc=auc, se=se, ci_low=lo, ci_high=hi, n=len(y), n_pos=int(y.sum()))


def delong_significance(y_true, y_score, *, ref: float = 0.5) -> dict:
    """DeLong z-test of H0: AUC == ``ref`` (two-sided). Returns auc, se, z, p."""
    from scipy.stats import norm
    auc, var = delong_auc_variance(y_true, y_score)
    se = math.sqrt(var)
    if se == 0:
        z = math.inf if auc != ref else 0.0
        p = 0.0 if auc != ref else 1.0
    else:
        z = (auc - ref) / se
        p = float(2.0 * norm.sf(abs(z)))
    return {"auc": auc, "se": se, "z": z, "p_value": p, "ref": ref}


# ---------------------------------------------------------------------------
# Bootstrap CI (for the pooled AUC — labelled pooled, NOT the generalization fig)
# ---------------------------------------------------------------------------


def bootstrap_auc_ci(y_true, y_score, *, n_boot: int = 1000, alpha: float = 0.05,
                     seed: int = 20250603, stratified: bool = True) -> dict:
    """Percentile bootstrap CI for AUC. Stratified resampling preserves the rare
    positive base rate so the resamples stay well-defined."""
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y_true).astype(int)
    s = np.asarray(y_score, dtype=float)
    rng = np.random.default_rng(seed)
    pos_idx = np.flatnonzero(y == 1)
    neg_idx = np.flatnonzero(y == 0)
    boots = np.empty(n_boot, dtype=float)
    k = 0
    for _ in range(n_boot):
        if stratified:
            bi = np.concatenate([rng.choice(pos_idx, len(pos_idx), replace=True),
                                 rng.choice(neg_idx, len(neg_idx), replace=True)])
        else:
            bi = rng.integers(0, len(y), len(y))
        yb = y[bi]
        if yb.min() == yb.max():
            continue
        boots[k] = roc_auc_score(yb, s[bi])
        k += 1
    boots = boots[:k]
    lo = float(np.quantile(boots, alpha / 2.0))
    hi = float(np.quantile(boots, 1.0 - alpha / 2.0))
    return {"auc": float(roc_auc_score(y, s)), "ci95": [lo, hi],
            "n_boot_effective": int(k), "seed": seed, "method": "percentile bootstrap"}


# ---------------------------------------------------------------------------
# Label-permutation test of H0: AUC == 0.5
# ---------------------------------------------------------------------------


def permutation_test_auc(y_true, y_score, *, n_perm: int = 1000,
                         seed: int = 20250603) -> dict:
    """One-sided permutation test (H0: scores carry no rank info → AUC≈0.5).

    p = (1 + #{permuted AUC ≥ observed}) / (1 + n_perm)  (add-one, never 0)."""
    from sklearn.metrics import roc_auc_score
    y = np.asarray(y_true).astype(int)
    s = np.asarray(y_score, dtype=float)
    observed = float(roc_auc_score(y, s))
    rng = np.random.default_rng(seed)
    ge = 0
    for _ in range(n_perm):
        if roc_auc_score(rng.permutation(y), s) >= observed:
            ge += 1
    return {"auc": observed, "p_value": (1.0 + ge) / (1.0 + n_perm),
            "n_perm": n_perm, "seed": seed, "alternative": "auc > 0.5"}


# ---------------------------------------------------------------------------
# Mean-of-folds interval (small-sample t; the n=6 caveat lives here)
# ---------------------------------------------------------------------------


def mean_of_folds_interval(aucs, *, alpha: float = 0.05) -> dict:
    """t-based CI on the mean of per-fold AUCs. Reports n and flags small samples.

    With only ~6 fires this is a **small-sample** interval — the per-fold DeLong
    CIs are the stronger evidence; this is reported with that caveat, never as a
    tight generalization bound."""
    from scipy.stats import t
    a = np.asarray([x for x in aucs if x is not None], dtype=float)
    n = len(a)
    mean = float(np.mean(a)) if n else float("nan")
    sd = float(np.std(a, ddof=1)) if n > 1 else float("nan")
    if n > 1:
        half = float(t.ppf(1.0 - alpha / 2.0, n - 1)) * sd / math.sqrt(n)
        ci = [mean - half, mean + half]
    else:
        ci = [float("nan"), float("nan")]
    return {"mean": mean, "sd": sd, "n": n, "ci95": ci,
            "small_sample": n <= 12,
            "caveat": ("n=%d folds — small-sample t interval; the per-fold DeLong "
                       "CIs are the stronger evidence" % n)}


__all__ = [
    "delong_auc_variance",
    "AucCI",
    "delong_ci",
    "delong_significance",
    "bootstrap_auc_ci",
    "permutation_test_auc",
    "mean_of_folds_interval",
]
