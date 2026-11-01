"""Program rule 6 for the test suite itself: it refuses to start beside a timed run (tests/conftest.py). Each case runs
a collect-only pytest of one light file in a child process against a private lock file (WFG_BENCH_LOCK)."""
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCHLOCK = HERE.parents[1] / "program" / "benchlock.py"


def _pytest(env, under_lock=False):
    cmd = [sys.executable, "-m", "pytest", "-q", "--co", "-p", "no:cacheprovider", str(HERE / "test_schema.py")]
    if under_lock:
        cmd = [sys.executable, str(BENCHLOCK), "--label", "unit-test-suite", "--", *cmd]
    out = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
    return out.returncode, out.stdout + out.stderr


def test_the_suite_runs_only_under_the_bench_lock_and_never_beside_a_timed_run(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "EVACPLAN_TESTS_UNLOCKED"}
    env["WFG_BENCH_LOCK"] = str(tmp_path / "bench.lock")
    code, text = _pytest(env)                                       # lock free, not under it: refused
    assert code == 75 and "does not run under the shared bench lock" in text, text
    code, text = _pytest(env, under_lock=True)                      # benchlock.py -- pytest: runs
    assert code == 0, text
    code, text = _pytest({**env, "EVACPLAN_TESTS_UNLOCKED": "1"})   # light selection, nothing queued: runs
    assert code == 0, text
    hold = (f"import importlib.util, time\n"
            f"s = importlib.util.spec_from_file_location('benchlock', {str(BENCHLOCK)!r})\n"
            f"m = importlib.util.module_from_spec(s)\ns.loader.exec_module(m)\n"
            f"with m.bench_lock('timed-run'):\n    time.sleep(120)\n")
    holder = subprocess.Popen([sys.executable, "-c", hold], env=env)   # one process: killing it frees the lock
    try:
        deadline = time.monotonic() + 30
        while "timed-run" not in (tmp_path / "bench.lock").read_text(errors="ignore") and time.monotonic() < deadline:
            time.sleep(0.05)
        code, text = _pytest({**env, "EVACPLAN_TESTS_UNLOCKED": "1"})   # someone else holds it: refused anyway
        assert code == 75 and "held by: timed-run" in text, text
    finally:
        holder.kill()
        holder.wait(timeout=30)
