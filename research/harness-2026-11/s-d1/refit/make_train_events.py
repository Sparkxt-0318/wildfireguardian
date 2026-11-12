"""Write the A1 §3.1 --train-events list (pre-weather): the forecast-v2 fit-23 fires plus every part-a incident that
Daniel's builder built (status OK), with >= 2 surveys and >= 1 consecutive-survey interval of 0 < dt <= 48 h.

The final list is fixed only after weather lands: pipeline's Environment.available_at() can still skip intervals with
missing cutoff weather, and incidents left with no usable interval are then reported (never replaced).

    python make_train_events.py --build-log BUILD_LOG.csv --out train_events/TRAIN_EVENTS_preweather.txt
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ap = argparse.ArgumentParser()
ap.add_argument("--build-log", type=Path, required=True)
ap.add_argument("--out", type=Path, required=True)
a = ap.parse_args()
fit = json.loads((REPO / "research/forecast-v2/SPLIT.json").read_text())["fit"]["us_perimeter_and_kriged"]
rows = list(csv.DictReader(a.build_log.open()))
kept, dropped = [], []
for r in rows:
    reason = ("status " + r["status"]) if r["status"] != "OK" else ("< 2 surveys" if int(r["survey_times"]) < 2 else
             ("no interval <= 48 h" if int(r["intervals_le_48h"]) < 1 else None))
    (dropped.append((r["incident"], reason)) if reason else kept.append(r["incident"]))
assert not set(fit) & set(kept), "fit-23 and part-a overlap"
events = sorted(fit) + sorted(kept)
a.out.parent.mkdir(parents=True, exist_ok=True)
a.out.write_text("\n".join(events) + "\n")
report = dict(build_log_sha256=hashlib.sha256(a.build_log.read_bytes()).hexdigest(), fit23=len(fit),
              part_a_built=len(rows), part_a_kept=len(kept), dropped=dropped, total=len(events),
              list_sha256=hashlib.sha256(a.out.read_bytes()).hexdigest(),
              intervals_le_48h_part_a=sum(int(r["intervals_le_48h"]) for r in rows if r["incident"] in set(kept)))
a.out.with_suffix(".json").write_text(json.dumps(report, indent=1) + "\n")
print(json.dumps({k: v for k, v in report.items() if k != "dropped"}), "dropped:", dropped[:10], len(dropped))
