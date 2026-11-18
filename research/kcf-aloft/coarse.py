#!/usr/bin/env python3
"""S5 (PROTOCOL.md section 6), COARSE: seasons 2019 and 2020 from the GEFS control as issued (1 deg, leads 6/12/18 h),
and what the same coarse sampling does to GFS in 2021-2025. Never pooled with the primary counts; enters no verdict.

    python3 coarse.py --gefs NWP_DIR/gefs_KOR --burden derived/burden_days.csv.gz --out derived/coarse_s5.json
"""
import argparse
import json
import math

import numpy as np
import pandas as pd

from burden import POINTS, coarse_levels, season_days
from rules import A_CAL, Store

RULES = {"A-cal": ("w", A_CAL, True), "A25": ("w", 25.0, False), "A30": ("w", 30.0, False), "G k=1 (any time)": ("g", 20.0, False)}


def count(d, gcol, wcol):
    out = {}
    for n, (v, thr, strict) in RULES.items():
        x = d[wcol if v == "w" else gcol].values
        al = (x > thr) if strict else (x >= thr)
        per = {}
        for s, g in d.assign(al=al).groupby("season"):
            per[int(s)] = dict(days=int(g.kst_day.nunique()), alarm_point_days=int(g.al.sum()),
                               mean_per_point=round(float(g.al.sum()) / g.point.nunique(), 2),
                               days_any_point=int(g.groupby("kst_day").al.any().sum()))
        out[n] = per
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gefs", required=True)
    ap.add_argument("--burden", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    st = Store(a.gefs)
    rows = []
    for year in (2019, 2020):
        for day in season_days(year):
            hours = [day - pd.Timedelta(hours=9) + pd.Timedelta(hours=k) for k in range(24)]
            for name, (prov, lat, lon) in POINTS.items():
                v = np.array([coarse_levels(st, t, lat, lon) for t in hours])
                rows.append(dict(season=year, kst_day=day.strftime("%Y-%m-%d"), point=name,
                                 g_hours=int(np.isfinite(v[:, 0]).sum()), w_hours=int(np.isfinite(v[:, 1]).sum()),
                                 coarse_g_k1=round(float(np.nanmax(v[:, 0])), 4) if np.isfinite(v[:, 0]).any() else math.nan,
                                 coarse_w_k1=round(float(np.nanmax(v[:, 1])), 4) if np.isfinite(v[:, 1]).any() else math.nan))
    ge = pd.DataFrame(rows)
    ge.to_csv(a.out.replace("coarse_s5.json", "coarse_days_2019_2020.csv.gz"), index=False)
    okw = ge[ge.w_hours == 24]
    okg = ge[(ge.g_hours == 24) & (ge.w_hours == 24)]
    bd = pd.read_csv(a.burden)
    b = bd[(bd.hours_evaluated == 24) & (bd.coarse_hours == 24)]
    out = dict(
        label="COARSE: GEFS control as issued, 1 deg, leads 6/12/18 h; not pooled; no verdict",
        gefs_2019_2020=dict(point_days=int(len(ge)), point_days_wind_complete=int(len(okw)), point_days_gust_complete=int(len(okg)),
                            wind_rules=count(okw, "coarse_g_k1", "coarse_w_k1"),
                            gust_rule_on_days_with_gust=count(okg, "coarse_g_k1", "coarse_w_k1")["G k=1 (any time)"]),
        bridge_gfs_2021_2025=dict(
            note="same point-days; GFS read at 1 deg points and leads 6/12/18 h, against the full-resolution hourly reading",
            point_days=int(len(b)), coarse=count(b, "coarse_g_k1", "coarse_w_k1"), full_resolution=count(b, "g_k1", "w_k1")))
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(out["gefs_2019_2020"], indent=1)[:1500])


if __name__ == "__main__":
    main()
