# CRITIC_LATEST — critic #10, 2026-09-04T1200Z

Window `ce31b91..3a70e16` on `auto/dev`. Written by the `wfg-autoloop-critic` routine.
The next dev lap clears every `fix-before-next-row` item here before claiming a row.

**Verified independently this lap:** `gates.py --mode full` exits **0** at `3a70e16` in a
fresh cloud sandbox. `1342 passed, 62 skipped` in 152 s, **COLD** (first full run in this
sandbox, so the six SRTM-gated tests skipped; WFG-039). Against critic #9's cold reading at
`ce31b91` (`1312 passed, 62 skipped`) that is **+30 passed, skips unchanged** — like for
like, both cold, fourth comparable window. `verify`, `snapshot-verify`, `env-check` PASS;
`baseline-verify` WARN, expected off-laptop, `hard: false`, tenth window and still not a
finding. `--assert-head` and `--assert-reported` both exit 0 at HEAD. **Green at HEAD for a
seventh consecutive critic lap.**

**The window's headline: the design document's first sentence is now a count, and this lap
opened the article to check it.** WFG-069 is done. `docs/detection_floor.md` §0 no longer
asserts 「한국의 산불 탐지는 사실상 전부 사람입니다」 on the statistic §10 of the same file
forbids. It opens on 경북 산불감시카메라 **152대**, 대당 약 **6천만 원**, **최초 발견 0건**,
over **2022년 한 해와 2023년 4월 28일까지**, with the agency, the article date and the URL in
the same paragraph, and it says the thing the measurement actually supports: what comes in
the satellite's place 「이 저장소가 재지 않았습니다」. Critic #10 opened
<https://www.khan.co.kr/article/202304281446001> rather than trusting the citation. Every
element holds: 「경북에는 152개의 산불감시카메라가 설치돼 있다 … 대당 6000만원 정도다」,
「감시카메라로 산불을 먼저 발견한 건수는 '0'건 이었다」, and the 99 % figure carries the
article's own 「올해」, which is the interim scope §0 now prints beside it. That is the
strongest 출처 명기 work yet done in a judge-facing Korean document.

**And the claim it withdrew is alive in English, in the file this routine is told to read
every lap.** That is this lap's finding and its root objection.

---

## fix-before-next-row

**Two items. One is a paragraph of annotation; one is a single character.**

1. **WFG-070 (F52)** — `docs/auto/research/RESEARCH_BRIEF_2026-09-03.md:75`, under the
   heading 「**The ten hardest judge questions, with the answers that survive the verdicts**」,
   answers question 7 with 「a satellite trigger would have fired +22/+34/+64 min **after the
   human report** … So the design is **report-first, satellite-confirm**」.
   `docs/auto/research/sweeps_2026-09-03/R3_science_gaps.md:22` says the same. That is the
   claim WFG-053 and WFG-063 spent two laps withdrawing from five surfaces. Neither file
   carries the dated annotation `docs/SESSION19_REPORT.md` was given. Annotate both — do not
   edit them, CHARTER §3 rule 7 — and fix question 10's `Files:` line, which cites
   `docs/auto/AI_DISCLOSURE.md`, retired to `docs/auto/archive/` on 2026-09-04.

2. **WFG-071, the one-character half** — `tests/test_external_figures_carry_their_scope.py`
   accepts `%` and `퍼센트` and not **`％`** (U+FF05, fullwidth), which is what a Korean IME
   produces by default. `목격 신고 99％가 …` walks through the gate shipped this window. One
   character in one character class; the rest of WFG-071 is a row, not a fix-before-next-row.

Otherwise **the table order stands and this lap does not reorder it**. The next `todo` row in
table order is **WFG-003** (finals screen audit + the 5-minute demo script), which has now
been named 「next」 by two consecutive critic laps and started by neither, then **WFG-067**.
**NH-021 is unanswered and its stated default is table order**, so WFG-062 and WFG-071 stay
at P1 and no critic re-decides that by editing a priority column — see the correction at the
foot of `docs/auto/BACKLOG.md`.

---

## fix-this-sprint

### F52 — The withdrawn claim is alive, in English, in the drill brief

**Where:** `docs/auto/research/RESEARCH_BRIEF_2026-09-03.md:75` and
`docs/auto/research/sweeps_2026-09-03/R3_science_gaps.md:22`. **Row: WFG-070 (P0), new, and
the first `fix-before-next-row` item.**

Critic #9 certified its window with this sentence: 「Grepped every `.md` and `.html` in the
tree this lap: the only surviving affirmative-primacy strings are that dated withdrawal block
and §10's own paragraph explaining what its table used to be.」 **It is not true.** The reason
it was missed is the same reason the gates missed it: **both claim families in
`tests/test_detection_ordering_is_not_claimed.py` are Korean-only, and so was the grep.**

| where | what it says today |
|---|---|
| `RESEARCH_BRIEF_2026-09-03.md:75` | 「a satellite trigger would have fired +22/+34/+64 min *after* the human report (FIRMS +117/+151/+17) … So the design is **report-first, satellite-confirm**」 |
| `sweeps_2026-09-03/R3_science_gaps.md:22` | 「GK2A detection floor: +22 / +34 / +64 min **after the human report** (n = 3)」 |

The first is not an archived record in practice. `docs/auto/ROUTINE_PROMPTS.md` tells this
routine to read that file's sections (a) and **(c)** on every lap, and (c) is where the
sentence lives. Its section heading is 「the answers that **survive the verdicts**」. It is the
student's drill material, and a student who reads answer 7 the night before says at the booth
the sentence five other documents were rewritten to stop them saying.

**The structural half, which is the part worth keeping.** `PRIMACY_GUARDED` is five files and
`GUARDED` in the new gate is seven; **neither list contains `README.md`, and neither contains
anything under `docs/auto/research/`**. `paper/manuscript.md` is in the second and not the
first, so the manuscript is guarded for a figure's labels and unguarded for the claim — and
the manuscript is the document going to an IEEE venue. Every token in `BANNED_PRIMACY`,
`PRIORITY_WORDS`, `SOURCE_NOUNS` and `NEGATION_MORPHEMES` is Korean. Half of this repository
is in English and none of it is covered by a sentence-level claim gate.

**What this is not.** It is not a claim that a judge-facing document is wrong today. Every
Korean surface a judge can be handed is clean in meaning, checked again this lap. It is a
claim that the certification 「the tree is clean」 was made by an instrument that can only read
one of the two languages the tree is written in, and that the certification was believed.

### F53 — The third claim gate was built beside the registry that already holds its answer

**Where:** `tests/test_external_figures_carry_their_scope.py` `EXTERNAL_FIGURES` (`:108-147`)
against `docs/NUMBERS.json`. **Row: WFG-071 (P1), new. This is the lap's root objection.**

The new gate is a real improvement and this finding is not about its quality. It publishes
its own catch rate, folds in six escapes a reviewer found, and keeps two it cannot close in
`test_the_escapes_this_gate_cannot_close_are_still_open`, which **fails when the gate starts
catching something the docstring says it cannot**. That is the first instrument in this
repository whose job is to keep its author honest rather than its documents consistent.

What it asks of every guarded block is that the block carry the figure's **agency**, its
**as-of date** and its **scope**. Counted this lap:

| | count |
|---|---:|
| registry keys in `docs/NUMBERS.json` | 312 |
| keys with `provenance: external` | **16** |
| of those, carrying `agency` **and** `as_of` **and** `scope` | **16** |
| figures in the gate's `EXTERNAL_FIGURES` | **2** |
| of those 2, present in `docs/NUMBERS.json` | **0** |

Two registries of external figures now exist: one structured, complete on its three labels,
machine-readable, sixteen deep; and one hand-written in a test file holding the two 경향신문
2023 figures that are in no registry at all. **The gate reads the second and not the first.**

**The cost is not hypothetical and it is six windows old.** Five of the sixteen are printed
today *inside files this gate lists as `GUARDED`* — `docs/auto/JUDGE_QA.md` (99,289 ha, 26명),
`web/finals.html` (3,819동, 3,587명), `paper/manuscript.md` (99,289, 3,819, 3,587, 2,246,
104,788) — where it does not look. One of them is **WFG-051**: `fire2025_chain_deaths` carries
`agency: 중앙재난안전대책본부`, and `paper/manuscript.md:37`, a `GUARDED` file, calls the same
26 deaths 「the **provincial** disaster headquarters' count」.

A check that compared each printed value against **its own key's** `agency` field would have
failed on that line the day it was written. The gate that was built cannot see the number at
all. It would also be **language-neutral**, because it matches a value rather than a sentence,
which is the one property neither hand-rolled family has and is exactly what F52 cost.

### F54 — A critic report says three times that it changed a priority, and it did not

**Where:** `docs/auto/reports/2026-09-04T1005Z-critic.md:33, 134, 148` against
`docs/auto/BACKLOG.md:95`. **No new row; the record is corrected in `BACKLOG.md`.**

Critic #9 wrote 「F47 (WFG-062, **raised P1 → P0**)」, 「build WFG-062's withdrawn-claims
registry」 and, in the section headed 「**Updated, not duplicated**」 whose entire job is to list
what the lap changed, 「WFG-062 (**P1 → P0**, with the 18/20 measurement …)」. The table row
still reads `| WFG-062 | P1 |`, and `git show adf712d -- docs/auto/BACKLOG.md` shows the lap
edited the row's **text** and not its priority column. The same lap's `CRITIC_LATEST.md` says
the opposite of its own report — 「the table order stands and this lap does not reorder it」 —
and refers the question to NH-021.

Both positions are defensible; holding both in one lap is not. And it matters mechanically:
CHARTER §4 step 3 sends the next dev lap to 「the highest-priority backlog row that is `todo`」,
which it reads from the table, not from the report. This is F49's pattern one window on — a
report that cannot describe its own actions — and critic #10 says it about the series before
anything else.

**Critic #10 leaves WFG-062 at P1 deliberately.** NH-021 is the author's open decision, its
stated default is table order, and a critic that re-decides it by editing a column takes the
choice the entry exists to give the author.

### F55 — The measurement the routine asks for, on the gate that shipped

Critic #9's standing instruction is that a new claim gate is graded against a mutation set its
author did not write, and the rate printed. The 1045Z lap did this for its **first draft**
(12 / 20, measured by its reviewer) and then folded six of the eight escapes in as rules, so
the **shipped** version was unmeasured by anyone outside it. Critic #10 wrote twenty fresh
blocks — none of them in `INCOMPLETE_BLOCKS`, ten per registered figure, each an ordinary
Korean sentence printing the figure with no agency, no date and no scope — and ran them
against the shipped patterns:

| detector | caught |
|---|---:|
| `test_external_figures_carry_their_scope.py`, shipped | **14 / 20** |
| (`test_detection_ordering_is_not_claimed.py`, critic #9's set, for scale) | 2 / 20 |

**14 of 20 is a large, real improvement and it should be read as one.** The six escapes:

1. **`99％`** — U+FF05, fullwidth. The class is `(?:%|퍼센트)`. A Korean IME produces ％ by
   default. **One character, and it is a `fix-before-next-row` item.**
2. the figure restated as a count — 「산불 신고 100건 가운데 **99건**이 목격 신고였습니다」;
3. 목격 paraphrased — 「전체 신고의 99%가 **눈으로 본 사람의** 신고였습니다」;
4–6. the camera figure with no digit beside 최초 — 「카메라가 먼저 찾아낸 산불은 **한 건도
   없었습니다**」, 「단 한 건의 산불도 **먼저 발견하지 못했습니다**」, 「**인지한 최초 산불: 0건**」.

Only the first is cheap. Escapes 2–6 are the class the docstring already names and refuses to
claim — 「a paraphrase that carries no digits」 — and finding five more instances of an admitted
limit is a measurement, not a rebuttal. It is the reason WFG-071 asks for the registry rather
than a seventh regex.

### F56 — Carried, verified unchanged, with the checks that were run

- **WFG-051 (F46)**, P0, **sixth window**, and the oldest live defect in the tree. Now with
  the fourth document: `docs/NUMBERS.json` → `fire2025_chain_deaths` `agency:
  중앙재난안전대책본부`; `README.md:198` and `:510` 「경상북도 최종 집계·중앙재난안전대책본부
  확인」; `docs/data_sources.md` 경상북도 재난안전대책본부; `paper/manuscript.md:37` 「the
  provincial disaster headquarters' count」. One number, three attributions, and nothing in
  this repository supporting the 중대본 confirmation. **The booth is not exposed:** `JUDGE_QA.md`
  Q30b (T1) now names the disagreement, names WFG-051, and tells the student not to assert one
  agency. That is the honest interim answer and it is why this is still a row and not a
  `fix-before-next-row`.
- **WFG-067 (F41)**, P0, **third window**, on a ☑ line. `git cat-file -t a562045` in this fresh
  clone still answers `fatal: Not a valid object name`; `web/finals.html` still carries
  `"git":"a562045"`. Nothing in this window touched `web/`. `JUDGE_QA.md` Q35 answers it
  honestly at the booth.
- **WFG-057 (F49)**, P0, **fifth window**, and it did not move. Counted at `3a70e16`: header
  says 33 / 14 / 13 / 6, file holds **41 / 15 / 19 / 7**. **It is now blocking this routine's
  own output for a second lap:** the routine prompt says a judge-drill question no file can
  answer becomes a backlog row *or a `JUDGE_QA.md` entry*, and adding a 42nd question to a file
  that says 33 makes the defect worse by the hand of the lap reporting it. Critic #9 declined
  for that reason and so does this one. Two consecutive critic laps have now been unable to use
  half of step 3 of their own prompt; that is a cost this row has not been priced at.
- **WFG-065 (F38)**, **fourth window**. 8.2 km h⁻¹ is still only in
  `docs/auto/knowledge/PYROGEOGRAPHY.md`, the backlog and four critic reports. Checked by
  `git grep` over `docs/*.md`, `paper/`, `web/` and `README.md`.
- **WFG-056 (F50)**, **third window**. `--assert-reported` run this lap against six bases in
  the window — `3a70e16`, `613ff3c`, `05691d6`, `c57ef90`, `197dae3`, `adf712d` — and all six
  exit 0, all six naming `docs/auto/reports/2026-09-04T1045Z-dev.md`, **including
  `--base adf712d`**, the commit that carried critic #9's own report. Third critic lap that
  cannot perform the verification its prompt asks for, and the third to say so rather than
  report a pass.
- **What this lap *can* verify from the report files:** every dev report in the 24-hour window
  carries a `Reviewed by:` line except `docs/auto/reports/2026-09-04T0401Z-dev.md` (critic #7's
  F40, unchanged, a record). The 1045Z lap's reads `Reviewed by: subagent (block, then fixed)`.
- **WFG-054, WFG-055, WFG-050, WFG-048, WFG-044, WFG-038 / WFG-039, WFG-068, WFG-066** —
  unchanged; nothing in this window touched them.

---

## note

- **N57 · The best thing in the window is a test written to fail when its own docstring stops
  being true.** `test_the_escapes_this_gate_cannot_close_are_still_open` asserts that two
  named sentences are **not** caught, so a later lap that widens the rule past what it can
  defend fails here and has to correct the docstring and the report together. Most
  repositories document a limitation in prose and let it rot. This one made the limitation
  executable. It is the reason F53 is a row about where the gate reads from and not a
  complaint about the gate.
- **N58 · The lap graded itself down in public and was right to.** The 1045Z lap's first draft
  defended itself with the argument that a closed registry of literal figures is immune to the
  2-of-20 result, 「a sentence escapes it only by not containing the figure」. Its reviewer
  measured 12 of 20 and the docstring now says, in the lap's own words, 「**That argument is
  false and the reviewer measured it**」. A loop that writes its own refuted argument into the
  file is doing the thing this project is selling.
- **N59 · `factchk` on this window's new world-claims: all of them hold.** The window asserts
  five things about the world, all from 경향신문 2023-04-28, and this lap opened the article:
  152 cameras ✓ (「경북에는 152개의 산불감시카메라가 설치돼 있다」), 대당 6천만 원 ✓ (「대당
  6000만원 정도다」), 최초 발견 0건 ✓ (「감시카메라로 산불을 먼저 발견한 건수는 '0'건
  이었다」), the 0건 period covering 2022 and the year to 2023-04-28 ✓, and the 99 % figure
  carrying the article's own 「올해」 ✓, which is what makes it the interim tally §0 now labels.
  Nothing was overstated and one thing was **narrowed** correctly: the article says 152개 and
  §0 writes 152대, which is the same count in the classifier a Korean reader expects.
- **N60 · The census is comparable for a fourth window.** `1312 → 1342` cold to cold, `+30`,
  skips unchanged at 62. WFG-039 has now reproduced in five consecutive laps; it is still
  `todo`, still P1, and the reason it has not hurt anyone is that four laps in a row have
  quoted their readings with a temperature by hand.
- **N61 · Eleven windows without a commit to `web/`, and the demo script is the row that keeps
  being named next.** Three of eleven `KCF_READINESS.md` lines are ticked. WFG-003 has been
  「the next row in table order」 in two consecutive critic laps and neither dev lap in between
  took it; both took a claim-gate row instead. That is not a rule violation — WFG-069 was a
  `fix-before-next-row` item and clearing it first is exactly what CHARTER §11 asks — but it is
  the second time the mechanism has spent the booth's lap, and NH-021 is the entry that exists
  to let the author say whether to keep paying for it.

---

## The judge drill

Ten questions, answered using only files in the repository.

| # | question | can a file answer it? |
|---|---|---|
| 1 | 「이 문서 첫 줄의 카메라 152대·0건은 어느 기간 이야기입니까?」 | **Yes, and it could not last window.** `docs/detection_floor.md` §0 gives agency, article date, URL and the period the 0건 covers. Critic #10 opened the article and every element holds. WFG-069 closed |
| 2 | 「그러면 왜 사람 신고를 일차 소스로 둡니까?」 | **Yes.** The premise is refused in one sentence, identical in Q10, Q10d, `detection_floor.md` §10, the booth card and the screen |
| 3 | 「그 문장이 영어로 되살아나면 무엇이 잡습니까?」 | **No, and it already has.** Both claim families are Korean-only; the claim is alive at `RESEARCH_BRIEF_2026-09-03.md:75` and `R3_science_gaps.md:22`. F52, WFG-070, the first `fix-before-next-row` item |
| 4 | 「외부 수치가 기관·기준일·범위를 달고 있는지 무엇이 확인합니까?」 | **Partly, and now measurably.** The new gate covers **2** figures; `docs/NUMBERS.json` holds **16** external keys all carrying those three fields, five of them printed inside the gate's own `GUARDED` files. Outside catch rate 14/20. F53, WFG-071 |
| 5 | 「사망 26명은 어느 기관 집계입니까?」 | **Half**, sixth window. Four documents, three attributions (WFG-051) — but Q30b tells the student the disagreement exists and forbids asserting one. The booth answer is honest; the tree is not consistent |
| 6 | 「화면 아래 「commit a562045」 로 이 화면을 다시 만들 수 있습니까?」 | **No**, third window, and the bank says 「아니오」 honestly at Q35 with what *is* reproducible. WFG-067 |
| 7 | 「Q&A 카드는 몇 문항이고 그중 몇 개를 외워야 합니까?」 | **No.** Header says 33 / 14 / 13 / 6; the file holds **41 / 15 / 19 / 7**. F56, WFG-057, fifth window |
| 8 | 「이 산불의 확산 속도는 시간당 얼마였습니까?」 | **No file a judge can be shown.** Q34 answers honestly (「저희가 측정한 값이 아닙니다」). WFG-065, fourth window |
| 9 | 「5분 시연 대본이 있습니까? 부스 노트북에서는 어떻게 띄웁니까?」 | **No, twice.** `docs/auto/DEMO_SCRIPT_5MIN.md` and `docs/auto/finals/BOOTH_SETUP.md` do not exist (R4 ☐, R3 half ☐). WFG-003, WFG-037 |
| 10 | 「제출용 번들을 하나로 받을 수 있습니까?」 | **No.** `release/` does not exist (R9 ☐, WFG-036, plan date 09-10). Three of eleven `KCF_READINESS.md` lines ticked |

**No question was added to `docs/auto/JUDGE_QA.md` this lap.** Questions 3 and 4 have no answer
in a file and both became backlog rows instead, because WFG-057 is open and a 42nd question
under a header that says 33 makes the defect worse by the hand of the lap reporting it. That is
now two consecutive critic laps unable to use half of their own step 3, and it is recorded as a
cost of WFG-057 rather than as a preference.

---

## What five lenses converged on

| lens | verdict | the one load-bearing reason |
|---|---|---|
| KCF judge · SW professor | **pass**, held | Green at HEAD for a seventh window, `1342 / 62` cold, and the window contains a test that fails when its own docstring stops being true. Show me `test_the_escapes_this_gate_cannot_close_are_still_open` and I will believe the rest of the suite. What stops it being a rise: you have written three separate hand-rolled string families in three windows, and the fields the newest one demands are already columns in a JSON registry you wrote yourself. That is not a gate problem, it is an architecture answer you keep declining to give |
| KCF judge · 재난 대응 공무원 | **pass**, and this is the window it improved | Last window I said fix the first sentence of the design document before you show it to me. You did, and you fixed it by replacing an opinion with a count — 152 cameras, zero first detections, and the two years that covers. That is the sentence I would have written. I still cannot get one answer about who counted the 26 dead, and that is the number I would be asked about in my office |
| fire-behaviour scientist | **pass**, unchanged and still short of strong | Nothing about fire behaviour moved this window, for a fourth window. 8.2 km h⁻¹ is still the number that characterises 의성 and it is still in a note I would not be handed. The size floor is still given as an order of magnitude, which is still the right instinct |
| ML reviewer (leakage, baselines) | **pass**, and `mandela` fires on the same axis as last window | No model, split, metric, arm or eval moved, so nothing fires in the science. On the instrument: the lap **fixed** pattern #4 — its mutation set was written by a reviewer who had not seen the patterns, and the rate was published. Then it folded six of the eight escapes in as parametrised cases, which converts external ground truth into internal ground truth, and the file says so out loud. The shipped version was therefore ungraded until this lap ran twenty fresh blocks: **14 / 20**. Keep doing exactly this, and note that the leak closes permanently only when the ground truth is a registry field rather than a sentence someone wrote |
| statistician | **pass**, and the complaint is now three windows old | Fourth comparable cold census, `+30`, temperature stated: a habit, and I credit it. Against it: the bank still miscounts itself by eight, fifth window; `--assert-reported` gave me six zeros for six different bases naming one report, third window; and this window a report asserted three times that it changed a priority column that it did not change. Three of your instruments returned a value that does not depend on the thing being measured, and one of them was a report about a report |

**Where they agree:** the §0 rewrite is the best sentence-level work in the window and the
lap's public self-downgrade is the best process work. Four of five named one or the other
unprompted.

**Where they split:** the professor and the ML reviewer are looking at where the next gate
should read from and want the registry; the 공무원 and the statistician are looking at two
documents in front of them — the 26 deaths' agency and the bank's header — and both have been
wrong for five and six windows while three windows of engineering went into claim gates.

---

## The root objection, and its cheapest test

Critic #4 asked which numbers can be wrong without a gate noticing. #5 asked which sentences.
#6 asked which sentences the repository already knows are wrong. #7 asked why eight windows had
never touched what judges look at. #8 asked why every gate points away from the screen. #9
asked whether a bigger string gate is the right instrument at all. This one is narrower, and it
is the constructive half of #9's question:

> **The loop keeps building the gate beside the registry instead of on it.** Three hand-rolled
> string families now guard prose. The newest asks every guarded block to carry a figure's
> **agency**, **as-of date** and **scope** — the exact three fields `docs/NUMBERS.json` already
> stores, and stores for **all sixteen** of its external figures. It reads none of them; it
> hand-writes a second registry holding **two** figures that are in no registry at all. Five of
> the sixteen are printed inside files the gate itself lists as guarded, where it does not look,
> and one of those five is **WFG-051**: the registry says the 26 deaths are 중앙재난안전대책본부's,
> and `paper/manuscript.md:37` — a guarded file — calls them 「the provincial disaster
> headquarters' count」. A gate that compared a printed value against its own key's `agency`
> field would have failed on that line the day it was written, and would have been
> **language-neutral**, which is precisely what F52 cost: the claim the loop spent two laps
> withdrawing is alive in English in the file this routine is told to read every lap, because
> every token in both claim families is Korean.

**The cheapest test, and it is one function inside one lap:** iterate `docs/NUMBERS.json` for
`provenance == "external"`; for each guarded file, for each block printing that key's value in
the spelling the document uses, require a token from that key's own `agency` / `as_of` /
`scope` in the same block or a `scope-ok:` pragma naming the key. **Print the number of failing
blocks on the current tree before fixing any of them.** If WFG-051's manuscript line is among
them, the instrument is right and both hand-rolled families should migrate onto it. If the
output is mostly noise, that is the more valuable answer, and WFG-030's shape — every
judge-facing claim sentence cites a registry key or an artifact — is the right instrument
instead.

**And it is still not this lap's call which comes first.** WFG-071 is one lap, and the rows it
would displace are the booth ones: no demo script, no booth recipe, no bundle, eleven windows
without a commit to `web/`. That trade is **NH-021**, asked on 2026-09-04, due 09-06, and
unanswered — as are sixteen other entries across twenty-nine report emails. Until it is
answered the backlog table order stands, and this lap changed no priority.
