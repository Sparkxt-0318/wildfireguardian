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


# --------------------------------------------------------------------------
# 1. The property, computed from the artifacts rather than quoted from a doc.
# --------------------------------------------------------------------------
def test_the_property_holds_on_the_committed_grids():
    """Refining the grid raised the opponent and lowered the margin, in fact.

    This is the claim every surface now makes, and it is derived here: the
    forecast-aware total comes from the registry, both argmaxes from the two
    artifacts, and the comparison is between two computed values. Nothing is
    compared against a literal.
    """
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    forecast_aware = numbers["pp_uiseong_safe_forecast_aware"]["value"]
    coarse, dense = _sweep(COMMITTED), _sweep(DENSE)

    assert set(coarse) < set(dense), (
        "the dense grid is not a refinement of the committed one, so nothing "
        "below is a statement about refinement")
    w_coarse, best_coarse = _best(coarse)
    w_dense, best_dense = _best(dense)

    assert best_dense >= best_coarse, (
        f"refining the grid LOWERED the opponent's best score "
        f"({best_coarse} at {w_coarse:.0f} m -> {best_dense} at {w_dense:.0f} m), "
        f"which a maximum over a superset cannot do. Either the two sweeps are "
        f"not comparable or one of the artifacts moved.")
    assert (forecast_aware - best_dense) <= (forecast_aware - best_coarse), (
        "refining the grid RAISED the forecast's margin, which contradicts "
        "every surface that now states the property")


def test_the_documents_worked_instance_is_what_the_artifacts_say():
    """§4's 9-to-5 sentence must be the artifacts' numbers, not a memory.

    The sibling module's lesson (MEMO 2026-09-08T2235Z) is that reading a file
    is not deriving from it unless the assertion consumes what it read. So the
    two margins are computed here and the document is searched for them.
    """
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    forecast_aware = numbers["pp_uiseong_safe_forecast_aware"]["value"]
    margin_coarse = forecast_aware - _best(_sweep(COMMITTED))[1]
    margin_dense = forecast_aware - _best(_sweep(DENSE))[1]
    body = SHAPE_DOC.read_text(encoding="utf-8").split("## 4.")[-1]

    for value, which in ((margin_coarse, "five-point"), (margin_dense, "eight-point")):
        assert re.search(rf"\*{{0,2}}{value}\*{{0,2}}\b", body), (
            f"docs/present_perimeter_buffer_shape.md §4 does not state the "
            f"{which} grid's margin of {value}, so its worked instance is not "
            f"the one the artifacts carry")
    assert margin_coarse - margin_dense > 0, (
        "the worked instance is only worth writing if the refinement actually "
        "cost margin; it did not")


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
