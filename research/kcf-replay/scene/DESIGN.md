# KCF 3D scene: design and data contract

One browser 3D scene for the judged presentation of `research/kcf-replay` (25 March 2025, 12:00–24:00 KST).
It runs from the published demo site (GitHub Pages, `planner/public/kcf-scene/` is copied verbatim into the
planner's static build and served at `<pages>/kcf-scene/`) and from a local folder opened with `file://`
(double-click `index.html`; no server, no install, no network).

## Stack

* MapLibre GL JS 5.24.0 (vendored from `planner/node_modules/maplibre-gl/dist`, BSD-3), 3D terrain from a
  `raster-dem` source, every other layer draped on or extruded from that terrain. The terrain is clipped to the bbox
  (lon 128.28–129.50, lat 36.20–36.62) at every zoom: a lower-zoom tile reaches further beyond the bbox, so unclipped
  tiles made the terrain's edge move, and notches open in it, when MapLibre mixed zoom levels across the view.
* No three.js / deck.gl: nothing in levels 1–3 needs a second renderer (see "Level 3 crossing view" below).
* Classic `<script>` tags only (ES modules and `fetch()` are blocked on `file://`). All data ships as `.js` files
  that assign to `window.KCF.*`. Tiles and glyphs are served to MapLibre through `maplibregl.addProtocol`
  handlers that read those in-memory objects. No request ever leaves the page.

## Files

```
planner/public/kcf-scene/
  index.html, app.js, style.css           front end (hand-written, no build step)
  vendor/maplibre-gl.js, maplibre-gl.css, LICENSE-maplibre-gl.txt
  data/scene.js      window.KCF.scene     (build_scene.py)
  data/terrain.js    window.KCF.terrain   (build_terrain.py)
  data/basemap.js    window.KCF.basemap   (build_basemap.py)
  data/fonts.js      window.KCF.fonts     (build_fonts.py; UI face = Pretendard subset renamed "KCF UI Sans" per the OFL)
  README.md          how to open it, what every layer is, sources
  kcf_scene_tour_90s.mp4   the 90 s fallback recording (tests/record_tour.mjs, from the scene's own ?tour=1)
research/kcf-replay/scene/
  DESIGN.md (this file), build_*.py, verify_scene.py, VERIFY.json, SOURCES.json,
  tests/ (Playwright smoke, file:// check, load-time measurement), MEASUREMENTS.md,
  CLICK_SCRIPT.md (+ .pdf)
```

Every builder writes deterministic output (sorted keys, fixed float rounding) and records, in its output, the
repository-relative path, byte size and SHA-256 of every input it read (`built.inputs`).

## Inputs

Committed:
* `research/kcf-replay/per_place.csv` — step, latest safe departure, shelter, arrival per place × issue × stand-in × horizon.
* `research/kcf-replay/named_places_timeline.csv`, `SOURCES.md`, `RESULTS.md` §4 — six named places, documented ("reported") times.
* `research/kcf-replay/fire_discs.json` — the known-fire-area discs (EPSG:5179, `t_utc`, `r_m`, `src`).
* `research/kcf-replay/planner_cache/RUNNING_8h/**` — the planner cache (30-min departure grid, witness geometry).
* `research/kcf-replay/HOTSPOT_RULE.md`, `replay.py` — the frozen rule, R(h) stand-ins, closure formula.
* `research/kcf-replay/MEASURED_RULE.md`, `measured_arms.py` — the two MEASURED arms (frozen R(h) of `research/kcf-margin`,
  one class per issue hour; piecewise-linear closure curve), with `research/kcf-margin/numbers.json` (R per class) and
  `research/kcf-gust/work/gust_hours.json` (ERA5 next-8 h maximum gust, the MEASURED+GUST class input; PROVISIONAL).
* `planner/public/data/regions/<region>/places.geojson` — place and shelter entry nodes.
* `planner/research-map/site/regions/<region>.osm.js` — roads, water (from the committed planner PMTiles).
* `planner/data/osm/<region>.overpass.json` — town / 읍·면 names.
* `planner/public/basemap/fonts/Noto Sans Regular/0-255.pbf` — glyphs.
* UI font: Pretendard (OFL) from `planner/node_modules/pretendard`, i.e. the version pinned in `planner/package-lock.json`
  (installed by `npm ci`, not committed); the subset ships in `data/fonts.js`.

Not committed, SHA-pinned: `data/routing/graphs/<region>/graph.json` from release `research-final-20261015`
(`tools/fetch_routing_inputs.py`, zip SHA-256 `d7e0a5fc…`), and `research/kcf-replay/out/runs/*.json` re-made by
`replay.py fire_discs.json out/runs --horizons 8h` (code and inputs committed; the builder checks the re-made runs
reproduce `per_place.csv` exactly before using them).

## Time

Scene second `s` = seconds after 2025-03-25T03:00:00Z (= 12:00 KST). Issue hours `k = 0..12` at `s = 3600 k`
(12:00 … 24:00 KST). The slider runs 0 … 43 200 s. "Current issue" = the latest issue hour ≤ slider time.
Known fire area at issue `k` = discs with `t_utc` strictly before the issue time (HOTSPOT_RULE.md). Road cell `c`
is drawn closed at slider time `s` when `issue_s + close_s[k][c] ≤ s` (the issue-`k` screen's own closure time).

## `window.KCF.scene` (data/scene.js)

```js
{
  schema: "kcf-scene/1",
  built: { script, commit, generated_utc, inputs: [{path, bytes, sha256}], runs: {standin: "complete"|"absent"} },
  t0_utc: "2025-03-25T03:00:00Z",
  issues_s: [0, 3600, …, 43200], issue_kst: ["12:00", …, "24:00"], issue_utc: ["2025-03-25T03:00:00Z", …],
  horizon: "8h", horizon_s: 28800, dwell_s: 120,
  standins: { RUNNING: {kind: "standin", a_m: 0, v_m_per_h: 8200, label, basis, src: "research/kcf-replay/HOTSPOT_RULE.md"},
              ORDINARY: {…}, WORST: {…},
              MEASURED: {kind: "measured", label: "MEASURED", provisional: false, r_text, basis, results_line,   // RESULTS.md 2b row
                         classes: [ 13 × {cls, r5_m, r8_m} ], src: "…/MEASURED_RULE.md", code, numbers, gust_hours: null},
              MEASURED_GUST: {kind: "measured", label: "MEASURED+GUST", provisional: true, …,
                              classes: [ 13 × {cls, r5_m, r8_m, gust_ms (gust_hours.json fwd8.fire_wide_max; absent at 24:00)} ]} },
  default_standin: "RUNNING", standin_order: ["RUNNING", "MEASURED", "MEASURED_GUST", "WORST", "ORDINARY"],   // the R key cycle
  regions: { <region>: { name_ko, name_en, grid: {x0, y0, res, w, h, crs: "EPSG:5179"}, bbox: [W,S,E,N] } },
  places: [ { id, region, name, category, vulnerable, sigungu, lon, lat, entry: [lon, lat], named: bool } ],   // 174, sorted by id
  named: [ { id, name, order } ],                 // the six of RESULTS.md §4, in that order
  shelters: { <shelter_id>: { name, region, category, lon, lat, entry: [lon, lat] } },
  hourly: { <standin>: { <place_id>: [ 13 × {             // verbatim per_place.csv, horizon 8h
      step, state, lsd, last, shelter, arr, d_km, cut_before, first_cut, pieces, row } ] } },
      // lsd/last/arr/first_cut keep the CSV text ("03-25 18:47"); row = 1-based data-row number in per_place.csv
  routes: { <standin>: { <place_id>: [ 13 × null | {
      ld, arr, sh, e: [edge index …], sh_cell } ] } },      // seconds after the issue hour; edges index routeEdges[region]
  routeEdges: { <region>: [ { id, D, seg: [[cell, z_end] …], c: [[lon,lat] …] } ] },   // only edges used by a witness; c = u..v chord
  roadCells: { <region>: { cells: [cell …], ring: [[[lon,lat]×5] …] } },              // every grid cell any graph edge touches
  close: { <standin>: { <region>: [ 13 × [close_s per roadCells[region].cells[i], or -1 if not within 8 h] ] } },
  discs: { fields: ["s","lon","lat","r_m","src"], rows: [[s, lon, lat, r_m, src] …] },   // sorted by s; s may be < 0
  discCounts: [ 13 × { total, AHI, FIRMS } ],   // discs strictly before each issue hour
  planner: { <place_id>: [ 13 × { file, offsets_step_s, shelters: [[shelter_id, "1101…"] …], contiguous_s, best: {shelter, off_s, arr_s} | null } ] },
  reported: { <place_id>: { documented: "<named_places_timeline.csv 'documented' text>", rows: [ { kst, what, place, source, url, flag, line } ] } },
                                                  // place: "영덕군" for county-log rows, else the SOURCES.md Place cell (e.g. 면-level)
  countyLog: [ { kst, entry, line } ],            // SOURCES.md 뉴스로 table, verbatim, with SOURCES.md line numbers
  countyLogSource: { line, text, source, url, block, flag },   // that table's "Source:" line
  score: { "RUNNING/8h": {…} … },                 // score.json, verbatim
  src: { per_place: "research/kcf-replay/per_place.csv", … }   // every path the front end cites (also make_planner_cache,
                                                  // regions_index, graph per region, runs_dir, design; graph_release = {tag, zip, sha256, url, script})
}
```

## Front end (index.html + app.js)

Always on screen, every level: the test-data badge "시험 데이터 · 평가 호스트 아님 (test data, not the evaluated host)",
the label "2025년 실제 산불 기록 기반 시나리오 재현 · reconstruction from the 2025 record", and the active R(h) arm:
a stand-in ("RUNNING 8.2 km/h — a stand-in, not the frozen R(h)") or a MEASURED arm with its class at the issue hour
("MEASURED · running class at 16:00: 7.6 km at 5 h, 10.0 km at 8 h"; MEASURED+GUST always marked PROVISIONAL).

**R(h) arms.** Five, cycled with R: RUNNING (default; the only arm with a planner cache), MEASURED, MEASURED+GUST, WORST,
ORDINARY. The MEASURED arms are the frozen R(h) of `research/kcf-margin` (MEASURED_RULE.md): one class per issue hour for all
places (prior-3 h spread: quiet 12–14, slow 15, running 16–24 KST; gust: ≥ 20 m/s 12–22, 10–20 m/s 23–24 KST), closure on the
curve (0, 0), (5 h, R5), (8 h, R8), never beyond R8. Every place panel shows the same screen under all five arms (leave-by or
state, step, and whether the full record reached the road first), labelled "not a ranking".

* **Level 1, region.** Terrain of 의성·안동–영덕. Slider over the 13 issue hours. Known fire area (discs before the issue
  hour). Road cells drawn closed from their closure time. Every place: a dot coloured by its government step and a label
  with its leave-by clock (latest safe departure) or its state ("not cut in 8 h", "inside known fire area", "no safe
  departure"). Labels that would overlap are hidden by MapLibre at region zoom; hovering a dot shows its step and clock.
* **Level 2, place.** Click a place (or one of the six bookmarks). Shelter, witness route on the terrain, latest safe
  departure, planner 30-min strip, and "Check it": re-walks the witness edge by edge from its departure second against
  the issue hour's cell closures (the `analyze.py` `recheck` rule) and shows PASS/FAIL with the arrival second, next to
  the committed arrival it must equal. "One minute later" re-walks the same road from `ld + 60 s` (labelled "this road
  only"). Named places show their reported times as "reported", with outlet, date, URL and SINGLE flag.
* **Level 3, road.** Drive along the witness in about 30 s (a whole-number speed-up; a road under 30 s is slowed down and labelled):
  a chase view 115 m behind and 38 m above the vehicle (a road-level eye over a 30 m terrain model sinks into the slopes),
  terrain exaggeration 1.0. Clock = departure second + committed edge travel ticks; fire = discs time-stamped before that
  moment (reconstruction, delivery latency not modelled) and the issue-hour closures.
* **Sources panel.** Every number element carries `data-src`; a small panel lists the sources of what is on screen.
* **Level 3 crossing view (vehicle, flame wall, verdict) and REOPENED event: not built.** The only logger recordings in
  the repository are synthetic: four simulated sessions in a synthetic city (`hardware/field_logger_demo/sessions`) and the
  phone exporter's synthetic test walks (`hardware/phone_export/samples`);
  there is no vehicle-unit or crossing log for this event, and the frozen rule has no reopening (closures are
  permanent, HOTSPOT_RULE.md).

Test hooks: `window.KCF_APP` = `{ ready: Promise, timings, state (state.view = "region"|"place"|"drive", state.place,
state.drive, …), map, setTime(s), setIssue(k), setStandin(name), selectPlace(idOrName), home(), back(), check(offsetS),
rewalk(placeId, k, departS, standin), drive({manual}?), driveSeek(frac), stopDrive(), idle(), tour: { duration: 90, seek(t),
plan() }, sources() }`.
