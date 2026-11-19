#!/usr/bin/env python3
"""Hourly issued-forecast inputs at the ten burden points (PROTOCOL.md section 6, target A).

    python3 burden_hours.py --nwp NWP_DIR/gfs_KOR --seasons 2021 2022 2023 2024 2025 --out derived/burden_hours.csv.gz

Per KST hour of 1 Feb to 15 May: window maxima of gust and 850 hPa wind, window minimum of 2 m relative humidity (valid
hours t+1..t+8 of cycle floor6(t - 5 h), four lattice points; kcf-abstain/kcf-aloft rule, imported), and g_k2, the level
of kcf-aloft's gust rule G (G fires when g_k2 >= 20 m/s). Hours with a missing lead are kept with NaN.
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kcf-aloft"))
from burden import POINTS, season_days  # noqa: E402
from rules import Store, level  # noqa: E402

GUST, U850, V850, RH = range(4)     # field order of fetch_burden.py


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
            for k in range(24):
                t = day - pd.Timedelta(hours=9) + pd.Timedelta(hours=k)
                for name, (prov, lat, lon) in POINTS.items():
                    b, c = st.window(t, lat, lon)
                    r = dict(season=year, kst_day=day.strftime("%Y-%m-%d"), kst_hour=k, point=name, t_utc=str(t), lon=lon,
                             gust_ms=math.nan, w850_ms=math.nan, rhmin_pct=math.nan, g_k2=math.nan)
                    if b is not None and not np.isnan(b).any():
                        g = b[:, GUST]
                        r.update(gust_ms=float(g.max()), w850_ms=float(np.hypot(b[:, U850], b[:, V850]).max()),
                                 rhmin_pct=float(b[:, RH].min()), g_k2=level(g.max(axis=1), 2))
                    rows.append(r)
        print(year, "done", flush=True)
    out = pd.DataFrame(rows).round(4)
    out.to_csv(a.out, index=False)
    print(len(out), "rows;", int(out.gust_ms.notna().sum()), "with forecast")


if __name__ == "__main__":
    main()
