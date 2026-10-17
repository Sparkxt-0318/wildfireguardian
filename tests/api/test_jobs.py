"""Job manager robustness: a task that raises SystemExit (as the frozen controller does on a pre-launch hash mismatch)
must fail only that job, and later jobs must still run."""
import threading

from api import jobs as J

from . import _pool_tasks


def test_system_exit_does_not_wedge_the_pool(tmp_path, monkeypatch):
    monkeypatch.setitem(J.TASKS, "t_exit", _pool_tasks.raise_system_exit)
    monkeypatch.setitem(J.TASKS, "t_echo", _pool_tasks.echo)
    jm = J.JobManager(tmp_path, workers=1)
    try:
        got, done = {}, {k: threading.Event() for k in ("a", "b")}

        def cb(key):
            def on_done(res, exc):
                got[key] = (res, exc)
                done[key].set()
            return on_done
        jm.schedule("t_exit", {}, lambda: None, cb("a"))
        jm.schedule("t_echo", {"x": 1}, lambda: None, cb("b"))
        assert done["a"].wait(120) and done["b"].wait(120)
        assert got["a"][0] is None and isinstance(got["a"][1], BaseException)
        assert got["b"][0] == {"status": "done", "echo": {"x": 1}}
    finally:
        jm.shutdown()


def test_paused_manager_holds_new_launches(tmp_path, monkeypatch):
    monkeypatch.setitem(J.TASKS, "t_echo", _pool_tasks.echo)
    jm = J.JobManager(tmp_path, workers=1)
    try:
        jm.pause("cleanup not confirmed")
        ev = threading.Event()
        jm.schedule("t_echo", {}, lambda: None, lambda r, e: ev.set())
        assert not ev.wait(3)                      # held while paused (frozen lifecycle rule)
        assert jm.paused == "cleanup not confirmed"
    finally:
        jm.shutdown()
