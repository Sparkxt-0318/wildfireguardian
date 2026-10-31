"""Shared trip machinery for the greedy baselines (B0, B1).

A trip = approach (route from the vehicle's position) -> wait for release -> board -> (wait) ->
route to a shelter -> (wait for the window) -> unload. Routes and stays use the POSITIVE masks of
:mod:`evacplan.reach` (contact-free in all K members, supported, by the horizon); capacities,
release times, windows, shifts, waits and turn rules follow the validator. Times are whole seconds.
Nothing here declares a state: the harness checks every plan with the oracle, and
:meth:`Dispatcher.repair` can use the oracle to cut itineraries before their first trip that is not
checked (peak or dose, which the relaxed masks do not model).
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from ..oracle import Oracle, State
from ..reach import Reach, Route
from ..schema import Board, ClassCounts, Instance, Itinerary, Solution, Unload, Vehicle, Wait


def _dur(per_class, counts) -> int:
    return int(sum(int(n) * int(d) for n, d in zip(counts, per_class)))


@dataclass
class Track:
    vehicle: Vehicle
    node: int
    t: int
    end: int                                   # last instant an action may end (shift and horizon)
    actions: list = field(default_factory=list)
    trips: list = field(default_factory=list)  # committed Trip objects, in order
    starts: list = field(default_factory=list)  # action index where each trip begins

    @property
    def cap(self) -> tuple[int, int, int]:
        return self.vehicle.capacity()


@dataclass(frozen=True)
class Boarding:
    route: Route                               # approach
    arrive: int
    start: int                                 # boarding start (>= release)
    end: int                                   # boarding end


@dataclass(frozen=True)
class Delivery:
    route: Route
    shelter: str
    arrive: int
    start: int                                 # unloading start
    end: int


@dataclass(frozen=True)
class Trip:
    vehicle: str
    facility: str
    counts: tuple[int, int, int]
    boarding: Boarding
    depart: int
    delivery: Delivery

    @property
    def end(self) -> int:
        return self.delivery.end


class Dispatcher:
    """Vehicle states, remaining residents and shelter capacities, and timed trips."""

    def __init__(self, instance: Instance, reach: Reach):
        self.inst = instance
        self.rh = reach
        self.fac = {f.id: f for f in instance.facilities}
        self.shel = {s.id: s for s in instance.shelters}
        self.fnode = {f.id: reach.node(f.node) for f in instance.facilities}
        self.snode = {s.id: reach.node(s.node) for s in instance.shelters}
        self.left = {f.id: list(f.residents.vector()) for f in instance.facilities}
        self.room = {s.id: list(s.capacity.vector()) for s in instance.shelters}
        self.windows = {s.id: [(int(math.ceil(a - 1e-6)), int(math.floor(b + 1e-6))) for a, b in s.open_windows]
                        for s in instance.shelters}
        self.vs: dict[str, Track] = {}
        for v in instance.vehicles:
            end = reach.Hi if v.shift_limit_s is None else min(reach.Hi, int(math.floor(v.start_s + v.shift_limit_s + 1e-6)))
            self.vs[v.id] = Track(vehicle=v, node=reach.node(v.depot), t=int(v.start_s), end=end)
        self._routes: dict[tuple[int, int, int], Route | None] = {}

    # -------------------------------------------------------------------- routing
    def route(self, src: int, t: int, dst: int) -> Route | None:
        key = (src, int(t), dst)
        if key not in self._routes:
            self._routes[key] = self.rh.route(src, int(t), dst)
        return self._routes[key]

    def accepts(self, sid: str, counts) -> bool:
        return all(self.room[sid][c] >= counts[c] for c in range(3))

    # ---------------------------------------------------------------------- stages
    def board(self, vs: Track, fid: str, counts) -> Boarding | None:
        """Approach ``fid`` from the vehicle's position, wait for release, board ``counts``."""
        rh, f, fn = self.rh, self.fac[fid], self.fnode[fid]
        if any(counts[c] > vs.cap[c] or counts[c] > self.left[fid][c] for c in range(3)) or not any(counts):
            return None
        r = self.route(vs.node, vs.t, fn)
        if r is None:
            return None
        a = r.arrival
        s = max(a, int(math.ceil(f.release_s - 1e-6)))
        if s > a and not (rh.waitable[fn] and rh.stay_ok(fn, a, s)):
            return None
        e = s + _dur(f.boarding_s.vector(), counts)
        if e > vs.end or not rh.stay_ok(fn, s, e):
            return None
        return Boarding(route=r, arrive=a, start=s, end=e)

    def hold(self, fid: str, e: int, d: int) -> bool:
        """May a vehicle that finished boarding at ``e`` stay at the facility until ``d``?"""
        fn = self.fnode[fid]
        return d == e or (d > e and bool(self.rh.waitable[fn]) and self.rh.stay_ok(fn, e, d))

    def deliver(self, vs: Track, fid: str, d: int, counts, shelters, *, first: bool = False) -> Delivery | None:
        """Route from the facility leaving at ``d`` to one of ``shelters`` (with room) and unload:
        the earliest unloading end, or the first feasible shelter in order if ``first``."""
        rh, fn = self.rh, self.fnode[fid]
        best = None
        for sid in shelters:
            if not self.accepts(sid, counts):
                continue
            sn = self.snode[sid]
            r = self.route(fn, d, sn)
            if r is None:
                continue
            a = r.arrival
            U = _dur(self.shel[sid].unloading_s.vector(), counts)
            u0 = None
            for lo, hi in self.windows[sid]:
                s = max(a, lo)
                if s + U <= min(hi, vs.end, rh.Hi):
                    u0 = s
                    break
            if u0 is None:
                continue
            if u0 > a and not (rh.waitable[sn] and rh.stay_ok(sn, a, u0)):
                continue
            if not rh.stay_ok(sn, u0, u0 + U):
                continue
            cand = Delivery(route=r, shelter=sid, arrive=a, start=u0, end=u0 + U)
            if first:
                return cand
            if best is None or (cand.end, sid) < (best.end, best.shelter):
                best = cand
        return best

    def trip(self, vs: Track, fid: str, counts, shelters, *, depart: int | None = None,
             boarding: Boarding | None = None, first: bool = False) -> Trip | None:
        """A complete trip leaving the facility right after boarding (or at ``depart``)."""
        b = boarding or self.board(vs, fid, counts)
        if b is None:
            return None
        d = b.end if depart is None else int(depart)
        if not self.hold(fid, b.end, d):
            return None
        dl = self.deliver(vs, fid, d, counts, shelters, first=first)
        if dl is None:
            return None
        return Trip(vehicle=vs.vehicle.id, facility=fid, counts=tuple(int(x) for x in counts), boarding=b, depart=d,
                    delivery=dl)

    # --------------------------------------------------------------------- commit
    def actions(self, vs: Track, tr: Trip) -> list:
        rh, fid = self.rh, tr.facility
        fn, sn = self.fnode[fid], self.snode[tr.delivery.shelter]
        b, dl = tr.boarding, tr.delivery
        acts = rh.actions(b.route, vs.node)
        if b.start > b.arrive:
            acts.append(Wait(node=rh.node_ids[fn], duration_s=float(b.start - b.arrive)))
        acts.append(Board(facility=fid, counts=ClassCounts.of(tr.counts)))
        if tr.depart > b.end:
            acts.append(Wait(node=rh.node_ids[fn], duration_s=float(tr.depart - b.end)))
        acts += rh.actions(dl.route, fn)
        if dl.start > dl.arrive:
            acts.append(Wait(node=rh.node_ids[sn], duration_s=float(dl.start - dl.arrive)))
        acts.append(Unload(shelter=dl.shelter, counts=ClassCounts.of(tr.counts)))
        return acts

    def commit(self, tr: Trip) -> None:
        vs = self.vs[tr.vehicle]
        vs.starts.append(len(vs.actions))
        vs.actions += self.actions(vs, tr)
        vs.trips.append(tr)
        vs.node = self.snode[tr.delivery.shelter]
        vs.t = tr.end
        for c in range(3):
            self.left[tr.facility][c] -= tr.counts[c]
            self.room[tr.delivery.shelter][c] -= tr.counts[c]
            if self.left[tr.facility][c] < 0 or self.room[tr.delivery.shelter][c] < 0:  # pragma: no cover
                raise AssertionError("committed a trip beyond the residents or the shelter capacity")

    # ------------------------------------------------------------------- outputs
    def solution(self, method: str, provenance: dict | None = None) -> Solution:
        its = [Itinerary(vehicle=vid, actions=list(vs.actions)) for vid, vs in self.vs.items() if vs.actions]
        return Solution(instance=self.inst.name, method=method, itineraries=its, provenance=dict(provenance or {}))

    def repair(self, oracle: Oracle, deadline: float | None = None) -> dict:
        """Check each vehicle's itinerary with the oracle and cut it before its first trip that is not
        checked (those residents are no longer planned). Stops early at ``deadline`` (monotonic)."""
        cut = {"vehicles_checked": 0, "trips_cut": 0, "residents_cut": 0, "complete": True}
        for vid, vs in self.vs.items():
            if not vs.actions:
                continue
            if deadline is not None and time.monotonic() > deadline:
                cut["complete"] = False
                break
            res = oracle.check_itinerary(Itinerary(vehicle=vid, actions=list(vs.actions)))
            cut["vehicles_checked"] += 1
            bad = next((k for k, t in enumerate(res.trips) if t.state is not State.CHECKED), None)
            if bad is None:
                continue
            for tr in vs.trips[bad:]:
                cut["trips_cut"] += 1
                cut["residents_cut"] += sum(tr.counts)
                for c in range(3):
                    self.left[tr.facility][c] += tr.counts[c]
                    self.room[tr.delivery.shelter][c] += tr.counts[c]
            vs.actions = vs.actions[: vs.starts[bad]]
            vs.trips, vs.starts = vs.trips[:bad], vs.starts[:bad]
            last = vs.trips[-1] if vs.trips else None
            vs.node = self.snode[last.delivery.shelter] if last else self.rh.node(vs.vehicle.depot)
            vs.t = last.end if last else int(vs.vehicle.start_s)
        return cut


__all__ = ["Boarding", "Delivery", "Dispatcher", "Trip", "Track"]
