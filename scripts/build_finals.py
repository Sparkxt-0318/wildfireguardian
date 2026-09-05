#!/usr/bin/env python3
"""Build ``web/finals.html`` — the finals presentation screen.

One static file, three regions, zero network. The screen is a *presentation*
layer only: every number and every geometry is read from the canonical
artifacts at build time and embedded as one JSON payload. Nothing is typed
into the template, and the builder never writes into ``data/processed``
(``make baseline-verify`` freezes that tree).

Sources (see docs/finals_demo_plan.md for the full lineage table):
- region table + comparison figures  data/processed/multi_region_comparison.json
- per-region scan geometry           newest replay run's viz.json (same
                                     selection logic as the operator console)
- hazard-over-time                   the region's canonical npz, banded with
                                     build_operator_screen.quantise
- road geometry                      data/snapshots/osm-walk_*.graphml.gz
                                     (the same snapshots the routing consumed)
- terrain                            data/snapshots/srtm-dem_*.tif
- evidence numbers                   docs/NUMBERS.json entries, carried with
                                     their source_file/json_path/derivation
- intervals / calibration / baselines  the three committed artifacts, read
                                     directly (they are not registry entries)

Derived-at-build (not a committed artifact, and labelled as such on screen):
per-road-segment first-crossing times of the hazard field at the two
thresholds the pipeline itself uses — 0.50 (p_cut: impassable to the walking
router) and 0.30 (the console's amber band). Sampling is HazardSequence's own
bilinear-in-space / linear-in-time rule, on a 10-minute grid (the routing's
time_step_min).

``--verify`` runs the fast repository gates and records their REAL exit
status into the payload; without it the SYSTEM INTEGRITY panel says the
gates were not run by this build, which is the honest rendering.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import io
import json
import math
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

from build_console import (  # noqa: E402  (single-source shared constants)
    BUCKETS, _coverage_pct, _dash_safe, _label_kr, newest_run,
)
from build_operator_screen import (  # noqa: E402
    BAND_FILLS, BAND_LABELS, quantise,
)
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402

TEMPLATE = REPO / "scripts" / "finals.template.html"
OUT = REPO / "web" / "finals.html"
PLACEHOLDER = "/*__" + "DATA" + "__*/"  # never appears verbatim in this file

#: The two thresholds the pipeline itself applies to this field. 0.50 is
#: parameters.p_cut in every canonical routing artifact; 0.30 is the lower
#: bound of the console's amber band (build_operator_screen.BANDS[1]).
P_CLOSED = 0.50
P_RISK = 0.30
#: The routing scan's own time grid (parameters.time_step_min = 10).
T_STEP_MIN = 10
T_MAX_MIN = 720

# --------------------------------------------------------------------------
# snapshot resolution
# --------------------------------------------------------------------------


def _slug(region: str) -> str:
    return region.replace("_", "-")


def snapshot_path(region: str, source: str) -> Path:
    """Resolve a committed snapshot file for ``region`` via the MANIFEST."""
    manifest = json.loads(
        (REPO / "data" / "snapshots" / "MANIFEST.json").read_text(encoding="utf-8"))
    hits = [s for s in manifest["snapshots"]
            if s.get("source") == source and s.get("region") == _slug(region)]
    if not hits:
        raise SystemExit(f"no {source} snapshot recorded for {region}")
    hits.sort(key=lambda s: s["snapshot_file"])
    name = hits[-1]["snapshot_file"]
    for candidate in (name, name + ".gz"):
        p = REPO / "data" / "snapshots" / candidate
        if p.exists():
            return p
    raise SystemExit(f"snapshot file missing on disk: {name}")


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------


class View:
    """EPSG:5179 content box -> viewBox units (x right, y down, 1000 wide)."""

    def __init__(self, x0: float, y0: float, x1: float, y1: float):
        pad = 0.04 * max(x1 - x0, y1 - y0)
        self.x0, self.y0 = x0 - pad, y0 - pad
        self.x1, self.y1 = x1 + pad, y1 + pad
        self.scale = 1000.0 / (self.x1 - self.x0)
        self.vh = round((self.y1 - self.y0) * self.scale)

    def px(self, x: float) -> float:
        return round((x - self.x0) * self.scale, 1)

    def py(self, y: float) -> float:
        return round((self.y1 - y) * self.scale, 1)

    def pt(self, x: float, y: float) -> list[float]:
        return [self.px(x), self.py(y)]


def _parse_linestring(wkt: str) -> list[tuple[float, float]] | None:
    m = re.match(r"\s*LINESTRING\s*\((.+)\)\s*$", wkt)
    if not m:
        return None
    pts = []
    for pair in m.group(1).split(","):
        xs, ys = pair.split()[:2]
        pts.append((float(xs), float(ys)))
    return pts


def _simplify(pts: list[tuple[float, float]], tol_m: float = 12.0):
    if len(pts) <= 2:
        return pts
    from shapely.geometry import LineString
    line = LineString(pts).simplify(tol_m, preserve_topology=False)
    return list(line.coords)


_HW_MAJOR = {"motorway", "trunk", "primary", "secondary", "motorway_link",
             "trunk_link", "primary_link", "secondary_link"}
_HW_MID = {"tertiary", "tertiary_link", "unclassified", "residential",
           "living_street", "road"}


def _hw_class(value) -> int:
    text = str(value)
    for token in re.findall(r"[a-z_]+", text):
        if token in _HW_MAJOR:
            return 2
    for token in re.findall(r"[a-z_]+", text):
        if token in _HW_MID:
            return 1
    return 0


def load_walk_edges(region: str) -> list[dict]:
    """Unique undirected walk edges with polylines in EPSG:5179 metres."""
    import networkx as nx
    path = snapshot_path(region, "osm-walk")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rb") as fh:
        graph = nx.read_graphml(fh)

    # The Yeongdeok snapshot stores WGS84 lon/lat; the 2026-08-02 snapshots
    # store EPSG:5179 metres. Detect by magnitude and project once.
    xs = [float(d["x"]) for _, d in list(graph.nodes(data=True))[:50]]
    lonlat = max(abs(v) for v in xs) <= 180.0
    if lonlat:
        from pyproj import Transformer
        tf = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

    def node_xy(node: str) -> tuple[float, float]:
        d = graph.nodes[node]
        x, y = float(d["x"]), float(d["y"])
        return tf.transform(x, y) if lonlat else (x, y)

    seen: set[tuple] = set()
    edges: list[dict] = []
    for u, v, d in graph.edges(data=True):
        a, b = (u, v) if u <= v else (v, u)
        key = (a, b, round(float(d.get("length", 0.0)), 1))
        if key in seen:
            continue
        seen.add(key)
        pts = None
        if "geometry" in d and d["geometry"]:
            pts = _parse_linestring(str(d["geometry"]))
            if pts and lonlat:
                pts = [tf.transform(x, y) for x, y in pts]
        if not pts:
            pts = [node_xy(u), node_xy(v)]
        pts = _simplify(pts)
        name = d.get("name")
        if not isinstance(name, str) or name.startswith("["):
            name = None
        edges.append({
            "pts": pts,
            "len_m": float(d.get("length", 0.0)),
            "hw": _hw_class(d.get("highway", "")),
            "name": name,
        })
    return edges


# --------------------------------------------------------------------------
# hazard sampling (the pipeline's own rule, on the routing's time grid)
# --------------------------------------------------------------------------


def hazard_sequence(npz_path: Path) -> HazardSequence:
    z = np.load(npz_path)
    ext = z["grid_extent"]
    stack = z["haz_stack"].astype(np.float32)
    grid = CoarseGrid(minx=float(ext[0]), miny=float(ext[1]),
                      maxx=float(ext[2]), maxy=float(ext[3]),
                      cell_size_m=float(ext[4]),
                      nrows=stack.shape[1], ncols=stack.shape[2])
    return HazardSequence(grid=grid,
                          times_min=z["haz_times"].astype(float),
                          surfaces=[stack[i] for i in range(stack.shape[0])])


def first_crossings(seq: HazardSequence, sample_xy: np.ndarray,
                    starts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per group: first minute max-prob-over-points crosses P_RISK / P_CLOSED.

    ``sample_xy`` is (N,2); ``starts`` holds each group's first row index
    (groups are contiguous). Returns (t_risk, t_closed) in minutes, -1 where
    the threshold is never reached within the horizon.
    """
    times = np.arange(0, T_MAX_MIN + 1, T_STEP_MIN, dtype=float)
    xs, ys = sample_xy[:, 0], sample_xy[:, 1]
    n_items = len(starts)
    t_risk = np.full(n_items, -1.0)
    t_closed = np.full(n_items, -1.0)
    for t in times:
        prob = seq.prob_at_points(xs, ys, float(t))
        peak = np.maximum.reduceat(prob, starts)
        hit_r = (t_risk < 0) & (peak >= P_RISK)
        t_risk[hit_r] = t
        hit_c = (t_closed < 0) & (peak >= P_CLOSED)
        t_closed[hit_c] = t
        # the field is cumulative: once every group is closed nothing changes
        if (t_closed >= 0).all():
            break
    # a group that closes at its first crossing is also at-risk from then on
    fix = (t_closed >= 0) & ((t_risk < 0) | (t_risk > t_closed))
    t_risk[fix] = t_closed[fix]
    return t_risk, t_closed


def sample_along(pts: list[tuple[float, float]], step_m: float = 250.0,
                 cap: int = 9) -> list[tuple[float, float]]:
    """Points along a polyline every ``step_m`` (ends included, capped)."""
    out = [pts[0]]
    acc = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        seg = math.hypot(x1 - x0, y1 - y0)
        while acc + seg >= step_m:
            f = (step_m - acc) / seg
            x0, y0 = x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
            seg -= (step_m - acc)
            acc = 0.0
            out.append((x0, y0))
        acc += seg
    out.append(pts[-1])
    if len(out) > cap:
        idx = np.linspace(0, len(out) - 1, cap).astype(int)
        out = [out[i] for i in idx]
    return out


# --------------------------------------------------------------------------
# terrain
# --------------------------------------------------------------------------


def hillshade_png(region: str, view: View, res_m: float = 120.0) -> dict | None:
    """Graphite-toned hillshade + coastline from the committed SRTM snapshot.

    Real terrain, deliberately quiet: the PNG is pre-tinted toward the page
    background so it can sit at full opacity without fighting the data layers.
    Rendered with a generous bleed margin so the map never letterboxes into a
    different tone. Areas outside the DEM read as neutral ground, NOT sea;
    sea is only where the raster itself says elevation <= 0.
    Returns None (screen falls back to a flat ground) if anything is missing.
    """
    try:
        import rasterio
        from rasterio.warp import Resampling, reproject
    except ImportError:
        return None
    try:
        dem_path = snapshot_path(region, "srtm-dem")
    except SystemExit:
        return None
    # bleed: 45 % extra width, 18 % extra height on each side
    bx = 0.45 * (view.x1 - view.x0)
    by = 0.18 * (view.y1 - view.y0)
    gx0, gy1 = view.x0 - bx, view.y1 + by
    with rasterio.open(dem_path) as src:
        w = max(2, int(round((view.x1 - view.x0 + 2 * bx) / res_m)))
        h = max(2, int(round((view.y1 - view.y0 + 2 * by) / res_m)))
        dst = np.full((h, w), np.nan, dtype=np.float32)
        from affine import Affine
        transform = Affine(res_m, 0, gx0, 0, -res_m, gy1)
        reproject(source=rasterio.band(src, 1), destination=dst,
                  dst_transform=transform, dst_crs="EPSG:5179",
                  resampling=Resampling.bilinear,
                  src_nodata=src.nodata, dst_nodata=np.nan)
    outside = ~np.isfinite(dst)
    elev = np.nan_to_num(dst, nan=0.0)
    sea = (~outside) & (elev <= 0.0)
    z = np.clip(elev, 0.0, None)
    gy, gx = np.gradient(z, res_m)
    az, alt = math.radians(315.0), math.radians(45.0)
    slope = np.arctan(np.hypot(gx, gy) * 2.4)     # legibility exaggeration
    aspect = np.arctan2(-gx, gy)
    shade = (np.sin(alt) * np.cos(slope)
             + np.cos(alt) * np.sin(slope) * np.cos(az - aspect))
    shade = np.clip((shade + 1.0) / 2.0, 0.0, 1.0) ** 0.72
    # a whisper of hypsometric lift so ridgelines separate from valleys
    zn = z / max(1.0, np.percentile(z[~outside], 98) or 1.0)
    tone = np.clip(shade * 0.82 + np.clip(zn, 0, 1) * 0.18, 0.0, 1.0)

    lo = np.array([11, 15, 21], dtype=np.float32)      # shadow
    hi = np.array([74, 92, 112], dtype=np.float32)     # lit slope
    rgb = lo[None, None, :] + (hi - lo)[None, None, :] * tone[:, :, None]
    rgb[outside] = np.array([15, 20, 27], dtype=np.float32)   # beyond DEM
    rgb[sea] = np.array([9, 15, 23], dtype=np.float32)        # real sea
    from PIL import Image
    img = Image.fromarray(rgb.astype(np.uint8), "RGB").convert(
        "P", palette=Image.ADAPTIVE, colors=64)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return {"png": "data:image/png;base64," + data,
            "x": round((gx0 - view.x0) * view.scale, 1),
            "y": round((view.y1 - gy1) * view.scale, 1),
            "w": round(w * res_m * view.scale, 1),
            "h": round(h * res_m * view.scale, 1)}


# --------------------------------------------------------------------------
# per-region payload
# --------------------------------------------------------------------------


def build_region(region: str, mrc_row: dict, verbose: bool = True) -> dict:
    run_dir = newest_run(region)
    viz = json.loads((run_dir / "viz.json").read_text(encoding="utf-8"))
    run_meta = {}
    run_json = run_dir / "RUN.json"
    if run_json.exists():
        run_meta = json.loads(run_json.read_text(encoding="utf-8"))

    npz_rel = viz["hazard"]["npz_path"]
    npz_path = REPO / npz_rel
    bands, band_meta = quantise(npz_path)
    seq = hazard_sequence(npz_path)
    ext = viz["hazard"]["grid_extent_5179"]
    cell = float(viz["hazard"]["cell_size_m"])

    # ---- content box: hazard cells >= band 0 at final slice + walk points
    xs: list[float] = []
    ys: list[float] = []
    for band in bands[-1]:
        for row, col0, width in band:
            xs += [ext[0] + col0 * cell, ext[0] + (col0 + width) * cell]
            ys += [ext[3] - (row + 1) * cell, ext[3] - row * cell]
    for o in viz["origins"]:
        xs.append(o["x"]); ys.append(o["y"])
    for rgo in viz["refuges"]:
        xs.append(rgo["x"]); ys.append(rgo["y"])
    view = View(min(xs), min(ys), max(xs), max(ys))

    # ---- roads with derived state times
    edges = load_walk_edges(region)
    samples: list[tuple[float, float]] = []
    starts: list[int] = []
    for e in edges:
        pts = sample_along(e["pts"])
        starts.append(len(samples))
        samples.extend(pts)
    t_risk, t_closed = first_crossings(
        seq, np.asarray(samples), np.asarray(starts, dtype=np.intp))

    names: list[str] = []
    name_idx: dict[str, int] = {}
    flat_pts: list[float] = []
    lens: list[int] = []
    tr_out: list[int] = []
    tc_out: list[int] = []
    hw_out: list[int] = []
    nm_out: list[int] = []
    for i, e in enumerate(edges):
        for x, y in e["pts"]:
            flat_pts += view.pt(x, y)
        lens.append(len(e["pts"]))
        tr_out.append(int(t_risk[i]))
        tc_out.append(int(t_closed[i]))
        hw_out.append(e["hw"])
        if e["name"]:
            j = name_idx.setdefault(e["name"], len(names))
            if j == len(names):
                names.append(_dash_safe(e["name"]))
            nm_out.append(j)
        else:
            nm_out.append(-1)

    # network-loss curve on the same 10-min grid (count + km of closed edges)
    times = list(range(0, T_MAX_MIN + 1, T_STEP_MIN))
    lengths_km = np.array([e["len_m"] for e in edges]) / 1000.0
    tc_arr = np.array(tc_out, dtype=float)
    closed_n = [int(((tc_arr >= 0) & (tc_arr <= t)).sum()) for t in times]
    closed_km = [round(float(lengths_km[(tc_arr >= 0) & (tc_arr <= t)].sum()), 1)
                 for t in times]

    # ---- origins (all scanned) + actionable overlay
    bucket_order = [b["key"] for b in BUCKETS]
    origins = []
    origin_at: dict[tuple, int] = {}
    for o in viz["origins"]:
        b = bucket_order.index(o["bucket"]) if o["bucket"] in bucket_order else 0
        origin_at[(round(o["x"], 1), round(o["y"], 1))] = len(origins)
        origins.append(view.pt(o["x"], o["y"]) + [b])
    act = {}
    for a in viz["actionable"]:
        i = origin_at.get((round(a["x"], 1), round(a["y"], 1)))
        if i is None:
            continue
        act[str(i)] = {
            "l": _dash_safe(a.get("label") or ""),
            "w": a.get("walk_time_min"),
            "c": a.get("closing_window_min"),
        }

    # ---- stored route pairs, with derived first-unsafe times along each
    routes = []
    for r in viz["routes"]:
        rec = {"o": None}
        for kind in ("naive", "fa"):
            pts = r[f"{kind}_xy"]
            spts = np.asarray(pts, dtype=float)
            tcs = []
            times_grid = np.arange(0, T_MAX_MIN + 1, T_STEP_MIN, dtype=float)
            probs = np.stack([seq.prob_at_points(spts[:, 0], spts[:, 1], t)
                              for t in times_grid])
            crossed = probs >= P_CLOSED
            first = np.where(crossed.any(axis=0),
                             times_grid[np.argmax(crossed, axis=0)], -1.0)
            tcs = [int(v) for v in first]
            flat = []
            for x, y in pts:
                flat += view.pt(x, y)
            rec[kind] = {
                "pts": flat,
                "t_min": round(float(r[f"{kind}_time_min"]), 1),
                "dist_m": round(float(r[f"{kind}_distance_m"]), 0),
                "enters": bool(r[f"{kind}_enters_hazard"]),
                "tc": tcs,
            }
        key = (round(r["naive_xy"][0][0], 1), round(r["naive_xy"][0][1], 1))
        rec["o"] = origin_at.get(key)
        rec["node"] = r.get("origin_node")
        routes.append(rec)

    # Flagship pair for the guided demo: the clearest honest telling of
    # "time changes the answer" — prefer a naive route that is CLEAR at t=0
    # and crosses a cell that reaches p_cut later, with a clean time-aware
    # alternative; among those, the shortest naive route reads best on a map.
    def _flagship_key(r: dict) -> tuple:
        n_tc = [t for t in r["naive"]["tc"] if t >= 0]
        closes_later = bool(n_tc) and min(n_tc) > 0
        fa_clean = not any(t >= 0 for t in r["fa"]["tc"])
        contrast = r["naive"]["enters"] and not r["fa"]["enters"]
        return (contrast, closes_later, fa_clean, -r["naive"]["dist_m"])

    flagship = max(range(len(routes)),
                   key=lambda i: _flagship_key(routes[i])) if routes else 0

    refuges = [{"n": _dash_safe(s["name"]), "p": view.pt(s["x"], s["y"])}
               for s in viz["refuges"]]

    from pyproj import Transformer
    tf = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    w, s, e, n = mrc_row["walk_bbox_wgs84_wsen"]
    bbox_view = [view.pt(*tf.transform(lon, lat))
                 for lon, lat in ((w, n), (e, n), (e, s), (w, s))]

    trig = viz.get("trigger_hotspot") or {}
    trig_out = None
    if trig:
        tx, ty = tf.transform(trig["lon"], trig["lat"])
        trig_out = {
            "p": view.pt(tx, ty),
            "utc": trig.get("acquired_utc", ""),
            "sat": f'{trig.get("instrument", "")} {trig.get("satellite", "")}'.strip(),
            "frp": trig.get("frp"),
            "conf": trig.get("confidence", ""),
        }

    scope = viz.get("scope") or {}
    resp = viz.get("responder_side") or {}
    fieldapp = viz.get("field_applicability") or {}

    hz = viz["hazard"]
    counts = viz["counts"]
    n_scanned = sum(counts.values())

    hill = hillshade_png(region, view)
    if verbose:
        print(f"  {region}: {len(edges)} edges, {len(origins)} origins, "
              f"{len(routes)} route pairs, run {run_dir.name}")

    return {
        "label": _label_kr(region),
        "view": {"vh": view.vh, "x0": view.x0, "y1": view.y1,
                 "scale": view.scale},
        "haz": {
            "bands": bands,
            "cell": round(cell * view.scale, 3),
            "ox": round((ext[0] - view.x0) * view.scale, 2),
            "oy": round((view.y1 - ext[3]) * view.scale, 2),
            "times": band_meta["times_min"],
            "cells05": hz.get("cells_ge_0.5_per_slice"),
        },
        "hill": hill,
        "roads": {"pts": flat_pts, "lens": lens, "tr": tr_out, "tc": tc_out,
                  "hw": hw_out, "nm": nm_out, "names": names},
        "loss": {"t": times, "n": closed_n, "km": closed_km,
                 "total_n": len(edges),
                 "total_km": round(float(lengths_km.sum()), 1)},
        "bbox": bbox_view,
        "origins": origins,
        "act": act,
        "routes": routes,
        "flagship": flagship,
        "refuges": refuges,
        "trigger": trig_out,
        "counts": counts,
        "n_scanned": n_scanned,
        "fa_only_pct": mrc_row["future_aware_only_safe_pct"],
        "coverage_pct": _coverage_pct(region),
        "coverage_note": _dash_safe(scope.get("coverage_caveat_ko")
                                    or viz.get("coverage_caveat_ko") or ""),
        "detect_line": _dash_safe(scope.get("detection_line_ko", "")),
        "weather_line": _dash_safe(scope.get("weather_line_ko", "")),
        "mode_banner": _dash_safe(scope.get("mode_banner_ko", "")),
        "field_note": _dash_safe(fieldapp.get("statement_ko", "")),
        "responder": {
            "available": bool(resp.get("responder_side_available")),
            "status": _dash_safe(resp.get("status_ko", "")),
        },
        "shelter_pois": mrc_row["shelter_pois"],
        "depot_pois": mrc_row["depot_pois"],
        "envelope_ha": mrc_row["envelope_area_ha"],
        "naive_unsafe_pct": mrc_row["naive_route_unsafe_pct"],
        "prov": {
            "run": run_dir.name,
            "npz": npz_rel,
            "npz_sha16": hz.get("npz_sha256", "")[:16],
            "walk_snap": snapshot_path(region, "osm-walk").name,
            "dem_snap": (snapshot_path(region, "srtm-dem").name
                         if hill else None),
            "warm_s": (run_meta.get("timings_s", {}) or {}).get("warm_total_s"),
        },
    }


# --------------------------------------------------------------------------
# evidence + reliability payloads
# --------------------------------------------------------------------------

REGISTRY_KEYS = [
    "lofo_mean_of_folds_auc", "lofo_fold_auc_sd",
    "responder_exposure_reduction_pct",
    "responder_exposure_shortest_path_mean",
    "responder_exposure_survival_aware_mean",
    "rescue_dispatch_count",
    "slope_walk_time_increase_pct", "slope_mean_abs_slope",
    "slope_canonical_fa_routes_changed_60m",
    "objective_canonical_longest_walk_saving_min",
    "walk_failure_rate_pct",
    "dispatch_order_deadline_wins_pct",
    "dispatch_order_deadline_wins_at_committed_window",
    "ordering_boundary_first_window_with_a_win",
    "wxdep_shuffle_far_band_delta",
    "mr_yeongdeok_walk_time_increase_pct",
    "mr_uiseong_walk_time_increase_pct",
    "mr_uljin_walk_time_increase_pct",
    # --- v2 evidence cards (WFG-017) -------------------------------------
    # operating point (WFG-019)
    "oof_pooled_recall_at_operating_threshold",
    "oof_mean_of_folds_recall_at_operating_threshold",
    "oof_pooled_precision_at_operating_threshold",
    "oof_average_precision", "oof_prevalence",
    "optpoint_uiseong_fnr_advance_cut", "optpoint_uljin_fnr_advance_cut",
    "optpoint_yeongdeok_fnr_advance_cut",
    # detection floor (WFG-021)
    "det_size_floor_ha_tf750",
    "det_gk2a_delay_uiseong_andong_min", "det_gk2a_delay_gangneung_2023_min",
    "det_gk2a_delay_hongseong_2023_min",
    "det_control_steps", "det_false_alarm_steps",
    # horizon grounding (Session 20)
    "kfs_cum_le_240_pct", "kfs_n_usable_events",
    "kfs_containment_median_min", "kfs_area_ge100ha_median_min",
    # refuge placement (Session 22)
    "l0i_best_single_refuge_saved", "l0i_best_pair_saved",
    "l0i_third_refuge_gain", "l0i_candidates_enumerated",
    "l0i_survival_check_reached_by_fire",
]


def registry_slice() -> dict:
    reg = json.loads((REPO / "docs" / "NUMBERS.json").read_text(encoding="utf-8"))
    out = {"config_hash": reg.get("config_hash", "")[:16],
           "built_at_commit": reg.get("built_at_git_commit", "")[:12],
           "n_entries": len(reg["numbers"]),
           "n_reproducible": sum(
               1 for e in reg["numbers"].values()
               if e.get("reproducible") is True
               or (isinstance(e.get("reproducibility"), dict)
                   and e["reproducibility"].get("status") == "reproducible")),
           "entries": {}}
    for key in REGISTRY_KEYS:
        e = reg["numbers"].get(key)
        if not e:
            continue
        out["entries"][key] = {
            "value": e["value"],
            "unit": _dash_safe(str(e.get("unit", ""))),
            "source": e.get("source_file", ""),
            "path": e.get("json_path", ""),
            "caveat": _dash_safe(str(e.get("caveat", "")))[:600],
        }
    return out


def model_evidence() -> dict:
    """The three committed evidence artifacts (not registry entries)."""
    lofo = json.loads((REPO / "data" / "processed" / "spread_v2_lofo.json")
                      .read_text(encoding="utf-8"))
    intervals = json.loads((REPO / "data" / "processed" / "auc_intervals.json")
                           .read_text(encoding="utf-8"))
    calib = json.loads((REPO / "data" / "processed" / "calibration_metrics.json")
                       .read_text(encoding="utf-8"))
    baselines = json.loads((REPO / "data" / "processed" / "ml_baselines.json")
                           .read_text(encoding="utf-8"))
    per_fire = intervals["per_fire"]
    folds = [{"fire": k,
              "auc": round(v["auc_ci_delong"]["auc"], 3),
              "lo": round(v["auc_ci_delong"]["ci95"][0], 3),
              "hi": round(v["auc_ci_delong"]["ci95"][1], 3),
              "n": v.get("n"), "pos": v.get("n_pos")}
             for k, v in per_fire.items()]
    fwd = json.loads((REPO / "data" / "processed" / "yeongdeok_forward_sim.json")
                     .read_text(encoding="utf-8"))
    drift_iou = [round(d["iou"], 2) for d in fwd["drift"][1:5]]
    return {
        "pooled_auc": round(lofo["pooled_auc"], 3),
        "mean_folds": {
            "mean": round(intervals["mean_of_folds_interval"]["mean"], 3),
            "sd": round(intervals["mean_of_folds_interval"]["sd"], 3),
            "ci95": [round(v, 3) for v in
                     intervals["mean_of_folds_interval"]["ci95"]],
            "lineage": intervals.get("gate_lineage", ""),
        },
        "pooled_ci": [round(v, 4) for v in
                      intervals["pooled_bootstrap_ci"]["ci95"]],
        "folds": folds,
        "brier": {
            "gbm": round(calib["models"]["hist_gbm"]["pooled"]["brier"], 4),
            "rf": round(calib["models"]["random_forest"]["pooled"]["brier"], 4),
            "logistic": round(calib["models"]["logistic"]["pooled"]["brier"], 4),
        },
        "baseline_auc": {
            "rf_mean_folds": round(baselines["models"]["random_forest"]
                                   ["mean_of_folds"], 3),
            "gbm_minus_rf": round(baselines["gbm_minus_rf_mean_of_folds"], 3),
        },
        "iou_steps": drift_iou,
        "sources": {
            "lofo": "data/processed/spread_v2_lofo.json",
            "intervals": "data/processed/auc_intervals.json",
            "calibration": "data/processed/calibration_metrics.json",
            "baselines": "data/processed/ml_baselines.json",
            "forward_sim": "data/processed/yeongdeok_forward_sim.json",
        },
    }


# --------------------------------------------------------------------------
# gates (--verify)
# --------------------------------------------------------------------------

GATES = (
    ("verify-numbers", ["scripts/verify_numbers.py"]),
    ("check-forbidden", ["scripts/check_forbidden.py"]),
    ("check-region-literals", ["scripts/check_region_literals.py"]),
)


def evidence_v2() -> dict:
    """Session 19/20/22 facts the registry cannot hold as single keys.

    Everything on the v2 cards that IS a registry key is read through
    ``regEntry`` in the template. What lands here is the handful of
    structural facts a key cannot carry: how many LOFO folds have no true
    positive at all and how few positive cells those folds contain (the row
    asks for ``n_positive`` beside the perfect-miss folds so the reader sees
    prevalence, not a broken model), the failing-household denominator the
    refuge optimiser starts from, and the artifacts' own caveat sentences.

    Read straight from the committed artifacts, the way ``model_evidence``
    already is, and pinned to them by ``tests/test_finals_screen.py``.
    """
    opp = json.loads((REPO / "data" / "processed" / "operating_point" /
                      "per_fire_recall.json").read_text(encoding="utf-8"))
    per = opp["per_fire"]
    misses = [v for v in per.values() if v["false_negative_rate"] >= 1.0]
    # the range the card prints is over the folds that DO have a true
    # positive. Taking it over all six would put 1.000 in a sentence that
    # says "the remaining folds", which is the perfect-miss folds' value.
    rest = [v for v in per.values() if v["false_negative_rate"] < 1.0]
    fnrs = sorted(round(v["false_negative_rate"], 3) for v in rest)

    # the size floor is an ORDER OF MAGNITUDE: the assumed flaming temperature
    # alone moves it more than eightfold, and the registry caveat says to read
    # it as roughly 0.1 to 1 ha. A single Tf_750K point estimate on the card
    # would be five times narrower than the repository's own interval, so the
    # card prints the span across the assumed temperatures instead.
    det = json.loads((REPO / "data" / "processed" / "detection" /
                      "gk2a_detection_floor.json").read_text(encoding="utf-8"))
    spa = det["per_fire"]["uiseong_andong_2025"]["sub_pixel_area"]
    areas = sorted(v["fire_area_ha"] for v in spa.values())

    rp = json.loads((REPO / "data" / "processed" / "vulnerability" /
                     "refuge_placement.json").read_text(encoding="utf-8"))
    ver = rp["verification"]["full_layer_verification"]
    surv = rp["verification"]["survival_check"]

    return {
        "operating_point": {
            "n_fires": len(per),
            "n_folds_without_a_true_positive": len(misses),
            "n_positive_of_those": sorted(v["n_positive"] for v in misses),
            "n_folds_with_a_true_positive": len(rest),
            "fnr_min_among_folds_with_a_true_positive": fnrs[0],
            "fnr_max_among_folds_with_a_true_positive": fnrs[-1],
            "source": "data/processed/operating_point/per_fire_recall.json",
        },
        "size_floor": {
            "ha_min": areas[0],
            "ha_max": areas[-1],
            "n_assumed_temperatures": len(areas),
            "assumed_temperatures": sorted(spa),
            "source": "data/processed/detection/gk2a_detection_floor.json",
        },
        "refuge": {
            "site": rp["site"],
            "failing_before": ver["full_layer_failing_before"],
            "failing_after": ver["full_layer_failing_after"],
            "horizon_min": ver["horizon_min"],
            # the full-layer recomputation covers ONE site at k = 1, and it is
            # not even the k1 optimum (marginal_curve.k1_nodes names a
            # different node). k2 and k3 were never recomputed that way, so
            # the card may not put the agreement verb after all three.
            "verified_node": ver["node"],
            "verified_k1_node": rp["optimum_h240"]["marginal_curve"]["k1_nodes"][0],
            "n_sites_full_layer_verified": 1,
            "full_layer_agrees": bool(ver["agree"]),
            "survival_evaluations": surv["n_site_scenario_evaluations"],
            "readme": _dash_safe(str(rp["_README"]))[:600],
            "source": "data/processed/vulnerability/refuge_placement.json",
        },
        "sources": {
            "detection": "data/processed/detection/gk2a_detection_floor.json",
            "horizon": "data/processed/detection/kfs_containment_duration.json",
        },
    }


def run_gates() -> list[dict]:
    results = []
    for name, argv in GATES:
        t0 = time.time()
        proc = subprocess.run([sys.executable, *argv], cwd=REPO,
                              capture_output=True, text=True, timeout=600)
        tail = (proc.stdout.strip().splitlines() or [""])[-1]
        results.append({
            "name": name,
            "ok": proc.returncode == 0,
            "seconds": round(time.time() - t0, 1),
            "line": _dash_safe(tail[:160]),
        })
    return results


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
            stderr=subprocess.DEVNULL).decode().strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true",
                    help="run the fast gates and record their real results")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()

    mrc = json.loads((REPO / "data" / "processed" /
                      "multi_region_comparison.json").read_text(encoding="utf-8"))
    rows = {r["region"]: r for r in mrc["regions"]}
    region_order = mrc["region_order"]

    print("=== reading canonical artifacts ===")
    regions = {}
    for region in region_order:
        regions[region] = build_region(region, rows[region])

    gates = run_gates() if args.verify else []

    payload = {
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "git": git_head(),
        "default_region": "uiseong_andong_2025",
        "region_order": region_order,
        "regions": regions,
        "band_fills": list(BAND_FILLS),
        "band_labels": list(BAND_LABELS),
        "buckets": [{"key": b["key"], "ko": b["ko"], "fill": b["fill"],
                     "shape": b["shape"], "mark": b["mark"]} for b in BUCKETS],
        "p_closed": P_CLOSED,
        "p_risk": P_RISK,
        "registry": registry_slice(),
        "model": model_evidence(),
        "ev2": evidence_v2(),
        "integrity": {
            "verified": bool(gates),
            "gates": gates,
            "note_media": None,
        },
    }

    tpl = TEMPLATE.read_text(encoding="utf-8")
    if PLACEHOLDER not in tpl:
        raise SystemExit(f"template lacks the payload placeholder: {TEMPLATE}")
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # belt-and-braces: the dash gate cannot see payload strings written to the
    # DOM through variables, so the payload itself must be dash-clean.
    blob = blob.replace("—", "·").replace("–", "~")
    html = tpl.replace(PLACEHOLDER, blob)
    args.out.write_text(html, encoding="utf-8")
    size_kb = args.out.stat().st_size / 1024
    print(f"wrote {args.out} ({size_kb:,.0f} KiB)")
    if gates:
        for g in gates:
            print(f"  gate {g['name']}: {'OK' if g['ok'] else 'FAIL'} "
                  f"({g['seconds']}s)")
        if not all(g["ok"] for g in gates):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
