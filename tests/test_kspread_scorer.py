"""K-SPREAD-2025 scorer — the rules of the protocol, asserted rather than described.

Five things can rot here, and each of them would make a leaderboard say something it has
not measured:

1. **The truth rule drifts from its reference.** ``docs/benchmark/K_SPREAD_2025.md`` §4
   builds truth under ``docs/regrade_three_way.md`` §2, whose reference implementation is
   ``scripts/regrade_three_way.py``. ``scripts/benchmark/kspread_truth.py`` transcribes two
   of its functions; a transcription that is never compared is a second opinion wearing the
   first one's name. So it is compared, on the committed npz, cell for cell, and
   ``node_truth`` is compared against ``classify_route``'s own verdict on a synthetic route.
2. **An indeterminate cell reaches a score.** Protocol §5 excludes it from the AUC and
   counts it separately in the IoU. A scorer that folds it into the negatives inflates both.
3. **The complex rule quietly lapses.** E3 must be the field fitted with 영덕 AND 의성·안동
   held out (``routing_demo_leakfree.npz``), not the canonical field, which had 의성·안동 in
   its training set.
4. **A hindcast is reported beside a forecast.** Protocol §3 forbids it. The committed WFG
   field steps on ERA5 weather from after T0, so it is hindcast-track, and the leaderboard
   must keep the two tracks apart.
5. **The 500 m -> 100 m upsampling is assumed rather than checked.** Protocol §4 allows a
   500 m entrant if it says so; C4 claims nearest-neighbour upsampling changes no metric.

Nothing here reads the clock, the timezone, the network or a file outside the repository
(CHARTER §4b).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "benchmark"))

import kspread_metrics as M  # noqa: E402
import kspread_truth as T  # noqa: E402

CANON = REPO / "data/processed/routing_demo_canonical.npz"
BENCH = REPO / "data/processed/benchmark"
HORIZONS = (180.0, 300.0, 480.0)


# --- 1. the truth rule is the reference implementation ------------------------------

def test_first_seen_and_earliest_match_the_reference_implementation():
    from regrade_three_way import earliest as ref_earliest, first_seen_grid as ref_fs

    z = np.load(CANON)
    fs, t = T.first_seen_grid(z)
    fs_ref, t_ref = ref_fs(z)
    assert np.array_equal(t, t_ref)
    assert np.array_equal(np.isfinite(fs), np.isfinite(fs_ref))
    assert np.array_equal(fs[np.isfinite(fs)], fs_ref[np.isfinite(fs_ref)])
    for first in list(t) + [np.inf]:
        for m in T.MISS:
            assert T.earliest(first, t, m) == ref_earliest(first, t_ref, m)


def test_node_truth_reproduces_classify_route_class_m0():
    """A route's ``class_m0`` is a fold over its nodes; ``node_truth`` must give the folds."""
    import networkx as nx
    from regrade_three_way import classify_route

    from wildfireguardian.spread_v2.grid import CoarseGrid

    cell = 500.0
    nrows = ncols = 4
    grid = CoarseGrid(minx=0.0, miny=0.0, maxx=cell * ncols, maxy=cell * nrows,
                      cell_size_m=cell, nrows=nrows, ncols=ncols)
    t = np.array([0.0, 300.0, 900.0])
    fs = np.full((nrows, ncols), np.inf)
    fs[0, 0] = 0.0        # burning at T0
    fs[0, 1] = 300.0      # first seen at the second overpass
    fs[0, 2] = 900.0      # first seen at the third
    xy = {i: (cell * i + cell / 2, grid.maxy - cell / 2) for i in range(ncols)}

    class _Net:
        def __init__(self, g, xy):
            self.graph, self._xy = g, xy

        def node_xy(self, n):
            return self._xy[n]

    for travel in (10.0, 200.0, 500.0):
        g = nx.DiGraph()
        for a in range(ncols - 1):
            g.add_edge(a, a + 1, time_min=travel)
        net = _Net(g, xy)
        path = list(range(ncols))
        ref = classify_route(net, path, fs, t, grid)

        times, acc = [0.0], 0.0
        for _ in range(len(path) - 1):
            acc += travel
            times.append(acc)
        inadmissible, indeterminate = False, False
        for n, tp in zip(path, times):
            x, y = xy[n]
            nt = T.node_truth(x, y, fs, t, (grid.minx, grid.miny, grid.maxx, grid.maxy,
                                            cell, nrows, ncols), 0)
            assert nt["supported"]
            if nt["observed_min"] <= tp:
                inadmissible = True
            if tp >= nt["earliest_min"]:
                indeterminate = True
        mine = ("inadmissible_all" if inadmissible
                else "indeterminate" if indeterminate else "admissible_all")
        assert mine == ref["class_m0"], (travel, mine, ref)


def test_the_two_readings_of_protocol_section_4_agree():
    """§4's overpass wording and A2's miss-allowance wording must class every cell alike."""
    z = np.load(CANON)
    fs, t = T.first_seen_grid(z)
    for h in HORIZONS:
        a = T.horizon_truth(fs, t, h, 0)
        b = T.horizon_truth_from_overpasses(fs, t, h)
        for c in T.CLASSES:
            assert np.array_equal(a[c], b[c]), (h, c)
        assert int(sum(a[c].sum() for c in T.CLASSES)) == fs.size


def test_horizon_classes_partition_and_indeterminate_is_the_overpass_gap():
    z = np.load(CANON)
    fs, t = T.first_seen_grid(z)
    tr = T.horizon_truth(fs, t, 180.0, 0)
    # 영덕's overpasses are 0 and 333 min: nothing between them, so everything first seen at
    # 333 is unknowable at 180 min and nothing else is.
    assert set(np.unique(fs[tr[T.INDETERMINATE]]).tolist()) == {333.0}
    assert set(np.unique(fs[tr[T.DETECTED]]).tolist()) == {0.0}


# --- 2. an indeterminate cell never reaches a score ----------------------------------

def _toy():
    """A 1 x 4 event with truth known by hand at horizon 100.

    overpasses 0 and 200; cell 0 detected at 0, cell 1 first seen at 200 (indeterminate at
    100 because it could have been burning since 0), cells 2 and 3 never detected.
    """
    obs = np.array([[[1, 0, 0, 0]], [[1, 1, 0, 0]]], dtype=np.uint8)
    z = {"obs_stack": obs, "obs_times": np.array([0.0, 200.0])}
    fs, t = T.first_seen_grid(z)
    return fs, t


def test_indeterminate_cells_enter_neither_auc_nor_iou():
    fs, t = _toy()
    times = np.array([0.0, 100.0])
    # the entrant calls cells 0 and 1 burned; cell 1 is the indeterminate one.
    stack = np.array([[[1.0, 0.0, 0.0, 0.0]], [[1.0, 1.0, 0.0, 0.0]]])
    r = M.auc_iou_at_horizon(stack, times, fs, t, 100.0, 0)
    assert r["cells_by_truth_class"] == {T.DETECTED: 1, T.INDETERMINATE: 1, T.NOT_DETECTED: 2}
    assert r["cells_unscorable_indeterminate"] == 1
    # scorable cells are 0 (detected, p=1) and 2, 3 (not detected, p=0): perfect.
    assert r["roc_auc"] == 1.0
    assert r["iou_at_p_ge_0.5"] == pytest.approx(1.0)
    assert r["iou_intersection"] == 1 and r["iou_union"] == 1
    # the same entrant graded with the indeterminate cell folded into the negatives would
    # be punished for it; that is the mistake this asserts against.
    assert r["cells_predicted_positive"] == 2
    assert r["cells_predicted_positive_indeterminate"] == 1


def test_an_entrant_that_misses_a_detected_cell_is_punished():
    fs, t = _toy()
    times = np.array([0.0, 100.0])
    stack = np.zeros((2, 1, 4))            # calls nothing burned, ever
    r = M.auc_iou_at_horizon(stack, times, fs, t, 100.0, 0)
    assert r["iou_at_p_ge_0.5"] == pytest.approx(0.0)   # one detected cell, nothing predicted
    assert r["iou_intersection"] == 0 and r["iou_union"] == 1
    assert r["roc_auc"] == 0.5             # constant score, one positive, two negatives
    # IoU is None only when there is nothing to intersect AND nothing to miss.
    empty = np.zeros((2, 1, 2))
    fs2, t2 = T.first_seen_grid({"obs_stack": np.zeros((2, 1, 2), np.uint8),
                                 "obs_times": np.array([0.0, 200.0])})
    assert M.auc_iou_at_horizon(empty, times, fs2, t2, 100.0, 0)["iou_at_p_ge_0.5"] is None


# --- metric 1/2/3 arithmetic, re-derived by hand -------------------------------------

def test_surface_and_crossing_are_linear_in_time_and_clamped_outside():
    times = np.array([0.0, 100.0, 200.0])
    stack = np.array([[[0.0, 0.2]], [[0.6, 0.4]], [[1.0, 0.5]]])
    assert M.surface_at(stack, times, -5.0).tolist() == [[0.0, 0.2]]
    assert M.surface_at(stack, times, 999.0).tolist() == [[1.0, 0.5]]
    assert M.surface_at(stack, times, 50.0) == pytest.approx(np.array([[0.3, 0.3]]))
    c = M.crossing_grid(stack, times)
    assert c[0, 0] == pytest.approx(100.0 * (0.5 - 0.0) / (0.6 - 0.0))
    assert c[0, 1] == pytest.approx(200.0)
    never = M.crossing_grid(np.array([[[0.1]], [[0.2]]]), np.array([0.0, 10.0]))
    assert not np.isfinite(never[0, 0])


def test_arrival_time_error_signs_late_as_positive_and_counts_false_safe():
    nodes = [
        {"supported": True, "model_min": 120.0, "observed_min": 60.0, "earliest_min": 0.0},
        {"supported": True, "model_min": 30.0, "observed_min": 60.0, "earliest_min": 0.0},
        {"supported": True, "model_min": math.inf, "observed_min": 90.0, "earliest_min": 0.0},
        {"supported": True, "model_min": math.inf, "observed_min": math.inf, "earliest_min": math.inf},
        {"supported": True, "model_min": 50.0, "observed_min": math.inf, "earliest_min": math.inf},
        {"supported": False, "model_min": math.inf, "observed_min": math.inf, "earliest_min": math.inf},
    ]
    r = M.arrival_time_error(nodes, 600.0)
    assert r["nodes_unsupported"] == 1 and r["nodes_supported"] == 5
    assert r["nodes_both_burn"] == 2
    assert r["median_signed_error_min"] == pytest.approx(15.0)   # median of +60 and -30
    assert r["median_abs_error_min"] == pytest.approx(45.0)      # median of 60 and 30
    assert r["nodes_model_late"] == 1 and r["nodes_model_early"] == 1
    assert r["nodes_model_calls_safe"] == 2                       # the two inf rows
    assert r["false_safe_nodes"] == 1                             # only the observed-burned one
    assert r["false_safe_rate"] == pytest.approx(0.5)
    assert r["false_alarm_nodes"] == 1


def test_a_node_the_observation_burns_only_after_the_window_is_not_a_false_safe():
    """The entrant's horizon bounds the charge; the whole record is reported beside it."""
    nodes = [{"supported": True, "model_min": math.inf, "observed_min": 900.0, "earliest_min": 700.0}]
    r = M.arrival_time_error(nodes, 720.0)
    assert r["false_safe_nodes"] == 0
    assert r["nodes_observation_indeterminate_at_window"] == 1
    assert r["whole_observation_record"]["false_safe_nodes"] == 1


# --- C4: the 500 m -> 100 m upsampling changes no metric -----------------------------

def test_nearest_neighbour_upsampling_to_100m_changes_no_metric():
    fs, t = _toy()
    times = np.array([0.0, 100.0])
    stack = np.array([[[1.0, 0.0, 0.0, 0.0]], [[1.0, 0.9, 0.3, 0.0]]])
    k = 5                                   # 500 m -> 100 m
    up = (lambda a: np.repeat(np.repeat(a, k, axis=-1), k, axis=-2))
    fs_up = up(fs[None])[0]
    base = M.auc_iou_at_horizon(stack, times, fs, t, 100.0, 0)
    fine = M.auc_iou_at_horizon(up(stack), times, fs_up, t, 100.0, 0)
    assert fine["roc_auc"] == pytest.approx(base["roc_auc"])
    assert fine["iou_at_p_ge_0.5"] == pytest.approx(base["iou_at_p_ge_0.5"])
    assert fine["cells_total"] == base["cells_total"] * k * k


# --- 3, 4: the committed v0.1 bundles obey the protocol ------------------------------

def test_e3_is_the_leave_one_complex_out_field_and_not_the_canonical_one():
    import hashlib

    meta = json.loads((BENCH / "entrants/e3_wfg_canonical/entrant.json").read_text(encoding="utf-8"))
    src = REPO / meta["provenance"]["source"]
    assert src.name == "routing_demo_leakfree.npz", "E3 must be the leak-free field"
    assert hashlib.sha256(src.read_bytes()).hexdigest() == meta["provenance"]["source_sha256"]
    fold = json.loads((REPO / "data/processed/leakfree_yeongdeok_fold.json").read_text(encoding="utf-8"))
    rows = fold["held_out_yeongdeok_auc"]["training_rows"]
    assert rows["leakfree"] < rows["canonical"], "의성·안동 was not held out of E3's training set"
    zc, zf = np.load(CANON), np.load(src)
    assert not np.array_equal(zc["haz_stack"], zf["haz_stack"]), "E3 is the canonical field"


def test_the_leaderboard_keeps_the_two_tracks_apart():
    board = json.loads((BENCH / "leaderboard.json").read_text(encoding="utf-8"))
    tracks = board["tracks"]
    assert set(tracks) == {"forecast", "hindcast"}
    ids = {e["entrant"]: track for track, rows in tracks.items() for e in rows}
    assert ids["e0_persistence"] == "forecast"
    assert ids["e3_wfg_canonical"] == "hindcast", (
        "the committed WFG field steps on ERA5 weather after T0 (protocol §3)")
    assert board["protocol_version"] == "v0.1"


def test_every_protocol_event_is_either_scored_or_named_as_unscorable():
    from score_kspread import PROTOCOL_EVENTS

    board = json.loads((BENCH / "leaderboard.json").read_text(encoding="utf-8"))
    named = set(board["events_scored"]) | set(board["events_unscorable"])
    assert named == set(PROTOCOL_EVENTS), "an event must be scored or explained, never dropped"
    for rows in board["tracks"].values():
        for e in rows:
            assert set(e["per_event"]) | set(e["events_not_scored"]) == set(PROTOCOL_EVENTS)


def test_metric3_node_set_is_the_canonical_scan_and_is_the_same_for_every_entrant():
    board = json.loads((BENCH / "leaderboard.json").read_text(encoding="utf-8"))
    assert board["metric3_node_set"]["origins_subset_n"] == 458
    assert board["metric3_node_set"]["n_nodes"] > 458
    sizes = set()
    for e in ("e0_persistence", "e3_wfg_canonical"):
        d = json.loads((BENCH / e / "yeongdeok_2025.json").read_text(encoding="utf-8"))
        a = d["arrival_time_error"]
        sizes.add((a["nodes_scanned"], a["canonical_scan_origins_subset"]["nodes_scanned"]))
        assert a["nodes_scanned"] == board["metric3_node_set"]["n_nodes"]
        assert a["canonical_scan_origins_subset"]["nodes_scanned"] == 458
        cc = a["cell_coverage"]
        assert cc["cells_with_a_road_node"] < cc["cells_total"]
        assert a["nodes_observation_burns"] == a["whole_observation_record"]["nodes_observation_burns"] - 17
    assert len(sizes) == 1, "entrants were judged on different node sets"


def test_lsd_classes_are_the_published_cuts():
    assert M.lsd_class(-1.0) == "never"
    assert M.lsd_class(0.0) == "closes_before_5h"
    assert M.lsd_class(290.0) == "closes_before_5h"
    assert M.lsd_class(300.0) == "closes_after_5h"
    assert M.lsd_class(590.0) == "closes_after_5h"
    assert M.lsd_class(600.0) == "censored"


def test_decision_shift_counts_buildings_not_nodes_and_flags_optimism():
    weights = {1: 10, 2: 3, 3: 1}
    entrant = {1: 600.0, 2: 600.0, 3: -1.0}
    truth = {1: 600.0, 2: 100.0, 3: -1.0}
    r = M.decision_shift(entrant, truth, weights)
    assert r["buildings_scored"] == 14
    assert r["buildings_class_changed"] == 3
    assert r["buildings_entrant_more_optimistic"] == 3
