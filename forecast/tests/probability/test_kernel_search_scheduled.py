"""Controlled LR comparisons, scheduler boundaries, and exact continuation.

The four-epoch numerical checks deliberately exercise dropout, AdamW state,
and the two-stage search boundary without starting a long training run.
"""

import copy
import itertools
import json
import math

import numpy as np
import pytest
import torch

from wildfire.search import Search as frozen_search
from wildfire.search import ScheduledSearch as search
from wildfire.cache import CachedSplit
from wildfire.cache import fit_normalization
from wildfire.cohort import crop_split
from wildfire.train import learning_rate_at_step
from wildfire.train import fit_global_rate


RATES = (0.001, 0.003, 0.01, 0.03)
SCHEDULES = ("constant", "warmup_cosine", "warmup_cosine_restarts")


@pytest.fixture(autouse=True)
def _one_cpu_thread():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def _scheduler(name="warmup_cosine", *, horizon=10, warmup=2, floor=0.1, restart=3):
    return dict(name=name, horizon=horizon, warmup_epochs=warmup,
                minimum_lr_factor=floor, restart_period=restart)


def _data(seed, event_index, count=24):
    rng = np.random.default_rng(seed)
    burned = np.zeros((count, 1, 9, 9), dtype=np.float32)
    burned[:, 0, 3, 4] = 1
    burned[::3, 0, 4, 5] = 1
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


def _train_candidate(candidate, metadata, protocol, output, epochs):
    device = torch.device("cpu")
    train = crop_split(_data(801, 0), 3)
    validation = crop_split(_data(802, 1), 3)
    mean, std = fit_normalization(train)
    tensors = search.tensor_data(train, mean, std, candidate["family"], device)
    validation_tensors = search.tensor_data(validation, mean, std, candidate["family"], device)
    return search.fit_candidate(
        candidate, train, validation, tensors, validation_tensors, mean, std,
        fit_global_rate(train), metadata, protocol, output, device, epochs,
    )


def test_default_search_is_complete_controlled_lr_schedule_crossing():
    plan = search.candidate_plan()
    base = {candidate["id"]: candidate for candidate in frozen_search.candidate_plan()}
    assert len(plan) == 320
    assert len({candidate["id"] for candidate in plan}) == 320
    assert set(candidate["base_configuration_id"] for candidate in plan) == set(base)
    for base_id, configuration in base.items():
        variants = [candidate for candidate in plan if candidate["base_configuration_id"] == base_id]
        assert len(variants) == 8
        assert {(candidate["learning_rate"], candidate["scheduler"]["name"]) for candidate in variants} == set(
            itertools.product(RATES, ("constant", "warmup_cosine"))
        )
        for candidate in variants:
            for key, value in configuration.items():
                if key not in ("id", "learning_rate"):
                    assert candidate[key] == value, (base_id, key)
            assert candidate["scheduler"]["horizon"] == 4096
            assert candidate["scheduler"]["warmup_epochs"] == 32
            assert candidate["scheduler"]["minimum_lr_factor"] == 0.01


def test_optional_restart_schedule_is_an_independent_controlled_comparison():
    plan = search.candidate_plan(learning_rates=RATES, schedules=SCHEDULES)
    assert len(plan) == 480
    assert len({candidate["id"] for candidate in plan}) == 480
    assert {candidate["scheduler"]["name"] for candidate in plan} == set(SCHEDULES)
    for base_id in {candidate["base_configuration_id"] for candidate in plan}:
        variants = [candidate for candidate in plan if candidate["base_configuration_id"] == base_id]
        assert {(candidate["learning_rate"], candidate["scheduler"]["name"]) for candidate in variants} == set(
            itertools.product(RATES, SCHEDULES)
        )


def test_distinct_close_learning_rates_cannot_share_an_artifact_directory():
    rates = (0.0010000001, 0.0010000002)
    # A display formatter with six significant figures rounds both to 0.001.
    assert format(rates[0], "g") == format(rates[1], "g")
    plan = search.candidate_plan(learning_rates=rates, schedules=("constant",))
    assert len(plan) == 80
    assert len({candidate["id"] for candidate in plan}) == 80


@pytest.mark.parametrize("rates", ((), (0.001, 0.001), (0,), (-0.001,), (float("nan"),), (float("inf"),)))
def test_search_rejects_empty_duplicate_nonpositive_and_nonfinite_rates(rates):
    with pytest.raises(ValueError, match="Learning rates"):
        search.candidate_plan(learning_rates=rates)


@pytest.mark.parametrize("schedules", ((), ("constant", "constant"), ("unknown",)))
def test_search_rejects_empty_duplicate_and_unknown_schedules(schedules):
    with pytest.raises(ValueError):
        search.candidate_plan(schedules=schedules)


def test_constant_learning_rate_has_no_unintended_warmup_or_decay():
    schedule = _scheduler("constant")
    assert [learning_rate_at_step(0.03, step, schedule) for step in range(1, 11)] == [0.03] * 10


def test_warmup_cosine_closed_form_boundaries_midpoint_and_positive_endpoint():
    schedule = _scheduler()
    expected = {1: 0.015, 2: 0.03, 6: 0.0165, 10: 0.003}
    for step, rate in expected.items():
        assert learning_rate_at_step(0.03, step, schedule) == pytest.approx(rate, rel=1e-14)
    rates = [learning_rate_at_step(0.03, step, schedule) for step in range(1, 11)]
    assert 0 < min(rates) <= max(rates) == 0.03
    assert rates[0] < rates[1]
    assert all(first > second for first, second in zip(rates[1:], rates[2:], strict=False))
    # This checks the mathematical trajectory, not only the named landmarks.
    for step in range(3, 11):
        reference = 0.003 + 0.027 * (1 + math.cos(math.pi * (step - 2) / 8)) / 2
        assert learning_rate_at_step(0.03, step, schedule) == pytest.approx(reference, rel=1e-14)


def test_cosine_without_warmup_uses_first_and_last_optimizer_steps_as_endpoints():
    schedule = _scheduler(horizon=5, warmup=0)
    assert learning_rate_at_step(0.03, 1, schedule) == 0.03
    assert learning_rate_at_step(0.03, 3, schedule) == pytest.approx(0.0165)
    assert learning_rate_at_step(0.03, 5, schedule) == pytest.approx(0.003)


def test_restart_cycles_hit_floor_and_return_to_peak_at_named_optimizer_steps():
    schedule = _scheduler("warmup_cosine_restarts", horizon=11)
    expected = {1: 0.015, 2: 0.03, 3: 0.03, 4: 0.0165, 5: 0.003,
                6: 0.03, 8: 0.003, 9: 0.03, 11: 0.003}
    for step, rate in expected.items():
        assert learning_rate_at_step(0.03, step, schedule) == pytest.approx(rate, rel=1e-14)
    assert min(learning_rate_at_step(0.03, step, schedule) for step in range(1, 12)) > 0


@pytest.mark.parametrize("peak", (0, -0.03, float("nan"), float("inf")))
def test_schedule_rejects_nonpositive_and_nonfinite_peak_rates(peak):
    with pytest.raises(ValueError, match="Peak learning rate"):
        learning_rate_at_step(peak, 1, _scheduler())


@pytest.mark.parametrize("step", (0, -1, 11, 1.5, True))
def test_schedule_rejects_invalid_optimizer_steps(step):
    with pytest.raises(ValueError, match="Optimizer step"):
        learning_rate_at_step(0.03, step, _scheduler())


@pytest.mark.parametrize("changed", (
    {"horizon": 0}, {"horizon": True}, {"warmup_epochs": -1},
    {"warmup_epochs": 10}, {"warmup_epochs": 0.5},
    {"minimum_lr_factor": -0.1}, {"minimum_lr_factor": 1.1},
    {"minimum_lr_factor": float("nan")}, {"restart_period": 1},
    {"name": "unknown"},
))
def test_schedule_rejects_invalid_configuration(changed):
    scheduler = _scheduler()
    scheduler.update(changed)
    with pytest.raises(ValueError):
        learning_rate_at_step(0.03, 1, scheduler)


@pytest.mark.parametrize("schedule_name", SCHEDULES)
def test_actual_lr_steps_and_dropout_adamw_rng_resume_equal_continuous(
    small_cache, tmp_path, monkeypatch, schedule_name,
):
    cache, metadata = small_cache
    candidate = next(
        candidate for candidate in search.candidate_plan(
            learning_rates=(0.03,), schedules=(schedule_name,), horizon=4,
            warmup_epochs=1, minimum_lr_factor=0.1, restart_period=2,
        ) if candidate["kernel_size"] == 3 and candidate["family"] == "residual_mlp"
        and candidate["hidden_channels"] == 32
    )
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
            output, cache, 2, 4, 71,
            learning_rates=(0.03,), schedules=(schedule_name,), warmup_epochs=1,
            minimum_lr_factor=0.1, restart_period=2,
        )
        for budget in budgets:
            summary = _train_candidate(candidate, metadata, protocol, output, budget)
        summaries.append(summary)
    expected = [learning_rate_at_step(0.03, step, candidate["scheduler"]) for step in range(1, 5)]
    assert optimizer_rates == [[rate] for rate in expected + expected]
    assert summaries[0]["best_epoch"] == summaries[1]["best_epoch"]
    assert summaries[0]["validation_common_brier"] == summaries[1]["validation_common_brier"]
    assert summaries[0]["epochs_completed"] == summaries[1]["epochs_completed"] == 4
    states = [torch.load(output / "candidates" / candidate["id"] / "last.pt", weights_only=True)
              for output in outputs]
    for key in ("model_state_dict", "optimizer_state_dict", "epoch", "best_validation_brier", "cpu_rng_state", "best_checkpoint"):
        _equal_nested(states[0][key], states[1][key])
    assert all(int(state["step"]) == 4 for state in states[0]["optimizer_state_dict"]["state"].values())
    histories = [json.loads((output / "candidates" / candidate["id"] / "history.json").read_text())
                 for output in outputs]
    assert len(histories[0]) == len(histories[1]) == 4
    for history in histories:
        assert [record["optimizer_step"] for record in history] == [1, 2, 3, 4]
        assert [record["learning_rate"] for record in history] == expected
    for first, second in zip(*histories, strict=True):
        assert {key: value for key, value in first.items() if key != "elapsed_seconds"} == {
            key: value for key, value in second.items() if key != "elapsed_seconds"
        }


def test_lr_and_schedule_variants_begin_from_identical_model_and_rng(small_cache, tmp_path, monkeypatch):
    cache, metadata = small_cache
    candidates = [candidate for candidate in search.candidate_plan(
        learning_rates=(0.001, 0.03), schedules=("constant", "warmup_cosine"),
        horizon=4, warmup_epochs=1, minimum_lr_factor=0.1, restart_period=2,
    ) if candidate["kernel_size"] == 3 and candidate["family"] == "residual_mlp"
        and candidate["hidden_channels"] == 32]
    assert len(candidates) == 4
    initial_states = []
    initial_rngs = []
    real_build = search.build

    def capture_initialization(*args, **kwargs):
        model = real_build(*args, **kwargs)
        initial_states.append(copy.deepcopy(model.state_dict()))
        initial_rngs.append(torch.get_rng_state().clone())
        return model

    monkeypatch.setattr(search, "build", capture_initialization)
    output = tmp_path / "variants"
    protocol = search.setup(
        output, cache, 2, 4, 71, learning_rates=(0.001, 0.03),
        schedules=("constant", "warmup_cosine"), warmup_epochs=1,
        minimum_lr_factor=0.1, restart_period=2,
    )
    for candidate in candidates:
        _train_candidate(candidate, metadata, protocol, output, 1)
    for state, rng in zip(initial_states[1:], initial_rngs[1:], strict=True):
        _equal_nested(initial_states[0], state)
        _equal_nested(initial_rngs[0], rng)


@pytest.mark.parametrize("changed", (
    {"learning_rates": (0.001, 0.003, 0.01)},
    {"schedules": ("constant",)},
    {"warmup_epochs": 2},
    {"minimum_lr_factor": 0.2},
    {"restart_period": 3},
    {"finalist_epochs": 5},
))
def test_resume_protocol_rejects_lr_schedule_and_horizon_changes(small_cache, tmp_path, changed):
    cache, _ = small_cache
    options = dict(epochs=2, finalist_epochs=4, seed=71, forest_trees=10,
                   learning_rates=RATES, schedules=("constant", "warmup_cosine"),
                   warmup_epochs=1, minimum_lr_factor=0.1, restart_period=2)
    output = tmp_path / "protocol"
    search.setup(output, cache, **options)
    search.setup(output, cache, **options)
    options.update(changed)
    with pytest.raises(ValueError, match="Resume protocol mismatch"):
        search.setup(output, cache, **options)


def test_saved_schedule_horizon_cannot_disagree_with_frozen_finalist_budget(small_cache, tmp_path):
    cache, metadata = small_cache
    output = tmp_path / "bad_horizon"
    protocol = search.setup(output, cache, 2, 4, 71, warmup_epochs=1, restart_period=2)
    candidate = next(candidate for candidate in protocol["candidates"] if candidate["kernel_size"] == 3)
    candidate = copy.deepcopy(candidate)
    candidate["scheduler"]["horizon"] = 5
    with pytest.raises(ValueError, match="horizon|protocol"):
        _train_candidate(candidate, metadata, protocol, output, 1)
