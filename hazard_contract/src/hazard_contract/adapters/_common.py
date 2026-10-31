from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from ..geometry import Grid
from ..meta import HeatSource

# Nominal heat-source defaults for adapters that are not given parameters. They are
# placeholders for SYNTHETIC/drawn inputs, not calibrated physics; real producers must pass
# their own HeatSource.
NOMINAL_HEAT = dict(fuel_load_kg_m2=1.0, heat_content_kj_kg=18000.0, radiative_fraction=0.3)


def nominal_heat(burn_duration_s: float, note: str) -> HeatSource:
    return HeatSource(burn_duration_s=float(burn_duration_s), note=note, **NOMINAL_HEAT)


def parse_time(t) -> datetime:
    if isinstance(t, datetime):
        dt = t
    else:
        dt = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("times must be timezone-aware (UTC)")
    return dt.astimezone(timezone.utc)


def seconds_after(t, issue: datetime) -> float:
    if isinstance(t, (int, float, np.floating, np.integer)):
        return float(t)
    return (parse_time(t) - issue).total_seconds()


def grid_from(transform, height: int, width: int) -> Grid:
    return Grid(tuple(float(v) for v in transform), int(height), int(width))
