"""NASA FIRMS NRT hotspot acquisition.

Round-3 PHASE 6-A.

WHAT IS REAL-TIME HERE
----------------------
This module, and only this module, is the real-time part of the project. FIRMS
NRT publishes VIIRS and MODIS active-fire detections within roughly three hours
of the satellite overpass. Nothing downstream of it is real-time — see
:mod:`wildfireguardian.live.scope`.

NRT ONLY, DELIBERATELY
----------------------
``*_SP`` (standard processing) archives are excluded at the config level. They
are better data, and they lag by about two months; polling one would turn a
"live" pipeline into a historical one without changing a single line of output.
:func:`fetch_hotspots` refuses any source whose name does not end ``_NRT``.

ALL-OR-NOTHING, LIKE OVERPASS
-----------------------------
A partial hotspot list is worse than none: a missing detection reads as "no new
fire". So a source that fails after its retries aborts the whole poll rather
than contributing what it managed to fetch — the same rule
``docs/HANDOFF_ROUND3.md`` §5.6 sets for Overpass.

CREDENTIALS
-----------
``FIRMS_MAP_KEY`` comes from the environment (``.env`` is git-ignored and loaded
by the caller). It is never logged, never written into an artifact, and never
placed in a URL that is printed — :func:`_redact` is applied to every URL that
reaches stdout or an exception message.
"""

from __future__ import annotations

import csv
import io
import math
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime

#: Environment variable holding the FIRMS MAP_KEY.
ENV_MAP_KEY: str = "FIRMS_MAP_KEY"
#: Historical alias used by `.env.example`; accepted so an older `.env` works.
ENV_MAP_KEY_ALT: str = "NASA_FIRMS_MAP_KEY"

#: Confidence ladder. VIIRS reports l/n/h; MODIS reports 0-100.
_CONFIDENCE_ORDER: dict[str, int] = {"low": 0, "nominal": 1, "high": 2}
_VIIRS_CONFIDENCE: dict[str, str] = {"l": "low", "n": "nominal", "h": "high"}


class FirmsError(RuntimeError):
    """FIRMS could not be queried, or answered with something unusable."""


class FirmsCredentialsMissing(FirmsError):
    """No MAP_KEY in the environment. The live branch cannot run."""


def map_key(env: dict[str, str] | None = None) -> str:
    """Read the MAP_KEY, or raise. Never returns an empty string."""
    src = os.environ if env is None else env
    for name in (ENV_MAP_KEY, ENV_MAP_KEY_ALT):
        v = (src.get(name) or "").strip()
        if v:
            return v
    raise FirmsCredentialsMissing(
        f"{ENV_MAP_KEY} is not set. Issue a key at "
        "https://firms.modaps.eosdis.nasa.gov/api/area/ and put it in .env "
        "(git-ignored). Replay mode needs no key and is the demo path.")


def credentials_present(env: dict[str, str] | None = None) -> bool:
    try:
        map_key(env)
    except FirmsCredentialsMissing:
        return False
    return True


def _redact(url: str, key: str) -> str:
    return url.replace(key, "<MAP_KEY>") if key else url


def confidence_rank(raw: object) -> int:
    """Normalise VIIRS (l/n/h) and MODIS (0-100) confidence onto one ladder.

    Unknown values rank as ``low`` — the conservative direction, because a
    detection we cannot grade should not be the one that fires a dispatch.
    """
    s = str(raw).strip().lower()
    if s in _CONFIDENCE_ORDER:
        return _CONFIDENCE_ORDER[s]
    if s in _VIIRS_CONFIDENCE:
        return _CONFIDENCE_ORDER[_VIIRS_CONFIDENCE[s]]
    try:                                    # MODIS: percentage
        pct = float(s)
    except ValueError:
        return _CONFIDENCE_ORDER["low"]
    if pct >= 80.0:
        return _CONFIDENCE_ORDER["high"]
    if pct >= 30.0:
        return _CONFIDENCE_ORDER["nominal"]
    return _CONFIDENCE_ORDER["low"]


def confidence_label(raw: object) -> str:
    rank = confidence_rank(raw)
    for name, r in _CONFIDENCE_ORDER.items():
        if r == rank:
            return name
    return "low"


@dataclass(frozen=True)
class Hotspot:
    """One active-fire detection, from FIRMS NRT or from a replayed archive."""

    lat: float
    lon: float
    acquired_utc: datetime
    source: str                      # VIIRS_SNPP_NRT, or "replay:<csv name>"
    satellite: str
    instrument: str
    confidence_raw: str
    frp: float | None = None
    daynight: str = ""

    @property
    def confidence(self) -> str:
        return confidence_label(self.confidence_raw)

    @property
    def confidence_rank(self) -> int:
        return confidence_rank(self.confidence_raw)

    def key(self, *, decimals: int = 4) -> str:
        """Identity for the seen-set.

        Rounded to ~11 m at Korean latitudes, which is well under one VIIRS
        pixel: the same ground pixel re-observed on the next overpass yields the
        same key, and is therefore not "new". Coarser clustering is
        :func:`new_hotspots`' job, not this one's.
        """
        return f"{self.lat:.{decimals}f},{self.lon:.{decimals}f}"

    def as_dict(self) -> dict:
        return {
            "lat": self.lat, "lon": self.lon,
            "acquired_utc": self.acquired_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": self.source, "satellite": self.satellite,
            "instrument": self.instrument,
            "confidence": self.confidence, "confidence_raw": self.confidence_raw,
            "frp": self.frp, "daynight": self.daynight,
        }


def in_bbox(h: Hotspot, bbox_wsen: tuple[float, float, float, float]) -> bool:
    """Is the hotspot inside the registered region? Bounds are inclusive."""
    w, s, e, n = bbox_wsen
    return (w <= h.lon <= e) and (s <= h.lat <= n)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres. Used for de-duplication and for the
    hotspot-to-ignition distance that decides field applicability."""
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def new_hotspots(candidates: list[Hotspot], seen_keys: set[str], *,
                 dedupe_radius_m: float = 375.0,
                 seen_points: list[tuple[float, float]] | None = None
                 ) -> list[Hotspot]:
    """The hotspots this poll saw that the previous polls did not.

    Two filters, in order:

    1. **exact key** — the same rounded coordinate seen before is a
       re-observation of the same ground pixel;
    2. **radius** — a detection within ``dedupe_radius_m`` of any previously
       seen point is the same hotspot observed by a different instrument or on a
       shifted pixel grid. One VIIRS pixel is ~375 m, so anything closer than
       that cannot be resolved as a separate fire and must not be reported as
       one.

    Within a single batch the accepted hotspots are also compared against each
    other, so one overpass over a large fire front yields a handful of distinct
    new points rather than four hundred near-identical ones.
    """
    pts = list(seen_points or [])
    out: list[Hotspot] = []
    for h in candidates:
        if h.key() in seen_keys:
            continue
        if any(haversine_m(h.lat, h.lon, la, lo) <= dedupe_radius_m
               for la, lo in pts):
            continue
        out.append(h)
        pts.append((h.lat, h.lon))
    return out


# ---------------------------------------------------------------------------
# CSV parsing — shared by the live branch and the replay branch
# ---------------------------------------------------------------------------


def _parse_time(row: dict[str, str]) -> datetime | None:
    """FIRMS gives ``acq_date`` (YYYY-MM-DD) and ``acq_time`` (HHMM or HMM)."""
    date = (row.get("acq_date") or "").strip()
    raw = (row.get("acq_time") or "").strip()
    if not date:
        ts = (row.get("timestamp") or "").strip()
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            return None
    hhmm = raw.split(".")[0].zfill(4) if raw else "0000"
    try:
        return datetime.strptime(f"{date} {hhmm[:2]}:{hhmm[2:4]}",
                                 "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
    except ValueError:
        return None


def parse_csv(text: str, *, source: str) -> list[Hotspot]:
    """Parse a FIRMS area-API CSV body (or an archived detections CSV)."""
    rows = list(csv.DictReader(io.StringIO(text)))
    out: list[Hotspot] = []
    for r in rows:
        try:
            lat = float(r["latitude"])
            lon = float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        when = _parse_time(r)
        if when is None:
            continue
        frp_raw = (r.get("frp") or "").strip()
        try:
            frp = float(frp_raw) if frp_raw else None
        except ValueError:
            frp = None
        out.append(Hotspot(
            lat=lat, lon=lon, acquired_utc=when, source=source,
            satellite=str(r.get("satellite") or "").strip(),
            instrument=str(r.get("instrument") or "").strip(),
            confidence_raw=str(r.get("confidence") or "").strip(),
            frp=frp, daynight=str(r.get("daynight") or "").strip()))
    out.sort(key=lambda h: h.acquired_utc)
    return out


# ---------------------------------------------------------------------------
# The live branch
# ---------------------------------------------------------------------------


@dataclass
class PollResult:
    """One complete poll: every source answered, or the poll failed."""

    polled_utc: datetime
    bbox_wsen: tuple[float, float, float, float]
    sources: list[str]
    hotspots: list[Hotspot] = field(default_factory=list)
    per_source_counts: dict[str, int] = field(default_factory=dict)
    raw_csv: dict[str, str] = field(default_factory=dict)
    attempts: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "polled_utc": self.polled_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bbox_wsen": list(self.bbox_wsen),
            "sources": self.sources,
            "n_hotspots": len(self.hotspots),
            "per_source_counts": self.per_source_counts,
            "attempts": self.attempts,
        }


def _get(url: str, timeout_s: float) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "wildfireguardian/round3"})
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:  # noqa: S310
        if resp.status != 200:
            raise FirmsError(f"HTTP {resp.status}")
        return resp.read().decode("utf-8", errors="replace")


def fetch_hotspots(bbox_wsen: tuple[float, float, float, float], *,
                   sources: list[str], day_range: int = 1,
                   api_base: str = "https://firms.modaps.eosdis.nasa.gov/api/area/csv",
                   timeout_s: float = 60.0, retries: int = 3,
                   backoff_s: list[float] | None = None,
                   key: str | None = None,
                   opener=None) -> PollResult:
    """Query every configured NRT source over ``bbox_wsen``. All or nothing.

    ``opener`` is the seam the tests use; production passes ``None`` and gets
    :func:`_get`. It exists so the parsing, retry and all-or-nothing logic can be
    exercised with **no network at all** — the replay branch must never be able
    to reach this function, and the tests assert that too.
    """
    bad = [s for s in sources if not s.upper().endswith("_NRT")]
    if bad:
        raise FirmsError(
            f"refusing non-NRT source(s) {bad}: the *_SP archives lag by about "
            "two months, and polling one would make a historical query look "
            "like a live one. config live.firms.sources must be NRT only.")
    k = key if key is not None else map_key()
    fetch = opener or _get
    waits = list(backoff_s or [30.0, 60.0, 120.0])
    w, s, e, n = bbox_wsen
    area = f"{w},{s},{e},{n}"

    res = PollResult(polled_utc=datetime.now(UTC), bbox_wsen=bbox_wsen,
                     sources=list(sources))
    for src in sources:
        url = f"{api_base}/{k}/{src}/{area}/{int(day_range)}"
        body: str | None = None
        last: Exception | None = None
        for attempt in range(1, max(int(retries), 1) + 1):
            t0 = time.monotonic()
            try:
                body = fetch(url, timeout_s)
                res.attempts.append({
                    "source": src, "attempt": attempt, "ok": True,
                    "elapsed_s": round(time.monotonic() - t0, 3),
                    "url": _redact(url, k)})
                break
            except (urllib.error.URLError, OSError, FirmsError) as exc:
                last = exc
                res.attempts.append({
                    "source": src, "attempt": attempt, "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                    "elapsed_s": round(time.monotonic() - t0, 3),
                    "url": _redact(url, k)})
                if attempt < max(int(retries), 1):
                    time.sleep(waits[min(attempt - 1, len(waits) - 1)])
        if body is None:
            raise FirmsError(
                f"{src}: no usable response after {retries} attempts "
                f"({type(last).__name__ if last else 'unknown'}: {last}). "
                "Discarding the whole poll — a partial hotspot list reads as "
                "'no new fire', which is the one wrong answer here.")
        # The API answers a bad key with a plain-text explanation, not a 4xx.
        head = body.lstrip()[:200].lower()
        if head and not head.startswith("country_id") and "latitude" not in head:
            raise FirmsError(
                f"{src}: response is not a FIRMS CSV. First bytes: "
                f"{body.lstrip()[:120]!r}")
        res.raw_csv[src] = body
        got = parse_csv(body, source=src)
        res.per_source_counts[src] = len(got)
        res.hotspots.extend(got)

    res.hotspots.sort(key=lambda h: h.acquired_utc)
    return res


__all__ = [
    "ENV_MAP_KEY", "FirmsCredentialsMissing", "FirmsError", "Hotspot",
    "PollResult", "confidence_label", "confidence_rank", "credentials_present",
    "fetch_hotspots", "haversine_m", "in_bbox", "map_key", "new_hotspots",
    "parse_csv",
]
