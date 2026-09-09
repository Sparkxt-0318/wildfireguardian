# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-09T0230Z by critic #47 (CHARTER §14).
The dev routine reads this before it claims a row; the critic re-checks it after every dev lap, at most one
reorder per lap, with a reason. Only the most recent critic note is kept, as §14 specifies; the 54,923-byte
version this page replaced is archived verbatim at `docs/auto/archive/DIRECTION_superseded_2026-09-08T1817Z.md`.*

## Thesis (two sentences)

WildfireGuardian forecasts where an already-burning Korean wildfire goes next, and turns that forecast into a
per-household walk-or-be-rescued decision for rural elderly residents, on public data a stranger can re-derive.
Its defensible contribution is not forecast accuracy — Korea's own agencies forecast spread better resourced
than we can — but the **output object**: a household-level, time-dependent decision with its limits measured
and written down.

## Next three rows, and why each is next

Table order at `86f8929` after critic #47. **This lap spent its ONE §3b reorder moving a non-P0 row DOWN
below the P0 block (WFG-202), which is the only direction that rule permits. It set NO `fix-before-next-row`
item and added NO row above the P0 block.** The first `todo` row in table order is now WFG-194, so the table
and this page agree without further instruction.

1. **WFG-194 (P0, KCF)** — 창의성 is **20 points on both rubric tables** and the 심사기준 names it first
   (「단순 암기 발표 지양; 창의성, 과학적 원리, 과학적 사고 중점」). Re-measured at this head, unpiped:
   a count of 창의 or 독창 answers **0** on `web/finals.html`, **0** on `docs/auto/DEMO_SCRIPT_5MIN.md`,
   **2** on `docs/auto/JUDGE_QA.md`. `docs/creativity_card.md` exists and holds **10** such mentions, and
   nothing under `release/` or `scripts/` references it, so it is in **none** of the printed kit's six
   `SOURCES`. The material is written; a judge cannot reach it. This is an assembly onto surfaces that
   exist, not a new claim.
2. **WFG-125 (P0, science)** — unchanged in place and **re-costed against critic #45's re-costing of it**.
   Critic #45 raised it to P0 on 「the input is already committed」. It is committed and it is a **sample,
   not a field**: `spread_v2_lofo_oof_cells.csv.gz` scores **4,859** distinct cells = **18.3 %** of 영덕's
   26,607-cell hazard grid (`routing_demo.npz`, `haz_stack` (5, 181, 147)), 50.1 % of Uiseong-Andong and
   16.9 % of Uljin-Samcheok. The expensive branch therefore needs a fill rule for the other ~82 %, and a
   fill rule chosen after seeing the margin is a second post-hoc maximum on the headline number. **The
   second branch — record the absence with the paths checked — is the one that fits a lap**, and the paths
   are now on the row.
3. **WFG-024 (P0, infra) — UNBLOCKED THIS LAP, and it is the row that ticks readiness line R11.** It had
   been `blocked(WFG-022, WFG-023)` and neither blocker gates the work. `docs/HANDOFF_ROUND3.md:898` is
   rule 1 of the §5 block this loop binds itself to and it reads 「All work stays on `round3-dev`」 — a live
   instruction naming an abandoned branch, inside the one rule set the loop may never break.

Behind those, the P0 block: WFG-007, WFG-117, WFG-128, WFG-129, WFG-121, WFG-106, WFG-036, WFG-101,
WFG-119, WFG-054. **Thirteen P0 rows `todo`, six sprint days.** That ratio is still the most important
fact on this page and it did not improve; one row left the block (WFG-201 done) and one re-entered it
(WFG-024 unblocked). The decision that would resolve it is **NH-038, due today**.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block. CHARTER §14b
  holds loop hygiene behind the readiness lines. This lap's three new rows (WFG-203, WFG-204, WFG-205) were
  appended at the **end** of the table for exactly that reason.
- **Do not refit anything.** Every headline number is downstream of the fitted `spread_v2` model and
  CHARTER §3 rule 2 forbids regenerating a committed artifact.
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13–§14:
  investigated and deliberately stopped).
- **Do not compare accuracy with NIFoS or G-DAPS.** Their figures are agency statements with no published
  metric definition; the differentiator is the output object.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or
  `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).
- **Do not run WFG-125's first branch without writing the fill rule down first.** See row 2 above.

## Readiness lines ticked in the last 24 h: ZERO, for the fourth consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** (R1, R2, R4, R5, R6, R7, R8, R9) and has stood there
since critic #43 ticked R8 at 2026-09-08T1429Z. Critics #44, #45, #46 and #47 each ticked nothing. The
routine prompt calls zero across two consecutive laps a finding about the loop's direction; this is four.
**Part of the cause is now measured rather than guessed:** R11's row, WFG-024, was held `blocked` for five
days by WFG-022, whose own blocker NH-008 the author closed on 2026-09-04. R3 is blocked by NH-046 and R12
is the author's (NH-014). So of the three unticked lines, one was stuck on bookkeeping, one on an open
question, and one on the author.

## Critic's last direction note

**2026-09-09T0230Z, critic #47. ONE §3b reorder (WFG-202 down, below the P0 block); NO `fix-before-next-row`
item; three rows appended at the END of the table (WFG-203, WFG-204, WFG-205); four rows updated with
measurements (WFG-125, WFG-027, WFG-022, WFG-023, WFG-024); one new NEEDS_HUMAN entry (NH-049) and a
measurement appended to NH-032 and NH-034.**

Verified at `86f8929`. ⚠ **The clone opened SHALLOW at 50 commits**, which reads back only to
2026-09-08T08:28Z and would have hidden a third of my window. I deepened it with
`git fetch --shallow-since='2026-09-08T00:00:00Z'` to **66** commits, reaching back to 00:22Z — **a
deepening whose predicate is the window rather than a guessed number**, which is the control CHARTER §4's
paragraph warns is missing when a lap deepens by 120 or 250. `--is-shallow-repository` still answers `true`,
so **no ancestry or reachability claim appears anywhere in this lap's output.** `gates.py --mode full`
exits **0** (1806 passed, 63 skipped, 2 xfailed, pytest 348.2 s); `baseline-verify` WARNs on the two
`data/raw/**` contracts that are git-ignored and cannot exist in any sandbox, which is NH-029/§3d working.
GitHub `auto-gates` runs **256 to 267** carry one `failure`, run **260** at `7eeccab`, already closed by
`1fa0b7f` and reported; **267 is green at this exact head**, so there is no finding #1. Every dev report in
the window carries `Reviewed by:`, and `gates.py --assert-reported --base d36ad21` exits 0.

**The root objection: the loop has spent two dev laps writing about the bound and none measuring it, and
the measurement it keeps calling cheap is not.** The project's headline 42곳 is what a *perfect* forecast
buys — the README and Q36 both say so — and WFG-125 is the row that would replace the bound with a real
number. Three critic laps have called its input already committed. I measured the input: **18.3 % of the
grid.** Closing that gap needs a fill rule for the rest, and a fill rule picked after seeing the margin is
the same defect WFG-201 was filed about, on a bigger number. **Cheapest test, thirty seconds, already run:**
count the distinct `(row, col)` the out-of-fold file scores against `haz_stack.shape`. **The honest planning
assumption for 2026-10-24 is that the oracle gap will not be measured before the finals**, and the project
should keep saying so plainly, which today it does.

⚠ **This lap's own defect, recorded because the record is the point.** My first version of WFG-202's move
note contained a `grep` pattern with an escaped pipe in it, which split the row into 12 fields — **the
twelfth instance of the exact defect WFG-191 exists for, committed by the lap reading WFG-191**, which is
what critic #44 also did. I measured it, rewrote the pattern in words, and re-measured: **11** malformed
rows, all pre-existing, none mine. That the convention cannot hold this invariant is now evidence from two
consecutive critics.

⚠ **The one `Do NOT edit` note, RE-STATED after re-checking its premise (CHARTER §14c, NH-036 A).** It
covers **`README.md:220-247` only** — the Round-4 fair-opponent block. It forbids exactly one thing:
putting a present-perimeter **margin value** (9, 27, 5, 19, 86) into those lines while NH-032 and NH-034
are open. I re-read both rather than inheriting the note: both are still `open` and both are now one day
overdue, and this lap appended a measurement to each. **It expires at critic #48 unless that lap re-states
it after re-reading them.** It freezes no file and no question: those lines were edited this window to
name the statistic as a post-hoc maximum, and that is the kind of edit it permits.

⚠ **Candidate for the next critic lap, so it need not re-derive it:** **WFG-027** (일정) is the promotion
candidate ahead of WFG-197. 일정 및 팀원 역할 배분 is a named sub-item of 설계와 방법론, **20 points on
both tables**; a count of 일정 answers **0** on the finals screen, **0** on the bank and **1** on the
five-minute script, and that one hit is `DEMO_SCRIPT_5MIN.md:70`, 「일정 크기 아래의」, an adjective and
not a schedule. The 팀원 half is excluded for a solo entrant by the 심사기준's own 「개인의 경우 제외」;
the 일정 half is not, and the answer already exists in CHARTER §1 and §11. Both it and WFG-197 need a
**priority change**, not a §3b move.
