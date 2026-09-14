"""F1's freeze, and the resolution trap it must not inherit (Part B, 2026-09-14).

``scripts/run_forecast_track_f1.py`` builds the forecast-track field by holding the ERA5
values at the LAST TIME AT OR BEFORE T0. That one function is the entire difference
between F1 and the committed hindcast, so it is the one function worth a gate: if it picks
a sample after T0, F1 is a hindcast wearing a different filename and the whole entrant is
void without anything looking wrong.

⚠ WHY THE RESOLUTION CASES ARE HERE. ``WeatherSeries.at`` resolves a time with
``self.time.view("int64") - when.value``. That is correct ONLY when the index resolution is
nanoseconds. Under the pinned pandas 3.0.5 a ``datetime64[us]`` or ``[s]`` index yields
ints 1e3 / 1e9 times smaller than ``Timestamp.value``, so every comparison goes the same
way and the lookup silently returns the LAST sample in the series. A freeze built on that
idiom returned index 23 of 24 for a T0 at 10:30 -- the far end of the window, hours after
T0 -- and it did so silently. These cases exist so F1 can never acquire that bug, at any
resolution a netCDF might carry.

This file does NOT assert anything about ``WeatherSeries.at`` itself or about any committed
field: whether the real ERA5 files are nanosecond-resolution is not knowable from a clone
without the git-ignored bundle, and changing ``weather.py`` could move registered numbers.
That is escalated in docs/auto/NEEDS_HUMAN.md, not decided here.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.spread_v2.weather import WeatherSeries  # noqa: E402

FIELDS = ("wind_speed_ms", "wind_toward_deg", "wind_u", "wind_v", "temp_c",
          "rh_pct", "vpd_kpa", "days_since_rain", "precip_24h_mm")
RESOLUTIONS = ("ns", "us", "s")


@pytest.fixture(scope="module")
def f1():
    spec = importlib.util.spec_from_file_location(
        "f1_mod", REPO / "scripts" / "run_forecast_track_f1.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _series(resolution: str, n: int = 24) -> WeatherSeries:
    """A series whose value at hour *i* IS *i*, so a wrong pick is a readable number."""
    arr = np.array([np.datetime64("2025-03-25T00:00:00") + np.timedelta64(i, "h")
                    for i in range(n)], dtype=f"datetime64[{resolution}]")
    idx = pd.to_datetime(arr, utc=True)
    v = np.arange(n, dtype=float)
    return WeatherSeries(time=idx, **{f: v.copy() for f in FIELDS})


@pytest.mark.parametrize("resolution", RESOLUTIONS)
def test_the_freeze_takes_the_last_sample_at_or_before_t0(f1, resolution):
    """T0 at 10:30 must freeze hour 10 — never hour 11, which an operator cannot see."""
    ws = _series(resolution)
    _, idx, held, _ = f1.freeze_at_t0(ws, pd.Timestamp("2025-03-25T10:30:00Z"))
    assert idx == 10, (
        f"[{resolution}] the freeze took index {idx}, not the last sample at or before T0. "
        "Index 23 means the int64 resolution trap described in this module's docstring."
    )
    assert all(held[f] == 10.0 for f in FIELDS)


@pytest.mark.parametrize("resolution", RESOLUTIONS)
def test_no_lookup_can_reach_past_t0(f1, resolution):
    """The property the entrant rests on, probed across the whole 12 h horizon."""
    ws = _series(resolution)
    t0 = pd.Timestamp("2025-03-25T10:30:00Z")
    frozen, _, held, _ = f1.freeze_at_t0(ws, t0)
    for lead_h in (0, 1, 3, 6, 9, 12, 23):
        got = frozen.at(t0 + pd.Timedelta(hours=lead_h))
        assert all(got[f] == held[f] for f in FIELDS), (
            f"[{resolution}] the freeze leaked at +{lead_h} h: {got['temp_c']} != {held['temp_c']}. "
            "F1 would be reading weather that had not happened at T0 — the exact defect "
            "docs/forecast_track.md exists to remove."
        )


@pytest.mark.parametrize("resolution", RESOLUTIONS)
def test_a_t0_that_lands_exactly_on_a_sample_takes_that_sample(f1, resolution):
    ws = _series(resolution)
    _, idx, held, _ = f1.freeze_at_t0(ws, pd.Timestamp("2025-03-25T05:00:00Z"))
    assert idx == 5 and held["temp_c"] == 5.0


@pytest.mark.parametrize("resolution", RESOLUTIONS)
def test_a_t0_before_the_series_refuses_rather_than_taking_the_nearest(f1, resolution):
    """The refusal matters more than it looks: the nearest sample is the forbidden one."""
    ws = _series(resolution)
    with pytest.raises(SystemExit) as exc:
        f1.freeze_at_t0(ws, pd.Timestamp("2025-03-24T00:00:00Z"))
    assert "at or before T0" in str(exc.value)


def test_the_frozen_series_keeps_its_time_index(f1):
    """The freeze replaces VALUES, not the window: the object still says where it came from."""
    ws = _series("ns")
    frozen, _, _, _ = f1.freeze_at_t0(ws, pd.Timestamp("2025-03-25T10:30:00Z"))
    assert list(frozen.time) == list(ws.time)


def test_every_weather_field_is_frozen_and_none_is_left_live(f1):
    """A field left unfrozen would be a post-T0 leak through one variable only."""
    ws = _series("ns")
    frozen, _, held, _ = f1.freeze_at_t0(ws, pd.Timestamp("2025-03-25T10:30:00Z"))
    for f in FIELDS:
        arr = np.asarray(getattr(frozen, f))
        assert np.all(arr == held[f]), f"{f} is not constant after the freeze"
