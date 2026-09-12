"""WFG-255: the footprint geometry measurement, and the claims made from it.

The tests that matter here are not「does ndimage.label work」. They are the three
ways this measurement could quietly become a lie:

1. someone quotes a component count as a property of the fire, when it is a
   reading of the connectivity rule (`test_the_count_is_a_reading_of_the_rule`);
2. someone writes a count of FIRES from it (`test_no_page_counts_fires`);
3. the page and the registry drift apart from the artifact.

Every test reads committed files only: no clock, no timezone, no network and no
file outside the repository.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
ART_DIR = REPO / "data" / "processed" / "footprint_components"
DOC = REPO / "docs" / "footprint_components.md"
NUMBERS = REPO / "docs" / "NUMBERS.json"
NPZ = REPO / "data" / "processed" / "routing_demo_canonical.npz"
PREFIX = "fc_yeongdeok_"


@pytest.fixture(scope="module")
def artifact() -> dict:
    files = sorted(ART_DIR.glob("footprint_components_*.json"))
    assert files, "no footprint-component artifact committed"
    return json.loads(files[-1].read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def registry() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]


def _headline_obs(artifact: dict) -> dict:
    t = artifact["headline"]["obs_time_min"]
    return next(e for e in artifact["observations"] if e["obs_time_min"] == t)


def test_the_artifact_re_derives_from_the_committed_array(artifact):
    """The whole point of the row is that a stranger can re-run it. Re-run it."""
    ndimage = pytest.importorskip("scipy.ndimage")
    z = np.load(NPZ, allow_pickle=True)
    obs, haz = z["obs_stack"], z["haz_stack"]
    s8 = np.ones((3, 3), dtype=bool)
    for entry in artifact["observations"]:
        i = int(np.argmin(np.abs(z["obs_times"] - entry["obs_time_min"])))
        mask = obs[i] > 0
        _, n = ndimage.label(mask, structure=s8)
        assert int(mask.sum()) == entry["n_cells"]
        assert n == entry["n_components_8conn"]
    for entry in artifact["forecast_cores"]:
        i = int(np.argmin(np.abs(z["haz_times"] - entry["haz_time_min"])))
        mask = haz[i] >= artifact["rule"]["p_cut"]
        _, n = ndimage.label(mask, structure=s8)
        assert int(mask.sum()) == entry["n_cells"]
        assert n == entry["n_components_8conn"]


def test_the_count_is_a_reading_of_the_rule(artifact):
    """The load-bearing claim of the whole page, asserted as a property.

    If a future change ever made the component count STABLE across the sweep,
    the page's headline ("the stability profile is the result, not a number")
    would silently become false while every individual number stayed correct.
    This test fails in that case, which is the only way the page can be wrong
    without any single figure being wrong.
    """
    e = _headline_obs(artifact)
    sweep = e["link_sweep"]
    assert e["n_components_4conn"] > e["n_components_8conn"], (
        "4-connectivity no longer disagrees with 8-connectivity on this mask, so "
        "the page's central claim needs re-deriving rather than re-wording")
    assert sweep["0"] > sweep["1"] > sweep["2"] >= sweep["4"], (
        f"the link sweep no longer collapses ({sweep}); the page says the same "
        "mask is many pieces or one depending on the rule, and that is now false")
    assert sweep["4"] == 1, "the mask no longer becomes one object at 2 km"


def test_the_dominant_piece_is_what_survives_every_rule(artifact):
    """`docs/disc_null.md`'s surviving 「reach」 reading rests on exactly this."""
    e = _headline_obs(artifact)
    assert e["largest_component_share"] > 0.5
    assert e["largest_component_cells"] > 4 * e["second_component_cells"]
    # The dominant piece is itself elongated: that is the reach claim's evidence.
    long_side = max(e["largest_component_span_km"])
    assert long_side > 40.0


def test_the_two_span_conventions_differ_by_exactly_one_cell(artifact):
    """WFG-255 was filed quoting the other convention; both must stay derivable."""
    cell_km = artifact["source"]["cell_m"] / 1000.0
    for e in artifact["observations"] + artifact["forecast_cores"]:
        if e.get("n_cells", 0) == 0:
            continue
        for a, b in zip(e["span_km"], e["centre_span_km"]):
            assert a - b == pytest.approx(cell_km)


def test_the_registry_matches_the_artifact(registry, artifact):
    keys = [k for k in registry if k.startswith(PREFIX)]
    assert keys, "no fc_yeongdeok_ keys registered"
    for k in keys:
        entry = registry[k]
        node = artifact
        for part in entry["json_path"].split("."):
            node = node[int(part)] if isinstance(node, list) else node[part]
        assert entry["value"] == node, f"{k} is stale against the artifact"


def test_every_registered_key_carries_the_rule_caveat(registry):
    """Caveat (1) is the one a later lap will be tempted to drop. Pin it."""
    keys = [k for k in registry if k.startswith(PREFIX)]
    for k in keys:
        caveat = registry[k].get("caveat", "")
        assert "READING OF A RULE" in caveat, (
            f"{k} lost the caveat that stops its count being quoted as a "
            "property of the fire")
        assert "NOT A COUNT OF FIRES" in caveat


def test_no_page_counts_fires(artifact):
    """The row's hardest constraint, checked on the pages this lap wrote.

    The geometry does NOT distinguish one fragmented fire from several, and the
    row forbids any count of fires being written from it.
    """
    banned = ["여러 개의 산불", "개의 산불이", "separate fires in the mask",
              "the mask contains", "fires in the footprint"]
    for page in (DOC, REPO / "docs" / "disc_null.md",
                 REPO / "docs" / "oracle_gap.md"):
        text = page.read_text(encoding="utf-8")
        for phrase in banned:
            # The doc quotes the forbidden phrase once, to forbid it.
            hits = text.count(phrase)
            allowed = 1 if (page == DOC and phrase == "여러 개의 산불") else 0
            assert hits == allowed, (
                f"{page.name} writes 「{phrase}」 {hits} times; WFG-255 measured "
                "geometry and this repository cannot tell a fragmented single "
                "perimeter from several fires")


def test_the_doc_states_what_it_does_not_show(artifact):
    text = DOC.read_text(encoding="utf-8")
    assert "## 6. What this does NOT show" in text
    # The three that are not negotiable.
    assert "detection field" in text
    assert "reading of a rule" in text
    assert "moves no IoU" in text
    assert artifact["what_this_does_not_show"], "the artifact dropped its caveats"


def test_the_arms_claim_was_narrowed_and_its_old_wording_kept():
    """HANDOFF §5 rule 7: a superseded wording is recorded, never deleted."""
    text = (REPO / "docs" / "disc_null.md").read_text(encoding="utf-8")
    assert "the arms the fire actually ran down" in text, (
        "the superseded wording was deleted rather than recorded")
    assert "the long band the fire was detected along" in text, (
        "the narrowed wording is missing")
    # and the live sentence is the narrowed one: the old spelling survives only
    # inside the paragraph that records the change.
    live = text.split("⚠ **「the long band the fire was detected along」")[0]
    assert "the arms the fire actually ran down" not in live, (
        "the old wording is still asserted as a live claim above the record")


def test_the_doc_never_quotes_a_count_without_its_rule():
    """A bare 「55 pieces」 is the failure mode the whole page exists to prevent."""
    text = DOC.read_text(encoding="utf-8")
    for m in re.finditer(r"\*\*55\*\*", text):
        window = text[max(0, m.start() - 400):m.end() + 400]
        assert ("connectiv" in window or "rule" in window
                or "pieces" in window), (
            "a bare 55 appears with no connectivity rule within 400 characters")
