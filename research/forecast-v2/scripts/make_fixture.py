"""Write a small SYNTHETIC data root in the layout ``wildfire.data`` reads (FIXTURE only).

Nothing written here is an observation. The fixture exists so that the
track 1B pipeline can be exercised end to end before the real data tree is
attached; every number computed on it is labelled FIXTURE.

Layout inferred from ``forecast/wildfire/data.py`` (``WildfireSequenceDataset``)
and ``observed_evaluation.py``:

    <root>/events.json                       list of event dicts (id, country, t0_utc,
                                             start_utc, end_utc, width, height, epsg,
                                             transform, ...), copied from the repository
    <root>/biome_classes.json                {"classes": [{"code", "name"}, ...]}
    <root>/regions/<id>/grid.json            the event dict
    <root>/regions/<id>/arrival_time_hours.tif, kriging_std_hours.tif   (labels; copied from Zenodo)
    <root>/regions/<id>/weather/ecmwf_ifs_complete.json  {"variables": {name: {...}}, "hours": n}
    <root>/regions/<id>/weather/ecmwf_ifs_bands.csv      band,time_utc (hourly, start..end inclusive)
    <root>/regions/<id>/weather/<variable>_375m.tif      one band per hour, NoData -9999
    <root>/regions/<id>/terrain/slope_degrees_375m.tif
    <root>/regions/<id>/vegetation/tree_cover_percent_375m.tif
    <root>/regions/<id>/biome/biome_class_375m.tif       int16 codes 1..14, NoData -9999

Grids, windows and label rasters are the real ones (from the repository's
events.json and the Zenodo archive); the environmental values are synthetic:
smooth random slope and tree-cover fields and a daily random-walk wind.

Usage: python research/forecast-v2/scripts/make_fixture.py --root DIR --zenodo DIR --events ID [ID ...]
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from affine import Affine
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve()
NODATA = -9999.0


def write(path: Path, data: np.ndarray, event: dict, *, dtype="float32", tags=None, names=None):
    data = np.asarray(data)
    if data.ndim == 2:
        data = data[None]
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = dict(driver="GTiff", width=event["width"], height=event["height"], count=data.shape[0],
                   dtype=dtype, crs=f"EPSG:{event['epsg']}", transform=Affine(*event["transform"]),
                   nodata=NODATA, compress="deflate", tiled=False)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data.astype(dtype))
        if tags:
            dst.update_tags(**{k: str(v) for k, v in tags.items()})
        if names:
            for i, name in enumerate(names, 1):
                dst.set_band_description(i, name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--zenodo", type=Path, required=True)
    parser.add_argument("--events", nargs="+", required=True)
    parser.add_argument("--seed", type=int, default=20261029)
    args = parser.parse_args()
    catalog = {e["id"]: e for e in json.loads((HERE.parents[3] / "forecast/data/environment/events.json").read_text())}
    rng = np.random.default_rng(args.seed)
    root = args.root
    root.mkdir(parents=True, exist_ok=True)
    events = [catalog[i] for i in args.events]
    (root / "events.json").write_text(json.dumps(events, indent=1) + "\n")
    (root / "biome_classes.json").write_text(json.dumps(dict(
        product="FIXTURE legend with RESOLVE biome codes", classes=[dict(code=c, name=f"biome {c}") for c in range(1, 15)],
        fixture=True)) + "\n")
    for e in events:
        region = root / "regions" / e["id"]
        region.mkdir(parents=True, exist_ok=True)
        (region / "grid.json").write_text(json.dumps(e) + "\n")
        folder = "rasters_kr" if e["country"] == "KR" else "rasters_us"
        shutil.copy2(args.zenodo / folder / f"{e['id']}_pswt_ok_toa.tif", region / "arrival_time_hours.tif")
        shutil.copy2(args.zenodo / folder / f"{e['id']}_pswt_ok_std.tif", region / "kriging_std_hours.tif")
        h, w = e["height"], e["width"]
        times = pd.date_range(e["start_utc"], e["end_utc"], freq="h")
        days = max(1, int(np.ceil(len(times) / 24)))
        speed = np.clip(3 + np.cumsum(rng.normal(0, 1, days)), 0.5, 12)
        direction = np.cumsum(rng.normal(0, 0.6, days)) + rng.uniform(0, 2 * np.pi)
        u_day, v_day = speed * np.cos(direction), speed * np.sin(direction)
        hour_day = np.minimum(np.arange(len(times)) // 24, days - 1)
        fields = dict(temperature_2m=20 + 5 * np.sin(2 * np.pi * (times.hour.to_numpy() - 9) / 24),
                      wind_eastward_10m=u_day[hour_day], wind_northward_10m=v_day[hour_day])
        weather = region / "weather"
        for name, series in fields.items():
            stack = np.broadcast_to(np.asarray(series, np.float32)[:, None, None], (len(times), h, w))
            write(weather / f"{name}_375m.tif", stack, e,
                  tags=dict(variable=name, unit="FIXTURE", source_model="ecmwf_ifs", fixture="synthetic"))
        pd.DataFrame({"band": np.arange(1, len(times) + 1),
                      "time_utc": times.strftime("%Y-%m-%dT%H:%M:%SZ")}).to_csv(weather / "ecmwf_ifs_bands.csv", index=False)
        (weather / "ecmwf_ifs_complete.json").write_text(json.dumps(dict(
            model="ecmwf_ifs", hours=len(times), fixture=True,
            variables={k: dict(unit="FIXTURE", finite_node_hours=len(times), total_node_hours=len(times)) for k in fields})) + "\n")
        slope = np.clip(gaussian_filter(rng.normal(0, 1, (h, w)), 4) * 60 + 15, 0, 60)
        trees = np.clip(gaussian_filter(rng.normal(0, 1, (h, w)), 6) * 150 + 50, 0, 100)
        write(region / "terrain" / "slope_degrees_375m.tif", slope, e, tags=dict(unit="degrees", fixture="synthetic"))
        write(region / "vegetation" / "tree_cover_percent_375m.tif", trees, e, tags=dict(unit="percent", fixture="synthetic"))
        biome = np.where(gaussian_filter(rng.normal(0, 1, (h, w)), 8) > 0, 5, 6).astype(np.int16)
        write(region / "biome" / "biome_class_375m.tif", biome, e, dtype="int16",
              tags=dict(unit="categorical biome ID", categorical="true", fixture="synthetic"))
        print("FIXTURE", e["id"], h, w, len(times), "hours", flush=True)
    (root / "FIXTURE.txt").write_text("SYNTHETIC environmental values on real grids; not observations.\n")


if __name__ == "__main__":
    main()
