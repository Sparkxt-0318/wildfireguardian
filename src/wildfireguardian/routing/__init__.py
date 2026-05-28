"""Elderly-aware evacuation routing.

Session 5 spine: route people away from where the fire WILL be, not just
to the nearest shelter. See :mod:`.future_front`.
"""

from __future__ import annotations

from .future_front import (
    ELDERLY_WALK_SPEED_MS,
    EvacuationResult,
    RoadNetwork,
    front_arrival_times,
    naive_shortest_path,
    time_dependent_evacuation,
)

__all__ = [
    "ELDERLY_WALK_SPEED_MS",
    "RoadNetwork",
    "EvacuationResult",
    "front_arrival_times",
    "time_dependent_evacuation",
    "naive_shortest_path",
]
