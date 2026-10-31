"""Test helpers: tiny hand-built SYNTHETIC scenario sets."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from hazard_contract import HeatSource, ScenarioMeta, ScenarioSet

# The packet parameters of this repo (wfg_latest): q_rad = 1.40598 kW/m^2 with T = 3970.46 s.
PACKET_HEAT = dict(fuel_load_kg_m2=10.0, consumed_fraction=0.1, heat_content_kj_kg=18608.0,
                   radiative_fraction=0.3, emission_height_m=5.0, receiver_height_m=0.0)


def make_set(ig, ex=None, sup=None, *, cell=100.0, horizon=1000.0, burn=100.0, policy="scalar") -> ScenarioSet:
    ig = np.asarray(ig, dtype=float)
    if ig.ndim == 2:
        ig = ig[None]
    K, H, W = ig.shape
    if ex is None:
        ex = np.where(np.isfinite(ig), ig + burn, ig)
    ex = np.asarray(ex, dtype=float).reshape(K, H, W)
    if sup is None:
        sup = ~np.isnan(ig) & ~np.isnan(ex)
    sup = np.asarray(sup, dtype=bool).reshape(K, H, W)
    meta = ScenarioMeta(
        crs_epsg=3310, transform=(cell, 0.0, 0.0, 0.0, -cell, H * cell), height=H, width=W, K=K,
        issue_time_utc=datetime(2021, 8, 17, tzinfo=timezone.utc), horizon_s=horizon, source="synthetic",
        synthetic=True, model_version="test", weather_source="SYNTHETIC",
        heat_source=HeatSource(burn_duration_s=burn, burn_duration_policy=policy, **PACKET_HEAT),
    )
    return ScenarioSet(ig, ex, sup, meta)


def center(s: ScenarioSet, r: int, c: int) -> np.ndarray:
    return s.grid.cell_centers(np.array([r]), np.array([c]))[0]


def seg_hits_rect_sat(p, q, x0, x1, y0, y1) -> bool:
    """Independent closed segment / closed AABB test (separating axis theorem)."""
    if max(p[0], q[0]) < x0 or min(p[0], q[0]) > x1:
        return False
    if max(p[1], q[1]) < y0 or min(p[1], q[1]) > y1:
        return False
    nx, ny = -(q[1] - p[1]), q[0] - p[0]
    s = nx * p[0] + ny * p[1]
    proj = [nx * x + ny * y for x in (x0, x1) for y in (y0, y1)]
    return min(proj) <= s <= max(proj)


def brute_cells(s: ScenarioSet, g: np.ndarray) -> tuple[set, bool]:
    """Closed cells touched by a polyline, by testing every cell (and a ring outside the grid)."""
    H, W = s.meta.height, s.meta.width
    hit, outside = set(), False
    px = s.grid.to_pixel(np.asarray(g, dtype=float))
    c_lo, c_hi = min(-1, int(np.floor(px[:, 0].min())) - 1), max(W, int(np.ceil(px[:, 0].max())) + 1)
    r_lo, r_hi = min(-1, int(np.floor(px[:, 1].min())) - 1), max(H, int(np.ceil(px[:, 1].max())) + 1)
    for r in range(r_lo, r_hi + 1):
        for c in range(c_lo, c_hi + 1):
            x0, x1, y0, y1 = (float(v[0]) for v in s.grid.cell_rects(np.array([r]), np.array([c])))
            if len(g) == 1 or np.all(g == g[0]):
                p = g[0]
                touched = x0 <= p[0] <= x1 and y0 <= p[1] <= y1
            else:
                touched = any(seg_hits_rect_sat(g[i], g[i + 1], x0, x1, y0, y1) for i in range(len(g) - 1))
            if touched:
                if 0 <= r < H and 0 <= c < W:
                    hit.add((r, c))
                else:
                    outside = True
    return hit, outside


def exact_flux_at(s: ScenarioSet, k: int, xy, t: float) -> float:
    """Direct sheet-law flux at a point and instant from every burning cell of the grid."""
    from hazard_contract.geometry import solid_angle_rects
    h = s.meta.heat_source
    ig, ex, sup = s.ignite_s[k], s.extinguish_s[k], s.supported[k]
    burning = sup & (ig <= t) & (t < ex)
    rr, cc = np.nonzero(burning)
    if rr.size == 0:
        return 0.0
    x0, x1, y0, y1 = s.grid.cell_rects(rr, cc)
    om = solid_angle_rects(np.asarray(xy, dtype=float).reshape(1, 2), x0, x1, y0, y1, h.height_gap_m)[0]
    q = s._cell_emission(ig[rr, cc], ex[rr, cc])
    return float(np.sum(q * om) / (4 * np.pi))
