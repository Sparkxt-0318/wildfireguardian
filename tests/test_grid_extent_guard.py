"""The simulation-canvas guard: clipping must be loud, clearance must be visible.

Round-3 PHASE 1. These tests exist because the previous behaviour — a fire
silently truncated at the grid edge, and a canvas that changed whenever a
git-ignored manifest was regenerated — produced no signal at all.
"""

from __future__ import annotations

import warnings

import numpy as np
import pytest

from wildfireguardian.spread_v2.extent import (
    GridBoundaryError,
    RoutingClearanceWarning,
    assert_envelope_within_grid,
    boundary_contact,
    check_routing_clearance,
    resolve_simulation_bbox,
)
from wildfireguardian.spread_v2.grid import CoarseGrid, build_grid


def _grid(nrows=20, ncols=20, cell=500.0):
    return CoarseGrid(minx=0.0, miny=0.0, maxx=ncols * cell, maxy=nrows * cell,
                      cell_size_m=cell, nrows=nrows, ncols=ncols)


def _interior_blob(nrows=20, ncols=20, p=0.9):
    a = np.zeros((nrows, ncols), float)
    a[8:12, 8:12] = p
    return a


def test_interior_fire_does_not_trip_the_guard():
    surfaces = [_interior_blob()]
    reports = assert_envelope_within_grid(surfaces, grid=_grid())
    assert reports[0]["reached"] is False
    assert max(reports[0]["max_p_per_edge"].values()) == 0.0


@pytest.mark.parametrize(
    "sl, edge",
    [((slice(0, 1), slice(None)), "north"),
     ((slice(-1, None), slice(None)), "south"),
     ((slice(None), slice(0, 1)), "west"),
     ((slice(None), slice(-1, None)), "east")],
)
def test_each_edge_is_detected(sl, edge):
    a = _interior_blob()
    a[sl] = 0.9
    r = boundary_contact(a)
    assert r["reached"] is True
    assert edge in r["edges_reached"]


def test_boundary_contact_raises_and_names_the_fix():
    a = _interior_blob()
    a[-1, :] = 0.9                       # fire runs off the southern edge
    with pytest.raises(GridBoundaryError) as exc:
        assert_envelope_within_grid([a], grid=_grid())
    msg = str(exc.value)
    assert "enlarge simulation_bbox" in msg
    assert "south" in msg


def test_threshold_is_respected():
    """A boundary value below p_threshold is not contact."""
    a = _interior_blob()
    a[-1, :] = 0.1                       # below the 0.3 default
    assert boundary_contact(a)["reached"] is False
    assert boundary_contact(a, p_threshold=0.05)["reached"] is True


def test_routing_clearance_warns_when_tight_and_is_silent_when_ample():
    hg = _grid(nrows=100, ncols=100)     # 50 km x 50 km
    ample = (20_000.0, 20_000.0, 30_000.0, 30_000.0)   # 20 km margins
    with warnings.catch_warnings():
        warnings.simplefilter("error")   # any warning would fail the test
        rep = check_routing_clearance(ample, hg)
    assert rep["ok"] is True
    assert rep["sides_below_clearance"] == []

    tight = (1_000.0, 20_000.0, 30_000.0, 30_000.0)    # 1 km on the west
    with pytest.warns(RoutingClearanceWarning, match="west"):
        rep = check_routing_clearance(tight, hg)
    assert rep["ok"] is False
    assert "west" in rep["sides_below_clearance"]


def test_routing_extent_outside_the_grid_is_reported_as_such():
    hg = _grid(nrows=100, ncols=100)
    outside = (-5_000.0, 20_000.0, 30_000.0, 30_000.0)
    with pytest.warns(RoutingClearanceWarning):
        rep = check_routing_clearance(outside, hg)
    assert "west" in rep["outside_grid"]


def test_simulation_bbox_resolves_from_config_not_from_the_fire_manifest():
    """The canvas must come from config, which is the whole point of the change."""
    bbox, prov = resolve_simulation_bbox(fallback=(0.0, 0.0, 1.0, 1.0))
    assert "config" in prov
    assert bbox == (128.97, 36.10, 129.77, 36.90)


def test_config_canvas_reproduces_the_committed_hazard_grid():
    """The committed routing_demo.npz grid is 181x147; config must regenerate it.

    This is the regression test for docs/grid_extent.md: when fire_manifest.json
    was regenerated on 2026-07-23 the canvas silently became 125x119.
    """
    bbox, _ = resolve_simulation_bbox()
    g = build_grid(bbox, cell_size_m=500.0)
    assert (g.nrows, g.ncols) == (181, 147)
    assert g.minx == pytest.approx(1130969.9509370383, abs=1e-6)
    assert g.miny == pytest.approx(1789870.4640061273, abs=1e-6)
    assert g.maxx == pytest.approx(1204469.9509370383, abs=1e-6)
    assert g.maxy == pytest.approx(1880370.4640061273, abs=1e-6)
