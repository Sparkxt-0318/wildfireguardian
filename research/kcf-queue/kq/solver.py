"""KQ-1 solver (PROTOCOL.md section 3): sequential capacity reservation on a point-queue road network.

Generic: it sees only arrays, so the same code runs on random test networks and on the real road graph.
Net fields (all per edge j unless noted):
  tail, head, D            integer ends and travel seconds (D >= 1)
  lo                       edge may be entered at second t iff t < lo[j]   (BIG = never closes)
  ncap                     entries allowed per clock bin, or None for unlimited capacity
  bin_s                    bin length in seconds
  forbid                   set of (i, j): turn i -> j not allowed
  wcut[node]               a vehicle may wait at the node and leave at t > arrival only if t < wcut[node]
  out[node], inc[node]     edge lists
Village context: origin node, shelters {node: amax} (arrival a accepted iff a <= amax).
"""
from __future__ import annotations

import heapq

BIG = 1 << 60


class Net:
    def __init__(self, n, tail, head, D, lo, ncap, bin_s, forbid, wcut):
        self.n, self.tail, self.head, self.D, self.lo = n, list(tail), list(head), list(D), list(lo)
        self.ncap = None if ncap is None else list(ncap)
        self.bin_s, self.forbid, self.wcut = bin_s, set(forbid), list(wcut)
        self.E = len(self.tail)
        self.out = [[] for _ in range(n)]
        self.inc = [[] for _ in range(n)]
        for j in range(self.E):
            self.out[self.tail[j]].append(j)
            self.inc[self.head[j]].append(j)


def latest_labels(net: Net, shelters: dict):
    """ell[j] = largest arrival second at head(j) over j from which some route reaches an accepted shelter in free flow
    (-1: none). Latest-label Dijkstra (PROTOCOL 3.6 (i))."""
    ell = [-1] * net.E
    heap = []
    for s, amax in shelters.items():
        if amax < 0:
            continue
        for j in net.inc[s]:
            if amax > ell[j]:
                ell[j] = amax
                heap.append((-amax, j))
    heapq.heapify(heap)
    while heap:
        negl, j = heapq.heappop(heap)
        if -negl != ell[j]:
            continue
        u = min(net.lo[j] - 1, ell[j] - net.D[j])
        if u < 0:
            continue
        for i in net.inc[net.tail[j]]:
            if (i, j) in net.forbid:
                continue
            if u > ell[i]:
                ell[i] = u
                heapq.heappush(heap, (-u, i))
    return ell


def static_h(net: Net, shelter_nodes):
    """Free-flow travel-time lower bound from every node to the nearest shelter node (reverse Dijkstra on D)."""
    h = [BIG] * net.n
    heap = []
    for s in shelter_nodes:
        h[s] = 0
        heap.append((0, s))
    heapq.heapify(heap)
    while heap:
        d, v = heapq.heappop(heap)
        if d != h[v]:
            continue
        for j in net.inc[v]:
            u = net.tail[j]
            nd = d + net.D[j]
            if nd < h[u]:
                h[u] = nd
                heapq.heappush(heap, (nd, u))
    return h


class Ctx:
    """Per-village routing context at one issue hour."""

    def __init__(self, net, origin, shelters, ell=None, h=None):
        self.origin, self.shelters = origin, shelters
        self.ell = ell if ell is not None else latest_labels(net, shelters)
        self.h = h if h is not None else static_h(net, shelters.keys())

    def L0(self, net):
        """Free-flow latest departure second of one vehicle (None if there is none)."""
        best = None
        cut = net.wcut[self.origin]
        for k in net.out[self.origin]:
            u = min(net.lo[k] - 1, self.ell[k] - net.D[k], cut - 1)
            if u >= 0 and (best is None or u > best):
                best = u
        return best


def _earliest(net, j, a, bins):
    """Earliest second t >= a whose clock bin of edge j has room (or a if capacity is unlimited)."""
    if net.ncap is None:
        return a
    B, cap = net.bin_s, net.ncap[j]
    t = a
    while True:
        m = t // B
        if bins.get((j, m), 0) < cap:
            return t
        t = (m + 1) * B


def route(net: Net, ctx: Ctx, r: int, bins: dict):
    """Earliest-arrival timed path for one vehicle released at r, given reservations `bins` {(edge, bin): count}.
    Returns [(edge, entry second), ...] or None."""
    ell, h, D, lo = ctx.ell, ctx.h, net.D, net.lo
    o = ctx.origin
    cut_o = net.wcut[o]
    arr, par, heap = {}, {}, []
    for k in net.out[o]:
        if ell[k] < 0:
            continue
        t = _earliest(net, k, r, bins)
        if t >= cut_o or t > min(lo[k] - 1, ell[k] - D[k]):
            continue
        a = t + D[k]
        if a < arr.get(k, BIG):
            arr[k], par[k] = a, (None, t)
            heapq.heappush(heap, (a + h[net.head[k]], a, k))
    forbid, shelters = net.forbid, ctx.shelters
    while heap:
        _, a, j = heapq.heappop(heap)
        if arr[j] != a:
            continue
        v = net.head[j]
        amax = shelters.get(v)
        if amax is not None and a <= amax:
            path = []
            cur = j
            while cur is not None:
                p, t = par[cur]
                path.append((cur, t))
                cur = p
            path.reverse()
            return path
        wc = net.wcut[v]
        for k in net.out[v]:
            if ell[k] < 0 or (j, k) in forbid:
                continue
            t = _earliest(net, k, a, bins)
            if t > min(lo[k] - 1, ell[k] - D[k]) or (t > a and t >= wc):
                continue
            a2 = t + D[k]
            if a2 < arr.get(k, BIG):
                arr[k], par[k] = a2, (j, t)
                heapq.heappush(heap, (a2 + h[net.head[k]], a2, k))
    return None


def reserve(net, path, bins, log=None):
    if net.ncap is None:
        return
    B = net.bin_s
    for j, t in path:
        key = (j, t // B)
        bins[key] = bins.get(key, 0) + 1
        if log is not None:
            log.append(key)


def release(bins, log):
    for key in log:
        c = bins[key] - 1
        if c:
            bins[key] = c
        else:
            del bins[key]
    log.clear()


def releases(N, s, W):
    return [s + (W * (2 * k + 1)) // (2 * N) for k in range(N)]


def try_start(net, ctx, N, s, W, base_bins):
    """Feasibility of start s for one village on top of `base_bins` (not modified). Returns paths or None."""
    bins = dict(base_bins) if net.ncap is not None else {}
    paths = []
    for r in releases(N, s, W):
        p = route(net, ctx, r, bins)
        if p is None:
            return None
        reserve(net, p, bins)
        paths.append(p)
    return paths


def latest_start(net, ctx, N, W, base_bins, hi, step=10):
    """Largest multiple of `step` in [0, hi] for which try_start succeeds, by bisection (monotone assumed).
    Returns (s*, paths) or (None, None) if even s = 0 fails."""
    p0 = try_start(net, ctx, N, 0, W, base_bins)
    if p0 is None:
        return None, None
    lo_i, best = 0, p0
    hi_i = hi // step
    # invariant: lo_i feasible
    while lo_i < hi_i:
        mid = (lo_i + hi_i + 1) // 2
        p = try_start(net, ctx, N, mid * step, W, base_bins)
        if p is not None:
            lo_i, best = mid, p
        else:
            hi_i = mid - 1
    return lo_i * step, best
