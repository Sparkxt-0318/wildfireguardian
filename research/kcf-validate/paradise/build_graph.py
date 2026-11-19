"""Build a Paradise/Chico road graph in the format of product/wfg-roadlayer's RoadModel (PROTOCOL.md amendment 9).
Usage: python3 -I build_graph.py SEGMENTS.parquet OUT_graph.json
Overture segments (subtype road; classes motorway..living_street), split at connectors; two-way; free-flow speeds by class; EPSG:32610; 375 m grid."""
import hashlib, json, math, sys

import pyarrow.parquet as pq
import shapely
from pyproj import Transformer
from shapely.geometry import LineString
from shapely.ops import substring

SEG, OUT = sys.argv[1], sys.argv[2]
RES = 375.0
SPEED_KMH = {"motorway": 100, "trunk": 80, "primary": 70, "secondary": 60, "tertiary": 50, "unclassified": 40, "residential": 30, "living_street": 15}
TO_UTM = Transformer.from_crs(4326, 32610, always_xy=True)

t = pq.read_table(SEG, columns=["id", "class", "subtype", "connectors", "geometry"])
segs = []
for sid, cl, st, cn, g in zip(t.column("id").to_pylist(), t.column("class").to_pylist(), t.column("subtype").to_pylist(),
                              t.column("connectors").to_pylist(), t.column("geometry").to_pylist()):
    if st != "road" or cl not in SPEED_KMH or not cn or len(cn) < 2:
        continue
    geom = shapely.from_wkb(g)
    if geom.geom_type != "LineString":
        continue
    xs, ys = TO_UTM.transform(*zip(*geom.coords))
    line = LineString(list(zip(xs, ys)))
    if line.length < 1.0:
        continue
    segs.append((sid, cl, cn, line))
print("segments used", len(segs))

# nodes: connector id -> (x, y)
nodes = {}
pieces = []  # (sid, k, class, u, v, sublinestring)
for sid, cl, cn, line in segs:
    cs = sorted({round(c["at"], 9): c["connector_id"] for c in cn}.items())
    pts = []
    for at, cid in cs:
        p = line.interpolate(at, normalized=True)
        nodes.setdefault(cid, (p.x, p.y))
        pts.append((at, cid))
    for k in range(len(pts) - 1):
        (a0, u), (a1, v) = pts[k], pts[k + 1]
        if u == v or a1 <= a0:
            continue
        sub = substring(line, a0, a1, normalized=True)
        if sub.geom_type != "LineString" or sub.length < 0.5:
            continue
        pieces.append((sid, k, cl, u, v, sub))
print("pieces", len(pieces), "nodes", len(nodes))

# largest connected component (two-way graph)
parent = {n: n for n in nodes}
def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
for _, _, _, u, v, _ in pieces:
    ra, rb = find(u), find(v)
    if ra != rb:
        parent[ra] = rb
comp = {}
for n in nodes:
    comp.setdefault(find(n), []).append(n)
big = set(max(comp.values(), key=len))
pieces = [p for p in pieces if p[3] in big and p[4] in big]
used = {n for p in pieces for n in (p[3], p[4])}
nodes = {n: xy for n, xy in nodes.items() if n in used}
print("largest component: nodes", len(nodes), "pieces", len(pieces), "(of", len(comp), "components)")

xs = [xy[0] for xy in nodes.values()]; ys = [xy[1] for xy in nodes.values()]
x0 = math.floor(min(xs) / RES) * RES; y0 = math.floor(min(ys) / RES) * RES
W = int(math.ceil((max(xs) - x0) / RES)) + 1; H = int(math.ceil((max(ys) - y0) / RES)) + 1


def cells_along(line):
    """[(cell, start_frac, end_frac)] of the cells a polyline crosses, by cumulative length."""
    co = list(line.coords)
    L = line.length
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
    return out


edges, forb = [], []
for n, (sid, k, cl, u, v, sub) in enumerate(pieces):
    speed = SPEED_KMH[cl] / 3.6
    ticks = max(1, math.ceil(sub.length / speed))
    cs = cells_along(sub)
    cs_rev = [(c, 1.0 - e, 1.0 - s) for c, s, e in reversed(cs)]
    ef, er = "p%d:f" % n, "p%d:r" % n
    way = int(hashlib.sha1(sid.encode()).hexdigest()[:8], 16)
    edges.append({"id": ef, "u": "ov:" + u, "v": "ov:" + v, "travel_ticks": ticks, "reverse_edge": er,
                  "segments": [{"cell": c, "start": round(s, 9), "end": round(e, 9)} for c, s, e in cs], "source_way": way,
                  "direction_evidence": "overture_two_way_assumed", "length_m": round(sub.length, 1), "class": cl})
    edges.append({"id": er, "u": "ov:" + v, "v": "ov:" + u, "travel_ticks": ticks, "reverse_edge": ef,
                  "segments": [{"cell": c, "start": round(s, 9), "end": round(e, 9)} for c, s, e in cs_rev], "source_way": way,
                  "direction_evidence": "overture_two_way_assumed", "length_m": round(sub.length, 1), "class": cl})
    forb += [[ef, er], [er, ef]]
graph = {"revision": "paradise-overture-20261021-two-way-grid375-dt1", "crs": "EPSG:32610",
         "grid": {"x0": x0, "y0": y0, "resolution": RES, "width": W, "height": H},
         "nodes": [{"id": "ov:" + n, "x": xy[0], "y": xy[1], "waitable": False} for n, xy in nodes.items()],
         "edges": edges, "forbidden_turns": forb, "mid_edge_reversal": False,
         "provenance": {"source": "Overture Maps transportation segments, release 2026-10-21.0 (OpenStreetMap-derived, ODbL); present-day network used as a proxy for November 2018",
                        "license": "ODbL; https://www.openstreetmap.org/copyright", "speeds_kmh": SPEED_KMH,
                        "assumptions": "all roads two-way; free-flow speeds by class; no congestion; service roads, tracks, paths excluded"}}
json.dump(graph, open(OUT, "w"))
print("grid", graph["grid"], "nodes", len(graph["nodes"]), "edges", len(edges), "sha256", hashlib.sha256(open(OUT, "rb").read()).hexdigest()[:16])
