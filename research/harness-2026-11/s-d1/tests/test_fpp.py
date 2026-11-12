"""Tests for the first-passage sampler and reference CA.

Run from the repository root:
    python -m pytest research/harness-2026-11/s-d1/tests -q

Statistical assertions use binomial standard errors with a 5-sigma bound so that
false failures are ~1e-6 per assertion with fixed seeds (the seeds make them deterministic).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from fpp import cellular_automaton, first_passage, stencil_offsets, stencil_rate  # noqa: E402

REPO = Path(__file__).resolve().parents[4]


def channel(k, dy, dx):
    r = k // 2
    return (dy + r) * k + (dx + r)


def chain_kernel(H, W, links, k=3):
    """K with nonzero coefficient only for listed (target, source, rate) links."""
    K = np.zeros((k * k, H, W))
    for (ty, tx), (sy, sx), rate in links:
        K[channel(k, sy - ty, sx - tx), ty, tx] = rate
    return K


def within(p_hat, p, n, sigmas=5.0):
    se = math.sqrt(max(p * (1 - p), 1e-12) / n)
    return abs(p_hat - p) <= sigmas * se + 1e-12


N = 40000


def test_single_edge_constant_rate_both_exact():
    # source (1,1) -> target (1,2), rate 0.7/h
    K = chain_kernel(3, 4, [((1, 2), (1, 1), 0.7)])
    init = np.zeros((3, 4), bool)
    init[1, 1] = True
    hs = [0.5, 1.0, 3.0]
    c, _ = first_passage(K, init, hs, n_samples=N, seed=1)
    for i, h in enumerate(hs):
        assert within(c[i, 1, 2] / N, 1 - math.exp(-0.7 * h), N)
    assert c[:, [0, 2], :].sum() == 0  # no other links
    ca = cellular_automaton(K, init, [1.0, 3.0], dt=1.0, n_samples=N, seed=2)
    for i, h in enumerate([1.0, 3.0]):
        assert within(ca[i, 1, 2] / N, 1 - math.exp(-0.7 * h), N)


def test_competing_sources_superpose():
    K = chain_kernel(1, 3, [((0, 1), (0, 0), 0.3), ((0, 1), (0, 2), 0.5)])
    init = np.array([[True, False, True]])
    c, _ = first_passage(K, init, [1.0, 2.0], n_samples=N, seed=3)
    for i, h in enumerate([1.0, 2.0]):
        assert within(c[i, 0, 1] / N, 1 - math.exp(-0.8 * h), N)


def hypoexp_cdf(a, b, t):
    return 1 - (b * math.exp(-a * t) - a * math.exp(-b * t)) / (b - a)


def test_two_hop_chain_fpp_exact_hourly_ca_biased_fine_ca_converges():
    a, b = 1.3, 0.9
    K = chain_kernel(1, 3, [((0, 1), (0, 0), a), ((0, 2), (0, 1), b)])
    init = np.array([[True, False, False]])
    t = 2.0
    exact = hypoexp_cdf(a, b, t)
    c, _ = first_passage(K, init, [t], n_samples=N, seed=4)
    assert within(c[0, 0, 2] / N, exact, N)
    # Hourly CA: the middle cell can only emit from the following hour.
    # Exact value: P(B by 1h) * P(C ignites in hour 2 | B burned at hour 1).
    hourly_exact = (1 - math.exp(-a)) * (1 - math.exp(-b))
    ca1 = cellular_automaton(K, init, [t], dt=1.0, n_samples=N, seed=5)
    assert within(ca1[0, 0, 2] / N, hourly_exact, N)
    assert hourly_exact < exact - 0.1
    errors = []
    for m in (1, 4, 16):
        ca = cellular_automaton(K, init, [t], dt=1.0 / m, n_samples=N, seed=10 + m)
        errors.append(abs(ca[0, 0, 2] / N - exact))
    se = math.sqrt(exact * (1 - exact) / N)
    # O(dt) convergence: error shrinks by >= 3x per 4x refinement, until MC noise.
    assert errors[1] < errors[0] / 3
    assert errors[2] < max(errors[1] / 3, 5 * se)
    assert errors[2] < 5 * se + 0.02


def test_time_varying_rate_integrated_hazard():
    # Rates by hour: 0.2, 0.0, 1.5, then 0.5 forever.
    rates = [0.2, 0.0, 1.5, 0.5]
    K = np.stack([chain_kernel(1, 2, [((0, 1), (0, 0), r)]) for r in rates])
    init = np.array([[True, False]])
    hs = [0.5, 1.5, 2.5, 5.0]
    cum = lambda t: sum(r * max(0.0, min(t, j + 1 if j < 3 else 1e9) - j) for j, r in enumerate(rates))
    c, _ = first_passage(K, init, hs, n_samples=N, seed=6)
    for i, h in enumerate(hs):
        assert within(c[i, 0, 1] / N, 1 - math.exp(-cum(h)), N)
    ca = cellular_automaton(K, init, [1.0, 3.0, 5.0], dt=0.5, n_samples=N, seed=7)
    for i, h in enumerate([1.0, 3.0, 5.0]):
        assert within(ca[i, 0, 1] / N, 1 - math.exp(-cum(h)), N)


def test_time_varying_two_hop_matches_fine_ca():
    # Time-dependent Dijkstra must equal the dt->0 CA with hourly-varying kernels.
    rng = np.random.default_rng(0)
    K = rng.uniform(0, 0.25, size=(3, 9, 6, 6))
    K[:, 4] = 0
    init = np.zeros((6, 6), bool)
    init[0, 0] = True
    n = 20000
    c, _ = first_passage(K, init, [3.0], n_samples=n, seed=8)
    ca = cellular_automaton(K, init, [3.0], dt=1 / 32, n_samples=n, seed=9)
    p_f = c[0] / n
    p_c = ca[0] / n
    se = np.sqrt((p_f * (1 - p_f) + p_c * (1 - p_c)) / n) + 1e-9
    z = (p_f - p_c) / se
    # dt = 1/32 leaves an O(dt) bias; require agreement within 5 sigma + 0.01 everywhere.
    assert np.all(np.abs(p_f - p_c) <= 5 * se + 0.01), np.abs(z).max()


def test_arrival_field_consistency():
    rng = np.random.default_rng(1)
    K = rng.uniform(0, 0.3, size=(25, 8, 8))
    K[12] = 0
    init = np.zeros((8, 8), bool)
    init[4, 4] = True
    c, arr = first_passage(K, init, [1.0, 4.0], n_samples=50, seed=10, keep_arrivals=50)
    assert np.all(arr[:, 4, 4] == 0)
    from_arr = [(arr <= h).sum(axis=0) - 50 * init for h in (1.0, 4.0)]
    assert np.array_equal(np.stack(from_arr), c)
    # Each burned non-initial cell must have an in-neighbour that burned strictly earlier.
    offs = stencil_offsets(5)
    for m in range(50):
        a = arr[m]
        for y in range(8):
            for x in range(8):
                if init[y, x] or not np.isfinite(a[y, x]):
                    continue
                earlier = [a[y + dy, x + dx] < a[y, x] for (dy, dx), kk in zip(offs, K[:, y, x])
                           if kk > 0 and 0 <= y + dy < 8 and 0 <= x + dx < 8]
                assert any(earlier)


def test_seed_reproducible():
    rng = np.random.default_rng(2)
    K = rng.uniform(0, 0.3, size=(9, 10, 10))
    init = np.zeros((10, 10), bool)
    init[5, 5] = True
    a, _ = first_passage(K, init, [3.0], n_samples=100, seed=42)
    b, _ = first_passage(K, init, [3.0], n_samples=100, seed=42)
    assert np.array_equal(a, b)


torch = pytest.importorskip("torch")


def _forecast_module():
    sys.path.insert(0, str(REPO / "forecast"))
    from wildfire.models import new_burn_probability
    return new_burn_probability


def test_offset_convention_and_rate_match_forecast_new_burn_probability():
    new_burn_probability = _forecast_module()
    rng = np.random.default_rng(3)
    for k in (3, 5, 9):
        H, W = 11, 13
        K = rng.uniform(0, 0.4, size=(k * k, H, W))
        K[(k * k) // 2] = 0
        burned = rng.random((H, W)) < 0.2
        out = new_burn_probability(torch.tensor(burned[None, None], dtype=torch.float64),
                                   torch.tensor(K[None]), dt_hours=1.0, boundary="zero")
        lam = stencil_rate(K, stencil_offsets(k), burned[None].astype(float))[0]
        ref_rate = out.rate[0, 0].numpy()
        assert np.allclose(lam, ref_rate, rtol=1e-12, atol=1e-12)
        q = np.where(burned, 0, -np.expm1(-lam))
        assert np.allclose(q, out.probability[0, 0].numpy(), rtol=1e-12, atol=1e-12)


def test_first_passage_single_source_direction_matches_forecast():
    # Source at (5,5); only offset (dy,dx)=(+2,-1) nonzero everywhere: the forecast says
    # target (y,x) reads source (y+2, x-1), i.e. target = (3, 6).
    new_burn_probability = _forecast_module()
    k = 5
    K = np.zeros((k * k, 11, 11))
    K[channel(k, 2, -1)] = 5.0
    init = np.zeros((11, 11), bool)
    init[5, 5] = True
    out = new_burn_probability(torch.tensor(init[None, None], dtype=torch.float64),
                               torch.tensor(K[None]), boundary="zero")
    target = np.argwhere(out.probability[0, 0].numpy() > 0)
    assert target.tolist() == [[3, 6]]
    c, _ = first_passage(K, init, [0.3], n_samples=200, seed=0)
    assert c[0, 3, 6] > 150
    burned = {tuple(v) for v in np.argwhere(c[0] > 0).tolist()}
    assert burned <= {(3, 6), (1, 7)}  # only along the (-2, +1) ray, inside the grid
