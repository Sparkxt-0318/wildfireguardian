"""Tiny stored-scenario identities and current receipt-bound matched populations."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


@pytest.fixture
def audit():
    path = Path(__file__).resolve().parents[2] / "research/forecast-v2/scripts/audit_farsite.py"
    spec = importlib.util.spec_from_file_location("synthetic_farsite_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fixture(audit, root, outcomes=("SCORED",), *, empty_farsite=False):
    """Only synthetic arrays and current source bytes, never scientific artifacts."""
    data, assessment, out = root / "data", root / "assessment", root / "output.json"
    event = "SYNTHETIC_US2024"
    grid = dict(id=event, year=2024, country="US", height=2, width=2, epsg=32610, transform=[1, 0, 0, 0, -1, 2])
    write(data / "environment/events.json", [grid])
    source_path = data / "farsite-inputs/synthetic-weather.bin"
    source_path.parent.mkdir(parents=True); source_path.write_bytes(b"synthetic pinned station input")
    write(data / "FARSITE_INPUTS_EXTRACTION.json", dict(files=[dict(path=str(source_path.relative_to(data)),
        sha256=audit.sha(source_path), historical_input_identity_matches=True)]))
    times = pd.date_range("2024-01-01", periods=len(outcomes) + 1, freq="h", tz="UTC")
    states = np.zeros((len(times), 2, 2), bool); states[:, 0, 0] = True; states[1:, 0, 1] = True
    states_path = data / "perimeters" / event / "states.npz"; states_path.parent.mkdir(parents=True)
    np.savez_compressed(states_path, times=np.array([t.isoformat() for t in times]), states=states)
    reporting = audit.load_reporting()
    sources = {relative: reporting.sha256(reporting.REPO / relative) for relative in
               ("forecast/wildfire/survival.py", "forecast/wildfire/meanfield.py", "forecast/wildfire/burnout.py")}
    frozen = dict(cohort="us2024", current_phase=reporting.F.current_phase_identity(),
                  spotting_source_contract=reporting.F.spotting_source_contract(reporting.REPO, sources))
    write(assessment / "FROZEN_ASSESSMENT.json", frozen)
    frozen_sha = audit.sha(assessment / "FROZEN_ASSESSMENT.json")
    names = {*(v + "_seed0" for v in reporting.F.VARIANTS), "c651_mc", "c651_meanfield", "persistence", "logistic",
             "dilation_best", *(f"dilation_{n}h" for n in (1, 2, 4, 8))}
    cases, columns, probabilities, historical = [], {k: [] for k in ("row", "col", "y", "interval")}, {name: [] for name in names}, []
    for index, status in enumerate(outcomes):
        start, end = times[index], times[index + 1]
        directory = data / f"historical_observed/20261013_observed_merged/cases/stored_{index:02d}"
        directory.mkdir(parents=True)
        protocol = dict(event=event, cutoff=start.isoformat(), endpoint=end.isoformat(), hours=1,
                        n_samples=1024, case_seed=audit.case_seed(0, event, start.isoformat()), trajectory_batch_size=32,
                        boundary="zero", environment_policy="repeated_current", environmental_snapshot_time_utc=start.isoformat())
        write(directory / "protocol.json", protocol)
        clock = dict(start_hhmm=start.hour * 100 + start.minute, end_hhmm=end.hour * 100 + end.minute, duration_minutes=60)
        write(directory / "report.json", dict(farsite_input_manifest=dict(original_shape=[2, 2], original_epsg=grid["epsg"],
              original_transform=grid["transform"]), models=[dict(name="historical_m548"), dict(sha256="a" * 64)],
              native_clock_verification=clock, farsite_execution=dict(elapsed_minutes=60, native_clock_verification=clock,
                  arrival_units="minutes since simulation cutoff", endpoint_selection="0 <= arrival <= 60",
                  timings_sha256="b" * 64, arrival_sha256="c" * 64, header=dict(nodata_value=-9999))))
        np.savez_compressed(directory / "reference.npz", burned_area=states[[index, index + 1], None],
                            burned_area_valid=np.ones((2, 1, 2, 2), bool), pixel_valid=np.ones((1, 2, 2), bool))
        arrival = np.array([[0., 30.], [-9999., -9999.]])
        fp = (~states[index] & (arrival >= 0) & (arrival <= 60)).astype(float)
        fv = np.ones((2, 2), bool)
        if empty_farsite: fv[:] = False
        else: fv[1, 1] = False  # Exact common subset is smaller than the assessed population.
        np.savez_compressed(directory / "farsite_prediction.npz", probability=fp[None, None], valid=fv[None, None],
                            arrival_minutes=arrival, metadata_json=np.array(json.dumps(dict(observed_initial=True,
                                method="farsite_deterministic", scenario_count=1, arrival_units="minutes",
                                no_burn_value=-9999., arrival_origin_time_utc=start.timestamp(),
                                arrival_endpoint="inclusive_at_exact_cutoff_plus_hours", exact_duration_minutes=60,
                                initial_ignition_policy="observed_initial_burn_union_simulated_arrivals_including_zero"))))
        # Deliberately not an NPZ: identities may hash it, but no reader may load M548 arrays.
        (directory / "m548_prediction.npz").write_bytes(b"M548_ARRAY_ACCESS_IS_FORBIDDEN")
        write(directory / "combined_case_manifest.json", {p.name: audit.sha(p) for p in directory.iterdir()})
        historical.append(directory)
        initial, endpoint = states[index], states[index + 1]
        mask = ~initial
        rr, cc = np.nonzero(mask)
        y = endpoint[mask].astype(np.int8)
        case = dict(event=event, cutoff=start.isoformat(), endpoint=end.isoformat(), hours=1.)
        cid = f"synthetic_case_{index:02d}"
        record = dict(case=case, case_id=cid, receipt_version="wfg.forecast-assessment-case/2", assessment_sha256=frozen_sha,
                      status=status, initial_sha256=audit.array_sha(initial), endpoint_sha256=audit.array_sha(endpoint), rectangle=[2, 2])
        if status == "SCORED":
            predictions = {name: np.where(y, .8, .2) for name in names}
            predictions["persistence"] = np.zeros(len(y))
            predictions["dilation_best"] = np.where(y, 1., .1)
            path = assessment / "cases" / (cid + ".npz"); path.parent.mkdir(exist_ok=True)
            np.savez_compressed(path, row=rr, col=cc, y=y, **{"p_" + name: value for name, value in predictions.items()})
            record.update(sha256=audit.sha(path), scored_cells=len(y), positives=int(y.sum()), scored_mask_sha256=audit.array_sha(mask))
            for name, values in dict(row=rr, col=cc, y=y, interval=np.full(len(y), index)).items(): columns[name].append(values)
            for name, values in predictions.items(): probabilities[name].append(values)
        else:
            record.update(scored_cells=0, reason="Synthetic unavailable source support" if status == "UNAVAILABLE" else "Synthetic recorded numerical failure")
        write(assessment / "cases" / (cid + ".json"), record)
        cases.append(record)
    files = {}
    if columns["y"]:
        path = assessment / (event + ".npz")
        np.savez_compressed(path, **{key: np.concatenate(value) for key, value in columns.items()},
            **{"p_" + name: np.concatenate(value) for name, value in probabilities.items()},
            t1=np.array([t.isoformat() for t in times[:-1]]), hours=np.ones(len(outcomes)))
        files[path.name] = audit.sha(path)
    failures = [record for record in cases if record["status"] != "SCORED"]
    receipt = dict(receipt_version="wfg.forecast-assessment/2", status="HOLD" if failures else "COMPLETE", frozen_sha256=frozen_sha,
                   per_fire_files=files, events=[event], cases=cases, failed_or_unavailable=failures)
    write(assessment / "ASSESSMENT.json", receipt)
    return SimpleNamespace(data=data, assessment=assessment, out=out, receipt=receipt, historical=historical, event=event)


def run(audit, made, monkeypatch, *, assessment=True):
    argv = ["audit_farsite.py", "--data", str(made.data), "--out", str(made.out)]
    if assessment: argv += ["--assessment", str(made.assessment)]
    monkeypatch.setattr(sys, "argv", argv)
    audit.main()
    return json.loads(made.out.read_text())


def test_identity_only_mode_keeps_manifests_and_never_loads_historical_m548(audit, tmp_path, monkeypatch):
    made = fixture(audit, tmp_path)
    original = audit.np.load
    def checked(path, *args, **kwargs):
        assert "m548" not in str(path).lower()
        return original(path, *args, **kwargs)
    monkeypatch.setattr(audit.np, "load", checked)
    result = run(audit, made, monkeypatch, assessment=False)
    assert result["status"] == "AUTHENTICATED_IDENTITIES_ONLY" and result["scores_available"] is False
    assert "scores" not in result and result["scored_cases"] == 0 and result["total_historical_cases"] == 1
    row = result["cases"][0]
    assert row["status"] == "AUTHENTICATED_IDENTITIES_ONLY"
    assert row["historical_m548_predictions_admitted"] is False
    assert row["combined_case_manifest_sha256"] == audit.sha(made.historical[0] / "combined_case_manifest.json")


def test_positive_scores_use_exact_common_ordered_coordinates_and_labels(audit, tmp_path, monkeypatch):
    made = fixture(audit, tmp_path)
    result = run(audit, made, monkeypatch)
    row = result["cases"][0]
    assert row["cells"] == 2  # (0,1), (1,0); (1,1) is outside FARSITE validity.
    expected = np.array([[0, 1], [1, 0]], dtype=np.int64)
    import hashlib
    assert row["exact_row_col_sha256"] == hashlib.sha256(expected.tobytes()).hexdigest()
    assert result["scores"]["entries"] == 2 and result["scores"]["positives"] == 1
    assert result["scores"]["models"]["farsite_scenario"]["pooled"]["brier"] == 0
    assert result["scores"]["models"]["base_seed0"]["pooled"]["brier"] == pytest.approx(.04)
    assert result["scores_available"] is True and result["all_stored_cases_scored"] is True
    assert result["status"] == "DESCRIPTIVE_MATCHED_SUBSET_COMPLETE" and result["superiority_criteria_pass"] is False
    assert result["native_execution_this_command"] is False
    assert "station" in result["configuration_differences"]["weather"]
    assert "fuel99" in result["configuration_differences"]["boundary"]


def test_hold_retains_all_thirty_available_unavailable_and_failed_historical_rows(audit, tmp_path, monkeypatch):
    made = fixture(audit, tmp_path, ("SCORED", "FAILED", *("UNAVAILABLE",) * 28))
    result = run(audit, made, monkeypatch)
    assert result["status"] == result["assessment_status"] == "HOLD"
    assert result["total_historical_cases"] == len(result["cases"]) == 30
    assert result["scored_cases"] == 1 and result["scores_available"] is True
    assert result["all_stored_cases_scored"] is False and result["superiority_criteria_pass"] is False
    assert len(result["skipped_unavailable_cases"]) == 29
    assert result["assessment_unscored_outcomes"] == made.receipt["failed_or_unavailable"]
    assert result["cases"][1]["status"] == "FAILED" and result["cases"][1]["reason"] == "Synthetic recorded numerical failure"
    assert result["cases"][2]["reason"] == "Synthetic unavailable source support"


@pytest.mark.parametrize("outcomes,empty_farsite", [(("SCORED",), True), (("UNAVAILABLE",), False)])
def test_no_actual_common_entries_has_no_scores_or_success_status(audit, tmp_path, monkeypatch, outcomes, empty_farsite):
    made = fixture(audit, tmp_path, outcomes, empty_farsite=empty_farsite)
    result = run(audit, made, monkeypatch)
    assert result["status"] == "HOLD" and result["scores_available"] is False
    assert result["scored_cases"] == 0 and result["measurement_status"] == "UNAVAILABLE_NO_COMMON_SCORED_MATCHES"
    assert "scores" not in result and result["superiority_criteria_pass"] is False
    assert len(result["skipped_unavailable_cases"]) == 1
    if empty_farsite: assert result["cases"][0]["reason"] == "EMPTY_FARSITE_COMMON_SUPPORT_INTERSECTION"


@pytest.mark.parametrize("tamper", ["missing_case", "changed_case", "missing_receipt", "changed_receipt", "changed_aggregate", "changed_phase"])
def test_missing_or_changed_current_assessment_evidence_refuses(audit, tmp_path, monkeypatch, tamper):
    made = fixture(audit, tmp_path)
    case = made.assessment / "cases/synthetic_case_00.npz"
    receipt = case.with_suffix(".json")
    if tamper == "missing_case": case.unlink()
    if tamper == "changed_case": case.write_bytes(b"changed predictions")
    if tamper == "missing_receipt": receipt.unlink()
    if tamper == "changed_receipt":
        record = json.loads(receipt.read_text()); record["scored_cells"] += 1; write(receipt, record)
    if tamper == "changed_aggregate": (made.assessment / (made.event + ".npz")).write_bytes(b"changed aggregate")
    if tamper == "changed_phase":
        path = made.assessment / "FROZEN_ASSESSMENT.json"
        frozen = json.loads(path.read_text()); frozen["current_phase"]["spotting_source_mode"] = "historical"; write(path, frozen)
    with pytest.raises(ValueError): run(audit, made, monkeypatch)
    assert not made.out.exists()


def resign_historical(audit, directory):
    manifest = json.loads((directory / "combined_case_manifest.json").read_text())
    write(directory / "combined_case_manifest.json", {name: audit.sha(directory / name) for name in manifest})


@pytest.mark.parametrize("tamper,expected", [
    ("missing_elapsed", "HORIZON_OR_CENSOR_EVIDENCE_UNAVAILABLE"),
    ("missing_arrivals", "HORIZON_OR_CENSOR_EVIDENCE_UNAVAILABLE"),
    ("short_native_run", "HORIZON_SHORTER_THAN_REFERENCE_ENDPOINT"),
    ("unknown_sentinel", "CENSOR_OR_ARRIVAL_CONVENTION_UNVERIFIED"),
    ("undocumented_negative", "CENSOR_OR_ARRIVAL_CONVENTION_UNVERIFIED"),
    ("false_endpoint_negative", "CENSOR_ENDPOINT_OCCUPANCY_MISMATCH"),
])
def test_native_horizon_and_right_censor_evidence_must_support_each_endpoint(audit, tmp_path, monkeypatch, tamper, expected):
    made = fixture(audit, tmp_path)
    directory = made.historical[0]
    report_path, prediction_path = directory / "report.json", directory / "farsite_prediction.npz"
    report = json.loads(report_path.read_text())
    with np.load(prediction_path) as source: arrays = {name: source[name].copy() for name in source.files}
    metadata = json.loads(str(arrays["metadata_json"]))
    if tamper == "missing_elapsed": del report["farsite_execution"]["elapsed_minutes"]
    if tamper == "missing_arrivals": del arrays["arrival_minutes"]
    if tamper == "short_native_run": report["farsite_execution"]["elapsed_minutes"] = 30
    if tamper == "unknown_sentinel": metadata["no_burn_value"] = -1
    if tamper == "undocumented_negative": arrays["arrival_minutes"][1, 0] = -1
    if tamper == "false_endpoint_negative": arrays["probability"][0, 0, 0, 1] = 0
    arrays["metadata_json"] = np.array(json.dumps(metadata))
    np.savez_compressed(prediction_path, **arrays); write(report_path, report); resign_historical(audit, directory)
    result = run(audit, made, monkeypatch)
    assert result["status"] == "HOLD" and result["scores_available"] is False and "scores" not in result
    assert result["cases"][0]["reason"] == expected
    assert result["cases"][0]["native_horizon"]["status"] == "UNAVAILABLE"
    assert result["superiority_criteria_pass"] is False


@pytest.mark.parametrize("tamper", ["reordered", "fractional", "label", "aggregate_difference"])
def test_re_signed_case_cannot_change_exact_coordinates_labels_or_aggregate_population(audit, tmp_path, monkeypatch, tamper):
    made = fixture(audit, tmp_path)
    path = made.assessment / "cases/synthetic_case_00.npz"
    with np.load(path) as source: arrays = {name: source[name].copy() for name in source.files}
    if tamper == "reordered": arrays = {name: values[::-1].copy() for name, values in arrays.items()}
    if tamper == "fractional": arrays["row"] = arrays["row"].astype(float) + .1
    if tamper == "label": arrays["y"][0] = 1 - arrays["y"][0]
    if tamper == "aggregate_difference": arrays["p_base_seed0"][0] = .5
    np.savez_compressed(path, **arrays)
    assessment = json.loads((made.assessment / "ASSESSMENT.json").read_text())
    record = assessment["cases"][0]; record["sha256"] = audit.sha(path)
    write(path.with_suffix(".json"), record); write(made.assessment / "ASSESSMENT.json", assessment)
    with pytest.raises(ValueError): run(audit, made, monkeypatch)
    assert not made.out.exists()


@pytest.mark.parametrize("arrival_at,expected_brier", [(60., 0.), (61., .5)])
def test_exact_endpoint_is_inclusive_and_later_arrival_remains_negative_at_endpoint(audit, tmp_path, monkeypatch, arrival_at, expected_brier):
    made = fixture(audit, tmp_path)
    directory = made.historical[0]
    path = directory / "farsite_prediction.npz"
    with np.load(path) as source: arrays = {name: source[name].copy() for name in source.files}
    arrays["arrival_minutes"][0, 1] = arrival_at
    arrays["probability"][0, 0, 0, 1] = float(arrival_at <= 60)
    np.savez_compressed(path, **arrays); resign_historical(audit, directory)
    result = run(audit, made, monkeypatch)
    horizon = result["cases"][0]["native_horizon"]
    assert horizon["status"] == "AVAILABLE" and horizon["native_horizon_minutes"] == horizon["endpoint_minutes"] == 60
    assert horizon["no_burn_value"] == -9999
    assert "finite native horizon" in horizon["right_censoring"]
    assert result["scores"]["models"]["farsite_scenario"]["pooled"]["brier"] == expected_brier
