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
    parser.add_argument("--track-c", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    track = args.track_a.resolve()
    worktree_head = subprocess.check_output(["git", "-C", str(track), "rev-parse", "HEAD"], text=True).strip()
    # The orchestrator can advance the audit worktree during a parallel review.
    # This report retains only the explicitly reviewed radiation revision.
    head = json.loads((args.out_dir / "audit/1a-simultaneous-repaired.json").read_text())["track_head"]
    def a_bytes(path):
        return subprocess.check_output(["git", "-C", str(track), "show", f"{head}:{path}"])
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
    evidence = json.loads(a_bytes(paths[0]))
    requirements = json.loads(a_bytes(paths[1]))
    audit_path = args.out_dir / "audit/1a-simultaneous-initial.json"
    audit = json.loads(audit_path.read_text())
    gates = {
        "status": "INTERIM_HOLD_INCOMPLETE",
        "record_kind": "readiness_audit_only_not_integrated_experiment",
        "track_evidence": {
            "1A": {
                "head": head,
                "source_selection": "Git snapshot pinned by separately reviewed A repair record, independent of current worktree HEAD",
                "worktree_head_at_generation": worktree_head,
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
                "source_sha256": {path: hashlib.sha256(a_bytes(path)).hexdigest() for path in paths},
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


def extend_interim_report():
    """Add the retained repair and the separately audited immutable C snapshot."""
    import csv
    import gzip
    from collections import defaultdict
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-a", type=Path, required=True)
    parser.add_argument("--track-c", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    out = args.out_dir
    root = args.track_c.resolve()
    def read(rel):
        return json.loads((root / rel).read_text())
    gates = json.loads((out / "GATES.json").read_text())
    repaired = json.loads((out / "audit/1a-simultaneous-repaired.json").read_text())
    audit_c = json.loads((out / "audit/1c-core-393f37748.json").read_text())
    a = gates["track_evidence"]["1A"]
    a["initial_targeted_audit"] = a.pop("targeted_audit")
    a["repaired_targeted_audit"] = {"status": repaired["status"], "head": repaired["track_head"], "path": "audit/1a-simultaneous-repaired.json"}
    native = read("research/sipp-routing/RESULTS.json")
    exports = read("research/scenario-members/EXPORT_AUDIT.json")
    wrapper = read("research/scenario-members/WRAPPER_EQUIVALENCE.json")
    custody = read("research/sipp-routing/native-panel-20261030/CUSTODY.json")
    rows = list(csv.DictReader((root / "research/sipp-routing/native-panel-20261030/EXECUTIONS.csv").open()))
    pairs = defaultdict(dict)
    for row in rows:
        pairs[(row["panel"], row["mission"], row["repetition"])][row["method"]] = row
    equivalent = sum((p["sweep"]["status"], p["sweep"]["arrival"]) == (p["sipp"]["status"], p["sipp"]["arrival"]) and p["sipp"]["status"] != "UNRESOLVED" for p in pairs.values())
    slower = sum(float(p["sipp"]["complete_wall_s"]) > float(p["sweep"]["complete_wall_s"]) for p in pairs.values())
    assert len(rows) == native["native"]["executions"]
    assert equivalent == native["native"]["equivalent_pairs"] and len(pairs) == native["native"]["pairs"]
    assert slower == native["native"]["sipp_slower_pairs"]
    fields = [v for row in custody["rows"] for v in row["fields"].values()]
    assert len(fields) == custody["pinned_fields"]
    assert sum(v["matches_job"] is True and v["matches_case"] for v in fields) == custody["job_matches"]
    counts = {}
    compressed = sorted((root / "research/synthetic-truth/strict-support-20261030").glob("C*.jsonl.gz"))
    for path in compressed:
        count = 0
        with gzip.open(path, "rt") as stream:
            for line in stream:
                row = json.loads(line)
                assert row["outcome"] == "unresolved" and row["false_safe"] is None and row["false_refusal"] is None
                count += 1
        counts[path.name.split(".")[0]] = count
    paths = ["research/sipp-routing/RESULTS.json", "research/sipp-routing/PROPERTY_CENSUS.json", "research/sipp-routing/native-panel-20261030/EXECUTIONS.csv", "research/sipp-routing/native-panel-20261030/CUSTODY.json", "research/scenario-members/EXPORT_AUDIT.json", "research/scenario-members/WRAPPER_EQUIVALENCE.json", "research/scenario-members/TRACK_STATUS.json", "research/scenario-members/TEST_RECEIPT.json", "research/synthetic-truth/RESULTS.json"]
    paths += [str(path.relative_to(root)) for path in compressed]
    c = {"status": "AUDITED_INTERIM_SNAPSHOT_OWNER_CONTINUES", "head": subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip(),
         "native": native["native"], "abstract_census": native["random_census"], "custody": native["custody"],
         "exports": {k: exports[k] for k in ("windows", "v2_array_identity_passes", "full_n_mean_passes", "windows_with_unknown_support")},
         "wrapper_equivalence": {k: wrapper[k] for k in ("event", "cutoff", "npz_bytes_identical", "old_npz_sha256", "new_npz_sha256")},
         "admission_record_counts": counts, "admission_records": sum(counts.values()), "scorable_truth_cases": 0,
         "false_safe_rate": None, "false_refusal_rate": None, "targeted_audit": audit_c,
         "owner_requirements": read("research/scenario-members/TRACK_STATUS.json"), "source_sha256": {p: digest(root / p) for p in paths},
         "audit_scope": "Independent pair/count and internal custody-record checks; original-job/source matches are owner-recorded evidence"}
    gates["track_evidence"]["1C"] = c
    gates["track_evidence"]["1B"]["heldout_scores_inspected"] = False
    gates["open_work"][0] = "1A empirical geometry, usable enclosure and full journey adapter"
    gates["open_work"].insert(2, "1C defensive score and weight-admission repairs")
    gates["commands"].append({"command": "ROUTING_PYTHON research/next-combined/audit_1c_semantics.py --track-c SNAPSHOT_C --out FRESH_AUDIT", "exit_code": 1, "scope": "small interface fixtures, not a campaign"})
    gates["commands"].append({"command": "ROUTING_PYTHON research/next-combined/audit_1a_semantics.py --track-a REPAIRED_A --out FRESH_AUDIT", "exit_code": 0, "scope": "retained repair fixture"})
    for item in gates["commands"]:
        command = item.get("command")
        if isinstance(command, list) and "research/next-combined/build_report.py" in command:
            command.extend(["--track-c", str(root)])
    (out / "GATES.json").write_text(json.dumps(gates, indent=2, allow_nan=False) + "\n")
    text = (out / "README.md").read_text()
    text = text.replace("build_report.py --track-a ../track-1a", "build_report.py --track-a ../track-1a --track-c ../audit-1c")
    text = text.replace("Tracks 1B and 1C are still executing.", "Forecast fits are still in progress; an immutable interim 1C snapshot is audited below.")
    text = text.replace("The independent targeted audit also found an unsupported-case zero-enclosure defect.", "The original unsupported-case zero-enclosure defect has been repaired and independently rechecked; its failing record remains preserved.")
    text = text.replace("targeted refusal repair needed", "targeted refusal defect repaired")
    n = c["native"]
    text = text.replace("| 1C members, SIPP and synthetic truth | Pending final owner evidence | Pending, no headline assigned |", f'| 1C members, SIPP and synthetic truth | {n["equivalent_pairs"]}/{n["pairs"]} native contact pairs; {c["abstract_census"]["agree"]:,}/{c["abstract_census"]["cases"]:,} abstract comparisons; {c["exports"]["v2_array_identity_passes"]}/{c["exports"]["windows"]} export-array equality checks | HOLD_PARTIAL; owner continues; targeted score-admission fixes needed |')
    text = text.replace("The orchestrator has been notified and owns follow-up with the track agent.", f'The defect was repaired at `{repaired["track_head"]}`. The same fixture now raises consistently from both interfaces: `{repaired["status"]}` in `audit/1a-simultaneous-repaired.json`. This is a bounded interface repair, not an empirical-physics pass.')
    text = text.replace("final repair verification must be retained separately", "repair verification is retained separately")
    text = text.replace("The model still needs consistent refusal behavior, a complete adapter, empirical case identification, and the requested journey-level studies.", "The repaired domain guard adds consistent refusal evidence; a complete adapter, empirical case identification, and the requested journey-level studies remain open.")
    text = text.replace("The targeted audit exited 1, a retained finding.", "The initial targeted audit exited 1; the repaired fixture exited 0, both retained separately.")
    text += f'''

## Immutable 1C snapshot audit

Historical core snapshot `{audit_c["track_head"]}` has {n["executions"]} native contact-relaxation executions across {n["missions"]} missions, with {n["equivalent_pairs"]}/{n["pairs"]} paired status-and-arrival matches. SIPP was slower in {n["sipp_slower_pairs"]}/{n["pairs"]} pairs. The raw CSV independently reproduces these counts. The custody ledger is internally consistent with its {custody["job_matches"]}/{custody["pinned_fields"]} reported original-job field matches. Original controller bytes remain retained; its final-after-exit guard was repaired after these executions, which were far below both limits. These are bounded contact-relaxation results, not full thermal-planner or universal runtime claims.

All {exports["windows"]} real exports pass the producing v2-array equality checks and full-N mean checks on known support. That script uses `array_equal`, including equal-NaN handling; this is not a general dtype or NaN-bit identity proof. A separate real {wrapper["event"]} cutoff establishes identical whole-NPZ hashes between the relocated wrapper and archived producer for that cutoff. The frozen exporter was restored; the default rollout diff adds only the optional observer and guarded call. The Boolean observer state is separately allocated. Block identity, offset and batch size are required for individual trajectory replay; seed alone is insufficient.

The copied full-journey checker explicitly checks a cell-centre surrogate. The wrapper preserves rejected candidates as unresolved, retains no-route only for uncut all-member relaxation exhaustion, and does not promote union exhaustion to k-of-m refusal. Its bounded lazy cuts remove whole departure singletons, so their exhaustion cannot prove global infeasibility or optimality. Whole-road validity, real scenario-reduction coverage, member-count scaling and scored risk campaigns remain open. Global-source completeness is a conservative admission policy, not proof that every local checker or pessimistic bound on unknown sources would fail.

The compressed campaign records were independently counted and checked for unresolved outcomes and null false-safe/false-refusal fields:

| Campaign | Admission records | Scored risk cases |
|---|---:|---:|
| C1 | {counts["C1"]:,} | 0 |
| C2 | {counts["C2"]:,} | 0 |
| C3 | {counts["C3"]:,} | 0 |
| C4 | {counts["C4"]:,} | 0 |

The total {c["admission_records"]:,} records are unscorable admission records, not risk-validation samples. They identify no numerical false-safe/refusal rate. Brier diagnostics concern joint known cells only. The one-hour single-component case supplies no multi-step coherence contrast, and changing missing-data policy would confound the comparison. Shared truth draws and regional panels are clustered rather than independent fires.

The pure-interface audit passed {audit_c["passed"]}/{audit_c["checks"]} fixtures, with four retained defensive failures: inconsistent evaluator flags can erase a known-contact violation; a supported passing journey can coexist with a no-route oracle without rejection; nonfinite oracle arrival can produce nonfinite regret; and overflowing finite weights can turn positive CVaR into zero. These defects concern admitted inconsistent or extreme inputs, not numerical errors asserted in the unscorable campaign. Exact fixtures and source hashes are retained in `audit/1c-core-393f37748.json`, produced by `audit_1c_semantics.py`, exit 1. The owner has been notified. Unknown-mass decisions and all-member versus k-of-m no-route semantics passed their targeted fixtures. The scoring API also relies on caller-provided truth and oracle identities; the label `scope=full_policy` alone is not an independent proof or source binding.

This audit did not inspect 1B held-out scores. Its final fits, selection registry and reviewed blind protocol remain pending. The 1C owner is adding independent adapters and features after this snapshot, so this report does not finalize that track's gate. All cross-track scientific integration checks remain `NOT_RUN_GATED`.

To regenerate the interim summary and repeat targeted checks, use fresh output paths:

```sh
../venv-routing/bin/python research/next-combined/audit_1c_semantics.py --track-c ../audit-1c --out FRESH_C_AUDIT.json
../venv-routing/bin/python research/next-combined/audit_1a_semantics.py --track-a ../track-1a --out FRESH_A_AUDIT.json
../venv-routing/bin/python research/next-combined/build_report.py --track-a ../track-1a --track-c ../audit-1c
```

The owner host is native macOS arm64 with Python 3.12.1 and NumPy 1.26.4; export seed 0, member/campaign seed 20261008. Exact commands, owner test receipts, hashes and audit scope are in `GATES.json`. No performance result is derived from these interface fixtures, and no branch was merged.
'''
    (out / "README.md").write_text(text)
    print(json.dumps({"a_repair": repaired["status"], "c_pairs": len(pairs), "c_records": c["admission_records"], "c_interface_audit": audit_c["status"]}))


def extend_repaired_core_and_reader_audit():
    """Preserve prior findings while adding the next immutable review stage."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-a", type=Path, required=True)
    parser.add_argument("--track-c", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    out, root = args.out_dir, args.track_c.resolve()
    gates = json.loads((out / "GATES.json").read_text())
    c = gates["track_evidence"]["1C"]
    repaired = json.loads((out / "audit/1c-core-a2c6f8a69.json").read_text())
    readers = json.loads((out / "audit/1c-readers-a2c6f8a69.json").read_text())
    receipt = json.loads((root / "research/scenario-members/POST_REPAIR_RECEIPT.json").read_text())
    byte_audit = json.loads((root / "research/scenario-members/EXPORT_BYTE_AUDIT.json").read_text())
    smoke = json.loads((root / "research/synthetic-truth/REAL_READERS_SMOKE.json").read_text())
    c["initial_targeted_audit"] = c.pop("targeted_audit")
    c["repaired_targeted_audit"] = repaired
    c["reader_targeted_audit"] = readers
    c["export_exact_byte_audit"] = {k: v for k, v in byte_audit.items() if k != "rows"}
    assert all(row["exact_arrays_equal"] and row["all_npy_entries_equal"] for row in byte_audit["rows"])
    assert len(byte_audit["rows"]) == byte_audit["exact_array_window_passes"] == byte_audit["exact_npy_window_passes"]
    c["post_repair_test_receipt"] = receipt
    for path, expected in receipt["artifacts"].items():
        assert digest(root / path) == expected
    # Historical manifests can change in a later independently audited repair.
    # Keep that generation's expected digest rather than asserting that it is current.
    c["historical_source_manifests_match_current"] = {path: digest(root / path) == expected
                                                       for path, expected in receipt["source_manifests"].items()}
    c["post_repair_artifact_hashes_match_receipt"] = True
    summaries = []
    for row in smoke["readers"]:
        summary = {k: v for k, v in row.items() if k != "source"}
        summary["source_identity"] = {k: v for k, v in row["source"].items() if k in ("path", "source_id", "sha256")}
        if row["kind"] == "external_simulator":
            summary["metadata"] = row["source"].get("metadata")
        summaries.append(summary)
    c["real_reader_smoke"] = {"scope": smoke["scope"], "readers": summaries, "native_simulator_execution": smoke["native_simulator_execution"]}
    for rel in ("research/scenario-members/POST_REPAIR_RECEIPT.json", "research/scenario-members/EXPORT_BYTE_AUDIT.json", "research/synthetic-truth/REAL_READERS_SMOKE.json", "experimental/scenario-members/src/wfg_scenario_members/features.py", "experimental/synthetic-truth/src/wfg_synthetic_truth/adapters.py"):
        c["source_sha256"][rel] = digest(root / rel)
    gates["open_work"] = ["1A empirical geometry and full journey adapter, separately from a later unaudited enclosure revision", "1B remaining fits, geometry sensitivity, frozen selection and protocol review", "1C reader time/georeference/source-kind admission repairs", "real reduction/coverage and risk campaigns under a declared supported policy", "final publication by orchestrator"]
    gates["commands"].append({"command": "ROUTING_PYTHON research/next-combined/audit_1c_semantics.py --track-c REPAIRED_C --out FRESH_CORE_AUDIT", "exit_code": 0, "checks": repaired["checks"], "passed": repaired["passed"]})
    gates["commands"].append({"command": "ROUTING_PYTHON research/next-combined/audit_1c_readers.py --track-c SNAPSHOT_C --out FRESH_READER_AUDIT", "exit_code": 1, "checks": readers["checks"], "passed": readers["passed"]})
    (out / "GATES.json").write_text(json.dumps(gates, indent=2, allow_nan=False)+"\n")
    text = (out / "README.md").read_text()
    text = text.replace("targeted score-admission fixes needed", "prior core defects repaired; reader admission findings open")
    text = text.replace("The pure-interface audit passed", "The historical core snapshot `393f37748` pure-interface audit passed")
    text = text.replace("The owner has been notified. Unknown-mass decisions", "The owner repaired those four core findings; the same fixtures now pass at the current snapshot, retained separately below. Unknown-mass decisions")
    text = text.replace("The 1C owner is adding independent adapters and features after this snapshot", "The 1C owner has added independent adapters and features at this snapshot, with reader-boundary repairs pending")
    text = text.replace("../track-1a", "../audit-1a")
    text += f'''

## Repaired core and new reader review

The prior repaired-core snapshot is `{repaired["track_head"]}`. The original core failure record at `393f37748` is unchanged. The independent post-repair core audit passes {repaired["passed"]}/{repaired["checks"]} fixtures, recorded separately in `audit/1c-core-a2c6f8a69.json`; it repairs the earlier known-contact, oracle-consistency, nonfinite-arrival and weight-normalization failures. It does not discharge physical, whole-road or risk-study gates.

The stronger export method is now separate from the historical value-equality method: {byte_audit["exact_array_window_passes"]}/{byte_audit["windows"]} windows match dtype, shape, exact payload bytes including NaN bits, and {byte_audit["exact_npy_window_passes"]}/{byte_audit["windows"]} match the uncompressed NPY entries for every shared v2 array. The earlier `array_equal` limitation remains documented as history, not the final method. A regression verifies that different NaN payloads fail this stronger method even when value equality passes. This is shared-array identity; the separate one-cutoff whole-NPZ wrapper comparison has its narrower scope.

The post-repair receipt records 40 routing-environment tests passed with 4 dependency skips, and 20 selected forecast/GIS/export/features/scoring tests passed separately. These selectors overlap and must not be summed as independent tests. The source/artifact digests in the receipt match the archived files. The reported release verifier passes 367 copied hashes. A failed attempt to run the entire suite in the forecast environment is retained because that environment lacked Hypothesis; the successful split-environment receipts are stated explicitly.

The new reconstruction reader uses explicit seconds/minutes/hours and origin-to-cutoff conversion, exact grid alignment, nodata support and optional descriptive SD intervals. Nodata is not never-burned. The observed-perimeter reader keeps only arrival upper bounds, never exact ignition or survey-negative coverage; its actual CedarCreek collection is wholly unscorable after eight invalid source geometries, without silently repairing them. These are reader smoke results, not risk cases. The road-feature function reports unit-second unsafe departure times and metre chord weights, using the declared native-row mapping; no real road-reduction/K-scaling study is added by those fixtures, and caller data/grid admission remains a separate obligation.

The actual stored Wapiti metadata declares FARSITE, minutes, engine origin 1724048580 and a finite 1470 minute duration. It does not describe a new native simulation in this run. The smoke report has 11,655 covered cells, including 11,215 nonarrival sentinels. Those finite-run nonarrivals need a preserved query-time horizon or right-censoring interpretation; they do not establish global never-ignition after the simulation ends.

Five new reader boundary fixtures currently fail defensive admission or qualification, retained in `audit/1c-readers-a2c6f8a69.json`: a 1000 minute arrival is accepted despite a declared 10 minute simulation; nonarrival is exposed as a point-model infinity without a query-time validity bound; explicitly contradictory learned-probability metadata is still labeled FARSITE; an output lacking geometry is accepted against two reference grids shifted by 1000 m without an explicit unverified-alignment state; and a fractional UTC offset is silently truncated to a whole second. These are synthetic schema fixtures. They do not assert that the actual Wapiti file has wrong family, out-of-range arrivals or misaligned coordinates. Borrowed grid information must be qualified as a caller assertion unless verified from source coordinates or an independently bound alignment record. The owner has been notified for repair.

```sh
../venv-routing/bin/python research/next-combined/audit_1c_semantics.py --track-c ../audit-1c --out FRESH_REPAIRED_CORE.json
../venv-routing/bin/python research/next-combined/audit_1c_readers.py --track-c ../audit-1c --out FRESH_READER_AUDIT.json
../venv-routing/bin/python research/next-combined/build_report.py --track-a ../audit-1a --track-c ../audit-1c
```

The current A evidence remains the immutable f9fa03290 radiation snapshot, not the later spatial-enclosure implementation being developed on its live branch. No claim about that later enclosure is made. All scientific integration experiments remain gated, and B final fits, geometry sensitivity, selection registry, protocol review and held-out results remain pending in this record.
'''
    (out / "README.md").write_text(text)
    print(json.dumps({"core_repair": repaired["status"], "reader_audit": readers["status"], "byte_identity_windows": byte_audit["windows"]}))


def extend_reader_repair_and_preheldout_review():
    """Record the separately audited reader repair and preheldout tool failures."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-a", type=Path, required=True)
    parser.add_argument("--track-c", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    out, root = args.out_dir, args.track_c.resolve()
    gates = json.loads((out / "GATES.json").read_text())
    c, b = gates["track_evidence"]["1C"], gates["track_evidence"]["1B"]
    readers = json.loads((out / "audit/1c-readers-e68123d81.json").read_text())
    assert c["head"] == readers["track_head"], "Review the next immutable repair independently before regenerating"
    core = json.loads((out / "audit/1c-core-e68123d81.json").read_text())
    horizon = json.loads((out / "audit/1c-horizon-e68123d81.json").read_text())
    review = json.loads((out / "audit/1b-blind-tools-be678bb65.json").read_text())
    metrics = json.loads((out / "audit/1b-metric-reference-be678bb65.json").read_text())
    receipt = json.loads((root / "research/synthetic-truth/READERS_REPAIR_RECEIPT.json").read_text())
    native = json.loads((root / "research/synthetic-truth/NATIVE_FARSITE_AVAILABILITY.json").read_text())
    smoke = json.loads((root / "research/synthetic-truth/REAL_READERS_SMOKE_POST_REPAIR.json").read_text())
    matches = {}
    for group in ("current_sources", "artifacts", "historical_artifacts_preserved"):
        matches[group] = {p: digest(root / p) == expected for p, expected in receipt[group].items()}
        assert all(matches[group].values())
    native_root = root.parent / "data/forecast-v2/native-farsite"
    matches["native_files"] = {p: digest(native_root / p) == row["sha256"] == row["expected_sha256"] for p, row in native["identities"].items()}
    matches["native_outputs"] = {kind: digest(Path(native["usage"][kind + "_path"])) == native["usage"][kind + "_sha256"] for kind in ("stdout", "stderr")}
    assert all(matches["native_files"].values()) and all(matches["native_outputs"].values())
    summary = {"scope": "Independent source/receipt/file custody checks, targeted fixtures and finite-run boundaries; no new native execution", "head": c["head"], "reader_fixture": readers["status"], "core_fixture": core["status"], "horizon_fixture": horizon, "matches": matches, "owner_receipt": receipt,
               "native_availability": {"usage_exit": native["usage"]["exit_code"], "elapsed_s": native["usage"]["elapsed_s"], "timeout_s": native["usage"]["timeout_s"], "timed_out": native["usage"]["timed_out"], "cleanup": native["usage"]["cleanup"], "availability": native["availability"], "clock": native["clock"]},
               "post_repair_smoke": [{k: v for k, v in row.items() if k != "source"} for row in smoke["readers"]]}
    (out / "audit/1c-repair-custody-e68123d81.json").write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n")
    c["status"] = "SOFTWARE_TARGETED_REPAIRS_VERIFIED_DRAFT_REVIEWABLE_SCIENCE_HOLD_PARTIAL"
    c["reader_targeted_audit_historical"] = c.pop("reader_targeted_audit")
    c["reader_repaired_audit"] = readers
    c["core_recheck"] = core
    c["reader_repair_custody"] = "audit/1c-repair-custody-e68123d81.json"
    c["native_execution_scope"] = summary["native_availability"]
    c["post_reader_repair_smoke"] = summary["post_repair_smoke"]
    b.update(status="PREHELDOUT_TOOL_REVIEW_FAIL_OWNER_REPAIR_REQUIRED", head=review["track_head"], software_review=review, synthetic_metric_reference=metrics, heldout_scores_inspected=False)
    gates["open_work"] = ["1A physics and journey-adapter gate, separately from unaudited live enclosure work", "1B source/cache/resume/reference binding, completeness gate and independent repaired-tool review before heldout", "1B remaining final fits, frozen selection, baselines and 12-cutoff comparison", "real reduction/coverage and risk campaigns under a declared supported policy", "final publication by orchestrator"]
    for script, record, exit_code in [("audit_1c_readers.py", "audit/1c-readers-e68123d81.json", 0), ("audit_1c_semantics.py", "audit/1c-core-e68123d81.json", 0), ("audit_1c_horizon.py", "audit/1c-horizon-e68123d81.json", 0), ("audit_1b_blind_tools.py", "audit/1b-blind-tools-be678bb65.json", 1), ("audit_1b_metric_reference.py", "audit/1b-metric-reference-be678bb65.json", 0)]:
        track = "c" if "1c" in script else "b"
        gates["commands"].append({"command": f"../venv-{'routing' if track == 'c' else 'forecast'}/bin/python research/next-combined/{script} --track-{track} ../audit-1{track} --out research/next-combined/{record}", "exit_code": exit_code, "scope": "synthetic fixtures only; immutable source, no heldout study input read"})
    (out / "GATES.json").write_text(json.dumps(gates, indent=2, allow_nan=False) + "\n")
    text = (out / "README.md").read_text()
    text = text.replace("| 1B forecast | Pending final owner evidence | Pending, no headline assigned |", "| 1B forecast | Final fits pending; pre-heldout tool audit finds five admission failures; no heldout scores inspected | HOLD; repair and independent review required before scoring |")
    text = text.replace("prior core defects repaired; reader admission findings open", "core and reader defects repaired; software draft-reviewable, science HOLD_PARTIAL")
    text = text.replace("Five new reader boundary fixtures currently fail defensive admission or qualification", "At the prior a2c6f8a69 snapshot, five reader boundary fixtures failed defensive admission or qualification")
    text += '''

## Reader repairs verified and pre-heldout tool review

The immutable 1C snapshot is now `e68123d81fb9064ad057425d7c954f923b50097c`. Separate repaired records retain 5/5 reader admissions and 9/9 core interface checks. Four additional synthetic finite-run boundary queries pass: an explicit horizon is required, 3600 s and the inclusive 88200 s endpoint are supported, and 88201 s is unscorable. Infinity from a bounded query means no arrival through that query only. The actual Wapiti smoke now retains 11,215 right-censored cells and zero global-never cells, with arrival-model validity through 88,200 s. Its metadata is qualified as a declared deterministic stored FARSITE model, not a new simulation or observed ignition truth.

All repair-receipt source/artifact/historical digests match their archived bytes. The owner reports 44 routing tests passed with four skips and 24 selected forecast/GIS tests passed; the selectors overlap and are not summed. The release receipt reports 367 copied hashes passed. Five archived native binary/source/manifest identities and the recorded stdout/stderr hashes were independently checked. The isolated no-argument native usage probe exited 1 as expected in 1.414 s under a 5 s timeout, with its process group absent at completion. This establishes execution availability on this host only. The optional clock probe was NOT_RUN_HEAVY_LOCK_BUSY. No native spread simulation or physical validity result is claimed. These checks make the repaired software reviewable for draft publication; the track's whole-road, supported risk-campaign and scientific gates remain open.

The independent pre-heldout review of 1B is pinned to `be678bb655cb2b3f7985d2b6f73b4f20b044a2ce`. Both complete scoring scripts and the directly called pipeline helpers were read from that immutable snapshot. All research-script code is excluded from the graph by design, so direct source was required. Baseline metric functions and the draft registration were checked against the indexed snapshot. No actual heldout predictions, scores or source datasets were inspected.

Five synthetic probes expose these open admission defects:

| Tool and source | Reproduced behavior | Required repair |
|---|---|---|
| `score_cohorts.py:164-210` | Resume accepts deliberately wrong initial, endpoint, environment and reference hashes; stale label 0 is reused against current endpoint 1, with only a persistence model column, and the assessment becomes COMPLETE | Recompute and compare every executed input identity; authenticate exact labels, ordered coordinates, common support and model set before reuse |
| `pipeline.py:136-141` | A cache with raw value 123456 and an invented channel is returned without any source rasters | Bind cache entries to input/source contract and verify metadata/payload; refuse unauthenticated entries |
| `blind_test.py:264-297` | Fractional coordinates and columns beyond 100000 enter scoring; no pinned reference labels or common-support identity is checked | Bind scoring to validated references, integer in-range ordered coordinates, exact endpoint labels and the registered common support |
| `blind_test.py:264-274` | A 1999 cohort with a minimally shaped registry and a self-consistent receipt enters the score path | Revalidate eligibility/model/source/input closure or verify a complete authenticated validated-run receipt before scoring |
| `blind_test.py:280-320` | Ten scored synthetic fires plus one failed eligible case yield a primary statistical pass flag and SCORED_PENDING_RELOCATION_REPLAY | Make full cohort completion an explicit necessary decision gate; retain failures and hold any promotion |

The last fixture does not issue a superiority claim: the top-level flag remains false. Its concern is the misleading intermediate pass/completion state, which must not become eligible for promotion merely after relocation. The resume fixture replaces only numerical producers and identity setup with synthetic objects to isolate the existing resume branch. These are defensive mechanism failures, not allegations of wrong numbers in an actual heldout campaign. Exact scripts, immutable-source hashes, observations and exit codes are preserved in `audit/1b-blind-tools-be678bb65.json` and its producer `audit_1b_blind_tools.py`, exit 1. The owner has been notified before heldout execution.

The draft's primary metric is pooled cell-interval Brier, distinct from equal-fire development model selection. The code correctly pools error sums/counts within each whole-fire bootstrap draw. A separate unequal-fire synthetic arithmetic fixture reproduces pooled difference -0.8 versus equal-fire difference 0.0, the expected bootstrap endpoints, and fixed calibration-bin boundaries. This pass does not repair input custody. The fixed model set, both baseline comparisons, low-bin comparison, ten-fire minimum and separate Korean evidence class are present, but dataset-release completeness and external registration authenticity remain documentary obligations beyond a self-declared catalog or URL. The blind protocol remains NOT_READY.

All historical failures are preserved. C software repair evidence, B tool failures, pending B numerical evidence and the unresolved A physics gate remain separate. No track merge, new default checkpoint, heldout score inspection or scientific integration experiment has occurred.
'''
    (out / "README.md").write_text(text)
    print(json.dumps({"c_reader_repair": readers["status"], "c_core": core["status"], "b_tools": review["status"], "cross_track": "NOT_RUN_GATED"}))


def extend_b_repair_recheck():
    """Preserve first failures, then record repaired guards and new fresh-run gaps."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-a", type=Path, required=True)
    parser.add_argument("--track-c", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    out = args.out_dir
    gates = json.loads((out / "GATES.json").read_text())
    audit = json.loads((out / "audit/1b-repaired-tools-08ac32c7.json").read_text())
    b = gates["track_evidence"]["1B"]
    b["previous_software_review"] = b.pop("software_review")
    b["head"] = audit["track_head"]
    b["status"] = "ORIGINAL_GUARDS_REPAIRED_FRESH_ASSESSMENT_HOLD_TWO_NEW_ADMISSIONS"
    b["software_review"] = audit
    b["owner_reported_checks"] = {"targeted_tests": 60, "full_forecast_tests": 2939,
        "environment_caches_rederived": 1387, "active_sample_lists_rederived": 80,
        "value_dtype_shape_order_metadata_changes": 0, "obsolete_mixed_caches_retained_excluded": 34,
        "scope": "Owner report only; this independent review did not open actual study inputs or caches. Synthetic exploits do not establish actual cache corruption."}
    gates["track_evidence"]["1C"]["draft_pr"] = "https://github.com/Sparkxt-0318/wildfireguardian/pull/86"
    gates["open_work"][1] = "1B fresh assessment baseline execution identity and deterministic full-support admission; independent repaired review before heldout"
    gates["commands"].append({"command": "../venv-forecast/bin/python research/next-combined/audit_1b_repaired_tools.py --track-b ../audit-1b --out research/next-combined/audit/1b-repaired-tools-08ac32c7.json", "exit_code": 1, "checks": audit["checks"], "passed": audit["passed"], "scope": "Independent synthetic guard matrix; numerical producers mocked, no study inputs read"})
    (out / "GATES.json").write_text(json.dumps(gates, indent=2, allow_nan=False) + "\n")
    text = (out / "README.md").read_text()
    text = text.replace("Final fits pending; pre-heldout tool audit finds five admission failures; no heldout scores inspected", "Original five guard mechanisms repaired; 50/52 independent synthetic checks pass, with two fresh-assessment admissions open; no heldout scores inspected")
    text += '''

## Independent B repair recheck

The next immutable B review is pinned to `08ac32c7f23a886dba6a8373eea27dd84e18d83e`. The original failure record and script remain unchanged. The separate repaired harness now correctly treats constructor refusal of an unauthenticated cache as a pass and continues. The independent matrix passes 50/52 checks. A valid assessment control has all 16 expected model columns; the blind protocol has 15 because it excludes the additional c651 mean-field comparator. Separate otherwise valid fixtures test each receipt/source field, integer and exact ordered coordinates, negative/out-of-range/duplicate/reordered/subset coordinates, label identity, missing/extra model columns, nonfinite/out-of-range/misshaped probabilities, counts and the complete common-support hash. They do not rely on an earlier model-set refusal to infer the later guards work.

Direct blind scoring now reruns full validation, rederives current support, compares every endpoint label and exact ordered coordinate, and verifies the validated source/model/input identity of its run receipt. The separate synthetic identity tests refuse changed source, checkpoint and input bytes, a 1999 cohort, old receipt contracts and substituted case metadata. Incomplete primary decisions keep every promotion field false, with subset comparisons explicitly descriptive. The fixed pooled statistic and whole-fire bootstrap remain unchanged. These repairs discharge the original five mechanism findings within the tested scope.

Two fresh-assessment cases still fail, both in `score_cohorts.py`:

| Finding | Exact synthetic reproduction | Required action |
|---|---|---|
| Executed baseline paths differ from frozen selection | `identities:82-116` validates logistic and dilation files under the selection's frozen paths, then accepts different files under `--run/baselines`; the loaded hashes differ, and the loaded dilation is 8 instead of the frozen 4 | Compare the actual files consumed by `main` against the selection's frozen baseline bytes before execution |
| Fresh Monte Carlo numeric failure trims the scored population | `predict_case:174-198` has three deterministic supported cells but one MC NaN with validity true; fresh mask shrinks to two, and `validate_entries` accepts that smaller mask because fresh `main` supplies it as the expected mask | Independently compute fresh deterministic support, require equality and finite MC probabilities on all of it, and refuse numerical failure rather than exclude those cells |

The second guard already exists in the blind producer. Resumed assessment validation recomputes deterministic support; fresh and resumed admission need the same population. The exact producer is `audit_1b_repaired_tools.py`, with separate record `audit/1b-repaired-tools-08ac32c7.json`, exit 1. These synthetic cases do not establish that actual study baselines differ or that actual Monte Carlo predictions contain NaNs. The owner has both findings before any heldout evaluation.

The actual cache audit is a distinct owner report: 1,387 environmental caches and 80 active sample lists were rederived with no value, dtype, shape, order or metadata changes; 34 obsolete mixed caches were retained and excluded. The owner reports 60 targeted tests and 2,939 full forecast tests passed. This independent review did not inspect those study inputs or pool their test counts with the synthetic matrix. A provisional perimeter-binding concern was resolved by the exact helper: `pipeline.perimeter_samples:224-228` checks each states NPZ against the pinned perimeter manifest before reading.

Current US2024/Korean2025 assessment remains held for the two fresh admission fixes and an independent recheck, with final fits, frozen selection and comparison outputs still pending. Future 2026 registration remains NOT_READY separately: a pinned derived event catalog cannot authenticate all incidents/exclusions in a complete future raw NIROPS release, and a supplied OSF URL is not independent registration authentication. Repairing the current five bugs alone does not make that protocol ready.

The repaired C software is available for draft review in [PR 86](https://github.com/Sparkxt-0318/wildfireguardian/pull/86), with its scientific HOLD_PARTIAL retained. A remains pinned here to the independently audited f9fa03290 snapshot while the orchestrator reviews its newer enclosure/math revision. All scientific integration rows remain NOT_RUN_GATED. No heldout predictions or scores were opened, and no branch was merged or pushed by this audit.
'''
    (out / "README.md").write_text(text)
    print(json.dumps({"b_repair_checks": audit["checks"], "passed": audit["passed"], "state": b["status"]}))


def extend_scoped_admission_clearance_and_math_review():
    """Add final bounded software clearance without promoting a scientific gate."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-a", type=Path, required=True)
    parser.add_argument("--track-c", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    out = args.out_dir
    gates = json.loads((out / "GATES.json").read_text())
    audit = json.loads((out / "audit/1b-final-admission-a6d15519.json").read_text())
    assert audit["passed"] == audit["checks"] == 57
    b = gates["track_evidence"]["1B"]
    b["previous_fresh_admission_review"] = b.pop("software_review")
    b["head"] = audit["track_head"]
    b["status"] = "SCOPED_ADMISSION_REPAIRS_VERIFIED_FINAL_SELECTION_AND_NUMERICAL_EVIDENCE_PENDING"
    b["software_review"] = audit
    b["current_US2024_KR2025_admission_clearance"] = {"state": "PASS_SCOPED_SOFTWARE_ONLY", "preconditions": "Complete final checkpoint/baseline/input/source identities and selection must be frozen before assessment", "actual_heldout_predictions_or_scores_inspected": False}
    b["future_2026_blind_protocol"] = "NOT_READY_PENDING_AUTHENTICATED_RAW_RELEASE_INVENTORY_EXCLUSIONS_AND_EXTERNAL_REGISTRATION"
    inventory = json.loads((out / "radiation-review-43324736/SOURCE_INVENTORY.json").read_text())
    gates["track_evidence"]["1A"]["separate_math_review_43324736"] = inventory
    gates["open_work"][1] = "1B complete final fit/baseline/input/source selection freeze before qualified current-cohort assessment; future raw-release completeness remains separate"
    gates["commands"].append({"command": "../venv-forecast/bin/python research/next-combined/audit_1b_final_admission.py --track-b ../audit-1b --out research/next-combined/audit/1b-final-admission-a6d15519.json", "exit_code": 0, "checks": 57, "passed": 57, "scope": "Tiny synthetic positive/negative controls only; no heldout input/prediction/score read and no heavy lease"})
    (out / "GATES.json").write_text(json.dumps(gates, indent=2, allow_nan=False) + "\n")
    text = (out / "README.md").read_text()
    text = text.replace("Original five guard mechanisms repaired; 50/52 independent synthetic checks pass, with two fresh-assessment admissions open; no heldout scores inspected", "57/57 independent software admission checks pass at a6d15519; final fits, selection and numerical evidence pending; no heldout scores inspected")
    text = text.replace("| HOLD; repair and independent review required before scoring |", "| Scoped software clearance; complete final identities and selection required before qualified assessment |")
    text += '''

## Scoped B admission clearance at a6d15519

The separately pinned repair `a6d1551926ad9d830836e4b0d77ee9a7b8e9cd0d` passes all 57 independent synthetic admission checks, exit 0, in `audit/1b-final-admission-a6d15519.json`. The historical be678bb65 and 08ac32c7 failures and their producer scripts remain unchanged. The owner separately reports 21 targeted tests passed; these are not added to the independent count.

The executed-baseline control first supplies matching frozen logistic, logistic-parameter and dilation bytes and passes; changing each actual consumed file separately then refuses. A finite three-cell control reaches all 16 model outputs and independently reconstructed support before the otherwise identical MC-NaN fixture raises the expected numerical-failure error. Both `logistic_features` and `logistic_predict` are mocked consistently for the synthetic fixture channel. An unrelated early channel or model-set error therefore cannot masquerade as verification of the deeper support guard. Earlier individual reference/coordinate/label/probability/source/checkpoint/receipt checks also pass. Full scoring scripts were directly read because their subtree is deliberately excluded from the graph; pipeline and blind-tool bytes are unchanged from the independently read 08 snapshot.

This removes the two confirmed software-admission blockers for the qualified US2024/Korean2025 assessment, conditional on complete final model/baseline/source/input identities and selection being frozen first. It does not certify an actual assessment result, cache integrity for data not opened here, or the future 2026 blind protocol. No heldout data, predictions or scores were inspected, no heavy numerical lease was taken, and no fit or selection decision changed during this audit. Future release-inventory/exclusion and external-registration obligations remain NOT_READY.

## Separate independent radiation math review at 43324736

`radiation-review-43324736/` archives the independent review and its exact producer/result bytes for source `43324736fc5301a0444b01b918ef14a0372b1ec3`. The reviewer found no confirmed actionable defect in the bounded directed arithmetic/polygon and swept-hull argument under its declared domain. This is a source/proof review with fixed checks, not a machine-checked proof or universal census. The review explicitly assumes represented panel geometry and Python Decimal, exact rational and NumPy runtime behavior; it does not prove those runtimes or cover every malformed/extreme input or rounding environment.

The reviewer reports 42 fixed arithmetic sanity checks, a reproduced public counterexample with point flux 5.844308577232327e-26 and upper 5.865954053640389e-25 kW/m2, retained-table arithmetic comparisons, and four byte-identical PNG/SVG files. This readiness audit read those artifacts and checked their source hash and counterexample values against the pinned source/result; it did not rerun their scripts or count them as its own new numerical study. `SOURCE_INVENTORY.json` preserves original paths/hashes and the execution layout needed to reproduce the verbatim archived scripts.

This 433 math record is separate from the prior f9 radiation evidence row. The orchestrator's fresh 42-test suite was still queued when this record was added. The lower bound remains zero, a unit fallback remains outside the separation cone, whole-quad hull refinement need not converge, and adaptive precision has no uniform runtime/memory guarantee. An outer consumer still needs a budget and an unresolved state. Physics remains HOLD, with no new empirical accuracy, useful routing-certificate tightness, thermal threshold, law-v2 routing or operational-safety claim. All cross-track scientific experiments remain NOT_RUN_GATED.
'''
    (out / "README.md").write_text(text)
    print(json.dumps({"b_admission": audit["status"], "checks": 57, "a_math_source": inventory["source_commit"], "physics": "HOLD"}))


if __name__ == "__main__":
    main()
    extend_interim_report()
    extend_repaired_core_and_reader_audit()
    extend_reader_repair_and_preheldout_review()
    extend_b_repair_recheck()
    extend_scoped_admission_clearance_and_math_review()
