"""Minimal reader for the single-band, strip-organised, deflate or uncompressed float32 GeoTIFFs of the Zenodo
time-of-arrival archive (10.5281/zenodo.21788344, CC-BY-4.0). Standard library and NumPy only.

Returns the array, the affine transform (pixel-is-area, north-up) and the GDAL metadata tags (t0_utc etc.). Anything
else (tiles, predictors, other sample formats) is refused rather than guessed.
"""
from __future__ import annotations

import re
import struct
import zlib

import numpy as np

TYPES = {1: ("B", 1), 2: ("s", 1), 3: ("H", 2), 4: ("I", 4), 11: ("f", 4), 12: ("d", 8), 16: ("Q", 8)}


def read(path):
    data = open(path, "rb").read()
    bo = {b"II": "<", b"MM": ">"}[data[:2]]
    if struct.unpack(bo + "H", data[2:4])[0] != 42:
        raise ValueError("not a classic TIFF")
    off = struct.unpack(bo + "I", data[4:8])[0]
    n = struct.unpack(bo + "H", data[off:off + 2])[0]
    tags = {}
    for k in range(n):
        e = data[off + 2 + 12 * k: off + 14 + 12 * k]
        tag, typ, cnt = struct.unpack(bo + "HHI", e[:8])
        fmt, size = TYPES[typ]
        raw = e[8:12] if size * cnt <= 4 else data[struct.unpack(bo + "I", e[8:12])[0]:][:size * cnt]
        tags[tag] = raw[:cnt].decode("latin-1").rstrip("\x00") if fmt == "s" else struct.unpack(bo + fmt * cnt, raw[:size * cnt])
    W, H = tags[256][0], tags[257][0]
    if tags.get(277, (1,))[0] != 1 or tags[258][0] != 32 or tags.get(339, (1,))[0] != 3:
        raise ValueError("single-band float32 required")
    if 322 in tags or tags.get(317, (1,))[0] != 1:
        raise ValueError("tiles or predictors are not supported")
    comp = tags.get(259, (1,))[0]
    rows_per = tags.get(278, (H,))[0]
    buf = b""
    for o, c in zip(tags[273], tags[279]):
        chunk = data[o:o + c]
        if comp in (8, 32946):
            chunk = zlib.decompress(chunk)
        elif comp != 1:
            raise ValueError("compression %d not supported" % comp)
        buf += chunk
    arr = np.frombuffer(buf, dtype=bo + "f4")[:W * H].reshape(H, W).astype(np.float64)
    sx, sy = tags[33550][0], tags[33550][1]
    i, j, _, x, y, _ = tags[33922][:6]
    transform = (sx, 0.0, x - i * sx, 0.0, -sy, y + j * sy)
    meta = {}
    if 42112 in tags:
        for name, value in re.findall(r'<Item name="([^"]+)"[^>]*>([^<]*)</Item>', tags[42112]):
            meta[name] = value
    nodata = tags.get(42113)
    if nodata not in (None, ""):
        nd = float(nodata.strip())
        if not np.isnan(nd):
            arr = np.where(arr == nd, np.nan, arr)
    return arr, transform, meta
