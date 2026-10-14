"""DEM loading and path-profile utilities (Copernicus GLO-30 DSM, reprojected to UTM)."""
from __future__ import annotations

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import Resampling, calculate_default_transform, reproject
from scipy.ndimage import map_coordinates

from common import RAW


class DEM:
    def __init__(self, z, transform, crs):
        self.z, self.transform, self.crs = z, transform, crs
        self.res = transform.a
        self.x0, self.y0 = transform.c, transform.f
        self.ny, self.nx = z.shape

    @classmethod
    def load(cls, tiles, bbox, epsg, res):
        srcs = [rasterio.open(RAW / "dem" / t) for t in tiles]
        mosaic, mtr = merge(srcs, bounds=bbox)
        src_crs = srcs[0].crs
        for s in srcs:
            s.close()
        h, w = mosaic.shape[1:]
        dst_crs = f"EPSG:{epsg}"
        left, bottom, right, top = bbox
        tr, nx, ny = calculate_default_transform(src_crs, dst_crs, w, h, left, bottom, right, top,
                                                 resolution=res)
        out = np.full((ny, nx), np.nan, dtype="float32")
        reproject(mosaic[0], out, src_transform=mtr, src_crs=src_crs, dst_transform=tr,
                  dst_crs=dst_crs, resampling=Resampling.bilinear, dst_nodata=np.nan)
        return cls(out, tr, dst_crs)

    def rc(self, x, y):
        """Fractional row/col for UTM coordinates (cell centres)."""
        col = (np.asarray(x) - self.x0) / self.res - 0.5
        row = (self.y0 - np.asarray(y)) / self.res - 0.5
        return row, col

    def xy(self, row, col):
        return self.x0 + (np.asarray(col) + 0.5) * self.res, self.y0 - (np.asarray(row) + 0.5) * self.res

    def sample(self, x, y):
        r, c = self.rc(x, y)
        return map_coordinates(self.z, [r, c], order=1, mode="nearest")

    def extent(self):
        return (self.x0, self.x0 + self.nx * self.res, self.y0 - self.ny * self.res, self.y0)


def link_profile(dem, p1, p2, h_ant, step, k=4 / 3, R=6_371_000.0):
    """Terrain profile and ray geometry along a straight link between UTM points p1 and p2.

    Returns dict with distance x, terrain (DSM), Earth bulge, ray height, clearance of the
    ray above (terrain + bulge), and the coordinates of each sample.
    """
    (x1, y1), (x2, y2) = p1, p2
    L = float(np.hypot(x2 - x1, y2 - y1))
    n = max(int(np.ceil(L / step)), 2)
    s = np.linspace(0, 1, n + 1)
    xs, ys = x1 + s * (x2 - x1), y1 + s * (y2 - y1)
    terr = dem.sample(xs, ys)
    d = s * L
    bulge = d * (L - d) / (2 * k * R)
    z1, z2 = terr[0] + h_ant, terr[-1] + h_ant
    ray = z1 + s * (z2 - z1)
    return {"x": d, "L": L, "terrain": terr, "bulge": bulge, "ray": ray,
            "clearance": ray - terr - bulge, "xs": xs, "ys": ys}


def fresnel_r1(f_hz, d, L):
    lam = 299_792_458.0 / f_hz
    d = np.clip(d, 1e-6, L - 1e-6)
    return np.sqrt(lam * d * (L - d) / L)
