"""WFG-260 — the claim 「the fair opponent needs no model at all」, bound to the array.

Why this file exists
--------------------
``paper/manuscript.md``'s Abstract and §4.5 say the present-perimeter opponent needs
no model at all, and ``docs/present_perimeter_yeongdeok.md`` §2 now says why: slice 0
of the canonical hazard field is the seeded FIRMS observation, so the opponent's
planning side is fed an observation and not a model output. That sentence is true
today and nothing in the repository was stopping it from quietly becoming false —
``scripts/build_canonical_hazard.py`` could be changed to seed the simulation
differently, or ``hazard.py``'s time bracket could start mixing slice 1 into
``prob_at(x, y, 0.0)``, and the claim would keep being printed in the manuscript and
on the page while the array underneath it no longer supported it.

So the assertions below read the committed array itself rather than the artifact's
summary of it wherever the claim depends on it, and the artifact and the registry
where the DOCUMENT depends on them.

⚠ What these tests do NOT check: that the observation is CORRECT (the canonical
field's envelope-coverage caveat is untouched), and anything at all about the
의성·안동 arm, which has a different input.

Graded by mutation, in this lap's own process, all three ways:
  * make ``haz_stack[0]`` non-binary -> ``test_slice_zero_is_a_binary_mask`` red;
  * flip one cell of ``haz_stack[0]`` -> ``test_slice_zero_is_exactly_the_observed_mask``
    red (and the count test stays GREEN, which is the point of comparing cell for
    cell rather than by count);
  * change the registered value -> ``test_the_registry_agrees_with_the_artifact`` red.

⚠ This file does NOT re-register the 249. ``obs_stack[0] > 0`` and ``haz_stack[0] >=
p_cut`` being the same 249 cells was established and registered one lap earlier by
``scripts/measure_disc_null.py`` (``dn_yeongdeok_t0min_n_cells``,
``dn_yeongdeok_seed_cells_in_model``) and stated in ``docs/disc_null.md`` §2. What is new
here is the component count and the binding of both to the array from this side.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
CANON_NPZ = REPO / "data/processed/routing_demo_canonical.npz"
ARTIFACT = REPO / "data/processed/present_perimeter_yeongdeok_slice0_2025.json"
DOC = REPO / "docs/present_perimeter_yeongdeok.md"
NUMBERS = REPO / "docs/NUMBERS.json"

#: The threshold the present-perimeter arm filters nodes with. Duplicated from
#: scripts/measure_slice0_is_observation.py on purpose: a test that imports the
#: constant it is checking cannot catch the constant changing.
P_CUT = 0.5

pytestmark = pytest.mark.skipif(
    not CANON_NPZ.exists(),
    reason="routing_demo_canonical.npz is not present in this checkout",
)


@pytest.fixture(scope="module")
def arrays() -> dict:
    z = np.load(CANON_NPZ)
    return {"haz": z["haz_stack"], "obs": z["obs_stack"], "times": z["haz_times"]}


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def test_slice_zero_is_the_field_at_the_departure_time(arrays):
    """The arms plan at t = 0, so the slice they plan on must be the t = 0 slice."""
    assert float(arrays["times"][0]) == 0.0, (
        "haz_times[0] is no longer 0.0, so prob_at(x, y, 0.0) is interpolating "
        "between slices instead of returning slice 0 exactly, and the "
        "present-perimeter arm's node filter is no longer reading one observed mask."
    )


def test_slice_zero_is_a_binary_mask(arrays):
    """An observation is a mask; a forward-simulated slice is a probability field.

    Slice 1 is compared alongside so the assertion says what a model output
    actually looks like on this grid rather than asserting it in the abstract.
    """
    values = np.unique(arrays["haz"][0])
    assert sorted(float(v) for v in values) == [0.0, 1.0], (
        "haz_stack[0] is no longer strictly binary (values: "
        f"{values[:8]}...). The paper's 「needs no model at all」 rests on slice 0 "
        "being the seeded FIRMS observation rather than a simulated field; a "
        "continuous slice 0 means build_canonical_hazard.py stopped seeding from "
        "snaps[0].cumulative_mask, and that claim must come out of "
        "paper/manuscript.md and docs/present_perimeter_yeongdeok.md §2 before "
        "anything else is done."
    )
    assert np.unique(arrays["haz"][1]).size > 100, (
        "haz_stack[1] is nearly binary too, so this file's contrast between an "
        "observed slice and a modelled one no longer distinguishes them and the "
        "binary test above has stopped being evidence of anything."
    )


def test_slice_zero_is_exactly_the_observed_mask(arrays):
    """Cell for cell, not by count: equal counts over different cells prove nothing."""
    burning = arrays["haz"][0] >= P_CUT
    observed = arrays["obs"][0] > 0
    assert (burning == observed).all(), (
        "haz_stack[0] >= %.1f is no longer the same SET OF CELLS as obs_stack[0] > 0 "
        "(%d vs %d cells, %d disagreeing). The present-perimeter opponent filters "
        "the walk graph on the first and the repository claims it is the second; if "
        "they have parted, the opponent is planning on something that is not the "
        "observation and 「needs no model at all」 is false."
        % (P_CUT, int(burning.sum()), int(observed.sum()),
           int((burning != observed).sum()))
    )


def test_the_artifact_matches_the_array(arrays, art):
    """The committed summary is re-derived here, not trusted."""
    burning = arrays["haz"][0] >= P_CUT
    m = art["measurements"]
    assert m["slice0_burning_cells"] == int(burning.sum())
    assert m["obs0_observed_cells"] == int((arrays["obs"][0] > 0).sum())
    assert m["slice0_equals_obs0_cell_for_cell"] is True
    assert m["p_cut"] == P_CUT


def test_the_registry_agrees_with_the_artifact(art):
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    # ⚠ The 249 is NOT registered under this prefix, on purpose: it is already
    # dn_yeongdeok_t0min_n_cells from scripts/measure_disc_null.py, and a third home
    # for one fact is what `ssotize` exists to prevent (WFG-260's reviewer). Both are
    # checked here, each against the artifact that owns it.
    pairs = {
        "ppy_yeongdeok_slice0_components_8conn":
            art["measurements"]["slice0_components_8conn"],
        "dn_yeongdeok_t0min_n_cells": art["measurements"]["slice0_burning_cells"],
    }
    for key, value in pairs.items():
        assert key in numbers, (
            f"{key} is not registered. Run the OWNING registrar additively — "
            "scripts/register_slice0_observation.py for ppy_yeongdeok_slice0_, "
            "scripts/register_disc_null.py for dn_yeongdeok_ — and never "
            "scripts/build_numbers.py wholesale, which drops other registrars' keys."
        )
        assert numbers[key]["value"] == value, (
            f"{key} is {numbers[key]['value']} in docs/NUMBERS.json and "
            f"{value} in the artifact."
        )


def test_the_qualification_travels_with_the_claim(art):
    """The component count cuts against the project's own word, so it is not optional.

    249 cells in 226 8-connected components is a detection scatter, not a mapped
    perimeter. A lap that registers the supporting number and drops the qualifying
    one has made the registry an advocate.
    """
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    band = numbers["ppy_yeongdeok_slice0_components_8conn"]["caveat"]
    for fragment in ("DETECTION SCATTER", "4-connectivity", "PLANNING SIDE ONLY"):
        assert fragment in band, (
            f"the caveat band on the component count no longer says {fragment!r}. "
            "That count qualifies the claim rather than supporting it, and the "
            "qualification is the reason it is registered at all."
        )
    assert art["measurements"]["slice0_components_4conn"] == 236, (
        "the 4-connected count changed; the caveat band names it as the reason the "
        "8-connected figure is convention-dependent and must be updated with it."
    )


def test_the_document_does_not_claim_the_scoring_side_is_model_free(art):
    """§5 item 6's oracle conclusion is TRUE and this row must not weaken it.

    The whole risk of WFG-260 is that a lap correcting the input sentence also
    softens the scoring sentence beside it, which would turn a correct piece of
    self-criticism into an overclaim in the project's favour.
    """
    doc = DOC.read_text(encoding="utf-8")
    assert "채점" in doc or "scored against" in doc, (
        "docs/present_perimeter_yeongdeok.md no longer says the arm is SCORED "
        "against the full forecast. That oracle is real, §5 item 6 is right about "
        "it, and WFG-260 corrected only the sentence about the arm's INPUT."
    )
