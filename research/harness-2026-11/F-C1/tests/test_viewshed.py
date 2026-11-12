import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from seebefore.viewshed import K_REFRACTION, R_EARTH, Surface, required_height, ring_points, subpoints  # noqa: E402

C = (1 - K_REFRACTION) / (2 * R_EARTH)


def flat(w=4000, h=50, res=10.0, z=0.0):
    return Surface(np.full((h, w), z, float), x0=0.0, y_top=h * res, res=res)


def test_flat_short_range_visible():
    s = flat()
    h = required_height(s, 100.0, 250.0, [2.0], [1100.0, 2100.0], [250.0, 250.0], step=10.0)
    assert np.all(h == 0.0)


def test_flat_curvature_matches_horizon_formula():
    # flat earth surface with curvature: h_req = c (D - sqrt(eye/c))^2 beyond the eye's horizon distance
    s = flat(w=4000, res=10.0)
    eye = 2.0
    for D in (15_000.0, 25_000.0, 35_000.0):
        h = required_height(s, 50.0, 250.0, [eye], [50.0 + D], [250.0], step=5.0)[0, 0]
        expected = C * (D - math.sqrt(eye / C)) ** 2
        assert h == pytest.approx(expected, rel=2e-3, abs=0.05)


def test_ridge_blocks_and_required_height_analytic():
    # 1-D ridge of height 100 m at x=2000 between observer at x=0 (eye 2) and target at x=4000; curvature off
    w, res = 600, 10.0
    z = np.zeros((20, w))
    xs = (np.arange(w) + 0.5) * res
    z[:, np.abs(xs - 2000.0) < 1.0] = 0.0
    z[:, (xs > 1990) & (xs < 2010)] = 100.0
    s = Surface(z, 0.0, 200.0, res)
    h = required_height(s, 5.0, 100.0, [2.0], [4005.0], [100.0], step=1.0, k=1.0)[0, 0]
    # line from (0, 2) over the ridge top (~2005, 100): slope (100-2)/f; worst near f ~ 0.5 -> h ~ 2*(100-2) - (0-2)
    assert h > 180.0
    assert h == pytest.approx(2 * 98 + 2, rel=0.02)
    # higher eye needs less
    h2 = required_height(s, 5.0, 100.0, [2.0, 50.0], [4005.0], [100.0], step=1.0, k=1.0)
    assert h2[1, 0] < h2[0, 0]


def test_outside_surface_is_nan():
    s = flat(w=100, res=10.0)
    h = required_height(s, 50.0, 250.0, [2.0], [5000.0], [250.0])
    assert np.isnan(h[0, 0])


def test_chunking_equals_unchunked():
    rng = np.random.default_rng(0)
    z = rng.normal(0, 30, (300, 300)).cumsum(0).cumsum(1) / 50
    s = Surface(z, 0.0, 3000.0, 10.0)
    tx, ty = rng.uniform(100, 2900, 50), rng.uniform(100, 2900, 50)
    a = required_height(s, 1500, 1500, [2.0, 10.0], tx, ty)
    b = required_height(s, 1500, 1500, [2.0, 10.0], tx, ty, max_samples_per_chunk=50)
    np.testing.assert_allclose(a, b)


def test_subpoints_and_ring():
    sp = subpoints(np.array([[1000.0, 2000.0]]))
    assert sp.shape == (1, 9, 2)
    assert np.allclose(sp[0].mean(0), [1000.0, 2000.0])
    assert np.isclose(sp[0, :, 0].max() - sp[0, :, 0].min(), 250.0)
    r = ring_points(0.0, 0.0)
    assert r.shape == (9, 2) and np.allclose(np.hypot(*r[1:].T), 250.0)
