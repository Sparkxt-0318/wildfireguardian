"""Background models on the luma channel.

ApproxMedianBackground: each frame moves every background pixel one step toward the
current frame (a running approximation of the temporal median). It costs about one
millisecond, so it is the live default. Glowing embers are brief, so they barely move it;
static lights are absorbed after (brightness / step) frames.

ExactMedianBackground: the median of the last N frames (file mode option, slower).

Both return the background *before* the current frame is included, so a new ember never
subtracts itself.
"""
from __future__ import annotations

from collections import deque

import cv2
import numpy as np


class ApproxMedianBackground:
    def __init__(self, step_dn: int = 1, warmup_frames: int = 5):
        self.step = int(step_dn)
        self.warmup = max(1, int(warmup_frames))
        self._seed: list[np.ndarray] = []
        self.bg: np.ndarray | None = None

    @property
    def ready(self) -> bool:
        return self.bg is not None

    def reset(self) -> None:
        self._seed.clear()
        self.bg = None

    def apply(self, y: np.ndarray) -> np.ndarray | None:
        """Return the background for this frame (None while warming up), then update it."""
        if self.bg is None or self.bg.shape != y.shape:
            if self.bg is not None:
                self.reset()
            self._seed.append(y.copy())
            if len(self._seed) >= self.warmup:
                self.bg = np.median(np.stack(self._seed), axis=0).astype(np.uint8)
                self._seed.clear()
            return None
        current = self.bg.copy()
        up = cv2.compare(y, self.bg, cv2.CMP_GT)
        down = cv2.compare(y, self.bg, cv2.CMP_LT)
        cv2.add(self.bg, self.step, dst=self.bg, mask=up)
        cv2.subtract(self.bg, self.step, dst=self.bg, mask=down)
        return current


class ExactMedianBackground:
    def __init__(self, window: int = 11, warmup_frames: int = 5):
        self.window = int(window)
        self.warmup = max(1, int(warmup_frames))
        self._frames: deque[np.ndarray] = deque(maxlen=self.window)

    @property
    def ready(self) -> bool:
        return len(self._frames) >= self.warmup

    def reset(self) -> None:
        self._frames.clear()

    def apply(self, y: np.ndarray) -> np.ndarray | None:
        if self._frames and self._frames[0].shape != y.shape:
            self.reset()
        current = None
        if len(self._frames) >= self.warmup:
            current = np.median(np.stack(self._frames), axis=0).astype(np.uint8)
        self._frames.append(y.copy())
        return current


def make_background(cfg: dict) -> ApproxMedianBackground | ExactMedianBackground:
    b = cfg["detect"]["background"]
    if b["method"] == "approx_median":
        return ApproxMedianBackground(b["step_dn"], b["warmup_frames"])
    if b["method"] == "exact_median":
        return ExactMedianBackground(b["exact_window"], b["warmup_frames"])
    raise ValueError(f"unknown background method {b['method']!r}")
