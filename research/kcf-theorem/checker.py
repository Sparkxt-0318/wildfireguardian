"""Independent route checker for the deadline-field model (THEOREM.md section 1). Standard library only; imports
nothing from the repository.

Instance (plain dict; JSON-compatible, integer keys may be strings):
  H          horizon (int); every leg must end at or before H
  edges      [[tail, head, D], ...]; edge j is entry j; D >= 1 whole seconds
  waitable   node ids where a vehicle may wait
  forbidden  [[i, j], ...]: arriving over edge i, the vehicle may not take edge j next
  B          {j: [[lo, hi], ...]}  start seconds at which driving edge j is closed (flame contact)
  W          {v: [[lo, hi], ...]}  start seconds at which a 1-second wait at v is closed
  A          {j: [[lo, hi], ...]}  arrival seconds at which arriving over edge j is accepted (at a shelter)
  IB         {o: [[lo, hi], ...]}  departure seconds at which origin o itself is closed
  AN         {o: [[lo, hi], ...]}  departure seconds accepted with an empty route (origin is a shelter)
Closed intervals are inclusive. A closure TIME c (closed from c on, never reopens) is the interval [c, H].

Route: [["EDGE", j, start, end] | ["WAIT", v, start, end], ...]. A WAIT may span several seconds.
"""
from __future__ import annotations

from collections import deque


def _set(ivs):
    out = set()
    for lo, hi in ivs or ():
        out.update(range(int(lo), int(hi) + 1))
    return out


def _by_int(d):
    return {int(k): _set(v) for k, v in (d or {}).items()}


class Model:
    """Instance with interval lists expanded to plain sets of seconds (small graphs only)."""

    def __init__(self, inst):
        self.H = int(inst["H"])
        self.tail = [int(e[0]) for e in inst["edges"]]
        self.head = [int(e[1]) for e in inst["edges"]]
        self.D = [int(e[2]) for e in inst["edges"]]
        if any(d < 1 for d in self.D):
            raise ValueError("every travel time D must be >= 1")
        self.waitable = {int(v) for v in inst.get("waitable", ())}
        self.forbidden = {(int(i), int(j)) for i, j in inst.get("forbidden", ())}
        self.B, self.W, self.A = _by_int(inst.get("B")), _by_int(inst.get("W")), _by_int(inst.get("A"))
        self.IB, self.AN = _by_int(inst.get("IB")), _by_int(inst.get("AN"))
        self.out = {}
        for j, u in enumerate(self.tail):
            self.out.setdefault(u, []).append(j)

    def edge_ok(self, last, j, t):
        """Reason the move is illegal, or None. last = edge arrived over (None at the origin)."""
        if last is not None and (last, j) in self.forbidden:
            return "turn (%d -> %d) is forbidden" % (last, j)
        if t + self.D[j] > self.H:
            return "edge %d started at %d ends at %d > H = %d" % (j, t, t + self.D[j], self.H)
        if t in self.B.get(j, ()):
            return "edge %d is closed at start second %d" % (j, t)
        return None

    def wait_ok(self, v, t):
        if v not in self.waitable:
            return "node %d is not waitable" % v
        if t + 1 > self.H:
            return "wait at node %d from %d ends after H = %d" % (v, t, self.H)
        if t in self.W.get(v, ()):
            return "wait at node %d is closed at second %d" % (v, t)
        return None


def check_route(inst, origin, departure, route):
    """(True, why) if the route is a valid accepted journey from origin departing at `departure`, else (False, why)."""
    m = inst if isinstance(inst, Model) else Model(inst)
    o, t = int(origin), int(departure)
    if not 0 <= t <= m.H:
        return False, "departure %d outside [0, H = %d]" % (t, m.H)
    if t in m.IB.get(o, ()):
        return False, "origin %d is closed at departure %d" % (o, t)
    if not route:
        if t in m.AN.get(o, ()):
            return True, "origin %d is itself accepted at %d" % (o, t)
        return False, "empty route and the origin is not accepted at %d" % t
    node, last, admitted = o, None, False
    for k, leg in enumerate(route):
        kind, x, a, b = leg[0], int(leg[1]), int(leg[2]), int(leg[3])
        where = "leg %d (%s %d [%d, %d])" % (k, kind, x, a, b)
        if a != t:
            return False, "%s: starts at %d but the vehicle is there at %d" % (where, a, t)
        if kind == "EDGE":
            if not 0 <= x < len(m.D):
                return False, "%s: no such edge" % where
            if m.tail[x] != node:
                return False, "%s: edge leaves node %d, vehicle is at node %d" % (where, m.tail[x], node)
            if b != a + m.D[x]:
                return False, "%s: edge takes D = %d s, leg takes %d s" % (where, m.D[x], b - a)
            why = m.edge_ok(last, x, a)
            if why:
                return False, "%s: %s" % (where, why)
            node, last, t, admitted = m.head[x], x, b, True
        elif kind == "WAIT":
            if x != node:
                return False, "%s: vehicle is at node %d" % (where, node)
            if b <= a:
                return False, "%s: empty or negative wait" % where
            for s in range(a, b):
                why = m.wait_ok(node, s)
                if why:
                    return False, "%s: %s" % (where, why)
            t, admitted = b, False
        else:
            return False, "%s: unknown leg kind" % where
    if not admitted:
        return False, "route ends with a wait; acceptance is checked only on arrival over an edge"
    if t not in m.A.get(last, ()):
        return False, "arrival over edge %d at %d is not accepted" % (last, t)
    return True, "accepted at node %d at %d over edge %d" % (node, t, last)


def find_route(inst, origin, departure, *, limit=2_000_000):
    """Exhaustive forward search over (node, last edge, time, admitted); no dominance, no pruning. Returns a valid
    route or None. Raises if more than `limit` configurations would be explored (use small graphs)."""
    m = inst if isinstance(inst, Model) else Model(inst)
    o, t0 = int(origin), int(departure)
    if not 0 <= t0 <= m.H or t0 in m.IB.get(o, ()):
        return None
    if t0 in m.AN.get(o, ()):
        return []
    start = (o, None, t0, False)
    parent = {start: None}
    queue = deque([start])
    while queue:
        cfg = queue.popleft()
        node, last, t, admitted = cfg
        if admitted and t in m.A.get(last, ()):
            legs = []
            while parent[cfg] is not None:
                cfg, leg = parent[cfg]
                legs.append(leg)
            return legs[::-1]
        nxt = []
        for j in m.out.get(node, ()):
            if m.edge_ok(last, j, t) is None:
                nxt.append(((m.head[j], j, t + m.D[j], True), ["EDGE", j, t, t + m.D[j]]))
        if m.wait_ok(node, t) is None:
            nxt.append(((node, last, t + 1, False), ["WAIT", node, t, t + 1]))
        for c, leg in nxt:
            if c not in parent:
                parent[c] = (cfg, leg)
                queue.append(c)
                if len(parent) > limit:
                    raise RuntimeError("search space above limit; graph too large for brute force")
    return None


def confirm_deadline(inst, origin, deadline, route):
    """Certify a claimed latest departure L: the route departing at L is valid, and brute force finds no valid route
    departing at L + 1. Returns (ok, why)."""
    m = inst if isinstance(inst, Model) else Model(inst)
    ok, why = check_route(m, origin, deadline, route)
    if not ok:
        return False, "route at L = %d is invalid: %s" % (deadline, why)
    later = find_route(m, origin, deadline + 1)
    if later is not None:
        return False, "departing at L + 1 = %d has a valid route: %r" % (deadline + 1, later)
    return True, "valid at L = %d (%s); no valid route at L + 1 (exhaustive)" % (deadline, why)


def feasible_set(inst, origin):
    """Every departure second 0..H with a valid route (brute force, one second at a time)."""
    m = inst if isinstance(inst, Model) else Model(inst)
    return [t for t in range(m.H + 1) if find_route(m, origin, t) is not None]
