"""ERA5 → fire-weather-severity features for the spread_v2 ignition model.

This module derives the fire-weather variables (dryness, humidity,
temperature, wind speed) from raw ERA5 fields, plus the wind vector that
lets the feature builder compute the ``wind_alignment`` control.

⚠ An earlier version of this docstring called "severity ≫ direction" THE
CRITICAL FINDING shaping the routing project. That conclusion is WITHDRAWN
as not established (docs/MODEL_CARD.md, permutation-importance section):
the measured importance ratio is real; the reading of it was not supported.

Derived per time step from ERA5 ``u10, v10, t2m, d2m, tp``:

- ``wind_speed_ms``   = ``hypot(u10, v10)``
- ``wind_toward_deg`` = compass bearing the wind blows *toward*
- ``wind_u, wind_v``  = unit vector the wind blows toward (for alignment)
- ``temp_c``          = ``t2m - 273.15``
- ``rh_pct``          = relative humidity from t2m/d2m (Magnus / Tetens)
- ``vpd_kpa``         = vapour-pressure deficit (a strong dryness proxy)
- ``days_since_rain`` = days since the last 3-h step with >1 mm precip
- ``dry_run_mm``      = precipitation accumulated in a trailing 24 h window

All formulae are standard meteorology; see Alduchov & Eskridge (1996) for the
improved Magnus coefficients used here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# Improved Magnus-Tetens coefficients (Alduchov & Eskridge 1996), over water.
_MAGNUS_A = 17.625
_MAGNUS_B = 243.04  # deg C
_RAIN_STEP_THRESHOLD_M = 0.001  # 1 mm in a step counts as "it rained"


def _sat_vapour_pressure_hpa(temp_c: np.ndarray) -> np.ndarray:
    """Saturation vapour pressure (hPa) via the improved Magnus formula."""
    return 6.1094 * np.exp(_MAGNUS_A * temp_c / (_MAGNUS_B + temp_c))


def relative_humidity_pct(t2m_k: np.ndarray, d2m_k: np.ndarray) -> np.ndarray:
    """RH (%) from 2 m temperature and dewpoint (both Kelvin)."""
    tc = np.asarray(t2m_k) - 273.15
    tdc = np.asarray(d2m_k) - 273.15
    rh = 100.0 * _sat_vapour_pressure_hpa(tdc) / _sat_vapour_pressure_hpa(tc)
    return np.clip(rh, 0.0, 100.0)


def vpd_kpa(t2m_k: np.ndarray, d2m_k: np.ndarray) -> np.ndarray:
    """Vapour-pressure deficit (kPa) from 2 m temperature and dewpoint (K)."""
    tc = np.asarray(t2m_k) - 273.15
    tdc = np.asarray(d2m_k) - 273.15
    es = _sat_vapour_pressure_hpa(tc)
    ea = _sat_vapour_pressure_hpa(tdc)
    return np.clip((es - ea) / 10.0, 0.0, None)  # hPa → kPa


@dataclass
class WeatherSeries:
    """Domain-mean ERA5 severity time series for one fire.

    All arrays are aligned to ``time`` (tz-aware UTC). Spatial structure is
    dropped: at ERA5's 0.25 deg resolution a single Korean fire spans ~1-3
    grid cells, so the domain mean is the honest resolution of the signal.
    """

    time: pd.DatetimeIndex
    wind_speed_ms: np.ndarray
    wind_toward_deg: np.ndarray
    wind_u: np.ndarray            # unit vector (east) the wind blows toward
    wind_v: np.ndarray            # unit vector (north) the wind blows toward
    temp_c: np.ndarray
    rh_pct: np.ndarray
    vpd_kpa: np.ndarray
    days_since_rain: np.ndarray
    precip_24h_mm: np.ndarray

    def at(self, when: pd.Timestamp) -> dict[str, float]:
        """Severity features at the time step nearest ``when``."""
        when = pd.Timestamp(when)
        if when.tzinfo is None:
            when = when.tz_localize("UTC")
        idx = int(np.argmin(np.abs(self.time.view("int64") - when.value)))
        return {
            "wind_speed_ms": float(self.wind_speed_ms[idx]),
            "wind_toward_deg": float(self.wind_toward_deg[idx]),
            "wind_u": float(self.wind_u[idx]),
            "wind_v": float(self.wind_v[idx]),
            "temp_c": float(self.temp_c[idx]),
            "rh_pct": float(self.rh_pct[idx]),
            "vpd_kpa": float(self.vpd_kpa[idx]),
            "days_since_rain": float(self.days_since_rain[idx]),
            "precip_24h_mm": float(self.precip_24h_mm[idx]),
        }


def _days_since_rain(time: pd.DatetimeIndex, tp_m: np.ndarray) -> np.ndarray:
    """Days since the last step whose precipitation exceeded the threshold.

    Causal: only past/current steps are considered. Before any wet step the
    value grows from the series start (a lower bound on true dryness, since
    ERA5 here begins at the fire window — flagged in the report).
    """
    out = np.zeros(len(time), dtype=float)
    last_wet_t: pd.Timestamp | None = None
    t0 = time[0]
    for i, t in enumerate(time):
        if tp_m[i] is not None and np.isfinite(tp_m[i]) and tp_m[i] >= _RAIN_STEP_THRESHOLD_M:
            last_wet_t = t
        ref = last_wet_t if last_wet_t is not None else t0
        out[i] = (t - ref).total_seconds() / 86400.0
    return out


def _precip_24h(time: pd.DatetimeIndex, tp_m: np.ndarray) -> np.ndarray:
    """Trailing-24 h accumulated precipitation (mm) at each step."""
    tp_mm = np.where(np.isfinite(tp_m), tp_m, 0.0) * 1000.0
    out = np.zeros(len(time), dtype=float)
    secs = time.view("int64") / 1e9
    for i in range(len(time)):
        lo = secs[i] - 24 * 3600
        mask = (secs <= secs[i]) & (secs >= lo)
        out[i] = float(tp_mm[mask].sum())
    return out


def weather_series_from_event(event) -> WeatherSeries | None:
    """Build a :class:`WeatherSeries` from a :class:`FireEvent`'s ERA5 file.

    Returns ``None`` if the event has no usable ERA5 (e.g. the 0-byte
    gangneung_donghae_2022 file) — callers should drop weather-dependent
    rows for that fire and note it.
    """
    from .data import open_era5

    if not event.has_era5:
        return None
    ds = open_era5(event.era5_path)
    if ds is None:
        return None
    try:
        # Domain mean over lat/lon; squeeze any singleton coords.
        spatial = [d for d in ("latitude", "longitude") if d in ds.dims]
        m = ds.mean(dim=spatial) if spatial else ds
        time = pd.to_datetime(np.asarray(m["valid_time"].values), utc=True)

        def col(name: str) -> np.ndarray:
            if name not in m:
                return np.full(len(time), np.nan)
            return np.asarray(m[name].values, dtype=float).reshape(len(time))

        u10, v10 = col("u10"), col("v10")
        t2m, d2m = col("t2m"), col("d2m")
        tp = col("tp")
    finally:
        ds.close()

    speed = np.hypot(u10, v10)
    safe = np.where(speed > 1e-6, speed, 1.0)
    wu, wv = u10 / safe, v10 / safe  # unit vector the wind blows toward
    toward_deg = (np.degrees(np.arctan2(u10, v10)) + 360.0) % 360.0

    order = np.argsort(time.values)
    time = time[order]
    return WeatherSeries(
        time=time,
        wind_speed_ms=speed[order],
        wind_toward_deg=toward_deg[order],
        wind_u=wu[order],
        wind_v=wv[order],
        temp_c=(t2m[order] - 273.15),
        rh_pct=relative_humidity_pct(t2m, d2m)[order],
        vpd_kpa=vpd_kpa(t2m, d2m)[order],
        days_since_rain=_days_since_rain(time, tp[order]),
        precip_24h_mm=_precip_24h(time, tp[order]),
    )


__all__ = [
    "WeatherSeries",
    "weather_series_from_event",
    "relative_humidity_pct",
    "vpd_kpa",
]
