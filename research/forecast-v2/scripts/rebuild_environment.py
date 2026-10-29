"""Rebuild the six c651 source channels from public sources into an external data root.

The repository holds event metadata only. This script recreates, outside the
git worktree, the subset of the aligned 375 m environmental inputs that the
c651 checkpoint and the track 1B models read:

- weather.temperature_2m, weather.wind_eastward_10m, weather.wind_northward_10m
  (ECMWF IFS 9 km archive through the Open-Meteo archive API, nearest model node)
- terrain.slope_degrees (Copernicus DEM GLO-30 tiles, same 31.25 m method)
- vegetation.tree_cover_percent (Copernicus Global Land Cover 100 m, 2019)
- biome.biome_class (RESOLVE Ecoregions 2017)

It reuses the repository's own acquisition functions in
``forecast/wildfire/environment.py`` by pointing that module's data-root
globals at the external directory; it never edits repository files. The
weather stage is a slimmed copy of ``environment.weather``: it requests only
the three variables c651 needs and omits the 30-day rain history, which no
model here reads. Node selection, unit conversion and raster layout are
unchanged. A rebuilt raster is not guaranteed to be byte-identical to the
original private rasters (public archives can be revised), so every output is
hashed and the comparison against the private inputs is recorded as not run.

Usage (from the worktree root, with the forecast venv):
    python research/forecast-v2/scripts/rebuild_environment.py \
        --root /home/user/wfg-shared/forecast-data/environment_public \
        --zenodo /home/user/wfg-shared/forecast-data/zenodo/extracted
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "forecast"))

from wildfire import environment as env  # noqa: E402

VARIABLES = ["temperature_2m", "wind_speed_10m", "wind_direction_10m"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def configure(root: Path, zenodo: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    env.ROOT = root
    env.BUNDLE = zenodo.parents[1]
    env.ARCHIVE = zenodo
    env.SOURCE = root / "sources/resolve_ecoregions_2017"
    env.LC_LAYERS = {"tree_cover_percent": "Tree-CoverFraction-layer"}


def polite_response(path: Path, url: str, params: dict, *, wait_seconds: int = 300,
                    max_waits: int = 36) -> Path:
    """Cache one original response; wait politely when the service reports a limit.

    The free Open-Meteo tier allows 10,000 weighted calls per day. The whole
    rebuild needs about 7,100 (counted in DATA_PROVENANCE.md). The egress
    address is shared with other users, so the service can report its daily
    limit before this job has used its share. This client never sends
    requests faster than the repository's own pacing and, on a limit reply,
    waits ``wait_seconds`` before one further attempt, at most ``max_waits``
    times per request, then stops with the cached responses preserved.
    """
    path = Path(path)
    if path.exists():
        return path
    for attempt in range(max_waits + 1):
        response = env.SESSION.get(url, params=params, timeout=(30, 240))
        if response.status_code == 200:
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(response.content)
            tmp.replace(path)
            env.jsave(path.with_suffix(path.suffix + ".source.json"),
                      {"url": response.url, "downloaded_utc": pd.Timestamp.now(tz="UTC").isoformat(),
                       "content_type": response.headers.get("Content-Type"), "kind": "original_response"})
            return path
        text = response.text[:200]
        if "limit" in text.lower() and attempt < max_waits:
            print(f"SERVICE LIMIT reply ({text.strip()}); waiting {wait_seconds} s "
                  f"[{attempt + 1}/{max_waits}]", flush=True)
            time.sleep(wait_seconds)
            continue
        if response.status_code >= 500 and attempt < max_waits:
            time.sleep(30)
            continue
        raise RuntimeError(f"Daily public API limit reached or request failed: HTTP {response.status_code} {text}")
    raise RuntimeError("Daily public API limit reached; cached downloads preserved")


def slim_weather(e: dict) -> None:
    """Hourly temperature and wind on the event grid; no rain history."""
    root = env.ROOT
    out = root / "regions" / e["id"] / "weather"
    marker = out / "ecmwf_ifs_complete.json"
    if marker.exists():
        return
    p, _, _ = env.grid(e)
    start, end = pd.Timestamp(e["start_utc"]), pd.Timestamp(e["end_utc"])
    common = dict(models="ecmwf_ifs", timezone="UTC", cell_selection="nearest",
                  wind_speed_unit="ms", temperature_unit="celsius", precipitation_unit="mm")
    raw = root / "raw" / e["id"] / "weather" / "ecmwf_ifs"
    locations = env.o1280_locations(e, p)
    all_times = pd.date_range(start.floor("D"), end.floor("D") + pd.Timedelta(hours=23), freq="h")
    values = {v: np.full((len(all_times), len(locations)), np.nan, "float32") for v in VARIABLES}
    units: dict[str, str] = {}
    covered = np.zeros((len(all_times), len(locations)), dtype=bool)
    dependencies = []
    dates = (all_times[0].strftime("%Y-%m-%d"), all_times[-1].strftime("%Y-%m-%d"))
    batches = [list(range(n, min(n + 12, len(locations)))) for n in range(0, len(locations), 12)]
    for number, js in enumerate(batches):
        chunk = [locations[j] for j in js]
        params = dict(common, latitude=",".join(str(v[0]) for v in chunk),
                      longitude=",".join(str(v[1]) for v in chunk),
                      elevation=",".join(["nan"] * len(chunk)),
                      start_date=dates[0], end_date=dates[1], hourly=",".join(VARIABLES))
        signature = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]
        path = polite_response(raw / f"hourly_slim_{signature}.json",
                               "https://archive-api.open-meteo.com/v1/archive", params)
        data = json.loads(path.read_text())
        items = data if isinstance(data, list) else [data]
        assert len(items) == len(chunk)
        for j, item in enumerate(items):
            actual = (round(item["latitude"], 5), round(item["longitude"], 5))
            assert env.o1280_key(*actual) == env.o1280_key(*chunk[j]), (actual, chunk[j])
            times = pd.to_datetime(item["hourly"]["time"], utc=True)
            idx = all_times.get_indexer(times)
            assert np.all(idx >= 0)
            units.update(item["hourly_units"])
            for v in VARIABLES:
                values[v][idx, js[j]] = np.asarray(item["hourly"][v], dtype="float32")
            locations[js[j]] = (item["latitude"], item["longitude"])
            covered[idx, js[j]] = True
        dependencies.append(str(path.relative_to(root)))
        print(f"WEATHER {e['id']} batch {number + 1}/{len(batches)} ({len(locations)} nodes)", flush=True)
        time.sleep(0.4)
    assert covered.all(), e["id"]
    angle = np.deg2rad(values["wind_direction_10m"])
    values["wind_eastward_10m"] = -values["wind_speed_10m"] * np.sin(angle)
    values["wind_northward_10m"] = -values["wind_speed_10m"] * np.cos(angle)
    units.update(wind_eastward_10m="m/s", wind_northward_10m="m/s")
    out.mkdir(parents=True, exist_ok=True)
    xy = Transformer.from_crs(4326, p["crs"], always_xy=True)
    nx, ny = xy.transform([v[1] for v in locations], [v[0] for v in locations])
    xx, yy = env.event_xy(e)
    dist, indexes = cKDTree(np.c_[nx, ny]).query(np.c_[xx.ravel(), yy.ravel()])
    indexes = indexes.reshape(xx.shape)
    env.write_tif(out / "ecmwf_ifs_node_index_375m.tif", indexes.astype("int32"), p, nodata=-1)
    chosen = (all_times >= start) & (all_times <= end)
    times = all_times[chosen]
    pd.DataFrame({"band": np.arange(1, len(times) + 1),
                  "time_utc": times.strftime("%Y-%m-%dT%H:%M:%SZ")}).to_csv(out / "ecmwf_ifs_bands.csv", index=False)
    availability = {}
    for v in ("temperature_2m", "wind_eastward_10m", "wind_northward_10m"):
        a = values[v][chosen]
        availability[v] = dict(unit=units[v], finite_node_hours=int(np.isfinite(a).sum()),
                               total_node_hours=int(a.size))
        file = out / f"{v}_375m.tif"
        profile = dict(driver="GTiff", width=e["width"], height=e["height"], count=len(times),
                       dtype="float32", crs=p["crs"], transform=p["transform"],
                       nodata=env.environment_NODATA, tiled=True, blockxsize=128, blockysize=128,
                       compress="deflate", predictor=3, interleave="band", BIGTIFF="IF_SAFER")
        tmp = file.with_suffix(".part.tif")
        with rasterio.open(tmp, "w", **profile) as dst:
            dst.update_tags(variable=v, unit=units[v], source_model="ecmwf_ifs",
                            native_resolution_km=9, resampling="nearest returned model-cell centre",
                            time_zone="UTC", spatial_information="coarse source data resampled; not measured at 375m")
            stack = np.where(np.isfinite(a[:, indexes]), a[:, indexes], env.environment_NODATA).astype("float32")
            dst.write(stack)
            for i in range(len(times)):
                dst.set_band_description(i + 1, times[i].strftime("%Y-%m-%dT%H:%M:%SZ"))
        tmp.replace(file)
    env.jsave(marker, dict(model="ecmwf_ifs", native_resolution_km=9, nodes=len(locations),
                           hours=len(times), max_node_distance_m=float(dist.max()),
                           original_response_dependencies=sorted(set(dependencies)),
                           variables=availability, missing_is_nodata=True,
                           rebuild_note="track 1B slim rebuild: three variables, no 30-day rain history"))
    print(f"WEATHER COMPLETE {e['id']} {len(times)} hours", flush=True)


def biome(events: list[dict]) -> None:
    pending = [e for e in events if not (env.ROOT / "regions" / e["id"] / "biome/biome_class_375m.tif").exists()]
    if not pending:
        return
    path = env.acquire_source()
    reader, records, legend = env.read_catalog(path)
    excluded = {r["record_index"] for r in legend["excluded_source_records"]}
    digest = env.sha256(env.SOURCE / "Ecoregions2017.zip")
    try:
        for e in pending:
            env.build_event(e, reader, records, excluded, digest)
    finally:
        reader.close()


def manifest(root: Path, events: list[dict]) -> dict:
    rows = {}
    for e in events:
        region = root / "regions" / e["id"]
        for file in sorted(region.rglob("*_375m.tif")) + sorted(region.rglob("*.json")) + sorted(region.rglob("*.csv")):
            rows[str(file.relative_to(root))] = dict(bytes=file.stat().st_size, sha256=sha256(file))
    for name in ("events.json", "biome_classes.json"):
        if (root / name).exists():
            rows[name] = dict(bytes=(root / name).stat().st_size, sha256=sha256(root / name))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--zenodo", type=Path, required=True)
    parser.add_argument("--events", nargs="*", default=None)
    parser.add_argument("--stages", nargs="*", default=["inventory", "biome", "terrain", "landcover", "weather"])
    args = parser.parse_args()
    configure(args.root.resolve(), args.zenodo.resolve())
    if "inventory" in args.stages and not (env.ROOT / "events.json").exists():
        env.inventory()
    events = json.loads((env.ROOT / "events.json").read_text())
    reference = json.loads((HERE.parents[3] / "forecast/data/environment/events.json").read_text())
    by_id = {e["id"]: e for e in reference}
    for e in events:
        r = by_id[e["id"]]
        for key in ("width", "height", "epsg", "transform", "start_utc", "end_utc", "t0_utc", "valid_arrival_pixels"):
            if e[key] != r[key]:
                raise SystemExit(f"Rebuilt inventory differs from repository events.json: {e['id']} {key}")
    if args.events:
        events = [e for e in events if e["id"] in set(args.events)]
    # Cheapest weather first so a daily API limit still leaves complete small fires.
    events.sort(key=lambda e: e["width"] * e["height"] * (pd.Timestamp(e["end_utc"]) - pd.Timestamp(e["start_utc"])).days)
    if "biome" in args.stages:
        biome(events)
    for e in events:
        if "terrain" in args.stages:
            env.terrain(e)
        if "landcover" in args.stages:
            env.landcover([e])
    if "weather" in args.stages:
        for e in events:
            try:
                slim_weather(e)
            except RuntimeError as error:
                if "Daily public API limit" in str(error):
                    print(f"WEATHER STOPPED at {e['id']}: {error}", flush=True)
                    break
                raise
    files = manifest(env.ROOT, events)
    (env.ROOT / "REBUILD_MANIFEST.json").write_text(json.dumps(dict(
        script_sha256=sha256(HERE), environment_module_sha256=sha256(Path(env.__file__)),
        created_utc=pd.Timestamp.now(tz="UTC").isoformat(), files=files), indent=1) + "\n")
    print(f"REBUILD MANIFEST {len(files)} files", flush=True)


if __name__ == "__main__":
    main()
