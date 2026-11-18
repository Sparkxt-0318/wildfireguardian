"""Brute-force checks of the score, threshold and AUROC helpers in abstain.py (synthetic data only)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import abstain as A  # noqa: E402


def test_tail_fractions_match_brute_force():
    rng = np.random.default_rng(0)
    ref = rng.integers(0, 6, (50, 5)).astype(float)
    q = rng.integers(-1, 7, (30, 5)).astype(float)
    ge, le = A.tail_fractions(ref, q)
    for i in range(30):
        for j in range(5):
            assert np.isclose(ge[i, j], np.mean(ref[:, j] >= q[i, j]))
            assert np.isclose(le[i, j], np.mean(ref[:, j] <= q[i, j]))


def test_thresholds_rule():
    s = np.arange(100) / 100.0
    w = np.full(100, 0.01)
    tau = A.thresholds(s, w, [0.0, 0.05, 0.5, 1.0])
    assert tau[0] == -1.0 and np.isclose(tau[1], 0.04) and np.isclose(tau[2], 0.49) and np.isclose(tau[3], 0.99)
    # ties: weight at the tied minimum exceeds beta -> nothing abstains
    s2 = np.r_[np.zeros(10), np.ones(90)]
    assert A.thresholds(s2, np.full(100, 0.01), [0.05])[0] == -1.0
    # brute force on random weighted data
    rng = np.random.default_rng(1)
    s3 = rng.integers(0, 20, 300) / 20.0
    w3 = rng.random(300)
    w3 /= w3.sum()
    for b in (0.01, 0.05, 0.2, 0.7):
        t = A.thresholds(s3, w3, [b])[0]
        ok = [v for v in np.unique(s3) if w3[s3 <= v].sum() <= b + 1e-12]
        assert (t == -1.0 and not ok) or np.isclose(t, max(ok))


def test_weighted_auc_equals_mann_whitney():
    rng = np.random.default_rng(2)
    s = rng.integers(0, 15, 400).astype(float)
    y = rng.random(400) < 0.3
    w = np.ones(400)
    pos, neg = s[y], s[~y]
    mw = np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg])
    assert np.isclose(A.wauc(s, y, w), mw)
    # weights: duplicating rows equals weight 2
    w2 = rng.integers(1, 3, 400).astype(float)
    sd, yd = np.repeat(s, w2.astype(int)), np.repeat(y, w2.astype(int))
    assert np.isclose(A.wauc(s, y, w2), A.wauc(sd, yd, np.ones(sd.size)))


def test_two_sided_score():
    pge = np.array([[0.02, 0.9], [0.6, 0.5]])
    ple = np.array([[0.99, 0.2], [0.5, 0.7]])
    s1, _ = A.score_from(pge, ple, False)
    s2, _ = A.score_from(pge, ple, True)
    assert np.allclose(s1, [0.02, 0.5]) and np.allclose(s2, [0.04, 1.0])
