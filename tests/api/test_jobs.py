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


def test_dead_worker_during_a_route_check_pauses_launches(tmp_path, monkeypatch):
    """A route-check worker that dies leaves its kit attempt without the controller's cleanup: launches must pause."""
    monkeypatch.setitem(J.TASKS, "route_check", _pool_tasks.die)
    monkeypatch.setitem(J.TASKS, "t_echo", _pool_tasks.echo)
    jm = J.JobManager(tmp_path, workers=1)
    try:
        got, ev = {}, threading.Event()

        def on_done(res, exc):
            got["r"] = (res, exc)
            ev.set()
        jm.schedule("route_check", {}, lambda: None, on_done)
        assert ev.wait(120)
        assert got["r"][0] is None and isinstance(got["r"][1], BaseException)
        assert jm.paused and "cleanup" in jm.paused
        held = threading.Event()
        jm.schedule("t_echo", {}, lambda: None, lambda r, e: held.set())
        assert not held.wait(3)                    # no new launch until the API is restarted
    finally:
        jm.shutdown()


def test_dead_worker_in_a_non_launching_task_does_not_pause(tmp_path, monkeypatch):
    monkeypatch.setitem(J.TASKS, "t_die", _pool_tasks.die)
    monkeypatch.setitem(J.TASKS, "t_echo", _pool_tasks.echo)
    jm = J.JobManager(tmp_path, workers=1)
    try:
        ev = {k: threading.Event() for k in ("a", "b")}
        got = {}
        jm.schedule("t_die", {}, lambda: None, lambda r, e: ev["a"].set())
        assert ev["a"].wait(120)
        assert jm.paused is None

        def on_b(res, exc):
            got["b"] = res
            ev["b"].set()
        jm.schedule("t_echo", {"x": 2}, lambda: None, on_b)
        assert ev["b"].wait(120) and got["b"] == {"status": "done", "echo": {"x": 2}}
        assert jm.pool_restarts == 1               # the broken pool was rebuilt for the next task
    finally:
        jm.shutdown()


def test_jobs_left_running_by_a_previous_server_are_failed_on_start(tmp_path):
    import json
    jobs = tmp_path / "jobs"
    for jid, status in (("rc_a", "running"), ("rc_b", "queued"), ("rc_c", "done"), ("dp_d", "running")):
        (jobs / jid).mkdir(parents=True)
        (jobs / jid / "job.json").write_text(json.dumps({"job_id": jid, "status": status, "result": {"verdict": "x"} if status == "done" else None,
                                                         "error": None, "finished_at": None}))
    jm = J.JobManager(tmp_path, workers=1)
    try:
        assert jm.interrupted == 3
        for jid in ("rc_a", "rc_b", "dp_d"):
            j = jm.get(jid)
            assert j["status"] == "failed" and j["result"] is None and j["error"]["code"] == "SERVER_RESTARTED"
            assert j["finished_at"]
        assert jm.get("rc_c")["status"] == "done" and jm.get("rc_c")["result"] == {"verdict": "x"}
    finally:
        jm.shutdown()
