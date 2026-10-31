"""Safe Interval Path Planning (Phillips and Likhachev 2011, IEEE ICRA, pp. 5628-5635) for the contact-only lattice
relaxation of `integration/kit/phaseB/zsweep.py`, on an abstract instance.

Lattice (identical to the sweep): states are (incoming directed edge s, integer second t, admission flag); s = E is the
virtual issue state. From (s, t): EDGE j leaves the head node of s when (s, j) is not a forbidden turn, t is not a
blocked departure second of j and t + D_j <= horizon, arriving at (j, t + D_j) WITH admission; WAIT moves to (s, t + 1)
WITHOUT admission when the head node is waitable and t is not a blocked wait second. A destination is accepted at t only
on an admission arrival (or the issue state at departure) whose second lies in the node's acceptance set.

Safe intervals. For a head node, a wait component is a maximal run [a, b] of seconds such that every t in [a, b - 1]
may wait (b <= horizon); at a non-waitable node every second is its own component. A label is a piece
(s, [lo, hi], arrival_hi): every second of [lo, hi] is reachable in state s, seconds <= arrival_hi by an edge arrival,
later ones by waiting from arrival_hi inside one component. At waitable heads a piece is the SIPP state (configuration,
safe interval) with the earliest arrival as its label, extended to the end of the safe interval (Theorem 1 of Phillips
and Likhachev: an earlier arrival can wait to every successor a later one reaches). Classic SIPP assumes waiting
everywhere; at non-waitable heads a later arrival is not dominated, so the piece keeps the whole arrival run and
dominance is set inclusion: per state, seconds already covered by an earlier piece are subtracted from every new piece.
Destination acceptance needs admission at a specific second, so goal candidates are computed from the raw edge-arrival
run before that subtraction.

Search: best-first on key = lo + h(head), h an admissible and consistent static lower bound on remaining travel time
(backward Dijkstra on travel ticks). Keys are monotone along transitions, goal keys are exact arrivals, so the first
goal popped is the earliest relaxed arrival; an exhausted queue proves that no admissible journey exists in the
relaxation. See docs/SIPP_EQUIVALENCE.md.
"""
from __future__ import annotations

import heapq
import math
import time
from dataclasses import dataclass, field

from .intervals import Covered, complement, first_in, next_member, normalise


@dataclass
class Instance:
    n_nodes: int
    tail: list                      # [E] node index
    head: list                      # [E] node index
    D: list                         # [E] travel seconds (integer >= 1)
    origin: int                     # node index
    start_state: int                # E for the virtual issue state, else the incoming edge index
    forbidden: set                  # {(s, j)}: s in 0..E (E = issue state), j edge index
    waitable: list                  # [V] bool
    edge_block: dict                # j -> normalised blocked departure seconds
    wait_block: dict                # node -> normalised blocked wait-start seconds
    accept: dict                    # node -> normalised acceptance seconds (admission arrivals only)
    departure: int
    horizon: int
    h: list = None                  # [V] lower bound on remaining travel seconds (None: computed)
    succ: list = field(default=None, repr=False)

    @property
    def E(self):
        return len(self.D)

    def successors(self):
        if self.succ is None:
            out_by_node = [[] for _ in range(self.n_nodes)]
            for j in range(self.E):
                out_by_node[self.tail[j]].append(j)
            succ = []
            for s in range(self.E + 1):
                node = self.origin if s == self.E else self.head[s]
                succ.append([j for j in out_by_node[node] if (s, j) not in self.forbidden])
            self.succ = succ
        return self.succ

    def state_head(self, s):
        return self.origin if s == self.E else self.head[s]

    def lower_bound(self):
        if self.h is None:
            dist = [math.inf] * self.n_nodes
            rev = [[] for _ in range(self.n_nodes)]
            for j in range(self.E):
                rev[self.head[j]].append((self.tail[j], self.D[j]))
            heap = [(0, n) for n in self.accept if self.accept[n]]
            for _, n in heap:
                dist[n] = 0
            heapq.heapify(heap)
            while heap:
                d, n = heapq.heappop(heap)
                if d != dist[n]:
                    continue
                for u, w in rev[n]:
                    if d + w < dist[u]:
                        dist[u] = d + w
                        heapq.heappush(heap, (d + w, u))
            self.h = dist
        return self.h


def component_end(inst, node, t):
    """Last second reachable from t at `node` by waiting (t itself at a non-waitable node)."""
    if not inst.waitable[node]:
        return t
    blocked = inst.wait_block.get(node, [])
    x = next_member(blocked, t)
    return min(x, inst.horizon) if x is not None else inst.horizon


def solve(inst, *, deadline=None, max_labels=None):
    """Return {status, arrival, legs (abstract), metrics}. status: FOUND, EXHAUSTED, TIMEOUT, LABEL_CAP."""
    t0 = time.perf_counter()
    succ = inst.successors()
    h = inst.lower_bound()
    E, hor, dep = inst.E, inst.horizon, inst.departure
    covered = {}
    pieces = []                     # (state, lo, hi, arrival_hi, parent_piece, edge)
    heap = []
    counter = 0
    metrics = {"pieces": 0, "expansions": 0, "goal_candidates": 0, "successor_runs": 0}

    def push_piece(s, lo, hi, arr_hi, parent):
        nonlocal counter
        cov = covered.get(s)
        if cov is None:
            cov = covered[s] = Covered()
        node = inst.state_head(s)
        hv = h[node]
        if hv == math.inf:
            return
        for a, b in cov.subtract(lo, hi):
            cov.add(a, b)
            pieces.append((s, a, b, arr_hi, parent))
            metrics["pieces"] += 1
            counter += 1
            heapq.heappush(heap, (a + hv, counter, 0, len(pieces) - 1))

    def push_goal(s, t, parent):
        nonlocal counter
        counter += 1
        metrics["goal_candidates"] += 1
        heapq.heappush(heap, (t, counter, 1, (s, t, parent)))

    s0 = inst.start_state
    node0 = inst.state_head(s0)
    if first_in(inst.accept.get(node0, []), dep, dep) is not None:
        return {"status": "FOUND", "arrival": dep, "legs": [], "destination_node": node0, "metrics": metrics,
                "wall_s": time.perf_counter() - t0}
    end0 = component_end(inst, node0, dep)
    push_piece(s0, dep, end0, dep, None)
    while heap:
        if deadline is not None and (metrics["expansions"] & 255) == 0 and time.perf_counter() >= deadline:
            return {"status": "TIMEOUT", "arrival": None, "legs": [], "metrics": metrics, "wall_s": time.perf_counter() - t0}
        if max_labels is not None and metrics["pieces"] > max_labels:
            return {"status": "LABEL_CAP", "arrival": None, "legs": [], "metrics": metrics, "wall_s": time.perf_counter() - t0}
        key, _, kind, item = heapq.heappop(heap)
        if kind == 1:
            s, t, parent = item
            return {"status": "FOUND", "arrival": t, "legs": _reconstruct(inst, pieces, s, t, parent),
                    "destination_node": inst.head[s], "metrics": metrics, "wall_s": time.perf_counter() - t0}
        s, lo, hi, arr_hi, parent = pieces[item]
        metrics["expansions"] += 1
        for j in succ[s]:
            Dj = inst.D[j]
            top = min(hi, hor - Dj)
            if top < lo:
                continue
            v = inst.head[j]
            acc = inst.accept.get(v)
            for x, y in complement(inst.edge_block.get(j, []), lo, top):
                metrics["successor_runs"] += 1
                ax, ay = x + Dj, y + Dj
                if acc:
                    g = first_in(acc, ax, ay)
                    if g is not None:
                        push_goal(j, g, item)
                if h[v] == math.inf:
                    continue
                if not inst.waitable[v]:
                    push_piece(j, ax, ay, ay, item)
                    continue
                t = ax
                while t <= ay:                              # one piece per wait component met by the arrival run
                    b = component_end(inst, v, t)
                    push_piece(j, t, b, min(ay, b), item)
                    t = b + 1
    return {"status": "EXHAUSTED", "arrival": None, "legs": [], "metrics": metrics, "wall_s": time.perf_counter() - t0}


def _reconstruct(inst, pieces, s, t, parent):
    """Abstract legs [("EDGE", j, start, end) | ("WAIT", node, start, end)] ending with an admission arrival at t."""
    legs = []
    cur_s, cur_t, cur_parent = s, t, parent
    while True:
        Dj = inst.D[cur_s]
        start = cur_t - Dj
        legs.append(("EDGE", cur_s, start, cur_t))
        ps, plo, phi, parr, pparent = pieces[cur_parent]
        assert plo <= start <= phi, "SIPP_BACKTRACK"
        node = inst.state_head(ps)
        if start > parr:                                    # waited from the piece's last edge arrival
            for w in range(start - 1, parr - 1, -1):
                legs.append(("WAIT", node, w, w + 1))
            arrive = parr
        else:
            arrive = start
        if pparent is None:
            assert arrive == inst.departure, "SIPP_BACKTRACK_START"
            break
        cur_s, cur_t, cur_parent = ps, arrive, pparent
    legs.reverse()
    return legs


def structurally_reachable(inst):
    succ = inst.successors()
    seen = {inst.start_state}
    stack = [inst.start_state]
    goal_nodes = {n for n, a in inst.accept.items() if a is not None}
    while stack:
        s = stack.pop()
        if inst.state_head(s) in goal_nodes:
            return True
        for j in succ[s]:
            if j not in seen:
                seen.add(j)
                stack.append(j)
    return False


def make_instance(**kw):
    kw["edge_block"] = {j: normalise(v) for j, v in kw.get("edge_block", {}).items() if v}
    kw["wait_block"] = {n: normalise(v) for n, v in kw.get("wait_block", {}).items() if v}
    kw["accept"] = {n: normalise(v) for n, v in kw.get("accept", {}).items()}
    return Instance(**kw)
