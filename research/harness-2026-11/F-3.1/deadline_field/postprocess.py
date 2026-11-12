"""Post-processing on top of a verified deadline field (kept separate from the field itself).

Issue-order-by time per village = exact leave-by time - alert latency - door-to-door time.
Latency settings are ASSUMPTIONS for a sensitivity table, not measurements of this event:
  low    : 15 min alert + 15 min door-to-door
  median : 99 min alert (Board of Audit mean situation-room-to-text, 1 h 39 min; Sofia's source) + 30 min
  high   : 180 min alert + 60 min door-to-door
Every origin gets an explicit line; silence is never emitted. Times are seconds after the forecast input time; a
negative issue-by time means the order is already late at the forecast time under that setting.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

SETTINGS = {"low": (15 * 60, 15 * 60), "median": (99 * 60, 30 * 60), "high": (180 * 60, 60 * 60)}


def hhmm(sec, input_time):
    import datetime as dt
    t0 = dt.datetime.fromisoformat(input_time.replace("Z", "+00:00"))
    return (t0 + dt.timedelta(seconds=int(sec))).strftime("%H:%M UTC")


def issue_by(run: dict, variant="cert"):
    rows = []
    counts = {k: {"past": 0, "future": 0, "no_route": 0} for k in SETTINGS}
    for oid, o in sorted(run["origins"].items()):
        lb = o.get("field_deadline_exact_uncapped_" + variant)
        row = {"origin": oid, "kind": o.get("kind"), "leave_by_s": lb}
        if lb is None:
            row["message"] = "NO CHECKED ROUTE in this model at any departure - do not wait for an order"
            for k in SETTINGS:
                counts[k]["no_route"] += 1
        else:
            row["message"] = "not ordered yet - leave by %s" % hhmm(lb, run["input_time"])
            for k, (alert, door) in SETTINGS.items():
                ib = lb - alert - door
                row["issue_by_s_" + k] = ib
                counts[k]["past" if ib < 0 else "future"] += 1
        rows.append(row)
    return {"input_time": run["input_time"], "cache_file": run.get("cache_file"), "settings_s": SETTINGS,
            "counts": counts, "origins": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    out = [issue_by(json.loads(p.read_text())) for p in a.runs]
    a.out.write_text(json.dumps(out, indent=1))
    for o in out:
        print(o["cache_file"], json.dumps(o["counts"]))


if __name__ == "__main__":
    main()
