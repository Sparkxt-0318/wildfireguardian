# G6b run procedure (rule; committed before the first G6b job)

**Governing text.**
- G6_RULE.md;
- G6A_RULING.md (1) and (2): the amended definition, prospective and for G6b only, as accepted by the assessor and
  read by the independent verifier;
- G6A_RUN.md for how a job is run and how its outcome is extracted, unchanged.

Where this file is silent, those govern. Nothing here loosens them.

## Kits
- V2 `0fffb589…`: Main's kit, built from Main, byte-identical to the verified kit.
- PARENT `b6770404…`: the frozen request-window kit.

## Jobs
All **9,722** route-check jobs of the six planner caches (`planner/cache/INDEX.json`), in strata as in G6A_SAMPLE:

| Cache | Jobs | ROUTE | NOROUTE | TIMEOUT | AT_ISSUE |
|---|---|---|---|---|---|
| uiseong_andong_2025/20250323T010000Z | 1,523 | 1,188 | 335 | 0 | 0 |
| uiseong_andong_2025/20250324T090000Z | 1,518 | 1,158 | 354 | 0 | 6 |
| uiseong_andong_2025/20250325T170000Z | 1,557 | 1,029 | 399 | 39 | 90 |
| yeongdeok_2025/20250325T190000Z | 1,810 | 1,400 | 161 | 195 | 54 |
| yeongdeok_2025/20250325T230000Z | 1,673 | 1,486 | 138 | 49 | 0 |
| yeongdeok_2025/20250326T080000Z | 1,641 | 1,510 | 81 | 14 | 36 |

- The list is written deterministically by `tools/g6b_jobs.py`, sorted by cache and then job_id, to `G6B_JOBS.json`.
- The G6a sample's rows are **not** reused. Every job is run fresh in G6b.

## Runs per job (fixed)
- **PARENT exactly 2 times** (P1, P2). "Every PARENT run" in the amended definition means both.
- **V2 exactly 1 time** (V).
- **V2 rerun once (R), only** where V2 is UNRESOLVED with a time-capped reason (the closed list) and PARENT is not.
  This is G6_RULE's "listed and rerun once". The rerun's outcome replaces V's. If V2 is still unresolved there, it is
  a failure.

## Order, tracking and the stop rule
- **One cache at a time, in the table's order:** P1 → P2 → V → R → classification (below) → the next cache.
- Each cache's phases checkpoint per job (`tools/g6_run.py`).
- A launch is one harness-tracked task of at most 2 h, driven by `tools/g6b_drive.py`. On relaunch it resumes at the
  first unfinished phase of the first unfinished cache. Every stop (task limit, container restart) is logged in
  `RUNLOG.txt`. No detached jobs.
- 3 workers. G6 runs are never used for timing claims.
- **Stop rule.** After each cache's classification, if any job is in a class **other than** "unchanged" or "allowed
  difference" (both kinds), or any harness or identity or input error occurs, the driver stops before the next cache.
  The author reports to the orchestrator before anything continues.
- **Progress reports per cache** are counts only, until the comparison is final.

## Classification of each job (the amended definition; `tools/g6b_classify.py`)
- **unchanged:** the V2 outcome key (verdict, plus arrival for a checked route) is in {P1, P2}, and it is allowed
  against the RECORD by G6_RULE's table.
  - Ties (V2 legs differ from every PARENT run with the same key) and raw_status differences (judged against
    {P1, P2}) are listed beside it.
- **allowed difference, optimum confirmed** / **allowed difference, optimality not verified:** all of G6A_RULING (1)
  holds:
  - both PARENT runs are time-capped (the closed list: unresolved / TIMEOUT / raw reason ∈ {LATE_RESULT,
    DEADLINE_STOP, SEARCH_TIMEOUT});
  - V2 is a checked route, published on time within 81 s;
  - no contradiction with the RECORD, the router field (crossref @ 5389803e) or the certificates (@ c0e34d4);
  - both frozen checkers accept the route (`tools/g2_recheck.py`, fresh interpreters);
  - arrival = `router.arrival` gives "optimum confirmed".
    - Arrival > `router.arrival` → the router witness is regenerated (field code @ 5389803e, matched by legs_sha256)
      and run through both checkers.
    - A passing witness is a **failure**. A failing witness gives "optimality not verified". If the witness cannot be
      regenerated with a matching hash, the job is "witness unavailable", which is a stop-rule class.
  - g2b @ deeb7c2 is run on every allowed difference and reported.
- **failure:** everything else, including:
  - a route or refusal → V2 UNRESOLVED (after R);
  - PARENT UNRESOLVED for a reason not on the closed list;
  - UNRESOLVED → refusal;
  - any refusal ↔ route change;
  - an arrival change on a route;
  - a V2 timeout contradiction;
  - V2 disagreeing with the RECORD where PARENT agrees.
- **pre-existing (listed, not V2 failures):** PARENT ≠ RECORD, where V2 equals PARENT.

## Pass
G6b passes if all 9,722 jobs are "unchanged" or "allowed difference", with 0 errors and 0 identity or input
mismatches.
- Allowed differences are reported as their **own counts** (optimum confirmed / optimality not verified), per stratum
  and per cache, never folded into "unchanged" or into "pass".
- Concentration is stated.

## Cost (estimated from G6a's measured wall per stratum, weighted by these counts)
About 19.6 h for P1, 19.6 h for P2 and 17.2 h for V at 3 workers: **about 56 h**, plus R and the checks.

## Then
- The independent verifier recomputes the classification from the rows.
- The reviewers rerun the checks on a sample of the allowed differences.
