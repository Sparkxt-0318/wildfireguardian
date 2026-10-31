"""Property (hypothesis): the relaxation claims behind a scoped model_no_route leave no trip.

Whenever the oracle accepts a relaxation claim for a class at a facility (``UNSERVABLE:NO_ROUTE``,
``NO_VEHICLE_IN_TIME`` or ``NO_TRIP_BY_HORIZON``), an exhaustive search on the 1 s lattice finds no delivery
trip for that class: no vehicle that goes from its depot (from its start), boards one resident at the
facility after the release, reaches a shelter that accepts the class and unloads inside an opening window,
with every occupancy ending by the horizon and the trip within the vehicle's shift, while avoiding flame
contact as ``hazard_contract`` itself reports it. Every trip the oracle checks avoids contact, so none is
checked either. The search is independent of :mod:`evacplan.reach` (contact comes from ``hazard_contract``
queries) and more permissive than the oracle (waits anywhere, no turn rules, unknown cells passable), so it
covers every checked trip; a checked deadline must give it a trip from the facility (it is not vacuous).

Tiny SYNTHETIC instances with persistent burning and whole-second data: the lattice is complete, so the
claims are certified, and contact is monotone in the departure time (a cell that burns keeps burning), which
lets the search find each occupancy's first contact departure by bisection on ``hazard_contract`` queries.
"""
from __future__ import annotations

import math
from collections import defaultdict

import pytest
from hypothesis import HealthCheck, event, given, settings
from hypothesis import strategies as st

from evacplan import Oracle, State
from evacplan.deadlines import class_deadlines
from evacplan.oracle import NO_ROUTE, NO_TRIP_BY_HORIZON, NO_VEHICLE_IN_TIME, RELAXATION_CLAIMS, UNSERVABLE_PREFIX
from evacplan.schema import CLASSES, InstanceIndex
from evacplan_testkit import (
    NAN, board, drive, facility, grid_graph, instance, itinerary, make_set, nid, path, quiet, shelter, unload,
    vehicle,
)

PERSIST = 1e9


class Lattice:
    """Exhaustive search for one-resident delivery trips on the 1 s lattice of an instance whose cells burn
    persistently (contact is then monotone in the start time of an occupancy)."""

    def __init__(self, inst, ss):
        burns = ss.supported & (ss.extinguish_s > ss.ignite_s) & (ss.ignite_s <= ss.meta.horizon_s)
        assert not (burns & (ss.extinguish_s <= ss.meta.horizon_s)).any(), "needs persistent burning"
        self.inst, self.ss = inst, ss
        self.index = InstanceIndex(inst)
        self.off = float(inst.hazard.t0_offset_s)
        self.Hi = int(math.floor(ss.meta.horizon_s - self.off + 1e-9))
        self.out = defaultdict(list)
        for e in inst.graph.edges:
            self.out[e.u].append((e.id, e.v, int(e.travel_time_s)))
        self._first: dict = {}

    def _contact(self, kind: str, what: str, t: int, d: int) -> bool:
        a, b = t + self.off, t + d + self.off
        if kind == "edge":
            hz = self.ss.query_uniform(self.index.edge_geometry(what), a, b)
        else:
            hz = self.ss.query(self.index.node_xy(what), a, b)
        return any(h.contact is True for h in hz)

    def _first_contact(self, kind: str, what: str, d: int) -> int:
        """The earliest start t in [0, Hi - d] of a ``d``-second occupancy with contact (Hi - d + 1: none)."""
        key = (kind, what, d)
        if key not in self._first:
            lo, hi = 0, self.Hi - d
            if hi < 0 or not self._contact(kind, what, hi, d):
                self._first[key] = max(hi, -1) + 1
            else:
                while lo < hi:                      # invariant: contact at hi
                    mid = (lo + hi) // 2
                    if self._contact(kind, what, mid, d):
                        hi = mid
                    else:
                        lo = mid + 1
                self._first[key] = lo
        return self._first[key]

    def edge_ok(self, edge: str, t: int, T: int) -> bool:
        return t + T <= self.Hi and t < self._first_contact("edge", edge, T)

    def stay_ok(self, node: str, t: int, d: int) -> bool:
        return t + d <= self.Hi and t < self._first_contact("node", node, d)

    def trip_exists(self, c: int, fac, start_node: str, start_t: int, shift_end: float | None = None) -> bool:
        """Is there a trip from ``start_node`` at ``start_t`` that boards one resident of class ``c`` at
        ``fac`` and unloads it at an accepting shelter, avoiding contact, by the horizon and the shift end?"""
        rel = int(math.ceil(fac.release_s - 1e-6))
        b = int(fac.boarding_s.vector()[c])
        drops = defaultdict(list)
        for s in self.inst.shelters:
            if s.capacity.vector()[c] > 0:
                drops[s.node].append((int(s.unloading_s.vector()[c]), s.open_windows))
        seen = set()
        stack = [(start_node, int(start_t), False)]
        while stack:
            v, t, loaded = stack.pop()
            if t > self.Hi or (v, t, loaded) in seen:
                continue
            seen.add((v, t, loaded))
            if loaded:
                for u, windows in drops.get(v, ()):
                    if ((shift_end is None or t + u <= shift_end + 1e-6) and any(a <= t and t + u <= w for a, w in windows)
                            and self.stay_ok(v, t, u)):
                        return True
            elif v == fac.node and t >= rel and self.stay_ok(v, t, b):
                stack.append((v, t + b, True))
            if self.stay_ok(v, t, 1):
                stack.append((v, t + 1, loaded))
            for edge, w, T in self.out[v]:
                if self.edge_ok(edge, t, T):
                    stack.append((w, t + T, loaded))
        return False


def assert_claims_leave_no_trip(inst, ss) -> list[str]:
    """The property on one instance; returns the deadline states and causes seen."""
    lat = Lattice(inst, ss)
    fac = {f.id: f for f in inst.facilities}
    seen = []
    for d in class_deadlines(inst, ss):
        c, f = CLASSES.index(d.mobility_class), fac[d.facility]
        claim = d.cause[len(UNSERVABLE_PREFIX):] if d.state is State.MODEL_NO_ROUTE else None
        seen.append(f"{d.state.value}: {claim or d.cause}")
        if claim in RELAXATION_CLAIMS:
            for v in inst.vehicles:
                if v.capacity()[c] > 0:
                    end = None if v.shift_limit_s is None else v.start_s + v.shift_limit_s
                    assert not lat.trip_exists(c, f, v.depot, int(v.start_s), end), (claim, v.id, d.detail)
            if claim == NO_ROUTE:                 # not even a vehicle waiting at the facility from time 0
                assert not lat.trip_exists(c, f, f.node, 0), d.detail
        if d.state is State.CHECKED:              # the probe's trip is one the search must find
            assert lat.trip_exists(c, f, f.node, 0), d
    return seen


@st.composite
def tiny_cases(draw):
    """A tiny SYNTHETIC instance: 1-2 x 2-4 lattice, 1-2 members with persistent burning (some cells
    unknown), one facility, 1-2 shelters, 1-2 vehicles; short horizons, late starts and short shifts so
    that every kind of relaxation claim occurs."""
    H, W = draw(st.integers(1, 2)), draw(st.integers(2, 4))
    K = draw(st.integers(1, 2))
    cells = [(r, c) for r in range(H) for c in range(W)]
    ig = quiet(H, W, K)
    for k in range(K):
        for r, c in cells:
            ig[k, r, c] = draw(st.sampled_from([math.inf] * 6 + [-50.0, 0.0, 40.0, 90.0, 150.0, 250.0, NAN]))
    horizon = draw(st.sampled_from([60.0, 100.0, 150.0, 250.0, 400.0]))
    ss = make_set(ig, horizon=horizon, burn=PERSIST)
    travel = draw(st.sampled_from([20.0, 30.0, 50.0]))
    waitable = set(draw(st.lists(st.sampled_from(cells), unique=True)))
    pick = st.sampled_from(cells)
    secs = st.sampled_from([0.0, 5.0, 15.0])
    room = st.sampled_from([3, 3, 3, 0])
    fr, fc = draw(pick)
    if draw(st.sampled_from([False, False, False, True])):    # the facility itself burns early in member 0
        ig[0, fr, fc] = draw(st.sampled_from([-50.0, 0.0, 30.0]))
        ss = make_set(ig, horizon=horizon, burn=PERSIST)
    fac = facility("F", nid(fr, fc), *draw(st.tuples(st.integers(0, 3), st.integers(0, 2), st.integers(0, 1))),
                   board=draw(st.tuples(secs, secs, secs)), release=draw(st.sampled_from([0.0, 0.0, 30.0])))
    windows = [((0.0, 1e5),), ((0.0, 1e5),), ((60.0, 1e5),), ((0.0, 120.0),)]
    shelters = [shelter(f"S{i}", nid(*draw(pick)), cap=draw(st.tuples(room, room, room)),
                        windows=draw(st.sampled_from(windows)), unload=draw(st.tuples(secs, secs, secs)))
                for i in range(draw(st.integers(1, 2)))]
    vehicles = [vehicle(f"V{i}", nid(*draw(pick)), start=draw(st.sampled_from([0.0, 20.0, 60.0, 150.0])),
                        seats=draw(st.sampled_from([4, 4, 0])), wc=draw(st.sampled_from([1, 1, 0])),
                        stretchers=draw(st.sampled_from([1, 1, 0])),
                        shift=draw(st.sampled_from([None, None, 100.0, 200.0])))
                for i in range(draw(st.integers(1, 2)))]
    inst = instance(grid_graph(H, W, travel=travel, waitable=waitable), facilities=[fac], vehicles=vehicles,
                    shelters=shelters, offset=draw(st.sampled_from([0.0, 0.0, 25.0])))
    return inst, ss


@settings(max_examples=150, deadline=None, derandomize=True, suppress_health_check=[HealthCheck.too_slow])
@given(case=tiny_cases())
def test_relaxation_claims_leave_no_trip_for_an_exhaustive_search(case):
    for e in assert_claims_leave_no_trip(*case):
        event(e)


def row_case(*, horizon=400.0, ig_cells=(), vehicles=None, window=((0.0, 1e6),)):
    """1 x 4 row (test_deadlines): F (5 ambulatory, 10 s boarding) at n0_0, S at n0_3, 50 s edges."""
    ig = quiet(1, 4)
    for (r, c), t in ig_cells:
        ig[0, r, c] = t
    ss = make_set(ig, horizon=horizon, burn=PERSIST)
    inst = instance(grid_graph(1, 4), facilities=[facility("F", nid(0, 0), 5)],
                    vehicles=vehicles if vehicles is not None else [vehicle("V", nid(0, 3))],
                    shelters=[shelter("S", nid(0, 3), windows=window)])
    return inst, ss


FIXED = {      # every kind of relaxation claim, each attribution (test_deadlines), with short horizons
    NO_TRIP_BY_HORIZON + " (route)": (dict(horizon=100.0), NO_TRIP_BY_HORIZON),
    NO_TRIP_BY_HORIZON + " (vehicle)": (dict(vehicles=[vehicle("V", nid(0, 3), start=300.0)]), NO_TRIP_BY_HORIZON),
    NO_ROUTE + " (contact)": (dict(ig_cells=[((0, 0), -100.0)]), NO_ROUTE),
    NO_ROUTE + " (no fire, no horizon)": (dict(window=((0.0, 100.0),)), NO_ROUTE),
    NO_VEHICLE_IN_TIME + " (contact)": (dict(ig_cells=[((0, 1), 200.0)]), NO_VEHICLE_IN_TIME),
    NO_VEHICLE_IN_TIME + " (shift)": (dict(vehicles=[vehicle("V", nid(0, 3), shift=250.0)]), NO_VEHICLE_IN_TIME),
}


@pytest.mark.parametrize("name", list(FIXED))
def test_every_kind_of_claim_leaves_no_trip(name):
    kw, claim = FIXED[name]
    seen = assert_claims_leave_no_trip(*row_case(**kw))
    assert seen == [f"model_no_route: {claim}"]


def test_the_exhaustive_search_finds_trips_and_respects_horizon_shift_and_fire():
    inst, ss = row_case()                                       # 150 + 10 + 150 + 5 = 315 s <= 400
    lat, f = Lattice(inst, ss), inst.facilities[0]
    assert lat.trip_exists(0, f, nid(0, 3), 0) and lat.trip_exists(0, f, nid(0, 3), 85)
    assert not lat.trip_exists(0, f, nid(0, 3), 86)             # 86 + 315 = 401 > 400
    assert not lat.trip_exists(0, f, nid(0, 3), 0, shift_end=314.0)
    it = itinerary("V", drive(path((0, 3), (0, 2), (0, 1), (0, 0)), 0.0), board("F", 1),
                   drive(path((0, 0), (0, 1), (0, 2), (0, 3)), 160.0), unload("S", 1))
    assert Oracle(inst, ss).check_itinerary(it).trips[0].state is State.CHECKED      # the oracle agrees
    inst, ss = row_case(ig_cells=[((0, 1), 200.0)])
    lat = Lattice(inst, ss)
    # the trip must leave F by 124 (edge n0_1 -> n0_2 touches cell (0, 1) until d + 75 < 200)
    assert lat.trip_exists(0, f, nid(0, 0), 0) and not lat.trip_exists(0, f, nid(0, 0), 115)
    assert lat.trip_exists(0, f, nid(0, 0), 114)                # board [114, 124], leave at 124
