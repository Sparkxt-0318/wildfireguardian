"""Discover event IDs and hourly cutoff times without opening raster data.

Availability describes the time support declared in events.json. It does not
imply that every environmental input or prediction cell is valid.
"""
from __future__ import annotations

from datetime import datetime
import json
from numbers import Integral
from pathlib import Path

from .paths import DATA_ROOT, resolve_recorded_path

__all__ = ["available_events", "available_cutoffs"]

_HOUR_NS = 3_600_000_000_000


def _length(value):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 1:
        raise ValueError("sequence_length must be a positive integer")
    return int(value)


def _timestamp(value, name, *, require_offset=False):
    # Pandas preserves nanosecond precision and matches the dataset's hourly
    # grid. Import it only when querying, without importing Torch or rasterio.
    import pandas as pd

    if not isinstance(value, (str, datetime)):
        raise ValueError(f"{name} must be a finite timestamp string or datetime")
    try:
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp):
            raise ValueError("timestamp is missing")
        if timestamp.tzinfo is None:
            if require_offset:
                raise ValueError("timestamp must include a UTC offset")
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")
        # Validate the exact nanosecond representation used for grid arithmetic.
        timestamp.value
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be a finite timestamp"
                         + (" with a UTC offset" if require_offset else "")) from error
    return timestamp


def _catalog(data_root):
    path = resolve_recorded_path(data_root).resolve() / "events.json"
    entries = json.loads(path.read_text())
    if not isinstance(entries, list):
        raise ValueError("events.json must contain a list of event records")
    result, seen = [], set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Each catalog event must be an object")
        event = entry.get("id")
        if not isinstance(event, str) or not event.strip():
            raise ValueError("Each catalog event must have a nonempty string id")
        if event in seen:
            raise ValueError(f"Duplicate catalog event id: {event!r}")
        seen.add(event)
        start = _timestamp(entry.get("start_utc"), f"{event} start_utc", require_offset=True)
        end = _timestamp(entry.get("end_utc"), f"{event} end_utc", require_offset=True)
        if end < start:
            raise ValueError(f"{event} end_utc must not precede start_utc")
        count = (int(end.value) - int(start.value)) // _HOUR_NS + 1
        result.append((event, start, count))
    return result


def available_events(
    cutoff: str | datetime | None = None, *, data_root: str | Path = DATA_ROOT,
    sequence_length: int = 1,
) -> list[str]:
    """List catalog event IDs, optionally available at one exact cutoff.

    Preserve catalog order. ``cutoff`` may be a UTC/offset timestamp or datetime;
    naive query values are interpreted as UTC.
    It must be on the event's exact hourly grid, anchored at start_utc. An
    off-grid or out-of-range cutoff returns no matching events, without rounding.
    ``sequence_length`` requires that many consecutive hourly snapshots within
    the catalog interval; padded tail windows are excluded. Use 2 when the first
    prediction needs a next-hour reference label for plotting.

    Reads only events.json. It does not load a checkpoint, open rasters, check
    pixel/channel quality, or determine whether a fire is actively burning.
    """
    length = _length(sequence_length)
    timestamp = None if cutoff is None else _timestamp(cutoff, "cutoff")
    result = []
    for event, start, count in _catalog(data_root):
        if length > count:
            continue
        if timestamp is None:
            result.append(event)
        else:
            delta = int(timestamp.value) - int(start.value)
            if delta % _HOUR_NS == 0 and 0 <= delta // _HOUR_NS <= count - length:
                result.append(event)
    return result


def available_cutoffs(
    event: str, *, data_root: str | Path = DATA_ROOT, sequence_length: int = 1,
    time_range: tuple[str | datetime, str | datetime] | None = None,
) -> list[str]:
    """List chronological UTC cutoff strings for an event's complete sequences.

    Returned strings end in Z and are accepted directly by select_time().
    Grid times retain the exact catalog start, even if it is between clock
    hours. ``sequence_length`` excludes starts needing padded tail snapshots.
    ``time_range=(start,end)`` inclusively filters cutoff/start times only;
    following sequence snapshots may lie outside this filter but must fit the
    event's catalog interval. Naive filter timestamps are interpreted as UTC.

    Unknown events raise ValueError. An empty selection returns []. The query
    reads only catalog metadata, rather than verifying raster/predictor quality.
    """
    import pandas as pd

    length = _length(sequence_length)
    if not isinstance(event, str) or not event.strip():
        raise ValueError("event must be one nonempty event identifier")
    bounds = None
    if time_range is not None:
        if not isinstance(time_range, tuple) or len(time_range) != 2:
            raise ValueError("time_range must be a (start, end) tuple")
        bounds = (_timestamp(time_range[0], "time_range start"),
                  _timestamp(time_range[1], "time_range end"))
        if bounds[1] < bounds[0]:
            raise ValueError("time_range end must not precede start")
    entries = _catalog(data_root)
    selected = next((entry for entry in entries if entry[0] == event), None)
    if selected is None:
        raise ValueError(f"Unknown event ID: {event!r}")
    _, start, count = selected
    first, last = 0, count - length
    if bounds is not None:
        lower = int(bounds[0].value) - int(start.value)
        upper = int(bounds[1].value) - int(start.value)
        first = max(first, -(-lower // _HOUR_NS))
        last = min(last, upper // _HOUR_NS)
    if last < first:
        return []
    beginning = pd.Timestamp(int(start.value) + first * _HOUR_NS, tz="UTC")
    return [time.isoformat().replace("+00:00", "Z")
            for time in pd.date_range(beginning, periods=last - first + 1, freq="h")]
