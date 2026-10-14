"""Process worker mode (live.worker_mode: process).

Capture and analysis run in a child process, so the GUI thread never competes with them
for the Python interpreter lock. The child writes each analysis image into one of two
shared-memory slots and sends the rest of the LiveState (small) through a queue; the GUI
copies the image out of the slot and paints. If the queue is full the newest state wins.
The interface matches BoothWorker (a state_ready signal, start, stop, wait, frames, errors),
so the booth window does not care which mode runs.
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


def _child_main(cfg: dict, source: str, booth_meta: dict | None, shm_name: str, q, stop) -> None:
    from wfglink.io.capture import ChainConfig, SourceChain
    from wfglink.pipeline import Pipeline
    from wfglink.ui.booth_app import build_options, make_booth_context

    shm = shared_memory.SharedMemory(name=shm_name)
    slots = [np.ndarray((SLOT_BYTES,), np.uint8, shm.buf, offset=k * SLOT_BYTES) for k in range(2)]
    chain = SourceChain(build_options(cfg, source), ChainConfig.from_config(cfg))
    chain.start()
    pipes: dict[str, Pipeline] = {}
    active = None
    last = None
    slot = 0
    times: list[float] = []
    try:
        while not stop.is_set():
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
            d.update(source_label=status.label or status.key or "",
                     source_state="synthetic" if status.key == "synthetic" else status.state, fps=fps,
                     unprepared=pipe.booth is None and status.key not in ("synthetic", "file"))
            msg = ("state", slot, shape, d)
            try:
                q.put_nowait(msg)
            except queue.Full:
                try:
                    q.get_nowait()
                except queue.Empty:
                    pass
                q.put_nowait(msg)
            slot = 1 - slot
    finally:
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

    def start(self) -> None:
        self.proc.start()
        self.timer.start(4)

    def _poll(self) -> None:
        latest = None
        while True:
            try:
                msg = self.q.get_nowait()
            except queue.Empty:
                break
            if msg[0] == "error":
                self.errors.append(msg[1])
            else:
                latest = msg
        if latest is None:
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

    def stop(self) -> None:
        self.timer.stop()
        self.stop_event.set()

    def wait(self, ms: int = 5000) -> bool:
        self.proc.join(ms / 1000)
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

    def stats(self) -> dict[str, Any]:
        return {"frames": self.frames, "errors": self.errors[-10:], "mode": "process"}
