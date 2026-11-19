"""Random small networks for T1 / T2 (PROTOCOL section 5). Seeded; consistent in the sense that an edge cutoff never
exceeds the wait cutoff of its tail (as holds on the real graph, where an edge's first segment is the tail's own cell)."""
from __future__ import annotations

import random

from .solver import BIG, Net


def make(seed, *, unlimited=False, max_t=12, bin_s=3):
    rnd = random.Random(seed)
    n = rnd.randint(4, 6)
    E = rnd.randint(max(n, 5), 10)
    tail, head = [], []
    for _ in range(E):
        u = rnd.randrange(n)
        v = rnd.randrange(n)
        while v == u:
            v = rnd.randrange(n)
        tail.append(u); head.append(v)
    # make sure the origin (0) has an out edge and some edge reaches a shelter
    if not any(t == 0 for t in tail):
        tail[0] = 0
        if head[0] == 0:
            head[0] = 1
    D = [rnd.randint(1, 3) for _ in range(E)]
    lo = [BIG if rnd.random() < 0.4 else rnd.randint(2, max_t) for _ in range(E)]
    wcut = [BIG] * n
    for u in range(n):
        outs = [lo[j] for j in range(E) if tail[j] == u]
        if any(x >= BIG for x in outs) or not outs:
            wcut[u] = BIG if rnd.random() < 0.7 else max_t + 1
        else:
            wcut[u] = rnd.randint(max(outs), max_t + 2)
    for u in range(n):  # enforce lo_k <= wcut[tail k]
        for j in range(E):
            if tail[j] == u and wcut[u] < BIG and lo[j] > wcut[u]:
                lo[j] = wcut[u]
    forbid = set()
    for i in range(E):
        for j in range(E):
            if head[i] == tail[j] and rnd.random() < 0.25:
                forbid.add((i, j))
    ncap = None if unlimited else [rnd.randint(1, 2) for _ in range(E)]
    shelters = {}
    cand = [u for u in range(1, n)]
    for u in rnd.sample(cand, rnd.randint(1, min(2, len(cand)))):
        shelters[u] = rnd.randint(max_t - 4, max_t)
    net = Net(n, tail, head, D, lo, ncap, bin_s, forbid, wcut)
    return net, 0, shelters
