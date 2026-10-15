"""A tiny H.264 clip with bright dots at known positions, for tests of file-mode frame naming,
coordinates and directions (not a validation generator)."""
from __future__ import annotations

from pathlib import Path

import av
import numpy as np


def dots_clip(path: str | Path, *, size: tuple[int, int] = (320, 240), fps: int = 30, frames: int = 75,
              dots: list[tuple[float, float, float, float]] | None = None, repeat: set[int] = frozenset(),
              sigma: float = 1.0, amp: float = 170.0, seed: int = 0) -> list[np.ndarray]:
    """Write the clip and return, per file frame, the (n, 2) dot centres (x, y) in full-frame pixels
    (pixel centres at integers).

    dots: (x0, y0, vx, vy) in px and px per changed frame; positions wrap inside a 10 px border.
    repeat: file frames that repeat the previous frame (the dots do not move).
    """
    W, H = size
    rng = np.random.default_rng(seed)
    dots = dots or [(40, 30, 4, 3), (150, 60, 4, 3), (250, 40, 4, 3), (60, 150, 4, 3), (180, 170, 4, 3),
                    (270, 200, 4, 3)]
    base = 18 + rng.normal(0, 2.0, (H, W))
    yy, xx = np.mgrid[0:H, 0:W]
    truth: list[np.ndarray] = []
    step = 0
    img = None
    with av.open(str(path), "w") as c:
        s = c.add_stream("libx264", rate=fps)
        s.width, s.height, s.pix_fmt = W, H, "yuv420p"
        s.options = {"crf": "10", "preset": "veryfast"}
        for k in range(frames):
            if k in repeat and img is not None:
                truth.append(truth[-1].copy())
            else:
                pos = np.array([((x0 + vx * step) % (W - 20) + 10, (y0 + vy * step) % (H - 20) + 10)
                                for x0, y0, vx, vy in dots], dtype=np.float64)
                lum = base + rng.normal(0, 1.0, (H, W))
                for x, y in pos:
                    lum += amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * sigma ** 2))
                g = np.clip(lum, 0, 255).astype(np.uint8)
                img = np.stack([g // 2, (g * 3) // 4, g], axis=2)      # warm dots on a dark scene (BGR)
                truth.append(pos)
                step += 1
            for p in s.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(img), format="bgr24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    return truth


def write_clip_settings(path: str | Path, video: str | Path, **keys) -> Path:
    """A clip settings file for a test clip (the video path is absolute, so the project folder is not used)."""
    import yaml

    cc = {"clip_id": Path(video).stem, "file": str(Path(video).resolve()), "roi": None, "segments_s": None,
          "gate": None, "distance_m": None, **keys}
    Path(path).write_text(yaml.safe_dump(cc), encoding="utf-8")
    return Path(path)
