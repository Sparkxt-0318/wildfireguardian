#!/usr/bin/env python3
"""Build the planner's offline basemap: Protomaps vector-tile extracts, glyphs and sprites.

Owner: basemap builder (see planner/docs/ARCHITECTURE.md §2). Writes only planner/public/basemap/**
(plus an optional raw cache under planner/.assets/basemap_cache/, gitignored).

What it does
------------
1. Region extents come from the recorded road graphs (``graphs/<region>/graph.json`` of
   WFG-evaluated-routing-inputs-20261015, read from the extracted copy if present, else straight from
   the release zip). Node coordinates are EPSG:5179 and are converted to WGS84 with pyproj. The
   lon/lat bounding box of all nodes is padded on every side by 15 % of its width / height.
2. Tiles are copied byte-for-byte (still gzip-compressed MVT) from a Protomaps daily planet build
   (OpenStreetMap data, ODbL) using HTTP Range requests only; directories are cached and adjacent tile
   payloads are fetched in coalesced ranges. No tile.openstreetmap.org raster tiles are used.
   Per region: every z0-z15 tile intersecting the padded box plus a South Korea context box at z0-z8.
   Output: ``planner/public/basemap/<region_id>.pmtiles`` (PMTiles v3).
   The two demo regions are always built first; the other regions are kept only while the total size of
   all region archives stays at or below ``--budget-mb`` (default 40 MB).
3. Glyph PBFs for the font stacks used by @protomaps/basemaps 5.x (all 256 ranges per stack) and the
   v4 sprites (light, white, grayscale) from protomaps.github.io/basemaps-assets.
4. ``SOURCES.json`` with source URL/build, boxes, zooms, tile counts and per-file sha256/sizes.
5. Verification: every written archive is reopened, its header/metadata checked, every tile compared
   with the source bytes, and the z14 tile at the region centre decoded (layer names + feature counts).

Usage
-----
    python3 planner/tools/build_basemap.py                 # tiles + fonts + sprites + SOURCES.json + verify
    python3 planner/tools/build_basemap.py --skip-assets   # tiles only
    python3 planner/tools/build_basemap.py --verify-only   # re-check what is on disk
    python3 planner/tools/build_basemap.py --regions uiseong_andong_2025 yeongdeok_2025

Network: urllib honours HTTPS_PROXY. Everything is deterministic for a fixed source build.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as _dt
import gzip
import hashlib
import io
import json
import math
import os
import shutil
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from pyproj import Transformer
from pmtiles.reader import MmapSource, Reader, all_tiles
from pmtiles.tile import (
    Compression,
    TileType,
    deserialize_directory,
    deserialize_header,
    find_tile,
    tileid_to_zxy,
    zxy_to_tileid,
)
from pmtiles.writer import Writer

# --------------------------------------------------------------------------------------------------
# Fixed configuration
# --------------------------------------------------------------------------------------------------
PLANNER = Path(__file__).resolve().parents[1]
REPO = PLANNER.parent
OUT_DIR_DEFAULT = PLANNER / "public" / "basemap"
CACHE_DIR_DEFAULT = PLANNER / ".assets" / "basemap_cache"

INPUTS_ASSET = "WFG-evaluated-routing-inputs-20261015.zip"
INPUTS_SHA256 = "d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202"
INPUTS_ZIP = PLANNER / ".assets" / "release" / INPUTS_ASSET
INPUTS_EXTRACTED = PLANNER / ".assets" / "extracted" / "WFG-evaluated-routing-inputs-20261015"

SOURCE_BUILD = "20261016"
SOURCE_URL = f"https://build.protomaps.com/{SOURCE_BUILD}.pmtiles"

DEMO_REGIONS = ["uiseong_andong_2025", "yeongdeok_2025"]
OTHER_REGIONS = ["uljin_2022", "miryang_2022", "hongseong_2023"]
ALL_REGIONS = DEMO_REGIONS + OTHER_REGIONS

PAD_FRACTION = 0.15
DETAIL_MINZOOM, DETAIL_MAXZOOM = 0, 15
CONTEXT_NAME = "South Korea context"
CONTEXT_BBOX = (124.5, 33.0, 131.0, 38.7)  # w, s, e, n
CONTEXT_MINZOOM, CONTEXT_MAXZOOM = 0, 8
BUDGET_MB_DEFAULT = 40.0

ASSETS_BASE = "https://protomaps.github.io/basemaps-assets"
STYLE_PACKAGE = "@protomaps/basemaps@5.7.2"
# Font stacks referenced by "text-font" in @protomaps/basemaps 5.7.2 dist (layers()):
# e.regular||"Noto Sans Regular", e.bold||"Noto Sans Medium", e.italic||"Noto Sans Italic" and
# "Noto Sans Devanagari Regular v1" (used only for features whose script is Devanagari).
FONTSTACKS = [
    "Noto Sans Regular",
    "Noto Sans Medium",
    "Noto Sans Italic",
    "Noto Sans Devanagari Regular v1",
]
GLYPH_RANGES = [f"{s}-{s + 255}" for s in range(0, 65536, 256)]
SPRITE_FLAVORS = ["light", "white", "grayscale"]
SPRITE_SUFFIXES = [".json", ".png", "@2x.json", "@2x.png"]

USER_AGENT = "WildfireGuardian-planner-basemap-builder/1.0 (+offline extract; range requests)"
ATTRIBUTION_HTML = (
    '<a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap contributors</a>'
)
ATTRIBUTION_TEXT = "© OpenStreetMap contributors"

_print_lock = threading.Lock()


def log(*a):
    with _print_lock:
        print(*a, flush=True)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(REPO))
    except ValueError:
        return str(p)


# --------------------------------------------------------------------------------------------------
# HTTP with retries
# --------------------------------------------------------------------------------------------------
class HttpError(RuntimeError):
    pass


def http_get(url: str, byte_range: tuple[int, int] | None = None, retries: int = 6,
             timeout: float = 120.0) -> tuple[bytes, dict]:
    """GET url (optionally bytes=start..end inclusive). Retries with exponential backoff.

    Returns (body, headers). For range requests the response must be 206 with the exact length.
    """
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    if byte_range is not None:
        headers["Range"] = f"bytes={byte_range[0]}-{byte_range[1]}"
    delay = 1.0
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                hdrs = {k.lower(): v for k, v in resp.headers.items()}
                status = resp.status
            if byte_range is not None:
                want = byte_range[1] - byte_range[0] + 1
                if status != 206:
                    raise HttpError(f"expected 206 for range request, got {status}")
                if len(body) != want:
                    raise HttpError(f"short range read: {len(body)} of {want} bytes")
            elif status != 200:
                raise HttpError(f"HTTP {status}")
            return body, hdrs
        except urllib.error.HTTPError as e:  # 4xx other than 408/429 are permanent
            last_err = e
            if e.code not in (408, 425, 429, 500, 502, 503, 504):
                raise HttpError(f"{url}: HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, ConnectionError, HttpError, OSError) as e:
            last_err = e
        if attempt < retries - 1:
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
    raise HttpError(f"{url} failed after {retries} attempts: {last_err}")


# --------------------------------------------------------------------------------------------------
# Remote PMTiles archive (Range requests, cached directories)
# --------------------------------------------------------------------------------------------------
class RemoteArchive:
    def __init__(self, url: str, cache_dir: Path | None, workers: int = 8):
        self.url = url
        self.workers = workers
        self.cache_dir = (cache_dir / Path(urllib.parse.urlparse(url).path).stem) if cache_dir else None
        if self.cache_dir:
            (self.cache_dir / "dirs").mkdir(parents=True, exist_ok=True)
            (self.cache_dir / "tiles").mkdir(parents=True, exist_ok=True)
        self._dir_mem: dict[tuple[int, int], list] = {}
        self._dir_lock = threading.Lock()
        self._key_locks: dict[tuple[int, int], threading.Lock] = {}
        self.etag: str | None = None
        self.last_modified: str | None = None
        self.total_bytes: int | None = None
        self.requests = 0
        self.bytes_fetched = 0
        head = self._range(0, 127)
        self.header = deserialize_header(head)
        h = self.header
        md = self._cached_blob("metadata", h["metadata_offset"], h["metadata_length"])
        if h["internal_compression"] == Compression.GZIP:
            md = gzip.decompress(md)
        self.metadata = json.loads(md)

    # -- low level -------------------------------------------------------------------------------
    def _range(self, offset: int, length: int) -> bytes:
        body, hdrs = http_get(self.url, (offset, offset + length - 1))
        with self._dir_lock:
            self.requests += 1
            self.bytes_fetched += len(body)
            etag = hdrs.get("etag")
            total = hdrs.get("content-range", "").rpartition("/")[2]
            if self.etag is None:
                self.etag, self.last_modified = etag, hdrs.get("last-modified")
                self.total_bytes = int(total) if total.isdigit() else None
            elif etag and etag != self.etag:
                raise HttpError(f"source archive changed during the build (ETag {self.etag} -> {etag})")
        return body

    def _cached_blob(self, kind: str, offset: int, length: int) -> bytes:
        p = self.cache_dir / "dirs" / f"{kind}_{offset}_{length}.bin" if self.cache_dir else None
        if p and p.exists() and p.stat().st_size == length:
            return p.read_bytes()
        b = self._range(offset, length)
        if p:
            tmp = p.with_suffix(f".{threading.get_ident()}.part")
            tmp.write_bytes(b)
            tmp.replace(p)
        return b

    def directory(self, offset: int, length: int):
        key = (offset, length)
        with self._dir_lock:
            if key in self._dir_mem:
                return self._dir_mem[key]
            key_lock = self._key_locks.setdefault(key, threading.Lock())
        with key_lock:  # single flight: each directory is fetched once even with many threads
            with self._dir_lock:
                if key in self._dir_mem:
                    return self._dir_mem[key]
            entries = deserialize_directory(self._cached_blob("dir", offset, length))
            with self._dir_lock:
                self._dir_mem[key] = entries
        return entries

    # -- tile lookup -----------------------------------------------------------------------------
    def locate(self, tile_id: int) -> tuple[int, int] | None:
        """Absolute (offset, length) of a tile's payload, or None if the archive has no such tile."""
        h = self.header
        off, ln = h["root_offset"], h["root_length"]
        for _depth in range(4):
            entries = self.directory(off, ln)
            e = find_tile(entries, tile_id)
            if e is None:
                return None
            if e.run_length == 0:
                off, ln = h["leaf_directory_offset"] + e.offset, e.length
                continue
            return h["tile_data_offset"] + e.offset, e.length
        return None

    def fetch_tiles(self, tile_ids: list[int], gap: int = 128 * 1024,
                    max_chunk: int = 8 * 1024 * 1024) -> dict[int, bytes]:
        """Fetch payloads for tile_ids. Adjacent payloads are read in one coalesced range."""
        out: dict[int, bytes] = {}
        need: dict[tuple[int, int], list[int]] = {}
        tile_cache = self.cache_dir / "tiles" if self.cache_dir else None
        # Leaf directories: resolve in parallel (each leaf is fetched once and cached).
        with cf.ThreadPoolExecutor(self.workers) as ex:
            located = list(ex.map(self.locate, tile_ids))
        for tid, loc in zip(tile_ids, located):
            if loc is None:
                continue
            if tile_cache is not None:
                p = tile_cache / f"{tid}.bin"
                if p.exists() and p.stat().st_size == loc[1]:
                    out[tid] = p.read_bytes()
                    continue
            need.setdefault(loc, []).append(tid)
        spans = sorted(need)
        groups: list[list[tuple[int, int]]] = []
        for s in spans:
            if groups:
                g = groups[-1]
                g_start, g_end = g[0][0], max(o + ln for o, ln in g)
                if s[0] - g_end <= gap and (max(g_end, s[0] + s[1]) - g_start) <= max_chunk:
                    g.append(s)
                    continue
            groups.append([s])

        def get_group(g):
            start = g[0][0]
            end = max(o + ln for o, ln in g)
            blob = self._range(start, end - start)
            res = {}
            for o, ln in g:
                data = blob[o - start:o - start + ln]
                for tid in need[(o, ln)]:
                    res[tid] = data
            return res

        if groups:
            log(f"    fetching {len(spans)} tile payloads in {len(groups)} range requests")
        with cf.ThreadPoolExecutor(self.workers) as ex:
            for res in ex.map(get_group, groups):
                for tid, data in res.items():
                    out[tid] = data
                    if tile_cache is not None:
                        p = tile_cache / f"{tid}.bin"
                        tmp = p.with_suffix(f".{threading.get_ident()}.part")
                        tmp.write_bytes(data)
                        tmp.replace(p)
        return out


# --------------------------------------------------------------------------------------------------
# Region extents
# --------------------------------------------------------------------------------------------------
_TO_WGS84 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)


def load_graph(region: str) -> tuple[dict, dict]:
    member = f"graphs/{region}/graph.json"
    extracted = INPUTS_EXTRACTED / member
    if extracted.exists():
        raw = extracted.read_bytes()
        src = {"asset": INPUTS_ASSET, "path": member, "read_from": rel(extracted)}
    elif INPUTS_ZIP.exists():
        with zipfile.ZipFile(INPUTS_ZIP) as zf:
            raw = zf.read(member)
        src = {"asset": INPUTS_ASSET, "path": member, "read_from": rel(INPUTS_ZIP) + "!" + member}
    else:
        raise SystemExit(f"graph for {region} not found: run planner/scripts/fetch_planner_assets.sh first "
                         f"(looked for {extracted} and {INPUTS_ZIP})")
    src["sha256"] = sha256_bytes(raw)
    src["asset_sha256"] = INPUTS_SHA256
    return json.loads(raw), src


def region_extent(region: str) -> dict:
    g, src = load_graph(region)
    if g.get("crs") != "EPSG:5179":
        raise SystemExit(f"{region}: unexpected graph CRS {g.get('crs')!r}")
    xs = np.array([n["x"] for n in g["nodes"]], dtype=float)
    ys = np.array([n["y"] for n in g["nodes"]], dtype=float)
    lon, lat = _TO_WGS84.transform(xs, ys)
    w, s, e, n = float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max())
    dw, dh = (e - w) * PAD_FRACTION, (n - s) * PAD_FRACTION
    padded = (w - dw, s - dh, e + dw, n + dh)
    src["node_count"] = len(g["nodes"])
    src["revision"] = g.get("revision")
    return {"graph": src, "graph_bbox": [round(v, 7) for v in (w, s, e, n)],
            "detail_bbox": [round(v, 7) for v in padded]}


# --------------------------------------------------------------------------------------------------
# Tile math (Web Mercator XYZ)
# --------------------------------------------------------------------------------------------------
MAX_LAT = 85.0511287798066


def _tx(lon: float, z: int) -> int:
    n = 1 << z
    return min(n - 1, max(0, int(math.floor((lon + 180.0) / 360.0 * n))))


def _ty(lat: float, z: int) -> int:
    n = 1 << z
    lat = max(-MAX_LAT, min(MAX_LAT, lat))
    r = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(r)) / math.pi) / 2.0 * n
    return min(n - 1, max(0, int(math.floor(y))))


def tiles_for_bbox(bbox, zmin: int, zmax: int) -> set[int]:
    w, s, e, n = bbox
    out = set()
    for z in range(zmin, zmax + 1):
        x0, x1 = _tx(w, z), _tx(e, z)
        y0, y1 = _ty(n, z), _ty(s, z)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                out.add(zxy_to_tileid(z, x, y))
    return out


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    return _tx(lon, z), _ty(lat, z)


def fit_zoom(bbox, px: int = 1024) -> int:
    """Largest integer zoom at which bbox fits in a px × px viewport (256-px tiles)."""
    w, s, e, n = bbox
    for z in range(15, -1, -1):
        width = (e - w) / 360.0 * (1 << z) * 256
        y_n = (1.0 - math.asinh(math.tan(math.radians(n))) / math.pi) / 2.0 * (1 << z) * 256
        y_s = (1.0 - math.asinh(math.tan(math.radians(s))) / math.pi) / 2.0 * (1 << z) * 256
        if width <= px and (y_s - y_n) <= px:
            return z
    return 0


def union_bbox(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


# --------------------------------------------------------------------------------------------------
# Minimal MVT reader (layer names + feature counts) for verification
# --------------------------------------------------------------------------------------------------
def _varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


def _skip(buf: bytes, pos: int, wire: int) -> int:
    if wire == 0:
        return _varint(buf, pos)[1]
    if wire == 1:
        return pos + 8
    if wire == 2:
        ln, pos = _varint(buf, pos)
        return pos + ln
    if wire == 5:
        return pos + 4
    raise ValueError(f"unsupported protobuf wire type {wire}")


def mvt_layers(tile: bytes) -> list[dict]:
    """Return [{name, features, extent, version}] for an uncompressed MVT tile."""
    layers = []
    pos = 0
    while pos < len(tile):
        key, pos = _varint(tile, pos)
        field, wire = key >> 3, key & 7
        if field == 3 and wire == 2:
            ln, pos = _varint(tile, pos)
            lb, pos = tile[pos:pos + ln], pos + ln
            info = {"name": None, "features": 0, "extent": 4096, "version": 1}
            p = 0
            while p < len(lb):
                k, p = _varint(lb, p)
                f, wt = k >> 3, k & 7
                if f == 1 and wt == 2:
                    sl, p = _varint(lb, p)
                    info["name"] = lb[p:p + sl].decode("utf-8")
                    p += sl
                elif f == 2 and wt == 2:
                    info["features"] += 1
                    p = _skip(lb, p, wt)
                elif f == 5 and wt == 0:
                    info["extent"], p = _varint(lb, p)
                elif f == 15 and wt == 0:
                    info["version"], p = _varint(lb, p)
                else:
                    p = _skip(lb, p, wt)
            layers.append(info)
        else:
            pos = _skip(tile, pos, wire)
    return layers


def decompress_tile(data: bytes, compression: Compression) -> bytes:
    if compression == Compression.GZIP:
        return gzip.decompress(data)
    if compression in (Compression.NONE, Compression.UNKNOWN):
        return data
    raise SystemExit(f"tile compression {compression} not supported by the verifier")


# --------------------------------------------------------------------------------------------------
# Building one region archive
# --------------------------------------------------------------------------------------------------
def build_region(src: RemoteArchive, region: str, out_path: Path) -> dict:
    ext = region_extent(region)
    detail = tuple(ext["detail_bbox"])
    detail_ids = tiles_for_bbox(detail, DETAIL_MINZOOM, DETAIL_MAXZOOM)
    context_ids = tiles_for_bbox(CONTEXT_BBOX, CONTEXT_MINZOOM, CONTEXT_MAXZOOM)
    ids = sorted(detail_ids | context_ids)
    log(f"  {region}: detail bbox {detail}  {len(detail_ids)} detail tiles + {len(context_ids)} context "
        f"tiles -> {len(ids)} unique")
    payloads = src.fetch_tiles(ids)
    missing = [t for t in ids if t not in payloads]
    if missing:
        raise SystemExit(f"{region}: source archive has no data for {len(missing)} tiles, e.g. "
                         f"{[tileid_to_zxy(t) for t in missing[:5]]}")

    bounds = union_bbox(detail, CONTEXT_BBOX)
    center = ((detail[0] + detail[2]) / 2.0, (detail[1] + detail[3]) / 2.0)
    center_zoom = fit_zoom(detail)
    sh = src.header
    header = {
        "tile_type": sh["tile_type"],
        "tile_compression": sh["tile_compression"],
        "min_lon_e7": int(round(bounds[0] * 1e7)),
        "min_lat_e7": int(round(bounds[1] * 1e7)),
        "max_lon_e7": int(round(bounds[2] * 1e7)),
        "max_lat_e7": int(round(bounds[3] * 1e7)),
        "center_zoom": center_zoom,
        "center_lon_e7": int(round(center[0] * 1e7)),
        "center_lat_e7": int(round(center[1] * 1e7)),
    }
    sm = src.metadata
    metadata = {
        "name": f"WildfireGuardian planner basemap — {region}",
        "description": (f"Offline extract of the Protomaps Basemap daily build {SOURCE_BUILD} "
                        f"(OpenStreetMap data): z{DETAIL_MINZOOM}-z{DETAIL_MAXZOOM} inside the padded road-graph "
                        f"box of {region}, plus {CONTEXT_NAME} z{CONTEXT_MINZOOM}-z{CONTEXT_MAXZOOM}. "
                        f"Outside the detail box there are no tiles above z{CONTEXT_MAXZOOM}."),
        "attribution": ATTRIBUTION_HTML,
        "attribution_text": ATTRIBUTION_TEXT,
        "license": "Data: ODbL-1.0 (OpenStreetMap contributors). Tile schema: Protomaps Basemap.",
        "type": sm.get("type", "baselayer"),
        "version": sm.get("version"),
        "vector_layers": sm.get("vector_layers"),
        "wfg:region_id": region,
        "wfg:detail_bounds": list(detail),
        "wfg:detail_zooms": [DETAIL_MINZOOM, DETAIL_MAXZOOM],
        "wfg:context_bounds": list(CONTEXT_BBOX),
        "wfg:context_zooms": [CONTEXT_MINZOOM, CONTEXT_MAXZOOM],
        "wfg:graph_bbox": ext["graph_bbox"],
        "wfg:pad_fraction": PAD_FRACTION,
        "wfg:source_url": src.url,
        "wfg:source_build": SOURCE_BUILD,
        "wfg:source_etag": src.etag,
        "wfg:generator": "planner/tools/build_basemap.py",
        "source_metadata": {k: v for k, v in sm.items() if k != "vector_layers"},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        w = Writer(f)
        for tid in ids:
            w.write_tile(tid, payloads[tid])
        w.finalize(header, metadata)

    per_zoom: dict[str, int] = {}
    for tid in ids:
        z = tileid_to_zxy(tid)[0]
        per_zoom[str(z)] = per_zoom.get(str(z), 0) + 1
    return {
        "region_id": region,
        "graph": ext["graph"],
        "graph_bbox": ext["graph_bbox"],
        "detail_bbox": list(detail),
        "detail_zooms": [DETAIL_MINZOOM, DETAIL_MAXZOOM],
        "header_bounds": [round(v, 7) for v in bounds],
        "center": [round(center[0], 7), round(center[1], 7), center_zoom],
        "tile_count": len(ids),
        "detail_tile_count": len(detail_ids),
        "context_tile_count": len(context_ids),
        "tiles_per_zoom": per_zoom,
        "payloads": payloads,
    }


# --------------------------------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------------------------------
def verify_archive(path: Path, region: str, expected: dict[int, bytes] | None,
                   src_header: dict | None) -> dict:
    with open(path, "rb") as f:
        gb = MmapSource(f)
        r = Reader(gb)
        h = r.header()
        md = r.metadata()
        problems = []
        if h["tile_type"] != TileType.MVT:
            problems.append(f"tile_type {h['tile_type']}")
        if src_header and (h["tile_type"], h["tile_compression"]) != (src_header["tile_type"],
                                                                     src_header["tile_compression"]):
            problems.append("tile type/compression differ from source")
        if (h["min_zoom"], h["max_zoom"]) != (0, DETAIL_MAXZOOM):
            problems.append(f"zoom range {h['min_zoom']}-{h['max_zoom']}")
        detail = md.get("wfg:detail_bounds")
        b = (h["min_lon_e7"] / 1e7, h["min_lat_e7"] / 1e7, h["max_lon_e7"] / 1e7, h["max_lat_e7"] / 1e7)
        if not detail or not (b[0] <= detail[0] and b[1] <= detail[1] and b[2] >= detail[2] and b[3] >= detail[3]):
            problems.append("header bounds do not contain the detail box")
        for key in ("attribution", "vector_layers", "version", "wfg:source_build"):
            if not md.get(key):
                problems.append(f"metadata.{key} missing")
        if "OpenStreetMap" not in md.get("attribution", ""):
            problems.append("attribution lacks OpenStreetMap")
        # Every tile round-trips byte-for-byte.
        n = 0
        mismatched = 0
        seen = set()
        for (z, x, y), data in all_tiles(gb):
            tid = zxy_to_tileid(z, x, y)
            seen.add(tid)
            n += 1
            if expected is not None and expected.get(tid) != data:
                mismatched += 1
        if expected is not None:
            if mismatched:
                problems.append(f"{mismatched} tiles differ from the source bytes")
            if seen != set(expected):
                problems.append(f"tile set differs from the requested set ({len(seen)} vs {len(expected)})")
        if n != h["addressed_tiles_count"]:
            problems.append(f"addressed_tiles_count {h['addressed_tiles_count']} != {n}")
        # Decode the z14 tile at the centre of the detail box.
        cx, cy = (detail[0] + detail[2]) / 2.0, (detail[1] + detail[3]) / 2.0
        tx, ty = lonlat_to_tile(cx, cy, 14)
        raw = r.get(14, tx, ty)
        layers = []
        if raw is None:
            problems.append(f"no z14 tile at centre {14}/{tx}/{ty}")
        else:
            layers = mvt_layers(decompress_tile(raw, h["tile_compression"]))
        names = {lyr["name"] for lyr in layers}
        for want in ("roads", "earth"):
            if want not in names:
                problems.append(f"centre z14 tile has no '{want}' layer")
        # Also decode the largest z14 tile inside the detail box (usually a town centre).
        x0, y0 = lonlat_to_tile(detail[0], detail[3], 14)
        x1, y1 = lonlat_to_tile(detail[2], detail[1], 14)
        best = None
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                d = r.get(14, x, y)
                if d is not None and (best is None or len(d) > best[2]):
                    best = (x, y, len(d), d)
        dense = None
        if best is not None:
            dl = mvt_layers(decompress_tile(best[3], h["tile_compression"]))
            dense = {"z": 14, "x": best[0], "y": best[1], "bytes": best[2],
                     "layers": [{"name": lyr["name"], "features": lyr["features"]} for lyr in dl]}
            dn = {lyr["name"] for lyr in dl}
            for want in ("roads", "buildings", "places", "water", "landuse"):
                if want not in dn:
                    problems.append(f"densest z14 tile has no '{want}' layer")
    return {
        "region_id": region,
        "ok": not problems,
        "problems": problems,
        "tiles_read": n,
        "header": {
            "tile_type": h["tile_type"].name, "tile_compression": h["tile_compression"].name,
            "min_zoom": h["min_zoom"], "max_zoom": h["max_zoom"],
            "bounds": [round(v, 7) for v in b],
            "center": [h["center_lon_e7"] / 1e7, h["center_lat_e7"] / 1e7, h["center_zoom"]],
            "addressed_tiles_count": h["addressed_tiles_count"],
            "tile_entries_count": h["tile_entries_count"],
            "tile_contents_count": h["tile_contents_count"],
            "clustered": h["clustered"],
        },
        "centre_tile": {"z": 14, "x": tx, "y": ty,
                        "layers": [{"name": lyr["name"], "features": lyr["features"]} for lyr in layers]},
        "densest_z14_tile": dense,
    }


# --------------------------------------------------------------------------------------------------
# Glyphs and sprites
# --------------------------------------------------------------------------------------------------
def _glyph_pbf_info(data: bytes) -> tuple[str | None, str | None, int]:
    """Parse a glyphs PBF: (fontstack name, range, glyph count). Raises on malformed data."""
    pos = 0
    name = rng = None
    count = 0
    while pos < len(data):
        key, pos = _varint(data, pos)
        field, wire = key >> 3, key & 7
        if field == 1 and wire == 2:
            ln, pos = _varint(data, pos)
            fs, pos = data[pos:pos + ln], pos + ln
            p = 0
            while p < len(fs):
                k, p = _varint(fs, p)
                f, wt = k >> 3, k & 7
                if f in (1, 2) and wt == 2:
                    sl, p = _varint(fs, p)
                    s = fs[p:p + sl].decode("utf-8")
                    p += sl
                    if f == 1:
                        name = s
                    else:
                        rng = s
                elif f == 3 and wt == 2:
                    count += 1
                    p = _skip(fs, p, wt)
                else:
                    p = _skip(fs, p, wt)
        else:
            pos = _skip(data, pos, wire)
    return name, rng, count


def fetch_fonts(out_dir: Path, refresh: bool, workers: int = 8) -> dict:
    jobs = [(fs, r) for fs in FONTSTACKS for r in GLYPH_RANGES]

    def one(job):
        fs, r = job
        p = out_dir / "fonts" / fs / f"{r}.pbf"
        if p.exists() and not refresh:
            data = p.read_bytes()
        else:
            url = f"{ASSETS_BASE}/fonts/{urllib.parse.quote(fs)}/{r}.pbf"
            data, _ = http_get(url)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".pbf.part")
            tmp.write_bytes(data)
            tmp.replace(p)
        _name, rng, count = _glyph_pbf_info(data)
        if rng is not None and rng != r:
            raise SystemExit(f"glyph file {p} declares range {rng}, expected {r}")
        return fs, r, len(data), sha256_bytes(data), count

    results = []
    with cf.ThreadPoolExecutor(workers) as ex:
        for res in ex.map(one, jobs):
            results.append(res)
    stacks = []
    agg = hashlib.sha256()
    total = 0
    for fs in FONTSTACKS:
        rows = sorted((x for x in results if x[0] == fs), key=lambda x: int(x[1].split("-")[0]))
        h = hashlib.sha256()
        for _fs, r, ln, sha, _c in rows:
            line = f"fonts/{fs}/{r}.pbf {sha} {ln}\n".encode()
            h.update(line)
            agg.update(line)
        b = sum(x[2] for x in rows)
        total += b
        stacks.append({
            "fontstack": fs,
            "files": len(rows),
            "bytes": b,
            "ranges_with_glyphs": sum(1 for x in rows if x[4] > 0),
            "glyphs": sum(x[4] for x in rows),
            "aggregate_sha256": h.hexdigest(),
        })
    return {
        "source_url_template": f"{ASSETS_BASE}/fonts/{{fontstack}}/{{range}}.pbf",
        "derived_from": f"text-font values in {STYLE_PACKAGE} dist (layers())",
        "license": "Noto fonts: SIL Open Font License 1.1",
        "ranges_per_stack": len(GLYPH_RANGES),
        "fontstacks": stacks,
        "total_files": sum(s["files"] for s in stacks),
        "total_bytes": total,
        "aggregate_sha256": agg.hexdigest(),
        "aggregate_sha256_definition": ("sha256 over lines 'fonts/<fontstack>/<range>.pbf <sha256> <bytes>\\n' "
                                        "in FONTSTACKS order, ranges ascending"),
    }


def fetch_sprites(out_dir: Path, refresh: bool) -> dict:
    files = []
    for flavor in SPRITE_FLAVORS:
        for suf in SPRITE_SUFFIXES:
            name = f"{flavor}{suf}"
            p = out_dir / "sprites" / "v4" / name
            if p.exists() and not refresh:
                data = p.read_bytes()
            else:
                data, _ = http_get(f"{ASSETS_BASE}/sprites/v4/{name}")
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
            if suf.endswith(".json"):
                icons = json.loads(data)
                if not isinstance(icons, dict) or not icons:
                    raise SystemExit(f"sprite index {p} is empty or not an object")
            elif data[:8] != b"\x89PNG\r\n\x1a\n":
                raise SystemExit(f"sprite sheet {p} is not a PNG")
            files.append({"path": f"sprites/v4/{name}", "bytes": len(data), "sha256": sha256_bytes(data)})
    return {"source_url_template": f"{ASSETS_BASE}/sprites/v4/{{flavor}}{{.json,.png,@2x.json,@2x.png}}",
            "flavors": SPRITE_FLAVORS, "files": files}


# --------------------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--regions", nargs="*", default=ALL_REGIONS,
                    help="regions to build (demo regions are built first and always kept)")
    ap.add_argument("--out", type=Path, default=OUT_DIR_DEFAULT)
    ap.add_argument("--cache-dir", type=Path, default=CACHE_DIR_DEFAULT,
                    help="raw directory/tile cache (gitignored); '' disables")
    ap.add_argument("--budget-mb", type=float, default=BUDGET_MB_DEFAULT,
                    help="keep non-demo regions only while the total of all region archives stays <= this")
    ap.add_argument("--skip-assets", action="store_true", help="do not fetch glyphs/sprites")
    ap.add_argument("--skip-tiles", action="store_true", help="do not (re)build region archives")
    ap.add_argument("--refresh-assets", action="store_true", help="re-download glyphs/sprites")
    ap.add_argument("--verify-only", action="store_true", help="only verify what is on disk (offline)")
    ap.add_argument("--compare-source", action="store_true",
                    help="with --verify-only: also compare every tile with the source archive (network/cache)")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args(argv)

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    sources_path = out / "SOURCES.json"
    prev = json.loads(sources_path.read_text()) if sources_path.exists() else {}
    cache_dir = Path(args.cache_dir) if str(args.cache_dir) else None

    unknown = [r for r in args.regions if r not in ALL_REGIONS]
    if unknown:
        raise SystemExit(f"unknown regions: {unknown}; known: {ALL_REGIONS}")
    order = [r for r in DEMO_REGIONS if r in args.regions] + [r for r in OTHER_REGIONS if r in args.regions]

    need_source = not args.verify_only and not args.skip_tiles
    src = None
    if need_source or (args.verify_only and args.compare_source):
        log(f"source: {SOURCE_URL}")
        src = RemoteArchive(SOURCE_URL, cache_dir, workers=args.workers)
        sh = src.header
        log(f"  tile_type={sh['tile_type'].name} tile_compression={sh['tile_compression'].name} "
            f"zooms={sh['min_zoom']}-{sh['max_zoom']} schema version={src.metadata.get('version')} "
            f"osm replication={src.metadata.get('planetiler:osm:osmosisreplicationtime')} "
            f"size={src.total_bytes} etag={src.etag}")

    regions_out: list[dict] = []
    skipped: list[dict] = []
    verification: list[dict] = []
    budget = args.budget_mb * 1e6
    if need_source:
        total = 0
        for region in order:
            final = out / f"{region}.pmtiles"
            fd, tmpname = tempfile.mkstemp(prefix=f".{region}.", suffix=".pmtiles.part", dir=out)
            os.close(fd)
            tmp = Path(tmpname)
            try:
                info = build_region(src, region, tmp)
                size = tmp.stat().st_size
                demo = region in DEMO_REGIONS
                if not demo and total + size > budget:
                    log(f"  {region}: {size / 1e6:.2f} MB would bring the total to {(total + size) / 1e6:.2f} MB "
                        f"> budget {args.budget_mb} MB -> not kept")
                    skipped.append({"region_id": region, "bytes": size,
                                    "reason": f"total would exceed {args.budget_mb} MB budget"})
                    if final.exists():
                        final.unlink()
                    continue
                v = verify_archive(tmp, region, info["payloads"], src.header)
                if not v["ok"]:
                    raise SystemExit(f"{region}: verification failed: {v['problems']}")
                os.chmod(tmp, 0o644)
                tmp.replace(final)
                total += size
                info.pop("payloads")
                info.update({"file": f"{region}.pmtiles", "bytes": size, "sha256": sha256_file(final),
                             "demo": demo})
                regions_out.append(info)
                verification.append(v)
                layer_list = ", ".join(f"{lyr['name']}({lyr['features']})" for lyr in v["centre_tile"]["layers"])
                dense = v["densest_z14_tile"] or {"layers": []}
                dense_list = ", ".join(f"{lyr['name']}({lyr['features']})" for lyr in dense["layers"])
                log(f"  {region}: {size / 1e6:.2f} MB, {info['tile_count']} tiles "
                    f"({v['header']['tile_contents_count']} unique) -> {final.name}; "
                    f"z14 centre tile layers: {layer_list}; densest z14 tile "
                    f"{dense.get('x')}/{dense.get('y')}: {dense_list}")
            finally:
                if tmp.exists():
                    tmp.unlink()
        log(f"  region archives total: {total / 1e6:.2f} MB (budget {args.budget_mb} MB); "
            f"{src.requests} range requests, {src.bytes_fetched / 1e6:.1f} MB fetched this run")
    else:
        # Verify (or keep) what is on disk.
        prev_regions = {r["region_id"]: r for r in prev.get("tiles", {}).get("regions", [])}
        for region in order:
            p = out / f"{region}.pmtiles"
            if not p.exists():
                continue
            expected = None
            if src is not None:
                ids = []
                with open(p, "rb") as f:
                    ids = [zxy_to_tileid(*zxy) for zxy, _ in all_tiles(MmapSource(f))]
                expected = src.fetch_tiles(ids)
            v = verify_archive(p, region, expected, src.header if src else None)
            verification.append(v)
            info = dict(prev_regions.get(region, {"region_id": region, "file": p.name}))
            info.update({"bytes": p.stat().st_size, "sha256": sha256_file(p)})
            regions_out.append(info)
            layer_list = ", ".join(f"{lyr['name']}({lyr['features']})" for lyr in v["centre_tile"]["layers"])
            log(f"  verify {region}: ok={v['ok']} {v['problems'] or ''} tiles={v['tiles_read']} "
                f"bounds={v['header']['bounds']} z14 centre layers: {layer_list}")
        skipped = prev.get("tiles", {}).get("skipped_regions", [])

    fonts = prev.get("fonts")
    sprites = prev.get("sprites")
    if not args.skip_assets and not args.verify_only:
        log("glyphs: " + ", ".join(FONTSTACKS))
        fonts = fetch_fonts(out, args.refresh_assets, args.workers)
        log(f"  {fonts['total_files']} files, {fonts['total_bytes'] / 1e6:.2f} MB")
        log("sprites: v4 " + ", ".join(SPRITE_FLAVORS))
        sprites = fetch_sprites(out, args.refresh_assets)
        log(f"  {len(sprites['files'])} files, {sum(f['bytes'] for f in sprites['files']) / 1e6:.2f} MB")
    elif args.verify_only and fonts:
        # Recompute the font aggregate from disk without network access.
        missing = [f"{fs}/{r}" for fs in FONTSTACKS for r in GLYPH_RANGES
                   if not (out / "fonts" / fs / f"{r}.pbf").exists()]
        log(f"  glyph files missing on disk: {len(missing)}")
        if missing:
            verification.append({"fonts_missing": missing[:20], "ok": False})

    if args.verify_only:
        bad = [v for v in verification if not v.get("ok")]
        log("verification: " + ("OK" if not bad else f"{len(bad)} problem(s)"))
        return 1 if bad else 0

    tiles_section = prev.get("tiles", {}) if args.skip_tiles else {}
    if args.skip_tiles:
        verification = prev.get("verification", [])
    if not args.skip_tiles:
        sm = src.metadata
        tiles_section = {
            "source_url": SOURCE_URL,
            "source_build": SOURCE_BUILD,
            "source_etag": src.etag,
            "source_last_modified": src.last_modified,
            "source_bytes": src.total_bytes,
            "source_header": {
                "tile_type": src.header["tile_type"].name,
                "tile_compression": src.header["tile_compression"].name,
                "min_zoom": src.header["min_zoom"], "max_zoom": src.header["max_zoom"],
            },
            "source_metadata": {k: v for k, v in sm.items() if k != "vector_layers"},
            "source_vector_layers": [lyr.get("id") for lyr in sm.get("vector_layers", [])],
            "method": ("HTTP Range requests against the source PMTiles archive; tile payloads copied byte-for-byte "
                       "(no re-encoding); PMTiles v3 written with the python 'pmtiles' writer"),
            "region_box_rule": (f"lon/lat bbox of all graph nodes (EPSG:5179 -> EPSG:4326, pyproj) padded on each "
                                f"side by {PAD_FRACTION:.0%} of its width/height"),
            "detail_zooms": [DETAIL_MINZOOM, DETAIL_MAXZOOM],
            "context": {"name": CONTEXT_NAME, "bbox": list(CONTEXT_BBOX),
                        "zooms": [CONTEXT_MINZOOM, CONTEXT_MAXZOOM]},
            "budget_mb": args.budget_mb,
            "budget_rule": "demo regions always kept; others only while the total of region archives stays <= budget",
            "regions": regions_out,
            "skipped_regions": skipped,
            "total_bytes": sum(r["bytes"] for r in regions_out),
        }
    doc = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generator": "planner/tools/build_basemap.py",
        "license_summary": {
            "tiles": "© OpenStreetMap contributors, ODbL-1.0; Protomaps Basemap schema/build (BSD-3-Clause code)",
            "fonts": "Noto Sans, SIL OFL 1.1",
            "sprites": "Protomaps basemaps-assets",
        },
        "tiles": tiles_section,
        "fonts": fonts,
        "sprites": sprites,
        "verification": verification,
    }
    sources_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    log(f"wrote {rel(sources_path)}")
    bad = [v for v in verification if not v.get("ok")]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
