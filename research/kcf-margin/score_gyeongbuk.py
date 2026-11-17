"""Gyeongbuk 2025 stress test inputs (PROTOCOL.md): hourly reach on 25 March 2025 KST from FIRMS VIIRS + Himawari AHI.

Never used to set R. Builds an arrival-hour raster on a 375 m EPSG:5179 grid:
  * FIRMS VIIRS S-NPP + NOAA-20, confidence != 'l', box lon 128.2-129.7 lat 36.1-36.8, from 2025-03-21; one cell each;
    arrival hour = ceil(acquisition time to the hour).
  * AHI (Japan area, 2 km) over the KFS_01 rectangle, 2025-03-24 06:00 - 03-25 18:00 UTC: hotspot if B07 >= 320 K and
    B07 - B14 >= 25 K in >= 2 scans of an hour [tau, tau+1); arrival hour = tau + 1; drawn as a square of the median
    pixel spacing (~2.1 km).
Hour index 0 = 2025-03-22 00:00 UTC. Issue hours = 25 March 00-23 KST = 24 Mar 15 UTC .. 25 Mar 14 UTC. An issue hour is
complete for horizon h only if t + h <= 25 Mar 18:00 UTC (end of AHI coverage); later hours are reported as truncated.

    python score_gyeongbuk.py --small ../harness-2026-11/data-fetch/small/firms --ahi ../harness-2026-11/data-fetch-2/ahi_kfs01 --out work/gyeongbuk_reach.csv
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from reach import CELL_KM, NEVER, component_reach, dist_km  # noqa: E402

CELL = CELL_KM * 1000
T0 = pd.Timestamp("2025-03-22 00:00")
BOX = (128.2, 36.1, 129.7, 36.8)
AHI_FILES = ("kfs01_ahi_20250324T06_20250324T18.npz", "kfs01_ahi_20250324T18_20250325T18.npz")
AHI_END = pd.Timestamp("2025-03-25 18:00")
B07_MIN, DIFF_MIN, MIN_SCANS = 320.0, 25.0, 2


def hour_index(ts):
    return ((ts - T0).total_seconds() / 3600)


def build_arrival(small, ahi_dir):
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, 5179, always_xy=True)
    bx0, by0 = tr.transform(BOX[0], BOX[1])
    bx1, by1 = tr.transform(BOX[2], BOX[3])
    x0, y1 = np.floor(min(bx0, bx1) / CELL) * CELL - 8 * CELL, np.ceil(max(by0, by1) / CELL) * CELL + 8 * CELL
    W = int((np.ceil(max(bx0, bx1) / CELL) * CELL + 8 * CELL - x0) / CELL)
    H = int((y1 - (np.floor(min(by0, by1) / CELL) * CELL - 8 * CELL)) / CELL)
    A = np.full((H, W), NEVER, np.int32)
    src = np.zeros((H, W), np.int8)  # 1 FIRMS, 2 AHI

    def put(r0, r1, c0, c1, k, s):
        r0, c0 = max(r0, 0), max(c0, 0)
        sub = A[r0:r1, c0:c1]
        m = sub > k
        sub[m] = k
        src[r0:r1, c0:c1][m] = s

    frames = [pd.read_csv(Path(small) / f) for f in ("viirs-snpp_2025_Republic_of_Korea.csv",
                                                     "viirs-jpss1_2025_Republic_of_Korea.csv")]
    df = pd.concat(frames, ignore_index=True)
    df["t"] = pd.to_datetime(df["acq_date"] + " " + df["acq_time"].astype(str).str.zfill(4), format="%Y-%m-%d %H%M")
    df = df[(df.longitude >= BOX[0]) & (df.longitude <= BOX[2]) & (df.latitude >= BOX[1]) & (df.latitude <= BOX[3])
            & (df.t >= "2025-03-21") & (df.t < "2025-03-27") & (df.confidence != "l")]
    x, y = tr.transform(df.longitude.values, df.latitude.values)
    n_firms = 0
    for xi, yi, ti in zip(x, y, df.t):
        k = int(np.ceil(hour_index(ti)))
        r, c = int((y1 - yi) // CELL), int((xi - x0) // CELL)
        put(r, r + 1, c, c + 1, k, 1)
        n_firms += 1
    half = None
    n_ahi = 0
    for f in AHI_FILES:
        z = np.load(Path(ahi_dir) / f)
        if half is None:
            from scipy.spatial import cKDTree
            P = np.c_[z["x5179"], z["y5179"]]
            half = float(np.median(cKDTree(P).query(P, 2)[0][:, 1])) / 2
        t = pd.to_datetime(z["scan_start_utc"])
        hot = (z["b07_K"] >= B07_MIN) & (z["b07_minus_b14_K"] >= DIFF_MIN)
        hr = t.floor("h")
        for tau in hr.unique():
            cnt = hot[np.asarray(hr == tau)].sum(axis=0)
            for p in np.flatnonzero(cnt >= MIN_SCANS):
                k = int(hour_index(tau)) + 1
                xs, ys = z["x5179"][p], z["y5179"][p]
                put(int((y1 - (ys + half)) // CELL), int((y1 - (ys - half)) // CELL) + 1,
                    int((xs - half - x0) // CELL), int((xs + half - x0) // CELL) + 1, k, 2)
                n_ahi += 1
    return A, src, dict(x0=x0, y1=y1, firms_detections=n_firms, ahi_pixel_hours=n_ahi, ahi_half_m=half)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", required=True)
    ap.add_argument("--ahi", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    A, src, meta = build_arrival(a.small, a.ahi)
    print(meta)
    end = int(hour_index(AHI_END))
    rows = []
    for kst in range(24):
        t = int(hour_index(pd.Timestamp("2025-03-24 15:00"))) + kst
        known = A <= t
        dist = dist_km(known)
        r3, _, _ = component_reach(A <= t - 3, (A > t - 3) & (A <= t), (5.0,))
        for h in (5, 8):
            new = (A > t) & (A <= t + h)
            r, _, _ = component_reach(known, new, (5.0, np.inf), dist=dist)
            rows.append(dict(kst_hour=kst, t_utc=str(T0 + pd.Timedelta(hours=t)), h=h, reach_km=r[5.0],
                             reach_nosep_km=r[np.inf], prior3_km=r3[5.0], known_cells=int(known.sum()),
                             complete=t + h <= end))
    df = pd.DataFrame(rows)
    df.to_csv(a.out, index=False)
    np.savez_compressed(Path(a.out).with_suffix(".arrival.npz"), A=A, src=src, **{k: v for k, v in meta.items()})
    print(df.to_string())


if __name__ == "__main__":
    main()
