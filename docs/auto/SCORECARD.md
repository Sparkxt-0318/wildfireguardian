# Scorecard — what the five judges would score today

The critic lap appends one dated row **only when the window's diff plausibly moved a
score**; a lap that moved nothing leaves the table alone and says so in its report.
Scores are 0–20 per row against `docs/auto/RUBRIC.md`, Track B five first
(연구 목적 · 설계와 방법론 · 데이터 수집·분석·해석 · 창의성 · 제출 자료), then Track A five
(개발 목적 · 설계와 방법론 · 구현 및 유용성 · 창의성 · 제출 자료). The track assignment is
not published, so both tables are kept.

These are **one critic's estimate of what a judge would give on the current tree**, not a
measurement. They exist to show direction between laps. A score that moves without a
commit to point at is a defect in the scoring, not evidence of progress.

## Track B — SW 연구

| date | window head | 연구 목적 | 설계와 방법론 | 데이터 수집·분석·해석 | 창의성 | 제출 자료 | /100 | what moved |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-09-03 | `1113388` | 15 | 15 | 16 | 15 | 11 | **72** | baseline (first critic lap) |
| 2026-09-03 | `0ff1b36` | 15 | 15 | 17 | 15 | 13 | **75** | +1 데이터: the survey evidence card, digest-gated extractor and doc-to-artifact tests. +2 제출 자료: 21 verified references (F2 closed, N4 closed), a 7,204-word manuscript, F3 fixed. 연구 목적 held at 15 by F5, still open |
| 2026-09-03 | `8d1decf` | 15 | 15 | 18 | 15 | 13 | **76** | +1 데이터 (재현) only: 545 test lines under a detector that had none, six registry keys bound to the artifact, and a Korean §12 that states what the tests do NOT show. Everything else held. Nothing in the window touched the screen, the printables, the bundle or `paper/`. The branch being red at HEAD (F13) is a process defect and is not scored here, because a judge scores the tree the author brings to the booth, not the loop |
| 2026-09-04 | `12b8ac7` | 14 | 15 | 18 | 15 | 13 | **75** | **-1 연구 목적**, the first fall in this table. `12b8ac7` rewrote the opening paragraph and replaced an overstated figure with an understated one: 45,157 ha for a chain that burned 99,289 ha, plus a scope note telling the reader the 104,788 ha nationwide total is a different event when about 95 % of it is this chain, plus 영덕 8명 against this repository's own correction to 10 at `f2eecf9` (F16, F17). Unsourced-and-too-big scored 15; wrong-in-two-directions-with-no-URL scores 14. 데이터 18 and 제출 자료 13 both **held** on two offsetting moves: `DETECTION_FLOOR_CARD.md` with 17 registry-binding tests is the first judge-holdable card that cannot drift (+), and `docs/data_sources.md` gained eleven figures with no URL in the document named 데이터 출처 (-) |
| 2026-09-04 | `5a0466e` | 15 | 15 | 18 | 15 | 15 | **78** | **+1 연구 목적 (14 to 15) and +2 제출 자료 (13 to 15).** The opening paragraph's figures are now correct and every one traces to a primary page a lap opened: critic #5 re-opened the 경상북도 release (99,289 ha / 149시간 / 3,819동 / 2,246세대 3,587명 / 1조 505억), the 경향신문 joint-survey article and the 산림청 season-end release, and all of them hold. 제출 자료 gains the two points critic #4 took off it and one more: `docs/data_sources.md` table A now carries a URL on every row, the eleven-figures-no-URL section is gone, `data/processed/external/fire_2025_scale.json` gives each figure agency + as-of + scope + status + the verified quote, 16 `fire2025_*` keys are registered, and `make verify` now refuses a paragraph that drops a final figure or states an interim one as final. That is the strongest sourcing standard in the repository, in the document named 데이터 출처. 연구 목적 stops at 15 and not 16 because of F21: the scope note still tells the reader this fire is 「about 43 %」 of the national total, which is false and contradicts the repository's own registered 94.8. 데이터 18 and 설계와 방법론 15 held; nothing in the window touched a model, a split or a metric |
| 2026-09-04 | `b855943` | 16 | 15 | 18 | 15 | 15 | **79** | **+1 연구 목적 (15 to 16), the first 16 this table has recorded.** The 「약 43 %」 sentence critic #5 called false is gone from both languages, deleted rather than rewritten a fourth time, and the lap that deleted it checked the critic's reasoning and found one of its three premises wrong: 산림청 told 경향신문 that 산불영향구역 and 피해면적 「개념이 달라서 단순 비교할 수 없고」, which is a better reason to refuse the ratio than the directional one the critic gave. The opening paragraph now states figures that are all sourced and makes no claim about them that is not sourced. 데이터 18, 설계 15, 창의성 15 and 제출 자료 15 all held; see the window note for the two moves that cancel in 데이터 |

## Track A — 애플리케이션 / 실생활 도구

| date | window head | 개발 목적 | 설계와 방법론 | 구현 및 유용성 | 창의성 | 제출 자료 | /100 | what moved |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-09-03 | `1113388` | 15 | 15 | 11 | 15 | 11 | **67** | baseline (first critic lap) |
| 2026-09-03 | `0ff1b36` | 15 | 15 | 11 | 15 | 12 | **68** | +1 제출 자료 only: the survey card gives Q17 a file to point at. 구현 및 유용성 does not move, because nothing in this window touched the screen, the printables or the bundle (R1, R2, R7, R9 all still ☐) |
| 2026-09-03 | `8d1decf` | 15 | 15 | 11 | 15 | 12 | **68** | **held, every row.** Track A's judges score a working tool at a booth. This window added tests to a script that runs offline in the sandbox and never appears on the screen. R1, R2, R7, R9 are still ☐, and R2 is now blocked on WFG-021's stranded status rather than on work (F15). Said explicitly so 545 test lines are not read as progress on the thing these judges watch |
| 2026-09-04 | `12b8ac7` | 14 | 15 | 11 | 15 | 12 | **67** | **-1 개발 목적**, the same paragraph, and these judges read it at the booth with a phone in hand. 구현 및 유용성 **11, held for the fifth consecutive window**: no commit in this window touched `web/`, the printables or the release bundle, and R1, R2, R7 and R9 are all still ☐. WFG-017 is now the single most overdue thing in the sprint plan |
| 2026-09-04 | `5a0466e` | 15 | 15 | 11 | 15 | 13 | **69** | **+1 개발 목적 (back to 15), +1 제출 자료 (12 to 13).** These judges read the opening paragraph at the booth with a phone in hand, and the phone now agrees with the paragraph. 제출 자료 rises on the sources table gaining a URL per row. **구현 및 유용성 11, held for the sixth consecutive window.** No commit in this window touched `web/`, the printables or the release bundle; R1, R2, R4, R7 and R9 are all still ☐ with eleven days left in the sprint. Three windows ago this was a note, two ago a risk. It is now the finding that decides the score: the artifact five judges watch for five minutes still does not exist in its finals form, and WFG-017 has been named the next row by two critic laps running |
| 2026-09-04 | `b855943` | 16 | 15 | 11 | 15 | 13 | **70** | **+1 개발 목적 (15 to 16)**, the same deletion, read at the booth. **구현 및 유용성 11, held for the SEVENTH consecutive window.** No commit in this window touched `web/`, the printables or the release bundle. `docs/auto/KCF_READINESS.md` has 2 of its 11 lines ticked (R5, R6) with eleven days of sprint left, and R1, R2, R4, R7, R9 and R11 are all still ☐. 제출 자료 13 held: `references.bib` gained five entries whose notes are the best sourcing work in this repository (one of them re-opens its own URL and corrects a paraphrase the previous lap wrote), and against that the 사망 26명 attribution disagreement is now in three documents instead of two |

## 2026-09-03 · `25f1e14..1113388` — why these numbers

**연구 목적 / 개발 목적 · 15.** The problem is specific, the population is specific, and
the frame (spread forecast → rescue-aware routing → decision layer) is the submitted one.
It loses points on its own opening paragraph: three scale figures with no URL, no registry
key, and one that exceeds the national total (CRITIC F5, WFG-043). A judge who checks the
motivation before the method finds the softest evidence in the repository first.

**설계와 방법론 · 15 (both tracks).** Leave-one-fire-out is the right design and is
enforced, variables and controls are named, and the negative results are kept rather than
buried. Held back by 기존 연구와의 차별점: the related-work table is WFG-026 and unstarted,
and the one related-work citation that exists is not the paper at its URL (F2). 일정·역할
(WFG-027) is also unstarted.

**데이터 수집·분석·해석 · 16 — the strongest row.** Six fires, event-held-out, an operating
point owned rather than hidden (pooled recall 0.138, three folds with zero true positives),
mean-of-folds and pooled kept apart as different quantities, a 296-entry registry that
re-derives, and a lineage gate that found four real instances the moment it was switched
on. It is not 18+ because the loop's own suite instrument is compromised: every recorded
pass/skip baseline is an unlabelled mixture of cold-run and warm-run readings (F8,
WFG-038/039), so the "no test was lost" comparison has been comparing different quantities.

**창의성 · 15.** The coupling — a calibrated held-out hazard field driving a time-expanded
pedestrian router with a rescue-ingress term — is the creative claim and it is real. Nothing
in this window added to it; the window was traceability and scaffolding work.

**제출 자료 · 11 — the weakest row, and the cheapest to move.** 출처 명기 is scored, and it
is where the repository is thinnest: the opening scale figures are unsourced (F5), one
`verified` citation is the wrong paper (F2), SRTM / ESA WorldCover / OpenStreetMap are used
and uncited in the manuscript (N4), and the finals screen, printables, README Round-4
section and release bundle (R1, R2, R7, R8, R9) do not exist yet. Logical 구성 is good; the
graphics are good; the sourcing is not.

**구현 및 유용성 · 11 (Track A only).** `web/finals.html` v2, the 5-minute script, the booth
recipe and the release bundle are all still `todo` (WFG-017, WFG-003, WFG-037, WFG-036).
This row is scored on what a judge can watch at the booth, and that artifact does not exist
in its finals form yet. It should move most between 09-07 and 09-14.

**Not scored here:** the two Pass/Fail rows (서류 구비, 위험성 검토). 서류 is the author's
(WFG-022 / NH-008); 위험성 is not at risk — the delivery layer stays dry-run by design.

## 2026-09-03 · `a278a56..0ff1b36` — why these numbers moved (critic #2)

Two rows moved and three did not. The window was one dev lap (WFG-020, the survivor
survey) and the first real paper lap (605 words to 7,204).

**데이터 수집·분석·해석 · 16 → 17.** `docs/evidence/greenpeace_2026_survey.md` plus
`data/processed/evidence/greenpeace_2026_survey.json` plus
`scripts/extract_survey_evidence.py`, which refuses to read a digit until the source
sha256 matches, is the first time this repository has taken a third-party measurement
and made the transcription itself machine-checkable rather than hand-typed beside a
hash. `tests/test_greenpeace_evidence.py` then binds both the evidence card and the
booth answer to the artifact, and its own docstring records the mutation that shows
where the binding stops. That is the behaviour the row scores. It is +1 and not +2
because the survey evaluates nothing about our model, which the card says plainly.

**제출 자료 · 11 → 13 (Track B), 11 → 12 (Track A).** 출처 명기 was named the weakest
and cheapest row at the baseline, on four specific defects. Two are closed: the
`verified` citation that was not the paper at its URL (F2) and the three uncited data
sources SRTM, ESA WorldCover, OpenStreetMap (N4). `references.bib` is now 21 entries,
each opened at its URL by the lap that added it. The manuscript is a real artifact a
judge can be handed. It is not more than +2 because F5 (the opening scale figures) is
untouched, F11 (21 citations, no bibliography) is new, and R1, R2, R7, R8 and R9 are
still ☐. Track A gets +1 rather than +2 because a manuscript is not what its judges
score.

**연구 목적 / 개발 목적 · 15, held.** The paragraph that states why the project exists
still carries ~116,000 ha (F5). One search, in the first thing a judge reads.

**설계와 방법론 · 15, held; 창의성 · 15, held.** Nothing in this window changed a method
or the coupling. The paper *describes* them better, which is the 제출 자료 row.

**구현 및 유용성 · 11, held (Track A).** No commit in this window touched `web/`, the
printables or the release bundle. Said explicitly so the manuscript is not read as
progress on the thing the booth judges actually watch.

## 2026-09-03 · `1c1561e..8d1decf` — why these numbers

**데이터 수집·분석·해석 · 17 → 18 (Track B).** `scripts/gk2a_detection.py` produces the
+22 / +34 / +64 minute figures and the 0-of-709 false-alarm bound, both of which are
quoted on judge-facing documents, and until this window it had no tests at all.
`tests/test_gk2a_detector.py` binds six registry keys to
`data/processed/detection/*.json`, reproduces the recorded 21.964 K contextual threshold
from the artifact rather than from a literal, and pins the geometry that makes 영덕's
교란 classification mean something. `docs/detection_floor.md` §12 then states, in bold,
which groups are synthetic and that their gains are the test's own and must not be cited
as GK2A calibration. It is +1 and not +2 because the tests mostly ask the code to agree
with itself, which §12 says first, and because the one group with outside ground truth is
opt-in and runs for nobody by default (N14).

**제출 자료 · 13, held (Track B); 12, held (Track A).** No citation, reference or
submission artifact changed. F11 (21 citations, no bibliography) is untouched because
`paper/` did not move.

**연구 목적 / 개발 목적 · 15, held.** F5 is in its third critic lap. The opening paragraph
still carries a burned area larger than the national total, and it is blocked on the
author's sources (NH-015), not on a lap.

**설계와 방법론 · 15, held; 창의성 · 15, held.** The `contextual_flag` extraction is
semantics-preserving by design and by inspection. Nothing in this window changed a method,
a coupling or an experimental arm.

**구현 및 유용성 · 11, held (Track A).** No commit touched `web/`, the printables or the
release bundle. Fourth consecutive window in which that is true, which is the one thing in
this table the sprint plan should worry about: the finals screen is what five judges
actually watch for five minutes, and WFG-017 is still ahead of the loop.

## 2026-09-04 · `9bf15fb..12b8ac7` — why these numbers

**연구 목적 / 개발 목적 · 15 → 14.** The first fall this table has recorded, and it is
deliberate. For three critic laps this row was held at 15 with F5 open: the opening
paragraph carried ~116,000 ha, unsourced and larger than the national total. That is a
figure a judge distrusts. `12b8ac7` replaced it with 45,157 ha, which is the 경북 provincial
interim tally on 2025-03-27, one day before 주불 진화 on 03-28, for a chain whose final
burned area is **99,289 ha** — and added a 범위 주의 note asserting that the 104,788 ha
nationwide figure belongs to a different event, when the chain is about 95 % of it. The
same commit left 영덕 **8명** standing in both languages twelve hours after this repository
corrected that figure to **10** in `docs/evidence/greenpeace_2026_survey.md` §7. One wrong
number a judge can find is a 15; two wrong numbers in opposite directions, one of which
contradicts the project's own committed evidence card, is a 14.

**데이터 수집·분석·해석 · 18, held.** Nothing in this window changed a method, a split, a
metric or an eval; `mandela` fires on nothing. The window's data work is traceability, and
it is good traceability: `tests/test_detection_floor_card.py` binds every figure on the new
card to `docs/NUMBERS.json` and binds each delay inside its own table row, so a swapped
attribution fails rather than passing on a substring. That is worth saying and it is not
worth a point, because the underlying result is the one already scored at `8d1decf`.

**설계와 방법론 · 15, held; 창의성 · 15, held.** No coupling, arm or protocol moved.

**제출 자료 · 13 (Track B) / 12 (Track A), held, on two moves that cancel.** Up:
`docs/auto/finals/DETECTION_FLOOR_CARD.md` is the first evidence card in this project a
judge can hold whose every digit is checked against the registry by a test, and the lap that
wrote it left a number **off** the card because it has no key (WFG-048) rather than typing
it. That is the sourcing standard this row has been asking for since the baseline. Down:
`docs/data_sources.md` gained a section of eleven figures across two tables with an 출처
column of agency names, a 기준일 column, and **not one URL, 보도자료 number or page** — in
the document whose title is 데이터 출처, closing the entry that existed to put sources under
exactly these numbers. The previous text at least named three checkable outlets. A judge
scoring 출처 명기 would read the card and the table in the same sitting.

**구현 및 유용성 · 11, held (Track A). Fifth consecutive window.** Five windows is no longer
a note, it is the sprint's main risk: the artifact five judges watch for five minutes does
not exist in its finals form, and every lap since 09-03 morning has improved something
those judges will never see. WFG-017 should be the next row after WFG-043.

**Not scored here:** the two Pass/Fail rows. 서류 is now the author's own decision under the
NH-008 closure (no contact with the 운영사무국 will be made); 위험성 is not at risk.


---

## Window 2026-09-04 `a4dc9a7..5a0466e` (critic #5)

**연구 목적 · 15, recovered, and capped there by one sentence.** Three laps spent a whole
window on the first paragraph a judge reads, and the figures are now right: checked cold
against four primary pages this lap, not one is wrong. The row does not go back to 16
because the paragraph still asserts, in both languages, that a like-for-like comparison
would put this fire at about 43 % of the national total. 산불영향구역 includes the unburned
ground inside the fire line and is normally the larger of the two statistics, so a 45,157 ha
영향구역 under a 99,289 ha 피해면적 is the relation inverted; the article the repository
cites for the definition calls the 45,157 an undercount that the survey more than doubled;
and `docs/NUMBERS.json` records the share as 94.8. One deleted sentence is the whole fix
(F21) and it is worth a point.

**제출 자료 · 15 (Track B) / 13 (Track A), the largest single-window rise in this table.**
The mechanism is what earns it, not the prose. A figure in the opening paragraph now has a
registry key, an artifact row with agency and as-of date and scope and status, the URL a lap
opened, and the sentence that page actually said; two gates hold the paragraph to it; and
the sourcing rule was applied where it cost something, with two figures removed rather than
kept at lower confidence. A judge who asks 출처가 어디입니까 can be shown a chain from the
screen to the page in four steps.

**설계와 방법론 · 15, 창의성 · 15, 데이터 · 18: held.** No model, split, metric, arm or
protocol moved. Said explicitly so 44 new tests are not read as scientific progress.

**구현 및 유용성 · 11 (Track A), sixth consecutive window.** Eleven days of sprint remain
and the finals screen has not been touched since 09-03. Every lap since then improved
something these five judges will never see. This is now the largest single risk in the
sprint plan, larger than any finding in this report.

**Not scored here:** the two Pass/Fail rows. 서류 is the author's own under the NH-008
closure; 위험성 is not at risk.

---

## Window 2026-09-04 `5a0466e..b855943` (critic #6)

**연구 목적 / 개발 목적 · 15 → 16.** The first 16 in this table. Three critic laps in a row
named the opening paragraph as the softest evidence in the repository; it is no longer that.
Every figure has a registry key, an artifact row carrying agency and as-of date and scope and
status and the sentence the page actually said, a URL a lap opened, and two gates holding the
prose to all of it — and as of this window the paragraph also makes no *claim* about those
figures that is not sourced. What earns the extra point rather than a hold is how the last
sentence went: the lap deleted it, checked the critic's argument for deleting it, found one
of the critic's three premises was wrong (산림청 itself says 산불영향구역 and 피해면적
「개념이 달라서 단순 비교할 수 없고」, so the directional argument does not hold), and wrote
the agency's wording into `docs/data_sources.md` 함정 1 and 함정 6 instead of the critic's.
A loop whose reviewer can be wrong and whose lap checks it is a different object from a loop
that obeys its reviewer.

**데이터 수집·분석·해석 · 18, held, on two moves that cancel.** Up: `paper/manuscript.md`
§4.7 is a real new result written the way this project's best work is written — a negative
control with its numerator at zero reported as an upper bound and not a rate, a sub-pixel
size floor given as an order of magnitude because the flame-temperature assumption moves it
eightfold, one of the four fires excluded as confounded rather than counted either way, and
an n = 3 comparison labelled a description of three events rather than an operating
characteristic. The same lap's reviewer blocked an ordering claim it could not source and
the lap **reverted the claim rather than repeating it**, filing `paper/GAPS.md` G5 and
NH-019. Down, and exactly offsetting: the repository now holds two answers to that same
question. `docs/detection_floor.md` §9, `docs/auto/finals/DETECTION_FLOOR_CARD.md` and
`docs/auto/JUDGE_QA.md` Q10 all still assert that the satellite rang after the telephone,
and the manifest they measure from calls the reference field the ignition (F27, WFG-053).
A row scored on 재현 가능성 and 논리적 해석 cannot rise while the paper and the booth card
answer one question differently.

**설계와 방법론 · 15, held; 창의성 · 15, held.** No model, split, metric, arm, coupling or
protocol moved. Said explicitly so that a 938-line manuscript rewrite is not read as
scientific progress: it is 제출 자료 work and one new result, and the new result is §4.7.

**제출 자료 · 15 (Track B) / 13 (Track A), held.** The references work in this window is the
best sourcing this repository has produced. `references.bib` gained five entries, and the
WWA note does something no gate asked for: it re-opened its own URL and corrected the
paraphrase the previous lap's note carried, which had rendered 「Uiseong was hardest hit,
with 26 deaths, while four occurred in Sancheong」 as "26 of them in Uiseong-gun" — turning a
fire attribution into a county one and dropping the four deaths that reconcile 26 with 32.
Against that: F23 is unfixed in its second window and has now **propagated**. 사망 26명 is a
중앙재난안전대책본부 count in the registry, a 경상북도 재난안전대책본부 count in
`docs/data_sources.md:190`, and "the provincial disaster headquarters' count" in
`paper/manuscript.md:37`, and the README link a judge would click still carries no death
figure at all. And the manuscript is 7,479 words against a 7,500 hard fail, enforced as a
proxy for a 20-page limit the loop's own recount puts at about 21 pages (F29). A row scored
on 출처 명기 and 논리적 구성 does not rise on excellent citations while the same window leaves
one figure with three agencies and a length gate measuring the wrong quantity.

**구현 및 유용성 · 11 (Track A), seventh consecutive window, and this is now the report's
second finding rather than a note.** Since 2026-09-03 morning, every lap has improved
something these five judges will never see. `KCF_READINESS.md` is the definition of done for
the final product and it has **2 of 11 lines ticked**. Eleven days of sprint remain. The
backlog table order puts WFG-017 next once WFG-021 stops reading as `todo`, which this lap
fixed by parking its unrunnable part; nothing else stands between the loop and the screen.

**Not scored here:** the two Pass/Fail rows. 서류 is the author's own under the NH-008
closure; 위험성 is not at risk, the delivery layer stays dry-run.
