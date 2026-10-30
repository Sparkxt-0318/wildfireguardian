"""Authenticate supplied deterministic scenarios, then optionally rescore a subset.

The audit reads identities/references only. Optional scoring authenticates a
current COMPLETE or HOLD assessment and recomputes available comparators on
identical ordered cell-interval entries. Historical M548 arrays are never loaded.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "forecast"))
from wildfire.cumulative_report import case_seed


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array_sha(value):
    value = np.ascontiguousarray(value)
    return hashlib.sha256(str((value.shape, str(value.dtype))).encode() + value.tobytes()).hexdigest()


def load_reporting():
    spec = importlib.util.spec_from_file_location("matched_subset_reporting", HERE.with_name("report.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native_horizon(report, metadata, arrival, initial, probability, valid, start, end):
    """Admit negatives only through the source-recorded native run horizon.

    This replays the stored timing receipt, not native execution. A no-arrival
    sentinel is right-censored at that finite horizon, never an all-future zero.
    """
    result = dict(status="UNAVAILABLE", reason="HORIZON_OR_CENSOR_EVIDENCE_UNAVAILABLE",
                  evidence="RECORDED_NATIVE_TIMING_RECEIPT_NOT_NEW_EXECUTION",
                  field_paths=["report.json:farsite_execution.elapsed_minutes",
                               "report.json:native_clock_verification.duration_minutes",
                               "farsite_prediction.npz:metadata_json.exact_duration_minutes",
                               "farsite_prediction.npz:metadata_json.no_burn_value",
                               "farsite_prediction.npz:arrival_minutes"])
    execution, clock = report.get("farsite_execution", {}), report.get("native_clock_verification", {})
    elapsed, duration = execution.get("elapsed_minutes"), clock.get("duration_minutes")
    exact = metadata.get("exact_duration_minutes")
    numeric = lambda value: isinstance(value, (int, float)) and not isinstance(value, bool) and np.isfinite(value) and value > 0
    if (not all(numeric(value) for value in (elapsed, duration, exact)) or arrival is None
            or not isinstance(execution.get("header"), dict)):
        return result
    result.update(native_horizon_minutes=float(elapsed), endpoint_minutes=(end-start).total_seconds()/60,
                  native_timings_sha256=execution.get("timings_sha256"), native_arrival_sha256=execution.get("arrival_sha256"),
                  no_burn_value=metadata.get("no_burn_value"),
                  right_censoring="-9999 means no arrival through the verified finite native horizon only")
    if result["endpoint_minutes"] > elapsed:
        result["reason"] = "HORIZON_SHORTER_THAN_REFERENCE_ENDPOINT"
        return result
    if (elapsed != duration or exact != result["endpoint_minutes"]
            or execution.get("native_clock_verification") != clock
            or execution.get("arrival_units") != "minutes since simulation cutoff"
            or any(not isinstance(execution.get(name), str) or not re.fullmatch(r"[0-9a-f]{64}", execution[name])
                   for name in ("timings_sha256", "arrival_sha256"))):
        result["reason"] = "HORIZON_EVIDENCE_MISMATCH"
        return result
    selection = re.fullmatch(r"0 <= arrival <= ([0-9.+eE-]+)", str(execution.get("endpoint_selection")))
    try:
        selected_minutes = float(selection[1]) if selection else None
    except ValueError:
        selected_minutes = None
    if selected_minutes != elapsed:
        result["reason"] = "HORIZON_ENDPOINT_SELECTION_UNVERIFIED"
        return result
    if (metadata.get("no_burn_value") != -9999 or execution["header"].get("nodata_value") != -9999
            or metadata.get("arrival_units") != "minutes" or metadata.get("arrival_origin_time_utc") != start.timestamp()
            or metadata.get("arrival_endpoint") != "inclusive_at_exact_cutoff_plus_hours"
            or metadata.get("initial_ignition_policy") != "observed_initial_burn_union_simulated_arrivals_including_zero"
            or metadata.get("method") != "farsite_deterministic" or metadata.get("scenario_count") != 1
            or arrival.shape != initial.shape or not np.isfinite(arrival[valid]).all()
            or ((arrival[valid] < 0) & (arrival[valid] != -9999)).any()):
        result["reason"] = "CENSOR_OR_ARRIVAL_CONVENTION_UNVERIFIED"
        return result
    expected = ~initial & (arrival != -9999) & (arrival >= 0) & (arrival <= exact)
    if not np.array_equal(probability[valid], expected[valid]):
        result["reason"] = "CENSOR_ENDPOINT_OCCUPANCY_MISMATCH"
        return result
    result.update(status="AVAILABLE", reason=None)
    return result


def load_current_assessment(directory, reporting):
    """Authenticate the reviewed aggregate plus every individual case receipt."""
    _, assessment = reporting.load_assessment(directory)
    frozen = json.loads((directory / "FROZEN_ASSESSMENT.json").read_text())
    if frozen.get("cohort") != "us2024":
        raise ValueError("Matched stored US scenarios require a current US2024 assessment")
    receipts, ids, scored_ids = {}, set(), set()
    for record in assessment["cases"]:
        case, cid = record["case"], record["case_id"]
        key = (case["event"], pd.Timestamp(case["cutoff"]), pd.Timestamp(case["endpoint"]))
        if (key in receipts or cid in ids or not isinstance(cid, str) or Path(cid).name != cid
                or record.get("receipt_version") != "wfg.forecast-assessment-case/2"
                or record.get("assessment_sha256") != assessment["frozen_sha256"]):
            raise ValueError("Individual assessment case identity is invalid or duplicated")
        receipt_path = directory / "cases" / (cid + ".json")
        if not receipt_path.is_file() or json.loads(receipt_path.read_text()) != record:
            raise ValueError("Individual case receipt is missing or differs from the assessment")
        path = directory / "cases" / (cid + ".npz")
        if record["status"] == "SCORED":
            if not path.is_file() or sha(path) != record.get("sha256"):
                raise ValueError("Current case prediction bytes are missing or changed")
            scored_ids.add(cid)
        elif record["status"] not in ("UNAVAILABLE", "FAILED") or not record.get("reason") or path.exists():
            raise ValueError("Unscored assessment cases must retain their outcome/reason without predictions")
        receipts[key], ids = record, ids | {cid}
    if ({p.stem for p in (directory / "cases").glob("*.json")} != ids
            or {p.stem for p in (directory / "cases").glob("*.npz")} != scored_ids):
        raise ValueError("Unlisted individual case artifacts cannot enter the matched subset")
    return assessment, receipts


def matched_entries(directory, record, event, start, end, initial, endpoint, fp, fv, reference_valid):
    """Bind ordered source labels and case arrays to their authenticated aggregate."""
    path = directory / "cases" / (record["case_id"] + ".npz")
    with np.load(path, allow_pickle=False) as scored, np.load(directory / (event + ".npz"), allow_pickle=False) as aggregate:
        rr, cc, y = scored["row"], scored["col"], scored["y"]
        shape = initial.shape
        if (rr.dtype.kind not in "iu" or cc.dtype.kind not in "iu" or rr.ndim != 1 or cc.shape != rr.shape
                or not len(rr) or y.shape != rr.shape or (rr < 0).any() or (cc < 0).any()
                or (rr >= shape[0]).any() or (cc >= shape[1]).any()
                or (np.diff(rr.astype(np.int64) * shape[1] + cc.astype(np.int64)) <= 0).any()):
            raise ValueError("Current case coordinates must be unique ordered integer source cells")
        mask = np.zeros(shape, bool); mask[rr, cc] = True
        if (initial[rr, cc].any() or not np.array_equal(y, endpoint[rr, cc])
                or record.get("initial_sha256") != array_sha(initial)
                or record.get("endpoint_sha256") != array_sha(endpoint)
                or record.get("rectangle") != list(shape) or record.get("scored_mask_sha256") != array_sha(mask)
                or record.get("scored_cells") != len(y) or record.get("positives") != int(y.sum())):
            raise ValueError("Current case support or ordered endpoint labels differ from source")
        indices = [i for i, cutoff in enumerate(aggregate["t1"]) if pd.Timestamp(str(cutoff)) == start]
        if (len(indices) != 1 or abs(float(aggregate["hours"][indices[0]]) - (end-start).total_seconds()/3600) > 1e-9):
            raise ValueError("Current case interval differs from its authenticated per-fire aggregate")
        index = aggregate["interval"] == indices[0]
        names = {name for name in aggregate.files if name.startswith("p_")}
        if set(scored.files) != {"row", "col", "y", *names} or not names:
            raise ValueError("Current case and aggregate must contain the same probability columns")
        for name in ("row", "col", "y", *sorted(names)):
            if not np.array_equal(scored[name], aggregate[name][index]):
                raise ValueError("Individual case entries differ from authenticated per-fire entries")
        predictions = {}
        for name in sorted(names):
            value = scored[name]
            if value.shape != y.shape or not np.isfinite(value).all() or ((value < 0) | (value > 1)).any():
                raise ValueError("Current assessed probabilities must be finite and in range on every admitted cell")
            predictions[name[2:]] = value.copy()
        use = fv[rr, cc] & reference_valid[rr, cc]
        if not use.any():
            return None, dict(status="UNAVAILABLE", reason="EMPTY_FARSITE_COMMON_SUPPORT_INTERSECTION", cells=0)
        predictions = {name: value[use] for name, value in predictions.items()}
        predictions["farsite_scenario"] = fp[rr[use], cc[use]]
        return dict(fire=np.full(int(use.sum()), event), y=y[use].copy(), predictions=predictions), dict(
            status="SCORED_COMMON_SUBSET", cells=int(use.sum()),
            exact_row_col_sha256=hashlib.sha256(np.column_stack((rr[use], cc[use])).tobytes()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--assessment", type=Path)
    args = parser.parse_args()
    catalog = {e["id"]: e for e in json.loads((args.data / "environment/events.json").read_text())}
    extraction = args.data / "FARSITE_INPUTS_EXTRACTION.json"
    inputs = json.loads(extraction.read_text())
    for row in inputs["files"]:
        if not row["historical_input_identity_matches"] or sha(args.data / row["path"]) != row["sha256"]:
            raise ValueError("A historical scenario input identity changed")
    receipts, assessed, reporting = {}, None, None
    if args.assessment:
        reporting = load_reporting()
        assessed, receipts = load_current_assessment(args.assessment, reporting)
    rows, entries = [], []
    root = args.data / "historical_observed/20261013_observed_merged/cases"
    for directory in sorted(root.iterdir()):
        report_path = directory / "report.json"
        report = json.loads(report_path.read_text())
        protocol = json.loads((directory / "protocol.json").read_text())
        manifest = json.loads((directory / "combined_case_manifest.json").read_text())
        for name, expected in manifest.items():
            if sha(directory / name) != expected:
                raise ValueError("Historical scenario bytes changed")
        event, start, end = protocol["event"], pd.Timestamp(protocol["cutoff"]), pd.Timestamp(protocol["endpoint"])
        grid = catalog[event]
        context = report["farsite_input_manifest"]
        expected_seed = case_seed(0, event, start.isoformat())
        if (protocol["n_samples"] != 1024 or protocol["case_seed"] != expected_seed
                or protocol["trajectory_batch_size"] != 32 or protocol["boundary"] != "zero"
                or protocol["environment_policy"] != "repeated_current"
                or pd.Timestamp(protocol["environmental_snapshot_time_utc"]) != start.floor("h")
                or abs((end - start).total_seconds() / 3600 - protocol["hours"]) > 1e-9):
            raise ValueError("Historical comparison configuration differs")
        if (context["original_shape"] != [grid["height"], grid["width"]]
                or context["original_epsg"] != grid["epsg"]
                or not np.array_equal(context["original_transform"], grid["transform"])):
            raise ValueError("Historical FARSITE rectangle differs")
        states_path = args.data / "perimeters" / event / "states.npz"
        with np.load(states_path, allow_pickle=False) as source, np.load(directory / "reference.npz", allow_pickle=False) as ref:
            times = list(pd.to_datetime(source["times"], utc=True))
            i, j = times.index(start), times.index(end)
            if j != i + 1 or not np.array_equal(ref["burned_area"][:, 0].astype(bool), source["states"][[i, j]].astype(bool)):
                raise ValueError("Historical initial or endpoint extent differs")
            reference_valid = ref["burned_area_valid"][0, 0] & ref["burned_area_valid"][1, 0] & ref["pixel_valid"][0]
            initial = source["states"][i].astype(bool)
            endpoint = source["states"][j].astype(bool)
        with np.load(directory / "farsite_prediction.npz", allow_pickle=False) as f:
            fp, fv = f["probability"][0, 0].copy(), f["valid"][0, 0].copy()
            metadata = json.loads(str(f["metadata_json"]))
            arrival = f["arrival_minutes"].copy() if "arrival_minutes" in f.files else None
        if (fp.shape != initial.shape or fv.shape != initial.shape or fv.dtype != bool
                or reference_valid.shape != initial.shape or reference_valid.dtype != bool
                or not np.isin(fp[fv], (0, 1)).all() or not metadata["observed_initial"]):
            raise ValueError("Expected one deterministic observed-cutoff scenario")
        horizon = native_horizon(report, metadata, arrival, initial, fp, fv, start, end)
        row = dict(case_id=directory.name, event=event, cutoff=start.isoformat(), endpoint=end.isoformat(),
            status="AUTHENTICATED_IDENTITIES_ONLY", report_sha256=sha(report_path),
            protocol_sha256=sha(directory / "protocol.json"), combined_case_manifest_sha256=sha(directory / "combined_case_manifest.json"),
            reference_sha256=sha(directory / "reference.npz"), farsite_prediction_sha256=sha(directory / "farsite_prediction.npz"),
            initial_and_endpoint_equal_current_source=True, consecutive_survey_pair=True,
            source_raster_identities_verified=True, weather="same cutoff-source rasters; FARSITE repeats a spatially summarized station scenario",
            boundary="FARSITE one-cell nonburnable fuel99 padding; original rectangle and explicit validity retained",
            native_executable_sha256=report["models"][1]["sha256"], historical_m548_predictions_admitted=False,
            native_horizon=horizon)
        if horizon["status"] != "AVAILABLE":
            row.update(status="UNAVAILABLE", reason=horizon["reason"], cells=0)
        if args.assessment:
            record = receipts.get((event, start, end))
            if record is None:
                row.update(status="UNAVAILABLE", reason="NO_MATCHING_CURRENT_ASSESSMENT_CASE", cells=0)
            else:
                row.update(current_case=record, current_case_receipt_sha256=sha(args.assessment / "cases" / (record["case_id"] + ".json")))
                if record["status"] != "SCORED":
                    row.update(status=record["status"], reason=record["reason"], cells=0)
                elif horizon["status"] == "AVAILABLE":
                    entry, details = matched_entries(args.assessment, record, event, start, end, initial, endpoint, fp, fv, reference_valid)
                    row.update(details, current_prediction_sha256=record["sha256"])
                    if entry is not None:
                        entries.append(entry)
        rows.append(row)
    result = dict(evidence_class="authenticated stored deterministic scenarios; fresh metric recomputation only when assessment supplied",
        source_input_manifest_sha256=sha(extraction), cases=rows,
        stored_case_count=len(rows), stored_fire_count=len({row["event"] for row in rows}),
        coverage="Stored US2024 intervals only, incomplete relative to all eligible2024 intervals; no extrapolation",
        comparison_scope="Descriptive separate deterministic station-weather scenario on matched common cells; no model selection or full-cohort superiority claim",
        configuration_differences=dict(weather="Current forecasts repeat spatial cutoff rasters; FARSITE repeats a spatially summarized station scenario",
            boundary="Current forecasts use zero exterior; FARSITE uses one-cell nonburnable fuel99 padding",
            stochasticity="Current c651 uses 1024 trajectories; supplied FARSITE is one deterministic observed-cutoff scenario"),
        native_execution_this_command=False, execution_status="NO_NATIVE_EXECUTION_STORED_SCENARIOS_ONLY",
        superiority_criteria_pass=False, scores_available=bool(entries), scored_cases=len(entries), total_historical_cases=len(rows),
        skipped_unavailable_cases=[{key: row[key] for key in ("case_id", "event", "cutoff", "endpoint", "status", "reason")}
                                   for row in rows if row["status"] in ("UNAVAILABLE", "FAILED")],
        scored_case_count=len(entries), all_stored_cases_scored=bool(assessed is not None and rows and len(entries) == len(rows)))
    if assessed is not None:
        result.update(assessment_status=assessed["status"], assessment_complete=assessed["status"] == "COMPLETE",
            assessment_sha256=sha(args.assessment / "ASSESSMENT.json"), frozen_assessment_sha256=assessed["frozen_sha256"],
            assessment_unscored_outcomes=assessed["failed_or_unavailable"],
            status="HOLD" if assessed["status"] == "HOLD" or len(entries) != len(rows) else "DESCRIPTIVE_MATCHED_SUBSET_COMPLETE",
            measurement_status="AVAILABLE_DESCRIPTIVE_MATCHED_SUBSET" if entries else "UNAVAILABLE_NO_COMMON_SCORED_MATCHES",
            metric_status="DESCRIPTIVE_AVAILABLE_MATCHED_SUBSET" if entries else "UNAVAILABLE_NO_COMMON_SCORED_MATCHES")
    else:
        result.update(status="AUTHENTICATED_IDENTITIES_ONLY", measurement_status="NOT_REQUESTED_IDENTITIES_ONLY")
        result["metric_status"] = "IDENTITIES_ONLY"
    if entries:
        if any(set(entry["predictions"]) != set(entries[0]["predictions"]) for entry in entries):
            raise ValueError("Every matched case must score exactly the same model columns")
        combined = dict(fire=np.concatenate([e["fire"] for e in entries]), y=np.concatenate([e["y"] for e in entries]),
            predictions={n: np.concatenate([e["predictions"][n] for e in entries]) for n in entries[0]["predictions"]})
        result["scores"] = reporting.detailed_scores(combined, draws=10000, seed=20261030)
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(cases=len(rows), scored="scores" in result)))


if __name__ == "__main__":
    main()
