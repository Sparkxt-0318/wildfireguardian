"""Obligation O2: independent re-derivation of the integer contact-relaxation instance from raw inputs.

Written from the semantics in experimental/sipp-routing/docs/SIPP_EQUIVALENCE.md and the frontend docstring, without
importing wfg_sipp (frontend, geometry, sipp, intervals). Differences from the frontend by construction:
  * own exact-rational grid geometry (no copied geometry module);
  * every edge is examined (no bounding-box prefilter);
  * blocked sets are built per (occupancy, activity interval) and merged with own code.
Shared, still-trusted inputs: the graph JSON, the request JSON, and ContactModel.cell_intervals (packet arrays ->
exact per-cell half-open activity intervals). Comparison is semantic, on the part of each set that the certificate
conditions can read: EB_j ∩ [dep, H], WB_n ∩ [dep, H] for waitable n, AC_n exactly.

Also reports grid-aliasing hazards: geometry points whose column or row lies outside the grid, where the frozen
cell formula row*width+col can name a different in-grid cell.
"""
from __future__ import annotations

import math
from fractions import Fraction as F


def _ceil(q):
    return -((-q.numerator) // q.denominator)


def merge(ivs):
    out = []
    for lo, hi in sorted(ivs):
        if lo > hi:
            continue
        if out and lo <= out[-1][1] + 1:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return [tuple(x) for x in out]


def clip(ivs, lo, hi):
    return [(max(a, lo), min(b, hi)) for a, b in ivs if b >= lo and a <= hi]


class Grid:
    def __init__(self, g):
        self.x0, self.y0, self.res = F(g["x0"]), F(g["y0"]), F(g["resolution"])
        self.W, self.Hc = int(g["width"]), int(g["height"])
        self.out_of_grid = 0

    def cell(self, x, y):
        col = math.floor((x - self.x0) / self.res)
        row = math.floor((y - self.y0) / self.res)
        if not (0 <= col < self.W and 0 <= row < self.Hc):
            self.out_of_grid += 1
        return row * self.W + col

    def occupancies(self, ux, uy, vx, vy):
        """[(cell, za, zb)]: open pieces between cuts (midpoint cell) and every cut point (za = zb)."""
        cuts = {F(0), F(1)}
        for a, b, origin, count in ((ux, vx, self.x0, self.W), (uy, vy, self.y0, self.Hc)):
            if a == b:
                continue
            lo, hi = min(a, b), max(a, b)
            k0 = max(1, math.floor((lo - origin) / self.res))
            k1 = min(count - 1, math.ceil((hi - origin) / self.res))
            for k in range(k0, k1 + 1):
                c = (origin + k * self.res - a) / (b - a)
                if 0 < c < 1:
                    cuts.add(c)
        cuts = sorted(cuts)
        pt = lambda z: (ux + z * (vx - ux), uy + z * (vy - uy))
        out = [(self.cell(*pt((a + b) / 2)), a, b) for a, b in zip(cuts, cuts[1:])]
        out += [(self.cell(*pt(z)), z, z) for z in cuts]
        return out


def derive(graph, request, cell_intervals):
    nodes = graph["nodes"]
    nidx = {n["id"]: i for i, n in enumerate(nodes)}
    grid = Grid(graph["grid"])
    dep, H = F(request["departure"]), F(request["horizon"])
    assert dep.denominator == 1 and H.denominator == 1
    dep, H = int(dep), int(H)
    xy = [(F(n["x"]), F(n["y"])) for n in nodes]
    EB = {}
    for j, e in enumerate(graph["edges"]):
        D = F(int(e["travel_ticks"]))
        (ux, uy), (vx, vy) = xy[nidx[e["u"]]], xy[nidx[e["v"]]]
        bl = []
        for c, za, zb in grid.occupancies(ux, uy, vx, vy):
            for b, en in cell_intervals.get(c, ()):
                # contact iff t + D*za < en and t + D*zb >= b
                bl.append((_ceil(b - D * zb), _ceil(en - D * za) - 1))
        bl = clip(merge(bl), dep, H)
        if bl:
            EB[j] = bl
    node_cell = [grid.cell(x, y) for x, y in xy]
    WB = {}
    for i, n in enumerate(nodes):
        if not n["waitable"]:
            continue
        bl = [(_ceil(b - 1), _ceil(en) - 1) for b, en in cell_intervals.get(node_cell[i], ())]
        bl = clip(merge(bl), dep, H)
        if bl:
            WB[i] = bl
    AC = {}
    for d in request["destinations"]:
        i = nidx[d["node"]]
        w = F(d["dwell"])
        acts = cell_intervals.get(node_cell[i], ())
        free = []
        for a, c in d["open_intervals"]:
            lo, hi = max(dep, _ceil(F(a))), min(H, math.floor(F(c) - w), math.floor(H - w))
            if lo > hi:
                continue
            blocked = merge([(_ceil(b - w), _ceil(en) - 1) for b, en in acts])
            cur = lo
            for x, y in blocked:
                if y < cur:
                    continue
                if x > hi:
                    break
                if x > cur:
                    free.append((cur, min(x - 1, hi)))
                cur = max(cur, y + 1)
            if cur <= hi:
                free.append((cur, hi))
        AC[i] = merge(AC.get(i, []) + free)
    return dict(EB=EB, WB=WB, AC=AC, dep=dep, H=H, out_of_grid_points=grid.out_of_grid)


def compare(inst, derived):
    """Semantic comparison against a wfg_sipp Instance; returns a list of difference records."""
    dep, H = derived["dep"], derived["H"]
    diffs = []
    if (inst.departure, inst.horizon) != (dep, H):
        diffs.append(("CLOCK", None, (inst.departure, inst.horizon), (dep, H)))
    for name, a_tab, b_tab, keys in (
            ("EB", inst.edge_block, derived["EB"], range(inst.E)),
            ("WB", inst.wait_block, derived["WB"], [n for n in range(inst.n_nodes) if inst.waitable[n]]),
            ("AC", inst.accept, derived["AC"], sorted(set(inst.accept) | set(derived["AC"])))):
        for k in keys:
            a = merge(a_tab.get(k, []))
            b = b_tab.get(k, [])
            if name != "AC":
                a = clip(a, dep, H)
            if a != b:
                diffs.append((name, k, a, b))
    return diffs


def compare_semantic(inst, derived):
    """Like compare(), but EB_j is compared only on legal departures [dep, H − D_j] and WB on [dep, H − 1]: blocks on
    departures that cannot be taken anyway (t + D_j > H) are not a difference (e.g. an activity set clipped at H)."""
    dep, H = derived["dep"], derived["H"]
    diffs = []
    for j in range(inst.E):
        lim = H - inst.D[j]
        a = clip(merge(inst.edge_block.get(j, [])), dep, lim)
        b = clip(derived["EB"].get(j, []), dep, lim)
        if a != b:
            diffs.append(("EB", j, a, b))
    for n in range(inst.n_nodes):
        if not inst.waitable[n]:
            continue
        a = clip(merge(inst.wait_block.get(n, [])), dep, H - 1)
        b = clip(derived["WB"].get(n, []), dep, H - 1)
        if a != b:
            diffs.append(("WB", n, a, b))
    for n in sorted(set(inst.accept) | set(derived["AC"])):
        if merge(inst.accept.get(n, [])) != derived["AC"].get(n, []):
            diffs.append(("AC", n, inst.accept.get(n), derived["AC"].get(n)))
    return diffs
