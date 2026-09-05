# Direction — where the project is going, on one screen

*Written 2026-09-04 by the author's session; steered again the same evening (product first). Rewritten by the research routine every second day; the critic checks it after every dev lap (CHARTER §14). The dev routine reads it before claiming a row. Last checked by critic #20, 2026-09-05.*

## Thesis (two sentences)

A forecast of where the fire will be, not where it is, changes which walking route and which rescue order are safe, and the repository proves that on committed public data for real Korean fires with every number re-derived by a gate. The finals product is that proof made legible at a booth: the map, the routes, the honest limits.

## Next three rows, and why

*WFG-109 closed and its gate is real: I mutated the template myself and `tests/test_finals_template_sync.py`
goes red. The two rows below it on this page are no longer the top of the queue, because the author moved
one row into the sprint and this page did not know.*

1. **WFG-114** (P0, one lap) — **the author's own row, and this page has never named it.** NH-027 option A,
   verbatim: 「Run it in the sprint now, P0 ... report the number whatever it says」. It is the
   present-perimeter + buffer arm on 의성·안동: the fair opponent for the headline. It sits at the top of the
   backlog table where the author asked for it, and it answers the root objection three consecutive critics
   have written down. *(Filed by the author as `WFG-108`; renumbered here because two live rows held that id.)*
2. **WFG-007** (P0, the printables) — **raised from P1 by this lap, which is its one row move.** Critic #19
   wrote the test: 「if WFG-109 is closed and the printables still do not exist, then WFG-007's priority is the
   defect, not its position」. WFG-109 is closed. `docs/auto/finals/` holds two `.md` files and no PDF. This
   row alone holds **R7 and half of R9**, and no readiness line has moved for **five** critic laps.
3. **WFG-115** (P0, new this lap) — the judged screen prints a second commit id, `41498ef`, and
   `git merge-base --is-ancestor 41498ef HEAD` exits non-zero. Same failure shape WFG-067 closed, in the same
   panel, unread by the gate WFG-067 added, and it falsifies half of `JUDGE_QA.md` Q35's answer.

Then WFG-106 then WFG-104 (the two Q&A cards; read WFG-106's corrected opening first, it answers the
**dilution** objection, not the **opponent** one), WFG-113, WFG-110, WFG-036 v2, WFG-101, WFG-010
(README Round-4 + abstract → R8), WFG-096, WFG-024 when its blockers clear (R11), and only then WFG-088,
WFG-089, WFG-094, WFG-097, WFG-099, WFG-102, WFG-105, WFG-107, WFG-108, WFG-111, WFG-112, WFG-116 and the
other infra rows, which CHARTER §14b holds behind R1, R3, R7, R8 and R9.

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

**2026-09-05, critic #20. Critic #19's falsifiable test resolved, and it resolved AGAINST the queue.** It read:
「if `WFG-109` is closed and the printables still do not exist, then WFG-007's priority is the defect, not its
position, and critic #20 should raise it to P0」. WFG-109 is `done(20260905T1520Z)`; `docs/auto/finals/` holds
`BOOTH_SETUP.md` and `DETECTION_FLOOR_CARD.md` and no PDF. **Raised, and that is this lap's one row move.**

**But the bigger direction defect this window is not mine and not the queue's: it is this page.** At 14:24Z the
author pushed `9442430`, closing NH-027 with 「A) Run it in the sprint now, P0」 and putting the fair-opponent
arm at the top of the backlog table. Critic #19 rewrote this page at 14:12Z, twelve minutes earlier, and
nothing since has added the row. CHARTER §14b says the dev lap takes **this page's** order over the table when
the two differ, so for one full lap this page has been steering the loop away from the one row the author
personally promoted into the sprint. Two dev-lap slots passed. **A page that overrides the table has to be
re-read after every author push, not only after every dev lap.**

**So I set no `fix-before-next-row` item.** Not because nothing qualifies: WFG-115 is a judge-facing falsehood
on the screen today and would qualify under §14b. Because setting one would displace either the author's row or
the printables, and readiness has now been 4 of 11 for **five** consecutive critic laps while four of the last
five dev slots went to a critic's item. Critic #18 proved the empty block moves the product; critic #19 set an
item anyway and readiness did not move. The rule stands and this lap obeys it.

**Readiness: 4 of 11 (R2, R4, R5, R6), unchanged, five laps.** R7 and half of R9 are WFG-007. R3 moved
materially without moving the box: the author executed NH-029 option A at `38620f2` and I re-ran
`make baseline-verify` here — six differences are now **two**, and both are the git-ignored raw manifests that
exist only on the laptop. The re-freeze preserved every protection: the two `untracked_contracts` hashes and
all four `protected` artifact hashes are byte-identical to the previous freeze. R3 now waits on one
`make all-checks` run on the author's own machine, which is NH-029's remaining half.

**The falsifiable test for critic #21:** if the next two dev laps take WFG-114 and WFG-007 in that order, this
page's re-read after an author push is what did it, and the re-read should become a line in CHARTER §14. If
either lap takes something else, then this page is not actually the lever §14b says it is, and critic #21
should say so rather than reorder it again.

## Critic's previous direction note

**2026-09-05, critic #19.** Set WFG-109 as its one item after proving on disk that
`scripts/finals.template.html` still carried the STATIC VIEW sentence `web/finals.html` had withdrawn. The
next lap closed it and built a stronger gate than the row asked for. #19 also read the direction rule as
「measuring the wrong thing」 and wrote the WFG-007 test this lap resolved. *(Critic #18's note is in
`docs/auto/reports/2026-09-05T1412Z-critic.md`; this page stays one screen.)*
