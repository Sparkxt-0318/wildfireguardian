"""OpenStreetMap basemap for the real-map figures (F07_map, F08_map).

Tiles of the OpenStreetMap standard layer (https://tile.openstreetmap.org, "© OpenStreetMap contributors", tiles
CC BY-SA 2.0, data ODbL) are fetched once, at low volume with an identifying User-Agent, into build/osm_tiles/ and
committed with build/osm_tiles/TILES.json (URL, fetch time, SHA-256), so later builds need no network. The stitched
tiles are turned to grey and faded towards paper so the five figure colours stay readable on top.

Figures draw in Web Mercator metres (EPSG:3857), the tiles' own projection, with equal aspect.
"""
import hashlib
import io
import json
import math
import time
import urllib.request
from datetime import datetime, timezone

import matplotlib.colors as mc
import numpy as np
from PIL import Image
from pyproj import Transformer

import style as S

TILES = S.BUILD / "osm_tiles"
URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
UA = "kcf-talk-figures/1.0 (static research figure; tiles cached and attributed)"
ATTRIBUTION = "Basemap © OpenStreetMap contributors"
R_EARTH = 6378137.0
HALF = math.pi * R_EARTH
TO_M = Transformer.from_crs(4326, 3857, always_xy=True)


def to_m(lonlat):
    a = np.asarray(lonlat, dtype=float)
    x, y = TO_M.transform(a[..., 0], a[..., 1])
    return np.stack([x, y], axis=-1)


def _tile_xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n
    return x, y


def _manifest():
    p = TILES / "TILES.json"
    return json.loads(p.read_text()) if p.exists() else {"source": URL, "attribution": ATTRIBUTION, "tiles": {}}


def _get(z, x, y, man):
    p = TILES / f"{z}/{x}/{y}.png"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL.format(z=z, x=x, y=y), headers={"User-Agent": UA})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read()
                Image.open(io.BytesIO(data)).verify()
                break
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(1.0 + attempt)
        p.write_bytes(data)
        man["tiles"][f"{z}/{x}/{y}"] = {"fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                        "sha256": hashlib.sha256(data).hexdigest()}
        time.sleep(0.2)
    return Image.open(p).convert("RGB")


def basemap(bbox_lonlat, z, fade=0.55):
    """(image as float RGB array, extent [x0, x1, y0, y1] in EPSG:3857 metres) covering bbox_lonlat at zoom z.
    fade: 0 keeps the grey tiles, 1 turns them to paper."""
    lon0, lat0, lon1, lat1 = bbox_lonlat
    xa, ya = _tile_xy(lon0, lat1, z)
    xb, yb = _tile_xy(lon1, lat0, z)
    xs = range(int(math.floor(xa)), int(math.floor(xb)) + 1)
    ys = range(int(math.floor(ya)), int(math.floor(yb)) + 1)
    man = _manifest()
    img = Image.new("RGB", (256 * len(xs), 256 * len(ys)))
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            img.paste(_get(z, x, y, man), (256 * i, 256 * j))
    (TILES / "TILES.json").write_text(json.dumps(man, indent=1, sort_keys=True))
    a = np.asarray(img, dtype=float) / 255.0
    lum = a @ np.array([0.2126, 0.7152, 0.0722])
    paper = np.array(mc.to_rgb(S.PAPER))
    grey_lo = np.array(mc.to_rgb(S.GREY))
    # luminance 1 -> paper, luminance 0 -> grey; then fade towards paper
    rgb = grey_lo[None, None, :] + (paper - grey_lo)[None, None, :] * lum[..., None]
    rgb = rgb + (paper - rgb) * fade
    size = 2 * HALF / 2 ** z
    x0 = -HALF + xs[0] * size
    x1 = -HALF + (xs[-1] + 1) * size
    y1 = HALF - ys[0] * size
    y0 = HALF - (ys[-1] + 1) * size
    return np.clip(rgb, 0, 1), [x0, x1, y0, y1]


def tiles_used(z, bbox_lonlat):
    lon0, lat0, lon1, lat1 = bbox_lonlat
    xa, ya = _tile_xy(lon0, lat1, z)
    xb, yb = _tile_xy(lon1, lat0, z)
    return (int(math.floor(xb)) - int(math.floor(xa)) + 1) * (int(math.floor(yb)) - int(math.floor(ya)) + 1)
