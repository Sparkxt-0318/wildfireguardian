"""Continuous-time first-passage sampler and reference cellular automata for SMOKE-type kernels.

Model (same parameterisation as ``forecast/wildfire/models.py``):

    kernel array K[s, c, y, x] >= 0, units 1/h, s = hourly weather segment,
    c = row-major offset index of a K-by-K stencil (dy, dx) in -r..r,
    PyTorch cross-correlation convention: coefficient (dy, dx) stored at
    target (y, x) multiplies the source cell (y + dy, x + dx).

    Hazard of an unburned target i at time t:
        lambda_i(t) = sum_c K[seg(t), c, i] * B_{i + delta_c}(t)
    Burning is absorbing and a burned cell keeps emitting (no burnout), as in
    ``wildfire.rollout.simulate``.

Hourly CA (the existing recursion): B is frozen within each step and
P(ignite during dt) = 1 - exp(-dt * lambda_i). With dt -> 0 this is the
continuous-time Markov jump process with the same intensities.

First-passage sampler (this module): attach an independent Exp(1) variable
E_{s,i} to each source -> target pair. Target i ignites at
    T_i = min_s inf{t > T_s : int_{T_s}^t K[seg(u), c(s,i), i] du >= E_{s,i}}.
Because burned sources emit forever and intensities are additive, this has
exactly the law of the Markov jump process (superposition of independent
Poisson clocks; the absorbing target ignores clocks after it ignites). The
time-dependent edge delay is FIFO (arrival is nondecreasing in T_s), so
time-dependent Dijkstra from the initially burned set is exact.

Segments: segment j covers [j*seg_len, (j+1)*seg_len); the last segment
extends to infinity (repeated-current-weather policy if S == 1).
Boundary: sources outside the grid do not exist (the forecast's 'zero'
boundary). Unknown-cell / coverage envelopes are not modelled here.
"""
from __future__ import annotations

import heapq
import math

import numpy as np
from numba import njit


def stencil_offsets(kernel_size: int) -> np.ndarray:
    """Row-major (dy, dx) offsets, matching the forecast's channel order."""
    if kernel_size < 3 or kernel_size % 2 != 1:
        raise ValueError("kernel_size must be odd and >= 3")
    r = kernel_size // 2
    return np.array([(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1)],
                    dtype=np.int64)


def _check(K: np.ndarray, initial: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    K = np.ascontiguousarray(K, dtype=np.float64)
    if K.ndim == 3:
        K = K[None]
    if K.ndim != 4:
        raise ValueError("K must be [S, K*K, H, W] or [K*K, H, W]")
    k = math.isqrt(K.shape[1])
    if k * k != K.shape[1]:
        raise ValueError("channel count must be a perfect square")
    if not np.isfinite(K).all() or (K < 0).any():
        raise ValueError("K must be finite and nonnegative")
    initial = np.ascontiguousarray(initial, dtype=np.bool_)
    if initial.shape != K.shape[2:]:
        raise ValueError("initial must be [H, W] matching K")
    return K, initial, stencil_offsets(k)


# --------------------------------------------------------------------------------------
# First-passage sampler
# --------------------------------------------------------------------------------------

@njit(cache=True)
def _edge_arrival(K, c, ty, tx, t0, e, seg_len, horizon):
    """Smallest t >= t0 with int_{t0}^t K[seg(u), c, ty, tx] du = e; inf if beyond horizon."""
    S = K.shape[0]
    j = int(math.floor(t0 / seg_len))
    if j > S - 1:
        j = S - 1
    t = t0
    rem = e
    while True:
        rate = K[j, c, ty, tx]
        end = np.inf if j == S - 1 else (j + 1) * seg_len
        if rate > 0.0:
            need = rem / rate
            if t + need <= end:
                res = t + need
                return res if res <= horizon else np.inf
            rem -= rate * (end - t)
        if end >= horizon:
            return np.inf
        t = end
        j += 1


@njit(cache=True)
def _fpp_one(K, offs, initial_flat, horizon, seg_len, arrival, done, positive, parent):
    """One trajectory of time-dependent Dijkstra.

    Fills ``arrival`` (inf = not burned by horizon) and ``parent`` (shortest-path-tree predecessor,
    -1 for initially burned or unreached cells).
    """
    S, KK, H, W = K.shape
    n = H * W
    heap = [(0.0, np.int64(-1))]
    heap.pop()
    for idx in range(n):
        done[idx] = False
        parent[idx] = -1
        if initial_flat[idx]:
            arrival[idx] = 0.0
            heapq.heappush(heap, (0.0, np.int64(idx)))
        else:
            arrival[idx] = np.inf
    while len(heap) > 0:
        t, s = heapq.heappop(heap)
        if done[s] or t > arrival[s]:
            continue
        done[s] = True
        sy = s // W
        sx = s - sy * W
        for c in range(KK):
            ty = sy - offs[c, 0]
            tx = sx - offs[c, 1]
            if ty < 0 or ty >= H or tx < 0 or tx >= W:
                continue
            ti = ty * W + tx
            if done[ti] or not positive[c, ty, tx]:
                continue
            e = np.random.exponential(1.0)
            ta = _edge_arrival(K, c, ty, tx, t, e, seg_len, horizon)
            if ta < arrival[ti]:
                arrival[ti] = ta
                parent[ti] = s
                heapq.heappush(heap, (ta, np.int64(ti)))


@njit(cache=True)
def _fpp_counts(K, offs, initial_flat, horizons, seg_len, n_samples, seed, keep):
    S, KK, H, W = K.shape
    n = H * W
    np.random.seed(seed)
    positive = np.zeros((KK, H, W), dtype=np.bool_)
    for j in range(S):
        for c in range(KK):
            for y in range(H):
                for x in range(W):
                    if K[j, c, y, x] > 0.0:
                        positive[c, y, x] = True
    nh = horizons.shape[0]
    hmax = horizons.max()
    counts = np.zeros((nh, n), dtype=np.int64)
    kept = np.empty((keep, n), dtype=np.float64)
    arrival = np.empty(n, dtype=np.float64)
    done = np.empty(n, dtype=np.bool_)
    parent = np.empty(n, dtype=np.int64)
    for m in range(n_samples):
        _fpp_one(K, offs, initial_flat, hmax, seg_len, arrival, done, positive, parent)
        if m < keep:
            kept[m, :] = arrival
        for idx in range(n):
            if initial_flat[idx]:
                continue
            a = arrival[idx]
            for h in range(nh):
                if a <= horizons[h]:
                    counts[h, idx] += 1
    return counts, kept


def first_passage(K, initial, horizons, *, n_samples, seed, seg_len=1.0, keep_arrivals=0):
    """Monte Carlo first-passage forecast.

    Returns ``(counts [len(horizons), H, W], arrivals [keep, H, W])`` where counts are the
    number of trajectories in which an initially unburned cell is burned by each horizon and
    arrivals are the full arrival-time fields (inf = not burned by max(horizons)) of the first
    ``keep_arrivals`` trajectories.
    """
    K, initial, offs = _check(K, initial)
    horizons = np.asarray(horizons, dtype=np.float64)
    H, W = initial.shape
    counts, kept = _fpp_counts(K, offs, initial.ravel(), horizons, float(seg_len),
                               int(n_samples), int(seed), int(keep_arrivals))
    return counts.reshape(len(horizons), H, W), kept.reshape(-1, H, W)


# --------------------------------------------------------------------------------------
# Reference synchronous CA (independent re-implementation of the hourly recursion)
# --------------------------------------------------------------------------------------

def stencil_rate(K_seg: np.ndarray, offs: np.ndarray, states: np.ndarray) -> np.ndarray:
    """lambda[b, y, x] = sum_c K_seg[c, y, x] * states[b, y + dy, x + dx] (zero outside)."""
    B, H, W = states.shape
    r = int(np.abs(offs).max())
    padded = np.zeros((B, H + 2 * r, W + 2 * r), dtype=np.float64)
    padded[:, r:r + H, r:r + W] = states
    lam = np.zeros((B, H, W), dtype=np.float64)
    for c, (dy, dx) in enumerate(offs):
        kc = K_seg[c]
        if not kc.any():
            continue
        lam += kc * padded[:, r + dy:r + dy + H, r + dx:r + dx + W]
    return lam


def cellular_automaton(K, initial, horizons, *, dt, n_samples, seed, seg_len=1.0,
                       batch=500, return_totals=False, half_step=False, return_cmc=False):
    """Synchronous CA with step ``dt`` (hours) and link P = 1 - exp(-dt * lambda).

    ``dt`` must divide ``seg_len`` and every horizon. dt = 1 reproduces the semantics of
    ``wildfire.rollout.simulate`` (cumulative absorbing sources, synchronous update).

    ``half_step=True`` (Iris's lag-correction arm, an approximation): after each step's draws, cells
    that ignited in this step also act as sources for half a step (the expected remaining fraction of
    the step for an ignition time uniform in it), giving still-unburned targets an extra ignition
    probability 1 - exp(-dt/2 * lambda_new). No further cascade within the step.

    ``return_cmc=True`` (standard CA only): also return the conditional estimator
    Y_i(t) = sum_{steps k <= t} 1{i unburned before k} q_i(k) per trajectory, whose mean is P(i burned
    by t) exactly (each term has expectation P(i ignites at step k)). Returned as a dict with
    ``counts``, ``totals``, ``cmc_mean`` and ``cmc_var`` (per-trajectory variance).
    """
    if half_step and return_cmc:
        raise ValueError("return_cmc is defined for the standard CA only")
    K, initial, offs = _check(K, initial)
    S = K.shape[0]
    horizons = np.asarray(horizons, dtype=np.float64)
    steps_per_seg = seg_len / dt
    if abs(steps_per_seg - round(steps_per_seg)) > 1e-9:
        raise ValueError("dt must divide seg_len")
    steps_per_seg = int(round(steps_per_seg))
    record = {}
    for i, h in enumerate(horizons):
        k = h / dt
        if abs(k - round(k)) > 1e-9:
            raise ValueError("dt must divide every horizon")
        record[int(round(k))] = i
    total_steps = max(record)
    H, W = initial.shape
    counts = np.zeros((len(horizons), H, W), dtype=np.int64)
    totals = np.zeros((len(horizons), n_samples), dtype=np.int64)
    cmc1 = np.zeros((len(horizons), H, W))
    cmc2 = np.zeros((len(horizons), H, W))
    rng = np.random.default_rng(seed)
    for start in range(0, n_samples, batch):
        size = min(batch, n_samples - start)
        states = np.broadcast_to(initial, (size, H, W)).copy()
        Y = np.zeros((size, H, W)) if return_cmc else None
        for step in range(total_steps):
            seg = min(step // steps_per_seg, S - 1)
            lam = stencil_rate(K[seg], offs, states)
            q = -np.expm1(-dt * lam)
            if return_cmc:
                Y += np.where(states, 0.0, q)
            ignite = (~states) & (rng.random((size, H, W)) < q)
            states |= ignite
            if half_step and ignite.any():
                lam_new = stencil_rate(K[seg], offs, ignite)
                q2 = -np.expm1(-0.5 * dt * lam_new)
                states |= (~states) & (rng.random((size, H, W)) < q2)
            if step + 1 in record:
                new = states & ~initial
                r = record[step + 1]
                counts[r] += new.sum(axis=0)
                totals[r, start:start + size] = new.sum(axis=(1, 2))
                if return_cmc:
                    cmc1[r] += Y.sum(axis=0)
                    cmc2[r] += (Y ** 2).sum(axis=0)
    if return_cmc:
        mean = cmc1 / n_samples
        return dict(counts=counts, totals=totals, cmc_mean=mean, cmc_var=cmc2 / n_samples - mean ** 2)
    return (counts, totals) if return_totals else counts


# --------------------------------------------------------------------------------------
# Conditional Monte Carlo (cut on the in-edges of each cell)
# --------------------------------------------------------------------------------------

@njit(cache=True)
def _cum_hazard(K, c, ty, tx, u, seg_len):
    """int_0^u K[seg(v), c, ty, tx] dv."""
    S = K.shape[0]
    total = 0.0
    j = 0
    start = 0.0
    while start < u:
        end = np.inf if j == S - 1 else (j + 1) * seg_len
        stop = u if u < end else end
        total += K[j, c, ty, tx] * (stop - start)
        start = end
        j += 1
    return total


@njit(cache=True)
def _is_descendant(s, i, parent, arrival):
    """True if cell i lies on the shortest-path-tree ancestor chain of cell s."""
    p = s
    ti = arrival[i]
    while p != -1 and arrival[p] > ti:
        p = parent[p]
    return p == i


@njit(cache=True)
def _fpp_cmc(K, offs, initial_flat, horizons, seg_len, n_samples, seed):
    """Per-trajectory plain indicators and conditional estimators, accumulated as sums and squares.

    For cell i and horizon t the conditional estimator is
        P(T_i <= t | T^{-i}) = 1 - exp(-sum_s [Lambda_si(t) - Lambda_si(T_s^{-i})]^+),
    exact because a first passage to i never passes through i and E_si is independent of T^{-i}.
    From one Dijkstra, T_s^{-i} = T_s for every in-neighbour s that is not a descendant of i in the
    shortest-path tree. Descendants have T_s^{-i} >= T_s > T_i: dropping them gives the lower bound
    ``lo``; using their full-graph T_s gives the upper bound ``hi``. If T_i >= t, every descendant has
    T_s > t and contributes nothing, so lo == hi exactly on the cells not burned by t.
    """
    S, KK, H, W = K.shape
    n = H * W
    np.random.seed(seed)
    positive = np.zeros((KK, H, W), dtype=np.bool_)
    for j in range(S):
        for c in range(KK):
            for y in range(H):
                for x in range(W):
                    if K[j, c, y, x] > 0.0:
                        positive[c, y, x] = True
    nh = horizons.shape[0]
    hmax = horizons.max()
    plain = np.zeros((nh, n))
    lo1 = np.zeros((nh, n))
    lo2 = np.zeros((nh, n))
    hi1 = np.zeros((nh, n))
    gap_cells = np.zeros(nh, dtype=np.int64)
    arrival = np.empty(n)
    done = np.empty(n, dtype=np.bool_)
    parent = np.empty(n, dtype=np.int64)
    for m in range(n_samples):
        _fpp_one(K, offs, initial_flat, hmax, seg_len, arrival, done, positive, parent)
        for i in range(n):
            if initial_flat[i]:
                continue
            ty = i // W
            tx = i - ty * W
            for h in range(nh):
                t = horizons[h]
                if arrival[i] <= t:
                    plain[h, i] += 1.0
                a_lo = 0.0
                a_hi = 0.0
                for c in range(KK):
                    if not positive[c, ty, tx]:
                        continue
                    sy = ty + offs[c, 0]
                    sx = tx + offs[c, 1]
                    if sy < 0 or sy >= H or sx < 0 or sx >= W:
                        continue
                    s = sy * W + sx
                    ts = arrival[s]
                    if ts >= t:
                        continue
                    contrib = _cum_hazard(K, c, ty, tx, t, seg_len) - _cum_hazard(K, c, ty, tx, ts, seg_len)
                    a_hi += contrib
                    if arrival[i] < t and _is_descendant(s, i, parent, arrival):
                        continue
                    a_lo += contrib
                p_lo = -math.expm1(-a_lo)
                p_hi = -math.expm1(-a_hi)
                lo1[h, i] += p_lo
                lo2[h, i] += p_lo * p_lo
                hi1[h, i] += p_hi
                if p_hi > p_lo:
                    gap_cells[h] += 1
    return plain, lo1, lo2, hi1, gap_cells


def first_passage_cmc(K, initial, horizons, *, n_samples, seed, seg_len=1.0):
    """Plain and conditional Monte Carlo burn-probability estimates from the same trajectories.

    Returns a dict of [len(horizons), H, W] arrays: ``plain`` (mean indicator), ``cmc_lo`` and
    ``cmc_hi`` (means of the lower/upper conditional estimators), ``cmc_lo_var`` (per-trajectory
    variance of the lower estimator), and ``gap_fraction`` [len(horizons)]: share of (trajectory,
    cell) pairs where the bounds differ.
    """
    K, initial, offs = _check(K, initial)
    horizons = np.asarray(horizons, dtype=np.float64)
    H, W = initial.shape
    plain, lo1, lo2, hi1, gap = _fpp_cmc(K, offs, initial.ravel(), horizons, float(seg_len),
                                         int(n_samples), int(seed))
    n = n_samples
    shape = (len(horizons), H, W)
    lo_mean = lo1 / n
    return dict(plain=(plain / n).reshape(shape), cmc_lo=lo_mean.reshape(shape),
                cmc_hi=(hi1 / n).reshape(shape),
                cmc_lo_var=(lo2 / n - lo_mean ** 2).reshape(shape),
                gap_fraction=gap / (n * (~initial).sum()))
