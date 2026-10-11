"""Bundle operations for the wildfire workspace."""
from __future__ import annotations



# Build bundle
# Build hourly estimates from downloaded, checksum-verified arrival rasters.
# 
# Run with the workspace's existing .venv/bin/python. This script never runs the
# code distributed by the data provider and never writes to the legacy folder.


import csv
import hashlib
import json
import math
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window, from_bounds
from rasterio.warp import transform, transform_bounds


from .paths import DATA as build_ROOT
WORKSPACE = build_ROOT.parent
LEGACY = WORKSPACE / "legacy/wildfire_prediction"
EXPANSION = LEGACY / "records/generalization_fix_20261006/data_expansion"
DEPOSIT = build_ROOT / "sources/zenodo_21788344/extracted"
KST = timezone(timedelta(hours=9))
EVENT_IDS = {
    "yeongdeok_2025": "KFS_01",
    "uiseong_andong_2025": "KFS_01",
    "uljin_samcheok_2022": "KFS_02",
    "miryang_2022": "KFS_11",
    "hongseong_2023": "KFS_05",
}


def build_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def utc(text: str) -> datetime:
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    # The publisher's field name and documentation explicitly specify UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def copy_legacy() -> list[dict]:
    pairs = [
        (LEGACY / "data/environment", build_ROOT / "legacy_data/environment"),
        (LEGACY / "data/modis", build_ROOT / "legacy_data/modis"),
        (LEGACY / "raw/jaxa", build_ROOT / "legacy_data/himawari/original_events"),
        (EXPANSION / "raw", build_ROOT / "legacy_data/expanded_events/raw"),
        (EXPANSION / "regions", build_ROOT / "legacy_data/expanded_events/regions"),
        (EXPANSION / "regions.json", build_ROOT / "legacy_data/expanded_events/regions.json"),
        (EXPANSION / "source_environment/regions.json", build_ROOT / "legacy_data/expanded_events/source_environment_regions.json"),
        (LEGACY / "experiments/native_support/prepared/manifest.json", build_ROOT / "legacy_data/metadata/native_support_prepared_manifest.json"),
        (EXPANSION / "prepared/manifest.json", build_ROOT / "legacy_data/metadata/expanded_prepared_manifest.json"),
    ]
    records = []
    for source, destination in pairs:
        if source.is_dir():
            files = sorted(p for p in source.rglob("*") if p.is_file() and p.name != ".DS_Store")
        else:
            files = [source]
        for original in files:
            target = destination / original.relative_to(source) if source.is_dir() else destination
            target.parent.mkdir(parents=True, exist_ok=True)
            source_hash = build_sha256(original)
            if not target.exists() or build_sha256(target) != source_hash:
                shutil.copy2(original, target)
            assert build_sha256(target) == source_hash, str(target)
            records.append({"source": str(original.relative_to(WORKSPACE)), "copy": str(target.relative_to(build_ROOT)),
                            "bytes": target.stat().st_size, "sha256": source_hash})
    build_write_json(build_ROOT / "records/legacy_copy_manifest.json", {"files": records,
        "file_count": len(records), "total_bytes": sum(x["bytes"] for x in records),
        "policy": "Real byte-identical copies of raw and environmental data; no model checkpoints or large prepared model-input tensors."})
    return records


def region_grid(region: dict, event_id: str):
    source = DEPOSIT / f"rasters_kr/{event_id}_pswt_ok_toa.tif"
    uncertainty = DEPOSIT / f"rasters_kr/{event_id}_pswt_ok_std.tif"
    with rasterio.open(source) as ds, rasterio.open(uncertainty) as sd:
        assert ds.crs.to_epsg() == 5179 and ds.res == (375.0, 375.0)
        assert ds.transform == sd.transform and ds.shape == sd.shape
        bounds = transform_bounds("EPSG:4326", ds.crs, *region["bbox"], densify_pts=41)
        raw_window = from_bounds(*bounds, transform=ds.transform)
        c0, r0 = math.floor(raw_window.col_off), math.floor(raw_window.row_off)
        c1 = math.ceil(raw_window.col_off + raw_window.width)
        r1 = math.ceil(raw_window.row_off + raw_window.height)
        window = Window(c0, r0, c1-c0, r1-r0)
        affine = ds.window_transform(window)
        toa = ds.read(1, window=window, boundless=True, fill_value=np.nan)
        std = sd.read(1, window=window, boundless=True, fill_value=np.nan)
        rows, cols = np.indices(toa.shape)
        xs, ys = rasterio.transform.xy(affine, rows.ravel(), cols.ravel())
        lon, lat = transform(ds.crs, "EPSG:4326", xs, ys)
        lon = np.asarray(lon).reshape(toa.shape)
        lat = np.asarray(lat).reshape(toa.shape)
        w, s, e, n = region["bbox"]
        inside_bbox = (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
        valid = inside_bbox & np.isfinite(toa) & np.isfinite(std)
        toa[~valid] = np.nan
        std[~valid] = np.nan
        assert valid.any() and np.all(std[valid] >= 0)
        tags = ds.tags()
        profile = {"driver": "GTiff", "height": toa.shape[0], "width": toa.shape[1],
                   "crs": ds.crs, "transform": affine, "compress": "deflate"}
        full_event_cells = int(np.isfinite(ds.read(1)).sum())
    return toa, std, valid, profile, tags, full_event_cells


def build_region(region: dict, events: dict) -> dict:
    region_id = region["region_id"]
    event_id = EVENT_IDS[region_id]
    event = events[event_id]
    toa, std, valid, profile, source_tags, full_event_cells = region_grid(region, event_id)
    t0 = utc(source_tags["t0_utc"])
    assert t0 == utc(event["t0_utc"])
    start = utc(region["fire_search_start_date"])
    stop = utc(region["fire_search_end_date"]) + timedelta(days=1)
    intervals = int((stop - start).total_seconds() / 3600)
    # Include a terminal snapshot, so every legacy study hour has two boundaries.
    times = [start + timedelta(hours=i) for i in range(intervals + 1)]
    directory = build_ROOT / f"regions/{region_id}"
    directory.mkdir(parents=True, exist_ok=True)
    common_tags = {"event_id": event_id, "region_id": region_id, "t0_utc": stamp(t0),
        "source_doi": "10.5281/zenodo.21788344", "data_kind": "retrospective_reconstruction_estimate",
        "source_native_resolution_m": "375", "independently_validated_in_korea": "false",
        "timing_accuracy_is_not_one_hour": "true", "missingness": "Outside source reconstruction mask or study bbox is NoData, not unburned."}
    for name, data, quantity in [("arrival_time_hours.tif", toa, "Estimated hours since t0_utc"),
                                  ("kriging_std_hours.tif", std, "Model kriging standard deviation, hours; not calibrated confidence interval")]:
        with rasterio.open(directory / name, "w", **profile, count=1, dtype="float32", nodata=np.nan) as out:
            out.write(data.astype("float32"), 1)
            out.update_tags(**common_tags, quantity=quantity)
    with rasterio.open(directory / "reconstruction_mask.tif", "w", **profile, count=1, dtype="uint8", nodata=255) as out:
        out.write(np.where(valid, 1, 255).astype("uint8"), 1)
        out.update_tags(**common_tags, quantity="1: source reconstruction exists; 255: unavailable")
    path = directory / "estimated_burned_area_hourly.tif"
    table = []
    previous = np.zeros(toa.shape, dtype=bool)
    pixel_area_ha = abs(profile["transform"].a * profile["transform"].e) / 10000
    with rasterio.open(path, "w", **profile, count=len(times), dtype="uint8", nodata=255) as out:
        out.update_tags(**common_tags, interval_hours="1", time_basis="UTC whole hours",
            quantity="Cumulative estimated burned support by snapshot UTC time",
            values="1: estimated arrival <= time; 0: estimated arrival > time inside final reconstruction mask; 255: unavailable",
            window_start_utc=stamp(start), window_end_exclusive_utc=stamp(stop),
            includes_terminal_boundary="true")
        for band, at in enumerate(times, start=1):
            elapsed = (at-t0).total_seconds()/3600
            burned = valid & (toa.astype("float64") <= elapsed)
            assert not np.any(previous & ~burned)
            count = int(burned.sum())
            new_count = int((burned & ~previous).sum()) if band > 1 else None
            out.write(np.where(valid, burned.astype("uint8"), 255).astype("uint8"), band)
            out.set_band_description(band, stamp(at))
            out.update_tags(band, timestamp_utc=stamp(at), timestamp_kst=at.astimezone(KST).isoformat(),
                            elapsed_since_source_t0_hours=str(elapsed))
            table.append({"band": band, "timestamp_utc": stamp(at), "timestamp_kst": at.astimezone(KST).isoformat(),
                "terminal_boundary": band == len(times), "valid_reconstruction_cells": int(valid.sum()),
                "estimated_burned_cells": count, "estimated_burned_grid_area_ha": count*pixel_area_ha,
                "estimated_new_burned_cells_since_previous_snapshot": new_count,
                "estimated_new_burned_grid_area_ha_since_previous_snapshot": None if new_count is None else new_count*pixel_area_ha})
            previous = burned
    with (directory / "hourly_area.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    metadata = {"region_id": region_id, "event_id": event_id, "source_event_locality": event["locality"],
        "event_group": region.get("event_group"), "bbox_wgs84": region["bbox"], "bbox_rule": "Pixel center within WGS84 bbox; native source cells copied without spatial interpolation.",
        "t0_utc": stamp(t0), "time_origin_priority": "Downloaded GeoTIFF tag, independently cross-checked against deposit kr_events_21.csv.",
        "window_start_utc": stamp(start), "window_end_exclusive_utc": stamp(stop),
        "interval_hours": 1, "hour_intervals": intervals, "snapshot_count": len(times), "includes_terminal_boundary": True,
        "grid_crs": "EPSG:5179", "grid_resolution_m": 375, "shape": list(toa.shape),
        "valid_reconstruction_cells": int(valid.sum()), "source_full_event_valid_cells": full_event_cells,
        "estimated_arrival_range_hours_since_t0": [float(toa[valid].min()), float(toa[valid].max())],
        "kriging_std_range_hours": [float(std[valid].min()), float(std[valid].max())],
        "source_block_cv_r": float(event["blockcv_r"]), "source_block_cv_MAE_hours": float(event["MAE_h"]),
        "source_reported_final_forest_area_ha": float(event["final_area_ha"]),
        "source_full_event_grid_support_area_ha": full_event_cells*pixel_area_ha,
        "study_bbox_final_grid_support_area_ha": int(valid.sum())*pixel_area_ha,
        "area_interpretation": "Count of 375 m projected grid supports times pixel area. Not an authoritative forest-damage area or exact vector perimeter area.",
        "classification": "Hourly estimates derived from published continuous arrival-time reconstruction, not hourly observations.",
        "limitations": ["Korean timing has no independent aerial/field validation.",
            "Source final perimeter and full event history are retrospective inputs; the estimates are not cutoff-safe forecast inputs.",
            "Kriging standard deviation is not a calibrated interval for the true arrival time.",
            "The raster mask does not establish absence of burning outside it.",
            "Uljin source event is KFS_02; full independent Samcheok administrative coverage is not established.",
            "2025 Yeongdeok uses KFS_01 Gyeongbuk complex, not the different KFS_12 Yeongdeok fire of February 2022.",
            "Administrative forest-damage areas differ from valid raster support areas; no rescaling was applied."]}
    build_write_json(directory / "metadata.json", metadata)
    return metadata


def validate_region(metadata: dict) -> dict:
    directory = build_ROOT / "regions" / metadata["region_id"]
    with rasterio.open(directory / "arrival_time_hours.tif") as arrival, rasterio.open(directory / "estimated_burned_area_hourly.tif") as hourly:
        toa = arrival.read(1, masked=True)
        valid = ~np.ma.getmaskarray(toa)
        assert hourly.count == metadata["snapshot_count"]
        assert hourly.res == (375.0, 375.0) and hourly.crs.to_epsg() == 5179
        assert hourly.transform == arrival.transform
        origin = utc(metadata["t0_utc"])
        prev_time = None
        previous_burned = np.zeros(toa.shape, dtype=bool)
        for band in range(1, hourly.count+1):
            at = utc(hourly.tags(band)["timestamp_utc"])
            if prev_time is not None:
                assert (at-prev_time).total_seconds() == 3600
            actual = hourly.read(band)
            assert np.array_equal(actual == 255, ~valid)
            threshold = (at-origin).total_seconds()/3600
            expected = valid & (np.asarray(toa.data, dtype="float64") <= threshold)
            assert np.array_equal(actual == 1, expected)
            assert not np.any(previous_burned & ~expected)
            previous_burned, prev_time = expected, at
    return {"region_id": metadata["region_id"], "status": "passed", "validated_hourly_bands": hourly.count,
            "checks": ["375 m native grid", "3600-second consecutive timestamps", "band thresholds reproduce downloaded arrival values", "source NoData preserved", "monotonic cumulative burned mask"]}


def build_main() -> None:
    copies = copy_legacy()
    region_specs = json.loads((build_ROOT / "legacy_data/environment/regions.json").read_text())["regions"]
    region_specs += json.loads((build_ROOT / "legacy_data/expanded_events/regions.json").read_text())["regions"]
    with (DEPOSIT / "results/kr_events_21.csv").open(newline="") as stream:
        events = {row["id"]: row for row in csv.DictReader(stream)}
    results = [build_region(r, events) for r in region_specs]
    validation = [validate_region(r) for r in results]
    catalog = [{k: r[k] for k in ["region_id", "event_id", "window_start_utc", "window_end_exclusive_utc", "grid_resolution_m", "hour_intervals", "snapshot_count", "valid_reconstruction_cells", "source_block_cv_MAE_hours"]} for r in results]
    with (build_ROOT / "catalog.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(catalog[0]))
        writer.writeheader()
        writer.writerows(catalog)
    build_write_json(build_ROOT / "records/validation_summary.json", {"status": "passed", "regions": validation,
        "legacy_files_verified": len(copies), "legacy_bytes_verified": sum(r["bytes"] for r in copies),
        "total_hour_intervals": sum(r["hour_intervals"] for r in results),
        "total_hourly_snapshots": sum(r["snapshot_count"] for r in results),
        "scientific_validation": "Technical integrity only; does not establish one-hour timing accuracy or independently observed burned extent."})
    print(json.dumps({"regions": len(results), "snapshots": sum(r["snapshot_count"] for r in results),
                      "legacy_files_verified": len(copies), "validation": "passed"}, indent=2))




# Convert to bitmaps
# Export downloaded and regional rasters to BMP with exact coordinates.
# 
# The images retain the source grid. World files, WKT/PAM sidecars, coordinate
# arrays, and exact floating-point arrays store information BMP cannot embed.
# Every output is reopened and verified before the conversion succeeds.


import argparse

from PIL import Image
from rasterio.warp import transform as project

from .paths import DATA as bitmaps_ROOT
CATEGORIES = {
    0: {"rgb": [230, 235, 240], "meaning": "Estimated arrival after snapshot, inside reconstruction mask"},
    1: {"rgb": [224, 55, 41], "meaning": "Estimated burned by snapshot, or valid reconstruction mask cell"},
    255: {"rgb": [35, 45, 60], "meaning": "NoData / unavailable"},
}


def bitmaps_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return digest.hexdigest()


def bitmaps_write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def number(value):
    return None if value is None else float(value) if np.isfinite(value) else str(value)


def palette(categorical):
    if categorical:
        colors = np.full((256, 3), [255, 0, 255], dtype=np.uint8)
        for index, entry in CATEGORIES.items():
            colors[index] = entry["rgb"]
    else:
        anchors = np.asarray([[55, 35, 100], [45, 95, 140], [25, 155, 135], [145, 200, 70], [250, 230, 50]])
        levels = np.linspace(0, 4, 255)
        colors = np.column_stack([np.interp(levels, np.arange(5), anchors[:, j]) for j in range(3)])
        colors = np.vstack([np.rint(colors), [35, 45, 60]]).astype(np.uint8)
    return colors.ravel().tolist()


def grid_export(ds, output, cache):
    definition = {"width": ds.width, "height": ds.height, "crs_wkt": ds.crs.to_wkt(),
        "crs_authority": ds.crs.to_string(), "affine_a_b_c_d_e_f": list(ds.transform)[:6],
        "pixel_center_formula": "x=a*(column+0.5)+b*(row+0.5)+c; y=d*(column+0.5)+e*(row+0.5)+f",
        "array_order": "[row, column]; row zero is the top of the source image"}
    token = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()[:20]
    if token in cache:
        return cache[token]
    directory = output / "grids"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{token}.coordinates.npz"
    row, col = np.indices(ds.shape, dtype=np.float64)
    a = ds.transform
    x = a.a*(col+0.5) + a.b*(row+0.5) + a.c
    y = a.d*(col+0.5) + a.e*(row+0.5) + a.f
    lon, lat = project(ds.crs, "EPSG:4326", x.ravel(), y.ravel())
    longitude = np.asarray(lon, dtype=np.float64).reshape(ds.shape)
    latitude = np.asarray(lat, dtype=np.float64).reshape(ds.shape)
    np.savez_compressed(path, x=x, y=y, longitude=longitude, latitude=latitude,
                        affine=np.asarray(list(a)[:6]), crs_wkt=np.asarray(ds.crs.to_wkt()))
    with np.load(path, allow_pickle=False) as saved:
        assert np.array_equal(saved["x"], x) and np.array_equal(saved["y"], y)
        back_x, back_y = project("EPSG:4326", ds.crs, saved["longitude"].ravel(), saved["latitude"].ravel())
        error = float(max(np.max(np.abs(np.asarray(back_x)-x.ravel())), np.max(np.abs(np.asarray(back_y)-y.ravel()))))
        assert error < 0.001, (path, error)
    result = {**definition, "coordinate_file": str(path.relative_to(output)), "coordinate_sha256": bitmaps_sha256(path),
        "coordinate_keys": ["x", "y", "longitude", "latitude"], "projected_units": "metres",
        "longitude_latitude_crs": "EPSG:4326", "longitude_latitude_units": "degrees",
        "coordinate_roundtrip_max_error_m": error}
    bitmaps_write_json(directory / f"{token}.grid.json", result)
    cache[token] = result
    return result


def sidecars(path, ds):
    a = ds.transform
    # A,D,B,E,C,F: C/F are the upper-left pixel CENTER, not its corner.
    world = [a.a, a.d, a.b, a.e, a.c+(a.a+a.b)/2, a.f+(a.d+a.e)/2]
    path.with_suffix(".bpw").write_text("\n".join(format(v, ".17g") for v in world) + "\n")
    path.with_suffix(".prj").write_text(ds.crs.to_wkt() + "\n")
    # Let GDAL serialize PAM metadata, including each CRS's data-axis mapping.
    # EPSG:5179's authority axes are northing/easting, while raster data use x/y.
    with rasterio.open(path, "r+") as exported:
        exported.crs = ds.crs
        exported.nodata = 255


def verify_bitmap(path, indices, colors, source):
    with Image.open(path) as saved:
        assert saved.format == "BMP" and saved.mode == "P"
        assert saved.size == (source.width, source.height)
        assert np.array_equal(np.asarray(saved), indices), str(path)
        assert saved.getpalette() == colors, str(path)
    a, d, b, e, c, f = map(float, path.with_suffix(".bpw").read_text().splitlines())
    recovered = rasterio.Affine(a, b, c-(a+b)/2, d, e, f-(d+e)/2)
    assert np.allclose(tuple(recovered), tuple(source.transform), rtol=0, atol=1e-9)
    with rasterio.open(path) as saved:
        assert saved.crs == source.crs, str(path)
        assert np.allclose(tuple(saved.transform), tuple(source.transform), rtol=0, atol=1e-9)
        assert saved.shape == source.shape and saved.nodata == 255
        assert np.array_equal(saved.read(1), indices)
        assert np.array_equal(saved.read_masks(1) == 0, indices == 255)
        errors = []
        for row, col in [(0,0), (0,source.width-1), (source.height-1,0), (source.height-1,source.width-1), (source.height//2,source.width//2)]:
            expected = source.xy(row, col)
            actual = saved.xy(row, col)
            errors.extend(abs(x-y) for x,y in zip(expected,actual))
    return float(max(errors))


def output_path(ds, band, prefix):
    if ds.count == 1:
        return prefix.with_suffix(".bmp")
    timestamp = ds.tags(band).get("timestamp_utc")
    name = timestamp.replace("-", "").replace(":", "") if timestamp else f"band_{band:04d}"
    return prefix / (name + ".bmp")


def convert(source, prefix, root, output, cache):
    records = []
    source_hash = bitmaps_sha256(source)
    with rasterio.open(source) as ds:
        if ds.crs is None:
            raise ValueError(f"Cannot preserve unknown CRS: {source}")
        grid = grid_export(ds, output, cache)
        tags = ds.tags()
        for band in range(1, ds.count+1):
            values = ds.read(band)
            valid = (ds.read_masks(band) != 0) & np.isfinite(values)
            path = output_path(ds, band, prefix)
            path.parent.mkdir(parents=True, exist_ok=True)
            categorical = np.issubdtype(values.dtype, np.integer)
            if categorical:
                categories = set(np.unique(values[valid]).tolist())
                if not categories.issubset({0,1}):
                    raise ValueError(f"Unexpected categories {categories}: {source}, band {band}")
                indices = np.where(valid, values, 255).astype(np.uint8)
                encoding = {"kind": "exact_categorical_values", "nodata_index": 255,
                            "palette": CATEGORIES, "scientific_values_exact_in_bitmap": True}
            else:
                indices = np.full(values.shape, 255, dtype=np.uint8)
                low = float(values[valid].min()) if valid.any() else None
                high = float(values[valid].max()) if valid.any() else None
                step = (high-low)/254 if low is not None and high > low else 0.0
                if valid.any():
                    indices[valid] = np.clip(np.rint((values[valid].astype(np.float64)-low)/step),0,254).astype(np.uint8) if step else 0
                exact_path = path.with_suffix(".values.npy")
                np.save(exact_path, values, allow_pickle=False)
                restored = np.load(exact_path, allow_pickle=False)
                assert restored.dtype == values.dtype and restored.shape == values.shape
                assert restored.tobytes() == values.tobytes(), str(exact_path)
                encoding = {"kind": "continuous_values_colorized_to_palette_indices", "valid_indices": [0,254],
                    "nodata_index": 255, "minimum_value": low, "maximum_value": high, "quantization_step": step,
                    "approximate_decode": "minimum_value + palette_index*quantization_step; index 255 is unavailable",
                    "scientific_values_exact_in_bitmap": False, "exact_values_file": str(exact_path.relative_to(output)),
                    "exact_values_sha256": bitmaps_sha256(exact_path), "exact_values_dtype": str(values.dtype),
                    "exact_values_missing_rule": "Use the BMP index-255 mask; original numeric NoData is preserved in the NPY array."}
            colors = palette(categorical)
            image = Image.frombytes("P", (ds.width,ds.height), indices.tobytes())
            image.putpalette(colors)
            image.save(path, format="BMP")
            sidecars(path, ds)
            error = verify_bitmap(path, indices, colors, ds)
            band_tags = ds.tags(band)
            metadata = {"source_raster": str(source.relative_to(root)), "source_sha256": source_hash,
                "source_band": band, "source_dtype": str(values.dtype), "source_nodata": number(ds.nodatavals[band-1]),
                "source_description": ds.descriptions[band-1], "source_tags": tags, "source_band_tags": band_tags,
                "bitmap": str(path.relative_to(output)), "bitmap_sha256": bitmaps_sha256(path), "grid": grid,
                "world_file": str(path.with_suffix(".bpw").relative_to(output)),
                "projection_file": str(path.with_suffix(".prj").relative_to(output)),
                "gdal_pam_file": str(Path(str(path)+".aux.xml").relative_to(output)),
                "encoding": {**encoding, "palette_rgb": np.asarray(colors).reshape(256,3).tolist()},
                "valid_pixels": int(valid.sum()), "nodata_pixels": int((~valid).sum()),
                "validation": {"status": "passed", "source_grid_preserved": True,
                    "pixel_indices_exact_after_reopening": True, "crs_recognized_after_reopening": True,
                    "missing_mask_preserved": True, "pixel_center_max_error_m": error}}
            bitmaps_write_json(path.with_suffix(".json"), metadata)
            records.append({"source_raster": str(source.relative_to(root)), "source_band": band,
                "bitmap": str(path.relative_to(output)), "width": ds.width, "height": ds.height,
                "crs": ds.crs.to_string(), "pixel_width_m": ds.res[0], "pixel_height_m": ds.res[1],
                "timestamp_utc": band_tags.get("timestamp_utc", ""), "timestamp_kst": band_tags.get("timestamp_kst", ""),
                "event": tags.get("event", tags.get("event_id", "")), "region": tags.get("region_id", ""),
                "kind": encoding["kind"], "coordinate_file": grid["coordinate_file"],
                "valid_pixels": int(valid.sum()), "nodata_pixels": int((~valid).sum()),
                "bitmap_sha256": metadata["bitmap_sha256"], "pixel_center_max_error_m": error, "validation": "passed"})
    return records


def bitmaps_main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=bitmaps_ROOT)
    root = parser.parse_args().root.resolve()
    output = root / "bitmaps"
    output.mkdir(parents=True, exist_ok=True)
    archive = root / "sources/zenodo_21788344/extracted"
    jobs = [(p, output/"archive"/p.relative_to(archive).with_suffix("")) for p in sorted(archive.rglob("*.tif"))]
    jobs += [(p, output/"regions"/p.relative_to(root/"regions").with_suffix("")) for p in sorted((root/"regions").rglob("*.tif"))]
    cache, records = {}, []
    for source, prefix in jobs:
        records.extend(convert(source, prefix, root, output, cache))
    with (output/"catalog.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    summary = {"status": "passed", "source_raster_files": len(jobs), "bitmap_files": len(records),
        "downloaded_archive_bitmaps": sum(r["bitmap"].startswith("archive/") for r in records),
        "regional_hourly_bitmaps": sum(bool(r["timestamp_utc"]) for r in records),
        "categorical_bitmaps": sum(r["kind"] == "exact_categorical_values" for r in records),
        "continuous_bitmaps_with_exact_value_sidecars": sum(r["kind"] != "exact_categorical_values" for r in records),
        "coordinate_grids": len(cache), "max_longitude_latitude_roundtrip_error_m": max(v["coordinate_roundtrip_max_error_m"] for v in cache.values()),
        "max_bitmap_pixel_center_error_m": max(r["pixel_center_max_error_m"] for r in records),
        "checks": ["Each BMP reopened with Pillow and GDAL/rasterio", "Palette indices and colors preserved", "World files independently recover original affine",
            "CRS and pixel centers preserved", "Missing masks preserved", "Exact floating-point arrays checked byte-for-byte", "Longitude/latitude roundtrip below 1 mm"],
        "scientific_interpretation": "Storage and display conversion only; all source reconstruction and timing limitations remain."}
    bitmaps_write_json(output/"validation_summary.json", summary)
    bitmaps_write_json(output/"manifest.json", {"summary": summary, "bitmaps": records, "grids": list(cache.values())})
    print(json.dumps(summary, indent=2))


