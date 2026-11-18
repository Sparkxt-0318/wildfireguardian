"""Download the DEM box (+-30 km around each weather point) for the CA fires or the Korean box. Inputs only, no scores.
    python3 fetch_dem.py ca|kr CACHE_DIR OUT_DIR
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
from pyproj import Transformer
import terrain

HALF = 30000.0
KR_CENTRE = (128.95, 36.45)   # centre of the kcf-margin BOX (128.2, 36.1, 129.7, 36.8)

def main():
    which, cache, out = sys.argv[1:4]
    Path(out).mkdir(parents=True, exist_ok=True)
    if which == "ca":
        g = pd.read_csv(Path(__file__).resolve().parent.parent / "kcf-margin/derived/gofer_gusts.csv.gz")
        pts = {f: (s.lon.iloc[0], s.lat.iloc[0]) for f, s in g.groupby("fire")}; epsg = 3310
    else:
        pts = {"Gyeongbuk": KR_CENTRE}; epsg = 5179
    tr = Transformer.from_crs(4326, epsg, always_xy=True)
    for f, (lon, lat) in pts.items():
        p = Path(out) / (f.replace(" ", "_").replace("/", "_") + ".npz")
        if p.exists():
            continue
        x, y = tr.transform(lon, lat)
        z, x0, y1 = terrain.dem_grid(epsg, x - HALF, y - HALF, x + HALF, y + HALF, cache)
        np.savez_compressed(p, z=z.astype(np.float32), x0=x0, y1=y1, cell=terrain.CELL, epsg=epsg)
        print(f, z.shape, float(np.nanmin(z)), float(np.nanmax(z)), flush=True)

if __name__ == "__main__":
    main()
