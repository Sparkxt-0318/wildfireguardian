"""Stand-in dashcam clips with known truth, for tests and the LED stand-in check.

- led_turntable_clip: three glowing LEDs on a turntable seen from above, at a known
  angular speed, with exposure motion blur, a slight optional tilt (ellipse), sensor
  noise and H.264 compression. Options: a burnt-in date stamp like a dashcam's, a ruler
  in the LED plane, and splitting the recording into loop files _a, _b, ...
- night_drive_clip: a dark, noisy scene with static lights and a date stamp (no embers),
  the hard negative's stand-in.

The real clips come from the user's dashcam (plan 4.4); these only check the analysis code.
"""
from __future__ import annotations

import math
import string
from pathlib import Path

import cv2
import numpy as np


def _encode(path: Path, frames, fps: float, crf: int = 18, pts_times=None, codec: str = "libx264") -> Path:
    import av
    from fractions import Fraction

    path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), "w") as c:
        s = c.add_stream(codec, rate=Fraction(fps).limit_denominator(1000))
        first = True
        for i, img in enumerate(frames):
            if first:
                s.width, s.height, s.pix_fmt = img.shape[1], img.shape[0], "yuv420p"
                if codec == "libx264":
                    s.options = {"crf": str(crf), "preset": "veryfast"}
                first = False
            vf = av.VideoFrame.from_ndarray(img, format="bgr24")
            for pkt in s.encode(vf):
                c.mux(pkt)
        for pkt in s.encode():
            c.mux(pkt)
    return path


def part_paths(path: Path, parts: int) -> list[Path]:
    """The loop-file names of one recording: led_33rpm_a.mp4, led_33rpm_b.mp4, ... (one part: path)."""
    path = Path(path)
    if parts <= 1:
        return [path]
    return [path.with_name(f"{path.stem}_{string.ascii_lowercase[k]}{path.suffix}") for k in range(parts)]


def draw_stamp(img: np.ndarray, position: str, t_s: float, start_clock_s: float = 21 * 3600.0) -> np.ndarray:
    """Burn a dashcam-like date and time into the picture at position (top-left, ..., bottom).

    The text is about 3.5 percent of the frame height and changes every second, like the
    clock overlay of a real dashcam, and a small recording dot before it blinks (on for the
    first half of every second). The detector's large-region mask hides the text line, but
    not the dot, which makes short false tracks unless the stamp is masked.
    """
    h, w = img.shape[:2]
    clock = int(start_clock_s + t_s)
    text = f"2026/10/16 {clock // 3600 % 24:02d}:{clock // 60 % 60:02d}:{clock % 60:02d}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.035 * h / 22.0
    (tw, th), base = cv2.getTextSize(text, font, scale, 1)
    if tw > 0.36 * w:
        scale *= 0.36 * w / tw
        (tw, th), base = cv2.getTextSize(text, font, scale, 1)
    dot = max(2, int(round(0.006 * h)))
    gap = 4 * dot
    mx, my = int(0.02 * w), int(0.025 * h)
    x = {"left": mx + gap, "right": w - mx - tw}.get(position.split("-")[-1], (w - tw + gap) // 2)
    y = my + th if position.startswith("top") else h - my - base
    cv2.putText(img, text, (x, y), font, scale, (235, 235, 235), 1, cv2.LINE_AA)
    if (t_s % 1.0) < 0.5:
        cv2.circle(img, (x - gap // 2, y - th // 2), dot, (60, 60, 255), -1, cv2.LINE_AA)
    return img


def _ruler(img: np.ndarray, center: tuple[float, float], px_per_mm: float, length_mm: float = 300.0) -> None:
    """A dimly lit ruler through the centre, marks every 10 mm (longer every 50 mm)."""
    h, w = img.shape[:2]
    cx, cy = center
    half = 0.5 * length_mm * px_per_mm
    x0, x1 = int(max(0, cx - half)), int(min(w - 1, cx + half))
    y0, y1 = int(cy + 0.3 * 25 * px_per_mm), int(cy + 0.3 * 25 * px_per_mm + 25 * px_per_mm)
    img[max(0, y0):min(h, y1), x0:x1] += 40.0
    for mm in range(0, int(length_mm) + 1, 10):
        x = int(round(cx - half + mm * px_per_mm))
        if 0 <= x < w:
            tick = (10 if mm % 50 else 16) * px_per_mm * 0.5
            img[max(0, y0):min(h, int(y0 + tick)), x] -= 30.0


def led_turntable_clip(path: Path, rpm: float = 33.333, seconds: float = 6.0, fps: float = 30.0,
                       size: tuple[int, int] = (1280, 720), radii_px: tuple[float, ...] = (60, 160, 280),
                       duty: float = 0.9, tilt_ratio: float = 1.0, noise: float = 2.0, seed: int = 0,
                       amp: float = 6000.0, sigma: float = 1.6, stamp: str | None = None, parts: int = 1,
                       ruler_px_per_mm: float | None = None, codec: str = "libx264") -> dict:
    """Render the clip and return its truth (omega in rad/s, centre and radii in px).

    stamp: burn a changing date stamp at this position (top-left, ..., bottom), or None.
    parts: split the recording into this many consecutive loop files named _a, _b, ...;
           the turntable keeps turning across them and each file's times start at 0.
    ruler_px_per_mm: draw a lit ruler in the LED plane at this scale (the ruler clip).
    """
    w, h = size
    rng = np.random.default_rng(seed)
    omega = rpm * 2 * math.pi / 60.0
    cx, cy = w / 2, h / 2
    phases = np.array([0.0, 2.1, 4.2])
    n_sub = 24
    n_frames = int(seconds * fps)
    paths = part_paths(Path(path), parts)
    bounds = np.linspace(0, n_frames, len(paths) + 1).round().astype(int)

    def frames(i0: int, i1: int):
        for i in range(i0, i1):
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
            if ruler_px_per_mm:
                _ruler(base, (cx, cy), ruler_px_per_mm)
            b = base + 0.15 * glow
            g = base + 0.65 * glow
            r = base + 1.0 * glow
            img = np.clip(np.dstack([b, g, r]), 0, 255).astype(np.uint8)
            if stamp:
                draw_stamp(img, stamp, t0)
            yield img

    for k, p in enumerate(paths):
        _encode(p, frames(bounds[k], bounds[k + 1]), fps, codec=codec)
    return {"omega_rad_s": omega, "rpm": rpm, "center_px": [cx, cy], "radii_px": list(radii_px),
            "tilt_ratio": tilt_ratio, "fps": fps, "exposure_s": duty / fps,
            "t30_s": 30 * 60.0 / rpm if rpm > 0 else None, "files": [str(p) for p in paths],
            "stamp": stamp, "ruler_px_per_mm": ruler_px_per_mm}


def night_drive_clip(path: Path, seconds: float = 6.0, fps: float = 30.0, size: tuple[int, int] = (640, 360),
                     stamp: str | None = "bottom", lights: int = 3, seed: int = 0) -> dict:
    """Dark noisy night-drive stand-in (no embers): static lights and a date stamp, cheap to encode."""
    w, h = size
    rng = np.random.default_rng(seed)
    bank = [np.clip(rng.normal(18, 3, (h, w, 3)), 0, 255).astype(np.uint8) for _ in range(8)]
    spots = [(int(rng.uniform(0.1, 0.9) * w), int(rng.uniform(0.15, 0.6) * h)) for _ in range(lights)]

    def frames():
        for i in range(int(seconds * fps)):
            img = bank[i % len(bank)].copy()
            for x, y in spots:
                img[y:y + 3, x:x + 3] = 255              # streetlights that never move
            if stamp:
                draw_stamp(img, stamp, i / fps)
            yield img

    _encode(Path(path), frames(), fps, crf=28)
    return {"seconds": seconds, "fps": fps, "lights_px": spots, "stamp": stamp}
