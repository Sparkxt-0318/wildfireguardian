#!/usr/bin/env python3
"""The four forecast predictors at every issue hour (PROTOCOL.md section 3).

    python3 predictors.py --hours derived/hours_base.csv.gz --nwp NWP_DIR --out derived/hours_pred.csv.gz

Cycle c(t) = latest 00/06/12/18 UTC cycle with c + 5 h <= t; valid hours t+1..t+8 (leads 6-18 h); the four 0.25 deg
lattice points at the corners of the lattice cell containing P_t; max/min over points x hours. A predictor is NaN
(and the reason recorded) if any of its values is missing; nothing is filled.
"""
import argparse
import math
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

DELAY_H = 5
WINDOW_H = 8
# field order in fetch_nwp.py
GUST, TMP, RH, U10, V10, U850, V850 = range(7)


def cycle_of(t):
    c = t - pd.Timedelta(hours=DELAY_H)
    return c.floor("6h")


def vpd_hpa(t_k, rh):
    tc = t_k - 273.15
    es = 6.112 * np.exp(17.67 * tc / (tc + 243.5))
    return es * (1.0 - rh / 100.0)


@lru_cache(maxsize=64)
def load(path):
    if not Path(path).exists():
        return None
    z = np.load(path)
    return z["arr"], z["leads"], z["lat"], z["lon"]


def one(row, nwp):
    t = pd.Timestamp(row.t_utc)
    c = cycle_of(t)
    path = str(Path(nwp) / f"{row.model}_{row.region}" / (c.strftime("%Y%m%d%H") + ".npz"))
    out = dict(cycle_utc=str(c), gust_ms=np.nan, w850_ms=np.nan, rhmin_pct=np.nan, hdw=np.nan, fc_note="")
    if not np.isfinite(row.lat):
        out["fc_note"] = "no_location"
        return out
    z = load(path)
    if z is None:
        out["fc_note"] = "no_cycle_file"
        return out
    arr, leads, lat, lon = z
    lon360 = row.lon % 360.0
    i = int(math.floor((row.lat - lat[0]) / 0.25 + 1e-9))
    j = int(math.floor((lon360 - lon[0]) / 0.25 + 1e-9))
    if not (0 <= i < lat.size - 1 and 0 <= j < lon.size - 1):
        out["fc_note"] = "outside_region"
        return out
    want = [int((t + pd.Timedelta(hours=k) - c) / pd.Timedelta(hours=1)) for k in range(1, WINDOW_H + 1)]
    li = [int(np.flatnonzero(leads == L)[0]) if (leads == L).any() else -1 for L in want]
    if min(li) < 0:
        out["fc_note"] = "lead_out_of_range"
        return out
    b = arr[li][:, :, i:i + 2, j:j + 2].astype(np.float64)  # [8 leads, 7 fields, 2, 2]
    notes = []

    def red(v, fn, name):
        if np.isnan(v).any():
            notes.append(name)
            return np.nan
        return float(fn(v))

    out["gust_ms"] = red(b[:, GUST], np.max, "gust")
    out["w850_ms"] = red(np.hypot(b[:, U850], b[:, V850]), np.max, "w850")
    out["rhmin_pct"] = red(b[:, RH], np.min, "rh")
    out["hdw"] = red(np.hypot(b[:, U10], b[:, V10]) * vpd_hpa(b[:, TMP], b[:, RH]), np.max, "hdw")
    out["fc_note"] = ("missing:" + ",".join(notes)) if notes else ""
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", required=True)
    ap.add_argument("--nwp", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    df = pd.read_csv(a.hours, low_memory=False)
    df["_c"] = [cycle_of(pd.Timestamp(t)) for t in df.t_utc]
    df = df.sort_values(["model", "region", "_c"]).reset_index(drop=True)
    res = [one(r, a.nwp) for r in df.itertuples(index=False)]
    out = pd.concat([df.drop(columns="_c"), pd.DataFrame(res)], axis=1)
    out.to_csv(a.out, index=False)
    print(out.groupby(["product", "role", "model"]).size().to_string())
    print("notes:", out.fc_note.replace("", "ok").value_counts().to_dict())


if __name__ == "__main__":
    main()
