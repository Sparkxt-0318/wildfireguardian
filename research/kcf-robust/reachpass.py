"""Compiled latest-departure pass for many closure levels at once (PROTOCOL.md section 4).

The road instance of ``product/wfg-roadlayer`` (``engine.build_instance``, ``engine.accept``,
``engine.origin_closure``) has only permanent closures: an edge is closed for every start >= lo_j, a wait at node v
for every start >= b_v - 1, an origin for every departure >= b_o, and a shelter accepts arrivals in [0, acc]. Then
every feasible set of the F-3.1 field is downward closed: a journey that works from t also works from any t' < t,
shifted (earlier edge starts, earlier waits and an earlier arrival are all still allowed). So R_s = [0, L_s] and the
F-3.1 recursion of ``core.backward`` reduces to one integer per edge state:

    G_j = max(L_j, acc_j),   L_s = max over allowed j after s of min(lo_j - 1, G_j - D_j)   (-1 = empty)
    L_o = min(b_o - 1, max over j out of o of min(lo_j - 1, G_j - D_j))

Waiting adds nothing to a downward-closed set. Since G_j - D_j < G_j, a max-heap label-setting pass (latest
departure, Dijkstra in reverse) is exact. ``tests/test_reachpass.py`` checks it against the unchanged engine and a
brute-force search over all journeys.

A *level* is one closure assignment per road cell (int64 seconds, NONE = no closure within H); the pass is run per
shelter and per level. Levels are expected nested (each one closes everything earlier than the previous), which
lets the caller stop once every origin of a shelter has no safe departure.
"""
from __future__ import annotations

import numpy as np

try:
    from numba import njit
except Exception:  # pragma: no cover - runs (slowly) without numba
    def njit(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f

NONE = np.int64(1) << 50


class Graph:
    """Arrays of a ``regiondata.RoadModel`` used by the pass (built once per region)."""

    def __init__(self, road):
        E = len(road.tail)
        self.E, self.N = E, len(road.node_ids)
        self.tail = np.asarray(road.tail, np.int64)
        self.head = np.asarray(road.head, np.int64)
        self.D = np.asarray(road.D, np.int64)
        self.waitable = np.asarray(road.waitable, np.bool_)
        self.node_cell = np.asarray(road.node_cell, np.int64)
        # allowed predecessor lists: s with head(s) = tail(j) and (s, j) not forbidden
        inc = road.inc_by_node
        ptr = [0]
        idx = []
        for j in range(E):
            for s in inc.get(road.tail[j], []):
                if (s, j) not in road.forbidden:
                    idx.append(s)
            ptr.append(len(idx))
        self.pptr = np.asarray(ptr, np.int64)
        self.pidx = np.asarray(idx, np.int64)
        optr, oidx = [0], []
        for v in range(self.N):
            oidx.extend(road.out_by_node.get(v, []))
            optr.append(len(oidx))
        self.optr = np.asarray(optr, np.int64)
        self.oidx = np.asarray(oidx, np.int64)
        iptr, iidx = [0], []
        for v in range(self.N):
            iidx.extend(inc.get(v, []))
            iptr.append(len(iidx))
        self.iptr = np.asarray(iptr, np.int64)
        self.iidx = np.asarray(iidx, np.int64)
        # segments: lo_j = max(0, min over segments of b_cell - floor(D_j * zb)), zb = p / q exactly (replay.py)
        sptr, scell, sfl = [0], [], []
        for j, segs in enumerate(road.seg):
            for c, zb in segs:
                scell.append(int(c))
                sfl.append((road.D[j] * zb.numerator) // zb.denominator)
            sptr.append(len(scell))
        self.sptr = np.asarray(sptr, np.int64)
        self.scell = np.asarray(scell, np.int64)
        self.sfl = np.asarray(sfl, np.int64)


@njit(cache=True)
def edge_lo(sptr, scell, sfl, close, H):
    """Per edge: first start second at which the edge meets a closed cell (NONE if never within H)."""
    E = sptr.shape[0] - 1
    lo = np.full(E, NONE, np.int64)
    for j in range(E):
        best = NONE
        for k in range(sptr[j], sptr[j + 1]):
            b = close[scell[k]]
            if b >= NONE:
                continue
            s = b - sfl[k]
            if s < 0:
                s = 0
            if s < best:
                best = s
        if best <= H:
            lo[j] = best
    return lo


@njit(cache=True)
def _hpush(hk, hv, n, k, v):
    i = n
    hk[i] = k
    hv[i] = v
    while i > 0:
        p = (i - 1) >> 1
        if hk[p] >= hk[i]:
            break
        hk[p], hk[i] = hk[i], hk[p]
        hv[p], hv[i] = hv[i], hv[p]
        i = p
    return n + 1


@njit(cache=True)
def _hpop(hk, hv, n):
    k, v = hk[0], hv[0]
    n -= 1
    hk[0] = hk[n]
    hv[0] = hv[n]
    i = 0
    while True:
        l = 2 * i + 1
        if l >= n:
            break
        c = l
        if l + 1 < n and hk[l + 1] > hk[l]:
            c = l + 1
        if hk[c] <= hk[i]:
            break
        hk[c], hk[i] = hk[i], hk[c]
        hv[c], hv[i] = hv[i], hv[c]
        i = c
    return k, v, n


@njit(cache=True)
def shelter_pass(E, D, pptr, pidx, iptr, iidx, lo, snode, acc, G, L, hk, hv):
    """Fill G (accepted-or-completable latest second per edge state) for one shelter. acc = latest accepted arrival
    over an edge into the shelter (-1 = none). G, L are scratch arrays of length E (overwritten)."""
    for j in range(E):
        G[j] = -1
        L[j] = -1
    n = 0
    if acc >= 0:
        for k in range(iptr[snode], iptr[snode + 1]):
            j = iidx[k]
            G[j] = acc
            n = _hpush(hk, hv, n, acc, j)
    while n > 0:
        g, j, n = _hpop(hk, hv, n)
        if g != G[j]:
            continue
        c = g - D[j]
        if lo[j] - 1 < c:
            c = lo[j] - 1
        if c < 0:
            continue
        for k in range(pptr[j], pptr[j + 1]):
            s = pidx[k]
            if c > L[s]:
                L[s] = c
                if c > G[s]:
                    G[s] = c
                    n = _hpush(hk, hv, n, c, s)
    return G


@njit(cache=True)
def origin_latest(o, optr, oidx, D, lo, G, ob):
    best = -1
    for k in range(optr[o], optr[o + 1]):
        j = oidx[k]
        if G[j] < 0:
            continue
        c = G[j] - D[j]
        if lo[j] - 1 < c:
            c = lo[j] - 1
        if c > best:
            best = c
    if ob < NONE and ob - 1 < best:
        best = ob - 1
    return best if best >= 0 else -1


@njit(cache=True)
def run_levels(E, H, dwell, D, pptr, pidx, iptr, iidx, optr, oidx, sptr, scell, sfl, node_cell,
               closes, snodes, job_ptr, job_orig, out, nested):
    """closes: [K, ncells] closure seconds per level (NONE = open). Jobs: shelter snodes[i] with origins
    job_orig[job_ptr[i]:job_ptr[i+1]]. out[k, m] = latest departure of the m-th (shelter, origin) pair at level k.
    Levels are processed in order; if nested, a shelter is skipped at later levels once all its origins are -1."""
    K = closes.shape[0]
    G = np.empty(E, np.int64)
    L = np.empty(E, np.int64)
    nh = pidx.shape[0] + iidx.shape[0] + 16  # pushes <= relaxations + initial seeds
    hk = np.empty(nh, np.int64)
    hv = np.empty(nh, np.int64)
    alive = np.ones(snodes.shape[0], np.bool_)
    for k in range(K):
        close = closes[k]
        lo = edge_lo(sptr, scell, sfl, close, H)
        for i in range(snodes.shape[0]):
            if not alive[i]:
                for m in range(job_ptr[i], job_ptr[i + 1]):
                    out[k, m] = -1
                continue
            sn = snodes[i]
            b = close[node_cell[sn]]
            acc = H - dwell
            if b < NONE:
                x = b - dwell
                if x < 0:
                    x = 0
                if x - 1 < acc:
                    acc = x - 1
            shelter_pass(E, D, pptr, pidx, iptr, iidx, lo, sn, acc, G, L, hk, hv)
            anyok = False
            for m in range(job_ptr[i], job_ptr[i + 1]):
                o = job_orig[m]
                ob = close[node_cell[o]]
                v = origin_latest(o, optr, oidx, D, lo, G, ob)
                out[k, m] = v
                if v >= 0:
                    anyok = True
            if nested and not anyok:
                alive[i] = False
    return out


def jobs_for(region):
    """(snodes, job_ptr, job_orig, pairs): pairs[m] = (origin id, shelter node) for out[:, m]."""
    by = {}
    for o in region.origins:
        if o["node"] is None or not o["checkable"]:
            continue
        for s in region.cands.get(o["id"], []):
            by.setdefault(s["node"], []).append(o)
    snodes, ptr, orig, pairs = [], [0], [], []
    for sn in sorted(by):
        snodes.append(sn)
        for o in sorted(by[sn], key=lambda o: o["node"]):
            orig.append(o["node"])
            pairs.append((o["id"], sn))
        ptr.append(len(orig))
    return (np.asarray(snodes, np.int64), np.asarray(ptr, np.int64), np.asarray(orig, np.int64), pairs)


def latest_by_level(g: Graph, region, closes: np.ndarray, H: int, dwell: int, nested: bool = True):
    """closes: [K, ncells] int64. Returns ({origin id: array[K] of latest departure over its shelters}, raw, pairs)."""
    sn, ptr, orig, pairs = jobs_for(region)
    closes = np.ascontiguousarray(closes, np.int64)
    out = np.empty((closes.shape[0], len(pairs)), np.int64)
    run_levels(g.E, H, dwell, g.D, g.pptr, g.pidx, g.iptr, g.iidx, g.optr, g.oidx, g.sptr, g.scell, g.sfl,
               g.node_cell, closes, sn, ptr, orig, out, nested)
    best = {}
    for m, (oid, _) in enumerate(pairs):
        best[oid] = np.maximum(best[oid], out[:, m]) if oid in best else out[:, m].copy()
    return best, out, pairs


def close_array(close_s: dict, ncells: int) -> np.ndarray:
    a = np.full(ncells, NONE, np.int64)
    for c, b in close_s.items():
        a[int(c)] = int(b)
    return a
