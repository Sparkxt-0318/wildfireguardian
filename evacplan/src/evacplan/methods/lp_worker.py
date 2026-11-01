"""Solve one LP with HiGHS (``highspy``) in a child process and return the primal values and the row duals.

Used by E4 (:mod:`evacplan.methods.flow_bound`). Like :mod:`evacplan.methods.highs_worker` (B3), the LP is
solved in a child process because the OR-Tools wheel (B2) bundles an ABI-incompatible ``libhighs.so.1``
(HiGHS 1.11 vs ``highspy`` 1.15; the loader keeps whichever is loaded first). The parent never imports
``highspy``: :func:`solve_lp` writes the model to a temporary ``.npz``, runs this file as a script
(``python -I lp_worker.py IN OUT``; only numpy and highspy are imported there) and reads the result back.
The child's start-up time counts in the method's wall clock.

The row duals are returned so that the caller can turn them into a bound by weak duality
(:func:`evacplan.methods.flow_bound.dual_bound`), which holds whatever the solver's tolerances or status.
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
class LpResult:
    status: str                       # HiGHS model status, or "worker failed: ..." / "worker timeout"
    objective: float | None           # primal objective (maximized) when HiGHS reports one
    x: np.ndarray | None              # primal column values
    row_dual: np.ndarray | None       # row duals (HiGHS sign convention; the caller tries both signs)
    solve_s: float                    # HiGHS run time in the child
    wall_s: float                     # including the child's start-up and I/O
    info: dict = field(default_factory=dict)


def solve_lp(arrays: dict[str, np.ndarray], *, time_limit: float, threads: int = 1, solver: str = "ipm",
             crossover: bool = False, presolve: bool = False, ipm_tolerance: float | None = None,
             grace_s: float = 30.0) -> LpResult:
    """Maximize ``cost @ x`` subject to ``row_lower <= A x <= row_upper`` and the column bounds (``A`` row-wise:
    ``a_start``, ``a_index``, ``a_value``), in a child process, within ``time_limit`` seconds of HiGHS time.
    Presolve is off by default: without crossover, HiGHS's postsolve does not restore consistent row duals, and
    the duals are what the bound is computed from."""
    t0 = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="evacplan-lp-") as tmp:
        inp, out = Path(tmp) / "model.npz", Path(tmp) / "result.npz"
        opts = {"time_limit": max(0.05, float(time_limit)), "threads": int(threads), "solver": str(solver),
                "run_crossover": "on" if crossover else "off", "presolve": "on" if presolve else "off"}
        if ipm_tolerance is not None:
            opts["ipm_optimality_tolerance"] = float(ipm_tolerance)
        np.savez(inp, **{k: np.asarray(v) for k, v in arrays.items()},
                 options=np.frombuffer(json.dumps(opts).encode(), dtype=np.uint8))
        try:
            proc = subprocess.run([sys.executable, "-I", str(WORKER), str(inp), str(out)], capture_output=True,
                                  text=True, timeout=opts["time_limit"] + grace_s,
                                  env={k: v for k, v in os.environ.items() if not k.startswith("PYTHON")})
        except subprocess.TimeoutExpired:
            return LpResult("worker timeout", None, None, None, math.nan, time.monotonic() - t0)
        if proc.returncode != 0 or not out.is_file():
            msg = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["no output"]
            return LpResult(f"worker failed: {msg[0][:200]}", None, None, None, math.nan, time.monotonic() - t0)
        with np.load(out) as r:
            info = json.loads(bytes(r["info"]).decode())
            x = np.array(r["x"]) if r["x"].size else None
            dual = np.array(r["row_dual"]) if r["row_dual"].size else None
    return LpResult(info["status"], info["objective"], x, dual, float(info["solve_s"]), time.monotonic() - t0, info)


def main(argv: list[str]) -> int:      # runs in the child process
    import highspy

    inp, out = argv[1], argv[2]
    with np.load(inp) as d:
        a = {k: np.array(d[k]) for k in d.files}
    opts = json.loads(bytes(a.pop("options")).decode())
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    lp = highspy.HighsLp()
    lp.num_col_ = int(a["cost"].size)
    lp.num_row_ = int(a["row_lower"].size)
    lp.col_cost_ = a["cost"]
    lp.col_lower_ = a["lower"]
    lp.col_upper_ = np.where(np.isinf(a["upper"]), highspy.kHighsInf, a["upper"])
    lp.row_lower_ = np.where(np.isinf(a["row_lower"]), -highspy.kHighsInf, a["row_lower"])
    lp.row_upper_ = np.where(np.isinf(a["row_upper"]), highspy.kHighsInf, a["row_upper"])
    lp.a_matrix_.format_ = highspy.MatrixFormat.kRowwise
    lp.a_matrix_.start_ = a["a_start"].astype(np.int32)
    lp.a_matrix_.index_ = a["a_index"].astype(np.int32)
    lp.a_matrix_.value_ = a["a_value"]
    lp.sense_ = highspy.ObjSense.kMaximize
    h.passModel(lp)
    for k, v in opts.items():
        h.setOptionValue(k, v)
    t0 = time.monotonic()
    h.run()
    solve_s = time.monotonic() - t0
    status = h.modelStatusToString(h.getModelStatus())
    info = h.getInfo()
    sol = h.getSolution()
    x = np.asarray(sol.col_value, dtype=float) if sol.value_valid else np.zeros(0)
    dual = np.asarray(sol.row_dual, dtype=float) if sol.dual_valid else np.zeros(0)
    obj = float(info.objective_function_value)
    res = {"status": status, "objective": obj if (sol.value_valid and math.isfinite(obj)) else None,
           "solve_s": solve_s, "iterations_ipm": int(info.ipm_iteration_count),
           "iterations_simplex": int(info.simplex_iteration_count), "highs_version": h.version(),
           "value_valid": bool(sol.value_valid), "dual_valid": bool(sol.dual_valid)}
    tmp = out + ".tmp.npz"
    np.savez(tmp, x=x, row_dual=dual, info=np.frombuffer(json.dumps(res).encode(), dtype=np.uint8))
    os.replace(tmp, out)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through solve_lp
    sys.exit(main(sys.argv))
