"""Method A: the recorded per-departure method, one job at a time, single process (PLAN.md 2.A).

    python3 run_a.py CACHE_NAME JOBS_JSON OUT_JSONL WORK_DIR

Each job is run through the UNCHANGED planner worker entry point `api.runner.execute` with the spec the planner server
builds for a recorded-fire, full-policy route check (`api/app.py::_new_route_job`): candidate route by the kit
(`wfg_latest.api.route_and_check`, arm RDA_CAND, 30 s budget) plus the full-journey check, then the API verdict.
The request parameters are the recorded ones. Jobs run sequentially in this one worker process (the kit itself
launches its frozen child process per job, as it did for the recorded checks). After each job its work directory is
deleted (disk), and one JSON line is appended and flushed.
"""
from __future__ import annotations

import json
import os
import resource
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_ROOT, ROOT, load_cache  # noqa: E402

sys.path.insert(0, str(ROOT))
from api import runner  # noqa: E402


def cpu_now():
    s, c = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return s.ru_utime + s.ru_stime + c.ru_utime + c.ru_stime


def main():
    name, jobs_json, out_jsonl, work = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    doc = load_cache(name)
    region, compact = doc["region_id"], doc["input_time"].replace("-", "").replace(":", "")
    graph = DATA_ROOT / "graphs" / region / "graph.json"
    packet = DATA_ROOT / "latest_inputs_try02" / "packets" / region / compact
    ids = json.loads(jobs_json.read_text())
    work.mkdir(parents=True, exist_ok=True)
    stop_at = float(os.environ.get("KCF_BENCH_STOP_AT", "inf"))    # hard-stop rule (PLAN.md 8): no job starts after it
    with open(out_jsonl, "a") as out:
        for k, jid in enumerate(ids):
            if time.time() > stop_at:
                break
            rec = doc["route_checks"][jid]
            q, rres = rec["request"], rec.get("result") or {}
            lim = dict(rres.get("limits") or {})
            lim.setdefault("peak_kw_m2", q["limits"]["peak_kw_m2"])
            lim.setdefault("dose_kj_m2", q["limits"]["dose_kj_m2"])
            lim.setdefault("incurred_dose_kj_m2", q.get("incurred_dose_kj_m2", 0) or 0)
            spec = {"job_id": "BENCH_" + jid, "job_dir": str(work / jid), "graph_path": str(graph), "packet_dir": str(packet),
                    "fire_input": {"type": "recorded"}, "zone_plan": None,
                    "request_params": {"start_node": q["start"]["node_id"], "dest_node": q["destination"]["node_id"],
                                       "depart_offset_s": q["depart_offset_s"], "dwell_s": q["dwell_s"],
                                       "window": q["destination_window"], "limits": lim},
                    "policy": "full", "python": sys.executable, "run_independent_check": False,
                    "runtime_dir": str(work / "_runtime")}
            c0, t0 = cpu_now(), time.perf_counter()
            r = runner.execute(spec)
            wall, cpu = time.perf_counter() - t0, cpu_now() - c0
            res = r.get("result") or {}
            route = res.get("route") or {}
            row = {"cache": name, "job": jid, "i": k, "wall_s": wall, "cpu_s": cpu, "status": r.get("status"),
                   "tainted": r.get("tainted"), "error": r.get("error"), "verdict": res.get("verdict"),
                   "reason_code": res.get("reason_code"), "raw_status": res.get("raw_status"),
                   "departure_s": res.get("departure_s"), "arrival_s": res.get("arrival_s"),
                   "compute_s": res.get("compute_s"), "within_budget": res.get("within_budget"),
                   "route_properties": route.get("properties"), "receipt": r.get("receipt"), "timings": r.get("timings"),
                   "loadavg": os.getloadavg(), "t_unix": time.time()}
            out.write(json.dumps(row, default=str) + "\n")
            out.flush()
            shutil.rmtree(work / jid, ignore_errors=True)
    s, c = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    scale = 1.0 if sys.platform == "darwin" else 1024.0
    with open(str(out_jsonl) + ".proc.json", "a") as f:
        f.write(json.dumps({"worker_peak_rss_mib": s.ru_maxrss * scale / 2 ** 20,
                            "largest_kit_child_peak_rss_mib": c.ru_maxrss * scale / 2 ** 20, "jobs": len(ids)}) + "\n")


if __name__ == "__main__":
    main()
