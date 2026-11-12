# G6: reproduction of the 9,722 recorded one-hour route-check verdicts

Rule written before any G6 run. Decided by the orchestrator at 16:10 UTC as option (a), with attribution.

## Source of record

The planner's six caches, `planner/cache/INDEX.json` on Main, schema `wfg.planner.cache/1`.
- The cache file sha256s are recorded in `G6A_SAMPLE.json`.
- The jobs were produced by the **release** kit: `kit_candidate_id WFG-latest-completion-kit-20261015-v3`, API 1.8.0,
  budget_s 30, on macOS arm64.

**Inputs.** Each is identified by its sha256 (via `integration/kit/INPUT_BINDING.json`) and verified present in the
fetched `data/routing` tree:

| Region | Input | HAZARD.json sha256 prefix |
|---|---|---|
| uiseong_andong_2025 | 20250323T010000Z | 21a8a087 |
| uiseong_andong_2025 | 20250324T090000Z | cde0707d |
| uiseong_andong_2025 | 20250325T170000Z | 87c2ee0c |
| uiseong_andong_2025 | graph | 8c37e5b6 |
| yeongdeok_2025 | 20250325T190000Z | fe33db21 |
| yeongdeok_2025 | 20250325T230000Z | fa347cf3 |
| yeongdeok_2025 | 20250326T080000Z | 0f468b69 |
| yeongdeok_2025 | graph | f097e6c8 |

The runner re-verifies every sha before each job.

**Job contents (cache: `route_checks[job_id]`).**
- `request`: start node, destination node, depart_offset_s, dwell_s, window [0, 3600], limits.
- `result`: verdict ∈ {checked_route, model_no_route, unresolved}, raw_status, reason_code, arrival_s, and the route
  (edge_ids, times_s, route_sha256).
- `recheck_of` marks a re-run of a timed-out original.

**Counts.**

| Class | Jobs |
|---|---|
| Checked routes | 7,771 |
| Model no-route | 1,468 |
| Timeouts (291 originals + 6 rechecks; raw_status UNRESOLVED, reason TIMEOUT) | 297 |
| AT_ISSUE_FAILURE | 186 |
| **Total** | **9,722** |

## How each job is run

Each job is run by **both** kits, in fresh processes, on this host:
- **V2:** the kit under test;
- **PARENT:** the frozen request-window kit.

The request is rebuilt from the cache with `api.requests_build.build_request` (the same builder as the API). The budget
is the **work-unit budget of Step 3**, plus a wall cap of 81 s, which is 30 s × the measured 2.7 host factor.

**G6 runs are never used for timing claims.** They may run in parallel.

## "Reproduce" (Iris's definition) and attribution

Per job, V2 is compared with the RECORD. Any difference is attributed by also comparing PARENT with the RECORD:

| Recorded | Allowed for V2 |
|---|---|
| checked_route | a checked route with **identical arrival_s**, and identical legs (edge_ids and times) unless another route has the same arrival |
| model_no_route | a refusal (`FULL_MODEL_REFUSAL_PROVEN`) |
| timeout | anything except a contradiction (see below) |
| AT_ISSUE_FAILURE | AT_ISSUE_FAILURE |

For timeouts, a contradiction uses Richard's router-only field (`results/TIMEOUT_NO_ROUTE_CERTS_1h.json`, c0e34d4):
- the **98** jobs the field proves infeasible (NO_ROUTE certificates accepted by check_py) must **not** become routes;
- the **199** feasible jobs must **not** become refusals.

**Attribution:**
- **V2 ≠ PARENT** on any job is a **G6 failure**, except an UNRESOLVED on one side caused by the wall cap; that is
  listed and rerun once.
- **PARENT ≠ RECORD** is a **pre-existing kit difference**, release vs request-window. It is listed with both outcomes
  and is not a v2 failure.
- **FL2-type exception:** a job whose PARENT outcome differs between 2 runs is cap-sensitive. It is judged against the
  set of PARENT outcomes, and the list of such jobs is produced before V2 runs.

## G6a: required before the FIRST multi-hour v2 number is quoted

**Sample.** Fixed by seed **20261112** with `tools/g6_select.py`; committed as `G6A_SAMPLE.json` with this rule.

| Stratum | Jobs | How chosen |
|---|---|---|
| Timeouts | 297 | all |
| AT_ISSUE | 186 | all |
| Checked routes | 150 | 25 per cache, seeded |
| Model no-routes | 72 | 12 per cache, seeded |
| **Total** | **705** | × 2 kits |

**Cost.**
- Recorded compute_s × 2.7, capped at 81 s, for both kits:
  - timeouts about 8.1 CPU-h (re-check times where recorded, else the full cap);
  - routes about 3.8 CPU-h (median recorded 17.5 s);
  - no-routes about 1.0 CPU-h;
  - AT_ISSUE about 0.3 CPU-h.
- **Total about 13 CPU-h**, above the 8–10 CPU-h target. The 297 timeouts alone are about 8 CPU-h and are mandatory.
- At 3 parallel workers this is about 4.5 h of wall time.

**Smaller alternative, if the orchestrator prefers:**
- 15 routes per cache (90) and 8 no-routes per cache (48), about 11 CPU-h;
- power 3.3% for routes and 6.1% for no-routes.

**Detection power** (zero failures in n ⇒ 95% upper bound ≈ 3/n on the per-job V2 ≠ PARENT rate):
- routes, n = 150: ≤ **2.0%**;
- no-routes, n = 72: ≤ **4.2%**;
- timeouts and AT_ISSUE are complete (all jobs).

**Order.** G6a runs **after Step 3**, because the work-unit budgets must land first (orchestrator, Iris).

## G6b: required before any paper claim or kit-v2 release cut

All 9,722 jobs × 2 kits:
- run detached, checkpointed per cache;
- at the parallelism the host allows without disturbing G1/G5 timing runs (paused during them);
- same rule as above.
