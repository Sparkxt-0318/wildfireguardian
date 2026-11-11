#!/usr/bin/env python3
"""KCF facility planner command-line interface.

    python3 cli.py --case INPUT.json --output RESULT.json [--max-labels N] [--time-limit S] [--no-crosscheck]

Reads a schema_version 1 case (SCHEMA.md), writes the result atomically. Exit codes: 0 result written (any planning
status), 2 invalid input (an INVALID_INPUT result is still written), 3 internal error (an UNRESOLVED result is written
when possible). Works offline with the Python standard library only.
"""
import argparse
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kcf_planner.io import write_json_atomic  # noqa: E402
from kcf_planner.run import run_case  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", required=True, help="input case JSON (absolute or relative path)")
    ap.add_argument("--output", required=True, help="result JSON path (written atomically)")
    ap.add_argument("--max-labels", type=int, default=2_000_000, help="search cap; reaching it gives UNRESOLVED")
    ap.add_argument("--time-limit", type=float, default=None, help="wall-clock cap in seconds (UNRESOLVED if hit)")
    ap.add_argument("--no-crosscheck", action="store_true", help="skip the wfg_sipp cross-check (replay still runs)")
    a = ap.parse_args(argv)
    raw = None
    try:
        with open(a.case, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as exc:
        write_json_atomic(a.output, {"schema_version": 1, "case_id": None, "status": "INVALID_INPUT",
                                     "reason": "UNREADABLE_CASE: %s" % exc, "reason_codes": ["UNREADABLE_CASE"],
                                     "final_unload_s": None, "groups_total": None, "people_total": None,
                                     "people_with_checked_transport": 0, "trips": [], "missing_information": [],
                                     "assumptions": []})
        print("INVALID_INPUT: %s" % exc, file=sys.stderr)
        return 2
    try:
        result = run_case(raw, max_labels=a.max_labels, time_limit_s=a.time_limit, crosscheck=not a.no_crosscheck)
    except Exception as exc:  # never turn a crash into a no-route claim
        traceback.print_exc()
        write_json_atomic(a.output, {"schema_version": 1, "case_id": raw.get("case_id") if isinstance(raw, dict)
                                     else None, "status": "UNRESOLVED", "reason": "INTERNAL_ERROR: %r" % exc,
                                     "reason_codes": ["INTERNAL_ERROR"], "final_unload_s": None, "groups_total": None,
                                     "people_total": None, "people_with_checked_transport": 0, "trips": [],
                                     "missing_information": [], "assumptions": []})
        return 3
    write_json_atomic(a.output, result)
    print("%s %s final_unload_s=%s people_checked=%s/%s -> %s" % (
        result["case_id"], result["status"], result["final_unload_s"], result["people_with_checked_transport"],
        result["people_total"], os.path.abspath(a.output)))
    return 2 if result["status"] == "INVALID_INPUT" else 0


if __name__ == "__main__":
    sys.exit(main())
