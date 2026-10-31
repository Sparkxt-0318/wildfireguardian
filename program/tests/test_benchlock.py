"""The bench lock must serialize timed runs across processes (and therefore worktrees)."""
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

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
