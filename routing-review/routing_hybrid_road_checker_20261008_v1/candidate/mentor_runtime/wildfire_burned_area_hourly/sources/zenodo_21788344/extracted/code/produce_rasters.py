"""Time-of-arrival products: PSwt-OK prediction and kriging standard deviation at the pixel centres of a 375 m grid,
for the pixels whose centre lies inside the final perimeter.
"""
import numpy as np
import rasterio
import shapely
from affine import Affine
from pyproj import Transformer

from block_cv import geostationary_variance
from preprocess import kr_km
from toa_kriging import fit_variogram, local_kriging

CELL_M = 375.0
MIN_CELLS = 5                   # a product is made only from at least this many VIIRS cells inside the perimeter


def pswt_ok(xp, yp, cells, geo):
    """PSwt-OK at (xp, yp). `cells` and `geo` are tables with columns x, y (km) and t (h).
    Raises ValueError with fewer than MIN_CELLS cells and RuntimeError if the variogram fit does not converge."""
    if len(cells) < MIN_CELLS:
        raise ValueError(f"fewer than {MIN_CELLS} VIIRS cells inside the perimeter")
    params = fit_variogram(cells["x"].values, cells["y"].values, cells["t"].values)
    x, y, z = (np.r_[cells[c].values, geo[c].values] for c in ("x", "y", "t"))
    ev = np.r_[np.zeros(len(cells)), geostationary_variance(params[2], len(geo))]
    return local_kriging(xp, yp, x, y, z, ev, params), params


def us_product(reference_toa, transform, cells, geo):
    """U.S. product on the reference grid (EPSG:5070): ToA (h) and kriging standard deviation (h) inside the final perimeter."""
    rows, cols = np.where(np.isfinite(reference_toa))
    xp = (transform.c + (cols + 0.5) * transform.a) / 1000.0
    yp = (transform.f + (rows + 0.5) * transform.e) / 1000.0
    (z, v), params = pswt_ok(xp, yp, cells, geo)
    toa, std = (np.full(reference_toa.shape, np.nan, np.float32) for _ in range(2))
    toa[rows, cols], std[rows, cols] = z, np.sqrt(v)
    return toa, std, params


def kr_product(perimeter_5179, cells, geo, lat_centre):
    """Korean product on a 375 m EPSG:5179 grid whose edges are multiples of 375 m: ToA (h) and kriging standard
    deviation (h). Returns (toa, std, transform, variogram parameters)."""
    x0, y0, x1, y1 = perimeter_5179.bounds
    gx0, gy1 = np.floor(x0 / CELL_M) * CELL_M, np.ceil(y1 / CELL_M) * CELL_M
    w, h = int(np.ceil((x1 - gx0) / CELL_M)), int(np.ceil((gy1 - y0) / CELL_M))
    cols, rows = np.meshgrid(np.arange(w), np.arange(h))
    cx, cy = gx0 + (cols + 0.5) * CELL_M, gy1 - (rows + 0.5) * CELL_M
    shapely.prepare(perimeter_5179)
    inside = shapely.contains_properly(perimeter_5179, shapely.points(cx.ravel(), cy.ravel())).reshape(h, w)
    lon, lat = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True).transform(cx[inside], cy[inside])
    (z, v), params = pswt_ok(*kr_km(lon, lat, lat_centre), cells, geo)
    toa, std = (np.full((h, w), np.nan, np.float32) for _ in range(2))
    toa[inside], std[inside] = z, np.sqrt(v)
    return toa, std, Affine(CELL_M, 0, gx0, 0, -CELL_M, gy1), params


US_NODATA = -1.0                # stored outside the final perimeter in the U.S. rasters; the Korean rasters store NaN


def write_geotiff(path, array, transform, crs, nodata=np.nan, **tags):
    """Pixels without a value (NaN in `array`) are stored as `nodata`."""
    out = array if np.isnan(nodata) else np.where(np.isnan(array), nodata, array)
    with rasterio.open(path, "w", driver="GTiff", height=array.shape[0], width=array.shape[1], count=1, dtype="float32",
                       crs=crs, transform=transform, nodata=nodata, compress="deflate") as dst:
        dst.write(out.astype("float32"), 1)
        dst.update_tags(**tags)
