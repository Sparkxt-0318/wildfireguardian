"""Replay a past fire's hotspots in time order, entirely offline.

Round-3 PHASE 6-C.

WHY THIS IS THE PRIMARY PATH, NOT THE FALLBACK
----------------------------------------------
A live demonstration depends on three things the venue does not control: a
working network, a FIRMS overpass inside the demo window, and an actual fire
burning somewhere in the registered region. On any given October afternoon the
third is very unlikely and the first two are merely unreliable. So replay is
built to be **more** robust than live, not less, and it is the path a
demonstration should default to.

OFFLINE BY CONSTRUCTION, NOT BY POLICY
--------------------------------------
This module imports nothing from :mod:`wildfireguardian.live.firms` except the
pure data types and the parser. There is no HTTP client on this branch, no
credential read, and no code path from here that can reach one. That is a
structural guarantee rather than a runtime check, and
``tests/test_live_pipeline.py`` additionally runs a full replay with the socket
layer disabled to prove it.

TIME
----
A replay maps archive time onto wall-clock time by a speed multiplier: at 60x,
twelve hours of a real fire take twelve minutes to watch. The clock is the only
thing that is simulated — the detections, their coordinates, their instruments
and their confidences are the real recorded ones.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .firms import Hotspot, parse_csv

#: Detections separated by more than this are different satellite overpasses.
#: Matches ``spread_v2.grid.overpass_snapshots``'s default, so a replayed
#: overpass is the same grouping the hazard field was built from.
OVERPASS_GAP_MIN: float = 90.0


@dataclass(frozen=True)
class ReplayOverpass:
    """One satellite pass over the region, as recorded."""

    index: int
    archive_time: datetime
    hotspots: list[Hotspot]

    @property
    def n(self) -> int:
        return len(self.hotspots)

    def as_dict(self) -> dict:
        return {"index": self.index,
                "archive_time_utc": self.archive_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "n_hotspots": self.n}


def load_archive(csv_path: Path, *, source_label: str | None = None) -> list[Hotspot]:
    """Read a committed detections CSV. No network, no credentials.

    The archives under ``data/raw/firms_data/`` are the same FIRMS product the
    live branch polls, downloaded once and committed by digest, so the parser is
    shared and a replayed hotspot is indistinguishable in type from a live one.
    """
    p = Path(csv_path)
    if not p.exists():
        raise FileNotFoundError(
            f"replay archive missing: {p}. Replay reads a committed detections "
            "CSV from data/raw/firms_data/; it never downloads anything.")
    label = source_label or f"replay:{p.name}"
    return parse_csv(p.read_text(encoding="utf-8"), source=label)


def group_overpasses(hotspots: list[Hotspot], *,
                     gap_minutes: float = OVERPASS_GAP_MIN) -> list[ReplayOverpass]:
    """Cluster detections into satellite passes on a time gap."""
    if not hotspots:
        return []
    ordered = sorted(hotspots, key=lambda h: h.acquired_utc)
    groups: list[list[Hotspot]] = [[ordered[0]]]
    for h in ordered[1:]:
        prev = groups[-1][-1].acquired_utc
        if (h.acquired_utc - prev) > timedelta(minutes=gap_minutes):
            groups.append([h])
        else:
            groups[-1].append(h)
    return [ReplayOverpass(index=i, archive_time=max(g, key=lambda x: x.acquired_utc).acquired_utc,
                           hotspots=g)
            for i, g in enumerate(groups)]


@dataclass
class ReplayClock:
    """Maps archive time to wall-clock time at a fixed speed multiplier.

    ``speed`` is archive-seconds per wall-second. 60x means an hour of the fire
    passes in a minute. ``speed = 0`` means "as fast as the machine allows",
    which is what the tests use — the pipeline must not depend on real sleeping
    to be correct.
    """

    t0_archive: datetime
    speed: float = 60.0
    sleep: Callable[[float], None] = time.sleep

    def wall_delay_s(self, when: datetime) -> float:
        """Wall-clock seconds from the replay's start to ``when``."""
        if self.speed <= 0:
            return 0.0
        return max(0.0, (when - self.t0_archive).total_seconds() / self.speed)

    def wait_until(self, when: datetime, elapsed_s: float) -> float:
        """Sleep until ``when`` is due. Returns the seconds actually slept."""
        due = self.wall_delay_s(when)
        gap = due - elapsed_s
        if gap > 0:
            self.sleep(gap)
            return gap
        return 0.0


@dataclass
class ReplaySource:
    """An offline, time-ordered hotspot feed built from a committed archive."""

    hotspots: list[Hotspot]
    overpasses: list[ReplayOverpass]
    csv_path: Path
    window_h: float | None
    speed: float

    @classmethod
    def from_csv(cls, csv_path: Path, *, window_h: float | None = 12.0,
                 speed: float = 60.0,
                 bbox_wsen: tuple[float, float, float, float] | None = None,
                 gap_minutes: float = OVERPASS_GAP_MIN) -> "ReplaySource":
        """Build a replay over the first ``window_h`` hours of the archive.

        ``bbox_wsen`` filters to the registered region **before** windowing, so
        the window is a window on the region's own detections rather than on the
        raw file.
        """
        all_hs = load_archive(csv_path)
        if bbox_wsen is not None:
            w, s, e, n = bbox_wsen
            all_hs = [h for h in all_hs if w <= h.lon <= e and s <= h.lat <= n]
        if not all_hs:
            raise ValueError(
                f"no detections in {Path(csv_path).name} inside the registered "
                "region. Replay has nothing to show; check live.region and "
                "bbox.multi_region_walk_bbox.")
        t0 = all_hs[0].acquired_utc
        if window_h is not None:
            cut = t0 + timedelta(hours=float(window_h))
            all_hs = [h for h in all_hs if h.acquired_utc <= cut]
        return cls(hotspots=all_hs,
                   overpasses=group_overpasses(all_hs, gap_minutes=gap_minutes),
                   csv_path=Path(csv_path), window_h=window_h, speed=speed)

    @property
    def t0(self) -> datetime:
        return self.hotspots[0].acquired_utc

    @property
    def t_end(self) -> datetime:
        return self.hotspots[-1].acquired_utc

    @property
    def archive_span_h(self) -> float:
        return (self.t_end - self.t0).total_seconds() / 3600.0

    @property
    def projected_wall_s(self) -> float:
        if self.speed <= 0:
            return 0.0
        return (self.t_end - self.t0).total_seconds() / self.speed

    def clock(self, sleep: Callable[[float], None] = time.sleep) -> ReplayClock:
        return ReplayClock(t0_archive=self.t0, speed=self.speed, sleep=sleep)

    def iter_overpasses(self) -> Iterator[ReplayOverpass]:
        yield from self.overpasses

    def as_dict(self) -> dict:
        return {
            "csv_path": str(self.csv_path),
            "n_hotspots": len(self.hotspots),
            "n_overpasses": len(self.overpasses),
            "archive_t0_utc": self.t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "archive_t_end_utc": self.t_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "archive_span_h": round(self.archive_span_h, 3),
            "window_h": self.window_h,
            "speed_multiplier": self.speed,
            "projected_wall_clock_s": round(self.projected_wall_s, 1),
            "overpasses": [o.as_dict() for o in self.overpasses],
            "offline": True,
            "network_used": False,
            "note": "REPLAY — archived detections from a past fire, replayed in "
                    "time order. Not a fire happening now.",
        }


def utcnow() -> datetime:
    return datetime.now(UTC)


__all__ = ["OVERPASS_GAP_MIN", "ReplayClock", "ReplayOverpass", "ReplaySource",
           "group_overpasses", "load_archive", "utcnow"]
