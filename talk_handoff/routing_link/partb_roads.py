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


def fetch(bbox_wgs84, date, endpoint, out):
    w, s, e, n = bbox_wgs84
    q = QUERY.format(date=date, s=s, w=w, n=n, e=e)
    data = urllib.parse.urlencode({"data": q}).encode()
    req = urllib.request.Request(endpoint, data=data, headers={"User-Agent": "routing-link-research/1.0"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=900) as r:
                raw = r.read()
            js = json.loads(raw)
            if "elements" not in js:
                raise ValueError("no elements in response")
            out.write_bytes(gzip.compress(raw))
            return {"query": q, "endpoint": endpoint, "fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "server_timestamp_osm_base": js.get("osm3s", {}).get("timestamp_osm_base"),
                    "sha256": hashlib.sha256(out.read_bytes()).hexdigest(), "n_elements": len(js["elements"])}
        except Exception as ex:  # noqa: BLE001
            wait = 30 * (attempt + 1)
            print("  fetch failed (%s), retry in %d s" % (str(ex)[:120], wait), flush=True)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--endpoint", default="https://overpass.private.coffee/api/interpreter")
    a = ap.parse_args()
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
            p = fetch(bbox, r["cutoff_utc"], a.endpoint, out)
            p["note"] = ("whether the server applied the [date:] historical filter is not verified, as for Fish Creek")
            prov.write_text(json.dumps(p, indent=1))
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
