# Why the Q&A bank holds no registry counts (WFG-117)

*Method proposed by the loop (dev lap 2026-09-06T1230Z), not by the student. The
booth consequence is the student's to explain and it is one sentence: **the card
tells you where to count, because any count printed on it is already out of date.***

## The defect this closes

`docs/auto/JUDGE_QA.md` Q30 is a **T0** question — the student answers it from
memory, with no paper — and it is the question a judge asks about why today's
numbers should be believed. Its draft answer quoted the size of the number
registry (`docs/NUMBERS.json`): how many values are registered, and how many
re-derive under `make verify`.

Three consecutive critic laps found that quote stale and each replaced it with
the then-correct pair:

| lap | date | what it wrote into the card | how long it stayed true |
|---|---|---|---|
| critic #21 | 2026-09-05 | replaced the draft's counts, and told the student to point at the screen instead | under a day |
| critic #22 | 2026-09-05 evening | wrote that #21's replacement was already stale, and that the screen was stale too | until the screen was rebuilt |
| critic #26 | 2026-09-06 | wrote that #22's warning was now false, with a fresh count | this lap |

The third correction is the finding. A number that has been corrected three
times in two days is not a number with a typo in it; it is a number that does
not belong in a rehearsal document. Worse, by the time critic #26 ran, the
*warning* had outlived the defect: `WFG-113` had rebuilt the screen at
`1ec1d06`, so the card was drilling the student to distrust the one surface that
was, by then, correct.

## Method

Two changes, and the first is the one that matters.

**1. The recited answer carries no count.** Q30's draft now says that *most*
registered values re-derive, that the rest carry a 「확인됨, 재현 불가」 label with
its reason, and that the exact figures are read — with the judge, at the booth —
from `docs/NUMBERS.json` and the screen's 검증 레지스트리 카드. The four
superseded blocks are kept as dated records (CHARTER §3.7 — superseded values are
annotated, never deleted), each opening with
`[기록 · YYYY-MM-DD · 오늘의 값이 아닙니다]`.

**2. Three gates in `tests/test_judge_qa_bank.py`.**

| test | what it asserts | graded red by |
|---|---|---|
| `test_the_recited_registry_answer_quotes_no_count` | Q30's draft holds no multi-digit number, and still names both places to read one | typing today's count into the draft |
| `test_every_registry_count_in_the_bank_sits_in_a_dated_record` | every 「등록 N」/「재현 가능 N」/「재현 불가 N」 in the bank opens a dated record block | removing one record marker |
| `test_the_banks_qualitative_registry_claim_is_true_of_the_registry` | the word 「대부분」 the student says out loud is true of `docs/NUMBERS.json`, re-derived in-process | flipping most registry entries to non-reproducible |
| `test_the_cards_account_of_the_irreproducible_covers_every_bucket` | every reason the registry gives for not re-deriving is a kind the card names | adding a new `reproducibility.status` to the registry; removing a bucket phrase from the card |

## What the independent reviewer caught, and why it is the same defect

The first version of this change removed the counts and kept, ungated, a **two-bucket**
account of *why* the rest do not re-derive: the overwritten OSM graph, and past runs held
for the reconciliation sheet. The reviewer counted the registry in one command:

```
json.load(open('docs/NUMBERS.json'))['numbers']   # bucket the reproducible=false entries
                                                  # on reproducibility.status
```

Of the 58 irreproducible entries, **16** carry the overwritten-OSM reason, **18** are past
runs not re-executed in this environment, and **24** — the largest group — are
`status == "external"`: agency-published figures whose re-verification means opening the
source again rather than re-running a pipeline. The recited answer named two of three
kinds and omitted the biggest, on the T0 question about honesty, while inviting the judge
to open `docs/NUMBERS.json` alongside them. Four paragraphs below, the same card filed the
older 16 + 18 split as *never verified* — so the file marked the categorisation unverified
and recited it as fact at the same time.

**Removing the numbers had removed the only handle a gate had on the claim.** That is the
row's own defect reproduced one clause later in the same sentence. The fix is the fourth
gate above, which takes the bucket set from the artifact rather than from the author, plus
a 없는 것 line that records the count the card had called unmeasured — it took one command,
and no lap had run it.

## Why the live claim is qualitative


The obvious gate is to keep one correct count in the card and re-derive it. It
was rejected on a measurement rather than on taste. Taken here on an
**unshallowed** clone — `git rev-parse --is-shallow-repository` → `false`, 485
commits, which matters because a shallow clone silently truncates any claim of
this shape (see `docs/auto/DIRECTION.md`) — by walking every revision of the file:

```
git log --format='%H %cI' -- docs/NUMBERS.json     # 57 of the 485 commits
git show <sha>:docs/NUMBERS.json                   # len(json[...]["numbers"]) at each
```

The registry's entry count **changed 44 times**, across **45 distinct values**,
between 2026-08-01 and 2026-09-05. On the four sprint days so far it changed
**10 times** (09-02: 1, 09-03: 3, 09-04: 2, 09-05: 4), and one dev lap
(`c8a3eee`) moved it by 57 keys at once. A gated literal would therefore turn the
suite red about two to four times a day and oblige each of those laps to edit a
judge-facing rehearsal document for no booth benefit — the student is told not to
memorise the figure regardless.

These are measurements of this repository's own git history, not registry
values, so they are not `docs/NUMBERS.json` keys; the two commands above are what
makes them checkable, and they are written nowhere a judge reads.

「대부분」 is the claim that survives a growing registry: it is what the student
actually says, it is falsifiable against the artifact, and it does not need
retyping when a lap registers a key.

## What this does NOT show

- **It does not check that the screen agrees with the registry.** That is
  `tests/test_finals_payload_rederives.py::test_the_registry_card_counts_the_registry_it_ships_beside`
  (WFG-113), which re-derives both, and it is what makes the recited answer's
  「그 둘은 같은 수를 말합니다」 safe to say at a booth. Verified here rather than
  assumed: adding one key to `docs/NUMBERS.json` without rebuilding the screen
  turns that test red, and leaves these three green. If the registry moves and
  the screen is not rebuilt, **that** gate is the one that fires.
- It does not check that Q30's answer is *good*, only that it is not
  arithmetically stale. That remains the student's job and the critic lap's.
- It does not count *why* the non-reproducible values are non-reproducible. The
  card's 없는 것 line still says no lap has counted that split, which is why the
  draft names the two reasons and no proportion.
- The record-marker rule is a convention this lap introduced, so it binds only
  the phrasings the bank has actually used (「등록 N」, 「재현 가능 N」,
  「재현 불가 N」). A future lap that invents a fourth way to write the count
  escapes it. The mitigation is the note addressed to laps inside Q30 itself,
  not a regex.

---

## Update · 2026-09-10 · the two counts that ARE allowed in the bank (WFG-229)

*Row WFG-229 · method proposed by the loop (critic #58 filed the row; this lap
built it) · gates in `tests/test_judge_qa_bank.py`.*

The rule above reads like 「no number in the bank」 and it is not that rule. It
is 「no number the registrar moves under the student's feet」. Q29 is the case
that separates the two.

**The defect.** `docs/auto/finals/TIMELINE_ROLES.md` §0 and §2 publish
`timeline_agent_trailer_commits` and `timeline_total_commits` — the count of
commits carrying the `Co-Authored-By: Claude` trailer, and the total. That
document is this repository's answer to 「일정 및 팀원 역할 배분의 타당성」, a
named sub-item of a 20-point row on both rubric tables. `docs/auto/JUDGE_QA.md`
Q29 answers the same question at tier **T0**, which means the student says it
from memory with no paper, and until this lap it carried **no number at all**.
So a judge could be holding the arithmetic while the student had never
rehearsed it. That is `WC-004`'s shape with a document boundary in place of
eight sections.

**Why a literal is safe here and is not safe in Q30.** Q30's count is the size
of `docs/NUMBERS.json`, which moves on every lap that registers a key — §「Why
the live claim is qualitative」 above measures **10 changes on the four sprint
days**, inside 44 changes across 45 distinct values between 2026-08-01 and
2026-09-05, so a literal there is stale before the student rehearses it. These two are **frozen readings**:
each registry entry carries its own `git_commit` (`89da7d3`, 2026-09-09), the
entry's caveat says in its own words that the figure is 'as of' that commit and
that nothing re-derives it forward, and the artifact behind it changes only when
a lap deliberately runs `scripts/build_timeline_roles.py`. A frozen reading can
be gated; a moving one cannot.

**Method.** Four gates, and the second and third exist because a frozen reading
has two ways to go wrong that a moving one does not:

1. `test_the_authorship_card_carries_the_trailer_counts_the_registry_holds` —
   the spoken draft states both figures **with their units**, re-derived from
   `docs/NUMBERS.json` in the same process. Re-run the registrar and the card
   goes red until it is updated with it.
2. `test_the_trailer_counts_travel_with_their_as_of_commit` — the draft carries
   the seven-character anchor the registry entry names. A total that grows every
   lap is quotable only with one.
3. `test_the_authorship_card_says_what_the_trailer_count_is_not` — the two facts
   the registry's caveat makes mandatory (the trailer is a mechanical string
   test; a commit is not a unit of work) are in the **draft**, not merely in the
   card.
4. `test_the_bank_writes_none_of_the_timeline_forbidden_phrasings` — see below.

**Mutation grading, as it came out.** Restored tree: 31 passed.

| mutation | red |
|---|---|
| M1 · registry value moved 513 → 999 | **1** |
| M2 · the two figures cut from the draft | **2** |
| M3 · the as-of commit removed, figures kept | **1** |
| M4a · 「기계적인 검사」 cut from the DRAFT only | **1** |
| M4b · 「커밋 수는 작업량이 아닙니다」 cut from the DRAFT only | **1** |
| M5 · a registered forbidden phrasing written into the bank | **1** |

⚠ **M4a scored ZERO on the first version of gate 3, and the reason is the
finding.** That gate read the whole card body, and Q29's 없는 것 block says
「기계적 문자열 검사」 too — so a caveat in the block the student does **not**
recite was passing a gate on the sentence they **do**. It is WFG-138's finding
on Q19's 42 arriving one card over, and it was the mutation that found it, not
a reading of the assertion. The gate now reads the draft.

## What `forbidden_phrasings` enforces, and the half of it that is missing

Measured 2026-09-10 in this clone, by experiment rather than by reading. ⚠ **The
first version of this section said 「no gate reads the field」 and that was
false** — the lap's independent reviewer refuted it in one command, and the
correction is kept here rather than quietly replaced, because the shape of the
error matters more than the error. What the lap actually ran was
`grep -rln forbidden_phrasings scripts/ src/ tests/ Makefile | head`, and `head`
truncated the list at ten lines with two test files below the cut. A truncated
listing reads exactly like a complete one.

**Two different things are being asked, and only one of them is enforced:**

1. **「Is the phrasing still declared on the key?」 — enforced, by four tests.**
   `tests/test_present_perimeter_arm.py::test_the_caveat_travels_with_every_key`,
   `tests/test_full_coverage.py::test_registry_forbids_substituting_the_drift_values`,
   `tests/test_sparsity_and_page_budget.py::test_registry_forbids_reading_sparsity_as_household_dispersion`
   and `tests/test_oracle_gap.py` each read the field for their own prefix.
   Empty the `pp_uiseong_*` lists and the first goes red (1 failed, 19 passed);
   the same holds for the other two prefixes. **A phrasing cannot be silently
   deleted from the registry.**
2. **「Does any document write a registered phrasing?」 — enforced for exactly two
   documents.** `tests/test_oracle_gap.py::test_the_forbidden_phrasings_are_registered_and_absent_from_the_doc`
   asserts `docs/oracle_gap.md` contains none of its own prefix's phrasings —
   verified by mutation: appending 「this measures what the model buys」 to that
   file turns exactly that test red — and gate 4 above adds the same shape for
   the Q&A bank and the `timeline_*` keys. Every other document, and every other
   prefix, is unscanned.

And in neither case is `make verify` involved: appending a registered phrasing to
a tracked document leaves all eleven of its sub-targets at exit 0 (checked with
the full target, not a sample of three — the reviewer's re-run, because the
lap's own experiment ran three). `scripts/check_forbidden.py` is the tree-wide
prose scanner and keeps its **own hand-written** HARD/LABEL list, which carries
none of the `og_yeongdeok_*` or `timeline_*` spellings.

**So the gap is (2), not the field.** `WFG-232` carries it, and the naive fix is
wrong: an absence rule over the whole tree goes red immediately, because the
record class exists to quote a forbidden spelling in order to record it. That is
the problem `docs/withdrawn_claims.json` already solved with file scoping plus a
per-line licensing pragma (CHARTER §3.5c).
