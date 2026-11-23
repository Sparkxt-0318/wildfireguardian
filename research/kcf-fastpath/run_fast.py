"""Method B of kcf-bench-mac with a choice of field solver (PROTOCOL.md 4).

    python3 run_fast.py SOLVER CACHE_NAME OUT_JSON [JOBS_JSON]

SOLVER: ``baseline`` (the unchanged ``deadline_field.core.backward``), ``scalar`` (change 1), ``prune`` (change 2),
``both``. Everything else is ``research/kcf-bench-mac/run_b.py`` step for step (packet model, precondition per
(limits, incurred), one field per destination spec over the jobs' start nodes, issue set and witness per job), so
the four solvers are timed by the same procedure as kcf-bench-mac. With ``KCF_FAST_TRACEMALLOC=1`` the run is an
untimed memory probe: ``tracemalloc`` records, per spec, the peak bytes allocated during the solver call and the bytes
the finished field keeps.
"""
from __future__ import annotations

import json
import os
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

T_START = time.perf_counter()
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research" / "kcf-bench-mac"))
from common import DATA_ROOT, load_cache  # noqa: E402

sys.path.insert(0, str(ROOT / "research" / "harness-2026-11" / "F-3.1"))
sys.path.insert(0, str(HERE))
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set, witness  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402
import fastfield as ff  # noqa: E402

VAR = "cert"
SOLVERS = ("baseline", "scalar", "prune", "both")


def make_field(solver, inst, origin_idx):
    if solver == "baseline":
        return backward(inst)
    return ff.solve(inst, scalar=solver in ("scalar", "both"),
                    prune_origins=origin_idx if solver in ("prune", "both") else None)


def main():
    solver, name, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    if solver not in SOLVERS:
        raise SystemExit("solver must be one of %s" % (SOLVERS,))
    only = set(json.loads(Path(sys.argv[4]).read_text())) if len(sys.argv) > 4 else None
    probe = bool(os.environ.get("KCF_FAST_TRACEMALLOC"))
    if probe:
        import tracemalloc
    t_import = time.perf_counter() - T_START
    t0 = time.perf_counter()
    doc = load_cache(name)
    region, compact = doc["region_id"], doc["input_time"].replace("-", "").replace(":", "")
    graph = DATA_ROOT / "graphs" / region / "graph.json"
    packet = DATA_ROOT / "latest_inputs_try02" / "packets" / region / compact
    jobs = []
    for key, job in sorted(doc["route_checks"].items()):
        if only is not None and key not in only:
            continue
        q = job["request"]
        if set(q["start"]) != {"node_id"} or q.get("incoming_edge") is not None or set(q["destination"]) != {"node_id"}:
            raise ValueError("unsupported start/destination position in job %s" % key)
        jobs.append({"job": key, "offset": int(q["depart_offset_s"]), "start": q["start"]["node_id"],
                     "dest": q["destination"]["node_id"], "dwell": q["dwell_s"], "window": tuple(q["destination_window"]),
                     "incurred": q.get("incurred_dose_kj_m2", 0) or 0,
                     "limits": (q["limits"]["peak_kw_m2"], q["limits"]["dose_kj_m2"])})
    t_load = time.perf_counter() - t0
    t0 = time.perf_counter()
    pm = PacketModel(graph, packet)
    hazard = json.loads((packet / "HAZARD.json").read_text())
    t_prep = time.perf_counter() - t0
    t0 = time.perf_counter()
    pre = {}
    for r in jobs:
        k = (r["limits"], r["incurred"])
        if k not in pre:
            ok, _ = pm.full_policy_reduces_to_contact(hazard, peak_limit=k[0][0], dose_limit=k[0][1], incurred=k[1])
            pre[k] = ok
    t_pre = time.perf_counter() - t0
    specs = defaultdict(set)
    for r in jobs:
        specs[(r["dest"], r["dwell"], r["window"])].add(r["start"])
    t_inst = t_field = t_read = 0.0
    pieces = 0
    kinds = Counter()
    hyp = Counter()
    mem = []
    by_spec = defaultdict(list)
    for r in jobs:
        by_spec[(r["dest"], r["dwell"], r["window"])].append(r)
    results = {}
    for spec in sorted(specs, key=str):
        dnode, dwell, window = spec
        origins = sorted(specs[spec])
        t1 = time.perf_counter()
        inst = pm.instance(VAR, [{"node": dnode, "dwell": dwell, "window": list(window)}], origins)
        t2 = time.perf_counter()
        t_inst += t2 - t1
        origin_idx = [pm.nidx[o] for o in origins]
        if probe:
            tracemalloc.start()
            before = tracemalloc.get_traced_memory()[0]
            fld = make_field(solver, inst, origin_idx)
            cur, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            mem.append({"spec": str(spec), "solver_peak_bytes": peak - before, "field_kept_bytes": cur - before})
        else:
            fld = make_field(solver, inst, origin_idx)
        t3 = time.perf_counter()
        t_field += t3 - t2
        pieces += fld.stats["pieces"]
        if solver != "baseline":
            kinds.update(fld.stats["kinds"])
            hyp.update(fld.stats.get("hypotheses", {}))
        rd = issue_set if solver == "baseline" else ff.issue_set
        wt = witness if solver == "baseline" else ff.witness
        feas_of = {o: rd(fld, pm.nidx[o]) for o in origins}
        for r in by_spec[spec]:
            t = r["offset"]
            oi = pm.nidx[r["start"]]
            w = wt(fld, oi, t) if iv.contains(feas_of[r["start"]], t) else None
            results[r["job"]] = {
                "verdict": "checked_route" if w is not None else "model_no_route",
                "issue_blocked": iv.contains(inst.IB.get(oi, []), t), "departure_s": t,
                "arrival_s": None if w is None else int(w[0]),
                "legs": None if w is None else [(k, (pm.g.edge_ids[x] if k == "EDGE" else pm.node_ids[x]), int(a), int(b))
                                                for k, x, a, b in w[1]]}
        t_read += time.perf_counter() - t3
        del fld
    scale = 1.0 if sys.platform == "darwin" else 1024.0
    rec = {"method": "B", "solver": solver, "variant": VAR, "cache": name, "jobs": len(jobs),
           "destination_specs": len(specs), "edges": len(pm.g.u), "nodes": len(pm.node_ids), "pieces": pieces,
           "state_kinds": dict(kinds), "hypothesis_failures_summed_over_specs": dict(hyp),
           "precondition_ok": {str(k): v for k, v in pre.items()},
           "timing_s": {"import": t_import, "load_cache": t_load, "prepare_packet_model": t_prep, "precondition": t_pre,
                        "instances": t_inst, "fields": t_field, "issue_and_witness": t_read,
                        "total_in_process": time.perf_counter() - T_START},
           "peak_rss_mib_self": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale / 2 ** 20,
           "tracemalloc": mem if probe else None,
           "results": results}
    if os.environ.get("KCF_BENCH_B_SLIM"):
        rec["results"] = None
        rec["verdict_counts"] = dict(Counter(r["verdict"] for r in results.values()))
    out.write_text(json.dumps(rec))


if __name__ == "__main__":
    main()
