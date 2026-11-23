"""A faster, lighter backward deadline field: scalar fast path (change 1) and lower-bound pruning (change 2).

Drop-in companion to ``deadline_field.core.backward`` (that file is not changed). ``solve`` returns a ``FastField``
with the same ``inst``, ``R``, ``G`` and ``stats`` attributes as ``core.Field``, so ``core.issue_set``,
``core.issue_core`` and ``core.witness`` read it unchanged. See ``WRITEUP.md`` for the proofs.

Change 1, scalar fast path (``scalar=True``). Per edge state s the solver checks, on the instance it is given, the
hypotheses of THEOREM.md Theorem 2 restricted to what s can reach:

* M1 for every allowed successor edge j (its closures, inside the window where j can be started, are upward closed);
* M2 at head(s) if it is waitable (wait closures upward closed in the window);
* M3 for s itself (acceptance downward closed in the window), needed only for G_s;
* and the same, recursively, for every allowed successor j (j must be "G-clean").

A state that passes is "R-clean" (R_s is one interval, its end given by the recursion of Theorem 2(b)); if M3 also
holds it is "G-clean" (G_s is one interval). These states are solved by a reverse Dijkstra on the latest time, one
integer per state. Every other state ("dirty") is solved by the interval method of ``core.backward``, reading the
clean states' sets as fixed. Clean states never depend on dirty ones (the clean set is closed under successors), so
the two phases run one after the other. Nothing is assumed: a state is scalar only if its checks pass.

Change 2, lower-bound pruning (``prune_origins=[...]``). One forward Dijkstra from all given origins at departure 0,
ignoring closures, turns, waiting and acceptance, gives e(v), a lower bound on the arrival second at v of any journey
from any of those origins at any departure t >= 0. alpha_s = e(tail s) + D_s bounds the arrival over s. Every set
of state s is then kept only on [alpha_s, H]; pieces below alpha_s are discarded. ``issue_set``/``witness`` below
refuse (or, with ``fallback=True``, re-solve without pruning) for an origin that was not in the forward search.
"""
from __future__ import annotations

import heapq
import sys
from array import array
from pathlib import Path

_F31 = Path(__file__).resolve().parents[1] / "harness-2026-11" / "F-3.1"
if str(_F31) not in sys.path:
    sys.path.insert(0, str(_F31))

from deadline_field import intervals as iv  # noqa: E402
from deadline_field import core  # noqa: E402

INF = 1 << 60
NEG = -(1 << 60)

# state kinds
VOID, GCLEAN, RCLEAN, DIRTY = 0, 1, 2, 3


class _View:
    """Read-only sequence of interval lists: explicit lists for interval states, one piece built on demand for
    scalar states. Indexing returns a fresh list, so callers cannot change the field."""

    __slots__ = ("lists", "lo", "hi")

    def __init__(self, lists, lo, hi):
        self.lists, self.lo, self.hi = lists, lo, hi

    def __len__(self):
        return len(self.lists)

    def __getitem__(self, s):
        x = self.lists[s]
        if x is not None:
            return x
        lo, hi = self.lo[s], self.hi[s]
        return [(lo, hi)] if lo <= hi else []

    def __iter__(self):
        for s in range(len(self.lists)):
            yield self[s]


class FastField:
    """Same reading interface as ``core.Field``: ``inst``, ``R[s]``, ``G[s]`` (interval lists), ``stats``.

    With pruning, ``R[s]`` and ``G[s]`` are the true sets intersected with [alpha_s, H] and ``sources`` is the
    frozenset of origins of the forward search; without pruning ``sources`` is None and the sets are the full ones."""

    def __init__(self, inst, R, G, stats, sources, lo, kind):
        self.inst, self.R, self.G, self.stats = inst, R, G, stats
        self.sources = sources
        self.lo = lo            # per state: lower end of the kept window (0 without pruning)
        self.kind = kind        # per state: VOID / GCLEAN / RCLEAN / DIRTY
        self._unpruned = None


def _upward_ok(ivs, lo, hi):
    """Is ivs ∩ [lo, hi] empty or of the form [c, hi]? Returns (ok, c) with c = first closed second in the window,
    or hi + 1 if none. An empty window (lo > hi) is trivially ok."""
    if lo > hi:
        return True, hi + 1
    i = max(0, _bisect_piece(ivs, lo))
    first = None
    n = 0
    while i < len(ivs) and ivs[i][0] <= hi:
        a, b = ivs[i]
        if b >= lo:
            n += 1
            if first is None:
                first = (max(a, lo), min(b, hi))
        i += 1
    if n == 0:
        return True, hi + 1
    return (n == 1 and first[1] == hi), first[0]


def _downward_ok(ivs, lo, hi):
    """Is ivs ∩ [lo, hi] empty or of the form [lo, a]? Returns (ok, a) with a = last element (NEG if empty)."""
    if lo > hi:
        return True, NEG
    i = max(0, _bisect_piece(ivs, lo))
    first = None
    n = 0
    while i < len(ivs) and ivs[i][0] <= hi:
        a, b = ivs[i]
        if b >= lo:
            n += 1
            if first is None:
                first = (max(a, lo), min(b, hi))
        i += 1
    if n == 0:
        return True, NEG
    return (n == 1 and first[0] == lo), first[1]


def _bisect_piece(ivs, t):
    """Index of the last piece with start <= t (-1 if none)."""
    lo_, hi_ = 0, len(ivs)
    while lo_ < hi_:
        m = (lo_ + hi_) // 2
        if ivs[m][0] <= t:
            lo_ = m + 1
        else:
            hi_ = m
    return lo_ - 1


def dest_lower_bound(inst):
    """h(v): fire-free, turn-free lower bound on the travel time from v to any acceptance (core.static_to_dest)."""
    return core.static_to_dest(inst)


def forward_lower_bound(inst, origins):
    """e(v): fire-free, turn-free shortest travel time from the nearest origin (departure 0). INF if unreachable."""
    e = [INF] * inst.n_nodes
    heap = []
    for o in set(origins):
        e[o] = 0
        heap.append((0, o))
    heapq.heapify(heap)
    D, head, out = inst.D, inst.head, inst.out
    while heap:
        d, v = heapq.heappop(heap)
        if d != e[v]:
            continue
        for j in out[v]:
            w = head[j]
            nd = d + D[j]
            if nd < e[w]:
                e[w] = nd
                heapq.heappush(heap, (nd, w))
    return e


def solve(inst, *, scalar: bool = True, prune_origins=None, windows: bool = True) -> FastField:
    """Backward field with the scalar fast path (``scalar``) and/or lower-bound pruning (``prune_origins``: node
    indices of every origin that will be queried; None = no pruning). ``scalar=False, prune_origins=None`` runs the
    interval method on every state and returns the same sets as ``core.backward``.

    ``windows``: check M1 and M2 only on the seconds at which the edge (wait) can be part of an ACCEPTED journey,
    i.e. up to H - D_j - h(head j) (H - 1 - h(v)), h = ``core.static_to_dest`` (fire-free, turn-free lower bound on the
    remaining travel to any acceptance). False = the plain hypotheses of THEOREM.md on [0, H - D_j] and [0, H - 1].
    The sets returned are the same either way; only how many states take the scalar path changes."""
    E, H, D, B, W, A = len(inst.tail), inst.H, inst.D, inst.B, inst.W, inst.A
    head, tail, waitable = inst.head, inst.tail, inst.waitable
    pred = [[i for i in inst.inc[tail[j]] if (i, j) not in inst.forbidden] for j in range(E)]

    # ---- windows (change 2) -------------------------------------------------------------------------------------
    if prune_origins is not None:
        sources = frozenset(int(o) for o in prune_origins)
        e = forward_lower_bound(inst, sources)
        lo_s = array("q", (min(e[tail[j]] + D[j], H + 1) for j in range(E)))   # alpha_s, capped at H + 1
        lo_start = [e[tail[j]] for j in range(E)]                              # earliest start second on j
        lo_wait = e                                                            # earliest second at v
    else:
        sources = None
        lo_s = array("q", bytes(8 * E))
        lo_start = None
        lo_wait = None

    kind = bytearray([DIRTY]) * E
    hi_r = array("q", [NEG]) * E      # scalar end of R_s (clean states)
    hi_g = array("q", [NEG]) * E      # scalar end of G_s (G-clean states)
    n_void = 0
    for s in range(E):
        if lo_s[s] > H:
            kind[s] = VOID
            n_void += 1

    # ---- hypotheses, per state (change 1) ------------------------------------------------------------------------
    if scalar:
        hd = dest_lower_bound(inst) if windows else [0] * inst.n_nodes
        c = array("q", [0]) * E        # first closed start second of j inside its window (M1 holds)
        m1 = bytearray(E)
        for j in range(E):
            lo = 0 if lo_start is None else lo_start[j]
            ok, cj = _upward_ok(B[j], lo, H - D[j] - hd[head[j]])
            m1[j] = ok
            c[j] = cj
        m2 = bytearray(inst.n_nodes)
        for v in range(inst.n_nodes):
            if not waitable[v]:
                m2[v] = 1
            else:
                lo = 0 if lo_wait is None else lo_wait[v]
                m2[v] = _upward_ok(W[v], lo, H - 1 - hd[v])[0]
        a_end = array("q", [NEG]) * E
        m3 = bytearray(E)
        for s in range(E):
            ok, a = _downward_ok(A[s], lo_s[s], H)
            m3[s] = ok
            a_end[s] = a
        # R-dirty: head wait fails M2, or some allowed successor fails M1 or is not G-clean. Not G-clean: R-dirty or
        # M3 fails. VOID states have empty windows: their sets are empty, a valid (empty) prefix; they are G-clean.
        rdirty = bytearray(E)
        gdirty = bytearray(E)
        queue = []
        for s in range(E):
            if kind[s] == VOID:
                continue
            if not m2[head[s]]:
                rdirty[s] = 1
            if rdirty[s] or not m3[s]:
                gdirty[s] = 1
                queue.append(s)
        for j in range(E):
            if not m1[j]:
                for s in pred[j]:
                    if kind[s] != VOID and not rdirty[s]:
                        rdirty[s] = 1
                        if not gdirty[s]:
                            gdirty[s] = 1
                            queue.append(s)
        while queue:
            j = queue.pop()
            for s in pred[j]:
                if kind[s] != VOID and not rdirty[s]:
                    rdirty[s] = 1
                    if not gdirty[s]:
                        gdirty[s] = 1
                        queue.append(s)
        for s in range(E):
            if kind[s] == VOID:
                continue
            kind[s] = DIRTY if rdirty[s] else (RCLEAN if gdirty[s] else GCLEAN)

        # ---- scalar phase: reverse Dijkstra on the latest time, clean states only ------------------------------
        heap = []
        for j in range(E):
            if kind[j] == GCLEAN and a_end[j] >= lo_s[j]:
                hi_g[j] = a_end[j]
                heap.append((-a_end[j], j))
        heapq.heapify(heap)
        spops = 0
        while heap:
            negl, j = heapq.heappop(heap)
            lj = -negl
            if lj != hi_g[j]:
                continue
            spops += 1
            v = lj - D[j]
            cj1 = c[j] - 1
            if cj1 < v:
                v = cj1
            for s in pred[j]:
                k = kind[s]
                if k == DIRTY or k == VOID or v < lo_s[s] or v <= hi_r[s]:
                    continue
                hi_r[s] = v
                if k == GCLEAN and v > hi_g[s]:
                    hi_g[s] = v
                    heapq.heappush(heap, (-v, s))
        scalar_pops = spops
    else:
        for s in range(E):
            if kind[s] != VOID:
                kind[s] = DIRTY
        scalar_pops = 0

    # ---- interval phase (core.backward on dirty states, windows applied) -------------------------------------
    Rl = [None] * E
    Gl = [None] * E
    for s in range(E):
        if kind[s] == DIRTY:
            Rl[s] = []
        elif kind[s] == VOID:
            Rl[s] = []
            Gl[s] = []
        elif kind[s] == RCLEAN:
            lo = lo_s[s]
            Gl[s] = iv.normalize(([(lo, hi_r[s])] if hi_r[s] >= lo else []) + _clip(A[s], lo, H))
    Aw = [None] * E
    heap = []
    pushes = pops = 0
    for j in range(E):
        k = kind[j]
        if k == VOID:
            continue
        if not any(kind[s] == DIRTY for s in pred[j]):
            if k == DIRTY:
                Aw[j] = _clip(A[j], lo_s[j], H)
            continue
        if k == DIRTY:
            Aw[j] = _clip(A[j], lo_s[j], H)
            pieces = Aw[j]
        elif k == GCLEAN:
            pieces = [(lo_s[j], hi_g[j])] if hi_g[j] >= lo_s[j] else []
        else:
            pieces = Gl[j]
        for lo, hi in pieces:
            heap.append((-hi, j, lo, hi))
            pushes += 1
    heapq.heapify(heap)
    while heap:
        _, j, lo, hi = heapq.heappop(heap)
        pops += 1
        a, b = max(lo - D[j], 0), hi - D[j]
        if a > b:
            continue
        cand = iv.subtract((a, b), B[j])
        if not cand:
            continue
        for s in pred[j]:
            if kind[s] != DIRTY:
                continue
            ls = lo_s[s]
            new = _clip(cand, ls, H) if ls > 0 else cand
            if not new:
                continue
            Rs = Rl[s]
            new = iv.subtract_all(new, Rs)
            if not new:
                continue
            hv = head[s]
            if waitable[hv]:
                ext = []
                for p in new:
                    lo2, hi2 = core._wait_close(p, W[hv], Rs)
                    if lo2 < ls:
                        lo2 = ls
                    ext.extend(iv.subtract((lo2, hi2), Rs))
                new = iv.normalize(ext)
                new = iv.subtract_all(new, Rs)
            for p in new:
                iv.add(Rs, p)
            As = Aw[s]
            for p in new:
                for q in iv.subtract(p, As):
                    heapq.heappush(heap, (-q[1], s, q[0], q[1]))
                    pushes += 1
    for s in range(E):
        if kind[s] == DIRTY:
            Gl[s] = iv.normalize(Rl[s] + Aw[s])

    # R view: scalar states give [lo_s, hi_r]; G view: G-clean give [lo_s, hi_g]
    Rv = _View(Rl, lo_s, hi_r)
    Gv = _View(Gl, lo_s, hi_g)
    counts = {"states": E, "void": n_void,
              "g_clean": sum(1 for k in kind if k == GCLEAN),
              "r_clean_only": sum(1 for k in kind if k == RCLEAN),
              "interval": sum(1 for k in kind if k == DIRTY)}
    stats = {"pushes": pushes, "pops": pops, "scalar_pops": scalar_pops, "kinds": counts,
             "pieces": sum(len(r) for r in Rl if r) + sum(1 for s in range(E) if Rl[s] is None and hi_r[s] >= lo_s[s]),
             "scalar": scalar, "pruned": sources is not None, "windows": windows}
    if scalar:
        stats["hypotheses"] = {"m1_fail_edges": E - sum(m1), "m2_fail_nodes": inst.n_nodes - sum(m2),
                               "m3_fail_states": E - sum(m3)}
    return FastField(inst, Rv, Gv, stats, sources, lo_s, kind)


def _clip(ivs, lo, hi):
    if lo <= 0 and hi >= (ivs[-1][1] if ivs else 0):
        return list(ivs)
    out = []
    for a, b in ivs:
        if b < lo or a > hi:
            continue
        out.append((max(a, lo), min(b, hi)))
    return out


# ---- reading the field ------------------------------------------------------------------------------------------

def _for_origin(fld: FastField, o: int, fallback: bool):
    if fld.sources is None or o in fld.sources:
        return fld
    if not fallback:
        raise ValueError("origin %d was not in the forward search of this pruned field; pruning must be off for it" % o)
    if fld._unpruned is None:
        fld._unpruned = solve(fld.inst, scalar=fld.stats["scalar"], prune_origins=None, windows=fld.stats["windows"])
    return fld._unpruned


def issue_set(fld: FastField, o: int, *, fallback: bool = False):
    """Feas(o). For a pruned field, o must be one of its sources; otherwise this raises, or with ``fallback`` reads
    an unpruned field built for the purpose (pruning off for that origin)."""
    return core.issue_set(_for_origin(fld, o, fallback), o)


def witness(fld: FastField, o: int, t: int, *, fallback: bool = False):
    return core.witness(_for_origin(fld, o, fallback), o, t)


def check_fixed_point(fld: FastField):
    """Certificate, independent of the solving order (core.check_fixed_point, windowed): for every state s,
    R[s] must EQUAL [alpha_s, H] ∩ (right-hand side of equation (E) on the stored sets), and G[s] = R[s] ∪ (A_s ∩
    [alpha_s, H]). Without pruning alpha_s = 0 and this is exactly core.check_fixed_point. The windowed equation has a
    unique solution (downward induction on t), so equality proves the stored sets are the true sets on their windows.
    """
    inst = fld.inst
    E, H = len(inst.tail), inst.H
    for s in range(E):
        lo = fld.lo[s]
        if lo > H:
            if fld.R[s] or fld.G[s]:
                raise AssertionError("void state %d has a non-empty set" % s)
            continue
        hv = inst.head[s]
        rhs = []
        for j in inst.out[hv]:
            if (s, j) in inst.forbidden:
                continue
            for a0, b0 in fld.G[j]:
                a, b = max(a0 - inst.D[j], 0), b0 - inst.D[j]
                if a <= b:
                    rhs.extend(iv.subtract((a, b), inst.B[j]))
        if inst.waitable[hv]:
            for a0, b0 in fld.R[s]:
                a, b = max(a0 - 1, 0), b0 - 1
                if a <= b:
                    rhs.extend(iv.subtract((a, b), inst.W[hv]))
        rhs = _clip(iv.normalize(rhs), lo, H)
        if rhs != fld.R[s]:
            raise AssertionError("fixed point violated at state %d: R=%r rhs=%r" % (s, fld.R[s][:4], rhs[:4]))
        if fld.G[s] != iv.normalize(fld.R[s] + _clip(inst.A[s], lo, H)):
            raise AssertionError("G != R u A at state %d" % s)
    return E
