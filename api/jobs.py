"""Asynchronous jobs on a spawn-context process pool (default workers = physical cores - 2).

Route checks are CPU bound and the kit controller launches workers with preexec_fn and process groups, so every check
runs in a pool worker process, never in a server thread. A feeder thread keeps at most ``workers`` tasks in flight, so
a task is ``running`` exactly while it occupies a worker; single route checks (priority 0) are scheduled ahead of
dispatch-plan attempts (priority 1). Job records live in memory and are mirrored to <runtime>/jobs/<id>/job.json.

Frozen lifecycle rule: no new kit launch after an attempt whose process cleanup was not confirmed. Besides a ``tainted``
result reported by the worker, a ``route_check`` task whose future fails at the pool level (the worker died, or its result
never came back) left its attempt without the controller's cleanup, so launches pause then too. Jobs that a previous
server process left queued or running never resume; on start-up they are recorded as failed (``SERVER_RESTARTED``).
"""
from __future__ import annotations

import itertools
import json
import multiprocessing as mp
import queue
import threading
import uuid
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .provenance import utc_now


def _init_worker():
    import os
    os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    from . import config  # noqa: F401  (puts integration/src first on sys.path)
    parent = os.getppid()

    def _watch():                        # exit when the server dies, instead of lingering as an orphan
        import time
        while True:
            time.sleep(2)
            if os.getppid() != parent:
                os._exit(0)
    threading.Thread(target=_watch, name="wfg-parent-watch", daemon=True).start()


def _ready():
    import sys
    return sys.path[:1]


def _execute(spec):
    from .runner import execute
    return execute(spec)


def _build_zone_packet(spec):
    from .runner import build_zone_packet
    return build_zone_packet(spec)


TASKS = {"route_check": _execute, "zone_packet": _build_zone_packet}
LAUNCHING_TASKS = {"route_check"}      # task kinds that start a kit attempt (and so need the controller's cleanup)
MAX_FINISHED_IN_MEMORY = 2000          # finished route-check records kept in memory; older ones are read from job.json
MAX_QUEUED_TASKS = 20000               # beyond this POST returns 503 BUSY


class JobManager:
    def __init__(self, runtime_dir: Path, workers: int):
        self.runtime_dir = Path(runtime_dir)
        (self.runtime_dir / "jobs").mkdir(parents=True, exist_ok=True)
        self.workers = workers
        self.pool = self._new_pool()
        self.pool_restarts = 0
        self.paused: str | None = None       # frozen lifecycle rule: no new launch after an unconfirmed cleanup
        self._finished: list = []            # finished job ids, oldest first (memory bound; records stay on disk)
        self.interrupted = self._fail_interrupted()
        self.jobs: dict[str, dict] = {}
        self.lock = threading.RLock()
        self._q: queue.PriorityQueue = queue.PriorityQueue()
        self._seq = itertools.count()
        self._slots = threading.Semaphore(workers)
        self._stop = threading.Event()
        self._feeder = threading.Thread(target=self._feed, name="wfg-feeder", daemon=True)
        self._feeder.start()

    def _new_pool(self) -> ProcessPoolExecutor:
        pool = ProcessPoolExecutor(max_workers=self.workers, mp_context=mp.get_context("spawn"), initializer=_init_worker)
        # start every worker now, while sys.path is clean, so later imports in the server cannot leak into workers
        for f in [pool.submit(_ready) for _ in range(self.workers)]:
            f.result(timeout=120)
        return pool

    def _ensure_pool(self):
        """A worker that dies (e.g. killed by the OS) breaks a ProcessPoolExecutor for good; rebuild it once broken."""
        if getattr(self.pool, "_broken", False):
            try:
                self.pool.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass
            self.pool = self._new_pool()
            self.pool_restarts += 1

    def _fail_interrupted(self) -> int:
        """Jobs a previous server process left queued or running never resume: record them as failed (never safe)."""
        n = 0
        for p in sorted((self.runtime_dir / "jobs").glob("*/job.json")):
            try:
                job = json.loads(p.read_text())
            except ValueError:
                continue
            if isinstance(job, dict) and job.get("status") in ("queued", "running") and "job_id" in job:
                job.update(status="failed", finished_at=utc_now(), result=None,
                           error={"code": "SERVER_RESTARTED",
                                  "message": "the API restarted before this job finished; it was not resumed. Treat it as "
                                             "unresolved (never safe) and submit it again."})
                self._persist(job)
                n += 1
        return n

    # ---- records -----------------------------------------------------------------------------------------------
    def new_id(self, prefix: str) -> str:
        return "%s_%s" % (prefix, uuid.uuid4().hex[:20])

    def job_dir(self, job_id: str) -> Path:
        return self.runtime_dir / "jobs" / job_id

    def put(self, job: dict):
        with self.lock:
            self.jobs[job["job_id"]] = job
            self._persist(job)

    def get(self, job_id: str):
        with self.lock:
            j = self.jobs.get(job_id)
            if j is not None:
                return json.loads(json.dumps(j, default=str))
        p = self.job_dir(job_id) / "job.json"           # evicted finished job: served from its persisted record
        if "/" not in job_id and ".." not in job_id and p.is_file():
            try:
                return json.loads(p.read_text())
            except ValueError:
                return None
        return None

    def update(self, job_id: str, **fields):
        with self.lock:
            j = self.jobs[job_id]
            j.update(fields)
            self._persist(j)
            if fields.get("status") in ("done", "failed") and j.get("kind") == "route_check":
                self._finished.append(job_id)
                while len(self._finished) > MAX_FINISHED_IN_MEMORY:
                    self.jobs.pop(self._finished.pop(0), None)

    def pause(self, reason: str):
        with self.lock:
            if self.paused is None:
                self.paused = reason

    def _persist(self, job: dict):
        d = self.job_dir(job["job_id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "job.json.tmp"
        tmp.write_text(json.dumps(job, indent=1, default=str))
        tmp.replace(d / "job.json")

    def counts(self) -> dict:
        with self.lock:
            out = {}
            for j in self.jobs.values():
                out[j["status"]] = out.get(j["status"], 0) + 1
            return out

    # ---- scheduling ----------------------------------------------------------------------------------------------
    def schedule(self, kind: str, spec: dict, on_start, on_done, priority: int = 0):
        """Queue ``spec`` for TASKS[kind]; ``on_start()`` runs when it enters a worker, ``on_done(result|None, exc|None)``."""
        self._q.put((priority, next(self._seq), kind, spec, on_start, on_done))

    def _feed(self):
        while not self._stop.is_set():
            try:
                item = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            _, _, kind, spec, on_start, on_done = item
            # hold while paused; re-check after taking a slot, because the task that frees the slot decides on the
            # pause before releasing it (a launch never slips through between a failed attempt and its pause)
            while True:
                while self.paused is not None and not self._stop.is_set():
                    self._stop.wait(1.0)
                self._slots.acquire()
                if self.paused is None or self._stop.is_set():
                    break
                self._slots.release()
            if self._stop.is_set():
                self._slots.release()
                break
            try:
                on_start()
            except Exception:
                pass
            try:
                self._ensure_pool()
                fut = self.pool.submit(TASKS[kind], spec)
            except Exception as exc:   # pool broken or shut down: nothing was launched
                self._slots.release()
                on_done(None, exc)
                continue

            def _done(f, on_done=on_done, kind=kind, spec=spec):
                try:
                    try:
                        res, err = f.result(), None
                    except BaseException as exc:     # worker died or the task raised (SystemExit included)
                        res, err = None, exc
                        if kind in LAUNCHING_TASKS:  # the attempt never got the controller's cleanup
                            self.pause("a pool worker failed while running %s task %s (%s); its kit attempt's process "
                                       "cleanup was not confirmed, so new launches are paused as the frozen controller "
                                       "requires. Check for leftover processes, then restart the API."
                                       % (kind, spec.get("job_id", "?"), type(exc).__name__))
                    try:
                        on_done(res, err)
                    except Exception:
                        import traceback
                        traceback.print_exc()
                    if kind in LAUNCHING_TASKS and isinstance(res, dict) and res.get("tainted"):
                        self.pause("kit attempt of %s task %s: process cleanup was not confirmed CLEAN; new launches are "
                                   "paused as the frozen controller requires. Check for leftover processes, then restart "
                                   "the API." % (kind, spec.get("job_id", "?")))
                finally:
                    self._slots.release()        # only after the pause decision, so the feeder sees it
            fut.add_done_callback(_done)

    def queued(self) -> int:
        return self._q.qsize()

    def shutdown(self):
        self._stop.set()
        self.pool.shutdown(wait=False, cancel_futures=True)
