"""Disk neighbourhood kernels for grid-space proximity features."""

from __future__ import annotations

from functools import lru_cache

import numpy as np


@lru_cache(maxsize=32)
def disk_kernel(radius_cells: float) -> np.ndarray:
    """A binary disk kernel of the given radius (in cell units).

    Cells whose centre lies within ``radius_cells`` of the kernel centre are 1.
    Returns at least a 1×1 kernel. The kernel is intended for
    :func:`scipy.ndimage.correlate`-style neighbourhood counts/sums.
    """
    r = max(0.0, float(radius_cells))
    h = int(np.floor(r))
    if h == 0:
        return np.ones((1, 1), dtype=np.float64)
    yy, xx = np.mgrid[-h:h + 1, -h:h + 1]
    return ((yy * yy + xx * xx) <= r * r).astype(np.float64)


__all__ = ["disk_kernel"]
