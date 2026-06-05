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

- :mod:`.rescue` (this feature) — **rescue-aware** routing on top of the above:
  routes the elderly only to refuges whose vehicle access road survives the
  predicted fire, and for residents who cannot self-evacuate computes the
  responder's ingress route instead, always reporting honestly who cannot be
  reached. :mod:`.rescue_demo` runs it end-to-end on the 영덕 extent (synthetic
  fallback when the FIRMS bundle is absent).
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
from .rescue import (
    FOUR_WAY_CLASSES,
    Depot,
    Destination,
    DestinationAssessment,
    DispatchEntry,
    IngressResult,
    RescueConfig,
    assess_destinations,
    assess_ingress,
    build_dispatch_list,
    build_drive_network,
    classify_origin,
    corridor_survival_time,
    ingress_corridor,
    rescuer_reachable,
    rescuer_route,
    resident_policies,
    sample_corridor_points,
)

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
    # rescue-aware routing (this feature)
    "RescueConfig",
    "Destination",
    "Depot",
    "DestinationAssessment",
    "IngressResult",
    "DispatchEntry",
    "FOUR_WAY_CLASSES",
    "build_drive_network",
    "sample_corridor_points",
    "corridor_survival_time",
    "ingress_corridor",
    "assess_ingress",
    "assess_destinations",
    "resident_policies",
    "rescuer_route",
    "rescuer_reachable",
    "build_dispatch_list",
    "classify_origin",
]
