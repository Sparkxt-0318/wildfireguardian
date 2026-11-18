#!/usr/bin/env python3
"""Height of 850 hPa against the local ridge (PROTOCOL.md section 5).

    python3 height.py --fire derived/fire_hours.csv.gz --burden derived/burden_days.csv.gz --tiles TILE_DIR --out derived/height.json

Ground: SRTM 1 arc-second tiles (AWS elevation-tiles-prod, skadi), highest cell within 10 km and within 25 km of a
place. 850 hPa: the GFS forecast geopotential height already stored with each hour (mean over the four lattice
points and the leads 6, 12, 18 h in the window). Model terrain: GFS HGT:surface at the four lattice points.
"""
import argparse
import gzip
import json
import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "kcf-abstain"))
from fetch_nwp import get  # noqa: E402
from burden import POINTS  # noqa: E402

TILE = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/N{la:02d}/N{la:02d}E{lo:03d}.hgt.gz"
OROG = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20250325/00/atmos/gfs.t00z.pgrb2.0p25.f006"
TDIR = None


@lru_cache(maxsize=16)
def tile(la, lo):
    p = Path(TDIR) / f"N{la:02d}E{lo:03d}.hgt.gz"
    if not p.exists():
        b = get(TILE.format(la=la, lo=lo))
        if b is None:
            return None
        p.write_bytes(b)
    a = np.frombuffer(gzip.decompress(p.read_bytes()), dtype=">i2").reshape(3601, 3601).astype(np.float32)
    a[a < -1000] = np.nan            # voids and sea
    return a


def max_within(lat, lon, radii=(10.0, 25.0)):
    """Highest ground (m) within each radius (km) of (lat, lon)."""
    rmax = max(radii)
    dlat = rmax / 111.2
    dlon = rmax / (111.2 * math.cos(math.radians(lat)))
    best = {r: -math.inf for r in radii}
    for la in range(math.floor(lat - dlat), math.floor(lat + dlat) + 1):
        for lo in range(math.floor(lon - dlon), math.floor(lon + dlon) + 1):
            a = tile(la, lo)
            if a is None:
                continue
            r0 = max(0, int((la + 1 - (lat + dlat)) * 3600))
            r1 = min(3601, int((la + 1 - (lat - dlat)) * 3600) + 2)
            c0 = max(0, int((lon - dlon - lo) * 3600))
            c1 = min(3601, int((lon + dlon - lo) * 3600) + 2)
            if r1 <= r0 or c1 <= c0:
                continue
            sub = a[r0:r1, c0:c1]
            yy = (la + 1 - np.arange(r0, r1) / 3600.0)[:, None]
            xx = (lo + np.arange(c0, c1) / 3600.0)[None, :]
            d = np.hypot((yy - lat) * 111.2, (xx - lon) * 111.2 * math.cos(math.radians(lat)))
            for r in radii:
                m = np.where(d <= r, sub, np.nan)
                if np.isfinite(m).any():
                    best[r] = max(best[r], float(np.nanmax(m)))
    return {r: (None if best[r] == -math.inf else best[r]) for r in radii}


def model_terrain():
    import pygrib
    idx = get(OROG + ".idx").decode().splitlines()
    L = [l.split(":") for l in idx]
    for i, l in enumerate(L):
        if l[3] == "HGT" and l[4] == "surface":
            b = get(OROG, (int(l[1]), int(L[i + 1][1]) - 1))
            return np.ma.filled(pygrib.fromstring(b).values.astype(float), np.nan)
    raise RuntimeError("no HGT:surface")


def lattice4(orog, lat, lon):
    i0, j0 = math.floor(lat / 0.25) * 0.25, math.floor(lon / 0.25) * 0.25
    v = [float(orog[int(round((90.0 - (i0 + a)) / 0.25)), int(round((j0 + b) / 0.25))]) for a in (0, 0.25) for b in (0, 0.25)]
    return [round(x) for x in v]


def main():
    global TDIR
    ap = argparse.ArgumentParser()
    ap.add_argument("--fire", required=True)
    ap.add_argument("--burden", required=True)
    ap.add_argument("--tiles", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    TDIR = a.tiles
    Path(TDIR).mkdir(parents=True, exist_ok=True)
    orog = model_terrain()
    fh = pd.read_csv(a.fire, low_memory=False)
    fh = fh[(fh.timeline == "primary") & fh.issue.astype(bool)]
    out = dict(source=dict(ground="SRTM 1 arc-second, AWS elevation-tiles-prod (skadi)", level="GFS HGT:850 mb, leads 6/12/18 h",
                           model_terrain="GFS HGT:surface, cycle 2025-03-25 00 UTC f006"), fires={}, points={})
    for fire, g in fh.groupby("fire", sort=True):
        pos = g[["lat", "lon"]].round(2).drop_duplicates()
        m = [max_within(r.lat, r.lon) for r in pos.itertuples(index=False)]
        r10 = max(x[10.0] for x in m)
        r25 = max(x[25.0] for x in m)
        h = g.hgt850_m.dropna()
        out["fires"][fire] = dict(
            name=g.name.iloc[0], positions=int(len(pos)), ridge_10km_m=round(r10), ridge_25km_m=round(r25),
            hgt850_median_m=round(float(h.median())), hgt850_min_m=round(float(h.min())), hgt850_max_m=round(float(h.max())),
            gap_to_ridge_10km_m=round(float(h.median()) - r10), gap_to_ridge_25km_m=round(float(h.median()) - r25),
            smallest_gap_25km_m=round(float(h.min()) - r25),
            model_terrain_4pts_m=lattice4(orog, float(g.lat.median()), float(g.lon.median())))
        print(fire, out["fires"][fire], flush=True)
    bd = pd.read_csv(a.burden)
    for p, (prov, lat, lon) in POINTS.items():
        m = max_within(lat, lon)
        h = bd[bd.point == p].hgt850_m.dropna()
        out["points"][p] = dict(province=prov, ridge_10km_m=round(m[10.0]), ridge_25km_m=round(m[25.0]),
                                hgt850_median_m=round(float(h.median())), hgt850_min_m=round(float(h.min())),
                                hgt850_max_m=round(float(h.max())), gap_to_ridge_10km_m=round(float(h.median()) - m[10.0]),
                                gap_to_ridge_25km_m=round(float(h.median()) - m[25.0]),
                                smallest_gap_25km_m=round(float(h.min()) - m[25.0]),
                                model_terrain_4pts_m=lattice4(orog, lat, lon))
        print(p, out["points"][p], flush=True)
    json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
