"""Real data root access. Fails loudly when the root is absent and never falls back.

The real root (``events.json`` + ``regions/<id>/arrival_time_hours.tif`` ...) lives on Siyeong's Mac.
``forecast/data/environment`` in this repo holds ``events.json`` only and is rejected on purpose.

Data check (exact window counts and headline-domain sizes; docs/DATA_NOTES.md section 7):

    python -m firecast_lab.data --data-root PATH [--allow-test] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from firecast_lab import splits as sp
from firecast_lab.domain import HEADLINE_BUFFER_M, headline_domain, ring_cells_off_grid

ENV_VAR = "FIRECAST_DATA_ROOT"
LEADS_H = (24.0, 12.0)


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


def read_arrival(event_id: str, root: Path, *, allow_test: bool = False,
                 splits: dict | None = None) -> tuple[np.ndarray, dict]:
    """Reconstructed arrival in hours since the event's t0 (NaN where the raster's nodata tag says NoData; valid
    US values can be negative) and the event's catalog record. The raster must sit on the event grid."""
    import rasterio

    check_access(event_id, allow_test=allow_test, splits=splits)
    events = {e["id"]: e for e in json.loads((root / "events.json").read_text())}
    if event_id not in events:
        raise DataRootNotFound(f"data root not found: {event_id} is missing from {root / 'events.json'}")
    event = events[event_id]
    path = root / event["arrival_path"]
    if not path.is_file():
        raise DataRootNotFound(f"data root not found: missing {path}")
    with rasterio.open(path) as src:
        if (src.crs is None or src.crs.to_epsg() != event["epsg"] or src.shape != (event["height"], event["width"])
                or not np.allclose(tuple(src.transform)[:6], event["transform"])):
            raise ValueError(f"{path} is not on the event grid of {event_id}")
        arrival = src.read(1, masked=True).astype(np.float64).filled(np.nan)
    arrival[~np.isfinite(arrival)] = np.nan
    return arrival, event


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
