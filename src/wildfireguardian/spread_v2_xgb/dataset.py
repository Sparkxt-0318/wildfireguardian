"""Data access for the v2 data-driven fire-spread model.

This module is the single entry point to the ``firms_data/`` bundle that
the v2 spread classifier consumes. Each Korean wildfire event ships with:

- ``{id}_detections.csv`` / ``.geojson`` — NASA FIRMS VIIRS 375 m active-fire
  detections (SNPP + NOAA-20), one row per detection pixel with ``frp``,
  ``confidence`` and a UTC ``timestamp``.
- ``{id}_fuel.tif`` — ESA WorldCover 10 m land-cover class codes (EPSG:4326).
- ``{id}_dem.tif`` — Copernicus/SRTM ~30 m elevation (EPSG:4326).
- ``{id}_era5.nc`` — ECMWF ERA5 single-level hourly reanalysis, CDS
  zip-wrapped (instant: u10/v10/t2m/d2m + accum: tp). May be 0 bytes when
  the CDS retrieval failed (handled downstream as weather = NaN).

Two manifests describe the bundle:

- ``fire_manifest.json`` — per-fire bbox, dates, ignition, reported area,
  detection counts, distinct overpass hours.
- ``data_layers_manifest.json`` — per-fire raster paths/shapes, the
  ``worldcover_burnable_map`` (class → burnable 0/1), and ``burnable_frac``.

**Provenance is first-class.** Nothing here is synthetic; every layer
traces to a public archive (NASA FIRMS, ESA WorldCover, ECMWF ERA5).
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path


def firms_dir() -> Path:
    """Locate the extracted ``firms_data`` bundle under ``data/raw``."""
    root = Path(__file__).resolve().parents[3]
    d = root / "data" / "raw" / "firms_data"
    if not d.exists():
        raise FileNotFoundError(
            f"firms_data bundle not found at {d}. Extract firms_data.zip into "
            f"data/raw/ first (see scripts/spread_v2/00_audit.py)."
        )
    return d


@lru_cache(maxsize=1)
def load_manifests() -> tuple[dict, dict]:
    """Return ``(fire_manifest, data_layers_manifest)`` as parsed dicts."""
    d = firms_dir()
    fire = json.loads((d / "fire_manifest.json").read_text())
    layers = json.loads((d / "data_layers_manifest.json").read_text())
    return fire, layers


@dataclass(frozen=True)
class FireData:
    """All on-disk artefacts + metadata for one wildfire event.

    Paths are absolute; ``has_era5`` is False when the ERA5 file is missing
    or 0 bytes (e.g. ``gangneung_donghae_2022`` whose CDS retrieval failed).
    """

    fire_id: str
    name_kr: str
    bbox_wgs84: tuple[float, float, float, float]
    start: date
    end: date
    ignition_wgs84: tuple[float, float]
    reported_ha: float
    n_detections: int
    distinct_overpass_hours: int
    notes: str
    detections_csv: Path
    fuel_tif: Path
    dem_tif: Path
    era5_nc: Path
    burnable_frac: float

    @property
    def has_era5(self) -> bool:
        return self.era5_nc.exists() and self.era5_nc.stat().st_size > 0


# ESA WorldCover legend → burnable gate (1 = carries fire, 0 = does not).
# 10 tree, 20 shrub, 30 grass, 40 crop, 90 herbaceous wetland, 95 mangrove,
# 100 moss/lichen are burnable; 50 built, 60 bare, 70 snow/ice, 80 water are not.
def worldcover_burnable_map() -> dict[int, int]:
    _, layers = load_manifests()
    return {int(k): int(v) for k, v in layers["worldcover_burnable_map"].items()}


def _parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


@lru_cache(maxsize=1)
def all_fires() -> dict[str, FireData]:
    """Build a ``{fire_id: FireData}`` registry from the two manifests."""
    fire_m, layers_m = load_manifests()
    d = firms_dir()
    layers_by_id = {ly["id"]: ly for ly in layers_m["layers"]}

    out: dict[str, FireData] = {}
    for f in fire_m["fires"]:
        fid = f["id"]
        ly = layers_by_id.get(fid, {})
        out[fid] = FireData(
            fire_id=fid,
            name_kr=f["name"],
            bbox_wgs84=tuple(f["bbox"]),  # type: ignore[arg-type]
            start=_parse_date(f["start"]),
            end=_parse_date(f["end"]),
            ignition_wgs84=tuple(f["ignition"]),  # type: ignore[arg-type]
            reported_ha=float(f["reported_ha"]),
            n_detections=int(f["n_detections"]),
            distinct_overpass_hours=int(f["distinct_overpass_hours"]),
            notes=f.get("notes", ""),
            detections_csv=d / f["csv"],
            fuel_tif=d / f"{fid}_fuel.tif",
            dem_tif=d / f"{fid}_dem.tif",
            era5_nc=d / f"{fid}_era5.nc",
            burnable_frac=float(ly.get("burnable_frac", float("nan"))),
        )
    return out


def get_fire(fire_id: str) -> FireData:
    fires = all_fires()
    if fire_id not in fires:
        raise KeyError(f"unknown fire {fire_id!r}; have {sorted(fires)}")
    return fires[fire_id]


def era5_is_zip(path: Path) -> bool:
    """True iff ``path`` is a non-empty CDS zip-wrapped ERA5 file."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    return zipfile.is_zipfile(path)


__all__ = [
    "firms_dir",
    "load_manifests",
    "FireData",
    "worldcover_burnable_map",
    "all_fires",
    "get_fire",
    "era5_is_zip",
]
