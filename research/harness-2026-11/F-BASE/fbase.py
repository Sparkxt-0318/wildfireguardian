"""F-BASE: independent exact earliest-arrival baseline on the O2 integer instance, plus naive baselines.

Reads ONLY the ``INSTANCE`` block of a ``.wfgc`` bundle (F-3.2 FORMAT.md). Shares no code with the router
(experimental/sipp-routing), Richard's F-3.1 field, or Thomas's checkers/generators. Integers only.

Semantics (FORMAT.md): state s = incoming edge (s = nE is the origin start state); from (s, t):
  edge j:  tail[j] = hd(s), (s, j) not forbidden, t not in EB_j, t + D_j <= H  ->  (j, t + D_j), ADMITTED
  wait:    hd(s) waitable, t not in WB_hd(s), t + 1 <= H                     ->  (s, t + 1), not admitted
Goal: smallest admitted arrival T in AC_hd(state), starting admitted at (s0, dep). Otherwise NO_ROUTE.

Solvers:
  exact   interval-set labels per state, chronological sweep (earliest-label dominance is invalid at
          non-waitable nodes, so whole reachable sets are kept)
  n1      classic time-dependent Dijkstra: one earliest label per state, waiting allowed everywhere (also at
          the destination), WB ignored  -> unsound under waiting restrictions
  n2      one earliest label per state, waiting rules respected  -> incomplete (false NO_ROUTE / late T)
  n3      exact sweep but destinations accept on any arrival (AC windows ignored)  -> early T
  brute   time-expanded BFS over every (state, second); reference for tests on small instances
"""
from __future__ import annotations

import bisect
import heapq
from dataclasses import dataclass, field

# ------------------------------------------------------------------------------------------------ parsing


@dataclass
class Instance:
    nV: int
    nE: int
    dep: int
    H: int
    origin: int
    s0: int
    tail: list
    head: list
    D: list
    waitable: set
    forbid: set
    EB: dict = field(default_factory=dict)   # edge -> sorted list of (lo, hi)
    WB: dict = field(default_factory=dict)   # node -> sorted list of (lo, hi)
    AC: dict = field(default_factory=dict)   # node -> sorted list of (lo, hi)

    def hd(self, s):
        return self.origin if s == self.nE else self.head[s]


def _ivlist(tok, i):
    m = int(tok[i]); i += 1
    out = []
    for _ in range(m):
        out.append((int(tok[i]), int(tok[i + 1]))); i += 2
    return out, i


def parse_instance(text: str) -> Instance:
    start = text.index("INSTANCE")
    end = text.index("END_INSTANCE")
    tok = text[start:end].split()
    assert tok[0] == "INSTANCE"
    i = 1

    def expect(word):
        nonlocal i
        if tok[i] != word:
            raise ValueError(f"expected {word}, got {tok[i]}")
        i += 1

    expect("V"); nV = int(tok[i]); i += 1
    expect("E"); nE = int(tok[i]); i += 1
    expect("DEP"); dep = int(tok[i]); i += 1
    expect("HOR"); H = int(tok[i]); i += 1
    expect("ORIGIN"); origin = int(tok[i]); i += 1
    expect("START"); s0 = int(tok[i]); i += 1
    expect("EDGES")
    tail, head, D = [], [], []
    for _ in range(nE):
        tail.append(int(tok[i])); head.append(int(tok[i + 1])); D.append(int(tok[i + 2])); i += 3
    expect("WAITABLE"); k = int(tok[i]); i += 1
    waitable = {int(x) for x in tok[i:i + k]}; i += k
    expect("FORBID"); k = int(tok[i]); i += 1
    forbid = set()
    for _ in range(k):
        forbid.add((int(tok[i]), int(tok[i + 1]))); i += 2
    blocks = {}
    for name in ("EB", "WB", "AC"):
        expect(name); k = int(tok[i]); i += 1
        d = {}
        for _ in range(k):
            key = int(tok[i]); i += 1
            d[key], i = _ivlist(tok, i)
        blocks[name] = d
    if i != len(tok):
        raise ValueError("trailing tokens in INSTANCE")
    return Instance(nV, nE, dep, H, origin, s0, tail, head, D, waitable, forbid, blocks["EB"], blocks["WB"], blocks["AC"])


def instance_text(inst: Instance) -> str:
    """Serialise to the FORMAT.md INSTANCE block (for committed smallest-failure examples)."""
    def ivs(lst):
        return " ".join([str(len(lst))] + [f"{a} {b}" for a, b in lst])
    lines = ["INSTANCE", f"V {inst.nV} E {inst.nE}", f"DEP {inst.dep} HOR {inst.H} ORIGIN {inst.origin} START {inst.s0}",
             "EDGES"]
    lines += [f"{inst.tail[j]} {inst.head[j]} {inst.D[j]}" for j in range(inst.nE)]
    w = sorted(inst.waitable)
    lines.append(" ".join(["WAITABLE", str(len(w))] + [str(x) for x in w]))
    f = sorted(inst.forbid)
    lines.append(" ".join(["FORBID", str(len(f))] + [f"{s} {j}" for s, j in f]))
    for name, d in (("EB", inst.EB), ("WB", inst.WB), ("AC", inst.AC)):
        lines.append(f"{name} {len(d)}")
        lines += [f"{key} {ivs(d[key])}" for key in sorted(d)]
    lines.append("END_INSTANCE")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------------------- interval helpers

def contains(ivs, t):
    k = bisect.bisect_right(ivs, (t, float("inf"))) - 1
    return k >= 0 and ivs[k][0] <= t <= ivs[k][1]


def next_in(ivs, t):
    """Smallest element >= t of the interval set, or None."""
    k = bisect.bisect_right(ivs, (t, float("inf"))) - 1
    if k >= 0 and ivs[k][1] >= t:
        return t
    k += 1
    return ivs[k][0] if k < len(ivs) else None


def subtract(lo, hi, ivs):
    """[lo, hi] minus a sorted disjoint interval list -> list of pieces."""
    out = []
    k = max(bisect.bisect_right(ivs, (lo, float("inf"))) - 1, 0)
    cur = lo
    while k < len(ivs) and ivs[k][0] <= hi:
        a, b = ivs[k]
        if b >= cur:
            if a > cur:
                out.append((cur, min(hi, a - 1)))
            cur = max(cur, b + 1)
            if cur > hi:
                return out
        k += 1
    if cur <= hi:
        out.append((cur, hi))
    return out


def intersect_first(lo, hi, ivs):
    """Smallest t in [lo, hi] that lies in ivs, or None."""
    t = next_in(ivs, lo)
    return t if t is not None and t <= hi else None


def add_interval(ivs, a, b):
    """Insert [a, b] (disjoint from ivs) and merge adjacent neighbours."""
    k = bisect.bisect_left(ivs, (a, b))
    ivs.insert(k, (a, b))
    if k + 1 < len(ivs) and ivs[k + 1][0] == b + 1:
        ivs[k] = (ivs[k][0], ivs[k + 1][1]); del ivs[k + 1]
    if k > 0 and ivs[k - 1][1] + 1 == ivs[k][0]:
        ivs[k - 1] = (ivs[k - 1][0], ivs[k][1]); del ivs[k]


# ------------------------------------------------------------------------------------------------ exact solver

def solve_exact(inst: Instance, *, respect_ac=True):
    """Return (claim, T, witness). claim in {'ROUTE','NO_ROUTE'}; witness = list of legs (E j a b) / (W n a b)."""
    out_edges = [[] for _ in range(inst.nV)]
    for j in range(inst.nE):
        out_edges[inst.tail[j]].append(j)
    dests = set(inst.AC)

    def accepts(node, lo, hi):
        if node not in dests:
            return None
        return lo if not respect_ac else intersect_first(lo, hi, inst.AC[node])

    R = {}               # state -> reachable interval list
    segs = []            # (state, a, b, e, parent_seg, edge)
    best = (None, None)  # (T, (parent_seg, edge)) ; parent None means the initial state at dep
    heap = []
    if accepts(inst.hd(inst.s0), inst.dep, inst.dep) is not None:
        return "ROUTE", inst.dep, []
    heapq.heappush(heap, (inst.dep, inst.dep, inst.s0, -1, -1))
    counter = 0
    while heap:
        lo, hi, s, parent, edge = heapq.heappop(heap)
        if best[0] is not None and lo >= best[0]:
            break
        node = inst.hd(s)
        Rs = R.setdefault(s, [])
        for a, b in subtract(lo, hi, Rs):
            e = b
            if node in inst.waitable:
                w = next_in(inst.WB.get(node, []), b)
                e = min(inst.H, w if w is not None else inst.H)
                # waiting from b reaches up to e, but stop at the first already-known second
                k = next_in(Rs, b + 1)
                if k is not None and k <= e:
                    e = k - 1
            add_interval(Rs, a, e)
            seg_id = len(segs)
            segs.append((s, a, b, e, parent, edge))
            counter += 1
            for j in out_edges[node]:
                if (s, j) in inst.forbid:
                    continue
                for d0, d1 in subtract(a, min(e, inst.H - inst.D[j]), inst.EB.get(j, [])):
                    t0, t1 = d0 + inst.D[j], d1 + inst.D[j]
                    g = accepts(inst.head[j], t0, t1)
                    if g is not None and (best[0] is None or g < best[0]):
                        best = (g, (seg_id, j))
                    heapq.heappush(heap, (t0, t1, j, seg_id, j))
    if best[0] is None:
        return "NO_ROUTE", None, []
    return "ROUTE", best[0], _witness(inst, segs, best)


def _witness(inst, segs, best):
    T, (seg_id, j) = best
    legs = [("E", j, T - inst.D[j], T)]
    t = T - inst.D[j]
    while True:
        s, a, b, e, parent, edge = segs[seg_id]
        if t > b:  # reached by waiting from b
            legs.extend(("W", inst.hd(s), x, x + 1) for x in range(t - 1, b - 1, -1))
            t = b
        if parent < 0:
            break
        legs.append(("E", edge, t - inst.D[edge], t))
        t = t - inst.D[edge]
        # find the parent segment piece containing t: the creating segment
        seg_id = parent
        ps, pa, pb, pe, _, _ = segs[seg_id]
        assert pa <= t <= pe, "witness reconstruction left the parent segment"
    legs.reverse()
    return legs


# ------------------------------------------------------------------------------------------ naive baselines

def solve_n1(inst: Instance):
    """Classic TD-Dijkstra: one earliest label per state; waiting allowed anywhere (WB ignored), incl. at the
    destination until its acceptance window opens."""
    out_edges = [[] for _ in range(inst.nV)]
    for j in range(inst.nE):
        out_edges[inst.tail[j]].append(j)
    label = {inst.s0: inst.dep}
    heap = [(inst.dep, inst.s0)]
    best = None
    while heap:
        t, s = heapq.heappop(heap)
        if label.get(s) != t or (best is not None and t >= best):
            continue
        node = inst.hd(s)
        if node in inst.AC:
            g = next_in(inst.AC[node], t)
            if g is not None and g <= inst.H and (best is None or g < best):
                best = g
        for j in out_edges[node]:
            if (s, j) in inst.forbid:
                continue
            d = t
            eb = inst.EB.get(j, [])
            while d is not None and contains(eb, d):
                k = bisect.bisect_right(eb, (d, float("inf"))) - 1
                d = eb[k][1] + 1
            if d is None or d + inst.D[j] > inst.H:
                continue
            a = d + inst.D[j]
            if a < label.get(j, float("inf")):
                label[j] = a
                heapq.heappush(heap, (a, j))
    return ("ROUTE", best) if best is not None else ("NO_ROUTE", None)


def solve_n2(inst: Instance):
    """One earliest label per state; waiting rules respected (only at waitable nodes, not at WB starts);
    acceptance only at admitted arrival seconds."""
    out_edges = [[] for _ in range(inst.nV)]
    for j in range(inst.nE):
        out_edges[inst.tail[j]].append(j)
    if inst.hd(inst.s0) in inst.AC and contains(inst.AC[inst.hd(inst.s0)], inst.dep):
        return "ROUTE", inst.dep
    label = {inst.s0: inst.dep}
    heap = [(inst.dep, inst.s0)]
    best = None
    while heap:
        t, s = heapq.heappop(heap)
        if label.get(s) != t or (best is not None and t >= best):
            continue
        node = inst.hd(s)
        if node in inst.waitable:
            w = next_in(inst.WB.get(node, []), t)
            reach_hi = min(inst.H, w if w is not None else inst.H)
        else:
            reach_hi = t
        for j in out_edges[node]:
            if (s, j) in inst.forbid:
                continue
            free = subtract(t, min(reach_hi, inst.H - inst.D[j]), inst.EB.get(j, []))
            if not free:
                continue
            a = free[0][0] + inst.D[j]
            hn = inst.head[j]
            if hn in inst.AC and contains(inst.AC[hn], a) and (best is None or a < best):
                best = a
            if a < label.get(j, float("inf")):
                label[j] = a
                heapq.heappush(heap, (a, j))
    return ("ROUTE", best) if best is not None else ("NO_ROUTE", None)


def solve_n3(inst: Instance):
    claim, T, _ = solve_exact(inst, respect_ac=False)
    return claim, T


# ------------------------------------------------------------------------------------------- brute force

def solve_brute(inst: Instance):
    """Time-expanded BFS over all (state, second) pairs. Small instances only."""
    if inst.hd(inst.s0) in inst.AC and contains(inst.AC[inst.hd(inst.s0)], inst.dep):
        return "ROUTE", inst.dep
    frontier = {inst.s0}
    best = None
    reach = {inst.dep: {inst.s0}}
    for t in range(inst.dep, inst.H + 1):
        states = reach.pop(t, set())
        for s in states:
            node = inst.hd(s)
            if node in inst.waitable and not contains(inst.WB.get(node, []), t) and t + 1 <= inst.H:
                reach.setdefault(t + 1, set()).add(s)
            for j in range(inst.nE):
                if inst.tail[j] != node or (s, j) in inst.forbid or contains(inst.EB.get(j, []), t):
                    continue
                a = t + inst.D[j]
                if a > inst.H:
                    continue
                hn = inst.head[j]
                if hn in inst.AC and contains(inst.AC[hn], a) and (best is None or a < best):
                    best = a
                reach.setdefault(a, set()).add(j)
        if best is not None and best <= t + 1:
            break
    return ("ROUTE", best) if best is not None else ("NO_ROUTE", None)


def replay(inst: Instance, witness, T):
    """Independent lattice walker: True iff the witness is a legal path from (s0, dep) ending admitted at T in AC."""
    s, t = inst.s0, inst.dep
    admitted = True
    for kind, x, a, b in witness:
        if a != t:
            return False
        if kind == "E":
            j = x
            if inst.tail[j] != inst.hd(s) or (s, j) in inst.forbid or contains(inst.EB.get(j, []), a):
                return False
            if b != a + inst.D[j] or b > inst.H:
                return False
            s, t, admitted = j, b, True
        else:
            n = x
            if n != inst.hd(s) or n not in inst.waitable or contains(inst.WB.get(n, []), a) or b != a + 1 or b > inst.H:
                return False
            t, admitted = b, False
    node = inst.hd(s)
    return admitted and t == T and node in inst.AC and contains(inst.AC[node], t)
