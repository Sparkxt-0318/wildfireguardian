"""Voxel radiometer, front metrics and thermal dose units on synthetic fields."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kcf_heat import law, voxel  # noqa: E402
from kcf_heat.exposure import tdu  # noqa: E402

x = np.arange(0, 100) + 0.5
y = np.arange(-60, 60) + 0.5
z = np.arange(0, 20) + 0.5


def test_single_voxel_is_inverse_square_with_cosine():
    h = np.zeros((len(z), len(y), len(x)))
    h[2, 60, 10] = 1000.0          # voxel centre (10.5, 0.5, 2.5)
    rec = (20.5, 0.5, 2.5)          # 10 m ahead, same height, facing -x
    assert voxel.voxel_flux(h, x, y, z, rec, chi=0.3) == pytest.approx(0.3 * 1000 / (4 * math.pi * 100))
    rec2 = (20.5, 10.5, 2.5)        # off-axis: cos = 10/sqrt(200)
    r2 = 200.0
    assert voxel.voxel_flux(h, x, y, z, rec2, chi=0.3) == pytest.approx(0.3 * 1000 * (10 / math.sqrt(r2)) / (4 * math.pi * r2))
    behind = (5.5, 0.5, 2.5)        # source behind the receiver plane: no contribution
    assert voxel.voxel_flux(h, x, y, z, behind, chi=0.3) == 0.0


def test_uniform_slab_front_metrics_and_far_field_line_law():
    h = np.zeros((len(z), len(y), len(x)))
    h[0:3, 30:90, 40:50] = 100.0    # slab x 40..50, y -30..30, z 0..3; 100 kW/m3
    m = voxel.front_metrics(h, x, y, z, threshold_kw_m3=20)
    assert (m["le"], m["te"], m["depth"]) == (50.0, 40.0, 10.0)
    assert m["intensity"] == pytest.approx(100 * 3 * 10)           # kW per m of front
    assert m["centroid"] == pytest.approx(45.0)
    assert m["effective_width"] == pytest.approx(60.0)
    assert m["flame_height"] == 3.0
    # far field: voxel sum vs finite line law at the centroid (receiver at the slab mid-height)
    rec = (45.0 + 30.0, 0.0, 1.5)
    qv = voxel.voxel_flux(h, x, y, z, rec, chi=0.3)
    ql = law.line_flux_s(30.0, 0.3, m["intensity"], 30.0)
    assert qv == pytest.approx(ql, rel=0.02)


def test_tdu_counts_only_above_q0():
    assert tdu([10.0] * 10) == pytest.approx(10 * 10 ** (4 / 3))
    assert tdu([1.0, 1.5, 2.0], q0=1.42) == pytest.approx(1.5 ** (4 / 3) + 2.0 ** (4 / 3))
    assert tdu([1.4] * 600, q0=1.42) == 0.0


def test_stoll_greene_pain_pairs_are_about_92_tdu():
    # PGS 1 deel 1A Table 3-7A (Stoll & Greene 1959): flux kW/m2 -> time to pain s
    pairs = [(4.2, 13.5), (5.2, 10.1), (6.3, 7.8), (8.4, 5.5), (12.6, 2.9), (16.8, 2.2)]
    for q, t in pairs:
        assert 80 <= tdu([q] * 1, dt=t) <= 100
