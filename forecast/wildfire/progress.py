"""Small terminal progress displays with no dependency or random-state access.

Known work uses :class:`ProgressBar`; opaque native work uses :class:`Activity`
and therefore never receives a manufactured completion percentage. Displays go
to stderr by default. Redirected output receives sparse ordinary lines instead
of terminal control sequences.
"""
from __future__ import annotations

from numbers import Integral
import sys
import threading
import time


_OUTPUT_LOCK = threading.RLock()
_LINES = {}


def _integer(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer excluding booleans")
    return int(value)


def _duration(seconds):
    seconds = max(0, int(seconds))
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class _Display:
    def __init__(self, description, *, enabled=True, stream=None, min_interval=None):
        self.description = str(description)
        self.enabled = bool(enabled)
        self.stream = sys.stderr if stream is None else stream
        try:
            self._tty = bool(self.stream.isatty())
        except (AttributeError, OSError, ValueError):
            self._tty = False
        interval = (.2 if self._tty else 10.) if min_interval is None else float(min_interval)
        if not 0 <= interval < float("inf"):
            raise ValueError("min_interval must be finite and nonnegative")
        self.min_interval = interval
        self._started = time.monotonic()
        self._last_render = None
        self._closed = False
        self._status = "running"

    def _write(self, text):
        try:
            self.stream.write(text)
            self.stream.flush()
        except (OSError, ValueError):
            # An unavailable display must not invalidate model results.
            self.enabled = False
            if _LINES.get(id(self.stream), (None, 0))[0] is self:
                _LINES.pop(id(self.stream), None)

    def _render(self, *, force=False, final=False):
        with _OUTPUT_LOCK:
            if not self.enabled or (self._closed and not final):
                return
            now = time.monotonic()
            if (not force and self._last_render is not None
                    and now - self._last_render < self.min_interval):
                return
            line = self._line(max(0., now - self._started))
            if self._tty:
                key = id(self.stream)
                owner, width = _LINES.get(key, (None, 0))
                if owner is not None and owner is not self:
                    self._write("\n")
                    width = 0
                self._write("\r" + line + " " * max(0, width - len(line)))
                if final:
                    self._write("\n")
                    _LINES.pop(key, None)
                else:
                    if self.enabled:
                        _LINES[key] = (self, len(line))
            else:
                self._write(line + "\n")
            self._last_render = now

    def set_description(self, description):
        with _OUTPUT_LOCK:
            self.description = str(description)
            self._render(force=True)

    def write(self, message):
        """Write an ordinary status line without overwriting an active bar."""
        with _OUTPUT_LOCK:
            if not self.enabled:
                return
            if self._tty:
                key = id(self.stream)
                owner, width = _LINES.pop(key, (None, 0))
                if owner is not None:
                    self._write("\r" + " " * width + "\r")
            self._write(str(message).rstrip("\n") + "\n")
            self._render(force=True)

    def close(self, status="complete"):
        with _OUTPUT_LOCK:
            if self._closed:
                return
            self._status = str(status)
            self._closed = True
            self._render(force=True, final=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        status = "complete" if exc_type is None else "interrupted" if issubclass(exc_type, KeyboardInterrupt) else "failed"
        self.close(status)
        return False


class ProgressBar(_Display):
    """Display completed work out of a known total, with elapsed time and ETA.

    ``advance(amount)`` increments work; ``update(completed)`` sets its absolute
    completed count. Neither closing nor catching an exception changes counts.
    Percentages count work units and are not model-success probabilities or a
    guarantee that the same fraction of wall time has elapsed.
    """
    def __init__(self, total, description="", *, enabled=True, stream=None, min_interval=None):
        self.total = _integer(total, "total")
        self.completed = 0
        super().__init__(description, enabled=enabled, stream=stream, min_interval=min_interval)
        self._render(force=True)

    def _line(self, elapsed):
        fraction = self.completed / self.total if self.total else 1.
        filled = int(20 * fraction)
        bar = "#" * filled + "-" * (20 - filled)
        eta = _duration(elapsed * (self.total - self.completed) / self.completed) if self.completed else "--:--:--"
        if self.completed == self.total:
            eta = "00:00:00"
        return (f"{self.description} [{bar}] {self.completed}/{self.total} ({100 * fraction:.1f}%) "
                f"elapsed {_duration(elapsed)} ETA {eta} [{self._status}]").lstrip()

    def update(self, completed=None, *, description=None):
        """Set the absolute count, optionally changing the label."""
        with _OUTPUT_LOCK:
            if self._closed:
                return
            if completed is not None:
                completed = _integer(completed, "completed")
                if completed > self.total:
                    raise ValueError("completed must not exceed total")
                self.completed = completed
            if description is not None:
                self.description = str(description)
            self._render(force=self.completed == self.total)

    def advance(self, amount=1):
        with _OUTPUT_LOCK:
            self.update(self.completed + _integer(amount, "amount"))


class Activity(_Display):
    """Show elapsed time for opaque work without an estimated percentage.

    Entering its context starts a daemon heartbeat thread. Exiting or closing
    stops and joins that thread, including when the enclosed operation fails.
    The operation itself remains in the caller's thread and keeps its existing
    timeout and cancellation behavior.
    """
    def __init__(self, description="", *, enabled=True, stream=None, min_interval=None):
        self._frame = 0
        self._stop = threading.Event()
        self._thread = None
        super().__init__(description, enabled=enabled, stream=stream, min_interval=min_interval)
        self._render(force=True)

    def _line(self, elapsed):
        marker = "|/-\\"[self._frame % 4] if self._tty and self._status == "running" else self._status
        self._frame += 1
        return f"{self.description} [{marker}] elapsed {_duration(elapsed)}".lstrip()

    def _heartbeat(self):
        while not self._stop.wait(max(.05, self.min_interval)):
            self._render()

    def __enter__(self):
        with _OUTPUT_LOCK:
            if self.enabled and not self._closed and self._thread is None:
                self._thread = threading.Thread(target=self._heartbeat, name="wildfire-progress", daemon=True)
                self._thread.start()
        return self

    def close(self, status="complete"):
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join()
        super().close(status)
