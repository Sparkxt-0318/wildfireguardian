"""Per-transition candidate generation and spread geometry.

For each pair of consecutive overpasses (k → k+1) we form the supervised
learning problem:

- **Active fire** at k = the monotone cumulative burned mask (every cell
  detected at or before overpass k). Once a cell burns it is a spread source
  to its neighbours over the next interval.
- **Candidate** = an *unburned* cell within 2 km of the active fire that passes
  the burnable gate and lies inside the fuel raster. (The gate is the
  orientation-safe one from :mod:`layers`.)
- **Label** = 1 iff that candidate is in the cumulative burned mask at k+1
  (it ignited by the next overpass), else 0.

The geometry here is purely raster-mask arithmetic on the 375 m grid, so
"active fire" and "candidate" live in the same orientation by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import ndimage

from .candidates_kernels import disk_kernel
from .detections import ObservedSequence
from .grid import Grid
from .layers import StaticLayers

CANDIDATE_RADIUS_M: float = 2000.0


def distance_to_burned_m(burned: np.ndarray, cell_size_m: float) -> np.ndarray:
    """Euclidean distance (m) from every cell to the nearest burned cell."""
    if not burned.any():
        return np.full(burned.shape, np.inf)
    return ndimage.distance_transform_edt(~burned) * cell_size_m


def count_within(burned: np.ndarray, cell_size_m: float, radius_m: float) -> np.ndarray:
    """Count of burned cells within ``radius_m`` of each cell (disk neighbourhood)."""
    k = disk_kernel(radius_m / cell_size_m)
    return ndimage.correlate(burned.astype(np.float64), k, mode="constant")


def sum_within(field: np.ndarray, cell_size_m: float, radius_m: float) -> np.ndarray:
    """Sum of ``field`` over burned/active cells within ``radius_m`` (disk)."""
    k = disk_kernel(radius_m / cell_size_m)
    return ndimage.correlate(np.nan_to_num(field, nan=0.0), k, mode="constant")


def max_within(field: np.ndarray, cell_size_m: float, radius_m: float) -> np.ndarray:
    """Max of ``field`` within ``radius_m`` (disk footprint)."""
    k = disk_kernel(radius_m / cell_size_m) > 0
    return ndimage.maximum_filter(np.nan_to_num(field, nan=0.0), footprint=k, mode="constant")


@dataclass
class Transition:
    """One k → k+1 spread transition's candidate set and geometry."""

    fire_id: str
    k: int
    time_now: pd.Timestamp
    dt_hours: float
    burned_now: np.ndarray          # cumulative burned mask at k
    newly_next: np.ndarray          # cells newly burned at k+1
    rows: np.ndarray                # candidate cell rows
    cols: np.ndarray                # candidate cell cols
    labels: np.ndarray              # 1 if candidate ignites by k+1
    dist_to_burning: np.ndarray     # m, candidate → nearest burned cell
    # diagnostics on positives lost to the gate / radius:
    n_newly_total: int
    n_newly_captured: int


def iter_transitions(
    seq: ObservedSequence,
    static: StaticLayers,
    radius_m: float = CANDIDATE_RADIUS_M,
) -> list[Transition]:
    """Build all candidate sets for a fire's observed overpass sequence."""
    grid: Grid = seq.grid
    cs = grid.cell_size_m
    gate = static.burnable_gate & static.in_fuel_bounds
    out: list[Transition] = []

    for k in range(seq.n_overpasses - 1):
        burned_now = seq.cumulative[k]
        burned_next = seq.cumulative[k + 1]
        newly = burned_next & (~burned_now)
        if not burned_now.any():
            continue

        dist = distance_to_burned_m(burned_now, cs)
        cand_mask = (~burned_now) & (dist <= radius_m) & gate
        rows, cols = np.where(cand_mask)
        if rows.size == 0:
            continue
        labels = newly[rows, cols].astype(np.int64)

        dt_hours = (
            seq.overpasses[k + 1].time - seq.overpasses[k].time
        ).total_seconds() / 3600.0

        out.append(
            Transition(
                fire_id=seq.fire_id,
                k=k,
                time_now=seq.overpasses[k].time,
                dt_hours=float(dt_hours),
                burned_now=burned_now,
                newly_next=newly,
                rows=rows,
                cols=cols,
                labels=labels,
                dist_to_burning=dist[rows, cols],
                n_newly_total=int(newly.sum()),
                n_newly_captured=int(labels.sum()),
            )
        )
    return out


__all__ = [
    "CANDIDATE_RADIUS_M",
    "distance_to_burned_m",
    "count_within",
    "sum_within",
    "max_within",
    "Transition",
    "iter_transitions",
]
