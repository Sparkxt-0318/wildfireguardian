"""ECMWF ERA5 weather ingestion + derived fire-weather features.

ERA5 single-level hourly reanalysis as delivered by the Copernicus CDS is a
**zip-wrapped pair** of netCDF files:

- ``data_stream-oper_stepType-instant.nc`` — instantaneous: ``u10``, ``v10``
  (10 m wind components, m/s), ``t2m`` (2 m temperature, K), ``d2m`` (2 m
  dew-point, K).
- ``data_stream-oper_stepType-accum.nc`` — accumulated: ``tp`` (total
  precipitation, m, over the hour ending at ``valid_time``).

Both share a ``valid_time`` coordinate and a coarse (~0.25° ≈ 31 km) 2×2
lat/lon footprint over each fire's bbox. We unzip, merge on ``valid_time``,
and derive:

- ``wind_speed`` = |(u10, v10)|
- ``wind_direction`` = meteorological FROM-bearing (deg, 0 = N, clockwise)
- wind *toward* unit vector (east, north) — for the downwind alignment features
- ``temperature`` (°C), ``relative_humidity`` (%) via the Magnus formula
- ``days_since_rain`` — hours since the last hour with tp ≥ 0.1 mm, /24

The 31 km coarseness means the field is nearly spatially uniform across a
single fire; we still bilinearly interpolate to each cell (clamped to the node
box) to honour the small gradient. This coarseness is a documented limitation.
"""

from __future__ import annotations

import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from .dataset import FireData

RAIN_THRESHOLD_M: float = 1e-4  # 0.1 mm/hr counts as "rain"


def _open_era5_zip(path: Path) -> xr.Dataset:
    """Unzip a CDS ERA5 archive and merge the instant + accum streams."""
    with zipfile.ZipFile(path) as z, tempfile.TemporaryDirectory() as td:
        members = z.namelist()
        z.extractall(td)
        parts = [
            xr.open_dataset(Path(td) / m, engine="netcdf4").load()
            for m in members
            if m.endswith(".nc")
        ]
    merged = xr.merge(parts, compat="override", join="outer")
    # Normalise the time coordinate name to ``valid_time``.
    if "valid_time" not in merged.coords and "time" in merged.coords:
        merged = merged.rename({"time": "valid_time"})
    return merged


@dataclass
class WeatherSeries:
    """Merged ERA5 fields + derived series for one fire."""

    fire_id: str
    times: np.ndarray             # datetime64[ns], length T
    lats: np.ndarray              # node latitudes
    lons: np.ndarray              # node longitudes
    ds: xr.Dataset                # merged dataset (u10,v10,t2m,d2m,tp)
    days_since_rain: np.ndarray   # length T, days since last rainy hour (spatial mean)

    @classmethod
    def from_fire(cls, fire: FireData) -> "WeatherSeries | None":
        if not fire.has_era5:
            return None
        ds = _open_era5_zip(fire.era5_nc)
        times = ds["valid_time"].values
        lats = ds["latitude"].values
        lons = ds["longitude"].values
        # days_since_rain from the spatial-mean precip series (31 km ~ uniform).
        tp = ds["tp"].mean(dim=("latitude", "longitude")).values
        dsr = _days_since_rain(times, tp)
        return cls(fire.fire_id, times, lats, lons, ds, dsr)

    def _nearest_time_index(self, t: pd.Timestamp) -> int:
        return int(np.argmin(np.abs(self.times - np.datetime64(t))))

    def sample(self, t: pd.Timestamp, lon: np.ndarray, lat: np.ndarray) -> dict:
        """Bilinearly sample derived weather at one time for arrays of (lon, lat).

        Coordinates are clamped to the ERA5 node box before interpolation
        (the 31 km footprint can be narrower than the fire bbox).
        """
        ti = self._nearest_time_index(t)
        snap = self.ds.isel(valid_time=ti)
        lo = np.clip(np.asarray(lon), float(self.lons.min()), float(self.lons.max()))
        la = np.clip(np.asarray(lat), float(self.lats.min()), float(self.lats.max()))
        xlo = xr.DataArray(lo.ravel(), dims="pt")
        xla = xr.DataArray(la.ravel(), dims="pt")
        interp = snap.interp(longitude=xlo, latitude=xla, method="linear")

        u = interp["u10"].values
        v = interp["v10"].values
        t2m = interp["t2m"].values
        d2m = interp["d2m"].values

        speed = np.hypot(u, v)
        # Meteorological FROM-bearing: wind blowing toward atan2(u, v); FROM = +180.
        toward_deg = np.degrees(np.arctan2(u, v))
        from_deg = (toward_deg + 180.0) % 360.0
        # Toward unit vector in (east, north) = (5179 +x, +y) axes.
        norm = np.where(speed > 1e-6, speed, 1.0)
        toward_e = u / norm
        toward_n = v / norm

        temp_c = t2m - 273.15
        rh = _relative_humidity(t2m, d2m)

        return {
            "wind_speed": speed.reshape(np.asarray(lon).shape),
            "wind_direction": from_deg.reshape(np.asarray(lon).shape),
            "wind_toward_e": toward_e.reshape(np.asarray(lon).shape),
            "wind_toward_n": toward_n.reshape(np.asarray(lon).shape),
            "temperature": temp_c.reshape(np.asarray(lon).shape),
            "relative_humidity": rh.reshape(np.asarray(lon).shape),
            "days_since_rain": float(self.days_since_rain[ti]),
        }

    def status(self) -> dict:
        return {
            "n_timesteps": int(self.times.size),
            "time_start": str(np.datetime_as_string(self.times.min(), unit="h")),
            "time_end": str(np.datetime_as_string(self.times.max(), unit="h")),
            "n_lat": int(self.lats.size),
            "n_lon": int(self.lons.size),
        }


def _relative_humidity(t2m_k: np.ndarray, d2m_k: np.ndarray) -> np.ndarray:
    """RH (%) from temperature and dew-point (K) via the Magnus formula.

    e/es = exp[ (a·Td)/(b+Td) - (a·T)/(b+T) ], a=17.625, b=243.04 (°C).
    """
    a, b = 17.625, 243.04
    t = t2m_k - 273.15
    td = d2m_k - 273.15
    rh = 100.0 * np.exp((a * td) / (b + td) - (a * t) / (b + t))
    return np.clip(rh, 0.0, 100.0)


def _days_since_rain(times: np.ndarray, tp: np.ndarray) -> np.ndarray:
    """Days since the most recent hour with tp ≥ threshold, per timestep.

    Before any rain in the record, counts hours since the series start (a lower
    bound, flagged implicitly by being monotone from 0). Hourly cadence assumed.
    """
    out = np.empty(times.size, dtype=np.float64)
    last_rain_idx = None
    for i in range(times.size):
        if np.isfinite(tp[i]) and tp[i] >= RAIN_THRESHOLD_M:
            last_rain_idx = i
        if last_rain_idx is None:
            hours = i  # hours since record start (no rain yet observed)
        else:
            hours = (times[i] - times[last_rain_idx]) / np.timedelta64(1, "h")
        out[i] = float(hours) / 24.0
    return out


__all__ = ["WeatherSeries", "RAIN_THRESHOLD_M"]
