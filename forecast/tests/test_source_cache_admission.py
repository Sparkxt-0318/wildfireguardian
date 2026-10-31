"""Cached covariates must be checked against source-derived values."""
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle
import sys
import numpy as np
import pandas as pd
import pytest
import torch


@pytest.fixture
def pipeline():
    path = Path(__file__).resolve().parents[2] / "research/forecast-v2/scripts/pipeline.py"
    spec = importlib.util.spec_from_file_location("source_cache_fixture", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_cache_without_frozen_sources_is_refused(pipeline, tmp_path):
    root, cache = tmp_path / "environment", tmp_path / "cache"
    root.mkdir(); cache.mkdir()
    (root / "events.json").write_text('[{"id":"fixture"}]')
    np.savez(cache / "fixture_20260101T00.npz", raw=np.full((1, 1, 2), 123456., dtype=np.float32), names=["invented"])
    with pytest.raises(ValueError, match="cache is not source evidence"):
        pipeline.Environment(root, cache)


def test_source_loader_recomputation_rejects_fabricated_cached_values(pipeline, tmp_path, monkeypatch):
    root, cache = tmp_path / "environment", tmp_path / "cache"
    root.mkdir(); cache.mkdir()
    event_file = root / "events.json"
    event_file.write_text('[{"id":"fixture"}]')
    pins = {"environment/events.json": hashlib.sha256(event_file.read_bytes()).hexdigest()}
    environment = pipeline.Environment(root, cache, input_sha256=pins)
    names = environment.names
    np.savez(cache / "fixture_20260101T00.npz", raw=np.full((19, 1, 2), 123456., dtype=np.float32), names=np.array(names))

    class Dataset:
        channel_names = names
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def __len__(self): return 1
        def __getitem__(self, index):
            return dict(features=torch.zeros((1, 19, 1, 2)), feature_valid=torch.ones((1, 19, 1, 2), dtype=torch.bool))
    import wildfire.data
    monkeypatch.setattr(wildfire.data, "load_data", lambda *args, **kwargs: Dataset())
    with pytest.raises(ValueError, match="differ from verified source recomputation"):
        environment.at("fixture", pd.Timestamp("2026-01-01T00:00:00Z"))


def test_sample_cache_cannot_override_a_current_source_builder(pipeline, tmp_path):
    sample = pipeline.PerimeterSample("fixture", "2022-01-01T00:00:00Z", 1., np.zeros((2, 1, 2)),
        np.array([[True, False]]), np.array([[True, False]]), np.array([[False, True]]),
        np.ones((1, 2)), np.zeros((1, 2)))
    fresh = pickle.loads(pickle.dumps(sample))
    fresh.endpoint[0, 1] = True
    path = tmp_path / "samples/fixture.pkl"
    path.parent.mkdir()
    path.write_bytes(pickle.dumps([sample]))
    before = path.read_bytes()
    with pytest.raises(ValueError, match="samples differ from verified source recomputation"):
        pipeline.load_or_build(tmp_path, "fixture", lambda: [fresh])
    assert path.read_bytes() == before
