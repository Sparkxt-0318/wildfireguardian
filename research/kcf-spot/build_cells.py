"""Step 3 data: for every fire, issue hour and lead, cells not yet burned within 15 km of the burned set, binned by
distance and angle to downwind, with the count lit by a spot in (t, t + h] (PROTOCOL 2.4).

Issue hours are the kcf-abstain forecast hours of the fire (GOFER / CHOI / DET product), which carry the issued gust.
B(t) = cells first marked by a look at or before t. Wind direction: ERA5 at hour t (ASSUMED as forecast direction).

    python build_cells.py --work WORK --wind derived/era5_wind.csv.gz --out WORK/cells.pkl
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spotlib as S  # noqa: E402

ABSTAIN = HERE.parent / "kcf-abstain/derived/hours.csv.gz"
XE = np.array([0.375, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0001])
AE = np.arange(0, 181, 30.0)
AE[-1] = 180.0001
LEADS = (1, 2, 3, 5, 8)
PRODUCT = {"CA": "GOFER", "KR": "CHOI", "DET": "DET"}


def load_fire(p):
    z = np.load(p, allow_pickle=False)
    return {k: z[k] for k in z.files}


def fire_rows(z, fire, region, hours, wind, conf_ids):
    first = z["first"].astype(np.float64)
    label = z["label"]
    sid = z["spot_id"]
    epoch = pd.Timestamp(str(z["epoch"]))
    spotborn = (label == S.SPOT) | (label == S.GROWTH)
    conf = spotborn & np.isin(sid, conf_ids)
    marked = np.isfinite(first)
    if not marked.any():
        return []
    t_first = first[marked].min()
    t_last = first[marked].max()
    w = wind[wind.fire == fire].set_index("t_utc")
    out = []
    H, W = first.shape
    rr, cc = np.mgrid[0:H, 0:W]
    prev_n, dist, ind = -1, None, None
    for _, hrow in hours.iterrows():
        tu = pd.Timestamp(hrow.t_utc)
        t = (tu - epoch).total_seconds() / 3600
        if t < t_first + S.MIN_AGE_H or t >= t_last:
            continue
        B = first <= t
        n = int(B.sum())
        if n != prev_n:
            d, ind = ndimage.distance_transform_edt(~B, return_indices=True)
            dist = d * S.CELL_KM
            prev_n = n
        wd = w["era5_dir_deg"].get(tu.floor("h"), np.nan)
        if not np.isfinite(wd):
            continue
        cand = (~B) & (dist >= XE[0]) & (dist < XE[-1])
        r, c = rr[cand], cc[cand]
        b = S.bearing_deg(r - ind[0][cand], c - ind[1][cand])
        a = S.angle_to_downwind(b, wd)
        xi = np.digitize(dist[cand], XE) - 1
        ai = np.digitize(a, AE) - 1
        key = xi * (len(AE) - 1) + ai
        nb = (len(XE) - 1) * (len(AE) - 1)
        N = np.bincount(key, minlength=nb)
        fc = first[cand]
        for h in LEADS:
            if t + h > t_last + 1e-9:
                continue
            lit = (fc > t) & (fc <= t + h)
            ya = np.bincount(key[lit & spotborn[cand]], minlength=nb)
            yc = np.bincount(key[lit & conf[cand]], minlength=nb)
            nz = np.flatnonzero(N)
            out.append(pd.DataFrame(dict(
                fire=fire, region=region, t_utc=str(tu), lead=h, xbin=(nz // (len(AE) - 1)).astype(np.int8),
                abin=(nz % (len(AE) - 1)).astype(np.int8), n=N[nz].astype(np.int32), y_all=ya[nz].astype(np.int32),
                y_conf=yc[nz].astype(np.int32), gust=np.float32(hrow.gust_ms), era5_dir=np.float32(wd),
                era5_ws=np.float32(w["era5_ws_ms"].get(tu.floor("h"), np.nan)))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--wind", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--regions", default="CA,KR,DET")
    a = ap.parse_args()
    hrs = pd.read_csv(ABSTAIN, low_memory=False, usecols=["fire", "product", "t_utc", "gust_ms"])
    wind = pd.read_csv(a.wind)
    wind["t_utc"] = pd.to_datetime(wind.t_utc)
    sp = pd.concat([pd.read_csv(p) for p in Path(a.work).glob("spots_*.csv") if p.stat().st_size > 1],
                   ignore_index=True)
    parts = []
    for region in a.regions.split(","):
        for p in sorted((Path(a.work) / region).glob("*.npz")):
            fire = p.stem
            hours = hrs[(hrs.fire == fire) & (hrs["product"] == PRODUCT[region]) & hrs.gust_ms.notna()]
            if not len(hours):
                print(region, fire, "no forecast hours", flush=True)
                continue
            s = sp[(sp.fire == fire) & (sp.region == region)]
            conf_ids = s[s.confirmed.astype(bool)].spot.values
            rows = fire_rows(load_fire(p), fire, region, hours, wind, conf_ids)
            if rows:
                df = pd.concat(rows, ignore_index=True)
                parts.append(df)
                print(region, fire, len(hours), "hours ->", len(df), "rows; lit all", int(df.y_all.sum()),
                      "conf", int(df.y_conf.sum()), flush=True)
    out = pd.concat(parts, ignore_index=True)
    out.to_pickle(a.out)
    print("rows", len(out))


if __name__ == "__main__":
    main()
