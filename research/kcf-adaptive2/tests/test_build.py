import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_data as b
from reach import NEVER

FEATS = ["area_known_km2", "age_h", "g1", "g3", "g6", "g12", "g24"]


def synth(seed, n=60, T=80):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:n, :n]
    d = np.hypot(yy - n / 2, xx - n / 2) + rng.normal(0, 1.5, (n, n))
    A = np.floor(d * T / d.max() * 0.9).astype(np.int32)
    A[d > 0.8 * d.max()] = NEVER
    return A


def test_L1_features_ignore_future():
    for seed in range(3):
        A = synth(seed)
        ts = lambda t: pd.Timestamp("2020-01-01") + pd.Timedelta(hours=int(t))
        first, last = int(A[A != NEVER].min()), int(A[A != NEVER].max())
        t_test = first + 30
        r0, c0 = b.process(A, first, last, ts, True, hours=set(range(first, t_test + 1)))
        B = A.copy()
        fut = (B > t_test) & (B != NEVER)
        rng = np.random.default_rng(99)
        B[fut] = rng.integers(t_test + 1, last + 20, fut.sum())      # scramble the future arrival hours
        r1, c1 = b.process(B, first, last + 20, ts, True, hours=set(range(first, t_test + 1)))
        a0, a1 = pd.DataFrame(r0), pd.DataFrame(r1)
        assert len(a0) == len(a1) > 10
        for c in FEATS:
            np.testing.assert_array_equal(a0[c].values, a1[c].values)
        np.testing.assert_array_equal(c0, c1)           # area curves also depend on K_t only
        assert not np.allclose(a0.reach5_km.values, a1.reach5_km.values)   # the outcome does change (sanity)
