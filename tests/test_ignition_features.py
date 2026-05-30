"""Tests for feature extraction and the leakage / hard-gate discipline."""

from __future__ import annotations

import numpy as np
from affine import Affine

from wildfireguardian.ignition_model.config import PipelineConfig
from wildfireguardian.ignition_model.features import FEATURE_COLUMNS, transition_table
from wildfireguardian.ignition_model.grid import FireGridSequence, _terrain


def _seq():
    H = W = 12
    transform = Affine(375.0, 0, 0.0, 0, -375.0, float(375 * H))
    burn = np.full((H, W), -1, dtype=int)
    burn[6, 6] = 0  # burning at t=0
    burn[6, 7] = 1  # newly ignites by t=1 (a positive)
    frp = np.zeros((H, W))
    frp[6, 6] = 50.0
    elev = (np.arange(W)[None, :] * 5.0).repeat(H, axis=0).astype(float)
    slope, ue, un, aspect = _terrain(elev, 375.0)
    is_burn = np.ones((H, W))
    is_burn[6, 5] = 0.0  # non-burnable neighbour -> must be gated out
    fuel_class = np.where(is_burn == 0, 80.0, 10.0)
    return FireGridSequence(
        fire_id="syn", transform=transform, shape=(H, W), cell_size_m=375.0,
        cluster_ends=[0, 1], burn_overpass=burn, cell_frp=frp, elevation=elev,
        slope_deg=slope, uphill_e=ue, uphill_n=un, aspect_deg=aspect,
        fuel_class=fuel_class, is_burnable=is_burn,
        burnable_frac_cell=is_burn.copy(), fuel_covered=np.ones((H, W), bool),
    )


def test_label_and_distance_correct():
    cfg = PipelineConfig()
    df, diag = transition_table(_seq(), 0, cfg)
    assert df is not None
    # the cell that actually ignites is a positive at exactly one cell east (375 m)
    pos = df[df["label"] == 1]
    assert len(pos) == 1
    row = pos.iloc[0]
    assert (int(row["row"]), int(row["col"])) == (6, 7)
    assert abs(row["dist_to_nearest_burning_m"] - 375.0) < 1e-6


def test_hard_gate_excludes_known_nonburnable():
    cfg = PipelineConfig()
    df, _ = transition_table(_seq(), 0, cfg)
    # the non-burnable cell (6,5) must never appear as a candidate
    assert not (((df["row"] == 6) & (df["col"] == 5)).any())


def test_capture_rate_full_when_ignition_adjacent():
    cfg = PipelineConfig()
    _, diag = transition_table(_seq(), 0, cfg)
    assert diag["capture_rate"] == 1.0
    assert diag["n_positive"] == 1


def test_features_present_and_bounded():
    cfg = PipelineConfig()
    df, _ = transition_table(_seq(), 0, cfg)
    for col in FEATURE_COLUMNS:
        assert col in df.columns
    # alignment cosines bounded
    assert df["slope_alignment"].between(-1.0001, 1.0001).all()
    assert df["directional_alignment"].between(-1.0001, 1.0001).all()
    # distance never exceeds candidate radius
    assert (df["dist_to_nearest_burning_m"] <= cfg.candidate_radius_m + 1e-6).all()


def test_no_future_leakage_in_n_burning():
    """n_burning_within_500m at t must reflect only cells burned by t."""
    cfg = PipelineConfig()
    seq = _seq()
    df, _ = transition_table(seq, 0, cfg)
    # at t=0 only (6,6) is burning; any candidate's neighbour-count <= 1
    assert df["n_burning_within_500m"].max() <= 1
