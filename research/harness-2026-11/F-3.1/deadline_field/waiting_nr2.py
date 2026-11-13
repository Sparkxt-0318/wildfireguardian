"""WAITING_NR2_RULE.md: waiting-location sensitivity on one /2 HEADLINE packet. Default arm (supplied graph rule)
vs sensitivity arm (waitable_all), CERT and ROUTER, one field in memory at a time.
    python3 -m deadline_field.waiting_nr2 --graph G --packet P --instance-json I --region R --start S --horizon-s HS
        --variant V --summary results/HEADLINE_NR2_summary.json --out OUT"""
from __future__ import annotations
import argparse, gc, json, resource, sys, time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set, witness_greedy  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from deadline_field.verify import full_check  # noqa: E402

STEP = 1800
LABEL = "SENSITIVITY: waiting allowed at every node (not the supplied graph rule)"


def rss_mib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


def fields(graph, packet, specs, waitable_all):
    pm = PacketModel(graph, packet, waitable_all=waitable_all)
    H = pm.H
    feas = {}
    for var in ("cert", "router"):
        for (dn, dw), origins in sorted(specs.items()):
            fld = backward(pm.instance(var, [{"node": dn, "dwell": dw, "window": [0, H]}], sorted(origins)))
            for o in origins:
                feas[(var, dn, dw, o)] = [tuple(p) for p in issue_set(fld, pm.nidx[o])]
            del fld
    del pm
    gc.collect()
    return feas, H


def place_lb(feas, var, o):
    e = o["entry_node"]
    u = iv.normalize([p for d in o["destinations"] for p in feas[(var, d["node"], d["dwell_s"], e)]])
    return u[-1][1] if u and u[0][0] == 0 else None, u


def main():
    ap = argparse.ArgumentParser()
    for k in ("graph", "packet", "instance-json", "region", "start", "horizon-s", "variant", "summary", "out"):
        ap.add_argument("--" + k, required=True)
    a = ap.parse_args()
    t0 = time.perf_counter()
    doc = json.loads(Path(a.instance_json).read_text())
    inst = next(i for i in doc["instances"] if i["region"] == a.region and i["horizon_s"] == int(a.horizon_s)
                and i["start_tag"] == a.start)
    h = int(a.horizon_s) // 3600
    summ = {p["origin"]: p for p in json.loads(Path(a.summary).read_text())["places"]
            if p["region"] == a.region and p["start"] == a.start and p["horizon_h"] == h}
    specs = {}
    for o in inst["origins"]:
        for d in o["destinations"]:
            specs.setdefault((d["node"], d["dwell_s"]), set()).add(o["entry_node"])
    peak, timing = {}, {}
    t1 = time.perf_counter(); f0, H = fields(a.graph, a.packet, specs, False); peak["default"] = rss_mib(); timing["default_s"] = time.perf_counter() - t1
    t1 = time.perf_counter(); f1, _ = fields(a.graph, a.packet, specs, True); peak["after_all"] = rss_mib(); timing["all_s"] = time.perf_counter() - t1
    faults, grid_tab, control_mism = [], Counter(), []
    # exact containment check per destination unit: every default interval inside the sensitivity set
    for k in f0:
        for lo, hi in f0[k]:
            u = iv.normalize(f1[k])
            if not any(a_ <= lo and hi <= b_ for a_, b_ in u):
                faults.append({"unit": list(k), "default_interval": [lo, hi], "sensitivity_set": u})
        for t in range(0, H + 1, STEP):
            grid_tab["%s:%s->%s" % (k[0], "feasible" if iv.contains(f0[k], t) else "infeasible",
                                    "feasible" if iv.contains(f1[k], t) else "infeasible")] += 1
    rows, cnt, shifts = [], Counter(), {"cert": [], "router": []}
    need = {}
    for o in inst["origins"]:
        for var in ("cert", "router"):
            lb0, _ = place_lb(f0, var, o)
            lb1, _ = place_lb(f1, var, o)
            sp = summ[o["origin_id"]]["nr_" + var]["per_variant"][a.variant] if a.variant != "envelope_burnset" else \
                {"leave_by_s": (summ[o["origin_id"]].get("static_final_footprint_row") or {}).get("nr_" + var)}
            want = sp.get("leave_by_s") if isinstance(sp, dict) else None
            if lb0 != want:
                control_mism.append({"origin": o["origin_id"], "field": var, "default": lb0, "committed": want})
            if lb0 == lb1:
                dep = "no"
            elif lb0 is None:
                dep = "yes: route only with waiting allowed everywhere"
            elif lb1 is not None and lb1 > lb0:
                dep = "yes: leave-by later by %d s with waiting allowed everywhere" % (lb1 - lb0)
                shifts[var].append(lb1 - lb0)
            else:
                dep = "FAULT: earlier or lost with waiting allowed everywhere"
            cls = ("no" if dep == "no" else "route_only" if dep.startswith("yes: route only") else
                   "leave_by_later" if dep.startswith("yes: leave-by later") else "FAULT")
            cnt["%s:%s" % (var, cls)] += 1
            if cls == "FAULT":
                faults.append({"place_unit": [o["origin_id"], var], "default": lb0, "all": lb1})
            rows.append({"origin": o["origin_id"], "field": var, "leave_by_default": lb0, "leave_by_all": lb1,
                         "depends_on_waiting_rule": dep})
            if lb1 is not None and lb1 != lb0:
                for d in o["destinations"]:
                    if iv.contains(f1[(var, d["node"], d["dwell_s"], o["entry_node"])], lb1):
                        need.setdefault((var, d["node"], d["dwell_s"]), []).append((o, lb1))
                        break
    # witnesses for changed place units, sensitivity arm (one field at a time)
    wc = Counter()
    if need:
        pm = PacketModel(a.graph, a.packet, waitable_all=True)
        hz = json.loads((Path(a.packet) / "HAZARD.json").read_text())
        pl, dl = inst["limits"]["peak_kw_m2"], inst["limits"]["dose_kj_m2"]
        for (var, dn, dw), lst in sorted(need.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
            fld = backward(pm.instance(var, [{"node": dn, "dwell": dw, "window": [0, H]}], sorted(specs[(dn, dw)])))
            for o, lb1 in lst:
                e = o["entry_node"]
                w = witness_greedy(fld, pm.nidx[e], lb1)
                legs = [(k, (pm.g.edge_ids[x] if k == "EDGE" else pm.node_ids[x]), s_, t_) for k, x, s_, t_ in w[1]]
                c = full_check(pm, hz, origin=e, legs=legs, dest=dn, dwell=dw, window=[0, H], departure=lb1,
                               incurred=0.0, peak=pl, dose=dl)
                ok = c["full_policy_ok"] and c["closed_and_router_replay_clear"]
                nxt = not iv.contains(issue_set(fld, pm.nidx[e]), lb1 + 1)
                wc["%s:%s" % (var, "PASS" if ok else "FAIL")] += 1
                wc["%s:next_second_infeasible:%s" % (var, nxt)] += 1
            del fld
        del pm
    peak["final"] = rss_mib()
    out = {"what": "waiting sensitivity on the /2 HEADLINE field (WAITING_NR2_RULE.md)", "label": LABEL,
           "region": a.region, "start": a.start, "horizon_h": h, "variant": a.variant, "H": H,
           "control_mismatches": control_mism, "faults": faults, "grid_verdicts": dict(grid_tab),
           "place_counts": dict(cnt), "shifts_s": shifts, "witness_checks": dict(wc), "rows": rows,
           "peak_rss_mib": peak, "timing_s": timing, "wall_s": time.perf_counter() - t0}
    Path(a.out).write_text(json.dumps(out))
    print(json.dumps({k: out[k] for k in ("place_counts", "witness_checks", "peak_rss_mib")} |
                     {"faults": len(faults), "control_mismatches": len(control_mism)}))


if __name__ == "__main__":
    main()
