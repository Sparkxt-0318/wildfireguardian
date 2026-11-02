"""Per-origin deadline explanations (schema wfg.explanation/1). See README.md for the rules; summary:

checked origin, deadline D (planner's 출발 마감) and the next attempted offset N = D + delta:
  * no later offset                         -> no_later_offset            (explained)
  * N is a "시간창 밖" cell (research mission)  -> window                    (explained; zero-travel rule)
  * N unresolved                            -> unresolved_next            (not_explainable; never turned into a reason)
  * N model_no_route: for every shelter with a checked route at D (the set C_D), the first class that holds at N:
      - fire-free fastest road journey from N cannot finish the stay in the window          -> window_fire_free
      - the route checked at D, replayed rigidly shifted to N, meets flame first on a
        moving segment (closed-footprint or router rule, any member)                       -> flame_on_route
      - no flame-avoiding relaxed journey (reach.py) arrives by close - dwell                -> window_fire_detour
      - the shifted route first meets flame during its stay                                 -> dwell
      - every stay [a, a + dwell] the relaxation allows meets flame                          -> stay_blocked_without_shown_route_contact
      - else                                                                                  -> open
    shelters tried at N without a checked route at D get window_fire_free / flame_blocked / stay_blocked / open;
    a shelter is PROVEN unreachable at N when window_fire_free, the relaxation is late, or every stay meets flame.
    deadline_cause over all shelters considered: time_window when none can be reached in time even without fire,
    flames when one would be reached by a fire-free road but is proven unreachable on every flame-avoiding road.
    The origin's reason follows the shown route's class (window_fire_free -> window when the cause is time_window,
    no_flame_avoiding_route / other_shelters_flame_blocked when it is flames; window_fire_detour ->
    no_flame_avoiding_route); explained when every shelter considered is proven and the cause is established.
model_no_route origin: every attempted (offset, shelter) must be proven by the relaxation without turn restrictions;
  none reachable in time even without fire -> window (no_route_even_without_fire); otherwise all shelters
  unreachable within the hazard window and the flame-free area closed by flame -> all_exits_blocked (exits = roads
  leaving that area), else no_flame_avoiding_route. Unresolved origin -> not_explainable.
"""
from __future__ import annotations

import collections
import json
from dataclasses import dataclass, field
from fractions import Fraction as F

from .labels import PlaceIndex, label_for
from .packet import Packet
from .plans import CacheModel, OriginPlan, RouteError, reconstruct_legs, tie_at
from .reach import ContactIndex, dwell_free_arrival, earliest_free, flame_avoiding
from .replay import build_segments, first_contact, any_contact, segment_contact
from .roads import RoadGraph

SCHEMA = "wfg.explanation/1"
STATUSES = ("explained", "explained_partial", "not_explainable")
REASONS = ("flame_on_route", "no_flame_avoiding_route", "all_exits_blocked", "dwell_at_destination", "unresolved_next",
           "window", "no_later_offset", "other")


def r1(x) -> float:
    """Round a time (Fraction/float) to 0.1 s for output."""
    return round(float(x), 1)


@dataclass
class Context:
    region_id: str
    input_time: str
    scenario_set_id: str
    graph: RoadGraph
    packet: Packet
    index: ContactIndex
    places: PlaceIndex | None
    model: CacheModel
    to_lonlat: object            # (x, y) EPSG:5179 -> (lon, lat)
    horizon: int


@dataclass
class Evidence:
    """Everything the validator needs to re-check one explanation (not written to the JSON)."""
    origin_id: str
    deadline_routes: list = field(default_factory=list)   # [(destination_id, job_id, route, segs, request)]
    shift: F | None = None
    binding_checks: list = field(default_factory=list)    # [(segs, segment_index, members, slack_exact, shift)]
    window_proofs: list = field(default_factory=list)     # [dict]
    exits_proof: dict | None = None
    times: list = field(default_factory=list)             # every event timestamp reported (exact or float)


def _job_request(job: dict) -> dict:
    req = job.get("request") or {}
    win = req.get("destination_window")
    return {"start": req["start"]["node_id"], "destination": req["destination"]["node_id"],
            "dwell": int(req.get("dwell_s", 120)), "open": int(float(win[0])) if win else 0,
            "close": int(float(win[1])) if win else None, "offset": int(float(req.get("depart_offset_s", 0)))}


def _close(ctx: Context, req: dict) -> int:
    return min(req["close"], ctx.horizon) if req["close"] is not None else ctx.horizon


def _members(ctx: Context, idx) -> list:
    return sorted(ctx.packet.member_label(s) for s in idx)


def _point_label(ctx: Context, p0, p1, u: F, node_id: str) -> dict:
    x = float(p0[0] + u * (p1[0] - p0[0]))
    y = float(p0[1] + u * (p1[1] - p0[1]))
    lab = label_for(ctx.places, x, y, node_id)
    lon, lat = ctx.to_lonlat(x, y)
    lab["point"] = [round(lon, 6), round(lat, 6)]
    return lab


def _way(ctx: Context, edge_id: str):
    w = ctx.graph.source_way[ctx.graph.edge_index[edge_id]]
    return int(w) if isinstance(w, (int, float)) else None


# ------------------------------------------------------------------------------------------------ binding items
def _binding_item(ctx: Context, segs: list, sc, shift: F, destination_ids: list) -> tuple:
    """Item for the first contact segment ``sc`` (closed-rule pairs at ``shift``). Returns (item, check)."""
    seg = sc.segment
    kind = seg.kind.lower()
    # the road of the item: the segment's own edge; the next edge for the issue point or a wait; the arriving edge
    # for the destination stay
    if seg.kind == "EDGE":
        edge_seg = seg
    elif seg.kind in ("ISSUE", "WAIT"):
        edge_seg = next((s for s in segs[seg.index:] if s.kind == "EDGE"), None)
    else:
        edge_seg = next((s for s in reversed(segs[:seg.index]) if s.kind == "EDGE"), None)
    pairs = sc.pairs
    # slack: smallest (birth - leave_at_D) over the contact pairs; the pair also gives flame and pass times
    best = min(pairs, key=lambda p: (p[3] - p[5], p[0], p[1]))
    slack = best[3] - best[5]
    contact_time = min(p[2] for p in pairs)
    witness = min(pairs, key=lambda p: (p[2], p[0], p[1]))
    # label at the witness point (where the shifted journey first meets flame)
    if seg.end > seg.start:
        u = (witness[2] - (seg.start + shift)) / (seg.end - seg.start)
    else:
        u = F(0)
    u = min(max(u, F(0)), F(1))
    node_for_label = (seg.node if seg.node else ctx.graph.u[ctx.graph.edge_index[seg.edge]])
    lab = _point_label(ctx, seg.p0, seg.p1, u, node_for_label)
    item = {"edge_id": edge_seg.edge if edge_seg else None, "osm_way_id": _way(ctx, edge_seg.edge) if edge_seg else None,
            **lab, "flame_time_s": r1(best[3]), "contact_time_s": r1(contact_time),
            "members": _members(ctx, {p[0] for p in pairs}), "members_total": ctx.packet.S,
            "pass_time_at_deadline_s": r1(best[5]), "slack_s": r1(slack), "segment": kind,
            "leg_index": seg.leg_index, "destination_ids": sorted(destination_ids),
            "rules": {"closed_footprint": bool(pairs), "router_cells": bool(sc.router_members)},
            # router-grid cells of the earliest contact at N and of the smallest margin at D (pass/flame/slack refer to it)
            "contact_cell": witness[1], "slack_cell": best[1]}
    member_times = {}
    for p in pairs:
        member_times[p[0]] = min(member_times.get(p[0], p[2]), p[2])
    check = {"segs": segs, "segment_index": seg.index, "members": {p[0] for p in pairs}, "slack": slack, "shift": shift,
             "times": [best[3], contact_time, best[5]], "member_times": member_times}
    return item, check


# ------------------------------------------------------------------------------------------------ checked origins
def _analyse_destination(ctx: Context, attempt, next_offset: int, delta: F, ev: Evidence, notes: list) -> dict:
    job = ctx.model.job(attempt.job_id)
    if job is None:
        return {"cls": "unknown", "proven": False, "why": "route_check_job_missing"}
    try:
        route = reconstruct_legs(job)
    except (RouteError, KeyError, TypeError, ValueError) as exc:
        return {"cls": "unknown", "proven": False, "why": "route_reconstruction_failed: %s" % exc}
    req = _job_request(job)
    close = _close(ctx, req)
    g = ctx.graph
    segs = build_segments(grid=g.grid, packet=ctx.packet, xy=g.xy, legs=route["legs"], edges=g.edge,
                          start_node=route["start_node"], departure=route["departure"], destination=route["destination"],
                          dwell=req["dwell"])
    ev.deadline_routes.append((attempt.destination_id, attempt.job_id, route, segs, req))
    c0 = any_contact(ctx.packet, segs, F(0), F(ctx.horizon))
    if c0:
        notes.append("CONTRADICTION: checked route %s has flame contact at its recorded time" % attempt.job_id)
        return {"cls": "unknown", "proven": False, "why": "recorded_route_contact"}
    fast = g.fastest_ticks(req["start"], [req["destination"]], max_ticks=ctx.horizon)[req["destination"]]
    fire_free_late = fast is None or next_offset + fast + req["dwell"] > close
    relax = flame_avoiding(ctx.index, req["start"], next_offset, [req["destination"]], close - req["dwell"])
    ea = relax["arrival"][req["destination"]]
    relax_late = ea is None
    dwell_blocked = False
    if not fire_free_late and not relax_late:
        dwell_blocked = dwell_free_arrival(ctx.index, req["destination"], ea, close - req["dwell"], req["dwell"]) is None
    # earliest flame-avoiding arrival within the whole hazard window (reported only; None = not reachable by then)
    relax_h = flame_avoiding(ctx.index, req["start"], next_offset, [req["destination"]], ctx.horizon)
    ea_h = relax_h["arrival"][req["destination"]]
    fc = first_contact(ctx.packet, segs, delta, F(ctx.horizon))
    if fc is not None and not fc.router_members <= {p[0] for p in fc.pairs}:
        notes.append("CONTRADICTION: router-rule contact without closed-rule contact on %s" % attempt.job_id)
        return {"cls": "unknown", "proven": False, "why": "rule_subset_violation"}
    if fire_free_late:
        cls = "window_fire_free"
    elif fc is not None and fc.segment.kind != "DWELL":
        cls = "flame_on_route"
    elif relax_late:
        cls = "window_fire_detour"
    elif fc is not None and fc.segment.kind == "DWELL":
        cls = "dwell"
    elif dwell_blocked:
        cls = "stay_blocked_without_shown_route_contact"     # proven, but not localised on the shown route
    else:
        cls = "open"
    proven = fire_free_late or relax_late or dwell_blocked
    ev.window_proofs.append({"destination_id": attempt.destination_id, "start": req["start"], "destination": req["destination"],
                             "next": next_offset, "dwell": req["dwell"], "close": close, "fastest_ticks": fast,
                             "fire_free_late": fire_free_late, "relax_late": relax_late, "dwell_blocked": dwell_blocked,
                             "relax_arrival": ea})
    return {"cls": cls, "proven": proven, "segs": segs, "first": fc, "route": route, "req": req, "close": close,
            "fastest_ticks": fast, "fire_free_late": fire_free_late, "relax_late": relax_late, "dwell_blocked": dwell_blocked,
            "flame_avoiding_arrival_h": ea_h, "job": job}


def _analyse_refused(ctx: Context, attempt, next_offset: int, ev: Evidence) -> dict:
    """A shelter tried at N that had no checked route at D (refused there too): whether a fire-free road would still
    reach it in time from N and, if so, whether the flame-avoiding relaxation proves it unreachable (or every stay it
    allows meets flame)."""
    job = ctx.model.job(attempt.job_id)
    if job is None:
        return {"cls": "unknown", "proven": False, "why": "route_check_job_missing"}
    try:
        req = _job_request(job)
    except (KeyError, TypeError, ValueError):
        return {"cls": "unknown", "proven": False, "why": "request_unreadable"}
    close = _close(ctx, req)
    g = ctx.graph
    fast = g.fastest_ticks(req["start"], [req["destination"]], max_ticks=ctx.horizon)[req["destination"]]
    fire_free_late = fast is None or next_offset + fast + req["dwell"] > close
    relax_late = dwell_blocked = False
    ea = ea_h = None
    if not fire_free_late:
        ea = flame_avoiding(ctx.index, req["start"], next_offset, [req["destination"]], close - req["dwell"])["arrival"][req["destination"]]
        relax_late = ea is None
        if not relax_late:
            dwell_blocked = dwell_free_arrival(ctx.index, req["destination"], ea, close - req["dwell"], req["dwell"]) is None
        ea_h = flame_avoiding(ctx.index, req["start"], next_offset, [req["destination"]], ctx.horizon)["arrival"][req["destination"]]
    cls = "window_fire_free" if fire_free_late else "flame_blocked" if relax_late else "stay_blocked" if dwell_blocked else "open"
    ev.window_proofs.append({"destination_id": attempt.destination_id, "start": req["start"], "destination": req["destination"],
                             "next": next_offset, "dwell": req["dwell"], "close": close, "fastest_ticks": fast,
                             "fire_free_late": fire_free_late, "relax_late": relax_late, "dwell_blocked": dwell_blocked,
                             "relax_arrival": ea})
    return {"cls": cls, "proven": fire_free_late or relax_late or dwell_blocked, "req": req, "close": close,
            "fastest_ticks": fast, "fire_free_late": fire_free_late, "relax_late": relax_late, "dwell_blocked": dwell_blocked,
            "flame_avoiding_arrival_h": ea_h}


def _shelter_record(destination_id: str, r: dict, next_offset: int, checked_at_deadline: bool, tried_next: bool) -> dict:
    """Per-shelter facts at N for the JSON (`shelters_next`)."""
    req, fast = r.get("req"), r.get("fastest_ticks")
    known = req is not None and r.get("fire_free_late") is not None
    return {"destination_id": destination_id, "checked_at_deadline": checked_at_deadline, "tried_next": tried_next,
            "class": r["cls"], "proven": bool(r["proven"]), "close_s": r.get("close"),
            "dwell_s": req["dwell"] if req else None,
            "fire_free_fits": (not r["fire_free_late"]) if known else None,
            "fire_free_end_s": next_offset + fast + req["dwell"] if (known and fast is not None) else None,
            "flame_avoiding_arrival_s": r.get("flame_avoiding_arrival_h")}


def _explain_checked(ctx: Context, plan: OriginPlan, rec: dict, ev: Evidence) -> None:
    D = plan.latest_s
    rec["deadline_offset_s"] = D
    later = [c for c in plan.sweep if c.offset_s > D]
    dcell = next(c for c in plan.sweep if c.offset_s == D)
    best = dcell.best
    rec["deadline_route"] = _deadline_route(ctx, best)
    if tie_at(dcell.attempts):
        rec["notes"].append("tie_on_arrival_at_deadline")
    if not later:
        rec.update(status="explained", reason_code="no_later_offset", next_offset_s=None, next_verdict=None,
                   detail_code="last_checked_offset")
        rec["window"] = {"close_s": ctx.horizon, "fire_free": None, "fastest_end_s": None, "flame_avoiding_arrival_s": None}
        # still verify the deadline route against the packet (assertion a: no contact at D)
        _verify_deadline_routes(ctx, dcell, ev, rec)
        return
    nxt = later[0]
    rec["next_offset_s"] = nxt.offset_s
    ev.times += [D, nxt.offset_s]
    if nxt.skipped == "window_unsatisfiable" and not nxt.attempts:
        rec["next_verdict"] = "window"
        job = ctx.model.job(best.job_id)
        if job is None:
            rec.update(status="not_explainable", reason_code="other", detail_code="route_check_job_missing")
            return
        req = _job_request(job)
        close = _close(ctx, req)
        rec.update(status="explained", reason_code="window", detail_code="outside_recorded_arrival_window")
        rec["window"] = {"open_s": req["open"], "close_s": close, "dwell_s": req["dwell"], "fire_free": True,
                         "fastest_end_s": None, "flame_avoiding_arrival_s": None}
        ev.window_proofs.append({"zero_travel": True, "next": nxt.offset_s, "open": req["open"], "close": close, "dwell": req["dwell"]})
        _verify_deadline_routes(ctx, dcell, ev, rec)
        return
    rec["next_verdict"] = nxt.verdict
    if nxt.verdict == "unresolved":
        rec.update(status="not_explainable", reason_code="unresolved_next", detail_code="next_offset_unresolved",
                   next_attempt_verdicts=_verdict_counts(nxt.attempts))
        _verify_deadline_routes(ctx, dcell, ev, rec)
        return
    if nxt.verdict != "model_no_route":       # cannot happen: D is the latest checked offset
        raise AssertionError("next cell after the deadline is %s" % nxt.verdict)
    delta = F(nxt.offset_s - D)
    ev.shift = delta
    checked = [a for a in dcell.attempts if a.verdict == "checked_route"]
    results = {a.destination_id: _analyse_destination(ctx, a, nxt.offset_s, delta, ev, rec["notes"]) for a in checked}
    # shelters tried at N without a checked route at D were refused at D as well; they do not explain the change from
    # D to N, but they decide whether the fire is what keeps a later departure from working (deadline_cause)
    extra = {}
    for a in nxt.attempts:
        if a.destination_id not in results and a.destination_id not in extra:
            extra[a.destination_id] = _analyse_refused(ctx, a, nxt.offset_s, ev)
    considered = {**results, **extra}
    tried = {a.destination_id for a in nxt.attempts}
    rec["checked_at_deadline"] = len(checked)
    rec["proven_unreachable_next"] = sum(1 for r in results.values() if r["proven"])
    rec["next_attempts"] = dict(sorted(collections.Counter(a.verdict for a in nxt.attempts).items()))
    rec["destination_classes"] = {d: r["cls"] for d, r in sorted(results.items())}
    rec["shelters_next"] = [_shelter_record(d, considered[d], nxt.offset_s, d in results, d in tried) for d in sorted(considered)]
    shown = results[best.destination_id]
    cls = shown["cls"]
    if shown.get("req"):
        rec["window"] = {"close_s": shown["close"], "dwell_s": shown["req"]["dwell"], "fire_free": bool(shown["fire_free_late"]),
                         "fastest_end_s": None if shown["fastest_ticks"] is None else nxt.offset_s + shown["fastest_ticks"] + shown["req"]["dwell"],
                         "flame_avoiding_arrival_s": shown["flame_avoiding_arrival_h"]}
    # what keeps a later departure from working, over every shelter considered at N (checked at D or tried at N):
    #   time_window -- none of them can be reached in time at N even without fire;
    #   flames      -- at least one would be reached in time by a fire-free road but is proven unreachable on every
    #                  flame-avoiding road (so without the fire a later departure would work);
    #   None        -- not established
    all_out_of_window = all(r.get("fire_free_late") is True for r in considered.values())
    fire_limited = sorted(d for d, r in considered.items() if r.get("fire_free_late") is False and r["proven"])
    cause = "time_window" if all_out_of_window else "flames" if fire_limited else None
    rec["deadline_cause"] = cause
    if cls == "window_fire_free":
        if cause == "time_window":
            rec.update(reason_code="window", detail_code="window_fire_free")
        elif cause == "flames":
            # the shown shelter is out of reach even without fire, other shelters only because of the flames
            rec.update(reason_code="no_flame_avoiding_route", detail_code="other_shelters_flame_blocked")
        else:
            rec.update(reason_code="window", detail_code="window_fire_free")
    elif cls == "window_fire_detour":
        rec.update(reason_code="no_flame_avoiding_route", detail_code="window_fire_detour")
    elif cls == "flame_on_route":
        rec.update(reason_code="flame_on_route", detail_code="route_meets_flame_when_shifted")
        # one item per distinct first contact among the routes checked at D (the shown route's item first)
        order = [best.destination_id] + sorted(d for d in results if d != best.destination_id)
        seen = {}
        for d in order:
            r = results[d]
            if r["cls"] != "flame_on_route":
                continue
            item, check = _binding_item(ctx, r["segs"], r["first"], delta, [d])
            check["destination_id"] = d
            ev.binding_checks.append(check)          # every route's claim is validated, merged or not
            ev.times += check["times"]
            # merge two routes only when every field of their items is identical (same road, times, members, leg)
            key = json.dumps({k: v for k, v in item.items() if k != "destination_ids"}, sort_keys=True)
            if key in seen:
                seen[key]["destination_ids"].append(d)
                continue
            seen[key] = item
            rec["binding"].append(item)
        for item in rec["binding"]:
            item["destination_ids"] = sorted(item["destination_ids"])
    elif cls == "dwell":
        rec.update(reason_code="dwell_at_destination", detail_code="stay_meets_flame")
        fc = shown["first"]
        if fc is not None and fc.segment.kind == "DWELL":
            item, check = _binding_item(ctx, shown["segs"], fc, delta, [best.destination_id])
            check["destination_id"] = best.destination_id
            rec["binding"].append(item)
            ev.binding_checks.append(check)
            ev.times += check["times"]
    else:
        rec.update(reason_code="other", detail_code="refusal_not_reproduced" if cls == "open" else (shown.get("why") or cls))
    if rec["reason_code"] == "other":
        rec["status"] = "not_explainable"
    elif rec["reason_code"] == "dwell_at_destination" or cause is None or not all(r["proven"] for r in considered.values()):
        rec["status"] = "explained_partial"
    else:
        rec["status"] = "explained"


def _deadline_route(ctx: Context, best) -> dict | None:
    job = ctx.model.job(best.job_id) if best else None
    if job is None:
        return None
    res = job.get("result") or {}
    req = job.get("request") or {}
    return {"route_check_job_id": best.job_id, "destination_id": best.destination_id,
            "departure_s": res.get("departure_s"), "arrival_s": res.get("arrival_s"), "dwell_s": req.get("dwell_s"),
            "route_sha256": ((res.get("route") or {}).get("properties") or {}).get("route_sha256"),
            "raw_status": res.get("raw_status")}


def _verify_deadline_routes(ctx: Context, dcell, ev: Evidence, rec: dict) -> None:
    """Assertion (a) material for deadlines explained without a replay: rebuild every route checked at D."""
    g = ctx.graph
    for a in dcell.attempts:
        if a.verdict != "checked_route":
            continue
        job = ctx.model.job(a.job_id)
        try:
            route = reconstruct_legs(job)
        except (RouteError, KeyError, TypeError, ValueError):
            rec["notes"].append("route_reconstruction_failed:%s" % a.job_id)
            continue
        req = _job_request(job)
        segs = build_segments(grid=g.grid, packet=ctx.packet, xy=g.xy, legs=route["legs"], edges=g.edge,
                              start_node=route["start_node"], departure=route["departure"], destination=route["destination"],
                              dwell=req["dwell"])
        ev.deadline_routes.append((a.destination_id, a.job_id, route, segs, req))


# ------------------------------------------------------------------------------------------------ no-route origins
def _explain_no_route(ctx: Context, plan: OriginPlan, rec: dict, ev: Evidence) -> None:
    attempts = [a for c in plan.sweep for a in c.attempts]
    reqs = []
    for a in attempts:
        job = ctx.model.job(a.job_id)
        if job is None:
            rec.update(status="not_explainable", reason_code="other", detail_code="route_check_job_missing")
            return
        reqs.append((a, _job_request(job)))
    starts = {r["start"] for _, r in reqs}
    if len(starts) != 1:
        rec.update(status="not_explainable", reason_code="other", detail_code="several_start_nodes")
        return
    start = starts.pop()
    proven, unreachable, out_of_window = True, True, True
    for a, r in reqs:
        close = _close(ctx, r)
        fast = ctx.graph.fastest_ticks(start, [r["destination"]], max_ticks=ctx.horizon)[r["destination"]]
        ff_late = fast is None or a.offset_s + fast + r["dwell"] > close
        out_of_window &= ff_late
        late = flame_avoiding(ctx.index, start, a.offset_s, [r["destination"]], close - r["dwell"], turns=False)
        anytime = flame_avoiding(ctx.index, start, a.offset_s, [r["destination"]], ctx.horizon, turns=False)
        ok_late = late["arrival"][r["destination"]] is None
        ok_any = anytime["arrival"][r["destination"]] is None
        ev.window_proofs.append({"no_route_attempt": True, "start": start, "destination": r["destination"], "offset": a.offset_s,
                                 "dwell": r["dwell"], "close": close, "late": ok_late, "unreachable": ok_any,
                                 "fastest_ticks": fast, "fire_free_late": ff_late})
        proven &= ok_late
        unreachable &= ok_any
    t0 = min(a.offset_s for a, _ in reqs)
    rec["first_offset_s"] = t0
    if not proven:
        rec.update(status="not_explainable", reason_code="other", detail_code="refusal_not_reproduced")
        return
    window = {"close_s": min(_close(ctx, r) for _, r in reqs), "dwell_s": reqs[0][1]["dwell"],
              "fire_free": out_of_window, "fastest_end_s": None, "flame_avoiding_arrival_s": None}
    if out_of_window:
        # even without fire no attempted shelter could be reached in time: the fire is not what prevents a route
        rec.update(status="explained", reason_code="window", detail_code="no_route_even_without_fire",
                   deadline_cause="time_window", window=window)
        return
    rec["deadline_cause"] = "flames"
    if not unreachable:
        rec.update(status="explained", reason_code="no_flame_avoiding_route", detail_code="no_flame_avoiding_route_fits_window",
                   window=window)
        return
    run = flame_avoiding(ctx.index, start, t0, [], ctx.horizon, turns=False)
    if run["issue_blocked"]:
        rec.update(status="explained", reason_code="all_exits_blocked", detail_code="entry_point_in_flame")
        rec["exits"] = []
        return
    if run["horizon_cut_exits"] or not run["frontier_exits"]:
        # the flame-free area is not closed by flame alone within the window: the proof is a timing one
        rec.update(status="explained", reason_code="no_flame_avoiding_route", detail_code="no_flame_avoiding_route_fits_window",
                   window=window)
        rec["reachable_nodes"] = run["reached_nodes"]
        return
    g = ctx.graph
    exits = []
    for edge_id, at in run["frontier_exits"]:
        e = g.edge_index[edge_id]
        blocks = ctx.index.edge_blocks(e)
        tau = g.ticks[e]
        hit = [b for b in blocks if b[0] <= at < b[1]]
        if not hit:     # cannot happen: a frontier edge is blocked at every start second from ``at`` on
            raise AssertionError("frontier edge %s free at its first reach time" % edge_id)
        at_eval = at
        p0, p1 = g.xy(g.u[e]), g.xy(g.v[e])
        # contact pairs of a traversal starting at at_eval (closed rule)
        sc_pairs = []
        for (lo, hi, s, cell, b) in hit:
            occ = [o for o in ctx.index.occupancies(p0, p1, F(tau)) if o[0] == cell][0]
            w = max(at_eval + occ[1], b)
            sc_pairs.append((s, cell, w, b, occ[1]))
        witness = min(sc_pairs, key=lambda p: (p[2], p[0], p[1]))
        u = (witness[2] - at_eval) / tau if tau else F(0)
        u = min(max(u, F(0)), F(1))
        lab = _point_label(ctx, p0, p1, u, g.u[e])
        exits.append({"edge_id": edge_id, "osm_way_id": _way(ctx, edge_id), **lab,
                      "flame_time_s": r1(min(p[3] for p in sc_pairs)), "contact_time_s": r1(witness[2]),
                      "members": _members(ctx, {p[0] for p in sc_pairs}), "members_total": ctx.packet.S,
                      "pass_time_at_deadline_s": None, "slack_s": None, "reached_at_s": int(at),
                      "segment": "edge"})
        ev.times += [min(p[3] for p in sc_pairs), witness[2]]
    rec["exits"] = exits
    rec["reachable_nodes"] = run["reached_nodes"]
    ev.exits_proof = {"start": start, "t0": t0, "frontier": run["frontier_exits"], "horizon_cut": run["horizon_cut_exits"]}
    rec.update(status="explained", reason_code="all_exits_blocked", detail_code="flame_free_area_closed")


def _window_limit(ctx: Context, rec: dict) -> None:
    """Name the limit a window block refers to: the 1-hour scenario window (close = hazard horizon) or a recorded
    mission's own arrival window (close < horizon)."""
    w = rec.get("window")
    if w is not None:
        w["limit"] = "scenario_window" if w["close_s"] >= ctx.horizon else "arrival_window"
        w["horizon_s"] = ctx.horizon


def _verdict_counts(attempts) -> dict:
    """{"model_no_route": n, "unresolved/<reason_code>": n, ...} (reason codes only for unresolved attempts)."""
    c = collections.Counter(a.verdict if a.verdict != "unresolved" else "unresolved/%s" % (a.reason_code or "UNKNOWN")
                            for a in attempts)
    return dict(sorted(c.items()))


# ------------------------------------------------------------------------------------------------ entry point
def explain_plan(ctx: Context, plan: OriginPlan) -> tuple:
    rec = {"status": None, "verdict_summary": plan.best_verdict, "deadline_offset_s": plan.latest_s, "next_offset_s": None,
           "next_verdict": None, "reason_code": None, "binding": [], "exits": [], "notes": list(plan.notes),
           "detail_code": None, "origin_kind": plan.kind}
    ev = Evidence(plan.origin_id)
    if plan.best_verdict == "unresolved":
        rec.update(status="not_explainable", reason_code="other", detail_code="origin_unresolved",
                   attempt_verdicts=_verdict_counts([a for c in plan.sweep for a in c.attempts]))
    elif plan.best_verdict == "model_no_route":
        _explain_no_route(ctx, plan, rec, ev)
    else:
        _explain_checked(ctx, plan, rec, ev)
    _window_limit(ctx, rec)
    for it in rec["binding"] + rec["exits"]:
        # the named place is the origin itself (planner origin ids are "osm:<type>/<id>")
        it["place_is_origin"] = bool(it.get("place_osm_id")) and "osm:%s" % it["place_osm_id"] == plan.origin_id
    assert rec["status"] in STATUSES and rec["reason_code"] in REASONS, rec
    return rec, ev
