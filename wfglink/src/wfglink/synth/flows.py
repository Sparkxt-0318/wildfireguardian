"""Analytic air-flow fields for the synthetic ember generator.

Every flow has `velocity(x, y, t) -> (u, v)`: the air velocity in px/s at image position
(x, y) in px and time t in s. Image coordinates are used throughout: x to the right and
y DOWN. Inputs broadcast against each other like numpy arrays and the outputs are float64
arrays of the broadcast shape.

Every field here is divergence free (du/dx + dv/dy = 0), so a passive tracer neither
bunches up nor thins out, and the ember density stays uniform where it started uniform.

Rotation sign convention (important because y points down)
-----------------------------------------------------------
Circulation Gamma is the line integral of the velocity around a closed curve traversed in
the positive sense of the image axes, which turns from +x toward +y. Because +y points
down, that sense looks CLOCKWISE on the screen. A vortex with Gamma > 0 therefore turns
clockwise as displayed: a point to the right of the centre moves down (+y) and a point
below the centre moves left (-x). In formulas, with r the distance to the centre,

    (u, v) = u_theta(r) / r * (-(y - cy), x - cx),

and Gamma = 2 pi r u_theta(r) far outside the core. The tests check this with a
numerical line integral around a circle parametrised as (cx + r cos a, cy + r sin a) for
increasing a.

Flows:
- Uniform(u, v): constant velocity.
- Shear(u0, dudy, y_ref, v): u = u0 + dudy (y - y_ref), v constant.
- Rankine(cx, cy, circulation, core_radius, background): solid-body rotation inside the
  core, potential vortex Gamma / (2 pi r) outside, plus a uniform background.
- LambOseen(cx, cy, circulation, core_radius, background): tangential speed
  Gamma / (2 pi r) (1 - exp(-r^2 / rc^2)), a smooth viscous core.
- RandomModes: a stream function made of n random Fourier modes, so the field is exactly
  divergence free; wavelengths are drawn log-uniformly in a range, each mode's phase drifts
  in time, and the amplitudes are scaled to a requested RMS speed.
- Sum(*flows): the sum of several flows.

`from_config(cfg)` builds any of them from a mapping with a "type" key.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

ArrayLike = float | np.ndarray


def _bcast(x: ArrayLike, y: ArrayLike, t: ArrayLike) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x, y, t = np.broadcast_arrays(np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64),
                                  np.asarray(t, dtype=np.float64))
    return x, y, t


class Flow:
    """Base class: an air velocity field in px/s, image coordinates (y down)."""

    def velocity(self, x: ArrayLike, y: ArrayLike, t: ArrayLike = 0.0) -> tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError

    def __add__(self, other: "Flow") -> "Sum":
        return Sum(self, other)


@dataclass
class Uniform(Flow):
    """Constant velocity (u, v) px/s."""

    u: float = 0.0
    v: float = 0.0

    def velocity(self, x, y, t=0.0):
        x, _, _ = _bcast(x, y, t)
        return np.full(x.shape, float(self.u)), np.full(x.shape, float(self.v))


@dataclass
class Shear(Flow):
    """Linear shear: u = u0 + dudy (y - y_ref), v constant. dudy is in 1/s."""

    u0: float = 0.0
    dudy: float = 0.0
    y_ref: float = 0.0
    v: float = 0.0

    def velocity(self, x, y, t=0.0):
        x, y, _ = _bcast(x, y, t)
        return self.u0 + self.dudy * (y - self.y_ref), np.full(x.shape, float(self.v))


@dataclass
class _Vortex(Flow):
    """Axisymmetric vortex plus a uniform background; subclasses give u_theta(r) / r."""

    cx: float = 0.0
    cy: float = 0.0
    circulation: float = 0.0           # px^2/s; > 0 turns clockwise on screen (see module docstring)
    core_radius: float = 1.0           # px
    background: tuple[float, float] = (0.0, 0.0)

    def _omega(self, r2: np.ndarray) -> np.ndarray:
        """u_theta(r) / r as a function of r^2 (an angular velocity in rad/s)."""
        raise NotImplementedError

    def velocity(self, x, y, t=0.0):
        x, y, _ = _bcast(x, y, t)
        dx, dy = x - self.cx, y - self.cy
        om = self._omega(dx * dx + dy * dy)
        return float(self.background[0]) - om * dy, float(self.background[1]) + om * dx

    def tangential_speed(self, r: ArrayLike) -> np.ndarray:
        r = np.asarray(r, dtype=np.float64)
        return self._omega(r * r) * r


class Rankine(_Vortex):
    """Rankine vortex: solid-body rotation for r < core_radius, potential vortex outside."""

    def _omega(self, r2):
        rc2 = float(self.core_radius) ** 2
        return self.circulation / (2 * np.pi) / np.maximum(r2, rc2)


class LambOseen(_Vortex):
    """Lamb-Oseen vortex: u_theta = Gamma / (2 pi r) (1 - exp(-r^2 / rc^2))."""

    def _omega(self, r2):
        rc2 = float(self.core_radius) ** 2
        safe = np.where(r2 > 1e-12 * rc2, r2, 1.0)
        f = np.where(r2 > 1e-12 * rc2, -np.expm1(-r2 / rc2) / safe, 1.0 / rc2)
        return self.circulation / (2 * np.pi) * f


@dataclass
class RandomModes(Flow):
    """Divergence-free random field from a stream function of n Fourier modes.

    psi(x, y, t) = sum_j a_j sin(k_j . (p - c t) + w_j t + phi_j), with p = (x, y) and
    c an optional advection velocity (the pattern drifts with it, Taylor's frozen
    turbulence). The velocity is u = d psi / dy, v = -d psi / dx, so du/dx + dv/dy = 0
    exactly. Wavelengths 2 pi / |k_j| are drawn log-uniformly in `wavelength_px`, directions
    uniformly, phase periods 2 pi / |w_j| log-uniformly in `period_s` with a random sign.
    Each mode's velocity amplitude a_j |k_j| is proportional to wavelength^spectrum_slope
    (1/3 mimics the Kolmogorov scaling of velocity increments), then all amplitudes are
    scaled so that the space-time RMS speed sqrt(<u^2 + v^2>) equals `rms_speed`
    (each mode contributes a_j^2 |k_j|^2 / 2 to <u^2 + v^2>).
    """

    n_modes: int = 16
    wavelength_px: tuple[float, float] = (150.0, 800.0)
    rms_speed: float = 50.0
    period_s: tuple[float, float] = (1.0, 4.0)
    spectrum_slope: float = 1.0 / 3.0
    advection: tuple[float, float] = (0.0, 0.0)
    seed: int = 0
    kx: np.ndarray = field(init=False, repr=False)
    ky: np.ndarray = field(init=False, repr=False)
    amp: np.ndarray = field(init=False, repr=False)
    omega: np.ndarray = field(init=False, repr=False)
    phase: np.ndarray = field(init=False, repr=False)

    def __post_init__(self) -> None:
        rng = np.random.default_rng(self.seed)
        n = int(self.n_modes)
        lo, hi = (float(v) for v in self.wavelength_px)
        lam = np.exp(rng.uniform(np.log(lo), np.log(hi), n))
        ang = rng.uniform(0, 2 * np.pi, n)
        kmag = 2 * np.pi / lam
        self.kx, self.ky = kmag * np.cos(ang), kmag * np.sin(ang)
        p_lo, p_hi = (float(v) for v in self.period_s)
        period = np.exp(rng.uniform(np.log(p_lo), np.log(p_hi), n))
        self.omega = 2 * np.pi / period * rng.choice([-1.0, 1.0], n)
        self.phase = rng.uniform(0, 2 * np.pi, n)
        vel_amp = (lam / hi) ** float(self.spectrum_slope)          # a_j |k_j| before scaling
        scale = float(self.rms_speed) / np.sqrt(np.sum(vel_amp ** 2) / 2.0) if n else 0.0
        self.amp = vel_amp * scale / kmag

    def velocity(self, x, y, t=0.0):
        x, y, t = _bcast(x, y, t)
        cx, cy = (float(v) for v in self.advection)
        xs = (x - cx * t)[..., None]
        ys = (y - cy * t)[..., None]
        th = xs * self.kx + ys * self.ky + t[..., None] * self.omega + self.phase
        c = self.amp * np.cos(th)
        return np.sum(c * self.ky, axis=-1), -np.sum(c * self.kx, axis=-1)


class Sum(Flow):
    """Sum of several flows."""

    def __init__(self, *flows: Flow):
        self.flows: tuple[Flow, ...] = tuple(flows)

    def velocity(self, x, y, t=0.0):
        x, y, t = _bcast(x, y, t)
        u = np.zeros(x.shape)
        v = np.zeros(x.shape)
        for f in self.flows:
            fu, fv = f.velocity(x, y, t)
            u += fu
            v += fv
        return u, v

    def __repr__(self) -> str:
        return f"Sum{self.flows!r}"


def _center(cfg: Mapping[str, Any], frame_size: Sequence[int] | None) -> tuple[float, float]:
    if cfg.get("center_frac") is not None:
        if frame_size is None:
            raise ValueError("center_frac needs the frame size")
        fx, fy = cfg["center_frac"]
        return float(fx) * frame_size[0], float(fy) * frame_size[1]
    return float(cfg.get("cx", 0.0)), float(cfg.get("cy", 0.0))


def _vortex_circulation(kind: str, cfg: Mapping[str, Any], rc: float) -> float:
    """Circulation from `circulation`, or from `core_speed` (tangential speed at r = rc)."""
    if cfg.get("circulation") is not None:
        return float(cfg["circulation"])
    if cfg.get("core_speed") is None:
        raise ValueError(f"{kind} flow needs circulation or core_speed")
    us = float(cfg["core_speed"])
    if kind == "rankine":
        return 2 * np.pi * rc * us
    return 2 * np.pi * rc * us / (1 - np.exp(-1.0))


def from_config(cfg: Mapping[str, Any], frame_size: Sequence[int] | None = None, seed: int = 0) -> Flow:
    """Build a flow from a mapping with a "type" key.

    Types and keys (velocities px/s, lengths px, times s):
    - uniform: u, v
    - shear: u0, dudy (1/s), y_ref or y_ref_frac (fraction of the frame height), v
    - rankine, lamb_oseen: cx, cy or center_frac [fx, fy]; circulation (px^2/s) or
      core_speed (tangential speed at the core radius); core_radius; background [u, v]
    - random_modes: n_modes, wavelength_px [lo, hi], rms_speed, period_s [lo, hi],
      spectrum_slope, advection [u, v], seed (defaults to the `seed` argument)
    - sum: flows (a list of flow mappings)
    """
    kind = str(cfg.get("type", "uniform")).lower()
    if kind == "uniform":
        return Uniform(float(cfg.get("u", 0.0)), float(cfg.get("v", 0.0)))
    if kind == "shear":
        if cfg.get("y_ref_frac") is not None:
            if frame_size is None:
                raise ValueError("y_ref_frac needs the frame size")
            y_ref = float(cfg["y_ref_frac"]) * frame_size[1]
        else:
            y_ref = float(cfg.get("y_ref", 0.0))
        return Shear(float(cfg.get("u0", 0.0)), float(cfg.get("dudy", 0.0)), y_ref, float(cfg.get("v", 0.0)))
    if kind in ("rankine", "lamb_oseen"):
        cx, cy = _center(cfg, frame_size)
        rc = float(cfg.get("core_radius", 50.0))
        gamma = _vortex_circulation(kind, cfg, rc)
        bg = tuple(float(v) for v in cfg.get("background", (0.0, 0.0)))
        cls = Rankine if kind == "rankine" else LambOseen
        return cls(cx, cy, gamma, rc, bg)
    if kind == "random_modes":
        return RandomModes(
            n_modes=int(cfg.get("n_modes", 16)),
            wavelength_px=tuple(cfg.get("wavelength_px", (150.0, 800.0))),
            rms_speed=float(cfg.get("rms_speed", 50.0)),
            period_s=tuple(cfg.get("period_s", (1.0, 4.0))),
            spectrum_slope=float(cfg.get("spectrum_slope", 1.0 / 3.0)),
            advection=tuple(cfg.get("advection", (0.0, 0.0))),
            seed=int(cfg["seed"]) if cfg.get("seed") is not None else int(seed),
        )
    if kind == "sum":
        parts = [from_config(c, frame_size, seed + 1000 * i) for i, c in enumerate(cfg.get("flows", []))]
        return Sum(*parts)
    raise ValueError(f"unknown flow type {kind!r}")


def divergence(flow: Flow, x: ArrayLike, y: ArrayLike, t: ArrayLike = 0.0, h: float = 1e-3) -> np.ndarray:
    """Central-difference divergence du/dx + dv/dy in 1/s (used by the tests)."""
    x, y, t = _bcast(x, y, t)
    up, _ = flow.velocity(x + h, y, t)
    um, _ = flow.velocity(x - h, y, t)
    _, vp = flow.velocity(x, y + h, t)
    _, vm = flow.velocity(x, y - h, t)
    return (up - um) / (2 * h) + (vp - vm) / (2 * h)


def circulation(flow: Flow, cx: float, cy: float, r: float, t: float = 0.0, n: int = 4096) -> float:
    """Line integral of the velocity around the circle (cx + r cos a, cy + r sin a), a increasing.

    This is the positive sense of the image axes (from +x toward +y), clockwise on screen.
    """
    a = (np.arange(n) + 0.5) * (2 * np.pi / n)
    x, y = cx + r * np.cos(a), cy + r * np.sin(a)
    u, v = flow.velocity(x, y, t)
    dxda, dyda = -r * np.sin(a), r * np.cos(a)
    return float(np.sum(u * dxda + v * dyda) * (2 * np.pi / n))
