"""Backward deadline field with a thermal-dose budget (TDU) enforced inside the search.

F-3.1's field (deadline_field/core.py) answers "does a contact-free accepted journey exist from (state, second)?"
with interval sets. A dose budget is ONE additive, non-negative resource, and every other constraint is already part
of the state (time) or of the masks. So "does a journey with dose <= budget exist?" is exactly "is the minimum dose
over all journeys <= budget?", and the minimum dose obeys a Bellman equation on the same time-expanded graph:

    m_s(t) = min( over successor edges j of head(s), (s, j) allowed, t not in B[j], t + D_j <= H:
                      e_j(t) + g_j(t + D_j);
                  if head(s) is waitable and t not in W[head(s)]:  w(t) + m_s(t + 1) )
    g_j(t) = min( m_j(t),  a(t) if t in A[j] )                        (acceptance on arrival over j, dwell dose a)

with e, w, a the move doses (kcf_heat/dose.py) and +inf where no move exists. Every move takes >= 1 s and doses are
>= 0, so a Dijkstra on dose settles each (state, second) once with its minimum. Seconds are kept as runs of equal value
(intervals, as in F-3.1); a run splits only where a move's dose changes. Runs above the budget are never created, so
the field holds exactly the seconds with m <= budget (and their m). With all doses 0 it settles exactly F-3.1's sets.

Departure (issue) value of origin o at t: the same equation from the issue state (no incoming edge, waiting keeps the
issue state), then the origin-is-destination acceptance at the departure second, then the issue-point block IB.
Doses are integer quanta, so every comparison is exact.
"""
from __future__ import annotations

import bisect
import heapq
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .closure import F31  # noqa: F401  (puts F-3.1 on sys.path)
from .dose import EMPTY, RLE

from deadline_field import intervals as iv  # noqa: E402

INF = 1 << 62
_G, _M, _MW = 0, 1, 2      # _MW: an m-run produced by the waiting closure (its own closure would repeat it)


class Costs:
    """Move doses for one field: edge(j) -> RLE over start seconds, wait(n) -> RLE over wait starts,
    dwell(n) -> RLE over arrival seconds at destination node n (the instance's dwell)."""

    def __init__(self, edge=None, wait=None, dwell=None):
        self._edge, self._wait, self._dwell = edge or {}, wait or {}, dwell or {}

    def edge(self, j):
        return self._edge.get(j, EMPTY)

    def wait(self, n):
        return self._wait.get(n, EMPTY)

    def dwell(self, n):
        return self._dwell.get(n, EMPTY)


class ModelCosts(Costs):
    """Costs from a DoseModel; dwell per destination node index -> dwell length (s)."""

    def __init__(self, dm, dwell_by_node: dict):
        self.dm, self.dwell_by_node = dm, dict(dwell_by_node)

    def edge(self, j):
        return self.dm.edge(j)

    def wait(self, n):
        return self.dm.wait(n)

    def dwell(self, n):
        L = self.dwell_by_node.get(n)
        return EMPTY if L is None else self.dm.dwell(n, int(L))


@dataclass
class DoseField:
    inst: object
    costs: Costs
    budget: int
    vG: list            # per edge state: sorted runs (lo, hi, value) of g
    vM: list            # per edge state: sorted runs (lo, hi, value) of m
    stats: dict = field(default_factory=dict)

    def _val(self, runs, t):
        i = bisect.bisect_right(runs, (t, INF, INF)) - 1
        if i >= 0 and runs[i][1] >= t:
            return runs[i][2]
        return INF

    def g(self, j, t):
        return self._val(self.vG[j], t)

    def m(self, s, t):
        return self._val(self.vM[s], t)


def tdu_backward(inst, costs: Costs, budget: int, *, pieces_cap: int | None = None) -> DoseField:
    E = len(inst.tail)
    pred = [[i for i in inst.inc[inst.tail[j]] if (i, j) not in inst.forbidden] for j in range(E)]
    sG = [[] for _ in range(E)]
    sM = [[] for _ in range(E)]
    vG = [[] for _ in range(E)]
    vM = [[] for _ in range(E)]
    heap = []
    pushes = pops = 0
    for j in range(E):
        if inst.A[j]:
            dw = costs.dwell(inst.head[j])
            for lo, hi in inst.A[j]:
                for a, b, c in dw.split(lo, hi):
                    if c <= budget:
                        heap.append((c, -b, _G, j, a, b))
                        pushes += 1
    heapq.heapify(heap)
    push = heapq.heappush
    while heap:
        val, _, kind, s, lo, hi = heapq.heappop(heap)
        pops += 1
        if kind == _G:
            new = iv.subtract((lo, hi), sG[s])
            if not new:
                continue
            for p in new:
                iv.add(sG[s], p)
                vG[s].append((p[0], p[1], val))
            D = inst.D[s]
            cand = []
            for a, b in new:
                a2, b2 = max(a - D, 0), b - D
                if a2 <= b2:
                    cand.extend(iv.subtract((a2, b2), inst.B[s]))
            if not cand:
                continue
            ec = costs.edge(s)
            pieces = []
            for a, b in cand:
                if ec:
                    for x, y, c in ec.split(a, b):
                        if val + c <= budget:
                            pieces.append((x, y, val + c))
                else:
                    pieces.append((a, b, val))
            for i in pred[s]:
                Si = sM[i]
                for x, y, v2 in pieces:
                    for q in iv.subtract((x, y), Si):
                        push(heap, (v2, -q[1], _M, i, q[0], q[1]))
                        pushes += 1
        else:
            new = iv.subtract((lo, hi), sM[s])
            if not new:
                continue
            for p in new:
                iv.add(sM[s], p)
                vM[s].append((p[0], p[1], val))
            for a, b in new:
                for q in iv.subtract((a, b), sG[s]):
                    push(heap, (val, -q[1], _G, s, q[0], q[1]))
                    pushes += 1
            hv = inst.head[s]
            if kind == _M and inst.waitable[hv]:
                wc = costs.wait(hv)
                for a, b in new:
                    # downward waiting closure: m_s(t) <= w(t) + m_s(t + 1) for t < a, until a wait block or a second
                    # that is already settled (its own closure has covered what lies below it)
                    lo_w = iv.max_below(inst.W[hv], a)
                    L = 0 if lo_w is None else lo_w + 1
                    st = iv.max_below(sM[s], a)
                    if st is not None:
                        L = max(L, st + 1)
                    if L > a - 1:
                        continue
                    acc = 0
                    for x, y, c in reversed(wc.split(L, a - 1) if wc else [(L, a - 1, 0)]):
                        if c == 0:
                            if val + acc > budget:
                                break
                            for q in iv.subtract((x, y), sM[s]):
                                push(heap, (val + acc, -q[1], _MW, s, q[0], q[1]))
                                pushes += 1
                        else:
                            stop = False
                            for t in range(y, x - 1, -1):
                                acc += c
                                if val + acc > budget:
                                    stop = True
                                    break
                                push(heap, (val + acc, -t, _MW, s, t, t))
                                pushes += 1
                            if stop:
                                break
        if pieces_cap is not None and pushes > pieces_cap:
            raise RuntimeError("PIECES_CAP")
    for lst in vG:
        lst.sort()
    for lst in vM:
        lst.sort()
    return DoseField(inst, costs, budget, vG, vM,
                     {"pushes": pushes, "pops": pops, "runs_G": sum(map(len, vG)), "runs_M": sum(map(len, vM))})


def _dense(rle: RLE, n: int):
    a = np.zeros(n, dtype=np.int64)
    for lo, hi, c in rle.runs:
        if lo < n:
            a[lo:min(hi, n - 1) + 1] = c
    return a


def _fill(runs, n, default):
    """Dense length-n array from sorted runs (lo, hi, v), `default` elsewhere (runs clipped to [0, n - 1])."""
    a = np.full(n, default, dtype=np.int64)
    if not runs:
        return a
    r = np.asarray(runs, dtype=np.int64)
    lo, hi, v = np.clip(r[:, 0], 0, n), np.clip(r[:, 1], -1, n - 1), r[:, 2]
    L = np.maximum(hi - lo + 1, 0)
    if L.sum() == 0:
        return a
    off = np.concatenate(([0], np.cumsum(L)[:-1]))
    pos = np.repeat(lo - off, L) + np.arange(int(L.sum()))
    a[pos] = np.repeat(v, L)
    return a


def issue_core_values(fld: DoseField, o: int):
    """Minimum dose from the issue state at o for each departure second t in [0, H] (before the origin-acceptance
    and issue-point checks); INF where no journey within the budget exists."""
    inst = fld.inst
    H = inst.H
    m = np.full(H + 1, INF, dtype=np.int64)
    for j in inst.out[o]:
        D = inst.D[j]
        if not fld.vG[j] or D > H:
            continue
        g = _fill(fld.vG[j], H + 1, INF)[D:]                 # g_j(t + D) for t in [0, H - D]
        e = _fill(fld.costs.edge(j).runs, H - D + 1, 0)
        cand = np.where(g < INF, g + e, INF)
        for lo, hi in inst.B[j]:
            lo, hi = max(lo, 0), min(hi, H - D)
            if lo <= hi:
                cand[lo:hi + 1] = INF
        np.minimum(m[:H - D + 1], cand, out=m[:H - D + 1])
    if inst.waitable[o] and H >= 1:
        w = _dense(fld.costs.wait(o), H)
        for s0, s1 in iv.subtract((0, H - 1), inst.W[o]):
            n = s1 - s0 + 1
            P = np.concatenate(([0], np.cumsum(w[s0:s1 + 1])))
            vals = m[s0:s1 + 2].copy()
            ok = vals < INF
            vals[ok] += P[ok]
            suf = np.minimum.accumulate(vals[::-1])[::-1]
            cand = np.where(suf[:n] < INF, suf[:n] - P[:n], INF)
            np.minimum(m[s0:s1 + 1], cand, out=m[s0:s1 + 1])
    m[m > fld.budget] = INF
    return m


def issue_values(fld: DoseField, o: int, core=None):
    """Minimum dose of a feasible journey departing origin o at t (INF where none within the budget).
    `core`: issue_core_values(fld, o), if already computed (not modified)."""
    inst = fld.inst
    H = inst.H
    m = issue_core_values(fld, o) if core is None else core.copy()
    an = inst.AN.get(o, [])
    if an:
        dw = _dense(fld.costs.dwell(o), H + 1)
        for lo, hi in an:
            np.minimum(m[lo:hi + 1], dw[lo:hi + 1], out=m[lo:hi + 1])
    for lo, hi in iv.normalize(inst.IB.get(o, [])):
        lo, hi = max(lo, 0), min(hi, H)
        if lo <= hi:
            m[lo:hi + 1] = INF
    m[m > fld.budget] = INF
    return m


def feasible_set(values, limit: int):
    """Interval list of seconds with value <= limit."""
    ok = values <= limit
    if not ok.any():
        return []
    idx = np.flatnonzero(np.diff(np.concatenate(([0], ok.astype(np.int8), [0]))))
    return [(int(a), int(b) - 1) for a, b in zip(idx[::2], idx[1::2])]


def witness_tdu(fld: DoseField, o: int, t: int, *, values=None, core=None):
    """A journey departing o at t whose dose equals the field's minimum (follows equalities of the Bellman equation).
    Returns (dose, arrival, legs) or None. Legs: ('EDGE', j, start, end) / ('WAIT', node, start, end)."""
    inst, costs = fld.inst, fld.costs
    vals = issue_values(fld, o, core) if values is None else values
    V = int(vals[t])
    if V >= INF:
        return None
    if iv.contains(inst.AN.get(o, []), t) and costs.dwell(o).at(t) == V:
        return V, t, []
    if core is None:
        core = issue_core_values(fld, o)
    s, time, rem, admitted, legs = -1, t, V, False, []
    for _ in range(4 * inst.H + 8):
        if s != -1 and admitted and iv.contains(inst.A[s], time) and costs.dwell(inst.head[s]).at(time) == rem:
            return V, time, legs
        node = o if s == -1 else inst.head[s]
        moved = False
        for j in inst.out[node]:
            if s != -1 and (s, j) in inst.forbidden:
                continue
            arr = time + inst.D[j]
            if arr > inst.H or iv.contains(inst.B[j], time):
                continue
            gv = fld.g(j, arr)
            if gv < INF and costs.edge(j).at(time) + gv == rem:
                legs.append(("EDGE", j, time, arr))
                s, time, rem, admitted, moved = j, arr, gv, True, True
                break
        if moved:
            continue
        if inst.waitable[node] and time + 1 <= inst.H and not iv.contains(inst.W[node], time):
            nxt = int(core[time + 1]) if s == -1 else fld.m(s, time + 1)
            if nxt < INF and costs.wait(node).at(time) + nxt == rem:
                legs.append(("WAIT", node, time, time + 1))
                time, rem, admitted = time + 1, nxt, False
                continue
        raise AssertionError("dose witness dead end at state %d time %d rem %d" % (s, time, rem))
    raise AssertionError("dose witness did not terminate")
