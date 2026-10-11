"""Fast numerical, frozen-preprocessing, and resumable-search checks."""

import copy
import json

import numpy as np
import pytest
import torch

from wildfire.cache import CachedSplit
from wildfire.cache import fit_normalization
from wildfire.cohort import crop_split
from wildfire.models import build_kernel_model
from wildfire.search import Search
build = Search.build
cached_probability = Search.cached_probability
candidate_plan = Search.candidate_plan
fit_candidate = Search.fit_candidate
probabilities = Search.probabilities
setup = Search.setup
tensor_data = Search.tensor_data
verify_protocol = Search.verify_protocol
from wildfire.models import EnvironmentConditionedConvolution
from wildfire.models import center_probability
from wildfire.train import fit_global_rate


FAMILIES = ("legacy", "constant", "linear", "cnn", "mlp", "residual_mlp")


@pytest.fixture(autouse=True)
def _few_threads():
    original = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(original)


def _model(family, size, dropout=0):
    if family == "legacy":
        return EnvironmentConditionedConvolution(2, size, 6)
    return build_kernel_model(2, size, family, hidden_channels=6, depth=3, dropout=dropout)


def _features(environment, family):
    return environment.flatten(1) if family in ("legacy", "cnn") else environment.mean((2, 3))


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("size", (3, 5, 9))
def test_cached_probabilities_and_derivatives_match_public_center(family, size):
    torch.manual_seed(13)
    model = _model(family, size).double().eval()
    cached_model = copy.deepcopy(model)
    environment = torch.randn(7, 2, size, size, dtype=torch.float64)
    burned = torch.randint(0, 2, (7, 1, size, size)).double()
    burned[:, 0, size // 2, size // 2] = 0
    burned[0] = 0
    target = torch.tensor([0, 1, 0, 1, 0, 0, 1], dtype=torch.float64)
    weights = torch.tensor([1, 2, 7, 1, 3, 5, 2], dtype=torch.float64)
    public = center_probability(model, environment, burned)
    cached = cached_probability(cached_model, _features(environment, family), burned.flatten(1))
    torch.testing.assert_close(cached, public, rtol=0, atol=1e-12)
    assert cached[0] == 0
    (weights * (public - target).square()).sum().backward()
    (weights * (cached - target).square()).sum().backward()
    for (name, parameter), (cached_name, cached_parameter) in zip(
        model.named_parameters(), cached_model.named_parameters(), strict=True,
    ):
        assert name == cached_name
        torch.testing.assert_close(parameter.grad, cached_parameter.grad, rtol=1e-11, atol=1e-12)


@pytest.mark.parametrize("family", ("cnn", "mlp", "residual_mlp"))
def test_cached_dropout_has_same_training_values_and_derivatives_for_same_rng(family):
    torch.manual_seed(130)
    model = _model(family, 5, dropout=0.35).double().train()
    cached_model = copy.deepcopy(model)
    environment = torch.randn(19, 2, 5, 5, dtype=torch.float64)
    burned = torch.zeros(19, 1, 5, 5, dtype=torch.float64)
    burned[:, 0, 1, 2] = 1
    state = torch.get_rng_state()
    public = center_probability(model, environment, burned)
    torch.set_rng_state(state)
    cached = cached_probability(cached_model, _features(environment, family), burned.flatten(1))
    torch.testing.assert_close(cached, public, rtol=0, atol=1e-12)
    public.square().sum().backward()
    cached.square().sum().backward()
    for parameter, cached_parameter in zip(model.parameters(), cached_model.parameters(), strict=True):
        torch.testing.assert_close(parameter.grad, cached_parameter.grad, rtol=1e-11, atol=1e-12)


def _data(size=9, count=24, seed=801, event_index=0):
    rng = np.random.default_rng(seed)
    burned = np.zeros((count, 1, size, size), dtype=np.float32)
    burned[:, 0, size // 2 - 1, size // 2] = 1
    burned[::3, 0, size // 2, size // 2 + 1] = 1
    return CachedSplit(
        environment=(rng.normal(size=(count, 2, size, size)) * 3 + 15).astype(np.float32),
        burned=burned,
        target=(np.arange(count) % 3 == 0).astype(np.float32),
        weight=np.where(np.arange(count) % 4, 1, 7).astype(np.float64),
        event_index=np.full(count, event_index, dtype=np.int64),
        time_utc=np.full(count, 3600, dtype=np.int64),
        row=np.arange(count, dtype=np.int64),
        col=np.full(count, 10, dtype=np.int64),
    )


@pytest.mark.parametrize("family", FAMILIES)
def test_tensor_cache_retains_labels_weights_and_saved_normalization(family):
    data = _data(size=5)
    mean, std = np.array([11, 19], np.float32), np.array([2, 4], np.float32)
    common = np.array([1, 5, 9], dtype=np.int64)
    tensors = tensor_data(data, mean, std, family, torch.device("cpu"), common)
    model = _model(family, 5).eval()
    normalized = torch.from_numpy((data.environment - mean[None, :, None, None]) / std[None, :, None, None])
    expected = center_probability(model, normalized, torch.from_numpy(data.burned)).detach().numpy()
    actual = probabilities(model, tensors, batch_size=7)
    np.testing.assert_allclose(actual, expected, rtol=2e-5, atol=2e-6)
    np.testing.assert_array_equal(tensors.target, data.target)
    np.testing.assert_array_equal(tensors.weight, data.weight)
    np.testing.assert_array_equal(tensors.common, common)
    np.testing.assert_array_equal(tensors.loss_weight.numpy(), (data.weight / data.weight.mean()).astype(np.float32))
    np.testing.assert_array_equal(data.burned[:, 0, 2, 2], np.zeros(len(data)))


def _cache(tmp_path):
    directory = tmp_path / "cache"
    directory.mkdir()
    metadata = dict(
        dt_hours=1.0, kernel_size=9, channels=["weather.temperature_2m", "terrain.slope_degrees"],
        event_ids=["train_event", "validation_event", "test_event"],
        splits={"train_event": "train", "validation_event": "validation", "test_event": "test"},
        data_root=str(directory), source_files=[],
    )
    (directory / "metadata.json").write_text(json.dumps(metadata))
    for index, name in enumerate(("train", "validation", "test")):
        data = _data(seed=811 + index, event_index=index)
        np.savez(directory / f"{name}.npz", **vars(data))
    return directory, metadata


def _assert_state_equal(first, second):
    if isinstance(first, torch.Tensor):
        torch.testing.assert_close(first, second, rtol=0, atol=0)
    elif isinstance(first, dict):
        assert first.keys() == second.keys()
        for key in first:
            _assert_state_equal(first[key], second[key])
    elif isinstance(first, (tuple, list)):
        assert len(first) == len(second)
        for a, b in zip(first, second, strict=True):
            _assert_state_equal(a, b)
    else:
        assert first == second


def test_dropout_optimizer_and_rng_resume_equal_uninterrupted_training(tmp_path):
    cache, metadata = _cache(tmp_path)
    device = torch.device("cpu")
    candidate = next(c for c in candidate_plan() if c["kernel_size"] == 3 and c["family"] == "residual_mlp" and c["hidden_channels"] == 32)
    train = crop_split(_data(seed=811), 3)
    validation = crop_split(_data(seed=812, event_index=1), 3)
    mean, std = fit_normalization(train)
    baseline = fit_global_rate(train)
    tensors = tensor_data(train, mean, std, candidate["family"], device)
    validation_tensors = tensor_data(validation, mean, std, candidate["family"], device)
    outputs = [tmp_path / "uninterrupted", tmp_path / "resumed"]
    summaries = []
    for output, budgets in zip(outputs, ((4,), (2, 4)), strict=True):
        protocol = setup(output, cache, 2, 4, 71)
        for epochs in budgets:
            summary = fit_candidate(
                candidate, train, validation, tensors, validation_tensors, mean, std,
                baseline, metadata, protocol, output, device, epochs,
            )
        summaries.append(summary)
    assert summaries[0]["best_epoch"] == summaries[1]["best_epoch"]
    assert summaries[0]["validation_common_brier"] == summaries[1]["validation_common_brier"]
    assert summaries[0]["epochs_completed"] == summaries[1]["epochs_completed"] == 4
    states = [torch.load(path / "candidates" / candidate["id"] / "last.pt", weights_only=True) for path in outputs]
    for key in ("model_state_dict", "optimizer_state_dict", "epoch", "best_validation_brier", "cpu_rng_state"):
        _assert_state_equal(states[0][key], states[1][key])
    histories = [json.loads((path / "candidates" / candidate["id"] / "history.json").read_text()) for path in outputs]
    for first, second in zip(*histories, strict=True):
        for key in first:
            if key != "elapsed_seconds":
                assert first[key] == second[key]


def test_candidate_search_is_prespecified_and_covers_all_unsigned_families():
    plan = candidate_plan()
    assert len(plan) == 40
    assert len({candidate["id"] for candidate in plan}) == 40
    for size in (3, 5, 7, 9):
        candidates = [c for c in plan if c["kernel_size"] == size]
        assert len(candidates) == 10
        assert set(c["family"] for c in candidates) == set(FAMILIES)
        for candidate in candidates:
            model = build(candidate, 2, torch.device("cpu"))
            assert model.kernel_size == size
            assert model.in_channels == 2
        assert {c["hidden_channels"] for c in candidates if c["family"] == "mlp"} == {8, 32, 128}
        assert {c["weight_decay"] for c in candidates if c["family"] == "mlp"} >= {0, 0.0001, 0.01, 0.1}


@pytest.mark.parametrize("name", ("metadata.json", "train.npz", "validation.npz", "test.npz"))
def test_frozen_protocol_rejects_changed_cache_before_resume(tmp_path, name):
    cache, _ = _cache(tmp_path)
    output = tmp_path / "output"
    protocol = setup(output, cache, 2, 4, 71)
    verify_protocol(protocol, cache)
    with (cache / name).open("ab") as stream:
        stream.write(b"changed-input")
    with pytest.raises(ValueError, match="Cache integrity mismatch"):
        setup(output, cache, 2, 4, 71)


def test_frozen_protocol_rejects_source_hash_and_cache_path_drift(tmp_path):
    cache, _ = _cache(tmp_path)
    output = tmp_path / "output"
    protocol = setup(output, cache, 2, 4, 71)
    changed_protocol = copy.deepcopy(protocol)
    changed_protocol["training_source_sha256"]["search.py"] = "0" * 64
    with pytest.raises(ValueError, match="Training source integrity mismatch"):
        verify_protocol(changed_protocol, cache)
    with pytest.raises(ValueError, match="Cache path differs"):
        verify_protocol(protocol, tmp_path / "different-cache")


@pytest.mark.parametrize("field", ("seed", "candidate_epochs", "finalist_epochs", "forest_trees"))
def test_frozen_protocol_rejects_changed_search_budgets(tmp_path, field):
    cache, _ = _cache(tmp_path)
    output = tmp_path / "output"
    setup(output, cache, 2, 4, 71, forest_trees=10)
    options = dict(epochs=2, finalist_epochs=4, seed=71, forest_trees=10)
    argument = {"candidate_epochs": "epochs"}.get(field, field)
    options[argument] += 1
    with pytest.raises(ValueError, match="Resume protocol mismatch"):
        setup(output, cache, **options)
