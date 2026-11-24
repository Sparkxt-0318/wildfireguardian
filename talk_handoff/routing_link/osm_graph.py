"""OpenStreetMap -> road-layer graph (the RoadModel format of product/wfg-roadlayer) on the Fish Creek 375 m grid.

Same mapping rules as the road layer's Korean graphs (their graph.json provenance): adjacent mapped node chords,
40 km/h rounded up to 1 s ticks, missing oneway assumed two-way, private/no-access ways excluded, no mid-edge
reversal, U-turns only at graph dead ends. Differences, stated: CRS EPSG:5070 (the Fish Creek grid's own CRS, not
the Korean EPSG:5179); no node is waitable (the Korean wait-node list cannot be rebuilt from its provenance);
turn restrictions are not encoded (none needed for a chord graph without relations, and none were fetched).

Origins and exits (PROTOCOL.md section 6): populated places from OSM (place = city, town, village, hamlet,
isolated_dwelling, neighbourhood, farm) snapped to the nearest graph node within 2 km. If there are none, road
junctions (graph nodes with three or more distinct neighbours) are the origins. Exits are graph nodes whose OSM way
continues outside the grid (the map edge). Destinations are always the map-edge exits.
"""
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

import numpy as np

DRIVABLE = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service", "track",
            "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "living_street", "road"}
NO_ACCESS = {"private", "no"}
POPULATED = {"city", "town", "village", "hamlet", "isolated_dwelling", "neighbourhood", "farm"}
SPEED_M_S = 40.0 / 3.6
SNAP_MAX_M = 2000.0


class Grid:
    """North-up raster grid (pipeline orientation) and the router's south-up cell numbering."""

    def __init__(self, transform, width, height, epsg):
        a, _, c, _, e, f = transform
        self.res, self.W, self.H, self.epsg = float(a), int(width), int(height), int(epsg)
        self.x0, self.ytop = float(c), float(f)
        self.y0 = self.ytop + e * self.H  # bottom edge (e < 0)
        self.affine = (float(a), 0.0, float(c), 0.0, float(e), float(f))

    @classmethod
    def from_json(cls, p):
        g = json.loads(Path(p).read_text())
        return cls(g["transform"], g["width"], g["height"], g["epsg"])

    def inside(self, x, y):
        return self.x0 < x < self.x0 + self.W * self.res and self.y0 < y < self.y0 + self.H * self.res

    def cell(self, x, y):
        c = int(math.floor((x - self.x0) / self.res))
        r = int(math.floor((y - self.y0) / self.res))
        return r * self.W + c

    def router_to_raster(self, cell):
        r, c = divmod(int(cell), self.W)
        return self.H - 1 - r, c

    def raster_to_router_cells(self, arr):
        """{router cell: value} for a north-down [H, W] array."""
        a = np.asarray(arr)
        return {(self.H - 1 - rr) * self.W + cc: a[rr, cc] for rr in range(self.H) for cc in range(self.W)}

    def json(self):
        return {"x0": self.x0, "y0": self.y0, "resolution": self.res, "width": self.W, "height": self.H}


def chord_segments(grid, p, q):
    """Cells crossed by the straight chord p -> q with the travel fraction at which each piece ends."""
    (x1, y1), (x2, y2) = p, q
    ts = {0.0, 1.0}
    for k in range(grid.W + 1):
        xl = grid.x0 + k * grid.res
        if (x1 - xl) * (x2 - xl) < 0:
            ts.add((xl - x1) / (x2 - x1))
    for k in range(grid.H + 1):
        yl = grid.y0 + k * grid.res
        if (y1 - yl) * (y2 - yl) < 0:
            ts.add((yl - y1) / (y2 - y1))
    ts = sorted(ts)
    segs = []
    for a, b in zip(ts[:-1], ts[1:]):
        if b - a < 1e-12:
            continue
        m = (a + b) / 2
        cell = grid.cell(x1 + m * (x2 - x1), y1 + m * (y2 - y1))
        if segs and segs[-1]["cell"] == cell:
            segs[-1]["end"] = b
        else:
            segs.append({"cell": cell, "start": a, "end": b})
    segs[-1]["end"] = 1.0
    return segs


def build(osm_json, grid_json, snapshot_utc):
    from pyproj import Transformer

    grid = Grid.from_json(grid_json)
    p = Path(osm_json)
    osm = json.loads(gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_text())
    tr = Transformer.from_crs("EPSG:4326", "EPSG:%d" % grid.epsg, always_xy=True)
    lonlat = {e["id"]: (e["lon"], e["lat"]) for e in osm["elements"] if e["type"] == "node" and "lon" in e}
    xy = {}

    def P(n):
        if n not in xy:
            xy[n] = tr.transform(*lonlat[n])
        return xy[n]

    ways = [e for e in osm["elements"] if e["type"] == "way" and e.get("tags", {}).get("highway") in DRIVABLE]
    edges, used, exits, nbrs = [], set(), set(), {}
    excluded = {"no_access": 0}
    for w in ways:
        t = w["tags"]
        if t.get("access") in NO_ACCESS or t.get("motor_vehicle") in NO_ACCESS or t.get("motorcar") in NO_ACCESS:
            excluded["no_access"] += 1
            continue
        ow = t.get("oneway")
        fwd = rev = True
        evid = "missing_oneway_assumed_two_way" if ow is None else "oneway=%s" % ow
        if ow in ("yes", "true", "1") or t.get("junction") == "roundabout":
            rev = False
        elif ow == "-1":
            fwd = False
        nd = [n for n in w["nodes"] if n in lonlat]
        for k, (a, b) in enumerate(zip(nd[:-1], nd[1:])):
            if a == b:
                continue
            pa, pb = P(a), P(b)
            ia, ib = grid.inside(*pa), grid.inside(*pb)
            if ia and not ib:
                exits.add(a)
            if ib and not ia:
                exits.add(b)
            if not (ia and ib):
                continue
            L = math.dist(pa, pb)
            ticks = max(1, math.ceil(L / SPEED_M_S - 1e-9))
            segs = chord_segments(grid, pa, pb)
            used.update((a, b))
            nbrs.setdefault(a, set()).add(b)
            nbrs.setdefault(b, set()).add(a)
            base = "w%d:s%d" % (w["id"], k)
            f_id, r_id = base + ":f", base + ":r"
            if fwd:
                edges.append({"id": f_id, "u": "osm:%d" % a, "v": "osm:%d" % b, "travel_ticks": ticks,
                              "reverse_edge": r_id if rev else None, "segments": segs, "source_way": w["id"],
                              "highway": t["highway"], "length_m": round(L, 2), "direction_evidence": evid})
            if rev:
                rsegs = [{"cell": s["cell"], "start": 1 - s["end"], "end": 1 - s["start"]} for s in reversed(segs)]
                rsegs[-1]["end"] = 1.0
                edges.append({"id": r_id, "u": "osm:%d" % b, "v": "osm:%d" % a, "travel_ticks": ticks,
                              "reverse_edge": f_id if fwd else None, "segments": rsegs, "source_way": w["id"],
                              "highway": t["highway"], "length_m": round(L, 2), "direction_evidence": evid})
    exits &= used
    nodes = [{"id": "osm:%d" % n, "x": P(n)[0], "y": P(n)[1], "waitable": False} for n in sorted(used)]
    # U-turns (an edge followed by its own reverse) only where the node is a dead end
    forbidden = []
    deg = {n: len(s) for n, s in nbrs.items()}
    for e in edges:
        r = e["reverse_edge"]
        v = int(e["v"].split(":")[1])
        if r and deg.get(v, 0) > 1:
            forbidden.append([e["id"], r])
    graph = {"revision": "fishcreek-osm-%s-grid375-chord-40kmh" % snapshot_utc[:10].replace("-", ""),
             "crs": "EPSG:%d" % grid.epsg, "grid": grid.json(), "nodes": nodes, "edges": edges,
             "forbidden_turns": forbidden, "mid_edge_reversal": False,
             "provenance": {"source": "OpenStreetMap contributors, Overpass API historical query [date:\"%s\"]" % snapshot_utc,
                            "license": "ODbL; https://www.openstreetmap.org/copyright",
                            "interpretation": "Adjacent mapped node chords; assumed 40km/h rounded up to 1s ticks; missing "
                                              "oneway assumed two-way; private/no-access ways excluded; no mid-edge "
                                              "reversal; U-turns only at graph dead ends; no node waitable; no turn "
                                              "restrictions; highway classes %s" % ",".join(sorted(DRIVABLE)),
                            "excluded": excluded}}
    # places
    places = []
    for e in osm["elements"]:
        tg = e.get("tags", {})
        if e["type"] == "node" and tg.get("place") in POPULATED:
            places.append({"osm": "node/%d" % e["id"], "name": tg.get("name", ""), "place": tg["place"],
                           "lonlat": (e["lon"], e["lat"]), "xy": tr.transform(e["lon"], e["lat"])})
    others = [{"osm": "%s/%d" % (e["type"], e["id"]), "tags": {k: e["tags"][k] for k in ("name", "place", "amenity", "tourism") if k in e["tags"]}}
              for e in osm["elements"] if e.get("tags") and ("place" in e["tags"] or "amenity" in e["tags"] or "tourism" in e["tags"])]
    nid = sorted(used)
    nxy = np.array([P(n) for n in nid]) if nid else np.zeros((0, 2))
    origins, origin_rule = [], None
    for p in places:
        if not grid.inside(*p["xy"]):
            continue
        d = np.hypot(nxy[:, 0] - p["xy"][0], nxy[:, 1] - p["xy"][1])
        i = int(np.argmin(d))
        origins.append({"id": "place:" + p["osm"], "name": p["name"], "category": p["place"], "lonlat": p["lonlat"],
                        "entry_node_id": "osm:%d" % nid[i], "entry_distance_m": round(float(d[i]), 1),
                        "checkable": bool(d[i] <= SNAP_MAX_M)})
    if origins:
        origin_rule = "populated places from OSM (place=%s) snapped to the nearest graph node within 2 km" % "/".join(sorted(POPULATED))
    else:
        origin_rule = ("NO populated place or shelter in the area: road junctions (graph nodes with 3 or more distinct "
                       "neighbours) are the origins, and the map edge gives the exits")
        for n in nid:
            if deg.get(n, 0) >= 3 and n not in exits:
                origins.append({"id": "junction:osm:%d" % n, "name": "", "category": "junction", "lonlat": lonlat[n],
                                "entry_node_id": "osm:%d" % n, "entry_distance_m": 0.0, "checkable": True})
    exit_list = [{"id": "exit:osm:%d" % n, "name": "map edge", "category": "map_edge_exit", "lonlat": lonlat[n],
                  "entry_node_id": "osm:%d" % n, "checkable": True} for n in sorted(exits)]
    meta = {"origin_rule": origin_rule, "exit_rule": "graph nodes whose OSM way continues outside the grid (map edge)",
            "n_places_in_osm": len(places), "osm_tagged_features": others, "snapshot_utc": snapshot_utc}
    return graph, origins, exit_list, meta
