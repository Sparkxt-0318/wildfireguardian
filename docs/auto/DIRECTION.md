# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-10T1657Z by critic #60 (CHARTER §14).
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

**ZERO, and the reason is measured rather than assumed.** CHARTER §14b lets a preemption be **minutes** AND
on a listed surface (README opening, finals screen, Q&A bank, manuscript, printables, release bundle) or a
red gate. Measured at `71e95ee`: no gate is red anywhere (`gates.py --mode full` exits 0, **2041 passed**;
GitHub `auto-gates` run **338** green at this exact head), the printed kit's seven sources hash **7 of 7**
against the tree, the release bundle hashes **19 of 19**, and the finals screen's stamp `4ab2e07` is **5**
commits behind a 30-commit limit. The window's sharpest defect (**WFG-236**) sits on `docs/disc_null.md` and
`docs/oracle_gap.md`, which are on **none** of §14b's listed surfaces and in **neither** hashed set, so it
is a row. **Take the top row directly.**

The one thing this lap did NOT leave for a row: **WFG-235's own text was corrected in place**, because as
filed it told the next lap to write `2.536` onto a **T0** card while the same day's `docs/disc_null.md:119-120`
says 「2.5360 is not quotable without 2.2044 beside it」. That is a backlog edit, not a preemption.

## Next three rows, and why each is next

Table order at `71e95ee`. This lap spent **ZERO** §3b reorders, the **fourth** consecutive critic lap to
spend none; the ordering below uses this page's naming power (§14: dev 「takes the row it names when it names
one with a reason」), reversible by one line and touching no table.

1. **WFG-233 (P0, KCF, minutes plus one registration) is the next row to claim.** Unchanged from critic #59
   except that it has moved from second to first, because **WFG-228 closed at `b8fd6a8`**.
   `docs/MODEL_CARD.md:524-525` is the one sentence in this repository written to be pasted into the
   **submitted** 작품설명서, and it explains the weak `gangneung_2023` fold with 「탐지 약 17건」 while the
   same file at `:52-53` and `:86` and `docs/fold_sizes.md:10` explain the same fold with **8 positive
   cells**. `README.md:489` already writes both correctly. It costs minutes and pays no printables rebuild.

2. **WFG-236 (P0, KCF) behind it, and it is the window's own finding.** `docs/disc_null.md:20-21` and
   `docs/oracle_gap.md:180-181` both assert, in bold, that nothing in the repository said what **0.394**
   should be compared with. `README.md:520-522` and `:888-891` have compared it to the Rothermel surface
   model's **~0.09** and called it 「약 4배」 for months, sourced to
   `docs/ROUTING_INTEGRATION_REPORT.md:183`. The two comparisons point opposite ways, neither page names the
   other, and the README's comparator is a model its own TL;DR calls buggy. The row repairs the two
   sentences and cross-links; whether the README's framing itself moves is **NH-055**, the author's.

3. **WFG-237 (P0, science) third, and WFG-235 rides with it.** `docs/disc_null.md` §4 measured that the
   model's core centre of mass travels **3,646.1 m** where the observed footprint's travels **1,124.8 m**,
   and that the stationary disc ends up **closer to the truth** than the model. That is the magnitude the
   TL;DR's existing 「42 is what this policy buys when its own prediction is believed」 caveat never had, and
   today it exists in one file that nothing points at. WFG-237 is the document half; **WFG-235** is the Q36
   card half and pays the `make printables` rebuild NH-049 names, so the two should ride together.

**Behind those: eleven more P0 rows and five sprint days.** Counted at this head over every `| WFG-` row:
P0 `todo` is **15** (the three named above plus WFG-235, 230, 007, 117, 129, 121, 106, 036, 101, 119, 024,
054); `blocked`: WFG-213 (NH-052), WFG-124 and WFG-104 (NH-032), WFG-023 (human). **WFG-007 is still the
trap** its own status cell describes (「the agent half is done; the student half is not」), so a lap falling
back to table order reaches a row with nothing takeable in it. Take WFG-117 before it, or record in the row
why not.

⚠ **Filing note, and it is the same deliberate departure critics #57, #58 and #59 all made.** The stored
prompt says a larger judge-facing finding is 「filed as a P0 row at position 1」. **NH-051 is open and shows
that mechanic belongs to NH-038 option D**, while the prompt cites option **B**, whose own words put the row
「in the table like any other」. WFG-236 and WFG-237 are filed in table order and named here instead. If the
author's answer to NH-051 is D, moving them up is one edit.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠ **Do not quote `2.5360` or the pair `0.3941 / 0.1554` on any judge-facing surface without `2.2044` and
  `0.2577 / 0.1169` in the same block.** `docs/disc_null.md:119-120` and `docs/oracle_gap.md:194` both say
  so in the tree: `obs_stack` is cumulative, the 249-cell `t = 0` seed is inside the observation being
  scored, the model's core contains all 249 by construction and the disc recovers 92. WFG-235's row text
  was corrected here for exactly this.
- ⚠ **Do not edit `README.md`'s IoU bullet (`:520-522` Korean, `:888-891` English) while NH-055 is open**,
  and do not delete the `~0.09` Rothermel comparison in either direction. WFG-236 repairs the two `docs/`
  sentences and adds a cross-reference; the README framing is the author's call.
- ⚠ **Do not edit `README.md`'s TL;DR lead, in either direction, while NH-054 is open.** The 「Headline
  result」 bullet is 2,286 characters, of which 433 (19 %) state the result and 1,853 (81 %) are the
  qualifications after the first ⚠. Nothing there is false and nothing is proposed for deletion.
- ⚠ **Do not edit `docs/auto/JUDGE_QA.md` without `make printables` at a new stamp and a re-pointed
  `release/kcf-finals-2026/MANIFEST.json`.** Re-measured here in one process: the newest manifest is
  `manifest_20260910T1233Z.json` and its **seven** sources hash **7 of 7** against the tree, so the first
  byte written into the bank turns
  `tests/test_printables.py::test_the_newest_printable_is_not_stale_against_the_tree` red. NH-049 (its own
  text still says six sources; annotated, not edited).
- ⚠ **Do not write 「the fire stopped growing at 333 minutes」** anywhere. The repository has **no**
  observation between 0 and 333 minutes (obs_times are 0 / 333 / 1005 / 1480 / 1812 / 2403). WFG-230 says
  this properly.
- ⚠ **Do not "fix" 「household-level」 in `README.md:3`, `CITATION.cff:5`,
  `src/wildfireguardian/__init__.py:1` or `paper/manuscript.md:1`.** They name the **application**,
  `paper/GAPS.md:389` records the ruling, and WC-013 deliberately registers no spelling for the bare term.
  **WFG-231** moves the ruling to where a lap will find it.
- ⚠ **Do not rebuild `data/processed/timeline_roles/timeline_roles.json` from a clone you deepened.** The
  artifact's `last_commit_date` is **2026-09-09** and `web/finals.html`'s 개발 일정과 역할 card prints it as
  `counted_through`, so the guardrail freezes a date a judge reads. A rebuild from a **fresh full clone**
  writes seven-character anchors and is safe. **WFG-217** is the fix; deadline 10-16.
- ⚠ **Do not write 「가구 단위」 or "per-household" about the COMMITTED dispatch sheets.** `done` (WFG-222,
  `WC-013`); the corrected wording is **지점 단위** with 「화재 위험면과 지형은 합성 · 출발지는 표본 좌표」
  and 「실제 확산면으로 만든 출동 지시서는 아직 없습니다」 **in the same block**. `README.md:220-251` is the
  model. The four remaining 「가구 단위」 in `docs/auto/JUDGE_QA.md` are **deliberate and correct**.
- **Do not settle the word 「상한」 / 「upper bound」 in any lap.** NH-053 is open. Describe the mechanism.
- ⚠ **Do not put a margin value (9, 27, 5, 19, 86) on any judge-facing surface** while NH-032, NH-034 and
  NH-052 are open. **Re-measured by the two section headers rather than copied, and they held again this
  window**: 「### 1. 가장 강한 주장에 「공정한 상대」를 세웠습니다」 opens the block at **`:274`** and
  「### 2. 철회한 주장이…」 closes it at **`:354`** at `71e95ee`, the same pair critic #58 and #59 measured.
  The single 「구체적인 margin 값들은 부스에서 말하지 않습니다」 line is at **`:340`**, unmoved, and the
  block contains **zero** occurrences of all five digits. **Anchor on the two headers, not on the digits.**
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

## Readiness lines ticked in the last 24 h: ZERO, for the seventeenth consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. Re-counted from the checklist table at this head rather than inherited (⚠ its rows R1 to
R12 are now at **`:1832-1843`**, six lines below the `:1826-1837` critic #59 correctly measured at
`3867860`, because this lap added six lines to the page's lead; header `:1830`, rule `:1831`):
R1, R2, R4, R5, R6, R7, R8, R9 ticked; R3, R11, R12 not; R10 withdrawn 2026-09-04. The cause is unchanged:
R12 is the author's (NH-014); R3 is `blocked(NH-046)`; R11's row **WFG-024** is held by CHARTER §14b until
R1, R3, R4, R7, R8 and R9 all tick, of which **R3 is the only one unticked**. ⚠ **NH-046 is due TODAY,
2026-09-10, and it is NOT past due**: its heading reads 「(by 2026-09-10)」 at `docs/auto/NEEDS_HUMAN.md:2847`
and the entry was never re-dated. Critic #58 and critic #59 both published 「NH-046 is now two days past
due」, on this page and on `KCF_READINESS.md`; that is corrected here rather than repeated, and it is a fresh
instance of **WFG-107** (a hand-written figure beside a checkable one). The sprint still ends 2026-09-15.
⚠ This page's own lead was **one lap stale** when this lap read
it (it said 「critic #58 ... FIFTEENTH」 beside a `:1841` section saying 「critic #59 ... SIXTEENTH」);
repaired here by hand, and **WFG-238** is the gate that would bind them.

**Open decisions: 22 for the author (21 DECISION + 1 BLOCKER), 5 FYI besides, and 13 at or past their date**
— NH-032, 034, 045 (09-08), NH-035, 038, 043, 044 (09-09), NH-036, 037, 042, 046, 048, 050 (09-10), where
the last group is due **today** rather than overdue. **NH-049 and NH-051 both come due tomorrow.**
⚠ Two open entries (**NH-005, NH-014**) carry **no date at all** and drop out of any date-based count
silently; say 「13 of 22, and 2 undated」 rather than a bare number. ⚠ And **NH-035 is not a third undated
entry**, though a heading regex anchored on 「(by YYYY-MM-DD)」 says it is: its date is inside a longer
parenthesis, 「(by 2026-09-09, one day past; raised to HIGH by critic #55 …)」. The twenty-second entry is
**NH-055**, filed today. Counted at `71e95ee` over every `| WFG-` row: **P0 is 15 `todo`** (12 inherited plus
WFG-235 from critic #59's window and WFG-236 and WFG-237 filed today), 4 blocked, 1 dropped, the rest done.
P1 is **9 done against 105 `todo`** (WFG-238 added here).

## Critic's last direction note

**2026-09-10T1657Z, critic #60. ZERO §3b reorders, the fourth consecutive critic lap to spend none. ZERO
`fix-before-next-row` items, measured rather than assumed: the window's sharpest defect is on two `docs/`
pages that are on no §14b surface and in neither hashed set. THREE new backlog rows (WFG-236 P0 KCF,
WFG-237 P0 science, WFG-238 P1 infra) and ONE existing row corrected in place (WFG-235, which as filed told
the next lap to write onto a T0 card the number its own day forbids quoting alone). ONE new NEEDS_HUMAN
entry (NH-055, the README's 「약 4배」 against today's 2.2×, four options, nothing proposed for deletion).
Scorecard: Track B 94 → 96 (데이터 수집·분석·해석 UP to 20 on critic #58's pre-registration, PAID by
WFG-228; 창의성 UP to 19). Track A 96 → 97 (창의성 UP to 19 on the identical criterion). 제출 자료 HELD at
19 on both tracks: WFG-233 is still open and WFG-236 is new, against a window that shipped the seed-removed
correction onto both pages and into the band on all 84 keys.**

Verified at `71e95ee`. `gates.py --mode full` exits **0** (**2041 passed**, 64 skipped, 3 xfailed, pytest
315.2 s); `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029 and §3d
working. **GitHub `auto-gates`, runs 294 to 338: 45 runs, 36 `success`, 9 `cancelled` and ZERO `failure`**,
with **338 green at this exact head**, so CHARTER §4b sets no finding #1 for the ninth consecutive lap.
**All nine** dev reports in the window record `Reviewed by:`, all nine name `subagent`, and **seven of the
nine record `block`**. **Every push in the window carried a report**: `assert_reported`'s own predicate,
replayed pairwise over the 46 pushed heads `359fd15` → `71e95ee`, returns **46 OK, 0 FAIL**. The clone was
**unshallowed** before any counting (`--is-shallow-repository` answers `false`, **725** commits) because it
arrived at depth **51**, the fourth lap running.
