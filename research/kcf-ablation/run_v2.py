"""N2 (LAYOUT.md section 6): the V2 six-cache 1-hour panel under one changed arm, same code path as kcf-heat C.4.

Copy of research/kcf-heat/scripts/c4_tdu_1h.py::run without the witness pass, with one switch:

  --arm full         cert_heat + dose <= budget                      (reproduction check against kcf-heat/data/tdu_1h)
  --arm persistence  full, packet reduced to fire already burning     (row 2)
  --arm heat_off     cert masks + dose <= budget (no heat closure)    (row 4)

Per origin: exact 1-s leave-by (latest feasible departure in the planner range [0, last offset], over the origin's
recorded (start, destination) pairs) at each budget, and the 10-min grid value. Dwell counted (router span), q0 1.42.

    python run_v2.py --data-root DATA/routing --out-dir DIR --arm ARM CACHE...
"""
import argparse
import json
import platform
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KH = ROOT / "research" / "kcf-heat"
sys.path.insert(0, str(KH))
sys.path.insert(0, str(KH / "scripts"))
from kcf_heat.closure import HeatPacketModel, HeatRule, iv  # noqa: E402
from kcf_heat.dose import Q0_KW_M2, DoseModel  # noqa: E402
from kcf_heat.tdu_field import ModelCosts, feasible_set, issue_core_values, issue_values, tdu_backward  # noqa: E402
from deadline_field.core import backward, issue_set  # noqa: E402
from tools.explain_deadlines.plans import CacheModel  # noqa: E402
from c4_tdu_1h import capped_latest  # noqa: E402


def run(cache: Path, data_root: Path, arm: str, budgets=(92.0, 105.0, 290.0), with_cert=False):
    t_all = time.perf_counter()
    tm = Counter()
    doc = json.loads(cache.read_text())
    region, input_time = doc["region_id"], doc["input_time"]
    compact = input_time.replace("-", "").replace(":", "")
    model = CacheModel(doc)
    rule = HeatRule()
    t0 = time.perf_counter()
    pm = HeatPacketModel(data_root / "graphs" / region / "graph.json",
                         data_root / "latest_inputs_try02" / "packets" / region / compact, heat=rule,
                         present_only=(arm == "persistence"))
    dm = DoseModel(pm, rule, q0=Q0_KW_M2)
    tm["prepare"] = time.perf_counter() - t0
    bq = {b: dm.quanta(b) for b in budgets}
    bmax = max(bq.values())
    variant = "cert" if arm == "heat_off" else "cert_heat"
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
    jobs = []
    for key, job in sorted((doc.get("route_checks") or {}).items()):
        q = job["request"]
        r = {"origin_id": None, "offset": int(q["depart_offset_s"]), "start": q["start"]["node_id"],
             "spec": (q["destination"]["node_id"], q["dwell_s"], tuple(q["destination_window"]))}
        rows.append(r)
        jobs.append(r)
    specs = defaultdict(set)
    for r in rows:
        specs[r["spec"]].add(r["start"])
    feas = {}
    last_of = {oid: max((c.offset_s for c in plan.sweep), default=0) for oid, plan in model.plans.items()}
    combos = defaultdict(set)
    for oid in model.plans:
        rs = [r for r in rows if r["origin_id"] == oid]
        combos[oid] = {(sp, st) for sp in {r["spec"] for r in rs} for st in {r["start"] for r in rs} if st in specs[sp]}
    for spec in sorted(specs, key=str):
        dn, dw, win = spec
        origins = sorted(specs[spec])
        inst = pm.instance(variant, [{"node": dn, "dwell": dw, "window": list(win)}], origins)
        t1 = time.perf_counter()
        ref = backward(inst)
        tm["field_masks_only"] += time.perf_counter() - t1
        t1 = time.perf_counter()
        fld = tdu_backward(inst, ModelCosts(dm, {pm.nidx[dn]: dw}), bmax)
        tm["field_tdu"] += time.perf_counter() - t1
        for o in origins:
            oi = pm.nidx[o]
            feas[(variant, spec, o)] = issue_set(ref, oi)
            vals = issue_values(fld, oi, issue_core_values(fld, oi))
            for b in budgets:
                f = feasible_set(vals, bq[b])
                feas[("tdu%g" % b, spec, o)] = f
            if iv.subtract_all(feas[("tdu%g" % max(budgets), spec, o)], feas[(variant, spec, o)]):
                raise SystemExit("TDU set not a subset of the mask-only set")
        if with_cert:
            refc = backward(pm.instance("cert", [{"node": dn, "dwell": dw, "window": list(win)}], origins))
            for o in origins:
                feas[("cert", spec, o)] = issue_set(refc, pm.nidx[o])
            del refc
        del fld, ref, inst
    job_feasible = Counter()
    for r in jobs:
        for var in [variant] + ["tdu%g" % b for b in budgets] + (["cert"] if with_cert else []):
            job_feasible[var] += bool(iv.contains(feas[(var, r["spec"], r["start"])], r["offset"]))
    per_origin = {}
    by_origin = defaultdict(list)
    for r in rows:
        if r["origin_id"] is not None:
            by_origin[r["origin_id"]].append(r)
    for oid, rs in by_origin.items():
        last = last_of[oid]
        o = {"recorded_deadline": model.plans[oid].latest_s, "kind": model.plans[oid].kind}
        for var in [variant] + ["tdu%g" % b for b in budgets]:
            ok_offs = sorted({r["offset"] for r in rs if iv.contains(feas[(var, r["spec"], r["start"])], r["offset"])})
            o["grid_" + var] = ok_offs[-1] if ok_offs else None
            best = None
            for spec, st in combos[oid]:
                x = capped_latest(feas[(var, spec, st)], last)
                if x is not None and (best is None or x > best):
                    best = x
            o["exact_" + var] = best
        per_origin[oid] = o
    return {"schema": "kcf-ablation.v2/1", "arm": arm, "variant": variant, "region": region, "input_time": input_time,
            "H": pm.H, "burning_cells": len(pm.burning), "budgets_tdu": list(budgets), "dwell_dose": "count",
            "specs": len(specs), "jobs": len(jobs), "job_feasible": dict(job_feasible), "timing_s": {**dict(tm), "total": time.perf_counter() - t_all},
            "host": {"platform": platform.platform(), "python": platform.python_version()},
            "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, "origins": per_origin}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("caches", nargs="+", type=Path)
    ap.add_argument("--data-root", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--arm", choices=("full", "persistence", "heat_off"), required=True)
    a = ap.parse_args()
    a.out_dir.mkdir(parents=True, exist_ok=True)
    for cache in a.caches:
        out = run(cache.resolve(), a.data_root, a.arm, with_cert=(a.arm == "full"))
        tag = "%s__%s__%s" % (out["region"], out["input_time"].replace(":", "").replace("-", ""), a.arm)
        (a.out_dir / (tag + ".json")).write_text(json.dumps(out, indent=1, default=str))
        print(tag, round(out["timing_s"]["total"], 1), "s", flush=True)


if __name__ == "__main__":
    main()
