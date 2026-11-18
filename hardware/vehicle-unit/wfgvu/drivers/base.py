"""Driver base class (DESIGN.md section 3): live/sim, timestamps, heartbeats, reconnect.

``Driver(name, cfg, emit, sim_source=None, *, ctx=None)``; ``start()``, ``stop()``. Each driver runs one reader
thread and one heartbeat thread. ``emit(msg)`` receives complete protocol messages (dicts built by ``ctx.make``),
from driver threads; the server serialises, records and broadcasts them.

Live mode: the reader thread calls ``open()``; on any exception it reports ``no_device`` (detail = the error) and
retries every ``retry_s`` (2 s). Once open it loops on ``read()``, which returns a list of ``data`` dicts (may be
empty on a timeout). An exception from ``read()`` reports ``error``, closes the device and goes back to opening.
A device that comes back raises an ``event`` ``kind="sensor_reconnected"``.

Sim mode (``sim_source`` = ``replay.SensorStream``): recorded readings are re-emitted at their recorded spacing
on the shared ``SimClock`` with new envelopes (this unit's ``t_mono``/``t_utc`` now, ``sim: true``) and the
driver's own ``seq``; the recorded ``data`` is passed through unchanged. Recorded heartbeats with status
``no_device`` or ``error`` are adopted as this driver's device state (so a synthetic ``--fail`` overlay or a real
recorded outage shows up as it did); a recorded ``ok`` clears it. When the stream is exhausted the driver goes
silent (status becomes ``stale``); after the whole session's recorded time has elapsed it reports ``sim_ended``.

Heartbeats: every ``heartbeat_s`` (0.5 s) and immediately (checked every 0.1 s) when the status changes.
``status`` is, in priority order: ``sim_ended``; ``no_device``/``error`` (device state); ``error`` if the latest
reading was flagged bad by ``assess()`` (e.g. a thermocouple fault); ``stale`` if no good reading for ``stale_s``
(DESIGN: thermal 1.0, radar 1.0, tc_* 1.0, imu 0.5, gnss 2.0, pi 3.0 s); else ``ok``. ``stop()`` sends a final
``no_device`` heartbeat with detail "driver stopped". The Pi's status is advisory: the laptop decides freshness
on its own clock.

Timestamps: every message carries the Pi's ``time.monotonic()`` and UTC wall clock at creation (``protocol.make``).
For live readings that is the moment the driver finished decoding, not the sensor's exposure time; the offset
(USB/UART/SPI latency, a few ms to tens of ms) is not measured.
"""
from __future__ import annotations

import collections
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from .. import protocol

STALE_S: Dict[str, float] = {"thermal": 1.0, "radar": 1.0, "tc_plate": 1.0, "tc_housing": 1.0, "tc_air": 1.0,
                             "imu": 0.5, "gnss": 2.0, "pi": 3.0}
HEARTBEAT_S = 0.5
RETRY_S = 2.0
RATE_WINDOW_S = 2.0

EmitFn = Callable[[dict], None]


class DeviceUnavailable(OSError):
    """The device (or its Python library) is not present."""


class Driver:
    """Base driver. Subclasses implement ``open``, ``read``, ``close`` and optionally ``assess``."""

    def __init__(self, name: str, cfg: Optional[dict], emit: EmitFn, sim_source=None, *,
                 ctx: Optional[protocol.Context] = None):
        if name not in protocol.SENSORS:
            raise ValueError("unknown sensor name %r" % name)
        self.name = name
        self.cfg = dict(cfg or {})
        self.emit_fn = emit
        self.sim_source = sim_source
        self.sim = sim_source is not None
        self.ctx = ctx or protocol.Context(sim=self.sim)
        self.stale_s = float(self.cfg.get("stale_s", STALE_S[name]))
        self.heartbeat_s = float(self.cfg.get("heartbeat_s", HEARTBEAT_S))
        self.retry_s = float(self.cfg.get("retry_s", RETRY_S))
        self.last_seq: Optional[int] = None
        self.last_ok_mono: Optional[float] = None
        self.last_bad: Optional[str] = None
        self.last_info: Optional[str] = None     # detail of the latest GOOD reading (e.g. IMU calibration), live only
        self.emit_errors = 0
        self._seq = 0
        self._hb_seq = 0
        self._times: "collections.deque[float]" = collections.deque()
        self._dev_state = "init"           # init | open | no_device | error | sim | sim_ended | stopped
        self._dev_detail = "starting"
        self._sim_override: Optional[Tuple[str, str]] = None
        self._ever_failed = False
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._threads: List[threading.Thread] = []

    # ------------------------------------------------------------------ hooks for subclasses (live)
    def open(self) -> None:
        raise DeviceUnavailable("no live implementation")

    def read(self) -> Iterable[dict]:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def assess(self, data: dict) -> Tuple[bool, str]:
        """Is this reading good (for freshness)? Return (good, detail). Default: always good."""
        return True, ""

    # ------------------------------------------------------------------ helpers
    def emit(self, msg: dict) -> None:
        try:
            self.emit_fn(msg)
        except Exception:                                    # noqa: BLE001 - a consumer bug must not kill I/O
            self.emit_errors += 1

    def event(self, kind: str, detail: str) -> None:
        self.emit(self.ctx.make("event", kind=kind, detail="%s: %s" % (self.name, detail)))

    def sleep(self, seconds: float) -> bool:
        """Interruptible sleep; returns False if the driver is stopping."""
        return not self._stop.wait(max(0.0, seconds))

    @property
    def stopping(self) -> bool:
        return self._stop.is_set()

    def publish(self, data: dict) -> Optional[dict]:
        """Timestamp and emit one reading; update seq, rate and freshness bookkeeping."""
        good, detail = self.assess(data)
        with self._lock:
            seq = self._seq
            try:
                msg = self.ctx.make("reading", sensor=self.name, seq=seq, data=data)
            except protocol.ProtocolError as exc:
                self.last_bad = "malformed reading: %s" % exc
                return None
            self._seq += 1
            self.last_seq = seq
            now = float(msg["t_mono"])
            self._times.append(now)
            while self._times and now - self._times[0] > RATE_WINDOW_S:
                self._times.popleft()
            if good:
                self.last_ok_mono = now
                self.last_bad = None
                self.last_info = detail or None
            else:
                self.last_bad = detail or "bad reading"
        self.emit(msg)
        return msg

    def rate_hz(self, now: Optional[float] = None) -> Optional[float]:
        now = time.monotonic() if now is None else now
        with self._lock:
            ts = [t for t in self._times if now - t <= RATE_WINDOW_S]
        if len(ts) < 2:
            return 0.0
        span = max(ts[-1] - ts[0], 1e-6)
        return (len(ts) - 1) / span if now - ts[-1] <= RATE_WINDOW_S else 0.0

    def status(self, now: Optional[float] = None) -> Tuple[str, str]:
        now = time.monotonic() if now is None else now
        with self._lock:
            if self._dev_state == "sim_ended":
                return "sim_ended", self._dev_detail
            if self._dev_state in ("no_device", "error", "stopped"):
                return ("no_device" if self._dev_state == "stopped" else self._dev_state), self._dev_detail
            if self._sim_override is not None:
                return self._sim_override
            if self._dev_state == "init":
                return "stale", self._dev_detail
            if self.last_bad is not None:
                return "error", self.last_bad
            if self.last_ok_mono is None:
                return "stale", "no good reading yet"
            age = now - self.last_ok_mono
            if age > self.stale_s:
                return "stale", "no good reading for %.1f s" % age
            return "ok", "sim" if self.sim else ""

    def parser_stats(self) -> str:
        """Optional parser counters for the heartbeat detail (VU-R6), e.g. ``"nmea_bad=3"``; '' by default.
        Appended to the detail of LIVE heartbeats only (no new heartbeat field: the protocol stays as it is)."""
        return ""

    def heartbeat(self) -> dict:
        """Current heartbeat message (does not emit it). Live drivers append the latest good reading's info
        (``assess`` detail, e.g. IMU calibration) and ``parser_stats()`` to the detail."""
        now = time.monotonic()
        status, detail = self.status(now)
        if not self.sim:
            extra = []
            try:
                if status == "ok" and self.last_info:
                    extra.append(str(self.last_info))
                st = self.parser_stats()
                if st:
                    extra.append(str(st))
            except Exception:                                # noqa: BLE001 - stats must never stop heartbeats
                pass
            if extra:
                detail = "; ".join([d for d in [detail] + extra if d])[:500]
        with self._lock:
            seq = self._hb_seq
            self._hb_seq += 1
        return self.ctx.make("heartbeat", sensor=self.name, status=status, detail=detail,
                             last_reading_seq=self.last_seq, rate_hz=self.rate_hz(now), seq=seq, t_mono=now)

    def _set_dev(self, state: str, detail: str) -> None:
        with self._lock:
            self._dev_state, self._dev_detail = state, detail

    # ------------------------------------------------------------------ threads
    def start(self) -> "Driver":
        if self._threads:
            return self
        self._stop.clear()
        target = self._run_sim if self.sim else self._run_live
        self._threads = [threading.Thread(target=target, name="drv-%s" % self.name, daemon=True),
                         threading.Thread(target=self._run_heartbeat, name="hb-%s" % self.name, daemon=True)]
        for t in self._threads:
            t.start()
        return self

    def stop(self, timeout: float = 3.0) -> None:
        if not self._threads:
            return
        self._stop.set()
        for t in self._threads:
            t.join(timeout)
        self._threads = []
        self._set_dev("stopped", "driver stopped")
        self.emit(self.heartbeat())

    def _run_heartbeat(self) -> None:
        last_sent = -1e9
        last_status = None
        while not self._stop.is_set():
            now = time.monotonic()
            status = self.status(now)[0]
            if status != last_status or now - last_sent >= self.heartbeat_s - 1e-3:
                self.emit(self.heartbeat())
                last_sent, last_status = now, status
            self._stop.wait(0.1)

    def _run_live(self) -> None:
        opened = False
        while not self._stop.is_set():
            if not opened:
                try:
                    self.open()
                    opened = True
                    self._set_dev("open", "")
                    if self._ever_failed:
                        self.event("sensor_reconnected", "device open")
                except Exception as exc:                     # noqa: BLE001 - any failure = no device
                    self._ever_failed = True
                    self._set_dev("no_device", "%s: %s" % (type(exc).__name__, exc))
                    self._safe_close()
                    self._stop.wait(self.retry_s)
                    continue
            try:
                for data in self.read() or ():
                    self.publish(data)
            except Exception as exc:                         # noqa: BLE001
                self._ever_failed = True
                self._set_dev("error", "read failed: %s: %s" % (type(exc).__name__, exc))
                self._safe_close()
                opened = False
                self._stop.wait(self.retry_s)
        self._safe_close()

    def _safe_close(self) -> None:
        try:
            self.close()
        except Exception:                                    # noqa: BLE001
            pass

    def _run_sim(self) -> None:
        self._set_dev("sim", "")
        src = self.sim_source
        for msg in src.play(self._stop):
            if msg["type"] == "reading":
                self.publish(msg["data"])
            elif msg["type"] == "heartbeat":
                st = msg["status"]
                with self._lock:
                    if st in ("no_device", "error"):
                        self._sim_override = (st, "recorded: %s" % msg.get("detail", ""))
                    elif st == "ok":
                        self._sim_override = None
        if self._stop.is_set():
            return
        if src.wait_session_end(self._stop):
            self._set_dev("sim_ended", "recorded session ended")


def first_present(mods: Iterable[str]) -> Optional[Any]:
    """Import the first importable module name from ``mods`` (optional hardware libraries)."""
    import importlib
    for m in mods:
        try:
            return importlib.import_module(m)
        except ImportError:
            continue
    return None
