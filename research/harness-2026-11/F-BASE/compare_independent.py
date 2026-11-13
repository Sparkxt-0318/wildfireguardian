"""Compare F-BASE exact results with the frozen published independent rows (Main 2a751631,
research/routing/INDEPENDENT_ROWS.csv; column meanings per INDEPENDENT_REPORT.v1.md: `resolved` = outcome
resolved under the frozen rules, `route` = a checked route was returned, `arrival` = arrival second).

    python compare_independent.py --rows INDEPENDENT_ROWS.csv [--panel RESULTS_panel.json] [--out RESULTS_independent.json]
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ap = argparse.ArgumentParser()
ap.add_argument("--rows", type=Path, required=True)
ap.add_argument("--panel", type=Path, default=HERE / "RESULTS_panel.json")
ap.add_argument("--out", type=Path, default=HERE / "RESULTS_independent.json")
a = ap.parse_args()
panel = {r["mission"]: r["solvers"]["exact"] for r in json.loads(a.panel.read_text())["rows"]}
out, tally = [], {}
for row in csv.DictReader(a.rows.open()):
    ex = panel[row["case_id"]]
    resolved = row["resolved"] == "True"
    ref = ("ROUTE", int(row["arrival"])) if row["route"] == "True" else ("NO_ROUTE", None)
    agree = (ex["claim"], ex["T"]) == ref if resolved else None
    out.append(dict(case_id=row["case_id"], arm=row["arm"], rep=row["rep"], state=row["state"], resolved=resolved,
                    reference=list(ref) if resolved else None, exact=[ex["claim"], ex["T"]], agrees=agree))
    t = tally.setdefault(row["arm"], dict(rows=0, resolved=0, agree=0))
    t["rows"] += 1; t["resolved"] += resolved; t["agree"] += bool(agree)
res = dict(source=dict(file="research/routing/INDEPENDENT_ROWS.csv", commit="2a751631",
                       sha256=hashlib.sha256(a.rows.read_bytes()).hexdigest()),
           scope="contact relaxation (O2); equality with full-policy verdicts only under the per-request dose/peak precondition",
           tally=tally, rows=out)
a.out.write_text(json.dumps(res, indent=1))
print(json.dumps(tally)); [print(r) for r in out if r["agrees"] is False]
