"""Elderly-aware evacuation routing.

Two generations live here:

- :mod:`.future_front` (Session 5) — the original spine, which treats the
  predicted fire as a deterministic *moving polygon front* and keeps the
  evacuee out of its footprint via a time-dependent Dijkstra.

- :mod:`.hazard` + :mod:`.evacuation` (this session) — the routing layer that
  consumes the **spread_v2 probabilistic hazard as-is**: a time-varying
  per-cell ignition-PROBABILITY surface (a broad, severity-scaled reach
  envelope), not a binarised front. :class:`~.hazard.HazardSequence` samples
  P(ignition | location, time); :func:`~.evacuation.naive_route` and
  :func:`~.evacuation.future_aware_route` are the headline contrast (run to
  the nearest shelter, fire-blind, vs minimise cumulative exposure to the
  predicted future hazard).
"""

from __future__ import annotations

from .evacuation import (
    ELDERLY_FLAT_SPEED_MS,
    RouteResult,
    build_evacuation_network,
    elderly_speed_ms,
    future_aware_route,
    naive_route,
)
from .future_front import (
    ELDERLY_WALK_SPEED_MS,
    EvacuationResult,
    RoadNetwork,
    front_arrival_times,
    naive_shortest_path,
    time_dependent_evacuation,
)
from .hazard import HazardSequence

__all__ = [
    # Session-5 deterministic-front spine
    "ELDERLY_WALK_SPEED_MS",
    "RoadNetwork",
    "EvacuationResult",
    "front_arrival_times",
    "time_dependent_evacuation",
    "naive_shortest_path",
    # probabilistic-hazard routing (consumes spread_v2)
    "HazardSequence",
    "ELDERLY_FLAT_SPEED_MS",
    "elderly_speed_ms",
    "build_evacuation_network",
    "RouteResult",
    "naive_route",
    "future_aware_route",
]
