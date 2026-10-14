"""The observed M548 adapter must retain binary Monte Carlo trajectories.

These tests use M548's mixed-kernel architecture with an explicit westward
rate oracle. They never load a saved checkpoint or run a real-data evaluation.
The independent oracle specifies the random-stream contract and simultaneous
binary updates, so a fixed-state analytic shortcut cannot satisfy the tests.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import random

import numpy as np
import pytest
import torch

from tests.test_rollout import _DirectedKernel, _contract, _inputs
from wildfire import WildfireModel
from wildfire.models import MixedNonnegativeKernel, TrainedBurnModel
from wildfire.observed_evaluation import exact_survey_prediction


@pytest.fixture
def mixed_model():
    previous_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    kernel = MixedNonnegativeKernel(2, (3, 5, 7, 9), hidden_channels=2).double()
    total_weight = float(kernel.mixing_weights().sum())
    kernel.branches = torch.nn.ModuleDict({
        str(size): _DirectedKernel(size, fixed_rate=math.log(2) / total_weight).double()
        for size in kernel.kernel_sizes
    })
    contract = _contract(9, "MixedNonnegativeKernel")
    contract["kernel_sizes"] = [3, 5, 7, 9]
    predictor = TrainedBurnModel(kernel, torch.zeros(2, dtype=torch.float64),
        torch.ones(2, dtype=torch.float64), contract, best_epoch=1).double().eval()
    model = WildfireModel(predictor, {"contract": deepcopy(contract)},
        Path("/private/tmp/m548_observed_mc_fixture.pt"), "fixture")
    yield model
    torch.set_num_threads(previous_threads)


def sample(model):
    burned, features = _inputs(leading=(1,))
    return dict(burned_area=burned, features=features, channel_names=model.channel_names,
        burned_area_valid=torch.ones_like(burned, dtype=torch.bool),
        feature_valid=torch.ones_like(features, dtype=torch.bool))


def oracle_states(initial, durations, n_samples, seed, block_size):
    """Independently simulate the specified westward Bernoulli process."""
    retained = []
    for block, start in enumerate(range(0, n_samples, block_size)):
        stream_seed = int(np.random.SeedSequence([seed, 0, block, 0]).generate_state(
            1, dtype=np.uint64)[0])
        rng = torch.Generator(device="cpu").manual_seed(stream_seed)
        state = initial.expand(block_size, -1, -1, -1).bool().clone()
        for duration in durations:
            uniforms = torch.rand(state.shape, dtype=torch.float64, generator=rng)
            west = torch.zeros_like(state)
            west[..., 1:] = state[..., :-1]
            probability = (west & ~state).double() * (-math.expm1(-math.log(2) * duration))
            state = state | (uniforms < probability)
        retained.append(state[:min(block_size, n_samples - start)])
    return torch.cat(retained)


@pytest.mark.parametrize("durations", [[1.0], [1.0, 1.0], [1.0, 1.0, .2]])
def test_observed_m548_exact_counts_follow_binary_monte_carlo_oracle(mixed_model, durations):
    inputs = sample(mixed_model)
    n, seed, block = 37, 92, 16
    hours = sum(durations)
    result = exact_survey_prediction(mixed_model, inputs, hours,
        n_samples=n, seed=seed, trajectory_batch_size=block).at(hours=hours)
    states = oracle_states(inputs["burned_area"], durations, n, seed, block)
    expected_counts = (states & ~inputs["burned_area"].bool()).sum(dim=0, keepdim=True)
    torch.testing.assert_close(result.probability * n, expected_counts.double(), rtol=0, atol=0)
    assert result.valid.all()
    assert not result.probability.requires_grad
    assert result.metadata["method"] == "recursive"
    assert result.metadata["uncertainty_kind"] == "monte_carlo"
    assert result.metadata["n_samples"] == n
    assert result.metadata["seed"] == seed
    assert result.metadata["trajectory_batch_size"] == block
    assert result.metadata["step_durations_hours"] == pytest.approx(durations)


def test_observed_m548_spreads_from_new_ignitions_in_subsequent_hours(mixed_model):
    inputs = sample(mixed_model)
    n = 8192
    first = exact_survey_prediction(mixed_model, inputs, 1., n_samples=n, seed=41,
        trajectory_batch_size=32).at(hours=1)
    second = exact_survey_prediction(mixed_model, inputs, 2., n_samples=n, seed=41,
        trajectory_batch_size=32).at(hours=2)
    assert first.probability[0, 0, 2, 3] == 0
    assert float(second.probability[0, 0, 2, 3]) == pytest.approx(.25,
        abs=6 * math.sqrt(.25 * .75 / n))
    fixed = mixed_model.predict_cumulative(inputs, hours=[2], method="fixed").at(hours=2)
    assert fixed.probability[0, 0, 2, 3] == 0
    assert second.probability[0, 0, 2, 3] > fixed.probability[0, 0, 2, 3]


def test_m548_receives_full_blocks_of_binary_states_under_inference_mode(mixed_model):
    calls = []
    def record(module, args, options):
        states = args[0]
        calls.append((states.clone(), options["dt_hours"], torch.is_inference_mode_enabled()))
        assert torch.all((states == 0) | (states == 1))
    hook = mixed_model.predictor.register_forward_pre_hook(record, with_kwargs=True)
    try:
        exact_survey_prediction(mixed_model, sample(mixed_model), 2.5,
            n_samples=37, seed=7, trajectory_batch_size=16)
    finally:
        hook.remove()
    # Three deterministic coverage calls precede three trajectory blocks.
    # Even the block retaining only five samples must infer all sixteen rows.
    assert len(calls) == 3 + 3*3
    assert [state.shape[0] for state, _, _ in calls[:3]] == [1, 1, 1]
    assert [state.shape[0] for state, _, _ in calls[3:]] == [16]*9
    assert [duration for _, duration, _ in calls] == [1., 1., .5]*4
    assert all(inference for _, _, inference in calls)
    assert any(bool(state[:, 0, 2, 2].any()) for state, _, _ in calls[3:])


def test_observed_mc_reproducibility_and_all_global_random_streams_are_unchanged(mixed_model):
    inputs = sample(mixed_model)
    torch_state = torch.random.get_rng_state().clone()
    numpy_state = deepcopy(np.random.get_state())
    python_state = random.getstate()
    options = dict(n_samples=67, seed=18, trajectory_batch_size=32)
    first = exact_survey_prediction(mixed_model, inputs, 2.5, **options)
    second = exact_survey_prediction(mixed_model, inputs, 2.5, **options)
    torch.testing.assert_close(first.probability, second.probability, rtol=0, atol=0)
    torch.testing.assert_close(torch.random.get_rng_state(), torch_state, rtol=0, atol=0)
    assert random.getstate() == python_state
    after = np.random.get_state()
    assert after[0] == numpy_state[0]
    np.testing.assert_array_equal(after[1], numpy_state[1])
    assert after[2:] == numpy_state[2:]
    changed = exact_survey_prediction(mixed_model, inputs, 2.5,
        **dict(options, seed=19))
    assert not torch.equal(first.probability, changed.probability)


def test_increasing_budget_retains_existing_trajectory_prefix(mixed_model):
    inputs = sample(mixed_model)
    durations, seed, block = [1., 1., .5], 7, 16
    small_n, large_n = 37, 53
    states = oracle_states(inputs["burned_area"], durations, large_n, seed, block)
    small_states = oracle_states(inputs["burned_area"], durations, small_n, seed, block)
    torch.testing.assert_close(states[:small_n], small_states, rtol=0, atol=0)
    predictions = [exact_survey_prediction(mixed_model, inputs, 2.5, n_samples=n,
        seed=seed, trajectory_batch_size=block).at(hours=2.5) for n in (small_n, large_n)]
    added_counts = (states[small_n:] & ~inputs["burned_area"].bool()).sum(dim=0, keepdim=True)
    actual_added = predictions[1].probability * large_n - predictions[0].probability * small_n
    torch.testing.assert_close(actual_added, added_counts.double(), rtol=0, atol=0)


def test_progress_counts_exact_work_and_preserves_seeded_results(mixed_model):
    inputs = sample(mixed_model)
    options = dict(n_samples=37, seed=7, trajectory_batch_size=16)
    expected = exact_survey_prediction(mixed_model, inputs, 2.5, **options).at(hours=2.5)
    global_state = torch.random.get_rng_state().clone()
    work = []
    def progress(completed, total):
        assert torch.is_inference_mode_enabled()
        work.append((completed, total))
    actual = exact_survey_prediction(mixed_model, inputs, 2.5,
        **options, progress_callback=progress).at(hours=2.5)
    # Three time steps, one deterministic coverage pass and three full blocks.
    assert work == [(completed, 12) for completed in range(13)]
    for name in ("probability", "burned_probability", "valid", "rate", "rate_valid",
                 "mc_standard_error", "confidence_lower", "confidence_upper"):
        torch.testing.assert_close(getattr(actual, name), getattr(expected, name),
                                   rtol=0, atol=0, equal_nan=True)
    assert actual.metadata == expected.metadata
    assert torch.equal(torch.random.get_rng_state(), global_state)


def test_cached_rollout_retains_exact_trajectories_and_prepares_each_batch_once(mixed_model, monkeypatch):
    inputs = sample(mixed_model)
    options = dict(n_samples=37, seed=7, trajectory_batch_size=16)
    kernel = mixed_model.predictor.model
    original = kernel._kernels
    batches = []
    def record(clean):
        batches.append(clean.shape[0])
        return original(clean)
    monkeypatch.setattr(kernel, "_kernels", record)
    ordinary = exact_survey_prediction(mixed_model, inputs, 2.5,
        **options, cache_environment_kernels=False).at(hours=2.5)
    assert batches == [1] * 3 + [16] * 9
    batches.clear()
    state = torch.random.get_rng_state().clone()
    cached = exact_survey_prediction(mixed_model, inputs, 2.5,
        **options, cache_environment_kernels=True).at(hours=2.5)
    assert batches == [1, 16]
    for name in ("probability", "burned_probability", "valid", "rate", "rate_valid",
                 "mc_standard_error", "confidence_lower", "confidence_upper"):
        torch.testing.assert_close(getattr(cached, name), getattr(ordinary, name),
                                   rtol=0, atol=0, equal_nan=True)
    assert cached.metadata == ordinary.metadata
    assert torch.equal(torch.random.get_rng_state(), state)


def test_observed_mc_uncertainty_absorption_and_numpy_export(mixed_model):
    inputs = sample(mixed_model)
    n = 127
    result = exact_survey_prediction(mixed_model, inputs, 2., n_samples=n, seed=4,
        trajectory_batch_size=16).at(hours=2)
    p = result.probability
    torch.testing.assert_close(result.mc_standard_error, torch.sqrt(p * (1-p) / n))
    z = 1.95996398454
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n)) / denominator
    half = z/denominator * torch.sqrt(p*(1-p)/n + z*z/(4*n*n))
    initial = inputs["burned_area"].bool()
    expected_lower = torch.where(initial, 0., (center-half).clamp(0, 1))
    expected_upper = torch.where(initial, 0., (center+half).clamp(0, 1))
    torch.testing.assert_close(result.confidence_lower, expected_lower)
    torch.testing.assert_close(result.confidence_upper, expected_upper)
    assert p[initial].eq(0).all()
    assert result.burned_probability[initial].eq(1).all()
    assert result.mc_standard_error[initial].eq(0).all()
    assert torch.isnan(result.rate).all() and not result.rate_valid.any()
    exported = result.numpy()
    assert json.loads(exported["metadata_json"].item())["n_samples"] == n
    exported["probability"].fill(1)
    assert result.probability[initial].eq(0).all()
