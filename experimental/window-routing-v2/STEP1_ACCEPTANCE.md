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

## Amendment, committed before any Step 1 code (16:2x UTC)

Reading the code before implementing showed two things that make the rule above imprecise. They are fixed here; no
code or run exists yet.

1. **Which module.** The **authoritative** decision is `decision/journey_decision_v2_1.py`. That is the one used by
   the API path, `run_profile` and G1. The worker's in-process `decision/journey_decision.py` record is
   **provisional**. Both get the same remapping, so the provisional and authoritative reasons agree.
2. **Exact remapping rules.** They are applied as a final post-step in `decision_from_worker_record`.
   - They touch only `unresolved_reason`, `unresolved_reason_text` and `unresolved_detail`.
   - The frozen reason and detail are kept under `detail.frozen_reason` / `detail.frozen_detail`, with
     `detail.evidence`.
   - Status is asserted unchanged.
   - They apply only if status is UNRESOLVED **and** no identity field is in state `MISMATCH` **and** route binding is
     not mismatched. A genuine mismatch keeps the frozen reason.
   - In order:
     - **a. MEMORY_GUARD_STOP:** `receipt.memory_guard_triggered` is true.
     - **b. DEADLINE_STOP_NO_EVIDENCE:** all three hold:
       - `receipt.deadline_termination_requested` is true;
       - the frozen reason is LATE_RESULT or STALE_OR_IDENTITY_MISMATCH;
       - the worker left no search result: RESULT absent, or `worker_failure.type == DeadlineStop` with a synthetic
         result.
     - **c. CHECK_MEMORY_LIMIT_ON_FOUND_ROUTE:** the frozen reason is SEARCH_TIMEOUT, at least one search stage
       returned a route (`arrival` not null), and every whole-road check of those routes ended
       `RSS_LIMIT` or `RSS_LIMIT_AFTER_ADAPTIVE_FALLBACK`.
     - **d. SEARCH_MEMORY_LIMIT:** the frozen reason is SEARCH_TIMEOUT, at least one search stage stopped with reason
       `RSS_LIMIT`, and no stage returned a route.
       - This replaces "every stage that ran stopped with RSS_LIMIT". The Z stage always stops on its own fixed wall
         cap first, so that wording would never fire.
     - Otherwise the frozen reason is kept.
   - `module_version` gains the suffix `+kit-v2-step1`. The schema strings are unchanged.
3. **Progress hook.**
   - `road_core`, `zsweep.contact_sweep` and `zsweep.EarliestArrivalBound` call a module-level `PROGRESS_HOOK` when
     set. They call it at points where they already do bookkeeping: the existing every-64-expansions RSS check, and
     each sweep second.
   - The worker installs a hook that writes `STAGE_PROGRESS.json` atomically, at most every 2 s.
   - The worker flushes the hook on DeadlineStop.
   - With the hook unset, behaviour is byte-identical to the parent. Tested.

**Expected F-DYN replay** (records already on disk; rules above):
- the 300 s / 3 GiB rows → MEMORY_GUARD_STOP (12/12);
- A1 Yeongdeok kriged …207, …166 and …168, and firms …166 → CHECK_MEMORY_LIMIT_ON_FOUND_ROUTE (4);
- the controller-only 12 GiB repeat's 9 rows with LO/HI RSS_LIMIT at 0 expansions → SEARCH_MEMORY_LIMIT, except
  where a SEARCH_RESULT is missing;
- A1 Uiseong at 300 s → DEADLINE_STOP_NO_EVIDENCE.

**Implementation note (before any run).** The progress file is named **`SEARCH_PROGRESS.json`**, not
`STAGE_PROGRESS.json`. The harness reads every `STAGE_*.json` as a phase checkpoint with a `phase` key, so the
original name would collide. The content is unchanged. After each LO, LO2 and HI return, the final metrics (expansions,
labels, status, reason) are written with `final: true`. The "final counts equal SEARCH_RESULT" test compares those.

## Amendment 2: rule (b) refined, before any Step 1 panel run (16:3x UTC)

**Finding.** Checking the Step 0 records showed that rule (b) would label a deadline stop **after** search stages had
run as "no evidence", which is untrue. Yeongdeok 0325T19 FX2 on the 1-hour panel is an example: Z and LO ran, then the
outer deadline stopped the worker.

**Rule (b) is split:**
- **b1. DEADLINE_STOP_NO_EVIDENCE:** as before, **and** the worker recorded no search stage (`rda_stages` empty or
  absent).
- **b2. DEADLINE_STOP_DURING_SEARCH (new reason):** `receipt.deadline_termination_requested`, the frozen reason is
  LATE_RESULT or STALE_OR_IDENTITY_MISMATCH, the worker stopped with DeadlineStop, **and** it recorded at least one
  search stage. The evidence lists the stages with status and reason.

**Expected reason changes on the 1-hour panel, stated now** (this replaces "expected 0"):
- Yeongdeok 0325T19 FX2 changes in every rep where the outer deadline stopped it: LATE_RESULT →
  DEADLINE_STOP_DURING_SEARCH. In Step 0 that happened in 3 of 4 runs.
- **No other mission** is expected to change reason.
- Statuses: **0 changes expected**, as before.
- Any reason change on any other mission goes to review.

**F-DYN replay expectation, corrected.** The A1 Uiseong rows (Z ran, then a deadline stop) give
DEADLINE_STOP_DURING_SEARCH, not NO_EVIDENCE. The replay test is updated accordingly, before the panel run.
