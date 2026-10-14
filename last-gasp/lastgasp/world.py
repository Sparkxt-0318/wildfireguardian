"""Synthetic world: roads, buildings and substation in a local metric frame.

Real OpenStreetMap roads, mapped buildings and the mapped substation are used
when the OSM extract is available. OSM building coverage in rural Gyeongbuk is
sparse, so additional synthetic buildings are placed along real roads to reach
a plausible building count. If no OSM data can be loaded, a fully synthetic
road layout is generated instead and the world is flagged as such.
"""
from __future__ import annotations

import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON_EQ = 111_320.0


def lonlat_to_xy(lon, lat, lon0, lat0):
    """Local equirectangular projection (error well below 1 m over a few km)."""
    x = (np.asarray(lon) - lon0) * M_PER_DEG_LON_EQ * math.cos(math.radians(lat0))
    y = (np.asarray(lat) - lat0) * M_PER_DEG_LAT
    return x, y


def parse_osm(path: str | Path, bbox, road_classes):
    """Parse an OSM XML extract into roads, buildings and substations (metres)."""
    lon0, lat0, lon1, lat1 = bbox
    tree = ET.parse(path)
    root = tree.getroot()
    nodes = {}
    node_tags = {}
    for n in root.iter("node"):
        nid = int(n.get("id"))
        nodes[nid] = (float(n.get("lon")), float(n.get("lat")))
        tags = {t.get("k"): t.get("v") for t in n.findall("tag")}
        if tags:
            node_tags[nid] = tags

    def xy(nid):
        lon, lat = nodes[nid]
        x, y = lonlat_to_xy(lon, lat, lon0, lat0)
        return float(x), float(y)

    roads, buildings, substations = [], [], []
    for w in root.iter("way"):
        tags = {t.get("k"): t.get("v") for t in w.findall("tag")}
        refs = [int(nd.get("ref")) for nd in w.findall("nd")]
        refs = [r for r in refs if r in nodes]
        if len(refs) < 2:
            continue
        if tags.get("highway") in road_classes:
            roads.append({"osm_id": int(w.get("id")), "highway": tags["highway"],
                          "node_ids": refs, "xy": [xy(r) for r in refs]})
        elif "building" in tags:
            ring = refs[:-1] if refs[0] == refs[-1] else refs
            pts = np.array([xy(r) for r in ring])
            cx, cy = pts.mean(axis=0)
            buildings.append({"x": float(cx), "y": float(cy), "kind": tags["building"],
                              "source": "osm", "osm_id": int(w.get("id"))})
        elif tags.get("power") == "substation":
            pts = np.array([xy(r) for r in refs])
            cx, cy = pts.mean(axis=0)
            substations.append({"x": float(cx), "y": float(cy), "name": tags.get("name:en", tags.get("name", "")),
                                "osm_id": int(w.get("id"))})
    for nid, tags in node_tags.items():
        if "building" in tags:
            x, y = xy(nid)
            buildings.append({"x": x, "y": y, "kind": tags["building"], "source": "osm", "osm_id": nid})
        if tags.get("power") == "substation":
            x, y = xy(nid)
            substations.append({"x": x, "y": y, "name": tags.get("name:en", ""), "osm_id": nid})
    width, _ = lonlat_to_xy(lon1, lat0, lon0, lat0)
    _, height = lonlat_to_xy(lon0, lat1, lon0, lat0)
    return {"roads": roads, "buildings": buildings, "substations": substations,
            "width_m": float(width), "height_m": float(height)}


def synthetic_roads(width, height, rng):
    """Fallback road layout: one main road, a few cross roads and spurs."""
    roads = []
    nid = [0]

    def add(pts, cls):
        ids = list(range(nid[0], nid[0] + len(pts)))
        nid[0] += len(pts)
        roads.append({"osm_id": -len(roads) - 1, "highway": cls, "node_ids": ids, "xy": [tuple(p) for p in pts]})

    ym = height * 0.5
    xs = np.linspace(0, width, 40)
    add([(x, ym + 80 * math.sin(x / 400)) for x in xs], "primary")
    for xc in np.linspace(width * 0.15, width * 0.85, 5):
        ys = np.linspace(height * 0.1, height * 0.9, 30)
        add([(xc + 40 * math.sin(y / 300), y) for y in ys], "residential")
    # Shared node ids are not created here; intersections are snapped later by distance.
    return roads


def place_buildings(roads, existing, width, height, cfg, rng):
    """Place synthetic buildings along roads, weighted by road class and a smooth cluster field."""
    n_target = cfg["n_buildings_target"]
    n_new = max(0, n_target - len(existing))
    weights = cfg["synthetic_building_road_weight"]
    lo, hi = cfg["synthetic_building_offset_m"]
    min_sp = cfg["synthetic_building_min_spacing_m"]
    margin = cfg["edge_margin_m"]

    # Smooth lognormal settlement-density field on a 25 m grid.
    cell = 25.0
    nx, ny = int(width / cell) + 1, int(height / cell) + 1
    g = gaussian_filter(rng.standard_normal((ny, nx)), cfg["synthetic_cluster_corr_m"] / cell)
    g = (g - g.mean()) / (g.std() + 1e-12)
    dens = np.exp(cfg["synthetic_cluster_sigma"] * g)

    segs = []
    for r in roads:
        w = weights.get(r["highway"], 0.5)
        pts = np.asarray(r["xy"])
        for a, b in zip(pts[:-1], pts[1:]):
            L = float(np.hypot(*(b - a)))
            if L > 0.5:
                segs.append((a, b, L, w))
    seg_w = np.array([s[2] * s[3] for s in segs])
    seg_w = seg_w / seg_w.sum()

    placed = [(b["x"], b["y"]) for b in existing]
    out = []
    tree_pts = list(placed)
    tree = cKDTree(tree_pts) if tree_pts else None
    attempts = 0
    pending = []
    while len(out) < n_new and attempts < n_new * 60:
        attempts += 1
        a, b, L, _ = segs[rng.choice(len(segs), p=seg_w)]
        t = rng.random()
        p = a + t * (b - a)
        d = (b - a) / L
        nrm = np.array([-d[1], d[0]]) * (1 if rng.random() < 0.5 else -1)
        q = p + nrm * rng.uniform(lo, hi)
        if not (margin <= q[0] <= width - margin and margin <= q[1] <= height - margin):
            continue
        ix, iy = int(q[0] / cell), int(q[1] / cell)
        if rng.random() > dens[iy, ix] / dens.max() * 3.0:
            continue
        if tree is not None and tree.query(q)[0] < min_sp:
            continue
        if pending and np.min(np.hypot(*(np.asarray(pending) - q).T)) < min_sp:
            continue
        pending.append(q)
        out.append({"x": float(q[0]), "y": float(q[1]), "kind": "synthetic", "source": "synthetic"})
        if len(pending) >= 200:
            tree_pts.extend(pending)
            tree = cKDTree(tree_pts)
            pending = []
    return out


def build_world(cfg_world, root: Path, allow_download=True):
    """Return the world dict, creating data/processed/... from OSM or a synthetic fallback."""
    proc = root / cfg_world["processed"]
    if proc.exists():
        return json.loads(proc.read_text())
    rng = np.random.default_rng(cfg_world["building_seed"])
    raw = root / cfg_world["osm_raw"]
    bbox = cfg_world["bbox_lonlat"]
    source = "osm"
    note = ""
    try:
        if not raw.exists() and allow_download:
            from .fetch import fetch_osm_map
            fetch_osm_map(bbox, raw)
        osm = parse_osm(raw, bbox, set(cfg_world["road_classes"]))
        if len(osm["roads"]) < 10:
            raise RuntimeError("too few OSM roads")
    except Exception as exc:  # fall back to a synthetic layout and say so
        source = "synthetic"
        note = f"OSM unavailable ({exc}); fully synthetic layout used."
        lon0, lat0, lon1, lat1 = bbox
        w, _ = lonlat_to_xy(lon1, lat0, lon0, lat0)
        _, h = lonlat_to_xy(lon0, lat1, lon0, lat0)
        osm = {"roads": synthetic_roads(float(w), float(h), rng), "buildings": [], "substations": [],
               "width_m": float(w), "height_m": float(h)}
    W, H = osm["width_m"], osm["height_m"]
    real = [b for b in osm["buildings"] if 0 <= b["x"] <= W and 0 <= b["y"] <= H]
    synth = place_buildings(osm["roads"], real, W, H, cfg_world, rng)
    subs = osm["substations"] or [{"x": W * 0.9, "y": H * 0.2, "name": "synthetic substation", "osm_id": None}]
    world = {
        "source": source,
        "note": note,
        "area_name": cfg_world["area_name"],
        "bbox_lonlat": bbox,
        "width_m": W,
        "height_m": H,
        "roads": [{"highway": r["highway"], "node_ids": r["node_ids"], "xy": r["xy"]} for r in osm["roads"]],
        "buildings": real + synth,
        "n_osm_buildings": len(real),
        "n_synthetic_buildings": len(synth),
        "substation": subs[0],
        "attribution": "Roads, mapped buildings and substation: (c) OpenStreetMap contributors, ODbL 1.0" if source == "osm" else "synthetic",
    }
    proc.parent.mkdir(parents=True, exist_ok=True)
    proc.write_text(json.dumps(world))
    return world
