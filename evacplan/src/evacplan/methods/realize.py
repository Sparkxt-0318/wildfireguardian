"""Realize per-vehicle stop sequences as a timed plan on the time-dependent network (B2, B3).

A static model (B2's VRPTW) or a time-expanded one (B3's MIP) decides, per vehicle, an ordered list
of stops and what happens at each (unloadings, boardings). This module turns that into schema
actions AS SOON AS POSSIBLE: from each stop it takes the POSITIVE earliest-arrival route of
:mod:`evacplan.reach` to the next stop (contact-free in all K members, supported, by the horizon;
waits only at waitable nodes with usable stays), waits for the facility's release or the shelter's
opening window, then unloads and boards in the stop's order, under the validator's rules (vehicle
space per class, residents left, shelter capacity, release, windows, shift end, horizon). Every stop
that is kept performs an action, so the heading resets there and the next route may start fresh; a
stop where nothing can be done is skipped together with its approach.

Residents travel in UNITS: one mobility class, boarded together at one stop, unloaded at one or more
later stops. A boarding that cannot be done drops its units (and their later unloadings); an
unloading that cannot be done drops its units, and the vehicle is re-realized from its start without
them (they were already on board). Vehicles are realized one after another; shelter capacity and the
residents left at each facility are shared. Nothing here declares a state: the harness checks the
plan with :mod:`evacplan.oracle`; :meth:`Realizer.repair` optionally uses the oracle to drop the units
of every trip it does not check (and of all later trips of that vehicle).
"""
from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field

from ..oracle import Oracle, State
from ..reach import Reach
from ..schema import Board, ClassCounts, Instance, Itinerary, Solution, Unload, Wait
from .dispatch import Dispatcher, _dur

BOARD = "board"
UNLOAD = "unload"


@dataclass(frozen=True)
class Unit:
    """Residents of one class of one facility, boarded together at stop ``board_stop`` and unloaded at
    the stops in ``drops`` (``(stop index, shelter, residents)``, residents summing to ``n``)."""

    facility: str
    cls: int
    n: int
    board_stop: int
    drops: tuple[tuple[int, str, int], ...]

    def __post_init__(self):
        if self.n <= 0 or sum(m for _, _, m in self.drops) != self.n:
            raise ValueError(f"unit {self}: the unloaded residents must add up to n > 0")
        if any(s <= self.board_stop or m <= 0 for s, _, m in self.drops):
            raise ValueError(f"unit {self}: every unloading must come after the boarding stop")


@dataclass(frozen=True)
class Stop:
    """A graph node and the actions there, in execution order: ``("unload", shelter)``, ``("board", facility)``."""

    node: str
    order: tuple[tuple[str, str], ...]


@dataclass
class Sequence:
    vehicle: str
    stops: list[Stop]
    units: list[Unit]


@dataclass
class VehiclePlan:
    vehicle: str
    actions: list = field(default_factory=list)
    stop_of: list[int] = field(default_factory=list)       # stop index of each action
    kept: set[int] = field(default_factory=set)           # units delivered by this plan
    dropped: dict[int, str] = field(default_factory=dict)  # unit -> reason
    restarts: int = 0


@dataclass
class Realized:
    vehicles: dict[str, VehiclePlan]

    def solution(self, instance: Instance, method: str, provenance: dict | None = None) -> Solution:
        its = [Itinerary(vehicle=vid, actions=list(vp.actions)) for vid, vp in self.vehicles.items() if vp.actions]
        return Solution(instance=instance.name, method=method, itineraries=its, provenance=dict(provenance or {}))

    def summary(self, sequences: list[Sequence]) -> dict:
        units = {s.vehicle: s.units for s in sequences}
        reasons: dict[str, int] = defaultdict(int)
        for vp in self.vehicles.values():
            for uid, why in vp.dropped.items():
                reasons[why] += units[vp.vehicle][uid].n
        return {
            "residents_planned": sum(u.n for s in sequences for u in s.units),
            "residents_realized": sum(units[vp.vehicle][u].n for vp in self.vehicles.values() for u in vp.kept),
            "residents_dropped": dict(sorted(reasons.items())),
            "restarts": sum(vp.restarts for vp in self.vehicles.values()),
        }


class _Restart(Exception):
    def __init__(self, units: set[int], reason: str):
        super().__init__(reason)
        self.units, self.reason = units, reason


def _compact(actions: list, stops: list[int]) -> tuple[list, list[int]]:
    """Merge adjacent waits at one node and adjacent boardings (unloadings) at one facility (shelter)."""
    out: list = []
    st: list[int] = []
    for a, s in zip(actions, stops):
        p = out[-1] if out else None
        if isinstance(a, Wait) and isinstance(p, Wait) and p.node == a.node:
            out[-1] = Wait(node=a.node, duration_s=p.duration_s + a.duration_s)
        elif isinstance(a, Board) and isinstance(p, Board) and p.facility == a.facility:
            out[-1] = Board(facility=a.facility, counts=ClassCounts.of(
                [x + y for x, y in zip(p.counts.vector(), a.counts.vector())]))
        elif isinstance(a, Unload) and isinstance(p, Unload) and p.shelter == a.shelter:
            out[-1] = Unload(shelter=a.shelter, counts=ClassCounts.of(
                [x + y for x, y in zip(p.counts.vector(), a.counts.vector())]))
        elif isinstance(a, Wait) and a.duration_s <= 0:
            continue
        else:
            out.append(a)
            st.append(s)
    return out, st


class Realizer:
    """ASAP realization of stop sequences on the POSITIVE masks (see the module docstring)."""

    def __init__(self, instance: Instance, reach: Reach, *, dispatcher: Dispatcher | None = None):
        self.inst = instance
        self.rh = reach
        self.dsp = dispatcher or Dispatcher(instance, reach)
        self.veh = {v.id: v for v in instance.vehicles}

    # ---------------------------------------------------------------- one action
    def _board(self, node: int, t: int, fid: str, cnt, end: int):
        rh, f = self.rh, self.dsp.fac[fid]
        s = max(t, int(math.ceil(f.release_s - 1e-6)))
        if s > t and not (rh.waitable[node] and rh.stay_ok(node, t, s)):
            return None
        e = s + _dur(f.boarding_s.vector(), cnt)
        if e > end or not rh.stay_ok(node, s, e):
            return None
        acts = [Wait(node=rh.node_ids[node], duration_s=float(s - t))] if s > t else []
        return acts + [Board(facility=fid, counts=ClassCounts.of(cnt))], e

    def _unload(self, node: int, t: int, sid: str, cnt, end: int):
        rh, dsp = self.rh, self.dsp
        U = _dur(dsp.shel[sid].unloading_s.vector(), cnt)
        u0 = None
        for lo, hi in dsp.windows[sid]:
            s = max(t, lo)
            if s + U <= min(hi, end, rh.Hi):
                u0 = s
                break
        if u0 is None:
            return None
        if u0 > t and not (rh.waitable[node] and rh.stay_ok(node, t, u0)):
            return None
        if not rh.stay_ok(node, u0, u0 + U):
            return None
        acts = [Wait(node=rh.node_ids[node], duration_s=float(u0 - t))] if u0 > t else []
        return acts + [Unload(shelter=sid, counts=ClassCounts.of(cnt))], u0 + U

    # ---------------------------------------------------------------- one vehicle
    def _simulate(self, seq: Sequence, active: set[int], room: dict, left: dict, plan: VehiclePlan) -> dict:
        rh, dsp = self.rh, self.dsp
        v = self.veh[seq.vehicle]
        node, t, end = rh.node(v.depot), int(v.start_s), dsp.vs[v.id].end
        cap = v.capacity()
        load = [0, 0, 0]
        acts: list = []
        stop_of: list[int] = []
        used_room: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
        used_left: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
        for si, stop in enumerate(seq.stops):
            boards: dict[str, list[int]] = {}
            bunits: dict[str, list[int]] = defaultdict(list)
            unloads: dict[str, list[int]] = {}
            uunits: dict[str, list[int]] = defaultdict(list)
            for uid in sorted(active):
                u = seq.units[uid]
                if u.board_stop == si:
                    boards.setdefault(u.facility, [0, 0, 0])[u.cls] += u.n
                    bunits[u.facility].append(uid)
                for sj, sid, m in u.drops:
                    if sj == si:
                        unloads.setdefault(sid, [0, 0, 0])[u.cls] += m
                        uunits[sid].append(uid)
            if not boards and not unloads:
                continue
            dst = rh.node(stop.node)
            mark = (len(acts), node, t)
            if dst != node:
                r = dsp.route(node, t, dst)
                if r is None:
                    if unloads:
                        raise _Restart({u for us in uunits.values() for u in us}, "no route to the shelter")
                    for us in bunits.values():
                        for uid in us:
                            plan.dropped[uid] = "no route to the facility"
                            active.discard(uid)
                    continue
                ra = rh.actions(r, node)
                acts += ra
                stop_of += [si] * len(ra)
                node, t = dst, r.arrival
            did = False
            for kind, site in stop.order:
                if kind == UNLOAD and site in unloads:
                    cnt = unloads[site]
                    room_left = [room[site][c] - used_room[site][c] for c in range(3)]
                    if any(cnt[c] > load[c] or cnt[c] > room_left[c] for c in range(3)):
                        raise _Restart(set(uunits[site]), "shelter full")
                    got = self._unload(node, t, site, cnt, end)
                    if got is None:
                        raise _Restart(set(uunits[site]), "shelter closed or stay not usable")
                    a, t = got
                    acts += a
                    stop_of += [si] * len(a)
                    for c in range(3):
                        load[c] -= cnt[c]
                        used_room[site][c] += cnt[c]
                    did = True
                elif kind == BOARD and site in boards:
                    cnt = boards[site]
                    have = [left[site][c] - used_left[site][c] for c in range(3)]
                    got = None
                    if all(load[c] + cnt[c] <= cap[c] and cnt[c] <= have[c] for c in range(3)):
                        got = self._board(node, t, site, cnt, end)
                    if got is None:
                        for uid in bunits[site]:
                            plan.dropped[uid] = "boarding not possible (space, release, stay or shift)"
                            active.discard(uid)
                        continue
                    a, t = got
                    acts += a
                    stop_of += [si] * len(a)
                    for c in range(3):
                        load[c] += cnt[c]
                        used_left[site][c] += cnt[c]
                    did = True
            if not did:                      # nothing done here: skip the stop and its approach
                del acts[mark[0]:], stop_of[mark[0]:]
                node, t = mark[1], mark[2]
        if any(load):  # pragma: no cover - every kept unit has its unloadings
            raise AssertionError(f"{seq.vehicle}: residents left on board after realization")
        return {"actions": acts, "stop_of": stop_of, "room": used_room, "left": used_left}

    def _vehicle(self, seq: Sequence, active: set[int], room: dict, left: dict) -> tuple[VehiclePlan, dict]:
        plan = VehiclePlan(vehicle=seq.vehicle)
        active = set(active)
        for _ in range(len(seq.units) + 1):
            try:
                out = self._simulate(seq, active, room, left, plan)
            except _Restart as r:
                for uid in r.units:
                    plan.dropped[uid] = r.reason
                    active.discard(uid)
                plan.restarts += 1
                continue
            plan.actions, plan.stop_of = _compact(out["actions"], out["stop_of"])
            plan.kept = set(active)
            return plan, out
        raise AssertionError("realization did not converge")  # pragma: no cover

    # ------------------------------------------------------------------- the plan
    def realize(self, sequences: list[Sequence], active: dict[str, set[int]] | None = None) -> Realized:
        """Realize every vehicle's sequence (``active``: the units still wanted per vehicle; default all)."""
        room = {sid: list(r) for sid, r in self.dsp.room.items()}
        left = {fid: list(x) for fid, x in self.dsp.left.items()}
        out: dict[str, VehiclePlan] = {}
        for seq in sequences:
            if seq.vehicle in out:
                raise ValueError(f"two sequences for vehicle {seq.vehicle!r}")
            want = set(range(len(seq.units))) if active is None else set(active.get(seq.vehicle, ()))
            plan, used = self._vehicle(seq, want, room, left)
            for uid in set(range(len(seq.units))) - want:
                plan.dropped.setdefault(uid, "not wanted")
            for sid, cnt in used["room"].items():
                for c in range(3):
                    room[sid][c] -= cnt[c]
            for fid, cnt in used["left"].items():
                for c in range(3):
                    left[fid][c] -= cnt[c]
            out[seq.vehicle] = plan
        return Realized(out)

    def repair(self, sequences: list[Sequence], realized: Realized, oracle: Oracle, method: str,
               deadline: float | None = None) -> tuple[Realized, dict]:
        """Check the plan with the oracle; for every vehicle with a trip that is not checked, drop the units
        unloaded at or after that trip's stop and realize again, until every trip is checked (or the
        deadline). A vehicle's state never improves along its itinerary, so this only turns residents the
        oracle would not count as delivered into not planned."""
        active = {vid: set(vp.kept) for vid, vp in realized.vehicles.items()}
        reasons = {vid: dict(vp.dropped) for vid, vp in realized.vehicles.items()}
        info = {"rounds": 0, "units_cut": 0, "complete": True}
        by_vid = {s.vehicle: s for s in sequences}
        while True:
            if deadline is not None and time.monotonic() > deadline:
                info["complete"] = False
                break
            sol = realized.solution(self.inst, method)
            res = oracle.check_plan(sol)
            info["rounds"] += 1
            cut = 0
            for it, vres in zip(sol.itineraries, res.vehicles):
                bad = next((t for t in vres.trips if t.state is not State.CHECKED), None)
                if bad is None:
                    continue
                vp = realized.vehicles[it.vehicle]
                stop = vp.stop_of[bad.action]
                for uid in list(active[it.vehicle]):
                    if any(s >= stop for s, _, _ in by_vid[it.vehicle].units[uid].drops):
                        active[it.vehicle].discard(uid)
                        reasons[it.vehicle][uid] = f"oracle: trip not checked ({bad.cause})"
                        cut += 1
            if not cut:
                break
            info["units_cut"] += cut
            realized = self.realize(sequences, active)
            for vid, vp in realized.vehicles.items():
                vp.dropped = {uid: reasons[vid].get(uid, why) for uid, why in vp.dropped.items()}
                reasons[vid].update(vp.dropped)
        return realized, info


__all__ = ["BOARD", "UNLOAD", "Realized", "Realizer", "Sequence", "Stop", "Unit", "VehiclePlan"]
