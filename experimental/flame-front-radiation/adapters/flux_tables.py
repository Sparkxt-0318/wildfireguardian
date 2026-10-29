"""Planning flux tables of law v2 on road probe points (test-only adapter for the policy sweep).

Probe points: every graph node, plus interior points every <= ``spacing_m`` metres along each edge, restricted to the
roads that can see a counted flame piece (within the cutoff radius plus one cell of any dual-square half that can carry
a flame in the horizon); every other probe has exactly zero v2 flux, because the point law only counts pieces within
the cutoff. For each member the table holds, on a regular time grid, the radiation term per unit emissive power and the
engulfment indicator, so that any panel emissive power E and in-flame value give q = E * rad + engulfed * E_inflame
(the radiation term is linear in E). Values between grid times are linearly interpolated: this is a planning
approximation only; every returned route is re-checked with the exact law by ``journey_check``.
"""
from __future__ import annotations

import math

import numpy as np

import wfg_flamefront as W
from wfg_flamefront.law_v2 import _PointGeometry, _residence_map, view_factors_pairs
from wfg_flamefront.intensity import flame_geometry
from wfg_flamefront.solidflame import panel_vertices


def fire_cells(ff, t_end):
    """Host cells of halves that can carry a flame piece at some t in [0, t_end]."""
    from wfg_flamefront.law_v2 import _half_triangles
    D = _half_triangles(ff, W.FuelParameters())
    ever = ff.frames.any(axis=0)
    m = (D["tmin"] <= t_end) & (D["tmax"] > 0) & (D["mag"] > 0) & ever[D["hr"], D["hc"]]
    return np.unique(np.column_stack([D["hr"][m], D["hc"][m]]), axis=0)


class ProbeSet:
    def __init__(self, graph, grid, fields, t_end, spacing_m=10.0, cutoff_m=W.constants.CUTOFF_RADIUS_M):
        nodes = graph["nodes"]; edges = graph["edges"]
        self.node_index = {n["id"]: i for i, n in enumerate(nodes)}
        NX = np.array([float(n["x"]) for n in nodes]); NY = np.array([float(n["y"]) for n in nodes])
        cells = np.concatenate([fire_cells(ff, t_end) for ff in fields]) if fields else np.zeros((0, 2), int)
        cells = np.unique(cells, axis=0) if len(cells) else cells
        H, Wd = grid.height, grid.width
        near = np.zeros((H, Wd), bool)
        reach = int(math.ceil(cutoff_m / min(grid.dx, grid.dy))) + 1
        for r, c in cells:
            near[max(r - reach, 0):r + reach + 1, max(c - reach, 0):c + reach + 1] = True
        self.near_mask = near

        def is_near(x, y):
            rr, cc = grid.cell_of(x, y)
            ok = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < Wd)
            out = np.zeros(np.shape(x), bool)
            out[ok] = near[rr[ok], cc[ok]]
            return out
        node_near = is_near(NX, NY)
        px, py = list(NX[node_near]), list(NY[node_near])
        node_probe = -np.ones(len(nodes), np.int64)
        node_probe[node_near] = np.arange(node_near.sum())
        self.edge_probes = {}            # edge index -> (probe indices [n+1], fractions z [n+1])
        for ei, e in enumerate(edges):
            iu, iv = self.node_index[e["u"]], self.node_index[e["v"]]
            if not (node_near[iu] or node_near[iv]):
                # an edge whose both ends are far can still pass near; test its midpoint as well
                mx, my = 0.5 * (NX[iu] + NX[iv]), 0.5 * (NY[iu] + NY[iv])
                if not is_near(np.array([mx]), np.array([my]))[0]:
                    continue
            L = math.hypot(NX[iv] - NX[iu], NY[iv] - NY[iu])
            n = max(1, int(math.ceil(L / spacing_m)))
            z = np.linspace(0.0, 1.0, n + 1)
            idx = np.empty(n + 1, np.int64)
            for k, zk in enumerate(z):
                if k == 0 and node_probe[iu] >= 0:
                    idx[k] = node_probe[iu]
                elif k == n and node_probe[iv] >= 0:
                    idx[k] = node_probe[iv]
                else:
                    if k == 0:
                        node_probe[iu] = len(px)
                    if k == n:
                        node_probe[iv] = len(px)
                    idx[k] = len(px)
                    px.append(NX[iu] + zk * (NX[iv] - NX[iu])); py.append(NY[iu] + zk * (NY[iv] - NY[iu]))
            self.edge_probes[ei] = (idx, z)
        self.node_probe = node_probe
        self.points = np.column_stack([np.array(px, float), np.array(py, float)]) if px else np.zeros((0, 2))


def flux_table(probes, ff, grid, times, fuel=None, receiver="worst_case"):
    """Radiation per unit E rad[P, T] and engulfment mask eng[P, T] (bool) on the time grid."""
    fuel = W.FuelParameters.coerce(fuel).with_(emissive_power_kw_m2=1.0)
    pts = probes.points
    P, T = pts.shape[0], len(times)
    rad = np.zeros((P, T), np.float32)
    eng = np.zeros((P, T), bool)
    if P == 0:
        return rad, eng
    pg = _PointGeometry(ff, pts)
    res = _residence_map(fuel, ff.shape)[pg.hr, pg.hc]
    zr = float(fuel.receiver_height_m)
    cutoff = float(fuel.cutoff_radius_m)
    H, Wd = ff.shape
    reach = int(math.ceil(cutoff / min(grid.dx, grid.dy))) + 1
    prow, pcol = grid.cell_of(pts[:, 0], pts[:, 1])
    prow = np.clip(prow, -reach - 1, H + reach); pcol = np.clip(pcol, -reach - 1, Wd + reach)
    for j, t in enumerate(times):
        act = ff.active_at(t)
        with np.errstate(invalid="ignore"):
            band = pg.inside & act[pg.hr, pg.hc] & (pg.tau <= t) & (t < pg.tau + res)
        eng[:, j] = band
        p = W.front_pieces(ff, t, r_max=fuel.r_max_m_s, active=act)
        S = p["x0"].size
        if S == 0:
            continue
        geo = flame_geometry(p, fuel)
        V = panel_vertices(p["x0"], p["y0"], p["x1"], p["y1"], geo["height"], geo["reach"] * geo["lean_x"],
                           geo["reach"] * geo["lean_y"], 0.0)
        # bin pieces by host cell; pair each probe with pieces whose host is within `reach` cells
        key = p["host_r"] * Wd + p["host_c"]
        order = np.argsort(key, kind="stable")
        skey = key[order]
        cand_p, cand_s = [], []
        for dr in range(-reach, reach + 1):
            for dc in range(-reach, reach + 1):
                rr, cc = prow + dr, pcol + dc
                okc = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < Wd) & ~band
                if not okc.any():
                    continue
                k = rr[okc] * Wd + cc[okc]
                lo = np.searchsorted(skey, k, "left"); hi = np.searchsorted(skey, k, "right")
                cnt = hi - lo
                if cnt.sum() == 0:
                    continue
                pi = np.repeat(np.nonzero(okc)[0], cnt)
                offs = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
                si = order[np.repeat(lo, cnt) + offs]
                cand_p.append(pi); cand_s.append(si)
        if not cand_p:
            continue
        pi = np.concatenate(cand_p); si = np.concatenate(cand_s)
        dx1, dy1 = p["x1"][si] - p["x0"][si], p["y1"][si] - p["y0"][si]
        L2 = dx1 * dx1 + dy1 * dy1
        with np.errstate(divide="ignore", invalid="ignore"):
            tt = np.clip(np.where(L2 > 0, ((pts[pi, 0] - p["x0"][si]) * dx1 + (pts[pi, 1] - p["y0"][si]) * dy1) / L2, 0), 0, 1)
        d = np.hypot(pts[pi, 0] - (p["x0"][si] + tt * dx1), pts[pi, 1] - (p["y0"][si] + tt * dy1))
        m = d <= cutoff
        if not m.any():
            continue
        pi, si = pi[m], si[m]
        for c0 in range(0, pi.size, 400000):
            a, b = pi[c0:c0 + 400000], si[c0:c0 + 400000]
            P3 = np.column_stack([pts[a], np.full(a.size, zr)])
            F = view_factors_pairs(P3, V[b], receiver)
            rad[:, j] += np.bincount(a, weights=fuel.transmissivity * F, minlength=P).astype(np.float32)
    return rad, eng
