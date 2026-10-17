# WildfireGuardian 마을별 사전 대피계획 도구 — architecture and build contract

This is the working contract for everyone building `planner/`. It fixes directory ownership,
data formats, how the planner uses the official Route-Check API contract
(`planner/contract/wfg_api_v1.yaml`) and the honesty rules. If the contract changes, only
`planner/src/api/` (wire types, client, adapter) and the mock server change; the UI's internal
model (§6) stays stable.

## 0. Non-negotiable rules

1. Never modify anything outside `planner/`, `tests/planner/` and the root `.gitignore`.
   Do not touch forecasting, routing, checking code, thresholds or recorded results.
2. Never import routing or forecasting code (`wfg_latest`, `integration/`, `routing-*`, `forecast/`).
   The app talks only to the Route-Check API over HTTP (`http://127.0.0.1:8765/v1`).
3. Never invent villages, shelters, routes, fires or numbers. Every point carries its source tag;
   every route and number carries provenance. The mock serves only real recorded results.
4. Three result states only: `checked_route` (green, check icon, "확인된 경로"),
   `model_no_route` (black, slashed-circle icon, "모델상 경로 없음"),
   `unresolved` (mid-grey, question icon, "미확인"). Unresolved is never shown as safe,
   never coloured green and never counted toward a departure deadline.
5. Every screen states the fire input in a visible banner:
   - recorded scenario: `"{fire_year}년 실제 산불 기록 기반 시나리오 재현"` (2025 regions → "2025년 실제 산불 기록 기반 시나리오 재현")
   - drawn zones: `"사용자 입력 확산 구역 (가정)"`
   - any data from the mock server additionally shows a `MOCK` badge.
6. Footer on every screen: "사전 계획 보조 도구입니다. 실시간 대피 지휘·운영용이 아닙니다." /
   "Planning aid only — not for live evacuation operations."
7. No secrets in Git. `.env` is ignored; `planner/.env.example` documents keys.
   No forecasting weights, no raw environmental rasters, no personal data, no file > 50 MB.
8. Agents do not run `git commit`/`git push`; the coordinator commits.

## 1. Fixed facts (do not change)

- Forecast checkpoint c651 (`c651f6724fe6b036b0162edf264cb0063c061b80c2c936d48965ee66afbd1843`),
  next-hour new-burn probability, 375 m cells, EPSG:5179.
- Routing package `wfg_latest` 1.0.0, executed kit v3. Evaluated arm used by the API: `RDA_CAND`.
- Regions (real OSM road graphs): `uljin_2022` 울진, `miryang_2022` 밀양, `hongseong_2023` 홍성,
  `uiseong_andong_2025` 의성·안동, `yeongdeok_2025` 영덕. Demo regions: 의성·안동, 영덕
  (both KFS_01, Gyeongbuk March 2025 fire group).
- Each check uses one scenario set of 4 members (`ffb1:<input>:<construction>:0..3`).
  Recorded scenario window: 0–3600 s after the input time (`valid_from`/`valid_until`).
- About 8 s median per check on an Apple M5 Pro (recorded native benchmark).

## 2. Directory ownership

| Path | Owner | Contents |
|---|---|---|
| `planner/package.json`, `vite.config.ts`, `tsconfig*.json`, `index.html`, `src/**` | frontend | Vite + React + TS + MapLibre app |
| `tests/planner/*.test.ts` | frontend | Vitest unit tests (config `include` points here) |
| `planner/tools/*.py`, `planner/scripts/fetch_planner_assets.sh` | data | asset fetch, fixture + place extraction |
| `planner/mock_api/fixtures/**`, `planner/public/data/**`, `planner/data/osm/**` | data | generated, committed (small) |
| `tests/planner/test_build_*.py` | data | pytest |
| `planner/mock_api/*.py`, `planner/contract/README.md`, `planner/scripts/fetch_contract.sh` | mock | stdlib HTTP mock of the official contract |
| `tests/planner/test_mock_*.py` | mock | pytest |
| `planner/tools/build_basemap.py`, `planner/public/basemap/**` | basemap | offline vector tiles + glyphs/sprites |
| `planner/scripts/precompute.py`, `planner/cache/**` | precompute | batch via `/dispatch-plans` |

Gitignored working dirs: `planner/node_modules/`, `planner/dist/`, `planner/.assets/` (downloaded
release zips, extracted records, raw caches).

## 3. Source assets (already public GitHub Release assets of this repo)

Fetched by `planner/scripts/fetch_planner_assets.sh` into `planner/.assets/release/` and
verified by SHA-256 before use:

| Release tag | Asset | SHA-256 |
|---|---|---|
| research-final-20261015 | WFG-evaluated-routing-inputs-20261015.zip | d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202 |
| research-final-20261015 | WildfireGuardian_Latest_Independent_Final_20261015.zip | a3cd27b88d065883ce3d0534592d1406e3f9798c1abd98256c730f0cf3d60d3f |
| routing-ablation-final-inputs-20261016 | WFG-final-input-routing-ablation-20261016-v1.zip | 661090bd059a862a9874c4e19977c105d1978bf32ee6d6d3cd7f6d40d244c006 |

Inside them:

- Inputs zip: `graphs/<region>/graph.json` (EPSG:5179 nodes `{id:"osm:<n>",x,y,waitable}`,
  edges `{id,u,v,travel_ticks,segments,...}`; an edge is the straight chord u→v);
  `latest_inputs_try02/packets/<region>/<YYYYMMDDTHHMMSSZ>/{HAZARD.json,constructed_arrays.npz}`
  (`ignition_time_s[4,H,W]` inf=never, `current_active`, `mask__known_burned`,
  `mask__constructed_probability` = next-hour new-burn probability, grid in HAZARD.json `grid`,
  `row_reversal: true` — check cell indexing against the graph's edge `segments[].cell`);
  `latest_inputs_try02/requests/<region>/<case>.json` (origin node, destinations with dwell and
  open intervals, departure, horizon, budgets: peak 10 kW/m², dose 100 kJ/m² per member);
  `latest_inputs_try02/exports/<event>/FORECAST_<t>.npz` (full event grid incl.
  `source_burned_area` = recorded burned footprint at the input time).
- Final zip: `.../study/execution/run/WFG-latest-completion-kit-20261015-v3/raw/LATEST_PRIMARY/<region>__<case>__r<1|2>__<RDA_CAND|RDA_BASE>/RESULT.json`
  (`result.status`, `result.legs[{kind:EDGE|WAIT,edge,start,end,from_fraction,to_fraction}]`,
  `result.arrival`, `result.destination`, `result.per_member{<id>:{peak,dose,...}}`,
  `refusal_certificate`) and `INDEPENDENT_ROWS.csv` (authoritative frozen outcome per execution,
  complete-request `wall_s`).
- Ablation zip: `routing_final_input_ablation_20261016_v1/study/raw/ABLATION/<region>__<case>__r<rep>__A<0-4>/RESULT.json`
  (A0 = travel time only; A4 = full policy) and `analysis/ROWS.csv` (`full_policy_pass`,
  `full_failure_components`).

Recorded outcome → verdict mapping (final panel: `RDA_CAND` repetition 1; record repetition 2 too; ablation
rows map the same way via `own_outcome`/`authoritative_decision`):
`CHECKED_CENTRE_OPTIMUM`/`CHECKED_ROUTE` → `checked_route`;
`CERTIFIED_CENTRE_REFUSAL` (admitted scoped refusal, result `PROVEN_INFEASIBLE`) → `model_no_route`;
anything else (TIMEOUT, centre-only refusal without authority) → `unresolved`.

## 4. Generated data formats (data owner writes, everyone reads)

### 4.1 `planner/mock_api/fixtures/` (consumed only by the mock server)

- `MANIFEST.json` — `{generated_at, generator, sources:[{release_tag, asset, sha256}], conventions:{...verified grid orientation...}, files:[{path, sha256, bytes}]}`.
- `regions.json` — exactly the official `GET /regions` payload (`RegionList`: `regions[]` of `Region` with
  `id, name_ko, name_en, event_id, bbox, graph_id, graph_sha256, node_count, edge_count, allowed_node_count,
  crs, grid{x0,y0,resolution_m,width,height}, input_times[], scenario_sets[{scenario_set_id, input_time,
  scenario_ids[4], horizon_s, hazard_sha256}]` and a `provenance` block). Extra field allowed: `fire_year`.
- `forecast/<region_id>/<input_compact>.json` — exactly the official `ForecastCollection` for that input time with
  ALL cells of the region grid (`properties: row, col, p_new_burn_1h, valid, burning_now`; extra optional
  properties `cell`, `known_burned`); the mock filters for `only_nonzero=true`. `input_compact` = `20250324T090000Z`.
- `nodes/<region_id>.json` — compact node table for mock snapping: `{"ids":[...],"lon":[...],"lat":[...],
  "allowed":[0|1,...], "allowed_rule":"largest strongly connected component (mock assumption)"}`.
- `records/<region_id>/<case_id>__<policy>.json` — one recorded execution. `policy` ∈
  `full` (final panel `RDA_CAND` repetition 1 — the evaluated configuration), `travel_only` (ablation A0),
  `flame_only` (A1), `flame_peak` (A2), `flame_dose` (A3); verify the A-index ↔ policy mapping from the
  ablation's POLICY_TRANSFORMS.json/README before writing.

```json
{
  "case_id": "20250324T090000Z_FL2", "region_id": "uiseong_andong_2025", "policy": "full",
  "source_arm": "RDA_CAND", "repetition": 1,
  "scenario_set_id": "ffb1:20250324T090000Z:08721049cc48e045", "input_time": "2025-03-24T09:00:00Z",
  "scenario_ids": ["…:0", "…:1", "…:2", "…:3"],
  "request": {"origin_node": "osm:7836400838", "destination_node": "osm:365846317", "depart_offset_s": 0,
              "dwell_s": 120, "destination_window": [0, 3600], "horizon_s": 3600,
              "limits": {"peak_kw_m2": 10, "dose_kj_m2": 100},
              "incurred_dose_kj_m2": 0, "incurred_per_member": {"…:0": 0}},
  "outcome": {"verdict": "checked_route", "reason_code": null, "raw_status": "CHECKED_ROUTE",
              "raw_reason": "WHOLE_ROAD_CERTIFIED_FULL_MODEL_OPTIMUM_BY_CERTIFICATE",
              "frozen_state": "CHECKED_CENTRE_OPTIMUM", "departure_s": 0, "arrival_s": 2143,
              "lower_bound_L_s": 2143, "dwell_end_s": 2263, "compute_s": 6.59, "within_budget": true},
  "route": {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[128.69, 36.35]]},
            "properties": {"times_s": [0], "node_ids": ["osm:…"], "segment_count": 472, "edge_ids": ["w…"],
                           "waits": [], "length_m": 23810.5}},
  "exposure": [{"scenario_id": "…:0", "peak_kw_m2": 0.00037, "dose_kj_m2": 0.0567, "contact": false}],
  "refusal_scope": null,
  "full_policy_check": {"pass": true, "failure_components": null},
  "repetitions": [{"arm": "RDA_CAND", "rep": 1, "frozen_state": "…", "verdict": "…", "wall_s": 6.59, "arrival_s": 2143}],
  "input_hashes": {"graph": "…", "hazard": "…", "request": "…"},
  "source_records": [{"asset": "WildfireGuardian_Latest_Independent_Final_20261015.zip", "path": "…/RESULT.json", "sha256": "…"}]
}
```
`compute_s` = complete-request `wall_s` of that execution (INDEPENDENT_ROWS.csv for `full`, ablation ROWS.csv
otherwise). Missing values are `null`, never 0. `route` is null unless the verdict is `checked_route`.
`exposure` is filled only for `checked_route`. Route vertices: each EDGE leg is the straight chord u→v of the
graph edge, interpolated by `from_fraction`/`to_fraction`; a WAIT leg repeats the point with the later time;
`times_s` are absolute seconds after `input_time`, one per vertex; first vertex = origin node, last = destination node.

### 4.2 `planner/public/data/regions/<region_id>/places.geojson` (consumed by the app)

WGS84 FeatureCollection of candidate origins and destinations. Point properties:

```json
{
  "id": "osm:node/415158323",
  "role": "origin",                    // origin | destination | research_origin | research_destination
  "category": "village",               // village | hamlet | nursing_home | social_facility |
                                       // shelter | assembly_point | school | community_hall | research
  "name": "신석리", "name_en": "Sinseok-ri",   // null when OSM has no name — never invent one
  "source": "OpenStreetMap",           // OpenStreetMap | 연구 패널 기록 임무
  "source_tag": "place=village",       // exact OSM tag, or "request <case_id> origin node osm:…"
  "osm": {"type": "node", "id": 415158323, "tags": {}, "merged_ids": []},
  "snap": {"node": "osm:123", "distance_m": 84.2},   // nearest node of the largest SCC (display only)
  "checkable": true,                   // false when snap.distance_m > 300 (the API refuses snaps > 300 m)
  "vulnerable": false,                 // true for nursing_home / social_facility
  "scenario_set_id": null, "input_time": null, "case_id": null,   // research_* only
  "recorded": null                     // research_origin only: {destination_id, destination_node, depart_offset_s,
                                       //   dwell_s, destination_window, incurred_dose_kj_m2}
}
```

Filters: origins = `place=village|hamlet` nodes and `amenity=nursing_home|social_facility` (and
`social_facility=*`) inside the graph bbox. Destinations = `amenity=shelter` (excluding `shelter_type`
gazebo, public_transport, picnic_shelter, sun_shelter, weather_shelter, field_shelter, changing_rooms,
lean_to, rock_shelter), `emergency=assembly_point`, `amenity=school` / `building=school`,
`amenity=community_centre`, and `amenity=townhall` whose name contains `회관` (community hall). Points with
snap distance > 2 000 m are dropped and listed in `places_report.json` with the reason (as is every other
excluded element). Research points are the recorded missions' origin/destination nodes, one feature per
(case, role), id `research:<region>:<case_id>:origin|destination`.

- `planner/public/data/regions/index.json` — `[{region_id, name:{ko,en}, fire_year, event_id, bbox:[w,s,e,n],
  center:[lon,lat], zoom, demo:boolean, counts:{origins, destinations, research}}]`.
- `planner/public/data/regions/<region_id>/footprints.geojson` — recorded burned footprint polygons
  (`source_burned_area > 0` cells dissolved) per recorded input time of that event, clipped to the region
  window, property `input_time`, `area_km2`. Used only as presets for user-drawn zones and labelled as such.
- `planner/data/osm/<region_id>.overpass.json` — raw Overpass extract (ODbL), with query text, endpoint and
  `timestamp_osm_base` in `planner/data/osm/SOURCES.json`.

## 5. Route-Check API v1 — official contract

**The official contract is `planner/contract/wfg_api_v1.yaml`** (fetched from `origin/feat/api`,
`contracts/wfg_api_v1.yaml` v1.0.0; refresh with `planner/scripts/fetch_contract.sh`; changes are listed
in `contracts/CHANGELOG.md`). It supersedes the earlier draft. Key points for the planner:

- `POST /route-checks` checks ONE start → ONE destination: `{region, input_time, start: {node_id}|{lon,lat},
  destination: {node_id}|{lon,lat}, depart_offset_s, dwell_s (120), destination_window [open_s, close_s],
  policy (full|travel_only|flame_only|flame_peak|flame_dose), limits {peak_kw_m2 10, dose_kj_m2 100},
  incurred_dose_kj_m2, fire_input, run_independent_check, client_ref}` (`additionalProperties: false`).
  Coordinates snap to the nearest allowed road node; > 300 m → 422 `SNAP_TOO_FAR`.
- The travel-time-only comparison route is a second check with `policy: "travel_only"`.
- `POST /dispatch-plans`: `{region, input_time, fire_input, origins ≤ 200 [{id, location}],
  destinations ≤ 20 [{id, location, dwell_s, window}], depart_offsets_s ≤ 24, dwell_s, policy, limits}`;
  every origin is checked against every destination at every offset (attempts). Result: `plans[]` sorted by
  urgency with `best_verdict`, `latest_checked_depart_offset_s`, `best`, `attempts[{destination_id,
  depart_offset_s, verdict, reason_code, arrival_s, lower_bound_L_s, compute_s, route_check_job_id}]`,
  plus `summary`, `rejected_origins`, `assumptions`, `provenance`. The planner groups origins by their K
  nearest shelters so each plan stays within the limits and the number of checks stays small.
- `reason_code` enum (unresolved only, else null): TIMEOUT, STATE_CAP, MEMORY_CAP, CHECK_NOT_FINISHED,
  CHECK_FAILED, WORKER_ERROR, CLEANUP_UNCONFIRMED, INTERNAL_ERROR, OTHER.
- `GET /regions/{region}/forecast?input_time=&only_nonzero=` returns `ForecastCollection` (cells with
  `p_new_burn_1h, valid, burning_now`). No per-member ignition times are served.
- `spread_zones` fire input: `{type, zones (arrival_h_max), issued_at, margin_min (60),
  burning_scenario_set_id}`; results carry an `assumptions` object (show it verbatim in the side panel) and
  `provenance.approximation`.
- `/health` has no mode field; the mock adds `"mode": "mock"` (extra properties are allowed) and every mock
  provenance carries `"mock": true`. The real API is detected by the absence of these markers.
- Export (`/route-checks/{id}/export?format=geojson|kml|csv`) exists only for `checked_route`
  (409 `NO_CHECKED_ROUTE` otherwise); CSV header `seq,node_id,lon,lat,time_s,event`.

### 5.1 Mock matching rule (honesty)
The mock returns a recorded result only when `region`, `input_time`, `fire_input.scenario_set_id`, start node,
destination node, `depart_offset_s`, `dwell_s`, `destination_window` (omitted = `[0, horizon_s]`), `policy`,
`limits` and `incurred_dose_kj_m2` all equal a recorded execution (§4.1). Start/destination given as lon/lat
are snapped with the mock node table (largest SCC, ≤ 300 m, else 422 `SNAP_TOO_FAR`). Everything else returns
`verdict: "unresolved"`, `reason_code: "OTHER"`, `raw_status: "MOCK_NO_RECORDED_RESULT"`, and every
`spread_zones` request returns `unresolved`, `reason_code: "OTHER"`, `raw_status: "MOCK_SPREAD_ZONES_NOT_EVALUATED"`
with an `assumptions` object saying the mock did not evaluate the zones. Unmatched results have
`compute_s: null`. Recorded results carry the recorded `compute_s` (complete-request wall time on the
recorded Apple M5 Pro host) and `provenance.host = {"recorded": true, "machine": "Apple M5 Pro", "os": "macOS (native)"}`.
The mock never sleeps to imitate computation beyond a short state transition (queued → running → done over
≈ 0.6 s) so the progress UI is exercised.

## 6. Frontend internal model (`planner/src/domain/types.ts`)

```ts
export type Verdict = 'checked_route' | 'model_no_route' | 'unresolved';
export type FireInput =
  | { type: 'recorded'; scenarioSetId: string; inputTime: string }
  | { type: 'spread_zones'; issuedAt: string; inputTime: string; zones: GeoJSON.FeatureCollection;
      marginMin: number; burningScenarioSetId: string | null };
export interface Attempt { offsetS: number; destinationId: string; verdict: Verdict; arrivalS: number | null;
  computeS: number | null; jobId: string | null; reasonCode: string | null; }
export interface SweepCell { offsetS: number; verdict: Verdict;           // best over destinations at this offset
  attempts: Attempt[]; best?: Attempt; }
export interface OriginPlan { originId: string; latestSafeDepartureS: number | null; bestVerdict: Verdict;
  best?: Attempt; sweep: SweepCell[]; windows: { verdict: Verdict; fromS: number; toS: number }[];
  source: 'cache' | 'live'; mock: boolean; }
```
Per offset the cell verdict is `checked_route` if any destination is checked, `model_no_route` only if every
destination is `model_no_route`, else `unresolved` (same rule as the contract's `best_verdict`).
Urgency order: origins whose best verdict is `model_no_route` first, then `unresolved`, then `checked_route`
origins by `latestSafeDepartureS` ascending; ties put `vulnerable` facilities first, then name.

Departure sweep: offsets every 10 min (configurable 5/10/15/20/30) over the window the scenario supports —
recorded: `[0, horizon_s)`; drawn zones: `[0, max arrival_h_max × 3600)` (≤ 24 offsets per dispatch plan; split
plans if needed) — plus the recorded departure offset of research origins. Shelter candidates per origin: the
K = 3 nearest destinations by straight-line distance (configurable 1–5); research origins use their recorded
destination with its recorded dwell, window and incurred dose. Non-checkable places (snap > 300 m) are shown as
unresolved "도로망 300 m 밖 — 점검 불가" without calling the API.

Clock display: recorded scenarios show KST wall time = input time + offset ("출발 마감 18:10");
drawn zones show issued time + offset and the relative "T+1:40".

Ready-Set-Go (산림청): origins inside the drawn 8 h zone → "준비(Set): 노약자·취약시설 우선 대피";
inside the 5 h zone → "실행(Go): 전원 대피". Containment is planner-side point-in-polygon only.

## 7. Visual design

- Colours: ink `#0B0B0C`, paper `#FFFFFF`, surface `#F5F5F7`, hairline `#E3E3E6`, secondary text
  `#6E6E73`, single accent green `#1A9E55` (hover `#14824A`, tint `#E8F6EE`), unresolved grey `#9A9AA0`.
- No gradients, no drop-shadow stacks (one subtle elevation max), radius 10–14 px, 8 px grid.
- Font: Pretendard Variable (bundled, OFL), tabular numerals for times.
- Status always = colour + icon + text. Icons are simple geometric inline SVG (check, slashed circle,
  question mark in circle), never clip-art.
- Layout at ≥1440 px: top bar 56 px; left 340 px; right 400 px; map fills the rest; footer 32 px.
