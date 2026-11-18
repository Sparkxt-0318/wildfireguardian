#!/usr/bin/env python3
"""Assemble numbers.json, the per-hour table and the forecast-fetch provenance from the analysis outputs.

    python3 make_numbers.py --abstain derived/abstain_numbers.json --evt derived/evt.json \
        --hours derived/hours_full.csv.gz --nwp NWP_DIR --out numbers.json --hours-out derived/hours.csv.gz
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

KEEP = ["fire", "name", "product", "role", "country", "model", "t_utc", "kst_hour", "lat", "lon", "cycle_utc",
        "gust_ms", "w850_ms", "rhmin_pct", "hdw", "prior3_km", "p_gust_ms", "p_w850_ms", "p_rhmin_pct", "p_hdw",
        "p_prior3_km", "score", "abstain", "min_predictor", "score_two_sided", "abstain_two_sided", "score_gfs_only",
        "abstain_gfs_only", "reach5_km", "reach8_km", "R_km_5", "R_km_8", "held5", "held8", "fc_note"]


def fetch_summary(nwp):
    out = {}
    for d in sorted(Path(nwp).glob("*_*")):
        log = d / "log.jsonl"
        if not log.exists():
            continue
        L = [json.loads(x) for x in open(log)]
        out[d.name] = dict(cycles=len(L), first_cycle=min(x["cycle"] for x in L), last_cycle=max(x["cycle"] for x in L),
                           cycles_with_missing=[x["cycle"] for x in L if x["missing"]],
                           gigabytes=round(sum(x["bytes"] for x in L) / 1e9, 2),
                           fetched_utc=[min(x["fetched_utc"] for x in L), max(x["fetched_utc"] for x in L)],
                           source=("https://noaa-gfs-bdp-pds.s3.amazonaws.com gfs.YYYYMMDD/HH/atmos/gfs.tHHz.pgrb2.0p25.fFFF"
                                   if d.name.startswith("gfs") else
                                   "https://noaa-hrrr-bdp-pds.s3.amazonaws.com hrrr.YYYYMMDD/conus/hrrr.tHHz.wrfsfcfFF.grib2"),
                           byte_ranges="from the .idx file of each forecast hour; 7 fields; leads 6-18 h")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--abstain", required=True)
    ap.add_argument("--evt", required=True)
    ap.add_argument("--hours", required=True)
    ap.add_argument("--nwp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hours-out", required=True)
    a = ap.parse_args()
    A = json.load(open(a.abstain))
    E = json.load(open(a.evt))
    df = pd.read_csv(a.hours, low_memory=False)
    fs = fetch_summary(a.nwp)
    json.dump(fs, open(Path(a.hours_out).parent / "forecast_fetch_log.json", "w"), indent=1)

    nb = dict(
        meta=dict(A["meta"], labels="MEASURED = computed here or reused from a committed file; ASSUMED = input, proxy "
                                    "or simplification. No reanalysis was used, so nothing is ASSUMED PERFECT FORECAST.",
                  forecast=dict(gfs="issued GFS 0.25 deg, cycles 00/06/12/18 UTC, assumed available 5 h after the cycle, "
                                    "leads 6-18 h (fires with issue hours from 2021-01-01)",
                                hrrr="issued HRRR 3 km box-averaged to the 0.25 deg lattice, same cycles, delay and leads "
                                     "(US fires before 2021)", hdw="surface form, ASSUMED simplification",
                                fetch=fs),
                  products=dict(GOFER="hourly GOFER perimeters, kcf-margin reach reused (MEASURED)",
                                DET="25 March 2025 FIRMS VIIRS + AHI detection union, kcf-margin reach reused "
                                    "(detections, not perimeters: ASSUMED proxy)",
                                CHOI="Choi et al. 2026 kriged arrival rasters (retrospective reconstruction, smooth in "
                                     "time), reach computed here (MEASURED on the reconstruction)")),
        calibration_lofo=dict(primary=A["calibration_lofo_primary"], S1_two_sided=A["calibration_lofo_S1_two_sided"],
                              S2_gfs_only=A["calibration_lofo_S2_gfs_only"]),
        calibration_not_scored=A["calibration_not_scored"],
        thresholds_for_test_fires=A["thresholds_for_test_fires"],
        test_groups=A["test_groups"], test_fires=A["test_fires"], test_fires_not_tested=A["test_fires_not_tested"],
        march25=dict(hours=A["march25_hours"],
                     hours_10_20_kst=[r for r in A["march25_hours"] if 10 <= r["kst_hour"] <= 20],
                     choi_raster_same_hours=A["march25_choi_hours"]),
        S3_product_crosscheck=A["S3_product_crosscheck"],
        tail_evt=dict((k, v) for k, v in E.items() if not k.startswith("profile_")))
    json.dump(nb, open(a.out, "w"), indent=1, default=float)

    keep = [c for c in KEEP if c in df.columns]
    h = df[keep].copy()
    for c in h.columns:
        if h[c].dtype.kind == "f":
            h[c] = h[c].round(5)
    h.to_csv(a.hours_out, index=False)
    print("numbers.json written;", len(h), "hour rows")


if __name__ == "__main__":
    main()
