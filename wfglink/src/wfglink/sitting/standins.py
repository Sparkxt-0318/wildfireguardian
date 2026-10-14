"""Stand-in clips with known truth, for dry runs of the sittings and for tests.

- led_turntable_clip: three glowing LEDs on a turntable seen from above, at a known
  angular speed, with exposure motion blur, a slight optional tilt (ellipse), sensor
  noise and H.264 compression.
- panel_slowmo_clip: a 60 Hz panel alternating black and white, refreshed by a scan
  sweep of known direction and duration, sampled at 240 fps with a rolling-shutter
  camera of known readout time.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np


def _encode(path: Path, frames, fps: float, crf: int = 18, pts_times=None) -> Path:
    import av
    from fractions import Fraction

    path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), "w") as c:
        s = c.add_stream("libx264", rate=Fraction(fps).limit_denominator(1000))
        first = True
        for i, img in enumerate(frames):
            if first:
                s.width, s.height, s.pix_fmt = img.shape[1], img.shape[0], "yuv420p"
                s.options = {"crf": str(crf), "preset": "veryfast"}
                first = False
            vf = av.VideoFrame.from_ndarray(img, format="bgr24")
            for pkt in s.encode(vf):
                c.mux(pkt)
        for pkt in s.encode():
            c.mux(pkt)
    return path


def led_turntable_clip(path: Path, rpm: float = 33.333, seconds: float = 6.0, fps: float = 30.0,
                       size: tuple[int, int] = (1280, 720), radii_px: tuple[float, ...] = (60, 160, 280),
                       duty: float = 0.9, tilt_ratio: float = 1.0, noise: float = 2.0, seed: int = 0,
                       amp: float = 6000.0, sigma: float = 1.6) -> dict:
    """Render the clip and return its truth (omega in rad/s, centre and radii in px)."""
    w, h = size
    rng = np.random.default_rng(seed)
    omega = rpm * 2 * math.pi / 60.0
    cx, cy = w / 2, h / 2
    phases = np.array([0.0, 2.1, 4.2])
    n_sub = 24

    def frames():
        for i in range(int(seconds * fps)):
            t0 = i / fps
            acc = np.zeros((h, w), np.float32)
            for k in range(n_sub):
                tk = t0 + (k + 0.5) / n_sub * duty / fps
                ang = phases + omega * tk
                xs = cx + np.array(radii_px) * np.cos(ang)
                ys = cy + np.array(radii_px) * np.sin(ang) * tilt_ratio
                for x, y in zip(xs, ys):
                    xi, yi = int(x), int(y)
                    fx, fy = x - xi, y - yi
                    a = amp / n_sub
                    acc[yi, xi] += a * (1 - fx) * (1 - fy)
                    acc[yi, xi + 1] += a * fx * (1 - fy)
                    acc[yi + 1, xi] += a * (1 - fx) * fy
                    acc[yi + 1, xi + 1] += a * fx * fy
            glow = cv2.GaussianBlur(acc, (0, 0), sigma)
            base = 12 + rng.normal(0, noise, (h, w)).astype(np.float32)
            b = base + 0.15 * glow
            g = base + 0.65 * glow
            r = base + 1.0 * glow
            yield np.clip(np.dstack([b, g, r]), 0, 255).astype(np.uint8)

    _encode(path, frames(), fps)
    return {"omega_rad_s": omega, "rpm": rpm, "center_px": [cx, cy], "radii_px": list(radii_px),
            "tilt_ratio": tilt_ratio, "fps": fps, "exposure_s": duty / fps,
            "t30_s": 30 * 60.0 / rpm if rpm > 0 else None}


def panel_slowmo_clip(path: Path, seconds: float = 2.0, capture_fps: float = 240.0,
                      panel_hz: float = 60.0, content_fps: float = 30.0, scan_ms: float = 15.0,
                      scan_axis: str = "vertical", readout_ms: float = 3.0, size: tuple[int, int] = (640, 360),
                      seed: int = 0) -> dict:
    """A panel of known scan direction filmed by a rolling-shutter camera at 240 fps."""
    w, h = size
    rng = np.random.default_rng(seed)
    x0, x1, y0, y1 = int(0.15 * w), int(0.85 * w), int(0.15 * h), int(0.85 * h)
    rows = np.arange(h)[:, None] * np.ones((1, w))
    cols = np.ones((h, 1)) * np.arange(w)[None, :]
    frac = ((rows - y0) / (y1 - y0)) if scan_axis == "vertical" else ((cols - x0) / (x1 - x0))
    frac = np.clip(frac, 0, 1)

    def panel_value(t):
        # Content frame k starts its panel update at the first refresh at or after k / content_fps.
        k = np.floor(t * content_fps)
        refresh = np.ceil(k / content_fps * panel_hz - 1e-9) / panel_hz
        arrive = refresh + frac * scan_ms / 1000.0
        shown = np.where(t >= arrive, k, k - 1)
        return np.where(shown % 2 == 1, 230.0, 20.0)

    def frames():
        for i in range(int(seconds * capture_fps)):
            t = i / capture_fps + (np.arange(h)[:, None] / h) * readout_ms / 1000.0 * np.ones((1, w))
            img = np.full((h, w), 8.0)
            val = panel_value(t)
            img[y0:y1, x0:x1] = val[y0:y1, x0:x1]
            img += rng.normal(0, 2, (h, w))
            yield cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)

    _encode(path, frames(), capture_fps)
    return {"scan_axis": scan_axis, "scan_ms": scan_ms, "readout_ms": readout_ms, "panel_hz": panel_hz,
            "content_fps": content_fps, "capture_fps": capture_fps}
