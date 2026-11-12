"""Apply addendum A1 §1.2 (committed before this script first ran): NIROPS four-part split.

Reads only these metadata columns of nirops_incidents.csv: Incident_C, surveys,
project_status, shares_irwin_with_project_fire and year. max_acres is never read.

  python select_cohort.py --incidents nirops_incidents.csv --out COHORT_SPLIT.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

USED = ("forecast_v2_fit", "held_out")
MIN_SURVEYS = 20
SIZES = (("b", 30), ("c", 30), ("a", 60))  # in rank order; the remainder is d


def u_of(incident: str) -> float:
    return int(hashlib.sha256(("S-D9-A1|NIROPS|" + incident).encode()).hexdigest()[:12], 16) / 16 ** 12


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--incidents", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    rows = list(csv.DictReader(args.incidents.open()))
    statuses = sorted({r["project_status"] for r in rows})
    clean = [r for r in rows if r["project_status"] not in USED and r["project_status"] == "unused"
             and r["shares_irwin_with_project_fire"] == "False"]
    eligible = sorted((r for r in clean if int(r["surveys"]) >= MIN_SURVEYS), key=lambda r: u_of(r["Incident_C"]))
    out, rank = [], 0
    for part, n in SIZES:
        for r in eligible[rank:rank + n]:
            out.append((r, part))
        rank += n
    out += [(r, "d") for r in eligible[rank:]]
    out += [(r, "a") for r in sorted(clean, key=lambda r: u_of(r["Incident_C"])) if int(r["surveys"]) < MIN_SURVEYS]
    with args.out.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["Incident_C", "irwinid", "year", "surveys", "u", "eligible", "part", "eligible_rank"])
        ranks = {r["Incident_C"]: i + 1 for i, r in enumerate(eligible)}
        for r, part in sorted(out, key=lambda x: u_of(x[0]["Incident_C"])):
            w.writerow([r["Incident_C"], r["irwinid"], r["year"], r["surveys"], f"{u_of(r['Incident_C']):.12f}",
                        int(r["surveys"]) >= MIN_SURVEYS, part, ranks.get(r["Incident_C"], "")])
    counts = {p: sum(1 for _, q in out if q == p) for p in "abcd"}
    pilot = [r["Incident_C"] for r, p in sorted(out, key=lambda x: u_of(x[0]["Incident_C"]))
             if p == "a" and int(r["surveys"]) >= MIN_SURVEYS][:3]
    summary = dict(source_rows=len(rows), statuses=statuses, clean=len(clean), eligible=len(eligible),
                   parts=counts, pilot_first_3_part_a_eligible=pilot,
                   out_sha256=hashlib.sha256(args.out.read_bytes()).hexdigest())
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
