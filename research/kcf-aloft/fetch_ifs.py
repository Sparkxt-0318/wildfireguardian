#!/usr/bin/env python3
"""Fetch issued ECMWF IFS open-data forecasts over Korea by byte range (PROTOCOL.md section 5). No value is interpreted.

    python3 fetch_ifs.py --out NWP_DIR --ranges 2025-03-19T00:2025-04-01T00 [...] --seasons 2023 2024 2025

Cycles 00/06/12/18 UTC (oper for 00/12, scda for 06/18), steps 6, 9, 12, 15, 18 h. Fields: u and v at 850 hPa, and
10fg (maximum 10 m gust since the previous step) where the file has it. Kept on the model's own lattice (0.4 deg in
2023, 0.25 deg later) inside 32.8-39.2 N, 124.8-131.2 E.
Output: OUT/ifs_KOR/<YYYYMMDDHH>.npz with arr[step, field, lat, lon] (NaN = missing), steps, lat (ascending), lon,
res; OUT/ifs_KOR/log.jsonl.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kcf-abstain"))
from fetch_nwp import get  # noqa: E402
from fetch_gfs import season_range  # noqa: E402

B = "https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com"
STEPS = [6, 9, 12, 15, 18]
FIELDS = ["u", "v", "10fg"]
BOX = (32.8, 39.2, 124.8, 131.2)
LAYOUTS = [("ifs/0p25", 0.25), ("0p25", 0.25), ("ifs/0p4-beta", 0.4), ("0p4-beta", 0.4)]


def layout_of(cyc):
    """The layout this cycle is stored in (first that has the 6 h index); one layout per cycle, never mixed."""
    d, hh = cyc[:8], cyc[8:10]
    stream = "oper" if hh in ("00", "12") else "scda"
    for _ in range(2):
        for lay, r in LAYOUTS:
            if get(f"{B}/{d}/{hh}z/{lay}/{stream}/{d}{hh}0000-{STEPS[0]}h-{stream}-fc.index", attempts=3) is not None:
                return lay, r
    return None, None


def one(cyc, step, lay, res):
    import pygrib
    d, hh = cyc[:8], cyc[8:10]
    stream = "oper" if hh in ("00", "12") else "scda"
    base = f"{B}/{d}/{hh}z/{lay}/{stream}/{d}{hh}0000-{step}h-{stream}-fc"
    idx = get(base + ".index", attempts=5)
    if idx is None:
        return step, None, "no_index", 0, res
    ent = [json.loads(x) for x in idx.decode().splitlines() if x.strip()]
    out, miss, nb, grid = {}, [], 0, None
    for f in FIELDS:
        e = [x for x in ent if x.get("param") == f and (f == "10fg" or x.get("levelist") == "850")]
        if not e:
            if f != "10fg":
                miss.append(f)
            continue
        b = get(base + ".grib2", (e[0]["_offset"], e[0]["_offset"] + e[0]["_length"] - 1))
        if not b:
            miss.append(f + "(fetch)")
            continue
        nb += len(b)
        m = pygrib.fromstring(b)
        if grid is None:
            la, lo = m.latlons()
            la, lo = la[:, 0], np.where(lo[0, :] < 0, lo[0, :] + 360.0, lo[0, :])
            ii = np.flatnonzero((la >= BOX[0]) & (la <= BOX[1]))
            jj = np.flatnonzero((lo >= BOX[2]) & (lo <= BOX[3]))
            ii = ii[np.argsort(la[ii])]
            jj = jj[np.argsort(lo[jj])]
            grid = (la[ii], lo[jj], ii, jj)
        out[f] = np.ma.filled(m.values.astype(np.float64), np.nan)[np.ix_(grid[2], grid[3])]
    if grid is None:
        return step, None, ";".join(miss) or "no_field", nb, res
    arr = np.full((len(FIELDS), grid[0].size, grid[1].size), np.nan, np.float32)
    for k, f in enumerate(FIELDS):
        if f in out:
            arr[k] = out[f]
    return step, (arr, np.round(grid[0], 4), np.round(grid[1], 4)), ";".join(miss), nb, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--ranges", nargs="*", default=[])
    ap.add_argument("--seasons", nargs="*", type=int, default=[])
    ap.add_argument("--procs", type=int, default=5)
    ap.add_argument("--retry-missing", action="store_true", help="fetch again the cycles whose last log line has a missing step")
    a = ap.parse_args()
    d = os.path.join(a.out, "ifs_KOR")
    os.makedirs(d, exist_ok=True)
    spans = [(pd.Timestamp(r[:13]), pd.Timestamp(r[14:])) for r in a.ranges] + [season_range(y) for y in a.seasons]
    cyc = []
    for s, e in spans:
        for c in pd.date_range(s.floor("6h"), e, freq="6h", inclusive="left"):
            k = c.strftime("%Y%m%d%H")
            if k not in cyc:
                cyc.append(k)
    if a.retry_missing and os.path.exists(os.path.join(d, "log.jsonl")):
        last = {}
        for l in open(os.path.join(d, "log.jsonl")):
            r = json.loads(l)
            last[r["cycle"]] = r
        for c, r in last.items():
            if r["missing"] and c in cyc and os.path.exists(os.path.join(d, c + ".npz")):
                os.remove(os.path.join(d, c + ".npz"))
    todo = [c for c in cyc if not os.path.exists(os.path.join(d, c + ".npz"))]
    print(f"ifs KOR: {len(cyc)} cycles, {len(todo)} to fetch", flush=True)
    with ProcessPoolExecutor(a.procs) as ex:
        for c in todo:
            t0 = time.time()
            res = {}
            lay, r0 = layout_of(c)
            if lay is None:
                with open(os.path.join(d, "log.jsonl"), "a") as fh:
                    fh.write(json.dumps(dict(cycle=c, missing={s: "no_layout" for s in STEPS}, bytes=0, saved=False, res=None,
                                             seconds=round(time.time() - t0, 1),
                                             fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))) + "\n")
                print(c, "no layout found", flush=True)
                continue
            for f in as_completed([ex.submit(one, c, s, lay, r0) for s in STEPS]):
                step, got, m, b, r = f.result()
                res[step] = (got, m, b, r)
            ok = [s for s in STEPS if res[s][0] is not None]
            miss = {s: res[s][1] for s in STEPS if res[s][1]}
            nb = sum(res[s][2] for s in STEPS)
            if ok:
                la, lo = res[ok[0]][0][1], res[ok[0]][0][2]
                arr = np.full((len(STEPS), len(FIELDS), la.size, lo.size), np.nan, np.float32)
                for s in ok:
                    arr[STEPS.index(s)] = res[s][0][0]
                np.savez_compressed(os.path.join(d, c + ".npz"), arr=arr, steps=np.array(STEPS), lat=la, lon=lo,
                                    res=res[ok[0]][3], fields=np.array(FIELDS))
            with open(os.path.join(d, "log.jsonl"), "a") as fh:
                fh.write(json.dumps(dict(cycle=c, missing=miss, bytes=nb, saved=bool(ok), res=res[ok[0]][3] if ok else None,
                                         seconds=round(time.time() - t0, 1),
                                         fetched_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))) + "\n")
            print(c, f"{nb/1e6:.1f} MB", f"{time.time()-t0:.1f}s", "missing " + json.dumps(miss) if miss else "", flush=True)


if __name__ == "__main__":
    main()
