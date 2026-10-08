"""Experiment 2: vehicle evacuation under a spreading fire on the Nangok graph.

For each held-out "truth" fire member k (leave-one-out), forecast-based
strategies only see the other members; nowcast strategies see the truth
fire's *current* state (a generous, perfect-observation assumption).

Strategies
  rk_static_now    RoutingKit CCH, block edges unsafe right now, plan once
  rk_replan_60s    RoutingKit CCH, re-block from current truth state and
                   re-plan every 60 s from the vehicle's current edge
  rk_static_fcst   RoutingKit CCH, block every edge unsafe at ANY time in the
                   forecast horizon (time-agnostic conservative closure)
  ours_exact       routing.core.solve (A*), exact time-dependent multi-member
  rk_td_hull       RoutingKit Dijkstra with a time-dependent weight functor
                   (edge allowed iff traversal ends before its forecast
                   closing time; monotone hull) + our independent checker gate
  ours_monotone    our solver with cross-time dominance on the monotone hull

Every executed route is re-timed on the same 1 s lattice and evaluated by our
independent checker (routing.independent.check_route) against the truth fire.
"""
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from common import *

H = 5400.0  # 90 min planning horizon
N_EVAC = int(os.environ.get("N_EVAC", 30))
N_MEMBERS = 5
WALL = float(os.environ.get("OURS_WALL", 60))


def setup():
    d = load_fixture()
    road = Road(d["graph"])
    A = make_ensemble(road, N_MEMBERS)
    bps, raw = hazard_tables(A, H)
    _, hull = hazard_tables(A, H, monotone=True)
    return road, A, bps, raw, hull


def pick_sites(road, A, hull, seed=5):
    rng = np.random.default_rng(seed)
    amin = A.min(axis=0)
    maxflux = np.max([fl.max(axis=0) for fl, _ in hull], axis=0)
    has_out = np.array([len(o) > 0 for o in road.out])
    has_in = np.array([len(i) > 0 for i in road.inc])
    cell = road.node_cell
    centre = road.xy[np.isfinite(amin[cell]) & (amin[cell] < 3600)].mean(axis=0)
    safe = np.where(has_in & has_out & (maxflux[cell] < 1.0) & (amin[cell] > 3 * H)
                    & (np.hypot(*(road.xy - centre).T) < 9000))[0]
    shelters = [safe[np.argmin(np.hypot(*(road.xy[safe] - centre).T))]]
    while len(shelters) < 6:
        dmin = np.min([np.hypot(*(road.xy[safe] - road.xy[s]).T) for s in shelters], axis=0)
        shelters.append(safe[np.argmax(dmin)])
    t0_ok = np.all([(fl[0] <= CAR_PEAK) & ~fm[0] for fl, fm in hull], axis=0)
    cand = np.where(has_out & t0_ok[cell] & (amin[cell] >= 600) & (amin[cell] <= 3000))[0]
    evac = rng.choice(cand, size=min(N_EVAC, len(cand)), replace=False)
    return [int(s) for s in shelters], [int(e) for e in evac]


def request_for(road, origin, shelters, member_ids, solver="astar", wall=WALL):
    return {
        "position": {"node": road.node_ids[origin]}, "incoming_edge": None,
        "departure": 0.0, "horizon": H,
        "destinations": [{"node": road.node_ids[s], "dwell": 0.0, "open_intervals": [[0.0, H]]} for s in shelters],
        "incurred": {m: 0.0 for m in member_ids}, "hazard_version": 1,
        "as_of": "2026-10-04T00:00:00+09:00", "objective": "earliest_arrival",
        "exposure_scope": "route_only",
        "budgets": {"peak": CAR_PEAK, "dose": {m: CAR_DOSE for m in member_ids}},
        "limits": {"wall_s": wall, "max_labels": 2_000_000, "max_expansions": 2_000_000,
                   "frontier_width": 4096, "rss_limit_mb": 5000},
        "solver": solver,
    }


def legs_from_edges(road, ticks, edges, t0=0.0):
    legs, t = [], t0
    for e in edges:
        end = t + float(ticks[e])
        legs.append({"kind": "EDGE", "edge": road.edge_ids[e], "start": t, "end": end,
                     "from_fraction": 0, "to_fraction": 1})
        t = end
    return legs, t


# ------------------------------------------------------------------ worker state
W = {}


def _init():
    road, A, bps, raw, hull = setup()
    from routing.prepared import prepare_graph
    g = road.solver_graph(EVAC_SPEED)
    W.update(road=road, bps=bps, raw=raw, hull=hull, g=g, pg=prepare_graph(g))


def forecast_hazard(k, kind):
    F = [j for j in range(N_MEMBERS) if j != k]
    tables = W[kind]
    return to_solver_hazard(W["road"], W["bps"], [tables[j] for j in F], ids=[f"m{j}" for j in F]), [f"m{j}" for j in F]


def run_ours(args):
    k, origin, shelters, variant = args
    from routing.core import solve as exact
    import monotone_core
    road = W["road"]
    hz, ids = forecast_hazard(k, "raw" if variant == "ours_exact" else "hull")
    req = request_for(road, origin, shelters, ids)
    t0 = time.perf_counter()
    r = (exact if variant == "ours_exact" else monotone_core.solve)(W["pg"], hz, req)
    wall = time.perf_counter() - t0
    edges = [road.eidx[l["edge"]] for l in r["legs"] if l["kind"] == "EDGE"]
    return {"k": k, "origin": origin, "variant": variant, "status": r["status"], "reason": r["reason"],
            "arrival": r["arrival"], "edges": edges, "compute_s": wall,
            "labels": r["metrics"].get("labels"), "expansions": r["metrics"].get("expansions"),
            "dominance": r.get("provenance", {}).get("dominance")}


# ------------------------------------------------------------------ main
def main():
    road, A, bps, raw, hull = setup()
    shelters, evac = pick_sites(road, A, hull)
    print("shelters", shelters, "evacuees", len(evac), flush=True)
    g = road.solver_graph(EVAC_SPEED)
    ticks = np.array([e["travel_ticks"] for e in g["edges"]])
    road.write_rk(RESULTS / "car_graph_lattice.txt", EVAC_SPEED, lattice_dt=DT)
    rk = RK()
    rk.cmd(f"LOAD car {RESULTS / 'car_graph_lattice.txt'}")
    from routing.independent import check_route
    from routing.prepared import prepare_graph
    pg = prepare_graph(g)

    def unsafe_edges(tables_list, t_lo, t_hi, peak=CAR_PEAK):
        """Edges with any cell inadmissible in any member during [t_lo, t_hi]."""
        i0 = int(t_lo // BP_STEP)
        i1 = min(len(bps) - 2, int(t_hi // BP_STEP))
        bad = np.zeros(tables_list[0][0].shape[1], bool)
        for fl, fm in tables_list:
            bad |= ((fl[i0:i1 + 1] > peak) | fm[i0:i1 + 1]).any(axis=0)
        return [i for i, cs in enumerate(road.cells) if any(bad[c] for c in cs)]

    def static_plan(src, blocked):
        rk.cmd("UNBLOCK_ALL car")
        t0 = time.perf_counter()
        if blocked:
            rk.cmd(f"BLOCK car {len(blocked)} " + " ".join(map(str, blocked)))
        q = rk.cmd(f"STATIC car {src} {len(shelters)} " + " ".join(map(str, shelters)))
        return q, time.perf_counter() - t0

    jobs = []
    rows = []
    shelter_set = set(shelters)
    truth_hz = {}
    for k in range(N_MEMBERS):
        F = [j for j in range(N_MEMBERS) if j != k]
        truth_hz[k] = to_solver_hazard(road, bps, [raw[k]], ids=["truth"])
        fc_raw = to_solver_hazard(road, bps, [raw[j] for j in F], ids=[f"m{j}" for j in F])
        hull_close = edge_close_ms(road, cell_close_times(bps, [hull[j] for j in F], CAR_PEAK))
        rk.setclose("car", hull_close)
        fc_block = unsafe_edges([raw[j] for j in F], 0, H)
        for o in evac:
            jobs += [(k, o, shelters, "ours_exact"), (k, o, shelters, "ours_monotone")]
            row = {"k": k, "origin": o}
            # rk_static_now
            q, dt_ = static_plan(o, unsafe_edges([raw[k]], 0, 0))
            row["rk_static_now"] = {"edges": q["path"], "compute_s": dt_, "status": "ROUTE" if q["dist"] >= 0 else "NO_ROUTE"}
            # rk_static_fcst
            q, dt_ = static_plan(o, fc_block)
            row["rk_static_fcst"] = {"edges": q["path"], "compute_s": dt_, "status": "ROUTE" if q["dist"] >= 0 else "NO_ROUTE"}
            # rk_td_hull + checker gate against the forecast (raw, non-monotone)
            t0 = time.perf_counter()
            q = rk.td("car", [(o, 0)], shelters)
            t_rk = time.perf_counter() - t0
            st = "ROUTE" if q["arrival"] >= 0 else "NO_ROUTE"
            gate = None
            if q["arrival"] >= 0:
                legs, _ = legs_from_edges(road, ticks, q["path"])
                t1 = time.perf_counter()
                c = check_route(g, fc_raw, request_for(road, o, shelters, [f"m{j}" for j in F]), legs, road.node_ids[road.ev[q["path"][-1]]])
                gate = {"ok": c["ok"], "codes": c.get("codes"), "check_s": time.perf_counter() - t1}
                if not c["ok"]:
                    st = "GATE_REJECTED"
            row["rk_td_hull"] = {"edges": q["path"], "compute_s": t_rk, "status": st, "gate": gate, "rk_us": q["us"]}
            # rk_replan_60s (truth nowcast)
            t, edges, path, cur, next_replan, comp, nre = 0.0, [], None, str(o), 0.0, 0.0, 0
            status = "ROUTE"
            while True:
                if t >= next_replan:
                    q, dt_ = static_plan(cur, unsafe_edges([raw[k]], t, t))
                    comp += dt_
                    nre += 1
                    if q["dist"] >= 0:
                        path = q["path"][1:] if cur.startswith("e") else q["path"]
                    next_replan = t + 60.0
                    if path is None:
                        status = "NO_ROUTE"
                        break
                if not path:
                    break
                e = path.pop(0)
                edges.append(e)
                t += float(ticks[e])
                cur = f"e{e}"
                if road.ev[e] in shelter_set or t > H:
                    break
            row["rk_replan_60s"] = {"edges": edges, "compute_s": comp, "status": status if (edges and road.ev[edges[-1]] in shelter_set) else "NO_ROUTE", "replans": nre}
            rows.append(row)
        print("truth", k, "rk strategies done", flush=True)
    rk.close()

    print("running our solver on", len(jobs), "jobs", flush=True)
    ours = {}
    if os.environ.get("SKIP_OURS"):
        jobs = []
        for row in rows:
            for v in ["ours_exact", "ours_monotone"]:
                ours[(row["k"], row["origin"], v)] = {"edges": [], "compute_s": 0, "status": "SKIPPED", "reason": None,
                                                      "labels": None, "dominance": None, "arrival": None}
    with ProcessPoolExecutor(max_workers=int(os.environ.get("WORKERS", 3)), initializer=_init) as ex:
        for i, r in enumerate(ex.map(run_ours, jobs)):
            ours[(r["k"], r["origin"], r["variant"])] = r
            if i % 10 == 0:
                print(i, r["variant"], r["status"], r["arrival"], round(r["compute_s"], 2), flush=True)

    # evaluate every executed route against its truth fire
    def evaluate(k, o, strat, edges, status):
        if status not in ("ROUTE", "CONDITIONAL_OPTIMUM", "CHECKED_ROUTE") or not edges:
            return {"outcome": "NO_ROUTE"}
        legs, arr = legs_from_edges(road, ticks, edges)
        dest = road.node_ids[road.ev[edges[-1]]]
        c = check_route(g, truth_hz[k], request_for(road, o, shelters, ["truth"]), legs, dest)
        pm = c.get("per_member", {}).get("truth", {})
        return {"outcome": "SAFE" if c["ok"] else "UNSAFE", "codes": c.get("codes"), "arrival": arr,
                "dose": pm.get("dose"), "peak": pm.get("peak")}

    strategies = ["rk_static_now", "rk_replan_60s", "rk_static_fcst", "rk_td_hull", "ours_exact", "ours_monotone"]
    for row in rows:
        k, o = row["k"], row["origin"]
        for v in ["ours_exact", "ours_monotone"]:
            r = ours[(k, o, v)]
            row[v] = {"edges": r["edges"], "compute_s": r["compute_s"], "status": r["status"], "reason": r["reason"],
                      "labels": r["labels"], "dominance": r["dominance"], "planned_arrival": r["arrival"]}
        for s in strategies:
            st = row[s]["status"]
            row[s]["eval"] = evaluate(k, o, s, row[s]["edges"], st)
            row[s].pop("edges")

    summary = {}
    for s in strategies:
        ev = [r[s]["eval"] for r in rows]
        comp = [r[s]["compute_s"] for r in rows]
        safe = [e for e in ev if e["outcome"] == "SAFE"]
        summary[s] = {
            "n": len(ev),
            "safe": len(safe), "unsafe": sum(e["outcome"] == "UNSAFE" for e in ev),
            "no_route": sum(e["outcome"] == "NO_ROUTE" for e in ev),
            "statuses": {st: sum(r[s]["status"] == st for r in rows) for st in sorted({r[s]["status"] for r in rows})},
            "mean_arrival_safe_s": float(np.mean([e["arrival"] for e in safe])) if safe else None,
            "median_compute_ms": 1000 * float(np.median(comp)),
            "p95_compute_ms": 1000 * float(np.percentile(comp, 95)),
            "max_compute_ms": 1000 * float(np.max(comp)),
        }
    # paired arrival comparison where both are SAFE
    def paired(a, b):
        d = [r[a]["eval"]["arrival"] - r[b]["eval"]["arrival"] for r in rows
             if r[a]["eval"]["outcome"] == "SAFE" and r[b]["eval"]["outcome"] == "SAFE"]
        return {"n": len(d), "mean_s": float(np.mean(d)) if d else None, "max_s": float(np.max(d)) if d else None}
    summary["paired_arrival_vs_ours_exact"] = {s: paired(s, "ours_exact") for s in strategies if s != "ours_exact"}
    out = {"config": {"H": H, "members": N_MEMBERS, "evacuees": len(evac), "shelters": shelters,
                      "car_peak": CAR_PEAK, "evac_kmh": EVAC_SPEED * 3.6, "head_ros": os.environ.get("HEAD_ROS", "1.1"), "car_dose": CAR_DOSE, "ours_wall_s": WALL},
           "summary": summary, "rows": rows}
    save(f"exp2_fire_evacuation{os.environ.get('TAG', '')}.json", out)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
