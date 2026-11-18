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

Flux-disc guard (DiscGuard, used by every record script through record_run, and by test D): the copper flux disc
sits on printed PETG tabs, so a run STOPS and prints "STOP: flux disc at X C >= 70 C (PETG tabs)" as soon as a
tc_plate reading (no MAX31855 fault) is >= the limit (crossing.yaml flux.disc_max_c, 70 C, user-set; 69.75 C does
not stop, 70.00 C does), and, while the run needs the disc temperature (whole run, or only the listed phases),
when no valid tc_plate reading arrived for more than 2 s (missing stream, link drop or thermocouple fault).
trial.json gets stop_reason DISC_OVER_70C / DISC_TEMP_UNKNOWN (null when not stopped), stop_detail and a
disc_guard summary (limit, peak, readings); marks.jsonl gets a `disc_stop` mark. The guard only stops the
RECORDING and warns: the operator must remove the heat source. Not tested on hardware.
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


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


class DiscGuard:
    """Stop rule for the flux disc (see module docstring). Feed it every received message (``on_message``) or crossing
    app State (``on_state``) with this laptop's receipt time, and call ``check(now)`` periodically (missing-data
    rule). Both return the stop reason once triggered (it latches), else None. Times are seconds on one clock."""

    MISSING_S = 2.0

    def __init__(self, disc_max_c: Optional[float] = None, needs_plate: bool = True,
                 missing_s: float = MISSING_S):
        # never above the user's 70 C (PETG tabs), whatever crossing.yaml or the caller says
        self.disc_max_c = common.cap_disc_max_c(common.disc_max_c() if disc_max_c is None else disc_max_c)
        self.missing_s = float(missing_s)
        self.needs_plate = bool(needs_plate)
        self.need_since: Optional[float] = None       # when the current "needs plate" stretch began
        self.armed_t: Optional[float] = None          # first message received
        self.last_ok_t: Optional[float] = None        # last valid tc_plate reading (receipt time)
        self.last_c: Optional[float] = None
        self.peak_c: Optional[float] = None
        self.n_readings = 0
        self.n_bad = 0
        self.stop_reason: Optional[str] = None
        self.stop_detail = ""
        self.stop_t: Optional[float] = None
        self.stop_pi_t: Optional[float] = None
        self.stop_c: Optional[float] = None

    def set_needs_plate(self, flag: bool, t: float) -> None:
        """Start / end a stretch during which a missing disc temperature stops the run (2 s grace from ``t``)."""
        flag = bool(flag)
        if flag and not self.needs_plate:
            self.need_since = float(t)
        self.needs_plate = flag

    def _stop(self, reason: str, t: float, detail: str, pi_t=None, temp_c=None) -> str:
        self.stop_reason, self.stop_detail, self.stop_t = reason, detail, float(t)
        self.stop_pi_t = None if pi_t is None else float(pi_t)
        self.stop_c = temp_c
        return reason

    def _reading(self, temp_c, fault, t: float, pi_t=None) -> Optional[str]:
        if self.stop_reason:
            return self.stop_reason
        self.n_readings += 1
        if fault or not _num(temp_c):
            self.n_bad += 1
            return self.check(t)
        v = float(temp_c)
        self.last_c = v
        self.peak_c = v if self.peak_c is None else max(self.peak_c, v)
        if v >= self.disc_max_c:
            return self._stop(common.STOP_DISC_OVER, t, "flux disc at %.2f C >= %.0f C (PETG tabs)"
                              % (v, self.disc_max_c), pi_t, v)
        self.last_ok_t = float(t)
        return None

    def on_message(self, msg: dict, t: float) -> Optional[str]:
        """One parsed unit message received at time t."""
        if self.stop_reason:
            return self.stop_reason
        if self.armed_t is None:
            self.armed_t = float(t)
        if msg.get("type") == "reading" and msg.get("sensor") == "tc_plate":
            d = msg.get("data") or {}
            return self._reading(d.get("temp_c"), d.get("fault"), t, msg.get("t_mono"))
        return self.check(t)

    def on_state(self, state: dict, t: float) -> Optional[str]:
        """One crossing-app State (test D without --pi): flux.tc_plate_c and tc.tc_plate.fault."""
        if self.stop_reason:
            return self.stop_reason
        if self.armed_t is None:
            self.armed_t = float(t)
        fl = state.get("flux") if isinstance(state, dict) else None
        tc = ((state.get("tc") or {}).get("tc_plate") if isinstance(state, dict) else None) or {}
        if isinstance(fl, dict) and "tc_plate_c" in fl:
            return self._reading(fl.get("tc_plate_c"), tc.get("fault") if isinstance(tc, dict) else None, t)
        return self.check(t)

    def check(self, t: float) -> Optional[str]:
        """Missing-data rule: while the run needs the disc temperature, > missing_s without a valid reading stops."""
        if self.stop_reason or not self.needs_plate or self.armed_t is None:
            return self.stop_reason
        ref = max(x for x in (self.last_ok_t, self.armed_t, self.need_since) if x is not None)
        if float(t) - ref > self.missing_s:
            last = "never" if self.last_ok_t is None else "%.1f s ago" % (float(t) - self.last_ok_t)
            return self._stop(common.STOP_DISC_UNKNOWN, t, "no valid flux-disc temperature for > %.0f s (missing or "
                              "faulted tc_plate; last valid reading %s)" % (self.missing_s, last))
        return None

    def warning(self) -> str:
        if self.stop_reason == common.STOP_DISC_OVER:
            return ("STOP: flux disc at %.2f C >= %.0f C (PETG tabs). Remove the heat source NOW. Run stopped "
                    "(stop_reason %s)." % (self.stop_c, self.disc_max_c, self.stop_reason))
        if self.stop_reason == common.STOP_DISC_UNKNOWN:
            return ("STOP: flux disc temperature unknown (%s). Remove the heat source until tc_plate reads again. "
                    "Run stopped (stop_reason %s)." % (self.stop_detail, self.stop_reason))
        return ""

    def summary(self) -> dict:
        return {"disc_max_c": self.disc_max_c, "disc_max_user_set": True, "missing_s": self.missing_s,
                "needs_plate_at_end": self.needs_plate, "n_plate_readings": self.n_readings,
                "n_plate_bad": self.n_bad, "peak_c": self.peak_c, "last_c": self.last_c,
                "stop_reason": self.stop_reason, "stop_detail": self.stop_detail, "stop_pi_t_mono": self.stop_pi_t,
                "stop_disc_c": self.stop_c}

    def annotate(self, trial: dict) -> dict:
        """Write stop_reason / stop_detail / disc_max_c / disc_guard into ``trial`` (in place) and return it."""
        trial["stop_reason"] = self.stop_reason
        trial["stop_detail"] = self.stop_detail
        trial["disc_max_c"] = self.disc_max_c
        trial["disc_guard"] = self.summary()
        return trial


EXIT_DISC_STOP = 3
EXIT_ABORTED = 4


def report_end(trial: dict, run_dir, out=sys.stdout) -> int:
    """Print how a recorded run ended and return the record script's exit code: 3 when the disc guard stopped it,
    4 when the run was aborted (e.g. no data from the unit; trial.json "aborted"), else 0."""
    if trial.get("stop_reason"):
        print("STOPPED (%s): %s\nRun kept in %s; the analysis reports it as measured."
              % (trial["stop_reason"], trial.get("stop_detail", ""), run_dir), file=out)
        return EXIT_DISC_STOP
    if trial.get("aborted"):
        print("ABORTED: %s\nNothing was measured; run directory kept (recorded as aborted): %s"
              % (trial["aborted"], run_dir), file=out)
        return EXIT_ABORTED
    print("Done: %s" % run_dir, file=out)
    return 0


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
                     out=sys.stdout, countdown_s: int = 5, sleep=asyncio.sleep,
                     guard: Optional[DiscGuard] = None, plate_phases: Optional[Sequence[str]] = None) -> None:
    """Run a timed protocol: before each phase print a countdown, then mark `<kind>` at "NOW" and print the
    instruction. The operator acts on "NOW" (human timing error of a few tenths of a second, not measured).
    With ``plate_phases``, ``guard`` needs the disc temperature only during those phases (missing-data rule)."""
    for kind, dur, text in phases:
        if stop.is_set():
            return
        print("\nNext: %s" % text, file=out)
        for k in range(countdown_s, 0, -1):
            if stop.is_set():
                return
            print("  %d ..." % k, file=out, flush=True)
            await sleep(1.0)
        if stop.is_set():
            return
        writer.mark(kind, text)
        if guard is not None and plate_phases is not None:
            guard.set_needs_plate(kind in plate_phases, writer.clock())
        print(">>> NOW: %s   (phase %s, %.0f s)" % (text, kind, dur), file=out, flush=True)
        t_end = time.monotonic() + dur
        while not stop.is_set():
            left = t_end - time.monotonic()
            if left <= 0:
                break
            await sleep(min(1.0, left))
    if stop.is_set():                    # stopped (disc guard / operator q) during the last phase: no "end" mark
        print("\nProtocol stopped before the end.", file=out, flush=True)
        return
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


def guard_trigger(writer: SessionWriter, guard: DiscGuard, stop: Optional[asyncio.Event] = None,
                  out=sys.stderr) -> None:
    """Once the guard has a stop reason: mark `disc_stop`, print the warning (stderr and stdout), set ``stop``."""
    if not guard.stop_reason or getattr(guard, "_reported", False):
        return
    guard._reported = True
    writer.mark("disc_stop", guard.stop_detail, stop_reason=guard.stop_reason, disc_c=guard.stop_c,
                disc_max_c=guard.disc_max_c, pi_t_mono_reading=guard.stop_pi_t)
    msg = "\a\n" + "!" * 78 + "\n" + guard.warning() + "\n" + "!" * 78
    print(msg, file=out, flush=True)
    if out is not sys.stdout:
        print(msg, flush=True)
    if stop is not None:
        stop.set()


async def _wait_or_stop(stop: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop.wait(), timeout=max(0.0, seconds))
    except asyncio.TimeoutError:
        pass


def record_run(url: str, run_dir, trial: dict, phases: Sequence[Phase], tail_s: float = 0.0,
               warmup_s: float = 3.0, interactive: bool = True, countdown_s: int = 5,
               no_data_timeout_s: float = 15.0, guard: Optional[DiscGuard] = None, needs_plate: bool = False,
               plate_phases: Optional[Sequence[str]] = None) -> Path:
    """Connect, wait `warmup_s` for data, run the timed phases, record `tail_s` more, close and write trial.json.
    Refuses to start the protocol if nothing arrives within 15 s of connecting (prints the reason).

    Every run is guarded (DiscGuard): disc >= 70 C stops it at once. The missing / faulted disc-temperature rule
    applies for the whole run when ``needs_plate``, or only during ``plate_phases`` when given. On a stop the
    protocol ends, nothing more is recorded after the tail of the current receive, and trial.json says why."""
    writer = SessionWriter(run_dir, {"session_extra": {"trial": trial.get("run_id")}})
    if guard is None:
        guard = DiscGuard(needs_plate=bool(needs_plate) and plate_phases is None)
    if plate_phases is not None:
        guard.needs_plate = False

    async def main():
        stop = asyncio.Event()

        def on_msg(msg: dict) -> None:
            if guard.on_message(msg, writer.clock()):
                guard_trigger(writer, guard, stop)

        async def watchdog():
            while not stop.is_set():
                if guard.check(writer.clock()):
                    guard_trigger(writer, guard, stop)
                    return
                await _wait_or_stop(stop, 0.2)

        rx = asyncio.create_task(run_ws(url, writer, stop, on_message=on_msg))
        tasks = [rx, asyncio.create_task(watchdog())]
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
            await _wait_or_stop(stop, warmup_s)
            await run_phases(writer, phases, stop, countdown_s=countdown_s, guard=guard, plate_phases=plate_phases)
            if tail_s > 0:
                await _wait_or_stop(stop, tail_s)
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
    guard.annotate(trial)
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
