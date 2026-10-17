"""Job manager robustness: a task that raises SystemExit (as the frozen controller does on a pre-launch hash mismatch)
must fail only that job, and later jobs must still run."""
import threading

import pytest

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


@pytest.mark.parametrize("action", ["die", "taint"])
def test_no_launch_slips_through_after_a_failed_attempt(tmp_path, monkeypatch, action):
    """A route check queued behind a dying (or tainted) attempt must not start: the pause comes before the slot is freed."""
    monkeypatch.setitem(J.TASKS, "route_check", _pool_tasks.scripted)
    jm = J.JobManager(tmp_path, workers=1)
    try:
        first, started = threading.Event(), threading.Event()
        jm.schedule("route_check", {"action": action, "job_id": "rc_first"}, lambda: None, lambda r, e: first.set())
        jm.schedule("route_check", {"action": "echo", "job_id": "rc_second"}, started.set, lambda r, e: None)
        assert first.wait(120)
        assert not started.wait(4)                 # the queued attempt never reached on_start
        assert jm.paused and "rc_first" in jm.paused
    finally:
        jm.shutdown()


@pytest.mark.parametrize("attempt", range(2))
def test_no_launch_slips_through_when_another_task_frees_the_slot(tmp_path, monkeypatch, attempt):
    """workers=2: a non-launching task (zone packet stand-in) is in flight next to a route check whose worker dies.

    The broken pool fails both futures; the non-launching one may free its slot first. The queued route check must
    still not start: the feeder settles the pool (which waits for every failure callback, so the pause is set) and
    checks the pause before starting anything.
    """
    monkeypatch.setitem(J.TASKS, "route_check", _pool_tasks.scripted)
    monkeypatch.setitem(J.TASKS, "t_sleep", _pool_tasks.sleep_then_echo)
    jm = J.JobManager(tmp_path, workers=2)
    try:
        done_a, started_b = threading.Event(), threading.Event()
        jm.schedule("t_sleep", {"sleep_s": 3.0}, lambda: None, lambda r, e: None)
        import time
        time.sleep(0.5)                            # the non-launching task holds the first slot
        jm.schedule("route_check", {"action": "die", "job_id": "rc_dies"}, lambda: None, lambda r, e: done_a.set())
        jm.schedule("route_check", {"action": "echo", "job_id": "rc_queued"}, started_b.set, lambda r, e: None)
        assert done_a.wait(120)
        assert not started_b.wait(5)
        assert jm.paused and "rc_dies" in jm.paused
    finally:
        jm.shutdown()


class _FakeFuture:
    def __init__(self, result):
        self._result = result

    def add_done_callback(self, fn):
        fn(self)

    def result(self):
        return self._result


class _FakePool:
    """Stand-in for ProcessPoolExecutor: records submissions; can look broken or hold a dead worker."""

    def __init__(self, broken=False, dead_worker=False, on_shutdown=None):
        self._broken = broken
        self._processes = {1: type("P", (), {"exitcode": 1 if dead_worker else None})()}
        self.on_shutdown = on_shutdown
        self.submitted = []

    def shutdown(self, wait=False, cancel_futures=False):
        if self.on_shutdown:
            self.on_shutdown()

    def submit(self, fn, spec):
        self.submitted.append(spec)
        return _FakeFuture({"status": "done"})


def _manager_with(tmp_path, monkeypatch, pool):
    fresh = _FakePool()
    monkeypatch.setattr(J.JobManager, "_new_pool", lambda self: fresh)
    jm = J.JobManager(tmp_path, workers=1)
    jm.pool = pool
    return jm, fresh


def test_feeder_settles_the_pool_before_checking_the_pause(tmp_path, monkeypatch):
    """The pause a dying attempt sets while the broken pool is being shut down must stop the next launch (v1.8 order)."""
    holder = {}
    broken = _FakePool(broken=True, on_shutdown=lambda: holder["jm"].pause("rc_dead: worker died"))
    jm, fresh = _manager_with(tmp_path, monkeypatch, broken)
    holder["jm"] = jm
    try:
        started = threading.Event()
        jm.schedule("route_check", {"job_id": "rc_next"}, started.set, lambda r, e: None)
        assert not started.wait(3)
        assert fresh.submitted == [] and jm.paused == "rc_dead: worker died"
    finally:
        jm.shutdown()


def test_feeder_never_submits_into_a_pool_with_a_dead_worker(tmp_path, monkeypatch):
    """A dead worker the executor has not registered (its manager thread is busy) blocks the launch; on timeout the job
    fails as unresolved without starting, and launches pause."""
    monkeypatch.setattr(J.JobManager, "SETTLE_WAIT_S", 1.0)
    pool = _FakePool(dead_worker=True)
    jm, _ = _manager_with(tmp_path, monkeypatch, pool)
    try:
        started, done = threading.Event(), {}
        ev = threading.Event()

        def on_done(res, exc):
            done["r"] = (res, exc)
            ev.set()
        jm.schedule("route_check", {"job_id": "rc_next"}, started.set, on_done)
        assert ev.wait(30)
        assert not started.is_set() and pool.submitted == []
        assert done["r"][0] is None and isinstance(done["r"][1], RuntimeError)
        assert jm.paused and "did not register" in jm.paused
    finally:
        jm.shutdown()
