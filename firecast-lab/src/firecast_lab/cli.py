"""``firecast-lab`` command line. Real data only: every command checks the data root first and never falls back.

    firecast-lab run --baseline X --split dev [--members 64] [--coupling shared|copula --length-cells L]
        cross-fitted run of one baseline (persistence, dilation, calibrated_dilation, logistic, c651); one score
        row per window, with commit, seed, config and host, in firecast-lab/results/<baseline>.csv
    firecast-lab time-c651 --fire ID [--members 256]
        times c651 on one fire's first window(s) and extrapolates the dev run: do this before any full c651 run

CPU-heavy runs go through the bench lock: ``python program/benchlock.py --label NAME -- firecast-lab run ...``.
The test split needs ``--allow-test`` (milestones only, after Siyeong approves); the fresh holdout is refused.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from itertools import islice
from pathlib import Path

from firecast_lab import baselines as bl
from firecast_lab import harness
from firecast_lab import splits as sp
from firecast_lab.data import (DOMAINS, ENV_VAR, DataRootNotFound, WindowSource, data_root, load_windows,
                               read_arrival, run_record, window_cutoffs)
from firecast_lab.members import COUPLINGS

RESULTS = sp.LAB / "results"
PROVENANCE = ("commit", "dirty", "host", "seed", "config")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="firecast-lab", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="cross-fitted baseline run -> results/<baseline>.csv")
    run.add_argument("--baseline", required=True, choices=bl.BASELINES)
    run.add_argument("--split", required=True, choices=("dev", "test"))
    run.add_argument("--allow-test", action="store_true", help="read test fires (milestones only, Siyeong approves)")
    run.add_argument("--lead", type=int, default=24, help="lead hours: 24 is the headline, 12 a diagnostic")
    run.add_argument("--members", type=int, default=64, help="K, matched across baselines")
    run.add_argument("--coupling", choices=COUPLINGS, default="shared")
    run.add_argument("--length-cells", type=float, default=None, help="declared copula correlation length (cells)")
    run.add_argument("--domain", choices=DOMAINS, default="headline")
    run.add_argument("--batch-size", type=int, default=32, help="c651 trajectory batch size (changes the members)")
    timing = sub.add_parser("time-c651", help="time c651 on one fire before any full run")
    timing.add_argument("--fire", required=True)
    timing.add_argument("--windows", type=int, default=1, help="windows of the fire to time")
    timing.add_argument("--lead", type=int, default=24)
    timing.add_argument("--members", type=int, default=256)
    timing.add_argument("--batch-size", type=int, default=32)
    for p in (run, timing):
        p.add_argument("--data-root", default=None, help=f"the real data root (default: ${ENV_VAR})")
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--out", default=None, help="CSV path (default: firecast-lab/results/...)")
    return parser


def _write(path: Path, rows: list[dict], columns, provenance: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    extra = {k: json.dumps(provenance[k], sort_keys=True) if k == "config" else provenance[k] for k in PROVENANCE}
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*columns, *PROVENANCE])
        writer.writeheader()
        writer.writerows({**row, **extra} for row in rows)


def _synthetic_root(root: Path) -> bool:
    return any(e.get("synthetic", False) for e in json.loads((root / "events.json").read_text()))


def _run(args, splits: dict) -> Path:
    root = data_root(args.data_root)
    if args.split == "test" and not args.allow_test:
        raise PermissionError("the test split is read only at a milestone Siyeong approved (--allow-test)")
    if args.coupling == "copula" and args.length_cells is None:
        raise ValueError("--coupling copula needs a declared --length-cells")
    if args.out is None and _synthetic_root(root):
        raise ValueError("SYNTHETIC data root: pass --out; firecast-lab/results/ holds real-data rows only")
    config = dict(baseline=args.baseline, split=args.split, lead_h=args.lead, members=args.members,
                  coupling=args.coupling, length_cells=args.length_cells, domain=args.domain, data_root=str(root),
                  splits_sha256=hashlib.sha256(json.dumps(splits, sort_keys=True).encode()).hexdigest(),
                  **(dict(batch_size=args.batch_size) if args.baseline == "c651" else {}))

    def windows_of(fires):
        return WindowSource(root, fires, args.lead, allow_test=args.allow_test, splits=splits, domain=args.domain)

    options = dict(root=root, batch_size=args.batch_size) if args.baseline == "c651" else None
    rows = harness.run(args.baseline, args.split, windows_of, splits, K=args.members, seed=args.seed,
                       coupling=args.coupling, length_cells=args.length_cells, options=options)
    out = Path(args.out) if args.out else RESULTS / f"{args.baseline}.csv"
    _write(out, rows, harness.COLUMNS, run_record(config, args.seed))
    print(f"{len(rows)} windows -> {out}")
    return out


def _time_c651(args, splits: dict) -> Path:
    """Seconds per window at K members on one fire, and the dev run extrapolated by cells x windows."""
    from firecast_lab.c651 import C651

    root = data_root(args.data_root)
    windows = list(islice(load_windows(root, args.fire, args.lead, inputs=False, splits=splits), args.windows))
    if not windows:
        raise ValueError(f"{args.fire} has no {args.lead} h window")
    model = C651(root, batch_size=args.batch_size)
    start = time.perf_counter()
    model.load()
    load_s, start = time.perf_counter() - start, time.perf_counter()
    for w in windows:
        model.members(w, K=args.members, seed=args.seed)
    per_window = (time.perf_counter() - start) / len(windows)
    cells = windows[0].outcome_h.size
    cell_windows = 0
    for fire in sp.fires("dev", splits=splits):
        arrival, event = read_arrival(fire, root, splits=splits)
        cell_windows += arrival.size * len(window_cutoffs(arrival, event, args.lead))
    row = dict(fire=args.fire, members=args.members, batch_size=args.batch_size, lead_h=args.lead,
               windows_timed=len(windows), cells=cells, model_load_s=round(load_s, 3),
               seconds_per_window=round(per_window, 3), dev_cell_windows=cell_windows,
               extrapolated_dev_hours=round(per_window / cells * cell_windows / 3600.0, 2))
    config = dict(command="time-c651", **{k: row[k] for k in ("fire", "members", "batch_size", "lead_h",
                                                               "windows_timed")}, data_root=str(root))
    out = Path(args.out) if args.out else RESULTS / "c651_timing.csv"
    _write(out, [row], tuple(row), run_record(config, args.seed))
    print(json.dumps(row))
    return out


def main(argv: list[str] | None = None, *, splits: dict | None = None) -> Path:
    args = _parser().parse_args(argv)
    splits = splits or sp.load_splits()
    return _run(args, splits) if args.command == "run" else _time_c651(args, splits)


def console() -> None:
    """Entry point of the ``firecast-lab`` script: expected refusals print one line and exit non-zero."""
    try:
        main()
    except (DataRootNotFound, PermissionError, ModuleNotFoundError, ValueError) as error:
        sys.exit(f"error: {error}")


if __name__ == "__main__":
    console()
