"""NH-062 — the weather lookup must not depend on the index's datetime resolution.

`WeatherSeries.at` is how `forward_simulate` gets the weather for EVERY step of EVERY
committed spread field. It used to resolve a time with

    self.time.view("int64") - when.value

`Timestamp.value` is ALWAYS nanoseconds; `DatetimeIndex.view("int64")` is the index's OWN
resolution. Under the pinned pandas 3.0.5 a ``datetime64[us]`` or ``[s]`` index makes those
ints 10³ / 10⁹ times smaller, every comparison goes the same way, and ``argmin`` returns
the LAST sample in the series for every query — silently, with no error anywhere. On a
24-hour series with T0 at 10:30 that returned index 23.

⚠ WHAT THIS TEST IS NOT. It is NOT evidence that any committed field was ever wrong.
Measured on the author's laptop on 2026-09-14 against the real bundle, the ERA5 index is
``datetime64[ns, UTC]`` (56 samples, 2025-03-22 → 03-28) and ``at()`` already resolved
correctly — ``at(time[1])`` returned 19.5121, which is ``time[1]``'s own value, against a
last sample of 1.1706. So the hardening removed a trap; it repaired nothing, and no
registered number moved. That is NH-062 option A, and this file is what stops the idiom
coming back.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from wildfireguardian.spread_v2.weather import WeatherSeries, _precip_24h  # noqa: E402

FIELDS = ("wind_speed_ms", "wind_toward_deg", "wind_u", "wind_v", "temp_c",
          "rh_pct", "vpd_kpa", "days_since_rain", "precip_24h_mm")
#: The real ERA5 index is [ns]; [us] and [s] are the resolutions pandas 3 can hand back
#: from a differently-encoded netCDF, and are exactly where the old idiom broke.
RESOLUTIONS = ("ns", "us", "s")


def _series(resolution: str, n: int = 24, step_h: int = 1) -> WeatherSeries:
    """Value at sample *i* IS *i*, so a wrong pick reads as a wrong number."""
    arr = np.array([np.datetime64("2025-03-25T00:00:00") + np.timedelta64(step_h * i, "h")
                    for i in range(n)], dtype=f"datetime64[{resolution}]")
    idx = pd.to_datetime(arr, utc=True)
    v = np.arange(n, dtype=float)
    return WeatherSeries(time=idx, **{f: v.copy() for f in FIELDS})


@pytest.mark.parametrize("resolution", RESOLUTIONS)
def test_at_picks_the_nearest_sample_at_every_resolution(resolution):
    ws = _series(resolution)
    for target, want in ((0, 0.0), (1, 1.0), (11, 11.0), (23, 23.0)):
        got = ws.at(ws.time[target])["temp_c"]
        assert got == want, (
            f"[{resolution}] at(time[{target}]) returned {got}, want {want}. "
            "Returning the LAST sample is the int64-resolution trap NH-062 describes."
        )


@pytest.mark.parametrize("resolution", RESOLUTIONS)
def test_at_does_not_collapse_onto_the_last_sample(resolution):
    """The specific failure shape, pinned on its own so it cannot regress quietly."""
    ws = _series(resolution)
    last = float(ws.temp_c[-1])
    got = ws.at(ws.time[1] + pd.Timedelta(minutes=30))["temp_c"]
    assert got != last, f"[{resolution}] at() collapsed onto the last sample ({last})"
    assert got in (1.0, 2.0), f"[{resolution}] at() picked {got}, not a neighbour of time[1]"


@pytest.mark.parametrize("resolution", RESOLUTIONS)
def test_the_precip_window_is_24_hours_at_every_resolution(resolution):
    """`_precip_24h` carried the same idiom: a wrong unit widens or collapses the window."""
    n = 48
    ws = _series(resolution, n=n)
    tp = np.zeros(n)
    tp[0] = 0.001          # 1 mm, 47 h before the last sample
    tp[n - 1] = 0.002      # 2 mm, at the last sample
    out = _precip_24h(ws.time, tp)
    assert out[n - 1] == pytest.approx(2.0), (
        f"[{resolution}] the trailing-24 h total at the last sample is {out[n-1]}, want 2.0 — "
        "a window that reached 47 h back would also collect the 1 mm at sample 0."
    )
    assert out[0] == pytest.approx(1.0)


def test_the_two_resolutions_agree_with_each_other():
    """The strongest statement available without the bundle: [us] and [s] now match [ns]."""
    ref = _series("ns")
    tp = np.where(np.arange(len(ref.time)) % 6 == 0, 0.002, 0.0)
    ref_at = [ref.at(t)["temp_c"] for t in ref.time]
    ref_pr = _precip_24h(ref.time, tp)
    for resolution in ("us", "s"):
        ws = _series(resolution)
        assert [ws.at(t)["temp_c"] for t in ws.time] == ref_at, f"{resolution} disagrees with ns"
        assert np.allclose(_precip_24h(ws.time, tp), ref_pr), f"{resolution} precip disagrees with ns"


def test_the_banned_idiom_is_gone_from_the_module():
    """A reworded regression is still a regression; this catches the shape, not the effect."""
    src = (REPO / "src/wildfireguardian/spread_v2/weather.py").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert 'view("int64")' not in code, (
        "weather.py has reacquired `view(\"int64\")`. It is only correct on a [ns] index; "
        "difference as timedeltas and fix the unit instead (NH-062)."
    )
