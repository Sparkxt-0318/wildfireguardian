# KCF replay — one 3D scene, three zoom levels

What a screen would have shown on 25 March 2025, 12:00–24:00 KST, for the 174 planner places of 의성·안동 and 영덕, replayed
from the committed results of [`research/kcf-replay`](../../../research/kcf-replay/RESULTS.md). It is a reconstruction from the
2025 record and is marked as test data (시험 데이터 · 평가 호스트 아님) on every view. It is not a claim about outcomes.

## Open it

* **Offline (primary for the talk):** copy this whole `kcf-scene` folder to the laptop and open `index.html` in Chrome or
  Edge. It needs no server and no network: every file is a classic script, and MapLibre reads terrain tiles and glyphs from
  memory. Tested from `file://` in Chromium only (`research/kcf-replay/scene/tests/smoke.mjs`); Firefox and Safari use the same
  standard features but were not tried. The 90-s fallback recording `kcf_scene_tour_90s.mp4` is in this folder.
* **Published site:** `https://sparkxt-0318.github.io/wildfireguardian/kcf-scene/`, **live only once this folder is on `Main`**
  (merge the pull request; `.github/workflows/planner-pages.yml` then copies `planner/public` verbatim into the static build and
  deploys it). No login, no install. Open it once cold before the talk to confirm the deploy.
* `?lite` forces lite mode (no colour relief, 1× pixel ratio, coarser fire discs, lower drive camera); it switches on by itself when
  the browser has no GPU (a notice says so), and `?full` overrides that. Deep links: `?t=18:00`, `?place=지품리`, `?standin=MEASURED` (or `RUNNING`, `MEASURED_GUST_KMA`, `MEASURED_GUST`, `WORST`, `ORDINARY`).

## R(h) arms

Every number depends on R(h), the fire's reach after h hours. The scene has the six arms of `research/kcf-replay`, cycled with
**R** (bottom right shows the active one): **RUNNING** (default, 8.2 km/h; the only arm with a planner cache), **MEASURED**,
**MEASURED+GUST**, **WORST** and **ORDINARY**. RUNNING, WORST and ORDINARY are labelled stand-ins. The two MEASURED arms are the
frozen R(h) of `research/kcf-margin` (`MEASURED_RULE.md`): one class per issue hour for all places, picked by the prior-3 h
spread of the known fire area (quiet / slow / running) or by the maximum gust over the next 8 h (KMA ASOS hourly series, primary; ERA5, secondary), with R(5 h) and R(8 h)
from `research/kcf-margin/numbers.json` and the curve through (0, 0), (5 h, R5), (8 h, R8). **MEASURED+GUST (ERA5, secondary) is
PROVISIONAL** (ERA5 gusts only); MEASURED+GUST (KMA) is the primary gust arm. The ≥ 20 m/s class rests on 9 fires in both. Each place panel shows the same screen under all six arms; they are
different R(h), not a ranking.

## The three levels

| level | what | how |
|---|---|---|
| 1 Region | 3D terrain (Terrain Tiles, z5–12). Time slider over the 13 issue hours. Known fire area = every kept FIRMS detection and AHI hotspot time-stamped before the issue hour (`fire_discs.json`, rule frozen in `HOTSPOT_RULE.md`). Road cells (375 m) turn violet at the issue time + the time R(h) takes to reach them; each hourly screen recomputes every closure from its own known fire area, so at an issue hour some cells the previous screen had closed show open again until their new closure time (a new screen, not a reopening). Every place: a dot coloured by its government step, and a label with its leave-by clock (latest safe departure). At region zoom MapLibre hides labels that would overlap; hover a dot (or zoom in) for its step and clock. | ←/→ issue hour, Space play, R R(h) arm |
| 2 Place | Click a place or a bookmark (the six places of RESULTS.md §4, keys 1–6). Shelter, witness road on the terrain, latest safe departure, arrival, the planner's 30-min strip, all 13 screens, and for the six named places the reported times (as *reported*, with outlet, date, link and the SINGLE flag). **Check it** re-walks the witness road edge by edge against that hour's closures (the `analyze.py` rule) and shows PASS/FAIL with the arrival second next to the committed one. **One minute later** re-walks the same road from 60 s later. | C, L |
| 3 Road | Chase view along the witness road from the latest safe departure, played in about 30 s: a whole-number speed-up, or, for a road shorter than 30 s, slowed down and labelled "slowed" in the HUD. When the vehicle enters a detection disc, or the full record reached the road before the departure (per_place.csv `route_cut_before_departure`), the HUD says so in red; the arrival is shown as that screen's projection, not an outcome. Clock = departure second + edge travel ticks; fire = detections time-stamped before each moment; violet = cells that hour's screen has closed. | D, Esc |

**Sources panel** (S, bottom left): every number on screen sits in an element with its source path (hover for the row and column);
the panel lists the committed files behind everything visible.

## Not in this scene

* **Crossing view (vehicle, flame wall, verdict) and a REOPENED event.** The repository has no vehicle-unit or crossing log for this
  event: the only logger recordings are synthetic (four simulated city sessions in `hardware/field_logger_demo/sessions`, and the
  phone exporter's synthetic test walks in `hardware/phone_export/samples`), and the frozen rule has no reopening event: within one
  screen a closed cell stays closed to the end of its 8 h horizon (`HOTSPOT_RULE.md`).

## Files

| file | built by | from |
|---|---|---|
| `data/scene.js` | `research/kcf-replay/scene/build_scene.py`, checked by `verify_scene.py` → `VERIFY.json` | `per_place.csv`, `fire_discs.json`, `planner_cache/RUNNING_8h`, `SOURCES.md`, `named_places_timeline.csv`, `score.json`, `RESULTS.md` (§2–5), `MEASURED_RULE.md` + `measured_arms.py` + `research/kcf-margin/numbers.json` + `research/kcf-gust/work/gust_hours.json` (MEASURED arms), `planner/public/data/regions/*/places.geojson`; road graph and witness edges from the SHA-pinned release inputs (`tools/fetch_routing_inputs.py`) and `replay.py` runs, checked to reproduce `per_place.csv` exactly |
| `data/terrain.js` | `build_terrain.py` | Terrain Tiles (Mapzen, AWS Open Data; SRTM, GMTED, ETOPO1), Terrarium z5–12, 1 m steps, clipped to the scene's bbox at every zoom |
| `data/basemap.js` | `build_basemap.py` | `planner/research-map/site/regions/*.osm.js`, `planner/data/osm/*.overpass.json` (© OpenStreetMap contributors, ODbL) |
| `data/fonts.js` | `build_fonts.py` | Noto Sans glyphs from `planner/public/basemap/fonts`; a subset of Pretendard (SIL OFL, renamed "KCF UI Sans") |
| `vendor/` | `build_vendor.py` | MapLibre GL JS 5.24.0 (BSD-3-Clause) |
| `kcf_scene_tour_90s.mp4` | `research/kcf-replay/scene/tests/record_tour.mjs` | the scene's own deterministic tour (`?tour=1&full`), captured frame by frame at 1920×1080, 24 fps |

Design and data contract: [`research/kcf-replay/scene/DESIGN.md`](../../../research/kcf-replay/scene/DESIGN.md). Tests, load-time
measurement and the presenter's click script: `research/kcf-replay/scene/`.
