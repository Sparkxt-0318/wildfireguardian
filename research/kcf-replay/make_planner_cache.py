"""Write the replay as a planner cache (schema wfg.planner.cache/1) the demo can play with WFG_CACHE_DIR.

One file per region and issue hour for one (stand-in, horizon). Verdicts come from the F-3.1 deadline field with the
stand-in closures (HOTSPOT_RULE.md), NOT from the Route-Check API: api.mode = "kcf-replay-offline", the host is the
machine that ran the field (so the app marks it 시험 데이터 · 평가 호스트 아님), and every scenario id starts with
"kcf-replay:". Departure grid: every 30 min over the horizon.

Usage: python3 make_planner_cache.py out/runs OUT_DIR --standin RUNNING --horizon 8h
"""
from __future__ import annotations

import argparse, hashlib, json, platform, subprocess
from datetime import datetime, timezone
from pathlib import Path

from pyproj import Transformer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
H_S = {"5h": 18000, "8h": 28800}
STEP = 1800
DWELL = 120
TR = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)


def contains(S, t):
    return any(lo <= t <= hi for lo, hi in S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs"); ap.add_argument("out")
    ap.add_argument("--standin", default="RUNNING"); ap.add_argument("--horizon", default="8h")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    H = H_S[a.horizon]
    offsets = list(range(0, H - DWELL, STEP))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    host = {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()}
    now = datetime.now(timezone.utc).isoformat()
    graphs, places = {}, {}
    index = []
    for p in sorted(Path(a.runs).glob(f"*__{a.standin}__{a.horizon}__*.json")):
        job = json.loads(p.read_text())
        region, T = job["region"], job["issue_utc"]
        if region not in graphs:
            raw = json.loads((ROOT / f"data/routing/graphs/{region}/graph.json").read_text())
            graphs[region] = ({n["id"]: (n["x"], n["y"]) for n in raw["nodes"]}, {e["id"]: e for e in raw["edges"]})
            places[region] = {f["properties"]["id"]: f for f in json.loads(
                (ROOT / f"planner/public/data/regions/{region}/places.geojson").read_text())["features"]}
        nodes, edges = graphs[region]
        compact = T[:4] + T[5:7] + T[8:10] + "T" + T[11:13] + "0000Z"
        input_time = T[:19] + "Z"
        sset = f"kcf-replay:{a.standin}:{a.horizon}:{compact}"
        fire_input = {"type": "recorded", "scenario_set_id": sset}
        requests, plans, route_checks = [], [], {}
        for rank, r in enumerate(sorted(job["rows"], key=lambda r: (r["ld_s"] is not None, r["ld_s"] or 0)), 1):
            f = places[region][r["place_id"]]
            # the 3 candidate shelters, in the planner's order, with their F-3.1 departure sets
            from replay import planner_candidates  # same rule as planner/scripts/precompute.py
            o, near = CANDS[region][r["place_id"]]
            dests = [{"id": s["properties"]["id"], "location": {"node_id": s["properties"]["entry"]["node"]},
                      "dwell_s": DWELL, "window": [0, H]} for s in near]
            req = {"region": region, "input_time": input_time, "fire_input": fire_input,
                   "origins": [{"id": r["place_id"], "location": {"node_id": f["properties"]["entry"]["node"]}}],
                   "destinations": dests, "depart_offsets_s": offsets, "dwell_s": DWELL, "policy": "full",
                   "client_ref": f"kcf-replay:{region}:{compact}"}
            attempts = []
            best_rc = None
            for d in dests:
                S = r["sets_by_shelter_node"].get(d["location"]["node_id"], [])
                for off in offsets:
                    ok = contains(S, off)
                    rc_id = None
                    if ok and d["id"] == r.get("shelter_id") and off == max(x for x in offsets if contains(S, x)):
                        rc_id = f"kcf_{hashlib.sha1((sset + r['place_id']).encode()).hexdigest()[:20]}"
                    attempts.append({"destination_id": d["id"], "depart_offset_s": off,
                                     "verdict": "checked_route" if ok else "model_no_route",
                                     "reason_code": None if ok else "NO_ROUTE_BEFORE_CLOSURE",
                                     "arrival_s": None, "lower_bound_L_s": None, "compute_s": None,
                                     "route_check_job_id": rc_id})
                    if rc_id:
                        best_rc = (rc_id, d, off)
            checked = [x["depart_offset_s"] for x in attempts if x["verdict"] == "checked_route"]
            contiguous = None
            for off in offsets:
                if off in checked:
                    contiguous = off
                else:
                    break
            snap = {"node_id": f["properties"]["entry"]["node"], "distance_m": 0.0,
                    "lon": f["properties"]["entry"]["lon"], "lat": f["properties"]["entry"]["lat"], "input": "node_id"}
            best = None
            if best_rc and r.get("route_edges"):
                rc_id, d, off = best_rc
                ids = [edges[e]["u"] for e in r["route_edges"]] + [edges[r["route_edges"][-1]]["v"]]
                coords = [list(TR.transform(*nodes[n])) for n in ids]
                t, times = off, [off]
                for e in r["route_edges"]:
                    t += edges[e]["travel_ticks"]; times.append(t)
                route_checks[rc_id] = {
                    "job_id": rc_id, "kind": "route_check", "status": "done", "created_at": now, "started_at": now, "finished_at": now,
                    "request": {"region": region, "input_time": input_time, "start": {"node_id": snap["node_id"]},
                                "destination": d["location"], "depart_offset_s": off, "dwell_s": DWELL,
                                "destination_window": [0, H], "policy": "full", "fire_input": fire_input},
                    "snap": {"start": snap, "destination": {"node_id": d["location"]["node_id"], "distance_m": 0.0,
                                                            "lon": coords[-1][0], "lat": coords[-1][1], "input": "node_id"}},
                    "result": {"verdict": "checked_route", "reason_code": None, "raw_status": "KCF_REPLAY_F31_FIELD_WITNESS",
                               "raw_reason": None, "departure_s": off, "arrival_s": t, "lower_bound_L_s": None,
                               "lower_bounds": [], "dwell_end_s": t + DWELL,
                               "route": {"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
                                         "properties": {"times_s": times, "node_ids": ids, "segment_count": len(ids) - 1,
                                                        "edge_ids": r["route_edges"], "waits": [], "legs_total": len(ids) - 1}},
                               "exposure": [], "compute_s": None, "within_budget": True, "policy": "full", "limits": None,
                               "independent_check": None, "assumptions": None,
                               "notes": ["kcf-replay: witness from the F-3.1 deadline field with stand-in road-cell closures; "
                                         "not a Route-Check API result"],
                               "provenance": {"host": host, "fire_input_type": "kcf-replay", "evaluated_configuration": False}},
                    "error": None}
                best = {"destination_id": d["id"], "depart_offset_s": off, "verdict": "checked_route", "reason_code": None,
                        "arrival_s": t, "lower_bound_L_s": None, "compute_s": None, "route_check_job_id": rc_id}
            plan = {"origin_id": r["place_id"], "urgency_rank": rank, "snap": snap,
                    "best_verdict": "checked_route" if checked else "model_no_route",
                    "latest_checked_depart_offset_s": max(checked) if checked else None,
                    "latest_contiguous_checked_depart_offset_s": contiguous, "best": best, "attempts": attempts}
            requests.append(req)
            plans.append({"job_id": f"kcfdp_{hashlib.sha1((sset + r['place_id']).encode()).hexdigest()[:20]}",
                          "kind": "dispatch_plan", "status": "done", "created_at": now, "started_at": now, "finished_at": now,
                          "request": req, "progress": {"done": len(attempts), "total": len(attempts)},
                          "result": {"plans": [plan], "summary": {"origins": 1, "attempts": len(attempts)},
                                     "rejected_origins": [], "assumptions": None,
                                     "provenance": {"host": host, "region": region, "input_time": input_time,
                                                    "scenario_set_id": sset, "fire_input_type": "kcf-replay",
                                                    "evaluated_configuration": False}},
                          "error": None})
        doc = {"schema": "wfg.planner.cache/1", "region_id": region, "scenario_set_id": sset, "input_time": input_time,
               "fire_input": fire_input, "created_at": now,
               "api": {"base": "none: offline F-3.1 deadline field (research/kcf-replay)", "mode": "kcf-replay-offline",
                       "health": None, "host": host},
               "planner_commit": commit,
               "generator": {"script": "research/kcf-replay/make_planner_cache.py", "purpose": "kcf-replay",
                             "rule": "research/kcf-replay/HOTSPOT_RULE.md", "standin": a.standin, "horizon": a.horizon,
                             "step_min": STEP // 60, "shelters_per_origin": 3, "default_dwell_s": DWELL,
                             "note": "what the screen would have shown at this issue hour; not a Route-Check API result"},
               "requests": requests, "plans": plans, "research_checks": [], "rejected_requests": [],
               "route_checks": route_checks, "travel_only": {}}
        rel = f"{region}/{a.standin}_{a.horizon}_{compact}.json"
        (out / region).mkdir(exist_ok=True)
        b = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode()
        (out / rel).write_bytes(b)
        index.append({"region_id": region, "scenario_set_id": sset, "input_time": input_time, "path": rel,
                      "api_mode": "kcf-replay-offline", "purpose": "kcf-replay", "api_version": None, "host": host,
                      "created_at": now, "origins": len(requests), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()})
    (out / "INDEX.json").write_text(json.dumps(sorted(index, key=lambda e: (e["region_id"], e["input_time"])), indent=1))
    print(len(index), "files", sum(e["bytes"] for e in index) // 1024, "KiB")


CANDS = {}
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(HERE))
    from replay import planner_candidates
    for region in ("yeongdeok_2025", "uiseong_andong_2025"):
        CANDS[region] = planner_candidates(json.loads(
            (ROOT / f"planner/public/data/regions/{region}/places.geojson").read_text())["features"])
    main()
