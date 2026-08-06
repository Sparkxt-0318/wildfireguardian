"""The service layer: the pipeline in a shape a request can be made of.

Round-3 PHASE 19. Full write-up: ``docs/service_layer.md``.

⚠ THERE IS NO WEB SERVER IN THIS PACKAGE, AND THAT IS THE POINT OF IT.
No HTTP, no framework, no port, no route table. PHASE 19 was scoped to end
exactly here: the computation is separated from the scripts, made safe to call
twice at once, given a job model and a progress report, and left one layer
short of a transport. A transport written on top of an unproven service layer
would have two things to debug at once; this one is already tested.

WHAT IS HERE
------------
``params``     the frozen parameter set of one request, defaults lifted
               field-for-field from the scripts' argparse defaults
``guards``     osmnx settings and numpy's global RNG, frozen at start-up and
               asserted unchanged around every job
``progress``   stage-by-stage progress — ``경로 산출 137/458`` — for the ~27 s
               a scan takes
``resources``  the walk graph, hazard field and refuge POIs, loaded once per
               region and shared read-only by every request
``routing``    the service functions themselves: arguments in, serialisable
               results out, no print and no exit
``jobs``       submit → job id → poll status → read result → cancel, on a
               bounded queue. Cancellation reaches a RUNNING scan and leaves
               no artifact behind.

WHAT IS NOT HERE, AND WHY
-------------------------
**The routing is not optimised.** Nothing that computes a number was touched, so
"the answer did not change" stays falsifiable. The measured profile a later
PHASE should start from is in ``docs/service_layer.md`` §5.1 — and it is not the
one an early draft claimed.

WHAT THE COMMITTED SCRIPTS DO NOW
---------------------------------
They call these functions. ``scripts/run_live_detection.run_trigger`` is a
printing wrapper over :func:`~.routing.run_trigger_core`, and the manual and
replay paths reach it through that wrapper, so the three triggers running the
same code is a property of one function rather than an agreement between three.
No script was deleted.
"""

from __future__ import annotations

from ..live.pipeline import RoutingCancelled
from .guards import (
    GlobalStateViolation, assert_globals_unchanged, freeze_globals,
    frozen_snapshot, stable_globals,
)
from .jobs import (
    CANCELLED, FAILED, QUEUED, RUNNING, SUCCEEDED, Job, JobRunner, JobStore,
    QueueFull, build_runner,
)
from .params import (
    ParameterError, RoutingParams, check_in_region, check_npz, known_regions,
    npz_for_region, walk_bbox,
)
from .progress import NullProgress, Progress, StageSpec, TRIGGER_STAGES
from .resources import CacheEntry, ResourceCache, ResourceError, ResourceKey
from .routing import (
    IgnitionRequest, ScanOutcome, ServiceError, make_run_id, region_catalogue,
    region_gate, render_deliverables, result_digest, route_from_ignition,
    run_trigger_core, scan,
)

__all__ = [
    "CANCELLED", "CacheEntry", "FAILED", "GlobalStateViolation",
    "IgnitionRequest", "Job", "JobRunner", "JobStore", "NullProgress",
    "ParameterError", "Progress", "QUEUED", "QueueFull", "RUNNING",
    "ResourceCache", "ResourceError", "ResourceKey", "RoutingCancelled",
    "RoutingParams",
    "SUCCEEDED", "ScanOutcome", "ServiceError", "StageSpec", "TRIGGER_STAGES",
    "assert_globals_unchanged", "build_runner", "check_in_region", "check_npz",
    "freeze_globals", "frozen_snapshot", "known_regions", "make_run_id",
    "npz_for_region", "region_catalogue", "region_gate", "render_deliverables",
    "result_digest", "route_from_ignition", "run_trigger_core", "scan",
    "stable_globals", "walk_bbox",
]
