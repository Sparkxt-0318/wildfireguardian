import numpy as np
import pytest
from scipy.stats import norm

from soft_labels import (hard_window_labels, normal_interval_probability, soft_next_hour_targets,
                         soft_window_labels)

RNG = np.random.default_rng(20261112)


def test_windows_sum_to_probability_of_their_union():
    mean = RNG.uniform(-5, 60, size=500)
    sd = RNG.uniform(0.01, 12, size=500)
    edges = np.arange(0.0, 49.0)
    p = soft_window_labels(mean, sd, edges)
    expected = norm.cdf(48, mean, sd) - norm.cdf(0, mean, sd)
    np.testing.assert_allclose(p.sum(axis=0), expected, atol=1e-12)
    assert (p >= 0).all() and (p <= 1).all()


def test_truncated_support_sums_to_one():
    mean = RNG.uniform(-20, 80, size=400)
    sd = RNG.uniform(0.01, 30, size=400)
    edges = np.arange(0.0, 49.0)
    p = soft_window_labels(mean, sd, edges, support=(0.0, 48.0))
    np.testing.assert_allclose(p.sum(axis=0), 1.0, atol=1e-10)


def test_zero_sd_is_exactly_the_loader_hard_label():
    # Includes values exactly on hour boundaries: (t-1, t] convention.
    mean = np.array([0.0, 0.5, 1.0, 1.0000001, 2.999999, 3.0, 47.0, 48.0, 48.5, np.nan])
    edges = np.arange(0.0, 49.0)
    hard = hard_window_labels(mean, edges)
    soft = soft_window_labels(np.nan_to_num(mean, nan=-1e9), np.zeros_like(mean), edges)
    np.testing.assert_array_equal(soft[:, :-1], hard[:, :-1])
    # Loader rule from data.py: newly = (arrival > t-1) & (arrival <= t) at elapsed t.
    for k in range(48):
        t = edges[k + 1]
        loader = ((mean > t - 1) & (mean <= t)).astype(float)
        np.testing.assert_array_equal(hard[k], loader)


@pytest.mark.parametrize("sd", [1e-3, 1e-5, 1e-8])
def test_small_sd_converges_to_hard_label(sd):
    mean = RNG.uniform(0.2, 47.8, size=1000)
    # Keep means at least 50 sd from any boundary so the limit is sharp.
    frac = mean - np.floor(mean)
    mean = np.where((frac < 0.01) | (frac > 0.99), mean + 0.5, mean)
    edges = np.arange(0.0, 49.0)
    soft = soft_window_labels(mean, np.full_like(mean, sd), edges)
    hard = hard_window_labels(mean, edges)
    assert np.abs(soft - hard).max() < 1e-9


def test_conditional_hazard_telescopes_to_survival():
    mean = RNG.uniform(0, 48, size=300)
    sd = RNG.uniform(0.5, 10, size=300)
    edges = np.arange(0.0, 49.0)
    h = soft_window_labels(mean, sd, edges, conditional=True)
    # Undefined (NaN) only once the cell is no longer at risk: survival at the
    # window start underflowed to zero, so the subsequent survival is zero too.
    start_survival = norm.sf(edges[:-1, None], mean, sd)
    np.testing.assert_array_equal(np.isnan(h), start_survival == 0)
    survive = np.cumprod(1 - np.nan_to_num(h, nan=1.0), axis=0)
    expected = norm.sf(edges[1:, None], mean, sd) / norm.sf(0.0, mean, sd)
    np.testing.assert_allclose(survive, expected, rtol=1e-8, atol=1e-12)


def test_matches_monte_carlo():
    mean, sd = np.array([10.3, 30.0]), np.array([2.5, 7.0])
    draws = RNG.normal(mean, sd, size=(400_000, 2))
    edges = np.array([5.0, 9.0, 10.0, 11.0, 20.0, 35.0])
    p = soft_window_labels(mean, sd, edges)
    for k in range(len(edges) - 1):
        mc = ((draws > edges[k]) & (draws <= edges[k + 1])).mean(axis=0)
        np.testing.assert_allclose(p[k], mc, atol=4e-3)


def test_upper_tail_is_not_lost_to_cancellation():
    p = normal_interval_probability(9.0, 10.0, 0.0, 1.0)
    assert p == pytest.approx(norm.sf(9) - norm.sf(10), rel=1e-6)
    assert p > 0


def test_invalid_inputs_give_nan():
    p = normal_interval_probability(0.0, 1.0, np.array([np.nan, 0.5, 0.5]), np.array([1.0, -1.0, np.nan]))
    assert np.isnan(p).all()
    with pytest.raises(ValueError):
        soft_window_labels([1.0], [1.0], [0.0, 0.0])


def test_row_targets_agree_with_window_labels():
    mean = RNG.uniform(0, 48, size=200)
    sd = RNG.uniform(0.0, 6, size=200)
    sd[:20] = 0.0
    hours = RNG.integers(0, 48, size=200).astype(float)
    edges = np.arange(0.0, 49.0)
    for conditional in (False, True):
        grid = soft_window_labels(mean, sd, edges, support=(0.0, 48.0), conditional=conditional)
        rows = soft_next_hour_targets(mean, sd, hours, support=(0.0, 48.0), conditional=conditional)
        expected = grid[hours.astype(int), np.arange(200)]
        np.testing.assert_allclose(rows, expected, equal_nan=True, atol=1e-12)
