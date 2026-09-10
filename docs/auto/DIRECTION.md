# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-10T0523Z by critic #56 (CHARTER §14).
The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one
reorder per lap, with a reason. Only the most recent critic note is kept, as §14 specifies; the 54,923-byte
version this page replaced is archived verbatim at `docs/auto/archive/DIRECTION_superseded_2026-09-08T1817Z.md`.*

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a
per-point walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive.
Its defensible contribution is not forecast accuracy (Korea's own agencies forecast spread better resourced
than we can) but the **output object**: a time-dependent decision per point, with its limits measured and
written down.

## Before any row: this lap's one `fix-before-next-row` item

**Print `time_gap_min` beside every ratio and every IoU in `docs/oracle_gap.md` §4 and §4b, and say in one
sentence that three of the four slices are scored against the same observation.** Minutes, prose only, no new
measurement, no unregistered number. The row is **WFG-215** and its own placement note (「not a judge-facing
surface」) is false at this head: `docs/oracle_gap.md` is the cited evidence anchor from **seven places on four
judge-facing surfaces**, including card **Q36 at tier T0** in the printed kit and, new at `c4eb8d2`, the
**first** card of the finals screen's 알려진 한계 panel. ⚠ Do **not** follow the row's 「Do」 literally: per-slice
`obs_time_min` is **not** registered and printing it would break CHARTER §3 rule 3. The registration half is
the rest of the row, not the preemption.

## Next three rows, and why each is next

Table order at `9b7d21c`, after this lap's **one** §3b reorder.

1. **WFG-128 (P0, KCF) is the next row to claim**, moved to the head of the P0 block by this lap. It is
   `minutes`, judge-facing, and the author already decided it (NH-031 A, closed 2026-09-06). `docs/multi_region.md:187-192`
   states the one number in this repository that runs against the project, and it still does not say that the
   two arms are scored under **different** time rules: the future-aware arm now carries its 600-minute budget
   in the sentence, the fire-blind arm carries no budget at all, and `README.md:146` sends a judge to that page
   for 「완전한 분할」. It needs no margin value, so NH-032 does not bar it.

2. **WFG-007 and WFG-117 sit behind it and one of them is a trap.** WFG-007's own status cell says 「the agent
   half is done; the student half is not」; a dev lap that takes it in table order finds (a) a printing task
   that is the student's and (b) WFG-130. Take WFG-117 before it, or record in the row why not.

3. **Behind those: eleven P0 rows and five sprint days.** **Eleven** P0 rows are `todo` at this head, counted
   here rather than inherited: WFG-128, 007, 117, 129, 121, 106, 036, 101, 119, 024, 054. `blocked`: WFG-213
   (NH-052), WFG-124 (NH-032), WFG-104 (NH-032), WFG-023 (human). Three P0 rows closed this window
   (WFG-222, 218, 220) and none was filed, so the P0 `todo` count is down by three, the largest one-window fall
   of the sprint.

### Why one reorder, in one paragraph

DIRECTION named WFG-218 and WFG-220 and both are `done`, so this page named nothing and a dev lap would have
fallen back to table order onto WFG-007, whose remaining work is the student's. WFG-128 is the row that should
meet a dev lap first on every reading: P0, judge-facing, `minutes`, decided by the author eight days ago, and
blocked by nothing. P0 above P0, so CHARTER §14's ordering rule is untouched. The one row I would otherwise
have promoted, **WFG-215**, is handled as the preemption above rather than as a reorder, because its
minutes-sized half is a preemption and its registry half is not.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block.
- ⚠ **Do not print a per-slice `obs_time_min` from `data/processed/oracle_gap_yeongdeok.json` anywhere.**
  Only the headline `og_yeongdeok_obs_time_min` is registered; the five per-slice values are not, and
  CHARTER §3 rule 3 says a number you cannot register you do not write. The five per-slice
  `og_yeongdeok_t###min_time_gap_min` keys **are** registered and are what the preemption uses.
- ⚠ **Do not rebuild `data/processed/timeline_roles/timeline_roles.json` from a clone you deepened.**
  Unchanged from critic #55, and it now has a judge-facing edge: `web/finals.html`'s new 개발 일정과 역할 card
  prints its as-of stamp from that artifact's `last_commit_date` (**2026-09-09** at this head), so the guardrail
  freezes a date a judge reads, and the finals are 2026-10-24. A rebuild from a **fresh full clone** writes
  seven-character anchors and is safe. **WFG-217** is still the right fix and its deadline is the 10-16 freeze.
- ⚠ **Do not write 「가구 단위」 or "per-household" about the COMMITTED dispatch sheets.** `done` (WFG-222,
  `WC-013`); the corrected wording is **지점 단위** with 「화재 위험면과 지형은 합성 · 출발지는 표본 좌표」 and
  「실제 확산면으로 만든 출동 지시서는 아직 없습니다」 **in the same block**. `README.md:212-251` is the model.
  The four remaining 「가구 단위」 in `docs/auto/JUDGE_QA.md` are **deliberate and correct** (`:600` names the
  quantity, `:680-681` is the ⭕/❌ pair about other systems, `:968` is Q20a's own question). Do not "fix" them.
- **Do not file a judge-facing critic finding at table position 1 while NH-051 is open.** NH-038's own option B
  puts it 「in the table like any other」; 「at position 1」 is option **D**'s mechanic.
- **Do not settle the word 「상한」 / 「upper bound」 in any lap.** NH-053 is open. Describe the mechanism.
- **Do not put a margin value (9, 27, 5, 19, 86) on any judge-facing surface** while NH-032, NH-034 and NH-052
  are open, and not in `README.md:270-349` at all. ⚠ Those bounds **MOVED this window** (they were 263-342 at
  `7dabdef`, pushed down seven lines by WFG-218's TL;DR bullet); the `Do NOT edit` note in
  `CRITIC_LATEST.md` is re-measured there, and a lap that copies the old numbers protects the wrong lines.
- ⚠ **Do not add a word to `paper/manuscript.md` without trimming one.** `check_paper.py` reads **8,997** body
  words at this head against a 9,000 hard fail: **three** words of margin, up from zero. NH-037 came due
  **2026-09-10** and is open.
- **Do not refit anything**, and do not regenerate a committed artifact (CHARTER §3 rule 2).
- **Do not add documents to the release bundle.** WFG-128 changes text on a file already reachable from it.
- **Do not re-open the AI-disclosure question** (NH-008 closed; CHARTER §9).
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13-§14).
- **Do not compare accuracy with NIFoS or G-DAPS.** The differentiator is the output object.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or
  `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).

## Readiness lines ticked in the last 24 h: ZERO, for the thirteenth consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. The cause is unchanged and was re-read rather than restated: R12 is the author's (NH-014);
R3 is `blocked(NH-046)`; R11's row **WFG-024** is held by CHARTER §14b until R1, R3, R4, R7, R8 and R9 all
tick, of which **R3 is the only one unticked**. **NH-046 came due 2026-09-10 and is open.**

⚠ **This lap stops describing the zero and measures what §14b's other half has cost, because that is a
direction fact and not a product fact.** Counted at this head across the whole table: **P0 is 64 done, 11 todo,
4 blocked** — the loop closes P0 rows and closed three this window. **P1 is 6 done and 100 todo.** Six, over the
whole sprint. Every critic lap in the last 24 h added one or two rows and every dev lap removed one or two, so
the total `todo` count went **104 → 107** while `done` went 32 → 33. §14b releases the P1 infra block only when
R1, R3, R4, R7, R8 and R9 tick, R3 cannot tick without the author, and the sprint ends **2026-09-15**. So the
P1 queue is, on the measured rate, a **write-only ledger**, and the critic is its main producer. That
measurement is appended to **NH-038**, which is the author's question about exactly this rule, rather than
filed as a fourteenth question.

## Critic's last direction note

**2026-09-10T0523Z, critic #56. ONE §3b reorder (WFG-128 to the head of the P0 block). ONE
`fix-before-next-row` item (WFG-215's minutes-sized half). ZERO new backlog rows and ZERO new NEEDS_HUMAN
entries: every finding this lap made belongs to a row that already exists, and saying so is the restraint
CHARTER §7 asks for. Two rows updated with measurements (WFG-215, WFG-217) and one moved (WFG-128). NH-038
raised MEDIUM to HIGH on a new measurement. Scorecard: Track B 94 HELD on two moves that offset (제출 자료 UP
to 20, 데이터 수집·분석·해석 DOWN to 19); Track A 93 → 94 (제출 자료 UP to 18), because Track A has no
데이터 row for the deduction to land on.**

Verified at `9b7d21c`. `gates.py --mode full` exits **0** (**1958 passed**, 64 skipped, 3 xfailed, pytest
373.8 s, up 17 tests in one window); `baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts,
which is NH-029 and §3d working. **GitHub `auto-gates`, runs 283 to 315: no `failure` anywhere in the window**,
**four** `cancelled` (284, 306, 310, 312), each superseded by the next push within minutes, and **315 green at
this exact head**, so CHARTER §4b sets no finding #1 for the fifth consecutive lap. Every dev report in the
window records `Reviewed by:`, and **seven of the eight** record `subagent (block)` and spend commits acting
on it (the eighth, 1928Z, records `pass`);
`gates.py --assert-reported --base 435c54d` exits **0** over 66 substantive paths. `factchk`: the window adds
no new external URL and no new citation to any judge-facing surface; the three new URLs in the diff are inside
`docs/auto/` record-class pages.
