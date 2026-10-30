"""Bounded execution-availability probes, never a forecast-validity study."""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import tempfile
import time


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now(): return datetime.now(timezone.utc).isoformat()


def probe(binary, folder, timeout):
    started = now(); tic = time.monotonic()
    p = subprocess.Popen([str(binary)], cwd=folder, stdin=subprocess.DEVNULL,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    timed_out = False; cleanup = []
    try:
        stdout, stderr = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True; os.killpg(p.pid, signal.SIGKILL)
        cleanup.append("Killed only probe-owned process group on timeout")
        stdout, stderr = p.communicate()
    finally:
        # A child surviving the leader still belongs to this fresh probe group.
        try:
            os.killpg(p.pid, 0)
        except ProcessLookupError:
            cleanup.append("Probe-owned process group absent after completion")
        else:
            os.killpg(p.pid, signal.SIGKILL)
            cleanup.append("Killed surviving probe-owned process group")
    stdout_path = folder/"stdout.txt"; stderr_path = folder/"stderr.txt"
    stdout_path.write_bytes(stdout); stderr_path.write_bytes(stderr)
    return {"command": [str(binary)], "cwd": str(folder), "stdin": "DEVNULL", "timeout_s": timeout,
            "started_utc": started, "ended_utc": now(), "elapsed_s": time.monotonic()-tic,
            "pid": p.pid, "process_group": p.pid, "exit_code": p.returncode,
            "timed_out": timed_out, "cleanup": cleanup,
            "stdout": stdout.decode("utf-8", errors="replace"), "stderr": stderr.decode("utf-8", errors="replace"),
            "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
            "stdout_path": str(stdout_path), "stderr_path": str(stderr_path)}


def main():
    p = argparse.ArgumentParser(); p.add_argument("--native-root", type=Path, required=True)
    p.add_argument("--work-root", type=Path, required=True); p.add_argument("--out", type=Path, required=True)
    p.add_argument("--timeout-s", type=int, default=5); a = p.parse_args()
    if not 1 <= a.timeout_s <= 15: raise ValueError("Short positive timeout required")
    native = a.native_root.resolve(); a.work_root.mkdir(parents=True, exist_ok=True)
    workspace = Path(tempfile.mkdtemp(prefix="native-farsite-probe-", dir=a.work_root.resolve()))
    manifest = native/"EXTRACTION_MANIFEST.json"; rows = {r["path"]: r for r in json.loads(manifest.read_text())["files"]}
    paths = ["src/TestFARSITE", "src/TestFARSITE.cpp", "observed_clock_probe", "observed_clock_probe.cpp", "observed_build_manifest.json"]
    identities = {}
    for rel in paths:
        digest = sha(native/rel)
        if digest != rows[rel]["sha256"]: raise ValueError("Archive extraction identity mismatch: "+rel)
        identities[rel] = {"sha256": digest, "expected_sha256": rows[rel]["sha256"]}
    usage_folder = workspace/"usage"; usage_folder.mkdir()
    usage = probe(native/"src/TestFARSITE", usage_folder, a.timeout_s)
    usage["expected_behavior"] = "No-argument linuxMain prints usage then exit(1), source TestFARSITE.cpp lines841-863"
    usage["pass"] = not usage["timed_out"] and usage["exit_code"] == 1 and "TestFARSITE Usage:" in usage["stdout"]
    lock_path = Path("/tmp/wfg/HEAVY.lock"); lock_path.parent.mkdir(parents=True, exist_ok=True)
    clock = {"status": "NOT_RUN_HEAVY_LOCK_BUSY", "lock_path": str(lock_path)}
    with lock_path.open("a+") as lease:
        try: fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: pass
        else:
            try:
                acquired = now(); clock_folder = workspace/"clock"; clock_folder.mkdir()
                clock = probe(native/"observed_clock_probe", clock_folder, a.timeout_s)
                expected = {"start_hhmm": 802, "end_hhmm": 214, "duration_minutes": 1092}
                try: actual = json.loads(clock["stdout"])
                except json.JSONDecodeError: actual = None
                clock.update(expected_fixture=expected, observed_fixture=actual,
                             pass_check=not clock["timed_out"] and clock["exit_code"] == 0 and actual == expected,
                             lock_path=str(lock_path), lease_acquired_utc=acquired)
                clock["status"] = "PASS_CLOCK_FIXTURE" if clock["pass_check"] else "FAIL_CLOCK_FIXTURE"
            finally:
                fcntl.flock(lease, fcntl.LOCK_UN)
                clock["lease_released_utc"] = now()
    report = {"scope": "Execution availability and optional embedded clock fixture only; no spread forecast, physical validation or routing risk",
              "host": platform.platform(), "software_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "producer_sha256": sha(Path(__file__)), "extraction_manifest_sha256": sha(manifest), "identities": identities,
              "working_directory": str(workspace), "usage": usage, "clock": clock,
              "availability": "EXECUTES_USAGE_ON_CURRENT_HOST" if usage["pass"] else "UNRESOLVED_EXECUTION_AVAILABILITY"}
    a.out.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"availability": report["availability"], "usage_exit": usage["exit_code"], "clock": clock["status"]}))
    return 0 if usage["pass"] else 1


if __name__ == "__main__": raise SystemExit(main())
