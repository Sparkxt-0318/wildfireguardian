"""Merge the two new arms (analyze.py output on out/runs for MEASURED, MEASURED_GUST) into the committed per_place.csv and
score.json. The three stand-in rows are kept byte-for-byte. Usage: python3 merge_arms.py out/an"""
import csv, json, sys
from pathlib import Path
H = Path(__file__).resolve().parent
an = Path(sys.argv[1])
old = list(csv.DictReader(open(H / "per_place.csv", encoding="utf-8")))
new = list(csv.DictReader(open(an / "per_place.csv", encoding="utf-8")))
assert {r["standin"] for r in new} == {"MEASURED", "MEASURED_GUST"}
assert not ({r["standin"] for r in old} & {"MEASURED", "MEASURED_GUST"})
rows = old + new
with open(H / "per_place.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(old[0])); w.writeheader(); w.writerows(rows)
so = json.loads((H / "score.json").read_text()); sn = json.loads((an / "score.json").read_text())
so["score"].update(sn["score"])
so["witness_recheck_new_arms"] = sn["witness_recheck"]
so["rows"] = len(rows)
so["steps_by_issue"].update(sn["steps_by_issue"])
(H / "score.json").write_text(json.dumps(so, indent=1, ensure_ascii=False))
print(len(old), "+", len(new), "=", len(rows))
