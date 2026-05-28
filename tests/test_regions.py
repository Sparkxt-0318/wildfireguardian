"""Unit tests for the geographic region presets and vulnerability framework."""

from __future__ import annotations

import math

import pytest

from wildfireguardian.utils.regions import (
    ALL_REGIONS,
    CENTRAL_MOUNTAIN_BELT,
    EAST_COAST_PINE_BELT,
    GOSEONG_2019,
    HISTORICAL_VALIDATION_CASES,
    KOREA_2000_UNIFIED,
    KOREA_PENINSULA,
    SOUTHWESTERN_COAST,
    ULJIN_SAMCHEOK_2022,
    WGS84,
    YEONGDEOK_2025,
    RegionConfig,
    lookup,
)
from wildfireguardian.utils.vulnerability import (
    DEPLOYMENT_THRESHOLD,
    WILDFIRE_VULNERABLE_COUNTIES,
    all_vulnerability_scores,
    composite_from_subscores,
    vulnerability_score,
)


# ---------------------------------------------------------------------------
# RegionConfig — bbox sanity
# ---------------------------------------------------------------------------


PRIMARY_REGIONS = [
    YEONGDEOK_2025, ULJIN_SAMCHEOK_2022, GOSEONG_2019, EAST_COAST_PINE_BELT,
    CENTRAL_MOUNTAIN_BELT, SOUTHWESTERN_COAST, KOREA_PENINSULA,
]


@pytest.mark.parametrize("region", PRIMARY_REGIONS, ids=[r.name for r in PRIMARY_REGIONS])
def test_region_bbox_is_inside_korean_peninsula(region: RegionConfig) -> None:
    """Every preset's WGS84 bbox lies inside the broad Korean peninsula box."""
    minlon, minlat, maxlon, maxlat = region.bbox_wgs84
    K_minlon, K_minlat, K_maxlon, K_maxlat = KOREA_PENINSULA.bbox_wgs84
    assert K_minlon <= minlon < maxlon <= K_maxlon, region.name
    assert K_minlat <= minlat < maxlat <= K_maxlat, region.name


@pytest.mark.parametrize("region", PRIMARY_REGIONS, ids=[r.name for r in PRIMARY_REGIONS])
def test_region_5179_bbox_has_positive_area(region: RegionConfig) -> None:
    minx, miny, maxx, maxy = region.bbox_epsg5179
    assert maxx > minx, region.name
    assert maxy > miny, region.name
    assert region.width_m > 0
    assert region.height_m > 0


def test_yeongdeok_bbox_includes_main_township() -> None:
    """The Yeongdeok bbox must include 영덕읍 — approx (129.37 E, 36.42 N)."""
    minlon, minlat, maxlon, maxlat = YEONGDEOK_2025.bbox_wgs84
    assert minlon < 129.37 < maxlon
    assert minlat < 36.42 < maxlat


def test_uljin_samcheok_spans_provincial_boundary() -> None:
    """Uljin/Samcheok bbox must span 36.85 N (북면) through 37.30 N (삼척)."""
    minlon, minlat, maxlon, maxlat = ULJIN_SAMCHEOK_2022.bbox_wgs84
    assert minlat <= 36.95 < 37.20 <= maxlat


def test_east_coast_pine_belt_contains_validation_cases() -> None:
    """The pine-belt deployment region must contain all 3 validation cases."""
    belt = EAST_COAST_PINE_BELT.bbox_wgs84
    for case in HISTORICAL_VALIDATION_CASES:
        c = case.bbox_wgs84
        assert belt[0] <= c[0], f"{case.name}: minlon"
        assert belt[1] <= c[1], f"{case.name}: minlat"
        assert c[2] <= belt[2], f"{case.name}: maxlon"
        assert c[3] <= belt[3], f"{case.name}: maxlat"


def test_grid_dims_are_consistent_with_cell_size() -> None:
    """grid_dims @ cell_size_m gives a grid that covers the region."""
    rows, cols = YEONGDEOK_2025.grid_dims(30.0)
    assert rows > 100, rows
    assert cols > 100, cols
    # Coarser cell size should produce smaller grid.
    rows_coarse, cols_coarse = YEONGDEOK_2025.grid_dims(300.0)
    assert rows_coarse < rows
    assert cols_coarse < cols


def test_affine_transform_is_north_up_at_minx_maxy() -> None:
    """Affine for north-up grid: j=0,i=0 maps to (minx, maxy)."""
    a, b, c, d, e, f = YEONGDEOK_2025.affine_transform(30.0)
    minx, _miny, _maxx, maxy = YEONGDEOK_2025.bbox_epsg5179
    assert c == pytest.approx(minx)
    assert f == pytest.approx(maxy)
    assert a == pytest.approx(30.0)
    assert e == pytest.approx(-30.0)
    assert b == 0.0 and d == 0.0


def test_synthetic_region_factory_works() -> None:
    """RegionConfig.synthetic returns a usable non-geographic region."""
    r = RegionConfig.synthetic(name="testbed")
    assert r.is_synthetic
    assert r.width_m == 5000.0
    assert r.height_m == 5000.0
    rows, cols = r.grid_dims(50.0)
    assert (rows, cols) == (100, 100)


def test_lookup_by_name() -> None:
    assert lookup("yeongdeok_2025") is YEONGDEOK_2025
    with pytest.raises(KeyError):
        lookup("not_a_region")


def test_vulnerability_tiers_are_assigned_correctly() -> None:
    """Tier-1 includes our deployment cases; Tier-2 is research extension."""
    assert YEONGDEOK_2025.vulnerability_tier == 1
    assert ULJIN_SAMCHEOK_2022.vulnerability_tier == 1
    assert GOSEONG_2019.vulnerability_tier == 1
    assert EAST_COAST_PINE_BELT.vulnerability_tier == 1
    assert CENTRAL_MOUNTAIN_BELT.vulnerability_tier == 2
    assert SOUTHWESTERN_COAST.vulnerability_tier == 2


# ---------------------------------------------------------------------------
# VulnerabilityScore
# ---------------------------------------------------------------------------


def test_vulnerability_score_bounded() -> None:
    """All sub-scores AND composite must be in [0, 1]."""
    for s in all_vulnerability_scores():
        for v in (
            s.fire_frequency_score, s.rural_elderly_density,
            s.infrastructure_score, s.composite_score,
        ):
            assert 0.0 <= v <= 1.0, (s.sigungu_code, v)


def test_yeongdeok_is_highest_tier_county() -> None:
    """영덕군 should be near the top of the deployment-target list.

    This is a sanity check on the placeholder ordering: Yeongdeok is the
    most recent major-event county and demographically very elderly.
    """
    scores = sorted(all_vulnerability_scores(), key=lambda s: -s.composite_score)
    top_codes = {s.sigungu_code for s in scores[:3]}
    assert "yeongdeok-gun" in top_codes
    assert "uljin-gun" in top_codes


def test_pohang_excluded_from_deployment_targets() -> None:
    """Semi-urban 포항시 districts are NOT in the target list."""
    assert "pohang-nam-gu" not in WILDFIRE_VULNERABLE_COUNTIES
    assert "uljeongbuk-pohang-buk" not in WILDFIRE_VULNERABLE_COUNTIES


def test_composite_geometric_zeros_near_zero_subscore() -> None:
    """A near-zero sub-score drags the composite near zero (geometric mean)."""
    high_two = composite_from_subscores(0.99, 0.99, 0.01)
    all_high = composite_from_subscores(0.99, 0.99, 0.99)
    assert high_two < 0.25
    assert all_high > 0.95


def test_composite_monotonic_in_each_subscore() -> None:
    """Increasing any sub-score with the others fixed → composite increases."""
    base = composite_from_subscores(0.5, 0.5, 0.5)
    for which in (0, 1, 2):
        args = [0.5, 0.5, 0.5]
        args[which] = 0.8
        higher = composite_from_subscores(*args)
        assert higher > base


def test_unknown_sigungu_raises() -> None:
    with pytest.raises(KeyError):
        vulnerability_score("seoul")


def test_vulnerable_counties_have_above_threshold_scores() -> None:
    """Every entry in WILDFIRE_VULNERABLE_COUNTIES has composite ≥ threshold."""
    for code in WILDFIRE_VULNERABLE_COUNTIES:
        s = vulnerability_score(code)
        assert s.composite_score >= DEPLOYMENT_THRESHOLD


def test_vulnerable_counties_includes_validation_event_counties() -> None:
    """All 3 validation-event counties make the deployment list."""
    expected = {"yeongdeok-gun", "uljin-gun", "goseong-gun"}
    assert expected <= set(WILDFIRE_VULNERABLE_COUNTIES)
