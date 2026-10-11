"""Portable search entry points resolve host paths without starting training."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys

import numpy as np
import pytest
import torch


FILES = ("metadata.json", "train.npz", "validation.npz", "test.npz")


@pytest.fixture(autouse=True)
def _one_cpu_thread():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def _wrapper():
    from wildfire_burned_area_hourly.probability_model import kernel_search_portable

    return kernel_search_portable


def _availability(monkeypatch, cuda, mps):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: cuda)
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: mps)


def _stub_relocation(monkeypatch):
    calls = []

    def record(source, destination, data_root):
        calls.append((Path(source), Path(destination), Path(data_root)))
        return {"status": "already_present", "training_started": False, "verified_source_files": 2}

    monkeypatch.setattr(_wrapper(), "relocate_cache", record)
    return calls


def _parse(stage="run", *options):
    return _wrapper().parser().parse_args([stage, *map(str, options)])


def test_defaults_follow_this_project_location_and_keep_original_cache():
    wrapper = _wrapper()
    args = _parse()
    package = Path(wrapper.__file__).resolve().parent
    assert args.data_root == package.parent / "environmental_data"
    assert args.cache == package / "training_runs/20261007_1h_kernel_sweep/9x9/prepared_all"
    assert args.output is None
    assert args.portable_cache is None
    assert args.check_only is False
    assert args.device == "auto"
    assert args.epochs == 512 and args.finalist_epochs == 4096
    assert args.learning_rates == [0.001, 0.003, 0.01, 0.03]
    assert args.schedules == ["constant", "warmup_cosine"]


@pytest.mark.parametrize("cuda,mps,expected", [(True, True, "cuda"), (True, False, "cuda"),
                                                (False, True, "mps"), (False, False, "cpu")])
def test_auto_device_prefers_cuda_then_mps_then_cpu(monkeypatch, cuda, mps, expected):
    wrapper = _wrapper()
    _availability(monkeypatch, cuda, mps)
    calls = _stub_relocation(monkeypatch)
    args = wrapper.prepare_args(_parse())
    assert args.device == expected
    output_root = Path(wrapper.__file__).resolve().parent / "training_runs" / (
        f"20261009_multiscale_kernel_search_{expected}_portable"
    )
    cache_id = sha256(str(args.cache.resolve()).encode()).hexdigest()[:16]
    assert args.output == output_root / cache_id
    assert len(calls) == 1
    assert args.cache == calls[0][1]


@pytest.mark.parametrize("device,cuda,mps", [("cpu", True, True), ("cuda", True, False), ("mps", False, True)])
def test_explicit_available_device_is_respected(monkeypatch, device, cuda, mps):
    _availability(monkeypatch, cuda, mps)
    calls = _stub_relocation(monkeypatch)
    args = _wrapper().prepare_args(_parse("run", "--device", device))
    assert args.device == device
    assert len(calls) == 1


def test_indexed_cuda_keeps_device_selection_and_uses_portable_directory_label(monkeypatch):
    wrapper = _wrapper()
    _availability(monkeypatch, True, False)
    calls = _stub_relocation(monkeypatch)
    dispatched = []

    def train(args):
        dispatched.append(args)

    monkeypatch.setattr(wrapper.search, "train_search", train)
    monkeypatch.setattr(sys, "argv", ["kernel_search_portable", "train", "--device", "cuda:0"])
    wrapper.main()
    assert len(dispatched) == len(calls) == 1
    args = dispatched[0]
    assert args.device == "cuda:0"
    assert args.output.parent.name == "20261009_multiscale_kernel_search_cuda-0_portable"
    assert ":" not in args.output.parent.name
    assert args.output.name == sha256(str(args.cache.resolve()).encode()).hexdigest()[:16]


@pytest.mark.parametrize("device", ["cuda", "mps", "xpu", "not_a_device"])
def test_unavailable_or_invalid_device_fails_before_relocation(monkeypatch, device, tmp_path):
    _availability(monkeypatch, False, False)
    calls = _stub_relocation(monkeypatch)
    destination = tmp_path / "portable_cache"
    output = tmp_path / "run_output"
    with pytest.raises((ValueError, RuntimeError)):
        _wrapper().prepare_args(_parse("run", "--device", device, "--portable-cache", destination,
                                      "--output", output))
    assert not calls
    assert not destination.exists() and not output.exists()


def test_device_validation_precedes_any_relocation_work(monkeypatch):
    wrapper = _wrapper()
    calls = _stub_relocation(monkeypatch)

    def refuse_device(requested):
        assert requested == "cpu"
        raise ValueError("Explicit pre-write device validation")

    monkeypatch.setattr(wrapper, "choose_device", refuse_device)
    with pytest.raises(ValueError, match="pre-write device"):
        wrapper.prepare_args(_parse("run", "--device", "cpu"))
    assert calls == []


def test_automatic_cache_destination_depends_on_resolved_data_root(monkeypatch, tmp_path):
    _availability(monkeypatch, False, False)
    calls = _stub_relocation(monkeypatch)
    source = tmp_path / "original" / "prepared_all"
    data_root = tmp_path / "data" / ".." / "actual_data"
    args = _wrapper().prepare_args(_parse("run", "--cache", source, "--data-root", data_root))
    resolved = data_root.resolve()
    digest = sha256(str(resolved).encode()).hexdigest()[:16]
    expected = source.resolve().parent / "prepared_portable" / digest
    assert args.cache == expected
    assert args.data_root == resolved
    assert calls == [(source.resolve(), expected, resolved)]


def test_default_output_changes_when_portable_cache_location_changes(monkeypatch, tmp_path):
    _availability(monkeypatch, False, False)
    _stub_relocation(monkeypatch)
    first_cache, second_cache = tmp_path / "first_host" / "cache", tmp_path / "second_host" / "cache"
    first = _wrapper().prepare_args(_parse("run", "--portable-cache", first_cache))
    second = _wrapper().prepare_args(_parse("run", "--portable-cache", second_cache))
    assert first.output != second.output
    assert first.output.parent == second.output.parent
    for args in (first, second):
        assert args.output.name == sha256(str(args.cache.resolve()).encode()).hexdigest()[:16]


def test_explicit_paths_are_resolved_and_other_search_options_are_preserved(monkeypatch, tmp_path):
    _availability(monkeypatch, False, False)
    calls = _stub_relocation(monkeypatch)
    source, root = tmp_path / "source", tmp_path / "inputs"
    destination, output = tmp_path / "clone", tmp_path / "cuda_comparison"
    args = _wrapper().prepare_args(_parse(
        "train", "--cache", source, "--data-root", root, "--portable-cache", destination,
        "--output", output, "--device", "cpu", "--epochs", 16, "--finalist-epochs", 64,
        "--learning-rates", 0.003, 0.03, "--schedules", "warmup_cosine_restarts",
        "--warmup-epochs", 4, "--minimum-lr-factor", 0.05, "--restart-period", 8,
        "--seed", 11, "--threads", 2, "--forest-trees", 17,
    ))
    assert calls == [(source.resolve(), destination.resolve(), root.resolve())]
    assert args.cache == destination.resolve() and args.output == output.resolve()
    assert args.stage == "train" and args.device == "cpu"
    assert (args.epochs, args.finalist_epochs, args.seed, args.threads, args.forest_trees) == (16, 64, 11, 2, 17)
    assert args.learning_rates == [0.003, 0.03]
    assert args.schedules == ["warmup_cosine_restarts"]
    assert (args.warmup_epochs, args.minimum_lr_factor, args.restart_period) == (4, 0.05, 8)


@pytest.mark.parametrize("device", ["cpu", "cuda", "mps"])
def test_smoke_default_output_cannot_overlap_full_search_output(monkeypatch, device):
    _availability(monkeypatch, device == "cuda", device == "mps")
    _stub_relocation(monkeypatch)
    full = _wrapper().prepare_args(_parse("run", "--device", device))
    smoke = _wrapper().prepare_args(_parse("smoke", "--device", device))
    assert smoke.output != full.output
    assert smoke.output.parent.name == f"20261009_multiscale_kernel_smoke_{device}_portable"
    assert full.cache == smoke.cache


def test_smoke_preserves_explicit_output(monkeypatch, tmp_path):
    _availability(monkeypatch, False, False)
    _stub_relocation(monkeypatch)
    output = tmp_path / "private_smoke"
    args = _wrapper().prepare_args(_parse("smoke", "--output", output))
    assert args.output == output.resolve()


@pytest.mark.parametrize("stage,handler", [("run", "run_all"), ("smoke", "smoke"),
                                           ("train", "train_search"), ("forests", "forest_search"),
                                           ("finalize", "finalize")])
def test_main_prepares_arguments_then_dispatches_existing_stage(monkeypatch, stage, handler):
    wrapper = _wrapper()
    args = _parse(stage)
    seen = []
    monkeypatch.setattr(sys, "argv", ["kernel_search_portable", stage])

    def prepare(actual):
        assert actual.stage == args.stage
        actual.prepared_marker = True
        seen.append("prepared")
        return actual

    def dispatch(actual):
        assert actual.prepared_marker is True
        seen.append(handler)

    monkeypatch.setattr(wrapper, "prepare_args", prepare)
    monkeypatch.setattr(wrapper.search, handler, dispatch)
    wrapper.main()
    assert seen == ["prepared", handler]


@pytest.mark.parametrize("options", [("--epochs", "0"), ("--finalist-epochs", "128"),
                                      ("--threads", "0")])
def test_main_budget_and_thread_validation_precedes_relocation(monkeypatch, options):
    wrapper = _wrapper()
    called = _stub_relocation(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["kernel_search_portable", "run", *options])
    with pytest.raises(ValueError):
        wrapper.main()
    assert called == []


@pytest.fixture
def portable_fixture(tmp_path):
    source = tmp_path / "original_cache"
    source.mkdir()
    root = tmp_path / "copied_inputs"
    root.mkdir()
    input_file = root / "biome_classes.json"
    input_file.write_bytes(b'{"forest": 1}\n')
    metadata = {
        "dt_hours": 1.0, "kernel_size": 9, "channels": ["fixture.a", "fixture.b"],
        "data_root": "/Users/previous-machine/Wildfire/environmental_data",
        "source_files": [{"path": input_file.name, "sha256": sha256(input_file.read_bytes()).hexdigest()}],
        "event_ids": ["train_event", "validation_event", "test_event"],
        "splits": {f"{split}_event": split for split in ("train", "validation", "test")},
        "split_summary": {split: {"samples": 3} for split in ("train", "validation", "test")},
        "seed": 7,
    }
    (source / "metadata.json").write_text(json.dumps(metadata))
    for i, split in enumerate(("train", "validation", "test")):
        burned = np.ones((3, 1, 9, 9), dtype=np.float32)
        burned[:, 0, 4, 4] = 0
        np.savez(
            source / f"{split}.npz",
            environment=np.ones((3, 2, 9, 9), dtype=np.float32),
            burned=burned,
            target=np.array([1, 0, 1], dtype=np.float32), weight=np.ones(3, dtype=np.float64),
            event_index=np.full(3, i, dtype=np.int64), time_utc=np.full(3, 3600, dtype=np.int64),
            row=np.arange(3, dtype=np.int64), col=np.zeros(3, dtype=np.int64),
        )
    return source, root, metadata


def _forward_fixture_hashes(monkeypatch, source):
    from wildfire_burned_area_hourly.probability_model.relocate_search_cache import relocate_cache

    hashes = {name: sha256((source / name).read_bytes()).hexdigest() for name in FILES}

    def forward(original, destination, root):
        return relocate_cache(original, destination, root, expected_hashes=hashes)

    monkeypatch.setattr(_wrapper(), "relocate_cache", forward)
    return hashes


def test_portable_preparation_is_accepted_by_original_runner_without_training(monkeypatch, portable_fixture, tmp_path):
    wrapper = _wrapper()
    source, root, metadata = portable_fixture
    before = {name: (source / name).read_bytes() for name in FILES}
    hashes = _forward_fixture_hashes(monkeypatch, source)
    _availability(monkeypatch, False, False)
    output = tmp_path / "fresh_cpu_run"
    args = wrapper.prepare_args(_parse("run", "--cache", source, "--data-root", root, "--output", output))
    assert args.device == "cpu" and args.cache != source
    protocol = wrapper.search.setup_from_args(args)
    assert protocol["cache"] == str(args.cache)
    assert protocol["verified_source_files"] == 1
    assert len(protocol["candidates"]) == 368
    assert protocol["cache_sha256"]["metadata.json"] != hashes["metadata.json"]
    assert json.loads((args.cache / "metadata.json").read_text()) == {**metadata, "data_root": str(root.resolve())}
    for name in FILES:
        assert (source / name).read_bytes() == before[name]
        if name != "metadata.json":
            assert protocol["cache_sha256"][name] == hashes[name]
            assert (args.cache / name).read_bytes() == before[name]
    assert wrapper.search.setup_from_args(args) == protocol
    assert not list(output.rglob("*.pt"))


def test_moving_identical_inputs_to_another_root_creates_distinct_portable_cache(monkeypatch, portable_fixture, tmp_path):
    source, first_root, metadata = portable_fixture
    second_root = tmp_path / "second_machine_inputs"
    shutil.copytree(first_root, second_root)
    _forward_fixture_hashes(monkeypatch, source)
    _availability(monkeypatch, False, False)
    first = _wrapper().prepare_args(_parse("run", "--cache", source, "--data-root", first_root))
    second = _wrapper().prepare_args(_parse("run", "--cache", source, "--data-root", second_root))
    assert first.cache != second.cache
    assert first.output != second.output
    assert first.cache.parent == second.cache.parent == source.parent / "prepared_portable"
    for args, root in ((first, first_root), (second, second_root)):
        expected = sha256(str(root.resolve()).encode()).hexdigest()[:16]
        assert args.cache.name == expected
        assert json.loads((args.cache / "metadata.json").read_text()) == {**metadata, "data_root": str(root.resolve())}
        for split in ("train", "validation", "test"):
            assert (args.cache / f"{split}.npz").read_bytes() == (source / f"{split}.npz").read_bytes()


@pytest.mark.parametrize("explicit", [False, True])
def test_lightweight_entry_sets_environment_before_delegating_and_preserves_explicit_values(monkeypatch, explicit):
    import os
    from wildfire_burned_area_hourly import portable_search

    keys = ("PYTORCH_ENABLE_MPS_FALLBACK", "OPENBLAS_NUM_THREADS")
    expected = {keys[0]: "0", keys[1]: "2"} if explicit else dict.fromkeys(keys, "1")
    for key in keys:
        if explicit:
            monkeypatch.setenv(key, expected[key])
        else:
            monkeypatch.delenv(key, raising=False)
    calls = []

    def delegate():
        assert {key: os.environ[key] for key in keys} == expected
        calls.append("delegated")

    monkeypatch.setattr(_wrapper(), "main", delegate)
    portable_search.main()
    assert calls == ["delegated"]


@pytest.mark.parametrize("existing_output", [False, True])
def test_check_only_validates_in_temporary_output_without_dispatching_or_modifying_run(
    monkeypatch, portable_fixture, tmp_path, capsys, existing_output,
):
    wrapper = _wrapper()
    source, root, _ = portable_fixture
    _forward_fixture_hashes(monkeypatch, source)
    _availability(monkeypatch, False, False)
    output = tmp_path / "intended_run"
    if existing_output:
        output.mkdir()
        (output / "protocol.json").write_text('{"existing": "protocol must stay intact"}\n')
        (output / "last.pt").write_bytes(b"Existing checkpoint must stay intact")
    before = {path.name: path.read_bytes() for path in output.iterdir()} if existing_output else None
    trials = []
    real_setup = wrapper.search.setup_from_args

    def track_setup(args):
        assert args.output != output
        trials.append(args.output)
        return real_setup(args)

    def no_training(*args, **kwargs):
        raise AssertionError("Check-only must never dispatch a training/evaluation stage")

    monkeypatch.setattr(wrapper.search, "setup_from_args", track_setup)
    for handler in ("run_all", "smoke", "train_search", "forest_search", "finalize"):
        monkeypatch.setattr(wrapper.search, handler, no_training)
    monkeypatch.setattr(sys, "argv", [
        "kernel_search_portable", "run", "--cache", str(source), "--data-root", str(root),
        "--output", str(output), "--device", "cpu", "--check-only",
    ])
    wrapper.main()
    assert len(trials) == 1
    assert not trials[0].exists() and not trials[0].parent.exists()
    if existing_output:
        assert {path.name: path.read_bytes() for path in output.iterdir()} == before
    else:
        assert not output.exists()
    text = capsys.readouterr().out
    summary = json.loads(text[text.rfind("\n{") + 1:])
    assert summary["status"] == "passed"
    assert summary["candidate_count"] == 368
    assert summary["verified_source_files"] == 1
    assert summary["training_started"] is False
    assert summary["experiment_output_modified"] is False
    assert summary["intended_output"] == str(output.resolve())


def test_complete_portable_run_trains_reports_and_resumes_without_changing_histories(
    monkeypatch, portable_fixture, tmp_path,
):
    wrapper = _wrapper()
    source, root, _ = portable_fixture
    original_bytes = {name: (source / name).read_bytes() for name in FILES}
    _forward_fixture_hashes(monkeypatch, source)
    _availability(monkeypatch, False, False)
    output = tmp_path / "portable_full_smoke"
    argv = [
        "kernel_search_portable", "run", "--cache", str(source), "--data-root", str(root),
        "--output", str(output), "--device", "cpu", "--epochs", "2", "--finalist-epochs", "4",
        "--learning-rates", "0.003", "--schedules", "constant", "--warmup-epochs", "1",
        "--restart-period", "2", "--forest-trees", "3", "--threads", "1",
    ]
    monkeypatch.setattr(sys, "argv", argv)
    wrapper.main()
    neural = json.loads((output / "neural_complete.json").read_text())
    assert neural["candidates"] == 46 and neural["long_finalists"] == 6
    complete = json.loads((output / "complete.json").read_text())
    assert complete["completed"] and complete["evaluated_models"] == 28
    assert not complete["test_used_for_selection"]
    assert all(complete["cache_sha256_verified"].values())
    best = json.loads((output / "best_models.json").read_text())
    assert len(best) == 28 and {"mixed_k9", "neural_mixed_k9"} <= best.keys()
    metrics = json.loads((output / "metrics.json").read_text())
    assert set(metrics) == {"train", "validation", "test"}
    assert all(len(split["models"]) == 28 for split in metrics.values())
    assert (output / "report.md").is_file()
    assert (output / "learning_rate_comparison.csv").is_file()
    histories = {path: path.read_bytes() for path in output.rglob("history.json")}
    assert len(histories) == 46
    assert all(Path(selected["checkpoint"]).is_file() for selected in best.values())
    wrapper.main()
    assert {path: path.read_bytes() for path in output.rglob("history.json")} == histories
    assert {name: (source / name).read_bytes() for name in FILES} == original_bytes
    assert json.loads((output / "complete.json").read_text())["completed"]
