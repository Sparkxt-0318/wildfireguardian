# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. Last checked by critic #26, 2026-09-06T1100Z.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*One row moved this lap and it is **WFG-117**, from deep in the table to position 2. The reason is that its
defect inverted inside one window: the repair landed and the warning about it did not, so the Q&A bank now
tells the student a false thing about a screen that is right. Critic #25's two branches are both answered
below.*

1. **WFG-117 (P0, minutes) — the Q&A bank is wrong about the screen, and it is a T0 question.**
   `web/finals.html` prints `n_entries` **383** / `n_reproducible` **325**, which is exactly what
   `docs/NUMBERS.json` holds (counted here in one process: 383 / 325 / 58 not). `docs/auto/JUDGE_QA.md`
   Q30's ⚠⚠ block still says the screen prints 「**326 · 268**」, that pointing at it 「학생을 낡은 숫자로
   데려갑니다」, and that 「서로 다른 수가 셋 있습니다」. All three are false at this head. A student
   rehearsing today is drilled to distrust the one surface that is now correct, on the question about why
   today's numbers should be believed. **This is critic #26's one `fix-before-next-row` item.** A dated
   correction note is already on Q30 so nobody rehearses the stale block; the row makes the answer true and
   puts a gate behind it.
2. **WFG-130** (P0, minutes, carried from critic #25) — the booth PDF omits the reconciliation sheet and its
   manifest declares that committed file 「does not exist yet」. R7 names five printables and the build's
   source list overlaps it in **one**. This is the difference between R7 ticking this week and not.
3. **WFG-128** (P0, minutes, carried from critics #24 and #25) — `docs/multi_region.md:191` still states the
   one bucket that runs against this project in a form this project's own measurement contradicts, and
   `README.md:113` still sends a judge there. The author closed NH-031 option A on 2026-09-06; no committed
   value moves and no margin is spoken.

Then **WFG-129** (P0, one lap: the cheapest test of the headline 42 of 458, fully specified in
`paper/GAPS.md` G7), WFG-007's human half (the student prints it once), WFG-110 (which is now the **only**
thing holding R1 — see below), WFG-124 (`blocked(NH-032)`), WFG-104 (`blocked(NH-032)` on its margin half),
WFG-106, WFG-127, WFG-125, WFG-122, WFG-121 (c), WFG-036 v2, WFG-101, WFG-010 (README Round-4 + abstract →
R8), WFG-096, WFG-026 (the other half of R7), WFG-024 when its blockers clear (R11), and only then the infra
rows — **WFG-119**, **WFG-131** and the new **WFG-132** among them — which CHARTER §14b holds behind R1, R3,
R7, R8 and R9.

⚠⚠ **WFG-115 is off this page and off P0. Its premise is false.** `41498ef` **is** an ancestor of `HEAD`,
277 commits back, verified here on a clone deepened to 300. Five critic laps said otherwise because five
critic laps measured inside a shorter graph. Do not act on the old premise; do not edit the screen's
provenance line to "fix" reachability; do not edit `JUDGE_QA.md` Q35, which is correct. The row survives at
P1, re-scoped to the real and much smaller defect: the line is stale by construction and mislabelled.

## What not to do

- No new spread model, no retrain, no re-acquired region before 2026-10-16 (CHARTER §3). WFG-127's extra
  buffer widths are routing only on committed inputs and are not an exception to this.
- No fourth rewrite of the README's opening paragraph; disagreements go to NEEDS_HUMAN.
- No consultation-dependent claim (NH-010): nothing may wait on an expert reply.
- No ratio between the chain and the season areas (NH-018).
- Do not spend a lap on the six-fire study-area map until per-fire burned areas are registered (WFG-060).
- Do not commit the bundle payload. R9 does not require it and critic #16 said so on the line itself.
- Do not open another gate-about-the-loop row while a judge-facing surface is wrong (CHARTER §14b).
- **Do not put any fair-opponent margin (9, 27, 5, 19) on a judge-facing surface** until NH-032 is answered.
  The do-not-say list in `JUDGE_QA.md` Q19 is the one deliberate exception and it is not an assertion; the
  gate `test_no_contested_margin_reaches_the_booth_script` documents that split. Settled by critic #23.
- **Do not overwrite `WFG_printables_20260906T0620Z.pdf` or its manifest.** CHARTER §3.2: a corrected build
  gets a new stamp and sits beside it.
- **Do not release a claim younger than three hours** (CHARTER §5b, the author's NH-030 option C). ⚠ Both
  releases this rule has ever performed landed within 90 seconds of the bar, one on each side of it
  (**NH-035**, open, MEDIUM). Until the author answers, the rule stands as written — do not reinterpret it.
- **Do not run `make baseline-freeze` in a sandbox.** The author ran it on the laptop at `38620f2` and it
  was correct there; here it would record the two raw contracts as MISSING and destroy the protection.
- **Do not use `curl` for the GitHub Actions API in a cloud lap.** It returns 403 through the proxy. Read
  runs through the GitHub MCP (WFG-119).
- ⚠⚠ **Do not write a reachability or ancestry claim until `git rev-parse --is-shallow-repository` answers
  `false`, and record the depth beside the claim.** Deepening by a number you chose is not a control: this
  sandbox clones at **depth 50**, critic #21 deepened by 120, critic #24 to 250, and the object in dispute
  sat at **277**. Five laps published the same false finding that way (WFG-115's withdrawal, WFG-119).

## Critic's last direction note

**2026-09-06T1100Z, critic #26. The window did what it was told, and the finding is in the instrument that
has been grading it.**

Verified here rather than read from the reports: `gates.py --mode full` **ALL GREEN** at `b2bdaf0`
(`1565 passed, 62 skipped`, cold, 199.1 s; **+3 passed** on critic #25), the 25 most recent `auto-gates`
runs on `auto/dev` (numbers 140 to 168) are **22 `success` and 3 `cancelled`** with **no `failure`** — so
there is no gate finding and no CHARTER §4b finding this lap — `--assert-reported` exits 0 across the
window, every dev and paper report of the last 24 h carries `Reviewed by:`, and no author reply is waiting
(the Gmail search returns only threads this loop sent, each holding one message with no reply;
`decisions_seen.json` unchanged).

**Critic #25's falsifiable test, branch (1), answered.** `web/finals.html` prints **383 / 325** against the
registry's 383 / 325. The two-command repair ran (WFG-113, `1ec1d06`), the screen's stamp moved to
`62b58e1`, **6** commits behind `HEAD` rather than 29, and WFG-119's ten-hour clock is reset. The item
mechanism worked; branch (2) does not fire.

**The root objection is about how this loop knows things, and it costs five laps of the record.**
`41498ef` — the commit five critic laps have called unreachable from this branch — **is an ancestor of
`HEAD`, 277 commits back.** Verified three independent ways on a clone deepened to 300: `merge-base
--is-ancestor` exits 0, `rev-list HEAD` contains the full sha, `branch -a --contains` names `auto/dev` and
`origin/Main`. Critic #20 raised it at the sandbox's default **depth 50**; critic #21 found the shallow
clone, deepened by **120**, and re-confirmed; critic #24 deepened to **250** and wrote 「so the shallow
boundary is not the confounder」. It still was. Every one of those laps wrote 「re-run rather than read」 —
this loop's central honesty claim — and every one of them re-ran the same command inside the same short
instrument. **「Re-run rather than read」 defends against a stale reading. It does nothing against a
systematically wrong instrument, and deepening by a number you picked is not a control.** The finding
reached `KCF_READINESS.md` R1, this page, `SCORECARD.md` (where critic #20 docked Track A a point for it,
now withdrawn) and `docs/finals_screen_v2.md` §4.3, the screen's own explainer. The cheapest test is one
line and is now a rule above: no ancestry claim until `is-shallow-repository` answers `false`, with the
depth recorded beside it.

**My one `fix-before-next-row` item is WFG-117, and it is the mirror image of the same problem on a
judge-facing surface.** WFG-113's repair landed and the warning about it did not: `JUDGE_QA.md` Q30, a
**T0** question, still tells the student the screen prints 326 · 268, that pointing at it leads them to a
stale number, and that three counts are in play. All three are false. A wrong warning survives a correct
repair, and this one drills the student to distrust the one surface that is now right.

**The falsifiable test for critic #27.** (1) Re-run the three ancestry commands on an **unshallowed** clone
and confirm 277; if any of them disagrees, my withdrawal is wrong and WFG-115 goes back to P0 with the
measurement. (2) If Q30's ⚠⚠ block still says 326 · 268 at the next critic head, then a `fix-before-next-row`
item on a Q&A-bank sentence is not enough to move a Q&A-bank sentence, and the item mechanism — which
worked this window on a two-command repair — does not carry prose; say so and escalate the mechanism rather
than the row.

## Critic's previous direction note

**2026-09-06T0800Z, critic #25.** The window shipped the booth printables — the object nine days of this
page had argued about — and the finding was that the kit was measured against its own sources rather than
against R7's five named ones, which is **WFG-130**, still open. Its one `fix-before-next-row` item was
WFG-113's two-command repair on the judged screen; critic #26 confirms it ran.
*(Full text: `docs/auto/reports/2026-09-06T0816Z-critic.md`; #24's is in the 2026-09-06T0516Z report, #23's
in the 0215Z, #22's in the 2026-09-05T2330Z. This page stays one screen, which is why the older notes live
in the reports and not here.)*
