import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import beta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reach import (CELL_KM, NEVER, arrival_from_stack, clopper_pearson, component_reach,  # noqa: E402
                   conformal_R, weighted_quantile_by_fire)


def grid():
    return np.zeros((60, 60), bool)


def test_contiguous_advance_distance():
    known = grid(); known[30, 10] = True
    new = grid(); new[30, 11:21] = True          # 10 cells east, touching
    r, d, m = component_reach(known, new, (5.0,))
    assert r[5.0] == pytest.approx(10 * CELL_KM)
    assert m.sum() == 10 and d.max() == pytest.approx(10 * CELL_KM)


def test_separate_fire_rule():
    known = grid(); known[30, 10] = True
    new = grid()
    new[30, 12] = True                            # spot 2 cells = 0.75 km away: spread
    new[30, 30:33] = True                         # nearest 20 cells = 7.5 km: separate fire under 5 km rule
    r, _, _ = component_reach(known, new, (5.0, 2.0, np.inf))
    assert r[5.0] == pytest.approx(2 * CELL_KM)
    assert r[2.0] == pytest.approx(2 * CELL_KM)
    assert r[np.inf] == pytest.approx(22 * CELL_KM)


def test_spot_between_2_and_5_km():
    known = grid(); known[30, 10] = True
    new = grid(); new[30, 18] = True              # 8 cells = 3 km
    r, _, _ = component_reach(known, new, (5.0, 2.0))
    assert r[5.0] == pytest.approx(3.0) and r[2.0] == 0.0


def test_component_judged_by_nearest_cell():
    known = grid(); known[30, 10] = True
    new = grid(); new[30, 11:40] = True           # long run touching the perimeter: all counts
    r, _, _ = component_reach(known, new, (5.0,))
    assert r[5.0] == pytest.approx(29 * CELL_KM)


def test_empty_new_is_zero():
    known = grid(); known[5, 5] = True
    r, d, _ = component_reach(known, grid(), (5.0,))
    assert r[5.0] == 0.0 and d.size == 0


def test_arrival_from_stack_cumulative_first_hour():
    a = grid(); a[1, 1] = True
    b = grid(); b[1, 1] = b[2, 2] = True
    A = arrival_from_stack([a, b, grid()])
    assert A[1, 1] == 0 and A[2, 2] == 1 and A[3, 3] == NEVER


def test_conformal_order_statistic():
    scores = [np.array([float(i)]) for i in range(1, 20)]   # 19 fires, one hour each
    R, Rs, n = conformal_R(scores, 0.1, draws=10)
    assert n == 19 and R == 18.0                             # ceil(20*0.9)=18th smallest
    R, _, _ = conformal_R(scores[:5], 0.1, draws=10)
    assert R == np.inf                                        # too few fires for 90%


def test_conformal_marginal_coverage_simulation():
    rng = np.random.default_rng(0)
    misses = []
    for _ in range(300):
        fires = [rng.lognormal(rng.normal(0, 1), 1, size=rng.integers(5, 50)) for _ in range(21)]
        R, _, _ = conformal_R(fires[:20], 0.2, draws=50, seed=int(rng.integers(1e9)))
        misses.append(np.mean(fires[20] > R))
    assert np.mean(misses) <= 0.2 + 0.03


def test_clopper_pearson_known_values():
    lo, hi = clopper_pearson(3, 28)
    assert lo == pytest.approx(beta.ppf(0.025, 3, 26)) and hi == pytest.approx(beta.ppf(0.975, 4, 25))
    assert clopper_pearson(0, 10)[0] == 0.0 and clopper_pearson(10, 10)[1] == 1.0


def test_weighted_quantile_fire_equal_weight():
    # fire A: 1000 values at 1.0; fire B: one value at 10.0 -> 50% weight each
    q = weighted_quantile_by_fire([np.ones(1000), np.array([10.0])], 0.6)
    assert q == 10.0
