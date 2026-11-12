"""Issue-order-by on the F-DYN v3.1 deadline fields (post-processing; SCENARIO, not what happened).

Leave-by = the CONTIGUOUS deadline (merged rule: end of the first feasible interval when it starts at 0; a later
window after a gap is never a resident time). Issue-by = leave-by - alert latency - door-to-door time.
Settings are ASSUMPTIONS: lat1.5h = 90 + 30 min, lat2h = 120 + 30 min, plus the 1-h panel's low / median / high
(15+15, 99+30, 180+60 min). Every origin gets a line. Flags per origin:
  hole            : the feasible set has a gap or a late start; staff-only note "not the deadline, do not plan on it"
  dose_upper_bound: some witness at a per-destination deadline is labelled upper_bound (dose could bind) -> the
                    leave-by carries two placeholder dependencies (burning-duration law and dose limit)
  counts            : future / past (issue-by already late at the start) / late_window_only (infeasible at the start,
                      feasible later; never shown to residents) / no_route (no feasible departure at all)
  censored_at_horizon: leave-by within 10 min of the horizon -> the issue-by is bounded by the scenario horizon
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter
from pathlib import Path

SETTINGS = {"lat1.5h": (90 * 60, 30 * 60), "lat2h": (120 * 60, 30 * 60),
            "low": (15 * 60, 15 * 60), "median": (99 * 60, 30 * 60), "high": (180 * 60, 60 * 60)}


def contiguous(union):
    return union[0][1] if union and union[0][0] == 0 else None


def packet_rows(p: dict):
    t0 = dt.datetime.strptime(p["start"], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc)
    ub = {(c["origin"]) for c in p.get("checks", []) if not c.get("exact_full_policy", True)}
    cnt = {k: Counter() for k in SETTINGS}
    flags = Counter()
    rows = []
    for oid, o in sorted(p["origins_detail"].items()):
        u = o["union_cert"]
        lb = contiguous(u)
        hole = bool(u) and (len(u) > 1 or u[0][0] > 0)
        r = {"origin": oid, "type": o.get("type"), "leave_by_s": lb, "hole": hole,
             "dose_upper_bound": o["entry_node"] in ub}
        if lb is None:
            kind = "late_window_only" if u else "no_route"
            r["message"] = ("NO CHECKED ROUTE at the start in this scenario - do not wait for an order" if u else
                            "NO CHECKED ROUTE at any departure in this scenario - do not wait for an order")
            for k in SETTINGS:
                cnt[k][kind] += 1
        else:
            r["leave_by_utc"] = (t0 + dt.timedelta(seconds=lb)).strftime("%m-%d %H:%M UTC")
            for k, (a, d) in SETTINGS.items():
                ib = lb - a - d
                r["issue_by_s_" + k] = ib
                cnt[k]["past" if ib < 0 else "future"] += 1
        if hole:
            r["staff_note"] = "feasible set has a gap or late start: later windows are not the deadline, do not plan on it"
        flags["hole"] += hole
        flags["dose_upper_bound"] += r["dose_upper_bound"]
        flags["censored_at_horizon"] += lb is not None and lb >= p["H"] - 600
        rows.append(r)
    return cnt, flags, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("claim", type=Path, help="results/FDYN_V31_recorded_starts.json")
    ap.add_argument("--checks-dir", type=Path, help="raw fdyn_run outputs (for the per-witness upper_bound labels)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    doc = json.loads(a.claim.read_text())
    out = {"what": "issue-order-by on F-DYN v3.1 (SCENARIO, not what happened); leave-by = contiguous deadline; "
                   "latency settings are assumptions", "settings_s": SETTINGS, "packets": []}
    for p in doc["packets"]:
        tag = "%s__%s_h%d_%s" % (p["region"], p["start"], p["horizon_h"], p["variant"])
        if a.checks_dir and (a.checks_dir / (tag + ".json")).exists():
            p = {**p, "checks": json.loads((a.checks_dir / (tag + ".json")).read_text())["checks"]}
        p = {**p, "start": p["start"]}
        cnt, flags, rows = packet_rows(p)
        out["packets"].append({"packet": tag, "soundness": p.get("soundness"), "counts": {k: dict(v) for k, v in cnt.items()},
                               "flags": dict(flags), "origins": rows})
        print(tag, json.dumps({k: dict(v) for k, v in cnt.items()}), dict(flags))
    a.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
