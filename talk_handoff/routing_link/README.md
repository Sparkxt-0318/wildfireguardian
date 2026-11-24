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

## When the pipeline is here

1. From the saved run, write one `hour_HH.npz` per consecutive forecast hour with the keys in `blocking.HourFields`
   (binwise radiant flux and CO if the run keeps them; otherwise accumulated thermal energy and hourly mean CO, and
   the outputs then say which checks are lower bounds or not computable), and the fire-arrival raster in the road
   layer's format on the same grid.
2. `python3 run_all.py --hours EXPORT_DIR --fire fire_arrival.tif --grid /Users/jp/Desktop/wildfire/data/environment/regions/WY-BTF-002416_FishCreek/grid.json --osm data/fishcreek_osm_20240823.json`
3. Write RESULTS.md from `out/summary.json`, every number with its n.

## Limits (to be repeated in RESULTS.md)

One fire; uncalibrated exposure; thresholds made for buildings or workplaces, not for people in vehicles; no Korean
case, because Korea has no fuel maps. The visibility criterion is an assumption (10 m building-egress reference, 0.5
level our choice).
