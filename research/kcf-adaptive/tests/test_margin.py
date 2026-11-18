"""Shape, score/zone agreement and ACI delay (PROTOCOL.md section 5)."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import margin as M  # noqa: E402


def blob(rng, n=40):
    k = np.zeros((n, n), bool)
    k[n // 2 - 4:n // 2 + 3, n // 2 - 6:n // 2 + 5] = True
    k[n // 2 - 8:n // 2 - 3, n // 2:n // 2 + 3] = True
    k &= rng.random((n, n)) > 0.05
    k[n // 2, n // 2] = True
    return k


def test_shape_basics():
    for u in (0, 5, 20, 60, 200):
        e = float(M.eccentricity(u))
        assert 0 <= e < 1
        for k in M.KS:
            assert M.g(1.0, e, k) == pytest.approx(1.0)
            th = np.linspace(-1, 1, 201)
            gg = M.g(th, e, k)
            assert gg.max() <= 1 + 1e-12 and gg.min() > 0
    assert float(M.eccentricity(0)) == 0.0
    assert float(M.length_to_breadth(1e4)) == M.LB_CAP
    assert M.downwind_unit(270) == pytest.approx((1.0, 0.0), abs=1e-12)      # westerly wind blows east
    assert M.downwind_unit(0) == pytest.approx((0.0, -1.0), abs=1e-12)       # northerly wind blows south
    s, d = M.mean_wind([10, 10], [270, 270])
    assert s == pytest.approx(10) and d == pytest.approx(270)


def test_k0_is_euclidean_reach():
    rng = np.random.default_rng(0)
    known = blob(rng)
    cells = np.argwhere(~known)[::7]
    s = M.cell_scores(known, cells, (0.6, 0.8), 0.9, ks=(0.0,))[0]
    d = M.dist_km(known)[cells[:, 0], cells[:, 1]]
    assert np.allclose(s, d, atol=1e-9)


@pytest.mark.parametrize("seed", range(6))
def test_zone_and_score_agree(seed):
    """A cell is inside the zone of size q exactly when its score is <= q; scores are minima over all known cells."""
    rng = np.random.default_rng(seed)
    known = blob(rng)
    d = M.downwind_unit(rng.uniform(0, 360))
    e = float(M.eccentricity(rng.choice([0, 8, 25, 60, 120])))
    cells = np.argwhere(~known)
    sc = M.cell_scores(known, cells, d, e)
    # brute force over every known cell
    kxy = np.argwhere(known)
    to_xy = lambda rc: np.c_[rc[:, 1] * M.CELL_KM, -rc[:, 0] * M.CELL_KM]  # noqa: E731
    brute = M._pairs_min(to_xy(cells), to_xy(kxy), d, e, M.KS)
    assert np.allclose(sc, brute, rtol=1e-12, atol=1e-12)
    for i, k in enumerate(M.KS):
        for q in (0.5, 1.3, 2.9, 5.0):
            z, pad = M.zone(known, q, d, e, k)
            inside = z[cells[:, 0] + pad, cells[:, 1] + pad]
            near = np.abs(sc[i] - q) < 1e-6
            assert np.array_equal(inside[~near], (sc[i] <= q)[~near])
            assert z[pad:-pad, pad:-pad][known].all()


def test_circle_area_matches_zone():
    rng = np.random.default_rng(3)
    known = blob(rng)
    for q in (0.4, 1.0, 2.7, 6.1):
        z, _ = M.zone(known, q)
        assert int(M.circle_areas(known, [q])[0]) == int(z.sum() - known.sum())


def test_zone_points_downwind():
    known = np.zeros((41, 41), bool)
    known[20, 20] = True
    z, pad = M.zone(known, 3.0, M.downwind_unit(270), float(M.eccentricity(60)), 1.0)   # blows east
    rows, cols = np.nonzero(z)
    assert cols.max() - (20 + pad) == 8 and (20 + pad) - cols.min() < 2           # 3 km = 8 cells east, ~0 west


def test_aci_uses_no_outcome_before_it_is_known():
    Q = M.WeightedQuantile([np.arange(1, 101, dtype=float)])
    t = np.arange(50)
    base = np.zeros(50)
    q0, a0, _ = M.aci(t, base, 5, 0.1, 0.05, Q)
    for s in range(50):
        sc = base.copy()
        sc[s:] = 1e6                                    # change the outcome of issue hour s and everything later
        q1, a1, _ = M.aci(t, sc, 5, 0.1, 0.05, Q)
        assert np.array_equal(q1[:s + 5], q0[:s + 5])   # nothing issued before s + h can differ
        assert np.array_equal(a1[:s + 5], a0[:s + 5])
        if s + 5 < 50:
            assert q1[s + 5] != q0[s + 5]               # and the first later hour does react
    qt0 = M.tracker(t, base, 5, 0.1, 0.2, 2.0)
    sc = base.copy(); sc[10:] = 1e6
    qt1 = M.tracker(t, sc, 5, 0.1, 0.2, 2.0)
    assert np.array_equal(qt1[:15], qt0[:15]) and qt1[15] > qt0[15]


def test_aci_update_rule_and_saturation():
    Q = M.WeightedQuantile([np.arange(1, 101, dtype=float)])
    t = np.arange(4)
    q, a, sat = M.aci(t, np.array([1e9, 0.0, 0.0, 0.0]), 1, 0.1, 0.05, Q)
    assert a[0] == pytest.approx(0.1) and a[1] == pytest.approx(0.1 + 0.05 * (0.1 - 1))   # a miss lowers a
    assert a[2] == pytest.approx(a[1] + 0.05 * 0.1) and q[1] > q[0]                      # a hold raises it
    q, a, sat = M.aci(np.arange(40), np.full(40, 1e9), 1, 0.1, 0.05, Q)
    assert sat[-1] and q[-1] == 100.0 and a[-1] < 0                                       # saturates, a not clipped
    assert Q(0.0) == (0.0, False) and Q(-0.2) == (0.0, False)
    assert Q(0.9)[0] == 90.0
    with pytest.raises(ValueError):
        M.tracker(t, np.zeros(4), 1, 0.1, 0.1, 0.0)


def test_nan_scores_never_feed_back():
    Q = M.WeightedQuantile([np.arange(1, 101, dtype=float)])
    t = np.arange(10)
    q, a, _ = M.aci(t, np.full(10, np.nan), 2, 0.1, 0.05, Q)
    assert np.allclose(a, 0.1)
    assert math.isfinite(q[0])
