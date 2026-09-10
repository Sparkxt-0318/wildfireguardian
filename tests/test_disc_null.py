"""WFG-228 — the area-matched disc null for the IoU 0.394 headline.

These tests exist because this result is easy to overstate in exactly one
direction. The finding a lap WANTS to write is 「our model beats the null 2.5 to
1」; the finding the artifact actually supports is that plus 「and by centre of
mass it overshoots the fire worse than the null does」. The second half is the
half a later lap will quietly drop, so it is pinned here, in the artifact and in
the prose, three separate ways.

The suite grades four things: that the null re-derives from the committed npz
under the rule the claim commit pre-registered; that the rule really has no free
parameter to tune (the centre is the seed's, and the area is the model's); that
the prose agrees with the artifact including the inconvenient half; and that
neither the doc nor the registry lets the comparison be spoken of as directional
skill or as a validation.

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
ART = REPO / "data/processed/disc_null_yeongdeok.json"
DOC = REPO / "docs/disc_null.md"
GAP_DOC = REPO / "docs/oracle_gap.md"
NUMBERS = REPO / "docs/NUMBERS.json"
PREFIX = "dn_yeongdeok_"


def _load_module(name: str):
    """`scripts/` is not a package, so import by location like the sibling suites."""
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ART.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# the null re-derives, under the rule that was fixed before the answer was seen
# --------------------------------------------------------------------------

@pytest.mark.skipif(not NPZ.exists(), reason="canonical npz not in this clone")
def test_the_artifact_re_derives_from_the_committed_npz(art):
    """Recompute every slice from the npz and demand the artifact's own numbers."""
    mod = _load_module("measure_disc_null")
    fresh = mod.measure(NPZ, art["p_cut"])
    assert len(fresh["slices"]) == len(art["slices"])
    for got, want in zip(fresh["slices"], art["slices"], strict=True):
        assert got["disc"]["iou"] == want["disc"]["iou"]
        assert got["model"]["iou"] == want["model"]["iou"]
        assert got["n_cells"] == want["n_cells"]
        assert got["direction"] == want["direction"]


@pytest.mark.skipif(not NPZ.exists(), reason="canonical npz not in this clone")
def test_the_disc_is_area_matched_to_the_model_exactly_not_approximately(art):
    """The area match IS the null: if it drifts, the comparison stops being one."""
    z = np.load(NPZ, allow_pickle=True)
    haz = z["haz_stack"]
    for i, s in enumerate(art["slices"]):
        model_cells = int((haz[i] >= art["p_cut"]).sum())
        assert s["n_cells"] == model_cells
        assert s["model"]["predicted_cells"] == model_cells
        assert s["disc"]["predicted_cells"] == model_cells
        # Same area against the same observation means the same size_ratio; if
        # these ever differ, the two masks are not area-matched after all.
        assert s["model"]["size_ratio"] == s["disc"]["size_ratio"]


@pytest.mark.skipif(not NPZ.exists(), reason="canonical npz not in this clone")
def test_the_centre_is_the_seed_both_stacks_agree_on(art):
    """The centre is neutral only because the two stacks agree at t=0."""
    z = np.load(NPZ, allow_pickle=True)
    seed_haz = z["haz_stack"][0] >= art["p_cut"]
    seed_obs = z["obs_stack"][0] > 0
    assert (seed_haz == seed_obs).all(), (
        "the t=0 slices no longer agree, so the seed centroid takes information "
        "from one side of the comparison and the null is no longer neutral")
    assert art["null_rule"]["seed_stacks_agree"] is True
    assert art["null_rule"]["seed_cells"] == int(seed_obs.sum())
    rr, cc = np.nonzero(seed_obs)
    assert art["null_rule"]["centre_row_col"] == [
        round(float(rr.mean()), 4), round(float(cc.mean()), 4)]
    assert art["null_rule"]["free_parameters"] == 0


@pytest.mark.skipif(not NPZ.exists(), reason="canonical npz not in this clone")
def test_the_disc_mask_is_deterministic_and_the_right_size(art):
    """Two builds of the same disc are the same mask, cell for cell."""
    mod = _load_module("measure_disc_null")
    shape = tuple(art["grid_shape"])
    centre = tuple(art["null_rule"]["centre_row_col"])
    for n in (249, 692, 952, 1036):
        a = mod.disc_mask(shape, centre, n)
        b = mod.disc_mask(shape, centre, n)
        assert int(a.sum()) == n
        assert (a == b).all()


def test_no_mask_is_clipped_by_the_canvas(art):
    """A clipped disc is a half-disc, and the rule would not have run as written."""
    for s in art["slices"]:
        assert s["disc_touches_grid_border"] is False
        assert s["model_touches_grid_border"] is False


# --------------------------------------------------------------------------
# the inconvenient half, pinned
# --------------------------------------------------------------------------

def test_the_centroid_overshoot_is_what_the_artifact_says(art):
    """The load-bearing corrective: the DISC's centre of mass beats the model's.

    docs/disc_null.md §4 and docs/oracle_gap.md §4c both tell the reader that the
    IoU gap is NOT directional skill, and the evidence is this inequality. If a
    rebuild ever reverses it, both documents become false and must be rewritten
    rather than left standing, so this fails loudly instead of drifting.
    """
    h = art["headline"]["direction"]
    assert h["disc_to_observed_cells"] < h["model_to_observed_cells"], (
        "the model's centre of mass is now closer to the observation than the "
        "disc's; docs/disc_null.md §4 and docs/oracle_gap.md §4c say the "
        "opposite and must be rewritten")
    assert h["seed_to_model_cells"] > h["seed_to_observed_cells"], (
        "the model no longer overshoots; the 'overshoot' wording is now wrong")


def test_the_model_clears_the_null_at_every_slice(art):
    """The headline finding, stated as the artifact's own inequality.

    Both ways: as scored, AND with the shared seed removed. The second is the
    one that matters — if the finding only survives with the model's free
    initial condition included, it is not a finding.
    """
    for s in art["slices"]:
        if s["is_seed_slice"]:
            continue
        assert s["model"]["iou"] > s["disc"]["iou"]
        assert s["iou_delta_model_minus_disc"] > 0
        bare = s["seed_removed"]
        assert bare["model"]["iou"] > bare["disc"]["iou"], (
            "the model no longer clears the null once its free seed is removed; "
            "docs/disc_null.md §3c is the claim that fails first")
        assert bare["iou_ratio_model_over_disc"] < s["iou_ratio_model_over_disc"], (
            "removing the shared seed no longer costs the model anything, so the "
            "asymmetry §3c is built on has gone")


@pytest.mark.skipif(not NPZ.exists(), reason="canonical npz not in this clone")
def test_the_seed_asymmetry_is_real_and_is_the_model_s_advantage(art):
    """§3c's mechanism: the model gets all 249 seed cells free, the disc does not.

    This is the defect the row did not see and the lap did not see; the row's
    independent reviewer did. If a rebuild ever makes the two masks inherit the
    seed equally, §3c stops being true and must be rewritten rather than left.
    """
    z = np.load(NPZ, allow_pickle=True)
    seed = z["obs_stack"][0] > 0
    n_seed = int(seed.sum())
    for s in art["slices"]:
        if s["is_seed_slice"]:
            continue
        bare = s["seed_removed"]
        assert bare["seed_cells_in_model"] == n_seed, (
            "the model no longer contains the whole seed by construction")
        assert bare["seed_cells_in_disc"] < n_seed, (
            "the disc now inherits the whole seed too, so there is no asymmetry")


def test_the_docs_carry_the_seed_removed_figures_beside_the_raw_ones(art, doc):
    """2.5360 is not quotable alone. Both pages must show both."""
    bare = art["headline"]["seed_removed"]
    gap = GAP_DOC.read_text(encoding="utf-8")
    for page, name in ((doc, "docs/disc_null.md"), (gap, "docs/oracle_gap.md")):
        for value in (bare["model"]["iou"], bare["disc"]["iou"],
                      bare["iou_ratio_model_over_disc"]):
            assert str(value) in page, f"{value} (seed removed) is missing from {name}"


def test_the_headline_is_the_slice_the_oracle_gap_doc_quotes(art):
    """Fixed before the run; a later re-choice would be the WFG-201 failure."""
    non_seed = [s for s in art["slices"] if not s["is_seed_slice"]]
    assert art["headline"]["time_gap_min"] == min(s["time_gap_min"] for s in non_seed)
    assert art["headline"]["haz_time_min"] == 360.0
    # NOT the IoU maximum — the selection rule is time, not score.
    assert art["headline"]["model"]["iou"] != max(s["model"]["iou"] for s in non_seed)


# --------------------------------------------------------------------------
# registry and prose
# --------------------------------------------------------------------------

def test_every_registered_key_matches_the_artifact(registry, art):
    mod = _load_module("register_disc_null")
    keys = [k for k in registry if k.startswith(PREFIX)]
    assert keys, "no disc-null keys registered"
    for suffix, path, _unit, _deriv in mod.FIGURES + mod.slice_figures(art):
        key = PREFIX + suffix
        assert key in registry, f"{key} is not registered"
        assert registry[key]["value"] == mod._dig(art, path)


def test_the_caveat_travels_with_every_key(registry):
    """A key that loses its band can be quoted as a validation. None may."""
    keys = [k for k in registry if k.startswith(PREFIX)]
    for k in keys:
        band = registry[k].get("caveat") or ""
        assert "FLOOR" in band and "NOT A VALIDATION" in band
        # The facts a quote must not be separated from.
        assert "NOT DIRECTIONAL SKILL" in band
        assert "2.266" in band and "5.34" in band
        assert "INFLATED BY AN INITIAL CONDITION" in band
        assert "2.2044" in band, "the seed-removed ratio must travel with the raw one"
        assert registry[k].get("forbidden_phrasings")


def test_the_forbidden_phrasings_are_registered_and_absent_from_both_docs(registry):
    mod = _load_module("register_disc_null")
    keys = [k for k in registry if k.startswith(PREFIX)]
    for k in keys:
        assert registry[k]["forbidden_phrasings"] == mod.FORBIDDEN
    both = DOC.read_text(encoding="utf-8") + GAP_DOC.read_text(encoding="utf-8")
    for phrase in mod.FORBIDDEN:
        assert phrase not in both, f"{phrase!r} is registered as forbidden and is in a doc"


def test_the_doc_states_the_numbers_the_artifact_holds(doc, art):
    """Every figure the prose quotes is the artifact's, not a remembered one."""
    h = art["headline"]
    for value in (h["model"]["iou"], h["disc"]["iou"],
                  h["iou_delta_model_minus_disc"], h["iou_ratio_model_over_disc"],
                  h["disc"]["intersection_cells"], h["disc"]["false_alarm_cells"],
                  h["disc"]["missed_cells"], h["disc_vs_model_iou"]):
        assert str(value) in doc, f"{value} is in the artifact but not in the doc"
    # The four displacements §4's table is built from. `seed_to_disc` is
    # deliberately NOT required: it is ~0 by construction (the disc is centred on
    # the seed) and carries no finding, so demanding it in prose would be asking
    # the page to print a tautology.
    for field in ("seed_to_observed_cells", "seed_to_model_cells",
                  "model_to_observed_cells", "disc_to_observed_cells"):
        value = h["direction"][field]
        assert str(value) in doc or f"{value:.3f}" in doc, (
            f"{field}={value} is in the artifact but not in the doc")


def test_every_radius_the_doc_quotes_is_the_slice_it_names(art, doc, registry):
    """The number that broke `make verify`'s collision gate, now gated here too.

    An earlier draft wrote the LARGEST disc radius (18.162, the t=720 slice) and
    the only registered radius was the HEADLINE's (17.355), so the doc asserted a
    value the registry contradicted. Both are registered per slice now; this
    keeps the doc's 'largest' claim honest against the artifact.
    """
    radii = [s["disc_radius_cells"] for s in art["slices"]]
    assert str(max(radii)) in doc, "the doc's 'largest disc radius' is not the largest"
    for i, s in enumerate(art["slices"]):
        tag = f"t{int(s['haz_time_min'])}min"
        key = f"{PREFIX}{tag}_disc_radius_cells"
        assert key in registry, f"{key} is not registered"
        assert registry[key]["value"] == s["disc_radius_cells"]


def test_the_doc_says_what_it_does_not_show(doc):
    """The five limits that make the number quotable at a booth."""
    assert "floor" in doc.lower() and "not a competitive baseline" in doc.lower()
    assert "necessary" in doc and "sufficient" in doc
    assert "detection_floor.md" in doc
    assert "WFG-234" in doc, "the persistence null must be filed, not implied"
    assert "produces no routing margin" in doc or "no margin" in doc.lower()


def test_the_doc_refuses_the_row_s_own_interpretation(doc):
    """CHARTER §3.5: the correction is written down, not silently applied.

    The WFG-228 row asserts the gap is 'directional skill and nothing else'. The
    lap disagreed and pre-registered the disagreement. If a later edit smooths
    that out, the page stops recording that its own brief was wrong.
    """
    assert "directional skill and nothing else" in doc, (
        "the row's claim must be quoted before it is refused")
    assert "overshoot" in doc.lower()
    assert "shape and extent" in doc.lower()


def test_the_oracle_gap_doc_carries_both_numbers_side_by_side():
    """WFG-228's 'done when': §4c exists and puts the two IoUs together."""
    gap = GAP_DOC.read_text(encoding="utf-8")
    art_doc = json.loads(ART.read_text(encoding="utf-8"))
    h = art_doc["headline"]
    assert "### 4c." in gap
    assert str(h["model"]["iou"]) in gap and str(h["disc"]["iou"]) in gap
    assert str(h["iou_ratio_model_over_disc"]) in gap
    assert "not directional skill" in gap.lower()
    assert "docs/disc_null.md" in gap
