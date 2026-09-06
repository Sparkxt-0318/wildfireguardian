"""WFG-121 — the fair-opponent line travels with the headline, and no lap can put
the closed limitation back.

Three things can rot here between laps, and each has bitten this repository before:

1. A limitation that has been closed goes on being spoken. Until 2026-09-05 the booth
   script told the student to say the present-perimeter comparison had not been run.
   It has (WFG-114). The same shape as WFG-109, where a withdrawn sentence survived in
   the file the judged screen is generated from, so the guard is the same shape too:
   the exact retired strings, asserted absent.
2. The headline's contrast loses the word that makes it fair. `fire-blind` is not
   decoration; without it 「91 of 368」 reads as a comparison against a router that
   already avoids the fire, which is a stronger opponent than the one measured.
3. A margin figure that the author has not chosen yet reaches the spoken script. While
   NH-032 is open, no number answers 「what is the forecast worth against a present-aware
   planner」, so none may be spoken.

And the doc's own table is checked against `docs/NUMBERS.json`, because a table of
registry keys that no longer matches the registry is the WFG-057 failure.

Nothing here reads the clock, the timezone, the network or a file outside the
repository (CHARTER §4b).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs/fair_opponent_line.md"
SCRIPT = REPO / "docs/auto/DEMO_SCRIPT_5MIN.md"
BANK = REPO / "docs/auto/JUDGE_QA.md"
NUMBERS = REPO / "docs/NUMBERS.json"
NEEDS_HUMAN = REPO / "docs/auto/NEEDS_HUMAN.md"

# The clauses WFG-114 made false. Retired 2026-09-06; see docs/fair_opponent_line.md §2.
RETIRED = [
    "지금 불만 피하는 경로와의 비교는\n아직 돌리지 않았습니다",
    "WFG-104가 그것을 씁니다",
]


@pytest.fixture(scope="module")
def script() -> str:
    return SCRIPT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def doc() -> str:
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def registry() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]


def test_the_closed_limitation_is_not_spoken_anywhere(script: str) -> None:
    """WFG-114 ran the comparison; saying otherwise understates the work to a judge.

    Graded by putting either string back and watching this go red.
    """
    for dead in RETIRED:
        assert dead not in script, (
            f"docs/auto/DEMO_SCRIPT_5MIN.md still carries the retired clause "
            f"{dead!r}. The present-perimeter comparison ran on 2026-09-05 "
            f"(WFG-114, docs/present_perimeter_arm.md) and the Q&A card is "
            f"JUDGE_QA.md Q19. See docs/fair_opponent_line.md §2.")


def test_the_script_says_the_comparison_has_been_run(script: str) -> None:
    """The correction is present, not merely the old sentence absent."""
    assert "docs/present_perimeter_arm.md" in script, (
        "the booth script no longer points the student at the arm that answers "
        "「why not just avoid where the fire is now?」")
    assert "fair_opponent_line.md" in script, (
        "the booth script does not point at the file that holds the line it is "
        "supposed to speak (docs/fair_opponent_line.md)")


def test_every_registry_key_the_doc_names_is_registered(doc: str, registry: dict) -> None:
    """The doc quotes keys rather than cells now; the keys must still exist.

    Graded by renaming one key in the doc.
    """
    named = set(re.findall(r"`(pp_uiseong_\w+|mr_uiseong_\w+)`", doc))
    assert named, "docs/fair_opponent_line.md names no registry key at all"
    missing = sorted(k for k in named if k not in registry)
    assert not missing, (
        f"docs/fair_opponent_line.md names keys that docs/NUMBERS.json does not "
        f"hold: {missing}")


def test_the_headline_contrast_keeps_the_word_fire_blind(script: str, doc: str) -> None:
    """Every surface that prints the contrast also prints what it is against.

    The bank's own copy of this is JUDGE_QA.md Q19 and is checked below.
    """
    assert "불을 전혀 보지 않는" in script, (
        "the booth script prints the 91-of-368 contrast without saying that its "
        "control is fire-blind; that is the overclaim critic #17 caught")
    assert "fire-blind" in doc


def test_the_bank_card_for_the_present_perimeter_question_exists(  ) -> None:
    """The script now tells the student the card exists, so it must."""
    bank = BANK.read_text(encoding="utf-8")
    assert "docs/present_perimeter_arm.md" in bank, (
        "docs/auto/DEMO_SCRIPT_5MIN.md tells the student the Q&A bank carries the "
        "present-perimeter card, and JUDGE_QA.md does not mention the arm at all")
    assert "불을 전혀 보지 않는" in bank


MARGIN_PHRASES = ("9곳", "27곳", "5곳", "19곳")


def test_no_contested_margin_reaches_the_booth_script(script: str) -> None:
    """NH-032 chooses between two defensible opponents; until then, no margin.

    Scoped to the WHOLE script, not only its '> ' lines. The lap that wrote this
    file first scoped it to spoken lines, and its reviewer defeated that in one
    mutation: the sentence a ⚠ note instructs the student to *say* is not itself
    a '> ' line, so a margin could be planted in the one place the script tells
    the student to read aloud and every guard stayed green.

    The script carries no do-not-say list of its own (that list lives in
    JUDGE_QA.md Q19), so a bare absence check is correct here.
    """
    if "## NH-032" not in NEEDS_HUMAN.read_text(encoding="utf-8"):
        pytest.skip("NH-032 is no longer in the ledger; the ban it carries has lapsed")

    for phrase in MARGIN_PHRASES:
        assert phrase not in script, (
            f"docs/auto/DEMO_SCRIPT_5MIN.md contains {phrase!r}. While NH-032 is "
            f"open no present-perimeter margin may reach the booth script, spoken "
            f"or instructed: two laps built the opponent differently and the author "
            f"has not chosen. See docs/fair_opponent_line.md §5.")


def test_the_sweep_table_is_not_restated_here(doc: str) -> None:
    """One table, one home, one gate.

    The buffer sweep lives in docs/present_perimeter_arm.md §4 and is already
    bound cell-by-cell to the artifact by
    tests/test_present_perimeter_arm.py::test_the_doc_s_sensitivity_table_matches_the_sweep.
    This file's first draft copied it, which is two tables drifting against one
    artifact — the WFG-057 shape, in the file whose whole purpose is to stop drift.
    It also copied it with two of six columns missing, so the reader could not
    reconstruct the 368 or see that the safe total spikes at one width.

    Graded by pasting any buffer row back into this doc.
    """
    rows = [ln for ln in doc.splitlines()
            if re.match(r"^\|\s*\**\s*[\d.]+\s*(m|km)\b", ln.strip())]
    assert not rows, (
        f"docs/fair_opponent_line.md restates the buffer sweep: {rows[:2]}. The "
        f"table belongs to docs/present_perimeter_arm.md §4 alone; quote its "
        f"location, not its cells.")
    assert "present_perimeter_arm.md" in doc, (
        "docs/fair_opponent_line.md does not name the document that owns the sweep")


def test_the_doc_does_not_claim_a_fixed_buffer_cannot_work(doc: str) -> None:
    """The overclaim this file shipped in its first draft, pinned out.

    On this fire a well-chosen fixed buffer nearly matches the forecast — the
    committed arm reaches 345 of 368 at 1 km against 354 — so 「no fixed buffer
    width works」 is false, and it was false in the direction that flattered the
    project. The claim that survives is about WHICH width, not whether any does.

    ⚠ Narrowed 2026-09-06 (WFG-127 (i)). This test used to *require* the string
    「not knowable on the day」, so the gate written to stop one overclaim was
    holding a second one in place: a five-point grid spaced by factors of two
    (250 m / 500 m / 1 km / 2 km / 3 km) cannot separate a spike at 1 km from a
    plateau an operator could aim at, so neither 「spike, not a plateau」 nor
    「nothing on the day tells you which width」 is recoverable from the run.
    Critic #23 found the prose; the prose fix failed here, which is how the gate
    was found. What replaces the requirement is the claim that IS carried: the
    failure changes kind across the widths, and the grid's resolution is stated.
    """
    # Markdown emphasis is stripped before the substring check. Without this,
    # 「a **spike**, not a plateau」 slips the ban purely because two asterisks
    # sit inside it, and a later reflow of the same line would trip the gate
    # for a reason that has nothing to do with the claim.
    doc = doc.replace("**", "").replace("*", "")
    for overclaim in ("no fixed buffer width works",
                      "The failure does not shrink with width",
                      "spike, not a plateau",
                      "not knowable on the day"):
        assert overclaim not in doc, (
            f"docs/fair_opponent_line.md asserts {overclaim!r}. The first two are "
            f"contradicted by the artifact's own buffer_sensitivity (safe_total "
            f"peaks at 1 km); the last two are finer-grained than a grid whose "
            f"points differ by factors of two. See §3 and WFG-127.")
    assert "single point" in doc and "factor of two" in doc, (
        "docs/fair_opponent_line.md no longer states the resolution limit that "
        "bounds every width claim it makes: the sweep's spacing is a factor of "
        "two, so it holds a single point in the region a 'which width' claim "
        "would be about (WFG-127 (i))")
    assert "change of kind" in doc, (
        "docs/fair_opponent_line.md has dropped the width finding that the run "
        "does carry, and that both builds of the opponent agree on: thin buffers "
        "send people through burning ground, wide ones strand them")


def test_the_concession_and_the_oracle_caveat_are_both_present(doc: str) -> None:
    """Two things a later lap would be tempted to trim, because both weaken the story.

    The concession: a well-chosen fixed buffer nearly matches the forecast here.
    The oracle: the sweep is graded on the same simulated field the forecast-aware
    arm plans on, so §3's shape is no better grounded than the margin it replaces.
    """
    assert "nearly matches the forecast" in doc, (
        "docs/fair_opponent_line.md has dropped the concession that a well-chosen "
        "fixed buffer nearly matches the forecast on this fire")
    assert "inherits the oracle" in doc, (
        "docs/fair_opponent_line.md has dropped the disclosure that its buffer "
        "finding is graded against the same simulated field the forecast-aware "
        "arm plans on (mandela, this lap's reviewer)")


def test_the_doc_names_the_value_collisions_it_contains(doc: str) -> None:
    """91 and 80 each mean two different things in this file.

    A judge who reads the 250 m row as the headline's 91 has been misled by the
    document rather than by a person, so the file must say so itself.
    """
    assert "mr_uiseong_future_aware_only_safe" in doc
    assert "pp_uiseong_w250m_burns" in doc
    section = doc.split("Two coincidences", 1)
    assert len(section) == 2, (
        "docs/fair_opponent_line.md no longer names the two repeated values in its "
        "own table (91 at 250 m is not the headline's 91; the two 80s are different "
        "quantities)")
