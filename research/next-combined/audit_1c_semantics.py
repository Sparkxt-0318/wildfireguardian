"""Read-only fixtures for the acceptance and score-admission boundaries."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import warnings
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-c", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.track_c.resolve()
    for package in ("scenario-members", "sipp-routing", "synthetic-truth"):
        sys.path.insert(0, str(root / "experimental" / package / "src"))
    from wfg_scenario_members import accept, weighted_cvar
    from wfg_scenario_members.decision import decide
    from wfg_synthetic_truth.scoring import score_decision

    observations = []
    for name, flags, weights, expected in (
        ("unknown_mass_not_assumed_pass", [True, None], [0.4, 0.6], "unresolved"),
        ("known_mass_suffices_without_unknown", [True, None, False], [0.9, 0.05, 0.05], "checked_route"),
        ("insufficient_possible_mass_rejects_candidate_only", [False, None], [0.6, 0.4], "rejected_candidate"),
    ):
        k = 2 if len(flags) == 3 else 1
        verdict = accept(flags, rule="k_of_m", k=k, m=len(flags), weights=weights)
        observations.append({"id": name, "expected": expected, "observed": verdict["outcome"], "pass": verdict["outcome"] == expected})
    model = type("FixtureModel", (), {"ids": ["a", "b"]})()
    for rule, expected in (("all", "model_no_route"), ("k_of_m", "unresolved")):
        result = decide({}, {}, {}, model, planner=lambda *a, **k: {"status": "NO_ROUTE", "raw_status": "PROVEN_INFEASIBLE"},
                        acceptance={"rule": rule, "k": 1 if rule == "k_of_m" else 2, "m": 2})
        observations.append({"id": "union_exhaustion_" + rule, "expected": expected, "observed": result["outcome"], "pass": result["outcome"] == expected})

    def score(evaluation, oracle):
        return score_decision({"outcome": "checked_route", "arrival_s": 10}, evaluator=lambda _: evaluation,
            clairvoyant=oracle, cutoff="fixture", truth_source="holdout_trajectory", forecast_source="fixture",
            mission="fixture", truth_id="held-out", planning_ids=["planning"])

    score_cases = (
        ("known_contact_overrides_inconsistent_pass", {"supported": True, "passed": True, "contact": True},
         {"scope": "full_policy", "outcome": "checked_route", "arrival_s": 9}, "reject inconsistent evaluator or retain false_safe=true"),
        ("passing_truth_route_contradicts_no_route_oracle", {"supported": True, "passed": True, "contact": False},
         {"scope": "full_policy", "outcome": "model_no_route"}, "reject inconsistent oracle"),
        ("nonfinite_clairvoyant_arrival", {"supported": True, "passed": True, "contact": False},
         {"scope": "full_policy", "outcome": "checked_route", "arrival_s": float("nan")}, "reject nonfinite arrival"),
    )
    for name, evaluation, oracle, expected in score_cases:
        try:
            row = score(evaluation, oracle)
            passed = name == "known_contact_overrides_inconsistent_pass" and row["false_safe"] is True
            observed = {"state": "RETURNED", "false_safe": row["false_safe"], "false_refusal": row["false_refusal"],
                        "regret_s": "NaN" if isinstance(row["regret_s"], float) and math.isnan(row["regret_s"]) else row["regret_s"]}
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            passed = True
            observed = {"state": "RAISED", "type": type(exc).__name__, "message": str(exc)}
        observations.append({"id": name, "expected": expected, "observed": observed, "pass": passed})
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        try:
            cvar = weighted_cvar([10, 20], [1e308, 1e308], alpha=1.0, horizon=30)
            passed = math.isclose(cvar, 15.0, rel_tol=1e-14)
            observed = cvar
        except (ValueError, OverflowError) as exc:
            passed = True
            observed = {"state": "RAISED", "type": type(exc).__name__, "message": str(exc)}
    observations.append({"id": "finite_weight_normalization_overflow", "expected": "15 or explicit rejection", "observed": observed, "pass": passed})
    paths = [
        "experimental/scenario-members/src/wfg_scenario_members/acceptance.py",
        "experimental/scenario-members/src/wfg_scenario_members/decision.py",
        "experimental/synthetic-truth/src/wfg_synthetic_truth/scoring.py",
    ]
    result = {
        "scope": "small pure-interface fixtures only, no campaign or routing integration",
        "track_head": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
        "host": platform.platform(), "python": sys.version,
        "audit_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": {path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths},
        "observations": observations, "checks": len(observations), "passed": sum(row["pass"] for row in observations),
        "status": "PASS_TARGETED_INTERFACES" if all(row["pass"] for row in observations) else "FAIL_TARGETED_INTERFACES",
        "not_established": ["calibration", "physical correctness", "risk-campaign completion", "whole-road guarantee"],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"status": result["status"], "checks": result["checks"], "passed": result["passed"],
                      "failed": [row for row in observations if not row["pass"]]}, indent=2))
    return 0 if result["status"] == "PASS_TARGETED_INTERFACES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
