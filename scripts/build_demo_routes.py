#!/usr/bin/env python
"""Compute the 영덕 route-divergence geometry for the demo — from committed inputs.

The predicted spread_v2 fire front is FIRMS-locked (git-ignored bundle absent), so
this script does NOT invent it. Instead it demonstrates the *routing method* on:

  • the REAL 영덕 pedestrian road network (OpenStreetMap via OSMnx — the brief
    explicitly sanctions re-pulling this independently of the FIRMS bundle), and
  • the committed OBSERVED-APPROXIMATE fire perimeter isochrones
    (``data/validation_cases/yeongdeok_2025_perimeter_approx.geojson`` — an ellipse
    reconstruction from public reporting, clearly labelled; NOT the spread_v2 model).

It computes two routes with the SAME two policies as
``src/wildfireguardian/routing/evacuation.py``:
  • naive (fire-blind): least-walk-time path to the nearest coastal safe node,
    ignoring the fire — then evaluated against the front;
  • future-aware: the same objective but every node the front reaches at or before
    the evacuee could arrive there is forbidden (the moving-front avoidance).

Elderly walking speed 0.7 m/s (Tobler-family flat speed, as in evacuation.py).
Deterministic: fixed safe/candidate bands and a documented origin-selection rule
(seed 20250603 is carried for provenance; no randomness is used).

The projected walk graph is cached to ``data/processed/demo_yeongdeok_walk.graphml``
so the whole thing re-runs OFFLINE (no network) once committed. Output:
``data/processed/demo_geometry.json`` (raw EPSG:5179 + normalized [0,1]^2 + sources).

Run:  python scripts/build_demo_routes.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import networkx as nx
import osmnx as ox
from pyproj import Transformer
from shapely.geometry import Point, Polygon

REPO = Path(__file__).resolve().parents[1]
PROC = REPO / "data" / "processed"
PERIM = REPO / "data" / "validation_cases" / "yeongdeok_2025_perimeter_approx.geojson"
GRAPHML = PROC / "demo_yeongdeok_walk.graphml"
OUT = PROC / "demo_geometry.json"

SEED = 20250603
ELDERLY_SPEED_MS = 0.7          # matches evacuation.ELDERLY_FLAT_SPEED_MS
BBOX_WGS84 = (129.30, 36.44, 129.46, 36.56)   # west, south, east, north (fire + coast)
SAFE_EAST_QUANTILE = 0.93       # easternmost band = coastal assembly direction
CAND_WEST_QUANTILE = 0.12       # candidate origins on the upwind (west) side

ox.settings.use_cache = True
ox.settings.cache_folder = str(REPO / "data" / "cache" / "osm")
ox.settings.log_console = False

TO5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)


def load_fronts():
    """Committed observed-approx perimeter -> list of {t_min, area_ha, poly(5179)}."""
    perim = json.loads(PERIM.read_text())
    rings = []
    for f in perim["features"]:
        g = f["geometry"]
        ext = g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0]
        xy = [TO5179.transform(lon, lat) for lon, lat in ext]
        rings.append({"t_min": float(f["properties"]["time_min_since_ignition"]),
                      "area_ha": float(f["properties"]["area_ha"]),
                      "xy": xy, "poly": Polygon(xy)})
    rings.sort(key=lambda r: r["t_min"])
    return rings


def load_graph():
    """Load the projected walk graph from committed graphml, else pull from OSM + save."""
    if GRAPHML.exists():
        G = ox.load_graphml(GRAPHML)
        # graphml stringifies attrs; restore floats we need.
        for _, d in G.nodes(data=True):
            d["x"] = float(d["x"]); d["y"] = float(d["y"])
        for _, _, d in G.edges(data=True):
            d["length"] = float(d.get("length", 1.0))
        return G, "cached graphml (offline)"
    w, s, e, n = BBOX_WGS84
    G = ox.graph_from_bbox(bbox=(w, s, e, n), network_type="walk", simplify=True)
    G = ox.project_graph(G, to_crs="EPSG:5179")
    ox.save_graphml(G, GRAPHML)
    return G, "OpenStreetMap via OSMnx (fresh pull), projected to EPSG:5179, cached"


def front_arrival(rings, x, y):
    """Earliest ring t_min whose polygon contains the point (inf if never burned)."""
    p = Point(x, y)
    for r in rings:
        if r["poly"].contains(p):
            return r["t_min"]
    return math.inf


def path_enters_front(UG, arr, path):
    """Walk the path accumulating time; True if a node is reached at/after the
    front has arrived there. Returns (enters, node, cumulative_min)."""
    t = 0.0
    prev = None
    for nd in path:
        if prev is not None:
            t += UG[prev][nd]["t"]
        if arr[nd] <= t:
            return True, nd, t
        prev = nd
    return False, None, t


def main() -> int:
    rings = load_fronts()
    final_poly = rings[-1]["poly"]
    ign = TO5179.transform(129.37, 36.50)

    G, graph_src = load_graph()
    xy = {nd: (d["x"], d["y"]) for nd, d in G.nodes(data=True)}
    arr = {nd: front_arrival(rings, x, y) for nd, (x, y) in xy.items()}

    # undirected walk-time graph (elderly speed)
    UG = nx.Graph()
    for u, v, d in G.edges(data=True):
        t = (float(d.get("length", 1.0)) / ELDERLY_SPEED_MS) / 60.0
        if UG.has_edge(u, v):
            UG[u][v]["t"] = min(UG[u][v]["t"], t)
        else:
            UG.add_edge(u, v, t=t)

    xs = sorted(x for x, _ in xy.values())
    east_cut = xs[int(len(xs) * SAFE_EAST_QUANTILE)]
    west_cut = xs[int(len(xs) * CAND_WEST_QUANTILE)]
    safe = [nd for nd, (x, y) in xy.items() if x >= east_cut and arr[nd] == math.inf]
    safe_set = set(safe)

    def nearest_safe(origin, graph):
        if origin not in graph:
            return None
        lengths, paths = nx.single_source_dijkstra(graph, origin, weight="t")
        best = None
        for s in safe_set:
            if s in lengths and (best is None or lengths[s] < best[0]):
                best = (lengths[s], paths[s], s)
        return best

    def future_route(origin):
        tt, _ = nx.single_source_dijkstra(UG, origin, weight="t")   # earliest possible arrival
        allowed = {nd for nd in UG.nodes
                   if arr[nd] == math.inf or arr[nd] > tt.get(nd, math.inf)}
        if origin not in allowed:
            return None
        return nearest_safe(origin, UG.subgraph(allowed))

    # candidate origins: upwind (west) side, not already burned, reach a safe node
    cands = sorted(nd for nd, (x, y) in xy.items()
                   if x <= max(west_cut, final_poly.bounds[0]) and arr[nd] == math.inf)

    chosen = None
    for o in cands:
        nv = nearest_safe(o, UG)
        if not nv:
            continue
        enters, fail_node, fail_t = path_enters_front(UG, arr, nv[1])
        if not enters:
            continue                       # naive must FAIL (walk into the fire)
        fa = future_route(o)
        if not fa:
            continue
        fa_enters, _, _ = path_enters_front(UG, arr, fa[1])
        if fa_enters:
            continue                       # future-aware must be CLEAN
        detour = fa[0] - nv[0]
        cand = {"origin": o, "naive": nv, "fa": fa, "detour": detour,
                "fail_node": fail_node, "fail_t": fail_t}
        # Deterministic selection rule: the most consequential case — largest
        # extra walk-time the fire-blindness would cost (detour), tie-break by
        # lowest OSM node id. No randomness.
        if chosen is None or (detour, -o) > (chosen["detour"], -chosen["origin"]):
            chosen = cand

    if chosen is None:
        print("NO divergence origin found — aborting (would not fabricate one).")
        return 2

    o = chosen["origin"]
    nv_t, nv_path, nv_safe = chosen["naive"]
    fa_t, fa_path, fa_safe = chosen["fa"]
    fail_node, fail_t = chosen["fail_node"], chosen["fail_t"]

    # ---- shared normalization frame: fronts + routes + origin + safe nodes ----
    pts = []
    for r in rings:
        pts += r["xy"]
    pts += [xy[n] for n in nv_path] + [xy[n] for n in fa_path]
    minx = min(p[0] for p in pts); maxx = max(p[0] for p in pts)
    miny = min(p[1] for p in pts); maxy = max(p[1] for p in pts)
    padx = (maxx - minx) * 0.06; pady = (maxy - miny) * 0.06
    bbox = (minx - padx, miny - pady, maxx + padx, maxy + pady)

    def norm(x, y):
        nx_ = (x - bbox[0]) / (bbox[2] - bbox[0])
        ny_ = (y - bbox[1]) / (bbox[3] - bbox[1])
        return [round(nx_, 5), round(1.0 - ny_, 5)]     # flip y for screen

    def norm_path(path):
        return [norm(*xy[n]) for n in path]

    fronts_out = []
    for r in rings:
        fronts_out.append({
            "t_min": r["t_min"], "area_ha": r["area_ha"],
            "t_norm": round(r["t_min"] / rings[-1]["t_min"], 4) if rings[-1]["t_min"] else 0.0,
            "ring": [norm(x, y) for x, y in r["xy"]],
        })

    # committed rescue-demand points + refuges (real OSM 5179) that fall in-frame
    routing = json.loads((PROC / "rescue_routing.json").read_text())

    def in_frame(x, y):
        return bbox[0] <= x <= bbox[2] and bbox[1] <= y <= bbox[3]

    rescue_pts, refuges = [], []
    for h in routing["dispatch_top20"] + routing["unreachable_homes"]:
        if in_frame(h["x"], h["y"]):
            rescue_pts.append(norm(h["x"], h["y"]))
    for d in routing["destinations"]:
        if in_frame(d["x"], d["y"]):
            refuges.append({"xy": norm(d["x"], d["y"]), "safe": bool(d.get("safe")),
                            "rescue_reachable": bool(d.get("rescue_reachable"))})

    geom = {
        "meta": {
            "crs": "EPSG:5179",
            "bbox_5179": [round(v, 1) for v in bbox],
            "seed": SEED,
            "graph_source": graph_src,
            "graph_nodes": G.number_of_nodes(),
            "elderly_speed_ms": ELDERLY_SPEED_MS,
            "front_provenance": ("OBSERVED-APPROXIMATE perimeter (ellipse reconstruction from "
                                 "public reporting), reprojected WGS84->EPSG:5179. NOT the "
                                 "spread_v2 prediction (FIRMS-locked). Used to demonstrate the "
                                 "routing METHOD on real roads."),
            "front_source": "data/validation_cases/yeongdeok_2025_perimeter_approx.geojson",
            "route_method": ("naive = fire-blind least-walk-time to nearest coastal safe node; "
                             "future_aware = same objective, forbidding any node the front reaches "
                             "at/before arrival. Replicates routing/evacuation.py policies."),
            "origin_selection": ("deterministic: among origins where naive enters the front and "
                                 "future-aware stays clean, max detour-minutes, tie-break lowest "
                                 "OSM node id. No randomness."),
            "y_axis": "normalized y flipped for screen (north = up)",
        },
        "fire_fronts": fronts_out,
        "origin": norm(*xy[o]),
        "routes": {
            "naive": {
                "polyline": norm_path(nv_path),
                "reached_coast": True,
                "enters_front": True,
                "fail_point": norm(*xy[fail_node]),
                "fail_time_min": round(fail_t, 1),
                "total_time_min": round(nv_t, 1),
                "destination": norm(*xy[nv_safe]),
                "label": "주민 대피 경로 (화재 예측 없음)",
            },
            "future_aware": {
                "polyline": norm_path(fa_path),
                "reached_coast": True,
                "enters_front": False,
                "total_time_min": round(fa_t, 1),
                "detour_min": round(fa_t - nv_t, 1),
                "destination": norm(*xy[fa_safe]),
                "label": "미래 인지 경로",
            },
        },
        "safe_zone_note": "안전 지대 = 동측 해안 집결 방향 (routing_integration 방법과 동일).",
        "rescue_points_in_frame": {
            "value": rescue_pts,
            "count": len(rescue_pts),
            "provenance": "real OSM 영덕 households needing a rescuer (routing pipeline)",
            "source": "data/processed/rescue_routing.json :: dispatch_top20 + unreachable_homes",
        },
        "refuges_in_frame": {
            "value": refuges,
            "count": len(refuges),
            "source": "data/processed/rescue_routing.json :: destinations (source=osm)",
        },
    }
    OUT.write_text(json.dumps(geom, ensure_ascii=False, indent=2))

    print("=" * 70)
    print("DEMO ROUTE GEOMETRY")
    print("=" * 70)
    print(f"graph          : {graph_src}  ({G.number_of_nodes()} nodes)")
    print(f"fronts         : {len(rings)} observed-approx isochrones (reprojected)")
    print(f"origin node    : {o}  5179={[round(v) for v in xy[o]]}")
    print(f"naive          : {len(nv_path)} nodes, {nv_t:.0f} min, ENTERS front at "
          f"t={fail_t:.0f} min  -> 대피 실패")
    print(f"future_aware   : {len(fa_path)} nodes, {fa_t:.0f} min "
          f"(+{fa_t - nv_t:.0f} min detour), clean -> 대피 성공")
    print(f"rescue pts/ref : {len(rescue_pts)} demand pts, {len(refuges)} refuges in frame")
    print(f"graphml        : {GRAPHML.relative_to(REPO)} "
          f"({GRAPHML.stat().st_size // 1024} KiB)" if GRAPHML.exists() else "")
    print(f"wrote          : {OUT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
