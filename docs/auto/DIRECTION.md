# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. Last checked by critic #14, 2026-09-04.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*Author's steer, 2026-09-04 evening: the product first. The readiness checklist has 3 of 11 lines
ticked and no line has moved for five critic laps. **WFG-062 is done as of `e350571`, so NH-021 is
satisfied and nothing stands between the loop and the booth rows.** From here the next rows are the
ones a judge sees.*

1. **WFG-003** (P0) — finals screen audit and the 5-minute demo script, due 09-07 on the sprint plan; ticks R4 and half of R1. It is the next `todo` row in table order and needed no reorder to get there.
2. **WFG-036** then **WFG-037** (P0) — the release bundle v1 (R9) and the booth recipe (R3, R12), due 09-10.
3. **WFG-007** (P1) — booth checklist and printables (R7), the last unwritten judge-facing artifact.

Then in order: WFG-010 (README Round-4 + abstract → R8), WFG-024 when its blockers clear (R11), WFG-076 and the other infra rows only after the readiness lines above are ticked. **No further claim-gate row this sprint** unless a judge-facing surface is wrong: WFG-062 measured its own limit and published it, and critic #14 measured it independently at 1/20 on rewordings, which is what the document already said.

## What not to do

- No new spread model, no retrain, no re-acquired region before 2026-10-16 (CHARTER §3).
- No fourth rewrite of the README's opening paragraph; disagreements go to NEEDS_HUMAN.
- No consultation-dependent claim (NH-010): nothing may wait on an expert reply.
- No ratio between the chain and the season areas (NH-018).
- Do not spend a lap on the six-fire study-area map until per-fire burned areas are registered (WFG-060).
- Do not open another gate-about-the-loop row while `DEMO_SCRIPT_5MIN.md`, `BOOTH_SETUP.md` and `release/kcf-finals-2026/` do not exist (CHARTER §14b).

## Critic's last direction note

**2026-09-04, critic #14. The next `todo` row is WFG-003, no BACKLOG row was moved, and for the first time in three critic laps that is not a deferral — it is where the table already points.** WFG-062 closed at `e350571`, so option A of **NH-024** is spent, option C is what the table does on its own, and the escalation that critic #12 opened and critic #13 declined to answer is **resolved by events**; I annotated it so and left the author a one-line exit rather than a decision. What I add is the clock rather than another ratio. Judge-facing lines this 24 h window: **1,018 of 20,812 authored (4.9 %)**, against `docs/auto/reports/` at **8,052 in 45 files (38.7 %)** — better than critic #13's 2.6 %, still eight to one, and most of the improvement is the manuscript's §6 admission rather than anything at the booth. **Three of eleven readiness lines ticked; the last tick was R2 by critic #8 at `12bf2d9`, 0750Z, fifteen hours and five critic laps ago; `web/` has not been committed to for twelve windows.** My one `fix-before-next-row` item (WFG-087) is fifteen minutes on a T0 Q&A answer that teaches a blocker this repository removed the same day, and it is deliberately cheap so that the rest of the next lap is WFG-003. **The falsifiable test:** if the next dev lap produces `docs/auto/DEMO_SCRIPT_5MIN.md` and a `web/` commit, this page is steering; if it produces another gate, it is not, and critic #15 should say that to the author instead of filing a fifteenth row about it.

## Critic's previous direction note

**2026-09-04, critic #13. The next `todo` row is unchanged, no BACKLOG row was moved, and the reason is that the question is already with the author.** I did move WFG-003 above WFG-062 under CHARTER §14b, then put it back on finding **NH-024** open: the 1851Z dev lap had already escalated exactly this, with 「hand the booth rows their place back」 spelled out as option C. Critic #12's re-scope test has resolved (two laps passed, WFG-062 still `todo`), so the answer is due, but it is the author's and not a critic's — reordering under an open escalation of my own loop's making would be theatre. What I add instead is a measurement: over the 24 h to `baf6962`, 108 commits and 25,122 authored lines, of which **9,000 in 49 report files** and **3,386 in the steering documents** (49.3 % together) against **663 lines, 2.6 %**, on every surface a judge will ever see. Nineteen to one. Filed **WFG-084** as the structural half of that, P1 under §14b, and set **no `fix-before-next-row` item**.
