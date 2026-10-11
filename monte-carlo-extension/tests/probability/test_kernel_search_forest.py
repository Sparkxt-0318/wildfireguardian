"""Execute forest search and saved-model evaluation on a small real cache schema."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from wildfire.search import Search as search
from wildfire.models import PatchRandomForest
from wildfire.cache import fit_normalization
from wildfire.cache import load_split
from wildfire.cohort import common_indices
from wildfire.cohort import crop_split
from wildfire.cohort import native_indices


@pytest.fixture
def small_cache(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    events = ["training", "validation", "testing"]
    metadata = {"channels": ["weather.temperature", "terrain.slope"], "kernel_size": 9,
                "dt_hours": 1.0, "event_ids": events,
                "splits": dict(zip(events, ("train", "validation", "test"))),
                "data_root": str(tmp_path), "source_files": []}
    (cache / "metadata.json").write_text(json.dumps(metadata))
    for event, split in enumerate(("train", "validation", "test")):
        n = 32
        rng = np.random.default_rng(90 + event)
        environment = rng.normal(100 + event, 5, (n, 2, 9, 9)).astype(np.float32)
        burned = np.zeros((n, 1, 9, 9), np.float32)
        # Distinct footprints and a no-contact group with some positive labels.
        for i in range(n):
            position = {1: 5, 2: 6, 3: 8}.get(i % 4)
            if position is not None:
                burned[i, 0, 4, position] = 1
        target = ((np.arange(n) // 4) % 2).astype(np.float32)
        weight = (1 + np.arange(n) % 5).astype(np.float64)
        np.savez_compressed(cache / f"{split}.npz", environment=environment, burned=burned,
                            target=target, weight=weight,
                            event_index=np.full(n, event, np.int64),
                            time_utc=np.arange(n, dtype=np.int64) * 3600,
                            row=np.arange(n, dtype=np.int64), col=np.full(n, 9, np.int64))
    return cache, metadata


def _args(cache, output):
    return SimpleNamespace(cache=cache, output=output, epochs=1, finalist_epochs=2,
                           seed=7, threads=1, device="cpu", forest_trees=3)


def _write_neural_checkpoints(args, metadata, protocol):
    """Make real checkpoints and score the public reloaded model on validation."""
    train = load_split(args.cache, "train", metadata)
    validation = load_split(args.cache, "validation", metadata)
    common = common_indices(validation)
    summaries = []
    native_balances = {}
    for candidate in [c for c in search.candidate_plan() if c["family"] in ("constant", "linear")]:
        k = candidate["kernel_size"]
        training = crop_split(train, k, native_indices(train, k))
        mean, std = fit_normalization(training, metadata=metadata)
        if k not in native_balances:
            native_balances[k] = search.fit_native_balance(training, metadata, protocol, args.output)
        optimization_weight, balance_audit = native_balances[k]
        # This fixture has continuous inputs only. It still requires the same
        # training-cohort audit as every fresh model, with unchanged weights.
        np.testing.assert_array_equal(optimization_weight, training.weight)
        contract = search.make_contract(candidate, metadata, protocol)
        contract["categorical_balance"] = balance_audit
        model = search.build(candidate, len(metadata["channels"]), torch.device("cpu"))
        path = args.output / f"{candidate['id']}.pt"
        torch.save({"contract": contract,
                    "model_state_dict": model.state_dict(), "normalization_mean": torch.from_numpy(mean),
                    "normalization_std": torch.from_numpy(std), "best_epoch": 1}, path)
        reloaded = search.load_trained_model(path, "cpu")
        tensors = search.tensor_data(crop_split(validation, k),
                                     reloaded.mean[:, 0, 0].numpy(), reloaded.std[:, 0, 0].numpy(),
                                     candidate["family"], torch.device("cpu"))
        p = search.probabilities(reloaded.model, tensors)
        score = search.brier(validation.target[common], p[common], validation.weight[common])
        summaries.append({"candidate": candidate, "checkpoint": str(path),
                          "checkpoint_sha256": search.sha256(path), "validation_common_brier": score,
                          "categorical_balance": balance_audit})
    (args.output / "candidate_selection.json").write_text(json.dumps(summaries))
    (args.output / "neural_complete.json").write_text(json.dumps({"completed": True}))
    return summaries


def test_forest_search_saved_preprocessing_and_full_prediction_finalize(small_cache, tmp_path, monkeypatch):
    cache, metadata = small_cache
    args = _args(cache, tmp_path / "run")
    # This exercises real forest fitting/save/reload/evaluation. Restrict only
    # the additional neural comparison families; their own tests cover fitting.
    monkeypatch.setattr(search, "SIZES", (3, 5))
    monkeypatch.setattr(search, "NEURAL_FAMILIES", ())
    search.forest_search(args)
    selections = json.loads((args.output / "forest_selection.json").read_text())
    assert len(selections) == 6
    assert all(not entry["test_used_for_selection"] for entry in selections)
    train = load_split(cache, "train", metadata)
    validation = load_split(cache, "validation", metadata)
    protocol = json.loads((args.output / "protocol.json").read_text())
    for record in selections:
        fitted = PatchRandomForest.load(record["checkpoint"])
        k = record["kernel_size"]
        training = crop_split(train, k, native_indices(train, k))
        mean, std = fit_normalization(training, metadata=metadata)
        np.testing.assert_array_equal(fitted.metadata["normalization_mean"], mean)
        np.testing.assert_array_equal(fitted.metadata["normalization_std"], std)
        assert fitted.metadata["cache_metadata_sha256"] == protocol["cache_sha256"]["metadata.json"]
        assert fitted.metadata["categorical_balance"] == record["categorical_balance"]
        assert fitted.metadata["categorical_balance_settings"] == protocol["categorical_balance_settings"]
        comparison = crop_split(validation, k, common_indices(validation))
        p = fitted.predict_probability((comparison.environment - mean[None, :, None, None]) / std[None, :, None, None],
                                       comparison.burned, channel_names=metadata["channels"])
        expected = np.dot(comparison.weight, (p - comparison.target) ** 2) / comparison.weight.sum()
        assert record["validation_common_brier"] == pytest.approx(expected)
        assert record["checkpoint_sha256"] == search.sha256(record["checkpoint"])

    # Create actual loadable constant/linear checkpoints for finalize's other
    # required families without running a second, redundant optimizer test.
    _write_neural_checkpoints(args, metadata, protocol)
    reported = []
    monkeypatch.setattr(search, "report", lambda *values: reported.append(values))
    search.finalize(args)
    assert len(reported) == 1
    complete = json.loads((args.output / "complete.json").read_text())
    assert complete["completed"] and all(complete["cache_sha256_verified"].values())
    thresholds = json.loads((args.output / "classification_thresholds.json").read_text())
    metrics = json.loads((args.output / "metrics.json").read_text())
    for split in ("train", "validation", "test"):
        base = load_split(cache, split, metadata)
        for name, record in metrics[split]["models"].items():
            assert record["coverage"]["predicted_count"] == len(base)
            assert record["coverage"]["no_contact_count"] > 0
            for scope in ("native", "common"):
                assert record[scope]["zero_contact_population_weight"] == 0
                assert record[scope]["validation_f1_threshold"] == thresholds[name][scope]["f1"]["threshold"]
                assert record[scope]["validation_mcc_threshold"] == thresholds[name][scope]["mcc"]["threshold"]
                for field in ("average_precision", "precision_recall_auc", "bernoulli_kl_divergence_mean", "bernoulli_hellinger_distance_mean"):
                    assert field in record[scope]
                assert "bins" in record[scope]["calibration"]
                assert sum(bin["sample_count"] for bin in record[scope]["calibration"]["bins"]) == record[scope]["sample_count"]
            with np.load(args.output / "predictions" / split / f"{name}.npz") as archive:
                assert len(archive["p"]) == len(base)
                np.testing.assert_array_equal(archive["source_index"], np.arange(len(base)))
                np.testing.assert_array_equal(archive["common_index"], common_indices(base))
        with np.load(args.output / "predictions" / f"{split}_common.npz") as archive:
            selected = common_indices(base)
            np.testing.assert_array_equal(archive["y"], base.target[selected])
            np.testing.assert_array_equal(archive["w"], base.weight[selected])
            np.testing.assert_array_equal(archive["source_index"], selected)


def test_resume_rejects_modified_frozen_cache(small_cache, tmp_path):
    cache, _ = small_cache
    args = _args(cache, tmp_path / "run")
    search.setup(args.output, args.cache, args.epochs, args.finalist_epochs, args.seed)
    path = cache / "metadata.json"
    path.write_text(path.read_text() + " ")  # Remains valid JSON; byte identity changed.
    with pytest.raises(ValueError, match="[Hh]ash|[Ii]ntegrity|[Cc]ache.*(changed|mismatch)"):
        search.setup(args.output, args.cache, args.epochs, args.finalist_epochs, args.seed)


@pytest.mark.parametrize("drift", ["checkpoint", "validation_score", "categorical_summary", "categorical_checkpoint", "categorical_report"])
def test_finalize_rejects_selected_checkpoint_or_score_drift_before_test_read(small_cache, tmp_path, monkeypatch, drift):
    cache, metadata = small_cache
    args = _args(cache, tmp_path / "run")
    monkeypatch.setattr(search, "SIZES", (3, 5))
    monkeypatch.setattr(search, "NEURAL_FAMILIES", ())
    search.forest_search(args)
    protocol = json.loads((args.output / "protocol.json").read_text())
    summaries = _write_neural_checkpoints(args, metadata, protocol)
    if drift == "checkpoint":
        path = Path(summaries[0]["checkpoint"])
        path.write_bytes(path.read_bytes() + b"modified")
        expected_error, message = ValueError, "checkpoint integrity mismatch"
    elif drift == "validation_score":
        summaries[0]["validation_common_brier"] += .05
        (args.output / "candidate_selection.json").write_text(json.dumps(summaries))
        expected_error, message = AssertionError, "checkpoint validation score mismatch"
    elif drift == "categorical_summary":
        del summaries[0]["categorical_balance"]
        (args.output / "candidate_selection.json").write_text(json.dumps(summaries))
        expected_error, message = ValueError, "Categorical balance report differs"
    elif drift == "categorical_checkpoint":
        path = Path(summaries[0]["checkpoint"])
        checkpoint = torch.load(path, weights_only=True)
        checkpoint["contract"]["categorical_balance"]["factor_max"] += 1
        torch.save(checkpoint, path)
        # A recomputed file digest cannot override the bound training audit.
        summaries[0]["checkpoint_sha256"] = search.sha256(path)
        (args.output / "candidate_selection.json").write_text(json.dumps(summaries))
        expected_error, message = ValueError, "Categorical balance audit differs"
    else:
        path = args.output / "categorical_balance" / "k3.json"
        audit = json.loads(path.read_text())
        audit["factor_max"] += 1
        path.write_text(json.dumps(audit))
        expected_error, message = ValueError, "Categorical balance report differs"
    reads = []
    original_load = search.load_split

    def track_read(directory, split, contract):
        reads.append(split)
        assert split != "test", "Test arrays must remain unread when selected model provenance fails"
        return original_load(directory, split, contract)

    monkeypatch.setattr(search, "load_split", track_read)
    with pytest.raises(expected_error, match=message):
        search.finalize(args)
    assert "test" not in reads
    assert not (args.output / "complete.json").exists()
