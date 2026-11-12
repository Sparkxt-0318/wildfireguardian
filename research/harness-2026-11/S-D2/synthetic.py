"""Synthetic known-kernel study for the interval-censored arrival likelihood.

Generative model (continuous time, square grid):

    lambda_i(t) = k_0 + sum_d k_d * 1{tau_{i-d} <= t}

where ``d`` runs over the offsets of a (2r+1)x(2r+1) neighbourhood without its
centre (``d`` is the displacement from source to target) and ``k_0`` is a
background ignition rate.  Seeds ignite at ``t = 0``.  Arrival times are
simulated exactly (event-driven, piecewise-constant hazards) up to a horizon
``T``.

With exact arrival times the complete-data log-likelihood is

    l(k) = sum_{i: tau_i <= T} log lambda_i(tau_i)
           - sum_i integral_0^{min(tau_i, T)} lambda_i(s) ds,

which is concave and linear-in-k inside the log, so both terms reduce to
per-cell sufficient statistics: an "active source" indicator vector at the
event time and a per-offset exposure time.

Observation models (what the fitter sees):

* ``kriged``: every cell with tau <= T has a reconstructed arrival
  ``tau_hat = tau + eps`` with ``eps ~ N(0, sd_i)`` and a known per-cell sd;
  cells with tau > T are known unburned (finite reconstruction mask).
* ``perimeter``: survey times ``0 = P_0 < P_1 < ... < P_m = T``; each burned
  cell is only known to satisfy ``tau in (P_k, P_{k+1}]``.

Estimators compared:

* ``oracle``        complete-data MLE on the true tau (attainable floor).
* ``hard_hourly``   the current pipeline: hourly Bernoulli rows with
                    p = 1 - exp(-k . n(t)), state and label from tau_hat.
* ``sd_weighted``   hard_hourly with forecast-v2's weight 1 / (1 + (sd/L)^2).
* ``soft_hourly``   hard_hourly with target P(t < tau <= t+1) under N(tau_hat, sd).
* ``plugin``        continuous complete-data MLE treating tau_hat (or the
                    bracket's right end, as in Ganguly et al.'s first
                    observation time) as exact.
* ``mcem``          Monte Carlo EM for the interval-censored likelihood: a
                    Gibbs sampler over latent arrival fields consistent with
                    the observations (bracket or Gaussian error), alternating
                    with the concave complete-data M-step.

Everything is NumPy/SciPy; no repository data are read.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize

from soft_labels import normal_interval_probability

INF = np.inf


# --------------------------------------------------------------------------- model

def offsets(radius: int) -> np.ndarray:
    r = np.arange(-radius, radius + 1)
    dr, dc = np.meshgrid(r, r, indexing="ij")
    d = np.stack([dr.ravel(), dc.ravel()], axis=1)
    return d[~((d[:, 0] == 0) & (d[:, 1] == 0))]


def true_kernel(offs: np.ndarray, *, scale=0.025, length=0.9, wind=0.6) -> np.ndarray:
    """Anisotropic, distance-decaying kernel; wind toward +column."""
    dist = np.hypot(offs[:, 0], offs[:, 1])
    cos = offs[:, 1] / dist
    return scale * np.exp(-(dist - 1) / length) * (1 + wind * cos)


@dataclass
class Problem:
    n: int                       # grid side
    offs: np.ndarray             # (D, 2)
    k: np.ndarray                # (D,) true kernel
    k0: float                    # background rate
    T: float                     # horizon
    seeds: np.ndarray            # (S,) flat indices igniting at t=0
    tau: np.ndarray = field(default=None)   # (n*n,) true arrival, inf if > T

    @property
    def cells(self):
        return self.n * self.n


def _neighbour_table(n: int, offs: np.ndarray):
    """src[i, d] = flat index of i - d (source of offset d for target i), -1 outside."""
    rr, cc = np.divmod(np.arange(n * n), n)
    sr = rr[:, None] - offs[None, :, 0]
    sc = cc[:, None] - offs[None, :, 1]
    inside = (sr >= 0) & (sr < n) & (sc >= 0) & (sc < n)
    src = np.where(inside, sr * n + sc, -1)
    tr = rr[:, None] + offs[None, :, 0]
    tc = cc[:, None] + offs[None, :, 1]
    inside = (tr >= 0) & (tr < n) & (tc >= 0) & (tc < n)
    tgt = np.where(inside, tr * n + tc, -1)   # tgt[i, d] = i + d (target receiving from i)
    return src, tgt


def simulate(problem: Problem, rng: np.random.Generator) -> np.ndarray:
    """Exact event-driven simulation of arrival times up to the horizon."""
    n2 = problem.cells
    _, tgt = _neighbour_table(problem.n, problem.offs)
    tau = np.full(n2, INF)
    rate = np.full(n2, problem.k0)
    burned = np.zeros(n2, bool)

    def ignite(i, t):
        tau[i] = t
        burned[i] = True
        rate[i] = 0.0
        tg = tgt[i]
        ok = tg >= 0
        np.add.at(rate, tg[ok], problem.k[ok])
        rate[burned] = 0.0

    for s in problem.seeds:
        ignite(int(s), 0.0)
    t = 0.0
    while True:
        total = rate.sum()
        if total <= 0:
            break
        t += rng.exponential(1.0 / total)
        if t > problem.T:
            break
        i = int(np.searchsorted(np.cumsum(rate), rng.uniform(0, total), side="right"))
        i = min(i, n2 - 1)
        ignite(i, t)
    return tau


def make_problem(seed: int, *, n=40, radius=2, T=48.0, k0=2e-5, n_seeds=4, scale=0.025) -> Problem:
    rng = np.random.default_rng(seed)
    offs = offsets(radius)
    k = true_kernel(offs, scale=scale)
    centre = n // 2
    seeds = []
    for _ in range(n_seeds):
        r = int(rng.integers(centre - 4, centre + 5))
        c = int(rng.integers(4, 10))
        seeds.append(r * n + c)
    p = Problem(n=n, offs=offs, k=k, k0=k0, T=T, seeds=np.unique(seeds))
    p.tau = simulate(p, rng)
    return p


# ----------------------------------------------------------- complete-data likelihood

def sufficient_stats(problem: Problem, tau: np.ndarray, src=None):
    """Event indicator rows and total exposure for the complete-data likelihood.

    Returns ``(events, exposure)`` with ``events`` of shape (E, D+1) (column 0
    is the background) and ``exposure`` of shape (D+1,).  Seeds are conditioned
    on and excluded.
    """
    if src is None:
        src, _ = _neighbour_table(problem.n, problem.offs)
    T = problem.T
    not_seed = np.ones(problem.cells, bool)
    not_seed[problem.seeds] = False
    tsrc = np.where(src >= 0, tau[np.clip(src, 0, None)], INF)          # (N, D)
    end = np.minimum(tau, T)                                           # (N,)
    exp_d = np.clip(end[:, None] - tsrc, 0, None)
    exp_d[~np.isfinite(exp_d)] = 0.0
    exposure = np.concatenate([[end[not_seed].sum()], exp_d[not_seed].sum(axis=0)])
    ev = not_seed & (tau <= T)
    events = np.concatenate([np.ones((ev.sum(), 1)), (tsrc[ev] < tau[ev, None]).astype(float)], axis=1)
    return events, exposure


def complete_loglik(theta, events, exposure):
    lam = events @ theta
    return np.log(lam).sum() - exposure @ theta


def fit_complete(stats_list, *, floor=1e-9, x0=None):
    """MLE of theta = (k0, k_1..k_D) >= floor, averaging over stats samples."""
    events = np.concatenate([s[0] for s in stats_list])
    weights = np.concatenate([np.full(len(s[0]), 1.0 / len(stats_list)) for s in stats_list])
    exposure = np.mean([s[1] for s in stats_list], axis=0)
    D1 = exposure.shape[0]
    x0 = np.full(D1, 0.05) if x0 is None else np.maximum(x0, 1e-4)

    def f(theta):
        lam = events @ theta
        val = -(weights @ np.log(lam) - exposure @ theta)
        grad = -(events.T @ (weights / lam) - exposure)
        return val, grad

    res = minimize(f, x0, jac=True, method="L-BFGS-B", bounds=[(floor, None)] * D1,
                   options=dict(maxiter=5000, ftol=1e-13, gtol=1e-10))
    return res.x


# --------------------------------------------------------------- hourly Bernoulli fits

def hourly_rows(problem: Problem, tau_state: np.ndarray, target: np.ndarray, src=None):
    """Rows (features, target index) for unburned-at-t cells under ``tau_state``.

    ``target`` is a callable(cell_idx, t) -> label array.
    """
    if src is None:
        src, _ = _neighbour_table(problem.n, problem.offs)
    hours = int(problem.T)
    not_seed = np.ones(problem.cells, bool)
    not_seed[problem.seeds] = False
    tsrc = np.where(src >= 0, tau_state[np.clip(src, 0, None)], INF)
    X, Y, cells, times = [], [], [], []
    for t in range(hours):
        risk = np.flatnonzero(not_seed & (tau_state > t))
        x = np.concatenate([np.ones((len(risk), 1)), (tsrc[risk] <= t).astype(float)], axis=1)
        X.append(x)
        Y.append(target(risk, t))
        cells.append(risk)
        times.append(np.full(len(risk), t))
    return np.concatenate(X), np.concatenate(Y), np.concatenate(cells), np.concatenate(times)


def fit_bernoulli(X, y, w=None, *, floor=1e-9, x0=None):
    """Max weighted cross-entropy with p = 1 - exp(-X theta), soft targets allowed."""
    w = np.ones(len(y)) if w is None else w
    D1 = X.shape[1]
    x0 = np.full(D1, 0.05) if x0 is None else np.maximum(x0, 1e-4)

    def f(theta):
        eta = X @ theta
        with np.errstate(over="ignore"):
            dl = y / np.expm1(eta) - (1 - y)
        logp = np.log(-np.expm1(-eta))
        val = -(w @ (y * logp - (1 - y) * eta))
        # d/d eta: y * exp(-eta)/(1-exp(-eta)) - (1-y)
        grad = -(X.T @ (w * dl))
        return val, grad

    res = minimize(f, x0, jac=True, method="L-BFGS-B", bounds=[(floor, None)] * D1,
                   options=dict(maxiter=5000, ftol=1e-13, gtol=1e-10))
    return res.x


# ------------------------------------------------------------------ observations

def observe_kriged(problem: Problem, rng, *, sd_choices=(0.5, 2.0, 6.0)):
    burned = np.isfinite(problem.tau) & (problem.tau <= problem.T)
    sd = np.where(burned, rng.choice(sd_choices, size=problem.cells), np.nan)
    sd[problem.seeds] = 0.0
    tau_hat = np.where(burned, problem.tau + rng.normal(0, 1, problem.cells) * np.nan_to_num(sd), INF)
    return dict(kind="kriged", tau_hat=tau_hat, sd=sd, burned=burned)


def observe_perimeter(problem: Problem, *, every=12.0):
    surveys = np.arange(0.0, problem.T + 1e-9, every)
    if surveys[-1] < problem.T:
        surveys = np.append(surveys, problem.T)
    burned = np.isfinite(problem.tau) & (problem.tau <= problem.T)
    k = np.searchsorted(surveys, problem.tau, side="left")   # tau in (P_{k-1}, P_k]
    lo = np.where(burned, surveys[np.clip(k - 1, 0, None)], np.nan)
    hi = np.where(burned, surveys[np.clip(k, 0, len(surveys) - 1)], np.nan)
    lo[problem.seeds] = hi[problem.seeds] = 0.0
    return dict(kind="perimeter", lo=lo, hi=hi, burned=burned, surveys=surveys)


# ------------------------------------------------------------------- Gibbs / MCEM

class LatentSampler:
    """Gibbs sampler over latent arrival times of observed-burned cells.

    The conditional of tau_i given everything else is evaluated on a fine
    grid of candidate times inside the cell's allowed range, combining
    (a) its own arrival density log lambda_i(x) - Lambda_i(x),
    (b) its effect on each target neighbour's likelihood term, and
    (c) the observation factor (bracket indicator or Gaussian error).
    """

    def __init__(self, problem: Problem, obs: dict, *, step=0.1):
        self.p = problem
        self.obs = obs
        self.src, self.tgt = _neighbour_table(problem.n, problem.offs)
        self.step = step
        T = problem.T
        free = obs["burned"].copy()
        free[problem.seeds] = False
        if obs["kind"] == "kriged":
            free &= np.nan_to_num(obs["sd"]) > 0      # sd == 0: arrival observed exactly
        self.free = np.flatnonzero(free)
        self.grid = {}
        for i in self.free:
            if obs["kind"] == "perimeter":
                lo, hi = obs["lo"][i], obs["hi"][i]
            else:
                lo, hi = 0.0, T
            m = max(1, int(np.ceil((hi - lo) / step)))
            edges = np.linspace(lo, hi, m + 1)
            centres = 0.5 * (edges[:-1] + edges[1:])
            if obs["kind"] == "kriged":
                # Exact bin mass of the Gaussian observation factor, as a function of x,
                # is approximated at the bin centre (bins are 0.1 h).
                s = obs["sd"][i]
                logobs = -0.5 * ((obs["tau_hat"][i] - centres) / s) ** 2
            else:
                logobs = np.zeros(m)
            self.grid[i] = (edges, centres, logobs)

    def initial(self):
        tau = np.where(self.obs["burned"], 0.0, INF)
        if self.obs["kind"] == "perimeter":
            tau[self.free] = 0.5 * (self.obs["lo"][self.free] + self.obs["hi"][self.free])
        else:
            known = self.obs["burned"]
            tau[known] = np.clip(self.obs["tau_hat"][known], 1e-3, self.p.T)
        tau[self.p.seeds] = 0.0
        return tau

    def conditional_logf(self, i, tau, theta, x=None, logobs=None):
        """Unnormalised log conditional density of tau_i on candidate times x."""
        k0, k = theta[0], theta[1:]
        T = self.p.T
        if x is None:
            _, x, logobs = self.grid[i]
        if logobs is None:
            logobs = np.zeros(len(x))
        # (a) own term
        sidx = self.src[i]
        ok = sidx >= 0
        ts = tau[sidx[ok]]
        kk = k[ok]
        active = ts[None, :] < x[:, None]                          # (G, d)
        lam = k0 + active @ kk
        Lam = k0 * x + np.clip(x[:, None] - ts[None, :], 0, None) @ kk
        logf = np.log(lam) - Lam + logobs
        # (b) target neighbours m = i + d receiving k_d from i
        tidx = self.tgt[i]
        okt = np.flatnonzero(tidx >= 0)
        for d in okt:
            m = tidx[d]
            if m in self._seedset:
                continue
            tm = tau[m]
            kd = k[d]
            if np.isfinite(tm):
                # lambda_m(tau_m) without i's contribution
                ms = self.src[m]
                okm = ms >= 0
                tsm = tau[ms[okm]]
                contrib = (tsm < tm) & (ms[okm] != i)
                lam_rest = k0 + k[okm][contrib].sum()
                logf += np.log(lam_rest + kd * (x < tm)) - kd * np.clip(tm - x, 0, None)
            else:
                logf -= kd * np.clip(T - x, 0, None)
        return logf

    def sweep(self, tau, theta, rng):
        for i in rng.permutation(self.free):
            edges, x, logobs = self.grid[i]
            logf = self.conditional_logf(i, tau, theta, x, logobs)
            logf -= logf.max()
            prob = np.exp(logf)
            prob /= prob.sum()
            b = rng.choice(len(x), p=prob)
            tau[i] = rng.uniform(edges[b], edges[b + 1])
        return tau

    @property
    def _seedset(self):
        if not hasattr(self, "_ss"):
            self._ss = set(int(s) for s in self.p.seeds)
        return self._ss


def mcem(problem: Problem, obs: dict, rng, *, iterations=25, sweeps=3, keep=2, theta0=None,
         average_last=8, step=0.1):
    sampler = LatentSampler(problem, obs, step=step)
    tau = sampler.initial()
    theta = fit_complete([sufficient_stats(problem, tau, sampler.src)]) if theta0 is None else theta0
    history = []
    for it in range(iterations):
        stats = []
        for s in range(sweeps):
            tau = sampler.sweep(tau, theta, rng)
            if s >= sweeps - keep:
                stats.append(sufficient_stats(problem, tau, sampler.src))
        theta = fit_complete(stats, x0=theta)
        history.append(theta.copy())
    return np.mean(history[-average_last:], axis=0), np.array(history)


# --------------------------------------------------------------------- estimators

def estimate_all(problem: Problem, obs: dict, rng, *, mcem_kwargs=None):
    src, _ = _neighbour_table(problem.n, problem.offs)
    out = {}
    out["oracle"] = fit_complete([sufficient_stats(problem, problem.tau, src)])
    if obs["kind"] == "kriged":
        point = np.where(obs["burned"], np.clip(obs["tau_hat"], 1e-3, problem.T), INF)
    else:
        point = np.where(obs["burned"], obs["hi"], INF)      # first observation time
    point[problem.seeds] = 0.0
    out["plugin"] = fit_complete([sufficient_stats(problem, point, src)])
    if obs["kind"] == "kriged":
        hard = lambda cells, t: ((point[cells] > t) & (point[cells] <= t + 1)).astype(float)
        X, y, cells, times = hourly_rows(problem, point, hard, src)
        out["hard_hourly"] = fit_bernoulli(X, y)
        L = 1.0
        w = 1.0 / (1.0 + (np.nan_to_num(obs["sd"][cells]) / L) ** 2)
        out["sd_weighted"] = fit_bernoulli(X, y, w)
        ys = normal_interval_probability(times, times + 1, obs["tau_hat"][cells], np.nan_to_num(obs["sd"][cells]))
        ys = np.where(np.isfinite(obs["tau_hat"][cells]), ys, 0.0)
        out["soft_hourly"] = fit_bernoulli(X, ys)
        Xr, yr, wr = soft_risk_rows(problem, obs, point, src, soft_features=False)
        out["soft_risk"] = fit_bernoulli(Xr, yr, wr)
        Xr, yr, wr = soft_risk_rows(problem, obs, point, src, soft_features=True)
        out["soft_risk_softfeat"] = fit_bernoulli(Xr, yr, wr)
    out["mcem"], hist = mcem(problem, obs, rng, **(mcem_kwargs or {}))
    return out, hist


def soft_risk_rows(problem: Problem, obs: dict, point, src, *, soft_features=False, eps=1e-9):
    """Hourly rows over a soft risk set.

    Under tau_i ~ N(tau_hat_i, sd_i) truncated to (0, T] (the cell is known to
    have burned inside the window), row (i, t) has weight S_i(t) = P(tau_i > t)
    and target h_i(t) = P(t < tau_i <= t+1 | tau_i > t).  Expected positive
    mass per burned cell is then sum_t S h = 1, unlike the hard risk set with
    soft targets, which drops the mass after tau_hat.  Never-burned cells have
    S = 1 and h = 0.  Source features are the point state 1{tau_hat_j <= t}
    or, with ``soft_features``, P(tau_j <= t) (a mean-field input).
    """
    T = problem.T
    not_seed = np.ones(problem.cells, bool)
    not_seed[problem.seeds] = False
    burned = obs["burned"]
    mu = np.where(burned, obs["tau_hat"], np.nan)
    sd = np.nan_to_num(obs["sd"])
    mass = np.where(burned, normal_interval_probability(0.0, T, np.nan_to_num(mu), sd), 1.0)
    X, Y, W = [], [], []
    err = np.seterr(invalid="ignore", divide="ignore")
    for t in range(int(T)):
        surv = np.where(burned, normal_interval_probability(float(t), T, np.nan_to_num(mu), sd) / mass, 1.0)
        nxt = np.where(burned, normal_interval_probability(float(t + 1), T, np.nan_to_num(mu), sd) / mass, 1.0)
        cdf_t = np.where(burned, 1.0 - surv, 0.0)
        cdf_t[problem.seeds] = 1.0
        risk = np.flatnonzero(not_seed & (surv > eps))
        if soft_features:
            feats = np.where(src[risk] >= 0, cdf_t[np.clip(src[risk], 0, None)], 0.0)
        else:
            tp = np.where(src[risk] >= 0, point[np.clip(src[risk], 0, None)], INF)
            feats = (tp <= t).astype(float)
        X.append(np.concatenate([np.ones((len(risk), 1)), feats], axis=1))
        Y.append(np.clip(1.0 - nxt[risk] / surv[risk], 0.0, 1.0))
        W.append(surv[risk])
    np.seterr(**err)
    return np.concatenate(X), np.concatenate(Y), np.concatenate(W)


def heldout_nll(theta, problems):
    """Mean negative complete-data log-likelihood per arrival on fresh true fields."""
    total, events = 0.0, 0
    for p in problems:
        ev, ex = sufficient_stats(p, p.tau)
        total -= complete_loglik(theta, ev, ex)
        events += len(ev)
    return total / events


def kernel_errors(theta, problem: Problem):
    k = problem.k
    est = theta[1:]
    dist = np.hypot(problem.offs[:, 0], problem.offs[:, 1])
    near = dist < 1.5
    rel = lambda a, b: float(np.linalg.norm(a - b) / np.linalg.norm(b)) if len(b) else float("nan")
    return dict(rel_l2=rel(est, k), rel_l2_near=rel(est[near], k[near]), rel_l2_far=rel(est[~near], k[~near]),
                total_rate_ratio=float(est.sum() / k.sum()), k0=float(theta[0]))
