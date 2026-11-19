"""Geocode NIST record locations to points on the Overture road network (PROTOCOL.md amendments 9-10).
Usage: python3 -I geocode.py SEGMENTS.parquet PLACES.parquet PROGRESSION_ROWS.csv BURNOVERS.csv CLOSURE_ROWS.csv OUT_DIR
Outputs OUT_DIR/geocoded_{progression,burnovers,closures}.csv (x, y in EPSG:32610, lon, lat, rule) and a coverage summary."""
import csv, json, re, sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import shapely
from pyproj import Transformer
from shapely.geometry import Point
from shapely.ops import nearest_points, unary_union

SEG, PLC, PROG, BO, CLO, OUT = sys.argv[1:7]
OUT = Path(OUT); OUT.mkdir(parents=True, exist_ok=True)
TO_UTM = Transformer.from_crs(4326, 32610, always_xy=True); TO_LL = Transformer.from_crs(32610, 4326, always_xy=True)
GRAPH_CLASSES = {"motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "living_street"}
SUFFIX = {"road": "rd", "lane": "ln", "drive": "dr", "court": "ct", "circle": "cir", "avenue": "ave", "street": "st", "boulevard": "blvd",
          "highway": "hwy", "place": "pl", "trail": "trl", "terrace": "ter", "parkway": "pkwy"}


def norm(s):
    s = re.sub(r"[^\w\s]", " ", s.lower())
    return " ".join(SUFFIX.get(w, w) for w in s.split())


# ---- named road geometries (UTM), all graph classes (service excluded)
t = pq.read_table(SEG, columns=["names", "class", "subtype", "geometry"])
by = {}
for nm, cl, st, g in zip(t.column("names").to_pylist(), t.column("class").to_pylist(), t.column("subtype").to_pylist(), t.column("geometry").to_pylist()):
    if st != "road" or cl not in GRAPH_CLASSES or not nm or not nm.get("primary"):
        continue
    geom = shapely.from_wkb(g)
    xs, ys = TO_UTM.transform(*zip(*geom.coords)) if geom.geom_type == "LineString" else (None, None)
    if xs is None:
        continue
    by.setdefault(norm(nm["primary"]), []).append(shapely.LineString(list(zip(xs, ys))))
ROADS = {k: unary_union(v) for k, v in by.items()}
NAMES = sorted(ROADS, key=len, reverse=True)
# ---- named places (UTM)
pt = pq.read_table(PLC, columns=["names", "geometry"])
PLACES = {}
for nm, g in zip(pt.column("names").to_pylist(), pt.column("geometry").to_pylist()):
    if nm and nm.get("primary") and len(nm["primary"]) >= 8:
        p = shapely.from_wkb(g)
        x, y = TO_UTM.transform(p.x, p.y)
        PLACES.setdefault(norm(nm["primary"]), []).append(Point(x, y))
PARADISE = Point(*TO_UTM.transform(-121.62, 39.76))
print("road names", len(ROADS), "place names", len(PLACES))


def names_in(text):
    """Road names of the Overture network occurring in the text, in reading order, longest-name-first matching, no overlaps."""
    s = " " + norm(text) + " "
    found = []
    for n in NAMES:
        if len(n) < 4:
            continue
        for m in re.finditer(r"(?<= )" + re.escape(n) + r"(?= )", s):
            if not any(m.start() < e and m.end() > b for b, e, _ in found):
                found.append((m.start(), m.end(), n))
    out = []
    for _, _, n in sorted(found):  # distinct names only (amendment 11)
        if n not in out:
            out.append(n)
    return out


def closest(a, b, maxd=150.0):
    pa, pb = nearest_points(ROADS[a], ROADS[b])
    return ((pa.x + pb.x) / 2, (pa.y + pb.y) / 2) if pa.distance(pb) <= maxd else None


def place_in(text):
    s = " " + norm(text) + " "
    for n in sorted(PLACES, key=len, reverse=True):
        if " " + n + " " in s:
            return min(PLACES[n], key=lambda p: p.distance(PARADISE))
    return None


def geocode(text):
    text = re.sub(r"\b[A-Z]{2,4}-\d+,?", " ", text.replace("/", " and "))
    nm = names_in(text)
    low = " " + norm(text) + " "
    if len(nm) >= 3 and " between " in low:
        a, b, c = nm[:3]
        p, q = closest(a, b), closest(a, c)
        if p and q:
            return (p[0] + q[0]) / 2, (p[1] + q[1]) / 2, "between-midpoint"
        return None
    if len(nm) >= 2 and nm[0] != nm[1]:
        p = closest(nm[0], nm[1])
        if p:
            return p[0], p[1], "road-road"
    pl = place_in(text)
    if pl is not None and len(nm) >= 1 and ROADS[nm[0]].distance(pl) <= 300:
        return pl.x, pl.y, "road+place"
    if pl is not None and len(nm) == 0:
        return pl.x, pl.y, "place"
    return None


def closure_sentence(text):
    """Amendment 11: first sentence of a closure row that contains clos|block|impass (else the whole text)."""
    for s in re.split(r"(?<=[.!?])\s+", text):
        if re.search(r"clos|block|impass", s, re.I):
            return s
    return text


def run(path, textcol, keep, out, label):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    res, n = [], 0
    for r in rows:
        g = geocode(closure_sentence(r[textcol]) if label == "closures" else r[textcol])
        d = dict(r)
        if g:
            lon, lat = TO_LL.transform(g[0], g[1])
            d.update(x=round(g[0], 1), y=round(g[1], 1), lon=round(lon, 6), lat=round(lat, 6), rule=g[2]); n += 1
        else:
            d.update(x="", y="", lon="", lat="", rule="NOT GEOCODED")
        res.append(d)
    with open(OUT / out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, list(res[0].keys())); w.writeheader(); w.writerows(res)
    return {"rows": len(rows), "geocoded": n}


cov = {"progression": run(PROG, "location", None, "geocoded_progression.csv", "progression"),
       "burnovers": run(BO, "place", None, "geocoded_burnovers.csv", "burnovers"),
       "closures": run(CLO, "text", None, "geocoded_closures.csv", "closures")}
(OUT / "geocode_coverage.json").write_text(json.dumps(cov, indent=1))
print(json.dumps(cov))
