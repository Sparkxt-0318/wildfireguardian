"""Scalar (prefix) form of the F-3.1 deadline field under permanent closures (PROTOCOL.md §2.1).

Every set in the field is a prefix [0, L] of [0, H] when all closures are permanent, so one integer per edge state is
enough. ``backward`` is a bottleneck (max-min) label-setting pass over edge states with forbidden turns respected.
Value -1 = empty set. Checked against deadline_field.core by gate.py.
"""
from __future__ import annotations

import json, math, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from numba import njit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research/kcf-replay"))
sys.path.insert(0, str(ROOT / "research/harness-2026-11/F-3.1"))
sys.path.insert(0, str(ROOT))
import replay as RP  # noqa: E402
import measured_arms as MA  # noqa: E402

DWELL = RP.DWELL
HORIZONS = RP.HORIZONS
BIG = 1 << 40
ARMS = ["ORDINARY", "RUNNING", "WORST", "MEASURED", "MEASURED_GUST", "MEASURED_GUST_KMA"]
REGIONS = ["yeongdeok_2025", "uiseong_andong_2025"]


@njit(cache=True)
def _push(hk, hv, n, k, v):
    if n >= hk.shape[0]:
        return -1
    i = n
    hk[i] = k; hv[i] = v
    while i > 0:
        p = (i - 1) >> 1
        if hk[p] >= hk[i]:
            break
        hk[p], hk[i] = hk[i], hk[p]
        hv[p], hv[i] = hv[i], hv[p]
        i = p
    return n + 1


@njit(cache=True)
def _pop(hk, hv, n):
    k = hk[0]; v = hv[0]
    n -= 1
    hk[0] = hk[n]; hv[0] = hv[n]
    i = 0
    while True:
        l = 2 * i + 1
        if l >= n:
            break
        r = l + 1
        c = l
        if r < n and hk[r] > hk[l]:
            c = r
        if hk[i] >= hk[c]:
            break
        hk[c], hk[i] = hk[i], hk[c]
        hv[c], hv[i] = hv[i], hv[c]
        i = c
    return k, v, n


@njit(cache=True)
def backward(D, lo, acc_edges, acc_val, pred_ptr, pred_idx):
    """-> g (per edge state: max of R and acceptance top; -1 empty). lo[j] = block start (BIG if none)."""
    E = D.shape[0]
    R = np.full(E, -1, np.int64)
    g = np.full(E, -1, np.int64)
    a = np.full(E, -1, np.int64)
    cap = 4 * E + 16
    hk = np.empty(cap, np.int64); hv = np.empty(cap, np.int64); n = 0
    for t in range(acc_edges.shape[0]):
        j = acc_edges[t]
        if acc_val[t] > a[j]:
            a[j] = acc_val[t]
    for j in range(E):
        if a[j] >= 0:
            g[j] = a[j]
            n = _push(hk, hv, n, a[j], j)
    while n > 0:
        k, j, n = _pop(hk, hv, n)
        if k != g[j]:
            continue
        base = g[j] - D[j]
        if lo[j] - 1 < base:
            base = lo[j] - 1
        if base < 0:
            continue
        for q in range(pred_ptr[j], pred_ptr[j + 1]):
            s = pred_idx[q]
            if base > R[s]:
                R[s] = base
                if base > g[s]:
                    g[s] = base
                    n = _push(hk, hv, n, base, s)
                    if n < 0:
                        raise RuntimeError("heap overflow")
    return g


class FastRegion:
    def __init__(self, region):
        self.R = RP.Region(region)
        R = self.R
        inst = R.base
        E = len(inst.tail)
        self.E = E
        self.D = np.array(inst.D, np.int64)
        forb = inst.forbidden
        ptr = [0]; idx = []
        for j in range(E):
            for i in inst.inc[inst.tail[j]]:
                if (i, j) not in forb:
                    idx.append(i)
            ptr.append(len(idx))
        self.pred_ptr = np.array(ptr, np.int64); self.pred_idx = np.array(idx, np.int64)
        self.out = inst.out
        se, sc, sf = [], [], []
        for j, segs in enumerate(R.seg):
            for c, zb in segs:
                se.append(j); sc.append(c); sf.append(math.floor(inst.D[j] * zb))
        self.seg_edge = np.array(se, np.int64); self.seg_cell = np.array(sc, np.int64); self.seg_fl = np.array(sf, np.int64)
        self.ncell = R.grid.W * R.grid.H
        self.node_cell = np.array(R.node_cell, np.int64)
        # cells containing at least one road edge segment
        self.road_cells = np.unique(self.seg_cell)
        # shelter order exactly as replay.run_one iterates
        sh = {}
        for oid, (o, near) in R.cands.items():
            for s in near:
                sh.setdefault(s["properties"]["entry"]["node"], []).append(oid)
        self.shelter_nodes = list(sh)
        self.sidx = {n: i for i, n in enumerate(self.shelter_nodes)}
        self.sh_node = np.array([R.nidx[n] for n in self.shelter_nodes], np.int64)
        self.sh_inc = [np.array(R.inc_by_node.get(R.nidx[n], []), np.int64) for n in self.shelter_nodes]
        self.places = list(R.cands)
        self.pl_node = np.array([R.nidx[R.cands[o][0]["properties"]["entry"]["node"]] for o in self.places], np.int64)
        self.pl_sh = [sorted({self.sidx[s["properties"]["entry"]["node"]] for s in R.cands[o][1]}) for o in self.places]
        self.pl_out = [np.array(self.out[n], np.int64) for n in self.pl_node]
        self.sh_places = [[] for _ in self.shelter_nodes]
        for p, ss in enumerate(self.pl_sh):
            for s in ss:
                self.sh_places[s].append(p)

    # ---- closures -------------------------------------------------------------------------------------------------
    def dist(self, T):
        return self.R.cell_distance(DISCS, T)

    def curve(self, arm, T, H):
        """-> function d_m(np array) -> closure seconds (float, inf if never)."""
        if arm in MA.ARMS:
            r5, r8, cls_, info = MA.curve(arm, DISCS, T, H // 3600)
            f = np.vectorize(lambda d: MA.closure_s(r5, r8, float(d)))
            return f, (cls_, info)
        return np.vectorize(lambda d: RP.closure_s(arm, float(d))), None

    def closures(self, cs_float, H):
        """float closure seconds per cell (inf = none) -> int array per cell, -1 = not closed within H (matches
        replay.run_one: int(ceil(s)) kept if s <= H)."""
        b = np.full(self.ncell, -1, np.int64)
        ok = np.isfinite(cs_float) & (cs_float <= H)
        b[ok] = np.ceil(cs_float[ok]).astype(np.int64)
        return b

    def edge_lo(self, b):
        """Block start per edge (BIG = none) from cell closures b (-1 = none)."""
        bc = b[self.seg_cell]
        m = bc >= 0
        v = np.where(m, np.maximum(bc - self.seg_fl, 0), BIG)
        lo = np.full(self.E, BIG, np.int64)
        np.minimum.at(lo, self.seg_edge, v)
        return lo

    def accept_hi(self, b, H, s):
        bs = b[self.node_cell[self.sh_node[s]]]
        hi = H - DWELL
        if bs >= 0:
            hi = min(hi, max(bs - DWELL, 0) - 1)
        return min(hi, H)

    def shelter_field(self, b, lo, H, s):
        hi = self.accept_hi(b, H, s)
        inc = self.sh_inc[s]
        if hi < 0 or len(inc) == 0:
            return np.full(self.E, -1, np.int64)
        return backward(self.D, lo, inc, np.full(len(inc), hi, np.int64), self.pred_ptr, self.pred_idx)

    def issue_value(self, g, lo, b, p):
        on = self.pl_node[p]
        x = -1
        for j in self.pl_out[p]:
            v = min(g[j] - self.D[j], lo[j] - 1)
            if v > x:
                x = v
        bo = b[self.node_cell[on]]
        if bo >= 0:
            x = min(x, bo - 1)
        return x if x >= 0 else -1


DISCS = []


def load_discs():
    global DISCS
    d = json.loads((ROOT / "research/kcf-replay/fire_discs.json").read_text())["discs"]
    DISCS = [dict(x, t=datetime.fromisoformat(x["t_utc"])) for x in d]
    RP.DISCS = DISCS
    return DISCS


def issue_times():
    return [datetime(2025, 3, 25, h, tzinfo=timezone.utc) for h in range(3, 16)]
