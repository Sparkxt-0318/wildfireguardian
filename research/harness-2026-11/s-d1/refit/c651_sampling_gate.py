"""A1 §3.2 gate: can c651's cache sampling be reproduced from public inputs alone?

The c651 cache (prepared_all, metadata sha 6cd4ae58...) is not committed. Its committed totals are
(forecast/documents/weighted_stratified_split_20261009.json, frequencies.{train,validation}.base):
    train      199,185 rows, 64,420 positives, population weight 34,481,268.6405
    validation  49,900 rows, 16,099 positives, population weight  8,623,444.6375
(train/validation are a cell-hour re-split of the season-split train+validation rows, so only their SUM
is a property of the sampling: 249,085 rows, 80,519 positives, weight 43,104,713.2780).

Row selection in forecast/wildfire/prepare.py:prepare_event (lines 862-901) depends only on each event's
arrival raster, its events.json window, the kernel size and the two per-event negative limits:
    positives    = every eligible cell whose first burned snapshot is in 1..hours   (weight 1)
    contact negs = min(contact_limit, N_contact) draws, weight N_contact / n each   (sum = N_contact)
    cold negs    = min(no_contact_limit, N_cold) draws, weight N_cold / n each     (sum = N_cold)
Then rows whose full k x k ENVIRONMENT patch is invalid are dropped without refill (lines 958-962),
so committed totals equal the pre-filter totals only if no environment rejection occurred; otherwise
they are smaller. This script computes the pre-filter totals exactly (no random numbers are needed for
totals) using prepare.py's own season_split, mirroring lines 862-901 line by line, on the public Choi
rasters (Zenodo 10.5281/zenodo.21788344), which carry the same grids and t0_utc as events.json.

    python research/harness-2026-11/s-d1/refit/c651_sampling_gate.py --choi <unzipped archive> \
        [--kernel-size 9] [--contact-limit 5000] [--no-contact-limit 2000]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "forecast"))
from wildfire.prepare import season_split  # noqa: E402

COMMITTED = dict(rows=249085, positives=80519, weight=34481268.64050001 + 8623444.6375)
# native K-contact subset (>= 1 already-burned off-centre cell in the 9x9 window at t): train + validation,
# frequencies.{train,validation}.native_9x9 of the same document. It contains every contact negative and no
# cold negative, so its row count identifies the contact limit separately from the no-contact limit.
COMMITTED_NATIVE = dict(rows=158561 + 39776, positives=62397 + 15596, weight=5924361.291999999 + 1481807.708)


def event_totals(path, event, kernel_size, contact_limit, no_contact_limit):
    import rasterio
    from scipy.ndimage import minimum_filter
    radius = kernel_size // 2
    with rasterio.open(path) as source:  # prepare.py:862-864
        arrival = source.read(1, masked=True).filled(np.nan).astype(np.float32)
    finite = np.isfinite(arrival)
    neighborhood_known = minimum_filter(finite.astype("uint8"), size=kernel_size, mode="constant", cval=0) > 0
    offsets = np.ones((kernel_size, kernel_size), dtype=bool)
    offsets[radius, radius] = False
    neighbor_arrival = minimum_filter(np.where(finite, arrival, np.inf), footprint=offsets, mode="constant",
                                      cval=np.inf)
    start, end, origin = (pd.Timestamp(event[k]) for k in ("start_utc", "end_utc", "t0_utc"))
    hours = int((end - start).total_seconds() // 3600)
    elapsed = (start - origin).total_seconds() / 3600 + np.arange(hours + 1, dtype=np.float64)
    first_burn = np.searchsorted(elapsed, arrival, side="left")
    risk_lengths = np.minimum(first_burn, hours)
    cells_flat = np.flatnonzero(neighborhood_known)
    first = first_burn.ravel()[cells_flat]
    risk = risk_lengths.ravel()[cells_flat]
    positive = (first >= 1) & (first <= hours)
    negative_lengths = risk - positive.astype(np.int64)
    contact_start = np.searchsorted(elapsed[:-1], neighbor_arrival.ravel()[cells_flat], side="left")
    no_contact_lengths = np.minimum(contact_start, negative_lengths)
    contact_lengths = negative_lengths - no_contact_lengths
    n_pos = int(positive.sum())
    contact_pos = int((positive & (contact_start <= first - 1)).sum())  # burned neighbour at t = first-1
    n_contact_pop, n_cold_pop = int(contact_lengths.sum()), int(no_contact_lengths.sum())
    n_contact, n_cold = min(contact_limit, n_contact_pop), min(no_contact_limit, n_cold_pop)
    return dict(positives=n_pos, contact_population=n_contact_pop, cold_population=n_cold_pop,
                rows=n_pos + n_contact + n_cold,
                native_rows=contact_pos + n_contact, native_positives=contact_pos,
                native_weight=float(contact_pos + (n_contact_pop if n_contact else 0)),
                weight=float(n_pos + (n_contact_pop if n_contact else 0) + (n_cold_pop if n_cold else 0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--choi", type=Path, required=True)
    ap.add_argument("--kernel-size", type=int, default=9)
    ap.add_argument("--contact-limit", type=int, default=5000)
    ap.add_argument("--no-contact-limit", type=int, default=2000)
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("RESULTS_c651_sampling_gate.json"))
    args = ap.parse_args()
    catalog = json.loads((REPO / "forecast/data/environment/events.json").read_text())
    per_event, totals = {}, {}
    for event in catalog:
        split = season_split(event)
        sub = "rasters_kr" if event["id"].startswith("KFS_") else "rasters_us"
        path = args.choi / sub / f"{event['id']}_pswt_ok_toa.tif"
        t = event_totals(path, event, args.kernel_size, args.contact_limit, args.no_contact_limit)
        t["split"] = split
        per_event[event["id"]] = t
        agg = totals.setdefault(split, dict(rows=0, positives=0, weight=0.0, native_rows=0, native_positives=0,
                                            native_weight=0.0, events=0, events_with_rows=0))
        for k in ("rows", "positives", "weight", "native_rows", "native_positives", "native_weight"):
            agg[k] += t[k]
        agg["events"] += 1
        agg["events_with_rows"] += int(t["rows"] > 0)
    trval = {k: totals.get("train", {}).get(k, 0) + totals.get("validation", {}).get(k, 0)
             for k in ("rows", "positives", "weight", "native_rows", "native_positives", "native_weight")}
    verdict = dict(
        pre_filter_train_plus_validation=trval, committed_train_plus_validation=COMMITTED,
        rows_deficit=COMMITTED["rows"] - trval["rows"], positives_deficit=COMMITTED["positives"] - trval["positives"],
        weight_deficit=COMMITTED["weight"] - trval["weight"],
        committed_native=COMMITTED_NATIVE,
        native_rows_deficit=COMMITTED_NATIVE["rows"] - trval["native_rows"],
        native_positives_deficit=COMMITTED_NATIVE["positives"] - trval["native_positives"],
        native_weight_deficit=COMMITTED_NATIVE["weight"] - trval["native_weight"],
        exact_match=(trval["rows"] == COMMITTED["rows"] and trval["positives"] == COMMITTED["positives"]
                     and abs(trval["weight"] - COMMITTED["weight"]) < 1e-3),
        consistent_upper_bound=(trval["rows"] >= COMMITTED["rows"] and trval["positives"] >= COMMITTED["positives"]
                                and trval["weight"] >= COMMITTED["weight"] - 1e-3),
    )
    out = dict(kernel_size=args.kernel_size, contact_limit=args.contact_limit,
               no_contact_limit=args.no_contact_limit, totals_by_season_split=totals, verdict=verdict,
               per_event=per_event)
    print(json.dumps(dict(settings=[args.kernel_size, args.contact_limit, args.no_contact_limit],
                          totals=totals, verdict=verdict), indent=1))
    args.out.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
