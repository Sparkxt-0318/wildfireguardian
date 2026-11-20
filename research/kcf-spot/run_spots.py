"""Step 2: find spot fires in every fire (PROTOCOL sections 1-3, amendment 1).

    python run_spots.py kr  --choi DATA/choi/x --firms DATA/firms --ahi ../harness-2026-11/data-fetch-2/ahi_kfs01 --out WORK
    python run_spots.py ca  --gofer DATA/gofer/x/GOFER --firms DATA/firms --out WORK [--part i/n]

Writes per fire WORK/<region>/<fire>.npz (first-mark time, first system, label, spot id, grid) and
WORK/<region>/spots_<...>.csv with one row per candidate spot.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import spotlib as S  # noqa: E402

CELL = 375.0
PAD_M = 16000.0
B07_MIN, DIFF_MIN, MIN_SCANS = 320.0, 25.0, 2


class Grid:
    def __init__(self, epsg, x0, y1, H, W):
        from pyproj import Transformer
        self.epsg, self.x0, self.y1, self.H, self.W = epsg, x0, y1, H, W
        self.fwd = Transformer.from_crs(4326, epsg, always_xy=True)
        self.inv = Transformer.from_crs(epsg, 4326, always_xy=True)

    @classmethod
    def around(cls, epsg, minx, miny, maxx, maxy, pad=PAD_M):
        x0 = np.floor((minx - pad) / CELL) * CELL
        y1 = np.ceil((maxy + pad) / CELL) * CELL
        W = int(np.ceil((maxx + pad - x0) / CELL))
        H = int(np.ceil((y1 - (miny - pad)) / CELL))
        return cls(epsg, x0, y1, H, W)

    def rc(self, lon, lat):
        x, y = self.fwd.transform(np.asarray(lon), np.asarray(lat))
        return np.floor((self.y1 - y) / CELL).astype(int), np.floor((x - self.x0) / CELL).astype(int)

    def lonlat(self, r, c):
        return self.inv.transform(self.x0 + (np.asarray(c) + 0.5) * CELL, self.y1 - (np.asarray(r) + 0.5) * CELL)

    def bbox_ll(self):
        xs = [self.x0, self.x0 + self.W * CELL]
        ys = [self.y1 - self.H * CELL, self.y1]
        lo, la = self.inv.transform(np.array([xs[0], xs[1], xs[0], xs[1]]), np.array([ys[0], ys[0], ys[1], ys[1]]))
        return lo.min(), la.min(), lo.max(), la.max()

    def meta(self):
        return dict(epsg=self.epsg, x0=self.x0, y1=self.y1, H=self.H, W=self.W)


def read_viirs(firms_dir, country, years):
    fr = []
    for y in years:
        for s in ("viirs-snpp", "viirs-jpss1"):
            p = Path(firms_dir) / f"{s}_{y}_{country}.csv"
            if not p.exists():
                raise FileNotFoundError(p)
            d = pd.read_csv(p, usecols=["latitude", "longitude", "acq_date", "acq_time", "confidence", "frp"])
            d = d[d.confidence != "l"]
            d["t"] = pd.to_datetime(d.acq_date + " " + d.acq_time.astype(str).str.zfill(4), format="%Y-%m-%d %H%M")
            d["sat"] = s
            fr.append(d[["latitude", "longitude", "t", "sat", "frp"]])
    return pd.concat(fr, ignore_index=True)


def viirs_looks(df, grid, epoch, t0, t1):
    ll = grid.bbox_ll()
    d = df[(df.longitude >= ll[0]) & (df.longitude <= ll[2]) & (df.latitude >= ll[1]) & (df.latitude <= ll[3])
           & (df.t >= t0) & (df.t <= t1)].sort_values(["sat", "t"])
    looks = []
    for sat, g in d.groupby("sat"):
        gap = g.t.diff().dt.total_seconds().fillna(1e9) > 600
        gid = gap.cumsum()
        for _, gg in g.groupby(gid):
            r, c = grid.rc(gg.longitude.values, gg.latitude.values)
            ok = (r >= 0) & (r < grid.H) & (c >= 0) & (c < grid.W)
            if not ok.any():
                continue
            t = (gg.t.min() - epoch).total_seconds() / 3600
            frp = np.zeros((grid.H, grid.W))
            np.add.at(frp, (r[ok], c[ok]), gg.frp.values[ok])
            looks.append(S.Look(t, "V", r[ok], c[ok], sat=sat, meta=dict(frp=frp)))
    return looks


def ahi_looks(ahi_dir, grid, epoch, t0, t1):
    """Hourly AHI hotspot looks (kcf-margin rule); each 2 km pixel painted as a square of its median spacing."""
    from scipy.spatial import cKDTree
    looks = []
    files = sorted(Path(ahi_dir).glob("kfs01_ahi_*.npz"))
    for f in files:
        z = np.load(f)
        P = np.c_[z["x5179"], z["y5179"]]
        half = float(np.median(cKDTree(P).query(P, 2)[0][:, 1])) / 2
        ts = pd.to_datetime(z["scan_start_utc"])
        hot = (z["b07_K"] >= B07_MIN) & (z["b07_minus_b14_K"] >= DIFF_MIN)
        hr = ts.floor("h")
        for tau in hr.unique():
            if tau < t0 or tau > t1:
                continue
            cnt = hot[np.asarray(hr == tau)].sum(axis=0)
            pix = np.flatnonzero(cnt >= MIN_SCANS)
            if not len(pix):
                continue
            rr, cc = [], []
            for p in pix:
                xs, ys = z["x5179"][p], z["y5179"][p]
                r0, r1 = int((grid.y1 - (ys + half)) // CELL), int((grid.y1 - (ys - half)) // CELL) + 1
                c0, c1 = int((xs - half - grid.x0) // CELL), int((xs + half - grid.x0) // CELL) + 1
                R, C = np.mgrid[r0:r1, c0:c1]
                rr.append(R.ravel()); cc.append(C.ravel())
            t = (tau + pd.Timedelta(hours=1) - epoch).total_seconds() / 3600
            looks.append(S.Look(t, "H", np.concatenate(rr), np.concatenate(cc), sat="ahi",
                                meta=dict(n_pix=len(pix), half_m=half)))
    return looks


def finish(spots, arrays, grid, epoch, fire, region, outdir, extra=None):
    out = Path(outdir) / region
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / f"{fire}.npz", first=arrays["first"].astype(np.float32),
                        first_sys=arrays["first_sys"], label=arrays["label"], spot_id=arrays["spot_id"],
                        epoch=str(epoch), **{f"first_{k}": v.astype(np.float32) for k, v in arrays["first_by"].items()},
                        **{k: v for k, v in grid.meta().items()}, **(extra or {}))
    rows = []
    for s in spots:
        lon, lat = grid.lonlat(s["r"], s["c"])
        slon, slat = grid.lonlat(s["src_r"], s["src_c"])
        nlon, nlat = grid.lonlat(s["near_r"], s["near_c"])
        b = S.bearing_deg(s["r"] - s["src_r"], s["c"] - s["src_c"])
        rows.append(dict(fire=fire, region=region, t_utc=str(epoch + pd.Timedelta(hours=s["t"])), **s,
                         lon=float(lon), lat=float(lat), src_lon=float(slon), src_lat=float(slat),
                         near_lon=float(nlon), near_lat=float(nlat), bearing_deg=float(b)))
    return rows


def run_kr(a):
    ev = pd.read_csv(next(Path(a.choi).rglob("kr_events_21.csv")))
    ev = ev[ev.produced == 1]
    import rasterio
    years = sorted({int(str(t)[:4]) for t in ev.t0_utc})
    vi = read_viirs(a.firms, "Republic_of_Korea", years)
    allrows = []
    runs = [(e, "KR", False) for _, e in ev.iterrows()]
    runs += [(ev[ev.id == "KFS_01"].iloc[0], "DET", True)]
    for e, region, with_ahi in runs:
        with rasterio.open(Path(a.choi) / "rasters_kr" / f"{e.id}_pswt_ok_toa.tif") as ds:
            v = ds.read(1, masked=True).filled(np.nan)
            b = ds.bounds
            assert ds.crs.to_epsg() == 5179
        t0 = pd.Timestamp(e.t0_utc)
        t1 = t0 + pd.Timedelta(hours=float(np.nanmax(v)) + 24)
        if with_ahi:   # the AHI files cover the KFS_01 export rectangle
            b = type("B", (), dict(left=1085250.0, bottom=1815750.0, right=1174125.0, top=1845375.0))
        grid = Grid.around(5179, b.left, b.bottom, b.right, b.top, pad=PAD_M if not with_ahi else 0.0)
        epoch = t0.floor("h")
        looks = viirs_looks(vi, grid, epoch, t0 - pd.Timedelta(hours=1), t1)
        if with_ahi:
            looks += ahi_looks(a.ahi, grid, epoch, t0 - pd.Timedelta(hours=1), t1)
        spots, arrays = S.find_spots(looks, (grid.H, grid.W))
        allrows += finish(spots, arrays, grid, epoch, e.id, region, a.out)
        n = pd.Series([lk.system for lk in looks]).value_counts().to_dict()
        print(f"{region} {e.id} looks {n} spots {len(spots)} confirmed {sum(s['confirmed'] for s in spots)}", flush=True)
    pd.DataFrame(allrows).to_csv(Path(a.out) / "spots_kr_det.csv", index=False)


def run_ca(a):
    import geopandas as gpd
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    gdf = gpd.read_file(Path(a.gofer) / "GOFER_Combined" / "GOFERC_fireProg.shp")
    gdf["t"] = pd.to_datetime(gdf["tUTC"])
    names = sorted(gdf.fname.unique())
    if a.part:
        i, n = (int(x) for x in a.part.split("/"))
        names = names[i::n]
    cache = Path(a.out) / "firms_ca.pkl"
    if not cache.exists():
        vi = read_viirs(a.firms, "United_States", (2019, 2020, 2021))
        vi = vi[(vi.longitude >= -125.0) & (vi.longitude <= -113.5) & (vi.latitude >= 32.0) & (vi.latitude <= 42.6)]
        vi.to_pickle(cache)
    vi = pd.read_pickle(cache)
    allrows = []
    for name in names:
        g = gdf[gdf.fname == name].sort_values("t").reset_index(drop=True).to_crs(3310)
        minx, miny, maxx, maxy = g.total_bounds
        grid = Grid.around(3310, minx, miny, maxx, maxy)
        tf = from_origin(grid.x0, grid.y1, CELL, CELL)
        ts = [pd.Timestamp(x) for x in g["t"]]
        epoch = ts[0]
        A = np.full((grid.H, grid.W), np.inf)
        looks = []
        for k, geom in enumerate(g.geometry):
            if geom is None or geom.is_empty:
                continue
            r = rasterize([(geom, 1)], out_shape=(grid.H, grid.W), transform=tf, fill=0, dtype="uint8").astype(bool)
            tk = (ts[k] - epoch).total_seconds() / 3600
            newc = r & ~np.isfinite(A)
            A[newc] = tk
            rr, cc = np.nonzero(r)
            looks.append(S.Look(tk, "G", rr, cc, sat="goes"))
        if a.viirs_only:
            looks = []
        looks += viirs_looks(vi, grid, epoch, epoch - pd.Timedelta(hours=1), ts[-1])
        spots, arrays = S.find_spots(looks, (grid.H, grid.W))
        region = "CAV" if a.viirs_only else "CA"
        allrows += finish(spots, arrays, grid, epoch, name, region, a.out, extra=dict(gofer_A=A.astype(np.float32)))
        n = pd.Series([lk.system for lk in looks]).value_counts().to_dict()
        print(f"CA {name} grid {grid.H}x{grid.W} looks {n} spots {len(spots)} "
              f"confirmed {sum(s['confirmed'] for s in spots)}", flush=True)
    suffix = f"_{a.part.replace('/', 'of')}" if a.part else ""
    suffix += "_viirs_only" if a.viirs_only else ""
    pd.DataFrame(allrows).to_csv(Path(a.out) / f"spots_ca{suffix}.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("region", choices=["kr", "ca"])
    ap.add_argument("--choi"); ap.add_argument("--gofer"); ap.add_argument("--firms", required=True)
    ap.add_argument("--ahi"); ap.add_argument("--out", required=True); ap.add_argument("--part")
    ap.add_argument("--viirs-only", action="store_true", help="sensitivity: California front from VIIRS alone")
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    {"kr": run_kr, "ca": run_ca}[a.region](a)


if __name__ == "__main__":
    main()
