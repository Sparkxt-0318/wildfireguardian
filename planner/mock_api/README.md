# Route-Check API v1 — MOCK server

`planner/mock_api/server.py` is a Python standard-library HTTP server that implements every path of the
official contract [`planner/contract/wfg_api_v1.yaml`](../contract/wfg_api_v1.yaml) (**v1.5.0**) under
`http://127.0.0.1:8765/v1`. Use it to develop and demonstrate the village evacuation planner when the
real Route-Check API is not running. It never imports routing or forecasting code. It only reads the
recorded fixtures in `planner/mock_api/fixtures/`, which `planner/tools/build_fixtures.py` generates from
the verified release assets (ARCHITECTURE.md §4.1).

Error codes, the order of the request checks and the response layouts follow the real implementation
(`origin/feat/api`, `api/*.py`) wherever a mock can. The last section lists what still differs.

## Honesty rule (ARCHITECTURE.md §5.1)

The mock computes nothing. A request gets a **recorded result** only when all of these equal one recorded
execution in `fixtures/records/<region>/<case>__<policy>.json`:

- `region`
- `input_time`
- `fire_input.scenario_set_id`
- start node and destination node
- `depart_offset_s`
- `dwell_s`
- `destination_window` (if omitted: `[valid_from, horizon_s]`, i.e. `[0, 3600]`)
- `policy`
- `limits`
- `incurred_dose_kj_m2`

Every other request gets `verdict: "unresolved"`, `reason_code: "OTHER"` and
`raw_status: "MOCK_NO_RECORDED_RESULT"`. Its `raw_reason` names the closest recorded execution and the
fields that differ. `compute_s` is `null`, so `within_budget` is `false` (as the real API reports a null
compute time); `route` is `null` and `exposure` is `[]`.

Every `spread_zones` request is validated and then gets `unresolved` with
`raw_status: "MOCK_SPREAD_ZONES_NOT_EVALUATED"`. Its `assumptions` object says the zones were not
evaluated (`{"mock": true, "evaluated": false, "text": {ko, en}, "zones_received": n}`), and
`provenance.approximation` is `"approximation, requires expert review"`.

### Contract v1.4 rules applied to recorded results

The mock applies these rules exactly as the real API does, so a recorded verdict can be served as
`unresolved`:

- **`run_independent_check: true`** with policy `full`. The mock never runs the offline independent
  checker, so the requested check did not complete. As the frozen scorer requires, a recorded
  `checked_route` or `model_no_route` is served as `unresolved` with `reason_code: "CHECK_NOT_FINISHED"`
  and `raw_reason: "INDEPENDENT_CHECK_MISSING"`. `independent_check.status` is `"NOT_RUN_MOCK"`. With any
  other policy the checker is not defined: a note says so and the verdict is unchanged. **Send
  `run_independent_check: false` (the default) to replay a recorded result.**
- **A reduced-policy route that contradicts its own policy.** If the recorded full-hazard grade lists a
  failure that the policy itself enforces (for example flame contact under `flame_only`), the result is
  `unresolved` with `CHECK_FAILED` and `raw_reason: "INDEPENDENT_CONTRADICTION"`. No recorded fixture
  triggers this today; the synthetic tests cover it.

### What a recorded result carries

- `raw_status` is the kit's authoritative decision (`outcome.authoritative_decision`, for example
  `CHECKED_JOURNEY_FULL_OPTIMUM_PROVEN` or `FULL_MODEL_REFUSAL_PROVEN`), as the real API reports it.
  `raw_reason` is `null` for `checked_route` and `model_no_route`. The recorded RESULT.json primary status
  and reason are kept in `provenance.recorded_execution.raw_primary_status` / `raw_primary_reason` and in
  a note.
- `compute_s` is the recorded complete-request wall time on the native Apple M5 Pro campaign host.
- `provenance.host = {"recorded": true, "machine": "Apple M5 Pro", "os": "macOS (native)"}`, plus
  `provenance.clock` and the record's `input_hashes`.
- `provenance.recorded_mission_match` is the mission (case) id whenever the request restates a recorded
  mission. This holds for **every policy**, because all policies share the mission's request, as in the
  real API.
- `provenance.evaluated_configuration` follows the real API's definition: recorded input, policy `full`,
  and the default limits or a recorded mission request. It describes the configuration, so an unmatched
  `full` request with default limits also reports `true`; `host.recorded: false` and the verdict show that
  nothing was computed.
- `notes[0]` is `"MOCK: recorded result of case <case_id> (<source_arm> rep <n>) served without
  recomputation"`. The last note is the real API's standard sentence for `model_no_route` and
  `unresolved`.
- **Routes use the real API's vertex layout** (`api/runner.py route_feature`):
  - the vertices are the origin, one per EDGE leg end, and one at the end of each run of consecutive WAIT
    legs;
  - `node_ids` has one entry per vertex;
  - `segment_count` counts EDGE legs and `legs_total` counts all legs.

  The fixture stores one vertex per 1 s WAIT leg, so only those intermediate wait vertices are dropped.
  Positions and times are the recorded ones. For the recorded mission `20250324T090000Z_FL2`, the real API
  returned the same `node_ids`, `times_s`, `edge_ids`, arrival, L and dwell end as the fixture.
- `exposure` for `full`: the recorded centre-model values with `basis: "centre_model"`. The fixture does
  not record the whole-road upper bounds, so `peak_upper_kw_m2` and `dose_upper_kj_m2` are `null`.
- For the ablation policies (`travel_only`, `flame_only`, `flame_peak`, `flame_dose`):
  - `exposure` is the recorded **full-hazard** check of the route, with `basis:
    "full_model_centre_check"`; `contact` may be `true`.
  - `full_policy_assessment` has the real API's keys: `passes_full_centre_and_contact`, `whole_road_contact`,
    `violations` (`[{scenario_id, constraint}]`), `per_scenario`, `scope` and `passes_selected_policy`.
    These come from the recorded ablation dual-policy grade. `grammar_ok` was not recorded, so it is
    `null`.
  - `full_policy_assessment` also keeps the record's own `pass`, `failure_components`, `source` and
    `policy_exposure`.

`/health` reports `"mode": "mock"` and `"mock": true`. Every provenance block carries `"mock": true`. Every
response has the header `X-WFG-Mock: 1`. The real API has none of these markers, which is how the planner
tells the two apart.

## Run

```bash
python3 planner/mock_api/server.py                      # http://127.0.0.1:8765/v1
python3 planner/mock_api/server.py --port 9000 --quiet  # other port, no per-request log lines
python3 planner/mock_api/server.py --fixtures /path/to/fixtures
```

- It needs Python ≥ 3.11 and nothing else.
- It logs one line per request to stderr.
- It stops cleanly on Ctrl-C (SIGINT) or SIGTERM.
- Fixtures and code are loaded once at start-up. **Restart the server after updating `server.py` or
  regenerating fixtures.**
- If fixtures are missing or inconsistent, `/health` reports `status: "degraded"` and lists `issues`. The
  server keeps running. A record whose endpoint the node table does not allow is also an issue, because its
  request could never be posed.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/v1` | index of endpoints (mock only); the contract copy is served at `/openapi.yaml` |
| GET | `/v1/health` | `Health` with `provenance` (v1.3), plus `mode`, `mock`, `fixtures`, `jobs`, `queued_tasks: 0`, `budget_s`, `kit_candidate_id` (from the recorded source paths) |
| GET | `/v1/regions` | `fixtures/regions.json` sorted by id, plus each region's `recorded_missions` (as the real API); 503 `DATA_UNAVAILABLE` without fixtures (v1.2) |
| GET | `/v1/regions/{region}/forecast?input_time=&only_nonzero=` | `fixtures/forecast/<region>/<YYYYMMDDTHH0000Z>.json`; see Forecast |
| POST | `/v1/route-checks` | `RouteCheckRequest` → 202 `JobAccepted` with the snap pair and `provenance` (v1.4) |
| GET | `/v1/route-checks/{job_id}` | `RouteCheckJob` with `provenance`; `result` only when `status == "done"` |
| GET | `/v1/route-checks/{job_id}/export?format=geojson\|kml\|csv` | only for a done `checked_route` (409 `JOB_NOT_DONE` / `NO_CHECKED_ROUTE` otherwise) |
| POST | `/v1/dispatch-plans` | `DispatchPlanRequest` → 202 `JobAccepted` with `provenance` |
| GET | `/v1/dispatch-plans/{job_id}` | `DispatchPlanJob` with `progress`, `provenance` and, when done, `DispatchPlanResult` |

All endpoints send CORS headers (`Access-Control-Allow-Origin: *`; `Access-Control-Expose-Headers`
includes `X-WFG-Provenance`) and answer `OPTIONS` preflight with 204.

Every error is `{"error": {"code", "message", "details"}, "provenance": {...}}`, with provenance as of
contract v1.3.

**Snapping.**

- A `{node_id}` must be in `fixtures/nodes/<region>.json`; otherwise the request fails with 422
  `UNKNOWN_NODE`.
- The node must also be allowed; otherwise it fails with `NODE_NOT_ALLOWED` ("needs at least one incoming
  and one outgoing road").
- The allowed rule is the real API's (`api/regions.py`): the node has at least one incoming and one
  outgoing road edge. There is no exception for recorded endpoints, and every recorded mission endpoint
  satisfies the rule. The allowed counts equal the real API's `allowed_node_count` in all five regions.
- The node table also lists `not_in_largest_scc`. The planner's entry points are the nearest nodes of the
  largest strongly connected component (ARCHITECTURE.md §4.2). An allowed node outside that component may
  be unreachable (`DISCONNECTED`).

A `{lon, lat}` snaps to the nearest allowed node by haversine distance. The real API measures in
EPSG:5179; the difference is far below a metre. A snap farther than 300 m fails with 422 `SNAP_TOO_FAR`,
and `details` give `distance_m`, `nearest_node_id` and `limit_m`.

**Validation.** Request bodies are checked against a stdlib mirror of the contract's request schemas
(`REQUEST_SCHEMAS` in `server.py`). The tests assert that the mirror equals the contract. The checks run in
the real API's order: JSON and schema, data (503), region, input time, fire input, snaps, then the request
checks.

| Code | When |
|---|---|
| `VALIDATION_ERROR` | the body is not JSON or does not match the schema, `details = [{path, message}]`; non-finite numbers (`NaN`, `Infinity`, `1e999`) (v1.4); more than 200 origins (the schema's `maxItems` catches it first, as in the real API); a bad query parameter, with the real API's FastAPI layout `details = [{type, loc, msg, input}]` |
| `UNKNOWN_REGION` | the region is not in the fixtures (404 on the forecast path) |
| `INVALID_INPUT_TIME` | `input_time` cannot be parsed, has no time zone, or is not a whole UTC hour |
| `INPUT_TIME_UNAVAILABLE` | no scenario set is recorded at that time; `details.available` lists the recorded times. This also covers `spread_zones`, whose `input_time` must be a recorded input time of the region (v1.1) |
| `UNKNOWN_SCENARIO_SET` | the scenario set is not recorded for the region |
| `SCENARIO_SET_TIME_MISMATCH` | the scenario set belongs to another input time, or `burning_scenario_set_id` is not the recorded set at `input_time` (v1.3: it is only a consistency check) |
| `UNKNOWN_NODE`, `NODE_NOT_ALLOWED`, `SNAP_TOO_FAR` | see Snapping |
| `NOT_ON_TIME_LATTICE` | not a whole second (this includes `depart_offsets_s`) |
| `DEPARTURE_OUTSIDE_HORIZON` | not within `[0, horizon_s]` |
| `INVALID_WINDOW` | not `0 ≤ open < close ≤ horizon` |
| `START_EQUALS_DESTINATION` | start and destination are the same node |
| `WINDOW_UNSATISFIABLE` | `max(depart, open) + dwell > close` |
| `INVALID_ZONES`, `ZONES_OUTSIDE_REGION` | a zone is malformed, or lies entirely outside the region bbox; an empty `features` list is accepted, as in the real adapter |
| `DUPLICATE_ID` | two origins or two destinations share an id |
| `POLICY_NOT_ALLOWED` | a dispatch plan with a policy other than `full` (v1.4) |
| `DUPLICATE_OFFSET` | a dispatch plan repeats a departure offset (v1.4) |
| `TOO_MANY_ATTEMPTS` | origins × destinations × offsets > 4,800; rejected origins do not count (v1.4) |
| `DATA_UNAVAILABLE` (503) | no fixtures are loaded (`/regions`, forecast, `POST /route-checks`, `POST /dispatch-plans`), or a region's node table is missing |

The mock never returns 503 `BUSY` or `LAUNCHES_PAUSED` (v1.5), because it runs nothing.

**Jobs.** A job's status follows the time since it was created: `queued` for the first 0.15 s, `running`
until 0.6 s, then `done`. No thread sleeps. `started_at` and `finished_at` are these mock state-transition
times. They are not compute times; `compute_s` is always the recorded value or `null`.

**Dispatch plans.** Every origin × destination × offset becomes one attempt. The offsets are kept in the
requested order and must not repeat.

- Each attempt is a normal route-check job (`route_check_job_id`, `parent_job_id`), so
  `GET /v1/route-checks/{id}` returns its full result. The job's `request` is a valid
  `RouteCheckRequest`.
- A combination the real API cannot pose (for example an unsatisfiable window or an offset past the
  horizon) becomes an `unresolved` attempt without a job, with `reason_code: "INPUT_REJECTED"` and the
  request error code as `raw_reason` (for example `WINDOW_UNSATISFIABLE`).
- `best_verdict` per origin:
  - `checked_route` if any attempt is checked;
  - `model_no_route` only if every attempt is `model_no_route`;
  - `unresolved` otherwise.
- `latest_checked_depart_offset_s` is the latest offset with a checked route. `best` is the
  earliest-arrival attempt at that offset.
- `latest_contiguous_checked_depart_offset_s` (v1.4) is the last offset such that every requested offset
  from the earliest up to it has a checked route.
- Plans are sorted by urgency and get `urgency_rank` 1…n:
  1. checked origins, by the contiguous offset; an origin whose earliest offset has no checked route
     comes first;
  2. then `model_no_route`;
  3. then `unresolved`.
- `summary.checked_route`, `model_no_route` and `unresolved` count **origins** by best verdict.
  `summary.attempt_verdicts` counts **attempts**.
- `median_compute_s` is computed over recorded (non-null) values only. `wall_s` is `null`.
- `provenance.evaluated_configuration` is `true` for recorded input with default limits.
- Origins that fail snapping go to `rejected_origins` with their error. The rest of the plan is still
  computed.
- `progress.done` counts finished attempts, including INPUT_REJECTED ones from the start, and rises
  during `running`.

**Forecast.**

- `input_time` accepts ISO (`2025-03-24T09:00:00Z`) or compact (`20250324T090000Z`) form.
- `only_nonzero` parses like FastAPI's bool (`true/false/1/0/yes/no/on/off/t/f/y/n`). With `true`, it keeps
  cells with `p_new_burn_1h > 0` or `burning_now`.
- Query parameters are checked first, then data availability, the region (404), the input time and
  whether it is recorded (404).
- Rows are numbered **north-up** (row 0 is the northern edge) and `id` is `r<row>c<col>`, as in the real
  API. The fixture numbers rows from the south (graph cell convention). `properties.cell` keeps the graph
  cell index.
- A `grid` block (`crs`, `resolution_m`, `rows`, `cols`, `affine_transform`, `row_order`) is added from
  `regions.json`.

The same cells, polygons and values were compared against the real API for 홍성 2023-04-02T07:00Z.

**Exports.**

- `geojson`: a `RouteExportCollection` with the route (role `route`), the `start` and `destination`
  points, and provenance. Every feature carries `label`, `full_policy_route` and
  `full_policy_centre_and_contact_pass`.
- `kml`: KML 2.2 with a LineString and Placemarks. `ExtendedData` holds the verdict, times and provenance,
  and the document name contains `MOCK`. A reduced-policy route is labelled "route checked under policy …
  only (NOT a full-policy route)", never "checked route".
- `csv`: a plain table with header `seq,node_id,lon,lat,time_s,event`. There is one row per vertex
  (`depart`, `pass`, `wait_end`, `arrive`) and a final `dwell_end` row, as in the real API.
- KML and CSV carry compact provenance JSON in the `X-WFG-Provenance` header (v1.3).

## Examples

These examples use the recorded mission `20250324T090000Z_FL2` in 의성·안동, which has a recorded
`checked_route`. If an HTTP proxy is configured in your shell, add `--noproxy 127.0.0.1` to each `curl`.

```bash
B=http://127.0.0.1:8765/v1
curl -s $B/health
curl -s $B/regions
curl -s "$B/regions/uiseong_andong_2025/forecast?input_time=20250324T090000Z&only_nonzero=true"

# exact restatement of the recorded mission -> recorded checked_route (defaults: depart 0, dwell 120,
# window [0, 3600], policy full, limits 10 / 100, incurred 0, run_independent_check false)
curl -s -X POST $B/route-checks -H 'Content-Type: application/json' -d '{
  "region": "uiseong_andong_2025", "input_time": "2025-03-24T09:00:00Z",
  "start": {"node_id": "osm:7836400838"}, "destination": {"node_id": "osm:365846317"},
  "fire_input": {"type": "recorded", "scenario_set_id": "ffb1:20250324T090000Z:08721049cc48e045"}}'
curl -s $B/route-checks/<job_id>                      # queued -> running -> done within ~0.6 s
curl -s "$B/route-checks/<job_id>/export?format=csv"

# travel-time-only comparison route (recorded ablation A0 of the same mission; it fails the full policy)
curl -s -X POST $B/route-checks -H 'Content-Type: application/json' -d '{
  "region": "uiseong_andong_2025", "input_time": "2025-03-24T09:00:00Z", "policy": "travel_only",
  "start": {"node_id": "osm:7836400838"}, "destination": {"node_id": "osm:365846317"},
  "fire_input": {"type": "recorded", "scenario_set_id": "ffb1:20250324T090000Z:08721049cc48e045"}}'

# anything else (here: departing 10 min later) -> unresolved / MOCK_NO_RECORDED_RESULT
curl -s -X POST $B/route-checks -H 'Content-Type: application/json' -d '{
  "region": "uiseong_andong_2025", "input_time": "2025-03-24T09:00:00Z", "depart_offset_s": 600,
  "start": {"node_id": "osm:7836400838"}, "destination": {"node_id": "osm:365846317"},
  "fire_input": {"type": "recorded", "scenario_set_id": "ffb1:20250324T090000Z:08721049cc48e045"}}'

# dispatch plan: one origin x one shelter x two offsets (policy full only)
curl -s -X POST $B/dispatch-plans -H 'Content-Type: application/json' -d '{
  "region": "uiseong_andong_2025", "input_time": "2025-03-24T09:00:00Z",
  "fire_input": {"type": "recorded", "scenario_set_id": "ffb1:20250324T090000Z:08721049cc48e045"},
  "origins": [{"id": "research-origin", "location": {"node_id": "osm:7836400838"}}],
  "destinations": [{"id": "research-destination", "location": {"node_id": "osm:365846317"}}],
  "depart_offsets_s": [0, 600]}'
curl -s $B/dispatch-plans/<job_id>
```

## Differences from the real API that remain

These are data that the fixtures do not record, or behaviour that a mock cannot have. The mock leaves the
field out or sets it to `null`; it never invents a value.

- **Never computed:**
  - unmatched requests and every `spread_zones` request are `unresolved`;
  - the independent checker never runs;
  - `BUSY`/`LAUNCHES_PAUSED` never occur;
  - `ZONES_OUTSIDE_REGION` is judged on the region bbox, not on the rasterised grid.
- **Not in the fixtures:**
  - `lower_bounds`;
  - `route.properties.route_sha256` and `published_stage`;
  - the whole-road upper bounds (`null`);
  - `full_policy_assessment.grammar_ok` (`null`);
  - packet and policy input hashes;
  - `provenance.timings_s` and `receipt`;
  - the forecast `grid.event_window`.
- **Values that legitimately differ:**
  - `compute_s` is the recorded M5 Pro time;
  - route coordinates have 6 decimals, not 7;
  - `host` describes the recorded host or "nothing computed";
  - job timestamps are mock state transitions.
- **Real API behaviour the mock does not copy.** A body with an overflowing number such as `1e999` makes
  the real API (feat/api `bb2acd0`) answer **500** `INTERNAL_ERROR`, because it cannot serialise the
  infinite value in its error details. Contract v1.4 requires 422, and the mock answers 422.

## Tests

```bash
python3 -m pytest tests/planner/test_mock_api.py tests/planner/test_mock_fetch_contract.py -q
```

These tests need `pytest`, `jsonschema`, `referencing` and `PyYAML`; the server itself uses none of them.
They start the server in-process on an ephemeral port and validate every response body against the
contract's component schemas.

They run against two fixture sets:

- **A synthetic `test:` fixture tree.** It covers:
  - every endpoint, the validation errors and snapping;
  - the state machine and the matching edge cases;
  - the v1.4 independent-check and own-policy rules;
  - dispatch aggregation with contiguous urgency and the attempt limit;
  - exports and the served-route vertex rule.
- **The real fixtures, when `fixtures/MANIFEST.json` exists.**
  - All 20 final-panel missions replay their recorded verdicts (15 `checked_route`, 5 `model_no_route`),
    and so do the 80 ablation records.
  - The node tables follow the API's allowed rule.
  - The forecast rows are north-up.

## When the contract changes

`planner/scripts/fetch_contract.sh` refreshes `planner/contract/`; see
[`planner/contract/README.md`](../contract/README.md). When `CHANGELOG.md` gains a version, update the
following in `server.py`:

- `API_VERSION`;
- the `REQUEST_SCHEMAS` mirror;
- `REASON_CODES`;
- any new response fields and error codes. Compare them with the real implementation in `api/*.py` on
  `feat/api`.

Then run the tests. `test_request_schemas_mirror_contract` fails until the mirror matches the contract
again.
