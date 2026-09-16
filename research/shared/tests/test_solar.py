"""Tests for research/shared/geo/solar.py (T1.5a).

Reference sunrise/sunset pairs below were retrieved 2026-09-16 from the
sunrise-sunset.org API (https://api.sunrise-sunset.org/json,
zenith = 90.833 degrees, the same convention this module implements), e.g.::

    curl "https://api.sunrise-sunset.org/json?lat=37.4563&lng=126.7052&date=2025-06-21&formatted=0"

with the returned UTC times converted to KST (UTC+9). These are the "known
Korean sunrise/sunset pairs" the task requires: two locations at separated
longitudes (Incheon, west coast; Gangneung, east coast), each at a summer and
a winter date.

Tolerance is 5 minutes: this module's :func:`_fractional_year_gamma`
evaluates the NOAA fractional-year term once per date at solar noon rather
than iterating to the sunrise/sunset instant itself (documented in
solar.py's accuracy note), which costs one to three minutes of agreement
against a full ephemeris. That is far smaller than the 8-10 minute
east-west effect this module exists to capture, so 5 minutes is generous
enough to catch a real bug while tolerating the documented approximation.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from research.shared.geo.solar import (
    KST_UTC_OFFSET_HOURS,
    is_daytime,
    local_solar_times,
    local_sunrise,
    local_sunset,
)

#: raw data is git-ignored (see research/data/REGISTRY.yaml); this file only
#: exists in an environment that fetched it (A1, round 2, 2026-09-16).
REAL_STATE_HISTORY_CSV = (
    Path(__file__).resolve().parents[3]
    / "research"
    / "data"
    / "raw"
    / "kfs_fire_state_history_csv"
    / "산불상태별이력_2025.11.10.csv"
)

INCHEON = (37.4563, 126.7052)
GANGNEUNG = (37.7519, 128.8761)

TOLERANCE_MIN = 5

# (location, date, expected sunrise KST "HH:MM:SS", expected sunset KST "HH:MM:SS")
KNOWN_PAIRS = [
    ("incheon_summer", INCHEON, date(2025, 6, 21), "05:10:59", "19:58:58"),
    ("incheon_winter", INCHEON, date(2025, 12, 21), "07:42:22", "17:20:00"),
    ("gangneung_summer", GANGNEUNG, date(2025, 6, 21), "05:01:23", "19:51:11"),
    ("gangneung_winter", GANGNEUNG, date(2025, 12, 21), "07:34:31", "17:10:29"),
]


def _minutes_from_midnight(hhmmss: str) -> float:
    h, m, s = (int(x) for x in hhmmss.split(":"))
    return h * 60 + m + s / 60.0


def _minutes_diff(dt: datetime, hhmmss_expected: str) -> float:
    got = dt.hour * 60 + dt.minute + dt.second / 60.0
    return got - _minutes_from_midnight(hhmmss_expected)


@pytest.mark.parametrize("name,coord,on_date,exp_sunrise,exp_sunset", KNOWN_PAIRS)
def test_known_pairs_within_tolerance(name, coord, on_date, exp_sunrise, exp_sunset):
    lat, lon = coord
    times = local_solar_times(lat, lon, on_date)
    assert times.sunrise is not None and times.sunset is not None
    assert abs(_minutes_diff(times.sunrise, exp_sunrise)) <= TOLERANCE_MIN, (
        f"{name} sunrise off by more than {TOLERANCE_MIN} min: "
        f"got {times.sunrise.time()}, expected ~{exp_sunrise}"
    )
    assert abs(_minutes_diff(times.sunset, exp_sunset)) <= TOLERANCE_MIN, (
        f"{name} sunset off by more than {TOLERANCE_MIN} min: "
        f"got {times.sunset.time()}, expected ~{exp_sunset}"
    )


@pytest.mark.parametrize("on_date", [date(2025, 6, 21), date(2025, 12, 21)])
def test_east_west_sign_and_magnitude(on_date):
    """Gangneung (east) sees sunrise and sunset earlier, in KST clock time,
    than Incheon (west), on the same calendar date. This is the signature
    effect T1.5a exists to capture: a single national sunrise/sunset value
    cannot represent both locations correctly on the same day.
    """
    inc = local_solar_times(*INCHEON, on_date)
    gan = local_solar_times(*GANGNEUNG, on_date)

    sunrise_diff_min = (gan.sunrise - inc.sunrise).total_seconds() / 60.0
    sunset_diff_min = (gan.sunset - inc.sunset).total_seconds() / 60.0

    # Sign: east (Gangneung) is earlier, so the difference is negative.
    assert sunrise_diff_min < 0
    assert sunset_diff_min < 0

    # Magnitude: ~2.17 degrees of longitude separation * 4 min/degree =~ 8.7
    # minutes. Allow a wide band (5-15 min) since latitude also differs
    # slightly between the two cities.
    assert 5.0 <= abs(sunrise_diff_min) <= 15.0
    assert 5.0 <= abs(sunset_diff_min) <= 15.0


def test_same_national_value_would_be_wrong():
    """Directly demonstrates why the KFS national sunrise/sunset columns are
    unusable: two Korean coordinates on the same date disagree by minutes.
    """
    d = date(2025, 6, 21)
    inc_sunrise = local_sunrise(*INCHEON, d)
    gan_sunrise = local_sunrise(*GANGNEUNG, d)
    assert inc_sunrise != gan_sunrise
    assert abs((inc_sunrise - gan_sunrise).total_seconds()) > 60  # more than a minute apart


def test_sunset_after_sunrise():
    for lat, lon in (INCHEON, GANGNEUNG):
        for d in (date(2025, 6, 21), date(2025, 12, 21), date(2025, 3, 20)):
            times = local_solar_times(lat, lon, d)
            assert times.sunset > times.sunrise


def test_is_daytime_flag():
    lat, lon = INCHEON
    d = date(2025, 6, 21)
    sunrise = local_sunrise(lat, lon, d)
    sunset = local_sunset(lat, lon, d)

    before_dawn = sunrise - timedelta(hours=1)
    midday = sunrise + (sunset - sunrise) / 2
    after_dusk = sunset + timedelta(hours=1)

    assert is_daytime(lat, lon, before_dawn) is False
    assert is_daytime(lat, lon, midday) is True
    assert is_daytime(lat, lon, after_dusk) is False
    # Boundary: exactly at sunrise counts as day; exactly at sunset does not
    # (half-open interval [sunrise, sunset)), documented in solar.py.
    assert is_daytime(lat, lon, sunrise) is True
    assert is_daytime(lat, lon, sunset) is False


def test_kst_offset_is_fixed_utc9():
    """Documents and locks the no-DST convention every function relies on."""
    assert KST_UTC_OFFSET_HOURS == 9.0


def test_local_solar_times_accepts_datetime_or_date():
    lat, lon = INCHEON
    from_date = local_solar_times(lat, lon, date(2025, 6, 21))
    from_datetime = local_solar_times(lat, lon, datetime(2025, 6, 21, 15, 30))
    assert from_date.sunrise == from_datetime.sunrise
    assert from_date.sunset == from_datetime.sunset


def test_real_file_sunrise_sunset_is_a_single_national_value_per_date():
    """T1.5f: pins WHY THIS MODULE EXISTS by a test, not just by the module
    docstring's comment. The KFS state-history file's 일출시간/일몰시간
    columns report ONE value per calendar date for the whole of South Korea,
    never a value local to a fire's own address; that is exactly the gap
    this module (local computation from lat/lon) exists to fill. Confirmed
    empirically against the real file (round 2, 2026-09-16): across 607
    distinct 산불신고일 dates, zero carry more than one distinct 일출시간 or
    일몰시간 value. Skips cleanly if the file is absent, since raw data is
    git-ignored (research/data/REGISTRY.yaml).
    """
    if not REAL_STATE_HISTORY_CSV.exists():
        pytest.skip(
            "kfs_fire_state_history_csv raw file not present in this "
            "environment (raw data is git-ignored)"
        )

    pd = pytest.importorskip("pandas")

    df = pd.read_csv(REAL_STATE_HISTORY_CSV, encoding="cp949")
    # Defensive: this file's real header row carries trailing whitespace on
    # every column name (see research/shared/qc/timestamps.py).
    df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]

    report_date = pd.to_datetime(df["산불신고일"], errors="coerce").dt.date
    by_date = df.groupby(report_date)[["일출시간", "일몰시간"]].nunique()

    # Guard against a vacuous pass (e.g. an empty or truncated file).
    assert len(by_date) > 0

    multi_value_dates = by_date[(by_date["일출시간"] > 1) | (by_date["일몰시간"] > 1)]
    assert len(multi_value_dates) == 0, (
        f"{len(multi_value_dates)} date(s) carry more than one distinct "
        "일출시간 or 일몰시간 value; this would contradict the 'single "
        "national value per day' premise this module exists to work "
        "around, and must be reported, not silently kept."
    )
