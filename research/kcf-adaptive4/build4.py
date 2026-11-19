#!/usr/bin/env python3
"""Per-issue-hour geometry for kcf-adaptive4 (PROTOCOL sections 1 and 3).

Same reach rule and area curve as kcf-adaptive2/build_data.py, extended to every lead 1..8 h, plus the
start-area swap: reach measured from (K_t union E_t), where E_t is independent evidence of fire present at t
(California: FIRMS VIIRS detections; 25 March detection product: the Choi raster of KFS_01).

    python build4.py --gofer DATA/gofer/GOFER --choi DATA/choi --firms DATA/firms --out WORK
"""
import argparse
import importlib.util
import sys
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

NB = 160
PAD = NB
KS = (1, 3, 6, 12, 24)
LEADS = tuple(range(1, 9))
CELL2 = CELL_KM ** 2
CA_BOX = (-125.0, 32.0, -113.5, 42.6)


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def process(A, first, last, tstamp, hours=None, E=None, ev_sep=5.0):
    """A: int32 arrival hour index (NEVER = never). E: int32 evidence hour index on the same grid, or None.
    Returns rows and area curves (n x NB)."""
    H, W = A.shape
    Ap = np.full((H + 2 * PAD, W + 2 * PAD), NEVER, np.int32)
    Ap[PAD:PAD + H, PAD:PAD + W] = A
    rows, areas, ring = [], [], {}
    prev_n, dist, curve = -1, None, None
    prev_u, udist = -1, None
    if hours is None:
        hours = range(first, last - 1 + 1)
    for t in range(first, (max(hours) if len(hours) else first) + 1):
        known = A <= t
        n = int(known.sum())
        if n != prev_n:
            dp = ndimage.distance_transform_edt(~(Ap <= t)) * CELL_KM
            dist = dp[PAD:PAD + H, PAD:PAD + W].astype(np.float32)
            idx = np.ceil(dp[dp > 0] / CELL_KM - 1e-9).astype(np.int64)
            curve = np.cumsum(np.bincount(np.clip(idx, 0, NB + 1), minlength=NB + 2)[1:NB + 1]) * CELL2
            curve = curve.astype(np.float32)
            prev_n = n
        ring[t] = (dist, known)
        ring.pop(t - 26, None)
        if t not in hours:
            continue
        row = dict(t_idx=t, t_utc=str(tstamp(t)), area_known_km2=n * CELL2, age_h=t - first)
        for h in LEADS:
            if t + h <= last:
                new = (A > t) & (A <= t + h)
                rr, _, _ = component_reach(known, new, (5.0,), dist=dist)
                row[f"reach{h}_km"] = rr[5.0]
            else:
                row[f"reach{h}_km"] = np.nan
        if E is not None:
            ev = (E <= t) & ~known
            # evidence farther than the 5 km separate-fire rule from K_t is not this fire's front
            if ev_sep is not None:
                ev &= dist <= ev_sep
            ne = int(ev.sum())
            row["ev_cells"] = ne
            row["start_deficit_km"] = float(dist[ev].max()) if ne else 0.0
            if ne:
                union = known | ev
                u = int(union.sum()) * 1000003 + ne
                if u != prev_u:
                    udist = (ndimage.distance_transform_edt(~union) * CELL_KM).astype(np.float32)
                    prev_u = u
            for h in LEADS:
                if t + h <= last:
                    if ne:
                        new = (A > t) & (A <= t + h) & ~ev
                        # components are judged against K_t (same separate-fire rule), distance against the union
                        rr0, _, mask = component_reach(known, (A > t) & (A <= t + h), (5.0,), dist=dist)
                        m = mask & ~ev
                        row[f"sreach{h}_km"] = float(udist[m].max()) if m.any() else 0.0
                    else:
                        row[f"sreach{h}_km"] = row[f"reach{h}_km"]
                else:
                    row[f"sreach{h}_km"] = np.nan
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
        areas.append(curve)
    return rows, np.array(areas, np.float32)


def job_gofer(args):
    gofer_dir, name, firms_path = args
    import geopandas as gpd
    from pyproj import Transformer
    sg = _load(MARGIN / "score_gofer.py", "score_gofer")
    gdf = gpd.read_file(Path(gofer_dir) / "GOFER_Combined" / "GOFERC_fireProg.shp")
    gdf["t"] = pd.to_datetime(gdf["tUTC"])
    g = gdf[gdf.fname == name].sort_values("t").reset_index(drop=True)
    A, tf = sg.rasterise_arrival(g)
    T = len(g)
    first = int(A[A != NEVER].min())
    ts = [pd.Timestamp(x) for x in g["t"]]
    E = None
    if firms_path:
        f = pd.read_csv(firms_path)
        f["t"] = pd.to_datetime(f.t)
        f = f[(f.t >= ts[0] - pd.Timedelta(days=2)) & (f.t <= ts[-1])]
        x, y = Transformer.from_crs(4326, 3310, always_xy=True).transform(f.longitude.values, f.latitude.values)
        c, r = ~tf * (np.asarray(x), np.asarray(y))
        r, c = np.floor(r).astype(int), np.floor(c).astype(int)
        ok = (r >= 0) & (r < A.shape[0]) & (c >= 0) & (c < A.shape[1])
        tsv = np.array(ts, dtype="datetime64[ns]")
        k = np.searchsorted(tsv, f.t.values.astype("datetime64[ns]"), side="left")  # first hour index >= acquisition
        E = np.full(A.shape, NEVER, np.int32)
        for ri, ci, ki in zip(r[ok], c[ok], k[ok]):
            if ki < E[ri, ci]:
                E[ri, ci] = ki
    rows, areas = process(A, first, T - 1, lambda t: ts[t], E=E)
    return name, "GOFER", rows, areas


def choi_arrival(path):
    import rasterio
    with rasterio.open(path) as ds:
        v = ds.read(1, masked=True)
        tags = ds.tags()
        tf, crs = ds.transform, ds.crs
    toa = np.ma.filled(v.astype(float), np.nan)
    t0 = pd.Timestamp(tags["t0_utc"])
    return toa, t0, tf, crs


def job_choi(args):
    path, eid = args
    toa, t0, _, _ = choi_arrival(path)
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
    if last - 1 < first:
        return eid, "CHOI", [], np.zeros((0, NB), np.float32)
    rows, areas = process(A, first, last, lambda t: base + pd.Timedelta(hours=int(t)))
    return eid, "CHOI", rows, areas


def job_det(args):
    small, ahi, choi_path = args
    from pyproj import Transformer
    from rasterio.transform import rowcol
    sk = _load(MARGIN / "score_gyeongbuk.py", "score_gyeongbuk")
    A, src, meta = sk.build_arrival(small, ahi)
    end = int(sk.hour_index(sk.AHI_END))
    t_first = int(sk.hour_index(pd.Timestamp("2025-03-24 15:00")))
    first = int(A[A != NEVER].min())
    hours = set(range(t_first, t_first + 24))
    # evidence: the Choi raster of KFS_01 sampled at the centres of the detection grid
    toa, t0, tf, crs = choi_arrival(choi_path)
    x0, y1 = meta["x0"], meta["y1"]
    Hh, Ww = A.shape
    xs = x0 + (np.arange(Ww) + 0.5) * sk.CELL
    ys = y1 - (np.arange(Hh) + 0.5) * sk.CELL
    X, Y = np.meshgrid(xs, ys)
    if crs is not None and crs.to_epsg() != 5179:
        X, Y = Transformer.from_crs(5179, crs, always_xy=True).transform(X, Y)
    rr, cc = rowcol(tf, X.ravel(), Y.ravel())
    rr, cc = np.asarray(rr), np.asarray(cc)
    ok = (rr >= 0) & (rr < toa.shape[0]) & (cc >= 0) & (cc < toa.shape[1])
    val = np.full(X.size, np.nan)
    val[ok] = toa[rr[ok], cc[ok]]
    hrs = np.ceil(val + sk.hour_index(t0) - 1e-9)
    E = np.where(np.isfinite(hrs), hrs, NEVER).astype(np.int64).reshape(A.shape)
    E = np.clip(E, np.iinfo(np.int32).min, NEVER).astype(np.int32)
    rows, areas = process(A, first, end, lambda t: sk.T0 + pd.Timedelta(hours=int(t)), hours=hours, E=E, ev_sep=None)   # the Choi raster is this fire by construction
    return "KFS_01", "DET", rows, areas


def firms_ca(firms_dir, out):
    """All VIIRS detections (confidence not low) in the California box, 2019-2021, one small file."""
    fr = []
    for p in sorted(Path(firms_dir).glob("viirs-*_United_States.csv")):
        d = pd.read_csv(p, usecols=["latitude", "longitude", "acq_date", "acq_time", "confidence"])
        d = d[(d.longitude >= CA_BOX[0]) & (d.longitude <= CA_BOX[2]) & (d.latitude >= CA_BOX[1])
              & (d.latitude <= CA_BOX[3]) & (d.confidence != "l")]
        d["t"] = pd.to_datetime(d.acq_date + " " + d.acq_time.astype(str).str.zfill(4), format="%Y-%m-%d %H%M")
        d["sat"] = p.name.split("_")[0]
        fr.append(d[["latitude", "longitude", "t", "sat"]])
        print(p.name, len(d), flush=True)
    f = pd.concat(fr, ignore_index=True)
    f.to_csv(out, index=False)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gofer", required=True)
    ap.add_argument("--choi", required=True)
    ap.add_argument("--firms", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None, help="gofer|choi|det")
    ap.add_argument("--part", default=None, help="i/n: run the i-th of n slices of the job list, serially")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    hrs = pd.read_csv(ABSTAIN / "derived/hours.csv.gz", low_memory=False)
    gof = sorted(hrs[hrs["product"] == "GOFER"].fire.unique())
    kr = sorted(hrs[(hrs["product"] == "CHOI") & (hrs.role == "test") & (hrs.country == "KR")].fire.unique())
    fca = None
    if a.firms and a.only in (None, "gofer"):
        fca = out / "firms_ca.csv.gz"
        if not fca.exists():
            firms_ca(a.firms, fca)
        fca = str(fca)
    jobs = []
    if a.only in (None, "gofer"):
        jobs += [(job_gofer, (a.gofer, n, fca)) for n in gof]
    if a.only in (None, "choi"):
        jobs += [(job_choi, (str(Path(a.choi) / "rasters_kr" / f"{e}_pswt_ok_toa.tif"), e)) for e in kr]
    if a.only in (None, "det"):
        jobs.append((job_det, (str(REPO / "research/harness-2026-11/data-fetch/small/firms"),
                               str(REPO / "research/harness-2026-11/data-fetch-2/ahi_kfs01"),
                               str(Path(a.choi) / "rasters_kr" / "KFS_01_pswt_ok_toa.tif"))))
    allrows, curves = [], []
    suffix = f"_{a.only}" if a.only else ""
    if a.part:
        i, n = (int(x) for x in a.part.split("/"))
        jobs = jobs[i::n]
        suffix += f"_{i}of{n}"
    for f, ar in jobs:            # serial: process pools are not available in this sandbox
        fire, prod, rows, areas = f(ar)
        for r in rows:
            r["fire"], r["product"] = fire, prod
        allrows += rows
        curves.append(areas)
        print(f"{prod:6s} {fire:44s} hours {len(rows)}", flush=True)
    df = pd.DataFrame(allrows)
    cur = np.concatenate(curves)
    df.to_csv(out / f"hours_geom{suffix}.csv.gz", index=False)
    np.save(out / f"areacurve{suffix}.npy", cur)
    print("rows", len(df), cur.shape)


if __name__ == "__main__":
    main()
