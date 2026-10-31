"""THE feasibility oracle of evacplan (program rule 3).

This module is the only code that may declare a final state for a vehicle itinerary or a plan:
``checked``, ``model_no_route`` (model-infeasible, scoped to the hazard model, its K members and
its horizon) or ``unresolved`` (never safe, never delivered). The validator feeds it; the RELAXED
contact check at the end of this file only prunes searches and never yields a final state.

Semantics (reused from the single-vehicle router and its whole-journey checker; see
``docs/ASSUMPTIONS.md``)
----------------------------------------------------------------------------------------------
* Occupancies (legs): driving an edge is uniform motion along the edge geometry over the closed
  interval [depart, arrive], queried with ``ScenarioSet.query_uniform``; idling, waiting, boarding
  and unloading are the node as a stationary point over its closed interval (``ScenarioSet.query``).
  Hazard time = instance time + ``hazard.t0_offset_s``.
* Per leg and member (hazard_contract ``SegmentHazard``): ``contact`` True -> certain violation
  (model_no_route, FLAME_CONTACT); ``flux_lower`` > peak budget -> certain violation
  (PEAK_ABOVE_BUDGET); ``supported`` False or ``contact`` None (unknown cells, the grid's outside,
  time past the horizon) -> unresolved; ``flux_upper`` > peak budget -> unresolved
  (PEAK_UNRESOLVED); otherwise the leg passes in that member.
* Dose per member, cumulative over the vehicle's whole itinerary from its start (conservative for
  occupants): sum of ``dose_lower`` > budget -> model_no_route (DOSE_ABOVE_BUDGET); sum of
  ``dose_upper`` > budget -> unresolved (DOSE_UNRESOLVED).
* Validator issues -> model_no_route (``RESOURCE:<code>``) from the start of the offending action.
* A vehicle's state never improves along its itinerary: the state after a leg is the worst of
  everything so far (model_no_route < unresolved < checked); its ``cause`` is the first reason
  that brought it to that level.
* A trip ends with an unloading. Its residents are delivered iff the state at the end of that
  unloading is checked, i.e. every occupancy of the vehicle from its start through that unloading
  is checked in ALL K members. Residents still on board at the end count as model_no_route.
* Safety slack of a checked leg: the largest uniform delay that keeps it contact-free in all
  members (exact, from the cells' burning intervals), capped at the hazard horizon.
"""
from __future__ import annotations

import math
from collections import Counter, OrderedDict, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict

import hazard_contract as hc
from hazard_contract.geometry import as_polyline, is_stationary, polyline_cells
from hazard_contract.scenario import uniform_pieces

from .schema import ClassCounts, Instance, InstanceIndex, Itinerary, Solution
from .validate import Issue, Schedule, Segment, simulate, validate_solution

ORACLE_VERSION = "evacplan.oracle/0"

FLAME_CONTACT = "FLAME_CONTACT"
PEAK_ABOVE_BUDGET = "PEAK_ABOVE_BUDGET"
DOSE_ABOVE_BUDGET = "DOSE_ABOVE_BUDGET"
UNSUPPORTED_HAZARD = "UNSUPPORTED_HAZARD"
OUTSIDE_HAZARD_GRID = "OUTSIDE_HAZARD_GRID"
BEYOND_HORIZON = "BEYOND_HORIZON"
PEAK_UNRESOLVED = "PEAK_UNRESOLVED"
DOSE_UNRESOLVED = "DOSE_UNRESOLVED"
RESOURCE_PREFIX = "RESOURCE:"

SCOPE_RULES = (
    "contact: closed hazard cells (whole-road rule), uniform motion along each edge, stationary point at "
    "nodes for idle/wait/board/unload; peak and dose: hazard_contract bounds per member, dose cumulative per "
    "vehicle from its start; unsupported data or time past the horizon => unresolved. model_no_route is scoped "
    "to this hazard model, its K members and its horizon: it is not proof that no real-world plan exists. "
    "unresolved is never safe and never delivered.")


class State(str, Enum):
    CHECKED = "checked"
    MODEL_NO_ROUTE = "model_no_route"
    UNRESOLVED = "unresolved"


_RANK = {State.MODEL_NO_ROUTE: 0, State.UNRESOLVED: 1, State.CHECKED: 2}


def state_rank(s: State) -> int:
    """Order of states, worst first: model_no_route 0 < unresolved 1 < checked 2."""
    return _RANK[State(s)]


def _worsen(state: State, cause: str | None, new: State, new_cause: str | None) -> tuple[State, str | None]:
    if _RANK[new] < _RANK[state]:
        return new, new_cause
    return state, cause


class OracleInputError(ValueError):
    """The instance and the scenario set (or the solution) do not belong together."""


# ------------------------------------------------------------------------------------ results
class _Result(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", ser_json_inf_nan="strings")


class MemberHazard(_Result):
    contact: bool | None
    supported: bool
    flux_lower: float
    flux_upper: float
    dose_lower: float
    dose_upper: float


class LegResult(_Result):
    index: int
    action: int
    kind: Literal["idle", "drive", "wait", "board", "unload"]
    t_start: float
    t_end: float
    node: str | None
    edge: str | None
    hazard_state: State | None          # this leg alone (contact, peak, support); None if not evaluated
    reasons: list[str]                  # this leg's hazard reasons, then the cumulative dose reason if any
    dose_state: State | None            # cumulative dose through this leg
    state: State                        # the vehicle's state after this leg
    cause: str | None
    slack_s: float | None               # checked legs only
    members: list[MemberHazard] | None
    cum_dose_lower: list[float] | None
    cum_dose_upper: list[float] | None


class ActionResult(_Result):
    index: int
    kind: str
    t_start: float | None
    t_end: float | None
    issues: list[str]
    state: State                        # the vehicle's state at the end of this action
    cause: str | None


class TripResult(_Result):
    action: int                         # the unloading that ends the trip
    shelter: str
    t_end: float | None
    counts: ClassCounts
    by_facility: dict[str, ClassCounts]
    state: State
    cause: str | None


class IssueOut(_Result):
    code: str
    message: str
    vehicle: str | None
    itinerary: int | None
    action: int | None


class ItineraryResult(_Result):
    vehicle: str
    itinerary: int
    state: State                        # after the whole itinerary
    cause: str | None
    legs: list[LegResult]
    actions: list[ActionResult]
    trips: list[TripResult]
    delivered: ClassCounts
    onboard_end: ClassCounts            # never unloaded: model_no_route
    start_s: float | None
    end_s: float | None
    vehicle_time_s: float | None
    min_slack_s: float | None           # over the legs up to its last delivered trip
    issues: list[IssueOut]


class Scope(_Result):
    oracle: str
    hazard_contract_version: str
    model_version: str
    source: str
    synthetic: bool
    K: int
    issue_time_utc: str
    t0_offset_s: float
    horizon_hazard_s: float
    horizon_instance_s: float
    peak_budget_kw_m2: list[float]
    dose_budget_kj_m2: list[float]
    flux_model: str
    rules: str


class PlanResult(_Result):
    instance: str
    method: str
    synthetic: bool
    label: str                          # "SYNTHETIC" when any synthetic data went in
    scope: Scope
    vehicles: list[ItineraryResult]
    residents_total: int
    delivered: ClassCounts
    delivered_total: int
    delivered_by_facility: dict[str, ClassCounts]
    unresolved_total: int
    unresolved_by_reason: dict[str, int]
    model_no_route_total: int
    model_no_route_by_reason: dict[str, int]
    not_planned: dict[str, ClassCounts]  # residents no itinerary boards (not a verdict: no plan claim)
    not_planned_total: int
    min_slack_s: float | None
    vehicle_time_s: float
    makespan_s: float | None
    issues: list[IssueOut]

    def summary(self) -> dict:
        return {
            "instance": self.instance, "method": self.method, "label": self.label,
            "delivered": self.delivered_total, "unresolved": self.unresolved_total,
            "model_no_route": self.model_no_route_total, "not_planned": self.not_planned_total,
            "residents": self.residents_total, "min_slack_s": self.min_slack_s,
            "vehicle_time_s": self.vehicle_time_s, "makespan_s": self.makespan_s,
        }


# ------------------------------------------------------------------------- contact records
def _point_cells(grid: hc.Grid, xy) -> tuple[np.ndarray, np.ndarray]:
    r, c, _ = polyline_cells(grid, np.asarray(xy, dtype=float).reshape(1, 2))
    return r, c


def contact_records(grid: hc.Grid, geom_xy, t_in: float, t_out: float):
    """Closed cells an occupancy touches, with the closed hazard-time interval of each touch.

    The same rule hazard_contract applies for ``contact``: ``query_uniform`` for a moving polyline
    (each piece between grid lines over its sub-interval, each cut point at its instant) and
    ``query`` for a stationary point or a zero-duration occupancy (every touched cell over the
    whole interval). Returns ``(rows, cols, t0, t1, touches_outside)``.
    """
    g = as_polyline(geom_xy)
    a, b = float(t_in), float(t_out)
    if is_stationary(g) or b == a:
        rows, cols, outside = polyline_cells(grid, g)
        return rows, cols, np.full(rows.size, a), np.full(rows.size, b), outside
    outside = polyline_cells(grid, g)[2]
    pieces = uniform_pieces(grid, g, a, b)
    rr, cc, t0, t1 = [], [], [], []

    def add(xy, ta: float, tb: float) -> None:
        r, c = _point_cells(grid, xy)
        rr.append(r)
        cc.append(c)
        t0.append(np.full(r.size, ta))
        t1.append(np.full(r.size, tb))

    for pg, ta, tb in pieces:
        add(0.5 * (pg[0] + pg[1]), ta, tb)
        add(pg[0], ta, ta)
    add(pieces[-1][0][1], pieces[-1][2], pieces[-1][2])
    return (np.concatenate(rr), np.concatenate(cc), np.concatenate(t0), np.concatenate(t1), outside)


def _cell_arrays(ss: hc.ScenarioSet, rows: np.ndarray, cols: np.ndarray):
    return ss.ignite_s[:, rows, cols], ss.extinguish_s[:, rows, cols], ss.supported[:, rows, cols]


# ----------------------------------------------------------------------------------- oracle
class Oracle:
    """The feasibility oracle for one instance and one scenario set (reusable; caches queries)."""

    def __init__(self, instance: Instance, scenario_set: hc.ScenarioSet, *, evaluate_after_failure: bool = False,
                 cache_size: int = 100_000):
        meta = scenario_set.meta
        if instance.graph.crs_epsg != meta.crs_epsg:
            raise OracleInputError(f"graph CRS EPSG:{instance.graph.crs_epsg} != hazard CRS EPSG:{meta.crs_epsg}")
        self.instance = instance
        self.scenario = scenario_set
        self.index = InstanceIndex(instance)
        self.K = meta.K
        try:
            self.peak, self.dose = instance.hazard.budgets.per_member(self.K)
        except ValueError as exc:
            raise OracleInputError(str(exc)) from exc
        self.offset = float(instance.hazard.t0_offset_s)
        self.horizon = float(meta.horizon_s)
        self.synthetic = bool(instance.synthetic or meta.synthetic)
        self.evaluate_after_failure = evaluate_after_failure
        self._cache: OrderedDict = OrderedDict()
        self._cache_size = int(cache_size)
        self.scope = Scope(
            oracle=ORACLE_VERSION, hazard_contract_version=meta.contract_version, model_version=meta.model_version,
            source=meta.source, synthetic=self.synthetic, K=self.K,
            issue_time_utc=meta.issue_time_utc.isoformat().replace("+00:00", "Z"), t0_offset_s=self.offset,
            horizon_hazard_s=self.horizon, horizon_instance_s=self.horizon - self.offset,
            peak_budget_kw_m2=self.peak.tolist(), dose_budget_kj_m2=self.dose.tolist(),
            flux_model=meta.heat_source.flux_model, rules=SCOPE_RULES,
        )

    # ----------------------------------------------------------------------- one leg
    def _geometry(self, seg: Segment) -> np.ndarray:
        return self.index.edge_geometry(seg.edge) if seg.edge is not None else self.index.node_xy(seg.node)

    def _hazard(self, seg: Segment) -> tuple[list[hc.SegmentHazard], float, float, np.ndarray]:
        a, b = seg.t0 + self.offset, seg.t1 + self.offset
        geom = self._geometry(seg)
        key = ("e", seg.edge, a, b) if seg.edge is not None else ("n", seg.node, a, b)
        hz = self._cache.get(key)
        if hz is None:
            if seg.edge is not None:
                hz = self.scenario.query_uniform(geom, a, b)
            else:
                hz = self.scenario.query(geom, a, b)
            self._cache[key] = hz
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        else:
            self._cache.move_to_end(key)
        return hz, a, b, geom

    def _support_reasons(self, geom: np.ndarray, b: float, k: int) -> list[str]:
        rows, cols, outside = polyline_cells(self.scenario.grid, geom)
        out = []
        if b > self.horizon:
            out.append(BEYOND_HORIZON)
        if outside:
            out.append(OUTSIDE_HAZARD_GRID)
        if rows.size and not bool(np.all(self.scenario.supported[k, rows, cols])):
            out.append(UNSUPPORTED_HAZARD)
        return out or [UNSUPPORTED_HAZARD]

    def _classify(self, hz: list[hc.SegmentHazard], b: float, geom: np.ndarray) -> tuple[State, list[str]]:
        mnr: list[str] = []
        unr: list[str] = []
        for k, h in enumerate(hz):
            if h.contact is True:
                mnr.append(FLAME_CONTACT)
            if h.flux_lower > self.peak[k]:
                mnr.append(PEAK_ABOVE_BUDGET)
            if not h.supported or h.contact is None:
                unr.extend(self._support_reasons(geom, b, k))
            elif h.flux_upper > self.peak[k]:
                unr.append(PEAK_UNRESOLVED)
        mnr, unr = list(dict.fromkeys(mnr)), list(dict.fromkeys(unr))
        if mnr:
            return State.MODEL_NO_ROUTE, mnr + unr
        if unr:
            return State.UNRESOLVED, unr
        return State.CHECKED, []

    def leg_slack(self, geom: np.ndarray, a: float, b: float) -> float:
        """Largest uniform delay keeping a contact-free occupancy [a, b] (hazard time) contact-free in
        every member, capped at the horizon: min over touched cells of (ignition - last touch)."""
        rows, cols, t0, t1, _ = contact_records(self.scenario.grid, geom, a, b)
        ig, ex, sup = _cell_arrays(self.scenario, rows, cols)
        burns = sup & (ex > ig)
        if np.any(burns & (ig <= t1) & (ex > t0)):
            raise AssertionError("contact records disagree with hazard_contract's contact (interface drift)")
        future = burns & (ig > t1)
        s = float(np.min((ig - t1)[future])) if future.any() else math.inf
        return min(s, self.horizon - b)

    # ---------------------------------------------------------------- one itinerary
    def _evaluate(self, sch: Schedule, itinerary: Itinerary) -> ItineraryResult:
        K = self.K
        issues_at: dict[int, list[Issue]] = defaultdict(list)
        for iss in sorted(sch.issues, key=lambda i: (i.action, i.code)):
            issues_at[iss.action].append(iss)
        segs_at: dict[int, list[Segment]] = defaultdict(list)
        for seg in sch.segments:
            segs_at[seg.action].append(seg)
        state, cause = State.CHECKED, None
        lo, hi = np.zeros(K), np.zeros(K)
        legs: list[LegResult] = []
        actions: list[ActionResult] = []
        at_end: dict[int, tuple[State, str | None]] = {}
        for j, act in enumerate(itinerary.actions):
            codes = [i.code for i in issues_at.get(j, [])]
            if codes:
                state, cause = _worsen(state, cause, State.MODEL_NO_ROUTE, RESOURCE_PREFIX + codes[0])
            for seg in segs_at.get(j, []):
                common = dict(index=len(legs), action=j, kind=seg.kind, t_start=seg.t0, t_end=seg.t1,
                              node=seg.node, edge=seg.edge)
                if state is State.MODEL_NO_ROUTE and not self.evaluate_after_failure:
                    legs.append(LegResult(**common, hazard_state=None, reasons=[], dose_state=None,
                                          state=state, cause=cause, slack_s=None, members=None,
                                          cum_dose_lower=None, cum_dose_upper=None))
                    continue
                hz, a, b, geom = self._hazard(seg)
                h_state, reasons = self._classify(hz, b, geom)
                lo = lo + np.array([h.dose_lower for h in hz])
                hi = hi + np.array([h.dose_upper for h in hz])
                if np.any(lo > self.dose):
                    d_state, d_reason = State.MODEL_NO_ROUTE, DOSE_ABOVE_BUDGET
                elif np.any(hi > self.dose):
                    d_state, d_reason = State.UNRESOLVED, DOSE_UNRESOLVED
                else:
                    d_state, d_reason = State.CHECKED, None
                state, cause = _worsen(state, cause, h_state, reasons[0] if reasons else None)
                state, cause = _worsen(state, cause, d_state, d_reason)
                slack = self.leg_slack(geom, a, b) if h_state is State.CHECKED else None
                legs.append(LegResult(
                    **common, hazard_state=h_state,
                    reasons=reasons + ([d_reason] if d_reason else []), dose_state=d_state,
                    state=state, cause=cause, slack_s=slack,
                    members=[MemberHazard(contact=h.contact, supported=h.supported, flux_lower=h.flux_lower,
                                          flux_upper=h.flux_upper, dose_lower=h.dose_lower,
                                          dose_upper=h.dose_upper) for h in hz],
                    cum_dose_lower=lo.tolist(), cum_dose_upper=hi.tolist()))
            span = sch.spans[j] if j < len(sch.spans) else None
            actions.append(ActionResult(index=j, kind=act.kind, t_start=span[0] if span else None,
                                        t_end=span[1] if span else None, issues=codes, state=state, cause=cause))
            at_end[j] = (state, cause)
        end_codes = [i.code for i in issues_at.get(len(itinerary.actions), [])]
        if end_codes:
            state, cause = _worsen(state, cause, State.MODEL_NO_ROUTE, RESOURCE_PREFIX + end_codes[0])

        trips: list[TripResult] = []
        delivered = [0, 0, 0]
        last_delivered = -1
        for rec in sch.unloads:
            st, ca = at_end[rec.action]
            trips.append(TripResult(action=rec.action, shelter=rec.shelter, t_end=rec.t1,
                                    counts=ClassCounts.of(rec.counts),
                                    by_facility={k: ClassCounts.of(v) for k, v in rec.by_facility.items()},
                                    state=st, cause=ca))
            if st is State.CHECKED:
                delivered = [delivered[c] + rec.counts[c] for c in range(3)]
                last_delivered = max(last_delivered, rec.action)
        onboard = [sum(v[c] for v in sch.onboard_end.values()) for c in range(3)]
        if any(onboard) and state is not State.MODEL_NO_ROUTE:  # pragma: no cover - NOT_UNLOADED guarantees it
            raise AssertionError("residents left on board must make the itinerary model_no_route")
        prefix = [lg.slack_s for lg in legs if lg.action <= last_delivered]
        if any(s is None for s in prefix):  # pragma: no cover - invariant
            raise AssertionError("a delivered trip includes a leg that is not checked")
        start, end = sch.start_s, sch.clock_end
        return ItineraryResult(
            vehicle=sch.vehicle, itinerary=sch.itinerary, state=state, cause=cause, legs=legs, actions=actions,
            trips=trips, delivered=ClassCounts.of(delivered), onboard_end=ClassCounts.of(onboard),
            start_s=start, end_s=end,
            vehicle_time_s=(end - start) if (start is not None and end is not None) else None,
            min_slack_s=min(prefix) if prefix else None,
            issues=[IssueOut(code=i.code, message=i.message, vehicle=i.vehicle, itinerary=i.itinerary,
                             action=i.action) for i in sorted(sch.issues, key=lambda i: (i.action, i.code))],
        )

    # ------------------------------------------------------------------------ plan
    def check_plan(self, solution: Solution) -> PlanResult:
        inst = self.instance
        if solution.instance and solution.instance != inst.name:
            raise OracleInputError(f"the solution is for instance {solution.instance!r}, not {inst.name!r}")
        report = validate_solution(inst, solution, self.index)
        vehicles = [self._evaluate(sch, it) for sch, it in zip(report.schedules, solution.itineraries)]
        delivered = [0, 0, 0]
        by_fac: dict[str, list[int]] = {}
        unresolved: Counter = Counter()
        no_route: Counter = Counter()
        for v in vehicles:
            for t in v.trips:
                if t.state is State.CHECKED:
                    delivered = [delivered[c] + t.counts.vector()[c] for c in range(3)]
                    for fid, cc in t.by_facility.items():
                        acc = by_fac.setdefault(fid, [0, 0, 0])
                        for c in range(3):
                            acc[c] += cc.vector()[c]
                elif t.counts.total:
                    (unresolved if t.state is State.UNRESOLVED else no_route)[t.cause] += t.counts.total
            if v.onboard_end.total:
                no_route[v.cause] += v.onboard_end.total
        boarded: dict[str, list[int]] = {}
        for sch in report.schedules:
            for fid, cnt in sch.boarded.items():
                acc = boarded.setdefault(fid, [0, 0, 0])
                for c in range(3):
                    acc[c] += cnt[c]
        not_planned = {}
        for f in inst.facilities:
            got = boarded.get(f.id, [0, 0, 0])
            rest = [max(0, f.residents.vector()[c] - got[c]) for c in range(3)]
            if any(rest):
                not_planned[f.id] = ClassCounts.of(rest)
        slacks = [v.min_slack_s for v in vehicles if v.min_slack_s is not None]
        ends = [v.end_s for v, it in zip(vehicles, solution.itineraries) if it.actions and v.end_s is not None]
        return PlanResult(
            instance=inst.name, method=solution.method, synthetic=self.synthetic,
            label="SYNTHETIC" if self.synthetic else "", scope=self.scope, vehicles=vehicles,
            residents_total=inst.residents_total, delivered=ClassCounts.of(delivered), delivered_total=sum(delivered),
            delivered_by_facility={k: ClassCounts.of(v) for k, v in sorted(by_fac.items())},
            unresolved_total=sum(unresolved.values()), unresolved_by_reason=dict(sorted(unresolved.items())),
            model_no_route_total=sum(no_route.values()), model_no_route_by_reason=dict(sorted(no_route.items())),
            not_planned=not_planned, not_planned_total=sum(c.total for c in not_planned.values()),
            min_slack_s=min(slacks) if slacks else None,
            vehicle_time_s=float(sum(v.vehicle_time_s for v in vehicles if v.vehicle_time_s is not None)),
            makespan_s=max(ends) if ends else None,
            issues=[IssueOut(code=i.code, message=i.message, vehicle=i.vehicle, itinerary=i.itinerary,
                             action=i.action) for i in report.issues],
        )

    def check_itinerary(self, itinerary: Itinerary) -> ItineraryResult:
        """One vehicle in isolation: shared shelter and facility capacities count only this
        itinerary's own use. Final plan answers come from :meth:`check_plan`."""
        return self.check_plan(Solution(instance=self.instance.name, itineraries=[itinerary])).vehicles[0]


def check_plan(instance: Instance, scenario_set: hc.ScenarioSet, solution: Solution) -> PlanResult:
    """Check a whole plan against every member of the scenario set (the final answer)."""
    return Oracle(instance, scenario_set).check_plan(solution)


def check_itinerary(instance: Instance, scenario_set: hc.ScenarioSet, itinerary: Itinerary) -> ItineraryResult:
    """Check one vehicle itinerary in isolation (see :meth:`Oracle.check_itinerary`)."""
    return Oracle(instance, scenario_set).check_itinerary(itinerary)


# ------------------------------------------------------------------------------ RELAXED check
@dataclass(frozen=True)
class RelaxedLeg:
    """RELAXED outcome of one occupancy. Not a final state.

    blocked: flame contact is certain in at least one member (the oracle will not accept the leg).
    uncertain: the occupancy touches unknown hazard data or the grid's outside, or passes the horizon.
    Neither flag means only that contact cannot rule the leg out: peak, dose and resources may."""

    blocked: bool
    uncertain: bool


@dataclass(frozen=True)
class RelaxedItinerary:
    """RELAXED outcome of an itinerary (stops at the first blocked leg by default). Not a final state."""

    segments: tuple[Segment, ...]
    legs: tuple[RelaxedLeg, ...]
    first_blocked: int | None           # index into segments
    any_uncertain: bool
    issues: tuple[Issue, ...]           # validator issues, listed, not judged


class RelaxedContactCheck:
    """RELAXED check for search loops: contact only, cell level, no flux, no dose, no verdict.

    It is a relaxation of the oracle's contact rule (same occupancies, same closed cells, same
    instants): ``blocked`` implies the oracle rejects the leg; the converse needs the oracle. Use it
    to prune and guide searches; final answers go through :class:`Oracle`.
    """

    def __init__(self, instance: Instance, scenario_set: hc.ScenarioSet, *, index: InstanceIndex | None = None):
        if instance.graph.crs_epsg != scenario_set.meta.crs_epsg:
            raise OracleInputError("graph and hazard CRS differ")
        self.instance = instance
        self.scenario = scenario_set
        self.index = index or InstanceIndex(instance)
        self.offset = float(instance.hazard.t0_offset_s)
        self.horizon = float(scenario_set.meta.horizon_s)

    def _occupancy(self, geom: np.ndarray, t0: float, t1: float) -> RelaxedLeg:
        a, b = t0 + self.offset, t1 + self.offset
        rows, cols, r0, r1, outside = contact_records(self.scenario.grid, geom, a, b)
        ig, ex, sup = _cell_arrays(self.scenario, rows, cols)
        blocked = bool(np.any(sup & (ex > ig) & (ig <= r1) & (ex > r0)))
        uncertain = bool(outside or b > self.horizon or not np.all(sup))
        return RelaxedLeg(blocked=blocked, uncertain=uncertain)

    def segment(self, seg: Segment) -> RelaxedLeg:
        geom = self.index.edge_geometry(seg.edge) if seg.edge is not None else self.index.node_xy(seg.node)
        return self._occupancy(geom, seg.t0, seg.t1)

    def traverse(self, edge_id: str, depart_s: float) -> RelaxedLeg:
        e = self.index.edges[edge_id]
        return self._occupancy(self.index.edge_geometry(edge_id), depart_s, depart_s + e.travel_time_s)

    def stay(self, node_id: str, t0: float, t1: float) -> RelaxedLeg:
        return self._occupancy(self.index.node_xy(node_id), t0, t1)

    def itinerary(self, itinerary: Itinerary, *, stop_at_block: bool = True) -> RelaxedItinerary:
        sch, _, _ = simulate(self.index, itinerary)
        legs: list[RelaxedLeg] = []
        first = None
        for n, seg in enumerate(sch.segments):
            r = self.segment(seg)
            legs.append(r)
            if r.blocked and first is None:
                first = n
                if stop_at_block:
                    break
        return RelaxedItinerary(segments=tuple(sch.segments[:len(legs)]), legs=tuple(legs), first_blocked=first,
                                any_uncertain=any(r.uncertain for r in legs), issues=tuple(sch.issues))
