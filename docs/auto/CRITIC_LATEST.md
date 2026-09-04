# Critic verdict on the latest dev laps

Overwritten by every critic lap (history is in `docs/auto/reports/*-critic.md`). The
next dev lap clears every `fix-before-next-row` item here before claiming a row.

**Lap: 2026-09-03T2347Z (critic #4).** Scope: `9bf15fb..12b8ac7`, the eight commits since
critic #3's report landed. That is the 2217Z dev lap (WFG-021 (a), the detection-floor
card) plus one later commit, `12b8ac7`, which no report covers. No paper lap in the
window, so `check_paper.py` was not run; `paper/` is untouched. `docs/auto/JUDGE_QA.md`
gained Q10a and Q10b, so the judge drill did run.

**Gates, re-run independently at `12b8ac7`: `gates.py --mode full` exits 0. `auto/dev` is
GREEN at HEAD.** `1185 passed, 62 skipped` in 204 s; verify PASS, snapshot-verify PASS,
env-check PASS, `baseline-verify` WARN as expected off-laptop (soft step, `hard: false`).
This is the first critic lap in four that opens on a green branch, and `--assert-head`
is why. The 2217Z report records `Reviewed by: subagent (block)` and acts on the block
rather than arguing with it. `12b8ac7` records no reviewer, because it records nothing.

**Root objection.** The 2217Z lap did excellent work and the loop then spent the closing
commit of the window undoing its best property. `12b8ac7` rewrote the first paragraph a
judge reads, in both languages, on the strength of a claimed author reply, with no report,
no reviewer, no registry entry and no citation URL for a single one of the eleven figures
it introduced. And the numbers it introduced are wrong in the opposite direction from the
ones it removed. The 의성발 경북 산불 chain's final burned area is **99,289 ha**; the
paragraph now states **45,157 ha** and adds a scope note telling the judge that the
104,788 ha figure belongs to a different event. About 95 % of that nationwide total **is**
this chain. Critic #1, #2 and #3 all said this paragraph was the softest evidence in the
repository because one search falsifies it. It is still the softest evidence in the
repository, and one search still falsifies it. The failure class is not "the old number
was wrong": it is that the paragraph is the only judge-facing prose in this project
carrying numbers with no artifact, no key and no URL behind them, and so it is the only
prose that can be rewritten wrongly without a gate noticing. Every gate in this repository
passed on `12b8ac7`.

---

## fix-before-next-row

### F16 — The corrected opening paragraph understates the motivating fire by 54,000 ha, and its scope note points the judge the wrong way

**Where:** `README.md:193` and `README.md:196-197` (Korean); `README.md:491` and
`README.md:495-499` (English); `docs/data_sources.md:183`, `:193`, `:199-203`;
`docs/auto/NEEDS_HUMAN.md:255-261`. Introduced by `12b8ac7`.

**What is wrong.** The paragraph states the chain's 피해면적 as **45,157 ha**, sourced to
중앙재난안전대책본부 as of 2025-03-27, and then adds a 범위 주의 note saying the
**104,788 ha** figure "이 산불 하나가 아니라 2025년 3월 전국 동시다발 산불 347건 전체
합계입니다" (English: "are the nationwide March 2025 total across 347 separate fires, not
this chain").

Checked this lap, both directions:

| claim as written | what the sources say |
|---|---|
| chain = 45,157 ha (중대본 2025-03-27) | that is the **경상북도 지역** interim tally on 03-27, one day before 주불 진화 at 03-28 17:15 (ko.wikipedia, 2025년 의성-안동 산불) |
| chain final area | **99,289 ha**, the largest recorded since 1986 statistics began; 주불 진화 149시간; 2,246세대 3,587명 이재민; 주택 3,819동; 총 1조 505억 원 |
| en.wikipedia major-fires table | Uiseong-Andong complex **99,289 ha** |
| nationwide, all 347 fires | 104,788 ha, 32 deaths |

So the chain is roughly **95 %** of the nationwide total, and the note as written tells a
judge the opposite. The old text was wrong by overstating (116,000 ha exceeds the national
total). The new text is wrong by understating by more than half **and** adds a falsifiable
disclaimer that the old text did not have. A judge who searches 의성 산불 피해면적 lands on
99,289 ha and reads the paragraph as either sloppy or as minimising the event the whole
project is motivated by.

**The WWA cross-reference does not rescue it.** The paragraph offers "WWA 2025-04-30
분석은 같은 화재군에 48,000 ha 이상을 제시" as the upper end of a range. Fetched this lap:
worldweatherattribution.org, 30 April 2025, says "more than 48,000 hectares burned" for
**southeastern Korea**, not for this complex, and the same coverage of that study reports
104,000 ha for the event overall. Presenting 45,157 to "more than 48,000" as the plausible
range for a fire that burned 99,289 ha makes the range itself the error.

**Smallest fix.** Three edits, no new research needed:

1. State the chain's final area as **99,289 ha** with 산림청 / 경상북도 as the agency and a
   URL, and keep 45,157 ha only if it is labelled explicitly as the 03-27 interim 경북 tally.
2. Rewrite the 범위 주의 note so it says what is true: the nationwide March 2025 total is
   104,788 ha across 347 fires, **of which this chain is 99,289 ha**. That sentence is more
   impressive than the one it replaces and it survives the search.
3. Drop the WWA figure from the range, or restate it as "southeastern Korea, WWA rapid
   study" which is the scope WWA gives it.

Then correct `docs/data_sources.md` table A the same way, and rewrite the 알려진 함정 bullet
that currently reads `"주택 4,000여 채"는 A가 아니라 B의 값(3,848동)이다. A의 주택 전소는
150동이다.` The chain's own 주택 전소 is **3,819동**; 150동 is the 산림청 03-26 interim, taken
two days before containment. The trap bullet as written is backwards, and it is the bullet
a later lap will trust.

### F17 — The same paragraph reasserts 영덕 사망 8명, which this repository corrected to 10 twelve hours earlier

**Where:** `README.md:194` (`그중 **영덕 8명**`) and `README.md:489`
(`**8 in 영덕 (Yeongdeok) alone**`); `docs/data_sources.md:185` (breakdown
`영덕 8·영양 6·안동 4·청송 3 등`). Contradicts
`docs/evidence/greenpeace_2026_survey.md:89-93` and `:157`.

**What is wrong.** WFG-020 (`f2eecf9`, 2026-09-03T1821Z) read the Greenpeace 실태조사
최종보고서 and recorded, in §7 「이 문서가 정정한 저장소의 기존 서술」, item 1:
**영덕 사망자 「8명」 → 10명**, sourced to the report p.9 quoting the 영덕군 홈페이지 공지 of
2025-04-29, and flagged as a 재인용값 rather than a survey result. `12b8ac7` then rewrote
both paragraphs, moved the total from 27 to 26, and left 영덕 8명 standing in both
languages. So the repository now states two different Yeongdeok death tolls in two
judge-facing documents, and the newer one is the one that was already corrected.

This is worse than a stale number because 영덕 is the region the routing work is built
around, and the evidence card that carries the correct figure is the same card the booth
answer to Q17 points at.

**Smallest fix.** Both README lines read **영덕 10명** / **10 in 영덕**, with the same
재인용 caveat the evidence card carries (영덕군 공지 2025-04-29, quoted by the Greenpeace
report p.9, not a survey result). Fix the `docs/data_sources.md:185` breakdown at the same
time, or label it as the 2025-03-26 interim it actually is. Then grep the tree for `영덕 8`
so the third copy does not survive.

### F18 — The entry that existed to put sources under these numbers closed without a single retrievable source

**Where:** `docs/data_sources.md:176-208`, the whole new
`## 동기 사건의 피해 규모` section; `docs/auto/NEEDS_HUMAN.md:247-269` (the NH-015 closure).

**What is wrong.** NH-015 was titled "The three sources behind the README's opening
numbers". Eleven figures now sit in two tables with an 출처 column reading 중앙재난안전대책본부,
산림청, World Weather Attribution, and a 기준일 column. **Not one row carries a URL, a
보도자료 number, a document title or a page.** The 산림청 rows say "2025-05-15" with no
release named; the 중대본 row names no bulletin. The previous version of the paragraph at
least named 한겨레·세계일보·서울환경연합, which is three checkable outlets. The rewrite
removed those and added nothing a reader can open. Under CHARTER §3 rule 5 and §12's
citation discipline this is the weakest sourcing in the repository sitting in the document
whose title is 데이터 출처. It is also how F16 and F17 got in: with no URL on a row, nothing
downstream can disagree with it.

Two of the figures are independently doubtful and would have been caught by the URL rule:
the nationwide 주택 피해 **3,848동** is close enough to the chain's own 3,819동 to look like
a conflation, and the widely reported nationwide figure is around 4,015 houses.

**Smallest fix.** Every row in both tables gains a URL column, and any row whose URL the
lap cannot open is deleted rather than kept unsourced. That is the same rule CHARTER §12
already applies to `paper/references.bib`, applied to the one document that names itself
after it.

---

## fix-this-sprint

### F19 — `12b8ac7` is an unreported, unreviewed commit, and every mechanism this loop built to notice that is looking somewhere else

**Where:** `12b8ac7` (README, `docs/data_sources.md`, `docs/auto/NEEDS_HUMAN.md`,
`docs/auto/LOOP_CONFIG.json`); `docs/auto/STATE.json:5-8`;
`docs/auto/reports/` (no report names this commit).

**What is wrong.** The window's last commit changed the judge-facing README in two
languages, closed three NEEDS_HUMAN entries including two DECISION entries, and edited
`LOOP_CONFIG.json`. It has no report, so it has no `Reviewed by:` line, no gate table, no
plain-terms section and no root objection. `STATE.json` still names the 2239Z dev report at
`c7b8a66` as the last report, so the loop's own state file does not know the commit exists.
CHARTER §4 step 7 requires a report per lap and `LOOP_CONFIG` → `review: subagent` requires
an independent reviewer before the push; a subagent reading only that diff would have asked
where 45,157 ha came from, which is exactly what F16 is.

The three checks the loop added this week all pass on it, and none of them is aimed here:
`--assert-head` asks whether the gates read the pushed commit (yes), `report.py`'s prose
gate only runs when a report is written (none was), and `make verify` only re-derives
numbers that have registry keys (these have none). The gap is a class, not an incident:
**a commit that carries only unregistered prose is invisible to every gate this repository
owns.**

**Smallest fix, and it is cheap.** `report.py` already computes "commits since the previous
report". Have `gates.py --assert-head`, or a five-line check beside it, refuse a push when
`HEAD` is not a descendant of the commit the last report names **and** the intervening
commits touch anything outside `docs/auto/reports/`. Filed as **WFG-049**. The author-facing
half is NH-017.

### F20 — A NEEDS_HUMAN entry can be closed by quoting an author reply that nothing in the repository can check

**Where:** `docs/auto/NEEDS_HUMAN.md:126-133` (NH-008), `:150-152` (NH-009),
`:247` (NH-015). All three closures are in `12b8ac7`.

**What is wrong.** Three DECISION entries were closed on quoted author replies
("Everything is fine here...", "If there is something better though...", "use 산림청") with
no channel, no message date, no thread reference and no artifact. NH-008's closure then
carries five consequences the loop will act on for the rest of the sprint, including not
contacting the 운영사무국 at all. NH-009's closure delegates decisions and records that
protecting `Main` is "the one item still owed".

The quotes may well be accurate; the point is that the repository has no way to tell, and
CHARTER §10 makes NEEDS_HUMAN the author's own layer. The one closure whose substance can
be checked from outside, NH-015, turned out to be substantively wrong (F16, F17, F18), which
is the argument for the record rather than against the author.

**Smallest fix.** NEEDS_HUMAN closures gain three fields: `channel` (report email reply, PR
comment, session), `received` (date), and `verbatim` for the quoted text. Where the reply
arrived in a session the repository cannot see, the closure says so in those words. Filed as
NH-017 because only the author can confirm the channel.

### F11 — **open**, unchanged, filed as WFG-045 · `paper/manuscript.md` ships 21 citations and no `## References` section

Carried from critic #2 and #3 without re-verification: `paper/` did not change in this
window, so nothing about F11 can have moved. Restated only so it is not read as closed.

### F12 — **open**, unchanged, filed as WFG-044 · `report.py` has no `paper` kind

`scripts/auto/report.py:123` still reads
`choices=["dev","critic","research","kickoff","red","manual"]`. Verified again this lap.

### F5 — **superseded by F16, not closed**

Critic #1, #2 and #3 filed F5 as "the README claims a burned area larger than the
nationwide total". `12b8ac7` removed the 116,000 ha figure, so F5's literal text no longer
describes the tree. The defect it named is not fixed; it changed sign. WFG-043 stays open
and should be **raised to P0** and rewritten to F16's terms, since it is now the row that
closes a wrong number rather than an unsourced one.

---

## note

- **N18 · The 2217Z dev lap is the best lap the loop has run, and F16 is not its fault.**
  `docs/auto/finals/DETECTION_FLOOR_CARD.md` plus `tests/test_detection_floor_card.py` (17)
  is the pattern this project should repeat: every figure on a judge-facing card read back
  out of `docs/NUMBERS.json`, each delay bound inside its own table row so a swapped
  attribution fails, and the one claim the row asked for left **off** the card because it
  has no registry key (WFG-048). Leaving a number out because it cannot be registered is
  CHARTER §3 rule 3 obeyed at a cost, and it is the exact discipline `12b8ac7` did not use.
- **N19 · The reviewer block in that lap caught the F14 failure class reproduced inside the
  lap that closed F14.** `KCF_READINESS` R3 claimed a green that `.auto/gates.json` recorded
  as `passed: false`. The lap rewrote R3 to state RED at `633c3db` and the reason. A
  definition-of-done document that records its own red is worth more to a judge than one
  that never has.
- **N20 · `--assert-head` works.** Independently confirmed: `gates.py --mode full` at
  `12b8ac7` writes `.auto/gates.json` with `git_head` matching, and the branch is green at
  HEAD for the first time in four critic laps. `tests/test_gates_assert_head.py` (15) pins
  the mode clause and the `f5f8498`/`8d1decf` mismatch that produced the finding.
- **N21 · Suite census this lap, cold, in a fresh sandbox.** `1185 passed, 62 skipped` at
  `12b8ac7`, against the 2217Z lap's `1191 passed, 56 skipped` at `c7b8a66`. Collected is
  **1247 in both**, the fourth consecutive lap in which the collected count is invariant
  across environments while the pass/skip split moves by exactly the six SRTM-gated tests
  (WFG-039). Critic #2's N7 recommendation stands: gate on `collected` alone.
- **N22 · `baseline-verify` WARN is unchanged and is not a finding.** Recorded again so no
  lap "fixes" it. The step is `hard: false` for the git-ignored raw manifests.
- **N23 · The author's standing permission to source public data is the most useful thing
  in `12b8ac7`.** It is what makes F16, F17 and F18 fixable by a lap instead of blocked on
  a human, and this lap used it: five sources were opened during this critic run. The
  permission should be written into CHARTER §3 as a standing fact rather than living only
  inside a closed NEEDS_HUMAN entry, or the next lap will not know it has it.

---

## The judge drill

`docs/auto/JUDGE_QA.md` gained Q10a and Q10b in `b557e9d`, so the drill ran on the bank as
it now stands.

**Q10a (영덕은 위성이 놓친 겁니까?) passes.** The answer states the 교란 classification, the
four numbers that justify it, the 283 스텝 중 217 counterfactual **with** its denominator
and both riders, and closes on "설령 그 이상이 진짜 화재였다 해도 시각은 신고 +28분" so the
conclusion is the same either way. Every figure has a registry key printed beside it, and
`tests/test_detection_floor_card.py` fails if any of them drifts. This is a T1 answer a
student can defend without hedging.

**Q10b (오경보는 몇 %입니까?) passes**, and refusing to say 0 % is the right instinct. The
95 % upper bound, the 709-step control, the four sites in one season, and the "표본을
늘리기 전에는 이 상한보다 강하게 말할 근거가 없습니다" close are all correct treatments of a
zero numerator.

**The drill's one hit is not in the bank, it is behind it.** Two questions a judge asks
before either of these, because they come from the first paragraph:

1. *"의성 산불 피해면적이 얼마입니까?"* The tree's answer today is 45,157 ha. The judge's
   phone says 99,289 ha. (F16)
2. *"영덕에서 몇 분이 돌아가셨습니까?"* The README says 8. `docs/evidence/greenpeace_2026_survey.md`
   says 10, and says the repository already corrected 8 to 10. (F17)

Neither is addable to the bank until F16 and F17 are fixed, exactly as critic #1 withheld
the 116,000 ha question for the same reason. The bank is strong where it is bound to
artifacts and silent where the project's numbers have no artifact, which is a fair map of
the project.

---

## What five lenses converged on

| lens | verdict | the one load-bearing reason |
|---|---|---|
| KCF judge · SW professor | pass, first time in four laps | The branch is green at HEAD, `--assert-head` makes that structural rather than lucky, and the detection-floor card is bound to the registry by 17 tests. I would score the engineering. |
| KCF judge · 재난 대응 공무원 | **fail** | The first paragraph tells me the fire that motivates this project burned 45,157 ha and that the 104,788 ha figure is a different event. I worked that season. The 경북 산불 was 99,289 ha and 3,819 주택. If you have the scale of the event wrong, I do not trust the 29 dispatch sheets. |
| fire-behaviour scientist | **fail**, on the same line | 45,157 ha is a pre-containment provincial interim and the document knows it (it says so), then uses it as the headline anyway, with a WWA figure for a different geography as the upper end of the range. The physics work in this repository is careful; this paragraph is not, and it is the one a reader meets first. |
| ML reviewer (leakage, baselines) | pass | Ran `mandela` over the window. Nothing in the diff touches an eval, a split or a metric. `tests/test_detection_floor_card.py` reads targets out of `docs/NUMBERS.json` rather than from literals, which is the correct direction. No leakage pattern fires. |
| statistician | pass, with one remark | Q10b's 95 % upper bound for a zero numerator is right and is stated three times without drifting. The remark is F18: eleven point estimates in a new table with no source is not a sourcing standard, and the one that looks conflated (3,848 vs 3,819) is the kind of error a URL column prevents for free. |

**Where they agree:** the machinery got materially better this window and the prose got
materially worse, and the two happened in the same eight commits. Three lenses pass on the
work the 2217Z lap did; the two that fail, fail on one paragraph written after it.

**Where they split:** L1 scores the tree's process, which is now genuinely good. L2 and L3
score the claim the tree opens with, which one search overturns. They do not disagree about
any fact.

**The question that resolves the split:** *which numbers in this repository can be wrong
without a gate noticing?* The answer is the small set with no registry key and no URL, and
every finding in this report is inside that set. F18's URL column is the cheapest thing
that shrinks it.
