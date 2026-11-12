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
from tools.explain_deadlines.packet import Packet, round_up_sum  # noqa: E402


def load_packet(packet_dir, grid):
    """Packet reader. Scalar law: the unchanged replay-tool reader (phases from the npz, verified against HAZARD bins).
    Per-cell laws (F-DYN envelope variants; constructed_arrays.npz carries member<s>__extinction_breakpoint_s): phases
    are read from the HAZARD flame bins directly (one contiguous run per member and cell, asserted), because the npz
    does not represent every flame cell under these laws. Closed and router rules then use the same bin-aligned phase.
    'present_only' treats phases starting at 0 as present fire."""
    import numpy as np
    from pathlib import Path as _P
    if (_P(packet_dir) / "SUPPORT_WRITE_FAILED").exists():     # F-9.3 support_mask: a failed write is refused
        raise ValueError("packet %s carries SUPPORT_WRITE_FAILED; refused" % packet_dir)
    with np.load(_P(packet_dir) / "constructed_arrays.npz", allow_pickle=False) as z:
        ext = {k: np.array(z[k], dtype=float) for k in z.files if k.endswith("__extinction_breakpoint_s")}
    # Scalar law first: the unchanged reader verifies npz phases against the HAZARD flame bins. Only when that check
    # fails AND the packet carries per-cell extinction arrays is the packet read as a per-cell law.
    from tools.explain_deadlines.packet import PacketError
    with np.load(_P(packet_dir) / "constructed_arrays.npz", allow_pickle=False) as z:
        hazard_only = "per_cell_law_HAZARD_only" in z.files
    if hazard_only:          # v3.4 'envelope': the packet declares that its arrays must refuse; read HAZARD only
        return _hazard_only_packet(_P(packet_dir), grid), True
    try:
        return Packet(packet_dir, grid), False
    except PacketError:
        if not ext:
            raise
    orig = Packet.verify_consistency
    Packet.verify_consistency = lambda self: {"status": "DEFERRED"}
    try:
        pk = Packet(packet_dir, grid)
    finally:
        Packet.verify_consistency = orig
    big = pk.horizon + 10 ** 9
    pk.phases = []
    cells_all = set()
    for s_ in range(pk.S):
        bp = pk.breakpoints[s_]
        ph = {}
        for c, bins in pk.flame_bins[s_].items():
            bins = sorted(bins)
            if bins != list(range(bins[0], bins[-1] + 1)):
                raise ValueError("per-cell law: flame bins of cell %d member %d are not one contiguous run" % (c, s_))
            b = bp[bins[0]]
            x = big if bins[-1] == len(bp) - 2 else bp[bins[-1] + 1]
            ph[c] = (b, x, x, "CURRENT" if b == 0 else "FUTURE")
            cells_all.add(c)
        pk.phases.append(ph)
    pk.burning_cells = sorted(cells_all)
    pk.present_cells = sorted({c for ph in pk.phases for c, v in ph.items() if v[3] == "CURRENT"})
    pk.consistency = {"status": "PHASES_FROM_HAZARD_FLAME_BINS (per-cell law)", "cells": len(cells_all)}
    pk.per_cell_law = True
    return pk, True


def _phases_from_bins(pk):
    """One contiguous flame run per member and cell (asserted) -> phase [b, x); a run ending in the last bin burns
    through the horizon."""
    big = pk.horizon + 10 ** 9
    pk.phases, cells_all = [], set()
    for s_ in range(pk.S):
        bp = pk.breakpoints[s_]
        ph = {}
        for c, bins in pk.flame_bins[s_].items():
            bins = sorted(bins)
            if bins != list(range(bins[0], bins[-1] + 1)):
                raise ValueError("flame bins of cell %d member %d are not one contiguous run" % (c, s_))
            b = bp[bins[0]]
            x = big if bins[-1] == len(bp) - 2 else bp[bins[-1] + 1]
            ph[c] = (b, x, x, "CURRENT" if b == 0 else "FUTURE")
            cells_all.add(c)
        pk.phases.append(ph)
    pk.burning_cells = sorted(cells_all)
    pk.present_cells = sorted({c for ph in pk.phases for c, v in ph.items() if v[3] == "CURRENT"})
    return len(cells_all)


def _hazard_only_packet(d, grid):
    """HAZARD-only reader (no array is read): the header checks of the unchanged Packet reader on REPORT/HAZARD
    (grid, dt = 1 s, window [0, horizon], member order), router flame bins from HAZARD, and phases from the bins.
    The closed-replay checker then reads these phases: consistent with the field's reading, NOT independent of it."""
    import json as _j
    from tools.explain_deadlines.geometry import exact
    from tools.explain_deadlines.packet import PacketError, PACKET_FILES, sha256_file
    pk = Packet.__new__(Packet)
    pk.dir, pk.grid = d, grid
    pk.sha256 = {n: sha256_file(d / n) for n in PACKET_FILES if (d / n).is_file()}
    report = _j.loads((d / "REPORT.json").read_text())
    a = report["native_metadata"]["construction"]["assumptions"]
    pk.horizon = exact(a["horizon_s"])
    hz = _j.loads((d / "HAZARD.json").read_text())
    if hz.get("schema") != "wfg.routing.edgegrid/1":
        raise PacketError("HAZARD schema %r" % hz.get("schema"))
    g = hz["grid"]
    if (exact(g["x0"]), exact(g["y0"]), exact(g["resolution"]), int(g["width"]), int(g["height"])) != \
            (grid.x0, grid.y0, grid.res, grid.W, grid.H):
        raise PacketError("HAZARD grid differs from the graph grid")
    if exact(hz["dt"]) != 1 or exact(hz["valid_from"]) != 0 or exact(hz["valid_until"]) != pk.horizon:
        raise PacketError("HAZARD dt/window")
    pk.time_origin, pk.crs, pk.dt = hz["time_origin"], hz.get("crs"), 1
    pk.valid_from, pk.valid_until = exact(hz["valid_from"]), exact(hz["valid_until"])
    pk.member_ids = [m["id"] for m in hz["members"]]
    if list(report["rows"][0]["request"]["incurred"]) != pk.member_ids:
        raise PacketError("member order differs between HAZARD.json and REPORT.json")
    pk.S = len(pk.member_ids)
    pk.breakpoints, pk.flame_bins = [], []
    n_cells = grid.W * grid.H
    for m in hz["members"]:
        bp = [exact(x) for x in m["breakpoints"]]
        if any(b2 <= b1 for b1, b2 in zip(bp, bp[1:])):
            raise PacketError("breakpoints not increasing")
        fl = m["flame"]
        if len(fl) != len(bp) - 1 or any(len(row) != n_cells for row in fl):
            raise PacketError("flame array shape")
        bins = {}
        for i, row in enumerate(fl):
            for c in (j for j, v in enumerate(row) if v):
                bins.setdefault(c, []).append(i)
        pk.breakpoints.append(bp)
        pk.flame_bins.append(bins)
    n = _phases_from_bins(pk)
    pk.consistency = {"status": "HAZARD_ONLY (packet declares per_cell_law_HAZARD_only; arrays not read)", "cells": n}
    pk.per_cell_law = True
    return pk
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
                 present_only: bool = False, duration_factor=None):
        """extra_blocks: {router cell: start second} adds a pseudo-phase [start, beyond H) to that cell under BOTH
        rules (pessimistic unknown-support instances); None = the frozen packet exactly."""
        self.raw = json.loads(Path(graph_path).read_text())
        self.g = RoadGraph(self.raw)
        self.pk, self.per_cell_law = load_packet(packet_dir, self.g.grid)
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
                if duration_factor == "never":
                    xe = xr = F(10) ** 12
                elif duration_factor is not None:
                    f, b0 = F(duration_factor), max(b, F(0))   # present fire: [0, f*R)
                    xe = b0 + f * (xe - b0)
                    xr = b0 + f * (xr - b0)
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
