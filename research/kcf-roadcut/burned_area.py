"""Sentinel-2 dNBR burned-area map on the routing grids (PROTOCOL.md §5.3 and amendment 1).

Usage: python3 burned_area.py S2_DIR OUT.json
S2_DIR holds <scene>_{B8A,B12,SCL}.tif for the four scenes fixed in amendment 1 (AWS open bucket sentinel-cogs).
Output per region: per routing-grid cell (row-major, grid of data/routing/graphs/<region>/graph.json) the number of
pixels, valid pixels, burned pixels at dNBR >= 0.10 and >= 0.27, and the cell class (B burned / U unburned / N not assessable).
"""
from __future__ import annotations

import hashlib, json, sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
SCENES = {"yeongdeok_2025": ("S2B_52SEF_20250314_0_L2A", "S2C_52SEF_20250408_0_L2A"),
          "uiseong_andong_2025": ("S2B_52SDF_20250314_0_L2A", "S2C_52SDF_20250428_0_L2A")}
INVALID_SCL = (0, 1, 3, 6, 8, 9, 10, 11)
THRESH = (0.10, 0.27)
CELL_BURNED_FRAC = 0.25
CELL_MIN_VALID = 0.50


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(path, bounds):
    with rasterio.open(path) as s:
        w = from_bounds(*bounds, transform=s.transform).round_offsets().round_lengths()
        a = s.read(1, window=w)
        return a, s.window_transform(w), s.crs


def nbr(d, scene, bounds):
    b8a, tr, crs = read(d / f"{scene}_B8A.tif", bounds)
    b12, _, _ = read(d / f"{scene}_B12.tif", bounds)
    scl, _, _ = read(d / f"{scene}_SCL.tif", bounds)
    b8a = b8a.astype(float); b12 = b12.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        n = (b8a - b12) / (b8a + b12)
    ok = ~np.isin(scl, INVALID_SCL) & (b8a > 0) & (b12 > 0)
    return n, ok, tr, crs


def main(s2dir, out):
    d = Path(s2dir)
    res = {"rule": "PROTOCOL.md 5.3 + amendment 1", "thresholds": THRESH, "cell_burned_frac": CELL_BURNED_FRAC,
           "cell_min_valid": CELL_MIN_VALID, "invalid_scl": INVALID_SCL, "regions": {}, "files_sha256": {}}
    for region, (pre, post) in SCENES.items():
        g = json.loads((ROOT / f"data/routing/graphs/{region}/graph.json").read_text())["grid"]
        x0, y0, r, W, H = g["x0"], g["y0"], g["resolution"], g["width"], g["height"]
        with rasterio.open(d / f"{pre}_B8A.tif") as s:
            crs = s.crs
        to_utm = Transformer.from_crs(5179, crs.to_epsg(), always_xy=True)
        xs = [x0, x0 + W * r, x0, x0 + W * r]; ys = [y0, y0, y0 + H * r, y0 + H * r]
        ux, uy = to_utm.transform(xs, ys)
        bounds = (min(ux) - 100, min(uy) - 100, max(ux) + 100, max(uy) + 100)
        n0, ok0, tr, _ = nbr(d, pre, bounds)
        n1, ok1, tr1, _ = nbr(d, post, bounds)
        assert n0.shape == n1.shape and tr == tr1, (n0.shape, n1.shape)
        dnbr = n0 - n1
        ok = ok0 & ok1 & np.isfinite(dnbr)
        rows, cols = np.indices(dnbr.shape)
        px, py = rasterio.transform.xy(tr, rows.ravel(), cols.ravel(), offset="center")
        bx, by = Transformer.from_crs(crs.to_epsg(), 5179, always_xy=True).transform(np.asarray(px), np.asarray(py))
        ci = np.floor((bx - x0) / r).astype(int); ri = np.floor((by - y0) / r).astype(int)
        inside = (ci >= 0) & (ci < W) & (ri >= 0) & (ri < H)
        cell = np.where(inside, ri * W + ci, -1)
        n_all = np.bincount(cell[inside], minlength=W * H)
        okf = ok.ravel()
        n_ok = np.bincount(cell[inside & okf], minlength=W * H)
        dv = dnbr.ravel()
        burned = {}
        for t in THRESH:
            m = inside & okf & (dv >= t)
            burned[t] = np.bincount(cell[m], minlength=W * H)
        cls = {}
        for t in THRESH:
            c = np.where(n_ok < CELL_MIN_VALID * np.maximum(n_all, 1), "N",
                         np.where(burned[t] >= CELL_BURNED_FRAC * np.maximum(n_ok, 1), "B", "U"))
            cls[str(t)] = "".join(c.tolist())
        px_area_km2 = 0.02 * 0.02
        res["regions"][region] = {
            "pre": pre, "post": post, "grid": {"x0": x0, "y0": y0, "res": r, "W": W, "H": H},
            "pixels_in_grid": int(n_all.sum()), "valid_pixels": int(n_ok.sum()),
            "burned_area_km2": {str(t): round(float(burned[t].sum()) * px_area_km2, 2) for t in THRESH},
            "cells": {str(t): {k: cls[str(t)].count(k) for k in "BUN"} for t in THRESH},
            "cell_class": cls,
            "cell_n_pixels": n_all.tolist(), "cell_n_valid": n_ok.tolist(),
            "cell_n_burned": {str(t): burned[t].tolist() for t in THRESH},
        }
        for s_ in (pre, post):
            for b in ("B8A", "B12", "SCL"):
                res["files_sha256"][f"{s_}_{b}.tif"] = sha(d / f"{s_}_{b}.tif")
        print(region, res["regions"][region]["burned_area_km2"], res["regions"][region]["cells"])
    Path(out).write_text(json.dumps(res))


if __name__ == "__main__":
    main(*sys.argv[1:3])
