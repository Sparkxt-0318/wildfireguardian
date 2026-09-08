# CRITIC_LATEST — critic #46, 2026-09-08T2340Z

*The next dev lap reads this file before it claims a row (CHARTER §4 step 3). Reviewed head:
`cb9fcc3`. ⚠ **This clone is shallow:** `git rev-parse --is-shallow-repository` = **true**,
`git rev-list --count HEAD` = **55**, oldest resolvable commit `24f914f` at **03:21:30Z on 09-08**,
so this clone reads about **20.3 hours**, not 24. I claim nothing about anything older and **no
ancestry or reachability claim at all**. Full report:
`docs/auto/reports/2026-09-08T2343Z-critic.md` — the readings below were taken at **23:40Z** and
the report stamp is when `report.py` ran.*

## ⚠ First, this lap's own correction, because it is the loudest thing in the record

**I drafted this report against `7cfe29a` at 23:00Z and its headline finding was that the 21:17Z
dev lap had claimed WFG-199 and WFG-127 and died.** At that head the evidence was real: a pushed
claim at `97231a1`, no work commit, no report, 1 h 43 m elapsed. **The inference was wrong.** The
lap was slow, not dead. It pushed `9170a37` and its report at about 23:20Z while I was writing, and
it closed **both** rows. The draft was discarded before anything was pushed and this file is written
against the actual head.

**The lesson was already in this repository and I did not apply it.** NH-035 records that the
2026-09-05 lap 「looked dead for 1 h 45 m and was only slow」, which is the whole reason CHARTER §5b's
window is three hours and not two. I quoted that sentence in my own draft, as my reason for **not**
releasing the claim, and led with 「returned nothing」 anyway. **A critic lap may report what a head
shows; it may not convert an absence into a verdict about a lap that is still running.** The rule
for the next critic, and it costs one command: *before writing that a lap failed, `git fetch` again.*

## The one thing to read first: **the window closed both rows and the result runs against this project, which is the strongest kind of lap this loop produces**

`9170a37` re-ran the fair opponent's buffer sweep at the three widths the five-point grid was
missing (750, 1250, 1500 m), on committed inputs, no retrain, no re-acquisition, into a **new** file.
Safe totals across 250 m to 3 km: **275, 284, 349, 345, 318, 305, 275, 283**.

- The top is a **shoulder**, not a spike: 750 m scores **349** and 1 km **345**, four origins apart
  out of 368 on a grid whose own step is 250 m.
- All five shared widths reproduced **cell for cell**, bound by
  `tests/test_buffer_shape.py::test_the_five_shared_widths_reproduce_cell_for_cell`. That control is
  what makes three new points readable beside five old ones, and it is a test rather than a claim.
- The claim was withdrawn on four surfaces, registered as **WC-011**, and a **fifth** surface
  (`paper/GAPS.md` G8) was found by the registration sweep rather than by anyone's memory. That is
  CHARTER §3.5c working exactly as it was written to work.
- WFG-199 was cleared first: `make finals` re-stamped the screen onto `97231a1`, and
  `git rev-list --count 97231a1..HEAD` now answers **8** against a limit of 30. The countdown two
  critic laps recorded is gone.

## `fix-before-next-row` — **NONE this lap, and that is a finding rather than an omission**

Everything §14b names as eligible is green, re-run rather than read. `gates.py --mode full` exits
**0** (`1786 passed, 63 skipped, 2 xfailed`, pytest 346.6 s). `auto-gates` runs **246 to 263** carry
three `failure`s and all three are closed, with **262** and **263** green at the two newest heads.
`git ls-remote origin Main` answers **`cb9fcc3`**, so `Main` follows (CHARTER §4c). The printed kit
is `WFG_printables_20260908T2156Z.pdf` and **all six of its `SOURCES` re-hash to the tree in one
process**. The screen's stamp is 8 behind a limit of 30. There is no minutes-scale judge-facing
defect and no red gate, so setting an item would displace the top row for nothing.
**Take WFG-201, then WFG-194.**

---

## F1. The lap moved the premise of two overdue decisions and did not tell those decisions. I wrote the measurement into them myself.

`docs/present_perimeter_buffer_shape.md` §3(c), verbatim: 「750 m scores **higher** than the 1 km the
committed headline uses. The fair opponent is therefore **stronger** than the committed artifact
reports, and the forecast's margin over it on this fire is **smaller** than the committed margin:
**5** origins at 750 m against **9** at 1 km.」 The lap put that where it belongs, and correctly kept
the number off every judge-facing surface while NH-032 and NH-034 are open.

**What it did not do:** `git diff --stat 7cfe29a..HEAD -- docs/auto/NEEDS_HUMAN.md` is **empty**.
NH-032's decision table is computed **entirely at 1 km** (`present + 1 km` 345, `forecast-aware` 354,
`the margin` **9**) and its option A is offered to the author as 「margin 9, the more conservative
claim」. At the grid's own best measured width that row is now **5**, not 9. NH-034's title is
「cuts the headline from 91 to between 5 and 27」. Both entries were due **2026-09-08**, both are
open, and the author is being asked to choose between numbers this repository stopped believing
three hours ago. **NEEDS_HUMAN is a `docs/auto/` file and therefore the critic's to write, so no
dev-lap item is spent:** the measurement is appended to both entries with its consequence for each
option.

## F2. The root objection (`hate`): the headline margin is not a fixed quantity. It is a maximum over a grid, and it can only shrink as anyone looks harder.

The fair opponent's buffer width is chosen **after the fact, by scanning outcomes**. That is
conservative, it is honest, and it is the right design. But it makes the reported margin
「forecast minus the best post-hoc buffer width」, which is **non-increasing in how finely anyone
searches**: a new width can only tie or beat the incumbent, so the margin can only hold or fall.
**The first refinement this project ever ran removed four of the nine origins of margin**, 9 to 5, by
adding three points to a five-point grid.

`docs/present_perimeter_buffer_shape.md` §4 states the neighbouring caveat well (the grid is coarse,
it cannot locate the maximum, 349 and 345 are inside what a finer grid could reorder), and
`README.md:245-247` says plainly that the rerun went against the project and that the opponent is
stronger than the repository recorded. **What none of them states is the property**, and a
statistician judge lands it in five seconds: 「그 margin 은 계속 넓히는 격자 위의 최댓값입니다.
격자를 더 촘촘히 하면 얼마입니까?」 A number that fell by 44 % on its first refinement, with no
statement that refinement can only push it one way, is the most attackable object this project owns.

**Cheapest test, and the data for it is already committed:** report the margin at every measured
width beside the headline, and say in one sentence that refining the grid can only move it downward.
Eight widths exist; nobody needs to run anything. Filed as **WFG-201, P0 at position 1.**

## F3. Judge drill: the horizon has no card, and it is what this week's research called its own headline.

`grep -ciE 'Ready.?Set.?Go|화선|8시간'` answers **0** on `docs/auto/JUDGE_QA.md`, **0** on
`web/finals.html` and **0** on `docs/auto/DEMO_SCRIPT_5MIN.md`. The bank is **46** cards and **none
asks why the forecast horizon is 3 to 12 hours**; Q9 and Q10 answer the neighbouring question with
ERA5's lag and the satellite cadence, which the 18:17Z research lap itself called 「a technical
excuse」 to the disaster-response judge. The operational answer exists and is sourced: Korean
national doctrine decides the elderly evacuation at **8 h** and completes it at **5 h** before
fire-line arrival, and 3 to 12 h contains both
(`docs/auto/knowledge/KOREAN_OPERATIONAL_SYSTEMS.md`). One of the five judges is a public-sector
disaster-response official and the doctrine was announced 2026-02-12.

**WFG-197 keeps P1 this lap and I say why rather than promoting it.** Adding a second P0 row in one
lap, to a block this page is about to call unservable, is the behaviour it has criticised for three
days. It is **the next critic lap's promotion candidate**, ahead of WFG-027, and the measurement is
written onto the row so that lap need not re-derive it.

## F4. 창의성 is still at literal zero where five judges stand.

Re-measured at this head: `grep -cE '창의|독창'` is **0** on `web/finals.html`, **0** on
`docs/auto/DEMO_SCRIPT_5MIN.md` and **2** on the bank (Q29a). `grep -rn 'creativity_card' release/
scripts/` returns nothing, so `docs/creativity_card.md` is in no printed kit. 창의성 is **20 points
on both tables** and the 심사기준 names it first. **WFG-194**, position 2 after WFG-201.

## F5. The one code change nobody independently reviewed, and the backlog's order defect.

- **WFG-147.** `docs/auto/reports/2026-09-08T2231Z-manual.md` contains 「Reviewed」 **zero** times
  while its commit `1fa0b7f` changed **130 lines of `scripts/check_finals_acts.py` and 22 of
  `tests/test_finals_acts.py`**, the driver R1's tick rests on; `LOOP_CONFIG` sets
  `review: subagent`. Earlier laps excused reports missing the line because they carried no build.
  This one did. ⚠ **The change itself is right**, and I read it rather than trusting the message: it
  replaces `_free_port()`'s TOCTOU race with port 0 plus `DevToolsActivePort`, keeps Chromium's
  stderr, retries once, and narrows the skip from a **message substring** to an `isinstance` check on
  a `BrowserLaunchError` raised at exactly one site. Run **261**'s `finals-acts` job ran both steps
  to `success` on a clean runner. **WFG-196's residual risk is substantially discharged and R1 keeps
  its tick.**
- **WFG-191.** Counted here by parsing every table line whose first cell is a `WFG-` id: **63 non-P0
  `todo` rows sit above the last P0 `todo` row**, and the three rows the 18:17Z research lap filed sit
  near the top of the P1 block, above seven P0 `todo` rows.
  `docs/auto/research/WEEKLY_2026-W37.md` §7 states 「the two new rows enter at the end of the P1
  block, which reorders nothing」, which is **false as measured**. That is this lap's one `factchk`
  hit on new prose in the window's diff. The gate this row asks for must check **order**, not only
  **shape**.

## ⚠ The one `Do NOT edit` note, RE-STATED after re-checking (CHARTER §14c, NH-036 A)

**It covers `README.md:220-247` only** (the Round-4 fair-opponent block, which grew this window by
the dated withdrawal note and the 「이 재실행은 이 프로젝트에 불리한 쪽으로 끝났습니다」 bullet).
**It forbids exactly one thing: putting a present-perimeter margin value (9, 27, 5, 19, 86) into
those lines while NH-032 and NH-034 are open.** I re-read the premise rather than inheriting it:
both entries are still `open` and both were due today. **It expires at critic #47 unless that lap
re-states it after re-reading them.**

**It freezes no file and no question.** WFG-201 must edit those very lines to name the statistic as a
post-hoc maximum, and that edit is a sentence about *how the number is chosen*, not a margin value.
`README.md:232` is no longer a defect: the shape claim is withdrawn there with a dated note.
