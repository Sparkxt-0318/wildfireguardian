"""Burn-duration sensitivity of feasible-departure holes (rule: BURN_DURATION_SENSITIVITY_RULE.md, committed first).

One packet, factors f in {1, 0.5, 2, never}: cert contact field per destination of the region's origins; per origin the
union U of feasible departure seconds, hole flag, contiguous deadline (end of U's first interval if it starts at 0).
Holes surviving 'never' are classified from the blocking pieces. Contact-field counterfactuals (f != 1 is not
policy-checked). SCENARIO (F-DYN), not what happened.
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402

FACTORS = ("1", "0.5", "2", "never")


def _fac(s):
    return None if s == "1" else ("never" if s == "never" else s)


def run_factor(graph, packet, instance, fac):
    t0 = time.perf_counter()
    pm = PacketModel(graph, packet, duration_factor=_fac(fac))
    H = pm.H
    specs = {}
    for o in instance["origins"]:
        for d in o["destinations"]:
            specs.setdefault((d["node"], d["dwell_s"]), set()).add(o["entry_node"])
    feas = {}
    for (dnode, dwell), origins in sorted(specs.items()):
        fld = backward(pm.instance("cert", [{"node": dnode, "dwell": dwell, "window": [0, H]}], sorted(origins)))
        for o in origins:
            feas[(dnode, o)] = issue_set(fld, pm.nidx[o])
    rows = {}
    for o in instance["origins"]:
        e = o["entry_node"]
        U = iv.normalize([p for d in o["destinations"] for p in feas[(d["node"], e)]])
        hole = bool(U) and (len(U) > 1 or U[0][0] > 0)
        contig = U[0][1] if U and U[0][0] == 0 else None
        per_dest = {d["node"]: feas[(d["node"], e)] for d in o["destinations"]}
        rows[o["origin_id"]] = {"entry_node": e, "union": U, "hole": hole, "contiguous_deadline_s": contig,
                                "per_destination": per_dest if hole else None}
    return rows, {"seconds": time.perf_counter() - t0, "edges_touching": pm.edges_touching}


def classify_never_hole(row):
    """Rule order: destination opening window (all [0, H] here) -> issue-point/wait blocking -> implementation fault.
    Under never-clears every per-destination set should be a prefix; report which kind of non-prefix occurs."""
    kinds = []
    for d, s in row["per_destination"].items():
        if s and (len(s) > 1 or s[0][0] > 0):
            kinds.append({"dest": d, "set": s,
                          "kind": "single_destination_non_prefix" if len(s) > 1 or s[0][0] > 0 else "prefix"})
    return {"cause": "unclassified_needs_inspection(potential implementation fault)" if kinds else
            "union_only(per-destination prefixes; cannot happen for a union of prefixes)", "detail": kinds}


def summarize(outs: list) -> dict:
    """Committed summary: per packet and factor the counts of the rule, the origins with a hole, and every origin whose
    contiguous deadline differs from f = 1 (both values). Never pooled across packets."""
    pk = []
    for d in outs:
        base = d["per_origin"]["1"]
        e = d.get("manifest_entry", {})
        row = {"packet": "%s %s h%d %s" % (d["region"], d["start"], d["horizon_s"] // 3600, e.get("variant")),
               "variant_label": "bracket-start, not a lower bound" if e.get("variant") == "firms_early" else None,
               "counts": {f: {k: v for k, v in x.items() if k != "timing"} for f, x in d["summary"].items()},
               "never_clears_holes": d["never_clears_holes"],
               "holes": {f: sorted(o for o, r in d["per_origin"][f].items() if r["hole"]) for f in FACTORS},
               "deadline_changes": {f: {o: [base[o]["contiguous_deadline_s"], r["contiguous_deadline_s"]]
                                        for o, r in d["per_origin"][f].items()
                                        if r["contiguous_deadline_s"] != base[o]["contiguous_deadline_s"]}
                                    for f in FACTORS if f != "1"},
               "wall_s": {f: round(x["timing"]["seconds"], 1) for f, x in d["summary"].items()}}
        pk.append(row)
    return {"what": "burn-duration sensitivity of feasible-departure holes, Uiseong F-DYN v3.1 packets (rule: "
                    "BURN_DURATION_SENSITIVITY_RULE.md). SCENARIO, not what happened; f != 1 are contact-field "
                    "counterfactuals (not policy-checked). deadline_changes: origin -> [f=1, f] contiguous deadline (s).",
            "packets": pk}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-from", nargs="+", type=Path, help="write the committed summary from raw outputs")
    ap.add_argument("--graph", type=Path)
    ap.add_argument("--packet", type=Path)
    ap.add_argument("--instance-json", type=Path)
    ap.add_argument("--region")
    ap.add_argument("--start")
    ap.add_argument("--horizon-s", type=int)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.summary_from:
        a.out.write_text(json.dumps(summarize([json.loads(f.read_text()) for f in a.summary_from]), indent=1))
        return
    doc = json.loads(a.instance_json.read_text())
    cand = [i for i in doc["instances"] if i["region"] == a.region and i["horizon_s"] == a.horizon_s]
    inst = next((i for i in cand if i["start_tag"] == a.start), cand[0])
    res, tim = {}, {}
    for f in FACTORS:
        res[f], tim[f] = run_factor(a.graph, a.packet, inst, f)
    base = res["1"]
    summ = {}
    for f in FACTORS:
        r = res[f]
        summ[f] = {"origins": len(r), "origins_with_hole": sum(x["hole"] for x in r.values()),
                   "contiguous_deadline_changed_vs_f1": sum(r[o]["contiguous_deadline_s"] != base[o]["contiguous_deadline_s"] for o in r),
                   "contiguous_deadline_appeared": sum(base[o]["contiguous_deadline_s"] is None and r[o]["contiguous_deadline_s"] is not None for o in r),
                   "contiguous_deadline_disappeared": sum(base[o]["contiguous_deadline_s"] is not None and r[o]["contiguous_deadline_s"] is None for o in r),
                   "timing": tim[f]}
    never_holes = {o: classify_never_hole(x) for o, x in res["never"].items() if x["hole"]}
    out = {"schema": "wfg.f31.burn_sensitivity/1", "packet": str(a.packet), "region": a.region, "start": a.start,
           "horizon_s": a.horizon_s,
           "label": "SCENARIO (F-DYN), not what happened; contact-field counterfactuals for f != 1 (not policy-checked)",
           "summary": summ, "never_clears_holes": never_holes,
           "per_origin": {f: {o: {k: x[k] for k in ("union", "hole", "contiguous_deadline_s")} for o, x in res[f].items()}
                          for f in FACTORS},
           "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0}
    a.out.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({"summary": {f: {k: v for k, v in s.items() if k != "timing"} for f, s in summ.items()},
                      "never_holes": len(never_holes)}))


if __name__ == "__main__":
    main()
