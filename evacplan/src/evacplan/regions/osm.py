"""OpenStreetMap road graphs through osmnx -> evacplan :class:`~evacplan.schema.RoadGraph`.

Conventions (the router study graphs', map 01 section 12, except where noted):

* drivable roads (osmnx ``network_type="drive"``), simplified; only the largest strongly connected
  component is kept (every site can reach every other);
* projected to the hazard CRS (EPSG:3310, California Albers, for US region 1); node coordinates
  rounded to 1 cm; edge geometry = the OSM polyline (the router used straight chords; evacplan
  checks the polyline), its end vertices snapped to the nodes;
* ``travel_time_s = ceil(polyline length / speed)``, whole seconds, with the router's assumed
  40 km/h (``speed="fixed"``) or osmnx's speed imputation from ``maxspeed``/highway type
  (``speed="osm"``);
* U-turns (an edge followed by the reverse edge of the same OSM way) are forbidden except at dead
  ends; explicit OSM turn restrictions are NOT loaded (osmnx does not parse restriction relations);
* waiting only at dead ends and at the given site nodes (depots, facilities, shelters);
* provenance keeps "(c) OpenStreetMap contributors, ODbL 1.0".
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from ..schema import Edge, Node, RoadGraph
from . import BuildBlocked, Missing

OSM_HOST = "overpass-api.de"
ATTRIBUTION = "Road data (c) OpenStreetMap contributors, ODbL 1.0"
MAJOR_HIGHWAYS = frozenset({"motorway", "trunk", "primary", "motorway_link", "trunk_link", "primary_link"})


def download_drive_graph(bbox_lonlat: tuple[float, float, float, float]):
    """``osmnx.graph_from_bbox(bbox=(west, south, east, north), network_type="drive")`` (needs the
    Overpass API host)."""
    import osmnx as ox
    try:
        return ox.graph_from_bbox(bbox=tuple(float(v) for v in bbox_lonlat), network_type="drive", simplify=True,
                                  retain_all=False, truncate_by_edge=True)
    except Exception as exc:  # noqa: BLE001 - any download failure blocks the build
        raise BuildBlocked([Missing("OSM road graph", f"{ox.settings.overpass_url} ({OSM_HOST}) is unreachable "
                                    f"({type(exc).__name__}: {exc}); or pass --graph FILE.graphml")]) from exc


def load_graph_file(path):
    """A GraphML saved by ``osmnx.save_graphml`` (preferred), or an OSM XML file already filtered
    to drivable ways."""
    import osmnx as ox
    p = Path(path)
    if p.suffix.lower() == ".graphml":
        return ox.load_graphml(p)
    if p.suffix.lower() in (".osm", ".xml"):
        return ox.graph_from_xml(p, simplify=True, retain_all=False)
    raise ValueError(f"{p}: expected a .graphml or .osm file")


def _crs_epsg(crs) -> int | None:
    if crs is None:
        return None
    try:
        from pyproj import CRS
        return CRS.from_user_input(crs).to_epsg()
    except Exception:  # noqa: BLE001
        return None


def _osmid(v) -> tuple:
    return tuple(sorted(v)) if isinstance(v, (list, tuple, set)) else (v,)


def _highway(v) -> str:
    if isinstance(v, (list, tuple)):
        return ",".join(sorted(str(x) for x in v))
    return "" if v is None else str(v)


def to_road_graph(G, *, crs_epsg: int = 3310, speed_kmh: float = 40.0, speed: str = "fixed",
                  waitable_nodes=(), provenance: dict | None = None) -> tuple[RoadGraph, dict]:
    """Convert an osmnx MultiDiGraph. Returns ``(road graph, info)``; ``info`` has the OSM
    highway class per edge id (``highway``) and what was dropped."""
    import networkx as nx
    import osmnx as ox
    if speed not in ("fixed", "osm"):
        raise ValueError("speed must be 'fixed' or 'osm'")
    if _crs_epsg(G.graph.get("crs")) != crs_epsg:
        G = ox.project_graph(G, to_crs=f"EPSG:{crs_epsg}")
    comps = sorted(nx.strongly_connected_components(G), key=lambda c: (-len(c), min(str(n) for n in c)))
    keep = comps[0] if comps else set()
    H = G.subgraph(keep).copy()
    if speed == "osm":
        H = ox.add_edge_speeds(H, fallback=speed_kmh)

    def nid(n) -> str:
        return f"osm:{n}"

    xy = {n: (round(float(d["x"]), 2), round(float(d["y"]), 2)) for n, d in H.nodes(data=True)}
    neigh: dict = {n: set() for n in H.nodes}
    for u, v in H.edges():
        if u != v:
            neigh[u].add(v)
            neigh[v].add(u)
    dead = {n for n, s in neigh.items() if len(s) == 1}
    sites = {nid(n) if not str(n).startswith("osm:") else str(n) for n in waitable_nodes}
    nodes = [Node(id=nid(n), x=xy[n][0], y=xy[n][1], waitable=(n in dead or nid(n) in sites))
             for n in sorted(H.nodes, key=str)]
    edges: list[Edge] = []
    highway: dict[str, str] = {}
    ways: dict[tuple, list[str]] = {}
    loops = 0
    for u, v, k, d in sorted(H.edges(keys=True, data=True), key=lambda e: (str(e[0]), str(e[1]), e[2])):
        if u == v:
            loops += 1
            continue
        if "geometry" in d and d["geometry"] is not None:
            pts = [(round(float(x), 2), round(float(y), 2)) for x, y in d["geometry"].coords]
        else:
            pts = [xy[u], xy[v]]
        pts[0], pts[-1] = xy[u], xy[v]
        pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
        if len(pts) == 1:
            pts = [xy[u], xy[v]]
        a = np.asarray(pts, dtype=float)
        length = float(np.sum(np.hypot(*np.diff(a, axis=0).T))) if len(a) > 1 else 0.0
        kph = float(d.get("speed_kph", speed_kmh)) if speed == "osm" else float(speed_kmh)
        eid = f"osm:{u}>{v}#{k}"
        edges.append(Edge(id=eid, u=nid(u), v=nid(v), travel_time_s=float(max(1, math.ceil(length / (kph / 3.6)))),
                          geometry=pts if len(pts) > 2 else None))
        highway[eid] = _highway(d.get("highway"))
        ways.setdefault((u, v, _osmid(d.get("osmid"))), []).append(eid)
    turns = []
    for (u, v, osmid), ids in sorted(ways.items(), key=lambda kv: str(kv[0])):
        back = ways.get((v, u, osmid), [])
        if v in dead:
            continue
        turns.extend((a, b) for a in ids for b in back)
    prov = {
        "source": "OpenStreetMap via osmnx", "attribution": ATTRIBUTION, "license": "ODbL 1.0",
        "osmnx_version": ox.__version__, "crs_epsg": crs_epsg, "speed": speed, "speed_kmh": speed_kmh,
        "travel_time": "ceil(polyline length / speed), whole seconds",
        "turns": "U-turns on the same OSM way forbidden except at dead ends; OSM turn restrictions not loaded",
        "waitable": "dead ends and site nodes", "kept": "largest strongly connected component",
        **(provenance or {}),
    }
    info = {"highway": highway, "dropped_nodes": G.number_of_nodes() - H.number_of_nodes(),
            "dropped_edges": G.number_of_edges() - H.number_of_edges(), "self_loops": loops}
    return RoadGraph(crs_epsg=crs_epsg, nodes=nodes, edges=edges, forbidden_turns=turns, provenance=prov), info


def with_waitable(graph: RoadGraph, node_ids) -> RoadGraph:
    """The same graph with these nodes made waitable (sites with off-road parking)."""
    ids = set(node_ids)
    return graph.model_copy(update={"nodes": [n.model_copy(update={"waitable": n.waitable or n.id in ids})
                                              for n in graph.nodes]})


def nearest_node(graph: RoadGraph, x: float, y: float) -> tuple[str, float]:
    ids = [n.id for n in graph.nodes]
    pts = np.array([(n.x, n.y) for n in graph.nodes])
    d = np.hypot(pts[:, 0] - x, pts[:, 1] - y)
    i = int(np.argmin(d))
    return ids[i], float(d[i])
