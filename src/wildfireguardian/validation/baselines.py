"""Baseline fire-growth models for validation comparison.

Two baselines plus our model:

- **Persistence**: the fire never grows beyond the ignition cell. Reported
  burned area is identically equal to the ignition cell's area at every
  horizon. The naive null-hypothesis baseline; our model must beat it.
- **Isotropic**: the fire grows as a perfect circle from the ignition
  point at a rate equal to the mean (over time) head-fire rate produced
  by Rothermel under the case conditions. Wind-ignorant; serves as the
  "naive physics" baseline.

Both produce a :class:`PerimeterAtTime` series compatible with
:mod:`wildfireguardian.validation.metrics`.

The fact that real wildfires are wind-elongated, not isotropic, is what
our cellular automaton claims to capture relative to these baselines.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from .metrics import PerimeterAtTime


@dataclass(frozen=True)
class BaselineConfig:
    """Inputs shared by all baseline runs."""

    ignition_xy_5179: tuple[float, float]    # (x, y) in EPSG:5179 metres
    duration_min: float
    snapshot_every_min: float
    cell_size_m: float
    # Session 4: the model may be initialised from a finite disc; for a fair
    # comparison the baselines start from the same initial radius.
    initial_radius_m: float = 0.0


def run_persistence_baseline(cfg: BaselineConfig) -> list[PerimeterAtTime]:
    """Build the persistence-baseline perimeter series.

    The fire never grows beyond its initial state. If
    ``cfg.initial_radius_m > 0`` the frozen state is that initial disc (to
    match a disc-initialised model); otherwise it is a single cell.
    """
    x, y = cfg.ignition_xy_5179
    cs = cfg.cell_size_m
    if cfg.initial_radius_m > 0.0:
        poly: BaseGeometry = Point(x, y).buffer(cfg.initial_radius_m, quad_segs=32)
        area_m2 = math.pi * cfg.initial_radius_m ** 2
    else:
        from shapely.geometry import box
        poly = box(x - cs / 2.0, y - cs / 2.0, x + cs / 2.0, y + cs / 2.0)
        area_m2 = cs * cs
    series: list[PerimeterAtTime] = []
    t = 0.0
    while t <= cfg.duration_min + 1e-9:
        series.append(PerimeterAtTime(time_min=t, polygon=poly, area_m2=area_m2))
        t += cfg.snapshot_every_min
    return series


def run_isotropic_baseline(
    cfg: BaselineConfig, head_fire_rate_m_min: float,
) -> list[PerimeterAtTime]:
    """Build the isotropic (circular) baseline perimeter series.

    Radius grows linearly from the initial radius: r(t) = R0 + R · t.
    Wind direction is ignored. Area at time t = π · r(t)². Using the same
    initial radius R0 as the model keeps the comparison fair.
    """
    x, y = cfg.ignition_xy_5179
    r0 = cfg.initial_radius_m
    series: list[PerimeterAtTime] = []
    t = 0.0
    while t <= cfg.duration_min + 1e-9:
        radius_m = r0 + head_fire_rate_m_min * t
        if radius_m <= 0.0:
            poly: BaseGeometry | None = None
            area_m2 = 0.0
        else:
            poly = Point(x, y).buffer(radius_m, quad_segs=32)
            area_m2 = math.pi * radius_m * radius_m
        series.append(PerimeterAtTime(time_min=t, polygon=poly, area_m2=area_m2))
        t += cfg.snapshot_every_min
    return series


__all__ = [
    "BaselineConfig",
    "run_persistence_baseline",
    "run_isotropic_baseline",
]
