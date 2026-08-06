"""An asynchronous job model, in plain Python and with no web server.

Round-3 PHASE 19 STEP 1, decision ①.

WHY ASYNCHRONOUS AT ALL
-----------------------
The scan takes about 27 seconds. Three things follow, and each one on its own
would be enough:

1. A browser that blocks for 27 seconds looks broken, and an operator who
   believes the console is broken during a wildfire falls back to their own
   judgement — which is the failure this project exists to remove.
2. A synchronous request holds its connection open for 27 seconds, so a proxy
   with a 30-second read timeout is one slow machine away from cutting the
   answer off at the last second.
3. Nothing can be reported WHILE it runs. The per-origin counter is the only
   honest way to say "this is going to take half a minute" and be believed.

So: submit returns immediately with an id, the work happens on a worker, and
the id answers three questions — where is it, what did it produce, and what
went wrong.

⚠ NO WEB SERVER IS INTRODUCED HERE. This module has no HTTP, no framework and
no port. It is the layer a transport would sit on, built and tested first so
that when a transport is added the thing underneath it is already known to
work.

WHAT THREADS BUY, AND WHAT THEY DO NOT
--------------------------------------
Workers are threads. Two concurrent jobs are therefore SAFE — they share
read-only resources, they write to per-job directories, and each carries its
own progress — but they are not FASTER: the scan is pure-Python networkx
Dijkstra, so the GIL serialises it, and two jobs take about twice as long as
one. The default worker count is 1 for that reason. Raising it makes the second
request start immediately rather than after the first finishes, which is a
latency answer, not a throughput one. Real parallelism needs processes, and
processes need the resource cache to be per-process — a decision with a memory
bill attached, and one this PHASE deliberately leaves to the next.

CANCELLATION IS COOPERATIVE, AND THAT IS WHY IT LEAVES NOTHING BEHIND
--------------------------------------------------------------------
A demonstration cannot spend 26 seconds on a misclick, so :meth:`JobRunner.cancel`
reaches a scan that has already started. It sets a flag; the scan reads it at an
origin boundary and raises. Two consequences follow, and both are the reason it
is done this way rather than by killing a thread:

* the stop lands within about one origin — some tens of milliseconds — which is
  indistinguishable from instant to the person who clicked;
* **nothing has been written.** Routing precedes every write in a run, so a
  cancel inside it cannot produce a partial dispatch list, and the run
  directory the job reserved is removed if it is still empty.

A cancelled job is reported as ``cancelled``, never as ``failed``: the caller
asked for it, so it is not an error for anyone to go looking into.
"""

from __future__ import annotations

import queue
import threading
import traceback
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..live.pipeline import RoutingCancelled
from . import guards
from .params import RoutingParams
from .progress import Progress, TRIGGER_STAGES
from .resources import ResourceCache
from .routing import IgnitionRequest, ServiceError, route_from_ignition

#: Job lifecycle. A job is in exactly one of these at any moment.
QUEUED = "queued"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
CANCELLED = "cancelled"

TERMINAL: frozenset[str] = frozenset({SUCCEEDED, FAILED, CANCELLED})

_STATE_KO = {
    QUEUED: "대기",
    RUNNING: "실행 중",
    SUCCEEDED: "완료",
    FAILED: "실패",
    CANCELLED: "취소됨",
}


class QueueFull(RuntimeError):
    """The queue is at capacity. Better than an unbounded queue that pretends."""


@dataclass
class Job:
    """One unit of work and everything anyone can ask about it."""

    job_id: str
    kind: str
    request: dict
    state: str = QUEUED
    submitted_utc: str = ""
    started_utc: str | None = None
    finished_utc: str | None = None
    result: dict | None = None
    error: str | None = None
    error_code: str | None = None
    traceback: str | None = None
    progress: Progress = field(default_factory=lambda: Progress(TRIGGER_STAGES))
    _cancel: threading.Event = field(default_factory=threading.Event)

    @property
    def state_ko(self) -> str:
        return _STATE_KO.get(self.state, self.state)

    def status(self, *, with_result: bool = False) -> dict:
        """The status payload. Safe to call from any thread, at any time."""
        d = {
            "job_id": self.job_id,
            "kind": self.kind,
            "state": self.state,
            "state_ko": self.state_ko,
            "submitted_utc": self.submitted_utc,
            "started_utc": self.started_utc,
            "finished_utc": self.finished_utc,
            "request": self.request,
            "progress": self.progress.snapshot(),
        }
        if self.state in (FAILED, CANCELLED):
            d["error"] = self.error
            d["error_code"] = self.error_code
        if self.state == CANCELLED:
            d["nothing_was_written"] = True
            d["cancel_note_ko"] = (
                "취소된 요청은 산출물을 남기지 않습니다 — 라우팅이 모든 쓰기보다 "
                "앞서고, 예약해 둔 실행 디렉터리는 비어 있으면 삭제됩니다.")
        if with_result and self.state == SUCCEEDED:
            d["result"] = self.result
        return d


class JobStore:
    """In-memory job registry. Thread-safe, bounded, insertion-ordered."""

    def __init__(self, *, max_jobs: int = 256) -> None:
        self._lock = threading.RLock()
        self._jobs: dict[str, Job] = {}
        self._max = int(max_jobs)

    def add(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.job_id] = job
            self._reap()

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self, *, state: str | None = None) -> list[dict]:
        with self._lock:
            return [j.status() for j in self._jobs.values()
                    if state is None or j.state == state]

    def _reap(self) -> None:
        """Drop the oldest TERMINAL jobs once the registry is over budget.

        Running and queued jobs are never dropped: forgetting a job that is
        still working would leave a worker writing into a directory nobody can
        name.
        """
        if len(self._jobs) <= self._max:
            return
        for jid, job in list(self._jobs.items()):
            if len(self._jobs) <= self._max:
                return
            if job.state in TERMINAL:
                del self._jobs[jid]


class JobRunner:
    """A bounded queue and a pool of worker threads.

    Deliberately small: submit, status, result, wait, cancel, shutdown. Every
    method is safe to call from any thread.
    """

    def __init__(self, *, cache: ResourceCache | None = None,
                 max_workers: int = 1, max_queue: int = 32,
                 max_jobs: int = 256) -> None:
        guards.freeze_globals()
        self.cache = cache if cache is not None else ResourceCache(capacity=1)
        self.store = JobStore(max_jobs=max_jobs)
        self._q: queue.Queue[str | None] = queue.Queue(maxsize=int(max_queue))
        self._workers: list[threading.Thread] = []
        self._handlers: dict[str, Callable[[Job], dict]] = {
            "ignition": self._run_ignition,
        }
        self._shutdown = threading.Event()
        for i in range(max(1, int(max_workers))):
            t = threading.Thread(target=self._worker, name=f"wfg-worker-{i}",
                                 daemon=True)
            t.start()
            self._workers.append(t)

    # -- submission --------------------------------------------------------
    def submit_ignition(self, request: IgnitionRequest, *,
                        on_event: Callable[[dict], None] | None = None) -> str:
        """Queue one ignition-point routing job. Returns its id immediately."""
        job_id = uuid.uuid4().hex
        job = Job(job_id=job_id, kind="ignition", request=request.as_dict(),
                  submitted_utc=_now(),
                  progress=Progress(TRIGGER_STAGES, on_event=on_event))
        job._payload = request  # type: ignore[attr-defined]
        self.store.add(job)
        try:
            self._q.put_nowait(job_id)
        except queue.Full:
            job.state = FAILED
            job.error = ("작업 대기열이 가득 찼습니다. 동시 처리 한도를 넘는 "
                         "요청은 받아 두고 잊어버리는 것보다 즉시 거절하는 편이 "
                         "낫습니다.")
            job.error_code = "queue_full"
            job.finished_utc = _now()
            raise QueueFull(job.error) from None
        return job_id

    # -- reading -----------------------------------------------------------
    def status(self, job_id: str) -> dict:
        job = self.store.get(job_id)
        if job is None:
            raise KeyError(f"unknown job_id: {job_id}")
        return job.status()

    def result(self, job_id: str) -> dict:
        job = self.store.get(job_id)
        if job is None:
            raise KeyError(f"unknown job_id: {job_id}")
        if job.state != SUCCEEDED:
            raise ServiceError(
                f"job {job_id} is {job.state}, not {SUCCEEDED}",
                code=f"not_{SUCCEEDED}")
        return job.result or {}

    def wait(self, job_id: str, timeout: float | None = None,
             poll_s: float = 0.05) -> dict:
        """Block until a job leaves the queue-and-run states. Test convenience.

        A transport would poll :meth:`status` instead — that is the point of
        the model. This exists so a script can behave exactly as it did before.
        """
        import time as _time
        job = self.store.get(job_id)
        if job is None:
            raise KeyError(f"unknown job_id: {job_id}")
        deadline = None if timeout is None else _time.monotonic() + timeout
        while job.state not in TERMINAL:
            if deadline is not None and _time.monotonic() > deadline:
                raise TimeoutError(f"job {job_id} still {job.state} after {timeout}s")
            _time.sleep(poll_s)
        return job.status(with_result=True)

    def cancel(self, job_id: str) -> bool:
        """Ask a job to stop. Works while QUEUED and while RUNNING.

        Round-3 PHASE 19 STEP 2. A demonstration cannot wait 26 seconds for a
        misclick, so cancellation reaches a scan that has already started.

        It is COOPERATIVE, not pre-emptive: the flag is read at an origin
        boundary and once more before delivery begins. A cancelled request
        therefore stops within roughly one origin — about 55 ms — and, because
        routing precedes every write, leaves **no partial artifact**. The run
        directory it had reserved is removed if it is still empty.

        Returns ``True`` if the job was asked to stop, ``False`` if it had
        already finished — a finished job cannot be cancelled, and saying
        otherwise would let a caller believe a written run directory is about
        to disappear.
        """
        job = self.store.get(job_id)
        if job is None:
            raise KeyError(f"unknown job_id: {job_id}")
        if job.state in TERMINAL:
            return False
        job._cancel.set()
        return True

    def stats(self) -> dict:
        jobs = self.store.list()
        by_state: dict[str, int] = {}
        for j in jobs:
            by_state[j["state"]] = by_state.get(j["state"], 0) + 1
        return {
            "workers": len(self._workers),
            "queue_depth": self._q.qsize(),
            "jobs": len(jobs),
            "by_state": by_state,
            "resource_cache": self.cache.stats(),
            "globals": guards.frozen_snapshot().as_dict(),
        }

    def shutdown(self, *, wait: bool = True, timeout: float = 60.0) -> None:
        self._shutdown.set()
        for _ in self._workers:
            try:
                self._q.put_nowait(None)
            except queue.Full:
                pass
        if wait:
            for t in self._workers:
                t.join(timeout=timeout)

    # -- the worker --------------------------------------------------------
    def _worker(self) -> None:
        while not self._shutdown.is_set():
            try:
                job_id = self._q.get(timeout=0.2)
            except queue.Empty:
                continue
            if job_id is None:
                self._q.task_done()
                return
            job = self.store.get(job_id)
            try:
                if job is None:
                    continue
                if job._cancel.is_set():
                    job.state = CANCELLED
                    job.finished_utc = _now()
                    continue
                self._execute(job)
            finally:
                self._q.task_done()

    def _execute(self, job: Job) -> None:
        job.state = RUNNING
        job.started_utc = _now()
        try:
            handler = self._handlers[job.kind]
            job.result = handler(job)
            job.progress.close()
            job.state = SUCCEEDED
        except RoutingCancelled as exc:
            # Not a failure. The caller asked, the scan stopped at a boundary,
            # and nothing was written — so this is reported as its own state
            # rather than as an error a reader would go looking for.
            job.state = CANCELLED
            job.error = str(exc)
            job.error_code = "cancelled"
        except ServiceError as exc:
            job.state = FAILED
            job.error = str(exc)
            job.error_code = exc.code
            job.traceback = traceback.format_exc()
        except Exception as exc:  # noqa: BLE001 - a worker must never die
            job.state = FAILED
            job.error = f"{type(exc).__name__}: {exc}"
            job.error_code = "internal"
            job.traceback = traceback.format_exc()
        finally:
            job.finished_utc = _now()

    def _run_ignition(self, job: Job) -> dict:
        request: IgnitionRequest = job._payload  # type: ignore[attr-defined]
        return route_from_ignition(
            request, cache=self.cache, run_id=_run_id_for(job),
            progress=job.progress, should_cancel=job._cancel.is_set)


def _run_id_for(job: Job) -> str:
    from .routing import make_run_id
    return make_run_id(unique=job.job_id[:8])


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_runner(*, regions: list[str] | None = None, capacity: int = 1,
                 max_workers: int = 1,
                 params: RoutingParams | None = None) -> JobRunner:
    """A runner with its cache already warm. What a service does at start-up.

    Preloading is the difference between the first operator of the day waiting
    30 seconds and waiting 27 — and, more to the point, between the load
    happening once and happening on every request forever.
    """
    cache = ResourceCache(capacity=max(capacity, len(regions or [])))
    runner = JobRunner(cache=cache, max_workers=max_workers)
    if regions:
        cache.preload(regions, params or RoutingParams.from_config())
    return runner


__all__ = [
    "CANCELLED", "FAILED", "Job", "JobRunner", "JobStore", "QUEUED",
    "QueueFull", "RUNNING", "SUCCEEDED", "TERMINAL", "build_runner",
]
