# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-10T1426Z by critic #59 (CHARTER §14).
The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one
reorder per lap, with a reason. Only the most recent critic note is kept, as §14 specifies; the 54,923-byte
version this page replaced is archived verbatim at `docs/auto/archive/DIRECTION_superseded_2026-09-08T1817Z.md`.*

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a
per-point walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive.
Its defensible contribution is not forecast accuracy (Korea's own agencies forecast spread better resourced
than we can) but the **output object**: a time-dependent decision per point, with its limits measured and
written down.

## Before any row: this lap's `fix-before-next-row` items

**ZERO. Nothing here preempts a row, and that is a finding rather than an omission.** Critic #58's one item
(`docs/oracle_gap.md:233`) was cleared at `ba76b8c`, re-measured here and correct. CHARTER §14b lets a
preemption be **minutes** AND on a listed surface (README opening, finals screen, Q&A bank, manuscript,
printables, release bundle) or a red gate. Measured at `3867860`: no gate is red anywhere (`gates.py --mode
full` exits 0, GitHub run **331** green at this exact head), the printed kit's seven sources hash **7 of 7**
against the tree, the release bundle hashes **19 of 19**, and the finals screen is **11** commits behind a
30-commit limit. The one minutes-sized prose defect this lap found (**WFG-233**) is on `docs/MODEL_CARD.md`,
which is on **none** of §14b's listed surfaces, so it is a row. **Take the top row directly.**

## Next three rows, and why each is next

Table order at `3867860`. This lap spent **ZERO** §3b reorders, the **third** consecutive critic lap to spend
none; the ordering below uses this page's naming power (§14: dev 「takes the row it names when it names one
with a reason」), reversible by one line and touching no table.

1. **WFG-228 (P0, science) is the next row to claim.** Unchanged from critic #58, still `todo`, and it has
   moved from third to first only because WFG-226 and WFG-229 closed at `ba76b8c`. `docs/oracle_gap.md` §4
   concludes 「the place substantially wrong」 from **IoU 0.394** and that reading now stands on the README
   TL;DR, the finals screen's first 알려진 한계 card, JUDGE_QA **Q36 at tier T0** and the manuscript. Nothing
   in the repository says what 0.394 should be compared with. It is also the only row on this page with a
   **pre-registered score consequence**: critic #58 wrote that Track B 데이터 수집·분석·해석 returns to 20
   when it lands a null figure with its caveat, whatever the figure says. It is held at **19** again today.

2. **WFG-233 (P0, KCF, minutes plus one registration) behind it, and it is cheap.** `docs/MODEL_CARD.md:524-525`
   is the one sentence in this repository written to be pasted into the **submitted** 작품설명서, and it
   explains the weak `gangneung_2023` fold with 「탐지 약 17건」 while the same file at `:52-53` and `:86` and
   `docs/fold_sizes.md:10` explain the same fold with **8 positive cells**. Both are true and they measure
   different things; `README.md:489` already writes both correctly and the sentence that leaves the
   repository does not. 17 is registered under **no** key, is cited by neither surface, and its nearest
   grep-able home is `data/processed/spread_v2/audit.json`, which carries `LEGACY_DO_NOT_CITE.md`.

3. **WFG-230 (P0, science, minutes) third.** One paragraph in `docs/oracle_gap.md` §4 saying that all four
   slices, not three, are graded against a denominator inside 5 % of one another, and that FIRMS gives this
   fire **one** informative frame. It strengthens the document's own caveat and moves no headline.

**Behind those: ten inherited P0 rows and five sprint days.** Counted at this head, P0 `todo` is **13**: the
three named above plus WFG-007, 117, 129, 121, 106, 036, 101, 119, 024, 054; `blocked`: WFG-213 (NH-052), WFG-124 and WFG-104 (NH-032), WFG-023
(human). **WFG-007 is still the trap** its own status cell describes (「the agent half is done; the student
half is not」), so a lap falling back to table order reaches a row with nothing takeable in it. Take WFG-117
before it, or record in the row why not.

⚠ **Filing note, and it is the same deliberate departure critic #57 and #58 both made.** The stored prompt
says a larger judge-facing finding is 「filed as a P0 row at position 1」. **NH-051 is open and shows that
mechanic belongs to NH-038 option D**, while the prompt cites option **B**, whose own words put the row 「in
the table like any other」. WFG-233 is filed in table order and named here instead. If the author's answer to
NH-051 is D, moving it up is one edit.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠ **Do not edit `README.md`'s TL;DR lead, in either direction, while NH-054 is open.** Filed today: the
  「Headline result」 bullet is 2,286 characters, of which **433 (19 %)** state the result and **1,853 (81 %)**
  are the qualifications after the first ⚠. Nothing there is false and nothing is proposed for deletion; the
  proportion is a presentation judgement and it is the author's. Do not soften a caveat and do not add one.
- ⚠ **Do not edit `docs/auto/JUDGE_QA.md` without `make printables` at a new stamp and a re-pointed
  `release/kcf-finals-2026/MANIFEST.json`.** Re-proved here: the newest manifest is
  `manifest_20260910T1233Z.json` and its **seven** sources hash 7 of 7 against the tree, so the first byte
  written into the bank turns `tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree`
  red. NH-049 (its own text still says six sources; annotated, not edited).
- ⚠ **Do not write 「the fire stopped growing at 333 minutes」** anywhere. The repository has **no**
  observation between 0 and 333 minutes (obs_times are 0 / 333 / 1005 / 1480 / 1812 / 2403) and cannot say
  when the growth happened. WFG-230 is the row that says this properly.
- ⚠ **Do not "fix" 「household-level」 in `README.md:3`, `CITATION.cff:5`,
  `src/wildfireguardian/__init__.py:1` or `paper/manuscript.md:1`.** They name the **application**, not a
  per-household result, `paper/GAPS.md:389` records the ruling, and WC-013 deliberately registers no
  spelling for the bare term. **WFG-231** moves the ruling to where a lap will find it.
- ⚠ **Do not rebuild `data/processed/timeline_roles/timeline_roles.json` from a clone you deepened.**
  Re-measured here: the artifact's `last_commit_date` is **2026-09-09** and `web/finals.html`'s 개발 일정과
  역할 card prints it as `counted_through`, so the guardrail freezes a date a judge reads, and the finals are
  2026-10-24. A rebuild from a **fresh full clone** writes seven-character anchors and is safe. **WFG-217**
  is the fix; its deadline is the 10-16 freeze.
- ⚠ **Do not write 「가구 단위」 or "per-household" about the COMMITTED dispatch sheets.** `done` (WFG-222,
  `WC-013`); the corrected wording is **지점 단위** with 「화재 위험면과 지형은 합성 · 출발지는 표본 좌표」 and
  「실제 확산면으로 만든 출동 지시서는 아직 없습니다」 **in the same block**. `README.md:220-251` is the model.
  The four remaining 「가구 단위」 in `docs/auto/JUDGE_QA.md` are **deliberate and correct**. Do not "fix" them.
- **Do not settle the word 「상한」 / 「upper bound」 in any lap.** NH-053 is open. Describe the mechanism.
- ⚠ **Do not put a margin value (9, 27, 5, 19, 86) on any judge-facing surface** while NH-032, NH-034 and
  NH-052 are open. **Re-measured by the two section headers rather than copied, and this window they held
  still**: 「### 1. 가장 강한 주장에 「공정한 상대」를 세웠습니다」 opens the block at **`:274`** and
  「### 2. 철회한 주장이…」 closes it at **`:354`** at `3867860`, the same pair critic #58 measured at
  `d3ca754`. The single 「구체적인 margin 값들은 부스에서 말하지 않습니다」 line is at **`:340`**, unmoved, and
  the block contains **zero** occurrences of all five digits. **Anchor on the two headers, not on the digits.**
- ⚠ **Do not add a word to `paper/manuscript.md` without trimming one.** NH-037 came due **2026-09-10** and
  is open; `paper/check_paper.py` reads the body against a 9,000-word hard fail with single-digit margin.
- **Do not change `mr_uiseong_fa_exceeds_budget`.** It is 2, it is registered, NH-031 option A says nothing
  committed moves, and the registry half is **WFG-122** (`todo`).
- **Do not refit anything**, and do not regenerate a committed artifact (CHARTER §3 rule 2).
- **Do not re-open the AI-disclosure question** (NH-008 closed; CHARTER §9).
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13-§14).
- **Do not compare accuracy with NIFoS or G-DAPS.** The differentiator is the output object.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or
  `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).

## Readiness lines ticked in the last 24 h: ZERO, for the sixteenth consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. Re-counted from the checklist table at this head rather than inherited (⚠ its rows R1 to
R12 are at **`:1826-1837`**, not the `:1825-1836` critic #57 and #58 both cited; header `:1824`, rule `:1825`):
R1, R2, R4, R5, R6, R7, R8, R9 ticked; R3, R11, R12 not; R10 withdrawn 2026-09-04. The cause is unchanged:
R12 is the author's (NH-014); R3 is `blocked(NH-046)`; R11's row **WFG-024** is held by CHARTER §14b until
R1, R3, R4, R7, R8 and R9 all tick, of which **R3 is the only one unticked**. **NH-046 is now two days past
due, and the sprint ends 2026-09-15.** Appended to NH-046; not filed again.

**Open decisions: 21 for the author (20 DECISION + 1 BLOCKER), 5 FYI besides, and 13 at or past their date**
— NH-032, 034, 045 (09-08), NH-035, 038, 043, 044 (09-09), NH-036, 037, 042, 046, 048, 050 (09-10); NH-049
comes due **tomorrow**. ⚠ Two open entries (**NH-005, NH-014**) carry **no date at all** and drop out of any
date-based count silently; say 「13 of 21, and 2 undated」 rather than a bare number. The twenty-first is
**NH-054**, filed today. Counted at `3867860` over every `| WFG-` row: **P0 is 13 `todo`** (12 inherited plus
WFG-233), 4 blocked, 1 dropped, the rest done. ⚠ **P1 is 9 done against 108 `todo`, not the 102 critic #58 published** — measured at
three heads and recorded on WFG-107 and NH-038; the ledger is five to six items longer than the number that
entry has been argued with, which makes NH-038's case stronger rather than weaker.

## Critic's last direction note

**2026-09-10T1426Z, critic #59. ZERO §3b reorders, the third consecutive critic lap to spend none. ZERO
`fix-before-next-row` items, and the reason is measured rather than assumed: nothing found is both minutes
and on a CHARTER §14b listed surface. ONE new backlog row (WFG-233, P0 KCF, minutes plus one registration,
filed in table order). ONE new NEEDS_HUMAN entry (NH-054, the front door's caveat ratio, with four options
and nothing proposed for deletion). Three existing entries gained measurements (NH-038, NH-046, NH-049) and
two existing rows did (WFG-107, WFG-232). Scorecard: Track B 95 → 94 (제출 자료 DOWN to 19 on WFG-233);
Track A 95 → 96 (제출 자료 UP to 19 on critic #58's own pre-registration, paid). The two tracks converge on
19 for the same identically worded criterion.**

Verified at `3867860`. `gates.py --mode full` exits **0** (**2024 passed**, 63 skipped, 3 xfailed, pytest
321.1 s); `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029 and §3d
working. **GitHub `auto-gates`, runs 287 to 331: 45 runs, 38 `success`, 7 `cancelled` and ZERO `failure`**,
with **331 green at this exact head**, so CHARTER §4b sets no finding #1 for the eighth consecutive lap.
**All eight** dev reports in the window record `Reviewed by:`, all eight name `subagent`, and **six of the
eight record `block`**. **Every push in the window carried a report**: `gates.py --assert-reported` over the
45 pushed heads `f9183b0` → `3867860` returns **44 OK, 0 FAIL**. The clone was **unshallowed** before any
counting (`--is-shallow-repository` answers `false`, **717** commits) because it arrived at depth **50**
again, the third lap running.
