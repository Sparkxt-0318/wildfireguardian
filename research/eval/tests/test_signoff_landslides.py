"""Tests introduced by the landslides v0.1 sign-off record.

Three kinds of thing are pinned here, and only three, because a test that
restates prose is a test that breaks when the prose improves.

1. **The two traps in the registered landslide split.** A4's section 12.3 found
   the first: ``require_fire_disjoint=True`` welds every block sharing a fire
   identifier into one group, so a shared sentinel identifier on unburned
   control units collapses the country into a single group and the splitter
   refuses. Sign-off condition C7 found the second: ``canonical_fire_id``
   strips underscores, hyphens, spaces and dots, so two control identifiers
   that differ only in their separators normalise to the same key and weld two
   distant control blocks together **silently**, which is worse than the
   failure the first fix repairs. Both are behaviours of A6's own file and
   neither has a detector until here.

2. **The demonstration fingerprints**, so that the values quoted in the sign-off
   record and committed in ``research/landslides/design/design_numbers.json``
   cannot drift apart from what ``splits.py`` actually returns.

3. **The shape of the landslides sign-off artifacts**, on the same terms as the
   roads tests: a verdict exists, it declares one of the four states of
   ``SIGNOFF.md`` section 3, the fit permission agrees with the state, the
   conditions are numbered without gaps, the ledger carries the matching row,
   the kill-shot file has items 1 to 4 written and 5 to 7 empty, and A6's prior
   leakage read exists and says in its header that it predates the
   pre-registration. That last one is the whole of roads condition C10: if the
   prior read can be written afterwards, the P11 comparison means nothing.
"""

import hashlib
import re
from pathlib import Path

from splits import (
    LeakageRefusal,
    canonical_fire_id,
    primary_split_spec,
    spatial_block_cv,
    splits_fingerprint,
)

EVAL = Path(__file__).resolve().parents[1]
REPO = EVAL.parent.parent

FOUR_STATES = {"unsigned", "signed", "signed with conditions", "refused"}

#: The declared demonstration geometry of
#: ``research/landslides/design/split_demonstration.py``. Reproduced here rather
#: than imported, because importing it would run a script that writes into a
#: directory A6 does not own.
DEMO_SEED = 20260916
DEMO_CLUSTERS = 6
DEMO_UNITS_PER_CLUSTER = 200
DEMO_SPREAD_M = 12000.0
DEMO_CONTROLS = 1200
DEMO_CONTROL_SEED = 1

FIRES_ONLY_FINGERPRINT = (
    "7eab0f0267fb318ad36a9bcb70106b7da64955b4469a76094f66e60d5732a5f3"
)
UNIQUE_CONTROL_FINGERPRINT = (
    "5138895ca17fe17af909f3ce39618026e1e828d54c5bce464a30bad65e046178"
)


def _demo_fire_units():
    import random

    rng = random.Random(DEMO_SEED)
    xs, ys, fire_ids = [], [], []
    for c in range(DEMO_CLUSTERS):
        cx = 200000.0 + 60000.0 * c
        cy = 400000.0 + 37000.0 * ((c * 7) % 5)
        for _ in range(DEMO_UNITS_PER_CLUSTER):
            xs.append(cx + rng.uniform(-DEMO_SPREAD_M, DEMO_SPREAD_M))
            ys.append(cy + rng.uniform(-DEMO_SPREAD_M, DEMO_SPREAD_M))
            fire_ids.append("FIRE_%d" % c)
    return xs, ys, fire_ids


def _demo_controls():
    import random

    rng = random.Random(DEMO_CONTROL_SEED)
    xs, ys = [], []
    for _ in range(DEMO_CONTROLS):
        xs.append(rng.uniform(150000.0, 560000.0))
        ys.append(rng.uniform(300000.0, 700000.0))
    return xs, ys


# ------------------------------------------------------ the split traps --

def test_the_landslides_scheme_is_the_registered_one():
    spec = primary_split_spec("landslides")
    assert spec["scheme"] == "spatial_block_cv"
    assert spec["kwargs"]["require_fire_disjoint"] is True
    assert spec["kwargs"]["block_size_m"] == 5000.0
    assert spec["kwargs"]["buffer_m"] == 1000.0
    assert spec["kwargs"]["n_folds"] == 5


def test_a_shared_control_sentinel_collapses_the_country_and_refuses():
    """A4's section 12.3, and sign-off condition C7's first half.

    Every control block in the country shares one identifier, so the weld joins
    them into a single spatial group and five folds cannot be filled. The
    refusal is the correct behaviour; what this test protects is that it keeps
    happening, because a later change that returned a split instead would put
    the whole country on both sides of every fold.
    """
    fx, fy, fids = _demo_fire_units()
    cx, cy = _demo_controls()
    kwargs = dict(primary_split_spec("landslides")["kwargs"])
    try:
        spatial_block_cv(fx + cx, fy + cy,
                         fire_ids=fids + ["CONTROL"] * DEMO_CONTROLS, **kwargs)
    except LeakageRefusal as exc:
        assert "cannot fill" in str(exc)
    else:
        raise AssertionError(
            "a shared control sentinel no longer refuses; the landslides "
            "pre-registration section 12.3 rests on this refusal firing")


def test_unique_control_identifiers_yield_five_folds():
    """The other half of section 12.3: the fix works and reproduces."""
    fx, fy, fids = _demo_fire_units()
    cx, cy = _demo_controls()
    kwargs = dict(primary_split_spec("landslides")["kwargs"])
    splits = spatial_block_cv(
        fx + cx, fy + cy,
        fire_ids=fids + ["CONTROL_%d" % i for i in range(DEMO_CONTROLS)],
        **kwargs)
    assert len(splits) == 5
    assert splits_fingerprint(splits) == UNIQUE_CONTROL_FINGERPRINT


def test_the_fires_only_demonstration_fingerprint_is_the_one_committed():
    fx, fy, fids = _demo_fire_units()
    kwargs = dict(primary_split_spec("landslides")["kwargs"])
    splits = spatial_block_cv(fx, fy, fire_ids=fids, **kwargs)
    assert splits_fingerprint(splits) == FIRES_ONLY_FINGERPRINT


def test_control_identifiers_collide_under_the_normaliser():
    """Sign-off condition C7's second half, which is a defect in A6's own file.

    ``canonical_fire_id`` strips whitespace, underscores, hyphens, dots,
    commas, parentheses and middle dots before lookup, and
    ``spatial_block_cv`` resolves identifiers with ``strict=False``, so an
    unregistered identifier is accepted with no guard. Two control identifiers
    that differ only in their separators therefore weld two spatially distant
    blocks into one group and return a plausible split rather than refusing.

    This test asserts the collision **exists**, which is the point: the
    pre-registration has to declare a scheme that is injective after this
    normalisation, and a reader who does not know the normaliser eats
    separators will invent one that is not.
    """
    assert canonical_fire_id("CONTROL_1_2") == canonical_fire_id("CONTROL_12")
    assert canonical_fire_id("CONTROL-12") == canonical_fire_id("CONTROL_12")
    assert canonical_fire_id("CONTROL_1") != canonical_fire_id("CONTROL_12")


def test_a_colliding_control_scheme_silently_welds_two_blocks():
    """The consequence, demonstrated rather than asserted.

    Two controls placed far apart, given identifiers that differ only by an
    underscore, land in one spatial group. With the weld in place they can
    never fall on opposite sides of a fold, which is the wrong answer arrived
    at quietly.
    """
    xs = [200000.0, 600000.0, 200000.0, 600000.0]
    ys = [400000.0, 400000.0, 700000.0, 700000.0]
    colliding = ["CONTROL_1_2", "CONTROL_12", "CONTROL_3", "CONTROL_4"]
    injective = ["CONTROL_1", "CONTROL_2", "CONTROL_3", "CONTROL_4"]
    kwargs = dict(primary_split_spec("landslides")["kwargs"])
    kwargs["n_folds"] = 2

    def folds_of(ids):
        splits = spatial_block_cv(xs, ys, fire_ids=ids, **kwargs)
        return [next(k for k, s in enumerate(splits) if i in s.test)
                for i in range(len(xs))]

    welded = folds_of(colliding)
    clean = folds_of(injective)
    assert welded[0] == welded[1], (
        "the collision no longer welds; condition C7 has stopped being true")
    assert clean[0] != clean[1] or welded != clean


# ----------------------------------------------- the sign-off artifacts --

def _record_text():
    return (EVAL / "signoffs" / "landslides_v0.1.md").read_text(encoding="utf-8")


def test_the_landslides_verdict_exists_and_declares_one_of_the_four_states():
    record = EVAL / "signoffs" / "landslides_v0.1.md"
    assert record.is_file()
    declared = re.search(r"^\s*state:\s*(.+?)\s*$", _record_text(), re.MULTILINE)
    assert declared, "the record carries no `state:` field in its yaml block"
    assert declared.group(1) in FOUR_STATES


def test_the_landslides_fit_permission_agrees_with_its_state():
    text = _record_text()
    state = re.search(r"^\s*state:\s*(.+?)\s*$", text, re.MULTILINE).group(1)
    permitted = re.search(
        r"^\s*fits_permitted_on_real_labels:\s*(true|false)\s*$", text, re.MULTILINE)
    assert permitted, "the record does not say whether a fit is permitted"
    expected = "true" if state.startswith("signed") else "false"
    assert permitted.group(1) == expected


def test_the_landslides_conditions_are_numbered_without_gaps():
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


def test_the_ledger_carries_a_row_for_landslides_v01():
    text = (EVAL / "signoffs" / "LEDGER.md").read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines()
            if ln.startswith("|") and "landslides" in ln and "| v0.1 |" in ln]
    assert len(rows) == 1, "expected exactly one ledger row for landslides v0.1"
    row = rows[0]
    assert "`signed with conditions`" in row
    assert "research/landslides/PREREG_landslides_2026-09-16_v0.1.md" in row
    assert "research/eval/signoffs/landslides_v0.1.md" in row


def test_the_landslides_prereg_is_the_one_that_was_reviewed():
    """The record names a checksum; if the document moves, the review is stale."""
    text = _record_text()
    quoted = re.search(r"prereg_sha256:\s*([0-9a-f]{64})", text)
    assert quoted, "the record carries no prereg checksum"
    prereg = REPO / "research" / "landslides" / "PREREG_landslides_2026-09-16_v0.1.md"
    assert prereg.is_file()
    assert hashlib.sha256(prereg.read_bytes()).hexdigest() == quoted.group(1), (
        "the reviewed pre-registration has changed since the sign-off was "
        "written. SIGNOFF.md section 4 says a version is never edited: an "
        "amendment is a new file with a new version number.")


# ---------------------------------------------------- the kill shot ------

def test_the_landslides_killshot_fixes_items_one_to_four_before_any_result():
    text = (EVAL / "killshots" / "landslides.md").read_text(encoding="utf-8")
    for heading in ("## 1. The objection",
                    "## 2. Why a hostile reviewer raises it",
                    "## 3. What would have to be true",
                    "## 4. The discriminating test"):
        assert heading in text, "missing kill-shot item: %s" % heading
    body = text.split("## 1. The objection", 1)[1].split("## 5.", 1)[0]
    assert len(body.split()) > 400, "items 1 to 4 are too thin to be a kill shot"


def test_the_landslides_killshot_has_no_result_yet():
    text = (EVAL / "killshots" / "landslides.md").read_text(encoding="utf-8")
    tail = text.split("## 5. What the test actually returned", 1)[1]
    tail = tail.split("## Appendix", 1)[0]
    assert "Not written" in tail
    assert not re.search(r"\b(survives|does not survive)\b", tail)


# -------------------------------------------- the reversed P11 order -----

def test_the_prior_leakage_read_exists_and_declares_that_it_predates_the_prereg():
    """Roads condition C10, as a detector rather than a promise.

    The whole evidential value of A6's prior read is that it was written before
    A4's document was opened. Nothing can prove that after the fact, but the
    claim has to be present, explicit and findable, and the sign-off record has
    to point at the same file it was made in.
    """
    path = EVAL / "leakage_reads" / "landslides_A6_prior.md"
    assert path.is_file(), "the prior read named by the sign-off record is gone"
    head = path.read_text(encoding="utf-8").split("## 1.", 1)[0]
    assert "BEFORE opening" in head or "before opening" in head, (
        "the prior read does not state in its header that it predates the "
        "pre-registration, which is the only thing that makes it evidence")
    record = _record_text()
    assert "research/eval/leakage_reads/landslides_A6_prior.md" in record
    assert re.search(
        r"prior_leakage_read_written_before_reading_prereg:\s*true", record)
