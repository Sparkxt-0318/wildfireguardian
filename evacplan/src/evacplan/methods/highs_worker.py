"""Solve one MIP with HiGHS (``highspy``) in a child process.

Why a child process: the OR-Tools wheel (B2) bundles its own ``libhighs.so.1`` (HiGHS 1.11 in OR-Tools
9.14) and ``highspy`` ships another one under the same soname (HiGHS 1.15 here). The dynamic loader
keeps whichever is loaded first, so importing both in one process fails (missing symbols). B3 therefore
never imports ``highspy`` itself: :func:`solve_mip` writes the model to a temporary ``.npz``, runs this
file as a script (``python -I highs_worker.py IN OUT``; only numpy and highspy are imported there) and
reads the result back. The child's start-up time counts in the method's wall clock.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

WORKER = Path(__file__).resolve()


@dataclass
class MipResult:
    status: str                         # HiGHS model status, or "worker failed: ..." / "worker timeout"
    has_solution: bool
    x: np.ndarray | None
    objective: float | None             # of the incumbent (maximized)
    dual_bound: float | None            # HiGHS mip_dual_bound: an upper bound on the optimum (maximization)
    gap: float | None
    nodes: int | None
    solve_s: float                      # HiGHS run time in the child
    wall_s: float                       # including the child's start-up and I/O
    info: dict = field(default_factory=dict)


def solve_mip(model, *, time_limit: float, threads: int = 1, seed: int = 0, mip_rel_gap: float = 0.0,
              mip_abs_gap: float = 0.999, heuristic_effort: float | None = None, lp_bound_first: bool = False,
              start: np.ndarray | None = None, grace_s: float = 20.0) -> MipResult:
    """Solve a :class:`~evacplan.methods.timexp.MipModel` (maximize) in a child process within ``time_limit``
    seconds of HiGHS time; the child is killed ``grace_s`` later if it hangs. ``mip_abs_gap`` 0.999 stops at
    a proven optimum of an integer-valued objective. ``lp_bound_first``: first solve the LP relaxation with
    the interior-point method (much faster than simplex on these models) and report its optimum as
    ``info["lp_bound"]``, a bound that holds even if the MIP's root does not finish."""
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="evacplan-highs-") as tmp:
        inp, out = Path(tmp) / "model.npz", Path(tmp) / "result.npz"
        arrays = model.arrays()
        opts = {"time_limit": max(0.05, float(time_limit)), "threads": int(threads), "random_seed": int(seed) % (2**31),
                "mip_rel_gap": float(mip_rel_gap), "mip_abs_gap": float(mip_abs_gap), "lp_bound_first": bool(lp_bound_first)}
        if heuristic_effort is not None:
            opts["mip_heuristic_effort"] = float(heuristic_effort)
        extra = {"start": np.asarray(start, dtype=float)} if start is not None else {}
        np.savez(inp, **arrays, **extra, options=np.frombuffer(json.dumps(opts).encode(), dtype=np.uint8))
        try:
            proc = subprocess.run([sys.executable, "-I", str(WORKER), str(inp), str(out)], capture_output=True,
                                  text=True, timeout=opts["time_limit"] + grace_s,
                                  env={k: v for k, v in os.environ.items() if not k.startswith("PYTHON")})
        except subprocess.TimeoutExpired:
            return MipResult("worker timeout", False, None, None, None, None, None, math.nan, time.monotonic() - t0)
        if proc.returncode != 0 or not out.is_file():
            msg = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["no output"]
            return MipResult(f"worker failed: {msg[0][:200]}", False, None, None, None, None, None, math.nan,
                             time.monotonic() - t0)
        with np.load(out) as r:
            info = json.loads(bytes(r["info"]).decode())
            x = np.array(r["x"]) if info["has_solution"] else None
    return MipResult(info["status"], bool(info["has_solution"]), x, info["objective"], info["dual_bound"], info["gap"],
                     info["nodes"], float(info["solve_s"]), time.monotonic() - t0, info)


def _finite(v) -> float | None:
    v = float(v)
    return v if math.isfinite(v) else None


def main(argv: list[str]) -> int:      # runs in the child process
    import highspy

    inp, out = argv[1], argv[2]
    with np.load(inp) as d:
        a = {k: np.array(d[k]) for k in d.files}
    opts = json.loads(bytes(a.pop("options")).decode())
    lp_first = bool(opts.pop("lp_bound_first", False))
    t_all = time.monotonic()
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    lp = highspy.HighsLp()
    lp.num_col_ = int(a["cost"].size)
    lp.num_row_ = int(a["row_lower"].size)
    lp.col_cost_ = a["cost"]
    lp.col_lower_ = a["lower"]
    lp.col_upper_ = a["upper"]
    lp.row_lower_ = np.where(np.isinf(a["row_lower"]), -highspy.kHighsInf, a["row_lower"])
    lp.row_upper_ = np.where(np.isinf(a["row_upper"]), highspy.kHighsInf, a["row_upper"])
    lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
    lp.a_matrix_.start_ = a["a_start"].astype(np.int32)
    lp.a_matrix_.index_ = a["a_index"].astype(np.int32)
    lp.a_matrix_.value_ = a["a_value"]
    lp.sense_ = highspy.ObjSense.kMaximize
    lp_bound, lp_s = None, 0.0
    if lp_first:                                   # the LP relaxation by interior point: a bound in any case
        lp.integrality_ = [highspy.HighsVarType.kContinuous] * lp.num_col_
        h.passModel(lp)
        h.setOptionValue("solver", "ipm")
        h.setOptionValue("threads", int(opts.get("threads", 1)))
        h.setOptionValue("time_limit", max(0.05, 0.5 * float(opts["time_limit"])))
        h.run()
        lp_s = time.monotonic() - t_all
        if h.modelStatusToString(h.getModelStatus()) == "Optimal":
            lp_bound = _finite(h.getInfo().objective_function_value)
        h.clearModel()
        h.setOptionValue("solver", "choose")
        opts["time_limit"] = max(0.05, float(opts["time_limit"]) - lp_s)
    lp.integrality_ = [highspy.HighsVarType.kInteger if b else highspy.HighsVarType.kContinuous for b in a["integer"]]
    h.passModel(lp)
    for k, v in opts.items():
        h.setOptionValue(k, v)
    if "start" in a:
        sol = highspy.HighsSolution()
        sol.col_value = list(map(float, a["start"]))
        sol.value_valid = True
        h.setSolution(sol)
    t0 = time.monotonic()
    h.run()
    solve_s = time.monotonic() - t0
    info = h.getInfo()
    status = h.modelStatusToString(h.getModelStatus())
    has = int(info.primal_solution_status) == 2          # kSolutionStatusFeasible
    x = np.asarray(h.getSolution().col_value, dtype=float) if has else np.zeros(0)
    res = {"status": status, "has_solution": bool(has), "objective": _finite(info.objective_function_value) if has else None,
           "dual_bound": _finite(info.mip_dual_bound), "gap": _finite(info.mip_gap) if has else None,
           "nodes": int(info.mip_node_count), "solve_s": solve_s + lp_s, "lp_bound": lp_bound, "lp_s": lp_s,
           "highs_version": h.version()}
    tmp = out + ".tmp.npz"
    np.savez(tmp, x=x, info=np.frombuffer(json.dumps(res).encode(), dtype=np.uint8))
    os.replace(tmp, out)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through solve_mip
    sys.exit(main(sys.argv))
