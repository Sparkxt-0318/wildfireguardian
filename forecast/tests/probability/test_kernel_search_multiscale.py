"""Neural rate-combination math and complete, resumable multiscale searches."""

import copy
import hashlib
import itertools
import json
import math
from pathlib import Path
import shutil

import numpy as np
import pytest
import torch

from wildfire.search import MultiscaleSearch as search
from wildfire.search import MixedSearch as previous
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
    burned[:2] = 0
    burned[0, 0, 0, 0] = 1  # Outer-only contact, invisible to the common 3x3 cohort.
    return CachedSplit(
        environment=(rng.normal(size=(count, 2, 9, 9)) * 2 + 10).astype(np.float32),
        burned=burned, target=(np.arange(count) % 3 == 0).astype(np.float32),
        weight=np.where(np.arange(count) % 4, 1, 7).astype(np.float64),
        event_index=np.full(count, event_index, dtype=np.int64),
        time_utc=np.full(count, 3600, dtype=np.int64), row=np.arange(count, dtype=np.int64),
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


def _candidate(schedule="constant", width=32, horizon=4):
    return next(candidate for candidate in search.candidate_plan(
        learning_rates=(0.03,), schedules=(schedule,), horizon=horizon,
        warmup_epochs=1, minimum_lr_factor=0.1, restart_period=2,
    ) if candidate["family"] == "neural_mixed" and candidate["hidden_channels"] == width)


def _train_candidate(candidate, metadata, protocol, output, epochs):
    device = torch.device("cpu")
    train_base, validation_base = _data(801, 0), _data(802, 1)
    ti, vi = native_indices(train_base, 9), native_indices(validation_base, 9)
    train, validation = crop_split(train_base, 9, ti), crop_split(validation_base, 9, vi)
    mean, std = fit_normalization(train)
    tc = np.flatnonzero(np.isin(ti, common_indices(train_base)))
    vc = np.flatnonzero(np.isin(vi, common_indices(validation_base)))
    tensors = search.tensor_data(train, mean, std, "neural_mixed", device, tc)
    vt = search.tensor_data(validation, mean, std, "neural_mixed", device, vc)
    return search.fit_candidate(candidate, train, validation, tensors, vt, mean, std,
                                fit_global_rate(train), metadata, protocol, output, device, epochs)


def test_default_plan_adds_three_neural_combiners_and_preserves_all_linear_controls():
    plan = search.candidate_plan()
    assert len(plan) == len({candidate["id"] for candidate in plan}) == 368
    assert [candidate for candidate in plan if candidate["family"] != "neural_mixed"] == previous.candidate_plan()
    neural = [candidate for candidate in plan if candidate["family"] == "neural_mixed"]
    assert len(neural) == 24
    assert all(candidate["kernel_size"] == 9 and candidate["kernel_sizes"] == [3, 5, 7, 9] for candidate in neural)
    assert {(candidate["hidden_channels"], candidate["combiner_hidden_channels"], candidate["combiner_dropout"])
            for candidate in neural} == {(16, 8, 0.0), (32, 16, 0.1), (64, 32, 0.15)}
    for base_id in {candidate["base_configuration_id"] for candidate in neural}:
        variants = [candidate for candidate in neural if candidate["base_configuration_id"] == base_id]
        assert {(candidate["learning_rate"], candidate["scheduler"]["name"]) for candidate in variants} == set(
            itertools.product((0.001, 0.003, 0.01, 0.03), ("constant", "warmup_cosine"))
        )


def test_restart_plan_has_552_unique_candidates_and_preserves_linear_controls():
    plan = search.candidate_plan(schedules=SCHEDULES)
    assert len(plan) == len({candidate["id"] for candidate in plan}) == 552
    assert [candidate for candidate in plan if candidate["family"] != "neural_mixed"] == previous.candidate_plan(schedules=SCHEDULES)


def test_neural_native_cohort_is_union_support_and_matched_cohort_stays_three_contact():
    data = _data(801, 0)
    native, common = native_indices(data, 9), common_indices(data)
    assert 0 in native and 0 not in common
    assert 1 not in native and 1 not in common
    selected = crop_split(data, 9, native)
    mean, std = fit_normalization(selected)
    tensors = search.tensor_data(selected, mean, std, "neural_mixed", torch.device("cpu"),
                                 np.flatnonzero(np.isin(native, common)))
    assert tensors.features.shape == (23, 2 * 9 * 9)
    np.testing.assert_array_equal(tensors.common, np.arange(1, 23))


def test_unit_gain_initialization_matches_linear_branches_and_uniform_baseline():
    neural_candidate = _candidate(width=16)
    linear_candidate = next(candidate for candidate in search.candidate_plan(
        learning_rates=(0.03,), schedules=("constant",), horizon=4, warmup_epochs=1,
    ) if candidate["family"] == "mixed" and candidate["hidden_channels"] == 16)
    torch.manual_seed(51)
    neural = search.build(neural_candidate, 2, torch.device("cpu")).double().eval()
    torch.manual_seed(51)
    linear = search.build(linear_candidate, 2, torch.device("cpu")).double().eval()
    assert not hasattr(neural, "mixing_logits")
    with torch.no_grad():
        linear.mixing_logits.fill_(math.log(math.expm1(1.0)))
    search.initialize_neural_mixed_kernel_rate(neural, 0.03)
    search.initialize_mixed_kernel_rate(linear, 0.03)
    for name, parameter in linear.state_dict().items():
        if name.startswith("branches."):
            torch.testing.assert_close(parameter, neural.state_dict()[name], rtol=1e-12, atol=1e-12)
    data = _data(801, 0)
    environment, burned = torch.from_numpy(data.environment).double(), torch.from_numpy(data.burned).double()
    p = search.cached_probability(neural, environment.flatten(1), burned.flatten(1))
    expected = -torch.expm1(-0.03 * burned.sum((1, 2, 3)))
    torch.testing.assert_close(p, expected, rtol=1e-12, atol=1e-12)
    torch.testing.assert_close(p, search.cached_probability(linear, environment.flatten(1), burned.flatten(1)), rtol=1e-12, atol=1e-12)


def test_cached_neural_values_and_all_gradients_match_center_and_full_grid():
    torch.manual_seed(51)
    model = search.build(_candidate(width=16), 2, torch.device("cpu")).double().eval()
    # Exercise a learned, rate-dependent gain rather than only the unit-gain seed.
    with torch.no_grad():
        model.combiner[-1].weight.normal_(std=0.1)
        model.combiner[-1].bias.zero_()
    reference = copy.deepcopy(model)
    data = _data(801, 0)
    environment, burned = torch.from_numpy(data.environment).double() / 10, torch.from_numpy(data.burned).double()
    cached = search.cached_probability(model, environment.flatten(1), burned.flatten(1))
    public = center_probability(reference, environment, burned)
    grid = reference(burned, environment).probability[:, 0, 4, 4]
    torch.testing.assert_close(cached, public, rtol=1e-12, atol=1e-12)
    torch.testing.assert_close(cached, grid, rtol=1e-12, atol=1e-12)
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
    assert torch.count_nonzero(model.combiner[0].weight.grad) > 0


def test_neural_gain_is_not_an_environment_only_linear_kernel():
    model = search.build(_candidate(width=16), 2, torch.device("cpu")).double().eval()
    with torch.no_grad():
        for parameter in model.combiner.parameters():
            parameter.zero_()
        model.combiner[0].weight[0].fill_(1.0)
        model.combiner[-1].weight[0, 0] = 1.0
    rates = torch.full((1, 4), 0.1, dtype=torch.float64)
    assert model.combined_rate(2 * rates).item() > 2 * model.combined_rate(rates).item()
    assert model.combined_rate(torch.zeros_like(rates)).item() == 0
    with pytest.raises(TypeError, match="burned inputs"):
        model.kernel_rates(torch.zeros(1, 2, 9, 9, dtype=torch.float64))


@pytest.mark.parametrize("schedule_name", SCHEDULES)
def test_neural_dropout_adamw_and_rng_resume_equal_four_uninterrupted_epochs(
    small_cache, tmp_path, monkeypatch, schedule_name,
):
    cache, metadata = small_cache
    candidate = _candidate(schedule_name)
    assert candidate["dropout"] > 0 and candidate["combiner_dropout"] > 0
    optimizer_rates = []
    real_step = torch.optim.AdamW.step

    def capture_step(optimizer, *args, **kwargs):
        optimizer_rates.append([group["lr"] for group in optimizer.param_groups])
        return real_step(optimizer, *args, **kwargs)

    monkeypatch.setattr(torch.optim.AdamW, "step", capture_step)
    outputs = (tmp_path / "continuous", tmp_path / "resumed")
    summaries = []
    for output, budgets in zip(outputs, ((4,), (2, 4)), strict=True):
        protocol = search.setup(output, cache, 2, 4, 71, learning_rates=(0.03,), schedules=(schedule_name,),
                                warmup_epochs=1, minimum_lr_factor=0.1, restart_period=2)
        for budget in budgets:
            summary = _train_candidate(candidate, metadata, protocol, output, budget)
        summaries.append(summary)
    expected = [learning_rate_at_step(0.03, step, candidate["scheduler"]) for step in range(1, 5)]
    assert optimizer_rates == [[rate] for rate in expected + expected]
    assert summaries[0]["best_epoch"] == summaries[1]["best_epoch"]
    assert summaries[0]["validation_common_brier"] == summaries[1]["validation_common_brier"]
    assert summaries[0]["combiner_parameters"] == summaries[1]["combiner_parameters"]
    assert summaries[0]["train_sample_count"] == 23 and summaries[0]["validation_common_sample_count"] == 22
    states = [torch.load(output / "candidates" / candidate["id"] / "last.pt", weights_only=True) for output in outputs]
    for key in ("model_state_dict", "optimizer_state_dict", "epoch", "best_validation_brier", "cpu_rng_state", "best_checkpoint"):
        _equal_nested(states[0][key], states[1][key])
    assert all(int(state["step"]) == 4 for state in states[0]["optimizer_state_dict"]["state"].values())
    histories = [json.loads((output / "candidates" / candidate["id"] / "history.json").read_text()) for output in outputs]
    for history in histories:
        assert [record["optimizer_step"] for record in history] == [1, 2, 3, 4]
        assert [record["learning_rate"] for record in history] == expected
        assert all("combiner_parameter_norm" in record and "mixing_weights" not in record for record in history)
    for first, second in zip(*histories, strict=True):
        assert {key: value for key, value in first.items() if key != "elapsed_seconds"} == {
            key: value for key, value in second.items() if key != "elapsed_seconds"
        }


def test_additive_neural_protocol_preserves_frozen_linear_source_hashes(small_cache, tmp_path):
    cache, _ = small_cache
    old = previous.setup(tmp_path / "previous", cache, 2, 4, 71, warmup_epochs=1, restart_period=2)
    new = search.setup(tmp_path / "neural", cache, 2, 4, 71, warmup_epochs=1, restart_period=2)
    previous.verify_protocol(old, cache)
    for name, digest in old["training_source_sha256"].items():
        if name != "search.py":
            assert new["training_source_sha256"][name] == digest
    assert {"search.py", "models.py", "inference.py"} <= new["training_source_sha256"].keys()


@pytest.mark.parametrize("changed", (
    {"learning_rates": (0.001, 0.03)}, {"schedules": ("constant",)}, {"finalist_epochs": 5},
))
def test_neural_resume_rejects_changed_search_protocol(small_cache, tmp_path, changed):
    cache, _ = small_cache
    options = dict(epochs=2, finalist_epochs=4, seed=71, warmup_epochs=1, restart_period=2)
    output = tmp_path / "neural"
    search.setup(output, cache, **options)
    options.update(changed)
    with pytest.raises(ValueError, match="Resume protocol mismatch"):
        search.setup(output, cache, **options)


@pytest.fixture
def environmental_manifest(tmp_path):
    payloads = {
        "biome_classes.json": b'{"classes": [4, 5, 8]}\n',
        "weather/event/weather.bin": b"the exact frozen weather source bytes",
    }
    recorded = tmp_path / "recorded_environmental_data"
    local = tmp_path / "local_environmental_data"
    metadata = {
        "data_root": str(recorded),
        "source_files": [{"path": name, "sha256": hashlib.sha256(payload).hexdigest()}
                         for name, payload in payloads.items()],
        "unrelated_metadata": {"keep": ["this", "unchanged"]},
    }
    return metadata, payloads, recorded, local


def _write_source_copy(root, payloads):
    for name, payload in payloads.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def test_environmental_sources_accepts_complete_local_copy_when_recorded_root_missing(environmental_manifest):
    metadata, payloads, recorded, local = environmental_manifest
    assert not recorded.exists()
    _write_source_copy(local, payloads)
    before = copy.deepcopy(metadata)
    verified_root, checked = search.verify_environmental_sources(metadata, local_root=local)
    assert verified_root == local.resolve()
    assert checked == list(payloads)
    assert metadata == before


def test_environmental_sources_wrong_local_hash_falls_back_to_complete_recorded_copy(environmental_manifest):
    metadata, payloads, recorded, local = environmental_manifest
    _write_source_copy(local, payloads)
    _write_source_copy(recorded, payloads)
    # Local verification gets through the vocabulary before detecting this drift.
    (local / "weather/event/weather.bin").write_bytes(b"different weather bytes")
    before = copy.deepcopy(metadata)
    verified_root, checked = search.verify_environmental_sources(metadata, local_root=local)
    assert verified_root == recorded.resolve()
    assert checked == list(payloads)
    assert metadata == before


def test_environmental_sources_rejects_incomplete_copies_without_combining_or_mutating(environmental_manifest):
    metadata, payloads, recorded, local = environmental_manifest
    # The union contains all expected bytes, but neither root is a complete copy.
    _write_source_copy(local, {"biome_classes.json": payloads["biome_classes.json"]})
    _write_source_copy(recorded, {"weather/event/weather.bin": payloads["weather/event/weather.bin"]})
    before = copy.deepcopy(metadata)
    local_before, recorded_before = _saved_files(local), _saved_files(recorded)
    with pytest.raises(ValueError, match="Source integrity mismatch"):
        search.verify_environmental_sources(metadata, local_root=local)
    assert metadata == before
    assert _saved_files(local) == local_before
    assert _saved_files(recorded) == recorded_before


def _run_args(cache, output, *extra, stage="train", policy="auto"):
    """Small protocol budgets; these tests never fit production models."""
    return search.parser().parse_args([
        stage, "--cache", str(cache), "--output", str(output), "--device", "cpu",
        "--epochs", "2", "--finalist-epochs", "4", "--warmup-epochs", "1",
        "--restart-period", "2", "--learning-rates", "0.01", "0.03",
        "--schedules", "constant", "warmup_cosine", "--forest-trees", "3",
        "--run-policy", policy, *extra,
    ])


def _saved_files(folder):
    return {str(path.relative_to(folder)): path.read_bytes()
            for path in folder.rglob("*") if path.is_file()}


def _assert_config_sibling(base, actual):
    assert actual.parent == base.parent
    assert actual.name.startswith(base.name + "__config_")
    digest = actual.name.removeprefix(base.name + "__config_")
    assert len(digest) == 12 and all(value in "0123456789abcdef" for value in digest)


def test_cli_auto_same_configuration_resumes_without_changing_existing_files(small_cache, tmp_path):
    cache, _ = small_cache
    output = tmp_path / "experiment"
    first = _run_args(cache, output)
    protocol = search.setup_from_args(first)
    (output / "checkpoint_sentinel.pt").write_bytes(b"keep the prior checkpoint")
    saved = _saved_files(output)
    resumed = _run_args(cache, output)
    assert search.setup_from_args(resumed) == protocol
    assert resumed.output == first.output == output
    assert _saved_files(output) == saved
    strict = _run_args(cache, output, policy="resume")
    assert search.setup_from_args(strict) == protocol
    assert strict.output == output
    assert _saved_files(output) == saved


@pytest.mark.parametrize("changed", (
    ("--learning-rates", "0.01", "0.1"),
    ("--schedules", "constant"),
    ("--epochs", "3"),
    ("--finalist-epochs", "5"),
    ("--seed", "11"),
    ("--forest-trees", "7"),
    ("--categorical-balance", "none"),
    ("--device", "mps"),
))
def test_cli_auto_changed_settings_selects_reusable_independent_run(small_cache, tmp_path, monkeypatch, changed):
    cache, _ = small_cache
    output = tmp_path / "experiment"
    if changed == ("--device", "mps"):
        # Only device identity is inspected; no tensors or models are put on MPS.
        monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
    original = search.setup_from_args(_run_args(cache, output))
    (output / "checkpoint_sentinel.pt").write_bytes(b"keep the prior checkpoint")
    saved = _saved_files(output)
    changed_args = _run_args(cache, output, *changed)
    selected = search.setup_from_args(changed_args)
    _assert_config_sibling(output, changed_args.output)
    assert selected != original
    assert _saved_files(output) == saved
    assert (changed_args.output / "protocol.json").is_file()
    repeated = _run_args(cache, output, *changed)
    assert search.setup_from_args(repeated) == selected
    assert repeated.output == changed_args.output
    assert _saved_files(output) == saved


def test_cli_resume_rejects_changed_rates_without_redirecting_or_writing(small_cache, tmp_path):
    cache, _ = small_cache
    output = tmp_path / "experiment"
    search.setup_from_args(_run_args(cache, output))
    saved = _saved_files(tmp_path)
    args = _run_args(cache, output, "--learning-rates", "0.01", "0.1", policy="resume")
    with pytest.raises(ValueError):
        search.setup_from_args(args)
    assert args.output == output
    assert _saved_files(tmp_path) == saved


def test_cli_new_uses_one_fresh_directory_for_every_stage_in_same_invocation(small_cache, tmp_path):
    cache, _ = small_cache
    output = tmp_path / "experiment"
    search.setup_from_args(_run_args(cache, output))
    saved = _saved_files(output)
    first = _run_args(cache, output, stage="run", policy="new")
    protocol = search.setup_from_args(first)
    assert first.output != output and first.output.parent == output.parent
    selected = first.output
    for stage in ("train", "forests", "finalize"):
        first.stage = stage
        assert search.setup_from_args(first) == protocol
        assert first.output == selected
    second = _run_args(cache, output, policy="new")
    search.setup_from_args(second)
    assert second.output not in (output, selected)
    assert second.output.parent == output.parent
    assert _saved_files(output) == saved


def test_cli_auto_changed_cache_path_selects_independent_run(small_cache, tmp_path):
    cache, _ = small_cache
    output = tmp_path / "experiment"
    search.setup_from_args(_run_args(cache, output))
    saved = _saved_files(output)
    other_cache = tmp_path / "other_cache"
    shutil.copytree(cache, other_cache)
    args = _run_args(other_cache, output)
    protocol = search.setup_from_args(args)
    _assert_config_sibling(output, args.output)
    assert protocol["cache"] == str(other_cache.resolve())
    assert _saved_files(output) == saved
    repeated = _run_args(other_cache, output)
    assert search.setup_from_args(repeated) == protocol
    assert repeated.output == args.output


def test_cli_auto_changed_cache_contents_selects_independent_run(small_cache, tmp_path):
    cache, _ = small_cache
    output = tmp_path / "experiment"
    original = search.setup_from_args(_run_args(cache, output))
    saved = _saved_files(output)
    # Harmless JSON whitespace changes the input bytes while retaining a valid cache.
    metadata_path = cache / "metadata.json"
    metadata_path.write_bytes(metadata_path.read_bytes() + b"\n")
    args = _run_args(cache, output)
    selected = search.setup_from_args(args)
    _assert_config_sibling(output, args.output)
    assert selected["cache_sha256"]["metadata.json"] != original["cache_sha256"]["metadata.json"]
    assert _saved_files(output) == saved
    repeated = _run_args(cache, output)
    assert search.setup_from_args(repeated) == selected
    assert repeated.output == args.output


def test_cli_auto_source_drift_selects_independent_run_without_modifying_source(
    small_cache, tmp_path, monkeypatch,
):
    cache, _ = small_cache
    output = tmp_path / "experiment"
    original = search.setup_from_args(_run_args(cache, output))
    saved = _saved_files(output)
    real_sha256 = search.sha256
    changed_hash = "f" * 64

    def changed_source_sha256(path):
        return changed_hash if Path(path).name == "search.py" else real_sha256(path)

    monkeypatch.setattr(search, "sha256", changed_source_sha256)
    args = _run_args(cache, output)
    selected = search.setup_from_args(args)
    _assert_config_sibling(output, args.output)
    assert selected["training_source_sha256"]["search.py"] == changed_hash
    assert selected["training_source_sha256"] != original["training_source_sha256"]
    assert _saved_files(output) == saved
    repeated = _run_args(cache, output)
    assert search.setup_from_args(repeated) == selected
    assert repeated.output == args.output
    strict = _run_args(cache, output, policy="resume")
    with pytest.raises(ValueError):
        search.setup_from_args(strict)
    assert strict.output == output
    assert _saved_files(output) == saved


def test_cli_finalize_resolves_matching_existing_run_before_completion_checks(small_cache, tmp_path):
    cache, _ = small_cache
    output = tmp_path / "experiment"
    search.setup_from_args(_run_args(cache, output))
    changed = _run_args(cache, output, "--learning-rates", "0.01", "0.1")
    search.setup_from_args(changed)
    saved = _saved_files(tmp_path)
    finalize = _run_args(cache, output, "--learning-rates", "0.01", "0.1", stage="finalize")
    with pytest.raises(ValueError):
        search.finalize(finalize)
    assert finalize.output == changed.output
    assert _saved_files(tmp_path) == saved


@pytest.mark.parametrize("existing_base", (False, True))
def test_cli_finalize_missing_run_does_not_create_output_or_protocol(small_cache, tmp_path, existing_base):
    cache, _ = small_cache
    output = tmp_path / "experiment"
    if existing_base:
        search.setup_from_args(_run_args(cache, output))
    saved = _saved_files(tmp_path)
    directories = {str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*") if path.is_dir()}
    args = _run_args(cache, output, "--learning-rates", "0.01", "0.1", stage="finalize")
    with pytest.raises(ValueError):
        search.finalize(args)
    assert _saved_files(tmp_path) == saved
    assert {str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*") if path.is_dir()} == directories


@pytest.mark.parametrize("artifact", ("malformed_protocol", "unbound_checkpoint"))
def test_cli_auto_rejects_malformed_or_unbound_prior_run_without_writing(small_cache, tmp_path, artifact):
    cache, _ = small_cache
    output = tmp_path / "experiment"
    output.mkdir()
    if artifact == "malformed_protocol":
        (output / "protocol.json").write_text("{broken JSON")
    else:
        (output / "checkpoint.pt").write_bytes(b"checkpoint without an experiment protocol")
    saved = _saved_files(tmp_path)
    args = _run_args(cache, output)
    with pytest.raises(ValueError):
        search.setup_from_args(args)
    assert args.output == output
    assert _saved_files(tmp_path) == saved


def test_cli_smoke_reuses_same_sampling_but_separates_seed_and_source_changes(
    small_cache, tmp_path, monkeypatch,
):
    cache, _ = small_cache
    for index, split in enumerate(("train", "validation", "test")):
        count = 640 if split == "train" else 320
        np.savez(cache / f"{split}.npz", **vars(_data(801 + index, index, count=count)))
    # Exercise real smoke sampling and protocol routing, without fitting models.
    monkeypatch.setattr(search, "run_all", search.setup_from_args)
    output = tmp_path / "smoke_experiment"
    first = _run_args(cache, output, stage="smoke")
    search.smoke(first)
    assert first.output == output
    assert first.cache == output / "smoke_cache"
    protocol = json.loads((output / "protocol.json").read_text())
    assert protocol["smoke_verification_only"]
    assert protocol["run_identity"]["mode"] == "smoke"
    assert protocol["run_identity"]["cache"] == str(cache.resolve())
    old_folder = output / "candidates" / "partial_old_candidate"
    old_folder.mkdir(parents=True)
    (old_folder / "last.pt").write_bytes(b"old partial optimizer state")
    saved = _saved_files(output)
    original_indices = {}
    for split, count in (("train", 512), ("validation", 256), ("test", 256)):
        with np.load(first.cache / f"{split}.npz") as data:
            original_indices[split] = data["original_base_index"].copy()
            assert len(data["target"]) == count

    repeated = _run_args(cache, output, stage="smoke")
    search.smoke(repeated)
    assert repeated.output == output and repeated.cache == first.cache
    assert _saved_files(output) == saved

    # A separately invoked stage recovers the original sampling identity from
    # the saved sampled cache rather than treating it as a new full experiment.
    train_stage = _run_args(first.cache, output, "--forest-trees", "9", stage="train")
    assert search.setup_from_args(train_stage) == protocol
    assert train_stage.output == output and train_stage.cache == first.cache
    assert _saved_files(output) == saved

    different_seed = _run_args(cache, output, "--seed", "11", stage="smoke")
    search.smoke(different_seed)
    _assert_config_sibling(output, different_seed.output)
    assert not (different_seed.output / "candidates").exists()
    seed_protocol = json.loads((different_seed.output / "protocol.json").read_text())
    assert seed_protocol["seed"] == 11
    assert seed_protocol["run_identity"]["seed"] == 11
    for split in ("train", "validation", "test"):
        with np.load(different_seed.cache / f"{split}.npz") as data:
            assert not np.array_equal(data["original_base_index"], original_indices[split])
    assert _saved_files(output) == saved
    seed_saved = _saved_files(different_seed.output)

    changed_train = _data(801, 0, count=640)
    changed_train.environment[...] += 100
    np.savez(cache / "train.npz", **vars(changed_train))
    different_source = _run_args(cache, output, stage="smoke")
    search.smoke(different_source)
    _assert_config_sibling(output, different_source.output)
    assert different_source.output != different_seed.output
    assert not (different_source.output / "candidates").exists()
    source_protocol = json.loads((different_source.output / "protocol.json").read_text())
    assert source_protocol["run_identity"]["cache_sha256"]["train.npz"] != protocol["run_identity"]["cache_sha256"]["train.npz"]
    with np.load(different_source.cache / "train.npz") as new, np.load(first.cache / "train.npz") as old:
        np.testing.assert_array_equal(new["original_base_index"], old["original_base_index"])
        np.testing.assert_allclose(new["environment"], old["environment"] + 100, rtol=0, atol=0)
    assert _saved_files(output) == saved
    assert _saved_files(different_seed.output) == seed_saved


def test_complete_46_candidate_search_scores_28_models_and_six_finalists_before_test(
    small_cache, tmp_path, monkeypatch,
):
    cache, _ = small_cache
    output = tmp_path / "full_search"
    args = search.parser().parse_args([
        "run", "--cache", str(cache), "--output", str(output), "--device", "cpu", "--epochs", "1",
        "--finalist-epochs", "2", "--warmup-epochs", "0", "--learning-rates", "0.01",
        "--schedules", "constant", "--forest-trees", "3", "--threads", "1",
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
    assert neural["candidates"] == 46 and neural["long_finalists"] == 6
    search.finalize(args)
    assert loaded_splits.count("test") == 1
    complete = json.loads((output / "complete.json").read_text())
    assert complete["completed"] and complete["evaluated_models"] == 28
    assert not complete["test_used_for_selection"] and all(complete["cache_sha256_verified"].values())
    best_models = json.loads((output / "best_models.json").read_text())
    assert len(best_models) == 28 and {"mixed_k9", "neural_mixed_k9"} <= best_models.keys()
    selected = best_models["neural_mixed_k9"]
    assert "selected_mixing_weights" not in selected and selected["combiner_parameters"] > 0
    payload = np.load(output / "predictions" / "test" / f"{selected['candidate']['id']}.npz")
    assert payload["p"].shape == (24,) and payload["p"][1] == 0
    assert 0 in payload["native_index"] and 0 not in payload["common_index"]
    np.testing.assert_array_equal(payload["common_index"], np.arange(2, 24))
    metrics = json.loads((output / "metrics.json").read_text())
    assert set(metrics) == {"train", "validation", "test"}
    assert all(len(split["models"]) == 28 for split in metrics.values())
    assert (output / "report.md").is_file() and (output / "learning_rate_comparison.csv").is_file()
    with open(selected["checkpoint"], "ab") as handle:
        handle.write(b"integrity test")
    previous_test_reads = loaded_splits.count("test")
    with pytest.raises(ValueError, match="Selected checkpoint integrity mismatch"):
        search.finalize(args)
    assert loaded_splits.count("test") == previous_test_reads
