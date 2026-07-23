import rasterio
from rasterio.merge import merge
from rasterio.windows import from_bounds
import numpy as np

# ESA WorldCover 2021 v200 public S3 (COGs, EPSG:4326)
BASE = "/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
# box dips west of 129E, so it spans two 3x3 tiles: N36E126 and N36E129
tiles = [
    f"{BASE}/ESA_WorldCover_10m_2021_v200_N36E126_Map.tif",
    f"{BASE}/ESA_WorldCover_10m_2021_v200_N36E129_Map.tif",
]
# bbox: [minlon, minlat, maxlon, maxlat]
W, S, E, N = 128.97, 36.10, 129.77, 36.90

srcs = [rasterio.open(t) for t in tiles]
mosaic, transform = merge(srcs, bounds=(W, S, E, N))
meta = srcs[0].meta.copy()
meta.update({
    "height": mosaic.shape[1],
    "width": mosaic.shape[2],
    "transform": transform,
    "compress": "deflate",
})
out = "data/raw/firms/yeongdeok_2025_fuel.tif"
with rasterio.open(out, "w", **meta) as dst:
    dst.write(mosaic)
for s in srcs:
    s.close()

with rasterio.open(out) as chk:
    arr = chk.read(1)
    print(f"wrote {out}")
    print(f"  size {chk.width}x{chk.height}, crs {chk.crs}, dtype {arr.dtype}")
    print(f"  bounds {chk.bounds}")
    vals, counts = np.unique(arr, return_counts=True)
    print(f"  class codes present: {dict(zip(vals.tolist(), counts.tolist()))}")
