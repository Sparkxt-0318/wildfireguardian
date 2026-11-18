"""C.3 enforced (1-hour panel): the F-3.1 deadline field with the heat rule AND a thermal-dose budget inside the search.

For each recorded planner cache: one cert_heat field (F-3.1 core) and one TDU field (kcf_heat/tdu_field.py, at the
largest budget, read at every budget) per destination spec (node, dwell, window), the same specs and origins as
F-3.1's reproduce.run. Per origin, the exact 1-s planner deadline (latest feasible departure in the planner's range
[0, last offset], over the origin's recorded (start, destination) pairs) and the 10-min grid deadline (latest recorded
offset whose attempt is feasible), for cert_heat and for each budget.

Every per-(start, destination) TDU deadline inside the planner range gets a witness, replayed against the cert_heat
masks and bounded by the independent sampled dose check; the next second must be infeasible.

    python scripts/c4_tdu_1h.py --data-root DATA/routing --out-dir DIR [--budgets 92,105,290] [--q0 1.42] CACHE...
"""
import argparse
import json
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "scripts"))
from kcf_heat.closure import ROOT, HeatPacketModel, HeatRule, iv  # noqa: E402
from kcf_heat.dose import Q0_KW_M2, DoseModel  # noqa: E402
from kcf_heat.dose_check import DoseBounds  # noqa: E402
from kcf_heat.tdu_field import issue_core_values, ModelCosts, feasible_set, issue_values, tdu_backward, witness_tdu  # noqa: E402
from c2_deadlines_multihour import replay_contact  # noqa: E402
from deadline_field.core import backward, issue_set  # noqa: E402
from tools.explain_deadlines.plans import CacheModel  # noqa: E402


def capped_latest(feas, last):
    m = [hi if hi <= last else (last if lo <= last else None) for lo, hi in feas]
    m = [x for x in m if x is not None]
    return max(m) if m else None


def run(cache: Path, data_root: Path, budgets, q0, dwell_dose="count"):
    t_all = time.perf_counter()
    tm = Counter()
    doc = json.loads(cache.read_text())
    region, input_time = doc["region_id"], doc["input_time"]
    compact = input_time.replace("-", "").replace(":", "")
    model = CacheModel(doc)
    rule = HeatRule()
    t0 = time.perf_counter()
    pm = HeatPacketModel(data_root / "graphs" / region / "graph.json",
                         data_root / "latest_inputs_try02" / "packets" / region / compact, heat=rule)
    dm = DoseModel(pm, rule, q0=q0)
    ob = DoseBounds(dm)
    tm["prepare"] = time.perf_counter() - t0
    bq = {b: dm.quanta(b) for b in budgets}
    bmax = max(bq.values())
    rows = []
    for oid, plan in model.plans.items():
        for cell in plan.sweep:
            for a in cell.attempts:
                job = model.job(a.job_id)
                if job is None:
                    continue
                q = job["request"]
                rows.append({"origin_id": oid, "offset": int(a.offset_s), "start": q["start"]["node_id"],
                             "spec": (q["destination"]["node_id"], q["dwell_s"], tuple(q["destination_window"]))})
    for key, job in sorted((doc.get("route_checks") or {}).items()):     # every route-check job, as reproduce.run
        q = job["request"]
        rows.append({"origin_id": None, "offset": int(q["depart_offset_s"]), "start": q["start"]["node_id"],
                     "spec": (q["destination"]["node_id"], q["dwell_s"], tuple(q["destination_window"]))})
    specs = defaultdict(set)
    for r in rows:
        specs[r["spec"]].add(r["start"])
    vars_ = ["cert_heat"] + ["tdu%g" % b for b in budgets]
    feas = {}
    wit = Counter()
    fstats = Counter()
    last_of = {oid: max((c.offset_s for c in plan.sweep), default=0) for oid, plan in model.plans.items()}
    # reproduce.run's per-origin rule: every (destination spec, start) combination of the origin's attempts
    combos = defaultdict(set)
    for oid in model.plans:
        rs = [r for r in rows if r["origin_id"] == oid]
        combos[oid] = {(sp, st) for sp in {r["spec"] for r in rs} for st in {r["start"] for r in rs}
                       if st in specs[sp]}
    lasts_by = defaultdict(set)              # (spec, start) -> planner ranges that read it
    for oid, cs in combos.items():
        for c in cs:
            lasts_by[c].add(last_of[oid])
    for spec in sorted(specs, key=str):
        dn, dw, win = spec
        origins = sorted(specs[spec])
        t1 = time.perf_counter()
        inst = pm.instance("cert_heat", [{"node": dn, "dwell": dw, "window": list(win)}], origins)
        ref = backward(inst)
        tm["field_cert_heat"] += time.perf_counter() - t1
        t1 = time.perf_counter()
        fld = tdu_backward(inst, ModelCosts(dm, {pm.nidx[dn]: dw} if dwell_dose == "count" else {}), bmax)
        tm["field_tdu"] += time.perf_counter() - t1
        for k, v in fld.stats.items():
            fstats[k] += v
        t2 = time.perf_counter()
        for o in origins:
            oi = pm.nidx[o]
            feas[("cert_heat", spec, o)] = issue_set(ref, oi)
            core = issue_core_values(fld, oi)
            vals = issue_values(fld, oi, core)
            for b in budgets:
                f = feasible_set(vals, bq[b])
                feas[("tdu%g" % b, spec, o)] = f
                for last in lasts_by.get((spec, o), ()):
                    ld = capped_latest(f, last)
                    if ld is None:
                        continue
                    w = witness_tdu(fld, oi, ld, values=vals, core=core)
                    err = replay_contact(inst, oi, ld, w[2], w[1])
                    lo, hi, secs = ob.route(w[2], dn, w[1], dw if dwell_dose == "count" else 0)
                    V = w[0] * dm.quantum
                    wit["checked"] += 1
                    wit["contact_ok" if err is None else "contact_FAIL:" + err] += 1
                    ok = lo - 1e-6 <= V <= hi + secs * dm.quantum + 1e-6 and V <= b + 1e-9
                    wit["dose_within_independent_bounds" if ok else "dose_bounds_FAIL"] += 1
                    nxt = ld == last or ld + 1 > pm.H or vals[ld + 1] > bq[b]
                    wit["next_second_infeasible_or_range_end" if nxt else "next_second_FEASIBLE"] += 1
            # the field without any budget binding must equal cert_heat (a second with m <= max budget is a subset)
            if iv.subtract_all(feas[("tdu%g" % max(budgets), spec, o)], feas[("cert_heat", spec, o)]):
                wit["TDU_SET_NOT_SUBSET_OF_CERT_HEAT"] += 1
        tm["issue_and_witness"] += time.perf_counter() - t2
        del fld, ref, inst
    per_origin = {}
    by_origin = defaultdict(list)
    for r in rows:
        if r["origin_id"] is not None:
            by_origin[r["origin_id"]].append(r)
    for oid, rs in by_origin.items():
        last = last_of[oid]
        o = {"recorded_deadline": model.plans[oid].latest_s, "kind": model.plans[oid].kind}
        for var in vars_:
            ok_offs = sorted({r["offset"] for r in rs if iv.contains(feas[(var, r["spec"], r["start"])], r["offset"])})
            o["grid_" + var] = ok_offs[-1] if ok_offs else None
            best = None
            for spec, st in combos[oid]:
                x = capped_latest(feas[(var, spec, st)], last)
                if x is not None and (best is None or x > best):
                    best = x
            o["exact_" + var] = best
        per_origin[oid] = o
    return {"schema": "kcf-heat.tdu-1h/1", "cache_file": str(cache.relative_to(ROOT)) if cache.is_relative_to(ROOT) else str(cache),
            "region": region, "input_time": input_time, "H": pm.H, "heat_rule": rule.describe(), "q0_kw_m2": q0, "dwell_dose": dwell_dose,
            "budgets_tdu": budgets, "quantum_tdu": dm.quantum,
            "dose_model": {"members": pm.pk.S, "burning_cells": len(pm.burning), **dm.stats},
            "specs": len(specs), "witness_checks": dict(wit), "tdu_field_stats": dict(fstats),
            "timing_s": {**dict(tm), "total": time.perf_counter() - t_all},
            "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0 / 1024.0,
            "origins": per_origin}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("caches", nargs="+", type=Path)
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--budgets", default="92,105,290")
    ap.add_argument("--q0", type=float, default=Q0_KW_M2)
    ap.add_argument("--dwell-dose", choices=("count", "exclude"), default="count",
                    help="count the destination dwell in the budget (router dose span) or exclude it (stay indoors)")
    a = ap.parse_args()
    budgets = [float(x) for x in a.budgets.split(",")]
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for cache in a.caches:
        out = run(cache.resolve(), a.data_root, budgets, a.q0, a.dwell_dose)
        tag = "%s__%s__q0_%g__dwell_%s" % (out["region"], out["input_time"].replace(":", "").replace("-", ""), a.q0, a.dwell_dose)
        (a.out_dir / (tag + ".tdu.json")).write_text(json.dumps(out, indent=1, default=str))
        print(tag, json.dumps({k: out[k] for k in ("specs", "witness_checks", "timing_s")}), flush=True)


if __name__ == "__main__":
    main()
