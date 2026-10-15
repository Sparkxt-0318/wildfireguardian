#!/usr/bin/env python3
"""Download OpenStreetMap data for one area once, while online, and write it as the app's offline map data
(spec section 7): mapdata/<name>/roads.geojson, buildings.geojson, water.geojson, parks.geojson, meta.json, SOURCE.txt.

  python3 tools/fetch_mapdata.py --name gwangju_kdj --bbox 35.1382,126.8324,35.1516,126.8488
  python3 tools/fetch_mapdata.py --name walk_1 --around sessions/real/WFG-1A2B3C4D-000003_WALK.wfg --buffer-m 1200
  python3 tools/fetch_mapdata.py --name walk_1 --from-file export.osm          (a file saved from openstreetmap.org)

Sources, in order: the Overpass API (several public servers are tried), then the OpenStreetMap API's map call in tiles
of about 1 km (the one behind the Export button on openstreetmap.org). From mainland China either may need a VPN;
a downloaded extract (OSM XML, or Overpass JSON) can be converted with --from-file instead. The app itself never goes
online: it reads only these files.

Layers: roads (every highway=* way, with a class and a drawing width in metres), buildings (building=* ways and
multipolygons), water (natural=water areas, waterway=riverbank areas, waterway lines with a width), parks
(leisure=park, leisure=garden, landuse=grass). Geometry is simplified by 0.5 m and written in WGS84 with 6 decimals.
Data: (c) OpenStreetMap contributors, ODbL 1.0. SOURCE.txt records the date, the source and the area.
"""
import argparse
import datetime as dt
import json
import math
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
OSM_API = "https://api.openstreetmap.org/api/0.6/map?bbox=%.7f,%.7f,%.7f,%.7f"
USER_AGENT = "WildfireGuardian-field-logger-demo/2.1 (one-time map data download for an offline school project)"
TILE_DEG = 0.009            # about 1 km: well inside the OSM API's limits per request
SIMPLIFY_M = 0.5
ATTRIBUTION = {"ko": "© OpenStreetMap 기여자 · ODbL", "en": "© OpenStreetMap contributors · ODbL"}

# road class -> (kind used by the map style, drawing width in metres)
ROADS = {
    "motorway": ("major", 24), "trunk": ("major", 22), "primary": ("major", 18), "motorway_link": ("major", 10),
    "trunk_link": ("major", 10), "primary_link": ("major", 10),
    "secondary": ("art", 15), "tertiary": ("art", 12), "secondary_link": ("art", 8), "tertiary_link": ("art", 8),
    "residential": ("minor", 8), "unclassified": ("minor", 8), "living_street": ("minor", 6), "road": ("minor", 7),
    "service": ("minor", 5), "pedestrian": ("minor", 6), "busway": ("minor", 7),
    "footway": ("minor", 2.5), "path": ("minor", 2), "cycleway": ("minor", 2.5), "steps": ("minor", 2.5),
    "track": ("minor", 3), "bridleway": ("minor", 2), "corridor": ("minor", 2),
}
WATERWAYS = {"river": 24, "canal": 10, "stream": 4, "drain": 2.5, "ditch": 2, "brook": 3}
SKIP_HIGHWAY = {"proposed", "construction", "abandoned", "platform", "elevator", "bus_stop", "raceway"}


# ----------------------------------------------------------------------------- download
def overpass_query(bbox):
    s, w, n, e = bbox
    b = "%.7f,%.7f,%.7f,%.7f" % (s, w, n, e)
    parts = ['way["highway"](%s)', 'way["building"](%s)', 'relation["building"]["type"="multipolygon"](%s)',
             'way["natural"="water"](%s)', 'relation["natural"="water"](%s)', 'way["waterway"](%s)',
             'relation["waterway"="riverbank"](%s)', 'way["leisure"~"^(park|garden)$"](%s)',
             'relation["leisure"~"^(park|garden)$"](%s)', 'way["landuse"~"^(grass|reservoir|basin)$"](%s)']
    return "[out:json][timeout:120];(" + "".join(p % b + ";" for p in parts) + ");out geom;"


def _http(url, data=None, timeout=180):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_overpass(bbox, endpoints=None):
    q = overpass_query(bbox).encode()
    last = None
    for url in endpoints or OVERPASS:
        try:
            raw = _http(url, data=urllib.parse.urlencode({"data": q}).encode())
            obj = json.loads(raw.decode("utf-8"))
            if "elements" in obj:
                return obj, url
            last = "no elements in the reply from %s" % url
        except (OSError, ValueError) as ex:
            last = "%s: %s" % (url, ex)
            print("  overpass failed:", last, file=sys.stderr)
    raise RuntimeError(last or "no Overpass server answered")


def fetch_api(bbox):
    """The OSM API's map call, tile by tile; returns a list of OSM XML documents."""
    s, w, n, e = bbox
    docs = []
    lat = s
    while lat < n - 1e-9:
        lon = w
        while lon < e - 1e-9:
            t = (lat, lon, min(n, lat + TILE_DEG), min(e, lon + TILE_DEG))
            url = OSM_API % (t[1], t[0], t[3], t[2])
            for attempt in range(3):
                try:
                    docs.append(_http(url))
                    break
                except OSError as ex:
                    if attempt == 2:
                        raise RuntimeError("OSM API failed for %s: %s" % (url, ex))
                    time.sleep(2 + 3 * attempt)
            time.sleep(1.0)                     # be gentle with the OSM API
            lon += TILE_DEG
        lat += TILE_DEG
    return docs


# ----------------------------------------------------------------------------- one model for both formats
class Data:
    """ways: id -> {"tags", "coords" [(lon, lat)]}; relations: id -> {"tags", "members" [(role, id or None, coords)]}"""

    def __init__(self):
        self.ways = {}
        self.relations = {}


def read_overpass_json(obj, data=None):
    d = data or Data()
    for el in obj.get("elements", []):
        if el.get("type") == "way" and el.get("geometry"):
            d.ways[el["id"]] = {"tags": el.get("tags", {}), "coords": [(g["lon"], g["lat"]) for g in el["geometry"] if g]}
        elif el.get("type") == "relation":
            mem = []
            for m in el.get("members", []):
                if m.get("type") == "way" and m.get("geometry"):
                    mem.append((m.get("role") or "outer", m.get("ref"), [(g["lon"], g["lat"]) for g in m["geometry"] if g]))
            d.relations[el["id"]] = {"tags": el.get("tags", {}), "members": mem}
    return d


def read_osm_xml(raw, data=None):
    d = data or Data()
    root = ET.fromstring(raw)
    nodes = {n.get("id"): (float(n.get("lon")), float(n.get("lat"))) for n in root.iter("node") if n.get("lat")}
    d._nodes = getattr(d, "_nodes", {})
    d._nodes.update(nodes)
    pending = []
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        refs = [nd.get("ref") for nd in w.findall("nd")]
        wid = int(w.get("id"))
        prev = d.ways.get(wid)
        coords = [d._nodes[r] for r in refs if r in d._nodes]
        if len(coords) == len(refs) or not prev:
            d.ways[wid] = {"tags": tags, "coords": coords, "refs": refs}
    for r in root.iter("relation"):
        tags = {t.get("k"): t.get("v") for t in r.findall("tag")}
        mem = [(m.get("role") or "outer", int(m.get("ref")), None) for m in r.findall("member") if m.get("type") == "way"]
        pending.append((int(r.get("id")), tags, mem))
    for rid, tags, mem in pending:
        d.relations[rid] = {"tags": tags, "members": mem}
    return d


def _resolve_members(d):
    """Relations read from OSM XML name their member ways; take the coordinates from the ways we have."""
    for rel in d.relations.values():
        out = []
        for role, ref, coords in rel["members"]:
            if coords is None:
                w = d.ways.get(ref)
                if not w or len(w["coords"]) < 2:
                    continue
                coords = w["coords"]
            out.append((role, ref, coords))
        rel["members"] = out


# ----------------------------------------------------------------------------- geometry
def _metres(lat0):
    ky = 111320.0
    return ky * math.cos(math.radians(lat0)), ky


def simplify(coords, tol_m=SIMPLIFY_M):
    """Douglas-Peucker in a local metric frame; keeps the first and last point."""
    if len(coords) < 3:
        return list(coords)
    kx, ky = _metres(coords[0][1])
    pts = [(x * kx, y * ky) for x, y in coords]
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        L = math.hypot(dx, dy)
        best, idx = 0.0, None
        for i in range(a + 1, b):
            px, py = pts[i]
            dd = abs(dy * (px - x1) - dx * (py - y1)) / L if L > 0 else math.hypot(px - x1, py - y1)
            if dd > best:
                best, idx = dd, i
        if idx is not None and best > tol_m:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    return [c for c, k in zip(coords, keep) if k]


def _r(coords):
    return [[round(x, 6), round(y, 6)] for x, y in coords]


def _closed(coords):
    return len(coords) >= 4 and coords[0] == coords[-1]


def join_rings(segments):
    """Join way segments that share end points into closed rings (multipolygon members); unclosed pieces are dropped."""
    segs = [list(s) for s in segments if len(s) >= 2]
    rings = []
    while segs:
        ring = segs.pop(0)
        changed = True
        while not _closed(ring) and changed:
            changed = False
            for i, s in enumerate(segs):
                if s[0] == ring[-1]:
                    ring += s[1:]
                elif s[-1] == ring[-1]:
                    ring += s[::-1][1:]
                elif s[-1] == ring[0]:
                    ring = s + ring[1:]
                elif s[0] == ring[0]:
                    ring = s[::-1] + ring[1:]
                else:
                    continue
                segs.pop(i)
                changed = True
                break
        if _closed(ring):
            rings.append(ring)
    return rings


def _inside(pt, ring):
    x, y = pt
    c = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


def _polygon(outer, inners=()):
    ring = simplify(outer)
    if not _closed(ring):
        return None
    rings = [_r(ring)] + [_r(simplify(h)) for h in inners if _closed(simplify(h))]
    return {"type": "Polygon", "coordinates": rings}


def _feature(geom, props):
    return {"type": "Feature", "properties": props, "geometry": geom}


def _is_building(t):
    return t.get("building") not in (None, "no")


def _is_water(t):
    return t.get("natural") == "water" or t.get("waterway") == "riverbank" or t.get("landuse") in ("reservoir", "basin")


def _is_park(t):
    return t.get("leisure") in ("park", "garden") or t.get("landuse") == "grass"


def convert(d):
    """Data -> {layer: FeatureCollection}."""
    _resolve_members(d)
    layers = {k: [] for k in ("roads", "buildings", "water", "parks")}
    for rel in d.relations.values():
        t = rel["tags"]
        if t.get("type") != "multipolygon":
            continue
        target = "buildings" if _is_building(t) else "water" if _is_water(t) else "parks" if _is_park(t) else None
        if not target:
            continue
        outers = join_rings([c for role, _, c in rel["members"] if role == "outer"])
        inners = join_rings([c for role, _, c in rel["members"] if role == "inner"])
        for o in outers:
            holes = [h for h in inners if _inside(h[0], o)]
            g = _polygon(o, holes)
            if g:
                layers[target].append(_feature(g, {"kind": target}))
    for wid, w in d.ways.items():
        t, c = w["tags"], w["coords"]
        if len(c) < 2:
            continue
        hw = t.get("highway")
        if hw and hw not in SKIP_HIGHWAY and t.get("area") != "yes":
            kind, width = ROADS.get(hw, ("minor", 4))
            layers["roads"].append(_feature({"type": "LineString", "coordinates": _r(simplify(c))},
                                            {"kind": kind, "w": width, "hw": hw}))
            continue
        if t.get("waterway") in WATERWAYS and not _closed(c):
            layers["water"].append(_feature({"type": "LineString", "coordinates": _r(simplify(c))},
                                            {"kind": t["waterway"], "w": WATERWAYS[t["waterway"]]}))
            continue
        if not _closed(c):
            continue
        target = "buildings" if _is_building(t) else "water" if _is_water(t) else "parks" if _is_park(t) else None
        if target:
            g = _polygon(c)
            if g:
                layers[target].append(_feature(g, {"kind": target}))
    return {k: {"type": "FeatureCollection", "features": v} for k, v in layers.items()}


# ----------------------------------------------------------------------------- the area
def bbox_around(session_file, buffer_m):
    from app import session
    s = session.load_any(session_file)
    fixes = [r for r in s.rows if r["fix"] and r["lat"] is not None]
    if not fixes:
        raise SystemExit("%s has no fixes: nothing to centre the map on" % session_file)
    lats, lons = [r["lat"] for r in fixes], [r["lon"] for r in fixes]
    lat0 = (min(lats) + max(lats)) / 2
    dlat = buffer_m / 111320.0
    dlon = buffer_m / (111320.0 * math.cos(math.radians(lat0)))
    return (min(lats) - dlat, min(lons) - dlon, max(lats) + dlat, max(lons) + dlon)


def parse_bbox(text):
    try:
        s, w, n, e = (float(x) for x in text.split(","))
    except ValueError:
        raise SystemExit("--bbox needs S,W,N,E in degrees, for example 35.1382,126.8324,35.1516,126.8488")
    if not (-90 <= s < n <= 90 and -180 <= w < e <= 180):
        raise SystemExit("--bbox: south must be below north and west left of east")
    return s, w, n, e


def write_area(out_dir, name, layers, bbox, source, query):
    out_dir.mkdir(parents=True, exist_ok=True)
    for k, fc in layers.items():
        (out_dir / ("%s.geojson" % k)).write_text(json.dumps(fc, separators=(",", ":"), ensure_ascii=False),
                                                 encoding="utf-8")
    s, w, n, e = bbox
    meta = {"name": name, "synthetic": False, "center": [round((w + e) / 2, 6), round((s + n) / 2, 6)],
            "bounds": [round(w, 7), round(s, 7), round(e, 7), round(n, 7)], "attribution": ATTRIBUTION,
            "source": source, "fetched": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "counts": {k: len(v["features"]) for k, v in layers.items()}, "layers": sorted(layers)}
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "SOURCE.txt").write_text(
        "Map data for the area \"%s\": OpenStreetMap, downloaded %s by tools/fetch_mapdata.py.\n"
        "Source: %s\nArea (S,W,N,E): %.7f,%.7f,%.7f,%.7f\nQuery: %s\n"
        "© OpenStreetMap contributors. The data is available under the Open Database License (ODbL) 1.0:\n"
        "https://www.openstreetmap.org/copyright\n" % (name, meta["fetched"], source, s, w, n, e, query),
        encoding="utf-8")
    return meta


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--name", required=True, help="folder name under mapdata/ (letters, digits, _ and -)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--bbox", help="S,W,N,E in degrees")
    g.add_argument("--around", help="a session file (.wfg, .csv or .gpx): its fixes plus --buffer-m")
    ap.add_argument("--buffer-m", type=float, default=1200.0)
    ap.add_argument("--from-file", help="convert a saved OSM XML (.osm) or Overpass JSON (.json) instead of downloading")
    ap.add_argument("--source", choices=("auto", "overpass", "api"), default="auto")
    ap.add_argument("--endpoint", action="append", help="an Overpass interpreter URL to try (repeatable)")
    ap.add_argument("--out", default=str(ROOT / "mapdata"))
    a = ap.parse_args(argv)
    if not all(ch.isalnum() or ch in "_-" for ch in a.name):
        raise SystemExit("--name: letters, digits, _ and - only")
    if a.bbox:
        bbox = parse_bbox(a.bbox)
    elif a.from_file and not a.around:
        bbox = None
    else:
        bbox = bbox_around(a.around, a.buffer_m)
    d = Data()
    if a.from_file:
        raw = Path(a.from_file).read_bytes()
        if raw.lstrip()[:1] == b"{":
            d = read_overpass_json(json.loads(raw.decode("utf-8")))
        else:
            d = read_osm_xml(raw)
        source, query = "file " + Path(a.from_file).name, "-"
    else:
        query = overpass_query(bbox)
        got = None
        if a.source in ("auto", "overpass"):
            try:
                obj, url = fetch_overpass(bbox, a.endpoint)
                d, source, got = read_overpass_json(obj), "Overpass API " + url, True
            except RuntimeError as ex:
                if a.source == "overpass":
                    raise SystemExit("Overpass: %s" % ex)
                print("Overpass did not answer; trying the OpenStreetMap API.", file=sys.stderr)
        if not got:
            for raw in fetch_api(bbox):
                read_osm_xml(raw, d)
            source = "OpenStreetMap API 0.6 map call, %.3f degree tiles" % TILE_DEG
            query = "highway, building, natural=water, waterway, leisure=park|garden, landuse=grass (filtered locally)"
    layers = convert(d)
    if bbox is None:
        xs = [x for fc in layers.values() for f in fc["features"] for x, _ in _coords(f["geometry"])]
        ys = [y for fc in layers.values() for f in fc["features"] for _, y in _coords(f["geometry"])]
        if not xs:
            raise SystemExit("nothing usable in %s" % a.from_file)
        bbox = (min(ys), min(xs), max(ys), max(xs))
    meta = write_area(Path(a.out) / a.name, a.name, layers, bbox, source, query)
    print("wrote %s: %s" % (Path(a.out) / a.name, ", ".join("%s %d" % kv for kv in meta["counts"].items())))


def _coords(g):
    if g["type"] == "LineString":
        return g["coordinates"]
    return [p for ring in g["coordinates"] for p in ring]


if __name__ == "__main__":
    main()
