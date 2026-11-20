"""Optional fragility columns and pages (``run --fragility``), from research/kcf-robust.

For every village, for leaving **now** (at the issue time):

* **tolerated extra reach** (km): the largest r on a 0.125 km grid (0 to 15 km) such that a safe route still
  exists when the fire reaches r km farther than the input raster says, at every moment (the raster dilated by r:
  each pixel takes the earliest arrival within r of it). "< 0": no safe route even on the raster as given;
  ">= 15": still safe at 15 km.
* **tolerated timing error** (min): the largest m on a 60 s grid such that a safe route still exists when every
  closure (roads, waiting, the village, the shelter) happens m seconds earlier than the raster says. Closures here
  are permanent, so this is the closure-timing margin of research/kcf-idea-routing (the margin field) with the
  shelter's own burn time also uncertain; the end of the horizon is not moved.
* **binding road**: on the route that still works at the tolerated reach (and at the tolerated timing error), the
  road with the least time between the vehicle entering it and its closure: the road that fails first.

Method: for a fixed departure (the issue time) and a fixed closure level, the earliest-arrival search over edge
states (turn bans respected, no waiting: with permanent closures waiting never helps) finds a safe route iff one
exists. The closure levels are nested, so the largest safe level is found by bisection. This is a forward search,
independent of the research code's backward pass; research/kcf-robust checks the two agree. Standard library and
numpy only.

Model output · advisory · not an order.
"""
from __future__ import annotations

import heapq
import math
import tempfile
from pathlib import Path

import numpy as np

from . import fireinput, geotiff

R_STEP_KM = 0.125
R_MAX_KM = 15.0
M_STEP_S = 60
NONE = 1 << 50


class _Edges:
    """Per-edge segment arrays for fast closure-start computation (replay.py rule, exact integer arithmetic)."""

    def __init__(self, road):
        self.road = road
        E = len(road.tail)
        seg_edge, seg_cell, seg_fl = [], [], []
        for j, segs in enumerate(road.seg):
            for c, zb in segs:
                seg_edge.append(j)
                seg_cell.append(int(c))
                seg_fl.append((road.D[j] * zb.numerator) // zb.denominator)
        self.E = E
        self.seg_edge = np.asarray(seg_edge, np.int64)
        self.seg_cell = np.asarray(seg_cell, np.int64)
        self.seg_fl = np.asarray(seg_fl, np.int64)
        self.ncell = road.W * road.H
        self.out = road.out_by_node
        self.forbidden = road.forbidden
        self.D = road.D
        self.head = road.head

    def lo(self, close_arr, H):
        """First start second at which each edge meets a closed cell (engine.build_instance), NONE if none <= H."""
        b = close_arr[self.seg_cell]
        s = np.where(b < NONE, np.maximum(b - self.seg_fl, 0), NONE)
        lo = np.full(self.E, NONE, np.int64)
        np.minimum.at(lo, self.seg_edge, s)
        lo[lo > H] = NONE
        return lo


def close_array(close_s: dict, ncell: int) -> np.ndarray:
    a = np.full(ncell, NONE, np.int64)
    for c, b in close_s.items():
        a[int(c)] = int(b)
    return a


def route_now(ed: _Edges, lo, close_arr, o: int, shelters, H: int, dwell: int, node_cell):
    """Earliest-arrival safe journey departing at 0 from origin node o to any of the shelter nodes at this closure
    level. Returns (shelter node, [(edge, entry second)], arrival, accepted-latest) or None."""
    bo = close_arr[node_cell[o]]
    if bo < NONE and bo <= 0:
        return None
    acc = {}
    for sn in shelters:
        b = close_arr[node_cell[sn]]
        a = H - dwell
        if b < NONE:
            a = min(a, max(b - dwell, 0) - 1)
        acc[sn] = a
    best, h = {}, []
    for j in ed.out.get(o, []):
        a = ed.D[j]
        if 0 <= lo[j] - 1 and a <= H:
            best[j] = (a, None)
            heapq.heappush(h, (a, j))
    while h:
        a, j = heapq.heappop(h)
        if best[j][0] != a:
            continue
        v = ed.head[j]
        if v in acc and a <= acc[v]:
            legs, k = [], j
            while k is not None:
                ak, pk = best[k]
                legs.append((k, ak - ed.D[k]))
                k = pk
            return v, legs[::-1], a, acc[v]
        for k in ed.out.get(v, []):
            if (j, k) in ed.forbidden:
                continue
            b = a + ed.D[k]
            if a <= lo[k] - 1 and b <= H and (k not in best or b < best[k][0]):
                best[k] = (b, j)
                heapq.heappush(h, (b, k))
    return None


def dilate(data: np.ndarray, r_pix: float) -> np.ndarray:
    """Each pixel takes the minimum (earliest arrival) over pixels whose centres lie within r_pix pixels.
    NaN (no data) pixels do not spread and stay NaN."""
    a = np.where(np.isnan(data), np.inf, data)
    out = a.copy()
    k = int(math.floor(r_pix + 1e-9))
    rr = r_pix * r_pix + 1e-9
    Hh, W = a.shape
    for di in range(-k, k + 1):
        for dj in range(-k, k + 1):
            if (di == 0 and dj == 0) or di * di + dj * dj > rr:
                continue
            sh = np.full_like(a, np.inf)
            ys = slice(max(di, 0), Hh + min(di, 0)); yd = slice(max(-di, 0), Hh + min(-di, 0))
            xs = slice(max(dj, 0), W + min(dj, 0)); xd = slice(max(-dj, 0), W + min(-dj, 0))
            sh[yd, xd] = a[ys, xs]
            out = np.minimum(out, sh)
    return np.where(np.isnan(data), np.nan, out)


def _levels_reach(raster_path, road, issue, horizon_min, not_reached_value):
    """Closure arrays for r = 0, 0.125, ..., 15 km: the input raster dilated, read by the product's own resampling."""
    r = geotiff.read(raster_path)
    a, b, c, d, e, f = r.affine
    if not (r.epsg == 5179 and b == 0 and d == 0 and abs(abs(a) - abs(e)) < 1e-9):
        return None, "fragility needs an axis-aligned EPSG:5179 raster with square pixels"
    ncell = road.W * road.H
    levels, radii = [], []
    data = np.asarray(r.data, float)
    nd = r.nodata
    if nd is not None and not math.isnan(nd):
        data = np.where(data == nd, np.nan, data)
    with tempfile.TemporaryDirectory(prefix="wfg_frag_") as td:
        n = int(round(R_MAX_KM / R_STEP_KM))
        for k in range(n + 1):
            rk = k * R_STEP_KM
            dd = dilate(data, rk * 1000.0 / abs(a)) if k else data
            p = Path(td) / "d.tif"
            geotiff.write(p, dd, r.affine, 5179, nodata=float("nan"), metadata=dict(r.metadata))
            fi = fireinput.load_geotiff(p, road, issue_utc=issue, horizon_min=horizon_min, not_reached_value=not_reached_value)
            levels.append(close_array(fi.arrival_s, ncell))
            radii.append(rk)
    return (levels, radii), None


def _bisect(ok, n):
    """Largest k in [0, n] with ok(k), for ok monotone non-increasing; -1 if not ok(0)."""
    if not ok(0):
        return -1
    if ok(n):
        return n
    lo, hi = 0, n
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if ok(mid):
            lo = mid
        else:
            hi = mid
    return lo


def binding(ed, lo, close_arr, res, road, ways):
    sn, legs, arr, acc = res
    cand = [(int(lo[j]) - s, "edge", j) for j, s in legs if lo[j] < NONE]
    cand.append((acc - arr, "shelter", sn))
    slack, kind, x = min(cand)
    if kind != "edge":
        return {"kind": kind, "slack_s": int(slack), "way": None, "label": "대피소 / shelter"}
    w = road.source_way[x]
    info = ways.get(str(w)) or {}
    label = " ".join(t for t in ((info.get("ref") or ""), (info.get("name") or "")) if t) or "OSM way %s" % w
    return {"kind": "edge", "slack_s": int(slack), "way": w, "edge": int(x), "label": label}


def load_ways(region_id, product_dir):
    import csv
    import gzip
    p = Path(product_dir) / "data/edges" / ("%s_ways.csv.gz" % region_id)
    if not p.is_file():
        return {}
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return {r["source_way"]: r for r in csv.DictReader(f)}


def compute(c: dict, raster_path, product_dir, log=print) -> dict:
    """Per village id: {'reach_km', 'reach_censored', 'timing_s', 'timing_censored', 'reach_binding', 'timing_binding'}.
    ``c`` is pipeline.compute's result."""
    region, fire, H, dwell = c["region"], c["fire"], c["H"], c["dwell"]
    road = region.road
    ed = _Edges(road)
    ways = load_ways(region.id, product_dir)
    lv, why = _levels_reach(raster_path, road, fire.issue_utc, fire.horizon_s / 60.0, None) if raster_path else (None, "fragility needs a raster input")
    base = close_array(c["close_s"], road.W * road.H)
    los = {}

    def lo_of(key, arr):
        if key not in los:
            los[key] = ed.lo(arr, H)
        return los[key]

    out = {}
    for row in c["rows"]:
        o = row["origin"]
        if row["refusal"]:
            continue
        on = o["node"]
        sns = [s["node"] for s in row["candidates"]]

        def at(key, arr):
            return route_now(ed, lo_of(key, arr), arr, on, sns, H, dwell, road.node_cell)

        rec = {"method": "forward earliest-arrival search per closure level, bisection (wfg_roadlayer/fragility.py)"}
        if lv is not None:
            levels, radii = lv
            k = _bisect(lambda i: at(("r", i), levels[i]) is not None, len(levels) - 1)
            rec["reach_km"] = radii[k] if k >= 0 else None
            rec["reach_censored"] = k == len(levels) - 1
            res = at(("r", k), levels[k]) if k >= 0 else None
            rec["reach_binding"] = binding(ed, lo_of(("r", k), levels[k]), levels[k], res, road, ways) if res else None
        else:
            rec["reach_km"], rec["reach_censored"], rec["reach_binding"], rec["reach_note"] = None, False, None, why

        def shifted(m):
            s = base.copy()
            f = s < NONE
            s[f] = np.maximum(s[f] - m, 0)
            return s

        nm = H // M_STEP_S
        cache = {}

        def ok_m(i):
            if i not in cache:
                cache[i] = shifted(i * M_STEP_S)
            return at(("m", i), cache[i]) is not None

        k = _bisect(ok_m, nm)
        rec["timing_s"] = k * M_STEP_S if k >= 0 else None
        rec["timing_censored"] = k == nm
        if k >= 0:
            arr = cache.get(k) if k in cache else shifted(k * M_STEP_S)
            res = at(("m", k), arr)
            rec["timing_binding"] = binding(ed, lo_of(("m", k), arr), arr, res, road, ways) if res else None
        else:
            rec["timing_binding"] = None
        out[o["id"]] = rec
    log("fragility: %d villages" % len(out))
    return out
