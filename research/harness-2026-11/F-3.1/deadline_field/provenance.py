"""Deadline provenance labels at 1 h (wfg.f31.deadline_provenance/1), from
  (a) reproduce.py outputs (cert and fire-free 'free' fields; exact uncapped deadlines per origin), and
  (b) ablation.py planner output (c651 vs present-fire-only exact deadlines per origin).
Labels: window (cert == free), present_fire (cert < free and c651 == present), forecast_dependent (c651 != present;
both values given), no_checked_route (cert is None), not_computed (origin absent from the ablation).
Asserts that the ablation's c651 deadline equals the reproduction's cert deadline for every origin."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def build(reproduce_paths, ablation_path):
    ab = json.loads(Path(ablation_path).read_text())
    A = {(p["cache_file"], oid): r for p in ab["planner"] for oid, r in p["origins"].items()}
    out, c = [], Counter()
    for p in reproduce_paths:
        d = json.loads(Path(p).read_text())
        for oid, o in d["origins"].items():
            a = A.get((d["cache_file"], oid))
            ec, ef = o["field_deadline_exact_uncapped_cert"], o["field_deadline_exact_uncapped_free"]
            rec = {"cache": d["cache_file"], "origin_id": oid, "kind": o["kind"], "leave_by_s": ec, "fire_free_leave_by_s": ef}
            if a is not None and a["exact_c651"] != ec:
                raise AssertionError("ablation c651 != reproduction cert for %s %s" % (d["cache_file"], oid))
            if ec is None:
                lab = "no_checked_route"
            elif a is None:
                lab = "not_computed"
            elif ec == ef:
                lab = "window"
            elif a["exact_c651"] == a["exact_present"]:
                lab = "present_fire"
            else:
                lab = "forecast_dependent"
                rec["leave_by_with_forecast_s"] = a["exact_c651"]
                rec["leave_by_present_fire_only_s"] = a["exact_present"]
            rec["provenance"] = lab
            c[lab] += 1
            out.append(rec)
    # origins requested in the cache but without any route-check job (rejected/failed requests): explicit not_computed
    root = Path(__file__).resolve().parents[4]
    have = {(r["cache"], r["origin_id"]) for r in out}
    for cache in sorted({r["cache"] for r in out}):
        doc = json.loads((root / cache).read_text())
        for req in doc.get("requests") or []:
            for o in req.get("origins") or []:
                if (cache, o["id"]) not in have:
                    have.add((cache, o["id"]))
                    out.append({"cache": cache, "origin_id": o["id"], "kind": "dispatch", "leave_by_s": None,
                                "fire_free_leave_by_s": None, "provenance": "not_computed",
                                "note": "requested in the cache but no route-check job exists for it; never render as safe"})
                    c["not_computed"] += 1
    return {"schema": "wfg.f31.deadline_provenance/1",
            "time_base": "integer seconds after the cache input_time (UTC); exact 1-second latest departure, uncapped by the planner grid",
            "rule": "cert field (router rule OR closed whole-road rule); full policy on these packets (checked precondition)",
            "labels": {"window": "leave_by equals the fire-free control: set by the scenario window/horizon and travel time",
                       "present_fire": "leave_by earlier than fire-free, unchanged when forecast new ignitions are removed: set by fire already burning",
                       "forecast_dependent": "leave_by changes when forecast new ignitions are removed; both values given",
                       "no_checked_route": "no departure second in [0,H] has a checked route (proven within the model)",
                       "not_computed": "no field result: origin absent from the ablation run, or requested in the cache without any route-check job"},
            "counts": dict(c), "records": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("reproduce", nargs="+", type=Path)
    ap.add_argument("--ablation", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    doc = build(a.reproduce, a.ablation)
    a.out.write_text(json.dumps(doc, indent=0))
    print(doc["counts"])


if __name__ == "__main__":
    main()
