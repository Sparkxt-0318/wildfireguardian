"""Deadline fields on F-DYN v3 packets (Leo, leo/f-c1-see-before-leave, MANIFEST_v3.json; scenario, not what
happened; roads limited to the recorded windows).

Per packet: one 'cert' field (router rule OR closed whole-road rule) and one fire-free control field per destination
of the region's origins. Per origin: exact latest departure (1 s), latest departure on the 30-min grid, fire-set vs
window-set (control), feasible-set holes. Every exact per-(origin, destination) deadline witness is checked by the
UNCHANGED full-policy checker (routing-package/routing/independent.check_route: flame, peak, dose incl. dwell) and
the closed-footprint replay. Dose can bind at 5-8 h: each deadline is labelled
  exact_full_policy   : journey duration (departure .. end of dwell) <= (dose limit - incurred) / max non-flame flux
                        and peak cannot bind off flame -> the contact field is exact for the full policy;
  upper_bound         : otherwise; the contact deadline is an upper bound on the full-policy deadline, and the full
                        checker's verdict on the witness is reported (pass = the deadline is attained by a checked
                        route; fail = the true full-policy deadline is earlier and is NOT computed here).
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set, witness_greedy  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from deadline_field.verify import full_check  # noqa: E402


def run(graph: Path, packet: Path, instance: dict, *, verify=True, step=1800):
    t_all = time.perf_counter()
    t0 = time.perf_counter()
    pm = PacketModel(graph, packet)
    hazard = json.loads((packet / "HAZARD.json").read_text()) if verify else None
    prep = time.perf_counter() - t0
    H = pm.H
    peak_l, dose_l = instance["limits"]["peak_kw_m2"], instance["limits"]["dose_kj_m2"]
    if hazard is None:
        hazard = json.loads((packet / "HAZARD.json").read_text())
    ok, pre = pm.full_policy_reduces_to_contact(hazard, peak_limit=peak_l, dose_limit=dose_l, incurred=0.0)
    max_dur = pre["max_exact_journey_duration_s"]
    offsets = list(range(0, H + 1, step))
    window = [0, H]
    specs = {}
    for o in instance["origins"]:
        for d in o["destinations"]:
            specs.setdefault((d["node"], d["dwell_s"]), set()).add(o["entry_node"])
    feas = {}
    tm = Counter()
    pieces = Counter()
    checks = []
    for (dnode, dwell), origins in sorted(specs.items()):
        for var in ("cert", "free"):
            t1 = time.perf_counter()
            inst = pm.instance(var, [{"node": dnode, "dwell": dwell, "window": window}], sorted(origins))
            fld = backward(inst)
            tm["field_" + var] += time.perf_counter() - t1
            multi = [len(x) for x in fld.R if len(x) > 1]
            pieces[var + ":states_nonempty"] += sum(1 for x in fld.R if x)
            pieces[var + ":states_multi_interval"] += len(multi)
            pieces[var + ":max_intervals_per_state"] = max(pieces[var + ":max_intervals_per_state"], max(multi, default=1))
            for o in origins:
                feas[(var, dnode, o)] = issue_set(fld, pm.nidx[o])
            if var == "cert" and verify:
                t2 = time.perf_counter()
                for o in sorted(origins):
                    f = feas[("cert", dnode, o)]
                    if not f:
                        continue
                    ld = f[-1][1]
                    w = witness_greedy(fld, pm.nidx[o], ld)   # feasible witness; arrival not necessarily earliest
                    legs = [(k, (pm.g.edge_ids[x] if k == "EDGE" else pm.node_ids[x]), a, b) for k, x, a, b in w[1]]
                    dur = (w[0] + dwell) - ld
                    chk = full_check(pm, hazard, origin=o, legs=legs, dest=dnode, dwell=dwell, window=window,
                                     departure=ld, incurred=0.0, peak=peak_l, dose=dose_l)
                    exact = bool(pre["peak_cannot_bind_off_flame"] and max_dur is not None and dur <= max_dur)
                    checks.append({"origin": o, "dest": dnode, "deadline_s": ld, "arrival": w[0], "duration_s": dur,
                                   "exact_full_policy": exact, "next_second_infeasible": not iv.contains(f, ld + 1),
                                   **chk})
                tm["verify"] += time.perf_counter() - t2
    origins_out = {}
    cls = Counter()
    for o in instance["origins"]:
        e = o["entry_node"]
        row = {"origin_id": o["origin_id"], "entry_node": e, "type": o.get("origin_type")}
        for var in ("cert", "free"):
            sets = [feas[(var, d["node"], e)] for d in o["destinations"]]
            union = iv.normalize([p for s in sets for p in s])
            row["exact_" + var] = union[-1][1] if union else None
            g = [t for t in offsets if iv.contains(union, t)]
            row["grid_" + var] = g[-1] if g else None
            row["holes_" + var] = len(union) > 1 or (bool(union) and union[0][0] > 0)
            row["union_" + var] = union
        if row["exact_cert"] is None:
            c = "no_checked_departure"
        elif row["exact_cert"] == row["exact_free"]:
            c = "window_set"
        else:
            c = "fire_set"
        row["class"] = c
        cls[c] += 1
        origins_out[o["origin_id"]] = row
    wc = Counter()
    for c in checks:
        wc[("exact" if c["exact_full_policy"] else "upper_bound") + ":" +
           ("PASS" if (c["full_policy_ok"] and c["closed_and_router_replay_clear"]) else "FAIL:" + ",".join(c["codes"]))] += 1
        wc["next_second_infeasible:" + str(c["next_second_infeasible"])] += 1
    diffs = [r["exact_cert"] - r["grid_cert"] for r in origins_out.values() if r["grid_cert"] is not None]
    bs = Path(packet) / "BUILD_SUMMARY.json"
    bsd = json.loads(bs.read_text()) if bs.exists() else {}
    writer = {k: bsd.get(k) for k in ("packet_writer_sha256", "support_writer")}   # F-9.3: part of the instance key
    return {"schema": "wfg.f31.fdyn/1", "packet": str(packet), "graph": str(graph), "H": H, "writer_identity": writer,
            "label": "SCENARIO (F-DYN v3), not what happened; roads limited to the recorded windows",
            "precondition": pre, "destinations": len(specs), "origins": len(origins_out),
            "classes": dict(cls), "witness_checks": dict(wc), "pieces": dict(pieces),
            "exact_minus_grid_s": {"n": len(diffs), "median": sorted(diffs)[len(diffs) // 2] if diffs else None,
                                   "max": max(diffs) if diffs else None, "n_positive": sum(d > 0 for d in diffs)},
            "holes_cert": sum(r["holes_cert"] for r in origins_out.values()),
            "timing_s": {"prepare": prep, **dict(tm), "total": time.perf_counter() - t_all},
            "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0,
            "origins_detail": origins_out, "checks": checks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", type=Path, required=True)
    ap.add_argument("--packet", type=Path, required=True)
    ap.add_argument("--instance-json", type=Path, required=True)
    ap.add_argument("--region", required=True)
    ap.add_argument("--start", required=True, help="start tag; origins/destinations are the region's (start-independent)")
    ap.add_argument("--horizon-s", type=int, required=True)
    ap.add_argument("--no-verify", action="store_true")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    doc = json.loads(a.instance_json.read_text())
    cand = [i for i in doc["instances"] if i["region"] == a.region and i["horizon_s"] == a.horizon_s]
    inst = next((i for i in cand if i["start_tag"] == a.start), cand[0])
    out = run(a.graph, a.packet, inst, verify=not a.no_verify)
    out["instance_entry"] = {"region": inst["region"], "start_tag": inst["start_tag"], "horizon_s": inst["horizon_s"]}
    a.out.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("destinations", "origins", "classes", "witness_checks", "pieces",
                                           "exact_minus_grid_s", "holes_cert", "timing_s", "peak_rss_mib")}, indent=1))


if __name__ == "__main__":
    main()
