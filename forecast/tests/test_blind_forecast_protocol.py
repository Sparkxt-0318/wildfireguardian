"""Mechanism fixtures for future blind-test custody, never study evidence."""
import importlib.util
import os
import pickle
import subprocess
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest
import torch


@pytest.fixture
def blind():
    path = Path(__file__).resolve().parents[2] / "research/forecast-v2/scripts/blind_test.py"
    spec = importlib.util.spec_from_file_location("blind_protocol_test", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_baseline_terrain(path, event):
    import rasterio
    from affine import Affine
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", count=1, dtype="float32", crs=event["epsg"],
                       height=event["height"], width=event["width"], transform=Affine(*event["transform"])) as source:
        source.write(np.arange(event["height"] * event["width"], dtype=np.float32).reshape(1, event["height"], event["width"]))


def refresh_inventory_fixture(blind, root, cohort):
    manifest = dict(environment_sha256={str(p.relative_to(root)): blind.sha(p)
                                        for p in (root / "environment").rglob("*") if p.is_file()},
                    states_sha256={p.parent.name: blind.sha(p) for p in (root / "perimeters").rglob("states.npz")},
                    release=dict(path="publisher.zip", sha256=blind.sha(root / "publisher.zip"),
                                 first_public_release_attestation=dict(path="attestation.json", sha256=blind.sha(root / "attestation.json"))))
    path = root / "inventory-input.json"
    blind.write(path, manifest)
    cohort["input_sha256"] = {str(p.relative_to(root)): blind.sha(p) for p in root.rglob("*") if p.is_file() and p.name not in
                              {"documentary-clearance.json", "signed-synthetic-statement.txt", "public_osf_registration.txt",
                               "publisher_first_release_chronology.txt", "no_pre_registration_source_access.txt"}}
    cohort["inventory"] = dict(path="inventory-input.json", sha256=blind.sha(path), exclusions=[])


@pytest.fixture
def registered(blind, tmp_path, monkeypatch):
    repo, root = tmp_path / "repo", tmp_path / "inputs"
    repo.mkdir()
    (root / "environment").mkdir(parents=True)
    monkeypatch.setattr(blind, "REPO", repo)
    names = ["forecast/wildfire/example.py", "research/forecast-v2/scripts/pipeline.py",
             "research/forecast-v2/scripts/blind_test.py", "research/forecast-v2/scripts/blind_inventory.py",
             "research/forecast-v2/scripts/freeze_registry.py", "research/forecast-v2/SPLIT.json"]
    for name in names:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    checkpoint = repo / "fixture.pt"
    checkpoint.write_bytes(b"fixture checkpoint, no scientific model")
    monkeypatch.setattr(blind, "C651_SHA", blind.sha(checkpoint))
    model = dict(path="fixture.pt", sha256=blind.sha(checkpoint))
    registry = dict(status="FROZEN", models={n: model for n in blind.MODEL_NAMES}, logistic=model,
                    selected_model="base_seed0", best_dilation_hours_per_cell=4, dependency_versions=blind.runtime_dependencies(),
                    producer_source_sha256={n: blind.sha(repo / n) for n in names})
    registry_path = repo / "registry.json"
    blind.write(registry_path, registry)
    events = [dict(id="fixture", year=2026, country="US", t0_utc="2026-01-01T00:00:00Z",
                   start_utc="2026-01-01T00:00:00Z", end_utc="2026-01-03T00:00:00Z", height=1, width=4,
                   epsg=32610, transform=[375, 0, 500000, 0, -375, 5000000])]
    blind.write(root / "environment/events.json", events)
    terrain = root / "baseline-terrain/fixture/elevation_m_375m.tif"
    write_baseline_terrain(terrain, events[0])
    states = root / "perimeters/fixture/states.npz"
    states.parent.mkdir(parents=True)
    np.savez(states, times=np.array(["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"]),
             states=np.array([[[1, 0, 0, 0]], [[1, 1, 0, 1]]], dtype=np.uint8))
    cohort = dict(registry_sha256=blind.sha(registry_path), source_release_utc="2026-03-01T00:00:00Z",
                  registration=dict(url="https://osf.io/fixture", registered_utc="2026-02-01T00:00:00Z",
                                    registry_sha256=blind.sha(registry_path)),
                  input_sha256={str(p.relative_to(root)): blind.sha(p) for p in root.rglob("*") if p.is_file()})
    (root / "publisher.zip").write_bytes(b"synthetic archive, numerical protocol fixture only")
    blind.write(root / "attestation.json", dict(claim="fixture local attestation, not external proof"))
    refresh_inventory_fixture(blind, root, cohort)

    def validate_fixture_inventory(input_root, manifest_path, expected_manifest_sha256):
        assert blind.sha(manifest_path) == expected_manifest_sha256
        catalog = json.loads((input_root / "environment/events.json").read_text())
        cases, incidents = [], []
        for event in catalog:
            if event["country"] != "US" or event["year"] != 2026:
                continue
            with np.load(input_root / f"perimeters/{event['id']}/states.npz") as data:
                times = list(blind.pd.to_datetime(data["times"], utc=True))
            incidents.append(dict(event=event["id"], record_count=len(times), first_survey_year=times[0].year))
            cases.extend(dict(event=event["id"], cutoff=times[i].isoformat(), endpoint=times[j].isoformat(),
                              year=2026, reference_kind="nirops_mapped_extent")
                         for i, j, _ in blind.consecutive_intervals(times, 48))
        return dict(status="LOCAL_INVENTORY_VALIDATED_EXTERNAL_RELEASE_UNVERIFIED", cases=cases, exclusions=[],
                    raw_inventory=dict(incidents=incidents), manifest_sha256=expected_manifest_sha256,
                    release_identity=dict(public_release_utc=cohort["source_release_utc"],
                                          publisher_url="https://example.invalid/immutable-synthetic-release/v1",
                                          archive_sha256=blind.sha(input_root / "publisher.zip")),
                    execution_status="NOT_READY_FOR_2026_EXECUTION")

    monkeypatch.setattr(blind, "load_inventory", lambda: SimpleNamespace(validate_inventory=validate_fixture_inventory))
    cases, _ = blind.reference_cases(root, cohort)
    cohort["cases"] = cases
    cohort_path = repo / "cohort.json"
    blind.write(cohort_path, cohort)
    return repo, root, registry_path, cohort_path, registry, cohort


def test_complete_reference_cohort_validates_and_changed_inputs_refuse(blind, registered):
    repo, root, registry, cohort, _, _ = registered
    _, _, references = blind.validate(registry, cohort, repo, root)
    assert len(references) == 1
    (root / "environment/events.json").write_text("[]")
    with pytest.raises(ValueError, match="Input identity changed|Blind input bytes changed"):
        blind.validate(registry, cohort, repo, root)


@pytest.mark.parametrize("change", ["missing_model", "wrong_primary", "missing_source", "late_registration", "missing_case", "false_year"])
def test_registry_and_source_cohort_refuse_incomplete_attestations(blind, registered, change):
    repo, root, rp, cp, registry, cohort = registered
    if change == "missing_model": registry["models"].pop("ellipse_seed0")
    if change == "wrong_primary": registry["selected_model"] = "c651_mc"
    if change == "missing_source": registry["producer_source_sha256"].pop("forecast/wildfire/example.py")
    blind.write(rp, registry)
    cohort["registry_sha256"] = blind.sha(rp)
    cohort["registration"]["registry_sha256"] = blind.sha(rp)
    if change == "late_registration": cohort["registration"]["registered_utc"] = "2027-02-01T00:00:00Z"
    if change == "missing_case": cohort["cases"] = []
    if change == "false_year": cohort["cases"][0]["year"] = 2025
    blind.write(cp, cohort)
    with pytest.raises(ValueError): blind.validate(rp, cp, repo, root)


def test_operational_us_first_survey_year_does_not_assert_physical_ignition_year(blind, registered):
    _, root, _, _, _, cohort = registered
    path = root / "environment/events.json"
    events = json.loads(path.read_text())
    events[0]["t0_utc"] = "2025-12-31T00:00:00Z"
    blind.write(path, events)
    refresh_inventory_fixture(blind, root, cohort)
    cases, _ = blind.reference_cases(root, cohort)
    assert len(cases) == 1
    assert cases[0]["year"] == 2026


def test_unhashed_extra_prediction_cannot_enter_score(blind, registered, tmp_path):
    repo, root, rp, cp, registry, cohort = registered
    entries = tmp_path / "predictions"
    (entries / "cases").mkdir(parents=True)
    record = dict(case=cohort["cases"][0], status="UNAVAILABLE")
    blind.write(entries / "RECEIPT.json", dict(receipt_version=blind.RECEIPT_VERSION, validated_identity=blind.validation_identity(registry, cohort),
                                                        inventory_validation=blind.inventory_admission(root, cohort),
                                                        registry_sha256=blind.sha(rp), cohort_sha256=blind.sha(cp), cases=[record]))
    np.savez(entries / "cases/unlisted.npz", y=[1])
    with pytest.raises(ValueError, match="Unlisted"):
        blind.score(SimpleNamespace(registry=rp, cohort=cp, model_root=repo, input_root=root,
                                    entries=entries, out=tmp_path / "scores.json"))


def test_primary_gate_requires_fire_count_both_comparisons_and_calibration(blind):
    result = dict(fires=list(range(10)), models={}, paired={})
    for name, prediction in [("base_seed0", .02), ("persistence", 0.), ("dilation_best", 0.)]:
        result["models"][name] = dict(pooled=dict(lowest_bin=dict(count=10, mean_prediction=prediction, observed_frequency=.02)))
    for ref in ("persistence", "dilation_best"):
        result["paired"]["base_seed0__vs__" + ref] = dict(percentile_95_interval=[-.02, -.01])
    assert blind.primary_decision(result, "base_seed0", complete=True, clearance_present=True)["statistical_superiority_criteria_pass"]
    result["fires"].pop()
    assert not blind.primary_decision(result, "base_seed0", complete=True, clearance_present=True)["statistical_superiority_criteria_pass"]
    result["fires"].append(9)
    result["paired"]["base_seed0__vs__dilation_best"]["percentile_95_interval"] = [-.02, .001]
    assert not blind.primary_decision(result, "base_seed0", complete=True, clearance_present=True)["statistical_superiority_criteria_pass"]


def test_declared_model_root_cannot_authenticate_a_different_import_tree(blind, registered, tmp_path):
    _, root, registry, cohort, _, _ = registered
    with pytest.raises(ValueError, match="exact verified source tree"):
        blind.validate(registry, cohort, tmp_path, root)


def documentary_fixture(blind, root, registry, cohort, scope="pre_run_registration_first_release_and_access"):
    inventory = blind.inventory_admission(root, cohort)
    released = blind.pd.Timestamp(cohort["source_release_utc"])
    evidence = []
    purposes = ["public_osf_registration", "publisher_first_release_chronology", "no_pre_registration_source_access"]
    if scope == "post_score_independent_relocated_replay_and_claim":
        purposes += ["independent_relocated_replay_execution", "primary_claim_and_completeness"]
    for purpose in purposes:
        path = root / (purpose + ".txt")
        path.write_text("Synthetic documentary evidence only, no actual external fact is asserted: " + purpose)
        evidence.append(dict(path=path.name, sha256=blind.sha(path), immutable_url="https://example.invalid/immutable/" + purpose,
                             purpose=purpose))
    attestation = root / "signed-synthetic-statement.txt"
    attestation.write_text("Synthetic signed attestation fixture, not a genuine signature or review")
    return dict(schema=blind.DOCUMENTARY_SCHEMA, scope=scope, decision=blind.DOCUMENTARY_DECISION,
                bindings=blind.clearance_bindings(registry, cohort),
                verifier=dict(name="Independent synthetic reviewer", affiliation="Fixture organization",
                              independence_statement="Synthetic reviewer is independent of the synthetic producer"),
                attestation=dict(path=attestation.name, sha256=blind.sha(attestation),
                                 signature_description="Synthetic signature description, no cryptographic authenticity claimed"),
                evidence_reviewed=evidence, limits=["Synthetic mechanism fixture; external truth is not established"],
                registration=dict(immutable_url=cohort["registration"]["url"],
                                  registry_artifact_sha256=cohort["registry_sha256"],
                                  registered_utc=cohort["registration"]["registered_utc"]),
                publisher_release=dict(immutable_url=inventory["release_identity"]["publisher_url"],
                                       archive_sha256=inventory["release_identity"]["archive_sha256"],
                                       public_release_utc=cohort["source_release_utc"]),
                reviewed_utc=(released + blind.pd.Timedelta(hours=1)).isoformat(),
                signed_utc=(released + blind.pd.Timedelta(hours=2)).isoformat())


def attach_documentary_fixture(blind, registered):
    _, root, _, cp, registry, cohort = registered
    review = documentary_fixture(blind, root, registry, cohort)
    path = root / "documentary-clearance.json"
    blind.write(path, review)
    cohort["documentary_clearance"] = dict(path=path.name, sha256=blind.sha(path))
    blind.write(cp, cohort)
    return path, review


@pytest.fixture
def numerical_fixture(blind, registered, monkeypatch):
    """Mock only numerical producers; keep real validation, files, receipts and scoring."""
    repo, root, rp, cp, registry, cohort = registered
    attach_documentary_fixture(blind, registered)
    names = tuple(["fixture_channel"])

    class Environment:
        def __init__(self, data_root, cache, input_sha256):
            assert data_root == root / "environment"
            assert input_sha256 == cohort["input_sha256"]
            self.names = names

        def at(self, event, hour):
            return np.zeros((1, 1, 4), dtype=np.float32)

        def residence(self, event):
            return None

        def terrain_gradient(self, event):
            return np.zeros((1, 4)), np.zeros((1, 4))

    supported = np.array([[True, True, True, False]])
    calls = dict(mc=0, deterministic=0)

    def sample_forecast(model, sample, **kwargs):
        calls["deterministic"] += 1
        return torch.full((1, 4), .1), torch.from_numpy(supported)

    def monte_carlo(*args):
        calls["mc"] += 1
        return np.full((1, 4), .1), supported.copy()

    pipeline = SimpleNamespace(Environment=Environment, load_structured=lambda path: object(),
                               sample_forecast=sample_forecast, c651_monte_carlo=monte_carlo,
                               logistic_predict=lambda *args: np.full((1, 4), .1))
    monkeypatch.setattr(blind, "heavy_lock", lambda: (repo / "synthetic-heavy.lock").open("a+"))
    monkeypatch.setattr(blind, "load_pipeline", lambda: pipeline)
    monkeypatch.setattr(blind, "load_model", lambda *args, **kwargs: SimpleNamespace(predictor=object()))
    monkeypatch.setattr(blind.pickle, "loads", lambda value: object())
    return calls


def produce(blind, registered, tmp_path):
    repo, root, rp, cp, _, _ = registered
    entries = tmp_path / "predictions"
    blind.run(SimpleNamespace(registry=rp, cohort=cp, model_root=repo, input_root=root, out=entries))
    return SimpleNamespace(registry=rp, cohort=cp, model_root=repo, input_root=root,
                           entries=entries, out=tmp_path / "scores.json")


def rewrite_prediction(blind, args, change):
    receipt_path = args.entries / "RECEIPT.json"
    receipt = json.loads(receipt_path.read_text())
    record = next(r for r in receipt["cases"] if r["status"] == "SCORED")
    path = args.entries / record["file"]
    with np.load(path, allow_pickle=False) as data:
        arrays = {name: data[name].copy() for name in data.files}
    change(arrays, record)
    np.savez_compressed(path, **arrays)
    record["sha256"] = blind.sha(path)
    blind.write(receipt_path, receipt)


def test_validated_run_scores_source_bound_support_without_mc_replay(blind, registered, numerical_fixture, tmp_path):
    args = produce(blind, registered, tmp_path)
    assert numerical_fixture["mc"] == 1
    blind.score(args)
    assert numerical_fixture["mc"] == 1
    assert numerical_fixture["deterministic"] == 16
    result = json.loads(args.out.read_text())
    assert result["complete_cohort_pass"]
    assert result["results"]["nirops_mapped_extent"]["entries"] == 2
    assert not result["results"]["nirops_mapped_extent"]["decision"]["statistical_superiority_criteria_pass"]


@pytest.mark.parametrize("tamper", ["fractional", "integral_float", "out_of_bounds", "reorder", "omit", "add", "label",
                                    "duplicate", "missing_model", "extra_model", "nonfinite", "probability_range", "counts"])
def test_resigned_predictions_cannot_change_the_reference_population(blind, registered, numerical_fixture, tmp_path, tamper):
    args = produce(blind, registered, tmp_path)

    def change(arrays, record):
        if tamper == "fractional": arrays["row"] = arrays["row"].astype(float) + .25
        if tamper == "integral_float": arrays["row"] = arrays["row"].astype(float)
        if tamper == "out_of_bounds": arrays["col"][0] = 100000
        if tamper == "reorder":
            for name in arrays: arrays[name] = arrays[name][::-1]
        if tamper == "omit":
            for name in arrays: arrays[name] = arrays[name][:-1]
            record["scored_cells"] -= 1
            record["excluded_cells"] += 1
        if tamper == "add":
            for name in arrays: arrays[name] = np.r_[arrays[name], arrays[name][-1]]
            arrays["col"][-1] = 3
            record["scored_cells"] += 1
            record["excluded_cells"] -= 1
        if tamper == "label": arrays["y"] = 1 - arrays["y"]
        if tamper == "duplicate": arrays["col"][1] = arrays["col"][0]
        if tamper == "missing_model": arrays.pop("p_base_seed0")
        if tamper == "extra_model": arrays["p_unregistered"] = arrays["p_base_seed0"]
        if tamper == "nonfinite": arrays["p_base_seed0"][0] = np.nan
        if tamper == "probability_range": arrays["p_base_seed0"][0] = 1.1
        if tamper == "counts": record["reference_cells"] += 1

    rewrite_prediction(blind, args, change)
    with pytest.raises(ValueError):
        blind.score(args)


def test_score_revalidates_source_inputs_before_loading_models(blind, registered, numerical_fixture, tmp_path, monkeypatch):
    args = produce(blind, registered, tmp_path)
    (args.input_root / "environment/events.json").write_text("[]")
    monkeypatch.setattr(blind, "load_pipeline", lambda: pytest.fail("invalid inputs reached numerical producer"))
    with pytest.raises(ValueError, match="Blind input bytes changed"):
        blind.score(args)


@pytest.mark.parametrize("tamper", ["missing_validation", "old_protocol", "source_identity", "checkpoint_identity", "input_identity"])
def test_score_refuses_receipt_without_the_same_validated_identity(blind, registered, numerical_fixture, tmp_path, tamper):
    args = produce(blind, registered, tmp_path)
    path = args.entries / "RECEIPT.json"
    receipt = json.loads(path.read_text())
    if tamper == "missing_validation": receipt.pop("validated_identity")
    if tamper == "old_protocol": receipt.pop("receipt_version")
    if tamper == "source_identity": receipt["validated_identity"]["producer_source_sha256"] = {}
    if tamper == "checkpoint_identity": receipt["validated_identity"]["model_sha256"]["base_seed0"] = "0" * 64
    if tamper == "input_identity": receipt["validated_identity"]["input_sha256"] = {}
    blind.write(path, receipt)
    with pytest.raises(ValueError, match="Validated predictions"):
        blind.score(args)


def test_incomplete_cohort_hard_gates_every_primary_criterion(blind):
    result = dict(fires=list(range(10)), models={}, paired={})
    for name, prediction in [("base_seed0", .02), ("persistence", 0.), ("dilation_best", 0.)]:
        result["models"][name] = dict(pooled=dict(lowest_bin=dict(count=10, mean_prediction=prediction, observed_frequency=.02)))
    for ref in ("persistence", "dilation_best"):
        result["paired"]["base_seed0__vs__" + ref] = dict(percentile_95_interval=[-.02, -.01])
    decision = blind.primary_decision(result, "base_seed0", complete=False)
    assert not decision["complete_cohort_pass"]
    assert not any(decision["brier_comparisons_pass"].values())
    assert not decision["calibration_pass"]
    assert not decision["minimum_fire_count_pass"]
    assert not decision["statistical_superiority_criteria_pass"]
    assert all(decision["descriptive_subset_criteria"]["brier_comparisons"].values())
    assert decision["descriptive_subset_criteria"]["calibration"]
    assert decision["descriptive_subset_criteria"]["minimum_fire_count"]


def test_score_with_failed_case_retains_descriptive_subset_without_promotion(blind, registered, numerical_fixture, tmp_path):
    repo, root, rp, cp, registry, cohort = registered
    events_path = root / "environment/events.json"
    events = json.loads(events_path.read_text())
    state = root / "perimeters/fixture/states.npz"
    terrain = root / "baseline-terrain/fixture/elevation_m_375m.tif"
    for i in range(1, 11):
        name = f"fixture_{i}"
        events.append(dict(events[0], id=name))
        for source, relative in [(state, f"perimeters/{name}/states.npz"),
                                 (terrain, f"baseline-terrain/{name}/elevation_m_375m.tif")]:
            path = root / relative
            path.parent.mkdir(parents=True)
            path.write_bytes(source.read_bytes())
            cohort["input_sha256"][relative] = blind.sha(path)
    blind.write(events_path, events)
    refresh_inventory_fixture(blind, root, cohort)
    cohort["cases"], _ = blind.reference_cases(root, cohort)
    blind.write(cp, cohort)
    attach_documentary_fixture(blind, registered)
    args = produce(blind, registered, tmp_path)
    receipt_path = args.entries / "RECEIPT.json"
    receipt = json.loads(receipt_path.read_text())
    record = receipt["cases"][-1]
    (args.entries / record["file"]).unlink()
    record.update(status="FAILED", reason="synthetic failure")
    record.pop("file")
    record.pop("sha256")
    blind.write(receipt_path, receipt)
    # Make the selected model perfect enough for both subset comparisons and
    # lowest-bin calibration, so incompleteness is the only blocking gate.
    for record in receipt["cases"][:-1]:
        path = args.entries / record["file"]
        with np.load(path, allow_pickle=False) as data:
            arrays = {name: data[name].copy() for name in data.files}
        arrays["p_base_seed0"] = np.where(arrays["y"], .9, 0.)
        arrays["p_persistence"] = np.zeros(2)
        arrays["p_dilation_best"] = np.zeros(2)
        np.savez_compressed(path, **arrays)
        record["sha256"] = blind.sha(path)
    blind.write(receipt_path, receipt)
    before = numerical_fixture["mc"]
    blind.score(args)
    assert numerical_fixture["mc"] == before
    output = json.loads(args.out.read_text())
    result = output["results"]["nirops_mapped_extent"]
    assert len(result["fires"]) == 10
    assert result["status"] == "INCOMPLETE_COHORT"
    assert result["statistics_scope"] == "descriptive_scored_subset_only"
    decision = result["decision"]
    assert all(decision["descriptive_subset_criteria"]["brier_comparisons"].values())
    assert decision["descriptive_subset_criteria"]["calibration"]
    assert decision["descriptive_subset_criteria"]["minimum_fire_count"]
    assert not any(decision["brier_comparisons_pass"].values())
    assert not decision["statistical_superiority_criteria_pass"]
    assert not output["complete_cohort_pass"]
    assert not output["superiority_claim_permitted"]


@pytest.mark.parametrize("tamper", ["source", "checkpoint", "year", "case_evidence_kind", "unavailable_with_support"])
def test_scoring_rechecks_admission_instead_of_trusting_a_resigned_receipt(blind, registered, numerical_fixture, tmp_path, monkeypatch, tamper):
    args = produce(blind, registered, tmp_path)
    receipt_path = args.entries / "RECEIPT.json"
    receipt = json.loads(receipt_path.read_text())
    if tamper == "source":
        (args.model_root / "forecast/wildfire/example.py").write_text("changed producer")
    if tamper == "checkpoint":
        (args.model_root / "fixture.pt").write_bytes(b"changed checkpoint")
    if tamper == "year":
        cohort = json.loads(args.cohort.read_text())
        cohort["cases"][0]["year"] = 1999
        blind.write(args.cohort, cohort)
        receipt["cohort_sha256"] = blind.sha(args.cohort)
        receipt["cases"][0]["case"] = cohort["cases"][0]
    if tamper == "case_evidence_kind":
        receipt["cases"][0]["case"]["reference_kind"] = "korean_arrival_reconstruction"
    if tamper == "unavailable_with_support":
        record = receipt["cases"][0]
        (args.entries / record.pop("file")).unlink()
        record.pop("sha256")
        record["status"] = "UNAVAILABLE"
    blind.write(receipt_path, receipt)
    with pytest.raises(ValueError):
        blind.score(args)


@pytest.fixture
def freezer():
    path = Path(__file__).resolve().parents[2] / "research/forecast-v2/scripts/freeze_registry.py"
    spec = importlib.util.spec_from_file_location("blind_registry_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fit_coverage_module(freezer):
    path = Path(freezer.__file__).with_name("audit_fit_coverage.py")
    spec = importlib.util.spec_from_file_location("fit_coverage_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def freeze_inputs(freezer, tmp_path, monkeypatch):
    from wildfire.survival import PerimeterSample
    import rasterio
    from affine import Affine
    coverage = fit_coverage_module(freezer)
    root = tmp_path / "freeze-repo"
    run = root / "forecast/runs/synthetic"
    inputs, caches = tmp_path / "synthetic-fit-inputs", tmp_path / "synthetic-fit-work"
    evidence = root / "research/forecast-v2"
    script_names = ["pipeline", "blind_test", "blind_inventory", "freeze_registry", "audit_fit_coverage", "score_cohorts", "run_campaign"]
    for relative in ["forecast/wildfire/module.py", "forecast/wildfire/nested/config.json", "forecast/pyproject.toml",
                     "forecast/documents/preregistration_blind_test.md", "research/forecast-v2/RUN_PROTOCOL.json",
                     *(f"research/forecast-v2/scripts/{n}.py" for n in script_names)]:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic source/configuration")
    # Exact production source is evidence for the historical schedule inference;
    # no production input, checkpoint, result or score is read.
    source_repo = Path(__file__).resolve().parents[2]
    for relative in ["research/forecast-v2/scripts/pipeline.py", "forecast/wildfire/survival.py",
                     "research/forecast-v2/scripts/audit_fit_coverage.py", "research/forecast-v2/scripts/audit_caches.py"]:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((source_repo / relative).read_bytes())
    us, kr = ["synthetic_fit", "synthetic_fit_second"], ["synthetic_kr", "synthetic_kr_zero"]
    split = dict(fit=dict(us_perimeter_and_kriged=us, korean_kriged_only=kr))
    (evidence / "SPLIT.json").write_text(json.dumps(split))
    metadata = [dict(id=name, start_utc="2020-01-01T00:00:00Z", end_utc="2020-01-03T00:00:00Z",
                     t0_utc="2020-01-01T00:30:00Z" if name == "synthetic_kr" else "2020-01-01T00:00:00Z")
                for name in us + kr]
    (inputs / "environment").mkdir(parents=True)
    (inputs / "environment/events.json").write_text(json.dumps(metadata))
    perimeter_manifest = dict(events={})
    for name in us:
        path = inputs / f"perimeters/{name}/states.npz"
        path.parent.mkdir(parents=True)
        np.savez(path, times=np.array(["2020-01-01T00:00:00Z", "2020-01-01T12:00:00Z", "2020-01-02T00:00:00Z"]),
                 states=np.array([[[1, 0], [0, 0]], [[1, 1], [0, 0]], [[1, 1], [1, 0]]], dtype=np.uint8))
        perimeter_manifest["events"][name] = dict(states_sha256=coverage.sha(path))
    (inputs / "perimeters/PERIMETER_MANIFEST.json").write_text(json.dumps(perimeter_manifest))
    for name in us + kr:
        for filename in ("arrival_time_hours.tif", "kriging_std_hours.tif"):
            path = inputs / f"environment/regions/{name}/{filename}"
            path.parent.mkdir(parents=True, exist_ok=True)
            values = np.array([[0, 12], [24, 36]], dtype=np.float32) if filename.startswith("arrival") else np.ones((2, 2), np.float32)
            if name == "synthetic_kr_zero" and filename.startswith("arrival"): values[:] = np.nan
            with rasterio.open(path, "w", driver="GTiff", height=2, width=2, count=1, dtype="float32", nodata=np.nan,
                               crs=32610, transform=Affine(375, 0, 500000, 0, -375, 5000000)) as raster:
                raster.write(values, 1)
    extraction = inputs / "EXTRACTION_MANIFEST.json"
    extraction.write_text(json.dumps(dict(members=[dict(path=str(p.relative_to(inputs)), sha256=coverage.sha(p))
                                                   for p in (inputs / "environment").rglob("*") if p.is_file()])))
    (inputs / "BASELINE_TERRAIN_MANIFEST.json").write_text(json.dumps(dict(files=[])))
    (evidence / "RUN_PROTOCOL.json").write_text(json.dumps(dict(data_manifest_sha256=coverage.sha(extraction))))
    expected = coverage.expected_membership(root, inputs)
    source = coverage.producer_sources(root)
    groups, audit_rows = {}, []
    for kind, ledger in expected["ledger"].items():
        for event, entry in ledger.items():
            samples = []
            for case in entry["cases"]:
                hours = (coverage._stamp(case["endpoint"]) - coverage._stamp(case["cutoff"])).total_seconds() / 3600
                samples.append(PerimeterSample(event, case["cutoff"], hours, np.zeros((1, 2, 2), np.float32),
                    np.array([[True, False], [False, False]]), np.array([[True, True], [False, False]]),
                    np.array([[False, True], [True, True]]), np.ones((2, 2)), np.zeros((2, 2)), kind=kind,
                    meta=dict(t2=case["endpoint"]) if kind == "perimeter" else {}))
            prefix = "perimeter_crop" if kind == "perimeter" else "kriged_utc_v2"
            path = caches / f"samples/{prefix}_first0_{event}.pkl"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(pickle.dumps(samples, protocol=5))
            value_id = coverage.sample_list_identity(samples)
            audit_rows.append(dict(kind="sample-list", cache=str(path), cache_sha256=coverage.sha(path), event=event,
                                   samples=len(samples), cached_value_identity=value_id, recomputed_value_identity=value_id,
                                   status="MATCHES_RECOMPUTED_SOURCES"))
            groups[(kind, event)] = samples
    perimeter = [s for event in us for s in groups[("perimeter", event)]]
    mixed = perimeter + [s for event in us + kr for s in groups[("kriged", event)]]
    checkpoints = {}
    for variant in freezer.VARIANTS:
        samples = mixed if variant == "mixed_base" else perimeter
        count = len(samples)
        checkpoint = run / "final" / f"{variant}_seed0/checkpoint.pt"
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        checkpoint.write_bytes(("synthetic exact checkpoint identity " + variant).encode())
        value = dict(variant=variant, seed=0, epochs=3, train_samples=count, train_events=us,
                     checkpoint_sha256=freezer.sha(checkpoint), fit=dict(history=[
                         dict(epoch=i, optimizer_steps=count, skipped_unsupported_intervals=[]) for i in (1, 2, 3)]))
        if variant == "mixed_base":
            manifest_path = checkpoint.with_name("FIT_INPUT_MANIFEST.json")
            coverage.write_new(manifest_path, coverage.capture_sample_manifest(samples, regime="mixed", producer_source_sha256=source,
                                                                               input_sha256=expected["input_sha256"]))
            ids = [coverage.case_id(s) for s in samples]
            value["fit_input_manifest"] = coverage.identity(root, manifest_path)
            value["intended_kriged_fit_events"] = us + kr
            value["fit"]["runtime_membership"] = dict(schema=coverage.RUNTIME_SCHEMA, sample_manifest_sha256=coverage.sha(manifest_path),
                epochs=[dict(epoch=i, attempted_case_ids=ids[::-1], attempted_case_ids_sha256=coverage.object_sha(ids[::-1]),
                             skipped_case_ids=[], optimizer_steps=count) for i in (1, 2, 3)])
        record = checkpoint.with_name("result.json")
        record.write_text(json.dumps(value))
        execution = evidence / f"executions/a03_final_{variant}.json"
        execution.parent.mkdir(parents=True, exist_ok=True)
        command = ["python", "pipeline.py", "final", "--variant", variant, "--seed", "0", "--epochs", "3",
                   "--max-fit-intervals-per-fire", "3", "--max-fit-intervals-per-fire", "0", "--intervals-per-epoch", "0",
                   "--samples-per-step", "1", "--work", str(caches), "--run", str(run),
                   "--data-root", str(inputs / "environment"), "--perimeters", str(inputs / "perimeters"),
                   "--data-manifest-sha256", coverage.sha(extraction)]
        execution.write_text(json.dumps(dict(exit_code=0, output=str(record), output_sha256=freezer.sha(record), command=command,
                                             source_sha256=source)))
        checkpoints[variant] = freezer.identity(root, checkpoint)
    comparator = root / "c651.pt"
    comparator.write_bytes(b"synthetic comparator")
    monkeypatch.setattr(freezer, "C651_SHA", freezer.sha(comparator))
    baselines = {}
    for name, filename in freezer.BASELINES.items():
        path = run / "baselines" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(best_hours_per_cell=4)) if name == "dilation_choice" else "synthetic exact baseline bytes")
        baselines[name] = freezer.identity(root, path)
    baseline_receipt = evidence / "executions/a03_baselines.json"
    baseline_receipt.write_text(json.dumps(dict(exit_code=0, output_sha256=baselines["dilation_choice"]["sha256"])))
    cache_audit = evidence / "CACHE_AUDIT.json"
    cache_audit.write_text(json.dumps(dict(status="PASS_NO_CONSUMED_VALUES_CHANGED", producer_unchanged_during_audit=True,
                                          producer_sha256=source["research/forecast-v2/scripts/pipeline.py"], records=audit_rows, mismatches=[],
                                          audit_script_sha256=coverage.sha(evidence / "scripts/audit_caches.py"))))
    coverage_path = evidence / "FIT_COVERAGE.json"
    coverage.write_new(coverage_path, coverage.audit_coverage(root, inputs, caches, run, cache_audit))
    selection = dict(checkpoints=checkpoints, baselines=baselines, selected_variant="base", fit_coverage=coverage.identity(root, coverage_path),
                     development_brier={v: .1 for v in freezer.VARIANTS}, frozen_before_heldout_scoring=True,
                     frozen_utc="2026-10-30T00:00:00Z", baseline_execution_sha256=freezer.sha(baseline_receipt),
                     cache_audit=coverage.identity(root, cache_audit), cache_audit_sha256=freezer.sha(cache_audit), protocol_sha256=freezer.sha(evidence / "RUN_PROTOCOL.json"),
                     input_manifests_sha256={name: coverage.sha(inputs / name) for name in
                        ["EXTRACTION_MANIFEST.json", "BASELINE_TERRAIN_MANIFEST.json", "perimeters/PERIMETER_MANIFEST.json"]})
    selection_path = evidence / "MODEL_SELECTION.json"
    selection_path.write_text(json.dumps(selection))
    return root, run, selection_path, comparator, selection


def test_registry_freeze_pins_exact_models_baselines_and_complete_executed_closure(freezer, freeze_inputs):
    root, run, selection_path, comparator, _ = freeze_inputs
    registry = freezer.build_registry(root, run, selection_path, comparator)
    assert set(registry["models"]) == {"c651_mc", *(v + "_seed0" for v in freezer.VARIANTS)}
    assert registry["selected_model"] == "base_seed0"
    assert registry["best_dilation_hours_per_cell"] == 4
    assert set(registry["baselines"]) == set(freezer.BASELINES)
    assert "research/forecast-v2/scripts/blind_inventory.py" in registry["producer_source_sha256"]
    assert "research/forecast-v2/scripts/freeze_registry.py" in registry["producer_source_sha256"]
    assert "forecast/wildfire/nested/config.json" in registry["producer_source_sha256"]
    assert registry["protocol_status"] == "READY_FOR_OWNER_REGISTRATION"
    assert registry["execution_status"] == "NOT_READY_FOR_2026_EXECUTION"
    assert not registry["future_inputs_pinned"]


def test_registry_does_not_read_selection_before_all_seven_full_fits(freezer, freeze_inputs):
    root, run, selection_path, comparator, _ = freeze_inputs
    selection_path.write_text("invalid JSON, must never be read")
    (run / "final/mixed_base_seed0/checkpoint.pt").unlink()
    with pytest.raises(ValueError, match="nonempty existing files"):
        freezer.build_registry(root, run, selection_path, comparator)


@pytest.mark.parametrize("tamper", ["missing_model", "extra_model", "placeholder_hash", "checkpoint_bytes", "baseline_bytes",
                                    "missing_baseline", "wrong_selection", "bad_development", "limited_fit", "failed_fit",
                                    "unreceipted_fit", "missing_source", "changed_c651", "heldout_started", "missing_cache_audit"])
def test_registry_freeze_refuses_incomplete_or_changed_known_identities(freezer, freeze_inputs, tamper):
    root, run, selection_path, comparator, selection = freeze_inputs
    if tamper == "missing_model": selection["checkpoints"].pop("ellipse")
    if tamper == "extra_model": selection["checkpoints"]["unregistered"] = selection["checkpoints"]["base"]
    if tamper == "placeholder_hash": selection["checkpoints"]["base"]["sha256"] = "TBD"
    if tamper == "checkpoint_bytes": (run / "final/base_seed0/checkpoint.pt").write_bytes(b"changed")
    if tamper == "baseline_bytes": (run / "baselines/logistic.pkl").write_bytes(b"changed")
    if tamper == "missing_baseline": selection["baselines"].pop("logistic_parameters")
    if tamper == "wrong_selection": selection["selected_variant"] = "d4"
    if tamper == "bad_development": selection["development_brier"]["base"] = float("nan")
    if tamper in ("limited_fit", "failed_fit"):
        path = root / "research/forecast-v2/executions/a03_final_base.json"
        record = json.loads(path.read_text())
        if tamper == "limited_fit": record["command"][record["command"].index("--intervals-per-epoch") + 1] = "1"
        else: record["exit_code"] = 1
        path.write_text(json.dumps(record))
    if tamper == "unreceipted_fit": (root / "research/forecast-v2/executions/a03_final_base.json").unlink()
    if tamper == "missing_source": (root / "research/forecast-v2/scripts/blind_inventory.py").unlink()
    if tamper == "changed_c651": comparator.write_bytes(b"changed immutable comparator")
    if tamper == "heldout_started":
        path = run / "heldout/cases/synthetic.json"
        path.parent.mkdir(parents=True)
        path.write_text("synthetic assessment started")
    if tamper == "missing_cache_audit": (root / "research/forecast-v2/CACHE_AUDIT.json").unlink()
    selection_path.write_text(json.dumps(selection))
    with pytest.raises(ValueError):
        freezer.build_registry(root, run, selection_path, comparator)


def test_registry_cli_preserves_existing_registry(freezer, tmp_path):
    target = tmp_path / "registry.json"
    target.write_text("preserve existing freeze")
    with pytest.raises(FileExistsError):
        freezer.main(["--run-root", str(tmp_path), "--out", str(target)])
    assert target.read_text() == "preserve existing freeze"


@pytest.fixture
def complete_inventory_fixture(blind, registered, monkeypatch, tmp_path):
    """Exercise the actual reviewed adapter with genuine tiny synthetic SHP/TIFs."""
    helper_path = Path(__file__).with_name("test_blind_inventory.py")
    spec = importlib.util.spec_from_file_location("reviewed_inventory_fixture_helpers", helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    release = helper.SyntheticRelease(tmp_path / "actual-synthetic-inventory")
    repo, _, rp, cp, registry, cohort = registered
    terrain = release.root / "baseline-terrain/SYNTHETIC_A/elevation_m_375m.tif"
    write_baseline_terrain(terrain, release.grid)
    report = release.validate()
    cohort["source_release_utc"] = release.manifest["release"]["public_release_utc"]
    cohort["inventory"] = dict(path="inventory-input.json", sha256=release.pinned_manifest_sha, exclusions=report["exclusions"])
    cohort["input_sha256"] = {str(p.relative_to(release.root)): blind.sha(p)
                              for p in release.root.rglob("*") if p.is_file() and "construction" not in p.parts}
    monkeypatch.setattr(blind, "load_inventory", lambda: helper.inventory)
    cohort["cases"], _ = blind.reference_cases(release.root, cohort)
    blind.write(cp, cohort)
    return repo, release, rp, cp, registry, cohort


def test_actual_inventory_adapter_is_wired_into_source_case_admission(blind, complete_inventory_fixture):
    repo, release, rp, cp, _, _ = complete_inventory_fixture
    _, cohort, references = blind.validate(rp, cp, repo, release.root)
    report = cohort["_inventory_validation"]
    assert len(references) == report["case_count"] == 2
    assert report["raw_inventory"]["raw_record_count"] == 3
    assert report["execution_status"] == "NOT_READY_FOR_2026_EXECUTION"
    assert report["release_identity"]["attestation_status"] == "CALLER_ATTESTATION_NOT_EXTERNALLY_VERIFIED"


@pytest.mark.parametrize("tamper", ["no_manifest", "manifest_hash", "missing_archive_pin", "missing_state_pin", "exclusion_ledger",
                                    "release_time", "omitted_case", "raw_archive_bytes"])
def test_catalog_alone_cannot_bypass_authoritative_raw_inventory(blind, complete_inventory_fixture, tamper):
    repo, release, rp, cp, _, cohort = complete_inventory_fixture
    if tamper == "no_manifest": cohort.pop("inventory")
    if tamper == "manifest_hash": cohort["inventory"]["sha256"] = "0" * 64
    if tamper == "missing_archive_pin": cohort["input_sha256"].pop("publisher.zip")
    if tamper == "missing_state_pin": cohort["input_sha256"].pop("perimeters/SYNTHETIC_A/states.npz")
    if tamper == "exclusion_ledger": cohort["inventory"]["exclusions"] = [dict(event="SYNTHETIC_A", reason="caller wants exclusion")]
    if tamper == "release_time": cohort["source_release_utc"] = "2027-01-11T00:00:00Z"
    if tamper == "omitted_case": cohort["cases"].pop()
    if tamper == "raw_archive_bytes":
        release.archive.write_bytes(b"not the pinned publisher archive")
        cohort["input_sha256"]["publisher.zip"] = blind.sha(release.archive)
    blind.write(cp, cohort)
    with pytest.raises(ValueError):
        blind.validate(rp, cp, repo, release.root)


def test_absent_external_review_blocks_model_loading_and_future_execution(blind, registered, tmp_path, monkeypatch):
    repo, root, rp, cp, _, _ = registered
    monkeypatch.setattr(blind, "load_pipeline", lambda: pytest.fail("No documentary clearance may reach model loading"))
    _, diagnostic, _ = blind.validate(rp, cp, repo, root)
    assert diagnostic["_documentary_clearance"] is None
    out = tmp_path / "never-created"
    with pytest.raises(ValueError, match="NOT_READY_FOR_2026_EXECUTION"):
        blind.run(SimpleNamespace(registry=rp, cohort=cp, model_root=repo, input_root=root, out=out))
    assert not out.exists()


@pytest.mark.parametrize("minimal", [dict(verified=True), dict(approved=True, url="https://osf.io/fixture"),
                                      dict(decision="HUMAN_ATTESTED_DOCUMENTARY_CLEARANCE")])
def test_caller_boolean_or_url_is_not_documentary_clearance(blind, registered, minimal):
    repo, root, rp, cp, _, cohort = registered
    path = root / "minimal-review.json"
    blind.write(path, minimal)
    cohort["documentary_clearance"] = dict(path=path.name, sha256=blind.sha(path))
    blind.write(cp, cohort)
    with pytest.raises(ValueError, match="scope-specific human documentary clearance"):
        blind.validate(rp, cp, repo, root)


@pytest.mark.parametrize("tamper", ["registry_binding", "input_binding", "inventory_binding", "source_binding", "case_binding",
                                    "reviewer", "independence", "attestation", "evidence_bytes", "chronology_scope",
                                    "registration_reference", "archive_identity", "registration_time", "limits", "receipt_bytes"])
def test_documentary_review_requires_every_bound_identity_scope_and_pinned_evidence(blind, registered, tamper):
    repo, root, rp, cp, registry, cohort = registered
    path, review = attach_documentary_fixture(blind, registered)
    binding = {"registry_binding": "registry_sha256", "input_binding": "input_closure_sha256",
               "inventory_binding": "inventory_manifest_sha256", "source_binding": "source_closure_sha256",
               "case_binding": "case_membership_sha256"}.get(tamper)
    if binding: review["bindings"][binding] = "0" * 64
    if tamper == "reviewer": review["verifier"]["name"] = ""
    if tamper == "independence": review["verifier"].pop("independence_statement")
    if tamper == "attestation": review["attestation"]["signature_description"] = ""
    if tamper == "evidence_bytes": (root / review["evidence_reviewed"][0]["path"]).write_text("changed evidence")
    if tamper == "chronology_scope": review["evidence_reviewed"] = review["evidence_reviewed"][:1]
    if tamper == "registration_reference": review["registration"]["immutable_url"] = "https://osf.io/other"
    if tamper == "archive_identity": review["publisher_release"]["archive_sha256"] = "0" * 64
    if tamper == "registration_time": review["registration"]["registered_utc"] = cohort["source_release_utc"]
    if tamper == "limits": review["limits"] = [True]
    blind.write(path, review)
    if tamper != "receipt_bytes": cohort["documentary_clearance"]["sha256"] = blind.sha(path)
    else: path.write_text(path.read_text() + " ")
    blind.write(cp, cohort)
    with pytest.raises(ValueError):
        blind.validate(rp, cp, repo, root)


def test_bound_human_review_is_explicitly_not_machine_authentication(blind, registered, numerical_fixture, tmp_path):
    args = produce(blind, registered, tmp_path)
    blind.score(args)
    run = json.loads((args.entries / "RECEIPT.json").read_text())
    scores = json.loads(args.out.read_text())
    for review in (run["pre_run_documentary_clearance"], scores["pre_run_documentary_clearance"]):
        assert review["state"] == "HUMAN_ATTESTED_DOCUMENTARY_CLEARANCE"
        assert review["machine_authentication"] is False
        assert "does not authenticate" in review["verification_limit"]
    assert not scores["superiority_claim_permitted"]
    assert scores["completion"] == "SCORED_PENDING_INDEPENDENT_DOCUMENTARY_APPROVAL_AND_RELOCATED_REPLAY"


@pytest.fixture
def finalize_fixture(blind, registered, numerical_fixture, tmp_path):
    args = produce(blind, registered, tmp_path)
    blind.score(args)
    repo, root, rp, cp, registry, cohort = registered
    replay = tmp_path / "relocated-scores.json"
    replay.write_bytes(args.out.read_bytes())
    scores = json.loads(args.out.read_text())
    review = documentary_fixture(blind, root, registry, cohort, "post_score_independent_relocated_replay_and_claim")
    now = blind.datetime.now(blind.timezone.utc).isoformat()
    review["reviewed_utc"] = review["signed_utc"] = now
    review["scored_artifacts"] = dict(score_sha256=blind.sha(args.out), relocated_replay_sha256=blind.sha(replay),
                                    run_receipt_sha256=scores["run_receipt_sha256"])
    review["independent_replay"] = dict(source_root="/synthetic/independent/relocated-source", command=["python", "blind_test.py", "score"],
                                        verifier_name=review["verifier"]["name"], output_sha256=blind.sha(replay))
    path = root / "post-score-approval.json"
    blind.write(path, review)
    final = SimpleNamespace(registry=rp, cohort=cp, model_root=repo, input_root=root, scores=args.out, replay=replay,
                            approval=path.name, approval_sha256=blind.sha(path), out=tmp_path / "final-review.json")
    return final, review, path


def test_post_score_review_cannot_promote_failed_statistical_criteria(blind, finalize_fixture):
    args, _, _ = finalize_fixture
    blind.finalize(args)
    final = json.loads(args.out.read_text())
    assert not final["superiority_claim_permitted"]
    assert final["status"] == "COMPLETE_REVIEW_NO_SUPERIORITY_CLAIM"
    assert final["machine_authentication"] is False
    assert final["independent_post_score_approval"]["state"] == "HUMAN_ATTESTED_DOCUMENTARY_CLEARANCE"


@pytest.mark.parametrize("tamper", ["minimal", "wrong_score", "wrong_replay", "wrong_run", "original_tree", "no_command",
                                    "different_reviewer", "same_file", "replay_bytes", "old_approval", "criterion_flag"])
def test_final_review_requires_independent_replay_and_exact_score_binding(blind, finalize_fixture, tamper):
    args, review, path = finalize_fixture
    if tamper == "minimal": review = dict(approved=True)
    if tamper == "wrong_score": review["scored_artifacts"]["score_sha256"] = "0" * 64
    if tamper == "wrong_replay": review["scored_artifacts"]["relocated_replay_sha256"] = "0" * 64
    if tamper == "wrong_run": review["scored_artifacts"]["run_receipt_sha256"] = "0" * 64
    if tamper == "original_tree": review["independent_replay"]["source_root"] = str(args.model_root)
    if tamper == "no_command": review["independent_replay"]["command"] = []
    if tamper == "different_reviewer": review["independent_replay"]["verifier_name"] = "different reviewer"
    if tamper == "same_file": args.replay = args.scores
    if tamper == "replay_bytes": args.replay.write_text(args.replay.read_text() + " ")
    if tamper == "old_approval": review["reviewed_utc"] = review["signed_utc"] = review["publisher_release"]["public_release_utc"]
    if tamper == "criterion_flag":
        scores = json.loads(args.scores.read_text())
        scores["results"]["nirops_mapped_extent"]["decision"]["statistical_superiority_criteria_pass"] = True
        blind.write(args.scores, scores)
        args.replay.write_bytes(args.scores.read_bytes())
        review["scored_artifacts"]["score_sha256"] = blind.sha(args.scores)
        review["scored_artifacts"]["relocated_replay_sha256"] = blind.sha(args.replay)
        review["independent_replay"]["output_sha256"] = blind.sha(args.replay)
    blind.write(path, review)
    args.approval_sha256 = blind.sha(path)
    with pytest.raises(ValueError):
        blind.finalize(args)
    assert not args.out.exists()


def test_registered_dependency_versions_cannot_be_ignored(blind, registered):
    repo, root, rp, cp, registry, cohort = registered
    registry["dependency_versions"]["numpy"] = "unregistered-version"
    blind.write(rp, registry)
    cohort["registry_sha256"] = cohort["registration"]["registry_sha256"] = blind.sha(rp)
    blind.write(cp, cohort)
    with pytest.raises(ValueError, match="registered direct dependency versions"):
        blind.validate(rp, cp, repo, root)


def test_complete_ten_fire_synthetic_protocol_requires_both_human_review_stages(blind, registered, numerical_fixture, tmp_path):
    repo, root, rp, cp, registry, cohort = registered
    path = root / "environment/events.json"
    events = json.loads(path.read_text())
    for i in range(1, 10):
        name = f"fixture_{i}"
        events.append(dict(events[0], id=name))
        for source, relative in [(root / "perimeters/fixture/states.npz", f"perimeters/{name}/states.npz"),
                                 (root / "baseline-terrain/fixture/elevation_m_375m.tif", f"baseline-terrain/{name}/elevation_m_375m.tif")]:
            target = root / relative
            target.parent.mkdir(parents=True)
            target.write_bytes(source.read_bytes())
    blind.write(path, events)
    refresh_inventory_fixture(blind, root, cohort)
    cohort["cases"], _ = blind.reference_cases(root, cohort)
    attach_documentary_fixture(blind, registered)
    args = produce(blind, registered, tmp_path)
    receipt_path = args.entries / "RECEIPT.json"
    receipt = json.loads(receipt_path.read_text())
    for record in receipt["cases"]:
        file = args.entries / record["file"]
        with np.load(file, allow_pickle=False) as data:
            arrays = {name: data[name].copy() for name in data.files}
        arrays["p_base_seed0"] = np.where(arrays["y"], .9, 0.)
        arrays["p_persistence"] = arrays["p_dilation_best"] = np.zeros(len(arrays["y"]))
        np.savez_compressed(file, **arrays)
        record["sha256"] = blind.sha(file)
    blind.write(receipt_path, receipt)
    blind.score(args)
    scores = json.loads(args.out.read_text())
    assert scores["results"]["nirops_mapped_extent"]["decision"]["statistical_superiority_criteria_pass"]
    assert not scores["superiority_claim_permitted"]
    replay = tmp_path / "independent-relocated-scores.json"
    replay.write_bytes(args.out.read_bytes())
    review = documentary_fixture(blind, root, registry, cohort, "post_score_independent_relocated_replay_and_claim")
    now = blind.datetime.now(blind.timezone.utc).isoformat()
    review["reviewed_utc"] = review["signed_utc"] = now
    review["scored_artifacts"] = dict(score_sha256=blind.sha(args.out), relocated_replay_sha256=blind.sha(replay),
                                    run_receipt_sha256=scores["run_receipt_sha256"])
    review["independent_replay"] = dict(source_root="/synthetic/relocated-source", command=["python", "blind_test.py", "score"],
                                       verifier_name=review["verifier"]["name"], output_sha256=blind.sha(replay))
    approval = root / "synthetic-post-score-approval.json"
    blind.write(approval, review)
    final = SimpleNamespace(registry=rp, cohort=cp, model_root=repo, input_root=root, scores=args.out, replay=replay,
                            approval=approval.name, approval_sha256=blind.sha(approval), out=tmp_path / "synthetic-final-review.json")
    blind.finalize(final)
    decision = json.loads(final.out.read_text())
    assert decision["superiority_claim_permitted"]
    assert decision["machine_authentication"] is False
    assert decision["status"] == "STATISTICAL_CLAIM_PERMITTED_UNDER_HUMAN_ATTESTED_DOCUMENTARY_REVIEW"


def repin_baseline_fixture(blind, release, cp, cohort):
    for path in (release.root / "baseline-terrain").rglob("*"):
        if path.is_file(): cohort["input_sha256"][str(path.relative_to(release.root))] = blind.sha(path)
    blind.write(cp, cohort)


def test_consumed_baseline_geotiff_and_pinned_external_mask_are_admitted(blind, complete_inventory_fixture):
    import rasterio
    repo, release, rp, cp, _, cohort = complete_inventory_fixture
    source = release.root / "baseline-terrain/SYNTHETIC_A/elevation_m_375m.tif"
    with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=False):
        with rasterio.open(source, "r+") as raster:
            raster.write_mask(np.full((3, 3), 255, dtype=np.uint8))
    mask = Path(str(source) + ".msk")
    assert mask.is_file()
    repin_baseline_fixture(blind, release, cp, cohort)
    _, admitted, _ = blind.validate(rp, cp, repo, release.root)
    assert str(mask.relative_to(release.root)) in admitted["input_sha256"]


@pytest.mark.parametrize("component", ["canonical_vrt", "mask_vrt", "file_symlink", "ancestor_symlink", "missing_sidecar_pin"])
def test_consumed_baseline_terrain_rejects_indirect_or_unpinned_dependencies(blind, complete_inventory_fixture, component):
    import rasterio
    repo, release, rp, cp, _, cohort = complete_inventory_fixture
    source = release.root / "baseline-terrain/SYNTHETIC_A/elevation_m_375m.tif"
    borrowed = release.root / "unregistered-borrowed-elevation.tif"
    borrowed.write_bytes(source.read_bytes())
    if component == "file_symlink":
        source.unlink()
        source.symlink_to(borrowed)
    elif component == "ancestor_symlink":
        folder = source.parent
        moved = release.root / "borrowed-elevation-folder"
        folder.rename(moved)
        folder.symlink_to(moved, target_is_directory=True)
    elif component == "canonical_vrt":
        source.write_text(f'<VRTDataset rasterXSize="3" rasterYSize="3"><VRTRasterBand dataType="Float32" band="1"><SimpleSource>'
                          f'<SourceFilename relativeToVRT="0">{borrowed}</SourceFilename><SourceBand>1</SourceBand>'
                          '</SimpleSource></VRTRasterBand></VRTDataset>')
    else:
        with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=False):
            with rasterio.open(source, "r+") as raster:
                raster.write_mask(np.full((3, 3), 255, dtype=np.uint8))
        mask = Path(str(source) + ".msk")
        if component == "mask_vrt":
            mask.write_text(f'<VRTDataset rasterXSize="3" rasterYSize="3"><VRTRasterBand dataType="Byte" band="1"><SimpleSource>'
                            f'<SourceFilename relativeToVRT="0">{borrowed}</SourceFilename><SourceBand>1</SourceBand>'
                            '</SimpleSource></VRTRasterBand></VRTDataset>')
    repin_baseline_fixture(blind, release, cp, cohort)
    if component == "ancestor_symlink":
        cohort["input_sha256"][str(source.relative_to(release.root))] = blind.sha(source)
        blind.write(cp, cohort)
    if component == "missing_sidecar_pin":
        cohort["input_sha256"].pop(str(mask.relative_to(release.root)))
        blind.write(cp, cohort)
    with pytest.raises(ValueError):
        blind.validate(rp, cp, repo, release.root)



def test_relocated_score_json_is_stable_across_python_hash_seeds(blind, tmp_path):
    script = Path(blind.__file__)
    code = """
import importlib.util
from pathlib import Path
import sys
import numpy as np
spec = importlib.util.spec_from_file_location('synthetic_score_replay', sys.argv[1])
blind = importlib.util.module_from_spec(spec)
spec.loader.exec_module(blind)
y = np.tile(np.array([0, 1]), 10)
entries = dict(fire=np.repeat(np.arange(10).astype(str), 2), y=y,
               predictions={n: np.where(y, .8, .1) for n in blind.MODEL_NAMES | blind.BASELINE_NAMES})
blind.write(Path(sys.argv[2]), blind.B.score_entries(entries, draws=10000, seed=20261030))
"""
    paths = []
    for seed in ("1", "2"):
        path = tmp_path / ("pure-synthetic-score-seed" + seed + ".json")
        completed = subprocess.run([sys.executable, "-c", code, str(script), str(path)],
                                   env=dict(os.environ, PYTHONHASHSEED=seed), capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr
        paths.append(path)
    assert blind.sha(paths[0]) == blind.sha(paths[1])



def test_registry_preserves_stale_attempt_receipts_without_using_them(freezer, freeze_inputs):
    root, run, selection_path, comparator, _ = freeze_inputs
    current = root / "research/forecast-v2/executions/a03_final_base.json"
    old = current.with_name("a01_final_base.json")
    receipt = json.loads(current.read_text())
    receipt.update(exit_code=1, output_sha256="0" * 64)
    original = json.dumps(receipt)
    old.write_text(original)
    registry = freezer.build_registry(root, run, selection_path, comparator)
    assert registry["final_executions"]["base"]["path"].endswith("a03_final_base.json")
    assert old.read_text() == original


def fit_coverage_state(freezer, freeze_inputs):
    root, run, selection_path, comparator, selection = freeze_inputs
    module = fit_coverage_module(freezer)
    path = root / selection["fit_coverage"]["path"]
    recorded = json.loads(path.read_text())
    return module, root, run, Path(recorded["input_root"]), Path(recorded["cache_root"]), path, recorded


def resign_result_receipt(freezer, root, run, variant, change):
    path = run / f"final/{variant}_seed0/result.json"
    result = json.loads(path.read_text())
    change(result)
    path.write_text(json.dumps(result))
    receipt_path = root / f"research/forecast-v2/executions/a03_final_{variant}.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["output_sha256"] = freezer.sha(path)
    receipt_path.write_text(json.dumps(receipt))


def test_full_fit_coverage_derives_all_case_ids_and_retains_zero_window_korean_keys(freezer, freeze_inputs):
    module, root, run, inputs, _, _, record = fit_coverage_state(freezer, freeze_inputs)
    expected = module.expected_membership(root, inputs)
    assert expected["intended_us_fit_events"] == ["synthetic_fit", "synthetic_fit_second"]
    assert len(expected["perimeter_cases"]) == 4
    assert len(expected["mixed_cases"]) == 12
    assert expected["ledger"]["kriged"]["synthetic_kr_zero"]["sample_count"] == 0
    assert expected["ledger"]["kriged"]["synthetic_kr_zero"]["cases"] == []
    assert len(expected["ledger"]["kriged"]["synthetic_kr"]["cases"]) == 2
    assert expected["ledger"]["kriged"]["synthetic_kr"]["cases"][0]["cutoff"] == "2020-01-01T12:00:00+00:00"
    assert record["variants"]["base"]["schedule_evidence"] == "SOURCE_DERIVED_SCHEDULE_INFERENCE_NO_RUNTIME_IDS_RECORDED"
    assert record["variants"]["base"]["runtime_membership"] is None
    assert record["variants"]["mixed_base"]["schedule_evidence"].startswith("RUNTIME_ATTEMPTED_IDS")
    assert record["variants"]["base"]["effective_arguments"]["max_fit_intervals_per_fire"] == "0"
    assert record["expected"] == expected


def test_registry_rejects_parent_audit_incomplete_declared_fire_set(freezer, freeze_inputs):
    root, run, selection_path, comparator, _ = freeze_inputs
    split_path = root / "research/forecast-v2/SPLIT.json"
    original = split_path.read_bytes()
    split = json.loads(original)
    split["fit"]["us_perimeter_and_kriged"].append("omitted_intended_fit_fire")
    split_path.write_text(json.dumps(split))
    with pytest.raises(ValueError, match="Completed fixed-policy full fit"):
        freezer.build_registry(root, run, selection_path, comparator)
    # The fixture leaves the rejected evidence intact for inspection, without
    # changing any original audit report or source campaign artifacts.
    assert split_path.read_bytes() != original


@pytest.mark.parametrize("tamper", ["omit_cached_case", "duplicate_cached_case", "wrong_cached_cutoff", "wrong_cached_duration", "missing_event_cache"])
def test_flags_counts_and_re_signed_cache_metadata_cannot_replace_full_source_membership(freezer, freeze_inputs, tamper):
    module, root, run, inputs, caches, _, _ = fit_coverage_state(freezer, freeze_inputs)
    path = caches / "samples/perimeter_crop_first0_synthetic_fit.pkl"
    if tamper == "missing_event_cache":
        path.unlink()
    else:
        samples = pickle.loads(path.read_bytes())
        if tamper == "omit_cached_case": samples.pop()
        if tamper == "duplicate_cached_case": samples[1] = samples[0]
        if tamper == "wrong_cached_cutoff":
            samples[0].t1 = "2020-01-01T01:00:00+00:00"
            samples[0].hours = 11.
        if tamper == "wrong_cached_duration": samples[0].hours = 1.
        path.write_bytes(pickle.dumps(samples, protocol=5))
        audit_path = root / "research/forecast-v2/CACHE_AUDIT.json"
        audit = json.loads(audit_path.read_text())
        row = next(row for row in audit["records"] if Path(row["cache"]) == path)
        row.update(cache_sha256=module.sha(path), samples=len(samples), cached_value_identity=module.sample_list_identity(samples),
                   recomputed_value_identity=module.sample_list_identity(samples))
        audit_path.write_text(json.dumps(audit))
    with pytest.raises(ValueError, match="cached full sample identities|existing files|consumed perimeter duration"):
        module.audit_coverage(root, inputs, caches, run, root / "research/forecast-v2/CACHE_AUDIT.json")


@pytest.mark.parametrize("tamper", ["wrong_count", "short_epoch", "skipped_sample", "missing_runtime", "runtime_omission", "runtime_duplicate",
                                    "runtime_hash", "runtime_skip", "missing_zero_window_kr", "input_manifest_omission", "input_manifest_values"])
def test_coverage_requires_complete_recorded_counts_and_actual_new_mixed_runtime_membership(freezer, freeze_inputs, tamper):
    module, root, run, inputs, caches, _, _ = fit_coverage_state(freezer, freeze_inputs)
    variant = "base" if tamper in ("wrong_count", "short_epoch", "skipped_sample") else "mixed_base"

    def change(result):
        if tamper == "wrong_count": result["train_samples"] -= 1
        if tamper == "short_epoch": result["fit"]["history"][0]["optimizer_steps"] -= 1
        if tamper == "skipped_sample": result["fit"]["history"][0]["skipped_unsupported_intervals"] = [dict(event="synthetic_fit")]
        if tamper == "missing_runtime": result["fit"].pop("runtime_membership")
        if tamper in ("runtime_omission", "runtime_duplicate", "runtime_hash", "runtime_skip"):
            epoch = result["fit"]["runtime_membership"]["epochs"][0]
            if tamper == "runtime_omission": epoch["attempted_case_ids"].pop()
            if tamper == "runtime_duplicate": epoch["attempted_case_ids"][0] = epoch["attempted_case_ids"][1]
            if tamper == "runtime_skip": epoch["skipped_case_ids"] = epoch["attempted_case_ids"][:1]
            epoch["attempted_case_ids_sha256"] = module.object_sha(epoch["attempted_case_ids"])
            if tamper == "runtime_hash": epoch["attempted_case_ids_sha256"] = "0" * 64
        if tamper == "missing_zero_window_kr": result["intended_kriged_fit_events"].remove("synthetic_kr_zero")
        if tamper in ("input_manifest_omission", "input_manifest_values"):
            path = root / result["fit_input_manifest"]["path"]
            manifest = json.loads(path.read_text())
            if tamper == "input_manifest_omission": manifest["sample_cases"].pop()
            else: manifest["sample_values_sha256"] = "0" * 64
            path.write_text(json.dumps(manifest))
            result["fit_input_manifest"]["sha256"] = module.sha(path)
            result["fit"]["runtime_membership"]["sample_manifest_sha256"] = module.sha(path)

    resign_result_receipt(freezer, root, run, variant, change)
    with pytest.raises(ValueError):
        module.audit_coverage(root, inputs, caches, run, root / "research/forecast-v2/CACHE_AUDIT.json")


def test_old_pure_schedule_inference_binds_the_actual_indexed_sample_source(freezer, freeze_inputs):
    module, root, run, inputs, caches, _, _ = fit_coverage_state(freezer, freeze_inputs)
    source_path = root / "forecast/wildfire/survival.py"
    source_path.write_text(source_path.read_text().replace("sample = train[index]", "sample = train[0]"))
    receipt_path = root / "research/forecast-v2/executions/a03_final_base.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["source_sha256"]["forecast/wildfire/survival.py"] = module.sha(source_path)
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="actual indexed member"):
        module.audit_coverage(root, inputs, caches, run, root / "research/forecast-v2/CACHE_AUDIT.json")


@pytest.mark.parametrize("tamper", ["absent_coverage", "coverage_hash", "coverage_counts", "unbound_input_manifest", "wrong_cache_root", "wrong_data_root"])
def test_registry_cannot_promote_without_rederived_complete_coverage(freezer, freeze_inputs, tamper):
    root, run, selection_path, comparator, selection = freeze_inputs
    module, _, _, _, _, coverage_path, coverage = fit_coverage_state(freezer, freeze_inputs)
    if tamper == "absent_coverage": selection.pop("fit_coverage")
    if tamper == "coverage_hash": selection["fit_coverage"]["sha256"] = "0" * 64
    if tamper == "coverage_counts":
        coverage["variants"]["base"]["sample_count"] -= 1
        coverage_path.write_text(json.dumps(coverage))
        selection["fit_coverage"]["sha256"] = module.sha(coverage_path)
    if tamper == "unbound_input_manifest": selection["input_manifests_sha256"]["EXTRACTION_MANIFEST.json"] = "0" * 64
    if tamper in ("wrong_cache_root", "wrong_data_root"):
        path = root / "research/forecast-v2/executions/a03_final_base.json"
        receipt = json.loads(path.read_text())
        name = "--work" if tamper == "wrong_cache_root" else "--data-root"
        receipt["command"][receipt["command"].index(name) + 1] = "/unbound/source/location"
        path.write_text(json.dumps(receipt))
    selection_path.write_text(json.dumps(selection))
    with pytest.raises(ValueError):
        freezer.build_registry(root, run, selection_path, comparator)


def repin_fit_source_fixture(module, root, inputs):
    extraction = inputs / "EXTRACTION_MANIFEST.json"
    extraction.write_text(json.dumps(dict(members=[dict(path=str(p.relative_to(inputs)), sha256=module.sha(p))
                                                   for p in (inputs / "environment").rglob("*") if p.is_file()])))
    protocol = root / "research/forecast-v2/RUN_PROTOCOL.json"
    protocol.write_text(json.dumps(dict(data_manifest_sha256=module.sha(extraction))))


def test_expected_fit_membership_uses_exact_timestamps_and_no_endpoint_growth_filter(freezer, freeze_inputs):
    module, root, _, inputs, _, _, _ = fit_coverage_state(freezer, freeze_inputs)
    path = inputs / "perimeters/synthetic_fit/states.npz"
    times = ["2020-01-01T00:00:00Z", "2020-01-01T12:00:00Z", "2020-01-03T12:00:00Z", "2020-01-05T12:00:00.000000001Z"]
    np.savez(path, times=np.array(times), states=np.ones((4, 2, 2), dtype=np.uint8))
    manifest_path = inputs / "perimeters/PERIMETER_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["events"]["synthetic_fit"]["states_sha256"] = module.sha(path)
    manifest_path.write_text(json.dumps(manifest))
    catalog = inputs / "environment/events.json"
    events = json.loads(catalog.read_text())
    events[0]["end_utc"] = "2020-01-06T00:00:00Z"
    catalog.write_text(json.dumps(events))
    repin_fit_source_fixture(module, root, inputs)
    expected = module.expected_membership(root, inputs)
    cases = expected["ledger"]["perimeter"]["synthetic_fit"]["cases"]
    assert len(cases) == 2
    assert cases[1]["endpoint"] == "2020-01-03T12:00:00+00:00"
    # All reference states are identical. Eligibility comes from timestamps,
    # never from endpoint growth or a useful training mask.
    assert cases[0]["cutoff"] == "2020-01-01T00:00:00+00:00"


def test_expected_fit_membership_uses_cutoff_weather_availability_without_losing_declared_keys(freezer, freeze_inputs):
    module, root, _, inputs, _, _, _ = fit_coverage_state(freezer, freeze_inputs)
    path = inputs / "environment/events.json"
    events = json.loads(path.read_text())
    events[0]["start_utc"] = "2020-01-01T12:00:00Z"
    path.write_text(json.dumps(events))
    repin_fit_source_fixture(module, root, inputs)
    expected = module.expected_membership(root, inputs)
    assert expected["ledger"]["perimeter"]["synthetic_fit"]["sample_count"] == 1
    assert expected["ledger"]["kriged"]["synthetic_fit"]["sample_count"] == 2
    assert set(expected["ledger"]["kriged"]) == set(expected["intended_kriged_fit_events"])
    assert expected["ledger"]["kriged"]["synthetic_kr_zero"]["sample_count"] == 0


def test_historical_schedule_inference_reads_exact_preserved_phase_source(freezer, freeze_inputs):
    module, root, run, inputs, caches, _, recorded = fit_coverage_state(freezer, freeze_inputs)
    source = root / "forecast/wildfire/survival.py"
    original = source.read_bytes()
    digest = module.sha(source)
    snapshot = root / "research/forecast-v2/source_snapshots" / digest / source.name
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(original)
    source.write_bytes(original + b"\n# Later metadata-only source comment, never attributed to old runtime.\n")
    audited = module.audit_coverage(root, inputs, caches, run, root / "research/forecast-v2/CACHE_AUDIT.json")
    assert audited["variants"]["base"]["source_schedule_contract"]["survival_sha256"] == digest
    assert audited["source_sha256"]["forecast/wildfire/survival.py"] != digest
    assert audited["variants"]["base"]["runtime_membership"] is None


def test_registry_authenticates_named_final_cache_audit_while_preserving_original(freezer, freeze_inputs):
    root, run, selection_path, comparator, selection = freeze_inputs
    module, _, _, inputs, caches, _, _ = fit_coverage_state(freezer, freeze_inputs)
    original = root / "research/forecast-v2/CACHE_AUDIT.json"
    original_bytes = original.read_bytes()
    final = original.with_name("CACHE_AUDIT_FINAL.json")
    value = json.loads(original_bytes)
    value["completed_utc"] = "2026-10-30T01:00:00Z"
    module.write_new(final, value)
    coverage_path = original.with_name("FIT_COVERAGE_FINAL.json")
    module.write_new(coverage_path, module.audit_coverage(root, inputs, caches, run, final))
    selection["fit_coverage"] = module.identity(root, coverage_path)
    selection["cache_audit"] = module.identity(root, final)
    selection["cache_audit_sha256"] = module.sha(final)
    selection_path.write_text(json.dumps(selection))
    registry = freezer.build_registry(root, run, selection_path, comparator)
    assert registry["cache_audit"] == selection["cache_audit"]
    assert registry["cache_audit"]["path"].endswith("CACHE_AUDIT_FINAL.json")
    assert original.read_bytes() == original_bytes


def test_declared_kriged_inputs_cannot_be_disappeared_after_the_source_manifest(freezer, freeze_inputs):
    module, root, _, inputs, _, _, _ = fit_coverage_state(freezer, freeze_inputs)
    region = inputs / "environment/regions/synthetic_kr_zero"
    for path in region.iterdir(): path.unlink()
    region.rmdir()
    with pytest.raises(ValueError, match="missing despite pinned archive"):
        module.expected_membership(root, inputs)


def test_mixed_regime_source_cannot_declare_full_counts_while_disabling_extra_inputs(freezer, freeze_inputs):
    module, root, run, inputs, caches, _, _ = fit_coverage_state(freezer, freeze_inputs)
    path = root / "research/forecast-v2/scripts/pipeline.py"
    snapshot = root / "research/forecast-v2/source_snapshots" / module.sha(path) / path.name
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(path.read_bytes())
    path.write_text(path.read_text().replace('d4=False, mixed=True)', 'd4=False, mixed=False)'))
    receipt_path = root / "research/forecast-v2/executions/a03_final_base.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["source_sha256"]["research/forecast-v2/scripts/pipeline.py"] = module.sha(path)
    receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="mixed extra-source regime"):
        module.audit_coverage(root, inputs, caches, run, root / "research/forecast-v2/CACHE_AUDIT.json")
