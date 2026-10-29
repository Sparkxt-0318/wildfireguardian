"""Extract NIROPS survey polygons for the 29 Zenodo US fires and rasterize cumulative states.

One pass over the verified NIROPS v1 shapefile selects records whose
``Inc Number`` and ``Incident_C`` both match an event (``Incident_C`` equals
the Zenodo event id), as in ``observed_catalog_data.extract_catalog``. Each
fire's cumulative mapped extent at every survey time is rasterized at cell
centres on the event's 375 m Zenodo grid (``survival.survey_states``), which
equals the grid in ``forecast/data/environment/events.json``. The kriging
arrival and SD rasters are copied alongside for the mixed regime.

Outputs (outside git): ``<out>/<event>/{perimeters.geojson, states.npz}`` and
``<out>/PERIMETER_MANIFEST.json`` with SHA-256 of every output.

Usage: python research/forecast-v2/scripts/prepare_perimeters.py \
    --shapefile .../NIROPS_2020_2024_R1_R6.shp --zenodo .../zenodo/extracted --out .../perimeters
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
import shapefile

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[3] / "forecast"))
from wildfire.survival import consecutive_intervals, survey_states  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shapefile", type=Path, required=True)
    parser.add_argument("--zenodo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    events = json.loads((HERE.parents[3] / "forecast/data/environment/events.json").read_text())
    by_id = {e["id"]: e for e in events}
    us = list(csv.DictReader(open(args.zenodo / "results/us_selection_29.csv")))
    wanted = {(row["incident_number"], row["incident"]): row["incident"] for row in us}
    records: dict[str, list] = {row["incident"]: [] for row in us}
    with shapefile.Reader(str(args.shapefile), encoding="utf-8") as reader:
        # First pass: attributes only (memory bounded); second pass per event.
        for index, record in enumerate(reader.iterRecords(fields=["Inc Number", "Incident_C"])):
            key = (str(record["Inc Number"]).strip(), str(record["Incident_C"]).strip())
            if key in wanted:
                records[wanted[key]].append(index)
        args.out.mkdir(parents=True, exist_ok=True)
        manifest = dict(shapefile_sha256=sha256(args.shapefile), created_utc=datetime.now(timezone.utc).isoformat(),
                        script_sha256=sha256(HERE), events={})
        for event, indices in sorted(records.items()):
            items = []
            for index in indices:
                record = reader.record(index)
                stamp = datetime.fromisoformat(str(record["UTC"]).strip())
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                properties = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in record.as_dict().items()}
                properties.update(time_utc=stamp.astimezone(timezone.utc).isoformat(), source_record_id=index)
                items.append(dict(type="Feature", id=index, properties=properties,
                                  geometry=reader.shape(index).__geo_interface__))
            write_event(args, event, items, by_id[event], manifest)
            del items
    (args.out / "PERIMETER_MANIFEST.json").write_text(json.dumps(manifest, indent=1) + "\n")


def write_event(args, event, items, grid, manifest) -> None:
    if True:
        items.sort(key=lambda f: (f["properties"]["time_utc"], f["id"]))
        folder = args.out / event
        folder.mkdir(exist_ok=True)
        geojson = folder / "perimeters.geojson"
        geojson.write_text(json.dumps(dict(type="FeatureCollection", name=event, features=items)) + "\n")
        times, states = survey_states(items, grid)
        arrival_path = args.zenodo / "rasters_us" / f"{event}_pswt_ok_toa.tif"
        with rasterio.open(arrival_path) as src:
            assert src.width == grid["width"] and src.height == grid["height"]
            assert list(src.transform)[:6] == grid["transform"]
            arrival = src.read(1, masked=True).filled(np.nan).astype(np.float32)
            t0 = src.tags()["t0_utc"]
        with rasterio.open(str(arrival_path).replace("_toa.tif", "_std.tif")) as src:
            std = src.read(1, masked=True).filled(np.nan).astype(np.float32)
        np.savez_compressed(folder / "states.npz", times=np.array([t.isoformat() for t in times]),
                            states=states, arrival_hours=arrival, arrival_std_hours=std,
                            arrival_t0_utc=np.array(t0))
        intervals = consecutive_intervals(times, 48.0)
        manifest["events"][event] = dict(
            records=len(items), distinct_times=len(times), intervals_le_48h=len(intervals),
            growth_intervals_le_48h=int(sum(int((states[j] > states[i]).sum()) > 0 for i, j, _ in intervals)),
            final_mapped_cells=int(states[-1].sum()), geojson_sha256=sha256(geojson),
            states_sha256=sha256(folder / "states.npz"))
        print(event, manifest["events"][event], flush=True)


if __name__ == "__main__":
    main()
