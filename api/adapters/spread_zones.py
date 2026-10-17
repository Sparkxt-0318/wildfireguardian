"""spread_zones adapter: zone forecasts (e.g. Korea Forest Service 5 h / 8 h fire-line ranges) -> 4-scenario packet.

APPROXIMATION, REQUIRES EXPERT REVIEW. The adapter does not forecast and does not change the routing or checking
models. It only decides per-cell ignition times and then builds the hazard packet with the unchanged packet writer
(``wfg_latest.packets.write_regional_packet``), injecting those times where the writer normally draws them
(``bridge.draw_ignitions``) -- the same injection point ``packets.construct_regional`` uses for regional windows.

Rules (all echoed under ``assumptions``):
* Rasterization (conservative): a 375 m cell belongs to a zone when the zone polygon intersects the cell (centre or
  corner inside, or a polygon edge crossing the cell). A cell takes the band of the smallest ``arrival_h_max`` among
  the zones that touch it (nested zones).
* Bands: the distinct ``arrival_h_max`` values sorted ascending give bands (H_prev, H]; H_prev = 0 for the innermost.
* Ignition: a cell in band (H_prev, H] may ignite from max(0, H_prev - margin) (margin default 60 min). Four scenarios:
  scenario 0 = that earliest time; scenarios 1-3 = H_prev + (H - H_prev) * k/3 for k = 1, 2, 3 (inside the band, the
  last at H). Each ignited cell then burns on [ignition, ignition + T) with T the experiment's active duration
  (the checker's scalar law); the latest scenario therefore stays active until H + T.
* Clock: zone hours count from ``issued_at``; packet times count from ``input_time``. Times before ``input_time`` are
  clamped to 0 (conservative); times at or after the experiment's 1 h hazard horizon cannot affect the journey and are
  left unignited, as the packet writer requires.
* Present fire: the recorded c651 export at ``input_time`` supplies the grid, clock binding and the cells burning now,
  which stay exactly as recorded (zone ignitions are never placed on them). ``input_time`` must therefore be a recorded
  input time of the region.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

from ..errors import unprocessable

ADAPTER_VERSION = "wfg.api.spread-zones-adapter/1"
APPROXIMATION = "approximation, requires expert review"
DEFAULT_MARGIN_MIN = 60.0
LATER_FRACTIONS = (1.0 / 3.0, 2.0 / 3.0, 1.0)


# ------------------------------------------------------------------------------------------------- geometry
def _rings_of(geom: dict) -> list:
    """Return a list of polygons, each a list of rings (outer first), as float arrays (lon, lat)."""
    t = geom.get("type")
    coords = geom.get("coordinates")
    if t == "Polygon":
        polys = [coords]
    elif t == "MultiPolygon":
        polys = coords
    else:
        raise unprocessable("INVALID_ZONES", "zone geometry must be Polygon or MultiPolygon, got %r" % t)
    out = []
    for poly in polys or []:
        rings = []
        for ring in poly or []:
            a = np.asarray(ring, dtype=float)
            if a.ndim != 2 or a.shape[0] < 3 or a.shape[1] < 2 or not np.isfinite(a[:, :2]).all():
                raise unprocessable("INVALID_ZONES", "each polygon ring needs at least 3 finite [lon, lat] positions")
            a = a[:, :2]
            if (np.abs(a[:, 0]) > 180).any() or (np.abs(a[:, 1]) > 90).any():
                raise unprocessable("INVALID_ZONES", "zone coordinates must be WGS84 [lon, lat]")
            if not np.array_equal(a[0], a[-1]):
                a = np.vstack([a, a[:1]])
            rings.append(a)
        if not rings:
            raise unprocessable("INVALID_ZONES", "empty polygon")
        out.append(rings)
    if not out:
        raise unprocessable("INVALID_ZONES", "empty geometry")
    return out


def _points_in_rings(px, py, rings) -> np.ndarray:
    """Even-odd rule over all rings (holes subtract)."""
    inside = np.zeros(px.shape, dtype=bool)
    for r in rings:
        x0, y0 = r[:-1, 0], r[:-1, 1]
        x1, y1 = r[1:, 0], r[1:, 1]
        for a, b, c, d in zip(x0, y0, x1, y1):
            if b == d:
                continue
            cond = (b > py) != (d > py)
            xint = a + (py - b) * (c - a) / (d - b)
            inside ^= cond & (px < xint)
    return inside


def _segment_hits_cells(ax, ay, bx, by, xl, xr, yb, yt) -> np.ndarray:
    """Vectorised segment-vs-axis-aligned-rectangle test (separating axis) for one segment and many cells."""
    bbox = (np.maximum(xl, min(ax, bx)) <= np.minimum(xr, max(ax, bx))) & (np.maximum(yb, min(ay, by)) <= np.minimum(yt, max(ay, by)))
    dx, dy = bx - ax, by - ay
    s = [dx * (cy - ay) - dy * (cx - ax) for cx, cy in ((xl, yb), (xr, yb), (xr, yt), (xl, yt))]
    s = np.stack(s)
    straddle = ~((s > 0).all(axis=0) | (s < 0).all(axis=0))
    return bbox & straddle


def rasterize(polys_xy: list, grid: dict) -> np.ndarray:
    """Conservative cell mask on the region grid (native north-up rows, shape (height, width))."""
    H, W, res = int(grid["height"]), int(grid["width"]), float(grid["resolution"])
    x0, ytop = float(grid["x0"]), float(grid["y0"]) + H * res
    cols, rows = np.meshgrid(np.arange(W), np.arange(H))
    xl = x0 + cols * res; xr = xl + res
    yt = ytop - rows * res; yb = yt - res
    mask = np.zeros((H, W), dtype=bool)
    for rings in polys_xy:
        pts = [((xl + xr) / 2, (yb + yt) / 2), (xl, yb), (xr, yb), (xr, yt), (xl, yt)]
        for px, py in pts:
            mask |= _points_in_rings(px, py, rings)
        for r in rings:
            for (ax, ay), (bx, by) in zip(r[:-1], r[1:]):
                mask |= _segment_hits_cells(ax, ay, bx, by, xl, xr, yb, yt)
    return mask


# ------------------------------------------------------------------------------------------------- planning
def _utc(text, field):
    try:
        t = dt.datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        raise unprocessable("INVALID_ZONES", "%s must be an ISO 8601 time" % field, {field: text})
    if t.tzinfo is None:
        raise unprocessable("INVALID_ZONES", "%s must carry a time zone" % field, {field: text})
    return t.astimezone(dt.timezone.utc)


def plan(*, region, sset, fire_input: dict, to_5179, horizon_s: float, active_duration_s: float,
         present_fire: np.ndarray, window) -> dict:
    """Validate zones and compute the 4-scenario ignition schedule on the region grid (pure; no packet writing)."""
    zones = fire_input.get("zones") or {}
    feats = zones.get("features")
    if zones.get("type") != "FeatureCollection" or not isinstance(feats, list):
        raise unprocessable("INVALID_ZONES", "zones must be a GeoJSON FeatureCollection")
    margin_min = float(fire_input.get("margin_min", DEFAULT_MARGIN_MIN))
    if not (math.isfinite(margin_min) and margin_min >= 0):
        raise unprocessable("INVALID_ZONES", "margin_min must be a non-negative number of minutes")
    issued = _utc(fire_input.get("issued_at"), "issued_at")
    input_time = _utc(sset.time_origin, "input_time")
    offset_s = (issued - input_time).total_seconds()        # zone clock origin on the packet clock
    grid = dict(region.graph.grid)
    H, W = int(grid["height"]), int(grid["width"])
    if present_fire.shape != (H, W):
        raise unprocessable("GRID_MISMATCH", "recorded present-fire grid differs from the region grid")
    zone_rows, outside = [], []
    for i, f in enumerate(feats):
        if not isinstance(f, dict) or f.get("type") != "Feature":
            raise unprocessable("INVALID_ZONES", "zones.features[%d] must be a GeoJSON Feature" % i)
        props = f.get("properties") or {}
        h = props.get("arrival_h_max")
        if isinstance(h, bool) or not isinstance(h, (int, float)) or not math.isfinite(h) or h <= 0:
            raise unprocessable("INVALID_ZONES", "zones.features[%d].properties.arrival_h_max must be a positive number of hours" % i)
        polys = _rings_of(f.get("geometry") or {})
        polys_xy = []
        for rings in polys:
            rr = []
            for ring in rings:
                x, y = to_5179(ring[:, 0], ring[:, 1])
                rr.append(np.column_stack([x, y]))
            polys_xy.append(rr)
        m = rasterize(polys_xy, grid)
        if not m.any():
            outside.append(i)
        zone_rows.append((float(h), m))
    if outside:
        raise unprocessable("ZONES_OUTSIDE_REGION", "zone(s) %s do not touch the %s grid" % (outside, region.id),
                            {"zones_outside": outside, "region_bbox_wgs84": list(region.graph.bbox)})
    levels = sorted({h for h, _ in zone_rows})
    band_h = np.full((H, W), np.inf)
    for h, m in zone_rows:
        band_h = np.where(m & (h < band_h), h, band_h)
    in_zone = np.isfinite(band_h)
    prev_of = {h: (levels[k - 1] if k else 0.0) for k, h in enumerate(levels)}
    T = float(active_duration_s)
    times = np.full((4, H, W), np.inf)
    bands, clamped, beyond = [], 0, 0
    for h in levels:
        hp = prev_of[h]
        cells = in_zone & (band_h == h) & ~present_fire
        earliest_h = max(0.0, hp - margin_min / 60.0)
        offs_h = [earliest_h] + [hp + (h - hp) * fr for fr in LATER_FRACTIONS]
        packet_s = [offset_s + oh * 3600.0 for oh in offs_h]
        eff = []
        for k, t in enumerate(packet_s):
            if t >= horizon_s:
                beyond += int(cells.sum()); eff.append(None); continue
            if t < 0:
                clamped += int(cells.sum()); t = 0.0
            times[k][cells] = t
            eff.append(t)
        bands.append({"arrival_h_max": h, "h_prev": hp, "cells": int(cells.sum()),
                      "present_fire_cells_kept_as_recorded": int((in_zone & (band_h == h) & present_fire).sum()),
                      "ignition_offsets_h_from_issue": offs_h, "ignition_times_s_from_input_time": packet_s,
                      "effective_packet_times_s": eff, "active_until_s_from_input_time": [None if t is None else t + T for t in eff]})
    plan_digest = hashlib.sha256(json.dumps({"zones": zones, "issued_at": issued.isoformat(), "margin_min": margin_min,
                                             "input_time": input_time.isoformat(), "region": region.id},
                                            sort_keys=True, default=str).encode()).hexdigest()
    assumptions = {
        "adapter": ADAPTER_VERSION, "label": APPROXIMATION,
        "rasterization": "conservative: a 375 m EPSG:5179 cell is in a zone when the polygon intersects the cell; nested zones take the smallest arrival_h_max",
        "bands": "distinct arrival_h_max values ascending; band (H_prev, H], H_prev = 0 for the innermost band",
        "margin_min": margin_min,
        "scenario_rule": "scenario 0 ignites at max(0, H_prev - margin); scenarios 1-3 at H_prev + (H - H_prev) * 1/3, 2/3, 1",
        "burning_law": "each ignited cell burns on [ignition, ignition + T) (experiment scalar law); the latest scenario stays active until H + T",
        "active_duration_s": T, "horizon_s": horizon_s,
        "clock": {"issued_at": issued.isoformat(), "input_time": input_time.isoformat(), "issued_minus_input_s": offset_s,
                  "clamped_to_input_time_cell_scenarios": clamped, "beyond_horizon_cell_scenarios": beyond,
                  "rule": "times before input_time clamp to 0 (conservative); times at or after the 1 h horizon stay unignited"},
        "present_fire": {"source": "recorded c651 export at input_time (scenario set %s)" % sset.scenario_set_id,
                         "cells": int(present_fire.sum()), "rule": "kept exactly as recorded; zones never re-ignite them"},
        "bands_detail": bands, "zones": len(feats), "cells_in_zones": int(in_zone.sum()),
        "grid": {"height": H, "width": W, "resolution_m": grid["resolution"], "crs": "EPSG:5179"},
        "plan_sha256": plan_digest,
        "limitations": ["Zone products give arrival ranges, not ignition times; the four scenarios are a deterministic sample, not a probability model.",
                        "Only the first hour after input_time is represented (the experiment's hazard horizon).",
                        "Radiation uses the experiment's fixed heat-release parameters for every zone cell."],
    }
    return {"region": region.id, "tag": sset.tag, "packet_dir": str(sset.packet_dir), "event_id": sset.event_id,
            "window": window, "shape": [H, W], "times": times.tolist(), "plan_sha256": plan_digest,
            "assumptions": assumptions}


def build_packet(zone_plan: dict, *, graph_path: Path, out_dir: Path, python: str, inputs_root: Path | None = None):
    """Write the packet in a fresh child interpreter (the packet writer installs its vendored namespace packages)."""
    out_dir = Path(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    plan_path = out_dir.parent / "ZONE_PLAN.json"
    if not plan_path.exists():
        plan_path.write_text(json.dumps(zone_plan, allow_nan=True))
    child = Path(__file__).resolve().parent / "_zone_packet_child.py"
    p = subprocess.run([python, "-I", "-B", str(child), "--plan", str(plan_path), "--graph", str(graph_path), "--out", str(out_dir)],
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise RuntimeError("ZONE_PACKET_BUILD_FAILED: " + (p.stdout + p.stderr)[-800:])
    meta = json.loads((out_dir / "ZONE_ADAPTER.json").read_text())
    meta["assumptions"] = zone_plan["assumptions"]
    meta["input_hashes"] = {"plan": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                            "recorded_export": meta.get("forecast_export_sha256")}
    return out_dir, meta
