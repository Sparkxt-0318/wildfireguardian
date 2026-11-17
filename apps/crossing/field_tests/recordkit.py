"""Laptop-side recorder used by the field-test record scripts (tests A, B, C, E, F) and by test D.

It connects to the unit's WebSocket (DESIGN.md section 2) as an ordinary client and writes a run directory:

    <run>/session.json          unit/session ids from the messages, hello, counts, t_mono_first/last (Pi clock)
    <run>/<sensor>.jsonl.gz     every reading/heartbeat line exactly as received (wfgvu.replay.load can read it)
    <run>/events.jsonl.gz       events; <run>/unit.jsonl.gz: server ("unit") heartbeats
    <run>/rx.jsonl.gz           one line per received message: laptop receipt time t_rx (time.monotonic of THIS
                                laptop), the Pi t_mono, type, sensor, seq; plus link lines (connect / disconnect /
                                connect_failed). Used for link-dropout and latency analysis.
    <run>/marks.jsonl           operator / protocol marks: laptop t_rx, and the estimated Pi t_mono at that moment
    <run>/trial.json            test-specific metadata (written by the record script)

The Pi records its own full-rate copy in hardware/vehicle-unit/records/<session_id>/; this copy only holds what
reached the laptop (thermal decimated to the wire rate, minus any messages lost on the link).

Clock mapping: the Pi t_mono and the laptop monotonic clock are unrelated. For each received message
offset = t_rx - t_mono = (true offset) + (network + processing delay >= 0); the smallest offset over the last 200
messages is the best estimate of the true offset (delays are positive). Marks store `pi_t_mono = t_rx - offset`.
Accuracy is limited by the minimum link delay (normally a few ms on a local hotspot); not measured on hardware.
"""
from __future__ import annotations

import asyncio
import collections
import gzip
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from . import common  # noqa: F401  (sets sys.path for wfgvu)
from wfgvu import protocol


class SessionWriter:
    """Writes one run directory from received wire texts. Thread-safe for marks vs messages."""

    OFFSET_WINDOW = 200

    def __init__(self, out_dir, meta: Optional[dict] = None, clock: Callable[[], float] = time.monotonic):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta = dict(meta or {})
        self.clock = clock
        self._files: Dict[str, gzip.GzipFile] = {}
        self._rx = gzip.open(self.dir / "rx.jsonl.gz", "wt", compresslevel=5)
        self._marks = open(self.dir / "marks.jsonl", "a")
        self._lock = threading.Lock()
        self._offsets: collections.deque = collections.deque(maxlen=self.OFFSET_WINDOW)
        self.counts: Dict[str, int] = {}
        self.bad = 0
        self.hello: Optional[dict] = None
        self.unit_ids: List[str] = []
        self.session_ids: List[str] = []
        self.sim_flags: set = set()
        self.t_first: Optional[float] = None
        self.t_last: Optional[float] = None
        self.connected = False
        self.closed = False

    # -- link events
    def on_connect(self, url: str = "", t_rx: Optional[float] = None) -> None:
        self.connected = True
        self._link("connect", url, t_rx)

    def on_disconnect(self, detail: str = "", t_rx: Optional[float] = None) -> None:
        if self.connected:
            self.connected = False
            self._link("disconnect", detail, t_rx)

    def on_connect_failed(self, detail: str = "", t_rx: Optional[float] = None) -> None:
        self._link("connect_failed", detail, t_rx)

    def _link(self, kind: str, detail: str, t_rx: Optional[float]) -> None:
        t = self.clock() if t_rx is None else float(t_rx)
        with self._lock:
            self._rx.write(json.dumps({"t_rx": t, "link": kind, "detail": str(detail)}) + "\n")

    # -- messages
    def on_text(self, text, t_rx: Optional[float] = None) -> Optional[dict]:
        """Parse and store one wire message. Returns the parsed dict, or None if it failed protocol.parse
        (counted in `bad` and logged in rx.jsonl.gz as type "bad")."""
        t = self.clock() if t_rx is None else float(t_rx)
        if isinstance(text, (bytes, bytearray)):
            text = bytes(text).decode("utf-8", "replace")
        try:
            msg = protocol.parse(text)
        except protocol.ProtocolError as exc:
            with self._lock:
                self.bad += 1
                self._rx.write(json.dumps({"t_rx": t, "type": "bad", "detail": str(exc)[:200]}) + "\n")
            return None
        mtype = msg["type"]
        if mtype in ("reading", "heartbeat"):
            name = msg["sensor"]
        elif mtype == "event":
            name = "events"
        else:
            name = None
        tm = float(msg["t_mono"])
        with self._lock:
            if mtype == "hello":
                self.hello = msg
            if msg["unit_id"] not in self.unit_ids:
                self.unit_ids.append(msg["unit_id"])
            if msg["session_id"] not in self.session_ids:
                self.session_ids.append(msg["session_id"])
            self.sim_flags.add(bool(msg["sim"]))
            if name is not None:
                fh = self._files.get(name)
                if fh is None:
                    fh = self._files[name] = gzip.open(self.dir / ("%s.jsonl.gz" % name), "wt", compresslevel=5)
                fh.write(text.rstrip("\n") + "\n")
                self.counts[name] = self.counts.get(name, 0) + 1
            self.t_first = tm if self.t_first is None else min(self.t_first, tm)
            self.t_last = tm if self.t_last is None else max(self.t_last, tm)
            self._offsets.append(t - tm)
            self._rx.write(json.dumps({"t_rx": t, "t_mono": tm, "type": mtype, "sensor": msg.get("sensor"),
                                       "seq": msg.get("seq"), "status": msg.get("status"),
                                       "session_id": msg["session_id"]}) + "\n")
        return msg

    def offset(self) -> Optional[float]:
        with self._lock:
            return min(self._offsets) if self._offsets else None

    def mark(self, kind: str, note: str = "", t_rx: Optional[float] = None, **extra: Any) -> dict:
        """Record a protocol / operator mark at laptop time t_rx (now by default)."""
        t = self.clock() if t_rx is None else float(t_rx)
        off = self.offset()
        rec = {"t_rx": t, "pi_t_mono": None if off is None else t - off, "kind": kind, "note": note,
               "utc": common.utc_now()}
        rec.update(extra)
        with self._lock:
            self._marks.write(json.dumps(common.clean(rec)) + "\n")
            self._marks.flush()
        return rec

    def flush(self) -> None:
        with self._lock:
            for fh in self._files.values():
                fh.flush()
            self._rx.flush()

    def close(self, trial: Optional[dict] = None) -> Path:
        if self.closed:
            return self.dir
        self.closed = True
        with self._lock:
            for fh in self._files.values():
                fh.close()
            self._rx.close()
            self._marks.close()
        info = {"unit_id": self.unit_ids[0] if self.unit_ids else "unknown",
                "session_id": self.session_ids[0] if self.session_ids else "unknown",
                "session_ids": self.session_ids, "sim": True in self.sim_flags,
                "hello": self.hello, "counts": self.counts, "bad_messages": self.bad,
                "t_mono_first": self.t_first, "t_mono_last": self.t_last,
                "recorded_by": "apps/crossing/field_tests/recordkit.py (laptop copy of the wire stream)"}
        info.update(self.meta.get("session_extra", {}))
        common.write_json(self.dir / "session.json", info)
        if trial is not None:
            common.write_json(self.dir / "trial.json", trial)
        return self.dir


# ---------------------------------------------------------------------------------------------- WS client loop
async def run_ws(url: str, writer: SessionWriter, stop: asyncio.Event, reconnect_s: float = 1.0,
                 open_timeout: float = 3.0, on_message: Optional[Callable[[dict], None]] = None) -> None:
    """Receive from `url` into `writer` until `stop` is set; reconnect every `reconnect_s` after a drop."""
    import websockets
    while not stop.is_set():
        try:
            async with websockets.connect(url, open_timeout=open_timeout, max_size=2 ** 24,
                                          ping_interval=1.0, ping_timeout=2.0) as ws:
                writer.on_connect(url)
                while not stop.is_set():
                    try:
                        text = await asyncio.wait_for(ws.recv(), timeout=0.25)
                    except asyncio.TimeoutError:
                        continue
                    msg = writer.on_text(text)
                    if msg is not None and on_message is not None:
                        on_message(msg)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - any link failure is recorded and retried
            if writer.connected:
                writer.on_disconnect("%s: %s" % (type(exc).__name__, exc))
            else:
                writer.on_connect_failed("%s: %s" % (type(exc).__name__, exc))
            try:
                await asyncio.wait_for(stop.wait(), timeout=reconnect_s)
            except asyncio.TimeoutError:
                pass
    writer.on_disconnect("stopped")


# ---------------------------------------------------------------------------------------------- timed protocol
Phase = Tuple[str, float, str]          # (mark kind, duration s, instruction printed at its start)


async def run_phases(writer: SessionWriter, phases: Sequence[Phase], stop: asyncio.Event,
                     out=sys.stdout, countdown_s: int = 5, sleep=asyncio.sleep) -> None:
    """Run a timed protocol: before each phase print a countdown, then mark `<kind>` at "NOW" and print the
    instruction. The operator acts on "NOW" (human timing error of a few tenths of a second, not measured)."""
    for kind, dur, text in phases:
        if stop.is_set():
            return
        print("\nNext: %s" % text, file=out)
        for k in range(countdown_s, 0, -1):
            print("  %d ..." % k, file=out, flush=True)
            await sleep(1.0)
        writer.mark(kind, text)
        print(">>> NOW: %s   (phase %s, %.0f s)" % (text, kind, dur), file=out, flush=True)
        t_end = time.monotonic() + dur
        while not stop.is_set():
            left = t_end - time.monotonic()
            if left <= 0:
                break
            await sleep(min(1.0, left))
    writer.mark("end", "protocol finished")
    print("\nProtocol finished.", file=out, flush=True)


async def stdin_marks(writer: SessionWriter, stop: asyncio.Event) -> None:
    """Every line typed on stdin becomes an `operator` mark (the text is the note). 'q' stops the run."""
    loop = asyncio.get_running_loop()
    while not stop.is_set():
        line = await loop.run_in_executor(None, sys.stdin.readline)
        if not line:
            return
        line = line.strip()
        if line.lower() == "q":
            writer.mark("operator_stop", "q typed")
            stop.set()
            return
        writer.mark("operator", line)
        print("  marked: %s" % (line or "(no note)"), flush=True)


def record_run(url: str, run_dir, trial: dict, phases: Sequence[Phase], tail_s: float = 0.0,
               warmup_s: float = 3.0, interactive: bool = True, countdown_s: int = 5,
               no_data_timeout_s: float = 15.0) -> Path:
    """Connect, wait `warmup_s` for data, run the timed phases, record `tail_s` more, close and write trial.json.
    Refuses to start the protocol if nothing arrives within 15 s of connecting (prints the reason)."""
    writer = SessionWriter(run_dir, {"session_extra": {"trial": trial.get("run_id")}})

    async def main():
        stop = asyncio.Event()
        rx = asyncio.create_task(run_ws(url, writer, stop))
        tasks = [rx]
        if interactive and sys.stdin and sys.stdin.isatty():
            tasks.append(asyncio.create_task(stdin_marks(writer, stop)))
        try:
            t0 = time.monotonic()
            while sum(writer.counts.values()) == 0 and time.monotonic() - t0 < no_data_timeout_s:
                await asyncio.sleep(0.2)
            if sum(writer.counts.values()) == 0:
                why = "no data from the unit within %.0f s" % no_data_timeout_s
                writer.mark("abort", why)
                print("%s (%s): run aborted (recorded as such)." % (why, url), file=sys.stderr)
                trial["aborted"] = why
                return
            await asyncio.sleep(warmup_s)
            await run_phases(writer, phases, stop, countdown_s=countdown_s)
            if tail_s > 0:
                await asyncio.sleep(tail_s)
        finally:
            stop.set()
            for t in tasks[1:]:
                t.cancel()
            try:
                await asyncio.wait_for(rx, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        writer.mark("operator_stop", "Ctrl-C")
        trial["interrupted"] = True
    trial["counts"] = dict(writer.counts)
    trial["bad_messages"] = writer.bad
    trial["sim"] = True in writer.sim_flags
    return writer.close(trial)


def read_marks(run_dir) -> List[dict]:
    p = Path(run_dir) / "marks.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def read_rx(run_dir) -> List[dict]:
    """Receipt log of a run: rx.jsonl.gz from this recorder, or else the crossing app research log's
    wire.jsonl.gz ({"rx", "msg"} / {"rx", "link": "up"|"down"}), converted to the same line shape."""
    p = Path(run_dir) / "rx.jsonl.gz"
    if not p.exists():
        return _read_wire(Path(run_dir) / "wire.jsonl.gz")
    out = []
    try:
        with gzip.open(p, "rt") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except (EOFError, OSError):
        pass                       # truncated tail (laptop crash): keep what was read
    return out


def _read_wire(p: Path) -> List[dict]:
    out: List[dict] = []
    if not p.exists():
        return out
    try:
        with gzip.open(p, "rt") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "link" in r:
                    out.append({"t_rx": float(r["rx"]), "link": "connect" if r["link"] == "up" else "disconnect",
                                "detail": r.get("reason", "")})
                elif isinstance(r.get("msg"), dict):
                    m = r["msg"]
                    out.append({"t_rx": float(r["rx"]), "t_mono": m.get("t_mono"), "type": m.get("type"),
                                "sensor": m.get("sensor"), "seq": m.get("seq"), "status": m.get("status"),
                                "session_id": m.get("session_id")})
    except (EOFError, OSError):
        pass
    return out
