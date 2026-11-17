"""Radiant exposure along a deadline-field witness route under the closed-form law (C.3), and thermal dose units.

Flux model at a point p and time t, for one hazard member, taking the maximum over cells (a nearest-front reading of
the long-front law; summing 375 m 'flaming' cells would count one front many times):

* cell c flaming at t (b_c <= t < x_c):  q = chi*E_A*R / (2*pi*(dist(p, rect c) + R*t_r/2)),  dist = 0 inside;
* p inside cell c before its arrival (t < b_c):  q = chi*E_A / (2*pi*((b_c - t) + t_r/2))   (front approaching).

The route's exposure is the maximum over members at each second (the field must hold for every member). Seconds are
sampled at their midpoints (1-s midpoint quadrature). Unshielded person: vehicle shielding is NOT modelled.

TDU = sum over seconds with q > q0 of q^(4/3) * 1 s, with q in kW/m2 ((kW/m2)^(4/3) s). Thresholds and q0: see
ROUTING_EFFECT.md for sources.
"""
from __future__ import annotations

import math

from .closure import HeatRule


def tdu(q_series, dt=1.0, q0=0.0):
    """Thermal dose units counted only while q > q0."""
    return float(sum((q ** (4.0 / 3.0)) * dt for q in q_series if q > q0))


class RouteExposure:
    def __init__(self, pm, rule: HeatRule = HeatRule(), search_m: float = 150.0):
        self.pm = pm; self.rule = rule; self.search = search_m
        g = pm.g
        self.eidx = {e: j for j, e in enumerate(g.edge_ids)}
        self.k_flame = rule.chi * rule.energy_kj_m2 * rule.spread_m_s / (2 * math.pi)     # kW/m
        self.off = rule.spread_m_s * rule.residence_s / 2.0                                 # m
        self.k_time = rule.chi * rule.energy_kj_m2 / (2 * math.pi)                          # kJ/m2 -> kW/m2 * s
        self.S = pm.pk.S
        # per member: cell -> (b, x) floats
        self.ph = [dict() for _ in range(self.S)]
        for c, lst in pm.closed_ph.items():
            for b, x, s in lst:
                if s >= 0:
                    self.ph[s][c] = (float(b), float(x) if x is not None else math.inf)
        self._near = {}

    def _cells_near(self, p):
        key = (round(p[0] / 50), round(p[1] / 50))
        if key not in self._near:
            grid = self.pm.g.grid
            from fractions import Fraction as F
            cx, cy = F(key[0] * 50), F(key[1] * 50)
            r = F(int(self.search) + 50)
            self._near[key] = [c for c in grid.cells_touching_box(cx - r, cx + r, cy - r, cy + r) if c in self.pm.burning]
        return self._near[key]

    def flux(self, p, t):
        grid = self.pm.g.grid
        best = 0.0
        cells = self._cells_near(p)
        for s in range(self.S):
            ph = self.ph[s]
            for c in cells:
                if c not in ph:
                    continue
                b, x = ph[c]
                x0, x1, y0, y1 = (float(v) for v in grid.rect(c))
                dx = max(x0 - p[0], 0.0, p[0] - x1); dy = max(y0 - p[1], 0.0, p[1] - y1)
                dist = math.hypot(dx, dy)
                if b <= t < x:
                    q = self.k_flame / (dist + self.off)
                elif t < b and dist == 0.0:
                    q = self.k_time / ((b - t) + self.rule.residence_s / 2.0)
                else:
                    continue
                if q > best:
                    best = q
        return best

    def route_series(self, legs, dest=None, dwell=0, origin=None, departure=None):
        """Per-second flux along the journey (driving + waits) and, separately, during the destination dwell."""
        g = self.pm.g
        drive = []
        for kind, ident, a, b in legs:
            a = int(a); b = int(b)
            if kind == "EDGE":
                j = self.eidx[ident]
                p0 = tuple(float(v) for v in g.xy(g.u[j])); p1 = tuple(float(v) for v in g.xy(g.v[j]))
                for t in range(a, b):
                    z = (t + 0.5 - a) / max(b - a, 1e-9)
                    drive.append(self.flux((p0[0] + z * (p1[0] - p0[0]), p0[1] + z * (p1[1] - p0[1])), t + 0.5))
            else:
                p = tuple(float(v) for v in g.xy(ident))
                drive.extend(self.flux(p, t + 0.5) for t in range(a, b))
        stay = []
        if dest is not None and legs:
            arr = int(legs[-1][3]); p = tuple(float(v) for v in g.xy(dest))
            stay = [self.flux(p, t + 0.5) for t in range(arr, arr + int(dwell))]
        at_origin = None
        if origin is not None and departure is not None:
            at_origin = self.flux(tuple(float(v) for v in g.xy(origin)), float(departure))
        return drive, stay, at_origin
