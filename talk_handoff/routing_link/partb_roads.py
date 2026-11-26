"""PROTOCOL_v3 section 9 + Amendment 1 item 3, road part: road length inside each fire's buffered 6 h footprint.

Reads partb/select/<event>.{npz,json} (partb_select.py). For each fire with a runnable cutoff:

* the footprint cells as polygons, unioned and buffered by 2 km (Euclidean, grid CRS);
* OpenStreetMap over the buffer's bounding box with Fish Creek's Overpass query, [date:] = the fire's cutoff, saved to
  partb/osm/<event>_footprint.json.gz with its provenance;
* the road layer's graph (osm_graph.build, unchanged) on the fire's grid; road length = undirected edge length inside
  the buffer (each OSM way segment once, clipped to the buffer).

Writes partb/selection.json with every candidate, the choice and the runner-up. Run from this folder:

    python3 partb_roads.py [--fetch] [--endpoint URL]
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REGIONS = Path("/Users/jp/Desktop/wildfire/data/environment/regions")
BUFFER_M = 2000.0
QUERY = """[out:json][timeout:600][date:"{date}"];
(
  way[highway]({s},{w},{n},{e});
  node[place]({s},{w},{n},{e});
  nwr[amenity~"^(shelter|fire_station|school|townhall|community_centre)$"]({s},{w},{n},{e});
  nwr[tourism~"^(camp_site|alpine_hut)$"]({s},{w},{n},{e});
);
(._;>;);
out body;"""


def footprint_polygon(z):
    from shapely.geometry import box
    from shapely.ops import unary_union
    t = z["transform"]
    a, b, c, d, e, f = (float(x) for x in t[:6])
    rr, cc = np.nonzero(z["footprint"])
    cells = [box(c + a * j, f + e * (i + 1), c + a * (j + 1), f + e * i) for i, j in zip(rr, cc)]
    return unary_union(cells)


def fetch(bbox_wgs84, date, endpoints, out):
    w, s, e, n = bbox_wgs84
    q = QUERY.format(date=date, s=s, w=w, n=n, e=e)
    data = urllib.parse.urlencode({"data": q}).encode()
    eps = [x for x in endpoints.split(",") if x]
    for attempt in range(2 * len(eps)):
        endpoint = eps[attempt % len(eps)]
        req = urllib.request.Request(endpoint, data=data, headers={"User-Agent": "routing-link-research/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=360) as r:
                raw = r.read()
            js = json.loads(raw)
            if "elements" not in js:
                raise ValueError("no elements in response")
            if "error" in js.get("remark", "").lower():
                raise ValueError("server remark: %s" % js["remark"][:120])
            out.write_bytes(gzip.compress(raw))
            return {"query": q, "endpoint": endpoint, "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "server_timestamp_osm_base": js.get("osm3s", {}).get("timestamp_osm_base"),
                    "sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "n_elements": len(js["elements"])}
        except Exception as ex:  # noqa: BLE001
            wait = 20 * (attempt + 1)
            print("  fetch failed at %s (%s), retry in %d s" % (endpoint.split("/")[2], str(ex)[:100], wait), flush=True)
            time.sleep(wait)
    raise RuntimeError("Overpass fetch failed after retries")


def road_length(osm_path, grid_json, cutoff, poly):
    import osm_graph as G
    from shapely.geometry import LineString
    graph, origins, exits, meta = G.build(osm_path, grid_json, cutoff)
    xy = {n["id"]: (n["x"], n["y"]) for n in graph["nodes"]}
    seen, total, inside_edges = set(), 0.0, 0
    from shapely.prepared import prep
    pp = prep(poly)
    for e in graph["edges"]:
        base = e["id"].rsplit(":", 1)[0]
        if base in seen:
            continue
        seen.add(base)
        ln = LineString([xy[e["u"]], xy[e["v"]]])
        if not pp.intersects(ln):
            continue
        L = ln.intersection(poly).length
        if L > 0:
            total += L
            inside_edges += 1
    return {"road_length_m": total, "segments_in_buffer": inside_edges, "graph_segments": len(seen),
            "graph_nodes": len(graph["nodes"]), "origins": len(origins), "exits": len(exits),
            "origin_rule": meta["origin_rule"]}


def fetch_full(ev, endpoints, tiles=3):
    """Amendment 1 item 3: the chosen fire's OSM over its whole grid, as data/fishcreek_osm_20240823.json.gz was."""
    sel = json.loads((HERE / "partb" / "select" / ("%s.json" % ev)).read_text())
    g = json.loads((REGIONS / ev / "grid.json").read_text())
    out = HERE / "partb" / "osm" / ("%s_grid.json.gz" % ev)
    w, s, e, n = g["bounds_wgs84"]
    k = tiles
    tdir = HERE / "partb" / "osm" / ("%s_grid_tiles" % ev)
    tdir.mkdir(exist_ok=True)
    merged, tiles_prov, base = {}, [], None
    for i in range(k):
        for j in range(k):
            tb = (w + (e - w) * j / k, s + (n - s) * i / k, w + (e - w) * (j + 1) / k, s + (n - s) * (i + 1) / k)
            tf = tdir / ("tile_%d_%d.json.gz" % (i, j))
            tp = tdir / ("tile_%d_%d.provenance.json" % (i, j))
            if not tf.exists():
                print("tile", i, j, flush=True)
                tp.write_text(json.dumps(fetch(tb, sel["cutoff_utc"], endpoints, tf), indent=1))
                time.sleep(5)
            q = json.loads(tp.read_text())
            tiles_prov.append({"tile": [i, j], "bbox": tb, "endpoint": q["endpoint"], "sha256": q["sha256"],
                               "n_elements": q["n_elements"], "server_timestamp_osm_base": q["server_timestamp_osm_base"]})
            js = json.loads(gzip.decompress(tf.read_bytes()))
            base = js
            for el in js["elements"]:
                merged[(el["type"], el["id"])] = el
    doc = {k2: v for k2, v in base.items() if k2 != "elements"}
    doc["elements"] = list(merged.values())
    out.write_bytes(gzip.compress(json.dumps(doc).encode()))
    p = {"query": QUERY, "date": sel["cutoff_utc"], "bbox": "grid bounds_wgs84 %s in %dx%d tiles, merged by (type, id)" % (g["bounds_wgs84"], k, k),
         "tiles": tiles_prov, "n_elements": len(merged), "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
         "endpoint": sorted({t["endpoint"] for t in tiles_prov}),
         "server_timestamp_osm_base": sorted({t["server_timestamp_osm_base"] for t in tiles_prov}),
         "event": ev, "license": "ODbL, OpenStreetMap contributors",
         "why_tiles": "the whole-grid query ran out of the server's 2 GB memory limit (remark: runtime error)",
         "note": "whether the server applied the [date:] historical filter is not verified, as for Fish Creek"}
    (HERE / "partb" / "osm" / ("%s_grid.provenance.json" % ev)).write_text(json.dumps(p, indent=1))
    print(json.dumps({k: p[k] for k in ("endpoint", "n_elements", "server_timestamp_osm_base", "sha256")}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--endpoint", default="https://overpass-api.de/api/interpreter,https://overpass.private.coffee/api/interpreter,"
                    "https://overpass.kumi.systems/api/interpreter",
                    help="comma-separated; tried in turn, the one that answered is in the provenance")
    ap.add_argument("--full", metavar="EVENT", help="fetch OSM over the chosen fire's whole grid (bounds_wgs84) and stop")
    ap.add_argument("--tiles", type=int, default=3, help="--full: k x k tiles (one whole-grid query exceeds 2 GB)")
    a = ap.parse_args()
    if a.full:
        return fetch_full(a.full, a.endpoint, a.tiles)
    from pyproj import Transformer
    sel, osm_dir = HERE / "partb" / "select", HERE / "partb" / "osm"
    osm_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for js in sorted(sel.glob("*.json")):
        r = json.loads(js.read_text())
        ev = r["event"]
        row = {"event": ev, "status": r["status"], "cutoff_utc": r.get("cutoff_utc"),
               "first_burned_index": r.get("first_burned_index"), "cutoff_index": r.get("cutoff_index"),
               "tries": len(r.get("tries", [])), "footprint_cells": r.get("footprint_cells"),
               "burned_at_cutoff": r.get("burned_at_cutoff"), "reached_by_any_path": r.get("reached_by_any_path")}
        if r["status"] != "ok":
            rows.append(row)
            continue
        z = np.load(sel / ("%s.npz" % ev))
        poly = footprint_polygon(z).buffer(BUFFER_M)
        tr = Transformer.from_crs("EPSG:%d" % int(z["epsg"]), "EPSG:4326", always_xy=True)
        x0, y0, x1, y1 = poly.bounds
        xs, ys = np.linspace(x0, x1, 21), np.linspace(y0, y1, 21)
        X, Y = np.meshgrid(xs, ys)
        lon, lat = tr.transform(X.ravel(), Y.ravel())
        bbox = (float(np.min(lon)), float(np.min(lat)), float(np.max(lon)), float(np.max(lat)))
        row.update(buffer_area_km2=poly.area / 1e6, bbox_wgs84=bbox)
        out = osm_dir / ("%s_footprint.json.gz" % ev)
        prov = osm_dir / ("%s_footprint.provenance.json" % ev)
        if not out.exists() and a.fetch:
            print("fetching", ev, flush=True)
            try:
                p = fetch(bbox, r["cutoff_utc"], a.endpoint, out)
                p["note"] = ("whether the server applied the [date:] historical filter is not verified, as for Fish Creek")
                prov.write_text(json.dumps(p, indent=1))
            except RuntimeError as ex:
                row["osm_fetch_error"] = str(ex)
                print("  giving up on", ev, "for this run", flush=True)
            time.sleep(10)
        if out.exists():
            row.update(road_length(out, REGIONS / ev / "grid.json", r["cutoff_utc"], poly))
            row["osm_sha256"] = json.loads(prov.read_text())["sha256"] if prov.exists() else None
        rows.append(row)
        print(ev, row.get("road_length_m"), flush=True)
    ok = [x for x in rows if x.get("road_length_m") is not None]
    ok.sort(key=lambda x: -x["road_length_m"])
    S = {"rule": "PROTOCOL_v3 section 9 and Amendment 1 items 2-3", "buffer_m": BUFFER_M, "n_candidates": len(rows),
         "n_with_road_length": len(ok), "candidates": rows,
         "ranking": [{"event": x["event"], "road_length_km": round(x["road_length_m"] / 1000, 3)} for x in ok],
         "choice": ok[0]["event"] if ok else None, "runner_up": ok[1]["event"] if len(ok) > 1 else None,
         "complete": len(ok) == sum(1 for x in rows if x["status"] == "ok")}
    (HERE / "partb" / "selection.json").write_text(json.dumps(S, indent=1))
    print(json.dumps({k: S[k] for k in ("choice", "runner_up", "complete", "n_with_road_length")}),
          json.dumps(S["ranking"][:6]))


if __name__ == "__main__":
    main()
