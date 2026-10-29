"""Synthetic-truth harness (observing system simulation experiment) around the routing decision procedure.

The router sees only forecast members; it decides once per (forecast source, mission) with the recorded acceptance rule
(wfg_members.decide, SIPP planner by default); the decision is then executed against every truth of the case set and
scored (score.record). The per-member checks of the router and the truth scoring both use the cheap checker
(wfg_members.coverage: exact contact, dose by linear superposition of the inherited radiation operator, conservative by
at most 1e-5 relative), which tests compare with the frozen centre checker.

This package imports track 1C-1 (wfg_members: members, reduction, acceptance, decision procedure, cheap checker) and
track 1C-2 (wfg_sipp: the SIPP planner).
"""
from __future__ import annotations

import sys
from pathlib import Path

_EXP = Path(__file__).resolve().parents[3]
for sub in ("scenario-members/src", "scenario-members", "sipp-routing/src"):
    if str(_EXP / sub) not in sys.path:
        sys.path.insert(0, str(_EXP / sub))
from wfg_members import coverage as COV  # noqa: E402
from wfg_members import decide as D  # noqa: E402
from wfg_members import kit  # noqa: E402
from wfg_sipp.frontend import sipp_plan  # noqa: E402

from . import score as S  # noqa: E402


def cheap_reporter(graph, request, model, *, kernels=None, current_flux=None):
    """Reporter for wfg_members.decide: per-member pass flags from the cheap checker."""
    ind = kit.install()["independent"]
    current = set(model.current) if model.R > 0 else set()

    def report(plan):
        ev = S.journey_evaluator(graph, request, plan, ind)
        out = []
        for k, births in enumerate(model.events):
            ok, info = ev.passes(births, model.T, current, model.R, kernels, current_flux)
            out.append({"id": model.ids[k], "contact": info["contact"], "passed": ok,
                        "peak_ok": info.get("peak_kw_m2", 0) <= float(request["budgets"]["peak"]),
                        "dose_ok": info.get("dose_kj_m2", 0) <= ev.budget_dose, "peak_kw_m2": info.get("peak_kw_m2"),
                        "dose_kj_m2": info.get("dose_kj_m2"), "check_mode": "cheap"})
        return out
    return report


def decide(graph, request, model, *, rule=None, weights=None, kernels=None, current_flux=None, planner=sipp_plan, wall_s=60.0):
    return D.decide(graph, None, request, model, rule=rule, weights=weights, planner=planner, wall_s=wall_s,
                    reporter=cheap_reporter(graph, request, model, kernels=kernels, current_flux=current_flux))


def score_against(graph, request, decision, truths, *, cutoff, region, mission, forecast_source, shared_route, kernels=None,
                  current_flux=None, planner=sipp_plan, clair_cache=None, cells=None, extra=None):
    """Contract E records of one decision against many truths (clairvoyant results cached per truth label)."""
    ind = kit.install()["independent"]
    ev = S.journey_evaluator(graph, request, decision, ind) if decision["verdict"] == D.CHECKED else None
    cache = clair_cache if clair_cache is not None else {}
    eval_cache = {}

    def evaluator_for(route):
        key = id(route)
        if key not in eval_cache:
            eval_cache[key] = S.journey_evaluator(graph, request, route, ind)
        return eval_cache[key]
    out = []
    for t in truths:
        key = (mission, t.source, t.label)
        if key not in cache:
            cache[key] = S.clairvoyant(graph, request, t, planner=planner, shared_route=shared_route, kernels=kernels,
                                       current_flux=current_flux, evaluator_for=evaluator_for, cells=cells)
        out.append(S.record(cutoff=cutoff, region=region, mission=mission, forecast_source=forecast_source, decision=decision,
                            truth=t, evaluator=ev, clair=cache[key], kernels=kernels, current_flux=current_flux, request=request,
                            extra=extra))
    return out


def brier(member_events, weights, truth_births, cells):
    """Brier score of the member ensemble's one-hour burn probability against the truth over `cells` (graph cells)."""
    import numpy as np
    w = np.asarray([float(x) for x in weights], float)
    w = w / w.sum()
    p = {c: 0.0 for c in cells}
    for k, ev in enumerate(member_events):
        for c in ev:
            if c in p:
                p[c] += w[k]
    o = {c: 1.0 if c in truth_births else 0.0 for c in cells}
    return float(sum((p[c] - o[c]) ** 2 for c in cells) / max(1, len(cells)))
