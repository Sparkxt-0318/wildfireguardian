"""Minimal single-band GeoTIFF reader and writer (numpy + standard library only; no GDAL).

Reads what GIS tools commonly write for one-band rasters:
  * classic TIFF and BigTIFF, little- or big-endian;
  * strips or tiles; compression none (1), LZW (5), Deflate (8, 32946), PackBits (32773);
  * predictor 1, 2 (integer samples) and 3 (floating point);
  * sample types uint8/16/32, int8/16/32, float32/64;
  * GeoTIFF georeferencing: ModelPixelScale + one ModelTiepoint, or ModelTransformation; EPSG code from
    ProjectedCSTypeGeoKey (3072) or GeographicTypeGeoKey (2048); PixelIsPoint is shifted by half a pixel, as GDAL does;
  * GDAL_NODATA (42113) and GDAL_METADATA (42112) dataset items.

Anything else raises ``GeoTiffError`` with the reason; nothing is guessed.
"""
from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
import zlib
from dataclasses import dataclass, field

import numpy as np

_TYPES = {1: ("B", 1), 2: ("s", 1), 3: ("H", 2), 4: ("I", 4), 5: ("II", 8), 6: ("b", 1), 7: ("B", 1), 8: ("h", 2),
          9: ("i", 4), 10: ("ii", 8), 11: ("f", 4), 12: ("d", 8), 16: ("Q", 8), 17: ("q", 8), 18: ("Q", 8)}
_DTYPES = {(1, 8): "u1", (1, 16): "u2", (1, 32): "u4", (2, 8): "i1", (2, 16): "i2", (2, 32): "i4", (3, 32): "f4",
           (3, 64): "f8"}


class GeoTiffError(ValueError):
    pass


@dataclass
class GeoRaster:
    data: np.ndarray                 # (rows, cols), float64
    affine: tuple                    # (a, b, c, d, e, f): x = a*col + b*row + c, y = d*col + e*row + f (pixel corner)
    epsg: int | None
    nodata: float | None
    metadata: dict = field(default_factory=dict)
    info: dict = field(default_factory=dict)

    @property
    def shape(self):
        return self.data.shape


def _lzw_decode(data: bytes) -> bytes:
    """TIFF LZW (MSB-first codes, early change)."""
    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    bitpos, nbits, n = 0, 9, len(data) * 8
    prev = None
    while bitpos + nbits <= n:
        byte = bitpos >> 3
        chunk = int.from_bytes(data[byte:byte + 4].ljust(4, b"\0"), "big")
        code = (chunk >> (32 - (bitpos & 7) - nbits)) & ((1 << nbits) - 1)
        bitpos += nbits
        if code == 256:
            table = table[:258]
            nbits, prev = 9, None
            continue
        if code == 257:
            break
        if prev is None:
            entry = table[code]
            out += entry
            prev = entry
            continue
        if code < len(table):
            entry = table[code]
            table.append(prev + entry[:1])
        elif code == len(table):
            entry = prev + prev[:1]
            table.append(entry)
        else:
            raise GeoTiffError("corrupt LZW stream")
        out += entry
        prev = entry
        if len(table) + 1 >= (1 << nbits) and nbits < 12:
            nbits += 1
    return bytes(out)


def _packbits_decode(data: bytes) -> bytes:
    out, i = bytearray(), 0
    while i < len(data):
        h = data[i]
        i += 1
        if h < 128:
            out += data[i:i + h + 1]
            i += h + 1
        elif h > 128:
            out += data[i:i + 1] * (257 - h)
            i += 1
    return bytes(out)


class _Reader:
    def __init__(self, buf: bytes):
        self.b = buf
        if buf[:2] == b"II":
            self.e = "<"
        elif buf[:2] == b"MM":
            self.e = ">"
        else:
            raise GeoTiffError("not a TIFF file")
        magic = struct.unpack(self.e + "H", buf[2:4])[0]
        if magic == 42:
            self.big = False
            self.ifd = struct.unpack(self.e + "I", buf[4:8])[0]
        elif magic == 43:
            self.big = True
            self.ifd = struct.unpack(self.e + "Q", buf[8:16])[0]
        else:
            raise GeoTiffError("not a TIFF file (magic %d)" % magic)

    def tags(self):
        e, b = self.e, self.b
        off = self.ifd
        if self.big:
            n = struct.unpack(e + "Q", b[off:off + 8])[0]
            off += 8
            esz, vsz = 20, 8
        else:
            n = struct.unpack(e + "H", b[off:off + 2])[0]
            off += 2
            esz, vsz = 12, 4
        out = {}
        for k in range(n):
            p = off + k * esz
            if self.big:
                tag, typ, cnt = struct.unpack(e + "HHQ", b[p:p + 12])
                vp = p + 12
            else:
                tag, typ, cnt = struct.unpack(e + "HHI", b[p:p + 8])
                vp = p + 8
            if typ not in _TYPES:
                continue
            fmt, size = _TYPES[typ]
            total = size * cnt
            if total > vsz:
                vp = struct.unpack(e + ("Q" if self.big else "I"), b[vp:vp + vsz])[0]
            raw = b[vp:vp + total]
            if typ == 2:
                out[tag] = raw.split(b"\0")[0].decode("utf-8", "replace")
            elif typ in (5, 10):
                v = struct.unpack(e + fmt[0] * (2 * cnt), raw)
                out[tag] = [v[i] / v[i + 1] if v[i + 1] else float("nan") for i in range(0, len(v), 2)]
            else:
                out[tag] = list(struct.unpack(e + fmt * cnt, raw))
        return out


def _one(tags, tag, default=None):
    v = tags.get(tag, default)
    if isinstance(v, list):
        if len(set(v)) != 1:
            raise GeoTiffError("tag %d has differing values %r (only one band is supported)" % (tag, v[:4]))
        return v[0]
    return v


def read(path, *, require_georef: bool = True) -> GeoRaster:
    with open(path, "rb") as f:
        buf = f.read()
    r = _Reader(buf)
    t = r.tags()
    W, H = _one(t, 256), _one(t, 257)
    spp = _one(t, 277, 1)
    if spp != 1:
        raise GeoTiffError("expected a single band, found %d samples per pixel" % spp)
    bits = _one(t, 258, 1)
    fmt = _one(t, 339, 1)
    if (fmt, bits) not in _DTYPES:
        raise GeoTiffError("unsupported sample type (format %s, %s bits)" % (fmt, bits))
    dt = np.dtype(r.e + _DTYPES[(fmt, bits)])
    comp = _one(t, 259, 1)
    pred = _one(t, 317, 1)
    if comp not in (1, 5, 8, 32946, 32773):
        raise GeoTiffError("unsupported compression %d (supported: none, LZW, Deflate, PackBits)" % comp)
    if pred not in (1, 2, 3):
        raise GeoTiffError("unsupported predictor %d" % pred)
    if pred == 2 and dt.kind == "f":
        raise GeoTiffError("predictor 2 on floating-point samples is not supported")
    if pred == 3 and dt.kind != "f":
        raise GeoTiffError("predictor 3 needs floating-point samples")
    if 322 in t:
        bw, bh = _one(t, 322), _one(t, 323)
        offs, cnts = t[324], t[325]
    else:
        bw, bh = W, min(_one(t, 278, H), H)
        offs, cnts = t[273], t[279]
    out = np.empty((H, W), dtype=dt.newbyteorder("="))
    across = -(-W // bw)
    for k, (o, c) in enumerate(zip(offs, cnts)):
        raw = buf[o:o + c]
        if comp == 1:
            dec = raw
        elif comp == 5:
            dec = _lzw_decode(raw)
        elif comp in (8, 32946):
            dec = zlib.decompress(raw)
        else:
            dec = _packbits_decode(raw)
        if 322 in t:
            r0, c0 = (k // across) * bh, (k % across) * bw
            rows, cols = bh, bw
        else:
            r0, c0 = k * bh, 0
            rows, cols = min(bh, H - r0), W
        need = rows * cols * dt.itemsize
        if len(dec) < need:
            raise GeoTiffError("block %d is truncated (%d of %d bytes)" % (k, len(dec), need))
        if pred == 3:
            a = np.frombuffer(dec[:need], dtype=np.uint8).reshape(rows, cols * dt.itemsize)
            a = np.cumsum(a, axis=1, dtype=np.uint8)
            a = a.reshape(rows, dt.itemsize, cols).transpose(0, 2, 1).copy()
            block = a.view(np.dtype(">" + dt.str[1:])).reshape(rows, cols).astype(out.dtype)
        else:
            block = np.frombuffer(dec[:need], dtype=dt).reshape(rows, cols).astype(out.dtype)
            if pred == 2:
                block = np.cumsum(block, axis=1, dtype=out.dtype)
        rr, cc = min(rows, H - r0), min(cols, W - c0)
        out[r0:r0 + rr, c0:c0 + cc] = block[:rr, :cc]
    geok = t.get(34735)
    epsg, keys = None, {}
    if geok:
        n = geok[3]
        for i in range(n):
            kid, loc, cnt, val = geok[4 + 4 * i: 8 + 4 * i]
            if loc == 0:
                keys[kid] = val
        model = keys.get(1024)
        if keys.get(3072) not in (None, 32767) and model in (None, 1):
            epsg = keys[3072]
        elif keys.get(2048) not in (None, 32767) and model in (None, 2):
            epsg = keys[2048]
    if 34264 in t:
        m = t[34264]
        aff = (m[0], m[1], m[3], m[4], m[5], m[7])
    elif 33550 in t and 33922 in t:
        sx, sy = t[33550][0], t[33550][1]
        tp = t[33922]
        if len(tp) != 6:
            raise GeoTiffError("only a single ModelTiepoint is supported")
        I, J, X, Y = tp[0], tp[1], tp[3], tp[4]
        aff = (sx, 0.0, X - I * sx, 0.0, -sy, Y + J * sy)
    elif require_georef:
        raise GeoTiffError("no georeferencing (ModelPixelScale/ModelTiepoint or ModelTransformation)")
    else:
        aff = (1.0, 0.0, 0.0, 0.0, -1.0, 0.0)
    if keys.get(1025) == 2:  # PixelIsPoint: the tie point is a pixel centre
        a, b, c, d, e, f = aff
        aff = (a, b, c - 0.5 * a - 0.5 * b, d, e, f - 0.5 * d - 0.5 * e)
    nodata = None
    if 42113 in t:
        s = t[42113].strip()
        try:
            nodata = float(s)
        except ValueError as exc:
            raise GeoTiffError("unreadable GDAL_NODATA %r" % s) from exc
    md = {}
    if 42112 in t:
        try:
            root = ET.fromstring(t[42112])
            for it in root.iter("Item"):
                if it.get("sample") is None and it.get("role") is None:
                    md[it.get("name")] = (it.text or "").strip()
        except ET.ParseError as exc:
            raise GeoTiffError("unreadable GDAL_METADATA") from exc
    info = {"width": W, "height": H, "compression": comp, "predictor": pred, "dtype": dt.name,
            "byte_order": "little" if r.e == "<" else "big", "bigtiff": r.big, "tiled": 322 in t,
            "raster_type": "PixelIsPoint" if keys.get(1025) == 2 else "PixelIsArea"}
    return GeoRaster(out.astype(np.float64), tuple(float(v) for v in aff), epsg, nodata, md, info)


def write(path, data: np.ndarray, affine: tuple, epsg: int, *, nodata=None, metadata: dict | None = None,
          dtype="float64", deflate=True, geographic=False):
    """Write a little-endian classic GeoTIFF, one band, one strip per 16 rows, optional Deflate."""
    a = np.ascontiguousarray(np.asarray(data, dtype=dtype))
    H, W = a.shape
    sx, b, x0, d, ey, y0 = affine
    if b != 0 or d != 0 or ey >= 0:
        raise GeoTiffError("writer supports north-up, unrotated rasters only")
    rps = 16
    strips = []
    for r0 in range(0, H, rps):
        raw = a[r0:r0 + rps].astype("<" + a.dtype.str[1:]).tobytes()
        strips.append(zlib.compress(raw, 9) if deflate else raw)
    fmt = 3 if a.dtype.kind == "f" else (2 if a.dtype.kind == "i" else 1)
    keys = [1, 1, 0, 3, 1024, 0, 1, 2 if geographic else 1, 1025, 0, 1, 1,
            2048 if geographic else 3072, 0, 1, int(epsg)]
    md_xml = None
    if metadata:
        items = "".join('<Item name="%s">%s</Item>' % (k, _xml_escape(str(v))) for k, v in sorted(metadata.items()))
        md_xml = "<GDALMetadata>%s</GDALMetadata>" % items
    entries = [(256, 4, [W]), (257, 4, [H]), (258, 3, [a.dtype.itemsize * 8]), (259, 3, [8 if deflate else 1]),
               (262, 3, [1]), (273, 4, [0] * len(strips)), (277, 3, [1]), (278, 4, [rps]),
               (279, 4, [len(s) for s in strips]), (284, 3, [1]), (339, 3, [fmt]),
               (33550, 12, [sx, -ey, 0.0]), (33922, 12, [0.0, 0.0, 0.0, x0, y0, 0.0]), (34735, 3, keys)]
    if md_xml is not None:
        entries.append((42112, 2, md_xml))
    if nodata is not None:
        entries.append((42113, 2, repr(float(nodata)) if not np.isnan(nodata) else "nan"))
    entries.sort()
    # layout: header, strips, IFD, out-of-line values
    out = bytearray(b"II*\0\0\0\0\0")
    strip_offs = []
    for s in strips:
        strip_offs.append(len(out))
        out += s
        if len(out) % 2:
            out += b"\0"
    ifd_off = len(out)
    n = len(entries)
    ext_off = ifd_off + 2 + 12 * n + 4
    ifd = bytearray(struct.pack("<H", n))
    ext = bytearray()
    sizes = {2: 1, 3: 2, 4: 4, 12: 8}
    codes = {3: "H", 4: "I", 12: "d"}
    for tag, typ, vals in entries:
        if tag == 273:
            vals = strip_offs
        if typ == 2:
            raw = vals.encode("utf-8") + b"\0"
            cnt = len(raw)
        else:
            raw = struct.pack("<" + codes[typ] * len(vals), *vals)
            cnt = len(vals)
        if len(raw) <= 4:
            ifd += struct.pack("<HHI", tag, typ, cnt) + raw.ljust(4, b"\0")
        else:
            ifd += struct.pack("<HHII", tag, typ, cnt, ext_off + len(ext))
            ext += raw
            if len(ext) % 2:
                ext += b"\0"
    ifd += b"\0\0\0\0"
    out += ifd + ext
    out[4:8] = struct.pack("<I", ifd_off)
    with open(path, "wb") as f:
        f.write(bytes(out))


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
