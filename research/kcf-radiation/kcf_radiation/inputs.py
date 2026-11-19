"""Full-grid arrival seconds on a routing grid from either fire-input kind (replay GeoTIFF or finals packet), so the
spread rate can be read from the whole field and not only from road cells. Same reading rules as
product/wfg-roadlayer/wfg_roadlayer/fireinput.py; rows are returned SOUTH-UP (router row order: cell = r * W + c).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "product/wfg-roadlayer"))
from wfg_roadlayer import geotiff  # noqa: E402


def arrival_grid_geotiff(path, road):
    """Seconds after issue (float, +inf = not reached within the horizon, NaN = no data), on the road grid.
    The replay rasters share the 375 m lattice with the road grids (checked); pixel = cell."""
    r = geotiff.read(Path(path))
    a, b, c, d, e, f = r.affine
    if not (r.epsg == 5179 and b == 0 and d == 0 and abs(a - float(road.res)) < 1e-9 and abs(e + float(road.res)) < 1e-9):
        raise ValueError("raster is not on a 375 m EPSG:5179 lattice")
    H = float(r.metadata["WFG_HORIZON_MIN"]) * 60.0
    col0 = (float(road.x0) - c) / a
    row_top = (f - (float(road.y0) + float(road.res) * road.H)) / -e
    if abs(col0 - round(col0)) > 1e-6 or abs(row_top - round(row_top)) > 1e-6:
        raise ValueError("raster lattice is offset from the road grid")
    col0, row_top = int(round(col0)), int(round(row_top))
    out = np.full((road.H, road.W), np.nan)
    data = np.asarray(r.data, dtype=float)
    for rr in range(road.H):              # router row rr (south-up) = raster row row_top + (H-1-rr)
        src = row_top + road.H - 1 - rr
        if 0 <= src < data.shape[0]:
            lo, hi = max(col0, 0), min(col0 + road.W, data.shape[1])
            out[rr, lo - col0:hi - col0] = data[src, lo:hi]
    sec = np.where(np.isfinite(out), np.where(out <= 0, 0.0, np.floor(60.0 * out + 1e-6)), out)
    sec = np.where(np.isfinite(sec) & (sec > H), np.inf, sec)
    return sec, H


def arrival_grid_packet(pdir, road):
    pdir = Path(pdir)
    md = json.loads((pdir / "REPORT.json").read_text())["native_metadata"]
    H = float(md["construction"]["assumptions"]["horizon_s"])
    with np.load(pdir / "constructed_arrays.npz", allow_pickle=False) as z:
        ev = np.array(z["ignition_time_s"], dtype=float)
        cur = np.array(z["current_active"], dtype=bool)
        burned = np.array(z["mask__known_burned"], dtype=bool) if "mask__known_burned" in z.files else np.zeros_like(cur)
    first = np.where(np.isfinite(ev), ev, np.inf).min(axis=0)
    first = np.where(cur | burned, 0.0, first)
    first = np.where(np.isfinite(first), np.floor(first + 1e-9), np.inf)
    first = np.where(first > math.floor(H), np.inf, first)
    return first[::-1].copy(), H  # npz rows north-up -> router south-up


def cell_centres(road):
    rr, cc = np.mgrid[0:road.H, 0:road.W]
    x = float(road.x0) + (cc + 0.5) * float(road.res)
    y = float(road.y0) + (rr + 0.5) * float(road.res)
    return x, y
