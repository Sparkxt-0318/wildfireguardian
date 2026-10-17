"""Scene backgrounds and distractors for synthetic ember clips.

All levels are linear DN (0 to 255 scale, before gamma) at camera gain 1 and the clip's
reference exposure; the camera model (degrade.py) applies gain, exposure changes, haze and
noise.

- Backgrounds (static): "night", a dark sky gradient over darker ground, and "smoky", an
  orange-tinted haze gradient that brightens toward the fire below. Both are three-band
  vertical gradients (top, horizon, bottom; B, G, R levels) times a mild static texture of
  smoothed noise. Every preset value can be overridden in the config.
- Static point lights: fixed Gaussian blobs (street lamps, windows) with an optional slow
  flicker. Kind "light".
- Flame region: a large flickering bright area. An elliptical envelope multiplies a
  texture of smoothed noise; independent noise keyframes are blended smoothly at the
  flicker rate, so the texture changes over time. Not a particle: it only marks embers
  inside it (in_large_region).
- Headlights: a pair of large bright Gaussian blobs moving along a straight path. Kind
  "headlight". Embers within a radius of a lamp are in_large_region.

Distractor point sources (lights, headlights) are `LinearSources`, so the renderer and the
ground truth treat them exactly like embers, with their own kind; they are never counted
as embers.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

import cv2
import numpy as np

from wfglink.synth.particles import LinearSources, PointSources, draw_range, glow_color, snap_to_levels

KIND_LIGHT = "light"
KIND_HEADLIGHT = "headlight"

BACKGROUND_PRESETS: dict[str, dict[str, Any]] = {
    # Linear DN, B G R order. A dark sky (slightly blue at the top, warmer at the horizon
    # from distant lights) over darker ground.
    "night": {"top_dn": [2.0, 1.7, 1.5], "horizon_dn": [2.8, 3.2, 3.8], "bottom_dn": [1.4, 1.6, 1.8],
              "horizon_frac": 0.62, "texture_amp": 0.12, "texture_px": 24},
    # Smoke lit by the fire: orange haze, brighter toward the bottom.
    "smoky": {"top_dn": [5.0, 8.0, 12.0], "horizon_dn": [10.0, 19.0, 34.0], "bottom_dn": [9.0, 16.0, 28.0],
              "horizon_frac": 0.7, "texture_amp": 0.18, "texture_px": 80},
    "flat": {"top_dn": [3.0, 3.0, 3.0], "horizon_dn": [3.0, 3.0, 3.0], "bottom_dn": [3.0, 3.0, 3.0],
             "horizon_frac": 0.5, "texture_amp": 0.0, "texture_px": 24},
}


def smooth_noise(shape: tuple[int, int], scale_px: float, rng: np.random.Generator) -> np.ndarray:
    """Zero-mean, unit-std smooth noise of the given (rows, cols) shape and feature size."""
    h, w = shape
    s = max(float(scale_px), 1.0)
    gh, gw = max(2, int(np.ceil(h / s)) + 2), max(2, int(np.ceil(w / s)) + 2)
    coarse = rng.standard_normal((gh, gw)).astype(np.float32)
    coarse = cv2.GaussianBlur(coarse, (0, 0), 0.7)
    fine = cv2.resize(coarse, (w, h), interpolation=cv2.INTER_CUBIC)
    sd = float(fine.std())
    return (fine - float(fine.mean())) / (sd if sd > 0 else 1.0)


def make_background(cfg: Mapping[str, Any] | None, frame_size: Sequence[int], rng: np.random.Generator) -> np.ndarray:
    """Static background, (H, W, 3) float32 linear DN. cfg: kind plus optional preset overrides."""
    cfg = dict(cfg or {})
    kind = str(cfg.get("kind", "night"))
    if kind not in BACKGROUND_PRESETS:
        raise ValueError(f"unknown background kind {kind!r}")
    p = {**BACKGROUND_PRESETS[kind], **{k: v for k, v in cfg.items() if k != "kind" and v is not None}}
    w, h = int(frame_size[0]), int(frame_size[1])
    top, hor, bot = (np.asarray(p[k], dtype=np.float64) for k in ("top_dn", "horizon_dn", "bottom_dn"))
    hf = float(np.clip(p["horizon_frac"], 1e-3, 1 - 1e-3))
    f = np.arange(h) / max(h - 1, 1)
    a_sky = np.clip(f / hf, 0, 1)[:, None]
    a_gnd = np.clip((f - hf) / (1 - hf), 0, 1)[:, None]
    rows = np.where(f[:, None] <= hf, top + (hor - top) * a_sky, hor + (bot - hor) * a_gnd)
    img = np.broadcast_to(rows[:, None, :], (h, w, 3)).astype(np.float32)
    amp = float(p.get("texture_amp", 0.0))
    if amp > 0:
        tex = smooth_noise((h, w), float(p.get("texture_px", 24)), rng)
        img = img * np.clip(1.0 + amp * tex, 0.2, None)[..., None]
    return np.ascontiguousarray(img, dtype=np.float32)


def _frac_or_px(cfg: Mapping[str, Any], key: str, frame_size: Sequence[int]) -> np.ndarray:
    """A point or list of points given as `<key>` (px) or `<key>_frac` (fractions of W, H)."""
    w, h = frame_size
    if cfg.get(f"{key}_frac") is not None:
        a = np.asarray(cfg[f"{key}_frac"], dtype=np.float64)
        return a * np.array([w, h], dtype=np.float64)
    return np.asarray(cfg[key], dtype=np.float64)


def make_lights(cfg: Mapping[str, Any] | None, frame_size: Sequence[int], rng: np.random.Generator,
                levels: np.ndarray, pid_start: int, t_range: tuple[float, float]) -> LinearSources | None:
    """Static point lights at random positions inside region_frac (or given `positions` px)."""
    cfg = cfg or {}
    w, h = frame_size
    if cfg.get("positions") is not None:
        pos = np.asarray(cfg["positions"], dtype=np.float64).reshape(-1, 2)
    else:
        n = int(cfg.get("count", 0))
        if n <= 0:
            return None
        fx0, fy0, fx1, fy1 = cfg.get("region_frac", [0.0, 0.55, 1.0, 1.0])
        pos = np.stack([rng.uniform(fx0 * (w - 1), fx1 * (w - 1), n), rng.uniform(fy0 * (h - 1), fy1 * (h - 1), n)], 1)
    n = pos.shape[0]
    if n == 0:
        return None
    sig = draw_range(cfg.get("sigma_px", [1.0, 2.0]), n, rng)
    lo, hi = float(levels.min()), float(levels.max())
    sig = np.where((sig >= lo * 0.999) & (sig <= hi * 1.001), snap_to_levels(sig, levels), sig)
    peak = draw_range(cfg.get("peak_dn", [40.0, 200.0]), n, rng)
    fl = cfg.get("flicker") or {}
    return LinearSources(
        pid=np.arange(pid_start, pid_start + n), kind=np.full(n, KIND_LIGHT),
        t_birth=np.full(n, t_range[0]), t_death=np.full(n, t_range[1]),
        flux=peak * 2 * np.pi * sig ** 2, sigma=sig,
        color=glow_color(draw_range(cfg.get("temperature_k", [2200.0, 4500.0]), n, rng)),
        flicker_amp=draw_range(fl.get("amp", 0.0), n, rng), flicker_hz=draw_range(fl.get("freq_hz", 0.5), n, rng),
        flicker_phase=rng.uniform(0, 2 * np.pi, n), x0=pos[:, 0], y0=pos[:, 1])


def make_headlights(cfg: Mapping[str, Any] | None, frame_size: Sequence[int], pid_start: int) -> LinearSources | None:
    """A pair of lamps whose midpoint moves from path[0] to path[1] over t_range_s."""
    cfg = cfg or {}
    if not cfg.get("enabled", False):
        return None
    path = _frac_or_px(cfg, "path", frame_size).reshape(2, 2)
    t0, t1 = (float(v) for v in cfg.get("t_range_s", [0.0, 5.0]))
    vel = (path[1] - path[0]) / max(t1 - t0, 1e-9)
    sep = float(cfg.get("separation_px", 60.0))
    sig = float(cfg.get("sigma_px", 6.0))
    peak = float(cfg.get("peak_dn", 600.0))
    off = np.array([-0.5, 0.5]) * sep
    return LinearSources(
        pid=np.arange(pid_start, pid_start + 2), kind=np.full(2, KIND_HEADLIGHT),
        t_birth=np.full(2, t0), t_death=np.full(2, t1), flux=np.full(2, peak * 2 * np.pi * sig ** 2),
        sigma=np.full(2, sig), color=np.repeat(glow_color(float(cfg.get("temperature_k", 4500.0))), 2, axis=0),
        x0=path[0, 0] + off, y0=np.full(2, path[0, 1]), vx=vel[0], vy=vel[1], t_ref=t0)


class FlameRegion:
    """A flickering, textured bright region with an elliptical envelope."""

    def __init__(self, cfg: Mapping[str, Any], frame_size: Sequence[int], t_range: tuple[float, float],
                 rng: np.random.Generator):
        w, h = int(frame_size[0]), int(frame_size[1])
        c = _frac_or_px(cfg, "center", frame_size)
        if cfg.get("size_frac") is not None:
            ax, ay = float(cfg["size_frac"][0]) * w, float(cfg["size_frac"][1]) * h
        else:
            ax, ay = (float(v) for v in cfg.get("size_px", [120.0, 80.0]))
        self.x0, self.x1 = max(int(np.floor(c[0] - ax)), 0), min(int(np.ceil(c[0] + ax)) + 1, w)
        self.y0, self.y1 = max(int(np.floor(c[1] - ay)), 0), min(int(np.ceil(c[1] + ay)) + 1, h)
        bw, bh = max(self.x1 - self.x0, 1), max(self.y1 - self.y0, 1)
        yy, xx = np.mgrid[self.y0:self.y0 + bh, self.x0:self.x0 + bw].astype(np.float64)
        r2 = ((xx - c[0]) / ax) ** 2 + ((yy - c[1]) / ay) ** 2
        self.envelope = (np.clip(1.0 - r2, 0.0, 1.0) ** float(cfg.get("envelope_power", 1.5))).astype(np.float32)
        self.mask = self.envelope >= float(cfg.get("mask_level", 0.15))
        self.brightness = float(cfg.get("brightness_dn", 220.0))
        self.color = glow_color(float(cfg.get("temperature_k", 1250.0)))[0].astype(np.float32)
        self.flicker_hz = max(float(cfg.get("flicker_hz", 6.0)), 1e-3)
        self.amp = float(cfg.get("texture_amp", 0.6))
        self.t_first = float(t_range[0])
        n_key = int(np.ceil((t_range[1] - t_range[0]) * self.flicker_hz)) + 3
        tex_px = float(cfg.get("texture_px", 10.0))
        self.keys = [smooth_noise((bh, bw), tex_px, rng) for _ in range(n_key)]

    def layer(self, t: float) -> np.ndarray:
        """(bh, bw, 3) float32 linear intensity of the flame at time t."""
        p = (t - self.t_first) * self.flicker_hz
        j = int(np.clip(np.floor(p), 0, len(self.keys) - 2))
        a = float(np.clip(p - j, 0.0, 1.0))
        a = a * a * (3 - 2 * a)
        tex = ((1 - a) * self.keys[j] + a * self.keys[j + 1]) / np.sqrt((1 - a) ** 2 + a ** 2)
        inten = self.brightness * self.envelope * np.clip(1.0 + self.amp * tex, 0.0, None)
        return inten[..., None] * self.color

    def contains(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        ix = np.rint(np.asarray(x)).astype(np.int64) - self.x0
        iy = np.rint(np.asarray(y)).astype(np.int64) - self.y0
        ok = (ix >= 0) & (iy >= 0) & (ix < self.mask.shape[1]) & (iy < self.mask.shape[0])
        out = np.zeros(np.shape(x), dtype=bool)
        out[ok] = self.mask[iy[ok], ix[ok]]
        return out


class Scene:
    """Background, flame region and distractor sources of one clip."""

    def __init__(self, cfg: Mapping[str, Any], frame_size: Sequence[int], seed: int, *,
                 levels: np.ndarray, pid_start: int, t_range: tuple[float, float],
                 background: np.ndarray | None = None):
        sc = copy.deepcopy(dict(cfg.get("scene", {}) or {}))
        self.frame_size = (int(frame_size[0]), int(frame_size[1]))
        # A precomputed (for example hazed) background may be passed in.
        self.background = (background if background is not None else
                           make_background(sc.get("background"), frame_size, np.random.default_rng([seed, 201])))
        self.lights = make_lights(sc.get("lights"), frame_size, np.random.default_rng([seed, 202]), levels,
                                  pid_start, t_range)
        nxt = pid_start + (len(self.lights) if self.lights is not None else 0)
        hl_cfg = sc.get("headlights") or {}
        self.headlights = make_headlights(hl_cfg, frame_size, nxt)
        self.headlight_radius = float(hl_cfg.get("region_radius_px", 4.0 * float(hl_cfg.get("sigma_px", 6.0))))
        fl = sc.get("flame") or {}
        self.flame = (FlameRegion(fl, frame_size, t_range, np.random.default_rng([seed, 203]))
                      if fl.get("enabled", False) else None)

    def sources(self) -> list[PointSources]:
        return [s for s in (self.lights, self.headlights) if s is not None]

    def add_flame(self, img: np.ndarray, t: float, transmission: np.ndarray | float = 1.0) -> None:
        """Add the flame layer at time t into img (in place), times the haze transmission."""
        if self.flame is None:
            return
        f = self.flame
        lay = f.layer(t)
        if isinstance(transmission, np.ndarray):
            lay = lay * transmission[f.y0:f.y1, f.x0:f.x1, None]
        else:
            lay = lay * float(transmission)
        img[f.y0:f.y1, f.x0:f.x1] += lay

    def in_large_region(self, x: np.ndarray, y: np.ndarray, t: np.ndarray) -> np.ndarray:
        """True where (x, y) at time t lies inside the flame mask or near a headlight lamp."""
        x, y, t = np.broadcast_arrays(np.asarray(x, np.float64), np.asarray(y, np.float64), np.asarray(t, np.float64))
        out = np.zeros(x.shape, dtype=bool)
        if self.flame is not None:
            out |= self.flame.contains(x, y)
        hl = self.headlights
        if hl is not None and x.size:
            for i in range(len(hl)):
                alive = (t >= hl.t_birth[i]) & (t <= hl.t_death[i])
                lx, ly = hl.position(np.full(x.shape, i), t)
                out |= alive & (np.hypot(x - lx, y - ly) <= self.headlight_radius)
        return out
