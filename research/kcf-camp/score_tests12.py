"""Tests 1 and 2 (PROTOCOL §4-§6). Usage: python3 -I score_tests12.py GRAPH.json OUT_DIR
Reads data/observations_dedup.csv, data/classes_final.csv, data/burnovers_tn2252.csv."""
import json, math, sys
from pathlib import Path

import numpy as np

from model import (HERE, HOLD_M, HOLD_MIN, TOL_MIN, TO_UTM, VARIANTS, Field, Graph, boot_median, hhmm, minutes, read_csv,
                   verdict, wilson, write_csv)

G = Graph(sys.argv[1])
OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
obs = {r["obs_id"]: r for r in read_csv(HERE / "data/observations_dedup.csv")}
cls = {r["obs_id"]: r["class_final"] for r in read_csv(HERE / "data/classes_final.csv")}
for k, r in obs.items():
    r["cls"] = cls[k]
    r["t"] = minutes(r["day"], r["time"])
    r["x"], r["y"] = TO_UTM.transform(float(r["lon"]), float(r["lat"]))
fire = [r for r in obs.values() if r["cls"] == "FIRE_ARRIVAL"]
road = [r for r in obs.values() if r["cls"].startswith("ROAD_")]
scored = [r for r in road if r["cls"] in ("ROAD_CLOSED", "ROAD_PASSABLE")]
counts = {"unique_observations": len(obs), "by_class": {c: sum(1 for r in obs.values() if r["cls"] == c) for c in sorted(set(cls.values()))}}

# ------------------------------------------------------------------ Test 1
fx = np.array([[r["x"], r["y"], r["t"]] for r in fire])
sx = np.array([[r["x"], r["y"], r["t"]] for r in scored])
near = np.zeros(len(fire), bool)
for x, y, t in sx:
    near |= (np.hypot(fx[:, 0] - x, fx[:, 1] - y) <= HOLD_M) & (np.abs(fx[:, 2] - t) <= HOLD_MIN)
dupkey = {(r["day"], r["time"], r["lat"], r["lon"], r["text"].lower()) for r in road}
leak_drop = np.array([(r["day"], r["time"], r["lat"], r["lon"], r["text"].lower()) in dupkey for r in fire])
inputs = {"strict": [(r["x"], r["y"], r["t"]) for r, d in zip(fire, near) if not d],
          "leaky": [(r["x"], r["y"], r["t"]) for r, d in zip(fire, leak_drop) if not d]}
fields = {k: Field(G, v) for k, v in inputs.items()}
counts["test1_input"] = {"fire_arrival_rows": len(fire), "removed_strict_500m_60min": int(near.sum()), "kept_strict": len(inputs["strict"]),
                         "removed_leaky_exact_duplicates": int(leak_drop.sum()), "kept_leaky": len(inputs["leaky"]),
                         "observed_cells_strict": len(fields["strict"].cells), "observed_cells_leaky": len(fields["leaky"].cells)}
rows1, placed = [], []
for r in sorted(road, key=lambda r: (r["t"], r["obs_id"])):
    c, how = G.match(r["x"], r["y"])
    row = {"obs_id": r["obs_id"], "class": r["cls"], "day": r["day"], "time": r["time"], "window_min": r["window_min"], "lat": r["lat"], "lon": r["lon"],
           "cell": c if c is not None else "", "match": how, "text": r["text"]}
    for inp, F in fields.items():
        for v in VARIANTS:
            C = F.closure(c, v) if c is not None else math.nan
            row["C_%s_%s" % (v, inp)] = hhmm(C) if c is not None else ""
            row["err_%s_%s" % (v, inp)] = round(C - r["t"], 1) if c is not None and math.isfinite(C) else ""
            if c is None:
                st = ""
            elif r["cls"] == "ROAD_CLOSED":
                st = "HIT" if C <= r["t"] + TOL_MIN else "MISS"
            elif r["cls"] == "ROAD_PASSABLE":
                st = "FALSE_CLOSURE" if C <= r["t"] - TOL_MIN else "OK_OPEN"
            else:
                st = "closed" if C <= r["t"] else "open"
            row["state_%s_%s" % (v, inp)] = st
    rows1.append(row)
write_csv(OUT / "test1_road_state.csv", rows1)


def summarise1(rows, inp):
    out = {}
    for v in VARIANTS:
        k = "state_%s_%s" % (v, inp)
        cl = [r for r in rows if r["class"] == "ROAD_CLOSED" and r[k]]
        pa = [r for r in rows if r["class"] == "ROAD_PASSABLE" and r[k]]
        bo = [r for r in rows if r["class"] == "ROAD_BLOCKED_OTHER" and r[k]]
        hits = sum(r[k] == "HIT" for r in cl)
        fc = sum(r[k] == "FALSE_CLOSURE" for r in pa)
        errs = [float(r["err_%s_%s" % (v, inp)]) for r in cl if r["err_%s_%s" % (v, inp)] != ""]
        hit_ci, fc_ci = wilson(hits, len(cl)), wilson(fc, len(pa))
        vh = verdict(hit_ci, 0.80, True, len(cl)); vf = verdict(fc_ci, 0.20, False, len(pa))
        out[v] = {"closed_scored": len(cl), "hits": hits, "misses": len(cl) - hits, "hit_rate": round(hits / len(cl), 3) if cl else None, "hit_ci95": hit_ci,
                  "misses_no_closure_at_all": sum(1 for r in cl if r["err_%s_%s" % (v, inp)] == ""),
                  "passable_scored": len(pa), "false_closures": fc, "false_closure_rate": round(fc / len(pa), 3) if pa else None, "false_closure_ci95": fc_ci,
                  "time_error_min_closed_rows": boot_median(errs), "blocked_other_scored": len(bo), "blocked_other_model_closed": sum(r[k] == "closed" for r in bo),
                  "verdict_hits": vh, "verdict_false_closures": vf,
                  "verdict": "FAIL" if "FAIL" in (vh, vf) else ("PASS" if (vh, vf) == ("PASS", "PASS") else "INCONCLUSIVE")}
    return out


res = {"counts": counts, "test1": {}}
nplaced = {c: sum(1 for r in rows1 if r["class"] == c and r["cell"] != "") for c in ("ROAD_CLOSED", "ROAD_PASSABLE", "ROAD_BLOCKED_OTHER")}
res["test1"]["placed"] = nplaced
res["test1"]["not_placed"] = {c: sum(1 for r in rows1 if r["class"] == c and r["cell"] == "") for c in nplaced}
for inp in fields:
    res["test1"][inp] = summarise1(rows1, inp)
    for day in ("11-08", "11-09"):
        res["test1"]["%s_%s" % (inp, day)] = summarise1([r for r in rows1 if r["day"] == day], inp)

# ------------------------------------------------------------------ Test 2
pts_by_name = {}
for e in G.raw["edges"]:
    if e["name"]:
        for a, b in zip(e["geom"][:-1], e["geom"][1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1]); n = max(1, int(L // 25))
            for k in range(n + 1):
                pts_by_name.setdefault(e["name"], []).append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
for k in pts_by_name:
    pts_by_name[k] = np.unique(np.round(np.array(pts_by_name[k]), 1), axis=0)


def junction(n1, n2):
    A, B = pts_by_name.get(n1), pts_by_name.get(n2)
    if A is None or B is None:
        return None, "road name not on graph: %s" % (n1 if A is None else n2)
    from scipy.spatial import cKDTree
    d, j = cKDTree(B).query(A)
    i = int(np.argmin(d))
    if d[i] > 60:
        return None, "%s and %s do not meet on the graph (closest %.0f m)" % (n1, n2, d[i])
    return A[i], "junction %s / %s" % (n1, n2)


bos = read_csv(HERE / "data/burnovers_tn2252.csv")
st37 = [r for r in obs.values() if "station 37" in r["text"].lower() and r["day"] == "11-08"]
rows2 = []
for b in bos:
    name = b["loc_road"]; P = pts_by_name.get(name)
    L = float(b["length_affected_m"]) if b["length_affected_m"] else None
    rad = L / 2 if L else 400.0
    sel, note = None, ""
    if P is None:
        note = "road name not on graph: %s" % name
    elif b["loc_method"] in ("point", "obs_point", "road_centroid", "junction"):
        if b["loc_method"] == "point":
            cxy = TO_UTM.transform(float(b["loc_lon"]), float(b["loc_lat"])); note = "point from source"
        elif b["loc_method"] == "obs_point":
            r0 = min(st37, key=lambda r: r["t"]); cxy = (r0["x"], r0["y"]); note = "workbook %s ('%s')" % (r0["obs_id"], r0["text"][:40])
        elif b["loc_method"] == "road_centroid":
            m = P.mean(0); cxy = tuple(P[int(np.argmin(np.hypot(P[:, 0] - m[0], P[:, 1] - m[1])))]); note = "road centroid"
        else:
            cxy, note = junction(name, b["loc_road2"])
        if cxy is not None:
            d0 = np.hypot(P[:, 0] - cxy[0], P[:, 1] - cxy[1])
            if d0.min() > 375:
                note += "; named road %.0f m from the point: not placed" % d0.min()
            else:
                sel = P[d0 <= max(rad, d0.min() + 1)]
    elif b["loc_method"] in ("between", "between_junctions"):
        if b["loc_method"] == "between":
            a = TO_UTM.transform(float(b["loc_lon"]), float(b["loc_lat"])); bb = TO_UTM.transform(-121.585289, 39.798183); note = "between TRA-N and TRA-S"
        else:
            r1, r2 = b["loc_road2"].split("|")
            a, n1 = junction(name, r1); bb, n2 = junction(name, r2); note = n1 + "; " + n2
        if a is not None and bb is not None:
            D = math.hypot(a[0] - bb[0], a[1] - bb[1])
            dd = np.hypot(P[:, 0] - a[0], P[:, 1] - a[1]) + np.hypot(P[:, 0] - bb[0], P[:, 1] - bb[1])
            sel = P[dd <= D + 200.0]
    if sel is None or not len(sel):
        rows2.append({"bo_id": b["bo_id"], "location": b["location"], "date": b["date"], "initiation": b["initiation"], "placed": "no", "loc_note": note})
        continue
    cells = sorted({G.cell(x, y) for x, y in sel} & G.road_set)
    t0 = minutes(b["date"][5:], b["initiation"])
    keep = np.ones(len(fire), bool)
    for x, y in sel[:: max(1, len(sel) // 200)]:
        keep &= ~((np.hypot(fx[:, 0] - x, fx[:, 1] - y) <= HOLD_M) & (np.abs(fx[:, 2] - t0) <= HOLD_MIN))
    F = Field(G, [(r["x"], r["y"], r["t"]) for r, k in zip(fire, keep) if k])
    row = {"bo_id": b["bo_id"], "location": b["location"], "date": b["date"], "initiation": b["initiation"], "first_obs_flag": b["first_obs_flag"],
           "placed": "yes", "loc_note": note, "n_cells": len(cells), "road_length_m": round(len(sel) * 25.0),
           "input_removed": int((~keep).sum())}
    for v in VARIANTS:
        C = min(F.closure(c, v) for c in cells)
        row["C_%s" % v] = hhmm(C)
        row["lead_min_%s" % v] = round(t0 - C, 1) if math.isfinite(C) else ""
        for lab, tau in (("t-60", t0 - 60), ("t-30", t0 - 30), ("t", t0)):
            row["%s_%s" % (v, lab)] = "CLOSED" if C <= tau else ("UNSAFE" if C <= tau + 30 else "OPEN")
    rows2.append(row)
write_csv(OUT / "test2_burnovers.csv", rows2, list(max(rows2, key=len).keys()))
placed2 = [r for r in rows2 if r["placed"] == "yes"]
res["test2"] = {"burnovers": len(rows2), "placed": len(placed2), "not_placed": [(r["bo_id"], r["loc_note"]) for r in rows2 if r["placed"] == "no"]}
for subset, rs in (("all", placed2), ("nov8", [r for r in placed2 if r["date"].endswith("11-08")]), ("nov9", [r for r in placed2 if r["date"].endswith("11-09")])):
    s = {}
    for v in VARIANTS:
        d = {}
        for lab in ("t-60", "t-30", "t"):
            k = sum(r["%s_%s" % (v, lab)] in ("CLOSED", "UNSAFE") for r in rs)
            d[lab] = {"closed": sum(r["%s_%s" % (v, lab)] == "CLOSED" for r in rs), "unsafe": sum(r["%s_%s" % (v, lab)] == "UNSAFE" for r in rs),
                      "closed_or_unsafe": k, "n": len(rs), "share": round(k / len(rs), 3) if rs else None, "ci95": wilson(k, len(rs))}
        d["verdict"] = verdict(d["t-30"]["ci95"], 0.80, True, len(rs))
        d["lead_min"] = boot_median([float(r["lead_min_%s" % v]) for r in rs if r["lead_min_%s" % v] != ""])
        s[v] = d
    res["test2"][subset] = s
(OUT / "tests12.json").write_text(json.dumps(res, indent=1))
print(json.dumps({"counts": counts, "t1_placed": nplaced, "t2_placed": res["test2"]["placed"]}, indent=1))
