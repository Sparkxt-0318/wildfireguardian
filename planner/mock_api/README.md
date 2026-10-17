# Route-Check API v1 — MOCK server

`planner/mock_api/server.py` is a Python standard-library HTTP server that implements every path of the
official contract [`planner/contract/wfg_api_v1.yaml`](../contract/wfg_api_v1.yaml) under
`http://127.0.0.1:8765/v1`. Use it to develop and demonstrate the village evacuation planner when the
real Route-Check API is not running. It never imports routing or forecasting code. It only reads the
recorded fixtures in `planner/mock_api/fixtures/`, which `planner/tools/build_fixtures.py` generates from
the verified release assets (ARCHITECTURE.md §4.1).

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
fields that differ. `compute_s` is `null`, `route` is `null` and `exposure` is `[]`.

Every `spread_zones` request is validated and then gets `unresolved` with
`raw_status: "MOCK_SPREAD_ZONES_NOT_EVALUATED"`. Its `assumptions` object says the zones were not
evaluated (`{"mock": true, "evaluated": false, "text": {ko, en}, "zones_received": n}`), and
`provenance.approximation` is `"approximation, requires expert review"`.

What a recorded result carries:

- the recorded `compute_s`: the complete-request wall time on the native Apple M5 Pro campaign host;
- `provenance.host = {"recorded": true, "machine": "Apple M5 Pro", "os": "macOS (native)"}`;
- `provenance.clock`;
- the record's `input_hashes`;
- `evaluated_configuration: true` only for the `full` policy;
- `notes[0] = "MOCK: recorded result of case <case_id> (<source_arm> rep <n>) served without recomputation"`.

For the ablation policies (`travel_only`, `flame_only`, `flame_peak`, `flame_dose`), these policies do not
enforce the full hazard. So `exposure` is the recorded **full-hazard** check of the route (`basis:
"full_model_centre_check"`, and `contact` may be `true`). The policy's own values and the recorded
full-policy pass or fail are in `full_policy_assessment`. These are additive fields that contract v1.1
also defines.

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
- Fixtures are loaded once at start-up. Restart the server after regenerating them.
- If fixtures are missing or inconsistent, `/health` reports `status: "degraded"` and lists `issues`. The
  server keeps running.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/v1` | index of endpoints (mock only); the contract copy is served at `/openapi.yaml` |
| GET | `/v1/health` | `Health` + `mode`, `mock`, `fixtures`, `jobs`, `budget_s` |
| GET | `/v1/regions` | `fixtures/regions.json` (`RegionList`, provenance gets `mock: true`) |
| GET | `/v1/regions/{region}/forecast?input_time=&only_nonzero=` | `fixtures/forecast/<region>/<YYYYMMDDTHH0000Z>.json`; `input_time` accepts ISO (`2025-03-24T09:00:00Z`) or compact (`20250324T090000Z`); `only_nonzero=true` keeps cells with `p_new_burn_1h > 0` or `burning_now` |
| POST | `/v1/route-checks` | `RouteCheckRequest` → 202 `JobAccepted` with the snap pair |
| GET | `/v1/route-checks/{job_id}` | `RouteCheckJob`; `result` only when `status == "done"` |
| GET | `/v1/route-checks/{job_id}/export?format=geojson\|kml\|csv` | only for a done `checked_route` (409 `JOB_NOT_DONE` / `NO_CHECKED_ROUTE` otherwise) |
| POST | `/v1/dispatch-plans` | `DispatchPlanRequest` → 202 `JobAccepted` |
| GET | `/v1/dispatch-plans/{job_id}` | `DispatchPlanJob` with `progress` and, when done, `DispatchPlanResult` |

All endpoints send CORS headers (`Access-Control-Allow-Origin: *`) and answer `OPTIONS` preflight with 204.
Every error is `{"error": {"code", "message", "details"}}`.

**Snapping.** A `{node_id}` must be in `fixtures/nodes/<region>.json`, or the request fails with 422
`UNKNOWN_NODE`. The node must also be allowed, or the request fails with `NODE_NOT_ALLOWED`. The mock's
allowed rule is the largest strongly connected component. Recorded mission endpoints are always accepted
by `node_id`, so every recorded mission replays.

A `{lon, lat}` snaps to the nearest allowed node by haversine distance. The real API measures in
EPSG:5179; the difference is far below a metre. A snap farther than 300 m fails with 422 `SNAP_TOO_FAR`,
and `details` give `distance_m`, `nearest_node_id` and `limit_m`.

**Validation.** Request bodies are checked against a stdlib mirror of the contract's request schemas
(`REQUEST_SCHEMAS` in `server.py`). The tests assert that the mirror equals the contract. These errors
mirror the real API's checks:

| Code | When |
|---|---|
| `VALIDATION_ERROR` | the body does not match the schema; `details` = `[{path, message}]` |
| `UNKNOWN_REGION` | the region is not in the fixtures |
| `INVALID_INPUT_TIME` | `input_time` cannot be parsed, has no time zone, or is not a whole UTC hour |
| `INPUT_TIME_UNAVAILABLE` | no scenario set is recorded at that time; `details.available` lists the recorded times |
| `UNKNOWN_SCENARIO_SET` | the scenario set is not recorded for the region |
| `SCENARIO_SET_TIME_MISMATCH` | the scenario set belongs to another input time |
| `UNKNOWN_NODE`, `NODE_NOT_ALLOWED`, `SNAP_TOO_FAR` | see Snapping |
| `NOT_ON_TIME_LATTICE` | not a whole second |
| `DEPARTURE_OUTSIDE_HORIZON` | not within `[0, horizon_s]` |
| `INVALID_WINDOW` | not `0 ≤ open < close ≤ horizon` |
| `START_EQUALS_DESTINATION` | start and destination are the same node |
| `WINDOW_UNSATISFIABLE` | `max(depart, open) + dwell > close` |
| `INVALID_ZONES`, `ZONES_OUTSIDE_REGION` | a zone is malformed, or lies entirely outside the region bbox |
| `TOO_MANY_ORIGINS` | more than 200 origins |
| `DUPLICATE_ID` | two origins or two destinations share an id |
| `DATA_UNAVAILABLE` (503) | the fixtures for that region are not loaded |

`spread_zones` additionally requires `input_time` to be a recorded input time of the region.

**Jobs.** A job's status follows the time since it was created: `queued` for the first 0.15 s, `running`
until 0.6 s, then `done`. No thread sleeps. `started_at` and `finished_at` are these mock state-transition
times. They are not compute times; `compute_s` is always the recorded value or `null`.

**Dispatch plans.** Every origin × destination × offset becomes one attempt. Offsets are de-duplicated and
sorted.

- Each attempt is a normal route-check job (`route_check_job_id`, `parent_job_id`), so
  `GET /v1/route-checks/{id}` returns its full result.
- A combination that the real API would reject becomes an `unresolved` attempt with
  `raw_status: "INPUT_REJECTED"` and no job, for example an unsatisfiable window.
- `best_verdict` per origin:
  - `checked_route` if any attempt is checked;
  - `model_no_route` only if every attempt is `model_no_route`;
  - `unresolved` otherwise.
- `latest_checked_depart_offset_s` is the latest offset with a checked route. `best` is the
  earliest-arrival attempt at that offset.
- Plans are sorted by urgency and get `urgency_rank` 1…n:
  1. checked origins, earliest latest-safe offset first;
  2. then `model_no_route`;
  3. then `unresolved`.
- `summary.checked_route`, `model_no_route` and `unresolved` count **origins** by best verdict.
  `summary.attempt_verdicts` counts **attempts**.
- `median_compute_s` is computed over recorded (non-null) values only. `wall_s` is `null`.
- Origins that fail snapping go to `rejected_origins` with their error. The rest of the plan is still
  computed.
- `progress.done` counts finished attempts and rises during `running`.

**Exports.**

- `geojson`: a `RouteExportCollection` with the route plus origin and destination points, and provenance.
- `kml`: KML 2.2 with a LineString and Placemarks. `ExtendedData` holds the verdict, times and provenance,
  and the document name contains `MOCK`.
- `csv`: header `seq,node_id,lon,lat,time_s,event`, where `event` is `depart|edge|wait|arrive`.

## Examples

These examples use the recorded mission `20250324T090000Z_FL2` in 의성·안동, which has a recorded
`checked_route`. If an HTTP proxy is configured in your shell, add `--noproxy 127.0.0.1` to each `curl`.

```bash
B=http://127.0.0.1:8765/v1
curl -s $B/health
curl -s $B/regions
curl -s "$B/regions/uiseong_andong_2025/forecast?input_time=20250324T090000Z&only_nonzero=true"

# exact restatement of the recorded mission -> recorded checked_route (defaults: depart 0, dwell 120,
# window [0, 3600], policy full, limits 10 / 100, incurred 0)
curl -s -X POST $B/route-checks -H 'Content-Type: application/json' -d '{
  "region": "uiseong_andong_2025", "input_time": "2025-03-24T09:00:00Z",
  "start": {"node_id": "osm:7836400838"}, "destination": {"node_id": "osm:365846317"},
  "fire_input": {"type": "recorded", "scenario_set_id": "ffb1:20250324T090000Z:08721049cc48e045"}}'
curl -s $B/route-checks/<job_id>                      # queued -> running -> done within ~0.6 s
curl -s "$B/route-checks/<job_id>/export?format=csv"

# travel-time-only comparison route (recorded ablation A0 of the same mission)
curl -s -X POST $B/route-checks -H 'Content-Type: application/json' -d '{
  "region": "uiseong_andong_2025", "input_time": "2025-03-24T09:00:00Z", "policy": "travel_only",
  "start": {"node_id": "osm:7836400838"}, "destination": {"node_id": "osm:365846317"},
  "fire_input": {"type": "recorded", "scenario_set_id": "ffb1:20250324T090000Z:08721049cc48e045"}}'

# anything else (here: departing 10 min later) -> unresolved / MOCK_NO_RECORDED_RESULT
curl -s -X POST $B/route-checks -H 'Content-Type: application/json' -d '{
  "region": "uiseong_andong_2025", "input_time": "2025-03-24T09:00:00Z", "depart_offset_s": 600,
  "start": {"node_id": "osm:7836400838"}, "destination": {"node_id": "osm:365846317"},
  "fire_input": {"type": "recorded", "scenario_set_id": "ffb1:20250324T090000Z:08721049cc48e045"}}'

# dispatch plan: one origin x one shelter x two offsets
curl -s -X POST $B/dispatch-plans -H 'Content-Type: application/json' -d '{
  "region": "uiseong_andong_2025", "input_time": "2025-03-24T09:00:00Z",
  "fire_input": {"type": "recorded", "scenario_set_id": "ffb1:20250324T090000Z:08721049cc48e045"},
  "origins": [{"id": "research-origin", "location": {"node_id": "osm:7836400838"}}],
  "destinations": [{"id": "research-destination", "location": {"node_id": "osm:365846317"}}],
  "depart_offsets_s": [0, 600]}'
curl -s $B/dispatch-plans/<job_id>
```

## Tests

```bash
python3 -m pytest tests/planner/test_mock_api.py -q
```

These tests need `pytest`, `jsonschema`, `referencing` and `PyYAML`; the server itself uses none of them.
They start the server in-process on an ephemeral port and validate every response body against the
contract's component schemas.

They run against two fixture sets:

- **A synthetic `test:` fixture tree.** It covers every endpoint, the validation errors, snapping, the
  state machine, the matching edge cases, dispatch aggregation and exports.
- **The real fixtures, when `fixtures/MANIFEST.json` exists.** All 20 final-panel missions replay their
  recorded verdicts (15 `checked_route`, 5 `model_no_route`), and so do the 80 ablation records.

## When the contract changes

`planner/scripts/fetch_contract.sh` refreshes `planner/contract/`; see
[`planner/contract/README.md`](../contract/README.md). When `CHANGELOG.md` gains a version, update the
following in `server.py`:

- `API_VERSION`;
- the `REQUEST_SCHEMAS` mirror;
- `REASON_CODES`;
- any new response fields.

Then run the tests. `test_request_schemas_mirror_contract` fails until the mirror matches the contract
again.
