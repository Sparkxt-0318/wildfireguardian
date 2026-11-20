"""Heat closure of road pieces and graph nodes from per-cell arrival, spread rate and safe distance
(METHOD.md section 7; PROTOCOL.md section 6).

Rule. Cell c is reached by the fire at A_c (s after issue; the earliest arrival over the cell, the existing
contact rule), the front moves at R_c (m/s) and the radiant flux exceeds the threshold q* within the safe
distance d*_c of the front. A road piece p at distance delta(p, c) >= 0 from the rectangle of cell c is untenable
from

    b_c(p) = A_c - max(0, d*_c - delta(p, c)) / R_c         (only if delta(p, c) < d*_c, or p lies in c)

and the piece closes at b(p) = min over cells c of b_c(p), floored at 0. For p in c (delta = 0) this is
A_c - d*_c / R_c: the cell's own contact closure moved earlier by the time the front needs to cover the safe distance.
For a piece outside c it is the time the front, assumed to be at the nearest point of c when c is first reached and
to approach along the line to p at R_c, comes within d*_c of p. Both assumptions put the closure no later than a
front that reaches c elsewhere or moves obliquely (the conservative direction). Closures are permanent, as in the
contact rule.

Without heat (d* = 0) the rule gives b(p) = A_{cell(p)}, the existing contact closure, exactly.

The engine-facing outputs reproduce product/wfg-roadlayer/wfg_roadlayer/engine.py (= research/kcf-replay/replay.py)
with per-piece and per-node closure seconds in place of per-cell ones.
"""
from __future__ import annotations

import math
from fractions import Fraction as F

import numpy as np

from . import roadgeom


def ceil_q(x: F) -> int:
    return -((-x.numerator) // x.denominator)


class HeatClosure:
    """Per-piece and per-node closure seconds for one road model and one fire input."""

    def __init__(self, road, arrival_s: dict, ros_m_s: dict, dstar_m: dict, *, H: int):
        """arrival_s: cell -> closure second (0..H) as the contact rule reads it (cells absent: not reached within H);
        ros_m_s, dstar_m: cell -> spread rate and safe distance for cells in arrival_s (missing d* = 0)."""
        self.road = road
        self.H = H
        self.arrival = arrival_s
        self.P = roadgeom.pieces(road)
        burning = np.array(sorted(arrival_s), dtype=np.int64)
        A = np.array([arrival_s[c] for c in burning], dtype=float)
        R = np.array([ros_m_s.get(int(c), np.nan) for c in burning], dtype=float)
        D = np.array([dstar_m.get(int(c), 0.0) for c in burning], dtype=float)
        D = np.where(np.isfinite(D), np.maximum(D, 0.0), 0.0)
        R = np.where(np.isfinite(R) & (R > 0), R, np.inf)  # unknown R: no lead (d*/inf = 0); see PROTOCOL 6
        self.cell_A = dict(zip(burning.tolist(), A.tolist()))
        self.cell_R = dict(zip(burning.tolist(), R.tolist()))
        self.cell_D = dict(zip(burning.tolist(), D.tolist()))
        dmax = float(D.max()) if D.size else 0.0
        self.ring = max(1, int(math.ceil(dmax / float(road.res))))
        self.piece_close = self._close_points_or_pieces(self.P["cell"], self.P["x0"], self.P["y0"], self.P["x1"], self.P["y1"])
        nx = np.array([xy[0] for xy in road.node_xy]); ny = np.array([xy[1] for xy in road.node_xy])
        self.node_close = self._close_points_or_pieces(np.array(road.node_cell, dtype=np.int64), nx, ny, nx, ny)

    def _close_points_or_pieces(self, own_cell, x0, y0, x1, y1):
        n = own_cell.size
        best = np.full(n, np.inf)
        nb = roadgeom.neighbour_cells(self.road, own_cell, self.ring)
        for k in range(nb.shape[1]):
            c = nb[:, k]
            has = np.array([ci in self.cell_A for ci in c.tolist()]) & (c >= 0)
            if not has.any():
                continue
            idx = np.nonzero(has)[0]
            cc = c[idx]
            A = np.array([self.cell_A[i] for i in cc.tolist()])
            R = np.array([self.cell_R[i] for i in cc.tolist()])
            D = np.array([self.cell_D[i] for i in cc.tolist()])
            xmin, xmax, ymin, ymax = roadgeom.cell_rect_arrays(self.road, cc)
            delta = roadgeom.segment_rect_distance(x0[idx], y0[idx], x1[idx], y1[idx], xmin, xmax, ymin, ymax)
            own = cc == own_cell[idx]
            delta = np.where(own, 0.0, delta)
            reach = own | (delta < D)
            with np.errstate(invalid="ignore"):
                b = A - np.maximum(D - delta, 0.0) / R
            b = np.where(reach, b, np.inf)
            best[idx] = np.minimum(best[idx], b)
        out = np.where(np.isfinite(best), np.floor(np.maximum(best, 0.0) + 1e-9), np.inf)
        return out

    # ------------------------------------------------------------------ engine-facing (wfg_roadlayer.engine shape)
    def edge_blocks(self):
        """B[j] as engine.build_instance builds it: start seconds s at which a vehicle on edge j meets a closed
        piece: s >= b(p) - D_j * zb(p), zb = the piece's end fraction."""
        road, H = self.road, self.H
        lo = {}
        E, Z, b = self.P["edge"], self.P["f1"], self.piece_close
        for j, zb, bb, k in zip(E.tolist(), Z.tolist(), b.tolist(), self.P["k"].tolist()):
            if not math.isfinite(bb):
                continue
            zq = road.seg[j][k][1]
            s = max(ceil_q(F(int(bb)) - F(road.D[j]) * zq), 0)
            if j not in lo or s < lo[j]:
                lo[j] = s
        return [[(lo[j], H)] if j in lo and lo[j] <= H else [] for j in range(len(road.seg))]

    def node_b(self, v: int):
        b = self.node_close[v]
        return int(b) if math.isfinite(b) and b <= self.H else None

    def wait_blocks(self):
        road, H = self.road, self.H
        W = []
        for v in range(len(road.node_ids)):
            b = self.node_b(v)
            W.append([(max(b - 1, 0), H)] if (road.waitable[v] and b is not None and b - 1 <= H) else [])
        return W
