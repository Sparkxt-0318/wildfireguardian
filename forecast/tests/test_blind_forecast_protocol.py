"""Mechanism fixtures for future blind-test custody, never study evidence."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
import pytest


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
                   start_utc="2026-01-01T00:00:00Z", end_utc="2026-01-03T00:00:00Z", height=1, width=2)]
    blind.write(root / "environment/events.json", events)
    terrain = root / "baseline-terrain/fixture/elevation_m_375m.tif"
    terrain.parent.mkdir(parents=True)
    terrain.write_bytes(b"identity-only fixture; this test never runs environmental inference")
    states = root / "perimeters/fixture/states.npz"
    states.parent.mkdir(parents=True)
    np.savez(states, times=np.array(["2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"]),
             states=np.array([[[1, 0]], [[1, 1]]], dtype=np.uint8))
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
    _, _, rp, cp, _, cohort = registered
    entries = tmp_path / "predictions"
    (entries / "cases").mkdir(parents=True)
    record = dict(case=cohort["cases"][0], status="UNAVAILABLE")
    blind.write(entries / "RECEIPT.json", dict(registry_sha256=blind.sha(rp), cohort_sha256=blind.sha(cp), cases=[record]))
    np.savez(entries / "cases/unlisted.npz", y=[1])
    with pytest.raises(ValueError, match="Unlisted"):
        blind.score(SimpleNamespace(registry=rp, cohort=cp, entries=entries, out=tmp_path / "scores.json"))


def test_primary_gate_requires_fire_count_both_comparisons_and_calibration(blind):
    result = dict(fires=list(range(10)), models={}, paired={})
    for name, prediction in [("base_seed0", .02), ("persistence", 0.), ("dilation_best", 0.)]:
        result["models"][name] = dict(pooled=dict(lowest_bin=dict(count=10, mean_prediction=prediction, observed_frequency=.02)))
    for ref in ("persistence", "dilation_best"):
        result["paired"]["base_seed0__vs__" + ref] = dict(percentile_95_interval=[-.02, -.01])
    assert blind.primary_decision(result, "base_seed0")["statistical_superiority_criteria_pass"]
    result["fires"].pop()
    assert not blind.primary_decision(result, "base_seed0")["statistical_superiority_criteria_pass"]
    result["fires"].append(9)
    result["paired"]["base_seed0__vs__dilation_best"]["percentile_95_interval"] = [-.02, .001]
    assert not blind.primary_decision(result, "base_seed0")["statistical_superiority_criteria_pass"]


def test_declared_model_root_cannot_authenticate_a_different_import_tree(blind, registered, tmp_path):
    _, root, registry, cohort, _, _ = registered
    with pytest.raises(ValueError, match="exact verified source tree"):
        blind.validate(registry, cohort, tmp_path, root)
