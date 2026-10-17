# Route-Check API: endpoint-to-code map

The API wraps the frozen research code and never re-implements it. Each endpoint below names the existing functions and
files it calls. Recorded inputs come from `tools/fetch_routing_inputs.py`. They live in `data/routing/` (git-ignored),
which is verified against `INPUT_FILES.json` and archive SHA-256 `d7e0a5fc…`.

## Found in Step 0

| Item | Location |
|---|---|
| Single-request entry point | `integration/src/wfg_latest/api.py:route_and_check` (job built from `integration/kit/queues/LATEST_PREFLIGHT_REAL.json`) → `integration/kit/runner/wfg_controller.py:run_attempt` → worker `integration/kit/phaseB/rda_worker_v1_1.py` (arm `RDA_CAND`) → `integration/kit/decision/journey_decision_v2_1.py:decision_from_worker_record` |
| Recorded risk inputs (scenario sets) | `data/routing/latest_inputs_try02/packets/<region>/<cutoff>/` holds `HAZARD.json` (`wfg.routing.edgegrid/1`, 4 members, per-interval flame and flux in kW/m², router rows south-up), `constructed_arrays.npz` (per-member `ignition_time_s`, `extinction_breakpoint_s`, `current_active`, masks; native north-up), `REPORT.json` and `NATIVE_METADATA.json` (construction assumptions, T = 3970.46 s, regional window) |
| Recorded requests (final panel) | `data/routing/latest_inputs_try02/requests/<region>/<cutoff>_<mission>.json`: 20 missions, 4 per region |
| Graph files | `data/routing/graphs/<region>/graph.json`: OSM nodes (EPSG:5179 x/y, `waitable`), directed edges (`u`, `v`, `travel_ticks`, cell `segments`), forbidden turns. There is no per-edge geometry. |
| Checkpoint c651 | Identity `c651f672…` in `docs/RELEASE_IDENTITY.json` and `integration/src/wfg_latest/contract.py:CHECKPOINT_SHA256`. The weights are not in Git; the forecast is never re-run by the API. |
| Recorded forecast outputs | `data/routing/latest_inputs_try02/exports/<KFS_xx>/FORECAST_<cutoff>.npz` + `FORECAST_RECORD_<cutoff>.json` (whole event grid, north-up; KFS_01 is shared by the two 2025 regions through windows) |
| Recorded results | `research/routing/INDEPENDENT_ROWS.csv`, `INDEPENDENT_RESULTS.json`, `FINAL_REVIEW.json`; ablation in `research/routing/final-input-ablation/data/ROWS.csv` |
| Policies | `research/routing/final-input-ablation/experiment_source/phaseB/{arm_transform.py, arm_check.py, ablation_worker.py}` (A0–A4) |

## Endpoints

| Endpoint | API code | Existing code it calls |
|---|---|---|
| `GET /v1/health` | `api/app.py:health`, `api/provenance.py:Identity` | `docs/RELEASE_IDENTITY.json`, `wfg_latest.__version__`, `wfg_latest.contract.CHECKPOINT_SHA256`, `integration/kit/CANDIDATE_MANIFEST.json`, `git rev-parse HEAD` |
| `GET /v1/regions` | `api/regions.py:Registry.load`, `GraphIndex.load`, `scenario_set_from_packet` | Reads `graph.json`, `HAZARD.json` and `NATIVE_METADATA.json` as data only. Scenario-set ID = member-ID prefix `ffb1:<cutoff>:<construction16>` (ID format from `wfg_latest/packets.py:write_regional_packet`). |
| `GET /v1/regions/{r}/forecast` | `api/forecast.py:forecast_collection` | Reads the recorded export npz (`new_burn_probability`, `probability_valid`). Windowed regions are cropped with `wfg_latest/packets.py:crop_forecast`. `burning_now` comes from the recorded packet's `current_active`. The record's `checkpoint_sha256` must equal c651. |
| `POST /v1/route-checks` (`policy=full`) | `api/app.py:create_route_check` → `api/jobs.py` (spawn process pool) → `api/runner.py:execute` | `wfg_latest.api.route_and_check(arm="RDA_CAND", budget_s=30, memory_guard_mib=3072)` → `wfg_controller.run_attempt` → `rda_worker_v1_1.py`. Then `journey_decision_v2_1.decision_from_worker_record` and `phaseB/publication_v1_1.py:route_of`. The optional independent check runs `integration/kit/runner/ffi_independent_checker.py`, the same command as `route_and_check(check=True)` but with its 120 s timeout handled. |
| `POST /v1/route-checks` (other policies) | `api/runner.py:run_ablation_attempt`, `ablation_kit`, `full_policy_assessment` | Builds an identity-checked copy of the study kit (`integration/kit` plus the three study files). Every file must match `research/routing/final-input-ablation/FREEZE.json`. Then: `arm_transform.arm_inputs`, `verify_transform`, `sentinel_sufficiency` → `wfg_controller.run_attempt` with job worker `phaseB/ablation_worker.py` (job layout of the study's `ABLATION.json`) → `decision_from_worker_record`. Full-hazard exposure comes from `ffi_independent_checker.grammar`, `centre_model` and `whole_road_contact`, as in `grade_route.py`. |
| `POST /v1/route-checks` (`spread_zones`) | `api/adapters/spread_zones.py:plan` and `build_packet` → `api/adapters/_zone_packet_child.py` | In a child interpreter: `wfg_latest/build_packet.py:install_radiation`, then `wfg_latest/packets.py:write_regional_packet` on the recorded c651 export, injecting ignition times at `bridge.draw_ignitions` (the hook `construct_regional` uses) and an adapter key at `bridge.settings_for`. Then the same route-check path as above. |
| `GET /v1/route-checks/{id}` | `api/jobs.py:JobManager.get` | n/a |
| `GET /v1/route-checks/{id}/export` | `api/exports.py` | n/a. Only `checked_route` results are exported. |
| `POST /v1/dispatch-plans` / `GET …/{id}` | `api/app.py:create_dispatch`, `api/dispatch.py` | One ordinary route check per (origin, destination, offset), as above. A spread_zones packet is built once and shared. |
| `GET /docs`, `/openapi.json` | `api/app.py`, `api/contract.py` | Serves `contracts/wfg_api_v1.yaml` and vendored Swagger UI 5.17.14 (`api/static/swagger-ui`). |

## Fixed rules

- **Verdict mapping** (`api/verdict.py`) mirrors the frozen scorer `integration/kit/runner/native_tally.py`.
  - Receipt-level failures win: memory guard → `MEMORY_CAP`; non-zero exit without a deadline → `WORKER_ERROR`; cleanup that is not CLEAN → `CLEANUP_UNCONFIRMED`; no publication → `WORKER_ERROR`.
  - `checked_route` requires one of the three `CHECKED_JOURNEY_*` statuses and `whole_road_check.status == CERTIFIED_ADMISSIBLE`. It must not be a road-only route (`ROAD_CERTIFIED_CENTRE_INFEASIBLE_ROUTE`). Whole-road contact must be `CLEAR` whenever flame contact is enforced.
  - `model_no_route` requires `FULL_MODEL_REFUSAL_PROVEN`.
  - Everything else is `unresolved`.
  - If the independent check was requested (`policy=full` only), the scorer's rules apply. Contradictions downgrade the verdict. A check that did not complete gives `CHECK_NOT_FINISHED` / `INDEPENDENT_CHECK_MISSING`, because the scorer never counts such a run as resolved. One difference, which makes the API stricter: a disputed optimum (`NOT_OPTIMAL_COUNTEREXAMPLE`) always stays `unresolved`, because the API never runs the scorer's offline whole-road witness (`native_tally.py` lines 91-109). By default no independent check runs, so a `checked_route` or `model_no_route` is the kit's own verdict without the corroboration the scorer would require.
  - **Reduced policies** (`travel_only`, `flame_*`): the route is re-assessed against the unchanged full hazard with the independent functions, as the ablation grader `grade_route.py` does. If it contradicts the selected policy's own enabled constraints, it is `unresolved/CHECK_FAILED`. `full_policy_assessment` always reports whether it would pass the full policy.
- **Dispatch plans** accept only `policy=full`. Urgency uses the conservative `latest_contiguous_checked_depart_offset_s`. The ordering follows the task: checked routes (earliest first), then `model_no_route`, then `unresolved`.
- **Request construction** (`api/requests_build.py`) reproduces the recorded request layout and constants: `objective`, `exposure_scope=including_dwell`, `limits{wall_s 30, max_labels 1e6, max_expansions 1e6, frontier_width 16384}`, `solver baseline`, `as_of = time_origin`, and `horizon = valid_until`. A body that restates a recorded mission yields that mission's request object exactly, compared as parsed JSON. Key order in the written `REQUEST.json` follows one fixed layout, so for 16 of the 20 recorded files it differs. Provenance `recorded_mission_match` names the matched mission.
- **Timing:** `compute_s` is the controller receipt's `external_launch_to_completion_wall_s`, the same clock and scope as the experiments. The independent check, the full-policy assessment and adapter packet building are reported separately under `provenance.timings_s`.
- **Caching:**
  - Graph indexes are read-only arrays and mapping proxies, re-validated by content hash on every access (`api/regions.py`).
  - SHA-256 results are cached by (size, mtime, inode) and rehashed on any change (`api/provenance.py:sha256_file`).
  - Forecast GeoJSON is cached per input hash.
  - The kit worker itself always runs `COLD_FAST`. The reviewed queues pin that mode, and the 30 s results were measured with it. The opt-in `AUTHENTICATED_ARTIFACT` cache is therefore not used.
- **Concurrency:** checks run only in spawn-context pool processes, because the controller uses `preexec_fn` and process groups. The default worker count is physical cores − 2. A feeder thread keeps at most `workers` tasks in flight and runs single route checks ahead of dispatch attempts.
- **Lifecycle (frozen controller rule):** no new kit launch after an attempt whose process cleanup was not confirmed. Two cases pause launches until a restart (503 `LAUNCHES_PAUSED`): a worker reports a cleanup that is not CLEAN, or a `route_check` task's future fails at the pool level, for example because the worker died (`api/jobs.py`). Jobs that a previous process left queued or running are recorded as `failed` (`SERVER_RESTARTED`) on start-up and are not resumed.

## Host requirements found while wrapping

- The controller needs `/usr/bin/time` (GNU `time -v` on Linux) and `/bin/ps`. `/v1/health` reports either one missing.
- The native macOS M5 Pro is the evaluated host. On slower hosts the fixed 30 s budget turns heavy missions into `unresolved/TIMEOUT`, for example Uljin FX1 at 38.6 s on a 2.1 GHz Xeon. The budget is never raised.
