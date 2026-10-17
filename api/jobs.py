"""Asynchronous jobs on a spawn-context process pool (default workers = physical cores - 2).

Route checks are CPU bound and the kit controller launches workers with preexec_fn and process groups, so every check
runs in a pool worker process, never in a server thread. A feeder thread keeps at most ``workers`` tasks in flight, so
a task is ``running`` exactly while it occupies a worker; single route checks (priority 0) are scheduled ahead of
dispatch-plan attempts (priority 1). Job records live in memory and are mirrored to <runtime>/jobs/<id>/job.json.
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


class JobManager:
    def __init__(self, runtime_dir: Path, workers: int):
        self.runtime_dir = Path(runtime_dir)
        (self.runtime_dir / "jobs").mkdir(parents=True, exist_ok=True)
        self.workers = workers
        self.pool = ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("spawn"), initializer=_init_worker)
        self.jobs: dict[str, dict] = {}
        self.lock = threading.RLock()
        self._q: queue.PriorityQueue = queue.PriorityQueue()
        self._seq = itertools.count()
        self._slots = threading.Semaphore(workers)
        self._stop = threading.Event()
        # start every worker now, while sys.path is clean, so later imports in the server cannot leak into workers
        for f in [self.pool.submit(_ready) for _ in range(workers)]:
            f.result(timeout=120)
        self._feeder = threading.Thread(target=self._feed, name="wfg-feeder", daemon=True)
        self._feeder.start()

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
            return None if j is None else json.loads(json.dumps(j, default=str))

    def update(self, job_id: str, **fields):
        with self.lock:
            j = self.jobs[job_id]
            j.update(fields)
            self._persist(j)

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
            self._slots.acquire()
            try:
                on_start()
            except Exception:
                pass
            try:
                fut = self.pool.submit(TASKS[kind], spec)
            except Exception as exc:   # pool broken or shut down
                self._slots.release()
                on_done(None, exc)
                continue

            def _done(f, on_done=on_done):
                self._slots.release()
                try:
                    res, err = f.result(), None
                except Exception as exc:     # worker process died or task raised
                    res, err = None, exc
                try:
                    on_done(res, err)
                except Exception:
                    import traceback
                    traceback.print_exc()
            fut.add_done_callback(_done)

    def queued(self) -> int:
        return self._q.qsize()

    def shutdown(self):
        self._stop.set()
        self.pool.shutdown(wait=False, cancel_futures=True)
