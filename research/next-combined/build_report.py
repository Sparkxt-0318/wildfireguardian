"""Build an interim readiness record from committed track evidence.

This command summarizes existing evidence. It does not execute routing,
train a model, merge branches, or waive any acceptance gate.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-a", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    track = args.track_a.resolve()
    head = subprocess.check_output(["git", "-C", str(track), "rev-parse", "HEAD"], text=True).strip()
    paths = [
        "research/flame-front-radiation/RESULTS.json",
        "research/flame-front-radiation/REQUIREMENTS_STATUS.json",
        "research/flame-front-radiation/README.md",
        "research/flame-front-radiation/physics_validation/RESULTS.json",
        "research/flame-front-radiation/physics_validation/SOURCES.json",
        "experimental/flame-front-radiation/src/wfg_flamefront/law_v2.py",
        "experimental/flame-front-radiation/src/wfg_flamefront/isochrone.py",
        "experimental/flame-front-radiation/src/wfg_flamefront/solidflame.py",
        "experimental/flame-front-radiation/adapters/journey_check.py",
    ]
    evidence = json.loads((track / paths[0]).read_text())
    requirements = json.loads((track / paths[1]).read_text())
    audit_path = args.out_dir / "audit/1a-simultaneous-initial.json"
    audit = json.loads(audit_path.read_text())
    gates = {
        "status": "INTERIM_HOLD_INCOMPLETE",
        "record_kind": "readiness_audit_only_not_integrated_experiment",
        "track_evidence": {
            "1A": {
                "head": head,
                "reported_status": evidence["status"],
                "test_count": evidence["tests"]["passed"],
                "random_enclosure_cases": evidence["tests"]["random_box_interval_cases"],
                "test_exit_code": evidence["tests"]["exit_code"],
                "seed": evidence["seed"],
                "physics_gate": evidence["physics_gate"],
                "routing_executions": evidence["routing_executions"],
                "previous_routes_rejected_under_v2": evidence["previous_routes_rejected_under_v2"],
                "peak_binding_missions": evidence["peak_binding_missions"],
                "dose_binding_missions": evidence["dose_binding_missions"],
                "requirements": requirements,
                "targeted_audit": {"status": audit["status"], "head": audit["track_head"], "path": str(audit_path.relative_to(args.out_dir))},
                "source_sha256": {path: digest(track / path) for path in paths},
                "reported_host": evidence["host"],
            },
            "1B": {"status": "PENDING_OWNER_FINAL_EVIDENCE", "head": None, "headline": None},
            "1C": {"status": "PENDING_OWNER_FINAL_EVIDENCE", "head": None, "headline": None},
        },
        "cross_track_checks": {
            "C1_C4_law_v2_vs_v1": {"state": "NOT_RUN_GATED", "reason": "1A empirical gate unresolved and complete journey adapter unavailable"},
            "binding_coherent_K4_K16": {"state": "NOT_RUN_GATED", "reason": "1A binding study and full journey adapter not implemented; no accepted empirical gate"},
            "SIPP_on_combined_bridge_v2_packets": {"state": "NOT_RUN_GATED", "reason": "Step 4 requires accepted 1A, 1C-1 and 1C-3; precondition not met"},
        },
        "branches_merged": [],
        "checkpoint_promoted": False,
        "commands": [
            {"command": evidence["tests"]["command"], "exit_code": evidence["tests"]["exit_code"], "kind": "owner_evidence"},
            {"command": ["../venv-routing/bin/python", "research/next-combined/audit_1a_semantics.py", "--track-a", "../track-1a", "--out", "research/next-combined/audit/1a-simultaneous-initial.json"], "exit_code": 1, "kind": "independent_targeted_audit"},
            {"command": [sys.executable, "research/next-combined/build_report.py", "--track-a", str(track)], "exit_code": 0, "kind": "summary_generation_only"},
        ],
        "summary_host": {"platform": platform.platform(), "python": sys.version},
        "open_work": ["1A targeted refusal repair and renewed audit", "1B final cohort evidence", "1C final export/member/campaign evidence", "final ownership/style/figure/claim checks", "publication by orchestrator"],
        "prior_remote_results_used_as_new_execution": False,
        "merge_order": ["1C-1 export and members", "1A library", "1B", "1C-2 SIPP", "1C-3 synthetic-truth harness", "integration"],
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "GATES.json").write_text(json.dumps(gates, indent=2) + "\n")
    a = gates["track_evidence"]["1A"]
    link = f"https://github.com/Sparkxt-0318/wildfireguardian/blob/{head}/research/flame-front-radiation/README.md"
    readme = f'''# Combined next-track readiness, interim HOLD

**No combined experiment has run. Track 1A reports {a["test_count"]} passing tests and {a["random_enclosure_cases"]:,} seeded enclosure regression cases, but its empirical physics gate is unresolved. Tracks 1B and 1C are still executing.** The independent targeted audit also found an unsupported-case zero-enclosure defect. This document is a readiness record, not a claim that the requested scientific campaign is complete.

## Track evidence

| Track | Current evidence | Acceptance state |
|---|---|---|
| 1A radiation | {a["test_count"]} tests, {a["random_enclosure_cases"]:,} enclosure regression cases, seed {a["seed"]}; routing rejection and binding counts are null | HOLD_INCOMPLETE; physics unresolved; targeted refusal repair needed |
| 1B forecast | Pending final owner evidence | Pending, no headline assigned |
| 1C members, SIPP and synthetic truth | Pending final owner evidence | Pending, no headline assigned |

The [1A report at its audited source revision]({link}) gives the detailed source and requirement ledger. `GATES.json` records the source hashes, exact test command, reported host and pending states. Results from the earlier remote Claude run are reference material and are not counted as executions in this run.

## Cross-track checks

| Requested check | Result | Reason |
|---|---|---|
| C1 and C4 with radiation v2 versus v1 | NOT_RUN_GATED | Empirical gate unresolved; complete v2 journey adapter unavailable |
| Binding on coherent members at K=4 and K=16 | NOT_RUN_GATED | 1A binding study and complete adapter unavailable |
| SIPP versus sweep on combined bridge-v2 packets | NOT_RUN_GATED | The orchestration Step 4 acceptance precondition is not met |

No track branch has been merged into this worktree. A pending or gated result has no numerical rate. It must not be replaced by zero, no-route, or a checked route.

## Independent targeted finding

At source revision `{audit["track_head"]}`, a 2 by 2 simultaneous-ignition field with a 10 s residence time causes point evaluation at 1.5 s to raise `UnsupportedGeometry`. Enclosure evaluation over the interior interval [1,2] s instead returns [0,0]. An enclosure consumer could mistake that unsupported case for known zero flux. The failing fixture, source hashes and observations are retained in `audit/1a-simultaneous-initial.json`. This is a model-interface defect; it does not measure a physical fire. The orchestrator has been notified and owns follow-up with the track agent.

## Commands and provenance

From this worktree, with the fresh pinned routing environment prepared by the orchestrator:

```sh
../venv-routing/bin/python research/next-combined/audit_1a_semantics.py --track-a ../track-1a --out research/next-combined/audit/1a-simultaneous-initial.json
../venv-routing/bin/python research/next-combined/build_report.py --track-a ../track-1a
```

The targeted audit exited 1, a retained finding. Report generation exits 0 and only summarizes evidence; it does not turn a failed gate into a pass. The track-owner test command and exit 0 are recorded verbatim in `GATES.json`. Owner test host: {a["reported_host"]["platform"]}, Python 3.12.1, NumPy 1.26.4. The summary host and exact versions are also recorded there. No performance claim is derived from unit-test elapsed time. Hashes identify the exact artifact bytes reviewed, not a new field observation.

## What changed in the scientific claims

The optical prototype supports a narrower claim than the requested completed radiation study. It supplies a deterministic panel model with closed-form geometry checks and a finite, coarse model envelope on supported input geometry. Straight marching-square segments approximate a bilinear contour, and the leading/trailing panels are a declared representation of a flaming band. Regression samples test implementation behavior; they do not establish physical accuracy. The spatially constant coarse enclosure can remain too loose to decide a thermal route condition under refinement.

The empirical gate cannot be inferred from the supplied literature numbers alone. Vegetation height is not flame height, plot width is not instantaneous emitting width, and an in-flame sensor measurement does not uniquely identify a spatially uniform emitter power. A diagnostic model ratio under assumed geometry is not a measured validation error. Constants must not be fitted to the desired routing headline. There is consequently no new supported count of formerly accepted journeys rejected under radiation v2, and no supported peak or dose binding frequency.

Support must also be part of a mathematical contract. If a source array does not identify old-fire phases, or a simultaneous ignition does not identify a moving-front gradient, a checker must retain that uncertainty. The targeted zero-enclosure inconsistency illustrates why a successful scalar return is not enough to establish a usable certificate. The model still needs consistent refusal behavior, a complete adapter, empirical case identification, and the requested journey-level studies.

For coherent trajectory experiments, a change in missing-data policy would confound a comparison of dependence structures. Invalid trajectory states must remain unknown rather than become never-burned cells. A route whose needed support is unknown remains unresolved or unscorable under its declared contract. Earlier remote results that used a different policy cannot be relabeled as current evidence.

SIPP evidence, once finalized, concerns equivalence and computational cost for the declared contact relaxation. It cannot by itself establish a full thermal optimum, calibrated road-cut probabilities, universal runtime improvement or real evacuation effectiveness. Forecast fits and historical mapped perimeters, once finalized, likewise remain conditional retrospective evidence. They are not the blind future-fire test, and no new checkpoint becomes the integration default from a descriptive lead.

The current scientific conclusion is therefore an explicit hold with retained independent checks and open obligations. It adds no field-accuracy or operational-safety claim. Later evidence may fill pending rows only after its source, denominator, support policy, seeds, host and gate state are recorded.

## Scope and limits

This interim artifact audits one committed prototype and records unfinished work. It is not an integrated software build or a cross-track experiment. No field validation, operational deployment, full continuous-road checker, new default checkpoint, or GitHub merge has occurred. Timing from unit tests is not campaign performance. The source-level finding is bounded to its documented fixture and revision; final repair verification must be retained separately without overwriting the failing preimage.

## Recommended review and merge order

1C-1 export and members, 1A library, 1B forecast, 1C-2 SIPP, 1C-3 synthetic-truth harness, then integration. This is a logical future order conditional on acceptance, not a recommendation to merge the present held prototype.
'''
    (args.out_dir / "README.md").write_text(readme)
    print(json.dumps({"status": gates["status"], "track_a_head": head, "track_a_tests": a["test_count"], "cross_track_experiments": "NOT_RUN_GATED"}))


if __name__ == "__main__":
    main()
