"""Guards for the multi-region 459-series extension (Round-3 PHASE 5, 2-3 + 4).

The named risks in adding regions to a committed series are:

1. the second run silently REDEFINES the origin rule or the classification, so
   the new rows are not the same quantity as the Yeongdeok row they sit beside;
2. a Yeongdeok artifact gets touched;
3. a bucket count is quoted without the covariate that explains it;
4. "no depot in this bbox" degrades into "zero dispatches".

Each is pinned below. Tests that need the generated artifacts skip cleanly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from wildfireguardian.routing.future_front import RoadNetwork  # noqa: E402
from wildfireguardian.routing.hazard import HazardSequence  # noqa: E402
from wildfireguardian.spread_v2.grid import CoarseGrid  # noqa: E402

UISEONG = REPO / "data/processed/real_roads_real_hazard_uiseong_andong_2025.json"
ULJIN = REPO / "data/processed/real_roads_real_hazard_uljin_samcheok_2022.json"
COMPARISON = REPO / "data/processed/multi_region_comparison.json"
YEONGDEOK_COMMITTED = REPO / "data/processed/real_roads_real_hazard.json"

ORIGINAL_CATEGORIES = ("naive_into_FA_safe", "no_safe_route", "both_safe",
                       "both_enter", "naive_unreachable", "unclassified")


def _needs(*paths):
    for p in paths:
        if not p.exists():
            pytest.skip(f"{p.name} absent — run scripts/run_multi_region_routing.py")


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1. The two runners must mean the same thing by "origin" and by each bucket
# ---------------------------------------------------------------------------


#: Budget at which the toy below populates three buckets at once. Not 600: on a
#: 60 km chain every origin is either fine or hopeless at 600 minutes, and a pin
#: that agrees only because one bucket holds everything proves nothing.
TOY_BUDGET_MIN = 900.0


def _toy():
    """A 1-D chain with a hazard front sweeping in from the west.

    121 nodes so a stride-18 scan yields six origins rather than one, and two
    shelters (one at each end) so the fire-blind router has a wrong choice
    available to make.
    """
    ncols, cell = 121, 500.0
    grid = CoarseGrid(minx=0.0, miny=0.0, maxx=ncols * cell, maxy=cell,
                      cell_size_m=cell, nrows=1, ncols=ncols)
    X, _ = grid.center_grids()
    surfaces = [np.where(X <= fx, 1.0, 0.0) for fx in (8000.0, 25000.0, 45000.0)]
    hazard = HazardSequence(grid=grid, times_min=np.array([0.0, 300.0, 600.0]),
                            surfaces=surfaces)
    haz = np.stack(surfaces).astype(np.float32)

    g = nx.Graph()
    for i in range(ncols):
        g.add_node(i, x=(i + 0.5) * cell, y=0.5 * cell)
        if i:
            g.add_edge(i - 1, i, length_m=cell, time_min=(cell / 0.7) / 60.0)
    net = RoadNetwork(graph=g, shelters={0, ncols - 1})
    extent = (grid.minx, grid.miny, grid.maxx, grid.maxy, cell)
    return net, hazard, haz, extent


def test_origin_rule_is_identical_to_the_yeongdeok_runner():
    """The stride/p_cut/reach-band rule must not have drifted between scripts."""
    from run_multi_region_routing import candidate_origins as mr_origins
    from run_real_roads_real_hazard_slope import candidate_origins as yd_origins

    net, hazard, haz, extent = _toy()
    mr_cand, mr_ign, _band = mr_origins(net, hazard, haz, extent, 0.5)
    yd_cand, yd_ign = yd_origins(net, hazard, haz, extent, 0.5)
    assert mr_cand == yd_cand, "the two runners disagree on which nodes are origins"
    assert mr_ign == pytest.approx(yd_ign)
    assert len(mr_cand) >= 5, "a one-origin scan is not a pin"
    assert mr_cand == [18, 36, 54, 72, 90, 108], (
        "stride 18 over the sorted node list, minus nodes already at/above p_cut")


def test_origin_rule_reads_the_same_stride_constant():
    import run_multi_region_routing as mr
    import run_real_roads_real_hazard_slope as yd

    assert mr.REAL_OSM_SCAN_STRIDE == yd.REAL_OSM_SCAN_STRIDE == 18


def test_classification_is_identical_to_the_yeongdeok_runner():
    from run_multi_region_routing import classify as mr_classify
    from run_real_roads_real_hazard_slope import classify as yd_classify

    from run_multi_region_routing import candidate_origins

    net, hazard, haz, extent = _toy()
    cand, _ign, _band = candidate_origins(net, hazard, haz, extent, 0.5)
    mr_counts, mr_classes = mr_classify(net, cand, hazard, 0.5, TOY_BUDGET_MIN, 10.0)
    yd_counts = yd_classify(net, cand, hazard, 0.5, TOY_BUDGET_MIN, 10.0)
    assert mr_counts == yd_counts
    assert sum(mr_counts.values()) == len(cand), "classification must partition"
    assert sum(len(v) for v in mr_classes.values()) == len(cand)


def test_the_toy_case_is_not_degenerate():
    """A pin that agrees only because every origin lands in one bucket is worthless."""
    from run_multi_region_routing import candidate_origins, classify

    net, hazard, haz, extent = _toy()
    cand, _ign, _band = candidate_origins(net, hazard, haz, extent, 0.5)
    counts, _ = classify(net, cand, hazard, 0.5, TOY_BUDGET_MIN, 10.0)
    populated = {k for k, v in counts.items() if v}
    assert len(cand) >= 5
    assert populated >= {"both_safe", "naive_into_FA_safe", "no_safe_route"}, (
        f"toy case must exercise all three reported buckets; got {counts}")


# ---------------------------------------------------------------------------
# 2. Yeongdeok must be untouchable
# ---------------------------------------------------------------------------


def test_yeongdeok_is_not_a_runnable_region():
    import run_multi_region_routing as mr

    assert "yeongdeok_2025" not in mr.RUNNABLE_REGIONS


def test_runner_refuses_yeongdeok_on_the_command_line(monkeypatch, capsys):
    import run_multi_region_routing as mr

    monkeypatch.setattr(sys, "argv",
                        ["run_multi_region_routing.py", "--regions", "yeongdeok_2025"])
    assert mr.main() == 2
    assert "yeongdeok" in capsys.readouterr().err.lower()


def test_the_committed_yeongdeok_artifacts_are_protected():
    import run_multi_region_routing as mr

    assert "data/processed/real_roads_real_hazard.json" in mr.PROTECTED
    assert "data/processed/real_roads_real_hazard_slope_60.json" in mr.PROTECTED
    assert "data/processed/routing_demo.npz" in mr.PROTECTED
    for rel in mr.PROTECTED:
        assert (REPO / rel).exists(), f"protected artifact missing: {rel}"


def test_a_changed_protected_artifact_exits_4(monkeypatch, tmp_path, capsys):
    """The guard, not the intent, is what stops a Yeongdeok artifact moving."""
    import run_multi_region_routing as mr

    calls = {"n": 0}
    real = mr.protected_digests

    def drifting():
        calls["n"] += 1
        d = real()
        if calls["n"] > 1:                      # pretend it changed mid-run
            k = "data/processed/real_roads_real_hazard.json"
            d[k] = "0" * 64
        return d

    monkeypatch.setattr(mr, "protected_digests", drifting)
    monkeypatch.setattr(sys, "argv", ["run_multi_region_routing.py",
                                      "--regions", "uiseong_andong_2025",
                                      "--limit-origins", "1",
                                      "--out-dir", str(tmp_path)])
    assert mr.main() == 4
    assert "PROTECTED artifact changed" in capsys.readouterr().err


def test_committed_yeongdeok_counts_are_unmoved():
    """The committed 459 = 438 + 18 + 3 must still be exactly that."""
    _needs(YEONGDEOK_COMMITTED)
    c = _load(YEONGDEOK_COMMITTED)["counts"]
    assert (c["both_safe"], c["naive_into_FA_safe"], c["no_safe_route"]) == (438, 18, 3)
    assert _load(YEONGDEOK_COMMITTED)["n_origins_scanned"] == 459


# ---------------------------------------------------------------------------
# 3. The generated artifacts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", [UISEONG, ULJIN])
def test_every_arm_partitions_its_origins(path):
    _needs(path)
    d = _load(path)
    for name, arm in d["arms"].items():
        assert sum(arm["counts"].values()) == arm["n_origins_scanned"], name
        assert set(arm["counts"]) == set(ORIGINAL_CATEGORIES) | {"fa_exceeds_budget"}
        assert arm["counts"]["unclassified"] == 0, (
            f"{name}: an origin fell through every branch")


@pytest.mark.parametrize("path", [UISEONG, ULJIN])
def test_flat_digraph_regression_passed(path):
    _needs(path)
    d = _load(path)
    assert d["digraph_regression"]["identical"] is True
    assert (d["arms"]["flat_undirected_control"]["counts"]
            == d["arms"]["flat_digraph_regression"]["counts"])


@pytest.mark.parametrize("path", [UISEONG, ULJIN])
def test_parameters_were_not_varied_per_region(path):
    _needs(path)
    p = _load(path)["parameters"]
    assert p["slope_sampling_m"] == 60.0 and p["is_canonical_sampling"] is True
    assert p["max_abs_slope"] == 0.60
    assert p["p_cut"] == 0.5
    assert p["time_budget_min"] == 600.0
    assert p["time_step_min"] == 10.0
    assert p["origin_scan_stride"] == 18
    assert p["routing_objective"].startswith("length_m")


@pytest.mark.parametrize("path", [UISEONG, ULJIN])
def test_the_run_read_snapshots_and_not_the_cache(path):
    _needs(path)
    src = _load(path)["network_source"]
    assert src["read_from_cache"] is False
    for key in ("snapshot_walk", "snapshot_shelters", "snapshot_depots"):
        assert (REPO / "data/snapshots" / src[key]).exists(), src[key]


@pytest.mark.parametrize("path", [UISEONG, ULJIN])
def test_preflight_checks_are_recorded_not_merely_run(path):
    _needs(path)
    pf = _load(path)["preflight"]
    assert pf["boundary_contact"]["any_slice_reached_edge"] is False
    assert pf["walk_nodes_vs_hazard_grid"]["n_outside_hazard_extent"] == 0
    assert pf["envelope_coverage"]["final_slice"]["coverage"] is not None
    assert "dem_footprint" in pf


# ---------------------------------------------------------------------------
# 4. "No depot in this bbox" must never become "zero dispatches"
# ---------------------------------------------------------------------------


def test_uiseong_records_the_responder_side_as_not_applicable():
    _needs(UISEONG)
    r = _load(UISEONG)["responder_side"]
    assert r["responder_side_available"] is False
    assert r["n_depot_pois"] == 0
    assert r["computed"] is False
    assert "NOT APPLICABLE" in r["status"]
    # The status line is what a reader quotes. It must not read as a count.
    assert "0 dispatch" not in r["status"] and "zero dispatch" not in r["status"].lower()
    # And the record must carry both prohibitions explicitly, not merely avoid
    # tripping them.
    assert "NEVER zero dispatches" in r["note"] or "never as zero dispatches" in r["note"]
    assert "has no fire stations" in r["depot_phrasing_rule"], (
        "the artifact must state the forbidden phrasing so it cannot be "
        "reinvented downstream")
    assert "NEVER write" in r["depot_phrasing_rule"]
    assert "3,926" in r["depot_phrasing_rule"], (
        "the wider bbox containing six stations must travel with the zero")


def test_uljin_has_depots_but_the_series_still_does_not_compute_them():
    """Symmetry: the 459 series is resident-side for EVERY region."""
    _needs(ULJIN)
    r = _load(ULJIN)["responder_side"]
    assert r["responder_side_available"] is True
    assert r["n_depot_pois"] == 4
    assert r["computed"] is False


# ---------------------------------------------------------------------------
# 5. The Uljin DEM hole — the claim the comparison leans on
# ---------------------------------------------------------------------------


def test_uljin_dem_gap_is_measured_and_bounded():
    _needs(ULJIN)
    d = _load(ULJIN)
    gap = d["preflight"]["dem_footprint"]
    assert gap["n_nodes_outside_dem"] > 0, (
        "this region's DEM starts at 36.85 N and its walk bbox at 36.81 N; a zero "
        "here means the check stopped working, not that the gap closed")
    hole = d["dem_hole_origins"]
    assert hole is not None
    # THE bound: no origin in the DEM hole reaches a bucket the comparison reads.
    for bucket in ("naive_into_FA_safe", "no_safe_route", "both_enter"):
        assert hole["by_bucket"][bucket] == 0, (
            f"a DEM-hole origin landed in {bucket}; the flat-timing fallback now "
            "touches a reported count and the comparison must say so")


def test_the_silent_flat_fallback_is_counted():
    _needs(ULJIN)
    ds = _load(ULJIN)["arms"]["slope_digraph_canonical"]["slope_stats"]["dem_sampling"]
    assert ds["n_nodata_samples"] > 0
    assert 0.0 < ds["frac_nodata"] < 0.25
    assert ds["n_elev_samples"] > ds["n_nodata_samples"]


# ---------------------------------------------------------------------------
# 6. The comparison table
# ---------------------------------------------------------------------------


def test_comparison_covers_three_regions_in_a_fixed_order():
    _needs(COMPARISON)
    d = _load(COMPARISON)
    assert [r["region"] for r in d["regions"]] == list(d["region_order"])
    assert d["n_regions"] == 3


def test_yeongdeok_row_is_quoted_not_rerun():
    _needs(COMPARISON)
    y = next(r for r in _load(COMPARISON)["regions"] if r["region"] == "yeongdeok_2025")
    assert y["quoted_not_rerun"] is True
    assert y["primary_source"]["source_file"].endswith("slope_60.json")
    variants = {v["role"] for v in y["yeongdeok_variants"]}
    assert variants == {"primary", "context"}


def test_every_row_carries_its_covariates():
    _needs(COMPARISON)
    for r in _load(COMPARISON)["regions"]:
        for key in ("envelope_coverage_final_slice", "road_density_km_per_km2",
                    "node_density_per_km2", "envelope_area_ha", "depot_pois",
                    "origins_per_road_km", "origins_per_1000_walk_nodes"):
            assert r[key] is not None, f"{r['region']} missing {key}"


def test_the_metric_is_labelled_as_not_being_w():
    _needs(COMPARISON)
    md = _load(COMPARISON)["metric_definition"]
    assert "NOT the walk-failure rate w" in md["is_not"]
    assert md["series"].startswith("459")


def test_n_equals_3_is_stated_and_no_p_values_are_emitted():
    _needs(COMPARISON)
    a = _load(COMPARISON)["associations_directional_only"]
    assert a["n"] == 3
    assert a["no_p_values"] is True
    assert "n = 3" in a["warning"]

    # No significance statistic anywhere in the document, under any spelling.
    banned = {"p_value", "pvalue", "p", "significance", "confidence_interval",
              "ci", "alpha"}

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                assert k.lower() not in banned, f"significance-flavoured key: {k}"
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(_load(COMPARISON))


def test_envelope_area_uses_one_definition_for_all_three():
    _needs(COMPARISON)
    d = _load(COMPARISON)["envelope_area_definition"]
    assert d["computed_here_for_all_three"] is True
    assert len(d["values_ha"]) == 3
    assert d["spread_max_over_min"] < 5.0, (
        "a spread near 12x means a Yeongdeok figure from a DIFFERENT simulation "
        "artifact has been mixed into this column")


def test_normalised_origin_counts_are_reported_against_both_denominators():
    """Uiseong-Andong is the reason this exists: most road, fewest nodes."""
    _needs(COMPARISON)
    rows = {r["region"]: r for r in _load(COMPARISON)["regions"]}
    ui, yd = rows["uiseong_andong_2025"], rows["yeongdeok_2025"]
    assert ui["road_density_km_per_km2"] > yd["road_density_km_per_km2"]
    assert ui["node_density_per_km2"] < yd["node_density_per_km2"]
    # Per NODE the scan is near-identical across regions; per ROAD-KM it is not.
    per_node = [r["origins_per_1000_walk_nodes"] for r in rows.values()]
    per_km = [r["origins_per_road_km"] for r in rows.values()]
    assert max(per_node) / min(per_node) < 1.10
    assert max(per_km) / min(per_km) > 1.30, (
        "if these agreed, the two-denominator caveat would be unnecessary")


def test_the_decomposition_is_present_because_the_headline_alone_misleads():
    _needs(COMPARISON)
    cg = _load(COMPARISON)["core_growth_vs_metric"]
    assert cg["n_is_3"] is True
    assert cg["same_ordering_as_fa_only"] is False
    assert "NOT SUPPORTED" in cg["finding"]
    for r in _load(COMPARISON)["regions"]:
        assert r["future_aware_rescue_rate"] is not None
        assert r["n_naive_route_unsafe"] == (
            r["future_aware_only_safe"] + r["no_safe_route"]
            + r["other_buckets"]["both_enter"])
