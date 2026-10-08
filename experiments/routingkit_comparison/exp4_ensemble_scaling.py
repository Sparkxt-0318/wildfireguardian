"""Experiment 4: compute scaling with forecast ensemble size (5, 15, 30 members).

Plans with all members (no held-out truth); measures status and compute only.
rk_td_hull + our independent checker gate vs our exact solver vs our solver
with cross-time dominance on the monotone hull.
"""
import os
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from common import *
import exp2_fire_evacuation as X

SIZES = [5, 15, 30]
N_Q = int(os.environ.get("N_Q", 12))
W = {}


def build(n):
    d = load_fixture()
    road = Road(d["graph"])
    A = make_ensemble(road, n, seed=7)
    bps, raw = hazard_tables(A, X.H)
    _, hull = hazard_tables(A, X.H, monotone=True)
    return road, A, bps, raw, hull


def _init():
    from routing.prepared import prepare_graph
    road = Road(load_fixture()["graph"])
    W["pg"] = prepare_graph(road.solver_graph(EVAC_SPEED))
    W["road"] = road
    W["cache"] = {}


def job(args):
    n, origin, shelters, variant = args
    from routing.core import solve as exact
    import monotone_core
    if n not in W["cache"]:
        W["cache"] = {n: build(n)}
    road, A, bps, raw, hull = W["cache"][n]
    ids = [f"m{j}" for j in range(n)]
    hz = to_solver_hazard(road, bps, raw if variant == "ours_exact" else hull, ids=ids)
    req = X.request_for(road, origin, shelters, ids)
    t0 = time.perf_counter()
    r = (exact if variant == "ours_exact" else monotone_core.solve)(W["pg"], hz, req)
    return {"n": n, "origin": origin, "variant": variant, "status": r["status"], "arrival": r["arrival"],
            "compute_s": time.perf_counter() - t0, "labels": r["metrics"].get("labels")}


def main():
    from routing.independent import check_route
    rows = []
    road5, A5, _, _, hull5 = build(5)
    shelters, evac = X.pick_sites(road5, A5, hull5)
    evac = evac[:N_Q]
    g = road5.solver_graph(EVAC_SPEED)
    ticks = np.array([e["travel_ticks"] for e in g["edges"]])
    road5.write_rk(RESULTS / "car_graph_lattice.txt", EVAC_SPEED, lattice_dt=DT)
    rk = RK()
    rk.cmd(f"LOAD car {RESULTS / 'car_graph_lattice.txt'}")
    jobs = []
    for n in SIZES:
        road, A, bps, raw, hull = build(n)
        ids = [f"m{j}" for j in range(n)]
        fc_raw = to_solver_hazard(road, bps, raw, ids=ids)
        rk.setclose("car", edge_close_ms(road, cell_close_times(bps, hull, CAR_PEAK)))
        for o in evac:
            t0 = time.perf_counter()
            q = rk.td("car", [(o, 0)], shelters)
            t_rk = time.perf_counter() - t0
            st, t_chk = "NO_ROUTE", 0.0
            if q["arrival"] >= 0:
                legs, arr = X.legs_from_edges(road, ticks, q["path"])
                t1 = time.perf_counter()
                c = check_route(g, fc_raw, X.request_for(road, o, shelters, ids), legs, road.node_ids[road.ev[q["path"][-1]]])
                t_chk = time.perf_counter() - t1
                st = "CHECKED" if c["ok"] else "GATE_REJECTED"
            rows.append({"n": n, "origin": o, "variant": "rk_td_hull+check", "status": st,
                         "arrival": arr if q["arrival"] >= 0 else None, "compute_s": t_rk + t_chk, "rk_s": t_rk, "check_s": t_chk})
            jobs += [(n, o, shelters, "ours_exact"), (n, o, shelters, "ours_monotone")]
        print("rk done", n, flush=True)
    rk.close()
    jobs.sort(key=lambda j: j[0])
    with ProcessPoolExecutor(max_workers=int(os.environ.get("WORKERS", 3)), initializer=_init) as ex:
        for r in ex.map(job, jobs, chunksize=1):
            rows.append(r)
            print(r, flush=True)
    summary = {}
    for n in SIZES:
        for v in ["rk_td_hull+check", "ours_exact", "ours_monotone"]:
            rr = [r for r in rows if r["n"] == n and r["variant"] == v]
            c = [r["compute_s"] for r in rr]
            summary[f"{n}:{v}"] = {"median_ms": 1000 * float(np.median(c)), "max_ms": 1000 * float(np.max(c)),
                                   "statuses": {s: sum(r["status"] == s for r in rr) for s in sorted({r["status"] for r in rr})}}
        a = {(r["origin"], r["variant"]): r["arrival"] for r in rows if r["n"] == n}
        summary[f"{n}:arrival_agreement_rk_vs_monotone"] = sum(a[(o, "rk_td_hull+check")] == a[(o, "ours_monotone")] for o in evac)
    save("exp4_ensemble_scaling.json", {"summary": summary, "rows": rows})
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
