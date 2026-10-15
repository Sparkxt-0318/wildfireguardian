"""Process worker mode (live.worker_mode: process).

Playback and analysis run in a child process, so the GUI thread never competes with them
for the Python interpreter lock. The child writes each analysis image into one of two
shared-memory slots and sends the rest of the LiveState (small) through a queue; the GUI
copies the image out of the slot and paints. If the queue is full the newest state wins.
The interface matches LiveWorker (state_ready, start, stop, shutdown, set_paused, paused,
clip, frames, errors, error_count, report, pipeline_counters, child_pids), so the booth
window does not care which mode runs.

Every STATS_EVERY_S seconds, and once more when it stops, the child also sends a small
report over the same queue: the clip playing, the last booth.report_events playback
events, playback counters, each clip's pipeline stats and its analysis errors. Each report
is complete, so losing one to the newest-wins rule costs nothing; shutdown() keeps reading
the queue until the child has exited, so the final one reaches run_live's report.

Space pauses through a shared event; the child stops if its parent disappears (a parent
killed with SIGKILL cannot stop it otherwise).
"""
from __future__ import annotations

import multiprocessing as mp
import os
import queue
import time
from dataclasses import asdict
from multiprocessing import shared_memory
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal

from wfglink.pipeline import heartbeat_counters
from wfglink.render.scene import LiveState

STATS_EVERY_S = 1.0


def slot_bytes(cfg: dict) -> int:
    """Bytes of one image slot: room for a frame live.analysis_max_width wide and twice as tall
    (a portrait roi), and never less than 1920x1080."""
    w = int((cfg.get("live") or {}).get("analysis_max_width", 1280))
    return max(1920 * 1080, 2 * w * w) * 3


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


def _child_main(cfg: dict, spec: dict, shm_name: str, q, stop, pause, parent_pid: int) -> None:
    from wfglink.ui.booth_app import LiveAnalyser, make_player

    shm = shared_memory.SharedMemory(name=shm_name)
    nbytes = slot_bytes(cfg)
    slots = [np.ndarray((nbytes,), np.uint8, shm.buf, offset=k * nbytes) for k in range(2)]
    player = make_player(cfg, spec)
    player.start()
    analyser = LiveAnalyser(cfg)
    n_events = int((cfg.get("booth") or {}).get("report_events", 100))
    errors: list[str] = []
    n_errors = 0
    last = None
    slot = 0
    t_stats = time.monotonic()

    def stats_msg() -> tuple:
        return ("stats", {"clip": analyser.active, "events": list(player.events[-n_events:]) if n_events > 0 else [],
                          "playback": dict(player.stats), "pipelines": analyser.stats(),
                          "errors": errors[-10:], "error_count": n_errors})

    try:
        while not stop.is_set():
            if os.getppid() != parent_pid:      # orphaned: the booth app is gone
                break
            if pause.is_set() != player.paused:
                player.pause() if pause.is_set() else player.resume()
            if time.monotonic() - t_stats >= STATS_EVERY_S:
                t_stats = time.monotonic()
                _put_newest(q, stats_msg())
            f = player.latest()
            if f is None or f.index == last:
                time.sleep(0.003)
                continue
            last = f.index
            try:
                st = analyser.process(f)
            except Exception as exc:
                n_errors += 1
                errors = (errors + [f"{type(exc).__name__}: {exc}"])[-100:]
                continue
            img = st.image
            shape = None
            if img is not None:
                h, w = img.shape[:2]
                if h * w * 3 <= nbytes:
                    slots[slot][: h * w * 3] = img.reshape(-1)
                    shape = (h, w, 3)
                elif not errors or not errors[-1].startswith("frame too large"):
                    n_errors += 1
                    errors = (errors + [f"frame too large for the shared slot: {w}x{h}"])[-100:]
            d = {k: v for k, v in asdict(st).items() if k != "image"}
            _put_newest(q, ("state", slot, shape, d))
            slot = 1 - slot
    finally:
        try:   # the final report: blocking, because the parent reads the queue until we exit
            q.put(stats_msg(), timeout=2.0)
        except Exception:
            pass
        player.stop()
        shm.close()


class ProcessLiveWorker(QObject):
    state_ready = Signal(object)

    def __init__(self, cfg: dict, spec: dict):
        super().__init__()
        self.cfg, self.spec = cfg, spec
        self.ctx = mp.get_context("spawn")
        self.slot_bytes = slot_bytes(cfg)
        self.shm = shared_memory.SharedMemory(create=True, size=2 * self.slot_bytes)
        self.q = self.ctx.Queue(maxsize=2)
        self.stop_event = self.ctx.Event()
        self.pause_event = self.ctx.Event()
        self.proc = self.ctx.Process(target=_child_main, args=(cfg, spec, self.shm.name, self.q, self.stop_event,
                                                               self.pause_event, os.getpid()), daemon=True)
        self.timer = QTimer()
        self.timer.timeout.connect(self._poll)
        self.frames = 0
        # The child's last report (see the module docstring).
        self.clip: str | None = None
        self.events: list[dict] = []
        self.playback: dict[str, Any] = {}
        self.pipelines: dict[str, dict] = {}
        self.errors: list[str] = []
        self.error_count = 0

    def start(self) -> None:
        self.proc.start()
        self.timer.start(4)

    def set_paused(self, paused: bool) -> None:
        self.pause_event.set() if paused else self.pause_event.clear()

    @property
    def paused(self) -> bool:
        return self.pause_event.is_set()

    def child_pids(self) -> list[int]:
        return [self.proc.pid] if self.proc.pid else []

    def _drain(self, emit: bool = True) -> None:
        latest = None
        while True:
            try:
                msg = self.q.get_nowait()
            except queue.Empty:
                break
            except (EOFError, OSError):    # the child went away mid-message
                break
            if msg[0] == "stats":
                d = msg[1]
                self.clip = d.get("clip")
                self.events = list(d.get("events") or [])
                self.playback = dict(d.get("playback") or {})
                self.pipelines = dict(d.get("pipelines") or {})
                self.errors = list(d.get("errors") or [])
                self.error_count = int(d.get("error_count") or 0)
            else:
                latest = msg
        if latest is None or not emit:
            return
        _, slot, shape, d = latest
        img = None
        if shape is not None:
            n = shape[0] * shape[1] * shape[2]
            img = np.frombuffer(self.shm.buf, np.uint8, count=n, offset=slot * self.slot_bytes).reshape(shape).copy()
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

    def shutdown(self, ms: int = 5000) -> bool:
        """Stop the child and wait for it. Keep reading while it finishes: its final report must
        not be left in the queue, and a child cannot exit while the queue holds data it has not flushed."""
        self.stop()
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
        """The child's last report: the clip at the end, the last n_events playback events, playback
        counters and each clip's pipeline stats."""
        return {"clip": self.clip, "events": self.events[-n_events:] if n_events > 0 else [],
                "playback": dict(self.playback), "pipelines": dict(self.pipelines)}

    def pipeline_counters(self) -> dict[str, Any] | None:
        """The active pipeline's frame counters from the child's last report (at most
        STATS_EVERY_S old; they restart with each clip when booth.reset_per_clip is true)."""
        return heartbeat_counters(self.clip, self.pipelines.get(self.clip) if self.clip is not None else None)
