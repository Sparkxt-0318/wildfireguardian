#!/usr/bin/env python
"""Truck-crew replay of the 2025-03-25 영덕 fire, built from committed inputs only.

Rule: `docs/truck_crew_replay.md` §1-§3, written BEFORE this ran. Brief:
`docs/auto/briefs/TRUCK_CREW_REPLAY.md`. Nothing here re-implements routing,
snapping, scheduling or grading: every one of those comes from the module that
already owns it and is imported below.

Writes (new filenames only, never a committed artifact):
  data/processed/truck_crew_replay_yeongdeok.json
  web/truck_crew_replay.html             (from scripts/truck_crew_replay.template.html)
  outputs/truck_crew_replay/<stamp>/     (per-vehicle GeoJSON + KML)
and appends §4 to docs/truck_crew_replay.md.

    python scripts/build_truck_crew_replay.py
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from pyproj import Transformer

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.routing.margins import round_trip_margin  # noqa: E402
from wildfireguardian.routing.rescue import (  # noqa: E402
    RescueConfig, assess_destinations, corridor_survival_time, ingress_corridor,
    node_survival_time, rescuer_route, sample_corridor_points,
)
from wildfireguardian.routing.rescue_demo import _immobile_homes  # noqa: E402

from regrade_three_way import MISS, classify_route, first_seen_grid  # noqa: E402
from run_real_roads_real_hazard_slope import REAL_OSM_SCAN_STRIDE  # noqa: E402
from run_rescue_routing_full import materialise_snapshots  # noqa: E402
from run_rescue_routing_real_hazard import build_scenario  # noqa: E402
from run_vehicle_pickup_intervention import (  # noqa: E402
    MARGIN, T_LOAD, T_UNLOAD, W, schedule,
)

# Inputs are read, never written, so their paths are assembled rather than written
# as one literal: scripts/build_artifact_manifest.py infers 「which script regenerates
# this artifact」 from full-path string literals and takes the first script in
# alphabetical order, and an unsplit literal here would make this build claim it
# regenerates the two artifacts it only reads.
PROC = REPO / "data/processed"
NPZ = PROC / "routing_demo_canonical.npz"
GRADING = PROC / "building_origins_observed_grading_yeongdeok.json"
OUT = REPO / "data/processed/truck_crew_replay_yeongdeok.json"   # written by this script
TEMPLATE = REPO / "scripts/truck_crew_replay.template.html"
PAGE = REPO / "web/truck_crew_replay.html"
OUTROOT = REPO / "outputs/truck_crew_replay"
DOC = REPO / "docs/truck_crew_replay.md"
PLACEHOLDER = "/*__" + "DATA" + "__*/"   # never appears verbatim in this file

HORIZON = 720.0          # the forecast field's own horizon; the replay clock (§2)
FLEETS = (4, 2, 6)       # k = 4 is the headline case, one vehicle per OSM depot
DISPATCH = 30.0          # the config's dispatch delay, all vehicles free at D
MARKERS_MIN = (300.0, 480.0)   # 5 h / 8 h doctrine lead times, drawn on the clock
TO_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)


def _git() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def _f(v):
    """A finite float, or None for inf/nan (never a silent 0)."""
    return None if v is None or not math.isfinite(v) else round(float(v), 2)


def _cell(grid, x: float, y: float) -> tuple[int, int] | None:
    """(row, col) of a point on the hazard grid, or None if outside it (A5)."""
    col = int(math.floor((x - grid.minx) / grid.cell_size_m))
    row = int(math.floor((grid.maxy - y) / grid.cell_size_m))
    if 0 <= row < grid.nrows and 0 <= col < grid.ncols:
        return row, col
    return None


def build_population(sc, cfg) -> tuple[list[dict], dict]:
    """§1: rescue-needing walk nodes, aggregated onto drive nodes (pickups)."""
    grading = json.loads(GRADING.read_text(encoding="utf-8"))
    per_node = grading["per_node"]
    walk_nodes = [int(r["node"]) for r in per_node]
    buildings = {int(r["node"]): int(r["n_buildings"]) for r in per_node}
    no_safe = {int(r["node"]) for r in per_node
               if r["forecast_bucket"] == "no_safe_route"}
    # the pipeline's own deterministic draw, same code, same seed, new node list
    immobile = set(_immobile_homes(SimpleNamespace(origins=walk_nodes), cfg))
    needing = sorted(immobile | no_safe)

    pick: dict[int, dict] = {}
    for w in needing:
        x, y = sc.walk.node_xy(w)
        dn = int(sc.drive.nearest_node(x, y))
        dx, dy = sc.drive.node_xy(dn)
        p = pick.setdefault(dn, {"drive_node": dn, "walk_nodes": [], "snaps": [],
                                 "n_buildings": 0, "sources": set(),
                                 "x": float(dx), "y": float(dy)})
        p["walk_nodes"].append(w)
        p["snaps"].append(math.hypot(dx - x, dy - y))
        p["n_buildings"] += buildings[w]
        if w in no_safe:
            p["sources"].add("no_safe_walk")
        if w in immobile:
            p["sources"].add("immobile_draw")

    pickups = []
    for dn in sorted(pick):
        p = pick[dn]
        surv = node_survival_time(sc.hazard, p["x"], p["y"], cfg.vehicle_cutoff)
        pickups.append({
            "drive_node": dn,
            "walk_node": p["walk_nodes"][0],
            "walk_nodes": p["walk_nodes"],
            "n_walk_nodes": len(p["walk_nodes"]),
            "n_buildings": p["n_buildings"],
            "snap_m_median": round(float(np.median(p["snaps"])), 1),
            "snap_m_max": round(float(max(p["snaps"])), 1),
            "sources": sorted(p["sources"]),
            "x": round(p["x"], 1), "y": round(p["y"], 1),
            "node_cutoff_min": _f(surv),
            "deadline": float(min(surv, HORIZON)),
        })
    stats = {
        "building_walk_nodes": len(walk_nodes),
        "routable_buildings": grading["denominators"]["routable_buildings"],
        "no_safe_walk_nodes": len(no_safe),
        "immobile_draw_nodes": len(immobile),
        "immobile_fraction": cfg.immobile_fraction,
        "seed": cfg.seed,
        "rescue_needing_walk_nodes": len(needing),
        "pickups": len(pickups),
        "buildings_behind_pickups": sum(p["n_buildings"] for p in pickups),
        "walk_nodes_sharing_a_pickup": len(needing) - len(pickups),
        "deadline_histogram": {},
    }
    hist: dict[str, int] = {}
    for p in pickups:
        hist[str(p["deadline"])] = hist.get(str(p["deadline"]), 0) + 1
    stats["deadline_histogram"] = dict(sorted(hist.items(), key=lambda kv: float(kv[0])))
    return pickups, stats


def leg_detail(sc, cfg, route, departure_min: float, fs, tobs) -> dict:
    """Geometry, forecast closing minute and observed class for one driven leg."""
    path = [int(n) for n in route]
    xs, ys, _seg = sample_corridor_points(sc.drive, path, cfg.ingress_sample_spacing_m)
    closing = corridor_survival_time(sc.hazard, xs, ys, cfg.vehicle_cutoff)
    # A6': the observation clock is shifted by the trip's departure minute, so
    # regrade_three_way.classify_route is reused unchanged (docs §3).
    cls = classify_route(sc.drive, path, fs - departure_min, tobs - departure_min,
                         sc.hazard.grid)
    return {
        "departure_min": round(float(departure_min), 2),
        "travel_min": round(float(cls["total_time_min"]), 2),
        "closing_min": _f(closing),
        "closing_never_in_window": not math.isfinite(closing),
        "n_nodes": len(path),
        "xy": [[int(round(v)) for v in sc.drive.node_xy(n)] for n in path],
        "observed": {f"class_m{m}": cls[f"class_m{m}"] for m in MISS},
    }


def depot_corridors(sc, cfg, depot_nodes, target: int) -> tuple[dict | None, dict | None]:
    """Primary and fallback depot ingress corridors for one pickup (imported)."""
    res = []
    for i, dn in enumerate(depot_nodes):
        r = ingress_corridor(sc.drive, dn, target, sc.hazard, cfg, depot_index=i)
        res.append((i, dn, r))
    ok = [t for t in res if t[2].reachable]
    ok.sort(key=lambda t: t[2].responder_eta_min)

    def pack(t):
        i, dn, r = t
        return {"depot_index": i, "depot_drive_node": int(dn),
                "eta_min": _f(r.responder_eta_min),
                "closing_min": _f(r.ingress_survival_time_min),
                "closing_window_min": _f(r.closing_window_min),
                "reachable": bool(r.reachable),
                "corridor_len_nodes": len(r.corridor_nodes)}

    if not ok:
        best = max(res, key=lambda t: t[2].closing_window_min)
        return pack(best), None
    primary = ok[0]
    fallback = next((t for t in ok[1:] if t[1] != primary[1]), None)
    return pack(primary), (pack(fallback) if fallback else None)


def run_fleet(sc, cfg, pickups, refuge_nodes, depot_nodes, k, fs, tobs, obs_first):
    """One fleet size: the imported scheduler, then the per-trip detail (§2, §3)."""
    homes = [dict(p) for p in pickups]
    outcome, vehicles = schedule(sc, cfg, homes, refuge_nodes, k, DISPATCH)
    by_node = {p["drive_node"]: p for p in pickups}

    # The imported scheduler advances a vehicle's clock for a pickup it reaches and
    # then cannot safely leave ("unsafe_egress"): it charges the loading time and
    # leaves the vehicle at its PREVIOUS location, and writes no log entry. Those
    # events are recovered from the per-home outcome and replayed in arrival order
    # with the logged trips, or the reconstruction runs on a clock the scheduler
    # never had. A vehicle's arrivals are non-decreasing, so arrival order is the
    # order it did them in; every step below is checked against the scheduler's
    # own recorded minute and the run stops if one disagrees.
    stranded: dict[int, list[dict]] = {}
    for dn, o in outcome.items():
        if o and o.get("status") == "unsafe_egress":
            stranded.setdefault(o["vehicle"], []).append(
                {"home": int(dn), "arrival_min": o["arrival_min"], "kind": "unsafe_egress"})

    per_vehicle = []
    trips_all = []
    for v in vehicles:
        start = depot_nodes[v["id"] % len(depot_nodes)]
        dep = DISPATCH
        trips = []
        unsafe_legs = []
        events = [dict(e, kind="trip") for e in v["log"]] + stranded.get(v["id"], [])
        events.sort(key=lambda e: (e["arrival_min"], e["kind"] != "trip"))
        for entry in events:
            home = int(entry["home"])
            ing = rescuer_route(sc.drive, start, home, sc.hazard, cfg, departure_min=dep)
            if not (ing.reached and not ing.enters_hazard):
                raise RuntimeError(f"k={k} v={v['id']} ingress to {home} did not "
                                   "reproduce; refusing to report a trip it did not plan")
            arrival = dep + ing.total_time_min
            if round(arrival, 1) != entry["arrival_min"]:
                raise RuntimeError(
                    f"k={k} v={v['id']} replay diverged from the scheduler at "
                    f"{home}: arrival {round(arrival,1)} vs {entry['arrival_min']}")
            if entry["kind"] == "unsafe_egress":
                unsafe_legs.append({
                    "drive_node": home, "arrival_min": round(arrival, 2),
                    "n_buildings": by_node[home]["n_buildings"],
                    "note": "reached, but the scheduler found no safe egress within the "
                            "responder budget; the vehicle is charged the loading time and "
                            "continues from its previous location",
                })
                dep = arrival + T_LOAD
                continue
            refuge = int(entry["refuge_node"])
            eg = rescuer_route(sc.drive, home, refuge, sc.hazard, cfg,
                               departure_min=arrival + T_LOAD)
            if not (eg.reached and not eg.enters_hazard):
                raise RuntimeError(f"k={k} v={v['id']} egress from {home} did not reproduce")
            free_at = arrival + T_LOAD + eg.total_time_min + T_UNLOAD
            if round(free_at, 1) != entry["free_at"]:
                raise RuntimeError(
                    f"k={k} v={v['id']} replay diverged from the scheduler: "
                    f"free {round(free_at,1)} vs {entry['free_at']}")

            p = by_node[home]
            ing_d = leg_detail(sc, cfg, ing.route, dep, fs, tobs)
            eg_d = leg_detail(sc, cfg, eg.route, arrival + T_LOAD, fs, tobs)
            primary, fallback = depot_corridors(sc, cfg, depot_nodes, home)
            rtm = round_trip_margin(sc.drive, depot_nodes[primary["depot_index"]], home,
                                    sc.hazard, cfg, depot_index=primary["depot_index"])
            closing = ing_d["closing_min"]
            abort_min = None if closing is None else round(closing - MARGIN, 2)
            aborted = bool(abort_min is not None and arrival > abort_min)
            seen = obs_first.get(home)
            reached_obs = (seen is None) or (seen > arrival)
            trip = {
                "vehicle": v["id"], "seq": len(trips),
                "drive_node": home, "walk_node": p["walk_node"],
                "n_walk_nodes": p["n_walk_nodes"], "n_buildings": p["n_buildings"],
                "snap_m_median": p["snap_m_median"], "snap_m_max": p["snap_m_max"],
                "sources": p["sources"],
                "x": p["x"], "y": p["y"],
                "start_node": int(start),
                "node_cutoff_min": p["node_cutoff_min"],
                "deadline_applied_min": round(p["deadline"], 2),
                "eta_min": round(arrival, 2),
                "margin_min": (None if closing is None else round(closing - arrival, 2)),
                "abort_min": abort_min,
                "aborted_by_rule": aborted,
                "load_min": T_LOAD, "unload_min": T_UNLOAD,
                "delivered_min": round(arrival + T_LOAD + eg.total_time_min, 2),
                "free_at_min": round(free_at, 2),
                "refuge_node": refuge,
                "ingress": ing_d, "egress": eg_d,
                "depot_primary": primary, "depot_fallback": fallback,
                "round_trip_margin_min": _f(rtm.margin_minutes),
                "round_trip_margin_policy": cfg.egress_policy,
                "round_trip_margin_note": rtm.note,
                "pickup_observed_first_seen_min": seen,
                "reached_before_observed_closure": bool(reached_obs and not aborted),
                "refuge_is_the_pickup_node": bool(refuge == home),
                "delivered_after_horizon": bool(arrival + T_LOAD + eg.total_time_min > HORIZON),
                "ingress_inadmissible_m0":
                    ing_d["observed"]["class_m0"] == "inadmissible_all",
                "egress_inadmissible_m0":
                    eg_d["observed"]["class_m0"] == "inadmissible_all",
            }
            trips.append(trip)
            trips_all.append(trip)
            start = refuge
            dep = free_at
        per_vehicle.append({
            "vehicle": v["id"],
            "depot_index": v["id"] % len(depot_nodes),
            "depot_drive_node": int(depot_nodes[v["id"] % len(depot_nodes)]),
            "n_trips": len(trips), "trips": trips,
            "n_unsafe_egress_legs": len(unsafe_legs), "unsafe_egress_legs": unsafe_legs,
        })

    n = len(trips_all)
    aborted = sum(1 for t in trips_all if t["aborted_by_rule"])
    reached = sum(1 for t in trips_all if t["reached_before_observed_closure"])
    status = {}
    for p in pickups:
        st = outcome[p["drive_node"]]["status"]
        status[st] = status.get(st, 0) + 1

    def tally(leg):
        return {f"m{m}": _classes(trips_all, leg, m) for m in MISS}

    return {
        "vehicles": k, "dispatch_delay_min": DISPATCH,
        "refuges_rescue_reachable": len(refuge_nodes),
        "trips_ordered": n,
        "aborted_by_rule": aborted,
        "reached_before_observed_closure": reached,
        "not_reached": n - aborted - reached,
        "partition_sums_to_trips": n == aborted + reached + (n - aborted - reached),
        "buildings_behind_ordered_trips": sum(t["n_buildings"] for t in trips_all),
        "buildings_behind_reached_trips":
            sum(t["n_buildings"] for t in trips_all if t["reached_before_observed_closure"]),
        "distinct_pickups_ordered": len({t["drive_node"] for t in trips_all}),
        "trips_with_an_inadmissible_ingress_leg_m0":
            sum(1 for t in trips_all if t["ingress_inadmissible_m0"]),
        "trips_with_an_inadmissible_egress_leg_m0":
            sum(1 for t in trips_all if t["egress_inadmissible_m0"]),
        "trips_delivering_at_the_pickup_node":
            sum(1 for t in trips_all if t["refuge_is_the_pickup_node"]),
        "trips_delivered_after_the_horizon":
            sum(1 for t in trips_all if t["delivered_after_horizon"]),
        "unsafe_egress_legs":
            sum(len(v["unsafe_egress_legs"]) for v in per_vehicle),
        "last_delivery_min": (max(t["delivered_min"] for t in trips_all) if trips_all else None),
        "pickup_outcomes": dict(sorted(status.items())),
        "leg_observed_classes": {"ingress": tally("ingress"), "egress": tally("egress")},
        "per_vehicle": per_vehicle,
    }


def _classes(trips, leg, m):
    out: dict[str, int] = {}
    for t in trips:
        c = t[leg]["observed"][f"class_m{m}"]
        out[c] = out.get(c, 0) + 1
    return dict(sorted(out.items()))


def map_layers(sc, z) -> dict:
    """Everything the offline page draws, in EPSG:5179 metres. No tiles, no assets."""
    grid = sc.hazard.grid
    haz = z["haz_stack"].astype(np.float32)
    haz_t = np.asarray(z["haz_times"], float)
    obs = z["obs_stack"]
    obs_t = np.asarray(z["obs_times"], float)

    def sparse_first(stack, times, thresh):
        first = np.full(stack.shape[1:], np.inf)
        for i in range(len(times) - 1, -1, -1):
            first[stack[i] >= thresh] = times[i]
        rows, cols = np.where(np.isfinite(first))
        return [[int(r), int(c), float(first[r, c])] for r, c in zip(rows, cols)]

    edges = []
    seen = set()
    for a, b in sc.drive.graph.edges():
        key = (min(a, b), max(a, b))
        if key in seen:
            continue
        seen.add(key)
        ax, ay = sc.drive.node_xy(a)
        bx, by = sc.drive.node_xy(b)
        edges.append([int(round(ax)), int(round(ay)), int(round(bx)), int(round(by))])
    return {
        "extent": [grid.minx, grid.miny, grid.maxx, grid.maxy],
        "cell_m": grid.cell_size_m, "nrows": grid.nrows, "ncols": grid.ncols,
        "forecast_cutoff_cells": sparse_first(haz, haz_t, 0.7),
        "forecast_walk_cells": sparse_first(haz, haz_t, 0.5),
        "observed_cells": sparse_first(obs, obs_t, 1),
        "roads": edges,
    }


def write_outputs(stamp: str, payload: dict) -> list[str]:
    """Per-vehicle GeoJSON + KML on disk, because a sandboxed viewer cannot download."""
    root = OUTROOT / stamp
    root.mkdir(parents=True, exist_ok=True)
    written = []
    for key, run in payload["runs"].items():
        for veh in run["per_vehicle"]:
            feats = []
            for t in veh["trips"]:
                for leg in ("ingress", "egress"):
                    coords = [list(TO_4326.transform(x, y)) for x, y in t[leg]["xy"]]
                    feats.append({
                        "type": "Feature",
                        "geometry": {"type": "LineString",
                                     "coordinates": [[round(a, 6), round(b, 6)] for a, b in coords]},
                        "properties": {"leg": leg, "vehicle": veh["vehicle"], "seq": t["seq"],
                                       "drive_node": t["drive_node"], "n_buildings": t["n_buildings"],
                                       "eta_min": t["eta_min"], "abort_min": t["abort_min"],
                                       "aborted_by_rule": t["aborted_by_rule"],
                                       "closing_min": t[leg]["closing_min"]},
                    })
                lon, lat = TO_4326.transform(t["x"], t["y"])
                feats.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
                    "properties": {"kind": "pickup", "vehicle": veh["vehicle"], "seq": t["seq"],
                                   "drive_node": t["drive_node"], "n_buildings": t["n_buildings"],
                                   "eta_min": t["eta_min"], "abort_min": t["abort_min"]},
                })
            base = f"{key}_vehicle{veh['vehicle']}"
            gj = {"type": "FeatureCollection", "name": base,
                  "note": payload["label_ko"], "features": feats}
            (root / f"{base}.geojson").write_text(
                json.dumps(gj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            (root / f"{base}.kml").write_text(_kml(base, payload["label_ko"], feats),
                                              encoding="utf-8")
            written += [f"{base}.geojson", f"{base}.kml"]
    (root / "README.md").write_text(
        "# truck_crew_replay " + stamp + "\n\n"
        "Per-vehicle trip geometry for `web/truck_crew_replay.html`, written here because a\n"
        "viewer opened in a sandbox cannot save the file the page offers. Rule and caveats:\n"
        "`docs/truck_crew_replay.md`. Coordinates are WGS84 (EPSG:4326), reprojected from the\n"
        "EPSG:5179 routing geometry. These are model trips on a committed forecast field, not\n"
        "a record of any vehicle movement.\n", encoding="utf-8")
    return sorted(written)


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _kml(name: str, note: str, feats: list[dict]) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
             f"<name>{_esc(name)}</name>", f"<description>{_esc(note)}</description>"]
    for f in feats:
        g = f["geometry"]
        pr = f["properties"]
        label = _esc(f"{pr.get('leg', pr.get('kind'))} v{pr['vehicle']} #{pr['seq']}")
        desc = _esc(json.dumps(pr, ensure_ascii=False))
        if g["type"] == "LineString":
            coords = " ".join(f"{a},{b},0" for a, b in g["coordinates"])
            parts.append(f"<Placemark><name>{label}</name><description>{desc}</description>"
                         f"<LineString><coordinates>{coords}</coordinates></LineString></Placemark>")
        else:
            a, b = g["coordinates"]
            parts.append(f"<Placemark><name>{label}</name><description>{desc}</description>"
                         f"<Point><coordinates>{a},{b},0</coordinates></Point></Placemark>")
    parts.append("</Document></kml>")
    return "\n".join(parts) + "\n"


LABEL_KO = (
    "이 화면은 2025년 3월 25일 영덕 산불의 커밋된 예측장(routing_demo_canonical.npz)과 "
    "2026-07-24 도로망 스냅샷으로 만든 재생(replay)입니다. 실시간 도구가 아니고, 출동 기록도 "
    "아닙니다. 지점은 건물이며 가구가 아닙니다. 규칙과 한계는 docs/truck_crew_replay.md."
)


def render_page(payload: dict) -> None:
    """Substitute the payload into the template. The only writer of web/."""
    tpl = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in tpl:
        raise SystemExit(f"template lacks the payload placeholder: {TEMPLATE}")
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    blob = blob.replace("—", "·").replace("–", "~")   # dash gate, payload side
    PAGE.write_text(tpl.replace(PLACEHOLDER, blob), encoding="utf-8")


def main() -> int:
    if "--render-only" in sys.argv:
        # Re-render the page from the artifact after a template edit, without
        # re-running the routing and without touching the artifact, the outputs
        # directory or the doc. Nothing measured changes.
        render_page(json.loads(OUT.read_text(encoding="utf-8")))
        print(f"re-rendered {PAGE.relative_to(REPO)} from {OUT.relative_to(REPO)} "
              f"({PAGE.stat().st_size/1024:.0f} KiB); no artifact was rewritten")
        return 0
    t0 = time.monotonic()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    tmp = Path(tempfile.mkdtemp(prefix="wfg-tcr-"))
    try:
        prov = materialise_snapshots(tmp / "yeongdeok_2025")
        cfg = RescueConfig(use_osm=True, osm_cache_dir=str(tmp),
                           scan_stride=REAL_OSM_SCAN_STRIDE,
                           responder_time_budget_min=W,
                           responder_dispatch_delay_min=DISPATCH)
        sc = build_scenario(cfg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"[1/6] scenario: drive={sc.drive.graph.number_of_nodes()} nodes, "
          f"walk={sc.walk.graph.number_of_nodes()}, refuges={len(sc.destinations)}, "
          f"depots={len(sc.depots)}", flush=True)

    z = np.load(NPZ)
    fs, tobs = first_seen_grid(z)
    depot_nodes = [int(sc.drive.nearest_node(d.x, d.y)) for d in sc.depots]
    ass = assess_destinations(sc.destinations, sc.drive, depot_nodes, sc.hazard, cfg)
    refuge_nodes = sorted({a.node for a in ass if a.rescue_reachable})

    pickups, pop = build_population(sc, cfg)
    grading_inputs = json.loads(GRADING.read_text(encoding="utf-8"))["inputs"]
    grid = sc.hazard.grid
    obs_first: dict[int, float] = {}
    outside = 0
    for p in pickups:
        rc = _cell(grid, p["x"], p["y"])
        if rc is None:
            outside += 1
            p["cell"] = None
            p["observed_first_seen_min"] = None
            continue
        p["cell"] = [rc[0], rc[1]]
        v = fs[rc]
        p["observed_first_seen_min"] = None if not math.isfinite(v) else float(v)
        if math.isfinite(v):
            obs_first[p["drive_node"]] = float(v)
    pop["pickups_outside_hazard_grid"] = outside
    pop["pickups_ever_detected"] = len(obs_first)
    print(f"[2/6] population: {pop['rescue_needing_walk_nodes']} rescue-needing walk nodes "
          f"-> {pop['pickups']} pickups, {pop['buildings_behind_pickups']} buildings", flush=True)

    runs = {}
    for k in FLEETS:
        tk = time.monotonic()
        runs[f"k{k}"] = run_fleet(sc, cfg, pickups, refuge_nodes, depot_nodes, k,
                                  fs, tobs, obs_first)
        r = runs[f"k{k}"]
        print(f"[3/6] k={k}: ordered {r['trips_ordered']}, reached {r['reached_before_observed_closure']}, "
              f"aborted {r['aborted_by_rule']}, not reached {r['not_reached']} "
              f"({time.monotonic()-tk:.0f}s)", flush=True)

    head = runs["k4"]
    success_ko = (
        f"2025년 3월 25일 영덕 실제 화재에서, 이 화면이 {head['vehicles']}대의 차량에 내린 "
        f"{head['trips_ordered']}건의 출동 지시 중 {head['reached_before_observed_closure']}건은 "
        f"위성이 관측한 화선이 도달하기 전에 도착했고, {head['aborted_by_rule']}건은 이 화면이 "
        "스스로 중단 규칙으로 취소했다."
    )
    payload = {
        "schema_version": 1,
        "title": "Truck-crew replay of the 2025-03-25 영덕 fire (build brief TRUCK_CREW_REPLAY)",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stamp": stamp,
        "git_commit": _git(),
        "rule_doc": "docs/truck_crew_replay.md §1-§3 (pre-registered)",
        "label_ko": LABEL_KO,
        "inputs": {
            "hazard_npz": str(NPZ.relative_to(REPO)),
            "hazard_npz_sha256": hashlib.sha256(NPZ.read_bytes()).hexdigest(),
            "population": str(GRADING.relative_to(REPO)),
            # the building layer the population artifact itself names, read from it
            # rather than restated here, so this script cannot drift from its input
            "buildings": grading_inputs.get("buildings"),
            "snapshots": prov,
        },
        "parameters": {
            "horizon_min": HORIZON, "fleets": list(FLEETS), "dispatch_delay_min": DISPATCH,
            "responder_budget_min": W, "safety_margin_min": MARGIN,
            "t_load_min": T_LOAD, "t_unload_min": T_UNLOAD,
            "vehicle_cutoff": cfg.vehicle_cutoff, "walk_cutoff": cfg.walk_cutoff,
            "ingress_sample_spacing_m": cfg.ingress_sample_spacing_m,
            "miss_allowances": list(MISS),
            "doctrine_markers_min": list(MARKERS_MIN),
            "scheduler": "scripts/run_vehicle_pickup_intervention.py::schedule (imported unchanged)",
            "grader": "scripts/regrade_three_way.py::classify_route (imported unchanged, "
                      "observation clock shifted by the trip departure minute, docs §3 A6')",
            "abort_rule": "arrival > ingress corridor closing minute - 12 min",
        },
        "population": pop,
        "depots": [{"index": i, "name": d.name, "x": round(d.x, 1), "y": round(d.y, 1),
                    "drive_node": depot_nodes[i]} for i, d in enumerate(sc.depots)],
        "depot_distinct_drive_nodes": sorted(set(depot_nodes)),
        "refuges": [{"name": a.name, "node": int(a.node), "x": round(a.x, 1),
                     "y": round(a.y, 1), "rescue_reachable": bool(a.rescue_reachable)}
                    for a in ass],
        "pickups": pickups,
        "runs": runs,
        "success_line_ko": success_ko,
        "map": map_layers(sc, z),
        "caveats": [
            "buildings are not households; a pickup is a road point, not a door",
            "the immobile draw is a modelling assumption (fraction 0.3, seed 20250603), "
            "not a register of who cannot walk",
            "the deadline is the committed forecast's, not the fire's",
            "the observation is FIRMS at 500 m at six times, graded under A1-A6 of "
            "docs/regrade_three_way.md with A6' for the trip departure minute",
            "one pickup per trip; no capacity in persons, no queues, no traffic",
            "영덕 only, one fire, one field; nothing here transfers without being run again",
            "the 5 h / 8 h markers are doctrine lead times drawn on a forward clock, "
            "not a zoning and not a registered figure",
        ],
        "seconds": round(time.monotonic() - t0, 1),
    }

    OUT.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[4/6] wrote {OUT.relative_to(REPO)} ({OUT.stat().st_size/1024:.0f} KiB)", flush=True)

    files = write_outputs(stamp, payload)
    print(f"[5/6] wrote {len(files)} file(s) under outputs/truck_crew_replay/{stamp}/", flush=True)

    render_page(payload)
    print(f"[6/6] wrote {PAGE.relative_to(REPO)} ({PAGE.stat().st_size/1024:.0f} KiB)", flush=True)

    lines = append_results(payload, files, stamp)
    print("\n".join(lines))
    return 0


def append_results(payload: dict, files: list[str], stamp: str) -> list[str]:
    p, runs = payload["population"], payload["runs"]
    head = runs["k4"]
    L = ["", f"_Run {payload['generated_utc']} at `{payload['git_commit'][:7]}`; artifacts "
             f"`data/processed/truck_crew_replay_yeongdeok.json`, `web/truck_crew_replay.html`, "
             f"`outputs/truck_crew_replay/{stamp}/` ({len(files)} files); "
             f"{payload['seconds']:.0f} s._", "",
         f"**Population.** {p['rescue_needing_walk_nodes']} rescue-needing walk nodes "
         f"({p['no_safe_walk_nodes']} in the no-safe-walk class, {p['immobile_draw_nodes']} in the "
         f"immobile draw, overlapping) out of {p['building_walk_nodes']} building walk nodes; they "
         f"snap onto **{p['pickups']} pickups** (road points) carrying "
         f"{p['buildings_behind_pickups']} buildings. {p['walk_nodes_sharing_a_pickup']} walk nodes "
         f"share a pickup with another. {p['pickups_ever_detected']} of the pickups stand in a cell "
         f"FIRMS ever detected.", "",
         "| fleet | trips ordered | reached before observed closure | not reached | aborted by rule | "
         "buildings behind ordered trips | last delivery (min) |", "|---|---:|---:|---:|---:|---:|---:|"]
    for key in ("k2", "k4", "k6"):
        r = runs[key]
        L.append(f"| {r['vehicles']} | {r['trips_ordered']} | {r['reached_before_observed_closure']} | "
                 f"{r['not_reached']} | {r['aborted_by_rule']} | {r['buildings_behind_ordered_trips']} | "
                 f"{r['last_delivery_min']} |")
    L += ["", f"**The count the success line does not carry.** At k = 4, "
              f"{head['trips_with_an_inadmissible_ingress_leg_m0']} of the "
              f"{head['trips_ordered']} ordered trips drove an ingress corridor that passes "
              f"through a cell the observation says was already detected by the time the "
              f"vehicle was in it (`inadmissible_all`, m = 0), and "
              f"{head['trips_with_an_inadmissible_egress_leg_m0']} did so on the way out. "
              f"「Reached before the observed closure」 is a statement about the pickup's own "
              f"cell and says nothing about the road the vehicle took to get there. The two "
              f"counts travel together or neither is quoted.", "",
          f"{head['trips_delivering_at_the_pickup_node']} of the ordered trips deliver to a "
          f"refuge that snaps to the pickup's own road node, so their egress leg is zero "
          f"minutes long; {head['trips_delivered_after_the_horizon']} complete their delivery "
          f"after minute 720, because the deadline binds the arrival at the pickup and not "
          f"the end of the round trip (§2).", "",
          f"Pickup outcomes at k = 4 (the scheduler's own classes over all "
              f"{p['pickups']} pickups): "
              + ", ".join(f"{k} {v}" for k, v in head["pickup_outcomes"].items()) + ".", "",
          "Observed class of the ordered trips' legs at k = 4 (A1 to A6 plus A6', "
          "docs/regrade_three_way.md §2):", ""]
    for leg in ("ingress", "egress"):
        for m in MISS:
            c = head["leg_observed_classes"][leg][f"m{m}"]
            L.append(f"- {leg}, m = {m}: " + ", ".join(f"{k} {v}" for k, v in c.items()))
    L += ["", "**Success line, filled with the measured numbers (k = 4):**", "",
          "「" + payload["success_line_ko"] + "」", "",
          "The three numbers in that sentence are `trips_ordered`, "
          "`reached_before_observed_closure` and `aborted_by_rule` of the `k4` run in the "
          "artifact, defined in §3 before the run. Nothing in it is registered in "
          "`docs/NUMBERS.json` and nothing in it is on a judge-facing surface."]
    DOC.write_text(DOC.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(L) + "\n",
                   encoding="utf-8")
    return L


if __name__ == "__main__":
    raise SystemExit(main())
