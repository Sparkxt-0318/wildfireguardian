"""Real data root access and forecast windows. Fails loudly when the root is absent and never falls back.

The real root (layout: map 03 section 2.2) lives on Siyeong's Mac::

    events.json
    regions/<id>/arrival_time_hours.tif               reconstructed arrival, hours since t0 (NoData outside the scar)
    regions/<id>/terrain/slope_degrees_375m.tif       static
    regions/<id>/weather/wind_{eastward,northward}_10m_375m.tif   hourly bands, m/s toward east / north
    regions/<id>/weather/ecmwf_ifs_bands.csv          band,time_utc of the hourly bands

``forecast/data/environment`` in this repo holds ``events.json`` only and is rejected on purpose.

Windows (``load_windows``) follow the SPLITS window rule. Each carries the cutoff inputs a forecast may use
(``Cutoff``), kept apart from the truth and the scoring domain. Cutoff state (DATA_NOTES section 5): burned where
the reconstructed arrival is at or before the cutoff, not burned everywhere else on the grid; the reconstruction's
NoData mask is never handed to a forecast.

Data check (exact window counts and headline-domain sizes; docs/DATA_NOTES.md section 7)::

    python -m firecast_lab.data --data-root PATH [--allow-test] [--out FILE]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator

import numpy as np

from firecast_lab import splits as sp
from firecast_lab.domain import HEADLINE_BUFFER_M, full_rectangle, headline_domain, ring_cells_off_grid

ENV_VAR = "FIRECAST_DATA_ROOT"
LEADS_H = (24.0, 12.0)
SLOPE = "terrain/slope_degrees_375m.tif"
WIND = ("weather/wind_eastward_10m_375m.tif", "weather/wind_northward_10m_375m.tif")
WEATHER_BANDS = "weather/ecmwf_ifs_bands.csv"
DOMAINS = ("headline", "full")


class DataRootNotFound(FileNotFoundError):
    """The real data root is missing or incomplete. There is no fallback, by design."""


def data_root(path: str | Path | None = None) -> Path:
    """The real data root: ``path``, else ``$FIRECAST_DATA_ROOT``. It must hold ``events.json`` and ``regions/``."""
    raw = path if path is not None else os.environ.get(ENV_VAR)
    if not raw:
        raise DataRootNotFound(f"data root not found: pass data_root or set {ENV_VAR}. The real root (events.json "
                               "and regions/) is on Siyeong's Mac, not in this repo.")
    root = Path(raw).expanduser()
    if not (root / "events.json").is_file() or not (root / "regions").is_dir():
        raise DataRootNotFound(f"data root not found: {root} must contain events.json and regions/ "
                               "(forecast/data/environment in this repo is metadata only)")
    return root


def check_access(event_id: str, *, allow_test: bool = False, splits: dict | None = None) -> dict:
    """The fire's SPLITS record; refuses unassigned fires, the locked fresh holdout, and test fires by default."""
    record = next((f for f in (splits or sp.load_splits())["fires"] if f["id"] == event_id), None)
    if record is None:
        raise ValueError(f"{event_id} is not in SPLITS.json: assign it a split before reading its data")
    if record["split"] == "fresh_holdout":
        raise PermissionError(f"{event_id} is in the locked fresh_holdout")
    if record["split"] == "test" and not allow_test:
        raise PermissionError(f"{event_id} is a test fire: read it only at a milestone Siyeong approved "
                              "(allow_test=True)")
    return record


def _read_raster(path: Path, event: dict, band: int = 1) -> np.ndarray:
    """One band as float64 with NaN where the nodata tag (or a non-finite value) says unknown; on the event grid."""
    import rasterio

    if not path.is_file():
        raise DataRootNotFound(f"data root not found: missing {path}")
    with rasterio.open(path) as src:
        if (src.crs is None or src.crs.to_epsg() != event["epsg"] or src.shape != (event["height"], event["width"])
                or not np.allclose(tuple(src.transform)[:6], event["transform"])):
            raise ValueError(f"{path} is not on the event grid of {event['id']}")
        values = src.read(band, masked=True).astype(np.float64).filled(np.nan)
    values[~np.isfinite(values)] = np.nan
    return values


def _event(root: Path, event_id: str) -> dict:
    events = {e["id"]: e for e in json.loads((root / "events.json").read_text())}
    if event_id not in events:
        raise DataRootNotFound(f"data root not found: {event_id} is missing from {root / 'events.json'}")
    return events[event_id]


def read_arrival(event_id: str, root: Path, *, allow_test: bool = False,
                 splits: dict | None = None) -> tuple[np.ndarray, dict]:
    """Reconstructed arrival in hours since the event's t0 (NaN where the raster's nodata tag says NoData; valid
    US values can be negative) and the event's catalog record. The raster must sit on the event grid."""
    check_access(event_id, allow_test=allow_test, splits=splits)
    event = _event(root, event_id)
    return _read_raster(root / event["arrival_path"], event), event


def read_layer(root: Path, event: dict, relative: str, band: int = 1) -> np.ndarray:
    """A layer of ``regions/<id>/`` (e.g. ``SLOPE``) on the event grid; NaN = missing."""
    return _read_raster(root / "regions" / event["id"] / relative, event, band)


def _utc(stamp: str) -> datetime:
    return datetime.fromisoformat(str(stamp).replace("Z", "+00:00")).astimezone(timezone.utc)


def weather_reader(root: Path, event: dict) -> Callable[[str], tuple[np.ndarray, np.ndarray]]:
    """``wind_at(time_utc) -> (u, v)``: 10 m wind toward east and north (m/s) in the hourly band stamped exactly
    ``time_utc`` (no interpolation; a missing stamp raises)."""
    table = root / "regions" / event["id"] / WEATHER_BANDS
    if not table.is_file():
        raise DataRootNotFound(f"data root not found: missing {table}")
    with table.open(newline="") as handle:
        bands = {_utc(row["time_utc"]): int(row["band"]) for row in csv.DictReader(handle)}

    def wind_at(time_utc: str) -> tuple[np.ndarray, np.ndarray]:
        band = bands.get(_utc(time_utc))
        if band is None:
            raise DataRootNotFound(f"data root not found: no weather band at {time_utc} in {table}")
        u, v = (read_layer(root, event, path, band) for path in WIND)
        return u, v

    return wind_at


def _hours_since_t0(event: dict, stamp: str) -> float:
    return (datetime.fromisoformat(stamp) - datetime.fromisoformat(event["t0_utc"])).total_seconds() / 3600.0


def window_cutoffs(arrival: np.ndarray, event: dict, lead_h: float,
                   spacing_h: float = sp.WINDOW_SPACING_H) -> list[float]:
    """Cutoffs (hours since t0) under the SPLITS window rule: start + 12 h * k (k >= 1) with cutoff + lead < end,
    and at least one reconstructed burned cell at the cutoff. A condition on the cutoff state, never on outcomes."""
    start, end = _hours_since_t0(event, event["start_utc"]), _hours_since_t0(event, event["end_utc"])
    first_arrival = np.min(np.where(np.isfinite(arrival), arrival, np.inf))
    cutoffs, k = [], 1
    while start + spacing_h * k + lead_h < end:
        cutoff = start + spacing_h * k
        if first_arrival <= cutoff:
            cutoffs.append(cutoff)
        k += 1
    return cutoffs


def window_labels(arrival: np.ndarray, cutoff_h: float, lead_h: float) -> dict[str, np.ndarray]:
    """States for the window (cutoff, cutoff + lead] from arrival hours since t0.

    Outside the final perimeter (NoData) a cell is outside the mapped extent at both times: False in both
    burned masks. That is a mapped-extent negative within the scoring domain, never "certified unburned".
    """
    final = np.isfinite(arrival)
    filled = np.where(final, arrival, np.inf)
    return dict(final_perimeter=final, burned_at_cutoff=filled <= cutoff_h, burned_at_end=filled <= cutoff_h + lead_h)


@dataclass(frozen=True, eq=False)
class Cutoff:
    """Everything a forecast may use: the burned state and inputs at the cutoff. Never the outcome."""

    burned: np.ndarray                    # bool [H, W]: reconstructed arrival at or before the cutoff
    initial_h: np.ndarray                 # arrival of burned cells in hours after the cutoff (<= 0); NaN elsewhere
    cell_m: float
    wind_u: np.ndarray | None = None      # m/s toward east at the cutoff hour (persistence weather); NaN = missing
    wind_v: np.ndarray | None = None      # m/s toward north
    slope: np.ndarray | None = None       # degrees

    @property
    def shape(self) -> tuple[int, int]:
        return self.burned.shape

    @property
    def inputs_valid(self) -> np.ndarray:
        """Cells where every loaded input is finite: the comparison support of the non-c651 baselines."""
        ok = np.ones(self.shape, dtype=bool)
        for layer in (self.wind_u, self.wind_v, self.slope):
            if layer is not None:
                ok &= np.isfinite(layer)
        return ok


@dataclass(frozen=True, eq=False)
class Window:
    """One forecast window (cutoff, cutoff + lead] of one fire: cutoff inputs, truth and scoring domain."""

    fire: str
    record: dict                          # the fire's SPLITS record (split, fold, country, c651_role)
    cutoff_utc: str                       # whole hour, ISO with Z
    cutoff_h: float                       # hours since the event's t0
    lead_h: int
    transform: tuple
    epsg: int
    synthetic: bool
    inputs: Cutoff
    outcome_h: np.ndarray                 # truth: arrival in hours after the cutoff; +inf outside the final perimeter
    domain: np.ndarray                    # scoring domain (headline: final perimeter + 3 km)

    @property
    def fitting_rows(self) -> np.ndarray:
        """Cells that are fitted and scored for the non-c651 baselines: domain, not burned at the cutoff, inputs."""
        return self.domain & ~self.inputs.burned & self.inputs.inputs_valid


def windows_from_arrays(event: dict, arrival: np.ndarray, lead_h: int, *, record: dict, slope=None,
                        wind_at: Callable[[str], tuple] | None = None, domain: str = "headline") -> Iterator[Window]:
    """Windows of one fire from its arrival hours since t0 (NaN outside the final perimeter) and optional inputs."""
    if domain not in DOMAINS:
        raise ValueError(f"domain must be one of {DOMAINS}")
    cutoffs = window_cutoffs(arrival, event, lead_h)
    if not cutoffs:
        return
    final = np.isfinite(arrival)
    cell = abs(float(event["transform"][0]))
    scored = headline_domain(final, cell) if domain == "headline" else full_rectangle(arrival.shape)
    t0 = datetime.fromisoformat(event["t0_utc"])
    for cutoff_h in cutoffs:
        stamp = datetime.fromtimestamp(round((t0 + timedelta(hours=cutoff_h)).timestamp()), tz=timezone.utc)
        cutoff_utc = stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
        burned = window_labels(arrival, cutoff_h, lead_h)["burned_at_cutoff"]
        u, v = wind_at(cutoff_utc) if wind_at is not None else (None, None)
        inputs = Cutoff(burned=burned, initial_h=np.where(burned, arrival - cutoff_h, np.nan), cell_m=cell,
                        wind_u=u, wind_v=v, slope=slope)
        yield Window(fire=event["id"], record=record, cutoff_utc=cutoff_utc, cutoff_h=cutoff_h, lead_h=int(lead_h),
                     transform=tuple(float(x) for x in event["transform"]), epsg=int(event["epsg"]),
                     synthetic=bool(event.get("synthetic", False)), inputs=inputs,
                     outcome_h=np.where(final, arrival - cutoff_h, np.inf), domain=scored)


def load_windows(root, event_id: str, lead_h: int, *, inputs: bool = True, allow_test: bool = False,
                 splits: dict | None = None, domain: str = "headline") -> Iterator[Window]:
    """Windows of one fire from the real data root. Checks the root, the split and the static layers now; reads
    the weather band of each cutoff lazily. ``inputs=False`` skips wind and slope (distance-only baselines)."""
    root = data_root(root)
    arrival, event = read_arrival(event_id, root, allow_test=allow_test, splits=splits)
    record = check_access(event_id, allow_test=allow_test, splits=splits)
    slope = read_layer(root, event, SLOPE) if inputs else None
    wind_at = weather_reader(root, event) if inputs else None
    return windows_from_arrays(event, arrival, lead_h, record=record, slope=slope, wind_at=wind_at, domain=domain)


class WindowSource:
    """Re-iterable windows of several fires, re-read from the data root on every pass (bounded memory)."""

    def __init__(self, root, fires: list[str], lead_h: int, **options):
        self.root, self.fires, self.lead_h, self.options = data_root(root), list(fires), lead_h, options

    def __iter__(self) -> Iterator[Window]:
        for fire in self.fires:
            yield from load_windows(self.root, fire, self.lead_h, **self.options)


def check_event(root: Path, event_id: str, *, allow_test: bool = False, splits: dict | None = None) -> dict:
    """Exact window counts and headline-domain sizes of one fire (the data check of DATA_NOTES.md section 7)."""
    arrival, event = read_arrival(event_id, root, allow_test=allow_test, splits=splits)
    final = np.isfinite(arrival)
    cell = abs(float(event["transform"][0]))
    row = dict(id=event_id, cells=int(arrival.size), final_perimeter_cells=int(final.sum()))
    if final.any():
        domain = headline_domain(final, cell)
        row.update(headline_cells=int(domain.sum()), ring_cells=int((domain & ~final).sum()),
                   ring_cells_off_grid=ring_cells_off_grid(final, cell))
    for lead in LEADS_H:
        row[f"windows_{lead:g}h"] = len(window_cutoffs(arrival, event, lead))
    return row


def case_seed(base: int, fire: str, cutoff_utc: str) -> int:
    """Per-window seed, the formula of ``wildfire.cumulative_report.case_seed`` (that module needs torch): every
    model gets the same seed for the same window, independent of run order."""
    payload = json.dumps([int(base), fire, cutoff_utc], separators=(",", ":")).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "little")


def run_record(config: dict, seed: int | None = None) -> dict:
    """Provenance of a result row: git commit (and whether the tree is dirty), host, Python, UTC time, seed, config."""
    def git(*args):
        try:
            return subprocess.run(["git", "-C", str(sp.REPO), *args], capture_output=True, text=True,
                                  check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    status = git("status", "--porcelain")
    return dict(commit=git("rev-parse", "HEAD"), dirty=None if status is None else bool(status),
                host=platform.node(), python=platform.python_version(),
                utc=datetime.now(timezone.utc).isoformat(timespec="seconds"), seed=seed, config=config)


def main(argv: list[str] | None = None, *, splits: dict | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exact window counts and headline-domain sizes per fire "
                                                 "(real data only; no fallback).")
    parser.add_argument("--data-root", default=None, help=f"the real data root (default: ${ENV_VAR})")
    parser.add_argument("--allow-test", action="store_true",
                        help="also read the test fires (only at a milestone Siyeong approved)")
    parser.add_argument("--out", default=None, help="write the JSON here instead of stdout")
    args = parser.parse_args(argv)
    root = data_root(args.data_root)
    splits = splits or sp.load_splits()
    ids = sp.fires("dev", splits=splits) + (sp.fires("test", splits=splits) if args.allow_test else [])
    rows = [check_event(root, i, allow_test=args.allow_test, splits=splits) for i in ids]
    config = dict(data_root=str(root), allow_test=args.allow_test, buffer_m=HEADLINE_BUFFER_M,
                  leads_h=list(LEADS_H), spacing_h=sp.WINDOW_SPACING_H)
    text = json.dumps(dict(run_record(config), rows=rows), indent=1)
    if args.out:
        Path(args.out).write_text(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except DataRootNotFound as error:
        sys.exit(f"error: {error}")
