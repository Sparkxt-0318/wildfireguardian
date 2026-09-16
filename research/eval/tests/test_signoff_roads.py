"""Tests introduced by the roads v0.1b sign-off record.

Two kinds of thing are pinned here, and only two, because a test that restates
prose is a test that breaks when the prose improves.

1. **The roads split fingerprint**, and the fact that it depends on row order.
   The sign-off record refuses item P6 partly because the pre-registration names
   its folds in prose and carries no fingerprint, and it hands A3 the value to
   write down. If ``splits.py`` ever changes so that the value moves, the
   document A3 wrote it into becomes wrong silently. This closes that.

2. **The shape of the sign-off artifacts themselves**: that a verdict exists,
   that it declares one of the four states of ``SIGNOFF.md`` section 3, that the
   ledger carries the matching row, and that the kill-shot file has items 1 to 4
   written and items 5 to 7 still empty. That last one is the ordering the whole
   kill-shot mechanism rests on: a discriminating test whose reading rule is
   written after the result is a test whose result will be read as support.
"""

import re
from pathlib import Path

from splits import leave_one_complex_out, primary_split_spec, splits_fingerprint

EVAL = Path(__file__).resolve().parents[1]

#: The five fires of the roads pre-registration section 2.1, in the order the
#: document lists them. Order matters: see the order-sensitivity test below.
ROADS_PREREG_FIRES = [
    "goseong_2019",
    "uljin_samcheok_2022",
    "gangneung_2023",
    "uiseong_andong_2025",
    "sancheong_2025",
]

#: The complex-level fingerprint quoted in
#: ``research/eval/signoffs/roads_v0.1b.md`` section 4, which the revised
#: pre-registration must carry in its ``prereg:`` block.
ROADS_COMPLEX_FINGERPRINT = (
    "844e82d06b534901590bc660f62cb49bb2b57279be055e112c93d801098d2cd5"
)

FOUR_STATES = {"unsigned", "signed", "signed with conditions", "refused"}


# ------------------------------------------------------- the fingerprint --

def test_the_roads_complex_fingerprint_is_the_one_quoted_in_the_record():
    splits = leave_one_complex_out(ROADS_PREREG_FIRES)
    assert splits_fingerprint(splits) == ROADS_COMPLEX_FINGERPRINT
    record = (EVAL / "signoffs" / "roads_v0.1b.md").read_text(encoding="utf-8")
    assert ROADS_COMPLEX_FINGERPRINT in record


def test_the_roads_scheme_is_the_registered_one_and_takes_no_arguments():
    spec = primary_split_spec("roads")
    assert spec["scheme"] == "leave_one_complex_out"
    assert spec["kwargs"] == {}


def test_the_2025_yeongnam_pair_is_one_fold_not_two():
    """Section 2.2 of the pre-registration, adopted from the repository rule."""
    with_yeongdeok = leave_one_complex_out(ROADS_PREREG_FIRES + ["yeongdeok_2025"])
    assert len(with_yeongdeok) == len(leave_one_complex_out(ROADS_PREREG_FIRES)) == 5
    held = {s.held_out for s in with_yeongdeok}
    assert "yeongnam_2025" in held
    assert "yeongdeok_2025" not in held


def test_the_fingerprint_moves_with_row_order():
    """The substance of sign-off condition R5's P6 clause.

    A ``Split`` holds positional indices, so naming the scheme and the fires is
    not enough to pin a split: the row order pins it too. The roads unit of
    analysis is the segment, so the fingerprint a result carries is computed on
    the committed segment layout in its committed order, and the document has to
    say so. If this test ever fails because the fingerprints coincide, the
    condition in the record has stopped being true and the record is wrong.
    """
    forward = splits_fingerprint(leave_one_complex_out(ROADS_PREREG_FIRES))
    reverse = splits_fingerprint(leave_one_complex_out(list(reversed(ROADS_PREREG_FIRES))))
    grouped = [f for f in ROADS_PREREG_FIRES for _ in range(3)]
    interleaved = [f for _ in range(3) for f in ROADS_PREREG_FIRES]
    seen = {
        forward,
        reverse,
        splits_fingerprint(leave_one_complex_out(grouped)),
        splits_fingerprint(leave_one_complex_out(interleaved)),
    }
    assert len(seen) == 4


# ------------------------------------------------ the sign-off artifacts --

def test_the_roads_verdict_exists_and_declares_one_of_the_four_states():
    record = EVAL / "signoffs" / "roads_v0.1b.md"
    assert record.is_file()
    text = record.read_text(encoding="utf-8")
    declared = re.search(r"^\s*state:\s*(.+?)\s*$", text, re.MULTILINE)
    assert declared, "the record carries no `state:` field in its yaml block"
    assert declared.group(1) in FOUR_STATES


def test_an_unsigned_direction_may_not_fit_on_real_labels():
    """``SIGNOFF.md`` section 0. A refused direction is not permitted a fit."""
    text = (EVAL / "signoffs" / "roads_v0.1b.md").read_text(encoding="utf-8")
    state = re.search(r"^\s*state:\s*(.+?)\s*$", text, re.MULTILINE).group(1)
    permitted = re.search(
        r"^\s*fits_permitted_on_real_labels:\s*(true|false)\s*$", text, re.MULTILINE)
    assert permitted, "the record does not say whether a fit is permitted"
    if state in {"unsigned", "refused"}:
        assert permitted.group(1) == "false"


def test_the_ledger_carries_a_row_for_the_reviewed_version():
    text = (EVAL / "signoffs" / "LEDGER.md").read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines()
            if ln.startswith("|") and "roads" in ln and "v0.1b" in ln]
    assert len(rows) == 1, "expected exactly one ledger row for roads v0.1b"
    row = rows[0]
    assert "`refused`" in row
    assert "research/eval/signoffs/roads_v0.1b.md" in row


def test_no_direction_is_staged_as_signed_without_a_record():
    """Silence is not a signature, and neither is a ledger row with no file."""
    text = (EVAL / "signoffs" / "LEDGER.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.startswith("|") or "`signed" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        record = cells[5].strip("`")
        assert record != "none", "a signed row with no record: %r" % line
        assert (EVAL.parent.parent / record).is_file(), record


# ------------------------------------------------------- the kill shot ---

def test_the_roads_killshot_fixes_items_one_to_four_before_any_result():
    text = (EVAL / "killshots" / "roads.md").read_text(encoding="utf-8")
    for heading in ("## 1. The objection",
                    "## 2. Why a hostile reviewer raises it",
                    "## 3. What would have to be true",
                    "## 4. The discriminating test"):
        assert heading in text, "missing kill-shot item: %s" % heading
    body = text.split("## 1. The objection", 1)[1].split("## 5.", 1)[0]
    assert len(body.split()) > 400, "items 1 to 4 are too thin to be a kill shot"


def test_the_roads_killshot_has_no_result_yet():
    """Items 5 to 7 stay empty until a result exists, and no result does."""
    text = (EVAL / "killshots" / "roads.md").read_text(encoding="utf-8")
    tail = text.split("## 5. What the test actually returned", 1)[1]
    tail = tail.split("## Appendix", 1)[0]
    assert "Not written" in tail
    assert not re.search(r"\b(survives|does not survive)\b", tail)


# ------------------------------------- the v0.2 record and the record class --
#
# Added by the roads v0.2 sign-off (`research/eval/signoffs/roads_v0.2.md`).
# Two things are pinned here and, as above, only two.
#
# 1. **The v0.2 artifacts**: a verdict exists, it declares one of the four
#    states, the ledger carries the matching row, and the state and the
#    fit permission in the record agree with each other.
#
# 2. **The frozen-record class**, which `research/shared/check_research_claims.py`
#    declares so that a superseded pre-registration can keep the wording a later
#    rule exists to stop recurring without being edited to carry a pragma.
#    Section 7 of the v0.2 record rules that construction sound and names two
#    narrowings it needs. The second one is fixed here, inside A6's own tree,
#    because it is the one that matters and pinning a hash touches nobody
#    else's file: membership in the class is granted by path and not by
#    content, so being in the class is exactly what removes the checker that
#    would have noticed an edit. `SIGNOFF.md` section 4 says editing a
#    superseded pre-registration is the one thing in the protocol that cannot
#    be repaired afterwards, and until now it was the one rule with no
#    detector on it.

import hashlib

REPO = EVAL.parent.parent

#: sha256 of `research/roads/PREREGISTRATION.md` (roads v0.1b, superseded and
#: frozen) as recorded in `research/eval/signoffs/roads_v0.2.md` section 7.
#: If this moves, the file the protocol says must never be edited has been
#: edited, and the record class stopped the claims checker from saying so.
FROZEN_V01B_SHA256 = (
    "9ddb41f9f86710b62d9732db23079a1c60e1f115ece993ff1e48936f39ed579e"
)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_the_frozen_superseded_roads_prereg_has_not_been_edited():
    frozen = REPO / "research" / "roads" / "PREREGISTRATION.md"
    assert frozen.is_file(), "the superseded record is gone, which is worse"
    assert _sha256(frozen) == FROZEN_V01B_SHA256, (
        "research/roads/PREREGISTRATION.md has changed. It is in the claims "
        "checker's RECORD_CLASS, so the checker is silent on it by design, and "
        "SIGNOFF.md section 4 says this edit cannot be repaired afterwards."
    )


def test_the_record_class_does_not_shelter_a_live_preregistration():
    """The first narrowing of v0.2 section 7, as a detector rather than a note.

    ``RECORD_CLASS`` grants a claim-rule exemption by path, and two of the three
    paths it names do not exist yet. The roads direction wrote v0.1, v0.1a and
    v0.1b at exactly that path while each was live, so the class currently
    pre-grants an exemption to where two directions are most likely to write a
    live first draft. The rule that makes it safe is ``SIGNOFF.md`` section 2:
    a pre-registration is named ``PREREG_<direction>_<date>_v<n>.md``. This test
    holds that rule for the paths the exemption covers: a sheltered path may
    exist only for a direction that also has a versioned file superseding it.
    """
    import importlib.util

    checker = REPO / "research" / "shared" / "check_research_claims.py"
    spec = importlib.util.spec_from_file_location("_claims_checker", checker)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    for rel in mod.RECORD_CLASS:
        path = REPO / rel
        if not path.is_file():
            continue
        direction_dir = path.parent
        versioned = sorted(direction_dir.glob("PREREG_*_v*.md"))
        assert versioned, (
            "%s is sheltered from the claim rules but nothing supersedes it, "
            "so the exemption is covering a live pre-registration" % rel
        )


def test_the_roads_v02_verdict_exists_and_declares_one_of_the_four_states():
    record = EVAL / "signoffs" / "roads_v0.2.md"
    assert record.is_file()
    text = record.read_text(encoding="utf-8")
    declared = re.search(r"^\s*state:\s*(.+?)\s*$", text, re.MULTILINE)
    assert declared, "the record carries no `state:` field in its yaml block"
    assert declared.group(1) in FOUR_STATES


def test_the_roads_v02_fit_permission_agrees_with_its_state():
    """`SIGNOFF.md` section 3: only `signed` and `signed with conditions` fit."""
    text = (EVAL / "signoffs" / "roads_v0.2.md").read_text(encoding="utf-8")
    state = re.search(r"^\s*state:\s*(.+?)\s*$", text, re.MULTILINE).group(1)
    permitted = re.search(
        r"^\s*fits_permitted_on_real_labels:\s*(true|false)\s*$", text, re.MULTILINE)
    assert permitted, "the record does not say whether a fit is permitted"
    expected = "true" if state.startswith("signed") else "false"
    assert permitted.group(1) == expected


def test_the_ledger_carries_a_row_for_v02_naming_the_versioned_prereg():
    text = (EVAL / "signoffs" / "LEDGER.md").read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines()
            if ln.startswith("|") and "roads" in ln and "| v0.2 |" in ln]
    assert len(rows) == 1, "expected exactly one ledger row for roads v0.2"
    row = rows[0]
    assert "`signed with conditions`" in row
    assert "research/roads/PREREG_roads_2026-09-16_v0.2.md" in row
    assert "research/eval/signoffs/roads_v0.2.md" in row


def test_a_conditional_signature_numbers_its_conditions():
    """`SIGNOFF.md` section 3: the record lists numbered conditions, each with
    the verification action that clears it and the phase by which it must
    clear, and each marked blocking for the primary result or for a named
    secondary claim. An unnumbered condition is one A3 has to ask about."""
    text = (EVAL / "signoffs" / "roads_v0.2.md").read_text(encoding="utf-8")
    state = re.search(r"^\s*state:\s*(.+?)\s*$", text, re.MULTILINE).group(1)
    if state != "signed with conditions":
        return
    ids = re.findall(r"\*\*C(\d+)\*\*", text)
    assert ids, "a conditional signature with no numbered conditions"
    numbers = sorted({int(i) for i in ids})
    assert numbers == list(range(1, len(numbers) + 1)), (
        "condition numbers are not a gapless run from 1: %r" % numbers)
    assert "**primary**" in text
    assert "named secondary claim" in text


def test_the_roads_killshot_items_one_to_four_are_still_unedited():
    """Later writing on the kill-shot file appends and never rewrites.

    Items 1 to 4 were written on 2026-09-16 before any pre-registration was
    signed. Their whole evidential value is that they predate the design, so an
    edit to them is not a correction, it is the loss of the record. The v0.2
    sign-off appended a dated addendum after the appendix; this pins the slice
    the addendum must not have touched.
    """
    text = (EVAL / "killshots" / "roads.md").read_text(encoding="utf-8")
    body = text.split("## 1. The objection", 1)[1].split("## 5.", 1)[0]
    assert hashlib.sha256(body.encode("utf-8")).hexdigest() == (
        "457bc2b7a0ae591b6ab6367d8507006b9c59c1a84002006c948166a09ce512a7"
    ), "kill-shot items 1 to 4 have changed; they are written before any result "
