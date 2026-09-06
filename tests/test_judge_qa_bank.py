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

# WFG-138. The spelling families live in the English gate and are shared rather
# than retyped here: two hand-kept lists of the same phrases drift, and the lap
# reviewer measured the cost of a one-token list (2 of 7 sentences classified
# correctly, with correct sentences among the misses).
from tests.test_future_aware_attribution import ATTRIBUTION as _ATTRIBUTION
from tests.test_future_aware_attribution import CONTROL as _CONTROL
from tests.test_future_aware_attribution import _flat

REPO = Path(__file__).resolve().parents[1]
QA = REPO / "docs" / "auto" / "JUDGE_QA.md"
NUMBERS = REPO / "docs" / "NUMBERS.json"

# A question heading looks like: **Q7 · T1. "..."**, and two variants the first
# pattern could not see: a letter suffix (**Q10d · T0 ...**), used when a
# question is inserted beside the one it refines rather than renumbering the
# bank, and a parenthetical provenance before the period (**Q35 · T1 (크리틱
# #8). "..."**).
#
# WFG-057. The first pattern was `Q(\d+) · (T[012])\.` and it matched 33 of the
# file's 41 headers. The eight it could not see (Q10a, Q10b, Q10c, Q10d, Q34,
# Q35, Q30a, Q30b) were therefore invisible to EVERY check built on
# `_questions()`: the tier counts the header states, the contiguity check, the
# 근거/없는 것 requirement, the T0-points-at-a-file check and the drill table.
# The counts stayed self-consistent while being wrong about the file, which is
# why three critic laps counted 41/15/19/7 by hand against a header saying
# 33/14/13/6 and nothing went red. The cost the critic named: the fifteenth T0
# is Q10d, whose whole job is to stop the student asserting the withdrawn
# ordering claim, and the drill plan sent them home after fourteen.
QUESTION_RE = re.compile(
    r"^\*\*Q(\d+[a-z]?) · (T[012])(?:\s*\([^)]*\))?\.", re.MULTILINE)

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


def _questions() -> list[tuple[str, str, str]]:
    """Return (id, tier, body) for every question, body up to the next one.

    The id is a string because a question may carry a letter suffix ("10d");
    `_base(id)` is its integer part.
    """
    text = _text()
    marks = list(QUESTION_RE.finditer(text))
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((m.group(1), m.group(2), text[m.start():end]))
    return out


def _base(qid: str) -> int:
    """The integer part of a question id: '10d' -> 10."""
    return int(re.match(r"\d+", qid).group(0))


def test_the_bank_holds_at_least_thirty_questions() -> None:
    questions = _questions()
    assert len(questions) >= 30, (
        "WFG-002 asks for at least 30 questions grouped by judge type; found "
        f"{len(questions)}"
    )


def test_question_numbers_are_unique_and_contiguous() -> None:
    """Every id is used once, and the numbered spine runs 1..N with no gaps.

    WFG-057 widened this from "the numbers are sorted and equal range(1, N+1)",
    which held only because the eight headers that break it were invisible.
    Two things are true of this file and neither is a defect:

    * a refining question is inserted beside the one it refines with a letter
      suffix (Q10a..Q10d after Q10), rather than renumbering a bank the student
      is memorising and four other documents cite by number;
    * Q34 and Q35 were appended by critic laps and sit between Q10d and Q11 in
      reading order. Q34 (spread rate) belongs to the fire-behaviour run it was
      added to; Q35 (can this screen be rebuilt from its stamp?) does NOT
      obviously belong there and would sit better beside Q27/Q28, which are the
      gates-and-tests questions. That is a placement worth revisiting, not an
      invariant to assert -- and renumbering it is the one thing that would
      break four other documents that cite this bank by number.

    So document order is not asserted to be sorted -- that would be a false
    invariant, and the check that the reader can actually find every question is
    `test_the_drill_table_names_the_right_questions`, which is exact. What is
    asserted is what a renumber would break: ids are unique, the distinct base
    numbers are exactly 1..N, and no suffixed question dangles off a base that
    does not exist.
    """
    ids = [q for q, _, _ in _questions()]
    assert len(set(ids)) == len(ids), (
        "a question id is used twice: "
        + str(sorted(q for q in set(ids) if ids.count(q) > 1))
    )
    bases = sorted({_base(q) for q in ids})
    assert bases == list(range(1, len(bases) + 1)), (
        "question numbers must run 1..N with no gaps, so the drill table can "
        "name them; found " + str(bases)
    )
    dangling = sorted(q for q in ids if not q.isdigit() and str(_base(q)) not in ids)
    assert not dangling, (
        "these questions carry a letter suffix but the question they refine is "
        "not in the bank: " + str(dangling)
    )


def test_the_count_is_reached_by_a_second_parser_that_shares_no_code() -> None:
    """Independence, not agreement: count the headers a deliberately different way.

    The lap reviewer's leakage finding, and it is the right one. Every other
    check here counts with `QUESTION_RE` and then compares that count to a
    header the same regex located -- one parser producing both sides, which is a
    closed loop. It is exactly how 33 · 14 · 13 · 6 stayed green for six windows
    while the file held 41 · 15 · 19 · 7: the regex could not see eight headers,
    so the count and the number it was checked against were wrong together and
    agreed perfectly.

    So this counts by a different route: split the file on its `---` rules and
    look for a bold run opening with `Q` and carrying a `· T<n>` tag, with no
    shared regex and no shared helper. If the two disagree, one of them has lost
    sight of a question, and which one is a question for a human -- that is the
    point, because the failure mode being guarded is both of them being wrong in
    the same direction.
    """
    blocks = _text().split("\n---\n")
    independent: dict[str, int] = {"T0": 0, "T1": 0, "T2": 0}
    for block in blocks:
        for line in block.splitlines():
            line = line.strip()
            if not line.startswith("**Q") or "·" not in line:
                continue
            head = line.split("·", 1)[1].lstrip()
            tier = head[:2]
            if tier in independent and (len(head) == 2 or not head[2].isdigit()):
                independent[tier] += 1
                break

    via_regex: dict[str, int] = {"T0": 0, "T1": 0, "T2": 0}
    for _, tier, _ in _questions():
        via_regex[tier] += 1

    assert independent == via_regex, (
        "two independent counts of this file disagree: the header regex sees "
        + str(via_regex) + " and a separate scan sees " + str(independent)
        + ". One of them cannot see a question. Do not adjust the header to "
        "match either until you know which."
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
        "CHARTER section 9: material meant for the "
        "student's own voice is labelled a draft, at the top, where it is read"
    )


def test_the_drill_table_names_the_right_questions() -> None:
    """Section 6 enumerates every question ID by tier; a renumber must not desync it."""
    text = _text()
    tiers: dict[str, list[str]] = {"T0": [], "T1": [], "T2": []}
    for qid, tier, _ in _questions():
        tiers[tier].append(qid)
    table = text[text.index("## 6."):]
    for tier, expected in tiers.items():
        row = next(
            (ln for ln in table.splitlines()
             if ln.startswith("|") and tier + " " in ln),
            None,
        )
        assert row is not None, "the drill table has no row for " + tier
        listed = re.findall(r"Q(\d+[a-z]?)", row)
        assert listed == expected, (
            "the drill table lists " + tier + " as " + str(listed)
            + " but those tags are on " + str(expected)
        )


def test_every_judge_type_has_a_section() -> None:
    text = _text()
    for group in ("ML 리뷰어", "산불 과학자", "재난대응 실무자", "소프트웨어 전공 교수"):
        assert group in text, "no section for the judge type: " + group


# ---------------------------------------------------------------------------
# WFG-117: the registry counts, and why this bank may not hold one
#
# Q30 is T0 --- the student recites it from memory --- and it is the question
# about why today's numbers should be believed. Three consecutive critic laps
# wrote the then-correct counts into that card (#21 on 2026-09-05, #22 the same
# evening, #26 on 2026-09-06) and all three were stale inside one lap, because
# the count moves whenever any lap registers a key. Measured over this
# repository's whole history on an UNSHALLOWED clone (485 commits,
# `git rev-parse --is-shallow-repository` -> false): docs/NUMBERS.json's entry
# count changed 44 times across 45 distinct values between 2026-08-01 and
# 2026-09-05, ten of those on the four sprint days. So a literal here is not a
# fix with a typo in it; it is a defect with a shorter fuse, and the third
# correction of a number is evidence that correcting it is the wrong move.
#
# Hence the split these three tests enforce:
#
#   * the answer the student recites carries NO count at all --- it names the
#     two places to read one (docs/NUMBERS.json and the screen's card);
#   * a count literal is allowed only inside a dated record block, which is
#     CHARTER section 3.7 (superseded values are annotated, never deleted);
#   * the one quantitative claim the recited answer DOES make is qualitative
#     ("대부분", most), and that word is checked against the registry --- so
#     this gate still has something to say when the registry moves, without
#     going red every time it does.
#
# What these do NOT do, and it matters for reading a red one. They do not check
# that the screen agrees with the registry; that is
# tests/test_finals_payload_rederives.py::test_the_registry_card_counts_the_registry_it_ships_beside,
# which re-derives both and is what makes the recited answer's "그 둘은 같은
# 수를 말합니다" safe to say at a booth. If the registry moves and the screen is
# not rebuilt, THAT test goes red, not these.

RECORD_MARK = re.compile(r"^\[기록 · \d{4}-\d{2}-\d{2} · 오늘의 값이 아닙니다\]")

# A registry count as this bank has ever written one: the quantity named, then
# the number. Deliberately not a bare-integer scan --- the card also carries
# critic numbers (#21, #26), commit ids and dates, none of which are claims
# about the registry.
COUNT_CLAIM = re.compile(r"(?:등록된 값|등록|재현 가능|재현 불가)\s*(\d{2,4})개?")


def _q30() -> str:
    body = next((b for qid, _, b in _questions() if qid == "30"), None)
    assert body is not None, "Q30 is gone from the bank; WFG-117 assumed it exists"
    return body


def test_the_recited_registry_answer_quotes_no_count() -> None:
    """The T0 draft names where to read the count instead of holding one."""
    draft = _q30().split("답변(초안):", 1)[1].split("\n\n", 1)[0]
    stray = re.findall(r"(?<!\d)\d{2,}(?!\d)", draft)
    assert not stray, (
        "Q30's recited draft answer quotes " + ", ".join(stray) + ". This card "
        "may not hold a registry count: it moves on every lap that registers a "
        "key, so a number typed here is stale before the student rehearses it "
        "(critics #21, #22 and #26 each corrected it and each correction went "
        "stale inside one lap). Say where to read it instead --- "
        "docs/NUMBERS.json and the screen's 검증 레지스트리 카드."
    )
    for place in ("docs/NUMBERS.json", "검증 레지스트리 카드"):
        assert place in draft, (
            "Q30's draft no longer tells the student to read the count at "
            + place + "; with no number and no pointer the answer is empty"
        )


def test_every_registry_count_in_the_bank_sits_in_a_dated_record() -> None:
    """A superseded count is kept (CHARTER 3.7) but must be marked and dated."""
    unmarked = []
    for para in _text().split("\n\n"):
        if not COUNT_CLAIM.search(para):
            continue
        if RECORD_MARK.match(para.strip()):
            continue
        unmarked.append(para.strip()[:180])
    assert not unmarked, (
        "these paragraphs state a registry count outside a dated record "
        "block. Either the value is today's --- in which case it does not "
        "belong in this document at all, read it from docs/NUMBERS.json --- "
        "or it is a record, and it opens with "
        "[기록 · YYYY-MM-DD · 오늘의 값이 아닙니다]:\n\n" + "\n\n".join(unmarked)
    )


# Q30's draft accounts for WHY a registered value does not re-derive. The
# registry sorts those values by `reproducibility.status`, so the set of buckets
# is the artifact's to decide, not the card's. This map is the card's side of
# it: each status the registry actually uses must have a phrase the card says.
#
# The first version of this lap's Q30 named two buckets, and this test did not
# exist. The independent reviewer counted the registry in one command and found
# a third bucket -- `external`, published agency figures whose re-verification
# means opening the source again rather than re-running a pipeline -- which was
# the LARGEST of the three and the one the card omitted, on the T0 question
# about honesty. Hence the direction of this gate: it fails when the registry
# grows a bucket the card does not describe, which is the failure that actually
# happened, rather than checking that a phrase the author chose is present.
IRREPRODUCIBLE_BUCKETS = {
    "not_reproducible": "덮어써져",      # the OSM graph overwritten 2026-07-24
    "external": "저장소 밖의 공개 수치",   # agency-published figures
    None: "다시 돌리지 않은 과거 실행",    # past runs not re-executed here
}


def test_the_cards_account_of_the_irreproducible_covers_every_bucket() -> None:
    """Every reason the registry gives for not re-deriving is one the card names."""
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    seen = set()
    for value in numbers.values():
        if value.get("reproducible"):
            continue
        repro = value.get("reproducibility")
        seen.add(repro.get("status") if isinstance(repro, dict) else None)
    unknown = sorted((s for s in seen if s not in IRREPRODUCIBLE_BUCKETS), key=str)
    assert not unknown, (
        "docs/NUMBERS.json marks values irreproducible for reason(s) this Q&A "
        "card does not describe: " + ", ".join(map(repr, unknown)) + ". Q30 is "
        "T0 and tells a judge what the labels mean, so a new bucket has to be "
        "named there (and added to IRREPRODUCIBLE_BUCKETS) before it ships."
    )
    q30 = _q30()
    for status in sorted(seen, key=str):
        phrase = IRREPRODUCIBLE_BUCKETS[status]
        assert phrase in q30, (
            "the registry has irreproducible values with status "
            + repr(status) + ", and Q30 no longer contains the phrase that "
            "describes them (" + phrase + "). The card would then account for "
            "fewer kinds than the registry has, which is the defect this gate "
            "was added for."
        )


def test_the_banks_qualitative_registry_claim_is_true_of_the_registry() -> None:
    """The recited answer says 대부분 ("most") re-derive. Check that against the registry.

    This is the claim that survives a registry that grows: it is what the
    student actually says out loud, it is falsifiable, and it does not need
    retyping when a lap registers a key.
    """
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    n_entries = len(numbers)
    n_reproducible = sum(1 for v in numbers.values() if v.get("reproducible"))
    draft = _q30().split("답변(초안):", 1)[1].split("\n\n", 1)[0]
    assert "대부분" in draft, (
        "Q30's draft no longer claims that 대부분 of the registry re-derives; "
        "if the wording changed, this gate is checking a sentence that is gone"
    )
    assert n_reproducible * 2 > n_entries, (
        "Q30 tells a judge that 대부분 ('most') of the registered values "
        "re-derive under make verify, and the registry says "
        + str(n_reproducible) + " of " + str(n_entries) + ", which is not most. "
        "Either the registry regressed or the booth answer is now an overclaim; "
        "the answer is the thing to change, not this threshold."
    )


# WFG-138 (b), critic #29. The 「시간 인지 경로에서만」 sentence is the bank's
# strongest claim and its baseline is `naive`, which is fire-blind
# (src/wildfireguardian/routing/evacuation.py:270). Critic #22 wrote the
# correction for the 91 into a ⚠ block *below* Q19's draft answer, critic #23
# tightened that block, and for two windows the 42 in the same sentence of the
# same draft stood uncorrected --- because a note beside a sentence is not the
# sentence. The student rehearses the draft, so the caveat has to live inside
# the draft; this gate is what makes that true of every card, not only of Q19.
#
# What it does NOT do: it keys on spellings (ATTRIBUTION and CONTROL, shared
# with the English gate and scored there against sentences neither gate's author
# wrote). It catches a caveat that is deleted, moved out of the draft, or a new
# card that never had one. A reworded overclaim carrying none of the keyed
# phrases still escapes --- the same limit docs/withdrawn_claims.md section 4
# records for the withdrawn-claim registry, kept as a strict xfail there.
def _draft(body: str) -> str:
    """The quoted draft answer of a question body, or '' if it has none."""
    if "답변(초안):" not in body:
        return ""
    return body.split("답변(초안):", 1)[1].split("\n\n", 1)[0]


def test_no_draft_answer_states_the_future_aware_only_claim_bare() -> None:
    """A card that says 「... 시간 인지 경로에서만 ...」 names its control in the same draft.

    Graded by mutation: delete the 「42도 91도 불을 전혀 보지 않는 ...」 sentence
    from Q19's draft and this goes red naming Q19.
    """
    offenders = []
    for qid, _, body in _questions():
        draft = _flat(_draft(body))
        if any(a.search(draft) for a in _ATTRIBUTION) and not any(
            c.search(draft) for c in _CONTROL
        ):
            offenders.append(qid)
    assert not offenders, (
        "Q" + ", Q".join(offenders) + ": the draft answer the student speaks "
        "attributes the count to knowing where the fire will be without saying, "
        "in the draft itself, that the comparison is against a route that sees no "
        "fire at all (「불을 전혀 보지 않는」, or any spelling in CONTROL). "
        "The baseline is fire-blind in this repository's "
        "own words (src/wildfireguardian/routing/evacuation.py:270), so the bare "
        "sentence lets a judge hear 「better than knowing where the fire is now」, "
        "which this repository has measured on 의성·안동 only. A ⚠ note above or "
        "below the draft does not satisfy this: that is exactly what failed for "
        "two windows on Q19's 42 (WFG-138, critic #29)."
    )
