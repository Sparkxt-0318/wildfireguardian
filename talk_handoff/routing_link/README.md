# routing_link: exposure fields as road-blocking times (Fish Creek)

**Status (25 Nov 2026): v2 done (per-path heat and CO, PROTOCOL.md Amendments 2–5): `RESULTS_v2.md`,
`RESULTS_all_v2.pdf`, figures `fig_blocked_cells_v2.*` and `fig_safety_zone.*`.** At the main v2 setting (share of
paths ≥ 0.5, half-of-paths fire) exposure still blocks no road and changes no origin; radiant heat never reaches
2.5 kW/m² on the 375 m grid in any path. v1 below, unchanged.

**v3 (25 Nov 2026): protocol written, not run.** `PROTOCOL_v3.md`: moving flame front instead of whole-cell fire
arrival, crown fire from the canopy layers, radiant and thermal-dose heat, CO, acrolein and HCN at AEGL-2; smoke
visibility reported only. Part B (a second fire) waits for the user's approval.

**v1 (25 Nov 2026): done. Results in `RESULTS.md`, figure `fig_blocked_cells.{png,svg,pdf}`.** At the protocol's
settings exposure blocks no cell and no road on Fish Creek in hours 0–5 and changes no last safe departure (0 of 350
origins, residents and responders). The pipeline came from the user's `wildfire4.zip` (PROTOCOL.md Amendment 1).

| file | what |
|---|---|
| `PROTOCOL.md` | blocking rule, thresholds, what will be reported; committed before any result |
| `SOURCES.md` | each threshold checked against its source, full citations, what could not be opened |
| `NEEDS.md` | what is missing and what unblocks it |
| `blocking.py` | exposure fields -> first blocked minute per cell (radiant 2.5 / 7.0 kW/m², CO AEGL-2 10/30/60 min running means across hours, visibility p ≥ 0.1 / 0.5 / 0.9); PM2.5 never blocks |
| `osm_graph.py` | OpenStreetMap -> road-layer graph on the Fish Creek grid (EPSG:5070, 375 m), same rules as the Korean graphs; origins = OSM populated places (or junctions if none); exits = map edge |
| `route.py` | the road layer's own raster rules, instance, backward passes and per-origin assembly (`product/wfg-roadlayer`, unchanged) on that graph |
| `run_all.py` | end to end: rasters, the two road-layer runs per audience and visibility level, the counts, the figure |
| `figure.py` | the one figure (five colours, transparent, no title) |
| `export_fishcreek.py` | runs the pipeline for hours 0–5 with the saved example's settings and exports what `run_all.py` reads |
| `RESULTS.md`, `fig_blocked_cells.*` | the results and the figure |
| `RESULTS_all.pdf`, `build_report.py` | every result, check, threshold source and limit in one PDF, with the figure; built from the committed outputs (`python3 build_report.py`) |
| `export_6h/`, `out_earliest/`, `out_half/` | exported exposure and fire arrival; run outputs |
| `tests/` | 21 synthetic tests (`python3 -m pytest -q tests`): 13 v1, 8 for the per-path rule |
| `perpath_export.py` | v2: per-path 60 s radiant and CO for all 1,024 paths, shares per criterion, minute and cell; checks |
| `perpath_rule.py` | v2: share-of-paths blocking rule (levels 0.5 main, 0.1, 0.9, any path) |
| `run_v2.py` | v2: blocking rasters, road-layer runs (both audiences, four levels, both fire readings), v1 beside v2, figure |
| `safety_zone_export.py`, `safety_zone_fine.py`, `safety_zone.py` | the safety-zone figure (Amendments 3–5): one path, one minute, zone at 375 m and 5 m, routing |
| `diag_co_check.py`, `diag_radiant.py` | v2 diagnostics: CO mean check; flame-front geometry and power |
| `build_report_v2.py` | builds `RESULTS_all_v2.pdf` from the committed v2 outputs |
| `co_paths_zone_export.py`, `co_paths_zone.py` | Amendment 6: safety zone and four-way routing on the 273 paths where CO blocks a road cell (section 8 of RESULTS_v2.md) |
| `RESULTS_v2.md`, `RESULTS_all_v2.pdf`, `fig_blocked_cells_v2.*`, `fig_safety_zone.*` | v2 results and figures |
| `export_v2/`, `out_v2/` | v2 per-path counts, peaks, distances, checks, safety-zone data; v2 run outputs |

## Fish Creek road network (built, 24 Nov 2026)

* OSM extract `data/fishcreek_osm_20240823.json.gz` (provenance in `data/OSM_SOURCE.json`; Overpass mirror, the
  2024-08-23 historical filter requested but not verified to have been applied by the mirror).
* Graph: 12,670 nodes, 25,436 directed road pieces (tracks 16,144; unclassified 6,792; service 1,526; trunk 746;
  residential 228); 109 private/no-access ways excluded; 569 footpaths not drivable.
* **No populated place or shelter in the area** (the only place tag is a `locality`, Jules Bowl; four campgrounds,
  no shelter). As the protocol says, the origins are the **360 road junctions** and the destinations are the **59
  points where roads leave the map edge**.
* Plumbing check, not a result: with the observed reconstructed arrival (data folder `arrival_time_hours.tif`,
  shifted to the 2024-08-23T00:00Z issue time, 6 h horizon) the road layer ran in 20 s (59 backward passes, one
  process); 350 of 360 junctions routed, 10 refused NO_ROAD_PATH (road fragments with no way to the map edge). None
  of the 1,293 road cells lies in the 207 observed burned or 6 h reached cells, so fire arrival alone blocked no
  road in that check. The forecast arrival may differ; the run_all result is what counts.
* Figure layout checked on the real roads with a dummy block (not committed).

## Reproduce

1. In the pipeline workspace (Python 3.12 with its pinned `pyproject.toml` versions), from the workspace root:
   `PYTHONPATH=. python /path/to/export_fishcreek.py --out EXPORT_DIR` (about 2.5 min; writes `hour_00..05.npz`,
   `fire_arrival_earliest.tif`, `fire_arrival_half.tif`, `checks.json`). The committed copy is `export_6h/`.
2. For each fire version V in `earliest`, `half`:
   `python3 run_all.py --hours export_6h --fire export_6h/fire_arrival_V.tif --grid /Users/jp/Desktop/wildfire/data/environment/regions/WY-BTF-002416_FishCreek/grid.json --osm data/fishcreek_osm_20240823.json.gz --out out_V --workers 1`
   (about 2.5 min each).

## Limits (to be repeated in RESULTS.md)

One fire; uncalibrated exposure; thresholds made for buildings or workplaces, not for people in vehicles; no Korean
case, because Korea has no fuel maps. The visibility criterion is an assumption (10 m building-egress reference, 0.5
level our choice).

## Reproduce v2 (Amendments 2–5)

1. In the pipeline workspace (same environment as v1), from its root, with `PYTHONPATH=.`:
   `python perpath_export.py --out export_v2 --v1 export_6h` (about 6 min),
   `python diag_co_check.py --v1 export_6h --out export_v2`, `python diag_radiant.py`,
   `python safety_zone_export.py --out export_v2`, then
   `python safety_zone_fine.py --grid GRID_JSON --osm data/fishcreek_osm_20240823.json.gz --out export_v2` with and
   without `--terrain-plane` (paths relative to this folder).
2. Here: `python3 run_v2.py --v2 export_v2 --v1 export_6h --grid GRID_JSON --osm data/fishcreek_osm_20240823.json.gz --out out_v2`
   (about 7 min), `python3 safety_zone.py --grid GRID_JSON --osm data/fishcreek_osm_20240823.json.gz`,
   `python3 build_report_v2.py`.
3. Amendment 6: in the workspace, `python co_paths_zone_export.py --grid GRID_JSON --osm data/fishcreek_osm_20240823.json.gz --out export_v2`;
   here, `python3 co_paths_zone.py --grid GRID_JSON --osm ... --shard i/10` for i = 0 … 9 (in parallel), then `--merge`.
