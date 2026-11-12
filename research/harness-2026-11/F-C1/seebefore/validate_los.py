"""Independent cross-check of required_height(): recompute h_req for random (place, fire sub-point) pairs directly on
the raw GLO-30 tiles in EPSG:4326, sampling along the WGS84 geodesic (pyproj.Geod) with bilinear interpolation in
lat/lon, a scalar per-sample loop (no shared code path with viewshed.required_height except the formula).

    python3 seebefore/validate_los.py --surface _data/surface_glo30_5179_30m.npz --tiles _data/raw/*.tif --n 300
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seebefore import dem, extract, fire  # noqa: E402
from seebefore.viewshed import K_REFRACTION, R_EARTH, required_height, subpoints  # noqa: E402


class Raw:
    def __init__(self, tiles):
        import rasterio
        from rasterio.merge import merge
        srcs = [rasterio.open(t) for t in tiles]
        m, tr = merge(srcs, nodata=-32767.0)
        self.z = m[0].astype(float)
        self.z[self.z == -32767.0] = np.nan
        self.lon0, self.dlon, self.lat0, self.dlat = tr.c, tr.a, tr.f, tr.e     # dlat < 0

    def at(self, lon, lat):
        c = (lon - self.lon0) / self.dlon - 0.5
        r = (lat - self.lat0) / self.dlat - 0.5
        c0, r0 = int(math.floor(c)), int(math.floor(r))
        dc, dr = c - c0, r - r0
        z = self.z
        return (z[r0, c0] * (1 - dc) * (1 - dr) + z[r0, c0 + 1] * dc * (1 - dr) +
                z[r0 + 1, c0] * (1 - dc) * dr + z[r0 + 1, c0 + 1] * dc * dr)


def hreq_geodesic(raw, geod, lon_o, lat_o, lon_t, lat_t, eye, step=10.0):
    c = (1 - K_REFRACTION) / (2 * R_EARTH)
    _, _, D = geod.inv(lon_o, lat_o, lon_t, lat_t)
    n = int(D // step)
    pts = geod.npts(lon_o, lat_o, lon_t, lat_t, n) if n > 0 else []
    ze = raw.at(lon_o, lat_o) + eye
    gt = raw.at(lon_t, lat_t) - c * D * D
    worst = -math.inf
    for i, (lo, la) in enumerate(pts, start=1):
        s = D * i / (n + 1)
        if s <= 0 or s >= D:
            continue
        g = raw.at(lo, la) - c * s * s
        worst = max(worst, (g - ze) / (s / D))
    return max(0.0, worst - (gt - ze)), D


def main():
    from pyproj import Geod, Transformer
    ap = argparse.ArgumentParser()
    ap.add_argument('--surface', type=Path, required=True)
    ap.add_argument('--tiles', nargs='+', type=Path, required=True)
    ap.add_argument('--n', type=int, default=300)
    ap.add_argument('--seed', type=int, default=20261112)
    ap.add_argument('--main-step', type=float, default=15.0)
    ap.add_argument('--ind-step', type=float, default=10.0)
    a = ap.parse_args()
    surface, _ = dem.load(a.surface)
    raw = Raw(a.tiles)
    geod = Geod(ellps='WGS84')
    inv = Transformer.from_crs(5179, 4326, always_xy=True)
    cases = extract.build()
    rnd = random.Random(a.seed)
    fs_cache = {}
    diffs, agree, n = [], 0, 0
    rel = []          # pairs where either value is below the largest threshold (the decision-relevant range)
    thresholds = (2.0, 10.0, 30.0, 150.0, 1000.0)
    flips = 0
    for _ in range(a.n):
        c = rnd.choice(cases)
        if c['scope'] not in fs_cache:
            fs_cache[c['scope']] = fire.load(c['region'], c['scope'].split('/')[1])
        fs = fs_cache[c['scope']]
        cell = fs.present_xy[rnd.randrange(len(fs.present_xy))]
        sp = subpoints(cell[None, :])[0][rnd.randrange(9)]
        h_main = required_height(surface, c['place_x'], c['place_y'], [2.0], [sp[0]], [sp[1]], step=a.main_step)[0, 0]
        lo, la = inv.transform(c['place_x'], c['place_y'])
        lt, lat = inv.transform(sp[0], sp[1])
        h_ind, D = hreq_geodesic(raw, geod, lo, la, lt, lat, 2.0, step=a.ind_step)
        n += 1
        diffs.append(h_main - h_ind)
        if min(h_main, h_ind) < max(thresholds):
            rel.append(h_main - h_ind)
        flips += sum((h_main < t) != (h_ind < t) for t in thresholds)
        agree += all((h_main < t) == (h_ind < t) for t in thresholds)
    d = np.array(diffs)
    print(f'pairs {n}; h_req main - independent: median {np.median(d):.2f} m, p05 {np.percentile(d, 5):.2f}, '
          f'p95 {np.percentile(d, 95):.2f}, max |d| {np.abs(d).max():.2f}')
    r = np.array(rel)
    print(f'decision-relevant pairs (min h_req < {max(thresholds):.0f} m): {r.size}; median diff {np.median(r):.2f} m, '
          f'p05 {np.percentile(r, 5):.2f}, p95 {np.percentile(r, 95):.2f}, max |d| {np.abs(r).max():.2f}')
    print(f'visibility verdict agreement at heights {thresholds}: {agree}/{n} pairs fully agree; '
          f'{flips} threshold flips of {n * len(thresholds)}')


if __name__ == '__main__':
    main()
