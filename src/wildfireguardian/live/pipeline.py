"""Detection -> routing -> operational outputs.

Round-3 PHASE 6-B / 6-D.

WHAT A TRIGGER ACTUALLY DOES
----------------------------
A new hotspot inside the registered region causes the 459-series scan to be run
against the **pre-computed canonical hazard field**, and its output rendered
into the three PHASE-3 delivery formats. The detection decides *whether* and
*where* to act. It does **not** move the hazard surface, and it cannot: ERA5
publishes on a ~5-day lag, so no field can be simulated for today
(:mod:`wildfireguardian.live.scope`).

THE HONEST LIMIT, STATED RATHER THAN HIDDEN
-------------------------------------------
The canonical field was simulated for one specific fire, anchored at that fire's
own ignition point. A hotspot 40 km away is a real detection, but the field is
not a statement about it. So every run measures the distance from the
triggering hotspot to the field's ignition point and records a verdict:

    IN_SCOPE       within live.trigger.field_applicability_radius_km
    OUT_OF_SCOPE   beyond it — outputs are still produced, and every one of
                   them is stamped, because suppressing them would hide a real
                   detection and publishing them silently would overclaim.

It is a LABEL, never a filter. Nothing is dropped on account of it.

THE 459 SERIES IS RESIDENT-SIDE
-------------------------------
Three buckets, no responder, no depot, no vehicle ETA. The mapping onto the
delivery layer's point schema is therefore:

    naive_into_FA_safe   -> a point to visit; the fire-blind route walks into
                            the fire and a detour exists
    no_safe_route        -> unreachable: no safe walking route within budget
    fa_exceeds_budget    -> unreachable: a route exists but not within budget
    both_safe            -> not on a sheet

``closing_window_min`` is the origin's OWN time-to-cutoff — the minutes until
that place reaches the impassable probability. For a 이장 reading the sheet that
is the same question the 439-series column answered, asked of a person on foot
rather than of a vehicle.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ..config import config_hash, get as _cfg
from ..delivery import broadcast, printable, sms
from ..delivery.villages import _bearing_word, cluster_points, named_refuges
from ..routing.evacuation import (
    build_time_expanded_field, future_aware_route, naive_route,
)
from ..routing.hazard import HazardSequence
from ..routing.slope import build_walk_network, load_snapshot_graph
from ..spread_v2.grid import CoarseGrid
from .firms import Hotspot, haversine_m
from .scope import (
    SCOPE_BANNER_KO, Scope, coverage_caveat_ko, responder_status_ko,
)
from .state import RunRecord, StageTimings

REPO = Path(__file__).resolve().parents[3]

#: Sheet wording for the resident-side series. `printable`'s defaults are
#: vehicle-side and belong to the 439 series; see its module docstring.
WALK_DISPATCH_HEADING = "■ 도보 대피 안내 지점 — 남은 시간 순"
WALK_UNREACHABLE_HEADING = "■ 안전한 도보 대피로 없음 — 별도 조치 필요"
WALK_UNREACHABLE_FALLBACK = "예산 내 안전한 보행 경로 없음"
WALK_ROUTE_FALLBACK = "대피 경로 확인 필요"

class RoutingCancelled(RuntimeError):
    """A scan was cancelled between origins, before anything was written.

    Round-3 PHASE 19 STEP 2. Raised by :func:`route_region` when the caller's
    ``should_cancel`` says so. It is a CONTROL signal and therefore separate
    from ``on_progress``, which is observation-only and whose return value is
    never read — keeping them apart is what lets the progress hook stay
    provably unable to change an answer.

    Cancellation is cooperative and lands only at an origin boundary. The scan
    has no other safe suspension point, and a half-finished classification is
    not a smaller answer — it is a wrong one.
    """


#: Bucket -> (is_unreachable, Korean reason / route note).
#: ⚠ `fa_exceeds_budget`'s sentence must not assert the BUDGET as the cause.
#: The code condition is only "the direct route avoids the fire AND the
#: future-aware search reached no refuge" — time-discretisation (the
#: ceil-rounded hazard bin blocking every detour) produces the same bucket
#: with the budget nowhere near binding, reproduced at 600 min. The sheet
#: states what is established and no more. docs/routing_limitations.md §1.
BUCKET_TEXT: dict[str, tuple[bool, str]] = {
    "naive_into_FA_safe": (False, "최단 경로는 화재 통과 — 우회 경로 필요"),
    "no_safe_route": (True, "예산 내 안전한 보행 경로가 없음(우회 포함)"),
    "fa_exceeds_budget": (True, "직행 경로는 화재를 지나지 않으나 예산 내 안전 도달은 확인되지 않음"),
    "both_enter": (True, "우회 경로도 화재를 통과함"),
    "naive_unreachable": (True, "대피처까지 연결된 경로 없음"),
}
#: Buckets that put a point on an operational sheet. `both_safe` does not.
ACTIONABLE: tuple[str, ...] = tuple(BUCKET_TEXT)


def _git() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with Path(p).open("rb") as fh:
        while block := fh.read(1 << 20):
            h.update(block)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# The weather basis — read from the data, never typed as a literal
# ---------------------------------------------------------------------------


def weather_basis(region: str, *, repo: Path = REPO) -> tuple[str, dict]:
    """When the pre-computed field's weather is from.

    The canonical field's t = 0 is the first satellite overpass of the fire it
    was built for (``spread_v2.grid.overpass_snapshots`` takes the max time of
    the first cluster), and the ERA5 series is evaluated from there. So the
    basis is derived from the committed detections CSV with the same clustering
    function the simulation used — it cannot drift away from the field, which a
    hard-coded date would.
    """
    import pandas as pd

    from ..spread_v2.grid import cluster_overpasses

    csv = repo / f"data/raw/firms_data/{region}_detections.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"cannot establish the weather basis: {csv} is missing. The scope "
            "statement is mandatory, so the run stops rather than printing an "
            "unlabelled one.")
    df = pd.read_csv(csv)
    col = "timestamp" if "timestamp" in df.columns else "acq_datetime"
    t = pd.to_datetime(df[col], utc=True).sort_values().reset_index(drop=True)
    op = cluster_overpasses(t, gap_minutes=90.0)
    first = op.iloc[0] if hasattr(op, "iloc") else op[0]
    t0 = t[op == first].max()
    stamp = t0.strftime("%Y-%m-%d %H:%M UTC")
    return stamp, {
        "basis_utc": t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "derived_from": str(csv.relative_to(repo)),
        "how": "first overpass cluster (gap 90 min) of the committed detections "
               "CSV — the same anchor spread_v2 forward-simulation uses for t=0",
        "era5_window": "ERA5 reanalysis for the fire's own dates; published on "
                       "an approximately five-day lag, so it exists for that "
                       "fire and does not exist for today",
    }


# ---------------------------------------------------------------------------
# Resources — loaded once, reused across triggers
# ---------------------------------------------------------------------------


@dataclass
class Resources:
    """Everything a trigger needs, loaded once so a running service is warm."""

    region: str
    hazard: HazardSequence
    haz: np.ndarray
    extent: tuple[float, float, float, float, float]
    npz_path: Path
    npz_sha256: str
    net: object
    destinations: list[dict]
    n_shelter_pois: int
    snapshot_walk: str
    snapshot_shelters: str
    #: Depot (119안전센터 proxy) POIs inside this region's walk bbox. Zero for
    #: Uiseong-Andong, which is why the responder side is NOT APPLICABLE there
    #: rather than zero. Never phrase this as "the region has no fire stations":
    #: six are mapped in the wider manifest bbox (HANDOFF_ROUND3.md rule 11).
    n_depot_pois: int
    #: The FIELD's own t = 0 core centroid. This — not the manifest's declared
    #: ignition coordinate — is what the simulation actually started from, and
    #: therefore what "is this field a statement about this hotspot?" must be
    #: measured against. For Yeongdeok the two differ by ~17 km: the manifest
    #: records 129.05, 36.43, which lies outside the walk bbox entirely, while
    #: the observed first-overpass core sits at 129.22, 36.47. Both are carried.
    field_core_lonlat: tuple[float, float]
    manifest_ignition_lonlat: tuple[float, float]
    timings: StageTimings

    def as_dict(self) -> dict:
        return {
            "region": self.region,
            "hazard_npz": str(self.npz_path.relative_to(REPO)),
            "hazard_npz_sha256": self.npz_sha256,
            "hazard_shape": list(self.haz.shape),
            "hazard_is_precomputed": True,
            "hazard_lineage": "CANONICAL (routing_demo_canonical.npz). NOT "
                              "routing_demo.npz, which is the output of a "
                              "reverted run — HANDOFF_ROUND3.md §2-A.",
            "snapshot_walk": self.snapshot_walk,
            "snapshot_shelters": self.snapshot_shelters,
            "n_walk_nodes": self.net.graph.number_of_nodes(),
            "n_walk_edges": self.net.graph.number_of_edges(),
            "n_shelter_pois": self.n_shelter_pois,
            "n_shelter_nodes": len(self.net.shelters),
            "field_core_lonlat": list(self.field_core_lonlat),
            "manifest_ignition_lonlat": list(self.manifest_ignition_lonlat),
            "anchor_note": (
                "field_core_lonlat is the centroid of the t=0 cells at p >= 0.5 "
                "in the pre-computed field — what the forward simulation was "
                "actually seeded from, and the same proxy candidate_origins "
                "uses for the reach band. manifest_ignition_lonlat is the "
                "editorial coordinate in fire_manifest.json. For "
                "yeongdeok_2025 they differ by about 17 km and the manifest "
                "point falls outside the walk bbox, so applicability is "
                "measured against the field, not against the manifest."),
            "read_from_cache": False,
        }


def load_resources(region: str, *, npz_path: Path, repo: Path = REPO,
                   sampling_m: float | None = None,
                   max_abs_slope: float | None = None) -> Resources:
    """Load the pre-computed field, the snapshot walk graph and the refuges.

    Everything comes from ``data/snapshots/`` and ``data/processed/`` — never
    from ``data/cache/**``, which is git-ignored and may be regenerated
    underneath a run.
    """
    import sys

    sys.path.insert(0, str(repo / "scripts"))
    from run_multi_region_routing import read_poi_snapshot, snapshot_for  # noqa: PLC0415

    t = StageTimings()

    t0 = time.monotonic()
    z = np.load(npz_path)
    haz = z["haz_stack"].astype(np.float32)
    times = np.asarray(z["haz_times"], float)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    hazard = HazardSequence(grid=grid, times_min=times,
                            surfaces=[haz[i] for i in range(haz.shape[0])])
    npz_sha = sha256_file(npz_path)
    t.load_hazard_s = time.monotonic() - t0

    t0 = time.monotonic()
    snap_walk = snapshot_for(region, "walk")
    G = load_snapshot_graph(snap_walk)
    dem = repo / f"data/raw/firms_data/{region}_dem.tif"
    net, _stats = build_walk_network(
        G, dem,
        sampling_m=float(sampling_m if sampling_m is not None
                         else _cfg("pedestrian.slope_sampling_m", 60.0)),
        max_abs_slope=float(max_abs_slope if max_abs_slope is not None
                            else _cfg("pedestrian.max_abs_slope", 0.60)),
        directed=True, apply_slope=True)
    t.load_network_s = time.monotonic() - t0

    t0 = time.monotonic()
    snap_shel = snapshot_for(region, "shelters")
    dests, n_pois = read_poi_snapshot(snap_shel, kind="shelter")
    if not dests:
        raise RuntimeError(
            "GATE A: zero refuges in the snapshot store. Every origin would be "
            "unreachable and the dispatch list would be meaningless.")
    net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
    dest_dicts = [{"name": d.name, "x": d.x, "y": d.y, "kind": d.kind}
                  for d in dests]
    # An EMPTY depot layer is a legitimate answer, not a failure. Read it so
    # the screen can say "responder side not applicable" instead of implying a
    # responder side that was silently never computed.
    _depots, n_depots = read_poi_snapshot(snapshot_for(region, "depots"),
                                          kind="depot")
    t.load_pois_s = time.monotonic() - t0

    manifest = json.loads(
        (repo / "data/raw/firms_data/fire_manifest.json").read_text(encoding="utf-8"))
    ign = next((f["ignition"] for f in manifest["fires"] if f["id"] == region), None)
    if ign is None:
        raise KeyError(f"{region} has no ignition point in fire_manifest.json")

    from pyproj import Transformer  # noqa: PLC0415

    to_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)
    rr, cc = np.where(haz[0] >= 0.5)
    core_x = float(xmin + (cc.mean() + 0.5) * cell)
    core_y = float(ymax - (rr.mean() + 0.5) * cell)
    core_lon, core_lat = to_4326.transform(core_x, core_y)

    return Resources(region=region, hazard=hazard, haz=haz,
                     extent=(xmin, ymin, xmax, ymax, cell),
                     npz_path=Path(npz_path), npz_sha256=npz_sha, net=net,
                     destinations=dest_dicts, n_shelter_pois=n_pois,
                     snapshot_walk=snap_walk.name, snapshot_shelters=snap_shel.name,
                     n_depot_pois=n_depots,
                     field_core_lonlat=(float(core_lon), float(core_lat)),
                     manifest_ignition_lonlat=(float(ign[0]), float(ign[1])),
                     timings=t)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


def candidate_origins(net, hazard, haz, extent, p_cut: float, stride: int):
    """The committed 459-series origin rule, unchanged.

    Duplicated from ``run_real_roads_real_hazard_slope.candidate_origins`` for
    the same reason the multi-region runner duplicates it: a later edit to a
    script must not silently redefine what "origin" means in a live run. The
    three copies are pinned against each other in tests.
    """
    xmin, ymin, xmax, ymax, cell = extent
    core = haz[0] >= 0.5
    rr, cc = np.where(core)
    ign_y = float(ymax - (rr.mean() + 0.5) * cell)
    ign_x = float(xmin + (cc.mean() + 0.5) * cell)
    band = 0.45 * (ymax - ymin)
    cand = []
    for i, n in enumerate(sorted(net.graph.nodes)):
        if i % stride:
            continue
        x, y = net.node_xy(n)
        if hazard.prob_at(x, y, 0.0) >= p_cut:
            continue
        if abs(y - ign_y) > band:
            continue
        cand.append(n)
    return cand, (ign_x, ign_y)


def _time_to_cutoff(hazard: HazardSequence, x: float, y: float, p_cut: float) -> float:
    for tm in hazard.times_min:
        if hazard.prob_at(x, y, float(tm)) >= p_cut:
            return float(tm)
    return math.inf


def route_region(res: Resources, *, p_cut: float, budget_min: float,
                 step_min: float, stride: int, limit_origins: int = 0,
                 collect_routes: int = 0,
                 on_progress: Callable[[int, int], None] | None = None,
                 should_cancel: Callable[[], bool] | None = None
                 ) -> tuple[dict, list[dict], list[dict], list[dict], float]:
    """Run the 459-series scan.

    Returns ``(counts, actionable points, every origin's geometry, route
    geometry, seconds)``.

    ``on_progress(done, total)`` is called after each origin is classified, for
    a caller that has to show a human what is happening for the ~27 seconds
    this takes (PHASE 19). It is OBSERVATION ONLY: it receives two integers,
    its return value is discarded, and it is never consulted for a decision —
    so a run with a callback and a run without one classify identically. The
    default is ``None``, which is the committed batch behaviour exactly.

    ``should_cancel()`` is the CONTROL hook, deliberately separate from the
    observation one. Consulted once per origin; a true answer raises
    :class:`RoutingCancelled` before anything has been written. A run that is
    never cancelled takes exactly the same path as a run with no hook at all —
    the only extra work is one predicate call per origin.

    The geometry list carries ALL scanned origins including ``both_safe``,
    because the operator screen colours the three outcomes against each other
    and a map showing only the 44 that need something would misrepresent the
    result as 44-of-44 rather than 44-of-458. It never reaches an operational
    artifact — see :func:`write_viz`.

    Unlike the batch runners this also carries each actionable origin's
    coordinates and window out, because the delivery layer needs a place, not a
    node id.

    ``collect_routes`` retains the polyline of BOTH routes for up to that many
    ``naive_into_FA_safe`` origins — the bucket where the two actually differ.
    Nothing extra is computed for it: both routes are already solved for every
    origin and are otherwise discarded. It exists so the PHASE-8 operator
    screen can draw a real route rather than an illustration, and it is written
    to a SEPARATE visualisation artifact: the operational sheets stay
    coordinate-free by requirement.
    """
    t0 = time.monotonic()
    cand, _ign = candidate_origins(res.net, res.hazard, res.haz, res.extent,
                                   p_cut, stride)
    if limit_origins:
        cand = cand[:limit_origins]

    counts = {k: 0 for k in ("naive_into_FA_safe", "no_safe_route", "both_safe",
                             "both_enter", "naive_unreachable",
                             "fa_exceeds_budget", "unclassified")}
    points: list[dict] = []
    geo: list[dict] = []
    routes: list[dict] = []
    n_cand = len(cand)
    if on_progress is not None:
        on_progress(0, n_cand)

    # PHASE 20: the time-expanded hazard table is a pure function of the
    # network, the hazard, the departure time, the budget and the step — and
    # this scan holds all five fixed, so the committed code rebuilt the SAME
    # array once per origin. Built once here instead. Every origin is handed
    # the identical object, so the answer is identical by construction rather
    # than by argument (docs/service_layer.md §5.1).
    #
    # The cancel check comes FIRST: the build costs a few hundred milliseconds,
    # and a request that has already been cancelled should not pay for a table
    # nobody will read.
    if should_cancel is not None and should_cancel():
        raise RoutingCancelled(
            f"cancelled before the hazard table was built; 0 of {n_cand} "
            "origins routed, nothing was written")
    field = build_time_expanded_field(
        res.net, res.hazard, departure_min=0.0, time_budget_min=budget_min,
        p_cut=p_cut, time_step_min=step_min)

    for i_origin, n in enumerate(cand, start=1):
        if should_cancel is not None and should_cancel():
            raise RoutingCancelled(
                f"cancelled after {i_origin - 1} of {n_cand} origins; nothing "
                "was written")
        nv = naive_route(res.net, n, res.hazard, departure_min=0.0, p_cut=p_cut)
        fa = future_aware_route(res.net, n, res.hazard, departure_min=0.0,
                                time_budget_min=budget_min, p_cut=p_cut,
                                time_step_min=step_min, field=field)
        if not nv.reached:
            bucket = "naive_unreachable"
        elif nv.enters_hazard and fa.reached and not fa.enters_hazard:
            bucket = "naive_into_FA_safe"
        elif nv.enters_hazard and not fa.reached:
            bucket = "no_safe_route"
        elif not nv.enters_hazard and fa.reached and not fa.enters_hazard:
            bucket = "both_safe"
        elif nv.enters_hazard and fa.enters_hazard:
            bucket = "both_enter"
        elif not nv.enters_hazard and not fa.reached:
            bucket = "fa_exceeds_budget"
        else:
            bucket = "unclassified"
        counts[bucket] += 1
        if (bucket == "naive_into_FA_safe" and collect_routes
                and len(routes) < collect_routes):
            routes.append({
                "origin_node": int(n),
                "naive_xy": [[round(v, 1) for v in res.net.node_xy(m)]
                             for m in nv.route],
                "fa_xy": [[round(v, 1) for v in res.net.node_xy(m)]
                          for m in fa.route],
                "naive_enters_hazard": bool(nv.enters_hazard),
                "fa_enters_hazard": bool(fa.enters_hazard),
                "naive_time_min": round(nv.total_time_min, 1),
                "fa_time_min": round(fa.total_time_min, 1),
                "naive_distance_m": round(nv.total_distance_m, 1),
                "fa_distance_m": round(fa.total_distance_m, 1),
            })
        x, y = res.net.node_xy(n)
        geo.append({"x": round(x, 1), "y": round(y, 1), "bucket": bucket})
        if on_progress is not None:
            on_progress(i_origin, n_cand)
        if bucket not in ACTIONABLE:
            continue
        tc = _time_to_cutoff(res.hazard, x, y, p_cut)
        unreachable, text = BUCKET_TEXT[bucket]
        pt = {
            "x": x, "y": y, "home_node": int(n), "bucket": bucket,
            "unreachable": unreachable,
            "closing_window_min": (None if math.isinf(tc) else tc),
            "walk_time_min": (round(fa.total_time_min, 1) if fa.reached else None),
        }
        if unreachable:
            pt["reason_ko"] = text
        else:
            pt["route_note"] = text
        points.append(pt)

    assert sum(counts.values()) == len(cand), "classification must partition"
    assert len(geo) == len(cand), "every scanned origin must have geometry"
    return counts, points, geo, routes, time.monotonic() - t0


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------


def _place_label(x: float, y: float, refuges: list[dict]) -> str:
    """A coordinate-free label. Identical rule to generate_dispatch_outputs."""
    best, bd = None, float("inf")
    for r in refuges:
        d = ((r["x"] - x) ** 2 + (r["y"] - y) ** 2) ** 0.5
        if d < bd:
            best, bd = r, d
    if best is None:
        return "위치 미상"
    word = _bearing_word(x - best["x"], y - best["y"])
    return f"{best['name'].strip()} {word}쪽 {int(round(bd))}m"


def _nearest_named(x: float, y: float, refuges: list[dict]) -> str:
    best, bd = None, float("inf")
    for r in refuges:
        d = ((r["x"] - x) ** 2 + (r["y"] - y) ** 2) ** 0.5
        if d < bd:
            best, bd = r, d
    return best["name"].strip() if best else "미상"


def deliver(points: list[dict], res: Resources, out_dir: Path, *,
            scope: Scope, counts: dict, applicability: dict, eps_m: float,
            make_pdf: bool = True,
            on_progress: Callable[[str, int, int], None] | None = None
            ) -> tuple[dict, float, float, float]:
    """Render the three PHASE-3 formats.

    ``on_progress(phase, done, total)`` is called with ``phase`` in
    ``{"cluster", "render", "pdf"}`` (PHASE 19). Observation only: two integers
    and a label go out, nothing comes back, and no decision reads it. Default
    ``None`` is the committed behaviour.

    Returns ``(manifest, cluster_s, render_s, pdf_s)``. PDF conversion is timed
    SEPARATELY because it happens after the dispatch list already exists and
    costs ~2.7 s per sheet in headless Chrome — folding it into the headline
    would answer "how long to print 29 sheets?" when the question is "how long
    until an operator has the list?".

    THIS PATH TRANSMITS NOTHING. ``sms.send`` is not called anywhere on it; the
    SMS layer only composes drafts and writes them to disk.

    ⚠ Since PHASE 7 that is a statement about the AUTOMATIC pipeline, not about
    the project. ``scripts/send_dispatch_email.py`` is a separate, manually
    invoked tool that CAN transmit by email — after an operator types a
    confirmation word in full. See ``docs/delivery_channels.md``.
    """
    refuges = named_refuges(res.destinations)

    t0 = time.monotonic()
    if on_progress is not None:
        on_progress("cluster", 0, len(points))
    for i_pt, p in enumerate(points, start=1):
        p["label"] = _place_label(p["x"], p["y"], refuges)
        if on_progress is not None:
            on_progress("cluster", i_pt, len(points))
    villages = cluster_points(points, res.destinations, eps_m=eps_m)
    cluster_s = time.monotonic() - t0

    t0 = time.monotonic()
    pdf_s = 0.0
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    commit, cfg = _git(), config_hash()
    # Two boxes, not five. Every mandated string still appears — the two scope
    # lines are merged into one box and the standing coverage qualifier moves
    # to the footer — because each bordered box costs enough vertical space
    # that five of them pushed the largest cluster onto a second page, and one
    # A4 page per village is a PHASE-3 design constraint.
    banners = [scope.mode_banner(),
               SCOPE_BANNER_KO + "  " + " · ".join(scope.lines())]
    if applicability["verdict"] != "IN_SCOPE":
        banners.insert(1, applicability["statement_ko"])
    # Per region. This is the A4 path: 273 sheets for the other two regions
    # carried Yeongdeok's caveat, and neither carried its own.
    footer_extra = [coverage_caveat_ko(res.region)]

    n_dispatch = sum(1 for p in points if not p["unreachable"])
    n_unreach = sum(1 for p in points if p["unreachable"])

    manifest: dict = {
        "schema_version": 1,
        "generated_utc": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "git_commit": commit,
        "config_hash": cfg,
        "series": "459 (canonical, resident-side, three buckets)",
        "scope": scope.as_dict(),
        "field_applicability": applicability,
        "counts": counts,
        "n_points": len(points),
        "n_dispatch": n_dispatch,
        "n_unreachable": n_unreach,
        "clustering": {"algorithm": "DBSCAN", "eps_m": eps_m, "min_samples": 1,
                       "is_administrative_village": False,
                       "note": "행정리가 아닌 공간 군집"},
        "sms_demo_mode": sms.demo_mode(),
        "sms_credentials_present": sms.credentials_present(),
        "nothing_was_sent": True,
        "nothing_was_sent_scope": (
            "This automatic pipeline transmits nothing. Since PHASE 7 the "
            "email channel CAN transmit, but only from the separate, manually "
            "invoked scripts/send_dispatch_email.py, and only after an "
            "operator types a confirmation word in full. If that ran against "
            "this run, its record is email_sent.json in this directory. "
            "docs/delivery_channels.md"),
        "villages": [],
    }

    prefix = ("재생 모드입니다.",) if scope.is_replay else ()
    if on_progress is not None:
        on_progress("render", 0, len(villages))
    for i_v, v in enumerate(villages, start=1):
        vdir = out_dir / v.slug()
        vdir.mkdir(parents=True, exist_ok=True)
        cx, cy = v.centroid
        refuge_name = _nearest_named(cx, cy, refuges or res.destinations)

        # (1) A4 sheet — the most important channel.
        html = printable.render_html(
            v, generated_at=generated_at, git_commit=commit, config_hash=cfg,
            source_file=str(res.npz_path.relative_to(REPO)),
            n_total_dispatch=n_dispatch, n_total_unreachable=n_unreach,
            banner_lines=banners, extra_footer_lines=footer_extra,
            dispatch_heading=WALK_DISPATCH_HEADING,
            unreachable_heading=WALK_UNREACHABLE_HEADING,
            unreachable_reason_fallback=WALK_UNREACHABLE_FALLBACK,
            route_note_fallback=WALK_ROUTE_FALLBACK)
        hp = vdir / "dispatch_a4.html"
        hp.write_text(html, encoding="utf-8")
        if make_pdf:
            t_pdf = time.monotonic()
            pdf = printable.html_to_pdf(hp, vdir / "dispatch_a4.pdf")
            pdf_s += time.monotonic() - t_pdf
            budget = printable.check_page_budget(pdf, v.name)
            if on_progress is not None:
                on_progress("pdf", i_v, len(villages))
        else:
            pdf = {"ok": False, "engine": None, "reason": "--no-pdf: HTML only"}
            budget = {"ok": None, "message": "not measured (--no-pdf)"}

        # (2) 마을방송 script.
        bc = broadcast.compose(v.name, refuge=refuge_name,
                               n_unreachable=v.n_unreachable, mode="walk",
                               prefix_lines=prefix)
        (vdir / "broadcast_script.txt").write_text(bc.text + "\n", encoding="utf-8")

        # (3) SMS drafts — composed and written, NEVER sent.
        soonest = min((p["closing_window_min"] for p in v.points
                       if p.get("closing_window_min") is not None), default=None)
        msgs = [sms.compose_family_walk(v.name, v.n_points, v.n_unreachable,
                                        refuge=refuge_name),
                sms.compose_welfare_walk(v.name, v.n_points, v.n_unreachable,
                                         soonest_min=soonest)]
        (vdir / "sms_drafts.json").write_text(json.dumps(
            {"village": v.name, "demo_mode": sms.demo_mode(), "sent": False,
             "scope_ko": scope.banner_block(),
             "note": "drafts only; sms.send() was never called and requires a "
                     "positional approval_token",
             "messages": [m.as_dict() for m in msgs]},
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (vdir / "sms_drafts.txt").write_text(
            scope.banner_block() + "\n\n"
            + "\n\n".join(f"[{m.recipient_role}] ({m.n_chars}자)\n{m.body}"
                          for m in msgs) + "\n", encoding="utf-8")

        entry = v.as_dict()
        entry.update({"directory": str(vdir.relative_to(out_dir)),
                      "refuge_used_in_messages": refuge_name,
                      "pdf": pdf, "page_budget": budget,
                      "broadcast_check": bc.check(),
                      "sms": [m.as_dict() for m in msgs],
                      # The points themselves, structurally. A downstream
                      # channel must never have to scrape the A4 HTML to learn
                      # what is on it: PHASE 7's first email did exactly that
                      # and silently rendered an unreachable point's checkbox
                      # column as its route note. Coordinates are deliberately
                      # NOT included — every operational artifact is
                      # coordinate-free by requirement.
                      "points": [{"label": p["label"],
                                  "unreachable": p["unreachable"],
                                  "bucket": p["bucket"],
                                  "closing_window_min": p["closing_window_min"],
                                  "walk_time_min": p.get("walk_time_min"),
                                  "reason_ko": p.get("reason_ko"),
                                  "route_note": p.get("route_note")}
                                 for p in v.points],
                      "formats_written": ["dispatch_a4.html",
                                          "broadcast_script.txt",
                                          "sms_drafts.json", "sms_drafts.txt"]})
        manifest["villages"].append(entry)
        if on_progress is not None:
            on_progress("render", i_v, len(villages))

    manifest["n_villages"] = len(villages)
    manifest["all_three_formats_per_village"] = all(
        len(v["formats_written"]) >= 4 for v in manifest["villages"])
    (out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest, cluster_s, (time.monotonic() - t0) - pdf_s, pdf_s


# ---------------------------------------------------------------------------
# Field applicability
# ---------------------------------------------------------------------------


def write_viz(out_dir: Path, res: Resources, *, points: list[dict],
              geo: list[dict], routes: list[dict], counts: dict, scope: Scope,
              trigger: Hotspot, hotspots: list[Hotspot],
              applicability: dict) -> Path:
    """Write ``viz.json`` — geometry for the PHASE-8 operator screen.

    ⚠ SEPARATE FROM THE OPERATIONAL ARTIFACTS, ON PURPOSE. Every sheet, script
    and SMS draft this project produces is COORDINATE-FREE by requirement: a
    이장 navigates by place name, and a coordinate on a dispatch sheet is
    unusable at best. A map, however, is nothing but coordinates. Keeping the
    two in different files is what lets both rules hold at once, so do not
    merge this into MANIFEST.json.

    Nothing here is recomputed. Every value is carried out of the run that just
    happened, and the counts are the same object the sheets were built from.
    """
    xmin, ymin, xmax, ymax, cell = res.extent
    doc = {
        "schema_version": 1,
        "purpose": "geometry for the operator screen. NOT an operational "
                   "artifact: the sheets, scripts and drafts are "
                   "coordinate-free by requirement and stay that way.",
        "region": res.region,
        "scope": scope.as_dict(),
        "trigger_source": scope.trigger_source,
        "field_applicability": applicability,
        "hazard": {
            "npz_path": str(res.npz_path.relative_to(REPO)),
            "npz_sha256": res.npz_sha256,
            "grid_extent_5179": [xmin, ymin, xmax, ymax],
            "cell_size_m": cell,
            "nrows": int(res.haz.shape[1]), "ncols": int(res.haz.shape[2]),
            "times_min": [float(t) for t in res.hazard.times_min],
            "cells_ge_0.5_per_slice": [int((res.haz[i] >= 0.5).sum())
                                       for i in range(res.haz.shape[0])],
        },
        "counts": counts,
        "responder_side": {
            "n_depot_pois": res.n_depot_pois,
            "available": res.n_depot_pois > 0,
            "computed": False,
            # ⚠ The separator is a FULL STOP, not an EM dash, and that is not a
            # style preference. This sentence is DISPLAYED: it reaches the
            # operator screen's footer warning and the console's amber panel.
            # The subset font shipped under `web/assets/fonts/` has no U+2014,
            # so the character was being served by whatever face the viewing
            # machine happened to have — one word of a Korean sentence in a
            # different typeface, differently on every laptop.
            # `docs/screen_gate_scope.md` §1 carries the measurement.
            #
            # ⚠ It was ALSO invisible to the dash gate, because it travels as
            # JSON payload data rather than as a literal beside a DOM sink
            # (`check_screen_assets.PAYLOAD_BLIND_SPOT`). Fixing it here does
            # not close that hole; the hole is recorded separately and stays.
            "status_ko": responder_status_ko(res.region, res.n_depot_pois),
            # ⚠ REGION-CONDITIONAL, AND GENERIC. This rule exists for regions
            # whose walk bbox holds zero mapped fire stations. The first
            # version wrote Uiseong-Andong's measured facts (its bbox
            # descriptor and its spelled-out wider-area depot count) into
            # EVERY region's record — the fourth instance of the
            # region-literal defect class, in an artifact instead of on a
            # screen, self-contradicted beside a status_ko reporting four
            # mapped depots. Absolute counts belong to status_ko, which is
            # derived per region from osm_completeness.json; this rule
            # carries none.
            "phrasing_rule": (
                "NEVER write 'this region has no fire stations'. The "
                "statement is that no amenity=fire_station is MAPPED IN OSM "
                "inside this region's registered walk bbox; wider areas can "
                "hold stations OSM has not mapped there. Absolute counts "
                "belong to status_ko. HANDOFF_ROUND3.md rule 11."
            ) if not res.n_depot_pois else None,
            "note": "The 459 series is RESIDENT-SIDE for every region, "
                    "Yeongdeok included: it contrasts a fire-blind walking "
                    "route with a future-aware one and never dispatches a "
                    "vehicle. No responder route exists to draw, anywhere.",
        },
        "field_core_lonlat": list(res.field_core_lonlat),
        "refuges": [{"name": d["name"], "x": round(d["x"], 1),
                     "y": round(d["y"], 1)} for d in res.destinations],
        "origins": geo,
        # ⚠ Every count in this sentence is COMPUTED. The static half used to
        # carry Yeongdeok's 44/458 into every region's viz.json — the fifth
        # instance of the region-literal class, an English note the Korean-
        # gated checker could not see (its scope is widened to match).
        "origins_note": (
            f"ALL {len(geo)} scanned origins, so the three outcomes can be "
            f"coloured against each other. Plotting only the {len(points)} "
            f"that need something would read as {len(points)}-of-{len(points)} "
            f"rather than {len(points)}-of-{len(geo)}."),
        "actionable": [{"x": round(p["x"], 1), "y": round(p["y"], 1),
                        "label": p.get("label"), "bucket": p["bucket"],
                        "unreachable": p["unreachable"],
                        "closing_window_min": p["closing_window_min"],
                        "walk_time_min": p.get("walk_time_min")}
                       for p in points],
        "routes": routes,
        "trigger_source": scope.trigger_source,
        "trigger_at": scope.trigger_at,
        "trigger_hotspot": trigger.as_dict(),
        "hotspots": [h.as_dict() for h in hotspots],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "viz.json"
    p.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
                 encoding="utf-8")
    return p


def assess_applicability(trigger: Hotspot, res: Resources, radius_km: float) -> dict:
    """Is the pre-computed field a statement about THIS hotspot?

    Measured against the field's own t = 0 core, because that is what the
    forward simulation was seeded from. The manifest's declared ignition
    coordinate is reported beside it, and its distance too — for Yeongdeok the
    two are ~17 km apart, so silently using the manifest one would put every
    genuine in-region detection out of scope.
    """
    lon0, lat0 = res.field_core_lonlat
    d_km = haversine_m(trigger.lat, trigger.lon, lat0, lon0) / 1000.0
    mlon, mlat = res.manifest_ignition_lonlat
    d_manifest = haversine_m(trigger.lat, trigger.lon, mlat, mlon) / 1000.0
    ok = d_km <= radius_km
    return {
        "verdict": "IN_SCOPE" if ok else "OUT_OF_SCOPE",
        "hotspot_to_field_core_km": round(d_km, 3),
        "hotspot_to_manifest_ignition_km": round(d_manifest, 3),
        "radius_km": radius_km,
        "anchor": "field t=0 core centroid (p >= 0.5)",
        "field_core_lonlat": [lon0, lat0],
        "manifest_ignition_lonlat": [mlon, mlat],
        "statement_ko": (
            f"트리거 화점은 사전 계산 위험면의 초기 화재 핵심에서 {d_km:.1f} km "
            f"떨어져 있습니다(기준 {radius_km:g} km 이내)."
            if ok else
            f"⚠ 범위 밖: 트리거 화점이 사전 계산 위험면의 초기 화재 핵심에서 "
            f"{d_km:.1f} km 떨어져 있습니다(기준 {radius_km:g} km). 이 위험면은 "
            f"이번 화점에 대한 예측이 아니며, 아래 수치는 참고용입니다."),
        "note": "A LABEL, never a filter. Nothing is dropped on account of it: "
                "suppressing a real detection is worse than publishing a "
                "stamped one.",
    }


def build_run_record(*, run_id: str, started: datetime, scope: Scope,
                     res: Resources, trigger: Hotspot, new_hotspots: list[Hotspot],
                     poll_meta: dict, counts: dict, applicability: dict,
                     timings: StageTimings, manifest: dict, out_dir: Path,
                     params: dict, notes: list[str]) -> RunRecord:
    return RunRecord(
        run_id=run_id, started_utc=started, mode=scope.mode, region=res.region,
        scope=scope.as_dict(),
        trigger={
            "trigger_source": scope.trigger_source,
            "trigger_at": scope.trigger_at,
            "trigger_at_meaning": scope.as_dict()["trigger_at_meaning"],
            "triggering_hotspot": trigger.as_dict(),
            "n_new_hotspots_this_trigger": len(new_hotspots),
            "new_hotspots": [h.as_dict() for h in new_hotspots],
            "rule": "a hotspot inside the registered bbox whose coordinate was "
                    "absent from every previous poll, at or above the "
                    "configured confidence, with the re-trigger interval "
                    "elapsed",
        },
        inputs={**res.as_dict(), "poll": poll_meta, "parameters": params},
        counts=counts,
        outputs={
            "directory": str(out_dir.relative_to(REPO))
                         if out_dir.is_relative_to(REPO) else str(out_dir),
            "n_villages": manifest.get("n_villages", 0),
            "n_points": manifest.get("n_points", 0),
            "n_dispatch": manifest.get("n_dispatch", 0),
            "n_unreachable": manifest.get("n_unreachable", 0),
            "formats": ["A4 sheet (HTML/PDF)", "마을방송 script (txt)",
                        "SMS drafts (json/txt)"],
            "all_three_formats_per_village":
                manifest.get("all_three_formats_per_village"),
            "sms_demo_mode": manifest.get("sms_demo_mode"),
            "sms_credentials_present": manifest.get("sms_credentials_present"),
        },
        timings=timings, field_applicability=applicability, notes=notes)


__all__ = [
    "ACTIONABLE", "BUCKET_TEXT", "Resources", "RoutingCancelled",
    "assess_applicability", "build_run_record", "candidate_origins", "deliver",
    "load_resources", "route_region", "sha256_file", "weather_basis",
]
