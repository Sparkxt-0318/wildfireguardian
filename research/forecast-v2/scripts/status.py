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
    for path in sorted((EVIDENCE / "executions").glob("a03_*.json")):
        record = json.loads(path.read_text())
        output = Path(record["output"])
        if record["exit_code"] == 0 and output.is_file() and digest(output) == record["output_sha256"]:
            receipts.append(record)
    names = {r["job"] for r in receipts}
    folds = sorted(n for n in names if "_fold_" in n)
    finals = sorted(n for n in names if "_final_" in n)
    requirements = [
        dict(id="1B-1-library", status="IMPLEMENTED_TESTED", evidence="forecast/wildfire/meanfield.py and forecast/tests/test_meanfield.py",
             limit="Multi-step closure approximation, not exact MC expectation"),
        dict(id="1B-1-12cutoffs", status="COMPLETE" if "a03_compare" in names else "PENDING",
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
        dict(id="1B-4-heldout-scoring", status="COMPLETE" if "a03_heldout" in names else "PENDING",
             expected="sixUS2024fires,fullrectangles,alleligibleintervals,exactcommoncohort; fourKR2025separate"),
        dict(id="1B-4-FARSITE-matched-subset", status="PENDING",
             expected="authenticateexistingdeterministicscenariosandscoreallmodelsontheirsamecellsandintervals"),
        dict(id="1B-5-pre-registration", status="NOT_READY",
             expected="exactcheckpointregistry,executableblindscoringclosure,frozenprimaryselection; ownerregistersOSF"),
    ]
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
