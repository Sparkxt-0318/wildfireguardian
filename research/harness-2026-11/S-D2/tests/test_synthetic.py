import numpy as np
import pytest

import synthetic as S


def tiny_problem(seed=3):
    p = S.make_problem(seed, n=12, radius=1, T=16.0, n_seeds=1)
    return p


def test_simulation_is_seeded_and_spreads():
    a, b = S.make_problem(5, n=20), S.make_problem(5, n=20)
    np.testing.assert_array_equal(a.tau, b.tau)
    burned = np.isfinite(a.tau).sum()
    assert burned > 30
    assert (a.tau[a.seeds] == 0).all()


def test_gibbs_conditional_matches_brute_force_joint_likelihood():
    p = tiny_problem()
    rng = np.random.default_rng(0)
    obs = S.observe_perimeter(p, every=4.0)
    sampler = S.LatentSampler(p, obs)
    tau = p.tau.copy()
    theta = np.concatenate([[p.k0], p.k])
    for i in sampler.free[:15]:
        x = np.linspace(obs["lo"][i] + 0.013, obs["hi"][i] - 0.017, 23)
        fast = sampler.conditional_logf(i, tau, theta, x)
        brute = []
        for xv in x:
            t2 = tau.copy(); t2[i] = xv
            ev, ex = S.sufficient_stats(p, t2)
            brute.append(S.complete_loglik(theta, ev, ex))
        brute = np.array(brute)
        np.testing.assert_allclose(fast - fast[0], brute - brute[0], atol=1e-9)


def test_oracle_mle_recovers_kernel_with_exact_arrivals():
    errs = []
    for seed in range(3):
        p = S.make_problem(seed, n=48, radius=1, n_seeds=8, scale=0.08)
        theta = S.fit_complete([S.sufficient_stats(p, p.tau)])
        errs.append(S.kernel_errors(theta, p)["rel_l2"])
    assert np.mean(errs) < 0.25


def test_bernoulli_gradient():
    rng = np.random.default_rng(1)
    X = (rng.uniform(size=(200, 4)) < 0.4).astype(float); X[:, 0] = 1
    y = rng.uniform(size=200)
    theta = rng.uniform(0.01, 0.3, 4)
    from scipy.optimize import check_grad
    def val(t):
        eta = X @ t
        return -(y * np.log(-np.expm1(-eta)) - (1 - y) * eta).sum()
    def grad(t):
        eta = X @ t
        return -(X.T @ (y / np.expm1(eta) - (1 - y)))
    assert check_grad(val, grad, theta) / np.linalg.norm(grad(theta)) < 1e-5


def test_soft_hourly_equals_hard_when_sd_zero():
    p = S.make_problem(2, n=24, radius=1)
    rng = np.random.default_rng(2)
    obs = S.observe_kriged(p, rng, sd_choices=(0.0,))
    np.testing.assert_array_equal(obs["tau_hat"][obs["burned"]], p.tau[obs["burned"]])
    out, _ = S.estimate_all(p, obs, rng, mcem_kwargs=dict(iterations=1, sweeps=1, keep=1, average_last=1))
    np.testing.assert_allclose(out["soft_hourly"], out["hard_hourly"], rtol=1e-6, atol=1e-9)
    np.testing.assert_allclose(out["sd_weighted"], out["hard_hourly"], rtol=1e-6, atol=1e-9)


def test_soft_risk_rows_conserve_one_arrival_per_burned_cell():
    p = S.make_problem(4, n=24, radius=1)
    rng = np.random.default_rng(4)
    obs = S.observe_kriged(p, rng)
    src, _ = S._neighbour_table(p.n, p.offs)
    point = np.where(obs["burned"], np.clip(obs["tau_hat"], 1e-3, p.T), np.inf)
    point[p.seeds] = 0
    X, y, w = S.soft_risk_rows(p, obs, point, src)
    burned_nonseed = obs["burned"].sum() - len(p.seeds)
    # Expected arrivals = sum_t S(t) h(t) = P(0 < tau <= T) = 1 per burned cell (truncated).
    assert (w * y).sum() == pytest.approx(burned_nonseed, rel=1e-6)


def test_soft_risk_reduces_to_hard_rows_when_sd_zero():
    p = S.make_problem(6, n=24, radius=1)
    rng = np.random.default_rng(6)
    obs = S.observe_kriged(p, rng, sd_choices=(0.0,))
    src, _ = S._neighbour_table(p.n, p.offs)
    point = np.where(obs["burned"], obs["tau_hat"], np.inf); point[p.seeds] = 0
    Xs, ys, ws = S.soft_risk_rows(p, obs, point, src)
    hard = lambda cells, t: ((point[cells] > t) & (point[cells] <= t + 1)).astype(float)
    Xh, yh, _, _ = S.hourly_rows(p, point, hard, src)
    np.testing.assert_allclose(S.fit_bernoulli(Xs, ys, ws), S.fit_bernoulli(Xh, yh), rtol=1e-6, atol=1e-9)
