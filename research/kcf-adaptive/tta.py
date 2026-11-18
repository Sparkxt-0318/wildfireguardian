"""Arm 1 core: test-time adaptation of a small set of c651's parameters (PROTOCOL.md 2.3).

The adapted parameters are offsets added to c651's own tensors:
  P4:  model.mixing_logits                                   (4 numbers)
  P+:  P4 and branches.<k>.kernel_network.output.bias        (9 + 25 + 49 + 81 = 164 numbers)
Everything else stays as in the checkpoint. The rollout is c651's mean field (forecast/wildfire/meanfield.py):
p <- p + (1 - p)(1 - exp(-dt * sum_delta K[delta] p[i + delta])), absorbing, zero boundary, whole hours then
the remainder. `repo_meanfield` runs the repository's own implementation for the equality check.
"""
from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as Fn

import fastmf
from cases import C651, C651_SHA256, REPO, Window

sys.path.insert(0, str(REPO / "forecast"))
from wildfire.inference import load_trained_model  # noqa: E402
from wildfire.survival import step_durations  # noqa: E402

LR, STEPS, PENALTY = 0.05, 60, 0.01
DTYPE = torch.float64
SETS = ("P4", "P+")


class C651Model:
    def __init__(self):
        if hashlib.sha256(C651.read_bytes()).hexdigest() != C651_SHA256:
            raise ValueError("checkpoint is not c651")
        self.tm = load_trained_model(C651).to(DTYPE).eval()
        for p in self.tm.parameters():
            p.requires_grad_(False)
        self.m = self.tm.model
        self.sizes = self.m.kernel_sizes
        self.n_params = sum(p.numel() for p in self.tm.parameters())

    def hidden(self, env_raw: np.ndarray) -> dict:
        """Frozen part of the kernel generator for one environment snapshot [19, H, W] (raw units)."""
        env = torch.as_tensor(env_raw, dtype=DTYPE)[None]
        fv = torch.isfinite(env)
        if not bool(fv.all()):
            raise ValueError("environment snapshot has missing values")
        with torch.no_grad():
            self.tm._validate_one_hot(env, fv)
            clean, available = self.m._features((env - self.tm.mean) / self.tm.std, fv, "zero")
            if not bool(available.all()):
                raise ValueError("incomplete environmental context")
            out = {}
            for s in self.sizes:
                net = self.m.branches[str(s)].kernel_network
                out[s] = net.hidden(net.spatial(clean))
        return out

    def zero_theta(self, which: str) -> dict:
        th = {"mix": torch.zeros(len(self.sizes), dtype=DTYPE, requires_grad=True)}
        if which == "P+":
            for s in self.sizes:
                th[f"bias{s}"] = torch.zeros(s * s, dtype=DTYPE, requires_grad=True)
        elif which != "P4":
            raise ValueError(which)
        return th

    def kernels(self, hidden: dict, theta: dict | None) -> torch.Tensor:
        """Combined hourly offset rates [1, 81, H, W] with the adapted offsets applied."""
        mix = self.m.mixing_logits if theta is None else self.m.mixing_logits + theta["mix"]
        w = Fn.softplus(mix)
        total = None
        for i, s in enumerate(self.sizes):
            br = self.m.branches[str(s)]
            net = br.kernel_network
            bias = net.output.bias if theta is None or f"bias{s}" not in theta else net.output.bias + theta[f"bias{s}"]
            rates = Fn.softplus(Fn.conv2d(hidden[s], net.output.weight, bias)) * br.off_center
            part = w[i] * self.m._embed(rates, s)
            total = part if total is None else total + part
        return total


def rollout(K: torch.Tensor, initial: np.ndarray, hours: float) -> torch.Tensor:
    """New-burn probability [H, W] at the end of the window (0 on cells burned at cut-off)."""
    h, w = initial.shape
    k = math.isqrt(K.shape[1])
    b = torch.as_tensor(initial, dtype=DTYPE)[None, None]
    p = b
    for dt in step_durations(hours):
        u = Fn.unfold(p, k, padding=k // 2).reshape(1, k * k, h, w)
        rate = (K * u).sum(dim=1, keepdim=True)
        p = p + (1 - p) * -torch.expm1(-rate * dt)
    return (p * (1 - b))[0, 0]


def repo_meanfield(model: C651Model, env_raw: np.ndarray, initial: np.ndarray, hours: float) -> np.ndarray:
    """The repository's own mean-field forecast of unadapted c651 (for the equality check)."""
    from wildfire.meanfield import propagate_mean_field
    env = torch.as_tensor(env_raw, dtype=DTYPE)[None]
    p0 = torch.as_tensor(initial, dtype=DTYPE)[None, None]
    with torch.no_grad():
        r = propagate_mean_field(model.tm, p0, env, step_durations(hours), channel_names=model.tm.channel_names,
                                 p0_valid=torch.ones_like(p0, dtype=torch.bool), feature_valid=torch.isfinite(env),
                                 boundary="zero")
    if not bool(r.valid[-1].all()):
        raise ValueError("mean-field support is incomplete")
    return r.new_burn_probability[-1][0, 0].numpy()


def window_brier(p_grid: torch.Tensor, w: Window) -> torch.Tensor:
    y = torch.as_tensor(w.y, dtype=DTYPE)
    return ((p_grid[torch.as_tensor(w.row), torch.as_tensor(w.col)] - y) ** 2).mean()


def _np_kernels(K: torch.Tensor) -> np.ndarray:
    return np.ascontiguousarray(K.detach()[0].permute(1, 2, 0).numpy())


def fast_new_burn(K: torch.Tensor, w: Window):
    """Compiled rollout: new-burn probability on the scored cells, plus what the adjoint needs."""
    Kn = _np_kernels(K)
    dur = np.array(step_durations(w.hours), float)
    P, E = fastmf.forward(Kn, w.initial.astype(np.float64), dur)
    r = (P.shape[1] - w.shape[0]) // 2
    final = P[-1, r:r + w.shape[0], r:r + w.shape[1]]
    return final[w.row, w.col], (Kn, P, E, dur)


def adapt(model: C651Model, which: str, hist: list[Window], hidden_of) -> dict | None:
    """Fit the offsets on the history windows only. Returns None when there is no history.

    Objective (PROTOCOL 2.3): mean over history windows of the window Brier score + PENALTY * |offsets|^2.
    The gradient with respect to the kernels comes from the exact adjoint in fastmf; torch autograd carries
    it from the kernels to the offsets.
    """
    if not hist:
        return None
    theta = model.zero_theta(which)
    params = list(theta.values())
    opt = torch.optim.Adam(params, lr=LR)
    cached = [(hidden_of(w), w) for w in hist]
    for _ in range(STEPS):
        opt.zero_grad()
        (PENALTY * sum((p ** 2).sum() for p in params)).backward()
        for hid, w in cached:                # one window at a time; gradients add up
            K = model.kernels(hid, theta)
            p, (Kn, P, E, dur) = fast_new_burn(K, w)
            a = np.zeros(w.shape)
            a[w.row, w.col] = 2.0 * (p - w.y) / (len(w.y) * len(cached))
            GK = fastmf.backward(Kn, P, E, dur, a)
            K.backward(torch.from_numpy(GK).permute(2, 0, 1)[None])
        opt.step()
    return {k: v.detach().clone() for k, v in theta.items()}


def predict(model: C651Model, theta: dict | None, w: Window, hidden_of) -> np.ndarray:
    with torch.no_grad():
        K = model.kernels(hidden_of(w), theta)
    return fast_new_burn(K, w)[0].copy()


def theta_vector(theta: dict | None, which: str, sizes=(3, 5, 7, 9)) -> np.ndarray:
    n = 4 + (sum(s * s for s in sizes) if which == "P+" else 0)
    if theta is None:
        return np.zeros(n)
    keys = ["mix"] + ([f"bias{s}" for s in sizes] if which == "P+" else [])
    return np.concatenate([theta[k].numpy().ravel() for k in keys])
