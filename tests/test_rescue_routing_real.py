"""Real-data (OSM partial-flip) tests for rescue-aware routing.

These mirror the four synthetic integration invariants but exercise the REAL
:func:`build_real_demo` path — OpenStreetMap walk/drive networks, OSM refuges
and OSM fire-station depots for the 영덕 extent. Following the repo's existing
skip-if-absent convention (cf. the FIRMS / SRTM real-data tests), the whole
module is skipped unless BOTH osmnx is importable AND the OSM graph cache is
present under ``data/cache/osm/`` — so the offline CI path is unaffected and
never silently downgrades to synthetic while claiming to test the real path.

The fire hazard and terrain remain synthetic here (pending the FIRMS bundle);
these tests therefore assert the routing *invariants* on real geometry, not any
absolute magnitude.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from wildfireguardian.routing.rescue import FOUR_WAY_CLASSES, RescueConfig
from wildfireguardian.routing.rescue_demo import (
    _split_counts,
    build_real_demo,
    run_pipeline,
)

# Derived from RescueConfig so it tracks the per-region layout automatically.
# Hard-coding "data/cache/osm" here would have made this whole module skip
# silently the moment the cache became region-scoped — the same silent-skip
# failure Round 2 shipped with (docs/ENVIRONMENT.md).
_OSM_CACHE = (Path(__file__).resolve().parents[1]
              / RescueConfig().osm_cache_path)
try:  # osmnx is needed to load the cached .graphml graphs
    import osmnx  # noqa: F401

    _HAVE_OSMNX = True
except Exception:  # pragma: no cover - depends on environment
    _HAVE_OSMNX = False

_HAVE_OSM = (
    _HAVE_OSMNX
    and (_OSM_CACHE / "drive.graphml").exists()
    and (_OSM_CACHE / "walk.graphml").exists()
)

pytestmark = pytest.mark.skipif(
    not _HAVE_OSM,
    reason=f"OSM cache absent ({_OSM_CACHE}) or osmnx not installed; "
    "real-data rescue-routing test skipped (offline CI path unaffected)",
)

# A modest, spatially-spread origin subsample keeps these real-graph tests fast
# (the OSM walk graph is ~8k nodes) while preserving the invariants.
_SUB_N = 60


@pytest.fixture(scope="module")
def real_scenario():
    scenario = build_real_demo(RescueConfig(use_osm=True))
    origins = scenario.origins
    if len(origins) > _SUB_N:
        stride = max(1, len(origins) // _SUB_N)
        origins = origins[::stride][:_SUB_N]
    sub = replace(scenario, origins=origins)
    return sub, run_pipeline(sub, sub.cfg)


def test_real_inputs_are_osm(real_scenario):
    """The real demo actually flipped the geometry to OSM (not a silent fallback)."""
    scenario, results = real_scenario
    assert scenario.walk_source == "osm"
    assert scenario.drive_source == "osm"
    assert scenario.shelters_source == "osm"
    assert scenario.depots_source == "osm"
    # Hazard + terrain remain synthetic pending the FIRMS bundle — never mislabelled.
    assert scenario.hazard_source == "synthetic"
    assert scenario.terrain_source == "synthetic"
    src = results.provenance["sources"]
    assert src["drive_network"] == "osm" and src["hazard"] == "synthetic"


def test_real_four_way_split_sums_to_n(real_scenario):
    """The four-way outcome split is exhaustive and sums to N on real geometry."""
    scenario, results = real_scenario
    assert set(results.four_way_counts) == set(FOUR_WAY_CLASSES)
    assert sum(results.four_way_counts.values()) == results.n_origins
    assert results.n_origins == len(scenario.origins)


def test_real_rescue_reachable_is_subset_of_safe(real_scenario):
    """rescue_reachable ⊆ safe holds on the real OSM drive network."""
    _scenario, results = real_scenario
    for a in results.dest_assessments:
        if a.rescue_reachable:
            assert a.safe, f"{a.name} rescue_reachable but not safe"


def test_real_four_way_reconciles_with_dispatch_and_unreachable(real_scenario):
    """no-walk / no-ingress counts ARE the dispatch / unreachable split (real run)."""
    _scenario, results = real_scenario
    c = results.four_way_counts
    assert c["no_safe_pedestrian_route"] == len(results.dispatch)
    assert c["no_surviving_vehicle_ingress"] == len(results.unreachable_homes)


def test_real_dispatch_delay_monotonicity(real_scenario):
    """Later responder dispatch → (weakly) more homes with no surviving ingress.

    The hazard is monotone non-decreasing in time, so a corridor that survives a
    larger dispatch delay also survives a smaller one; the ``no_surviving_vehicle_
    ingress`` count is therefore non-decreasing as the dispatch delay rises. This is
    the robust *direction* the full-N vehicle sweep reports, checked here on the real
    graph over the same fixed origin subsample.
    """
    scenario, _results = real_scenario
    unreach = []
    for delay in (0.0, 30.0, 60.0):
        rec = _split_counts(scenario, replace(scenario.cfg,
                                              responder_dispatch_delay_min=delay))
        assert sum(rec["counts"].values()) == len(scenario.origins)
        unreach.append(rec["counts"]["no_surviving_vehicle_ingress"])
    assert all(b >= a for a, b in zip(unreach, unreach[1:])), (
        f"no_surviving_vehicle_ingress not non-decreasing in dispatch delay: {unreach}")
    assert unreach[-1] >= unreach[0]
