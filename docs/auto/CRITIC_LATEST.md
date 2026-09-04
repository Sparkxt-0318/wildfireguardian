# CRITIC_LATEST — critic #7, 2026-09-04T0547Z

Window `b855943..8e0a6ad` on `auto/dev`. Written by the `wfg-autoloop-critic` routine.
The next dev lap clears every `fix-before-next-row` item here before claiming a row.

**Verified independently this lap:** `gates.py --mode full` exits **0** at `8e0a6ad` in a
fresh cloud sandbox. `1261 passed, 62 skipped` in 167 s, **COLD** (first full run in this
sandbox, so the six SRTM-gated tests skipped; WFG-039). `verify`, `snapshot-verify`,
`env-check` PASS; `baseline-verify` WARN, expected off-laptop, `hard: false`, seventh lap
running and still not a finding. Against critic #6's cold reading at `b855943`
(`1240 passed, 62 skipped`) that is **+21 passed, skips unchanged** — a like-for-like
comparison, both cold, which is the first time this series has had one.

---

## fix-before-next-row

**None. This is deliberate, and it is the whole point of this report.**

Every finding below is filed as a backlog row at its own priority and **placed below
WFG-017 in the table**. Nothing here needs to jump the queue, and the next dev lap should
take **WFG-017** — the finals screen.

Three critic laps running have named the finals screen the sprint's largest risk and then
handed the next lap a `fix-before-next-row` item that was not the screen. Critic #6 did it
for good reason (F27 was a false sentence on the card WFG-017 would have put on that
screen, and it said so). That reason is spent: F27 is closed and verified line by line.
A fourth lap of "the screen is the risk, now go fix this instead" would be this critic
writing the risk and causing it.

---

## fix-this-sprint

### F35 — The trigger recommendation lost its evidence, and the T0 answer kept the evidence that was withdrawn

**Where:** `docs/auto/JUDGE_QA.md:240` (Q10, **T0**); `docs/detection_floor.md:310` (the
ban) and `:319` (§10 row 1); `docs/auto/finals/DETECTION_FLOOR_CARD.md:28` and `:78`.
**Row: WFG-063 (P0).**

This is F27's shape, one window later, and the loop created it while fixing F27.

WFG-053 withdrew the detection-ordering claim across four judge-facing documents. Correct,
gated, and no number moved. But the ordering was also what supported the *other* half of
`docs/detection_floor.md` §10 — the recommendation that **사람 신고** be the **primary**
trigger source. With it gone, §10 reached for 「신고의 99 %가 목격 신고」. That lap's own
reviewer then showed the 99 % is an unregistered year-to-date interim (경향신문 2023-04-28),
had it struck from the booth card, and §10 gained a bold paragraph at `:310` stating that
this value may not carry a conclusion, citing CHARTER §3 rules 3 and 5b.

Two things were left standing.

1. **Q10 was not re-read.** Line 240 still names 「크기 바닥과 「신고의 99 %가 목격 신고」라는
   통계」 as the two grounds for 신고 우선 — the exact statistic forbidden 70 lines away in
   the file Q10 cites as its 근거. The card refuses it; the design doc forbids it; the
   sentence a **T0** answer tells the student to say rests on it.
2. **The remaining ground does not carry the claim, and this is the larger half.** The size
   floor says a 2 km pixel cannot resolve a fire below roughly a hectare. That rules the
   **satellite out** as an ignition-scale trigger. It says nothing about whether the human
   channel is fast, complete or primary. So `detection_floor.md:319`'s
   「일차 소스로 설계해야 합니다」 and the card's 「사람 신고가 일차」 are, as of this window,
   design recommendations with **no support in any judge-facing document in this
   repository**.

The fix is one claim-shape change and no number moves: say
「정지궤도 위성을 **일차** 트리거로 둘 수 없습니다」, which the measurement carries, and stop
saying who *should* be primary, which it does not. `JUDGE_QA.md` Q10d is added this lap with
the ⭕/❌ lines so the booth is safe before the row lands. `tests/test_detection_ordering_is_not_claimed.py`
guards the *ordering* sentence and cannot see this one, which is WFG-062's case made twice.

### F36 — Two of the seven restyled figures have colliding labels, and the lap said all seven were looked at

**Where:** `paper/figures/F2_lofo_auc.png`, `paper/figures/F7_dispatch_ordering.png`.
**Row: WFG-064 (P1).**

The Moreno restyle is real and F7 panel a is the best figure in the paper. Opened all
seven this lap; two carry defects that the claim in
`docs/auto/reports/2026-09-04T0401Z-dev.md` (「All seven figures regenerated and looked at」)
should have caught:

- **F2.** The Uiseong-Andong bar label `0.878` sits at x ≈ 0.878 and the red
  「mean of folds 0.89」 rule at x = 0.89, so the dashed line is drawn **through the label's
  last digit**. The 「pooled 0.905」 annotation is placed at the axes floor and overlaps the
  x-axis line and its tick labels.
- **F7.** Panel b's 「deadline first wins」 teal is the same teal as panel a's
  「nearest first」. One figure, one colour, two meanings.

The rubric row this costs is not a detail: 「그래픽 및 범례의 명확성」 is the literal wording of
제출 자료 in both tables, and F2 is the figure the LOFO result leads with.

### F37 — A bibliographic record was written from memory, in a repository whose rule 5 is "no fabricated citations"

**Where:** `docs/auto/knowledge/PYROGEOGRAPHY.md:169`. **Row: WFG-066 (P1).**

The entry is tagged `[UNVERIFIED — not opened; author list from memory]`. This lap checked
it and **every field is correct**: Sullivan, A. L., Sharples, J. J., Matthews, S.,
Plucinski, M. P. (2014), *Environmental Modelling & Software* **62**: 153–163, confirmed
against the FRAMES catalog record <https://www.frames.gov/catalog/53980> and the
ScienceDirect listing, both opened 2026-09-04.

So nothing is wrong today, and the row is small. It is filed because the tag does not
distinguish "I could not open the page that supports this claim", which is honest and
appears nineteen other times in these two notes, from "I produced a bibliographic record
without a source", which is a different act. CHARTER §13 should say so in one line before
the research routine extends these notes weekly.

### F38 — The most quotable fire-behaviour figure about the motivating event is in no judge-facing document

**Where:** `docs/auto/knowledge/PYROGEOGRAPHY.md:45`. **Row: WFG-065 (P1).**

8.2 km h⁻¹ forward spread for the 의성 fire, computed by 국가산림위성정보활용센터 from
satellite thermal detections and reported as the highest rate recorded for a Korean
wildfire. A fire-behaviour judge asks this before anything about the model. It exists in
one knowledge note and in no README paragraph, no `docs/data_sources.md` row, no registry
key and, until this lap, no Q&A answer.

CHARTER §13 is why it has not migrated, and **that rule is working correctly** — the note
did not leak into judge-facing prose, which this lap checked for seven figures across the
notes and found zero migrations. The fix is to register it, not to quote it. `JUDGE_QA.md`
Q34 is added this lap as 「근거 없음」 with the honest interim answer, which is
「that is not a value we measured」.

⚠ One half does not verify. The note's 「1.5×, against 고성 2019's 5.2 km h⁻¹」 comparison did
**not** come back in this lap's search; the 8.2 figure did. The comparison must not travel
with the figure into the registry.

### F39 — The last report of the window shipped with its own gate table marked stale

**Where:** `docs/auto/reports/2026-09-04T0501Z-dev.md:74`.

The committed report says, in the loop's own words:
「⚠ **stale: the gates read `6b2b969`, HEAD is `b6caa9b`** — this table does not certify the
pushed tree; re-run `gates.py --mode full` and `gates.py --assert-head` before pushing」.
The branch then moved once more, to `8e0a6ad`, which changed `docs/horizon_grounding.md`
and `tests/test_detection_ordering_is_not_claimed.py`.

**The tree is fine** — this lap re-ran the full gates at `8e0a6ad` and it is green, and
`8e0a6ad` turns out to be a pure WFG-058/059 → WFG-061/062 renumber in prose and one test
docstring. So no defect reached the branch. What reached the author is a report whose gate
table certifies nothing, carrying the machinery's own warning that it certifies nothing.
`report.py`'s stale marker did exactly its job (critic #3's F14 working as designed) and the
lap pushed past it. Not filed as a new row: WFG-056 (F32, commit a push ledger) is the
durable fix and is already open, and CHARTER §4 step 8 already forbids this in as many
words. Recorded so the next lap that sees a stale marker treats it as a stop, not a note.

### F40 — One dev report in the window records no reviewer at all

**Where:** `docs/auto/reports/2026-09-04T0401Z-dev.md`.

`docs/auto/LOOP_CONFIG.json` → `review` is `subagent`. Every other dev report in the 24-hour
window carries a `Reviewed by:` line, and the two laptop laps critic #6 noted at N39 both
declared `self` and said why. This one carries **no line at all** — not `subagent`, not
`self`, not a reason. It is also the largest prose commit of the window: about 14,000 words
of new world-claims across four knowledge notes, `paper/style.py` rewritten and all seven
figures regenerated. F36 is what an independent reader would have caught in one look at F2.

Not a new row: this is CHARTER §4 step 5 as written, and the remedy is a lap reading it.
Recorded because critic #6 wrote at N39 that 「I ran outside the routine」 should not become a
standing exemption, and one window later a laptop lap recorded no reviewer at all.

### Carried, unchanged, from earlier windows

- **WFG-051 (F23, F30) — third window open, and it is now the oldest live defect a judge
  can find.** 사망 26명 is a 중앙재난안전대책본부 count in the registry, a 경상북도
  재난안전대책본부 count in `docs/data_sources.md:190`, and 「the provincial disaster
  headquarters' count」 in `paper/manuscript.md:36-38`, and the README link a judge would
  click still carries no death figure. P0 since critic #6. Nothing in this window touched it.
- **WFG-054 (F28) — second window open, and it was a `fix-before-next-row` item that was
  not fixed.** The 0501Z lap cleared F27 and named WFG-054 as its next row, which is a
  reasonable call inside one lap; the paper and laptop laps then took the window. It matters
  because `decisions.py apply` marks an author reply read even when it recorded nothing, and
  **the author has still never replied**, so the very first reply is the one at risk.
- **WFG-055 (F29)** — `check_paper` reports `body_words: 7479` against a 7,500 hard fail,
  unchanged this window. 21 words of headroom, measuring a proxy for a page limit nobody has
  calibrated.
- **WFG-057 (F34), WFG-038/039, WFG-050, WFG-044** — all unchanged.

---

## note

- **N41 · The window's best act is a withdrawal.** WFG-053 took a headline verdict the
  project liked (「위성은 사람보다 느렸습니다」), found the clock under it unsourced, and
  removed it from four documents without moving a single number or registry key. Then the
  same lap's reviewer blocked it twice more, and the second block was the row repeating its
  own defect — promoting an unregistered interim statistic onto the booth card in the
  withdrawn claim's place. The lap took both blocks. F35 exists because the *third* instance
  of that pattern, one file over, was not caught; it does not diminish the first two.
- **N42 · The knowledge base did not leak, and that is the result worth recording.**
  14,000 words and about 110 references landed in one lap under CHARTER §13, which says
  notes are prose and their figures do not migrate without the registry. Checked seven of
  the most quotable figures (8.2 km h⁻¹, 51 km ember transport, 7.1 km h⁻¹, WUI +41 %,
  48.3 % late evacuation, the 6.17 units km⁻² WUI threshold) against `README.md`,
  `JUDGE_QA.md`, `paper/manuscript.md`, `docs/MODEL_CARD.md` and `docs/auto/finals/`:
  **zero migrations.** The three-tier `[opened]` / `[abstract]` / `[UNVERIFIED]` scheme is a
  sourcing discipline no rubric asked for. F37 is one phrase inside an otherwise honest
  apparatus.
- **N43 · The 8.2 km h⁻¹ figure checks out; its comparison does not.** Searched this lap:
  the 8.2 km h⁻¹ spread rate from satellite thermal detection, and its framing as the
  highest reported for a Korean wildfire, both come back. The 「1.5× 고성 2019's 5.2 km h⁻¹」
  half did not. Recorded in WFG-065 so the registration does not carry the unverified half.
- **N44 · The dispatch-ordering result is the most honest thing in the repository and it
  should be rehearsed, not buried.** `paper/manuscript.md` §4.6 is titled 「a dispatch
  ordering that does not work」; the abstract says it at `:21`; `:88` lists it as the
  non-claim; F7 panel b shows the shipped ordering winning **0 of 180** committed cells and
  losing 92; `JUDGE_QA.md:416` answers it. That is a contribution reported as negative, in
  the abstract, with the figure. Four of five lenses this lap named it unprompted as the
  reason they would trust the rest.
- **N45 · WFG-038/039 reproduced again, and this time the comparison is clean.** This lap
  ran one cold full-suite pass and quotes it as cold (`1261 passed, 62 skipped`), against
  critic #6's cold `1240 / 62`. Both cold, so +21 passed is a real number. Every census in
  this series should carry the word until WFG-039 makes the SRTM download opt-in.
- **N46 · `baseline-verify` WARN, seventh window, still not a finding.** Two git-ignored
  laptop-only manifests, `hard: false` by construction.

---

## The judge drill

Ten questions, answered using only files in the repository.

| # | question | can a file answer it? |
|---|---|---|
| 1 | 「그 22분·34분·64분은 신고 기준입니까, 발화 기준입니까?」 | **Yes, and it could not last window.** Q10c is now the standard answer, the card's front matter states it, and `detection_floor.md` §1 quotes the manifest's own `provenance only` sentence. F27 closed |
| 2 | 「그러면 왜 **사람 신고**를 일차 소스로 둡니까?」 | **No, and two documents assert it anyway.** F35. Added as **Q10d (T0)** with the ⭕ line the student may say and the ❌ lines they may not |
| 3 | 「이 산불의 확산 속도는 시간당 얼마였습니까?」 | **No file a judge can be shown.** F38. Added as **Q34 (T2)**; the honest answer is 「저희가 측정한 값이 아닙니다」 |
| 4 | 「사망 26명은 어느 기관 집계입니까?」 | **No.** Three agencies in three documents, third window (WFG-051). Unchanged |
| 5 | 「부스에서 무엇을 보여 주십니까?」 | **Not from a file.** `web/` untouched since 2026-09-02. WFG-017, and it is next |
| 6 | 「오경보율은 몇 %입니까?」 | Yes — `0 of 709` as an upper bound with its scope, on the card and in the paper. See the 재난 공무원 lens for what a judge does with the number after that |
| 7 | 「출동 순서 정렬이 실제로 효과가 있습니까?」 | Yes, and the answer is **no, and we report it** — §4.6, the abstract, F7 panel b, `JUDGE_QA.md:416`. The strongest answer in the bank |
| 8 | 「임계값에서 실제 발화의 몇 %를 잡습니까?」 | Yes — Q1, pooled 0.138, three folds with no true positive, in the model card above the AUC |
| 9 | 「낯선 사람이 이걸 다시 돌릴 수 있습니까?」 | Yes, and this lap is the data point: fresh sandbox, bootstrap in about a minute, 1,261 tests green |
| 10 | 「논문은 20쪽 제한 안에 들어갑니까?」 | **No.** The gate measures words, CHARTER §12 states pages, the conversion is uncalibrated and the loop's own recount says about 21 pages (WFG-055) |

---

## What five lenses converged on

| lens | verdict | the one load-bearing reason |
|---|---|---|
| KCF judge · SW professor | **pass** | Green at HEAD for a fourth window, 1,261 tests, and a loop that withdrew its own headline verdict across four documents without moving one number. The machine is the strongest part of this entry and the student can show it in ninety seconds |
| KCF judge · 재난 대응 공무원 | **fail**, and on a different sentence than last time | Last window I refused the card because it told me the satellite was late. That is fixed, properly. Now the card tells me to build the trigger with 사람 신고 first, and when I ask why, the answer is that the satellite cannot see small fires. That is a reason not to trust the satellite; it is not a reason to trust the telephone. I run the room where those calls land and I know its miss rate; you have not measured it. Also: your false-alarm bound is 「낮음」 at about three a day. Three a day is a desk that stops reading your alerts in a week |
| fire-behaviour scientist | **pass**, and it is close to a strong pass | The withdrawal is the right instinct and §4.7's size floor is given as an order of magnitude because the flame-temperature assumption moves it eightfold. What keeps it off strong: you have read 8.2 km h⁻¹, the number that characterises this fire's behaviour, and I cannot find it in anything you would hand me |
| ML reviewer (leakage, baselines) | **pass** | Ran `mandela` over the window. No model, split, metric, arm or eval moved, so it fires on nothing new. The 709-step control still reports zero as an upper bound with its scope. The negative result on the shipped dispatch ordering is in the **abstract**, which is where I look to find out whether a paper is honest, and it is there |
| statistician | **pass**, first time in this series | Last window I failed you for holding two answers to one question, twice. One of those is closed and gated. The other, the 26명 attribution, is unchanged and is now three windows old, so I am not giving you more than a pass. But the direction reversed, and 「+21 passed, both readings cold」 is the first census in this series I can actually compare |

**Where they agree:** the withdrawal, and the dispatch-ordering result. Four lenses named
one or the other unprompted as the reason they would trust the rest of the work.

**Where they split:** one lens fails, and it fails on the same document as last window for
the opposite reason. The card no longer says more than it can about *who was late*; it now
says more than it can about *who should be first*. Both times the loop fixed one clause of
a two-clause sentence.

---

## The root objection, and its cheapest test

Critic #4 asked which numbers can be wrong without a gate noticing. #5 asked which
sentences. #6 asked which sentences the repository already knows are wrong. This lap's is:

> **Every one of the last eight windows improved the evidence behind the project, and not
> one of them touched the thing five judges will look at for five minutes.** The
> spread-forecast contribution is honest and weak at its operating point; the dispatch
> ordering is honestly reported as not working; the decision layer is the one contribution
> that could still carry the booth, and it exists as five Markdown cards that have never
> been put on a screen.

Two corrections this objection owes the record, because three critic laps overstated it:

1. **The loop is not behind schedule.** The sprint plan dates WFG-017 at **09-07**; today is
   09-04; every row dated 09-04 and 09-05 is `done`. Calling WFG-017 「the single most
   overdue thing in the sprint」 was wrong when it was written.
2. **「Eighth consecutive window」 counts critic windows, not missed dates.** The honest
   statement is narrower and still serious: `web/finals.html` has not been opened by this
   loop since 2026-09-02, so **the cost of the first attempt is unknown**, and it is the one
   remaining P0 whose duration nobody has measured.

**The cheapest test, and it is one lap:** take WFG-017. Not to finish the screen — to find
out what it costs. If the five cards go on in one lap, the risk was imaginary and the loop
has ten days of slack. If they do not, that is discovered on 09-04 with eleven days left
rather than on 09-12 with three, and every one of the rows above can wait for it.

That is why this report hands the next lap **no** `fix-before-next-row` item.
