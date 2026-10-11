"""Guard common-cohort pairing and validation-only direct-kernel selection."""

import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from wildfire_burned_area_hourly.probability_model.direct_convolution import evaluate


def comparison_fixture(tmp_path, monkeypatch, corrupt=False):
    run, cache, prior = (tmp_path / name for name in ("run", "cache", "prior"))
    for directory in (run, cache, prior / "common_predictions"):
        directory.mkdir(parents=True)
    schema = {"channels": ["temperature"], "source_channels": ["temperature"],
              "categorical_classes": {}, "event_ids": ["fire"], "splits": {"fire": "test"}}
    (cache / "metadata.json").write_text(json.dumps(schema))
    digest = hashlib.sha256((cache / "metadata.json").read_bytes()).hexdigest()
    protocol = {"kernel_sizes": [3, 5, 7, 9], "training": {"threads": 1},
                "common_reference": str(prior), "native_data": {"9": str(cache)},
                "native_metadata_sha256": {str(k): digest for k in (3, 5, 7, 9)}}
    (run / "protocol.json").write_text(json.dumps(protocol))
    y = np.array([0, 1, 0], dtype=np.float32)
    w = np.array([4, 1, 2], dtype=np.float64)
    burned = np.zeros((3, 1, 9, 9), dtype=np.float32)
    burned[:, 0, 3, 4] = 1
    payload = {"y": y, "w": w, "event_index": np.zeros(3, dtype=np.int64),
               "time_utc": np.array([3600, 7200, 10800]),
               "row": np.arange(3, dtype=np.int32), "col": np.ones(3, dtype=np.int32)}
    for k in (3, 5, 7, 9):
        payload[f"p_{k}"] = np.array([0.1, 0.5, 0.2], dtype=np.float32)
        payload[f"neighbor_count_{k}"] = np.ones(3, dtype=np.float32)
    for split in ("validation", "test", "train"):
        arrays = {key: value.copy() for key, value in payload.items()}
        if corrupt and split == "validation":
            arrays["w"][0] += 1
        np.savez_compressed(prior / "common_predictions" / f"{split}.npz", **arrays)

    def load_model(path, device):
        k = int(path.parent.parent.name.split("x")[0])
        contract = {**schema, "kernel_constraint": "signed", "training_clipping": False,
                    "evaluation_clipping": [0, 1], "cache_metadata_sha256": digest,
                    "eligibility": "at_least_one_burned_neighbor"}
        return SimpleNamespace(model=SimpleNamespace(kernel_size=k), contract=contract,
                               mean=torch.zeros(1, 1, 1))

    order = []
    def load_data(directory, split, metadata):
        order.append(split)
        if split == "test":
            selected = json.loads((run / "common_selection.json").read_text())
            assert selected["kernel_size"] == 5
            assert selected["test_used_for_selection"] is False
        return SimpleNamespace(burned=burned, target=y, weight=w,
                               event_index=payload["event_index"], time_utc=payload["time_utc"],
                               row=payload["row"], col=payload["col"], split=split)

    def predict(model, data, indices):
        k = model.model.kernel_size
        # Validation favors 5; test deliberately favors 9. Raw values exercise clipping.
        winner = (data.split == "validation" and k == 5) or (data.split == "test" and k == 9)
        raw = np.array([-0.2, 1.4, -0.1] if winner else [0.4, -0.3, 0.4], dtype=np.float32)
        return raw, np.ones(3, dtype=np.float32), 0.0

    monkeypatch.setattr(evaluate, "load_trained_model", load_model)
    monkeypatch.setattr(evaluate, "load_split", load_data)
    monkeypatch.setattr(evaluate, "frozen_raw_predictions", predict)
    return run, payload, order


def test_validation_selects_before_test_and_preserves_raw_scores(tmp_path, monkeypatch):
    run, prior, order = comparison_fixture(tmp_path, monkeypatch)
    result = evaluate.evaluate_runs(run, device="cpu")
    assert order == ["validation", "test", "train"]
    assert result["selection"]["kernel_size"] == 5
    assert result["splits"]["test"]["models"]["direct_9"]["brier"] == 0
    assert result["splits"]["test"]["models"]["direct_5"]["exact_negative_log_likelihood_mean"] == "infinity"
    with np.load(run / "common_predictions/validation.npz") as saved:
        for key in ("y", "w", "row", "col", "event_index", "time_utc"):
            np.testing.assert_array_equal(saved[key], prior[key])
        np.testing.assert_array_equal(saved["p_direct_5"], [0, 1, 0])
        assert saved["raw_direct_5"].min() < 0
        assert saved["raw_direct_5"].max() > 1
        for k in (3, 5, 7, 9):
            np.testing.assert_array_equal(saved[f"p_original_{k}"], prior[f"p_{k}"])


def test_common_comparison_rejects_changed_original_weights(tmp_path, monkeypatch):
    run, _, order = comparison_fixture(tmp_path, monkeypatch, corrupt=True)
    with pytest.raises(AssertionError, match="Shared validation w changed"):
        evaluate.evaluate_runs(run, device="cpu")
    assert order == ["validation"]
    assert not (run / "common_selection.json").exists()


def test_raw_diagnostics_keeps_sampling_weights_and_unclipped_error():
    y = np.array([0, 1, 0], dtype=np.float32)
    raw = np.array([-1, 2, 0.5], dtype=np.float32)
    w = np.array([8, 1, 1], dtype=np.float64)
    result = evaluate.raw_diagnostics(y, raw, w)
    assert result["raw_brier"] == pytest.approx((8 + 1 + 0.25) / 10)
    assert result["below_zero_weighted_fraction"] == 0.8
    assert result["above_one_weighted_fraction"] == 0.1
    assert result["below_zero_count"] == 1
