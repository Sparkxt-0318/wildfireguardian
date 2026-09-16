"""Local solar sunrise, sunset and day/night flag for Korean coordinates.

WHY THIS MODULE EXISTS (T1.5a)
-------------------------------
The KFS fire state-history file's sunrise and sunset columns report a single
NATIONAL value for the whole of South Korea, not a value local to the fire's
own latitude and longitude. Korea spans roughly 126 to 130 degrees east, so a
single national sunrise time is wrong by several minutes almost everywhere.
Never use those two raw columns for a day/night classification. Use this
module instead, computed from the fire's own coordinates.

**Empirically confirmed, not just asserted (T1.5f, round 2, 2026-09-16).**
The state-history file was not on disk when this module was written in
round 1, so the claim above was necessarily a documented assumption from
the task brief. It is now on disk, and
``research/shared/tests/test_solar.py::test_real_file_sunrise_sunset_is_a_single_national_value_per_date``
checks it directly: across 607 distinct 산불신고일 dates in the real file,
zero carry more than one distinct 일출시간 or 일몰시간 value, i.e. every row
on a given date reports the identical pair regardless of the fire's own
address. The reason this module exists is pinned by that test, not only by
this comment; the test skips cleanly if the raw file is absent (it is
git-ignored).

ROUTE TAKEN AND WHY
--------------------
The task instructs: use ``astral`` if available in the venv, else ``pvlib``,
else implement the NOAA solar position algorithm directly. Both ``astral``
and ``pvlib`` were checked with ``python -c "import astral"`` /
``import pvlib`` against ``/home/user/wildfireguardian/.auto/venv`` on
2026-09-16 and neither is installed, and this program runs on one laptop with
no network dependency at import time. So this module implements the NOAA
Solar Calculator's general solar position equations directly (the same
equations used by NOAA's ESRL spreadsheet calculator,
https://gml.noaa.gov/grad/solcalc/solareqns.PDF), in pure Python with the
standard library ``math`` module only. No third-party geoastronomy package is
required to run or test this module.

ACCURACY NOTE. The fractional-year term (``gamma``) is evaluated once per
calendar date at solar noon (hour = 12) rather than iteratively refined
against the sunrise/sunset time itself. This is the standard simplification
used by the NOAA ESRL spreadsheet and by most lightweight ports of it; the
resulting sunrise/sunset times are within about one to two minutes of a full
ephemeris (e.g. the values published by sunrise-sunset.org, which itself uses
the same 90.833 degree zenith convention). That is far smaller than the
minutes-of-longitude effect this module exists to capture, and is documented
here so nobody mistakes this for a research-grade ephemeris.

TIME ZONE CONVENTION (every function in this module)
------------------------------------------------------
All timestamps in and out of this module are KST (Korea Standard Time,
UTC+9, fixed). South Korea has not observed daylight saving time since 1988,
so the UTC+9 offset never changes across the calendar year. Every datetime
this module accepts or returns is a naive ``datetime.datetime`` understood
to already be in KST; this module never attaches a timezone object, and
never converts from or to any other zone. If a caller's timestamp is in UTC
or another zone, convert to KST before calling.

UNITS
-----
Latitude and longitude are decimal degrees, WGS84 (EPSG:4326), positive
north and positive east (South Korea: roughly lat 33 to 38.6, lon 124.5 to
131.9). This is a geographic-CRS convention distinct from the EPSG:5186
projected CRS used for distance and area elsewhere in this program (see
``research/shared/geo/crs.py``); solar geometry is computed directly from
geographic coordinates and never needs the projected CRS.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, time, timedelta

#: KST is a fixed UTC+9 offset. Korea has not observed daylight saving time
#: since 1988, so this constant is never seasonally adjusted.
KST_UTC_OFFSET_HOURS = 9.0

#: The solar zenith angle used for the standard "sunrise/sunset" definition,
#: 90.833 degrees, accounts for both atmospheric refraction (~34 arcmin) and
#: the sun's apparent radius (~16 arcmin), per the NOAA Solar Calculator and
#: the convention widely used by public sunrise/sunset calculators.
_SUNRISE_ZENITH_DEG = 90.833


def _fractional_year_gamma(day_of_year: int, hour: float, days_in_year: int) -> float:
    """NOAA's fractional-year angle gamma, in radians.

    ``hour`` is fixed at 12 (solar-noon proxy) by the public functions in this
    module; see the accuracy note in the module docstring for why that is an
    acceptable simplification here.
    """
    return (2.0 * math.pi / days_in_year) * (day_of_year - 1 + (hour - 12.0) / 24.0)


def _equation_of_time_minutes(gamma: float) -> float:
    """NOAA equation of time, in minutes (apparent minus mean solar time)."""
    return 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )


def _solar_declination_rad(gamma: float) -> float:
    """NOAA solar declination, in radians."""
    return (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )


def _hour_angle_sunrise_deg(lat_deg: float, decl_rad: float) -> float | None:
    """Half-day hour angle in degrees at the 90.833-degree sunrise zenith.

    Returns ``None`` for a polar day (sun never sets) or polar night (sun
    never rises). This never happens at Korean latitudes (roughly 33 to 38.6
    degrees north), but the guard is here so the function fails loudly
    instead of raising ``ValueError`` from ``math.acos`` on out-of-domain
    input, in case this module is ever reused outside Korea.
    """
    lat = math.radians(lat_deg)
    zenith = math.radians(_SUNRISE_ZENITH_DEG)
    cos_ha = (math.cos(zenith) / (math.cos(lat) * math.cos(decl_rad))) - math.tan(
        lat
    ) * math.tan(decl_rad)
    if cos_ha < -1.0 or cos_ha > 1.0:
        return None
    return math.degrees(math.acos(cos_ha))


@dataclass(frozen=True)
class SolarTimes:
    """Local solar sunrise and sunset for one date and one coordinate.

    ``sunrise`` and ``sunset`` are naive ``datetime.datetime`` values in KST
    (see the module docstring's time zone convention). ``polar`` is ``True``
    only if the sun never rises or never sets at this latitude on this date
    (never true within South Korea).
    """

    sunrise: datetime | None
    sunset: datetime | None
    polar: bool


def local_solar_times(lat: float, lon: float, on_date: date_cls) -> SolarTimes:
    """Local sunrise and sunset in KST for one calendar date and coordinate.

    Parameters
    ----------
    lat, lon:
        Decimal degrees, WGS84 (EPSG:4326), positive north / positive east.
    on_date:
        The calendar DATE in KST for which sunrise/sunset is computed (a
        ``datetime.date``, or a ``datetime.datetime`` whose ``.date()`` is
        used).

    Returns
    -------
    SolarTimes
        ``sunrise`` and ``sunset`` as naive KST datetimes on ``on_date``.

    Notes
    -----
    This is the LOCAL computation the KFS state-history file's national
    sunrise/sunset columns cannot provide (see module docstring). Two
    records on the same calendar date but different longitudes will get
    different sunrise/sunset times from this function, by design.
    """
    if isinstance(on_date, datetime):
        on_date = on_date.date()

    day_of_year = on_date.timetuple().tm_yday
    days_in_year = 366 if _is_leap(on_date.year) else 365

    gamma = _fractional_year_gamma(day_of_year, hour=12.0, days_in_year=days_in_year)
    eqtime_min = _equation_of_time_minutes(gamma)
    decl_rad = _solar_declination_rad(gamma)
    ha_deg = _hour_angle_sunrise_deg(lat, decl_rad)

    if ha_deg is None:
        return SolarTimes(sunrise=None, sunset=None, polar=True)

    # NOAA solar-noon-in-local-clock-minutes formula. `lon` is signed positive
    # east and `KST_UTC_OFFSET_HOURS` is signed positive east, which is the
    # sign convention this formula expects.
    solar_noon_min = 720.0 - 4.0 * lon - eqtime_min + 60.0 * KST_UTC_OFFSET_HOURS
    sunrise_min = solar_noon_min - 4.0 * ha_deg
    sunset_min = solar_noon_min + 4.0 * ha_deg

    midnight = datetime.combine(on_date, time(0, 0))
    sunrise = midnight + timedelta(minutes=sunrise_min)
    sunset = midnight + timedelta(minutes=sunset_min)
    return SolarTimes(sunrise=sunrise, sunset=sunset, polar=False)


def local_sunrise(lat: float, lon: float, on_date: date_cls) -> datetime | None:
    """Local sunrise in KST. See :func:`local_solar_times`. ``None`` if polar."""
    return local_solar_times(lat, lon, on_date).sunrise


def local_sunset(lat: float, lon: float, on_date: date_cls) -> datetime | None:
    """Local sunset in KST. See :func:`local_solar_times`. ``None`` if polar."""
    return local_solar_times(lat, lon, on_date).sunset


def is_daytime(lat: float, lon: float, when_kst: datetime) -> bool:
    """Day/night flag for one coordinate and one KST timestamp.

    ``when_kst`` must be a naive ``datetime.datetime`` already in KST (see
    the module docstring's time zone convention; this function does not
    inspect or convert any ``tzinfo``).

    Returns ``True`` when ``when_kst`` falls on or after local sunrise and
    strictly before local sunset on the same calendar date, computed from
    this coordinate's own longitude, never from the KFS file's national
    sunrise/sunset columns.
    """
    times = local_solar_times(lat, lon, when_kst.date())
    if times.polar or times.sunrise is None or times.sunset is None:
        # Not reached at Korean latitudes; treated conservatively as
        # "cannot determine" rather than guessing.
        raise ValueError(
            "polar day/night at this latitude: sunrise/sunset undefined; "
            "this should not occur within South Korea (lat 33-38.6N)"
        )
    return times.sunrise <= when_kst < times.sunset


def _is_leap(year: int) -> bool:
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
