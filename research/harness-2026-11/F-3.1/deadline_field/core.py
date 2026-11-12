"""Backward deadline field on an abstract integer-time road instance (see ../DESIGN.md).

An ``Instance`` is the router's movement model with all hazard information already reduced to integer interval
sets (seconds):

* ``B[j]``  start seconds at which EDGE j has contact (occupancy [t, t + D[j]]);
* ``W[v]``  start seconds at which WAIT [t, t + 1] at node v has contact;
* ``A[j]``  arrival seconds at which arriving over edge j is accepted (head(j) is a destination, opening, horizon and
            the dwell all fit);
* ``IB[o]`` departure seconds at which the issue point o is in contact.

``backward`` computes, for every edge state s, the full set R[s] of seconds from which an accepted completion
exists (standing at head(s) having arrived over s, admission false). No scalar dominance is used.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from . import intervals as iv


@dataclass
class Instance:
    H: int
    n_nodes: int
    tail: list
    head: list
    D: list
    waitable: list
    forbidden: set = field(default_factory=set)       # {(incoming edge, outgoing edge)}
    B: list = None                                     # per edge
    W: list = None                                     # per node
    A: list = None                                     # per edge
    IB: dict = field(default_factory=dict)             # per origin node

    def __post_init__(self):
        E = len(self.tail)
        if self.B is None:
            self.B = [[] for _ in range(E)]
        if self.W is None:
            self.W = [[] for _ in range(self.n_nodes)]
        if self.A is None:
            self.A = [[] for _ in range(E)]
        if any(d < 1 for d in self.D):
            raise ValueError("travel ticks must be >= 1")
        self.out = [[] for _ in range(self.n_nodes)]
        self.inc = [[] for _ in range(self.n_nodes)]
        for j in range(E):
            self.out[self.tail[j]].append(j)
            self.inc[self.head[j]].append(j)
        self.B = [iv.normalize(b) for b in self.B]
        self.W = [iv.normalize(w) for w in self.W]
        # acceptance needs arrival <= H; edges also need start >= 0
        self.A = [[p for p in iv.normalize(a) if p[1] >= 0] for a in self.A]
        self.A = [[(max(lo, 0), min(hi, self.H)) for lo, hi in a if lo <= self.H and hi >= 0] for a in self.A]


@dataclass
class Field:
    inst: Instance
    R: list            # per edge state
    G: list            # per edge state: R ∪ A
    stats: dict


def _wait_close(piece, Wv, Rs):
    """Downward waiting closure of a new piece [lo, hi] at a waitable head: t joins when t+1 is in R and t is not
    wait-blocked. Returns the extended piece [lo', hi] (lo' >= 0)."""
    lo, hi = piece
    w = iv.max_below(Wv, lo)           # largest wait-blocked second < lo
    lo2 = 0 if w is None else max(w + 1, 0)
    return (min(lo, lo2), hi)


def backward(inst: Instance, *, pieces_cap: int | None = None) -> Field:
    E = len(inst.tail)
    R = [[] for _ in range(E)]
    pred = [[i for i in inst.inc[inst.tail[j]] if (i, j) not in inst.forbidden] for j in range(E)]
    heap = []
    pushes = pops = 0
    for j in range(E):
        for lo, hi in inst.A[j]:
            heapq.heappush(heap, (-hi, j, lo, hi))
            pushes += 1
    while heap:
        _, j, lo, hi = heapq.heappop(heap)
        pops += 1
        a, b = max(lo - inst.D[j], 0), hi - inst.D[j]
        if a > b:
            continue
        cand = iv.subtract((a, b), inst.B[j])
        if not cand:
            continue
        for s in pred[j]:
            new = iv.subtract_all(cand, R[s])
            if not new:
                continue
            hv = inst.head[s]
            if inst.waitable[hv]:
                ext = []
                for p in new:
                    ext.extend(iv.subtract(_wait_close(p, inst.W[hv], R[s]), R[s]))
                new = iv.normalize(ext)
                # pieces produced by the closure may already overlap each other; normalize then re-subtract
                new = iv.subtract_all(new, R[s])
            for p in new:
                iv.add(R[s], p)
            for p in new:
                for q in iv.subtract(p, inst.A[s]):
                    heapq.heappush(heap, (-q[1], s, q[0], q[1]))
                    pushes += 1
            if pieces_cap is not None and pushes > pieces_cap:
                raise RuntimeError("PIECES_CAP")
    G = [iv.normalize(R[j] + inst.A[j]) for j in range(E)]
    return Field(inst, R, G, {"pushes": pushes, "pops": pops,
                              "pieces": sum(len(r) for r in R)})


def issue_core(fld: Field, o: int):
    """Seconds t at which standing at origin o (no incoming edge, admission false after the issue) a completion
    exists, before the issue-point check."""
    inst = fld.inst
    X = []
    for j in inst.out[o]:
        for lo, hi in fld.G[j]:
            a, b = max(lo - inst.D[j], 0), hi - inst.D[j]
            if a <= b:
                X.extend(iv.subtract((a, b), inst.B[j]))
    X = iv.normalize(X)
    if inst.waitable[o]:
        X = iv.normalize([_wait_close(p, inst.W[o], X) for p in X])
    return X


def issue_set(fld: Field, o: int):
    """Feasible departure seconds of origin o: issue-point clear and a completion exists."""
    return iv.subtract_all(issue_core(fld, o), iv.normalize(fld.inst.IB.get(o, [])))


def static_to_dest(inst: Instance):
    """Node lower bound on remaining travel to any acceptance (reverse Dijkstra on travel ticks, turns and hazards
    ignored): h(v) <= D_j + h(head j) for every edge, h = 0 at acceptance heads. Consistent, so A* stays exact."""
    INFV = 1 << 60
    h = [INFV] * inst.n_nodes
    heap = []
    for j, a in enumerate(inst.A):
        if a and h[inst.head[j]] != 0:
            h[inst.head[j]] = 0
            heap.append((0, inst.head[j]))
    heapq.heapify(heap)
    while heap:
        d, v = heapq.heappop(heap)
        if d != h[v]:
            continue
        for j in inst.inc[v]:
            u = inst.tail[j]
            nd = d + inst.D[j]
            if nd < h[u]:
                h[u] = nd
                heapq.heappush(heap, (nd, u))
    return h


def witness(fld: Field, o: int, t: int):
    """Earliest-arrival accepted journey from origin o departing at t, restricted to the field (exact: every pushed
    state can complete, Dijkstra on time). Returns (arrival, legs) or None. Legs: ('EDGE', j, start, end) /
    ('WAIT', node, start, end)."""
    inst = fld.inst
    if iv.contains(iv.normalize(inst.IB.get(o, [])), t):
        return None
    core = issue_core(fld, o)
    if not iv.contains(core, t):
        return None
    if "h" not in fld.stats:
        fld.stats["h"] = static_to_dest(inst)
    h = fld.stats["h"]
    ISSUE = -1
    # state = (edge state or ISSUE, time, admitted): a WAIT keeps the edge state but clears admission
    start = (ISSUE, t, False)
    heap = [(t + h[o], t, ISSUE, 0, start)]
    parent = {start: None}
    seq = 1
    while heap:
        _, time, _, _, st = heapq.heappop(heap)
        s, _, admitted = st
        if admitted and iv.contains(inst.A[s], time):
            legs = []
            cur = st
            while parent[cur] is not None:
                prev, leg = parent[cur]
                legs.append(leg)
                cur = prev
            legs.reverse()
            return time, legs
        node = o if s == ISSUE else inst.head[s]
        for j in inst.out[node]:
            if s != ISSUE and (s, j) in inst.forbidden:
                continue
            arr = time + inst.D[j]
            if arr > inst.H or iv.contains(inst.B[j], time) or not iv.contains(fld.G[j], arr):
                continue
            key = (j, arr, True)
            if key not in parent:
                parent[key] = (st, ("EDGE", j, time, arr))
                heapq.heappush(heap, (arr + h[inst.head[j]], arr, j, seq, key)); seq += 1
        if inst.waitable[node] and time + 1 <= inst.H and not iv.contains(inst.W[node], time):
            nxt = core if s == ISSUE else fld.R[s]
            if iv.contains(nxt, time + 1):
                key = (s, time + 1, False)
                if key not in parent:
                    parent[key] = (st, ("WAIT", node, time, time + 1))
                    heapq.heappush(heap, (time + 1 + h[node], time + 1, s, seq, key)); seq += 1
    raise AssertionError("field says feasible but no witness found (field/witness inconsistency)")


def check_fixed_point(fld: Field):
    """Certificate check, independent of the solving order: for every edge state s, R[s] must EQUAL the right-hand
    side of the set equation evaluated on the stored sets. The time-expanded graph is acyclic (every move takes
    >= 1 s), so the equation has exactly one solution (induction on t from H downwards); equality therefore proves
    that R is that solution, given the masks B, W, A. Returns the number of states checked; raises on mismatch."""
    inst = fld.inst
    E = len(inst.tail)
    for s in range(E):
        hv = inst.head[s]
        rhs = []
        for j in inst.out[hv]:
            if (s, j) in inst.forbidden:
                continue
            for lo, hi in fld.G[j]:
                a, b = max(lo - inst.D[j], 0), hi - inst.D[j]
                if a <= b:
                    rhs.extend(iv.subtract((a, b), inst.B[j]))
        if inst.waitable[hv]:
            for lo, hi in fld.R[s]:
                a, b = max(lo - 1, 0), hi - 1
                if a <= b:
                    rhs.extend(iv.subtract((a, b), inst.W[hv]))
        rhs = iv.normalize(rhs)
        if rhs != fld.R[s]:
            raise AssertionError("fixed point violated at state %d: R=%r rhs=%r" % (s, fld.R[s][:4], rhs[:4]))
        if fld.G[s] != iv.normalize(fld.R[s] + inst.A[s]):
            raise AssertionError("G != R u A at state %d" % s)
    return E
