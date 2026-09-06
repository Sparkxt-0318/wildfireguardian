# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. Last checked by critic #23, 2026-09-06.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*The order changed this lap and the reason is that the row at the top was spent. WFG-121 shipped its (a) at
`a182cc0`, its (b) is `blocked(NH-032)`, and its (c) needs WFG-100's pace re-allocation, which is a different
row. A lap sent here would find nothing takeable.*

1. **WFG-007** (P0, the printables) — **eighth day, and it is now first on this page AND first in the table**,
   which is this lap's one row move. It alone holds readiness **R7** and half of **R9**; no readiness line has
   moved for eight critic laps; and no lap has claimed it in twenty-three critic windows. Its output is a file
   rather than an argument, and that has been the leading explanation for the stall since critic #22. **Nothing
   is in front of it now, so for the first time that explanation is actually testable.**
2. **WFG-127** (P0, filed this lap) — ⚠ **its prose half is this lap's one `fix-before-next-row` item: fifteen
   minutes, no run, no new number.** The booth script tells the student 「어느 폭이 맞는지는 그날 알 수 없고」,
   and the sweep behind it has five widths with the winner's neighbours a factor of two away on each side. Say
   what the grid is; stop asserting the shape it cannot resolve. Then take WFG-007. The run half (three more
   widths, routing only) is its own lap and can wait behind the printables.
3. **WFG-117 + WFG-113 + WFG-115** (all P0) — **one screen rebuild closes all three**, and none has been done
   for fourteen windows. `web/finals.html` prints `built at commit 41498ef`, which `merge-base --is-ancestor`
   refuses on a deepened clone, and `n_entries":326` where the registry now holds **383**. The judged screen is
   the most-looked-at artifact the project owns and two numbers on it are wrong today.

Then WFG-126 (raised P0 this lap; the manuscript still tells a reviewer the fair-opponent arm has not run),
WFG-124 (`blocked(NH-032)`), WFG-104 (`blocked(NH-032)` on its margin half), WFG-106, WFG-110, WFG-125,
WFG-122, WFG-121 (c) once WFG-100's re-allocation exists, WFG-036 v2, WFG-101, WFG-010 (README Round-4 +
abstract → R8), WFG-096, WFG-024 when its blockers clear (R11), and only then the infra rows, which
CHARTER §14b holds behind R1, R3, R7, R8 and R9.

## What not to do

- No new spread model, no retrain, no re-acquired region before 2026-10-16 (CHARTER §3). WFG-127's extra buffer
  widths are routing only on committed inputs and are not an exception to this.
- No fourth rewrite of the README's opening paragraph; disagreements go to NEEDS_HUMAN.
- No consultation-dependent claim (NH-010): nothing may wait on an expert reply.
- No ratio between the chain and the season areas (NH-018).
- Do not spend a lap on the six-fire study-area map until per-fire burned areas are registered (WFG-060).
- Do not commit the bundle payload. R9 does not require it and critic #16 said so on the line itself.
- Do not open another gate-about-the-loop row while the printables do not exist (CHARTER §14b).
- **Do not put any fair-opponent margin (9, 27, 5, 19) on a judge-facing surface** until NH-032 is answered.
  The do-not-say list in `JUDGE_QA.md` Q19 is the one deliberate exception and it is not an assertion; the gate
  `test_no_contested_margin_reaches_the_booth_script` documents that split. Settled by critic #23.
- **Do not release a claim younger than three hours** (CHARTER §5b, the author's NH-030 option C), and
  check `git log --all --grep=<row>` and `auto/red/*` before releasing an older one.
- **Do not run `make baseline-freeze` in a sandbox.** The author ran it on the laptop at `38620f2` and it was
  correct there; here it would record the two raw contracts as MISSING and destroy the protection.
- **Do not use `curl` for the GitHub Actions API in a cloud lap.** It returns 403 through the proxy. Read runs
  through the GitHub MCP (WFG-119). This sandbox also clones at **depth 50**, so deepen before any
  `merge-base --is-ancestor` claim.

## Critic's last direction note

**2026-09-06, critic #23. The window did good work, and the sharpest thing in it is a sentence the loop wrote
about its own evidence and then over-stated one step later.**

`docs/fair_opponent_line.md` is the best submission-material discipline this loop has produced: one home for one
contested line, a mutation-graded gate, and a §4 that checked the brief critic #22 handed it, found it wrong,
and said so in writing — 「this is the honest version, and it is less flattering than the one this file first
wrote」. My predecessor told that lap the buffer counts were 「the half no answer changes」. They are not, the lap
checked, and it corrected me. That is the loop working.

**And then the same document, and the booth script after it, drew a conclusion its own sweep cannot carry.** The
present-perimeter arm's one free variable is the buffer width. It was swept at **five** points — 250, 500,
**1000**, 2000, 3000 m — and the winner's nearest measured neighbours are a factor of two away on each side. So
「the safe total is a spike, not a plateau」 and 「nothing on the day tells you which width you are on」 are not
things this run can distinguish from a plateau spanning roughly 800 m to 1.5 km, which is a target an operator
**can** aim at. The second leg fails the same way: two coarse grids picking 1 km and 500 m is what a broad
optimum produces, not evidence of unknowability. It is on the booth script, in a sentence the student says out
loud, and a judge breaks it with one question. **WFG-127**, and the prose half is fifteen minutes.

**Readiness: 4 of 11 (R2, R4, R5, R6), unchanged, EIGHT laps.** And critic #22's falsifiable test did not run:
it asked whether a lap would voluntarily take a row whose output is a file, and this window's lap was **told**
to take WFG-121, which this page named first and which is the author's own row. A test of what a lap volunteers
for cannot run in a window where the lap was told what to take. **I am not reporting a verdict on it; I am
making it runnable.** WFG-007 is now first here and first in the table, so nothing stands in front of it.

**My one row move is WFG-007 to the front of the table.** Not to the front of this page — it was already going
to be named here — but to the front of the *table*, because critic #20's finding is that this page can go stale
for a lap and the table is the fallback when it does. WFG-121 sitting above it in the fallback order would have
sent a lap to a row with nothing takeable in it. P0 above P0, so §14's ordering rule is untouched.

**The falsifiable test for critic #24:** WFG-007 is now unambiguously first by both routes. If the next lap
ships a PDF under `docs/auto/finals/`, R7 moves and eight days of stall were queue position after all. If the
next lap ships anything else while WFG-007 is still `todo`, then position was never the constraint, the row
itself is, and #24 should stop moving it and instead **rewrite the row** — split it into one printable per lap,
or file NH asking the author whether the printables should exist at all — rather than write a ninth note about
the queue.

## Critic's previous direction note

**2026-09-05, critic #22. The row got built twice, and the second copy is the most valuable thing in the
window.** WFG-114 landed at `c8a3eee` with a margin of **9** of 368; a second lap built it independently,
could not rebase (15 conflicting files), and parked green on `auto/red/20260905T2248Z` with a margin of **27**,
and **5** at its sweep's best buffer. Neither is wrong; they built different opponents, both defensible, and
**the spread between them is wider than the effect either reports**. That is **WFG-124** and **NH-032**. The
direction finding underneath it: for six laps this page argued about the queue, and here the constraint was
that **two laps cannot see each other**, defeated by the release rule critic #21 wrote to un-stick the queue.
#22 moved no row and spent its reorder budget deliberately unspent. *(Full text:
`docs/auto/reports/2026-09-05T2330Z-critic.md`; #21's is in the 2015Z report, #20's in the 1716Z. This page
stays one screen, which is why the older notes live in the reports and not here.)*
