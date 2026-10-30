"""Contract E scoring; full-policy truth witnesses are supplied by a caller.

The evaluator must return contact, peak, dose and pass for the complete journey,
including issue and dwell. Unknown truth support keeps false_safe unknown. A
contact-only lower bound cannot establish a full-policy clairvoyant route.
"""
from __future__ import annotations

import math

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
    exists = oracle.get("outcome") == "checked_route"
    oracle_arrival = oracle.get("arrival_s") if exists else None
    row = dict(cutoff=cutoff, truth_source=truth_source, forecast_source=forecast_source,
               mission=mission, outcome=outcome, truth_id=truth_id,
               true_contact=None, true_peak=None, true_dose=None,
               arrival_s=None, clairvoyant_arrival_s=oracle_arrival,
               false_safe=None, false_refusal=None, regret_s=None)
    if outcome == "checked_route":
        checked = evaluator(decision)
        row.update(true_contact=checked.get("contact"), true_peak=checked.get("peak"),
                   true_dose=checked.get("dose"), arrival_s=decision["arrival_s"])
        if checked.get("supported") is True and isinstance(checked.get("passed"), bool):
            row["false_safe"] = not checked["passed"]
            row["false_refusal"] = False
            if checked["passed"] and exists:
                regret = row["arrival_s"] - oracle_arrival
                if regret < 0:
                    raise ValueError("TRUTH_ROUTE_BEATS_CLAIRVOYANT, inconsistent reference")
                row["regret_s"] = regret
    elif exists:
        row["false_refusal"] = True
    elif oracle.get("outcome") == "model_no_route":
        row["false_refusal"] = False
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
