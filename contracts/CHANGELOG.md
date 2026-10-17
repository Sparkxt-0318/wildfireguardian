# WildfireGuardian Route-Check API contract changelog

The contract file is `contracts/wfg_api_v1.yaml` (OpenAPI 3.1). Base URL `http://127.0.0.1:8765/v1`.
Any change after the first push is recorded here with a new minor version (v1.1, v1.2, ...).

## v1.0.0 — initial contract

- Endpoints: `GET /health`, `GET /regions`, `GET /regions/{region}/forecast`, `POST /route-checks`,
  `GET /route-checks/{job_id}`, `GET /route-checks/{job_id}/export`, `POST /dispatch-plans`, `GET /dispatch-plans/{job_id}`.
- Verdicts: `checked_route`, `model_no_route`, `unresolved` (with `reason_code`). `unresolved` is never safe.
- Defaults are the final-experiment values: peak 10 kW/m², dose 100 kJ/m², dwell 120 s, policy `full`.
- `incurred_dose_kj_m2` (default 0) is included so the recorded final-panel missions with prior exposure (FX missions)
  can be replayed exactly through the API.

## v1.1 — additive clarifications after wrapping the kit (no field removed or renamed)

- `ReasonCode` gains `INPUT_REJECTED`, `AT_ISSUE_FAILURE` and `DISCONNECTED`. These are the kit's pass-through
  decision statuses, which are always unresolved. Strict clients that enumerated v1.0 codes must accept them.
- `ScenarioExposure` gains optional `basis`, `peak_upper_kw_m2` and `dose_upper_kj_m2`. Under `travel_only`, `contact`
  is assessed against the unchanged full hazard and may be `true`, because that policy does not enforce flame contact.
- `RouteCheckResult` gains optional `lower_bounds` (completed relaxation bounds) and `full_policy_assessment` (an offline
  full-hazard assessment of routes found under reduced policies).
- `Provenance` gains optional `recorded_mission_match`.
- New 422 error codes are documented in `Error.code`.
- The `spread_zones` scope is documented: `input_time` must be a recorded input time, and the hazard horizon is 1 h.

## v1.2 — declare 503 on read endpoints (additive)

- `GET /regions` and `GET /regions/{region}/forecast` can return `503 DATA_UNAVAILABLE` when the recorded routing inputs
  are not installed (`python tools/fetch_routing_inputs.py`). `POST /route-checks` and `POST /dispatch-plans` already
  declared it. Found by the contract tests.

## v1.3 — provenance everywhere and documentation fixes (additive)

- `Error` responses and `GET /health` now include a `provenance` object, so every response carries provenance.
- KML and CSV exports carry provenance in the `X-WFG-Provenance` header. The CSV body is a plain table with no comment
  rows.
- `degraded` health also covers a missing `/usr/bin/time` or `/bin/ps`, which the kit controller needs.
- `burning_scenario_set_id` is documented as a consistency check. Burning cells always come from the recorded input at
  `input_time`.
- Documented error codes `GRID_MISMATCH`, `CHECKPOINT_MISMATCH` and `ZONE_PACKET_BUILD_FAILED`.
- `api_version` in provenance follows the contract version.

## v1.4 — safety tightening after review (additive fields, stricter dispatch)

- `POST /dispatch-plans` accepts only `policy: full`; anything else returns 422 `POLICY_NOT_ALLOWED`. Repeated
  `depart_offsets_s` return 422 `DUPLICATE_OFFSET`.
- `DispatchOriginPlan` gains `latest_contiguous_checked_depart_offset_s`. It is the last offset such that every
  requested offset from the earliest up to it has a checked route, and it is used for urgency ordering. The
  `latest_checked_depart_offset_s` field keeps its literal meaning.
- `run_independent_check` follows the frozen scorer: if the check was requested and did not complete, the result is
  unresolved (`CHECK_NOT_FINISHED`, raw reason `INDEPENDENT_CHECK_MISSING`).
- A reduced-policy route that contradicts its own policy's enabled constraints under the independent functions is
  unresolved (`CHECK_FAILED`), as in the ablation grader.
- `JobAccepted`, `RouteCheckJob` and `DispatchPlanJob` gain an optional `provenance` (inputs known at acceptance).
- Request bodies with non-finite numbers (NaN, Infinity) are rejected with 422.
- A dispatch plan may contain at most 4,800 attempts (origins × destinations × offsets); larger plans return 422
  `TOO_MANY_ATTEMPTS`. The contract's per-list limits are unchanged.

## v1.5 — robustness and spread_zones band rule (additive)

- New 503 codes. `BUSY` means too many checks are queued. `LAUNCHES_PAUSED` means a kit attempt's process cleanup was
  not confirmed CLEAN; new launches pause, as the frozen controller requires, until the API is restarted, and
  `/health` lists the issue.
- spread_zones bands: `H_prev` for a cell comes only from zones nested inside the zone that sets its band, so another
  fire's zones never shift it. The `max(0, H_prev − margin)` floor is applied on the `input_time` clock. This gives the
  same result when `issued_at <= input_time` and stays conservative when the product is issued later. Polygon edges are
  densified in lon/lat before projection. Assumptions now report `cells_igniting_within_horizon` and
  `zone_cells_outside_region_window`.
- Finished route-check records beyond the most recent 2,000 are served from their persisted `job.json`, so the
  response does not change.

## v1.6 — conservative spread_zones bands, job lifecycle, health fields

Behaviour changes:
- spread_zones `H_prev`. Zone j is nested in zone i when `H_j < H_i` and every cell of j is a cell of i. `H_prev` of
  zone i is now the smallest `H` over the **outermost** zones nested in i, i.e. those not nested in another zone nested
  in i. v1.5 used the largest `H` over all nested zones. Both rules give the same bands for concentric zones of one
  fire. v1.5 could raise a band's `H_prev`, which means a later and less conservative earliest ignition, when a zone of
  another fire lay inside the band. The v1.5 entry's "another fire's zones never shift it" held only for zones that are
  not nested. Under v1.6 such a zone can lower `H_prev` but never raise it.
- The adapter version is now `wfg.api.spread-zones-adapter/2`. `plan_sha256` also covers the adapter version and the
  resulting ignition times. The new `assumptions.ignition_times_sha256` and the packet's `zone_adapter` settings carry
  them as well, so a rule change yields new construction and scenario IDs. The assumptions now also state the
  densification step, the nesting test and the tie-break.
- `zones.features` accepts at most 200 zones.
- The kit's lifecycle rule now also covers a pool worker that dies while running a route check. That attempt never got
  the controller's cleanup, so new launches pause (503 `LAUNCHES_PAUSED`) until the API is restarted.
- Jobs that a previous server process left `queued` or `running` are recorded on start-up as `failed`, with `result:
  null` and the job error `SERVER_RESTARTED`. They are not resumed. `/health` reports them under `notices`.

Additive:
- `Health` declares the fields it already returned (`jobs`, `queued_tasks`, `budget_s`, `pool_restarts`,
  `kit_candidate_id`, `git_dirty`) and adds `notices`. Notices are informational and do not change `status`. A
  non-loopback bind address is also reported there.
- `recorded_mission_match` is documented precisely: it compares parsed JSON objects, not file bytes. Key order differs
  from the recorded file for 16 of the 20 missions.

Earlier versions, for clarity. No version removed or renamed a field. v1.4 tightened validation (dispatch `full` only,
duplicate offsets, attempt cap, non-finite numbers) and made an unfinished requested independent check `unresolved`.
v1.5 changed the band rule.

## v1.7 — spread_zones fires, launch-pause race, provenance commit

Behaviour changes:
- spread_zones takes an optional `fire_id` per zone. Zones with the same `fire_id`, or all zones without one, are one
  fire. Nesting is computed within a fire only.
- A zone cut off by the region grid or window edge is never nested, because its hidden part could lie outside the
  other zone. `assumptions.zones_cut_off_by_grid_edge` lists such zones.
- A cell's band is now (H_prev, H], where H_prev is the smallest prev over **all** zones touching the cell. v1.6 used
  only the zones with the cell's smallest H.
- With a distinct `fire_id` per fire, adding another fire's zones never makes any cell ignite later; a property test
  checks this. Without fire ids, a zone lying inside another zone of larger H is read as its inner band (the one-fire
  band rule).
- Correction to v1.6: its "can lower H_prev but never raise it" held only for a zone beside the band's existing inner
  zone. It did not hold for a band without an inner zone of its own, for a zone containing that inner zone, or for a
  zone cut off by the grid edge.
- The adapter version is now `wfg.api.spread-zones-adapter/3`, so the same zones give new scenario IDs.
- A route check queued behind an attempt that died or reported an unconfirmed cleanup no longer starts before the
  pause takes effect. The pause is now decided before the worker slot is freed, and the feeder checks again after
  taking a slot.
- Provenance `git_commit` now trusts `git rev-parse HEAD` only when the repository root is the top of its own git
  work tree. Otherwise it uses `WFG_API_GIT_COMMIT` or `unknown`, and `git_dirty` is null. This covers the v1.6
  precedence change too: the checkout's own commit wins over `WFG_API_GIT_COMMIT`.

Documentation only:
- More than 200 zones fails contract validation (422 `VALIDATION_ERROR`). The adapter's own `INVALID_ZONES` check is
  only a backstop.
- A `failed` job has either an `unresolved` result or `result: null` (`SERVER_RESTARTED`, or a failed dispatch plan).

## v1.8 — cut-off zones lower H_prev only, launch ordering

Behaviour changes:
- spread_zones (adapter `wfg.api.spread-zones-adapter/4`): in v1.7 a zone cut off by the grid or window edge was never
  nested. Excluding it could raise `prev(i)` when it was the smallest of i's outermost inner zones next to a whole one.
  A cut-off zone of the same fire whose visible cells all lie in i may or may not be one of i's inner bands, so
  `prev(i)` now takes the earlier reading: `prev(i) = min(prev from whole nested zones, H of each such cut-off zone)`.
  Such a zone can lower `prev(i)` but never raise it, and the result is never later than v1.6 or v1.7 for the same
  input. A zone of another fire (a different `fire_id`) is still never involved.
- Launch ordering: after taking a worker slot, the feeder first settles the pool. It waits for the executor to notice
  a dead worker, and rebuilding a broken pool waits for every failure callback, so each worker-death pause is set by
  then. The feeder then checks the pause before starting the job. It checks once more just before submitting, and a
  pause that landed in between fails that job as `unresolved` without launching it. With several workers, v1.7 could
  still start one queued check when a different task freed the slot.

Documentation only:
- A `fire_id` that is not a string of 1-100 characters (null included) fails contract validation with 422
  `VALIDATION_ERROR`, like more than 200 zones. The adapter's `INVALID_ZONES` check for both is only a backstop.
- `JobStatus.failed`: the result is an unresolved result or null (for example `SERVER_RESTARTED`). It is never safe.
- The v1.7 property test now builds concentric fires, so nested bands are exercised; it asserts a floor on such
  trials. It covers the `fire_id` and cell-`H_prev` rules. The cut-off rules are covered by their own tests.
