"""Tests introduced by the suppression v0.1 sign-off record.

Three kinds of thing are pinned here, and only three, because a test that
restates prose is a test that breaks when the prose improves.

1. **The fold arithmetic of pre-registration section 4.3**, which is the table
   the direction's whole data case rests on, and **the depth at which gate G1
   opens**. Sign-off condition C8 found that three committed documents give two
   different threshold years and that neither is the year that opens the gate:
   G1 requires at least two folds, two folds need twelve distinct report years,
   and a record ending in 2025 therefore has to reach 2014. That number is the
   one that goes to the human who clears WJ-001, so it gets a detector rather
   than a sentence. ``PRIMARY_SPLITS["suppression"]["minimum_units"]`` is 11,
   which is the one-fold figure, so A6's own registry does not disambiguate it
   either and this test is the only place the gate figure is pinned.

2. **The shape of the suppression sign-off artifacts**, on the same terms as the
   roads and landslides tests: a verdict exists, it declares one of the four
   states of ``SIGNOFF.md`` section 3, the fit permission agrees with the state,
   the conditions are numbered without gaps, the ledger carries the matching
   row, and the kill-shot file has items 1 to 4 written and 5 to 7 empty.

3. **The reviewed pre-registration is the one on disk**, by checksum, and A6's
   prior leakage read exists and says in its own header that it was written
   without reading a pre-registration. That last one is roads condition C10 and
   the successor condition of process finding PF-1: if the prior read can be
   written afterwards, the P11 comparison means nothing.
"""

import hashlib
import re
from pathlib import Path

from splits import LeakageRefusal, forward_chaining_by_year, primary_split_spec

EVAL = Path(__file__).resolve().parents[1]
REPO = EVAL.parent.parent

FOUR_STATES = {"unsigned", "signed", "signed with conditions", "refused"}

#: Pre-registration section 4.3, distinct report years to folds. The row at four
#: years is the committed record and it refuses.
FOLD_TABLE = {4: None, 10: None, 11: 1, 12: 2, 15: 5, 20: 10, 25: 15, 35: 25}

#: Gate G1 of pre-registration section 4.5 wants at least two folds, not one.
G1_MIN_FOLDS = 2

#: The last report year of the committed record.
LAST_REPORT_YEAR = 2025


def _folds(n_years):
    years = list(range(LAST_REPORT_YEAR - n_years + 1, LAST_REPORT_YEAR + 1))
    return forward_chaining_by_year(years, **primary_split_spec("suppression")["kwargs"])


# ------------------------------------------------- the fold arithmetic ----

def test_the_section_four_three_fold_table_reproduces():
    for n_years, expected in FOLD_TABLE.items():
        if expected is None:
            try:
                _folds(n_years)
            except LeakageRefusal:
                continue
            raise AssertionError(
                "%d distinct years should refuse and did not" % n_years)
        assert len(_folds(n_years)) == expected, (
            "%d distinct years should yield %d fold(s)" % (n_years, expected))


def test_gate_g1_opens_at_twelve_distinct_years_and_not_at_eleven():
    """Sign-off condition C8. The gate wants two folds, not one."""
    assert len(_folds(11)) < G1_MIN_FOLDS, (
        "eleven distinct report years yield one fold, and gate G1 of the "
        "suppression pre-registration requires at least two, so a record "
        "reaching 2015 leaves the gate shut")
    assert len(_folds(12)) >= G1_MIN_FOLDS


def test_the_record_must_reach_2014_for_gate_g1_to_open():
    """The one number this direction hands to the human who clears WJ-001."""
    shut = list(range(2015, LAST_REPORT_YEAR + 1))
    open_ = list(range(2014, LAST_REPORT_YEAR + 1))
    kwargs = primary_split_spec("suppression")["kwargs"]
    assert len(forward_chaining_by_year(shut, **kwargs)) < G1_MIN_FOLDS
    assert len(forward_chaining_by_year(open_, **kwargs)) >= G1_MIN_FOLDS


# ------------------------------------------- the sign-off record shape ----

def _record_text():
    return (EVAL / "signoffs" / "suppression_v0.1.md").read_text(encoding="utf-8")


def test_the_suppression_verdict_exists_and_declares_one_of_the_four_states():
    assert (EVAL / "signoffs" / "suppression_v0.1.md").is_file()
    declared = re.search(r"^\s*state:\s*(.+?)\s*$", _record_text(), re.MULTILINE)
    assert declared, "the record carries no `state:` field in its yaml block"
    assert declared.group(1) in FOUR_STATES


def test_the_suppression_fit_permission_agrees_with_its_state():
    text = _record_text()
    state = re.search(r"^\s*state:\s*(.+?)\s*$", text, re.MULTILINE).group(1)
    permitted = re.search(
        r"^\s*fits_permitted_on_real_labels:\s*(true|false)\s*$", text, re.MULTILINE)
    assert permitted, "the record does not say whether a fit is permitted"
    assert permitted.group(1) == ("true" if state.startswith("signed") else "false")


def test_the_suppression_conditions_are_numbered_without_gaps():
    text = _record_text()
    state = re.search(r"^\s*state:\s*(.+?)\s*$", text, re.MULTILINE).group(1)
    if state != "signed with conditions":
        return
    ids = re.findall(r"\*\*C(\d+)\.", text)
    assert ids, "a conditional signature with no numbered conditions"
    numbers = sorted({int(i) for i in ids})
    assert numbers == list(range(1, len(numbers) + 1)), (
        "condition numbers are not a gapless run from 1: %r" % numbers)
    assert "**primary**" in text
    assert "named secondary claim" in text


def test_the_ledger_carries_a_row_for_suppression_v01():
    text = (EVAL / "signoffs" / "LEDGER.md").read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines()
            if ln.startswith("| 2026-09-16 | suppression |") and "| v0.1 |" in ln]
    assert len(rows) == 1, "expected exactly one ledger row for suppression v0.1"
    row = rows[0]
    assert "`signed with conditions`" in row
    assert "research/suppression/PREREG_suppression_2026-09-16_v0.1.md" in row
    assert "research/eval/signoffs/suppression_v0.1.md" in row


def test_the_suppression_prereg_is_the_one_that_was_reviewed():
    """The record names a checksum; if the document moves, the review is stale."""
    text = _record_text()
    quoted = re.search(r"prereg_sha256:\s*([0-9a-f]{64})", text)
    assert quoted, "the record carries no prereg checksum"
    prereg = (REPO / "research" / "suppression"
              / "PREREG_suppression_2026-09-16_v0.1.md")
    assert prereg.is_file()
    assert hashlib.sha256(prereg.read_bytes()).hexdigest() == quoted.group(1), (
        "the reviewed pre-registration has changed since the sign-off was "
        "written. SIGNOFF.md section 4 says a version is never edited: an "
        "amendment is a new file with a new version number.")


# ---------------------------------------------------- the kill shot ------

def test_the_suppression_killshot_fixes_items_one_to_four_before_any_result():
    text = (EVAL / "killshots" / "suppression.md").read_text(encoding="utf-8")
    for heading in ("## 1. The objection",
                    "## 2. Why a hostile reviewer raises it",
                    "## 3. What would have to be true",
                    "## 4. The discriminating test"):
        assert heading in text, "missing kill-shot item: %s" % heading
    body = text.split("## 1. The objection", 1)[1].split("## 5.", 1)[0]
    assert len(body.split()) > 400, "items 1 to 4 are too thin to be a kill shot"


def test_the_suppression_killshot_has_no_result_yet():
    text = (EVAL / "killshots" / "suppression.md").read_text(encoding="utf-8")
    tail = text.split("## 5. What the test actually returned", 1)[1]
    tail = tail.split("## Appendix", 1)[0]
    assert "Not written" in tail
    assert not re.search(r"\b(survives|does not survive)\b", tail)


# -------------------------------------------- the reversed P11 order -----

def test_the_prior_leakage_read_exists_and_declares_that_it_predates_the_prereg():
    """Roads condition C10, as a detector rather than a promise."""
    path = EVAL / "leakage_reads" / "suppression_A6_prior.md"
    assert path.is_file(), "the prior read named by the sign-off record is gone"
    head = path.read_text(encoding="utf-8").split("## 1.", 1)[0]
    assert "without ever reading one" in head or "never opened it" in head, (
        "the prior read does not state in its header that it predates the "
        "pre-registration, which is the only thing that makes it evidence")
    record = _record_text()
    assert "research/eval/leakage_reads/suppression_A6_prior.md" in record
    assert re.search(
        r"prior_leakage_read_written_before_reading_prereg:\s*true", record)
