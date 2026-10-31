"""Build a requirement ledger from authenticated current-phase run outputs."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_fit_coverage as F

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parents[1]
RUN = ROOT / "forecast/runs/20261030_perimeter_trained/execution_v3"
CURRENT_COMPARISON_ATTEMPT = 6


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protocol_readiness(root, run, registry_path):
    """Report an existing complete authenticated freeze; never construct one."""
    missing = dict(protocol_status="NOT_READY", execution_status="NOT_READY_FOR_2026_EXECUTION")
    if not registry_path.is_file():
        return dict(**missing, reason="No final registry freeze")
    try:
        registry = json.loads(registry_path.read_text())
        source = registry.get("producer_source_sha256")
        if not isinstance(source, dict) or not source:
            raise ValueError("A nonempty complete source closure is required")
        selection_path = root / "research/forecast-v2/MODEL_SELECTION.json"
        selection = json.loads(selection_path.read_text())
        proof = F.saved_registry_admission(root, run, selection_path, selection, registry_path)
        if (proof.get("registry") != F.identity(root, registry_path)
                or registry.get("protocol_status") != "READY_FOR_OWNER_REGISTRATION"
                or registry.get("execution_status") != "NOT_READY_FOR_2026_EXECUTION"):
            raise ValueError("The authenticated registry does not declare the frozen protocol/execution states")
        return dict(protocol_status=registry["protocol_status"], execution_status=registry["execution_status"],
                    registry=proof["registry"], reason="Complete source/model/selection freeze authenticated; external prerequisites remain")
    except (ValueError, FileNotFoundError, KeyError, TypeError) as error:
        return dict(**missing, reason=str(error))


def farsite_readiness(record):
    """Keep scenario execution, available measurements and HOLD distinct."""
    if not record:
        return dict(status="PENDING", scores_available=False, measurement_status="NOT_REQUESTED")
    total, scored = record.get("total_historical_cases"), record.get("scored_cases")
    rows = record.get("cases", [])
    available = (type(total) is int and type(scored) is int and 0 <= scored <= total and total > 0
                 and len(rows) == total and scored == sum(r.get("status") == "SCORED_COMMON_SUBSET" for r in rows)
                 and all(r.get("cells", 0) > 0 for r in rows if r.get("status") == "SCORED_COMMON_SUBSET")
                 and bool(record.get("scores", {}).get("models")))
    measured = available and scored > 0 and record.get("scores_available") is True
    consistent = (record.get("execution_status") == "NO_NATIVE_EXECUTION_STORED_SCENARIOS_ONLY"
                  and record.get("superiority_criteria_pass") is False
                  and record.get("scores_available") == bool(measured))
    if not consistent or record.get("scores_available") and not measured:
        return dict(status="HOLD_INCONSISTENT_EVIDENCE", scores_available=False,
                    measurement_status="UNAVAILABLE_UNAUTHENTICATED_MEASUREMENT_STATE")
    return dict(status=record.get("status", "HOLD"), execution_status=record["execution_status"],
                scores_available=bool(measured), measurement_status=record.get("measurement_status", "UNAVAILABLE"),
                scored_cases=scored, total_historical_cases=total)


def comparison_evidence(receipts):
    """Separate executed frozen rows from the availability of their populations."""
    protocol = json.loads((EVIDENCE / "RUN_PROTOCOL.json").read_text())["mean_field_compare"]
    by_name = {r["job"]: r for r in receipts}
    rows, cutoffs = [], []
    for index, case in enumerate(protocol["cases"]):
        name = f"a{CURRENT_COMPARISON_ATTEMPT:02d}_compare_case{index:02d}"
        receipt = by_name.get(name)
        relative = F.comparison_case_relative(index, F.comparison_suffix(CURRENT_COMPARISON_ATTEMPT))
        output = RUN / relative / "meanfield_vs_mc.json"
        status, records = "PENDING", []
        if receipt is not None and Path(receipt["output"]) == output:
            records = json.loads(output.read_text())["rows"]
            expected = [("fixed", float(h)) for h in protocol["horizons_hours"]]
            if case["survey_hours"] is not None:
                expected.append(("survey", float(case["survey_hours"])))
            actual = [(r["horizon_kind"], float(r["hours"])) for r in records]
            if (actual != expected or any(r["event"] != case["event"] or r["cutoff"] != case["cutoff"]
                                         or r["country"] != case["country"] for r in records)):
                status = "HOLD_METADATA_MISMATCH"
            else:
                status = "COMPLETE"
        cutoffs.append(dict(id=f"1B-meanfield-cutoff-{index:02d}", status=status, case=case,
                            evidence=str(output.relative_to(ROOT)), executable="scripts/run_campaign.py compare --attempt 6"))
        for record in records:
            rows.append(dict(id=f"1B-meanfield-cutoff-{index:02d}-{record['horizon_kind']}-{record['hours']}h",
                             status=record.get("status", "UNKNOWN"), execution_status=status,
                             reference_status=record.get("reference_status"), scored_cells=record.get("cells"),
                             label_cells=record.get("label_cells"), evidence=str(output.relative_to(ROOT))))
    aggregate = by_name.get(f"a{CURRENT_COMPARISON_ATTEMPT:02d}_compare")
    complete = len(cutoffs) == 12 and all(c["status"] == "COMPLETE" for c in cutoffs)
    complete = complete and aggregate is not None and len(rows) == 66
    if complete:
        expected_receipts = [dict(path=str((EVIDENCE / "executions" / f"a{CURRENT_COMPARISON_ATTEMPT:02d}_compare_case{i:02d}.json").relative_to(ROOT)),
                                  sha256=digest(EVIDENCE / "executions" / f"a{CURRENT_COMPARISON_ATTEMPT:02d}_compare_case{i:02d}.json")) for i in range(12)]
        complete = aggregate.get("case_receipts") == expected_receipts and Path(aggregate["output"]) == RUN / "meanfield_vs_mc/meanfield_vs_mc.json"
    return bool(complete), cutoffs, rows


def main():
    receipts = []
    for path in sorted((EVIDENCE / "executions").glob("a*_*.json")):
        record = json.loads(path.read_text())
        output = Path(record["output"])
        if record["exit_code"] == 0 and output.is_file() and digest(output) == record["output_sha256"]:
            receipts.append(record)
    names = {r["job"] for r in receipts}
    comparison_complete, comparison_cutoffs, comparison_rows = comparison_evidence(receipts)
    phase_receipts, folds, finals = [], [], []
    for phase in F.current_phase_identity()["phases"]:
        try:
            _, _, _, receipt, _ = F.phase_result(ROOT, RUN, phase["variant"], phase["stage"], phase["fold"])
        except (ValueError, FileNotFoundError, KeyError):
            continue
        phase_receipts.append(receipt)
        (folds if phase["stage"] == "fold" else finals).append(receipt["job"])
    us_path, kr_path = RUN / "heldout/ASSESSMENT.json", RUN / "korean2025/ASSESSMENT.json"
    assessments = {key: json.loads(path.read_text()) if path.exists() else {} for key, path in
                   [("us2024", us_path), ("korea2025", kr_path)]}
    report_path = EVIDENCE / "RESULTS.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    qa_path = EVIDENCE / "FIGURE_QA.json"
    qa = json.loads(qa_path.read_text()) if qa_path.exists() else {}
    registry_path = EVIDENCE / "BLIND_REGISTRY.json"
    readiness = protocol_readiness(ROOT, RUN, registry_path)
    farsite_path = EVIDENCE / "FARSITE_SCORES.json"
    farsite = json.loads(farsite_path.read_text()) if farsite_path.exists() else {}
    farsite_state = farsite_readiness(farsite)
    requirements = [
        dict(id="1B-1-library", status="IMPLEMENTED_TESTED", evidence="forecast/wildfire/meanfield.py and forecast/tests/test_meanfield.py",
             limit="Multi-step closure approximation, not exact MC expectation"),
        dict(id="1B-1-12cutoffs", status="COMPLETE" if comparison_complete else "PENDING",
             expected="12cutoffs,6Korean+6US; all1/3/6/12/24h,1024trajectories; actualsurvey-endpoint checks where available",
             evidence="meanfield_vs_mc/meanfield_vs_mc.json"),
        dict(id="1B-2-development", status="COMPLETE" if len(folds) == 21 else "IN_PROGRESS",
             authenticated_fits=len(folds), expected_fits=21,
             limit="Earliest3eligible intervals per fire, bounded development subset; not full-cohort final fitting"),
        dict(id="1B-2-full-final-fits", status="COMPLETE" if len(finals) == 7 else "IN_PROGRESS",
             authenticated_fits=len(finals), expected_fits=7,
             expected="All eligible fit-fire intervals, fixed3epochs; unsupported zero-weight intervals explicitly logged"),
        dict(id="1B-3-structural-ablations", status="COMPLETE" if len(folds) == 21 and len(finals) == 7 else "IN_PROGRESS",
             expected="none,D4,D4+localwind,ellipse,burnout,burnout+spotting,mixed; sameeligibleperimeterfitpolicy"),
        dict(id="1B-4-baseline-fitting", status="COMPLETE" if "a03_baselines" in names else "PENDING",
             expected="persistence,4dilationrates,training-chosenbestdilation,weightedlogistic,c651"),
        dict(id="1B-4-heldout-scoring", status="COMPLETE" if all(r.get("status") == "COMPLETE" for r in assessments.values()) else "PENDING",
             expected="sixUS2024fires,fullrectangles,alleligibleintervals,exactcommoncohort; fourKR2025separate"),
        dict(id="1B-4-FARSITE-matched-subset", **farsite_state,
             expected="authenticateexistingdeterministicscenariosandscoreallmodelsontheirsamecellsandintervals",
             evidence="research/forecast-v2/FARSITE_SCORES.json", limit="Stored deterministic scenario subset with explicit configuration differences; not a new native campaign"),
        dict(id="1B-5-pre-registration", status=readiness["protocol_status"],
             execution_status=readiness["execution_status"], authentication=readiness,
             expected="exactcheckpointregistry,executableblindscoringclosure,frozenprimaryselection; ownerregistersOSF"),
    ]
    requirements.extend([
        dict(id="1B-2-frozen-split", status="COMPLETE" if digest(EVIDENCE / "SPLIT.json") ==
             json.loads((EVIDENCE / "RUN_PROTOCOL.json").read_text())["split_sha256"] else "HOLD",
             evidence="research/forecast-v2/SPLIT.json", executable="scripts/run_campaign.py fits"),
        dict(id="1B-2-exact-model-selection-freeze", status="COMPLETE" if (EVIDENCE / "MODEL_SELECTION.json").exists() else "PENDING",
             evidence="research/forecast-v2/MODEL_SELECTION.json", executable="scripts/run_campaign.py freeze"),
        dict(id="1B-2-complete-fit-membership", status="COMPLETE" if (EVIDENCE / "FIT_COVERAGE.json").exists() else "PENDING",
             evidence="research/forecast-v2/FIT_COVERAGE.json", executable="scripts/audit_fit_coverage.py",
             limit="Historical pure schedules are source-derived inference; new mixed IDs are actual runtime records"),
        dict(id="1B-global-spotting-wind-inputs", status="COMPLETE" if (EVIDENCE / "GLOBAL_WIND_PHASE_BINDINGS.json").exists() else "PENDING",
             evidence="research/forecast-v2/GLOBAL_WIND_PHASE_BINDINGS.json", executable="scripts/bind_global_wind_phases.py",
             limit="Availability and exact tensor/source identity only; not a quality or physical validation result"),
        dict(id="1B-data-geometry-sensitivity", status="COMPLETE" if (EVIDENCE / "GEOMETRY_AUDIT.json").exists() else "PENDING",
             evidence="research/forecast-v2/GEOMETRY_AUDIT.json", executable="scripts/audit_geometry.py",
             limit="Only cell-centre stability under the declared projected make_valid sensitivity; no physical geometry validation"),
    ])
    for variant in ("base", "d4", "d4_wind", "ellipse", "burnout", "burnout_spotting", "mixed_base"):
        current_folds = [r for r in folds if f"_{variant}" in r and
                         (variant != "base" or "mixed_base" not in r) and
                         (variant != "d4" or "d4_wind" not in r) and
                         (variant != "burnout" or "burnout_spotting" not in r)]
        final = [r for r in phase_receipts if r["output"] == str(RUN / F.intended_phase(variant, "final")["result"])]
        requirements.append(dict(id=f"1B-ablation-{variant}",
             development="COMPLETE" if len(current_folds) == 3 else "PENDING",
             status="COMPLETE" if final else "IN_PROGRESS",
             executable="scripts/run_campaign.py spotting-repair --attempt 5" if variant == "burnout_spotting" else "scripts/run_campaign.py fits --attempt 3",
             evidence=str((RUN / F.intended_phase(variant, "final")["result"]).relative_to(ROOT))))
    for cohort, result in assessments.items():
        requirements.append(dict(id="1B-assessment-" + cohort, status=result.get("status", "PENDING"),
            evidence=f"forecast/runs/20261030_perimeter_trained/execution_v3/{'heldout' if cohort == 'us2024' else 'korean2025'}/ASSESSMENT.json",
            executable=f"scripts/score_cohorts.py --cohort {cohort}",
            evidence_class="NIROPS mapped extent" if cohort == "us2024" else "reconstructed arrival, secondary only"))
    for baseline in ("persistence", "dilation_1", "dilation_2", "dilation_4", "dilation_8", "dilation_best", "logistic", "c651_mc", "c651_mf"):
        requirements.append(dict(id="1B-baseline-assessment-" + baseline,
            status=assessments["us2024"].get("status", "PENDING"), executable="scripts/score_cohorts.py --cohort us2024",
            evidence="forecast/runs/20261030_perimeter_trained/execution_v3/heldout/ASSESSMENT.json"))
    for metric in ("Brier", "BSS-persistence", "BSS-best-dilation", "AP", "ROC-AUC", "fixed-bin-ECE", "clipped-NLL",
                   "per-fire-values", "whole-fire-bootstrap", "lowest-bin-calibration"):
        requirements.append(dict(id="1B-metric-" + metric,
            status=("COMPLETE" if assessments["us2024"].get("status") == "COMPLETE" else "DESCRIPTIVE_SUBSET_HOLD")
            if report.get("heldout", {}).get("models") else
            "UNAVAILABLE_NO_SUPPORTED_ENTRIES" if "heldout" in report else "PENDING",
            executable="scripts/report.py", evidence="research/forecast-v2/RESULTS.json"))
    for number, name in enumerate(["reliability_all_models", "per_fire_brier_paired", "ablation_forest_plot",
                                    "meanfield_vs_mc_rmse_by_horizon", "example_forecast_vs_perimeter"], 1):
        stem = f"fig{number:02d}_{name}"
        paths = [EVIDENCE / "figures" / (stem + extension) for extension in (".png", ".svg")]
        figure = report.get("figure_evidence", {}).get(stem, {})
        authenticated = figure and all(p.is_file() and digest(p) == figure.get("files_sha256", {}).get(p.suffix[1:]) for p in paths)
        reviewed = qa.get("figures", {}).get(stem, {})
        qa_current = authenticated and reviewed.get("status") == "PASS" and reviewed.get("files_sha256") == figure.get("files_sha256")
        requirements.append(dict(id=stem, status=figure.get("status") if authenticated else "PENDING",
                                 visual_qa="PASS" if qa_current else "PENDING_SEPARATE_VISUAL_RECEIPT", metric_data_available=figure.get("metric_data_available", False),
                                 evidence=[str(p.relative_to(ROOT)) for p in paths]))
    requirements.extend(comparison_cutoffs)
    requirements.extend(comparison_rows)
    result = dict(current_phase=F.current_phase_identity(), schema="wfg.forecast-v2.requirements/1", evidence_class="current real-input executions, earlier attempts excluded from primary totals",
                  authenticated_development_fits=len(folds), authenticated_final_fits=len(finals),
                  promotion_authority=False, comparison_execution_complete=comparison_complete,
                  receipts=[dict(job=r["job"], output=r["output"], sha256=r["output_sha256"]) for r in receipts],
                  requirements=requirements)
    (EVIDENCE / "REQUIREMENTS_STATUS.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(development_fits=len(folds), final_fits=len(finals), pending=sum(r["status"] != "COMPLETE" for r in requirements))))


if __name__ == "__main__":
    main()
