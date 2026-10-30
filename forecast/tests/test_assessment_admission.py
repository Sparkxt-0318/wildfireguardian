"""Synthetic admission failures must be refused before study results exist."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import numpy as np
import pytest


@pytest.fixture
def assessment():
    path = Path(__file__).resolve().parents[2] / "research/forecast-v2/scripts/score_cohorts.py"
    spec = importlib.util.spec_from_file_location("assessment_admission_fixture", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def case(assessment, tmp_path):
    sample = SimpleNamespace(initial=np.array([[True, False], [False, False]]),
        endpoint=np.array([[True, True], [False, True]]), score_mask=np.array([[False, True], [True, True]]),
        environment=np.zeros((2, 2, 2), dtype=np.float32), t1="2024-01-01T00:00:00Z",
        initial_age_hours=np.zeros((2, 2)), residence_hours=None)
    mask = sample.score_mask.copy()
    arrays = dict(row=np.nonzero(mask)[0], col=np.nonzero(mask)[1], y=sample.endpoint[mask].astype(np.int8),
                  **{"p_" + n: np.full(3, .5) for n in assessment.EXPECTED_MODELS})
    path = tmp_path / "case.npz"
    np.savez(path, **arrays)
    record = dict(receipt_version="wfg.forecast-assessment-case/2", **assessment.source_identity(sample),
        sha256=assessment.sha(path), scored_mask_sha256=assessment.array_sha(mask), scored_cells=3, positives=2)
    return sample, mask, arrays, path, record


def test_complete_current_reference_and_modelset_are_admitted(assessment, case):
    sample, mask, _, path, record = case
    assessment.validate_entries(path, record, sample, mask)


@pytest.mark.parametrize("field", ["initial_sha256", "endpoint_sha256", "environmental_snapshot_sha256",
                                    "reference_mask_sha256", "initial_age_sha256", "rectangle"])
def test_resigned_receipt_cannot_change_the_source_binding(assessment, case, field):
    sample, mask, _, path, record = case
    record[field] = "deliberately false source identity"
    with pytest.raises(ValueError, match="current verified source"):
        assessment.validate_entries(path, record, sample, mask)


@pytest.mark.parametrize("mutation", ["fractional", "outside", "reordered", "subset", "wrong_y", "missing_model", "extra_model", "bad_probability"])
def test_resigned_prediction_bytes_cannot_change_reference_or_model_population(assessment, case, mutation):
    sample, mask, arrays, path, record = case
    if mutation == "fractional": arrays["row"] = arrays["row"].astype(float) + .25
    if mutation == "outside": arrays["col"][0] = 9999
    if mutation == "reordered": arrays = {k: v[::-1] for k, v in arrays.items()}
    if mutation == "subset": arrays = {k: v[:2] for k, v in arrays.items()}
    if mutation == "wrong_y": arrays["y"][0] = 0
    if mutation == "missing_model": arrays.pop("p_c651_mc")
    if mutation == "extra_model": arrays["p_unregistered"] = np.zeros(3)
    if mutation == "bad_probability": arrays["p_c651_mc"][0] = np.nan
    np.savez(path, **arrays)
    record["sha256"] = assessment.sha(path)
    with pytest.raises(ValueError): assessment.validate_entries(path, record, sample, mask)


def test_partial_mask_cannot_be_admitted_when_full_support_is_available(assessment, case):
    sample, mask, _, path, record = case
    record["scored_mask_sha256"] = assessment.array_sha(np.zeros_like(mask))
    with pytest.raises(ValueError, match="common-support mask"):
        assessment.validate_entries(path, record, sample, mask)
