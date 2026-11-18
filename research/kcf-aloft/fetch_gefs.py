#!/usr/bin/env python3
"""S5 (PROTOCOL.md section 6): the operational GEFS control forecast as issued, 1 deg, for the seasons 2019 and 2020.

    python3 fetch_gefs.py --out NWP_DIR --seasons 2019 2020

AWS noaa-gefs-pds, gec00 (control), leads 6, 12, 18 h: UGRD/VGRD 850 mb from pgrb2a, GUST:surface from pgrb2b.
Output: OUT/gefs_KOR/<YYYYMMDDHH>.npz with arr[lead, field, lat, lon] in the field order of fetch_gfs.py
(GUST, U850, V850, HGT850 = NaN), on the 1 deg lattice 33-39 N, 125-131 E; OUT/gefs_KOR/log.jsonl.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kcf-abstain"))
from fetch_nwp import get  # noqa: E402
from fetch_gfs import ranges_from_idx, season_range  # noqa: E402

B = "https://noaa-gefs-pds.s3.amazonaws.com"
LEADS = [6, 12, 18]
LAT = np.arange(33.0, 39.01, 1.0)
LON = np.arange(125.0, 131.01, 1.0)
PARTS = {"pgrb2a": [("UGRD", "850 mb"), ("VGRD", "850 mb")], "pgrb2b": [("GUST", "surface")]}
ORDER = [("GUST", "surface"), ("UGRD", "850 mb"), ("VGRD", "850 mb")]


def one(cyc, lead):
    import pygrib
    d, h = cyc[:8], cyc[8:10]
    out = np.full((4, LAT.size, LON.size), np.nan, np.float32)
    miss, nb = [], 0
    for part, want in PARTS.items():
        u = f"{B}/gefs.{d}/{h}/{part}/gec00.t{h}z.{part}f{lead:02d}"
        idx = get(u + ".idx", attempts=4)
        if idx is None:
            miss.append(part + ":no_idx")
            continue
        rg = ranges_from_idx(idx.decode("utf-8", "replace"), want)
        for f in want:
            if f not in rg:
                miss.append(f"{f[0]}:{f[1]}")
                continue
            b = get(u, rg[f])
            if not b:
                miss.append(f"{f[0]}:{f[1]}(fetch)")
                continue
            nb += len(b)
            m = pygrib.fromstring(b)
            la, lo = m.latlons()
            v = np.ma.filled(m.values.astype(float), np.nan)
            ii = [int(np.argmin(abs(la[:, 0] - x))) for x in LAT]
            jj = [int(np.argmin(abs(lo[0, :] - x))) for x in LON]
            assert abs(la[ii[0], 0] - LAT[0]) < 1e-6 and abs(lo[0, jj[0]] - LON[0]) < 1e-6, "not a 1 deg lattice"
            out[ORDER.index(f)] = v[np.ix_(ii, jj)]
    return lead, out, ";".join(miss), nb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seasons", nargs="+", type=int, required=True)
    a = ap.parse_args()
    d = os.path.join(a.out, "gefs_KOR")
    os.makedirs(d, exist_ok=True)
    cyc = []
    for y in a.seasons:
        s, e = season_range(y)
        cyc += [c.strftime("%Y%m%d%H") for c in pd.date_range(s, e, freq="6h", inclusive="left")]
    todo = [c for c in cyc if not os.path.exists(os.path.join(d, c + ".npz"))]
    print(f"gefs KOR: {len(cyc)} cycles, {len(todo)} to fetch", flush=True)

    def cycle(c):
        t0 = time.time()
        arr = np.full((len(LEADS), 4, LAT.size, LON.size), np.nan, np.float32)
        miss, nb = {}, 0
        for L in LEADS:
            _, o, m, b = one(c, L)
            arr[LEADS.index(L)] = o
            nb += b
            if m:
                miss[L] = m
        np.savez_compressed(os.path.join(d, c + ".npz"), arr=arr, leads=np.array(LEADS), lat=LAT, lon=LON)
        return dict(cycle=c, missing=miss, bytes=nb, seconds=round(time.time() - t0, 1),
                    fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    with ThreadPoolExecutor(8) as ex, open(os.path.join(d, "log.jsonl"), "a") as fh:
        for i, r in enumerate(ex.map(cycle, todo)):
            fh.write(json.dumps(r) + "\n")
            if r["missing"] or i % 100 == 0:
                print(r["cycle"], r["bytes"], "missing " + json.dumps(r["missing"]) if r["missing"] else "", flush=True)


if __name__ == "__main__":
    main()
