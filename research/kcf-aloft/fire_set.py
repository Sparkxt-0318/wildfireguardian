#!/usr/bin/env python3
"""Fire set: hourly timeline of every Korean fire with its rule levels (PROTOCOL.md sections 1a, 2, 3; amendment 1).

    python3 fire_set.py --nwp NWP_DIR/gfs_KOR --out derived/fire_hours.csv.gz

Reach, position and issue hours come unchanged from research/kcf-abstain/derived/hours.csv.gz. One row per fire,
product timeline ("primary" or "choi") and UTC hour, from 24 h before the first issue hour to the last row.
Also checks that the window maxima computed here reproduce kcf-abstain's committed gust_ms and w850_ms.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from rules import LEVEL_COLS, RUN_KM, Store, window_levels

HERE = Path(__file__).resolve().parent
ABSTAIN = HERE.parent / "kcf-abstain" / "derived"
PRE_H = 24
DET_DAY = "2025-03-25"   # KST day on which the detection product is primary for KFS_01


def timelines():
    h = pd.read_csv(ABSTAIN / "hours.csv.gz", low_memory=False)
    k = h[h.country == "KR"].copy()
    k["t_utc"] = pd.to_datetime(k.t_utc)
    k["kst"] = k.t_utc + pd.Timedelta(hours=9)
    k["scored_abstain"] = k.score.notna()
    out = []
    for fire, g in k.groupby("fire", sort=True):
        choi = g[g["product"] == "CHOI"]
        det = g[g["product"] == "DET"]
        variants = {"choi": choi}
        if len(det):
            keep = choi[choi.kst.dt.strftime("%Y-%m-%d") != DET_DAY]
            variants["primary"] = pd.concat([keep, det])
        else:
            variants["primary"] = choi
        for name, v in variants.items():
            v = v.sort_values("t_utc").drop_duplicates("t_utc")
            first, last = v.t_utc.min(), v.t_utc.max()
            grid = pd.DataFrame({"t_utc": pd.date_range(first - pd.Timedelta(hours=PRE_H), last, freq="1h")})
            m = grid.merge(v[["t_utc", "product", "lat", "lon", "reach5_km", "gust_ms", "w850_ms", "scored_abstain"]],
                           on="t_utc", how="left")
            m["pre"] = m.t_utc < first
            m["in_gap"] = m["product"].isna() & ~m.pre          # an hour inside the fire with no row (not expected)
            p0 = v.iloc[0]
            m.loc[m.pre, ["lat", "lon"]] = [p0.lat, p0.lon]
            m[["lat", "lon"]] = m[["lat", "lon"]].ffill()
            m["issue"] = m.reach5_km.notna()
            m["run"] = m.issue & (m.reach5_km > RUN_KM)
            m["scored_abstain"] = m.scored_abstain.fillna(False).astype(bool)
            kst = m.t_utc + pd.Timedelta(hours=9)
            m["kst_day"] = kst.dt.strftime("%Y-%m-%d")
            m["kst_hour"] = kst.dt.hour
            m.insert(0, "timeline", name)
            m.insert(0, "name", g.name.iloc[0])
            m.insert(0, "fire", fire)
            out.append(m)
    return pd.concat(out, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nwp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--check-out", default=str(HERE / "derived" / "reproduction_check.json"))
    a = ap.parse_args()
    tl = timelines()
    st = Store(a.nwp)
    lv = pd.DataFrame([window_levels(st, r.t_utc, r.lat, r.lon) for r in tl.itertuples(index=False)])
    out = pd.concat([tl, lv], axis=1)
    # reproduction check against kcf-abstain's committed window maxima (predictors, not outcomes)
    c = out[out.gust_ms.notna()]
    dg = (c.g_k1 - c.gust_ms).abs()
    dw = (c.w_k1 - c.w850_ms).abs()
    chk = dict(rows_compared=int(len(c)), rows_without_levels=int(c.g_k1.isna().sum() + c.w_k1.isna().sum()),
               gust_max_abs_diff=float(dg.max()), w850_max_abs_diff=float(dw.max()),
               tolerance=0.001, passed=bool(dg.max() <= 0.001 and dw.max() <= 0.001 and c.g_k1.notna().all()))
    Path(a.check_out).parent.mkdir(exist_ok=True)
    json.dump(chk, open(a.check_out, "w"), indent=1)
    print("reproduction check:", chk)
    out["t_utc"] = out.t_utc.dt.strftime("%Y-%m-%d %H:%M:%S")
    for col in LEVEL_COLS + ["hgt850_m"]:
        out[col] = out[col].round(4)
    out.to_csv(a.out, index=False)
    print(out.groupby(["fire", "timeline"]).agg(hours=("t_utc", "size"), issue=("issue", "sum"),
                                                no_level=("g_k1", lambda s: int(s.isna().sum())),
                                                gaps=("in_gap", "sum")).to_string())


if __name__ == "__main__":
    main()
