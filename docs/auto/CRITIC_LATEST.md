# Critic latest — the next dev lap's first read

*Critic lap #62, 2026-09-10T2305Z. Reviewed head `f93af93`. Window 2026-09-10T18:40Z
(`be39dea`) to 2026-09-10T22:45Z (`f93af93`), inside a 24 h look-back to 2026-09-09T22:45Z:
8 commits since critic #61, of which one is a paper lap, one is a dev lap that closed a P0
row, and six are report, board or header-correction commits. This lap changed no code, no
test, no data, no figure and no committed artifact. It wrote only under `docs/auto/`.*

⚠ The clone arrived **SHALLOW at 51 commits**, the sixth lap running, which is shorter than the
24 h window itself. `git fetch --unshallow` was run before anything was counted:
`--is-shallow-repository` answers **false** and `git rev-list --count HEAD` answers **740**.
Every ancestry statement below is licensed under CHARTER §4.

## `fix-before-next-row`: ZERO. Take the top row directly.

Measured rather than assumed, at `f93af93`. CHARTER §14b lets a preemption be **minutes** AND on
a listed surface (README opening, finals screen, Q&A bank, manuscript, printables, release
bundle) or a red gate.

- **No gate is red anywhere.** `gates.py --mode full` exits **0** (**2054 passed**, 63 skipped,
  3 xfailed, pytest 319.3 s). `baseline-verify` WARNs on the two git-ignored `data/raw/**`
  contracts, which is NH-029 and CHARTER §3d working as designed.
- **GitHub's own runs are green.** `auto-gates` runs **332 to 351** read through the GitHub MCP
  in this lap's own process: **14 `success`, 6 `cancelled`, ZERO `failure`**, with run **351**
  `success` at this exact head. CHARTER §4b sets no finding #1, the eleventh consecutive lap.
  (The six `cancelled` are runs superseded by a later push, the pattern every window shows.)
- **Every push in the window carried its report.** `--assert-reported` replayed pairwise over
  all seven pushed heads (`252c9f9`→`a6d49d3`→`99dee9b`→`938dff7`→`b729110`→`16d7933`→
  `ae12608`→`f93af93`) exits **0** at every step. The 24 h window holds **7 dev, 4 paper, 1
  research and 8 critic** reports; **every dev and paper report from 2026-09-09T0056Z onward
  (15 dev, 4 paper) records `Reviewed by:`**, checked by grep, which covers the window with
  margin. The research report carries none and that is by design, not a defect: only the dev and
  paper routines have a reviewer step.
- **Both judge-facing defects this lap found pay a price that is not minutes.** WFG-243 edits
  `docs/auto/JUDGE_QA.md` and `docs/auto/finals/RELATED_WORK_PANEL.md`, both hashed printables
  sources, so it costs `make printables` at a new stamp plus a re-pointed
  `release/kcf-finals-2026/MANIFEST.json` (**NH-049**). WFG-244 is on `docs/MODEL_CARD.md`,
  which is on **none** of §14b's listed surfaces and on neither the kit's seven sources nor the
  bundle's nineteen, both re-hashed here. So both are rows.

Sixth consecutive critic lap with zero preemptions, and the sixth measured rather than defaulted.

## Findings, ranked

**1. (WFG-243, P0, KCF) The card the student says from memory states this project's own output
object in the household register `WC-013` withdrew, and it is printed as well as spoken.**
`docs/auto/JUDGE_QA.md` **Q16a** is tier **T0** (`:646-647`) and answers 「산림청·경기도가 이미
산불확산예측을 하고 있는데, 무엇이 다릅니까?」. At `:657-659` it states the delta as 「저희가 내는
것은 그 예측 자체가 아니라 **가구 하나하나에 대한 「지금 걸어 나갈 수 있는가, 없다면 누구를 먼저
데리러 가는가」** 이고, 공간 단위가 읍면동이 아니라 **집**입니다」, and `:667` repeats it as 「지형을
곱게 본다고 「**이 집 사람이** 걸어 나갈 수 있는가」가 답해지지는 않습니다」. That is `WC-013`
exactly: the project's own output object, in the household register, with the output-object
phrase attached. The same file corrects the same register 580 lines away at `:1238`
(「「지점」도 실제 가구 주소가 아닙니다」). **It is on the paper, verified:**
`manifest_20260910T1233Z.json` lists this file among its seven `sources` and all **seven** hash
equal to the tree at this head, re-computed here. **And it is a T0 card**, so it is said aloud to
five judges as well as printed, which makes it a wider surface than WFG-240's.
**The two files are the same text by their own statement:** Q16a's 근거 block at `:672-674` calls
`docs/auto/finals/RELATED_WORK_PANEL.md` 「부스에서 펴는 인쇄 문안 — **이 카드와 같은 말을
합니다**」. WFG-222 corrected five surfaces on 2026-09-10 and this comparison pair was in none of
them. **Why no gate sees it:** `WC-013`'s Korean pattern needs 「가구 단위」 plus one of
{걸어서 나갈, 대피 판정, 구조 순서, 출동 순서, 판정과 걸어, 인명}. 「가구 하나하나에」 has no
「가구 단위」; 「걸어 나갈」 is not 「걸어서 나갈」; 「이 집 사람이」 and 「공간 단위가 … 집입니다」
carry neither token. The `:657-658` phrase also wraps the source line break, which is WFG-223's
measured limit. `docs/creativity_card.md:721-726` predicted a **fourth** differently-worded copy;
this lap swept every tracked `.md` and `.html` outside the record class and counted **six**.

**2. (WFG-240 corrected in place, no new row) The panel row names two lines of its file and there
are four.** Besides `:46` and `:119-120`, `docs/auto/finals/RELATED_WORK_PANEL.md:45-46` reads
「정하는 것은 **어느 집을 먼저, 어느 길로**입니다」 one clause before the line the row does name, and
`:73-74` reads 「지형을 곱게 본다고 「**이 집 사람이** 걸어 나갈 수 있는가」가 답해지지는 않습니다」,
which is the sheet's differentiator against 산림과학원's 5 m terrain plan. Neither contains
「가구 단위」 either. A lap that fixes only the two named lines leaves the sheet contradicting itself
27 lines later. The row now names all four. **The two off-kit copies are in WFG-243's done-when**:
`docs/global_portability.md:147` (「출력 … **가구별 대피 가능 여부와 여유 시간**」) and
`docs/SESSION14_REPORT.md:178` (「가구별 대피 판정」), both gated `.md`, neither on the kit, so they
cost no rebuild.

**3. (WFG-244, P0, KCF) The block written 90 minutes ago onto the submitted-document sentence
asserts a repository-wide negative, and the file it names four lines later holds both counts.**
`docs/MODEL_CARD.md:548-556` states 「⚠ **Neither count has a second, independent derivation in
this repository.**」 and then 「⚠ The legacy Build A `spread_v2` audit file also reports 17 for this
fire … **its 17 agrees with the whole-fire count by coincidence rather than by derivation**」.
Read here rather than inferred, `data/processed/spread_v2/audit.json :: fires[5]` is
`fire_id: gangneung_2023`, `bbox_wgs84 [128.75, 37.7, 129.05, 37.95]`,
`dates ["2023-04-11", "2023-04-13"]`, and it gives `detections_csv` **17**, `detections_in_grid`
**17**, **`total_positives` 8** and **`spread_cells_total` 8**. So (a) 「by coincidence」 is a
provenance mechanism nobody measured, and the plain reading is that two builds counting the same
FIRMS bundle for the same fire agree because they are counting the same thing; and (b) the
repository-wide negative is asserted over a record that holds the **other** count too, which the
block never says. The 「coincidence」 wording travelled verbatim from WFG-233's own row text, filed
by critic #59 and equally unmeasured there. **Why it is not a nitpick:** the block is attached to
the one text in this repository written to be pasted into the **submitted** 작품설명서, its whole
subject is what corroborates a number, and WFG-233's independent reviewer blocked that same lap for
overstating a corroboration. This is the same class understated, in the same commit, one layer up.
Both are unmeasured claims about provenance (CHARTER §3 rule 5).

**4. (no row; the loop's own direction) ZERO readiness lines ticked for the NINETEENTH consecutive
critic lap, and unlike critic #61's window this one had judge-facing artifacts to tick against.**
`docs/MODEL_CARD.md` changed and `web/finals.html` was rebuilt (registry 537 → 539). R1, R7 and R9
all HELD on their own criteria and were re-earned here: the screen is offline by gate inside the
green run, the kit hashes **7 of 7** and the bundle **19 of 19** against their sources. R3, R11 and
R12 are the three that do not tick and **none is a lap's to move**: R12 is the author's (NH-014),
R3 is `blocked(NH-046)`, and R11's WFG-024 is held by CHARTER §14b until R3 ticks, so **106 P1 rows
wait on one reply**. **NH-046 is due 2026-09-10 and this lap ran at 23:05 UTC, which is already
2026-09-11 08:05 KST**, so it is due now on the author's clock. Appended to NH-046, not filed again.

**5. (WFG-107, seventh instance, corrected in place; no new row) Two hand-written censuses on the
direction page are wrong, and one of them is a corrected figure that re-drifted.**
(a) **The P1 ledger is 106 rows, not 102.** `docs/auto/DIRECTION.md` and `docs/auto/KCF_READINESS.md`
both say 「102 P1 rows wait on one reply」. Counted here at `be39dea`, at `f93af93` and in this lap's
working tree, all three answer **106**. Critic #58 published 102; critic #59 counted 106 / 107 / 108
at three heads and recorded the correction **on WFG-107**; critic #61 wrote 102 again one lap later.
It did not grow, it was inherited from the page.
(b) **The board triple mixes two heads.** DIRECTION says 「Use 94 / 15」 and 「236 rows」. Reproduced
exactly here by critic #61's own method: at `be39dea`, the head that lap reviewed, the board is
**233 rows, 94 P0 (73 bold + 21 bare), 15 P0 `todo`**; **236** is the count only **after** that lap's
own three rows landed in `252c9f9`. The parts are all right and the head is not one head.
**At this head after this lap: 238 rows, 98 P0 (77 bold + 21 bare), 18 P0 `todo`, 106 P1 `todo`.**
**What this adds to WFG-107 rather than repeating it:** the remedy must emit the head each number was
measured at, not only the number, because a figure without its head cannot be re-derived by the next
lap and that is exactly how a corrected count comes back.

## What the window actually produced

**One dev lap (`e8b6e01`, WFG-233) and one paper lap (`938dff7`), and both were disciplined.**
The dev lap's independent reviewer blocked it for describing a verbatim dict copy
(`scripts/gk2a_detection.py:366`) as a second derivation, and the lap fixed it in all five places
rather than arguing; I re-derived that block's premise here and it holds. The paper lap changed no
manuscript sentence and said why: two obligations arrived and the word proxy refused both, measured
with the builder's own counter. Its own reviewer caught a completeness integer the lap had derived
wrongly in the direction that flattered a completeness claim. **Neither lap's report claims more
than its diff supports**, which is the thing this section exists to check.

**No `factchk` finding on new external claims, and the reason is stated rather than implied.** The
window's only new world claim is the `bokade2026` entry in `paper/references.bib`, and critic #61
re-fetched that record against the live Zenodo API three hours earlier, including the concept and
version DOI pair. Nothing in this window depends on it beyond what that lap verified, so this lap
did not re-fetch it and says so instead of implying a check it did not run. Every other new claim in
the diff is about this repository, and each was re-derived here from the artifact.

## Scorecard, at `f93af93`

**Track B 95 → 94.** 제출 자료 **18 → 17**. 연구 목적 18, 설계와 방법론 20, 데이터 수집·분석·해석 20,
창의성 19, all HELD.
**Track A 96 → 95.** 제출 자료 **18 → 17** on the identically worded criterion. 개발 목적 19,
설계와 방법론 20, 구현 및 유용성 20, 창의성 19, all HELD.

**One row closed and two opened on the same criterion, so it moves down by one and not by two.**
WFG-233 closed, and it closed well: the submitted-document sentence now carries both counts with a
`src:` line and a registry key each, which is 「사용된 자료에 대한 출처 명기」 paid. Against it,
WFG-243 puts the withdrawn household register on the **printed** kit for a second file and on a
**T0** card said from memory, and WFG-244 puts an unmeasured provenance claim into the same
submitted-document block the same commit repaired. 「자료의 논리적 구성」 is the first named sub-item
of this 20-point row on both tables, and a kit that names the project's spatial unit two ways is
that sub-item failing on paper. **Five open 제출 자료 defects now (WFG-236, WFG-240, WFG-241,
WFG-243, WFG-244), three of them on paper.**
**Pre-registered for critic #63:** 제출 자료 returns to **18** when WFG-240 and WFG-243 both close
**with `make printables` rebuilt and the bundle manifest re-pointed** (not when the tree is fixed,
and not on a report that says it was), to **19** when WFG-241 and WFG-244 close as well, and to
**20** when WFG-236 closes. 구현 및 유용성 is re-examined upward only when the disc null or the
centroid overshoot reaches `web/finals.html` or `docs/auto/JUDGE_QA.md`, unchanged from critic #60.

## Root objection (`hate`), and its cheapest test

**If the contribution is the output object, then the object's own name is the claim, and this
repository cannot say it the same way twice.** DIRECTION's thesis moved to 「the output object and
its measured limits」 one lap ago. On the four surfaces a judge meets inside ten minutes, the object
is called 지점 단위 on the screen (`scripts/finals.template.html:1594`), on the README
(`:246`, `:416`), on the panel's opening paragraph (`:23`) and in the bank at `:1238` — and 가구 /
집 on the panel at `:45-46`, `:73-74` and `:119-120` and in the bank at `:657-659` and `:667`. A
judge who reads the printed kit front to back holds both. **This is load-bearing rather than a
gotcha** precisely because the project's answer to 「무엇이 다릅니까?」 is the unit: 읍면동 versus
something smaller. Getting the something smaller wrong twice on the sheet that makes the comparison
is the differentiator failing on its own evidence.
**Cheapest test, and it was run here:** grep the printed kit's seven hashed sources for both
registers and count. It returns both, in two of the seven files, and the count is finding 1.
**Second-cheapest, for the next lap:** after the fix, re-run the same grep before `make printables`,
not after, so the rebuild certifies a corrected tree rather than recording an uncorrected one.

## `Do NOT edit` notes — one, line-scoped, re-measured, expiring

⚠ **Do not write a byte into `docs/auto/JUDGE_QA.md` or
`docs/auto/finals/RELATED_WORK_PANEL.md` without `make printables` at a new stamp and a re-pointed
`release/kcf-finals-2026/MANIFEST.json`.** Critic #61's note is **re-stated after re-measuring its
premise, as CHARTER §14c requires**, and it covers the same two files. The measurement, taken in
this lap's own process at `f93af93`: `docs/auto/finals/printables/manifest_20260910T1233Z.json`
lists seven `sources` — `docs/auto/finals/BOOTH_SETUP.md`, `docs/auto/DEMO_SCRIPT_5MIN.md`,
`docs/auto/JUDGE_QA.md`, `docs/submission_reconciliation.md`,
`docs/auto/finals/DETECTION_FLOOR_CARD.md`, `docs/creativity_card.md`,
`docs/auto/finals/RELATED_WORK_PANEL.md` — and all **seven** hash equal to the tree, both of these
among them, so the first changed byte turns
`tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` red.
**This note covers those two files and expires at critic #63 unless that lap re-measures the seven
hashes and re-states it.** It is a price tag, not a prohibition: WFG-235, WFG-240, WFG-241 and
WFG-243 are all expected to edit them, and **one lap should take all four so the rebuild is paid
once instead of four times.** ⚠ It is also why **this lap wrote no card into the bank itself**: a
critic lap cannot run `make printables`, so a card added here would ship the kit stale. That
collision is NH-049 and it comes due 2026-09-11.

⚠ **No `Do NOT edit` note is written on `docs/MODEL_CARD.md`, `docs/global_portability.md`,
`docs/SESSION14_REPORT.md`, `docs/disc_null.md`, `docs/oracle_gap.md` or
`docs/auto/KCF_READINESS.md`.** WFG-236, WFG-237, WFG-238, WFG-243 and WFG-244 must all edit them.

## Judge drill — the questions that still have no file behind them

Run against `docs/auto/JUDGE_QA.md` at this head, answering only from files.

1. 「이 프로젝트의 공간 단위는 집입니까, 지점입니까?」 **Four files answer, two of them printed, and
   they answer differently.** → **WFG-243** and **WFG-240**. This is the one that moved this lap.
2. 「무엇이 다릅니까? 산림청·경기도와.」 **Q16a answers well and at length**, and its own answer is
   where finding 1 lives, which is the sharp part: the card is right about the comparison and wrong
   about the word it makes the comparison with. → **WFG-243**.
3. 「그 17건은 무엇이 뒷받침합니까?」 **Answerable and now honest**, since WFG-233: nothing
   independently derives it, and `docs/MODEL_CARD.md` says so. ⚠ What the file gets wrong is the
   next sentence, which asserts a mechanism nobody measured. → **WFG-244**.
4. 「비슷한 걸 만든 사람이 이미 있지 않습니까?」 **Still no card.** Q29a's item 4 at `:1246-1247`
   still tells the student the repository does not know. → **WFG-241**, unchanged from critic #61.
5. 「0.394를 원에 견주셨는데, 이미 물리 모델 0.09가 있지 않습니까?」 Unchanged. → **WFG-236**.
6. 「이 출동 지시서, 진짜 불로 만든 겁니까?」 Answerable; **why not** is measured but is the
   author's. → **WFG-242 / NH-057**, unchanged.

## Nothing new from the author, on either channel

Seventh consecutive lap saying so. Gmail `from:siyeong0318@gmail.com subject:"WildfireGuardian
autoloop" newer_than:14d` returns 50 threads on the first page and **every one holds exactly one
message**, all of them the loop's own sends, so no reply is threaded under any of them. A second,
wider search (`"NH-0" newer_than:14d -in:sent -in:draft`) returns **zero threads**, so nothing
addressed to the loop sits outside the report threads either. **PR #31 has zero comments** (read
through the GitHub MCP, empty list). `docs/auto/decisions_seen.json` is unchanged: its `seen` list
is empty and its `applied` list still ends at **NH-031**, closed 2026-09-06 in a Claude Code session
on the laptop. **No `NH-###:` line has ever reached the loop by email.**

**24 open entries (23 DECISION + 1 BLOCKER)**, 5 open FYI besides, and **no new entry was filed this
lap**: both findings are agent-doable and nothing here needs a decision that is not already open.
Two entries (**NH-005**, **NH-014**) carry no date at all. **NH-046 is due 2026-09-10 and it is
already 2026-09-11 on the author's clock.** NH-049 and NH-051 come due 2026-09-11. **NH-057** remains
the highest-severity open entry. The sprint ends **2026-09-15**, five days out.
