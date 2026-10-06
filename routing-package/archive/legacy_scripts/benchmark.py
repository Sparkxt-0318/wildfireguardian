#!/usr/bin/env python3
"""Mechanical, subprocess-isolated benchmark for the frozen 17-case fixture.

No timing run is started by importing this module.  See --help and
evidence/BENCHMARK_PROTOCOL.json before invoking --run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures" / "evaluation_cases.json"
FREEZE = ROOT / "evidence" / "EVALUATION_FREEZE.json"
METHODS = ("legacy", "baseline", "astar", "dijkstra", "suffix")
MODES = ("cold", "warm")
REPETITIONS = 3


def read_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def frozen_cases():
    raw = FIXTURE.read_bytes()
    freeze = read_json(FREEZE)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != freeze.get("sha256"):
        raise RuntimeError(f"frozen fixture hash mismatch: expected {freeze.get('sha256')}, got {digest}")
    candidate_path=ROOT/"evidence/CANDIDATE_FREEZE.json"
    if candidate_path.exists():
        for name,expected in read_json(candidate_path)["hashes"].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:
                raise RuntimeError("candidate source changed after freeze: "+name)
    document = json.loads(raw)
    cases = document["cases"]
    if len(cases) != freeze.get("cases"):
        raise RuntimeError(f"frozen case count mismatch: {len(cases)}")
    return digest, cases


def _peak_rss_bytes():
    # macOS ru_maxrss is bytes; Linux and most BSDs report KiB.
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def _solve(case, method):
    if method == "legacy":
        from routing import legacy_bridge
        return legacy_bridge.solve(case["graph"], case["hazard"], case["request"])
    if method == "suffix":
        from routing.optimization import solve
        return solve(case["graph"],case["hazard"],case["request"])
    from routing import core
    request = dict(case["request"])
    request["solver"] = {"baseline": "baseline", "astar": "astar", "dijkstra": "dijkstra"}[method]
    return core.solve(case["graph"], case["hazard"], request)


def child(case_id, method, mode):
    _, cases = frozen_cases()
    by_id = {case["id"]: case for case in cases}
    if case_id not in by_id:
        raise ValueError(f"unknown frozen case id: {case_id}")
    case = by_id[case_id]
    record = {"case_id": case_id, "method": method, "mode": mode,
              "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
              "pid": os.getpid(), "python": sys.executable}
    try:
        if mode == "warm":
            warm_start = time.perf_counter()
            warm_result = _solve(case, method)
            record["warmup_elapsed_s"] = time.perf_counter() - warm_start
            record["warmup_status"] = warm_result.get("status") if isinstance(warm_result, dict) else "NON_DICT_RESULT"
        start = time.perf_counter()
        result = _solve(case, method)
        elapsed = time.perf_counter() - start
        record.update({"status": result.get("status", "INVALID_RESULT"),
                       "reason": result.get("reason"), "arrival": result.get("arrival"),
                       "destination": result.get("destination"),
                       "legs": result.get("legs", []),
                       "solver_status": result.get("solver_status"),
                       "metrics": result.get("metrics", {}),
                       "charged_elapsed_s": elapsed,
                       "process_peak_rss_bytes": _peak_rss_bytes()})
        # Keep the method's returned checker and separately run the independent checker
        # as distinct evidence.  This post-check is not in charged method time.
        if result.get("status") in {"CHECKED_ROUTE","CONDITIONAL_OPTIMUM"} and result.get("destination") is not None:
            try:
                from routing.independent import check_route
                check = check_route(case["graph"], case["hazard"], case["request"],
                                    result["legs"], result["destination"])
                record["independent_postcheck"] = check
            except Exception as exc:
                record["independent_postcheck"] = {"ok": False, "status": "CHECK_ERROR",
                                                    "error": f"{type(exc).__name__}:{exc}"}
        else:
            record["independent_postcheck"] = None
    except Exception as exc:
        unavailable = method == "legacy" and isinstance(exc, (ImportError, ModuleNotFoundError))
        record.update({"status": "NOT_AVAILABLE" if unavailable else "UNRESOLVED_EXCEPTION",
                       "reason": f"{type(exc).__name__}:{exc}",
                       "charged_elapsed_s": None, "process_peak_rss_bytes": _peak_rss_bytes()})
    print(json.dumps(record, sort_keys=True, default=str))


def independent_references(cases):
    from routing.independent import exhaustive
    outcomes = {}
    for case in cases:
        started = time.perf_counter()
        try:
            result = exhaustive(case["graph"], case["hazard"], case["request"])
            elapsed = time.perf_counter() - started
            outcomes[case["id"]] = {"status": result.get("status"),
                                     "arrival": result.get("arrival"),
                                     "destination": result.get("destination"),
                                     "walks": result.get("walks"), "reason": result.get("reason"),
                                     "elapsed_s_untimed": elapsed,
                                     "legs": result.get("legs", [])}
        except Exception as exc:
            outcomes[case["id"]] = {"status": "REFERENCE_ERROR", "arrival": None,
                                     "reason": f"{type(exc).__name__}:{exc}", "walks": None,
                                     "elapsed_s_untimed": time.perf_counter() - started}
    return outcomes


def child_interpreter(method, python, legacy_python):
    return legacy_python if method == "legacy" and legacy_python else python


def run(out_path: Path, python: str, legacy_python: str | None):
    digest, cases = frozen_cases()
    out_path.mkdir(parents=True, exist_ok=True)
    refs = independent_references(cases)
    (out_path / "reference.json").write_text(json.dumps({
        "fixture_sha256": digest, "reference": "routing.independent.exhaustive",
        "timing_role": "separate untimed checker evidence; never charged to a method",
        "cases": refs}, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rows = []
    total = len(cases) * len(METHODS) * len(MODES) * REPETITIONS
    for case_index, case in enumerate(cases):
        for mode in MODES:
            for repetition in range(REPETITIONS):
                # Rotate arm order across repetitions and cases to avoid a fixed-order bias.
                shift = (repetition + case_index) % len(METHODS)
                ordered = METHODS[shift:] + METHODS[:shift]
                for method in ordered:
                    args = [child_interpreter(method, python, legacy_python), str(Path(__file__).resolve()),
                            "--child", case["id"], method, mode]
                    proc_start = time.perf_counter()
                    try:
                        completed = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=case["request"]["limits"]["wall_s"]+10)
                    except subprocess.TimeoutExpired:
                        completed = subprocess.CompletedProcess(args,124,"","EXTERNAL_WATCHDOG_TIMEOUT")
                    process_elapsed = time.perf_counter() - proc_start
                    if completed.returncode == 0 and completed.stdout.strip():
                        try:
                            row = json.loads(completed.stdout.strip().splitlines()[-1])
                        except json.JSONDecodeError as exc:
                            row = {"case_id": case["id"], "method": method, "mode": mode,
                                   "status": "CHILD_OUTPUT_ERROR", "reason": str(exc)}
                    else:
                        row = {"case_id": case["id"], "method": method, "mode": mode,
                               "status": "CHILD_FAILED", "reason": completed.stderr[-2000:],
                               "returncode": completed.returncode,
                               "charged_elapsed_s": None, "process_peak_rss_bytes": None}
                    row.update({"repetition": repetition + 1, "run_order": len(rows) + 1,
                                "process_elapsed_s": process_elapsed,
                                "reference_status": refs[case["id"]].get("status"),
                                "reference_arrival": refs[case["id"]].get("arrival")})
                    ref_status, ref_arrival = refs[case["id"]].get("status"), refs[case["id"]].get("arrival")
                    if row.get("status") in {"CHECKED_ROUTE", "CONDITIONAL_OPTIMUM"}:
                        row["mechanical_agreement"] = (
                            ref_status in {"CHECKED_ROUTE", "CONDITIONAL_OPTIMUM"}
                            and row.get("arrival") == ref_arrival
                        ) if ref_status in {"CHECKED_ROUTE", "CONDITIONAL_OPTIMUM"} else None
                    elif row.get("status") in {"PROVEN_INFEASIBLE", "DISCONNECTED"}:
                        row["mechanical_agreement"] = (
                            ref_status in {"PROVEN_INFEASIBLE", "DISCONNECTED"}
                        ) if ref_status in {"PROVEN_INFEASIBLE", "DISCONNECTED"} else None
                    else:
                        row["mechanical_agreement"] = None
                    rows.append(row)
                    print(f"[{len(rows)}/{total}] {case['id']} {method} {mode} r{repetition+1}: {row.get('status')}", flush=True)
    with (out_path / "rows.jsonl").open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    by_key = {(r.get("case_id"), r.get("mode"), r.get("repetition"), r.get("method")): r for r in rows}
    pairs = []
    for case in cases:
        for mode in MODES:
            for repetition in range(1, REPETITIONS + 1):
                for i, left_method in enumerate(METHODS):
                    for right_method in METHODS[i+1:]:
                        left = by_key.get((case["id"], mode, repetition, left_method), {})
                        right = by_key.get((case["id"], mode, repetition, right_method), {})
                        left_time, right_time = left.get("charged_elapsed_s"), right.get("charged_elapsed_s")
                        left_exp = (left.get("metrics") or {}).get("expansions")
                        right_exp = (right.get("metrics") or {}).get("expansions")
                        pairs.append({"case_id": case["id"], "mode": mode, "repetition": repetition,
                                      "left_method": left_method, "right_method": right_method,
                                      "left_status": left.get("status"), "right_status": right.get("status"),
                                      "left_elapsed_s": left_time, "right_elapsed_s": right_time,
                                      "elapsed_delta_right_minus_left_s": (right_time-left_time)
                                      if isinstance(left_time, (int, float)) and isinstance(right_time, (int, float)) else None,
                                      "right_timing_regression": (right_time > left_time)
                                      if isinstance(left_time, (int, float)) and isinstance(right_time, (int, float)) else None,
                                      "left_expansions": left_exp, "right_expansions": right_exp,
                                      "expansion_delta_right_minus_left": right_exp-left_exp
                                      if isinstance(left_exp, (int, float)) and isinstance(right_exp, (int, float)) else None,
                                      "right_expansion_regression": (right_exp > left_exp)
                                      if isinstance(left_exp, (int, float)) and isinstance(right_exp, (int, float)) else None})
    (out_path / "paired_comparisons.json").write_text(json.dumps({
        "pairing": "same frozen case, mode, and repetition; method order is rotated",
        "rows": pairs, "rows_per_pair": len(cases) * len(MODES) * REPETITIONS,
        "pairs": [f"{METHODS[i]} vs {METHODS[j]}" for i in range(len(METHODS)) for j in range(i+1, len(METHODS))]},
        indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {"fixture_sha256": digest, "expected_rows": total, "actual_rows": len(rows),
               "methods": METHODS, "modes": MODES, "repetitions": REPETITIONS,
               "all_rows_retained": len(rows) == total,
               "status_counts": {}, "mechanical_disagreements": []}
    for row in rows:
        key = f"{row.get('method')}|{row.get('mode')}|{row.get('status')}"
        summary["status_counts"][key] = summary["status_counts"].get(key, 0) + 1
        if row.get("mechanical_agreement") is False:
            summary["mechanical_disagreements"].append({"case_id": row.get("case_id"),
                                                        "method": row.get("method"),
                                                        "mode": row.get("mode"),
                                                        "repetition": row.get("repetition"),
                                                        "status": row.get("status"),
                                                        "arrival": row.get("arrival"),
                                                        "reference_status": row.get("reference_status"),
                                                        "reference_arrival": row.get("reference_arrival")})
    (out_path / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", nargs=3, metavar=("CASE_ID", "METHOD", "MODE"))
    parser.add_argument("--run", action="store_true", help="run all frozen case/method/mode/repetition rows")
    parser.add_argument("--out", type=Path, help="output directory for --run")
    parser.add_argument("--python", default=sys.executable, help="interpreter for baseline/A*/Dijkstra children")
    parser.add_argument("--legacy-python", help="interpreter with NumPy for legacy children")
    args = parser.parse_args()
    if args.child:
        case_id, method, mode = args.child
        if method not in METHODS or mode not in MODES:
            parser.error("invalid --child method or mode")
        child(case_id, method, mode)
    elif args.run:
        if args.out is None:
            parser.error("--run requires --out")
        run(args.out, args.python, args.legacy_python)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
