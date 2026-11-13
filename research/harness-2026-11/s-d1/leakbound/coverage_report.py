"""Coverage of a leak-bound run (independent verifier's request): fires and intervals extracted vs the pool
(PERIMETER_MANIFEST intervals_le_48h; 490 fires, 3,773 intervals). Reads ONLY the scalar fields `intervals`, `newburn`,
`newburn_outside_crop` and the row count of each RUN/cache/<fire>.npz; no feature, label or prediction value.
A shortfall is attributed by re-testing pipeline.Environment.available_at on the pool's events.json window (the only
reason perimeter_samples skips an interval); any shortfall not explained that way is listed as UNEXPLAINED.
Separate from run_leakbound_L.py so the verified run script keeps its sha. Asserts count in (FOLDS fires) = count used
(cached fires) and exits non-zero otherwise (verifier row 62 note). The run script does not call pipeline.available():
it iterates all FOLDS fires directly, and a fire missing from events.json or without states.npz raises, it is not dropped.

    python coverage_report.py --run RUN --perimeters WS/data/perimeters --events WS/data/environment/events.json \
        --folds FOLDS.csv --out RUN/COVERAGE.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
SCRIPTS = REPO / "research/forecast-v2/scripts"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    for k in ("--run", "--perimeters", "--events", "--folds", "--out"):
        ap.add_argument(k, type=Path, required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(SCRIPTS)); sys.path.insert(0, str(REPO / "forecast"))
    from wildfire.survival import consecutive_intervals
    man = json.loads((a.perimeters / "PERIMETER_MANIFEST.json").read_text())["events"]
    cat = {e["id"]: e for e in json.loads(a.events.read_text())}
    fires = sorted(r["Incident_C"] for r in csv.DictReader(a.folds.open()))
    rows, missing_cache = [], []
    for ev in fires:
        c = a.run / "cache" / f"{ev}.npz"
        if not c.exists():
            missing_cache.append(ev)
            continue
        z = np.load(c)
        got, exp = int(z["intervals"]), int(man[ev]["intervals_le_48h"])
        skipped = []
        if got != exp:
            times = list(pd.to_datetime(np.load(a.perimeters / ev / "states.npz")["times"], utc=True))
            lo, hi = pd.Timestamp(cat[ev]["start_utc"]), pd.Timestamp(cat[ev]["end_utc"])
            for i, j, h in consecutive_intervals(times, 48.0):
                t = times[i].floor("h")
                if not (lo <= t <= hi):
                    skipped.append(dict(cutoff=times[i].isoformat(), reason="available_at false (no cutoff weather)"))
        row = dict(fire=ev, intervals_expected=exp, intervals_extracted=got, cells=int(len(z["y"])),
                   newburn=int(z["newburn"]), newburn_outside_crop=int(z["newburn_outside_crop"]), skipped=skipped,
                   unexplained=(exp - got) - len(skipped))
        rows.append(row)
    out = dict(pool_fires=len(fires), pool_intervals=sum(int(man[f]["intervals_le_48h"]) for f in fires),
               fires_extracted=len(rows), fires_missing_cache=missing_cache,
               intervals_extracted=sum(r["intervals_extracted"] for r in rows),
               intervals_skipped_weather=sum(len(r["skipped"]) for r in rows),
               intervals_unexplained=sum(r["unexplained"] for r in rows),
               fires_with_zero_cells=[r["fire"] for r in rows if r["cells"] == 0],
               perimeter_manifest_sha256=sha(a.perimeters / "PERIMETER_MANIFEST.json"),
               events_json_sha256=sha(a.events), folds_sha256=sha(a.folds), script_sha256=sha(__file__),
               rows=rows)
    out["count_in_equals_count_used"] = (len(rows) == len(fires) and not missing_cache)
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))
    if not out["count_in_equals_count_used"]:
        raise SystemExit(f"COUNT MISMATCH: {len(fires)} fires in, {len(rows)} used; missing: {missing_cache[:10]}")


if __name__ == "__main__":
    main()
