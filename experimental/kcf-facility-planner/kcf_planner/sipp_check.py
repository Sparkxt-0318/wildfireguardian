"""Adapter: re-check planner legs with the repository's existing experimental SIPP module (wfg_sipp).

wfg_sipp (experimental/sipp-routing/src) models a contact-only lattice: states are incoming edges, an EDGE leaves the
head node unless the (incoming, next) pair is forbidden or the departure second is blocked, WAIT keeps the incoming
edge, and a destination accepts only admission (edge) arrivals in its acceptance set. That is exactly the leg model of
this contract, so each emitted leg is translated into a wfg_sipp Instance and checked three ways:
  * wfg_sipp.predicate.violations  (JS-1..JS-8, JS-11 of docs/JOURNEY_SAFETY_PREDICATE.md; JS-9/JS-10 need flux data
    that this contract does not carry and are NOT checked),
  * wfg_sipp.sipp.solve            (earliest admissible arrival by safe-interval path planning),
  * wfg_sipp.bruteforce.earliest_arrival (second-by-second time-expanded reference), only when the lattice is small.
Translation: a blocking interval [a, b] with b > a on an edge of travel D blocks departure seconds a - D + 1 .. b - 1
(positive overlap of [d, d + D) with [a, b)); acceptance at the destination is [open, min(close, horizon) - unload_s].
Nothing in wfg_sipp is modified; it is imported read-only from its sibling directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

SIPP_SRC = Path(__file__).resolve().parents[2] / "sipp-routing" / "src"


def _import():
    if str(SIPP_SRC) not in sys.path:
        sys.path.insert(0, str(SIPP_SRC))
    from wfg_sipp import bruteforce, predicate, sipp  # noqa: E402
    return sipp, predicate, bruteforce


def available():
    try:
        _import()
        return True
    except Exception:  # pragma: no cover - only if the sibling module is absent
        return False


def _blocked_departures(ivs, D):
    return [(a - D + 1, b - 1) for a, b in ivs if b > a]


def leg_instance(case, *, start_node, start_state, departure, target, accept, view):
    sipp, _, _ = _import()
    nodes = case.nodes
    for n in (start_node, target):
        if n not in nodes:
            nodes.append(n)
    idx = {n: i for i, n in enumerate(nodes)}
    eidx = {e.id: k for k, e in enumerate(case.edges)}
    E = len(case.edges)
    forbidden = {(eidx[a], eidx[b]) for a, b in case.forbidden}
    block = {}
    for k, e in enumerate(case.edges):
        ivs = list(e.closed) + (list(e.unknown) if view == "supported" else [])
        block[k] = _blocked_departures(ivs, e.travel_s)
    inst = sipp.make_instance(
        n_nodes=len(nodes), tail=[idx[e.u] for e in case.edges], head=[idx[e.v] for e in case.edges],
        D=[e.travel_s for e in case.edges], origin=idx[start_node],
        start_state=E if start_state is None else eidx[start_state], forbidden=forbidden,
        waitable=[True] * len(nodes), edge_block=block, wait_block={},
        accept={idx[target]: [accept]} if accept[0] <= accept[1] else {}, departure=departure,
        horizon=case.horizon_s)
    return inst, idx, eidx


def trip_legs(trip, idx, eidx, departure):
    """Abstract wfg_sipp legs for an emitted trip starting at `departure` (waits written as multi-second legs)."""
    legs, t, node = [], departure, idx[trip["start_node"]]
    for s in trip["edges"]:
        if s["entry_s"] > t:
            legs.append(("WAIT", node, t, s["entry_s"]))
        legs.append(("EDGE", eidx[s["edge_id"]], s["entry_s"], s["exit_s"]))
        t, node = s["exit_s"], idx[s["to"]]
    return legs


def check_trip(case, trip, *, view="supported", require_earliest=False, brute_limit=400_000):
    """Return a dict of independent wfg_sipp checks for one emitted trip."""
    sipp, predicate, bruteforce = _import()
    outbound = trip["kind"] == "outbound"
    H = case.horizon_s
    if outbound:
        departure = trip["ready_s"] + case.board_s
        accept = (case.window[0], min(case.window[1], H) - case.unload_s)
    else:
        departure = trip["ready_s"]
        accept = (0, H)
    inst, idx, eidx = leg_instance(case, start_node=trip["start_node"], start_state=trip["incoming_edge_at_start"],
                                   departure=departure, target=trip["end_node"], accept=accept, view=view)
    legs = trip_legs(trip, idx, eidx, departure)
    member = {"edge_block": inst.edge_block, "wait_block": {}}
    viol = predicate.violations(inst, legs, trip["arrival_s"], [member])
    res = sipp.solve(inst)
    sipp_arrival = res["arrival"] if res["status"] == "FOUND" else None
    out = {"trip_id": trip.get("trip_id"), "view": view, "predicate_violations": [list(v) for v in viol],
           "sipp_status": res["status"], "sipp_earliest_arrival": sipp_arrival, "emitted_arrival": trip["arrival_s"]}
    lattice = (H - departure + 1) * (len(case.edges) + 1)
    if lattice <= brute_limit:
        out["bruteforce_earliest_arrival"] = bruteforce.earliest_arrival(inst)
    ok = not viol and sipp_arrival is not None and sipp_arrival <= trip["arrival_s"]
    if require_earliest:
        ok = ok and sipp_arrival == trip["arrival_s"]
    if "bruteforce_earliest_arrival" in out:
        ok = ok and out["bruteforce_earliest_arrival"] == sipp_arrival
    out["ok"] = ok
    return out


def check_no_route(case, *, view):
    """For a single-leg parallel case, confirm with wfg_sipp that a group's leg has no admissible arrival."""
    sipp, _, bruteforce = _import()
    H = case.horizon_s
    out = []
    for i, grp in enumerate(case.groups):
        if case.mode != "parallel" or i >= len(case.vehicles):
            break
        v = case.vehicles[i]
        inst, _, _ = leg_instance(case, start_node=case.origin, start_state=None, departure=v.available_s +
                                  case.board_s, target=case.destination,
                                  accept=(case.window[0], min(case.window[1], H) - case.unload_s), view=view)
        if inst.departure > H:
            out.append({"group_id": grp.id, "sipp_status": "DEPARTURE_AFTER_HORIZON", "bruteforce": None})
            continue
        res = sipp.solve(inst)
        out.append({"group_id": grp.id, "sipp_status": res["status"], "sipp_arrival": res["arrival"],
                    "bruteforce": bruteforce.earliest_arrival(inst)})
    return out


def check_result(case, result):
    """Cross-check every emitted trip. Last leg of each vehicle chain (and every parallel leg) must be earliest."""
    if not available():
        return {"available": False, "checks": []}
    trips = result.get("trips", [])
    last_by_vehicle = {}
    for t in trips:
        last_by_vehicle[t["vehicle_id"]] = t.get("trip_id")
    checks = [check_trip(case, t, view="supported", require_earliest=(t.get("trip_id") ==
                                                                       last_by_vehicle[t["vehicle_id"]]))
              for t in trips]
    for t in result.get("conditional_trips", []) or []:
        checks.append(check_trip(case, t, view="optimistic"))
    return {"available": True, "source": "experimental/sipp-routing/src/wfg_sipp", "checks": checks,
            "all_ok": all(c["ok"] for c in checks)}
