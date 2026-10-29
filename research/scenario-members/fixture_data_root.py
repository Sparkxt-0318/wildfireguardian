"""FIXTURE generator: a tiny synthetic forecast data root in the exact layout the forecast loader reads, so that export v3
model mode (frozen v2 exporter + rollout with trajectory_callback) runs end to end without the real environmental
rasters. Everything written here is synthetic and is labelled FIXTURE; no number from it describes a real fire.

Layout inferred from forecast/wildfire/data.py (WildfireSequenceDataset._discover, __getitem__, _describe) and the
checkpoint's channel schema (19 channels: weather.temperature_2m, weather.wind_eastward_10m, weather.wind_northward_10m,
terrain.slope_degrees, vegetation.tree_cover_percent, biome.biome_class one-hot over 14 classes):

  <root>/events.json                                   list of events: id, name, country, year, t0_utc, start_utc, end_utc,
                                                       epsg, width, height, transform (affine 6-tuple)
  <root>/biome_classes.json                            {"classes": [{"code": int, "name": str}, ...]}
  <root>/regions/<id>/grid.json                        grid description (hashed by the exporter when present)
  <root>/regions/<id>/arrival_time_hours.tif           float32, hours since t0_utc, NaN where never burned
  <root>/regions/<id>/kriging_std_hours.tif            float32, same support
  <root>/regions/<id>/weather/ecmwf_ifs_complete.json  {"variables": [hourly variable names]}
  <root>/regions/<id>/weather/ecmwf_ifs_bands.csv      columns band (1..T), time_utc (hourly start..end, inclusive)
  <root>/regions/<id>/weather/<variable>_375m.tif      one band per hour
  <root>/regions/<id>/terrain/slope_degrees_375m.tif, vegetation/tree_cover_percent_375m.tif, biome/biome_class_375m.tif
All rasters: EPSG:5179, 375 m, the event grid exactly (the loader rejects any other grid).

  python research/scenario-members/fixture_data_root.py --out /path/fixture_root     (forecast environment: rasterio)
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import Affine

EVENT = {"id": "FIX_01", "name": "Synthetic fixture (not a real fire)", "country": "FIXTURE", "year": 2000,
         "t0_utc": "2000-01-01T00:00:00+00:00", "start_utc": "2000-01-01T00:00:00+00:00", "end_utc": "2000-01-01T08:00:00+00:00",
         "epsg": 5179, "width": 24, "height": 20, "transform": [375.0, 0.0, 1000000.0, 0.0, -375.0, 1907500.0],
         "burned_label": "FIXTURE synthetic arrival field"}


def write(path, arrays, tags=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = np.asarray(arrays, dtype="float32")
    if arrays.ndim == 2:
        arrays = arrays[None]
    with rasterio.open(path, "w", driver="GTiff", width=EVENT["width"], height=EVENT["height"], count=arrays.shape[0],
                       dtype="float32", crs="EPSG:5179", transform=Affine(*EVENT["transform"]), nodata=np.nan) as d:
        d.write(arrays)
        if tags:
            d.update_tags(**tags)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=20261029)
    a = ap.parse_args()
    root = Path(a.out)
    if root.exists():
        raise SystemExit("refusing to overwrite %s" % root)
    rng = np.random.default_rng(a.seed)
    H, W = EVENT["height"], EVENT["width"]
    rr, cc = np.mgrid[0:H, 0:W]
    dist = np.hypot(rr - 10, (cc - 6) * 0.8)                      # fire spreading east from (10, 6)
    toa = 0.3 + 0.55 * dist + rng.uniform(0, 0.2, (H, W))
    toa[dist > 13] = np.nan
    (root / "regions" / EVENT["id"]).mkdir(parents=True)
    (root / "events.json").write_text(json.dumps([EVENT], indent=1) + "\n")
    (root / "biome_classes.json").write_text(json.dumps({"classes": [{"code": k, "name": "fixture biome %d" % k} for k in range(1, 15)]}) + "\n")
    reg = root / "regions" / EVENT["id"]
    (reg / "grid.json").write_text(json.dumps({"fixture": True, "transform": EVENT["transform"], "shape": [H, W], "epsg": 5179}) + "\n")
    write(reg / "arrival_time_hours.tif", toa, {"quantity": "FIXTURE time of arrival, hours since t0_utc"})
    write(reg / "kriging_std_hours.tif", np.where(np.isfinite(toa), 0.3, np.nan))
    times = pd.date_range(EVENT["start_utc"], EVENT["end_utc"], freq="h")
    variables = ["temperature_2m", "wind_eastward_10m", "wind_northward_10m"]
    (reg / "weather").mkdir()
    (reg / "weather" / "ecmwf_ifs_complete.json").write_text(json.dumps({"variables": variables, "fixture": True}) + "\n")
    pd.DataFrame({"band": np.arange(1, len(times) + 1), "time_utc": [t.isoformat() for t in times]}).to_csv(
        reg / "weather" / "ecmwf_ifs_bands.csv", index=False)
    T = len(times)
    write(reg / "weather" / "temperature_2m_375m.tif", np.full((T, H, W), 18.0) + rng.normal(0, 0.5, (T, H, W)), {"unit": "degC"})
    write(reg / "weather" / "wind_eastward_10m_375m.tif", np.full((T, H, W), 6.0), {"unit": "m/s"})
    write(reg / "weather" / "wind_northward_10m_375m.tif", np.full((T, H, W), 0.5), {"unit": "m/s"})
    write(reg / "terrain" / "slope_degrees_375m.tif", np.clip(rng.normal(12, 4, (H, W)), 0, 45), {"unit": "degrees"})
    write(reg / "vegetation" / "tree_cover_percent_375m.tif", np.clip(rng.normal(65, 10, (H, W)), 0, 100), {"unit": "percent"})
    write(reg / "biome" / "biome_class_375m.tif", np.full((H, W), 4.0))
    print(json.dumps({"fixture_root": str(root), "event": EVENT["id"], "hours": T, "burning_cells": int(np.isfinite(toa).sum())}))


if __name__ == "__main__":
    main()
