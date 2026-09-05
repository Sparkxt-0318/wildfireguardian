# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. Last checked by critic #16, 2026-09-05.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*WFG-036 v1 landed and `make finals-bundle` verifies byte-identically, so the bundle mechanism works and
what R9 still lacks is the two artifacts that go inside it. The table now points at them in order.*

1. **WFG-100** (P0, minutes to one lap) — the one `fix-before-next-row` item: the booth script's six segment
   times are unmeasured and cannot all be right (1,630 spoken syllables in 300 s; 4.24 to 7.07 per second
   across segments, fastest on the limitations close, which is last). Judge-facing, and it must be settled
   before anyone else edits that document.
2. **WFG-037** then **WFG-007** (P0, P1) — the booth recipe (R3's booth half) and the printables (R7). These
   are the two things R9 is waiting on, so they come before WFG-036 v2, which folds them in on 09-14.
   **Moved WFG-037 up this lap** (below).
3. **WFG-101** (P0, hours) — the card for the question the repository can already answer better than any
   competitor and the student cannot: the headline 24.73 % was 3.53 % before a DEM defect this project found
   and corrected in its own data.

Then WFG-010 (README Round-4 + abstract → R8), WFG-096, WFG-024 when its blockers clear (R11), and only then
WFG-088, WFG-089, WFG-094, WFG-097, WFG-099, WFG-102 and the other infra rows, which CHARTER §14b holds
behind R1, R3, R7, R8 and R9.

## What not to do

- No new spread model, no retrain, no re-acquired region before 2026-10-16 (CHARTER §3).
- No fourth rewrite of the README's opening paragraph; disagreements go to NEEDS_HUMAN.
- No consultation-dependent claim (NH-010): nothing may wait on an expert reply.
- No ratio between the chain and the season areas (NH-018).
- Do not spend a lap on the six-fire study-area map until per-fire burned areas are registered (WFG-060).
- Do not commit the bundle payload. R9 does not require it and critic #16 said so on the line itself.
- Do not open another gate-about-the-loop row while the printables and `BOOTH_SETUP.md` do not exist
  (CHARTER §14b). WFG-097, WFG-099 and WFG-102 are filed and parked behind exactly that rule.

## Critic's last direction note

**2026-09-05, critic #16. I moved one row and it is the same correction as last lap, one line further down: WFG-037 (P0, the booth recipe, R3) sat at table line 75, below fourteen P1 rows, so the row after WFG-036 in table order was a P1 hygiene item and not the thing R9 is actually waiting on.** CHARTER §3b forbids a P0 below a non-P0 and §14b holds those P1 rows behind the readiness lines, so this was the table contradicting the charter twice, not a judgement call. WFG-037 now sits directly under WFG-036; WFG-100 goes above both as the `fix-before-next-row` item and WFG-101 below them. **What the window earned:** `release/kcf-finals-2026/` exists, and I ran `make finals-bundle` myself rather than reading the claim — exit 0, 16 files, byte-identical. I also answered on the R9 line the question WFG-036 v1 put to the critic: R9 does **not** require a committed payload, because the line's own condition is a byte-identical rebuild. So R9 is held by the printables and the recipe alone, which is why they are rows 2 and 3 above. **No readiness line ticked this window** (still 4 of 11), and that is not the direction finding — R4 moved last window, so the two-consecutive-laps rule does not fire. The census holds the shape critic #15 opened: judge-facing lines **382 of 1,754 authored (21.8 %)** against 27.3 %, 4.9 % and 2.6 % in the three windows before it — two consecutive windows above 20 % after eleven below 5 %. **The falsifiable test for critic #17:** if the next lap produces `docs/auto/finals/BOOTH_SETUP.md`, this page is steering; if it produces another gate or another registry, WFG-084's cap should stop being a proposal and become the rule.

## Critic's previous direction note

**2026-09-05, critic #15.** Moved WFG-036 (P0, release bundle, due 09-10) up from table line 69 where it sat below two P1 hygiene rows. Ticked **R4** on its own reading of `docs/auto/DEMO_SCRIPT_5MIN.md` — six timed segments summing to exactly 300 s, five judge-lens interruption sentences, 33 registry keys resolved and value-matched — the first readiness line to move in six critic laps, taking the count to 4 of 11. Judge-facing lines that window: 257 of 943 authored (27.3 %). One `fix-before-next-row` item, WFG-095, on the same document. *(Critic #14's note is in `docs/auto/reports/2026-09-05T0221Z-critic.md`; this page stays one screen.)*
