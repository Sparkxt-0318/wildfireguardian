"""The classification must stay a partition, and the sixth category must be additive.

PHASE 2-C-2 added ``fa_exceeds_budget`` — "naive route safe, future-aware router
cannot finish within budget". The risk in adding a category is that it quietly
REDEFINES an existing one, which would change the committed 459-origin reading.
These tests pin that down: at a 600-minute budget the new category must be empty
and the five original counts must be exactly 440 / 17 / 3 / 0 / 0.

Tests needing the OSM snapshot and DEM skip cleanly when absent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

SNAP = REPO / "data/snapshots/osm-walk_yeongdeok-2025_20260724_2bff8d85.graphml.gz"
DEM = REPO / "data/raw/firms_data/yeongdeok_2025_dem.tif"
NPZ = REPO / "data/processed/routing_demo.npz"
SLOPE60 = REPO / "data/processed/real_roads_real_hazard_slope_60.json"
BUDGET = REPO / "data/processed/budget_sweep_experiment.json"

ORIGINAL_CATEGORIES = ("naive_into_FA_safe", "no_safe_route", "both_safe",
                       "both_enter", "naive_unreachable", "unclassified")
NEW_CATEGORY = "fa_exceeds_budget"


def _needs(*paths):
    for p in paths:
        if not p.exists():
            pytest.skip(f"{p.name} absent")


# ---------------------------------------------------------------------------
# Artifact-level guarantees (cheap: read the committed JSON)
# ---------------------------------------------------------------------------


def test_600min_counts_are_unchanged_by_the_new_category():
    """THE regression: adding a category must not move the five originals."""
    _needs(SLOPE60)
    d = json.loads(SLOPE60.read_text())
    c = d["three_column_comparison"]["col3_jul24_slope"]["counts"]
    assert c["both_safe"] == 440
    assert c["naive_into_FA_safe"] == 17
    assert c["no_safe_route"] == 3
    assert c["both_enter"] == 0
    assert c["naive_unreachable"] == 0
    assert c[NEW_CATEGORY] == 0, (
        "on THIS committed field the category is empty at a 600-minute budget "
        "— a non-zero value means the artifact moved. (This pins the committed "
        "count, not a law: the bucket's code condition does not establish the "
        "budget as the cause, and time-discretisation can populate it at any "
        "budget — docs/routing_limitations.md §1.)")
    assert c["unclassified"] == 0


def test_every_category_set_is_complete_and_partitions_n():
    _needs(SLOPE60)
    d = json.loads(SLOPE60.read_text())
    for arm in ("col2_jul24_flat", "col3_jul24_slope"):
        a = d["three_column_comparison"][arm]
        c = a["counts"]
        assert set(c) == set(ORIGINAL_CATEGORIES) | {NEW_CATEGORY}
        assert sum(c.values()) == a["n_origins_scanned"]


@pytest.mark.parametrize("budget", [30, 60, 90, 120, 600])
def test_unclassified_is_empty_at_every_budget(budget):
    """The residue bucket must be empty now that the real state has a name."""
    _needs(BUDGET)
    d = json.loads(BUDGET.read_text())
    row = next(r for r in d["sweep"] if int(r["budget_min"]) == budget)
    c = row["future_aware_counts"]
    assert c["unclassified"] == 0
    assert sum(c.values()) == row["n_origins"]


def test_new_category_only_fires_when_the_budget_binds():
    _needs(BUDGET)
    d = json.loads(BUDGET.read_text())
    rows = {int(r["budget_min"]): r["future_aware_counts"] for r in d["sweep"]}
    assert rows[600][NEW_CATEGORY] == 0
    for b in (30, 60, 90, 120):
        assert rows[b][NEW_CATEGORY] > 0, f"budget {b} should bind"
    # Tightening the budget can only move origins INTO the new category.
    seq = [rows[b][NEW_CATEGORY] for b in (600, 120, 90, 60, 30)]
    assert seq == sorted(seq), f"must increase monotonically as budget falls: {seq}"


def test_hazard_entry_is_a_baseline_property_not_a_system_cost():
    """The future-aware router never enters the hazard, by construction.

    The +3 hazard entries under the time objective therefore belong to the
    FIRE-BLIND baseline, not to the proposed system. `both_enter` — the only
    bucket where the future-aware route enters the hazard — must be 0 always.
    """
    _needs(BUDGET)
    d = json.loads(BUDGET.read_text())
    for r in d["sweep"]:
        assert r["future_aware_counts"]["both_enter"] == 0, (
            "future_aware_route skips nodes at/above p_cut, so it can never "
            "enter the hazard; a non-zero both_enter would contradict that")


# ---------------------------------------------------------------------------
# Live re-classification (needs the graph + DEM)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not (SNAP.exists() and DEM.exists() and NPZ.exists()),
                    reason="snapshot / DEM / hazard npz absent")
def test_live_classification_partitions_and_matches_the_artifact():
    pytest.importorskip("osmnx")
    from run_real_roads_real_hazard_slope import (
        candidate_origins, classify, load_hazard,
    )
    from wildfireguardian.routing.rescue import RescueConfig, load_shelters
    from wildfireguardian.routing.slope import build_walk_network, load_snapshot_graph
    from wildfireguardian.utils import regions
    from pyproj import Transformer

    hazard, haz, extent, _ = load_hazard()
    G = load_snapshot_graph(SNAP)
    net, _ = build_walk_network(G, DEM, sampling_m=60.0, directed=True,
                                apply_slope=True)
    cfg = RescueConfig(use_osm=True, osm_cache_dir=str(REPO / "data/cache/osm"))
    dests, _src = load_shelters(
        cfg, regions.lookup(cfg.region_name).bbox_wgs84,
        to_5179=Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True))
    net.shelters = {net.nearest_node(d.x, d.y) for d in dests}
    cand, _ = candidate_origins(net, hazard, haz, extent, 0.5)

    counts = classify(net, cand, hazard, 0.5, 600.0, 10.0)
    assert sum(counts.values()) == len(cand)
    assert counts[NEW_CATEGORY] == 0
    assert counts["unclassified"] == 0
    assert counts["both_safe"] == 440
    assert counts["naive_into_FA_safe"] == 17
    assert counts["no_safe_route"] == 3
    _ = np
