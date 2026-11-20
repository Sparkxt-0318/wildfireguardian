"""Method B: the F-3.1 deadline field (`deadline_field.core.backward`), `cert` rule, single process (PLAN.md 2.B).

    python3 run_b.py CACHE_NAME OUT_JSON [JOBS_JSON]

The same steps as `deadline_field/reproduce.py::run` restricted to the `cert` variant with `certify=False,
verify=False` (its `--timing-only` path): build the packet model, check the precondition per (limits, incurred), run
ONE backward field per destination spec (node, dwell, window) over the jobs' start nodes, and read every job off it
(issue set, then a forward witness at the job's departure second). With JOBS_JSON only those jobs (and only the
destination specs and start nodes they use) are run. No existing code is changed; everything is imported.
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_ROOT, ROOT, load_cache  # noqa: E402

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "harness-2026-11" / "F-3.1"))
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import backward, issue_set, witness  # noqa: E402
from deadline_field.real import PacketModel  # noqa: E402

VAR = "cert"


def main():
    name, out = sys.argv[1], Path(sys.argv[2])
    only = set(json.loads(Path(sys.argv[3]).read_text())) if len(sys.argv) > 3 else None
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
    t_field = t_read = 0.0
    pieces = 0
    by_spec = defaultdict(list)
    for r in jobs:
        by_spec[(r["dest"], r["dwell"], r["window"])].append(r)
    results = {}
    for spec in sorted(specs, key=str):
        dnode, dwell, window = spec
        origins = sorted(specs[spec])
        t1 = time.perf_counter()
        inst = pm.instance(VAR, [{"node": dnode, "dwell": dwell, "window": list(window)}], origins)
        fld = backward(inst)
        t_field += time.perf_counter() - t1
        pieces += fld.stats["pieces"]
        t2 = time.perf_counter()
        feas_of = {o: issue_set(fld, pm.nidx[o]) for o in origins}
        for r in by_spec[spec]:
            t = r["offset"]
            oi = pm.nidx[r["start"]]
            w = witness(fld, oi, t) if iv.contains(feas_of[r["start"]], t) else None
            results[r["job"]] = {
                "verdict": "checked_route" if w is not None else "model_no_route",
                "issue_blocked": iv.contains(inst.IB.get(oi, []), t), "departure_s": t,
                "arrival_s": None if w is None else int(w[0]),
                "legs": None if w is None else [(k, (pm.g.edge_ids[x] if k == "EDGE" else pm.node_ids[x]), int(a), int(b))
                                                for k, x, a, b in w[1]]}
        t_read += time.perf_counter() - t2
    scale = 1.0 if sys.platform == "darwin" else 1024.0
    rec = {"method": "B", "variant": VAR, "cache": name, "jobs": len(jobs), "destination_specs": len(specs),
           "edges": len(pm.g.u), "nodes": len(pm.node_ids), "pieces": pieces,
           "precondition_ok": {str(k): v for k, v in pre.items()},
           "timing_s": {"import": t_import, "load_cache": t_load, "prepare_packet_model": t_prep, "precondition": t_pre,
                        "fields": t_field, "issue_and_witness": t_read, "total_in_process": time.perf_counter() - T_START},
           "peak_rss_mib_self": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale / 2 ** 20,
           "results": results}
    if os.environ.get("KCF_BENCH_B_SLIM"):          # repeats 2-3: computed identically, per-job output not written (disk)
        rec["results"] = None
        rec["verdict_counts"] = dict(Counter(r["verdict"] for r in results.values()))
    out.write_text(json.dumps(rec))


if __name__ == "__main__":
    main()
