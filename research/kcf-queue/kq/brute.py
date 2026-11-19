"""Exhaustive vehicle-by-vehicle reference for T1. Shares no code with solver.py beyond reading the Net fields.
It enumerates every timed route of every vehicle (waiting anywhere allowed by the wait rule, every shelter, every
capacity-respecting entry time) and searches all joint assignments. Only for tiny instances."""
from __future__ import annotations

BIG = 1 << 60


def routes(net, origin, shelters, r, bins, tmax):
    """Yield every complete timed route (list of (edge, entry second)) for a vehicle released at r, given bin counts."""
    B = net.bin_s

    def room(j, t):
        if net.ncap is None:
            return True
        return bins.get((j, t // B), 0) < net.ncap[j]

    def rec(u, a, last, path):
        for k in net.out[u]:
            if last is not None and (last, k) in net.forbid:
                continue
            for t in range(a, min(net.lo[k] - 1, tmax) + 1):
                if t > a and t >= net.wcut[u]:
                    break
                if last is None and t >= net.wcut[u]:
                    break
                if not room(k, t):
                    continue
                a2 = t + net.D[k]
                if a2 > tmax:
                    continue
                path.append((k, t))
                v = net.head[k]
                if v in shelters and a2 <= shelters[v]:
                    yield list(path)
                else:
                    yield from rec(v, a2, k, path)
                path.pop()

    yield from rec(origin, r, None, [])


def feasible(net, origin, shelters, releases, tmax):
    """True iff all vehicles (released at the given seconds) can be given routes jointly within capacity."""
    B = net.bin_s
    bins = {}

    def put(path, sign):
        if net.ncap is None:
            return
        for j, t in path:
            key = (j, t // B)
            bins[key] = bins.get(key, 0) + sign
            if bins[key] == 0:
                del bins[key]

    def go(i):
        if i == len(releases):
            return True
        for p in routes(net, origin, shelters, releases[i], bins, tmax):
            put(p, 1)
            ok = go(i + 1)
            put(p, -1)
            if ok:
                return True
        return False

    return go(0)
