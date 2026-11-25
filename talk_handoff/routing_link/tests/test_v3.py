"""Synthetic checks of v3_physics.py (PROTOCOL_v3 sections 3-6) and the v3 attribution rule."""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import v3_physics as V  # noqa: E402


def test_thomas_matches_rothermel_table_4():
    # Rothermel (1991) Table 4: 100 ft <-> 38,800 kW/m; 50 ft <-> 13,700; 200 ft <-> 109,000
    for ft, kw in ((100, 38800), (50, 13700), (200, 109000)):
        assert abs(V.thomas_flame_length_m(kw) - ft * 0.3048) / (ft * 0.3048) < 0.01


def test_van_wagner_and_constants():
    # I_crit = [0.01 * CBH * (460 + 25.9 * FMC)]^1.5; CBH 1 m, FMC 100 -> (30.5)^1.5
    assert abs(V.van_wagner_critical_intensity_kw_m(1.0) - 30.5 ** 1.5) < 1e-9
    assert V.ROTHERMEL_CROWN_FACTOR == 3.34 and V.VAN_WAGNER_MASS_FLOW == 0.05


def test_gas_limits_and_scaling():
    assert V.gas_limits_mg_m3("co") == (480.0, 170.0, 95.0)
    acro = V.gas_limits_mg_m3("acrolein")
    assert abs(acro[0] - 0.44 * 56.06 / 24.45) < 1e-12 and len(acro) == 3
    assert V.AEGL2_PPM["hcn"] == (17.0, 10.0, 7.1) and V.AEGL2_PPM["acrolein"] == (0.44, 0.18, 0.10)
    assert abs(float(V.gas_from_co(113.0, "acrolein")) - 0.34) < 1e-12
    assert abs(float(V.gas_from_co(113.0, "hcn")) - 0.64) < 1e-12


def test_fed_rate_is_the_pipeline_law():
    q, t = np.array([0.0, 2.4, 2.5, 10.0]), np.array([20.0, 20.0, 20.0, 200.0])
    expect = np.where(q >= 2.5, q ** 1.9 / 4.2, 0.0) + np.maximum(t, 0) ** 3.61 / 4.1e8
    assert np.allclose(V.fed_rate_per_min(q, t), expect)
    # 2.5 kW/m2 alone reaches FED 0.3 in well under a minute
    assert V.fed_rate_per_min(2.5, 0.0) > 0.3


def test_trailing_sum_and_first_true():
    x = np.zeros((12, 1))
    x[3:6, 0] = 1.0
    s = V.trailing_sum(x, 3)
    assert np.all(np.isnan(s[:2, 0])) and s[5, 0] == 3.0 and s[6, 0] == 2.0
    assert V.first_true(s >= 3.0)[0] == 5.0
    assert np.isinf(V.first_true(np.zeros((4, 1), bool))[0])


def test_moving_front_geometry():
    corners = V.cell_square(0.0, 375.0, 375.0, 0, 0)         # cell [0,375] x [0,375]
    d = np.array([1.0, 0.0])                                  # spread towards +x
    s0, depth = V.entry_offset_and_depth(corners, d)
    assert s0 == 0.0 and depth == 375.0
    a, b = V.chord(corners, d, 100.0)
    assert np.allclose(sorted([a[1], b[1]]), [0.0, 375.0]) and np.allclose([a[0], b[0]], 100.0)
    # contact = onset + projected distance / rate
    t = V.contact_time_s(np.array([[0.0, 10.0], [300.0, 10.0]]), 600.0, d, s0, 0.05)
    assert np.allclose(t, [600.0, 600.0 + 300.0 / 0.05])
    # diagonal spread: depth is the projected width, the centre chord is the longest
    d2 = np.array([1.0, 1.0]) / np.sqrt(2.0)
    s0, depth = V.entry_offset_and_depth(corners, d2)
    assert abs(depth - 375.0 * np.sqrt(2.0)) < 1e-9
    a, b = V.chord(corners, d2, s0 + depth / 2)
    assert abs(np.hypot(*(b - a)) - 375.0 * np.sqrt(2.0)) < 1e-6
    assert V.chord(corners, d2, s0 - 1.0) is None


def test_seg_distance():
    d = V.seg_distance(np.array([0.0, 5.0, 20.0]), np.array([3.0, 0.0, 0.0]), (0.0, 0.0), (10.0, 0.0))
    assert np.allclose(d, [3.0, 0.0, 10.0])


def test_attribution_order():
    import v3_route as RT
    contact = np.array([5.0, 5.0, np.inf, 5.0, np.inf])
    heat = np.array([3.0, 5.0, 2.0, np.inf, np.inf])
    gas = np.array([4.0, 1.0, 1.0, 5.0, np.inf])
    assert list(RT.attribute(contact, heat, gas)) == ["heat", "gas", "gas", "flame", "none"]
