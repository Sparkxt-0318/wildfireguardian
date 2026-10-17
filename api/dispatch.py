"""Dispatch-plan aggregation (pure functions; the attempts themselves are ordinary route checks)."""
from __future__ import annotations

import statistics

CHECKED, NO_ROUTE, UNRESOLVED = "checked_route", "model_no_route", "unresolved"


def best_verdict(attempts: list) -> str:
    """checked_route if any attempt is checked; model_no_route only if every attempt is a scoped refusal;
    otherwise unresolved (an unresolved attempt might have had a route, so a refusal cannot be concluded)."""
    vs = [a["verdict"] for a in attempts]
    if CHECKED in vs:
        return CHECKED
    if vs and all(v == NO_ROUTE for v in vs):
        return NO_ROUTE
    return UNRESOLVED


def contiguous_latest(attempts: list):
    """Largest requested offset t such that every requested offset <= t has a checked route (to some destination);
    None when the earliest requested offset has none. Stops at the first offset with no checked route, because a
    refusal or unresolved result in between means waiting at the origin until a later offset is not supported."""
    offsets = sorted({a["depart_offset_s"] for a in attempts})
    ok = {a["depart_offset_s"] for a in attempts if a["verdict"] == CHECKED}
    latest = None
    for t in offsets:
        if t not in ok:
            break
        latest = t
    return latest


def origin_plan(origin_id: str, snap, attempts: list, dest_order: dict) -> dict:
    attempts = sorted(attempts, key=lambda a: (a["depart_offset_s"], dest_order.get(a["destination_id"], 0)))
    checked = [a for a in attempts if a["verdict"] == CHECKED]
    latest = max((a["depart_offset_s"] for a in checked), default=None)
    best = None
    if latest is not None:
        cands = [a for a in checked if a["depart_offset_s"] == latest]
        best = min(cands, key=lambda a: (a["arrival_s"], dest_order.get(a["destination_id"], 0)))
    return {"origin_id": origin_id, "urgency_rank": 0, "snap": snap, "best_verdict": best_verdict(attempts),
            "latest_checked_depart_offset_s": latest, "latest_contiguous_checked_depart_offset_s": contiguous_latest(attempts),
            "best": best, "attempts": attempts}


def sort_by_urgency(plans: list, origin_order: dict) -> list:
    """Earliest latest-safe-departure first, then model_no_route, then unresolved (the order the task fixes).
    Within checked origins the conservative contiguous latest offset is used; an origin whose earliest requested offset
    has no checked route (contiguous value None) ranks first."""
    group = {CHECKED: 0, NO_ROUTE: 1, UNRESOLVED: 2}

    def key(p):
        g = group[p["best_verdict"]]
        c = p.get("latest_contiguous_checked_depart_offset_s")
        lat = (float("-inf") if c is None else c) if g == 0 else 0
        arr = p["best"]["arrival_s"] if p["best"] else 0
        return (g, lat, arr, origin_order.get(p["origin_id"], 0))
    out = sorted(plans, key=key)
    for i, p in enumerate(out, 1):
        p["urgency_rank"] = i
    return out


def summary(plans: list, attempts: list, wall_s=None) -> dict:
    cs = [a["compute_s"] for a in attempts if a.get("compute_s") is not None]
    return {"origins": len(plans), "attempts": len(attempts),
            "checked_route": sum(p["best_verdict"] == CHECKED for p in plans),
            "model_no_route": sum(p["best_verdict"] == NO_ROUTE for p in plans),
            "unresolved": sum(p["best_verdict"] == UNRESOLVED for p in plans),
            "attempt_verdicts": {v: sum(a["verdict"] == v for a in attempts) for v in (CHECKED, NO_ROUTE, UNRESOLVED)},
            "median_compute_s": statistics.median(cs) if cs else None, "wall_s": wall_s}
