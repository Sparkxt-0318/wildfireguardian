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
  time and within its shift). The oracle declares every state (:meth:`evacplan.oracle.Oracle.class_deadline`).
"""
from __future__ import annotations

import math

from .oracle import (
    NO_ROUTE, NO_SHELTER_CAPACITY, NO_VEHICLE_IN_TIME, NO_VEHICLE_SPACE, ClassDeadline, Oracle, State,
)
from .reach import POS_INF, Reach, one_resident
from .schema import CLASSES, ClassCounts, Instance, Unload, Wait

MAX_PROBES = 6


def _claim(reach: Reach, inst: Instance, f, c: int, ld_neg, ea_neg: dict) -> tuple[str | None, str]:
    """A reason why no plan can deliver class ``c`` of facility ``f`` (or ``None``)."""
    if all(s.capacity.vector()[c] == 0 for s in inst.shelters):
        return NO_SHELTER_CAPACITY, f"no shelter accepts {CLASSES[c]} residents"
    if all(v.capacity()[c] == 0 for v in inst.vehicles):
        return NO_VEHICLE_SPACE, f"no vehicle has room for {CLASSES[c]} residents"
    fn = reach.node(f.node)
    b = int(f.boarding_s.vector()[c])
    rel = int(math.ceil(f.release_s - 1e-6))
    ldn = int(ld_neg[fn])
    if ldn < rel + b:
        return NO_ROUTE, (f"certain-contact relaxation: the latest departure that can still reach an open shelter by "
                          f"the horizon is {'never' if ldn < -1e12 else ldn}, before release + one boarding = {rel + b}")
    targets = reach.class_targets(c)
    lb = min((int(reach.lower_bound_to(tg.node)[fn]) + tg.unload_s for tg in targets), default=POS_INF)
    late = []
    for v in inst.vehicles:
        if v.capacity()[c] == 0:
            continue
        a = int(ea_neg[v.id][fn])
        if a >= POS_INF:
            late.append(f"{v.id}: cannot reach the facility by the horizon")
            continue
        d = max(a, rel) + b
        if d > ldn:
            late.append(f"{v.id}: earliest departure {d} > {ldn}")
            continue
        if v.shift_limit_s is not None and d + lb > v.start_s + v.shift_limit_s + 1e-6:
            late.append(f"{v.id}: cannot finish within its shift (ends {v.start_s + v.shift_limit_s:g})")
            continue
        return None, ""
    return NO_VEHICLE_IN_TIME, "certain-contact relaxation: " + "; ".join(late)


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
    out: list[ClassDeadline] = []
    for f in instance.facilities:
        fn = reach.node(f.node)
        for c in present:
            if f.residents.vector()[c] == 0:
                continue
            claim, detail = _claim(reach, instance, f, c, ld_neg[c], ea_neg)
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


__all__ = ["MAX_PROBES", "class_deadlines", "facility_summary"]
