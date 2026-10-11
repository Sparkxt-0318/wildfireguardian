"""Full environmental rectangles, arrival footprints, gaps, and explicit tiles.

Source availability is independent of the reconstructed arrival footprint.
Prediction availability can additionally require neighboring/exterior context.
These tests distinguish those three objects using an existing raster bundle.
"""

from copy import deepcopy
import json
import math
from pathlib import Path

from affine import Affine
import numpy as np
import pytest
import rasterio
import torch

from tests.loader.test_dataset import bundle, write
from wildfire import WildfireModel, load_data, select_time
from wildfire.models import (
    TrainedBurnModel,
    build_kernel_model,
    initialize_kernel_rate,
    kernel_model_configuration,
)


CHANNELS = ("weather.temperature_2m", "terrain.elevation_m")


@pytest.fixture(autouse=True)
def _few_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


@pytest.fixture
def rectangular_bundle(bundle):
    """A 5x7 source grid with arrival data confined to an interior 2x2 block."""
    events = json.loads((bundle / "events.json").read_text())
    event = next(value for value in events if value["id"] == "KR_TEST")
    event.update(height=5, width=7)
    (bundle / "events.json").write_text(json.dumps(events))
    transform = Affine(*event["transform"])
    region = bundle / "regions" / event["id"]
    arrival = np.full((5, 7), -9999, dtype=np.float32)
    arrival[2:4, 2:4] = 2
    arrival[2, 2] = -1.5  # One observed seed at the first cutoff (-0.5 h).
    terrain = np.arange(35, dtype=np.float32).reshape(5, 7) + 10
    rows, columns = np.indices((5, 7))
    weather = np.stack([1000 + 100*hour + 10*rows + columns for hour in range(3)]).astype(np.float32)
    write(region / "arrival_time_hours.tif", arrival, transform)
    write(region / "kriging_std_hours.tif", np.ones((5, 7)), transform)
    write(region / "terrain" / "elevation_m_375m.tif", terrain, transform)
    write(region / "weather" / "temperature_2m_375m.tif", weather, transform)
    # Keep the other existing KR layers coherent with the enlarged reference
    # grid, although these regression tests select only the two channels above.
    write(region / "weather" / "soil_moisture_0_to_7cm_375m.tif", np.full((3, 5, 7), 0.2), transform)
    write(region / "vegetation" / "landcover_class_375m.tif", np.full((5, 7), 111), transform)
    write(bundle / "quality_flags" / "KR_TEST" / "soil_moisture_0_to_7cm_quality_flags_375m.tif",
          np.zeros((3, 5, 7)), transform)
    return bundle, event, terrain, weather


def _read(root, **options):
    with load_data(root, events=["KR_TEST"], sequence_length=None, channels=CHANNELS, **options) as dataset:
        assert len(dataset) == 1
        return dataset[0]


def _fitted_model():
    kernel = build_kernel_model(2, 3, "constant", hidden_channels=2, depth=1)
    initialize_kernel_rate(kernel, math.log(2))
    contract = {
        "format_version": 1, "architecture": "LearnedNonnegativeKernel",
        "in_channels": 2, "channels": list(CHANNELS), "kernel_size": 3,
        "kernel_model": kernel_model_configuration(kernel),
        "dt_hours": 1.0, "center_rate": 0.0,
        "eligibility": "at_least_one_burned_neighbor",
    }
    predictor = TrainedBurnModel(kernel, torch.zeros(2), torch.ones(2), contract, best_epoch=1).eval()
    return WildfireModel(predictor, {"contract": deepcopy(contract)},
                         Path("/private/tmp/environment_rectangle_fixture.pt"), "test-checkpoint")


def _recursive(model, sample, boundary):
    return model.predict_cumulative(select_time(sample, index=0), hours=1,
                                    n_samples=32, seed=2, boundary=boundary)


def test_default_loader_preserves_original_rectangle_and_features_outside_arrival_footprint(rectangular_bundle):
    root, event, terrain, weather = rectangular_bundle
    sample = _read(root)
    assert sample["features"].shape == (3, 2, 5, 7)
    assert sample["spatial_window"].tolist() == [0, 0, 5, 7]
    assert sample["pixel_valid"].all()
    assert int(sample["arrival_valid"].sum()) == 4
    assert sample["arrival_valid"][0, 2:4, 2:4].all()
    assert not sample["arrival_valid"][0, 0, 0]
    assert not sample["burned_area_valid"][:, 0, 0, 0].any()
    # Full field equality catches silent footprint masking, cropping, and
    # resampling, including both corners outside the arrival bounding box.
    torch.testing.assert_close(sample["features"][:, 0], torch.from_numpy(weather), rtol=0, atol=0)
    torch.testing.assert_close(sample["features"][:, 1], torch.from_numpy(terrain).expand(3, -1, -1),
                               rtol=0, atol=0)
    assert sample["feature_valid"].all()
    assert sample["feature_quality"].eq(0).all()
    assert torch.isfinite(sample["coordinates"]).all()
    torch.testing.assert_close(sample["affine_transform"], torch.tensor(event["transform"], dtype=torch.float64))
    assert sample["coordinates"][:, 0, 0].tolist() == [1000187.5, 1999812.5]
    assert sample["coordinates"][:, -1, -1].tolist() == [1002437.5, 1998312.5]


def test_probability_boundary_unavailability_does_not_mean_source_features_were_cropped(rectangular_bundle):
    root, _, _, _ = rectangular_bundle
    sample = _read(root)
    model = _fitted_model()
    before_features, before_valid = sample["features"].clone(), sample["feature_valid"].clone()
    unknown = _recursive(model, sample, "unknown")
    zero = _recursive(model, sample, "zero")
    assert zero.valid.all()
    assert zero.metadata["assumed_unburned_cells"] == 31
    assert not unknown.at(hours=1).valid[0, 0, 0, 0]
    assert torch.isnan(unknown.at(hours=1).probability[0, 0, 0, 0])
    assert sample["feature_valid"][0, :, 0, 0].all()
    assert sample["feature_quality"][0, :, 0, 0].eq(0).all()
    # This interior target is outside the arrival footprint but retains all
    # original environmental neighbors and can be simulated under the default
    # explicit missing-burn-as-unburned assumption.
    assert not sample["burned_area_valid"][0, 0, 1, 1]
    assert unknown.at(hours=1).valid[0, 0, 1, 1]
    assert unknown.at(hours=1).valid[0, 0, 2, 2]  # Original seed remains known.
    torch.testing.assert_close(sample["features"], before_features, rtol=0, atol=0)
    torch.testing.assert_close(sample["feature_valid"], before_valid)


def test_genuine_environmental_nodata_remains_a_gap_in_the_full_rectangle(rectangular_bundle):
    root, _, _, _ = rectangular_bundle
    temperature_path = root / "regions" / "KR_TEST" / "weather" / "temperature_2m_375m.tif"
    with rasterio.open(temperature_path, "r+") as source:
        first = source.read(1)
        first[1, 5] = -9999
        source.write(first, 1)
    sample = _read(root)
    assert sample["features"].shape == (3, 2, 5, 7)
    assert not sample["feature_valid"][0, 0, 1, 5]
    assert sample["feature_quality"][0, 0, 1, 5] == 2
    assert sample["feature_valid"][0, 1, 1, 5]  # Terrain at the same cell is retained.
    assert sample["feature_valid"][1:, 0, 1, 5].all()
    assert sample["pixel_valid"][0, 1, 5]  # A source gap is not spatial padding.
    model = _fitted_model()
    zero = _recursive(model, sample, "zero")
    assert not zero.at(hours=1).valid[0, 0, 1, 5]
    assert torch.isnan(zero.at(hours=1).probability[0, 0, 1, 5])
    assert zero.at(hours=1).valid[0, 0, 1, 1]
    assert zero.at(hours=1).valid[0, 0, 0, 0]


def test_explicit_patches_are_exact_windows_and_introduce_only_requested_tile_boundaries(rectangular_bundle):
    root, _, _, _ = rectangular_bundle
    full = _read(root)
    with load_data(root, events=["KR_TEST"], sequence_length=None, channels=CHANNELS,
                   patch_size=(3, 4)) as dataset:
        assert len(dataset) == 4
        tiles = [dataset[index] for index in range(len(dataset))]
    assert [tile["spatial_window"].tolist() for tile in tiles] == [
        [0, 0, 3, 4], [0, 4, 3, 3], [3, 0, 2, 4], [3, 4, 2, 3],
    ]
    for tile in tiles:
        row, column, height, width = tile["spatial_window"].tolist()
        torch.testing.assert_close(tile["features"][:, :, :height, :width],
                                   full["features"][:, :, row:row+height, column:column+width],
                                   rtol=0, atol=0)
        assert tile["feature_valid"][:, :, :height, :width].all()
        torch.testing.assert_close(tile["coordinates"][:, :height, :width],
                                   full["coordinates"][:, row:row+height, column:column+width],
                                   rtol=0, atol=0)
    assert tiles[-1]["feature_quality"][:, :, :, 3].eq(4).all()
    assert not tiles[-1]["pixel_valid"][0, :, 3].any()
    model = _fitted_model()
    full_unknown = _recursive(model, full, "unknown")
    tile_unknown = _recursive(model, tiles[0], "unknown")
    assert full_unknown.at(hours=1).valid[0, 0, 1, 3]
    assert not tile_unknown.at(hours=1).valid[0, 0, 1, 3]
    assert tiles[0]["feature_valid"][0, :, 1, 3].all()
    # An explicit exterior-zero assumption can supply outside-tensor context,
    # but it must not make internal tile padding into known source data.
    padded_zero = _recursive(model, tiles[-1], "zero")
    assert not padded_zero.at(hours=1).valid[0, 0, 0, 3]
    assert not padded_zero.at(hours=1).valid[0, 0, 0, 2]
