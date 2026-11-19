"""Paradise run (PROTOCOL.md amendments 9-11): fire field reconstructed from NIST TN 2135 progression rows, closures at arrival, the unchanged
roadlayer engine (vendored F-3.1 deadline field) on a Paradise/Chico road graph, comparison with NIST burnover/closure records.
Usage: python3 -I paradise_run.py GRAPH.json GEO_DIR PLACES.parquet OUT_DIR [WORKERS]
Model output on a reconstruction. Not what happened to people."""
import csv, json, math, sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import shapely
from pyproj import Transformer
from scipy.interpolate import RBFInterpolator
from scipy.spatial import Delaunay, cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "product/wfg-roadlayer"))
from wfg_roadlayer import regiondata, engine, settings as rl_settings  # noqa: E402

GRAPH, GEO, PLACES, OUT = sys.argv[1], Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
WORKERS = int(sys.argv[5]) if len(sys.argv) > 5 else 4
OUT.mkdir(parents=True, exist_ok=True)
ISSUES = {"07:30": 450, "08:00": 480, "08:30": 510, "09:00": 540}  # minutes after 2018-11-08 00:00 PST
H = 8 * 3600
TO_LL = Transformer.from_crs(32610, 4326, always_xy=True); TO_UTM = Transformer.from_crs(4326, 32610, always_xy=True)


def minutes(date, hhmm):
    d = {"11/8": 0, "11/9": 1440, "11/10": 2880}[date]
    h, m = hhmm.split(":")
    return d + int(h) * 60 + int(m)


# ------------------------------------------------------------------ observations and field
obs = {}
for r in csv.DictReader(open(GEO / "geocoded_progression.csv", encoding="utf-8-sig")):
    if r["rule"] == "NOT GEOCODED" or not r["start"] or r["date"] not in ("11/8", "11/9", "11/10"):
        continue
    key = (round(float(r["x"]) / 50), round(float(r["y"]) / 50))
    t = minutes(r["date"], r["start"])
    if key not in obs or t < obs[key][2]:
        obs[key] = (float(r["x"]), float(r["y"]), t)
P = np.array([[o[0], o[1]] for o in obs.values()]) / 1000.0; T = np.array([o[2] for o in obs.values()], float)
print("unique-location observations", len(T), "time range", T.min(), T.max())
SMOOTH = 1.0
rbf = RBFInterpolator(P, T, kernel="thin_plate_spline", smoothing=SMOOTH)
# leave-one-out
loo = []
for i in range(len(T)):
    m = np.ones(len(T), bool); m[i] = False
    pred = RBFInterpolator(P[m], T[m], kernel="thin_plate_spline", smoothing=SMOOTH)(P[i:i + 1])[0]
    loo.append(pred - T[i])
loo = np.array(loo)
loo_stats = {"n": int(len(loo)), "median_abs_min": float(np.median(np.abs(loo))), "p25_p75_abs_min": [float(np.percentile(np.abs(loo), 25)), float(np.percentile(np.abs(loo), 75))],
             "within_30min": int((np.abs(loo) <= 30).sum()), "within_60min": int((np.abs(loo) <= 60).sum()), "bias_mean_min": float(loo.mean())}
print("LOO", loo_stats)

# ------------------------------------------------------------------ graph and cells
raw = json.load(open(GRAPH))
g = raw["grid"]; X0, Y0, RES, W, Hh = g["x0"], g["y0"], g["resolution"], g["width"], g["height"]
cx = X0 + (np.arange(W) + 0.5) * RES; cy = Y0 + (np.arange(Hh) + 0.5) * RES
CX, CY = np.meshgrid(cx, cy)
cells_xy = np.column_stack([CX.ravel() / 1000.0, CY.ravel() / 1000.0])
d_obs, _ = cKDTree(P).query(cells_xy)
reached = d_obs <= 2.0
A = np.full(CX.size, np.inf)
A[reached] = np.maximum(rbf(cells_xy[reached]), T.min())   # minutes after 2018-11-08 00:00 PST
Agrid = A.reshape(Hh, W)
print("cells reached by the field", int(reached.sum()), "of", reached.size)

# ------------------------------------------------------------------ origins and shelters (amendment 9)
nodes = raw["nodes"]
nid = {n["id"]: i for i, n in enumerate(nodes)}
nxy = np.array([[n["x"], n["y"]] for n in nodes])
inc = {}
for e in raw["edges"]:
    inc.setdefault(e["u"], []).append(e["class"])
hull = Delaunay(P * 1000.0)
cand_nodes = []
for i, n in enumerate(nodes):
    cls = inc.get(n["id"], [])
    if len(cls) < 3 or sum(c in ("residential", "tertiary") for c in cls) < 2:
        continue
    p = nxy[i]
    near = hull.find_simplex(p[None, :])[0] >= 0 or cKDTree(P * 1000.0).query(p)[0] <= 2000.0
    if near:
        cand_nodes.append(n["id"])
cand_nodes.sort()
origins_nodes, kept = [], []
for nidn in cand_nodes:
    p = nxy[nid[nidn]]
    if all(math.hypot(p[0] - q[0], p[1] - q[1]) >= 750.0 for q in kept):
        kept.append(p); origins_nodes.append(nidn)
print("origins", len(origins_nodes))
# shelters
pt = pq.read_table(PLACES, columns=["names", "basic_category", "geometry"])
tree = cKDTree(nxy)
shel = []
for nm, cat, gm in zip(pt.column("names").to_pylist(), pt.column("basic_category").to_pylist(), pt.column("geometry").to_pylist()):
    if not cat or not any(k in cat for k in ("school", "hospital", "place_of_worship", "community", "shelter")):
        continue
    p = shapely.from_wkb(gm)
    x, y = TO_UTM.transform(p.x, p.y)
    d, j = tree.query([x, y])
    if d > 500.0:
        continue
    c = int((y - Y0) // RES) * W + int((x - X0) // RES)
    if not (0 <= c < Agrid.size) or np.isfinite(A[c]):   # outside the field's reached area
        continue
    shel.append({"id": "pl:%d" % len(shel), "name": (nm or {}).get("primary") or "", "category": cat, "xy": (x, y), "entry_node_id": nodes[j]["id"], "d": d})
by_entry = {}
for s in shel:
    by_entry.setdefault(s["entry_node_id"], s)
shel = sorted(by_entry.values(), key=lambda s: s["id"])
print("shelters (distinct entry nodes)", len(shel))
if len(shel) < 3 or len(origins_nodes) < 5:
    raise SystemExit("too few origins/shelters; stop")
wait_nodes = set(origins_nodes) | {s["entry_node_id"] for s in shel}
for n in nodes:
    n["waitable"] = n["id"] in wait_nodes
road = regiondata.RoadModel(raw)


def hav_xy(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


class Reg: pass
region = Reg(); region.road = road; region.origins = []; region.cands = {}
shelter_recs = [{"id": s["id"], "name": s["name"], "entry_node_id": s["entry_node_id"], "node": road.nidx[s["entry_node_id"]], "xy": s["xy"]} for s in shel]
for on in origins_nodes:
    i = road.nidx[on]
    lon, lat = TO_LL.transform(*road.node_xy[i])
    rec = {"id": on, "name": on, "category": "origin", "vulnerable": False, "lonlat": (lon, lat), "entry_node_id": on, "checkable": True, "node": i,
           "sigungu": "", "eupmyeon": "", "town_method": "", "xy": road.node_xy[i]}
    region.origins.append(rec)
    cand, seen = [], set()
    for s in sorted([s for s in shelter_recs if s["entry_node_id"] != on], key=lambda s: (hav_xy(rec["xy"], s["xy"]), s["id"])):
        if s["entry_node_id"] in seen:
            continue
        seen.add(s["entry_node_id"]); cand.append(s)
        if len(cand) >= 3:
            break
    region.cands[on] = cand
cfg = rl_settings.load()
cfg["routing"]["dwell_s"] = 120
dwell = cfg["routing"]["dwell_s"]


class Fire: pass
fire = Fire(); fire.horizon_s = H; fire.uncovered_set = set()

# ------------------------------------------------------------------ run per issue time
summary = {"label": "Model output on a reconstruction of the Camp Fire progression. Not what happened to people.", "protocol": "PROTOCOL.md amendments 9-11",
           "field": {"observations_unique_locations": int(len(T)), "smoothing": SMOOTH, "cells_reached": int(reached.sum()), "cells": int(reached.size), "LOO": loo_stats},
           "graph": {"nodes": len(nodes), "edges": len(raw["edges"]), "grid": g, "revision": raw["revision"]},
           "origins": len(origins_nodes), "shelters": len(shel), "issues": {}}
for lab, tmin in ISSUES.items():
    close_s = {}
    for c in road.road_cells:
        a = A[c]
        if not np.isfinite(a):
            continue
        s = math.ceil((a - tmin) * 60.0)
        if s <= 0:
            close_s[c] = 0
        elif s <= H:
            close_s[c] = s
    inst = engine.build_instance(road, close_s, H)
    from collections import defaultdict
    jobs_by = defaultdict(set)
    for o in region.origins:
        for s in region.cands.get(o["id"], []):
            jobs_by[s["node"]].add(o["node"])
    jobs = [(sn, engine.accept(road, close_s, sn, H, dwell), [(on, engine.origin_closure(road, close_s, on, H)) for on in sorted(ons)]) for sn, ons in sorted(jobs_by.items())]
    results = engine.run_passes(road, inst, jobs, WORKERS)
    rows = engine.assemble(region, fire, cfg, inst, results, close_s)
    out_rows, st = [], {"CUT_AT_ISSUE": 0, "CUT_WITHIN_H": 0, "NOT_CUT": 0, "REFUSED": 0}
    for r in rows:
        o = r["origin"]
        if r["refusal"]:
            st["REFUSED"] += 1
            out_rows.append({"origin": o["id"], "lon": round(o["lonlat"][0], 5), "lat": round(o["lonlat"][1], 5), "state": "REFUSED:" + r["refusal"][0]})
            continue
        cut, Aa = r["cut"], r["A"]
        state = "CUT_AT_ISSUE" if cut == 0 else ("NOT_CUT" if cut is None else "CUT_WITHIN_H")
        st[state] += 1
        out_rows.append({"origin": o["id"], "lon": round(o["lonlat"][0], 5), "lat": round(o["lonlat"][1], 5), "state": state, "cut_s": cut if cut is not None else "",
                         "fire_arrival_at_origin_s": Aa if Aa is not None else "", "latest_departure_s": r["L"] if r["L"] is not None else "",
                         "gap_arrival_minus_cut_s": r["gap"] if r["gap"] is not None else ""})
    with open(OUT / f"origins_{lab.replace(':', '')}.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, sorted({k for r in out_rows for k in r}, key=lambda k: list(out_rows[0]).index(k) if k in out_rows[0] else 99)); w.writeheader(); w.writerows(out_rows)
    gaps = [r["gap_arrival_minus_cut_s"] / 60.0 for r in out_rows if r.get("gap_arrival_minus_cut_s") not in ("", None)]
    summary["issues"][lab] = {"issue_min_after_midnight_PST": tmin, "road_cells_closed_within_horizon": len(close_s), "states": st,
                              "exact_gap_min": {"n": len(gaps), "median": float(np.median(gaps)) if gaps else None, "min": float(min(gaps)) if gaps else None, "max": float(max(gaps)) if gaps else None}}
    print(lab, st, "exact gaps", len(gaps), "closed cells", len(close_s), flush=True)

# ------------------------------------------------------------------ comparison with the records (frozen)
def cell_rect_dist(px, py, c):
    r, cc = divmod(c, W)
    x0, y0 = X0 + cc * RES, Y0 + r * RES
    dx = max(x0 - px, 0, px - (x0 + RES)); dy = max(y0 - py, 0, py - (y0 + RES))
    return math.hypot(dx, dy)


def model_arrival(px, py):
    best = None
    c0 = int((py - Y0) // RES) * W + int((px - X0) // RES)
    r0, cc0 = divmod(c0, W)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            r, cc = r0 + dr, cc0 + dc
            if 0 <= r < Hh and 0 <= cc < W:
                c = r * W + cc
                if cell_rect_dist(px, py, c) <= 150.0 and np.isfinite(A[c]) and c in set(road.road_cells):
                    best = A[c] if best is None else min(best, A[c])
    return best


recs = []
for r in csv.DictReader(open(GEO / "geocoded_burnovers.csv", encoding="utf-8-sig")):
    if r["rule"] != "NOT GEOCODED":
        t = r["time"]; day = 1440 if r["flag"] == "b" else 0
        recs.append({"kind": "burnover", "id": "BO%s" % r["id"], "place": r["place"][:50], "record_min": day + int(t[:2]) * 60 + int(t[3:5]), "x": float(r["x"]), "y": float(r["y"]), "flag": r["flag"]})
for r in csv.DictReader(open(GEO / "geocoded_closures.csv", encoding="utf-8-sig")):
    if r["closure_match"] == "True" and r["rule"] != "NOT GEOCODED":
        recs.append({"kind": "closure", "id": "CL-%s-%s" % (r["road"], r["start"]), "place": r["text"][:60], "record_min": minutes("11/8", r["start"]), "x": float(r["x"]), "y": float(r["y"]), "flag": ""})
cmp_rows = []
for r in recs:
    m = model_arrival(r["x"], r["y"])
    cmp_rows.append(dict(r, model_arrival_min="" if m is None else round(float(m), 1), error_min="" if m is None else round(float(m) - r["record_min"], 1), status="MISS: cell not reached by the field" if m is None else "ok"))
with open(OUT / "record_comparison.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, list(cmp_rows[0].keys())); w.writeheader(); w.writerows(cmp_rows)
errs = np.array([float(r["error_min"]) for r in cmp_rows if r["error_min"] != ""])
summary["records"] = {"n_geocoded": len(cmp_rows), "n_model_value": int(errs.size), "misses": int(len(cmp_rows) - errs.size),
                      "error_min_model_minus_record": {"median": float(np.median(errs)) if errs.size else None, "p25_p75": [float(np.percentile(errs, 25)), float(np.percentile(errs, 75))] if errs.size else None,
                                                       "within_30": int((np.abs(errs) <= 30).sum()), "within_60": int((np.abs(errs) <= 60).sum()), "min": float(errs.min()) if errs.size else None, "max": float(errs.max()) if errs.size else None},
                      "by_kind": {k: int(sum(1 for r in cmp_rows if r["kind"] == k)) for k in ("burnover", "closure")}}
(OUT / "paradise_summary.json").write_text(json.dumps(summary, indent=1))
print(json.dumps(summary["records"]))
