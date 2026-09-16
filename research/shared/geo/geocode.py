"""Address-to-coordinate geocoding with an explicit precision ladder (T1.5d).

WHY THIS MODULE EXISTS
-----------------------
KFS fire locations are Korean addresses (administrative hierarchy text, down
to 시군구/읍면/동리), not coordinates. Turning an address into a coordinate
always loses some precision, and how MUCH precision is lost varies row by
row: a fully resolved 산 lot number can be pinned to a parcel, but many
records bottom out at a 읍면동 or even a 시군구 centroid, and some addresses
do not resolve at all. A downstream join or model that silently mixes a
parcel-level point with a county-centroid point as if they were the same
kind of measurement will misrepresent its own spatial resolution.

**Precision levels are never mixed silently in any downstream join.** Every
function in this module returns the precision level ALONGSIDE the
coordinate (see :class:`GeocodeResult`); no function in this module or
downstream of it should carry a bare ``(lat, lon)`` pair without its
precision. A join or a model that needs one consistent precision level
filters explicitly on the ``precision`` field rather than assuming it.

THE PRECISION LADDER
-----------------------
:class:`GeocodePrecision` is an ordered enum, most precise first:

1. ``PARCEL``: a 산 (mountain) lot number resolved to a specific parcel via
   the VWorld geocoding API.
2. ``RI_CENTROID``: resolved only to the centroid of the named 리 (a village
   below 읍/면 in the Korean administrative hierarchy; 시/도 > 시/군/구 >
   읍/면/동 > 리 > lot number). Finer than a 읍면동 centroid, coarser than a
   real parcel. **Added T1.5g (2026-09-16), forced by a specific dataset:**
   agent A4 measured the KFS landslide occurrence record
   (``kfs_landslide_history``, 5,118 rows,
   ``research/landslides/design/address_precision.py`` /
   ``design_numbers.json`` key ``address_precision``) and found that ZERO
   records carry a lot number in any address field, so ``PARCEL`` is
   unreachable for the entire record; 95.64 % of records instead bottom out
   at a named 리 (their finest populated address field) and 4.28 % bottom
   out at 읍면동. Before this rung existed, that 95.64 % had no correct
   place on the ladder: forcing them to ``EUPMYEONDONG_CENTROID`` would
   silently claim less precision than the address actually carries, and
   there is no other landslide dataset in this program to fall back to, so
   the ladder itself had to grow rather than the caller working around it.
3. ``EUPMYEONDONG_CENTROID``: resolved only to the centroid of the named
   읍/면/동 (the finer administrative unit below 시군구; used when no 리 name
   is available or matched either).
4. ``SIGUNGU_CENTROID``: resolved only to the centroid of the named 시/군/구
   (coarser than 읍면동; used when even the 읍면동 could not be matched).
5. ``UNRESOLVED``: no coordinate could be produced at all; ``lat``/``lon``
   are ``None``.

Because it is an ``IntEnum`` with values assigned in that order, ordinary
comparison operators express "more precise than" directly:
``GeocodePrecision.PARCEL < GeocodePrecision.SIGUNGU_CENTROID`` is ``True``.
Adding ``RI_CENTROID`` shifted the underlying integer VALUES of
``EUPMYEONDONG_CENTROID`` (1 -> 2), ``SIGUNGU_CENTROID`` (2 -> 3) and
``UNRESOLVED`` (3 -> 4); every existing NAME still works and every existing
``<``/``<=``/``==`` comparison between names still holds, because nothing in
this program stores or compares the bare integer value (checked: the only
importers are this module's own test file and
``research/landslides/design/address_precision.py``, which reads member
NAMES via ``[p.name for p in GeocodePrecision]``, never a raw value).

THE VWORLD CLIENT IS BLOCKED THIS ROUND
------------------------------------------
``VWORLD_KEY`` is unset in this sandbox (confirmed 2026-09-16, all six data
API keys unset). :class:`VWorldClient` therefore cannot make a live call
here. It is written so that:

- the key is read from ``os.environ`` ONLY, never accepted as a hardcoded
  default and never accepted as a plain function argument that could end up
  in a log line or a committed file;
- the key is never logged, never included in an exception message, and never
  printed by this module;
- constructing the client with no key set raises :class:`VWorldKeyMissingError`
  immediately, with a message that names the environment variable and where
  to get a key, but never echoes back whatever (empty) value was found.

The actual HTTP call (:meth:`VWorldClient.geocode_parcel`) is written but
cannot be exercised in this sandbox; it is tested here only through a mock
client, per the task's "test the precision ladder ordering and the
key-missing error path with a mocked client, not a live call."
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol


class GeocodePrecision(IntEnum):
    """Geocoding precision ladder, most precise first (see module docstring).

    Ordered so that a smaller value always means "more precise" and ordinary
    comparisons (``<``, ``<=``, ``==``) express the ladder directly.
    """

    PARCEL = 0
    RI_CENTROID = 1
    EUPMYEONDONG_CENTROID = 2
    SIGUNGU_CENTROID = 3
    UNRESOLVED = 4


#: The ladder in order, most to least precise. Provided alongside the enum
#: for callers that want to iterate the ladder explicitly (e.g. to build a
#: fallback chain) rather than relying on enum member order.
PRECISION_LADDER: tuple[GeocodePrecision, ...] = (
    GeocodePrecision.PARCEL,
    GeocodePrecision.RI_CENTROID,
    GeocodePrecision.EUPMYEONDONG_CENTROID,
    GeocodePrecision.SIGUNGU_CENTROID,
    GeocodePrecision.UNRESOLVED,
)


@dataclass(frozen=True)
class GeocodeResult:
    """A geocoded address. ``precision`` is ALWAYS set, even when unresolved.

    ``lat``/``lon`` are decimal degrees, WGS84 (EPSG:4326; see
    ``research/shared/geo/crs.py`` for the program's exchange-vs-analysis
    CRS convention). Both are ``None`` exactly when
    ``precision is GeocodePrecision.UNRESOLVED``.
    """

    address: str
    lat: float | None
    lon: float | None
    precision: GeocodePrecision
    note: str = ""


class VWorldKeyMissingError(RuntimeError):
    """Raised when ``VWORLD_KEY`` is not set. Never echoes the (empty) key."""


class _CentroidLookup(Protocol):
    """Minimal interface a centroid table must satisfy for the fallback ladder.

    Any ``Mapping[str, tuple[float, float]]`` (address-component string ->
    ``(lat, lon)``) satisfies this, so tests can pass a plain ``dict``.
    """

    def get(self, key: str, default=None):  # pragma: no cover - structural
        ...


class VWorldClient:
    """Thin, mockable seam over the VWorld geocoding API.

    The key is read from the environment ONLY (see module docstring). This
    class never logs, prints, or includes the key in any exception message.

    ``geocode_parcel`` is written to shape the real VWorld call, but making
    it is out of scope this round (no ``VWORLD_KEY`` in this sandbox); it is
    exercised only via mocks/subclasses in the test suite.
    """

    #: Name of the environment variable this client reads. A module-level
    #: constant (rather than a string literal repeated in three places) so a
    #: test can reference the same name the error message uses.
    KEY_ENV_VAR = "VWORLD_KEY"

    def __init__(self, key: str | None = None) -> None:
        # `key` is accepted only so a test double can inject a fake key
        # without touching the process environment; production callers must
        # leave it unset and rely on `VWORLD_KEY`.
        resolved = key if key is not None else os.environ.get(self.KEY_ENV_VAR)
        if not resolved:
            raise VWorldKeyMissingError(
                f"{self.KEY_ENV_VAR} is not set. Get a key at "
                "https://www.vworld.kr (API 인증키 발급) and "
                f"`export {self.KEY_ENV_VAR}=<your key>` before constructing "
                "VWorldClient. The key is read from the environment only "
                "and this error never echoes it back."
            )
        self._key = resolved  # never logged, never printed, never repr'd

    def __repr__(self) -> str:  # defensive: keep the key out of any repr/log
        return f"{type(self).__name__}(key=<redacted>)"

    def geocode_parcel(self, address: str) -> tuple[float, float] | None:
        """Resolve ``address`` to a parcel-level ``(lat, lon)``, or ``None``.

        Not implemented against the live VWorld API this round (blocked on
        ``VWORLD_KEY`` being unset; see ``research/data/REGISTRY.yaml``).
        A subclass or a mock supplies this in tests; production use requires a
        working key and a real HTTP call, deliberately left unbuilt until the
        key is available so this round does not ship an untestable code
        path.
        """
        raise NotImplementedError(
            "VWorldClient.geocode_parcel: live VWorld calls are blocked "
            "this round (VWORLD_KEY unset). Use a mock client in tests, or "
            "implement the HTTP call once the key is available."
        )


def geocode_address(
    address: str,
    client: VWorldClient,
    *,
    ri: str | None = None,
    eupmyeondong: str | None = None,
    sigungu: str | None = None,
    ri_centroids: "_CentroidLookup | None" = None,
    eupmyeondong_centroids: "_CentroidLookup | None" = None,
    sigungu_centroids: "_CentroidLookup | None" = None,
) -> GeocodeResult:
    """Geocode one address by walking the precision ladder top to bottom.

    Tries, in order, and stops at the first that succeeds:

    1. Parcel level via ``client.geocode_parcel(address)``.
    2. 리 centroid: looks up ``ri`` in ``ri_centroids``. **Added T1.5g**, for
       records (e.g. ``kfs_landslide_history``) whose finest address field is
       a 리 name with no lot number, so step 1 can never resolve them; see
       the module docstring's "THE PRECISION LADDER" section for why.
    3. 읍면동 centroid: looks up ``eupmyeondong`` in ``eupmyeondong_centroids``.
    4. 시군구 centroid: looks up ``sigungu`` in ``sigungu_centroids``.
    5. ``UNRESOLVED`` (``lat``/``lon`` both ``None``).

    A step that is not GIVEN the inputs it needs (e.g. no ``ri_centroids``
    table, or no ``ri`` for this address) is skipped rather than treated as a
    failure that stops the ladder, so an existing caller that never passes
    ``ri``/``ri_centroids`` sees exactly its old behaviour: the ladder falls
    straight from parcel to 읍면동, unchanged. A step whose lookup raises is
    also treated as "this step did not resolve" and the ladder continues,
    EXCEPT :class:`VWorldKeyMissingError`, which is re-raised immediately: a
    missing key is a configuration error the caller must fix, not an
    address-specific fallback case.

    The returned :class:`GeocodeResult` always carries a precision, per the
    module docstring's "never mixed silently" rule.
    """
    try:
        parcel = client.geocode_parcel(address)
    except VWorldKeyMissingError:
        raise
    except NotImplementedError:
        parcel = None
    except Exception:  # noqa: BLE001 - any other client failure falls through the ladder
        parcel = None

    if parcel is not None:
        lat, lon = parcel
        return GeocodeResult(address, lat, lon, GeocodePrecision.PARCEL)

    if ri is not None and ri_centroids is not None:
        hit = ri_centroids.get(ri)
        if hit is not None:
            lat, lon = hit
            return GeocodeResult(address, lat, lon, GeocodePrecision.RI_CENTROID)

    if eupmyeondong is not None and eupmyeondong_centroids is not None:
        hit = eupmyeondong_centroids.get(eupmyeondong)
        if hit is not None:
            lat, lon = hit
            return GeocodeResult(
                address, lat, lon, GeocodePrecision.EUPMYEONDONG_CENTROID
            )

    if sigungu is not None and sigungu_centroids is not None:
        hit = sigungu_centroids.get(sigungu)
        if hit is not None:
            lat, lon = hit
            return GeocodeResult(address, lat, lon, GeocodePrecision.SIGUNGU_CENTROID)

    return GeocodeResult(
        address,
        None,
        None,
        GeocodePrecision.UNRESOLVED,
        note="no parcel match and no centroid fallback available",
    )
