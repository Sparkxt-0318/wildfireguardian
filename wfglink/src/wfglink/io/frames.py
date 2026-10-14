"""The Frame record passed from every source to the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(slots=True)
class Frame:
    """One video frame.

    image: BGR uint8 array (H, W, 3), owned by this record.
    t: presentation time in seconds on the source clock (true PTS for files).
    index: running index of frames delivered by the source (0, 1, 2, ...).
    t_wall: monotonic wall-clock time when the frame was received (live sources).
    meta: source-specific extras (duplicate flag, decoded booth code, camera name, ...).
    """

    image: np.ndarray
    t: float
    index: int
    t_wall: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def shape(self) -> tuple[int, int]:
        return int(self.image.shape[0]), int(self.image.shape[1])
