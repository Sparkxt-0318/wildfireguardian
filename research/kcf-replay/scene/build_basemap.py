"""Basemap vectors for the KCF scene: planner/public/kcf-scene/data/basemap.js (window.KCF.basemap).

Inputs (committed):
* planner/research-map/site/regions/<region>.osm.js: window.WFG_OSM[region] = {roads, water, landuse}, each a list of
  [kind, subkind, [[lon, lat, lon, lat, ...], ...]] (simplified from the planner's Protomaps PMTiles by
  planner/research-map/tools/build_regions.py; water kind "water" = polygon exterior rings, other kinds = lines).
* planner/data/osm/<region>.overpass.json: place=town nodes and amenity=townhall nodes.

Output: three GeoJSON FeatureCollections, merged over both regions, coordinates rounded to 5 decimals.
* roads: every kind kept, properties {k: kind, s: subkind}.
* water: lines and polygons as they are, properties {k, s}.
* towns: place=town nodes (kind "town") and amenity=townhall nodes whose name ends with
  면사무소 / 읍사무소 / 군청 / 시청 (kind "office"), properties {name, kind, osm}.
Nothing is clipped; a line part, ring or point entirely outside the terrain bbox (lon 128.28..129.50, lat 36.20..36.62)
is dropped (a feature with no part left is dropped). landuse is not used.

Usage: python3 research/kcf-replay/scene/build_basemap.py
"""
from __future__ import annotations

import hashlib, json, re, subprocess
from collections import Counter
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon, box

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = ROOT / "planner/public/kcf-scene/data/basemap.js"
REGIONS = ["uiseong_andong_2025", "yeongdeok_2025"]
OSM_JS = "planner/research-map/site/regions/{r}.osm.js"
OVERPASS = "planner/data/osm/{r}.overpass.json"
BBOX = (128.28, 36.20, 129.50, 36.62)  # the terrain bbox (build_terrain.py)
OFFICE_SUFFIXES = ("면사무소", "읍사무소", "군청", "시청")
ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"
SCRIPT = "research/kcf-replay/scene/build_basemap.py"
ND = 5


def rel_input(rel, inputs):
    b = (ROOT / rel).read_bytes()
    inputs.append({"path": rel, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
    return b


def parse_osm_js(text, region):
    m = re.fullmatch(r'\(window\.WFG_OSM=window\.WFG_OSM\|\|\{\}\)\["([A-Za-z0-9_]+)"\]=(.*);\s*', text, re.S)
    if not m or m.group(1) != region:
        raise SystemExit(f"{region}.osm.js: unexpected wrapper")
    o = json.loads(m.group(2))
    for lay in ("roads", "water"):
        for f in o[lay]:
            if not (isinstance(f, list) and len(f) == 3 and isinstance(f[0], str) and isinstance(f[1], str)
                    and all(isinstance(p, list) and len(p) % 2 == 0 for p in f[2])):
                raise SystemExit(f"{region}.osm.js {lay}: unexpected feature shape {str(f)[:80]}")
    return o


def pairs(flat):
    return [[round(flat[i], ND), round(flat[i + 1], ND)] for i in range(0, len(flat), 2)]


def feature(geom, props):
    return {"type": "Feature", "properties": props, "geometry": geom}


def main():
    clip = box(*BBOX)
    inputs = []
    roads, water, towns = [], [], []
    counts = {"roads": Counter(), "water": Counter(), "towns": Counter(),
              "dropped": Counter(), "per_region": {}}
    for r in REGIONS:
        o = parse_osm_js(rel_input(OSM_JS.format(r=r), inputs).decode("utf-8"), r)
        rc = Counter()
        for lay, out in (("roads", roads), ("water", water)):
            for k, s, parts in o[lay]:
                poly = lay == "water" and k == "water"
                keep = []
                for p in parts:
                    c = pairs(p)
                    if poly:
                        if len(c) < 4 or c[0] != c[-1]:
                            raise SystemExit(f"{r} water ring not closed or too short: {c[:3]}")
                        g = Polygon(c)
                    else:
                        if len(c) < 2:
                            counts["dropped"][f"{lay}: part with < 2 points"] += 1
                            continue
                        g = LineString(c)
                    if not g.intersects(clip):
                        counts["dropped"][f"{lay}: part outside bbox"] += 1
                        continue
                    keep.append(c)
                if not keep:
                    counts["dropped"][f"{lay}: feature outside bbox"] += 1
                    continue
                if poly:
                    geom = ({"type": "Polygon", "coordinates": [keep[0]]} if len(keep) == 1
                            else {"type": "MultiPolygon", "coordinates": [[ring] for ring in keep]})
                else:
                    geom = ({"type": "LineString", "coordinates": keep[0]} if len(keep) == 1
                            else {"type": "MultiLineString", "coordinates": keep})
                out.append(feature(geom, {"k": k, "s": s}))
                counts[lay][f"{k}/{s}" if s else k] += 1
                rc[lay] += 1
        ov = json.loads(rel_input(OVERPASS.format(r=r), inputs))
        for e in ov["elements"]:
            if e.get("type") != "node":
                continue
            t = e.get("tags", {})
            name = t.get("name")
            if not name:
                continue
            if t.get("place") == "town":
                kind = "town"
            elif t.get("amenity") == "townhall" and name.endswith(OFFICE_SUFFIXES):
                kind = "office"
            else:
                continue
            lon, lat = round(e["lon"], ND), round(e["lat"], ND)
            if not Point(lon, lat).intersects(clip):
                counts["dropped"]["towns: outside bbox"] += 1
                continue
            towns.append((e["id"], feature({"type": "Point", "coordinates": [lon, lat]},
                                           {"name": name, "kind": kind, "osm": f"node/{e['id']}"})))
            rc["towns"] += 1
        counts["per_region"][r] = dict(sorted(rc.items()))
    seen, tf = set(), []
    for i, f in sorted(towns, key=lambda t: t[0]):
        if i in seen:
            counts["dropped"]["towns: duplicate node"] += 1
            continue
        seen.add(i)
        tf.append(f)
        counts["towns"][f["properties"]["kind"]] += 1

    fc = lambda fs: {"type": "FeatureCollection", "features": fs}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    obj = {
        "attribution": ATTRIBUTION,
        "bounds": list(BBOX),
        "roads": fc(roads), "water": fc(water), "towns": fc(tf),
        "counts": {k: dict(sorted(v.items())) if isinstance(v, Counter) else v for k, v in counts.items()},
        "built": {"script": SCRIPT, "commit": commit, "inputs": inputs,
                  "rules": {"bbox": list(BBOX), "round": ND,
                            "drop": "line parts, rings and points entirely outside bbox; nothing clipped",
                            "water_polygons": "kind 'water' (polygon exterior rings in the source)",
                            "office_suffixes": list(OFFICE_SUFFIXES),
                            "towns": "nodes only: place=town; amenity=townhall with name ending in office_suffixes"}},
    }
    js = f"// built by {SCRIPT} (do not edit)\n(window.KCF=window.KCF||{{}}).basemap=" + \
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + ";\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(js, encoding="ascii")
    n = OUT.stat().st_size
    print(f"wrote {OUT.relative_to(ROOT)}: {n} bytes ({n / 1e6:.2f} MB)")
    print(f"  roads {len(roads)}, water {len(water)}, towns {len(tf)}")
    print("  counts", json.dumps(obj["counts"], ensure_ascii=False, sort_keys=True))
    print("  towns", ", ".join(f"{f['properties']['name']}({f['properties']['kind']})" for f in tf))


if __name__ == "__main__":
    main()
