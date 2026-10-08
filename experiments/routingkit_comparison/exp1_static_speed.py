"""Experiment 1: raw shortest-path speed on the full Nangok graph, no fire.

Compares RoutingKit (Dijkstra / CH / CCH, node-based and turn-expanded) with
our exact solver (routing.core.solve, baseline and A*) on hazard-free
earliest-arrival queries. This isolates engine overhead from wildfire logic.
"""
import time
import numpy as np
from common import *
from routing.core import solve
from routing.prepared import prepare_graph


def main(n_ours=30, seed=3):
    d = load_fixture()
    road = Road(d["graph"])
    road.write_rk(RESULTS / "car_graph.txt", CAR_SPEED)
    rk = RK()
    info = rk.cmd(f"LOAD car {RESULTS / 'car_graph.txt'}")
    bench = rk.cmd("BENCH car 2000 11")
    # our solver: zero-flux, fully supported hazard over 1 h
    horizon = 3600.0
    zero = [(np.zeros((60, road.grid["width"] * road.grid["height"])),
             np.zeros((60, road.grid["width"] * road.grid["height"]), bool))]
    bps = np.arange(0.0, horizon + 60, 60)
    hz = to_solver_hazard(road, bps, zero)
    g = road.solver_graph()
    t0 = time.perf_counter(); pg = prepare_graph(g); prep_s = time.perf_counter() - t0
    rng = np.random.default_rng(seed)
    rows = []
    rk.setclose("car", [None] * len(road.edge_ids))
    while len(rows) < n_ours:
        a, b = rng.integers(len(road.node_ids), size=2)
        if a == b or not road.out[a] or not road.inc[b]:
            continue
        req = {
            "position": {"node": road.node_ids[a]}, "incoming_edge": None,
            "departure": 0.0, "horizon": horizon,
            "destinations": [{"node": road.node_ids[b], "dwell": 0.0, "open_intervals": [[0.0, horizon]]}],
            "incurred": {"m0": 0.0}, "hazard_version": 1, "as_of": hz["issued_at"],
            "objective": "earliest_arrival", "exposure_scope": "route_only",
            "budgets": {"peak": CAR_PEAK, "dose": {"m0": CAR_DOSE}},
            "limits": {"wall_s": 60.0, "max_labels": 3_000_000, "max_expansions": 3_000_000,
                       "frontier_width": 4096, "rss_limit_mb": 6000},
        }
        row = {"src": int(a), "dst": int(b)}
        for solver in ["baseline", "astar"]:
            req["solver"] = solver
            t0 = time.perf_counter()
            r = solve(pg, hz, req)
            row[solver] = {"status": r["status"], "arrival": r["arrival"], "wall_s": time.perf_counter() - t0,
                           "labels": r["metrics"]["labels"], "expansions": r["metrics"]["expansions"]}
        tdq = rk.td("car", [(a, 0)], [b])
        row["rk_td_arrival_s"] = tdq["arrival"] / 1000 if tdq["arrival"] >= 0 else None
        row["rk_td_us"] = tdq["us"]
        rows.append(row)
        print(row, flush=True)
    rk.close()
    def med(k):
        v = [r[k]["wall_s"] for r in rows if r[k]["status"] != "TIMEOUT"]
        return {"median_ms": 1000 * float(np.median(v)) if v else None,
                "timeouts": sum(r[k]["status"] == "TIMEOUT" for r in rows), "n": len(rows)}
    # arrival agreement: our lattice uses 1 s ceilings per edge, RK uses 1 ms ceilings
    agree = [abs((r["astar"]["arrival"] or 0) - (r["rk_td_arrival_s"] or 0)) for r in rows
             if r["astar"]["arrival"] is not None and r["rk_td_arrival_s"] is not None]
    out = {"routingkit_load": info, "routingkit_bench": bench, "ours_prepare_graph_s": prep_s,
           "ours_baseline": med("baseline"), "ours_astar": med("astar"),
           "arrival_abs_diff_s": {"max": max(agree) if agree else None, "median": float(np.median(agree)) if agree else None},
           "rows": rows}
    save("exp1_static_speed.json", out)
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
