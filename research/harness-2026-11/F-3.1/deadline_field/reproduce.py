"""Reproduce the planner cache from backward deadline fields.

For one cache file: build the exact interval instance from its frozen graph and hazard packet, run ONE backward field
per (destination node, dwell, window, rule variant), and read every recorded attempt (origin, departure offset,
destination) off the field. A forward witness gives the earliest arrival, compared with the recorded arrival.
Per origin: the planner deadline (latest offset with a checked attempt) and the exact 1-second deadline.

Output: one JSON per cache file with per-attempt and per-origin comparisons and timings.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import resource
import sys
import time
from collections import Counter, defaultdict
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.explain_deadlines.plans import CacheModel, reconstruct_legs  # noqa: E402

from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, check_fixed_point, issue_core, issue_set, witness  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
from deadline_field.verify import full_check  # noqa: E402

VARIANTS = ("router", "cert", "free")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cache_path: Path, data_root: Path, *, variants=VARIANTS, limit_dests=None, certify=True, verify=True):
    t_all = time.perf_counter()
    doc = json.loads(cache_path.read_text())
    region, input_time = doc["region_id"], doc["input_time"]
    compact = input_time.replace("-", "").replace(":", "")
    graph_path = data_root / "graphs" / region / "graph.json"
    packet_dir = data_root / "latest_inputs_try02" / "packets" / region / compact
    model = CacheModel(doc)
    t0 = time.perf_counter()
    pm = PacketModel(graph_path, packet_dir)
    hazard = json.loads((packet_dir / "HAZARD.json").read_text())
    t_prep = time.perf_counter() - t0
    # ---------------- attempts with their requests
    rows = []
    for oid, plan in model.plans.items():
        for cell in plan.sweep:
            for a in cell.attempts:
                job = model.job(a.job_id)
                if job is None:
                    rows.append({"origin_id": oid, "offset": a.offset_s, "dest_id": a.destination_id,
                                 "verdict": a.verdict, "arrival": a.arrival_s, "job": None})
                    continue
                q = job["request"]
                res = job.get("result") or {}
                rows.append({"origin_id": oid, "offset": a.offset_s, "dest_id": a.destination_id, "verdict": a.verdict,
                             "arrival": a.arrival_s, "job": a.job_id, "raw_status": res.get("raw_status"),
                             "start": q["start"]["node_id"], "dest": q["destination"]["node_id"],
                             "dwell": q["dwell_s"], "window": tuple(q["destination_window"]),
                             "incurred": q.get("incurred_dose_kj_m2", 0) or 0,
                             "limits": (q["limits"]["peak_kw_m2"], q["limits"]["dose_kj_m2"]),
                             "lower_bound": res.get("lower_bound_L_s"), "kind": plan.kind,
                             "recorded_compute_s": res.get("compute_s")})
    # ---------------- every route-check job of the file (also originals replaced by re-checks, research checks)
    job_rows = []
    for key, job in sorted((doc.get("route_checks") or {}).items()):
        q = job["request"]
        # scope guard: the field models a start at a plain node with no incoming edge and no edge fraction
        if set(q["start"]) != {"node_id"} or q.get("incoming_edge") not in (None,) or set(q["destination"]) != {"node_id"}:
            raise ValueError("unsupported start/destination position in job %s: %r" % (key, q["start"]))
        res = job.get("result") or {}
        rec_edges = None
        if res.get("verdict") == "checked_route":
            try:
                rl = reconstruct_legs(job)
                rec_edges = [(l["kind"], l.get("edge") or l.get("node"), int(l["start"]), int(l["end"])) for l in rl["legs"]]
            except Exception as exc:  # recorded but not rebuildable: reported, not hidden
                rec_edges = "unrebuildable: %s" % exc
        job_rows.append({"job": key, "offset": int(q["depart_offset_s"]), "verdict": res.get("verdict"),
                         "arrival": res.get("arrival_s"), "raw_status": res.get("raw_status"),
                         "start": q["start"]["node_id"], "dest": q["destination"]["node_id"], "dwell": q["dwell_s"],
                         "window": tuple(q["destination_window"]), "incurred": q.get("incurred_dose_kj_m2", 0) or 0,
                         "limits": (q["limits"]["peak_kw_m2"], q["limits"]["dose_kj_m2"]),
                         "recheck_of": job.get("recheck_of"), "recorded_compute_s": res.get("compute_s"),
                         "recorded_legs": rec_edges})
    # ---------------- precondition per distinct (limits, incurred)
    pre = {}
    for r in rows + job_rows:
        if r["job"] is None:
            continue
        k = (r["limits"], r["incurred"])
        if k not in pre:
            ok, det = pm.full_policy_reduces_to_contact(hazard, peak_limit=k[0][0], dose_limit=k[0][1], incurred=k[1])
            pre[k] = (ok, det)
    # ---------------- one backward field per (destination spec, variant)
    specs = defaultdict(set)
    for r in rows + job_rows:
        if r["job"] is not None:
            specs[(r["dest"], r["dwell"], r["window"])].add(r["start"])
    spec_list = sorted(specs, key=str)
    if limit_dests:
        spec_list = spec_list[:limit_dests]
    out_attempts = []
    field_s = Counter()
    certify_s = Counter()
    verify_s = Counter()
    verified = []
    piece_stats = Counter()
    limits_of = {}
    for r in rows + job_rows:
        if r["job"] is not None:
            limits_of.setdefault((r["start"], r["dest"], r["dwell"], r["window"]), (r["limits"], r["incurred"]))
    witness_s = Counter()
    pieces = Counter()
    issue_sets = {}
    exact_deadline = {}
    for spec in spec_list:
        dnode, dwell, window = spec
        origins = sorted(specs[spec])
        for var in variants:
            t1 = time.perf_counter()
            inst = pm.instance(var, [{"node": dnode, "dwell": dwell, "window": list(window)}], origins)
            fld = backward(inst)
            field_s[var] += time.perf_counter() - t1
            pieces[var] += fld.stats["pieces"]
            multi = [len(x) for x in fld.R if len(x) > 1]
            piece_stats[var + ":states_nonempty"] += sum(1 for x in fld.R if x)
            piece_stats[var + ":states_multi_interval"] += len(multi)
            piece_stats[var + ":max_intervals_per_state"] = max(piece_stats[var + ":max_intervals_per_state"], max(multi, default=1))
            if certify:
                t3 = time.perf_counter()
                check_fixed_point(fld)
                certify_s[var] += time.perf_counter() - t3
            t2 = time.perf_counter()
            for o in origins:
                oi = pm.nidx[o]
                core = issue_core(fld, oi)
                feas = issue_set(fld, oi)
                issue_sets[(var, spec, o)] = (core, feas, inst.IB.get(oi, []))
            for r in rows + job_rows:
                if r["job"] is None or (r["dest"], r["dwell"], r["window"]) != spec:
                    continue
                core, feas, ib = issue_sets[(var, spec, r["start"])]
                t = int(r["offset"])
                w = witness(fld, pm.nidx[r["start"]], t) if iv.contains(feas, t) else None
                r.setdefault("field", {})[var] = {
                    "issue_blocked": iv.contains(ib, t),
                    "feasible": w is not None,
                    "arrival": None if w is None else w[0],
                    "legs": None if w is None else [(k, (pm.g.edge_ids[x] if k == "EDGE" else pm.node_ids[x]), a, b)
                                                    for k, x, a, b in w[1]],
                }
            witness_s[var] += time.perf_counter() - t2
            if var == "cert" and verify:
                t4 = time.perf_counter()
                for o in origins:
                    core, feas, ib = issue_sets[(var, spec, o)]
                    if not feas:
                        continue
                    ld = feas[-1][1]
                    w = witness(fld, pm.nidx[o], ld)
                    (lim, inc) = limits_of[(o, dnode, dwell, window)]
                    legs = [(k, (pm.g.edge_ids[x] if k == "EDGE" else pm.node_ids[x]), a, b) for k, x, a, b in w[1]]
                    chk = full_check(pm, hazard, origin=o, legs=legs, dest=dnode, dwell=dwell, window=window,
                                     departure=ld, incurred=inc, peak=lim[0], dose=lim[1])
                    verified.append({"what": "exact_deadline", "origin": o, "dest": dnode, "window": window,
                                     "deadline_s": ld, "arrival": w[0], "next_second_infeasible": not iv.contains(feas, ld + 1),
                                     **chk})
                for r in rows + job_rows:
                    if r["job"] is None or (r["dest"], r["dwell"], r["window"]) != spec:
                        continue
                    f = r["field"]["cert"]
                    if not f["feasible"]:
                        continue
                    chk = full_check(pm, hazard, origin=r["start"], legs=f["legs"], dest=dnode, dwell=dwell, window=window,
                                     departure=int(r["offset"]), incurred=r["incurred"], peak=r["limits"][0], dose=r["limits"][1])
                    f["full_check"] = chk
                verify_s[var] += time.perf_counter() - t4
    # ---------------- per-origin deadlines (planner rule) on the recorded grid, and exact
    per_origin = {}
    by_origin = defaultdict(list)
    for r in rows:
        by_origin[r["origin_id"]].append(r)
    for oid, rs in by_origin.items():
        plan = model.plans[oid]
        offs = sorted({c.offset_s for c in plan.sweep})
        rec_D = plan.latest_s
        o = {"recorded_deadline": rec_D, "best_verdict": plan.best_verdict, "kind": plan.kind}
        for var in variants:
            ok_offs = sorted({r["offset"] for r in rs if r.get("field", {}).get(var, {}).get("feasible")})
            o["field_deadline_grid_" + var] = ok_offs[-1] if ok_offs else None
            # exact 1-s deadline over the same destinations, departures in [0, last offset]
            last = max(offs) if offs else 0
            best = None
            dests = {(r["dest"], r["dwell"], r["window"]) for r in rs if r["job"] is not None}
            starts = {r["start"] for r in rs if r["job"] is not None}
            for spec in dests:
                for st in starts:
                    key = (var, spec, st)
                    if key not in issue_sets:
                        continue
                    feas = issue_sets[key][1]
                    m = [hi if hi <= last else (last if lo <= last else None) for lo, hi in feas]
                    m = [x for x in m if x is not None]
                    if m and (best is None or max(m) > best):
                        best = max(m)
            o["field_deadline_exact_" + var] = best
            unc = None
            sets = {}
            for spec in dests:
                for st in starts:
                    key = (var, spec, st)
                    if key in issue_sets:
                        feas = issue_sets[key][1]
                        sets["%s|%s|%s" % (st, spec[0], spec[2])] = feas
                        if feas and (unc is None or feas[-1][1] > unc):
                            unc = feas[-1][1]
            o["field_deadline_exact_uncapped_" + var] = unc
            union = iv.normalize([p for v_ in sets.values() for p in v_])
            within = iv.subtract_all(union, [(last + 1, 10 ** 9)])
            o["holes_" + var] = (len(within) > 1) or (bool(within) and within[0][0] > 0)
            o["union_feasible_" + var] = within
            o["feasible_departures_" + var] = sets
        per_origin[oid] = o
    out = {
        "schema": "wfg.f31.reproduce/1",
        "cache_file": str(cache_path.relative_to(ROOT)), "cache_sha256": sha256(cache_path),
        "graph_sha256": sha256(graph_path), "hazard_sha256": sha256(packet_dir / "HAZARD.json"),
        "npz_sha256": sha256(packet_dir / "constructed_arrays.npz"),
        "region": region, "input_time": input_time, "H": pm.H,
        "edges": len(pm.g.u), "nodes": len(pm.node_ids), "edges_touching_burning": pm.edges_touching,
        "precondition": {str(k): {"ok": v[0], **v[1]} for k, v in pre.items()},
        "destination_specs": len(spec_list),
        "timing_s": {"prepare_packet_model": t_prep, "fields": dict(field_s), "issue_and_witness": dict(witness_s),
                     "fixed_point_certificate_check": dict(certify_s),
                     "witness_full_checker": dict(verify_s),
                     "total_wall": time.perf_counter() - t_all},
        "pieces": dict(pieces), "piece_stats": dict(piece_stats),
        "deadline_witness_checks": verified,
        "host": {"platform": platform.platform(), "python": platform.python_version(), "machine": platform.machine(),
                 "cpu_count": __import__("os").cpu_count()},
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0,
        "attempts": [{k: v for k, v in r.items()} for r in rows],
        "jobs": job_rows,
        "origins": per_origin,
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cache", type=Path)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "routing")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit-dests", type=int)
    ap.add_argument("--variants", default=",".join(VARIANTS))
    ap.add_argument("--timing-only", action="store_true", help="skip the certificate check and the full-checker witness verification")
    a = ap.parse_args()
    out = run(a.cache.resolve(), a.data_root, variants=tuple(a.variants.split(",")), limit_dests=a.limit_dests,
              certify=not a.timing_only, verify=not a.timing_only)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("cache_file", "destination_specs", "timing_s", "pieces", "peak_rss_mib")}, default=str))


if __name__ == "__main__":
    main()
