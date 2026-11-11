"""Time-dependent facility transport planner for the portable KCF contract.

Model (see SCHEMA.md and CONSTRAINTS.md):
* A vehicle state is (incoming edge, second) at the head node of that edge; the virtual state None means "no incoming
  edge yet" and only occurs at the origin before the first trip. Waiting at a node keeps the incoming edge, so a turn
  restriction applies to the next edge after any wait, including the gap between shuttle legs.
* Traversing edge e entered at second d occupies [d, d + travel_s). It is admissible iff it has no positive-duration
  overlap with any blocking interval of e and d + travel_s <= horizon. Supported search blocks closed AND unknown
  intervals; optimistic search blocks closed intervals only.
* Waiting is allowed at every node, so for a fixed incoming edge an earlier time dominates a later one. Each leg is a
  time-dependent Dijkstra over incoming-edge states with earliest-departure transitions (FIFO by waiting).
* A destination arrival counts only as an edge arrival (admission) whose second lies in
  [window_open, min(window_close, horizon) - unload_s]. Waiting at the destination does not create a new arrival.
* A multi-leg chain (shuttle: out, return, out, ...) is solved exactly by dynamic programming over the leg-end incoming
  edge, again using earliest-time dominance per state.

The search counts settled labels against a cap; hitting the cap yields UNRESOLVED, never a no-route claim.
"""
from __future__ import annotations

import heapq
import time

from .model import positive

INF = float("inf")


class CapReached(Exception):
    pass


class Budget:
    def __init__(self, max_labels=2_000_000, deadline_s=None):
        self.max_labels = max_labels
        self.used = 0
        self.deadline = None if deadline_s is None else time.perf_counter() + deadline_s

    def tick(self):
        self.used += 1
        if self.used > self.max_labels:
            raise CapReached("label cap %d reached" % self.max_labels)
        if self.deadline is not None and (self.used & 255) == 0 and time.perf_counter() > self.deadline:
            raise CapReached("wall-clock limit reached")


def blocking(edge, view):
    """Blocking intervals of an edge under a view: 'supported' (closed + unknown) or 'optimistic' (closed only)."""
    if view == "supported":
        return positive(list(edge.closed) + list(edge.unknown))
    if view == "optimistic":
        return list(edge.closed)
    if view == "topology":
        return []
    raise ValueError(view)


def overlapping(ivs, entry, exit_):
    """Intervals with positive-duration overlap with [entry, exit_)."""
    return [(a, b) for a, b in ivs if b > a and a < exit_ and b > entry]


def earliest_free(D, ivs, t, arr_lo, arr_hi):
    """Smallest entry d >= t with arr_lo <= d + D <= arr_hi and [d, d + D) free of ivs; None if none."""
    d = max(t, arr_lo - D)
    while True:
        if d + D > arr_hi:
            return None
        hit = overlapping(ivs, d, d + D)
        if not hit:
            return d
        d = max(b for _, b in hit)


def latest_free(D, ivs, upper, lower):
    """Largest entry d with lower <= d <= upper and [d, d + D) free; `lower` is known to be free."""
    d = upper
    while d > lower:
        hit = overlapping(ivs, d, d + D)
        if not hit:
            return d
        d = min(a for a, _ in hit) - D
    return lower


class Graph:
    def __init__(self, case, view, horizon=None):
        self.case = case
        self.view = view
        self.H = case.horizon_s if horizon is None else horizon
        self.by_id = {e.id: e for e in case.edges}
        self.out = {}
        for e in case.edges:
            self.out.setdefault(e.u, []).append(e)
        self.block = {e.id: blocking(e, view) for e in case.edges}
        self.forbidden = case.forbidden


def search_leg(g, start_node, start_state, t0, target, acc_lo, acc_hi, budget):
    """Earliest admission arrival at `target` per final incoming edge.

    Returns {end_edge_id: (arrival, path)} where path is a list of (edge_id, entry, exit) and the dict is empty if no
    admissible arrival exists within the horizon.
    """
    acc_hi = min(acc_hi, g.H)
    START = ("START",)
    best = {start_state: (t0, START, None)}
    heap = [(t0, 0, start_state)]
    seq = 1
    settled = set()
    goals = {}
    while heap:
        t, _, s = heapq.heappop(heap)
        if s in settled or best[s][0] != t:
            continue
        settled.add(s)
        budget.tick()
        node = start_node if s is None else g.by_id[s].v
        for e in g.out.get(node, []):
            if s is not None and (s, e.id) in g.forbidden:
                continue
            ivs = g.block[e.id]
            d = earliest_free(e.travel_s, ivs, t, -INF, g.H)
            if d is not None:
                arr = d + e.travel_s
                if e.id not in best or arr < best[e.id][0]:
                    best[e.id] = (arr, s, d)
                    heapq.heappush(heap, (arr, seq, e.id))
                    seq += 1
            if e.v == target and acc_lo <= acc_hi:
                d2 = earliest_free(e.travel_s, ivs, t, acc_lo, acc_hi)
                if d2 is not None and (e.id not in goals or d2 + e.travel_s < goals[e.id][0]):
                    goals[e.id] = (d2 + e.travel_s, d2, s)
    out = {}
    for j, (arr, d, pred) in goals.items():
        path = [(j, d, arr)]
        s = pred
        while best[s][1] is not START:
            a_s, p_s, d_s = best[s]
            path.append((s, d_s, a_s))
            s = p_s
        path.reverse()
        out[j] = (arr, path)
    return out


def shift_late(g, path, t0):
    """Same road sequence and arrival, every wait moved as early in the journey as possible (to the start node).

    Residents then wait at the facility (or an empty vehicle at the shelter), not at an intermediate junction.
    """
    path = list(path)
    upper = path[-1][1]  # last entry is fixed: arrival second is the admission second
    new = [None] * len(path)
    for k in range(len(path) - 1, -1, -1):
        j, d, a = path[k]
        e = g.by_id[j]
        if k == len(path) - 1:
            nd = d
        else:
            nd = latest_free(e.travel_s, g.block[j], upper - e.travel_s, d)
        new[k] = (j, nd, nd + e.travel_s)
        upper = nd
    assert new[0][1] >= t0
    return new


def chain_legs(case, vehicle, groups):
    legs = []
    for k, grp in enumerate(groups):
        if k:
            legs.append({"kind": "empty_return", "group": None})
        legs.append({"kind": "outbound", "group": grp})
    return legs


def solve_chain(case, g, vehicle, groups, budget, *, shift=True):
    """Exact earliest-final-unloading schedule for one vehicle taking `groups` in order.

    Returns dict: status FOUND | INFEASIBLE, trips (witness for the delivered prefix), delivered (group ids),
    final_unload_s, failure (dict) for the first undeliverable group.
    """
    H = g.H
    wlo, whi = case.window
    legs = chain_legs(case, vehicle, groups)
    frontier = {None: (vehicle.available_s, None)}  # end incoming edge -> (ready second, back-pointer)
    history = []
    failure = None
    for i, leg in enumerate(legs):
        if leg["kind"] == "outbound" and leg["group"].people > vehicle.seats:
            failure = {"code": "CAPACITY", "group_id": leg["group"].id,
                       "detail": "group %s has %d people; vehicle %s has %d seats" % (
                           leg["group"].id, leg["group"].people, vehicle.id, vehicle.seats)}
            break
        new = {}
        for st, (ready, _) in sorted(frontier.items(), key=lambda kv: (kv[1][0], str(kv[0]))):
            if leg["kind"] == "outbound":
                res = search_leg(g, case.origin, st, ready + case.board_s, case.destination, wlo,
                                 min(whi, H) - case.unload_s, budget)
                bump = case.unload_s
            else:
                res = search_leg(g, case.destination, st, ready, case.origin, -INF, H, budget)
                bump = 0
            for j, (arr, path) in res.items():
                nr = arr + bump
                if j not in new or nr < new[j][0] or (nr == new[j][0] and str(st) < str(new[j][1][0])):
                    new[j] = (nr, (st, ready, path))
        if not new:
            gid = leg["group"].id if leg["kind"] == "outbound" else None
            failure = {"code": "NO_ADMISSIBLE_LEG", "leg_index": i, "leg_kind": leg["kind"], "group_id": gid,
                       "detail": "no admissible %s leg for vehicle %s within the horizon" % (
                           leg["kind"].replace("_", " "), vehicle.id)}
            if leg["kind"] == "empty_return":
                failure["group_id"] = legs[i + 1]["group"].id
            break
        history.append(new)
        frontier = new

    # Delivered prefix: last outbound leg completed.
    last_out = None
    for i in range(len(history) - 1, -1, -1):
        if legs[i]["kind"] == "outbound":
            last_out = i
            break
    if last_out is None:
        return {"status": "INFEASIBLE", "trips": [], "delivered": [], "final_unload_s": None, "failure": failure,
                "vehicle_id": vehicle.id}
    end = min(history[last_out].items(), key=lambda kv: (kv[1][0], str(kv[0])))[0]
    raw_trips = []
    st = end
    for i in range(last_out, -1, -1):
        nr, (prev_st, ready, path) = history[i][st]
        raw_trips.append((i, prev_st, ready, path))
        st = prev_st
    raw_trips.reverse()
    trips = []
    for i, prev_st, ready, path in raw_trips:
        leg = legs[i]
        t0 = ready + (case.board_s if leg["kind"] == "outbound" else 0)
        forward = path
        if shift:
            path = shift_late(g, path, t0)
        trips.append(make_trip(case, g, vehicle, leg, prev_st, ready, path, forward, t0))
    delivered = [t["group_id"] for t in trips if t["kind"] == "outbound"]
    complete = failure is None and len(history) == len(legs)
    return {"status": "FOUND" if complete else "INFEASIBLE", "trips": trips, "delivered": delivered,
            "final_unload_s": trips[-1]["unloading_end_s"] if complete else None, "failure": failure,
            "vehicle_id": vehicle.id}


def forward_causes(case, g, path, t0):
    """Causes of each wait in the earliest-departure (unshifted) witness: these are the binding constraints."""
    out, prev = [], t0
    for k, (j, d, a) in enumerate(path):
        if d > prev:
            c = hold_cause(case, g, path[k], prev, path)
            c["delay_s"] = d - prev
            out.append(c)
        prev = a
    return out


def make_trip(case, g, vehicle, leg, start_state, ready, path, forward=None, t0=None):
    outbound = leg["kind"] == "outbound"
    dep = path[0][1]
    arr = path[-1][2]
    start_node = case.origin if outbound else case.destination
    edges = [{"edge_id": j, "from": g.by_id[j].u, "to": g.by_id[j].v, "entry_s": d, "exit_s": a}
             for j, d, a in path]
    waits = []
    causes = forward_causes(case, g, forward if forward is not None else path, t0 if t0 is not None else
                            (ready + case.board_s if outbound else ready))
    prev_t = dep if outbound else ready
    prev_node, prev_edge = start_node, start_state
    if outbound:
        # Hold at the facility before boarding (residents are not yet on board).
        hold_end = dep - case.board_s
        if hold_end > ready:
            waits.append({"node": start_node, "start_s": ready, "end_s": hold_end, "incoming_edge_id": start_state,
                          "phase": "before_boarding", "causes": causes})
    for k, (j, d, a) in enumerate(path):
        if d > prev_t:
            waits.append({"node": prev_node, "start_s": prev_t, "end_s": d, "incoming_edge_id": prev_edge,
                          "phase": "on_board" if outbound else "empty_vehicle",
                          "causes": [hold_cause(case, g, path[k], prev_t, path)] if k else causes})
        prev_t, prev_node, prev_edge = a, g.by_id[j].v, j
    trip = {
        "vehicle_id": vehicle.id,
        "kind": leg["kind"],
        "group_id": leg["group"].id if outbound else None,
        "people": leg["group"].people if outbound else 0,
        "seats": vehicle.seats,
        "start_node": start_node,
        "end_node": case.destination if outbound else case.origin,
        "incoming_edge_at_start": start_state,
        "ready_s": ready,
        "boarding_start_s": dep - case.board_s if outbound else None,
        "boarding_end_s": dep if outbound else None,
        "departure_s": dep,
        "arrival_s": arr,
        "unloading_start_s": arr if outbound else None,
        "unloading_end_s": arr + case.unload_s if outbound else None,
        "edges": edges,
        "waits": waits,
        "binding_constraints": causes,
        "uses_unknown_input": any(overlapping(g.by_id[j].unknown, d, a) for j, d, a in path),
    }
    lengths = [g.by_id[j].length_m for j, _, _ in path]
    if all(isinstance(x, (int, float)) for x in lengths):
        trip["length_m"] = sum(lengths)
    return trip


def hold_cause(case, g, step, wait_from, path):
    """Why the next edge could not be entered earlier: the blocking interval hit by an earlier entry, or the
    destination window, or a voluntary shift that moves waiting to the start node."""
    j, d, a = step
    e = g.by_id[j]
    hits = overlapping(g.block[j], wait_from, wait_from + e.travel_s)
    if hits:
        a0, b0 = hits[0]
        kind = "closed" if overlapping(e.closed, wait_from, wait_from + e.travel_s) else "unknown"
        return {"code": "EDGE_CLOSED" if kind == "closed" else "EDGE_UNKNOWN", "edge_id": j,
                "interval": [a0, b0]}
    if e.v == case.destination and j == path[-1][0] and wait_from + e.travel_s < case.window[0]:
        return {"code": "DESTINATION_NOT_OPEN", "window_open_s": case.window[0]}
    return {"code": "SHIFTED_TO_START", "detail": "waiting moved earlier so it happens at the start node"}


# ----------------------------------------------------------------------------------------------------------------------
def plan(case, view, budget, *, horizon=None, window=None, shift=True):
    """Plan every chain under a view. Returns {'chains': [...], 'unassigned': [group ids]}."""
    if window is not None or horizon is not None:
        case = _with(case, horizon=horizon, window=window)
    g = Graph(case, view)
    chains, unassigned = [], []
    if case.mode == "parallel":
        for i, grp in enumerate(case.groups):
            if i >= len(case.vehicles):
                unassigned.append(grp.id)
                continue
            chains.append(solve_chain(case, g, case.vehicles[i], [grp], budget, shift=shift))
    else:
        chains.append(solve_chain(case, g, case.vehicles[0], case.groups, budget, shift=shift))
    return {"chains": chains, "unassigned": unassigned}


def _with(case, horizon=None, window=None):
    import copy
    c = copy.copy(case)
    if horizon is not None:
        c.horizon_s = horizon
    if window is not None:
        c.window = window
    return c


def whole(p):
    if p is None:
        return "UNKNOWN"
    if p["unassigned"] or any(c["status"] == "INFEASIBLE" for c in p["chains"]):
        return "INFEASIBLE"
    return "FOUND"
