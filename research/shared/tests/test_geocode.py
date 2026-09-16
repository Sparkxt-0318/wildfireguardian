"""Tests for research/shared/geo/geocode.py (T1.5d).

No live VWorld call is made anywhere in this file (VWORLD_KEY is unset in
this sandbox). Everything below uses a mock/subclass client, per the task.
"""

from __future__ import annotations

import os

import pytest

from research.shared.geo.geocode import (
    GeocodePrecision,
    GeocodeResult,
    PRECISION_LADDER,
    VWorldClient,
    VWorldKeyMissingError,
    geocode_address,
)


class _MockClient(VWorldClient):
    """Bypasses the real HTTP call; returns a canned answer instead."""

    def __init__(self, key: str = "fake-test-key", parcel_result=None):
        super().__init__(key=key)
        self._parcel_result = parcel_result

    def geocode_parcel(self, address: str):
        return self._parcel_result


# --------------------------------------------------------------------- ladder


def test_precision_ladder_ordering():
    assert list(PRECISION_LADDER) == [
        GeocodePrecision.PARCEL,
        GeocodePrecision.RI_CENTROID,
        GeocodePrecision.EUPMYEONDONG_CENTROID,
        GeocodePrecision.SIGUNGU_CENTROID,
        GeocodePrecision.UNRESOLVED,
    ]


def test_precision_ladder_is_ordered_int_enum():
    assert GeocodePrecision.PARCEL < GeocodePrecision.RI_CENTROID
    assert GeocodePrecision.RI_CENTROID < GeocodePrecision.EUPMYEONDONG_CENTROID
    assert GeocodePrecision.EUPMYEONDONG_CENTROID < GeocodePrecision.SIGUNGU_CENTROID
    assert GeocodePrecision.SIGUNGU_CENTROID < GeocodePrecision.UNRESOLVED
    assert GeocodePrecision.PARCEL < GeocodePrecision.UNRESOLVED


def test_ri_centroid_sits_between_parcel_and_eupmyeondong():
    """T1.5g: the rung A4's landslide measurement forced (see geocode.py's
    module docstring) must land in this exact ordinal slot, not just
    anywhere below PARCEL."""
    assert GeocodePrecision.PARCEL.value + 1 == GeocodePrecision.RI_CENTROID.value
    assert (
        GeocodePrecision.RI_CENTROID.value + 1
        == GeocodePrecision.EUPMYEONDONG_CENTROID.value
    )


# --------------------------------------------------------------- key-missing


def test_key_missing_error_when_env_unset(monkeypatch):
    monkeypatch.delenv("VWORLD_KEY", raising=False)
    with pytest.raises(VWorldKeyMissingError) as exc_info:
        VWorldClient()
    msg = str(exc_info.value)
    assert "VWORLD_KEY" in msg
    assert "vworld.kr" in msg.lower()


def test_key_missing_error_message_never_echoes_a_key(monkeypatch):
    monkeypatch.delenv("VWORLD_KEY", raising=False)
    with pytest.raises(VWorldKeyMissingError) as exc_info:
        VWorldClient()
    # the message is static and explanatory; it cannot contain a key value
    # because none was ever read successfully
    assert "None" not in str(exc_info.value)


def test_key_from_environment_is_accepted(monkeypatch):
    monkeypatch.setenv("VWORLD_KEY", "env-supplied-key")
    client = VWorldClient()
    assert "env-supplied-key" not in repr(client)  # never in repr
    assert "redacted" in repr(client)


def test_client_repr_never_leaks_key():
    client = _MockClient(key="super-secret-value")
    assert "super-secret-value" not in repr(client)


def test_confirms_key_actually_unset_in_this_sandbox():
    """Documents the sandbox state this round's report relies on."""
    assert os.environ.get("VWORLD_KEY") in (None, "")


# ----------------------------------------------------------------- fallback


def test_parcel_success_returns_parcel_precision():
    client = _MockClient(parcel_result=(36.5, 127.5))
    result = geocode_address("경상북도 의성군 산 12-3", client)
    assert isinstance(result, GeocodeResult)
    assert result.precision is GeocodePrecision.PARCEL
    assert result.lat == 36.5 and result.lon == 127.5


def test_falls_back_to_ri_centroid():
    """T1.5g: a record with no lot number but a resolved 리 name lands on
    RI_CENTROID rather than falling through to the coarser 읍면동 centroid."""
    client = _MockClient(parcel_result=None)  # parcel resolution fails
    centroids = {"용전리": (36.42, 128.58)}
    result = geocode_address(
        "경상북도 의성군 안계면 용전리",
        client,
        ri="용전리",
        ri_centroids=centroids,
    )
    assert result.precision is GeocodePrecision.RI_CENTROID
    assert result.lat == 36.42 and result.lon == 128.58


def test_ri_centroid_takes_priority_over_eupmyeondong_when_both_resolve():
    """The ladder stops at the first rung that resolves; RI_CENTROID is
    tried (and wins) before EUPMYEONDONG_CENTROID even when both fallback
    tables would produce a hit."""
    client = _MockClient(parcel_result=None)
    ri_centroids = {"용전리": (36.42, 128.58)}
    eupmyeondong_centroids = {"안계면": (36.4, 128.6)}
    result = geocode_address(
        "경상북도 의성군 안계면 용전리",
        client,
        ri="용전리",
        ri_centroids=ri_centroids,
        eupmyeondong="안계면",
        eupmyeondong_centroids=eupmyeondong_centroids,
    )
    assert result.precision is GeocodePrecision.RI_CENTROID
    assert result.lat == 36.42 and result.lon == 128.58


def test_ri_lookup_miss_falls_through_to_eupmyeondong_centroid():
    """RI_CENTROID is skipped, not fatal, when `ri` has no entry in
    `ri_centroids`; the ladder continues to the next rung."""
    client = _MockClient(parcel_result=None)
    result = geocode_address(
        "경상북도 의성군 안계면 이름없는리",
        client,
        ri="이름없는리",
        ri_centroids={"용전리": (36.42, 128.58)},  # no match for this address
        eupmyeondong="안계면",
        eupmyeondong_centroids={"안계면": (36.4, 128.6)},
    )
    assert result.precision is GeocodePrecision.EUPMYEONDONG_CENTROID
    assert result.lat == 36.4 and result.lon == 128.6


def test_no_ri_inputs_behaves_exactly_as_before_the_rung_was_added():
    """Backward compatibility: a caller that never passes `ri`/`ri_centroids`
    (every caller before T1.5g) gets identical behaviour to before this rung
    existed -- straight from parcel to 읍면동."""
    client = _MockClient(parcel_result=None)  # parcel resolution fails
    centroids = {"안계면": (36.4, 128.6)}
    result = geocode_address(
        "경상북도 의성군 안계면",
        client,
        eupmyeondong="안계면",
        eupmyeondong_centroids=centroids,
    )
    assert result.precision is GeocodePrecision.EUPMYEONDONG_CENTROID
    assert result.lat == 36.4 and result.lon == 128.6


def test_falls_back_to_sigungu_centroid_when_eupmyeondong_also_fails():
    client = _MockClient(parcel_result=None)
    eupmyeondong_centroids = {}  # nothing matches
    sigungu_centroids = {"의성군": (36.35, 128.7)}
    result = geocode_address(
        "경상북도 의성군",
        client,
        eupmyeondong="알수없음",
        eupmyeondong_centroids=eupmyeondong_centroids,
        sigungu="의성군",
        sigungu_centroids=sigungu_centroids,
    )
    assert result.precision is GeocodePrecision.SIGUNGU_CENTROID
    assert result.lat == 36.35 and result.lon == 128.7


def test_unresolved_when_nothing_matches():
    client = _MockClient(parcel_result=None)
    result = geocode_address("알 수 없는 주소", client)
    assert result.precision is GeocodePrecision.UNRESOLVED
    assert result.lat is None and result.lon is None


def test_precision_always_present_never_none():
    """Every branch of the ladder must set a precision (module docstring's
    'always returns the precision level alongside the coordinate')."""
    client_ok = _MockClient(parcel_result=(1.0, 2.0))
    client_fail = _MockClient(parcel_result=None)
    for client, kwargs in (
        (client_ok, {}),
        (client_fail, {}),
        (
            client_fail,
            dict(
                eupmyeondong="x",
                eupmyeondong_centroids={"x": (1.0, 1.0)},
            ),
        ),
    ):
        result = geocode_address("아무 주소", client, **kwargs)
        assert result.precision is not None
        assert isinstance(result.precision, GeocodePrecision)


def test_missing_key_during_geocode_reraises_not_swallowed(monkeypatch):
    """A VWorldKeyMissingError raised mid-ladder is a configuration error,
    never silently treated as 'this address just failed to resolve'."""

    class _AlwaysFailsKey(VWorldClient):
        def __init__(self):
            pass  # skip the normal key check so we can raise it from geocode_parcel

        def geocode_parcel(self, address: str):
            raise VWorldKeyMissingError("VWORLD_KEY is not set")

    client = _AlwaysFailsKey()
    with pytest.raises(VWorldKeyMissingError):
        geocode_address("아무 주소", client)
