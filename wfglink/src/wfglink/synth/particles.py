"""Synthetic embers: births, drag dynamics, brightness, glow color and sampled states.

Births. Each population (embers, and optionally sparks) is born by a Cox process: the rate
is rate(t) = rate_hz exp(s G(t) - s^2 / 2), where G is a unit-variance Ornstein-Uhlenbeck
"gust" process with timescale tau_g. The mean rate is rate_hz for any s, and s = 0 gives a
homogeneous Poisson process. Birth times fall on the integration grid. The rate is either
configured directly or calibrated so that a target number of embers is inside the frame on
average (over gusts and seeds): a pilot simulation with the same spawn rules measures the
mean time an ember spends inside the frame, and rate_hz = target / mean residence time.

Spawn region. A rectangle (px), the whole frame, or "upwind": just outside the frame edges
that the mean drift comes from. For upwind spawning each particle's drift is the mean air
velocity over the frame at t = 0 plus its terminal settling speed (tracers have none), and
it enters through the left or right edge with weight |drift_x| H and through the top or
bottom edge with weight |drift_y| W, at a uniform position along that edge. For a uniform
drift this is exactly the inflow of a uniformly seeded stream, so apart from lifetime
losses the frame fills uniformly. Without a drift, upwind falls back to the whole frame.

Dynamics. The initial velocity equals the air velocity (plus an optional ejection kick,
used by sparks). Embers then follow quadratic drag toward the air plus gravity (+y, down):

    dv/dt = g_vec - (g / Vt^2) |v - u| (v - u),

in px units: g = 9.81 px_per_m px/s^2 and Vt_px = Vt_m_s px_per_m. In still air an ember
settles at Vt. A particle with Vt = null is a perfect tracer: dx/dt = u(x, t) and its
velocity is the air velocity. The integrator is classical fourth-order Runge-Kutta on a
fixed grid with step no larger than a quarter of the shortest relaxation time Vt / g
(shortened further when an ejection kick makes the drag stiffer) and no larger than the
frame interval divided by the minimum number of render samples. Particles die at the end
of an exponential lifetime or when they leave the frame by more than a kill margin.

States at arbitrary times come from cubic Hermite interpolation of the stored grid
positions and velocities, so positions and velocities are consistent (C1) and the same
interpolant is used for rendering and for the ground truth.

Appearance per particle: log-normal integrated brightness (given as a point-source SNR, see
generate.py, or directly as flux in DN px^2), Gaussian PSF sigma from a range snapped to a
few levels (so the renderer blurs each level once and the truth sigma is exact), glow color
as a BGR ratio interpolated from a temperature table (deep red at 900 K to orange-yellow
at 1300 K, yellow-white for sparks), normalised to unit BT.601 luma so that flux is luma
flux. Emission is multiplied by a fade in after birth, a fade out before the natural end
of life, a flicker 1 + a sin(2 pi f t + phi) with f of 3 to 15 Hz (dropouts between frames)
and, for a fraction of particles, a tumbling flicker of 30 Hz or more that makes dashed
streaks inside one exposure.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.signal import lfilter

from wfglink.synth.flows import Flow

KIND_EMBER = "ember"
KIND_SPARK = "spark"

# BT.601 luma weights in B, G, R order (the order of OpenCV images).
LUMA_BGR = np.array([0.114, 0.587, 0.299])

# Glow color table: temperature (K) to relative linear B, G, R. A simple hand-made
# interpolation table: deep red at 900 K, orange at 1100 to 1200 K, orange-yellow at
# 1300 K, yellow-white for sparks, warm white for lamps.
_TEMP_K = np.array([700.0, 900.0, 1000.0, 1100.0, 1200.0, 1300.0, 1500.0, 1800.0, 2200.0, 3000.0, 4500.0])
_TEMP_BGR = np.array([
    [0.000, 0.04, 1.0],
    [0.010, 0.12, 1.0],
    [0.020, 0.22, 1.0],
    [0.040, 0.33, 1.0],
    [0.080, 0.45, 1.0],
    [0.140, 0.58, 1.0],
    [0.300, 0.72, 1.0],
    [0.550, 0.85, 1.0],
    [0.750, 0.92, 1.0],
    [0.850, 0.95, 1.0],
    [0.950, 0.98, 1.0],
])


def glow_color(temp_k: float | np.ndarray) -> np.ndarray:
    """BGR color ratio for glow temperature(s), scaled to unit BT.601 luma. Shape (n, 3)."""
    t = np.atleast_1d(np.asarray(temp_k, dtype=np.float64))
    bgr = np.stack([np.interp(t, _TEMP_K, _TEMP_BGR[:, c]) for c in range(3)], axis=-1)
    return bgr / (bgr @ LUMA_BGR)[:, None]


def snap_to_levels(values: np.ndarray, levels: np.ndarray) -> np.ndarray:
    """Replace each value by the nearest level in log space."""
    values = np.asarray(values, dtype=np.float64)
    levels = np.asarray(levels, dtype=np.float64)
    if levels.size == 0:
        return values
    d = np.abs(np.log(values)[..., None] - np.log(levels))
    return levels[np.argmin(d, axis=-1)]


def sigma_levels(sigma_range: Sequence[float] | float, n_levels: int) -> np.ndarray:
    """n geometric PSF sigma levels spanning the configured range."""
    lo, hi = _range_pair(sigma_range)
    if n_levels <= 1 or hi <= lo:
        return np.array([math.sqrt(lo * hi)])
    return lo * (hi / lo) ** (np.arange(n_levels) / (n_levels - 1))


def _range_pair(spec: Any) -> tuple[float, float]:
    if isinstance(spec, Mapping):
        spec = spec.get("range")
    if np.isscalar(spec):
        return float(spec), float(spec)
    lo, hi = spec
    return float(lo), float(hi)


def draw_range(spec: Any, n: int, rng: np.random.Generator) -> np.ndarray:
    """A number (constant), [lo, hi] or {range: [lo, hi]} (uniform)."""
    lo, hi = _range_pair(spec)
    if hi <= lo:
        return np.full(n, lo)
    return rng.uniform(lo, hi, n)


def draw_vt(spec: Any, n: int, rng: np.random.Generator) -> np.ndarray:
    """Terminal velocity in m/s: null (tracer, NaN), a number, a list of equally likely
    choices, {choices: [...], weights: [...]} or {range: [lo, hi]}."""
    if spec is None:
        return np.full(n, np.nan)
    if isinstance(spec, Mapping):
        if "range" in spec:
            return draw_range(spec["range"], n, rng)
        choices = np.asarray(spec["choices"], dtype=np.float64)
        w = spec.get("weights")
        p = None if w is None else np.asarray(w, dtype=np.float64) / np.sum(w)
        return rng.choice(choices, size=n, p=p)
    if np.isscalar(spec):
        return np.full(n, float(spec))
    return rng.choice(np.asarray(spec, dtype=np.float64), size=n)


def draw_lognormal(spec: Mapping[str, Any], n: int, rng: np.random.Generator) -> np.ndarray:
    """Log-normal values with the given median and natural-log sigma."""
    med = float(spec.get("median", 1.0))
    ls = float(spec.get("log_sigma", 0.0))
    return med * np.exp(ls * rng.standard_normal(n)) if ls > 0 else np.full(n, med)


# Births ---------------------------------------------------------------------------------
def ou_process(n: int, h: float, tau_s: float, rng: np.random.Generator) -> np.ndarray:
    """Stationary unit-variance Ornstein-Uhlenbeck samples on a grid with step h (exact update)."""
    if n <= 0:
        return np.zeros(0)
    a = math.exp(-h / tau_s) if tau_s > 0 else 0.0
    g0 = rng.standard_normal()
    xi = rng.standard_normal(n)
    out = lfilter([math.sqrt(1 - a * a)], [1.0, -a], xi, zi=[a * g0])[0]
    return out


def cox_birth_steps(rate_hz: float, strength: float, tau_s: float, n_steps: int, h: float,
                    rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Birth step indices (0 to n_steps - 1, sorted, repeated for multiple births) of a Cox
    process with rate rate_hz exp(s G - s^2/2) on a grid of step h. Also returns G."""
    g = ou_process(n_steps, h, tau_s, rng)
    rate = rate_hz * np.exp(strength * g - 0.5 * strength ** 2)
    counts = rng.poisson(rate * h)
    return np.repeat(np.arange(n_steps), counts), g


# Point sources ---------------------------------------------------------------------------
class PointSources:
    """Point-like light sources with a lifetime, brightness, PSF sigma, color and flicker.

    Subclasses provide `state(idx, t) -> (x, y, vx, vy)`. `idx` indexes this object's
    arrays; `pid` holds the clip-wide particle ids.
    """

    def __init__(self, *, pid: np.ndarray, kind: np.ndarray, t_birth: np.ndarray, t_death: np.ndarray,
                 flux: np.ndarray, sigma: np.ndarray, color: np.ndarray,
                 t_fade_end: np.ndarray | None = None, fade_in_s: np.ndarray | float = 0.0,
                 fade_out_s: np.ndarray | float = 0.0,
                 flicker_amp: np.ndarray | float = 0.0, flicker_hz: np.ndarray | float = 0.0,
                 flicker_phase: np.ndarray | float = 0.0,
                 tumble_amp: np.ndarray | float = 0.0, tumble_hz: np.ndarray | float = 0.0,
                 tumble_phase: np.ndarray | float = 0.0):
        n = len(pid)
        full = lambda v: np.broadcast_to(np.asarray(v, dtype=np.float64), (n,)).copy()  # noqa: E731
        self.pid = np.asarray(pid, dtype=np.int64)
        self.kind = np.asarray(kind, dtype="<U9")
        self.t_birth = full(t_birth)
        self.t_death = full(t_death)
        self.flux = full(flux)
        self.sigma = full(sigma)
        self.color = np.asarray(color, dtype=np.float64).reshape(n, 3)
        self.t_fade_end = full(self.t_death if t_fade_end is None else t_fade_end)
        self.fade_in_s = full(fade_in_s)
        self.fade_out_s = full(fade_out_s)
        self.flicker_amp = full(flicker_amp)
        self.flicker_hz = full(flicker_hz)
        self.flicker_phase = full(flicker_phase)
        self.tumble_amp = full(tumble_amp)
        self.tumble_hz = full(tumble_hz)
        self.tumble_phase = full(tumble_phase)

    def __len__(self) -> int:
        return int(self.pid.shape[0])

    def alive_in(self, t0: float, t1: float) -> np.ndarray:
        """Indices of sources alive for a positive time inside (t0, t1)."""
        return np.nonzero((self.t_birth < t1) & (self.t_death > t0))[0]

    def state(self, idx: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        raise NotImplementedError

    def position(self, idx: np.ndarray, t: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        x, y, _, _ = self.state(idx, t)
        return x, y

    def emission(self, idx: np.ndarray, t: np.ndarray) -> np.ndarray:
        """Relative emission (multiplies flux) at times t; zero outside the lifetime."""
        idx, t = np.broadcast_arrays(np.asarray(idx), np.asarray(t, dtype=np.float64))
        tb, td = self.t_birth[idx], self.t_death[idx]
        e = ((t >= tb) & (t <= td)).astype(np.float64)
        fi = self.fade_in_s[idx]
        e *= np.where(fi > 0, np.clip((t - tb) / np.where(fi > 0, fi, 1.0), 0.0, 1.0), 1.0)
        fo = self.fade_out_s[idx]
        e *= np.where(fo > 0, np.clip((self.t_fade_end[idx] - t) / np.where(fo > 0, fo, 1.0), 0.0, 1.0), 1.0)
        a = self.flicker_amp[idx]
        e *= 1.0 + a * np.sin(2 * np.pi * self.flicker_hz[idx] * t + self.flicker_phase[idx])
        b = self.tumble_amp[idx]
        e *= 1.0 + b * np.sin(2 * np.pi * self.tumble_hz[idx] * t + self.tumble_phase[idx])
        return np.maximum(e, 0.0)


class LinearSources(PointSources):
    """Sources moving at constant velocity: x = x0 + vx (t - t_ref) (static lights use v = 0)."""

    def __init__(self, *, x0: np.ndarray, y0: np.ndarray, vx: np.ndarray | float = 0.0,
                 vy: np.ndarray | float = 0.0, t_ref: float = 0.0, **kw: Any):
        super().__init__(**kw)
        n = len(self)
        self.x0 = np.broadcast_to(np.asarray(x0, dtype=np.float64), (n,)).copy()
        self.y0 = np.broadcast_to(np.asarray(y0, dtype=np.float64), (n,)).copy()
        self.vx = np.broadcast_to(np.asarray(vx, dtype=np.float64), (n,)).copy()
        self.vy = np.broadcast_to(np.asarray(vy, dtype=np.float64), (n,)).copy()
        self.t_ref = float(t_ref)

    def state(self, idx, t):
        idx, t = np.broadcast_arrays(np.asarray(idx), np.asarray(t, dtype=np.float64))
        tc = np.clip(t, self.t_birth[idx], self.t_death[idx]) - self.t_ref
        vx, vy = self.vx[idx], self.vy[idx]
        return self.x0[idx] + vx * tc, self.y0[idx] + vy * tc, vx.copy(), vy.copy()


class EmberSystem(PointSources):
    """Simulated embers (and sparks) stored on a fine time grid, Hermite-interpolated.

    Grid: t_k = t0 + k h. Particle i has states at steps k_birth[i] to k_birth[i] +
    n_states[i] - 1, stored contiguously from row offset[i] of the flat arrays.
    """

    def __init__(self, *, t0: float, h: float, k_birth: np.ndarray, n_states: np.ndarray,
                 offset: np.ndarray, X: np.ndarray, Y: np.ndarray, VX: np.ndarray, VY: np.ndarray,
                 vt_px: np.ndarray, info: dict[str, Any] | None = None, **kw: Any):
        super().__init__(**kw)
        self.t0, self.h = float(t0), float(h)
        self.k_birth = np.asarray(k_birth, dtype=np.int64)
        self.n_states = np.asarray(n_states, dtype=np.int64)
        self.offset = np.asarray(offset, dtype=np.int64)
        self.X, self.Y, self.VX, self.VY = X, Y, VX, VY
        self.vt_px = np.asarray(vt_px, dtype=np.float64)
        self.info: dict[str, Any] = info or {}

    def state(self, idx, t):
        """Cubic Hermite position and velocity; times are clamped to each lifetime."""
        idx, t = np.broadcast_arrays(np.asarray(idx), np.asarray(t, dtype=np.float64))
        tc = np.clip(t, self.t_birth[idx], self.t_death[idx])
        s_abs = (tc - self.t0) / self.h - self.k_birth[idx]
        j = np.clip(np.floor(s_abs).astype(np.int64), 0, self.n_states[idx] - 2)
        s = s_abs - j
        r = self.offset[idx] + j
        h = self.h
        s2, s3 = s * s, s * s * s
        h00, h10, h01, h11 = 2 * s3 - 3 * s2 + 1, s3 - 2 * s2 + s, -2 * s3 + 3 * s2, s3 - s2
        d00, d10, d01, d11 = 6 * s2 - 6 * s, 3 * s2 - 4 * s + 1, -6 * s2 + 6 * s, 3 * s2 - 2 * s
        x0, x1, y0, y1 = self.X[r], self.X[r + 1], self.Y[r], self.Y[r + 1]
        u0, u1, v0, v1 = self.VX[r] * h, self.VX[r + 1] * h, self.VY[r] * h, self.VY[r + 1] * h
        x = h00 * x0 + h10 * u0 + h01 * x1 + h11 * u1
        y = h00 * y0 + h10 * v0 + h01 * y1 + h11 * v1
        vx = (d00 * x0 + d10 * u0 + d01 * x1 + d11 * u1) / h
        vy = (d00 * y0 + d10 * v0 + d01 * y1 + d11 * v1) / h
        return x, y, vx, vy

    def grid_states(self, i: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Stored grid times and states of particle i (for tests and diagnostics)."""
        r = slice(self.offset[i], self.offset[i] + self.n_states[i])
        t = self.t0 + self.h * (self.k_birth[i] + np.arange(self.n_states[i]))
        return t, self.X[r], self.Y[r], self.VX[r], self.VY[r]


# Dynamics -------------------------------------------------------------------------------
def integrate(flow: Flow, *, x0: np.ndarray, y0: np.ndarray, vx0: np.ndarray, vy0: np.ndarray,
              vt_px: np.ndarray, k_birth: np.ndarray, k_death: np.ndarray, t0: float, h: float,
              n_steps: int, g_px: float, bounds: tuple[float, float, float, float] | None = None
              ) -> dict[str, np.ndarray]:
    """Integrate particles on the grid t_k = t0 + k h with classical RK4.

    Each particle is born at step k_birth with position (x0, y0) and velocity (vx0, vy0)
    (tracers, vt_px NaN, always take the air velocity) and lives to step k_death, or until
    its position leaves `bounds` (xmin, ymin, xmax, ymax), after which its last state is
    the first one outside. Returns flat state arrays sorted by particle then time, with
    per-particle offset, n_states and the final death step.
    """
    n = len(k_birth)
    k_birth = np.asarray(k_birth, dtype=np.int64)
    k_death = np.minimum(np.asarray(k_death, dtype=np.int64).copy(), n_steps)
    k_death = np.maximum(k_death, k_birth + 1)
    tracer = np.isnan(vt_px)
    inv_vt2 = np.where(tracer, 0.0, 1.0 / np.where(tracer, 1.0, vt_px) ** 2)
    x = np.zeros(n)
    y = np.zeros(n)
    vx = np.zeros(n)
    vy = np.zeros(n)
    order = np.argsort(k_birth, kind="stable")
    kb_sorted = k_birth[order]
    rec_i: list[np.ndarray] = []
    rec: list[list[np.ndarray]] = [[], [], [], []]
    active = np.zeros(0, dtype=np.int64)
    if n == 0:
        k_first, k_last = 0, -1
    else:
        k_first, k_last = int(kb_sorted[0]), int(k_death.max())

    def deriv(px, py, pvx, pvy, t, tr, inv):
        ua, va = flow.velocity(px, py, t)
        wx, wy = pvx - ua, pvy - va
        kd = g_px * inv * np.hypot(wx, wy)
        ax = np.where(tr, 0.0, -kd * wx)
        ay = np.where(tr, 0.0, g_px - kd * wy)
        return np.where(tr, ua, pvx), np.where(tr, va, pvy), ax, ay

    ptr = 0
    for k in range(k_first, k_last + 1):
        t = t0 + k * h
        end = ptr
        while end < n and kb_sorted[end] == k:
            end += 1
        if end > ptr:
            new = order[ptr:end]
            ptr = end
            ua, va = flow.velocity(x0[new], y0[new], t)
            x[new], y[new] = x0[new], y0[new]
            vx[new] = np.where(tracer[new], ua, vx0[new])
            vy[new] = np.where(tracer[new], va, vy0[new])
            active = np.concatenate([active, new])
        if active.size == 0:
            continue
        rec_i.append(active)
        rec[0].append(x[active])
        rec[1].append(y[active])
        rec[2].append(vx[active])
        rec[3].append(vy[active])
        active = active[k_death[active] > k]
        if active.size == 0 or k >= n_steps:
            continue
        a = active
        px, py, pvx, pvy = x[a], y[a], vx[a], vy[a]
        tr, inv = tracer[a], inv_vt2[a]
        hh = 0.5 * h
        k1 = deriv(px, py, pvx, pvy, t, tr, inv)
        k2 = deriv(px + hh * k1[0], py + hh * k1[1], pvx + hh * k1[2], pvy + hh * k1[3], t + hh, tr, inv)
        k3 = deriv(px + hh * k2[0], py + hh * k2[1], pvx + hh * k2[2], pvy + hh * k2[3], t + hh, tr, inv)
        k4 = deriv(px + h * k3[0], py + h * k3[1], pvx + h * k3[2], pvy + h * k3[3], t + h, tr, inv)
        w6 = h / 6.0
        nx = px + w6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        ny = py + w6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        nvx = pvx + w6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2])
        nvy = pvy + w6 * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3])
        if tr.any():
            ua, va = flow.velocity(nx, ny, t + h)
            nvx = np.where(tr, ua, nvx)
            nvy = np.where(tr, va, nvy)
        x[a], y[a], vx[a], vy[a] = nx, ny, nvx, nvy
        if bounds is not None:
            out = (nx < bounds[0]) | (ny < bounds[1]) | (nx > bounds[2]) | (ny > bounds[3])
            k_death[a[out]] = np.minimum(k_death[a[out]], k + 1)

    if rec_i:
        ids = np.concatenate(rec_i)
        srt = np.argsort(ids, kind="stable")
        ids = ids[srt]
        arrs = [np.concatenate(r)[srt] for r in rec]
    else:
        ids = np.zeros(0, dtype=np.int64)
        arrs = [np.zeros(0) for _ in range(4)]
    n_states = np.bincount(ids, minlength=n).astype(np.int64)
    offset = np.concatenate([[0], np.cumsum(n_states)[:-1]]).astype(np.int64) if n else np.zeros(0, np.int64)
    return {"X": arrs[0], "Y": arrs[1], "VX": arrs[2], "VY": arrs[3], "offset": offset,
            "n_states": n_states, "k_death": k_birth + n_states - 1}


# Population sampling -------------------------------------------------------------------
def _mean_drift(flow: Flow, frame_size: Sequence[int]) -> tuple[float, float]:
    w, h = frame_size
    gx, gy = np.meshgrid(np.linspace(0, w - 1, 9), np.linspace(0, h - 1, 5))
    u, v = flow.velocity(gx, gy, 0.0)
    return float(np.mean(u)), float(np.mean(v))


def spawn_positions(spawn: Mapping[str, Any], n: int, rng: np.random.Generator,
                    frame_size: Sequence[int], drift: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Spawn positions for n particles. drift (n, 2) px/s is needed for mode "upwind"."""
    w, h = frame_size
    mode = str(spawn.get("mode", "upwind")).lower()
    margin = float(spawn.get("margin_px", 8.0))
    if mode == "rect":
        if spawn.get("rect_frac") is not None:
            fx0, fy0, fx1, fy1 = spawn["rect_frac"]
            rect = (fx0 * w, fy0 * h, fx1 * w, fy1 * h)
        else:
            rect = spawn["rect"]
        x0, y0, x1, y1 = (float(v) for v in rect)
        return rng.uniform(x0, x1, n), rng.uniform(y0, y1, n)
    if mode == "frame":
        return rng.uniform(0, w - 1, n), rng.uniform(0, h - 1, n)
    if mode != "upwind":
        raise ValueError(f"unknown spawn mode {mode!r}")
    if drift is None:
        raise ValueError("upwind spawning needs the drift")
    dx, dy = drift[:, 0], drift[:, 1]
    wx, wy = np.abs(dx) * h, np.abs(dy) * w
    still = (wx + wy) < 1e-9
    px = rng.uniform(0, w - 1, n)
    py = rng.uniform(0, h - 1, n)
    on_x_edge = rng.uniform(0, 1, n) * np.where(still, 1.0, wx + wy) < wx
    x = np.where(on_x_edge, np.where(dx > 0, -margin, w - 1 + margin), px)
    y = np.where(on_x_edge, py, np.where(dy > 0, -margin, h - 1 + margin))
    # No drift: fall back to uniform positions over the frame.
    return np.where(still, px, x), np.where(still, py, y)


def _sample_population(pcfg: Mapping[str, Any], kind: str, n: int, rng: np.random.Generator, *,
                       flow: Flow, frame_size: Sequence[int], px_per_m: float,
                       flux_per_snr: float, levels: np.ndarray) -> dict[str, np.ndarray]:
    """Draw every per-particle attribute except the birth time."""
    vt_px = draw_vt(pcfg.get("vt_m_s"), n, rng) * px_per_m
    life = rng.exponential(float(pcfg.get("lifetime_s", 5.0)), n)
    sig = snap_to_levels(draw_range(pcfg.get("sigma_px", [0.6, 2.0]), n, rng), levels)
    if pcfg.get("flux") is not None:
        flux = draw_lognormal(pcfg["flux"], n, rng)
    else:
        flux = draw_lognormal(pcfg.get("snr", {"median": 10.0}), n, rng) * flux_per_snr * sig
    color = glow_color(draw_range(pcfg.get("temperature_k", [900.0, 1300.0]), n, rng))
    fl = pcfg.get("flicker") or {}
    tb = pcfg.get("tumble") or {}
    tumbling = rng.uniform(0, 1, n) < float(tb.get("prob", 0.0))
    ej_speed = draw_range(pcfg.get("eject_speed_px_s", 0.0), n, rng)
    ang = np.radians(draw_range(pcfg.get("eject_angle_deg", [0.0, 360.0]), n, rng))
    mu, mv = _mean_drift(flow, frame_size)
    settle = np.where(np.isnan(vt_px), 0.0, vt_px)
    drift = np.stack([np.full(n, mu), mv + settle], axis=1)
    x0, y0 = spawn_positions(pcfg.get("spawn", {"mode": "upwind"}), n, rng, frame_size, drift)
    return {
        "kind": np.full(n, kind, dtype="<U9"),
        "vt_px": vt_px, "life": life, "sigma": sig, "flux": flux, "color": color,
        "flicker_amp": draw_range(fl.get("amp", 0.0), n, rng),
        "flicker_hz": draw_range(fl.get("freq_hz", 0.0), n, rng),
        "flicker_phase": rng.uniform(0, 2 * np.pi, n),
        "tumble_amp": np.where(tumbling, draw_range(tb.get("amp", 1.0), n, rng), 0.0),
        "tumble_hz": np.where(tumbling, draw_range(tb.get("freq_hz", [30.0, 60.0]), n, rng), 0.0),
        "tumble_phase": rng.uniform(0, 2 * np.pi, n),
        "fade_in_s": np.full(n, float(pcfg.get("fade_in_s", 0.0))),
        "fade_out_s": np.full(n, float(pcfg.get("fade_out_s", 0.0))),
        "ejx": ej_speed * np.cos(ang), "ejy": ej_speed * np.sin(ang),
        "x0": x0, "y0": y0,
    }


def _concat(parts: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def _vt_values(spec: Any) -> list[float]:
    """Representative terminal velocities (m/s) of a vt_m_s spec; 0 for tracers."""
    if spec is None:
        return [0.0]
    if isinstance(spec, Mapping):
        spec = spec.get("range", spec.get("choices"))
    return [float(v) for v in np.atleast_1d(np.asarray(spec, dtype=np.float64))]


def _step_limit(pops: list[Mapping[str, Any]], px_per_m: float, g_m_s2: float) -> float:
    """Largest stable step from the relaxation times: h <= tau / (4 max(1, w_max / Vt)),
    with tau = Vt / g for the smallest Vt and w_max the largest ejection kick."""
    limit = math.inf
    for p in pops:
        if p.get("vt_m_s") is None:
            continue
        vmin = min(_vt_values(p.get("vt_m_s")))
        tau = vmin / g_m_s2
        ej = _range_pair(p.get("eject_speed_px_s", 0.0))[1] / (vmin * px_per_m)
        limit = min(limit, tau / (4.0 * max(1.0, ej)))
    return limit


def population_configs(cfg: Mapping[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(kind, config) for embers and, if enabled, sparks (spark keys override ember keys)."""
    from wfglink.config import deep_merge

    emb = dict(cfg.get("embers", {}))
    pops: list[tuple[str, dict[str, Any]]] = [(KIND_EMBER, emb)]
    sp = cfg.get("sparks") or {}
    if sp.get("enabled", False):
        pops.append((KIND_SPARK, deep_merge(emb, {k: v for k, v in sp.items() if k != "enabled"})))
    return pops


def _warmup(cfg: Mapping[str, Any], pops: list[tuple[str, dict[str, Any]]], flow: Flow,
            frame_size: Sequence[int], px_per_m: float) -> float:
    """Pre-roll before t = 0 so the frame is in steady state when the clip starts.

    "auto": for upwind spawning, warmup_factor times the longest time any terminal-velocity
    class needs to cross the frame along its drift (at most three mean lifetimes);
    otherwise three mean lifetimes. Capped by warmup_max_s.
    """
    pc = cfg.get("particles", {})
    spec = pc.get("warmup_s", "auto")
    if spec != "auto" and spec is not None:
        return float(spec)
    w, h = frame_size
    mu, mv = _mean_drift(flow, frame_size)
    best = 0.0
    for _, p in pops:
        need = 3.0 * float(p.get("lifetime_s", 5.0))
        if str((p.get("spawn") or {}).get("mode", "upwind")) == "upwind":
            cross = 0.0
            for vt in _vt_values(p.get("vt_m_s")):
                dy = mv + vt * px_per_m
                tx = w / abs(mu) if abs(mu) > 1e-9 else math.inf
                ty = h / abs(dy) if abs(dy) > 1e-9 else math.inf
                cross = max(cross, min(tx, ty))
            need = min(need, float(pc.get("warmup_factor", 1.05)) * cross)
        best = max(best, need)
    return float(min(best, float(pc.get("warmup_max_s", 15.0))))


def simulate(cfg: Mapping[str, Any], flow: Flow, *, frame_size: Sequence[int], fps: float,
             duration_s: float, seed: int, flux_per_snr: float = 1.0, t_end_pad_s: float = 0.0,
             pid_start: int = 0) -> EmberSystem:
    """Simulate every particle population of a clip.

    Config keys used: px_per_m, embers.*, sparks.*, particles.*, render.n_sub_min.
    Births run from -warmup to duration_s + t_end_pad_s. flux_per_snr converts the
    configured point-source SNR into flux (DN px^2 per unit SNR per px of PSF sigma).
    """
    pc = cfg.get("particles", {})
    px_per_m = float(cfg.get("px_per_m", 40.0))
    g_m_s2 = float(pc.get("g_m_s2", 9.81))
    g_px = g_m_s2 * px_per_m
    pops = population_configs(cfg)
    n_sub_min = int(cfg.get("render", {}).get("n_sub_min", 8))
    h = min(1.0 / (fps * n_sub_min), _step_limit([p for _, p in pops], px_per_m, g_m_s2))
    if pc.get("max_step_s") is not None:
        h = min(h, float(pc["max_step_s"]))
    warm = _warmup(cfg, pops, flow, frame_size, px_per_m)
    t0 = -warm
    n_steps = int(math.ceil((duration_s + t_end_pad_s - t0) / h)) + 1
    w, hgt = frame_size
    km = float(pc.get("kill_margin_px", 40.0))
    bounds = (-km, -km, w - 1 + km, hgt - 1 + km)
    levels_all = sigma_levels(cfg.get("embers", {}).get("sigma_px", [0.6, 2.0]),
                              int(pc.get("sigma_levels", 4)))

    parts: list[dict[str, np.ndarray]] = []
    info: dict[str, Any] = {"step_s": h, "warmup_s": warm, "t0": t0, "populations": {}}
    for i, (kind, p) in enumerate(pops):
        prng = np.random.default_rng([int(seed), 101, i])
        lv = levels_all
        lo, hi = _range_pair(p.get("sigma_px", [0.6, 2.0]))
        if lo < levels_all[0] * 0.999 or hi > levels_all[-1] * 1.001:
            lv = sigma_levels([lo, hi], int(pc.get("sigma_levels", 4)))
        dens = p.get("density") or {}
        rate = dens.get("rate_hz")
        if rate is None:
            target = float(dens.get("on_screen", 100.0))
            res = _mean_residence(p, kind, flow, frame_size=frame_size, fps=fps, duration_s=duration_s,
                                  h=h, g_px=g_px, px_per_m=px_per_m, bounds=bounds,
                                  n_pilot=int(dens.get("pilot_particles", 1500)),
                                  rng=np.random.default_rng([int(seed), 102, i]), levels=lv,
                                  horizon_cap_s=float(dens.get("pilot_horizon_s", 60.0)))
            rate = target / res if res > 0 else 0.0
            info["populations"][kind] = {"target_on_screen": target, "pilot_residence_s": res}
        rate = float(rate)
        gust = p.get("gust") or {}
        kb, _ = cox_birth_steps(rate, float(gust.get("strength", 0.0)), float(gust.get("tau_s", 1.0)),
                                n_steps - 1, h, prng)
        attrs = _sample_population(p, kind, kb.size, prng, flow=flow, frame_size=frame_size,
                                   px_per_m=px_per_m, flux_per_snr=flux_per_snr, levels=lv)
        attrs["k_birth"] = kb
        info["populations"].setdefault(kind, {}).update({"rate_hz": rate, "n_born": int(kb.size)})
        parts.append(attrs)

    a = _concat(parts)
    order = np.lexsort((np.arange(a["k_birth"].size), a["k_birth"]))
    a = {k: v[order] for k, v in a.items()}
    kb = a["k_birth"].astype(np.int64)
    k_nat = kb + np.maximum(np.ceil(a["life"] / h).astype(np.int64), 1)
    # Initial velocity: the air velocity at birth plus the ejection kick (zero for embers).
    ua, va = flow.velocity(a["x0"], a["y0"], t0 + kb * h)
    st = integrate(flow, x0=a["x0"], y0=a["y0"], vx0=ua + a["ejx"], vy0=va + a["ejy"], vt_px=a["vt_px"],
                   k_birth=kb, k_death=k_nat, t0=t0, h=h, n_steps=n_steps, g_px=g_px, bounds=bounds)
    n = kb.size
    t_birth = t0 + kb * h
    t_death = t0 + st["k_death"] * h
    info["n_particles"] = int(n)
    return EmberSystem(
        t0=t0, h=h, k_birth=kb, n_states=st["n_states"], offset=st["offset"],
        X=st["X"], Y=st["Y"], VX=st["VX"], VY=st["VY"], vt_px=a["vt_px"], info=info,
        pid=np.arange(pid_start, pid_start + n, dtype=np.int64), kind=a["kind"],
        t_birth=t_birth, t_death=t_death, t_fade_end=t_birth + a["life"],
        flux=a["flux"], sigma=a["sigma"], color=a["color"],
        fade_in_s=a["fade_in_s"], fade_out_s=a["fade_out_s"],
        flicker_amp=a["flicker_amp"], flicker_hz=a["flicker_hz"], flicker_phase=a["flicker_phase"],
        tumble_amp=a["tumble_amp"], tumble_hz=a["tumble_hz"], tumble_phase=a["tumble_phase"],
    )


def _mean_residence(p: Mapping[str, Any], kind: str, flow: Flow, *, frame_size: Sequence[int], fps: float,
                    duration_s: float, h: float, g_px: float, px_per_m: float,
                    bounds: tuple[float, float, float, float], n_pilot: int, rng: np.random.Generator,
                    levels: np.ndarray, horizon_cap_s: float = 60.0) -> float:
    """Pilot simulation: mean time a newborn particle spends inside the frame (s).

    Particles are born at uniform times over the clip with the population's spawn rules
    and followed until they die or leave (at most horizon_cap_s after the clip).
    """
    hp = h
    n_clip = max(1, int(math.ceil(duration_s / hp)))
    kb = np.sort(rng.integers(0, n_clip, n_pilot))
    attrs = _sample_population(p, kind, n_pilot, rng, flow=flow, frame_size=frame_size, px_per_m=px_per_m,
                               flux_per_snr=1.0, levels=levels)
    horizon = min(float(np.max(attrs["life"])), horizon_cap_s) if n_pilot else 0.0
    n_steps = n_clip + int(math.ceil(horizon / hp)) + 1
    k_nat = kb + np.maximum(np.ceil(attrs["life"] / hp).astype(np.int64), 1)
    ua, va = flow.velocity(attrs["x0"], attrs["y0"], kb * hp)
    st = integrate(flow, x0=attrs["x0"], y0=attrs["y0"], vx0=ua + attrs["ejx"], vy0=va + attrs["ejy"],
                   vt_px=attrs["vt_px"], k_birth=kb, k_death=k_nat, t0=0.0, h=hp, n_steps=n_steps,
                   g_px=g_px, bounds=bounds)
    w, hgt = frame_size
    inside = (st["X"] >= 0) & (st["X"] <= w - 1) & (st["Y"] >= 0) & (st["Y"] <= hgt - 1)
    # Each stored state stands for one step of duration hp (the last state of a life ends it).
    owner = np.repeat(np.arange(n_pilot), st["n_states"])
    last = np.zeros(st["X"].size, dtype=bool)
    last[st["offset"] + st["n_states"] - 1] = True
    total = np.bincount(owner, (inside & ~last).astype(np.float64), minlength=n_pilot) * hp
    return float(np.mean(total))
