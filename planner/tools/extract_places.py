#!/usr/bin/env python3
"""Candidate origins / destinations for the village evacuation planner (ARCHITECTURE.md §4.2).

Inputs (read only): graphs/<region>/graph.json and the recorded mission requests from the verified
inputs release extract; raw Overpass extracts (current OpenStreetMap, ODbL).

Outputs:
  planner/data/osm/<region>.overpass.json          raw Overpass response bytes (ODbL)
  planner/data/osm/SOURCES.json                    endpoint, query, fetch time, timestamp_osm_base, sha256
  planner/public/data/regions/<region>/places.geojson
  planner/public/data/regions/<region>/places_report.json   every excluded / dropped / merged element
  planner/public/data/regions/index.json

Usage:
  python3 planner/tools/extract_places.py                 # build everything (fetch only missing extracts)
  python3 planner/tools/extract_places.py --fetch-only    # only make sure every raw extract exists
  python3 planner/tools/extract_places.py --refresh R     # re-download region R's extract

Nothing is invented: names come only from OSM `name` / `name:en` / `name:ko-Latn` (else null);
research points come only from the recorded mission requests.
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import planner_common as pc  # noqa: E402

OSM_DIR = pc.PLANNER / "data" / "osm"
RAW_REUSE_DIR = pc.ASSETS / "osm_raw"
PUBLIC_REGIONS = pc.PLANNER / "public" / "data" / "regions"

ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
MAX_ATTEMPTS = 12

QUERY_TEMPLATE = (
    '[out:json][timeout:120];('
    'node["place"~"^(village|hamlet|isolated_dwelling|neighbourhood|quarter|town)$"]({bbox});'
    'nwr["amenity"~"^(nursing_home|social_facility|shelter|community_centre|school|townhall|kindergarten|hospital|clinic)$"]({bbox});'
    'nwr["emergency"~"^(assembly_point|shelter)$"]({bbox});'
    'nwr["social_facility"]({bbox});'
    'nwr["building"~"^(school|community_centre)$"]({bbox});'
    ');out center tags;'
)

# Extracts fetched by the earlier (interrupted) run of this tool and kept in planner/.assets/osm_raw/.
# Endpoint per region as recorded by that run; the download time is the earlier run's file time.
REUSED_EXTRACT_ENDPOINTS = {
    "uiseong_andong_2025": "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "uljin_2022": "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "hongseong_2023": "https://overpass.kumi.systems/api/interpreter",
}
REUSED_FETCHED_AT = {  # mtime (UTC) of the earlier run's download files
    "uiseong_andong_2025": "2026-10-17T06:00:10Z",
    "uljin_2022": "2026-10-17T06:02:49Z",
    "hongseong_2023": "2026-10-17T06:03:13Z",
}

SHELTER_TYPE_EXCLUDED = {"gazebo", "public_transport", "picnic_shelter", "sun_shelter", "weather_shelter",
                         "field_shelter", "changing_rooms", "lean_to", "rock_shelter"}
ENTRY_MAX_M = 2000.0      # no accepted road node within this distance -> 점검 불가 (kept, never dropped)
API_SNAP_LIMIT_M = 300.0  # the API refuses lon/lat snaps beyond this; entry points are sent as node_id instead
SCHOOL_MERGE_M = 150.0


# ---------------------------------------------------------------------------------------------
# Overpass
# ---------------------------------------------------------------------------------------------

def query_bbox(g: pc.Graph):
    w, s, e, n = g.wgs84_bbox()
    f = 1e7
    return (math.floor(s * f) / f, math.floor(w * f) / f, math.ceil(n * f) / f, math.ceil(e * f) / f)


def query_text(bbox_swne) -> str:
    return QUERY_TEMPLATE.format(bbox="%.7f,%.7f,%.7f,%.7f" % bbox_swne)


def validate_overpass(data: bytes) -> dict:
    doc = json.loads(data.decode("utf-8"))
    if not isinstance(doc, dict) or "elements" not in doc:
        raise ValueError("no elements in response")
    if "remark" in doc and ("error" in doc["remark"].lower() or "timed out" in doc["remark"].lower()):
        raise ValueError("overpass remark: %s" % doc["remark"][:200])
    if not doc.get("osm3s", {}).get("timestamp_osm_base"):
        raise ValueError("missing osm3s.timestamp_osm_base")
    return doc


def fetch_overpass(query: str, log=print):
    body = urllib.parse.urlencode({"data": query}).encode("ascii")
    last = None
    for attempt in range(MAX_ATTEMPTS):
        endpoint = ENDPOINTS[attempt % len(ENDPOINTS)]
        req = urllib.request.Request(endpoint, data=body, method="POST", headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "WildfireGuardian-planner-data/1.0 (pre-season evacuation planning research)",
            "Accept": "application/json"})
        started = pc.real_utc_now()
        try:
            with urllib.request.urlopen(req, timeout=200) as resp:
                data = resp.read()
            doc = validate_overpass(data)
            log("  ok    attempt %d %s (%d elements)" % (attempt + 1, endpoint, len(doc["elements"])))
            return data, doc, endpoint, started, attempt + 1
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError, ValueError,
                OSError) as exc:
            last = "%s: %s" % (type(exc).__name__, str(exc)[:200])
            wait = min(60, 4 * 2 ** min(attempt, 4))
            log("  fail  attempt %d %s -> %s; retry in %ds" % (attempt + 1, endpoint, last, wait))
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep(wait)
    raise RuntimeError("all %d Overpass attempts failed (last: %s)" % (MAX_ATTEMPTS, last))


def load_sources() -> dict:
    p = OSM_DIR / "SOURCES.json"
    if p.is_file():
        return json.loads(p.read_text())
    return {}


def ensure_extracts(regions, refresh=(), log=print):
    """Make sure planner/data/osm/<region>.overpass.json exists for each region. Returns (sources, failed)."""
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    sources = load_sources()
    entries = sources.get("regions", {})
    failed = {}
    for region in regions:
        g = pc.load_graph(region)
        bbox = query_bbox(g)
        q = query_text(bbox)
        out = OSM_DIR / f"{region}.overpass.json"
        entry = entries.get(region)
        if out.is_file() and region not in refresh:
            sha = pc.sha256_file(out)
            if entry and entry.get("sha256") == sha:
                log("ok      %s extract present (sha256 matches SOURCES.json)" % region)
                continue
            if not entry:
                raise SystemExit("%s exists but has no SOURCES.json entry; use --refresh %s" % (out, region))
            raise SystemExit("%s sha256 %s differs from SOURCES.json; use --refresh %s" % (out, sha, region))
        reuse = RAW_REUSE_DIR / f"{region}.json"
        if reuse.is_file() and region not in refresh and region in REUSED_EXTRACT_ENDPOINTS:
            data = reuse.read_bytes()
            doc = validate_overpass(data)
            # Every element of the reused extract must lie inside this tool's query bbox.
            for el in doc["elements"]:
                lat = el.get("lat", el.get("center", {}).get("lat"))
                lon = el.get("lon", el.get("center", {}).get("lon"))
                if lat is not None and not (bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3]):
                    raise SystemExit("reused extract %s has element outside bbox: %s" % (reuse, el["id"]))
            shutil.copyfile(reuse, out)
            entries[region] = {
                "file": f"planner/data/osm/{region}.overpass.json",
                "sha256": pc.sha256_bytes(data), "bytes": len(data),
                "endpoint": REUSED_EXTRACT_ENDPOINTS[region],
                "query": q, "bbox_swne": list(bbox),
                "query_note": ("Downloaded by an earlier, interrupted run of this tool with the same query "
                               "template over the region graph grid bbox; that run did not record the bbox "
                               "literal, so the query shown is this tool's; every element of the extract was "
                               "verified to lie inside this bbox."),
                "fetched_at": REUSED_FETCHED_AT.get(region),
                "fetched_at_source": "modification time of the earlier run's download file",
                "timestamp_osm_base": doc["osm3s"]["timestamp_osm_base"],
                "generator": doc.get("generator"), "element_count": len(doc["elements"]),
                "attempts": None, "reused_from": f"planner/.assets/osm_raw/{region}.json",
            }
            log("reuse   %s from %s" % (region, reuse))
        else:
            log("fetch   %s bbox %s" % (region, bbox))
            try:
                data, doc, endpoint, started, attempts = fetch_overpass(q, log=log)
            except RuntimeError as exc:
                failed[region] = str(exc)
                log("FAILED  %s: %s" % (region, exc))
                continue
            out.write_bytes(data)
            entries[region] = {
                "file": f"planner/data/osm/{region}.overpass.json",
                "sha256": pc.sha256_bytes(data), "bytes": len(data), "endpoint": endpoint,
                "query": q, "bbox_swne": list(bbox), "query_note": None,
                "fetched_at": started, "fetched_at_source": "request start time (UTC) of the successful attempt",
                "timestamp_osm_base": doc["osm3s"]["timestamp_osm_base"],
                "generator": doc.get("generator"), "element_count": len(doc["elements"]),
                "attempts": attempts, "reused_from": None,
            }
        entries[region]["graph_revision"] = g.revision
        entries[region]["graph_snapshot"] = pc.graph_snapshot_date(g)
        sources = {
            "license": "ODbL 1.0 — © OpenStreetMap contributors (https://www.openstreetmap.org/copyright)",
            "note": ("Points of interest are CURRENT OpenStreetMap data (see timestamp_osm_base per region), "
                     "while the road graphs are HISTORICAL OSM snapshots taken just before each fire "
                     "(graph_snapshot). Places can differ from the road network of the fire date."),
            "query_template": QUERY_TEMPLATE,
            "endpoints_rotation": ENDPOINTS,
            "regions": dict(sorted(entries.items())),
        }
        pc.write_json(OSM_DIR / "SOURCES.json", sources)
    return load_sources(), failed


# ---------------------------------------------------------------------------------------------
# Classification (ARCHITECTURE.md §4.2, applied exactly)
# ---------------------------------------------------------------------------------------------

def classify(el: dict):
    """Return (role, category, source_tag) or (None, None, reason)."""
    t = el.get("tags", {})
    typ = el["type"]
    place = t.get("place")
    amenity = t.get("amenity")
    social = t.get("social_facility")
    name = t.get("name") or ""

    # Origins
    if place in ("village", "hamlet"):
        if typ == "node":
            return "origin", place, f"place={place}"
        origin_place_reason = f"place={place} mapped as {typ}; the origin filter takes place nodes only"
    else:
        origin_place_reason = None
    if amenity == "nursing_home":
        return "origin", "nursing_home", "amenity=nursing_home"
    if amenity == "social_facility":
        cat = "nursing_home" if social == "nursing_home" else "social_facility"
        tag = "amenity=social_facility" + (f" social_facility={social}" if social else "")
        return "origin", cat, tag
    if social is not None:
        cat = "nursing_home" if social == "nursing_home" else "social_facility"
        return "origin", cat, f"social_facility={social}"

    # Destinations
    if amenity == "shelter":
        st = t.get("shelter_type")
        if st in SHELTER_TYPE_EXCLUDED:
            return None, None, f"amenity=shelter with shelter_type={st} (excluded shelter type)"
        return "destination", "shelter", "amenity=shelter" + (f" shelter_type={st}" if st else "")
    if t.get("emergency") == "assembly_point":
        return "destination", "assembly_point", "emergency=assembly_point"
    if amenity == "school":
        return "destination", "school", "amenity=school"
    if t.get("building") == "school":
        return "destination", "school", "building=school"
    if amenity == "community_centre":
        return "destination", "community_hall", "amenity=community_centre"
    if amenity == "townhall":
        if "회관" in name:
            return "destination", "community_hall", "amenity=townhall name contains 회관"
        return None, None, "amenity=townhall whose name does not contain 회관 (administrative office, not a community hall)"

    if origin_place_reason:
        return None, None, origin_place_reason
    if place is not None:
        return None, None, f"place={place} is not an origin category (village|hamlet only)"
    if amenity in ("hospital", "clinic", "kindergarten"):
        return None, None, f"amenity={amenity} is excluded by the §4.2 filters"
    if t.get("emergency") == "shelter":
        return None, None, "emergency=shelter is not in the §4.2 destination filter"
    if t.get("building") == "community_centre":
        return None, None, "building=community_centre without amenity=community_centre is not in the §4.2 filter"
    return None, None, "no §4.2 origin or destination filter matches (tags: %s)" % ", ".join(
        f"{k}={v}" for k, v in sorted(t.items()) if k in ("amenity", "building", "emergency", "place"))


def element_lonlat(el):
    if el["type"] == "node":
        return el.get("lon"), el.get("lat")
    c = el.get("center") or {}
    return c.get("lon"), c.get("lat")


def osm_ref(el):
    return f"{el['type']}/{el['id']}"


def snap_points(g: pc.Graph, xs, ys):
    idx = np.nonzero(g.scc_mask)[0]
    nx, ny = g.x[idx], g.y[idx]
    out = []
    for x, y in zip(xs, ys):
        d2 = (nx - x) ** 2 + (ny - y) ** 2
        k = int(np.argmin(d2))
        out.append((g.node_ids[idx[k]], float(math.sqrt(d2[k]))))
    return out


def fit_zoom(bbox, width_px=700, height_px=812):
    """Web-mercator zoom that fits bbox [w,s,e,n] into the planner map pane (≈700×812 px at 1440×900)."""
    w, s, e, n = bbox

    def merc_y(lat):
        r = math.radians(lat)
        return math.log(math.tan(math.pi / 4 + r / 2))

    zx = math.log2(width_px / 256.0 * 360.0 / (e - w))
    zy = math.log2(height_px / 256.0 * 2 * math.pi / (merc_y(n) - merc_y(s)))
    return math.floor(min(zx, zy) * 4) / 4.0


def build_region(region_meta: dict, sources: dict, log=print):
    region = region_meta["id"]
    g = pc.load_graph(region)
    x0, y0, x1, y1 = g.grid_rect()
    raw_path = OSM_DIR / f"{region}.overpass.json"
    doc = json.loads(raw_path.read_bytes())
    src = sources["regions"][region]

    excluded, dropped, merged = [], [], []
    candidates = []
    for el in doc["elements"]:
        tags = el.get("tags", {})
        role, cat, tag_or_reason = classify(el)
        lon, lat = element_lonlat(el)
        base = {"id": f"osm:{osm_ref(el)}", "osm_type": el["type"], "osm_id": el["id"],
                "name": tags.get("name"), "tags": tags}
        if role is None:
            excluded.append({**base, "reason": tag_or_reason})
            continue
        if lon is None or lat is None:
            excluded.append({**base, "reason": "no coordinates in the extract"})
            continue
        x, y = pc.to_5179(lon, lat)
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            excluded.append({**base, "reason": "outside the region road-graph grid rectangle (EPSG:5179)"})
            continue
        candidates.append({"el": el, "role": role, "category": cat, "source_tag": tag_or_reason,
                           "lon": lon, "lat": lat, "x": x, "y": y, "merged": []})

    # Dedupe a school mapped as both node and way: same name within 150 m -> keep the way centre.
    schools = [c for c in candidates if c["category"] == "school" and c["el"].get("tags", {}).get("name")]
    removed = set()
    for cn in [c for c in schools if c["el"]["type"] == "node"]:
        best = None
        for cw in [c for c in schools if c["el"]["type"] in ("way", "relation")]:
            if cw["el"]["tags"]["name"] != cn["el"]["tags"]["name"]:
                continue
            d = math.hypot(cw["x"] - cn["x"], cw["y"] - cn["y"])
            if d <= SCHOOL_MERGE_M and (best is None or d < best[1]):
                best = (cw, d)
        if best:
            cw, d = best
            if not cw["merged"]:
                cw["merged"].append(f"osm:{osm_ref(cw['el'])}")
            cw["merged"].append(f"osm:{osm_ref(cn['el'])}")
            removed.add(id(cn))
            merged.append({"kept": f"osm:{osm_ref(cw['el'])}", "merged": f"osm:{osm_ref(cn['el'])}",
                           "name": cn["el"]["tags"]["name"], "distance_m": round(d, 1),
                           "reason": "school mapped as both node and way (same name within 150 m); kept the way centre"})
    candidates = [c for c in candidates if id(c) not in removed]

    # Same-name destination pairs that are NOT merged (reported for review only).
    possible_dupes = []
    dests = [c for c in candidates if c["role"] == "destination" and c["el"].get("tags", {}).get("name")]
    for i in range(len(dests)):
        for j in range(i + 1, len(dests)):
            a, b = dests[i], dests[j]
            if a["el"]["tags"]["name"] == b["el"]["tags"]["name"]:
                d = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
                if d <= SCHOOL_MERGE_M:
                    possible_dupes.append({"ids": [f"osm:{osm_ref(a['el'])}", f"osm:{osm_ref(b['el'])}"],
                                           "name": a["el"]["tags"]["name"], "distance_m": round(d, 1),
                                           "note": "same name within 150 m, not node+way school pair; kept both"})

    # Entry point (진입 지점): the nearest road node the API accepts as a node_id start/destination. Nodes of
    # the largest strongly connected component all have incoming and outgoing roads (the API's node rule) and
    # can reach each other. OSM villages here are mapped as points, so "inside or nearest to the village area"
    # reduces to the nearest such node to the OSM point. Only points with no such node within 2 km are
    # marked not checkable (점검 불가); none are dropped.
    snaps = snap_points(g, [c["x"] for c in candidates], [c["y"] for c in candidates])
    features = []
    for c, (node, dist) in zip(candidates, snaps):
        el, tags = c["el"], c["el"].get("tags", {})
        i = g.index[node]
        elon, elat = pc.to_wgs84(g.x[i], g.y[i])
        checkable = dist <= ENTRY_MAX_M
        if not checkable:
            dropped.append({"id": f"osm:{osm_ref(el)}", "osm_type": el["type"], "osm_id": el["id"],
                            "name": tags.get("name"), "tags": tags, "role": c["role"], "category": c["category"],
                            "entry": {"node": node, "distance_m": round(dist, 1)},
                            "reason": "kept as not checkable: nearest accepted road node is %.1f m away (> 2000 m)" % dist})
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(c["lon"], 7), round(c["lat"], 7)]},
            "properties": {
                "id": f"osm:{osm_ref(el)}",
                "role": c["role"], "category": c["category"],
                "name": tags.get("name"),
                "name_en": tags.get("name:en") or tags.get("name:ko-Latn"),
                "source": "OpenStreetMap", "source_tag": c["source_tag"],
                "osm": {"type": el["type"], "id": el["id"], "tags": tags, "merged_ids": c["merged"]},
                "snap": {"node": node, "distance_m": round(dist, 1)},
                "entry": {"node": node, "lon": round(float(elon), 7), "lat": round(float(elat), 7),
                          "distance_m": round(dist, 1), "within_api_lonlat_snap": dist <= API_SNAP_LIMIT_M},
                "checkable": checkable,
                "vulnerable": c["category"] in ("nursing_home", "social_facility"),
                "scenario_set_id": None, "input_time": None, "case_id": None, "recorded": None,
            },
        })
    order = {"origin": 0, "destination": 1}
    features.sort(key=lambda f: (order[f["properties"]["role"]], f["properties"]["category"],
                                 f["properties"]["name"] or "￿", f["properties"]["id"]))

    # Research points from the 20 recorded mission requests.
    scen_by_time = {}
    for pdir in pc.packet_dirs(region):
        h = json.loads((pdir / "HAZARD.json").read_bytes())
        ssid, _ = pc.scenario_set_from_hazard(h)
        scen_by_time[pc.compact_time(h["time_origin"])] = ssid
    research = []
    research_notes = []
    for rp in pc.request_paths(region):
        case_id = rp.stem
        req = json.loads(rp.read_bytes())
        input_compact = case_id.split("_")[0]
        if pc.compact_time(req["as_of"]) != input_compact:
            raise SystemExit("request %s as_of %s does not match case id" % (rp, req["as_of"]))
        ssid = scen_by_time[input_compact]
        dest = req["destinations"]
        if len(dest) != 1 or len(dest[0]["open_intervals"]) != 1:
            raise SystemExit("request %s: expected one destination with one open interval" % rp)
        dest = dest[0]
        inc_vals = list(req["incurred"].values())
        inc = pc.single_value(inc_vals)
        dose_budget = pc.single_value(req["budgets"]["dose"].values())
        if inc is None:
            research_notes.append(f"{case_id}: incurred dose differs between members {req['incurred']}; recorded incurred_dose_kj_m2 = null")
        if dose_budget is None:
            research_notes.append(f"{case_id}: dose budget differs between members; recorded limits.dose_kj_m2 = null")
        o_node, d_node = req["position"]["node"], dest["node"]
        dest_id = f"research:{region}:{case_id}:destination"
        for role, node in (("research_origin", o_node), ("research_destination", d_node)):
            i = g.index[node]
            lon, lat = pc.to_wgs84(g.x[i], g.y[i])
            word = "origin" if role == "research_origin" else "destination"
            recorded = None
            if role == "research_origin":
                recorded = {
                    "destination_id": dest_id, "destination_node": d_node,
                    "depart_offset_s": req["departure"], "dwell_s": dest["dwell"],
                    "destination_window": list(dest["open_intervals"][0]),
                    "incurred_dose_kj_m2": inc,
                    # Extra (needed to replay FN/FX missions exactly): the recorded budgets.
                    "limits": {"peak_kw_m2": req["budgets"]["peak"], "dose_kj_m2": dose_budget},
                    "horizon_s": req["horizon"],
                }
            research.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(float(lon), 7), round(float(lat), 7)]},
                "properties": {
                    "id": f"research:{region}:{case_id}:{word}",
                    "role": role, "category": "research",
                    "name": None, "name_en": None,
                    "source": "연구 패널 기록 임무",
                    "source_tag": f"request {case_id} {word} node {node}",
                    "osm": None,
                    "snap": {"node": node, "distance_m": 0.0, "in_largest_scc": bool(g.scc_mask[i])},
                    "entry": {"node": node, "lon": round(float(lon), 7), "lat": round(float(lat), 7),
                              "distance_m": 0.0, "within_api_lonlat_snap": True},
                    "checkable": True, "vulnerable": False,
                    "scenario_set_id": ssid, "input_time": pc.iso_z(input_compact), "case_id": case_id,
                    "recorded": recorded,
                },
            })
            if not g.scc_mask[i]:
                research_notes.append(f"{case_id} {word} node {node} is outside the largest SCC "
                                      "(recorded mission endpoint; the mock must accept it by node_id)")
    nodes_used = {}
    for f in research:
        nodes_used.setdefault(f["properties"]["snap"]["node"], []).append(f["properties"]["id"])
    shared = {k: v for k, v in nodes_used.items() if len(v) > 1}

    all_features = features + research
    fc = {"type": "FeatureCollection",
          "region_id": region,
          "notes": ["OpenStreetMap points are current OSM (timestamp_osm_base %s); the road graph is the "
                    "historical snapshot %s." % (src["timestamp_osm_base"], pc.graph_snapshot_date(g)),
                    "entry = 진입 지점: nearest node of the largest strongly connected road component (every such "
                    "node has incoming and outgoing roads, the API's node_id rule); the planner sends it as "
                    "{node_id}. checkable = entry distance <= 2000 m; travel between the OSM point and its entry "
                    "point is not modelled."],
          "features": all_features}
    out_dir = PUBLIC_REGIONS / region
    pc.write_json(out_dir / "places.geojson", fc, compact=True)

    n_orig = sum(1 for f in features if f["properties"]["role"] == "origin")
    n_dest = sum(1 for f in features if f["properties"]["role"] == "destination")
    dists = [f["properties"]["entry"]["distance_m"] for f in features]
    report = {
        "region_id": region,
        "generated_at": pc.utc_now(),
        "generator": "planner/tools/extract_places.py",
        "osm_extract": {k: src[k] for k in ("file", "sha256", "endpoint", "timestamp_osm_base", "element_count")},
        "graph": {"revision": g.revision, "sha256": g.sha256, "snapshot": pc.graph_snapshot_date(g),
                  "node_count": g.node_count, "largest_scc_nodes": int(g.scc_mask.sum())},
        "filters": {
            "origins": "place=village|hamlet nodes; amenity=nursing_home|social_facility; social_facility=*",
            "destinations": ("amenity=shelter (shelter_type not in %s); emergency=assembly_point; amenity=school; "
                             "building=school; amenity=community_centre; amenity=townhall with 회관 in name"
                             % sorted(SHELTER_TYPE_EXCLUDED)),
            "inside": "point inside the road-graph grid rectangle (EPSG:5179)",
            "entry": "nearest node of the largest strongly connected component of the directed road graph (진입 지점), sent as node_id",
            "checkable": "entry distance <= 2000 m", "not_checkable": "entry distance > 2000 m (kept, listed in dropped_far)",
            "school_dedupe": "school node + way with the same name within 150 m -> keep the way centre",
        },
        "counts": {"osm_elements": len(doc["elements"]), "origins": n_orig, "destinations": n_dest,
                   "research": len(research), "excluded": len(excluded), "dropped_far": len(dropped),
                   "merged": len(merged),
                   "checkable": sum(1 for f in features if f["properties"]["checkable"]),
                   "not_checkable": sum(1 for f in features if not f["properties"]["checkable"])},
        "snap_distance_m": ({"min": min(dists), "median": float(np.median(dists)), "max": max(dists)} if dists else None),
        "excluded": sorted(excluded, key=lambda e: (e["reason"], e["id"])),
        "dropped_far": dropped,
        "merged": merged,
        "possible_duplicates_not_merged": possible_dupes,
        "research": {"features": len(research), "missions": len(research) // 2,
                     "shared_nodes": shared, "notes": research_notes},
    }
    pc.write_json(out_dir / "places_report.json", report)
    log("places  %-20s origins %3d destinations %3d research %2d excluded %3d dropped %d merged %d"
        % (region, n_orig, n_dest, len(research), len(excluded), len(dropped), len(merged)))
    return {"origins": n_orig, "destinations": n_dest, "research": len(research)}


def verified_event_id(region: str, expected: str) -> str:
    """Event id from every packet's NATIVE_METADATA.json and its export NPZ; must equal the expected id."""
    ids = set()
    for pdir in pc.packet_dirs(region):
        ev = pc.packet_event_id(pdir)
        t = pdir.name
        exp = pc.INPUTS_ROOT / "latest_inputs_try02" / "exports" / ev / f"FORECAST_{t}.npz"
        with np.load(exp, allow_pickle=False) as z:
            ids.add(str(z["contract__event_id"]))
        ids.add(ev)
    if ids != {expected}:
        raise SystemExit("event id for %s: found %s, expected %s" % (region, ids, expected))
    return expected


def write_index(counts: dict):
    rows = []
    for meta in pc.REGIONS:
        region = meta["id"]
        g = pc.load_graph(region)
        bbox = [round(v, 6) for v in g.wgs84_bbox()]
        rows.append({
            "region_id": region,
            "name": {"ko": meta["name_ko"], "en": meta["name_en"]},
            "fire_year": meta["fire_year"],
            "event_id": verified_event_id(region, meta["expected_event"]),
            "bbox": bbox,
            "center": [round((bbox[0] + bbox[2]) / 2, 6), round((bbox[1] + bbox[3]) / 2, 6)],
            "zoom": fit_zoom(bbox),
            "demo": meta["demo"],
            "counts": counts[region],
        })
    pc.write_json(PUBLIC_REGIONS / "index.json", rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fetch-only", action="store_true")
    ap.add_argument("--refresh", action="append", default=[], help="re-download this region's extract")
    ap.add_argument("--regions", nargs="*", default=pc.REGION_IDS)
    args = ap.parse_args(argv)
    pc.require_assets()
    sources, failed = ensure_extracts(args.regions, refresh=set(args.refresh))
    if args.fetch_only:
        if failed:
            print("FAILED regions: %s" % failed, file=sys.stderr)
            return 2
        return 0
    counts = {}
    missing = [r for r in pc.REGION_IDS if r not in sources.get("regions", {})]
    for meta in pc.REGIONS:
        if meta["id"] in missing:
            print("skip    %s: no Overpass extract (%s)" % (meta["id"], failed.get(meta["id"], "missing")),
                  file=sys.stderr)
            continue
        counts[meta["id"]] = build_region(meta, sources)
    if missing:
        print("index.json not written: missing extracts for %s" % missing, file=sys.stderr)
        return 2
    write_index(counts)
    print("done    places for %d regions" % len(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
