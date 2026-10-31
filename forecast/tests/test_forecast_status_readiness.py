"""Report readiness delegates to the authenticated freeze, never a caller flag."""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("forecast_status_readiness", ROOT / "research/forecast-v2/scripts/status.py")
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)


def setup_registry(tmp_path, source):
    path = tmp_path / "research/forecast-v2/BLIND_REGISTRY.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(dict(protocol_status="READY_FOR_OWNER_REGISTRATION", execution_status="NOT_READY_FOR_2026_EXECUTION", producer_source_sha256=source)))
    path.with_name("MODEL_SELECTION.json").write_text(json.dumps(dict(selected_variant="base")))
    return path


@pytest.mark.parametrize("source", [None, {}, [], "caller assertion"])
def test_empty_source_cannot_report_ready(tmp_path, monkeypatch, source):
    path = setup_registry(tmp_path, source)
    def forbidden(*args):
        raise AssertionError("Empty source should be refused before validator delegation")
    monkeypatch.setattr(S.F, "saved_registry_admission", forbidden)
    result = S.protocol_readiness(tmp_path, tmp_path / "run", path)
    assert result["protocol_status"] == "NOT_READY"
    assert result["execution_status"] == "NOT_READY_FOR_2026_EXECUTION"


def test_authenticated_positive_delegates_exact_freeze(tmp_path, monkeypatch):
    path = setup_registry(tmp_path, {"source.py": "a" * 64})
    calls = []
    def admitted(root, run, selection_path, selection, registry_path):
        calls.append((root, run, selection_path, selection, registry_path))
        return dict(registry=S.F.identity(root, registry_path))
    monkeypatch.setattr(S.F, "saved_registry_admission", admitted)
    result = S.protocol_readiness(tmp_path, tmp_path / "run", path)
    assert result["protocol_status"] == "READY_FOR_OWNER_REGISTRATION"
    assert result["execution_status"] == "NOT_READY_FOR_2026_EXECUTION"
    assert calls == [(tmp_path, tmp_path / "run", path.with_name("MODEL_SELECTION.json"), {"selected_variant": "base"}, path)]


def test_nonempty_incomplete_source_still_requires_authentication(tmp_path, monkeypatch):
    path = setup_registry(tmp_path, {"source.py": "a" * 64})
    def refused(*args):
        raise ValueError("Saved registry complete executed source closure changed")
    monkeypatch.setattr(S.F, "saved_registry_admission", refused)
    assert S.protocol_readiness(tmp_path, tmp_path / "run", path)["protocol_status"] == "NOT_READY"


def test_mismatched_authentication_proof_cannot_report_ready(tmp_path, monkeypatch):
    path = setup_registry(tmp_path, {"source.py": "a" * 64})
    monkeypatch.setattr(S.F, "saved_registry_admission", lambda *args: dict(registry={"path": "different", "sha256": "b" * 64}))
    assert S.protocol_readiness(tmp_path, tmp_path / "run", path)["protocol_status"] == "NOT_READY"


@pytest.mark.parametrize("record", [{"scores": {}}, {"status": "HOLD", "scores": {}}, {"status": "DESCRIPTIVE_MATCHED_SUBSET_COMPLETE", "scores_available": True, "scores": {}}])
def test_empty_farsite_scores_never_count_as_measurement(record):
    result = S.farsite_readiness(record)
    assert result["scores_available"] is False
    assert result["status"] == "HOLD_INCONSISTENT_EVIDENCE"


def test_farsite_partial_measurement_keeps_hold():
    record = dict(status="HOLD", execution_status="NO_NATIVE_EXECUTION_STORED_SCENARIOS_ONLY", superiority_criteria_pass=False,
                  measurement_status="DESCRIPTIVE_COMMON_SUBSET_AVAILABLE", scores_available=True,
                  scored_cases=1, total_historical_cases=2, cases=[{"status": "SCORED_COMMON_SUBSET", "cells": 3}, {"status": "UNAVAILABLE"}],
                  scores={"models": {"base": {"pooled": {"entries": 3}}}})
    result = S.farsite_readiness(record)
    assert result["status"] == "HOLD"
    assert result["scores_available"] is True
    assert result["scored_cases"] == 1


def test_farsite_completed_output_without_entries_remains_unavailable():
    record = dict(status="HOLD", execution_status="NO_NATIVE_EXECUTION_STORED_SCENARIOS_ONLY", superiority_criteria_pass=False,
                  measurement_status="UNAVAILABLE_NO_COMMON_ENTRIES", scores_available=False,
                  scored_cases=0, total_historical_cases=1, cases=[{"status": "UNAVAILABLE"}])
    result = S.farsite_readiness(record)
    assert result["status"] == "HOLD"
    assert result["scores_available"] is False


@pytest.mark.parametrize("with_measurements", [False, True])
def test_full_ledger_keeps_farsite_hold_separate(tmp_path, monkeypatch, with_measurements):
    evidence = tmp_path / "research/forecast-v2"
    evidence.mkdir(parents=True)
    run = tmp_path / "run"
    run.mkdir()
    split = evidence / "SPLIT.json"
    split.write_text("{}")
    (evidence / "RUN_PROTOCOL.json").write_text(json.dumps(dict(split_sha256=S.digest(split), mean_field_compare=dict(cases=[], horizons_hours=[]))))
    rows = [{"status": "SCORED_COMMON_SUBSET", "cells": 3}, {"status": "UNAVAILABLE"}] if with_measurements else [{"status": "UNAVAILABLE"}]
    record = dict(status="HOLD", execution_status="NO_NATIVE_EXECUTION_STORED_SCENARIOS_ONLY", superiority_criteria_pass=False,
                  measurement_status="DESCRIPTIVE_COMMON_SUBSET_AVAILABLE" if with_measurements else "UNAVAILABLE_NO_COMMON_ENTRIES",
                  scores_available=with_measurements, scored_cases=int(with_measurements), total_historical_cases=len(rows), cases=rows)
    if with_measurements:
        record["scores"] = {"models": {"base": {"pooled": {"entries": 3}}}}
    (evidence / "FARSITE_SCORES.json").write_text(json.dumps(record))
    monkeypatch.setattr(S, "ROOT", tmp_path)
    monkeypatch.setattr(S, "EVIDENCE", evidence)
    monkeypatch.setattr(S, "RUN", run)
    monkeypatch.setattr(S.F, "current_phase_identity", lambda: {"phases": []})
    S.main()
    report = json.loads((evidence / "REQUIREMENTS_STATUS.json").read_text())
    row = next(r for r in report["requirements"] if r["id"] == "1B-4-FARSITE-matched-subset")
    assert row["status"] == "HOLD"
    assert row["scores_available"] is with_measurements
    assert report["promotion_authority"] is False
