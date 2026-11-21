"""Step 1 (PROTOCOL §2.2): burn-out time from the Camp Fire workbook, per road cell.
Usage: python3 -I estimate_tau.py GRAPH.json OUT_DIR
E_c = first FIRE_ARRIVAL or ROAD_CLOSED time in road cell c; g_block = last ROAD_CLOSED - E_c; g_open = first
ROAD_PASSABLE or vehicle-present (location_source contains AVL) time u > E_c, - E_c; g_open_after_block = first such u
after the last ROAD_CLOSED, - E_c. Frozen choice: tau = 80th percentile of g_block over cells with g_block > 0,
rounded up to 15 min; low = median, high = 95th percentile (same set, same rounding); floor 15 min."""
import json, math, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "kcf-camp"))
from model import HERE as CAMP, TO_UTM, Graph, hhmm, minutes, read_csv, write_csv  # noqa: E402

G = Graph(sys.argv[1])
OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
cls = {r["obs_id"]: r["class_final"] for r in read_csv(CAMP / "data/classes_final.csv")}
rows = []
for r in read_csv(CAMP / "data/observations_dedup.csv"):
    if ":" not in r["time"]:
        continue
    x, y = TO_UTM.transform(float(r["lon"]), float(r["lat"]))
    c, how = G.match(x, y)
    rows.append({"id": r["obs_id"], "cls": cls[r["obs_id"]], "t": minutes(r["day"], r["time"]), "cell": c,
                 "veh": "AVL" in r["location_source"], "day": r["day"]})
placed = [r for r in rows if r["cell"] is not None]


def up15(v):
    return max(15, int(math.ceil(v / 15.0)) * 15)


cells = {}
for r in placed:
    cells.setdefault(r["cell"], []).append(r)
per = []
for c, rs in cells.items():
    fire = [r["t"] for r in rs if r["cls"] in ("FIRE_ARRIVAL", "ROAD_CLOSED")]
    if not fire:
        continue
    E = min(fire)
    blk = [r["t"] for r in rs if r["cls"] == "ROAD_CLOSED"]
    opn = sorted(r["t"] for r in rs if r["cls"] == "ROAD_PASSABLE" or r["veh"])
    lb = max(blk) if blk else None
    o1 = next((u for u in opn if u > E), None)
    o2 = next((u for u in opn if lb is not None and u > lb), None)
    per.append({"cell": c, "E": hhmm(E), "n_fire_evidence": len(fire), "n_blocked": len(blk), "n_open_evidence": len(opn),
                "n_vehicle": sum(r["veh"] for r in rs), "n_passable": sum(r["cls"] == "ROAD_PASSABLE" for r in rs),
                "g_block_min": round(lb - E, 1) if blk else "", "g_open_min": round(o1 - E, 1) if o1 is not None else "",
                "g_open_after_block_min": round(o2 - E, 1) if o2 is not None else "", "day_E": "11-08" if E < 1440 else "11-09"})
per.sort(key=lambda r: r["cell"])
write_csv(OUT / "tau_per_cell.csv", per)


def dist(v):
    v = np.array(sorted(v), float)
    if not len(v):
        return {"n": 0}
    q = lambda p: round(float(np.percentile(v, p)), 1)
    return {"n": len(v), "min": round(float(v.min()), 1), "p10": q(10), "p25": q(25), "median": q(50), "p75": q(75),
            "p80": q(80), "p90": q(90), "p95": q(95), "max": round(float(v.max()), 1)}


gb = [r["g_block_min"] for r in per if r["g_block_min"] != ""]
gbp = [g for g in gb if g > 0]
go = [r["g_open_min"] for r in per if r["g_open_min"] != ""]
goab = [r["g_open_after_block_min"] for r in per if r["g_open_after_block_min"] != ""]
res = {"rows_timed": len(rows), "rows_placed": len(placed), "vehicle_present_rows": sum(r["veh"] for r in rows),
       "vehicle_present_rows_placed": sum(r["veh"] for r in placed), "road_cells_with_fire_evidence": len(per),
       "g_block_all": dist(gb), "g_block_positive": dist(gbp), "g_open": dist(go),
       "g_open_passable_only": dist([r["g_open_min"] for r in per if r["g_open_min"] != "" and r["n_passable"]]),
       "g_open_after_block": dist(goab),
       "bracketed_cells": [{"cell": r["cell"], "lo_min": r["g_block_min"], "hi_min": r["g_open_after_block_min"]} for r in per
                           if r["g_block_min"] != "" and r["g_open_after_block_min"] != ""],
       "by_day": {d: {"g_block_positive": dist([r["g_block_min"] for r in per if r["day_E"] == d and r["g_block_min"] != "" and r["g_block_min"] > 0]),
                      "g_open": dist([r["g_open_min"] for r in per if r["day_E"] == d and r["g_open_min"] != ""])} for d in ("11-08", "11-09")}}
if len(gbp) >= 10:
    res["frozen"] = {"tau_min": up15(np.percentile(gbp, 80)), "tau_low_min": up15(np.percentile(gbp, 50)),
                     "tau_high_min": up15(np.percentile(gbp, 95)), "rule": "PROTOCOL 2.2 percentiles of g_block > 0", "n": len(gbp)}
else:
    res["frozen"] = {"tau_min": 180, "tau_low_min": 60, "tau_high_min": 360, "rule": "PROTOCOL 2.2 fallback (fewer than 10 cells)", "n": len(gbp)}
# cross-fit halves (PROTOCOL 2.3): split at the median easting of cells with g_block > 0
xs = {r["cell"]: G.centre(r["cell"])[0] for r in per}
pos = [r for r in per if r["g_block_min"] != "" and r["g_block_min"] > 0]
xm = float(np.median([xs[r["cell"]] for r in pos]))
halves = {}
for name, f in (("west", lambda c: xs[c] < xm), ("east", lambda c: xs[c] >= xm)):
    v = [r["g_block_min"] for r in pos if f(r["cell"])]
    halves[name] = {"n": len(v), "tau_min": up15(np.percentile(v, 80)) if len(v) >= 10 else 180}
res["crossfit"] = {"split_easting_m": xm, "halves": halves}
(OUT / "tau.json").write_text(json.dumps(res, indent=1))
print(json.dumps({k: res[k] for k in ("g_block_positive", "g_open", "g_open_after_block", "frozen", "crossfit")}, indent=1))
