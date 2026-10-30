"""Runtime identity logging must observe the existing numeric training path."""
from copy import deepcopy
import hashlib
import json

import numpy as np
import pytest
import torch

from wildfire.models import StructuredKernelModel
from wildfire.survival import PerimeterSample, fit_mean_field


def object_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def fixture():
    names = ["weather.wind_eastward_10m", "weather.wind_northward_10m", "weather.temperature_2m"]
    with torch.random.fork_rng():
        torch.manual_seed(5)
        model = StructuredKernelModel(3, 3, 2, 0., channel_names=names)
    samples = []
    for i in range(3):
        initial = np.zeros((7, 7), bool)
        initial[3, 3] = True
        endpoint = initial.copy()
        endpoint[3, 4] = True
        mask = ~initial
        if i == 2:
            mask[:] = False
        samples.append(PerimeterSample(str(i), "2021-01-01T00:00:00Z", 1.,
            np.ones((3, 7, 7), np.float32), initial, endpoint, mask,
            np.ones((7, 7), np.float32), np.zeros((7, 7), np.float32)))
    return model, samples


def test_runtime_logging_preserves_d4_numeric_path_and_records_actual_skips():
    before_threads = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        model, samples = fixture()
        old = deepcopy(model)
        options = dict(epochs=3, seed=4, d4=True, samples_per_step=1,
                       validate_each_epoch=False, log=lambda _: None)
        baseline = fit_mean_field(old, samples, [], **options)
        result = fit_mean_field(model, samples, [], **options,
            runtime_case_id_fn=lambda sample: sample.event_id, runtime_object_sha_fn=object_sha,
            runtime_sample_manifest_sha256="a" * 64)
        for name, value in model.state_dict().items():
            assert torch.equal(value, old.state_dict()[name]), name
        assert result["train_prevalence"] == baseline["train_prevalence"]
        for actual, expected in zip(result["history"], baseline["history"]):
            assert {k: v for k, v in actual.items() if k != "seconds"} == {
                k: v for k, v in expected.items() if k != "seconds"}
        ledger = result["runtime_membership"]
        assert ledger["sample_manifest_sha256"] == "a" * 64
        for i, row in enumerate(ledger["epochs"], 1):
            assert row["epoch"] == i and sorted(row["attempted_case_ids"]) == ["0", "1", "2"]
            assert row["attempted_case_ids_sha256"] == object_sha(row["attempted_case_ids"])
            assert row["skipped_case_ids"] == ["2"] and row["optimizer_steps"] == 2
        assert "runtime_membership" not in baseline
    finally:
        torch.set_num_threads(before_threads)


def test_runtime_logging_refuses_a_partial_identity_contract():
    model, samples = fixture()
    with pytest.raises(ValueError, match="Runtime membership"):
        fit_mean_field(model, samples, [], runtime_case_id_fn=lambda sample: sample.event_id)
