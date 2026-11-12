"""Null calibration of lag_persistence_v2 under iid values (Owen's probe): the excess must be unbiased, raw and detrended."""
import numpy as np

import lag_persistence_v2 as L


def _fake(rng, fires=25, n=8):
    return {f"F{i}": dict(rank=rng.normal(size=n), log_ratio=rng.normal(size=n), index=np.arange(n, dtype=float),
                          run=np.ones(n, int)) for i in range(fires)}


def test_detrended_excess_unbiased_under_iid():
    rng = np.random.default_rng(0)
    ex = {False: [], True: []}
    for _ in range(150):
        per = _fake(rng)
        fires = sorted(per)
        for det in (False, True):
            obs = L.stat(per, fires, "rank", 1, det, False)
            null = np.mean([L.stat(per, fires, "rank", 1, det, False, rng) for _ in range(40)])
            ex[det].append(obs - null)
    for det in (False, True):
        m, se = np.mean(ex[det]), np.std(ex[det]) / np.sqrt(len(ex[det]))
        assert abs(m) < 4 * se + 0.01, (det, m, se)
