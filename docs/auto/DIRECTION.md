# Direction — where the project is going, on one screen

*Rewritten 2026-09-08T1817Z by the research routine; updated 2026-09-09T0526Z by critic #48 (CHARTER §14).
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

Table order at `5f4e32b` after critic #48. **This lap spent its ONE §3b reorder promoting WFG-027 to P0 and
moving it above WFG-125, which is the move critics #45 and #47 both pre-registered and neither could make.**
It added no row above the P0 block and set one `fix-before-next-row` item, minutes, on the release bundle.

1. **WFG-194 (P0, KCF)** — `in-progress(20260909T0321Z)`, claimed 97 minutes before this lap read the tree and
   under CHARTER §5b's three hours, so it is another lap's and this lap did not touch its status. 창의성 is
   **20 points on both rubric tables** and the 심사기준 names it first. Re-measured at this head on the raw
   count of 창의 or 독창: **0** on `web/finals.html`, **0** on `docs/auto/DEMO_SCRIPT_5MIN.md`, **3** on
   `docs/auto/JUDGE_QA.md`, **12** on `docs/creativity_card.md` and ⚠ **0 on `README.md`**, which the row does
   not name and which is the page a judge browses first. The card is in none of the printed kit's six
   `SOURCES` and not among the 19 files of the bundle. **Add README.md to the row's surfaces before closing it.**
2. **WFG-027 (P0, KCF) — PROMOTED AND MOVED HERE THIS LAP, and it is the first todo row once WFG-194 closes.**
   일정 및 팀원 역할 배분 is a named sub-item of 설계와 방법론, **20 points on both tables**, and for a solo
   entrant the 심사기준's own 「개인의 경우 제외」 excludes the 팀원 half and not the 일정 half. Re-measured
   at this head: a count of 일정 answers **0** on `README.md`, **0** on `web/finals.html`, **0** on
   `docs/auto/JUDGE_QA.md`, **1** on `docs/auto/DEMO_SCRIPT_5MIN.md`, and that hit is line 70, 「일정 크기
   아래의」, the adjective. 로드맵 and 개발과정 are zero on all four; 타임라인 occurs once, at
   `web/finals.html:463`, and it is a UI hint for the fire-time slider; 계획
   occurs eleven times across the three text surfaces and **not one is a development schedule** (route
   planning, the opponent's planner, an agency's announced plan, a plan not held, 연구 계획서). So a sub-item of a
   20-point row is at **literal zero on every surface a judge meets**, and the answer already exists in
   CHARTER §1 and §11 plus `git log`. That is a larger scoring hole than row 3 for less work.
3. **WFG-125 (P0, science)** — unchanged in place and unchanged in reasoning; critic #47's measurement stands
   and this lap did not re-derive it. The out-of-fold file covers **18.3 %** of 영덕's 26,607-cell grid, so
   the expensive branch needs a fill rule for the other ~82 % and a fill rule chosen after seeing the margin
   is a second post-hoc maximum. **The second branch, record the absence with the paths checked, is the one
   that fits a lap.** ⚠ It was demoted below WFG-027 for one reason only: the README already tells a judge in
   its own words that 42곳 is a ceiling and that nobody has measured how far below it the truth sits, so this
   row's cheap branch adds honesty the front door already has, while WFG-027 adds points nothing has.

Behind those, the P0 block: WFG-007, WFG-117, WFG-128, WFG-129, WFG-121, WFG-106, WFG-036, WFG-101,
WFG-119, WFG-054, WFG-024. **Thirteen P0 rows `todo`, six sprint days.** The ratio did not improve.

## What not to do

- **Do not start a P1 row while a P0 row is `todo`**, and do not file one above the P0 block. This lap's two
  new rows (WFG-208, WFG-209) were appended at the **end** of the table for exactly that reason.
- **Do not refit anything.** Every headline number is downstream of the fitted `spread_v2` model and
  CHARTER §3 rule 2 forbids regenerating a committed artifact.
- **Do not add the seven missing documents to the release bundle** when clearing WFG-208. The fix is one
  sentence and a URL in `README_KO.md`; adding payload widens the freeze.
- **Do not re-propose international portability or real-time weather** (`docs/HANDOFF_ROUND3.md` §13–§14).
- **Do not compare accuracy with NIFoS or G-DAPS.** Their figures are agency statements with no published
  metric definition; the differentiator is the output object.
- **Do not let a number from a knowledge note reach a card, the README, the manuscript or
  `docs/NUMBERS.json`** (CHARTER §13, §3 rule 5b).

## Readiness lines ticked in the last 24 h: ZERO, for the fifth consecutive critic lap

`docs/auto/KCF_READINESS.md` stands at **8 of 11** and has stood there since critic #43 ticked R8 at
2026-09-08T1429Z. **This window is an honest zero rather than a direction failure:** `86f8929..5f4e32b`
contains one paper lap and three report-header repairs, and the one dev lap in it is a bare claim whose work
had not landed when this lap read the tree. No readiness line has a surface in this window to tick against.

## Critic's last direction note

**2026-09-09T0526Z, critic #48. ONE §3b reorder (WFG-027 promoted to P0 and moved above WFG-125); ONE
`fix-before-next-row` item (WFG-208, minutes, release bundle); two rows appended at the END of the table
(WFG-208, WFG-209); one measurement appended to WFG-194; one new NEEDS_HUMAN entry (NH-050).**

Verified at `5f4e32b`. ⚠ **The clone opened SHALLOW at 50 commits**, reading back only to 2026-09-08T10:20Z.
Deepened with `git fetch --shallow-since='2026-09-08T00:00:00Z'` to **73** commits, oldest resolvable
`088203c` at **00:29:26Z on 09-08**, a predicate that is the window and not a guessed depth.
`--is-shallow-repository` still answers `true`, so **no ancestry or reachability claim appears in this lap's
output.** `gates.py --mode full` exits **0** (1806 passed, 63 skipped, 2 xfailed, pytest 273.2 s);
`baseline-verify` WARNs on the two git-ignored `data/raw/**` contracts, which is NH-029/§3d working.
**GitHub `auto-gates` runs 263 to 273 are all `success`**, including run **273** at this exact head, so there
is no finding #1. All three dev reports in the window carry `Reviewed by:`, and
`gates.py --assert-reported --base 86f8929` exits 0. `make finals-bundle` rebuilds byte-identically, 19 files.

**The root objection: the loop is asking the author for decisions the author has already made, and the rule
this routine actually obeys is not written in the charter it cites.** The stored critic prompt binds this lap
to 「§14b ... as amended 2026-09-07 by NH-038 B」 and to 「CHARTER §14c ... NH-036 A」. A search for `14c` in
`docs/auto/CHARTER.md` answers **0**, §14b there is the unamended 2026-09-04 text, both NH entries are `open`,
`decisions_seen.json` stops at NH-031, and this morning's report email asked for both again inside a list of
fifteen. **Cheapest test, ten seconds, already run:** grep the charter for its own section number. That is
**NH-050** and **WFG-209**, and it is filed as a question rather than a closure because the routine page is
not one of CHARTER §6's three declared channels and registering a decision the author did not make is worse
than asking once more.

⚠ **The one `Do NOT edit` note, RE-STATED after re-checking its premise (CHARTER §14c, NH-036 A), with its
line range CORRECTED.** Critic #47 wrote it over `README.md:220-247`. Measured here, the Round-4 fair-opponent
block runs **`README.md:210-282`** (「### 1.」 at 210 to 「### 2.」 at 283), so the inherited range covered
about a third of what the note is about, and the drift is what a line-numbered note does the moment the file
is edited. The note forbids exactly one thing over **`README.md:210-282`**: putting a present-perimeter
**margin value** (9, 27, 5, 19, 86) into those lines while NH-032 and NH-034 are open. I re-read both rather
than inheriting: `NEEDS_HUMAN.md:1391` and `:1574` both still say `open`, both are now two days overdue, and
a scan of 210-282 finds no margin value there today. **It expires at critic #49 unless that lap re-states it
after re-reading them.** It freezes no file and no question: those lines were rewritten twice this week and
that is the kind of edit it permits.

⚠ **Candidate for the next critic lap, so it need not re-derive it:** **WFG-197** (the 8-hour 화선 도달
lead time at which 고령자 preemptive evacuation begins) is the remaining promotion candidate, and it is the
same shape as WFG-027 was: a judge-facing answer that exists in a research note and on no surface. It needs a
**priority change plus a move**, which is one §3b act.
