#!/usr/bin/env python3
"""Build the per-issue-hour table for kcf-adaptive2 (PROTOCOL sections 1-2).

For every fire series (GOFER 28, Choi US/KR, DET 25 March) and every issue hour t from the fire's first arrival hour to
(last - 5): reach at 5 h and 8 h (kcf-margin rule, 5 km separate-fire rule, imported), own-past reach g1,g3,g6,g12,g24
(cells burned in (t-k, t] seen from K_{t-k}), area of K_t, hours since first perimeter, and (GOFER, KR, DET only) the
cumulative flagged-area curve A_t(q) at q = 0.375 km * 1..160 (exact, from the distance transform of K_t).

    python build_data.py --gofer DATA/gofer --choi DATA/choi --out WORK
"""
import argparse
import importlib.util
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
MARGIN = REPO / "research/kcf-margin"
ABSTAIN = REPO / "research/kcf-abstain"
sys.path.insert(0, str(MARGIN))
from reach import CELL_KM, NEVER, component_reach  # noqa: E402

NB = 160                      # area-curve bins: q = 0.375 * 1..160 = 60 km
PAD = NB
KS = (1, 3, 6, 12, 24)
CELL2 = CELL_KM ** 2


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def process(A, first, last, tstamp, with_area, hours=None):
    """A int32 arrival hour index (NEVER = never). Returns rows (list of dict) and area curves (n x NB float32)."""
    H, W = A.shape
    Ap = np.full((H + 2 * PAD, W + 2 * PAD), NEVER, np.int32) if with_area else None
    if with_area:
        Ap[PAD:PAD + H, PAD:PAD + W] = A
    rows, areas = [], []
    ring = {}
    prev_n, dist, curve = -1, None, None
    if hours is None:
        hours = range(first, last - 5 + 1)
    for t in range(first, (max(hours) if len(hours) else first) + 1):
        known = A <= t
        n = int(known.sum())
        if n != prev_n:
            if with_area:
                dp = ndimage.distance_transform_edt(~(Ap <= t)) * CELL_KM
                dist = dp[PAD:PAD + H, PAD:PAD + W].astype(np.float32)
                idx = np.ceil(dp[dp > 0] / CELL_KM - 1e-9).astype(np.int64)
                curve = np.cumsum(np.bincount(np.clip(idx, 0, NB + 1), minlength=NB + 2)[1:NB + 1]) * CELL2
                curve = curve.astype(np.float32)
            else:
                dist = (ndimage.distance_transform_edt(~known) * CELL_KM).astype(np.float32)
            prev_n = n
        ring[t] = (dist, known)
        ring.pop(t - 26, None)
        if t not in hours:
            continue
        r = {}
        for h in (5, 8):
            if t + h <= last:
                new = (A > t) & (A <= t + h)
                rr, _, _ = component_reach(known, new, (5.0,), dist=dist)
                r[h] = rr[5.0]
            else:
                r[h] = np.nan
        row = dict(t_idx=t, t_utc=str(tstamp(t)), reach5_km=r[5], reach8_km=r[8], area_known_km2=n * CELL2,
                   age_h=t - first)
        for k in KS:
            tk = t - k
            if tk >= first and tk in ring:
                dk, kk = ring[tk]
                new = (A > tk) & (A <= t)
                rr, _, _ = component_reach(kk, new, (5.0,), dist=dk)
                row[f"g{k}"] = rr[5.0]
            else:
                row[f"g{k}"] = 0.0
        rows.append(row)
        if with_area:
            areas.append(curve)
    return rows, (np.array(areas, np.float32) if with_area else None)


# ------------------------------------------------------------------ jobs
def job_gofer(args):
    gofer_dir, name = args
    import geopandas as gpd
    sg = _load(MARGIN / "score_gofer.py", "score_gofer")
    gdf = gpd.read_file(Path(gofer_dir) / "GOFER_Combined" / "GOFERC_fireProg.shp")
    gdf["t"] = pd.to_datetime(gdf["tUTC"])
    g = gdf[gdf.fname == name].sort_values("t").reset_index(drop=True)
    A, tf = sg.rasterise_arrival(g)
    T = len(g)
    first = int(A[A != NEVER].min())
    ts = [pd.Timestamp(x) for x in g["t"]]
    rows, areas = process(A, first, T - 1, lambda t: ts[t], True)
    return name, "GOFER", rows, areas


def job_choi(args):
    path, eid, with_area = args
    import rasterio
    with rasterio.open(path) as ds:
        v = ds.read(1, masked=True)
        tags = ds.tags()
    toa = np.ma.filled(v.astype(float), np.nan)
    t0 = pd.Timestamp(tags["t0_utc"])
    ok = np.isfinite(toa)
    base = t0.floor("h")
    off = (t0 - base).total_seconds() / 3600
    A = np.full(toa.shape, NEVER, np.int64)
    A[ok] = np.ceil(toa[ok] + off - 1e-9).astype(np.int64)
    shift = int(A[ok].min()) - 1
    A[ok] -= shift
    base = base + pd.Timedelta(hours=shift)
    A = A.astype(np.int32)
    first, last = int(A[ok].min()), int(A[ok].max())
    if last - 5 < first:
        return eid, "CHOI", [], None
    rows, areas = process(A, first, last, lambda t: base + pd.Timedelta(hours=int(t)), with_area)
    return eid, "CHOI", rows, areas


def job_det(args):
    small, ahi = args
    sk = _load(MARGIN / "score_gyeongbuk.py", "score_gyeongbuk")
    A, src, meta = sk.build_arrival(small, ahi)
    end = int(sk.hour_index(sk.AHI_END))
    t_first = int(sk.hour_index(pd.Timestamp("2025-03-24 15:00")))
    first = int(A[A != NEVER].min())
    hours = list(range(t_first, t_first + 24))
    rows, areas = process(A, first, end, lambda t: sk.T0 + pd.Timedelta(hours=int(t)), True, hours=set(hours))
    # age is relative to the first detection of the product; note the product starts 2025-03-21 (VIIRS)
    return "KFS_01", "DET", rows, areas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gofer", required=True)
    ap.add_argument("--choi", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None, help="gofer|choi|det")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    hrs = pd.read_csv(ABSTAIN / "derived/hours.csv.gz", low_memory=False)
    gof = sorted(hrs[hrs["product"] == "GOFER"].fire.unique())
    choi_fires = hrs[(hrs["product"] == "CHOI") & (hrs.role == "test")][["fire", "country"]].drop_duplicates()
    jobs = []
    if a.only in (None, "gofer"):
        jobs += [("gofer", job_gofer, (a.gofer, n)) for n in gof]
    if a.only in (None, "choi"):
        for eid, c in zip(choi_fires.fire, choi_fires.country):
            sub = "rasters_kr" if c == "KR" else "rasters_us"
            jobs.append(("choi", job_choi, (str(Path(a.choi) / sub / f"{eid}_pswt_ok_toa.tif"), eid, c == "KR")))
    if a.only in (None, "det"):
        jobs.append(("det", job_det, (str(REPO / "research/harness-2026-11/data-fetch/small/firms"),
                                       str(REPO / "research/harness-2026-11/data-fetch-2/ahi_kfs01"))))
    allrows, curves = [], []
    with ProcessPoolExecutor(4) as ex:
        futs = [(k, ex.submit(f, ar)) for k, f, ar in jobs]
        for k, fu in futs:
            fire, prod, rows, areas = fu.result()
            for r in rows:
                r["fire"], r["product"] = fire, prod
            allrows += rows
            if areas is not None:
                curves.append(areas)
            else:
                curves.append(np.full((len(rows), NB), np.nan, np.float32))
            print(f"{prod:6s} {fire:44s} hours {len(rows)}", flush=True)
    df = pd.DataFrame(allrows)
    cur = np.concatenate(curves) if curves else np.zeros((0, NB), np.float32)
    suffix = f"_{a.only}" if a.only else ""
    df.to_csv(out / f"hours_geom{suffix}.csv.gz", index=False)
    np.save(out / f"areacurve{suffix}.npy", cur)
    print("rows", len(df), cur.shape)


if __name__ == "__main__":
    main()
