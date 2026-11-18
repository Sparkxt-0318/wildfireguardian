"""GeoTIFF reading (compressions, predictors, byte order) and the raster → 375 m road-cell rule."""
from __future__ import annotations

import io
import struct
import zlib
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path

import numpy as np
import pytest

from wfg_roadlayer import fireinput, geotiff

A = (np.arange(53 * 70, dtype=np.float32).reshape(53, 70) / 7).astype(np.float32)
A[3, 4] = np.inf


@pytest.mark.parametrize("comp", ["tiff_lzw", "tiff_adobe_deflate", "packbits", "raw"])
def test_pillow_compressions(tmp_path, comp):
    Image = pytest.importorskip("PIL.Image")
    p = tmp_path / "a.tif"
    Image.fromarray(A, mode="F").save(p, compression=comp)
    r = geotiff.read(p, require_georef=False)
    assert np.array_equal(r.data, A.astype(float))


def test_lzw_code_width_changes(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    b = np.random.default_rng(1).integers(0, 50, (400, 300)).astype(np.float32)
    p = tmp_path / "b.tif"
    Image.fromarray(b, mode="F").save(p, compression="tiff_lzw")
    assert np.array_equal(geotiff.read(p, require_georef=False).data, b)


def test_floating_point_predictor(tmp_path):
    """Predictor 3 (GDAL's default for compressed floats), encoded by hand from the TIFF Technical Note 3 rule."""
    p = tmp_path / "p.tif"
    geotiff.write(p, A, (1.0, 0, 0.0, 0, -1.0, 0.0), 5179, dtype="float32", deflate=True)
    buf = bytearray(p.read_bytes())
    t = geotiff._Reader(bytes(buf)).tags()
    offs, cnts = [], []
    for r0 in range(0, 53, 16):
        blk = A[r0:r0 + 16]
        rows, cols = blk.shape
        be = blk.astype(">f4").view(np.uint8).reshape(rows, cols, 4).transpose(0, 2, 1).reshape(rows, cols * 4)
        d = np.diff(be.astype(np.int16), axis=1, prepend=0).astype(np.uint8)
        d[:, 0] = be[:, 0]
        s = zlib.compress(d.tobytes())
        offs.append(len(buf)); cnts.append(len(s)); buf += s
    ifd = struct.unpack("<I", buf[4:8])[0]
    n = struct.unpack("<H", buf[ifd:ifd + 2])[0]
    for k in range(n):
        q = ifd + 2 + 12 * k
        tag, typ, cnt, val = struct.unpack("<HHII", buf[q:q + 12])
        if tag in (273, 279):
            buf[val:val + 4 * cnt] = struct.pack("<" + "I" * cnt, *(offs if tag == 273 else cnts))
        if tag == 284:  # replace PlanarConfiguration by Predictor = 3 (tags stay sorted)
            buf[q:q + 12] = struct.pack("<HHI", 317, 3, 1) + struct.pack("<H", 3) + b"\0\0"
    p.write_bytes(bytes(buf))
    r = geotiff.read(p)
    assert r.info["predictor"] == 3 and np.array_equal(r.data, A.astype(float))


def test_big_endian_tiled_geotiff(tmp_path):
    tifffile = pytest.importorskip("tifffile")
    p = tmp_path / "be.tif"
    tifffile.imwrite(p, A.astype(np.float64), byteorder=">", compression="zlib", tile=(32, 48),
                     extratags=[(33550, 12, 3, (375.0, 375.0, 0.0), False), (33922, 12, 6, (0, 0, 0, 1000.0, 2000.0, 0), False),
                                (34735, 3, 8, (1, 1, 0, 1, 3072, 0, 1, 5186), False), (42113, 2, 0, "-9999", False)])
    r = geotiff.read(p)
    assert r.epsg == 5186 and r.nodata == -9999 and r.affine == (375.0, 0.0, 1000.0, 0.0, -375.0, 2000.0)
    assert np.array_equal(r.data, A.astype(float))


def test_writer_metadata_roundtrip(tmp_path):
    p = tmp_path / "w.tif"
    geotiff.write(p, A, (375.0, 0, 1000.0, 0, -375.0, 2000.0), 5179, nodata=-9999, metadata={"WFG_HORIZON_MIN": "480", "X": "a<b"})
    r = geotiff.read(p)
    assert r.metadata == {"WFG_HORIZON_MIN": "480", "X": "a<b"} and r.nodata == -9999 and r.epsg == 5179


class Road:
    """Two road cells on a 375 m grid at the origin."""
    x0, y0, res, W, H = F(0), F(0), F(375), 2, 1
    road_cells = [0, 1]

    def cell_rect(self, c):
        return (375.0 * c, 375.0 * (c + 1), 0.0, 375.0)


def _fine(tmp_path, values, nodata=float("nan"), **md):
    p = tmp_path / "fine.tif"
    meta = {"WFG_HORIZON_MIN": "60"}
    meta.update(md)
    geotiff.write(p, values, (75.0, 0, 0.0, 0, -75.0, 375.0), 5179, nodata=nodata, metadata=meta)
    return fireinput.load_geotiff(p, Road(), issue_utc=datetime(2025, 3, 25, tzinfo=timezone.utc), horizon_min=None)


def test_cell_takes_earliest_pixel_and_rounds_down(tmp_path):
    v = np.full((5, 10), np.inf)
    v[2, 2] = 30.0          # cell 0: one pixel at 30 min
    v[4, 9] = 10.0 + 1 / 120  # cell 1: 10 min 0.5 s -> 600 s (rounded down)
    v[0, 7] = 45.0
    f = _fine(tmp_path, v)
    assert f.arrival_s == {0: 1800, 1: 600} and f.uncovered == []


def test_values_beyond_horizon_and_burnt(tmp_path):
    v = np.full((5, 10), 61.0)   # beyond the 60 min horizon: not reached
    v[1, 6] = -5.0               # burnt before the issue time: closed from 0
    f = _fine(tmp_path, v)
    assert f.arrival_s == {1: 0}


def test_nodata_pixel_makes_cell_uncovered_unless_burnt(tmp_path):
    v = np.full((5, 10), 20.0)
    v[0, 0] = -9999.0
    v[0, 5] = -9999.0
    v[1, 6] = 0.0
    f = _fine(tmp_path, v, nodata=-9999.0)
    assert f.uncovered == [0] and f.arrival_s == {1: 0}


def test_raster_smaller_than_roads_is_uncovered(tmp_path):
    p = tmp_path / "small.tif"
    geotiff.write(p, np.full((5, 5), 20.0), (75.0, 0, 0.0, 0, -75.0, 375.0), 5179, metadata={"WFG_HORIZON_MIN": "60"})
    f = fireinput.load_geotiff(p, Road(), issue_utc=datetime(2025, 3, 25, tzinfo=timezone.utc), horizon_min=None)
    assert f.uncovered == [1] and f.arrival_s == {0: 1200}


def test_declared_not_reached_value(tmp_path):
    v = np.full((5, 10), -1.0)
    v[2, 7] = 15.0
    f = _fine(tmp_path, v, WFG_NOT_REACHED="-1")
    assert f.arrival_s == {1: 900}


def test_other_crs_via_pyproj(tmp_path):
    pyproj = pytest.importorskip("pyproj")
    tr = pyproj.Transformer.from_crs("EPSG:5179", "EPSG:5186", always_xy=True)
    # a 5186 raster around two 5179 road cells of the 영덕 grid
    x, y = tr.transform(1150000.0, 1820000.0)
    p = tmp_path / "k.tif"
    v = np.full((40, 40), 25.0)
    geotiff.write(p, v, (50.0, 0, x - 1000, 0, -50.0, y + 1000), 5186, metadata={"WFG_HORIZON_MIN": "60"})

    class R2(Road):
        road_cells = [0]

        def cell_rect(self, c):
            return (1150000.0, 1150375.0, 1820000.0, 1820375.0)
    f = fireinput.load_geotiff(p, R2(), issue_utc=datetime(2025, 3, 25, tzinfo=timezone.utc), horizon_min=None)
    assert f.arrival_s == {0: 1500} and "pyproj" in f.info["resampling"]
