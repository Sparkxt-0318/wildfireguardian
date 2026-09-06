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
