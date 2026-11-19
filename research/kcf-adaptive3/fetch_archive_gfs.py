#!/usr/bin/env python3
"""Fetch issued GFS 0.25 deg global fields for the archive year (PROTOCOL.md section 1.2). No value is interpreted here.

Cycles 00 and 12 UTC, leads 6, 9, 12, 15 h, fields GUST:surface, UGRD/VGRD:850 mb (stored as speed), RH:2 m.
    python3 fetch_archive_gfs.py --out DIR --start 2021-01-01 --end 2022-01-02 [--procs 2]
Output: DIR/<YYYYMMDDHH>.npz with arr[lead, 3, 721, 1440] float16 (gust m/s, 850 hPa wind m/s, RH %), NaN = missing.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kcf-aloft"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kcf-abstain"))
from fetch_gfs import ranges_from_idx, urls  # noqa: E402
from fetch_nwp import get  # noqa: E402

FIELDS = [("GUST", "surface"), ("UGRD", "850 mb"), ("VGRD", "850 mb"), ("RH", "2 m above ground")]
LEADS = (6, 9, 12, 15)


def one(cyc, lead):
    import pygrib
    out = np.full((3, 721, 1440), np.nan, np.float16)
    u, idx = None, None
    for cand in urls(cyc, lead):
        idx = get(cand + ".idx", attempts=4)
        if idx is not None:
            u = cand
            break
    if idx is None:
        return lead, out, "no_idx", 0
    rg = ranges_from_idx(idx.decode("utf-8", "replace"), FIELDS)
    with ThreadPoolExecutor(4) as ex:
        blobs = {f: ex.submit(get, u, rg[f]) for f in FIELDS if f in rg}
        blobs = {f: fu.result() for f, fu in blobs.items()}
    if any(blobs.get(f) is None for f in FIELDS):
        return lead, out, "missing:" + ",".join(f[0] for f in FIELDS if blobs.get(f) is None), 0
    v = {f: np.ma.filled(pygrib.fromstring(blobs[f]).values.astype(np.float64), np.nan) for f in FIELDS}
    out[0] = v[FIELDS[0]]
    out[1] = np.hypot(v[FIELDS[1]], v[FIELDS[2]])
    out[2] = v[FIELDS[3]]
    return lead, out, "", sum(len(b) for b in blobs.values())


def cycle(args):
    cyc, d = args
    t0 = time.time()
    arr = np.full((len(LEADS), 3, 721, 1440), np.nan, np.float16)
    miss, nb = {}, 0
    for li, L in enumerate(LEADS):
        lead, o, m, b = one(cyc, L)
        arr[li] = o
        nb += b
        if m:
            miss[L] = m
    np.savez_compressed(os.path.join(d, cyc + ".npz"), arr=arr, leads=np.array(LEADS))
    return dict(cycle=cyc, missing=miss, bytes=nb, seconds=round(time.time() - t0, 1),
                fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--procs", type=int, default=2)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    cyc = [c.strftime("%Y%m%d%H") for c in pd.date_range(a.start, a.end, freq="12h", inclusive="left")]
    todo = [c for c in cyc if not os.path.exists(os.path.join(a.out, c + ".npz"))]
    print(f"{len(cyc)} cycles, {len(todo)} to fetch", flush=True)
    with ProcessPoolExecutor(a.procs) as ex:
        for r in ex.map(cycle, [(c, a.out) for c in todo]):
            with open(os.path.join(a.out, "log.jsonl"), "a") as fh:
                fh.write(json.dumps(r) + "\n")
            print(r["cycle"], f"{r['bytes']/1e6:.1f} MB", f"{r['seconds']}s", "missing" if r["missing"] else "", flush=True)


if __name__ == "__main__":
    main()
