"""Per-cell land-cover class for the heat option (research/kcf-radiation METHOD.md section 3), for every 375 m cell of
each region's road grid.

Source: Copernicus Global Land Cover v3.0.1 2019 (100 m, discrete classification), mode-resampled to the KFS_01 375 m
lattice by the forecast workspace (data/environment/regions/KFS_01/vegetation/landcover_class_375m.tif in the owner
archive; research/kcf-radiation/DATA.md). The KFS_01 lattice contains both 2025 road grids exactly (x0 offsets are
whole cells). Build time only (needs rasterio); the run reads the CSV.

    python3 tools/build_heat_fuel.py ENV_REGIONS_DIR
writes data/fuel/<region>_landcover.csv.gz (cell, lc) and prints the source raster's SHA-256.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import sys
from pathlib import Path

PRODUCT = Path(__file__).resolve().parents[1]
REPO = PRODUCT.parents[1]


def main():
    import rasterio
    env = Path(sys.argv[1]) / "KFS_01"
    src = env / "vegetation/landcover_class_375m.tif"
    with rasterio.open(src) as r:
        lc = r.read(1)
        t = r.transform
    x0, ytop, res = t.c, t.f, t.a
    out = PRODUCT / "data/fuel"
    out.mkdir(parents=True, exist_ok=True)
    for rid in ("uiseong_andong_2025", "yeongdeok_2025"):
        g = json.loads((REPO / "data/routing/graphs" / rid / "graph.json").read_text())["grid"]
        W, H = int(g["width"]), int(g["height"])
        c0 = round((g["x0"] - x0) / res)
        rtop = round((ytop - (g["y0"] + res * H)) / res)
        with gzip.open(out / ("%s_landcover.csv.gz" % rid), "wt", newline="") as f:
            w = csv.writer(f)
            w.writerow(["cell", "lc"])
            for rr in range(H):
                src_r = rtop + H - 1 - rr
                for cc in range(W):
                    v = int(lc[src_r, c0 + cc])
                    w.writerow([rr * W + cc, v if v >= 0 else ""])
        print(rid, W, H, "offset col", c0, "row", rtop)
    print("source sha256", hashlib.sha256(src.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
