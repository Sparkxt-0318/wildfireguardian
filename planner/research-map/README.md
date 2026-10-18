# 산불 레이어 지도 (research map)

A 3D/2D map that replays the research for all five study regions (울진 2022, 밀양 2022, 홍성 2023, 의성·안동 2025,
영덕 2025): recorded burned area and fire front, the model's next-hour probability q, the four-scenario radiant heat
flux used by routing, the recorded Route-Check results under five constraint policies, the planner's booth-cache
results for every origin, a comparison with prior approaches, and the field route-logger resources. It is a
presentation and explanation tool for the booth. It computes no forecasts or routes; everything it draws comes from
recorded files in this repository, and the illustrative layers are marked ✱.

## Open it

`site/` is self-contained and works offline from `file://` (three.js r128 is vendored in `site/vendor/`):

```bash
open planner/research-map/site/index.html          # macOS; any recent Chrome, Edge or Safari
```

Hash options (combine with `&`): `region=uljin_2022|miryang_2022|hongseong_2023|uiseong_andong_2025|yeongdeok_2025`,
`lang=en`, `tab=pLayers|pOverview|pEvac|pRoute|pCompare|pModel|pDocs`, `mode=2d`, `case=0..3`,
`cmp=spread|travel|ours`, `t=<hours from the first record>`, `lite=1` (no bloom, fewer trees and a 1× pixel ratio
for slower machines and projectors). The region and language choice are also remembered in `localStorage`.

## Publish on Vercel

`site/` is a static site with no build step (`site/vercel.json` only sets cache headers). One-time setup on
vercel.com: **Add New → Project → Import** `Sparkxt-0318/wildfireguardian` → **Root Directory**
`planner/research-map/site` → **Framework Preset** "Other", leave Build and Output empty → **Deploy**. Every push to
Main then redeploys it. The site is public: anyone with the URL can see the map and its data (all of it is already
in this repository).

## What each part shows

| Part | Source | Notes |
|---|---|---|
| Terrain, slope | AWS Terrain Tiles (Terrarium) | resampled per region; below sea level drawn as sea; heights ×3 by default |
| Base map, names, peaks | `planner/public/basemap/<region>.pmtiles` | © OpenStreetMap contributors (ODbL) |
| Burned state, fire front | `planner/public/data/regions/<region>/footprints.geojson`, forecast fixtures | recorded (reconstructed) |
| q (next hour) | `planner/mock_api/fixtures/forecast/<region>/` | model output; valid 1 h after each input, never interpolated |
| Heat flux F(x), 4 scenarios | routing hazard packets (`HAZARD.json`, release extracts) | drawn from 0.01 kW/m²; 1 h after each input |
| Route checks, 5 policies | `planner/mock_api/fixtures/records/<region>/` | verdicts and exposure as recorded; the on-screen dose is a cell-centre recomputation, labelled as such |
| 대피 현황 (evacuation status) | `planner/cache/` (booth cache, real Route-Check API) | 의성·안동 and 영덕 only |
| 기존 연구 비교 | records' `full_policy_check`; poster Table 1 | the presets show only the kind of output each approach produces; they are not runs of those tools |
| 자료 (route logger) | WildfireGuardian Route Logger build manual (Oct 2026) | summary and figures; the manual states no purpose, sample rate or cost, so none is shown |
| ✱ temperature, wind, canopy, biome | synthetic | illustrative patterns, not model inputs |
| F(h) hourly Monte Carlo | `tools/run_hourly_export.sh` output | empty until a real export is merged (below) |

The comparison tab's map marks where a travel-time-only route passes a flame cell, recomputed at cell centres from the
hazard packets. It agrees with the recorded full-policy check in all 20 cases (8 fail; 3 of those get a checked
detour, 5 are no route in the model).

## Rebuild

Prerequisites: `cd planner && npm ci` (the OSM extractor uses the planner's `pmtiles` and `@mapbox/vector-tile`),
`planner/scripts/fetch_planner_assets.sh` (hazard packets from the verified release extracts), Python with
`numpy`, `shapely`, `pyproj` (see `planner/tools/requirements.txt`) and `pillow`.

```bash
cd planner/research-map
python3 tools/build_regions.py      # site/regions/<id>.js + index.js (downloads DEM tiles once into .cache/)
python3 tools/build_viewer.py       # site/index.html from src/
PLAYWRIGHT_MODULE=/path/to/node_modules/playwright node tools/bake_textures.mjs   # site/regions/<id>.tex.js: pre-built terrain
python3 tools/build_viewer.py --cdn /tmp/page.html   # page fragment with CDN scripts, for hosting
```

`tools/bake_textures.mjs` lets the page draw each region's static terrain once in headless Chromium and saves the
images, so visitors decode them instead of drawing for several seconds; rerun it after `build_regions.py` (a stale file
is ignored by key and the page draws instead). `.cache/` (DEM tiles, OSM extracts, merged hourly files) is not committed. The region bundles are deterministic:
a rebuild from the same inputs is byte-identical.

### Hourly cumulative probability F(h)

The F(h) layer needs the KFS_01 environmental rasters, which are not on GitHub (`forecast/README.md`, External
inputs). On a machine that has them:

```bash
bash planner/research-map/tools/run_hourly_export.sh            # writes ./kfs01_hourly.npz (c651 checkpoint, 1024 samples)
python3 tools/merge_hourly.py kfs01_hourly.npz uiseong_andong_2025 yeongdeok_2025
python3 tools/build_regions.py --only uiseong_andong_2025,yeongdeok_2025
```

A synthetic rehearsal export is refused by `build_regions.py`.

## Licences

three.js r128 (`site/vendor/`): MIT, © three.js authors. Map data © OpenStreetMap contributors (ODbL 1.0).
Terrain: AWS Terrain Tiles (Mapzen Terrarium; SRTM, GMTED and other public sources). Route logger figures: from the
project's own build manual.
