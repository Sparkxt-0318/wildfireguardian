# Step 1 acceptance: honest terminal reasons and persisted stage metrics

Written before any Step 1 code or run. Implementation waits for Mira's verification of Step 0 (PLAN §0).

## What changes

### 1. Decision reasons only (`decision/journey_decision.py`)

No `authoritative_status` changes. Only `unresolved_reason` and the detail change, in these cases (all UNRESOLVED
today):

| Situation (from the worker's own records) | Today | v2 Step 1 |
|---|---|---|
| Controller memory guard stopped the process (`COMPLETE_PROCESS_RECEIPT.memory_guard_triggered`) | LATE_RESULT or STALE_OR_IDENTITY_MISMATCH | `MEMORY_GUARD_STOP` |
| Outer deadline stop before any search evidence (exit by deadline signal; no SEARCH_RESULT) | STALE_OR_IDENTITY_MISMATCH or LATE_RESULT | `DEADLINE_STOP_NO_EVIDENCE` |
| No route; every search stage that ran stopped with `RSS_LIMIT` | SEARCH_TIMEOUT | `SEARCH_MEMORY_LIMIT` |
| Search returned route(s), but every whole-road check ended `RSS_LIMIT` / `RSS_LIMIT_AFTER_ADAPTIVE_FALLBACK` | SEARCH_TIMEOUT | `CHECK_MEMORY_LIMIT_ON_FOUND_ROUTE` |
| No route; stages stopped on the wall clock | SEARCH_TIMEOUT | `SEARCH_TIMEOUT` (unchanged) |

**Precedence.** A genuine identity **mismatch**, i.e. a field present and different, keeps overriding everything,
exactly as today. The new reasons replace only the cases where the identity evidence is absent because the process
was stopped.

**Detail and schema.**
- Each new reason carries `detail.evidence`: the exact records it was derived from (receipt flag, stage
  statuses/reasons, check reasons).
- The decision `schema` stays `wfg.journey-decision/1`, with `module_version` bumped. The status vocabulary is
  unchanged.

### 2. Persisted stage progress

- Each search stage (Z sweep; road_core.solve for LO, LO2 and HI; the EA build) writes `STAGE_PROGRESS.json`
  atomically, at least every 2 s of wall time and when it returns. Contents: `{stage, elapsed_s, labels, expansions,
  frontier, rss_mb_current, utc}`.
- On the deadline signal, the worker flushes the last progress before exiting.
- The writes are side effects only: no control-flow change.

## Tests, written first (`tests/test_step1_reasons.py`, `tests/test_step1_progress.py`)

**Reasons.** Each row of the table, built from synthetic worker records, maps to its reason with its evidence.
Further cases:
- a mismatched identity still gives STALE_OR_IDENTITY_MISMATCH;
- a certified route is unaffected;
- every PASS_THROUGH status is unaffected;
- a refusal is unaffected.

**Progress.**
- A worker killed by its deadline leaves a STAGE_PROGRESS.json no older than 2 s of stage time.
- A worker that completes leaves the final counts, equal to SEARCH_RESULT's labels and expansions.

**Replay.** Feeding the frozen kit's recorded F-DYN folders (`fdyn_b300`, `fdyn_b300_g12k`, `fdyn_b300_g12k_rss12k`)
to the new decision function:
- every status is unchanged;
- the reasons become the table's, e.g. the A1 Yeongdeok rows give CHECK_MEMORY_LIMIT_ON_FOUND_ROUTE.

## Acceptance (Step 1 passes iff all hold)

- **G1** on the 1-hour panel: identical (status, arrival) sets plus the FL2 rule. **Expected changes: 0 statuses, 0
  arrivals.** Reason changes are listed; on the 1-hour panel I expect 0 (no memory stops occur there), and any reason
  change there goes to review.
- **G2, G2b, G3, G5** as in PLAN.
- **G5 specifically:** the progress writes must not raise the summed median wall by more than 10%.
- **All tests above pass. Parent tests and the Step 0 tests pass unchanged.**
- **F-DYN replay (records only, no new runs):** 0 status changes and every reason as in the table, reported per
  folder.
