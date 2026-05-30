"""Tests for grid construction, terrain derivation, and the burn sequence."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from affine import Affine

from wildfireguardian.ignition_model.grid import (
    FireGridSequence,
    _snap_grid,
    _terrain,
)


def test_snap_grid_aligns_to_lattice():
    transform, H, W = _snap_grid(100.0, 100.0, 1000.0, 1000.0, cell=375.0, buffer=0.0)
    # origin snapped to a multiple of 375
    assert transform.c % 375 == 0
    assert transform.f % 375 == 0
    assert transform.a == 375 and transform.e == -375
    assert H >= 2 and W >= 2


def test_terrain_on_east_facing_ramp():
    # elevation rises 10 m per column (towards the east)
    elev = (np.arange(8)[None, :] * 10.0).repeat(8, axis=0).astype(float)
    slope, ue, un, aspect = _terrain(elev, cell=375.0)
    # uphill points east (+e, ~0 n)
    assert np.allclose(ue, 1.0, atol=1e-6)
    assert np.allclose(un, 0.0, atol=1e-6)
    expected_slope = np.degrees(np.arctan(10.0 / 375.0))
    assert np.allclose(slope, expected_slope, atol=1e-3)


def _synthetic_seq(n_overpass=3):
    H = W = 10
    transform = Affine(375.0, 0, 0.0, 0, -375.0, 3750.0)
    burn = np.full((H, W), -1, dtype=int)
    burn[5, 5] = 0
    burn[5, 6] = 1
    burn[5, 7] = 2
    frp = np.zeros((H, W))
    frp[5, 5] = 100.0
    elev = (np.arange(W)[None, :] * 10.0).repeat(H, axis=0).astype(float)
    slope, ue, un, aspect = _terrain(elev, 375.0)
    fuel_class = np.full((H, W), 10.0)
    is_burn = np.ones((H, W))
    is_burn[5, 8] = 0.0  # a known non-burnable cell
    return FireGridSequence(
        fire_id="synthetic",
        transform=transform,
        shape=(H, W),
        cell_size_m=375.0,
        cluster_ends=list(pd.date_range("2025-03-22", periods=n_overpass, freq="6h")),
        burn_overpass=burn,
        cell_frp=frp,
        elevation=elev,
        slope_deg=slope,
        uphill_e=ue,
        uphill_n=un,
        aspect_deg=aspect,
        fuel_class=fuel_class,
        is_burnable=is_burn,
        burnable_frac_cell=is_burn.copy(),
        fuel_covered=np.ones((H, W), dtype=bool),
    )


def test_burned_mask_monotone_and_frp():
    seq = _synthetic_seq()
    a0 = seq.burned_mask(0).sum()
    a1 = seq.burned_mask(1).sum()
    a2 = seq.burned_mask(2).sum()
    assert a0 == 1 and a1 == 2 and a2 == 3
    assert a0 <= a1 <= a2
    # frp present only for cells burned by t
    assert seq.frp_at(0)[5, 5] == 100.0
    assert seq.frp_at(0)[5, 6] == 0.0


def test_seq_npz_roundtrip(tmp_path):
    seq = _synthetic_seq()
    p = tmp_path / "s.npz"
    seq.save_npz(p)
    back = FireGridSequence.load_npz(p)
    assert back.shape == seq.shape
    assert np.array_equal(back.burn_overpass, seq.burn_overpass)
    assert back.transform.c == seq.transform.c
    assert np.allclose(back.elevation, seq.elevation)
