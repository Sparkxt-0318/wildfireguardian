#!/usr/bin/env python3
"""Burden set: rule levels at ten fixed points on every day of the spring seasons (PROTOCOL.md section 1b).

    python3 burden.py --nwp NWP_DIR/gfs_KOR --seasons 2021 2022 2023 2024 2025 --out derived/burden_days.csv.gz

One row per point and KST day: the day's largest value of every rule level over its 24 issue hours (so a rule
"level >= threshold at some issue hour of the day" can be read off for any threshold), the number of issue hours
that could be evaluated, and the same for the coarse sampling of S5 (1 deg points, leads 6, 12, 18 h).
"""
import argparse
import math

import numpy as np
import pandas as pd

from rules import GUST, LEVEL_COLS, U850, V850, Store, cycle_of, window_levels

POINTS = {  # PROTOCOL.md section 1b
    "Sokcho": ("Gangwon", 38.2509, 128.5647), "Gangneung": ("Gangwon", 37.7709, 128.8681),
    "Taebaek": ("Gangwon", 37.1703, 128.9893), "Chuncheon": ("Gangwon", 37.9000, 127.7333),
    "Wonju": ("Gangwon", 37.4381, 127.9604), "Uljin": ("Gyeongbuk", 37.0000, 129.4167),
    "Yeongdeok": ("Gyeongbuk", 36.5333, 129.4094), "Pohang": ("Gyeongbuk", 36.0333, 129.3833),
    "Andong": ("Gyeongbuk", 36.5667, 128.7000), "Sangju": ("Gyeongbuk", 36.4167, 128.1500)}
COARSE_LEADS = (6, 12, 18)


def season_days(year):
    return pd.date_range(f"{year}-02-01", f"{year}-05-15", freq="1D")


def coarse_levels(store, t, lat, lon):
    """S5 sampling of the same forecasts: the four 1 deg points around the place, valid times of (t, t+8 h] whose
    lead is 6, 12 or 18 h. Returns (max gust, max 850 hPa wind) or (nan, nan)."""
    t = pd.Timestamp(t)
    c = cycle_of(t)
    z = store.load(c.strftime("%Y%m%d%H"))
    if z is None:
        return math.nan, math.nan
    arr, leads, la, lo = z
    first = int((t - c) / pd.Timedelta(hours=1)) + 1
    use = [L for L in range(first, first + 8) if L in COARSE_LEADS]
    li = [int(np.flatnonzero(leads == L)[0]) for L in use]
    i0, j0 = math.floor(lat), math.floor(lon)
    ii = [int(np.flatnonzero(np.isclose(la, x))[0]) for x in (i0, i0 + 1)]
    jj = [int(np.flatnonzero(np.isclose(lo, x))[0]) for x in (j0, j0 + 1)]
    b = arr[li][:, :, ii][:, :, :, jj].astype(float)
    g = b[:, GUST]
    w = np.hypot(b[:, U850], b[:, V850])
    return (float(g.max()) if not np.isnan(g).any() else math.nan,
            float(w.max()) if not np.isnan(w).any() else math.nan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nwp", required=True)
    ap.add_argument("--seasons", nargs="+", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    st = Store(a.nwp)
    rows = []
    for year in a.seasons:
        for day in season_days(year):
            hours = [day - pd.Timedelta(hours=9) + pd.Timedelta(hours=k) for k in range(24)]   # KST 00..23 in UTC
            for name, (prov, lat, lon) in POINTS.items():
                lv = [window_levels(st, t, lat, lon) for t in hours]
                cg = [coarse_levels(st, t, lat, lon) for t in hours]
                r = dict(season=year, kst_day=day.strftime("%Y-%m-%d"), point=name, province=prov)
                ok = [x for x in lv if x["fc_note"] == ""]
                r["hours_evaluated"] = len(ok)
                for c in LEVEL_COLS:
                    v = [x[c] for x in ok]
                    r[c] = round(max(v), 4) if v else math.nan
                h = [x["hgt850_m"] for x in lv if not math.isnan(x["hgt850_m"])]
                r["hgt850_m"] = round(float(np.median(h)), 1) if h else math.nan
                cgv = [x[0] for x in cg if not math.isnan(x[0])]
                cwv = [x[1] for x in cg if not math.isnan(x[1])]
                r["coarse_hours"] = len(cwv)
                r["coarse_g_k1"] = round(max(cgv), 4) if cgv else math.nan
                r["coarse_w_k1"] = round(max(cwv), 4) if cwv else math.nan
                rows.append(r)
        print(year, "done", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(a.out, index=False)
    print(out.groupby("season").agg(point_days=("point", "size"), complete=("hours_evaluated", lambda s: int((s == 24).sum())),
                                    none=("hours_evaluated", lambda s: int((s == 0).sum()))).to_string())


if __name__ == "__main__":
    main()
