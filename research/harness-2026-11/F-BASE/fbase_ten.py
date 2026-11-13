"""F-BASE-TEN: a non-interval baseline (Iris's critique; Sofia's recommended published method).

The O2 contact relaxation as an explicit integer-tick time-expanded network (Cai, Kloks & Wong 1997; Zeitz 2023):
one node per (state, second), state = incoming edge (nE = origin start state), closed integer intervals. Arcs:
  * EDGE j from (s, t) to (j, t + D_j) when tail[j] = hd(s), (s, j) not forbidden, t not in EB_j, t + D_j <= H;
  * WAIT from (s, t) to (s, t + 1) when hd(s) is waitable, t not in WB_hd(s), t + 1 <= H.
Reachability is computed by a third-party graph search (scipy.sparse.csgraph.breadth_first_order) on the whole
graph. No interval reasoning and no code from fbase.py, the router, F-3.1 or F-3.2: own tokenizer for the INSTANCE
block (FORMAT.md) and own construction.

Goal: the smallest T with an admitted arrival in AC_hd: either the start (s0, dep) if dep in AC_hd(s0) (k = 0), or an
EDGE arc whose source node is reachable and whose arrival second lies in AC of the edge's head. The witness is the
BFS predecessor path to that arc's source plus the arc, written as WITNESS legs for F-3.2's checker.
"""
from __future__ import annotations

import numpy as np
import scipy
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import breadth_first_order


def parse(text):
    tok = text[text.index("INSTANCE"):text.index("END_INSTANCE")].split()
    it = iter(tok)
    nxt = lambda: next(it)  # noqa: E731
    assert nxt() == "INSTANCE"
    assert nxt() == "V"; nV = int(nxt()); assert nxt() == "E"; nE = int(nxt())
    assert nxt() == "DEP"; dep = int(nxt()); assert nxt() == "HOR"; H = int(nxt())
    assert nxt() == "ORIGIN"; origin = int(nxt()); assert nxt() == "START"; s0 = int(nxt())
    assert nxt() == "EDGES"
    tail, head, D = (np.empty(nE, np.int64) for _ in range(3))
    for j in range(nE):
        tail[j], head[j], D[j] = int(nxt()), int(nxt()), int(nxt())
    assert nxt() == "WAITABLE"
    waitable = np.zeros(nV, bool)
    for _ in range(int(nxt())):
        waitable[int(nxt())] = True
    assert nxt() == "FORBID"
    forbid = set()
    for _ in range(int(nxt())):
        forbid.add((int(nxt()), int(nxt())))

    def records(key):
        assert nxt() == key
        out = {}
        for _ in range(int(nxt())):
            k = int(nxt())
            out[k] = [(int(nxt()), int(nxt())) for _ in range(int(nxt()))]
        return out
    EB, WB, AC = records("EB"), records("WB"), records("AC")
    return dict(nV=nV, nE=nE, dep=dep, H=H, origin=origin, s0=s0, tail=tail, head=head, D=D, waitable=waitable,
                forbid=forbid, EB=EB, WB=WB, AC=AC)


def _mask(L, dep, intervals):
    """Boolean over seconds dep..H (offset index): True inside the closed intervals."""
    m = np.zeros(L, bool)
    for lo, hi in intervals:
        a, b = max(lo, dep) - dep, min(hi, dep + L - 1) - dep
        if a <= b:
            m[a:b + 1] = True
    return m


def count_arcs(I):
    nE, dep, H = I["nE"], I["dep"], I["H"]
    L = H - dep + 1
    hd = np.append(I["head"], I["origin"])
    out_by_node = {}
    for j in range(nE):
        out_by_node.setdefault(int(I["tail"][j]), []).append(j)
    pairs = [(s, j) for s in range(nE + 1) for j in out_by_node.get(int(hd[s]), ()) if (s, j) not in I["forbid"]]
    n_edge = sum(max(0, L - int(I["D"][j])) for _, j in pairs)  # upper bound (before EB removal)
    n_wait = int(I["waitable"][hd].sum()) * (L - 1)
    return pairs, n_edge + n_wait, (nE + 1) * L


def solve_ten(I, pairs=None):
    nE, dep, H = I["nE"], I["dep"], I["H"]
    L = H - dep + 1
    N = (nE + 1) * L
    hd = np.append(I["head"], I["origin"])
    if pairs is None:
        pairs = count_arcs(I)[0]
    idx = np.arange(L, dtype=np.int64)
    # departure-valid offsets per edge
    valid = {}
    by_j = {}
    for s, j in pairs:
        by_j.setdefault(j, []).append(s)
    rows, cols = [], []
    for j, ss in by_j.items():
        Dj = int(I["D"][j])
        ok = (idx + Dj <= L - 1) & ~_mask(L, dep, I["EB"].get(j, ()))
        t = idx[ok]
        valid[j] = t
        if t.size == 0:
            continue
        ss = np.asarray(ss, np.int64)
        rows.append((ss[:, None] * L + t[None, :]).ravel())
        cols.append(np.broadcast_to(j * L + t + Dj, (ss.size, t.size)).ravel())
    n_edge_arcs = int(sum(r.size for r in rows))
    for s in range(nE + 1):
        n = int(hd[s])
        if I["waitable"][n]:
            t = idx[(idx + 1 <= L - 1) & ~_mask(L, dep, I["WB"].get(n, ()))]
            rows.append(s * L + t)
            cols.append(s * L + t + 1)
    r = np.concatenate(rows).astype(np.int32) if rows else np.zeros(0, np.int32)
    c = np.concatenate(cols).astype(np.int32) if cols else np.zeros(0, np.int32)
    del rows, cols
    G = csr_matrix((np.ones(r.size, np.int8), (r, c)), shape=(N, N))
    start = I["s0"] * L
    order, pred = breadth_first_order(G, start, directed=True, return_predecessors=True)
    del G
    reached = np.zeros(N, bool)
    reached[order] = True
    # goal
    acc = np.zeros(N, bool)
    for j in range(nE):
        n = int(I["head"][j])
        if n in I["AC"]:
            acc[j * L:(j + 1) * L] = _mask(L, dep, I["AC"][n])
    if int(hd[I["s0"]]) in I["AC"] and _mask(L, dep, I["AC"][int(hd[I["s0"]])])[0]:
        return "ROUTE", dep, [], dict(nodes=N, arcs=int(r.size), edge_arcs=n_edge_arcs, reached=int(reached.sum()))
    er, ec = r[:n_edge_arcs], c[:n_edge_arcs]
    hit = reached[er] & acc[ec]
    stats = dict(nodes=N, arcs=int(r.size), edge_arcs=n_edge_arcs, reached=int(reached.sum()))
    if not hit.any():
        return "NO_ROUTE", None, [], stats
    times = ec[hit] % L
    k = int(np.argmin(times))
    src, dst = int(er[hit][k]), int(ec[hit][k])
    T = dep + int(dst % L)
    path = [src]
    while path[-1] != start:
        path.append(int(pred[path[-1]]))
    path = path[::-1] + [dst]
    legs = []
    for a, b in zip(path, path[1:]):
        sa, ta = divmod(a, L)
        sb, tb = divmod(b, L)
        n = int(hd[sa])
        wait_ok = (sa == sb and tb == ta + 1 and I["waitable"][n]
                   and not _mask(L, dep, I["WB"].get(n, ()))[ta] and b != dst)
        if wait_ok:
            legs.append(("W", n, dep + ta, dep + tb))
        else:
            legs.append(("E", sb, dep + ta, dep + tb))
    return "ROUTE", T, legs, stats


SCIPY_VERSION = scipy.__version__
