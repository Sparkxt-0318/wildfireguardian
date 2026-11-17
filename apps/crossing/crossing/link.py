"""Laptop side of the roof-unit link: WebSocket client and per-sensor freshness (DESIGN.md section 5).

Freshness is decided ONLY with the laptop's own ``time.monotonic()`` taken at receipt. The Pi's ``t_mono``/``t_utc``
and its heartbeat ``status`` are never trusted alone: a sensor is fresh only when ALL of these hold at ``now``:

1. the link is up: the socket is connected AND some message arrived within ``silence_s`` (the Pi sends a heartbeat
   per sensor every 0.5 s, so 1.5 s of silence means the Wi-Fi link or the Pi is gone even if TCP has not noticed);
2. a ``reading`` of that sensor arrived within ``stale_s`` (2.0 s);
3. the latest Pi heartbeat for that sensor arrived within ``heartbeat_stale_s`` (2.0 s) and says ``"ok"``;
4. the Pi stream advances: the latest reading's ``seq`` is above the previous one and its ``t_mono`` later, and the
   same for the sensor's heartbeats. A repeated or backwards ``seq`` / ``t_mono`` (a stuck or replaying driver
   or server on the Pi) makes the sensor not fresh AT ONCE, until a reading / heartbeat advances again (D2a);
5. the reading VALUE changed within ``freeze_s[sensor]`` (thermal 1.0, radar 1.0, imu 2.0, tc_* 5.0, gnss 5.0;
   ``None`` = not checked). The value is the raw pixels (``pix``) for thermal and the IQ heatmap / range profile /
   points for radar (their frame counters and flags are ignored, so a driver that re-sends old raw data with a new
   frame number is still frozen; D2b); for the other sensors the whole ``data``. Thermal and radar raw values
   never repeat byte for byte while the sensor works (sensor noise), so 1.0 s is enough; a P2 Pro shutter / FFC pause
   longer than 1.0 s therefore gives a short CLOSED (fail closed, documented). Thermocouples (0.25 C steps), the IMU
   (1/16 deg steps on a still vehicle) and a GNSS without a fix can repeat legitimately, so their value windows
   stay long and a Pi-side freeze there is caught by rule 4 instead (D2c). GNSS payloads carry the fix time, so a
   working receiver with a fix changes every fix even when the vehicle is stopped.

Link loss (socket closed, or silence) marks every sensor not fresh at once (rule 1 is checked first).

Worst-case detection at the laptop (5 Hz pipeline tick adds <= 0.2 s): link silence 1.5 s; Pi-side freeze at the
next reading (<= 0.25 s at the 4 Hz thermal wire rate); a thermal / radar value freeze <= 1.0 s after the last
changed frame, i.e. <= 1.0 s after the fault plus the tick; tc / gnss value freeze with seq still advancing 5.0 s
(not within the 2 s test D criterion; the planned test D faults do not freeze them).

``LinkState`` is pure and synchronous (tested without sockets). ``LinkClient`` is the asyncio WebSocket client with
reconnect and exponential backoff; it hands every text frame and every link up/down change to a sink (the
pipeline), which owns a ``LinkState``.

Counted, never fatal: messages failing ``wfgvu.protocol.parse`` (``parse_errors``), Pi ``dropped`` events, and
per-sensor sequence gaps (thermal excluded: the Pi decimates thermal on the wire, so its ``seq`` jumps by design).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

from . import _repo
from .config import SENSORS, LinkConfig
from .decision import AGE_ROUNDING_TOL_S

_repo.vu()
from wfgvu import protocol  # noqa: E402  (shared wire protocol of the sensor head)

log = logging.getLogger("crossing.link")


# Keys of ``data`` whose VALUES are compared for the value-freeze rule (None = the whole ``data``).
VALUE_KEYS: Dict[str, Optional[Tuple[str, ...]]] = {
    "thermal": ("w", "h", "pix"),
    "radar": ("range_profile_db", "az_heatmap", "points"),
}


def payload_digest(data: Any, sensor: Optional[str] = None) -> str:
    """Digest of a reading's sensor VALUES (canonical JSON) used for frozen-value detection: for thermal and radar
    only the raw values (``VALUE_KEYS``), otherwise the whole ``data``."""
    keys = VALUE_KEYS.get(sensor) if sensor is not None else None
    if keys is not None and isinstance(data, dict):
        data = {k: data.get(k) for k in keys}
    blob = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str)
    return hashlib.blake2b(blob.encode("utf-8"), digest_size=16).hexdigest()


@dataclass
class SensorTrack:
    """What the laptop knows about one sensor. All ``*_mono`` values are laptop ``time.monotonic()`` at receipt."""
    sensor: str
    last_rx_mono: Optional[float] = None          # latest reading
    last_seq: Optional[int] = None
    last_t_mono_pi: Optional[float] = None        # Pi t_mono of the latest reading
    not_advancing: str = ""                       # set while the latest reading did not advance seq / t_mono
    last_hb_seq: Optional[int] = None
    last_hb_t_mono_pi: Optional[float] = None
    hb_not_advancing: str = ""                    # same for heartbeats
    pi_freezes: int = 0                           # readings / heartbeats that did not advance
    last_payload_digest: Optional[str] = None
    last_change_mono: Optional[float] = None      # when the payload last differed from the one before
    status_from_pi: Optional[str] = None          # latest heartbeat status
    status_detail: str = ""
    last_hb_mono: Optional[float] = None
    rate_hz_pi: Optional[float] = None            # rate measured by the Pi driver (heartbeat)
    drops: int = 0                                # sequence gaps (readings lost between Pi and laptop)
    seq_resets: int = 0
    n_readings: int = 0
    last_msg: Optional[dict] = None               # latest reading message (as parsed)

    def reset(self) -> None:
        self.__init__(self.sensor)  # type: ignore[misc]


@dataclass
class SensorHealth:
    fresh: bool
    reason: str
    age_s: Optional[float]
    status_from_pi: Optional[str] = None
    drops: int = 0
    rate_hz_pi: Optional[float] = None

    def to_dict(self) -> dict:
        return {"fresh": self.fresh, "reason": self.reason, "age_s": self.age_s,
                "status_from_pi": self.status_from_pi, "drops": self.drops, "rate_hz_pi": self.rate_hz_pi}


@dataclass
class Health:
    """Snapshot at ``t`` (laptop monotonic). ``as_dict()`` gives sensor -> {fresh, reason, age_s, ...}, the form
    ``decision.decide`` reads."""
    t: float
    link_up: bool
    link_reason: str
    sensors: Dict[str, dict] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, dict]:
        return dict(self.sensors)

    def to_dict(self) -> dict:
        return {"t": self.t, "link_up": self.link_up, "link_reason": self.link_reason, "sensors": dict(self.sensors)}


def _maxf(a: Optional[float], b: Any) -> Optional[float]:
    if isinstance(b, (int, float)) and not isinstance(b, bool):
        return float(b) if a is None else max(a, float(b))
    return a


def _not_advancing(last_seq: Optional[int], last_t: Optional[float], seq: Any, t_mono: Any) -> str:
    """Reason text when (seq, t_mono) does not advance past the previous message of the same stream, else ""."""
    if isinstance(seq, int) and not isinstance(seq, bool) and last_seq is not None and seq <= last_seq:
        return "seq %d after %d (repeated or backwards)" % (seq, last_seq)
    if isinstance(t_mono, (int, float)) and not isinstance(t_mono, bool) and last_t is not None \
            and float(t_mono) <= last_t:
        return "t_mono %.4f not after %.4f" % (float(t_mono), last_t)
    return ""


class LinkState:
    """Per-sensor tracks and the freshness rules of DESIGN 5. Not thread-safe: use from one thread / event loop."""

    def __init__(self, cfg: Optional[LinkConfig] = None):
        self.cfg = cfg if cfg is not None else LinkConfig()
        self.tracks: Dict[str, SensorTrack] = {s: SensorTrack(s) for s in SENSORS}
        self.connected = False
        self.connected_since: Optional[float] = None
        self.last_change_reason = "never connected"
        self.last_any_rx: Optional[float] = None
        self.hello: Optional[dict] = None
        self.unit_id: Optional[str] = None
        self.session_id: Optional[str] = None
        self.sim = False                          # sticky: any message with sim true marks the session simulated
        self.parse_errors = 0
        self.last_parse_error = ""
        self.dropped_events = 0
        self.last_dropped_detail = ""
        self.unit_hb_mono: Optional[float] = None
        self.n_messages = 0
        self.connects = 0

    # ------------------------------------------------------------------------------------------- input
    def set_connected(self, flag: bool, now: float, reason: str = "") -> None:
        flag = bool(flag)
        if flag and not self.connected:
            self.connects += 1
            self.connected_since = now
        if not flag:
            self.connected_since = None
        self.connected = flag
        self.last_change_reason = reason or ("connected" if flag else "disconnected")

    def on_text(self, text: Any, now: float) -> Optional[dict]:
        """Parse one wire frame; malformed frames are dropped and counted (returns None)."""
        try:
            msg = protocol.parse(text)
        except protocol.ProtocolError as exc:
            self.parse_errors += 1
            self.last_parse_error = str(exc)[:200]
            return None
        self.on_message(msg, now)
        return msg

    def on_message(self, msg: dict, now: float) -> None:
        """Track one parsed message received at laptop time ``now``."""
        self.n_messages += 1
        self.last_any_rx = now
        if msg.get("sim") is True:
            self.sim = True
        mtype = msg.get("type")
        if mtype == "hello":
            sid = msg.get("session_id")
            if self.session_id is not None and sid != self.session_id:
                for t in self.tracks.values():          # the Pi restarted: nothing from before counts
                    t.reset()
            self.hello = msg
            self.unit_id = msg.get("unit_id")
            self.session_id = sid
            return
        if mtype == "event":
            if msg.get("kind") == "dropped":
                self.dropped_events += 1
                self.last_dropped_detail = str(msg.get("detail", ""))[:200]
            return
        sensor = msg.get("sensor")
        if mtype == "heartbeat":
            if sensor == "unit":
                self.unit_hb_mono = now
                return
            tr = self.tracks.get(sensor)
            if tr is None:
                return
            why = _not_advancing(tr.last_hb_seq, tr.last_hb_t_mono_pi, msg.get("seq"), msg.get("t_mono"))
            tr.hb_not_advancing = why
            if why:
                tr.pi_freezes += 1
            tr.last_hb_seq = msg.get("seq") if isinstance(msg.get("seq"), int) else tr.last_hb_seq
            tr.last_hb_t_mono_pi = _maxf(tr.last_hb_t_mono_pi, msg.get("t_mono"))
            tr.status_from_pi = msg.get("status")
            tr.status_detail = str(msg.get("detail", ""))
            tr.last_hb_mono = now
            tr.rate_hz_pi = msg.get("rate_hz")
            return
        if mtype == "reading":
            tr = self.tracks.get(sensor)
            if tr is None:
                return
            seq = msg.get("seq")
            why = _not_advancing(tr.last_seq, tr.last_t_mono_pi, seq, msg.get("t_mono"))
            tr.not_advancing = why                   # D2a: a repeated / backwards seq or t_mono = Pi-side freeze
            if why:
                tr.pi_freezes += 1
            if tr.last_seq is not None and isinstance(seq, int):
                if seq <= tr.last_seq:
                    tr.seq_resets += 1               # duplicate / stuck driver / restart: not a gap
                elif seq > tr.last_seq + 1 and sensor != "thermal":
                    tr.drops += seq - tr.last_seq - 1
            tr.last_seq = seq if isinstance(seq, int) else tr.last_seq
            tr.last_t_mono_pi = _maxf(tr.last_t_mono_pi, msg.get("t_mono"))
            try:
                dig = payload_digest(msg.get("data"), sensor)
            except (TypeError, ValueError):
                dig = None
            if dig is None or dig != tr.last_payload_digest:
                tr.last_change_mono = now
            tr.last_payload_digest = dig
            tr.last_rx_mono = now
            tr.n_readings += 1
            tr.last_msg = msg

    # ------------------------------------------------------------------------------------------- rules
    def link_status(self, now: float) -> Tuple[bool, str]:
        if not self.connected:
            return False, "link down (%s)" % self.last_change_reason
        if self.last_any_rx is None:
            return False, "link up but nothing received"
        silent = now - self.last_any_rx
        if silent > self.cfg.silence_s:
            return False, "link silent %.1f s" % silent
        return True, ""

    def link_up(self, now: float) -> bool:
        return self.link_status(now)[0]

    def status(self, sensor: str, now: float) -> SensorHealth:
        """(fresh, reason, age_s) for one sensor at laptop time ``now``. The first failing rule is the reason."""
        tr = self.tracks.get(sensor)
        if tr is None:
            return SensorHealth(False, "unknown sensor", None)
        age = None if tr.last_rx_mono is None else now - tr.last_rx_mono
        common = dict(status_from_pi=tr.status_from_pi, drops=tr.drops, rate_hz_pi=tr.rate_hz_pi)
        up, why = self.link_status(now)
        if not up:
            return SensorHealth(False, why, age, **common)
        if tr.last_rx_mono is None:
            return SensorHealth(False, "no reading received", None, **common)
        if age < -AGE_ROUNDING_TOL_S:                # below -1e-3 s is not float rounding (decision._fresh, D6)
            return SensorHealth(False, "reading time in the future", age, **common)
        if age > self.cfg.stale_s:
            return SensorHealth(False, "stale: last reading %.1f s ago" % age, age, **common)
        if tr.last_hb_mono is None:
            return SensorHealth(False, "no Pi heartbeat", age, **common)
        hb_age = now - tr.last_hb_mono
        if hb_age > self.cfg.heartbeat_stale_s:
            return SensorHealth(False, "Pi heartbeat %.1f s old" % hb_age, age, **common)
        if tr.status_from_pi != "ok":
            return SensorHealth(False, "Pi status %s: %s" % (tr.status_from_pi, tr.status_detail[:80]), age,
                                **common)
        if tr.not_advancing:
            return SensorHealth(False, "frozen on the Pi: reading %s" % tr.not_advancing, age, **common)
        if tr.hb_not_advancing:
            return SensorHealth(False, "frozen on the Pi: heartbeat %s" % tr.hb_not_advancing, age, **common)
        fz = self.cfg.freeze_s.get(sensor)
        if fz is not None:
            still = now - (tr.last_change_mono if tr.last_change_mono is not None else now)
            if still > fz:
                if tr.last_change_mono is not None and tr.last_rx_mono <= tr.last_change_mono + 1e-9:
                    # no reading at all since the last change: the stream stopped (not fresh either way)
                    return SensorHealth(False, "no reading for %.2f s (values unchanged for %.2f s)" % (age, still),
                                        age, **common)
                return SensorHealth(False, "frozen: values unchanged for %.2f s" % still, age, **common)
        return SensorHealth(True, "", age, **common)

    def fresh(self, sensor: str, now: float) -> bool:
        return self.status(sensor, now).fresh

    def health(self, now: float) -> Health:
        up, why = self.link_status(now)
        return Health(t=now, link_up=up, link_reason=why,
                      sensors={s: self.status(s, now).to_dict() for s in SENSORS})

    def info(self) -> dict:
        return {"connected": self.connected, "unit_id": self.unit_id, "session_id": self.session_id,
                "sim": self.sim, "parse_errors": self.parse_errors, "last_parse_error": self.last_parse_error,
                "dropped_events": self.dropped_events, "last_dropped_detail": self.last_dropped_detail,
                "connects": self.connects, "n_messages": self.n_messages,
                "pi_version": (self.hello or {}).get("version"),
                "thermal_wire_hz": (self.hello or {}).get("thermal_wire_hz")}


class LinkClient:
    """asyncio WebSocket client to the roof unit with reconnect and exponential backoff.

    ``sink`` needs ``on_text(text, now)`` and ``set_connected(flag, now, reason)`` (the Pipeline has both).
    The connection is dropped and re-opened if nothing arrives for ``2 * silence_s``. ``clock`` is the laptop
    monotonic clock (injectable for tests).
    """

    def __init__(self, url: str, sink: Any, cfg: Optional[LinkConfig] = None,
                 clock: Callable[[], float] = time.monotonic):
        self.url = url
        self.sink = sink
        self.cfg = cfg if cfg is not None else LinkConfig()
        self.clock = clock
        self.attempts = 0
        self.last_error = ""
        self.backoff_s = self.cfg.reconnect_min_s

    def next_backoff(self) -> float:
        b = self.backoff_s
        self.backoff_s = min(self.cfg.reconnect_max_s, self.backoff_s * 2.0)
        return b

    async def run(self, stop: Optional[asyncio.Event] = None) -> None:
        from websockets.asyncio.client import connect
        from websockets.exceptions import ConnectionClosed, InvalidHandshake, InvalidURI

        stop = stop or asyncio.Event()
        while not stop.is_set():
            self.attempts += 1
            reason = ""
            try:
                async with connect(self.url, open_timeout=self.cfg.open_timeout_s,
                                   ping_interval=self.cfg.ping_interval_s, ping_timeout=self.cfg.ping_timeout_s,
                                   max_size=self.cfg.max_frame_bytes, close_timeout=1.0) as ws:
                    self.backoff_s = self.cfg.reconnect_min_s
                    self.sink.set_connected(True, self.clock(), "connected to %s" % self.url)
                    log.info("connected to %s", self.url)
                    while not stop.is_set():
                        try:
                            text = await asyncio.wait_for(ws.recv(), timeout=2.0 * self.cfg.silence_s)
                        except asyncio.TimeoutError:
                            reason = "no data for %.1f s" % (2.0 * self.cfg.silence_s)
                            break
                        self.sink.on_text(text, self.clock())
            except (OSError, ConnectionClosed, InvalidHandshake, InvalidURI, asyncio.TimeoutError) as exc:
                reason = "%s: %s" % (type(exc).__name__, exc)
            except Exception as exc:  # noqa: BLE001 - never let the client die; report and retry
                reason = "unexpected %s: %s" % (type(exc).__name__, exc)
                log.exception("link client error")
            self.last_error = reason
            self.sink.set_connected(False, self.clock(), reason or "closed")
            if stop.is_set():
                break
            delay = self.next_backoff()
            log.info("link down (%s); retry in %.1f s", reason, delay)
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    def info(self) -> dict:
        return {"url": self.url, "attempts": self.attempts, "last_error": self.last_error,
                "next_backoff_s": self.backoff_s}
