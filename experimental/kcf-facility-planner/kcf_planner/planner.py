"""Turn solver runs into the portable result contract (SCHEMA.md).

Status rules (exactly these, in this order):
  supported plan complete                                  -> CHECKED_ROUTE
  optimistic plan (unknown treated as open) proven impossible -> MODEL_SCOPED_NO_ROUTE   (also if supported unresolved)
  supported proven impossible and optimistic complete       -> MISSING_INPUT
  anything else (cap or deadline before a proof)            -> UNRESOLVED
Supported search treats every `unknown` interval as blocking; optimistic search treats it as open. Because the
optimistic model only removes restrictions, an optimistic impossibility proof is also a supported one.
"""
from __future__ import annotations

import time

from . import solver as S
from .model import SCHEMA_VERSION

RESULT_SCHEMA = 1
TOOL = "kcf-facility-planner/1"

BASE_ASSUMPTIONS = [
    "All times are integer seconds from the exercise origin; travel on an edge occupies [entry, exit).",
    "An edge may not be entered if [entry, exit) has positive-duration overlap with a closed interval; supported "
    "(checked) schedules also avoid every unknown interval. Unlisted times within the horizon are known and open.",
    "Every journey leg must finish by horizon_s; unloading must finish by min(destination window close, horizon_s). "
    "Completion exactly at the horizon or window close is allowed.",
    "Waiting is allowed at every node and keeps the incoming edge, so forbidden turns apply after waits and between "
    "shuttle legs. Nodes are assumed supported and open in this contract.",
    "A destination arrival counts only as an edge arrival inside the window; waiting at the destination is not an "
    "arrival.",
    "Boarding takes board_s at the origin and starts no earlier than vehicle availability (or its return). Boarding "
    "is placed to end exactly at departure, so any hold happens at the facility before residents board.",
    "Parallel mode: group i uses vehicle i, one trip, no return. Shuttle mode: one vehicle serves groups in listed "
    "order with empty returns; no other vehicle is introduced.",
    "No road capacity, vehicle interaction, destination capacity, driver availability, loading variability, heat "
    "exposure, smoke or physical road status is modelled.",
]


def _missing_from_trips(case, trips, label):
    by_id = case.edge_by_id
    out = []
    for t in trips:
        for e in t["edges"]:
            # Report intervals exactly as listed in the input (not merged), so a person can find each one.
            for a, b in S.overlapping(by_id[e["edge_id"]].unknown_raw, e["entry_s"], e["exit_s"]):
                out.append({"kind": "UNKNOWN_EDGE_INTERVAL", "edge_id": e["edge_id"], "unknown_interval": [a, b],
                            "traversal": [e["entry_s"], e["exit_s"]], "vehicle_id": t["vehicle_id"],
                            "group_id": t["group_id"], "trip_kind": t["kind"], "needed_for": label})
    return out


def _number(trips):
    for k, t in enumerate(trips, 1):
        t["trip_id"] = "T%d" % k
    return trips


def _chain_trips(p):
    return [t for c in p["chains"] for t in c["trips"]]


def solve_case(case, *, max_labels=2_000_000, time_limit_s=None, diagnostics=True):
    t0 = time.perf_counter()
    budget = S.Budget(max_labels, time_limit_s)
    sup = opt = None
    cap_note = None
    try:
        sup = S.plan(case, "supported", budget)
        opt = S.plan(case, "optimistic", budget)
    except S.CapReached as exc:
        cap_note = str(exc)
    ws, wo = S.whole(sup), S.whole(opt)
    if ws == "FOUND":
        status = "CHECKED_ROUTE"
    elif wo == "INFEASIBLE":
        status = "MODEL_SCOPED_NO_ROUTE"
    elif ws == "INFEASIBLE" and wo == "FOUND":
        status = "MISSING_INPUT"
    else:
        status = "UNRESOLVED"

    people_total = sum(g.people for g in case.groups)
    groups_by_id = {g.id: g for g in case.groups}
    trips = _number(_chain_trips(sup)) if sup is not None else []
    covered = [t["group_id"] for t in trips if t["kind"] == "outbound"]
    checked_people = sum(groups_by_id[gid].people for gid in covered)
    missing, assumptions = [], list(BASE_ASSUMPTIONS) + list(case.notes)
    reason_codes, diag = [], []
    result_extra = {}

    if status == "CHECKED_ROUTE":
        final = max(c["final_unload_s"] for c in sup["chains"]) if sup["chains"] else None
        reason = "Every group has a fully supported legal schedule; final unloading at %ss." % final
        reason_codes.append("ALL_GROUPS_SUPPORTED")
        if wo == "FOUND":
            ofinal = max(c["final_unload_s"] for c in opt["chains"]) if opt["chains"] else None
            if ofinal is not None and final is not None and ofinal < final:
                otrips = _chain_trips(opt)
                missing += _missing_from_trips(case, otrips, "EARLIER_COMPLETION_IF_OPEN")
                result_extra["optimistic_final_unload_s"] = ofinal
                reason_codes.append("UNKNOWN_INPUT_COULD_ALLOW_EARLIER")
    else:
        final = None
        if status == "MISSING_INPUT":
            # Rely on unknown inputs only where needed: a chain (vehicle) that already has a supported schedule keeps
            # it; only the chains without one use the optimistic witness. Chains are independent in parallel mode;
            # shuttle mode has a single chain.
            mixed = [sc if sc["status"] == "FOUND" else oc for sc, oc in zip(sup["chains"], opt["chains"])]
            otrips = _number([t for c in mixed for t in c["trips"]])
            missing += _missing_from_trips(case, otrips, "ANY_FEASIBLE_SCHEDULE")
            result_extra["conditional_trips"] = otrips
            result_extra["conditional_final_unload_s"] = max(c["final_unload_s"] for c in mixed)
            reason_codes.append("FEASIBLE_ONLY_IF_UNKNOWN_OPEN")
            reason = ("No fully supported schedule exists; a schedule exists only if the listed unknown intervals are "
                      "open. A person must obtain those inputs before relying on it.")
        elif status == "MODEL_SCOPED_NO_ROUTE":
            codes, text = _no_route_reasons(case, opt, sup, diagnostics, diag, max_labels,
                                            None if budget.deadline is None else budget.deadline)
            reason_codes += codes
            reason = text
        else:
            reason_codes.append("SEARCH_CAP" if cap_note else "PROOF_INCOMPLETE")
            reason = ("Search stopped before a proof (%s); this is not evidence that no route exists." %
                      (cap_note or "incomplete"))
        # Partial coverage is claimed only with a supported witness.
        if checked_people:
            reason_codes.append("PARTIAL_SUPPORTED_COVERAGE")

    chain_failures = []
    for p, view in ((sup, "supported"), (opt, "optimistic")):
        if p is None:
            continue
        for c in p["chains"]:
            if c["failure"]:
                f = dict(c["failure"])
                f["view"] = view
                f["vehicle_id"] = c["vehicle_id"]
                chain_failures.append(f)
        for gid in p["unassigned"]:
            chain_failures.append({"code": "NO_VEHICLE_ASSIGNED", "group_id": gid, "view": view,
                                   "detail": "parallel mode has no vehicle %d for group %s" % (
                                       [g.id for g in case.groups].index(gid) + 1, gid)})

    awaiting = [g.id for g in case.groups if g.id not in covered]
    result = {
        "schema_version": RESULT_SCHEMA,
        "case_id": case.case_id,
        "status": status,
        "reason": reason,
        "reason_codes": reason_codes,
        "final_unload_s": final,
        "groups_total": len(case.groups),
        "people_total": people_total,
        "people_with_checked_transport": checked_people,
        "groups_with_checked_transport": covered,
        "groups_awaiting_checked_transport": awaiting,
        "people_awaiting_checked_transport": people_total - checked_people,
        "mode": case.mode,
        "trips": trips,
        "missing_information": missing,
        "assumptions": assumptions,
        "failures": chain_failures,
        "diagnostics": diag,
        "search": {"settled_labels": budget.used, "label_cap": max_labels, "time_limit_s": time_limit_s,
                   "cap_reached": cap_note is not None, "supported_view": ws, "optimistic_view": wo},
        "tool": TOOL,
        "input_schema_version": SCHEMA_VERSION,
        "wall_s": round(time.perf_counter() - t0, 6),
    }
    result.update(result_extra)
    return result


def _no_route_reasons(case, opt, sup, diagnostics, diag, max_labels=2_000_000, deadline=None):
    codes = []
    fails = [c["failure"] for c in opt["chains"] if c["failure"]]
    if opt["unassigned"]:
        codes.append("NO_VEHICLE_ASSIGNED")
    if any(f["code"] == "CAPACITY" for f in fails):
        codes.append("CAPACITY")
    wlo, whi = case.window
    if min(whi, case.horizon_s) - case.unload_s < wlo:
        codes.append("DESTINATION_WINDOW_TOO_SHORT")
    if any(f["code"] == "NO_ADMISSIBLE_LEG" for f in fails) and diagnostics:
        # Counterfactual diagnostics: clearly hypothetical, never a schedule.
        n_legs = 2 * max(1, len(case.groups))
        span = max([case.horizon_s, whi] + [v.available_s for v in case.vehicles] +
                   [b for e in case.edges for _, b in e.closed + e.unknown])
        ext = span + n_legs * (sum(e.travel_s for e in case.edges) + case.board_s + case.unload_s) + 1
        tests = [
            ("HORIZON_EXTENDED", "optimistic", ext, None),
            ("HORIZON_AND_WINDOW_EXTENDED", "optimistic", ext, (wlo, ext)),
            ("CLOSURES_REMOVED", "topology", None, None),
            ("CLOSURES_REMOVED_HORIZON_WINDOW_EXTENDED", "topology", ext, (wlo, ext)),
        ]
        found = {}
        for name, view, hor, win in tests:
            try:
                # Same label cap and the remaining wall-clock allowance as the main search.
                b = S.Budget(max_labels)
                b.deadline = deadline
                if deadline is not None and time.perf_counter() > deadline:
                    raise S.CapReached("time limit reached before diagnostics")
                p = S.plan(case, view, b, horizon=hor, window=win, shift=False)
                w = S.whole(p)
            except S.CapReached:
                w = "UNKNOWN"
            found[name] = w
            diag.append({"counterfactual": name, "view": view, "horizon_s": hor, "window": list(win) if win else None,
                         "outcome": w, "hypothetical": True,
                         "note": "Counterfactual only: times beyond the horizon are outside the model and are not "
                                 "evidence that a road is open."})
        if found["HORIZON_EXTENDED"] == "FOUND":
            codes.append("OUT_OF_HORIZON")
        if found["CLOSURES_REMOVED"] == "FOUND":
            codes.append("CLOSURES_BLOCK_ALL_ROUTES")
        if found["HORIZON_EXTENDED"] != "FOUND" and found["HORIZON_AND_WINDOW_EXTENDED"] == "FOUND" and \
                "DESTINATION_WINDOW_TOO_SHORT" not in codes:
            codes.append("DESTINATION_WINDOW")
        if any(v == "UNKNOWN" for v in found.values()):
            codes.append("DIAGNOSTICS_INCOMPLETE")
        elif not any(c in codes for c in ("OUT_OF_HORIZON", "CLOSURES_BLOCK_ALL_ROUTES", "DESTINATION_WINDOW",
                                        "DESTINATION_WINDOW_TOO_SHORT", "CAPACITY", "NO_VEHICLE_ASSIGNED")):
            if found["CLOSURES_REMOVED_HORIZON_WINDOW_EXTENDED"] == "FOUND":
                codes.append("CLOSURES_AND_TIME_LIMITS")
            else:
                codes.append("NO_PATH_IN_ROAD_MODEL")
    elif any(f["code"] == "NO_ADMISSIBLE_LEG" for f in fails):
        codes.append("NO_ADMISSIBLE_LEG")
    text = {
        "NO_VEHICLE_ASSIGNED": "a group has no vehicle in parallel mode (no vehicle is added silently)",
        "CAPACITY": "a group exceeds its vehicle's seats",
        "DESTINATION_WINDOW_TOO_SHORT": "the destination window cannot fit unloading",
        "OUT_OF_HORIZON": "a schedule would need time beyond horizon_s, which is outside the model",
        "DESTINATION_WINDOW": "every schedule would arrive or finish unloading after the destination window closes",
        "CLOSURES_BLOCK_ALL_ROUTES": "the closed intervals block every route within the horizon and window",
        "CLOSURES_AND_TIME_LIMITS": "closures combined with the horizon/window leave no schedule",
        "NO_PATH_IN_ROAD_MODEL": "no road sequence (with the turn rules) reaches the required node",
        "NO_ADMISSIBLE_LEG": "no admissible leg exists",
        "DIAGNOSTICS_INCOMPLETE": "the explanation search hit its cap, so the specific cause is not determined (the "
                                  "no-route result itself is proved)",
    }
    reason = ("No legal schedule exists in this model even if every unknown interval were open: " +
              "; ".join(text[c] for c in codes if c in text) + ". This is model-scoped, not a statement about real "
              "roads.")
    return codes, reason
