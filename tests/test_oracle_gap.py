"""WFG-125 — the planning field vs the observed footprint.

These tests exist because the claim in `docs/oracle_gap.md` is easy to overstate
by one word: it is a comparison of two committed arrays, and it becomes false the
moment it is read as a routing margin. So the suite grades three things — that
the artifact re-derives from the npz, that the prose agrees with the artifact,
and that neither the doc nor the registry lets the field comparison be spoken of
as a routing result.

No clock, no timezone, no network, no file outside the repository.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
NPZ = REPO / "data/processed/routing_demo_canonical.npz"
ART = REPO / "data/processed/oracle_gap_yeongdeok.json"
DOC = REPO / "docs/oracle_gap.md"
NUMBERS = REPO / "docs/NUMBERS.json"
PREFIX = "og_yeongdeok_"


@pytest.fixture(scope="module")
def art() -> dict:
    return json.loads(ART.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]


def test_the_artifact_re_derives_from_the_committed_npz(art):
    """Recompute every slice from the npz and demand the artifact matches.

    This is the whole warrant for the document: the numbers are two array
    comparisons, so a test that cannot reproduce them from the arrays is not
    testing anything.
    """
    z = np.load(NPZ, allow_pickle=True)
    haz, obs = z["haz_stack"], z["obs_stack"]
    haz_times, obs_times = z["haz_times"], z["obs_times"]
    p_cut = art["p_cut"]

    assert len(art["slices"]) == haz.shape[0]
    for i, row in enumerate(art["slices"]):
        j = int(np.argmin(np.abs(obs_times - haz_times[i])))
        pred, seen = haz[i] >= p_cut, obs[j] > 0
        inter = int((pred & seen).sum())
        union = int((pred | seen).sum())
        assert row["predicted_cells"] == int(pred.sum())
        assert row["observed_cells"] == int(seen.sum())
        assert row["intersection_cells"] == inter
        assert row["false_alarm_cells"] == int(pred.sum()) - inter
        assert row["missed_cells"] == int(seen.sum()) - inter
        assert row["iou"] == pytest.approx(inter / union, abs=5e-5)


def test_the_headline_is_the_best_time_matched_slice_and_not_the_last(art):
    """t=0 agrees by construction and the last slice is 285 minutes off.

    Quoting either would flatter the result. The headline must be the pair with
    the smallest time gap among the slices that are not the shared seed.
    """
    rest = art["slices"][1:]
    best = min(rest, key=lambda s: s["time_gap_min"])
    assert art["headline"]["haz_time_min"] == best["haz_time_min"]
    assert art["headline"]["time_gap_min"] == min(s["time_gap_min"] for s in rest)
    assert art["slices"][0]["iou"] == 1.0, "t=0 should be the shared seed"
    assert art["headline"]["time_gap_min"] < art["last_slice"]["time_gap_min"]


def test_both_stacks_are_cumulative(art):
    """The decomposition reads each slice as a footprint-to-date.

    If either stack stopped being monotone the false-alarm/miss split would mean
    something else, so the artifact records the check and this pins it.
    """
    assert art["stacks_are_cumulative"] == {"haz": True, "obs": True}


def test_every_registered_key_matches_the_artifact(registry, art):
    keys = [k for k in registry if k.startswith(PREFIX)]
    # 10 headline keys + 3 per-slice keys on each of the 5 slices.
    assert len(keys) == 25, f"expected 25 {PREFIX}* keys, found {len(keys)}"
    for k in keys:
        entry = registry[k]
        cur = art
        for part in entry["json_path"].split("."):
            cur = cur[int(part)] if isinstance(cur, list) else cur[part]
        assert entry["value"] == cur, f"{k} is stale against the artifact"


def test_the_time_gap_is_registered_so_it_cannot_be_dropped(registry):
    """The 27-minute gap is the residual unfairness of the comparison.

    A reader who gets the IoU without the gap has been told the two fields were
    compared at the same moment, which is not true.
    """
    assert registry[PREFIX + "time_gap_min"]["value"] > 0


def test_the_doc_states_the_numbers_the_artifact_holds(art):
    text = DOC.read_text(encoding="utf-8")
    h = art["headline"]
    for field in ("predicted_cells", "observed_cells", "intersection_cells",
                  "false_alarm_cells", "missed_cells"):
        assert f"**{h[field]}**" in text, f"{field} ({h[field]}) is not in the doc"
    assert f"**{h['iou']:.3f}**" in text
    assert f"**{h['time_gap_min']:.0f} minutes**" in text


def test_the_doc_says_what_it_does_not_show(art):
    """CHARTER §4 step 4: a docs/<topic>.md states caveats and what it does NOT show."""
    text = DOC.read_text(encoding="utf-8")
    assert "## 7. What this does NOT show" in text
    # The three limits that make the result honest rather than a headline.
    assert "produces no margin" in text
    assert "detection_floor" in text
    assert "not a new performance claim" in text.lower()


@pytest.mark.parametrize("claim", [
    "42 of 458",
    "91 of 368",
])
def test_the_doc_does_not_restate_a_headline_margin_as_this_run_s_result(claim):
    """The document may NAME the committed numbers as untouched; it may not
    present one as something this run measured.

    Graded by mutation: a sentence attributing either count to this comparison
    should fail here.
    """
    text = DOC.read_text(encoding="utf-8")
    for line in text.splitlines():
        if claim in line:
            assert any(w in line for w in ("untouched", "scanned on", "headline")), (
                f"{claim!r} appears in a line that does not mark it as a "
                f"pre-existing committed figure: {line!r}")


def test_the_forbidden_phrasings_are_registered_and_absent_from_the_doc(registry):
    """A field comparison read as a routing result is the one way this misleads."""
    keys = [k for k in registry if k.startswith(PREFIX)]
    text = DOC.read_text(encoding="utf-8").lower()
    for k in keys:
        forbidden = registry[k]["forbidden_phrasings"]
        assert "the forecast is useless" in forbidden
        assert "this measures what the model buys" in forbidden
        for phrase in forbidden:
            # The doc quotes none of them; it says the opposite of each.
            assert phrase.lower() not in text, f"{k}: doc contains {phrase!r}"


def test_the_uiseong_field_has_no_observation_stack():
    """§7's last bullet is a live claim about a committed file, so it is graded.

    If a later lap adds obs_stack to the 의성·안동 hazard npz, this test goes red
    and the document's 'not currently possible' sentence must be rewritten —
    which is the point.
    """
    p = REPO / "data/processed/hazard_uiseong_andong_2025.npz"
    if not p.exists():
        pytest.skip("hazard_uiseong_andong_2025.npz is not in this checkout")
    with np.load(p, allow_pickle=True) as z:
        assert "obs_stack" not in z.files
