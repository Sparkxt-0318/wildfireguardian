# Planner data tools

Data builders for the 마을별 사전 대피계획 도구 (pre-season village evacuation planner).
The binding contract is `planner/docs/ARCHITECTURE.md` (§3 sources, §4 formats) and the official
Route-Check API contract `planner/contract/wfg_api_v1.yaml`. `build_basemap.py` in this folder belongs to
the basemap builder and is not described here.

These tools only **read recorded data** (graph JSON, packet HAZARD.json / NPZ, mission requests, event exports,
recorded RESULT.json files and CSV rows). They never import or run forecasting or routing code, and they never
invent places, routes, fires or numbers: absent values are `null`, names come only from OSM.

## Run

```bash
pip install -r planner/tools/requirements.txt          # numpy, pyproj, shapely (+ test deps)
planner/scripts/fetch_planner_assets.sh                # download + SHA-256 verify + safe extract (idempotent)
python3 planner/tools/extract_places.py                # Overpass extracts + places + index.json
python3 planner/tools/build_fixtures.py                # mock fixtures + footprints + MANIFEST.json
python3 -m pytest tests/planner/test_build_places.py tests/planner/test_build_fixtures.py -q
```

`WFG_ASSETS_DIR=/some/dir` relocates `planner/.assets/` for the script, the tools and the tests. Tests that
need the release extracts skip with a reason when they are missing; output-only tests still run.

`extract_places.py` downloads an Overpass extract only when `planner/data/osm/<region>.overpass.json` is
missing (`--refresh <region>` forces a new download, `--fetch-only` stops after the extracts). Extracts kept by
an earlier run in `planner/.assets/osm_raw/` are reused (uiseong_andong_2025 and uljin_2022 from
maps.mail.ru, hongseong_2023 from overpass.kumi.systems). Downloads rotate over four public Overpass endpoints
with exponential back-off (12 attempts).

## Files

| Tool | Writes |
|---|---|
| `planner_common.py` | shared helpers (paths, hashes, graph loading, iterative Tarjan SCC, EPSG:5179 ↔ WGS84) |
| `extract_places.py` | `planner/data/osm/<region>.overpass.json`, `planner/data/osm/SOURCES.json`, `planner/public/data/regions/<region>/places.geojson`, `.../places_report.json`, `planner/public/data/regions/index.json` |
| `build_fixtures.py` | `planner/mock_api/fixtures/{MANIFEST.json, regions.json, forecast/<region>/<input>.json, nodes/<region>.json, records/<region>/<case>__<policy>.json}`, `planner/public/data/regions/<region>/footprints.geojson` |

Sizes of the committed outputs (last build): fixtures ≈ 19.0 MB in total (15 forecast grids 12.8 MB, node
tables 3.7 MB, 100 records 2.6 MB); places + reports + footprints + index ≈ 0.5 MB; raw OSM extracts ≈ 0.2 MB.
Set `SOURCE_DATE_EPOCH` to make `generated_at` (and therefore every output byte) reproducible.

## Places (§4.2)

* Region bbox = the road-graph grid rectangle (EPSG:5179) transformed to WGS84 with densified edges; the
  Overpass query uses it (S,W,N,E rounded outwards to 1e-7°). POIs are **current** OSM
  (`timestamp_osm_base` per region in `SOURCES.json`); the road graphs are **historical** snapshots taken just
  before each fire.
* Filters are applied exactly as §4.2 states. Every element of the raw extract ends up either as a feature, a
  merged id, or an entry in `places_report.json` (`excluded` / `dropped_far`) with its reason, e.g. hospitals,
  clinics, kindergartens, `place=town|quarter|neighbourhood|isolated_dwelling`, place ways, gazebo-type
  shelters, town halls without 회관 in the name, points outside the grid rectangle, snaps > 2 km.
* A school mapped as both node and way (same name, ≤ 150 m) keeps the way centre; both ids are in
  `osm.merged_ids`. Other same-name pairs are only listed under `possible_duplicates_not_merged`.
* `snap` = nearest node of the largest strongly connected component of the directed road graph (display
  only); `checkable` = snap ≤ 300 m.
* Research points: one feature per (case, role) from the 20 recorded mission requests (40 features; some
  missions share an origin node). `recorded` on research origins additionally carries the recorded `limits`
  (peak and per-member dose budget) and `horizon_s`, needed to replay the FN/FX missions exactly.
* `index.json` `zoom` fits the bbox into the 1440×900 layout's map pane (≈ 700 × 812 px), quarter steps.

## Fixtures (§4.1)

* **Grid orientation (verified, recorded in `MANIFEST.json` → `conventions.grid_orientation`).** Graph edge
  `segments[].cell` and HAZARD.json member arrays use `cell = row*width + col` with **row 0 at the south edge**
  (`grid.y0`). `constructed_arrays.npz` and the event export `FORECAST_<t>.npz` are native **north-up** rasters
  (`affine [375,0,x0,0,-375,y_top]`), so `native_row = height-1-row` — this is what HAZARD
  `row_reversal: true` denotes. Checks on every build: 100 % of graph segment midpoints fall in the cell
  `row_s*W+col`; a 3 000-point sample per region falls inside the published WGS84 polygon of its cell; every
  packet probability/validity array equals the export window in native order (and not flipped); every
  `current_active` cell is flame-active in HAZARD member interval 0 at the south-up index. `ForecastCell`
  `row`, `col`, `cell` and `id` (`r<row>c<col>`) use the south-up graph convention.
* `regions.json` is the official `RegionList` (extra field `fire_year`). One scenario set per packet directory;
  `allowed_node_count` = largest SCC size (mock rule, stated in the provenance).
* `forecast/<region>/<input>.json` holds **all** grid cells (`p_new_burn_1h` from
  `mask__constructed_probability`, 6 significant digits; `valid`; `burning_now`; extra `cell`, `known_burned`).
* `records/`: policy `full` = final panel `RDA_CAND` repetition 1 (repetition 2 stored and asserted equal in
  verdict and arrival); `travel_only`/`flame_only`/`flame_peak`/`flame_dose` = ablation A0/A1/A2/A3 repetition 1
  (mapping verified from `POLICY_TRANSFORMS.json` enabled constraint sets). `compute_s` is the complete-request
  `wall_s` from `INDEPENDENT_ROWS.csv` (full) or the ablation `analysis/ROWS.csv` (the repo copy
  `research/routing/final-input-ablation/data/ROWS.csv` is `ROWS_REVIEWED.csv`: identical outcomes and wall
  times plus independent-refusal annotations, carried as `independent_refusal_status`).
  The panel split (15 `checked_route`, 5 `model_no_route`) is asserted against `FINAL_REVIEW.json`.
* `request.limits` are the **recorded request budgets**: FN/FX missions use mission-specific dose budgets
  (e.g. 2.35 kJ/m² with 0.71 incurred), all others 10 kW/m² and 100 kJ/m². The mock must match them exactly.
* `exposure` = the execution's own centre-model per-member values (`result.per_member`, dose includes the
  incurred dose; `contact: false` for checked routes). Policies A0/A1 zero the radiant flux, so their
  `exposure` is not physical exposure; ablation records therefore also carry `full_model_exposure` (the
  dual-policy grade's offline full-policy check of that route, with flame contact) and `full_policy_check`.
* Route geometry: one vertex per leg end plus the origin; EDGE legs are straight chords u→v; a WAIT leg repeats
  the point with its end time; `waits[]` merges consecutive 1 s WAIT legs at one node; `segment_count` = number
  of legs; `length_m` = sum of EPSG:5179 chord lengths.
* `nodes/<region>.json`: `allowed` = in the largest SCC. `recorded_mission_nodes` lists the recorded mission
  endpoints; one of them (uljin_2022 `20220304T030000Z_FX1` destination `osm:4744584066`, on a one-way way)
  is **outside** the largest SCC although the recorded execution reached it — the mock should accept recorded
  endpoints by `node_id`.
* `footprints.geojson`: recorded burned area (`source_burned_area_valid & source_burned_area > 0`) of the parent
  event at each export time (KFS_01 has six, shared by both 2025 regions), 375 m cells dissolved with shapely,
  clipped to the region grid padded 2 km, WGS84. Presets for user-drawn zones only.
