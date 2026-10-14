"""A lightweight synthetic live source for demos and tests.

It draws glowing embers that rise from a flickering flame band and drift in a gentle wind
with a slow vortex, with motion blur from the exposure, over a dark smoky night scene.
It runs in real time at 1280x720 so the booth UI always has something honest to show
when no camera or clip is available (the screen labels it as synthetic).

This is a demo source, not the validation generator: measured validation numbers come
from wfglink.synth, which records exact ground truth.
"""
from __future__ import annotations

import math
import time

import cv2
import numpy as np

from wfglink.io.frames import Frame
from wfglink.io.sources import Source


class SyntheticLiveSource(Source):
    kind = "synthetic"
    is_live = True

    def __init__(self, width: int = 1280, height: int = 720, fps: float = 30.0,
                 rate_hz: float = 40.0, wind_px_s: float = 160.0, duty: float = 0.6,
                 seed: int = 0, realtime: bool = True, label: str = "synthetic", **_: object):
        super().__init__(label)
        self.w, self.h, self.fps = int(width), int(height), float(fps)
        self.rate = float(rate_hz)
        self.wind = float(wind_px_s)
        self.duty = float(duty)
        self.realtime = bool(realtime)
        self.rng = np.random.default_rng(seed)
        self._t = 0.0
        self._wall0: float | None = None
        self.p = np.zeros((0, 8), np.float32)  # x, y, vx, vy, flux, age, life, phase
        self._bg = self._background()
        self._bg_ch = [np.ascontiguousarray(self._bg[:, :, c]) for c in range(3)]
        self.info = {"backend": "synthetic", "width": self.w, "height": self.h, "fps": self.fps,
                     "exposure_s": self.duty / self.fps}

    def _background(self) -> np.ndarray:
        h, w = self.h, self.w
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        sky = 10 + 22 * yy ** 2
        bg = np.repeat(sky, w, axis=1)
        smoke = cv2.GaussianBlur(self.rng.normal(0, 1, (h // 8, w // 8)).astype(np.float32), (0, 0), 3)
        smoke = cv2.resize(smoke, (w, h), interpolation=cv2.INTER_CUBIC)
        bg = bg + 6 * smoke
        out = np.stack([bg * 0.55, bg * 0.65, bg * 0.9], axis=2)  # cool smoky night (B, G, R)
        return np.clip(out, 0, 255).astype(np.float32)

    def open(self) -> None:
        self._wall0 = time.monotonic()

    def _air(self, x: np.ndarray, y: np.ndarray, t: float) -> tuple[np.ndarray, np.ndarray]:
        cx, cy, r0 = 0.62 * self.w, 0.42 * self.h, 0.22 * self.h
        dx, dy = x - cx, y - cy
        r2 = dx * dx + dy * dy + 1.0
        swirl = 220.0 * (1 - np.exp(-r2 / (r0 * r0))) * r0 / np.sqrt(r2)
        gust = 1.0 + 0.35 * math.sin(2 * math.pi * t / 7.0)
        u = self.wind * gust - swirl * dy / np.sqrt(r2)
        v = -40.0 + swirl * dx / np.sqrt(r2)
        return u.astype(np.float32), v.astype(np.float32)

    def _spawn(self, dt: float, t: float) -> None:
        n = self.rng.poisson(self.rate * dt * (1.0 + 0.6 * math.sin(2 * math.pi * t / 5.0) ** 2))
        if n == 0:
            return
        x = self.rng.uniform(0.0, 0.55 * self.w, n)
        y = self.h - self.rng.uniform(0.03, 0.12, n) * self.h
        vx = self.rng.normal(40, 30, n)
        vy = -self.rng.uniform(120, 320, n)
        flux = np.exp(self.rng.normal(np.log(700), 0.6, n))
        life = self.rng.uniform(2.0, 6.0, n)
        phase = self.rng.uniform(0, 2 * math.pi, n)
        new = np.stack([x, y, vx, vy, flux, np.zeros(n), life, phase], axis=1).astype(np.float32)
        self.p = np.concatenate([self.p, new])

    def _flames(self, t: float) -> np.ndarray:
        """Animated flame band: upward-scrolling smoothed noise shaped by a height profile."""
        h, w = self.h, self.w
        sh, sw = h // 6, w // 6
        if not hasattr(self, "_noise"):
            self._noise = self.rng.normal(0, 1, (sh * 2, sw)).astype(np.float32)
        self._noise = 0.9 * self._noise + 0.44 * self.rng.normal(0, 1, self._noise.shape).astype(np.float32)
        shift = int(t * 40) % sh
        field = cv2.GaussianBlur(np.roll(self._noise, -shift, axis=0)[:sh], (0, 0), 1.6)
        rows = np.linspace(0, 1, sh, dtype=np.float32)[:, None]
        cols = np.linspace(0, 1, sw, dtype=np.float32)[None, :]
        extent = np.clip((0.62 - cols) / 0.08, 0, 1)                   # fire on the left part only
        height = 0.80 + 0.08 * np.sin(6.0 * cols * np.pi + 2.0 * t)
        body = np.clip((rows - height) / 0.12 + 0.5 * field, 0, 1.6) * extent
        return body.astype(np.float32)  # low resolution; colored, then upsampled by the caller

    def read(self) -> Frame | None:
        dt = 1.0 / self.fps
        t = self._t
        self._spawn(dt, t)
        exp = self.duty * dt
        acc = np.zeros((self.h + 2, self.w + 2), np.float32)
        p = self.p
        if len(p):
            n_sub = 10
            x, y, vx, vy = p[:, 0].copy(), p[:, 1].copy(), p[:, 2].copy(), p[:, 3].copy()
            flick = 0.75 + 0.25 * np.sin(2 * math.pi * 6.0 * t + p[:, 7])
            fade = np.clip(1.0 - p[:, 5] / p[:, 6], 0, 1) ** 0.5
            amp = (p[:, 4] * flick * fade / n_sub).astype(np.float32)
            relax = 1.0 - math.exp(-(exp / n_sub) / 0.35)
            for k in range(n_sub):
                tk = t + (k + 0.5) * exp / n_sub
                u, v = self._air(x, y, tk)
                vx += (u - vx) * relax
                vy += (v + 60.0 - vy) * relax  # settling: embers fall slightly relative to the air
                xm, ym = x + 0.5 * vx * exp / n_sub, y + 0.5 * vy * exp / n_sub
                self._splat(acc, xm, ym, amp)
                x, y = x + vx * exp / n_sub, y + vy * exp / n_sub
            rest = dt - exp
            u, v = self._air(x, y, t + dt)
            relax = 1.0 - math.exp(-rest / 0.35)
            vx += (u - vx) * relax
            vy += (v + 60.0 - vy) * relax
            p[:, 0], p[:, 1] = x + vx * rest, y + vy * rest
            p[:, 2], p[:, 3] = vx, vy
            p[:, 5] += dt
            keep = (p[:, 5] < p[:, 6]) & (p[:, 0] > -50) & (p[:, 0] < self.w + 50) & (p[:, 1] > -50) & (p[:, 1] < self.h + 50)
            self.p = p[keep]
        glow = cv2.GaussianBlur(acc[1:-1, 1:-1], (0, 0), 1.0)
        small = cv2.resize(glow, (self.w // 4, self.h // 4), interpolation=cv2.INTER_AREA)
        halo = cv2.resize(cv2.GaussianBlur(small, (0, 0), 1.0), (self.w, self.h), interpolation=cv2.INTER_LINEAR)
        heat = self._flames(t)
        noise = np.empty((self.h, self.w), np.float32)
        cv2.randn(noise, 0.0, 1.6)
        # Fire palette at low resolution: deep red at low heat, orange, then yellow-white.
        fire_small = (np.clip(heat * 2.2, 0, 1) * 255.0,
                      np.clip(heat * 1.6 - 0.35, 0, 1) * 235.0,
                      np.clip(heat * 1.4 - 1.0, 0, 1) * 200.0)
        chans = []
        for c, (ge, ha) in enumerate(((0.22, 0.03), (0.66, 0.21), (1.0, 0.6))):
            fire = cv2.resize(fire_small[2 - c].astype(np.float32), (self.w, self.h), interpolation=cv2.INTER_CUBIC)
            ch = cv2.add(self._bg_ch[c], fire)
            ch = cv2.scaleAdd(glow, ge, ch)
            ch = cv2.scaleAdd(halo, ha, ch)
            ch = cv2.add(ch, noise)
            chans.append(cv2.convertScaleAbs(ch))
        frame = cv2.merge(chans)
        self._t += dt
        now = time.monotonic()
        if self.realtime and self._wall0 is not None:
            wait = (self._wall0 + self._t) - now
            if wait > 0:
                time.sleep(wait)
            elif wait < -0.5:
                self._wall0 = now - self._t
        return Frame(frame, t, self._next_index(), time.monotonic(),
                     {"source": self.name, "synthetic": True, "n_embers": int(len(self.p))})

    def _splat(self, acc: np.ndarray, x: np.ndarray, y: np.ndarray, amp: np.ndarray) -> None:
        """Bilinear splat of point fluxes into acc (which has a 1 px border)."""
        xi, yi = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
        ok = (xi >= -1) & (xi < self.w) & (yi >= -1) & (yi < self.h)
        xi, yi, fx, fy, a = xi[ok] + 1, yi[ok] + 1, (x[ok] - np.floor(x[ok])), (y[ok] - np.floor(y[ok])), amp[ok]
        for ddx, ddy, wgt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
            np.add.at(acc, (yi + ddy, xi + ddx), (a * wgt).astype(np.float32))
