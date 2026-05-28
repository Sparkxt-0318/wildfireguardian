"""Tests for the LFMC×wind decomposition (Session 4 Deliverable 2)."""

from __future__ import annotations

import pytest

from wildfireguardian.spread_model.demo_lfmc_wind_decomposition import (
    compute_decomposition,
)


def test_decomposition_corners_ordered() -> None:
    """R should increase A < B < C < D (benign < drought < wind < combined)."""
    d = compute_decomposition()
    r = d["rates_m_min"]
    assert r["A"] < r["B"] < r["C"] < r["D"]


def test_wind_dominates_moisture() -> None:
    """Honest framing check: wind-alone amplification >> moisture-alone."""
    d = compute_decomposition()
    assert d["wind_alone_CA"] > 5.0 * d["moisture_alone_BA"]


def test_coupling_is_multiplicative() -> None:
    """The interaction ratio (D/A) / ((B/A)(C/A)) must be ~1.0.

    This confirms the structural multiplicativity of the Rothermel equation
    (η_M and (1+φ_w) are separate multiplicative factors).
    """
    d = compute_decomposition()
    assert d["interaction_ratio"] == pytest.approx(1.0, abs=0.01)


def test_combined_ratio_matches_product() -> None:
    d = compute_decomposition()
    assert d["combined_DA"] == pytest.approx(d["product_of_alones"], rel=0.01)


def test_combined_ratio_is_about_18x() -> None:
    """The headline number should be ~18× (locked for the writeup)."""
    d = compute_decomposition()
    assert 16.0 < d["combined_DA"] < 21.0
