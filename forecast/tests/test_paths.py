"""Relocated records keep their content binding and local path meaning."""
from pathlib import Path
import hashlib

import pytest

from wildfire import paths


@pytest.mark.parametrize("legacy,new", [
    ("wildfire_burned_area_hourly/environmental_data/events.json", "data/environment/events.json"),
    ("wildfire_burned_area_hourly/probability_model/training_runs/demo/checkpoint.pt", "runs/demo/checkpoint.pt"),
    ("wildfire_burned_area_hourly/regions/demo/toa.tif", "data/regions/demo/toa.tif"),
])
def test_local_recorded_paths_resolve_to_the_relocated_file(tmp_path, monkeypatch, legacy, new):
    monkeypatch.setattr(paths, "WORKSPACE", tmp_path)
    monkeypatch.setattr(paths, "DATA", tmp_path / "data")
    monkeypatch.setattr(paths, "DATA_ROOT", tmp_path / "data/environment")
    monkeypatch.setattr(paths, "RUNS", tmp_path / "runs")
    target = tmp_path / new
    target.parent.mkdir(parents=True)
    target.write_bytes(b"frozen content")
    assert paths.resolve_recorded_path(tmp_path / legacy).read_bytes() == b"frozen content"
    assert paths.resolve_recorded_path(legacy) == target


def test_foreign_and_existing_paths_keep_their_original_meaning(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACE", tmp_path / "workspace")
    foreign = tmp_path / "other/wildfire_burned_area_hourly/environmental_data/events.json"
    assert paths.resolve_recorded_path(foreign) == foreign
    existing = tmp_path / "workspace/wildfire_burned_area_hourly/environmental_data/events.json"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing content")
    assert paths.resolve_recorded_path(existing) == existing


def test_missing_checkout_root_requires_matching_source_hashes_before_using_local_inputs(tmp_path, monkeypatch):
    current = tmp_path / "current/environment"
    current.mkdir(parents=True)
    source = current / "input.bin"
    source.write_bytes(b"frozen input")
    monkeypatch.setattr(paths, "DATA_ROOT", current)
    metadata = {"data_root": str(tmp_path / "previous/environment"), "source_files": [
        {"path": "input.bin", "bytes": source.stat().st_size,
         "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
    ]}
    assert paths.resolve_source_root(metadata) == current
    assert metadata["data_root"] == str(tmp_path / "previous/environment")
    source.write_bytes(b"changed data")
    with pytest.raises(ValueError, match="Source integrity mismatch"):
        paths.resolve_source_root(metadata)


def test_checkpoint_path_recorded_before_relocation_loads_without_changing_record():
    from wildfire.inference import load_trained_model
    from wildfire.heat import AffineGrid, CombustionParameters, WildfireHeatModel
    from wildfire.search import MixedSearch, MultiscaleSearch

    relative = paths.DEFAULT_CHECKPOINT.relative_to(paths.RUNS)
    recorded = paths.WORKSPACE / "wildfire_burned_area_hourly/probability_model/training_runs" / relative
    model = load_trained_model(recorded)
    current = load_trained_model(paths.DEFAULT_CHECKPOINT)
    assert model.contract == current.contract
    assert model.model.kernel_size == current.model.kernel_size
    assert not recorded.exists()
    for loader in (MixedSearch.load_trained_model, MultiscaleSearch.load_trained_model):
        assert loader(recorded).contract == model.contract
    heat = WildfireHeatModel.from_checkpoint(
        recorded, grid=AffineGrid.from_cell_size(10.0),
        combustion=CombustionParameters(1.0, 18e6, 300.0),
        radiative_fraction=0.3, emission_height_m=5.0,
    )
    assert heat.predictor.contract == model.contract
