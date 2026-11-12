"""Brute-force oracle: exhaustive forward search of the time-expanded graph, one departure second at a time.

Deliberately independent of the interval code and of the backward equations: plain Python sets of seconds, the
router's transition rules spelled out directly (EDGE with turn restriction and contact; WAIT only at waitable nodes,
no re-admission; acceptance only on arrival over an edge; issue point checked at departure).
"""
from __future__ import annotations

import heapq


def _set(ivs):
    s = set()
    for lo, hi in ivs:
        s.update(range(lo, hi + 1))
    return s


class Oracle:
    def __init__(self, inst_raw: dict):
        """inst_raw: H, n_nodes, tail, head, D, waitable, forbidden, B, W, A, IB (interval lists, un-normalized ok)."""
        r = inst_raw
        self.H = r["H"]
        self.tail, self.head, self.D = r["tail"], r["head"], r["D"]
        self.waitable = r["waitable"]
        self.forbidden = set(r["forbidden"])
        self.B = [_set(b) for b in r["B"]]
        self.W = [_set(w) for w in r["W"]]
        self.A = [{a for a in _set(x) if 0 <= a <= self.H} for x in r["A"]]
        self.IB = {o: _set(x) for o, x in r.get("IB", {}).items()}
        self.out = {}
        for j, u in enumerate(self.tail):
            self.out.setdefault(u, []).append(j)

    def earliest(self, o: int, t: int):
        """Earliest accepted arrival departing origin o at second t, or None (exhaustive, Dijkstra on time over
        every reachable time-expanded state; no pruning, no dominance)."""
        if t in self.IB.get(o, set()):
            return None
        start = ("issue", None, t)
        seen = {start}
        heap = [(t, 0, start)]
        k = 1
        while heap:
            time, _, (kind, s, _t) = heapq.heappop(heap)
            node = o if kind == "issue" else self.head[s]
            if kind == "edge" and time in self.A[s]:
                return time
            for j in self.out.get(node, []):
                if kind != "issue" and (s, j) in self.forbidden:
                    continue
                arr = time + self.D[j]
                if arr > self.H or time in self.B[j]:
                    continue
                st = ("edge", j, arr)
                if st not in seen:
                    seen.add(st)
                    heapq.heappush(heap, (arr, k, st)); k += 1
            if self.waitable[node] and time + 1 <= self.H and time not in self.W[node]:
                # a WAIT keeps the incoming edge and clears admission: model as a non-accepting copy of the state
                st = ("waited", s, time + 1) if kind != "issue" else ("issue", None, time + 1)
                if st not in seen:
                    seen.add(st)
                    heapq.heappush(heap, (time + 1, k, st)); k += 1
        return None
