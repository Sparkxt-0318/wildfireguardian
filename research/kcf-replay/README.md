# kcf-replay: hour-by-hour screen reconstruction, 25 March 2025 12:00–24:00 KST

Results: [RESULTS.md](RESULTS.md). Rule (frozen first, commit `796e91c`): [HOTSPOT_RULE.md](HOTSPOT_RULE.md). Documented
times re-read at source: [SOURCES.md](SOURCES.md).

| file | content |
|---|---|
| `per_place.csv` | 174 places × 13 issue hours × 3 R(h) stand-ins × 2 horizons (13,572 rows): step, latest safe departure, shelter, arrival, witness road (OSM ways), reconstruction cut time, score flag |
| `named_places_timeline.csv` | 6 named places, every hour/stand-in/horizon, with documented times |
| `timeline.png` | timeline figure for the 6 named places |
| `frames/frame_*.png` | 13 hourly map frames (RUNNING, 8 h); `map_sequence.mp4` = all 73 ten-minute frames, 73 s |
| `planner_cache/RUNNING_8h/` | planner cache (schema `wfg.planner.cache/1`), 13 issue hours × 2 regions |
| `score.json`, `fixed_point.json`, `ahi_firms_agreement.json` | score, F-3.1 certificate, AHI/FIRMS diagnostic |
| `fire_discs.json` | the known-fire-area inputs (every kept FIRMS detection and AHI hotspot with time and radius) |

## 3D scene (presentation)

One browser scene with three zoom levels (region, place, road) replays these results on 3D terrain:
[`planner/public/kcf-scene/`](../../planner/public/kcf-scene/README.md), published with the planner demo at
`https://sparkxt-0318.github.io/wildfireguardian/kcf-scene/` and runnable offline by double-clicking its `index.html`.
Builders, checks (`scene/VERIFY.json`), load-time measurement, the presenter's one-page click script and the 90 s fallback
recording are in [`scene/`](scene/DESIGN.md).

## Play it in the planner demo

```bash
cd planner && npm ci
```

```bash
WFG_CACHE_DIR=../research/kcf-replay/planner_cache/RUNNING_8h VITE_WFG_API_MODE=static npx vite --mode static
```

Open `?region=yeongdeok_2025&scenario=kcf-replay:RUNNING:8h:20250325T100000Z` (19:00 KST) or pick any 12:00–24:00 KST
input in the left panel. The app marks the data as test data (not the evaluated host). Verdicts come from the F-3.1
field with stand-in closures, not from the Route-Check API.

## Reproduce (from the repository root)

```bash
python3 tools/fetch_routing_inputs.py
```

```bash
pip install pyproj matplotlib numpy
```

```bash
cd research/kcf-replay && python3 fire_area.py out/fire_discs.json && python3 replay.py out/fire_discs.json out/runs --workers 4
```

```bash
cd research/kcf-replay && python3 analyze.py out/fire_discs.json out/runs out/an && python3 figures.py out/fire_discs.json out/runs out/fig && python3 verify_fixed_point.py out/fire_discs.json out/fixed_point.json && python3 ahi_firms_agreement.py out/fire_discs.json out/ahi_firms_agreement.json && python3 named_timeline.py out/an/per_place.csv named_places_timeline.csv && python3 make_planner_cache.py out/runs planner_cache/RUNNING_8h --standin RUNNING --horizon 8h
```

`replay.py` takes about 1 h on 4 cores (Yeongdeok: 151 shelters, about 3.5 min per issue-hour job).

## When research/kcf-margin lands

Put the frozen R(h) into `STANDINS` in `replay.py` as a new label (keep the three stand-ins), rerun `replay.py` with
`--standins <LABEL>`, then rerun the post-processing. `HOTSPOT_RULE.md` does not change.
