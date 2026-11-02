"""Property tests (hypothesis) of the contact engine and the planner rules on random toy inputs."""
from fractions import Fraction as F

from hypothesis import HealthCheck, given, settings, strategies as st

from tools.explain_deadlines.geometry import Grid, chord_pieces, clip_closed
from tools.explain_deadlines.packet import Packet, round_up_sum
from tools.explain_deadlines.plans import Attempt, combine, plan_from_attempts
from tools.explain_deadlines.reach import ContactIndex, earliest_free, flame_avoiding
from tools.explain_deadlines.replay import Segment, min_contact_shift, segment_contact
from tools.explain_deadlines.roads import RoadGraph

from . import synth

G = Grid(0, 0, 100, 4, 3)
SETTINGS = settings(max_examples=150, deadline=None, database=None, suppress_health_check=[HealthCheck.too_slow])
# multiples of 25 m: lands on interior grid lines and corners often; the far edges (x = 400, y = 300) are outside
# the lattice (floor rule), as real road nodes always are inside it
coord_x = st.integers(0, 15).map(lambda k: F(25 * k))
coord_y = st.integers(0, 11).map(lambda k: F(25 * k))
point = st.tuples(coord_x, coord_y)
T = 4000.0


def fake_packet(births: dict, present: list, R: float, horizon: float = 3600.0) -> Packet:
    """One-member packet built in memory with the writer's breakpoint rules (no files)."""
    pk = object.__new__(Packet)
    pk.grid, pk.S, pk.T, pk.R, pk.horizon = G, 1, F(T), F(R), F(horizon)
    ph = {}
    if R > 0:
        for c in present:
            ph[c] = (F(0), F(R), F(R), "CURRENT")
    for c, b in births.items():
        ph[c] = (F(b), F(b) + F(T), F(round_up_sum(b, T)), "FUTURE")
    pk.phases = [ph]
    knots = {0.0, horizon} | {b for b in births.values() if 0 < b < horizon}
    knots |= {round_up_sum(b, T) for b in births.values() if round_up_sum(b, T) < horizon}
    if present and 0 < R < horizon:
        knots.add(R)
    bp = sorted(knots)
    bins = {}
    for i, left in enumerate(bp[:-1]):
        for c, (b0, _, er, _) in ph.items():
            if b0 <= left < er:
                bins.setdefault(c, []).append(i)
    pk.breakpoints, pk.flame_bins = [[F(x) for x in bp]], [bins]
    pk.burning_cells = sorted(ph)
    pk.member_ids = ["m:0"]
    return pk


births_st = st.dictionaries(st.integers(0, 11), st.floats(1.0, 3500.0, allow_nan=False).map(lambda x: round(x, 3)), max_size=4)
present_st = st.lists(st.integers(0, 11), max_size=3, unique=True)


def segment(p0, p1, dur, pk):
    from tools.explain_deadlines.replay import _closed_occupancies
    seg = Segment("EDGE", 1, 0, "E", None, F(0), F(dur), p0, p1)
    seg.closed = _closed_occupancies(G, set(pk.burning_cells), p0, p1, F(0), F(dur))
    pieces, points = chord_pieces(G, p0, p1)
    seg.router = [(c, F(dur) * a, F(dur) * b) for c, a, b in pieces if c in pk.phases[0]] + \
                 [(c, F(dur) * z, F(dur) * z) for c, z in points if c in pk.phases[0]]
    return seg


@SETTINGS
@given(point, point, st.integers(1, 60), births_st, present_st, st.sampled_from([0.0, 1000.0, 3700.0]), st.integers(0, 3500))
def test_router_contact_implies_closed_contact(p0, p1, dur, births, present, R, shift):
    if p0 == p1:
        return
    pk = fake_packet(births, present, R)
    seg = segment(p0, p1, dur, pk)
    sc = segment_contact(pk, seg, F(shift), F(10 ** 6))
    closed_cells = {p[1] for p in sc.pairs}
    for cell, lo, hi in seg.router:
        if pk.contact_router(0, cell, lo + shift, hi + shift) == "FLAME_CONTACT":
            assert cell in closed_cells


@SETTINGS
@given(point, point, st.integers(1, 60), births_st)
def test_min_contact_shift_is_exact(p0, p1, dur, births):
    if p0 == p1:
        return
    pk = fake_packet(births, [], 0.0)
    seg = segment(p0, p1, dur, pk)
    big = F(10 ** 6)
    if segment_contact(pk, seg, F(0), big).pairs:
        return
    s_star, _ = min_contact_shift(pk, seg, big)
    if s_star is None:
        for s in (0, 100, 1000, 3000):
            assert not segment_contact(pk, seg, F(s), big).pairs
        return
    assert s_star > 0
    assert segment_contact(pk, seg, s_star, big).pairs
    assert not segment_contact(pk, seg, s_star - F(1, 1000), big).pairs


@SETTINGS
@given(st.lists(st.tuples(st.integers(-50, 400), st.integers(1, 120), st.integers(1, 4)), max_size=6),
       st.integers(0, 300), st.integers(0, 400))
def test_earliest_free_matches_brute_force(raw, a, latest):
    blocks = [(F(lo, d), F(lo, d) + F(w, d), 0, 0, F(0)) for lo, w, d in raw]
    want = next((t for t in range(a, latest + 1) if not any(lo <= t < hi for lo, hi, *_ in blocks)), None)
    assert earliest_free(blocks, a, latest) == want


@SETTINGS
@given(point, point, st.integers(0, 11))
def test_clip_closed_matches_sampling(p0, p1, cell):
    rect = G.rect(cell)
    u = clip_closed(p0, p1, rect)
    for k in range(65):
        z = F(k, 64)
        x, y = p0[0] + z * (p1[0] - p0[0]), p0[1] + z * (p1[1] - p0[1])
        inside = rect[0] <= x <= rect[1] and rect[2] <= y <= rect[3]
        assert inside == (u is not None and u[0] <= z <= u[1])


NODES = {"n0": (50, 50), "n1": (150, 150), "n2": (250, 50), "n3": (350, 250), "n4": (50, 250), "n5": (250, 250)}
edge_st = st.lists(st.tuples(st.sampled_from(sorted(NODES)), st.sampled_from(sorted(NODES)), st.integers(1, 25)), min_size=1, max_size=9)


def brute_force_arrival(g, idx, start, target, depart, latest):
    """Exhaustive time-expanded search with free waiting and closed-rule blocking (no turn restrictions)."""
    reach = {start: depart}
    changed = True
    while changed:
        changed = False
        for e in range(len(g.edge_ids)):
            u, v = g.u[e], g.v[e]
            if u not in reach:
                continue
            for t in range(reach[u], latest - g.ticks[e] + 1):
                if any(lo <= t < hi for lo, hi, *_ in idx.edge_blocks(e)):
                    continue
                arr = t + g.ticks[e]
                if arr < reach.get(v, 1 << 30):
                    reach[v] = arr
                    changed = True
                break
    return reach.get(target) if target != start else None


@settings(max_examples=60, deadline=None, database=None, suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])
@given(edge_st, births_st, present_st, st.integers(0, 40))
def test_relaxation_equals_exhaustive_search(tmp_path_factory, edges, births, present, depart):
    edges = [(a, b, t) for a, b, t in edges if a != b]
    if not edges:
        return
    raw = synth.graph(NODES, [("e%d" % i, a, b, t) for i, (a, b, t) in enumerate(edges)])
    g = RoadGraph(raw)
    d = tmp_path_factory.mktemp("pk")
    # a present-fire cell never draws a first-new ignition (packet contract)
    synth.write_packet(d, members=1, current=present, R=3700.0,
                       ignitions={0: {c: b % 200 + 1 for c, b in births.items() if c not in present}})
    pk = Packet(d, g.grid)
    idx = ContactIndex(g, pk)
    latest = 200
    for target in ("n3", "n5"):
        if target == "n0":
            continue
        run = flame_avoiding(idx, "n0", depart, [target], latest, turns=False)
        issue = run["issue_blocked"]
        want = None if issue else brute_force_arrival(g, idx, "n0", target, depart, latest)
        assert run["arrival"][target] == want


offsets_st = st.lists(st.integers(0, 5).map(lambda k: 600 * k), min_size=1, max_size=6, unique=True)
verdict_st = st.sampled_from(["checked_route", "model_no_route", "unresolved"])


@SETTINGS
@given(offsets_st, st.lists(st.tuples(st.integers(0, 5), st.sampled_from(["d1", "d2"]), verdict_st, st.integers(100, 3000)), max_size=12))
def test_planner_deadline_rules(offsets, raw):
    atts, seen = [], set()
    for k, dest, v, arr in raw:
        key = (600 * k, dest)
        if key in seen:
            continue
        seen.add(key)
        atts.append(Attempt(600 * k, dest, v, arr if v == "checked_route" else None, "j%d%s" % (k, dest)))
    p = plan_from_attempts("o", offsets, atts, "dispatch")
    checked = [a for a in atts if a.verdict == "checked_route"]
    assert p.latest_s == (max(a.offset_s for a in checked) if checked else None)
    assert p.best_verdict == combine(a.verdict for a in atts)
    if checked:
        at = [a for a in checked if a.offset_s == p.latest_s]
        assert p.best.arrival_s == min(a.arrival_s for a in at)
    # contiguous: every offset up to it is checked; the next one (if any) is not
    cells = sorted(p.sweep, key=lambda c: c.offset_s)
    if p.contiguous_s is not None:
        assert all(c.verdict == "checked_route" for c in cells if c.offset_s <= p.contiguous_s)
    nxt = [c for c in cells if p.contiguous_s is None or c.offset_s > p.contiguous_s]
    if nxt:
        assert nxt[0].verdict != "checked_route"
    # unresolved never counts toward the deadline
    assert all(not (c.verdict == "unresolved" and c.offset_s == p.latest_s) for c in cells)
