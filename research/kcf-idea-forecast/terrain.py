"""Terrain inputs and the lee-slope-bypass ("ridge hop") kinematics. See IDEA.md.

DEM: Mapzen/AWS Terrarium tiles (zoom 11, ~60 m), resampled bilinearly to a metric grid of CELL m.
"""
import io, math, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from PIL import Image
from pyproj import Transformer
from scipy import ndimage

Z = 11
CELL = 90.0
TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"


def _tile(x, y, cache):
    p = Path(cache) / f"{Z}_{x}_{y}.png"
    if not p.exists():
        for k in range(6):
            try:
                r = requests.get(TILE_URL.format(z=Z, x=x, y=y), timeout=60)
                if r.status_code == 200:
                    p.write_bytes(r.content); break
            except requests.RequestException:
                pass
            time.sleep(2 * (k + 1))
        else:
            raise RuntimeError(f"tile {x},{y}")
    a = np.asarray(Image.open(io.BytesIO(p.read_bytes())).convert("RGB"), dtype=np.float64)
    return a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768


def dem_grid(epsg, x0, y0, x1, y1, cache):
    """Elevation (m) on a north-up grid of CELL m covering [x0,x1]x[y0,y1] in `epsg`. Returns (z, x0, y1)."""
    Path(cache).mkdir(parents=True, exist_ok=True)
    nx, ny = int(math.ceil((x1 - x0) / CELL)), int(math.ceil((y1 - y0) / CELL))
    X, Y = np.meshgrid(x0 + (np.arange(nx) + .5) * CELL, y1 - (np.arange(ny) + .5) * CELL)
    lon, lat = Transformer.from_crs(epsg, 4326, always_xy=True).transform(X, Y)
    n = 2 ** Z
    px = (lon + 180) / 360 * n * 256
    py = (1 - np.arcsinh(np.tan(np.radians(lat))) / math.pi) / 2 * n * 256
    tx0, tx1, ty0, ty1 = int(px.min() // 256), int(px.max() // 256), int(py.min() // 256), int(py.max() // 256)
    jobs = [(x, y) for y in range(ty0, ty1 + 1) for x in range(tx0, tx1 + 1)]
    with ThreadPoolExecutor(8) as ex:
        tiles = list(ex.map(lambda j: _tile(j[0], j[1], cache), jobs))
    mos = np.zeros(((ty1 - ty0 + 1) * 256, (tx1 - tx0 + 1) * 256))
    for (x, y), t in zip(jobs, tiles):
        mos[(y - ty0) * 256:(y - ty0 + 1) * 256, (x - tx0) * 256:(x - tx0 + 1) * 256] = t
    z = ndimage.map_coordinates(mos, [py - ty0 * 256 - .5, px - tx0 * 256 - .5], order=1, mode="nearest")
    return z, x0, y1


def rotate_to_wind(z, to_deg):
    """Rotate so the wind blows along +x (columns). to_deg = compass bearing the wind blows TOWARD."""
    # compass bearing b (clockwise from north) -> image rotation so that direction b maps to +x
    return ndimage.rotate(z, to_deg - 90.0, reshape=True, order=1, mode="constant", cval=np.nan)


def landing(zr, tanphi, z0, max_cells):
    """Ray-trace embers released z0 m above every cell, descending at slope tanphi along +x.

    Returns jump length in cells (0 if the ember comes down within one cell or flies > max_cells = burnout)."""
    ny, nx = zr.shape
    jump = np.zeros((ny, nx), np.int32)
    alive = np.isfinite(zr)
    h0 = zr + z0
    for k in range(1, max_cells + 1):
        ground = np.full_like(zr, np.nan); ground[:, :nx - k] = zr[:, k:]
        ray = h0 - k * CELL * tanphi
        hit = alive & (ray <= ground)
        jump[hit] = k
        alive &= ~hit & np.isfinite(ground)
    jump[jump == 1] = 0
    return jump


def speedup(zr, jump, r, t_i, U):
    """First-passage along +x with head rate r (m/s) and spot jumps (delay t_i + flight). Returns F = (L/r)/T,
    aggregated over rows as sum(L)/sum(r*T), using each row's finite span."""
    ny, nx = zr.shape
    T = np.full((ny, nx), np.inf)
    ok = np.isfinite(zr)
    first = ok.argmax(1)
    rows = np.arange(ny)
    T[rows, first] = 0.0
    step = CELL / r
    for x in range(nx):
        if x:
            T[:, x] = np.minimum(T[:, x], T[:, x - 1] + step)
        j = jump[:, x]
        m = (j > 0) & np.isfinite(T[:, x])
        if m.any():
            tx = x + j[m]
            cand = T[m, x] + t_i + j[m] * CELL / U
            np.minimum.at(T, (rows[m], tx), cand)
    last = nx - 1 - ok[:, ::-1].argmax(1)
    good = ok.any(1) & (last - first >= 20)
    L = (last - first)[good] * CELL
    Tt = T[rows[good], last[good]]
    return float(L.sum() / (r * Tt).sum())
