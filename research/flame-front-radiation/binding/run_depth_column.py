"""Third, clearly labelled column (not the headline): the flame-depth emissivity law on fixed routes.

Evaluates the 18 returned journeys and the travel-only (A0) and contact (A1) routes of the policy study, whose planning
does not depend on the radiation law, with FuelParameters(emissivity_model="flame_depth") (k = 0.72 /m, T_f = 1200 K).
Thermal policies (A2 to A4) are not re-planned under this law (that would need new planning tables). Writes
DEPTH_COLUMN.json next to this script. Resumable through binding/work/depth_column.jsonl.

    OMP_NUM_THREADS=1 python research/flame-front-radiation/binding/run_depth_column.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "experimental/flame-front-radiation/adapters"))
sys.path.insert(0, str(HERE))
import journey_check as JC  # noqa: E402
import policy_sweep as PS  # noqa: E402
from journeys import load_returned_journeys  # noqa: E402
from workstore import WorkStore  # noqa: E402

FUEL = {"emissivity_model": "flame_depth"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default=os.environ.get("WFG_ROUTING_INPUTS", "/home/user/wfg-shared/routing-inputs"))
    a = ap.parse_args()
    store = WorkStore(HERE / "work" / "depth_column.jsonl")
    cases = {}

    def case_of(c, cid):
        if (c, cid) not in cases:
            cases[(c, cid)] = JC.Case(a.inputs, c, cid)
        return cases[(c, cid)]
    out = {"law": "flame-depth emissivity, k = 0.72 per m, T_f = 1200 K (not the headline)", "journeys": [], "routes": []}
    for i, j in enumerate(load_returned_journeys()):
        key = ("journey", i)
        if not store.has(key):
            t0 = time.perf_counter()
            r = JC.check_v2(case_of(j["cohort"], j["case_id"]), j["legs"], j["destination"], fuel=FUEL)
            r["wall_s"] = time.perf_counter() - t0
            store.put(key, json.loads(json.dumps(r, default=str)))
            print("journey", i, r["journey_status"], flush=True)
        out["journeys"].append({"index": i, "case_id": j["case_id"], **store.get(key)})
    missions = sorted((p.parent.name, p.stem) for p in (Path(a.inputs) / "latest_inputs_try02/requests").glob("*/*.json"))
    for cohort, cid in missions:
        case = case_of(cohort, cid)
        P = PS.Problem(case)
        for pol, contact in (("A0", False), ("A1", True)):
            key = ("route", cid, pol)
            if not store.has(key):
                r = PS.reach_sweep(P, contact=contact)
                rec = {"status": r["status"], "arrival": r.get("arrival")}
                if r["status"] == "ROUTE":
                    chk = JC.check_v2(case, r["legs"], r["destination"], fuel=FUEL, certify=False)
                    mem = chk["per_member"].values()
                    rec.update({"contact_ok": chk["contact_ok"],
                                "peak_ok": all(m["peak_kw_m2"] <= m["peak_limit_kw_m2"] for m in mem),
                                "dose_ok": all(m["dose_kj_m2"] <= m["dose_budget_kj_m2"] for m in mem),
                                "max_peak_kw_m2": max(m["peak_kw_m2"] for m in mem),
                                "max_dose_added_kj_m2": max(m["dose_added_kj_m2"] for m in mem),
                                "max_dose_tdu": max(m["dose_tdu"] for m in mem)})
                store.put(key, rec)
                print("route", cid, pol, rec.get("status"), rec.get("peak_ok"), rec.get("dose_ok"), flush=True)
            out["routes"].append({"case_id": cid, "policy": pol, **store.get(key)})
    (HERE / "DEPTH_COLUMN.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
