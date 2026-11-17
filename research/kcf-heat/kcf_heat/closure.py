"""Radiant-heat closure rule for the F-3.1 deadline field (C.1).

For every burning router cell c with phase [b, x) (the packet's own flame phase, member by member):

* in-cell rule: a road piece inside the closed cell rectangle is closed on [b - T*(q*), x)
  (closure = fire arrival minus the lead time of the closed-form law, DERIVATION.md);
* lateral rule: a road piece inside the rectangle grown by the halo h = R*T*(q*) is closed while the cell flames,
  on [b, x).

q* = 10 kW/m2 for vehicle movement and vehicle waits; q* = 2.5 kW/m2 for people standing (the origin at the
departure second) and for shelter stays (the destination dwell). T* is rounded UP to a whole second and h UP to the
centimetre; the halo is applied as an axis-aligned square buffer, which contains the Euclidean buffer (it over-closes by
at most (sqrt(2)-1)*h near cell corners). Both roundings are conservative.

The rule is ADDED to the unchanged F-3.1 rules: variant ``cert_heat`` blocks by router OR closed OR heat, so a heat
deadline is never later than the ``cert`` deadline, and every change is attributable to the heat rule.
Nothing in research/harness-2026-11/F-3.1 is modified; this module subclasses ``deadline_field.real.PacketModel``.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from fractions import Fraction as F
from pathlib import Path

from . import law

ROOT = Path(__file__).resolve().parents[3]
F31 = ROOT / "research" / "harness-2026-11" / "F-3.1"
for p in (str(ROOT), str(F31)):
    if p not in sys.path:
        sys.path.insert(0, p)

from tools.explain_deadlines.geometry import ceil_q, clip_closed, exact, floor_q  # noqa: E402
from deadline_field import intervals as iv  # noqa: E402
from deadline_field.core import Instance  # noqa: E402
from deadline_field.real import PacketModel, _starts  # noqa: E402


@dataclass(frozen=True)
class HeatRule:
    q_vehicle_kw_m2: float = 10.0
    q_person_kw_m2: float = 2.5
    chi: float = law.PACKET.chi
    energy_kj_m2: float = law.PACKET.energy_kj_m2
    residence_s: float = law.PACKET.residence_s
    spread_m_s: float = law.PACKET.spread_m_s
    lead_scale: float = 1.0          # sensitivity knob (e.g. 1/1.10 for the C064 closed-form bias); 1 = the law

    def lead_s(self, q_star: float) -> int:
        """T*(q*) rounded up to a whole second."""
        return int(math.ceil(self.lead_scale * law.lead_time(q_star, self.chi, self.energy_kj_m2, self.residence_s) - 1e-12))

    def halo_m(self, q_star: float) -> F:
        """h = R*T*(q*), using the rounded-up T*, rounded up to the centimetre (exact Fraction)."""
        return F(int(math.ceil(self.spread_m_s * self.lead_s(q_star) * 100 - 1e-9)), 100)

    def describe(self):
        return {"q_vehicle_kw_m2": self.q_vehicle_kw_m2, "q_person_kw_m2": self.q_person_kw_m2, "chi": self.chi,
                "energy_kj_m2": self.energy_kj_m2, "residence_s": self.residence_s, "spread_m_s": self.spread_m_s,
                "lead_scale": self.lead_scale,
                "lead_vehicle_s": self.lead_s(self.q_vehicle_kw_m2), "halo_vehicle_m": float(self.halo_m(self.q_vehicle_kw_m2)),
                "lead_person_s": self.lead_s(self.q_person_kw_m2), "halo_person_m": float(self.halo_m(self.q_person_kw_m2))}


def grow(rect, h: F):
    return (rect[0] - h, rect[1] + h, rect[2] - h, rect[3] + h)


class HeatPacketModel(PacketModel):
    """PacketModel plus the heat rule (edge blocks and point blocks), exposed as variant ``cert_heat``."""

    def __init__(self, graph_path, packet_dir, *, heat: HeatRule = HeatRule(), **kw):
        super().__init__(graph_path, packet_dir, **kw)
        self.heat = heat
        self.heat_info = heat.describe()
        Tv, hv = heat.lead_s(heat.q_vehicle_kw_m2), heat.halo_m(heat.q_vehicle_kw_m2)
        grid, H = self.g.grid, self.H
        E = len(self.g.u)
        self.B["heat"] = [[] for _ in range(E)]
        self.heat_edges = 0
        for j in range(E):
            p0, p1 = self.g.xy(self.g.u[j]), self.g.xy(self.g.v[j])
            box = (min(p0[0], p1[0]) - hv, max(p0[0], p1[0]) + hv, min(p0[1], p1[1]) - hv, max(p0[1], p1[1]) + hv)
            cells = set(grid.cells_touching_box(*box)) & self.burning
            if not cells:
                continue
            Dq = F(self.g.ticks[j])
            out = []
            for c in cells:
                rect = grid.rect(c)
                for clip, shift in ((clip_closed(p0, p1, rect), Tv), (clip_closed(p0, p1, grow(rect, hv)), 0)):
                    if clip is None:
                        continue
                    for b, x, _s in self.closed_ph.get(c, ()):
                        r = _starts(Dq * clip[0], Dq * clip[1], b - shift, x, H)
                        if r:
                            out.append(r)
            self.B["heat"][j] = iv.normalize(out)
            if self.B["heat"][j]:
                self.heat_edges += 1
        self._heat_point_cache = {}

    def heat_point_blocks(self, node, length: F, q_star: float):
        """Start seconds t at which the stay [t, t + length] at the node point is closed by the heat rule at q*."""
        key = (node, length, q_star)
        if key in self._heat_point_cache:
            return self._heat_point_cache[key]
        T, h = self.heat.lead_s(q_star), self.heat.halo_m(q_star)
        grid, H = self.g.grid, self.H
        p = self.g.xy(node)
        out = []
        for c in set(grid.cells_touching_box(p[0] - h, p[0] + h, p[1] - h, p[1] + h)) & self.burning:
            rect = grid.rect(c)
            for clip, shift in ((clip_closed(p, p, rect), T), (clip_closed(p, p, grow(rect, h)), 0)):
                if clip is None:
                    continue
                for b, x, _s in self.closed_ph.get(c, ()):
                    r = _starts(F(0), length, b - shift, x, H)
                    if r:
                        out.append(r)
        out = iv.normalize(out)
        self._heat_point_cache[key] = out
        return out

    def rules(self, variant: str):
        if variant == "cert_heat":
            return ("router", "closed")
        return super().rules(variant)

    def instance(self, variant: str, destinations, origins=()) -> Instance:
        if variant != "cert_heat":
            return super().instance(variant, destinations, origins)
        g, H = self.g, self.H
        rules = self.rules(variant)
        qv, qp = self.heat.q_vehicle_kw_m2, self.heat.q_person_kw_m2
        E = len(g.u)
        B = [iv.normalize([p for r in rules for p in self.B[r][j]] + list(self.B["heat"][j])) for j in range(E)]
        W = [[] for _ in self.node_ids]
        for n in self.node_ids:
            if g.waitable[n]:
                W[self.nidx[n]] = iv.normalize([p for r in rules for p in self.point_blocks(n, F(1), r)]
                                               + self.heat_point_blocks(n, F(1), qv))
        acc = {}
        for d in destinations:
            dwell = exact(d["dwell"])
            op, cl = exact(d["window"][0]), exact(d["window"][1])
            lo, hi = max(ceil_q(op), 0), floor_q(min(cl, F(H)) - dwell)
            if lo > hi:
                continue
            blocked = iv.normalize([p for r in rules for p in self.point_blocks(d["node"], dwell, r)]
                                   + self.heat_point_blocks(d["node"], dwell, qp))
            n = self.nidx[d["node"]]
            acc[n] = iv.normalize(acc.get(n, []) + iv.subtract((lo, hi), blocked))
        A = [list(acc.get(self.nidx[g.v[j]], [])) for j in range(E)]
        IB = {self.nidx[o]: iv.normalize([p for r in rules for p in self.point_blocks(o, F(0), r)]
                                         + self.heat_point_blocks(o, F(0), qp)) for o in origins}
        return Instance(H=H, n_nodes=len(self.node_ids), tail=[self.nidx[u] for u in g.u],
                        head=[self.nidx[v] for v in g.v], D=list(g.ticks),
                        waitable=[g.waitable[n] for n in self.node_ids], forbidden=set(g.forbidden),
                        B=B, W=W, A=A, IB=IB, AN=acc)
