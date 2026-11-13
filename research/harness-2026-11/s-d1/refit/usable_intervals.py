"""A1 §3.1 train-events finalisation: usable intervals per event under the landed weather (no-usable-interval report).

An interval is usable iff pipeline.perimeter_samples would not skip it for weather: for each
consecutive_intervals(times, 48.0) pair (i, j), Environment.available_at(event, times[i].floor("h")) holds, i.e.
start_utc <= floor_h(t_i) <= end_utc, read from the pool's events.json (the catalog available_at uses). Also required:
Daniel's per-event weather completeness record is all_finite with bands == complete_hours, and floor_h(t_i) lies in its
band window [first_band_utc, last_band_utc]. Any difference between the catalog window and the band window is reported.
Events with zero usable intervals are REPORTED and never replaced. Stage 1 = part a (490); fit-23 follows on day 2.

    python usable_intervals.py --preweather train_events/TRAIN_EVENTS_preweather.txt --pool PARTA_POOL \
        --completeness parta_weather_completeness_night1.json --stage parta --out USABLE_parta.json
"""
from __future__ import annotations

import argparse
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
    ap.add_argument("--preweather", type=Path, required=True)
    ap.add_argument("--pool", type=Path, required=True)
    ap.add_argument("--completeness", type=Path, required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(SCRIPTS)); sys.path.insert(0, str(REPO / "forecast"))
    spec = importlib.util.spec_from_file_location("full_cohort_pipeline", SCRIPTS / "pipeline.py")
    P = importlib.util.module_from_spec(spec); sys.modules[spec.name] = P; spec.loader.exec_module(P)
    comp = json.loads(a.completeness.read_text())
    manifest = json.loads((a.pool / "PERIMETER_MANIFEST.json").read_text())
    catalog = {e["id"]: e for e in json.loads((a.pool / "events.json").read_text())}
    window_diff, item5_diff = [], []
    events = [e.strip() for e in a.preweather.read_text().splitlines() if e.strip()]
    rows, zero, not_in_stage = [], [], []
    for ev in events:
        if ev not in comp:
            not_in_stage.append(ev)
            continue
        c = comp[ev]
        sp = a.pool / "perimeters" / ev / "states.npz"
        if sha(sp) != manifest["events"][ev]["states_sha256"]:
            raise SystemExit(f"perimeter sha mismatch: {ev}")
        times = list(pd.to_datetime(np.load(sp, allow_pickle=False)["times"], utc=True))
        lo, hi = pd.Timestamp(c["first_band_utc"]), pd.Timestamp(c["last_band_utc"])
        clo, chi = pd.Timestamp(catalog[ev]["start_utc"]), pd.Timestamp(catalog[ev]["end_utc"])
        if (clo, chi) != (lo, hi):
            window_diff.append(dict(event=ev, catalog=[str(clo), str(chi)], bands=[str(lo), str(hi)]))
        ok_rec = bool(c["all_finite"]) and c["bands"] == c["complete_hours"]
        # §3.1 item 5: catalog window = [floor_hour(first survey), ceil_hour(last survey)]
        exp = (min(times).floor("h"), max(times).ceil("h"))
        if (clo, chi) != exp:
            item5_diff.append(dict(event=ev, catalog=[str(clo), str(chi)], expected=[str(exp[0]), str(exp[1])]))
        iv = list(P.consecutive_intervals(times, 48.0))

        def why(i):  # which test skips the interval; available_at is the §3.1 test, the others are stricter extras
            t = times[i].floor("h")
            return [n for n, ok in (("available_at", clo <= t <= chi), ("band_window", lo <= t <= hi),
                                    ("record", ok_rec)) if not ok]
        usable = [k for k, (i, j, h) in enumerate(iv) if not why(i)]
        rows.append(dict(event=ev, intervals_le_48h=len(iv), usable=len(usable), record_ok=ok_rec,
                         skipped=[dict(t1=times[i].isoformat(), hours=h, failed_tests=why(i)) for k, (i, j, h) in enumerate(iv)
                                  if k not in set(usable)]))
        if not usable:
            zero.append(ev)
    out = dict(stage=a.stage, rule="usable iff events.json start_utc <= floor_h(cutoff) <= end_utc (pipeline.available_at) and the weather record is all-finite with floor_h(cutoff) in its band window",
               preweather_sha256=sha(a.preweather), completeness_sha256=sha(a.completeness),
               perimeter_manifest_sha256=sha(a.pool / "PERIMETER_MANIFEST.json"), events_json_sha256=sha(a.pool / "events.json"),
               pipeline_sha256=sha(SCRIPTS / "pipeline.py"), script_sha256=sha(__file__),
               events_in_stage=len(rows), events_not_in_stage=len(not_in_stage),
               intervals_le_48h=sum(r["intervals_le_48h"] for r in rows), usable_intervals=sum(r["usable"] for r in rows),
               events_with_skips=sum(1 for r in rows if r["skipped"]), catalog_vs_band_window_differences=window_diff,
               item5_catalog_window_is_floor_first_ceil_last_survey=dict(events_checked=len(rows), differences=item5_diff), no_usable_interval=zero, rows=rows)
    a.out.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
