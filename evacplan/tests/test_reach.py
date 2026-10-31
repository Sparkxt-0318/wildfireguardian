"""The RELAXED reachability layer (evacplan.reach): hand-worked latest departures, the vectorised
sweep against a plain-Python recursion, forward routing, and soundness of both relaxations against
the oracle. All instances are SYNTHETIC test fixtures.

Hand-worked geometry (testkit): 100 m cells, nodes at cell centres, 50 s per edge. An edge between
horizontal neighbours (r, c) -> (r, c+1) is in cell (r, c) for its first 25 s, touches both cells at
the boundary at 25 s and is in (r, c+1) for its last 25 s (closed touch intervals)."""
import numpy as np
import pytest

from evacplan import Oracle, State
from evacplan.oracle import contact_records
from evacplan.reach import NEG_INF, POS_INF, Reach
from evacplan_testkit import (
    eid, facility, grid_graph, instance, make_set, nid, quiet, random_case, shelter, vehicle,
)

PERSIST = 1e9          # burn duration: cells keep burning through every horizon used here


def row_instance(*, H=1, W=4, ig_cells=(), horizon=10_000.0, waitable=True, window=((0.0, 1e6),), forbidden=(),
                 release=0.0, vehicles=None):
    ig = quiet(H, W)
    for (r, c), t in ig_cells:
        ig[0, r, c] = t
    ss = make_set(ig, horizon=horizon, burn=PERSIST)
    g = grid_graph(H, W, waitable=waitable, forbidden=forbidden)
    inst = instance(g, facilities=[facility("F", nid(0, 0), amb=5, release=release)],
                    vehicles=vehicles if vehicles is not None else [vehicle("V", nid(0, W - 1))],
                    shelters=[shelter("S", nid(0, W - 1), windows=window)])
    return inst, ss


def latest(inst, ss, c=0):
    rh = Reach(inst, ss)
    f = inst.facilities[0]
    fn = rh.node(f.node)
    sw = rh.sweep([rh.class_targets(c)], [fn])
    b = int(f.boarding_s.vector()[c])
    return rh, sw, sw.latest_departure(0, fn, not_before=int(f.release_s) + b, board_s=b)


# --------------------------------------------------------------------------- hand-worked
def test_hand_worked_row_latest_departure():
    # cell (0,1) burns from 500: edge 1 (F -> n0_1) touches it during [d+25, d+50] -> d <= 449;
    # edge 2 (n0_1 -> n0_2) during [d+50, d+75] -> d <= 424. Nothing else touches it.
    inst, ss = row_instance(ig_cells=[((0, 1), 500.0)])
    rh, sw, ld = latest(inst, ss)
    assert ld == 424
    e1, e2 = rh.eidx[eid((0, 0), (0, 1))], rh.eidx[eid((0, 1), (0, 2))]
    assert rh.okT[449, e1] and not rh.okT[450, e1]
    assert rh.okT[474, e2] and not rh.okT[475, e2]
    route, tg, unload_at = sw.witness(0, rh.node(nid(0, 0)), ld)
    assert [rh.edge_ids[e] for e, _ in route.steps] == [eid((0, 0), (0, 1)), eid((0, 1), (0, 2)), eid((0, 2), (0, 3))]
    assert [d for _, d in route.steps] == [424, 474, 524] and route.arrival == unload_at == 574 and tg.shelter == "S"
    assert rh.route_ok(route, rh.node(nid(0, 0)))
    # the certain-contact relaxation is narrowed by the margin: 425 (contact at the instant 500) is not certain there
    ld_neg = rh.latest_arrival_neg(rh.class_targets(0))
    assert ld_neg[rh.node(nid(0, 0))] == 425 >= ld
    assert ld_neg[rh.node(nid(0, 3))] == 10_000 - 5           # shelter: unload one ambulatory (5 s) by the horizon


def test_hand_worked_departure_field_per_node():
    # same row, horizon 10000: n0_1 lies in the burning cell (its edge east touches it until 25 s: <= 474);
    # n0_2 and the shelter n0_3 are never touched: 10000 - 50 - 5 and 10000 - 5 (one ambulatory unloading)
    inst, ss = row_instance(ig_cells=[((0, 1), 500.0)])
    rh = Reach(inst, ss)
    field = rh.departure_field([0, 2])
    assert field[0].tolist() == [424, 474, 9945, 9995]
    assert field[1].tolist() == [424, 474, 9945 - 10, 9995 - 10]   # bedbound unloads 15 s: only horizon-bound nodes move
    inst, ss = row_instance(ig_cells=[((0, 1), 500.0)], window=((0.0, 300.0),))
    assert Reach(inst, ss).departure_field([0])[0].tolist() == [145, 195, 245, 295]


def test_hand_worked_detour_window_and_turn_ban():
    # second row: cell (1,1) burns from 800. Row 1 route (F, n1_0, n1_1, n1_2, n1_3, S): edge n1_1->n1_2
    # leaves at d+100 and touches (1,1) until d+125 -> d <= 674 (n1_0->n1_1 allows d <= 699).
    inst, ss = row_instance(H=2, ig_cells=[((0, 1), 500.0), ((1, 1), 800.0)])
    assert latest(inst, ss)[2] == 674
    # shelter closes at 600: row 0 arrives at d+150 (d <= 445 for the window, 424 for the fire),
    # row 1 at d+250 (d <= 345)
    inst, ss = row_instance(H=2, ig_cells=[((0, 1), 500.0), ((1, 1), 800.0)], window=((0.0, 600.0),))
    assert latest(inst, ss)[2] == 424


def test_hand_worked_forbidden_turn():
    # 2 x 3, shelter at n0_2, cell (0,1) burns from 300, horizon 1000. Direct: d <= 224. Row 1 avoids
    # the fire: d <= 1000 - 200 - 5 = 795. Banning the straight turn n1_0->n1_1->n1_2 leaves only routes
    # through (0,1): 224 (also via n0_1 -> n1_1 -> n1_2 -> n0_2). The relaxation ignores turn rules.
    kw = dict(H=2, W=3, ig_cells=[((0, 1), 300.0)], horizon=1000.0)
    inst, ss = row_instance(**kw)
    assert latest(inst, ss)[2] == 795
    ban = [(eid((1, 0), (1, 1)), eid((1, 1), (1, 2)))]
    inst, ss = row_instance(**kw, forbidden=ban)
    rh, sw, ld = latest(inst, ss)
    assert ld == 224
    assert rh.latest_arrival_neg(rh.class_targets(0))[rh.node(nid(0, 0))] == 795


def test_waiting_rules_and_release():
    # the shelter opens at 1000; the fire closes the row after 424 -> a vehicle must wait at the shelter.
    inst, ss = row_instance(ig_cells=[((0, 1), 500.0)], window=((1000.0, 1e6),))
    assert latest(inst, ss)[2] == 424                        # waitable shelter: arrive 574, unload at 1000
    _, sw, _ = latest(inst, ss)
    route, _, unload_at = sw.witness(0, sw.reach.node(nid(0, 0)), 424)
    assert route.arrival == 574 and unload_at == 1000
    # only the facility is waitable and every U-turn is banned (no driving back and forth to pass time)
    uturns = [(eid((0, c), (0, c + d)), eid((0, c + d), (0, c))) for c in range(4) for d in (-1, 1) if 0 <= c + d < 4]
    inst, ss = row_instance(ig_cells=[((0, 1), 500.0)], window=((1000.0, 1e6),), waitable={(0, 0)}, forbidden=uturns)
    rh, sw, ld = latest(inst, ss)
    assert ld is None                                        # no checkable route ...
    assert rh.latest_arrival_neg(rh.class_targets(0))[rh.node(nid(0, 0))] == 425   # ... the relaxation waits anywhere
    # release after the fire closes the road: nothing leaves after release + boarding
    inst, ss = row_instance(ig_cells=[((0, 1), 500.0)], release=420.0)
    assert latest(inst, ss)[2] is None                       # 420 + 10 > 424


# ---------------------------------------------------------------- plain-Python cross-check
def brute_R(rh: Reach, targets, fresh_nodes):
    """The sweep's recursion written out state by state (no vectorisation)."""
    Hi, E = rh.Hi, rh.E
    states = list(range(E)) + [("fresh", v) for v in fresh_nodes]
    tmask = {}
    for tg in targets:
        m = rh._target_mask(tg)
        tmask[tg.node] = m if tg.node not in tmask else (tmask[tg.node] | m)
    R = {s: [False] * (Hi + 2) for s in states}

    def node_of(s):
        return s[1] if isinstance(s, tuple) else rh.headl[s]
    for t in range(Hi, -1, -1):
        for s in states:
            v = node_of(s)
            ok = bool(v in tmask and tmask[v][t])
            ban = () if isinstance(s, tuple) else rh.forbidden.get(s, ())
            for e in rh.out[v]:
                if ok:
                    break
                if e in ban:
                    continue
                a = t + rh.Tl[e]
                ok = a <= Hi and bool(rh.okT[t, e]) and R[e][a]
            if not ok and t < Hi and rh.WT[t, v]:
                ok = R[s][t + 1]
            R[s][t] = ok
    return R


@pytest.mark.parametrize("seed", range(8))
def test_sweep_matches_plain_recursion(seed):
    inst, ss, _ = random_case(300 + seed)
    if ss.meta.horizon_s > 1000:
        ss = make_set(ss.ignite_s, ss.extinguish_s, ss.supported, horizon=900.0)
    rh = Reach(inst, ss)
    fresh = sorted({rh.node(f.node) for f in inst.facilities})
    for c in range(3):
        tgs = rh.class_targets(c)
        sw = rh.sweep([tgs], fresh)
        R = brute_R(rh, tgs, fresh)
        for e in range(rh.E):
            np.testing.assert_array_equal(sw.R[: rh.Hi + 1, 0, e], np.array(R[e][: rh.Hi + 1]))
        for v in fresh:
            np.testing.assert_array_equal(sw.R[: rh.Hi + 1, 0, sw.fresh[v]], np.array(R[("fresh", v)][: rh.Hi + 1]))


@pytest.mark.parametrize("seed", range(8))
def test_route_is_the_earliest_arrival_on_monotone_hazards(seed):
    inst, ss, _ = random_case(400 + seed)
    ig = ss.ignite_s.copy()
    ex = np.where(np.isfinite(ig), np.inf, ss.extinguish_s)       # burning cells keep burning: monotone
    ss = make_set(ig, ex, ss.supported, horizon=min(ss.meta.horizon_s, 900.0))
    rh = Reach(inst, ss)
    for src in range(min(rh.N, 4)):
        for t0 in (0, 37, 150):
            # brute force: forward over (state, t) with the same masks
            reach_t = {("fresh", src): t0}
            frontier = [(t0, ("fresh", src))]
            best = {}
            while frontier:
                frontier.sort()
                t, s = frontier.pop(0)
                v = s[1] if isinstance(s, tuple) else rh.headl[s]
                best.setdefault(v, t)
                ban = () if isinstance(s, tuple) else rh.forbidden.get(s, ())
                for e in rh.out[v]:
                    if e in ban:
                        continue
                    d = t
                    while d <= rh.Hi and not rh.okT[d, e] and rh.WT[d, v]:
                        d += 1
                    if d <= rh.Hi and rh.okT[d, e] and d + rh.Tl[e] < reach_t.get(e, POS_INF):
                        reach_t[e] = d + rh.Tl[e]
                        frontier.append((d + rh.Tl[e], e))
            for dst in range(rh.N):
                r = rh.route(src, t0, dst)
                if dst not in best:
                    assert r is None
                else:
                    assert r is not None and r.arrival == best[dst], (src, t0, dst)
                    assert rh.route_ok(r, src)


# ------------------------------------------------------------ soundness against the oracle
@pytest.mark.parametrize("seed", range(10))
def test_edge_masks_agree_with_the_oracle(seed):
    """POSITIVE usable => hazard_contract finds no contact and full support; NEGATIVE blocked =>
    certain flame contact by the horizon (the oracle's model_no_route FLAME_CONTACT)."""
    inst, ss, _ = random_case(500 + seed)
    rh = Reach(inst, ss)
    oracle = Oracle(inst, ss)
    rng = np.random.default_rng(seed)
    for e in rng.choice(rh.E, size=min(rh.E, 12), replace=False).tolist():
        geom = rh.index.edge_geometry(rh.edge_ids[e])
        T = rh.Tl[e]
        for d in rng.integers(0, rh.Hi + 1, size=25).tolist() + [rh.Hi - T]:
            if d < 0:
                continue
            a = d + rh.off
            hz = ss.query_uniform(geom, a, a + T)
            if rh.okT[d, e]:
                assert all(h.contact is False and h.supported for h in hz), (e, d)
            blocked_neg = any(lo <= d <= hi for lo, hi in zip(rh.neg_lo[e], rh.neg_hi[e]))
            if blocked_neg:
                state, reasons = oracle._classify(hz, a, a + T, geom)
                assert state is State.MODEL_NO_ROUTE and "FLAME_CONTACT" in reasons, (e, d)
            if not rh.edge_unsupported[e] and d + T <= rh.Hi:
                rows, cols, t0, t1, _ = contact_records(ss.grid, geom, a, a + T)
                hit = (ss.supported[:, rows, cols] & (ss.extinguish_s[:, rows, cols] > ss.ignite_s[:, rows, cols])
                       & (ss.ignite_s[:, rows, cols] <= t1 + 1e-3) & (ss.extinguish_s[:, rows, cols] > t0 - 1e-3))
                if not hit.any():                  # clear by a millisecond: the positive mask must allow it
                    assert rh.okT[d, e], (e, d)


@pytest.mark.parametrize("seed", range(12))
def test_relaxations_bracket_checked_trips(seed):
    """Every trip the oracle checks leaves its facility no later than the certain-contact relaxation's
    latest departure, and its vehicle gets there no earlier than the relaxation's earliest arrival."""
    inst, ss, sol = random_case(600 + seed)
    rh = Reach(inst, ss)
    plan = Oracle(inst, ss).check_plan(sol)
    ld = {c: rh.latest_arrival_neg(rh.class_targets(c)) for c in range(3)}
    fac = {f.id: f for f in inst.facilities}
    for it, res in zip(sol.itineraries, plan.vehicles):
        v = next(x for x in inst.vehicles if x.id == it.vehicle)
        ea = rh.earliest_arrival_neg(rh.node(v.depot), int(v.start_s))
        for trip in res.trips:
            if trip.state is not State.CHECKED:
                continue
            for fid, cc in trip.by_facility.items():
                fn = rh.node(fac[fid].node)
                boards = [j for j, a in enumerate(it.actions[: trip.action]) if a.kind == "board" and a.facility == fid]
                last = boards[-1]
                depart = res.actions[last].t_end
                assert ea[fn] <= res.actions[boards[0]].t_start
                for c in range(3):
                    if cc.vector()[c]:
                        assert ld[c][fn] >= depart > NEG_INF, (fid, c)
