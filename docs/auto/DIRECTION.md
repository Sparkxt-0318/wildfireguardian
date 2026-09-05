# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. Last checked by critic #19, 2026-09-05.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*WFG-037 closed. `docs/auto/finals/BOOTH_SETUP.md` exists, every command in it was executed, and writing
it falsified three of the repository's own claims. The booth now has a recipe. What it does not have is
paper.*

1. **WFG-109** (P0, one lap) — the judged screen and the template it is built from disagree, and the
   template wins on the next `make finals`. Verified on disk by critic #19 at `92bfc4f`. **This is critic
   #19's one `fix-before-next-row` item**, and it is deliberately not another edit of
   `DEMO_SCRIPT_5MIN.md`.
2. **WFG-106** then **WFG-104** (both P0) — the two Q&A cards. **WFG-106 was moved above WFG-104 this lap**
   because this page has said since critic #18 that it is the cheaper and stronger of the two and the table
   said the opposite. Read WFG-106's corrected opening first: it answers the **dilution** objection, not
   the **opponent** objection, and a card that confuses the two would overclaim worse than the sentence
   WFG-103 just withdrew.
3. **WFG-007** (P1, the printables) — **now the single artifact holding two readiness lines, R7 and R9**,
   and the hole `BOOTH_SETUP.md` §7.3 openly stands on. It is P1 and sits below four P0 rows in the table;
   this page puts it third, and CHARTER §14b says the dev lap takes this page's order when the two differ.

Then WFG-110 (R1's screen → key table, six rows wide and now measured), WFG-036 v2, WFG-101, WFG-010
(README Round-4 + abstract → R8), WFG-096, WFG-024 when its blockers clear (R11), and only then WFG-088,
WFG-089, WFG-094, WFG-097, WFG-099, WFG-102, WFG-105, WFG-107, WFG-111 and the other infra rows, which
CHARTER §14b holds behind R1, R3, R7, R8 and R9.

## What not to do

- No new spread model, no retrain, no re-acquired region before 2026-10-16 (CHARTER §3).
- No fourth rewrite of the README's opening paragraph; disagreements go to NEEDS_HUMAN.
- No consultation-dependent claim (NH-010): nothing may wait on an expert reply.
- No ratio between the chain and the season areas (NH-018).
- Do not spend a lap on the six-fire study-area map until per-fire burned areas are registered (WFG-060).
- Do not commit the bundle payload. R9 does not require it and critic #16 said so on the line itself.
- Do not open another gate-about-the-loop row while the printables do not exist (CHARTER §14b).
- **Do not run the WFG-033(b) arm before the finals** unless the author reopens NH-027.
- **Do not run `make baseline-freeze` in a sandbox.** It would record the two raw contracts as MISSING and
  destroy the protection on the irreproducible Korean artifacts. NH-029 is the author's.

## Critic's last direction note

**2026-09-05, critic #19. Critic #18's falsifiable test resolved, and it resolved FOR the loop.** It read:
「if `docs/auto/finals/BOOTH_SETUP.md` exists at that lap, the no-item lever works and should be used again
whenever readiness stalls two laps.」 **It exists**, 256 lines, Korean, and I read it line by line rather
than reading the lap that wrote it. Critic #18 spent its whole act on withholding one lever for one lap,
and one lap later the file that had gone unclaimed for six days was written. The lever is real and the
rule now stands: **when readiness stalls two critic laps, set no `fix-before-next-row` item.**

**So why do I set one.** Readiness did not stall for want of direction this window; it stalled on paper and
on an email. And the window left one thing behind that a judge can see: `scripts/finals.template.html:1378`
and `:1381` still carry the STATIC VIEW sentence WFG-103 withdrew, while the built `web/finals.html` carries
the correction. I confirmed both on disk. Nothing is wrong on the judged screen today; the next `make finals`
puts a withdrawn claim back in front of five judges, and no gate reads the template. That is a judge-facing
surface under CHARTER §14b, it is minutes of work, and it is the first critic item in nine that is not
another sentence of `DEMO_SCRIPT_5MIN.md`.

**Readiness: 4 of 11 (R2, R4, R5, R6), and no line has moved for FOUR consecutive critic laps (#16 to #19).
The rule fires and this time it is measuring the wrong thing.** The three lines the loop is closest to are
held by two objects and neither is a direction problem. R7 and R9 both wait on **the printables** (WFG-007),
which no lap has claimed and which is P1 sitting below four P0 rows. R3 waits on the author: writing the
recipe proved that `make all-checks`, the command R3 names, **does not pass on any machine** including the
author's, because the baseline freeze is stale in four ways that are in every clone (NH-029). Eighteen critic
laps, mine included, read `baseline-verify WARN, expected off-laptop` and moved on. That is the single best
thing this window produced and no lap claimed credit for it.

**The falsifiable test for critic #20:** if `WFG-109` is closed and the printables still do not exist, then
WFG-007's priority is the defect, not its position, and critic #20 should raise it to P0 rather than write
another direction note about it.

## Critic's previous direction note

**2026-09-05, critic #18.** Of the last eleven dev claims, eight were a critic's `fix-before-next-row` item,
the last three on three consecutive slots and all three on `DEMO_SCRIPT_5MIN.md`, while `BOOTH_SETUP.md` had
never once been claimed. Critic #18 set **no** item and moved WFG-037 above WFG-104, so the next dev lap
would meet the booth first. It did, and it built it. *(Critic #17's note is in
`docs/auto/reports/2026-09-05T0815Z-critic.md`; this page stays one screen.)*
