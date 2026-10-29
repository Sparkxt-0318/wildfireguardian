"""Replay the 18 distinct returned journeys of the Korean 20-mission panel under law v1 and law v2.

Order: two repetitions; within repetition r the two checkers (v1 frozen centre check, v2 E = 100 with certification)
alternate ABBA by journey index (journey i runs v1 first when i + r is even). Timings are wall-clock on this host and
tracemalloc peaks of Python and NumPy allocations during each check. Afterwards (untimed) every journey is also
evaluated with the measurement-consistent setting E23 and, as a truncation sensitivity, with a 2,000 m cutoff (E100,
sampled only). Writes REPLAY.json and REPLAY_MEMBERS.csv next to this script.

    OMP_NUM_THREADS=2 python research/flame-front-radiation/binding/run_replay.py [--inputs DIR]
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

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "experimental/flame-front-radiation/adapters"))

import numpy as np  # noqa: E402

import journey_check as JC  # noqa: E402
from journeys import load_returned_journeys  # noqa: E402


def timed(fn):
    tracemalloc.start()
    t0 = time.perf_counter()
    out = fn()
    el = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return out, el, peak


def strip(v2):
    return {k: v for k, v in v2.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default=os.environ.get("WFG_ROUTING_INPUTS", "/home/user/wfg-shared/routing-inputs"))
    ap.add_argument("--reps", type=int, default=2)
    a = ap.parse_args()
    journeys = load_returned_journeys()
    cases = {}
    rows, timings = [], []
    results = {}
    load_before = os.getloadavg()
    for rep in range(1, a.reps + 1):
        for i, j in enumerate(journeys):
            key = (j["cohort"], j["case_id"])
            if key not in cases:
                cases[key] = JC.Case(a.inputs, *key)
            case = cases[key]
            order = ["v1", "v2"] if (i + rep) % 2 == 0 else ["v2", "v1"]
            v1res = None
            for law in order:
                if law == "v1":
                    out, el, peak = timed(lambda: JC.check_v1(case, j["legs"], j["destination"]))
                    v1res = out
                else:
                    out, el, peak = timed(lambda: JC.check_v2(case, j["legs"], j["destination"],
                                                             fuel=JC.FUEL_SETTINGS["E100"]["fuel"]))
                timings.append({"rep": rep, "journey": i, "cohort": j["cohort"], "case_id": j["case_id"],
                                "law": law, "position": order.index(law), "wall_s": el, "tracemalloc_peak_bytes": peak})
                results.setdefault((i, law), []).append(out)
            print("rep", rep, "journey", i, j["case_id"], "done", flush=True)
    # determinism across repetitions
    deterministic = all(json.dumps(v[0], sort_keys=True, default=str) == json.dumps(x, sort_keys=True, default=str)
                        for v in results.values() for x in v[1:])
    journeys_out = []
    for i, j in enumerate(journeys):
        case = cases[(j["cohort"], j["case_id"])]
        v1 = results[(i, "v1")][0]
        v2 = results[(i, "v2")][0]
        v2_e23 = JC.check_v2(case, j["legs"], j["destination"], fuel=JC.FUEL_SETTINGS["E23"]["fuel"], contact=v1)
        v2_far = JC.check_v2(case, j["legs"], j["destination"], fuel={"cutoff_radius_m": 2000.0}, contact=v1,
                             certify=False)
        recorded_ok = all(abs(v1["per_member"][m]["dose"] - r["dose"]) <= 1e-9 * max(1.0, abs(r["dose"]))
                          for m, r in j["recorded_centre_per_member"].items())
        journeys_out.append({"index": i, "cohort": j["cohort"], "case_id": j["case_id"], "legs_sha256": j["legs_sha256"],
                             "arrival": j["arrival"], "executions": j["executions"], "input_hashes": case.hashes,
                             "v1": {"status": v1["status"], "codes": v1["codes"], "per_member": v1["per_member"],
                                    "matches_recorded_centre_dose_1e-9": recorded_ok},
                             "v2_E100": v2, "v2_E23": v2_e23, "v2_E100_cutoff2000_sampled": v2_far})
        for setting, res in (("E100", v2), ("E23", v2_e23), ("E100_cutoff2000", v2_far)):
            for mid, rec in res["per_member"].items():
                rows.append({"journey": i, "cohort": j["cohort"], "case_id": j["case_id"], "setting": setting,
                             "member": mid, "journey_status": res["journey_status"], **{k: rec.get(k) for k in (
                                 "status", "peak_kw_m2", "peak_upper_kw_m2", "peak_time_s", "peak_x", "peak_y",
                                 "peak_phase", "peak_band", "dose_kj_m2", "dose_added_kj_m2", "dose_upper_kj_m2",
                                 "dose_budget_kj_m2", "dose_tdu", "dose_margin_kj_m2", "peak_margin_kw_m2",
                                 "exposed_seconds_over_1kw", "engulfed_samples")}})
    with open(HERE / "REPLAY_MEMBERS.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader(); w.writerows(rows)
    t = {law: [x["wall_s"] for x in timings if x["law"] == law] for law in ("v1", "v2")}
    m = {law: [x["tracemalloc_peak_bytes"] for x in timings if x["law"] == law] for law in ("v1", "v2")}
    summary = {"journeys": len(journeys), "route_executions": sum(len(j["executions"]) for j in journeys),
               "deterministic_across_reps": deterministic,
               "v1_regression_all_match": all(x["v1"]["matches_recorded_centre_dose_1e-9"] for x in journeys_out)}
    for s in ("E100", "E23"):
        key = "v2_" + s
        st = [x[key]["journey_status"] for x in journeys_out]
        summary[s] = {status: st.count(status) for status in sorted(set(st))}
        summary[s]["missions_with_a_failing_journey"] = len({x["case_id"] for x in journeys_out
                                                             if x[key]["journey_status"].startswith("FAIL")})
        summary[s]["max_sampled_peak_kw_m2"] = max(r["peak_kw_m2"] for x in journeys_out for r in x[key]["per_member"].values())
        summary[s]["max_peak_upper_kw_m2"] = max(r["peak_upper_kw_m2"] for x in journeys_out for r in x[key]["per_member"].values())
        summary[s]["max_added_dose_kj_m2"] = max(r["dose_added_kj_m2"] for x in journeys_out for r in x[key]["per_member"].values())
    summary["cost"] = {law: {"median_wall_s": float(np.median(t[law])), "max_wall_s": float(np.max(t[law])),
                             "median_tracemalloc_peak_mib": float(np.median(m[law])) / 2**20,
                             "max_tracemalloc_peak_mib": float(np.max(m[law])) / 2**20} for law in t}
    summary["cost"]["median_ratio_v2_over_v1"] = float(np.median([
        np.median([x["wall_s"] for x in timings if x["law"] == "v2" and x["journey"] == i])
        / np.median([x["wall_s"] for x in timings if x["law"] == "v1" and x["journey"] == i])
        for i in range(len(journeys))]))
    host = {"platform": platform.platform(), "python": platform.python_version(), "numpy": np.__version__,
            "cpu_count": os.cpu_count(), "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
            "loadavg_before": load_before, "loadavg_after": os.getloadavg(),
            "note": "host-specific Linux container measurement shared with two other agents; not comparable with the frozen native-Mac numbers"}
    (HERE / "REPLAY.json").write_text(json.dumps({"summary": summary, "host": host, "timings": timings,
                                                  "journeys": journeys_out}, indent=1, default=str))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
