"""Prepare an explicitly assumed FARSITE scenario from cached physical inputs.

The landscape uses measured-product classes and decoded physical raster units.
Missing burned observations initialize as unburned. Missing environmental data
remain unavailable and become artificial nonburnable barriers in the engine;
their locations are retained in the returned coverage mask. No future weather,
endpoint outcomes, vegetation-to-fuel conversion, or fitted probabilities are
used to construct a scenario.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta, timezone
import hashlib
import json
import numbers
from pathlib import Path
import struct

from affine import Affine
import numpy as np
import pandas as pd
from pyproj import CRS, Geod, Transformer
import rasterio
from rasterio.features import shapes
import shapefile
from shapely.geometry import shape
from shapely.geometry.polygon import orient

from .paths import DATA_ROOT


LCP_HEADER_BYTES = 7316
LCP_LAYER_NAMES = ("elevation", "slope", "aspect", "fuel_model", "canopy_cover",
                   "canopy_height", "canopy_base_height", "canopy_bulk_density")
LANDSCAPE_FILES = (
    "terrain/elevation_m_375m.tif", "terrain/slope_degrees_375m.tif",
    "terrain/aspect_degrees_375m.tif", "fuel/landfire_2016_fbfm40_375m.tif",
    "fuel/canopy_cover_percent_375m.tif", "fuel/canopy_height_m_375m.tif",
    "fuel/canopy_base_height_m_375m.tif", "fuel/canopy_bulk_density_kg_m3_375m.tif",
)
WEATHER_FILES = ("temperature_2m", "relative_humidity_2m", "precipitation",
                 "wind_speed_10m", "wind_direction_10m")


@dataclass(frozen=True)
class FuelMoistureScenario:
    """Assumed percentages of dry fuel mass, never inferred observations.

    These illustrative defaults are a fixed scenario. They are not event-date
    measurements, calibration estimates, or replacements derived from GRIDMET.
    The five surface moisture values apply to every standard fuel model.
    """

    dead_1h_percent: int = 6
    dead_10h_percent: int = 7
    dead_100h_percent: int = 8
    live_herb_percent: int = 60
    live_woody_percent: int = 90
    foliar_percent: int = 100

    def __post_init__(self):
        for key, value in asdict(self).items():
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral):
                raise ValueError(f"{key} must be a positive integer percentage")
            if not 1 <= value <= 300:
                raise ValueError(f"{key} must be between 1 and 300 percent")


@dataclass(frozen=True)
class PreparedFarsiteInputs:
    lcp_path: Path
    input_path: Path
    ignition_path: Path
    raws_path: Path
    manifest_path: Path
    original_shape: tuple[int, int]
    transform: Affine
    epsg: int
    boundary_padding: int
    initial_burned: np.ndarray
    initial_burned_valid: np.ndarray
    environment_valid: np.ndarray
    manifest: dict


def _integer(value, name, *, positive=True):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Integral):
        raise ValueError(f"{name} must be an integer excluding booleans")
    if value < (1 if positive else 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'}")
    return int(value)


def _cutoff(value, *, allow_minutes=False):
    result = pd.Timestamp(value)
    if result.tzinfo is None:
        raise ValueError("cutoff_utc must include an explicit UTC offset")
    result = result.tz_convert("UTC")
    if allow_minutes and result != result.floor("min"):
        raise ValueError("Observed cutoff_utc must be an exact minute timestamp")
    if not allow_minutes and result != result.floor("h"):
        raise ValueError("cutoff_utc must be an exact whole-hour timestamp")
    return result


def _read_aligned(path, *, transform, shape, epsg, band=1):
    if not path.is_file():
        raise ValueError(f"Required physical FARSITE input is unavailable: {path}")
    with rasterio.open(path) as src:
        if (src.transform != transform or (src.height, src.width) != shape
                or src.crs.to_epsg() != epsg):
            raise ValueError(f"FARSITE input grid does not match the original rectangle: {path}")
        values = src.read(band, masked=True).astype(np.float64).filled(np.nan)
        tags = src.tags()
    return values, tags


def _rounded(values, scale, name):
    encoded = np.rint(values * scale)
    if np.any(np.isfinite(encoded) & ((encoded < -32768) | (encoded > 32767))):
        raise ValueError(f"{name} is outside the signed 16-bit LCP encoding range")
    return np.where(np.isfinite(encoded), encoded, 0).astype("<i2")


def _encode_landscape(values):
    elevation, slope, aspect, fuel, cover, height, base, density = values
    # Flat terrain has no physical downslope direction; zero is an equivalent
    # representation when slope is exactly zero, not an imputed slope direction.
    flat_aspect = ~np.isfinite(aspect) & np.isfinite(slope) & (slope == 0)
    aspect = np.where(flat_aspect, 0, aspect)
    valid = np.logical_and.reduce([np.isfinite(a) for a in
                                   (elevation, slope, aspect, fuel, cover, height, base, density)])
    constraints = ((slope >= 0) & (slope <= 90) & (aspect >= 0) & (aspect <= 360)
                   & (cover >= 0) & (cover <= 100) & (height >= 0)
                   & (base >= 0) & (density >= 0))
    if np.any(valid & ~constraints):
        raise ValueError("Physical landscape values violate slope/aspect/canopy units")
    if np.any(np.isfinite(fuel) & (fuel != np.rint(fuel))):
        raise ValueError("LANDFIRE FBFM40 values must be integer fuel-model codes")
    # The port provides Anderson 1--13, Scott--Burgan 101--204, and nonburnable
    # 91--99. Do not silently assign an unrecognized class to a fuel model.
    standard = ((fuel >= 1) & (fuel <= 13)) | np.isin(fuel, [91, 92, 93, 98, 99])
    for lo, hi in [(101, 109), (121, 124), (141, 149), (161, 165), (181, 189), (201, 204)]:
        standard |= (fuel >= lo) & (fuel <= hi)
    if np.any(np.isfinite(fuel) & ~standard):
        bad = np.unique(fuel[np.isfinite(fuel) & ~standard]).tolist()
        raise ValueError(f"Unrecognized standard fuel-model codes; no conversion is assumed: {bad}")
    scales = (1, 1, 1, 1, 1, 10, 10, 100)
    data = np.stack([_rounded(a, scale, name) for a, scale, name in
                     zip((elevation, slope, aspect, fuel, cover, height, base, density),
                         scales, LCP_LAYER_NAMES)], axis=-1)
    data[..., 2] %= 360
    data[~valid] = 0
    data[..., 3][~valid] = 99
    return data, valid, int(flat_aspect.sum())


def _write_lcp(path, data, transform, epsg, *, source_names=LANDSCAPE_FILES):
    """Write the port's sequential 7,316-byte little-endian LCP header.

    Source: Farsite5::ReadHeader and LandscapeData unit conversions. Explicit
    packing avoids native C structure alignment and platform-dependent longs.
    Cells are eight interleaved signed shorts in north-to-south row order.
    """
    if data.ndim != 3 or data.shape[-1] != 8:
        raise ValueError("LCP cells must have shape [height, width, 8]")
    if transform.b != 0 or transform.d != 0 or transform.a <= 0 or transform.e >= 0:
        raise ValueError("FARSITE requires a north-up projected metric rectangle")
    crs = CRS.from_epsg(epsg)
    if not crs.is_projected or any(axis.unit_conversion_factor != 1 for axis in crs.axis_info):
        raise ValueError("FARSITE landscape coordinates must be projected in metres")
    height, width, _ = data.shape
    west, north = transform.c, transform.f
    east, south = west + width * transform.a, north + height * transform.e
    lon, lat = Transformer.from_crs(epsg, 4326, always_xy=True).transform(
        (west + east) / 2, (north + south) / 2)
    header = bytearray(struct.pack("<iii4d", 21, 20, round(lat), west, east, south, north))
    for i in range(10):
        unique = np.unique(data[..., i]) if i < 8 else np.array([0])
        count = len(unique) if len(unique) <= 100 else -1
        categories = np.zeros(100, dtype="<i4")
        if count > 0:
            categories[:count] = unique
        header.extend(struct.pack("<iii", int(unique.min()), int(unique.max()), count))
        header.extend(categories.tobytes())
    header.extend(struct.pack("<ii4di2d", width, height, east, west, north, south,
                              0, transform.a, -transform.e))
    # Elevation metres; slope degrees; aspect clockwise degrees from grid north;
    # standard fuels; canopy percent; height/base tenths m; density hundredths kg/m3.
    header.extend(struct.pack("<10h", 0, 0, 2, 0, 1, 1, 1, 1, 0, 0))
    for name in tuple(source_names) + ("", ""):
        raw = name.encode("utf-8")[:255]
        header.extend(raw.ljust(256, b"\0"))
    description = ("Cached physical 375m rectangle; assumed cutoff restart scenario; "
                   "EPSG:" + str(epsg)).encode("ascii")
    header.extend(description.ljust(512, b"\0"))
    if len(header) != LCP_HEADER_BYTES:
        raise RuntimeError(f"Unexpected packed LCP header size: {len(header)}")
    with path.open("xb") as stream:
        stream.write(header)
        stream.write(np.asarray(data, dtype="<i2", order="C").tobytes())
    return {"shape": [height, width], "bounds": [west, south, east, north],
            "transform": list(transform)[:6], "epsg": epsg,
            "centroid_longitude": lon, "centroid_latitude": lat,
            "header_bytes": LCP_HEADER_BYTES, "bytes_per_cell": 16}


def _write_ignition(path, burned, transform, epsg):
    polygons = []
    for geometry, value in shapes(burned.astype("uint8"), mask=burned,
                                   transform=transform, connectivity=4):
        if value == 1:
            polygons.append(orient(shape(geometry), sign=-1))
    if not polygons:
        raise ValueError("The selected cutoff has no known initial fire for FARSITE ignition")
    with shapefile.Writer(str(path), shapeType=shapefile.POLYGON) as writer:
        writer.field("source", "C", size=32)
        for polygon in polygons:
            rings = [list(polygon.exterior.coords)]
            rings += [list(ring.coords) for ring in polygon.interiors]
            writer.poly(rings)
            writer.record("known_cutoff_burned")
    path.with_suffix(".prj").write_text(CRS.from_epsg(epsg).to_wkt(version="WKT1_ESRI"))
    return {"polygon_count": len(polygons), "burned_pixels": int(burned.sum()),
            "burned_area_projected_m2": float(sum(p.area for p in polygons)),
            "restart_assumption": "every known cumulative burned polygon boundary is an initial active perimeter"}


def _weather_band(path, cutoff):
    with rasterio.open(path) as src:
        times = list(src.descriptions)
    if all(times):
        parsed = pd.to_datetime(times, utc=True, errors="coerce")
        matches = np.flatnonzero(parsed == cutoff)
        if len(matches) == 1:
            return int(matches[0]) + 1
    # Retain the exact acquisition timestamps, not a nearest/last-value clamp.
    for name in ("ecmwf_ifs_bands.csv", "era5_bands.csv"):
        sidecar = path.parent / name
        if sidecar.exists():
            table = pd.read_csv(sidecar)
            matches = table.loc[pd.to_datetime(table["time_utc"], utc=True) == cutoff, "band"]
            if len(matches) == 1:
                return int(matches.iloc[0])
    raise ValueError(f"Exact cutoff weather timestamp is unavailable: {cutoff.isoformat()} in {path}")


def _station_weather(arrays, valid, transform, epsg):
    if not valid.any():
        raise ValueError("No cells have complete physical landscape and cutoff weather")
    temp, humidity, precipitation, speed, direction = arrays
    if np.any(valid & ((humidity < 0) | (humidity > 100) | (precipitation < 0)
                       | (speed < 0) | (direction < 0) | (direction > 360))):
        raise ValueError("Cutoff weather violates temperature/humidity/rain/wind units")
    radians = np.deg2rad(direction[valid])
    u = float(np.mean(-speed[valid] * np.sin(radians)))
    v = float(np.mean(-speed[valid] * np.cos(radians)))
    mean_speed = float(np.hypot(u, v))
    true_direction = float(np.rad2deg(np.arctan2(-u, -v)) % 360) if mean_speed > 1e-12 else 0.0
    h, w = valid.shape
    x, y = transform @ (w / 2, h / 2)
    lon, lat = Transformer.from_crs(epsg, 4326, always_xy=True).transform(x, y)
    to_grid = Transformer.from_crs(4326, epsg, always_xy=True)
    lon2, lat2, _ = Geod(ellps="WGS84").fwd(lon, lat, true_direction, 100)
    x2, y2 = to_grid.transform(lon2, lat2)
    grid_direction = float(np.rad2deg(np.arctan2(x2 - x, y2 - y)) % 360)
    rotation = float((grid_direction - true_direction + 180) % 360 - 180)
    return {"temperature_celsius": float(np.mean(temp[valid])),
            "relative_humidity_percent": float(np.mean(humidity[valid])),
            "precipitation_mm_per_hour": float(np.mean(precipitation[valid])),
            "wind_speed_10m_m_per_s": mean_speed,
            "wind_direction_from_true_north_degrees": true_direction,
            "wind_direction_from_grid_north_degrees": grid_direction,
            "true_to_grid_rotation_degrees": rotation,
            "centroid_longitude": lon, "centroid_latitude": lat,
            "station_cells": int(valid.sum()),
            "spatial_reduction": "arithmetic mean temperature/humidity/rain over complete cells; mean east/north wind vector",
            "direction_projection": "100m WGS84 geodesic at rectangle centroid, transformed to the landscape CRS"}


def _sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare_farsite_inputs(event_id, cutoff_utc, hours, output_dir, *,
                           data_root=DATA_ROOT, moisture=None, cloud_cover_percent=0,
                           boundary_padding=1, utc_offset_hours=-7,
                           timestep_minutes=15, distance_resolution_m=30,
                           perimeter_resolution_m=60, observed_initial=None,
                           observed_initial_valid=None, observed_initial_source=None):
    """Write a FARSITE input bundle from the full cached U.S. rectangle.

    The hourly RAWS series repeats only the cutoff spatial summary. An extra
    synthetic hour supports the engine's final integration step; evaluation
    must still threshold arrival times at exactly ``60 * hours`` minutes.
    Local clock uses the explicit fixed UTC offset (Mountain Standard Time by
    default), because this engine's fuel-moisture solar calculations use RAWS
    clock hours. No future environmental slices are read.
    """
    observed_mode = observed_initial is not None
    if observed_mode:
        if (isinstance(hours, (bool, np.bool_)) or not isinstance(hours, numbers.Real)
                or not np.isfinite(hours) or hours <= 0
                or not np.isclose(hours * 60, round(hours * 60), rtol=0, atol=1e-8)):
            raise ValueError("Observed duration must be positive and contain a whole number of minutes")
        hours = float(hours)
        if not isinstance(observed_initial_source, dict) or not observed_initial_source:
            raise ValueError("Observed ignition requires nonempty observed_initial_source provenance")
    else:
        hours = _integer(hours, "hours")
        if observed_initial_valid is not None or observed_initial_source is not None:
            raise ValueError("Observed ignition metadata requires observed_initial")
    padding = _integer(boundary_padding, "boundary_padding", positive=False)
    timestep = _integer(timestep_minutes, "timestep_minutes")
    if timestep > 60:
        raise ValueError("timestep_minutes must be at most 60")
    if not isinstance(event_id, str) or Path(event_id).name != event_id or event_id in (".", ".."):
        raise ValueError("event_id must be one region identifier")
    cutoff = _cutoff(cutoff_utc, allow_minutes=observed_mode)
    weather_cutoff = cutoff.floor("h") if observed_mode else cutoff
    if (isinstance(utc_offset_hours, (bool, np.bool_)) or not isinstance(utc_offset_hours, numbers.Real)
            or not np.isfinite(utc_offset_hours) or not -12 <= utc_offset_hours <= 14):
        raise ValueError("utc_offset_hours must be a finite number between -12 and 14")
    # This pinned port sets the start hour but does not set the start minute.
    # Minute-bearing clock offsets therefore cannot represent exact UTC cutoffs.
    if utc_offset_hours != round(utc_offset_hours):
        raise ValueError("utc_offset_hours must be an integer number of hours for this FARSITE port")
    if (isinstance(cloud_cover_percent, (bool, np.bool_)) or not isinstance(cloud_cover_percent, numbers.Real)
            or not np.isfinite(cloud_cover_percent) or not 0 <= cloud_cover_percent <= 100):
        raise ValueError("cloud_cover_percent must be a finite percentage in [0,100]")
    for key, value in [("distance_resolution_m", distance_resolution_m),
                       ("perimeter_resolution_m", perimeter_resolution_m)]:
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, numbers.Real) or not np.isfinite(value) or value <= 0:
            raise ValueError(f"{key} must be finite and positive")
    moisture = FuelMoistureScenario() if moisture is None else moisture
    if not isinstance(moisture, FuelMoistureScenario):
        raise ValueError("moisture must be a FuelMoistureScenario")
    region = Path(data_root) / "regions" / event_id
    grid_path = region / "grid.json"
    grid = json.loads(grid_path.read_text())
    if grid["country"] != "US":
        raise ValueError("No cached LANDFIRE physical fuel models are available for this non-U.S. event")
    original_shape = (int(grid["height"]), int(grid["width"]))
    transform, epsg = Affine(*grid["transform"]), int(grid["epsg"])
    if not pd.Timestamp(grid["start_utc"]) <= cutoff <= pd.Timestamp(grid["end_utc"]):
        raise ValueError("cutoff_utc lies outside the cached event interval")
    files = [region / name for name in LANDSCAPE_FILES]
    values, landscape_tags = zip(*[_read_aligned(path, transform=transform,
                              shape=original_shape, epsg=epsg) for path in files])
    data, landscape_valid, flat_aspect_count = _encode_landscape(values)
    weather_paths = [region / "weather" / f"{name}_375m.tif" for name in WEATHER_FILES]
    weather_bands = [_weather_band(path, weather_cutoff) for path in weather_paths]
    weather, weather_tags = zip(*[_read_aligned(path, transform=transform,
                   shape=original_shape, epsg=epsg, band=band)
                   for path, band in zip(weather_paths, weather_bands)])
    environment_valid = landscape_valid & np.logical_and.reduce([np.isfinite(a) for a in weather])
    data[~environment_valid] = 0
    data[..., 3][~environment_valid] = 99
    station = _station_weather(weather, environment_valid, transform, epsg)
    elevation = float(np.mean(values[0][environment_valid]))
    if observed_mode:
        raw_initial = np.asarray(observed_initial)
        initial_valid = np.asarray(observed_initial_valid)
        if (raw_initial.shape != original_shape or initial_valid.shape != original_shape
                or initial_valid.dtype.kind != "b" or not np.isfinite(raw_initial).all()
                or np.any((raw_initial != 0) & (raw_initial != 1))):
            raise ValueError("Observed ignition and boolean validity must match the complete rectangle")
        initial = initial_valid & (raw_initial == 1)
        burn_source = dict(observed_initial_source)
    else:
        arrival_path = region / "arrival_time_hours.tif"
        arrival, _ = _read_aligned(arrival_path, transform=transform,
                                  shape=original_shape, epsg=epsg)
        age = float((cutoff - pd.Timestamp(grid["t0_utc"])) / pd.Timedelta(hours=1))
        initial_valid = np.isfinite(arrival)
        initial = initial_valid & (arrival <= age)
        burn_source = {"path": str(arrival_path.resolve()), "sha256": _sha256(arrival_path),
                       "derivation": "finite reconstructed arrival<=cutoff age only"}
    if not initial.any():
        raise ValueError("The selected cutoff has no known initial fire for FARSITE ignition")
    local_tz = timezone(timedelta(hours=float(utc_offset_hours)))
    start = cutoff.tz_convert(local_tz)
    # Survey endpoints are exact whole minutes. Construct their duration in
    # integer minutes: floating-point hours can otherwise lose one nanosecond,
    # which makes formatting an HHMM clock lose a whole minute.
    duration = (pd.Timedelta(minutes=int(round(hours * 60))) if observed_mode
                else pd.Timedelta(hours=hours))
    end = start + duration
    weather_end = end + pd.Timedelta(hours=1)
    records = pd.date_range(start.floor("h"), weather_end.ceil("h"), freq="h")
    if start.year != weather_end.year or any(date.month == 2 and date.day == 29 for date in records):
        raise ValueError("This FARSITE adapter does not support leap-day or year-crossing runs")
    output = Path(output_dir).resolve()
    if any(char.isspace() for char in str(output)):
        raise ValueError("The FARSITE command parser requires output paths without whitespace")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"FARSITE input directory must be new or empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    lcp_path, input_path = output / "landscape.lcp", output / "scenario.input"
    ignition_path, raws_path = output / "ignition.shp", output / "cutoff_weather.raws"
    if padding:
        padded = np.zeros((original_shape[0] + 2 * padding,
                           original_shape[1] + 2 * padding, 8), dtype="<i2")
        padded[..., 3] = 99
        padded[padding:-padding, padding:-padding] = data
        padded_transform = transform @ Affine.translation(-padding, -padding)
    else:
        padded, padded_transform = data, transform
    landscape = _write_lcp(lcp_path, padded, padded_transform, epsg)
    ignition = _write_ignition(ignition_path, initial, transform, epsg)
    raws_lines = [f"RAWS_ELEVATION: {elevation:.9g}", "RAWS_UNITS: Metric", f"RAWS: {len(records)}"]
    for date in records:
        raws_lines.append(
            f"{date.year} {date.month} {date.day} {date.hour * 100 + date.minute} "
            f"{station['temperature_celsius']:.9g} {station['relative_humidity_percent']:.9g} "
            f"{station['precipitation_mm_per_hour']:.9g} {station['wind_speed_10m_m_per_s'] * 3.6:.9g} "
            f"{station['wind_direction_from_grid_north_degrees']:.9g} {float(cloud_cover_percent):.9g}")
    raws_path.write_text("\n".join(raws_lines) + "\n")
    surface_moisture = " ".join(str(getattr(moisture, name)) for name in
                               ("dead_1h_percent", "dead_10h_percent", "dead_100h_percent",
                                "live_herb_percent", "live_woody_percent"))
    lines = ["FARSITE INPUTS FILE VERSION 1.0",
             f"FARSITE_START_TIME: {start.month:02d} {start.day:02d} {start.hour * 100 + start.minute:04d}",
             f"FARSITE_END_TIME: {end.month:02d} {end.day:02d} {end.hour * 100 + end.minute:04d}",
             f"FARSITE_TIMESTEP: {timestep}", f"FARSITE_DISTANCE_RES: {distance_resolution_m:g}",
             f"FARSITE_PERIMETER_RES: {perimeter_resolution_m:g}",
             "FARSITE_MIN_IGNITION_VERTEX_DISTANCE: 15", "FARSITE_SPOT_PROBABILITY: 0",
             "FARSITE_SPOT_IGNITION_DELAY: 0", "FARSITE_MINIMUM_SPOT_DISTANCE: 30",
             "FARSITE_ACCELERATION_ON: 1", "FARSITE_FILL_BARRIERS: 1", "SPOTTING_SEED: 0",
             "FUEL_MOISTURES_DATA: 1", f"0 {surface_moisture}",
             f"RAWS_FILE: {raws_path}", f"FOLIAR_MOISTURE_CONTENT: {moisture.foliar_percent}",
             "CROWN_FIRE_METHOD: Finney", "NUMBER_PROCESSORS: 1",
             "FLAMELENGTH:", "SPREADRATE:", "INTENSITY:", "CROWNSTATE:"]
    input_path.write_text("\n".join(lines) + "\n")
    manifest = {
        "event_id": event_id, "cutoff_utc": cutoff.isoformat(),
        "endpoint_utc": (cutoff + duration).isoformat(), "hours": hours,
        "scenario_kind": "deterministic FARSITE cutoff-perimeter restart; not calibrated probability",
        "original_shape": list(original_shape), "original_transform": list(transform)[:6],
        "original_epsg": epsg, "landscape": landscape,
        "layer_order": list(LCP_LAYER_NAMES),
        "encoding_scales": [1, 1, 1, 1, 1, 10, 10, 100],
        "unit_flags": [0, 0, 2, 0, 1, 1, 1, 1, 0, 0],
        "boundary_padding_cells": padding, "boundary_policy": "exterior unburned nonburnable fuel99; original rectangle retained",
        "environment_valid_pixels": int(environment_valid.sum()),
        "environment_unavailable_pixels": int((~environment_valid).sum()),
        "missing_environment_engine_policy": "artificial fuel99 barriers; returned coverage false; influences spread around gaps",
        "flat_aspect_equivalent_zero_pixels": flat_aspect_count,
        "missing_initial_burned_policy": "initialize unburned; original observation availability retained separately",
        "ignition": ignition, "station_weather": station,
        "environment_policy": "repeat the spatially summarized cutoff slice; no future environmental slices",
        "weather_source_bands": dict(zip(WEATHER_FILES, weather_bands)),
        "weather_source_cutoff_utc": weather_cutoff.isoformat(),
        "weather_units_written": {"temperature": "Celsius", "humidity": "percent", "precipitation": "mm per hour", "wind_speed": "10m km/h", "wind_direction": "meteorological from grid north degrees"},
        "native_metric_conversion": "engine converts10m km/h to20ft mph with0.5402, rainmm tohundredths inch with3.93",
        "clock": {"utc_offset_hours": float(utc_offset_hours), "start_local": start.isoformat(),
                  "end_local": end.isoformat(), "policy": "explicit fixed local-standard offset for native solar/moisture clock"},
        "synthetic_weather_records": len(records), "synthetic_weather_end_local": weather_end.isoformat(),
        "fuel_moisture_scenario_percent": asdict(moisture),
        "fuel_moisture_interpretation": "all supplied percentages assumed and fixed at scenario initialization; native dead-fuel conditioning may evolve them",
        "cloud_cover_scenario_percent": float(cloud_cover_percent),
        "cloud_cover_interpretation": "caller scenario assumption; not inferred from shortwave radiation",
        "spot_probability": 0, "crown_fire_method": "Finney", "timestep_minutes": timestep,
        "distance_resolution_m": float(distance_resolution_m), "perimeter_resolution_m": float(perimeter_resolution_m),
        "arrival_selection": f"native arrival minutes finite and between0 and{60 * hours}; initial burns added exactly",
        "source_files": [{"path": str(path.resolve()), "sha256": _sha256(path), "role": role,
                          "tags": tags} for path, role, tags in
                         list(zip(files, LCP_LAYER_NAMES, landscape_tags))
                         + list(zip(weather_paths, WEATHER_FILES, weather_tags))],
        "cutoff_burn_state_source": burn_source,
        "grid_source": {"path": str(grid_path.resolve()), "sha256": _sha256(grid_path)},
    }
    if observed_mode:
        manifest["native_clock_requirement"] = "minute-preserving observed-clock build required; legacy start/end minute truncation is rejected"
    manifest["generated_files"] = [{"path": path.name, "sha256": _sha256(path)}
                                    for path in sorted(output.iterdir()) if path.is_file()]
    manifest_path = output / "input_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return PreparedFarsiteInputs(lcp_path, input_path, ignition_path, raws_path,
              manifest_path, original_shape, transform, epsg, padding, initial.copy(),
              initial_valid.copy(), environment_valid.copy(), manifest)
