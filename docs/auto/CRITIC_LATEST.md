# CRITIC_LATEST — critic #59, 2026-09-10T1426Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head: `3867860`, and
every measurement below was taken at that head in this clone unless it says otherwise. ⚠ This clone arrived
**SHALLOW at exactly 50 commits** for the third lap running, which is almost exactly the 24-hour window, so
`git log --since` would have returned the whole clone and truncated silently. I ran `git fetch --unshallow`
before counting anything: `git rev-parse --is-shallow-repository` now answers **`false`** and
`git rev-list --count HEAD` answers **717**, so the window below is a real 24 hours and the ancestry
statements here are licensed under CHARTER §4. Full report:
`docs/auto/reports/2026-09-10T1426Z-critic.md`.*

## `fix-before-next-row`: ZERO, and the zero is measured

Critic #58's one item (`docs/oracle_gap.md:233`) was cleared at `ba76b8c`. I re-measured the repair rather
than accepting the lap's account of it, and it is correct: the `og_yeongdeok_*` prefix holds **30** keys,
**all 30** carry a `forbidden_phrasings` list of the **same seven** spellings, the string
「what the forecast buys」 is registered on **zero** keys, and the new sentence at `:229-241` names the
prefix, quotes no spelling, says why it cannot quote one, and points at the test that actually binds it.
The dev lap also refused the sentence critic #58 suggested, and it was right to: writing
「this measures what the model buys」 into that page turns
`tests/test_oracle_gap.py::test_the_forbidden_phrasings_are_registered_and_absent_from_the_doc` red. **A
preemption that would have shipped a second false appeal to the registry under the first one was caught by
the lap it was given to.** That is the loop working.

**Why I set none of my own.** CHARTER §14b lets a preemption be **minutes** AND on a listed surface (README
opening, finals screen, Q&A bank, manuscript, printables, release bundle) or a red gate. Neither half is
available today:

| candidate | why it is not a preemption |
|---|---|
| a red gate | there is none. `gates.py --mode full` exits **0** here; GitHub `auto-gates` run **331** is green at this exact head; runs 287 to 331 hold **ZERO** `failure` |
| the printed kit | `manifest_20260910T1233Z.json`'s **seven** sources hash **7 of 7** against the tree |
| the release bundle | `release/kcf-finals-2026/MANIFEST.json`'s **19** entries hash **19 of 19** against their sources |
| the finals screen | build stamp `53d1a4e`, **11** commits behind a 30-commit limit; registry payload **453 / 395** against **453 / 395** in `docs/NUMBERS.json` |
| the one minutes-sized prose defect I found (**WFG-233**) | it is on `docs/MODEL_CARD.md`, which is on **none** of §14b's listed surfaces. It is a row |
| the Q&A bank | any byte written there turns `tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` red until `make printables` runs, and this routine builds no artifact (NH-049) |

**So the next dev lap owes this critic nothing and should take `docs/auto/DIRECTION.md`'s top row directly:
WFG-228.**

## The one new finding, filed as a row

**WFG-233 (P0, KCF, minutes plus one registration) — the one sentence in this repository written to be
pasted into the SUBMITTED 작품설명서 explains the weak fold with a number the rest of the same file does not
use, and cites nothing for it.**

`docs/MODEL_CARD.md` §「작품설명서 (Korean writeup) correction mapping」 is not a note about the repository.
Its closing 「Suggested replacement sentence (formal 합니다체)」 is text the author is told to put into a
document five judges receive. At `:524-525` it reads 「평균 ROC-AUC는 **0.89**입니다(6개 산불, 범위
0.68–0.97; 0.68은 **탐지 약 17건**의 소규모 산불 폴드입니다)」.

| where | how the same fold is explained |
|---|---|
| `docs/MODEL_CARD.md:52-53`, the headline blockquote | 「the 0.68 fold, `gangneung_2023`, has only **~8 positives**」 |
| `docs/MODEL_CARD.md:86`, the per-fire table | 「**~8 positives**, fold far too small for a stable estimate」 |
| `docs/fold_sizes.md:10` | **396 rows, 8 positive cells, 2 overpasses, 1 transition, 0.26 % of the evidence** |
| `docs/MODEL_CARD.md:524-525`, the sentence that LEAVES the repository | 「**탐지 약 17건**」 |
| `README.md:489` | 「양성 약 **8**건(탐지 약 **17**건)뿐인 소규모·잡음 폴드」 |

**Both numbers are true and they measure different things**, which is why this is a defect rather than an
error: 17 is the whole-fire FIRMS detection count and 8 is the count of positive 500 m cells in the fold,
and the pasted sentence distinguishes them only through the single word 「탐지」. `README.md:489` already
writes both correctly, so the repair exists in the repository and has not reached the sentence that leaves it.

**The sourcing half is sharper.** 「17」 is registered under **no key** of the 453 in `docs/NUMBERS.json`
(the only registered 17 is `juso_yeongdeok_samul_coolingcen_point_count`), so `make verify` never re-derives
it, and neither surface names a source. It does trace, to
`data/processed/detection/firms_first_detection.json :: gangneung_2023.n` = **17**, which reaches
`gk2a_detection_floor.json` through `scripts/gk2a_detection.py:366`. ⚠⚠ **And there is a second 17, in the
directory that must not be cited:** `data/processed/spread_v2/audit.json` gives `detections_csv` **17** and
`detections_in_grid` **17** for the same fire over dates 2023-04-11 to 04-13, and that directory carries
`LEGACY_DO_NOT_CITE.md` and the instruction 「if you are writing a document, do not open these files」. The
two 17s are differently scoped and agree by coincidence, **so a lap that sources this number by grepping
lands in the legacy file first**. Do not cite it; cite `firms_first_detection.json`.

## Two existing rows and three existing entries gained measurements, and one of them corrects this routine

**WFG-107, sixth recorded instance, and this time it is the backlog's own size.** Critic #58 published
「P1 is 9 done against **102** `todo`, up one this lap, and mine is the 102nd」 on `DIRECTION.md`, in
`CRITIC_LATEST.md` and in its report. Counted here in one process over every `| WFG-` row, with the status
read as the fourth field from the end so a `|` inside a title cell cannot shift it:

| head | what it is | P1 `done` | P1 `todo` |
|---|---|---:|---:|
| `d3ca754` | the head critic #58 reviewed | 9 | **106** |
| `f4ef66e` | **the commit critic #58 itself pushed** | 9 | **107** |
| `3867860` | this head | 9 | **108** |

`done` was right both times; only `todo` is wrong, by five, and 「mine is the 102nd」 names a position
WFG-231 never occupied (it was the 107th). The number is load-bearing, because it is the evidence NH-038
uses to call the P1 queue a write-only ledger. **The direction of the error makes NH-038's case stronger,
not weaker.** Corrected on `DIRECTION.md`, appended to NH-038 and to WFG-107.

**WFG-232, the write-side gap sized.** **289 of 453** keys declare `forbidden_phrasings`, over **27**
prefixes (`pp` 57/57, `mr` 52/52, `og` 30/30, `timeline` 20/20, `ppshape` 18/18 are the largest). The write
side is bound for **two documents and two prefixes**, so **25 of the 27 have no document scanned at all**.
I also re-ran the reader enumeration **without a `head`**, which is that row's own lesson: five test files
and eight scripts, the five tests being the four the corrected row names plus `tests/test_judge_qa_bank.py`.
The eight scripts write the field rather than enforce it; `scripts/measure_demo_script_pace.py:251` declares
three spellings for `demo_*` and `tests/test_demo_script_pace.py` does not read them, which is one concrete
instance of the 25.

**NH-049 has two stale figures and its mechanism is unchanged.** It says the bank is one of **six** kit
sources; it is one of **seven** today. It lists three queued judge questions; **WFG-027 is
`done(20260909T1517Z)` and WFG-194 is `done(20260909T0321Z)`**, so the queue is **WFG-197 and WFG-228**,
two rather than three. The entry is a record and is annotated rather than edited (CHARTER §3.7).

## The new NEEDS_HUMAN entry, and it is the only judgement I could not make

**NH-054 · DECISION · open · due 2026-09-13.** `README.md`'s TL;DR 「Headline result」 bullet is **2,286
characters**: **433 (19 %)** before the first ⚠, stating the result and the 42 of 458; **1,853 (81 %)** after
it, holding four qualifications. Nothing there is false and every qualification was added by a lap that was
right to add it. What no lap may decide is the **proportion**, because the two judging lenses split on it by
construction: the fire scientist reads the caveats as the best thing in the repository, and the
disaster-response official reaches the end of the bullet without learning what the tool outputs.
`docs/auto/DIRECTION.md`'s standing rule sends a disagreement about the README lead to the author with
options rather than to an edit, so that is what happened. **Four options, and none of them deletes,
softens, hedges or withdraws anything.** My reading is offered as C (result first, then a pointer to a new
subsection holding all 1,853 characters verbatim) and it is not applied.

⚠ **Until NH-054 is answered, do not edit the README TL;DR lead in either direction.** Do not soften a
caveat and do not add one.

## What this lap verified and found clean

- **`gates.py --mode full` exits 0 at `3867860`** — **2024 passed**, 63 skipped, 3 xfailed, pytest 321.1 s,
  up 8 tests on critic #58's run and 22 seconds slower. `baseline-verify` WARNs on the two git-ignored
  `data/raw/**` contracts, which is NH-029 and CHARTER §3d working as designed.
- **GitHub `auto-gates`, runs 287 to 331: 45 runs, 38 `success`, 7 `cancelled` (306, 310, 312, 316,
  317, 320, 326, each superseded by the next push within minutes) and ZERO `failure`**, with run **331 green at this exact head**.
  CHARTER §4b sets **no finding #1** for the eighth consecutive lap.
- ⚠ **`curl` against `api.github.com` WORKS in this sandbox and returned HTTP 200 again**, the second lap
  running. CHARTER §4's sandbox-facts paragraph and WFG-119 both record it as 403. It is not 403 today.
  Recorded, not built on: a capability that flips between laps is not a foundation.
- **All eight** dev reports in the window record `Reviewed by:`, all eight name `subagent`, and **six of the
  eight record `block`** (1928Z and 0952Z record `pass`). The 1302Z block is the most useful thing in the
  window: the reviewer refuted the lap's own self-declared main finding with one command, and the mechanism
  was a `grep -rln` piped into `head` that cut the list at ten lines with two test files below the cut.
- **Every push in the window carried a report.** `gates.py --assert-reported` run over the 45 consecutive
  pushed heads from `f9183b0` to `3867860`: **44 OK, 0 FAIL**.
- **WFG-226 and WFG-229 shipped as the 1302Z report says, and I checked the built objects rather than the
  tree.** The kit was rebuilt at `20260910T1233Z`, `release/kcf-finals-2026/MANIFEST.json` names it, all
  seven printed sources hash 7 of 7 against the tree and all 19 bundle entries hash 19 of 19 against theirs.
  `timeline_agent_trailer_commits` = **513** and `timeline_total_commits` = **662** are both registered at
  `git_commit` `89da7d3`, `git rev-list --count 89da7d3` answers **662** exactly, and the five phase commit
  counts (55 + 42 + 99 + 49 + 417) sum to 662 with `commits_outside_phases` = 0.
- **`factchk` on the window's new prose about the world: nothing to correct.** The window adds no external
  citation and no URL to any judge-facing surface. The new URLs are all in `docs/auto/knowledge/` and
  `docs/auto/research/`, each carrying an `[opened]` marker, and CHARTER §13 keeps their figures off cards,
  the README, the manuscript and `docs/NUMBERS.json`.
- **The `hate` root objection, and it did not survive as a finding.** *「The front door spends four fifths of
  its headline retracting, and the one affirmative claim left, the output object, is the only claim in the
  repository with no measurement attached to it.」* The cheapest test was to count, and the count is real
  (19 % against 81 %). But the second half is false: the output object **is** measured, by 42 of 458, by the
  four registered per-slice IoUs, and by `docs/oracle_gap.md` §4. What the count actually shows is a
  presentation question, not an evidence question, so it became **NH-054** rather than a finding.

## `Do NOT edit` notes — one re-stated after re-checking, one new, both line-scoped

CHARTER §14c: such a note names the exact lines and the measurement behind it, and expires at the next
critic lap unless that lap re-states it after re-checking.

**RE-STATED, re-measured at `3867860`. Do not put a margin value (9, 27, 5, 19, 86) anywhere in the README's
Round-4 section 1 while NH-032, NH-034 and NH-052 are open.** Measured by the two section headers rather
than copied: 「### 1. 가장 강한 주장에 「공정한 상대」를 세웠습니다」 opens the block at **`:274`** and
「### 2. 철회한 주장이…」 closes it at **`:354`**. That is the **same pair** critic #58 measured at `d3ca754`,
so the block held still this window after growing by one line the window before. The single
「구체적인 margin 값들은 부스에서 말하지 않습니다」 line is at **`:340`**, unmoved, and the block contains
**zero** occurrences of all five digits as standalone numbers. **Anchor on the two headers, not on the digits.**

**NEW, and it is about a line reference rather than a claim. Do not re-emit the readiness checklist table by
appending a copy of it to `docs/auto/KCF_READINESS.md`.** Measurement: the table's rows R1 to R12 sit at
**`:1826-1837`** at this head (header `:1824`, rule `:1825`), critic #57, #58 and this lap all cite it by
line, and **critic #57 and #58 both cited `:1825-1836`, off by one**, because critic #58's own append moved
it. A lap that needs to tick a line **edits the status cell in place at those lines**; a lap that only
reports appends prose and leaves the table where it is, which is what this lap did. ⚠⚠ **And there is a
second, sharper reason, which this lap learned by turning the suite red on its own first draft:** a report
table in an appended section whose first cell reads `| R7 |` or `| R9 |` makes
`tests/test_printables.py::test_r7_still_enumerates_the_five_printables_this_list_resolves` and
`tests/test_finals_bundle.py::test_r9_still_enumerates_the_contents_this_list_resolves` **fail**, because
each asserts that **exactly one** line of this file starts with that prefix. My verification table was
rewritten to `| line R7 |` and the note is now in `KCF_READINESS.md` itself. **Write `line R7`, never
`R7`, as the first cell of any table you append to that file.** **This note expires at
the next critic lap unless that lap re-states it after re-measuring the line numbers.** It freezes no file,
no table content and no readiness question.

**NOT re-stated, because the defect it guarded is gone.** Critic #58's `docs/oracle_gap.md:233` item is
cleared at `ba76b8c` and re-verified above. The note expires and is not carried forward.

## Direction

**ZERO §3b reorders, for the third consecutive critic lap.** WFG-226 and WFG-229 closed, so
`docs/auto/DIRECTION.md`'s own list advanced by itself: **WFG-228** is now the top row, WFG-233 second and
WFG-230 third. A newly filed row is not a move, and WFG-233 is filed **in the table like any other P0 row**,
not at position 1. ⚠ **Same deliberate departure from the stored prompt that critic #57 and #58 both made,
and for the same reason:** the prompt says 「a P0 row at position 1」 and **NH-051 proves that mechanic is
NH-038 option D's while the prompt cites option B**, whose own words put the row 「in the table like any
other」. NH-051 is open. If the author answers D, moving WFG-233 up is one edit.

**Readiness: 8 of 11, ZERO ticked, SIXTEENTH consecutive critic lap.** R1, R2, R4, R5, R6, R7, R8, R9
ticked; R3, R11, R12 not; R10 withdrawn 2026-09-04. **R3 is `blocked(NH-046)` and NH-046 is now two days
past due**, R11's WFG-024 is held behind R3 by CHARTER §14b, and R12 is the author's (NH-014). **One open
decision of the author's is holding two of the three remaining lines.** Five days of sprint remain. Same
finding sixteen times; appended to NH-046 rather than filed again.

**Open decisions: 21 for the author (20 DECISION + 1 BLOCKER), plus 5 FYI, and 13 are at or past their
stated date** — parsed here over `^## NH-\d+ · (DECISION|BLOCKER) · open` with the date read from the same
header line. Overdue: **NH-032, 034, 045 (09-08), NH-035, 038, 043, 044 (09-09), NH-036, 037, 042, 046, 048,
050 (09-10)**. **NH-049 comes due tomorrow.** Two open entries carry **no date at all** (NH-005, NH-014) and
fall out of any date-based count, so say 「13 of 21, and 2 undated」 rather than a bare number. The
twenty-first is NH-054, filed today. The generated block in the report email is the authority if the two
ever disagree.

**Scorecard: Track B 95 → 94, Track A 95 → 96, and the divergence is a convergence.** 제출 자료 moves on
both tracks, in opposite directions, and lands on **19 on both** for a criterion the two tables word
identically. Track A UP on critic #58's own stated condition, now paid and verified on the object rather
than the report (7 of 7 kit sources, 19 of 19 bundle entries). Track B DOWN on WFG-233, a defect that
predates this window and is scored anyway, because a 20 on a 20-point row is a claim that nothing was found.
데이터 수집·분석·해석 HELD at 19; critic #58's pre-registration stands unchanged, and returns it to 20 when
WFG-228 lands a null figure with its caveat, whatever the figure says. **Pre-registered for critic #60:**
제출 자료 reaches **20 on both tracks** when WFG-233 closes with the count registered, and falls back to 18
on either track if a kit source drifts against its manifest.
