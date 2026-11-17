"""Score GOFER v0.2: h-hour reach from the known perimeter at every hourly issue time (PROTOCOL.md).

    python score_gofer.py --gofer /path/to/GOFER --out work/

Writes work/gofer_reach.csv.gz (fire, t, h, reach_km for sep 5 km / 2 km / none),
work/gofer_pixdist.npz (per fire, h in {5, 8}: distances of spread cells, 5 km rule; for the pixel calibration),
work/gofer_arrival/<fire>.npz (arrival grid, transform, hour timestamps; for the route experiment).
"""
import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from reach import CELL_KM, NEVER, component_reach, dist_km  # noqa: E402

HORIZONS = (1, 2, 3, 5, 8, 12, 18, 24, 36, 48)
SEPS = (5.0, 2.0, np.inf)
CELL_M = CELL_KM * 1000


def rasterise_arrival(g):
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    g = g.to_crs(3310)
    minx, miny, maxx, maxy = g.total_bounds
    pad = 8 * CELL_M
    x0 = np.floor((minx - pad) / CELL_M) * CELL_M
    y1 = np.ceil((maxy + pad) / CELL_M) * CELL_M
    w = int(np.ceil((maxx + pad - x0) / CELL_M))
    h = int(np.ceil((y1 - (miny - pad)) / CELL_M))
    tf = from_origin(x0, y1, CELL_M, CELL_M)
    A = np.full((h, w), NEVER, np.int32)
    for k, geom in enumerate(g.geometry):
        if geom is None or geom.is_empty:
            continue
        r = rasterize([(geom, 1)], out_shape=(h, w), transform=tf, fill=0, dtype="uint8").astype(bool)
        A[(A == NEVER) & r] = k
    return A, tf


def score_fire(A, T, horizons=HORIZONS, seps=SEPS, pix_h=(5, 8)):
    """T = number of perimeter hours (issue hours run to the last perimeter hour, PROTOCOL)."""
    first = int(A[A != NEVER].min())
    rows, pix = [], {h: [] for h in pix_h}
    prev_known_n, dist = -1, None
    for t in range(first, T):
        known = A <= t
        kn = int(known.sum())
        if kn != prev_known_n:
            dist = dist_km(known)
            prev_known_n = kn
        for h in horizons:
            if t + h > T - 1:
                continue
            new = (A > t) & (A <= t + h)
            r, d, _ = component_reach(known, new, seps, dist=dist)
            rows.append((t, h, r[seps[0]], r[seps[1]], r[seps[2]], int(new.sum())))
            if h in pix:
                pix[h].append(d)
    return rows, {h: (np.concatenate(v) if v else np.zeros(0)) for h, v in pix.items()}, T


def main():
    import geopandas as gpd
    ap = argparse.ArgumentParser()
    ap.add_argument("--gofer", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fires", nargs="*")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "gofer_arrival").mkdir(parents=True, exist_ok=True)
    gdf = gpd.read_file(Path(a.gofer) / "GOFER_Combined" / "GOFERC_fireProg.shp")
    gdf["t"] = pd.to_datetime(gdf["tUTC"])
    allrows, pixd = [], {}
    for name, g in gdf.groupby("fname", sort=True):
        if a.fires and name not in a.fires:
            continue
        t0 = time.time()
        g = g.sort_values("t").reset_index(drop=True)
        hours = (g["t"] - g["t"].iloc[0]).dt.total_seconds() / 3600
        assert np.allclose(hours, np.arange(len(g))), f"{name}: non-hourly GOFER steps"
        A, tf = rasterise_arrival(g)
        np.savez_compressed(out / "gofer_arrival" / f"{name}.npz", A=A, transform=np.array(tf)[:6],
                            t0=str(g["t"].iloc[0]))
        T = len(g)
        rows, pix, T = score_fire(A, T)
        for t, h, r5, r2, rinf, nnew in rows:
            allrows.append(dict(fire=name, t_idx=t, t=str(g["t"].iloc[t]), h=h, reach_km=r5, reach_sep2_km=r2,
                                reach_nosep_km=rinf, new_cells=nnew))
        for h, d in pix.items():
            pixd[f"{name}|{h}"] = d.astype(np.float32)
        print(f"{name:24s} grid {A.shape} hours {T} rows {len(rows)} {time.time() - t0:.0f}s", flush=True)
    pd.DataFrame(allrows).to_csv(out / "gofer_reach.csv.gz", index=False)
    np.savez_compressed(out / "gofer_pixdist.npz", **pixd)


if __name__ == "__main__":
    main()
