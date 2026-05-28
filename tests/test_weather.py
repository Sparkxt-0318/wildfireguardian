"""Unit tests for the wind-data ingestion (Session 3)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from wildfireguardian.data_io.weather import (
    WindSample,
    WindSeries,
    load_aws_wind,
)
from wildfireguardian.utils.regions import (
    GOSEONG_2019,
    KOREA_PENINSULA,
    YEONGDEOK_2025,
)


# ---------------------------------------------------------------------------
# Real KMA path is correctly stubbed
# ---------------------------------------------------------------------------


def test_kma_source_raises_not_implemented_without_key() -> None:
    with pytest.raises(NotImplementedError, match="KMA Open API"):
        load_aws_wind(
            YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 23)),
            source="kma",
        )


def test_auto_source_falls_back_to_synthetic() -> None:
    series = load_aws_wind(
        YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 28)),
        source="auto",
    )
    assert series.synthetic is True
    assert "SYNTHETIC" in series.provenance


# ---------------------------------------------------------------------------
# Synthetic series shape
# ---------------------------------------------------------------------------


def test_yeongdeok_march_2025_series_has_168_hourly_samples() -> None:
    """7 days × 24 hours = 168 samples at hourly resolution."""
    series = load_aws_wind(
        YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 28)),
        source="synthetic_historical", step_hours=1.0,
    )
    assert series.n_samples() == 168
    start, end = series.date_range()
    assert start == datetime(2025, 3, 22, 0, 0)
    assert end == datetime(2025, 3, 28, 23, 0)


def test_yeongdeok_series_peak_during_documented_foehn_window() -> None:
    """Wind speeds during the reported peak Foehn window should be highest."""
    series = load_aws_wind(
        YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 28)),
        source="synthetic_historical",
    )
    peak = series.at(datetime(2025, 3, 22, 18, 0)).speed_10m_ms
    quiet = series.at(datetime(2025, 3, 28, 3, 0)).speed_10m_ms
    assert peak > 13.0, f"peak speed {peak:.1f} m/s too low for reported Foehn"
    assert quiet < 6.0, f"late-event speed {quiet:.1f} m/s too high"
    assert peak > quiet


def test_yeongdeok_series_direction_is_westerly_during_peak() -> None:
    """During the peak Foehn, direction should be near 270-290° (W/NW)."""
    series = load_aws_wind(
        YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 28)),
        source="synthetic_historical",
    )
    direction = series.at(datetime(2025, 3, 22, 18, 0)).direction_from_deg
    assert 260.0 <= direction <= 305.0, f"direction {direction}° not westerly"


def test_wind_speed_is_physically_plausible() -> None:
    """All synthetic speeds should fall in 0–30 m/s (no impossible storms)."""
    series = load_aws_wind(
        YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 28)),
        source="synthetic_historical",
    )
    for s in series.samples:
        assert 0.0 <= s.speed_10m_ms <= 30.0


def test_wind_direction_is_in_compass_range() -> None:
    series = load_aws_wind(
        YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 28)),
        source="synthetic_historical",
    )
    for s in series.samples:
        assert 0.0 <= s.direction_from_deg < 360.0


def test_midflame_conversion_applies_canopy_factor() -> None:
    """midflame = 10-m × canopy_factor; default 0.30 (Andrews 2012)."""
    series = load_aws_wind(
        YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 22)),
        source="synthetic_historical",
        canopy_reduction_factor=0.30,
    )
    s = series.at(datetime(2025, 3, 22, 14, 0))
    mf_speed, mf_dir = series.midflame_at(datetime(2025, 3, 22, 14, 0))
    assert mf_speed == pytest.approx(s.speed_10m_ms * 0.30, rel=1e-6)
    assert mf_dir == s.direction_from_deg


def test_custom_canopy_factor() -> None:
    series = load_aws_wind(
        YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 22)),
        source="synthetic_historical",
        canopy_reduction_factor=0.15,    # open canopy
    )
    s = series.at(datetime(2025, 3, 22, 14, 0))
    mf_speed, _ = series.midflame_at(datetime(2025, 3, 22, 14, 0))
    assert mf_speed == pytest.approx(s.speed_10m_ms * 0.15, rel=1e-6)


# ---------------------------------------------------------------------------
# Default series for other regions / date ranges
# ---------------------------------------------------------------------------


def test_default_series_for_non_yeongdeok_region() -> None:
    """For a region the synthetic-historical path doesn't know, we still
    return a defensible default series."""
    series = load_aws_wind(
        GOSEONG_2019, (date(2019, 4, 4), date(2019, 4, 5)),
        source="synthetic_historical",
    )
    assert series.synthetic is True
    assert "default" in series.provenance.lower() or "april" in series.provenance.lower() \
        or "SYNTHETIC" in series.provenance
    assert all(s.direction_from_deg == 270.0 for s in series.samples)


# ---------------------------------------------------------------------------
# at() helper
# ---------------------------------------------------------------------------


def test_at_returns_nearest_sample() -> None:
    series = load_aws_wind(
        YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 22)),
        source="synthetic_historical",
    )
    # Request 14:30, nearest hourly sample is 14:00 or 15:00.
    sample = series.at(datetime(2025, 3, 22, 14, 30))
    assert sample.timestamp.hour in (14, 15)


def test_date_range_validation() -> None:
    with pytest.raises(ValueError):
        load_aws_wind(
            YEONGDEOK_2025, (date(2025, 3, 28), date(2025, 3, 22)),
            source="synthetic_historical",
        )


def test_unknown_source_raises() -> None:
    with pytest.raises(ValueError):
        load_aws_wind(
            YEONGDEOK_2025, (date(2025, 3, 22), date(2025, 3, 23)),
            source="not_a_source",  # type: ignore[arg-type]
        )
