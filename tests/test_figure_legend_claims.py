"""A figure legend may report what a search returned; it may not assert what exists.

WFG-266. The `no_safe_route` bucket's code condition is
``nv.enters_hazard and not fa.reached``. It establishes that the fire-blind route
entered the forecast hazard and the forecast-aware search reached no refuge.

⚠ That branch is hand-copied into **seven** places, and this docstring twice said
a smaller number. The authority is the command, not this paragraph — see
``docs/figure_legend_claims.md`` "Method", which pastes the command beside its
raw answer. One of the seven is ``paper/make_figures.py`` itself, inside
``F8b_routing_map``, which recomputes the partition it draws instead of reading a
committed artifact; that copy feeds the very markers the repaired legend labels. It establishes NOTHING about whether a
safe walking route is there, so a legend reading "no safe walking route" claims
more than the run measured.

WHY THIS IS A TEST AND NOT A GREP
---------------------------------
WFG-266's own done-when asked for a grep: ``no safe walking route`` in
``paper/make_figures.py`` should match only supersession docstrings. That clause
cannot be satisfied while the repository is CORRECT, because the repaired legends
read "no safe walking route **found**" and the row's grep is a substring match
that its own exemplar (``F5b``, repaired one lap earlier) fails. A substring is
the wrong instrument: it cannot tell a claim from a report of a search, which is
the entire distinction the repair is about.

So the predicate is on the claim instead. Every string literal in
``paper/make_figures.py`` that is NOT a docstring — that is, every string that can
reach a reader as a label — and that names this bucket must report the search
("found") rather than assert the world ("exists", or the bare noun phrase).
Docstrings are exempt BY DESIGN: they are where the superseded spellings are
quoted in order to record them (CHARTER §3.7), and a gate that forbade the
quotation would forbid keeping the record.

GRADING (all five run both ways before this file shipped, 2026-09-12; each fires a
different test, and the whole file is green once the mutation is undone)
-------------------------------------------------------------------------------
- revert F8b's legend to "origin: no safe walking route" -> RED (bare claim)
- write "no safe walking route exists" into any legend    -> RED (explicit claim)
- delete a legend entry instead of repairing it           -> RED (the per-figure check)
- point F8b's output back at F8_routing_map.png           -> RED (regenerates a
  committed predecessor)
- repoint the manuscript at a superseded file             -> RED (a repair no reader
  is sent to)
- move a superseded spelling into a docstring             -> GREEN, as intended

WHAT THIS FILE DOES NOT CHECK, stated because a gate that is trusted past its reach
is worse than none
----------------------------------------------------------------------------------
- It reads **source string literals**. Nothing here binds a committed PNG to the
  legend string that drew it, so a lap could repair the source, ship a stale
  render, and stay green. Both new figures were opened and read by eye instead.
- It keys on the literal substring ``no safe walking route``. A reworded
  over-claim — "no safe route", "no walkable route", "cannot reach safety" —
  escapes it entirely. This is the same measured limit CHARTER §3.5c records for
  registered withdrawal spellings: a copy-paste ratchet, not a claim detector.
- It says nothing about captions, or about labels built by concatenation at draw
  time.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FIGS = REPO / "paper" / "make_figures.py"
MANUSCRIPT = REPO / "paper" / "manuscript.md"

#: The bucket whose name is the claim under audit.
BUCKET_PHRASE = "no safe walking route"

#: What a legend is allowed to say about it: a report of what the search returned.
REPORTING_SUFFIX = "found"

#: Spellings that assert the world rather than the search. Never permitted in a label.
ASSERTING = ("exists", "at all")

#: The three figures that draw this bucket, and the file each must write to. The
#: predecessors keep the superseded legends and are NOT regenerated (CHARTER §3
#: rule 2; NH-042 open), so the manuscript must point at the `b` files.
REPAIRED_FIGURES = {
    "F3b_regions": "F3b_regions.png",
    "F5b_decision_shift": "F5b_decision_shift.png",
    "F8b_routing_map": "F8b_routing_map.png",
}

#: Superseded predecessors that must stay on disk as the record.
SUPERSEDED_PNGS = ("F3_regions.png", "F5_decision_shift.png", "F8_routing_map.png")


def _non_docstring_strings(src: str) -> list[tuple[int, str]]:
    """Every string constant in the module that is not a module/class/function docstring."""
    tree = ast.parse(src)
    docstring_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstring_ids.add(id(body[0].value))
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstring_ids):
            out.append((node.lineno, node.value))
    return out


@pytest.fixture(scope="module")
def source() -> str:
    return FIGS.read_text(encoding="utf-8")


def test_no_label_asserts_that_no_safe_route_exists(source: str) -> None:
    """A drawn label reports the search; it never asserts non-existence."""
    offenders = []
    for lineno, s in _non_docstring_strings(source):
        if BUCKET_PHRASE not in s:
            continue
        if any(a in s for a in ASSERTING) or REPORTING_SUFFIX not in s:
            offenders.append((lineno, s))
    assert not offenders, (
        "a legend label claims more than the code condition establishes "
        f"(`nv.enters_hazard and not fa.reached`): {offenders}. "
        f"Say '{BUCKET_PHRASE} {REPORTING_SUFFIX}'."
    )


def test_every_figure_that_draws_the_bucket_still_draws_it(source: str) -> None:
    """The repair is a rewording, so the label must still be there to be read.

    Without this, deleting a legend entry would turn the check above green. The
    predicate is per-figure rather than a total count: a hardcoded total would go
    spuriously red the first time a fourth correctly-worded legend is added, which
    would teach the next lap to weaken the file.
    """
    tree = ast.parse(source)
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    missing = []
    for name in REPAIRED_FIGURES:
        body = ast.unparse(funcs[name]) if name in funcs else ""
        if not any(BUCKET_PHRASE in s for _, s in _non_docstring_strings(body)):
            missing.append(name)
    assert not missing, (
        f"these figures draw the bucket but no longer label it: {missing}. "
        "A label is repaired by rewording it, never by removing it."
    )


def test_each_repaired_figure_writes_its_own_new_filename(source: str) -> None:
    """A repaired figure goes to a NEW file; the predecessor is never regenerated."""
    tree = ast.parse(source)
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    for name, png in REPAIRED_FIGURES.items():
        assert name in funcs, f"{name} is missing from paper/make_figures.py"
        written = [s for _, s in _non_docstring_strings(ast.unparse(funcs[name]))
                   if s.endswith(".png")]
        assert written == [png], f"{name} writes {written}, expected exactly ['{png}']"


def test_the_superseded_predecessors_are_kept_on_disk(source: str) -> None:
    """CHARTER §3.7: the old figure is the record and is archived, never deleted."""
    missing = [p for p in SUPERSEDED_PNGS if not (REPO / "paper" / "figures" / p).exists()]
    assert not missing, f"superseded figures must stay committed as the record: {missing}"


def test_the_manuscript_points_at_the_repaired_figures() -> None:
    """A repaired legend that no reader is sent to has repaired nothing."""
    text = MANUSCRIPT.read_text(encoding="utf-8")
    for png in REPAIRED_FIGURES.values():
        assert f"(figures/{png})" in text, f"manuscript.md does not reference {png}"
    for png in SUPERSEDED_PNGS:
        assert f"(figures/{png})" not in text, (
            f"manuscript.md still points at the superseded {png}"
        )
