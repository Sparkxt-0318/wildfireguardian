"""NIROPS 12-48 h external check (PROTOCOL.md). Reads ONLY incidents on S-D9 PART_A_ALLOWLIST_FINAL.csv.

Per incident: perimeters sorted by UTC, UTM, 375 m grid, accumulated. For each consecutive survey pair with gap g in
[12, 48] h, reach = max distance (km) of spread cells (5 km separate-fire rule) from the earlier cumulative perimeter.

    python score_nirops.py --shp .../NIROPS_2020_2024_R1_R6.shp --allowlist PART_A_ALLOWLIST_FINAL.csv --out work/nirops_pairs.csv.gz
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from reach import CELL_KM, component_reach  # noqa: E402

CELL = CELL_KM * 1000


def main():
    import pyogrio
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    ap = argparse.ArgumentParser()
    ap.add_argument("--shp", required=True)
    ap.add_argument("--allowlist", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--gap", nargs=2, type=float, default=(12.0, 48.0))
    a = ap.parse_args()
    allowed = set(pd.read_csv(a.allowlist)["Incident_C"])
    attrs = pyogrio.read_dataframe(a.shp, read_geometry=False)
    attrs["fid"] = np.arange(len(attrs))
    rows, skipped = [], 0
    for inc, at in attrs.groupby("Incident_C", sort=True):
        if inc not in allowed or len(at) < 2:
            continue
        g = pyogrio.read_dataframe(a.shp, fids=at["fid"].to_numpy())
        g["t"] = pd.to_datetime(g["UTC"])
        g = g[g.geometry.notna() & ~g.geometry.is_empty].sort_values("t").reset_index(drop=True)
        if len(g) < 2:
            continue
        g = g.to_crs(g.estimate_utm_crs())
        minx, miny, maxx, maxy = g.total_bounds
        pad = 8 * CELL
        x0 = math.floor((minx - pad) / CELL) * CELL
        y1 = math.ceil((maxy + pad) / CELL) * CELL
        w = int(math.ceil((maxx + pad - x0) / CELL))
        h = int(math.ceil((y1 - (miny - pad)) / CELL))
        if w * h > 4_000_000:
            skipped += 1
            continue
        tf = from_origin(x0, y1, CELL, CELL)
        burned = None
        for k in range(len(g)):
            r = rasterize([(g.geometry.iloc[k], 1)], out_shape=(h, w), transform=tf, fill=0,
                          dtype="uint8").astype(bool)
            if burned is None:
                burned = r
                continue
            gap = (g["t"].iloc[k] - g["t"].iloc[k - 1]).total_seconds() / 3600
            nxt = burned | r
            if a.gap[0] <= gap <= a.gap[1] and burned.any():
                res, _, _ = component_reach(burned, nxt & ~burned, (5.0, np.inf))
                rows.append(dict(incident=inc, t0=str(g["t"].iloc[k - 1]), t1=str(g["t"].iloc[k]), gap_h=gap,
                                 reach_km=res[5.0], reach_nosep_km=res[np.inf],
                                 new_cells=int((nxt & ~burned).sum())))
            burned = nxt
        print(inc, len(g), flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(a.out, index=False)
    print("pairs", len(df), "incidents", df.incident.nunique() if len(df) else 0, "skipped (grid too big)", skipped)


if __name__ == "__main__":
    main()
