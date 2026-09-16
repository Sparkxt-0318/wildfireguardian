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
