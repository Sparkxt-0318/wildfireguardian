"""Process worker mode (live.worker_mode: process).

Capture and analysis run in a child process, so the GUI thread never competes with them
for the Python interpreter lock. The child writes each analysis image into one of two
shared-memory slots and sends the rest of the LiveState (small) through a queue; the GUI
copies the image out of the slot and paints. If the queue is full the newest state wins.
The interface matches BoothWorker (a state_ready signal, start, stop, wait, report, frames,
errors), so the booth window does not care which mode runs.

Every STATS_EVERY_S seconds, and once more when it stops, the child also sends a small
report over the same queue: the active source key, the last booth.report_events source
chain events and each pipeline's stats. Each report is complete, so losing one to the
newest-wins rule costs nothing; wait() keeps reading the queue until the child has
exited, so the final one reaches run_booth's report.
"""
from __future__ import annotations

import multiprocessing as mp
import queue
import time
from dataclasses import asdict
from multiprocessing import shared_memory
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from wfglink.render.scene import LiveState

MAX_W, MAX_H = 1920, 1080
SLOT_BYTES = MAX_W * MAX_H * 3
STATS_EVERY_S = 1.0


def _put_newest(q, msg) -> None:
    """Put without blocking; when the queue is full, drop its oldest message first."""
    try:
        q.put_nowait(msg)
    except queue.Full:
        try:
            q.get_nowait()
        except queue.Empty:
            pass
        try:
            q.put_nowait(msg)
        except queue.Full:
            pass


def _child_main(cfg: dict, source: str, booth_meta: dict | None, shm_name: str, q, stop) -> None:
    from wfglink.io.capture import ChainConfig, SourceChain
    from wfglink.pipeline import Pipeline
    from wfglink.ui.booth_app import (build_options, last_events, make_booth_context, screen_check_factory,
                                      source_fields)

    shm = shared_memory.SharedMemory(name=shm_name)
    slots = [np.ndarray((SLOT_BYTES,), np.uint8, shm.buf, offset=k * SLOT_BYTES) for k in range(2)]
    chain = SourceChain(build_options(cfg, source), ChainConfig.from_config(cfg),
                        hook_factory=screen_check_factory(booth_meta, cfg))
    chain.start()
    n_events = int((cfg.get("booth") or {}).get("report_events", 100))
    pipes: dict[str, Pipeline] = {}
    active = None
    last = None
    slot = 0
    times: list[float] = []
    t_stats = time.monotonic()

    def stats_msg() -> tuple:
        return ("stats", {"source": chain.status.key, "source_events": last_events(chain.events, n_events),
                          "pipelines": {k: p.stats.as_dict() for k, p in pipes.items()}})

    try:
        while not stop.is_set():
            if time.monotonic() - t_stats >= STATS_EVERY_S:
                t_stats = time.monotonic()
                _put_newest(q, stats_msg())
            frame, status = chain.latest()
            key = (status.key, frame.index) if frame is not None else None
            if frame is None or key == last:
                time.sleep(0.003)
                continue
            last = key
            try:
                if status.key != active:
                    pipes.pop(status.key, None)
                    active = status.key
                if status.key not in pipes:
                    booth = make_booth_context(booth_meta, cfg) if booth_meta and status.key != "synthetic" else None
                    pipes[status.key] = Pipeline(cfg, booth=booth, downscale=True)
                pipe = pipes[status.key]
                st = pipe.process(frame)
            except Exception as exc:
                q.put(("error", f"{type(exc).__name__}: {exc}"))
                continue
            img = st.image
            shape = None
            if img is not None:
                h, w = img.shape[:2]
                if h * w * 3 <= SLOT_BYTES:
                    slots[slot][: h * w * 3] = img.reshape(-1)
                    shape = (h, w, 3)
            now = time.monotonic()
            times.append(now)
            times = times[-60:]
            fps = (len(times) - 1) / (times[-1] - times[0]) if len(times) > 2 else 0.0
            d = {k: v for k, v in asdict(st).items() if k != "image"}
            d.update(source_fields(pipe, status, frame, chain), fps=fps)
            _put_newest(q, ("state", slot, shape, d))
            slot = 1 - slot
    finally:
        try:   # the final report: blocking, because the parent reads the queue until we exit
            q.put(stats_msg(), timeout=2.0)
        except Exception:
            pass
        chain.stop()
        shm.close()


class ProcessBoothWorker(QObject):
    state_ready = Signal(object)

    def __init__(self, cfg: dict, source: str, booth_meta: dict | None):
        super().__init__()
        self.cfg, self.source, self.booth_meta = cfg, source, booth_meta
        self.ctx = mp.get_context("spawn")
        self.shm = shared_memory.SharedMemory(create=True, size=2 * SLOT_BYTES)
        self.q = self.ctx.Queue(maxsize=2)
        self.stop_event = self.ctx.Event()
        self.proc = self.ctx.Process(target=_child_main, args=(cfg, source, booth_meta, self.shm.name, self.q, self.stop_event),
                                     daemon=True)
        self.timer = QTimer()
        self.timer.timeout.connect(self._poll)
        self.frames = 0
        self.errors: list[str] = []
        self.chain = None  # the chain lives in the child
        # The child's last report (see the module docstring).
        self.source_key: str | None = None
        self.source_events: list[dict] = []
        self.pipelines: dict[str, dict] = {}

    def start(self) -> None:
        self.proc.start()
        self.timer.start(4)

    def _drain(self, emit: bool = True) -> None:
        latest = None
        while True:
            try:
                msg = self.q.get_nowait()
            except queue.Empty:
                break
            except (EOFError, OSError):    # the child went away mid-message
                break
            if msg[0] == "error":
                self.errors.append(msg[1])
            elif msg[0] == "stats":
                d = msg[1]
                self.source_key = d.get("source")
                self.source_events = list(d.get("source_events") or [])
                self.pipelines = dict(d.get("pipelines") or {})
            else:
                latest = msg
        if latest is None or not emit:
            return
        _, slot, shape, d = latest
        img = None
        if shape is not None:
            n = shape[0] * shape[1] * shape[2]
            img = np.frombuffer(self.shm.buf, np.uint8, count=n, offset=slot * SLOT_BYTES).reshape(shape).copy()
        for k in ("detections", "sparkline"):
            if k in d and not isinstance(d[k], np.ndarray):
                d[k] = np.asarray(d[k])
        self.frames += 1
        self.state_ready.emit(LiveState(image=img, **d))

    def _poll(self) -> None:
        self._drain(emit=True)

    def stop(self) -> None:
        self.timer.stop()
        self.stop_event.set()

    def wait(self, ms: int = 5000) -> bool:
        # Keep reading while the child finishes: its final report must not be left in the
        # queue, and a child cannot exit while the queue holds data it has not flushed.
        deadline = time.monotonic() + ms / 1000
        while self.proc.is_alive() and time.monotonic() < deadline:
            self._drain(emit=False)
            self.proc.join(0.02)
        self._drain(emit=False)
        alive = self.proc.is_alive()
        if alive:
            self.proc.terminate()
            self.proc.join(1)
        try:
            self.shm.close()
            self.shm.unlink()
        except FileNotFoundError:
            pass
        return not alive

    def report(self, n_events: int) -> dict[str, Any]:
        """The child's last report: source at the end, the last n_events chain events, pipeline stats."""
        return {"source": self.source_key, "source_events": self.source_events[-n_events:] if n_events > 0 else [],
                "pipelines": dict(self.pipelines)}

    def stats(self) -> dict[str, Any]:
        return {"frames": self.frames, "errors": self.errors[-10:], "mode": "process"}
