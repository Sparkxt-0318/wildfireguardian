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
    repo = root / "source"
    split_path = repo / "research/forecast-v2/SPLIT.json"
    write(split_path, dict(held_out=dict(us_2024=[event])))
    registry_path = repo / "research/forecast-v2/BLIND_REGISTRY.json"
    write(registry_path, dict(synthetic_identity_boundary=True))
    audit.REPO = repo
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
                  spotting_source_contract=reporting.F.spotting_source_contract(reporting.REPO, sources),
                  registry=dict(path=str(registry_path.relative_to(repo)), sha256=audit.sha(registry_path)),
                  split_sha256=audit.sha(split_path))
    # Mock only unchanged SC.identities. The audit still performs all receipt,
    # exact-model, source-label, ordered-array and SPLIT membership checks itself.
    identity_calls = []
    def identities(args):
        identity_calls.append(args)
        return json.loads(json.dumps(frozen))
    audit.load_current_scorer = lambda: SimpleNamespace(EXPECTED_MODELS=set(audit.EXPECTED_MODELS), identities=identities)
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
    return SimpleNamespace(data=data, assessment=assessment, out=out, receipt=receipt, historical=historical, event=event,
                           repo=repo, split_path=split_path, frozen=frozen, identity_calls=identity_calls)


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
    assert made.identity_calls == []
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
    assert len(audit.EXPECTED_MODELS) == 16 and set(result["scores"]["models"]) == audit.EXPECTED_MODELS | {"farsite_scenario"}
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


def resign_current(audit, made):
    receipt_path = made.assessment / "ASSESSMENT.json"
    receipt = json.loads(receipt_path.read_text())
    for record in receipt["cases"]:
        if record["status"] == "SCORED":
            record["sha256"] = audit.sha(made.assessment / "cases" / (record["case_id"] + ".npz"))
        write(made.assessment / "cases" / (record["case_id"] + ".json"), record)
    receipt["per_fire_files"] = {name: audit.sha(made.assessment / name) for name in receipt["per_fire_files"]}
    write(receipt_path, receipt)


@pytest.mark.parametrize("change", ["missing_d4", "extra_model"])
@pytest.mark.parametrize("location", ["both", "individual", "aggregate"])
def test_fixed_sixteen_columns_cannot_be_narrowed_or_extended_by_resigned_arrays(audit, tmp_path, monkeypatch, change, location):
    made = fixture(audit, tmp_path)
    paths = {"individual": made.assessment / "cases/synthetic_case_00.npz", "aggregate": made.assessment / (made.event + ".npz")}
    for key, path in paths.items():
        if location != "both" and key != location: continue
        with np.load(path) as source: arrays = {name: source[name].copy() for name in source.files}
        if change == "missing_d4": del arrays["p_d4_seed0"]
        else: arrays["p_unregistered_model"] = arrays["p_base_seed0"].copy()
        np.savez_compressed(path, **arrays)
    resign_current(audit, made)
    with pytest.raises(ValueError, match="fixed 16 probability columns"):
        run(audit, made, monkeypatch)
    assert not made.out.exists()


def rewrite_interval(audit, made, hours):
    """The independent 49-hour probe's same fully consistent re-signing recipe."""
    directory = made.historical[0]
    protocol_path = directory / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    start = pd.Timestamp(protocol["cutoff"]); end = start + pd.Timedelta(hours=hours)
    protocol.update(endpoint=end.isoformat(), hours=hours); write(protocol_path, protocol)
    report_path = directory / "report.json"; report = json.loads(report_path.read_text())
    report["native_clock_verification"].update(end_hhmm=end.hour * 100 + end.minute, duration_minutes=hours * 60)
    report["farsite_execution"].update(elapsed_minutes=hours * 60, native_clock_verification=report["native_clock_verification"],
                                         endpoint_selection=f"0 <= arrival <= {hours * 60}")
    write(report_path, report)
    path = directory / "farsite_prediction.npz"
    with np.load(path) as source: arrays = {name: source[name].copy() for name in source.files}
    metadata = json.loads(str(arrays["metadata_json"])); metadata["exact_duration_minutes"] = hours * 60
    arrays["metadata_json"] = np.array(json.dumps(metadata)); np.savez_compressed(path, **arrays)
    path = made.data / "perimeters" / made.event / "states.npz"
    with np.load(path) as source: arrays = {name: source[name].copy() for name in source.files}
    arrays["times"] = np.array([start.isoformat(), end.isoformat()]); np.savez_compressed(path, **arrays)
    path = made.assessment / (made.event + ".npz")
    with np.load(path) as source: arrays = {name: source[name].copy() for name in source.files}
    arrays["hours"] = np.array([float(hours)]); np.savez_compressed(path, **arrays)
    receipt_path = made.assessment / "ASSESSMENT.json"; receipt = json.loads(receipt_path.read_text())
    receipt["cases"][0]["case"].update(endpoint=end.isoformat(), hours=hours); write(receipt_path, receipt)
    resign_current(audit, made); resign_historical(audit, directory)


@pytest.mark.parametrize("hours,eligible", [(48, True), (49, False)])
def test_frozen_interval_cap_is_separate_from_a_sufficient_native_horizon(audit, tmp_path, monkeypatch, hours, eligible):
    made = fixture(audit, tmp_path)
    rewrite_interval(audit, made, hours)
    result = run(audit, made, monkeypatch)
    row = result["cases"][0]
    assert row["native_horizon"]["status"] == "AVAILABLE"
    assert row["native_horizon"]["native_horizon_minutes"] == hours * 60
    assert result["scores_available"] is eligible
    if eligible:
        assert row["frozen_cohort_eligibility"]["status"] == "ELIGIBLE"
        assert result["current_case_admission_pass"] is True
        assert result["status"] == "DESCRIPTIVE_MATCHED_SUBSET_COMPLETE"
    else:
        assert result["status"] == "HOLD" and "scores" not in result
        assert row["reason"] == "HISTORICAL_INTERVAL_OUTSIDE_FROZEN_0_TO_48H_POLICY"
        assert row["current_case_admission"]["reason"] == "CURRENT_CASE_INTERVAL_OUTSIDE_FROZEN_0_TO_48H_POLICY"
        assert result["rejected_current_cases"] == [row["current_case_admission"]]
        assert result["superiority_criteria_pass"] is False


@pytest.mark.parametrize("hours", [0, -1])
def test_nonpositive_current_intervals_are_retained_as_rejected_not_scored(audit, tmp_path, monkeypatch, hours):
    made = fixture(audit, tmp_path)
    path = made.assessment / "ASSESSMENT.json"; receipt = json.loads(path.read_text())
    case = receipt["cases"][0]["case"]
    case.update(hours=hours, endpoint=(pd.Timestamp(case["cutoff"]) + pd.Timedelta(hours=hours)).isoformat())
    write(path, receipt); resign_current(audit, made)
    result = run(audit, made, monkeypatch)
    assert result["status"] == "HOLD" and result["scores_available"] is False
    assert result["rejected_current_cases"][0]["reason"] == "CURRENT_CASE_INTERVAL_OUTSIDE_FROZEN_0_TO_48H_POLICY"


@pytest.mark.parametrize("change", ["not_in_split", "country", "year"])
def test_current_case_population_requires_authenticated_split_membership_and_us2024_catalog(audit, tmp_path, monkeypatch, change):
    made = fixture(audit, tmp_path)
    catalog_path = made.data / "environment/events.json"; catalog = json.loads(catalog_path.read_text())
    if change == "not_in_split":
        extra = dict(catalog[0], id="SYNTHETIC_US2024_OUTSIDE_SPLIT"); catalog.append(extra)
        path = made.assessment / "ASSESSMENT.json"; receipt = json.loads(path.read_text())
        receipt["cases"][0]["case"]["event"] = extra["id"]; write(path, receipt); resign_current(audit, made)
    if change == "country": catalog[0]["country"] = "KR"
    if change == "year": catalog[0]["year"] = 2025
    write(catalog_path, catalog)
    result = run(audit, made, monkeypatch)
    assert result["status"] == "HOLD" and result["scores_available"] is False
    assert result["rejected_current_cases"][0]["reason"] == "CURRENT_CASE_OUTSIDE_FROZEN_US2024_POPULATION"
    assert result["superiority_criteria_pass"] is False


def test_identity_delegation_uses_exact_current_verifier_arguments_before_case_loading(audit, tmp_path, monkeypatch):
    made = fixture(audit, tmp_path)
    run(audit, made, monkeypatch)
    assert len(made.identity_calls) == 1
    args = made.identity_calls[0]
    assert vars(args) == dict(data=made.data, run=made.assessment.parent, cohort="us2024",
                             registry=made.repo / made.frozen["registry"]["path"])


@pytest.mark.parametrize("failure", ["verifier_refusal", "frozen_identity_mismatch", "split_bytes_changed"])
def test_current_identity_or_split_refusal_happens_before_loading_any_case_arrays(audit, tmp_path, monkeypatch, failure):
    made = fixture(audit, tmp_path)
    if failure == "verifier_refusal":
        def identities(args): raise ValueError("synthetic identity verifier refusal")
        audit.load_current_scorer = lambda: SimpleNamespace(EXPECTED_MODELS=set(audit.EXPECTED_MODELS), identities=identities)
    if failure == "frozen_identity_mismatch":
        audit.load_current_scorer = lambda: SimpleNamespace(EXPECTED_MODELS=set(audit.EXPECTED_MODELS), identities=lambda args: dict(made.frozen, seed=99))
    if failure == "split_bytes_changed": made.split_path.write_text(made.split_path.read_text() + " ")
    monkeypatch.setattr(audit.np, "load", lambda *args, **kwargs: pytest.fail("Unverified identity reached prediction arrays"))
    with pytest.raises(ValueError): run(audit, made, monkeypatch)
    assert not made.out.exists()


def test_six_authenticated_split_events_are_the_declared_population_with_available_hold_subset(audit, tmp_path, monkeypatch):
    made = fixture(audit, tmp_path)
    expected = [made.event, *(f"SYNTHETIC_US2024_{index}" for index in range(5))]
    write(made.split_path, dict(held_out=dict(us_2024=expected)))
    made.frozen["split_sha256"] = audit.sha(made.split_path)
    frozen_path = made.assessment / "FROZEN_ASSESSMENT.json"; write(frozen_path, made.frozen)
    path = made.assessment / "ASSESSMENT.json"; receipt = json.loads(path.read_text())
    receipt.update(events=expected, status="HOLD", frozen_sha256=audit.sha(frozen_path),
                   failed_or_unavailable=[dict(event=event, reason="No eligible synthetic source intervals") for event in expected[1:]])
    receipt["cases"][0]["assessment_sha256"] = receipt["frozen_sha256"]
    write(path, receipt); resign_current(audit, made)
    result = run(audit, made, monkeypatch)
    assert result["scores_available"] is True and result["current_case_admission_pass"] is True
    assert result["status"] == "HOLD" and result["superiority_criteria_pass"] is False
    receipt["events"] = expected[:-1]; write(path, receipt)
    with pytest.raises(ValueError, match="exactly the frozen US2024"):
        run(audit, made, monkeypatch)
