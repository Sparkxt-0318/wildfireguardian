#!/usr/bin/env python3
"""Shared benchmark lock: timed runs must not overlap other heavy computation.

CLI:     python program/benchlock.py [--label NAME] -- <command> [args...]
         python program/benchlock.py --status
Python:  load this file by path and use ``with bench_lock("label"):``

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
import subprocess
import sys
import time
from pathlib import Path


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


@contextlib.contextmanager
def bench_lock(label: str = "bench"):
    """Hold the shared benchmark lock; yields the seconds spent waiting for it."""
    path = lock_path()
    with open(path, "a+") as fh:
        t0 = time.monotonic()
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            fh.seek(0)
            print(f"[benchlock] waiting for {path} (held by: {fh.read().strip() or 'unknown'})",
                  file=sys.stderr, flush=True)
            fcntl.flock(fh, fcntl.LOCK_EX)
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
    a = ap.parse_args(opts)
    if a.status:
        print(holder() or "free")
        return 0
    if not cmd:
        ap.error("give a command after --")
    with bench_lock(a.label or " ".join(cmd)[:160]) as waited:
        print(f"[benchlock] acquired after {waited:.1f}s: {' '.join(cmd)}", file=sys.stderr, flush=True)
        return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
