"""Block cross-validated standardized residuals of the kriging SD (detection-based calibration check).

For the six US 2024 fires (evaluation-only use, declared in RESULTS.md), VIIRS
detections (S-NPP, NOAA-20; FIRMS standard processing, from Daniel's
``firms_us2024_heldout6.csv.gz``) are reduced to one observation per 375 m
cell with Choi et al.'s ``cell_summary``. The cells are then cross-validated by
spatial blocks following Choi et al.'s U.S. design (``block_cv.cross_validate_us``):

* block size is half the whole-data variogram range, clipped to 5-30 km;
* every occupied block is one fold;
* the variogram is refitted per fold;
* ordinary kriging from the 50 nearest training cells is used.

At every held-out cell we record ``z = (observed - predicted) / sqrt(kriging variance)``.
If the kriging variance is calibrated, z is approximately N(0, 1).

Differences from the published product, so that this checks the P-OK variance rather than reproducing PSwt-OK:

* no GOES points, which are not in the keyless FIRMS archive;
* selection uses the raster's valid-cell mask (pixel centres inside the final
  perimeter) instead of the perimeter polygon;
* the time window is Choi et al.'s collection window from ``results/us_selection_29.csv``.

    python blockcv_kriging_sd.py --choi DIR --firms firms_us2024_heldout6.csv.gz --out results/kriging_sd_blockcv.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

EVENTS = ["ID-BOF-000683_Wapiti_Wapiti", "ID-BOF-000904_Goat", "ID-BOF-001080_Lava",
          "ID-SCF-240202_RedRock", "WA-SES-000173_Pioneer", "WY-BTF-002416_FishCreek"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--choi", type=Path, required=True, help="unzipped Zenodo archive (rasters_us/ and results/ are read as data)")
    ap.add_argument("--firms", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("results/kriging_sd_blockcv.json"))
    a = ap.parse_args(argv)
    import rasterio
    from pyproj import Transformer
    from choi_kriging import cell_summary, fit_variogram, local_kriging   # own port; downloaded code is not run

    sel = pd.read_csv(a.choi / "results/us_selection_29.csv").set_index("incident")
    firms = pd.read_csv(a.firms)
    firms = firms[firms["instrument"] == "VIIRS"].drop_duplicates()
    firms["time"] = pd.to_datetime(firms["acq_date"] + " " + firms["acq_time"].astype(str).str.zfill(4),
                                   format="%Y-%m-%d %H%M", utc=True)
    to5070 = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    out, allz = {}, []
    for ev in EVENTS:
        with rasterio.open(a.choi / "rasters_us" / f"{ev}_pswt_ok_toa.tif") as src:
            toa = src.read(1, masked=True)
            valid = ~np.ma.getmaskarray(toa)
            inv = ~src.transform
            t0 = pd.Timestamp(src.tags()["t0_utc"]).tz_localize("UTC")
        with rasterio.open(a.choi / "rasters_us" / f"{ev}_pswt_ok_std.tif") as src:
            std = src.read(1, masked=True).filled(np.nan)
        w0 = pd.Timestamp(sel.loc[ev, "window_start_utc"]).tz_localize("UTC")
        w1 = pd.Timestamp(sel.loc[ev, "window_end_utc"]).tz_localize("UTC")
        d = firms[(firms["incident"] == ev) & (firms["time"] >= w0) & (firms["time"] <= w1)]
        x, y = to5070.transform(d["longitude"].to_numpy(), d["latitude"].to_numpy())
        col, row = inv * (np.asarray(x), np.asarray(y))
        row, col = np.floor(row).astype(int), np.floor(col).astype(int)
        inside = (row >= 0) & (row < valid.shape[0]) & (col >= 0) & (col < valid.shape[1])
        inside[inside] &= valid[row[inside], col[inside]]
        d, x, y = d[inside], np.asarray(x)[inside], np.asarray(y)[inside]
        hours = ((d["time"] - t0).dt.total_seconds() / 3600).to_numpy()
        cells = cell_summary(x / 1000, y / 1000, hours, d["longitude"].to_numpy(), d["latitude"].to_numpy())
        cx, cy, cz = (cells[c].to_numpy() for c in ("x", "y", "t"))
        params_all = fit_variogram(cx, cy, cz)
        size = min(max(params_all[1] / 2.0, 5.0), 30.0)
        block = np.unique(np.c_[np.floor(cx / size), np.floor(cy / size)], axis=0, return_inverse=True)[1].ravel()
        obs, pred, var, used, skipped = [], [], [], 0, 0
        for b in np.unique(block):
            test, train = block == b, block != b
            if train.sum() < 5:
                skipped += 1
                continue
            try:
                params = fit_variogram(cx[train], cy[train], cz[train])
            except RuntimeError:
                skipped += 1
                continue
            p, v = local_kriging(cx[test], cy[test], cx[train], cy[train], cz[train], np.zeros(train.sum()), params)
            if not (np.isfinite(p).all() and np.isfinite(v).all()):
                skipped += 1
                continue
            used += 1
            obs.append(cz[test]); pred.append(p); var.append(v)
        obs, pred, var = map(np.concatenate, (obs, pred, var))
        z = (obs - pred) / np.sqrt(np.maximum(var, 1e-12))
        allz.append(z)
        e = pred - obs
        rec = dict(viirs_detections=int(len(d)), viirs_cells=int(len(cx)), block_km=float(size), folds_used=used,
                   folds_skipped=skipped, cv_r=float(np.corrcoef(obs, pred)[0, 1]), cv_ME_h=float(e.mean()),
                   cv_MAE_h=float(np.abs(e).mean()),
                   kriging_sd_median_h=float(np.median(np.sqrt(var))),
                   product_sd_median_h=float(np.nanmedian(std[valid])),
                   z_mean=float(z.mean()), z_sd=float(z.std()), z_robust_sd=float(np.median(np.abs(z - np.median(z))) / 0.6744897501960817),
                   frac_abs_z_gt_1_645=float((np.abs(z) > 1.6448536269514722).mean()),
                   frac_abs_z_gt_1_96=float((np.abs(z) > 1.959963984540054).mean()))
        pub = json.loads((a.choi / "results/us_events" / f"{ev}.json").read_text())
        rec["published_P_OK_cv_refit"] = pub["cv_refit"]["P-OK"] | dict(viirs_cells=pub["viirs_cells"], folds=pub["folds"])
        out[ev] = rec
        print(ev, json.dumps(rec))
    z = np.concatenate(allz)
    pooled = dict(cells=int(len(z)), z_mean=float(z.mean()), z_sd=float(z.std()),
                  z_robust_sd=float(np.median(np.abs(z - np.median(z))) / 0.6744897501960817),
                  frac_abs_z_gt_1_645=float((np.abs(z) > 1.6448536269514722).mean()),
                  frac_abs_z_gt_1_96=float((np.abs(z) > 1.959963984540054).mean()),
                  across_fires_z_sd=[out[e]["z_sd"] for e in EVENTS])
    print("POOLED", json.dumps(pooled))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(
        design="Choi et al. U.S. block CV (half-range blocks 5-30 km, per-fold variogram refit), P-OK from VIIRS cells only",
        nominal="calibrated variance gives z ~ N(0,1): sd 1, |z|>1.645 in 10%, |z|>1.96 in 5%",
        per_event=out, pooled=pooled), indent=1))


if __name__ == "__main__":
    main()
