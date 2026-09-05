"""WFG-114 — tests for the present-perimeter arm (the fair opponent).

These are written to go RED when the thing they protect actually breaks, not to
restate the artifact. Two of them are graded rather than asserted: they mutate a
scratch copy of an input and check that the machinery notices.

Nothing here needs the network, the clock, the timezone, or a file outside the
repository (CHARTER §4b).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

ARTIFACT = REPO / "data/processed/present_perimeter_arm_uiseong_andong_2025.json"
COMMITTED = REPO / "data/processed/real_roads_real_hazard_uiseong_andong_2025.json"
NUMBERS = REPO / "docs/NUMBERS.json"
DOC = REPO / "docs/present_perimeter_arm.md"


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def numbers() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]


# ---------------------------------------------------------------------------
# The comparison is only meaningful if it stands on the committed run
# ---------------------------------------------------------------------------


def test_the_arm_reproduced_the_committed_headline_node_for_node(art):
    """If the 91 did not re-derive here, no ppa_ number may sit beside the 91.

    This is the load-bearing precondition of the whole row: the new arm and the
    committed headline have to be measured on the same graph, the same origins
    and the same hazard field, or the comparison is between two different
    experiments.
    """
    rep = art["committed_arm_reproduction"]
    assert rep["node_for_node_match"] is True
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    canon = committed["arms"]["slope_digraph_canonical"]
    assert rep["fa_only_here"] == canon["counts"]["naive_into_FA_safe"]
    assert art["n_origins_scanned"] == canon["n_origins_scanned"]


def test_the_committed_artifact_is_not_touched_by_the_new_arm():
    """The new arm is additive: the file the headline lives in must be untouched."""
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    canon = committed["arms"]["slope_digraph_canonical"]
    assert canon["counts"]["naive_into_FA_safe"] == 91
    assert canon["n_origins_scanned"] == 368


# ---------------------------------------------------------------------------
# Internal consistency of what the arm reports
# ---------------------------------------------------------------------------


def test_every_buffer_partitions_the_scanned_origins(art):
    n = art["n_origins_scanned"]
    for key, arm in art["arms_by_buffer_m"].items():
        c = arm["counts"]
        total = c["present_safe"] + c["present_enters"] + c["present_no_route"]
        assert total == n, f"buffer {key} m: {total} != {n}"
        assert (arm["fa_only_recovered_by_present"]
                + arm["fa_only_still_forecast_only"]) == arm["fa_only_n"]


def test_recovered_origins_are_a_subset_of_the_forecast_only_origins(art):
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    fa_only = {int(v) for v in
               committed["arms"]["slope_digraph_canonical"]
               ["origin_nodes_by_bucket"]["naive_into_FA_safe"]}
    for key, arm in art["arms_by_buffer_m"].items():
        rec = {int(v) for v in arm["fa_only_recovered_nodes"]}
        assert rec <= fa_only, f"buffer {key} m recovered a node that was not FA-only"
        safe = {int(v) for v in arm["origin_nodes_by_bucket"]["present_safe"]}
        assert rec <= safe, f"buffer {key} m counted an unsafe origin as recovered"


def test_the_1km_arm_strands_rather_than_burns(art):
    """At 1 km, no unrecovered forecast-only origin is one this arm burns.

    The weaker half of the doc's claim, and the half that was always true.
    """
    arm = art["arms_by_buffer_m"]["1000"]
    assert arm["counts"]["present_enters"] == 0
    assert arm["fa_only_missed_because"]["route_entered_the_fire"] == 0


def test_the_two_no_route_causes_are_measured_separately_and_sum(art):
    """The failure this lap's reviewer caught, turned into a gate.

    The first draft recorded ONE merged bucket, `refused_to_move_or_no_path`, and
    the prose then asserted the whole of it was "inside its own buffer". It was
    not: at 1 km it is 16 refused at the origin and 25 walled off from every
    refuge. A merged count cannot support a claim about either half, so the two
    causes must stay separate and must add up to the bucket they decompose.
    """
    for key, arm in art["arms_by_buffer_m"].items():
        causes = arm["no_route_causes"]
        assert set(causes) == {"refused_to_start", "walled_off_from_every_refuge"}
        assert (causes["refused_to_start"] + causes["walled_off_from_every_refuge"]
                == arm["counts"]["present_no_route"]), f"buffer {key} m"
        why = arm["fa_only_missed_because"]
        assert (why["refused_to_start"] + why["walled_off_from_every_refuge"]
                + why["route_entered_the_fire"]) == arm["fa_only_still_forecast_only"]
        # A cause is never larger than the bucket it is a part of.
        assert why["refused_to_start"] <= causes["refused_to_start"]
        assert (why["walled_off_from_every_refuge"]
                <= causes["walled_off_from_every_refuge"])


def test_the_refusal_cause_matches_the_routers_own_predicate(art):
    """Grade the cause labels against the router's refusal test, not against
    the script that wrote them.

    `future_aware_route` refuses to start when the planning field at the origin's
    own node is at or above p_cut. This recomputes that from the hazard file and
    the snapshot graph — the same code path (`HazardSequence.prob_at`) the router
    uses — and checks every label at the headline buffer. If the two ever
    disagree, the split in docs/present_perimeter_arm.md §3 is decoration.
    """
    import sys as _sys
    _sys.path.insert(0, str(REPO / "src"))
    from wildfireguardian.routing.hazard import HazardSequence
    from wildfireguardian.routing.slope import load_snapshot_graph
    from wildfireguardian.spread_v2.grid import CoarseGrid
    from run_present_perimeter_arm import present_mask, snapshot_for

    z = np.load(REPO / "data/processed/hazard_uiseong_andong_2025.npz")
    haz = z["haz_stack"].astype(np.float32)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    mask = present_mask(haz, cell, 1000.0)
    frozen = HazardSequence(grid=grid, times_min=np.asarray(z["haz_times"], float),
                            surfaces=[mask.astype(float)] * len(z["haz_times"]))

    G = load_snapshot_graph(snapshot_for("osm-walk"))
    arm = art["arms_by_buffer_m"]["1000"]
    for node_str, label in arm["no_route_cause_by_node"].items():
        n = int(node_str)
        x, y = float(G.nodes[n]["x"]), float(G.nodes[n]["y"])
        inside = frozen.prob_at(x, y, 0.0) >= 0.5
        expected = "refused_to_start" if inside else "walled_off_from_every_refuge"
        assert label == expected, (
            f"node {n} is labelled {label} but the router's own refusal predicate "
            f"says {expected}")


def test_the_escape_analysis_partitions_and_is_not_decoration(art):
    """The measurement that refuted this lap's own second wrong sentence.

    The doc claims 10 of 11 walled-off origins escape across ground that never
    burns, so the residual advantage is "the buffer was too wide" rather than
    "the forecast knows which side stays open". That split has to partition, has
    to be a subset of the walled-off bucket, and the per-origin detail has to
    agree with the two summary counts — otherwise the sentence is decoration
    again, which is exactly how this lap got it wrong twice.
    """
    for key, arm in art["arms_by_buffer_m"].items():
        e = arm["walled_off_escape_analysis"]
        n = e["n_walled_off_with_a_forecast_route"]
        assert (e["n_whose_forecast_route_crosses_ground_that_does_burn"]
                + e["n_whose_forecast_route_only_crosses_ground_that_never_burns"]
                == n), f"buffer {key} m: the escape split does not partition"
        assert n <= arm["no_route_causes"]["walled_off_from_every_refuge"]
        assert len(e["per_origin"]) == n
        # Recount the summary from the detail rather than trusting it.
        burning = sum(1 for d in e["per_origin"]
                      if d["fa_nodes_in_mask_that_ever_burn"] > 0)
        assert burning == e["n_whose_forecast_route_crosses_ground_that_does_burn"]
        walled = {int(v) for v in
                  arm["origin_nodes_by_bucket"]["walled_off_from_every_refuge"]}
        assert {d["origin"] for d in e["per_origin"]} <= walled


def test_most_of_the_1km_mask_is_ground_that_never_burns(art):
    """The fact that made 'the forecast knows which side stays open' unsafe.

    Recomputed here from the hazard file and the dilation, not read from the
    artifact, so the artifact cannot assert it into being true.
    """
    from run_present_perimeter_arm import present_mask

    z = np.load(REPO / "data/processed/hazard_uiseong_andong_2025.npz")
    haz = z["haz_stack"].astype(np.float32)
    cell = float(z["grid_extent"][4])
    mask = present_mask(haz, cell, 1000.0)
    ever = (haz >= 0.5).any(axis=0)
    recorded = art["mask_1km_vs_what_actually_burns"]
    assert int(mask.sum()) == recorded["mask_cells"]
    assert int((mask & ~ever).sum()) == recorded["mask_cells_that_never_burn"]
    assert recorded["fraction_of_mask_that_never_burns"] > 0.3, (
        "if most of the buffer burns after all, the doc's §3 conclusion about "
        "the buffer being too wide has to be re-argued")


def test_the_gaps_are_the_subtraction_they_claim_to_be(art):
    lad = art["ladder_safe_counts"]
    g = art["gaps"]
    assert g["forecast_minus_present_1km"] == lad["forecast_aware"] - lad["present_1000m"]
    best = max(v for k, v in lad.items() if k.startswith("present_"))
    assert g["forecast_minus_present_best"] == lad["forecast_aware"] - best


def test_the_buffer_mask_grows_monotonically(art):
    """A bigger buffer must cover at least as much as a smaller one."""
    geo = sorted(art["geometry_by_buffer_m"].values(), key=lambda g: g["buffer_m"])
    cells = [g["mask_cells"] for g in geo]
    assert cells == sorted(cells)
    covered = [g["final_core_cells_covered"] for g in geo]
    assert covered == sorted(covered)


def test_the_ladder_agrees_with_the_arms_it_summarises(art):
    """`ladder_safe_counts` is a view, so it must not be able to drift."""
    lad = art["ladder_safe_counts"]
    for key, arm in art["arms_by_buffer_m"].items():
        assert lad[f"present_{key}m"] == arm["counts"]["present_safe"]
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    cc = committed["arms"]["slope_digraph_canonical"]["counts"]
    # `fa_exceeds_budget` is entered only when the NAIVE route was safe and the
    # forecast-aware one failed to reach, so those origins are naive successes.
    # Reporting only `both_safe` understates the opponent by 2, in this project's
    # own favour, which is the direction a gate should care about most.
    assert lad["naive"] == cc["both_safe"] + cc["fa_exceeds_budget"]
    assert lad["forecast_aware"] == cc["both_safe"] + cc["naive_into_FA_safe"]


# ---------------------------------------------------------------------------
# The dilation, tested against geometry rather than against itself
# ---------------------------------------------------------------------------


def test_the_buffer_is_a_disk_of_the_right_radius():
    """The buffer must be a EUCLIDEAN disk, not scipy's default cross.

    A cross under-buffers the diagonals, which would make the opponent quietly
    weaker than the margin it was told to keep. Graded on a synthetic grid, so
    it does not depend on the region's data.

    The shape is graded at radius 3, NOT at the headline's radius 2, because a
    disk and a cross of radius 2 are the same set of cells: at 1 km on the
    committed 500 m grid the choice of element cannot change the result, and a
    test written at radius 2 would pass a cross and prove nothing. (That is also
    a fact worth knowing about the headline: `ppa_recovered_1km` is invariant to
    this choice; the 2 km and wider rows in the sweep are not.)
    """
    from run_present_perimeter_arm import present_mask

    haz = np.zeros((1, 21, 21), dtype=np.float32)  # one slice, 21x21 cells
    haz[0, 10, 10] = 1.0

    # radius 2 (the headline's 1 km): reach, and no further.
    m = present_mask(haz, cell_m=500.0, buffer_m=1000.0)
    assert m[10, 12] and m[12, 10], "the buffer does not reach 2 cells on the axes"
    assert m[11, 11], "the buffer does not reach the near diagonal"
    assert not m[13, 10], "the buffer reaches further than it was asked to"
    assert not m[12, 12], "a square element over-buffered the far diagonal"

    # radius 3 (1.5 km): here disk and cross diverge, so the shape is graded.
    m3 = present_mask(haz, cell_m=500.0, buffer_m=1500.0)
    assert m3[12, 12], (
        "the (2,2) cell is 2.83 cells away and inside a radius-3 disk; a cross "
        "or diamond element excludes it and under-buffers every diagonal")
    assert not m3[13, 12], "the buffer reaches beyond radius 3"
    assert not m3[13, 13], "a square element over-buffered the far diagonal"

    # Zero buffer is the perimeter itself, with no dilation at all.
    m0 = present_mask(haz, cell_m=500.0, buffer_m=0.0)
    assert m0.sum() == 1 and m0[10, 10]


def test_a_sub_cell_buffer_rounds_up_rather_than_vanishing():
    """A margin smaller than one cell must not silently become no margin."""
    from run_present_perimeter_arm import present_mask

    haz = np.zeros((1, 11, 11), dtype=np.float32)
    haz[0, 5, 5] = 1.0
    m = present_mask(haz, cell_m=500.0, buffer_m=100.0)
    assert m[5, 6], "a 100 m margin on a 500 m grid disappeared"


# ---------------------------------------------------------------------------
# Graded, not asserted: does the registry gate actually notice a wrong number?
# ---------------------------------------------------------------------------


def test_the_registrar_refuses_a_run_that_did_not_reproduce_the_committed_91(tmp_path):
    """Flip the reproduction flag in a scratch copy; the registrar must refuse.

    Asserting that the registrar has an `if` in it proves nothing. This runs it
    against a mutated artifact and grades the exit code.
    """
    scratch = tmp_path / "repo"
    scratch.mkdir()
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    art["committed_arm_reproduction"]["node_for_node_match"] = False

    (scratch / "data" / "processed").mkdir(parents=True)
    (scratch / "docs").mkdir()
    (scratch / "scripts").mkdir()
    (scratch / "data/processed" / ARTIFACT.name).write_text(
        json.dumps(art), encoding="utf-8")
    (scratch / "docs/NUMBERS.json").write_text(NUMBERS.read_text(encoding="utf-8"),
                                               encoding="utf-8")
    reg = REPO / "scripts/register_present_perimeter_arm.py"
    (scratch / "scripts" / reg.name).write_text(reg.read_text(encoding="utf-8"),
                                                encoding="utf-8")

    r = subprocess.run([sys.executable, str(scratch / "scripts" / reg.name)],
                       capture_output=True, text=True)
    assert r.returncode == 2, (
        "the registrar registered numbers from a run that did not reproduce the "
        f"committed headline. stdout={r.stdout!r} stderr={r.stderr!r}")
    # And it must not have written anything: the registry is byte-identical.
    assert (scratch / "docs/NUMBERS.json").read_text(encoding="utf-8") == \
        NUMBERS.read_text(encoding="utf-8")


def test_the_registrar_notices_a_changed_artifact_value(tmp_path):
    """Move a number in a scratch artifact; `--check` must go red.

    The failure this guards against is the one that killed WFG-057: prose keeps
    quoting a figure the artifact no longer holds, and every gate stays green.
    """
    scratch = tmp_path / "repo"
    (scratch / "data" / "processed").mkdir(parents=True)
    (scratch / "docs").mkdir()
    (scratch / "scripts").mkdir()

    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    art["headline"]["fa_only_recovered_by_present"] += 1
    (scratch / "data/processed" / ARTIFACT.name).write_text(
        json.dumps(art), encoding="utf-8")
    (scratch / "docs/NUMBERS.json").write_text(NUMBERS.read_text(encoding="utf-8"),
                                               encoding="utf-8")
    reg = REPO / "scripts/register_present_perimeter_arm.py"
    (scratch / "scripts" / reg.name).write_text(reg.read_text(encoding="utf-8"),
                                                encoding="utf-8")

    r = subprocess.run([sys.executable, str(scratch / "scripts" / reg.name), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 1, f"--check passed a moved number. stdout={r.stdout!r}"
    assert "ppa_recovered_1km" in r.stdout


def test_check_passes_on_the_real_tree():
    """The other direction: the committed registry and artifact must agree now."""
    r = subprocess.run(
        [sys.executable, str(REPO / "scripts/register_present_perimeter_arm.py"), "--check"],
        capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------------------
# The doc may not drift from the artifact
# ---------------------------------------------------------------------------


def test_the_doc_quotes_the_registered_numbers(numbers):
    """Every headline figure in the prose has to be the registered one.

    Not a spell-check: these are the six figures a judge would repeat back.
    """
    text = DOC.read_text(encoding="utf-8")
    for key in ("ppa_fa_only_n", "ppa_recovered_1km", "ppa_forecast_only_1km",
                "ppa_safe_naive", "ppa_safe_1km", "ppa_safe_forecast",
                "ppa_safe_present_500m", "ppa_recovered_500m", "ppa_n_origins",
                "ppa_forecast_only_refused_1km", "ppa_forecast_only_walled_1km",
                "ppa_refused_to_start_1km", "ppa_walled_off_1km",
                "ppa_gap_1km", "ppa_gap_best",
                "ppa_walled_escape_n_analysed", "ppa_walled_escape_through_burning",
                "ppa_walled_escape_through_never_burning"):
        value = numbers[key]["value"]
        assert str(value) in text, f"{key} = {value} is not in {DOC.name}"


def test_the_doc_carries_the_limitation_that_makes_the_arm_an_upper_bound():
    """The present-aware arm is handed the TRUE perimeter. Saying so is not optional."""
    text = DOC.read_text(encoding="utf-8")
    assert "상한" in text
    assert "참" in text and "화선" in text


def test_the_forbidden_phrasing_is_registered_and_absent_from_the_doc(numbers):
    """The 12 are stranded, not burned; the wrong sentence is registered as forbidden."""
    entry = numbers["ppa_forecast_only_1km"]
    assert entry["forbidden_phrasings"], "no forbidden phrasing on the easiest key to misquote"
    text = DOC.read_text(encoding="utf-8")
    # The doc names both wrong sentences in order to forbid them.
    assert "금지 문장" in text
    assert "틀렸다, 0명이다" in text and "틀렸다, 4개다" in text
    assert "틀렸다, 11개 중 1개다" in text
    # And the doc must not claim the field is enforced, because it is not.
    assert "기록이지 강제가 아니다" in text
