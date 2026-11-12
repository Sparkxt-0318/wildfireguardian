import numpy as np
import pytest
from scipy.optimize import check_grad

import synthetic as S
import synthetic_robust as R


def test_fpp_with_exponential_delays_recovers_markov_kernel():
    errs, rates = [], []
    for seed in range(3):
        p = R.make_problem(seed, n=48, radius=1, n_seeds=8, scale=0.08)
        th = S.fit_complete([S.sufficient_stats(p, p.tau)])
        e = S.kernel_errors(th, p)
        errs.append(e["rel_l2"]); rates.append(e["total_rate_ratio"])
    assert np.mean(errs) < 0.25 and abs(np.mean(rates) - 1) < 0.1


def test_uniform_expectation_and_derivative_match_monte_carlo():
    rng = np.random.default_rng(0)
    u = rng.uniform(2.0, 7.0, 400_000)
    for t, k in [(1.0, 0.3), (4.0, 0.3), (9.0, 0.2), (5.5, 1.5)]:
        f, g = R._uniform_exp_expect(np.array([t]), np.array([2.0]), np.array([7.0]), np.array([k]))
        s = np.clip(t - u, 0, None)
        assert f[0] == pytest.approx(np.exp(-k * s).mean(), abs=2e-3)
        assert g[0] == pytest.approx((-s * np.exp(-k * s)).mean(), abs=5e-3)
    f, g = R._uniform_exp_expect(np.array([5.0]), np.array([2.0]), np.array([2.0]), np.array([0.4]))
    assert f[0] == pytest.approx(np.exp(-1.2)) and g[0] == pytest.approx(-3 * np.exp(-1.2))


def test_meanfield_adjoint_gradient():
    p = R.make_problem(1, n=20, radius=1, n_seeds=3, scale=0.08, T=24.0)
    obs = S.observe_perimeter(p, every=6.0)
    windows, targets, masks = [], [], []
    for a, b in zip(obs["surveys"][:-1], obs["surveys"][1:]):
        st = (p.tau <= a).astype(float)
        windows.append((st, int(b - a))); targets.append((p.tau <= b).astype(float)); masks.append((st == 0).astype(float))
    th = np.concatenate([[1e-3], p.k])
    for loss in ("nll", "brier"):
        f = lambda x: R._meanfield_loss_grad(p, x, windows, targets, masks, loss)[0]
        g = lambda x: R._meanfield_loss_grad(p, x, windows, targets, masks, loss)[1]
        # Central differences: the loss is strongly curved in k0, so a one-sided
        # difference (check_grad) has truncation error above the tolerance.
        fd = np.array([(f(th + e) - f(th - e)) / 2e-6 for e in np.eye(len(th)) * 1e-6])
        assert np.linalg.norm(fd - g(th)) / np.linalg.norm(g(th)) < 1e-4


def test_composite_gradient_and_narrow_brackets_recover_rate():
    p = R.make_problem(2, n=40, radius=1, n_seeds=6, scale=0.08)
    obs = S.observe_perimeter(p, every=1.0)
    th = R.fit_bracket_composite(p, obs)
    assert abs(S.kernel_errors(th, p)["total_rate_ratio"] - 1) < 0.15


def test_correlated_error_has_stated_scale_and_spatial_correlation():
    p = R.make_problem(3)
    rng = np.random.default_rng(3)
    obs = R.observe_kriged_robust(p, rng, sd_choices=(2.0,), corr_cells=3.0)
    b = obs["burned"].copy(); b[p.seeds] = False
    z = (obs["tau_hat"] - p.tau)[b] / 2.0
    assert 0.6 < z.std() < 1.4
    obs2 = R.observe_kriged_robust(p, np.random.default_rng(3), sd_choices=(2.0,), true_factor=1.75)
    z2 = (obs2["tau_hat"] - p.tau)[b] / 2.0
    assert 1.5 < z2.std() < 2.0


def test_scale_by_simulation_recovers_known_multiplier():
    # Truth is Markov; give the correct shape scaled by 1/3 and expect m ~ 3.
    p = R.make_problem(5)
    obs = S.observe_perimeter(p, every=12.0)
    shape = np.concatenate([[p.k0], p.k]) / 3.0
    _, m = R.fit_scale_by_simulation(p, obs, shape, n_sims=6, seed=1)
    assert 2.4 < m < 3.7


def test_mcem_scale_recovers_multiplier_with_true_shape():
    p = R.make_problem(4)
    obs = S.observe_perimeter(p, every=12.0)
    shape = np.concatenate([[p.k0], p.k]) / 2.5
    _, m = R.mcem_scale(p, obs, shape, np.random.default_rng(0), iterations=12, sweeps=2, keep=1, average_last=6)
    assert 2.0 < m < 3.1
