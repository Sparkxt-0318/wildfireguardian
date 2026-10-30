"""Fresh native ABBA comparison on exact sealed Korean and Caldor/Rim inputs.

One child per execution. The outer 30 s deadline includes imports and input
loading. The sampled child RSS guard is 3072 MiB. Only the contact relaxation is
measured, not the complete thermal routing request. No frozen file is written.
"""
from __future__ import annotations
import argparse
import csv
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
for name in ("sipp-routing", "scenario-members", "synthetic-truth"):
    sys.path.insert(0, str(ROOT / "experimental" / name / "src"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_cases(korean_jobs, caldor_jobs):
    cases = {}
    for folder, panel in ((korean_jobs, "Korean"), (caldor_jobs, "Caldor/Rim")):
        for p in sorted(Path(folder).glob("*.json")):
            d = json.loads(p.read_text())
            key = (d.get("cohort", panel), d["case_id"])
            if key in cases:
                continue
            def resolved(name):
                q = Path(d[name]); return str(q if q.is_absolute() else Path(d["root"]) / q)
            case = dict(panel=panel, region=d.get("cohort", d["case_id"].split("_")[0]),
                        mission=d["case_id"], graph=resolved("graph_path"), request=resolved("request_path"),
                        packet=resolved("source_directory"), job_sha256=sha(p))
            if not all(Path(case[k]).exists() for k in ("graph", "request", "packet")):
                continue
            case["input_sha256"] = {k: sha(case[k]) for k in ("graph", "request")}
            case["input_sha256"].update({name: sha(Path(case["packet"]) / name) for name in ("REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz", "HAZARD.json")})
            cases[key] = case
    return list(cases.values())


def child(case_path, method, result_path):
    from wfg_scenario_members.contact import ContactModel
    from wfg_sipp.adapter import sweep_plan
    from wfg_sipp.frontend import sipp_plan
    case = json.loads(Path(case_path).read_text())
    for key in ("graph", "request"):
        if sha(case[key]) != case["input_sha256"][key]:
            raise RuntimeError("INPUT_CHANGED:" + key)
    for name in ("REPORT.json", "NATIVE_METADATA.json", "constructed_arrays.npz", "HAZARD.json"):
        if sha(Path(case["packet"]) / name) != case["input_sha256"][name]:
            raise RuntimeError("INPUT_CHANGED:" + name)
    graph = json.loads(Path(case["graph"]).read_text())
    request = json.loads(Path(case["request"]).read_text())
    model = ContactModel.from_packet(case["packet"])
    run = sipp_plan if method == "sipp" else sweep_plan
    t0 = time.perf_counter()
    result = run(graph, request, model, wall_s=29.0)
    result["planner_wall_s"] = time.perf_counter() - t0
    result["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024)
    result.update(method=method, mission=case["mission"], panel=case["panel"], region=case["region"])
    Path(result_path).write_text(json.dumps(result, allow_nan=False) + "\n")


def parent(args):
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    if (out / "EXECUTIONS.jsonl").exists():
        raise RuntimeError("WRITE_ONCE_OUTPUT")
    cases = make_cases(args.korean_jobs, args.caldor_jobs)
    (out / "CASES.json").write_text(json.dumps(cases, indent=2) + "\n")
    rows = []
    with open("/tmp/wfg/HEAVY.lock", "a+") as lease:
        fcntl.flock(lease, fcntl.LOCK_EX)
        for index, case in enumerate(cases):
            casefile = out / ("case_%02d.json" % index); casefile.write_text(json.dumps(case))
            for rep, methods in ((1, ("sweep", "sipp")), (2, ("sipp", "sweep"))):
                for method in methods:
                    dest = out / ("%02d_r%d_%s.json" % (index, rep, method))
                    started = time.monotonic()
                    proc = subprocess.Popen([sys.executable, "-I", str(Path(__file__).resolve()),
                                             "--child", str(casefile), "--method", method, "--result", str(dest)],
                                            start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    stop = None; maximum = 0
                    while proc.poll() is None:
                        elapsed = time.monotonic() - started
                        try:
                            rss = subprocess.check_output(["ps", "-o", "rss=", "-p", str(proc.pid)], text=True).strip()
                            if rss:
                                maximum = max(maximum, int(rss) / 1024)
                        except (subprocess.CalledProcessError, ValueError):
                            pass
                        if elapsed >= 30 or maximum > 3072:
                            stop = "DEADLINE" if elapsed >= 30 else "RSS_LIMIT"
                            os.killpg(proc.pid, signal.SIGKILL)
                            break
                        time.sleep(0.05)
                    stdout, stderr = proc.communicate()
                    row = dict(case_index=index, mission=case["mission"], region=case["region"], panel=case["panel"],
                               repetition=rep, method=method, complete_wall_s=time.monotonic() - started,
                               sampled_child_rss_mib=maximum, exit_code=proc.returncode, stop=stop)
                    if proc.returncode == 0 and stop is None and dest.exists():
                        row.update(json.loads(dest.read_text()))
                    else:
                        row.update(status="UNRESOLVED", arrival=None, error=stderr.decode()[-3000:])
                    rows.append(row)
                    with (out / "EXECUTIONS.jsonl").open("a") as f:
                        f.write(json.dumps(row) + "\n")
                    print(json.dumps({k: row.get(k) for k in ("mission", "repetition", "method", "status", "arrival", "complete_wall_s")}), flush=True)
    pairs = []
    for i, case in enumerate(cases):
        for rep in (1, 2):
            a = next(r for r in rows if r["case_index"] == i and r["repetition"] == rep and r["method"] == "sweep")
            b = next(r for r in rows if r["case_index"] == i and r["repetition"] == rep and r["method"] == "sipp")
            pairs.append(dict(mission=case["mission"], panel=case["panel"], repetition=rep,
                              equivalent=(a["status"], a["arrival"]) == (b["status"], b["arrival"]) and a["status"] != "UNRESOLVED",
                              sweep_status=a["status"], sipp_status=b["status"], sweep_arrival=a["arrival"], sipp_arrival=b["arrival"]))
    summary = {"cases": len(cases), "pairs": len(pairs), "equivalent_pairs": sum(p["equivalent"] for p in pairs),
               "unresolved_executions": sum(r["status"] == "UNRESOLVED" for r in rows), "pair_results": pairs,
               "host": platform.platform(), "python": sys.version, "source_sha256": sha(__file__),
               "scope": "contact relaxation only, cold complete child time, no physical claim"}
    (out / "RESULTS.json").write_text(json.dumps(summary, indent=2) + "\n")
    columns = ["mission", "panel", "region", "repetition", "method", "status", "arrival", "complete_wall_s", "planner_wall_s", "sampled_child_rss_mib", "peak_rss_mib", "exit_code", "stop"]
    with (out / "EXECUTIONS.csv").open("w") as f:
        writer = csv.DictWriter(f, columns, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--child"); p.add_argument("--method"); p.add_argument("--result")
    p.add_argument("--korean-jobs"); p.add_argument("--caldor-jobs"); p.add_argument("--out")
    a = p.parse_args()
    child(a.child, a.method, a.result) if a.child else parent(a)
