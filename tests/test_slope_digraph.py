"""Guards for the slope-aware DiGraph walk network (Round-3 PHASE 2).

The named risk when converting an undirected graph to a DiGraph is that the
graph silently becomes half a graph: `add_edge(u, v)` on a DiGraph adds one
direction, and a router on a half-graph still returns plausible routes. These
tests make that failure loud.

Tests needing the OSM snapshot skip cleanly when it is absent.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import numpy as np
import pytest

from wildfireguardian.routing.evacuation import ELDERLY_FLAT_SPEED_MS, elderly_speed_ms
from wildfireguardian.routing.slope import _resample_uniform, build_walk_network

REPO = Path(__file__).resolve().parents[1]
SNAP = REPO / "data/snapshots/osm-walk_yeongdeok-2025_20260724_2bff8d85.graphml.gz"
DEM = REPO / "data/raw/firms_data/yeongdeok_2025_dem.tif"

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")


def _graph():
    pytest.importorskip("osmnx")
    if not SNAP.exists():
        pytest.skip("OSM walk snapshot absent")
    from wildfireguardian.routing.slope import load_snapshot_graph
    return load_snapshot_graph(SNAP)


# ---------------------------------------------------------------------------
# Tobler reuse — must be the SAME function the 407-origin run uses
# ---------------------------------------------------------------------------


def test_tobler_is_reused_not_reimplemented():
    import wildfireguardian.routing.slope as slope_mod
    assert slope_mod.elderly_speed_ms is elderly_speed_ms


def test_tobler_is_asymmetric_which_is_why_direction_matters():
    """Uphill is slower than downhill at equal |slope| — the premise of DiGraph."""
    for s in (0.05, 0.10, 0.20, 0.40):
        assert elderly_speed_ms(s) < elderly_speed_ms(-s)
    # Peak speed is at -5 % (gentle downhill), not on the flat.
    assert elderly_speed_ms(-0.05) > elderly_speed_ms(0.0)


# ---------------------------------------------------------------------------
# Uniform arc-length resampling
# ---------------------------------------------------------------------------


def test_resample_is_uniform_arc_length():
    x = np.array([0.0, 10.0, 10.0, 110.0])       # 10 + 0 + 100 = 110 m, with a
    y = np.array([0.0, 0.0, 0.0, 0.0])           # deliberately tiny first vertex gap
    xs, ys, dl = _resample_uniform(x, y, 60.0)
    seg = np.hypot(np.diff(xs), np.diff(ys))
    assert np.allclose(seg, dl), "every sub-segment must share one baseline"
    assert dl == pytest.approx(55.0)             # 110 m / round(110/60)=2
    assert xs[0] == pytest.approx(0.0) and xs[-1] == pytest.approx(110.0)


def test_resample_rejects_degenerate_input():
    assert _resample_uniform(np.array([1.0]), np.array([1.0]), 60.0) is None
    assert _resample_uniform(np.array([0.0, 0.0]), np.array([0.0, 0.0]), 60.0) is None
    assert _resample_uniform(np.array([0.0, np.nan]), np.array([0.0, 1.0]), 60.0) is None


# ---------------------------------------------------------------------------
# THE structural guard: a DiGraph must not be half a graph
# ---------------------------------------------------------------------------


def test_digraph_has_exactly_two_directed_edges_per_undirected_edge():
    G = _graph()
    und, _ = build_walk_network(G, None, apply_slope=False, directed=False)
    di, _ = build_walk_network(G, None, apply_slope=False, directed=True)
    assert isinstance(di.graph, nx.DiGraph)
    assert not isinstance(und.graph, nx.DiGraph)
    assert di.graph.number_of_edges() == 2 * und.graph.number_of_edges()
    assert set(di.graph.nodes) == set(und.graph.nodes)


def test_every_edge_has_its_reverse():
    """All of them, not a sample — a half-graph still routes plausibly."""
    G = _graph()
    di, _ = build_walk_network(G, None, apply_slope=False, directed=True)
    missing = [(u, v) for u, v in di.graph.edges() if not di.graph.has_edge(v, u)]
    assert missing == [], f"{len(missing)} directed edges have no reverse"


def test_random_sample_of_100_edges_is_bidirectional():
    G = _graph()
    di, _ = build_walk_network(G, None, apply_slope=False, directed=True)
    edges = list(di.graph.edges())
    rng = np.random.default_rng(20250603)
    for i in rng.choice(len(edges), size=min(100, len(edges)), replace=False):
        u, v = edges[i]
        assert di.graph.has_edge(v, u)
        assert di.graph[u][v]["length_m"] == pytest.approx(di.graph[v][u]["length_m"])


# ---------------------------------------------------------------------------
# THE regression: with flat timing, direction carries no information
# ---------------------------------------------------------------------------


def test_flat_digraph_times_are_symmetric():
    G = _graph()
    di, _ = build_walk_network(G, None, apply_slope=False, directed=True)
    for u, v in list(di.graph.edges())[:2000]:
        assert di.graph[u][v]["time_min"] == pytest.approx(di.graph[v][u]["time_min"])


def test_flat_undirected_and_flat_digraph_agree_edge_for_edge():
    """The conversion alone must change nothing when timing is flat."""
    G = _graph()
    und, _ = build_walk_network(G, None, apply_slope=False, directed=False)
    di, _ = build_walk_network(G, None, apply_slope=False, directed=True)
    for u, v, d in und.graph.edges(data=True):
        assert di.graph[u][v]["time_min"] == pytest.approx(d["time_min"])
        assert di.graph[v][u]["time_min"] == pytest.approx(d["time_min"])


def test_flat_times_match_distance_over_flat_speed():
    G = _graph()
    di, _ = build_walk_network(G, None, apply_slope=False, directed=True)
    for u, v, d in list(di.graph.edges(data=True))[:500]:
        assert d["time_min"] == pytest.approx(
            (d["length_m"] / ELDERLY_FLAT_SPEED_MS) / 60.0)


# ---------------------------------------------------------------------------
# Slope build
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not DEM.exists(), reason="SRTM DEM absent")
def test_slope_build_is_directionally_asymmetric():
    G = _graph()
    di, stats = build_walk_network(G, DEM, sampling_m=60.0, directed=True,
                                   apply_slope=True)
    assert stats is not None
    asym = [abs(di.graph[u][v]["time_min"] - di.graph[v][u]["time_min"])
            for u, v in list(di.graph.edges())[:3000]]
    assert max(asym) > 0.0, "slope build produced no directional difference at all"
    # Slope must SLOW the network overall: Tobler penalises both up and down.
    tt = stats.as_dict()["traversal_time"]
    assert tt["pct_change_forward"] > 0.0
    assert tt["pct_change_reverse"] > 0.0


@pytest.mark.skipif(not DEM.exists(), reason="SRTM DEM absent")
def test_clipping_bounds_slope_and_is_reported():
    G = _graph()
    _, clipped = build_walk_network(G, DEM, sampling_m=60.0, max_abs_slope=0.60,
                                    directed=True, apply_slope=True)
    _, raw = build_walk_network(G, DEM, sampling_m=60.0, max_abs_slope=None,
                                directed=True, apply_slope=True)
    assert clipped.slope_abs.max() <= 0.60 + 1e-9
    assert raw.slope_abs.max() > 0.60, "expected some raw slopes above the clip"
    c = clipped.as_dict()["clipping"]
    assert c["n_clipped_subsegments"] > 0
    assert 0.0 < c["frac_clipped"] < 0.05, "clipping should touch only outliers"


@pytest.mark.skipif(not DEM.exists(), reason="SRTM DEM absent")
def test_length_is_unchanged_by_slope():
    """Slope changes TIME, never distance — naive_route ranks by distance."""
    G = _graph()
    flat, _ = build_walk_network(G, None, apply_slope=False, directed=True)
    slope, _ = build_walk_network(G, DEM, sampling_m=60.0, directed=True,
                                  apply_slope=True)
    for u, v, d in list(flat.graph.edges(data=True))[:1000]:
        assert slope.graph[u][v]["length_m"] == pytest.approx(d["length_m"])
