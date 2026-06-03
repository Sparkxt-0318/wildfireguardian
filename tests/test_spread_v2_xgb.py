"""Tests for the v2 data-driven spread pipeline.

The headline test is orientation safety: the prior uljin bug was a
north-up/bottom-up mask mismatch, so we prove that
:class:`RasterSampler` returns the *same* value at the *same* geographic
point regardless of how the raster is stored on disk (north-up vs south-up),
and that it reads the geographically-correct pixel.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import rasterio
from affine import Affine
from pyproj import Transformer
from rasterio.crs import CRS

from wildfireguardian.spread_v2_xgb.candidates_kernels import disk_kernel
from wildfireguardian.spread_v2_xgb.detections import cluster_overpasses
from wildfireguardian.spread_v2_xgb.era5 import (
    _days_since_rain,
    _relative_humidity,
)
from wildfireguardian.spread_v2_xgb.grid import RasterSampler

_TO_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)

# A small WGS84 footprint in the Korean east-coast pine belt.
WEST, NORTH, PIX = 129.0, 37.4, 0.1  # 4×4 grid of 0.1° pixels


def _write_northup(path) -> np.ndarray:
    """4×4 north-up raster where value = row*10 + col (row 0 = north)."""
    arr = np.array([[r * 10 + c for c in range(4)] for r in range(4)], dtype=np.float32)
    transform = Affine(PIX, 0, WEST, 0, -PIX, NORTH)
    with rasterio.open(
        path, "w", driver="GTiff", height=4, width=4, count=1,
        dtype="float32", crs=CRS.from_epsg(4326), transform=transform,
    ) as dst:
        dst.write(arr, 1)
    return arr


def _write_southup(path) -> None:
    """The same scene stored south-up (row 0 = south); must sample identically."""
    arr = np.array([[r * 10 + c for c in range(4)] for r in range(4)], dtype=np.float32)
    south = NORTH - 4 * PIX
    arr_flipped = arr[::-1, :].copy()          # flip the array …
    transform = Affine(PIX, 0, WEST, 0, +PIX, south)  # … and the transform
    with rasterio.open(
        path, "w", driver="GTiff", height=4, width=4, count=1,
        dtype="float32", crs=CRS.from_epsg(4326), transform=transform,
    ) as dst:
        dst.write(arr_flipped, 1)


def _pixel_center_5179(row: int, col: int):
    lon = WEST + (col + 0.5) * PIX
    lat = NORTH - (row + 0.5) * PIX
    return _TO_5179.transform(lon, lat)


def test_sampler_reads_geographically_correct_pixel(tmp_path):
    p = tmp_path / "nu.tif"
    arr = _write_northup(p)
    s = RasterSampler(p)
    for row in range(4):
        for col in range(4):
            x, y = _pixel_center_5179(row, col)
            got = s.sample_xy(np.array([x]), np.array([y]))[0]
            assert got == pytest.approx(arr[row, col]), (row, col, got)


def test_sampler_orientation_invariant(tmp_path):
    """North-up and south-up storage must yield identical samples at the same point."""
    pn, ps = tmp_path / "nu.tif", tmp_path / "su.tif"
    _write_northup(pn)
    _write_southup(ps)
    sn, ss = RasterSampler(pn), RasterSampler(ps)
    for row in range(4):
        for col in range(4):
            x, y = _pixel_center_5179(row, col)
            vn = sn.sample_xy(np.array([x]), np.array([y]))[0]
            vs = ss.sample_xy(np.array([x]), np.array([y]))[0]
            assert vn == pytest.approx(vs), (row, col, vn, vs)
            assert vn == pytest.approx(row * 10 + col)


def test_window_fraction_matches_bruteforce(tmp_path):
    rng = np.random.default_rng(0)
    H = W = 20
    arr = (rng.random((H, W)) > 0.5).astype(np.float32)
    transform = Affine(PIX, 0, WEST, 0, -PIX, NORTH)
    p = tmp_path / "b.tif"
    with rasterio.open(
        p, "w", driver="GTiff", height=H, width=W, count=1,
        dtype="float32", crs=CRS.from_epsg(4326), transform=transform,
    ) as dst:
        dst.write(arr, 1)
    s = RasterSampler(p)
    integral = s.integral_image(arr)
    half = 2
    # centre on pixel (10, 7)
    lon = WEST + (7 + 0.5) * PIX
    lat = NORTH - (10 + 0.5) * PIX
    x, y = _TO_5179.transform(lon, lat)
    frac = s.window_fraction(np.array([x]), np.array([y]), half, integral)[0]
    brute = arr[10 - half:10 + half + 1, 7 - half:7 + half + 1].mean()
    assert frac == pytest.approx(brute)


def test_overpass_clustering_gap_rule():
    base = pd.Timestamp("2022-03-04T03:00:00Z")
    times = pd.Series([
        base, base + pd.Timedelta(minutes=5),      # overpass 0
        base + pd.Timedelta(minutes=12),           # overpass 0 (gap 7 < 60)
        base + pd.Timedelta(hours=12),             # overpass 1 (gap 12h)
        base + pd.Timedelta(hours=12, minutes=3),  # overpass 1
        base + pd.Timedelta(hours=24),             # overpass 2
    ])
    idx = cluster_overpasses(times, gap_minutes=60.0)
    assert idx.tolist() == [0, 0, 0, 1, 1, 2]


def test_relative_humidity_saturation_and_dry():
    # T == Td → 100 % RH; large dewpoint depression → low RH.
    assert _relative_humidity(np.array([290.0]), np.array([290.0]))[0] == pytest.approx(100.0)
    dry = _relative_humidity(np.array([300.0]), np.array([280.0]))[0]
    assert 20.0 < dry < 45.0


def test_days_since_rain_counts_from_last_wet_hour():
    times = pd.date_range("2022-03-04", periods=10, freq="h").values
    tp = np.zeros(10)
    tp[2] = 5e-4   # rain at hour 2 (≥ 0.1 mm)
    dsr = _days_since_rain(times, tp)
    assert dsr[2] == pytest.approx(0.0)
    assert dsr[5] == pytest.approx(3.0 / 24.0)   # 3 h after last rain
    assert dsr[9] == pytest.approx(7.0 / 24.0)


def test_disk_kernel_radius():
    k = disk_kernel(2.0)
    assert k.shape == (5, 5)
    assert k[2, 2] == 1.0           # centre included
    assert k[0, 0] == 0.0           # corner (dist √8 > 2) excluded
    assert k[0, 2] == 1.0           # straight-up dist 2 included
    assert disk_kernel(0.3).shape == (1, 1)


def test_distance_band_edges():
    from wildfireguardian.spread_v2_xgb.features import distance_band
    got = distance_band(np.array([0.0, 375.0, 376.0, 750.0, 1500.0, 3000.0]))
    assert got.tolist() == ["0-375", "0-375", "375-750", "375-750", "750-1500", ">1500"]


def test_feature_lists_have_no_leakage_columns():
    from wildfireguardian.spread_v2_xgb.features import (
        ALL_FEATURES, META_COLUMNS, NO_WEATHER_FEATURES, WEATHER,
    )
    # dt_hours / fire_id / row / col / label must never be features (leakage).
    for leak in ("dt_hours", "fire_id", "row", "col", "label", "k"):
        assert leak not in ALL_FEATURES
        assert leak in META_COLUMNS or leak == "k"
    assert len(ALL_FEATURES) == len(set(ALL_FEATURES)) == 19
    # no-weather is exactly all-features minus the 7 ERA5 weather features
    assert set(NO_WEATHER_FEATURES) == set(ALL_FEATURES) - set(WEATHER)


def test_observed_sequence_monotone_and_candidate_labels():
    """Monotone masks + correct positive labelling, without any raster I/O."""
    from dataclasses import replace

    from wildfireguardian.spread_v2_xgb.candidates import iter_transitions
    from wildfireguardian.spread_v2_xgb.detections import build_observed_sequence
    from wildfireguardian.spread_v2_xgb.grid import Grid
    from wildfireguardian.spread_v2_xgb.layers import StaticLayers
    from wildfireguardian.utils.regions import RegionConfig

    region = RegionConfig.from_wgs84_bbox("t", (129.0, 37.0, 129.12, 37.12))
    grid = Grid(region)
    # Two overpasses 12 h apart; the second burns a cell ~1 km north (a new cell).
    df = pd.DataFrame({
        "latitude": [37.05, 37.06],
        "longitude": [129.05, 129.05],
        "frp": [10.0, 20.0],
        "timestamp": ["2022-03-04 03:00:00+00:00", "2022-03-04 15:00:00+00:00"],
    })
    df["time"] = pd.to_datetime(df["timestamp"], utc=True)
    seq = build_observed_sequence("t", df, grid)
    assert seq.n_overpasses == 2
    # monotone: burned set only grows
    assert seq.cumulative[1].sum() >= seq.cumulative[0].sum() == 1

    # Build an all-burnable static layer stub (no fuel raster needed).
    ones = np.ones(grid.shape, bool)
    z = np.zeros(grid.shape)
    static = StaticLayers(
        grid=grid, fuel_class=z.astype(np.int64), burnable_frac_cell=np.ones(grid.shape),
        burnable_frac_nearby=np.ones(grid.shape), burnable_gate=ones, in_fuel_bounds=ones,
        elevation=z, slope_deg=z, aspect_deg=z, elevation_rel=z,
    )
    trs = iter_transitions(seq, static)
    assert len(trs) == 1
    t = trs[0]
    # exactly one positive: the newly-burned cell, within 2 km of the seed
    assert int(t.labels.sum()) == 1
    # the seed cell itself is excluded from candidates (already burned)
    seed_rc = np.argwhere(seq.cumulative[0])[0]
    assert not np.any((t.rows == seed_rc[0]) & (t.cols == seed_rc[1]))


def test_lofo_holds_out_whole_fire():
    """lofo_predict must train without the held-out fire and cover every row once."""
    from wildfireguardian.spread_v2_xgb.model import lofo_predict

    rng = np.random.default_rng(0)
    parts = []
    for fid, mu in [("A", 0.0), ("B", 0.5), ("C", -0.3)]:
        n = 400
        x = rng.normal(mu, 1, n)
        y = (rng.random(n) < 1 / (1 + np.exp(-(x - 1.0)))).astype(int)
        parts.append(pd.DataFrame({
            "fire_id": fid, "label": y, "dist_to_nearest_burning": rng.uniform(375, 2000, n),
            "row": rng.integers(0, 50, n), "col": rng.integers(0, 50, n),
            "k": rng.integers(0, 5, n),
            "f1": x, "f2": rng.normal(0, 1, n),
        }))
    df = pd.concat(parts, ignore_index=True)
    oof, models = lofo_predict(df, ["f1", "f2", "dist_to_nearest_burning"], seed=1)
    assert len(oof) == len(df)                       # every row predicted once
    assert set(models) == {"A", "B", "C"}            # one model per held-out fire
    assert oof["oof_pred"].between(0, 1).all()
    assert set(oof["band"].unique()) <= {"0-375", "375-750", "750-1500", ">1500"}
