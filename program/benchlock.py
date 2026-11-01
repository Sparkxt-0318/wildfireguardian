#!/usr/bin/env python3
"""Shared benchmark lock: timed runs must not overlap other heavy computation.

CLI:     python program/benchlock.py [--label NAME] [--wait-max SECONDS] -- <command> [args...]
         python program/benchlock.py --status
Python:  load this file by path and use ``with bench_lock("label"):``

``--wait-max SECONDS`` bounds the wait: if the lock is still busy after that long, exit 75
without starting the command (``bench_lock(..., wait_max=...)`` raises ``LockTimeout``). A
command that has started is never stopped. Use it for jobs run under a hard time limit (for
example a background runner), so that a long queue makes the job give up before it starts
instead of being killed in the middle of a timed run.

The lock file is ``program/.bench.lock`` in the MAIN checkout (found through
``git rev-parse --git-common-dir``), so every worktree of this repo shares one queue.
Uses ``fcntl.flock``, which works on macOS and Linux (stock macOS has no ``flock`` command).
Set ``WFG_BENCH_LOCK=/path/to/file`` to override the location.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import os
import socket
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

EXIT_NOT_ACQUIRED = 75  # EX_TEMPFAIL: the lock stayed busy for the whole --wait-max; nothing ran


class LockTimeout(TimeoutError):
    """The lock stayed busy for the whole ``wait_max``; the caller's work did not start."""


def lock_path() -> Path:
    env = os.environ.get("WFG_BENCH_LOCK")
    if env:
        path = Path(env)
    else:
        here = Path(__file__).resolve().parent
        root = here.parent
        try:
            out = subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                cwd=here, capture_output=True, text=True, check=True,
            ).stdout.strip()
            common = Path(out)
            if not common.is_absolute():
                common = (here / common).resolve()
            root = common.parent
        except (OSError, subprocess.CalledProcessError):
            pass
        path = root / "program" / ".bench.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def holder() -> str:
    """Return the current holder's label, or '' if the lock is free."""
    path = lock_path()
    with open(path, "a+") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fh.seek(0)
            return fh.read().strip() or "unknown"
        fcntl.flock(fh, fcntl.LOCK_UN)
        return ""


def _acquire(fh, wait_max: float | None, busy_label: str) -> None:
    """Block until ``fh`` holds the lock. With ``wait_max`` (seconds), raise ``LockTimeout`` instead
    of waiting longer. The blocking wait queues like any other waiter; an alarm ends it."""
    if wait_max is None:
        fcntl.flock(fh, fcntl.LOCK_EX)
        return
    message = f"bench lock still held after {wait_max:g} s (held by: {busy_label})"
    if threading.current_thread() is threading.main_thread():
        def expire(signum, frame):
            raise LockTimeout(message)

        previous = signal.signal(signal.SIGALRM, expire)
        signal.setitimer(signal.ITIMER_REAL, max(wait_max, 1e-3))
        try:
            fcntl.flock(fh, fcntl.LOCK_EX)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
        return
    deadline = time.monotonic() + wait_max  # signals reach only the main thread: poll instead
    while True:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise LockTimeout(message) from None
            time.sleep(0.2)


@contextlib.contextmanager
def bench_lock(label: str = "bench", wait_max: float | None = None):
    """Hold the shared benchmark lock; yields the seconds spent waiting for it. With ``wait_max``
    (seconds), raise ``LockTimeout`` rather than wait longer; the ``with`` body then never runs."""
    path = lock_path()
    with open(path, "a+") as fh:
        t0 = time.monotonic()
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fh.seek(0)
            busy = fh.read().strip() or "unknown"
            limit = "" if wait_max is None else f", at most {wait_max:g} s"
            print(f"[benchlock] waiting for {path} (held by: {busy}{limit})", file=sys.stderr, flush=True)
            _acquire(fh, wait_max, busy)
        waited = time.monotonic() - t0
        fh.seek(0)
        fh.truncate()
        fh.write(f"{label} pid={os.getpid()} host={socket.gethostname()} "
                 f"since={time.strftime('%Y-%m-%dT%H:%M:%S%z')}\n")
        fh.flush()
        try:
            yield waited
        finally:
            fh.seek(0)
            fh.truncate()
            fh.flush()
            fcntl.flock(fh, fcntl.LOCK_UN)


def main(argv: list[str]) -> int:
    if "--" in argv:
        i = argv.index("--")
        opts, cmd = argv[:i], argv[i + 1:]
    else:
        opts, cmd = argv, []
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--label", default=None)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--wait-max", type=float, default=None, metavar="SECONDS",
                    help=f"give up (exit {EXIT_NOT_ACQUIRED}, command not started) if the lock is still busy "
                         "after SECONDS; a started command is never stopped")
    a = ap.parse_args(opts)
    if a.status:
        print(holder() or "free")
        return 0
    if not cmd:
        ap.error("give a command after --")
    try:
        with bench_lock(a.label or " ".join(cmd)[:160], wait_max=a.wait_max) as waited:
            print(f"[benchlock] acquired after {waited:.1f}s: {' '.join(cmd)}", file=sys.stderr, flush=True)
            return subprocess.call(cmd)
    except LockTimeout as exc:
        print(f"[benchlock] not acquired: {exc}; command not started: {' '.join(cmd)}",
              file=sys.stderr, flush=True)
        return EXIT_NOT_ACQUIRED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
