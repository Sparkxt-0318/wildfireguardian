"""Per-facility deadlines and unservable residents (Problem v0 output, per facility and class).

For every facility and mobility class with residents:

* ``leave_by_s``: the latest time the last vehicle can leave the facility with a resident of the
  class: the latest departure on the 1 s lattice from which the RELAXED backward sweep
  (:meth:`evacplan.reach.Reach.sweep`, all K members) finds a turn-respecting route to an open
  shelter that accepts the class, after the facility's release and one boarding;
* ``arrive_by_s`` = ``leave_by_s`` - the boarding time of one resident: the latest time the first
  vehicle can arrive and still serve someone of the class;
* both confirmed by the oracle: a probe vehicle boards one resident from ``arrive_by_s``, leaves at
  ``leave_by_s`` on the sweep's witness route and unloads; only if the oracle checks that trip is
  the deadline ``checked`` (otherwise earlier departures are tried, then ``unresolved``);
* residents that no plan can serve: scoped ``model_no_route`` (``UNSERVABLE:<reason>``), from
  resource facts (no shelter or vehicle space for the class) or from the certain-contact relaxation
  (no route from the facility after release, or no vehicle that can reach it, board and leave in
  time and within its shift). A relaxation refusal is attributed to the weakest level of the
  relaxation that still refuses: ``contact`` (certain contact blocks, every leg by the horizon) gives
  ``NO_ROUTE`` / ``NO_VEHICLE_IN_TIME`` blamed on the fire; ``horizon`` (no fire at all, every leg by the
  horizon) gives ``NO_TRIP_BY_HORIZON``, a refusal scoped to the horizon with no fire involved; ``free``
  (no fire, no horizon: graph, windows, release and shifts alone) gives ``NO_ROUTE`` /
  ``NO_VEHICLE_IN_TIME`` blamed on neither. The oracle declares every state
  (:meth:`evacplan.oracle.Oracle.class_deadline`).
"""
from __future__ import annotations

import math

from .oracle import (
    NO_ROUTE, NO_SHELTER_CAPACITY, NO_TRIP_BY_HORIZON, NO_VEHICLE_IN_TIME, NO_VEHICLE_SPACE, ClassDeadline, Oracle,
    State,
)
from .reach import POS_INF, Reach, one_resident
from .schema import CLASSES, ClassCounts, Instance, Unload, Wait

MAX_PROBES = 6
LEVELS = ("contact", "horizon", "free")      # what the NEGATIVE relaxation keeps: certain contact and the horizon;
                                             # the horizon only (no fire); neither


class _Relax:
    """The NEGATIVE relaxation of :mod:`evacplan.reach` at the three :data:`LEVELS`, computed on demand
    and cached: latest departures per class and earliest arrivals per vehicle."""

    def __init__(self, reach: Reach, ld_neg: dict, ea_neg: dict):
        self.reach = reach
        self._ld = {("contact", c): v for c, v in ld_neg.items()}
        self._ea = {("contact", vid): v for vid, v in ea_neg.items()}

    def ld(self, level: str, c: int):
        key = (level, c)
        if key not in self._ld:
            self._ld[key] = self.reach.latest_arrival_neg(self.reach.class_targets(c), contact=False,
                                                          horizon=level == "horizon")
        return self._ld[key]

    def ea(self, level: str, v):
        key = (level, v.id)
        if key not in self._ea:
            self._ea[key] = self.reach.earliest_arrival_neg(self.reach.node(v.depot), int(v.start_s), contact=False,
                                                            horizon=level == "horizon")
        return self._ea[key]


def _refusal(rx: _Relax, inst: Instance, f, c: int, level: str) -> tuple[str, str] | None:
    """Why no trip delivers one resident of class ``c`` of facility ``f`` in the relaxation at ``level``:
    ``("route", why)`` (no departure after release + one boarding reaches an open shelter that accepts the
    class), ``("vehicle", why)`` (no vehicle with room can reach the facility, board and leave in time, or
    finish one trip within its shift), or ``None`` (the relaxation does not refuse)."""
    reach = rx.reach
    fn = reach.node(f.node)
    b = int(f.boarding_s.vector()[c])
    rel = int(math.ceil(f.release_s - 1e-6))
    ld = int(rx.ld(level, c)[fn])
    by = "inside an opening window" if level == "free" else "by the horizon"
    if ld < rel + b:
        return "route", (f"the latest departure that can still reach an open shelter {by} is "
                         f"{'never' if ld < -1e12 else ld}, before release + one boarding = {rel + b}")
    targets = reach.class_targets(c)
    lb = min((int(reach.lower_bound_to(tg.node)[fn]) + tg.unload_s for tg in targets), default=POS_INF)
    late = []
    for v in inst.vehicles:
        if v.capacity()[c] == 0:
            continue
        a = int(rx.ea(level, v)[fn])
        if a >= POS_INF:
            late.append(f"{v.id}: cannot reach the facility" + ("" if level == "free" else " by the horizon"))
            continue
        d = max(a, rel) + b
        if d > ld:
            late.append(f"{v.id}: earliest departure {d} > {ld}")
            continue
        if v.shift_limit_s is not None and d + lb > v.start_s + v.shift_limit_s + 1e-6:
            late.append(f"{v.id}: cannot finish within its shift (ends {v.start_s + v.shift_limit_s:g})")
            continue
        return None
    return "vehicle", "; ".join(late)


def _claim(rx: _Relax, inst: Instance, f, c: int) -> tuple[str | None, str]:
    """A reason why no plan can deliver class ``c`` of facility ``f`` (or ``None``), attributed to the
    weakest relaxation level that still refuses (module docstring)."""
    if all(s.capacity.vector()[c] == 0 for s in inst.shelters):
        return NO_SHELTER_CAPACITY, f"no shelter accepts {CLASSES[c]} residents"
    if all(v.capacity()[c] == 0 for v in inst.vehicles):
        return NO_VEHICLE_SPACE, f"no vehicle has room for {CLASSES[c]} residents"
    hit = _refusal(rx, inst, f, c, "contact")
    if hit is None:
        return None, ""
    no_fire = _refusal(rx, inst, f, c, "horizon")
    if no_fire is None:                                   # the refusal needs the fire
        kind, why = hit
        return (NO_ROUTE if kind == "route" else NO_VEHICLE_IN_TIME), f"certain-contact relaxation: {why}"
    free = _refusal(rx, inst, f, c, "free")
    if free is None:                                      # only the horizon refuses
        return NO_TRIP_BY_HORIZON, (
            f"horizon only, no fire involved: even with nothing burning, no trip delivers one {CLASSES[c]} resident "
            f"by the hazard horizon (instance time {rx.reach.H:g} s): {no_fire[1]}")
    kind, why = free
    return (NO_ROUTE if kind == "route" else NO_VEHICLE_IN_TIME), f"no fire and no horizon involved: {why}"


def class_deadlines(instance: Instance, scenario_set, *, oracle: Oracle | None = None, reach: Reach | None = None,
                    max_probes: int = MAX_PROBES) -> list[ClassDeadline]:
    """Deadlines and servability of every (facility, class) with residents, declared by the oracle."""
    oracle = oracle or Oracle(instance, scenario_set)
    reach = reach or Reach(instance, scenario_set, index=oracle.index)
    present = sorted({c for f in instance.facilities for c in range(3) if f.residents.vector()[c] > 0})
    if not present:
        return []
    cpos = {c: i for i, c in enumerate(present)}
    targets = {c: reach.class_targets(c) for c in present}
    sweep = reach.sweep([targets[c] for c in present], [reach.node(f.node) for f in instance.facilities])
    ld_neg = {c: reach.latest_arrival_neg(targets[c]) for c in present}
    ea_neg = {v.id: reach.earliest_arrival_neg(reach.node(v.depot), int(v.start_s)) for v in instance.vehicles}
    rx = _Relax(reach, ld_neg, ea_neg)
    out: list[ClassDeadline] = []
    for f in instance.facilities:
        fn = reach.node(f.node)
        for c in present:
            if f.residents.vector()[c] == 0:
                continue
            claim, detail = _claim(rx, instance, f, c)
            b = int(f.boarding_s.vector()[c])
            rel = int(math.ceil(f.release_s - 1e-6))
            kw: dict = {}
            if claim not in (NO_SHELTER_CAPACITY, NO_VEHICLE_SPACE):
                t = sweep.latest_departure(cpos[c], fn, not_before=rel + b, board_s=b)
                step = 1
                for _ in range(max_probes):
                    if t is None:
                        break
                    route, tg, unload_at = sweep.witness(cpos[c], fn, t)
                    acts = reach.actions(route, fn)
                    if unload_at > route.arrival:
                        acts.append(Wait(node=reach.node_ids[tg.node], duration_s=float(unload_at - route.arrival)))
                    acts.append(Unload(shelter=tg.shelter, counts=ClassCounts.of(one_resident(c))))
                    res = oracle.probe_trip(f.id, c, t - b, acts)
                    kw = dict(probe=res, board_start_s=t - b, leave_s=t, shelter=tg.shelter,
                              route=[reach.edge_ids[e] for e, _ in route.steps])
                    if res.state is State.CHECKED:
                        break
                    t = sweep.latest_departure(cpos[c], fn, not_before=rel + b, board_s=b, before=t - step)
                    step *= 2
                if not kw:
                    kw = dict(note="NO_ROUTE_IN_SWEEP")
            out.append(oracle.class_deadline(f.id, c, claim=claim, detail=detail, **kw))
    return out


def facility_summary(deadlines: list[ClassDeadline]) -> dict[str, dict]:
    """Per facility: the latest time the first vehicle must arrive (to serve every class it still can:
    the earliest class ``arrive_by_s``), the latest time the last vehicle can leave (the latest class
    ``leave_by_s``) and the residents certainly unservable."""
    out: dict[str, dict] = {}
    for d in deadlines:
        s = out.setdefault(d.facility, {"arrive_by_s": None, "leave_by_s": None, "unservable": 0, "residents": 0,
                                        "states": {}})
        s["residents"] += d.residents
        s["unservable"] += d.unservable
        s["states"][d.mobility_class] = d.state.value
        if d.arrive_by_s is not None:
            s["arrive_by_s"] = d.arrive_by_s if s["arrive_by_s"] is None else min(s["arrive_by_s"], d.arrive_by_s)
        if d.leave_by_s is not None:
            s["leave_by_s"] = d.leave_by_s if s["leave_by_s"] is None else max(s["leave_by_s"], d.leave_by_s)
    return out


__all__ = ["LEVELS", "MAX_PROBES", "class_deadlines", "facility_summary"]
