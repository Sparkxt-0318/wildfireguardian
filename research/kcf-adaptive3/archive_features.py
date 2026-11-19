#!/usr/bin/env python3
"""Issued-forecast day features for the archive fire-days, and the archive run-day propensity (PROTOCOL 1.2, 2.1).

    python3 archive_features.py --gfs GFS_DIR            # adds gust_ms, w850_ms, rhmin_pct to derived/archive_days.csv.gz
    python3 archive_features.py --fit                    # writes derived/archive_propensity.json

Day features: the 8 three-hourly valid times of the local solar day (start = 00 local = day 00 UTC - lon/15 h), each
from the most recent 00/12 UTC cycle at lead 6 to 15 h, four lattice points around the day's centroid; maximum gust,
maximum 850 hPa wind speed, minimum 2 m relative humidity. GlobFire's burn date is taken as the local day (ASSUMED).
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
F = HERE / "derived" / "archive_days.csv.gz"
LEADS = (6, 9, 12, 15)


def source(v):
    """valid time (Timestamp on the 3 h grid) -> (cycle string, lead index)."""
    h = v.hour
    if h in (6, 9, 12, 15):
        c, lead = v.floor("D"), h
    elif h in (18, 21):
        c, lead = v.floor("D") + pd.Timedelta(hours=12), h - 12
    else:
        c, lead = v.floor("D") - pd.Timedelta(hours=12), h + 12
    return c.strftime("%Y%m%d%H"), LEADS.index(lead)


def features(gfs):
    d = pd.read_csv(F)
    start = pd.to_datetime(d.day) - pd.to_timedelta(d.lon / 15.0, unit="h")
    first = start.dt.ceil("3h")
    need = defaultdict(list)
    for i, f in enumerate(first):
        for k in range(8):
            c, li = source(f + pd.Timedelta(hours=3 * k))
            need[c].append((li, i, k))
    r0 = np.floor((90.0 - d.lat.values) / 0.25).astype(int)
    c0 = np.floor((d.lon.values % 360) / 0.25).astype(int)
    out = np.full((len(d), 8, 3), np.nan)
    for n, (c, lst) in enumerate(sorted(need.items())):
        p = Path(gfs) / f"{c}.npz"
        if not p.exists():
            continue
        arr = np.load(p)["arr"].astype(np.float32)
        li, i, k = (np.array(x) for x in zip(*lst))
        blk = np.stack([arr[li, :, r0[i] + a, (c0[i] + b) % 1440] for a in (0, 1) for b in (0, 1)])   # 4, n, 3
        out[i, k, 0] = blk[:, :, 0].max(0)
        out[i, k, 1] = blk[:, :, 1].max(0)
        out[i, k, 2] = blk[:, :, 2].min(0)
        if n % 100 == 0:
            print(n, c, flush=True)
    ok = ~np.isnan(out).any(axis=(1, 2))
    d["gust_ms"] = np.where(ok, out[:, :, 0].max(1), np.nan)
    d["w850_ms"] = np.where(ok, out[:, :, 1].max(1), np.nan)
    d["rhmin_pct"] = np.where(ok, out[:, :, 2].min(1), np.nan)
    d.round(4).to_csv(F, index=False)
    print("fire-days", len(d), "with forecast", int(ok.sum()))


def fit():
    from sklearn.linear_model import LogisticRegression
    d = pd.read_csv(F).dropna(subset=["gust_ms", "w850_ms", "rhmin_pct"])
    X = d[["gust_ms", "w850_ms", "rhmin_pct"]].values
    mu, sd = X.mean(0), X.std(0)
    w = 1.0 / d.groupby("fire").fire.transform("size").values          # each fire weight 1
    lr = LogisticRegression(C=1.0, max_iter=2000).fit((X - mu) / sd, d.run.values, sample_weight=w * len(w) / w.sum())
    res = dict(mu=mu.tolist(), sd=sd.tolist(), b0=float(lr.intercept_[0]), b=lr.coef_[0].tolist(),
               fire_days=int(len(d)), fires=int(d.fire.nunique()), run_days=int(d.run.sum()),
               run_share_fire_weighted=float((w * d.run).sum() / w.sum()), inputs=["gust_ms", "w850_ms", "rhmin_pct"])
    json.dump(res, open(HERE / "derived" / "archive_propensity.json", "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gfs")
    ap.add_argument("--fit", action="store_true")
    a = ap.parse_args()
    if a.gfs:
        features(a.gfs)
    if a.fit:
        fit()
