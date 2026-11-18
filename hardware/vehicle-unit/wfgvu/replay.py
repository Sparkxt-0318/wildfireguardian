"""Read a recorded session (DESIGN.md section 4) for sim mode and offline analysis.

Session directory layout (written by ``wfgvu.recorder`` on the Pi, by ``recorder.write_session`` and by
``wfgvu.synth``)::

    session.json                      unit_id, session_id, started_utc, sim, config, (scenario, truth if synth),
                                      t_mono_first / t_mono_last when the recorder closed cleanly
    <sensor>.jsonl.gz                 one protocol reading or heartbeat per line, exactly as sent
    <sensor>.<n>.jsonl.gz             rotated continuation parts, n = 1, 2, ...
    events.jsonl.gz, unit.jsonl.gz    events and server heartbeats (not sensor streams)
    radar_uart.bin                    raw data-UART bytes (live only)

``load(dir) -> Session``; ``Session.streams[sensor]`` is a ``SensorStream``. Iterating a stream yields parsed
messages lazily (thermal files can be large) in ``t_mono`` order: files are in write order, which is ``t_mono``
order up to thread-scheduling jitter, and a 256-message reorder window sorts that out. ``Session.merged()``
merges all streams by ``t_mono`` (heap merge).

Robustness: a gzip file cut off by a power loss (no end-of-stream marker) is read up to the last complete line;
lines that fail ``protocol.parse`` are skipped and counted in ``SensorStream.bad_lines``. A session.json that is
empty, truncated or not a JSON object (power cut right after the session started) does not stop the replay:
``Session.info`` is then ``{}`` and ``Session.info_error`` says why ("session_json_unreadable"; "session_json_missing"
when there is none); ``session_id`` / ``unit_id`` fall back to the directory name and ``sim`` to the recorded
messages' own flags (true if none can be read). Nothing permissive is assumed for missing config or truth.

Sim playback: ``Session.start(speed, loop)`` fixes a shared ``SimClock``; ``SensorStream.play(stop_event)`` yields
each message when it is due, keeping the recorded spacing divided by ``speed``. With ``loop`` every stream restarts
after ``Session.duration`` so all sensors stay in step.
"""
from __future__ import annotations

import heapq
import itertools
import json
import re
import threading
import time
import zlib
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from . import protocol

_SID_RE = re.compile(r"^(?P<unit>.+)-\d{8}T\d{6}Z(?:-\d+)?$")
_PART_RE = re.compile(r"^(?P<name>[a-z_]+)(?:\.(?P<n>\d+))?\.jsonl\.gz$")
REORDER_WINDOW = 256     # messages; disorder within a file larger than this is passed through as is
LOOP_GAP_S = 0.5         # pause between the end of a loop and the restart, seconds of recorded time


def stream_files(session_dir: Path, name: str) -> List[Path]:
    """All parts of ``<name>.jsonl.gz`` in order (base file first, then ``.1``, ``.2`` ...)."""
    parts = []
    for p in Path(session_dir).glob("%s*.jsonl.gz" % name):
        m = _PART_RE.match(p.name)
        if m and m.group("name") == name:
            parts.append((int(m.group("n") or 0), p))
    return [p for _, p in sorted(parts)]


def iter_lines(path: Path, chunk_size: int = 65536) -> Iterator[bytes]:
    """Lines of a gzip file (one or more members), tolerating damage: a truncated tail (power cut before the final
    flush) or a corrupt later part (e.g. a member appended after a power-cut stream) ends the file at the last
    complete line BEFORE the damage, instead of hiding the lines already readable. A partial last line is dropped."""
    try:
        fh = open(path, "rb")
    except FileNotFoundError:
        return
    with fh:
        d = zlib.decompressobj(31)
        pending: List[bytes] = []                            # pieces of the current, incomplete line

        def lines_of(out: bytes) -> Iterator[bytes]:
            start = 0
            while True:
                i = out.find(b"\n", start)
                if i < 0:
                    if start < len(out):
                        pending.append(out[start:])
                    return
                pending.append(out[start:i + 1])
                line = b"".join(pending)
                pending.clear()
                yield line
                start = i + 1

        while True:
            try:
                chunk = fh.read(chunk_size)
            except OSError:
                return
            if not chunk:
                return
            while chunk:
                saved = d.copy()
                try:
                    out = d.decompress(chunk)
                except zlib.error:
                    # damage inside this chunk: decode it again byte by byte up to the bad byte (only on damage)
                    d = saved
                    k = 0
                    while k < len(chunk):
                        try:
                            out = d.decompress(chunk[k:k + 1])
                        except zlib.error:
                            return
                        k += 1
                        yield from lines_of(out)
                        if d.eof:
                            break
                    if not d.eof:                            # (all decoded: nothing was wrong after all)
                        chunk = b""
                        continue
                    rest = d.unused_data + chunk[k:]
                    d = zlib.decompressobj(31)
                    chunk = rest
                    continue
                yield from lines_of(out)
                if d.eof:                                    # next gzip member (rotation never appends, but a
                    chunk = d.unused_data                    # concatenated file is still valid gzip)
                    d = zlib.decompressobj(31)
                else:
                    chunk = b""


class SimClock:
    """Maps recorded time (seconds since session start) to this machine's monotonic clock.

    ``due_mono(t_rel) = start_mono + t_rel / speed``. Shared by every driver of a sim session.
    """

    def __init__(self, speed: float = 1.0, start_mono: Optional[float] = None):
        if not speed > 0:
            raise ValueError("speed must be > 0")
        self.speed = float(speed)
        self.start_mono = time.monotonic() if start_mono is None else start_mono

    def due_mono(self, t_rel: float) -> float:
        return self.start_mono + t_rel / self.speed

    def rel_now(self) -> float:
        return (time.monotonic() - self.start_mono) * self.speed

    def wait_until(self, t_rel: float, stop: Optional[threading.Event] = None) -> bool:
        """Sleep until ``t_rel`` is due. Returns False if ``stop`` was set first."""
        while True:
            dt = self.due_mono(t_rel) - time.monotonic()
            if dt <= 0:
                return not (stop is not None and stop.is_set())
            if stop is not None:
                if stop.wait(min(dt, 0.2)):
                    return False
            else:
                time.sleep(min(dt, 0.2))


class SensorStream:
    """Recorded messages of one sensor (readings and heartbeats), read lazily from its gzip parts."""

    def __init__(self, session: "Session", sensor: str, files: List[Path]):
        self.session = session
        self.sensor = sensor
        self.files = files
        self.bad_lines = 0

    def _raw(self) -> Iterator[dict]:
        for path in self.files:
            for line in iter_lines(path):
                try:
                    msg = protocol.parse(line)
                except protocol.ProtocolError:
                    self.bad_lines += 1
                    continue
                if msg["type"] in ("reading", "heartbeat") and msg.get("sensor") == self.sensor:
                    yield msg
                else:
                    self.bad_lines += 1

    def __iter__(self) -> Iterator[dict]:
        """Messages in ``t_mono`` order. Files are in write order; a reorder window of ``REORDER_WINDOW``
        messages fixes the small disorder between a driver's reading and heartbeat threads."""
        heap: list = []
        n = 0
        for msg in self._raw():
            heapq.heappush(heap, (float(msg["t_mono"]), n, msg))
            n += 1
            if len(heap) > REORDER_WINDOW:
                yield heapq.heappop(heap)[2]
        while heap:
            yield heapq.heappop(heap)[2]

    def readings(self) -> Iterator[dict]:
        return (m for m in self if m["type"] == "reading")

    def first_t(self) -> Optional[float]:
        for m in self:
            return float(m["t_mono"])
        return None

    def last_t(self) -> Optional[float]:
        last = None
        for m in self:
            last = float(m["t_mono"])
        return last

    def timed(self, loop: bool = False) -> Iterator[tuple]:
        """Yield ``(t_rel_s, msg)``: recorded seconds since session start, plus ``k * duration`` on loop k."""
        t0 = self.session.t0
        period = self.session.duration + LOOP_GAP_S if loop else 0.0
        for k in (itertools.count() if loop else range(1)):
            n = 0
            for msg in self:
                n += 1
                yield float(msg["t_mono"]) - t0 + k * period, msg
            if n == 0:
                return

    def play(self, stop: Optional[threading.Event] = None) -> Iterator[dict]:
        """Yield messages when due on the session's ``SimClock`` (starts it if needed). Ends when exhausted
        (never with ``loop``) or when ``stop`` is set."""
        clock = self.session.clock or self.session.start()
        for t_rel, msg in self.timed(loop=self.session.loop):
            if not clock.wait_until(t_rel, stop):
                return
            yield msg

    def wait_session_end(self, stop: Optional[threading.Event] = None) -> bool:
        """Block until the whole session's recorded time has elapsed (sim ended). False if stopped first."""
        clock = self.session.clock or self.session.start()
        return clock.wait_until(self.session.duration, stop)


class Session:
    """A recorded session directory. ``streams`` maps sensor name -> ``SensorStream`` for sensors with data."""

    def __init__(self, path: Path):
        self.path = Path(path)
        info_path = self.path / "session.json"
        self.info: dict = {}
        self.info_error: Optional[str] = None
        if info_path.exists():
            try:
                info = json.loads(info_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                info = None
            if isinstance(info, dict):
                self.info = info
            else:
                self.info_error = "session_json_unreadable"
        else:
            self.info_error = "session_json_missing"
        self.streams: Dict[str, SensorStream] = {}
        for sensor in protocol.SENSORS:
            files = stream_files(self.path, sensor)
            if files:
                self.streams[sensor] = SensorStream(self, sensor, files)
        self.clock: Optional[SimClock] = None
        self.loop = False
        self._lock = threading.Lock()
        self._t0: Optional[float] = None
        self._duration: Optional[float] = None

    @property
    def unit_id(self) -> str:
        if self.info_error == "session_json_unreadable":
            m = _SID_RE.match(self.path.name)
            if m:
                return m.group("unit")
        return self.info.get("unit_id", "VU-01")

    @property
    def session_id(self) -> Optional[str]:
        if self.info_error == "session_json_unreadable":
            return self.info.get("session_id") or self.path.name
        return self.info.get("session_id")

    @property
    def sim(self) -> bool:
        if self.info_error == "session_json_unreadable":
            # the messages carry their own flag: first readable message of each stream; any sim -> SIMULATED,
            # nothing readable -> SIMULATED too (never claim unknown data is real)
            firsts = [next(iter(st._raw()), None) for st in self.streams.values()]
            flags = [bool(m.get("sim", True)) for m in firsts if m is not None]
            return any(flags) or not flags
        return bool(self.info.get("sim", False))

    @property
    def t0(self) -> float:
        """Recorded ``t_mono`` of the first message of the session."""
        if self._t0 is None:
            t = self.info.get("t_mono_first")
            if t is None:
                firsts = [s.first_t() for s in self.streams.values()]
                firsts = [f for f in firsts if f is not None]
                t = min(firsts) if firsts else 0.0
            self._t0 = float(t)
        return self._t0

    @property
    def duration(self) -> float:
        """Recorded seconds from the first to the last message (scans the files if session.json lacks it)."""
        if self._duration is None:
            last = self.info.get("t_mono_last")
            if last is None:
                lasts = [s.last_t() for s in self.streams.values()]
                lasts = [x for x in lasts if x is not None]
                last = max(lasts) if lasts else self.t0
            self._duration = max(0.0, float(last) - self.t0)
        return self._duration

    def start(self, speed: float = 1.0, loop: bool = False) -> SimClock:
        """Fix the playback clock shared by all streams (idempotent: the first call wins)."""
        with self._lock:
            if self.clock is None:
                _ = self.t0
                if loop:
                    _ = self.duration
                self.loop = bool(loop)
                self.clock = SimClock(speed)
            return self.clock

    def merged(self) -> Iterator[dict]:
        """All sensor messages merged by recorded ``t_mono``."""
        return heapq.merge(*[iter(s) for s in self.streams.values()], key=lambda m: m["t_mono"])

    def events(self) -> Iterator[dict]:
        for path in stream_files(self.path, "events"):
            for line in iter_lines(path):
                try:
                    yield protocol.parse(line)
                except protocol.ProtocolError:
                    continue


def load(session_dir) -> Session:
    """Open a recorded session directory. Raises ``FileNotFoundError`` if it has no sensor streams."""
    s = Session(Path(session_dir))
    if not s.path.is_dir():
        raise FileNotFoundError("no such session directory: %s" % s.path)
    if not s.streams:
        raise FileNotFoundError("no <sensor>.jsonl.gz streams in %s" % s.path)
    return s
