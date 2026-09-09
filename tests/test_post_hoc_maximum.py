"""WFG-201: the fair opponent's width is chosen after the fact, so the margin is
a maximum over a grid and can only fall as the grid is refined.

`scripts/run_present_perimeter_arm.py` sweeps buffer widths and the opponent is
scored at the **best** one — the argmax of `safe_total`, read after the run,
because nothing in the problem chooses a width. That selection rule is
deliberate and conservative: the opponent should be given its best shot. What it
costs is that every conclusion drawn from the argmax — the shoulder, the
「be wrong thick」 asymmetry, and any margin the forecast is reported to hold over
this opponent — is conditioned on the set of widths that happened to be measured,
and a width added to the grid can only tie or beat the incumbent. So the
opponent's best score is non-decreasing and the margin non-increasing in how
finely anyone searches.

Two halves, and the second is the one this module exists for:

1. the property is **true of the committed artifacts**, checked by computing it
   rather than by quoting a document (`test_the_property_holds_...`); and
2. **no surface may read a conclusion off that argmax without saying so.** The
   ban is scoped to the **section** a judge actually reads — a card, a 막, a
   numbered section — not to the file. Scoping it to the file is exactly the
   WC-004 failure the charter records: a lap fixed Q30's card and left the same
   claim standing in Q35, eight sections away, in the same green file.

⚠ **What this gate cannot check, stated because the same agent wrote both sides.**
The qualifier sentences on the six surfaces and the patterns that recognise them
were written by one lap, so this module grades a **form** — is a qualifier of a
recognised shape present in the section a judge reads — and not a meaning. It
cannot tell a correct qualifier from a plausible one, and it would accept a
sentence that used the right words wrongly. That is `mandela` leakage #4, the
scorer grading a bucket it drew. Two things narrow it and neither closes it: the
qualifier needs **two independent halves** (the selection is post hoc; refinement
moves the result one way) with several alternative spellings each, so a single
borrowed phrase does not license a claim; and the mutations below are graded
against text this module did not author. The check that is *not* form-only is
`test_the_documents_worked_instance_is_what_the_artifacts_say`, which computes
both margins from the artifacts and requires §4 to state them.

⚠ **What this gate does NOT cover.** `paper/` is the paper routine's (CHARTER
§12) and no dev lap edits it, so `paper/manuscript.md` §4.5 and `paper/GAPS.md`
are outside the surface list even though the same qualifier is owed there. That
is a hole, it is named here rather than left to be discovered, and it is filed as
a backlog row for the paper lap. Adding those two paths to `SURFACES` is the
whole fix once that lap has written the sentence.

Everything here reads committed files only: no clock, no timezone, no network,
no path outside the repository (CHARTER §4b).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
COMMITTED = REPO / "data/processed/present_perimeter_arm_uiseong_andong_2025.json"
DENSE = REPO / "data/processed/present_perimeter_buffer_shape_uiseong_andong_2025.json"
NUMBERS = REPO / "docs/NUMBERS.json"
SHAPE_DOC = REPO / "docs/present_perimeter_buffer_shape.md"

#: The surfaces that read a conclusion off the argmax of the buffer sweep.
#: Named rather than globbed, for the reason the sibling module gives: a glob
#: starts passing silently the day a file is renamed.
SURFACES = (
    "README.md",
    "docs/present_perimeter_arm.md",
    "docs/present_perimeter_buffer_shape.md",
    "docs/fair_opponent_line.md",
    "docs/auto/DEMO_SCRIPT_5MIN.md",
    "docs/auto/JUDGE_QA.md",
)

# --------------------------------------------------------------------------
# What counts as reading a conclusion off the argmax, and what counts as saying
# so. Both sets are pasted from sentences the repository actually ships and then
# loosened, per MEMO 2026-09-08T2117Z: a pattern written from the *meaning* of a
# sentence rather than from the sentence matches nothing, and a green gate over
# an unmatching pattern is evidence FOR the thing it was meant to catch.
# --------------------------------------------------------------------------
TRIGGERS = (
    (re.compile(r"(?:top|answer)\s+(?:is|turned out to be)\s+a\s+\*{0,2}shoulder"),
     "states the shape of the top, which is read off the argmax"),
    (re.compile(r"(?:be wrong|guess)\s+\*{0,2}thick"),
     "draws the 'be wrong thick' lesson, which is read off the argmax"),
    (re.compile(r"(?:꼭대기|답)[은는]?\s*[^\n]{0,30}?\*{0,2}「?어깨"),
     "states the shape of the top (Korean)"),
    (re.compile(r"틀리려면\s*\*{0,2}두껍게"),
     "draws the 'be wrong thick' lesson (Korean)"),
    (re.compile(r"margin\s+(?:of|is|was)\s+\*{0,2}\d"),
     "states a margin over the fair opponent"),
    (re.compile(r"(?:여유|margin)[^\n]{0,12}\*{0,2}\d+\s*곳"),
     "states a margin over the fair opponent (Korean)"),
)

#: The qualifier has TWO halves and both are required. Half one alone reads as a
#: methods note; half two alone reads as arithmetic. Only together do they say
#: the thing a statistician judge asks about, which is that the number can only
#: move one way as anyone looks harder.
POST_HOC = re.compile(
    r"after the fact|scanning outcomes|결과를\s*(?:다\s*)?보고\s*고른"
    r"|다\s*돌린\s*뒤\s*점수표를\s*읽")
REFINEMENT = re.compile(
    r"non-increasing|non-decreasing|can only tie or beat|only (?:raise|lower|"
    r"rise|fall|strengthen|shrink)|세지기만|줄어들기만|좋을 수만|오르기만")


def _units(rel: str, text: str) -> list[tuple[str, str]]:
    """Split a surface into the units a judge reads as one thing.

    A markdown heading opens a new unit. In the Q&A bank a card is one table
    row, so every table line is its own unit: the bank is 1400 lines and a
    qualifier in Q37 must not license a bare claim in Q40.
    """
    units: list[tuple[str, list[str]]] = [(f"{rel}:preamble", [])]
    for line_no, line in enumerate(text.splitlines(), 1):
        if line.startswith("#"):
            units.append((f"{rel}:{line.strip()[:60]}", [line]))
        elif line.startswith("|") and len(line) > 200:
            units.append((f"{rel}:{line_no} (table row)", [line]))
            units.append((units[-2][0], []))  # the section resumes after it
        else:
            units[-1][1].append(line)
    return [(label, "\n".join(body)) for label, body in units if body]


def unqualified_post_hoc_claims(units) -> list[tuple[str, str]]:
    """Units that read a conclusion off the argmax without saying it is one."""
    out = []
    for label, body in units:
        fired = [what for pat, what in TRIGGERS if pat.search(body)]
        if not fired:
            continue
        if POST_HOC.search(body) and REFINEMENT.search(body):
            continue
        out.append((label, fired[0]))
    return out


def _sweep(path: Path) -> dict[float, dict]:
    art = json.loads(path.read_text(encoding="utf-8"))
    return {float(r["buffer_m"]): r for r in art["buffer_sensitivity"]}


def _best(grid: dict[float, dict]) -> tuple[float, int]:
    w = max(grid, key=lambda k: grid[k]["safe_total"])
    return w, grid[w]["safe_total"]


def _states(text: str, value: int) -> bool:
    """Is `value` written in `text` as a number of its own?

    ⚠ Anchored on BOTH sides, and this module shipped it unanchored first. The
    independent reviewer's nail: `\\*{0,2}9\\*{0,2}\\b` matches the 9 inside
    **349** and the 5 inside **345**, two substrings sitting in the very
    sentence the assertion was meant to check, so the test stayed green against
    a document whose worked instance had been rewritten to 12 and 7. A
    derivation that any falsification survives is decoration
    (MEMO 2026-09-08T2235Z), which is the anti-pattern this module's own
    docstring cites.
    """
    return re.search(rf"(?<![\d.])\*{{0,2}}{value}\*{{0,2}}(?![\d.\w])",
                     text) is not None


def _states_width(text: str, metres: float) -> bool:
    """A width, in either spelling the documents use: `750 m` or `1 km`."""
    if metres >= 1000 and metres % 1000 == 0:
        km = int(metres // 1000)
        if re.search(rf"(?<![\d.])\*{{0,2}}{km}\*{{0,2}}\s*km", text):
            return True
    return re.search(rf"(?<![\d.])\*{{0,2}}{int(metres)}\*{{0,2}}\s*m\b",
                     text) is not None


# --------------------------------------------------------------------------
# 1. The property, computed from the artifacts rather than quoted from a doc.
# --------------------------------------------------------------------------
def test_the_grids_are_nested_and_the_refinement_actually_moved_the_answer():
    """The two conditions every surface's sentence rests on, checked.

    ⚠ The monotonicity itself is *not* asserted here, and an earlier draft of
    this module did assert it. A maximum over a superset cannot be smaller than
    a maximum over the subset, so with `set(coarse) < set(dense)` established one
    line above, `best_dense >= best_coarse` is arithmetic and can only fail if
    the two files disagree on a shared width — which is already
    `test_buffer_shape.py::test_the_five_shared_widths_reproduce_cell_for_cell`'s
    job. A test that grades a bucket it drew itself is `mandela` #4, and the
    independent reviewer named it.

    What has content, and is what the prose actually leans on, is that the
    grids are **nested** (otherwise the monotonicity argument does not apply at
    all) and that this refinement **moved the argmax onto a new width** — the
    worked instance is worth writing only because it happened.
    """
    coarse, dense = _sweep(COMMITTED), _sweep(DENSE)
    assert set(coarse) < set(dense), (
        f"the dense grid is not a superset of the committed one "
        f"({sorted(set(coarse) - set(dense))} missing), so nothing on any "
        f"surface is a statement about adding widths to this grid, and the "
        f"monotonicity argument does not hold")

    w_coarse, best_coarse = _best(coarse)
    w_dense, best_dense = _best(dense)
    assert w_dense not in coarse, (
        f"the refinement left the best width at {w_coarse:.0f} m, so there is "
        f"no worked instance and the surfaces must not claim one")
    assert best_dense > best_coarse, (
        f"the refinement did not strengthen the opponent ({best_coarse} at "
        f"{w_coarse:.0f} m -> {best_dense} at {w_dense:.0f} m), so 「the first "
        f"refinement took part of the margin」 is false on this tree")


def test_the_forecast_aware_arm_is_the_same_number_on_both_grids():
    """The margin only falls if the arm it is measured from does not move.

    The forecast-aware arm plans no buffer, so widening the buffer grid cannot
    touch it — but that is the invariance the whole property rests on and no
    surface states it, so it is checked here rather than assumed.
    """
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    registered = numbers["pp_uiseong_safe_forecast_aware"]["value"]
    for path in (COMMITTED, DENSE):
        art = json.loads(path.read_text(encoding="utf-8"))
        assert art["headline"]["safe_forecast_aware"] == registered, (
            f"{path.name} reports a different forecast-aware total "
            f"({art['headline']['safe_forecast_aware']}) from the registered "
            f"{registered}, so the two margins are not measured from the same "
            f"baseline and cannot be compared")


def test_the_documents_worked_instance_is_what_the_artifacts_say():
    """§4's 9-to-5 sentence must be the artifacts' numbers, not a memory.

    The sibling module's lesson (MEMO 2026-09-08T2235Z) is that reading a file
    is not deriving from it unless the assertion consumes what it read. So the
    two margins are computed here and the document is searched for them.
    """
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    forecast_aware = numbers["pp_uiseong_safe_forecast_aware"]["value"]
    w_coarse, best_coarse = _best(_sweep(COMMITTED))
    w_dense, best_dense = _best(_sweep(DENSE))
    body = SHAPE_DOC.read_text(encoding="utf-8").split("## 4.")[-1].split("## 5.")[0]

    for value, which in ((forecast_aware - best_coarse, "five-point"),
                         (forecast_aware - best_dense, "eight-point")):
        assert _states(body, value), (
            f"docs/present_perimeter_buffer_shape.md §4 does not state the "
            f"{which} grid's margin of {value} as a number of its own, so its "
            f"worked instance is not the one the artifacts carry")
    for value, which in ((best_coarse, "the five-point grid's best safe total"),
                         (best_dense, "the eight-point grid's best safe total")):
        assert _states(body, value), (
            f"§4's worked instance does not state {which} ({value}), so a "
            f"reader cannot check the two margins against the sweep")
    for width, which in ((w_coarse, "the width it came from"),
                         (w_dense, "the width it moved to")):
        assert _states_width(body, width), (
            f"§4's worked instance does not name {which} ({width:.0f} m), so "
            f"the two margins are not attached to the grids they came from")


#: The worked-instance sentence as §4 actually ships it. Held as a probe rather
#: than as a regex, for the sibling module's reason: a mutation written from the
#: *meaning* of a sentence tests nothing, and if the sentence is reworded this
#: probe must go stale loudly instead of quietly matching nothing.
WORKED_INSTANCE_PROBE = ("margin went from **9** origins to **5**",
                         "margin went from **12** origins to **7**")


def test_the_worked_instance_check_fails_on_a_document_that_states_wrong_margins(
        monkeypatch, tmp_path):
    """The reviewer's nail, kept as a test so the anchoring cannot be lost.

    The first version of `_states` had no left boundary, so 9 matched inside
    **349** and 5 inside **345** — both in the same sentence — and the check
    passed against a §4 whose worked instance read 12 and 7, and against a §4
    with the bullet deleted outright. This test is that mutation.
    """
    shipped, falsified = WORKED_INSTANCE_PROBE
    original = SHAPE_DOC.read_text(encoding="utf-8")
    assert shipped in original, (
        f"the sentence this mutation targets is no longer in §4: {shipped!r}. "
        f"Re-take the probe from the document rather than deleting the test.")

    for mutated in (original.replace(shipped, falsified),
                    original.replace(shipped, "")):
        path = tmp_path / "mutated.md"
        path.write_text(mutated, encoding="utf-8")
        monkeypatch.setitem(globals(), "SHAPE_DOC", path)
        with pytest.raises(AssertionError):
            test_the_documents_worked_instance_is_what_the_artifacts_say()


# --------------------------------------------------------------------------
# 2. The live gate, and the mutations that prove it can fail.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("rel", SURFACES)
def test_every_surface_that_reads_a_conclusion_off_the_argmax_says_so(rel: str):
    text = (REPO / rel).read_text(encoding="utf-8")
    hits = unqualified_post_hoc_claims(_units(rel, text))
    assert not hits, (
        f"{rel} draws a conclusion from the best buffer width without saying "
        f"the width was chosen after the fact and that refining the grid can "
        f"only move the result one way: {hits}. The qualifier belongs in the "
        f"same section a judge reads, not elsewhere in the file "
        f"(docs/present_perimeter_buffer_shape.md §4).")


@pytest.mark.parametrize("rel", SURFACES)
def test_the_gate_fires_when_the_qualifier_is_removed(rel: str):
    """Mutation 1, on the real text: strike the qualifier, the gate must fail.

    A gate that cannot be made to fail is not a gate and its author cannot tell
    the difference — the sibling module learned that the expensive way.
    """
    text = (REPO / rel).read_text(encoding="utf-8")
    mutated = REFINEMENT.sub("", POST_HOC.sub("", text))
    assert unqualified_post_hoc_claims(_units(rel, mutated)), (
        f"removing every qualifier from {rel} did not make the gate fire, so "
        f"the gate is not what is keeping the qualifier there")


def test_the_gate_fires_on_a_margin_added_to_a_surface_that_had_none():
    """Mutation 2: the case the row named, and the one no surface hits today.

    No judge-facing surface states a margin value while NH-032 and NH-034 are
    open, so this arm of the gate is inert against the current tree. It is
    exercised against text instead of skipped, because the day those decisions
    close is the day it becomes load-bearing.
    """
    injected = "## 5. The result\n\nThe forecast holds a margin of **9** origins.\n"
    hits = unqualified_post_hoc_claims(_units("synthetic.md", injected))
    assert hits and "margin" in hits[0][1], (
        "a bare margin sentence on a fresh surface did not fire the gate")

    licensed = injected.rstrip() + (
        " That width was chosen after the fact by scanning outcomes, so the "
        "margin is non-increasing under refinement.\n")
    assert not unqualified_post_hoc_claims(_units("synthetic.md", licensed))


def test_half_a_qualifier_does_not_license_the_claim():
    """Either half alone must still fail, or the gate grades on a token word."""
    claim = "## 3.\n\nThe top is a **shoulder**.\n"
    for half in ("The width was chosen after the fact by scanning outcomes.",
                 "The result is non-increasing under refinement."):
        assert unqualified_post_hoc_claims(_units("synthetic.md", claim + half)), (
            f"half a qualifier licensed the claim: {half!r}")


def test_a_qualifier_in_another_section_does_not_license_the_claim():
    """The WC-004 shape: Q30 corrected, Q35 left standing in the same file."""
    text = ("## 3.\n\nThe answer is a **shoulder**.\n\n"
            "## 4.\n\nChosen after the fact by scanning outcomes; the margin is "
            "non-increasing under refinement.\n")
    hits = unqualified_post_hoc_claims(_units("synthetic.md", text))
    assert hits, "a qualifier one section away licensed the claim"


def test_the_surfaces_this_gate_names_all_exist():
    missing = [rel for rel in SURFACES if not (REPO / rel).exists()]
    assert not missing, f"the gate names paths that do not exist: {missing}"
