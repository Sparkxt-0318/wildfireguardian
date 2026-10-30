"""A sub-hour source epoch must not leak future state into a weather-hour cutoff."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import rasterio
from rasterio.transform import from_origin


def test_kriged_state_is_derived_at_the_exact_claimed_cutoff(tmp_path):
    root = Path(__file__).resolve().parents[2]
    path = root / "research/forecast-v2/scripts/pipeline.py"
    spec = importlib.util.spec_from_file_location("cutoff_regression_pipeline", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    region = tmp_path / "regions/fixture"
    region.mkdir(parents=True)
    (tmp_path / "events.json").write_text(json.dumps([dict(id="fixture", t0_utc="2022-01-01T02:24:00Z",
        start_utc="2022-01-01T00:00:00Z", end_utc="2022-01-02T00:00:00Z")]))
    for name, values in [("arrival_time_hours.tif", [-1., 10.8, 12.1]), ("kriging_std_hours.tif", [0., 0., 0.])]:
        with rasterio.open(region / name, "w", driver="GTiff", width=3, height=1, count=1,
                           dtype="float32", transform=from_origin(0, 375, 375, 375), crs="EPSG:5070") as writer:
            writer.write(np.asarray(values, dtype=np.float32)[None, :], 1)

    class Environment:
        def at(self, event, hour):
            return np.zeros((2, 1, 3), dtype=np.float32)
        def residence(self, event):
            return None

    samples = module.kriged_samples("fixture", tmp_path, Environment())
    assert len(samples) == 1
    sample = samples[0]
    assert sample.t1 == "2022-01-01T13:00:00+00:00"
    assert abs(sample.meta["start_hours"] - 10.6) < 1e-10
    assert sample.initial.tolist() == [[True, False, False]]
    assert sample.endpoint.tolist() == [[True, True, True]]
