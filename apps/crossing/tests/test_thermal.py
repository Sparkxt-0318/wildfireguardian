"""Tests for crossing.thermal on SYNTHETIC frames (numpy arrays of K), no camera."""
import numpy as np
import pytest

from crossing.thermal import (C_TO_K, CameraModel, column_bearing_deg, flame_at_bearing, flame_bearing_deg,
                              flame_columns, flame_mask, hot_mask, lowest_flame_row, saturated_mask, top_flame_row,
                              validate_frame)

CAM = CameraModel()


def scene(seed=0, base_c=25.0):
    rng = np.random.default_rng(seed)
    return (base_c + C_TO_K + rng.normal(0, 0.3, (192, 256))).astype(np.float32)


def test_camera_model_bearings():
    assert column_bearing_deg(127.5) == pytest.approx(0.0)
    # image edges (-0.5 and 255.5) are at +-hfov/2
    assert column_bearing_deg(255.5) == pytest.approx(28.0)
    assert column_bearing_deg(-0.5) == pytest.approx(-28.0)
    assert CAM.row_elevation_deg(-0.5) == pytest.approx(21.0)
    assert CAM.row_elevation_deg(191.5) == pytest.approx(-21.0)
    assert CAM.bearing_to_col(10.0) == pytest.approx(127.5 + CAM.fx * np.tan(np.radians(10.0)))
    assert column_bearing_deg(200) > 0                      # + right of boresight


def test_masks_and_rows():
    f = scene()
    f[100:150, 140:160] = 450 + C_TO_K                     # flame-temperature block right of centre
    f[160:170, 10:20] = 80 + C_TO_K                        # warm, not flame (e.g. exhaust)
    fm = flame_mask(f)
    assert fm.sum() == 50 * 20
    assert hot_mask(f).sum() == 50 * 20 + 100
    assert list(flame_columns(fm)) == list(range(140, 160))
    low = lowest_flame_row(fm); top = top_flame_row(fm)
    assert low[150] == 149 and top[150] == 100 and low[0] == -1 and top[0] == -1
    b = flame_bearing_deg(fm)
    assert b == pytest.approx(float(np.mean(CAM.col_bearing_deg(np.arange(140, 160)))))
    ok, n = flame_at_bearing(fm, b, tol_deg=2.0)
    assert ok and n > 0
    ok, n = flame_at_bearing(fm, -20.0, tol_deg=2.0)
    assert not ok and n == 0
    assert flame_mask(f, t_flame_c=500.0).sum() == 0     # threshold is configurable
    assert saturated_mask(f).sum() == 0


def test_single_hot_pixel_rejected():
    f = scene()
    f[50, 128] = 600 + C_TO_K
    ok, n = flame_at_bearing(flame_mask(f), 0.0, tol_deg=2.0)
    assert n == 1 and not ok


def test_smoke_only_frame_gives_no_flame_pixels():
    # SYNTHETIC smoke plume: broad warm region, max < 120 C (smoke is largely transparent in LWIR)
    f = scene(seed=3)
    yy, xx = np.mgrid[0:192, 0:256]
    f += (90.0 * np.exp(-((xx - 128) ** 2 / 2000.0 + (yy - 60) ** 2 / 800.0))).astype(np.float32)
    assert f.max() - C_TO_K < 120.0
    assert flame_mask(f).sum() == 0


def test_validate_frame_fails_closed():
    f = scene()
    assert validate_frame(f) == (True, "")
    assert not validate_frame(f[:100])[0]
    g = f.copy(); g[0, 0] = np.nan
    assert not validate_frame(g)[0]
    g = f.copy(); g[0, 0] = 2000.0
    assert not validate_frame(g)[0]
    assert not validate_frame(np.full((192, 256), 300.0))[0]


# --- FS-1: a frame that cannot show flame ABSENCE gives no flame mask -------------------------------------------
def test_flame_evidence_mask_needs_low_gain_and_verified_scale():
    from crossing import thermal as th
    t = np.full((192, 256), 300.0)
    t[10, 10] = 0.0 + 293.0
    m, why = th.flame_evidence_mask(t, "low", 300.0, scale_verified=True)
    assert m is not None and not m.any() and why == ""
    for gain in ("high", None, "", "LOW", 1):
        m, why = th.flame_evidence_mask(t, gain, 300.0, scale_verified=True)
        assert m is None and "not 'low'" in why, gain
    m, why = th.flame_evidence_mask(t, "low", 300.0, scale_verified=False)
    assert m is None and "not verified" in why
    m, why = th.flame_evidence_mask(t, "low", 548.0, scale_verified=True)      # threshold at the ceiling
    assert m is None and "ceiling" in why


def test_saturated_pixels_count_as_flame_pixels():
    from crossing import thermal as th
    t = np.full((192, 256), 300.0)
    t[50:52, 60:62] = th.TC001_LOW_GAIN_MAX_C + th.C_TO_K - 1.0                 # at the low-gain ceiling
    m, _ = th.flame_evidence_mask(t, "low", 600.0 - 100.0, scale_verified=True)  # threshold 500 C, below ceiling
    assert m.sum() == 4
    assert th.saturated_mask(t, 5.0, th.TC001_HIGH_GAIN_MAX_C).sum() == 4
