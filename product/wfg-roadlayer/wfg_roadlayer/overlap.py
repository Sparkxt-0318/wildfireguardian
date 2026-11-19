"""Check: do the places flagged single-exit or dangerous-road coincide with the places where the replay shows the
earliest road cut-off? Counts only.

Replay: research/kcf-replay/per_place.csv, MEASURED arm, 8 h horizon, 13 issue hours 12:00-24:00 KST (the arm the
worked example reproduces). A place's earliest cut-off = the earliest over the hours of: the issue hour when the
state is INSIDE_KNOWN_FIRE_AREA or NO_SAFE_DEPARTURE (cut at or before it), or latest_safe_departure + 1 min when it
is LATEST_SAFE_DEPARTURE. NOT_CUT_WITHIN_H at every hour = no cut-off in the replay.

"Earliest cut-off" places = within each region, the places whose earliest cut-off is at or before the first quartile
(25th percentile, lower value) of the earliest cut-offs of all its checkable places (never-cut places count as
latest). Regions are kept apart because the fire reaches 영덕 six hours after 의성·안동.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .regiondata import REPO

PER_PLACE = REPO / "research/kcf-replay/per_place.csv"
NEVER = datetime(2100, 1, 1)


def _t(s):
    return datetime.strptime("2025-" + s, "%Y-%m-%d %H:%M")


def earliest_cut(path: Path = PER_PLACE) -> dict:
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["standin"] != "MEASURED" or r["horizon"] != "8h":
            continue
        k = (r["region"], r["place_id"])
        st = r["departure_state"]
        if st in ("INSIDE_KNOWN_FIRE_AREA", "NO_SAFE_DEPARTURE"):
            t = _t(r["issue_kst"])
        elif st == "LATEST_SAFE_DEPARTURE":
            t = _t(r["latest_safe_departure_kst"]) + timedelta(minutes=1)
        else:
            t = NEVER
        out[k] = min(out.get(k, NEVER), t)
    return out


def early_set(cuts: dict) -> tuple[set, dict]:
    by_region = defaultdict(list)
    for (rid, pid), t in cuts.items():
        by_region[rid].append(t)
    q = {}
    for rid, ts in by_region.items():
        ts = sorted(ts)
        q[rid] = ts[(len(ts) - 1) // 4]
    return {k for k, t in cuts.items() if t <= q[k[0]] and t != NEVER}, q


def table(flags: dict, cuts: dict) -> dict:
    """flags: (region, place_id) -> {"single_exit": bool, "dangerous_road": bool}. Counts per region and in total."""
    early, q = early_set(cuts)
    res = {"quartile_cut_kst": {r: t.strftime("%m-%d %H:%M") for r, t in sorted(q.items())}, "rows": []}
    regions = sorted({k[0] for k in flags}) + ["all"]
    for flag in ("single_exit", "dangerous_road", "either"):
        for rid in regions:
            keys = [k for k in flags if (rid == "all" or k[0] == rid) and k in cuts]
            if flag == "either":
                f = {k for k in keys if flags[k]["single_exit"] or flags[k]["dangerous_road"]}
            else:
                f = {k for k in keys if flags[k][flag]}
            e = {k for k in keys if k in early}
            n = len(keys)
            both = len(f & e)
            res["rows"].append({"flag": flag, "region": rid, "places": n, "flagged": len(f), "earliest": len(e), "both": both,
                                "flagged_only": len(f - e), "earliest_only": len(e - f), "neither": n - len(f | e),
                                "expected_both_if_unrelated": round(len(f) * len(e) / n, 1) if n else 0})
    return res


def markdown(res: dict) -> str:
    lines = ["| flag | region | places | flagged | earliest cut-off | both | flagged only | earliest only | neither | both if unrelated |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in res["rows"]:
        lines.append("| %s | %s | %d | %d | %d | **%d** | %d | %d | %d | %.1f |" % (
            r["flag"], r["region"], r["places"], r["flagged"], r["earliest"], r["both"], r["flagged_only"], r["earliest_only"],
            r["neither"], r["expected_both_if_unrelated"]))
    lines.append("")
    lines.append("Earliest cut-off = at or before the region's first quartile: %s (KST)." %
                 ", ".join("%s %s" % kv for kv in res["quartile_cut_kst"].items()))
    return "\n".join(lines) + "\n"
