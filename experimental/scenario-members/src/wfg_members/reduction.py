"""Scenario reduction: choose K representative members from N trajectories, with redistributed weights.

Methods
  first_k             trajectories 0..K-1 (control; the trajectory prefix is invariant to N).
  forward_selection   greedy forward selection (Dupacova, Growe-Kuska and Romisch 2003, Math. Programming 95:493-511;
                      Heitsch and Romisch 2003, Comput. Optim. Appl. 24:187-206): repeatedly add the trajectory u that
                      minimises D_J = sum over deleted i of p_i * min_{j in J} c(i, j). O(K N^2).
  k_medoids           alternating k-medoids (assign to the nearest medoid, move each medoid to the cluster member of
                      least total distance) on the same distance matrix, k-medoids++ initialisation with a recorded seed.

Weights: every deleted trajectory gives its probability p_i (1/N) to its nearest kept trajectory (lowest index on ties),
so q_j = p_j + sum of the deleted masses nearest to j. These q_j are the member weights of every probability statement.

Distances (all three are kept and reported)
  edge_arrival   c(m, m') = sum_e w_e |min(a_m(e), T) - min(a_m'(e), T)|, a_m(e) the first departure second at which
                 member m alone makes a traversal of directed edge e meet flame (the sweep's occupancy rule), T the
                 horizon, w_e the edge length in metres. This is the distance in the space the checker consumes.
  first_burn_l1  L1 distance between first-burn-hour fields capped at horizon + 1 (unknown cells excluded).
  road_symdiff   road-weighted symmetric difference of the burned sets at the end of the horizon: weight 1 within
                 2 cells (Chebyshev) of a cell touched by a road edge bounding box, 0.1 elsewhere. It drops timing.

Extremes: for every corridor (the edge set of a mission's travel-only route) the trajectory with the earliest unsafe
time on the corridor is appended when it is strictly earlier than the shared present-fire value and not already kept,
so that "all members pass" is not optimistic about the corridor that matters. Weights are redistributed after appending.
Distances here are floating point; they only rank scenarios and never certify anything.
"""
from __future__ import annotations

import math

import numpy as np

METHODS = ("first_k", "forward_selection", "k_medoids")
DISTANCES = ("edge_arrival", "first_burn_l1", "road_symdiff")


# ------------------------------------------------------------------------------------------------ edge arrival times
class EdgeExposure:
    """Per (directed edge, cell) pairs with the occupancy fractions the sweep uses, for cells that ever burn."""

    def __init__(self, graph, cells, core):
        g = graph["grid"]
        res, x0, y0, W = float(g["resolution"]), float(g["x0"]), float(g["y0"]), int(g["width"])
        nodes = {n["id"]: n for n in graph["nodes"]}
        edges = graph["edges"]
        cells = sorted(set(int(c) for c in cells))
        self.E = len(edges)
        if not cells:
            self.pairs = np.zeros((0, 4))
            self.edge_len = np.zeros(0)
            self.edge_ids = np.zeros(0, dtype=np.int64)
            return
        rects = np.array([(x0 + (c % W) * res - 1, x0 + (c % W + 1) * res + 1, y0 + (c // W) * res - 1, y0 + (c // W + 1) * res + 1)
                          for c in cells])
        U = np.array([(float(nodes[e["u"]]["x"]), float(nodes[e["u"]]["y"])) for e in edges])
        V = np.array([(float(nodes[e["v"]]["x"]), float(nodes[e["v"]]["y"])) for e in edges])
        bx0, bx1 = np.minimum(U[:, 0], V[:, 0]), np.maximum(U[:, 0], V[:, 0])
        by0, by1 = np.minimum(U[:, 1], V[:, 1]), np.maximum(U[:, 1], V[:, 1])
        cellset = set(cells)
        rows = []
        cand = np.zeros(len(edges), bool)
        for lo in range(0, len(rects), 256):
            r = rects[lo:lo + 256]
            hit = ((bx0[:, None] <= r[None, :, 1]) & (bx1[:, None] >= r[None, :, 0]) & (by0[:, None] <= r[None, :, 3])
                   & (by1[:, None] >= r[None, :, 2])).any(axis=1)
            cand |= hit
        for i in np.flatnonzero(cand):
            e = edges[i]
            D = float(e["travel_ticks"])
            per = {}
            for o in core.edge_occupancies(e, 0, 1, 0, 1, graph, nodes):
                c = int(o["cell"])
                if c in cellset:
                    za, zb = float(o["start"]), float(o["end"])
                    a, b = per.get(c, (math.inf, -math.inf))
                    per[c] = (min(a, za), max(b, zb))
            for c, (za, zb) in per.items():
                rows.append((i, c, D * zb, D * za))
        self.pairs = np.array(rows, dtype=float) if rows else np.zeros((0, 4))
        self.edge_ids = np.unique(self.pairs[:, 0].astype(np.int64)) if rows else np.zeros(0, dtype=np.int64)
        length = np.hypot(V[:, 0] - U[:, 0], V[:, 1] - U[:, 1])
        self.edge_len = length[self.edge_ids]
        self.col = {int(e): j for j, e in enumerate(self.edge_ids)}

    def first_unsafe(self, births, T, horizon, current=(), R=0.0):
        """a(e) for one member: births {cell: second}; present fire cells active on [0, R). Returns [len(edge_ids)]."""
        out = np.full(self.edge_ids.size, float(horizon))
        if not self.pairs.size:
            return out
        start = np.full(int(self.pairs[:, 1].max()) + 1, np.inf)
        end = np.full_like(start, -np.inf)
        for c in current:
            if c < start.size and R > 0:
                start[c], end[c] = 0.0, R
        for c, b in births.items():
            if c < start.size:
                start[c], end[c] = float(b), float(b) + T
        cells = self.pairs[:, 1].astype(np.int64)
        b, e = start[cells], end[cells]
        lo = np.ceil(b - self.pairs[:, 2])
        hi = np.ceil(e - self.pairs[:, 3]) - 1
        ok = np.isfinite(b) & (np.maximum(lo, 0) <= np.minimum(hi, horizon))
        cols = np.array([self.col[int(i)] for i in self.pairs[ok, 0]], dtype=np.int64)
        np.minimum.at(out, cols, np.maximum(lo[ok], 0))
        return np.minimum(out, horizon)


def edge_arrival_matrix(exposure, births_list, T, horizon, current=(), R=0.0):
    return np.array([exposure.first_unsafe(b, T, horizon, current, R) for b in births_list]) if births_list else np.zeros((0, 0))


def l1_distance(X, w=None, budget=2_000_000):
    """Pairwise weighted L1 distance between rows of X, computed on the distinct rows and on varying columns only,
    in chunks of at most `budget` elements (bounded memory)."""
    X = np.asarray(X, dtype=np.float64)
    if w is not None:
        X = X * np.asarray(w, dtype=np.float64)[None]
    N = X.shape[0]
    if N == 0:
        return np.zeros((0, 0))
    varying = np.flatnonzero(X.max(axis=0) != X.min(axis=0))
    Y = X[:, varying]
    U, inv = np.unique(Y, axis=0, return_inverse=True)
    inv = np.asarray(inv).reshape(-1)
    n, c = U.shape
    Du = np.zeros((n, n))
    if c:
        rows = max(1, int(budget // max(1, n * c)))
        for lo in range(0, n, rows):
            Du[lo:lo + rows] = np.abs(U[lo:lo + rows, None, :] - U[None, :, :]).sum(axis=2)
    return Du[np.ix_(inv, inv)]


def distance_edge_arrival(A, edge_len):
    return l1_distance(A, edge_len)


def distance_first_burn_l1(fbh, horizon_hours):
    f = np.asarray(fbh).reshape(fbh.shape[0], -1).astype(np.int64)
    known = (f != -2).all(axis=0)
    capped = np.where(f == -1, horizon_hours + 1, f)[:, known]
    return l1_distance(capped)


def distance_road_symdiff(fbh, road_mask_native, horizon_hours, near=2, far_weight=0.1):
    f = np.asarray(fbh)
    burned = ((f >= 1) & (f <= horizon_hours)).reshape(f.shape[0], -1)
    m = np.asarray(road_mask_native, dtype=bool)
    H, W = m.shape
    dil = np.zeros_like(m)
    for dr in range(-near, near + 1):
        for dc in range(-near, near + 1):
            src = m[max(0, -dr):H - max(0, dr), max(0, -dc):W - max(0, dc)]
            dil[max(0, dr):H - max(0, -dr), max(0, dc):W - max(0, -dc)] |= src
    w = np.where(dil.ravel(), 1.0, far_weight)
    return l1_distance(burned.astype(float), w)


# ------------------------------------------------------------------------------------------------ selection
def redistribute(C, kept, p=None):
    N = C.shape[0]
    p = np.full(N, 1.0 / N) if p is None else np.asarray(p, float)
    kept = list(kept)
    sub = C[:, kept]
    nearest = np.argmin(sub, axis=1)            # lowest kept index among ties (kept is in selection order)
    for pos, j in enumerate(kept):
        nearest[j] = pos
    q = np.bincount(nearest, weights=p, minlength=len(kept))
    cost = float(sum(p[i] * sub[i].min() for i in range(N) if i not in set(kept)))
    return q, cost, nearest


def forward_selection(C, K, p=None):
    N = C.shape[0]
    p = np.full(N, 1.0 / N) if p is None else np.asarray(p, float)
    K = min(int(K), N)
    J, dmin, costs = [], np.full(N, np.inf), []
    for _ in range(K):
        cand = np.minimum(dmin[:, None], C)                 # [i, u]
        cost = p @ np.where(np.isfinite(cand), cand, 0.0) if J else p @ C
        cost = np.where(np.isin(np.arange(N), J), np.inf, cost)
        u = int(np.argmin(cost))
        J.append(u)
        dmin = np.minimum(dmin, C[:, u])
        costs.append(float(p @ dmin))
    return J, costs


def k_medoids(C, K, seed=0, p=None, max_iter=100):
    N = C.shape[0]
    K = min(int(K), N)
    rng = np.random.default_rng(seed)
    med = [int(rng.integers(N))]
    while len(med) < K:                                     # k-medoids++
        d = C[:, med].min(axis=1) ** 2
        if d.sum() <= 0:
            rest = [i for i in range(N) if i not in med]
            med.append(int(rest[0]))
            continue
        med.append(int(rng.choice(N, p=d / d.sum())))
    for _ in range(max_iter):
        assign = np.argmin(C[:, med], axis=1)
        new = []
        for k in range(K):
            members = np.flatnonzero(assign == k)
            if members.size == 0:
                new.append(med[k])
                continue
            within = C[np.ix_(members, members)].sum(axis=0)
            new.append(int(members[np.argmin(within)]))
        if new == med:
            break
        med = new
    seen, out = set(), []
    for m in med:                                           # medoids may coincide; keep order, drop duplicates
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def select(C, K, method, *, seed=0):
    if method == "first_k":
        return list(range(min(K, C.shape[0])))
    if method == "forward_selection":
        return forward_selection(C, K)[0]
    if method == "k_medoids":
        return k_medoids(C, K, seed=seed)
    raise ValueError("unknown method %r" % method)


def extremes(A, corridor_columns, shared_first, already):
    """Indices to append: per corridor (columns of A), the earliest-unsafe trajectory when it is strictly earlier than
    the shared present-fire value on that corridor (`shared_first[c]`) and not already kept."""
    add = []
    for cols, base in zip(corridor_columns, shared_first):
        cols = np.asarray(cols, dtype=np.int64)
        if cols.size == 0:
            continue
        first = A[:, cols].min(axis=1)
        j = int(np.argmin(first))
        if first[j] < base and j not in already and j not in add:
            add.append(j)
    return add


def reduce_members(C, K, method, *, A=None, corridors=None, shared_first=None, seed=0, append_extremes=True):
    """Selected indices, weights q (aligned with indices), reduction cost D_J, and the record for settings."""
    idx = select(C, K, method, seed=seed)
    ext = []
    if append_extremes and A is not None and corridors:
        ext = extremes(A, corridors, shared_first, idx)
    kept = idx + ext
    q, cost, _ = redistribute(C, kept)
    return {"method": method, "indices": [int(i) for i in kept], "selected": [int(i) for i in idx],
            "extremes": [int(i) for i in ext], "weights": [float(x) for x in q], "cost": cost, "K": int(K), "seed": int(seed)}
