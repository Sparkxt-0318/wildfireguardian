"""Total burned probability, Monte Carlo uncertainty, and result exports."""

from dataclasses import replace
import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from wildfire import CumulativePrediction, Prediction


OPTIONAL_FIELDS = (
    "burned_probability", "mc_standard_error", "confidence_lower", "confidence_upper",
)


def _details(shape=(2, 1, 2, 3)):
    probability = torch.full(shape, 0.25)
    valid = torch.ones(shape, dtype=torch.bool)
    return SimpleNamespace(
        probability=probability, valid=valid,
        rate=torch.full(shape, 0.5), rate_valid=valid.clone(),
    )


def _prediction(hours, *, shape=(2, 1, 2, 3), metadata=None):
    details = _details(shape)
    return Prediction.from_details(
        details, dt_hours=hours,
        burned_probability=torch.full(shape, 0.75),
        mc_standard_error=torch.full(shape, 0.01),
        confidence_lower=torch.full(shape, 0.2),
        confidence_upper=torch.full(shape, 0.3),
        metadata={"method": "recursive", "n_samples": 1024}
        if metadata is None else metadata,
    )


def test_prediction_preserves_old_positional_constructor_and_absent_exports():
    details = _details()
    result = Prediction(
        details.probability, details.valid, details.rate, details.rate_valid,
        None, None, 3, "fixture", None, None, None, None,
    )
    assert all(getattr(result, name) is None for name in OPTIONAL_FIELDS)
    assert result.metadata is None
    assert set(result.numpy()) == {"probability", "valid", "rate", "rate_valid", "dt_hours"}
    cumulative = CumulativePrediction((3,), (result,))
    assert all(getattr(cumulative, name) is None for name in OPTIONAL_FIELDS)
    assert "metadata_json" not in cumulative.numpy()


def test_optional_fields_share_probability_validity_and_padding():
    details = _details()
    details.valid[0, 0, 0, 0] = False
    pixels = np.ones((2, 3), dtype=bool)
    pixels[1, 2] = False
    values = {name: np.full(details.probability.shape, index + 0.1)
              for index, name in enumerate(OPTIONAL_FIELDS)}
    result = Prediction.from_details(
        details, pixel_valid=pixels, time_valid=np.array([True, False]), **values,
    )
    assert result.valid.sum().item() == 4
    for name, value in values.items():
        actual = getattr(result, name)
        assert actual.device == result.probability.device
        assert actual.dtype == result.probability.dtype
        assert torch.isnan(actual[~result.valid]).all()
        torch.testing.assert_close(actual[result.valid], torch.tensor(value, dtype=actual.dtype)[result.valid])


@pytest.mark.parametrize("field", OPTIONAL_FIELDS)
def test_optional_fields_reject_wrong_complete_shape(field):
    with pytest.raises(ValueError, match=field):
        Prediction.from_details(_details(), **{field: np.zeros((2, 3))})


def test_prediction_metadata_is_copied_and_npz_export_needs_no_pickle(tmp_path):
    metadata = {"method": "recursive", "n_samples": 1024, "assumptions": ["hourly"]}
    result = _prediction(1, metadata=metadata)
    metadata["assumptions"].append("changed")
    assert result.metadata["assumptions"] == ["hourly"]
    arrays = result.numpy()
    assert arrays["metadata_json"].shape == ()
    assert arrays["metadata_json"].dtype.kind == "U"
    assert json.loads(arrays["metadata_json"].item()) == result.metadata
    for name in OPTIONAL_FIELDS:
        arrays[name][:] = -10
        assert not torch.any(getattr(result, name) == -10)
    path = tmp_path / "prediction.npz"
    np.savez_compressed(path, **result.numpy())
    with np.load(path, allow_pickle=False) as saved:
        assert json.loads(saved["metadata_json"].item()) == result.metadata
        np.testing.assert_array_equal(saved["burned_probability"], result.burned_probability.numpy())


def test_cumulative_optional_fields_stack_and_selection_keeps_uncertainty():
    first = _prediction(1)
    third = _prediction(3, metadata={"n_samples": 1024, "method": "recursive"})
    third = replace(third, burned_probability=torch.full_like(third.probability, 0.9))
    result = CumulativePrediction((3, 1), (third, first))
    assert result.at(hours=1) is first
    assert result.at(hours=3) is third
    for name in OPTIONAL_FIELDS:
        torch.testing.assert_close(getattr(result, name), torch.stack((getattr(third, name), getattr(first, name))))
    assert result.burned_probability.shape == (2, 2, 1, 2, 3)
    copied = result.metadata
    copied["method"] = "changed"
    assert result.metadata["method"] == "recursive"
    arrays = result.numpy()
    assert json.loads(arrays["metadata_json"].item()) == result.metadata
    for name in OPTIONAL_FIELDS:
        arrays[name][:] = -10
        assert not torch.any(getattr(result, name) == -10)


@pytest.mark.parametrize("field", OPTIONAL_FIELDS)
def test_cumulative_optional_fields_reject_mixed_presence_or_shape(field):
    first, third = _prediction(1), _prediction(3)
    with pytest.raises(ValueError, match=field):
        CumulativePrediction((1, 3), (first, replace(third, **{field: None})))
    with pytest.raises(ValueError, match=field):
        CumulativePrediction((1, 3), (first, replace(third, **{field: torch.zeros(1, 2, 3)})))


def test_cumulative_metadata_requires_shared_presence_and_values():
    first, third = _prediction(1), _prediction(3)
    with pytest.raises(ValueError, match="metadata"):
        CumulativePrediction((1, 3), (first, replace(third, metadata=None)))
    with pytest.raises(ValueError, match="metadata"):
        CumulativePrediction((1, 3), (first, replace(third, metadata={"method": "fixed"})))


def test_snapshot_reference_alignment_promotes_optional_tensors(monkeypatch):
    prediction = _prediction(1, shape=(1, 2, 3))
    prediction = replace(prediction, time_utc=np.asarray(10_000, dtype=np.int64))
    result = CumulativePrediction((1,), (prediction,))
    reference = {
        "burned_area": np.stack((np.zeros((1, 2, 3)), np.ones((1, 2, 3)))),
        "burned_area_valid": np.ones((2, 1, 2, 3), dtype=bool),
        "time_utc": np.asarray([10_000, 13_600], dtype=np.int64),
    }
    original = Prediction.aligned_burned_area

    def checked_alignment(promoted, observed):
        for name in OPTIONAL_FIELDS:
            assert getattr(promoted, name).shape == promoted.probability.shape == (1, 1, 2, 3)
        return original(promoted, observed)

    monkeypatch.setattr(Prediction, "aligned_burned_area", checked_alignment)
    target, valid = result.aligned_observations(reference, hours=1)
    assert target.shape == valid.shape == prediction.probability.shape
    assert valid.all()
    np.testing.assert_array_equal(target, np.ones((1, 2, 3)))

