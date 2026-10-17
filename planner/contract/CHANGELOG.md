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
