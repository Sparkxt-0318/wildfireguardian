"""Loaders for the real Korean wildfire dataset (FIRMS + DEM + fuel + ERA5).

This is the data layer for the **spread_v2** data-driven per-cell ignition
model. It reads the bundle that ships as ``firms_data.zip``:

- ``<fire>_detections.csv`` — NASA FIRMS active-fire detections (MODIS +
  VIIRS) with ``latitude, longitude, acq_date, acq_time, frp, confidence,
  satellite, instrument, timestamp``.
- ``<fire>_dem.tif`` — SRTM-class elevation (EPSG:4326, ~30 m, metres).
- ``<fire>_fuel.tif`` — ESA WorldCover land-cover class codes (EPSG:4326,
  ~10 m, uint8); burnability via ``data_layers_manifest.json``.
- ``<fire>_era5.nc`` — ERA5 reanalysis (a CDS zip of two HDF5 NetCDFs:
  instantaneous ``u10, v10, t2m, d2m`` and accumulated ``tp``), 3-hourly on
  a 0.25° grid.
- ``fire_manifest.json`` / ``data_layers_manifest.json`` — provenance.

**Data provenance (honest):** every field here is REAL observational data.
FIRMS is a *detection* product, not a burned-area product: a cell is
labelled "detected" only when a satellite overpass caught an active thermal
anomaly there, so the labels under-count (cloud / canopy / between-overpass
burning) and the first detection can lag the true ignition by days (e.g.
Yeongdeok ignited 2025-03-22 but the first FIRMS hit is 2025-03-25). The
model and report treat the FIRMS footprint as an *observed lower bound*, not
ground truth.
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

# Candidate locations for the unzipped FIRMS bundle, most-specific first.
_DEFAULT_DATA_DIRS = (
    "data/raw/firms/firms_data",
    "data/raw/firms",
    "data/raw/firms_data",
)


def find_data_dir(explicit: str | os.PathLike | None = None) -> Path | None:
    """Locate the directory holding ``fire_manifest.json``.

    Resolution order: ``explicit`` arg → ``$WFG_FIRMS_DIR`` → the default
    in-repo locations. Returns ``None`` if the dataset is not present (it is
    git-ignored, so this is the normal case in a fresh clone — callers should
    degrade gracefully / skip).
    """
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(Path(explicit))
    env = os.environ.get("WFG_FIRMS_DIR")
    if env:
        candidates.append(Path(env))
    repo_root = Path(__file__).resolve().parents[3]
    for rel in _DEFAULT_DATA_DIRS:
        candidates.append(repo_root / rel)
        candidates.append(Path.cwd() / rel)
    for c in candidates:
        if (c / "fire_manifest.json").exists():
            return c
        # Allow pointing at a parent that contains the bundle folder.
        nested = c / "firms_data"
        if (nested / "fire_manifest.json").exists():
            return nested
    return None


def data_available(explicit: str | os.PathLike | None = None) -> bool:
    """True iff the real FIRMS dataset is present on disk."""
    return find_data_dir(explicit) is not None


@dataclass(frozen=True)
class FireMeta:
    """Metadata for one fire event, from ``fire_manifest.json``."""

    id: str
    name: str
    bbox_wgs84: tuple[float, float, float, float]  # (minlon, minlat, maxlon, maxlat)
    start: str
    end: str
    ignition_lonlat: tuple[float, float]
    reported_ha: float
    notes: str
    n_detections: int
    first_detection: str | None = None
    last_detection: str | None = None


@dataclass
class FireEvent:
    """All real data layers for a single fire, lazily loaded.

    Construct via :func:`load_event`. Heavy rasters/weather are loaded on
    first access and cached on the instance.
    """

    meta: FireMeta
    data_dir: Path
    has_era5: bool = True
    _detections: pd.DataFrame | None = field(default=None, repr=False)

    # -- detections --------------------------------------------------------
    @property
    def detections(self) -> pd.DataFrame:
        """FIRMS detections sorted by time, with a tz-aware ``time`` column."""
        if self._detections is None:
            csv = self.data_dir / f"{self.meta.id}_detections.csv"
            df = pd.read_csv(csv)
            # The bundle ships a pre-joined UTC ``timestamp`` column.
            df["time"] = pd.to_datetime(df["timestamp"], utc=True)
            df = df.sort_values("time").reset_index(drop=True)
            # Normalise the columns we rely on downstream.
            for col in ("frp", "confidence"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            self._detections = df
        return self._detections

    # -- raster paths ------------------------------------------------------
    @property
    def dem_path(self) -> Path:
        return self.data_dir / f"{self.meta.id}_dem.tif"

    @property
    def fuel_path(self) -> Path:
        return self.data_dir / f"{self.meta.id}_fuel.tif"

    @property
    def era5_path(self) -> Path:
        return self.data_dir / f"{self.meta.id}_era5.nc"


def load_manifest(data_dir: str | os.PathLike | None = None) -> dict:
    """Load ``fire_manifest.json`` as a dict (raises if data absent)."""
    d = find_data_dir(data_dir)
    if d is None:
        raise FileNotFoundError(
            "FIRMS dataset not found; set $WFG_FIRMS_DIR or unzip firms_data.zip "
            "into data/raw/firms/."
        )
    return json.loads((d / "fire_manifest.json").read_text())


@lru_cache(maxsize=1)
def _burnable_map(data_dir_str: str) -> dict[int, int]:
    """WorldCover class-code → burnable (0/1) map from the layers manifest."""
    p = Path(data_dir_str) / "data_layers_manifest.json"
    if p.exists():
        m = json.loads(p.read_text()).get("worldcover_burnable_map", {})
        return {int(k): int(v) for k, v in m.items()}
    # Fallback: ESA WorldCover defaults (tree/shrub/grass/crop/wetland burn).
    return {10: 1, 20: 1, 30: 1, 40: 1, 50: 0, 60: 0, 70: 0, 80: 0, 90: 1, 95: 1, 100: 1}


def burnable_map(data_dir: str | os.PathLike | None = None) -> dict[int, int]:
    d = find_data_dir(data_dir)
    if d is None:
        return {10: 1, 20: 1, 30: 1, 40: 1, 50: 0, 60: 0, 70: 0, 80: 0, 90: 1, 95: 1, 100: 1}
    return _burnable_map(str(d))


def list_fires(data_dir: str | os.PathLike | None = None) -> list[FireMeta]:
    """All fire metadata entries from the manifest."""
    man = load_manifest(data_dir)
    out: list[FireMeta] = []
    for f in man["fires"]:
        out.append(FireMeta(
            id=f["id"],
            name=f["name"],
            bbox_wgs84=tuple(f["bbox"]),  # type: ignore[arg-type]
            start=f["start"],
            end=f["end"],
            ignition_lonlat=tuple(f["ignition"]),  # type: ignore[arg-type]
            reported_ha=float(f["reported_ha"]),
            notes=f.get("notes", ""),
            n_detections=int(f.get("n_detections", 0)),
            first_detection=f.get("first_detection"),
            last_detection=f.get("last_detection"),
        ))
    return out


def load_event(fire_id: str, data_dir: str | os.PathLike | None = None) -> FireEvent:
    """Load one :class:`FireEvent` by id (e.g. ``"yeongdeok_2025"``)."""
    d = find_data_dir(data_dir)
    if d is None:
        raise FileNotFoundError("FIRMS dataset not found; see find_data_dir().")
    metas = {m.id: m for m in list_fires(d)}
    if fire_id not in metas:
        raise KeyError(f"unknown fire id {fire_id!r}; have {sorted(metas)}")
    era5 = d / f"{fire_id}_era5.nc"
    has_era5 = era5.exists() and era5.stat().st_size > 0
    return FireEvent(meta=metas[fire_id], data_dir=d, has_era5=has_era5)


# ---------------------------------------------------------------------------
# ERA5 reader (CDS ships a zip of HDF5 NetCDFs)
# ---------------------------------------------------------------------------


def open_era5(path: str | os.PathLike):
    """Open a CDS ERA5 ``.nc`` (a zip of two HDF5 NetCDFs) as one xarray Dataset.

    Merges the ``instant`` stream (``u10, v10, t2m, d2m``) and the ``accum``
    stream (``tp``) on their shared ``valid_time/latitude/longitude`` grid.
    Returns ``None`` if the file is empty/missing (e.g. the 0-byte
    gangneung_donghae_2022 ERA5).
    """
    import xarray as xr

    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return None
    raw = path.read_bytes()
    # The bundle's ERA5 files are CDS zips (magic ``PK``); inner files are HDF5.
    if raw[:2] == b"PK":
        datasets = []
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for name in zf.namelist():
                if not name.endswith(".nc"):
                    continue
                ds = xr.open_dataset(io.BytesIO(zf.read(name)), engine="h5netcdf")
                datasets.append(ds)
        if not datasets:
            return None
        merged = xr.merge(datasets, compat="override", join="outer")
        return merged
    # Plain NetCDF fallback.
    try:
        return xr.open_dataset(path, engine="h5netcdf")
    except Exception:
        return xr.open_dataset(path)


__all__ = [
    "FireMeta",
    "FireEvent",
    "find_data_dir",
    "data_available",
    "load_manifest",
    "list_fires",
    "load_event",
    "burnable_map",
    "open_era5",
]
