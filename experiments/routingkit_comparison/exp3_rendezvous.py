"""Experiment 3: pedestrians meeting a firefighter vehicle under a spreading fire.

A person on foot (no car) at P must reach a shelter. Fire vehicles wait at
staging stations and are dispatched after a delay. Plans use the leave-one-out
forecast (monotone hull); each plan is executed against the held-out truth fire.

  WALK     walk the whole way (time-dependent deadline Dijkstra, foot graph)
  DOOR     nearest truck drives to P, person waits at home, truck drives out
  MEET     exact fire-aware rendezvous: person walks to r, truck drives to r,
           pickup at max(walk, drive) + boarding, truck drives to a shelter;
           optimal r over ALL nodes in three Dijkstra runs (see below)
  MEET_STATIC  same rendezvous algorithm but computed fire-agnostically
           (what you get from a static engine), then executed in the fire
  BEST     min(WALK, MEET) -- the planner offers walking if it is faster

Exactness of MEET under FIFO closures that never reopen: for a fixed r the
earliest pickup is max(earliest walk(r), earliest drive(r)) because both parties
may wait at r (if r stays tenable) and arriving earlier never hurts; departing r
later never helps, so one multi-source time-dependent Dijkstra seeded with every
r at its own pickup time returns the optimal meeting point and shelter.
"""
import os
import time

import numpy as np

from common import *
import exp2_fire_evacuation as X

TRUCK_SPEED = float(os.environ.get("TRUCK_KMH", 30)) / 3.6  # emergency vehicle in partial congestion
WALK = float(os.environ.get("WALK_MS", WALK_SPEED))
DISPATCH_S = float(os.environ.get("DISPATCH_S", 120))
BOARD_S = 60.0
N_PED = int(os.environ.get("N_PED", 40))


def ped_edges(road):
    eu, ev, src = list(road.eu), list(road.ev), list(range(len(road.eu)))
    have = set(zip(eu, ev))
    for i, (u, v) in enumerate(zip(road.eu, road.ev)):
        if (v, u) not in have:
            eu.append(v), ev.append(u), src.append(i)
            have.add((v, u))
    return np.array(eu), np.array(ev), np.array(src)


def main():
    road, A, bps, raw, hull = X.setup()
    shelters, _ = X.pick_sites(road, A, hull)
    rng = np.random.default_rng(21)
    amin = A.min(axis=0)
    cell = road.node_cell
    has_out = np.array([len(o) > 0 for o in road.out])
    t0_ok = np.all([(fl[0] <= WALK_PEAK) & ~fm[0] for fl, fm in hull], axis=0)
    cand = np.where(has_out & t0_ok[cell] & (amin[cell] >= 600) & (amin[cell] <= 3000))[0]
    peds = [int(x) for x in rng.choice(cand, size=min(N_PED, len(cand)), replace=False)]
    # staging stations: safe nodes 2.5-5 km from the fire centre, spread out
    maxflux = np.max([fl.max(axis=0) for fl, _ in hull], axis=0)
    centre = road.xy[np.isfinite(amin[cell]) & (amin[cell] < 3600)].mean(axis=0)
    dist = np.hypot(*(road.xy - centre).T)
    safe = np.where(has_out & (maxflux[cell] < 1.0) & (amin[cell] > X.H + 1800) & (dist > 2500) & (dist < 5000))[0]
    stations = [int(safe[np.argmin(dist[safe])])]
    while len(stations) < 3:
        dmin = np.min([np.hypot(*(road.xy[safe] - road.xy[s]).T) for s in stations], axis=0)
        stations.append(int(safe[np.argmax(dmin)]))
    print("stations", stations, "pedestrians", len(peds), flush=True)

    # graphs: truck on directed/turn-restricted roads, people on undirected foot graph
    road.write_rk(RESULTS / "truck_graph.txt", TRUCK_SPEED, lattice_dt=DT)
    road.write_rk(RESULTS / "ped_graph.txt", WALK, pedestrian=True, lattice_dt=DT)
    peu, pev, psrc = ped_edges(road)
    ped_cells = [road.cells[i] for i in psrc]
    t_ms = (np.maximum(1, np.ceil(road.length / TRUCK_SPEED)) * 1000).astype(np.int64)
    p_ms = (np.maximum(1, np.ceil(road.length[psrc] / WALK)) * 1000).astype(np.int64)
    rk = RK()
    rk.cmd(f"LOAD truck {RESULTS / 'truck_graph.txt'}")
    rk.cmd(f"LOAD ped {RESULTS / 'ped_graph.txt'}")
    targets = list(shelters)
    INF = 1 << 62

    def closures(tables, peak):
        cc = cell_close_times(bps, tables, peak)
        return cc

    def ms(x):
        return int(x * 1000) if np.isfinite(x) else INF

    def plan(cc_ped, cc_truck, P):
        """Return dict of plans; each plan is a list of (agent, edges, t_start_ms) + wait checks."""
        if cc_ped is None:
            rk.cmd("CLEARCLOSE ped")
            rk.cmd("CLEARCLOSE truck")
            node_ped = node_truck = np.full(len(road.node_ids), INF)
        else:
            rk.setclose("ped", edge_close_ms(road, cc_ped, ped_cells))
            rk.setclose("truck", edge_close_ms(road, cc_truck))
            node_ped = np.array([ms(cc_ped[c]) for c in cell])
            node_truck = np.array([ms(cc_truck[c]) for c in cell])
        plans = {}
        t0 = time.perf_counter()
        # WALK
        q = rk.td("ped", [(P, 0)], targets)
        plans["WALK"] = None if q["arrival"] < 0 else {"arrival": q["arrival"], "legs": [("ped", q["path"], 0)], "waits": []}
        t_walk = time.perf_counter() - t0
        # trees
        t1 = time.perf_counter()
        walk_tree = np.array(rk.tree("ped", [(P, 0)])["arrival"], dtype=np.int64)
        truck_tree = np.array(rk.tree("truck", [(s, int(DISPATCH_S * 1000)) for s in stations])["arrival"], dtype=np.int64)
        both = (walk_tree >= 0) & (truck_tree >= 0)
        pick = np.where(both, np.maximum(walk_tree, truck_tree) + int(BOARD_S * 1000), -1)
        ok = both & (pick < node_ped) & (pick < node_truck)
        cand = np.where(ok)[0]
        meet = None
        if len(cand):
            q = rk.td("truck", [(int(r), int(pick[r])) for r in cand], targets)
            if q["arrival"] >= 0:
                r = q["source"] if q["path"] else None
                meet = (int(r), int(pick[r]), q)
        t_meet = time.perf_counter() - t1
        if meet:
            r, tp, q = meet
            pw = rk.td("ped", [(P, 0)], [r]) if r != P else {"path": [], "arrival": 0}
            pt = rk.td("truck", [(s, int(DISPATCH_S * 1000)) for s in stations], [r])
            plans["MEET"] = {"arrival": q["arrival"], "meet_node": r, "pickup_ms": tp,
                             "walk_ms": int(walk_tree[r]), "truck_ms": int(truck_tree[r]),
                             "legs": [("ped", pw["path"], 0), ("truck", pt["path"], int(DISPATCH_S * 1000)), ("truck", q["path"], tp)],
                             "waits": [("ped", r, int(walk_tree[r]), tp), ("truck", r, int(truck_tree[r]), tp)]}
        else:
            plans["MEET"] = None
        # DOOR: r = P only
        if both[P] and pick[P] < node_ped[P] and pick[P] < node_truck[P]:
            q = rk.td("truck", [(P, int(pick[P]))], targets)
            pt = rk.td("truck", [(s, int(DISPATCH_S * 1000)) for s in stations], [P])
            plans["DOOR"] = None if q["arrival"] < 0 else {
                "arrival": q["arrival"], "legs": [("truck", pt["path"], int(DISPATCH_S * 1000)), ("truck", q["path"], int(pick[P]))],
                "waits": [("ped", P, 0, int(pick[P])), ("truck", P, int(truck_tree[P]), int(pick[P]))]}
        else:
            plans["DOOR"] = None
        return plans, {"walk_ms": 1000 * t_walk, "meet_ms": 1000 * t_meet}

    def execute(p, truth_ped, truth_truck):
        """Check a plan against truth closures (edge-level, same semantics as planning)."""
        if p is None:
            return {"outcome": "NO_PLAN"}
        for agent, edges, t in p["legs"]:
            w = p_ms if agent == "ped" else t_ms
            cc = truth_ped if agent == "ped" else truth_truck
            ecells = ped_cells if agent == "ped" else road.cells
            for e in edges:
                t += int(w[e])
                if t >= ms(min(cc[c] for c in ecells[e])):
                    return {"outcome": "UNSAFE", "where": f"{agent}-edge"}
        for agent, node, a, b in p["waits"]:
            cc = truth_ped if agent == "ped" else truth_truck
            if b >= ms(cc[cell[node]]):
                return {"outcome": "UNSAFE", "where": f"{agent}-wait"}
        return {"outcome": "SAFE", "arrival_s": p["arrival"] / 1000}

    rows = []
    has_in = np.array([len(i) > 0 for i in road.inc])
    for k in range(len(A)):
        F = [j for j in range(len(A)) if j != k]
        if os.environ.get("TARGET", "shelters") == "safezone":
            # any node the forecast says the fire will not reach for 2 h past the horizon
            fmin = A[F].min(axis=0)
            targets[:] = [int(n) for n in np.where(has_in & (fmin[cell] > X.H + 1800))[0]]
        else:
            targets[:] = shelters
        fc_ped = closures([hull[j] for j in F], WALK_PEAK)
        fc_truck = closures([hull[j] for j in F], CAR_PEAK)
        margin = float(os.environ.get("MARGIN_S", 0))  # plan to clear every cell this long before it closes
        fc_ped, fc_truck = fc_ped - margin, fc_truck - margin
        tr_ped = closures([raw[k]], WALK_PEAK)
        tr_truck = closures([raw[k]], CAR_PEAK)
        for P in peds:
            plans, timing = plan(fc_ped, fc_truck, P)
            static_plans, _ = plan(None, None, P)
            row = {"k": k, "P": P, "timing": timing}
            for name in ["WALK", "DOOR", "MEET"]:
                row[name] = execute(plans[name], tr_ped, tr_truck)
                if plans[name] and name == "MEET":
                    row["meet_detail"] = {x: plans["MEET"][x] for x in ["meet_node", "pickup_ms", "walk_ms", "truck_ms"]}
                    row["meet_detail"]["meet_is_home"] = plans["MEET"]["meet_node"] == P
                    row["meet_detail"]["walk_m"] = float(np.hypot(*(road.xy[plans["MEET"]["meet_node"]] - road.xy[P])))
            row["MEET_STATIC"] = execute(static_plans["MEET"], tr_ped, tr_truck)
            row["WALK_STATIC"] = execute(static_plans["WALK"], tr_ped, tr_truck)
            cands = [row[n] for n in ["WALK", "MEET"] if row[n]["outcome"] == "SAFE"]
            # BEST chooses by *planned* arrival (no truth knowledge), then is executed
            pw, pm = plans["WALK"], plans["MEET"]
            choice = None
            if pw and pm:
                choice = "WALK" if pw["arrival"] <= pm["arrival"] else "MEET"
            elif pw or pm:
                choice = "WALK" if pw else "MEET"
            row["BEST"] = row[choice] if choice else {"outcome": "NO_PLAN"}
            row["BEST_choice"] = choice
            rows.append(row)
        print("truth", k, "done", flush=True)
    rk.close()

    strategies = ["WALK", "WALK_STATIC", "DOOR", "MEET", "MEET_STATIC", "BEST"]
    summary = {}
    for s in strategies:
        o = [r[s] for r in rows]
        safe = [x for x in o if x["outcome"] == "SAFE"]
        summary[s] = {"n": len(o), "safe": len(safe), "unsafe": sum(x["outcome"] == "UNSAFE" for x in o),
                      "no_plan": sum(x["outcome"] == "NO_PLAN" for x in o),
                      "mean_time_to_safety_min": float(np.mean([x["arrival_s"] for x in safe]) / 60) if safe else None}
    both = [r for r in rows if r["WALK"]["outcome"] == "SAFE" and r["MEET"]["outcome"] == "SAFE"]
    summary["paired_meet_minus_walk_min"] = {"n": len(both), "mean": float(np.mean([(r["MEET"]["arrival_s"] - r["WALK"]["arrival_s"]) / 60 for r in both])) if both else None,
                                             "share_meet_faster": float(np.mean([r["MEET"]["arrival_s"] < r["WALK"]["arrival_s"] for r in both])) if both else None}
    summary["rescued_by_meet"] = sum(1 for r in rows if r["MEET"]["outcome"] == "SAFE" and r["WALK"]["outcome"] != "SAFE" and r["DOOR"]["outcome"] != "SAFE")
    md = [r["meet_detail"] for r in rows if "meet_detail" in r]
    summary["meet_points"] = {"share_at_home": float(np.mean([m["meet_is_home"] for m in md])) if md else None,
                              "median_walk_m": float(np.median([m["walk_m"] for m in md])) if md else None,
                              "median_person_wait_s": float(np.median([(m["pickup_ms"] - m["walk_ms"]) / 1000 - BOARD_S for m in md])) if md else None,
                              "median_truck_wait_s": float(np.median([(m["pickup_ms"] - m["truck_ms"]) / 1000 - BOARD_S for m in md])) if md else None}
    summary["compute_ms"] = {"walk_median": float(np.median([r["timing"]["walk_ms"] for r in rows])),
                             "meet_median": float(np.median([r["timing"]["meet_ms"] for r in rows])),
                             "meet_p95": float(np.percentile([r["timing"]["meet_ms"] for r in rows], 95))}
    out = {"config": {"walk_ms": WALK, "truck_kmh": TRUCK_SPEED * 3.6, "dispatch_s": DISPATCH_S, "board_s": BOARD_S,
                      "walk_peak": WALK_PEAK, "margin_s": float(os.environ.get("MARGIN_S", 0)), "truck_peak": CAR_PEAK, "stations": stations, "shelters": shelters,
                      "pedestrians": len(peds), "target": os.environ.get("TARGET", "shelters"), "head_ros": os.environ.get("HEAD_ROS", "1.1")},
           "summary": summary, "rows": rows}
    tag = os.environ.get("TAG", "")
    save(f"exp3_rendezvous{tag}.json", out)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
