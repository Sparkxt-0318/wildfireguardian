"""WFG-114 (NH-032 C) — tests for the BUDGET-CAPPED present-perimeter arm.

This is the build the author chose on 2026-09-12 as the fair opponent the
project states. It lives beside the pruned-graph build (`tests/test_present_
perimeter_arm.py`, `pp_uiseong_*`) and overwrites nothing of it.

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
sys.path.insert(0, str(REPO / "src"))

ARTIFACT = REPO / "data/processed/present_perimeter_arm_budgeted_uiseong_andong_2025.json"
SIBLING = REPO / "data/processed/present_perimeter_arm_uiseong_andong_2025.json"
COMMITTED = REPO / "data/processed/real_roads_real_hazard_uiseong_andong_2025.json"
NUMBERS = REPO / "docs/NUMBERS.json"
DOC = REPO / "docs/present_perimeter_arm_budgeted.md"
REGISTRAR = REPO / "scripts/register_present_perimeter_arm_budgeted.py"
MODULE = "run_present_perimeter_arm_budgeted"

pytestmark = pytest.mark.skipif(
    not ARTIFACT.exists(),
    reason=f"{ARTIFACT.relative_to(REPO)} not built; run scripts/{MODULE}.py")


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
    """If the 91 did not re-derive here, no ppb_ number may sit beside the 91."""
    rep = art["committed_arm_reproduction"]
    assert rep["node_for_node_match"] is True
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    canon = committed["arms"]["slope_digraph_canonical"]
    assert rep["fa_only_here"] == canon["counts"]["naive_into_FA_safe"]
    assert art["n_origins_scanned"] == canon["n_origins_scanned"]


def test_the_committed_artifacts_are_not_touched_by_the_new_arm():
    """Additive: the headline file AND the sibling pruned-graph arm are untouched."""
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    canon = committed["arms"]["slope_digraph_canonical"]
    assert canon["counts"]["naive_into_FA_safe"] == 91
    assert canon["n_origins_scanned"] == 368
    sib = json.loads(SIBLING.read_text(encoding="utf-8"))
    assert sib["headline"]["forecast_margin_over_present"] == 9, (
        "the pruned-graph arm's committed margin moved; NH-032 C replaces the "
        "opponent the project STATES, it does not rewrite the other build")


def test_this_build_is_the_budgeted_one_and_says_so(art):
    """A judge reading the artifact must see which of the two builds it is."""
    assert art["build"] == "budgeted"
    assert "NH-032 option C" in art["decided_by"]
    assert art["sibling_arm"]["registry_prefix"] == "pp_uiseong_"
    assert art["parameters"]["time_budget_min"] == 600.0


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
    """At 1 km, no unrecovered forecast-only origin is one this arm burns."""
    arm = art["arms_by_buffer_m"]["1000"]
    assert arm["counts"]["present_enters"] == 0
    assert arm["fa_only_missed_because"]["route_entered_the_fire"] == 0


def test_the_two_no_route_causes_are_measured_separately_and_sum(art):
    """The failure the parked lap's reviewer caught, turned into a gate.

    The first draft recorded ONE merged bucket and the prose then asserted the
    whole of it was "inside its own buffer". A merged count cannot support a
    claim about either half, so the two causes must stay separate and must add
    up to the bucket they decompose.
    """
    for key, arm in art["arms_by_buffer_m"].items():
        causes = arm["no_route_causes"]
        assert set(causes) == {"refused_to_start", "walled_off_from_every_refuge"}
        assert (causes["refused_to_start"] + causes["walled_off_from_every_refuge"]
                == arm["counts"]["present_no_route"]), f"buffer {key} m"
        why = arm["fa_only_missed_because"]
        assert (why["refused_to_start"] + why["walled_off_from_every_refuge"]
                + why["route_entered_the_fire"]) == arm["fa_only_still_forecast_only"]
        assert why["refused_to_start"] <= causes["refused_to_start"]
        assert (why["walled_off_from_every_refuge"]
                <= causes["walled_off_from_every_refuge"])


def test_the_refusal_cause_matches_the_routers_own_predicate(art):
    """Grade the cause labels against the router's refusal test, not against
    the script that wrote them.

    `future_aware_route` refuses to start when the planning field at the origin's
    own node is at or above p_cut. This recomputes that from the hazard file and
    the snapshot graph — the same code path (`HazardSequence.prob_at`) the router
    uses — and checks every label at the headline buffer.
    """
    from wildfireguardian.routing.hazard import HazardSequence
    from wildfireguardian.routing.slope import load_snapshot_graph
    from wildfireguardian.spread_v2.grid import CoarseGrid
    mod = __import__(MODULE)

    z = np.load(REPO / "data/processed/hazard_uiseong_andong_2025.npz")
    haz = z["haz_stack"].astype(np.float32)
    xmin, ymin, xmax, ymax, cell = [float(v) for v in z["grid_extent"]]
    grid = CoarseGrid(minx=xmin, miny=ymin, maxx=xmax, maxy=ymax,
                      cell_size_m=cell, nrows=haz.shape[1], ncols=haz.shape[2])
    mask = mod.present_mask(haz, cell, 1000.0)
    frozen = HazardSequence(grid=grid, times_min=np.asarray(z["haz_times"], float),
                            surfaces=[mask.astype(float)] * len(z["haz_times"]))

    G = load_snapshot_graph(mod.snapshot_for("osm-walk"))
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
    """The measurement the parked lap's reviewer forced.

    The doc claims most walled-off origins escape across ground that never
    burns, so the residual advantage is "the buffer was too wide" rather than
    "the forecast knows which side stays open". That split has to partition, has
    to be a subset of the walled-off bucket, and the per-origin detail has to
    agree with the two summary counts.
    """
    for key, arm in art["arms_by_buffer_m"].items():
        e = arm["walled_off_escape_analysis"]
        n = e["n_walled_off_with_a_forecast_route"]
        assert (e["n_whose_forecast_route_crosses_ground_that_does_burn"]
                + e["n_whose_forecast_route_only_crosses_ground_that_never_burns"]
                == n), f"buffer {key} m: the escape split does not partition"
        assert n <= arm["no_route_causes"]["walled_off_from_every_refuge"]
        assert len(e["per_origin"]) == n
        burning = sum(1 for d in e["per_origin"]
                      if d["fa_nodes_in_mask_that_ever_burn"] > 0)
        assert burning == e["n_whose_forecast_route_crosses_ground_that_does_burn"]
        walled = {int(v) for v in
                  arm["origin_nodes_by_bucket"]["walled_off_from_every_refuge"]}
        assert {d["origin"] for d in e["per_origin"]} <= walled
    # And at the headline width the "never burns" half must dominate, or the
    # doc's §3 conclusion has to be re-argued.
    e = art["arms_by_buffer_m"]["1000"]["walled_off_escape_analysis"]
    assert (e["n_whose_forecast_route_only_crosses_ground_that_never_burns"]
            > e["n_whose_forecast_route_crosses_ground_that_does_burn"])


def test_most_of_the_1km_mask_is_ground_that_never_burns(art):
    """Recomputed from the hazard file and the dilation, not read from the artifact."""
    mod = __import__(MODULE)

    z = np.load(REPO / "data/processed/hazard_uiseong_andong_2025.npz")
    haz = z["haz_stack"].astype(np.float32)
    cell = float(z["grid_extent"][4])
    mask = mod.present_mask(haz, cell, 1000.0)
    ever = (haz >= 0.5).any(axis=0)
    recorded = art["mask_1km_vs_what_actually_burns"]
    assert int(mask.sum()) == recorded["mask_cells"]
    assert int((mask & ~ever).sum()) == recorded["mask_cells_that_never_burn"]
    assert recorded["fraction_of_mask_that_never_burns"] > 0.3


def test_the_gaps_are_the_subtraction_they_claim_to_be(art):
    lad = art["ladder_safe_counts"]
    g = art["gaps"]
    assert g["forecast_minus_present_1km"] == lad["forecast_aware"] - lad["present_1000m"]
    best = max(v for k, v in lad.items() if k.startswith("present_"))
    assert g["forecast_minus_present_best"] == lad["forecast_aware"] - best
    assert lad[f"present_{int(art['best_buffer_m'])}m"] == best
    # The stated margin is at the author's 1 km, and the best-width figure can
    # only be smaller or equal (it is a maximum over the grid).
    assert g["forecast_minus_present_best"] <= g["forecast_minus_present_1km"]


def test_the_buffer_mask_grows_monotonically(art):
    geo = sorted(art["geometry_by_buffer_m"].values(), key=lambda g: g["buffer_m"])
    cells = [g["mask_cells"] for g in geo]
    assert cells == sorted(cells)
    covered = [g["final_core_cells_covered"] for g in geo]
    assert covered == sorted(covered)


def test_the_ladder_agrees_with_the_arms_it_summarises(art):
    lad = art["ladder_safe_counts"]
    for key, arm in art["arms_by_buffer_m"].items():
        assert lad[f"present_{key}m"] == arm["counts"]["present_safe"]
    committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
    cc = committed["arms"]["slope_digraph_canonical"]["counts"]
    assert lad["naive"] == cc["both_safe"] + cc["fa_exceeds_budget"]
    assert lad["forecast_aware"] == cc["both_safe"] + cc["naive_into_FA_safe"]


def test_the_two_builds_agree_on_the_forecast_arm_and_differ_on_the_opponent(art):
    """The two builds are different OPPONENTS, not a disagreement about one.

    Both must sit on the same forecast-aware total (354) and the same 91, or the
    two margins are not measured from the same baseline. And the budgeted arm
    must reach no more origins than the unbudgeted pruned-graph arm at 1 km —
    a budget and a refusal rule can only remove routes, never add them.
    """
    sib = json.loads(SIBLING.read_text(encoding="utf-8"))
    assert art["ladder_safe_counts"]["forecast_aware"] == sib["headline"]["safe_forecast_aware"]
    assert art["headline"]["fa_only_n"] == sib["headline"]["forecast_only"]
    assert art["headline"]["present_safe"] <= sib["headline"]["safe_present_perimeter"]
    assert art["gaps"]["forecast_minus_present_1km"] >= sib["headline"]["forecast_margin_over_present"]


# ---------------------------------------------------------------------------
# The dilation, tested against geometry rather than against itself
# ---------------------------------------------------------------------------


def test_the_buffer_is_a_disk_of_the_right_radius():
    """The buffer must be a EUCLIDEAN disk, not scipy's default cross.

    Graded at radius 3, NOT at the headline's radius 2, because a disk and a
    cross of radius 2 are the same set of cells.
    """
    mod = __import__(MODULE)

    haz = np.zeros((1, 21, 21), dtype=np.float32)
    haz[0, 10, 10] = 1.0

    m = mod.present_mask(haz, cell_m=500.0, buffer_m=1000.0)
    assert m[10, 12] and m[12, 10], "the buffer does not reach 2 cells on the axes"
    assert m[11, 11], "the buffer does not reach the near diagonal"
    assert not m[13, 10], "the buffer reaches further than it was asked to"
    assert not m[12, 12], "a square element over-buffered the far diagonal"

    m3 = mod.present_mask(haz, cell_m=500.0, buffer_m=1500.0)
    assert m3[12, 12], "a cross or diamond element under-buffers every diagonal"
    assert not m3[13, 12], "the buffer reaches beyond radius 3"
    assert not m3[13, 13], "a square element over-buffered the far diagonal"

    m0 = mod.present_mask(haz, cell_m=500.0, buffer_m=0.0)
    assert m0.sum() == 1 and m0[10, 10]


def test_a_sub_cell_buffer_rounds_up_rather_than_vanishing():
    mod = __import__(MODULE)
    haz = np.zeros((1, 11, 11), dtype=np.float32)
    haz[0, 5, 5] = 1.0
    m = mod.present_mask(haz, cell_m=500.0, buffer_m=100.0)
    assert m[5, 6], "a 100 m margin on a 500 m grid disappeared"


# ---------------------------------------------------------------------------
# Graded, not asserted: does the registry gate actually notice a wrong number?
# ---------------------------------------------------------------------------


def _scratch_repo(tmp_path: Path, art: dict) -> Path:
    scratch = tmp_path / "repo"
    (scratch / "data" / "processed").mkdir(parents=True)
    (scratch / "docs").mkdir()
    (scratch / "scripts").mkdir()
    (scratch / "data/processed" / ARTIFACT.name).write_text(
        json.dumps(art), encoding="utf-8")
    (scratch / "docs/NUMBERS.json").write_text(NUMBERS.read_text(encoding="utf-8"),
                                               encoding="utf-8")
    (scratch / "scripts" / REGISTRAR.name).write_text(
        REGISTRAR.read_text(encoding="utf-8"), encoding="utf-8")
    return scratch


def test_the_registrar_refuses_a_run_that_did_not_reproduce_the_committed_91(tmp_path):
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    art["committed_arm_reproduction"]["node_for_node_match"] = False
    scratch = _scratch_repo(tmp_path, art)
    r = subprocess.run([sys.executable, str(scratch / "scripts" / REGISTRAR.name)],
                       capture_output=True, text=True)
    assert r.returncode == 2, (
        "the registrar registered numbers from a run that did not reproduce the "
        f"committed headline. stdout={r.stdout!r} stderr={r.stderr!r}")
    assert (scratch / "docs/NUMBERS.json").read_text(encoding="utf-8") == \
        NUMBERS.read_text(encoding="utf-8")


def test_the_registrar_notices_a_changed_artifact_value(tmp_path):
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    art["headline"]["fa_only_recovered_by_present"] += 1
    scratch = _scratch_repo(tmp_path, art)
    r = subprocess.run([sys.executable, str(scratch / "scripts" / REGISTRAR.name),
                        "--check"], capture_output=True, text=True)
    assert r.returncode == 1, f"--check passed a moved number. stdout={r.stdout!r}"
    assert "ppb_recovered_1km" in r.stdout


def test_check_passes_on_the_real_tree():
    r = subprocess.run([sys.executable, str(REGISTRAR), "--check"],
                       capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stdout + r.stderr


def test_every_ppb_key_matches_the_artifact_and_names_the_build(art, numbers):
    keys = [k for k in numbers if k.startswith("ppb_")]
    assert len(keys) >= 70, keys
    from register_present_perimeter_arm_budgeted import dig
    for k in keys:
        e = numbers[k]
        assert e["source_file"] == str(ARTIFACT.relative_to(REPO)), k
        assert e["value"] == dig(art, e["json_path"]), k
        assert "BUDGET-CAPPED" in e["caveat"], k
        assert "NO forecast error" in e["caveat"], k
        assert "post-hoc maximum" in e["caveat"], k
        assert "예보는 필요 없다" in e["forbidden_phrasings"], k


# ---------------------------------------------------------------------------
# The doc may not drift from the artifact
# ---------------------------------------------------------------------------


def test_the_doc_quotes_the_registered_numbers(numbers):
    text = DOC.read_text(encoding="utf-8")
    for key in ("ppb_fa_only_n", "ppb_recovered_1km", "ppb_forecast_only_1km",
                "ppb_safe_naive", "ppb_safe_1km", "ppb_safe_forecast",
                "ppb_safe_present_best", "ppb_recovered_best", "ppb_n_origins",
                "ppb_forecast_only_refused_1km", "ppb_forecast_only_walled_1km",
                "ppb_refused_to_start_1km", "ppb_walled_off_1km",
                "ppb_gap_1km", "ppb_gap_best",
                "ppb_walled_escape_n_analysed", "ppb_walled_escape_through_burning",
                "ppb_walled_escape_through_never_burning"):
        value = numbers[key]["value"]
        assert key in text, f"{key} is not named in {DOC.name}"
        assert str(value) in text, f"{key} = {value} is not in {DOC.name}"


def test_the_doc_s_sweep_table_matches_the_artifact(art):
    """Every row of §3's ladder table is re-read out of the artifact."""
    import re
    text = DOC.read_text(encoding="utf-8")
    body = text.split("## 3.", 1)[1].split("## 4.", 1)[0]
    seen = 0
    for line in body.splitlines():
        m = re.match(r"^\|\s*\**현재 화선 \+ ([\d.]+) km\b", line.strip())
        if not m:
            continue
        b = f"{float(m.group(1)) * 1000:.0f}"
        arm = art["arms_by_buffer_m"][b]
        cells = [c.strip().replace("*", "") for c in line.strip().strip("|").split("|")]
        assert [int(c) for c in cells[1:4]] == [
            arm["counts"]["present_safe"], arm["counts"]["present_enters"],
            arm["counts"]["present_no_route"]], line
        seen += 1
    # the 0-buffer row is spelled 「완충 없음」 and is checked separately
    assert seen == len(art["arms_by_buffer_m"]) - 1, seen
    row0 = art["arms_by_buffer_m"]["0"]["counts"]
    assert re.search(rf"완충 없음 \| {row0['present_safe']} \| {row0['present_enters']} "
                     rf"\| {row0['present_no_route']} \|", body), "the 0 km row drifted"


def test_the_doc_carries_the_limitation_that_makes_the_arm_an_upper_bound():
    text = DOC.read_text(encoding="utf-8")
    assert "상한" in text
    assert "참" in text and "화선" in text


def test_the_doc_names_the_decision_and_the_sibling_arm():
    """A reader must learn from this page that there are two builds and which
    one the author chose, or the pruned-graph 9 looks like a contradiction."""
    text = DOC.read_text(encoding="utf-8")
    assert "NH-032" in text and "C안" in text
    assert "present_perimeter_arm.md" in text
    assert "pp_uiseong_" in text
    assert "2026-09-12" in text


def test_the_forbidden_phrasing_is_registered_and_absent_from_the_doc(numbers):
    entry = numbers["ppb_forecast_only_1km"]
    assert entry["forbidden_phrasings"]
    text = DOC.read_text(encoding="utf-8")
    assert "금지 문장" in text
    assert "틀렸다, 0명이다" in text
    assert "기록이지 강제가 아니다" in text
