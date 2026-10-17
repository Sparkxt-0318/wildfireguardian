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
