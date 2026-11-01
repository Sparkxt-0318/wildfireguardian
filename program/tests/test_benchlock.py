"""The bench lock must serialize timed runs across processes (and therefore worktrees)."""
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("benchlock", HERE / "benchlock.py")
benchlock = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchlock)


def test_two_processes_do_not_overlap(tmp_path, monkeypatch):
    lock = tmp_path / "bench.lock"
    monkeypatch.setenv("WFG_BENCH_LOCK", str(lock))
    log = tmp_path / "log.txt"
    # Each child appends "start <i>" then sleeps then "end <i>"; overlap would interleave.
    child = (
        "import sys,time; p=sys.argv[1]; i=sys.argv[2]\n"
        "open(p,'a').write(f'start {i}\\n'); time.sleep(0.4); open(p,'a').write(f'end {i}\\n')\n"
    )
    procs = [
        subprocess.Popen([sys.executable, str(HERE / "benchlock.py"), "--", sys.executable, "-c", child, str(log), str(i)],
                         env={**__import__("os").environ, "WFG_BENCH_LOCK": str(lock)})
        for i in range(3)
    ]
    for p in procs:
        assert p.wait(timeout=30) == 0
    lines = log.read_text().split()
    pairs = [lines[k:k + 4] for k in range(0, len(lines), 4)]
    for start, i, end, j in pairs:
        assert (start, end) == ("start", "end") and i == j, lines


def test_wait_max_gives_up_before_starting_the_command(tmp_path, monkeypatch):
    """A background job with a hard time limit must not be killed mid-run because it queued too long:
    with --wait-max it gives up (exit 75) without starting the command, and runs normally once free."""
    lock = tmp_path / "bench.lock"
    monkeypatch.setenv("WFG_BENCH_LOCK", str(lock))
    marker = tmp_path / "ran"
    cmd = [sys.executable, str(HERE / "benchlock.py"), "--wait-max", "0.5", "--",
           sys.executable, "-c", f"open({str(marker)!r}, 'w')"]
    env = {**os.environ, "WFG_BENCH_LOCK": str(lock)}
    with benchlock.bench_lock("unit-test-holder"):
        t0 = time.monotonic()
        out = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
        took = time.monotonic() - t0
    assert out.returncode == benchlock.EXIT_NOT_ACQUIRED == 75, out.stderr
    assert not marker.exists()
    assert "not acquired" in out.stderr and "unit-test-holder" in out.stderr
    assert 0.4 <= took < 15
    out = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert marker.exists()


def test_wait_max_still_queues_behind_a_short_holder(tmp_path, monkeypatch):
    lock = tmp_path / "bench.lock"
    monkeypatch.setenv("WFG_BENCH_LOCK", str(lock))
    env = {**os.environ, "WFG_BENCH_LOCK": str(lock)}
    holder = subprocess.Popen([sys.executable, str(HERE / "benchlock.py"), "--label", "short-holder", "--",
                               sys.executable, "-c", "import time; time.sleep(1.0)"], env=env)
    deadline = time.monotonic() + 15
    while benchlock.holder() == "" and time.monotonic() < deadline:
        time.sleep(0.02)
    assert "short-holder" in benchlock.holder()
    out = subprocess.run([sys.executable, str(HERE / "benchlock.py"), "--wait-max", "20", "--",
                          sys.executable, "-c", "print('ran')"], env=env, capture_output=True, text=True, timeout=60)
    assert holder.wait(timeout=30) == 0
    assert out.returncode == 0 and out.stdout.strip() == "ran", out.stderr


def test_python_api_wait_max_raises_and_releases(tmp_path, monkeypatch):
    monkeypatch.setenv("WFG_BENCH_LOCK", str(tmp_path / "bench.lock"))
    with benchlock.bench_lock("outer"):
        with pytest.raises(benchlock.LockTimeout):
            with benchlock.bench_lock("inner", wait_max=0.2):
                raise AssertionError("the inner block must not run while the lock is held")
        assert "outer" in benchlock.holder()
    assert benchlock.holder() == ""
    with benchlock.bench_lock("again", wait_max=0.2) as waited:
        assert waited < 0.2


def test_status_reports_free_and_holder(tmp_path, monkeypatch):
    monkeypatch.setenv("WFG_BENCH_LOCK", str(tmp_path / "bench.lock"))
    assert benchlock.holder() == ""
    with benchlock.bench_lock("unit-test-label") as waited:
        assert waited >= 0
        # A second process sees the holder label.
        out = subprocess.run([sys.executable, str(HERE / "benchlock.py"), "--status"],
                             capture_output=True, text=True,
                             env={**__import__("os").environ, "WFG_BENCH_LOCK": str(tmp_path / "bench.lock")})
        assert "unit-test-label" in out.stdout
    assert benchlock.holder() == ""
