"""WFG-256 — the rotation null: is the 2.2x the shape, or not being a circle?

These tests exist because this result is easy to overstate in exactly one
direction, and it is not the direction the disc null's suite guards. The finding a
lap WANTS to write is 「our model gets the direction right, 1 of 24」; the finding
the artifact supports is that the overlap is not produced by irregularity —
together with the fact that most rotations of the model's own mask are a WORSE
opponent than a circle, and that `docs/disc_null.md` §4's centroid reading, which
says the model overshoots the fire worse than the stationary disc does, is
untouched. The second and third halves are the ones a later lap will quietly drop,
so they are pinned here, in the artifact, in the registry band and in the prose.

The suite grades five things: that the null re-derives from the committed inputs
under the rule the claim commit pre-registered; that the rule really has no free
parameter (the centre is the seed's, the shape and the count are the model's, the
angles are the pre-registered sweep); that the rasterisation residual is reported
and not resampled away; that every value the two documents quote is the artifact's;
and that neither the prose nor the registry lets this be spoken of as a validation,
as a test with a p-value, or as directional skill.

No clock, no timezone, no network, no file outside the repository.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
NPZ = REPO / "data/processed/routing_demo_canonical.npz"
ART = REPO / "data/processed/rotation_null_yeongdeok.json"
DISC_ART = REPO / "data/processed/disc_null_yeongdeok.json"
DOC = REPO / "docs/rotation_null.md"
DISC_DOC = REPO / "docs/disc_null.md"
CARD = REPO / "docs/auto/JUDGE_QA.md"
NUMBERS = REPO / "docs/NUMBERS.json"
PREFIX = "rn_yeongdeok_"


def _load_module(name: str):
    """`scripts/` is not a package, so import by location like the sibling suites."""
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ART.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def registry() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]


# --------------------------------------------------------------------------
# the rule, and that it has nothing to tune
# --------------------------------------------------------------------------

def test_the_sweep_is_the_pre_registered_one(art):
    """Every 15 degrees, 0 excluded. A different sweep is a different experiment."""
    rule = art["null_rule"]
    assert rule["angles_deg"] == list(range(15, 360, 15))
    assert rule["n_rotations"] == 23
    assert rule["angle_step_deg"] == 15
    assert rule["zero_excluded"] is True
    assert rule["free_parameters"] == 0
    assert rule["p_value_reported"] is False
    for s in art["slices"]:
        assert [r["angle_deg"] for r in s["rotations"]] == rule["angles_deg"]


def test_the_centre_is_the_seed_centroid_and_not_the_grid_or_the_observation(art):
    """The only centre that uses no information the model did not have."""
    z = np.load(NPZ, allow_pickle=True)
    seed = z["obs_stack"][0] > 0
    rr, cc = np.nonzero(seed)
    assert art["null_rule"]["centre_row_col"] == [round(float(rr.mean()), 4),
                                                  round(float(cc.mean()), 4)]
    # NOT the grid centre, and NOT the observed footprint's centroid.
    n_rows, n_cols = art["grid_shape"]
    assert art["null_rule"]["centre_row_col"] != [n_rows / 2, n_cols / 2]
    obs = z["obs_stack"][1] > 0
    orr, occ = np.nonzero(obs)
    assert art["null_rule"]["centre_row_col"] != [round(float(orr.mean()), 4),
                                                  round(float(occ.mean()), 4)]
    # It is the same centre the disc null uses, which is what makes the two
    # comparisons commensurable at all.
    disc = json.loads(DISC_ART.read_text(encoding="utf-8"))
    assert art["null_rule"]["centre_row_col"] == disc["null_rule"]["centre_row_col"]


def test_the_shape_and_the_cell_count_are_the_models_own(art):
    """If the rotation changed the shape, this would not be a rotation null."""
    z = np.load(NPZ, allow_pickle=True)
    haz = z["haz_stack"]
    for i, s in enumerate(art["slices"]):
        assert s["n_cells"] == int((haz[i] >= art["p_cut"]).sum())
        for r in s["rotations"]:
            assert r["target_cells"] == s["n_cells"]


def test_the_null_re_derives_from_the_committed_inputs(art):
    """The headline numbers come out of the committed npz, not out of memory."""
    mod = _load_module("measure_rotation_null")
    z = np.load(NPZ, allow_pickle=True)
    haz, obs = z["haz_stack"], z["obs_stack"]
    centre = tuple(art["null_rule"]["centre_row_col"])
    seed = obs[0] > 0
    h = art["headline"]
    i = [s["haz_time_min"] for s in art["slices"]].index(h["haz_time_min"])
    j = int(np.argmin(np.abs(z["obs_times"] - h["haz_time_min"])))
    model = haz[i] >= art["p_cut"]
    seen = obs[j] > 0
    for r in h["rotations"]:
        rot = mod.rotate_mask(model, centre, r["angle_deg"])
        assert int(rot.sum()) == r["achieved_cells"]
        bare_pred, bare_obs = rot & ~seed, seen & ~seed
        union = int((bare_pred | bare_obs).sum())
        iou = round(int((bare_pred & bare_obs).sum()) / union, 4)
        assert iou == r["seed_removed_iou"], f"{r['angle_deg']} degrees"


def test_the_scorer_is_the_disc_nulls_and_not_a_copy():
    """Two comparisons quoted in one breath must not have two scorers."""
    rot = _load_module("measure_rotation_null")
    disc = _load_module("measure_disc_null")
    # Not an identity check: loading a module twice by location produces two code
    # objects for one definition. What is asserted is that the rotation module's
    # scorer is DEFINED in the disc null's file, at the same line as the disc
    # null's own — i.e. there is one definition, not two that must be kept in step.
    assert rot._score.__code__.co_filename == str(REPO / "scripts/measure_disc_null.py")
    assert (rot._score.__code__.co_firstlineno
            == disc._score.__code__.co_firstlineno)
    src = (REPO / "scripts/measure_rotation_null.py").read_text(encoding="utf-8")
    assert "from measure_disc_null import" in src
    assert "def _score" not in src, "the scorer was copied into this script"


# --------------------------------------------------------------------------
# the rasterisation residual: reported, and not resampled away
# --------------------------------------------------------------------------

def test_every_rotation_reports_its_cell_count_residual(art):
    for s in art["slices"]:
        for r in s["rotations"]:
            assert r["cell_count_residual"] == r["achieved_cells"] - r["target_cells"]
            assert r["cell_count_residual_frac"] is not None
            assert "cells_pushed_off_grid" in r


def test_no_rotation_was_clipped_by_the_canvas(art):
    """If a rotation pushed the fire off the map, the spread would be an artefact."""
    for s in art["slices"]:
        assert s["max_cells_pushed_off_grid"] == 0


def test_the_lattice_exact_angles_are_lossless_and_are_not_the_winners(art):
    """The control for 「is the spread just rasterisation?」, and it says no.

    90, 180 and 270 degrees are exact permutations of a square grid, so their
    cell-count residual is 0. If rasterisation loss were producing the spread,
    those three would sit at the TOP. They sit at the bottom.
    """
    for s in art["slices"]:
        lat = s["lattice_exact_angles"]
        assert lat["angles_deg"] == [90, 180, 270]
        assert lat["cell_count_residuals"] == [0, 0, 0]
        all_ious = [r["iou"] for r in s["rotations"]]
        assert lat["iou_spread"]["max"] < max(all_ious), (
            "a lossless angle is the best rotation, so the spread may be "
            "rasterisation after all and this result must be re-derived")


def test_the_rotations_are_not_near_copies_of_the_true_orientation(art):
    """A spread built from near-identity masks would be tight for a trivial reason."""
    for s in art["slices"]:
        for r in s["rotations"]:
            assert r["iou_with_the_unrotated_core"] < 0.5, (
                f"{r['angle_deg']} degrees still overlaps the unrotated core more "
                "than half, so it is not an alternative orientation")


# --------------------------------------------------------------------------
# the result, including the half that does not flatter the model
# --------------------------------------------------------------------------

def test_the_headline_is_the_slice_the_disc_null_quotes(art):
    """Fixed before the run; a later re-choice would be the WFG-201 failure."""
    non_seed = [s for s in art["slices"] if not s["is_seed_slice"]]
    assert art["headline"]["time_gap_min"] == min(s["time_gap_min"] for s in non_seed)
    assert art["headline"]["haz_time_min"] == 360.0
    disc = json.loads(DISC_ART.read_text(encoding="utf-8"))
    assert art["headline"]["haz_time_min"] == disc["headline"]["haz_time_min"]


def test_the_rank_is_consistent_with_the_spread_it_is_a_rank_in(art):
    for s in art["slices"]:
        if s["is_seed_slice"]:
            continue
        q = s["seed_removed"]
        rank = q["unrotated_rank_by_iou"]
        assert rank["of"] == q["rotated_iou_spread"]["n"] + 1
        better = sum(1 for r in s["rotations"]
                     if r["seed_removed_iou"] > s["unrotated"]["seed_removed_iou"])
        assert rank["rank"] == better + 1
        assert rank["tied_with_it"] == sum(
            1 for r in s["rotations"]
            if r["seed_removed_iou"] == s["unrotated"]["seed_removed_iou"])


def test_the_disc_comparison_reads_the_committed_disc_artifact(art):
    """The opponent is the published number, not one recomputed differently here."""
    disc = json.loads(DISC_ART.read_text(encoding="utf-8"))
    by_time = {float(s["haz_time_min"]): s for s in disc["slices"]}
    for s in art["slices"]:
        if s["is_seed_slice"]:
            continue
        assert (s["seed_removed"]["disc_iou"]
                == by_time[s["haz_time_min"]]["seed_removed"]["disc"]["iou"])


def test_the_disc_comparison_is_decided_at_full_precision(art):
    """The reviewer's nail, pinned so it cannot grow back.

    The counts were first computed on IoUs already rounded to 4 dp, which made the
    720-minute slice read 3 where full precision says 4. This re-derives every
    count from the masks at full precision, with its own arithmetic, and it also
    asserts the disclosure: each slice names its nearest rotation's SIGNED margin,
    so a count that would flip on the fifth decimal is visible.
    """
    mod = _load_module("measure_rotation_null")
    z = np.load(NPZ, allow_pickle=True)
    haz, obs = z["haz_stack"], z["obs_stack"]
    centre = tuple(art["null_rule"]["centre_row_col"])
    seed = obs[0] > 0
    for i, s in enumerate(art["slices"]):
        if s["is_seed_slice"]:
            continue
        j = int(np.argmin(np.abs(z["obs_times"] - s["haz_time_min"])))
        model = haz[i] >= art["p_cut"]
        seen = obs[j] > 0
        bare_obs = seen & ~seed

        def iou(pred):
            union = int((pred | bare_obs).sum())
            return int((pred & bare_obs).sum()) / union if union else 0.0

        disc_full = iou(mod.disc_mask(model.shape, centre, int(model.sum())) & ~seed)
        # the published opponent is the committed 4 dp value, and the rebuild agrees
        assert round(disc_full, 4) == s["seed_removed"]["disc_iou"]
        rot_full = [iou(mod.rotate_mask(model, centre, d) & ~seed)
                    for d in art["null_rule"]["angles_deg"]]
        q = s["seed_removed"]
        assert q["rotations_beating_the_disc"] == sum(1 for v in rot_full if v > disc_full)
        assert q["rotations_not_beating_the_disc"] == sum(1 for v in rot_full if v <= disc_full)
        assert q["worst_rotation_beats_the_disc"] is (min(rot_full) > disc_full)
        assert q["unrotated_beats_the_disc"] is (iou(model & ~seed) > disc_full)
        # the near-tie disclosure
        closest = q["closest_rotation_to_the_disc"]
        k = min(range(len(rot_full)), key=lambda k: abs(rot_full[k] - disc_full))
        assert closest["angle_deg"] == art["null_rule"]["angles_deg"][k]
        assert closest["margin_over_the_disc"] == round(rot_full[k] - disc_full, 8)
        assert q["rotations_tied_with_the_disc_at_reported_precision"] == sum(
            1 for v in rot_full if round(v, 4) == s["seed_removed"]["disc_iou"])


def test_the_page_discloses_where_the_count_nearly_flips(art, doc):
    """A count that turns on the fifth decimal is named on the page, not buried."""
    assert "### 3b." in doc
    for s in art["slices"]:
        if s["is_seed_slice"]:
            continue
        margin = s["seed_removed"]["closest_rotation_to_the_disc"]["margin_over_the_disc"]
        if abs(margin) < 1e-3:
            assert str(margin) in doc, (
                f"slice {s['haz_time_min']:.0f} has a margin of {margin} and the "
                "page does not say so")
    # the headline's own margin, which is what makes 3-and-20 safe to quote
    assert str(art["headline"]["seed_removed"]["closest_rotation_to_the_disc"]
               ["margin_over_the_disc"]) in doc


def test_the_inconvenient_half_is_in_the_artifact(art):
    """Most rotations of the model's own mask are WORSE than a circle.

    This is the half that stops the result being read as 「the shape is what wins」,
    and the half a later lap would drop. It is asserted from the artifact rather
    than trusted to prose.
    """
    for s in art["slices"]:
        if s["is_seed_slice"]:
            continue
        q = s["seed_removed"]
        assert (q["rotations_beating_the_disc"] + q["rotations_not_beating_the_disc"]
                == len(s["rotations"]))
        assert q["worst_rotation_beats_the_disc"] is False
        assert q["rotations_not_beating_the_disc"] > q["rotations_beating_the_disc"]


def test_no_seed_removed_figures_at_the_seed_slice(art):
    """Removing the shared seed from the t=0 masks empties them; a number that
    means nothing does not get reported or registered."""
    seed_slices = [s for s in art["slices"] if s["is_seed_slice"]]
    assert len(seed_slices) == 1
    assert "seed_removed" not in seed_slices[0]


# --------------------------------------------------------------------------
# registry and prose
# --------------------------------------------------------------------------

def test_every_registered_key_matches_the_artifact(registry, art):
    mod = _load_module("register_rotation_null")
    keys = [k for k in registry if k.startswith(PREFIX)]
    assert keys, "no rotation-null keys registered"
    for suffix, path, _unit, _deriv in mod.FIGURES + mod.slice_figures(art):
        key = PREFIX + suffix
        assert key in registry, f"{key} is not registered"
        assert registry[key]["value"] == mod._dig(art, path)


def test_the_caveat_travels_with_every_key(registry):
    """A key that loses its band can be quoted as a validation. None may."""
    for k in [k for k in registry if k.startswith(PREFIX)]:
        band = registry[k].get("caveat") or ""
        assert "NOT A TEST" in band and "NOT A DECOMPOSITION" in band
        assert "IT DOES NOT SAY THE MODEL GETS THE DIRECTION RIGHT" in band
        # The three facts a quote must not be separated from.
        assert "20 of the 23" in band
        assert "5.34" in band and "2.266" in band, (
            "the centroid finding must travel with the rank")
        assert "DOES NOT PRESERVE THE CELL COUNT" in band
        assert "AT FULL PRECISION ON BOTH SIDES" in band, (
            "the band must say where a beats/does-not-beat count is decided")
        assert registry[k].get("forbidden_phrasings")


def test_the_forbidden_phrasings_are_registered_and_absent_from_the_prose(registry):
    mod = _load_module("register_rotation_null")
    for k in [k for k in registry if k.startswith(PREFIX)]:
        assert registry[k]["forbidden_phrasings"] == mod.FORBIDDEN
    prose = (DOC.read_text(encoding="utf-8") + DISC_DOC.read_text(encoding="utf-8")
             + CARD.read_text(encoding="utf-8"))
    for phrase in mod.FORBIDDEN:
        assert phrase not in prose, f"{phrase!r} is registered as forbidden and is in the prose"


def test_the_doc_states_the_numbers_the_artifact_holds(doc, art):
    """Every figure the prose quotes is the artifact's, not a remembered one."""
    h = art["headline"]
    q = h["seed_removed"]
    for value in (h["n_cells"], h["unrotated"]["seed_removed_iou"], h["unrotated"]["iou"],
                  q["rotated_iou_spread"]["min"], q["rotated_iou_spread"]["median"],
                  q["rotated_iou_spread"]["max"], q["disc_iou"],
                  q["worst_rotation_over_disc"], q["rotations_beating_the_disc"],
                  q["rotations_not_beating_the_disc"],
                  h["rotated_iou_spread"]["max"], h["rotated_iou_spread"]["median"],
                  h["worst_cell_count_residual_frac"],
                  h["lattice_exact_angles"]["iou_spread"]["max"],
                  art["null_rule"]["centre_row_col"][0],
                  art["null_rule"]["centre_row_col"][1]):
        assert str(value) in doc, f"{value} is in the artifact but not in docs/rotation_null.md"
    # every off-seed slice's own four figures
    for s in art["slices"]:
        if s["is_seed_slice"]:
            continue
        for value in (s["unrotated"]["seed_removed_iou"],
                      s["seed_removed"]["rotated_iou_spread"]["min"],
                      s["seed_removed"]["rotated_iou_spread"]["max"],
                      s["seed_removed"]["disc_iou"]):
            assert str(value) in doc, (
                f"{value} (slice {s['haz_time_min']:.0f}) is missing from the doc")


def test_the_doc_says_what_it_does_not_show(doc):
    """The five things this measurement is not, in the words that keep it honest."""
    assert "## 5. What this does NOT show" in doc
    for needed in ("not a decomposition",
                   "축은 맞고 거리는 과했다",
                   "No p-value",
                   "not ground truth",
                   "WFG-234"):
        assert needed in doc, f"{needed!r} is missing from docs/rotation_null.md"
    # The centroid finding must be restated here, not merely linked.
    assert "5.34" in doc and "2.266" in doc


def test_the_disc_null_page_carries_the_measured_spread(art):
    """The row's own definition of done: §5's qualitative claim gains numbers."""
    page = DISC_DOC.read_text(encoding="utf-8")
    assert "### 5b." in page
    q = art["headline"]["seed_removed"]
    for value in (q["rotated_iou_spread"]["max"], q["rotated_iou_spread"]["min"],
                  q["worst_rotation_over_disc"], q["rotations_beating_the_disc"],
                  q["rotations_not_beating_the_disc"]):
        assert str(value) in page, f"{value} is missing from docs/disc_null.md §5b"
    # §5 item 1 keeps its necessary-and-not-sufficient reading.
    assert "necessary** and not **sufficient" in page
    # and the centroid finding is not weakened anywhere on the page
    assert "방향은 아닙니다" in page


def test_the_card_carries_the_rank_and_the_half_that_qualifies_it(art):
    """Q36 is tier T0. If it gains the rank without the rest, it overstates."""
    card = CARD.read_text(encoding="utf-8")
    q = art["headline"]["seed_removed"]
    for value in (art["headline"]["unrotated"]["seed_removed_iou"],
                  q["rotated_iou_spread"]["max"],
                  q["unrotated_rank_by_iou"]["rank"],
                  q["rotations_beating_the_disc"],
                  q["rotations_not_beating_the_disc"]):
        assert str(value) in card, f"{value} is missing from docs/auto/JUDGE_QA.md Q36"
    # the three sentences that keep it from being read as directional skill
    assert "축은 맞고 거리는 과했다" in card
    assert "p값은 없습니다" in card
    # and the card must no longer tell the student this was never measured
    assert "그것이 모양 때문인지는 아직 재지 않았습니다" not in card
