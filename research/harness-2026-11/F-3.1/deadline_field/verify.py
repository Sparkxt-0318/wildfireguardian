"""Witness verification with UNCHANGED checkers (nothing here relaxes anything):

* full policy: routing-package/routing/independent.py::check_route (the kit's independently authored delivery
  checker: continuity, turns, admission, opening, horizon, flame/peak/dose per member, including the dwell);
* closed-footprint whole-road rule: tools/explain_deadlines/replay.py (ISSUE, EDGE, WAIT, DWELL segments).
"""
from __future__ import annotations

import sys
from fractions import Fraction as F

from .real import ROOT

sys.path.insert(0, str(ROOT / "routing-package"))
from routing.independent import check_route  # noqa: E402

from tools.explain_deadlines.replay import build_segments, first_contact  # noqa: E402


def full_check(pm, hazard, *, origin, legs, dest, dwell, window, departure, incurred=0.0, peak=10.0, dose=100.0):
    if getattr(pm, "support_masked", False):        # SUPPORT_READ_RULE.md 5 / WIDENED_GRAPH_RULE P5: never checked
        return {"full_policy_ok": False, "full_status": "REFUSED_SUPPORT_MASKED", "codes": ["REFUSED_SUPPORT_MASKED"],
                "closed_and_router_replay_clear": None, "max_dose": None}
    members = [m["id"] for m in hazard["members"]]
    request = {"position": {"node": origin}, "incoming_edge": None, "departure": departure, "horizon": pm.H,
               "destinations": [{"node": dest, "dwell": dwell, "open_intervals": [list(window)]}],
               "budgets": {"peak": peak, "dose": {m: dose for m in members}},
               "incurred": {m: incurred for m in members}, "exposure_scope": "including_dwell"}
    wl = []
    for kind, x, a, b in legs:
        if kind == "EDGE":
            wl.append({"kind": "EDGE", "edge": x, "start": a, "end": b, "from_fraction": 0, "to_fraction": 1})
        else:
            wl.append({"kind": "WAIT", "node": x, "start": a, "end": b})
    res = check_route(pm.raw, hazard, request, wl, dest)
    segs = build_segments(grid=pm.g.grid, packet=pm.pk, xy=pm.g.xy, legs=wl, edges=pm.g.edge,
                          start_node=origin, departure=departure, destination=dest, dwell=dwell)
    fc = first_contact(pm.pk, segs, F(0), pm.pk.horizon)
    return {"full_policy_ok": bool(res["ok"]), "full_status": res["status"], "codes": res["codes"],
            "closed_and_router_replay_clear": fc is None,
            "max_dose": max(float(v["dose"]) for v in res["per_member"].values()) if res.get("per_member") else None}
