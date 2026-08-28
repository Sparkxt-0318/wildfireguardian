"""Tests for the WUI (village-edge) building classification (Session 8 Phase 2).

The operational definition under test is the building-level parameterisation
of Radeloff et al. (2005): *interface* = centroid NOT inside wildland
vegetation but within D metres of it; *intermix* = centroid inside it.
"""

from __future__ import annotations

import numpy as np
import pytest

shapely = pytest.importorskip("shapely")
from shapely.geometry import Polygon  # noqa: E402

from wildfireguardian.buildings.wui import (  # noqa: E402
    WUI_INTERFACE_DISTANCE_SWEEP_M,
    interface_mask,
    wui_distances,
)


def _square(x0, y0, size=1000.0):
    return Polygon([(x0, y0), (x0 + size, y0), (x0 + size, y0 + size),
                    (x0, y0 + size)])


def test_wui_distances_inside_near_far():
    veg = [_square(0.0, 0.0, 1000.0)]
    xy = np.array([
        [500.0, 500.0],     # inside            -> intermix, dist 0
        [1050.0, 500.0],    # 50 m east of edge -> interface at D>=50
        [1500.0, 500.0],    # 500 m east        -> outside any swept D
    ])
    cls = wui_distances(xy, veg)
    assert cls["inside"].tolist() == [True, False, False]
    assert cls["dist_m"][0] == 0.0
    assert cls["dist_m"][1] == pytest.approx(50.0)
    assert cls["dist_m"][2] == pytest.approx(500.0)


def test_interface_mask_excludes_intermix_and_far():
    veg = [_square(0.0, 0.0, 1000.0)]
    xy = np.array([[500.0, 500.0], [1050.0, 500.0], [1500.0, 500.0]])
    cls = wui_distances(xy, veg)
    assert interface_mask(cls, 100.0).tolist() == [False, True, False]
    # monotone in D: a larger threshold can only add buildings
    m50 = interface_mask(cls, 50.0)
    m200 = interface_mask(cls, 200.0)
    assert np.all(m50 <= m200)


def test_interface_counts_monotone_over_the_swept_thresholds():
    rng = np.random.default_rng(20250603)
    veg = [_square(0.0, 0.0, 2000.0)]
    xy = rng.uniform(-1000.0, 4000.0, size=(200, 2))
    cls = wui_distances(xy, veg)
    counts = [int(interface_mask(cls, d).sum())
              for d in sorted(WUI_INTERFACE_DISTANCE_SWEEP_M)]
    assert counts == sorted(counts)


def test_no_vegetation_is_an_error_not_a_guess():
    with pytest.raises(ValueError):
        wui_distances(np.array([[0.0, 0.0]]), [])
