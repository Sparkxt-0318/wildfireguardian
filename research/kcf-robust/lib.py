"""Shared harness for kcf-robust (PROTOCOL.md sections 2-3): lattice, known-area distance, reach curves, closure
rasters, dilation and shift, and the product run (``product/wfg-roadlayer`` pipeline, unchanged)."""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PRODUCT = REPO / "product/wfg-roadlayer"
for p in (PRODUCT, REPO / "research/kcf-replay", REPO / "research/kcf-validate/twin", REPO / "research/kcf-idea-routing", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import measured_arms as MA  # noqa: E402
from wfg_roadlayer import engine, fireinput, geotiff, pipeline, regiondata  # noqa: E402
from wfg_roadlayer import settings as settings_mod  # noqa: E402

# KFS_01 375 m lattice over both regions (examples/build_example_raster.py, twin_lib.cell_xy)
X0, Y0, RES, W, HH = 1093875.0, 1815750.0, 375.0, 214, 67
HORIZON_S = 8 * 3600
DWELL = 120
INF = math.inf
REGIONS = ("uiseong_andong_2025", "yeongdeok_2025")
REPLAY_ISSUES = [datetime(2025, 3, 25, h, 0, tzinfo=timezone.utc) for h in range(3, 16)]
R50 = json.loads((HERE / "r50.json").read_text())["km"]


def cell_centres():
    cols = np.arange(W)
    rows = np.arange(HH)  # south-up
    cx = (X0 + (cols + 0.5) * RES)[None, :].repeat(HH, 0).ravel()
    cy = (Y0 + (rows + 0.5) * RES)[:, None].repeat(W, 1).ravel()
    return cx, cy


def known_distance_m(discs, T):
    """min over discs with t < T of max(0, |centre - disc centre| - radius), per lattice cell (flat, south-up)."""
    cx, cy = cell_centres()
    sel = [x for x in discs if x["t"] < T]
    d = np.full(cx.shape, np.inf)
    if sel:
        Xd = np.array([x["x"] for x in sel]); Yd = np.array([x["y"] for x in sel]); Rd = np.array([x["r_m"] for x in sel])
        for i in range(0, len(sel), 2000):
            dd = np.sqrt((cx[:, None] - Xd[None, i:i + 2000]) ** 2 + (cy[:, None] - Yd[None, i:i + 2000]) ** 2) - Rd[None, i:i + 2000]
            d = np.minimum(d, np.maximum(dd, 0).min(1))
    return d


def load_discs():
    return [dict(x, t=datetime.fromisoformat(x["t_utc"])) for x in
            json.loads((REPO / "research/kcf-replay/fire_discs.json").read_text())["discs"]]


# ------------------------------------------------------------------------------------------------ reach curves
def curve_closure_s(knots, d_m):
    """First second h (float) at which the piecewise-linear non-decreasing curve through knots [(h_s, km)] reaches
    d_m metres; inf if it never does within the last knot. Equals measured_arms.closure_s for (0,0),(5h,R5),(8h,R8)."""
    if d_m <= knots[0][1] * 1000.0:
        return float(knots[0][0])
    for (h0, g0), (h1, g1) in zip(knots, knots[1:]):
        g0m, g1m = g0 * 1000.0, g1 * 1000.0
        if d_m <= g1m:
            if g1m == g0m:
                return float(h0)
            return h0 + (d_m - g0m) / (g1m - g0m) * (h1 - h0)
    return INF


def minutes_from_curve(d, knots, H=HORIZON_S):
    """Raster minutes as run_twin.system_minutes / build_example_raster: ceil(closure s)/60 if <= H, else inf."""
    out = np.full(d.shape, np.inf)
    for k in np.flatnonzero(np.isfinite(d)):
        s = curve_closure_s(knots, float(d[k]))
        if s <= H:
            out[k] = int(math.ceil(s)) / 60.0
    return out


def minutes_r90(d, r5_m, r8_m, H=HORIZON_S):
    """The product's MEASURED raster through measured_arms.closure_s itself."""
    out = np.full(d.shape, np.inf)
    for k in np.flatnonzero(np.isfinite(d)):
        s = MA.closure_s(r5_m, r8_m, float(d[k]))
        if s <= H:
            out[k] = int(math.ceil(s)) / 60.0
    return out


def knots_measured(r5_km, r8_km):
    return [(0, 0.0), (5 * 3600, r5_km), (8 * 3600, r8_km)]


def knots_r50(cls):
    c = R50[cls if cls in R50 else "all"]
    return knots_measured(c["R5_a0.5"], c["R8_a0.5"])


@lru_cache(maxsize=None)
def _ee():
    import pandas as pd
    d = pd.read_csv(REPO / "research/kcf-adaptive4/derived/expected_error.csv.gz")
    return d


def knots_expected(T, kind, p="90"):
    """E raster curve: running max over leads of margin_km + err_qP_km. kind 'DET' (latest KFS_01 row <= T) or 'KR'
    (median over all KR rows per lead)."""
    d = _ee()
    col = "err_q%s_km" % p
    if kind == "DET":
        x = d[(d.set == "DET") & (d.fire == "KFS_01")].copy()
        x["t"] = [datetime.fromisoformat(s).replace(tzinfo=timezone.utc) for s in x.t_utc]
        t_use = max(t for t in x.t if t <= T)
        x = x[x.t == t_use]
        vals = {int(r.lead_h): float(r.margin_km + r[col]) for _, r in x.iterrows()}
        src = "DET KFS_01 t_utc %s" % t_use.strftime("%Y-%m-%d %H:%M")
    else:
        x = d[d.set == "KR"]
        vals = {int(h): float((g.margin_km + g[col]).median()) for h, g in x.groupby("lead_h")}
        src = "KR median over %d rows" % len(x)
    knots, run = [(0, 0.0)], 0.0
    for h in range(1, 9):
        run = max(run, max(vals[h], 0.0))
        knots.append((h * 3600, run))
    return knots, src


# ------------------------------------------------------------------------------------------------ raster ops
def dilate_minutes(m, r_km):
    """Raster value = min over cells whose centres are within r_km of the cell's centre (cell itself included)."""
    a = m.reshape(HH, W)
    if r_km <= 0:
        return a.ravel().copy()
    k = int(math.floor(r_km * 1000.0 / RES + 1e-9))
    out = a.copy()
    rr = (r_km * 1000.0 / RES) ** 2 + 1e-9
    for di in range(-k, k + 1):
        for dj in range(-k, k + 1):
            if (di == 0 and dj == 0) or di * di + dj * dj > rr:
                continue
            sh = np.full_like(a, np.inf)
            ys = slice(max(di, 0), HH + min(di, 0)); yd = slice(max(-di, 0), HH + min(-di, 0))
            xs = slice(max(dj, 0), W + min(dj, 0)); xd = slice(max(-dj, 0), W + min(-dj, 0))
            sh[yd, xd] = a[ys, xs]
            out = np.minimum(out, sh)
    return out.ravel()


def write_tif(path, minutes_flat, T, source):
    grid = minutes_flat.reshape(HH, W)[::-1]  # north-up
    md = {"WFG_ISSUE_TIME": T.strftime("%Y-%m-%dT%H:%M:%SZ"), "WFG_HORIZON_MIN": "480", "WFG_UNITS": "minutes", "WFG_SOURCE": source}
    geotiff.write(path, grid, (RES, 0.0, X0, 0.0, -RES, Y0 + RES * HH), 5179, nodata=float("nan"), metadata=md)


# ------------------------------------------------------------------------------------------------ regions and mapping
@lru_cache(maxsize=None)
def region(rid):
    return regiondata.Region(rid, regiondata.default_cache())


@lru_cache(maxsize=None)
def road_pixel_map(rid):
    """road cell -> lattice pixel (flat south-up index). The road grid is a sub-window of the lattice."""
    road = region(rid).road
    ox = int(round((float(road.x0) - X0) / RES)); oy = int(round((float(road.y0) - Y0) / RES))
    assert abs(float(road.res) - RES) < 1e-9
    m = {}
    for c in road.road_cells:
        r, cc = divmod(int(c), road.W)
        m[c] = (r + oy) * W + (cc + ox)
    return m


def close_s_from_minutes(rid, minutes_flat, H=HORIZON_S):
    """road cell -> closure second, as fireinput._classify / _cell_reduce for a raster on this lattice (one pixel per
    road cell). Cells with no closure within H are absent."""
    pm = road_pixel_map(rid)
    out = {}
    for c, k in pm.items():
        v = minutes_flat[k]
        if not np.isfinite(v):
            continue
        if v <= 0:
            out[c] = 0
            continue
        if v <= H / 60.0:
            s = int(math.floor(60.0 * v + 1e-6))
            if s <= H:
                out[c] = max(s, 0)
    return out


def close_array_from_minutes(rid, minutes_flat, H=HORIZON_S):
    from reachpass import NONE
    road = region(rid).road
    a = np.full(road.W * road.H, NONE, np.int64)
    for c, b in close_s_from_minutes(rid, minutes_flat, H).items():
        a[c] = b
    return a


# ------------------------------------------------------------------------------------------------ product run
_SETTINGS = None


def settings():
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = settings_mod.load(None)
    return _SETTINGS


class _Fire:
    def __init__(self, arrival_s, issue, H):
        self.arrival_s = arrival_s
        self.horizon_s = H
        self.issue_utc = issue
        self.uncovered = []
        self.uncovered_set = set()


def _shelter_job_last_only(job):
    """engine._shelter_job without the witness at the issue time (the 'leave now' route, never used here); the issue
    sets and the witness at the latest departure are computed exactly as the product does."""
    snode, acc, origins = job
    inst = engine._W["inst"]
    E = len(inst.tail)
    inst.A = [[] for _ in range(E)]
    for j in engine._W["inc"].get(snode, []):
        inst.A[j] = list(acc)
    inst.AN = {}
    inst.IB = {}
    fld = engine.core.backward(inst)
    out = {}
    for on, ib in origins:
        inst.IB = {on: ib}
        S = engine.core.issue_set(fld, on)
        res = {"set": [list(p) for p in S], "w_last": None, "w_first": None}
        if S:
            res["w_last"] = engine._legs(engine.core.witness(fld, on, S[-1][1]))
        out[on] = res
    inst.IB = {}
    return snode, out, fld.stats["pushes"]


engine._shelter_job = _shelter_job_last_only


def run_product(rid, close_s, T, workers=4, H=HORIZON_S):
    """pipeline.compute's field step on a closure dict (same build_instance / accept / origin_closure / run_passes /
    assemble). Returns (rows, inst)."""
    from collections import defaultdict
    reg = region(rid)
    cfg = settings()
    fire = _Fire(dict(close_s), T, H)
    inst = engine.build_instance(reg.road, close_s, H)
    jobs_by = defaultdict(set)
    for o in reg.origins:
        if o["node"] is None or not o["checkable"]:
            continue
        for s in reg.cands.get(o["id"], []):
            jobs_by[s["node"]].add(o["node"])
    jobs = [(sn, engine.accept(reg.road, close_s, sn, H, DWELL),
             [(on, engine.origin_closure(reg.road, close_s, on, H)) for on in sorted(ons)]) for sn, ons in sorted(jobs_by.items())]
    results = engine.run_passes(reg.road, inst, jobs, workers)
    rows = engine.assemble(reg, fire, cfg, inst, results, close_s)
    return rows, inst


def summarise_rows(rows):
    """Per place: refusal, L, cut, advised route legs at L (EDGE legs), shelter node, A."""
    out = {}
    for r in rows:
        o = r["origin"]
        if r["refusal"]:
            out[o["id"]] = {"refused": r["refusal"][0]}
            continue
        last = r.get("last")
        out[o["id"]] = {"refused": None, "L": r["L"] if r["L"] is not None else -1, "cut": r["cut"], "A": r["A"],
                        "shelter_node": last["shelter"]["node"] if last else None,
                        "legs": last["w_last"]["legs"] if last else None,
                        "arrival": last["w_last"]["arrival"] if last else None}
    return out
