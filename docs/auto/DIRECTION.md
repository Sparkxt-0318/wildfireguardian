# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. Last checked by critic #21, 2026-09-05.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*Critic #20's falsifiable test is half-resolved and it resolved FOR this page: the 18:17Z dev lap took
WFG-114, the row this page named and the author promoted. Then it pushed nothing (NH-030). The order below
is unchanged, because nothing about the order was wrong.*

1. **WFG-114** (P0, one lap) — **the author's own row.** NH-027 option A, verbatim: 「Run it in the sprint
   now, P0 ... report the number whatever it says」. The present-perimeter + buffer arm on 의성·안동: the
   fair opponent for the headline, and the answer to the objection four consecutive critics have written.
   ⚠ It is `in-progress(20260905T1820Z)` with **no work commit behind it**. `CRITIC_LATEST.md` carries the
   release rule; critic #21 released nothing, because a claim inside its time-box is not a stale claim.
2. **WFG-007** (P0, the printables) — unchanged from critic #20, and its evidence got one day worse.
   `docs/auto/finals/` still holds two `.md` files and no PDF. This row alone holds **R7 and half of R9**,
   and no readiness line has moved for **six** critic laps.
3. **WFG-117** (P0, new this lap) — **this lap's one `fix-before-next-row` item**, and the only finding in
   six laps that a judge would hear rather than read. `JUDGE_QA.md` Q30 is **T0** and drills the student to
   say 「등록된 값 295개 중 261개」 while `docs/NUMBERS.json` holds 326 / 268 / 58 and the screen behind them
   prints 326 · 268. Ungated. A ⚠ note is on Q30 already so nobody rehearses it.

Then WFG-115 (moved up this lap, see below), WFG-106 then WFG-104 (the two Q&A cards; read WFG-106's
corrected opening first, it answers the **dilution** objection, not the **opponent** one), WFG-113,
WFG-110, WFG-036 v2, WFG-101, WFG-010 (README Round-4 + abstract → R8), WFG-096, WFG-024 when its blockers
clear (R11), and only then the infra rows, which CHARTER §14b holds behind R1, R3, R7, R8 and R9.

## What not to do

- No new spread model, no retrain, no re-acquired region before 2026-10-16 (CHARTER §3). WFG-114 is routing
  only and is not an exception to this.
- No fourth rewrite of the README's opening paragraph; disagreements go to NEEDS_HUMAN.
- No consultation-dependent claim (NH-010): nothing may wait on an expert reply.
- No ratio between the chain and the season areas (NH-018).
- Do not spend a lap on the six-fire study-area map until per-fire burned areas are registered (WFG-060).
- Do not commit the bundle payload. R9 does not require it and critic #16 said so on the line itself.
- Do not open another gate-about-the-loop row while the printables do not exist (CHARTER §14b).
- **Do not run `make baseline-freeze` in a sandbox.** The author ran it on the laptop at `38620f2` and it was
  correct there; here it would record the two raw contracts as MISSING and destroy the protection.

## Critic's last direction note

**2026-09-05, critic #21. The window is one line long, and that is the finding.** Between critic #20's push
(`3efd0db`, 17:21Z) and `HEAD` there is exactly one changed line: the status cell of WFG-114. The 18:17Z dev
lap claimed the author's row at 18:20Z and, 1 h 50 m later, has pushed nothing; no artifact of the kind the
row asks for exists, and `git log --all --grep=WFG-114` finds only the claim. **NH-030** is open on it and
`CRITIC_LATEST.md` carries the CHARTER §5 release rule for the next lap. I released nothing myself: at the
moment of measurement the lap was still inside CHARTER §4's two-hour time-box, and releasing a live claim is
the NH-007 failure.

**Why that matters more than another reorder.** Readiness has read 4 of 11 for six consecutive critic laps.
Critic #18 blamed the queue, #19 blamed the queue, #20 blamed this page. This window rules all three out:
the page named the right row, the lap took it, and nothing came out. **The constraint this window was lap
completion, not direction.** A seventh lap of reordering would be measuring the wrong thing again, so the
order above is untouched.

**My one row move is WFG-115, and it is about the fallback rather than the front of the queue.** At
`492364c` the `todo` **P1** rows WFG-107 and WFG-108 sat above `todo` **P0** rows WFG-110, WFG-113 and
WFG-115, which CHARTER §14 forbids. It is latent while this page names the next rows — but #20's own finding
is that this page can go stale for a lap, and the table is the fallback when it does. WFG-115 moved above the
P1 block; the rest is **WFG-118**, because one move per lap cannot fix a systemic sort.

**Also filed: WFG-119, and it is why to trust WFG-115 more than yesterday.** This sandbox clones at **depth
50** and no lap has said so; `merge-base --is-ancestor`, the instrument behind WFG-067's gate and every
「not reachable」 claim four critics have written, cannot answer across that boundary. Deepened to 170 commits
and re-run: `41498ef` is still not an ancestor, so **WFG-115 survives the confounder**. Predicted, not yet
seen: once a screen stamp ages past 50 commits the ancestry gate goes red in every sandbox and stays green in
CI (`fetch-depth: 0`). The same row carries the 403 this routine's step-2 `curl` now returns.

**Readiness: 4 of 11 (R2, R4, R5, R6), unchanged, six laps.** R7 and half of R9 are WFG-007.

**The falsifiable test for critic #22:** if the next dev lap pushes a WFG-114 artifact, the 18:17Z lap was
merely slow and NH-030 closes as option B. If WFG-114 is still `in-progress(20260905T1820Z)` with no work
behind it, the claim is a lock with no key, the next lap must release it under CHARTER §5, and #22 should
raise NH-030 option C — an automatic expiry on stale claims — rather than write a seventh note about the
queue.

## Critic's previous direction note

**2026-09-05, critic #20.** Raised WFG-007 P1 → P0 on critic #19's falsifiable test (WFG-109 closed,
printables still absent), and found the direction defect this page had about itself: the author pushed
`9442430` at 14:24Z promoting the fair-opponent arm, critic #19 rewrote this page twelve minutes earlier,
and for one lap the page steered the loop away from the author's own row. The rule it added — **this page
is re-read after an author push, not only after a dev lap** — is what put WFG-114 first, and this lap's
window is the evidence it worked. #20 set no `fix-before-next-row` item and filed WFG-115 as a row instead.
*(Full text: `docs/auto/reports/2026-09-05T1716Z-critic.md`; critic #19's is in the 1412Z report. This page
stays one screen.)*
