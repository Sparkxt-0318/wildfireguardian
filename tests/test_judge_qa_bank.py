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


# ---------------------------------------------------------------------------
# WFG-229 · the trailer counts. Q29 is T0 --- said from memory, no paper --- and
# `docs/auto/finals/TIMELINE_ROLES.md` publishes the arithmetic a judge holding
# that document already has. The card carried NO number at all until 2026-09-10,
# so the student met 513 / 662 for the first time in front of a judge.
#
# WHY A LITERAL IS ALLOWED HERE AND IS NOT ALLOWED IN Q30. Q30's count is the
# size of docs/NUMBERS.json, which moves on every lap that registers a key: a
# literal there is stale before the student rehearses it (WFG-117; critics #21,
# #22 and #26 each wrote the then-correct pair). These two are frozen readings
# with a `git_commit` in the registry entry itself, and the artifact behind them
# is rebuilt only when a lap runs scripts/build_timeline_roles.py deliberately.
# So the literal is gate-able, and this gate is the thing that makes it safe:
# re-run the registrar and Q29 goes red until the card is updated with it.
TIMELINE_KEYS = {
    "timeline_agent_trailer_commits": "커밋 {value}개",
    "timeline_total_commits": "전체 커밋 {value}개",
}


def _q29() -> str:
    body = next((b for qid, _, b in _questions() if qid == "29"), None)
    assert body is not None, "Q29 is gone from the bank; WFG-229 assumes it exists"
    return body


def test_the_authorship_card_carries_the_trailer_counts_the_registry_holds() -> None:
    """Q29's spoken draft states both figures, with units, as the registry has them.

    Graded by mutation: move either value in docs/NUMBERS.json and this goes red
    naming the key; delete either sentence from the draft and it goes red too.
    """
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    draft = _draft(_q29())
    assert draft, "Q29 no longer has a 답변(초안) block"
    for key, shape in TIMELINE_KEYS.items():
        assert key in numbers, key + " is gone from the registry"
        want = shape.format(value=numbers[key]["value"])
        assert want in draft, (
            "Q29's spoken draft does not carry " + repr(want) + ". This is a T0 "
            "card, so the student says it from memory while a judge may be "
            "holding docs/auto/finals/TIMELINE_ROLES.md, which publishes the "
            "same figure. Write the UNIT (this bank already keeps 42일 apart "
            "from 42곳); a bare integer does not satisfy this gate."
        )


def test_the_trailer_counts_travel_with_their_as_of_commit() -> None:
    """A total that grows every lap is quotable only 'as of' a commit.

    The registry says so in its own caveat ("the figure is 'as of' its
    git_commit and nothing re-derives it forward"), and TIMELINE_ROLES.md 3-(4)
    tells the student not to quote a total without one. The card is the surface
    where that instruction is most likely to be dropped, because it is spoken.
    """
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    anchor = numbers["timeline_agent_trailer_commits"]["git_commit"][:7]
    draft = _draft(_q29())
    assert anchor in draft, (
        "Q29's draft quotes the trailer counts without the commit they were "
        "measured at (" + anchor + "). Every count but the last phase's grows "
        "with every later lap, so a total with no anchor is a number that is "
        "wrong by the time it is said."
    )


def test_the_authorship_card_says_what_the_trailer_count_is_not() -> None:
    """The two facts the registry's caveat makes mandatory travel in the SPOKEN draft.

    Graded against the draft and not the card body, and the first version of
    this gate read the body. The mutation that removed 「기계적인 검사」 from the
    draft scored ZERO, because the 없는 것 block below it says 「기계적 문자열
    검사」 too --- a caveat in the block the student does not recite, passing a
    gate on the sentence they do. WFG-138's finding on Q19's 42, one card over.
    """
    draft = _draft(_q29())
    assert draft, "Q29 no longer has a 답변(초안) block"
    for phrase, why in (
        ("기계적", "the trailer is a mechanical string test, not a statement "
                   "about who thought of what"),
        ("작업량이 아닙니다", "a commit is not a unit of work --- the loop "
                             "commits several times per lap by design"),
    ):
        assert phrase in draft, (
            "Q29's spoken draft states the trailer counts but not that " + why
            + ". The registry's caveat says four facts travel with any of "
            "these figures or none may be quoted; these two are the ones a "
            "judge hears wrong without them. A 없는 것 line does not satisfy "
            "this: the student recites the draft."
        )


def test_the_bank_writes_none_of_the_timeline_forbidden_phrasings() -> None:
    """The registry declares phrasings for these keys. Nothing enforced them here.

    Measured 2026-09-10, and the first version of this docstring got it wrong.
    FOUR tests read the field --- test_present_perimeter_arm, test_full_coverage,
    test_sparsity_and_page_budget and test_oracle_gap --- but three of them grade
    the field's CONTENT for their own prefix (a phrasing may not be deleted from
    the registry). Only test_oracle_gap grades a DOCUMENT against it, and only
    docs/oracle_gap.md. make verify reads the field in neither direction:
    appending a registered phrasing to a tracked file leaves all eleven of its
    sub-targets at exit 0, and scripts/check_forbidden.py, the tree-wide prose
    scanner, keeps its own hand-written list carrying none of these strings.
    This gate is the second document-side binding, for the surface that now
    writes the numbers. docs/judge_qa_gates.md and WFG-232 carry the rest.
    """
    numbers = json.loads(NUMBERS.read_text(encoding="utf-8"))["numbers"]
    text = _text().lower()
    hits = []
    for key, value in numbers.items():
        if not key.startswith("timeline_"):
            continue
        for phrase in value.get("forbidden_phrasings") or []:
            if phrase.lower() in text:
                hits.append(key + ": " + phrase)
    assert not hits, (
        "the Q&A bank writes a phrasing docs/NUMBERS.json registers as "
        "forbidden on the key it belongs to:\n  " + "\n  ".join(hits)
    )


# ---------------------------------------------------------------------------
# WFG-226 · Q38 told the student to open with 「오늘 저장소는 이 질문에 두 가지로
# 답합니다 --- 그게 결함입니다」 for four days after 5bcfe11 closed the
# contradiction, and the bank is one of the seven hashed SOURCES of the printed
# kit, so the stale card was on paper in the booth. The card also cited
# docs/multi_region.md by LINE, and the line moved, which is what made it stale.
def _q38() -> str:
    row = next(
        (line for line in _text().split("\n") if line.startswith("| **Q38 · T1**")),
        None,
    )
    assert row is not None, "Q38 is gone from the bank; WFG-226 assumes it exists"
    return row


def test_the_budget_card_does_not_recite_a_contradiction_that_is_closed() -> None:
    """The lead the student speaks must not report a defect the repository fixed.

    The sentence is KEPT as a dated record (CHARTER 3.7) --- this checks it is
    not what the card OPENS with. Graded by mutation: put the old lead back as
    the first sentence after the question and this goes red; delete the record
    block and the next test goes red.
    """
    row = _q38()
    lead = row.split("|")[2] if row.count("|") >= 3 else row
    lead = lead.split("⚠⚠")[0]
    assert "두 가지로 답합니다" not in lead, (
        "Q38 still OPENS by telling the student the repository answers this "
        "question two ways. 5bcfe11 rewrote docs/multi_region.md 3.1 and the "
        "repository has given one answer since. The card's substantive answer "
        "is unchanged and correct; only the framing was stale."
    )
    assert "한 가지로 답합니다" in lead, (
        "Q38's lead no longer states the repository's single current answer"
    )


def test_the_budget_card_keeps_its_own_correction_as_a_dated_record() -> None:
    """CHARTER 3.7: the superseded lead is kept, marked, and dated."""
    row = _q38()
    assert "2026-09-10" in row and "그대로 말하지 마십시오" in row, (
        "Q38 dropped the dated record of what it used to say. A student who "
        "rehearsed the old lead needs to be told it changed, which is how "
        "Q36 and Q40 handle the same event."
    )


def test_the_budget_card_cites_multi_region_by_section_not_by_line() -> None:
    """A line citation is what went stale here; the section survived the edit."""
    row = _q38()
    assert "§3.1" in row, "Q38 no longer points at docs/multi_region.md 3.1"
    stale = re.findall(r"docs/multi_region\.md[`\s]*:\s*\d+", row)
    assert not stale, (
        "Q38 cites docs/multi_region.md by line number again: "
        + ", ".join(stale) + ". The line moved once already and that move is "
        "the whole reason this row exists. Cite the section."
    )


# ---------------------------------------------------------------------------
# WFG-249 / WFG-251 — two cards that said something true of one layer, or of
# one document, as if it were true of everything. Both shipped INSIDE the
# 58-page booth kit, so both are worth a gate rather than a re-read.
# ---------------------------------------------------------------------------


def _card(qid: str) -> str:
    """One question's body, whitespace flattened and bold markers stripped.

    Flattened because both defects below hid across a line break: the clause
    that scopes a claim and the claim itself sat on different lines, so any
    single-line grep reads them as two sentences and finds neither whole.
    """
    for cur, _tier, body in _questions():
        if cur == qid:
            return re.sub(r"\s+", " ", body.replace("**", ""))
    raise AssertionError(f"Q{qid} is gone from the bank; this gate names it by id")


def test_the_privacy_card_scopes_its_household_definition_to_one_layer() -> None:
    """WFG-249: Q20a defined 「가구」 for the whole repository, and it is not.

    Q20a is a **T0** card, which `docs/auto/JUDGE_QA.md` §6's drill table puts on
    the FIRST round — the student answers the privacy question from memory. It
    said, unqualified, 「이 저장소에서 「가구」는 사람도 주소도 건물도 아니라 OSM
    보행 도로망의 노드 하나입니다」. That is true of the 구조 · 경로 계층, whose
    `home_node` output is what the rest of the answer describes, and it is false
    of the refuge-siting arm, whose 20가구 / 24가구 really are OSM buildings
    (`l0i_household_population`, registered from the artifact one lap earlier).
    The demo's spoken 마무리 says the building half to the same five judges, and
    its 금지 item 6 cited THIS card as the authority for the definition it broke.

    Both properties are asserted because either alone leaves the contradiction
    standing: the scope must sit on the defining sentence (not in a footnote a
    memorising student never reaches), and the other population must be named in
    the same card so 「아까 건물이 아니라고 하셨는데」 has an answer in hand.

    ⚠ What this cannot catch: whether the scope is the RIGHT one. It pins that a
    scope is stated and that both populations appear on one card; that the layer
    named is the layer the `home_node` output belongs to is a reading, and
    `WC-013`'s entry in `docs/auto/withdrawn_claims.json` is where that reading
    is recorded. Do not weaken the privacy answer to satisfy this test — it is
    correct about the routing output, which is why the card exists.
    """
    card = _card("20a")
    assert re.search(r"구조 ?· ?경로 계층에서 「가구」는", card), (
        "Q20a defines 「가구」 without naming the layer the definition is true "
        "of. Unqualified, it contradicts the demo script's closing sentence, "
        "which tells the same judge the 가구 it counts are OSM buildings. Scope "
        "it to the 구조 · 경로 계층; do NOT fix this by weakening the privacy "
        "answer or by deleting either sentence (CHARTER §3.5)"
    )
    assert "l0i_household_population" in card and re.search(r"OSM 건물 스냅숏 124동", card), (
        "Q20a scopes its definition but never says where the OTHER 가구 count "
        "lives. A student asked 「아까 건물이 아니라고 하셨는데 왜 마무리에서는 "
        "건물입니까」 then has a scope and no answer. Name the refuge-siting "
        "arm's population (OSM 건물 스냅숏 124동, l0i_household_population) in "
        "this same card — WC-013's say_instead: the bound goes in the same "
        "block as the claim"
    )


def test_the_related_preprint_card_scopes_its_negative_to_what_was_read() -> None:
    """WFG-251: Q16d asserted a negative over a record it never opened.

    The draft answer said 「기록에는 성능 수치가 하나도 없습니다」 — a claim about
    the whole deposit. The Zenodo record carries exactly one attached file and
    this project has never opened it, which the SAME card's 없는 것 item 1 states
    forty lines below, prescribing the wording 「공개된 기록과 초록에는 …」. Three
    paragraphs after the unscoped sentence the card tells the student to open that
    DOI in front of the judge, so the judge is standing next to the evidence.

    `WC-007` and `WC-009` are what this exact error class already cost this
    project once, in the other direction (a negative, then a positive, about two
    Korean systems whose manuals nobody here has read). The gate is the scope,
    not the fact: every other fact on Q16d was re-verified at the Zenodo API and
    none of it is touched here.
    """
    card = _card("16d")
    assert "기록에는 성능 수치가" not in card, (
        "Q16d asserts a negative over the whole deposited record again. Only "
        "the metadata and the abstract were read; the one attached file was "
        "never opened, and this card's own 없는 것 item 1 says so and gives the "
        "wording: 「공개된 기록과 초록에는 …」"
    )
    assert card.count("공개된 기록과 초록에는") >= 2, (
        "the scoped wording has to appear twice on this card — once in the "
        "spoken draft answer and once in 없는 것 item 1, which prescribes it. "
        "One without the other is how the contradiction lived here: the limits "
        "list was right and the sentence the student says was not"
    )
