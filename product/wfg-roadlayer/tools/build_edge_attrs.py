"""Per-edge forest share and per-way road class for the village cards, from what the repository already has.

Source: the planner's offline OpenStreetMap basemap, planner/public/basemap/<region>.pmtiles (Protomaps build
20261016, OSM replication 2026-10-16, ODbL; tiles copied byte for byte, planner/public/basemap/SOURCES.json), zoom 15.
No network.

* **Forest.** OSM `landuse` polygons of kind `wood` or `forest` (the basemap's `landuse` layer). The basemap keeps no
  `leaf_type`, and the repository has no Korean forest-type (conifer / broadleaf) map (research/kcf-idea-forecast/
  SURVEY.md: "No stand-level canopy data for the Gyeongbuk burn area in this repo"); so this is the share of each
  edge running through **any** mapped forest, not the conifer share. Each edge is its straight chord between the two
  graph nodes (as research/kcf-replay/replay.py reads it), sampled every 10 m (at least 2 samples, at the sample
  centres); a sample counts as forest when mapped forest lies within 50 m of it. The 50 m is ASSUMED: Korean OSM
  forest polygons are usually drawn up to, not across, the road corridor (in 의성·안동 74 % of random points are in
  mapped forest but only 7 % of road length is, on the centreline itself).
* **Road class.** For every OSM way of the graph (`source_way`), the basemap `roads` feature nearest to the
  midpoints of the way's edges (within 25 m), majority over the edges: Protomaps `kind` / `kind_detail`
  (= OSM highway=*), `name`, `ref`. The basemap is 2026 OSM, the graph is the 2025-03-21 snapshot: a way that is not
  matched gets class "unmatched" (treated as the narrowest class by the cards; ASSUMED).

Writes data/edges/<region>_forest.csv.gz (edge id, share in thousandths; edges with share 0 left out) and
data/edges/<region>_ways.csv.gz (source_way, kind, kind_detail, name, ref, matched edges / edges).

Needs (build time only, not at run time): pip install pmtiles mapbox-vector-tile shapely pyproj

    python3 tools/build_edge_attrs.py [--cache ~/.cache/wfg-roadlayer] [region ...]
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import mapbox_vector_tile
from pmtiles.reader import MmapSource, Reader
from pyproj import Transformer
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, shape
from shapely.prepared import prep
from shapely.strtree import STRtree

PRODUCT = Path(__file__).resolve().parents[1]
REPO = PRODUCT.parents[1]
sys.path.insert(0, str(PRODUCT))
from wfg_roadlayer import regiondata  # noqa: E402

Z = 15
N = 2 ** Z
FOREST_KINDS = {"wood", "forest"}
STEP_M = 10.0
NEAR_M = 50.0  # ASSUMED: forest within this distance of the road centreline counts
MATCH_M = 25.0


def tile_of(lon, lat):
    x = int((lon + 180) / 360 * N)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * N)
    return x, y


class Tiles:
    """Decoded z15 tiles in a local metric frame (EPSG:5179 coordinates)."""

    def __init__(self, path: Path):
        self.f = open(path, "rb")
        self.r = Reader(MmapSource(self.f))
        self.to5179 = Transformer.from_crs(4326, 5179, always_xy=True)
        self.cache = {}

    def get(self, x, y):
        k = (x, y)
        if k in self.cache:
            return self.cache[k]
        raw = self.r.get(Z, x, y)
        out = {"forest": None, "roads": []}
        if raw:
            d = mapbox_vector_tile.decode(gzip.decompress(raw), default_options={"y_coord_down": True})

            def conv(px, py, ext):
                lon = (x + px / ext) / N * 360 - 180
                lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + py / ext) / N))))
                return self.to5179.transform(lon, lat)

            def tr(geom, ext):
                t = geom["type"]
                c = geom["coordinates"]
                if t == "Polygon":
                    return Polygon([conv(*p, ext) for p in c[0]], [[conv(*p, ext) for p in h] for h in c[1:]])
                if t == "MultiPolygon":
                    return MultiPolygon([Polygon([conv(*p, ext) for p in poly[0]], [[conv(*p, ext) for p in h] for h in poly[1:]])
                                         for poly in c])
                if t == "LineString":
                    return [LineString([conv(*p, ext) for p in c])]
                if t == "MultiLineString":
                    return [LineString([conv(*p, ext) for p in line]) for line in c]
                return None

            lu = d.get("landuse", {})
            polys = []
            for ft in lu.get("features", []):
                if ft["properties"].get("kind") in FOREST_KINDS:
                    g = tr(ft["geometry"], lu["extent"])
                    if g is not None and not g.is_empty:
                        polys.append(g if g.is_valid else g.buffer(0))
            if polys:
                from shapely.ops import unary_union
                out["forest"] = prep(unary_union(polys))
            rd = d.get("roads", {})
            for ft in rd.get("features", []):
                p = ft["properties"]
                for ln in tr(ft["geometry"], rd["extent"]) or []:
                    out["roads"].append((ln, p.get("kind") or "", p.get("kind_detail") or "", p.get("name") or "", p.get("ref") or ""))
        self.cache[k] = out
        return out


def build(rid: str, cache: Path):
    meta = regiondata.REGISTRY["regions"][rid]
    g = json.loads((cache / "graphs" / rid / "graph.json").read_text(encoding="utf-8"))
    xy = {n["id"]: (float(n["x"]), float(n["y"])) for n in g["nodes"]}
    to4326 = Transformer.from_crs(5179, 4326, always_xy=True)
    tiles = Tiles(REPO / "planner/public/basemap" / ("%s.pmtiles" % rid))
    forest = {}
    way_votes = defaultdict(Counter)
    way_edges = Counter()
    road_trees = {}
    for i, e in enumerate(g["edges"]):
        (x0, y0), (x1, y1) = xy[e["u"]], xy[e["v"]]
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(2, int(math.ceil(L / STEP_M)))
        inside = 0
        for k in range(n):
            f = (k + 0.5) / n
            px, py = x0 + f * (x1 - x0), y0 + f * (y1 - y0)
            lon, lat = to4326.transform(px, py)
            t = tiles.get(*tile_of(lon, lat))
            if t["forest"] is not None and t["forest"].intersects(Point(px, py).buffer(NEAR_M, 8)):
                inside += 1
        share = round(1000 * inside / n)
        if share:
            forest[e["id"]] = share
        # road class: one vote per edge at its midpoint; forward and reverse edges vote once
        if e["id"].endswith(":r") and e.get("reverse_edge"):
            continue
        w = e["source_way"]
        way_edges[w] += 1
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        lon, lat = to4326.transform(mx, my)
        key = tile_of(lon, lat)
        if key not in road_trees:
            rs = tiles.get(*key)["roads"]
            road_trees[key] = (STRtree([r[0] for r in rs]) if rs else None, rs)
        tree, rs = road_trees[key]
        if tree is None:
            continue
        pt = Point(mx, my)
        j = tree.nearest(pt)
        if j is None:
            continue
        r = rs[int(j)]
        if r[0].distance(pt) <= MATCH_M:
            way_votes[w][r[1:]] += 1
        if i % 20000 == 0:
            print("%s: %d / %d edges" % (rid, i, len(g["edges"])), flush=True)
    outd = PRODUCT / "data" / "edges"
    outd.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["edge_id", "forest_share_permille"])
    for k in sorted(forest):
        w.writerow([k, forest[k]])
    (outd / ("%s_forest.csv.gz" % rid)).write_bytes(gzip.compress(buf.getvalue().encode(), mtime=0))
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["source_way", "kind", "kind_detail", "name", "ref", "matched_edges", "edges"])
    kinds = Counter()
    for way in sorted(way_edges):
        votes = way_votes.get(way)
        if votes:
            (kind, det, name, ref), m = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            matched = sum(votes.values())
        else:
            kind, det, name, ref, matched = "unmatched", "", "", "", 0
        kinds[det or kind] += 1
        w.writerow([way, kind, det, name, ref, matched, way_edges[way]])
    (outd / ("%s_ways.csv.gz" % rid)).write_bytes(gzip.compress(buf.getvalue().encode("utf-8"), mtime=0))
    print("%s: %d edges with forest > 0 of %d; ways %d, classes %s" % (rid, len(forest), len(g["edges"]), len(way_edges),
                                                                     dict(kinds.most_common())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=regiondata.default_cache())
    ap.add_argument("regions", nargs="*")
    a = ap.parse_args()
    for rid in a.regions or sorted(regiondata.REGISTRY["regions"]):
        build(rid, a.cache)


if __name__ == "__main__":
    main()
