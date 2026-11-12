"""Build the obstruction surface for F-C1: Copernicus GLO-30 DSM tiles, bilinear-resampled to EPSG:5179 at 30 m,
covering the KFS_01 export grid plus a pad. Writes an npz (z, x0, y_top, res, tile SHA-256s) outside git.

    python3 seebefore/dem.py _data/raw/*.tif --out _data/surface_glo30_5179_30m.npz
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

# KFS_01 export grid (FORECAST_*.npz affine): x 1085250 .. 1174125, y 1815750 .. 1845375 (EPSG:5179)
GRID_X0, GRID_X1 = 1_085_250.0, 1_085_250.0 + 237 * 375.0
GRID_Y0, GRID_Y1 = 1_845_375.0 - 79 * 375.0, 1_845_375.0
PAD = 3_000.0
RES = 30.0


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def build(tiles: list[Path]):
    import rasterio
    from rasterio.merge import merge
    from rasterio.warp import Resampling, reproject

    x0, x1 = GRID_X0 - PAD, GRID_X1 + PAD
    y0, y1 = GRID_Y0 - PAD, GRID_Y1 + PAD
    w, h = int(round((x1 - x0) / RES)), int(round((y1 - y0) / RES))
    srcs = [rasterio.open(t) for t in tiles]
    mosaic, mtr = merge(srcs, nodata=-32767.0)
    crs = srcs[0].crs
    for s in srcs:
        s.close()
    dst = np.full((h, w), np.nan, np.float32)
    from rasterio.transform import from_origin
    reproject(mosaic[0].astype(np.float32), dst, src_transform=mtr, src_crs=crs, src_nodata=-32767.0,
              dst_transform=from_origin(x0, y1, RES, RES), dst_crs='EPSG:5179', dst_nodata=np.nan,
              resampling=Resampling.bilinear)
    return dst, x0, y1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tiles', nargs='+', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    z, x0, ytop = build(a.tiles)
    meta = {'source': 'Copernicus DEM GLO-30 DSM (2021 release), bilinear to EPSG:5179',
            'tiles': {t.name: sha256(t) for t in a.tiles}, 'res_m': RES, 'pad_m': PAD,
            'nan_cells': int(np.isnan(z).sum()), 'shape': list(z.shape),
            'z_min': float(np.nanmin(z)), 'z_max': float(np.nanmax(z))}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out, z=z, x0=x0, y_top=ytop, res=RES, meta=json.dumps(meta))
    print(json.dumps(meta, indent=1))


def load(path: Path):
    from .viewshed import Surface
    d = np.load(path)
    return Surface(d['z'].astype(np.float64), float(d['x0']), float(d['y_top']), float(d['res'])), \
        json.loads(str(d['meta']))


if __name__ == '__main__':
    main()
