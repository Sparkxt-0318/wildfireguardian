"""Weather data ingestion — KMA AWS and synthetic fallback for historical events.

This module provides time-indexed wind fields that the cellular
automaton can consume. The Korean Meteorological Administration (KMA)
operates a dense network of Automated Weather Stations (AWS) at ~10
minute / hourly resolution; the official archive is on data.kma.go.kr
and requires a registered API key.

For Session 3 we have **no KMA API credentials configured** — so the
real-data path :func:`load_aws_wind(source='kma')` raises
``NotImplementedError`` with clear instructions. The fallback path
:func:`load_aws_wind(source='synthetic_historical')` returns a
**clearly-labelled synthetic** time series reconstructed from PUBLIC
news and KMA press reporting of the March 22–28, 2025 Yeongdeok event.

Every record returned carries explicit ``synthetic=True`` and a
``provenance`` string. The validation harness must respect these
flags and label any downstream artefact accordingly.

Public-reporting sources used for the synthetic March 2025 series
----------------------------------------------------------------

- KMA press releases (March 2025) — 양강지풍 westerly/northwesterly
  Foehn wind episode; sustained 10-m winds 10–15 m/s; gusts to 25 m/s
  during 2025-03-22 14:00 KST through 2025-03-23 06:00 KST.
- Yonhap News, Chosun, Hankyoreh coverage (2025-03-23 to 2025-03-25)
  reported "강한 서풍" (strong westerly wind) decreasing after the
  third day.
- KMA AWS 영덕 station historical typical March wind regime — diurnal
  amplification with afternoon peak.

These are public-record qualitative descriptions, NOT the actual KMA
AWS time series. The numbers below are a defensible reconstruction
that captures the qualitative pattern; absolute values may be off by
10-30 %. **Do not present output of the synthetic path as KMA data.**
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

import numpy as np

from ..utils.regions import RegionConfig

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WindSeries record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WindSample:
    """One row of a wind time series."""

    timestamp: datetime
    speed_10m_ms: float            # 10-m wind speed, m/s
    direction_from_deg: float      # standard meteorological "wind FROM" bearing


@dataclass
class WindSeries:
    """Time series of wind observations or reconstructed values.

    Attributes
    ----------
    samples : list[WindSample]
        One per timestamp, sorted by time.
    canopy_reduction_factor : float
        Conversion factor from 10-m wind to midflame wind speed for the
        target fuel canopy. Andrews 2012 GTR-RMRS-266 gives ~ 0.3 for
        closed Pinus densiflora and similar conifer stands.
    synthetic : bool
        True iff the data is reconstructed / synthesised, not from real
        KMA AWS observations.
    provenance : str
        Free-text source description.
    region_name : str
        The :class:`RegionConfig`.name this series was built for.
    """

    samples: list[WindSample]
    canopy_reduction_factor: float = 0.30
    synthetic: bool = True
    provenance: str = ""
    region_name: str = ""

    # ----- access helpers -----

    def at(self, t: datetime) -> WindSample:
        """Return the nearest sample by time (no interpolation)."""
        if not self.samples:
            raise ValueError("empty WindSeries")
        return min(self.samples, key=lambda s: abs(s.timestamp - t))

    def midflame_at(self, t: datetime) -> tuple[float, float]:
        """Return (midflame_speed_ms, from_deg) for the nearest timestamp.

        The 10-m wind is multiplied by ``canopy_reduction_factor`` to
        obtain the midflame wind required by Rothermel.
        """
        s = self.at(t)
        return s.speed_10m_ms * self.canopy_reduction_factor, s.direction_from_deg

    def n_samples(self) -> int:
        return len(self.samples)

    def date_range(self) -> tuple[datetime, datetime]:
        if not self.samples:
            raise ValueError("empty WindSeries")
        return self.samples[0].timestamp, self.samples[-1].timestamp

    def to_arrays(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (timestamps as numpy datetime64, speed, direction) arrays."""
        ts = np.array([s.timestamp for s in self.samples], dtype="datetime64[ns]")
        sp = np.array([s.speed_10m_ms for s in self.samples], dtype=np.float64)
        dr = np.array([s.direction_from_deg for s in self.samples], dtype=np.float64)
        return ts, sp, dr


# ---------------------------------------------------------------------------
# Synthetic Yeongdeok March 2025 reconstruction
# ---------------------------------------------------------------------------


def _yeongdeok_march_2025_synthetic_series(
    start: datetime, end: datetime, step_hours: float = 1.0,
) -> list[WindSample]:
    """Hour-by-hour reconstruction of the March 22–28 2025 Yeongdeok wind regime.

    Pattern (PUBLIC-REPORTING-derived; NOT actual KMA observations):

    - Mean direction: 270° (from west), with NW excursions to 300° during
      the peak Foehn episode (Mar 22 14:00 to Mar 23 06:00 KST).
    - Sustained 10-m wind speed:
        * Mar 22 06–14: ramping up 5 → 12 m/s.
        * Mar 22 14 to Mar 23 06: peak sustained 12–15 m/s, gusts to 25.
        * Mar 23 06 to Mar 24 12: declining 12 → 6 m/s.
        * Mar 24 12 to Mar 28: residual 4–8 m/s with diurnal amplification.
    - Diurnal cycle: ±2 m/s amplitude, peak at 14:00 local time.
    """
    samples: list[WindSample] = []
    t = start
    step = timedelta(hours=step_hours)
    peak_start = datetime(2025, 3, 22, 14, 0)
    peak_end = datetime(2025, 3, 23, 6, 0)

    while t <= end:
        # Day-phase amplitude
        day_phase = (t - start).total_seconds() / 3600.0
        hour_of_day = t.hour + t.minute / 60.0

        # Base sustained speed (reconstructed envelope)
        if t < peak_start:
            # Ramp-up
            ramp = max(0.0, (t - start).total_seconds() / 3600.0) / max(
                1e-6, (peak_start - start).total_seconds() / 3600.0
            )
            base = 5.0 + ramp * 7.0   # 5 → 12 m/s
        elif t < peak_end:
            base = 13.5               # peak plateau
        elif t < datetime(2025, 3, 24, 12, 0):
            decline_frac = (
                (t - peak_end).total_seconds()
                / max(1.0, (datetime(2025, 3, 24, 12, 0) - peak_end).total_seconds())
            )
            base = 12.0 - decline_frac * 6.0   # 12 → 6
        else:
            base = 6.0

        # Diurnal cycle ±2 m/s, peak ~ 14 KST
        diurnal = 2.0 * math.cos(2.0 * math.pi * (hour_of_day - 14.0) / 24.0)
        speed = max(0.5, base + diurnal)

        # Direction: 270° baseline, NW excursion during peak Foehn
        if peak_start <= t <= peak_end:
            direction = 285.0    # northwesterly during peak
        else:
            direction = 270.0 + 5.0 * math.sin(2.0 * math.pi * day_phase / 24.0)

        samples.append(WindSample(
            timestamp=t,
            speed_10m_ms=float(speed),
            direction_from_deg=float(direction),
        ))
        t += step

    return samples


WindSource = Literal["auto", "kma", "synthetic_historical"]


def load_aws_wind(
    region: RegionConfig,
    date_range: tuple[date, date] | tuple[datetime, datetime],
    *,
    source: WindSource = "auto",
    step_hours: float = 1.0,
    canopy_reduction_factor: float = 0.30,
) -> WindSeries:
    """Load a time series of AWS wind for a region + date range.

    Parameters
    ----------
    region : RegionConfig
        Used for region.name tagging and (in future KMA-API path) AWS-station
        selection.
    date_range : (start, end)
        Inclusive date or datetime range. If date is passed, start = 00:00,
        end = 23:00 of the respective day.
    source : str
        - ``"kma"``: real KMA Open API (raises NotImplementedError if no key).
        - ``"synthetic_historical"``: reconstructed from public reporting.
          Returns the labelled-synthetic series.
        - ``"auto"``: tries ``kma`` then falls back to
          ``synthetic_historical``.
    step_hours : float
        Sample interval, hours. Default 1.
    canopy_reduction_factor : float
        10-m → midflame conversion factor (Andrews 2012).

    Returns
    -------
    WindSeries
        Tagged with ``synthetic`` and ``provenance``.
    """
    start, end = _normalise_date_range(date_range)

    if source == "auto":
        try:
            return load_aws_wind(
                region, (start, end), source="kma",
                step_hours=step_hours,
                canopy_reduction_factor=canopy_reduction_factor,
            )
        except NotImplementedError:
            return load_aws_wind(
                region, (start, end), source="synthetic_historical",
                step_hours=step_hours,
                canopy_reduction_factor=canopy_reduction_factor,
            )

    if source == "kma":
        raise NotImplementedError(
            "KMA Open API ingestion is not yet wired (Session 3 has no KMA "
            "API key configured). Register at https://data.kma.go.kr/, set "
            "the WILDFIREGUARDIAN_KMA_API_KEY env var, then implement the "
            "HourlyObservation endpoint here. See docs/data_sources.md."
        )

    if source == "synthetic_historical":
        # Use the documented March 2025 reconstruction. For other dates we
        # interpolate from a sensible default (10 m/s westerly), labelled
        # synthetic regardless.
        if region.name == "yeongdeok_2025" and start >= datetime(2025, 3, 22) \
                and end <= datetime(2025, 3, 28, 23, 59):
            samples = _yeongdeok_march_2025_synthetic_series(start, end, step_hours)
            provenance = (
                "SYNTHETIC — March 2025 Yeongdeok event reconstruction "
                "from PUBLIC KMA press release + Yonhap/Chosun/Hankyoreh "
                "coverage. Captures 양강지풍 12-15 m/s westerly sustained "
                "with peak 14:00 Mar 22 KST. Not actual KMA AWS data."
            )
        else:
            samples = _default_westerly_series(start, end, step_hours)
            provenance = (
                "SYNTHETIC — default 10 m/s westerly diurnal envelope. "
                "Not derived from any real observation. For pipeline "
                "exercises only."
            )

        return WindSeries(
            samples=samples,
            canopy_reduction_factor=canopy_reduction_factor,
            synthetic=True,
            provenance=provenance,
            region_name=region.name,
        )

    raise ValueError(f"unknown wind source {source!r}")


def _normalise_date_range(
    rng: tuple[date, date] | tuple[datetime, datetime],
) -> tuple[datetime, datetime]:
    s, e = rng
    if isinstance(s, datetime):
        start = s
    else:
        start = datetime(s.year, s.month, s.day, 0, 0)
    if isinstance(e, datetime):
        end = e
    else:
        end = datetime(e.year, e.month, e.day, 23, 0)
    if end < start:
        raise ValueError(f"date range start {start} > end {end}")
    return start, end


def _default_westerly_series(
    start: datetime, end: datetime, step_hours: float,
) -> list[WindSample]:
    """Generic 10 m/s westerly diurnal envelope for unsupported regions."""
    samples: list[WindSample] = []
    t = start
    step = timedelta(hours=step_hours)
    while t <= end:
        hour_of_day = t.hour + t.minute / 60.0
        diurnal = 2.0 * math.cos(2.0 * math.pi * (hour_of_day - 14.0) / 24.0)
        speed = max(2.0, 10.0 + diurnal)
        samples.append(WindSample(
            timestamp=t,
            speed_10m_ms=float(speed),
            direction_from_deg=270.0,
        ))
        t += step
    return samples


__all__ = [
    "WindSample",
    "WindSeries",
    "WindSource",
    "load_aws_wind",
]
