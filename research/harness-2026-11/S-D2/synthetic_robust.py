"""Robustness extensions of the synthetic study (Iris / orchestrator round 2).

Adds to ``synthetic.py``:

* a first-passage simulator ``simulate_fpp``: each burned source ``j`` reaches
  target ``i = j + d`` after an independent delay ``D ~ Gamma(shape, mean 1/k_d)``
  and ``tau_i = min_j (tau_j + D_ji)`` (Dijkstra).  ``shape = 1`` is exactly the
  Markov hazard model of ``synthetic.simulate`` (memoryless competing sources);
  ``shape > 1`` gives non-exponential, more regular passage times.  Optional
  *spotting* offsets beyond the fitted radius are part of the truth but not of
  the fitted kernel.
* observation models: spatially correlated Gaussian error (smoothed white noise
  rescaled to the per-cell sd) and miscalibrated stated sd (true error = factor x stated).
* estimators:
  - ``bracket_composite``: independent-bracket composite likelihood.  For every
    cell, P(tau_i in (L_i, U_i]) = S_i(L_i) - S_i(U_i) with
    S_i(t) = exp(-k0 t) prod_d E_q[exp(-k_d (t - tau_(i-d))_+)], where q makes
    each neighbour's arrival independent and uniform on its own bracket.
    Closed form, no sampling; ignores neighbour coupling.
  - ``meanfield_nll`` / ``meanfield_brier``: the forecast-v2 perimeter regime
    analogue (``forecast/wildfire/survival.py``).  From the exactly known state
    at each survey, an hourly mean field ``p <- p + (1-p)(1-exp(-(k0 + sum_d
    k_d p_(i-d))))`` predicts the endpoint state at the next survey; fitted by
    Bernoulli NLL or Brier on cells unburned at the start.
  - ``mcem_long``: MCEM with more Monte Carlo samples (60 iterations x 6 sweeps,
    5 kept, average of last 30) to test whether its variance is Monte Carlo noise.

Peak memory is Python-heap peak via ``tracemalloc`` (NumPy buffers included).
"""
from __future__ import annotations

import heapq
import time
import tracemalloc

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.optimize import minimize

import synthetic as S
from synthetic import INF, Problem, _neighbour_table


# ----------------------------------------------------------------- generator

def spotting_offsets(rate=0.004, distance=5):
    """Downwind long-range offsets (+column), outside the radius-2 fitted kernel."""
    offs = np.array([(dr, distance) for dr in (-1, 0, 1)] + [(0, distance + 1)])
    return offs, np.full(len(offs), rate)


def simulate_fpp(problem: Problem, rng, *, shape=1.0, spot=None) -> np.ndarray:
    n, T = problem.n, problem.T
    offs, rates = problem.offs, problem.k
    if spot is not None:
        offs = np.concatenate([offs, spot[0]])
        rates = np.concatenate([rates, spot[1]])
    tau = np.full(n * n, INF)
    heap = []
    for s in problem.seeds:
        tau[s] = 0.0
        heap.append((0.0, int(s)))
    bg = rng.exponential(1.0 / problem.k0, size=n * n)
    for i in np.flatnonzero(bg <= T):
        if tau[i] > bg[i]:
            tau[i] = bg[i]
            heap.append((bg[i], int(i)))
    heapq.heapify(heap)
    done = np.zeros(n * n, bool)
    while heap:
        t, j = heapq.heappop(heap)
        if done[j] or t > T:
            continue
        done[j] = True
        r, c = divmod(j, n)
        tr, tc = r + offs[:, 0], c + offs[:, 1]
        ok = (tr >= 0) & (tr < n) & (tc >= 0) & (tc < n)
        tgt = tr[ok] * n + tc[ok]
        k = rates[ok]
        delay = rng.gamma(shape, 1.0 / (shape * k))
        cand = t + delay
        better = (cand < tau[tgt]) & ~done[tgt] & (cand <= T)
        for i, v in zip(tgt[better], cand[better]):
            if v < tau[i]:
                tau[i] = v
                heapq.heappush(heap, (v, int(i)))
    tau[tau > T] = INF
    return tau


def make_problem(seed, *, shape=1.0, spot=None, n=56, n_seeds=8, radius=2, T=48.0, k0=2e-5, scale=0.025):
    rng = np.random.default_rng(seed)
    offs = S.offsets(radius)
    k = S.true_kernel(offs, scale=scale)
    centre = n // 2
    seeds = [int(rng.integers(centre - 4, centre + 5)) * n + int(rng.integers(4, 10)) for _ in range(n_seeds)]
    p = Problem(n=n, offs=offs, k=k, k0=k0, T=T, seeds=np.unique(seeds))
    p.tau = simulate_fpp(p, rng, shape=shape, spot=spot)
    return p


def crossing_time(problem: Problem) -> float:
    """Median time from a cell's first burned 8-neighbour to its own arrival."""
    src, _ = _neighbour_table(problem.n, problem.offs)
    near = np.hypot(problem.offs[:, 0], problem.offs[:, 1]) < 1.5
    tau = problem.tau
    ts = np.where(src[:, near] >= 0, tau[np.clip(src[:, near], 0, None)], INF)
    first = ts.min(axis=1)
    ok = np.isfinite(tau) & np.isfinite(first) & (tau > 0)
    return float(np.median(tau[ok] - first[ok]))


# --------------------------------------------------------------- observations

def observe_kriged_robust(problem: Problem, rng, *, sd_choices=(0.5, 2.0, 6.0), corr_cells=0.0, true_factor=1.0):
    """Kriged-style observation; the fitter is told sd, the truth uses true_factor * sd.

    ``corr_cells > 0`` makes the standardized error a Gaussian-smoothed field
    (length ``corr_cells`` cells) rescaled to unit variance, so neighbouring
    cells share their error, as kriging interpolation does.
    """
    n = problem.n
    burned = np.isfinite(problem.tau)
    sd = np.where(burned, rng.choice(sd_choices, size=n * n), np.nan)
    sd[problem.seeds] = 0.0
    z = rng.normal(size=(n, n))
    if corr_cells > 0:
        z = gaussian_filter(z, corr_cells, mode="reflect")
        z /= z.std()
    eps = z.ravel() * np.nan_to_num(sd) * true_factor
    tau_hat = np.where(burned, problem.tau + eps, INF)
    return dict(kind="kriged", tau_hat=tau_hat, sd=sd, burned=burned)


# ---------------------------------------------------------------- estimators

def _uniform_exp_expect(t, a, b, k):
    """f = E[exp(-k (t - U)_+)] and df/dk for U ~ Uniform(a, b] (b == a: point mass at a).

    ``a = inf`` (source never active) gives f = 1, df/dk = 0.
    """
    t, a, b, k = (np.asarray(x, dtype=np.float64) for x in np.broadcast_arrays(t, a, b, k))
    f = np.ones(t.shape)
    g = np.zeros(t.shape)
    active = np.isfinite(a) & (t > a)
    with np.errstate(invalid="ignore"):
        width = np.where(active, b - a, 0.0)
    point = active & (width <= 1e-12)
    s = np.where(point, t - a, 0.0)
    f[point] = np.exp(-k[point] * s[point])
    g[point] = -s[point] * f[point]
    m = active & ~point
    tm, am, bm, km = t[m], a[m], b[m], np.maximum(k[m], 1e-12)
    top = np.minimum(bm, tm)
    s0, s1 = tm - top, tm - am                       # s = t - u runs over [s0, s1]
    e0, e1 = np.exp(-km * s0), np.exp(-km * s1)
    w = bm - am
    f[m] = ((e0 - e1) / km + (bm - top)) / w
    # d/dk of int_{s0}^{s1} e^{-ks} ds = -int s e^{-ks} ds
    int_s = (s0 * e0 - s1 * e1) / km + (e0 - e1) / km ** 2
    g[m] = -int_s / w
    return f, g


def fit_bracket_composite(problem: Problem, obs: dict, *, floor=1e-9, x0=None):
    src, _ = _neighbour_table(problem.n, problem.offs)
    T = problem.T
    burned = obs["burned"]
    lo = np.where(burned, obs["lo"], INF)
    hi = np.where(burned, obs["hi"], INF)
    lo[problem.seeds] = hi[problem.seeds] = 0.0
    not_seed = np.ones(problem.cells, bool)
    not_seed[problem.seeds] = False
    cells = np.flatnonzero(not_seed)
    s = src[cells]
    ok = s >= 0
    sc = np.clip(s, 0, None)
    na = np.where(ok, lo[sc], INF)                    # inf: never active before T
    nb = np.where(np.isfinite(na), hi[sc], INF)
    Li = np.where(burned[cells], lo[cells], T)
    Ui = hi[cells]
    burned_c = burned[cells]

    def logS(t, theta):
        f, g = _uniform_exp_expect(t[:, None], na, nb, theta[1:][None, :])
        f = np.clip(f, 1e-300, None)
        val = -theta[0] * t + np.log(f).sum(axis=1)
        grad = np.concatenate([-t[:, None], g / f], axis=1)
        return val, grad

    def nll(theta):
        la, ga = logS(Li, theta)
        lu, gu = logS(np.where(np.isfinite(Ui), Ui, T), theta)
        r = np.exp(np.minimum(lu - la, 0.0))         # S(U)/S(L) in (0, 1]
        one_minus = np.clip(1.0 - r, 1e-300, None)
        val = np.where(burned_c, la + np.log(one_minus), la)
        dval = np.where(burned_c[:, None], (ga - r[:, None] * gu) / one_minus[:, None], ga)
        return -val.sum(), -dval.sum(axis=0)

    D1 = len(problem.k) + 1
    x0 = np.full(D1, 0.02) if x0 is None else x0
    res = minimize(nll, x0, jac=True, method="L-BFGS-B", bounds=[(floor, None)] * D1,
                   options=dict(maxiter=2000, ftol=1e-12, gtol=1e-9))
    return res.x


def _shift(p, dr, dc):
    """out[r, c] = p[r - dr, c - dc] (zero outside): the source at offset (dr, dc)."""
    n = p.shape[0]
    out = np.zeros_like(p)
    rs, re = max(dr, 0), n + min(dr, 0)
    cs, ce = max(dc, 0), n + min(dc, 0)
    out[rs:re, cs:ce] = p[rs - dr:re - dr, cs - dc:ce - dc]
    return out


def _meanfield_loss_grad(problem: Problem, theta, windows, targets, masks, loss):
    """Endpoint loss of the hourly mean field and its exact gradient (adjoint pass)."""
    n, offs = problem.n, problem.offs
    k0, k = theta[0], theta[1:]
    total, grad = 0.0, np.zeros_like(theta)
    for (p0, steps), y, m in zip(windows, targets, masks):
        p = p0.reshape(n, n).copy()
        states, rates = [], []
        for _ in range(steps):
            r = k0 + sum(kd * _shift(p, dr, dc) for (dr, dc), kd in zip(offs, k))
            states.append(p)
            rates.append(r)
            p = p + (1 - p) * (-np.expm1(-r))
        pe = np.clip(p.ravel(), 1e-7, 1 - 1e-7)
        yy = y
        if loss == "nll":
            total += -np.sum(m * (yy * np.log(pe) + (1 - yy) * np.log1p(-pe)))
            g = m * (-(yy / pe) + (1 - yy) / (1 - pe))
        else:
            total += np.sum(m * (pe - yy) ** 2)
            g = m * 2 * (pe - yy)
        g = g.reshape(n, n) * ((p > 1e-7) & (p < 1 - 1e-7))
        for p_prev, r in zip(reversed(states), reversed(rates)):
            e = np.exp(-r)
            gr = g * (1 - p_prev) * e                 # dL/dr
            grad[0] += gr.sum()
            back = g * e                              # d p'/d p (direct) = 1 - (1 - e) = e
            for j, ((dr, dc), kd) in enumerate(zip(offs, k)):
                grad[1 + j] += np.sum(gr * _shift(p_prev, dr, dc))
                back += kd * _shift(gr, -dr, -dc)
            g = back
    return total, grad


def fit_meanfield(problem: Problem, obs: dict, *, loss="nll", floor=1e-9):
    surveys = obs["surveys"]
    tau = problem.tau          # perimeter states at survey times are exact functions of tau
    windows, targets, masks = [], [], []
    for a, b in zip(surveys[:-1], surveys[1:]):
        start = (tau <= a).astype(float)
        if start.sum() == 0:
            continue
        windows.append((start, int(round(b - a))))
        targets.append((tau <= b).astype(float))
        masks.append((start == 0).astype(float))
    f = lambda th: _meanfield_loss_grad(problem, th, windows, targets, masks, loss)
    D1 = len(problem.k) + 1
    res = minimize(f, np.full(D1, 0.02), jac=True, method="L-BFGS-B", bounds=[(floor, None)] * D1,
                   options=dict(maxiter=1000, ftol=1e-12, gtol=1e-9))
    return res.x


def timed(fn, *a, memory=False, **kw):
    """(result, seconds, peak MiB or None).  tracemalloc slows Python-heavy loops,
    so memory is measured in a separate pass from timing."""
    if memory:
        tracemalloc.start()
    t0 = time.perf_counter()
    out = fn(*a, **kw)
    dt = time.perf_counter() - t0
    peak = None
    if memory:
        peak = tracemalloc.get_traced_memory()[1] / 2**20
        tracemalloc.stop()
    return out, dt, peak


MCEM_SHORT = dict(iterations=30, sweeps=3, keep=2, average_last=10)
MCEM_LONG = dict(iterations=60, sweeps=6, keep=5, average_last=30)


# ------------------------------------------------- composite shape + scalar rate (Iris)

def _simulate_window(problem: Problem, burned0: np.ndarray, length: float, rates: np.ndarray, k0: float, rng):
    """Exact Markov forward simulation over one survey window from a known burned set.

    Sources burned at the window start act through memoryless exponential delays, so
    first passage with Exp(k_d) delays from the window start is exact. Returns the
    number of newly burned cells by the window end."""
    n, offs = problem.n, problem.offs
    tau = np.full(n * n, INF)
    heap = [(0.0, int(i)) for i in np.flatnonzero(burned0)]
    tau[burned0] = 0.0
    if k0 > 0:
        bg = rng.exponential(1.0 / k0, size=n * n)
        for i in np.flatnonzero((bg <= length) & ~burned0):
            tau[i] = bg[i]
            heap.append((bg[i], int(i)))
    heapq.heapify(heap)
    done = np.zeros(n * n, bool)
    ok_rate = rates > 0
    while heap:
        t, j = heapq.heappop(heap)
        if done[j] or t > length:
            continue
        done[j] = True
        r, c = divmod(j, n)
        tr, tc = r + offs[ok_rate, 0], c + offs[ok_rate, 1]
        inside = (tr >= 0) & (tr < n) & (tc >= 0) & (tc < n)
        tgt = tr[inside] * n + tc[inside]
        cand = t + rng.exponential(1.0 / rates[ok_rate][inside])
        better = (cand < tau[tgt]) & ~done[tgt] & (cand <= length)
        for i, v in zip(tgt[better], cand[better]):
            if v < tau[i]:
                tau[i] = v
                heapq.heappush(heap, (v, int(i)))
    return int((done & ~burned0).sum())


def fit_scale_by_simulation(problem: Problem, obs: dict, shape_theta: np.ndarray, *, n_sims=8, seed=0,
                            lo=0.1, hi=20.0, iters=14):
    """Scalar multiplier m on a fixed kernel shape, by matching total new-burn counts.

    For every survey window the exact state at its start is known (perimeter states); the
    expected number of new cells under m * shape is estimated by exact simulation with common
    random numbers, and m is found by bisection on log m so that the simulated total equals
    the observed total (method of moments; the count is increasing in m)."""
    surveys = obs["surveys"]
    hi_t = np.where(obs["burned"], obs["hi"], INF)
    windows = []
    for a, b in zip(surveys[:-1], surveys[1:]):
        start = hi_t <= a
        if start.any():
            windows.append((start, float(b - a), int(((hi_t > a) & (hi_t <= b)).sum())))
    target = sum(w[2] for w in windows)

    def expected(m):
        rng = np.random.default_rng(seed)          # common random numbers across m
        tot = 0.0
        for _ in range(n_sims):
            for start, length, _ in windows:
                tot += _simulate_window(problem, start, length, m * shape_theta[1:], m * shape_theta[0], rng)
        return tot / n_sims

    a, b = np.log(lo), np.log(hi)
    for _ in range(iters):
        mid = 0.5 * (a + b)
        if expected(np.exp(mid)) < target:
            a = mid
        else:
            b = mid
    m = float(np.exp(0.5 * (a + b)))
    return m * shape_theta, m


def fit_composite_then_scale(problem: Problem, obs: dict, **kw):
    shape = fit_bracket_composite(problem, obs)
    theta, _ = fit_scale_by_simulation(problem, obs, shape, **kw)
    return theta


# ----------------------------------------------------- missed detections (Iris)

def observe_detections(problem: Problem, rng, *, every=12.0, q=0.0, left_open=False):
    """Overpass detections with miss probability q per overpass after arrival.

    A burned cell is first detected at the first overpass at or after its arrival whose
    independent detection draw succeeds (probability 1 - q each time). Cells never detected
    by T look unburned (censored), as in real active-fire data. Bracket of a detected cell:
    hard ``(previous overpass, first detection]`` (``left_open=False``), which is wrong when
    earlier overpasses missed it, or left-open ``(0, first detection]``."""
    over = np.arange(0.0, problem.T + 1e-9, every)
    if over[-1] < problem.T:
        over = np.append(over, problem.T)
    tau = problem.tau
    burned = np.isfinite(tau) & (tau <= problem.T)
    det = np.full(problem.cells, np.nan)
    k0 = np.searchsorted(over, tau, side="left")
    for i in np.flatnonzero(burned):
        for k in range(int(k0[i]), len(over)):
            if rng.uniform() >= q:
                det[i] = over[k]
                break
    seen = np.isfinite(det)
    seen[problem.seeds] = True
    det[problem.seeds] = 0.0
    kk = np.searchsorted(over, det, side="left")
    lo = np.where(seen, 0.0 if left_open else over[np.clip(kk - 1, 0, None)], np.nan)
    hi = np.where(seen, det, np.nan)
    lo[problem.seeds] = hi[problem.seeds] = 0.0
    return dict(kind="perimeter", lo=lo, hi=hi, burned=seen, surveys=over,
                missed_cells=int((burned & ~seen).sum()))
