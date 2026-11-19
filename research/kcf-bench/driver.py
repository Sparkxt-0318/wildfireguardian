"""Benchmark driver (BENCH_PLAN.md sections 1, 3, 4). Resumable: finished tasks are in results/ledger.jsonl.

    python3 research/kcf-bench/driver.py --work <scratch dir outside the repository> [--repeats 5] [--only-repeat R]

Every timed child is pinned to core 3 with `taskset -c 3`, one thread. Before and after each task: a fixed CPU probe
(also pinned), /proc/loadavg and the /proc/stat jiffies. A file <work>/PAUSE makes the driver wait before the next task.
The harness files are hashed at start; a change mid-run stops the driver.
"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from common import CACHES, HERE, ROOT, cases_path, load_state

CORE = "3"
METHODS = ["field", "field_dec", "field_sample", "field_check", "margin1", "margin10", "old_cold", "old_warm"]
HARNESS = ["common.py", "driver.py", "run_field.py", "run_old.py", "make_cases.py"]
PIN = ["taskset", "-c", CORE]
ENV = dict(os.environ, OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1",
           PYTHONDONTWRITEBYTECODE="1")


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def harness_hashes():
    h = {n: sha(HERE / n) for n in HARNESS}
    h.update({"cases/" + cases_path(c).name: sha(cases_path(c)) for c in CACHES})
    return h


def probe():
    r = sh(PIN + [sys.executable, "-c", "import sys;sys.path.insert(0,%r);from common import cpu_probe;print(cpu_probe())" % str(HERE)],
           env=ENV)
    return float(r.stdout.strip())


def append(path, obj):
    with open(path, "a") as f:
        f.write(json.dumps(obj) + "\n")
        f.flush()
        os.fsync(f.fileno())


def machine(res):
    git = lambda *a: sh(["git", "-C", str(ROOT)] + list(a)).stdout.strip()
    info = {"started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "uname": " ".join(platform.uname()),
            "python": sys.version, "python_executable": sys.executable, "platform": platform.platform(),
            "cpu_model": next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), None),
            "logical_cpus": os.cpu_count(), "mem_total_kb": int(open("/proc/meminfo").readline().split()[1]),
            "git_head": git("rev-parse", "HEAD"), "git_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "git_status_outside_results": git("status", "--porcelain", "--", ".", ":(exclude)research/kcf-bench/results", ":(exclude)research/kcf-bench/results_dry"),
            "pinned_core": CORE, "numpy": sh([sys.executable, "-c", "import numpy;print(numpy.__version__)"]).stdout.strip(),
            "harness_sha256": harness_hashes(), "idea_routing_base": "a471eee1 (merged at dd8fe2d5)",
            "ps_top": sh(["ps", "-eo", "pcpu,pid,comm", "--sort=-pcpu"]).stdout.splitlines()[:8]}
    (res / "machine.json").write_text(json.dumps(info, indent=1))
    return info


def tasks_for(repeat):
    order = CACHES[(repeat - 1) % 6:] + CACHES[: (repeat - 1) % 6]
    meth = METHODS if repeat % 2 == 1 else METHODS[::-1]
    return [(m, c) for c in order for m in meth]


def safe(t):
    return t.replace("|", "__").replace("/", "__")


def run_task(method, cache, repeat, res, work, dry=False):
    tag = cache.replace("/", "__")
    tid = "%s|%s|r%d" % (method, cache, repeat)
    log = work / "logs" / (safe(tid) + ".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    if method.startswith("old_"):
        tmp = work / "tmp" / (safe(tid) + ".jsonl")
        tmp.parent.mkdir(exist_ok=True)
        cmd = PIN + [sys.executable, str(HERE / "run_old.py"), "--cache", cache, "--mode", method[4:], "--repeat", str(repeat),
                     "--out", str(tmp), "--work", str(work / "old_attempts")] + ["--resume"] + (["--limit", "3"] if dry else [])
        out = None
    else:
        out = res / "field" / ("%s__%s__r%d.json" % (method, tag, repeat))
        out.parent.mkdir(exist_ok=True)
        cmd = PIN + [sys.executable, str(HERE / "run_field.py"), "--cache", cache, "--method", method, "--out", str(out)]
        if repeat == 1 and method in ("field", "field_dec", "margin1", "margin10"):
            ans = res / "answers" / ("%s__%s.json" % (method, tag))
            ans.parent.mkdir(exist_ok=True)
            cmd += ["--answers", str(ans)]
    rec = {"task": tid, "method": method, "cache": cache, "repeat": repeat, "start_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "probe_before_s": probe(), "load_before": load_state()}
    t0 = time.perf_counter()
    with open(log, "w") as lf:
        p = subprocess.run(cmd, env=ENV, stdout=lf, stderr=subprocess.STDOUT, cwd=str(HERE))
    rec.update(task_wall_s=time.perf_counter() - t0, returncode=p.returncode, probe_after_s=probe(), load_after=load_state(),
               end_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    ok = p.returncode == 0
    if ok and method.startswith("old_"):
        lines = tmp.read_text().splitlines() if tmp.exists() else []
        ok = len(lines) == (3 if dry else 200)
        if ok:
            with open(res / "old.jsonl", "a") as f:
                f.write("\n".join(lines) + "\n")
                f.flush()
                os.fsync(f.fileno())
        rec["n_lines"] = len(lines)
        if ok:
            tmp.unlink()
    rec["status"] = "done" if ok else "failed"
    append(res / "ledger.jsonl", rec)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--only-repeat", type=int)
    ap.add_argument("--results", help="results directory (default research/kcf-bench/results); a dry run uses another one")
    ap.add_argument("--caches", help="substring: only caches containing it")
    ap.add_argument("--dry", action="store_true", help="dry run: OLD limited to 3 cases; never used for the benchmark")
    a = ap.parse_args()
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    res = Path(a.results) if a.results else HERE / "results"
    res.mkdir(exist_ok=True)
    first = not (res / "machine.json").exists()
    if first:
        info = machine(res)
        if info["git_status_outside_results"] and not a.dry:
            sys.exit("refusing to start: dirty tree\n" + info["git_status_outside_results"])
        base = harness_hashes()
    else:
        base = json.loads((res / "machine.json").read_text())["harness_sha256"]
        if harness_hashes() != base:
            sys.exit("harness files changed since the run started; refusing to continue")
    done = {json.loads(l)["task"] for l in (res / "ledger.jsonl").read_text().splitlines()
            if json.loads(l)["status"] == "done"} if (res / "ledger.jsonl").exists() else set()
    for r in range(1, a.repeats + 1):
        if a.only_repeat and r != a.only_repeat:
            continue
        for method, cache in tasks_for(r):
            if a.caches and a.caches not in cache:
                continue
            tid = "%s|%s|r%d" % (method, cache, r)
            if tid in done:
                continue
            while (work / "PAUSE").exists():
                (work / "PAUSED").write_text(time.strftime("%H:%M:%S"))      # idle: safe for git and other light work
                time.sleep(10)
            (work / "PAUSED").unlink(missing_ok=True)
            if harness_hashes() != base:
                sys.exit("harness files changed mid-run; stopping")
            ok = run_task(method, cache, r, res, work, a.dry)
            print(time.strftime("%H:%M:%S"), tid, "ok" if ok else "FAILED", flush=True)
    print("ALL TASKS ATTEMPTED", flush=True)


if __name__ == "__main__":
    main()
