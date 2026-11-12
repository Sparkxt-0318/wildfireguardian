# W-KIT checkpoint 1 (measured; not fit for live use)

Code: `planner/src/features/lastmile/channels/build.ts` · tests: `tests/planner/wkit.channels.test.ts`.
Run: `cd planner && npm ci && npx vitest run ../tests/planner/wkit.channels.test.ts` (13 tests). Full planner suite:
`npx vitest run` → 22 files, 378 tests passed (this container, Node 22, Linux x86_64).

Outputs per origin (ko source + en): 20 s head-script core with the five warning elements between a framing opener
(not real / data / markers) and closer (official orders first); ARS voice call (1 leaving|heard, 2 needs help to
leave — "passed to the 이장 and 읍·면사무소", 3 repeat); family text (≤ 90 B EUC-KR / ≤ 160 GSM-7) + 3-line call
script; "no order yet" message (only for supplied status `not_issued`, ≤ 157 chars); staff data-age line and
issue-order-by field (a time only for leave_by with a computed value). Staff transport-need list: no checked
leave-by first, then leave-by ascending.

Measured:
- Six booth caches, 531 real origins (501 leave_by, 11 no_route, 19 unresolved): 0 violations; every head core
  ≤ 20 s with all five elements (max 20.0 s ko, 16.0 s en); full script ≤ 32.7 s ko, 27.5 s en. Independent oracles
  (Python euc_kr, NEVER/DEPART patterns, clock-time regex) agree.
- 600 generated synthetic cases: cores ≤ 20 s with five elements in all; the only violations are 18 Korean full
  scripts over the provisional 35 s cap (long names and/or MOCK/test markers) — withheld, fail closed.
- Feasibility finding: the three mandatory framing sentences take ≈ 12.6 s, so a 20 s script *including* framing
  is infeasible; the 20 s budget applies to the core (option 1, pending Iris).

Pending: Iris's assessment (20 s framing, list ordering, order-status input); Sofia's exact August 2025 rules (157
unit, required order); Richard's issue-order-by fields (currently a generic `{offsetS}` input); English review.
Not wired into the UI panel or CSV yet.
