# KCF replay — one 3D scene, three zoom levels

What a screen would have shown on 25 March 2025, 12:00–24:00 KST, for the 174 planner places of 의성·안동 and 영덕, replayed
from the committed results of [`research/kcf-replay`](../../../research/kcf-replay/RESULTS.md). It is a reconstruction from the
2025 record and is marked as test data (시험 데이터 · 평가 호스트 아님) on every view. It is not a claim about outcomes.

## Open it

* **Published site:** `https://sparkxt-0318.github.io/wildfireguardian/kcf-scene/` (this folder is copied verbatim into the
  planner's static build by `.github/workflows/planner-pages.yml`). No login, no install.
* **Offline:** copy this whole `kcf-scene` folder (about 20 MB) to the laptop and double-click `index.html`. It needs no
  server and no network: every file is a classic script, and MapLibre reads terrain tiles and glyphs from memory.
  Chrome, Edge, Firefox and Safari all work from `file://`.
* `?lite` for a slow machine (1× pixel ratio, coarser fire discs). Deep links: `?t=18:00`, `?place=지품리`, `?standin=WORST`.

## The three levels

| level | what | how |
|---|---|---|
| 1 Region | 3D terrain (Terrain Tiles, z5–12). Time slider over the 13 issue hours. Known fire area = every kept FIRMS detection and AHI hotspot time-stamped before the issue hour (`fire_discs.json`, rule frozen in `HOTSPOT_RULE.md`). Road cells (375 m) turn violet at issue time + distance / R(h). Every place: a dot coloured by its government step and a label with its leave-by clock (latest safe departure). | ←/→ issue hour, Space play, R stand-in |
| 2 Place | Click a place or a bookmark (the six places of RESULTS.md §4, keys 1–6). Shelter, witness road on the terrain, latest safe departure, arrival, the planner's 30-min strip, all 13 screens, and for the six named places the reported times (as *reported*, with outlet, date, link and the SINGLE flag). **Check it** re-walks the witness road edge by edge against that hour's closures (the `analyze.py` rule) and shows PASS/FAIL with the arrival second next to the committed one. **One minute later** re-walks the same road from 60 s later. | C, L |
| 3 Road | Chase view along the witness road from the latest safe departure, sped up to about 30 s (real time when the drive is shorter). Clock = departure second + edge travel ticks; fire = detections time-stamped before each moment; violet = cells that hour's screen has closed. | D, Esc |

**Sources panel** (S, bottom left): every number on screen sits in an element with its source path (hover for the row and column);
the panel lists the committed files behind everything visible.

## Not in this scene

* **Crossing view (vehicle, flame wall, verdict) and a REOPENED event.** The repository has no vehicle-unit or crossing log for this
  event: the only logger recordings are four explicitly simulated city sessions (`hardware/field_logger_demo/sessions`), and the
  frozen rule never reopens a closed cell (`HOTSPOT_RULE.md`: closures are permanent).
* **MEASURED arms.** `research/kcf-replay` has only the three labelled R(h) stand-ins (ORDINARY, RUNNING, WORST); the frozen R(h) of
  `research/kcf-margin` has not been run through this replay, so no MEASURED arm is shown.

## Files

| file | built by | from |
|---|---|---|
| `data/scene.js` | `research/kcf-replay/scene/build_scene.py`, checked by `verify_scene.py` → `VERIFY.json` | `per_place.csv`, `fire_discs.json`, `planner_cache/RUNNING_8h`, `SOURCES.md`, `named_places_timeline.csv`, `score.json`, `planner/public/data/regions/*/places.geojson`; road graph and witness edges from the SHA-pinned release inputs (`tools/fetch_routing_inputs.py`) and `replay.py` runs, checked to reproduce `per_place.csv` exactly |
| `data/terrain.js` | `build_terrain.py` | Terrain Tiles (Mapzen, AWS Open Data; SRTM, GMTED, ETOPO1), Terrarium z5–12, 1 m steps |
| `data/basemap.js` | `build_basemap.py` | `planner/research-map/site/regions/*.osm.js`, `planner/data/osm/*.overpass.json` (© OpenStreetMap contributors, ODbL) |
| `data/fonts.js` | `build_fonts.py` | Noto Sans glyphs from `planner/public/basemap/fonts`; a subset of Pretendard (SIL OFL, renamed "KCF UI Sans") |
| `vendor/` | `build_vendor.py` | MapLibre GL JS 5.24.0 (BSD-3-Clause) |

Design and data contract: [`research/kcf-replay/scene/DESIGN.md`](../../../research/kcf-replay/scene/DESIGN.md). Tests, load-time
measurement and the presenter's click script: `research/kcf-replay/scene/`.
