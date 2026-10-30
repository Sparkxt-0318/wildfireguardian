"""Build a requirement ledger from authenticated current-phase run outputs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parents[1]
RUN = ROOT / "forecast/runs/20261030_perimeter_trained/execution_v3"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    receipts = []
    for path in sorted((EVIDENCE / "executions").glob("a0[34]_*.json")):
        record = json.loads(path.read_text())
        output = Path(record["output"])
        if record["exit_code"] == 0 and output.is_file() and digest(output) == record["output_sha256"]:
            receipts.append(record)
    names = {r["job"] for r in receipts}
    active_path = RUN / "ACTIVE_PHASE.json"
    active_outputs = {str(RUN / p) for p in json.loads(active_path.read_text())["active_folds"]} if active_path.exists() else None
    folds = sorted(r["job"] for r in receipts if "_fold_" in r["job"]
                   and (active_outputs is None or r["output"] in active_outputs))
    finals = sorted(n for n in names if "_final_" in n)
    us_path, kr_path = RUN / "heldout/ASSESSMENT.json", RUN / "korean2025/ASSESSMENT.json"
    assessments = {key: json.loads(path.read_text()) if path.exists() else {} for key, path in
                   [("us2024", us_path), ("korea2025", kr_path)]}
    report_path = EVIDENCE / "RESULTS.json"
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    requirements = [
        dict(id="1B-1-library", status="IMPLEMENTED_TESTED", evidence="forecast/wildfire/meanfield.py and forecast/tests/test_meanfield.py",
             limit="Multi-step closure approximation, not exact MC expectation"),
        dict(id="1B-1-12cutoffs", status="COMPLETE" if names & {"a03_compare", "a04_compare"} else "PENDING",
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
        dict(id="1B-4-FARSITE-matched-subset", status="PENDING",
             expected="authenticateexistingdeterministicscenariosandscoreallmodelsontheirsamecellsandintervals"),
        dict(id="1B-5-pre-registration", status="NOT_READY",
             expected="exactcheckpointregistry,executableblindscoringclosure,frozenprimaryselection; ownerregistersOSF"),
    ]
    requirements.extend([
        dict(id="1B-2-frozen-split", status="COMPLETE" if digest(EVIDENCE / "SPLIT.json") ==
             json.loads((EVIDENCE / "RUN_PROTOCOL.json").read_text())["split_sha256"] else "HOLD",
             evidence="research/forecast-v2/SPLIT.json", executable="scripts/run_campaign.py fits"),
        dict(id="1B-2-exact-model-selection-freeze", status="COMPLETE" if (EVIDENCE / "MODEL_SELECTION.json").exists() else "PENDING",
             evidence="research/forecast-v2/MODEL_SELECTION.json", executable="scripts/run_campaign.py fits"),
        dict(id="1B-data-geometry-sensitivity", status="COMPLETE" if (EVIDENCE / "GEOMETRY_AUDIT.json").exists() else "PENDING",
             evidence="research/forecast-v2/GEOMETRY_AUDIT.json", executable="scripts/audit_geometry.py",
             limit="Only cell-centre stability under the declared projected make_valid sensitivity; no physical geometry validation"),
    ])
    for variant in ("base", "d4", "d4_wind", "ellipse", "burnout", "burnout_spotting", "mixed_base"):
        current_folds = [r for r in folds if f"_{variant}" in r and
                         (variant != "base" or "mixed_base" not in r) and
                         (variant != "d4" or "d4_wind" not in r) and
                         (variant != "burnout" or "burnout_spotting" not in r)]
        final = f"a03_final_{variant}"
        requirements.append(dict(id=f"1B-ablation-{variant}",
             development="COMPLETE" if len(current_folds) == 3 else "PENDING",
             status="COMPLETE" if final in names else "IN_PROGRESS", executable="scripts/run_campaign.py fits",
             evidence=f"forecast/runs/20261030_perimeter_trained/execution_v3/final/{variant}_seed0/result.json"))
    for cohort, result in assessments.items():
        requirements.append(dict(id="1B-assessment-" + cohort, status=result.get("status", "PENDING"),
            evidence=f"forecast/runs/20261030_perimeter_trained/execution_v3/{'heldout' if cohort == 'us2024' else 'korean2025'}/ASSESSMENT.json",
            executable=f"scripts/score_cohorts.py --cohort {cohort}",
            evidence_class="NIROPS mapped extent" if cohort == "us2024" else "reconstructed arrival, secondary only"))
    for metric in ("Brier", "BSS-persistence", "BSS-best-dilation", "AP", "ROC-AUC", "fixed-bin-ECE", "clipped-NLL",
                   "per-fire-values", "whole-fire-bootstrap", "lowest-bin-calibration"):
        requirements.append(dict(id="1B-metric-" + metric,
            status="COMPLETE" if assessments["us2024"].get("status") == "COMPLETE" and
            "heldout" in report else "PENDING",
            executable="scripts/report.py", evidence="research/forecast-v2/RESULTS.json"))
    for number, name in enumerate(["reliability_all_models", "per_fire_brier_paired", "ablation_forest_plot",
                                    "meanfield_vs_mc_rmse_by_horizon", "example_forecast_vs_perimeter"], 1):
        stem = f"fig{number:02d}_{name}"
        paths = [EVIDENCE / "figures" / (stem + extension) for extension in (".png", ".svg")]
        requirements.append(dict(id=stem, status="GENERATED_PENDING_VISUAL_QA" if all(p.exists() for p in paths) else "PENDING",
                                 evidence=[str(p.relative_to(ROOT)) for p in paths]))
    result = dict(schema="wfg.forecast-v2.requirements/1", evidence_class="current real-input executions, earlier attempts excluded from primary totals",
                  authenticated_development_fits=len(folds), authenticated_final_fits=len(finals),
                  receipts=[dict(job=r["job"], output=r["output"], sha256=r["output_sha256"]) for r in receipts],
                  requirements=requirements)
    (EVIDENCE / "REQUIREMENTS_STATUS.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(dict(development_fits=len(folds), final_fits=len(finals), pending=sum(r["status"] != "COMPLETE" for r in requirements))))


if __name__ == "__main__":
    main()
