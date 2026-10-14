"""A fault-injecting camera for tests of reconnection and fallback logic.

FakeCamera wraps any source and follows a script of events in wall-clock seconds since
open(), so tests can reproduce what a real Continuity Camera or USB webcam does:

    ("stall", t0, t1)       read() returns None (no frame) between t0 and t1
    ("freeze", t0, t1)      read() keeps returning the same image between t0 and t1
    ("disconnect", t0, t1)  read() raises SourceError between t0 and t1, and so does open()
    ("fail_open", t0, t1)   open() raises SourceError between t0 and t1

A shared clock object can be injected so tests run without sleeping.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from wfglink.io.frames import Frame
from wfglink.io.sources import Source, SourceError


@dataclass
class FakeClock:
    """Manually advanced monotonic clock for deterministic tests."""

    now: float = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, dt: float) -> None:
        self.now += dt


@dataclass
class FaultScript:
    events: list[tuple[str, float, float]] = field(default_factory=list)

    def active(self, kind: str, t: float) -> bool:
        return any(k == kind and t0 <= t < t1 for k, t0, t1 in self.events)


class FakeCamera(Source):
    kind = "camera"
    is_live = True

    def __init__(self, inner: Source, script: FaultScript | None = None, clock=None,
                 label: str = "fake-camera", frame_interval: float = 1 / 30,
                 epoch: float | None = None):
        super().__init__(label)
        if epoch is not None:
            self._epoch = epoch  # script times are relative to this shared start time
        self.inner = inner
        self.script = script or FaultScript()
        self.clock = clock or time.monotonic
        self.frame_interval = frame_interval
        self._opened_at: float | None = None
        self._last: Frame | None = None
        self._inner_open = False
        self.opens = 0

    def _t(self) -> float:
        return self.clock() - (self._opened_at if self._opened_at is not None else self.clock())

    def open(self) -> None:
        now = self.clock()
        t_global = now - getattr(self, "_epoch", now)
        if not hasattr(self, "_epoch"):
            self._epoch = now
            t_global = 0.0
        if self.script.active("fail_open", t_global) or self.script.active("disconnect", t_global):
            raise SourceError(f"{self.name}: device not available")
        if not self._inner_open:
            self.inner.open()
            self._inner_open = True
        self._opened_at = now
        self.opens += 1
        self.info = {"backend": "fake", **getattr(self.inner, "info", {})}

    def read(self) -> Frame | None:
        t_global = self.clock() - self._epoch
        if self.script.active("disconnect", t_global):
            raise SourceError(f"{self.name}: device disconnected")
        if self.script.active("stall", t_global):
            return None
        if self.script.active("freeze", t_global) and self._last is not None:
            f = self._last
            return Frame(f.image.copy(), f.t, self._next_index(), self.clock(), dict(f.meta, frozen=True))
        f = self.inner.read()
        if f is None:
            return None
        self._last = f
        return Frame(f.image, f.t, self._next_index(), self.clock(), dict(f.meta, source=self.name))

    def close(self) -> None:
        self._opened_at = None
