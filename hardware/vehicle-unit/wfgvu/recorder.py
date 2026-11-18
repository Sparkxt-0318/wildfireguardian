"""Raw logging of everything the unit produces to ``records/<session_id>/`` (DESIGN.md section 4).

Files::

    session.json            written at start, rewritten at close (ended_utc, t_mono_first/last, counts, drops)
    <sensor>.jsonl.gz       one protocol message (reading or heartbeat) per line, the exact text sent
    events.jsonl.gz         events;  unit.jsonl.gz: server ("unit") heartbeats
    radar_uart.bin          raw data-UART bytes as read from the radar (live only)

Session directory: created exclusively. The Pi has no battery RTC and nothing disciplines its clock (no GNSS time,
usually no network), so two boots can produce the same wall-clock ``session_id``; an existing directory is never
reused: the recorder takes ``<id>-2``, ``<id>-3`` ... instead and exposes the id it really used as
``Recorder.session_id`` (``__main__`` puts it into the protocol context before anything is sent). Stream files are
opened with ``"xb"``: a file that already exists is never appended to (appending a gzip member after a power-cut
stream makes the whole file unreadable); the recorder reports ``record_error`` and continues in the next free part.
session.json records ``boot_id`` and the wall-clock source / sync state.

Rotation: when a file's compressed size passes ``rotate_bytes`` it is closed and ``<name>.<n>.jsonl.gz``
(``radar_uart.<n>.bin``) continues it; ``replay`` reads the parts in order (part numbers may have gaps after an
error). An ``on_event("record_rotated", ...)`` callback is made.

Durability: writes go through a bounded queue (``queue_max`` messages and ``queue_max_mb`` bytes) to one writer
thread, so a slow SD card never blocks a driver (if the queue is full the message is not recorded and ``dropped``
counts it). The writer flushes every gzip stream with ``Z_SYNC_FLUSH`` and fsyncs it every ``flush_s`` (default
1 s), so a power cut loses at most about that much; ``replay`` reads such a truncated file up to its last complete
line. session.json is written to a temporary file, fsynced, renamed, and the directory fsynced.

Errors: any exception while writing, flushing or rotating a stream closes that stream (counts kept), raises a
``record_error`` event (at most one per ``error_event_s``, with the number suppressed) and drops the message; the
stream is reopened in a NEW part at most once per ``flush_s``. The writer thread never exits on an error (a
last-resort guard sets ``failed``). ``stats()`` reports ``alive``, ``failed`` and ``paused``; the server's ``unit``
heartbeat turns ``error`` (``health()``) when the writer is dead or failed, recording is paused, or an error happened
within the last 10 s.

Disk space: free space under the records root is checked every ``disk_check_s``; below ``low_free_mb`` an
``on_event("disk_low", ...)`` is raised (repeated at most once a minute); below ``stop_free_mb`` recording pauses
(``record_paused``) so the OS card never fills up, and resumes (``record_resumed``) when space returns.
"""
from __future__ import annotations

import gzip
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import zlib
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional, Tuple

from . import __version__, protocol

EventFn = Callable[[str, str], None]
_STOP = object()
BOOT_ID_PATH = Path("/proc/sys/kernel/random/boot_id")
MAX_SESSION_SUFFIX = 999


def free_mb(path: Path) -> Optional[float]:
    """Free disk space at ``path`` in MB (1e6 bytes), or None if it cannot be read."""
    try:
        return shutil.disk_usage(str(path)).free / 1e6
    except OSError:
        return None


def boot_id() -> Optional[str]:
    """Linux kernel boot id (changes every boot), or None where it does not exist (laptop, simulator)."""
    try:
        v = BOOT_ID_PATH.read_text().strip()
        return v or None
    except OSError:
        return None


def clock_info() -> dict:
    """Where the wall clock (``t_utc``, ``started_utc``, ``session_id``) comes from and whether it is synchronised.

    The unit has no battery RTC and does not set its clock from GNSS. ``synchronized`` is "synchronized (NTP)" only
    when ``timedatectl`` confirms it (Linux), else "unsynchronized" (also when it cannot be checked)."""
    state = "unsynchronized"
    if sys.platform.startswith("linux"):
        try:
            out = subprocess.run(["timedatectl", "show", "-p", "NTPSynchronized", "--value"], capture_output=True,
                                 text=True, timeout=1.0)
            if out.returncode == 0 and out.stdout.strip() == "yes":
                state = "synchronized (NTP)"
        except (OSError, subprocess.SubprocessError):
            pass
    return {"source": "system wall clock (no RTC battery, no GNSS time discipline; may repeat or go backwards "
                      "across boots: order by session_id and t_mono)", "synchronized": state}


def _fsync_dir(d: Path) -> None:
    try:
        fd = os.open(str(d), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


class _Deferred(OSError):
    """Stream closed after an error and not yet due for a reopen: the message is dropped (counted, no event)."""


class _Sink:
    """One rotating output (gzip text or raw binary). Never appends to an existing file.

    ``ensure_open(now)`` opens the stream if it is closed: the first time at ``part``, after a close / error in the
    next part number, skipping (and listing in ``skipped``) files that already exist; after a failed attempt the
    next one waits ``retry_s``. ``write`` on a closed stream raises ``OSError``."""

    def __init__(self, directory: Path, name: str, binary: bool, rotate_bytes: int, retry_s: float = 1.0):
        self.directory, self.name, self.binary, self.rotate_bytes = directory, name, binary, rotate_bytes
        self.retry_s = float(retry_s)
        self.part = 0
        self.raw = None
        self.gz = None
        self.bytes_closed = 0
        self.lines = 0
        self.opened_once = False
        self.retry_at = -1e18
        self.skipped: list = []

    def path_for(self, part: int) -> Path:
        ext = ".bin" if self.binary else ".jsonl.gz"
        return self.directory / ("%s%s%s" % (self.name, "" if part == 0 else ".%d" % part, ext))

    @property
    def is_open(self) -> bool:
        return self.raw is not None

    def _open(self) -> None:
        raw = open(self.path_for(self.part), "xb")             # never "ab": see module docstring
        try:
            gz = None if self.binary else gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=1, mtime=0)
        except BaseException:
            raw.close()
            raise
        self.raw, self.gz = raw, gz

    def ensure_open(self, now: float) -> None:
        if self.raw is not None:
            return
        if now < self.retry_at:
            raise _Deferred("%s: closed after an error, reopen not yet due" % self.name)
        self.retry_at = now + self.retry_s
        if self.opened_once:
            self.part += 1
        for _ in range(1000):
            try:
                self._open()
            except FileExistsError:
                self.skipped.append(self.path_for(self.part).name)
                self.part += 1
                continue
            self.opened_once = True
            self.retry_at = -1e18
            return
        raise OSError("%s: no free part number" % self.name)

    def write(self, data: bytes) -> None:
        if self.raw is None:
            raise OSError("%s: stream not open" % self.name)
        if self.gz is not None:
            self.gz.write(data)
            self.lines += 1
        else:
            self.raw.write(data)

    def flush(self) -> None:
        if self.raw is None:
            return
        if self.gz is not None:
            self.gz.flush(zlib.Z_SYNC_FLUSH)
        self.raw.flush()
        try:
            os.fsync(self.raw.fileno())
        except OSError:
            pass

    def size(self) -> int:
        return self.raw.tell() if self.raw is not None else 0

    def close(self) -> None:
        """Close (gzip trailer, flush, fsync). The stream counts as closed even if this raises."""
        gz, raw = self.gz, self.raw
        self.gz = self.raw = None
        if raw is None:
            return
        try:
            if gz is not None:
                gz.close()
            raw.flush()
            try:
                os.fsync(raw.fileno())
            except OSError:
                pass
        finally:
            try:
                self.bytes_closed += raw.tell()
            except (OSError, ValueError):
                pass
            raw.close()

    def abandon(self, now: float) -> None:
        """Close after an error, ignoring further errors; reopen (in a new part) not before ``now + retry_s``."""
        try:
            self.close()
        except Exception:                                      # noqa: BLE001 - already failing
            pass
        self.retry_at = now + self.retry_s

    def rotate(self, now: float) -> Path:
        try:
            self.close()
        finally:
            self.retry_at = -1e18                              # reopen at once (next part), also after a failed close
        self.ensure_open(now)
        return self.path_for(self.part)


class Recorder:
    """Thread-safe raw recorder. ``write(msg, text)`` and ``write_raw(name, bytes)`` only enqueue.

    ``session_id`` is the id actually used (``<requested>``, or ``<requested>-<n>`` if that directory existed)."""

    def __init__(self, root, session_id: str, unit_id: str, sim: bool = False, config: Optional[dict] = None,
                 *, flush_s: float = 1.0, rotate_bytes: int = 256 * 1024 * 1024, queue_max: int = 20000,
                 queue_max_mb: float = 256.0, low_free_mb: float = 1000.0, stop_free_mb: float = 200.0,
                 disk_check_s: float = 5.0, error_event_s: float = 10.0, on_event: Optional[EventFn] = None,
                 free_mb_fn: Optional[Callable[[Path], Optional[float]]] = None, extra_info: Optional[dict] = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.requested_session_id = session_id
        self.session_id = self._make_dir(session_id)
        self.dir = self.root / self.session_id
        self.flush_s, self.rotate_bytes = float(flush_s), int(rotate_bytes)
        self.low_free_mb, self.stop_free_mb, self.disk_check_s = low_free_mb, stop_free_mb, disk_check_s
        self.error_event_s = float(error_event_s)
        self.on_event = on_event
        self.free_mb_fn = free_mb_fn or free_mb
        self.info: Dict[str, Any] = {
            "unit_id": unit_id, "session_id": self.session_id, "started_utc": protocol.utc_now_iso(),
            "sim": bool(sim), "config": protocol.sanitize(config or {}), "wfgvu_version": __version__,
            "protocol_version": protocol.PROTOCOL_VERSION, "ended_utc": None, "t_mono_first": None,
            "t_mono_last": None, "boot_id": boot_id(), "clock": clock_info(),
        }
        if self.session_id != session_id:
            self.info["session_id_requested"] = session_id
        if extra_info:
            self.info.update(protocol.sanitize(extra_info))
        self._write_info()
        self._q: "queue.Queue[Any]" = queue.Queue(maxsize=queue_max)
        self.queue_max_bytes = int(float(queue_max_mb) * 1e6)
        self._q_bytes = 0
        self._q_lock = threading.Lock()
        self._sinks: Dict[str, _Sink] = {}
        self.dropped = 0
        self.written = 0
        self.errors = 0
        self.paused = False
        self.failed = False
        self.fail_reason = ""
        self.disk_free_mb: Optional[float] = None
        self._last_low_event = -1e9
        self._last_err_event = -1e18
        self._last_err_mono = -1e18
        self.last_error = ""
        self._err_suppressed = 0
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="recorder", daemon=True)
        self._thread.start()

    def _make_dir(self, session_id: str) -> str:
        """Create ``root/<id>`` exclusively (``<id>-2``, ``<id>-3`` ... if taken). Returns the id used."""
        for n in range(1, MAX_SESSION_SUFFIX + 1):
            sid = session_id if n == 1 else "%s-%d" % (session_id, n)
            try:
                (self.root / sid).mkdir(exist_ok=False)
            except FileExistsError:
                continue
            _fsync_dir(self.root)
            return sid
        raise FileExistsError("session directories %s .. -%d all exist under %s"
                              % (session_id, MAX_SESSION_SUFFIX, self.root))

    # ------------------------------------------------------------------ producer side (any thread)
    def write(self, msg: dict, text: Optional[str] = None) -> bool:
        """Record one protocol message (``text`` = the exact wire text, else ``protocol.dumps(msg)``)."""
        mtype = msg.get("type")
        if mtype in ("reading", "heartbeat"):
            name = "unit" if msg.get("sensor") == "unit" else msg.get("sensor")
            if name not in protocol.HEARTBEAT_SENSORS:
                return False
        elif mtype == "event":
            name = "events"
        else:
            return False                                       # hello is per connection, not recorded
        if text is None:
            text = protocol.dumps(msg)
        return self._put((name, (text + "\n").encode("utf-8"), False, msg.get("t_mono")))

    def write_raw(self, name: str, data: bytes) -> bool:
        """Append raw bytes to ``<name>.bin`` (e.g. ``radar_uart``)."""
        return self._put((name, bytes(data), True, None))

    def _put(self, item: Tuple) -> bool:
        if self._closed:
            return False
        n = len(item[1])
        with self._q_lock:
            if self._q_bytes + n > self.queue_max_bytes:
                self.dropped += 1
                return False
            self._q_bytes += n
        try:
            self._q.put_nowait(item)
            return True
        except queue.Full:
            with self._q_lock:
                self._q_bytes -= n
            self.dropped += 1
            return False

    def _taken(self, item: Any) -> None:
        if isinstance(item, tuple):
            with self._q_lock:
                self._q_bytes -= len(item[1])

    @property
    def rec_bytes(self) -> int:
        """Bytes on disk so far (compressed), all files of this session."""
        total = 0
        for s in list(self._sinks.values()):
            try:
                total += s.bytes_closed + s.size()
            except (ValueError, OSError):
                total += s.bytes_closed
        return total

    @property
    def alive(self) -> bool:
        return self._thread.is_alive()

    def stats(self) -> dict:
        return {"written": self.written, "dropped": self.dropped, "paused": self.paused,
                "disk_free_mb": self.disk_free_mb, "rec_bytes": self.rec_bytes, "alive": self.alive,
                "failed": self.failed, "fail_reason": self.fail_reason, "errors": self.errors,
                "queue_bytes": self._q_bytes, "last_error": self.last_error}

    def health(self, recent_error_s: float = 10.0) -> Tuple[bool, str]:
        """(ok, detail) for the unit heartbeat: not ok when the writer is dead or failed, recording is paused, or a
        write/flush/rotation error happened within the last ``recent_error_s``."""
        if self._closed:
            return True, "recorder closed"
        if not self.alive:
            return False, "recorder dead"
        if self.failed:
            return False, "recorder dead: %s" % self.fail_reason[:120]
        if self.paused:
            return False, "recording paused"
        if time.monotonic() - self._last_err_mono < float(recent_error_s):
            return False, "record error: %s" % self.last_error[:120]
        return True, ""

    # ------------------------------------------------------------------ writer thread
    def _event(self, kind: str, detail: str) -> None:
        if self.on_event is not None:
            try:
                self.on_event(kind, detail)
            except Exception:                                  # noqa: BLE001 - never kill the writer
                pass

    def _error(self, where: str, exc: BaseException) -> None:
        """Count an error; ``record_error`` event at most once per ``error_event_s``."""
        self.errors += 1
        now = time.monotonic()
        self._last_err_mono = now
        self.last_error = "%s: %s: %s" % (where, type(exc).__name__, exc)
        if now - self._last_err_event >= self.error_event_s:
            extra = " (+%d earlier errors not reported)" % self._err_suppressed if self._err_suppressed else ""
            self._last_err_event = now
            self._err_suppressed = 0
            self._event("record_error", "%s: %s: %s%s" % (where, type(exc).__name__, exc, extra))
        else:
            self._err_suppressed += 1

    def _check_disk(self) -> None:
        mb = self.free_mb_fn(self.root)
        self.disk_free_mb = mb
        if mb is None:
            return
        now = time.monotonic()
        if mb < self.stop_free_mb and not self.paused:
            self.paused = True
            self._event("record_paused", "free %.0f MB < %.0f MB: recording paused" % (mb, self.stop_free_mb))
        elif mb >= self.stop_free_mb and self.paused:
            self.paused = False
            self._event("record_resumed", "free %.0f MB" % mb)
        if mb < self.low_free_mb and now - self._last_low_event >= 60.0:
            self._last_low_event = now
            self._event("disk_low", "free %.0f MB < %.0f MB" % (mb, self.low_free_mb))

    def _sink(self, name: str, binary: bool) -> _Sink:
        s = self._sinks.get(name)
        if s is None:
            s = self._sinks[name] = _Sink(self.dir, name, binary, self.rotate_bytes, retry_s=self.flush_s)
        return s

    def _report_skipped(self, s: _Sink) -> None:
        if s.skipped:
            skipped, s.skipped = s.skipped, []
            self._error(s.name, FileExistsError("existing file(s) %s not appended to; continuing in %s"
                                                % (", ".join(skipped), s.path_for(s.part).name)))

    def _write_item(self, item: Tuple) -> None:
        name, data, binary, t_mono = item
        if self.paused:
            self.dropped += 1
            return
        s = self._sink(name, binary)
        now = time.monotonic()
        try:
            s.ensure_open(now)
            self._report_skipped(s)
            s.write(data)
        except _Deferred:
            self.dropped += 1
            return
        except Exception as exc:                               # noqa: BLE001 - any error: drop, close, report
            self.dropped += 1
            s.abandon(now)
            self._report_skipped(s)
            self._error(name, exc)
            return
        self.written += 1
        if t_mono is not None:
            if self.info["t_mono_first"] is None:
                self.info["t_mono_first"] = t_mono
            self.info["t_mono_last"] = t_mono

    def _flush_all(self) -> None:
        now = time.monotonic()
        for name, s in list(self._sinks.items()):
            if not s.is_open:
                continue
            try:
                s.flush()
                if s.size() >= self.rotate_bytes:
                    new = s.rotate(now)
                    self._report_skipped(s)
                    self._event("record_rotated", "%s -> %s" % (name, new.name))
            except Exception as exc:                           # noqa: BLE001 - one bad sink must not stop the rest
                s.abandon(now)
                self._report_skipped(s)
                self._error("flush %s" % name, exc)

    def _run(self) -> None:
        last_flush = time.monotonic()
        last_disk = -1e9
        while True:
            try:
                now = time.monotonic()
                if now - last_disk >= self.disk_check_s:
                    last_disk = now
                    try:
                        self._check_disk()
                    except Exception as exc:                   # noqa: BLE001 - a bad disk probe is not fatal
                        self._error("disk check", exc)
                try:
                    item = self._q.get(timeout=min(0.1, self.flush_s))
                except queue.Empty:
                    item = None
                self._taken(item)
                if item is _STOP:
                    break
                if item is not None:
                    self._write_item(item)
                if time.monotonic() - last_flush >= self.flush_s:
                    last_flush = time.monotonic()
                    self._flush_all()
            except Exception as exc:                           # noqa: BLE001 - last-resort guard: never exit
                self.failed = True
                self.fail_reason = "%s: %s" % (type(exc).__name__, exc)
                self._error("writer", exc)
                time.sleep(0.05)
        for name, s in list(self._sinks.items()):
            try:
                s.close()
            except Exception as exc:                           # noqa: BLE001
                self._error("close %s" % name, exc)

    def _write_info(self) -> None:
        """session.json via a temporary file: write, fsync, rename, fsync the directory (power-cut safe)."""
        tmp = self.dir / "session.json.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(self.info, indent=1, sort_keys=True))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.dir / "session.json")
        _fsync_dir(self.dir)

    def close(self, timeout: float = 10.0) -> None:
        """Stop accepting, write everything queued, close files, finalise session.json.

        Bounded by ``timeout``: if the queue stays full, what is queued is discarded (counted as dropped) to let
        the stop marker in. If the writer has not finished in time, session.json says so (``closed_cleanly`` false,
        ``writer_alive`` true, ``queue_left``) and its counts are only what was written by then."""
        if self._closed:
            return
        self._closed = True
        t_end = time.monotonic() + max(0.0, float(timeout))
        try:
            self._q.put(_STOP, timeout=max(0.05, min(1.0, timeout / 2.0)))
        except queue.Full:
            while True:
                try:
                    item = self._q.get_nowait()
                except queue.Empty:
                    break
                self._taken(item)
                if item is not _STOP:
                    self.dropped += 1
            try:
                self._q.put_nowait(_STOP)
            except queue.Full:                                 # pragma: no cover - nothing else puts after _closed
                pass
        self._thread.join(max(0.0, t_end - time.monotonic()))
        alive = self._thread.is_alive()
        sinks = list(self._sinks.items())
        self.info["ended_utc"] = protocol.utc_now_iso()
        self.info["counts"] = {n: s.lines for n, s in sinks if not s.binary}
        self.info["dropped"] = self.dropped
        self.info["record_errors"] = self.errors
        self.info["closed_cleanly"] = (not alive) and not self.failed
        self.info["writer_alive"] = alive
        if alive:
            self.info["queue_left"] = self._q.qsize()
        if self.failed:
            self.info["writer_failed"] = self.fail_reason
        try:
            self.info["files"] = sorted(p.name for p in self.dir.iterdir()
                                        if p.name not in ("session.json", "session.json.tmp"))
            self._write_info()
        except OSError as exc:
            self._error("session.json", exc)

    def __enter__(self) -> "Recorder":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def write_session(session_dir, info: dict, messages: Iterable[dict], raw: Optional[Dict[str, bytes]] = None) -> Path:
    """Write a complete session directory synchronously (for ``wfgvu.synth`` and tests).

    ``info`` goes to session.json (must contain ``unit_id`` and ``session_id``; ``sim`` defaults to True since
    anything written this way is not a live recording). ``messages`` are protocol dicts (validated); each lands in
    the file ``Recorder.write`` would use. ``t_mono_first``/``t_mono_last`` are filled in. Returns the directory.
    """
    d = Path(session_dir)
    d.mkdir(parents=True, exist_ok=True)
    files: Dict[str, gzip.GzipFile] = {}
    meta = {"sim": True, "started_utc": protocol.utc_now_iso(), "ended_utc": protocol.utc_now_iso(),
            "wfgvu_version": __version__, "protocol_version": protocol.PROTOCOL_VERSION}
    meta.update(info)
    t_first = t_last = None
    counts: Dict[str, int] = {}
    try:
        for msg in messages:
            protocol.validate(msg)
            mtype = msg["type"]
            if mtype in ("reading", "heartbeat"):
                name = msg["sensor"]
            elif mtype == "event":
                name = "events"
            else:
                continue
            fh = files.get(name)
            if fh is None:
                fh = files[name] = gzip.GzipFile(str(d / ("%s.jsonl.gz" % name)), mode="wb", compresslevel=6,
                                                 mtime=0)
            fh.write((protocol.dumps(msg) + "\n").encode("utf-8"))
            counts[name] = counts.get(name, 0) + 1
            t = float(msg["t_mono"])
            t_first = t if t_first is None else min(t_first, t)
            t_last = t if t_last is None else max(t_last, t)
    finally:
        for fh in files.values():
            fh.close()
    for name, data in (raw or {}).items():
        (d / ("%s.bin" % name)).write_bytes(data)
    meta.setdefault("t_mono_first", t_first)
    meta.setdefault("t_mono_last", t_last)
    meta.setdefault("counts", counts)
    (d / "session.json").write_text(json.dumps(protocol.sanitize(meta), indent=1, sort_keys=True))
    return d
