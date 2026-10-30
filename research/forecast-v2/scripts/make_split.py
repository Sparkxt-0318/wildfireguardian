"""Write research/forecast-v2/SPLIT.json from the Zenodo event tables (run once, before any fit).

Usage: python research/forecast-v2/scripts/make_split.py ZENODO_EXTRACTED_DIR
"""
import csv
import json
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1])
out = Path(__file__).resolve().parents[1] / "SPLIT.json"
if out.exists():
    raise SystemExit("SPLIT.json already exists and is immutable")
us = list(csv.DictReader(open(root / "results/us_selection_29.csv")))
kr = [r for r in csv.DictReader(open(root / "results/kr_events_21.csv")) if r["produced"] == "1"]
us_by_year, kr_by_year = {}, {}
for r in us:
    us_by_year.setdefault(int(r["year"]), []).append(r["incident"])
for r in kr:
    kr_by_year.setdefault(int(r["start_date_kst"][:4]), []).append(r["id"])
fit_us = sorted(i for y in (2020, 2021, 2022, 2023) for i in us_by_year.get(y, []))
split = {
    "schema": "wfg.forecast-v2.split/1",
    "recorded_utc": datetime.now(timezone.utc).isoformat(),
    "recorded_before_any_fit": True,
    "immutable": "This file is never changed after the first fit. Any later change is a protocol deviation and must be reported as such.",
    "unit": "whole fire (all cells and intervals of one fire belong to one partition)",
    "sources": {
        "perimeters": "NIROPS v1, Mendeley 10.17632/95rj5d379g.1, archive SHA-256 b19fb16ce2792d9a9c01f1768d09962566b0f3cada8d1f23a9851ab3fce75615",
        "kriged_labels": "Zenodo 10.5281/zenodo.21788344, wildfire_toa_dataset_and_code.zip SHA-256 612edf5f879d8fe874ae20e9d49d0be5de477e6f8c3101b434f1642d5b19ebad",
    },
    "fit": {
        "us_perimeter_and_kriged": fit_us,
        "korean_kriged_only": sorted(i for y in (2020, 2021, 2022, 2023) for i in kr_by_year.get(y, [])),
        "note": "The archive contains no 2023 US fire; US fit years are therefore 2020 to 2022. Korean 2022 and 2023 fires have no perimeter series and enter only the mixed kriged-label regime.",
    },
    "development_folds": {
        "rule": "leave-one-year-out over the US fit fires; Korean fit fires stay in every training fold of the mixed regime and are never a validation fold",
        "folds": {str(y): sorted(us_by_year[y]) for y in (2020, 2021, 2022)},
    },
    "held_out": {
        "us_2024": sorted(us_by_year[2024]),
        "korean_2024": sorted(kr_by_year.get(2024, [])),
        "korean_2025": sorted(kr_by_year[2025]),
        "rule": "No development decision (variant, hyperparameter, epoch, threshold, interval rule) may use any held-out fire. Held-out fires are scored once, after the configuration in this file and in the frozen run configuration is fixed.",
    },
    "intervals": {
        "definition": "consecutive distinct NIROPS survey times t1 < t2 of one fire component; the state at t is the union of that component's polygons with time <= t, rasterized at cell centres on the Zenodo 375 m grid",
        "inclusion": "0 < t2 - t1 <= 48 h, decided from timestamps only (label-free); longer intervals are excluded for compute reasons",
        "cells": "known cells of the full event rectangle outside the initial union; outside the endpoint union is a negative mapped-extent outcome",
        "environment": "covariates at floor_hour(t1), repeated over the interval unless a sample is explicitly flagged as hourly reanalysis weather",
    },
    "c651_training_overlap": "c651 was fit on cell-hours of KFS_02, KFS_03 and the 2020 to 2022 US fires listed above; no held-out fire entered its fitting, but its selection followed inspection of Wapiti and other test events, so c651 is not blind on the held-out set.",
}
split["sources"]["event_table_hashes"] = {
    name: hashlib.sha256((root / "results" / name).read_bytes()).hexdigest()
    for name in ("us_selection_29.csv", "kr_events_21.csv")
}
out.write_text(json.dumps(split, indent=2) + "\n")
print({k: len(v) for k, v in split["fit"].items() if isinstance(v, list)},
      {k: len(v) for k, v in split["held_out"].items() if isinstance(v, list)},
      {k: len(v) for k, v in split["development_folds"]["folds"].items()})
