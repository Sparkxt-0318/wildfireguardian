"""The service functions: arguments in, serialisable results out.

Round-3 PHASE 19 STEP 1.

WHAT MOVED, AND WHAT DELIBERATELY DID NOT
-----------------------------------------
Nothing computational moved. Every number these functions return is produced by
the same calls the batch runners make — ``pipeline.route_region``,
``pipeline.deliver``, ``pipeline.write_viz``, ``pipeline.build_run_record`` —
with the same parameters, in the same order. What moved is everything AROUND
them: argparse, ``print``, ``sys.exit``, the working-directory assumption, and
the one-second-resolution run id.

That is the whole trick, and it is deliberate. A refactor that also improved the
routing would make "the answer did not change" unfalsifiable, because there
would be no way to tell a bug in the move from an improvement in the maths. The
answer must not change here, so nothing that computes it was touched.

⚠ THE ROUTING IS NOT OPTIMISED HERE, ON PURPOSE
Nothing that computes a number was touched, so "the answer did not change" stays
falsifiable: there is no way for a bug in the move to hide behind an improvement
in the maths.

The profile that a later PHASE should start from is in ``docs/service_layer.md``
§5.1 and is NOT the one an early draft of this docstring carried. Measured, the
per-origin cost is roughly one third ``naive_route`` and two thirds
``future_aware_route``; the largest single line is the hazard table
``future_aware_route`` rebuilds for every origin even though it is invariant
across them. ``naive_route`` already does ONE multi-destination Dijkstra per
origin — that optimisation is not available because it is already applied.

WHAT "STATELESS" MEANS HERE
---------------------------
Two calls with the same ``IgnitionRequest`` produce the same counts, the same
buckets, the same labels and the same message text. They do NOT produce the same
run id, the same ``generated_utc`` or the same timings, and they should not:
those record when the request happened, which genuinely differs.
:func:`result_digest` is the fingerprint over everything that must not differ,
and it is what the determinism tests compare.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..config import get as _cfg
from ..live import firms as _firms
from ..live import pipeline as _pipeline
from ..live.scope import Scope
from ..live.state import StageTimings
from . import guards
from .params import (
    RoutingParams, check_in_region, check_npz, known_regions, npz_for_region,
    walk_bbox,
)
from .progress import NullProgress, Progress
from .resources import ResourceCache, assert_read_only

REPO = Path(__file__).resolve().parents[3]

#: The keys of a run record that are ALLOWED to differ between two runs of the
#: same request. Everything else must be identical — see :func:`result_digest`.
NON_DETERMINISTIC_KEYS: frozenset[str] = frozenset({
    # when the request happened
    "run_id", "started_utc", "generated_utc", "generated_at", "trigger_at",
    "entered_utc", "acquired_utc",
    # how long it took. ⚠ EVERY duration field belongs here. A digest that
    # omits one reports a nondeterministic ANSWER for a run that was merely
    # slower — which is what the first PHASE-19 measurement did: `route_seconds`
    # was missing, and three scans with byte-identical buckets compared unequal.
    "timings_s", "elapsed_s", "idle_s", "duration_s", "seconds", "wall_s",
    "route_seconds", "load_seconds", "cluster_seconds", "render_seconds",
})


class ServiceError(RuntimeError):
    """A request could not be served. Carries a code a transport can map."""

    def __init__(self, message: str, *, code: str = "error") -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# The request
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IgnitionRequest:
    """One reported ignition point, and how to route from it.

    Frozen: a queued request cannot be edited while it waits, and two equal
    requests are equal objects.
    """

    region: str
    lat: float
    lon: float
    reported_by: str = "수동 입력"
    trigger_source: str = "manual"
    params: RoutingParams = field(default_factory=RoutingParams.from_config)
    make_pdf: bool = False
    #: Where the run directory goes. ``None`` = ``outputs/live/manual/{region}``.
    out_root: Path | None = None

    def as_dict(self) -> dict:
        return {
            "region": self.region,
            "lat": self.lat,
            "lon": self.lon,
            "reported_by": self.reported_by,
            "trigger_source": self.trigger_source,
            "make_pdf": self.make_pdf,
            "parameters": self.params.as_dict(),
        }

    def determinism_key(self) -> str:
        """Everything that must produce the same answer, hashed.

        Excludes ``reported_by`` and ``make_pdf``: the first is provenance text
        that reaches an artifact but not a computation, the second decides
        whether a PDF is rendered from an already-final list.
        """
        blob = json.dumps({
            "region": self.region,
            "lat": round(float(self.lat), 9),
            "lon": round(float(self.lon), 9),
            "params": {k: v for k, v in sorted(self.params.as_dict().items())},
        }, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# The outcome of a scan — serialisable, and with the internals kept beside it
# ---------------------------------------------------------------------------


@dataclass
class ScanOutcome:
    """What one 459-series scan produced.

    ``as_dict`` is the wire form: plain dicts and lists, no numpy, no graph, no
    Path. The internal lists are kept as attributes because
    :func:`render_deliverables` must hand ``pipeline.deliver`` the SAME point
    dicts the committed path hands it — a re-derived copy would be an
    opportunity for the answer to drift.
    """

    counts: dict
    points: list[dict]
    geo: list[dict]
    routes: list[dict]
    route_seconds: float
    n_scanned: int

    def as_dict(self) -> dict:
        return {
            "counts": dict(self.counts),
            "n_scanned": self.n_scanned,
            "n_actionable": len(self.points),
            "route_seconds": round(self.route_seconds, 3),
            # Coordinate-free, exactly as the operational artifacts are.
            "actionable": [{
                "bucket": p["bucket"],
                "unreachable": p["unreachable"],
                "closing_window_min": p["closing_window_min"],
                "walk_time_min": p.get("walk_time_min"),
                "reason_ko": p.get("reason_ko"),
                "route_note": p.get("route_note"),
                "label": p.get("label"),
            } for p in self.points],
        }

    def bucket_fingerprint(self) -> str:
        """The scan's answer, hashed: every origin's bucket, in scan order."""
        blob = "\n".join(f'{g["x"]},{g["y"]},{g["bucket"]}' for g in self.geo)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Read-only queries — cheap, no resources needed
# ---------------------------------------------------------------------------


def region_catalogue() -> list[dict]:
    """Every registered region and what is prepared for it.

    The first thing a screen needs, and it costs no load: a region is listed
    with ``ready`` false rather than omitted, so an operator sees that a region
    exists and why it cannot be routed instead of not seeing it at all.
    """
    out = []
    for r in known_regions():
        npz = npz_for_region(r)
        w, s, e, n = walk_bbox(r)
        ready = npz.exists()
        out.append({
            "region": r,
            "walk_bbox_wsen": [w, s, e, n],
            "hazard_npz": (str(npz.relative_to(REPO))
                           if npz.is_relative_to(REPO) else str(npz)),
            "ready": ready,
            "not_ready_reason": ("" if ready else
                                 "pre-computed hazard field is not on disk"),
        })
    return out


def region_gate(region: str, lat: float, lon: float) -> dict:
    """Is this coordinate servable? Verdict as data, no printing, no exit."""
    return check_in_region(region, lat, lon)


# ---------------------------------------------------------------------------
# The scan
# ---------------------------------------------------------------------------


def scan(resources, params: RoutingParams, *,
         progress: Progress | None = None,
         should_cancel: Callable[[], bool] | None = None) -> ScanOutcome:
    """Run the 459-series scan over already-loaded resources.

    Pure in the sense that matters: it reads shared, read-only resources,
    writes nothing to disk, mutates no global, and returns its whole answer.

    Raises :class:`~wildfireguardian.live.pipeline.RoutingCancelled` if
    ``should_cancel`` says so at an origin boundary — before any file exists.
    """
    p = progress or NullProgress()
    assert_read_only(resources)

    # The shelter count is what the per-origin cost is made of: each origin runs
    # one full-graph Dijkstra and then picks the nearest of these. Putting it on
    # the progress line tells an operator what the 25 seconds is DOING, not just
    # that it is doing something.
    n_shelters = len(getattr(resources.net, "shelters", ()) or ())

    def _tick(done: int, total: int) -> None:
        if done == 0:
            p.begin("routing", total, note_ko=f"대피소 {n_shelters}곳 탐색")
        else:
            p.set_done("routing", done, total=total)

    counts, points, geo, routes, route_s = _pipeline.route_region(
        resources,
        p_cut=params.p_cut,
        budget_min=params.time_budget_min,
        step_min=params.time_step_min,
        stride=params.stride,
        limit_origins=params.limit_origins,
        collect_routes=params.collect_routes,
        on_progress=_tick,
        should_cancel=should_cancel)
    p.finish("routing")
    return ScanOutcome(counts=counts, points=points, geo=geo, routes=routes,
                       route_seconds=route_s, n_scanned=sum(counts.values()))


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def render_deliverables(outcome: ScanOutcome, resources, out_dir: Path, *,
                        scope: Scope, applicability: dict,
                        params: RoutingParams, make_pdf: bool = False,
                        progress: Progress | None = None
                        ) -> tuple[dict, float, float, float]:
    """The three PHASE-3 formats, into ``out_dir``. Returns the deliver tuple.

    Writes files because the formats ARE files — an A4 sheet a 이장 prints is
    not a JSON payload. What changed is that the directory is an argument
    rather than a timestamp this function invents, which is what makes two
    concurrent requests land in two places.
    """
    p = progress or NullProgress()

    def _tick(phase: str, done: int, total: int) -> None:
        if done == 0:
            p.begin(phase, total)
        else:
            p.set_done(phase, done, total=total)

    out = _pipeline.deliver(
        outcome.points, resources, Path(out_dir), scope=scope,
        counts=outcome.counts, applicability=applicability, eps_m=params.eps_m,
        make_pdf=make_pdf, on_progress=_tick)
    p.finish("cluster")
    p.finish("render")
    if make_pdf:
        p.finish("pdf")
    else:
        p.skip("pdf", "--no-pdf")
    return out


# ---------------------------------------------------------------------------
# The whole job
# ---------------------------------------------------------------------------


def make_run_id(*, at: datetime | None = None, unique: str = "") -> str:
    """A run id that two simultaneous requests cannot share.

    The committed scheme was ``%Y%m%dT%H%M%SZ`` — one-second resolution, which
    is fine for a script that runs once and a collision waiting to happen for a
    service. The timestamp is kept, because sorting run directories by name is
    how every consumer in this tree finds the latest one; the job's own id is
    appended so two requests in the same second are two directories.
    """
    stamp = (at or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{unique}" if unique else stamp


def run_trigger_core(resources, scope: Scope, trigger, new_hotspots: list, *,
                     params: RoutingParams, out_dir: Path, poll_meta: dict,
                     notes: list[str], all_hotspots: list | None = None,
                     make_pdf: bool = True, run_id: str | None = None,
                     load_timings: StageTimings | None = None,
                     resources_were_cached: bool = False,
                     progress: Progress | None = None,
                     applicability: dict | None = None,
                     should_cancel: Callable[[], bool] | None = None,
                     extra_inputs: dict | None = None) -> dict:
    """One trigger: route, deliver, record. The single implementation.

    ``scripts/run_live_detection.run_trigger`` is a printing wrapper around
    this, and the manual and replay paths reach it through that wrapper, so
    "the three triggers run the same code" is a fact about one function rather
    than an agreement between three.

    The stage ORDER is the committed one, unchanged: applicability, route,
    deliver, timings, viz, record.
    """
    p = progress or NullProgress()
    started = datetime.now(UTC)
    run_id = run_id or make_run_id(at=started)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # A caller that already computed it (to print a banner before the 27-second
    # wait begins) passes it in rather than paying for a second identical
    # haversine — the function is pure, so the two can never disagree.
    if applicability is None:
        applicability = _pipeline.assess_applicability(
            trigger, resources, float(params.applicability_radius_km))

    try:
        outcome = scan(resources, params, progress=p, should_cancel=should_cancel)
    except _pipeline.RoutingCancelled:
        # Nothing has been written yet — routing precedes every write. Remove
        # the directory this run reserved so a cancelled request leaves no
        # empty shell that a later reader could mistake for a failed result.
        p.fail("routing", "취소됨")
        try:
            if out_dir.exists() and not any(out_dir.iterdir()):
                out_dir.rmdir()
        except OSError:
            pass
        raise

    # Cancelling mid-delivery would leave half a village's sheets on disk, so
    # the last chance to stop is here, with the answer computed and no file
    # written. After this point the run completes.
    if should_cancel is not None and should_cancel():
        p.fail("cluster", "취소됨")
        try:
            if out_dir.exists() and not any(out_dir.iterdir()):
                out_dir.rmdir()
        except OSError:
            pass
        raise _pipeline.RoutingCancelled(
            "cancelled after routing, before any delivery file was written")

    manifest, cluster_s, render_s, pdf_s = render_deliverables(
        outcome, resources, out_dir, scope=scope, applicability=applicability,
        params=params, make_pdf=make_pdf, progress=p)

    lt = load_timings or StageTimings()
    timings = StageTimings(
        load_hazard_s=lt.load_hazard_s, load_network_s=lt.load_network_s,
        load_pois_s=lt.load_pois_s, route_s=outcome.route_seconds,
        cluster_s=cluster_s, render_s=render_s, pdf_s=pdf_s)

    p.begin("record", 2)
    viz = _pipeline.write_viz(
        out_dir, resources, points=outcome.points, geo=outcome.geo,
        routes=outcome.routes, counts=outcome.counts, scope=scope,
        trigger=trigger, hotspots=(all_hotspots or new_hotspots),
        applicability=applicability)
    p.advance("record")

    rec = _pipeline.build_run_record(
        run_id=run_id, started=started, scope=scope, res=resources,
        trigger=trigger, new_hotspots=new_hotspots, poll_meta=poll_meta,
        counts=outcome.counts, applicability=applicability, timings=timings,
        manifest=manifest, out_dir=out_dir,
        params=params.as_run_parameters(), notes=notes)
    doc = rec.as_dict()
    doc["inputs"]["read_from_cache"] = bool(resources_were_cached)
    doc["inputs"]["resource_cache"] = {
        "resources_were_cached": bool(resources_were_cached),
        "note": ("load_* timings are zero when the resources were already "
                 "resident: a warm request did not pay that cost, and "
                 "reporting the filling request's cost again would inflate "
                 "every warm cold_total_s."),
    }
    if extra_inputs:
        doc["inputs"].update(extra_inputs)
    doc["service"] = {
        "phase": "PHASE 19 — service layer",
        "run_id_scheme": "%Y%m%dT%H%M%SZ_<job-id-8>; the suffix is what two "
                         "requests inside one second do not share",
        "globals": guards.frozen_snapshot().as_dict(),
    }
    (out_dir / "RUN.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    p.advance("record")
    p.finish("record")

    return {
        "run_id": run_id,
        "out_dir": str(out_dir),
        "counts": outcome.counts,
        "timings": timings.as_dict(),
        "applicability": applicability,
        "trigger_source": scope.trigger_source,
        "n_villages": manifest["n_villages"],
        "n_points": manifest["n_points"],
        "n_scanned": outcome.n_scanned,
        "n_routes": len(outcome.routes),
        "bucket_fingerprint": outcome.bucket_fingerprint(),
        "viz": str(viz),
        "resources_were_cached": bool(resources_were_cached),
        "scan": outcome.as_dict(),
        "manifest": manifest,
    }


def route_from_ignition(request: IgnitionRequest, *, cache: ResourceCache,
                        run_id: str | None = None,
                        progress: Progress | None = None,
                        should_cancel: Callable[[], bool] | None = None,
                        repo: Path = REPO) -> dict:
    """A reported coordinate to a dispatch list. THE web-facing entry point.

    Raises :class:`ServiceError` rather than printing or exiting — the caller
    decides whether that becomes an exit code, a console line or a 4xx.
    """
    p = progress or NullProgress()
    guards.freeze_globals()

    gate = region_gate(request.region, request.lat, request.lon)
    if not gate["inside_registered_region"]:
        raise ServiceError(gate["reason_ko"], code="out_of_region")

    npz = check_npz(npz_for_region(request.region, repo=repo))
    entered_utc = datetime.now(UTC)

    p.begin("load", 3)
    resources, was_cached, entry = cache.get(request.region, request.params,
                                             npz_path=npz)
    # Loading is not interruptible — it is one osmnx call — so the check lands
    # immediately after it, which costs a cancelled request the ~1.5 s load and
    # nothing more.
    if should_cancel is not None and should_cancel():
        raise _pipeline.RoutingCancelled("cancelled before routing began")
    if was_cached:
        p.skip("load", "이미 적재됨 (사전 적재 캐시 적중)")
        load_timings = StageTimings()
    else:
        p.finish("load")
        load_timings = StageTimings(
            load_hazard_s=resources.timings.load_hazard_s,
            load_network_s=resources.timings.load_network_s,
            load_pois_s=resources.timings.load_pois_s)

    basis, basis_meta = _pipeline.weather_basis(request.region, repo=repo)
    scope = Scope(mode="manual", weather_basis=basis,
                  hazard_field=str(npz.relative_to(repo)),
                  region=request.region,
                  trigger_source=request.trigger_source,
                  trigger_at=entered_utc.strftime("%Y-%m-%d %H:%M UTC"))

    point = _firms.Hotspot(
        lat=request.lat, lon=request.lon, acquired_utc=entered_utc,
        source=f"manual:{request.reported_by}", satellite="",
        instrument="manual", confidence_raw="high", frp=None, daynight="")

    out_root = Path(request.out_root) if request.out_root is not None else (
        repo / str(_cfg("live.output_root", "outputs/live"))
        / "manual" / request.region)
    rid = run_id or make_run_id(at=entered_utc)

    meta = {
        "kind": "manual",
        "reported_by": request.reported_by,
        "entered_utc": entered_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entered_utc_meaning": "when the coordinate was entered by an operator; "
                               "NOT a satellite overpass time",
        "input_lat": request.lat, "input_lon": request.lon,
        "region_bbox_wsen": gate["bbox_wsen"],
        "inside_registered_region": True,
        "hazard_field": str(npz.relative_to(repo)),
        "hazard_field_sha256": resources.npz_sha256,
        "hazard_weather_basis": basis,
        "hazard_weather_basis_utc": basis_meta["basis_utc"],
        "no_geocoding": "latitude/longitude only; address and 지번 lookup are "
                        "out of scope for this phase",
    }
    notes = [
        "MANUAL TRIGGER. The ignition point was reported, not detected. The "
        "trigger time is when the coordinate was entered, not a satellite "
        "overpass.",
        "The hazard surface is the SAME pre-computed field the FIRMS path uses "
        "and was not re-simulated: ERA5 publishes on a ~5-day lag.",
    ]

    t_input = time.monotonic()
    summary = run_trigger_core(
        resources, scope, point, [point], params=request.params,
        out_dir=out_root / rid, poll_meta=meta, notes=notes,
        all_hotspots=[point], make_pdf=request.make_pdf, run_id=rid,
        load_timings=load_timings, resources_were_cached=was_cached,
        progress=p, should_cancel=should_cancel,
        extra_inputs={"parameters": {**request.params.as_run_parameters(),
                                     "weather_basis": basis_meta}})

    total_s = (time.monotonic() - t_input) - summary["timings"]["pdf_s"]
    summary["manual_trigger"] = {
        **meta,
        "input_to_dispatch_list_s": round(total_s, 3),
        "input_to_dispatch_list_excludes_pdf_s": round(
            summary["timings"]["pdf_s"], 3),
        "resources_were_cached": was_cached,
        "input_to_dispatch_list_note": (
            "wall clock from the coordinate being in hand to the dispatch list "
            "existing in every text format. EXCLUDES A4 PDF conversion, which "
            "runs after the list already exists. When resources_were_cached is "
            "true this IS the warm figure — the service loaded nothing."),
    }
    summary["resource_cache_entry"] = entry.as_dict()
    summary["determinism_key"] = request.determinism_key()

    out_dir = Path(summary["out_dir"])
    rec = json.loads((out_dir / "RUN.json").read_text(encoding="utf-8"))
    rec["manual_trigger"] = summary["manual_trigger"]
    (out_dir / "RUN.json").write_text(
        json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    guards.assert_globals_unchanged(where=f"route_from_ignition({request.region})")
    return summary


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def result_digest(summary: dict) -> str:
    """Fingerprint of everything about a result that must not vary.

    Time stamps, timings and the run id are dropped, recursively — those are
    facts about WHEN the request ran. What survives is the answer: the counts,
    every origin's bucket, the village structure and every rendered message.
    """
    def strip(obj):
        if isinstance(obj, dict):
            return {k: strip(v) for k, v in sorted(obj.items())
                    if k not in NON_DETERMINISTIC_KEYS}
        if isinstance(obj, list):
            return [strip(v) for v in obj]
        return obj

    keep = {
        "counts": summary.get("counts"),
        "n_scanned": summary.get("n_scanned"),
        "bucket_fingerprint": summary.get("bucket_fingerprint"),
        "n_villages": summary.get("n_villages"),
        "n_points": summary.get("n_points"),
        "scan": strip(summary.get("scan", {})),
        "villages": strip([
            {k: v for k, v in village.items()
             if k in ("name", "n_points", "n_unreachable", "points", "sms",
                      "refuge_used_in_messages", "broadcast_check")}
            for village in summary.get("manifest", {}).get("villages", [])]),
        "applicability": strip(summary.get("applicability", {})),
    }
    blob = json.dumps(keep, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


__all__ = [
    "IgnitionRequest", "NON_DETERMINISTIC_KEYS", "ScanOutcome", "ServiceError",
    "make_run_id", "region_catalogue", "region_gate", "render_deliverables",
    "result_digest", "route_from_ignition", "run_trigger_core", "scan",
]
