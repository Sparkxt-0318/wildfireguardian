# routing_link: exposure fields as road-blocking times (Fish Creek)

**Status (24 Nov 2026): protocol frozen, code written and tested on synthetic inputs, no result yet.** The exposure
pipeline and its saved example are not on this machine (NEEDS.md), so there is no RESULTS.md and no figure from real
data. Nothing in this folder is a Fish Creek number.

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
| `tests/` | 13 synthetic tests (`python3 -m pytest -q tests`) |

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

## When the pipeline is here

1. From the saved run, write one `hour_HH.npz` per consecutive forecast hour with the keys in `blocking.HourFields`
   (binwise radiant flux and CO if the run keeps them; otherwise accumulated thermal energy and hourly mean CO, and
   the outputs then say which checks are lower bounds or not computable), and the fire-arrival raster in the road
   layer's format on the same grid.
2. `python3 run_all.py --hours EXPORT_DIR --fire fire_arrival.tif --grid /Users/jp/Desktop/wildfire/data/environment/regions/WY-BTF-002416_FishCreek/grid.json --osm data/fishcreek_osm_20240823.json.gz`
3. Write RESULTS.md from `out/summary.json`, every number with its n.

## Limits (to be repeated in RESULTS.md)

One fire; uncalibrated exposure; thresholds made for buildings or workplaces, not for people in vehicles; no Korean
case, because Korea has no fuel maps. The visibility criterion is an assumption (10 m building-egress reference, 0.5
level our choice).
