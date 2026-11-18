"""Compiled mean-field rollout and its exact adjoint (reverse-mode gradient), for Arm 1.

Same recursion as forecast/wildfire/meanfield.py for an absorbing source and a zero boundary:
    lambda[i] = sum_delta K[i, delta] * p[i + delta],   p <- p + (1 - p) * (1 - exp(-dt * lambda)).
K is [H, W, k*k] with the row-major offset order of torch's unfold. `backward` returns dLoss/dK for a loss
that depends on the final state only; tests/test_tta.py checks it against torch autograd.
"""
import math

import numpy as np
from numba import njit


@njit(cache=True)
def forward(K, initial, durations):
    """Returns padded states P [S+1, H+2r, W+2r] and the survival factors E [S, H, W] = exp(-dt * lambda)."""
    H, W, kk = K.shape
    k = int(round(math.sqrt(kk)))
    r = k // 2
    S = len(durations)
    P = np.zeros((S + 1, H + 2 * r, W + 2 * r))
    E = np.ones((S, H, W))
    for i in range(H):
        for j in range(W):
            P[0, i + r, j + r] = initial[i, j]
    for s in range(S):
        dt = durations[s]
        for i in range(H):
            for j in range(W):
                lam = 0.0
                for dy in range(k):
                    for dx in range(k):
                        lam += K[i, j, dy * k + dx] * P[s, i + dy, j + dx]
                f = -math.expm1(-dt * lam)
                pc = P[s, i + r, j + r]
                P[s + 1, i + r, j + r] = pc + (1.0 - pc) * f
                E[s, i, j] = 1.0 - f
    return P, E


@njit(cache=True)
def backward(K, P, E, durations, a_final):
    """dLoss/dK [H, W, k*k] given a_final = dLoss/dp at the final state [H, W]."""
    H, W, kk = K.shape
    k = int(round(math.sqrt(kk)))
    r = k // 2
    S = len(durations)
    GK = np.zeros_like(K)
    a = a_final.copy()
    for s in range(S - 1, -1, -1):
        dt = durations[s]
        nxt = np.zeros((H + 2 * r, W + 2 * r))
        for i in range(H):
            for j in range(W):
                aij = a[i, j]
                if aij == 0.0:
                    continue
                e = E[s, i, j]
                nxt[i + r, j + r] += aij * e
                g = aij * (1.0 - P[s, i + r, j + r]) * dt * e
                if g == 0.0:
                    continue
                for dy in range(k):
                    for dx in range(k):
                        idx = dy * k + dx
                        GK[i, j, idx] += g * P[s, i + dy, j + dx]
                        nxt[i + dy, j + dx] += K[i, j, idx] * g
        for i in range(H):
            for j in range(W):
                a[i, j] = nxt[i + r, j + r]
    return GK
