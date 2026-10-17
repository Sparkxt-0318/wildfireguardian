# WildfireGuardian 마을별 사전 대피계획 도구 — architecture and build contract

This is the working contract for everyone building `planner/`. It fixes directory ownership,
data formats, the draft wire format of the Route-Check API and the honesty rules. When the
API session publishes `contracts/wfg_api_v1.yaml`, only `planner/src/api/adapter.ts` and the
mock server change; the UI's internal model below stays stable.

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
| `planner/mock_api/*.py`, `planner/contract/**`, `planner/scripts/fetch_contract.sh` | mock | stdlib HTTP mock + draft contract |
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

Recorded outcome → verdict mapping (use `RDA_CAND` repetition 1; record repetition 2 too):
`CHECKED_CENTRE_OPTIMUM`/`CHECKED_ROUTE` → `checked_route`;
`CERTIFIED_CENTRE_REFUSAL` (admitted scoped refusal, result `PROVEN_INFEASIBLE`) → `model_no_route`;
anything else (TIMEOUT, centre-only refusal without authority) → `unresolved`.

## 4. Generated data formats (data owner writes, everyone reads)

### 4.1 `planner/mock_api/fixtures/`

- `MANIFEST.json` — `{generated_at, generator, sources:[{release_tag, asset, sha256}], files:[{path, sha256}]}`.
- `regions.json` — exactly the `GET /v1/regions` payload (§5.2).
- `forecast/<region_id>/<input_compact>.json` — exactly the `GET /v1/regions/{id}/forecast` payload (§5.3).
  `input_compact` = `20250324T090000Z`.
- `records/<region_id>/<case_id>.json` — one recorded mission:

```json
{
  "case_id": "20250324T090000Z_FL2",
  "region_id": "uiseong_andong_2025",
  "scenario_set_id": "ffb1:20250324T090000Z:08721049cc48e045",
  "input_time": "2025-03-24T09:00:00Z",
  "request": {
    "origin_node": "osm:7836400838",
    "departure_offset_s": 0,
    "horizon_s": 3600,
    "destinations": [{"node": "osm:365846317", "dwell_s": 120, "open_intervals_s": [[0, 3600]]}],
    "budgets": {"peak_kw_m2": 10, "dose_kj_m2": 100}
  },
  "result": { "...": "a complete RouteCheckResult (§5.4) with provenance.source = 'recorded'" },
  "repetitions": [{"arm": "RDA_CAND", "rep": 1, "state": "CHECKED_CENTRE_OPTIMUM", "wall_s": 6.59, "arrival_s": 2143}],
  "source_records": [{"asset": "WildfireGuardian_Latest_Independent_Final_20261015.zip", "path": ".../RESULT.json", "sha256": "..."}]
}
```

### 4.2 `planner/public/data/regions/<region_id>/places.geojson`

WGS84 FeatureCollection of candidate origins and destinations. Point properties:

```json
{
  "id": "osm:node/415158323",
  "role": "origin",                    // origin | destination
  "category": "village",               // village | hamlet | nursing_home | social_facility |
                                       // shelter | assembly_point | school | community_hall |
                                       // research_origin | research_destination
  "name": "신석리", "name_en": "Sinseok-ri",
  "source": "OpenStreetMap",           // OpenStreetMap | 연구 패널 기록 임무
  "source_tag": "place=village",       // the exact OSM tag (or "request <case_id> origin")
  "osm": {"type": "node", "id": 415158323, "tags": {"...": "..."}},
  "snap": {"node": "osm:123", "distance_m": 84.2},
  "vulnerable": false,                 // true for nursing_home / social_facility
  "scenario_set_id": null,             // research_* points only: their scenario set
  "case_id": null,                     // research_* points only
  "recorded_destination": null         // research_origin only: {"node","dwell_s","open_intervals_s"}
}
```

Filters: origins = `place=village|hamlet` nodes and `amenity=nursing_home|social_facility`
(and `social_facility=*`) inside the graph bbox. Destinations = `amenity=shelter` (excluding
`shelter_type` gazebo, public_transport, picnic_shelter, sun_shelter, weather_shelter,
field_shelter, changing_rooms, lean_to, rock_shelter), `emergency=assembly_point`,
`amenity=school` / `building=school`, `amenity=community_centre`, and `amenity=townhall` whose
name contains `회관` (community hall). Snap to the nearest graph node; drop points snapping
farther than 1 000 m and list them in the region's `places_report.json` with the reason.
Research points (recorded missions' origin/destination nodes) are added with their case id.

- `planner/public/data/regions/index.json` — `[{region_id, name:{ko,en}, fire_year, event_id,
  bbox:[w,s,e,n], center:[lon,lat], zoom, demo:boolean, counts:{origins, destinations}}]`.
- `planner/public/data/regions/<region_id>/footprints.geojson` — recorded burned footprint polygons
  (`source_burned_area > 0` cells dissolved) per recorded input time of that event clipped to
  the region window, property `input_time`. Used only as presets for user-drawn zones and
  labelled as such.
- `planner/data/osm/<region_id>.overpass.json` — raw Overpass extract (ODbL), with query text
  and `timestamp_osm_base` recorded in `planner/data/osm/SOURCES.json`.

## 5. Draft Route-Check API v1 wire format

Base `http://127.0.0.1:8765/v1`. JSON, UTF-8, CORS `*`. Times: ISO-8601 UTC strings; offsets in
seconds after the scenario input time. Coordinates: WGS84 `[lon, lat]`.

### 5.1 `GET /health`
`{"status":"ok","mode":"mock"|"live","api_version":"1.0.0-draft","engine":{"package":"wfg_latest","package_version":"1.0.0","kit":"v3","checkpoint":"c651f672…"}}`

### 5.2 `GET /regions`
```json
{"regions": [{
  "region_id": "uiseong_andong_2025", "name": {"ko": "의성·안동", "en": "Uiseong–Andong"},
  "event_id": "KFS_01", "fire_year": 2025, "crs": "EPSG:5179", "bbox": [128.546, 36.3346, 128.8548, 36.5512],
  "grid": {"x0": 1093875.0, "y0": 1815750.0, "resolution": 375.0, "width": 73, "height": 65},
  "graph": {"revision": "...", "canonical_sha256": "...", "nodes": 23158, "edges": 43826, "osm_snapshot": "2025-03-21T23:59:59Z"},
  "scenario_sets": [{"scenario_set_id": "ffb1:20250324T090000Z:08721049cc48e045", "input_time": "2025-03-24T09:00:00Z",
                     "members": ["...:0", "...:1", "...:2", "...:3"], "valid_from_s": 0, "valid_until_s": 3600,
                     "source": "recorded", "checkpoint": "c651…"}]
}]}
```

### 5.3 `GET /regions/{region_id}/forecast?input_time=<iso>`
```json
{"region_id": "...", "input_time": "...", "scenario_set_id": "...", "cell_size_m": 375, "horizon_s": 3600,
 "members": ["...:0", "...:1", "...:2", "...:3"],
 "cells": {"type": "FeatureCollection", "features": [{"type": "Feature",
    "geometry": {"type": "Polygon", "coordinates": [[[lon, lat], "..."]]},
    "properties": {"cell": 4512, "row": 61, "col": 59, "p_next_hour": 0.0479,
                   "burning_at_input": false, "known_burned": true, "ignition_s": [162.6, null, null, 900.1]}}]},
 "provenance": {"source": "recorded", "checkpoint": "c651…", "packet": "packets/<region>/<t>", "packet_npz_sha256": "..."}}
```
Only cells with `p_next_hour > 0`, burning, known burned, or any finite ignition are listed.

### 5.4 `POST /route-checks` → `202 {"job_id":"rc_…","status":"queued"}`; `GET /route-checks/{job_id}`
Request:
```json
{"region_id": "uiseong_andong_2025",
 "origin": {"id": "osm:node/1", "node": "osm:7836400838", "lon": 128.69, "lat": 36.35},
 "destinations": [{"id": "osm:way/2", "node": "osm:365846317", "dwell_s": 120, "open_intervals_s": [[0, 3600]]}],
 "departure_offset_s": 0,
 "fire_input": {"type": "recorded", "scenario_set_id": "ffb1:…"},
 "options": {"include_travel_only": true}}
```
or `"fire_input": {"type": "spread_zones", "reference_time": "<iso>", "zones": <FeatureCollection of Polygons with properties.arrival_h_max (5 | 8)>}`.

Job: `{"job_id","status":"queued|running|done|failed","submitted_at","finished_at","progress":{"stage":"queued|search|check|done","fraction":0..1},"result":RouteCheckResult|null,"error":null|{code,message}}`.

RouteCheckResult:
```json
{"verdict": "checked_route", "reason_code": "WHOLE_ROAD_CERTIFIED_FULL_MODEL_OPTIMUM_BY_CERTIFICATE",
 "origin_id": "...", "destination_id": "...", "departure_offset_s": 0, "arrival_s": 2143, "dwell_s": 120,
 "route": {"type": "Feature", "geometry": {"type": "LineString", "coordinates": [["lon", "lat"]]},
           "properties": {"times_s": [0, 4, 8], "n_legs": 472, "length_m": 23810.5}},
 "travel_only_route": {"type": "Feature", "geometry": {}, "properties": {"times_s": [], "arrival_s": 2010, "full_policy_pass": false, "failure_components": "flame"}},
 "exposure": [{"scenario_id": "...:0", "peak_kw_m2": 0.00037, "dose_kj_m2": 0.0567, "peak_limit_kw_m2": 10, "dose_limit_kj_m2": 100}],
 "compute_s": 6.59,
 "assumptions": [{"id": "...", "text": {"ko": "...", "en": "..."}}],
 "provenance": {"source": "recorded|computed|mock", "api_mode": "mock|live", "checkpoint": "c651…", "package": "wfg_latest 1.0.0",
                "kit": "v3", "arm": "RDA_CAND", "graph_revision": "...", "scenario_set_id": "...", "host": "Apple M5 Pro (recorded)",
                "case_id": "20250324T090000Z_FL2", "record": {"asset": "...", "path": "...", "sha256": "..."}}}
```
`route` is null unless `verdict = checked_route`. `times_s` are absolute seconds after the input time,
one per vertex (a WAIT leg repeats the coordinate with a later time).

### 5.5 `POST /dispatch-plans` → `202 {"plan_id":"dp_…","status":"queued"}`; `GET /dispatch-plans/{plan_id}`
Request: `{"region_id","fire_input","origins":[{id,node,lon,lat,destinations?:[dest ids]}],"destinations":[...],"departure_offsets_s":[0,600,...]}`.
Response: `{"plan_id","status","progress":{"done","total"},"results":[{"origin_id","latest_safe_departure_s":600|null,
"best":RouteCheckResult|null,"sweep":[{"departure_offset_s","verdict","destination_id","arrival_s","compute_s","job_id","reason_code"}]}],"provenance":{...}}`.
`latest_safe_departure_s` = the latest offset whose verdict is `checked_route` (null if none). Each sweep
entry's `job_id` resolves via `GET /route-checks/{job_id}` to the full result.

### 5.6 `GET /route-checks/{job_id}/export?format=geojson|kml|csv`

### 5.7 Mock matching rule (honesty)
The mock returns a recorded result only when region, `scenario_set_id`, origin node and
`departure_offset_s` equal a recorded mission and the recorded destination (same dwell and open
intervals) is among the request destinations. A recorded `checked_route` stays valid with extra
destinations (the checked journey still reaches a candidate shelter; note `"other_destinations_not_evaluated": true`).
A recorded `model_no_route` or `unresolved` is returned only if the destination set equals the
recorded set. Everything else, and every `spread_zones` request, returns
`verdict: "unresolved"`, `reason_code: "MOCK_NO_RECORDED_RESULT"` (or `"MOCK_SPREAD_ZONES_NOT_EVALUATED"`),
`compute_s: null`, `provenance.source: "mock"`. Mock compute times are the recorded `wall_s`
of the recorded execution, labelled as recorded; the mock never sleeps to imitate computation
beyond a short state transition (queued → running → done over ≈0.6 s) so progress UI is exercised.

## 6. Frontend internal model (`planner/src/domain/types.ts`)

```ts
export type Verdict = 'checked_route' | 'model_no_route' | 'unresolved';
export type FireInput =
  | { type: 'recorded'; scenarioSetId: string; inputTime: string }
  | { type: 'spread_zones'; referenceTime: string; zones: GeoJSON.FeatureCollection };
export interface SweepCell { offsetS: number; verdict: Verdict; destinationId?: string; arrivalS?: number;
  computeS?: number | null; jobId?: string; reasonCode?: string; }
export interface OriginPlan { originId: string; latestSafeDepartureS: number | null; best?: CheckResult;
  sweep: SweepCell[]; windows: { verdict: Verdict; fromS: number; toS: number }[]; source: 'cache' | 'live' | 'mock'; }
```
Urgency order: origins with no `checked_route` and any `model_no_route` first, then origins with
only `unresolved`, then `checked_route` origins by `latestSafeDepartureS` ascending; ties put
`vulnerable` facilities first, then name.

Departure sweep: offsets every 10 min (configurable 5/10/15/30) over the window the scenario
supports — recorded: `[valid_from_s, valid_until_s)`; drawn zones: `[0, max arrival_h_max × 3600)` —
plus any recorded departure offsets of research origins. Shelter candidates per origin: the K = 5
nearest destinations by straight-line distance (configurable); research origins use their recorded
destination only.

Clock display: recorded scenarios show KST wall time = input time + offset ("출발 마감 18:10");
drawn zones show reference time + offset and the relative "T+1:40".

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
