"""Exact integer interval instances from a frozen routing graph + hazard packet (planner/API inputs).

Contact rules (both exactly as replayed by ``tools/explain_deadlines``; see DESIGN.md section 3):

* ``router`` -- the full-policy router's sampling rule on HAZARD.json flame bins. For a breakpoint-aligned phase
  [b, x) (router extinction, bins closed at the horizon) and a closed occupancy [lo, hi], sampling lo, hi and every
  interior breakpoint finds flame iff [lo, hi] meets [b, x) (or meets [b, H] when x >= H).
* ``closed`` -- the mandatory runtime whole-road check: closed cell rectangles, exact expiry, w = max(lo, b) <= hi
  and w < x.

A start second t with relative occupancy [e, l] meets phase [b, x) iff ceil(b - l) <= t <= ceil(x - e) - 1.
``variant='router'`` blocks by the router rule only (= full policy under the checked precondition);
``variant='cert'`` blocks by router OR closed (every witness then also passes the whole-road check).
"""
from __future__ import annotations

import json
import sys
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.explain_deadlines.geometry import ceil_q, chord_pieces, clip_closed, exact, floor_q  # noqa: E402
from tools.explain_deadlines.packet import Packet  # noqa: E402
from tools.explain_deadlines.roads import RoadGraph  # noqa: E402

from . import intervals as iv  # noqa: E402
from .core import Instance  # noqa: E402

INF = None


def _starts(e: F, l: F, b: F, x, H: int):
    """Integer start seconds in [0, H] meeting phase [b, x) (x None = closed through the horizon)."""
    lo = ceil_q(b - l)
    hi = H if x is None else ceil_q(x - e) - 1
    lo, hi = max(lo, 0), min(hi, H)
    return (lo, hi) if lo <= hi else None


class PacketModel:
    """Per (graph, packet): blocked start intervals of every edge, wait and issue point, per rule."""

    def __init__(self, graph_path, packet_dir, *, H: int | None = None, extra_blocks: dict | None = None,
                 present_only: bool = False):
        """extra_blocks: {router cell: start second} adds a pseudo-phase [start, beyond H) to that cell under BOTH
        rules (pessimistic unknown-support instances); None = the frozen packet exactly."""
        self.raw = json.loads(Path(graph_path).read_text())
        self.g = RoadGraph(self.raw)
        self.pk = Packet(packet_dir, self.g.grid)
        self.H = int(self.pk.horizon) if H is None else H
        if F(self.H) != self.pk.horizon:
            raise ValueError("non-integer horizon")
        self.node_ids = list(self.g.node_xy)
        self.nidx = {n: i for i, n in enumerate(self.node_ids)}
        grid, H = self.g.grid, self.H
        self.present_only = present_only
        self.burning = set(self.pk.present_cells) if present_only else set(self.pk.burning_cells)
        # phases per cell: router [b, x_router) (None = through horizon) and closed [b, x_exact)
        self.router_ph, self.closed_ph = {}, {}
        for s in range(self.pk.S):
            for c, (b, xe, xr, _k) in self.pk.phases[s].items():
                if present_only and _k != "CURRENT":
                    continue
                self.router_ph.setdefault(c, []).append((b, None if xr >= H else xr, s))
                self.closed_ph.setdefault(c, []).append((b, xe, s))
        self.extra_blocks = dict(extra_blocks or {})
        for c, st in self.extra_blocks.items():
            self.router_ph.setdefault(c, []).append((F(int(st)), None, -1))
            self.closed_ph.setdefault(c, []).append((F(int(st)), None, -1))
            self.burning.add(c)
        E = len(self.g.u)
        self.B = {"router": [[] for _ in range(E)], "closed": [[] for _ in range(E)]}
        self.edges_touching = 0
        self.touching_edges = []
        for j in range(E):
            p0, p1 = self.g.xy(self.g.u[j]), self.g.xy(self.g.v[j])
            cells = set(grid.cells_touching_box(min(p0[0], p1[0]), max(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[1], p1[1])))
            if not (cells & self.burning):
                continue
            self.edges_touching += 1
            self.touching_edges.append(j)
            Dq = F(self.g.ticks[j])
            pieces, points = chord_pieces(grid, p0, p1)
            rb = []
            for c, za, zb in pieces:
                for b, x, _s in self.router_ph.get(c, ()):
                    r = _starts(Dq * za, Dq * zb, b, x, H)
                    if r: rb.append(r)
            for c, z in points:
                for b, x, _s in self.router_ph.get(c, ()):
                    r = _starts(Dq * z, Dq * z, b, x, H)
                    if r: rb.append(r)
            cb = []
            for c in cells & self.burning:
                u = clip_closed(p0, p1, grid.rect(c))
                if u is None:
                    continue
                for b, x, _s in self.closed_ph.get(c, ()):
                    r = _starts(Dq * u[0], Dq * u[1], b, x, H)
                    if r: cb.append(r)
            self.B["router"][j] = iv.normalize(rb)
            self.B["closed"][j] = iv.normalize(cb)
        self._point_cache = {}

    # ----------------------------------------------------------------------------------------- points
    def point_blocks(self, node: str, length: F, rule: str):
        """Start seconds at which the closed stay [t, t + length] at the node point meets flame."""
        key = (node, length, rule)
        if key in self._point_cache:
            return self._point_cache[key]
        grid, H = self.g.grid, self.H
        p = self.g.xy(node)
        out = []
        if rule == "router":
            c = grid.cell_of(*p)
            for b, x, _s in self.router_ph.get(c, ()):
                r = _starts(F(0), length, b, x, H)
                if r: out.append(r)
        else:
            for c in grid.cells_touching_box(p[0], p[0], p[1], p[1]):
                if c not in self.burning or clip_closed(p, p, grid.rect(c)) is None:
                    continue
                for b, x, _s in self.closed_ph.get(c, ()):
                    r = _starts(F(0), length, b, x, H)
                    if r: out.append(r)
        out = iv.normalize(out)
        self._point_cache[key] = out
        return out

    def rules(self, variant: str):
        """router: router rule only; cert: router OR closed footprint; free: no fire at all (control)."""
        return {"router": ("router",), "cert": ("router", "closed"), "free": ()}[variant]

    def instance(self, variant: str, destinations, origins=()) -> Instance:
        """destinations: [{"node": id, "dwell": int, "window": [open, close]}]; origins: node ids (issue checks)."""
        g, H = self.g, self.H
        rules = self.rules(variant)
        E = len(g.u)
        B = [iv.normalize([p for r in rules for p in self.B[r][j]]) for j in range(E)]
        W = [[] for _ in self.node_ids]
        for n in self.node_ids:
            if g.waitable[n]:
                W[self.nidx[n]] = iv.normalize([p for r in rules for p in self.point_blocks(n, F(1), r)])
        acc = {}
        for d in destinations:
            dwell = exact(d["dwell"])
            op, cl = exact(d["window"][0]), exact(d["window"][1])
            lo, hi = max(ceil_q(op), 0), floor_q(min(cl, F(H)) - dwell)
            if lo > hi:
                continue
            blocked = iv.normalize([p for r in rules for p in self.point_blocks(d["node"], dwell, r)])
            n = self.nidx[d["node"]]
            acc[n] = iv.normalize(acc.get(n, []) + iv.subtract((lo, hi), blocked))
        # acceptance on arrival over any edge into the node, and at the initial label (origin = destination)
        A = [list(acc.get(self.nidx[g.v[j]], [])) for j in range(E)]
        IB = {self.nidx[o]: iv.normalize([p for r in rules for p in self.point_blocks(o, F(0), r)]) for o in origins}
        forbidden = set(g.forbidden)
        return Instance(H=H, n_nodes=len(self.node_ids), tail=[self.nidx[u] for u in g.u],
                        head=[self.nidx[v] for v in g.v], D=list(g.ticks),
                        waitable=[g.waitable[n] for n in self.node_ids], forbidden=forbidden,
                        B=B, W=W, A=A, IB=IB, AN=acc)

    # ----------------------------------------------------------------------------------------- precondition
    def full_policy_reduces_to_contact(self, hazard: dict, *, peak_limit=10.0, dose_limit=100.0, incurred=0.0):
        """Section 2 of DESIGN.md: peak cannot bind, and a router-contact-free journey within [0, H] cannot exceed
        the dose limit. Returns (ok, details)."""
        mx = mx_nf = 0.0
        for m in hazard["members"]:
            for fl, fx in zip(m["flame"], m["flux"]):
                mx = max(mx, max(fx))
                mx_nf = max(mx_nf, max((x for x, b in zip(fx, fl) if not b), default=0.0))
        support = all(all(r) for m in hazard["members"] for r in m["support"])
        dose_bound = F(mx_nf) * self.H + F(incurred)
        ok = support and F(mx) <= F(peak_limit) and dose_bound <= F(dose_limit)
        # per-journey sufficient condition: a contact-free journey of total duration (departure to end of dwell)
        # at most this many seconds cannot exceed the dose limit; peak needs max non-flame flux <= peak limit.
        budget = F(dose_limit) - F(incurred)
        max_exact_duration_s = None if mx_nf == 0 else float(budget / F(mx_nf))
        peak_ok = F(mx_nf) <= F(peak_limit)
        return ok, {"max_flux": mx, "max_nonflame_flux": mx_nf, "dose_bound": float(dose_bound),
                    "support_all": support, "peak_limit": peak_limit, "dose_limit": dose_limit,
                    "peak_cannot_bind_off_flame": peak_ok, "max_exact_journey_duration_s": max_exact_duration_s}
