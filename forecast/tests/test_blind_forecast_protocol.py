"""Mechanism fixtures for future blind-test custody, never study evidence."""
import importlib.util
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


@pytest.fixture
def registered(blind, tmp_path, monkeypatch):
    repo, root = tmp_path / "repo", tmp_path / "inputs"
    repo.mkdir()
    (root / "environment").mkdir(parents=True)
    monkeypatch.setattr(blind, "REPO", repo)
    names = ["forecast/wildfire/example.py", "research/forecast-v2/scripts/pipeline.py",
             "research/forecast-v2/scripts/blind_test.py", "research/forecast-v2/SPLIT.json"]
    for name in names:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    checkpoint = repo / "fixture.pt"
    checkpoint.write_bytes(b"fixture checkpoint, no scientific model")
    monkeypatch.setattr(blind, "C651_SHA", blind.sha(checkpoint))
    model = dict(path="fixture.pt", sha256=blind.sha(checkpoint))
    registry = dict(status="FROZEN", models={n: model for n in blind.MODEL_NAMES}, logistic=model,
                    selected_model="base_seed0", best_dilation_hours_per_cell=4,
                    producer_source_sha256={n: blind.sha(repo / n) for n in names})
    registry_path = repo / "registry.json"
    blind.write(registry_path, registry)
    events = [dict(id="fixture", year=2026, country="US", t0_utc="2026-01-01T00:00:00Z",
                   start_utc="2026-01-01T00:00:00Z", end_utc="2026-01-03T00:00:00Z", height=1, width=4)]
    blind.write(root / "environment/events.json", events)
    terrain = root / "baseline-terrain/fixture/elevation_m_375m.tif"
    terrain.parent.mkdir(parents=True)
    terrain.write_bytes(b"identity-only fixture; this test never runs environmental inference")
    states = root / "perimeters/fixture/states.npz"
    states.parent.mkdir(parents=True)
    np.savez(states, times=np.array(["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"]),
             states=np.array([[[1, 0, 0, 0]], [[1, 1, 0, 1]]], dtype=np.uint8))
    cohort = dict(registry_sha256=blind.sha(registry_path), source_release_utc="2027-01-01T00:00:00Z",
                  registration=dict(url="https://osf.io/fixture", registered_utc="2026-12-01T00:00:00Z",
                                    registry_sha256=blind.sha(registry_path)),
                  input_sha256={str(p.relative_to(root)): blind.sha(p) for p in root.rglob("*") if p.is_file()})
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


def test_actual_source_year_cannot_be_declared_as_2026(blind, registered):
    _, root, _, _, _, cohort = registered
    path = root / "environment/events.json"
    events = json.loads(path.read_text())
    events[0]["t0_utc"] = "2025-12-31T00:00:00Z"
    blind.write(path, events)
    cohort["input_sha256"]["environment/events.json"] = blind.sha(path)
    with pytest.raises(ValueError, match="Fire year"):
        blind.reference_cases(root, cohort)


def test_unhashed_extra_prediction_cannot_enter_score(blind, registered, tmp_path):
    repo, root, rp, cp, registry, cohort = registered
    entries = tmp_path / "predictions"
    (entries / "cases").mkdir(parents=True)
    record = dict(case=cohort["cases"][0], status="UNAVAILABLE")
    blind.write(entries / "RECEIPT.json", dict(receipt_version=blind.RECEIPT_VERSION, validated_identity=blind.validation_identity(registry, cohort),
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
    assert blind.primary_decision(result, "base_seed0", complete=True)["statistical_superiority_criteria_pass"]
    result["fires"].pop()
    assert not blind.primary_decision(result, "base_seed0", complete=True)["statistical_superiority_criteria_pass"]
    result["fires"].append(9)
    result["paired"]["base_seed0__vs__dilation_best"]["percentile_95_interval"] = [-.02, .001]
    assert not blind.primary_decision(result, "base_seed0", complete=True)["statistical_superiority_criteria_pass"]


def test_declared_model_root_cannot_authenticate_a_different_import_tree(blind, registered, tmp_path):
    _, root, registry, cohort, _, _ = registered
    with pytest.raises(ValueError, match="exact verified source tree"):
        blind.validate(registry, cohort, tmp_path, root)


@pytest.fixture
def numerical_fixture(blind, registered, monkeypatch):
    """Mock only numerical producers; keep real validation, files, receipts and scoring."""
    repo, root, rp, cp, registry, cohort = registered
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
    cohort["input_sha256"]["environment/events.json"] = blind.sha(events_path)
    cohort["cases"], _ = blind.reference_cases(root, cohort)
    blind.write(cp, cohort)
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
