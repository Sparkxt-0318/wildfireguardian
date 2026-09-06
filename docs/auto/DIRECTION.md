# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. Last checked by critic #24, 2026-09-06T0457Z.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*No row moved this lap and the reorder budget is deliberately unspent (critic #22's precedent). The order
below is the table's own; the only change is that the top row is now claimed rather than waiting.*

1. **WFG-007** (P0, the printables) — **claimed at `7233743`, `in-progress(20260906T0320Z)`, three minutes
   after the 03:17Z lap woke.** That is critic #23's falsifiable test actually running: the row was first in
   the table and first on this page, and the lap took it rather than something else, so *queue position was
   at least part of the constraint*. Whether it ships a PDF is critic #25's to report, not mine — the claim
   was still in flight when this lap ran. ⚠ If that lap died, the row is **not** releasable at 06:17Z:
   a claim stamped 03:20 is 2 h 57 m old at the next dev wake and CHARTER §5b's bar is three hours. That is
   **NH-035**, filed this lap.
2. **WFG-127 (i)** — ⚠ **carried forward unchanged as this lap's one `fix-before-next-row` item, because
   critic #23 set it and it was not cleared.** Both surfaces still assert it today, checked at `91d3e05`:
   `docs/fair_opponent_line.md` §3 「spike, not a plateau」 and `DEMO_SCRIPT_5MIN.md` 3막
   「어느 폭이 맞는지는 그날 알 수 없고」. Fifteen minutes, prose only, no run, no new number. The manuscript
   fixed its half of exactly this in the same window (§4.5 asserts neither spike nor plateau), so the
   correction is already written and only needs porting to the two booth-side documents.
3. **The judged screen, three wrong numbers, two commands** — `web/finals.html` prints `n_entries` **326**
   and `n_reproducible` **268** where `docs/NUMBERS.json` holds **383** and **325**, and 「built at commit
   41498ef」 which is not an ancestor of `HEAD` on a 250-commit clone. `make finals` re-derives the first two
   from the registry; WFG-109's closure records this loop already running it, changing only the payload line,
   then `make finals-bundle UPDATE=1`. **WFG-113**, **WFG-115**, **WFG-117**, none done for fifteen windows.

Then **WFG-128** (P0, filed this lap: `docs/multi_region.md:191` states the one bucket that runs against the
project in a form this project's own measurement contradicts, and the README links that page as
「완전한 분할」), **WFG-129** (P0, filed this lap: the cheapest test of the 42 of 458, fully specified in
`paper/GAPS.md` G7 and in no file a dev lap reads), WFG-124 (`blocked(NH-032)`), WFG-104
(`blocked(NH-032)` on its margin half), WFG-106, WFG-110, WFG-125, WFG-122, WFG-121 (c) once WFG-100's
re-allocation exists, WFG-036 v2, WFG-101, WFG-010 (README Round-4 + abstract → R8), WFG-096, WFG-024 when
its blockers clear (R11), and only then the infra rows, which CHARTER §14b holds behind R1, R3, R7, R8 and R9.
**WFG-126 is `done(91d3e05)`** — the paper lap closed it inside the window that filed it.

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
  check `git log --all --grep=<row>` and `auto/red/*` before releasing an older one. ⚠ Critic #24 measured
  that this bar can never be met at the next dev wake (claims land 3 m after a 3 h grid, so they read
  2 h 57 m): **NH-035**, open. Until the author answers, the rule stands as written — do not reinterpret it.
- **Do not run `make baseline-freeze` in a sandbox.** The author ran it on the laptop at `38620f2` and it was
  correct there; here it would record the two raw contracts as MISSING and destroy the protection.
- **Do not use `curl` for the GitHub Actions API in a cloud lap.** It returns 403 through the proxy. Read runs
  through the GitHub MCP (WFG-119). This sandbox also clones at **depth 50**, so deepen before any
  `merge-base --is-ancestor` claim.

## Critic's last direction note

**2026-09-06T0457Z, critic #24. The window is one substantive commit and it is the best manuscript lap this
loop has run; the finding is not in it, it is in what the window did not touch.**

Verified here rather than read from the reports: `gates.py --mode full` **ALL GREEN** at `91d3e05`
(`1545 passed, 62 skipped`, cold, 179.9 s), all fifteen `auto-gates` runs on `auto/dev` in the window are
`success` (two `cancelled`, both superseded pushes) — **so there is no gate finding and no CHARTER §4b
finding this lap** — every dev report of the last 24 h carries `Reviewed by:`, and no author reply is waiting
in the mailbox (`decisions_seen.json` unchanged; the 2026-09-06 decisions came through the laptop session at
`4d705df` and are already applied).

**The root objection, and it is the oldest one in this project rather than a new one.** The number the student
says out loud and the judged screen prints is **42 of 458 on 영덕**, and it has never met a fair opponent. On
the one region where the fair opponent was built, most of that region's contrast did not survive it — the
manuscript said so in its own abstract this window, which is the loop at its best. **The cheapest test of the
42 exists, is fully specified, is runnable in this sandbox in minutes, and lives in the one file no dev lap
reads:** `paper/GAPS.md` G7 — mask slice 0 of the committed canonical field as a node filter, re-run
`naive_route` over only the 44 origins whose fire-blind route enters the hazard, count how many a
present-perimeter-only router already saves. Zero buffer, one region, every input committed. CHARTER §4 step 1
does not list `paper/GAPS.md` and CHARTER §12 forbids the paper routine from writing outside `paper/`, so the
instruction sat where neither routine could act on it. That is **WFG-129**, P0, filed this lap.

**The second finding is the same shape one document over.** `docs/multi_region.md:191` states
`fa_exceeds_budget` — the only bucket in the series that runs against this project — as 「fire-blind route
safe, future-aware router cannot finish in time」, 2 for 의성·안동. `docs/present_perimeter_arm.md:46-63`
measured those two origins' fire-blind arrivals at **624.8** and **628.2** minutes and concluded that under one
budget rule the bucket is **empty**. The manuscript took that qualification into §4.4 this window; its twin did
not, and `README.md:113` sends a judge to the twin for 「완전한 분할」. The author already chose the fix
(NH-031 option A, 2026-09-06). **WFG-128**, minutes, no committed value moves, no margin.

**My one `fix-before-next-row` item is critic #23's, carried forward unchanged: WFG-127 (i).** Both surfaces
still assert it at `91d3e05`. I am not spending the budget on my own findings, because an item that survives a
lap unspent is the only way to learn whether the item or the mechanism is at fault, and substituting a fresh
one would lose that and the finding with it.

**Readiness: 4 of 11 (R2, R4, R5, R6), unchanged, NINE laps** — and by the routine's own rule, zero ticks
across two consecutive critic laps is a finding about direction rather than about the product. Here is what it
actually is, and it is not the queue any more: **WFG-007 was claimed three minutes after the 03:17Z lap woke,
the first time it was unambiguously first by both routes.** Critic #23's test is running. What the window
exposes instead is the *release* rule — a claim that goes quiet is not recoverable at the next dev wake,
because 3 h is exactly the grid (**NH-035**). Nine days of R7 has been queue position and, twice now, a lock
with no key.

**The falsifiable test for critic #25.** Two things, and they separate cleanly. (1) If `docs/auto/finals/`
holds a PDF, R7 moves and WFG-007 is finished — say so and stop writing about the queue. (2) If it does not
**and** WFG-007 still reads `in-progress(20260906T0320Z)`, then the row was never the constraint and the lock
was: do not move the row, do not rewrite it — release it, and treat NH-035 as urgent rather than medium.

## Critic's previous direction note

**2026-09-06, critic #23.** The loop's honesty discipline outran its evidence discipline by one sentence:
`docs/fair_opponent_line.md` §3 and `DEMO_SCRIPT_5MIN.md` 3막 assert 「spike, not a plateau」 and
「어느 폭이 맞는지는 그날 알 수 없고」 off a five-point sweep (250 / 500 / **1000** / 2000 / 3000 m) whose winner's
nearest neighbours are a factor of two away, so the run cannot separate a spike at 1 km from a plateau an
operator could aim at. #23's one row move was WFG-007 to the front of the *table*, so the table and this page
would agree if the page went stale. *(Full text: `docs/auto/reports/2026-09-06T0215Z-critic.md`; #22's is in the
2026-09-05T2330Z report, #21's in the 2015Z, #20's in the 1716Z. This page stays one screen, which is why the
older notes live in the reports and not here.)*
