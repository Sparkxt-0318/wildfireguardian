"""L2/L3 (PROTOCOL 6): adaptive methods never use outcomes that are not yet known; a leaky variant must fail the same test."""
import os, sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lib, methods2 as m2

WORK = os.environ.get("KCF2_WORK", "/tmp/w/work")
pytestmark = pytest.mark.skipif(not Path(WORK, "hours_geom.csv.gz").exists(), reason="no data")


@pytest.fixture(scope="module")
def D():
    return lib.Data(5, WORK)


def scrambled(D, rows_fire, i0):
    """Copy of D whose outcomes S_j with t_j + h > t_i0 (not yet known at row i0) are replaced by noise."""
    import copy
    E = copy.copy(D)
    th = D.t.astype("datetime64[h]").astype(np.int64)
    S = D.S.copy()
    rng = np.random.default_rng(7)
    bad = rows_fire[th[rows_fire] + D.h > th[i0]]
    S[bad] = rng.uniform(0, 30, len(bad))
    E.S = S
    return E


def _check(D, method, model, fire_idx, leak=False):
    rows = np.flatnonzero(D.fid == fire_idx)
    base = method.predict(model, D, rows) if not leak else method.predict(model, D, rows, leak=True)
    th = D.t.astype("datetime64[h]").astype(np.int64)
    fails = 0
    for i0 in rows[[len(rows) // 4, len(rows) // 2, 3 * len(rows) // 4]]:
        E = scrambled(D, rows, i0)
        alt = method.predict(model, E, rows) if not leak else method.predict(model, E, rows, leak=True)
        upto = th[rows] <= th[i0]
        # META adapts in 6-hour blocks on information known at the block start, so compare rows up to i0 only
        if not np.array_equal(base[upto], alt[upto]):
            fails += 1
    return fails


def _fit(D, method, cfg):
    dev = [f for f in D.fires if D.product[D.fire == f][0] == "GOFER"]
    tr = D.rows_of(dev[:12])
    return method.fit(cfg, D, tr), [D.fires.index(f) for f in dev[12:17]]


def test_kalman_future_scramble_invariant(D):
    k = m2.Kalman()
    model, fires = _fit(D, k, dict(ridge=1.0, Q=1e-3))
    assert sum(_check(D, k, model, f) for f in fires) == 0


def test_kalman_leaky_control_fails(D):
    k = m2.Kalman()
    model, fires = _fit(D, k, dict(ridge=1.0, Q=1e-3))
    assert sum(_check(D, k, model, f, leak=True) for f in fires) > 0


def test_meta_future_scramble_invariant(D):
    m = m2.Meta()
    model, fires = _fit(D, m, dict(tau=0.9, arch="lin"))
    assert sum(_check(D, m, model, f) for f in fires) == 0
