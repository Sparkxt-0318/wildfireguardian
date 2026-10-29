"""Scoring a routing decision against a truth the router never saw (Contract E records).

Fields: cutoff, truth_source, truth_label, forecast_source, mission, verdict (checked_route | model_no_route |
unresolved), true_contact, true_peak, true_dose, arrival_s, clairvoyant_arrival_s, false_safe, false_refusal, regret_s.

  false_safe     a checked route that meets the true fire (flame contact) or exceeds the true peak or dose limit.
  false_refusal  model_no_route or unresolved while a clairvoyant route existed (the earliest checked journey computed
                 with the truth itself). Unresolved stays its own verdict; false_refusal records it separately with
                 `refusal_kind`.
  regret_s       arrival minus clairvoyant arrival, for checked routes when the clairvoyant route exists.
device_offline: only observed (cell, time) pairs are scored. Known contact = a journey span meets an observed burning
interval. A span over an unknown (cell, time) adds to `unknown_exposure` and never sets or clears false_safe. The
clairvoyant treats unknown as blocked (a journey certifiable from the observations alone); without one, false_refusal
is None (unscorable). Dose and peak are not observed and are None.
"""
from __future__ import annotations

import sys
from fractions import Fraction as F
from pathlib import Path

_MEMBERS_SRC = Path(__file__).resolve().parents[3] / "scenario-members" / "src"
if str(_MEMBERS_SRC) not in sys.path:
    sys.path.insert(0, str(_MEMBERS_SRC))
from wfg_members import coverage as COV  # noqa: E402
from wfg_members import planner as PL  # noqa: E402

from .truth import planning_model  # noqa: E402

CHECKED, NOROUTE, UNRES = "checked_route", "model_no_route", "unresolved"


def evaluate_truth(evaluator, truth, kernels=None, current_flux=None):
    """(true_contact, true_peak kW/m2, true_dose kJ/m2, unknown_exposure) of a fixed journey under the truth."""
    if truth.observed:
        contact, unknown = False, False
        unk = truth.unknown_intervals(evaluator.by_cell.keys())
        for c, spans in evaluator.by_cell.items():
            for a, b in spans:
                if any(a < hi and b >= lo for lo, hi in truth.burning.get(c, ())):
                    contact = True
                if any(a < hi and b >= lo for lo, hi in unk.get(c, ())):
                    unknown = True
        return contact, None, None, unknown
    current = set(truth.current) if truth.R > 0 else set()
    contact = evaluator.contact(truth.births, truth.T, current, truth.R)
    if kernels is None:
        return contact, None, None, False
    dose, peak = evaluator.dose_peak(truth.births, truth.T, truth.R, kernels, current_flux)
    return contact, peak, dose, False


def clairvoyant(graph, request, truth, *, planner, shared_route=None, kernels=None, current_flux=None, evaluator_for=None,
                cells=None):
    """Earliest checked arrival under the truth: {"status": ROUTE|NO_ROUTE|UNRESOLVED, "arrival", "legs", "destination"}.

    Exact shortcut: arrival(present fire only) <= arrival(truth); if the present-fire-only optimal route `shared_route`
    passes under the truth, it is the clairvoyant optimum."""
    def passes(route):
        ev = evaluator_for(route)
        c, peak, dose, unk = evaluate_truth(ev, truth, kernels, current_flux)
        if truth.observed:
            return not c and not unk
        return (not c) and (peak is None or peak <= float(request["budgets"]["peak"])) and (
            dose is None or dose <= float(F(next(iter(request["budgets"]["dose"].values())))))
    if shared_route is not None and not truth.observed:
        if shared_route["status"] == PL.NO_ROUTE:
            return {"status": PL.NO_ROUTE, "arrival": None, "via": "shared_bound"}
        if shared_route["status"] == PL.ROUTE and passes(shared_route):
            return {"status": PL.ROUTE, "arrival": shared_route["arrival"], "legs": shared_route["legs"],
                    "destination": shared_route["destination"], "via": "shared_bound"}
    model = planning_model(truth, unknown_as_burning=True, cells=cells)
    plan = planner(graph, request, model)
    if plan["status"] != PL.ROUTE:
        return {"status": plan["status"], "arrival": None, "via": "planner", "raw": plan["raw_status"]}
    if passes(plan):
        return {"status": PL.ROUTE, "arrival": plan["arrival"], "legs": plan["legs"], "destination": plan["destination"], "via": "planner"}
    return {"status": PL.UNRESOLVED, "arrival": None, "via": "planner_route_fails_dose_or_peak"}


def record(*, cutoff, region, mission, forecast_source, decision, truth, evaluator, clair, kernels=None, current_flux=None,
           request=None, extra=None):
    verdict = decision["verdict"]
    out = {"cutoff": cutoff, "region": region, "mission": mission, "truth_source": truth.source, "truth_label": truth.label,
           "forecast_source": forecast_source, "verdict": verdict, "arrival_s": decision.get("arrival_s"),
           "clairvoyant_arrival_s": clair.get("arrival"), "clairvoyant_status": clair.get("status"),
           "true_contact": None, "true_peak": None, "true_dose": None, "unknown_exposure": None,
           "false_safe": None, "false_refusal": None, "refusal_kind": None, "regret_s": None}
    if verdict == CHECKED:
        c, peak, dose, unk = evaluate_truth(evaluator, truth, kernels, current_flux)
        out.update(true_contact=c, true_peak=peak, true_dose=dose, unknown_exposure=unk)
        over = False
        if request is not None and peak is not None:
            over = peak > float(request["budgets"]["peak"]) or dose > float(F(next(iter(request["budgets"]["dose"].values()))))
        out["false_safe"] = bool(c or over)
        out["false_refusal"] = False
        if clair.get("status") == PL.ROUTE:
            out["regret_s"] = decision["arrival_s"] - clair["arrival"]
    else:
        out["false_safe"] = False
        out["refusal_kind"] = verdict
        if clair.get("status") == PL.ROUTE:
            out["false_refusal"] = True
        elif clair.get("status") == PL.NO_ROUTE and not truth.observed:
            out["false_refusal"] = False
        elif clair.get("status") == PL.NO_ROUTE and truth.observed:
            out["false_refusal"] = None                       # unknown cells may hide a route: unscorable
        else:
            out["false_refusal"] = None
    if extra:
        out.update(extra)
    return out


def journey_evaluator(graph, request, plan, independent):
    from wfg_members import check
    spans = check.journey_spans(graph, request, plan["legs"], plan["destination"])
    nodes = {n["id"]: n for n in graph["nodes"]}
    issue = independent._cell(graph, nodes[request["position"]["node"]])
    return COV.JourneyEvaluator(spans, issue, request["departure"], request)
