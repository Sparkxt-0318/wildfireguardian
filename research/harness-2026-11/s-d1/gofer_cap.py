"""Descriptive test: how often would the hourly 9x9 (4-cell) reach cap bind on observed hourly perimeters?

Data: GOFER v0.2 (Liu et al. 2024 ESSD 16:1395; Zenodo 10.5281/zenodo.14642378, CC-BY-4.0),
GOFER_Combined/GOFERC_fireProg.shp: hourly GOES-derived cumulative fire perimeters, 28 California fires.
Fetch with Daniel's fetch.py (branch daniel/data-fetch): `python fetch.py get gofer_v0.2`, unzip into
its own directory, and pass the GOFER/ directory as --gofer.

Method, per fire:
  * project to California Albers (EPSG:3310), rasterise each perimeter onto a 375 m grid by cell-centre
    inclusion; burned state is made cumulative (B_t = B_{t-1} | raster_t);
  * for each consecutive pair (t-1, t), gap g = tUTC difference in hours, new cells N_t = B_t & ~B_{t-1};
  * d(i) = chessboard (Chebyshev) distance in cells from new cell i to the nearest cell of B_{t-1};
  * a new cell lies outside the hourly CA's reach after g steps when d > 4 g (9x9 support).
Outputs per fire and pooled: number of new cells, share with d > 4g, share with d > 4g + 6 (one GOES
pixel of tolerance), share with d > 4 (one step),
quantiles of d / g (cells per hour), and the per-hour maximum advance. The first perimeter of each fire
(no predecessor) is excluded.

Caveat: GOFER perimeters come from ~2 km GOES pixels at 1-hour cadence, so sub-pixel advances are
quantised and isolated jumps can be detection artefacts. This is descriptive, not a validation.

    python research/harness-2026-11/s-d1/gofer_cap.py --gofer /path/to/GOFER --out RESULTS_gofer_cap.json
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

CELL = 375.0
# Tolerance for GOES pixel quantisation: a ~2-3 km ABI fire pixel over California spans ~6 cells.
GOES_PIXEL_CELLS = 6
# GOFER fires whose event is also in the c651 event catalogue (forecast/data/environment/events.json)
IN_C651_CATALOGUE = {"Dixie", "River Complex", "Antelope", "August Complex", "North Complex",
                     "Monument", "Creek", "SQF Complex", "McCash", "Red Salmon Complex"}


def rasterise_fire(g):
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    g = g.to_crs(3310)
    minx, miny, maxx, maxy = g.total_bounds
    pad = 8 * CELL
    x0 = np.floor((minx - pad) / CELL) * CELL
    y1 = np.ceil((maxy + pad) / CELL) * CELL
    w = int(np.ceil((maxx + pad - x0) / CELL))
    h = int(np.ceil((y1 - (miny - pad)) / CELL))
    tf = from_origin(x0, y1, CELL, CELL)
    rasters = []
    for geom in g.geometry:
        if geom is None or geom.is_empty:
            rasters.append(np.zeros((h, w), bool))
            continue
        rasters.append(rasterize([(geom, 1)], out_shape=(h, w), transform=tf, fill=0,
                                 all_touched=False, dtype="uint8").astype(bool))
    return rasters


def main():
    import geopandas as gpd
    from scipy.ndimage import distance_transform_cdt
    ap = argparse.ArgumentParser()
    ap.add_argument("--gofer", required=True)
    ap.add_argument("--out", default=str(Path(__file__).with_name("RESULTS_gofer_cap.json")))
    args = ap.parse_args()
    shp = Path(args.gofer) / "GOFER_Combined" / "GOFERC_fireProg.shp"
    gdf = gpd.read_file(shp)
    gdf["t"] = pd.to_datetime(gdf["tUTC"])
    per_fire, pooled_d, pooled_rate, pooled_cap, pooled_tol = {}, [], [], [], []
    hourly_rows = []
    for name, g in gdf.groupby("fname", sort=True):
        g = g.sort_values("t").reset_index(drop=True)
        rasters = rasterise_fire(g)
        burned = rasters[0].copy()
        d_all, rate_all, cap_all, cap_tol = [], [], [], []
        for t in range(1, len(g)):
            gap = (g.loc[t, "t"] - g.loc[t - 1, "t"]).total_seconds() / 3600
            new = rasters[t] & ~burned
            if new.any() and burned.any() and gap > 0:
                dist = distance_transform_cdt(~burned, metric="chessboard")[new].astype(float)
                d_all.append(dist)
                rate_all.append(dist / gap)
                cap_all.append(dist > 4 * gap)
                cap_tol.append(dist > 4 * gap + GOES_PIXEL_CELLS)
                hourly_rows.append(dict(fire=name, t=str(g.loc[t, "t"]), gap_h=gap,
                                        new_cells=int(new.sum()),
                                        beyond_cap=int((dist > 4 * gap).sum()),
                                        max_advance_cells=float(dist.max())))
            burned |= rasters[t]
        if not d_all:
            continue
        d = np.concatenate(d_all)
        r = np.concatenate(rate_all)
        c = np.concatenate(cap_all)
        per_fire[name] = dict(
            year=int(g["fyear"].iloc[0]), perimeters=len(g), in_c651_catalogue=name in IN_C651_CATALOGUE,
            new_cells=int(d.size), share_beyond_cap=float(c.mean()), share_d_gt_4=float((d > 4).mean()),
            share_beyond_cap_plus_goes_pixel=float(np.concatenate(cap_tol).mean()),
            cells_per_hour_q50_q90_q99_max=[float(x) for x in np.quantile(r, [0.5, 0.9, 0.99, 1.0])],
            hours_with_any_beyond_cap=int(sum(row["beyond_cap"] > 0 for row in hourly_rows if row["fire"] == name)),
            hourly_intervals=int(sum(row["fire"] == name for row in hourly_rows)),
        )
        pooled_d.append(d)
        pooled_rate.append(r)
        pooled_cap.append(c)
        pooled_tol.append(np.concatenate(cap_tol))
        pf = per_fire[name]
        print(f"{name:24s} {pf['year']} cells {pf['new_cells']:7d} beyond-cap {100 * pf['share_beyond_cap']:5.1f}% (+pixel {100 * pf['share_beyond_cap_plus_goes_pixel']:4.1f}%) "
              f"hours-with-any {pf['hours_with_any_beyond_cap']}/{pf['hourly_intervals']} "
              f"rate q50/q90/q99/max {pf['cells_per_hour_q50_q90_q99_max']}", flush=True)
    d = np.concatenate(pooled_d)
    r = np.concatenate(pooled_rate)
    c = np.concatenate(pooled_cap)
    fires = list(per_fire)
    shares = np.array([per_fire[f]["share_beyond_cap"] for f in fires])
    excl = [f for f in fires if not per_fire[f]["in_c651_catalogue"]]
    cap_excl = np.concatenate([pc for f, pc in zip(fires, pooled_cap) if f in excl])
    pooled = dict(
        fires=len(fires), new_cells=int(d.size), share_beyond_cap=float(c.mean()),
        share_beyond_cap_plus_goes_pixel=float(np.concatenate(pooled_tol).mean()),
        share_d_gt_4_any_gap=float((d > 4).mean()),
        gap_hours_values=sorted({row["gap_h"] for row in hourly_rows}),
        share_beyond_cap_excluding_c651_catalogue_fires=float(cap_excl.mean()),
        fires_excluding_c651_catalogue=len(excl),
        per_fire_share_beyond_cap_median=float(np.median(shares)),
        per_fire_share_beyond_cap_min_max=[float(shares.min()), float(shares.max())],
        cells_per_hour_q50_q90_q99_max=[float(x) for x in np.quantile(r, [0.5, 0.9, 0.99, 1.0])],
        hourly_intervals=len(hourly_rows),
        hourly_intervals_with_any_beyond_cap=int(sum(row["beyond_cap"] > 0 for row in hourly_rows)),
    )
    print("POOLED", json.dumps(pooled))
    Path(args.out).write_text(json.dumps(dict(
        source="GOFER v0.2 GOFERC_fireProg (Zenodo 10.5281/zenodo.14642378, sha256 of GOFER.zip "
               "96eca2e18529eb274ca94af9a730bcf1c9c6da597fb04a9b5cf9167aada451c2)",
        grid="EPSG:3310, 375 m, cell-centre inclusion, cumulative", cap="chessboard distance > 4 * gap_hours",
        pooled=pooled, per_fire=per_fire), indent=1))
    pd.DataFrame(hourly_rows).to_csv(Path(args.out).with_suffix(".hourly.csv.gz"), index=False)


if __name__ == "__main__":
    main()
