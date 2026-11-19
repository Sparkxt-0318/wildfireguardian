"""Cached safe-distance evaluation for many cells (PROTOCOL.md section 4.6).

d*(L, theta, P_w) is evaluated exactly (radiation.safe_distance) at inputs rounded to the conservative side:
L rounded UP to the next 1 % step in log L, theta rounded UP to the next 0.5 degree, P_w rounded DOWN to the next
5 % step (50 % for the worst-angle view factor; less water vapour = higher transmissivity). Each rounding can only increase d* where d* is monotone in
that input (tested for L and P_w; for theta the tilt toward the receiver increases the view factor). Results are
memoised, so a fire with thousands of cells needs a few hundred evaluations.

Interpolating a table was tried first and rejected: d* has a kink where the flame tip passes the receiver height,
and linear interpolation across it was up to 20 % low.
"""
from __future__ import annotations

import math

import numpy as np

from . import radiation

LOG_STEP_L = math.log(1.01)
TH_STEP = math.radians(0.5)
LOG_STEP_PW = math.log(1.05)


def _temp_for_pw(pw):
    """Air temperature (C) whose saturation vapour pressure is pw (inverse of Alduchov-Eskridge); with RH = 100 %
    this reproduces partial pressure pw in radiation.transmissivity_pietersen."""
    a = math.log(pw / 610.94)
    return 243.04 * a / (17.625 - a)


def round_inputs(L, theta, pw, pw_step=LOG_STEP_PW):
    Lr = math.exp(math.ceil(math.log(max(L, 1e-6)) / LOG_STEP_L - 1e-9) * LOG_STEP_L)
    tr = math.ceil(theta / TH_STEP - 1e-9) * TH_STEP
    pr = math.exp(math.floor(math.log(pw) / pw_step + 1e-9) * pw_step) if pw and pw > 0 else 0.0
    return Lr, tr, pr


_SHARED = {}  # memo shared by every cache with the same physical setting (persists across fire inputs)


class DstarCache:
    def __init__(self, q_star, T_flame_K, emissivity, kind, W=375.0, z_r=1.5, transmissivity=True):
        self.q, self.T, self.eps, self.kind, self.W, self.z_r, self.tau = q_star, T_flame_K, emissivity, kind, W, z_r, transmissivity
        # the worst-angle view factor costs ~100 integrations per evaluation: humidity is rounded down in 50 % steps
        self.pw_step = math.log(1.5) if kind == "tilted_max" else LOG_STEP_PW
        self.memo = _SHARED.setdefault((q_star, T_flame_K, emissivity, kind, W, z_r, transmissivity), {})

    def one(self, L, theta=0.0, pw=1000.0):
        if not (L > 0):
            return 0.0
        if self.kind != "tilted":
            theta = 0.0
        key = round_inputs(L, theta, pw if self.tau else 0.0, self.pw_step)
        if key not in self.memo:
            Lr, tr, pr = key
            fl = radiation.Flame(Lr, tr, self.W)
            kw = dict(T_flame_K=self.T, emissivity=self.eps, vf_kind=self.kind, z_r=self.z_r)
            if self.tau and pr > 0:
                kw.update(rh_pct=100.0, T_air_C=_temp_for_pw(pr))
            self.memo[key] = radiation.safe_distance(self.q, fl, **kw)
        return self.memo[key]

    def __call__(self, L, theta=0.0, pw=1000.0):
        L = np.atleast_1d(np.asarray(L, dtype=float))
        th = np.broadcast_to(np.asarray(theta, dtype=float), L.shape)
        p = np.broadcast_to(np.asarray(pw, dtype=float), L.shape)
        return np.array([self.one(a, b, c) for a, b, c in zip(L.tolist(), th.tolist(), p.tolist())])
