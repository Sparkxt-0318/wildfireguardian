"""Independent replay of an emitted result against the raw case JSON.

This module deliberately imports nothing from the solver or the case parser: it re-reads the raw JSON dictionaries and
re-derives every rule from SCHEMA.md. Each violation carries a stable rule identifier (see CONSTRAINTS.md).
"""
from __future__ import annotations

RULES = {
    "R-SCHEMA": "result has the documented fields and types",
    "R-STATUS": "status is consistent with the trips, final_unload_s and coverage counts",
    "R-EDGE": "each edge exists and is traversed from its tail to its head",
    "R-DURATION": "exit - entry equals the edge travel_s",
    "R-CONTIG": "consecutive edges connect and the next entry is not before the previous exit",
    "R-CLOSED": "no traversal [entry, exit) has positive overlap with a closed interval",
    "R-UNKNOWN": "a checked trip has no positive overlap with an unknown interval",
    "R-HORIZON": "every exit and unloading end is <= horizon_s; no time is negative",
    "R-TURN": "no forbidden consecutive pair, including the incoming edge kept through waits and between legs",
    "R-BOARD": "boarding lasts board_s, starts no earlier than availability/return and ends by departure",
    "R-WINDOW": "outbound arrival >= window open and unloading (unload_s) ends <= window close",
    "R-CAPACITY": "people on board <= seats and equal to the group's size",
    "R-CONTINUITY": "vehicle location, clock and incoming edge carry over from trip to trip",
    "R-ASSIGN": "parallel: group i uses vehicle i once; shuttle: one vehicle, groups in listed order",
    "R-COVERAGE": "people/group counts match the witnessed outbound trips",
    "R-MISSING": "MISSING_INPUT lists every unknown interval its conditional witness touches",
}


def _overlap(ivs, entry, exit_):
    return [list(iv) for iv in ivs if max(entry, iv[0]) < min(exit_, iv[1])]


def _is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def check_trips(case, trips, *, allow_unknown, out, label="trips"):
    edges = {e["id"]: e for e in case["edges"]}
    vehicles = {v["id"]: v for v in case["vehicles"]}
    groups = {g["id"]: g for g in case["groups"]}
    H = case["horizon_s"]
    wlo, whi = case["destination_window"]
    forbidden = {tuple(p) for p in case["forbidden_turns"]}

    def bad(rule, msg, k=None):
        out.append({"rule": rule, "where": "%s[%s]" % (label, k) if k is not None else label, "detail": msg})

    by_vehicle = {}
    for k, t in enumerate(trips):
        for f in ("vehicle_id", "kind", "group_id", "people", "start_node", "end_node", "incoming_edge_at_start",
                  "ready_s", "departure_s", "arrival_s", "edges"):
            if f not in t:
                bad("R-SCHEMA", "trip lacks %s" % f, k)
                return []
        for f in ("ready_s", "departure_s", "arrival_s", "people") + (
                ("boarding_start_s", "boarding_end_s", "unloading_start_s", "unloading_end_s")
                if t.get("kind") == "outbound" else ()):
            if not _is_int(t.get(f)):
                bad("R-SCHEMA", "%s must be an integer, got %r" % (f, t.get(f)), k)
        v = vehicles.get(t["vehicle_id"])
        if v is None:
            bad("R-ASSIGN", "unknown vehicle %r" % t["vehicle_id"], k)
            continue
        by_vehicle.setdefault(t["vehicle_id"], []).append((k, t))
        outbound = t["kind"] == "outbound"
        if t["kind"] not in ("outbound", "empty_return"):
            bad("R-SCHEMA", "kind %r" % t["kind"], k)
            continue
        exp_start = case["origin"] if outbound else case["destination"]
        exp_end = case["destination"] if outbound else case["origin"]
        if t["start_node"] != exp_start or t["end_node"] != exp_end:
            bad("R-EDGE", "trip endpoints %s->%s" % (t["start_node"], t["end_node"]), k)
        if not t["edges"]:
            bad("R-EDGE", "trip has no edges", k)
            continue
        # Edge sequence
        node, clock, prev_edge = t["start_node"], t["ready_s"], t["incoming_edge_at_start"]
        if outbound:
            clock = t.get("boarding_end_s")
        for m, s in enumerate(t["edges"]):
            e = edges.get(s.get("edge_id"))
            if e is None:
                bad("R-EDGE", "unknown edge %r" % s.get("edge_id"), k)
                break
            a, b = s.get("entry_s"), s.get("exit_s")
            if not (_is_int(a) and _is_int(b)):
                bad("R-SCHEMA", "non-integer times on %s" % e["id"], k)
                break
            if e["u"] != node:
                bad("R-CONTIG", "edge %s starts at %s, vehicle is at %s" % (e["id"], e["u"], node), k)
            if clock is not None and a < clock:
                bad("R-CONTIG", "edge %s entered at %d before %d" % (e["id"], a, clock), k)
            if b - a != e["travel_s"]:
                bad("R-DURATION", "edge %s took %d s, travel_s is %d" % (e["id"], b - a, e["travel_s"]), k)
            if a < 0 or b > H:
                bad("R-HORIZON", "edge %s [%d,%d) outside [0,%d]" % (e["id"], a, b, H), k)
            hit = _overlap(e.get("closed", []), a, b)
            if hit:
                bad("R-CLOSED", "edge %s [%d,%d) overlaps closed %s" % (e["id"], a, b, hit), k)
            hitu = _overlap(e.get("unknown", []), a, b)
            if hitu and not allow_unknown:
                bad("R-UNKNOWN", "edge %s [%d,%d) overlaps unknown %s" % (e["id"], a, b, hitu), k)
            if prev_edge is not None and [prev_edge, e["id"]] in [list(p) for p in forbidden]:
                bad("R-TURN", "forbidden turn %s->%s" % (prev_edge, e["id"]), k)
            if ("from" in s and s["from"] != e["u"]) or ("to" in s and s["to"] != e["v"]):
                bad("R-EDGE", "edge %s endpoints mislabelled" % e["id"], k)
            node, clock, prev_edge = e["v"], b, e["id"]
        if node != t["end_node"]:
            bad("R-EDGE", "trip ends at %s, not %s" % (node, t["end_node"]), k)
        if t["departure_s"] != t["edges"][0]["entry_s"] or t["arrival_s"] != t["edges"][-1]["exit_s"]:
            bad("R-CONTIG", "departure/arrival differ from first entry/last exit", k)
        if t["departure_s"] < t["ready_s"]:
            bad("R-CONTIG", "departure before the vehicle is ready", k)
        if outbound:
            g = groups.get(t["group_id"])
            if g is None:
                bad("R-ASSIGN", "unknown group %r" % t["group_id"], k)
            elif t["people"] != g["people"]:
                bad("R-CAPACITY", "people %r != group size %d" % (t["people"], g["people"]), k)
            if t["people"] > v["seats"]:
                bad("R-CAPACITY", "%d people, %d seats" % (t["people"], v["seats"]), k)
            bs, be = t.get("boarding_start_s"), t.get("boarding_end_s")
            if not (_is_int(bs) and _is_int(be)) or be - bs != case["board_s"] or bs < t["ready_s"] or \
                    be > t["departure_s"]:
                bad("R-BOARD", "boarding [%r,%r) ready %d departure %d" % (bs, be, t["ready_s"], t["departure_s"]), k)
            us, ue = t.get("unloading_start_s"), t.get("unloading_end_s")
            if us != t["arrival_s"] or not _is_int(ue) or ue - us != case["unload_s"]:
                bad("R-WINDOW", "unloading [%r,%r) does not start at arrival or last unload_s" % (us, ue), k)
            if t["arrival_s"] < wlo:
                bad("R-WINDOW", "arrival %d before window opens %d" % (t["arrival_s"], wlo), k)
            if _is_int(ue) and ue > whi:
                bad("R-WINDOW", "unloading ends %d after window closes %d" % (ue, whi), k)
            if _is_int(ue) and ue > H:
                bad("R-HORIZON", "unloading ends %d after horizon %d" % (ue, H), k)
        else:
            if t["group_id"] is not None or t["people"] != 0:
                bad("R-CAPACITY", "empty return carries a group", k)

    # Continuity and assignment
    vids = [v["id"] for v in case["vehicles"]]
    gids = [g["id"] for g in case["groups"]]
    for vid, seq in by_vehicle.items():
        v = vehicles[vid]
        prev = None
        for k, t in seq:
            if prev is None:
                if t["kind"] != "outbound" or t["ready_s"] != v["available_s"] or t["start_node"] != case["origin"] \
                        or t["incoming_edge_at_start"] is not None:
                    bad("R-CONTINUITY", "first trip of %s must be outbound from origin at availability %d with no "
                                        "incoming edge" % (vid, v["available_s"]), k)
            else:
                pk, p = prev
                exp_ready = p["unloading_end_s"] if p["kind"] == "outbound" else p["arrival_s"]
                if t["kind"] == p["kind"]:
                    bad("R-CONTINUITY", "two %s trips in a row for %s" % (t["kind"], vid), k)
                if t["start_node"] != p["end_node"]:
                    bad("R-CONTINUITY", "vehicle %s teleports %s -> %s" % (vid, p["end_node"], t["start_node"]), k)
                if t["ready_s"] != exp_ready:
                    bad("R-CONTINUITY", "ready %d != previous finish %r" % (t["ready_s"], exp_ready), k)
                if p["edges"] and t["incoming_edge_at_start"] != p["edges"][-1]["edge_id"]:
                    bad("R-CONTINUITY", "incoming edge not carried over between legs", k)
            prev = (k, t)
    if case["mode"] == "parallel":
        for vid, seq in by_vehicle.items():
            if len(seq) != 1 or seq[0][1]["kind"] != "outbound":
                bad("R-ASSIGN", "parallel vehicle %s must make exactly one outbound trip" % vid)
                continue
            gi = gids.index(seq[0][1]["group_id"]) if seq[0][1]["group_id"] in gids else -1
            if gi != vids.index(vid):
                bad("R-ASSIGN", "group %r is not group #%d for vehicle %s" % (seq[0][1]["group_id"],
                                                                                vids.index(vid) + 1, vid))
    else:
        if len(by_vehicle) > 1 or (by_vehicle and list(by_vehicle) != vids[:1]):
            bad("R-ASSIGN", "shuttle uses a vehicle other than the single listed one")
        order = [t["group_id"] for _, t in by_vehicle.get(vids[0], []) if t["kind"] == "outbound"] if vids else []
        if order != gids[:len(order)]:
            bad("R-ASSIGN", "shuttle groups out of listed order: %s" % order)
    outs = [t["group_id"] for t in trips if t.get("kind") == "outbound"]
    if len(outs) != len(set(outs)):
        bad("R-COVERAGE", "a group is transported twice")
    return outs


def replay(case, result):
    """Return a list of violations (empty means the emitted witness replays cleanly)."""
    out = []
    for f in ("schema_version", "case_id", "status", "reason", "final_unload_s", "groups_total", "people_total",
              "people_with_checked_transport", "trips", "missing_information", "assumptions"):
        if f not in result:
            out.append({"rule": "R-SCHEMA", "where": "result", "detail": "missing %s" % f})
    if out:
        return out
    if result["schema_version"] != 1 or not _is_int(result["schema_version"]):
        out.append({"rule": "R-SCHEMA", "where": "result", "detail": "schema_version must be 1"})
    for f in ("groups_total", "people_total", "people_with_checked_transport"):
        if not _is_int(result[f]):
            out.append({"rule": "R-SCHEMA", "where": "result", "detail": "%s must be an integer" % f})
    if result["final_unload_s"] is not None and not _is_int(result["final_unload_s"]):
        out.append({"rule": "R-SCHEMA", "where": "result", "detail": "final_unload_s must be integer or null"})
    if not isinstance(result["reason"], str) or not result["reason"]:
        out.append({"rule": "R-SCHEMA", "where": "result", "detail": "reason must be a non-empty string"})
    for f in ("trips", "missing_information", "assumptions"):
        if not isinstance(result[f], list):
            out.append({"rule": "R-SCHEMA", "where": "result", "detail": "%s must be a list" % f})
    if out:
        return out
    if result["case_id"] != case["case_id"]:
        out.append({"rule": "R-SCHEMA", "where": "result", "detail": "case_id mismatch"})
    status = result["status"]
    if status not in ("CHECKED_ROUTE", "MISSING_INPUT", "MODEL_SCOPED_NO_ROUTE", "UNRESOLVED"):
        out.append({"rule": "R-SCHEMA", "where": "result", "detail": "status %r" % status})
    groups = {g["id"]: g for g in case["groups"]}
    covered = check_trips(case, result["trips"], allow_unknown=False, out=out)
    people = sum(groups[g]["people"] for g in covered if g in groups)
    if result["people_with_checked_transport"] != people:
        out.append({"rule": "R-COVERAGE", "where": "result", "detail": "claims %r people, witness shows %d" % (
            result["people_with_checked_transport"], people)})
    if result["groups_total"] != len(case["groups"]) or result["people_total"] != sum(
            g["people"] for g in case["groups"]):
        out.append({"rule": "R-COVERAGE", "where": "result", "detail": "totals mismatch"})
    gids = [g["id"] for g in case["groups"]]
    if "groups_with_checked_transport" in result and sorted(result["groups_with_checked_transport"]) != sorted(covered):
        out.append({"rule": "R-COVERAGE", "where": "result", "detail": "groups_with_checked_transport %r != witnessed %r"
                    % (result["groups_with_checked_transport"], covered)})
    if "groups_awaiting_checked_transport" in result and sorted(result["groups_awaiting_checked_transport"]) != sorted(
            g for g in gids if g not in covered):
        out.append({"rule": "R-COVERAGE", "where": "result", "detail": "groups_awaiting_checked_transport mismatch"})
    if "people_awaiting_checked_transport" in result and result["people_awaiting_checked_transport"] != \
            sum(g["people"] for g in case["groups"]) - people:
        out.append({"rule": "R-COVERAGE", "where": "result", "detail": "people_awaiting_checked_transport mismatch"})
    if status != "MISSING_INPUT" and ("conditional_trips" in result or "conditional_final_unload_s" in result):
        out.append({"rule": "R-MISSING", "where": "result", "detail": "conditional witness outside MISSING_INPUT"})
    if status == "CHECKED_ROUTE":
        bad_mi = [m for m in result["missing_information"] if m.get("needed_for") != "EARLIER_COMPLETION_IF_OPEN"]
        if bad_mi:
            out.append({"rule": "R-MISSING", "where": "result", "detail": "CHECKED_ROUTE lists required missing input"})
    elif status != "MISSING_INPUT" and result["missing_information"]:
        out.append({"rule": "R-MISSING", "where": "result", "detail": "%s must not list missing inputs" % status})
    if status == "CHECKED_ROUTE":
        if sorted(covered) != sorted(groups):
            out.append({"rule": "R-STATUS", "where": "result", "detail": "CHECKED_ROUTE without every group"})
        ends = [t["unloading_end_s"] for t in result["trips"] if t.get("kind") == "outbound"]
        if result["final_unload_s"] != (max(ends) if ends else None):
            out.append({"rule": "R-STATUS", "where": "result", "detail": "final_unload_s %r != last unloading %r" % (
                result["final_unload_s"], max(ends) if ends else None)})
        if case["mode"] == "shuttle":
            kinds = [t["kind"] for t in result["trips"]]
            if kinds and kinds[-1] != "outbound":
                out.append({"rule": "R-STATUS", "where": "result", "detail": "shuttle ends with a return"})
    else:
        if result["final_unload_s"] is not None:
            out.append({"rule": "R-STATUS", "where": "result", "detail": "final_unload_s must be null"})
        if sorted(covered) == sorted(groups) and groups:
            out.append({"rule": "R-STATUS", "where": "result", "detail": "all groups witnessed but not CHECKED_ROUTE"})
    if status == "MISSING_INPUT":
        cond = result.get("conditional_trips")
        if not cond:
            out.append({"rule": "R-MISSING", "where": "result", "detail": "no conditional witness"})
        else:
            sub = []
            ccov = check_trips(case, cond, allow_unknown=True, out=sub, label="conditional_trips")
            out += sub
            if sorted(ccov) != sorted(groups):
                out.append({"rule": "R-MISSING", "where": "result", "detail": "conditional witness misses a group"})
            edges = {e["id"]: e for e in case["edges"]}
            listed = set()
            for m in result["missing_information"]:
                try:
                    assert m["kind"] == "UNKNOWN_EDGE_INTERVAL" and m["needed_for"] == "ANY_FEASIBLE_SCHEDULE"
                    listed.add((m["edge_id"], tuple(m["unknown_interval"]), tuple(m["traversal"])))
                except (KeyError, TypeError, AssertionError):
                    out.append({"rule": "R-MISSING", "where": "result", "detail": "malformed entry %r" % (m,)})
            touched = set()
            for t in cond:
                for s in t["edges"]:
                    for iv in _overlap(edges[s["edge_id"]].get("unknown", []), s["entry_s"], s["exit_s"]):
                        touched.add((s["edge_id"], tuple(iv), (s["entry_s"], s["exit_s"])))
            if not touched:
                out.append({"rule": "R-MISSING", "where": "result",
                            "detail": "conditional witness touches no unknown interval, so it would be supported"})
            if touched != listed:
                out.append({"rule": "R-MISSING", "where": "result", "detail": "listed %s != touched %s" % (
                    sorted(listed - touched), sorted(touched - listed))})
    return out
