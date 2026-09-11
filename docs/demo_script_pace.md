# The booth script's second budget, measured (WFG-100)

**Method proposed by:** the autonomous loop (critic #16 found the defect, the 2026-09-05T0625Z
dev lap measured and re-budgeted it). **Artifact:**
`data/processed/demo_script_pace/pace_20260905T0625Z.json`. **Script:**
`scripts/measure_demo_script_pace.py`. **Tests:** `tests/test_demo_script_pace.py`.

## The problem

`docs/auto/DEMO_SCRIPT_5MIN.md` is the only document in this repository whose sentences are
spoken out loud to a judge, five times in one day, inside a five-minute limit the KCF
심사개요 recommends and may enforce (「발표는 5분을 넘지 않는 것을 권장; 길어지면 중단될 수
있음」, `docs/auto/RUBRIC.md`). §1 divides those 300 seconds into six segments. Until this
lap the six numbers were 25 / 45 / 55 / 75 / 55 / 45 s, and §5 said they came from 「문장 수와
한국어 발화 속도」. Nobody had done that arithmetic. `tests/test_demo_script_5min.py`
asserted only that the six numbers **sum to 300**, which was true and is a different
question.

Measured over the spoken lines by this lap's convention, the old six implied **4.51 to 7.29
syllables per second — a 1.62x spread inside one document from one stated method.** (Critic
#16 got 4.24 to 7.07 and 1.67x on the same six under a convention it did not write down and
which no variant here reproduces — see 「What could not be reconciled」. The two sets of figures
are not interchangeable and this page never mixes them.) One rate cannot satisfy both
ends. The segment that had to be spoken fastest was **마무리 · 한계**, the limitations close,
and it is last: so the material 과학적 사고 is scored on was the material the clock would eat,
once per judge.

## What was measured, and how

The script counts the syllables a student actually pronounces:

* only `> ` blockquote lines inside §1 — the ⚠ blocks are prose *about* the script, the §3
  mapping table is a reference, and the DRAFT header is not spoken;
* the `[버림]` marker is not spoken, the sentence carrying it is, so it counts;
* one Hangul syllable block (U+AC00–U+D7A3) is one syllable;
* numerals are read sino-Korean and counted as that reading: `2,008` is 이천팔 (3),
  `0.1939` is 영점일구삼구 (6). **This is an approximation and the section below prices
  it:** Korean counter words take native numerals (세 시간, 여섯 개, 스무 가구), which this
  rule gets wrong;
* **every other non-space token must have an explicit reading in the script's `LEXICON`, and
  an unknown token is a hard error.** A tokenizer that scores what it does not recognise as
  zero under-counts exactly the segments densest in symbols, which is the failure this rule
  exists to prevent. It fired on the first run: `pooled` in 마무리 had no reading, and the
  count was two syllables short until it got one.

⚠ **This table is the measurement that SHIPS, re-written in place by each re-measure**; the
`seconds (before WFG-100)` column is the budget as it stood before any of this, kept because
the paragraph above prices the defect against it. Every intermediate allocation is a row of
「The measurements, in order」 at the end of this page, and none of them is deleted.

| 구간 | spoken syllables | seconds (before WFG-100) | seconds (now) | syl/s now |
|---|---:|---:|---:|---:|
| 도입 | 213 | 25 | **35** | 6.09 |
| 1막 · 발견 | 246 | 45 | **41** | 6.00 |
| 2막 · 시간이 도로망을 바꿉니다 | 280 | 55 | **47** | 5.96 |
| 3막 · 같은 출발지, 두 개의 답 | 346 | 75 | **58** | 5.97 |
| 4막 · 예측을 판단으로 | 331 | 55 | **55** | 6.02 |
| 마무리 · 한계 | 383 | 45 | **64** | 5.98 |
| **합계** | **1,799** | 300 | **300** | **6.00** |

The 300 seconds are allocated in proportion to the syllable counts by largest remainder, so
the six whole seconds still sum to exactly 300 without a fudge on the last segment. The
spread is now **1.02x** where it was 1.62x (it read 1.03x between WFG-103 and WFG-194). **No sentence was deleted to buy seconds**
(CHARTER §3.5): proportional allocation means no segment is over its share by construction,
so the trimming the backlog row allowed for was not needed.

**The table above is the allocation that ships today, not the one WFG-100 wrote.** WFG-100
measured 1,684 syllables and allocated 29 / 44 / 50 / 60 / 59 / 58 at spread 1.02x; WFG-103
then changed one spoken sentence and the count moved. What did *not* move is the method, and
the section 「Re-measuring after an edit」 below is the procedure that was followed rather
than described. Every measurement keeps its own artifact, its own registry tag and its own
row in 「The measurements, in order」 at the end of this page.

## How much of this is a judgement call

The counting rules contain two real judgements, and both are measured rather than defended.
All three variants below are in the committed artifact
(`pace_before_039a0de.json` → `variants`), so this table is committed numbers, not
remembered ones.

**First: whether `%`, `ha`, `km`, `OSM`, `pooled`, `STATIC VIEW` and `TIME-AWARE VIEW` are
pronounced as Korean syllables or skipped.**

**Second: `numerals are read sino-Korean` is an approximation, and a Korean speaker knows it
is wrong.** Counter words take *native* numerals — 세 시간, 여섯 개, 스무 가구 — and the flat
rule reads 6개 as 육 개. `--variant native-counters` implements the native readings for the
counts and counters that actually occur, and prices the approximation.

This table is WFG-100's sensitivity run, measured on the script **as it stood at `039a0de`**;
it is kept as measured rather than re-run, because what it prices is the *convention*, and the
convention has not changed since (WFG-103 changed one sentence, not a counting rule).

| variant | total syllables | allocation (s) | spread |
|---|---:|---|---:|
| `full` — Latin and symbols read aloud (**the shipped convention**) | 1,684 | 29 / 44 / 50 / 60 / 59 / 58 | 1.62 |
| `hangul-only` — they are skipped | 1,627 | 30 / 44 / 50 / 57 / 59 / 60 | 1.73 |
| `native-counters` — `full` plus native numerals for counters | 1,686 | 28 / 44 / 50 / 60 / 59 / 59 | 1.63 |

(The spread column is the *old* 25/45/55/75/55/45 budget under each convention — the defect
each one sees.)

**Across all three conventions the six seconds move by at most 3 of 300**, on 3막, and the
sino-Korean approximation alone costs at most 1 second. So the re-budget does not rest on
either judgement. The shipped budget is `full`: a student saying 「칠십구점이삼 퍼센트」 does
pronounce 퍼센트, and 3막's largest counted numbers are above the range where native numerals
are used anyway.

### What could not be reconciled, and is not papered over

Critic #16 reported per-segment counts of 161 / 235 / 279 / 318 / 319 / 318 = 1,630, rates
4.24 to 7.07, spread 1.67x, under a convention it did not write down. **No variant
implemented here reproduces those numbers.** The closest, `hangul-only`, totals 1,627 — within
three — but its per-segment counts are 161 / 237 / 274 / 312 / 320 / 323, which differ from
critic #16's by 0, +2, −5, −6, +1, +5, and its spread is **1.73x, not 1.67x**. The totals
agree only because the per-segment differences cancel; the agreement is arithmetic luck and is
**not** evidence that the conventions match. An earlier draft of this page called it 「the best
evidence available」 that critic #16 counted hangul-only, and the lap's independent reviewer was
right to strike that: it is an inference the segments contradict.

What survives the failure to reconcile is the only thing the re-budget needed: **every
convention anyone has counted with finds the same defect** — a spread between 1.62x and 1.73x
in a document whose stated method allows one rate — **and every one of them puts 마무리 · 한계
fastest and last.** The disagreement is about the defect's second decimal, never about its
existence or its direction.

## What this does NOT show

* **It does not show the script is sayable in five minutes.** 6.00 syllables per second is
  an arithmetic consequence of dividing this text by this budget, not a measurement of
  speech, and this repository has asserted no comfortable rate for spoken Korean. Whether a
  student can say 1,799 syllables in 300 seconds while a judge interrupts is a stopwatch
  question and a human one: **R12 / NH-014**, and WFG-037's booth recipe. ⚠ **And the rate
  is rising, now on four consecutive measurements**: 1,684 at WFG-100, 1,744 at WFG-194,
  1,776 at WFG-247, **1,799 at WFG-250**, against a fixed 300 s. ⚠⚠ **Two of those four
  landed on 2026-09-11, three hours apart, on the same closing sentence** — the first added a
  population, the second corrected which population it was. A page that records the rate
  rising should also record that one sentence took two laps to get right, because the cost of
  the second lap was paid in the same currency as the first.
  Every caveat added to a spoken line is bought at every segment's expense, and the page
  that would settle whether the price is payable is the stopwatch one nobody has run.
* **It does not show the budget is well-spent.** Giving 3막 — 「이 프로젝트의 전부」 — 58 s
  instead of 75 s is what one rate costs it (it was 61 s at WFG-103 and 60 s at WFG-194;
  this bullet said 61 s for four days after the value moved, which is the same staleness
  the table at the top of this page is re-written in place to avoid). If the student wants 3막 slower, the move is to
  cut 3막's sentences, not to hand it seconds another segment then loses; 300 s is fixed by
  the 운영요강.
* **It does not model pauses, breaths, 「어」, or the five interruptions §2 guarantees.** The
  count is of syllables in the text, and a real delivery is longer than its text.
* **It says nothing about the Q&A five minutes** that follow (`docs/auto/JUDGE_QA.md`).

## The before state is committed too

The numbers this page uses to justify the change — the old 25 / 45 / 55 / 75 / 55 / 45 budget,
its 4.51-to-7.29 rates and its 1.62x spread — describe a version of the document that this
lap's own commit overwrote. They are therefore measured from `039a0de`, the claim commit, and
committed as `data/processed/demo_script_pace/pace_before_039a0de.json`
(`python scripts/measure_demo_script_pace.py --stamp <s> --from-ref 039a0de`). The lap's first
attempt asserted them from memory and its reviewer blocked on exactly that. Registry:

| key | value | what |
|---|---:|---|
| `demo_pace_039a0de_rate_spread` | 1.62 | the defect, before <!-- collision-ok: 1.62 — the spread BEFORE the re-budget, at commit 039a0de; the 1.02 on the next line is the same quantity AFTER it, and the two are the point of this page. -->|
| `demo_pace_20260905t0625z_rate_spread` | 1.02 | after <!-- collision-ok: 1.02 — the spread AFTER the re-budget; the 1.62 on the previous line is the same quantity BEFORE it. -->|
| `demo_pace_039a0de_total_spoken_syllables` | 1684 | unchanged by the fix — only seconds moved |
| `demo_pace_20260905t0625z_total_spoken_syllables` | 1684 | " |
| `demo_pace_20260905t0947z_rate_spread` | 1.03 | after WFG-103's sentence <!-- collision-ok: 1.03 — the spread at tag 20260905t0947z; the 1.62 and 1.02 above are the same quantity at 039a0de and 20260905t0625z, and the three rows are this table's whole point. -->|
| `demo_pace_20260905t0947z_total_spoken_syllables` | 1692 | +8 — one spoken sentence in 3막 |
| `demo_pace_20260909t0321z_rate_spread` | 1.02 | after WFG-194's sentence <!-- collision-ok: 1.02 — the spread at tag 20260909t0321z. The 1.02 two rows up is the same quantity at tag 20260905t0625z, and that the two agree to two decimals is arithmetic, not the same measurement: the syllable totals behind them are 1,684 and 1,744. -->|
| `demo_pace_20260909t0321z_total_spoken_syllables` | 1744 | +52 — one spoken sentence in 도입 |
| `demo_pace_20260911t0326z_rate_spread` | 1.02 | after WFG-247's sentence <!-- collision-ok: 1.02 — the spread at tag 20260911t0326z. The two 1.02 rows above are the same quantity at tags 20260905t0625z and 20260909t0321z; that all three agree to two decimals is what proportional allocation guarantees, not evidence that the same text was measured. The syllable totals behind them are 1,684, 1,744 and 1,776. -->|
| `demo_pace_20260911t0326z_total_spoken_syllables` | 1776 | +32 — one spoken sentence in 마무리 |
| `demo_pace_20260911t0620z_rate_spread` | 1.02 | after WFG-250's denominator clause <!-- collision-ok: 1.02 — the spread at tag 20260911t0620z. The three 1.02 rows above are the same quantity at tags 20260905t0625z, 20260909t0321z and 20260911t0326z; that all four agree to two decimals is what proportional allocation guarantees, not evidence that the same text was measured. The syllable totals behind them are 1,684, 1,744, 1,776 and 1,799. -->|
| `demo_pace_20260911t0620z_total_spoken_syllables` | 1799 | +23 — the denominator clause in 마무리, net of what the rewrite gave back |

The per-segment rates and the variant tables are fields of those two artifacts rather than
registry keys of their own.

## One thing the measurement does to itself

The script's 마무리 segment says 「마지막 61초는…」 — **a number this allocation produced, inside
the text the allocation is computed from.** The count is therefore a fixed point of itself.
It did not bite at 58 only because 사십오 and 오십팔 are both three syllables, so replacing 45
with 58 changed no count. **Anyone re-measuring must re-run the count after writing the new
seconds into that sentence, not before**, and check that the allocation is still the one they
wrote. The reviewer of the WFG-100 lap found this; no test catches it.

⚠ **CORRECTED 2026-09-11 (WFG-247), by running the case this paragraph predicted would break**
— **and the first draft of this correction got its own arithmetic wrong, which is recorded
here rather than quietly fixed, because it is the same failure one paragraph later.**

<!-- forbidden-ok: wc015-61-seconds-would-bite-en -->
Until this lap the paragraph above ended 「It would bite at 61 s (육십일, four syllables)」, and
WFG-247's re-budget moved 마무리 to exactly **61 s**. It did not bite. `count_syllables`
answers **8** for 「마지막 61초는」 and **8** for 「마지막 56초는」 — identical, so replacing 56
with 61 changed no count and the allocation is a fixed point of itself at this value. The
reason is that 육십일 is **three** Hangul blocks and 오십육 is three as well, not four and
three; `count_syllables(["육십일"])` and `count_syllables(["오십육"])` both answer 3.
The retired claim was arithmetic asserted from memory inside a page whose whole subject is
not doing that, and it is corrected rather than deleted (CHARTER §3.5) because this section
is what tells the next re-measure to look for it. Registered as **`WC-015`**, with the mislabel the same row corrected as **`WC-016`**.

⚠⚠ **This lap's first draft of the paragraph above said 「both count 7」 and attributed the 7
to `count_syllables`.** Its independent reviewer ran the module and got 8. The cause is worth
a sentence, because it is a way of being wrong that a green gate cannot see:
`count_syllables` takes **a list of lines**, and a bare string passed to it is iterated
**character by character**, so `count_syllables("마지막 61초는")` returns a number that is
neither the rule's answer nor an error. **Call it as `count_syllables([line])`.** The
substantive finding survived the correction unchanged — 8 equals 8, the fixed point does not
bite at 61 — which is exactly why the wrong number was easy to ship: it pointed at a true
conclusion.

**The mechanism is real and only the example was wrong:** a fixed point still bites whenever
the new second-count reads with a different number of blocks than the old one — 100 (백, one
block) against 61 (육십일, three) — so the procedure stands unchanged. What no longer stands
is the idea that 61 is such a value.

⚠ **RE-RUN 2026-09-11 (WFG-250), three hours later, and the procedure held.** That lap moved
마무리 from 61 s to **64 s**, so the spoken 「마지막 61초는」 became 「마지막 64초는」;
`count_syllables(["마지막 64초는"])` answers **8**, the same as at 61 and at 56, because
육십사 is three Hangul blocks like 육십일. The count was re-run **after** the header and the
sentence were rewritten, as the section above instructs, and the allocation came back
unchanged at 35 / 41 / 47 / 58 / 55 / 64. Three consecutive values of this segment — 56, 61,
64 — now read as three blocks, which is a coincidence of the eleventh hour of a five-minute
budget and **not** a reason to stop re-running the count: 100 (백) still bites, and so would
any value under ten.

## Re-measuring after an edit

`docs/NUMBERS.json` binds `demo_pace_total_spoken_syllables` and
`demo_pace_syllables_per_second` to the artifact, and `tests/test_demo_script_pace.py`
recomputes them from the committed document. **Adding or removing a spoken sentence
therefore turns the gate red on purpose** — the budget is no longer the one that was
measured. **It caught WFG-103 on the very next lap**, which is the paragraph below.
The fix is never to relax the test:

```
python scripts/measure_demo_script_pace.py --print                 # see the new spread
python scripts/measure_demo_script_pace.py --stamp <NEW UTC STAMP> # new artifact, new filename
python scripts/measure_demo_script_pace.py --register --tag <NEW UTC STAMP>
```

`--register` **adds keys under the new tag and refuses to change the value of a key that is
already registered** (CHARTER §3.2: add, never edit). The previous measurement's entries stay
as the record of what the script used to ask the student to say; move `TAG` in
`tests/test_demo_script_pace.py` to the new one. Note also that `scripts/build_numbers.py`
rebuilds the registry from its own list and would drop these keys along with every other
additive registrar's — that is WFG-040, and it is why the registrar here is additive.

then re-allocate the six segment headers and their cumulative brackets to the printed
`allocation`, and update the table above. The script **refuses to overwrite an existing
artifact** (CHARTER §3.2), so a re-measure always leaves the previous one in place.

**Re-run the count after you write the new seconds into the headers, not before**, for the
fixed-point reason above; the 도입 header's seconds are not spoken, but 마무리's are.

## The measurements, in order

| tag | artifact | script state | spoken syllables | allocation (s) | spread |
|---|---|---|---:|---|---:|
| `039a0de` | `pace_before_039a0de.json` | before WFG-100 | 1,684 | 25 / 45 / 55 / 75 / 55 / 45 | 1.62 |
| `20260905t0625z` | `pace_20260905T0625Z.json` | after WFG-100 | 1,684 | 29 / 44 / 50 / 60 / 59 / 58 | 1.02 |
| `20260905t0947z` | `pace_20260905T0947Z.json` | after WFG-103 | 1,692 | 28 / 44 / 50 / 61 / 59 / 58 | 1.03 |
| `20260909t0321z` | `pace_20260909T0321Z.json` | after WFG-194 | 1,744 | 37 / 42 / 48 / 60 / 57 / 56 | 1.02 |
| `20260911t0326z` | `pace_20260911T0326Z.json` | after WFG-247 | 1,776 | 36 / 42 / 47 / 58 / 56 / 61 | 1.02 |
| `20260911t0620z` | `pace_20260911T0620Z.json` | after WFG-250 (**ships**) | 1,799 | 35 / 41 / 47 / 58 / 55 / 64 | 1.02 |

**What the third row cost, and what it bought.** WFG-103 replaced one spoken sentence in 3막 —
the one that described the STATIC VIEW baseline as 「지금 이 순간만 보는 지도」 when the arm is
fire-blind — with a sentence that says what the baseline is. It is **8 syllables longer**, so
3막 gains a second (60 → 61) and 도입 loses one (29 → 28); every other segment is unmoved, and
the spread widens from 1.02x to 1.03x, which is inside what whole-second allocation alone can
do. The re-measure was not optional and the sentence was not chosen to be cheap: the count was
run **after** the sentence was written, and the seconds followed it.

**A defect this re-measure exposed in its own test.**
`test_the_artifact_the_registry_points_at_is_committed_and_current` selected the artifact with
`sorted(glob("pace_*.json"))[-1]`, which is `pace_before_039a0de.json` — `b` sorts after every
`pace_2026…` name — so the test was checking the **before** artifact against the live script.
It was green only because 1,684 = 1,684 held across WFG-100 by coincidence. The first edit that
moved the count is the first edit that would have made it red, and it would have named the wrong
file while doing so. It now selects by `TAG`, which is what the registry keys are built from.
A test that identifies its subject by sort order is identifying it by accident.

## The 2026-09-09 re-measure, and what it cost (WFG-194)

The 창의성 row is **20 points on both KCF scoring tables** and the 심사기준 names it first,
and until this lap a count of 창의 or 독창 answered **0** on the booth script. The row's fix
was one spoken sentence in 도입 naming what the project's output object is, plus two ⚠ blocks
which are Q&A prose and are **not** in the 300 seconds by this page's own counting rule.

**The sentence cost 52 syllables and nine seconds of the other five segments**, because 300 s
is fixed by the 운영요강 and a segment that gains seconds takes them from the rest:

| 구간 | seconds before | seconds after | delta |
|---|---:|---:|---:|
| 도입 | 28 | 37 | +9 |
| 1막 | 44 | 42 | -2 |
| 2막 | 50 | 48 | -2 |
| 3막 | 61 | 60 | -1 |
| 4막 | 59 | 57 | -2 |
| 마무리 | 58 | 56 | -2 |

**Whether nine seconds is worth the 창의성 row is not a question this page can answer**, and
it is not a question the measurement answers either. What the measurement says is only that
the six segments still share one rate (spread 1.02x, tighter than the 1.03x it replaced) and
that 마무리 · 한계 is not the fastest segment - the defect WFG-100 was filed for stays fixed.
The trade is written into `docs/auto/DEMO_SCRIPT_5MIN.md` §1 where the student reads it, not
only here.

⚠ **The fixed point did not bite, and it was checked rather than assumed.** 마무리's own line
says 「마지막 NN초는…」, a number this allocation produces inside the text it is computed from.
58 and 56 are both three syllables read sino-Korean (오십팔, 오십육), so re-running the count
after rewriting the header returned the same allocation. At 60 s it would not have.
