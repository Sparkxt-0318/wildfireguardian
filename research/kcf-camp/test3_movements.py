"""Test 3 (PROTOCOL §6): the two documented movements through the unchanged deadline field.
Usage: python3 -I test3_movements.py GRAPH.json OUT_DIR
Closures at issue time T (seconds after T), input = FIRE_ARRIVAL observations before T (§4.3):
  M0 = cells already observed burning close at 0; M30 = M0 moved 30 min earlier (identical at T: floor 0);
  MR / MR_running = T + h(d) from the nearest observed cell (frozen R(h)), within the 2 h horizon."""
import heapq, json, math, sys
from pathlib import Path

import numpy as np

from model import HERE, R_ALL, R_RUN, TO_UTM, VARIANTS, Graph, closure_min, minutes, read_csv
from wfg_roadlayer import engine

G = Graph(sys.argv[1]); road = G.road
OUT = Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
H, DWELL = 7200, 120
obs = {r["obs_id"]: r for r in read_csv(HERE / "data/observations_dedup.csv")}
cls = {r["obs_id"]: r["class_final"] for r in read_csv(HERE / "data/classes_final.csv")}
fire = []
for k, r in obs.items():
    if cls[k] == "FIRE_ARRIVAL":
        x, y = TO_UTM.transform(float(r["lon"]), float(r["lat"]))
        fire.append((x, y, minutes(r["day"], r["time"])))
rc = [int(c) for c in road.road_cells]
rc_xy = np.array([G.centre(c) for c in rc])


def closures(T, variant):
    first = {}
    for x, y, t in fire:
        if t < T:
            c = G.cell(x, y)
            if c is not None and t < first.get(c, math.inf):
                first[c] = t
    if variant in ("M0", "M30"):
        return {c: 0 for c in first if c in G.road_set}
    R5, R8 = R_ALL if variant == "MR" else R_RUN
    oxy = np.array([G.centre(c) for c in first])
    out = {}
    for c, (x, y) in zip(rc, rc_xy):
        d = float(np.min(np.hypot(oxy[:, 0] - x, oxy[:, 1] - y)))
        m = closure_min(R5, R8, d)
        if m * 60 <= H:
            out[c] = int(math.ceil(m * 60))
    return out


def nearest_node(lat, lon):
    x, y = TO_UTM.transform(lon, lat)
    d = [math.hypot(a - x, b - y) for a, b in road.node_xy]
    i = int(np.argmin(d))
    return i, round(d[i])


name = {j: e["name"] for j, e in enumerate(G.raw["edges"])}
length = {j: e["length_m"] for j, e in enumerate(G.raw["edges"])}


def route_summary(edges, roads):
    tot = sum(length[j] for j in edges)
    on = sum(length[j] for j in edges if name[j] in roads)
    seq = []
    for j in edges:
        if not seq or seq[-1] != name[j]:
            seq.append(name[j] or "(unnamed)")
    return {"length_m": round(tot), "share_on_documented": round(on / tot, 3) if tot else None, "road_sequence": seq}


def fastest_fire_free(o, d):
    dist, heap, prev = {o: 0}, [(0, o)], {}
    while heap:
        t, v = heapq.heappop(heap)
        if v == d:
            break
        if t != dist[v]:
            continue
        for j in road.out_by_node.get(v, []):
            w, nt = road.head[j], t + road.D[j]
            if nt < dist.get(w, 1 << 60):
                dist[w] = nt; prev[w] = j; heapq.heappush(heap, (nt, w))
    path, v = [], d
    while v != o:
        j = prev[v]; path.append(j); v = road.tail[j]
    return dist[d], path[::-1]


mv = {m["movement"]: m for m in read_csv(HERE / "data/movements_tn2252.csv")}
cases = [("a", "12:00", ["Pearson Road", "Clark Road"]), ("b", "13:34", ["Skyway"]), ("b", "13:58", ["Skyway"])]
res = {"horizon_s": H, "dwell_s": DWELL, "cases": []}
for m, t, roads in cases:
    M = mv[m]
    o, od = nearest_node(float(M["origin_lat"]), float(M["origin_lon"]))
    dn, dd = nearest_node(float(M["dest_lat"]), float(M["dest_lon"]))
    T = minutes("11-08", t)
    ff_t, ff_path = fastest_fire_free(o, dn)
    case = {"movement": m, "issue": t, "documented_roads": roads, "origin_node_snap_m": od, "dest_node_snap_m": dd,
            "fire_free_fastest_s": ff_t, "fire_free_route": route_summary(ff_path, roads), "variants": {}}
    for v in VARIANTS:
        cs = closures(T, v)
        inst = engine.build_instance(road, cs, H)
        acc = engine.accept(road, cs, dn, H, DWELL)
        ib = engine.origin_closure(road, cs, o, H)
        args = {"H": inst.H, "n_nodes": inst.n_nodes, "tail": inst.tail, "head": inst.head, "D": inst.D, "waitable": inst.waitable,
                "forbidden": inst.forbidden, "B": inst.B, "W": inst.W}
        engine._init(args, road.inc_by_node)
        _, out, _ = engine._shelter_job((dn, acc, [(o, ib)]))
        r = out[o]
        S = [tuple(p) for p in r["set"]]
        feasible = bool(S) and S[0][0] == 0
        row = {"closed_road_cells": len(cs), "closed_at_issue": sum(1 for s in cs.values() if s == 0), "issue_set_s": S, "feasible_at_issue": feasible,
               "latest_departure_s": S[-1][1] if S else None}
        if r["w_first"]:
            edges = [leg[1] for leg in r["w_first"]["legs"] if leg[0] == "EDGE"]
            row["route"] = route_summary(edges, roads); row["arrival_s"] = r["w_first"]["arrival"]
        else:
            row["route"] = None
        # where the fastest fire-free route is cut: first closed cell on it and its closure second
        cut = None
        tt = 0
        for j in ff_path:
            for c, zb in road.seg[j]:
                if c in cs and cs[c] <= tt + road.D[j]:
                    cut = {"edge_name": name[j], "cell": c, "closure_s": cs[c], "reached_at_s": tt}
                    break
            if cut:
                break
            tt += road.D[j]
        row["fire_free_route_first_closed_cell"] = cut
        row["pass"] = feasible and row["route"] is not None and row["route"]["share_on_documented"] >= 0.80
        case["variants"][v] = row
    res["cases"].append(case)
    print(m, t, {v: (case["variants"][v]["feasible_at_issue"], case["variants"][v]["route"] and case["variants"][v]["route"]["share_on_documented"]) for v in VARIANTS}, flush=True)
(OUT / "test3_movements.json").write_text(json.dumps(res, indent=1, default=str))
