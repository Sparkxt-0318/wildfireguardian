"""Run one prepared job with a sampled process-family memory and wall-clock guard."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from io_utils import dump, read, sha

HERE = Path(__file__).resolve().parent


def utc():
    return datetime.now(timezone.utc).isoformat()


def snapshot(timeout):
    """Get a bounded process census, excluding the census helper."""
    helper = subprocess.Popen(
        ["/bin/ps", "-A", "-o", "pid=,ppid=,pgid=,rss=,stat=,lstart="],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        output, errors = helper.communicate(timeout=timeout)
    except BaseException:
        helper.kill()
        helper.wait(timeout=2)
        raise
    if helper.returncode:
        raise RuntimeError(f"Process census failed: {errors[:200]}")
    rows = {}
    for line in output.splitlines():
        fields = line.split(None, 9)
        if len(fields) != 10 or not all(value.lstrip("-").isdigit() for value in fields[:4]):
            raise RuntimeError("Malformed process census")
        pid, ppid, pgid, rss = map(int, fields[:4])
        if pid in rows or min(pid, ppid, pgid, rss) < 0:
            raise RuntimeError("Duplicate or negative process census entry")
        if pid != helper.pid:
            rows[pid] = dict(
                pid=pid, ppid=ppid, pgid=pgid, rss_kib=rss,
                state=fields[4], start=" ".join(" ".join(fields[5:]).split()),
            )
    if os.getpid() not in rows:
        raise RuntimeError("Controller missing from process census")
    return rows


def owned(rows, group, controller, lineage):
    """Include the isolated process group and identity-verified observed descendants."""
    live = {p: row for p, row in rows.items() if p != controller and not row["state"].startswith("Z")}
    selected = {p for p, row in live.items() if row["pgid"] == group}
    for pid, old in lineage.items():
        if pid in live and pid not in selected:
            if not old.get("start") or not live[pid].get("start"):
                raise RuntimeError("Tracked process identity unknown")
            if live[pid]["start"] == old["start"]:
                selected.add(pid)
    while True:
        children = {p for p, row in live.items() if row["ppid"] in selected}
        if children <= selected:
            break
        selected |= children
    for pid in selected:
        lineage[pid] = {key: live[pid][key] for key in ("ppid", "pgid", "start")}
    detached = [p for p in selected if live[p]["pgid"] != group]
    return selected, detached


def cleanup(child, group, lineage):
    record = {"status": "UNKNOWN", "signals": [], "census": []}
    try:
        for sig, duration in ((signal.SIGTERM, 2.0), (signal.SIGKILL, 3.0)):
            end = time.perf_counter() + duration
            while True:
                rows = snapshot(min(1.0, max(0.01, end - time.perf_counter())))
                pids, detached = owned(rows, group, os.getpid(), lineage)
                record["census"].append({"utc": utc(), "pids": sorted(pids), "detached": detached})
                if not pids:
                    break
                for pid in sorted(pids):
                    try:
                        os.kill(pid, sig)
                        record["signals"].append({"pid": pid, "signal": int(sig)})
                    except ProcessLookupError:
                        pass
                if time.perf_counter() >= end:
                    break
                time.sleep(min(0.05, max(0, end - time.perf_counter())))
            if not pids:
                break
        if child.poll() is None:
            child.kill()
        child.wait(timeout=2)
        rows = snapshot(1.0)
        pids, detached = owned(rows, group, os.getpid(), lineage)
        record.update(status="CLEAN" if not pids else "SURVIVORS", remaining=sorted(pids), detached=detached)
    except BaseException as error:
        record["error"] = type(error).__name__ + ": " + str(error)
        if child.poll() is None:
            child.kill()
            child.wait(timeout=2)
    return record


def supervise(command, out, env, wall_s=30.0, rss_mib=3072, require_result=True,
              bound_job=None, job_sha256=None):
    """Monitor a single worker and retain samples; no incomplete result is accepted."""
    out = Path(out)
    if wall_s <= 0 or rss_mib <= 0:
        raise ValueError("Wall and memory limits must be positive")
    lineage = {}
    samples = []
    reason = None
    proc = None
    wall_start = time.time()
    start = time.perf_counter()
    child_env = env.copy()
    child_env["WFG_OUTER_MONOTONIC_START"] = repr(start)
    with (out / "worker.log").open("x") as log:
        try:
            proc = subprocess.Popen(
                command, start_new_session=True, stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, env=child_env,
            )
            while True:
                elapsed = max(time.perf_counter() - start, time.time() - wall_start)
                remaining = wall_s - elapsed
                if remaining <= 0:
                    reason = "DEADLINE"
                    break
                if proc.poll() is not None:
                    break
                rows = snapshot(min(1, max(0.02, remaining)))
                family, detached = owned(rows, proc.pid, os.getpid(), lineage)
                if detached:
                    raise RuntimeError("Detached worker process")
                if proc.poll() is None and proc.pid not in family:
                    raise RuntimeError("Active worker missing from process census")
                used = 1024 * sum(rows[pid]["rss_kib"] for pid in family | {os.getpid()})
                samples.append([time.perf_counter() - start, used, sorted(family), rows[os.getpid()]["rss_kib"]])
                if used > rss_mib * 2**20:
                    reason = "MEMORY"
                    break
                time.sleep(min(0.045, max(0, wall_s - (time.perf_counter() - start))))
        except BaseException as error:
            reason = f"GUARD_FAILURE: {type(error).__name__}: {error}"
        elapsed = time.perf_counter() - start
        elapsed_wall = time.time() - wall_start
        if max(elapsed, elapsed_wall) >= wall_s and not reason:
            reason = "DEADLINE"
        clean = cleanup(proc, proc.pid, lineage) if proc else {"status": "UNKNOWN"}
    if not reason and bound_job is not None:
        try:
            if sha(bound_job) != job_sha256:
                reason = "JOB_CHANGED_DURING_EXECUTION"
        except OSError:
            reason = "JOB_UNAVAILABLE_AFTER_EXECUTION"
    if not reason and proc.returncode:
        reason = "WORKER_ERROR"
    if not reason and clean["status"] != "CLEAN":
        reason = "CLEANUP_FAILURE"
    if not reason and not samples:
        reason = "NO_MEMORY_SAMPLE"
    if not reason and require_result and not (out / "RESULT.json").is_file():
        reason = "MISSING_RESULT"
    receipt = {
        "includes_controller_rss": True, "accepted_execution": reason is None,
        "cause": reason, "wall_s": elapsed, "utc_elapsed_s": elapsed_wall,
        "sampled_peak_mib": max((s[1] for s in samples), default=0) / 2**20,
        "samples": len(samples), "returncode": proc.returncode if proc else None,
        "cleanup": clean, "wall_limit_s": wall_s, "rss_guard_mib": rss_mib,
        "guard_policy": "sampled process-family and controller RSS; unsampled peaks are unknown",
    }
    dump(out / "rss_samples.json", {"samples": samples})
    dump(out / "resource.json", receipt)
    return receipt


def run(job_path, cache=None):
    job_path = Path(job_path).resolve(strict=True)
    job = read(job_path)
    out = Path(job["output_path"]).resolve(strict=True)
    if job_path != out / "job.json":
        raise ValueError("job.json must reside inside its output directory")
    if not __debug__:
        raise RuntimeError("Python assertions must be enabled")
    if float(job["complete_budget_s"]) != 30 or float(job["memory_guard_mib"]) != 3072:
        raise ValueError("This entry point uses the 30 s / 3072 MiB limits")
    if job.get("preparation_mode") == "AUTHENTICATED_ARTIFACT" and cache is None:
        raise ValueError("Authenticated preparation requires --cache")
    if job.get("preparation_mode") == "COLD_FAST" and cache is not None:
        raise ValueError("Cold preparation does not accept --cache")
    env = {key: value for key, value in os.environ.items() if not key.startswith("PYTHON")}
    env.pop("WFG_OWNER_PREPARED_CACHE", None)
    env.update(PYTHONDONTWRITEBYTECODE="1", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
               MKL_NUM_THREADS="1", VECLIB_MAXIMUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    if cache is not None:
        env["WFG_OWNER_PREPARED_CACHE"] = str(Path(cache).absolute())
    before = sha(job_path)
    receipt = supervise([sys.executable, "-B", str(HERE / "update.py"), str(job_path)], out, env,
                        bound_job=job_path, job_sha256=before)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", help="Prepared job.json in a new output directory")
    parser.add_argument("--cache", help="Authenticated graph cache used during job preparation")
    args = parser.parse_args()
    try:
        result = run(args.job, args.cache)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        parser.exit(2, f"Cannot run job: {error}\n")
    print(json.dumps(result, indent=2))
    return 0 if result["accepted_execution"] else 1


if __name__ == "__main__":
    sys.exit(main())
