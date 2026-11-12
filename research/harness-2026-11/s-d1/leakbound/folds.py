"""LEAK_BOUND_PLAN fold rule (fixed in the plan): fire -> int(sha256(Incident_C).hexdigest(), 16) mod 5, over
PART_A_ALLOWLIST_FINAL (7db3cc0e...). Writes FOLDS.csv and prints its sha256; committed before any fit.

    python folds.py --allowlist PART_A_ALLOWLIST_FINAL.csv --out FOLDS.csv
"""
import argparse
import csv
import hashlib
from collections import Counter
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--allowlist", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()
assert hashlib.sha256(a.allowlist.read_bytes()).hexdigest().startswith("7db3cc0e"), "not PART_A_ALLOWLIST_FINAL"
ids = sorted({r["Incident_C"] for r in csv.DictReader(a.allowlist.open())})
rows = [(i, int(hashlib.sha256(i.encode()).hexdigest(), 16) % 5) for i in ids]
with a.out.open("w", newline="") as f:
    w = csv.writer(f); w.writerow(["Incident_C", "fold"]); w.writerows(rows)
print(len(rows), dict(sorted(Counter(k for _, k in rows).items())), hashlib.sha256(a.out.read_bytes()).hexdigest())
