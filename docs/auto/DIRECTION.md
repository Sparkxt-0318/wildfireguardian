# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. Last checked by critic #25, 2026-09-06T0800Z.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*No row moved this lap and the reorder budget is deliberately unspent for the third critic lap running.
The reason is not caution: **the top two entries on this page were both cleared in the window I reviewed**,
so the page's order was right and the queue below it has not been tested yet. The order below is the
table's own.*

1. **The judged screen, and it is now on a ten-hour clock.** `web/finals.html:434` prints `n_entries`
   **326** and `n_reproducible` **268**; `docs/NUMBERS.json` holds **383** and **325**, counted in one
   process at `b70e464`. Sixteen windows. `make finals` re-derives both from the registry
   (`scripts/build_finals.py:629-630`) and needs no decision; `make finals-bundle UPDATE=1` carries it into
   the 17-file release bundle, which ships this screen. ⚠ New today: the screen's stamp `5f9a3b8` is **29**
   commits behind `HEAD`, the branch takes ~**51** commits a day, and the sandbox clones at depth **50** —
   so WFG-119's predicted red arrives in roughly **ten hours**, after which a lap that hits it spends
   itself parking under CHARTER §9 on a screen that is not wrong. **This is critic #25's one
   `fix-before-next-row` item.** Rows: **WFG-113**, then **WFG-115** (`41498ef`, still not an ancestor on a
   deepened 250-commit clone; `make finals` does **not** touch it), then **WFG-117**.
2. **WFG-130** (P0, new, minutes) — the booth PDF exists and omits the one paper `JUDGE_QA.md` Q30 tells
   the student to open in front of a judge. `docs/submission_reconciliation.md` is `done(20260903T0653Z)`,
   is the file R6's tick is written on, says of itself 「인쇄본은 양면 한 장입니다」, and the build's manifest
   says it 「does not exist yet」. R7 names five printables and `scripts/build_printables.py:97-101` lists
   four sources that overlap it in **one**. This is the difference between R7 ticking this week and not.
3. **WFG-128** (P0, minutes, carried from critic #24) — `docs/multi_region.md:191` still states the one
   bucket that runs against this project in a form this project's own measurement contradicts, and
   `README.md:113` still sends a judge there for 「완전한 분할」. The author closed NH-031 option A on
   2026-09-06; no committed value moves and no margin is spoken. Checked unfixed at `b70e464`.

Then **WFG-129** (P0, one lap: the cheapest test of the headline 42 of 458, fully specified in
`paper/GAPS.md` G7 and still in no file a dev lap reads), WFG-007's human half (the student prints it once),
WFG-124 (`blocked(NH-032)`), WFG-104 (`blocked(NH-032)` on its margin half), WFG-106, WFG-110, WFG-125,
WFG-122, WFG-121 (c) once WFG-100's re-allocation exists, WFG-036 v2, WFG-101, WFG-010 (README Round-4 +
abstract → R8), WFG-096, WFG-026 (which is the other half of R7), WFG-024 when its blockers clear (R11), and
only then the infra rows — WFG-131 among them — which CHARTER §14b holds behind R1, R3, R7, R8 and R9.

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
  runs through the GitHub MCP (WFG-119). This sandbox also clones at **depth 50**, so deepen before any
  `merge-base --is-ancestor` claim.

## Critic's last direction note

**2026-09-06T0800Z, critic #25. The window shipped the object nine days of this page had been arguing
about, and the argument turns out to have been about the wrong thing.**

Verified here rather than read from the reports: `gates.py --mode full` **ALL GREEN** at `b70e464`
(`1562 passed, 62 skipped`, cold, 298.9 s; **+17 passed** on critic #24), the twenty most recent
`auto-gates` runs on `auto/dev` are nineteen `success` and one `cancelled` that a later push superseded —
**so there is no gate finding and no CHARTER §4b finding this lap** — every dev report of the last 24 h
carries `Reviewed by:`, and no author reply is waiting (thirty Gmail threads, every one a report this loop
sent, no reply on any; `decisions_seen.json` unchanged).

**Critic #24's falsifiable test, answered on branch (1).** `docs/auto/finals/` holds
`WFG_printables_20260906T0620Z.pdf`: 29 A4 pages, four sources and three fonts hashed into a manifest, all
seven hashes re-checked against the tree here and all seven current. **R7 has an object and WFG-007's agent
half is finished.** I am not writing about queue position again, and the nine-day question — position, or
the lock — is settled as *both*, both now paid.

**What the window exposes instead is a measurement gap, and it is the root objection.** The kit was
assembled from the four documents the loop writes and never compared against the five R7 asks for; the
overlap is **one**. The build then wrote that the missing 「A4 evidence sheet (WFG-018)」 「does not exist
yet」, and WFG-018 is `done(20260903T0653Z)` — `docs/submission_reconciliation.md`, 13,702 bytes, the file
R6's own tick is written on, whose fourth line says it is meant to be printed as one double-sided sheet.
Fifteen new tests and an independent reviewer that returned `block` all stayed green through it, because
nothing in the repository reads the builder's source list beside the readiness line it is supposed to
satisfy. **WFG-130**, P0, minutes.

**The consequence for this page is a rule about rows rather than about queues:** a row can be `done` and
leave its readiness line ☐ forever when its done-when and the line's condition describe different objects.
WFG-007's done-when says 「rehearsal aids + booth checklist」; R7 names five specific printables. That, not
priority and not the lock, is why R7 has looked stuck — and it is the honest answer to the routine's
「zero ticks for two consecutive critic laps is a direction finding」 rule, which fires today for the
second time.

**My one `fix-before-next-row` item is not either of my findings: it is WFG-113's two-command repair on the
judged screen.** It is wrong to a judge today, it has been for sixteen windows, it needs no decision, and it
is now on a ten-hour clock (WFG-119: stamp `5f9a3b8` **29** commits behind `HEAD`, ~**51** commits a day,
sandbox depth **50**). After that boundary the gate goes red in every sandbox on a screen that is not wrong
and CHARTER §9 spends the first lap that hits it on parking.

**The falsifiable test for critic #26.** (1) If `web/finals.html`'s payload prints **383 / 325**, the repair
ran and the clock is reset — score R1 on what is left (`41498ef`, WFG-115) and stop treating the counts as a
finding. (2) If it still prints **326 / 268** *and* the sandbox's `gates.py --mode full` is RED on
`test_the_integrity_panel_names_a_commit_this_repository_has`, then a two-command repair that three critic
laps have specified and one lap has already proven cannot survive a `fix-before-next-row` slot, and the
defect is the item mechanism rather than the item — say so and do not spend the budget on it a fourth time.

## Critic's previous direction note

**2026-09-06T0457Z, critic #24.** The window was one substantive commit and the best manuscript lap the loop
had run; the finding was in what the window did not touch. The root objection: **42 of 458 on 영덕** is the
number the student says out loud and the judged screen prints, and it has never met a fair opponent — while
the cheapest test of it is fully specified in `paper/GAPS.md` G7, runnable in minutes, and lives in the one
file no dev lap reads (CHARTER §4 step 1 does not list it; §12 forbids the paper routine from writing
outside `paper/`). That is **WFG-129**, still open. Its second finding was **WFG-128**, also still open.
*(Full text: `docs/auto/reports/2026-09-06T0516Z-critic.md`; #23's is in the 2026-09-06T0215Z report, #22's
in the 2026-09-05T2330Z, #21's in the 2015Z. This page stays one screen, which is why the older notes live
in the reports and not here.)*
