"""WFG-233 — the two counts that describe the weak LOFO fold, and the sentence
that leaves this repository carrying them.

`docs/MODEL_CARD.md`'s 작품설명서 section ends with the one piece of text in this
repository written to be pasted into a document the judges receive. Until WFG-233 it
explained the 0.68 `gangneung_2023` fold with a FIRMS detection count (17) while the
same file's headline blockquote, its per-fire table and `docs/fold_sizes.md` explained
the same fold with a positive-cell count (8). Both numbers are true and they count
different things, so the defect was not a wrong value: it was that one word carried the
whole distinction, and neither number was registered, so `make verify` re-derived
neither and nothing stopped a later lap from swapping them back.

What these tests pin, and why each one is here rather than left to a reader:

1. Both keys exist, re-derive from their committed artifacts, and are NOT equal. If a
   rebuild ever makes them equal, the distinction this row exists for has collapsed and
   the failure should be loud rather than quiet.
2. The whole-fire detection count agrees with the second artifact that carries it. ⚠ This
   is a TRANSCRIPTION check and not corroboration, and the docstring says so because the
   first version of this file claimed otherwise and its independent reviewer blocked on
   it: `scripts/gk2a_detection.py` copies the record verbatim out of
   `firms_first_detection.json` (`rec["firms"] = firms.get(label)`), so the two agree by
   construction. It catches a hand-edit of one file and nothing more. It CANNOT catch a
   rebuild against a different event definition, and no independent second derivation of
   this count exists in the repository.
2b. The citation the author pastes is positional (`folds.0.positive_cells`) while the
   registrar resolves the fold by `fire_id`. Those two can drift apart silently, so index
   0 is pinned to `gangneung_2023` here — that binding is what makes the pasted citation
   true, and nothing else in the tree checks it.
3. The pasted sentence carries BOTH counts. A later lap that trims it back to one number
   fails here, which is the regression this row was filed for.
4. Neither key may be spoken of as the other. The forbidden phrasings are registered and
   checked, because the swap is a sentence, not a value.

No clock, no timezone, no network, no file outside the repository.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NUMBERS = REPO / "docs/NUMBERS.json"
MODEL_CARD = REPO / "docs/MODEL_CARD.md"
FOLD_SIZES = REPO / "docs/fold_sizes.json"
FIRMS_FIRST = REPO / "data/processed/detection/firms_first_detection.json"
GK2A_FLOOR = REPO / "data/processed/detection/gk2a_detection_floor.json"

PREFIX = "foldev_"
POSITIVES_KEY = PREFIX + "gangneung2023_fold_positive_cells"
DETECTIONS_KEY = PREFIX + "gangneung2023_firms_whole_fire_detections"
FIRE = "gangneung_2023"


def _load_registrar():
    """`scripts/` is not a package, so import by location like the sibling suites."""
    spec = importlib.util.spec_from_file_location(
        "register_fold_evidence", REPO / "scripts" / "register_fold_evidence.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def numbers() -> dict:
    return json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]


@pytest.fixture(scope="module")
def card_text() -> str:
    return MODEL_CARD.read_text(encoding="utf-8")


def _fold_row() -> dict:
    folds = json.loads(FOLD_SIZES.read_text(encoding="utf-8"))["folds"]
    for row in folds:
        if row["fire_id"] == FIRE:
            return row
    pytest.fail(f"docs/fold_sizes.json carries no fold named {FIRE!r}")


def test_both_keys_are_registered(numbers):
    for key in (POSITIVES_KEY, DETECTIONS_KEY):
        assert key in numbers, (
            f"{key} is missing from docs/NUMBERS.json. Re-run it: "
            "python scripts/register_fold_evidence.py")


def test_each_key_rederives_from_its_own_artifact(numbers):
    assert numbers[POSITIVES_KEY]["value"] == _fold_row()["positive_cells"]
    firms = json.loads(FIRMS_FIRST.read_text(encoding="utf-8"))
    assert numbers[DETECTIONS_KEY]["value"] == firms[FIRE]["n"]


def test_the_two_counts_are_not_the_same_number(numbers):
    """The whole row exists because these count different things.

    If a rebuild ever makes them equal, the sentence in MODEL_CARD.md stops
    distinguishing anything and the reader cannot tell which one they are holding.
    """
    positives = numbers[POSITIVES_KEY]["value"]
    detections = numbers[DETECTIONS_KEY]["value"]
    assert positives != detections, (
        f"the fold's positive cells and the whole-fire FIRMS detections are both "
        f"{positives}. They measure different things and agreeing is not a repair: "
        "check which artifact was rebuilt before touching the prose.")


def test_the_detection_count_agrees_with_the_second_artifact_that_carries_it(numbers):
    """A transcription check: `gk2a_detection.py` COPIES this record, it does not derive it.

    Worth keeping only because it catches a hand-edit of one file while the other is
    left alone. It is not corroboration and the registry caveat must not call it that.
    """
    floor = json.loads(GK2A_FLOOR.read_text(encoding="utf-8"))
    assert floor["per_fire"][FIRE]["firms"]["n"] == numbers[DETECTIONS_KEY]["value"]


def test_the_registry_never_calls_the_transcription_check_a_corroboration(numbers):
    """The claim an independent reviewer blocked this row on, pinned so it cannot return."""
    for key in (POSITIVES_KEY, DETECTIONS_KEY):
        caveat = numbers[key].get("caveat", "")
        assert "TRANSCRIPTION CHECK AND NOT CORROBORATION" in caveat, (
            f"{key}'s caveat no longer states that the gk2a cross-check is a "
            "transcription of the same record rather than a second derivation")
        assert "reaches the same value through" not in caveat, (
            f"{key}'s caveat has gone back to describing the copied artifact as an "
            "independent derivation of this count")


def test_the_pasted_citation_points_at_the_fold_it_names(numbers):
    """The registrar resolves by fire_id; the pasted citation is positional.

    `docs/MODEL_CARD.md` tells the author to cite `folds.0.positive_cells`, and the
    entry's own `check.operands` re-derive against that literal path. Reorder
    `docs/fold_sizes.json` and re-run the registrar and the stored path moves to
    `folds.N`, while the sentence bound for a submitted document keeps pointing a judge
    at index 0. Nothing else in the tree binds the two, so it is bound here.
    """
    folds = json.loads(FOLD_SIZES.read_text(encoding="utf-8"))["folds"]
    assert folds[0]["fire_id"] == FIRE, (
        "docs/fold_sizes.json has been reordered: index 0 is now "
        f"{folds[0]['fire_id']!r}, but docs/MODEL_CARD.md cites folds.0 as "
        f"{FIRE}'s positive-cell count. Re-run scripts/register_fold_evidence.py AND "
        "update the citation in the pasted sentence.")
    entry = numbers[POSITIVES_KEY]
    assert entry["json_path"] == "folds.0.positive_cells"
    assert (entry["check"]["operands"]["a"]["json_path"]
            == "folds.0.positive_cells")


def test_the_pasted_sentence_carries_both_counts(card_text):
    """The regression WFG-233 was filed for: one count standing in for the other."""
    start = card_text.find("본 시스템의 산불 확산 모델")
    assert start != -1, (
        "docs/MODEL_CARD.md no longer contains the 작품설명서 replacement sentence; "
        "if it moved, move this test with it rather than deleting the check")
    block = card_text[start:start + 700]
    assert "양성 셀이 8개" in block, (
        "the sentence written to be pasted into the submitted 작품설명서 no longer "
        "states the fold's positive-cell count, which is the quantity the 0.682 AUC "
        "is computed over (WFG-233)")
    assert "17건" in block, (
        "the sentence no longer states the whole-fire FIRMS detection count beside "
        "the positive-cell count; README.md:489 is the model wording (WFG-233)")
    assert "탐지 약 17건" not in block, (
        "the sentence has gone back to explaining the fold with the whole-fire "
        "detection count alone, which is the WFG-233 defect")


def test_the_sentence_names_a_citable_artifact_for_each_count(card_text):
    assert "docs/fold_sizes.json/folds.0.positive_cells" in card_text
    assert ("data/processed/detection/firms_first_detection.json/"
            f"{FIRE}.n") in card_text
    assert "LEGACY_DO_NOT_CITE.md" in card_text, (
        "the note warning that the legacy Build A directory carries a coincidental "
        "second 17 is gone; it is what stops the next lap sourcing this by grep")


def test_the_legacy_audit_path_is_not_written_into_the_card(card_text):
    """Naming the path would register MODEL_CARD.md as a citation of a DO-NOT-CITE file.

    It also mis-binds the artifact manifest: `build_artifact_manifest.py` reads the
    nearest `Regenerate:` clause, so a path named inside this row's own registrar
    docstring was attributed the registrar as that artifact's regeneration command.
    Both are why the warning describes the file instead of addressing it.
    """
    assert "data/processed/spread_v2/audit.json" not in card_text, (
        "docs/MODEL_CARD.md names the legacy Build A audit path, which the row's own "
        "constraint forbids and which binds the file as a cited artifact (WFG-233)")


def test_neither_key_may_be_spoken_of_as_the_other(numbers):
    for key in (POSITIVES_KEY, DETECTIONS_KEY):
        forbidden = numbers[key].get("forbidden_phrasings") or []
        assert "17 positive cells" in forbidden
        assert "8 FIRMS detections" in forbidden


def test_the_caveat_states_both_scopes_on_both_keys(numbers):
    for key in (POSITIVES_KEY, DETECTIONS_KEY):
        caveat = numbers[key].get("caveat", "")
        assert "NOT interchangeable" in caveat
        assert "LEGACY_DO_NOT_CITE.md" in caveat, (
            f"{key}'s caveat no longer warns about the Build A 17")


def test_the_registrar_is_not_stale():
    """`--check` is the gate the next lap runs; a green suite must imply a green check."""
    assert _load_registrar().main.__module__  # importable
    import subprocess
    import sys
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "register_fold_evidence.py"), "--check"],
        cwd=REPO, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
