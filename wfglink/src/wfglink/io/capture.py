"""Live capture with health checks, reconnection and an ordered fallback chain.

Each source runs in its own capture thread that keeps only the newest frame (a one-slot
buffer), so a slow consumer drops frames instead of building latency.

SourceChain holds an ordered list of options (for the booth: iPhone, then USB webcam,
then labelled file replay). It always shows the best healthy option:

- A source is unhealthy when it raises, delivers no frame for `stale_s`, delivers
  repeated frames (at most freeze_max_px pixels changed) for `freeze_s`, or when an
  optional health hook (the booth's marker lock and advancing frame code) reports failure
  for `freeze_s`.
- An unhealthy source is closed and retried with exponential backoff (0.5 s to 5 s),
  and the next option takes over at once.
- While a lower option is active, higher options are probed in the background. A probe
  must stay healthy for `switch_back_s` (5 s) before it takes over, so an intermittent
  connection does not flap.
- Replay and synthetic options are always available and are labelled as not live.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

import cv2
import numpy as np

from wfglink.io.frames import Frame
from wfglink.io.sources import Source, SourceError


@dataclass
class SourceOption:
    key: str                         # "iphone", "webcam", "replay", "synthetic", ...
    factory: Callable[[], Source]    # builds a fresh Source for every attempt
    live: bool = True                # False for file replay and synthetic sources
    label: str = ""                  # shown in the status line


@dataclass
class ChainConfig:
    stale_s: float = 1.5
    freeze_s: float = 3.0
    freeze_dn: int = 2               # a pixel (half resolution) changed by at least this many DN
    freeze_max_px: int = 0           # at most this many changed pixels: the frame repeats
    backoff_min_s: float = 0.5
    backoff_max_s: float = 5.0
    switch_back_s: float = 5.0
    probe_every_s: float = 10.0
    open_timeout_s: float = 8.0

    @classmethod
    def from_config(cls, cfg: dict) -> "ChainConfig":
        c = cfg.get("capture", {}) if isinstance(cfg, dict) else {}
        return cls(**{k: float(v) for k, v in c.items() if k in cls.__dataclass_fields__})


class CaptureWorker(threading.Thread):
    """Open one source and keep its newest frame. Never raises; reports state instead."""

    def __init__(self, option: SourceOption, health_hook: Callable[[Frame], bool | None] | None = None):
        super().__init__(daemon=True, name=f"capture-{option.key}")
        self.option = option
        self.health_hook = health_hook
        self._lock = threading.Lock()
        self._halt = threading.Event()
        self.frame: Frame | None = None
        self.opened = threading.Event()
        self.error: str | None = None
        self.source: Source | None = None
        self.t_open: float | None = None
        self.t_last_frame: float | None = None
        self.t_last_change: float | None = None
        self.t_last_hook_ok: float | None = None
        self.frames = 0
        self._thumb: np.ndarray | None = None
        self._times: list[float] = []

    def stop(self) -> None:
        self._halt.set()

    def run(self) -> None:
        try:
            self.source = self.option.factory()
            self.source.open()
            self.t_open = time.monotonic()
            self.t_last_change = self.t_open
            self.t_last_hook_ok = self.t_open
            self.opened.set()
            while not self._halt.is_set():
                f = self.source.read()
                now = time.monotonic()
                if f is None:
                    if self.option.live:
                        time.sleep(0.005)
                        continue
                    self.error = "end of source"
                    break
                self._observe(f, now)
                with self._lock:
                    self.frame = f
                    self.frames += 1
                    self.t_last_frame = now
        except SourceError as exc:
            self.error = str(exc)
        except Exception as exc:  # a crashing backend must never take the app down
            self.error = f"{type(exc).__name__}: {exc}"
        finally:
            self.opened.set()
            if self.source is not None:
                try:
                    self.source.close()
                except Exception:
                    pass

    def _observe(self, f: Frame, now: float) -> None:
        # A frozen camera repeats its last frame exactly; any real new frame changes many
        # pixels through sensor noise or motion. Averaging into a thumbnail hid both on a
        # dark, nearly static scene (a few small embers), which would have looked frozen.
        gray = cv2.cvtColor(f.image, cv2.COLOR_BGR2GRAY) if f.image.ndim == 3 else f.image
        small = cv2.resize(gray, (max(1, gray.shape[1] // 2), max(1, gray.shape[0] // 2)), interpolation=cv2.INTER_AREA)
        if (self._thumb is None or self._thumb.shape != small.shape
                or cv2.countNonZero(cv2.compare(cv2.absdiff(small, self._thumb), self._freeze_dn, cv2.CMP_GE)) > self._freeze_px):
            self.t_last_change = now
        self._thumb = small
        if self.health_hook is not None:
            ok = self.health_hook(f)
            if ok is None or ok:
                self.t_last_hook_ok = now
        else:
            self.t_last_hook_ok = now
        self._times.append(now)
        if len(self._times) > 60:
            self._times = self._times[-60:]

    _freeze_dn = 2
    _freeze_px = 0

    def latest(self) -> Frame | None:
        with self._lock:
            return self.frame

    def fps(self) -> float:
        ts = self._times[-30:]
        if len(ts) < 2 or ts[-1] <= ts[0]:
            return 0.0
        return (len(ts) - 1) / (ts[-1] - ts[0])

    def health(self, cfg: ChainConfig, now: float) -> tuple[bool, str]:
        """(healthy, reason). Before the first frame, healthy until the open timeout."""
        if self.error:
            return False, self.error
        if not self.opened.is_set():
            return (now - (self._started_at or now)) < cfg.open_timeout_s, "opening"
        if self.t_last_frame is None:
            return (now - (self.t_open or now)) < max(cfg.stale_s, 2.0), "waiting for first frame"
        if now - self.t_last_frame > cfg.stale_s:
            return False, "no frames"
        if self.option.live and self.t_last_change is not None and now - self.t_last_change > cfg.freeze_s:
            return False, "frozen image"
        if self.t_last_hook_ok is not None and now - self.t_last_hook_ok > cfg.freeze_s:
            return False, "booth check failed"
        return True, "ok"

    _started_at: float | None = None

    def start(self) -> None:  # type: ignore[override]
        self._started_at = time.monotonic()
        super().start()


@dataclass
class ChainStatus:
    key: str | None = None
    label: str = ""
    live: bool = False
    state: str = "starting"        # starting, live, replay, reconnecting, no_source
    reason: str = ""
    since: float = field(default_factory=time.monotonic)
    fps: float = 0.0
    switches: int = 0
    failures: dict[str, int] = field(default_factory=dict)


class SourceChain:
    def __init__(self, options: list[SourceOption], cfg: ChainConfig | None = None,
                 health_hook: Callable[[Frame], bool | None] | None = None):
        if not options:
            raise ValueError("SourceChain needs at least one option")
        self.options = options
        self.cfg = cfg or ChainConfig()
        CaptureWorker._freeze_dn = int(self.cfg.freeze_dn)
        CaptureWorker._freeze_px = int(self.cfg.freeze_max_px)
        self.health_hook = health_hook
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.active: CaptureWorker | None = None
        self.probe: CaptureWorker | None = None
        self._probe_ok_since: float | None = None
        self._next_try: dict[str, float] = {o.key: 0.0 for o in options}
        self._backoff: dict[str, float] = {o.key: self.cfg.backoff_min_s for o in options}
        self._last_probe: dict[str, float] = {o.key: 0.0 for o in options}
        self.status = ChainStatus()
        self.events: list[dict] = []
        self._retired: list[CaptureWorker] = []

    # Public API ------------------------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True, name="source-chain")
        self._thread.start()

    def stop(self, timeout_s: float = 3.0) -> None:
        """Stop the manager and every capture thread, waiting for them to finish."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout_s)
        workers = [w for w in (self.active, self.probe) if w is not None] + self._retired
        for w in workers:
            w.stop()
        for w in workers:
            w.join(timeout=timeout_s)

    def latest(self) -> tuple[Frame | None, ChainStatus]:
        with self._lock:
            w = self.active
            st = ChainStatus(**vars(self.status))
        frame = w.latest() if w is not None else None
        return frame, st

    # Internals ---------------------------------------------------------------------------
    def _rank(self, key: str) -> int:
        return next(i for i, o in enumerate(self.options) if o.key == key)

    def _log(self, kind: str, **info) -> None:
        self.events.append({"t": time.monotonic(), "event": kind, **info})
        if len(self.events) > 500:
            self.events = self.events[-500:]

    def _fail(self, key: str, reason: str, now: float) -> None:
        self.status.failures[key] = self.status.failures.get(key, 0) + 1
        self._next_try[key] = now + self._backoff[key]
        self._backoff[key] = min(self._backoff[key] * 2, self.cfg.backoff_max_s)
        self._log("failed", key=key, reason=reason)

    def _launch(self, option: SourceOption) -> CaptureWorker:
        w = CaptureWorker(option, self.health_hook)
        w.start()
        return w

    def _activate(self, w: CaptureWorker, now: float, reason: str) -> None:
        with self._lock:
            old = self.active
            self.active = w
            self.status.key = w.option.key
            self.status.label = w.option.label or w.option.key
            self.status.live = w.option.live
            self.status.state = "live" if w.option.live else "replay"
            self.status.reason = reason
            self.status.since = now
            self.status.switches += 1
        if old is not None and old is not w:
            old.stop()
            self._retired.append(old)
        self._log("activated", key=w.option.key, reason=reason)

    def _run(self) -> None:
        while not self._stop.is_set():
            now = time.monotonic()
            self._step(now)
            time.sleep(0.05)

    def _step(self, now: float) -> None:
        cfg = self.cfg
        self._retired = [w for w in self._retired if w.is_alive()]
        # 1. Check the active source.
        if self.active is not None:
            ok, reason = self.active.health(cfg, now)
            if not ok:
                key = self.active.option.key
                self.active.stop()
                self._retired.append(self.active)
                self._fail(key, reason, now)
                with self._lock:
                    self.active = None
                    self.status.state = "reconnecting"
                    self.status.reason = reason
                    self.status.since = now
            else:
                with self._lock:
                    self.status.fps = self.active.fps()
                    if self.active.frames > 0:
                        self.status.state = "live" if self.active.option.live else "replay"
        # 2. Nothing active: start the best option that is not backing off.
        if self.active is None:
            for opt in self.options:
                if now >= self._next_try[opt.key] and not (self.probe and self.probe.option.key == opt.key):
                    self._activate(self._launch(opt), now, "start")
                    break
            else:
                with self._lock:
                    self.status.state = "no_source"
            return
        # 3. Active but not the best: probe a better option in the background.
        rank = self._rank(self.active.option.key)
        if self.probe is None:
            for opt in self.options[:rank]:
                if now >= self._next_try[opt.key] and now - self._last_probe[opt.key] >= min(cfg.probe_every_s, self._backoff[opt.key] * 2):
                    self._last_probe[opt.key] = now
                    self.probe = self._launch(opt)
                    self._probe_ok_since = None
                    self._log("probe", key=opt.key)
                    break
        else:
            ok, reason = self.probe.health(cfg, now)
            if not ok:
                self.probe.stop()
                self._retired.append(self.probe)
                self._fail(self.probe.option.key, reason, now)
                self.probe = None
            elif self.probe.frames > 0:
                if self._probe_ok_since is None:
                    self._probe_ok_since = now
                elif now - self._probe_ok_since >= cfg.switch_back_s:
                    w, self.probe = self.probe, None
                    self._backoff[w.option.key] = cfg.backoff_min_s
                    self._activate(w, now, "switched back after sustained health")
        # A healthy active source resets its own backoff.
        if self.active is not None and self.active.frames > 0:
            self._backoff[self.active.option.key] = cfg.backoff_min_s
