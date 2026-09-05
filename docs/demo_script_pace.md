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
#16, counting without Latin and symbols, got 4.24 to 7.07 and 1.67x on the same six. The two
sets of figures are not interchangeable and this page never mixes them.) One rate cannot satisfy both
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
  `0.1939` is 영점일구삼구 (6);
* **every other non-space token must have an explicit reading in the script's `LEXICON`, and
  an unknown token is a hard error.** A tokenizer that scores what it does not recognise as
  zero under-counts exactly the segments densest in symbols, which is the failure this rule
  exists to prevent. It fired on the first run: `pooled` in 마무리 had no reading, and the
  count was two syllables short until it got one.

| 구간 | spoken syllables | seconds (was) | seconds (now) | syl/s now |
|---|---:|---:|---:|---:|
| 도입 | 161 | 25 | **29** | 5.55 |
| 1막 · 발견 | 246 | 45 | **44** | 5.59 |
| 2막 · 시간이 도로망을 바꿉니다 | 280 | 55 | **50** | 5.60 |
| 3막 · 같은 출발지, 두 개의 답 | 338 | 75 | **60** | 5.63 |
| 4막 · 예측을 판단으로 | 331 | 55 | **59** | 5.61 |
| 마무리 · 한계 | 328 | 45 | **58** | 5.66 |
| **합계** | **1,684** | 300 | **300** | **5.61** |

The 300 seconds are allocated in proportion to the syllable counts by largest remainder, so
the six whole seconds still sum to exactly 300 without a fudge on the last segment. The
spread is now **1.02x** where it was 1.62x. **No sentence was deleted to buy seconds**
(CHARTER §3.5): proportional allocation means no segment is over its share by construction,
so the trimming the backlog row allowed for was not needed.

## How much of this is a judgement call

The counting rules contain one real judgement — whether `%`, `ha`, `km`, `OSM`, `pooled`,
`STATIC VIEW` and `TIME-AWARE VIEW` are pronounced as Korean syllables or skipped. Running
the script both ways sizes it:

| variant | total syllables | allocation (s) |
|---|---:|---|
| `full` (Latin and symbols read aloud) | 1,684 | 29 / 44 / 50 / **60** / 59 / **58** |
| `hangul-only` (they are skipped) | 1,627 | 30 / 44 / 50 / **57** / 59 / **60** |

**The largest disagreement between the two extreme conventions is 3 seconds out of 300**, on
3막, and four of the six segments move by one second or none. The re-budget therefore does
not rest on how `%` is pronounced. The shipped budget is the `full` variant, because a
student saying 「칠십구점이삼 퍼센트」 does pronounce 퍼센트.

The `hangul-only` total, 1,627, is within three of critic #16's independently counted 1,630,
which is the best evidence available that its unstated convention also skipped Latin and
symbols — an inference from one agreeing total, not something that critic wrote down. What
matters either way: both conventions find the same defect and disagree only about its size.

## What this does NOT show

* **It does not show the script is sayable in five minutes.** 5.61 syllables per second is
  an arithmetic consequence of dividing this text by this budget, not a measurement of
  speech, and this repository has asserted no comfortable rate for spoken Korean. Whether a
  student can say 1,684 syllables in 300 seconds while a judge interrupts is a stopwatch
  question and a human one: **R12 / NH-014**, and WFG-037's booth recipe.
* **It does not show the budget is well-spent.** Giving 3막 — 「이 프로젝트의 전부」 — 60 s
  instead of 75 s is what one rate costs it. If the student wants 3막 slower, the move is to
  cut 3막's sentences, not to hand it seconds another segment then loses; 300 s is fixed by
  the 운영요강.
* **It does not model pauses, breaths, 「어」, or the five interruptions §2 guarantees.** The
  count is of syllables in the text, and a real delivery is longer than its text.
* **It says nothing about the Q&A five minutes** that follow (`docs/auto/JUDGE_QA.md`).

## Re-measuring after an edit

`docs/NUMBERS.json` binds `demo_pace_total_spoken_syllables` and
`demo_pace_syllables_per_second` to the artifact, and `tests/test_demo_script_pace.py`
recomputes them from the committed document. **Adding or removing a spoken sentence
therefore turns the gate red on purpose** — the budget is no longer the one that was
measured. (WFG-101, which wants one sentence in 3막, is the next edit this will catch.)
The fix is never to relax the test:

```
python scripts/measure_demo_script_pace.py --print                 # see the new spread
python scripts/measure_demo_script_pace.py --stamp <NEW UTC STAMP> # new artifact, new filename
python scripts/measure_demo_script_pace.py --register              # upsert the two keys
```

then re-allocate the six segment headers and their cumulative brackets to the printed
`allocation`, and update the table above. The script **refuses to overwrite an existing
artifact** (CHARTER §3.2), so a re-measure always leaves the previous one in place.
