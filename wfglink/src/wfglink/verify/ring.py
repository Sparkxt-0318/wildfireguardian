"""The last few analysed frames (luma, background, noise map) for persistence features.

The ring holds references to the detector's per-frame arrays, which are never modified in
place: the background model returns a fresh copy every frame (detect/background.py), and the
noise map is replaced, not updated, when it is refreshed (detect/candidates.py, _update_maps).
The luma is copied only when it may share memory with the input picture (grey input).

Causality: a frame enters only after its own features are computed, and only frames of
increasing time enter, so the ring never holds a frame later than the one being analysed.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class RingFrame:
    index: int
    t: float
    luma: np.ndarray           # uint8, as in DetectorState.luma (native analysis pixels)
    background: np.ndarray     # uint8 background used for this frame
    sigma: np.ndarray          # float32 noise map in force for this frame


class FrameRing:
    """Deque of the last k analysed frames, oldest first."""

    def __init__(self, k: int):
        self.k = max(1, int(k))
        self._d: deque[RingFrame] = deque(maxlen=self.k)

    def __len__(self) -> int:
        return len(self._d)

    def clear(self) -> None:
        self._d.clear()

    def push(self, rf: RingFrame) -> None:
        if self._d and not rf.t > self._d[-1].t:
            raise ValueError(f"ring frames must increase in time: {rf.t} after {self._d[-1].t}")
        self._d.append(rf)

    def back(self, n: int) -> RingFrame | None:
        """The frame n analysed frames back from the newest one held (n = 1: the newest)."""
        if n < 1 or n > len(self._d):
            return None
        return self._d[-n]

    def frames(self) -> tuple[RingFrame, ...]:
        return tuple(self._d)

    @property
    def latest_t(self) -> float | None:
        return self._d[-1].t if self._d else None
