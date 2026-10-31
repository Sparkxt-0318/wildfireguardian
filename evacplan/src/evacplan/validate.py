"""Hazard-free validator: structure, times and resources of a Solution against an Instance.

It turns each itinerary into a timeline of occupancies (:class:`Segment`) and lists every rule
violation as an :class:`Issue` tied to the action where it happens. It declares no final state:
:mod:`evacplan.oracle` maps issues to ``model_no_route`` (a vehicle's state never improves after
its first issue).

Timeline (instance clock, seconds)
----------------------------------
A vehicle starts at its depot at ``start_s``. Waits, boardings and unloadings start when the
previous action ends. A drive leaves at its ``depart_s``; if that is later than the clock, the
vehicle idles at its current node in between (an ``idle`` segment, subject to the waiting rule).
Each edge is one ``drive`` segment of ``travel_time_s``. Stationary segments are the node over a
closed interval. Times compare with tolerance ``TIME_TOL_S``.

Rules (issue codes)
-------------------
* references: ``UNKNOWN_VEHICLE``, ``DUPLICATE_ITINERARY``, ``UNKNOWN_EDGE``, ``UNKNOWN_NODE``,
  ``UNKNOWN_FACILITY``, ``UNKNOWN_SHELTER`` (times after these are undefined);
* path: ``DISCONNECTED_PATH`` (edge does not start at the vehicle's node), ``FORBIDDEN_TURN``
  (turn context persists through waits and idles and resets at boarding/unloading stops);
* time: ``TIME_TRAVEL`` (departure before the clock), ``SHIFT_LIMIT`` (an action ends after
  ``start_s + shift_limit_s``);
* waiting: ``NOT_WAITABLE`` (wait at a non-waitable node), ``IDLE_NOT_WAITABLE`` (idle before a
  departure at a non-waitable node), ``WRONG_LOCATION`` (wait/board/unload away from its node);
* people: ``BEFORE_RELEASE`` (boarding starts before the facility's release time),
  ``VEHICLE_CAPACITY`` (seats, wheelchair slots or stretcher slots exceeded),
  ``UNLOAD_EXCEEDS_LOAD``, ``SHELTER_CLOSED`` (unloading not inside one closed opening window),
  ``NOT_UNLOADED`` (residents still on board after the last action; action index = len(actions));
* shared across ALL vehicles, first come first served by start time (ties: itinerary order,
  then action order; actions whose times are undefined count first): ``OVERBOARDED`` (more
  residents of a class boarded at a facility than live there: someone boarded twice) and
  ``SHELTER_CAPACITY``. Every stated boarding/unloading counts, valid or not, so tightening any
  constraint can only add issues.

Residents are anonymous within (facility, class); unloading takes them first in, first out,
which only matters for per-facility reporting.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from .schema import CLASSES, Board, Drive, Instance, InstanceIndex, Itinerary, Solution, Unload, Wait

TIME_TOL_S = 1e-6

UNKNOWN_VEHICLE = "UNKNOWN_VEHICLE"
DUPLICATE_ITINERARY = "DUPLICATE_ITINERARY"
UNKNOWN_EDGE = "UNKNOWN_EDGE"
UNKNOWN_NODE = "UNKNOWN_NODE"
UNKNOWN_FACILITY = "UNKNOWN_FACILITY"
UNKNOWN_SHELTER = "UNKNOWN_SHELTER"
DISCONNECTED_PATH = "DISCONNECTED_PATH"
FORBIDDEN_TURN = "FORBIDDEN_TURN"
TIME_TRAVEL = "TIME_TRAVEL"
SHIFT_LIMIT = "SHIFT_LIMIT"
NOT_WAITABLE = "NOT_WAITABLE"
IDLE_NOT_WAITABLE = "IDLE_NOT_WAITABLE"
WRONG_LOCATION = "WRONG_LOCATION"
BEFORE_RELEASE = "BEFORE_RELEASE"
VEHICLE_CAPACITY = "VEHICLE_CAPACITY"
UNLOAD_EXCEEDS_LOAD = "UNLOAD_EXCEEDS_LOAD"
SHELTER_CLOSED = "SHELTER_CLOSED"
NOT_UNLOADED = "NOT_UNLOADED"
OVERBOARDED = "OVERBOARDED"
SHELTER_CAPACITY = "SHELTER_CAPACITY"

Vec = tuple[int, int, int]


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    vehicle: str | None = None
    itinerary: int | None = None
    action: int | None = None


@dataclass(frozen=True)
class Segment:
    """One occupancy on the instance clock: a stationary node or one edge traversed uniformly."""

    action: int
    kind: str          # "idle" | "drive" | "wait" | "board" | "unload"
    t0: float
    t1: float
    node: str | None = None
    edge: str | None = None


@dataclass(frozen=True)
class UnloadRecord:
    action: int
    shelter: str
    counts: Vec                       # residents actually taken off (never more than were on board)
    by_facility: dict[str, Vec]
    t0: float | None                  # None when the action's time is undefined
    t1: float | None


@dataclass
class Schedule:
    """Timeline and issues of one itinerary of the solution."""

    itinerary: int
    vehicle: str
    known: bool                       # the vehicle exists in the instance and this is its only itinerary
    n_actions: int
    start_s: float | None
    segments: list[Segment] = field(default_factory=list)
    spans: list[tuple[float, float] | None] = field(default_factory=list)
    unloads: list[UnloadRecord] = field(default_factory=list)
    boarded: dict[str, Vec] = field(default_factory=dict)        # per facility (instance facilities only)
    onboard_end: dict[str, Vec] = field(default_factory=dict)    # per facility, still on board at the end
    clock_end: float | None = None    # clock after the last action with a defined time
    complete: bool = False            # every action has a defined time
    issues: list[Issue] = field(default_factory=list)

    @property
    def first_issue(self) -> int | None:
        return min((i.action for i in self.issues), default=None)


@dataclass
class ValidationReport:
    schedules: list[Schedule]

    @property
    def issues(self) -> list[Issue]:
        return [i for s in self.schedules for i in sorted(s.issues, key=lambda i: (i.action, i.code))]

    @property
    def ok(self) -> bool:
        return not any(s.issues for s in self.schedules)


@dataclass(frozen=True)
class _Event:
    t: float
    itinerary: int
    action: int
    site: str
    counts: Vec


def _vec(counts) -> Vec:
    return counts.vector()


def _add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def simulate(index: InstanceIndex, itinerary: Itinerary, position: int = 0, *,
             known: bool | None = None) -> tuple[Schedule, list[_Event], list[_Event]]:
    """Timeline, per-vehicle issues and shared-resource events of one itinerary."""
    vid = itinerary.vehicle
    actions = itinerary.actions
    n = len(actions)
    veh = index.vehicles.get(vid)
    if known is None:
        known = veh is not None
    sch = Schedule(itinerary=position, vehicle=vid, known=known and veh is not None, n_actions=n,
                   start_s=veh.start_s if veh is not None else None, spans=[None] * n)

    def issue(code: str, j: int, msg: str) -> None:
        sch.issues.append(Issue(code, msg, vehicle=vid, itinerary=position, action=j))

    boards: list[_Event] = []
    unloads: list[_Event] = []
    if veh is None:
        issue(UNKNOWN_VEHICLE, 0, f"vehicle {vid!r} is not in the instance")
    elif not sch.known:
        issue(DUPLICATE_ITINERARY, 0, f"vehicle {vid!r} already has an itinerary")
    timed = sch.known
    pos = veh.depot if veh is not None else None
    clock = veh.start_s if veh is not None else math.nan
    limit = (veh.start_s + veh.shift_limit_s) if (veh is not None and veh.shift_limit_s is not None) else math.inf
    cap = veh.capacity() if veh is not None else (0, 0, 0)
    last_edge: str | None = None
    load = [0, 0, 0]
    queues: list[deque] = [deque(), deque(), deque()]
    shift_flagged = False

    for j, a in enumerate(actions):
        # ---------------------------------------------------- people (all actions, times or not)
        if isinstance(a, Board):
            f = index.facilities.get(a.facility)
            cnt = _vec(a.counts)
            if f is not None:
                for c in range(3):
                    if cnt[c]:
                        load[c] += cnt[c]
                        queues[c].append([f.id, cnt[c]])
                sch.boarded[f.id] = _add(sch.boarded.get(f.id, (0, 0, 0)), cnt)
                if any(load[c] > cap[c] for c in range(3)) and veh is not None:
                    over = [CLASSES[c] for c in range(3) if load[c] > cap[c]]
                    issue(VEHICLE_CAPACITY, j, f"on board {tuple(load)} exceeds space {cap} for {over}")
        elif isinstance(a, Unload):
            cnt = _vec(a.counts)
            if any(cnt[c] > load[c] for c in range(3)):
                issue(UNLOAD_EXCEEDS_LOAD, j, f"unloads {cnt} but only {tuple(load)} on board")
            moved = [0, 0, 0]
            by_fac: dict[str, list[int]] = {}
            for c in range(3):
                need = min(cnt[c], load[c])
                moved[c] = need
                load[c] -= need
                while need:
                    head = queues[c][0]
                    take = min(need, head[1])
                    by_fac.setdefault(head[0], [0, 0, 0])[c] += take
                    head[1] -= take
                    need -= take
                    if head[1] == 0:
                        queues[c].popleft()
            rec_by_fac = {k: tuple(v) for k, v in sorted(by_fac.items())}
        # ------------------------------------------------------------------- timeline
        if not timed:
            if isinstance(a, Board):
                boards.append(_Event(-math.inf, position, j, a.facility, _vec(a.counts)))
            elif isinstance(a, Unload):
                unloads.append(_Event(-math.inf, position, j, a.shelter, _vec(a.counts)))
                sch.unloads.append(UnloadRecord(j, a.shelter, tuple(moved), rec_by_fac, None, None))
            continue
        start = clock
        if isinstance(a, Drive):
            if a.depart_s < clock - TIME_TOL_S:
                issue(TIME_TRAVEL, j, f"departs at {a.depart_s} before the vehicle is free at {clock}")
            if a.depart_s > clock:
                if a.depart_s > clock + TIME_TOL_S and not index.nodes[pos].waitable:
                    issue(IDLE_NOT_WAITABLE, j, f"idles {a.depart_s - clock:g} s at non-waitable node {pos!r}")
                sch.segments.append(Segment(j, "idle", clock, a.depart_s, node=pos))
            else:
                start = a.depart_s
            t = a.depart_s
            for eid in a.edges:
                e = index.edges.get(eid)
                if e is None:
                    issue(UNKNOWN_EDGE, j, f"edge {eid!r} is not in the graph")
                    timed = False
                    break
                if e.u != pos:
                    issue(DISCONNECTED_PATH, j, f"edge {eid!r} starts at {e.u!r}, the vehicle is at {pos!r}")
                if last_edge is not None and (last_edge, eid) in index.forbidden:
                    issue(FORBIDDEN_TURN, j, f"turn {last_edge!r} -> {eid!r} is forbidden")
                sch.segments.append(Segment(j, "drive", t, t + e.travel_time_s, edge=eid))
                t = t + e.travel_time_s
                pos = e.v
                last_edge = eid
            if not timed:
                continue
            clock = t
        elif isinstance(a, Wait):
            if a.node not in index.nodes:
                issue(UNKNOWN_NODE, j, f"node {a.node!r} is not in the graph")
                timed = False
                continue
            if a.node != pos:
                issue(WRONG_LOCATION, j, f"waits at {a.node!r} but the vehicle is at {pos!r}")
            if not index.nodes[a.node].waitable:
                issue(NOT_WAITABLE, j, f"node {a.node!r} is not waitable")
            sch.segments.append(Segment(j, "wait", clock, clock + a.duration_s, node=pos))
            clock = clock + a.duration_s
        elif isinstance(a, Board):
            f = index.facilities.get(a.facility)
            if f is None:
                issue(UNKNOWN_FACILITY, j, f"facility {a.facility!r} is not in the instance")
                boards.append(_Event(-math.inf, position, j, a.facility, _vec(a.counts)))
                timed = False
                continue
            if f.node != pos:
                issue(WRONG_LOCATION, j, f"boards at facility {f.id!r} (node {f.node!r}) but the vehicle is at {pos!r}")
            if clock < f.release_s - TIME_TOL_S:
                issue(BEFORE_RELEASE, j, f"boarding starts at {clock} before release at {f.release_s}")
            dur = f.boarding_s.duration(a.counts)
            boards.append(_Event(clock, position, j, f.id, _vec(a.counts)))
            sch.segments.append(Segment(j, "board", clock, clock + dur, node=pos))
            clock = clock + dur
            last_edge = None
        elif isinstance(a, Unload):
            s = index.shelters.get(a.shelter)
            if s is None:
                issue(UNKNOWN_SHELTER, j, f"shelter {a.shelter!r} is not in the instance")
                unloads.append(_Event(-math.inf, position, j, a.shelter, _vec(a.counts)))
                sch.unloads.append(UnloadRecord(j, a.shelter, tuple(moved), rec_by_fac, None, None))
                timed = False
                continue
            if s.node != pos:
                issue(WRONG_LOCATION, j, f"unloads at shelter {s.id!r} (node {s.node!r}) but the vehicle is at {pos!r}")
            dur = s.unloading_s.duration(a.counts)
            t0, t1 = clock, clock + dur
            if not any(lo - TIME_TOL_S <= t0 and t1 <= hi + TIME_TOL_S for lo, hi in s.open_windows):
                issue(SHELTER_CLOSED, j, f"unloading [{t0}, {t1}] is not inside an opening window of {s.id!r}")
            unloads.append(_Event(t0, position, j, s.id, _vec(a.counts)))
            sch.unloads.append(UnloadRecord(j, s.id, tuple(moved), rec_by_fac, t0, t1))
            sch.segments.append(Segment(j, "unload", t0, t1, node=pos))
            clock = t1
            last_edge = None
        sch.spans[j] = (start, clock)
        if clock > limit + TIME_TOL_S and not shift_flagged:
            issue(SHIFT_LIMIT, j, f"ends at {clock}, after the shift limit {limit}")
            shift_flagged = True

    sch.complete = timed
    if veh is not None:
        last = [sp for sp in sch.spans if sp is not None]
        sch.clock_end = last[-1][1] if last else veh.start_s
    rest: dict[str, list[int]] = {}
    for c in range(3):
        for fid, k in queues[c]:
            rest.setdefault(fid, [0, 0, 0])[c] += k
    sch.onboard_end = {k: tuple(v) for k, v in sorted(rest.items())}
    if any(load):
        issue(NOT_UNLOADED, n, f"{tuple(load)} residents are still on board after the last action")
    return sch, boards, unloads


def _first_come_first_served(events: list[_Event], limits: dict[str, Vec], code: str, what: str,
                             schedules: list[Schedule]) -> None:
    used: dict[str, list[int]] = {}
    for ev in sorted(events, key=lambda e: (e.t, e.itinerary, e.action)):
        lim = limits.get(ev.site)
        if lim is None:
            continue  # unknown site: already an issue of its own
        u = used.setdefault(ev.site, [0, 0, 0])
        over = []
        for c in range(3):
            u[c] += ev.counts[c]
            if ev.counts[c] and u[c] > lim[c]:
                over.append(CLASSES[c])
        if over:
            sch = schedules[ev.itinerary]
            sch.issues.append(Issue(code, f"{what} {ev.site!r}: {over} exceed {lim} (first come, first served)",
                                    vehicle=sch.vehicle, itinerary=ev.itinerary, action=ev.action))


def validate_solution(instance: Instance, solution: Solution, index: InstanceIndex | None = None) -> ValidationReport:
    """Check every itinerary and the resources shared by all vehicles. No hazard is used."""
    index = index or InstanceIndex(instance)
    schedules: list[Schedule] = []
    boards: list[_Event] = []
    unloads: list[_Event] = []
    seen: set[str] = set()
    for i, it in enumerate(solution.itineraries):
        sch, b, u = simulate(index, it, i, known=(it.vehicle in index.vehicles and it.vehicle not in seen))
        seen.add(it.vehicle)
        schedules.append(sch)
        boards += b
        unloads += u
    _first_come_first_served(boards, {f.id: f.residents.vector() for f in instance.facilities},
                             OVERBOARDED, "facility", schedules)
    _first_come_first_served(unloads, {s.id: s.capacity.vector() for s in instance.shelters},
                             SHELTER_CAPACITY, "shelter", schedules)
    return ValidationReport(schedules)
