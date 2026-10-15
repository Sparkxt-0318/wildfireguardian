"""Process worker mode (live.worker_mode: process).

Playback, the camera and the analysis run in a child process (the same BoothEngine as thread
mode), so the GUI thread never competes with them for the Python interpreter lock. The child
writes each analysis image into one of two shared-memory slots and sends the rest of the
LiveState (small) through a queue; the GUI copies the image out of the slot and paints. If
the queue is full the newest state wins. The interface matches LiveWorker (state_ready,
start, stop, shutdown, set_paused, paused, set_mode, mode, set_camera_allowed, camera_state,
clip, frames, errors, error_count, report, pipeline_counters, child_pids), so the booth
window does not care which mode runs.

Every STATS_EVERY_S seconds, and once more when it stops, the child also sends a small
report over the same queue: the clip playing, the last booth.report_events playback
events, playback counters, each clip's pipeline stats, its analysis errors, the mode it runs
and its camera state. Each report is complete, so losing one to the newest-wins rule costs
nothing; shutdown() keeps reading the queue until the child has exited, so the final one
reaches run_live's report. A change of camera state is also sent at once.

Mode (key M): the parent writes a shared integer, the request number times two plus one for
ember mode; the child applies it, and its messages carry the request number they belong
to, so a state or camera state from before the newest switch is never shown. The camera is
opened in the child only while the shared camera_ok event is set: the parent sets it once
it holds the camera permission (asked on its main thread), never the child.

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


def _child_main(cfg: dict, spec: dict, ember: dict, shm_name: str, q, stop, pause, mode_req, camera_ok,
                parent_pid: int) -> None:
    from wfglink.ui.booth_app import BoothEngine

    shm = shared_memory.SharedMemory(name=shm_name)
    nbytes = slot_bytes(cfg)
    slots = [np.ndarray((nbytes,), np.uint8, shm.buf, offset=k * nbytes) for k in range(2)]
    engine = BoothEngine(cfg, spec, ember, camera_allowed=camera_ok.is_set)
    req = int(mode_req.value)
    engine.start("ember" if req % 2 else "fire")
    n_events = int((cfg.get("booth") or {}).get("report_events", 100))
    errors: list[str] = []
    n_errors = 0
    slot = 0
    t_stats = time.monotonic()
    cam = None

    def stats_msg() -> tuple:
        rep = engine.report(n_events)
        return ("stats", {**rep, "errors": errors[-10:], "error_count": n_errors, "counters": engine.counters(),
                          "req": req})

    try:
        while not stop.is_set():
            if os.getppid() != parent_pid:      # orphaned: the booth app is gone
                break
            try:
                if int(mode_req.value) != req:
                    req = int(mode_req.value)
                    engine.set_mode("ember" if req % 2 else "fire")
                if engine.paused != pause.is_set():
                    engine.set_paused(pause.is_set())
                if engine.camera_state() != cam:
                    cam = engine.camera_state()
                    _put_newest(q, ("camera", req, cam))
                if time.monotonic() - t_stats >= STATS_EVERY_S:
                    t_stats = time.monotonic()
                    _put_newest(q, stats_msg())
                st = engine.step()
            except Exception as exc:
                n_errors += 1
                errors = (errors + [f"{type(exc).__name__}: {exc}"])[-100:]
                time.sleep(0.01)
                continue
            if st is None:
                time.sleep(0.003)
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
            _put_newest(q, ("state", slot, shape, d, req))
            slot = 1 - slot
    finally:
        try:   # the final report: blocking, because the parent reads the queue until we exit
            q.put(stats_msg(), timeout=2.0)
        except Exception:
            pass
        engine.stop()
        shm.close()


class ProcessLiveWorker(QObject):
    state_ready = Signal(object)

    def __init__(self, cfg: dict, spec: dict, ember: dict | None = None, mode: str = "fire", camera_allowed: bool = True):
        super().__init__()
        self.cfg, self.spec, self.ember = cfg, spec, ember or {"kind": "camera"}
        self.ctx = mp.get_context("spawn")
        self.slot_bytes = slot_bytes(cfg)
        self.shm = shared_memory.SharedMemory(create=True, size=2 * self.slot_bytes)
        self.q = self.ctx.Queue(maxsize=2)
        self.stop_event = self.ctx.Event()
        self.pause_event = self.ctx.Event()
        self.camera_ok = self.ctx.Event()
        if camera_allowed:
            self.camera_ok.set()
        self._req = 1 if mode == "ember" else 0
        self.mode_req = self.ctx.Value("i", self._req)
        self.proc = self.ctx.Process(target=_child_main, args=(cfg, spec, self.ember, self.shm.name, self.q, self.stop_event,
                                                               self.pause_event, self.mode_req, self.camera_ok, os.getpid()),
                                     daemon=True)
        self.timer = QTimer()
        self.timer.timeout.connect(self._poll)
        self.frames = 0
        # The child's last report (see the module docstring).
        self.clip: str | None = None
        self.events: list[dict] = []
        self.playback: dict[str, Any] = {}
        self.pipelines: dict[str, dict] = {}
        self.counters: dict[str, Any] | None = None
        self.child_mode = "ember" if self._req % 2 else "fire"
        self.camera_state = "off"
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

    def set_mode(self, mode: str) -> None:
        want = 1 if mode == "ember" else 0
        if self._req % 2 == want:
            return
        self._req = (self._req // 2 + 1) * 2 + want
        self.camera_state = "off"
        self.mode_req.value = self._req

    @property
    def mode(self) -> str:
        return "ember" if self._req % 2 else "fire"

    def set_camera_allowed(self, allowed: bool) -> None:
        self.camera_ok.set() if allowed else self.camera_ok.clear()

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
                self.counters = d.get("counters")
                self.errors = list(d.get("errors") or [])
                self.error_count = int(d.get("error_count") or 0)
                if d.get("req") == self._req:
                    self.child_mode = d.get("mode", self.child_mode)
                    self.camera_state = d.get("camera_state", self.camera_state)
            elif msg[0] == "camera":
                if msg[1] == self._req:
                    self.camera_state = msg[2]
            elif msg[-1] == self._req:          # a state from before the newest mode switch is dropped
                latest = msg
        if latest is None or not emit:
            return
        _, slot, shape, d, _ = latest
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
        if self.counters is not None:
            return dict(self.counters)
        return heartbeat_counters(self.clip, self.pipelines.get(self.clip) if self.clip is not None else None)
