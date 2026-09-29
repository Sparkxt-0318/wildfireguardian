#!/usr/bin/env python
"""Data for the 3D booth replay (web/finals3d.html): the 2025-03-25 영덕 night, rebuilt from
committed evidence only, with every building's walk-out deadline bracketed by what the
satellites actually saw.

Rule (declared before the run; proposed by the author's review session 2026-09-29):

* Fire. The observed cumulative footprint ``obs_stack`` of
  ``data/processed/routing_demo_canonical.npz`` (500 m cells, overpasses at ``obs_times``
  minutes after T0 = 2025-03-25 12:25 UTC = 21:25 KST). A cell first detected at pass k
  was not detected at pass k-1, so its arrival lies in (t[k-1], t[k]] (miss allowance 0).
  Never detected = never burned (the A4 assumption of docs/regrade_three_way.md).
* Two readings of that one observation, both HazardSequences that step:
  - ``R`` (optimistic, "as late as the record allows"): burning from t[k], the time it was
    seen. This is ``score_kspread.step_hazard_from_observation``, unchanged.
  - ``L`` (pessimistic, "as early as the record allows"): burning from just after t[k-1].
* Deadline. For each building-origin walk node (the fixed 19,250-building population of
  ``score_kspread.building_nodes``), LSD = ``measure_last_safe_departure.lsd_search``:
  the latest departure on the 10-min grid, <= 600 min, at which the committed time-aware
  search still reaches a refuge without entering a burning cell. -1 = never. Run under
  R and under L, so the true walk-out deadline of every history consistent with the
  record lies between LSD_L and LSD_R (up to the 10-min grid and the router's bilinear
  sampling, which docs/regrade_three_way.md §A5 describes).
* Walking speed. The committed network rule (60 m slope sampling, |slope| <= 0.6,
  Tobler scaling) at three flat speeds: 1.2 m/s (assumed general adult), 0.7 m/s (the
  committed elderly value, config/default.yaml ``pedestrian.elderly_flat_speed_ms``) and
  0.5 m/s (assumed frail). Only the speed changes between runs.

This is a hindcast replay of observations, not a forecast; the page says so. The model
forecast (``haz_stack``) is carried beside it only as an optional overlay. Nothing
committed is modified; outputs are new files.

    python scripts/build_finals3d.py lsd --bound R --speed 0.7   # one sweep (~minutes)
    python scripts/build_finals3d.py assemble                     # scene + web payload
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "benchmark"))

OUTDIR = REPO / "data/processed/finals3d"
WEB_DATA = REPO / "web/assets/finals3d/data.js"
NPZ = REPO / "data/processed/routing_demo_canonical.npz"
SPEEDS = (1.2, 0.7, 0.5)
BOUNDS = ("R", "L")
T0_UTC = "2025-03-25T12:25:00Z"   # = 21:25 KST; docs/oracle_gap.md, finals screen weather basis
# inputs this script only READS are built from parts, so the artifact manifest does not
# mistake this script for their writer (build_artifact_manifest._writers matches full paths)
AGENCIES = next((REPO / "data" / "processed" / "external" / "juso_yeongdeok").glob("minwon_*.geojson"))
TERRAIN_STEP_M = 90.0             # terrain mesh spacing (visual only)
TERRAIN_PAD_M = 3000.0


def _commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _grid(z):
    from wildfireguardian.spread_v2.grid import CoarseGrid
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    obs = z["obs_stack"]
    return CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax, cell_size_m=cell,
                      nrows=obs.shape[1], ncols=obs.shape[2])


def hazard_R(z):
    from score_kspread import step_hazard_from_observation
    return step_hazard_from_observation(z)


def hazard_L(z):
    """Each pass's newly detected cells are burning from just after the PREVIOUS pass."""
    from wildfireguardian.routing.hazard import HazardSequence
    obs = z["obs_stack"].astype(np.float32)
    t = np.asarray(z["obs_times"], float)
    eps = 1e-6
    times, surfaces = [float(t[0])], [obs[0]]
    for k in range(1, len(t)):
        times.append(float(t[k - 1]) + eps)
        surfaces.append(obs[k])
        times.append(float(t[k]))
        surfaces.append(obs[k])
    return HazardSequence(grid=_grid(z), times_min=np.asarray(times, float), surfaces=list(surfaces))


def scene(speed: float):
    """The canonical 영덕 walk network at one flat speed; everything else as committed."""
    from measure_present_perimeter_yeongdeok import CANON, snapshot
    from run_multi_region_routing import read_poi_snapshot
    from wildfireguardian.routing.slope import build_walk_network, load_snapshot_graph

    prm = json.loads(CANON.read_text(encoding="utf-8"))["parameters"]
    G = load_snapshot_graph(snapshot("osm-walk", "yeongdeok-2025"))
    net, _ = build_walk_network(G, snapshot("srtm-dem", "yeongdeok-2025"),
                                sampling_m=float(prm["slope_sampling_m"]),
                                max_abs_slope=float(prm["max_abs_slope"]),
                                flat_speed_ms=float(speed), directed=True, apply_slope=True)
    dests, _ = read_poi_snapshot(snapshot("osm-shelters", "yeongdeok-2025"), kind="shelter")
    net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
    return prm, net, dests


def building_population(net, z):
    """Per building: snapped walk node or None (score_kspread.building_nodes, per building)."""
    from measure_last_safe_departure import MAX_SNAP
    from run_building_origin_routing import origin_filter
    from wildfireguardian.buildings import load_buildings

    bld = load_buildings("yeongdeok_2025", source="juso_main", repo=REPO)
    haz = z["haz_stack"].astype(np.float32)
    extent = tuple(float(v) for v in z["grid_extent"])
    keep, _, _ = origin_filter(bld.xy, haz, extent, 0.5)
    nodes = []
    for i in range(len(bld)):
        nid = net.nearest_node(float(bld.xy[i, 0]), float(bld.xy[i, 1]))
        x, y = net.node_xy(nid)
        ok = math.hypot(x - bld.xy[i, 0], y - bld.xy[i, 1]) <= MAX_SNAP and bool(keep[i])
        nodes.append(int(nid) if ok else None)
    return bld, nodes


def cmd_lsd(bound: str, speed: float, limit: int | None) -> int:
    from measure_last_safe_departure import BUDGET, P_CUT, STEP, lsd_search
    from wildfireguardian.routing.evacuation import future_aware_route

    t0 = time.monotonic()
    z = np.load(NPZ)
    prm, net, _ = scene(speed)
    _, nodes = building_population(net, z)
    uniq = sorted({n for n in nodes if n is not None})
    if limit:
        uniq = uniq[:limit]
    hazard = hazard_R(z) if bound == "R" else hazard_L(z)
    rows = {}
    for k, n in enumerate(uniq):
        lsd = float(lsd_search(net, n, hazard))
        walk = None
        if lsd >= 0:
            r = future_aware_route(net, n, hazard, departure_min=0.0, time_budget_min=BUDGET,
                                   p_cut=P_CUT, time_step_min=STEP)
            walk = round(float(r.total_time_min), 1) if r.reached else None
        rows[str(n)] = [lsd, walk]
        if (k + 1) % 250 == 0:
            print(f"  [{bound} {speed}] {k + 1}/{len(uniq)} {time.monotonic() - t0:.0f}s", flush=True)
    out = OUTDIR / f"lsd_{bound}_{speed:.1f}.json"
    OUTDIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "schema_version": 1, "bound": bound, "flat_speed_ms": speed,
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_commit": _commit(), "rule": __doc__,
        "inputs": {"npz": str(NPZ.relative_to(REPO)), "npz_sha256": _sha256(NPZ)},
        "parameters": {"p_cut": P_CUT, "budget_min": BUDGET, "step_min": STEP,
                       "slope_sampling_m": prm["slope_sampling_m"], "max_abs_slope": prm["max_abs_slope"]},
        "n_nodes": len(uniq),
        "per_node": rows,
        "per_node_fields": ["lsd_min (-1 never, 600 censored)", "walk_min_at_departure_0 (null if no safe route)"],
        "seconds": round(time.monotonic() - t0, 1)}, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)} ({len(uniq)} nodes, {time.monotonic() - t0:.0f}s)")
    return 0



def _b64(a: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")


def _to5179():
    from pyproj import Transformer
    return Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)


def _roi(net, bld_xy, dem_bounds_5179):
    xs = [net.node_xy(n)[0] for n in net.graph.nodes]
    ys = [net.node_xy(n)[1] for n in net.graph.nodes]
    x0 = min(min(xs), float(bld_xy[:, 0].min())) - TERRAIN_PAD_M
    x1 = max(max(xs), float(bld_xy[:, 0].max())) + TERRAIN_PAD_M
    y0 = min(min(ys), float(bld_xy[:, 1].min())) - TERRAIN_PAD_M
    y1 = max(max(ys), float(bld_xy[:, 1].max())) + TERRAIN_PAD_M
    dx0, dy0, dx1, dy1 = dem_bounds_5179
    x0, y0, x1, y1 = max(x0, dx0), max(y0, dy0), min(x1, dx1), min(y1, dy1)
    step = TERRAIN_STEP_M
    x0, y0 = math.floor(x0 / step) * step, math.floor(y0 / step) * step
    nx = int(math.ceil((x1 - x0) / step)) + 1
    ny = int(math.ceil((y1 - y0) / step)) + 1
    return x0, y0, nx, ny


def _terrain(dem_path: Path, x0, y0, nx, ny):
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import Resampling, reproject

    step = TERRAIN_STEP_M
    dst = np.full((ny, nx), np.nan, np.float32)
    # row 0 = NORTH edge; the payload flips to row 0 = SOUTH so y grows with the row index
    tr = from_origin(x0 - step / 2, y0 + (ny - 1) * step + step / 2, step, step)
    with rasterio.open(dem_path) as src:
        reproject(source=rasterio.band(src, 1), destination=dst, dst_transform=tr,
                  dst_crs="EPSG:5179", resampling=Resampling.bilinear, dst_nodata=np.nan)
    dst = dst[::-1]
    sea = ~np.isfinite(dst)
    h = np.where(sea, 0.0, np.clip(dst, 0.0, None))
    return np.round(h).astype(np.int16), sea


def _cell_times(z):
    """Per 500 m cell: first-detection pass index (0 = never) and forecast crossing minute."""
    from score_kspread import crossing_series
    obs = z["obs_stack"].astype(bool)
    first = np.zeros(obs.shape[1:], np.uint8)
    for k in range(obs.shape[0] - 1, -1, -1):
        first[obs[k]] = k + 1
    haz = z["haz_stack"].astype(np.float32)
    ht = np.asarray(z["haz_times"], float)
    fc = np.full(obs.shape[1:], 65535, np.uint16)
    rr, cc = np.where(haz.max(axis=0) >= 0.5)
    for r, c in zip(rr, cc):
        t = crossing_series(haz[:, r, c], ht)
        if math.isfinite(t):
            fc[r, c] = int(round(t))
    return first, fc


def _edge_closures(G5179, z, first, x0, y0, xw, yw):
    """Road segments in the ROI with the observation's R and L closure minute of their edge.

    An edge closes when any point sampled every 50 m along it lies in a detected cell (cell
    membership, the A5 reading): R = that cell's detection pass time, L = the previous pass.
    """
    t = np.asarray(z["obs_times"], float)
    gx0, gy0, gx1, gy1, cell = [float(v) for v in z["grid_extent"]]
    nrows, ncols = first.shape

    def closes(xs, ys):
        col = np.floor((xs - gx0) / cell).astype(int)
        row = np.floor((gy1 - ys) / cell).astype(int)
        ok = (col >= 0) & (col < ncols) & (row >= 0) & (row < nrows)
        k = np.zeros(len(xs), np.int64)
        k[ok] = first[row[ok], col[ok]]
        k = k[k > 0]
        if k.size == 0:
            return 65535, 65535
        kk = int(k.min())
        return int(round(t[kk - 1])), int(round(t[kk - 2])) if kk >= 2 else 0

    seen, segs, cl = set(), [], []
    for u, v, d in G5179.edges(data=True):
        key = (min(u, v), max(u, v))
        if key in seen or u == v:
            continue
        seen.add(key)
        if "geometry" in d:
            xs, ys = (np.asarray(a, float) for a in d["geometry"].xy)
        else:
            xs = np.array([G5179.nodes[u]["x"], G5179.nodes[v]["x"]], float)
            ys = np.array([G5179.nodes[u]["y"], G5179.nodes[v]["y"]], float)
        if not ((xs >= x0).all() and (xs <= x0 + xw).all() and (ys >= y0).all() and (ys <= y0 + yw).all()):
            continue
        seg_len = np.hypot(np.diff(xs), np.diff(ys))
        n_s = max(2, int(seg_len.sum() // 50) + 2)
        s_at = np.linspace(0, seg_len.sum(), n_s)
        cum = np.concatenate([[0], np.cumsum(seg_len)])
        sx, sy = np.interp(s_at, cum, xs), np.interp(s_at, cum, ys)
        r_min, l_min = closes(sx, sy)
        for i in range(len(xs) - 1):
            segs.append((xs[i] - x0, ys[i] - y0, xs[i + 1] - x0, ys[i + 1] - y0))
            cl.append((r_min, l_min))
    return np.round(np.asarray(segs)).astype(np.uint16), np.asarray(cl, np.uint16)


def _status_counts(lsd_l, lsd_r, weights, t):
    """Buildings per state at minute t (the rule the page draws with)."""
    out = {"walk_out_open": 0, "undetermined": 0, "too_late": 0}
    for n, w in weights.items():
        lo, hi = lsd_l[n], lsd_r[n]
        if hi < 0 or t > hi:
            out["too_late"] += w
        elif lo >= 0 and t <= lo:
            out["walk_out_open"] += w
        else:
            out["undetermined"] += w
    return out


def cmd_assemble(dev_out: str | None = None) -> int:
    """``dev_out``: front-end development only. Missing runs/nodes are filled with 600 and
    the payload goes to that path; no artifact under data/processed is written."""
    import gzip as _gz
    import osmnx as ox
    import rasterio

    from measure_present_perimeter_yeongdeok import snapshot
    from wildfireguardian.routing.slope import load_snapshot_graph

    t_start = time.monotonic()
    z = np.load(NPZ)
    prm, net, dests = scene(0.7)
    bld, nodes = building_population(net, z)
    runs = {}
    for b in BOUNDS:
        for s in SPEEDS:
            p = OUTDIR / f"lsd_{b}_{s:.1f}.json"
            if dev_out and not p.exists():
                runs[(b, s)] = {}
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            runs[(b, s)] = {int(k): v for k, v in d["per_node"].items()}
    uniq = sorted({n for n in nodes if n is not None})
    for key, r in runs.items():
        missing = [n for n in uniq if n not in r]
        if missing and dev_out:
            for n in missing:
                r[n] = [600.0, None]
        elif missing:
            raise SystemExit(f"STOP: run {key} lacks {len(missing)} nodes; re-run it without --limit")

    dem_p = snapshot("srtm-dem", "yeongdeok-2025")
    with rasterio.open(dem_p) as src:
        b = src.bounds
    tf = _to5179()
    cx, cy = tf.transform([b.left, b.right, b.left, b.right], [b.bottom, b.bottom, b.top, b.top])
    dem_b = (max(cx[0], cx[2]), max(cy[0], cy[1]), min(cx[1], cx[3]), min(cy[2], cy[3]))
    x0, y0, nx, ny = _roi(net, bld.xy, dem_b)
    xw, yw = (nx - 1) * TERRAIN_STEP_M, (ny - 1) * TERRAIN_STEP_M
    heights, sea = _terrain(dem_p, x0, y0, nx, ny)

    first, fcast = _cell_times(z)
    gx0, gy0, gx1, gy1, cell = [float(v) for v in z["grid_extent"]]
    c0 = max(0, int(math.floor((x0 - gx0) / cell)))
    c1 = min(first.shape[1], int(math.ceil((x0 + xw - gx0) / cell)))
    r0 = max(0, int(math.floor((gy1 - (y0 + yw)) / cell)))
    r1 = min(first.shape[0], int(math.ceil((gy1 - y0) / cell)))
    fire_first = first[r0:r1, c0:c1][::-1].copy()     # row 0 = south
    fire_fcast = fcast[r0:r1, c0:c1][::-1].copy()
    fire_origin = (gx0 + c0 * cell - x0, gy1 - r1 * cell - y0)

    G = load_snapshot_graph(snapshot("osm-walk", "yeongdeok-2025"))
    G5179 = ox.project_graph(G, to_crs="EPSG:5179")
    segs, seg_close = _edge_closures(G5179, z, first, x0, y0, xw, yw)

    # buildings: every 도로명주소 주건물 in the ROI; floors joined from the source file
    floors = {}
    with _gz.open(REPO / bld.source_file, "rt", encoding="utf-8") as fh:
        for f in json.load(fh)["features"]:
            pr = f["properties"]
            floors[str(pr["bd_mgt_sn"])] = int(pr.get("gro_flo_co") or 1)
    node_index = {n: i for i, n in enumerate(uniq)}
    inside = ((bld.xy[:, 0] >= x0) & (bld.xy[:, 0] <= x0 + xw) & (bld.xy[:, 1] >= y0) & (bld.xy[:, 1] <= y0 + yw))
    sel = np.where(inside)[0]
    bx = np.round(bld.xy[sel, 0] - x0).astype(np.uint16)
    by = np.round(bld.xy[sel, 1] - y0).astype(np.uint16)
    bsize = np.clip(np.round(np.sqrt(np.asarray(bld.area_m2, float)[sel])), 3, 255).astype(np.uint8)
    bfl = np.array([min(floors.get(str(bld.ids[i]), 1), 30) for i in sel], np.uint8)
    bnode = np.array([node_index[nodes[i]] if nodes[i] is not None else -1 for i in sel], np.int32)

    per_speed = {}
    weights = {}
    for n in nodes:
        if n is not None:
            weights[n] = weights.get(n, 0) + 1
    scene_counts = {}
    for s in SPEEDS:
        lsd_r = np.array([runs[("R", s)][n][0] for n in uniq], np.int16)
        lsd_l = np.array([runs[("L", s)][n][0] for n in uniq], np.int16)
        walk = np.array([65535 if runs[("R", s)][n][1] is None else int(round(runs[("R", s)][n][1])) for n in uniq], np.uint16)
        per_speed[f"{s:.1f}"] = {"lsdR": _b64(lsd_r), "lsdL": _b64(lsd_l), "walkR": _b64(walk)}
        dl = {n: runs[("L", s)][n][0] for n in uniq}
        dr = {n: runs[("R", s)][n][0] for n in uniq}
        scene_counts[f"{s:.1f}"] = {str(t): _status_counts(dl, dr, weights, t) for t in (0, 60, 180, 332, 334, 600)}
        scene_counts[f"{s:.1f}"]["bracket_violations"] = int(sum(1 for n in uniq if dl[n] > dr[n]))

    refuges = [(round(d.x - x0), round(d.y - y0)) for d in dests
               if x0 <= d.x <= x0 + xw and y0 <= d.y <= y0 + yw]
    labels = []
    ag = json.loads(AGENCIES.read_text(encoding="utf-8"))
    for f in ag["features"]:
        pr = f["properties"]
        if pr.get("subtype") not in ("읍면동", "시군구", "119안전센터", "소방서"):
            continue
        lx, ly = tf.transform(*f["geometry"]["coordinates"])
        if x0 <= lx <= x0 + xw and y0 <= ly <= y0 + yw:
            labels.append({"name": pr["name"], "kind": pr["subtype"], "x": round(lx - x0), "y": round(ly - y0)})

    payload = {
        "schema_version": 1,
        "title": "영덕 2025-03-25 밤, 위성 관측으로 다시 그린 3D 재생",
        "t0_utc": T0_UTC, "t0_kst": "2025-03-25 21:25",
        "obs_times_min": [float(v) for v in z["obs_times"]],
        "horizon_min": 600,
        "speeds": [f"{s:.1f}" for s in SPEEDS],
        "origin_5179": [x0, y0],
        "terrain": {"nx": nx, "ny": ny, "step": TERRAIN_STEP_M, "h": _b64(heights),
                    "sea": _b64(sea.astype(np.uint8))},
        "fire": {"ncols": int(fire_first.shape[1]), "nrows": int(fire_first.shape[0]), "cell": cell,
                 "origin": [round(fire_origin[0], 1), round(fire_origin[1], 1)],
                 "first_pass": _b64(fire_first), "forecast_min": _b64(fire_fcast)},
        "roads": {"n": int(len(segs)), "xy": _b64(segs), "close": _b64(seg_close)},
        "buildings": {"n": int(len(sel)), "x": _b64(bx), "y": _b64(by), "size": _b64(bsize),
                      "floors": _b64(bfl), "node": _b64(bnode)},
        "nodes": {"n": len(uniq), "per_speed": per_speed},
        "refuges": refuges, "labels": labels,
        "sources": {
            "fire": "data/processed/routing_demo_canonical.npz obs_stack (FIRMS, cumulative, 500 m)",
            "forecast": "same file, haz_stack p>=0.5 crossing (hindcast, leave-one-complex-out)",
            "terrain": str(dem_p.relative_to(REPO)),
            "roads": str(snapshot('osm-walk', 'yeongdeok-2025').relative_to(REPO)),
            "buildings": bld.source_file, "refuges": str(snapshot('osm-shelters', 'yeongdeok-2025').relative_to(REPO)),
            "labels": str(AGENCIES.relative_to(REPO)),
            "deadlines": [f"data/processed/finals3d/lsd_{b}_{s:.1f}.json" for b in BOUNDS for s in SPEEDS]},
    }
    if dev_out:
        Path(dev_out).write_text("window.WFG3D=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
        print(f"DEV payload -> {dev_out}; counts {json.dumps(scene_counts)[:400]}")
        return 0
    WEB_DATA.parent.mkdir(parents=True, exist_ok=True)
    WEB_DATA.write_text("window.WFG3D=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")

    summary = {
        "schema_version": 1, "title": "3D booth replay scene: what the page draws, counted here",
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "git_commit": _commit(),
        "rule": __doc__, "web_payload": str(WEB_DATA.relative_to(REPO)),
        "web_payload_sha256": _sha256(WEB_DATA),
        "roi_5179": [x0, y0, x0 + xw, y0 + yw], "terrain_grid": [nx, ny], "terrain_step_m": TERRAIN_STEP_M,
        "buildings_in_roi": int(len(sel)), "buildings_routable_in_roi": int((bnode >= 0).sum()),
        "buildings_routable_total": int(sum(weights.values())), "nodes": len(uniq),
        "road_segments": int(len(segs)), "refuges_in_roi": len(refuges),
        "status_rule": "too_late if LSD_R < 0 or t > LSD_R; walk_out_open if LSD_L >= 0 and t <= LSD_L; else undetermined",
        "status_counts_buildings": scene_counts,
        "seconds": round(time.monotonic() - t_start, 1)}
    out = OUTDIR / "finals3d_scene.json"
    out.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "rule"}, indent=1, ensure_ascii=False))
    print(f"web payload {WEB_DATA.stat().st_size / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("lsd")
    a.add_argument("--bound", choices=BOUNDS, required=True)
    a.add_argument("--speed", type=float, required=True)
    a.add_argument("--limit", type=int, default=None)
    asm = sub.add_parser("assemble")
    asm.add_argument("--dev-out", default=None)
    args = ap.parse_args()
    if args.cmd == "lsd":
        raise SystemExit(cmd_lsd(args.bound, args.speed, args.limit))
    raise SystemExit(cmd_assemble(args.dev_out))
