"""Multiscale rate math, unchanged controls, cohorts, and resumable searches."""

import copy
import itertools
import json

import numpy as np
import pytest
import torch

from wildfire.search import MixedSearch as search
from wildfire.search import ScheduledSearch as previous
from wildfire.cache import CachedSplit
from wildfire.cache import fit_normalization
from wildfire.cohort import common_indices
from wildfire.cohort import crop_split
from wildfire.cohort import native_indices
from wildfire.train import learning_rate_at_step
from wildfire.models import center_probability
from wildfire.train import fit_global_rate


SCHEDULES = ("constant", "warmup_cosine", "warmup_cosine_restarts")


@pytest.fixture(autouse=True)
def _one_cpu_thread():
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous_threads)


def _data(seed, event_index, count=24):
    rng = np.random.default_rng(seed)
    burned = np.zeros((count, 1, 9, 9), dtype=np.float32)
    burned[:, 0, 3, 4] = 1
    burned[::3, 0, 4, 5] = 1
    # Row zero has only outer-scale contact; row one has no contact at all.
    burned[:2] = 0
    burned[0, 0, 0, 0] = 1
    return CachedSplit(
        environment=(rng.normal(size=(count, 2, 9, 9)) * 2 + 10).astype(np.float32),
        burned=burned,
        target=(np.arange(count) % 3 == 0).astype(np.float32),
        weight=np.where(np.arange(count) % 4, 1, 7).astype(np.float64),
        event_index=np.full(count, event_index, dtype=np.int64),
        time_utc=np.full(count, 3600, dtype=np.int64),
        row=np.arange(count, dtype=np.int64),
        col=np.full(count, 10, dtype=np.int64),
    )


@pytest.fixture
def small_cache(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    metadata = dict(
        dt_hours=1.0, kernel_size=9,
        channels=["weather.temperature_2m", "terrain.slope_degrees"],
        event_ids=["train_event", "validation_event", "test_event"],
        splits={"train_event": "train", "validation_event": "validation", "test_event": "test"},
        data_root=str(cache), source_files=[],
    )
    (cache / "metadata.json").write_text(json.dumps(metadata))
    for index, split in enumerate(("train", "validation", "test")):
        np.savez(cache / f"{split}.npz", **vars(_data(801 + index, index)))
    return cache, metadata


def _equal_nested(first, second):
    if isinstance(first, torch.Tensor):
        torch.testing.assert_close(first, second, rtol=0, atol=0)
    elif isinstance(first, dict):
        assert first.keys() == second.keys()
        for key in first:
            _equal_nested(first[key], second[key])
    elif isinstance(first, (tuple, list)):
        assert len(first) == len(second)
        for left, right in zip(first, second, strict=True):
            _equal_nested(left, right)
    else:
        assert first == second


def _mixed_candidate(schedule="constant", width=32, horizon=4):
    return next(candidate for candidate in search.candidate_plan(
        learning_rates=(0.03,), schedules=(schedule,), horizon=horizon,
        warmup_epochs=1, minimum_lr_factor=0.1, restart_period=2,
    ) if candidate["family"] == "mixed" and candidate["hidden_channels"] == width)


def _train_candidate(candidate, metadata, protocol, output, epochs):
    device = torch.device("cpu")
    train_base, validation_base = _data(801, 0), _data(802, 1)
    ti, vi = native_indices(train_base, 9), native_indices(validation_base, 9)
    train, validation = crop_split(train_base, 9, ti), crop_split(validation_base, 9, vi)
    mean, std = fit_normalization(train)
    train_common = np.flatnonzero(np.isin(ti, common_indices(train_base)))
    validation_common = np.flatnonzero(np.isin(vi, common_indices(validation_base)))
    tensors = search.tensor_data(train, mean, std, "mixed", device, train_common)
    vt = search.tensor_data(validation, mean, std, "mixed", device, validation_common)
    return search.fit_candidate(
        candidate, train, validation, tensors, vt, mean, std, fit_global_rate(train),
        metadata, protocol, output, device, epochs,
    )


def test_default_plan_adds_three_mixed_settings_and_preserves_every_existing_control():
    plan = search.candidate_plan()
    original = previous.candidate_plan()
    assert len(plan) == len({candidate["id"] for candidate in plan}) == 344
    assert [candidate for candidate in plan if candidate["family"] != "mixed"] == original
    mixed = [candidate for candidate in plan if candidate["family"] == "mixed"]
    assert len(mixed) == 24
    assert {candidate["kernel_size"] for candidate in mixed} == {9}
    assert all(candidate["kernel_sizes"] == [3, 5, 7, 9] for candidate in mixed)
    assert all(candidate["mixing_constraint"] == "nonnegative" for candidate in mixed)
    for base_id in {candidate["base_configuration_id"] for candidate in mixed}:
        variants = [candidate for candidate in mixed if candidate["base_configuration_id"] == base_id]
        assert {(candidate["learning_rate"], candidate["scheduler"]["name"]) for candidate in variants} == set(
            itertools.product((0.001, 0.003, 0.01, 0.03), ("constant", "warmup_cosine"))
        )


def test_restart_plan_has_516_unique_candidates_and_preserves_existing_controls():
    plan = search.candidate_plan(schedules=SCHEDULES)
    assert len(plan) == len({candidate["id"] for candidate in plan}) == 516
    assert [candidate for candidate in plan if candidate["family"] != "mixed"] == previous.candidate_plan(schedules=SCHEDULES)


def test_mixed_native_cohort_uses_union_support_but_matched_cohort_remains_three_contact():
    data = _data(801, 0)
    native = native_indices(data, 9)
    common = common_indices(data)
    assert 0 in native and 0 not in common
    assert 1 not in native and 1 not in common
    np.testing.assert_array_equal(native, np.array([0, *range(2, 24)]))
    np.testing.assert_array_equal(common, np.arange(2, 24))
    selected = crop_split(data, 9, native)
    mean, std = fit_normalization(selected)
    tensors = search.tensor_data(selected, mean, std, "mixed", torch.device("cpu"),
                                 np.flatnonzero(np.isin(native, common)))
    assert tensors.features.shape == (23, 2 * 9 * 9)
    np.testing.assert_array_equal(tensors.common, np.arange(1, 23))


def test_cached_mixed_probability_and_parameter_gradients_match_public_center():
    torch.manual_seed(51)
    model = search.build(_mixed_candidate(width=16), 2, torch.device("cpu")).double().eval()
    reference = copy.deepcopy(model)
    data = _data(801, 0)
    environment = torch.from_numpy(data.environment).double() / 10
    burned = torch.from_numpy(data.burned).double()
    cached = search.cached_probability(model, environment.flatten(1), burned.flatten(1))
    public = center_probability(reference, environment, burned)
    torch.testing.assert_close(cached, public, rtol=1e-12, atol=1e-12)
    assert cached[0] > 0 and cached[1] == 0
    loss_weights = torch.linspace(0.3, 1.7, len(cached), dtype=torch.float64)
    (loss_weights * cached.square()).sum().backward()
    (loss_weights * public.square()).sum().backward()
    for (name, parameter), (reference_name, reference_parameter) in zip(
        model.named_parameters(), reference.named_parameters(), strict=True,
    ):
        assert name == reference_name
        assert parameter.grad is not None and reference_parameter.grad is not None
        torch.testing.assert_close(parameter.grad, reference_parameter.grad, rtol=1e-10, atol=1e-12)
    assert torch.count_nonzero(model.mixing_logits.grad) == 4


@pytest.mark.parametrize("schedule_name", SCHEDULES)
def test_mixed_dropout_adamw_coefficients_and_rng_resume_equal_continuous(
    small_cache, tmp_path, monkeypatch, schedule_name,
):
    cache, metadata = small_cache
    candidate = _mixed_candidate(schedule_name)
    assert candidate["dropout"] > 0
    optimizer_rates = []
    real_step = torch.optim.AdamW.step

    def capture_step(optimizer, *args, **kwargs):
        optimizer_rates.append([group["lr"] for group in optimizer.param_groups])
        return real_step(optimizer, *args, **kwargs)

    monkeypatch.setattr(torch.optim.AdamW, "step", capture_step)
    outputs = (tmp_path / "continuous", tmp_path / "resumed")
    summaries = []
    for output, budgets in zip(outputs, ((4,), (2, 4)), strict=True):
        protocol = search.setup(
            output, cache, 2, 4, 71, learning_rates=(0.03,), schedules=(schedule_name,),
            warmup_epochs=1, minimum_lr_factor=0.1, restart_period=2,
        )
        for budget in budgets:
            summary = _train_candidate(candidate, metadata, protocol, output, budget)
        summaries.append(summary)
    expected = [learning_rate_at_step(0.03, step, candidate["scheduler"]) for step in range(1, 5)]
    assert optimizer_rates == [[rate] for rate in expected + expected]
    assert summaries[0]["best_epoch"] == summaries[1]["best_epoch"]
    assert summaries[0]["validation_common_brier"] == summaries[1]["validation_common_brier"]
    assert summaries[0]["selected_mixing_weights"] == summaries[1]["selected_mixing_weights"]
    assert summaries[0]["train_sample_count"] == 23
    assert summaries[0]["validation_common_sample_count"] == 22
    states = [torch.load(output / "candidates" / candidate["id"] / "last.pt", weights_only=True)
              for output in outputs]
    for key in ("model_state_dict", "optimizer_state_dict", "epoch", "best_validation_brier", "cpu_rng_state", "best_checkpoint"):
        _equal_nested(states[0][key], states[1][key])
    assert all(int(state["step"]) == 4 for state in states[0]["optimizer_state_dict"]["state"].values())
    histories = [json.loads((output / "candidates" / candidate["id"] / "history.json").read_text()) for output in outputs]
    for history in histories:
        assert [record["optimizer_step"] for record in history] == [1, 2, 3, 4]
        assert [record["learning_rate"] for record in history] == expected
        assert all(len(record["mixing_weights"]) == 4 for record in history)
    for first, second in zip(*histories, strict=True):
        assert {key: value for key, value in first.items() if key != "elapsed_seconds"} == {
            key: value for key, value in second.items() if key != "elapsed_seconds"
        }


def test_additive_mixed_protocol_preserves_previous_frozen_source_hashes(small_cache, tmp_path):
    cache, _ = small_cache
    old = previous.setup(tmp_path / "previous", cache, 2, 4, 71, warmup_epochs=1, restart_period=2)
    new = search.setup(tmp_path / "mixed", cache, 2, 4, 71, warmup_epochs=1, restart_period=2)
    previous.verify_protocol(old, cache)
    for name, digest in old["training_source_sha256"].items():
        if name != "search.py":
            assert new["training_source_sha256"][name] == digest
    assert {"search.py", "models.py", "inference.py"} <= new["training_source_sha256"].keys()


@pytest.mark.parametrize("changed", (
    {"learning_rates": (0.001, 0.03)}, {"schedules": ("constant",)}, {"finalist_epochs": 5},
))
def test_mixed_resume_rejects_changed_search_protocol(small_cache, tmp_path, changed):
    cache, _ = small_cache
    options = dict(epochs=2, finalist_epochs=4, seed=71, warmup_epochs=1, restart_period=2)
    output = tmp_path / "mixed"
    search.setup(output, cache, **options)
    options.update(changed)
    with pytest.raises(ValueError, match="Resume protocol mismatch"):
        search.setup(output, cache, **options)


def test_complete_small_search_scores_27_models_with_five_long_finalists_and_guards_test(
    small_cache, tmp_path, monkeypatch,
):
    cache, _ = small_cache
    output = tmp_path / "full_search"
    args = search.parser().parse_args([
        "run", "--cache", str(cache), "--output", str(output), "--device", "cpu",
        "--epochs", "1", "--finalist-epochs", "2", "--warmup-epochs", "0",
        "--learning-rates", "0.01", "--schedules", "constant", "--forest-trees", "3", "--threads", "1",
    ])
    loaded_splits = []
    real_load_split = search.load_split

    def track_load_split(cache_path, split, metadata):
        loaded_splits.append(split)
        return real_load_split(cache_path, split, metadata)

    monkeypatch.setattr(search, "load_split", track_load_split)
    search.train_search(args)
    search.forest_search(args)
    assert "test" not in loaded_splits
    neural = json.loads((output / "neural_complete.json").read_text())
    assert neural["candidates"] == 43 and neural["long_finalists"] == 5
    search.finalize(args)
    assert loaded_splits.count("test") == 1
    complete = json.loads((output / "complete.json").read_text())
    assert complete["completed"] and complete["evaluated_models"] == 27
    assert not complete["test_used_for_selection"]
    assert all(complete["cache_sha256_verified"].values())
    best_models = json.loads((output / "best_models.json").read_text())
    assert len(best_models) == 27 and "mixed_k9" in best_models
    mixed = best_models["mixed_k9"]
    assert mixed["candidate"]["family"] == "mixed"
    assert set(mixed["selected_mixing_weights"]) == {"3", "5", "7", "9"}
    payload = np.load(output / "predictions" / "test" / f"{mixed['candidate']['id']}.npz")
    assert payload["p"].shape == (24,) and payload["p"][1] == 0
    assert 0 in payload["native_index"] and 0 not in payload["common_index"]
    np.testing.assert_array_equal(payload["common_index"], np.arange(2, 24))
    metrics = json.loads((output / "metrics.json").read_text())
    assert set(metrics) == {"train", "validation", "test"}
    assert all(len(split["models"]) == 27 for split in metrics.values())
    assert (output / "report.md").is_file() and (output / "learning_rate_comparison.csv").is_file()
    # A checkpoint alteration must be rejected before another test-cache read.
    checkpoint = mixed["checkpoint"]
    with open(checkpoint, "ab") as handle:
        handle.write(b"integrity test")
    previous_test_reads = loaded_splits.count("test")
    with pytest.raises(ValueError, match="Selected checkpoint integrity mismatch"):
        search.finalize(args)
    assert loaded_splits.count("test") == previous_test_reads
