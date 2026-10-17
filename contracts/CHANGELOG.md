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
