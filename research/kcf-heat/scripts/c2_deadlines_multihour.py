"""C.2 / C.3 (multi-hour): F-3.1 HEADLINE leave-bys on one F-DYN no_reentry/2 packet, without and with heat, and with
the TDU budget enforced inside the field.

Same inputs as deadline_field/headline.py (MULTIHOUR_HEADLINE_RULE.md): the interim full-grid graph, the no_reentry/2
packet, INSTANCE.json (F-DYN fdyn/instance.py). The reopening packet is not used (no witness check against it here).

    python scripts/c2_deadlines_multihour.py --graph G --nr-packet P --instance-json I --region R --start S \
        --horizon-s H --variant V --out OUT.json [--reference HEADLINE_NR2_summary.json] [--budgets 92,105,290]

Per destination (node, dwell), window [0, H], fields:
  free       no fire (control: a leave-by equal to free is horizon-censored);
  cert       router OR closed footprint (F-3.1's headline field; checked against --reference per place);
  cert_heat  cert OR the heat rule (C.1);
  tdu        cert_heat AND dose <= budget (kcf_heat/tdu_field.py), one field at the largest budget, read at every budget.
Leave-by per origin = latest second of the union over its destinations of the feasible departure set, when that set
starts at 0 (headline.py's rule); a union that does not start at 0 has no leave-by.
Every per-(origin, destination) TDU deadline gets a witness, replayed against the cert_heat masks and bounded by the
independent sampled dose check (kcf_heat/dose_check.py); the next second must be infeasible.
"""
import argparse
import gc
import json
import resource
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from kcf_heat.closure import HeatPacketModel, HeatRule, iv  # noqa: E402
from kcf_heat.dose import Q0_KW_M2, DoseModel  # noqa: E402
from kcf_heat.dose_check import DoseBounds  # noqa: E402
from kcf_heat.tdu_field import INF, issue_core_values, ModelCosts, feasible_set, issue_values, tdu_backward, witness_tdu  # noqa: E402
from deadline_field.core import backward, issue_set  # noqa: E402


def replay_contact(inst, o, t, legs, arr):
    """The journey is legal under the instance's masks (independent of both fields)."""
    if iv.contains(iv.normalize(inst.IB.get(o, [])), t):
        return "issue_blocked"
    if not legs:
        return None if iv.contains(inst.AN.get(o, []), t) and arr == t else "bad_empty"
    node, inc, now, adm = o, None, t, False
    for kind, x, a, b in legs:
        if a != now:
            return "time_gap"
        if kind == "EDGE":
            if inst.tail[x] != node or (inc is not None and (inc, x) in inst.forbidden):
                return "bad_edge"
            if b != a + inst.D[x] or iv.contains(inst.B[x], a) or b > inst.H:
                return "edge_blocked"
            node, inc, now, adm = inst.head[x], x, b, True
        else:
            if x != node or not inst.waitable[node] or iv.contains(inst.W[node], a) or b != a + 1:
                return "wait_blocked"
            now, adm = b, False
    if not (adm and now == arr and iv.contains(inst.A[inc], arr)):
        return "not_accepted"
    return None


def leave_by(sets):
    u = iv.normalize([p for s in sets for p in s])
    return (u[-1][1] if u and u[0][0] == 0 else None), u


def main():
    ap = argparse.ArgumentParser()
    for k in ("--graph", "--nr-packet", "--instance-json", "--out"):
        ap.add_argument(k, type=Path, required=True)
    ap.add_argument("--reference", type=Path)
    ap.add_argument("--region", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--horizon-s", type=int, required=True)
    ap.add_argument("--variant", required=True)
    ap.add_argument("--budgets", default="92,105,290")
    ap.add_argument("--q0", type=float, default=Q0_KW_M2)
    ap.add_argument("--dwell-dose", choices=("count", "exclude"), default="count",
                    help="count the destination dwell in the budget (router dose span) or exclude it (stay indoors)")
    ap.add_argument("--limit-specs", type=int)
    a = ap.parse_args()
    t_all = time.perf_counter()
    tm = Counter()
    doc = json.loads(a.instance_json.read_text())
    inst_e = next(i for i in doc["instances"] if i["region"] == a.region and i["horizon_s"] == a.horizon_s
                  and i["start_tag"] == a.start)
    rule = HeatRule()
    t0 = time.perf_counter()
    pm = HeatPacketModel(a.graph, a.nr_packet, heat=rule)
    if pm.H != a.horizon_s:
        raise SystemExit("packet horizon %d != --horizon-s %d" % (pm.H, a.horizon_s))
    dm = DoseModel(pm, rule, q0=a.q0)
    ob = DoseBounds(dm)
    tm["prepare"] = time.perf_counter() - t0
    budgets = [float(x) for x in a.budgets.split(",")]
    dwell_dose = a.dwell_dose
    bq = {b: dm.quanta(b) for b in budgets}
    bmax = max(bq.values())
    window = [0, pm.H]
    specs = {}
    for o in inst_e["origins"]:
        for d in o["destinations"]:
            specs.setdefault((d["node"], d["dwell_s"]), set()).add(o["entry_node"])
    spec_list = sorted(specs)[: a.limit_specs] if a.limit_specs else sorted(specs)
    feas, wit = {}, Counter()
    wit_rows = []
    fstats = Counter()
    for dn, dw in spec_list:
        origins = sorted(specs[(dn, dw)])
        dests = [{"node": dn, "dwell": dw, "window": window}]
        for var in ("free", "cert", "cert_heat"):
            t1 = time.perf_counter()
            inst = pm.instance(var, dests, origins)
            fld = backward(inst)
            tm["field_" + var] += time.perf_counter() - t1
            for o in origins:
                feas[(var, dn, dw, o)] = issue_set(fld, pm.nidx[o])
            del fld
        t1 = time.perf_counter()
        costs = ModelCosts(dm, {pm.nidx[dn]: dw} if dwell_dose == "count" else {})
        fld = tdu_backward(inst, costs, bmax)
        tm["field_tdu"] += time.perf_counter() - t1
        for k, v in fld.stats.items():
            fstats[k] += v
        t2 = time.perf_counter()
        for o in origins:
            oi = pm.nidx[o]
            core = issue_core_values(fld, oi)
            vals = issue_values(fld, oi, core)
            for b in budgets:
                f = feasible_set(vals, bq[b])
                feas[("tdu%g" % b, dn, dw, o)] = f
                if not f:
                    continue
                ld = f[-1][1]
                w = witness_tdu(fld, oi, ld, values=vals, core=core)
                err = replay_contact(inst, oi, ld, w[2], w[1])
                lo, hi, secs = ob.route(w[2], dn, w[1], dw if dwell_dose == "count" else 0)
                V = w[0] * dm.quantum
                ok_dose = lo - 1e-6 <= V <= hi + secs * dm.quantum + 1e-6 and V <= b + 1e-9
                nxt = ld + 1 > pm.H or vals[ld + 1] > bq[b]
                wit["checked"] += 1
                wit["contact_ok" if err is None else "contact_FAIL:" + err] += 1
                wit["dose_within_independent_bounds" if ok_dose else "dose_bounds_FAIL"] += 1
                wit["next_second_infeasible" if nxt else "next_second_FEASIBLE"] += 1
                wit_rows.append({"origin": o, "dest": dn, "budget": b, "deadline_s": ld, "arrival": w[1],
                                 "dose_tdu": V, "independent_lower": lo, "independent_upper": hi})
        tm["tdu_issue_and_witness"] += time.perf_counter() - t2
        del fld, inst
        gc.collect()
    vars_ = ["free", "cert", "cert_heat"] + ["tdu%g" % b for b in budgets]
    rows, nonprefix = {}, Counter()
    for o in inst_e["origins"]:
        e = o["entry_node"]
        ds = [d for d in o["destinations"] if (d["node"], d["dwell_s"]) in spec_list]
        if not ds:
            continue
        r = {"entry_node": e, "type": o.get("origin_type")}
        for var in vars_:
            sets = [feas[(var, d["node"], d["dwell_s"], e)] for d in ds]
            lb, u = leave_by(sets)
            r["leave_by_" + var] = lb
            if u and not (len(u) == 1 and u[0][0] == 0):
                nonprefix[var] += 1
        r["censored_at_horizon"] = r["leave_by_cert"] is not None and r["leave_by_cert"] == r["leave_by_free"]
        rows[o["origin_id"]] = r
    ref = None
    if a.reference:
        R = json.loads(a.reference.read_text())
        ref = {}
        for p in R["places"]:
            if p["region"] == a.region and p["start"] == a.start and p["horizon_h"] * 3600 == a.horizon_s:
                if a.variant == "envelope_burnset":
                    ref[p["origin"]] = p["static_final_footprint_row"]["nr_cert"]
                else:
                    ref[p["origin"]] = p["nr_cert"]["per_variant"].get(a.variant, {}).get("leave_by_s")
    repro = Counter()
    for oid, r in rows.items():
        if ref is not None and oid in ref:
            repro["match" if ref[oid] == r["leave_by_cert"] else "MISMATCH"] += 1
            r["reference_leave_by_cert"] = ref[oid]

    def compare(x, y):
        c = Counter(); shifts = []
        for r in rows.values():
            p, q = r["leave_by_" + x], r["leave_by_" + y]
            if p is None and q is None:
                c["both_none"] += 1
            elif p is not None and q is None:
                c["lost_route"] += 1
            elif p is None:
                c["GAINED_route"] += 1
            elif q < p:
                c["moved_earlier"] += 1; shifts.append(p - q)
            elif q > p:
                c["MOVED_LATER"] += 1
            else:
                c["unchanged"] += 1
        shifts.sort()
        return {**dict(c), "shift_s": shifts}

    out = {"schema": "kcf-heat.multihour/2", "region": a.region, "start": a.start, "H": pm.H, "variant": a.variant,
           "transform": "no_reentry/2", "packet": str(a.nr_packet),
           "label": "SCENARIO (F-DYN), not what happened; roads limited to the recorded windows; exact = exact for the "
                    "time-dependent model's field, not for the fire",
           "heat_rule": rule.describe(), "q0_kw_m2": a.q0, "dwell_dose": dwell_dose, "budgets_tdu": budgets, "quantum_tdu": dm.quantum,
           "dose_model": {"members": pm.pk.S, "burning_cells": len(pm.burning), **dm.stats},
           "specs": len(spec_list), "origins": len(rows), "reference_cert_reproduction": dict(repro),
           "nonprefix_feasible_unions": dict(nonprefix),
           "compare": {"cert->cert_heat": compare("cert", "cert_heat"),
                       **{"cert_heat->tdu%g" % b: compare("cert_heat", "tdu%g" % b) for b in budgets},
                       **{"cert->tdu%g" % b: compare("cert", "tdu%g" % b) for b in budgets}},
           "witness_checks": dict(wit), "tdu_field_stats": dict(fstats),
           "timing_s": {**dict(tm), "total": time.perf_counter() - t_all},
           "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0 / 1024.0,
           "origins_detail": rows, "tdu_witnesses": wit_rows}
    a.out.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("region", "start", "H", "variant", "origins", "reference_cert_reproduction",
                                          "witness_checks", "timing_s")}
                     | {"compare": {k: {kk: vv for kk, vv in v.items() if kk != "shift_s"}
                                    for k, v in out["compare"].items()}}), flush=True)


if __name__ == "__main__":
    main()
