"""Contract E scoring; full-policy truth witnesses are supplied by a caller.

The evaluator must return contact, peak, dose and pass for the complete journey,
including issue and dwell. Unknown truth support keeps false_safe unknown. A
contact-only lower bound cannot establish a full-policy clairvoyant route.
"""
from __future__ import annotations

import math

def _nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Finite nonnegative " + name + " required")
    return value


OUTCOMES = {"checked_route", "model_no_route", "unresolved"}
TRUTHS = {"holdout_trajectory", "reconstructed_arrival", "observed_perimeters", "external_simulator"}


def score_decision(decision, *, evaluator, clairvoyant, cutoff, truth_source,
                   forecast_source, mission, truth_id=None, planning_ids=()):
    if truth_source not in TRUTHS:
        raise ValueError("Unknown truth source")
    if truth_id is not None and truth_id in planning_ids:
        raise ValueError("TRUTH_LEAKAGE")
    outcome = decision.get("outcome")
    if outcome not in OUTCOMES:
        raise ValueError("Explicit three-state outcome required")
    oracle = clairvoyant
    if oracle.get("scope") != "full_policy":
        raise ValueError("Clairvoyant reference must check the full policy")
    if oracle.get("outcome") not in OUTCOMES:
        raise ValueError("Explicit clairvoyant outcome required")
    exists = oracle.get("outcome") == "checked_route"
    oracle_arrival = _nonnegative(oracle.get("arrival_s"), "clairvoyant arrival") if exists else None
    row = dict(cutoff=cutoff, truth_source=truth_source, forecast_source=forecast_source,
               mission=mission, outcome=outcome, truth_id=truth_id,
               true_contact=None, true_peak=None, true_dose=None,
               arrival_s=None, clairvoyant_arrival_s=oracle_arrival,
               false_safe=None, false_refusal=None, regret_s=None)
    if outcome == "checked_route":
        row["false_refusal"] = False
        _nonnegative(decision.get("arrival_s"), "decision arrival")
        checked = evaluator(decision)
        for flag in ("contact", "passed", "supported", "definite_thermal_violation"):
            if checked.get(flag) is not None and not isinstance(checked[flag], bool):
                raise ValueError("Checker evidence flags require Boolean or unknown")
        for field in ("peak", "dose"):
            if checked.get(field) is not None:
                _nonnegative(checked[field], field)
        if checked.get("passed") is True and (checked.get("contact") is True or checked.get("definite_thermal_violation") is True):
            raise ValueError("Inconsistent checker evidence: passing known violation")
        if checked.get("supported") is True and checked.get("passed") is True and oracle.get("outcome") == "model_no_route":
            raise ValueError("Passing truth route contradicts clairvoyant no route")
        row.update(true_contact=checked.get("contact"), true_peak=checked.get("peak"),
                   true_dose=checked.get("dose"), arrival_s=decision["arrival_s"])
        if checked.get("contact") is True or checked.get("definite_thermal_violation") is True:
            row["false_safe"] = True
        if checked.get("supported") is True and isinstance(checked.get("passed"), bool):
            row["false_safe"] = not checked["passed"]
            row["false_refusal"] = False
            if checked["passed"] and exists:
                regret = row["arrival_s"] - oracle_arrival
                if regret < 0:
                    raise ValueError("TRUTH_ROUTE_BEATS_CLAIRVOYANT, inconsistent reference")
                row["regret_s"] = regret
    elif outcome == "model_no_route":
        row["false_safe"] = False
        if exists:
            row["false_refusal"] = True
        elif oracle.get("outcome") == "model_no_route":
            row["false_refusal"] = False
    # Unfinished computation makes neither a route nor a refusal assertion.
    # Leave both error metrics unknown and report unresolved separately.
    row["clairvoyant_outcome"] = oracle.get("outcome", "unresolved")
    return row


def wilson(successes, total, z=1.959963984540054):
    if total == 0:
        return None
    if not 0 <= successes <= total:
        raise ValueError("Invalid binomial count")
    p = successes / total
    den = 1 + z * z / total
    mid = (p + z * z / (2 * total)) / den
    half = z / den * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total))
    return [max(0.0, mid - half), min(1.0, mid + half)]


def summarize(rows):
    """Rates use known case outcomes; unresolved denominators stay visible.

    Wilson bounds are descriptive case-binomial intervals. Repeated truths or
    shared fire windows induce dependence and do not support population CIs.
    """
    rows = list(rows)
    out = {name: sum(r["outcome"] == name for r in rows) for name in sorted(OUTCOMES)}
    out["cases"] = len(rows)
    for metric in ("false_safe", "false_refusal"):
        known = [r[metric] for r in rows if isinstance(r.get(metric), bool)]
        count = sum(known)
        out[metric] = {"count": count, "denominator": len(known),
                       "unknown": len(rows) - len(known),
                       "rate": count / len(known) if known else None,
                       "wilson_descriptive": wilson(count, len(known))}
    return out
