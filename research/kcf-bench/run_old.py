"""Child process: OLD, one request at a time, on the frozen 200-case sample of a cache (BENCH_PLAN.md section 3a).

    taskset -c 3 python3 research/kcf-bench/run_old.py --cache <cache> --mode cold|warm --repeat R --out results/old.jsonl
        --work <scratch dir outside the repository> [--limit N]

Each request is `wfg_latest.api.route_and_check` exactly as the API makes it (request from api/requests_build.py, kit v3
worker RDA_CAND launched by the kit controller, full policy, 30 s budget, 3,072 MiB guard, check=False), except that the
call is made through the controller directly so the warm mode can name its private prepared-graph store. Verdict and
arrival are classified by the API's own api/verdict.py. Appends one JSON line per request.
"""
import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

from common import ROOT, add_paths, load_cases, packet_paths

add_paths()
from api import config as C  # noqa: E402
from api import verdict as V  # noqa: E402
from api.requests_build import build_request, effective_limits  # noqa: E402
from wfg_latest import api as WA  # noqa: E402

KIT = C.KIT_ROOT
sys.path[:0] = [str(KIT / "runner"), str(KIT / "decision")]
import journey_decision_v2_1 as JD  # noqa: E402
import wfg_controller as CTL  # noqa: E402


def sha(p):
    return WA._sha(p)


def one_request(case, packet, graph_path, graph_obj, hazard, sids, work, label, python, mode, store, q0, budget):
    lim = effective_limits({"limits": {"peak_kw_m2": case["peak"], "dose_kj_m2": case["dose"]},
                            "incurred_dose_kj_m2": case["incurred"]})
    req = build_request(start_node=case["start"], dest_node=case["dest"], depart_offset_s=case["offset"],
                        dwell_s=case["dwell"], window=case["window"], limits=lim, scenario_ids=sids,
                        horizon_s=hazard["valid_until"], valid_from=hazard["valid_from"],
                        hazard_version=hazard["version"], as_of_iso=hazard["time_origin"], dt=int(hazard["dt"]))
    d = work / label
    d.mkdir(parents=True)
    rp = d / "REQUEST.json"
    rp.write_text(json.dumps(req))
    out = d / "attempt"
    job = {"label": label, "case_id": label, "cohort": "api", "arm": "RDA_CAND", "arm_key": "RDA_CAND", "rep": 1,
           "source_root": q0["source_root"], "source_directory": str(packet), "graph_path": str(graph_path),
           "hazard_path": str(packet / "HAZARD.json"), "request_path": str(rp), "complete_budget_s": float(budget),
           "original_limits": req["limits"], "worker": WA.ARM_WORKER["RDA_CAND"], "env": {},
           "input_sha256": {"graph_path": GRAPH_SHA[str(graph_path)], "hazard_path": sha(packet / "HAZARD.json"),
                            "request_path": sha(rp)},
           "source_sha256": {n: sha(packet / n) for n in ("REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz")},
           "core_sha256": q0["core_sha256"], "checker_module": q0["checker_module"], "checker_sha256": q0["checker_sha256"],
           "root": None, "decision_dir": None, "output_path": str(out), "campaign": "BENCH", "queue": "BENCH",
           "preparation_mode": "AUTHENTICATED_ARTIFACT" if mode == "warm" else q0["preparation_mode"],
           "preparation_mode_sha256": q0["preparation_mode_sha256"],
           "preparation_source_sha256": q0["preparation_source_sha256"], "memory_guard_mib": C.MEMORY_GUARD_MIB,
           "phaseB_sha256": q0["phaseB_sha256"]}
    t0 = time.perf_counter()
    rc = CTL.run_attempt(KIT, job, python, {"api": True}, private_cache_root=(str(store) if mode == "warm" else None))
    outer = time.perf_counter() - t0
    res = json.loads((out / "RESULT.json").read_text()) if (out / "RESULT.json").exists() else {}
    jobj = json.loads((out / "JOB.json").read_text())
    dec = JD.decision_from_worker_record(res, rc, jobj, graph=graph_obj, request=req, hazard=hazard,
                                         optimality_certificate=res.get("optimality_certificate"),
                                         refusal_certificate=res.get("refusal_certificate"))
    verdict, reason, raw = V.classify(dec, rc, res, None, C.MEMORY_GUARD_MIB)
    if verdict == V.CHECKED and ((res.get("whole_road_check") or {}).get("contact") or {}).get("status") != "CLEAR":
        verdict, reason, raw = V.UNRESOLVED, "CHECK_FAILED", "CONTACT_NOT_CLEAR"
    arrival = (dec.get("journey") or {}).get("arrival") if verdict == V.CHECKED else None
    tv = rc.get("time_v") or {}
    rec = {"verdict": verdict, "reason": reason, "raw": raw, "authoritative": dec.get("authoritative_status"),
           "arrival": arrival, "wall_s": rc["external_launch_to_completion_wall_s"], "outer_s": outer,
           "rss_mb": None if tv.get("timed_command_RSS_bytes") is None else tv["timed_command_RSS_bytes"] / 2 ** 20,
           "fam_peak_mb": rc.get("sampled_family_peak_rss_bytes", 0) / 2 ** 20, "cpu_s": tv.get("CPU_s"),
           "on_time": rc.get("on_time_complete_publication"), "cleanup": rc.get("cleanup_state"),
           "exit": rc.get("exit_code"), "prep_mode": rc.get("preparation_mode_recorded"),
           "cache_hit": rc.get("preparation_cache_hit"), "term": rc.get("termination_requested"),
           "stage_s": (res.get("stages") or {})}
    shutil.rmtree(d, ignore_errors=True)
    return rec


GRAPH_SHA = {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--mode", choices=("cold", "warm"), required=True)
    ap.add_argument("--repeat", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--budget", type=float, default=C.BUDGET_S)
    a = ap.parse_args()
    doc = load_cases(a.cache)
    by_id = {c["id"]: c for c in doc["cases"]}
    sample = [by_id[i] for i in doc["sample"]][: a.limit]
    graph_path, packet = packet_paths(doc["region"], doc["input_time"])
    graph_obj = json.loads(graph_path.read_text())
    GRAPH_SHA[str(graph_path)] = sha(graph_path)
    hazard = json.loads((packet / "HAZARD.json").read_text())
    sids = [m["id"] for m in hazard["members"]]
    q0 = json.loads((KIT / "queues/LATEST_PREFLIGHT_REAL.json").read_text())["jobs"][0]
    work = Path(a.work) / ("%s_%s_r%d_%d" % (a.cache.replace("/", "__"), a.mode, a.repeat, os.getpid()))
    work.mkdir(parents=True)
    store = Path(a.work) / "prepared_store"
    if a.mode == "warm":
        store.mkdir(exist_ok=True, mode=0o700)
        os.chmod(store, 0o700)
        prime = one_request(sample[0], packet, graph_path, graph_obj, hazard, sids, work, "prime", sys.executable, "warm",
                            store, q0, 300.0)
        print(json.dumps({"prime": {k: prime[k] for k in ("verdict", "wall_s", "cache_hit")}}), flush=True)
    py = sys.executable
    with open(a.out, "a") as f:
        for n, case in enumerate(sample):
            rec = one_request(case, packet, graph_path, graph_obj, hazard, sids, work, "c%03d" % n, py, a.mode, store, q0,
                              a.budget)
            rec.update(cache=a.cache, mode=a.mode, repeat=a.repeat, n=n, case=case["id"], offset=case["offset"],
                       rec_verdict=case["rec_verdict"], rec_arrival=case["rec_arrival"])
            f.write(json.dumps(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
