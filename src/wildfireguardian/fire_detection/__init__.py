"""Satellite-based active-fire / hotspot ingestion.

Currently a scaffold. Will expose:

- `pull_firms_area(...)`: query NASA FIRMS area API for VIIRS / MODIS
  hotspots in a bounding box and time window.
- `dedupe_hotspots(...)`: cluster sub-daily revisit duplicates.
- `to_ignition_points(...)`: convert hotspot rows into the project's
  `IgnitionPoint` schema used by the spread model.
"""

from __future__ import annotations

__all__: list[str] = []
