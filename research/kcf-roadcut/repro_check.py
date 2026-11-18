"""PROTOCOL.md §1.1 reproduction check: analyze.py on the rerun vs the committed research/kcf-replay/per_place.csv.

Usage: python3 repro_check.py RERUN_PER_PLACE.csv OUT.json
"""
import csv, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLS = ["government_step", "departure_state", "latest_safe_departure_kst", "last_departure_in_horizon_kst",
        "departure_set_pieces", "shelter_id", "arrival_kst"]
KEY = ("region", "place_id", "issue_kst", "standin", "horizon")


def load(p):
    with open(p, encoding="utf-8") as f:
        return {tuple(r[k] for k in KEY): r for r in csv.DictReader(f)}


def main(rerun, out):
    a = load(ROOT / "research/kcf-replay/per_place.csv"); b = load(rerun)
    miss = sorted(set(a) ^ set(b))
    diff = Counter(); rows = []
    for k in set(a) & set(b):
        d = [c for c in COLS if a[k][c] != b[k][c]]
        for c in d:
            diff[c] += 1
        if d:
            rows.append({"key": k, "cols": {c: [a[k][c], b[k][c]] for c in d}})
    res = {"committed_rows": len(a), "rerun_rows": len(b), "keys_only_in_one": len(miss),
           "rows_with_any_mismatch": len(rows), "mismatches_by_column": dict(diff), "mismatch_rows": rows[:200]}
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print({k: v for k, v in res.items() if k != "mismatch_rows"})


if __name__ == "__main__":
    main(*sys.argv[1:3])
