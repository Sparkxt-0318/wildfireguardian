"""Synthetic city for SIM sessions ("sim_city"): a rotated street grid with blocks, buildings, a park, a river and an
arterial network out to about 6 km. It is not OpenStreetMap data and is labelled as simulated wherever it is shown.
Written as GeoJSON in WGS84, like the map data that tools/fetch_mapdata.py writes for real areas.
"""
import json
import math
import random

from .geo import Local

AREA = "sim_city"
CENTER = (35.1470, 126.8390)     # placed at the Gwangju venue test area; the streets themselves are invented
BLOCK = 150.0                     # metres
ROT = math.radians(-16.0)
CORE = 9                          # core grid: roads at -9..9 blocks
REGION = 42                       # arterials out to 42 blocks (6.3 km)
ART_STEP = 7                      # an arterial every 7 blocks (1,050 m)
W_MAJOR, W_MINOR, W_ART = 14.0, 8.0, 18.0
RIVER_W = 46.0
PARK = ((-3, -2), (-2, -1))       # park block in grid units (u0, v0), (u1, v1)


def g2m(u, v):
    """Grid units -> metres (x east, y north) in the rotated grid."""
    x, y = u * BLOCK, v * BLOCK
    return (x * math.cos(ROT) - y * math.sin(ROT), x * math.sin(ROT) + y * math.cos(ROT))


def river_control():
    pts = []
    for k, u in enumerate(range(-REGION, REGION + 1, 6)):
        v = 0.12 + 0.28 * math.sin(k * 0.9) + (0.15 if k % 2 else -0.1)
        pts.append((u, v))
    return pts


def catmull(points, steps=12):
    out = []
    for i in range(len(points) - 1):
        p0 = points[i - 1] if i > 0 else points[i]
        p1, p2 = points[i], points[i + 1]
        p3 = points[i + 2] if i + 2 < len(points) else points[i + 1]
        for s in range(steps):
            t = s / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    out.append(points[-1])
    return out


def river_line_m():
    return [g2m(u, v) for u, v in catmull(river_control())]


def build(seed=11):
    """Return {layer: FeatureCollection} plus meta for the synthetic city."""
    rnd = random.Random(seed)
    loc = Local(*CENTER)

    def ll(pt):
        lat, lon = loc.ll(*pt)
        return [round(lon, 7), round(lat, 7)]

    def line(pts, **props):
        return {"type": "Feature", "properties": props, "geometry": {"type": "LineString",
                                                                       "coordinates": [ll(p) for p in pts]}}

    def poly(pts, **props):
        ring = [ll(p) for p in pts] + [ll(pts[0])]
        return {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [ring]}}

    roads, blocks, bldgs, parks, water = [], [], [], [], []
    for k in range(-CORE, CORE + 1):
        w = W_MAJOR if k % 2 == 0 else W_MINOR
        kind = "major" if k % 2 == 0 else "minor"
        roads.append(line([g2m(k, -CORE), g2m(k, CORE)], kind=kind, w=w))
        roads.append(line([g2m(-CORE, k), g2m(CORE, k)], kind=kind, w=w))
    for k in range(-REGION, REGION + 1, ART_STEP):
        roads.append(line([g2m(k, -REGION), g2m(k, REGION)], kind="major", w=W_ART))
        roads.append(line([g2m(-REGION, k), g2m(REGION, k)], kind="major", w=W_ART))
    ins = 0.075
    (pu0, pv0), (pu1, pv1) = PARK
    for i in range(-CORE + 1, CORE - 1):
        for j in range(-CORE + 1, CORE - 1):
            blk = [g2m(i + ins, j + ins), g2m(i + 1 - ins, j + ins), g2m(i + 1 - ins, j + 1 - ins), g2m(i + ins, j + 1 - ins)]
            if (i, j) == (pu0, pv0):
                parks.append(poly(blk, kind="park"))
                continue
            blocks.append(poly(blk, kind="block"))
            for _ in range(rnd.randint(3, 6)):
                u0 = i + ins + 0.04 + rnd.random() * 0.5
                v0 = j + ins + 0.04 + rnd.random() * 0.5
                u1 = min(u0 + 0.1 + rnd.random() * 0.3, i + 1 - ins - 0.04)
                v1 = min(v0 + 0.1 + rnd.random() * 0.3, j + 1 - ins - 0.04)
                if u1 - u0 > 0.07 and v1 - v0 > 0.07:
                    bldgs.append(poly([g2m(u0, v0), g2m(u1, v0), g2m(u1, v1), g2m(u0, v1)], kind="building"))
    # a second park outside the core, so the region has some texture
    parks.append(poly([g2m(14.2, 7.2), g2m(20.8, 7.2), g2m(20.8, 13.8), g2m(14.2, 13.8)], kind="park"))
    # river as a polygon: offset the centre line by half its width on both sides
    c = river_line_m()
    left, right = [], []
    for i, (x, y) in enumerate(c):
        a = c[max(0, i - 1)]
        b = c[min(len(c) - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        n = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / n, dx / n
        left.append((x + nx * RIVER_W / 2, y + ny * RIVER_W / 2))
        right.append((x - nx * RIVER_W / 2, y - ny * RIVER_W / 2))
    water.append(poly(left + right[::-1], kind="river"))
    fc = lambda feats: {"type": "FeatureCollection", "features": feats}   # noqa: E731
    lo = loc.ll(*g2m(-REGION, -REGION))
    hi = loc.ll(*g2m(REGION, REGION))
    corners = [loc.ll(*g2m(a, b)) for a in (-REGION, REGION) for b in (-REGION, REGION)]
    meta = {"name": AREA, "synthetic": True, "center": [CENTER[1], CENTER[0]],
            "bounds": [min(p[1] for p in corners), min(p[0] for p in corners), max(p[1] for p in corners),
                       max(p[0] for p in corners)],
            "attribution": {"ko": "모의 지도 · 가상 도로", "en": "Simulated map · synthetic streets"},
            "source": "app/mapgen.py (seed %d); invented streets, not OpenStreetMap" % seed}
    del lo, hi
    return {"roads": fc(roads), "blocks": fc(blocks), "buildings": fc(bldgs), "parks": fc(parks),
            "water": fc(water)}, meta


def write(area_dir, seed=11):
    area_dir.mkdir(parents=True, exist_ok=True)
    layers, meta = build(seed)
    for name, fcoll in layers.items():
        (area_dir / (name + ".geojson")).write_text(json.dumps(fcoll, separators=(",", ":")), encoding="utf-8")
    (area_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (area_dir / "SOURCE.txt").write_text(
        "Synthetic city for SIM sessions, generated by app/mapgen.py (seed %d).\n"
        "Invented streets and buildings placed near the Gwangju venue test area. Not OpenStreetMap data.\n"
        "Shown with the attribution \"모의 지도 · 가상 도로\" / \"Simulated map · synthetic streets\".\n" % seed,
        encoding="utf-8")
    return meta
