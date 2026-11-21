"""PROTOCOL §1: Paradise road graph from OpenStreetMap (Overpass tiles) in product/wfg-roadlayer RoadModel format.
Usage: python3 -I build_graph_osm.py OUT_graph.json TILE1.json [TILE2.json ...]
Rules as research/kcf-validate/paradise/build_graph.py: EPSG:32610, 375 m cells, free-flow speeds by class, largest
connected component; OSM ways split at shared nodes; two-way unless oneway=yes/true/1 (or -1: reversed); service excluded.
Every edge keeps its OSM name and class so routes can be compared with the documented roads."""
import hashlib, json, math, sys

from pyproj import Transformer

OUT, TILES = sys.argv[1], sys.argv[2:]
RES = 375.0
SPEED_KMH = {"motorway": 100, "trunk": 80, "primary": 70, "secondary": 60, "tertiary": 50, "unclassified": 40, "residential": 30, "living_street": 15}
TO_UTM = Transformer.from_crs(4326, 32610, always_xy=True)

nodes_ll, ways = {}, {}
for p in TILES:
    for el in json.load(open(p))["elements"]:
        if el["type"] == "node":
            nodes_ll[el["id"]] = (el["lon"], el["lat"])
        elif el["type"] == "way":
            ways[el["id"]] = el
print("tiles", len(TILES), "osm ways", len(ways), "osm nodes", len(nodes_ll))
kept = []
for wid, w in sorted(ways.items()):
    tg = w.get("tags", {})
    hw = tg.get("highway", "")
    cl = hw[:-5] if hw.endswith("_link") else hw
    if cl not in SPEED_KMH or any(n not in nodes_ll for n in w["nodes"]) or len(w["nodes"]) < 2:
        continue
    ow = tg.get("oneway", "no")
    direction = "forward" if ow in ("yes", "true", "1") else ("reverse" if ow == "-1" else "both")
    kept.append((wid, cl, hw, tg.get("name") or tg.get("ref") or "", direction, w["nodes"]))
use = {}
for _, _, _, _, _, ns in kept:
    for k, n in enumerate(ns):
        use[n] = use.get(n, 0) + (2 if k in (0, len(ns) - 1) else 1)
xy = {}
for n in use:
    xy[n] = TO_UTM.transform(*nodes_ll[n])
pieces = []  # (wid, k, cl, hw, name, direction, [node ids])
for wid, cl, hw, name, direction, ns in kept:
    cur = [ns[0]]
    k = 0
    for n in ns[1:]:
        cur.append(n)
        if use[n] >= 2 and len(cur) >= 2:
            if cur[0] != cur[-1]:
                pieces.append((wid, k, cl, hw, name, direction, cur))
            k += 1
            cur = [n]
    if len(cur) >= 2 and cur[0] != cur[-1]:
        pieces.append((wid, k, cl, hw, name, direction, cur))
parent = {}
def find(a):
    parent.setdefault(a, a)
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
for p in pieces:
    ra, rb = find(p[6][0]), find(p[6][-1])
    if ra != rb:
        parent[ra] = rb
comp = {}
for p in pieces:
    for n in (p[6][0], p[6][-1]):
        comp.setdefault(find(n), set()).add(n)
big = max(comp.values(), key=len)
pieces = [p for p in pieces if p[6][0] in big and p[6][-1] in big]
gnodes = sorted({n for p in pieces for n in (p[6][0], p[6][-1])})
print("pieces", len(pieces), "graph nodes", len(gnodes), "components", len(comp))
allpts = [xy[n] for p in pieces for n in p[6]]
x0 = math.floor(min(a for a, _ in allpts) / RES) * RES; y0 = math.floor(min(b for _, b in allpts) / RES) * RES
W = int(math.ceil((max(a for a, _ in allpts) - x0) / RES)) + 1; H = int(math.ceil((max(b for _, b in allpts) - y0) / RES)) + 1


def cells_along(co):
    """[(cell, start_frac, end_frac)] of the cells a polyline crosses, by cumulative length (kcf-validate rule)."""
    L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(co[:-1], co[1:]))
    bps = [(0.0, co[0])]
    cum = 0.0
    for (xa, ya), (xb, yb) in zip(co[:-1], co[1:]):
        d = math.hypot(xb - xa, yb - ya)
        if d == 0:
            continue
        ts = {0.0, 1.0}
        for ax, bx, o in ((xa, xb, x0), (ya, yb, y0)):
            if ax != bx:
                lo, hi = sorted((ax, bx))
                kk = math.ceil((lo - o) / RES)
                while o + kk * RES < hi:
                    ts.add((o + kk * RES - ax) / (bx - ax)); kk += 1
        for tt in sorted(ts):
            if 0 < tt <= 1:
                bps.append((cum + tt * d, (xa + tt * (xb - xa), ya + tt * (yb - ya))))
        cum += d
    out = []
    for (s0, p0), (s1, p1) in zip(bps[:-1], bps[1:]):
        if s1 - s0 <= 1e-9:
            continue
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        c = int((my - y0) // RES) * W + int((mx - x0) // RES)
        f0, f1 = s0 / L, s1 / L
        if out and out[-1][0] == c:
            out[-1] = (c, out[-1][1], f1)
        else:
            out.append((c, f0, f1))
    out[-1] = (out[-1][0], out[-1][1], 1.0)
    return out, L


edges, forb = [], []
for n, (wid, k, cl, hw, name, direction, ns) in enumerate(pieces):
    co = [xy[v] for v in ns]
    cs, L = cells_along(co)
    if L < 0.5:
        continue
    ticks = max(1, math.ceil(L / (SPEED_KMH[cl] / 3.6)))
    cs_rev = [(c, 1.0 - e, 1.0 - s) for c, s, e in reversed(cs)]
    ef, er = "w%d.%d:f" % (wid, k), "w%d.%d:r" % (wid, k)
    base = {"travel_ticks": ticks, "source_way": wid, "length_m": round(L, 1), "class": hw, "name": name}
    geom = [[round(a, 1), round(b, 1)] for a, b in co]
    if direction in ("forward", "both"):
        edges.append(dict(base, id=ef, u="osm:%d" % ns[0], v="osm:%d" % ns[-1], reverse_edge=er if direction == "both" else None,
                          segments=[{"cell": c, "start": round(s, 9), "end": round(e, 9)} for c, s, e in cs],
                          direction_evidence="osm_oneway_" + direction, geom=geom))
    if direction in ("reverse", "both"):
        edges.append(dict(base, id=er, u="osm:%d" % ns[-1], v="osm:%d" % ns[0], reverse_edge=ef if direction == "both" else None,
                          segments=[{"cell": c, "start": round(s, 9), "end": round(e, 9)} for c, s, e in cs_rev],
                          direction_evidence="osm_oneway_" + direction, geom=geom[::-1]))
    if direction == "both":
        forb += [[ef, er], [er, ef]]
graph = {"revision": "paradise-osm-overpass-20261121-grid375", "crs": "EPSG:32610",
         "grid": {"x0": x0, "y0": y0, "resolution": RES, "width": W, "height": H},
         "nodes": [{"id": "osm:%d" % n, "x": xy[n][0], "y": xy[n][1], "waitable": False} for n in gnodes],
         "edges": edges, "forbidden_turns": forb, "mid_edge_reversal": False,
         "provenance": {"source": "OpenStreetMap via Overpass API (overpass-api.de), fetched 2026-11-21; present-day network as a proxy for November 2018",
                        "license": "ODbL; https://www.openstreetmap.org/copyright", "speeds_kmh": SPEED_KMH,
                        "assumptions": "two-way unless oneway tag; free-flow speeds by class; no congestion; service roads, tracks, paths excluded"}}
json.dump(graph, open(OUT, "w"))
print("grid", graph["grid"], "nodes", len(graph["nodes"]), "edges", len(edges), "sha256", hashlib.sha256(open(OUT, "rb").read()).hexdigest())
