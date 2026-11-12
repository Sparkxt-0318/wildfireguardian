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
def _fpp_one(K, offs, initial_flat, horizon, seg_len, arrival, done, positive):
    """One trajectory of time-dependent Dijkstra; fills ``arrival`` (inf = not burned by horizon)."""
    S, KK, H, W = K.shape
    n = H * W
    heap = [(0.0, np.int64(-1))]
    heap.pop()
    for idx in range(n):
        done[idx] = False
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
    for m in range(n_samples):
        _fpp_one(K, offs, initial_flat, hmax, seg_len, arrival, done, positive)
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
                       batch=500, return_totals=False):
    """Synchronous CA with step ``dt`` (hours) and link P = 1 - exp(-dt * lambda).

    ``dt`` must divide ``seg_len`` and every horizon. dt = 1 reproduces the semantics of
    ``wildfire.rollout.simulate`` (cumulative absorbing sources, synchronous update).
    """
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
    rng = np.random.default_rng(seed)
    for start in range(0, n_samples, batch):
        size = min(batch, n_samples - start)
        states = np.broadcast_to(initial, (size, H, W)).copy()
        for step in range(total_steps):
            seg = min(step // steps_per_seg, S - 1)
            lam = stencil_rate(K[seg], offs, states)
            q = -np.expm1(-dt * lam)
            ignite = (~states) & (rng.random((size, H, W)) < q)
            states |= ignite
            if step + 1 in record:
                new = states & ~initial
                counts[record[step + 1]] += new.sum(axis=0)
                totals[record[step + 1], start:start + size] = new.sum(axis=(1, 2))
    return (counts, totals) if return_totals else counts
