#!/usr/bin/env python3
"""Per fire and issue hour: where the fire is (P_t), prior-3 h spread, and 5 h / 8 h reach (PROTOCOL.md sections 2-3).

    python3 fire_hours.py --gofer DIR/GOFER --choi DIR/x_choi --out derived/hours_base.csv.gz

Products:
  GOFER  28 calibration fires. Reach and prior-3 h spread reused from kcf-margin/derived/gofer_reach.csv.gz;
         P_t from the same EPSG:3310 375 m arrival raster kcf-margin built (its rasterise_arrival, imported).
  DET    25 March 2025 Gyeongbuk, kcf-margin/derived/gyeongbuk_reach.csv reused; P_t from the VIIRS part of the
         known set (FIRMS S-NPP + NOAA-20, confidence != 'l', kcf-margin box, one 375 m cell per detection,
         known from the whole hour after acquisition).
  CHOI   Choi et al. 2026 kriged arrival rasters; reach and prior-3 h spread computed here with kcf-margin's
         component_reach (5 km rule). Arrival hour a = ceil(t0 + TOA) on the UTC clock; issue hours run from the
         first to the last arrival hour minus h, as for GOFER.
"""
import argparse
import importlib.util
import json
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MARGIN = HERE.parent / "kcf-margin"
sys.path.insert(0, str(MARGIN))
from reach import NEVER, component_reach, dist_km  # noqa: E402

REPO = HERE.parent.parent
EVENTS = REPO / "forecast/data/environment/events.json"
FIRMS = REPO / "research/harness-2026-11/data-fetch/small/firms"
GOFER_2021 = 2021
CATALOG_IN_GOFER = {  # catalog id -> GOFER name (FIRES.md)
    "CA-BTU-009205_Dixie": "Dixie", "CA-KNF-006385_RiverComplex_RiverComplex": "River Complex",
    "CA-KNF-006454_Antelope": "Antelope", "CA-MNF-000753_AugustComplex": "August Complex",
    "CA-PNF-001308_PNFNorthComplex": "North Complex", "CA-SHF-001187_Monument": "Monument",
    "CA-SNF-001391_Creek": "Creek", "CA-SQF-002622_SQFComplex": "SQF Complex",
    "CA-SRF-000651_McCash": "McCash", "CA-SRF-000656_RedSalmonComplex": "Red Salmon Complex"}


def to_lonlat(x, y, epsg):
    from pyproj import Transformer
    tr = Transformer.from_crs(epsg, 4326, always_xy=True)
    return tr.transform(x, y)


def centroids_by_hour(A, xc, yc, hours):
    """Centroid (x, y) of {A <= t} for each t in `hours` (A int arrival index, NEVER = never)."""
    ok = A != NEVER
    a = A[ok].astype(np.int64)
    x, y = xc[ok], yc[ok]
    lo = a.min()
    n = int(max(hours) - lo + 1) if len(hours) else 0
    idx = np.clip(a - lo, 0, None)
    keep = idx < n
    cnt = np.cumsum(np.bincount(idx[keep], minlength=n))
    sx = np.cumsum(np.bincount(idx[keep], weights=x[keep], minlength=n))
    sy = np.cumsum(np.bincount(idx[keep], weights=y[keep], minlength=n))
    out = []
    for t in hours:
        k = int(t - lo)
        out.append((sx[k] / cnt[k], sy[k] / cnt[k]) if 0 <= k < n and cnt[k] > 0 else (math.nan, math.nan))
    return np.array(out)


# ---------------------------------------------------------------- GOFER
def gofer(gofer_dir):
    import geopandas as gpd
    spec = importlib.util.spec_from_file_location("score_gofer", MARGIN / "score_gofer.py")
    sg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sg)
    reach = pd.read_csv(MARGIN / "derived/gofer_reach.csv.gz")
    gdf = gpd.read_file(Path(gofer_dir) / "GOFER_Combined" / "GOFERC_fireProg.shp")
    gdf["t"] = pd.to_datetime(gdf["tUTC"])
    rows, checks = [], []
    for name, g in gdf.groupby("fname", sort=True):
        g = g.sort_values("t").reset_index(drop=True)
        A, tf = sg.rasterise_arrival(g)
        H, W = A.shape
        cols, rws = np.meshgrid(np.arange(W), np.arange(H))
        xc = tf.c + (cols + 0.5) * tf.a
        yc = tf.f + (rws + 0.5) * tf.e
        r = reach[reach.fire == name]
        piv = r.pivot_table(index="t_idx", columns="h", values="reach_km")
        hours = sorted(set(r[r.h.isin([5, 8])].t_idx))
        cen = centroids_by_hour(A, xc, yc, hours)
        lon, lat = to_lonlat(cen[:, 0], cen[:, 1], 3310)
        # consistency check against the committed reach (raster rebuilt identically?)
        rng = np.random.default_rng(1)
        for t in rng.choice(hours, size=min(3, len(hours)), replace=False):
            for h in (5, 8):
                if h in piv.columns and not np.isnan(piv.loc[t, h]):
                    known = A <= t
                    new = (A > t) & (A <= t + h)
                    rr, _, _ = component_reach(known, new, (5.0,))
                    checks.append(abs(rr[5.0] - piv.loc[t, h]))
        tt = dict(zip(r.t_idx, r.t))
        for i, t in enumerate(hours):
            p3 = piv.loc[t - 3, 3] if (t - 3) in piv.index and 3 in piv.columns else np.nan
            rows.append(dict(fire=name, product="GOFER", role="calibration", country="US",
                             t_utc=str(pd.Timestamp(tt[t])), lat=lat[i], lon=lon[i], prior3_km=p3,
                             reach5_km=piv.loc[t, 5] if 5 in piv.columns else np.nan,
                             reach8_km=piv.loc[t, 8] if 8 in piv.columns else np.nan,
                             model="gfs" if pd.Timestamp(tt[t]).year >= GOFER_2021 else "hrrr", region="WUS"))
        print(f"GOFER {name:24s} hours {len(hours)}", flush=True)
    return pd.DataFrame(rows), checks


# ---------------------------------------------------------------- DET (25 March 2025)
def det():
    spec = importlib.util.spec_from_file_location("score_gyeongbuk", MARGIN / "score_gyeongbuk.py")
    sk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sk)
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, 5179, always_xy=True)
    BOX, CELL, T0 = sk.BOX, sk.CELL, sk.T0
    bx0, by0 = tr.transform(BOX[0], BOX[1])
    bx1, by1 = tr.transform(BOX[2], BOX[3])
    x0 = np.floor(min(bx0, bx1) / CELL) * CELL - 8 * CELL
    y1 = np.ceil(max(by0, by1) / CELL) * CELL + 8 * CELL
    df = pd.concat([pd.read_csv(FIRMS / f) for f in ("viirs-snpp_2025_Republic_of_Korea.csv",
                                                     "viirs-jpss1_2025_Republic_of_Korea.csv")], ignore_index=True)
    df["t"] = pd.to_datetime(df["acq_date"] + " " + df["acq_time"].astype(str).str.zfill(4), format="%Y-%m-%d %H%M")
    df = df[(df.longitude >= BOX[0]) & (df.longitude <= BOX[2]) & (df.latitude >= BOX[1]) & (df.latitude <= BOX[3])
            & (df.t >= "2025-03-21") & (df.t < "2025-03-27") & (df.confidence != "l")]
    x, y = tr.transform(df.longitude.values, df.latitude.values)
    k = np.ceil((df.t - T0).dt.total_seconds().values / 3600).astype(int)
    r = ((y1 - y) // CELL).astype(int)
    c = ((x - x0) // CELL).astype(int)
    cells = pd.DataFrame(dict(r=r, c=c, k=k)).groupby(["r", "c"]).k.min().reset_index()
    cells["x"] = x0 + (cells.c + 0.5) * CELL
    cells["y"] = y1 - (cells.r + 0.5) * CELL
    g = pd.read_csv(MARGIN / "derived/gyeongbuk_reach.csv")
    rows = []
    for kst, d in g.groupby("kst_hour"):
        t = pd.Timestamp(d.t_utc.iloc[0])
        kt = int(round((t - T0).total_seconds() / 3600))
        K = cells[cells.k <= kt]
        lon, lat = (to_lonlat(K.x.mean(), K.y.mean(), 5179) if len(K) else (math.nan, math.nan))
        d5, d8 = d[d.h == 5].iloc[0], d[d.h == 8].iloc[0]
        rows.append(dict(fire="KFS_01", product="DET", role="test", country="KR", t_utc=str(t), kst_hour=int(kst),
                         lat=lat, lon=lon, viirs_cells=int(len(K)), prior3_km=d5.prior3_km,
                         reach5_km=d5.reach_km if d5.complete else np.nan,
                         reach8_km=d8.reach_km if d8.complete else np.nan,
                         complete5=bool(d5.complete), complete8=bool(d8.complete), model="gfs", region="KOR"))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- CHOI rasters
def choi_one(args):
    path, ev = args
    import rasterio
    with rasterio.open(path) as ds:
        v = ds.read(1, masked=True)
        tags = ds.tags()
        tf = ds.transform
        epsg = ds.crs.to_epsg()
    toa = np.ma.filled(v.astype(float), np.nan)
    t0 = pd.Timestamp(tags["t0_utc"])  # naive UTC, e.g. '2025-03-22 02:24:00' 
    ok = np.isfinite(toa)
    # arrival hour index on the UTC clock relative to the whole hour at or before t0
    base = t0.floor("h")
    off = (t0 - base).total_seconds() / 3600
    A = np.full(toa.shape, NEVER, np.int64)
    A[ok] = np.ceil(toa[ok] + off - 1e-9).astype(np.int64)
    shift = int(A[ok].min()) - 1
    A[ok] -= shift                      # keep indices small and positive
    base = base + pd.Timedelta(hours=shift)
    A = A.astype(np.int32)
    first, last = int(A[ok].min()), int(A[ok].max())
    H, W = A.shape
    cols, rws = np.meshgrid(np.arange(W), np.arange(H))
    xc = tf.c + (cols + 0.5) * tf.a
    yc = tf.f + (rws + 0.5) * tf.e
    hours = list(range(first, last - 5 + 1))
    rows = []
    if not hours:
        return ev["id"], rows, dict(first=str(base + pd.Timedelta(hours=first)), last=str(base + pd.Timedelta(hours=last)),
                                    cells=int(ok.sum()), epsg=epsg, t0=str(t0))
    cen = centroids_by_hour(A, xc, yc, hours)
    lon, lat = to_lonlat(cen[:, 0], cen[:, 1], epsg)
    dist_cache = {}

    def reach(t, h):
        known = A <= t
        if not known.any():
            return math.nan
        if t not in dist_cache:
            dist_cache.clear()
            dist_cache[t] = dist_km(known)
        new = (A > t) & (A <= t + h)
        r, _, _ = component_reach(known, new, (5.0,), dist=dist_cache[t])
        return r[5.0]

    for i, t in enumerate(hours):
        r5 = reach(t, 5)
        r8 = reach(t, 8) if t + 8 <= last else math.nan
        p3 = reach(t - 3, 3) if (A <= t - 3).any() else math.nan
        rows.append(dict(t_utc=str(base + pd.Timedelta(hours=t)), lat=lat[i], lon=lon[i], prior3_km=p3,
                         reach5_km=r5, reach8_km=r8))
    return ev["id"], rows, dict(first=str(base + pd.Timedelta(hours=first)), last=str(base + pd.Timedelta(hours=last)),
                                cells=int(ok.sum()), epsg=epsg, t0=str(t0))


def choi(choi_dir):
    events = {e["id"]: e for e in json.load(open(EVENTS))}
    jobs = []
    for eid, ev in events.items():
        sub = "rasters_kr" if eid.startswith("KFS") else "rasters_us"
        jobs.append((str(Path(choi_dir) / sub / f"{eid}_pswt_ok_toa.tif"), ev))
    out, meta = [], {}
    with ProcessPoolExecutor(3) as ex:
        for eid, rows, m in ex.map(choi_one, jobs):
            ev = events[eid]
            kr = eid.startswith("KFS")
            role = "s3" if eid in CATALOG_IN_GOFER else "test"
            model = "gfs" if (kr or ev["year"] >= 2021) else "hrrr"
            for r in rows:
                r.update(fire=eid, name=ev["name"], product="CHOI", role=role, country="KR" if kr else "US",
                         model=model, region="KOR" if kr else "WUS", gofer_name=CATALOG_IN_GOFER.get(eid, ""))
            out += rows
            meta[eid] = dict(m, hours=len(rows), role=role, model=model)
            print(f"CHOI {eid:42s} hours {len(rows):5d} {m['first']} .. {m['last']}", flush=True)
    return pd.DataFrame(out), meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gofer", required=True)
    ap.add_argument("--choi", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    g, checks = gofer(a.gofer)
    print(f"GOFER raster check: {len(checks)} (t, h) pairs recomputed, max |diff| = {max(checks):.6f} km", flush=True)
    d = det()
    c, meta = choi(a.choi)
    df = pd.concat([g, d, c], ignore_index=True)
    df.to_csv(a.out, index=False)
    json.dump(dict(gofer_raster_check_max_abs_km=float(max(checks)), gofer_raster_check_n=len(checks), choi=meta),
              open(Path(a.out).with_suffix("").with_suffix(".meta.json"), "w"), indent=1)
    print("rows", len(df), df.groupby(["product", "role"]).size().to_dict())


if __name__ == "__main__":
    main()
