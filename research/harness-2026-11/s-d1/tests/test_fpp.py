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




def _forecast_module():
    sys.path.insert(0, str(REPO / "forecast"))
    from wildfire.models import new_burn_probability
    return new_burn_probability


def test_offset_convention_and_rate_match_forecast_new_burn_probability():
    torch = pytest.importorskip("torch")  # only the forecast-parity tests need torch
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
    torch = pytest.importorskip("torch")  # only the forecast-parity tests need torch
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


def test_reference_ca_matches_real_forecast_rollout_marginals():
    """Independent hourly CA == wildfire.rollout.simulate (stub predictor with fixed kernels)."""
    torch = pytest.importorskip("torch")  # only the forecast-parity tests need torch
    sys.path.insert(0, str(REPO / "forecast"))
    from wildfire.models import new_burn_probability
    from wildfire.rollout import simulate
    rng = np.random.default_rng(5)
    H = W = 14
    K = rng.uniform(0, 0.12, size=(49, H, W))
    K[24] = 0
    init = np.zeros((H, W), bool)
    init[6:8, 6:8] = True
    kern = torch.tensor(K)

    class Stub(torch.nn.Module):
        channel_names = ("x",)

        def forward(self, states, environment, *, channel_names, burned_area_valid,
                    feature_valid, dt_hours, boundary):
            return new_burn_probability(states, kern.expand(states.shape[0], -1, -1, -1),
                                        dt_hours=dt_hours, burned_area_valid=burned_area_valid,
                                        boundary=boundary)

    n = 2000
    b = torch.tensor(init, dtype=torch.float64)[None]
    env = torch.zeros((1, H, W), dtype=torch.float64)
    out = simulate(Stub(), b, env, channel_names=("x",),
                   burned_area_valid=torch.ones_like(b, dtype=torch.bool),
                   feature_valid=torch.ones_like(env, dtype=torch.bool), hours=[1.0, 3.0],
                   n_samples=n, seed=3, trajectory_batch_size=500, boundary="zero")
    ca = cellular_automaton(K, init, [1.0, 3.0], dt=1.0, n_samples=n, seed=4)
    for i in range(2):
        p_ref = out[i]["details"].probability[0].numpy()
        p_ref = np.where(init, 0, p_ref)
        p_ca = ca[i] / n
        se = np.sqrt((p_ref * (1 - p_ref) + p_ca * (1 - p_ca)) / n) + 1e-9
        assert np.all(np.abs(p_ref - p_ca) <= 5 * se + 1e-9)
    # and the hourly recursion is clearly below first passage at 3 h on this case
    fp, _ = first_passage(K, init, [3.0], n_samples=n, seed=5)
    assert fp[0].sum() / n > ca[1].sum() / n * 1.05


def hypoexp_cdf_general(rates, t):
    from scipy.linalg import expm
    k = len(rates)
    Q = np.zeros((k + 1, k + 1))
    for j, r in enumerate(rates):
        Q[j, j] = -r
        Q[j, j + 1] = r
    return expm(Q * t)[0, k]


def test_cmc_exact_on_chain_including_tail():
    from fpp import first_passage_cmc
    rates = [0.8, 0.5, 0.3, 0.2]
    links = [((0, j + 1), (0, j), r) for j, r in enumerate(rates)]
    K = chain_kernel(1, 5, links)
    init = np.array([[True, False, False, False, False]])
    t = 0.6
    n = 20000
    out = first_passage_cmc(K, init, [t], n_samples=n, seed=21)
    for j in range(1, 5):
        exact = hypoexp_cdf_general(rates[:j], t)
        est = out["cmc_lo"][0, 0, j]
        se = math.sqrt(max(out["cmc_lo_var"][0, 0, j], 1e-300) / n)
        assert abs(est - exact) <= 5 * se + 1e-15, (j, est, exact, se)
        assert abs(out["cmc_hi"][0, 0, j] - exact) <= 5 * se + 0.02 * exact
    # far tail (exact ~1e-4 at cell 4): CMC relative SE is several times below plain MC's
    exact4 = hypoexp_cdf_general(rates, t)
    assert exact4 < 1e-3
    rel_cmc = math.sqrt(out["cmc_lo_var"][0, 0, 4] / n) / exact4
    rel_plain = math.sqrt(exact4 * (1 - exact4) / n) / exact4
    assert rel_cmc < rel_plain / 3


def test_cmc_matches_plain_on_random_grid_and_gap_only_on_burned():
    from fpp import first_passage_cmc
    rng = np.random.default_rng(7)
    K = rng.uniform(0, 0.15, size=(2, 25, 10, 10))
    K[:, 12] = 0
    init = np.zeros((10, 10), bool)
    init[5, 5] = True
    n = 20000
    out = first_passage_cmc(K, init, [1.5, 3.0], n_samples=n, seed=22)
    p = out["plain"]
    se = np.sqrt((p * (1 - p)) / n) + 1e-9
    # lower estimator: equal to plain within MC error (its bias is confined to burned cells)
    assert np.all(np.abs(out["cmc_lo"] - p) <= 5 * se + 0.005)
    # upper estimator is a pointwise upper bound of the exact conditional estimator
    assert np.all(out["cmc_lo"] <= out["cmc_hi"] + 1e-12)
    assert out["cmc_hi"].mean() >= p.mean() - 5 * se.mean()
    assert np.all(out["gap_fraction"] < 0.5)


def test_ca_conditional_estimator_exact_on_two_hop_hourly_chain():
    a, b = 1.3, 0.9
    K = chain_kernel(1, 3, [((0, 1), (0, 0), a), ((0, 2), (0, 1), b)])
    init = np.array([[True, False, False]])
    n = 20000
    out = cellular_automaton(K, init, [1.0, 2.0], dt=1.0, n_samples=n, seed=31, return_cmc=True)
    exact = {(0, 1): 1 - math.exp(-a), (1, 1): 1 - math.exp(-2 * a),
             (0, 2): 0.0, (1, 2): (1 - math.exp(-a)) * (1 - math.exp(-b))}
    for (h, j), e in exact.items():
        est = out["cmc_mean"][h, 0, j]
        se = math.sqrt(max(out["cmc_var"][h, 0, j], 1e-300) / n)
        assert abs(est - e) <= 5 * se + 1e-12
        assert abs(out["counts"][h, 0, j] / n - e) <= 5 * math.sqrt(max(e * (1 - e), 1e-12) / n)
    # first-hop cell: conditional estimator is deterministic (zero variance)
    assert out["cmc_var"][0, 0, 1] < 1e-12


def test_half_step_ca_between_hourly_and_fine():
    K = np.full((25, 20, 20), 1.0 / 24)
    K[12] = 0
    init = np.zeros((20, 20), bool)
    init[10, 10] = True
    n = 3000
    hourly = cellular_automaton(K, init, [4.0], dt=1.0, n_samples=n, seed=1)[0].sum() / n
    half = cellular_automaton(K, init, [4.0], dt=1.0, n_samples=n, seed=2, half_step=True)[0].sum() / n
    fine = cellular_automaton(K, init, [4.0], dt=1 / 8, n_samples=n, seed=3)[0].sum() / n
    assert hourly < half


def test_speed_multiplier_scales_arrival_times_exactly_under_static_kernels():
    """S-D4mix: with K -> c K and static kernels, T(c) = T(1) / c pathwise (same Exp(1) clocks)."""
    rng = np.random.default_rng(9)
    K = rng.uniform(0, 0.2, size=(25, 12, 12))
    K[12] = 0
    init = np.zeros((12, 12), bool)
    init[6, 6] = True
    for horizon in (50.0, 3.0):  # 3 h leaves cells unburned: exercises the inf branch (Owen)
        _, a1 = first_passage(K, init, [horizon], n_samples=20, seed=5, keep_arrivals=20)
        if horizon == 3.0:
            assert (~np.isfinite(a1)).any() and np.isfinite(a1).sum() > 20
        for c in (0.5, 2.0, 8.0):
            _, ac = first_passage(c * K, init, [horizon / c], n_samples=20, seed=5, keep_arrivals=20)
            fin = np.isfinite(a1)
            assert np.array_equal(fin, np.isfinite(ac))
            assert np.allclose(ac[fin], a1[fin] / c, rtol=1e-12, atol=0)


def test_cmc_frontier_restriction_matches_full_loop_reference():
    """The frontier-restricted CMC loop must equal a direct full-grid evaluation on the same trajectories."""
    from fpp import _cum_hazard, first_passage_cmc
    rng = np.random.default_rng(11)
    K = rng.uniform(0, 0.2, size=(2, 25, 14, 14))
    K[:, 12] = 0
    K[:, :, 3:5, :] = 0  # some cells unreachable from some offsets
    init = np.zeros((14, 14), bool)
    init[7, 7] = True
    hs = [1.0, 2.5]
    n = 30
    out = first_passage_cmc(K, init, hs, n_samples=n, seed=4)
    _, arr = first_passage(K, init, [max(hs)], n_samples=n, seed=4, keep_arrivals=n)  # same RNG stream
    offs = stencil_offsets(5)
    hi = np.zeros((len(hs), 14, 14))
    for m in range(n):
        a = arr[m]
        for h, t in enumerate(hs):
            for y in range(14):
                for x in range(14):
                    if init[y, x]:
                        continue
                    tot = 0.0
                    for c, (dy, dx) in enumerate(offs):
                        sy, sx = y + dy, x + dx
                        if 0 <= sy < 14 and 0 <= sx < 14 and a[sy, sx] < t and K[:, c, y, x].any():
                            tot += (_cum_hazard(K, c, y, x, t, 1.0) - _cum_hazard(K, c, y, x, a[sy, sx], 1.0))
                    hi[h, y, x] += -math.expm1(-tot)
    assert np.allclose(out["cmc_hi"], hi / n, rtol=1e-10, atol=1e-14)
    assert np.allclose(out["plain"], np.stack([((arr <= t) & ~init).mean(axis=0) for t in hs]))


def test_repaired_cmc_exact_where_bounds_differ():
    """A->B (a), A->C (c), B->C (b), C->B (d): C is often B's SPT descendant, so lo != hi for B.
    Exact: P(T_B <= t) = 1 - exp(-a t) * P(E_ac + E_cb > t). The repaired estimate must match it;
    lo must be low and hi high."""
    from fpp import first_passage_cmc_repaired
    a, c, b, d, t = 0.4, 0.3, 2.0, 1.5, 1.5
    K = np.zeros((25, 1, 3))
    K[channel(5, 0, -1), 0, 1] = a  # B <- A
    K[channel(5, 0, 1), 0, 1] = d   # B <- C
    K[channel(5, 0, -2), 0, 2] = c  # C <- A
    K[channel(5, 0, -1), 0, 2] = b  # C <- B
    init = np.array([[True, False, False]])
    exact = 1 - math.exp(-a * t) * (1 - hypoexp_cdf(c, d, t))
    n = 20000
    out = first_passage_cmc_repaired(K, init, t, n_samples=n, seed=12, threshold=0.05)
    assert out["flagged"][0, 1]
    assert out["repairs"] > 0
    est, se = out["estimate"][0, 1], math.sqrt(out["estimate_var"][0, 1] / n)
    assert abs(est - exact) <= 5 * se, (est, exact, se)
    assert out["lo"][0, 1] < exact - 5 * se
    assert out["hi"][0, 1] > exact + 5 * se
    p = out["plain"][0, 1]
    assert abs(p - exact) <= 5 * math.sqrt(exact * (1 - exact) / n)
