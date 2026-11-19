"""Leakage tests (PROTOCOL section 4): the margin issued at hour t must not change when everything after t changes."""
import copy
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lib4 as L  # noqa: E402

FIRES, CURVE = L.load()


def scramble_after(f, t, rng):
    g = copy.deepcopy(f)
    for j in range(g.T):
        for h in range(L.NL):
            if j + L.LEADS[h] > t and np.isfinite(g.S[j, h]):
                g.S[j, h] = rng.uniform(0, 30)
                g.Ss[j, h] = rng.uniform(0, 30)
    for v in g.obs:
        g.obs[v][t + g.obs_off + 1:] = rng.uniform(0, 40, size=len(g.obs[v]) - (t + g.obs_off + 1))
    g.deficit[t + 1:] = rng.uniform(0, 5, size=g.T - t - 1)
    for c in ("gust_ms", "w850_ms"):
        x = g.X[c]
        x[t + 1:] = np.where(np.isfinite(x[t + 1:]), rng.uniform(1, 40, size=g.T - t - 1), np.nan)
    return g


@pytest.mark.parametrize("mode", ["targeted", "all"])
@pytest.mark.parametrize("name", ["KFS_02", "KFS_04"])
def test_no_future(mode, name):
    f = FIRES["KR"][name]
    ks = np.full(L.NL, 0.004)          # small k so that many hours are misses and every branch runs
    rng = np.random.default_rng(1)
    base, st = L.correct(f, ks, "gust_ms", mode, 12, 6, return_state=True)
    assert (st[:, 5] > 0).any() and (st[:, 4] >= 0).any(), "test must exercise the update"
    for t in (20, 47, 90):
        g = scramble_after(f, t, rng)
        q = L.correct(g, ks, "gust_ms", mode, 12, 6)
        assert np.array_equal(base[:t + 1], q[:t + 1], equal_nan=True)


def test_leaky_version_fails():
    """A deliberately leaky margin (uses the not-yet-matured outcome) must fail the same check."""
    f = FIRES["KR"]["KFS_02"]
    rng = np.random.default_rng(2)
    leaky = lambda x: np.nan_to_num(x.S) + 1.0      # noqa: E731
    g = scramble_after(f, 47, rng)
    assert not np.array_equal(leaky(f)[:48], leaky(g)[:48])


def test_shapley_efficiency():
    """Shares sum to v(all) - v(none) = v(all) for a miss."""
    rng = np.random.default_rng(3)
    n = 500
    S = rng.uniform(1, 10, n)
    q = S * rng.uniform(0.2, 0.99, n)
    sh, vall = L.shapley(S, S * rng.uniform(0.3, 1, n), q, rng.uniform(0.5, 2, n), rng.uniform(0.8, 1.5, n),
                         rng.uniform(0.5, 2.5, n), rng.uniform(1, 3, n))
    assert np.allclose(sh.sum(1), vall)
