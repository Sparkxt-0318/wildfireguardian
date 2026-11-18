#!/usr/bin/env python3
"""Fetch issued GFS 0.25 deg forecasts over Korea by byte range (PROTOCOL.md section 2). No value is interpreted here.

    python3 fetch_gfs.py --out NWP_DIR --ranges 2025-03-20T00:2025-04-01T00 [more ranges] [--procs 4]
    python3 fetch_gfs.py --out NWP_DIR --seasons 2021 2022 2023 2024 2025

Cycles 00/06/12/18 UTC, lead hours 6..18, the kcf-abstain lattice (33-39 N, 125-131 E, 0.25 deg; its `get`, `lattice`
and index parsing are imported, not copied). Fields: GUST:surface, UGRD:850 mb, VGRD:850 mb at every lead, HGT:850 mb
at leads 6, 12 and 18. Output: OUT/gfs_KOR/<YYYYMMDDHH>.npz with arr[lead, field, lat, lon] float32 (NaN = missing)
and OUT/gfs_KOR/log.jsonl (one line per cycle: missing leads or fields, bytes, seconds, fetch time).
"""
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kcf-abstain"))
from fetch_nwp import STEP, get, lattice  # noqa: E402

FIELDS = [("GUST", "surface"), ("UGRD", "850 mb"), ("VGRD", "850 mb"), ("HGT", "850 mb")]
HGT_LEADS = (6, 12, 18)
LEADS = list(range(6, 19))
REGION = "KOR"
BUCKET = "https://noaa-gfs-bdp-pds.s3.amazonaws.com"


def urls(cyc, lead):
    d, h = cyc[:8], cyc[8:10]
    return [f"{BUCKET}/gfs.{d}/{h}/atmos/gfs.t{h}z.pgrb2.0p25.f{lead:03d}",   # GFS v16, from 2021-03-22 06 UTC
            f"{BUCKET}/gfs.{d}/{h}/gfs.t{h}z.pgrb2.0p25.f{lead:03d}"]          # before


def ranges_from_idx(text, want):
    L = [l.split(":") for l in text.strip().splitlines()]
    out = {}
    for i, l in enumerate(L):
        if len(l) < 6:
            continue
        key = (l[3], l[4])
        if key in want and key not in out and re.fullmatch(r"\d+ hour fcst", l[5].strip()):
            out[key] = (int(l[1]), int(L[i + 1][1]) - 1 if i + 1 < len(L) else None)
    return out


def one(cyc, lead):
    import pygrib
    lat, lon = lattice(REGION)
    out = np.full((len(FIELDS), lat.size, lon.size), np.nan, np.float32)
    want = [f for f in FIELDS if f[0] != "HGT" or lead in HGT_LEADS]
    u, idx = None, None
    for cand in urls(cyc, lead):
        idx = get(cand + ".idx", attempts=4)
        if idx is not None:
            u = cand
            break
    if idx is None:
        return lead, out, "no_idx", 0
    rg = ranges_from_idx(idx.decode("utf-8", "replace"), want)
    missing = [f"{a}:{b}" for a, b in want if (a, b) not in rg]
    with ThreadPoolExecutor(len(want)) as ex:
        futs = {f: ex.submit(get, u, rg[f]) for f in want if f in rg}
        blobs = {f: fu.result() for f, fu in futs.items()}
    rows = np.rint((90.0 - lat) / STEP).astype(int)
    cols = np.rint(lon / STEP).astype(int)
    nbytes = 0
    for f in want:
        b = blobs.get(f)
        if not b:
            if f in rg:
                missing.append(f"{f[0]}:{f[1]}(fetch)")
            continue
        nbytes += len(b)
        v = np.ma.filled(pygrib.fromstring(b).values.astype(np.float64), np.nan)
        out[FIELDS.index(f)] = v[np.ix_(rows, cols)]
    return lead, out, ";".join(missing), nbytes


def season_range(year):
    # issue hours 1 Feb 00 KST .. 15 May 23 KST = 31 Jan 15 UTC .. 15 May 14 UTC; c(t) = floor6(t - 5 h)
    return pd.Timestamp(f"{year}-01-31T06"), pd.Timestamp(f"{year}-05-15T12")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--ranges", nargs="*", default=[], help="START:END (UTC, END exclusive), e.g. 2025-03-20T00:2025-04-01T00")
    ap.add_argument("--seasons", nargs="*", type=int, default=[])
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    d = os.path.join(a.out, "gfs_KOR")
    os.makedirs(d, exist_ok=True)
    spans = []
    for r in a.ranges:
        s, e = r.rsplit(":", 1) if r.count(":") == 1 else (r[:13], r[14:])
        spans.append((pd.Timestamp(s), pd.Timestamp(e)))
    spans += [season_range(y) for y in a.seasons]
    cyc = []
    for s, e in spans:
        for c in pd.date_range(s.floor("6h"), e, freq="6h", inclusive="left"):
            k = c.strftime("%Y%m%d%H")
            if k not in cyc:
                cyc.append(k)
    todo = [c for c in cyc if not os.path.exists(os.path.join(d, c + ".npz"))]
    print(f"gfs KOR: {len(cyc)} cycles, {len(todo)} to fetch", flush=True)
    lat, lon = lattice(REGION)
    with ProcessPoolExecutor(a.procs) as ex:
        for c in todo:
            t0 = time.time()
            futs = [ex.submit(one, c, L) for L in LEADS]
            arr = np.full((len(LEADS), len(FIELDS), lat.size, lon.size), np.nan, np.float32)
            miss, nb = {}, 0
            for f in as_completed(futs):
                lead, o, m, b = f.result()
                arr[LEADS.index(lead)] = o
                nb += b
                if m:
                    miss[lead] = m
            np.savez_compressed(os.path.join(d, c + ".npz"), arr=arr, leads=np.array(LEADS), lat=lat, lon=lon,
                                fields=np.array([f"{x}:{y}" for x, y in FIELDS]))
            with open(os.path.join(d, "log.jsonl"), "a") as fh:
                fh.write(json.dumps(dict(cycle=c, missing=miss, bytes=nb, seconds=round(time.time() - t0, 1),
                                         fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))) + "\n")
            print(c, f"{nb/1e6:.1f} MB", f"{time.time()-t0:.1f}s", "missing" if miss else "", flush=True)


if __name__ == "__main__":
    main()
