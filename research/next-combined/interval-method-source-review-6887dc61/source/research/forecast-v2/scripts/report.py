"""Tables, RESULTS.json and figures for track 1B from a pipeline run directory.

Usage: python research/forecast-v2/scripts/report.py --run RUN_DIR --out research/forecast-v2 [--label FIXTURE]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parent))
import audit_fit_coverage as F
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[3] / "forecast"))
from wildfire import baselines as B  # noqa: E402

# Okabe-Ito without yellow, which is too faint on white.
OKABE_ITO = ["#000000", "#E69F00", "#56B4E9", "#009E73", "#0072B2", "#D55E00", "#CC79A7"]
FINE_BINS = np.array([0, 1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1.0])
SINGLE, DOUBLE = 3.5, 7.2

# The completed a06 producer is immutable, even after the reviewed auditor repair.
COMPARISON_PROTOCOL_SHA256 = "c2dce7f7724b1bda6d71391b690904067e6ad46c808276c34f72fd4a1b1e8243"
COMPARISON_SOURCE_SHA256 = "eb51e5ff3a6e7b871a266b61791f0c2b3ec5efd00c99d0f299b3050fbec62d17"
COMPARISON_AUDITOR_SHA256 = "1753cf31b21be093e13d61a107e407cf41542e9ec6dbe4c8ced924f5a5320cf4"
COMPARISON_CURRENT_AUDITORS = {COMPARISON_AUDITOR_SHA256,
    "65a7917868b70e00881722bda8ab2af71688fe78bf88128fad0376537f1d6536"}
COMPARISON_CHECKPOINT_SHA256 = "c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843"
COMPARISON_COMMAND_SHA256 = "3d9142ef61779cb5aeccd93c5eaf7c98e83dc40ec5c9f8bc435e6a78ac7e8803"
COMPARISON_HOURS = (1, 3, 6, 12, 24)


def style():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7, "axes.titlesize": 7, "axes.labelsize": 7,
                         "legend.fontsize": 6, "xtick.labelsize": 6, "ytick.labelsize": 6,
                         "axes.spines.top": False, "axes.spines.right": False, "figure.facecolor": "white",
                         "savefig.facecolor": "white", "axes.facecolor": "white"})
    return plt


def save(fig, out: Path, name: str):
    out.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(out / f"{name}.{ext}", dpi=300)


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _comparison_json(path):
    def invalid(value):
        raise ValueError(f"Comparison JSON contains nonfinite {value}")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Comparison JSON contains duplicate object keys")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), parse_constant=invalid, object_pairs_hook=unique)


def _comparison_sources():
    """Authenticate the entire original producer, without opening scientific inputs."""
    evidence = REPO / "research/forecast-v2"
    paths = sorted(p for p in (REPO / "forecast/wildfire").rglob("*")
                   if p.is_file() and p.suffix in (".py", ".json"))
    paths += [evidence / "scripts" / name for name in
              ("run_campaign.py", "pipeline.py", "audit_fit_coverage.py")]
    paths += [evidence / "RUN_PROTOCOL.json", evidence / "RUN_PROTOCOL_EXTENSION_2.json"]
    sources = {str(p.relative_to(REPO)): sha256(p) for p in paths}
    auditor = "research/forecast-v2/scripts/audit_fit_coverage.py"
    current = sources[auditor]
    if current not in COMPARISON_CURRENT_AUDITORS:
        raise ValueError("Comparison requires a reviewed current auditor and exact original F1753")
    original = F._source_blob(REPO, auditor, COMPARISON_AUDITOR_SHA256).encode("utf-8")
    if hashlib.sha256(original).hexdigest() != COMPARISON_AUDITOR_SHA256:
        raise ValueError("Comparison original auditor bytes changed")
    sources[auditor] = COMPARISON_AUDITOR_SHA256
    digest = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != COMPARISON_SOURCE_SHA256:
        raise ValueError("Comparison complete original producer source closure changed")
    protocol = evidence / "RUN_PROTOCOL.json"
    if sha256(protocol) != COMPARISON_PROTOCOL_SHA256:
        raise ValueError("Comparison frozen protocol bytes changed")
    return sources, current, _comparison_json(protocol)


def _comparison_metrics(row, reference):
    """Check saved support/absence semantics, without claiming an array recomputation."""
    def count(name, upper=None):
        value = row[name]
        if type(value) is not int or value < 0 or upper is not None and value > upper:
            raise ValueError(f"Comparison {name} must be an exact supported cell count")
        return value

    def number(name, upper=None):
        value = row[name]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or upper is not None and value > upper:
            raise ValueError(f"Comparison {name} must be finite and within its declared range")
        return value

    cells = count("cells")
    active = count("active_cells", cells)
    if row["status"] != ("COMPARABLE" if cells else "UNAVAILABLE_SHARED_SUPPORT"):
        raise ValueError("Comparison status differs from its shared support")
    all_metrics = ("rmse_all", "mean_mc", "mean_mf", "expected_new_cells_mc",
                   "expected_new_cells_mf", "max_abs_difference")
    if not cells:
        if active or any(row[key] is not None for key in (*all_metrics, "rmse_active")):
            raise ValueError("Unavailable comparison support must retain null metrics, never zero error")
    else:
        for key in all_metrics:
            number(key, cells if key.startswith("expected_new_cells") else 1)
        if active:
            number("rmse_active", 1)
        elif row["rmse_active"] is not None:
            raise ValueError("No probability-active cells means active RMSE is unavailable")
    for key in ("mc_seconds", "mf_seconds"):
        number(key)
    if reference:
        label_cells = count("label_cells", cells)
        if reference == "US" and label_cells != cells:
            raise ValueError("US next-survey reference must retain the full declared shared support")
        if row["reference_status"] != ("SCORED" if label_cells else "UNAVAILABLE_REFERENCE_SUPPORT"):
            raise ValueError("Comparison reference status differs from its supported label count")
        if label_cells:
            count("positives", label_cells)
            for key in ("brier_mc", "brier_mf", "brier_persistence"):
                number(key, 1)
            if not math.isclose(row["brier_persistence"], row["positives"] / label_cells, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("Comparison persistence Brier differs from saved binary label counts")
        elif any(row[key] is not None for key in ("positives", "brier_mc", "brier_mf", "brier_persistence")):
            raise ValueError("Unavailable comparison reference must retain null scores")


def _comparison_rows(rows, case, settings):
    base = {"country", "event", "cutoff", "horizon_kind", "hours", "mc_seconds", "mf_seconds", "n_samples", "seed",
            "timing_scope", "status", "cells", "active_cells", "rmse_all", "rmse_active", "mean_mc", "mean_mf",
            "expected_new_cells_mc", "expected_new_cells_mf", "max_abs_difference"}
    reference_keys = {"reference_status", "label_cells", "positives", "brier_mc", "brier_mf", "brier_persistence", "label_kind"}
    horizons = [("fixed", h) for h in COMPARISON_HOURS]
    if case["country"] == "US":
        horizons.append(("survey", case["survey_hours"]))
    if not isinstance(rows, list) or len(rows) != len(horizons):
        raise ValueError("Every comparison cutoff requires five fixed horizons and its exact US survey endpoint")
    for row, (kind, hours) in zip(rows, horizons):
        reference = case["country"] if kind == "survey" or case["country"] == "KR" else None
        if not isinstance(row, dict) or row.keys() != base | (reference_keys if reference else set()):
            raise ValueError("Comparison row fields differ from the fixed producer schema")
        if (any(row[key] != case[key] for key in ("country", "event", "cutoff"))
                or row["horizon_kind"] != kind or type(row["hours"]) not in (int, float) or row["hours"] != hours):
            raise ValueError("Comparison ordered cutoff/horizon identities differ from the frozen protocol")
        if (type(row["n_samples"]) is not int or row["n_samples"] != settings["n_samples"]
                or type(row["seed"]) is not int or row["seed"] != settings["seed"]):
            raise ValueError("Comparison must retain c651, 1,024 trajectories and seed0")
        timing = "one joint 24h call, shared across five horizon rows" if kind == "fixed" else "one fractional survey-endpoint call"
        if row["timing_scope"] != timing:
            raise ValueError("Comparison timing scope changed")
        if reference and row["label_kind"] != ("kriged reconstruction (not observed)" if reference == "KR"
                                                else "NIROPS mapped extent at the next survey"):
            raise ValueError("Comparison reference kind changed")
        _comparison_metrics(row, reference)
    if any(row[key] != rows[0][key] for row in rows[:5] for key in ("mc_seconds", "mf_seconds")):
        raise ValueError("Five fixed horizons must share each cutoff's single joint24h call timings")


def _comparison_csv(path, rows):
    frame = pd.read_csv(path, float_precision="round_trip")
    expected = pd.DataFrame(rows)
    if list(frame.columns) != list(expected.columns) or len(frame) != len(expected):
        raise ValueError("Comparison CSV columns/row count differ from authenticated JSON")
    for name in expected.columns:
        for actual, wanted in zip(frame[name], expected[name]):
            if pd.isna(actual) and pd.isna(wanted):
                continue
            if pd.isna(actual) or pd.isna(wanted) or actual != wanted:
                raise ValueError("Comparison CSV values or ordered rows differ from authenticated JSON")
    return frame


def comparison_support(frame):
    """Available cutoff and unique catalog-event counts for every fixed position."""
    fixed = frame[frame.horizon_kind == "fixed"]
    rows = []
    for country, group in fixed.groupby("country", sort=True):
        cutoffs = group[["event", "cutoff"]].drop_duplicates()
        for hours in COMPARISON_HOURS:
            at = group[group.hours == hours]
            active = at[at.rmse_active.notna()]
            known = at[at.cells > 0]
            rows.append(dict(country=country, hours=hours, available_cutoffs=len(active),
                declared_cutoffs=len(cutoffs), available_catalog_events=active.event.nunique(),
                declared_catalog_events=cutoffs.event.nunique(), known_support_cutoffs=len(known),
                known_support_catalog_events=known.event.nunique(),
                status="AVAILABLE" if len(active) else "UNAVAILABLE_ACTIVE_SUPPORT"))
    return rows


def load_comparison(run):
    """Authenticate completed a06 summaries; unsaved numerical fields are not replayed."""
    run = Path(run).resolve()
    sources, current_auditor, protocol = _comparison_sources()
    settings = protocol["mean_field_compare"]
    cases = settings["cases"]
    if (len(cases) != 12 or [c["country"] for c in cases] != ["KR"] * 6 + ["US"] * 6
            or settings["horizons_hours"] != list(COMPARISON_HOURS) or settings["n_samples"] != 1024
            or settings["seed"] != 0 or settings["trajectory_batch_size"] != 32):
        raise ValueError("Comparison requires the complete frozen twelve-case/66-row prescription")
    root = REPO / "research/forecast-v2"
    artifacts = {}

    def pin(path):
        path = Path(path)
        artifacts[str(path.resolve().relative_to(REPO.resolve()))] = sha256(path)
        return artifacts[str(path.resolve().relative_to(REPO.resolve()))]

    def receipt(path, output, name):
        obj = _comparison_json(path)
        if (obj.get("job") != name or type(obj.get("exit_code")) is not int or obj["exit_code"] != 0
                or Path(obj.get("output", "")).resolve() != output.resolve()
                or obj.get("output_sha256") != pin(output) or obj.get("source_sha256") != sources):
            raise ValueError("Comparison receipt/output/complete source closure authentication failed")
        pin(path)
        return obj

    destination = run / "meanfield_vs_mc/meanfield_vs_mc.json"
    aggregate_receipt = root / "executions/a06_compare.json"
    final = receipt(aggregate_receipt, destination, "a06_compare")
    aggregate = _comparison_json(destination)
    if (aggregate.keys() != {"rows", "checkpoint_sha256", "case_receipts", "host", "timing"}
            or aggregate["checkpoint_sha256"] != COMPARISON_CHECKPOINT_SHA256
            or aggregate["timing"] != "Each fixed-horizon group shares one joint24h MC and MF call"):
        raise ValueError("Comparison aggregate model or schema differs from the frozen producer")
    all_rows, pins, joint_calls, survey_calls = [], [], [], []
    last_host = None
    for index, case in enumerate(cases):
        name = f"a06_compare_case{index:02d}"
        path = root / f"executions/{name}.json"
        output = run / f"meanfield_vs_mc/case_{index:02d}_a06/meanfield_vs_mc.json"
        rec = receipt(path, output, name)
        log = path.with_suffix(".log")
        if rec.get("log_sha256") != pin(log) or rec.get("data_manifest_sha256") != protocol["data_manifest_sha256"]:
            raise ValueError("Comparison case log/input-manifest identity changed")
        command = rec.get("command")
        if not isinstance(command, list) or not all(type(token) is str for token in command):
            raise ValueError("Comparison historical argv must be a complete list of strings")
        positions = [i for i, token in enumerate(command) if token == "--compare-case-index"]
        if (len(positions) != 1 or positions[0] + 1 >= len(command)
                or command[positions[0] + 1] != str(index)):
            raise ValueError("Comparison historical argv requires its unique exact standalone case index")
        normalized = command.copy()
        normalized[positions[0] + 1] = "0"
        command_sha = hashlib.sha256(json.dumps(normalized, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
        if command_sha != COMPARISON_COMMAND_SHA256:
            raise ValueError("Comparison complete historical argv family changed")
        result = _comparison_json(output)
        if result.keys() != {"rows", "host", "checkpoint_sha256"} or result["checkpoint_sha256"] != COMPARISON_CHECKPOINT_SHA256:
            raise ValueError("Comparison case checkpoint or schema changed")
        _comparison_rows(result["rows"], case, settings)
        csv = output.with_suffix(".csv")
        _comparison_csv(csv, result["rows"])
        pin(csv)
        pins.append(dict(path=str(path.relative_to(REPO)), sha256=pin(path)))
        all_rows.extend(result["rows"])
        identity = {key: case[key] for key in ("country", "event", "cutoff")}
        joint_calls.append(dict(**identity, **{key: result["rows"][0][key] for key in ("mc_seconds", "mf_seconds")}))
        if case["country"] == "US":
            survey_calls.append(dict(**identity, hours=case["survey_hours"],
                **{key: result["rows"][-1][key] for key in ("mc_seconds", "mf_seconds")}))
        last_host = result["host"]
    if (len(all_rows) != 66
            or json.dumps(aggregate["rows"], sort_keys=True, separators=(",", ":")) != json.dumps(all_rows, sort_keys=True, separators=(",", ":"))
            or aggregate["case_receipts"] != pins
            or final.get("case_receipts") != pins or aggregate["host"] != last_host):
        raise ValueError("Comparison aggregate must equal all twelve ordered receipt-bound case outputs")
    frame = _comparison_csv(destination.with_suffix(".csv"), all_rows)
    pin(destination.with_suffix(".csv"))
    pin(root / "RUN_PROTOCOL.json")
    aggregate.update(execution_complete=True, execution_status="COMPLETE_AUTHENTICATED_12_CASES_66_ROWS",
        metric_data_available=bool(frame.rmse_all.notna().any()),
        metric_availability=dict(known_support_rmse=bool(frame.rmse_all.notna().any()),
            fixed_horizon_active_rmse=bool(frame.loc[frame.horizon_kind == "fixed", "rmse_active"].notna().any()),
            reference_brier=bool(frame.brier_mc.notna().any())),
        support_by_horizon=comparison_support(frame),
        authentication=dict(artifacts_sha256=artifacts, producer_source_sha256=sources,
            producer_source_closure_sha256=COMPARISON_SOURCE_SHA256, current_auditor_sha256=current_auditor,
            original_auditor_sha256=COMPARISON_AUDITOR_SHA256,
            normalized_historical_command_sha256=COMPARISON_COMMAND_SHA256,
            limit="Authenticates saved identities and summary consistency; unsaved arrays, support masks and numerical values are not independently recomputed"),
        runtime=dict(joint24h=dict(cutoffs=joint_calls, mc_calls=len(joint_calls), mf_calls=len(joint_calls),
            mc_seconds=sum(r["mc_seconds"] for r in joint_calls), mf_seconds=sum(r["mf_seconds"] for r in joint_calls),
            mc_path="public predict_cumulative; cache_environment_kernels=False; each total shared across five horizons"),
            survey_endpoint=dict(cutoffs=survey_calls, mc_calls=len(survey_calls), mf_calls=len(survey_calls),
                mc_seconds=sum(r["mc_seconds"] for r in survey_calls), mf_seconds=sum(r["mf_seconds"] for r in survey_calls),
                mc_path="private fractional-endpoint simulate; cache_environment_kernels=True"),
            scope="Host-specific measured calls; preparation/model load/job wait excluded. Repeated cutoff timings are not independent horizon runtimes."),
        interpretation="Model agreement on known initially-unburned support, not physical validation. Cutoffs repeat catalog fires. KR Brier uses reconstruction; US Brier only the observed next-survey endpoint.")
    return frame, aggregate


def load_assessment(directory):
    """Load only the exact receipt-bound per-fire files, including honest HOLD."""
    receipt = json.loads((directory / "ASSESSMENT.json").read_text())
    if receipt.get("receipt_version") != "wfg.forecast-assessment/2" or receipt.get("status") not in ("COMPLETE", "HOLD"):
        raise ValueError("Current source-bound assessment receipts are required for reporting")
    frozen = json.loads((directory / "FROZEN_ASSESSMENT.json").read_text())
    F.validate_phase_identity(frozen.get("current_phase"))
    contract = frozen.get("spotting_source_contract", {})
    if contract != F.spotting_source_contract(REPO, contract.get("source_sha256", {})):
        raise ValueError("Assessment requires the corrected immutable spotting source phase")
    if sha256(directory / "FROZEN_ASSESSMENT.json") != receipt["frozen_sha256"]:
        raise ValueError("Assessment source/checkpoint/input identity changed")
    listed = receipt["per_fire_files"]
    if {p.name for p in directory.glob("*.npz")} != listed.keys():
        raise ValueError("Unlisted or missing per-fire score files cannot enter a report")
    for name, expected in listed.items():
        if sha256(directory / name) != expected:
            raise ValueError("Receipt-bound per-fire score bytes changed")
    if receipt["status"] == "COMPLETE" and receipt.get("failed_or_unavailable"):
        raise ValueError("A complete assessment cannot contain failed or unavailable outcomes")
    if not listed:
        if receipt["status"] != "HOLD" or not receipt.get("failed_or_unavailable"):
            raise ValueError("An empty assessment must explicitly retain its HOLD outcomes")
        return None, receipt
    entries = B.load_scored_entries(directory)
    if not len(entries["y"]):
        raise ValueError("Authenticated scored files must contain actual entries")
    if receipt["status"] == "COMPLETE" and set(entries["fire"]) != set(receipt["events"]):
        raise ValueError("A complete assessment must score every declared fire")
    return entries, receipt



def load_report_inputs(run, assessment):
    """Bind report settings to the scorer's exact frozen assessment metadata."""
    inputs = json.loads((run / "report_inputs.json").read_text())
    frozen = json.loads((run / "heldout/FROZEN_ASSESSMENT.json").read_text())
    if (inputs.get("frozen_assessment_sha256") != assessment["frozen_sha256"]
            or type(inputs.get("n_samples")) is not int or inputs["n_samples"] <= 1
            or inputs["n_samples"] != frozen["trajectories"] or inputs.get("seed") != frozen["seed"]
            or inputs.get("data_manifest_sha256") != frozen["extraction_manifest_sha256"]):
        raise ValueError("Report input metadata differs from the source-authenticated assessment settings")
    return inputs


def assessment_scores(entries, assessment):
    """Separate absence and descriptive subsets from complete-cohort statistics."""
    if entries is None:
        scored = dict(models={}, paired={}, fires=[], entries=0, positives=None,
                      metric_status="UNAVAILABLE_NO_SCORED_ENTRIES",
                      metric_unavailability_reason="No authenticated common-support entries were scored")
    else:
        scored = detailed_scores(entries)
        scored["metric_status"] = ("COMPLETE_DECLARED_COHORT" if assessment["status"] == "COMPLETE"
                                    else "DESCRIPTIVE_SUPPORTED_SUBSET")
    scored.update(assessment_status=assessment["status"], unscored_outcomes=assessment["failed_or_unavailable"],
                  declared_fires=assessment["events"], attempted_cases=len(assessment.get("cases", [])),
                  case_outcome_counts={status: sum(row.get("status") == status for row in assessment.get("cases", []))
                                       for status in ("SCORED", "UNAVAILABLE", "FAILED")},
                  statistic_scope=("complete declared cohort" if assessment["status"] == "COMPLETE" else
                      "descriptive supported subset; primary gate remains closed" if entries is not None else
                      "no scored subset; metrics unavailable and primary gate remains closed"))
    return scored


def retrospective_gate(scored, primary, assessment, selection_present):
    references = ("persistence", "dilation_best")
    names = [name for name in (primary, *references) if name]
    available = primary is not None and all(name in scored["models"] for name in names)
    gaps = {name: None for name in names}
    comparisons, calibration = {ref: None for ref in references}, None
    if available:
        bins = {name: scored["models"][name]["pooled"]["lowest_bin"] for name in names}
        gaps = {name: abs(row["mean_prediction"] - row["observed_frequency"]) if row["count"] else None
                for name, row in bins.items()}
        comparisons = {ref: scored["paired"][primary + "__vs__" + ref]["percentile_95_interval"][1] < 0
                       for ref in references}
        calibration = gaps[primary] is not None and all(gaps[ref] is not None and gaps[primary] <= gaps[ref]
                                                        for ref in references)
    complete = assessment["status"] == "COMPLETE" and bool(scored["entries"])
    return dict(criteria_pass=bool(complete and selection_present and available and calibration and all(comparisons.values())),
                brier_comparisons_pass={ref: bool(complete and value) for ref, value in comparisons.items()},
                lowest_bin_absolute_gaps=gaps, calibration_pass=bool(complete and calibration), complete_cohort_pass=complete,
                descriptive_subset_criteria=dict(brier_comparisons=comparisons, calibration=calibration),
                diagnostic_status="AVAILABLE" if available else "UNAVAILABLE_NO_PRIMARY_METRIC_DATA",
                interpretation="Retrospective mapped-extent comparison only; this is not the blind2026 test or physical validation")


def figure_unavailable(plt, out, name, title, reason, label, figsize):
    """A diagnostic panel contains no invented points, scores or calibration bins."""
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_axis_off()
    width = 88 if figsize[0] == DOUBLE else 43
    fig.suptitle(title + label, fontsize=7, y=.95)
    ax.text(.5, .69, "UNAVAILABLE", ha="center", va="center", transform=ax.transAxes, fontsize=9, weight="bold")
    ax.text(.5, .37, textwrap.fill(reason, width), ha="center", va="center", transform=ax.transAxes, fontsize=7)
    fig.subplots_adjust(left=.04, right=.96, bottom=.08, top=.81)
    save(fig, out, name)
    plt.close(fig)


def absence_reason(assessment):
    outcomes = assessment.get("failed_or_unavailable", [])
    reasons = list(dict.fromkeys(str(row.get("reason", row.get("status", "Unscored outcome"))) for row in outcomes))
    return (f"Assessment {assessment['status']}: no scored common-support entries. " + "; ".join(reasons[:2])
            + (f"; {len(reasons) - 2} further reasons" if len(reasons) > 2 else "")
            + ". Every outcome and reason is retained in RESULTS.json.")

def ablation(run: Path, draws: int = 10000, seed: int = 20261030) -> dict:
    """Absolute development scores on each model's own support, for selection.

    Aggregate validation receipts do not retain exact cell identities. Neither
    a shared fire name nor equal weights establishes a paired cell population.
    ``draws`` and ``seed`` remain accepted for existing callers; no development
    paired bootstrap is identified by these aggregate receipts.
    """
    rows = []
    paths = [run / phase["result"] for phase in F.current_phase_identity()["phases"]
             if phase["stage"] == "fold" and (run / phase["result"]).is_file()]
    for path in paths:
        phase = next(p for p in F.current_phase_identity()["phases"] if run / p["result"] == path)
        _, r, _, _, _ = F.phase_result(REPO, run, phase["variant"], "fold", phase["fold"])
        for fire, s in r["validation_per_fire"].items():
            rows.append(dict(variant=r["variant"], fold=r["fold"], seed=r["seed"], fire=fire,
                             sq=s["brier"] * s["weight"], w=s["weight"], nll=s["clipped_nll"] * s["weight"],
                             fit_seconds=r["fit_seconds"], parameters=r["parameters"]))
    frame = pd.DataFrame(rows)
    if frame.empty:
        return {}
    by = frame.groupby(["variant", "fire"]).agg(sq=("sq", "mean"), w=("w", "mean"), nll=("nll", "mean")).reset_index()
    summary = {}
    for variant, group in by.groupby("variant"):
        g = group.set_index("fire")
        entry = dict(pooled_brier=float(g.sq.sum() / g.w.sum()), pooled_clipped_nll=float(g.nll.sum() / g.w.sum()),
                     mean_fire_brier=float((g.sq / g.w).mean()),
                     fires=int(len(g)), seeds=sorted(frame[frame.variant == variant].seed.unique().tolist()),
                     folds=sorted(frame[frame.variant == variant].fold.unique().tolist()),
                     mean_fit_seconds=float(frame[frame.variant == variant].fit_seconds.mean()),
                     parameters=int(frame[frame.variant == variant].parameters.iloc[0]),
                     own_support_weight=float(g.w.sum()),
                     per_fire={str(fire): dict(brier=float(row.sq / row.w), weight=float(row.w),
                                              clipped_nll=float(row.nll / row.w)) for fire, row in g.iterrows()},
                     statistic_scope="descriptive absolute scores on each variant's own development support",
                     paired_status="UNAVAILABLE_NO_EXACT_COMMON_CELL_DEVELOPMENT_PREDICTIONS",
                     paired_unavailability_reason="Development aggregate receipts cannot establish identical scored cells, even when weights match",
                     difference_vs_base=None, interval_95=None, excludes_zero=None, fires_better_than_base=None)
        summary[variant] = entry
    return summary


def heldout_ablation(entries, assessment, cohort):
    """Secondary paired estimates from load_assessment's common-cell entries.

    This does not choose a model or satisfy a promotion gate. HOLD estimates
    describe only the supported subset, with every unscored outcome retained.
    """
    complete = assessment["status"] == "COMPLETE" and entries is not None
    result = dict(cohort=cohort, assessment_status=assessment["status"],
                  frozen_assessment_sha256=assessment["frozen_sha256"], per_fire_files=assessment["per_fire_files"],
                  estimand="cell-pooled candidate Brier minus base Brier on the same receipt-bound common cells",
                  statistic_scope="complete declared cohort" if complete else "descriptive supported subset only",
                  bootstrap=dict(draws=10000, seed=20261030, unit="whole fire", interval="percentile 95%"),
                  complete_cohort_pass=bool(complete), promotion_criteria_pass=False,
                  unscored_outcomes=assessment["failed_or_unavailable"], variants={})
    if entries is None:
        result.update(status="UNAVAILABLE_NO_SCORED_ENTRIES", reason=absence_reason(assessment))
        return result
    aliases = {variant: variant + "_seed0" for variant in F.VARIANTS}
    missing = sorted(set(aliases.values()) - set(entries["predictions"]))
    if missing:
        result.update(status="UNAVAILABLE_MISSING_FIXED_VARIANT_PREDICTIONS", missing_models=missing,
                      reason="Receipt-bound predictions do not include every fixed variant alias")
        return result
    scored = B.score_entries(entries, references=("base_seed0",), draws=10000, seed=20261030)
    for variant, alias in aliases.items():
        if variant == "base":
            continue
        paired = scored["paired"][alias + "__vs__base_seed0"]
        result["variants"][variant] = dict(model=alias, reference="base_seed0", **paired)
    result.update(status="AVAILABLE_COMPLETE_DECLARED_COHORT" if complete else "DESCRIPTIVE_SUPPORTED_SUBSET",
                  entries=int(len(entries["y"])), fires=scored["fires"])
    return result


def primary_candidate(abl: dict) -> str | None:
    """Frozen rule: lowest equal-fire development Brier, then fixed variant order."""
    priority = ["base", "d4", "d4_wind", "ellipse", "burnout", "burnout_spotting", "mixed_base"]
    return min(abl, key=lambda v: (abl[v]["mean_fire_brier"], priority.index(v))) if (set(abl) == set(priority)
            and all(v["folds"] == ["2020", "2021", "2022"] and v["seeds"] == [0] for v in abl.values())) else None


def detailed_scores(entries, draws=10000, seed=20261030):
    """Add honest exact-NLL limits and paired whole-fire skill intervals."""
    scored = B.score_entries(entries, draws=draws, seed=seed)
    fire, y = entries["fire"], entries["y"]
    fires = np.unique(fire)
    sampled = np.random.default_rng(seed).integers(0, len(fires), size=(draws, len(fires)))
    errors = {n: np.array([np.sum((p[fire == f] - y[fire == f]) ** 2) for f in fires])
              for n, p in entries["predictions"].items()}
    for name, record in scored["models"].items():
        p = entries["predictions"][name]
        wrong = int((((p == 0) & (y == 1)) | ((p == 1) & (y == 0))).sum())
        exact = None if wrong else float((-np.log(p[y == 1]).sum() - np.log1p(-p[y == 0]).sum()) / len(y))
        record["pooled"]["exact_nll"] = dict(value=exact, infinite=bool(wrong), certainty_wrong_entries=wrong)
        for reference in ("persistence", "dilation_best"):
            denominator = errors[reference].sum()
            metric = "bss_vs_" + ("best_dilation" if reference == "dilation_best" else "persistence")
            record["pooled"][metric] = float(1 - errors[name].sum() / denominator) if denominator else None
            resampled_denominator = errors[reference][sampled].sum(1)
            supported = resampled_denominator > 0
            values = 1 - errors[name][sampled].sum(1)[supported] / resampled_denominator[supported]
            interval = np.quantile(values, [.025, .975]).tolist() if len(values) else None
            record[metric + "_paired_fire_95_interval"] = dict(interval=interval, draws=draws, seed=seed,
                undefined_zero_reference_draws=int((~supported).sum()), unit="whole fire, pooled error ratio")
            for event, per_fire in record["per_fire"].items():
                db = scored["models"][reference]["per_fire"][event]["brier"]
                per_fire[metric] = 1 - per_fire["brier"] / db if db else None
    return scored


def figure_reliability(plt, scored, entries, out, label):
    fig, (ax, low) = plt.subplots(1, 2, figsize=(DOUBLE, 3.0))
    names = list(scored["models"])
    y_all = entries["y"]
    for index_model, (colour, name) in enumerate(zip(OKABE_ITO * 3, names)):
        line_style = ("-", "--", ":")[index_model // len(OKABE_ITO)]
        table = scored["models"][name]["pooled"]["calibration"]
        x = [r["mean_prediction"] for r in table if r["count"]]
        y = [r["observed_frequency"] for r in table if r["count"]]
        ax.plot(x, y, marker="o", ms=2.5, lw=0.9, ls=line_style, color=colour, label=name)
        p = entries["predictions"][name]
        index = np.clip(np.digitize(p, FINE_BINS[1:-1]), 0, len(FINE_BINS) - 2)
        xs, ys = [], []
        for b in range(len(FINE_BINS) - 1):
            use = index == b
            if use.sum() >= 50:
                xs.append(max(p[use].mean(), 1e-5))
                ys.append(max(y_all[use].mean(), 1e-5))
        low.plot(xs, ys, marker="o", ms=2.5, lw=0.9, ls=line_style, color=colour)
    for axis in (ax, low):
        axis.plot([1e-5, 1], [1e-5, 1], color="#999999", lw=0.6, ls="--")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    low.set_xscale("log")
    low.set_yscale("log")
    low.set_xlim(1e-5, 1)
    low.set_ylim(1e-5, 1)
    ax.set_xlabel("Mean forecast probability in bin\n(ten equal-width bins)")
    ax.set_ylabel("Observed new-mapping frequency")
    low.set_xlabel("Mean forecast probability in bin\n(log bins; >= 50 entries)\nvalues below 1e-5 plotted at 1e-5")
    ax.set_title(f"Reliability, held-out 2024 intervals{label}")
    low.set_title("Low-probability range")
    fig.legend(*ax.get_legend_handles_labels(), loc="lower center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 0.01))
    fig.subplots_adjust(left=0.09, right=0.985, top=0.89, bottom=0.40, wspace=0.30)
    save(fig, out, "fig01_reliability_all_models")
    plt.close(fig)


def figure_per_fire(plt, scored, out, label, primary):
    fires = scored["fires"]
    names = [n for n in ("persistence", "dilation_best", "logistic", "c651_mc", primary) if n and n in scored["models"]]
    fig, ax = plt.subplots(figsize=(DOUBLE, 2.6))
    x = np.arange(len(fires))
    for k, (colour, name) in enumerate(zip(OKABE_ITO, names)):
        values = [scored["models"][name]["per_fire"][f]["brier"] for f in fires]
        ax.scatter(x + (k - len(names) / 2) * 0.12, values, s=10, color=colour, label=name, zorder=3)
    if primary and "dilation_best" in names:
        left, right = names.index("dilation_best"), names.index(primary)
        for i, fire in enumerate(fires):
            xs = [i + (k - len(names) / 2) * .12 for k in (left, right)]
            ys = [scored["models"][n]["per_fire"][fire]["brier"] for n in ("dilation_best", primary)]
            ax.plot(xs, ys, color="#bbbbbb", lw=.6, zorder=1)
    ax.set_xticks(x, [f.split("_")[1] if "_" in f else f for f in fires])
    ax.set_ylabel("Brier score per fire (lower is better)")
    ax.set_title(f"Held-out 2024 fires, common cells for every model{label}")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), frameon=False)
    fig.subplots_adjust(left=.09, right=.74, bottom=.24, top=.88)
    save(fig, out, "fig02_per_fire_brier_paired")
    plt.close(fig)


def figure_ablation(plt, paired, out, label):
    variants = list(paired["variants"])
    if not variants:
        figure_unavailable(plt, out, "fig03_ablation_forest_plot", "Held-out structural ablations",
                           paired["reason"].rstrip(".") + ". Development scores remain descriptive on each model's own support.",
                           label, (SINGLE, 3.0))
        return
    fig, ax = plt.subplots(figsize=(SINGLE, 0.35 * max(len(variants), 1) + 0.9))
    for i, v in enumerate(variants):
        e = paired["variants"][v]
        ax.errorbar(e["point_difference"], i, xerr=[[e["point_difference"] - e["percentile_95_interval"][0]],
                                                      [e["percentile_95_interval"][1] - e["point_difference"]]],
                    fmt="o", ms=3, color=OKABE_ITO[5], ecolor=OKABE_ITO[5], lw=0.8, capsize=2)
    ax.axvline(0, color="#999999", lw=0.6, ls="--")
    ax.set_yticks(range(len(variants)), variants)
    ax.set_xlabel("Pooled common-cell Brier minus base\n(10,000 whole-fire draws, 95% interval)")
    scope = "\nHOLD: supported subset only" if paired["assessment_status"] == "HOLD" else ""
    ax.set_title(f"{paired['cohort']}{scope}" + ("\n" + label.strip() if label else ""))
    fig.subplots_adjust(left=.35, right=.98, bottom=.25, top=.84)
    save(fig, out, "fig03_ablation_forest_plot")
    plt.close(fig)


def figure_meanfield(plt, frame, out, label):
    fig = plt.figure(figsize=(SINGLE, 2.4))
    grid = fig.add_gridspec(2, 1, height_ratios=(3, 1.1), hspace=.65)
    ax, counts = fig.add_subplot(grid[0]), fig.add_subplot(grid[1])
    fixed = frame[frame.horizon_kind == "fixed"]
    support = comparison_support(frame)
    available = bool(fixed.rmse_active.notna().any())
    for colour, (country, group) in zip(OKABE_ITO[1:], fixed.groupby("country")):
        stats = group.groupby("hours").rmse_active.agg(["median", "min", "max"]).reindex(COMPARISON_HOURS)
        ax.plot(stats.index, stats["median"], marker="o", ms=3, color=colour, label=f"{country} cutoff median")
        ax.fill_between(stats.index, stats["min"], stats["max"], color=colour, alpha=0.2, lw=0)
    ax.set_xscale("log")
    ax.set_xticks([1, 3, 6, 12, 24], ["1", "3", "6", "12", "24"])
    ax.set_xlabel("Forecast horizon (h)", labelpad=1)
    ax.set_ylabel("MF vs MC RMSE")
    ax.set_title(f"c651, 1,024 trajectories{label}")
    ax.legend(frameon=False)
    if not available:
        ax.set_yticks([])
        ax.text(.5, .5, "UNAVAILABLE: no active supported cells", ha="center", va="center",
                transform=ax.transAxes, fontsize=6)
    countries = sorted(fixed.country.unique())
    values = [[f"C {row['available_cutoffs']}/{row['declared_cutoffs']}\nE {row['available_catalog_events']}/{row['declared_catalog_events']}"
               + (" U" if not row["available_cutoffs"] else "")
               for row in support if row["country"] == country] for country in countries]
    counts.set_axis_off()
    table = counts.table(cellText=values, rowLabels=countries, colLabels=[str(h) for h in COMPARISON_HOURS],
                         cellLoc="center", loc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(5.5)
    table.scale(1, 1.18)
    fig.text(.25, .095, "Available/all: C cutoffs; E unique catalog events; U unavailable", fontsize=5)
    fig.text(.25, .055, "Active: known initially unburned; either probability > 0.001.", fontsize=5)
    fig.text(.25, .015, "Band: cutoff min/max, not CI. Probability-active, not physical flaming.", fontsize=5)
    fig.subplots_adjust(left=.24, right=.98, bottom=.17, top=.87)
    save(fig, out, "fig04_meanfield_vs_mc_rmse_by_horizon")
    plt.close(fig)
    return dict(status="GENERATED_FROM_AUTHENTICATED_COMPARISON" if available else "GENERATED_WITH_UNAVAILABLE_EVIDENCE",
                metric_data_available=available, support_by_horizon=support,
                band="Descriptive minimum/maximum over available cutoffs, not a confidence interval",
                active="Known initially-unburned cells where max(MC probability, MF probability) > 0.001; not physical flaming")


def figure_example(plt, run, scored_entries, primary, out, label):
    import numpy as np
    fire_ids = sorted(set(scored_entries["fire"].tolist()))
    candidates = []
    for fire in fire_ids:
        data = np.load(run / "heldout" / f"{fire}.npz")
        for interval in np.unique(data["interval"]):
            use = data["interval"] == interval
            candidates.append((int(data["y"][use].sum()), fire, int(interval)))
    positive = sorted(c for c in candidates if c[0] > 0)
    if not positive or primary is None:
        return None
    count, fire, interval = positive[len(positive) // 2]
    data = np.load(run / "heldout" / f"{fire}.npz")
    perimeter_root = Path(json.loads((run / "report_inputs.json").read_text())["perimeters"])
    manifest_path, states_path = perimeter_root / "PERIMETER_MANIFEST.json", perimeter_root / fire / "states.npz"
    frozen = json.loads((run / "heldout/FROZEN_ASSESSMENT.json").read_text())
    if (sha256(manifest_path) != frozen["perimeter_manifest_sha256"]
            or json.loads(manifest_path.read_text())["events"][fire]["states_sha256"] != sha256(states_path)):
        raise ValueError("Example panel reference arrays differ from the frozen source manifest")
    states = np.load(states_path, allow_pickle=False)
    times = list(pd.to_datetime(states["times"], utc=True))
    t1 = pd.Timestamp(str(data["t1"][interval]))
    i = times.index(t1)
    initial, later = states["states"][i].astype(bool), states["states"][i + 1].astype(bool)
    use = data["interval"] == interval
    rows, cols = data["row"][use], data["col"][use]
    fields = {}
    for name in ("c651_mc", primary):
        field = np.full(initial.shape, np.nan)
        field[rows, cols] = data[f"p_{name}"][use]
        field[initial] = 1.0
        fields[name] = field
    r = np.flatnonzero((initial | later).any(1))
    c = np.flatnonzero((initial | later).any(0))
    window = (slice(max(r[0] - 8, 0), r[-1] + 9), slice(max(c[0] - 8, 0), c[-1] + 9))
    fig, axes = plt.subplots(1, 4, figsize=(DOUBLE, 2.0))
    panels = [("Initial mapped extent", initial.astype(float)), ("c651 Monte Carlo", fields["c651_mc"]),
              (f"{primary}\nmean field", fields[primary]), ("Later mapped extent", later.astype(float))]
    for ax, (title, image) in zip(axes, panels):
        shown = ax.imshow(image[window], vmin=0, vmax=1, cmap="viridis", interpolation="nearest")
        ax.set_title(title)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.subplots_adjust(left=.02, right=.89, bottom=.08, top=.70, wspace=.12)
    colour_axis = fig.add_axes([.915, .18, .013, .46])
    fig.colorbar(shown, cax=colour_axis, label="Cumulative probability or mapped (1)")
    fig.suptitle(f"{fire}\n{t1.isoformat()}, +{float(data['hours'][interval]):.1f} h, {count} newly mapped cells{label}", y=.98, fontsize=7)
    save(fig, out, "fig05_example_forecast_vs_perimeter")
    plt.close(fig)
    return dict(fire=fire, interval=interval, t1=t1.isoformat(), positives=count,
                rule="median positive count among held-out intervals with growth")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    label = f" [{args.label}]" if args.label else ""
    plt = style()
    figures = args.out / "figures"
    args.out.mkdir(parents=True, exist_ok=True)
    results = dict(current_phase=F.current_phase_identity(), label=args.label or "REAL INPUTS", run=str(args.run), figure_evidence={})
    abl = ablation(args.run)
    results["ablation"] = abl
    results["primary_candidate_rule"] = "lowest equal-fire development Brier over the 2020 to 2022 leave-one-year-out folds, with the fixed variant tie order"
    primary = primary_candidate(abl)
    finals = {}
    for variant in F.VARIANTS:
        path = args.run / F.intended_phase(variant, "final")["result"]
        if not path.is_file():
            continue
        _, r, _, _, _ = F.phase_result(REPO, args.run, variant, "final")
        finals[path.parent.name] = dict(variant=r["variant"], seed=r["seed"], epochs=r["epochs"],
                                        checkpoint_sha256=r["checkpoint_sha256"], parameters=r["parameters"],
                                        fit_seconds=r["fit_seconds"])
    results["final_models"] = finals
    chosen = [k for k, v in finals.items() if v["variant"] == primary]
    results["primary_candidate"] = dict(variant=primary, run=chosen[0] if chosen else None,
                                        checkpoint_sha256=finals[chosen[0]]["checkpoint_sha256"] if chosen else None)
    selection_path = args.out / "MODEL_SELECTION.json"
    if selection_path.exists():
        selection = json.loads(selection_path.read_text())
        F.validate_selection_phase(REPO, args.run, selection)
        if selection["selected_variant"] != primary or not chosen:
            raise ValueError("Report selection differs from the frozen development choice")
        if selection["checkpoints"][primary]["sha256"] != finals[chosen[0]]["checkpoint_sha256"]:
            raise ValueError("Report primary checkpoint differs from its frozen identity")
        results["model_selection_sha256"] = sha256(selection_path)
    if abl:
        pd.DataFrame(abl).T.to_csv(args.out / "ablation.csv")
    results["development_ablation_interpretation"] = "Absolute own-support scores preserve the frozen equal-fire selection rule; paired common-cell development effects are unavailable"
    paired_ablation = dict(status="UNAVAILABLE_NO_AUTHENTICATED_HELDOUT_ASSESSMENT", variants={},
                          reason="No authenticated held-out common-cell predictions are available",
                          promotion_criteria_pass=False, complete_cohort_pass=False)
    heldout = args.run / "heldout"
    if (heldout / "ASSESSMENT.json").is_file():
        entries, assessment = load_assessment(heldout)
        scored = assessment_scores(entries, assessment)
        inputs = load_report_inputs(args.run, assessment)
        paired_ablation = heldout_ablation(entries, assessment, "US2024 mapped extent")
        paired_ablation["assessment_receipt_sha256"] = sha256(heldout / "ASSESSMENT.json")
        if entries is not None and "c651_mc" in entries["predictions"]:
            # Preserve the fixed finite-trajectory variance correction.
            n = inputs["n_samples"]
            p = entries["predictions"]["c651_mc"]
            pooled = scored["models"]["c651_mc"]["pooled"]
            pooled["brier_mc_variance_corrected"] = float(pooled["brier"] - np.mean(p * (1 - p)) / (n - 1))
            pooled["mc_trajectories"] = n
        results["heldout_inputs"], results["heldout"] = inputs, scored
        # Artifact directory suffixes identify producer phases; model columns keep the fixed alias.
        primary_model = primary + "_seed0" if chosen else None
        results["retrospective_superiority_gate"] = retrospective_gate(scored, primary_model, assessment, selection_path.exists())
        rows = []
        if entries is not None:
            scope_label = ("\nHOLD: supported subset only" if assessment["status"] == "HOLD" else "") + label
            figure_reliability(plt, scored, entries, figures, scope_label)
            figure_per_fire(plt, scored, figures, scope_label, primary_model)
            status = "GENERATED_FROM_DESCRIPTIVE_SUPPORTED_SUBSET" if assessment["status"] == "HOLD" else "GENERATED_FROM_COMPLETE_DECLARED_COHORT"
            for name in ("fig01_reliability_all_models", "fig02_per_fire_brier_paired"):
                results["figure_evidence"][name] = dict(status=status, metric_data_available=True)
            for model, record in scored["models"].items():
                for fire, row in record["per_fire"].items():
                    rows.append(dict(model=model, fire=fire, **{key: row[key] for key in ("entries", "positives", "brier",
                        "bss_vs_persistence", "bss_vs_best_dilation", "average_precision", "roc_auc", "ece_10_bins", "clipped_nll")}))
            example = figure_example(plt, args.run, entries, primary_model, figures, scope_label) if primary_model else None
            results["example_figure"] = example
            if example is not None:
                results["figure_evidence"]["fig05_example_forecast_vs_perimeter"] = dict(status=status, metric_data_available=True)
        else:
            reason = absence_reason(assessment)
            for name, title, size in (("fig01_reliability_all_models", "Held-out reliability", (DOUBLE, 3.0)),
                                      ("fig02_per_fire_brier_paired", "Held-out per-fire Brier comparison", (DOUBLE, 2.6))):
                figure_unavailable(plt, figures, name, title, reason, label, size)
                results["figure_evidence"][name] = dict(status="GENERATED_WITH_UNAVAILABLE_EVIDENCE", metric_data_available=False, reason=reason)
            results["example_figure"] = None
        if "fig05_example_forecast_vs_perimeter" not in results["figure_evidence"]:
            reason = absence_reason(assessment) if entries is None else "No eligible positive-growth interval with the frozen primary model is available for the example panel. Subset metrics do not provide a complete-cohort result."
            figure_unavailable(plt, figures, "fig05_example_forecast_vs_perimeter", "Example forecast versus mapped extent", reason, label, (DOUBLE, 2.0))
            results["figure_evidence"]["fig05_example_forecast_vs_perimeter"] = dict(status="GENERATED_WITH_UNAVAILABLE_EVIDENCE", metric_data_available=False, reason=reason)
        pd.DataFrame(rows, columns=["model", "fire", "entries", "positives", "brier", "bss_vs_persistence", "bss_vs_best_dilation",
            "average_precision", "roc_auc", "ece_10_bins", "clipped_nll"]).to_csv(args.out / "per_fire.csv", index=False)
    elif heldout.exists() and list(heldout.glob("*.npz")):
        raise ValueError("Scored heldout files require an authenticated ASSESSMENT.json before reporting")
    results["heldout_ablation"] = paired_ablation
    figure_ablation(plt, paired_ablation, figures, label)
    available = bool(paired_ablation["variants"])
    results["figure_evidence"]["fig03_ablation_forest_plot"] = dict(
        status=("GENERATED_FROM_DESCRIPTIVE_SUPPORTED_SUBSET" if paired_ablation.get("assessment_status") == "HOLD"
                else "GENERATED_FROM_COMPLETE_DECLARED_COHORT") if available else "GENERATED_WITH_UNAVAILABLE_EVIDENCE",
        metric_data_available=available, source="heldout_ablation", cohort="US2024 mapped extent",
        reason=paired_ablation.get("reason"), promotion_criteria_pass=False)
    korea = args.run / "korean2025"
    if (korea / "ASSESSMENT.json").is_file():
        entries, assessment = load_assessment(korea)
        results["korean2025_secondary_reconstruction"] = assessment_scores(entries, assessment)
        results["korean2025_secondary_ablation"] = heldout_ablation(entries, assessment, "Korean2025 reconstruction")
        results["korean2025_secondary_ablation"]["assessment_receipt_sha256"] = sha256(korea / "ASSESSMENT.json")
    elif korea.exists() and list(korea.glob("*.npz")):
        raise ValueError("Scored Korean files require an authenticated ASSESSMENT.json before reporting")
    mf = args.run / "meanfield_vs_mc" / "meanfield_vs_mc.csv"
    if mf.exists() or mf.with_suffix(".json").exists() or (REPO / "research/forecast-v2/executions/a06_compare.json").exists():
        frame, results["meanfield_vs_mc"] = load_comparison(args.run)
        results["figure_evidence"]["fig04_meanfield_vs_mc_rmse_by_horizon"] = figure_meanfield(plt, frame, figures, label)
        results["figure_evidence"]["fig04_meanfield_vs_mc_rmse_by_horizon"]["execution_complete"] = True
        frame.to_csv(args.out / "meanfield_vs_mc.csv", index=False)
    else:
        figure_unavailable(plt, figures, "fig04_meanfield_vs_mc_rmse_by_horizon", "Mean field versus Monte Carlo",
                           "No mean-field/Monte Carlo comparison artifact is available. No RMSE is inferred.", label, (SINGLE, 2.4))
        results["figure_evidence"]["fig04_meanfield_vs_mc_rmse_by_horizon"] = dict(status="GENERATED_WITH_UNAVAILABLE_EVIDENCE", metric_data_available=False)
        results["meanfield_vs_mc"] = dict(execution_complete=False,
            execution_status="UNAVAILABLE_NO_AUTHENTICATED_COMPARISON", metric_data_available=False)
    for name, evidence in results["figure_evidence"].items():
        evidence["files_sha256"] = {extension: sha256(figures / (name + "." + extension)) for extension in ("png", "svg")}
    results["report_status"] = "HOLD" if any(value.get("assessment_status") == "HOLD" for value in
        (results.get("heldout", {}), results.get("korean2025_secondary_reconstruction", {}))) else "GENERATED_PENDING_VISUAL_QA"
    (args.out / "RESULTS.json").write_text(json.dumps(results, indent=1, default=str) + "\n")
    print(json.dumps(dict(primary=primary, finals=list(finals), heldout="heldout" in results)))


if __name__ == "__main__":
    main()
