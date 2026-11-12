"""Reverse-direction coverage check (Owen's note on 10ce6b93): the rebuilt case_ids in a control output equal the
stored heldout receipts exactly (none stored-not-rebuilt, none rebuilt-not-stored). A separate script so the verified
unmodified_rollout_control.py keeps its sha.

    python check_case_coverage.py --results RESULTS_identity.jsonl --heldout HELDOUT
"""
import argparse
import json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--results", type=Path, required=True)
ap.add_argument("--heldout", type=Path, required=True)
a = ap.parse_args()
rebuilt = [json.loads(l)["case_id"] for l in a.results.open() if '"header"' not in l]
stored = {p.stem for p in (a.heldout / "cases").glob("*.json")}
out = dict(rebuilt=len(rebuilt), rebuilt_unique=len(set(rebuilt)), stored=len(stored),
           stored_not_rebuilt=sorted(stored - set(rebuilt)), rebuilt_not_stored=sorted(set(rebuilt) - stored))
out["ok"] = (len(rebuilt) == len(set(rebuilt)) and not out["stored_not_rebuilt"] and not out["rebuilt_not_stored"])
print(json.dumps(out))
raise SystemExit(0 if out["ok"] else 1)
