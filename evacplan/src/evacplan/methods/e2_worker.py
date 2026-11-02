"""E2's persistent HiGHS worker: one child process per solve of ``e2_colgen`` that keeps the restricted master LP and
the integer master MIP in memory, so that adding columns and re-solving is a warm-started simplex call (milliseconds)
instead of a new process per LP.

Why a child process: the OR-Tools wheel (B2) bundles an ABI-incompatible ``libhighs.so.1`` (HiGHS 1.11 vs ``highspy``
1.15; the loader keeps whichever is loaded first), and in the interleaved final run B2 runs in the same process as
E2. The parent never imports ``highspy`` (as :mod:`evacplan.methods.highs_worker` and
:mod:`evacplan.methods.lp_worker`). The child runs this file (``python -I e2_worker.py``; only numpy and highspy are
imported there) and talks over its stdin/stdout: each message is an 8-byte length and a pickle of plain Python
values and numpy arrays. HiGHS runs single-threaded, and the parent blocks while it runs (no parallel work).

Every call has a timeout: if the child does not answer in time it is killed and :class:`WorkerError` is raised, so
a solve never outlives the method's deadline by more than the grace given to that call.
"""
from __future__ import annotations

import os
import pickle
import select
import struct
import subprocess
import sys
import time
from pathlib import Path

WORKER = Path(__file__).resolve()
_HEADER = struct.Struct("<Q")


class WorkerError(RuntimeError):
    """The worker failed, timed out or is gone (it has been killed)."""


# --------------------------------------------------------------------------------------------- parent side
class HighsWorker:
    """Client of one worker process (see the module docstring). Use as a context manager or call :meth:`close`."""

    def __init__(self, *, start_timeout: float = 20.0):
        env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
        self.proc = subprocess.Popen([sys.executable, "-I", str(WORKER)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, bufsize=0)
        self.calls = 0
        self.busy_s = 0.0
        self.call("ping", timeout=start_timeout)

    def __enter__(self) -> "HighsWorker":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def _kill(self) -> None:
        if self.proc is not None:
            try:
                self.proc.kill()
                self.proc.wait(timeout=5)
            except Exception:  # pragma: no cover - best effort
                pass

    def _read(self, n: int, end: float) -> bytes:
        fd = self.proc.stdout.fileno()
        buf = bytearray()
        while len(buf) < n:
            left = end - time.monotonic()
            if left <= 0:
                raise TimeoutError
            ready, _, _ = select.select([fd], [], [], left)
            if not ready:
                raise TimeoutError
            chunk = os.read(fd, n - len(buf))
            if not chunk:
                raise EOFError
            buf += chunk
        return bytes(buf)

    def call(self, cmd: str, *, timeout: float, **payload):
        """Send ``cmd`` with ``payload`` and wait at most ``timeout`` seconds for the answer (a dict)."""
        if not self.alive:
            raise WorkerError("the worker is not running")
        t0 = time.monotonic()
        data = pickle.dumps((cmd, payload), protocol=pickle.HIGHEST_PROTOCOL)
        try:
            self.proc.stdin.write(_HEADER.pack(len(data)) + data)
            self.proc.stdin.flush()
            end = t0 + max(0.05, float(timeout))
            (n,) = _HEADER.unpack(self._read(_HEADER.size, end))
            out = pickle.loads(self._read(n, end))
        except (TimeoutError, EOFError, BrokenPipeError, OSError) as exc:
            self._kill()
            raise WorkerError(f"worker call {cmd!r} failed: {type(exc).__name__}") from exc
        finally:
            self.calls += 1
            self.busy_s += time.monotonic() - t0
        if isinstance(out, dict) and out.get("error"):
            raise WorkerError(f"worker call {cmd!r}: {out['error']}")
        return out

    def close(self) -> None:
        if self.alive:
            try:
                self.call("quit", timeout=2.0)
            except WorkerError:
                pass
        self._kill()
        self.proc = None


# ---------------------------------------------------------------------------------------------- child side
def _serve() -> int:  # pragma: no cover - exercised through HighsWorker
    import numpy as np
    import highspy

    proto_in = sys.stdin.buffer
    proto_out = os.fdopen(os.dup(1), "wb", buffering=0)
    os.dup2(2, 1)                                   # anything HiGHS prints goes to stderr, never into the protocol
    inf = highspy.kHighsInf
    models: dict[str, highspy.Highs] = {}

    def new_model(threads: int, seed: int) -> "highspy.Highs":
        h = highspy.Highs()
        h.setOptionValue("output_flag", False)
        h.setOptionValue("threads", int(threads))
        h.setOptionValue("random_seed", int(seed) % (2 ** 31))
        h.changeObjectiveSense(highspy.ObjSense.kMaximize)
        return h

    def fin(a):
        a = np.asarray(a, dtype=np.float64)
        return np.where(np.isposinf(a), inf, np.where(np.isneginf(a), -inf, a))

    def reply(obj) -> None:
        data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
        proto_out.write(_HEADER.pack(len(data)) + data)

    while True:
        head = proto_in.read(_HEADER.size)
        if len(head) < _HEADER.size:
            return 0
        (n,) = _HEADER.unpack(head)
        cmd, kw = pickle.loads(proto_in.read(n))
        try:
            if cmd == "ping":
                reply({"ok": True, "highs_version": highspy.Highs().version()})
            elif cmd == "quit":
                reply({"ok": True})
                return 0
            elif cmd == "init":
                lo, hi = fin(kw["row_lower"]), fin(kw["row_upper"])
                for name in ("lp", "mip"):
                    h = new_model(kw.get("threads", 1), kw.get("seed", 0))
                    h.addRows(len(lo), lo, hi, 0, np.zeros(len(lo), dtype=np.int32), np.zeros(0, dtype=np.int32),
                              np.zeros(0))
                    models[name] = h
                reply({"ok": True})
            elif cmd == "add_cols":
                h = models[kw["model"]]
                first = h.getNumCol()
                cost = np.asarray(kw["cost"], dtype=np.float64)
                start = np.asarray(kw["start"], dtype=np.int32)
                index = np.asarray(kw["index"], dtype=np.int32)
                value = np.asarray(kw["value"], dtype=np.float64)
                h.addCols(len(cost), cost, fin(kw["lower"]), fin(kw["upper"]), len(value), start, index, value)
                if kw.get("integer"):
                    idx = np.arange(first, first + len(cost), dtype=np.int32)
                    h.changeColsIntegrality(len(idx), idx, np.full(len(idx), 1, dtype=np.uint8))
                reply({"ok": True, "first": first, "num_col": h.getNumCol()})
            elif cmd == "set_bounds":
                h = models[kw["model"]]
                idx = np.asarray(kw["index"], dtype=np.int32)
                h.changeColsBounds(len(idx), idx, fin(kw["lower"]), fin(kw["upper"]))
                reply({"ok": True})
            elif cmd == "solve":
                h = models[kw["model"]]
                h.setOptionValue("time_limit", max(0.05, float(kw["time_limit"])))
                for k, v in (kw.get("options") or {}).items():
                    h.setOptionValue(k, v)
                if kw.get("start") is not None:
                    sol = highspy.HighsSolution()
                    sol.col_value = list(map(float, kw["start"]))
                    sol.value_valid = True
                    h.setSolution(sol)
                t0 = time.monotonic()
                h.run()
                solve_s = time.monotonic() - t0
                info = h.getInfo()
                status = h.modelStatusToString(h.getModelStatus())
                sol = h.getSolution()
                out = {"status": status, "solve_s": solve_s, "num_col": h.getNumCol(),
                       "simplex_iterations": int(info.simplex_iteration_count)}
                if kw["model"] == "mip":
                    has = int(info.primal_solution_status) == 2
                    out["x"] = np.asarray(sol.col_value, dtype=np.float64) if has else None
                    out["objective"] = float(info.objective_function_value) if has else None
                    out["mip_dual_bound"] = float(info.mip_dual_bound)
                    out["mip_gap"] = float(info.mip_gap) if has else None
                    out["nodes"] = int(info.mip_node_count)
                else:
                    out["x"] = np.asarray(sol.col_value, dtype=np.float64) if sol.value_valid else None
                    out["row_dual"] = np.asarray(sol.row_dual, dtype=np.float64) if sol.dual_valid else None
                    out["objective"] = float(info.objective_function_value) if sol.value_valid else None
                reply(out)
            else:
                reply({"error": f"unknown command {cmd!r}"})
        except Exception as exc:  # noqa: BLE001 - reported to the parent, which decides
            reply({"error": f"{type(exc).__name__}: {exc}"})


if __name__ == "__main__":  # pragma: no cover - the child process
    sys.exit(_serve())
