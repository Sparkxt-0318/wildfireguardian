"""B0 independent: every facility planned alone with today's planner logic, no coordination.

Today's planner (``planner/README.md``, ``planner/docs/ARCHITECTURE.md`` section 6,
``api/dispatch.py``) treats every origin independently: departure offsets every 10 min over
[0, horizon), the K = 3 nearest shelters by straight-line distance (distinct entry nodes), one
route check per (offset, shelter) with a 120 s destination stay inside the shelter's opening
window, per offset "checked if any shelter is checked", and the departure deadline
("출발 마감") = the latest offset of the contiguous checked run from the first offset
(``latest_contiguous_checked_depart_offset_s``, the value the urgency list uses). It has no
vehicles, no capacities and no mobility classes.

B0 reproduces that per facility and adds only what a facility planning alone must know:

1. Planner check (RELAXED, :mod:`evacplan.reach`): an offset/shelter pair is checked when the
   time-dependent router finds a contact-free route (all K members) leaving the facility at the
   offset and the 120 s stay fits an opening window by the horizon. Candidates are the K nearest
   shelters that accept every mobility class of the load (the planner has no classes; without this
   a bedbound resident could be sent to a shelter without stretchers).
2. Each facility planned ALONE (as if it were the only facility, with the whole fleet and every
   shelter's full capacity): trip by trip, the vehicle that can leave the facility with a load
   EARLIEST takes it (a facility alone wants its own residents out soonest;
   ``vehicle_rule="per_resident"``: B1's least added vehicle time per resident); a load fills each class's own space (seats, wheelchair slots,
   stretchers); boarding starts at release; the vehicle leaves at the first checked 10 min offset
   after boarding, no later than the facility's contiguous deadline (the minimum over the loaded
   classes), for the checked candidate with the earliest arrival. The result is the facility's bookings: (vehicle, load, requested pickup time = the
   boarding start in its own plan).
3. No coordination: every vehicle serves all bookings made on it, first come first served by
   requested pickup time (ties: facility id), re-timed from where it actually is; a booking that can
   no longer leave by its facility's deadline (or find a checked shelter with room) is dropped and its
   residents stay unplanned. This is the double-booking a shared fleet suffers when every facility
   plans alone.

``repair`` (default off): optional oracle pass as in B1.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass

from ..oracle import Oracle
from ..reach import Reach
from .base import Method, MethodResult
from .dispatch import Dispatcher, Trip, Track

PLANNER_STEP_S = 600           # VITE_DEPARTURE_STEP_MIN = 10
PLANNER_SHELTERS = 3           # VITE_SHELTERS_PER_ORIGIN = 3
PLANNER_DWELL_S = 120          # DEFAULT_DWELL_S (API dwell_s default)


@dataclass(frozen=True)
class Booking:
    vehicle: str
    facility: str
    counts: tuple[int, int, int]
    request_s: int             # requested pickup (boarding start) in the facility's own plan


class PlannerLogic:
    """Per-facility departure sweep of today's planner (relaxed checks)."""

    def __init__(self, dsp: Dispatcher, *, step_s: int = PLANNER_STEP_S, k: int = PLANNER_SHELTERS,
                 dwell_s: int = PLANNER_DWELL_S, contiguous: bool = True):
        self.dsp, self.rh = dsp, dsp.rh
        self.step, self.k, self.dwell, self.contiguous = int(step_s), int(k), int(dwell_s), bool(contiguous)
        self.offsets = list(range(0, int(math.ceil(self.rh.H)), self.step))
        self._cand: dict = {}
        self._check: dict = {}
        self._deadline: dict = {}

    def candidates(self, fid: str, classes: frozenset[int]) -> list[str]:
        """The K nearest shelters (straight line) that accept every class, distinct nodes."""
        key = (fid, classes)
        if key not in self._cand:
            f = self.dsp.fac[fid]
            fx = self.rh.index.node_xy(f.node)[0]
            ok = [s for s in self.dsp.inst.shelters if all(s.capacity.vector()[c] > 0 for c in classes)]
            ok.sort(key=lambda s: (math.hypot(*(self.rh.index.node_xy(s.node)[0] - fx)), s.id))
            out, nodes = [], set()
            for s in ok:
                if s.node in nodes:
                    continue
                out.append(s.id)
                nodes.add(s.node)
                if len(out) == self.k:
                    break
            self._cand[key] = out
        return self._cand[key]

    def check(self, fid: str, t: int, sid: str) -> int | None:
        """Planner route check: arrival time, or None (not checked)."""
        key = (fid, t, sid)
        if key not in self._check:
            rh, dsp = self.rh, self.dsp
            fn, sn = dsp.fnode[fid], dsp.snode[sid]
            r = dsp.route(fn, t, sn)
            got = None
            if r is not None:
                a = r.arrival
                for lo, hi in dsp.windows[sid]:
                    s = max(a, lo)
                    if s + self.dwell <= min(hi, rh.Hi) and (s == a or (rh.waitable[sn] and rh.stay_ok(sn, a, s))) \
                            and rh.stay_ok(sn, s, s + self.dwell):
                        got = a
                        break
            self._check[key] = got
        return self._check[key]

    def checked_at(self, fid: str, classes: frozenset[int], t: int) -> list[str]:
        """Checked candidates at offset ``t``, earliest arrival first (the planner's best first)."""
        got = [(a, sid) for sid in self.candidates(fid, classes) if (a := self.check(fid, t, sid)) is not None]
        return [sid for _, sid in sorted(got)]

    def deadline(self, fid: str, classes: frozenset[int]) -> int | None:
        """出발 마감: the latest contiguous checked offset (or the latest checked one)."""
        key = (fid, classes)
        if key not in self._deadline:
            latest = None
            for t in self.offsets:
                if self.checked_at(fid, classes, t):
                    latest = t
                elif self.contiguous:
                    break
            self._deadline[key] = latest
        return self._deadline[key]


class B0Independent(Method):
    name = "b0_independent"

    def __init__(self, step_s: int = PLANNER_STEP_S, shelters_per_origin: int = PLANNER_SHELTERS,
                 dwell_s: int = PLANNER_DWELL_S, deadline: str = "contiguous", vehicle_rule: str = "earliest",
                 repair: bool = False, **config):
        if deadline not in ("contiguous", "latest"):
            raise ValueError("deadline must be 'contiguous' or 'latest'")
        if vehicle_rule not in ("per_resident", "earliest"):
            raise ValueError("vehicle_rule must be 'per_resident' or 'earliest'")
        super().__init__(step_s=int(step_s), shelters_per_origin=int(shelters_per_origin), dwell_s=int(dwell_s),
                         deadline=deadline, vehicle_rule=vehicle_rule, repair=bool(repair), **config)
        self.rule = vehicle_rule
        self.kw = dict(step_s=int(step_s), k=int(shelters_per_origin), dwell_s=int(dwell_s),
                       contiguous=deadline == "contiguous")
        self.do_repair = bool(repair)

    # ---------------------------------------------------------------- one trip
    @staticmethod
    def _trip(dsp: Dispatcher, pl: PlannerLogic, vs: Track, fid: str, counts) -> Trip | None:
        """A planner-style trip: depart at the first checked offset after boarding, by the deadline."""
        classes = frozenset(c for c in range(3) if counts[c] > 0)
        dl = pl.deadline(fid, classes)
        if dl is None:
            return None
        b = dsp.board(vs, fid, counts)
        if b is None:
            return None
        i = -(-b.end // pl.step)                       # first offset index at or after boarding end
        for t in pl.offsets[i:]:
            if t > dl:
                break
            shelters = [sid for sid in pl.checked_at(fid, classes, t) if dsp.accepts(sid, counts)]
            if not shelters:
                continue
            tr = dsp.trip(vs, fid, counts, shelters, depart=t, boarding=b, first=True)
            if tr is not None:
                return tr
            if not dsp.hold(fid, b.end, t):           # cannot stay at the facility until this offset
                return None
        return None

    def _loads(self, dsp: Dispatcher, pl: PlannerLogic, vs: Track, fid: str) -> list[tuple[int, int, int]]:
        left = dsp.left[fid]
        full = tuple(min(left[c], vs.cap[c]) for c in range(3))
        if not any(full):
            return []
        loads = [full]
        singles = [c for c in range(3) if full[c] > 0]
        if len(singles) > 1:
            singles.sort(key=lambda c: (pl.deadline(fid, frozenset([c])) or -1, c))
            loads += [tuple(full[k] if k == c else 0 for k in range(3)) for c in singles]
        return loads

    def _key(self, dsp: Dispatcher, tr: Trip) -> tuple:
        if self.rule == "earliest":
            return (tr.depart, tr.end, tr.vehicle)
        return ((tr.end - dsp.vs[tr.vehicle].t) / sum(tr.counts), tr.depart, tr.end, tr.vehicle)

    def _best(self, dsp: Dispatcher, pl: PlannerLogic, fid: str) -> Trip | None:
        best, best_key = None, None
        for vs in dsp.vs.values():
            for load in self._loads(dsp, pl, vs, fid):
                tr = self._trip(dsp, pl, vs, fid, load)
                if tr is not None:
                    if best is None or self._key(dsp, tr) < best_key:
                        best, best_key = tr, self._key(dsp, tr)
                    break
        return best

    # ------------------------------------------------------------------ solve
    def solve(self, instance, scenario_set, *, budget_s, seed, deadline) -> MethodResult:
        rh = Reach(instance, scenario_set)
        stop_at = deadline - 0.05 * budget_s
        routes: dict = {}
        bookings: list[Booking] = []
        stopped = False
        deadlines = {}
        for f in instance.facilities:                 # 1-2. every facility planned alone
            alone = Dispatcher(instance, rh)
            alone._routes = routes
            pl = PlannerLogic(alone, **self.kw)
            for c in range(3):
                if f.residents.vector()[c]:
                    deadlines[f"{f.id}/{c}"] = pl.deadline(f.id, frozenset([c]))
            while any(alone.left[f.id]):
                if time.monotonic() > stop_at:
                    stopped = True
                    break
                tr = self._best(alone, pl, f.id)
                if tr is None:
                    break
                alone.commit(tr)
                bookings.append(Booking(tr.vehicle, f.id, tr.counts, tr.boarding.start))
        real = Dispatcher(instance, rh)               # 3. shared fleet, first come first served
        real._routes = routes
        pl = PlannerLogic(real, **self.kw)
        dropped = []
        for bk in sorted(bookings, key=lambda b: (b.request_s, b.facility, b.vehicle)):
            if time.monotonic() > stop_at:
                stopped = True
                dropped.append(bk)
                continue
            tr = self._trip(real, pl, real.vs[bk.vehicle], bk.facility, bk.counts)
            if tr is None:
                dropped.append(bk)
                continue
            real.commit(tr)
        info = {"planner_deadlines": deadlines, "bookings": len(bookings), "dropped_bookings": len(dropped),
                "dropped_residents": sum(sum(b.counts) for b in dropped), "stopped_at_budget": stopped}
        if self.do_repair and time.monotonic() < stop_at:
            info["repair"] = real.repair(Oracle(instance, scenario_set), deadline=stop_at)
        sol = real.solution(self.name, {"seed": int(seed),
                                        "note": "B0 every facility planned alone, planner logic (SYNTHETIC instances)"})
        return MethodResult(sol, info=info)
