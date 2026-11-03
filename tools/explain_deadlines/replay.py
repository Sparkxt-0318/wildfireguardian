"""Flame-contact replay of a recorded journey, rigidly shifted in time.

A journey is the router's segment sequence (kit ``mission_contract.prepare_mission``): ISSUE (the start point at the
departure instant), every EDGE leg (straight chord u->v over [start, end]), every WAIT leg (stationary) and DWELL (the
destination point over [arrival, arrival + dwell], always part of the checked exposure: ``exposure_scope =
including_dwell``). Shifting the departure by ``s`` seconds shifts every time by ``s`` and leaves the geometry
unchanged, so occupancies are computed once at the recorded times and tested for any ``s``.

Contact rules (both must be clear for a recorded checked_route; see README.md "Contact rule"):

* ``closed`` -- runtime whole-road contact check (kit ``contact_first.check_contact``): for every burning cell whose
  CLOSED rectangle meets the closed segment, the closed occupancy [enter, leave] meets the half-open phase
  [birth, expiry) iff w = max(enter, birth) <= leave and w < expiry; w is the contact time.
* ``router`` -- router search (kit ``routing/core.py::evaluate_occupancy`` on HAZARD.json): each open piece between
  grid-line cuts (cell of its midpoint) and each cut point is a closed occupancy of one cell, sampled at its ends and
  at every breakpoint inside; contact iff a sample falls in a flame bin.

Every router occupancy lies inside the closed rectangle of its cell during a sub-interval of that cell's closed-rule
occupancy, so router contact implies closed contact (tested as a property). The closed rule therefore decides the
first contact; the router rule is reported alongside it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction as F

from .geometry import Grid, chord_pieces, clip_closed, exact
from .packet import Packet


@dataclass
class Segment:
    kind: str                      # ISSUE | EDGE | WAIT | DWELL
    index: int                     # position in the segment sequence
    leg_index: int | None
    edge: str | None
    node: str | None
    start: F
    end: F
    p0: tuple
    p1: tuple
    closed: list = field(default_factory=list)   # [(cell, enter, leave)] for burning cells (times at shift 0)
    router: list = field(default_factory=list)   # [(cell, lo, hi)] router occupancies of burning cells


def _closed_occupancies(grid: Grid, burning: set, p0, p1, start: F, end: F) -> list:
    xmin, xmax = min(p0[0], p1[0]), max(p0[0], p1[0])
    ymin, ymax = min(p0[1], p1[1]), max(p0[1], p1[1])
    out = []
    for cell in grid.cells_touching_box(xmin, xmax, ymin, ymax):
        if cell not in burning:
            continue
        u = clip_closed(p0, p1, grid.rect(cell))
        if u is None:
            continue
        out.append((cell, start + (end - start) * u[0], start + (end - start) * u[1]))
    return out


def build_segments(*, grid: Grid, packet: Packet, xy, legs: list, edges, start_node: str, departure,
                   destination: str, dwell, chord_cache: dict | None = None) -> list:
    """Segments of a full mission (ISSUE, legs, DWELL) with burning-cell occupancies at the recorded times.

    ``xy(node_id) -> (Fraction, Fraction)``; ``edges(edge_id) -> {"u", "v", "travel_ticks"}``. ``chord_cache``
    (optional, one dict per graph) memoises ``chord_pieces`` of each edge id across calls; the cached lists are only
    read, so the segments are the same with or without it."""
    burning = set(packet.burning_cells)
    segs = []
    dep = exact(departure)
    p = xy(start_node)
    issue = Segment("ISSUE", 0, None, None, start_node, dep, dep, p, p)
    issue.closed = _closed_occupancies(grid, burning, p, p, dep, dep)
    c = grid.cell_of(*p)
    issue.router = [(c, dep, dep)] if c in burning else []
    segs.append(issue)
    node, now = start_node, dep
    for i, leg in enumerate(legs):
        st, en = exact(leg["start"]), exact(leg["end"])
        if st != now or en <= st:
            raise ValueError("leg %d is not contiguous" % i)
        if leg["kind"] == "EDGE":
            e = edges(leg["edge"])
            if e["u"] != node or exact(leg.get("from_fraction", 0)) != 0 or exact(leg.get("to_fraction", 1)) != 1:
                raise ValueError("leg %d is not a whole edge from the current node" % i)
            if en - st != e["travel_ticks"]:
                raise ValueError("leg %d duration differs from travel_ticks" % i)
            p0, p1 = xy(e["u"]), xy(e["v"])
            seg = Segment("EDGE", len(segs), i, leg["edge"], None, st, en, p0, p1)
            seg.closed = _closed_occupancies(grid, burning, p0, p1, st, en)
            if chord_cache is None:
                pieces, points = chord_pieces(grid, p0, p1)
            else:
                if leg["edge"] not in chord_cache:
                    chord_cache[leg["edge"]] = chord_pieces(grid, p0, p1)
                pieces, points = chord_cache[leg["edge"]]
            when = lambda z, st=st, en=en: st + (en - st) * z
            seg.router = [(cc, when(a), when(b)) for cc, a, b in pieces if cc in burning] + \
                         [(cc, when(z), when(z)) for cc, z in points if cc in burning]
            node = e["v"]
        elif leg["kind"] == "WAIT":
            if leg.get("node") != node:
                raise ValueError("wait leg %d not at the current node" % i)
            p0 = xy(node)
            seg = Segment("WAIT", len(segs), i, None, node, st, en, p0, p0)
            seg.closed = _closed_occupancies(grid, burning, p0, p0, st, en)
            cc = grid.cell_of(*p0)
            seg.router = [(cc, st, en)] if cc in burning else []
        else:
            raise ValueError("leg kind %r" % leg["kind"])
        segs.append(seg)
        now = en
    if node != destination:
        raise ValueError("route does not end at its destination")
    pd = xy(destination)
    fin = now + exact(dwell)
    dw = Segment("DWELL", len(segs), None, None, destination, now, fin, pd, pd)
    dw.closed = _closed_occupancies(grid, burning, pd, pd, now, fin)
    cc = grid.cell_of(*pd)
    dw.router = [(cc, now, fin)] if (cc in burning and fin > now) else []
    segs.append(dw)
    return segs


@dataclass
class SegmentContact:
    """Contact of one segment at one shift."""
    segment: Segment
    pairs: list          # closed-rule contacts: [(member_index, cell, contact_time_w, birth, enter0, leave0)]
    router_members: set  # members with router-rule contact on this segment
    router_unsupported: bool

    @property
    def members(self) -> list:
        return sorted({p[0] for p in self.pairs})


def segment_contact(packet: Packet, seg: Segment, shift: F, horizon: F) -> SegmentContact:
    """Closed-rule contact pairs (contact time <= horizon only: the hazard is defined on [0, horizon]) and
    router-rule contact members of one segment at ``shift``."""
    pairs = []
    for s in range(packet.S):
        for cell, enter, leave in seg.closed:
            w = packet.contact_closed(s, cell, enter + shift, leave + shift)
            if w is not None and w <= horizon:
                ph = packet.phases[s][cell]
                pairs.append((s, cell, w, ph[0], enter, leave))
    router_members, unsupported = set(), False
    for s in range(packet.S):
        for cell, lo, hi in seg.router:
            r = packet.contact_router(s, cell, lo + shift, hi + shift)
            if r == "FLAME_CONTACT":
                router_members.add(s)
            elif r == "UNSUPPORTED":
                unsupported = True
    return SegmentContact(seg, pairs, router_members, unsupported)


def first_contact(packet: Packet, segs: list, shift: F, horizon: F):
    """First segment (route order) with a closed-rule or router-rule contact at ``shift``; None when clear."""
    for seg in segs:
        sc = segment_contact(packet, seg, shift, horizon)
        if sc.pairs or sc.router_members:
            return sc
    return None


def any_contact(packet: Packet, segs: list, shift: F, horizon: F) -> list:
    """Every segment with a contact at ``shift`` (closed or router rule)."""
    out = []
    for seg in segs:
        sc = segment_contact(packet, seg, shift, horizon)
        if sc.pairs or sc.router_members:
            out.append(sc)
    return out


def min_contact_shift(packet: Packet, seg: Segment, horizon: F):
    """Smallest shift s >= 0 at which the closed rule first meets flame on this segment (exact), with the pair
    realising it, or (None, None). For a phase [b, e) and occupancy [enter, leave] clear at s = 0, contact starts at
    s = b - leave (b > leave) because the occupancy is closed and the phase closed at b."""
    best, arg = None, None
    for s in range(packet.S):
        for cell, enter, leave in seg.closed:
            ph = packet.phases[s].get(cell)
            if ph is None:              # the cell burns in another member only
                continue
            b, e = ph[0], ph[1]
            if packet.contact_closed(s, cell, enter, leave) is not None:
                return F(0), (s, cell, b, enter, leave)
            if b > leave:
                cand = b - leave
                # the contact time at that shift is b; it must lie in the hazard window and before expiry
                if b <= horizon and b < e and (best is None or cand < best):
                    best, arg = cand, (s, cell, b, enter, leave)
    return best, arg
