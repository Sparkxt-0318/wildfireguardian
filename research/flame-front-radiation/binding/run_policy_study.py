"""Five-policy constraint study on the 20 Korean missions under law v1 (regression) and law v2 (E100 and E23).

For each mission and repetition the policies run in a cyclic order rotated by mission index and reversed in the
second repetition (the ordering rule of research/routing/final-input-ablation). v1 runs A0 and A1 only (with v1,
peak cannot bind: the global flux cap is 0.703 kW/m2 against 10 kW/m2; the frozen ablation records A2 to A4).
v2 planning tables are built once per packet (untimed per policy; their cost is reported separately). Every returned
route is re-checked with the exact law (journey_check.check_v2, sampled and certified). Writes EXECUTIONS.csv,
POLICY_STUDY.json next to this script.

    OMP_NUM_THREADS=2 python research/flame-front-radiation/binding/run_policy_study.py [--reps 2]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "experimental/flame-front-radiation/adapters"))
import journey_check as JC  # noqa: E402
import policy_sweep as PS  # noqa: E402
import flux_tables as FT  # noqa: E402

GRID_DT = 10.0
SETTINGS = {"E100": (100.0, 100.0), "E23": (JC.W.constants.EMISSIVE_POWER_MEASURED_DECAY_KW_M2, 100.0)}
FROZEN_ROWS = REPO / "research/routing/final-input-ablation/data/ROWS.csv"


def missions(inputs):
    out = []
    for p in sorted((Path(inputs) / "latest_inputs_try02/requests").glob("*/*.json")):
        out.append((p.parent.name, p.stem))
    return out


def frozen_outcomes():
    res = {}
    with open(FROZEN_ROWS) as f:
        for r in csv.DictReader(f):
            res.setdefault((r["case_id"], r["policy"]), set()).add((r["own_outcome"], r["arrival"]))
    return res


def run_policy(P, case, policy, setting):
    contact, peak, dose = PS.POLICIES[policy]
    peak_lim = float(case.request["budgets"]["peak"]) if peak else None
    if not dose:
        r = PS.reach_sweep(P, contact=contact, peak_lim=peak_lim)
        if r["status"] == "ROUTE":
            r["lb_arrival"] = r["arrival"]; r["optimal_planning_model"] = True
        return r
    lb = PS.mindose_lower_bound(P, peak_lim=peak_lim)
    if lb["status"] != "BOUND":
        return {"status": "NO_ROUTE_PLANNING" if lb["status"] == "INFEASIBLE" else lb["status"], "lb": lb}
    budgets = np.array([float(case.request["budgets"]["dose"][m]) for m in case.member_ids])
    inc = np.array([float(case.request["incurred"][m]) for m in case.member_ids])
    tried = []
    for theta in PS.THETA_LADDER:
        r = PS.reach_sweep(P, contact=contact, peak_lim=peak_lim, theta=theta)
        tried.append({"theta": theta, "status": r["status"], "arrival": r.get("arrival")})
        if r["status"] != "ROUTE":
            continue
        pk, ds = PS.planned_route_exposure(P, r["legs"], r["destination"])
        if np.all(inc + ds <= budgets):
            r["lb_arrival"] = lb["lb_arrival"]; r["theta"] = theta; r["ladder"] = tried
            r["optimal_planning_model"] = r["arrival"] == lb["lb_arrival"]
            return r
    return {"status": "UNRESOLVED_NO_FEASIBLE_LADDER_ROUTE", "lb_arrival": lb["lb_arrival"], "ladder": tried}


def judge(policy, chk):
    """Exact-law outcome of a planned route for the policy's own constraints, and full-policy pass."""
    contact, peak, dose = PS.POLICIES[policy]
    mem = chk["per_member"].values()
    own_fail = (contact and not chk["contact_ok"]) or (peak and any(m["peak_kw_m2"] > m["peak_limit_kw_m2"] for m in mem)) \
        or (dose and any(m["dose_kj_m2"] > m["dose_budget_kj_m2"] for m in mem))
    own_cert = all((not peak or m["peak_upper_kw_m2"] <= m["peak_limit_kw_m2"]) and
                   (not dose or m["dose_upper_kj_m2"] <= m["dose_budget_kj_m2"]) for m in mem)
    full = {"contact": chk["contact_ok"],
            "peak": all(m["peak_kw_m2"] <= m["peak_limit_kw_m2"] for m in mem),
            "dose": all(m["dose_kj_m2"] <= m["dose_budget_kj_m2"] for m in mem)}
    return own_fail, own_cert, full


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default=os.environ.get("WFG_ROUTING_INPUTS", "/home/user/wfg-shared/routing-inputs"))
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    ms = missions(a.inputs)
    if a.only:
        ms = [m for m in ms if m[1] in a.only]
    frozen = frozen_outcomes()
    rows, table_costs = [], {}
    pkt_cache = {}
    check_cache = {}     # (case, setting, route hash) -> exact check; the check is deterministic, reused across reps/policies
    load_before = os.getloadavg()
    pol_order = ["A0", "A1", "A2", "A3", "A4"]
    for rep in range(1, a.reps + 1):
        for mi, (cohort, case_id) in enumerate(ms):
            case = JC.Case(a.inputs, cohort, case_id)
            pkey = (cohort, case.cutoff)
            if pkey not in pkt_cache:
                t0 = time.perf_counter(); tracemalloc.start()
                t_end = float(case.request["horizon"]) + 200.0
                probes = FT.ProbeSet(case.graph, case.grid, case.fields, t_end)
                times = np.arange(0.0, t_end + GRID_DT, GRID_DT)
                tables = [FT.flux_table(probes, ff, case.grid, times) for ff in case.fields]
                _, peakmem = tracemalloc.get_traced_memory(); tracemalloc.stop()
                pkt_cache[pkey] = (probes, tables)
                table_costs["%s/%s" % pkey] = {"wall_s": time.perf_counter() - t0, "tracemalloc_peak_mib": peakmem / 2**20,
                                               "probes": int(probes.points.shape[0]), "times": int(times.size),
                                               "max_rad_per_unit_E": float(max(r.max() for r, _ in tables)) if probes.points.size else 0.0}
            probes, tables = pkt_cache[pkey]
            k = mi % 5
            order = pol_order[k:] + pol_order[:k]
            if rep % 2 == 0:
                order = order[::-1]
            Pv1 = PS.Problem(case)
            Pv2 = {s: PS.Problem(case, tables=tables, probes=probes, grid_dt=GRID_DT, E_panel=e, E_inflame=ei)
                   for s, (e, ei) in SETTINGS.items()}
            for pos, pol in enumerate(order):
                for setting in (["v1"] if pol in ("A0", "A1") else []) + list(SETTINGS):
                    P = Pv1 if setting == "v1" else Pv2[setting]
                    t0 = time.perf_counter()
                    r = run_policy(P, case, pol, setting)
                    wall = time.perf_counter() - t0
                    row = {"rep": rep, "mission_index": mi, "cohort": cohort, "case_id": case_id, "policy": pol,
                           "law": "v1" if setting == "v1" else "v2", "setting": setting, "order_position": pos,
                           "planner_status": r["status"], "arrival": r.get("arrival"), "lb_arrival": r.get("lb_arrival"),
                           "optimal_planning_model": r.get("optimal_planning_model"), "theta": r.get("theta"),
                           "planner_wall_s": wall}
                    if setting == "v1":
                        fz = frozen.get((case_id, pol), set())
                        row["frozen_outcome"] = ";".join(sorted("%s:%s" % x for x in fz))
                        row["matches_frozen"] = (("CHECKED_ROUTE", str(r.get("arrival"))) in fz) if r["status"] == "ROUTE" \
                            else (("SCOPED_REFUSAL", "") in fz and r["status"] in ("EXHAUSTED", "AT_ISSUE_FAILURE"))
                    if r["status"] == "ROUTE":
                        fuel = {} if setting in ("v1", "E100") else JC.FUEL_SETTINGS["E23"]["fuel"]
                        rh = JC.hashlib.sha256(json.dumps(r["legs"], sort_keys=True).encode()).hexdigest()
                        ckey = (case_id, "E100" if setting == "v1" else setting, rh)
                        if ckey in check_cache:
                            chk = check_cache[ckey]; row["check_wall_s"] = None; row["check_cached"] = True
                        else:
                            t1 = time.perf_counter()
                            chk = check_cache[ckey] = JC.check_v2(case, r["legs"], r["destination"], fuel=fuel)
                            row["check_wall_s"] = time.perf_counter() - t1; row["check_cached"] = False
                        own_fail, own_cert, full = judge(pol, chk)
                        row.update({"exact_own_fail": own_fail, "exact_own_certified": own_cert,
                                    "v2_contact_ok": full["contact"], "v2_peak_ok": full["peak"], "v2_dose_ok": full["dose"],
                                    "v2_full_pass": all(full.values()), "v2_journey_status": chk["journey_status"],
                                    "max_peak_kw_m2": max(m["peak_kw_m2"] for m in chk["per_member"].values()),
                                    "max_peak_upper_kw_m2": max(m["peak_upper_kw_m2"] for m in chk["per_member"].values()),
                                    "max_dose_added_kj_m2": max(m["dose_added_kj_m2"] for m in chk["per_member"].values()),
                                    "min_dose_margin_kj_m2": min(m["dose_margin_kj_m2"] for m in chk["per_member"].values()),
                                    "max_dose_tdu": max(m["dose_tdu"] for m in chk["per_member"].values()),
                                    "engulfed_samples": sum(m["engulfed_samples"] for m in chk["per_member"].values()),
                                    "n_legs": len(r["legs"]),
                                    "route_sha256": JC.hashlib.sha256(json.dumps(r["legs"], sort_keys=True).encode()).hexdigest()})
                    rows.append(row)
                    print(rep, mi, case_id, pol, setting, r["status"], r.get("arrival"), round(wall, 2), flush=True)
    keys = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(HERE / "EXECUTIONS.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    host = {"platform": platform.platform(), "python": platform.python_version(), "numpy": np.__version__,
            "cpu_count": os.cpu_count(), "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
            "loadavg_before": load_before, "loadavg_after": os.getloadavg(),
            "note": "host-specific Linux container measurement shared with two other agents; not comparable with the frozen native-Mac numbers"}
    (HERE / "POLICY_STUDY.json").write_text(json.dumps({"host": host, "table_costs": table_costs, "grid_dt_s": GRID_DT,
                                                        "settings": {k: list(v) for k, v in SETTINGS.items()},
                                                        "rows": rows}, indent=1, default=str))


if __name__ == "__main__":
    main()
