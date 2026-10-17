"""Record saved continuation evidence without rerunning any evaluation.

Run from a committed export, after copying the sealed JSON reports into --bundle.
Held-out reports are read only; this script never generates or scores clips.
"""
from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path

from wfglink import PROJECT_ROOT
from wfglink.config import load_config
from wfglink.provenance import git_state, record_number, sha256_file
from wfglink.validate.metrics import coverage as coverage_interval

SCRIPT = "scripts/record_continuation.py"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle", required=True)
    args = ap.parse_args()
    if git_state()["git_dirty"]:
        ap.error("recording requires committed source")
    bundle = PROJECT_ROOT / args.bundle
    names = ["c5_baseline_labels", "c5_multiscale_labels", "hires_eval", "coverage_eval",
             "mismatch_eval", "ember_report", "stride_report", "final_tests", "initial_tests",
             "phone_fullrate_comparison"]
    paths = {name: bundle / f"{name}.json" for name in names}
    reports = {name: json.loads(path.read_text()) for name, path in paths.items()}
    for suite, expected in (("mismatch", 60), ("coverage", 200)):
        rows = reports[f"{suite}_eval"]["clips"]
        if len(rows) != expected or any("error" in row for row in rows):
            ap.error(f"{suite} report is incomplete; do not record partial headline results")
    coverage = reports["coverage_eval"]["cases"]["base"]["cpc_coverage"]
    if coverage["n"] != 200:
        ap.error("coverage denominator must contain every independent clip")
    for name in ("ember_report", "stride_report"):
        if reports[name].get("git_dirty") is not False:
            ap.error(f"{name} must be a clean committed run")
    comparison = reports["phone_fullrate_comparison"]
    if not all(comparison[k] for k in ("all_histories_and_legacy_tracks_exact",
                                       "quality_speed_ruler_reports_exact", "exact_speed_rows_match")):
        ap.error("strict phone non-regression comparison did not pass")
    for relpath, expected in comparison["source_sha256"].items():
        if sha256_file(PROJECT_ROOT / relpath) != expected:
            ap.error(f"phone comparison describes another source: {relpath}")
    cfg = load_config()

    def put(key, value, unit, description, name):
        if value is None:
            return
        record_number(f"continuation.{key}", round(value, 6) if isinstance(value, float) else value,
                      unit, description, script=SCRIPT, config=cfg,
                      config_path="configs/default.yaml", inputs={"saved_report": paths[name]})

    for phase, name in (("before", "c5_baseline_labels"), ("after", "c5_multiscale_labels")):
        report = reports[name]
        for key in ("tp", "fp", "fn", "frames", "tiles_scored"):
            put(f"C5.{phase}.{key}", report[key], "count", f"C5 agent-label {phase} {key}", name)
        for metric in ("precision", "recall", "f1"):
            for key, value in (("value", report[metric]["value"]),
                               ("lo", report[metric]["ci"][0]), ("hi", report[metric]["ci"][1])):
                put(f"C5.{phase}.{metric}.{key}", value, "fraction",
                    f"C5 {phase} {metric} {key}; frame-bootstrap agent-label development evidence", name)
        put(f"C5.{phase}.ci_percent", report["level"] * 100, "percent", "Frame-bootstrap interval level", name)
    for key, value in coverage.items():
        put(f"coverage.{key}", value, "count" if key in ("k", "n") else "fraction",
            f"Saved independent-clip count-interval coverage {key}; lo/hi are Clopper-Pearson bounds", "coverage_eval")
    put("coverage.goal", 0.9, "fraction", "Predeclared point-coverage goal from PLAN section 4", "coverage_eval")
    put("coverage.ci_percent", 100 * inspect.signature(coverage_interval).parameters["ci"].default,
        "percent", "Confidence level of the saved exact binomial coverage interval", "coverage_eval")
    for name in ("mismatch_eval", "coverage_eval"):
        suite = name.removesuffix("_eval")
        put(f"{suite}.clips", len(reports[name]["clips"]), "count", "Completed final held-out clips", name)
        put(f"{suite}.errors", sum("error" in r for r in reports[name]["clips"]), "count", "Final held-out clip errors", name)
    for case, row in reports["hires_eval"]["cases"].items():
        for key in ("f1", "precision", "recall", "exposure_ok"):
            put(f"hires.{case}.{key}", row[key], "fraction", f"High-resolution verification {case} {key}", "hires_eval")
    ember = reports["ember_report"]["synthetic"]
    for key in ("precision", "recall", "recall_after_acquisition", "mota", "id_switches_per_phone_per_min",
                "id_switches_persistent_per_phone_per_min", "static_light_tracks_per_min"):
        put(f"ember.{key}", ember["pooled"][key], "per phone minute" if "switches" in key else
            "per minute" if "per_min" in key else "fraction", f"Phone tuning-set pooled {key}", "ember_report")
    put("ember.speed_median_rel_err", ember["speed"]["standing"]["median_abs_rel_err"], "fraction",
        "Standing-distance trailing-window speed error, phone tuning set", "ember_report")
    exact = comparison["exact_speed_summaries"]["cadence"]["2.0"]
    put("ember.speed_median_percent", 100 * exact["median_abs_rel_err"], "percent",
        "Exact standing-speed cohort median from strict full-rate history comparison", "phone_fullrate_comparison")
    for key, unit in (("seconds", "s"), ("max_tracks", "count")):
        put(f"stride.{key}", reports["stride_report"][key], unit, f"Uncapped replay {key}", "stride_report")
    for stride, row in reports["stride_report"]["strides"].items():
        for key in ("frames", "over_three_frames", "over_three_fraction", "lamp_frames"):
            put(f"stride.{stride}.{key}", row[key], "fraction" if key.endswith("fraction") else "count",
                f"Uncapped phone replay stride {stride}, {key}", "stride_report")
    for name in ("initial_tests", "final_tests"):
        for key in ("passed", "failed", "skipped"):
            put(f"{name}.{key}", reports[name][key], "count", f"Committed complete test run {key}", name)
    print("recorded saved continuation evidence; no evaluations rerun")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
