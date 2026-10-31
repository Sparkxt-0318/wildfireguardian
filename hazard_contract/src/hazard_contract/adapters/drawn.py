"""Scenario sets from hand-drawn hazard zones spreading isotropically."""
from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from ..geometry import polygons_dmin
from ..meta import HeatSource, ScenarioMeta
from ..scenario import ScenarioSet
from ._common import grid_from, nominal_heat, parse_time


def from_drawn_zones(polygons, spread_speed: float | Sequence[float], *, transform, height: int, width: int,
                     crs_epsg: int, issue_time_utc, horizon_s: float, burn_duration_s: float,
                     heat: HeatSource | None = None, synthetic: bool = False,
                     model_version: str = "drawn-isotropic-v1") -> ScenarioSet:
    """Zones drawn as burning at issue time, spreading outward at ``spread_speed`` (m/s).

    One member per speed. Every cell touched by a zone burns on ``[-inf, burn_duration_s)``
    (it may have ignited just before issue). Any other cell ignites at
    ``min distance from its closed square to the zones / speed`` (the earliest possible
    arrival, which is conservative) and burns for ``burn_duration_s``. Cells that would ignite
    after the horizon never burn within it.
    """
    speeds = np.atleast_1d(np.asarray(spread_speed, dtype=float))
    if np.any(~np.isfinite(speeds)) or np.any(speeds <= 0):
        raise ValueError("spread speeds must be finite and > 0")
    grid = grid_from(transform, height, width)
    d = polygons_dmin(grid, polygons)
    K = speeds.size
    ig = np.empty((K, height, width))
    ex = np.empty((K, height, width))
    for k, v in enumerate(speeds):
        arr = d / v
        arr = np.where(arr > horizon_s, np.inf, arr)
        ig[k] = np.where(d == 0.0, -np.inf, arr)
        ex[k] = np.where(d == 0.0, float(burn_duration_s), arr + burn_duration_s)
    meta = ScenarioMeta(
        crs_epsg=crs_epsg, transform=tuple(float(t) for t in transform), height=height, width=width, K=K,
        issue_time_utc=parse_time(issue_time_utc), horizon_s=float(horizon_s), source="drawn",
        synthetic=bool(synthetic), model_version=model_version, weather_source="none (drawn zones)",
        heat_source=heat or nominal_heat(burn_duration_s, "nominal heat-source parameters for drawn zones"),
        provenance={"spread_speeds_m_s": speeds.tolist()},
    )
    return ScenarioSet(ig, ex, np.ones((K, height, width), dtype=bool), meta)
