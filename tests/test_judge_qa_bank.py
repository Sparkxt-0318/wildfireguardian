"""Gates on the judge Q&A bank (docs/auto/JUDGE_QA.md), backlog row WFG-002.

Why these tests exist
---------------------
The backlog row's done-when clause is a *count* ("at least 30 questions") and a
*grep* ("the purged strings return nothing"), and the critic lap is supposed to
confirm "no P0 question without a file". A count is the wrong completion
criterion on its own: a bank padded to reach a number is a bank the student
will not rehearse, and "every P0 question points at a file" is worth nothing
while it is one reviewer's opinion rather than a check that runs.

So the invariants below are the row's done-when, made mechanical:

1. the bank is at least 30 questions and every one carries a drill tier;
2. the tier counts stated in the header equal the tiers actually tagged --- the
   cheapest guard against padding, because adding a question now forces the
   author to move a number the reader can see;
3. every question carries a 근거 line and a 없는 것 line (an answer that cannot
   say what it fails to show does not belong in a rehearsal document);
4. every T0 question's 근거 line resolves to a real repository path or a real
   registry key --- this is "no P0 question without a file";
5. every registry key named anywhere in the file exists in docs/NUMBERS.json,
   which is the one failure this document is most likely to have (a key that
   reads plausibly and does not exist is indistinguishable from a real one
   until something looks it up --- HANDOFF section 4-B);
6. the deprecated phrasings the row lists stay purged.

None of these check that an answer is *good*. That is the student's job and the
critic lap's; these stop the mechanical failures.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
QA = REPO / "docs" / "auto" / "JUDGE_QA.md"
NUMBERS = REPO / "docs" / "NUMBERS.json"

# A question heading looks like: **Q7 · T1. "..."**
QUESTION_RE = re.compile(r"^\*\*Q(\d+) · (T[012])\.", re.MULTILINE)

# Registry keys are written in backticks and are lowercase_with_underscores.
KEY_RE = re.compile(r"`([a-z][a-z0-9]*(?:_[a-z0-9]+){2,})`")

# Phrasings the row (WFG-002) retired. Each one is either a number that belongs
# to a superseded lineage or a claim about the world with no source.
#
# These are regexes, not literals, because the sharpest item on the list cannot
# be checked as a literal: the retired "40 minutes 안동→영덕" factoid has to be
# caught without firing on the legitimate 240-minute horizon that appears all
# over this document. Hence the negative lookbehind.
PURGED = {
    r"10\s*[-–]\s*14\s*s": (
        "the trigger-to-dispatch timing is about 25 seconds (HANDOFF section 9)"
    ),
    r"five fabricated citations": (
        "HANDOFF section 4-B is five *instructions* carrying findings that did "
        "not exist, not five fabricated citations"
    ),
    r"seven times": (
        "24.73 / 9.17 = 2.7x; the 7x compared against the retired 3.70 % share"
    ),
    r"every fire we could test": "the detection floor was measured on 3 of 6 fires",
    r"(?<!\d)40\s*-?\s*(?:minute|분)": (
        "the '40 minutes 안동→영덕' factoid has no source at all (RESEARCH_BRIEF "
        "section (c) marks it '(no source)'), which makes it the most dangerous "
        "item on the purge list -- a fabricated event, not a superseded number"
    ),
    r"Li et al\. 2019": (
        "no such paper; the real ones are Li, Cova & Dennison 2017 and 2018"
    ),
    r"Ronchi et al\. 2021": "WUI-NITY's first author is Wahlqvist",
    r"Lee et al\. KJRS": "the GK2A detection paper's first author is Sung",
}

# The two committed files that ordered the purge. The list above is checked
# against them so it cannot quietly drift from the row that asked for it.
PURGE_SOURCES = (
    (REPO / "docs" / "auto" / "research" / "RESEARCH_BRIEF_2026-09-03.md",
     "Deprecated Q&A material (do not use)"),
    (REPO / "docs" / "auto" / "research" / "BACKLOG_PROPOSAL_2026-09-03.md",
     "Purge:"),
)


def _text() -> str:
    return QA.read_text(encoding="utf-8")


def _questions() -> list[tuple[int, str, str]]:
    """Return (number, tier, body) for every question, body up to the next one."""
    text = _text()
    marks = list(QUESTION_RE.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((int(m.group(1)), m.group(2), text[m.start():end]))
    return out


def test_the_bank_holds_at_least_thirty_questions() -> None:
    questions = _questions()
    assert len(questions) >= 30, (
        "WFG-002 asks for at least 30 questions grouped by judge type; found "
        f"{len(questions)}"
    )


def test_question_numbers_are_unique_and_contiguous() -> None:
    numbers = [n for n, _, _ in _questions()]
    assert numbers == sorted(numbers), "questions are out of order"
    assert len(set(numbers)) == len(numbers), "a question number is used twice"
    assert numbers == list(range(1, len(numbers) + 1)), (
        "question numbers must run 1..N with no gaps, so the drill table can "
        "name them"
    )


def test_the_stated_tier_counts_match_the_tags() -> None:
    """The anti-padding guard: adding a question moves a number the reader sees."""
    text = _text()
    tagged: dict[str, int] = {"T0": 0, "T1": 0, "T2": 0}
    for _, tier, _ in _questions():
        tagged[tier] += 1
    for tier, count in tagged.items():
        stated = re.search(r"\*\*" + tier + r" \((\d+)개\)\*\*", text)
        assert stated is not None, "the header must state a count for " + tier
        assert int(stated.group(1)) == count, (
            tier + " is stated as " + stated.group(1) + " in the header but "
            + str(count) + " questions carry the tag"
        )


def test_every_question_states_its_evidence_and_its_gap() -> None:
    for number, tier, body in _questions():
        label = "Q" + str(number) + " (" + tier + ")"
        assert "\n근거:" in body or "\n근거: " in body, (
            label + " has no 근거 line. An answer without a file or a registry "
            "key is exactly the class of claim this project has had to retract."
        )
        assert "없는 것:" in body, (
            label + " has no 없는 것 line. Every answer must say what it does "
            "not show; that line is the one a judge remembers."
        )


def test_every_t0_question_points_at_something_that_exists() -> None:
    """'No P0 question without a file', as a check rather than an opinion."""
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    for number, tier, body in _questions():
        if tier != "T0":
            continue
        evidence = body.split("근거:", 1)[1].split("없는 것:", 1)[0]
        cited = KEY_RE.findall(evidence)
        keys = [c for c in cited if c in numbers]
        paths = [
            c for c in re.findall(r"`([^`]+)`", evidence)
            if "/" in c and (REPO / c.split("#")[0].split(" ")[0]).exists()
        ]
        assert keys or paths, (
            "Q" + str(number) + " is T0 (the student must recite it) but its "
            "근거 line resolves to no repository path and no registry key:\n"
            + evidence.strip()[:400]
        )


def test_every_registry_key_named_in_the_bank_exists() -> None:
    """A plausible-looking key that does not exist is HANDOFF section 4-B's failure."""
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    text = _text()
    # Only look at 근거 lines: prose elsewhere may name config fields
    # (forward_sim_advance_threshold, walk_cutoff_p) that are not registry keys.
    evidence_blocks = []
    for _, _, body in _questions():
        if "근거:" in body:
            evidence_blocks.append(body.split("근거:", 1)[1].split("없는 것:", 1)[0])
    candidates = {c for block in evidence_blocks for c in KEY_RE.findall(block)}
    # A candidate is a claimed registry key only if it shares a prefix with one.
    prefixes = {k.split("_")[0] for k in numbers}
    claimed = {c for c in candidates if c.split("_")[0] in prefixes}
    missing = sorted(c for c in claimed if c not in numbers)
    assert not missing, (
        "these read as registry keys and are not in docs/NUMBERS.json: "
        + ", ".join(missing)
    )


@pytest.mark.parametrize("pattern", sorted(PURGED))
def test_the_deprecated_phrasings_stay_purged(pattern: str) -> None:
    hit = re.search(pattern, _text())
    assert hit is None, (
        "/" + pattern + "/ matched " + repr(hit.group(0)) + " and is retired: "
        + PURGED[pattern]
    )


def test_the_purge_list_covers_what_the_row_actually_ordered() -> None:
    """Derive the list from the committed files, do not trust the retyped copy.

    The purge list is the one invariant here with no external referent --- it is
    the author's own list checked against the author's own document, which is
    exactly the shape of check that passes while missing the item nobody
    remembered. So: pull the quoted phrases out of the two committed files that
    ordered the purge (the research brief's "Deprecated Q&A material" line and
    the backlog proposal's "Purge:" clause) and assert every one of them is
    covered by a pattern above.
    """
    ordered: set[str] = set()
    for path, marker in PURGE_SOURCES:
        text = path.read_text(encoding="utf-8")
        assert marker in text, "purge source moved: " + marker + " in " + path.name
        line = text[text.index(marker):].split("\n", 1)[0]
        # The proposal's bullet continues past the purge clause into the answer
        # format ("what does not exist" line, ...), which is not a purged
        # phrase. Stop at that boundary.
        line = line.split("Each answer:", 1)[0]
        ordered.update(re.findall(r'"([^"]{4,60})"', line))
    assert len(ordered) >= 8, (
        "expected at least 8 quoted phrases across the two purge sources, "
        "parsed " + str(len(ordered)) + " --- the marker lines have been reworded"
    )
    uncovered = sorted(
        phrase for phrase in ordered
        if not any(re.search(p, phrase) for p in PURGED)
    )
    assert not uncovered, (
        "the row ordered these purged and no pattern in PURGED covers them: "
        + "; ".join(uncovered)
    )


def test_the_draft_label_is_on_the_file() -> None:
    head = _text()[:1500]
    assert "DRAFT" in head, (
        "CHARTER section 9 and AI_DISCLOSURE rule 3: material meant for the "
        "student's own voice is labelled a draft, at the top, where it is read"
    )


def test_the_drill_table_names_the_right_questions() -> None:
    """Section 6 enumerates every question ID by tier; a renumber must not desync it."""
    text = _text()
    tiers: dict[str, list[int]] = {"T0": [], "T1": [], "T2": []}
    for number, tier, _ in _questions():
        tiers[tier].append(number)
    table = text[text.index("## 6."):]
    for tier, expected in tiers.items():
        row = next(
            (ln for ln in table.splitlines()
             if ln.startswith("|") and tier + " " in ln),
            None,
        )
        assert row is not None, "the drill table has no row for " + tier
        listed = [int(m) for m in re.findall(r"Q(\d+)", row)]
        assert listed == expected, (
            "the drill table lists " + tier + " as " + str(listed)
            + " but those tags are on " + str(expected)
        )


def test_every_judge_type_has_a_section() -> None:
    text = _text()
    for group in ("ML 리뷰어", "산불 과학자", "재난대응 실무자", "소프트웨어 전공 교수"):
        assert group in text, "no section for the judge type: " + group
