"""Post-process the replay runs: per-place CSV, frozen score (HOTSPOT_RULE.md), independent witness re-check.

Usage: python3 analyze.py out/fire_discs.json out/runs OUT_DIR
"""
from __future__ import annotations

import csv, json, math, sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KST = timezone(timedelta(hours=9))
HORIZON_S = {"5h": 18000, "8h": 28800}
DWELL = 120


def kst(dt):
    return dt.astimezone(KST).strftime("%m-%d %H:%M")


def load_graph(region):
    raw = json.loads((ROOT / f"data/routing/graphs/{region}/graph.json").read_text())
    g = raw["grid"]
    edges = {e["id"]: e for e in raw["edges"]}
    nodes = {n["id"]: (n["x"], n["y"]) for n in raw["nodes"]}
    return raw, g, edges, nodes


def cell_centres(g):
    W, H = g["width"], g["height"]
    c = np.arange(W * H)
    r, col = np.divmod(c, W)
    return g["x0"] + (col + 0.5) * g["resolution"], g["y0"] + (r + 0.5) * g["resolution"]


def first_cut_times(discs, cx, cy):
    """Per cell: earliest disc time with the cell centre inside the disc (distance 0) = reconstructed fire cut."""
    out = np.full(cx.shape, np.inf)
    t = np.array([d["ts"] for d in discs])
    X = np.array([d["x"] for d in discs]); Y = np.array([d["y"] for d in discs]); Rr = np.array([d["r_m"] for d in discs])
    for i in range(0, len(discs), 1500):
        inside = np.hypot(cx[:, None] - X[None, i:i + 1500], cy[:, None] - Y[None, i:i + 1500]) <= Rr[None, i:i + 1500]
        tt = np.where(inside, t[None, i:i + 1500], np.inf).min(1)
        out = np.minimum(out, tt)
    return out


def recheck(route_edges, edges, close_s, ld, arrival, shelter_cell, H):
    """Independent replay of a witness: departing at ld, every edge segment must be left strictly before its cell
    closes ([t + D*z_a, t + D*z_b] must not meet [b, inf)), and the dwell [arr, arr+DWELL] before the shelter cell
    closes, and arr + DWELL <= H. Returns (ok, arrival)."""
    t = ld
    for eid in route_edges:
        e = edges[eid]
        D = e["travel_ticks"]
        for s in e["segments"]:
            b = close_s.get(str(s["cell"]))
            if b is not None and t + D * s["end"] >= b:
                return False, None
        t += D
    b = close_s.get(str(shelter_cell))
    if b is not None and t + DWELL >= b:
        return False, t
    return (t + DWELL <= H), t


def main(discs_path, runs_dir, out_dir):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    discs = json.loads(Path(discs_path).read_text())
    for d in discs["discs"]:
        d["ts"] = datetime.fromisoformat(d["t_utc"]).timestamp()
    places = {}
    for region in ("yeongdeok_2025", "uiseong_andong_2025"):
        for f in json.loads((ROOT / f"planner/public/data/regions/{region}/places.geojson").read_text())["features"]:
            places[f["properties"]["id"]] = f
    graphs = {r: load_graph(r) for r in ("yeongdeok_2025", "uiseong_andong_2025")}
    cut = {}
    for r, (raw, g, edges, nodes) in graphs.items():
        cx, cy = cell_centres(g)
        cut[r] = first_cut_times(discs["discs"], cx, cy)
    rows, score = [], defaultdict(Counter)
    recheck_stats = Counter()
    for p in sorted(Path(runs_dir).glob("*.json")):
        job = json.loads(p.read_text())
        region, standin, hz = job["region"], job["standin"], job["horizon"]
        raw, g, edges, nodes = graphs[region]
        T = datetime.fromisoformat(job["issue_utc"])
        H = HORIZON_S[hz]
        for r in job["rows"]:
            f = places[r["place_id"]]; pr = f["properties"]
            ld = r.get("ld_s")
            inside = r["dist_known_fire_m"] == 0.0
            if ld is None:
                state = "INSIDE_KNOWN_FIRE_AREA" if inside else "NO_SAFE_DEPARTURE"
            elif r["cut_within_H"]:
                state = "LATEST_SAFE_DEPARTURE"
            else:
                state = "NOT_CUT_WITHIN_H"
            row = {"region": region, "place_id": r["place_id"], "name": pr.get("name") or "", "category": pr["category"],
                   "vulnerable": bool(pr.get("vulnerable")), "sigungu": (pr.get("sigungu") or {}).get("ko", ""),
                   "lon": round(f["geometry"]["coordinates"][0], 5), "lat": round(f["geometry"]["coordinates"][1], 5),
                   "issue_kst": kst(T), "standin": standin, "horizon": hz,
                   "dist_known_fire_km": "" if r["dist_known_fire_m"] is None else round(r["dist_known_fire_m"] / 1000, 2),
                   "government_step": r["step"], "departure_state": state,
                   "latest_safe_departure_kst": kst(T + timedelta(seconds=ld)) if state == "LATEST_SAFE_DEPARTURE" else "",
                   "last_departure_in_horizon_kst": kst(T + timedelta(seconds=ld)) if ld is not None else "",
                   "departure_set_pieces": r.get("pieces") or "",
                   "shelter_id": r.get("shelter_id") or "", "shelter_name": r.get("shelter_name") or "",
                   "arrival_kst": kst(T + timedelta(seconds=r["arrival_s"])) if r.get("arrival_s") is not None else "",
                   "route_osm_ways": " ".join(dict.fromkeys(str(edges[e]["source_way"]) for e in r.get("route_edges", []))),
                   "route_first_cut_by_reconstruction_kst": "", "route_cut_before_departure": ""}
            if ld is not None:
                shelter_node = next((s for s in r["sets_by_shelter_node"] if True), None)
                sh = places.get(r["shelter_id"])
                sxy = nodes[sh["properties"]["entry"]["node"]]
                scell = int((sxy[1] - g["y0"]) // g["resolution"]) * g["width"] + int((sxy[0] - g["x0"]) // g["resolution"])
                ok, arr = recheck(r["route_edges"], edges, job["close_s"], ld, r["arrival_s"], scell, H)
                recheck_stats["ok" if ok and arr == r["arrival_s"] else "FAIL"] += 1
                cells = r.get("route_cells", [])
                fc = min((cut[region][c] for c in cells), default=np.inf)
                if np.isfinite(fc):
                    row["route_first_cut_by_reconstruction_kst"] = kst(datetime.fromtimestamp(fc, timezone.utc))
                if state == "LATEST_SAFE_DEPARTURE":
                    earlier = fc < (T + timedelta(seconds=ld)).timestamp()
                    row["route_cut_before_departure"] = "yes" if earlier else "no"
                    key = (standin, hz)
                    score[key]["rows_with_latest_safe_departure"] += 1
                    score[key]["route_cut_earlier_by_reconstruction"] += int(earlier)
                    score[key + ("places",)][r["place_id"] + ("|cut" if earlier else "|ok")] = 1
            rows.append(row)
    rows.sort(key=lambda x: (x["standin"], x["horizon"], x["region"], x["place_id"], x["issue_kst"]))
    with open(out / "per_place.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    summ = {}
    for (k, v) in score.items():
        if len(k) == 2:
            pl = score[k + ("places",)]
            ids = {x.split("|")[0] for x in pl}
            cut_ids = {x.split("|")[0] for x in pl if x.endswith("|cut")}
            summ[f"{k[0]}/{k[1]}"] = dict(v, places_with_latest_safe_departure=len(ids), places_with_any_earlier_cut=len(cut_ids))
    steps = defaultdict(Counter)
    for x in rows:
        steps[(x["standin"], x["horizon"], x["issue_kst"])][x["government_step"]] += 1
    res = {"score": summ, "witness_recheck": dict(recheck_stats), "rows": len(rows),
           "steps_by_issue": {"/".join(k): dict(v) for k, v in sorted(steps.items()) if k[1] == "8h"}}
    (out / "score.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res["score"], indent=1), res["witness_recheck"])


if __name__ == "__main__":
    main(*sys.argv[1:4])
